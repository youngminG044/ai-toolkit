import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('session_installer', ROOT / 'tools/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp).resolve() / 'task'
        self.root.mkdir()
        (self.root / 'README.md').write_text('Actual task instructions\n')
        (self.root / 'main.py').write_text('value = 1\n')
        installer.install(self.root, ['solve-task'], True, create_records=False)
        self.script = self.root / '.agents/skills/solve-task/scripts/session.py'
        self.addCleanup(self.cleanup_worker)

    def command(self, action, *args, check=True):
        result = subprocess.run([sys.executable, str(self.script), action, '--root', str(self.root), *args],
                                cwd=self.root, capture_output=True, text=True, timeout=10)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        return result

    def cleanup_worker(self):
        if self.root.exists():
            self.command('stop', check=False)

    def start(self, *args):
        return self.command('start', '--interval', '0.15', '--duration', '15', *args)

    def until(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(0.05)
        self.fail('expected observable state was not reached')

    def test_selected_install_includes_session_dependencies(self):
        for name in ['solve-task', 'record-work', 'git-checkpoint']:
            self.assertTrue((self.root / '.agents/skills' / name / 'SKILL.md').exists())
        self.assertFalse((self.root / 'devlog.md').exists())

    def test_background_saves_changes_and_new_folders_without_git_or_configuration(self):
        (self.root / '.env').write_text('TOKEN=must-not-be-saved')
        (self.root / 'input.csv').write_text('id,value\n001,2')
        (self.root / 'node_modules').mkdir()
        (self.root / 'node_modules/generated.js').write_text('generated')
        (self.root / 'public-kit').mkdir()
        (self.root / 'public-kit/.toolkit-package').write_text('distribution')
        (self.root / 'public-kit/example.py').write_text('kit_code = True')
        (self.root / 'probe.md').write_text('Human decisions already here\n')
        first = self.start()
        self.assertEqual(first['status'], 'running')
        self.assertEqual(first['last_snapshot']['status'], 'saved')
        dest = Path(first['storage'])
        self.assertFalse((self.root / '.git').exists())
        self.assertEqual(dest, self.root / '.local/ai-toolkit/snapshots')
        with zipfile.ZipFile(first['last_snapshot']['path']) as archive:
            names = archive.namelist()
            self.assertIn('files/main.py', names)
            self.assertNotIn('files/.env', names)
            self.assertNotIn('files/input.csv', names)
            self.assertNotIn('files/node_modules/generated.js', names)
            self.assertNotIn('files/public-kit/example.py', names)
        (self.root / 'main.py').write_text('value = 2\n')
        (self.root / 'new').mkdir()
        (self.root / 'new/config.json').write_text('{"enabled":true}')
        def saved_new_file():
            state = self.command('status')
            path = state.get('last_snapshot', {}).get('path')
            if not path:
                return False
            with zipfile.ZipFile(path) as archive:
                return 'files/new/config.json' in archive.namelist() and archive.read('files/main.py') == b'value = 2\n'
        self.until(saved_new_file)
        stopped = self.command('stop')
        self.assertEqual(stopped['status'], 'stopped')
        self.assertFalse(stopped['active'])
        self.assertEqual((self.root / 'probe.md').read_text(), 'Human decisions already here\n')
        self.assertIn(hashlib.sha256(b'value = 2\n').hexdigest()[:16], (self.root / 'devlog.md').read_text())
        with zipfile.ZipFile(stopped['last_snapshot']['path']) as archive:
            self.assertEqual(archive.read('files/devlog.md'), (self.root / 'devlog.md').read_bytes())
        self.assertLessEqual(len(list(dest.glob('*.zip'))), 20)

    def test_repeated_start_reuses_worker_without_resetting_duration(self):
        first = self.start()
        second = self.start()
        self.assertEqual(second['action'], 'already_running')
        self.assertEqual(first['pid'], second['pid'])
        self.assertEqual(first['started_utc'], second['started_utc'])

    def test_concurrent_start_has_one_worker(self):
        argv = [sys.executable, str(self.script), 'start', '--root', str(self.root), '--duration', '15']
        processes = [subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        results = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            results.append(json.loads(stdout))
        self.assertEqual(results[0]['pid'], results[1]['pid'])
        self.assertEqual({r['action'] for r in results}, {'started', 'already_running'})

    def test_deadline_expires_and_final_snapshot_is_saved(self):
        self.command('start', '--interval', '0.1', '--duration', '0.35')
        state = self.until(lambda: (s if (s := self.command('status'))['status'] == 'expired' and not s['active'] else None))
        self.assertTrue(Path(state['last_snapshot']['path']).is_file())

    def test_git_index_and_source_are_preserved(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', 'main.py'], check=True)
        index = self.root / '.git/index'
        before = index.read_bytes()
        (self.root / 'main.py').write_text('value = 3\n')
        state = self.start()
        self.assertEqual(Path(state['storage']), self.root / '.local/ai-toolkit/snapshots')
        self.command('stop')
        self.assertEqual(index.read_bytes(), before)
        self.assertFalse((self.root / '.git/ai-toolkit-snapshots').exists())
        self.assertEqual((self.root / 'main.py').read_text(), 'value = 3\n')

    def test_no_records_mode_keeps_extra_documents_absent(self):
        state = self.start('--no-records')
        self.assertFalse(state['records'])
        self.command('stop')
        self.assertFalse((self.root / 'devlog.md').exists())
        self.assertFalse((self.root / 'probe.md').exists())

    def test_symlink_record_conflict_prevents_any_record_or_worker(self):
        outside = Path(self.temp) / 'outside.md'
        outside.write_text('preserve')
        (self.root / 'probe.md').symlink_to(outside)
        self.assertNotEqual(self.command('start', check=False).returncode, 0)
        self.assertFalse((self.root / 'devlog.md').exists())
        self.assertFalse((self.root / '.local').exists())
        self.assertEqual(outside.read_text(), 'preserve')

    def test_symlink_storage_is_not_followed(self):
        outside = Path(self.temp) / 'outside'
        outside.mkdir()
        (self.root / '.local').symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.command('start', check=False).returncode, 0)
        self.assertFalse((self.root / 'devlog.md').exists())
        self.assertEqual(list(outside.iterdir()), [])

    def test_distribution_rejected_and_invalid_duration_has_no_records(self):
        result = subprocess.run([sys.executable, str(self.script), 'start', '--root', str(ROOT)], capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        for value in ['nan', 'inf', '0', '10801']:
            self.assertNotEqual(self.command('start', '--duration', value, check=False).returncode, 0)
        self.assertFalse((self.root / 'devlog.md').exists())

    def test_interrupted_worker_is_detected_and_can_restart(self):
        state = self.start()
        # Kill only the worker created by this isolated test.
        os.kill(state['pid'], signal.SIGKILL)
        self.until(lambda: self.command('status', check=False).returncode != 0)
        restarted = self.start()
        self.assertNotEqual(restarted['pid'], state['pid'])
        self.assertEqual(restarted['status'], 'running')

    def test_existing_snapshot_writer_is_preserved_and_failure_reported(self):
        dest = self.root / '.local/ai-toolkit/snapshots'
        dest.mkdir(parents=True)
        lock = dest / 'writer.lock'
        lock.write_text(str(os.getpid()))
        result = self.command('start', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('writer', result.stderr)
        self.assertEqual(lock.read_text(), str(os.getpid()))
        lock.unlink()

    def test_launcher_installs_skills_and_passes_prompt_without_invoking_real_ai(self):
        binary = Path(self.temp) / 'bin'
        binary.mkdir()
        fake = binary / 'codex'
        fake.write_text('#!' + sys.executable + '\nimport json,sys\nfrom pathlib import Path\nPath("launch.json").write_text(json.dumps({"cwd":str(Path.cwd()),"args":sys.argv[1:]}))\nsys.exit(7)\n')
        fake.chmod(0o700)
        env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ.get('PATH', ''))
        result = subprocess.run([sys.executable, str(ROOT / 'tools/start.py'), '--target', str(self.root)], env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 7, result.stderr)
        invocation = json.loads((self.root / 'launch.json').read_text())
        self.assertEqual(invocation['cwd'], str(self.root))
        self.assertIn('$solve-task', invocation['args'][0])
        self.assertEqual(len(list((self.root / '.agents/skills').glob('*/SKILL.md'))), 7)
        self.assertFalse((self.root / 'devlog.md').exists())


if __name__ == '__main__':
    unittest.main()
