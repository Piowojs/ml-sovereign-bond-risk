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

For a chronological log of what's been done, key decisions and their
rationale, and open items (distinct from this file's operational focus),
see `state.md` at the repo root — check it for the fuller narrative behind
any settled fact summarized here.

## Current state of the repo
This is an early-stage scaffold, not a working pipeline yet:
- `src/stage1_clustering/build_feature_matrix.py` builds the country x
  quarter feature matrix — see "Stage 1 feature matrix" below for full
  details. The actual clustering step now exists too:
  `src/stage1_clustering/clustering_utils.py` (shared primitives),
  `algorithm_comparison.py` (§4.2.1-4.2.3, diagnostic), and
  `build_risk_labels.py` (§4.2.5, walk-forward-safe production labels) —
  see "Stage 1 clustering" below for full details, including a
  methodologically important finding (VIX/DXY had to be dropped from the
  Stage 1 feature set — see that section). `stage2_signal/` is now built
  too — `stage2_utils.py` (shared primitives), `build_stage2_panel.py`
  (§4.3.2 target construction + §3.3 Stage-2-scoped features),
  `model_comparison.py` (§4.3.3 walk-forward LASSO/RF/XGBoost comparison,
  diagnostic), `build_return_signals.py` (§4.3.5 walk-forward-safe
  production signal + top-N output), `feature_importance.py` (§4.3.4
  SHAP), and `multi_horizon_robustness.py` (§2.4/§2.8 pre-registered
  robustness check across monthly/quarterly/semi-annual return horizons)
  — see "Stage 2 signal" below for full details, including a real
  data gap discovered before building (no coupon/cashflow field exists
  anywhere in the raw bond pull) and its documented, flagged workaround.
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
    threshold), `stage1_feature_matrix` (date range, extended-tier
    duration/convexity coverage threshold), `stage1_clustering` (feature
    set, imputation threshold, k range, chosen algorithm/tier/k — see
    "Stage 1 clustering" below), `stage2_signal` (target/feature
    construction params, model feature set, model hyperparameters, chosen
    model per framing — see "Stage 2 signal" below), and
    `ratings_ingestion`. Add new sections here as later stages need
    tunable parameters — never hardcode a hyperparameter in code.
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
- `src/data_acquisition/ingest_ratings.py` consolidates manually-collected
  sovereign rating-action files into `data/processed/ratings_panel.csv` —
  see "Ratings data acquisition" below for full details, including why
  this is a manual-file ingestion pipeline rather than a scripted pull.
  `src/data_acquisition/reconcile_ratings_sources.py` runs first when a
  country has both GE and CE transcriptions (recommended going forward),
  merging them under a documented priority policy before
  `ingest_ratings.py` ever sees the file.
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
- Reconcile a country's two ratings sources (when both GE and CE were
  transcribed): `python src/data_acquisition/reconcile_ratings_sources.py
  <Country> --xlsx <path to two-sheet workbook>` — writes
  `data/raw/ratings/manual/<Country>.csv` and
  `_reconciliation/<Country>_conflicts.csv`. Re-run after adding rows to
  `_reconciliation/<Country>_resolutions.csv` to fold resolved conflicts
  into the merged file.
- Consolidate ratings: `python src/data_acquisition/ingest_ratings.py` —
  reads whatever manually-collected per-country files exist in
  `data/raw/ratings/manual/`, writes `data/processed/ratings_panel.csv`,
  and logs coverage against the 44-country universe. No API/desktop app
  involved; safe to re-run any time as more countries' files are added.
- Run the Stage 1 algorithm comparison (diagnostic, full-sample —
  §4.2.1-4.2.3): `python src/stage1_clustering/algorithm_comparison.py`
  — writes `data/processed/stage1_algorithm_comparison.csv`,
  `stage1_dmem_disagreements.csv`, `stage1_dmem_ari_by_quarter.csv`.
  Requires `scikit-learn` and `hdbscan` (in `requirements.txt`).
- Build the Stage 1 walk-forward risk labels (production, §4.2.5):
  `python src/stage1_clustering/build_risk_labels.py` — reads the chosen
  algorithm/tier/k from `configs/params.yaml: stage1_clustering`, writes
  `data/processed/stage1_risk_labels.parquet`. Run
  `algorithm_comparison.py` first if changing the chosen combo — see
  "Stage 1 clustering" below.
- Build the Stage 2 target + feature panel (§4.3.2, §3.3 Stage-2-scoped
  features): `python src/stage2_signal/build_stage2_panel.py` — reads
  `data/processed/stage1_risk_labels.parquet` (EM satellite-candidate
  rows) and `stage1_feature_matrix_core.parquet`, plus the raw
  `data/raw/bonds/*.csv` files directly for price/momentum/carry/spread
  z-score, writes `data/processed/stage2_signal_panel.parquet`. Run this
  first whenever Stage 1's risk labels change.
- Run the Stage 2 model comparison (diagnostic, walk-forward — §4.3.3):
  `python src/stage2_signal/model_comparison.py` — writes
  `data/processed/stage2_model_comparison.csv` (per-fold) and
  `stage2_model_comparison_summary.csv`. See "Stage 2 signal" below for
  why LASSO was chosen over Random Forest/XGBoost for both framings.
- Build the Stage 2 walk-forward return signals (production, §4.3.5):
  `python src/stage2_signal/build_return_signals.py` — reads the chosen
  models from `configs/params.yaml: stage2_signal`, writes
  `data/processed/stage2_return_signals.parquet` (includes `top_5`/
  `top_10`/`top_15` selection flags per rebalancing date).
- Compute Stage 2 SHAP feature importance (§4.3.4):
  `python src/stage2_signal/feature_importance.py` — writes
  `data/processed/stage2_shap_importance.csv`. Full-sample diagnostic fit,
  not a walk-forward output — see "Stage 2 signal" below.
- Run the H2 multi-horizon robustness check (§2.4, §2.8 — pre-registered,
  see "Stage 2 signal" below and `state.md`):
  `python src/stage2_signal/multi_horizon_robustness.py` — writes
  `data/processed/stage2_multi_horizon_robustness.csv` (per-fold) and
  `stage2_multi_horizon_robustness_summary.csv`. Reuses
  `stage2_signal_panel.parquet`; rerun `build_stage2_panel.py` first if
  Stage 1's risk labels change.
- Run `test_lag_rules.py` after any change touching data loading, feature
  construction, clustering inputs, or backtesting logic —
  this is the project's core correctness check (see Bias-prevention rules).
  Includes a truncation-invariance leakage test for the Stage 1 walk-forward
  labeler (re-running it on a truncated panel and diffing against the
  full-panel output) — see "Stage 1 clustering" below — and an analogous
  pair of Stage 2 checks (structural + truncation-invariance, checked
  across many rebalancing dates) — see "Stage 2 signal" below.

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

