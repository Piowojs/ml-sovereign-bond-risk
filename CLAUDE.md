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
- `src/stage1_clustering/build_feature_matrix.py` builds the country x
  quarter feature matrix consumed by (not-yet-built) Stage 1 clustering —
  see "Stage 1 feature matrix" below for full details. `stage2_signal/`,
  `stage3_portfolio/`, `stage4_evaluation/` are still empty.
- `notebooks/` is empty. `configs/` now has two files (see "Macro data
  acquisition" below for how they got created):
  - `configs/universe.yaml` — the single source of truth for the 44-country
    sovereign universe (name, ISO2/ISO3, DM/EM classification, Refinitiv
    RICs, and the excluded-country list with reasons). Any script needing
    the country list should read this rather than hardcoding a second copy.
    Note `eikon_sovereign_pull_deprecated.py`'s own `UNIVERSE` dict (53
    countries, no exclusion filtering) predates this file; that script is
    dead (see below) and was never reconciled with it — a non-issue now
    since `bond_data_pull_reconstructed.py`'s `UNIVERSE` already matches
    the 44-country exclusion list.
  - `configs/params.yaml` — the central hyperparameter file. Sections:
    `macro_acquisition` (date range, per-source publication lag, coverage
    threshold) and `stage1_feature_matrix` (date range, extended-tier
    duration/convexity coverage threshold). Add new sections here as later
    stages need tunable parameters — never hardcode a hyperparameter in code.
- `test_lag_rules.py` has real bias-prevention assertions (previously a
  placeholder) covering both the macro pull (`available_date` vs.
  `period_date`/publication lag) and the Stage 1 feature matrix (no row's
  `asof_max_available_date` may exceed its `rebal_date`). Extend it with
  walk-forward / training-window checks as those are built.
- **Confirmed full-sample window: 2005–2025** (not the 2005–2023 figure
  still in `docs/thesis_outline_sovereign.md` §1.4 — that text is being
  updated separately). All data pulls and the Stage 1 feature matrix use
  `2005-01-01`–`2025-12-31`; treat this as the authoritative range for any
  later stage.
- **Bond data provenance is now resolved** (2026-08-10): the raw CSVs in
  `data/raw/bonds/` were never produced by `eikon_sovereign_pull_deprecated.py`
  (it requests a non-overlapping field set via the old `eikon` package —
  confirmed by diffing its field list against the actual on-disk columns).
  The real pull ran as an untracked script, `data_pull.py`, on a
  university-library Windows PC, already using `lseg-data` against RDP/EDP
  endpoints (confirmed via `data/logs/pull_log.txt`'s 2026-06-08 traceback,
  which shows the real file path and RDP endpoint URLs hit). That original
  script could not be recovered. It has been replaced by
  `src/data_acquisition/bond_data_pull_reconstructed.py` — a design-level
  reconstruction, **structurally verified against the on-disk data but not
  execution-verified** (see its docstring for the full verification note,
  including one flagged mismatch on YLDTOMAT licence scope). The old
  `eikon`-based script is kept only for historical reference, renamed to
  `eikon_sovereign_pull_deprecated.py` with a docstring banner — don't run
  it or treat it as the current approach.
  - **Standing constraint**: this environment has no Refinitiv Workspace /
    `lseg-data` access. Live execution-level verification of
    `bond_data_pull_reconstructed.py` (does it actually run, chunk, and
    return data as expected) requires the university library PC and cannot
    happen here. Treat the script as unverified-by-execution until that
    session happens.
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
- Bond data pull: `python src/data_acquisition/bond_data_pull_reconstructed.py`
  — requires Refinitiv Workspace open and logged in on the same machine
  (university library PC only; not runnable from this environment). Not yet
  execution-verified — see "Current state" above. The old
  `eikon_sovereign_pull_deprecated.py` is dead; do not run it.
- Run the macro data pull: `python src/data_acquisition/macro_pull.py`
  (`--refresh` to bypass the cache and re-fetch everything). No API keys or
  desktop apps required — World Bank, IMF DataMapper, and FRED's CSV
  endpoint are all key-free public APIs.
- Build the Stage 1 feature matrix: `python src/stage1_clustering/build_feature_matrix.py`
  — reads `data/raw/bonds/` and `data/raw/macro/macro_fundamentals.csv`,
  writes both parquet tiers to `data/processed/` and prints per-tier
  diagnostics (row/country counts, per-column missingness, as-of-join drops).
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
  Workspace. The real pull already used `lseg-data`/RDP endpoints (see
  "Current state" above); only the now-dead `eikon_sovereign_pull_deprecated.py`
  in this repo used the old `eikon` package, and it never produced any data
  on disk.
- App key must be generated via "EDP API," not "Eikon Data API".
- Bond data pulled via `XX10YT=RR` benchmark RICs.
- DM countries return rich field sets; EM countries typically return only
  `MID_PRICE` and `BMK_SPD` — column-renaming logic must be adaptive, never
  hardcoded, or it breaks silently on EM tickers.
