"""
The project's core bias-prevention check (see CLAUDE.md, "Bias-prevention
rules"). Covers macro data acquisition (src/data_acquisition/macro_pull.py)
and ratings ingestion (src/data_acquisition/ingest_ratings.py) today;
extend with walk-forward / feature-construction checks as those are built:
  - no test-window data leaks into training-window fitting, normalization,
    or feature selection stats

Run directly: python3 test_lag_rules.py
Exits 0 on pass, 1 on failure (so it can gate a pre-commit / hook check).
"""

import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parent
MACRO_CSV = REPO_ROOT / "data" / "raw" / "macro" / "macro_fundamentals.csv"
RATINGS_PANEL_CSV = REPO_ROOT / "data" / "processed" / "ratings_panel.csv"
PARAMS_YAML = REPO_ROOT / "configs" / "params.yaml"
FEATURE_MATRIX_PARQUETS = {
    "core": REPO_ROOT / "data" / "processed" / "stage1_feature_matrix_core.parquet",
    "extended": REPO_ROOT / "data" / "processed" / "stage1_feature_matrix_extended.parquet",
}
RISK_LABELS_PARQUET = REPO_ROOT / "data" / "processed" / "stage1_risk_labels.parquet"
STAGE2_PANEL_PARQUET = REPO_ROOT / "data" / "processed" / "stage2_signal_panel.parquet"
STAGE2_SIGNALS_PARQUET = REPO_ROOT / "data" / "processed" / "stage2_return_signals.parquet"

sys.path.insert(0, str(REPO_ROOT / "src" / "stage1_clustering"))
sys.path.insert(0, str(REPO_ROOT / "src" / "stage2_signal"))


def _add_months(d: date, months: int) -> date:
    y, m = d.year, d.month + months
    while m > 12:
        m -= 12
        y += 1
    return date(y, m, 1)


def test_macro_available_date_never_precedes_period_date():
    """No macro observation may claim to be usable before the period it
    describes has even ended."""
    if not MACRO_CSV.exists():
        print(f"SKIP: {MACRO_CSV} does not exist yet")
        return
    df = pd.read_csv(MACRO_CSV, parse_dates=["period_date", "available_date"])
    violations = df[df["available_date"] < df["period_date"]]
    assert violations.empty, (
        f"{len(violations)} row(s) have available_date before period_date, "
        f"e.g.:\n{violations.head()}"
    )


def test_macro_available_date_respects_configured_publication_lag():
    """For World Bank / IMF WEO rows, available_date must equal period_date
    (year-end) shifted forward by the source's configured lag in
    configs/params.yaml -- not same-day, not an arbitrary/looser gap."""
    if not MACRO_CSV.exists():
        print(f"SKIP: {MACRO_CSV} does not exist yet")
        return
    with open(PARAMS_YAML) as f:
        params = yaml.safe_load(f)["macro_acquisition"]

    df = pd.read_csv(MACRO_CSV, parse_dates=["period_date", "available_date"])
    lag_months = {
        "world_bank": params["lag_months_world_bank"],
        "imf_weo": params["lag_months_imf_weo"],
    }
    violations = []
    for source, months in lag_months.items():
        subset = df[df["source"] == source]
        for _, row in subset.iterrows():
            expected = _add_months(row["period_date"].date(), months)
            if row["available_date"].date() != expected:
                violations.append((source, row["country"], row["series"], row["period_date"]))
    assert not violations, f"{len(violations)} row(s) don't match configured lag: {violations[:5]}"


def test_macro_fred_available_date_respects_lag_days():
    """FRED (daily) rows must be lagged by exactly lag_days_fred, not
    available same-day."""
    if not MACRO_CSV.exists():
        print(f"SKIP: {MACRO_CSV} does not exist yet")
        return
    with open(PARAMS_YAML) as f:
        params = yaml.safe_load(f)["macro_acquisition"]
    lag_days = params["lag_days_fred"]

    df = pd.read_csv(MACRO_CSV, parse_dates=["period_date", "available_date"])
    subset = df[df["source"] == "fred"]
    if subset.empty:
        print("SKIP: no FRED rows present")
        return
    gaps = (subset["available_date"] - subset["period_date"]).dt.days
    assert (gaps == lag_days).all(), (
        f"FRED rows with unexpected lag (expected {lag_days} day(s)): "
        f"{sorted(gaps.unique())}"
    )