## Ratings data acquisition (issue #3 — settled facts)
Real sovereign rating history (not just a current snapshot) is required for
thesis §4.2.3/§4.2.4 and RQ1/H1 (does the ML risk score deteriorate ahead
of agency downgrades?). `TR.IssuerRating` (Refinitiv) is a confirmed dead
end for this — SDate/EDate are silently ignored and it only ever returns
the current snapshot, under our licence. Free public alternatives were
evaluated as automatable replacements (2026-08-10) and rejected:
- **Damodaran's country risk dataset** (NYU Stern, `ctryprem.xlsx`) is a
  current-snapshot table only (no historical time series at all) —
  useful only as an independent point-in-time cross-check, never as a
  pipeline input.
- **Trading Economics** exposes historical ratings only behind its paid
  API tier; the free website shows current ratings only.

**Primary manual source: TheGlobalEconomy.com, not countryeconomy.com**
(switched 2026-08-10, before any country was transcribed against either).
countryeconomy.com was the original pick — real dated rating-action
history back to the 1990s for many countries — but it turned out to have
a structural trap: each country page lays out **four independent
chronological lists** (Long-term Foreign Currency, Long-term Local
Currency, Short-term Foreign Currency, Short-term Local Currency) side by
side in one HTML table, positioned by row-index, not by shared date.
Adjacent columns on the same visual row are frequently different,
unrelated dates — confirmed on Greece's page, where the row showing
`2022-04-22 BB+ (Stable)` in the Foreign Currency column pairs visually
with `2025-04-18 BBB` in the Local Currency column, a different action
three years apart. Only the Long-term/Foreign-Currency pair matters for
our USD-denominated universe — the other three columns must be ignored
entirely, not read row-aligned, a real transcription-error risk if
missed. It also sometimes leaves the rating cell blank on an
outlook-only-change row, forcing inference from the row above.
TheGlobalEconomy.com's per-country tables are flat, single-list,
multi-agency (`agency | rating | outlook | date`), and every row carries
an explicit rating value even when only the outlook changed — no
blank-cell inference needed, a much closer structural match to our manual
CSV schema. countryeconomy.com is now a fallback only, used with the
column-alignment caveat above kept firmly in mind. Both remain
third-party aggregators, not primary agency sources — cite them as such.
- **Scope** is a 4th agency TheGlobalEconomy.com's tables include
  alongside S&P/Moody's/Fitch. Out of scope for this thesis and for
  `RATING_MAP` — drop Scope rows during transcription; `ingest_ratings.py`
  rejects them defensively if one slips through.
- **Date precision**: TheGlobalEconomy.com gives month/year precision
  only (e.g. `5/2026`), not exact day. Convention: use the 1st of the
  month as `date`, and append `(month-precision)` to `source` for
  traceability. Coarser than exact-day, but still well within thesis
  §4.5.1's quarterly walk-forward fold granularity, so H1's quarter-level
  lead/lag windows lose no real resolution. This does **not** interact
  with `test_lag_rules.py`'s zero-lag assertion — `available_date` is
  always set equal to whatever `date` value is in the raw file, so that
  check passes trivially regardless of precision (it was only ever
  checking `available_date == date`, never validating precision itself).
  The real risk from mixing precisions is a phantom near-duplicate: the
  same real-world action transcribed once from an exact-day source and
  once from a month-precision source looks like two distinct nearby rows.
  `ingest_ratings.py`'s `_warn_possible_duplicate_actions` flags same
  country+agency+rating_numeric pairs less than 35 days apart for manual
  review rather than silently double-counting them.

