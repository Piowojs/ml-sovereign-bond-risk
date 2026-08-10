# Project State Log

A running, chronological record of what's been done, what's open, and the
reasoning behind key decisions — kept separate from `CLAUDE.md`, which is
operational guidance for working in this repo, not a history of how it got
that way. Meant to be the primary source when writing the thesis's methods
sections and Appendix A (reproducibility) later, so entries favor clarity
and rationale over brevity.

**Convention**: newest entries first within "Chronological log". "Open
items" is a living section, edited in place as items resolve — it is not
itself chronological. Every entry should be updated (open items) or
appended to (chronological log) as part of normal workflow, not written up
after the fact from memory.

---

## Open items (as of 2026-08-10)

| Item | Blocks | Whose action | Status |
|---|---|---|---|
| Manually collect per-country rating-action history into `data/raw/ratings/manual/<Country>.csv` | §4.2.3, §4.2.4, RQ1/H1 | User (transcription from countryeconomy.com / agency IR pages) | Not started — pipeline ready, 0/44 countries collected |
| §4.2.4 lead/lag analysis (`ratings_leadlag_stub.py`) | §4.2.4, RQ1/H1 | Blocked on the ratings item above; also needs `build_risk_labels.py` extended to emit a continuous risk score, not just the categorical tier (see CLAUDE.md "Stage 1 clustering") | Interface stubbed, not implemented |
| Residual global-regime sensitivity in Stage 1 clustering (`core-eligible` = 0 for several consecutive quarters, 2009-2017) | §5.5 candidate robustness check; not blocking Stage 3/4 | Open — see CLAUDE.md "Stage 1 clustering" for the full diagnosis (us_10y/curve_slope are global-only features, thesis §3.3 keeps them in Stage 1 regardless) | Documented, not fixed further without a methodology-level call to override the thesis's own feature-group spec |
| Execution-verify `bond_data_pull_reconstructed.py` (does it actually run/chunk/return data as designed) | Appendix A reproducibility only — not blocking, since existing bond data already feeds Stage 1 | User (requires a session on the university-library Windows PC with Refinitiv Workspace) | Not started |
| CDS data (`data/raw/cds/`) never successfully pulled | Nothing currently — Stage 1 extended tier gates on duration/convexity, not CDS (see CLAUDE.md) | Would also require the library-PC session if pursued | Open, not currently prioritized |
| `docs/thesis_outline_sovereign.md` §1.4 still says "2005–2023"; actual pipeline uses 2005–2025 | Consistency of the written thesis, not the code | User (thesis text edit) | Open, tracked separately from code |
| Stage 2/3/4 (`src/stage2_signal/`, `stage3_portfolio/`, `stage4_evaluation/`) not started | Everything downstream of Stage 1 | — | Not started — Stage 1 (feature matrix + clustering + walk-forward labels) is now fully built; this is the next major phase |

---

## Chronological log

### 2026-08-10 — Stage 1 unsupervised sovereign risk classification built (§4.2.1-4.2.3, §4.2.5)
**What**: Built the actual clustering step on top of the Stage 1 feature
matrix (`3c11d87`) — `src/stage1_clustering/clustering_utils.py` (shared
primitives), `algorithm_comparison.py` (§4.2.1-4.2.3, full-sample
diagnostic: K-Means/GMM/HDBSCAN x CORE/EXTENDED, k=2-8, silhouette/BIC/AIC,
ARI vs DM/EM), and `build_risk_labels.py` (§4.2.5, the actual
point-in-time-safe production pipeline: refits the chosen model at every
rebalancing date using only `rebal_date <= date` rows). `§4.2.4` (lead/lag
vs ratings) stubbed only — blocked on issue #3's ratings data, see below.
Full write-up of every decision (feature set, imputation, algorithm/k
selection with real numbers, DM/EM disagreement highlights, leakage
tests) is in `CLAUDE.md`'s new "Stage 1 clustering" section — not
duplicated here in full, only the two findings worth flagging at the
narrative level:

**Finding 1 — a real bug caught by data, not just intuition**: the
initial version of this pipeline followed CLAUDE.md's Group C description
loosely and included `vix`/`dxy_proxy` in the Stage 1 clustering feature
set. Running it produced an immediately suspicious result: entire
quarters (2008-2015) had **zero** countries classified `core-eligible`,
and other quarters (2023, 2025) had **zero** in `excluded`/
`satellite-candidate` — every country in the world moving in lockstep by
quarter. Root cause: VIX/US-10y/DXY are identical across all 44 countries
within a given quarter (zero cross-sectional variance, all their variance
is across time), so in a full-sample pooled fit they let global regime
dominate the distance metric over actual country differentiation.
Rechecking thesis §3.3's Group C table confirmed VIX and DXY are scoped
to Stage 2 only ("2"), not Stage 1 ("1 & 2") — the original feature set
was a misread of the thesis's own spec, not a defensible design choice.
Removing them raised full-sample ARI vs DM/EM from 0.258 to 0.377 (k=3,
core, K-Means) and every year in the sample now shows a genuine mix of
all three tiers. A weaker residual version of the same effect persists
(`us_10y`/`curve_slope` are still global-only and the thesis keeps them in
Stage 1 regardless) — flagged in the open items table above as a §5.5
robustness-check candidate, not silently fixed further.