- `YLDTOMAT` (yield to maturity) is present only for the 5 countries in the
  `full_dm` coverage tier — Germany, Japan, Switzerland, United Kingdom,
  United States — populated at 98.5–100%. It is absent (not sparse — the
  column itself does not exist) for all other 39 countries, including
  unambiguous DM sovereigns such as Australia, Canada, France, and Italy.
  This is not a DM-vs-EM split; it is a licence/entitlement boundary that
  happens to coincide with the pre-existing `full_dm` tier definition. The
  previously documented claim that YLDTOMAT is "US-only" was incorrect and
  is superseded by this finding (full 44-country coverage check, 2026-08-10).
  Downstream code must continue to check column presence per country rather
  than assuming YLDTOMAT availability from DM/EM status alone. For the other
  39 countries, source YTM from IMF WEO / World Bank instead.
- CDS is not available as a standalone series; `INT_CDS` is only accessible
  on DM benchmark RICs.
- `TR.IssuerRating` returns only a current snapshot, not a historical
  series — ratings history is pulled directly from S&P/Moody's/Fitch
  websites.
- Universe exclusions (structural licence constraints, not bugs): Russia
  (permissions block); Argentina, Ecuador, Panama, Dominican Republic, Qatar,
  Saudi Arabia, UAE, Ukraine (no benchmark RICs). The dead
  `eikon_sovereign_pull_deprecated.py`'s `UNIVERSE` dict still includes
  several of these (predates the exclusion decision) — ignore it;
  `bond_data_pull_reconstructed.py`'s `UNIVERSE` already reflects the
  exclusions and matches `configs/universe.yaml`.
- EM data sparsity is a structural constraint of the university licence, not
  a script error — thesis sections 1.4, 3.2, 3.3, 3.4, 4.2.1, 6.6, and
  Appendix B need to reflect this framing.
- **Bond/CDS/ratings pull provenance**: the raw data in `data/raw/bonds/`
  and `data/raw/ratings/` came from an untracked script (`data_pull.py`, run
  2026-06-08 on a university-library Windows PC) that could not be
  recovered. `bond_data_pull_reconstructed.py` is a structurally-verified,
  execution-unverified reconstruction — see "Current state" above and the
  script's own docstring for the full verification note. No further bond
  pull is needed before Stage 2 (existing data already feeds Stage 1
  successfully); the open item is reproducibility documentation for
  Appendix A, not missing data.

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

## Stage 1 feature matrix (country x quarter — settled facts)
`src/stage1_clustering/build_feature_matrix.py` builds two wide, country x
quarter-end panels for the 44-country universe over **2005-2025**, writing
`data/processed/stage1_feature_matrix_core.parquet` (all 44 countries) and
`data/processed/stage1_feature_matrix_extended.parquet` (DM + duration/
convexity-rich EM). Agency ratings are excluded from both — see "Ratings
pull is still an open gap" below.

- **`yield_spread_bps` is sourced from the raw bond CSVs' `ZSPREAD` column,
  not `BMK_SPD`.** `BMK_SPD` is ~0% populated for most EM countries and,
  oddly, for the DM reserve-currency benchmarks themselves (US/UK/Japan/
  Germany all near 0%) — it appears to measure spread vs. each country's own
  benchmark curve, which is structurally near-zero for the benchmark bond
  itself, not a cross-country-comparable figure. `ZSPREAD` has 40–90%
  coverage for most countries and was validated against Greece's known 2012
  crisis spike (raw daily ZSPREAD ~2900–3800bps in June 2012; the Stage 1
  quarter-end value for 2012-06-30 is 2447.6bps, consistent with spreads
  easing after the June 17, 2012 election reduced euro-exit fears).
- **`ZSPREAD` is a spread over the swap curve, not over US Treasuries.**
  This matters beyond naming: it embeds a swap/OIS basis component on top of
  sovereign credit risk, so it is not a drop-in equivalent to a UST-based
  spread as described in thesis §3.3's Group A feature table. Flag this
  explicitly in Appendix B when documenting feature construction formulas.
- **Bond market data has no publication lag.** Unlike macro fundamentals,
  `yield_spread_bps`, `mod_duration`, `convexity`, and `cds_5y` are treated
  as knowable same-day (the bond CSVs' own `date` column, no separate
  `available_date`) — they are market-observed pricing, not a lagged
  publication. This assumption belongs next to the macro publication-lag
  documentation in Appendix B, since together they cover the full set of
  point-in-time assumptions the pipeline makes.
- **Quarter-end resampling uses the last observation in-quarter**, not a
  mean, for all bond fields.
