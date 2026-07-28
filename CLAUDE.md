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
- `notebooks/` is empty. `configs/` now has two files (see "Macro data
  acquisition" below for how they got created):
  - `configs/universe.yaml` — the single source of truth for the 44-country
    sovereign universe (name, ISO2/ISO3, DM/EM classification, Refinitiv
    RICs, and the excluded-country list with reasons). Any script needing
    the country list should read this rather than hardcoding a second copy.
    Note `eikon_sovereign_pull.py`'s own `UNIVERSE` dict (53 countries, no
    exclusion filtering) predates this file and should be reconciled with
    it when that script is eventually rewritten against `lseg-data`.
  - `configs/params.yaml` — the central hyperparameter file. Currently has
    one section, `macro_acquisition` (date range, per-source publication
    lag, coverage threshold). Add new sections here as later stages need
    tunable parameters — never hardcode a hyperparameter in code.
- `test_lag_rules.py` now has real bias-prevention assertions (previously a
  placeholder) — it checks that every row in `data/raw/macro/macro_fundamentals.csv`
  has `available_date` correctly offset from `period_date` by the
  configured publication lag for its source. Extend it with walk-forward /
  feature-construction checks as those are built.
- `src/data_acquisition/eikon_sovereign_pull.py` is a **legacy/inconsistent**
  script: it imports and drives the old `eikon` package, but the settled
  decision (see below, and `requirements.txt`) is to use `lseg-data` instead
  — `eikon` is incompatible with the current Refinitiv Workspace setup. Don't
  treat this file as the current data-pull approach without checking with the
  user first; it likely needs a rewrite against `lseg-data` rather than reuse.
- `src/data_acquisition/macro_pull.py` pulls World Bank / IMF WEO / FRED
  macro data — see "Macro data acquisition" below for full details.
- `data/raw/` has pulled data for `bonds/`, `ratings/`, `macro/`, and an
  empty `cds/` (CDS pull did not succeed / was not run). `data/logs/pull_log.txt`
  / `missing.txt` (Refinitiv) and `macro_pull_log.txt` / `macro_missing.txt`
  (macro) document exactly what succeeded and what's missing from each pull.

## Commands
No build, lint, or test tooling is configured yet (no pytest config, no
linter config, no packaging file). What exists today:
- Install dependencies: `pip install -r requirements.txt`
- Run the (legacy, see above) data pull: `python src/data_acquisition/eikon_sovereign_pull.py`
  — requires the Eikon desktop app open and logged in on the same machine.
- Run the macro data pull: `python src/data_acquisition/macro_pull.py`
  (`--refresh` to bypass the cache and re-fetch everything). No API keys or
  desktop apps required — World Bank, IMF DataMapper, and FRED's CSV
  endpoint are all key-free public APIs.
- Run `test_lag_rules.py` after any change touching data loading, feature
  construction, clustering inputs, or backtesting logic —
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

## Macro data acquisition (World Bank / IMF WEO / FRED — settled facts)
`src/data_acquisition/macro_pull.py` pulls all macro/fundamental and
global-macro features for the 44-country universe in `configs/universe.yaml`,
writing to `data/raw/macro/macro_fundamentals.csv` (tidy long format:
`country, series, period_date, available_date, value, source`) and
`data/raw/macro/coverage_report.csv`. Raw API responses are cached under
`data/raw/macro/_cache/` so re-runs don't re-hit the APIs.

- **No API keys needed anywhere.** World Bank's REST API, the IMF
  DataMapper API, and FRED's public CSV endpoint
  (`https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}`) are all
  key-free. Don't add `fredapi`/`.env`/API-key plumbing for this — it was
  considered and dropped once the key-free endpoints were confirmed working.
- **World Bank primary series** (`https://api.worldbank.org/v2/country/{iso2}/indicator/{code}`):
  `GC.DOD.TOTL.GD.ZS` (debt/GDP), `GC.BAL.CASH.GD.ZS` (fiscal balance/GDP),
  `BN.CAB.XOKA.GD.ZS` (current account/GDP), `FI.RES.TOTL.MO` (FX reserves,
  months of imports), `FP.CPI.TOTL.ZG` (CPI inflation YoY),
  `NY.GDP.MKTP.KD.ZG` (real GDP growth YoY). Political stability is a
  separate case: it lives in the WGI database, not the default WDI one —
  needs `source=3` **and** indicator ID `GOV_WGI_PV.EST` (the plain `PV.EST`
  ID 404s under `source=3`).
