"""Stage 2 model selection (thesis Sec 4.3.3), diagnostic -- compares
LASSO/Random Forest/XGBoost, both classification framing (AUC) and
regression framing (Information Coefficient), via true walk-forward
out-of-sample evaluation.

This is the Stage 2 analogue of Stage 1's algorithm_comparison.py, but
NOT full-sample-pooled the way that script is: because the Stage 2 target
is itself a forward (t, t+1] return, a naive full-sample fit would let a
model see 2020's realized returns while "predicting" 2010 -- an even more
direct leak than Stage 1's pooled-fit diagnostic. So this already walks
forward (refit at every rebalancing date on stage2_utils.build_expanding_
train_mask's target-realized-only training set) and evaluates out-of-
sample predictions pooled across all folds -- consistent with H2's test
design (thesis Sec 1.5): IC computed per fold (rebalancing date), then a
one-sided t-test of mean IC > 0 across folds; AUC computed on the pooled
out-of-sample classification predictions.

Small-sample caveat (see CLAUDE.md "Stage 2 signal"): Stage 1's EM
satellite-candidate tier only has rows in 65 of 84 quarters, median 4 /
mean 8.5 countries per quarter -- so this is a small-N walk-forward
evaluation by construction, not a large backtest. Fold counts and n per
fold are reported explicitly rather than only a headline metric, so this
isn't overstated.

Writes: data/processed/stage2_model_comparison.csv (per-fold metrics),
        data/processed/stage2_model_comparison_summary.csv (per-model summary)

Run directly: python3 src/stage2_signal/model_comparison.py
"""

from __future__ import annotations

import logging
from copy import deepcopy

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from stage2_utils import (
    REPO_ROOT,
    STAGE2_PANEL_PARQUET,
    build_expanding_train_mask,
    fit_impute_scale,
    ic_one_sided_ttest,
    information_coefficient,
    load_params,
    make_models,
    sufficiently_observed_mask,
    transform_apply,
)

logger = logging.getLogger("stage2_model_comparison")


def run_walk_forward(panel: pd.DataFrame, model_features: list[str], params: dict, framing: str):
    models = make_models(params, params["random_state"])[framing]
    dates = sorted(panel["rebal_date"].unique())
    min_frac = params["min_observed_feature_frac"]
    min_rows = params["min_training_rows"]

    fold_rows = []
    pooled_preds = {name: {"y_true": [], "y_pred": []} for name in models}

    for date in dates:
        train_mask = build_expanding_train_mask(panel, date) & panel["target_realized"]
        train_df = panel[train_mask]
        train_df = train_df[sufficiently_observed_mask(train_df, model_features, min_frac)]
        if len(train_df) < min_rows:
            continue

        test_df = panel[(panel["rebal_date"] == date) & panel["target_realized"]]
        test_df = test_df[sufficiently_observed_mask(test_df, model_features, min_frac)]
        if test_df.empty:
            continue

        if framing == "classification":
            y_train = train_df["excess_return_binary"].astype(int)
            y_test = test_df["excess_return_binary"].astype(int)
            if y_train.nunique() < 2:
                continue
        else:
            y_train = train_df["excess_return"]
            y_test = test_df["excess_return"]

        imputer, scaler, X_train = fit_impute_scale(train_df, model_features)
        X_test = transform_apply(imputer, scaler, test_df, model_features)

        for name, base_model in models.items():
            model = deepcopy(base_model)
            model.fit(X_train, y_train)
            if framing == "classification":
                y_pred = model.predict_proba(X_test)[:, 1]
                pooled_preds[name]["y_true"].extend(y_test.tolist())
                pooled_preds[name]["y_pred"].extend(y_pred.tolist())
                fold_rows.append({
                    "framing": framing, "model": name, "rebal_date": date,
                    "n_train": len(train_df), "n_test": len(test_df),
                })
            else:
                y_pred = model.predict(X_test)
                ic = information_coefficient(y_pred, y_test.values)
                fold_rows.append({
                    "framing": framing, "model": name, "rebal_date": date,
                    "n_train": len(train_df), "n_test": len(test_df), "ic": ic,
                })

    return pd.DataFrame(fold_rows), pooled_preds


def summarize(fold_df: pd.DataFrame, pooled_preds: dict, framing: str) -> pd.DataFrame:
    summaries = []
    for name in fold_df["model"].unique() if not fold_df.empty else []:
        sub = fold_df[fold_df["model"] == name]
        if framing == "classification":
            yt, yp = pooled_preds[name]["y_true"], pooled_preds[name]["y_pred"]
            auc = roc_auc_score(yt, yp) if len(set(yt)) > 1 else float("nan")
            summaries.append({
                "framing": framing, "model": name, "n_folds": sub["rebal_date"].nunique(),
                "n_pooled_obs": len(yt), "auc": auc,
            })
        else:
            fold_ics = sub["ic"].tolist()
            t_stat, p_value = ic_one_sided_ttest(fold_ics)
            summaries.append({
                "framing": framing, "model": name, "n_folds": len(fold_ics),
                "mean_ic": float(np.nanmean(fold_ics)) if fold_ics else float("nan"),
                "ic_t_stat": t_stat, "ic_one_sided_p": p_value,
            })
    return pd.DataFrame(summaries)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    params = load_params()
    panel = pd.read_parquet(STAGE2_PANEL_PARQUET)
    model_features = params["model_features"]

    logger.info("Running walk-forward model comparison: %d rows, %d quarters",
                len(panel), panel["rebal_date"].nunique())

    cls_folds, cls_preds = run_walk_forward(panel, model_features, params, "classification")
    reg_folds, _ = run_walk_forward(panel, model_features, params, "regression")

    cls_summary = summarize(cls_folds, cls_preds, "classification")
    reg_summary = summarize(reg_folds, {}, "regression")
    summary = pd.concat([cls_summary, reg_summary], ignore_index=True)

    output_dir = REPO_ROOT / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    all_folds = pd.concat([cls_folds, reg_folds], ignore_index=True)
    all_folds.to_csv(output_dir / "stage2_model_comparison.csv", index=False)
    summary.to_csv(output_dir / "stage2_model_comparison_summary.csv", index=False)

    print("\n=== Stage 2 model comparison summary ===")
    print(summary.to_string(index=False))
    print(
        f"\nClassification folds evaluated: {cls_folds['rebal_date'].nunique() if not cls_folds.empty else 0} "
        f"/ {panel['rebal_date'].nunique()} quarters"
    )
    print(
        f"Regression folds evaluated: {reg_folds['rebal_date'].nunique() if not reg_folds.empty else 0} "
        f"/ {panel['rebal_date'].nunique()} quarters"
    )


if __name__ == "__main__":
    main()
