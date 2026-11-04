import argparse
from collections import Counter, defaultdict
import csv
import io
import json
import math
from pathlib import Path
import statistics


def read_csv(text):
    if len(text) > 5_000_000:
        raise ValueError('CSV exceeds 5 million characters')
    reader = csv.reader(io.StringIO(text.lstrip('\ufeff')), strict=True)
    try:
        header = next(reader, [])
        raw_rows = list(reader)
    except csv.Error as error:
        raise ValueError('invalid CSV quoting: ' + str(error)) from error
    if not header or len(header) > 200 or len(set(header)) != len(header) or any(not x.strip() for x in header):
        raise ValueError('CSV needs 1..200 unique, nonempty column names')
    rows = []
    for n, row in enumerate(raw_rows, 2):
        if len(row) != len(header):
            raise ValueError(f'CSV row {n} has an incorrect number of cells')
        if len(rows) >= 100_000:
            raise ValueError('CSV exceeds 100000 rows')
        rows.append(dict(zip(header, row)))
    return header, rows


def finite(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def profile(text, group_by=None, value_column=None):
    header, rows = read_csv(text)
    columns = []
    for name in header:
        values = [row[name] for row in rows if row[name].strip()]
        numbers = [finite(v) for v in values]
        is_identifier = name.lower() == 'id' or name.lower().endswith('_id') or any(requires_string(v) for v in values)
        numeric = bool(values) and not is_identifier and all(v is not None for v in numbers)
        entry = {'name': name, 'kind': 'number' if numeric else 'text', 'missing': len(rows) - len(values),
                 'unique': len(set(values))}
        if numeric:
            entry.update(min=min(numbers), max=max(numbers), mean=statistics.fmean(numbers),
                         median=statistics.median(numbers), stdev=statistics.stdev(numbers) if len(numbers) > 1 else 0)
        columns.append(entry)
    result = {'rows': len(rows), 'columns': columns,
              'exact_duplicates': len(rows) - len({tuple(row.values()) for row in rows}), 'groups': [],
              'notes': ['Numeric inference is a convenience; confirm units, IDs and missing-value semantics.']}
    if group_by is not None or value_column is not None:
        if group_by not in header or value_column not in header:
            raise ValueError('group and value columns must exist')
        groups = defaultdict(list)
        for row in rows:
            value = finite(row[value_column])
            if value is not None:
                groups[row[group_by]].append(value)
        result['groups'] = [{'group': key, 'count': len(values), 'sum': sum(values), 'mean': statistics.fmean(values)}
                            for key, values in sorted(groups.items())]
    return result


def requires_string(value):
    return len(value) > 1 and value.startswith('0') and value.isdigit()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('csv')
    p.add_argument('--group-by')
    p.add_argument('--value-column')
    a = p.parse_args()
    print(json.dumps(profile(Path(a.csv).read_text(encoding='utf-8-sig'), a.group_by, a.value_column), ensure_ascii=False, indent=2))
