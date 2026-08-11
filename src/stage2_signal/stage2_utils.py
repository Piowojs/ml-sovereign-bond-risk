"""Shared building blocks for Stage 2 compensated EM sovereign risk
identification (thesis Sec 4.3). Used by build_stage2_panel.py (target +
feature construction), model_comparison.py (Sec 4.3.3 diagnostic),
build_return_signals.py (Sec 4.3.5 production walk-forward pipeline), and
feature_importance.py (Sec 4.3.4 SHAP).

Stage 2 operates only on the EM subset of Stage 1's satellite-candidate
output (data/processed/stage1_risk_labels.parquet) -- see CLAUDE.md
"Stage 2 signal" for the full data-gap writeup this module's choices are
built around: no explicit coupon-rate/cashflow field exists anywhere in
the raw bond pull, so total return is a documented price-return-based
proxy, not a true coupon-inclusive total return, except where DIRTY_PRC
(accrued interest) is available.

Two walk-forward "fold" concepts matter here and must not be conflated:
  - a rebalancing date's *features* must only use data with rebal_date <=
    that date (the Stage 1 principle, reused via the already lag-safe
    Stage 1 core feature matrix for the macro/global columns).
  - a rebalancing date's *training set* additionally requires the target
    to already be REALIZED -- i.e. target_period_end <= that date -- since
    the target itself is a forward (t, t+1] return. This is one quarter
    stricter than Stage 1's expanding window and is the single most
    important leakage-prevention detail specific to Stage 2 (see
    build_expanding_train_mask below).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[2]

STAGE1_CORE_PARQUET = REPO_ROOT / "data" / "processed" / "stage1_feature_matrix_core.parquet"
STAGE1_RISK_LABELS_PARQUET = REPO_ROOT / "data" / "processed" / "stage1_risk_labels.parquet"
MACRO_CSV = REPO_ROOT / "data" / "raw" / "macro" / "macro_fundamentals.csv"
STAGE2_PANEL_PARQUET = REPO_ROOT / "data" / "processed" / "stage2_signal_panel.parquet"

INSUFFICIENT_DATA_LABEL = "insufficient_data"


def load_params() -> dict:
    with open(REPO_ROOT / "configs" / "params.yaml") as f:
        return yaml.safe_load(f)["stage2_signal"]


def load_universe() -> list[dict]:
    with open(REPO_ROOT / "configs" / "universe.yaml") as f:
        return yaml.safe_load(f)["universe"]


def bond_file_path(country_name: str) -> Path:
    return REPO_ROOT / "data" / "raw" / "bonds" / f"{country_name.replace(' ', '_')}.csv"


def load_raw_bond_daily(country_name: str) -> pd.DataFrame | None:
    path = bond_file_path(country_name)
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    if df.empty:
        return None
    return df.set_index("date").sort_index()


def best_price_series(df: pd.DataFrame, priority: list[str]) -> tuple[pd.Series, str]:
    """Picks the first field in `priority` order with any non-null values.
    `synthetic_mid` is not a raw column -- it's (BID+ASK)/2, computed on
    the fly, the last-resort fallback for the 2 countries (Kazakhstan,
    Morocco) with no MID_PRICE/CLEAN_PRC column at all (both have BID/ASK
    at ~99-100%/~74-99% coverage). Returns (price_series, field_used);
    field_used == "" if no usable price data exists at all."""
    for field in priority:
        if field == "synthetic_mid":
            if "BID" in df.columns and "ASK" in df.columns:
                mid = (df["BID"] + df["ASK"]) / 2
                if mid.notna().any():
                    return mid, "synthetic_mid"
            continue
        if field in df.columns and df[field].notna().any():
            return df[field], field
    return pd.Series(dtype=float), ""


def quarterly_last(series: pd.Series, rebal_dates: pd.DatetimeIndex) -> pd.Series:
    q = series.resample("QE").last()
    return q.reindex(rebal_dates)


def asof_lookback(daily: pd.Series, target_date: pd.Timestamp, lookback_days: int,
                   tolerance_days: int) -> float:
    """Value of `daily` at the latest available date <= (target_date -
    lookback_days), but no earlier than (target_date - lookback_days -
    tolerance_days) -- i.e. a backward as-of lookup with a bounded staleness
    window, so a momentum feature never silently reaches back months beyond
    its intended lookback when a country's price series has a gap."""
    if daily.empty:
        return float("nan")
    anchor = target_date - pd.Timedelta(days=lookback_days)
    floor = anchor - pd.Timedelta(days=tolerance_days)
    window = daily[(daily.index <= anchor) & (daily.index >= floor)]
    if window.empty:
        return float("nan")
    return float(window.iloc[-1])


