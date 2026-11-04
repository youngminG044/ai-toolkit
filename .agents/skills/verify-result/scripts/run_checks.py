#!/usr/bin/env python3
"""Run explicit argv checks without shell and record real results, not correctness claims."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def run(config, root):
    checks = config.get('checks')
    if not isinstance(checks, list) or not checks:
        return {'status': 'NOT_RUN', 'reason': 'no checks configured', 'checks': []}, 2
    # Validate the complete configuration before executing any command.
    for c in checks:
        if not isinstance(c, dict) or not isinstance(c.get('name'), str) or not c['name']:
            raise ValueError('each check requires a nonempty name')
        argv = c.get('argv')
        if not isinstance(argv, list) or not argv or any(not isinstance(s, str) or not s for s in argv):
            raise ValueError('argv must be a nonempty string array')
        if not isinstance(c.get('timeout', 120), (int, float)) or c.get('timeout', 120) <= 0:
            raise ValueError('timeout must be positive')
    result = {'started_utc': datetime.now(timezone.utc).isoformat(), 'checks': []}
    for c in checks:
        start = time.monotonic()
        # Disk-backed capture bounds memory even for noisy commands.
        with tempfile.TemporaryFile() as output:
            try:
                proc = subprocess.Popen(c['argv'], cwd=root, stdout=output, stderr=subprocess.STDOUT,
                                        start_new_session=(os.name == 'posix'))
                try:
                    code = proc.wait(timeout=c.get('timeout', 120))
                    status = 'PASS' if code == 0 else 'FAIL'
                except subprocess.TimeoutExpired:
                    if os.name == 'posix':
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                    proc.wait()
                    code, status = None, 'TIMEOUT'
            except subprocess.TimeoutExpired:
                code, status = None, 'TIMEOUT'
            except OSError as e:
                code, status = None, 'ERROR'
                output.write(str(e).encode())
            size = output.tell()
            output.seek(0)
            text = output.read(16000).decode('utf-8', errors='replace')
        result['checks'].append({'name': c['name'], 'argv': c['argv'], 'status': status,
                                 'exit_code': code, 'seconds': round(time.monotonic() - start, 3),
                                 'output': text, 'output_truncated': size > 16000})
    result['status'] = 'PASS' if all(c['status'] == 'PASS' for c in result['checks']) else 'FAIL'
    result['meaning'] = 'Exit-code evidence only; inspect test counts, skipped tests and acceptance coverage separately.'
    return result, 0 if result['status'] == 'PASS' else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('config', help='JSON with checks: [{name, argv, timeout?}]')
    p.add_argument('--root', default='.')
    p.add_argument('--output', help='optional new JSON file; existing files are not overwritten')
    a = p.parse_args()
    try:
        if a.output and Path(a.output).exists():
            raise ValueError('output exists; choose a fresh evidence path')
        config = json.loads(Path(a.config).read_text())
        if not isinstance(config, dict):
            raise ValueError('configuration must be an object')
        result, code = run(config, Path(a.root).resolve())
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if a.output:
            with Path(a.output).open('x', encoding='utf-8') as f:
                f.write(text + '\n')
        print(text)
        return code
    except (OSError, ValueError, TypeError) as e:
        print('ERROR: ' + str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
