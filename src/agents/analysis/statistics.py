from __future__ import annotations

import numpy as np
import pandas as pd

from scipy.stats import pearsonr
from scipy.stats import ttest_ind

from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression


EXCLUDED_COLUMNS = {"postal_code", "row_id", "order_id"}


def _numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Numeric columns, with any row containing NaN in them dropped.
    Without this, scipy/sklearn functions (regression, PCA, KMeans) raise
    on missing data instead of handling it -- unlike pandas' own
    .mean()/.median()/etc., which already skip NaN by default. Made
    uniform here so every analysis function behaves consistently."""
    numeric = df.select_dtypes(include=[np.number])
    numeric = numeric.drop(columns=[c for c in EXCLUDED_COLUMNS if c in numeric.columns], errors="ignore")
    return numeric.dropna()


def _single(df: pd.DataFrame) -> pd.Series:
    numeric = _numeric(df)
    if numeric.empty:
        raise ValueError("No numeric columns found.")
    return numeric.iloc[:, 0]


def compute_mean(df): return {"analysis": "mean", "result": float(_single(df).mean())}
def compute_median(df): return {"analysis": "median", "result": float(_single(df).median())}
def compute_mode(df): return {"analysis": "mode", "result": float(_single(df).mode().iloc[0])}
def compute_variance(df): return {"analysis": "variance", "result": float(_single(df).var())}
def compute_std(df): return {"analysis": "std", "result": float(_single(df).std())}
def compute_min(df): return {"analysis": "min", "result": float(_single(df).min())}
def compute_max(df): return {"analysis": "max", "result": float(_single(df).max())}
def compute_count(df): return {"analysis": "count", "result": int(_single(df).count())}
def compute_describe(df): return {"analysis": "describe", "result": _numeric(df).describe().to_dict()}


def compute_correlation(df):
    numeric = _numeric(df)
    if numeric.shape[1] < 2:
        raise ValueError("Correlation requires two numeric columns.")
    r, p = pearsonr(numeric.iloc[:, 0], numeric.iloc[:, 1])
    return {"analysis": "correlation", "result": {"correlation": float(r), "p_value": float(p)}}


def compute_covariance(df):
    numeric = _numeric(df)
    if numeric.shape[1] < 2:
        raise ValueError("Covariance requires two numeric columns.")
    covariance = np.cov(numeric.iloc[:, 0], numeric.iloc[:, 1])[0, 1]
    return {"analysis": "covariance", "result": {"covariance": float(covariance)}}


def compute_ttest(df, group_column=None, group_values=None):
    """Compares ONE numeric variable across TWO groups defined by a
    categorical column (e.g. profit in the Consumer segment vs. profit in
    the Corporate segment) -- the standard meaning of a t-test.

    Previously this compared two numeric COLUMNS directly as independent
    samples (e.g. discount vs. profit) -- not a real two-group hypothesis
    test, since the two "samples" were different variables on different
    scales. group_column/group_values fixes this; see AnalysisPlan."""
    if group_column is None or group_values is None:
        raise ValueError("compute_ttest requires group_column and group_values "
                          "(a t-test compares one variable across two groups).")
    if group_column not in df.columns:
        raise ValueError(f"group_column '{group_column}' not found in the data.")

    numeric = _numeric(df.drop(columns=[group_column], errors="ignore"))
    if numeric.shape[1] < 1:
        raise ValueError("t-test requires at least one numeric column to compare across groups.")
    value_column = numeric.columns[0]

    a_label, b_label = group_values
    group_a = df.loc[df[group_column] == a_label, value_column].dropna()
    group_b = df.loc[df[group_column] == b_label, value_column].dropna()

    if len(group_a) < 2 or len(group_b) < 2:
        raise ValueError(
            f"Not enough data to compare: '{a_label}' has {len(group_a)} rows, "
            f"'{b_label}' has {len(group_b)} rows (need at least 2 each)."
        )

    statistic, p = ttest_ind(group_a, group_b, equal_var=False)
    return {"analysis": "ttest", "result": {
        "t_statistic": float(statistic), "p_value": float(p),
        "value_column": value_column, "group_column": group_column,
        "group_a": a_label, "group_a_mean": float(group_a.mean()), "group_a_n": int(len(group_a)),
        "group_b": b_label, "group_b_mean": float(group_b.mean()), "group_b_n": int(len(group_b)),
    }}


def compute_regression(df, target=None):
    """target: the column name to predict (y). Everything else numeric is a
    predictor (X). If target is None, falls back to the old "last column"
    convention for backward compatibility -- but callers should always pass
    target now; see AnalysisPlan.target."""
    numeric = _numeric(df)
    if numeric.shape[1] < 2:
        raise ValueError("Regression requires at least two numeric columns.")

    if target is None:
        X = numeric.iloc[:, :-1]
        y = numeric.iloc[:, -1]
        target = numeric.columns[-1]
    else:
        if target not in numeric.columns:
            raise ValueError(
                f"Regression target '{target}' not found among numeric columns: {list(numeric.columns)}"
            )
        X = numeric.drop(columns=[target])
        y = numeric[target]
        if X.shape[1] < 1:
            raise ValueError("Regression requires at least one predictor column besides the target.")

    model = LinearRegression()
    model.fit(X, y)
    return {"analysis": "regression", "result": {
        "coefficients": model.coef_.tolist(), "intercept": float(model.intercept_),
        "r2": float(model.score(X, y)), "target": target, "predictors": list(X.columns)}}


def compute_pca(df):
    numeric = _numeric(df)
    if numeric.shape[1] < 2:
        raise ValueError("PCA requires at least two numeric columns.")
    model = PCA()
    model.fit(numeric)
    return {"analysis": "pca", "result": {"explained_variance_ratio": model.explained_variance_ratio_.tolist()}}


def compute_kmeans(df, clusters=3):
    numeric = _numeric(df)
    if numeric.shape[1] < 2:
        raise ValueError("KMeans requires at least two numeric columns.")
    model = KMeans(n_clusters=clusters, random_state=42, n_init="auto")
    model.fit(numeric)
    return {"analysis": "kmeans", "result": {"centroids": model.cluster_centers_.tolist(), "inertia": float(model.inertia_)}}


ANALYSIS_FUNCTIONS = {
    "mean": compute_mean, "median": compute_median, "mode": compute_mode,
    "variance": compute_variance, "std": compute_std, "min": compute_min,
    "max": compute_max, "count": compute_count, "describe": compute_describe,
    "correlation": compute_correlation, "covariance": compute_covariance,
    "ttest": compute_ttest, "regression": compute_regression,
    "pca": compute_pca, "kmeans": compute_kmeans,
}