def forward_price_asof(daily: pd.Series, anchor_date: pd.Timestamp, horizon_days: int,
                        tolerance_days: int) -> float:
    """Value of `daily` at the latest available date <= (anchor_date +
    horizon_days), but no earlier than (anchor_date + horizon_days -
    tolerance_days) -- the forward-looking counterpart to asof_lookback,
    used only for constructing HISTORICAL targets (multi_horizon_
    robustness.py), never for a live feature: this looks *ahead* of
    anchor_date, which is only valid because anchor_date is itself in the
    past relative to when this function runs, and the resulting target is
    never fed back in as a feature for any date <= its own realization."""
    if daily.empty:
        return float("nan")
    target = anchor_date + pd.Timedelta(days=horizon_days)
    floor = target - pd.Timedelta(days=tolerance_days)
    window = daily[(daily.index <= target) & (daily.index >= floor)]
    if window.empty:
        return float("nan")
    return float(window.iloc[-1])


def rolling_zscore_asof(daily: pd.Series, target_date: pd.Timestamp, window_days: int) -> float:
    """(current - trailing mean) / trailing std over `window_days` ending at
    (and including) target_date -- uses only data with date <= target_date,
    so it is safe to compute at a rebalancing date."""
    if daily.empty:
        return float("nan")
    window = daily[(daily.index <= target_date) & (daily.index > target_date - pd.Timedelta(days=window_days))]
    window = window.dropna()
    if len(window) < 10:
        return float("nan")
    current = window.iloc[-1]
    mean, std = window.mean(), window.std()
    if not std or math.isnan(std) or std == 0:
        return float("nan")
    return float((current - mean) / std)


def load_us_3m_tbill(rebal_dates: pd.DatetimeIndex, params: dict) -> pd.Series:
    """Backward as-of join of the 3-month US T-bill yield (added to
    macro_pull.py's FRED_SERIES for this stage -- see CLAUDE.md) onto the
    rebalancing-date grid, same principle as build_feature_matrix.py's
    build_global_series."""
    macro_df = pd.read_csv(MACRO_CSV, parse_dates=["period_date", "available_date"])
    sub = (
        macro_df[
            (macro_df["country"] == params["risk_free_country_tag"])
            & (macro_df["series"] == params["risk_free_series"])
        ][["available_date", "value"]]
        .sort_values("available_date")
    )
    left = pd.DataFrame({"rebal_date": rebal_dates})
    merged = pd.merge_asof(left, sub, left_on="rebal_date", right_on="available_date", direction="backward")
    return merged.set_index("rebal_date")["value"]


def load_satellite_em_universe() -> pd.DataFrame:
    """The Stage 2 population: (country, rebal_date) rows with
    dm_em_flag == 'EM' and risk_label == 'satellite-candidate' in Stage 1's
    walk-forward output -- deliberately excludes the occasional DM rows
    that land in satellite-candidate under Stage 1's documented residual
    global-feature regime artifact (see CLAUDE.md 'Stage 1 clustering'),
    since this stage is scoped to the EM universe per thesis Ch.1/Sec 4.4.1."""
    labels = pd.read_parquet(STAGE1_RISK_LABELS_PARQUET)
    sat = labels[(labels["dm_em_flag"] == "EM") & (labels["risk_label"] == "satellite-candidate")]
    return sat[["country_code", "country_name", "dm_em_flag", "rebal_date"]].reset_index(drop=True)


def compute_n_observed(df: pd.DataFrame, feature_cols: list[str]) -> pd.Series:
    return df[feature_cols].notna().sum(axis=1)


def sufficiently_observed_mask(df: pd.DataFrame, feature_cols: list[str], min_frac: float) -> pd.Series:
    n_observed = compute_n_observed(df, feature_cols)
    threshold = math.ceil(min_frac * len(feature_cols))
    return n_observed >= threshold


