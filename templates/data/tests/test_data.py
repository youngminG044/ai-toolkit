import math
import unittest
from data.analysis import profile, read_csv
from data.forecast import backtest, forecast


class AnalysisTests(unittest.TestCase):
    def test_preserves_ids_counts_missing_and_exact_duplicates(self):
        result = profile('id,team,value\n001,A,2\n002,A,\n001,A,2\n')
        columns = {c['name']: c for c in result['columns']}
        self.assertEqual(columns['id']['kind'], 'text')
        self.assertEqual(columns['value']['missing'], 1)
        self.assertEqual(columns['value']['mean'], 2)
        self.assertEqual(result['exact_duplicates'], 1)

    def test_group_means_exclude_nonfinite_and_missing_values(self):
        result = profile('team,value\nA,2\nA,4\nA,NaN\nB,-3\n', 'team', 'value')
        self.assertEqual(result['groups'], [{'group': 'A', 'count': 2, 'sum': 6, 'mean': 3},
                                           {'group': 'B', 'count': 1, 'sum': -3, 'mean': -3}])

    def test_rejects_malformed_csv_and_unknown_group_columns(self):
        for text in ['', 'a,a\n1,2', 'a,b\n1', ' ,b\n1,2', 'a\n"unterminated']:
            with self.assertRaises(ValueError):
                read_csv(text)
        with self.assertRaises(ValueError):
            profile('a\n1', 'missing', 'a')

    def test_header_only_and_bom_csv(self):
        self.assertEqual(profile('\ufeffid,value\n')['rows'], 0)
        self.assertEqual(read_csv('a,b\n"hello, world",2')[1][0]['a'], 'hello, world')

    def test_forecast_repeats_only_past_season(self):
        self.assertEqual(forecast([1, 2, 3, 4], 5, 2), [3, 4, 3, 4, 3])
        result = backtest([1, 2, 3, 4, 5, 6], holdout=2)
        self.assertEqual(result['predicted'], [4, 4])
        self.assertEqual(result['mae'], 1.5)
        self.assertEqual(backtest([0, 0, 0, 0], 2)['wape'], None)

    def test_forecast_rejects_invalid_or_nonfinite_inputs(self):
        for values, horizon, season in [([], 1, 1), ([1], 1, 2), ([math.nan], 1, 1), ([1], 0, 1)]:
            with self.assertRaises(ValueError):
                forecast(values, horizon, season)


if __name__ == '__main__':
    unittest.main()
