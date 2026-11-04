#!/usr/bin/env python3
"""Start bounded local snapshots and observed file-change records, without AI or network."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

try:
    import fcntl
except ImportError:
    fcntl = None

SKILLS = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


records = load('session_records', SKILLS / 'record-work/scripts/init_records.py')
checkpoint = load('session_checkpoint', SKILLS / 'git-checkpoint/scripts/checkpoint.py')


def now():
    return datetime.now(timezone.utc).isoformat()


def regular(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('session metadata/document path must be a regular file: ' + str(path))


def workspace(root):
    root = Path(root).resolve()
    if not root.is_dir() or any((p / '.toolkit-package').exists() for p in (root, *root.parents)):
        raise ValueError('choose the existing task workspace outside the toolkit distribution')
    return root


def storage(root):
    # Automatic task state is ordinary workspace data, never managed Git metadata.
    dest = root / '.local/ai-toolkit/snapshots'
    for directory in [root / '.local', root / '.local/ai-toolkit', dest]:
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ValueError('local storage path conflict: ' + str(directory))
    dest.mkdir(parents=True, exist_ok=True)
    for name in ['session.lock', 'session.json', 'session-stop.json', 'session.log', 'writer.lock']:
        regular(dest / name)
    return dest


def read_state(dest):
    path = dest / 'session.json'
    regular(path)
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ValueError('unrecognized session state; preserve and inspect ' + str(path))
    return value


def write_state(dest, state, filename='session.json'):
    regular(dest / filename)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=dest, delete=False) as stream:
        path = Path(stream.name)
        try:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.replace(path, dest / filename)
        finally:
            path.unlink(missing_ok=True)


def acquire(dest):
    if fcntl is None:
        raise ValueError('automatic background sessions require Linux or macOS')
    regular(dest / 'session.lock')
    fd = os.open(dest / 'session.lock', os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def status(root):
    root = workspace(root)
    dest = storage(root)
    state = read_state(dest)
    fd = acquire(dest)
    if fd is not None:
        os.close(fd)
        if state.get('status') in {'running', 'starting'}:
            state['status'] = 'interrupted'
    elif not state:
        state = {'status': 'starting'}
    return {**state, 'status': state.get('status', 'not_started'), 'active': fd is None, 'storage': str(dest)}


def selected(root):
    return sorted(p.name for p in root.iterdir()
                  if not p.is_symlink() and not checkpoint.excluded(Path(p.name))
                  and p.name not in checkpoint.SKIP_DIRS
                  and not (p.is_dir() and (p / '.toolkit-package').is_file())
                  and (not p.name.startswith('.') or p.name in checkpoint.NAMES))


def save(root, dest, state):
    lock = dest / 'writer.lock'
    regular(lock)
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ValueError('another snapshot writer or stale writer.lock exists; preserve and inspect it') from error
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        result = checkpoint.snapshot(root, dest, selected(root), keep=20,
                                     allowed_extensions=checkpoint.EXTENSIONS - {'.csv'})
        if result['status'] == 'no-files':
            raise ValueError('no eligible saved source/config/document files; no snapshot created')
        if result['status'] == 'saved':
            with zipfile.ZipFile(result['path']) as archive:
                hashes = json.loads(archive.read('manifest.json'))['hashes']
            source = {p: h for p, h in hashes.items() if p not in {'devlog.md', 'probe.md'}}
            previous = state.get('source_hashes', {})
            changed = sorted(p for p in source.keys() | previous.keys() if source.get(p) != previous.get(p))
            if changed and state['records']:
                path = root / 'devlog.md'
                regular(path)
                with path.open('a', encoding='utf-8') as stream:
                    stream.write('\n### ' + now() + ' · 자동 파일 관측\n\n')
                    stream.write('스냅샷에 관측된 파일 상태 변화다. 변경 목적·구현 완료·테스트 통과를 추정하지 않는다.\n\n')
                    for name in changed[:30]:
                        label = name.replace('`', '').replace('\n', ' ')
                        stream.write('- `' + label + '` · ' + (source[name][:16] if name in source else '스냅샷 선택 범위에서 사라짐') + '\n')
                    if len(changed) > 30:
                        stream.write('- 추가 변화 ' + str(len(changed) - 30) + '개: 스냅샷 manifest 참조\n')
            state['source_hashes'] = source
        if result['status'] == 'unchanged' and state.get('last_snapshot', {}).get('path'):
            result['path'] = state['last_snapshot']['path']
        state['last_snapshot'] = {k: v for k, v in result.items() if k != 'skipped'}
        state['last_snapshot']['skipped_count'] = len(result.get('skipped', []))
        state['last_snapshot']['skipped'] = result.get('skipped', [])[:30]
        state['updated_utc'] = now()
    finally:
        lock.unlink(missing_ok=True)


def start(root, interval=180, duration=10800, create_records=True):
    root = workspace(root)
    if not all(math.isfinite(v) and v > 0 for v in [interval, duration]) or duration > 10800:
        raise ValueError('positive finite interval/duration required; maximum duration is 10800 seconds')
    if create_records:
        records.validate_target(root)
    dest = storage(root)
    fd = acquire(dest)
    if fd is None:
        for _ in range(100):
            state = status(root)
            if state['status'] != 'starting':
                return {**state, 'action': 'already_running'}
            time.sleep(0.03)
        raise ValueError('existing session startup not confirmed; inspect status')
    process = None
    try:
        previous = read_state(dest)
        if create_records:
            records.initialize(root)
        state = {'version': 1, 'root': str(root), 'token': uuid.uuid4().hex,
                 'status': 'starting', 'started_utc': now(), 'interval': interval,
                 'duration': duration, 'records': create_records,
                 'source_hashes': previous.get('source_hashes', {})}
        write_state(dest, state)
        with (dest / 'session.log').open('ab') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker', '--root', str(root),
                                        '--lock-fd', str(fd)], cwd=root, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=log, start_new_session=True, pass_fds=(fd,))
    finally:
        # The child inherits the locked open-file description. Do not LOCK_UN here.
        os.close(fd)
    for _ in range(100):
        state = read_state(dest)
        if state.get('status') != 'starting':
            if state.get('status') == 'error':
                raise ValueError(state.get('error', 'background worker failed'))
            return {**state, 'action': 'started', 'storage': str(dest)}
        if process.poll() is not None:
            raise ValueError('background worker exited; inspect ' + str(dest / 'session.log'))
        time.sleep(0.03)
    raise ValueError('background startup not confirmed; inspect session status before retrying')


def stop(root):
    root = workspace(root)
    current = status(root)
    if current['status'] not in {'running', 'starting'}:
        return current
    dest = storage(root)
    regular(dest / 'session-stop.json')
    write_state(dest, {'token': current.get('token')}, filename='session-stop.json')
    for _ in range(100):
        current = status(root)
        if not current['active']:
            return current
        time.sleep(0.05)
    raise ValueError('stop not confirmed; inspect status without killing unrelated processes')


def worker(root, lock_fd):
    root = workspace(root)
    dest = storage(root)
    expected, inherited = (dest / 'session.lock').stat(), os.fstat(lock_fd)
    if (expected.st_dev, expected.st_ino) != (inherited.st_dev, inherited.st_ino):
        raise ValueError('invalid inherited session lock')
    state = read_state(dest)
    state.update(pid=os.getpid(), status='running')
    deadline = time.monotonic() + state['duration']
    try:
        save(root, dest, state)
        write_state(dest, state)
        next_save = time.monotonic() + state['interval']
        while True:
            request = dest / 'session-stop.json'
            regular(request)
            requested = request.exists() and json.loads(request.read_text()).get('token') == state['token']
            if requested or time.monotonic() >= deadline:
                save(root, dest, state)
                # Include an observation appended during the final source snapshot.
                save(root, dest, state)
                state.update(status='stopped' if requested else 'expired', ended_utc=now())
                break
            if time.monotonic() >= next_save:
                save(root, dest, state)
                write_state(dest, state)
                next_save = time.monotonic() + state['interval']
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    except Exception as error:
        state.update(status='error', error=str(error), ended_utc=now())
    finally:
        write_state(dest, state)
        os.close(lock_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'status', 'stop', 'worker'])
    parser.add_argument('--root', default='.')
    parser.add_argument('--interval', type=float, default=180)
    parser.add_argument('--duration', type=float, default=10800)
    parser.add_argument('--no-records', action='store_true')
    parser.add_argument('--lock-fd', type=int)
    args = parser.parse_args()
    try:
        if args.action == 'worker':
            if args.lock_fd is None:
                raise ValueError('worker is internal; use start')
            worker(args.root, args.lock_fd)
            return 0
        result = (start(args.root, args.interval, args.duration, not args.no_records) if args.action == 'start'
                  else status(args.root) if args.action == 'status' else stop(args.root))
        result.pop('source_hashes', None)
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result['status'] in {'error', 'interrupted'} else 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
