# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is
ML-driven sovereign bond risk classification and portfolio construction — a
master's thesis codebase. Four-stage pipeline: (1) unsupervised clustering of
sovereign risk, (2) supervised return prediction for EM bonds (LASSO/RF/XGBoost),
(3) HRP portfolio construction, (4) benchmark comparison and evaluation.
Universe: ~44 DM/EM sovereigns, 2005–2025 (originally scoped as 2005–2023).

Full thesis outline (chapters, methodology, hypotheses, exact data sources per
chapter): @docs/thesis_outline_sovereign.md — consult it when naming outputs,
writing docstrings, or checking that code maps to the right thesis section.

## Current state of the repo
This is an early-stage scaffold, not a working pipeline yet:
- `src/stage1_clustering/`, `stage2_signal/`, `stage3_portfolio/`,
  `stage4_evaluation/` are all empty — nothing has been implemented past data
  acquisition.
- `configs/` and `notebooks/` are empty. `configs/params.yaml` (the central
  hyperparameter file described below) does not exist yet — create it before
  or alongside the first stage that needs a tunable parameter.
- `test_lag_rules.py` (the bias-prevention test referenced below) does not
  exist yet. Treat creating it as a priority once any lag-sensitive logic
  (macro joins, walk-forward folds) is written.
- `src/data_acquisition/eikon_sovereign_pull.py` is a **legacy/inconsistent**
  script: it imports and drives the old `eikon` package, but the settled
  decision (see below, and `requirements.txt`) is to use `lseg-data` instead
  — `eikon` is incompatible with the current Refinitiv Workspace setup. Don't
  treat this file as the current data-pull approach without checking with the
  user first; it likely needs a rewrite against `lseg-data` rather than reuse.
- `data/raw/` already has pulled data for `bonds/`, `ratings/`, and an empty
  `cds/` (CDS pull did not succeed / was not run). `data/logs/pull_log.txt`
  and `missing.txt` document exactly what succeeded and what's missing from
  that earlier pull.

## Commands
No build, lint, or test tooling is configured yet (no pytest config, no
linter config, no packaging file). What exists today:
- Install dependencies: `pip install -r requirements.txt`
- Run the (legacy, see above) data pull: `python src/data_acquisition/eikon_sovereign_pull.py`
  — requires the Eikon desktop app open and logged in on the same machine.
- Once `test_lag_rules.py` exists, run it after any change touching data
  loading, feature construction, clustering inputs, or backtesting logic —
  this is the project's core correctness check (see Bias-prevention rules).

## Repo structure — pipeline isomorphism
Folder layout mirrors the thesis chapters/stages 1:1. Key rules:
- `src/` is organized by stage, matching thesis section numbers (Stage 1 =
  §4.2, Stage 2 = §4.3, Stage 3 = §4.4, Stage 4 = §4.5 in the thesis outline).
- `configs/params.yaml` is meant to centralize ALL hyperparameters — never
  hardcode a hyperparameter in code; this file is what supports the
  sensitivity analysis in thesis §5.5.
- `data/raw/` is READ-ONLY. Never write to it, never modify files in it.
- Output files should be named by thesis section (e.g. `fig_5_1_cluster_map.png`).

## Data acquisition status (settled facts — do not re-derive)
- Use `lseg-data`, NOT `eikon` — `eikon` is incompatible with Refinitiv
  Workspace. (See "Current state" above: the one existing pull script still
  uses `eikon` and needs to be reconciled with this decision.)
- App key must be generated via "EDP API," not "Eikon Data API".
- Bond data pulled via `XX10YT=RR` benchmark RICs.
- DM countries return rich field sets; EM countries typically return only
  `MID_PRICE` and `BMK_SPD` — column-renaming logic must be adaptive, never
  hardcoded, or it breaks silently on EM tickers.
- `YLDTOMAT` (yield to maturity) is licence-blocked for all non-US
  countries — source YTM from IMF WEO / World Bank instead.
- CDS is not available as a standalone series; `INT_CDS` is only accessible
  on DM benchmark RICs.
- `TR.IssuerRating` returns only a current snapshot, not a historical
  series — ratings history is pulled directly from S&P/Moody's/Fitch
  websites.
- Universe exclusions (structural licence constraints, not bugs): Russia
  (permissions block); Argentina, Ecuador, Panama, Dominican Republic, Qatar,
  Saudi Arabia, UAE, Ukraine (no benchmark RICs). Note this contradicts the
  older `UNIVERSE` dict in `eikon_sovereign_pull.py`, which still includes
  several of these — that dict predates the exclusion decision.
- EM data sparsity is a structural constraint of the university licence, not
  a script error — thesis sections 1.4, 3.2, 3.3, 3.4, 4.2.1, 6.6, and
  Appendix B need to reflect this framing.

## Bias-prevention rules (the thesis's core methodological concern)
- Run `test_lag_rules.py` after any change touching data loading, feature
  construction, clustering inputs, or backtesting logic.
- Macro data (World Bank / IMF / FRED): only use data published *before* the
  rebalancing date. IMF/World Bank publication lags are typically 3–6 months
  and must be explicitly respected, not assumed away.
- Walk-forward design: no data from a test window may enter any training
  computation (fitting, normalization stats, feature selection).
- Normalization must use expanding-window statistics computed on the
  training window only.

## Conventions
- Python throughout.
- All hyperparameters live in `configs/params.yaml`.
- SHAP is used for Stage 2 model interpretability.
- HRP (Hierarchical Risk Parity) is the Stage 3 allocation method.