def test_feature_matrix_macro_available_date_never_exceeds_rebal_date():
    """Stage 1 feature matrix (core + extended tiers): no row's macro data
    may have available_date after the quarter it's used in -- this is the
    as-of join's core invariant (src/stage1_clustering/build_feature_matrix.py),
    tracked per row via asof_max_available_date."""
    any_present = False
    for tier, path in FEATURE_MATRIX_PARQUETS.items():
        if not path.exists():
            print(f"SKIP: {path} does not exist yet")
            continue
        any_present = True
        df = pd.read_parquet(path)
        violations = df[
            df["asof_max_available_date"].notna()
            & (df["asof_max_available_date"] > df["rebal_date"])
        ]
        assert violations.empty, (
            f"[{tier}] {len(violations)} row(s) have asof_max_available_date after "
            f"rebal_date, e.g.:\n{violations.head()}"
        )
        assert df["data_asof_ok"].all(), f"[{tier}] found row(s) with data_asof_ok=False"
    if not any_present:
        return


def test_ratings_available_date_has_zero_lag():
    """Rating actions are same-day public announcements (agency press
    releases / RNS filings), not periodic releases with a WB/IMF-style
    publication lag -- available_date must equal the action date exactly,
    per configs/params.yaml: ratings_ingestion.lag_days (see
    src/data_acquisition/ingest_ratings.py)."""
    if not RATINGS_PANEL_CSV.exists():
        print(f"SKIP: {RATINGS_PANEL_CSV} does not exist yet")
        return
    df = pd.read_csv(RATINGS_PANEL_CSV, parse_dates=["date", "available_date"])
    if df.empty:
        print(f"SKIP: {RATINGS_PANEL_CSV} has no rows yet")
        return
    with open(PARAMS_YAML) as f:
        lag_days = yaml.safe_load(f)["ratings_ingestion"]["lag_days"]

    gaps = (df["available_date"] - df["date"]).dt.days
    assert (gaps == lag_days).all(), (
        f"Ratings row(s) with unexpected lag (expected {lag_days} day(s)): "
        f"{sorted(gaps.unique())}"
    )


def test_stage1_risk_labels_training_window_never_exceeds_rebal_date():
    """Structural guard on src/stage1_clustering/build_risk_labels.py's
    output: every row's recorded training_window_end must equal its own
    rebal_date (by construction, the expanding window always stops at the
    row's own date), and training_window_start <= training_window_end.
    A cheap regression check that doesn't require re-running the model."""
    if not RISK_LABELS_PARQUET.exists():
        print(f"SKIP: {RISK_LABELS_PARQUET} does not exist yet")
        return
    df = pd.read_parquet(RISK_LABELS_PARQUET)
    bad_end = df[df["training_window_end"] != df["rebal_date"]]
    assert bad_end.empty, (
        f"{len(bad_end)} row(s) have training_window_end != rebal_date, e.g.:\n{bad_end.head()}"
    )
    with_start = df[df["training_window_start"].notna()]
    bad_order = with_start[with_start["training_window_start"] > with_start["training_window_end"]]
    assert bad_order.empty, (
        f"{len(bad_order)} row(s) have training_window_start after training_window_end, "
        f"e.g.:\n{bad_order.head()}"
    )


def test_stage1_risk_labels_no_future_leakage():
    """The real leakage check for Stage 1 clustering (thesis Sec 4.2.5):
    proves build_risk_labels.label_panel() never lets a rebalancing
    date's clustering fit see rows from a later date. Re-runs
    label_panel() on the feature matrix truncated to a cutoff date and
    asserts the labels it produces for EVERY date <= cutoff (not just the
    cutoff date itself) are identical to those in the full, already-written
    parquet -- if any future row had leaked into an earlier date's fit (via
    imputation stats, scaling stats, or the cluster fit itself), truncating
    the input would change that earlier date's labels too, since KMeans/GMM
    are refit fresh at every date using only data with rebal_date <= that
    date. Checking only the cutoff date itself would miss leakage that's
    specific to an earlier date's fit rather than uniform across the whole
    truncated run, so this compares the full truncated output (all dates
    from the start of the panel through cutoff, ~29 quarters), not one row.
    Deterministic given the fixed random_state in configs/params.yaml, so
    an exact match is the right bar, not a tolerance."""
    if not RISK_LABELS_PARQUET.exists():
        print(f"SKIP: {RISK_LABELS_PARQUET} does not exist yet")
        return

    import build_risk_labels
    from clustering_utils import feature_columns_for_tier, load_feature_matrix, load_params

    params = load_params()
    tier = params["chosen_tier"]
    algorithm = params["chosen_algorithm"]
    k = params["chosen_k"]

    full_df = load_feature_matrix(tier)
    feature_cols = feature_columns_for_tier(tier, params)
    rebal_dates = sorted(full_df["rebal_date"].unique())

    # A cutoff partway through the panel -- early enough to run fast,
    # late enough that the training window is non-trivial (past the
    # 2005-2006 insufficient-data period). Every one of the ~29 quarters
    # from the start of the panel through this cutoff is checked below.
    cutoff = rebal_dates[29]
    truncated_df = full_df[full_df["rebal_date"] <= cutoff].reset_index(drop=True)

    truncated_labels = build_risk_labels.label_panel(
        truncated_df, feature_cols, params, algorithm, k, params["random_state"], tier
    )

    full_labels = pd.read_parquet(RISK_LABELS_PARQUET)
    full_upto_cutoff = full_labels[full_labels["rebal_date"] <= cutoff].sort_values(
        ["rebal_date", "country_code"]
    ).reset_index(drop=True)
    truncated_labels = truncated_labels.sort_values(["rebal_date", "country_code"]).reset_index(drop=True)

    assert len(full_upto_cutoff) == len(truncated_labels), (
        f"Row count differs between the full-panel run ({len(full_upto_cutoff)} rows up to "
        f"{cutoff}) and the truncated run ({len(truncated_labels)} rows) -- cannot compare "
        f"row-for-row."
    )
    assert (full_upto_cutoff["country_code"].values == truncated_labels["country_code"].values).all() and (
        full_upto_cutoff["rebal_date"].values == truncated_labels["rebal_date"].values
    ).all(), "Row ordering/identity differs between the full-panel run and the truncated run."

    mismatches_by_date = (
        pd.Series(
            full_upto_cutoff["risk_label"].values != truncated_labels["risk_label"].values,
            index=full_upto_cutoff["rebal_date"],
        )
        .groupby(level=0)
        .sum()
    )
    mismatches_by_date = mismatches_by_date[mismatches_by_date > 0]
    total_mismatches = int(mismatches_by_date.sum())
    assert total_mismatches == 0, (
        f"{total_mismatches} risk_label(s) differ between the full-panel run and a run "
        f"truncated to {cutoff}, across {len(mismatches_by_date)} distinct rebalancing "
        f"date(s): {mismatches_by_date.to_dict()} -- this means future data is leaking into "
        f"an earlier rebalancing date's clustering fit."
    )


