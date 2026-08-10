"""Stage 1 output labeling (thesis Sec 4.2.5) -- the walk-forward-safe,
point-in-time-correct production pipeline. Assigns every sovereign, at
every rebalancing date, one of: core-eligible (low risk), excluded
(moderate risk / too uncertain), satellite-candidate (high risk), or
insufficient_data (too few observed features / too little training
history to fit a meaningful model yet).

This is deliberately a *separate* pipeline from algorithm_comparison.py's
full-sample diagnostic fit -- see clustering_utils.py's module docstring.
The core function here, `label_panel`, refits the chosen clustering model
at every rebalancing date using only rows with rebal_date <= that date
(an expanding window, same principle as the macro publication-lag and
walk-forward rules already enforced elsewhere in this repo -- see
CLAUDE.md's bias-prevention rules). This is what makes its output safe to
feed into Stage 3/4's backtest: a label assigned for 2010-06-30 cannot
have been influenced by any 2015 data.

Algorithm/tier/k are read from configs/params.yaml's stage1_clustering
section (chosen_algorithm / chosen_tier / chosen_k) -- see CLAUDE.md
"Stage 1 clustering" for why that combination was chosen over the
alternatives algorithm_comparison.py tried.

Writes: data/processed/stage1_risk_labels.parquet

Run directly: python3 src/stage1_clustering/build_risk_labels.py
"""

from __future__ import annotations

import logging

import hdbscan
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture

from clustering_utils import (
    INSUFFICIENT_DATA_LABEL,
    REPO_ROOT,
    cluster_labels_to_risk_tiers,
    compute_n_observed,
    feature_columns_for_tier,
    fit_impute_scale,
    load_feature_matrix,
    load_params,
    rank_to_tier,
    sufficiently_observed_mask,
    transform_apply,
)

logger = logging.getLogger("stage1_build_risk_labels")


def _fit_train_model(train_df: pd.DataFrame, feature_cols: list[str], algorithm: str, k,
                      random_state: int):
    """Returns (imputer, scaler, model, train_cluster_labels, noise_label)."""
    imputer, scaler, X_train = fit_impute_scale(train_df, feature_cols)
    noise_label = None
    if algorithm == "kmeans":
        model = KMeans(n_clusters=k, random_state=random_state, n_init=10).fit(X_train)
        train_labels = model.labels_
    elif algorithm == "gmm":
        model = GaussianMixture(n_components=k, random_state=random_state).fit(X_train)
        train_labels = model.predict(X_train)
    elif algorithm == "hdbscan":
        min_cluster_size = max(10, int(round(k * len(X_train)))) if k < 1 else int(k)
        model = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, prediction_data=True).fit(X_train)
        train_labels = model.labels_
        noise_label = -1
    else:
        raise ValueError(f"Unknown algorithm '{algorithm}'")
    return imputer, scaler, model, train_labels, noise_label


def _predict(algorithm: str, model, X_apply: np.ndarray) -> np.ndarray:
    if algorithm in ("kmeans", "gmm"):
        return model.predict(X_apply)
    pred, _ = hdbscan.approximate_predict(model, X_apply)
    return pred


