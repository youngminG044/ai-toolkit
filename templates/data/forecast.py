"""Chronological seasonal-naive evaluation and future baseline forecast."""
import argparse
import json
import math
from pathlib import Path
from data.analysis import read_csv


def forecast(values, horizon=5, season=1):
    if not values or horizon < 1 or season < 1 or season > len(values):
        raise ValueError('need observations, positive horizon and a valid season')
    if not all(math.isfinite(v) for v in values):
        raise ValueError('values must be finite')
    return [values[-season + i % season] for i in range(horizon)]


def backtest(values, holdout=5, season=1):
    if holdout < 1 or len(values) <= holdout + season - 1:
        raise ValueError('not enough observations for chronological holdout')
    predicted = forecast(values[:-holdout], holdout, season)
    actual = values[-holdout:]
    errors = [abs(a - b) for a, b in zip(actual, predicted)]
    denominator = sum(abs(v) for v in actual)
    return {'mae': sum(errors) / len(errors), 'wape': sum(errors) / denominator if denominator else None,
            'holdout': holdout, 'season': season, 'predicted': predicted, 'actual': actual}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv')
    p.add_argument('--value', required=True)
    p.add_argument('--horizon', type=int, default=5)
    p.add_argument('--season', type=int, default=1)
    p.add_argument('--holdout', type=int, default=5)
    a = p.parse_args()
    _, rows = read_csv(Path(a.csv).read_text(encoding='utf-8-sig'))
    values = [float(row[a.value]) for row in rows]
    print(json.dumps({'evaluation': backtest(values, a.holdout, a.season),
                      'forecast': forecast(values, a.horizon, a.season)}, indent=2))