- **Macro columns are joined via a backward as-of merge**
  (`available_date <= rebal_date`, `pd.merge_asof(..., direction="backward")`),
  never a plain date match — this is what prevents a macro figure from
  entering a quarter before it was actually publishable. Each row carries
  `asof_max_available_date` (the max `available_date` across the macro
  columns used) and `data_asof_ok` (whether that max is `<= rebal_date`);
  `test_lag_rules.py` asserts this holds for every row in both parquet
  files. On the last full run, 0 rows were dropped for `data_asof_ok=False`
  in either tier (expected, since the as-of join enforces this by
  construction — the check exists as an explicit, executable invariant).
- **`wb_or_imf_source` is implemented as 7 `_source` columns**, one per
  World Bank/IMF WEO-backed macro feature (`debt_gdp_source`,
  `fiscal_bal_gdp_source`, etc.) — not a single combined column — matching
  the values from `macro_fundamentals.csv`'s `source` field for the row
  actually matched by the as-of join.
- **Extended-tier "data-rich EM" is gated on `MOD_DURTN`/`CONVEXITY`
  coverage, not CDS coverage.** Raw CDS (`INT_CDS`) is essentially DM-only —
  among 26 EM countries only Egypt has any non-null CDS (~5% of rows); the
  dedicated `data/raw/cds/` pull never succeeded (see "Data acquisition
  status" above). Gating on CDS presence would collapse the extended tier to
  ~DM + Egypt. Instead, `configs/params.yaml:
  stage1_feature_matrix.extended_tier_min_duration_convexity_coverage`
  (currently 0.7) gates on full-history `MOD_DURTN`/`CONVEXITY` non-null
  coverage; `cds_5y` stays sparse/NaN for most EM rows in the extended tier,
  caught by `missing_flag` rather than tier exclusion.
  - **Correction to the original estimate**: pre-implementation analysis
    expected the 0.7 threshold to exclude only Peru (55% coverage). The
    actual run excludes **three** EM countries — Peru (54%), Hungary (64%),
    Colombia (66%) — giving an extended tier of **41 countries (18 DM + 23
    EM)**, not 43. This threshold is a candidate for the thesis's §5.5
    sensitivity sweep (0.6/0.7/0.8) once Stage 1 clustering results exist;
    no need to test multiple thresholds before then.
- **`coverage_tier`** is a per-row metadata column (not a tier-membership
  gate) recording which of 4 raw bond-field-richness variants a country's
  CSV has: `full_dm` (has `CLEAN_PRC`/`DIRTY_PRC` and `YLDTOMAT` — Germany,
  Japan, Switzerland, UK, US), `dm_standard` (has `CLEAN_PRC`/`DIRTY_PRC`,
  no `YLDTOMAT`), `em_standard` (has `MID_PRICE` only), `em_minimal` (no
  `MID_PRICE` at all — Kazakhstan, Morocco).
- **Coverage as of the last full run**:
  - CORE: 3,696 rows (44 countries x 84 quarters), 0 rows dropped for
    `data_asof_ok=False`. `yield_spread_bps` missingness is a high 43.2% —
    driven by several frontier EM countries (Chile, Kazakhstan, Morocco,
    Peru, Sri Lanka, Zambia, Nigeria) having ~0% `ZSPREAD` coverage in the
    raw pull, not a join bug. The 7 macro fundamentals are 6.0% missing each
    (early quarters before any macro data is knowable yet, plus Poland's
    entirely-IMF-fallback debt/GDP); `dxy_proxy` is 4.8% missing (the
    documented 2005 gap, see "Macro data acquisition"); `us_10y`/`us_2y`/
    `vix`/`curve_slope` are 3.6% missing each.
  - EXTENDED: 3,444 rows (41 countries x 84 quarters), 0 rows dropped for
    `data_asof_ok=False`. `cds_5y` is 82% missing (18% populated) — sparser
    than DM-only but less extreme than the raw daily per-country CDS
    percentages suggested, since quarter-end resampling and full-panel
    averaging behave differently from raw daily coverage; `mod_duration`/
    `convexity` are 12.2% missing (early quarters before a country's bond
    history starts, e.g. Turkey 2010, Zambia 2012).
- **Ratings pull is still an open gap.** Every `data/raw/ratings/*.csv` is
  just a header + one blank-value row — the real S&P/Moody's/Fitch website
  pull described in "Data acquisition status" above never happened. No
  `ratings_panel` table exists yet; both Stage 1 tiers simply exclude
  ratings, as the thesis design requires (ratings are a Stage 1 validation
  target — §4.2.3/§4.2.4 — not a clustering input). Tracked as a follow-up
  GitHub issue, blocking for those sections and for RQ1/H1 (the
  ratings-lead/lag validation depends on real ratings history).

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
- Bond market data (spread, duration, convexity, CDS) has no publication
  lag — it's treated as same-day-knowable, unlike macro fundamentals. See
  "Stage 1 feature matrix" above.

## Conventions
- Python throughout.
- All hyperparameters live in `configs/params.yaml`.
- SHAP is used for Stage 2 model interpretability.
- HRP (Hierarchical Risk Parity) is the Stage 3 allocation method.