def fit_impute_scale(train_df: pd.DataFrame, feature_cols: list[str]):
    """Training-window-only median imputation + standard scaling -- same
    convention and same rationale as Stage 1's clustering_utils.py."""
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    # keep_empty_features=True: Stage 2's small per-fold sample sizes mean a
    # feature (e.g. yield_spread_bps, sparse for several EM countries -- see
    # CLAUDE.md) can be 100% missing within a single fold's training window
    # even though it isn't globally. Without this, SimpleImputer silently
    # *drops* such a column for that fold only, changing the feature space
    # fold-to-fold and breaking the fixed feature-name <-> column-index
    # mapping feature_importance.py's SHAP output relies on. With it, an
    # all-missing column is filled with 0 (post-scaling, contributes no
    # signal) instead of vanishing.
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    scaler = StandardScaler()
    X_train = imputer.fit_transform(train_df[feature_cols])
    X_train = scaler.fit_transform(X_train)
    return imputer, scaler, X_train


def transform_apply(imputer, scaler, apply_df: pd.DataFrame, feature_cols: list[str]) -> np.ndarray:
    X = imputer.transform(apply_df[feature_cols])
    return scaler.transform(X)


def build_expanding_train_mask(panel: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.Series:
    """The Stage-2-specific leakage guard: a row is eligible for training a
    model used to predict at `as_of_date` only if BOTH its own features are
    already knowable (rebal_date <= as_of_date, inherited from Stage 1's
    already lag-safe inputs) AND its target is already realized
    (target_period_end <= as_of_date) -- one quarter stricter than Stage 1's
    plain rebal_date <= date, because the target here is itself a forward
    return. See this module's docstring."""
    return (panel["rebal_date"] <= as_of_date) & (panel["target_period_end"] <= as_of_date)


def make_models(params: dict, random_state: int):
    """Returns {"classification": {name: estimator}, "regression": {name: estimator}}
    -- LASSO / Random Forest / XGBoost per thesis Sec 4.3.3, with the
    classification framing's LASSO counterpart being L1-penalized logistic
    regression (LASSO itself is a regression method; this is the standard
    like-for-like classification analogue, not a fourth model)."""
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.linear_model import Lasso, LogisticRegression
    from xgboost import XGBClassifier, XGBRegressor

    classification = {
        "lasso_logistic": LogisticRegression(
            l1_ratio=1.0, solver="liblinear", C=params["logistic_C"], random_state=random_state
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=params["rf_n_estimators"], max_depth=params["rf_max_depth"],
            random_state=random_state,
        ),
        "xgboost": XGBClassifier(
            n_estimators=params["xgb_n_estimators"], max_depth=params["xgb_max_depth"],
            learning_rate=params["xgb_learning_rate"], random_state=random_state,
            eval_metric="logloss",
        ),
    }
    regression = {
        "lasso": Lasso(alpha=params["lasso_alpha"], random_state=random_state),
        "random_forest": RandomForestRegressor(
            n_estimators=params["rf_n_estimators"], max_depth=params["rf_max_depth"],
            random_state=random_state,
        ),
        "xgboost": XGBRegressor(
            n_estimators=params["xgb_n_estimators"], max_depth=params["xgb_max_depth"],
            learning_rate=params["xgb_learning_rate"], random_state=random_state,
        ),
    }
    return {"classification": classification, "regression": regression}


def information_coefficient(predicted: np.ndarray, realized: np.ndarray) -> float:
    """Spearman rank correlation between predicted and realized excess
    returns -- the IC definition thesis Sec 1.5/H2 specifies."""
    if len(predicted) < 3:
        return float("nan")
    ic, _ = stats.spearmanr(predicted, realized)
    return float(ic)


def ic_one_sided_ttest(fold_ics: list[float]) -> tuple[float, float]:
    """One-sided t-test of mean IC > 0 across fold observations, per H2's
    test design (thesis Sec 1.5): 'Test whether the mean IC is
    significantly greater than zero using a one-sided t-test across fold
    observations.' Returns (t_statistic, one_sided_p_value)."""
    fold_ics = [x for x in fold_ics if not math.isnan(x)]
    if len(fold_ics) < 2:
        return float("nan"), float("nan")
    t_stat, two_sided_p = stats.ttest_1samp(fold_ics, popmean=0.0)
    one_sided_p = two_sided_p / 2 if t_stat > 0 else 1 - two_sided_p / 2
    return float(t_stat), float(one_sided_p)