Given that, `src/data_acquisition/ingest_ratings.py` is deliberately **not**
a scraper or API pull. It's a normalizer: it reads whatever per-country
rating-history files have already been manually collected — transcribed
from TheGlobalEconomy.com (primary), countryeconomy.com (fallback, mind
the column-alignment caveat above), or S&P/Moody's/Fitch
investor-relations and press-release pages — from
`data/raw/ratings/manual/<Country>.csv` (see `_TEMPLATE.csv` there for the
exact format: `date,agency,rating,outlook,action,source`), and writes one
consolidated table to `data/processed/ratings_panel.csv`. It's designed to
be run incrementally as files land one country at a time — no raw file
yet for a country just means it's absent from the output, not an error.
- `rating_numeric` uses the same ordinal `RATING_MAP` as the dead
  `eikon_sovereign_pull_deprecated.py` (copied over, since the mapping
  itself doesn't depend on how the ratings were pulled).
- `outlook` is carried through to the output panel as its own column, not
  just used internally — outlook deterioration (e.g. Stable → Negative,
  no letter-grade change) can precede an actual downgrade by months, a
  potential leading-indicator signal beyond letter-grade actions alone.
  Thesis §1.5/§4.2.4's formal H1 test is defined against letter-grade
  downgrades specifically, so this isn't required for that test, but was
  captured now — marginal transcription cost ~zero — rather than
  retrofitted later if a future analysis wants it.
- `action` (upgrade/downgrade/outlook_change/affirm/initial) is inferred
  automatically, chronologically per country+agency, whenever the raw
  file leaves it blank: a `rating_numeric` change gives
  upgrade/downgrade; an unchanged rating with a changed `outlook` gives
  `outlook_change` (rather than collapsing it into `affirm`); otherwise
  `affirm`. An explicit value in the raw file is always kept as-is.
- **Zero publication lag, by design**: `available_date = date` for every
  row — rating actions are same-day public announcements (agency press
  releases / RNS filings), unlike World Bank/IMF's multi-month lag for
  periodic macro releases. Configured at `configs/params.yaml:
  ratings_ingestion.lag_days` (0) and asserted by `test_lag_rules.py`.
- Existing `data/raw/ratings/*.csv` files (the header-only stubs from the
  never-recovered original pull, see "Data acquisition status" above) are
  untouched by this script — it only reads `data/raw/ratings/manual/` and
  writes `data/processed/`, never `data/raw/` itself.
- **`src/data_acquisition/reconcile_ratings_sources.py`** merges a
  country's GE and CE transcriptions (two sheets of one .xlsx) into the
  `data/raw/ratings/manual/<Country>.csv` this script reads, applying an
  explicit, documented priority policy rather than silently picking a
  source: CE's default-designation rows (SD/RD/D) always win, since GE
  systematically omits them; not-rated/withdrawn tokens (e.g. `NR`) and
  Moody's short-term-scale tokens (e.g. `NP`, a different scale from
  `RATING_MAP`'s long-term one) in the *rating* field are dropped rather
  than crashing an unmappable lookup; CE's embedded-outlook (both the
  `BBB (Positive)` trailing form and the letter-grade-less `(Negative)`
  form — the latter must become true `NA`, not `""`, or it silently
  corrupts forward-fill for every later row in that agency's group),
  leading `(P)`-provisional prefix, and blank-rating (watch/under-review)
  quirks are all cleaned up before comparison; byte-for-byte duplicate
  rows within a single source are dropped before any matching; a watch/
  under-review qualifier present on only one side (e.g. GE `Negative
  watch` vs CE plain `Negative`) is treated as an information asymmetry,
  not a disagreement — the ratings still have to agree, but the more
  specific watch-qualified wording wins the merge regardless of which
  source had it; an agency entirely absent from one source (e.g. CE has
  zero Moody's rows for Zambia — confirmed genuine, not a scraping gap)
  needs no special handling, it's just every month becoming a
  single-source addition via the general union-of-months policy below;
  agreeing (agency, month) rows from both sources collapse into one row
  preferring CE's exact date; genuinely disagreeing rows are written to
  `_reconciliation/<Country>_conflicts.csv`, never auto-resolved, and
  only enter the merged output once a matching row appears in
  `_reconciliation/<Country>_resolutions.csv` recording which source was
  chosen, at what confidence, and why. **Known, accepted limitation**:
  matching buckets by calendar month means a same-action pair straddling
  a month boundary (CE's exact late-month date vs GE's 1st-of-*next*-
  month rounding) won't be caught as a match — found on Sri Lanka (Fitch,
  Nov 27 CE vs Dec 1 GE, same rating) and surfaced instead by
  `ingest_ratings.py`'s downstream duplicate-action warning, which is the
  accepted safety net for this gap rather than a bug to chase with
  riskier cross-month matching. See that script's docstring for the full
  policy and `state.md` for the worked Greece/Turkey/Sri Lanka/Portugal/
  Zambia/South Africa/Brazil/Colombia examples (eleven matching-logic
  policy points the real data drove across all eight, and how each was
  handled).
- **`RATING_MAP` (in `ingest_ratings.py`, imported by
  `reconcile_ratings_sources.py`) carries one confirmed transcription-
  artifact alias**: `"Ca-"` → 20, same value as `"Ca"`. Moody's own
  rating-scale documentation confirms long-term modifiers (1/2/3) only
  apply Aaa through Caa3 — Ca and C take no modifier at all, so `Ca-`
  found on a Zambia GE row (2020-04, right in the default window) isn't a
  real notch. Confirmed with the user before adding it, not guessed. The
  raw string `Ca-` is left as-is in `Zambia.csv` (only the numeric
  mapping is aliased, not the transcribed text rewritten).
- **Status as of 2026-08-11**: pipeline built and verified against
  synthetic test files (mapping, action/outlook_change inference,
  duplicate-action detection, Scope rejection, and coverage logging all
  confirmed correct); **5/44 countries collected — Greece, Turkey, Sri
  Lanka, Portugal, Zambia**, all reconciled from GE + CE via
  `reconcile_ratings_sources.py` (172 + 170 + 118 + 108 + 45 = 613 rows;
  3 genuine cross-source conflicts found and resolved total, all on
  Greece/Turkey — Sri Lanka, Portugal, and Zambia each had zero, Portugal
  only after the watch-qualifier-asymmetry policy folded its original 2
  in). Sri Lanka's 2022 default sequence confirmed the same GE
  default-designation gap seen on Greece, extending across the *entire*
  2022-2024 distressed/restructuring window for S&P and Fitch, not just
  the SD/RD moment itself; Portugal, as expected for a bailout rather
  than a default, had zero SD/RD/D designations and no GE blackout
  pattern in 2011-2014 — confirming the blackout is specifically tied to
  default events, not crisis periods generally. **Zambia extended both
  findings further**: CE captured a single SD (S&P) and single RD
  (Fitch) as expected, but Fitch's GE row also shows a *second* RD nearly
  4 years later (2024-12, outlook `NR`) — plausibly reflecting that
  Zambia's own debt restructuring didn't formally close until 2024, with
  Fitch conventionally holding an issuer in RD until a distressed
  exchange fully completes (a B-/Stable exit rating follows in Nov 2025).
  GE's blackout was *more* severe than Sri Lanka's for one agency: S&P's
  GE gap runs 2019-08 → 2025-11, over 6 years, versus Fitch's ~3 years —
  the blackout isn't a fixed duration, it appears to track how long each
  specific agency actually kept the issuer in distressed/default status.
  This closed all 5 of 5 Tier 1 countries. **South Africa (first Tier 2
  country, 2026-08-12)** added a 6th: 137 rows, 1 genuine conflict (Fitch
  2020-11, GE `Stable` vs CE-confirmed-correct `Negative`, a factual
  error not just a precision gap — Fitch's own release title and South
  Africa's National Treasury both confirm `Negative`), no SD/RD/D (none
  expected, none found), and the full 2012–2020 graduated
  investment-grade-loss trajectory confirmed present with no gaps in
  either source. Also the first country to validate the raw-paste
  CE-transcription workflow (both `LETTER_GRADE (Outlook)` and bare
  `(Outlook)`-only cells) against real, not synthetic, data — clean, no
  new edge case. **Brazil (second Tier 2 country, completing the South
  Africa/Brazil pair, 2026-08-12)** added a 7th: 137 rows, 1 genuine
  conflict (Moody's 2018-04, GE `Negative` vs CE-confirmed-correct
  `Stable`), no SD/RD/D, and the full pre-2015 investment-grade period
  plus the 2015–2016 downgrade-to-junk sequence (S&P first, Fitch next,
  Moody's last, all within ~5 months — matching the known
  Petrobras/recession story) confirmed present with no gaps. **The GE
  factual-error hypothesis was revised, not just extended, on this
  case**: the original multi-agency-round-clustering idea (from South
  Africa) was directly tested against Brazil's conflict and did *not*
  hold — no other agency acted anywhere near April 2018 — but Brazil's
  error turned out to share a more precise commonality with South
  Africa's anyway: in both, GE got the *rating* right and only the
  *outlook* wrong (South Africa borrowed a different agency's concurrent
  outlook; Brazil carried forward the same agency's own prior outlook
  instead of picking up an outlook-only revision). Turkey's original case
  (a rating-level error) remains a separate, unexplained outlier under
  this revised characterization. Standing hypothesis: **GE is reliable
  on letter ratings, unreliable on outlook-only updates** — see
  `state.md`'s "GE factual-error tracking" section for the full table and
  rationale. **Colombia (third Tier 2 country, completing the
  fiscal-deterioration/non-Eurozone trio, 2026-08-12)** added an 8th: 94
  rows, the pre-2021 IG period and 2021 downgrade sequence confirmed with
  no gaps — S&P first into junk, Fitch ~2 months later, and **Moody's
  held Baa2 continuously through 2021**, a partial (2-of-3) rather than
  universal loss of investment grade, only reaching junk itself in June
  2025. No SD/RD/D, as expected. Its one candidate conflict (S&P
  2025-06, GE outlook `NR` vs CE `Negative`) drove a new permanent
  policy rather than a one-off resolution: `NR` recurs as a GE outlook
  value often enough (8 of 33 GE S&P rows in this file) to be a
  convention meaning "no outlook tracked," not a directional assertion
  — `_outlook_eq`/`_prefer_outlook` now treat an outlook-field `NR` as
  equivalent to blank, explicitly kept separate in the docstring from a
  *rating*-field `NR` (still withdrawn coverage, still dropped outright).
  Applying the policy dissolved Colombia's conflict automatically. **Not
  counted as a third GE factual-error case** — South Africa/Brazil were
  GE asserting something wrong, this was GE asserting nothing at all; the
  hypothesis stays at 2 confirmed cases, untested by Colombia either way.
  **Egypt (first currency/commodity-driven country, 2026-08-12)** added
  a 9th: 138 rows, **zero conflicts** — the cleanest run since Sri Lanka
  — and all three of Egypt's stress episodes (Arab Spring 2011–2013,
  2016 currency-float/IMF period, 2022–2024 currency crisis) confirmed
  present with no gaps from either source. The 2016 window shows flat
  ratings rather than a fresh downgrade wave — a real historical
  pattern (the IMF deal read as a credibility anchor, not a
  credit-negative shock), not a coverage gap. No SD/RD/D, as expected.
  Zero conflicts means no test of the GE hypothesis this round either
  way. Egypt was reconciled *after* a written prediction was committed
  to `state.md` (Refs #4) that Egypt, Pakistan, and Nigeria should all
  come back null or near-null on the lead/lag pilot, since the working
  explanation for the pilot's mixed results ties positive signal to
  macro-fundamental-driven downgrades specifically — see `state.md`'s
  pre-registration entry for the full prediction and reasoning, committed
  before any of the three was touched, same discipline as the Stage 2
  multi-horizon protocol. **Pakistan (second currency/commodity-driven
  country, 2026-08-12)** added a 10th: 84 rows, **zero conflicts again**
  (neither currency/commodity-group country has produced one yet, unlike
  every fiscal-deterioration-group country), no SD/RD/D despite Pakistan
  genuinely nearing default in 2008 (S&P `CCC`/`CCC+`) and again 2022-23
  (Fitch `CCC-`, Moody's `Caa3`) — confirming the expectation, no primary-
  source check needed. The IMF-programme-flat-rating pattern Egypt showed
  in 2016 replicates during Pakistan's 2019 EFF arrangement (ratings hold
  or outlooks improve rather than deteriorate further), though over a
  much shorter window than Egypt's ~3-year plateau — a second data point
  toward a real, repeatable pattern, not confirmed as one yet. Manually
  collecting and transcribing the remaining 34 per-country files (Nigeria
  next, closing the currency/commodity trio, then Italy/Spain) is open,
  user-side work — see `state.md` for the full log, including the
  priority order and the GE factual-error tracking table, and issue #3
  for tracking.

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
- **Real ratings data is still an open gap, but the pipeline is now built.**
  Every `data/raw/ratings/*.csv` is still just a header + one blank-value
  row — the real S&P/Moody's/Fitch website pull described in "Data
  acquisition status" above never happened, and no free API offers
  automatable history (see "Ratings data acquisition" above). What's
  changed: `src/data_acquisition/ingest_ratings.py` can now consolidate
  manually-collected per-country rating-action files into a real
  `ratings_panel` table the moment they're dropped into
  `data/raw/ratings/manual/`; today that table has 0 rows since no country
  has been transcribed yet. Both Stage 1 tiers correctly continue to
  exclude ratings regardless (ratings are a Stage 1 validation target —
  §4.2.3/§4.2.4 — not a clustering input). Tracked in issue #3, blocking
  for those sections and for RQ1/H1 (the ratings-lead/lag validation
  depends on real ratings history) until enough countries are collected.

## Stage 1 clustering (thesis §4.2.1-4.2.3, §4.2.5 — settled facts)
Built on top of the feature matrices above. Two genuinely separate
pipelines share primitives in `src/stage1_clustering/clustering_utils.py`
but must not be conflated:
- `algorithm_comparison.py` (§4.2.1-4.2.3) fits **once on the full
  2005-2025 panel, pooled across all quarters** — diagnostic/descriptive
  only, used to pick an algorithm/tier/k and to examine DM/EM
  disagreements. **Not point-in-time safe** — a model fit on the whole
  sample implicitly "knows" about 2025 when scoring a 2008 row — so its
  output must never feed Stage 3/4.
- `build_risk_labels.py` (§4.2.5) is the actual production pipeline: at
  every rebalancing date it refits the chosen model from scratch using
  only rows with `rebal_date <= that date` (expanding window, same
  principle as the macro publication-lag rule elsewhere in this repo),
  then predicts that quarter's labels. This is what's safe to feed
  downstream, and what `test_lag_rules.py`'s truncation-invariance check
  (see below) verifies.

**Feature set — and a methodologically important correction.** Per thesis
§3.3's Group C table, only `curve_slope` and `us_10y` are scoped to Stage
1 ("1 & 2"); VIX and DXY are scoped to Stage 2 only ("2"). An early
version of this pipeline included `vix`/`dxy_proxy` in the Stage 1
feature set anyway, and it produced a concrete, diagnosable failure: since
global features are identical across all 44 countries within a given
quarter (all their variance is *across time*, none of it *across
countries*), the pooled full-sample fit let them dominate the distance
metric and collapsed entire quarters into a single risk tier regardless
of country — e.g. 2008-2015 had **zero** countries in `core-eligible`
across the whole period, and 2023/2025 had **zero** in
`excluded`/`satellite-candidate`. That's a global-regime artifact, not
country risk differentiation, and it's the opposite of what Stage 1 is
supposed to produce. Restricting the feature set to what §3.3 actually
specifies (dropping `vix`/`dxy_proxy`) fixed this: full-sample ARI vs
DM/EM rose from 0.258 to 0.377 (KMeans, core, k=3) and every year in the
sample now has a genuine mix of all three tiers. A **residual, weaker**
version of the same effect persists even after the fix (`core-eligible`
is genuinely 0 for several consecutive quarters in 2009-2017 in the
walk-forward output — see below), because `us_10y`/`curve_slope` are
still global-only features and the thesis's own spec keeps them in Stage
1; flagged as a candidate robustness check for §5.5, not fixed further
without a methodology-level decision to override the thesis's declared
feature groups. Final Stage 1 clustering feature set (`configs/params.yaml:
stage1_clustering.core_features`, extended tier adds `mod_duration` +
`convexity`): `yield_spread_bps`, the 7 macro fundamentals (`debt_gdp`,
`fiscal_bal_gdp`, `current_acct_gdp`, `fx_reserves_mo`, `cpi_inflation`,
`real_gdp_growth`, `political_stability`), `us_10y`, `curve_slope`.
`us_2y` is also excluded (redundant with `curve_slope`). `cds_5y` is
excluded from the extended tier's clustering features (kept in the
parquet, just not fed to the model) — at 82% missing, a feature that's
four-fifths imputed contributes mostly noise, not signal.

