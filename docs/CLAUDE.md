# Sovereign Bond ML Portfolio — Master's Thesis Codebase

## What this is
ML-driven sovereign bond risk classification and portfolio construction.
Four-stage pipeline: (1) unsupervised clustering of sovereign risk, (2)
supervised return prediction for EM bonds (LASSO/RF/XGBoost), (3) HRP
portfolio construction, (4) benchmark comparison and evaluation.
Universe: ~44 DM/EM sovereigns, 2005–2025.

Full thesis outline (chapters, methodology, hypotheses): @docs/thesis_outline_sovereign.md
Consult it when naming outputs, writing docstrings, or checking that code
maps to the right thesis section.

## Repo structure — pipeline isomorphism
Folder layout mirrors the thesis chapters/stages 1:1. Key rules:
- `src/` organized by stage, matching thesis section numbers
- `configs/params.yaml` centralizes ALL hyperparameters — never hardcode
  a hyperparameter in code; this file supports the sensitivity analysis
- `data/raw/` is READ-ONLY. Never write to it, never modify files in it.
- Output files are named by thesis section (e.g. `fig_5_1_cluster_map.png`)
- `test_lag_rules.py` is a priority file — see bias-prevention rules below

## Data acquisition status (settled facts — do not re-derive)
- Use `lseg-data`, NOT `eikon` — `eikon` is incompatible with Refinitiv
  Workspace
- App key must be generated via "EDP API," not "Eikon Data API"
- Bond data pulled via `XX10YT=RR` benchmark RICs
- DM countries return rich field sets; EM countries typically return only
  `MID_PRICE` and `BMK_SPD` — column-renaming logic must be adaptive,
  never hardcoded, or it breaks silently on EM tickers
- `YLDTOMAT` (yield to maturity) is licence-blocked for all non-US
  countries — source YTM from IMF WEO / World Bank instead
- CDS is not available as a standalone series; `INT_CDS` is only
  accessible on DM benchmark RICs
- `TR.IssuerRating` returns only a current snapshot, not a historical
  series — ratings history is pulled directly from S&P/Moody's/Fitch
  websites
- Universe exclusions (structural licence constraints, not bugs):
  Russia (permissions block); Argentina, Ecuador, Panama, Dominican
  Republic, Qatar, Saudi Arabia, UAE, Ukraine (no benchmark RICs)
- EM data sparsity is a structural constraint of the university licence,
  not a script error — thesis sections 1.4, 3.2, 3.3, 3.4, 4.2.1, 6.6,
  and Appendix B need to reflect this framing

## Bias-prevention rules (the thesis's core methodological concern)
- Run `test_lag_rules.py` after any change touching data loading,
  feature construction, clustering inputs, or backtesting logic
- Macro data (World Bank / IMF / FRED): only use data published *before*
  the rebalancing date. IMF/World Bank publication lags are typically
  3–6 months and must be explicitly respected, not assumed away
- Walk-forward design: no data from a test window may enter any
  training computation (fitting, normalization stats, feature selection)
- Normalization must use expanding-window statistics computed on the
  training window only

## Conventions
- Python throughout
- All hyperparameters live in `configs/params.yaml`
- SHAP is used for Stage 2 model interpretability
- HRP (Hierarchical Risk Parity) is the Stage 3 allocation method
