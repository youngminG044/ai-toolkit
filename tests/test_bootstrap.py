import errno
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/bootstrap.py'
spec = importlib.util.spec_from_file_location('restricted_bootstrap', SCRIPT)
bootstrap = importlib.util.module_from_spec(spec)
with mock.patch.object(sys, 'path', [str(ROOT / 'tools'), *sys.path]):
    spec.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp).resolve() / 'task with spaces'
        self.root.mkdir()
        (self.root / 'README.md').write_text('Actual task. Extra record files are forbidden until checked.\n')
        (self.root / 'AGENTS.md').write_text('Existing task instructions\n')
        (self.root / 'main.py').write_text('value = 1\n')

    def run_bootstrap(self, *args, env=None, cwd=ROOT, check=True):
        result = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=10)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        return result

    def test_handoff_installs_skills_preserves_task_and_returns_readable_entry(self):
        before = {name: (self.root / name).read_bytes() for name in ['README.md', 'AGENTS.md', 'main.py']}
        result = self.run_bootstrap('--target', str(self.root))
        self.assertEqual(result['status'], 'ready')
        self.assertTrue(result['continue_in_current_session'])
        self.assertEqual(result['target'], str(self.root))
        self.assertEqual(result['entry_skill'], 'solve-task')
        self.assertEqual(Path(result['entry_path']), self.root / '.agents/skills/solve-task/SKILL.md')
        self.assertTrue(Path(result['entry_path']).is_file())
        self.assertEqual(len(result['skills']), 7)
        for skill in result['skills']:
            self.assertTrue(skill['description'])
            self.assertTrue(Path(skill['path']).is_file())
            self.assertEqual(skill['action'], 'install')
        self.assertEqual(set(result['task_instruction_paths']), {str(self.root / name) for name in ['README.md', 'AGENTS.md']})
        for name, content in before.items():
            self.assertEqual((self.root / name).read_bytes(), content)
        for name in ['devlog.md', 'probe.md', '.local', 'frontend', 'backend']:
            self.assertFalse((self.root / name).exists(), name)

    def test_repeat_is_idempotent_and_preserves_existing_task_records(self):
        self.run_bootstrap('--target', str(self.root))
        (self.root / 'probe.md').write_text('Actual decisions\n')
        (self.root / 'devlog.md').write_text('Actual task history\n')
        result = self.run_bootstrap('--target', str(self.root))
        self.assertTrue(all(s['action'] == 'unchanged' for s in result['skills']))
        self.assertEqual((self.root / 'probe.md').read_text(), 'Actual decisions\n')
        self.assertEqual((self.root / 'devlog.md').read_text(), 'Actual task history\n')

    def test_explicit_target_is_required_and_distribution_is_refused(self):
        self.assertNotEqual(self.run_bootstrap(cwd=self.root, check=False).returncode, 0)
        self.assertFalse((self.root / '.agents').exists())
        result = self.run_bootstrap('--target', str(ROOT), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((ROOT / 'devlog.md').exists())
        self.assertFalse((ROOT / 'probe.md').exists())

    def test_existing_different_skill_blocks_other_installs(self):
        path = self.root / '.agents/skills/solve-task/SKILL.md'
        path.parent.mkdir(parents=True)
        path.write_text('Existing different user skill\n')
        result = self.run_bootstrap('--target', str(self.root), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(path.read_text(), 'Existing different user skill\n')
        self.assertEqual([p.name for p in path.parent.parent.iterdir()], ['solve-task'])

    def test_bootstrap_does_not_spawn_codex_or_start_watcher(self):
        binary = Path(self.temp).resolve() / 'bin'
        binary.mkdir()
        sentinel = self.root / 'nested-codex.txt'
        fake = binary / 'codex'
        fake.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nPath(' + repr(str(sentinel)) + ').write_text("started")\n')
        fake.chmod(0o700)
        env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ.get('PATH', ''))
        self.run_bootstrap('--target', str(self.root), env=env)
        self.assertFalse(sentinel.exists())
        self.assertFalse((self.root / '.local').exists())
        self.assertFalse((self.root / '.git').exists())

    def test_read_only_install_returns_reference_paths_without_claiming_installation(self):
        for error_number in [errno.EROFS, errno.EACCES, errno.EPERM]:
            with self.subTest(errno=error_number):
                error = OSError(error_number, 'protected agent settings', str(self.root / '.agents/skills'))
                with mock.patch.object(bootstrap, 'install', side_effect=error):
                    result = bootstrap.prepare(self.root)
                self.assertEqual(result['status'], 'ready')
                self.assertEqual(result['mode'], 'reference')
                self.assertEqual(result['installation_status'], 'not_completed')
                self.assertEqual(result['install_error']['errno'], error_number)
                self.assertEqual(Path(result['entry_path']), ROOT / '.agents/skills/solve-task/SKILL.md')
                self.assertTrue(Path(result['session_script']).is_file())
                self.assertTrue(all(s['action'] == 'reference' and Path(s['path']).is_file() for s in result['skills']))
                self.assertFalse((self.root / '.agents').exists())

    def test_explicit_reference_mode_does_not_attempt_installation(self):
        with mock.patch.object(bootstrap, 'install', side_effect=AssertionError('must not write agent settings')):
            result = bootstrap.prepare(self.root, mode='reference')
        self.assertEqual(result['mode'], 'reference')
        self.assertEqual(result['installation_status'], 'not_requested')
        self.assertIsNone(result['install_error'])
        self.assertEqual(len(list(self.root.iterdir())), 3)

    def test_disk_errors_and_explicit_install_failures_are_not_hidden(self):
        cases = [
            ('auto', OSError(errno.ENOSPC, 'disk full', str(self.root / '.agents/skills'))),
            ('auto', OSError(errno.EACCES, 'unrelated source error', str(ROOT / 'tools'))),
            ('install', OSError(errno.EROFS, 'read only', str(self.root / '.agents/skills'))),
        ]
        for mode, error in cases:
            with self.subTest(mode=mode, errno=error.errno, path=error.filename):
                with mock.patch.object(bootstrap, 'install', side_effect=error):
                    with self.assertRaises(OSError):
                        bootstrap.prepare(self.root, mode=mode)

    def test_reference_session_runs_with_protected_agents_and_git_metadata(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', 'main.py'], check=True)
        git_dir = self.root / '.git'
        agents = self.root / '.agents'
        agents.mkdir()
        before = {p.relative_to(git_dir).as_posix(): p.read_bytes() for p in git_dir.rglob('*') if p.is_file()}
        old_modes = {p: p.stat().st_mode & 0o777 for p in [git_dir, agents]}
        script = ROOT / '.agents/skills/solve-task/scripts/session.py'
        try:
            for path in old_modes:
                path.chmod(0o555)
            # EROFS is injected because a portable test cannot mount a read-only filesystem.
            error = OSError(errno.EROFS, 'read-only filesystem', str(agents / 'skills'))
            with mock.patch.object(bootstrap, 'install', side_effect=error):
                handoff = bootstrap.prepare(self.root)
            self.assertEqual(Path(handoff['session_script']), script)
            started = subprocess.run([sys.executable, handoff['session_script'], 'start', '--root', str(self.root),
                                      '--interval', '0.15', '--duration', '15'], capture_output=True, text=True, timeout=10)
            self.assertEqual(started.returncode, 0, started.stderr)
            state = json.loads(started.stdout)
            self.assertEqual(Path(state['storage']), self.root / '.local/ai-toolkit/snapshots')
            (self.root / 'main.py').write_text('value = 2\n')
            stopped = subprocess.run([sys.executable, str(script), 'stop', '--root', str(self.root)],
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(stopped.returncode, 0, stopped.stderr)
            final = json.loads(stopped.stdout)
            self.assertFalse(final['active'])
            with zipfile.ZipFile(final['last_snapshot']['path']) as archive:
                self.assertEqual(archive.read('files/main.py'), b'value = 2\n')
                self.assertIn('files/probe.md', archive.namelist())
            self.assertEqual(list(agents.iterdir()), [])
            after = {p.relative_to(git_dir).as_posix(): p.read_bytes() for p in git_dir.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
        finally:
            subprocess.run([sys.executable, str(script), 'stop', '--root', str(self.root)], capture_output=True, timeout=10)
            for path, mode in old_modes.items():
                path.chmod(mode)


if __name__ == '__main__':
    unittest.main()
