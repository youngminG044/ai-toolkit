import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cp = load('checkpoint', '.agents/skills/git-checkpoint/scripts/checkpoint.py')
csvtool = load('profile_csv', '.agents/skills/analyze-data/scripts/profile_csv.py')
checks = load('run_checks', '.agents/skills/verify-result/scripts/run_checks.py')
installer = load('installer', 'tools/install.py')
records = load('records', '.agents/skills/record-work/scripts/init_records.py')
submission = load('submission', '.agents/skills/verify-result/scripts/check_submission.py')


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        self.root.mkdir()

    def write(self, name, data='content'):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)
        return p

    def git_init(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True, capture_output=True)
        return cp.storage(self.root)


class InstallTests(Workspace):
    def test_preview_has_no_side_effects(self):
        installer.install(self.root, ['solve-task'])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_installs_resources_preserves_project_and_is_idempotent(self):
        self.write('AGENTS.md', 'original instructions')
        self.write('README.md', 'assignment')
        first = installer.install(self.root, ['solve-task', 'git-checkpoint'], True)
        self.assertEqual(first[0][1], 'install')
        self.assertTrue((self.root / '.agents/skills/solve-task/references/task-profiles.md').exists())
        self.assertTrue((self.root / '.agents/skills/git-checkpoint/scripts/checkpoint.py').exists())
        self.assertEqual((self.root / 'AGENTS.md').read_text(), 'original instructions')
        self.assertEqual((self.root / 'README.md').read_text(), 'assignment')
        self.assertEqual(installer.install(self.root, ['solve-task'], True),
                         [('solve-task', 'unchanged'), ('record-work', 'unchanged'), ('git-checkpoint', 'unchanged')])

    def test_conflict_prevents_all_planned_installs(self):
        self.write('.agents/skills/verify-result/SKILL.md', 'existing different skill')
        with self.assertRaises(ValueError):
            installer.install(self.root, ['solve-task', 'verify-result'], True)
        self.assertFalse((self.root / '.agents/skills/solve-task').exists())
        self.assertEqual((self.root / '.agents/skills/verify-result/SKILL.md').read_text(), 'existing different skill')

    def test_symlink_target_refused(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (self.root / '.agents').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            installer.install(self.root, ['solve-task'], True)
        self.assertEqual(list(outside.iterdir()), [])

    def test_traversal_skill_refused(self):
        with self.assertRaises(ValueError):
            installer.install(self.root, ['../solve-task'], True)

    def test_default_install_creates_records_in_actual_workspace_only(self):
        self.write('README.md', 'actual assignment')
        names = sorted(p.name for p in installer.SOURCE.iterdir() if (p / 'SKILL.md').is_file())
        installer.install(self.root, names, True)
        self.assertEqual(len(list((self.root / '.agents/skills').glob('*/SKILL.md'))), 7)
        self.assertTrue((self.root / 'devlog.md').is_file())
        self.assertTrue((self.root / 'probe.md').is_file())
        self.assertEqual((self.root / 'README.md').read_text(), 'actual assignment')
        self.assertFalse((ROOT / 'devlog.md').exists())
        self.assertFalse((ROOT / 'probe.md').exists())

    def test_install_preserves_existing_task_record_contents(self):
        self.write('devlog.md', 'actual task history\n')
        self.write('probe.md', 'actual feature decisions\n')
        installer.install(self.root, ['solve-task', 'record-work'], True)
        self.assertEqual((self.root / 'devlog.md').read_text(), 'actual task history\n')
        self.assertEqual((self.root / 'probe.md').read_text(), 'actual feature decisions\n')

    def test_optional_install_without_record_files(self):
        installer.install(self.root, ['record-work'], True, create_records=False)
        self.assertTrue((self.root / '.agents/skills/record-work/SKILL.md').is_file())
        self.assertFalse((self.root / 'devlog.md').exists())
        self.assertFalse((self.root / 'probe.md').exists())

    def test_record_path_conflict_prevents_skill_install(self):
        (self.root / 'probe.md').mkdir()
        with self.assertRaises(ValueError):
            installer.install(self.root, ['record-work'], True)
        self.assertFalse((self.root / '.agents').exists())
        self.assertFalse((self.root / 'devlog.md').exists())

    def test_distribution_is_not_a_task_installation_target(self):
        with self.assertRaises(ValueError):
            installer.install(ROOT, ['record-work'], True)
        self.assertFalse((ROOT / 'devlog.md').exists())
        self.assertFalse((ROOT / 'probe.md').exists())


class RecordTests(Workspace):
    def test_distribution_and_nested_directories_refuse_task_records(self):
        self.write('.toolkit-package', 'distribution\n')
        nested = self.root / 'nested'
        nested.mkdir()
        for target in (self.root, nested):
            with self.assertRaises(ValueError):
                records.initialize(target)
            self.assertFalse((target / 'devlog.md').exists())
            self.assertFalse((target / 'probe.md').exists())

    def test_check_mode_validates_without_creating_records(self):
        script = ROOT / '.agents/skills/record-work/scripts/init_records.py'
        result = subprocess.run([sys.executable, str(script), '--root', str(self.root), '--check'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_creates_two_records_and_second_run_preserves_edits(self):
        self.assertEqual(records.initialize(self.root), [('devlog.md', 'created'), ('probe.md', 'created')])
        self.assertGreater((self.root / 'probe.md').stat().st_size, 0)
        (self.root / 'devlog.md').write_text('실제 사용자의 기록\n')
        self.assertEqual(records.initialize(self.root), [('devlog.md', 'preserved'), ('probe.md', 'preserved')])
        self.assertEqual((self.root / 'devlog.md').read_text(), '실제 사용자의 기록\n')

    def test_preserves_existing_document_and_creates_only_missing_one(self):
        before = self.write('probe.md', 'existing feature decisions\n').read_bytes()
        result = records.initialize(self.root)
        self.assertEqual(result, [('devlog.md', 'created'), ('probe.md', 'preserved')])
        self.assertEqual((self.root / 'probe.md').read_bytes(), before)

    def test_symlink_conflict_prevents_creating_first_document(self):
        outside = self.base / 'outside.md'
        outside.write_text('outside')
        (self.root / 'probe.md').symlink_to(outside)
        with self.assertRaises(ValueError):
            records.initialize(self.root)
        self.assertFalse((self.root / 'devlog.md').exists())
        self.assertEqual(outside.read_text(), 'outside')

    def test_directory_conflict_preserves_workspace(self):
        (self.root / 'probe.md').mkdir()
        with self.assertRaises(ValueError):
            records.initialize(self.root)
        self.assertFalse((self.root / 'devlog.md').exists())

    def test_missing_root_is_not_created(self):
        root = self.base / 'missing'
        with self.assertRaises(ValueError):
            records.initialize(root)
        self.assertFalse(root.exists())

    def test_installed_script_runs_without_original_repository(self):
        self.write('README.md', 'original assignment')
        installer.install(self.root, ['record-work'], True)
        script = self.root / '.agents/skills/record-work/scripts/init_records.py'
        result = subprocess.run([sys.executable, str(script), '--root', str(self.root)],
                                cwd=self.base, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'devlog.md').is_file())
        self.assertTrue((self.root / 'probe.md').is_file())
        self.assertEqual((self.root / 'README.md').read_text(), 'original assignment')
        self.assertFalse(list((self.root / '.agents/skills').rglob('__pycache__')))


class SubmissionTests(Workspace):
    def test_no_contract_is_not_run(self):
        result, code = submission.validate(self.root / 'not-needed.csv')
        self.assertEqual((result['status'], code), ('NOT_RUN', 2))

    def test_bom_and_nonfirst_id_column_preserve_string_values(self):
        sample = self.write('sample.csv', '\ufeffscore,record_id\n0,001\n0,002\n')
        candidate = self.write('candidate.csv', 'score,record_id\n0.4,001\n0.6,002\n')
        r, code = submission.validate(candidate, sample, match_rows=True,
                                       id_column='record_id', required_columns=['score'])
        self.assertEqual((r['status'], code), ('PASS', 0))

    def test_column_order_is_checked(self):
        p = self.write('candidate.csv', 'value,id\n3,01\n')
        r, code = submission.validate(p, columns=['id', 'value'])
        self.assertEqual(code, 1)
        self.assertIn('column names or order differ', r['errors'])

    def test_example_rows_do_not_implicitly_set_expected_count(self):
        sample = self.write('sample.csv', 'id,value\n01,0\n')
        candidate = self.write('candidate.csv', 'id,value\n01,5\n02,6\n')
        r, code = submission.validate(candidate, sample)
        self.assertEqual((r['status'], code), ('PASS', 0))

    def test_explicit_row_contracts_are_enforced(self):
        sample = self.write('sample.csv', 'id,value\n01,0\n')
        candidate = self.write('candidate.csv', 'id,value\n01,5\n02,6\n')
        self.assertEqual(submission.validate(candidate, sample, match_rows=True)[1], 1)
        self.assertEqual(submission.validate(candidate, rows=2)[1], 0)
        self.assertEqual(submission.validate(candidate, rows=1)[1], 1)

    def test_id_order_and_leading_zero_loss_are_detected(self):
        sample = self.write('sample.csv', 'id,value\n001,0\n002,0\n')
        for text in ('id,value\n002,1\n001,2\n', 'id,value\n1,1\n2,2\n'):
            candidate = self.write('candidate.csv', text)
            result, code = submission.validate(candidate, sample, id_column='id')
            self.assertEqual(code, 1)
            self.assertIn('ID values or order differ from reference', result['errors'])

    def test_duplicate_or_empty_ids_are_detected(self):
        sample = self.write('sample.csv', 'id,value\n001,0\n002,0\n')
        for text in ('id,value\n001,1\n001,2\n', 'id,value\n001,1\n,2\n'):
            candidate = self.write('candidate.csv', text)
            self.assertEqual(submission.validate(candidate, sample, id_column='id')[1], 1)

    def test_bad_width_and_duplicate_header_are_failures(self):
        for text in ('id,value\n01,1,extra\n', 'id,id\n01,1\n'):
            candidate = self.write('candidate.csv', text)
            self.assertEqual(submission.validate(candidate, columns=['id', 'value'])[1], 1)

    def test_required_values_and_missing_declared_column(self):
        candidate = self.write('candidate.csv', 'id,value\n01,\n')
        self.assertEqual(submission.validate(candidate, required_columns=['value'])[1], 1)
        self.assertEqual(submission.validate(candidate, required_columns=['missing'])[1], 1)

    def test_invalid_or_conflicting_contract_is_rejected(self):
        candidate = self.write('candidate.csv', 'id,value\n01,1\n')
        with self.assertRaises(ValueError):
            submission.validate(candidate, id_column='id')
        with self.assertRaises(ValueError):
            submission.validate(candidate, rows=-1)
        with self.assertRaises(ValueError):
            submission.validate(candidate, candidate, columns=['value', 'id'])


class SnapshotTests(Workspace):
    def test_snapshot_and_restore_preserve_index_and_work(self):
        root, dest = self.git_init()
        original = self.write('src/main.py', 'print(1)\n')
        subprocess.run(['git', '-C', str(root), 'add', '--', 'src/main.py'], check=True)
        index_before = (root / '.git/index').read_bytes()
        original.write_text('print(2)\n')
        saved = cp.snapshot(root, dest, ['src'])
        self.assertEqual(saved['status'], 'saved')
        self.assertEqual((root / '.git/index').read_bytes(), index_before)
        restored = self.base / 'recovered'
        cp.restore(saved['path'], restored)
        self.assertEqual((restored / 'src/main.py').read_text(), 'print(2)\n')
        self.assertEqual(original.read_text(), 'print(2)\n')

    def test_identical_contents_do_not_add_snapshots(self):
        root, dest = self.git_init()
        self.write('README.md', 'a')
        cp.snapshot(root, dest, ['README.md'])
        self.assertEqual(cp.snapshot(root, dest, ['README.md'])['status'], 'unchanged')
        self.assertEqual(len(list(dest.glob('*.zip'))), 1)

    def test_excludes_sensitive_generated_binary_and_symlink(self):
        root, dest = self.git_init()
        self.write('src/main.py', 'ok')
        self.write('src/.env', 'FAKE_TEST_VALUE')
        self.write('src/secret.json', '{}')
        self.write('src/credentials/token.txt', 'FAKE_TEST_VALUE')
        self.write('src/node_modules/pkg/index.js', 'generated')
        self.write('src/a.bin', 'binary')
        (root / 'src/link.py').symlink_to(root / 'src/.env')
        result = cp.snapshot(root, dest, ['src'])
        with zipfile.ZipFile(result['path']) as z:
            m = json.loads(z.read('manifest.json'))
        self.assertEqual(set(m['hashes']), {'src/main.py'})

    def test_deletion_produces_full_new_manifest(self):
        root, dest = self.git_init()
        self.write('src/a.py', 'a')
        b = self.write('src/b.py', 'b')
        cp.snapshot(root, dest, ['src'])
        b.unlink()
        r = cp.snapshot(root, dest, ['src'])
        with zipfile.ZipFile(r['path']) as z:
            self.assertEqual(set(json.loads(z.read('manifest.json'))['hashes']), {'src/a.py'})

    def test_retention_is_bounded(self):
        root, dest = self.git_init()
        for i in range(4):
            self.write('README.md', str(i))
            cp.snapshot(root, dest, ['README.md'], keep=2)
        self.assertEqual(len(list(dest.glob('*.zip'))), 2)

    def test_escape_and_symlink_includes_refused(self):
        root, dest = self.git_init()
        with self.assertRaises(ValueError):
            cp.snapshot(root, dest, ['../outside'])
        (root / 'linked').symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(ValueError):
            cp.snapshot(root, dest, ['linked/project'])

    def test_empty_selection_and_large_file_are_not_success(self):
        root, dest = self.git_init()
        self.write('big.txt', 'x' * (cp.MAX_FILE + 1))
        r = cp.snapshot(root, dest, ['big.txt', 'missing'])
        self.assertEqual(r['status'], 'no-files')
        self.assertEqual({s['reason'] for s in r['skipped']}, {'over-2MiB', 'missing'})

    def test_excluded_directory_is_not_scanned_when_explicitly_selected(self):
        root, dest = self.git_init()
        self.write('node_modules/deep/code.js', 'generated')
        result = cp.snapshot(root, dest, ['node_modules'])
        self.assertEqual(result['status'], 'no-files')
        self.assertEqual(result['skipped'], [{'path': 'node_modules', 'reason': 'excluded-path'}])

    def test_restore_never_overwrites_existing_work(self):
        root, dest = self.git_init()
        self.write('README.md', 'snapshot')
        saved = cp.snapshot(root, dest, ['README.md'])
        (root / 'README.md').write_text('new work')
        with self.assertRaises(ValueError):
            cp.restore(saved['path'], root)
        self.assertEqual((root / 'README.md').read_text(), 'new work')

    def test_malicious_path_and_bad_checksum_rejected_before_writing(self):
        for name, digest in [('../escaped.txt', hashlib.sha256(b'x').hexdigest()), ('safe.txt', 'bad')]:
            source = self.base / 'malicious.zip'
            with zipfile.ZipFile(source, 'w') as z:
                z.writestr('manifest.json', json.dumps({'version': 1, 'hashes': {name: digest}}))
                z.writestr('files/' + name, b'x')
            target = self.base / 'recovered'
            with self.assertRaises(ValueError):
                cp.restore(source, target)
            self.assertFalse(target.exists())
            self.assertFalse((self.base / 'escaped.txt').exists())

    def test_watcher_has_deadline_cleans_lock_and_refuses_duplicate(self):
        root, dest = self.git_init()
        self.write('README.md', 'a')
        command = [sys.executable, str(ROOT / '.agents/skills/git-checkpoint/scripts/checkpoint.py'),
                   '--root', str(root), '--include', 'README.md', '--watch', '--interval', '0.02', '--duration', '0.06']
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((dest / 'writer.lock').exists())
        self.assertEqual(len(list(dest.glob('*.zip'))), 1)
        (dest / 'writer.lock').write_text('existing')
        blocked = subprocess.run(command, capture_output=True, text=True, timeout=5)
        self.assertEqual(blocked.returncode, 1)
        self.assertEqual((dest / 'writer.lock').read_text(), 'existing')

    def test_missing_git_is_not_initialized_automatically(self):
        with self.assertRaises(subprocess.CalledProcessError):
            cp.storage(self.root)
        self.assertFalse((self.root / '.git').exists())


class CsvTests(Workspace):
    def test_bom_missing_duplicates_malformed_and_numeric(self):
        p = self.write('input.csv', '\ufeffid,value\nA,2\nA,2\nB,\nC,3,extra\nD,-5\nE,NaN\n')
        r = csvtool.profile(p)
        self.assertEqual(r['rows_scanned'], 6)
        self.assertEqual(r['malformed_rows'], 1)
        self.assertEqual(r['exact_duplicate_rows'], 1)
        self.assertEqual(r['columns'][1]['missing'], 1)
        self.assertEqual(r['columns'][1]['numeric_parse'], {'min': -5.0, 'max': 2.0, 'count': 3})

    def test_scan_limit_reports_partial_scope(self):
        r = csvtool.profile(self.write('input.csv', 'id\nA\nB\nC\n'), 2)
        self.assertEqual(r['rows_scanned'], 2)
        self.assertTrue(r['truncated'])

    def test_duplicate_header_rejected(self):
        with self.assertRaises(ValueError):
            csvtool.profile(self.write('input.csv', 'x,x\n1,2\n'))


class CheckTests(Workspace):
    def test_no_checks_is_not_pass(self):
        result, code = checks.run({'checks': []}, self.root)
        self.assertEqual(code, 2)
        self.assertEqual(result['status'], 'NOT_RUN')

    def test_real_pass_and_failure_are_recorded(self):
        config = {'checks': [
            {'name': 'pass', 'argv': [sys.executable, '-c', 'print("ok")']},
            {'name': 'fail', 'argv': [sys.executable, '-c', 'raise SystemExit(7)']}]}
        result, code = checks.run(config, self.root)
        self.assertEqual(code, 1)
        self.assertEqual(result['checks'][0]['status'], 'PASS')
        self.assertEqual(result['checks'][1]['exit_code'], 7)

    def test_argv_is_not_interpreted_as_shell(self):
        result, code = checks.run({'checks': [{'name': 'literal', 'argv':
            [sys.executable, '-c', 'import sys; print(sys.argv[1])', 'x; touch SHOULD_NOT_EXIST']} ]}, self.root)
        self.assertEqual(code, 0)
        self.assertIn('x; touch SHOULD_NOT_EXIST', result['checks'][0]['output'])
        self.assertFalse((self.root / 'SHOULD_NOT_EXIST').exists())

    def test_timeout_and_missing_executable_are_failures(self):
        r, code = checks.run({'checks': [
            {'name': 'slow', 'argv': [sys.executable, '-c', 'import time; time.sleep(2)'], 'timeout': 0.05},
            {'name': 'missing', 'argv': ['/toolkit-test-missing-executable']} ]}, self.root)
        self.assertEqual(code, 1)
        self.assertEqual([x['status'] for x in r['checks']], ['TIMEOUT', 'ERROR'])

    def test_bad_later_config_prevents_earlier_execution(self):
        config = {'checks': [
            {'name': 'would-write', 'argv': [sys.executable, '-c', 'open("unexpected", "w").write("x")']},
            {'name': 'bad', 'argv': 'echo wrong'} ]}
        with self.assertRaises(ValueError):
            checks.run(config, self.root)
        self.assertFalse((self.root / 'unexpected').exists())


if __name__ == '__main__':
    unittest.main()
