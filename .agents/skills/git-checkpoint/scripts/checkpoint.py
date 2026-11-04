#!/usr/bin/env python3
"""Bounded local snapshots. Never stages, commits, pushes, or restores over work."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time
from datetime import datetime, timezone
import zipfile

MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 20 * 1024 * 1024
SKIP_DIRS = {'.git', '.local', 'node_modules', '.venv', 'venv', 'dist', 'build', '__pycache__', '.next', '.pytest_cache'}
EXTENSIONS = {'.md', '.txt', '.py', '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx', '.css', '.scss', '.html', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.sql', '.sh', '.csv', '.xml', '.svg', '.rs', '.go', '.java', '.c', '.h', '.cpp', '.hpp'}
NAMES = {'Dockerfile', 'Makefile', '.gitignore', '.gitattributes', 'LICENSE'}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.PIPE).strip()


def storage(root):
    root = Path(root).resolve()
    if Path(git(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise ValueError('--root must be the Git working-tree root')
    location = Path(git(root, 'rev-parse', '--absolute-git-dir')) / 'ai-toolkit-snapshots'
    if location.is_symlink():
        raise ValueError('snapshot storage must not be a symlink')
    location.mkdir(exist_ok=True)
    return root, location


def safe_name(name):
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and not any(x in {'..', '.', ''} for x in name.split('/')) and '\\' not in name


def excluded(path):
    for part in path.parts:
        name = part.lower()
        if name.startswith('.env') or name.endswith(('.pem', '.key', '.p12', '.pfx')):
            return True
        if any(x in name for x in ('credential', 'secret', 'id_rsa', 'id_ed25519')):
            return True
    return False


def collect(root, includes, allowed_extensions=None):
    extensions = EXTENSIONS if allowed_extensions is None else allowed_extensions
    selected, skipped = {}, []
    candidates = []
    for name in includes:
        if not safe_name(name):
            raise ValueError('include must be a relative path without dot components: ' + name)
        p = root / name
        if any(x.is_symlink() for x in [p] + list(p.parents) if x != root and root in x.parents):
            raise ValueError('symlink in include path: ' + name)
        if not p.exists():
            skipped.append({'path': name, 'reason': 'missing'})
            continue
        if any(x in SKIP_DIRS for x in p.relative_to(root).parts) or excluded(p.relative_to(root)):
            skipped.append({'path': name, 'reason': 'excluded-path'})
            continue
        if p.is_dir():
            for base, dirs, files in os.walk(p, followlinks=False):
                kept = []
                for d in dirs:
                    q = Path(base) / d
                    if d in SKIP_DIRS or q.is_symlink():
                        skipped.append({'path': q.relative_to(root).as_posix(), 'reason': 'excluded-directory-or-symlink'})
                    else:
                        kept.append(d)
                dirs[:] = kept
                candidates.extend(Path(base) / f for f in files)
        else:
            candidates.append(p)
    total = 0
    for p in sorted(set(candidates)):
        rel = p.relative_to(root).as_posix()
        if p.is_symlink() or any(x in SKIP_DIRS for x in p.relative_to(root).parts) or excluded(p.relative_to(root)):
            skipped.append({'path': rel, 'reason': 'excluded-name-or-symlink'})
            continue
        if p.suffix.lower() not in extensions and p.name not in NAMES:
            skipped.append({'path': rel, 'reason': 'not-a-selected-text-format'})
            continue
        if p.stat().st_size > MAX_FILE:
            skipped.append({'path': rel, 'reason': 'over-2MiB'})
            continue
        with p.open('rb') as f:
            data = f.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            skipped.append({'path': rel, 'reason': 'over-2MiB'})
            continue
        try:
            data.decode('utf-8')
        except UnicodeDecodeError:
            skipped.append({'path': rel, 'reason': 'not-utf8'})
            continue
        if b'\x00' in data:
            skipped.append({'path': rel, 'reason': 'binary'})
            continue
        total += len(data)
        if total > MAX_TOTAL:
            raise ValueError('selected contents exceed 20MiB; narrow --include')
        selected[rel] = data
    return selected, skipped


def snapshot(root, dest, includes, keep=20, allowed_extensions=None):
    files, skipped = collect(root, includes, allowed_extensions)
    if not files:
        return {'status': 'no-files', 'skipped': skipped}
    hashes = {p: hashlib.sha256(data).hexdigest() for p, data in files.items()}
    previous = sorted(dest.glob('*.zip'))
    if previous:
        with zipfile.ZipFile(previous[-1]) as z:
            old = json.loads(z.read('manifest.json'))
        if old.get('hashes') == hashes:
            return {'status': 'unchanged', 'files': len(files), 'skipped': skipped}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    target = dest / (stamp + '.zip')
    temporary = dest / (stamp + '.tmp')
    manifest = {'version': 1, 'created_utc': stamp, 'hashes': hashes, 'skipped': skipped}
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            for name, data in files.items():
                z.writestr('files/' + name, data)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    for old in sorted(dest.glob('*.zip'))[:-keep]:
        old.unlink()
    return {'status': 'saved', 'path': str(target), 'files': len(files), 'skipped': skipped}


def restore(source, target):
    target = Path(target)
    if target.is_symlink() or (target.exists() and (not target.is_dir() or any(target.iterdir()))):
        raise ValueError('restore destination must be an empty or nonexistent directory')
    with zipfile.ZipFile(source) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate ZIP entries')
        info = z.getinfo('manifest.json')
        if info.file_size > MAX_FILE:
            raise ValueError('manifest too large')
        m = json.loads(z.read(info))
        hashes = m.get('hashes')
        if m.get('version') != 1 or not isinstance(hashes, dict) or not hashes or len(hashes) > 10000:
            raise ValueError('invalid snapshot manifest')
        if set(names) != {'manifest.json'} | {'files/' + p for p in hashes}:
            raise ValueError('unexpected ZIP entries')
        files, total = {}, 0
        for name, digest in hashes.items():
            if not safe_name(name) or '.git' in PurePosixPath(name).parts:
                raise ValueError('unsafe restore path')
            info = z.getinfo('files/' + name)
            total += info.file_size
            if info.file_size > MAX_FILE or total > MAX_TOTAL:
                raise ValueError('restore size limit exceeded')
            data = z.read(info)
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError('snapshot checksum mismatch')
            files[name] = data
    # Validate every entry before creating any recovered file.
    target.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        p = target / name
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('xb') as f:
            f.write(data)
    return {'status': 'restored-to-separate-directory', 'path': str(target.resolve()), 'files': len(files)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', default='.')
    p.add_argument('--include', nargs='+')
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--once', action='store_true')
    mode.add_argument('--watch', action='store_true')
    mode.add_argument('--restore')
    p.add_argument('--to')
    p.add_argument('--interval', type=float, default=180)
    p.add_argument('--duration', type=float, default=10800)
    p.add_argument('--keep', type=int, default=20)
    a = p.parse_args()
    try:
        if a.restore:
            if not a.to:
                p.error('--restore requires --to')
            print(json.dumps(restore(a.restore, a.to), ensure_ascii=False))
            return 0
        if not a.include or a.interval <= 0 or a.duration <= 0 or a.keep < 1:
            p.error('provide --include and positive interval/duration/keep')
        root, dest = storage(a.root)
        lock = dest / 'writer.lock'
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise ValueError('another writer or stale lock exists: ' + str(lock))
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(str(os.getpid()))
            deadline = time.monotonic() + a.duration
            while True:
                result = snapshot(root, dest, a.include, a.keep)
                print(json.dumps(result, ensure_ascii=False), flush=True)
                if not a.watch or time.monotonic() >= deadline:
                    return 2 if result['status'] == 'no-files' else 0
                time.sleep(min(a.interval, max(0, deadline - time.monotonic())))
        finally:
            lock.unlink(missing_ok=True)
    except KeyboardInterrupt:
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile, KeyError) as e:
        print('ERROR: ' + str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
