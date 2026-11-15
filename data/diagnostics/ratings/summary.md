# ratings_v2 intake diagnostics — summary (2026-11-15)

Independent 44-country sovereign rating collection stored untouched in
`data/raw/ratings_v2/` (`ratings_history.csv` 2,610 rows ≤ 2025-12-31,
`coverage_report.csv`, `unresolved.md`, `excluded_source_rows.csv`).
Sources: countryeconomy.com, tradingeconomics.com (S&P only, currency
unstated), fxempire.com (last ~20 actions per country), Fitch's own 2011
sovereign-history table. **Not merged** into
`data/processed/ratings_panel.csv`; no Stage 1 labels regenerated, no
lead/lag computed — per `docs/stage1_h1_preregistration.md` (v0.3).
Produced by `diagnostics/ratings_v2_diagnostics.py`.

All ratings map cleanly onto the shared `RATING_MAP` ordinal scale
(0 unmappable rows). Row split: 1,512 FC_LT / 822 LC_LT / 276 S&P
currency-unspecified.

## (a) Sanity checks

- **Jumps > 4 notches**: 15 (`ratings_v2_sanity_jumps.csv`). All but one
  are default-entry/exit transitions (SD/RD ↔ exit rating: Greece 2012,
  Indonesia 2000/2002, Zambia 2020→2025, Sri Lanka 2022→2025) or the
  documented stale Portugal S&P-unspecified series (2013→2025). The one
  real problem: **Sri Lanka S&P FC_LT `A` on 2007-01-23** (8 notches to
  the next row).
- **Range outliers (|modified z| > 3.5)**: 4, all Sri Lanka
  (`ratings_v2_sanity_range_outliers.csv`) — three are genuine 2022
  default designations; the fourth is the same `A` row at z = −6.07.
- **Headline**: v2 **reproduces the known countryeconomy transcription
  error** already caught and corrected in the old panel via
  `_corrections.csv` (see state.md, Source factual-error tracking case
  5). v2's source for that row is countryeconomy — confirming the error
  originates at the aggregator, and that v2 inherits it uncorrected.
  Any future use of v2 must carry this correction over.
- **Single-source exposure**: 1,410 / 2,610 rows (54.0%) rest on one
  source (`ratings_v2_single_source.csv`) — same order as the old
  panel's 46% never-cross-validated share.

## (b) Pre-registration §5.1 currency tests (S&P unspecified rows)

- **Source test**: on S&P actions where the labelled FC_LT and LC_LT
  ratings differ on the same date, **35 of 35 tradingeconomics-backed
  rows carry the FC rating** (share 1.000 ≥ 0.95 → **pass**).
  Per-country breakdown in `ratings_v2_sp_source_test_by_country.csv`,
  row detail in `ratings_v2_sp_source_test_rows.csv`.
- **Continuity test** (`ratings_v2_sp_continuity_test.csv`): 38
  countries have unspecified rows; verdicts: 31
  `consistent_recorded_change` (the first FC row is the collector's own
  recorded change from the last unspecified rating), 1
  `consistent_equal`, 6 `no_unspecified_before_fc` (UK, France, Canada,
  Australia, Belgium, Sweden — nothing to bridge), **0 inconsistent**.
- → **All 38 countries with unspecified rows pass both tests**; their
  S&P unspecified rows qualify as FC_LT under §5.1.
- The superseded same-date overlap test would have had only **9
  (country, date) pairs** with both an unspecified and an FC_LT row —
  near-empty, confirming the replacement was necessary.

## (c) Comparison with the 13-country reconciled panel

Old panel 1,512 rows vs 685 v2 FC_LT rows for the same countries,
matched on country + agency + rating, dates within 3 days:

- **Matched 612** (609 exact-date, 3 at 1–3 days) —
  `ratings_v2_vs_panel_matched.csv`. Of these, **253 rest on
  countryeconomy in both collections** (flagged
  `both_rest_on_countryeconomy`) — those are NOT independent
  confirmations.
- **Disagreements 3** (`ratings_v2_vs_panel_disagreements.csv`):
  1. Sri Lanka S&P 2007-01-23: old (corrected) `B+` vs v2 `A` — the
     inherited countryeconomy error above.
  2. Zambia Moody's 2020-04: old `Ca-` (the documented GE
     transcription-artifact alias, numerically identical) vs v2 `Ca` —
     string-level only, not a real disagreement.
  3. Nigeria Moody's 2019-12: old (GE) `B3` vs v2 (fxempire) `B2` — a
     genuine 1-notch source disagreement, previously uncheckable
     (Nigeria's Moody's history is 100% GE-only in the old panel);
     needs a primary-source check.
- **Old-panel-only 897** (`..._old_only.csv`) — structurally expected:
  568 are affirmations and 154 outlook-only changes (v2 does not record
  affirmations), plus month-precision GE dates falling outside the
  3-day window.
- **v2-only 70** (`..._v2_only.csv`) — mostly fxempire-sourced recent
  actions and watch rows the manual transcriptions didn't carry.