- **IMF WEO fallback** via the IMF DataMapper API
  (`https://www.imf.org/external/datamapper/api/v1/{indicator}`, no key):
  `GGXWDG_NGDP` (debt/GDP), `GGXCNL_NGDP` (fiscal balance/GDP), `BCA_NGDPD`
  (current account/GDP), `PCPIPCH` (CPI inflation), `NGDP_RPCH` (real GDP
  growth). Applied per country-year cell (fills only where World Bank has no
  value) — the `source` column on each row records which one actually
  supplied it. No IMF WEO equivalent exists for FX reserves or political
  stability, so those two are World-Bank-only. **The DataMapper API's
  per-country path filter is ignored server-side** — it always returns the
  full payload for an indicator, so the script fetches once per indicator
  and filters client-side to our 44 ISO3 codes.
- **FRED global series** (tagged `country="United States"` for the two
  yields, `country="GLOBAL"` for VIX/DXY): `DGS10`, `DGS2`, `VIXCLS`, and
  `DTWEXBGS` (Trade-Weighted U.S. Dollar Index: Broad) as a **documented
  proxy for DXY** — FRED has no real ICE DXY series (it's proprietary).
  `DTWEXBGS` only starts 2006-01-02, so **2005 has no USD-index observation
  for the whole year**; this is correctly flagged in `macro_missing.txt`
  and shows as 0 rows for that year, not silently absent.
- **Publication lag**: annual World Bank/IMF series get
  `available_date = period_end_date (Dec 31) + lag_months` (default 6,
  `configs/params.yaml: macro_acquisition.lag_months_world_bank` /
  `lag_months_imf_weo`); FRED daily series get `available_date = period_date
  + lag_days_fred` (default 1 day). `test_lag_rules.py` asserts this holds
  for every row.
- **Coverage as of the last full run**: 0/312 (country × series) cells below
  the 50% threshold — see `data/raw/macro/coverage_report.csv` for exact
  percentages. One notable case: World Bank's `GC.DOD.TOTL.GD.ZS` (central
  government debt/GDP) is **entirely null for Poland** across 2005–2025, not
  just partially sparse — that country/series is 100% IMF WEO fallback.
- **Two known, accepted limitations** (not fixable within this script —
  flagged here so they're discovered from docs, not later):
  - *Vintage/revision data*: World Bank and IMF WEO APIs serve current,
    revised figures, not the value as it stood on the original publication
    date. `available_date` correctly models when a value first became
    knowable, but not that debt/GDP and fiscal balance figures (especially
    EM, post-crisis) are sometimes materially restated later. This is a
    structural limitation of free data sources.
  - *Consolidation-level mismatch in fallback pairs*: the WB→IMF fallback
    for debt/GDP (`GC.DOD.TOTL.GD.ZS` → `GGXWDG_NGDP`) and fiscal balance
    (`GC.BAL.CASH.GD.ZS` → `GGXCNL_NGDP`) mixes a *central government*
    measure with a broader *general government* (incl. subnational) one —
    for countries with meaningful subnational debt, a mid-series fallback
    could show an artificial level shift unrelated to actual credit change.
    The `source` column makes every such row traceable. (Current account's
    fallback pair — `BN.CAB.XOKA.GD.ZS` / `BCA_NGDPD` — doesn't have this
    issue; both are external-sector measures.)
- **Transient API flakiness**: World Bank's API occasionally times out or
  returns spurious 400s under rapid sequential requests (~300 calls across
  44 countries × 7 series) — confirmed transient by manual retry, not real
  gaps. `macro_pull.py` retries each request up to 3x with backoff before
  giving up and logging a genuine miss.

## Bias-prevention rules (the thesis's core methodological concern)
- Run `test_lag_rules.py` after any change touching data loading, feature
  construction, clustering inputs, or backtesting logic.
- Macro data (World Bank / IMF / FRED): only use data published *before* the
  rebalancing date. IMF/World Bank publication lags are typically 3–6 months
  and must be explicitly respected, not assumed away. Note the accepted
  vintage/revision-data caveat in "Macro data acquisition" above: this
  controls *when* a value first became usable, not whether later data
  revisions could differ from what was actually published at the time.
- Walk-forward design: no data from a test window may enter any training
  computation (fitting, normalization stats, feature selection).
- Normalization must use expanding-window statistics computed on the
  training window only.

## Conventions
- Python throughout.
- All hyperparameters live in `configs/params.yaml`.
- SHAP is used for Stage 2 model interpretability.
- HRP (Hierarchical Risk Parity) is the Stage 3 allocation method.
