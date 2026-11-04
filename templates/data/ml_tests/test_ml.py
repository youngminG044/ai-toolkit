import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from data.train import train


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp)
        self.path = self.root / 'train.csv'
        with self.path.open('w') as stream:
            writer = csv.writer(stream)
            writer.writerow(['id', 'day', 'group', 'x', 'category', 'target', 'amount'])
            for i in range(80):
                writer.writerow([f'{i:03}', f'2026-01-{i % 28 + 1:02}', f'g{i // 8}', i % 10,
                                 '' if i % 13 == 0 else ('A' if i % 2 else 'B'), i % 2, i * 1.5])

    def test_classification_pipeline_and_unknown_categories(self):
        import pandas as pd
        model, report = train(self.path, 'target', exclude=['id', 'day', 'group', 'amount'])
        self.assertEqual(report['split'], 'stratified')
        self.assertEqual(report['train_rows'] + report['test_rows'], 80)
        self.assertIn('accuracy', report['baseline'])
        self.assertEqual(len(model.predict(pd.DataFrame([{'x': 2, 'category': 'unseen'}]))), 1)

    def test_chronological_regression_and_group_split(self):
        _, report = train(self.path, 'amount', 'regression', time_column='day', exclude=['id', 'group', 'target'])
        self.assertEqual(report['split'], 'chronological')
        self.assertLess(report['split_details']['train_end'], report['split_details']['test_start'])
        self.assertNotIn('day', report['features'])
        self.assertIn('mae', report['model'])
        _, report = train(self.path, 'target', group_column='group', exclude=['id', 'day', 'amount'])
        self.assertEqual(report['split'], 'group')
        self.assertNotIn('group', report['features'])

    def test_train_predict_cli_preserves_ids_and_existing_output(self):
        import pandas as pd
        output = self.root / 'model'
        result = subprocess.run([sys.executable, '-m', 'data.train', str(self.path), '--target', 'target',
                                 '--exclude', 'id', 'day', 'group', 'amount', '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        incoming = self.root / 'incoming.csv'
        pd.DataFrame({'id': ['001', '002'], 'x': [1, 2], 'category': ['A', 'unseen']}).to_csv(incoming, index=False)
        destination = self.root / 'prediction.csv'
        command = [sys.executable, '-m', 'data.predict', '--model', str(output / 'model.joblib'),
                   '--input', str(incoming), '--output', str(destination), '--id-column', 'id']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with destination.open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([row['id'] for row in rows], ['001', '002'])
        before = destination.read_bytes()
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(destination.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