def test_stage2_target_period_end_is_next_quarter():
    """Structural guard on build_stage2_panel.py: every row's
    target_period_end (the date the forward excess-return outcome becomes
    known) must be exactly one quarter after its own rebal_date -- the
    target may never silently reach further into the future than the
    immediate next quarter."""
    if not STAGE2_PANEL_PARQUET.exists():
        print(f"SKIP: {STAGE2_PANEL_PARQUET} does not exist yet")
        return
    df = pd.read_parquet(STAGE2_PANEL_PARQUET)
    with_next = df[df["target_period_end"].notna()]
    if with_next.empty:
        print("SKIP: no rows with a target_period_end")
        return
    gap_days = (with_next["target_period_end"] - with_next["rebal_date"]).dt.days
    violations = with_next[(gap_days < 89) | (gap_days > 92)]
    assert violations.empty, (
        f"{len(violations)} row(s) have target_period_end not exactly one quarter after "
        f"rebal_date, e.g.:\n{violations[['country_name', 'rebal_date', 'target_period_end']].head()}"
    )


def test_stage2_training_window_never_uses_unrealized_target():
    """Structural guard on build_return_signals.py's score_panel output:
    every row's training_window_max_target_period_end (the latest
    target_period_end among the rows actually used to fit the model that
    scored it) must never exceed that row's own rebal_date -- the
    Stage-2-specific leakage guard, one quarter stricter than Stage 1's
    plain rebal_date <= date, because the Stage 2 target is itself a
    forward (t, t+1] return (see stage2_utils.build_expanding_train_mask)."""
    if not STAGE2_SIGNALS_PARQUET.exists():
        print(f"SKIP: {STAGE2_SIGNALS_PARQUET} does not exist yet")
        return
    df = pd.read_parquet(STAGE2_SIGNALS_PARQUET)
    with_train = df[df["training_window_max_target_period_end"].notna()]
    if with_train.empty:
        print("SKIP: no rows with a fitted training window")
        return
    violations = with_train[with_train["training_window_max_target_period_end"] > with_train["rebal_date"]]
    assert violations.empty, (
        f"{len(violations)} row(s) have training_window_max_target_period_end after "
        f"rebal_date, e.g.:\n{violations[['country_name', 'rebal_date', 'training_window_max_target_period_end']].head()}"
    )


