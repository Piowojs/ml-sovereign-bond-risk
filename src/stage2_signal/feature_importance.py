"""Stage 2 feature importance (thesis Sec 4.3.4) -- SHAP values for the
model that performed best in model_comparison.py's walk-forward evaluation
(configs/params.yaml: stage2_signal.chosen_model_regression, "lasso" --
LASSO won both the classification-AUC and regression-IC framings; see
CLAUDE.md "Stage 2 signal"). Answers the interpretive question thesis
Sec 6.2 depends on: do fundamental macro factors or market-based signals
dominate the EM excess-return prediction?

Deliberately a full-sample diagnostic fit (all target-realized rows with
sufficient feature coverage), not a per-rebalancing-date walk-forward
refit -- same "diagnostic vs production" distinction Stage 1 draws between
algorithm_comparison.py (full-sample, descriptive only) and
build_risk_labels.py (walk-forward, production). SHAP importance here
describes what the model learned in aggregate; it is not itself a live
trading signal (that's build_return_signals.py's job) and is never fed to
Stage 3/4.

Writes: data/processed/stage2_shap_importance.csv

Run directly: python3 src/stage2_signal/feature_importance.py
"""

from __future__ import annotations

import logging

import pandas as pd
import shap

from stage2_utils import (
    REPO_ROOT,
    STAGE2_PANEL_PARQUET,
    fit_impute_scale,
    load_params,
    make_models,
    sufficiently_observed_mask,
)

logger = logging.getLogger("stage2_feature_importance")

FEATURE_GROUPS = {
    "yield_spread_bps": "market",
    "mom_1m": "market",
    "mom_3m": "market",
    "mom_12m": "market",
    "carry": "market",
    "spread_zscore_52w": "market",
    "debt_gdp": "macro_fundamental",
    "fiscal_bal_gdp": "macro_fundamental",
    "cpi_inflation": "macro_fundamental",
    "real_gdp_growth": "macro_fundamental",
    "us_10y": "global_factor",
    "curve_slope": "global_factor",
    "vix": "global_factor",
    "dxy_proxy": "global_factor",
}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    params = load_params()
    panel = pd.read_parquet(STAGE2_PANEL_PARQUET)
    model_features = params["model_features"]
    min_frac = params["min_observed_feature_frac"]

    realized = panel[panel["target_realized"]]
    realized = realized[sufficiently_observed_mask(realized, model_features, min_frac)]
    logger.info("Fitting %s on %d full-sample rows for SHAP", params["chosen_model_regression"], len(realized))

    imputer, scaler, X = fit_impute_scale(realized, model_features)
    y = realized["excess_return"]

    model_name = params["chosen_model_regression"]
    model = make_models(params, params["random_state"])["regression"][model_name]
    model.fit(X, y)

    masker = shap.maskers.Independent(X, max_samples=len(X))
    explainer = shap.LinearExplainer(model, masker) if model_name in ("lasso",) else shap.Explainer(model, X)
    shap_values = explainer(X)

    importance = pd.DataFrame({
        "feature": model_features,
        "mean_abs_shap": abs(shap_values.values).mean(axis=0),
        "lasso_coef": model.coef_ if hasattr(model, "coef_") else float("nan"),
    }).sort_values("mean_abs_shap", ascending=False)
    importance["group"] = importance["feature"].map(FEATURE_GROUPS)

    output_dir = REPO_ROOT / params["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "stage2_shap_importance.csv"
    importance.to_csv(out_path, index=False)
    logger.info("Wrote %s", out_path)

    print("\n=== Stage 2 SHAP feature importance (model=%s, n=%d) ===" % (model_name, len(realized)))
    print(importance.to_string(index=False))

    group_totals = importance.groupby("group")["mean_abs_shap"].sum().sort_values(ascending=False)
    print("\n=== Total |SHAP| by feature group ===")
    print(group_totals.to_string())
    print(
        f"\nDominant group: {group_totals.index[0]} "
        f"({group_totals.iloc[0] / group_totals.sum():.1%} of total |SHAP|)"
    )
    print(
        "\nCaveat (see CLAUDE.md 'Stage 2 signal'): market-based features are 49-64% missing "
        "within the EM satellite-candidate population (vs 0% for the 4 macro fundamentals), so "
        "their zero SHAP contribution here is plausibly a data-richness artifact of this "
        "university-licence pull, not proof that market signals carry no genuine information -- "
        "flagged, not asserted as a clean result."
    )


if __name__ == "__main__":
    main()
