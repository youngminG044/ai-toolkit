"""Local tabular baseline training; preprocessing is fitted on training data only."""
import argparse
import json
from pathlib import Path


def train(csv_path, target, task='classification', time_column=None, group_column=None,
          exclude=(), seed=42, test_fraction=0.2):
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.dummy import DummyClassifier, DummyRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, mean_absolute_error, mean_squared_error
    from sklearn.model_selection import GroupShuffleSplit, train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    if task not in {'classification', 'regression'} or not 0 < test_fraction < 1:
        raise ValueError('invalid task or test fraction')
    if time_column and group_column:
        raise ValueError('choose chronological or group split, not both')
    df = pd.read_csv(csv_path)
    if target not in df or df[target].isna().any() or len(df) < 10:
        raise ValueError('need at least 10 rows with a nonmissing target')
    split_details = {}
    if time_column:
        df = df.assign(**{time_column: pd.to_datetime(df[time_column], utc=True, errors='raise')}).sort_values(time_column, kind='stable')
        if df[time_column].isna().any():
            raise ValueError('time values must not be missing')
        cut = int(len(df) * (1 - test_fraction))
        boundary = df[time_column].iloc[cut]
        train_index = [i for i, time in enumerate(df[time_column]) if time < boundary]
        test_index = [i for i, time in enumerate(df[time_column]) if time >= boundary]
        if not train_index or not test_index:
            raise ValueError('need distinct timestamps on both sides of the split')
        split = 'chronological'
        split_details = {'test_start': str(boundary), 'train_end': str(df[time_column].iloc[train_index[-1]])}
    elif group_column:
        if df[group_column].isna().any():
            raise ValueError('group values must not be missing')
        train_index, test_index = next(GroupShuffleSplit(n_splits=1, test_size=test_fraction, random_state=seed).split(df, groups=df[group_column]))
        split = 'group'
        split_details = {'train_groups': int(df[group_column].iloc[train_index].nunique()),
                         'test_groups': int(df[group_column].iloc[test_index].nunique())}
    else:
        train_index, test_index = train_test_split(list(range(len(df))), test_size=test_fraction,
            random_state=seed, stratify=df[target] if task == 'classification' else None)
        split = 'stratified' if task == 'classification' else 'random'
    features = df.drop(columns=[target, *exclude, *([time_column] if time_column else []), *([group_column] if group_column else [])])
    if features.empty:
        raise ValueError('no feature columns remain')
    numeric = list(features.select_dtypes(include='number').columns)
    categorical = [name for name in features.columns if name not in numeric]
    prep = ColumnTransformer([
        ('numeric', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), numeric),
        ('category', Pipeline([('impute', SimpleImputer(strategy='most_frequent')),
                               ('encode', OneHotEncoder(handle_unknown='ignore', sparse_output=True))]), categorical)])
    model = Pipeline([('preprocess', prep), ('estimator', LogisticRegression(max_iter=1000, class_weight='balanced', random_state=seed)
                      if task == 'classification' else Ridge())])
    x_train, x_test = features.iloc[train_index], features.iloc[test_index]
    y_train, y_test = df[target].iloc[train_index], df[target].iloc[test_index]
    baseline = DummyClassifier(strategy='most_frequent') if task == 'classification' else DummyRegressor(strategy='mean')
    baseline.fit(x_train, y_train)
    model.fit(x_train, y_train)
    def metrics(prediction):
        if task == 'classification':
            return {'accuracy': accuracy_score(y_test, prediction), 'balanced_accuracy': balanced_accuracy_score(y_test, prediction)}
        return {'mae': mean_absolute_error(y_test, prediction), 'rmse': mean_squared_error(y_test, prediction) ** 0.5}
    report = {'task': task, 'split': split, 'split_details': split_details, 'seed': seed, 'train_rows': len(train_index), 'test_rows': len(test_index),
              'features': list(features.columns), 'baseline': metrics(baseline.predict(x_test)),
              'model': metrics(model.predict(x_test)), 'scope': 'single held-out evaluation; no production performance guarantee'}
    return model, report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv')
    p.add_argument('--target', required=True)
    p.add_argument('--task', choices=['classification', 'regression'], default='classification')
    p.add_argument('--time-column')
    p.add_argument('--group-column')
    p.add_argument('--exclude', nargs='*', default=[])
    p.add_argument('--output', required=True, help='new directory for model and metrics')
    a = p.parse_args()
    out = Path(a.output)
    if out.exists():
        p.error('output already exists; choose a fresh directory')
    model, report = train(a.csv, a.target, a.task, a.time_column, a.group_column, a.exclude)
    import joblib
    out.mkdir(parents=True)
    joblib.dump(model, out / 'model.joblib')
    (out / 'metrics.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
