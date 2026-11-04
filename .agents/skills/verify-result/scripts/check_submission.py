#!/usr/bin/env python3
"""Validate an explicit CSV delivery contract; does not judge prediction correctness."""
import argparse
import csv
import json
from pathlib import Path
import sys


def inspect(path, id_column=None, required_columns=()):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        header = next(reader, [])
        errors = []
        if not header or any(not name for name in header) or len(set(header)) != len(header):
            return {'header': header, 'rows': 0, 'ids': [], 'errors': ['invalid or duplicate header']}
        requested = set(required_columns) | ({id_column} if id_column else set())
        for name in sorted(requested - set(header)):
            errors.append('missing declared column: ' + name)
        indices = [(name, header.index(name)) for name in required_columns if name in header]
        id_index = header.index(id_column) if id_column in header else None
        count, malformed, empty, ids = 0, 0, 0, []
        for row in reader:
            count += 1
            if len(row) != len(header):
                malformed += 1
                continue
            empty += sum(not row[index].strip() for _, index in indices)
            if id_index is not None:
                ids.append(row[id_index])
        if malformed:
            errors.append('rows with incorrect width: ' + str(malformed))
        if empty:
            errors.append('empty required cells: ' + str(empty))
        if id_index is not None:
            if any(not value.strip() for value in ids):
                errors.append('empty ID')
            if len(ids) != len(set(ids)):
                errors.append('duplicate ID')
        return {'header': header, 'rows': count, 'ids': ids, 'errors': errors}


def validate(candidate, sample=None, columns=None, rows=None, match_rows=False,
             id_column=None, required_columns=()):
    if rows is not None and (not isinstance(rows, int) or rows < 0):
        raise ValueError('rows must be a nonnegative integer')
    if (match_rows or id_column) and not sample:
        raise ValueError('matching row count or ID order requires --sample')
    if not any((sample, columns, rows is not None, required_columns)):
        return {'status': 'NOT_RUN', 'reason': 'no delivery contract declared'}, 2
    actual = inspect(candidate, id_column, required_columns)
    errors = list(actual['errors'])
    expected = inspect(sample, id_column) if sample else None
    if expected and expected['errors']:
        errors.extend('reference: ' + error for error in expected['errors'])
    if columns is not None and expected and list(columns) != expected['header']:
        raise ValueError('declared columns conflict with reference header')
    header = list(columns) if columns is not None else expected['header'] if expected else None
    if header is not None and actual['header'] != header:
        errors.append('column names or order differ')
    if rows is not None and actual['rows'] != rows:
        errors.append('row count differs from declared count')
    if match_rows and actual['rows'] != expected['rows']:
        errors.append('row count differs from reference')
    if id_column and actual['ids'] != expected['ids']:
        errors.append('ID values or order differ from reference')
    result = {'status': 'FAIL' if errors else 'PASS', 'rows': actual['rows'],
              'columns': actual['header'], 'errors': errors,
              'scope': 'CSV structure and declared constraints only; no semantic or prediction-quality verdict.'}
    return result, 1 if errors else 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate')
    p.add_argument('--sample')
    p.add_argument('--columns', nargs='+')
    p.add_argument('--rows', type=int)
    p.add_argument('--match-rows', action='store_true')
    p.add_argument('--id-column')
    p.add_argument('--required-column', action='append', default=[])
    a = p.parse_args()
    try:
        result, code = validate(a.candidate, a.sample, a.columns, a.rows, a.match_rows,
                                a.id_column, a.required_column)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
    except (OSError, ValueError, csv.Error) as e:
        print('ERROR: ' + str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
