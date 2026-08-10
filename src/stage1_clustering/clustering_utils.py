"""Shared building blocks for Stage 1 unsupervised sovereign risk
classification (thesis Sec 4.2). Used by both `algorithm_comparison.py`
(Sec 4.2.1-4.2.3, full-sample diagnostic) and `build_risk_labels.py`
(Sec 4.2.5, walk-forward point-in-time production labels).

Two distinct clustering "modes" share the same primitives here, and it
matters which one a caller is using:
  - full-sample fit: fit once on the entire (already-lag-safe) panel,
    pooled across all quarters. Valid for descriptive/diagnostic analysis
    (which algorithm/k best recovers DM/EM structure? what do the cluster
    centroids look like economically?) because nothing downstream treats
    it as a live signal. NOT valid as an input to Stage 3/4, since a model
    fit on 2005-2025 data implicitly "knows" about 2025 when labeling a
    2008 row.
  - expanding-window fit: refit at every rebalancing date using only rows
    with rebal_date <= that date, then predict labels for that date's
    cross-section only. This is the walk-forward-safe mode and is what
    Stage 3/4 may actually consume.

See CLAUDE.md "Stage 1 clustering" for the full rationale behind the
feature set, imputation strategy, and risk-tier mapping below.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[2]

FEATURE_MATRIX_PATHS = {
    "core": REPO_ROOT / "data" / "processed" / "stage1_feature_matrix_core.parquet",
    "extended": REPO_ROOT / "data" / "processed" / "stage1_feature_matrix_extended.parquet",
}

RISK_TIERS_LOW_TO_HIGH = ["core-eligible", "excluded", "satellite-candidate"]
INSUFFICIENT_DATA_LABEL = "insufficient_data"
HDBSCAN_NOISE_RAW_LABEL = -1


def load_params() -> dict:
    with open(REPO_ROOT / "configs" / "params.yaml") as f:
        return yaml.safe_load(f)["stage1_clustering"]


def load_feature_matrix(tier: str) -> pd.DataFrame:
    if tier not in FEATURE_MATRIX_PATHS:
        raise ValueError(f"Unknown tier '{tier}', expected one of {list(FEATURE_MATRIX_PATHS)}")
    df = pd.read_parquet(FEATURE_MATRIX_PATHS[tier])
    return df.sort_values(["rebal_date", "country_code"]).reset_index(drop=True)


def feature_columns_for_tier(tier: str, params: dict) -> list[str]:
    cols = list(params["core_features"])
    if tier == "extended":
        cols += list(params["extended_additional_features"])
    return cols


def compute_n_observed(df: pd.DataFrame, feature_cols: list[str]) -> pd.Series:
    return df[feature_cols].notna().sum(axis=1)


def sufficiently_observed_mask(df: pd.DataFrame, feature_cols: list[str], min_frac: float) -> pd.Series:
    n_observed = compute_n_observed(df, feature_cols)
    threshold = math.ceil(min_frac * len(feature_cols))
    return n_observed >= threshold


def fit_impute_scale(train_df: pd.DataFrame, feature_cols: list[str]):
    """Fits a median-imputer + standard-scaler on train_df's feature
    columns and returns (imputer, scaler, X_train_transformed).

    Median imputation with training-window-only statistics is used rather
    than a more sophisticated method (e.g. KNN or MICE) as a deliberate,
    documented simplification -- see CLAUDE.md. For the 7 EM countries
    with 0% yield_spread_bps coverage (Chile, Peru, Morocco, Kazakhstan,
    Nigeria, Sri Lanka, Zambia -- see CLAUDE.md's Stage 1 feature-matrix
    section), this means their spread column is *always* imputed to the
    training-window median every quarter, so their cluster assignment is
    effectively driven by macro fundamentals and global factors alone,
    never their own market-priced spread. Flagged explicitly rather than
    silently smoothed over.
    """
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    X_train = imputer.fit_transform(train_df[feature_cols])
    X_train = scaler.fit_transform(X_train)
    return imputer, scaler, X_train


def transform_apply(imputer, scaler, apply_df: pd.DataFrame, feature_cols: list[str]) -> np.ndarray:
    X = imputer.transform(apply_df[feature_cols])
    return scaler.transform(X)


def raw_risk_proxy_per_cluster(raw_yield_spread: pd.Series, cluster_labels: np.ndarray,
                                exclude_label: int | None = None) -> dict[int, float]:
    """Mean *non-imputed* yield_spread_bps per raw cluster label -- the
    ranking signal used to map arbitrary cluster indices onto an ordered
    low/moderate/high risk scale. Uses raw (pre-imputation) values
    deliberately: ranking clusters by a partly-imputed panel median would
    bias the ranking toward the imputation fill value rather than actual
    market-observed risk.
    """
    proxy = {}
    for label in sorted(set(cluster_labels)):
        if exclude_label is not None and label == exclude_label:
            continue
        mask = cluster_labels == label
        vals = raw_yield_spread[mask]
        mean_val = vals.mean(skipna=True)
        # Fall back to 0 (mid-scale) if literally every member of this
        # cluster has no raw spread observation -- avoids NaN propagating
        # into sort ordering; such clusters are rare and are flagged by
        # the diagnostic report's coverage columns.
        proxy[label] = float(mean_val) if pd.notna(mean_val) else 0.0
    return proxy


def rank_to_tier(rank: int, n_ranked_clusters: int) -> str:
    """Buckets a 0-indexed (0 = lowest risk) cluster rank into one of the
    three thesis Sec 4.2.5 tiers. For n_ranked_clusters == 3 this is an
    exact 1:1 mapping. For other k, splits into thirds by rank so the
    bucket sizes stay balanced regardless of k -- documented in
    algorithm_comparison.py's output for whichever k is not 3."""
    third = math.ceil(n_ranked_clusters / 3)
    if rank < third:
        return "core-eligible"
    if rank >= n_ranked_clusters - third:
        return "satellite-candidate"
    return "excluded"


