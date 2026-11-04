#!/usr/bin/env python3
"""Summarize CSV structure without dumping source rows. Uses the standard library."""
import argparse
import csv
from collections import Counter
import json
from pathlib import Path
import sys


def profile(path, limit=100000):
    counts, missing, numeric = Counter(), Counter(), {}
    seen, duplicates, rows, malformed = set(), 0, 0, 0
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header or len(set(header)) != len(header) or any(not x for x in header):
            raise ValueError('CSV needs a nonempty, unique header')
        truncated = False
        for values in reader:
            if rows >= limit:
                truncated = True
                break
            rows += 1
            if len(values) != len(header):
                malformed += 1
                continue
            key = tuple(values)
            if key in seen:
                duplicates += 1
            seen.add(key)
            for col, value in zip(header, values):
                counts[col] += 1
                if value.strip() == '':
                    missing[col] += 1
                    continue
                try:
                    v = float(value)
                    if not (-float('inf') < v < float('inf')):
                        continue
                    lo, hi, n = numeric.get(col, (v, v, 0))
                    numeric[col] = (min(lo, v), max(hi, v), n + 1)
                except ValueError:
                    pass
    return {'path': str(path), 'rows_scanned': rows, 'truncated': truncated, 'malformed_rows': malformed,
            'exact_duplicate_rows': duplicates, 'columns': [
                {'name': col, 'missing': missing[col], 'valid_width_rows': counts[col],
                 'numeric_parse': {'min': numeric[col][0], 'max': numeric[col][1], 'count': numeric[col][2]} if col in numeric else None}
                for col in header],
            'limits': 'No business semantics, key validation, unit validation, leakage detection, or exhaustive type inference.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('path')
    p.add_argument('--limit', type=int, default=100000)
    a = p.parse_args()
    if a.limit < 1:
        p.error('--limit must be positive')
    try:
        print(json.dumps(profile(a.path, a.limit), ensure_ascii=False, indent=2))
    except (OSError, ValueError, csv.Error) as e:
        print('ERROR: ' + str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