**Missing data handling.** A country-quarter row needs at least
`min_observed_feature_frac` (0.5) of its tier's features actually observed
(non-imputed) to get a real label; below that it's `insufficient_data`
rather than a label built mostly from imputation. Remaining gaps are
filled by **training-window-only median imputation** (never test-window
statistics — see Bias-prevention rules below). This has a specific,
worth-knowing consequence: 7 EM countries have **zero** `yield_spread_bps`
coverage ever (Chile, Peru, Morocco, Kazakhstan, Nigeria, Sri Lanka,
Zambia — see "Stage 1 feature matrix" above), so their spread column is
always the training-window median, and their cluster assignment is
effectively driven entirely by macro fundamentals + global factors, never
their own market-priced risk.

**Algorithm/k selection (§4.2.1-4.2.2) — actual numbers, not assumption.**
Ran K-Means and GMM for k=2..8 (silhouette, BIC, AIC — KMeans's BIC/AIC
use the standard spherical-Gaussian approximation, since KMeans has no
native likelihood) and HDBSCAN swept at `min_cluster_size` = 1%/2%/5% of
the analysis sample, on both CORE and EXTENDED tiers (6 combos total; full
numbers in `data/processed/stage1_algorithm_comparison.csv`). Findings:
- **HDBSCAN is not usable on this feature set at any density threshold
  tried.** At 2%/5% min_cluster_size it finds **zero** clusters (100%
  noise). At 1% (`min_cluster_size=35`) it "succeeds" with a deceptively
  high silhouette (0.33, the best of any combo) but ARI vs DM/EM of just
  0.018 (near-random) — inspecting the actual clusters shows why: one
  giant catch-all cluster (3,153 of 3,476 rows), a tiny 62-row cluster
  that's 100% DM (an extreme low-yield outlier pocket, not a risk tier),
  and 261 noise points scattered across both DM and EM. It isolates a
  density outlier, not an interpretable risk stratification. This is a
  clean instance of thesis §4.2.1's own caveat about HDBSCAN cutting both
  ways: robust to outliers, but here that means it collapses everything
  *except* the outliers into one undifferentiated mass.
