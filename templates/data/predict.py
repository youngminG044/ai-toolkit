"""Run inference with a model produced by this workspace; load trusted local artifacts only."""
import argparse
from pathlib import Path


if __name__ == '__main__':
    import joblib
    import pandas as pd
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', required=True)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--id-column')
    a = p.parse_args()
    if Path(a.output).exists():
        p.error('output exists')
    frame = pd.read_csv(a.input, dtype={a.id_column: 'string'} if a.id_column else None)
    prediction = joblib.load(a.model).predict(frame)
    result = pd.DataFrame({'prediction': prediction})
    if a.id_column:
        result.insert(0, a.id_column, frame[a.id_column])
    result.to_csv(a.output, index=False)