def test_stage2_return_signals_no_future_leakage():
    """The real leakage check for Stage 2 (thesis Sec 4.3), mirroring
    test_stage1_risk_labels_no_future_leakage's design -- including the gap
    that check's own docstring flags as having been a real one caught and
    fixed in Stage 1: checking only a single cutoff date would miss leakage
    specific to one rebalancing date's fit rather than uniform across the
    whole truncated run. Re-runs build_return_signals.score_panel() on the
    Stage 2 panel truncated to a cutoff date and asserts BOTH predicted
    scores (predicted_excess_return, predicted_prob_positive) for EVERY
    date <= cutoff (not just the cutoff itself) are identical to the
    full-panel run's stored output. LASSO/L1-logistic are both
    deterministic given a fixed random_state (configs/params.yaml), so an
    exact match is the right bar, not a tolerance -- if any future row had
    leaked into an earlier date's training set (via imputation/scaling
    stats or the fit itself), truncating the input would change that
    earlier date's predictions too, since models are refit fresh at every
    date using only build_expanding_train_mask's target-realized subset."""
    if not STAGE2_SIGNALS_PARQUET.exists():
        print(f"SKIP: {STAGE2_SIGNALS_PARQUET} does not exist yet")
        return
    if not STAGE2_PANEL_PARQUET.exists():
        print(f"SKIP: {STAGE2_PANEL_PARQUET} does not exist yet")
        return

    import build_return_signals
    from stage2_utils import load_params

    params = load_params()
    full_panel = pd.read_parquet(STAGE2_PANEL_PARQUET)
    model_features = params["model_features"]
    rebal_dates = sorted(full_panel["rebal_date"].unique())
    if len(rebal_dates) < 30:
        print(f"SKIP: only {len(rebal_dates)} quarters in panel, too few for a meaningful cutoff")
        return

    # A cutoff partway through the panel, same rationale as Stage 1's
    # equivalent test: early enough to run fast, late enough that the
    # training window is non-trivial. Every one of the quarters from the
    # start of the panel through this cutoff is checked below, not just
    # the cutoff date itself.
    cutoff = rebal_dates[49]
    truncated_panel = full_panel[full_panel["rebal_date"] <= cutoff].reset_index(drop=True)

    truncated_scored = build_return_signals.score_panel(truncated_panel, model_features, params)

    full_scored = pd.read_parquet(STAGE2_SIGNALS_PARQUET)
    full_upto_cutoff = full_scored[full_scored["rebal_date"] <= cutoff].sort_values(
        ["rebal_date", "country_code"]
    ).reset_index(drop=True)
    truncated_scored = truncated_scored.sort_values(["rebal_date", "country_code"]).reset_index(drop=True)

    assert len(full_upto_cutoff) == len(truncated_scored), (
        f"Row count differs between the full-panel run ({len(full_upto_cutoff)} rows up to "
        f"{cutoff}) and the truncated run ({len(truncated_scored)} rows) -- cannot compare "
        f"row-for-row."
    )
    assert (full_upto_cutoff["country_code"].values == truncated_scored["country_code"].values).all() and (
        full_upto_cutoff["rebal_date"].values == truncated_scored["rebal_date"].values
    ).all(), "Row ordering/identity differs between the full-panel run and the truncated run."

    mismatches_by_date = {}
    for col in ["predicted_excess_return", "predicted_prob_positive"]:
        a = full_upto_cutoff[col].values.astype(float)
        b = truncated_scored[col].values.astype(float)
        # np.isclose(..., equal_nan=True) treats a NaN/NaN pair at the same
        # position as "equal" and any other mismatch (value differs, or
        # only one side is NaN) as "differs" -- exactly the comparison
        # needed here.
        differs = ~np.isclose(a, b, equal_nan=True)
        if differs.any():
            bad_dates = pd.Series(
                differs, index=full_upto_cutoff["rebal_date"]
            ).groupby(level=0).sum()
            mismatches_by_date[col] = bad_dates[bad_dates > 0].to_dict()

    total_mismatches = sum(sum(v.values()) for v in mismatches_by_date.values())
    assert total_mismatches == 0, (
        f"{total_mismatches} prediction(s) differ between the full-panel run and a run "
        f"truncated to {cutoff}, across these columns/dates: {mismatches_by_date} -- this "
        f"means future data is leaking into an earlier rebalancing date's Stage 2 model fit."
    )


CHECKS = [
    test_macro_available_date_never_precedes_period_date,
    test_macro_available_date_respects_configured_publication_lag,
    test_macro_fred_available_date_respects_lag_days,
    test_feature_matrix_macro_available_date_never_exceeds_rebal_date,
    test_ratings_available_date_has_zero_lag,
    test_stage1_risk_labels_training_window_never_exceeds_rebal_date,
    test_stage1_risk_labels_no_future_leakage,
    test_stage2_target_period_end_is_next_quarter,
    test_stage2_training_window_never_uses_unrealized_target,
    test_stage2_return_signals_no_future_leakage,
]


def main():
    failures = []
    for check in CHECKS:
        try:
            check()
            print(f"PASS: {check.__name__}")
        except AssertionError as e:
            failures.append((check.__name__, str(e)))
            print(f"FAIL: {check.__name__}: {e}")

    if failures:
        print(f"\n{len(failures)} check(s) failed.")
        return 1

    print(f"\nAll {len(CHECKS)} check(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