def cluster_labels_to_risk_tiers(cluster_labels: np.ndarray, raw_yield_spread: pd.Series,
                                  noise_label: int | None = None) -> tuple[np.ndarray, dict]:
    """Maps raw cluster labels (e.g. from KMeans/GMM/HDBSCAN) to risk-tier
    strings, ranking clusters by raw_risk_proxy_per_cluster. HDBSCAN noise
    points (raw label -1) are mapped directly to "excluded" -- an
    intentional semantic fit, not an approximation: thesis Sec 4.2.5
    defines "excluded" as moderate risk, too uncertain for either sleeve,
    which is exactly what an HDBSCAN noise point is (doesn't fit any
    density-coherent risk regime).

    Returns (risk_tier_array, {raw_label: rank}) for diagnostics.
    """
    proxy = raw_risk_proxy_per_cluster(raw_yield_spread, cluster_labels, exclude_label=noise_label)
    ordered = sorted(proxy, key=proxy.get)
    rank_of = {label: i for i, label in enumerate(ordered)}
    n = len(ordered)

    tiers = np.empty(len(cluster_labels), dtype=object)
    for i, label in enumerate(cluster_labels):
        if noise_label is not None and label == noise_label:
            tiers[i] = "excluded"
        else:
            tiers[i] = rank_to_tier(rank_of[label], n)
    return tiers, rank_of


def kmeans_bic(kmeans, X: np.ndarray) -> float:
    """Approximate BIC for a fitted KMeans model, treating each cluster as
    a spherical Gaussian with a shared variance estimated from the
    within-cluster sum of squares (the standard KMeans-as-Gaussian-mixture
    approximation, e.g. Pelleg & Moore 2000) -- KMeans has no native
    likelihood, so this is what lets it be compared to GMM's BIC/AIC on
    the same k-range as thesis Sec 4.2.2 asks for."""
    n, d = X.shape
    k = kmeans.n_clusters
    if n <= k:
        return float("inf")
    within_ss = kmeans.inertia_
    variance = within_ss / max(n - k, 1)
    if variance <= 0:
        return float("inf")
    log_likelihood = (
        -0.5 * n * d * np.log(2 * np.pi * variance)
        - 0.5 * (n - k) * d
    )
    # cluster assignment isn't a free parameter here; free params are the
    # k*d centroid coordinates plus 1 shared variance parameter.
    n_params = k * d + 1
    return -2 * log_likelihood + n_params * np.log(n)


def kmeans_aic(kmeans, X: np.ndarray, bic_value: float | None = None) -> float:
    n, d = X.shape
    k = kmeans.n_clusters
    n_params = k * d + 1
    within_ss = kmeans.inertia_
    variance = within_ss / max(n - k, 1)
    if variance <= 0:
        return float("inf")
    log_likelihood = (
        -0.5 * n * d * np.log(2 * np.pi * variance)
        - 0.5 * (n - k) * d
    )
    return -2 * log_likelihood + 2 * n_params