def label_panel(df: pd.DataFrame, feature_cols: list[str], params: dict, algorithm: str,
                 k, random_state: int, tier: str) -> pd.DataFrame:
    """Pure function: no file I/O. Given the full (already lag-safe)
    feature-matrix panel, produces one output row per input row with a
    walk-forward-safe risk_label. Exposed standalone (rather than only
    reachable via main()) specifically so test_lag_rules.py can call it on
    a truncated copy of df and assert truncation invariance -- the direct
    leakage check for this stage."""
    sufficient = sufficiently_observed_mask(df, feature_cols, params["min_observed_feature_frac"])
    df = df.copy()
    df["_sufficient"] = sufficient.values
    min_rows_required = params["min_training_rows_per_k"] * (k if k >= 1 else 10)

    out_frames = []
    for date in sorted(df["rebal_date"].unique()):
        train_df = df[(df["rebal_date"] <= date) & df["_sufficient"]]
        apply_df = df[df["rebal_date"] == date]

        out = apply_df[["country_code", "country_name", "dm_em_flag", "rebal_date"]].copy()
        out["tier"] = tier
        out["algorithm"] = algorithm
        out["n_features_observed"] = compute_n_observed(apply_df, feature_cols).values
        out["training_window_start"] = train_df["rebal_date"].min() if len(train_df) else pd.NaT
        out["training_window_end"] = date
        out["training_window_n_rows"] = len(train_df)

        if len(train_df) < min_rows_required:
            out["raw_cluster_label"] = np.nan
            out["risk_label"] = INSUFFICIENT_DATA_LABEL
            out_frames.append(out)
            continue

        imputer, scaler, model, train_labels, noise_label = _fit_train_model(
            train_df, feature_cols, algorithm, k, random_state
        )
        _, rank_of = cluster_labels_to_risk_tiers(
            train_labels, train_df["yield_spread_bps"], noise_label=noise_label
        )
        n_ranked = len(rank_of)

        raw_labels = pd.Series(index=apply_df.index, dtype=object)
        risk_labels = pd.Series(index=apply_df.index, dtype=object)

        sufficient_apply = apply_df[apply_df["_sufficient"]]
        if len(sufficient_apply):
            X_apply = transform_apply(imputer, scaler, sufficient_apply, feature_cols)
            pred = _predict(algorithm, model, X_apply)
            for idx, lbl in zip(sufficient_apply.index, pred):
                raw_labels[idx] = lbl
                if noise_label is not None and lbl == noise_label:
                    risk_labels[idx] = "excluded"
                elif lbl in rank_of:
                    risk_labels[idx] = rank_to_tier(rank_of[lbl], n_ranked)
                else:
                    # A predicted cluster never seen in the training fit
                    # (possible edge case for HDBSCAN's approximate_predict
                    # against a sparse region) -- treated as "excluded"
                    # (moderate/uncertain), the same semantic used for
                    # HDBSCAN noise, rather than silently guessing a tier.
                    risk_labels[idx] = "excluded"

        insufficient_apply = apply_df[~apply_df["_sufficient"]]
        for idx in insufficient_apply.index:
            raw_labels[idx] = np.nan
            risk_labels[idx] = INSUFFICIENT_DATA_LABEL

        out["raw_cluster_label"] = raw_labels.values
        out["risk_label"] = risk_labels.values
        out_frames.append(out)

    return pd.concat(out_frames, ignore_index=True)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    params = load_params()
    tier = params["chosen_tier"]
    algorithm = params["chosen_algorithm"]
    k = params["chosen_k"]

    df = load_feature_matrix(tier)
    feature_cols = feature_columns_for_tier(tier, params)
    logger.info(
        "Building walk-forward risk labels: algorithm=%s tier=%s k=%s (%d rows, %d quarters)",
        algorithm, tier, k, len(df), df["rebal_date"].nunique(),
    )

    labels = label_panel(df, feature_cols, params, algorithm, k, params["random_state"], tier)

    output_dir = REPO_ROOT / params["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "stage1_risk_labels.parquet"
    labels.to_parquet(out_path, index=False)
    logger.info("Wrote %d rows to %s", len(labels), out_path)

    print("\n=== Risk label counts ===")
    print(labels["risk_label"].value_counts())
    print("\n=== Risk label x DM/EM crosstab (all quarters pooled) ===")
    print(pd.crosstab(labels["dm_em_flag"], labels["risk_label"]))
    print("\n=== Risk label x DM/EM crosstab (latest quarter only) ===")
    latest = labels[labels["rebal_date"] == labels["rebal_date"].max()]
    print(pd.crosstab(latest["dm_em_flag"], latest["risk_label"]))


if __name__ == "__main__":
    main()