## (d) Gap map (FC_LT coverage, 2004–2025, per country × agency × year)

`ratings_v2_gap_map.csv`, both variants:

| variant | complete | partial | missing |
|---|---|---|---|
| FC_LT only | 2,418 | 244 | 242 |
| FC_LT + passing S&P unspecified | 2,585 | 220 | 99 |

Adding the qualifying S&P unspecified rows repairs 143 missing
country-agency-years (mostly pre-2007/2011 S&P history that
countryeconomy only labels FC from ~2007–2011 onward) and 24 partial
ones. **486 cells remain non-complete in at least one variant**
(`ratings_v2_gap_blocking_cells.csv`), spread over 39 countries — these
are the cells that exclude downgrade events under §5.1's
4-preceding-quarters rule. Partial cells are driven by multi-notch
(≥3) consecutive jumps (the collector's own possible-gap rule) and the
documented stale Fitch tables ("no action found after …" in
`unresolved.md`, parsed per country/agency).

## (e) Downgrade-event counts (counts only — no scores)

Downgrade = `rating_numeric` worsening between consecutive FC_LT
actions, pooled across agencies, collapsed to ≤1 per country-quarter
(earliest date); initial = no collapsed event in the preceding 4
quarters:

| variant | collapsed country-quarter events | initial |
|---|---|---|
| FC_LT only | 212 | 102 |
| FC_LT + passing S&P unspecified | 238 | 109 |

Top event counts (fc_only): Turkey 13, Egypt 12, Greece 12, South
Africa 11, Italy/France/Zambia/Sri Lanka 10. Seven countries have zero
FC_LT downgrades 2000–2025: Australia, Czech Republic, Germany,
Indonesia, Norway, Sweden, Switzerland (Indonesia's defaults are in
the pre-2004 unspecified series only). Files:
`ratings_v2_events_fc_only.csv`, `ratings_v2_events_fc_plus_unspec.csv`,
`ratings_v2_event_counts.csv`.

## (f) Event survival under the gap rule + second-pass targets (added later on 2026-11-15)

Produced by `diagnostics/ratings_v2_event_survival.py`, on the FC_LT +
passing-S&P-unspecified variant throughout. A "gap" is a country ×
agency × year cell that is not `complete` under the same classification
as (d), computed over 2000–2025 so early events' lookback windows are
classifiable. The `initial` flag stays defined on the full collapsed
event set (actual downgrade history); the rules filter on top of it.

| rule | collapsed | initial | countries with ≥1 surviving initial |
|---|---|---|---|
| (i) no gap rule | 238 | 109 | 39 |
| (ii) pre-registration §5.1 (issuing agency) | 212 | 102 | 37 |
| (iii) strict (any of the 3 agencies) | 185 | 88 | 36 |

By-year detail in `ratings_v2_event_survival_by_year.csv`, per-event
flags in `ratings_v2_event_survival_events.csv`. The gap rule's cost is
concentrated where expected: 2000 is wiped out entirely (lookback into
pre-coverage years), and 2011–2012 (Eurozone crisis — multi-notch
possible-gap spans) plus 2008 lose the most under rule (iii)
(19→9 and 22→13 collapsed in 2011/2012). From ~2016 on the three rules
are nearly identical, so the rule choice mainly affects the crisis-era
sample. Even under the strict rule, 88 initial events across 36
countries remain — comfortably above the 13-country pilot's base.

**`second_pass_targets.csv`** (137 rows): one row per item a second
collection pass should resolve — 20 stale Fitch FC_LT tables ("no
action found after …" → 2025-12-31), 6 MISSING ACTION SUSPECTED cases,
38 multi-notch possible-gap spans (with both surrounding dates), 29
FC_LT series starting after 2004 whose first row is not marked as a new
rating (the big S&P FC-labelling gaps, 2004-01-01 → series start), the
2 known cross-collection problems (Nigeria Moody's 2019-12 B3-vs-B2;
Sri Lanka S&P 2007-01-23 `A`-for-`B+`), and 42 undated latest-rating
rows from `excluded_source_rows.csv` as hints for what the missing
action is (dateless, priority last). Priority ranks by
`n_events_affected` = rule-(iii)-excluded events whose event quarter or
4-quarter lookback overlaps the target span. Top of the list is Greece
(S&P 2011–2014 possible-gap span, 8 events affected; S&P pre-FC
history to 2011, 6; Fitch 2011 spans, 5 each).

Note: the user-facing count "62 rows … that are undated latest-rating
rows" splits as 42 undated latest-rating rows + 17 short-term/
provisional + 3 unrecognised strings; only the 42 undated ones are
hints and included.

## Notes

- `unresolved.md` references `excluded_source_rows.csv`; it was provided
  and is stored alongside the other three files (62 excluded source
  rows: undated latest-rating rows, short-term/provisional ratings in
  long-term columns, 3 unrecognised strings).
- The three aggregators (countryeconomy / tradingeconomics / fxempire)
  are counted as independent, but the collection itself flags this as
  unverified — `n_independent_sources` is an upper bound.
