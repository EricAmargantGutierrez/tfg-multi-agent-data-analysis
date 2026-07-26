"""
Statistical computations for the Analysis Agent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scipy.stats import pearsonr
from scipy.stats import ttest_ind

from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

EXCLUDED_COLUMNS = {
    "postal_code",
    "row_id",
    "order_id",
}


def _numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Return only numeric columns."""
    numeric = df.select_dtypes(include=[np.number])

    numeric = numeric.drop(
        columns=[c for c in EXCLUDED_COLUMNS if c in numeric.columns],
        errors="ignore",
    )

    return numeric


def _single(df: pd.DataFrame) -> pd.Series:
    """Return the first numeric column."""
    numeric = _numeric(df)

    if numeric.empty:
        raise ValueError("No numeric columns found.")

    return numeric.iloc[:, 0]


# ---------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------

def compute_mean(df: pd.DataFrame) -> dict:

    return {
        "analysis": "mean",
        "result": float(_single(df).mean())
    }


def compute_median(df: pd.DataFrame) -> dict:

    return {
        "analysis": "median",
        "result": float(_single(df).median())
    }


def compute_mode(df: pd.DataFrame) -> dict:

    mode = _single(df).mode()

    return {
        "analysis": "mode",
        "result": float(mode.iloc[0])
    }


def compute_variance(df: pd.DataFrame) -> dict:

    return {
        "analysis": "variance",
        "result": float(_single(df).var())
    }


def compute_std(df: pd.DataFrame) -> dict:

    return {
        "analysis": "std",
        "result": float(_single(df).std())
    }


def compute_min(df: pd.DataFrame) -> dict:

    return {
        "analysis": "min",
        "result": float(_single(df).min())
    }


def compute_max(df: pd.DataFrame) -> dict:

    return {
        "analysis": "max",
        "result": float(_single(df).max())
    }


def compute_count(df: pd.DataFrame) -> dict:

    return {
        "analysis": "count",
        "result": int(_single(df).count())
    }


def compute_describe(df: pd.DataFrame) -> dict:

    return {
        "analysis": "describe",
        "result": _numeric(df).describe().to_dict()
    }


# ---------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------

def compute_correlation(df: pd.DataFrame) -> dict:

    numeric = _numeric(df)

    if numeric.shape[1] < 2:
        raise ValueError("Correlation requires two numeric columns.")

    r, p = pearsonr(
        numeric.iloc[:, 0],
        numeric.iloc[:, 1],
    )

    return {
        "analysis": "correlation",
        "result": {
            "correlation": float(r),
            "p_value": float(p),
        },
    }


def compute_covariance(df: pd.DataFrame) -> dict:

    numeric = _numeric(df)

    if numeric.shape[1] < 2:
        raise ValueError("Covariance requires two numeric columns.")

    covariance = np.cov(
        numeric.iloc[:, 0],
        numeric.iloc[:, 1],
    )[0, 1]

    return {
        "analysis": "covariance",
        "result": {
            "covariance": float(covariance)
        },
    }


# ---------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------

def compute_ttest(df: pd.DataFrame) -> dict:

    numeric = _numeric(df)

    if numeric.shape[1] < 2:
        raise ValueError("t-test requires two numeric columns.")

    statistic, p = ttest_ind(
        numeric.iloc[:, 0],
        numeric.iloc[:, 1],
        equal_var=False,
    )

    return {
        "analysis": "ttest",
        "result": {
            "t_statistic": float(statistic),
            "p_value": float(p),
        },
    }


# ---------------------------------------------------------------------
# Machine Learning
# ---------------------------------------------------------------------

def compute_regression(df: pd.DataFrame) -> dict:

    numeric = _numeric(df)

    if numeric.shape[1] < 2:
        raise ValueError("Regression requires at least two numeric columns.")

    X = numeric.iloc[:, :-1]
    y = numeric.iloc[:, -1]

    model = LinearRegression()
    model.fit(X, y)

    return {
        "analysis": "regression",
        "result": {
            "coefficients": model.coef_.tolist(),
            "intercept": float(model.intercept_),
            "r2": float(model.score(X, y)),
        },
    }


def compute_pca(df: pd.DataFrame) -> dict:

    numeric = _numeric(df)

    if numeric.shape[1] < 2:
        raise ValueError("PCA requires at least two numeric columns.")

    model = PCA()
    model.fit(numeric)

    return {
        "analysis": "pca",
        "result": {
            "explained_variance_ratio": model.explained_variance_ratio_.tolist(),
        },
    }


def compute_kmeans(
    df: pd.DataFrame,
    clusters: int = 3,
) -> dict:

    numeric = _numeric(df)

    if numeric.shape[1] < 2:
        raise ValueError("KMeans requires at least two numeric columns.")

    model = KMeans(
        n_clusters=clusters,
        random_state=42,
        n_init="auto",
    )

    model.fit(numeric)

    return {
        "analysis": "kmeans",
        "result": {
            "centroids": model.cluster_centers_.tolist(),
            "inertia": float(model.inertia_),
        },
    }


# ---------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------

ANALYSIS_FUNCTIONS = {
    "mean": compute_mean,
    "median": compute_median,
    "mode": compute_mode,
    "variance": compute_variance,
    "std": compute_std,
    "min": compute_min,
    "max": compute_max,
    "count": compute_count,
    "describe": compute_describe,
    "correlation": compute_correlation,
    "covariance": compute_covariance,
    "ttest": compute_ttest,
    "regression": compute_regression,
    "pca": compute_pca,
    "kmeans": compute_kmeans,
}