- **GMM underperforms K-Means at essentially every k on both tiers** —
  e.g. core k=3: GMM ARI 0.296 / silhouette 0.115 vs K-Means ARI 0.377 /
  silhouette 0.136. GMM's elliptical-cluster flexibility doesn't pay off
  here; its BIC/AIC also don't show a clean elbow at k=3.
- **k=3 is not the silhouette-maximizing choice for K-Means** (silhouette
  is essentially flat across k=2..8, 0.13-0.17, no real elbow — the
  clusters are not that well separated at any k, itself a citable finding
  for §4.2.1/§6.1: sovereign risk doesn't form tight, well-separated
  clusters in this feature space). **k=2 has the highest raw ARI**
  (0.554, core) but is structurally unusable for §4.2.5's 3-tier output —
  by construction it never populates the `excluded` middle tier at all,
  collapsing the framework into a binary DM/EM lookalike with none of the
  "too uncertain for either sleeve" middle case the thesis output spec
  requires. **Among the options that actually support a 3-tier output,
  k=3 K-Means/core is the best combination of ARI (0.377, the highest of
  any k=3 combo across both algorithms and tiers) and silhouette
  (statistically indistinguishable from K-Means/core's k=2/4/5/8, all
  0.13-0.17)** — chosen on that basis, not by defaulting to K-Means for
  convenience. EXTENDED tier performs comparably (k=3: ARI 0.358,
  silhouette 0.152) but covers only 41 of 44 countries for no material
  gain — CORE is preferred so downstream stages get full universe
  coverage. `configs/params.yaml: stage1_clustering.chosen_algorithm/
  chosen_tier/chosen_k` = `kmeans`/`core`/`3`.

**DM/EM validation and disagreements (§4.2.3).** Overall full-sample ARI
0.377 (chosen combo); per-quarter ARI ranges 0.007-0.688, mean 0.381
(`data/processed/stage1_dmem_ari_by_quarter.csv`) — confirms the panel
*is* quarter-structured and validation must be (and is) computed
per-rebalancing-date, not once on the whole sample. The disagreement list
(`data/processed/stage1_dmem_disagreements.csv`, 1,139 rows) reproduces
exactly the kind of boundary case thesis §4.2.3 expects: Poland, Chile,
Czech Republic, South Africa, Malaysia, Vietnam, and Kazakhstan appear
repeatedly in `core-eligible` (the "stable EM" case §4.2.3 names by name),
while Greece, Italy, Japan, Portugal, and the UK appear repeatedly in
`satellite-candidate` — including as early as 2006, **before** the
2010-2012 crisis, which is a genuinely interesting early-warning signal
worth pursuing in §6.1/§6.4 once ratings data exists to test it formally
against actual downgrade timing (§4.2.4, still blocked — see below).

