"""H2 multi-horizon robustness check -- PRE-REGISTERED 2026-08-11, see
state.md's "PRE-REGISTRATION: H2 multi-horizon robustness check" entry
(committed before this script was run) for the full protocol and
rationale. Do not read this docstring as post-hoc justification -- the
protocol below was fixed and committed first.

Tests whether Stage 2's quarterly target horizon (chosen to match
rebalancing frequency, thesis Sec 4.4.3, not derived from a theoretical
claim about where sovereign return predictability appears -- Sec 2.4's
factor literature spans 1-12 months) is masking a stronger signal at a
shorter (monthly) or longer (semi-annual) horizon.

Design, exactly as pre-registered:
  - Same population at all three horizons: the (country, rebal_date) rows
    already in data/processed/stage2_signal_panel.parquet (Stage 1's EM
    satellite-candidate cross-sections). The observation calendar stays
    quarterly -- this does NOT re-run Stage 1 at monthly/semi-annual
    frequency, it only changes how far forward the return target looks
    from each existing quarterly observation date.
  - Same features at all three horizons -- reused unchanged from the
    existing panel (as-of rebal_date, horizon-independent).
  - Quarterly reuses the existing panel's target columns exactly as
    already built by build_stage2_panel.py (the real next-rebalancing-
    date price). Monthly/semi-annual recompute the target using a forward
    as-of daily-price lookup (stage2_utils.forward_price_asof) at
    rebal_date + 30d / + 182d respectively, with the same
    price_field_used per country as the existing panel (no field
    switching), and the 3m T-bill risk-free rate prorated by
    horizon_days/365 (the same /4-for-quarterly convention generalized).
  - Identical model specification (LASSO/RF/XGBoost, same fixed
    hyperparameters) reused via model_comparison.run_walk_forward with NO
    re-tuning per horizon -- any IC/AUC difference reflects the horizon,
    not a better-fit model.
  - All three horizons' results are written and printed unconditionally,
    regardless of which (if any) clear H2's bar (thesis Sec 1.5: IC>0.05
    and p<0.05) -- per thesis Sec 2.8 (Harvey, Liu & Zhu) applied to our
    own testing, not just cited against the literature.

Writes: data/processed/stage2_multi_horizon_robustness.csv (per-fold),
        data/processed/stage2_multi_horizon_robustness_summary.csv

Run directly: python3 src/stage2_signal/multi_horizon_robustness.py
"""

from __future__ import annotations

import logging

import pandas as pd
import yaml

from model_comparison import run_walk_forward, summarize
from stage2_utils import (
    REPO_ROOT,
    STAGE2_PANEL_PARQUET,
    best_price_series,
    forward_price_asof,
    load_params,
    load_raw_bond_daily,
)

logger = logging.getLogger("stage2_multi_horizon_robustness")


def load_horizon_params() -> dict:
    with open(REPO_ROOT / "configs" / "params.yaml") as f:
        return yaml.safe_load(f)["stage2_multi_horizon_robustness"]


def load_daily_price_by_country(country_names: list[str], price_field_priority: list[str]) -> dict:
    out = {}
    for name in country_names:
        raw = load_raw_bond_daily(name)
        if raw is None:
            continue
        price_daily, price_field = best_price_series(raw, price_field_priority)
        if price_field:
            out[name] = price_daily
    return out


