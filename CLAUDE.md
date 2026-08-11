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
  Stage 1 feature set — see that section). `stage2_signal/`,
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
    "Stage 1 clustering" below), and `ratings_ingestion`. Add new sections
    here as later stages need tunable parameters — never hardcode a
    hyperparameter in code.
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
- Run `test_lag_rules.py` after any change touching data loading, feature
  construction, clustering inputs, or backtesting logic —
  this is the project's core correctness check (see Bias-prevention rules).
  Includes a truncation-invariance leakage test for the Stage 1 walk-forward
  labeler (re-running it on a truncated panel and diffing against the
  full-panel output) — see "Stage 1 clustering" below.

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
  systematically omits them; CE's embedded-outlook and blank-rating
  (watch/under-review) quirks are cleaned up before comparison; agreeing
  (agency, month) rows from both sources collapse into one row preferring
  CE's exact date; genuinely disagreeing rows are written to
  `_reconciliation/<Country>_conflicts.csv`, never auto-resolved, and
  only enter the merged output once a matching row appears in
  `_reconciliation/<Country>_resolutions.csv` recording which source was
  chosen and why. See that script's docstring for the full policy and
  `state.md` for the worked Greece example (including two matching-logic
  bugs the real data caught and how they were fixed).
- **Status as of 2026-08-10**: pipeline built and verified against
  synthetic test files (mapping, action/outlook_change inference,
  duplicate-action detection, Scope rejection, and coverage logging all
  confirmed correct); **1/44 countries collected — Greece**, reconciled
  from both GE and CE sources via `reconcile_ratings_sources.py` (172
  rows, one genuine cross-source conflict found and resolved). Manually
  collecting and transcribing the remaining 43 per-country files is open,
  user-side work — see `state.md` for the full log, including a priority
  order for which countries to transcribe next, and issue #3 for
  tracking.

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