**Walk-forward output (§4.2.5).** `data/processed/stage1_risk_labels.parquet`
— one row per (country, rebal_date) with `risk_label` (`core-eligible` /
`excluded` / `satellite-candidate` / `insufficient_data`),
`raw_cluster_label`, and diagnostic columns (`n_features_observed`,
`training_window_start/end/n_rows`). HDBSCAN noise points and any
predicted label unseen in a given date's training fit are both mapped to
`excluded` — an intentional semantic fit (§4.2.5 defines `excluded` as
"too uncertain for either sleeve," which is exactly what a density-noise
or unseen-cluster point is), not an approximation. `insufficient_data`
is correctly 100% of 2005 and most of 2006 (before macro fundamentals are
publishable at all — see Macro data acquisition's publication-lag
section) and 0% from 2007 onward. Label counts: `excluded` 1,529,
`satellite-candidate` 1,239, `core-eligible` 664, `insufficient_data`
264. The residual regime-sensitivity flagged above shows up here as
`core-eligible` being 0 for several consecutive quarters spanning
2009-2017 — plausibly a real signal (in a sustained global low-rate/crisis
era, no country may look unambiguously low-risk relative to the model's
learned notion of "calm regime"), but flagged rather than asserted, since
it's confounded with the known residual global-feature effect.

**§4.2.4 (lead/lag vs. ratings) is intentionally not built.** It's
blocked on real ratings data (issue #3, 0/44 countries collected as of
this writing — see "Ratings data acquisition" above). The expected
interface is stubbed at `src/stage1_clustering/ratings_leadlag_stub.py`
(`compute_lead_lag()`, raises `NotImplementedError`) with the full
expected input/output schema documented in its docstring, including a
flagged follow-up: the paired t-test thesis §1.5/H1 describes needs a
*continuous* risk score, not just the categorical `risk_label`, so
`build_risk_labels.py` will need a scoring extension (e.g. distance to
the nearest low-risk centroid) before §4.2.4 can actually run — not solved
now, since there's nothing to validate it against yet.

**Leakage check.** `test_lag_rules.py` has two Stage-1-clustering-specific
checks: a structural check that every row's `training_window_end` equals
its own `rebal_date` (never later), and a real truncation-invariance
check — it re-runs `build_risk_labels.label_panel()` on the feature matrix
truncated to a mid-sample cutoff date and asserts the labels for dates
<= cutoff are byte-identical to the full-panel run's stored output. Since
K-Means is refit fresh at every date from only `rebal_date <= date` rows
with a fixed `random_state`, any future-data leak (via imputation stats,
scaling stats, or the cluster fit itself) would change the truncated run's
labels — an exact match is therefore the right bar, not a tolerance, and
both checks currently pass.

## Stage 2 signal (thesis §4.3.1-4.3.5 — settled facts)
Built on `src/stage2_signal/`. Operates only on the EM subset of Stage 1's
`satellite-candidate` output (`dm_em_flag == "EM" and risk_label ==
"satellite-candidate"` in `stage1_risk_labels.parquet`) — deliberately
excludes the occasional DM row that lands in `satellite-candidate` under
Stage 1's documented residual global-feature regime artifact (see "Stage 1
clustering" above), since Stage 2 is scoped to the EM universe per thesis
Ch.1/§4.4.1.

**Data gap confirmed before building, not assumed away.** No explicit
coupon-rate/cashflow field exists anywhere in the raw bond pull (11 fields
total — confirmed against `bond_data_pull_reconstructed.py`'s own field
list) — the bond CSVs are generic benchmark composites (`XX10YT=RR` RICs),
not individual fixed-coupon issues with a cashflow schedule. Thesis
§4.3.2's "excess total return (price return + coupon)" is therefore **not
constructible as a true coupon-inclusive total return**. What's built
instead, flagged per row rather than silently presented as equivalent
(`price_field_used`, `has_income_component` columns in
`stage2_signal_panel.parquet`):
- Where `DIRTY_PRC` (embeds accrued interest) is available, its
  quarter-over-quarter return is the closest available proxy to total
  return — `has_income_component=True`. 231/554 rows.
- Where only `CLEAN_PRC`, `MID_PRICE`, or a BID/ASK-derived synthetic mid
  is available, the return is a pure price-return proxy with **no income
  component at all** — `has_income_component=False`. 323/554 rows. This
  understates true total return, more severely for higher-coupon
  (typically higher-risk) EM sovereigns — a real, structural bias worth
  citing in Appendix B alongside the ZSPREAD-vs-swap-curve caveat.
- Price field priority (`configs/params.yaml:
  stage2_signal.price_field_priority`): `DIRTY_PRC > CLEAN_PRC >
  MID_PRICE > synthetic_mid ((BID+ASK)/2) > BID`. The last two fallbacks
  exist specifically for Kazakhstan and Morocco, the 2 EM countries with
  no `MID_PRICE`/`CLEAN_PRC` column at all (both have BID at ~99-100%,
  ASK at 74-100%) — without this fallback those 2 of 26 EM countries would
  be excluded from Stage 2 entirely; with it, all 26 get a price-based
  target.
- **Also confirmed missing before this build**: no 3-month US T-bill
  series (needed for the "excess ... over the 3-month US T-bill" risk-free
  leg) was pulled anywhere in the repo. Closed by adding `DGS3MO` to
  `macro_pull.py`'s `FRED_SERIES` (key-free, same pattern as every other
  FRED series — see "Macro data acquisition" above), not approximated
  from `us_10y`/`us_2y`.