**Finding 2 — HDBSCAN doesn't work on this feature set**: swept
`min_cluster_size` at 1%/2%/5% of sample size on both tiers. At 2%/5% it
finds zero clusters (100% noise). At 1% it "succeeds" with the best raw
silhouette of any combo tried (0.33) but ARI vs DM/EM of 0.018
(near-random) — inspection showed why: one 3,153-row catch-all cluster, a
62-row all-DM outlier pocket, and 261 scattered noise points. It isolates
density outliers, not a risk stratification. Documented rather than
forced to "work" — a legitimate negative result for §4.2.1's algorithm
comparison, not a bug in the implementation.

**Algorithm/k choice**: K-Means, CORE tier, k=3 — chosen because it's the
best ARI among all k=3 combinations tried (0.377, vs GMM-core-k3's 0.296),
its silhouette is statistically indistinguishable from K-Means-core's
best k (flat 0.13-0.17 across k=2-8, no real elbow — itself a citable
§4.2.1/§6.1 finding that sovereign risk doesn't form tightly separated
clusters here), and unlike k=2 (which has the single highest raw ARI,
0.554) it actually supports the thesis's 3-tier output structure — k=2
structurally can never populate the `excluded` middle tier. EXTENDED tier
performs comparably (k=3 ARI 0.358) but covers 3 fewer countries for no
material gain, so CORE was preferred for full-universe coverage
downstream.

**DM/EM disagreement highlights** (from `stage1_dmem_disagreements.csv`,
full-sample diagnostic fit): Poland, Chile, Czech Republic, South Africa,
Malaysia, Vietnam, and Kazakhstan repeatedly land in `core-eligible`
(matches thesis §4.2.3's own named "stable EM" examples exactly). Greece,
Italy, Japan, Portugal, and the UK repeatedly land in
`satellite-candidate`, including as early as 2006 — before the 2010-2012
crisis. That's a genuinely interesting early-warning result worth
pursuing in §6.1/§6.4, but formal validation (does it precede the actual
rating downgrade?) needs §4.2.4, which is blocked on real ratings data.

**Leakage check**: `test_lag_rules.py` extended with a structural check
(`training_window_end == rebal_date` for every row) and a real
truncation-invariance test — re-runs `build_risk_labels.label_panel()` on
the feature matrix truncated to a mid-sample cutoff and asserts exact
label agreement with the full-panel run for dates <= cutoff. Both pass.
All 7 checks in `test_lag_rules.py` pass as of this entry.

**Environment note**: `scikit-learn` and `hdbscan` were listed in
`requirements.txt` already but not actually installed in this
environment — installed via `pip install scikit-learn hdbscan` as part of
this session (sklearn 1.9.0, hdbscan installed cleanly, no dependency
conflicts).

**Open**: §4.2.4 still blocked on issue #3 (ratings — see below); also
needs a continuous risk score (not just the categorical tier) added to
`build_risk_labels.py` before it can implement thesis §1.5's paired
t-test, which isn't solved yet either. Tracked in a new GitHub issue
(Stage 1 clustering, predecessor: issue #2 — Stage 1 feature matrix).

Commit: (pending, this session) · Issue: #4 (opened and closed this
session, references #2 as predecessor)

---

### 2026-08-10 — Ratings sourcing research + manual-ingestion pipeline built (issue #3)
**What**: Researched free/public alternatives to `TR.IssuerRating` for
sovereign rating *history* (not snapshot): Damodaran's NYU Stern country
risk dataset, Trading Economics, and countryeconomy.com. Conclusion: none
give a free, automatable, citable historical pull —
- Damodaran's `ctryprem.xlsx` is a current-snapshot table only (last
  checked: updated January 2026), no time series.
- Trading Economics historical ratings require a paid API tier; the free
  site shows current ratings only.
- countryeconomy.com has real dated rating-action history (date, agency,
  rating, outlook) back to the 1990s for many countries — the best free
  option found — but it's a third-party aggregator, coverage depth is
  uneven by country/agency, and its Terms of Use should be checked before
  any bulk/automated scraping.

Given no free source is both historical and safely automatable, built
`src/data_acquisition/ingest_ratings.py` as a **manual-file normalizer**,
not a scraper: it reads whatever per-country CSVs the user has manually
transcribed (from countryeconomy.com or agency press pages) out of
`data/raw/ratings/manual/`, validates them (known agencies, mappable
ratings via a copy of the old `RATING_MAP` ordinal scale), infers
upgrade/downgrade/affirm actions chronologically where left blank, and
writes a consolidated `data/processed/ratings_panel.csv`. Verified against
a synthetic test file (Poland, 5 rows spanning three agencies) — rating
mapping, action inference, and the 0-lag `available_date` all behaved as
designed; test file removed after verification, no real data collected.

Also added: `configs/params.yaml: ratings_ingestion` section (raw dir,
output path, `lag_days: 0`, valid agencies) and
`test_lag_rules.py::test_ratings_available_date_has_zero_lag`, which
skips cleanly while `ratings_panel.csv` is empty and will start asserting
for real once rows exist.

**Why manual rather than scripted**: `TR.IssuerRating` (Refinitiv) was
already a confirmed dead end (SDate/EDate ignored, snapshot only) before
this session. Rather than force a weak free-API substitute or write an
automated scraper against a third-party site's ToS, the pipeline was
built to accept whatever manually-collected data arrives — matching how
the user already intended to fill this gap — and to make partial,
incremental coverage a first-class case (a country with no file yet is
just absent from the output, not an error).

**Why zero lag for ratings, unlike macro's 3–6 month lag**: rating
actions are same-day public announcements (agency press releases), so
there's no publication-lag mechanism to model — `available_date = date`
by construction. This is a different point-in-time assumption from macro
fundamentals (lagged) and from bond market data (also zero-lag, but for a
different reason — market prices are observed same-day, not announced).

**Open**: 0/44 countries actually collected. This is the blocking gap for
§4.2.3/§4.2.4 and RQ1/H1, not the pipeline itself.

Commit: (pending, this session) · Issue: #3

---

### 2026-08-10 — Bond data provenance gap resolved; reconstructed pull script added
**What**: Discovered that `eikon_sovereign_pull_deprecated.py` (the only
pull script previously in the repo) requests a field set that doesn't
overlap with the columns actually present in `data/raw/bonds/*.csv` —
confirmed by diffing its field list against on-disk columns. The real
pull that produced the existing data was an untracked script,
`data_pull.py`, run 2026-06-08 on a university-library Windows PC — not
recoverable, but its provenance was reconstructed from
`data/logs/pull_log.txt`'s 2026-06-08 traceback (real file path + RDP
endpoint URLs), confirming it used `lseg-data` against RDP/EDP endpoints,
not the old `eikon` package.

Replaced the dead script's role with
`src/data_acquisition/bond_data_pull_reconstructed.py` — a design-level
reconstruction built to match the on-disk data's structure exactly, but
**not execution-verified** (this environment has no Refinitiv Workspace
access; that requires the same library PC). One flagged mismatch:
YLDTOMAT licence scope (see below). Old script renamed to
`eikon_sovereign_pull_deprecated.py` with a docstring banner; kept only
for historical reference, not to be run.

**Correction to a previously-documented (incorrect) claim**: a full
44-country coverage check found `YLDTOMAT` (yield to maturity) is present
for exactly 5 countries — Germany, Japan, Switzerland, UK, US — populated
98.5–100%, and absent (column doesn't exist) for all other 39, including
clear DM sovereigns like Australia, Canada, France, Italy. This is a
licence/entitlement boundary that happens to coincide with the pre-existing
`full_dm` coverage tier, **not** a DM-vs-EM split as previously assumed
and documented. Downstream code must check column presence per country,
never infer YLDTOMAT availability from DM/EM classification.

**Why this matters**: without resolving provenance, there was no way to
trust the existing `data/raw/bonds/` data enough to build Stage 1 on top
of it, or to know whether a real pull was still needed before Stage 2.
Conclusion: no further pull is needed — existing data already
successfully fed Stage 1 (see next entry, which happened one commit
earlier but is documented after this investigation resolved trust in the
underlying data). The open item is Appendix A reproducibility
documentation, not missing data.

Commit: `7ca9713` · related to CLAUDE.md "Data acquisition status" and
"Bond/CDS/ratings pull provenance" sections

---

### 2026-07-29 — Stage 1 country x quarter feature matrix built (core + extended tiers)
**What**: `src/stage1_clustering/build_feature_matrix.py` built, producing
`data/processed/stage1_feature_matrix_core.parquet` (44 countries, 3,696
rows) and `..._extended.parquet` (41 countries — 3 EM excluded on
duration/convexity coverage below the 0.7 threshold: Peru 54%, Hungary
64%, Colombia 66% — 3,444 rows). Both tiers exclude agency ratings, per
thesis design (ratings are a Stage 1 *validation target*, not a
clustering input).

**Key decisions**:
- `yield_spread_bps` sourced from raw `ZSPREAD`, not `BMK_SPD` —
  `BMK_SPD` is near-zero even for DM reserve-currency benchmarks
  themselves, making it useless cross-country. Validated against Greece's
  known 2012 crisis spike (quarter-end 2012-06-30: 2447.6bps, consistent
  with post-election spread easing).
- `ZSPREAD` is over the swap curve, not UST — flagged for Appendix B since
  it's not a drop-in match for thesis §3.3's Group A spec.
- Bond market fields treated as same-day-knowable (no publication lag),
  unlike macro fundamentals — quarter-end resampling uses last
  observation in-quarter, not mean.
- Macro columns joined via backward as-of merge
  (`available_date <= rebal_date`) — 0 rows dropped for
  `data_asof_ok=False` in either tier, by construction.
- Extended tier gated on `MOD_DURTN`/`CONVEXITY` coverage rather than CDS,
  since `INT_CDS` is essentially DM-only (only Egypt has meaningful EM CDS
  coverage, ~5%) — gating on CDS would collapse the extended tier to
  ~DM + Egypt.
- **Correction to a pre-implementation estimate**: expected only Peru to
  be excluded by the 0.7 threshold; actual run excluded 3 countries
  (Peru, Hungary, Colombia), giving 41 not 43 countries in the extended
  tier. Flagged as a candidate for the thesis's §5.5 sensitivity sweep.

Commit: `3c11d87` · issue #2 (Stage 1 feature matrix) closed by this work

---

### 2026-07-28 — Macro data acquisition pipeline built
**What**: `src/data_acquisition/macro_pull.py` built — pulls World Bank,
IMF WEO (fallback), and FRED (global) series for all 44 universe
countries, writes `data/raw/macro/macro_fundamentals.csv` (tidy long
format) and `coverage_report.csv`. All three APIs are key-free; explicitly
chose not to add `fredapi`/API-key plumbing once the key-free endpoints
were confirmed working.

**Key decisions**:
- World Bank primary, IMF WEO fallback per country-year cell, `source`
  column records which one actually supplied each value.
- Political stability lives in the WGI database (`source=3`,
  `GOV_WGI_PV.EST`), not the default WDI one — the plain `PV.EST` ID 404s
  under `source=3`.
- IMF DataMapper's per-country path filter is silently ignored
  server-side — script fetches once per indicator, filters client-side.
- `DTWEXBGS` (Trade-Weighted USD Index: Broad) used as a documented proxy
  for DXY, since ICE's real DXY is proprietary and not on FRED — this
  series only starts 2006-01-02, so 2005 has no USD-index observation at
  all (flagged in `macro_missing.txt`, not silently absent).
- Publication lag modeled explicitly: annual WB/IMF series get
  `available_date = period_end (Dec 31) + lag_months` (6 by default);
  FRED daily series get `+lag_days_fred` (1 day). This is what
  `test_lag_rules.py` checks.
- Two accepted, documented limitations: vintage/revision data (APIs serve
  current revised figures, not point-in-time-as-published), and a
  consolidation-level mismatch in the WB→IMF fallback pairs for debt/GDP
  and fiscal balance (central government vs general government).
- Coverage as of last full run: 0/312 country×series cells below the 50%
  threshold. Poland's `GC.DOD.TOTL.GD.ZS` is 100% IMF-fallback (entirely
  null from World Bank) — the one fully-degenerate cell.
- World Bank API flakiness (occasional timeouts/spurious 400s under rapid
  sequential requests) confirmed transient via manual retry — script
  retries 3x with backoff before logging a genuine miss.

Commit: `68aa99c`

---

### 2026-07-28 — CLAUDE.md moved to repo root; bias-prevention hook and lag-rules test scaffolded
**What**: `CLAUDE.md` consolidated to the repo root (removing a legacy
`docs/CLAUDE.md`), and `test_lag_rules.py` given its first real
assertions (previously a placeholder) — establishing the pattern every
later data-acquisition script would need to satisfy: no test-window
leakage, no available-date-before-period-date violations, and (later)
explicit publication-lag checks per source.

Commits: `84c2b45`, `01f7cfb`

---

### 2026-07-28 — Repo scaffolded
**What**: Initial project structure created — `src/` organized by thesis
stage (1:1 with thesis §4.2–§4.5), `configs/`, `data/`, `docs/`,
`notebooks/`, `CLAUDE.md`, and the full thesis outline doc
(`docs/thesis_outline_sovereign.md`) added as the canonical reference for
chapter structure, hypotheses, and data source specs. `.gitignore` added
before importing any real data (`data/raw/`, `data/logs/` excluded from
version control; `data/processed/` is tracked).

Commits: `a706f85`, `8ed3aac`

---

### 2026-06-03 — Initial commit
Repository created.

Commit: `81751aa`
