"""Stage 1 algorithm comparison and DM/EM validation (thesis Sec 4.2.1-4.2.3).

Full-sample, diagnostic-only analysis -- see clustering_utils.py's module
docstring for why this is explicitly NOT the point-in-time-safe pipeline
that feeds Stage 3/4 (that's build_risk_labels.py). This script exists to
answer three questions with real numbers rather than assumption:
  1. Which algorithm (K-Means / GMM / HDBSCAN) and tier (core / extended)
     best separates sovereign risk?
  2. What k best fits the data (thesis expects, but does not require, 3)?
  3. Does the resulting clustering recover the DM/EM split without being
     given that label (Adjusted Rand Index), and where does it disagree,
     per rebalancing date?

Writes:
  data/processed/stage1_algorithm_comparison.csv   -- one row per
    (tier, algorithm, k or min_cluster_size) combination tried.
  data/processed/stage1_dmem_disagreements.csv      -- per-quarter,
    per-country disagreements between assigned risk tier and dm_em_flag,
    for the algorithm/tier/k combo chosen as best.

Run directly: python3 src/stage1_clustering/algorithm_comparison.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import hdbscan
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.mixture import GaussianMixture

from clustering_utils import (
    REPO_ROOT,
    cluster_labels_to_risk_tiers,
    feature_columns_for_tier,
    fit_impute_scale,
    kmeans_aic,
    kmeans_bic,
    load_feature_matrix,
    load_params,
    sufficiently_observed_mask,
)

logger = logging.getLogger("stage1_algorithm_comparison")


def prepare_analysis_df(tier: str, params: dict) -> tuple[pd.DataFrame, list[str]]:
    df = load_feature_matrix(tier)
    feature_cols = feature_columns_for_tier(tier, params)
    mask = sufficiently_observed_mask(df, feature_cols, params["min_observed_feature_frac"])
    analysis_df = df[mask].reset_index(drop=True)
    n_excluded = int((~mask).sum())
    logger.info(
        "[%s] %d/%d rows sufficiently observed (>=%.0f%% of %d features); %d excluded as insufficient_data",
        tier, len(analysis_df), len(df), params["min_observed_feature_frac"] * 100,
        len(feature_cols), n_excluded,
    )
    return analysis_df, feature_cols


def run_kmeans_gmm_sweep(tier: str, analysis_df: pd.DataFrame, feature_cols: list[str],
                          X: np.ndarray, params: dict, results: list[dict]):
    dm_em = (analysis_df["dm_em_flag"] == "EM").astype(int).values
    for k in params["kmeans_gmm_k_range"]:
        km = KMeans(n_clusters=k, random_state=params["random_state"], n_init=10).fit(X)
        sil = silhouette_score(X, km.labels_)
        ari = adjusted_rand_score(dm_em, km.labels_)
        results.append({
            "tier": tier, "algorithm": "kmeans", "k_or_mcs": k,
            "silhouette": sil, "bic": kmeans_bic(km, X), "aic": kmeans_aic(km, X),
            "ari_vs_dm_em": ari, "n_clusters_found": k, "noise_frac": 0.0,
        })

        gmm = GaussianMixture(n_components=k, random_state=params["random_state"]).fit(X)
        gmm_labels = gmm.predict(X)
        sil_gmm = silhouette_score(X, gmm_labels)
        ari_gmm = adjusted_rand_score(dm_em, gmm_labels)
        results.append({
            "tier": tier, "algorithm": "gmm", "k_or_mcs": k,
            "silhouette": sil_gmm, "bic": gmm.bic(X), "aic": gmm.aic(X),
            "ari_vs_dm_em": ari_gmm, "n_clusters_found": k, "noise_frac": 0.0,
        })


def run_hdbscan_sweep(tier: str, analysis_df: pd.DataFrame, X: np.ndarray, params: dict,
                       results: list[dict]):
    dm_em = (analysis_df["dm_em_flag"] == "EM").astype(int).values
    n = len(X)
    for frac in params["hdbscan_min_cluster_size_fracs"]:
        min_cluster_size = max(10, int(round(frac * n)))
        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, prediction_data=True)
        labels = clusterer.fit_predict(X)
        noise_frac = float((labels == -1).mean())
        non_noise = labels != -1
        n_found = len(set(labels[non_noise]))
        if non_noise.sum() > 1 and n_found > 1:
            sil = silhouette_score(X[non_noise], labels[non_noise])
            ari = adjusted_rand_score(dm_em[non_noise], labels[non_noise])
        else:
            sil, ari = float("nan"), float("nan")
        results.append({
            "tier": tier, "algorithm": "hdbscan", "k_or_mcs": min_cluster_size,
            "silhouette": sil, "bic": float("nan"), "aic": float("nan"),
            "ari_vs_dm_em": ari, "n_clusters_found": n_found, "noise_frac": noise_frac,
        })


def per_quarter_dmem_disagreements(analysis_df: pd.DataFrame, risk_tiers: np.ndarray) -> pd.DataFrame:
    """For the chosen algorithm/tier/k, list every EM country landing in
    'core-eligible' and every DM country landing in 'satellite-candidate',
    per rebalancing date -- the disagreement structure thesis Sec 4.2.3
    asks for, not just a single aggregate ARI number. This uses the
    full-sample-fitted labels (diagnostic mode); see module docstring."""
    d = analysis_df[["country_code", "country_name", "dm_em_flag", "rebal_date"]].copy()
    d["risk_tier"] = risk_tiers
    disagreements = d[
        ((d["dm_em_flag"] == "EM") & (d["risk_tier"] == "core-eligible"))
        | ((d["dm_em_flag"] == "DM") & (d["risk_tier"] == "satellite-candidate"))
    ].sort_values(["rebal_date", "country_name"])
    return disagreements


def per_quarter_ari(analysis_df: pd.DataFrame, cluster_labels: np.ndarray) -> pd.DataFrame:
    d = analysis_df[["rebal_date", "dm_em_flag"]].copy()
    d["cluster_label"] = cluster_labels
    rows = []
    for date, g in d.groupby("rebal_date"):
        if g["cluster_label"].nunique() < 2 or g["dm_em_flag"].nunique() < 2:
            rows.append({"rebal_date": date, "ari_vs_dm_em": float("nan"), "n_countries": len(g)})
            continue
        dm_em = (g["dm_em_flag"] == "EM").astype(int)
        rows.append({
            "rebal_date": date,
            "ari_vs_dm_em": adjusted_rand_score(dm_em, g["cluster_label"]),
            "n_countries": len(g),
        })
    return pd.DataFrame(rows)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    params = load_params()
    output_dir = REPO_ROOT / params["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    prepared = {}
    for tier in ["core", "extended"]:
        analysis_df, feature_cols = prepare_analysis_df(tier, params)
        _, _, X = fit_impute_scale(analysis_df, feature_cols)
        prepared[tier] = (analysis_df, feature_cols, X)
        run_kmeans_gmm_sweep(tier, analysis_df, feature_cols, X, params, results)
        run_hdbscan_sweep(tier, analysis_df, X, params, results)

    comparison = pd.DataFrame(results)
    comparison_path = output_dir / "stage1_algorithm_comparison.csv"
    comparison.to_csv(comparison_path, index=False)
    logger.info("Wrote %d comparison rows to %s", len(comparison), comparison_path)

    print("\n=== Algorithm comparison (silhouette / BIC / AIC / ARI vs DM-EM) ===")
    with pd.option_context("display.max_rows", None, "display.width", 160):
        print(comparison.sort_values(["tier", "algorithm", "k_or_mcs"]).to_string(index=False))

    # Best silhouette per (tier, algorithm) -- printed as a decision aid;
    # the actual chosen_* fields in configs/params.yaml are set by hand
    # after reviewing this table's economic interpretability, not purely
    # by picking the max silhouette (see CLAUDE.md "Stage 1 clustering").
    best_per_combo = (
        comparison.sort_values("silhouette", ascending=False)
        .groupby(["tier", "algorithm"], as_index=False)
        .first()
    )
    print("\n=== Best-silhouette k (or min_cluster_size) per tier x algorithm ===")
    print(best_per_combo.sort_values(["tier", "algorithm"]).to_string(index=False))

    chosen_tier = params["chosen_tier"]
    chosen_algorithm = params["chosen_algorithm"]
    chosen_k = params["chosen_k"]
    analysis_df, feature_cols, X = prepared[chosen_tier]

    if chosen_algorithm == "kmeans":
        model = KMeans(n_clusters=chosen_k, random_state=params["random_state"], n_init=10).fit(X)
        cluster_labels = model.labels_
        noise_label = None
    elif chosen_algorithm == "gmm":
        model = GaussianMixture(n_components=chosen_k, random_state=params["random_state"]).fit(X)
        cluster_labels = model.predict(X)
        noise_label = None
    else:
        n = len(X)
        min_cluster_size = max(10, int(round(chosen_k * n))) if chosen_k < 1 else int(chosen_k)
        model = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, prediction_data=True).fit(X)
        cluster_labels = model.labels_
        noise_label = -1

    risk_tiers, rank_of = cluster_labels_to_risk_tiers(
        cluster_labels, analysis_df["yield_spread_bps"], noise_label=noise_label
    )
    overall_ari = adjusted_rand_score(
        (analysis_df["dm_em_flag"] == "EM").astype(int), cluster_labels
    )
    print(f"\n=== Chosen combo: {chosen_algorithm} / {chosen_tier} / k={chosen_k} ===")
    print(f"Overall ARI vs DM/EM: {overall_ari:.4f}")
    print("Risk tier counts:", pd.Series(risk_tiers).value_counts().to_dict())

    disagreements = per_quarter_dmem_disagreements(analysis_df, risk_tiers)
    disagreements_path = output_dir / "stage1_dmem_disagreements.csv"
    disagreements.to_csv(disagreements_path, index=False)
    logger.info("Wrote %d disagreement rows to %s", len(disagreements), disagreements_path)
    print(f"\nDisagreement rows (EM in core-eligible or DM in satellite-candidate): {len(disagreements)}")
    if len(disagreements):
        print(disagreements.head(20).to_string(index=False))

    quarterly_ari = per_quarter_ari(analysis_df, cluster_labels)
    quarterly_ari_path = output_dir / "stage1_dmem_ari_by_quarter.csv"
    quarterly_ari.to_csv(quarterly_ari_path, index=False)
    logger.info("Wrote %d per-quarter ARI rows to %s", len(quarterly_ari), quarterly_ari_path)
    print(f"\nPer-quarter ARI: mean={quarterly_ari['ari_vs_dm_em'].mean():.4f}, "
          f"min={quarterly_ari['ari_vs_dm_em'].min():.4f}, max={quarterly_ari['ari_vs_dm_em'].max():.4f}")


if __name__ == "__main__":
    main()