**Feature set is deliberately narrower than reusing Stage 1's whole
feature list** — filtered to thesis §3.3's Group A/B/C table entries
marked Stage "2" or "1 & 2", not "1" only, the same discipline Stage 1
applied when it dropped `vix`/`dxy_proxy`. `configs/params.yaml:
stage2_signal.model_features` (14 features): `yield_spread_bps`, `mom_1m`/
`mom_3m`/`mom_12m` (price-return momentum, computed from daily prices via
a bounded as-of lookback so a gap in a country's price history never
silently reaches back further than intended), `carry` (proxy yield —
`us_10y + yield_spread_bps/100`, since real YTM is DM-only, see "Data
acquisition status" — minus the 3m T-bill; a documented approximation),
`spread_zscore_52w` (trailing 52-week z-score of daily `ZSPREAD`),
`debt_gdp`, `fiscal_bal_gdp`, `cpi_inflation`, `real_gdp_growth`, `us_10y`,
`curve_slope`, `vix`, `dxy_proxy`. Notably **excludes**, despite being
available in Stage 1's parquet: `mod_duration`/`convexity` (Group A, "1"
only), `current_acct_gdp`/`fx_reserves_mo`/`political_stability` (Group B,
"1" only). `cds_5y` and `cds_bond_basis` are computed and kept in the
output panel for inspection but excluded from `model_features` — `INT_CDS`
is essentially DM-only (see "Data acquisition status"), so both columns
are ~99% missing within the EM satellite population specifically (worse
than the ~82% missing seen in Stage 1's broader extended-tier check),
same reasoning Stage 1 used to exclude `cds_5y` from clustering.

**Population size is the binding constraint, not feature richness.**
Confirmed before going deep on any one algorithm, per the standing
instruction to check this early: Stage 1's `satellite-candidate` tier has
EM rows in only 65 of 84 quarters, median 4 / mean 8.5 countries per
quarter (`stage1_risk_labels.parquet`) — a small-N walk-forward setting by
construction, not a large backtest. Within that population, market-based
features are 49-64% missing (worst: `carry` 63.5%, `spread_zscore_52w`
61.0%, `yield_spread_bps` 60.5% — driven by the same ZSPREAD-sparse EM
countries flagged in "Stage 1 feature matrix" skewing disproportionately
into the highest-risk tier) versus 0% for the 4 macro fundamentals. Model
quality is therefore bounded by sample size and market-feature sparsity,
not by an absence of a feature-construction path — the pipeline is real
and leakage-safe, but small-N noise is a first-order caveat on every
result below, not a footnote.

**Model selection (§4.3.3) — actual walk-forward results, not assumption.**
`model_comparison.py` refits LASSO / Random Forest / XGBoost at every
rebalancing date (classification framing: L1-penalized logistic
regression as LASSO's classification analogue; regression framing: LASSO
proper) using only rows whose target is already realized as of that date,
then evaluates pooled out-of-sample predictions across 52 folds (of 65
quarters — the rest don't clear `min_training_rows=20` or the
sufficient-feature-coverage bar):

| Framing | Model | Metric | Value |
|---|---|---|---|
| Classification | lasso_logistic | AUC | **0.560** |
| Classification | random_forest | AUC | 0.546 |
| Classification | xgboost | AUC | 0.550 |
| Regression | lasso | mean IC | **+0.076** (t=0.83, one-sided p=0.205) |
| Regression | random_forest | mean IC | -0.168 (negative) |
| Regression | xgboost | mean IC | -0.261 (negative) |

**LASSO wins both framings** — not a Stage-1-style default choice, the
more flexible models measurably lost. Read this as a small-sample effect,
not evidence that non-linear structure doesn't exist in EM returns: with
median ~4-8 test rows per fold, Random Forest/XGBoost overfit each
per-quarter refit (mean IC goes *negative*, worse than a naive constant
prediction) while LASSO's linear regularization generalizes better under
low-N conditions — the same "simpler model wins" pattern as Stage 1's GMM/
HDBSCAN underperforming K-Means, for an analogous reason (the fancier
model's flexibility becomes a liability, not an asset, given what the data
can actually support). Per H2's own stated bar (thesis §1.5: IC > 0.05
*and* p < 0.05), **H2 is not rejected by this result** — mean IC (0.076)
clears the economic-significance threshold but p=0.205 does not clear the
statistical-significance one. Reported as a genuine, non-forced empirical
finding, not adjusted to fit the hypothesis. `configs/params.yaml:
stage2_signal.chosen_model_classification/chosen_model_regression` =
`lasso_logistic`/`lasso`.

**Feature importance (§4.3.4) — SHAP, with an important caveat.**
`feature_importance.py` fits the chosen LASSO regression model on the full
target-realized sample (274 rows) as a diagnostic (not a walk-forward
output — same "diagnostic vs production" split as Stage 1's
`algorithm_comparison.py` vs `build_risk_labels.py`). At LASSO's
configured `alpha=0.01` (confirmed close to the cross-validated optimum,
`LassoCV` selects `alpha≈0.0075` and produces the same sparsity pattern —
not an artifact of an arbitrarily strong fixed penalty), **only 3 of 14
features survive shrinkage: `cpi_inflation`, `fiscal_bal_gdp`,
`real_gdp_growth`** — all macro fundamentals. Every market-based feature
(`yield_spread_bps`, momentum, `carry`, `spread_zscore_52w`) and every
global factor (`us_10y`, `curve_slope`, `vix`, `dxy_proxy`) is shrunk to
exactly zero. `feature_importance.py`'s own output carries a printed
caveat line flagging that market-based features are 49-64% missing in
this population versus 0% for the macro fundamentals — **that hedge
("plausibly just a data-richness artifact") does not stand unqualified**;
see the two diagnostics immediately below, run specifically to test it,
which point the other way.

**Two diagnostics on the power-vs-absence question (2026-08-11,
exploratory, not part of the tracked pipeline).** The natural objection to
every result above — the weak AUC (0.560), the IC that misses H2's p<0.05
bar (p=0.205), and the SHAP result — is that Stage 1's
`satellite-candidate` gate leaves too few rows per quarter (median 4-8) to
detect a real premium, i.e. a statistical-power problem rather than an
absence of one. Two scratch diagnostics (not committed — exploratory
scripts only, reusing `stage2_utils` primitives and the identical feature
set/model config, no re-tuning) tested this directly:
1. **Split the real pipeline's existing 52 walk-forward folds by quarter
   population size** (`n_test`, already stored per fold in
   `stage2_model_comparison.csv` — no re-fitting needed). Better-populated
   quarters do NOT show a stronger signal: `n_test>=8` (8 folds, 99 pooled
   obs) gives mean IC **-0.004** vs the full sample's +0.076; `n_test>=15`
   (2 folds, 38 obs) gives +0.085, no clean monotonic strengthening with
   population size. (These sub-splits are themselves only 2-8 folds, so
   limited standalone power — the direction, not the magnitude, is the
   informative part.)
