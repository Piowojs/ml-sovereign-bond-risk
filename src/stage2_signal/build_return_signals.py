"""Stage 2 output (thesis Sec 4.3.5) -- the walk-forward-safe, point-in-time-
correct production pipeline. At every rebalancing date, refits the models
chosen by model_comparison.py (configs/params.yaml:
stage2_signal.chosen_model_classification/chosen_model_regression, both
"lasso" -- see CLAUDE.md "Stage 2 signal" for why LASSO won both framings)
using only rows whose target is already realized as of that date
(stage2_utils.build_expanding_train_mask), then scores that date's EM
satellite-candidate cross-section: a continuous predicted excess-return
score (the "expected excess return signal" thesis Sec 4.3.5 asks for) and a
classification probability of positive excess return, both used to rank
sovereigns and flag top-N membership for every N in
configs/params.yaml: stage2_signal.top_n_options (5/10/15 -- built for all
three sensitivity levels, not one hardcoded choice).

This is deliberately the *separate* production pipeline from
model_comparison.py's diagnostic, same split as Stage 1's build_risk_labels.py
vs algorithm_comparison.py -- see stage2_utils.py's module docstring for the
leakage-prevention principle (build_expanding_train_mask) both scripts share.

Writes: data/processed/stage2_return_signals.parquet

Run directly: python3 src/stage2_signal/build_return_signals.py
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from stage2_utils import (
    REPO_ROOT,
    STAGE2_PANEL_PARQUET,
    build_expanding_train_mask,
    fit_impute_scale,
    load_params,
    make_models,
    sufficiently_observed_mask,
    transform_apply,
)

logger = logging.getLogger("stage2_build_return_signals")


def score_panel(panel: pd.DataFrame, model_features: list[str], params: dict) -> pd.DataFrame:
    """Pure function: no file I/O. Given the full Stage 2 panel, produces
    one output row per input row with walk-forward-safe predicted scores.
    Exposed standalone (rather than only reachable via main()) specifically
    so test_lag_rules.py can call it on a truncated copy of the panel and
    assert truncation invariance -- the direct leakage check for this
    stage, mirroring Stage 1's build_risk_labels.label_panel."""
    models = make_models(params, params["random_state"])
    cls_name = params["chosen_model_classification"]
    reg_name = params["chosen_model_regression"]
    min_frac = params["min_observed_feature_frac"]
    min_rows = params["min_training_rows"]

    out_frames = []
    for date in sorted(panel["rebal_date"].unique()):
        apply_df = panel[panel["rebal_date"] == date].copy()
        train_mask = build_expanding_train_mask(panel, date) & panel["target_realized"]
        train_df = panel[train_mask]
        train_df = train_df[sufficiently_observed_mask(train_df, model_features, min_frac)]

        out = apply_df[["country_code", "country_name", "dm_em_flag", "rebal_date",
                         "target_period_end", "excess_return", "excess_return_binary",
                         "target_realized"]].copy()
        out["training_window_n_rows"] = len(train_df)
        # The Stage-2-specific leakage guard, recorded per row so
        # test_lag_rules.py can assert it structurally without re-running
        # the model: the latest target_period_end among the rows actually
        # used to train the model that scored this row must never exceed
        # this row's own rebal_date (see stage2_utils.build_expanding_
        # train_mask's docstring).
        out["training_window_max_target_period_end"] = (
            train_df["target_period_end"].max() if len(train_df) else pd.NaT
        )
        out["n_features_observed"] = apply_df[model_features].notna().sum(axis=1).values

        apply_sufficient = sufficiently_observed_mask(apply_df, model_features, min_frac)
        can_fit = len(train_df) >= min_rows
        has_two_classes = can_fit and train_df["excess_return_binary"].astype(object).nunique() >= 2

        out["predicted_excess_return"] = np.nan
        out["predicted_prob_positive"] = np.nan
        out["signal_status"] = "insufficient_data"

        if can_fit:
            fittable = apply_df[apply_sufficient]
            if len(fittable):
                imputer, scaler, X_train = fit_impute_scale(train_df, model_features)
                X_apply = transform_apply(imputer, scaler, fittable, model_features)

                reg_model = models["regression"][reg_name]
                reg_model.fit(X_train, train_df["excess_return"])
                reg_pred = reg_model.predict(X_apply)
                out.loc[fittable.index, "predicted_excess_return"] = reg_pred
                out.loc[fittable.index, "signal_status"] = "scored"

                if has_two_classes:
                    cls_model = models["classification"][cls_name]
                    cls_model.fit(X_train, train_df["excess_return_binary"].astype(int))
                    cls_pred = cls_model.predict_proba(X_apply)[:, 1]
                    out.loc[fittable.index, "predicted_prob_positive"] = cls_pred

        out_frames.append(out)

    scored = pd.concat(out_frames, ignore_index=True)

    top_n_options = params["top_n_options"]
    scored["rank_within_date"] = (
        scored.groupby("rebal_date")["predicted_excess_return"].rank(ascending=False, method="first")
    )
    scored["n_scored_within_date"] = scored.groupby("rebal_date")["predicted_excess_return"].transform(
        lambda s: s.notna().sum()
    )
    for n in top_n_options:
        scored[f"top_{n}"] = scored["predicted_excess_return"].notna() & (scored["rank_within_date"] <= n)

    return scored


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    params = load_params()
    panel = pd.read_parquet(STAGE2_PANEL_PARQUET)
    model_features = params["model_features"]

    logger.info(
        "Building walk-forward Stage 2 return signals: classification=%s regression=%s "
        "(%d rows, %d quarters)",
        params["chosen_model_classification"], params["chosen_model_regression"],
        len(panel), panel["rebal_date"].nunique(),
    )

    scored = score_panel(panel, model_features, params)

    output_dir = REPO_ROOT / params["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "stage2_return_signals.parquet"
    scored.to_parquet(out_path, index=False)
    logger.info("Wrote %d rows to %s", len(scored), out_path)

    print("\n=== Stage 2 signal status counts ===")
    print(scored["signal_status"].value_counts())
    print(f"\nQuarters with >=1 scored row: {scored[scored['signal_status']=='scored']['rebal_date'].nunique()} "
          f"/ {scored['rebal_date'].nunique()}")

    for n in params["top_n_options"]:
        col = f"top_{n}"
        print(f"\n=== top_{n} selection counts (latest scored quarter) ===")
        latest_scored = scored[scored["signal_status"] == "scored"]
        if latest_scored.empty:
            print("  (no scored rows)")
            continue
        latest_date = latest_scored["rebal_date"].max()
        latest = scored[scored["rebal_date"] == latest_date]
        print(f"  quarter={latest_date.date()}  n_scored={latest['signal_status'].eq('scored').sum()}  "
              f"n_selected={latest[col].sum()}")
        print(latest.loc[latest[col], ["country_name", "predicted_excess_return", "predicted_prob_positive"]]
              .sort_values("predicted_excess_return", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