def build_horizon_panel(base_panel: pd.DataFrame, horizon_days: int, tolerance_days: int,
                         daily_prices: dict) -> pd.DataFrame:
    """Same rows/features as base_panel; target columns recomputed for a
    forward window of `horizon_days` from each row's own rebal_date."""
    panel = base_panel.copy()
    target_period_end, excess_return, excess_return_binary, target_realized = [], [], [], []

    for _, row in panel.iterrows():
        daily = daily_prices.get(row["country_name"])
        p_t = row["price_t"]
        p_t1 = forward_price_asof(daily, row["rebal_date"], horizon_days, tolerance_days) if daily is not None else float("nan")
        total_return = (p_t1 / p_t - 1) if (pd.notna(p_t) and pd.notna(p_t1) and p_t != 0) else float("nan")
        rf_t = row["us_3m_tbill_yield_pct"]
        rf_period = (rf_t / 100 * (horizon_days / 365)) if pd.notna(rf_t) else float("nan")
        er = (total_return - rf_period) if (pd.notna(total_return) and pd.notna(rf_period)) else float("nan")

        target_period_end.append(row["rebal_date"] + pd.Timedelta(days=horizon_days))
        excess_return.append(er)
        excess_return_binary.append((er > 0) if pd.notna(er) else None)
        target_realized.append(pd.notna(er))

    panel["target_period_end"] = target_period_end
    panel["excess_return"] = excess_return
    panel["excess_return_binary"] = excess_return_binary
    panel["target_realized"] = target_realized
    return panel


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    params = load_params()
    horizon_params = load_horizon_params()
    model_features = params["model_features"]

    base_panel = pd.read_parquet(STAGE2_PANEL_PARQUET)
    countries = sorted(base_panel["country_name"].unique())
    daily_prices = load_daily_price_by_country(countries, params["price_field_priority"])

    horizons_days = horizon_params["horizons_days"]
    tolerance_days = horizon_params["forward_asof_tolerance_days"]

    all_folds = []
    all_summaries = []
    for horizon_name, horizon_days in horizons_days.items():
        if horizon_name == "quarterly":
            panel_h = base_panel  # reuse existing target as-is, not recomputed
        else:
            panel_h = build_horizon_panel(base_panel, horizon_days, tolerance_days, daily_prices)

        logger.info("Horizon=%s (%dd): %d target-realized rows / %d total",
                    horizon_name, horizon_days, panel_h["target_realized"].sum(), len(panel_h))

        cls_folds, cls_preds = run_walk_forward(panel_h, model_features, params, "classification")
        reg_folds, _ = run_walk_forward(panel_h, model_features, params, "regression")
        cls_folds["horizon"] = horizon_name
        reg_folds["horizon"] = horizon_name

        cls_summary = summarize(cls_folds.drop(columns=["horizon"]), cls_preds, "classification")
        reg_summary = summarize(reg_folds.drop(columns=["horizon"]), {}, "regression")
        cls_summary["horizon"] = horizon_name
        reg_summary["horizon"] = horizon_name

        all_folds.append(cls_folds)
        all_folds.append(reg_folds)
        all_summaries.append(cls_summary)
        all_summaries.append(reg_summary)

    folds_df = pd.concat(all_folds, ignore_index=True)
    summary_df = pd.concat(all_summaries, ignore_index=True)

    output_dir = REPO_ROOT / horizon_params["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    folds_df.to_csv(output_dir / "stage2_multi_horizon_robustness.csv", index=False)
    summary_df.to_csv(output_dir / "stage2_multi_horizon_robustness_summary.csv", index=False)

    print("\n=== H2 multi-horizon robustness check -- ALL THREE reported unconditionally ===")
    cols = ["horizon", "framing", "model", "n_folds", "n_pooled_obs", "auc",
            "mean_ic", "ic_t_stat", "ic_one_sided_p"]
    present_cols = [c for c in cols if c in summary_df.columns]
    print(summary_df[present_cols].to_string(index=False))

    print("\n=== H2 bar check (IC > 0.05 AND one-sided p < 0.05) -- regression framing only ===")
    reg = summary_df[summary_df["framing"] == "regression"]
    for _, r in reg.iterrows():
        clears = (r["mean_ic"] > 0.05) and (r["ic_one_sided_p"] < 0.05)
        print(f"  horizon={r['horizon']:12s} model={r['model']:15s} mean_ic={r['mean_ic']:+.4f} "
              f"p={r['ic_one_sided_p']:.4f}  clears_H2_bar={clears}")


if __name__ == "__main__":
    main()