2. **Re-ran the identical target/feature construction and LASSO/RF/XGBoost
   models on all 26 EM countries at every rebalancing date**, not gated by
   Stage 1's `satellite-candidate` tier — 72 folds, ~14-15 names/quarter
   median, 1,100 pooled test observations (4.4x the real pipeline's 251).
   If the null were a power problem, this should show a materially
   stronger signal. It does not: LASSO regression mean IC goes **negative**
   (-0.092, one-sided p=0.941 — the opposite direction from H2), Random
   Forest also negative (-0.027), XGBoost weakly positive but
   non-significant (+0.019, p=0.292). Classification AUC for all three
   models collapses to **0.48-0.50** — indistinguishable from chance,
   despite 4.4x the observations. This AUC collapse is the single
   strongest piece of evidence here, since composition (see caveat below)
   affects IC's sign/magnitude more plausibly than it affects a
   classifier's discriminative power dropping to a coin flip.

**Reading, and what it does and doesn't establish**: both diagnostics
point away from "insufficient power" and toward "this specification
doesn't recover a detectable premium" — a narrower and more defensible
claim than "no EM excess-return premium exists." The satellite-only
pipeline's +0.076 IC is more parsimoniously read as noise in a small,
high-risk-skewed subsample than as a real effect masked by low power.
**Composition caveat (diagnostic 1 specifically)**: scoring the full EM
universe isn't a clean "same population, more data" scale-up — it also
dilutes toward calmer, lower-dispersion EM countries Stage 1 never flags
as high-risk, so a weaker IC there is *consistent with* a power story
without fully ruling it out on population-composition grounds alone. The
AUC-to-0.50 result is less vulnerable to this composition objection than
the IC numbers are. **Also record explicitly**: both diagnostics reused
the production feature set and fixed hyperparameters (including LASSO's
`alpha=0.01`) with no re-tuning for the different population size/
composition — so precisely calibrated, this is evidence that *this*
feature set + these three fixed-hyperparameter models don't recover a
premium, not a general claim that no premium is recoverable by any
specification. That distinction should carry through directly into how
§6.2 and §7.4 (future work — richer market features, re-tuned
hyperparameters, alternative EM universes) characterize the result.

**H2 multi-horizon robustness check (§2.4, §2.8) — pre-registered, run,
0 of 9 regression combinations clear the bar.** The quarterly target
horizon was originally chosen to match rebalancing frequency (§4.4.3),
not derived from theory about where sovereign return predictability
should appear — §2.4's factor literature (Ilmanen 1995; Koijen et al.
2018; Asness, Moskowitz & Pedersen 2013) spans 1-12 months. Committed to
the protocol in `state.md` (dated, committed *before* running, so the
result can't be read as a post-hoc search) then ran
`src/stage2_signal/multi_horizon_robustness.py`: same satellite-candidate
population and features, same fixed model hyperparameters (no re-tuning),
target horizon swapped to monthly (30d) and semi-annual (182d) alongside
the existing quarterly (~91d, reused as-is). All three reported
unconditionally, per §2.8 (Harvey, Liu & Zhu) applied to Stage 2's own
testing:

| Horizon | Model | Regression mean IC | one-sided p | Classification AUC |
|---|---|---|---|---|
| Monthly | lasso | +0.0015 | 0.495 | 0.617 |
| Monthly | random_forest | -0.0235 | 0.606 | 0.590 |
| Monthly | xgboost | -0.0422 | 0.682 | 0.600 |
| Quarterly | lasso | +0.0758 | 0.205 | 0.560 |
| Quarterly | random_forest | -0.1675 | 0.965 | 0.546 |
| Quarterly | xgboost | -0.2613 | 1.000 | 0.550 |
| Semi-annual | lasso | -0.0487 | 0.714 | 0.467 |
| Semi-annual | random_forest | -0.0226 | 0.589 | 0.496 |
| Semi-annual | xgboost | -0.1410 | 0.940 | 0.442 |

**0 of 9 regression combinations clear H2's bar** (IC>0.05 and p<0.05) —
quarterly/LASSO remains the closest (+0.076, p=0.205); monthly is
essentially flat (+0.0015, p=0.495) rather than stronger; semi-annual
turns negative (-0.049, p=0.714) with AUC (0.467) below chance. Since
none of the 9 tests reach significance even *before* any multiple-testing
correction, Harvey/Liu/Zhu-style correction (needed when something looks
significant across a family of tests and you must ask if it's real)
isn't the operative concern here — this is a clean, uncorrected null
across the whole pre-registered family, a *stronger* form of "H2 not
rejected" than the single-horizon result alone, and it closes off horizon
choice as an alternative explanation for the quarterly null.

**One flagged, deliberately not-promoted observation**: monthly/LASSO's
classification AUC (0.617) is the highest AUC seen anywhere in Stage 2's
full investigation (quarterly 0.560; the full-EM-universe power
diagnostic's best was ~0.50). Recorded as a §7.4 future-work lead, not
folded into the H2 conclusion — thesis §1.5's H2 test is defined via the
regression/IC framing only, no significance threshold was ever
pre-specified for AUC, and with 9 combinations now in play, treating one
unvalidated AUC number as a finding would be exactly the kind of
post-hoc mining §2.8 warns against. A monthly-horizon,
classification-specific follow-up would need its own pre-registration.

**Output (§4.3.5).** `data/processed/stage2_return_signals.parquet` — one
row per (country, rebal_date) with `predicted_excess_return` (continuous,
the primary ranking signal), `predicted_prob_positive` (classification
framing, secondary diagnostic), `rank_within_date`, and `top_5`/`top_10`/
`top_15` boolean selection flags (`configs/params.yaml:
stage2_signal.top_n_options`) — all three sensitivity levels built, not
one hardcoded N. `signal_status` is `"scored"` (483/554 rows, 57/65
quarters) or `"insufficient_data"` (mirrors Stage 1's label, same
semantic: too little realized-target training history yet). A quarter can
have fewer scored countries than a given N (e.g. the final quarter,
2025-12-31, has only 2 EM satellite-candidates) — `n_scored_within_date`
records this so a downstream consumer never silently assumes a full N.

**Leakage check — Stage-2-specific, one quarter stricter than Stage 1's.**
Because the target itself is a forward `(t, t+1]` return, a row is
eligible for training a model used to predict at date `t` only if BOTH its
features are knowable by `t` (inherited from Stage 1's already lag-safe
inputs) **and** its target is already realized (`target_period_end <=
t`) — `stage2_utils.build_expanding_train_mask`. `test_lag_rules.py` has
three Stage-2 checks: a structural check that `target_period_end` is
always exactly one quarter after `rebal_date`, a structural check that
`training_window_max_target_period_end` (recorded per output row) never
exceeds that row's own `rebal_date`, and a real truncation-invariance
check mirroring Stage 1's — re-running `build_return_signals.score_panel()`
on the panel truncated to a mid-sample cutoff (quarter 50 of 65) and
asserting predictions for **every** date <= cutoff (not just the cutoff
itself — the exact gap Stage 1's equivalent test's docstring flags as a
real one caught and fixed there) are identical to the full-panel run.
LASSO/L1-logistic are deterministic given a fixed `random_state`, so an
exact match (via `np.isclose(..., equal_nan=True)` to handle NaN-vs-NaN
positions) is the right bar. All three checks currently pass.

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
- **Push after every commit** unless there's a specific reason not to
  (e.g. a commit that's intentionally part of a larger in-progress
  change, or the user says otherwise for that instance) — don't let
  commits sit local-only waiting to be asked for. This repo has no CI or
  collaborators to conflict with, so there's no cost to pushing
  immediately, and unpushed commits have previously piled up
  (12 at once, 2026-08-12) purely from not doing this by default.
