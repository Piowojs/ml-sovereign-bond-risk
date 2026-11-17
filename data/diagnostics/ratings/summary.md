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

## (g) Second-pass ingest and candidate panel (added 2026-11-17)

Scope: counts and data construction only. No labels regenerated, no lead/lag,
return or risk score computed. Pre-registration v0.4 (commit abe6997) governs.
Everything below is reproducible with
`diagnostics/build_h1_candidate_panel.py` and
`diagnostics/second_pass_event_survival.py`; outputs are in
`data/diagnostics/ratings/second_pass/`.

### g.1 What was stored and built
- Second-pass files stored untouched (local-only, `data/raw/` is gitignored):
  `data/raw/ratings_v2_second_pass/{second_pass_actions.csv,
  second_pass_resolution.csv, second_pass_unresolved.md}`.
- Corrections (tracked): [`data/interim/_corrections_v2.csv`](../../interim/_corrections_v2.csv)
  — 9 rows, each with its evidence URL (5 remove_row, 3 correct_date,
  1 correct_rating); every row matched exactly one v2 row (a non-match stops
  the build). It supersedes the old per-country
  `Sri_Lanka_corrections.csv` finding for v2 (A -> B+ becomes a removal,
  because S&P shows no action at all on 2007-01-23). Nigeria Moody's 2019-12:
  v2 already carries B2 dated 2019-12-04, matching the second pass, so no
  correction row was needed (the old panel's B3 is simply not carried).
- Candidate panel: `data/interim/ratings_h1_candidate.csv`, **1,775 rows, 44
  countries, all three agencies, status CANDIDATE_NOT_FROZEN** on every row
  (see the sibling README). Provenance: 1,538 v2-only, 208 v2 + second pass
  (same action in both, ratings agree), 26 second-pass-only, 3 initial_state
  anchors from the second-pass resolution file. Second-pass input: 271 rows,
  33 LC_LT dropped (LC is descriptive only), 4 dated after 2025-12-31 dropped
  (Portugal Fitch 2026-03/2026-09, South Africa 2026-06, Sri Lanka Fitch
  2026-09), 234 FC rows used.
- S&P unspecified rows: section 5.1 tests re-run on the corrected v2 frame —
  source test passes (35/35 tradingeconomics-backed rows carry FC); continuity
  test: **37 of 38 countries qualify**. Sri Lanka now fails the continuity
  test only because the removed 2007-01-23 row carried the recorded-change
  note the test looks for; following the pre-registration literally, its
  unspecified rows stay excluded. Nothing is lost: all of them have a
  second-pass FC_LT counterpart and were merged into FC_LT rows.

### g.2 Dedupe, conflicts, probable duplicates
S&P FC_LT and unspecified rows share one key (iso3, agency, date); other
agencies key on (iso3, agency, FC_LT, date). Same rating -> one FC_LT row, all
sources listed.

**Same key, different rating (every case):**

| iso3 | agency | date | v2 | second pass | resolution |
|---|---|---|---|---|---|
| VNM | S&P | 2010-12-23 | BB (tradingeconomics, unspecified) | BB- (S&P history, agency) | second pass used; recorded as the correct_rating row in `_corrections_v2.csv`. The v2 2011-08-19 BB- row now repeats the rating (no letter change, not an event) |
| AUS | S&P | 2000-01-01 | FC_LT AA+ vs unspecified AA, both in v2 | — | inside v2; kept the FC_LT-labelled row (pre-2004, outside every test window) |

**Same rating within 3 days (probable duplicates, listed not merged; 27
pairs, none creates an event because the rating does not change):** full list
in `probable_duplicates.csv`. 22 are v2-vs-v2 (mostly one-day offsets, two
of three days); 5 involve a second-pass row: CHN S&P 2004-02-17/18, IDN S&P
2004-12-21/22, JPN S&P 2007-04-22/23, ROU S&P 2007-11-05/06, PRT S&P
2025-02-28/03-01. The earlier date drives any change, so the pre-registered
"earliest date" rule holds by construction.

### g.3 Removals: neighbouring rows (amendment 4)

| series | removed | before | after | verdict |
|---|---|---|---|---|
| GRC S&P FC | 2014-12-12 B | 2014-09-12 B (v2) | 2015-01-28 B (v2) | consistent |
| PRT Fitch FC | 2011-10-07 BBB- | 2011-04-01 BBB- (second pass) | 2011-11-24 BB+ (v2) | consistent |
| PHL S&P LC | 2009-08-17 BBB+ | 2006-02-09 BB+ (second pass) | 2013-05-02 BBB- (v2) | consistent (S&P: BB+ through 2010-11-12; v2 lacks the 2010-11 LC step, LC is not in the panel) |
| LKA S&P FC | 2007-01-23 A | 2006-04-26 B+ (second pass) | 2007-08-08 B+ (second pass) | consistent |
| LKA S&P LC | 2007-01-23 A | none | 2007-08-08 BB- outlook_change (second pass) | **FLAG: LC series left with no starting rating action, not patched** (LC not used in the H1 panel) |

### g.4 S&P Sovereign Ratings History (Jul 2021) cross-check
**Not performed: the URL returned HTTP 403 to both `curl` and the fetch tool,
so the table could not be parsed.** Substitute, clearly a proxy and not the
requested comparison: the 576 panel S&P rows dated up to 2021-06-30 were
checked against the second pass's own transcription of that table.
192 are confirmed (same date and rating in both), 377 lie outside any
transcribed window (unverified), and **7 are v2-only rows inside a
transcribed window**, all date offsets of an action the transcription lists:
CHN 2004-02-17 (S&P 02-18), ESP 2004-12-13 (S&P 12-03, 10 days), IDN
2004-12-21 (12-22), JPN 2007-04-22 (04-23), PAK 2008-12-09 (S&P 12-19, v2 10
days earlier), ROU 2007-11-06 (S&P 11-05), VNM 2011-08-19 (see g.2). None
changes a downgrade event (all are upgrades, outlook changes or repeats); not
applied. Detail: `sp_history_proxy_check.csv`.

### g.5 Gap map and event survival — strict any-agency rule, v0.4 window
Cell rule: a country x agency x year cell is complete when the **letter-rating
path is established**, outlook path may be unverified. Window: event quarter
plus the 4 preceding quarters (calendar-year cells). A >= 3-notch step
between consecutive rows is not a gap when a resolved/partly_resolved
second-pass row covers it (69 windows used); 8 stale-Fitch cutoffs lifted
(CHL, ESP, CZE, MEX, MAR, NGA, ROU, ZAF); the 12 unresolved Fitch rows keep
theirs (they block no initial event). The "before" column re-runs the first
collection with its own logic but the v0.4 window; the first row
reproduces the earlier 185 / 88 / 36 exactly.

| | collapsed events | initial events | collapsed surviving | initial surviving | countries | initial surviving, events 2005+ | countries 2005+ |
|---|---|---|---|---|---|---|---|
| before, old window (reproduction) | 238 | 109 | 185 | 88 | 36 | 79 | 35 |
| **before, v0.4 window** | 238 | 109 | 179 | **88** | 36 | 79 | 35 |
| **after second pass, v0.4 window** | 237 | 108 | 192 | **93** | 36 | 84 | 35 |
| after, sensitivity: first-ever ratings not a gap | 237 | 108 | 207 | 104 | 37 | 94 | 36 |

Net effect of the second pass: **+5 surviving initial events (88 -> 93), all
from events dated 2005 or later (79 -> 84; the 9 pre-2005 survivors are
unchanged and irrelevant for H1, no risk scores exist that early)**;
collapsed surviving +13. The gain is smaller than the volume of recovered S&P
history suggests, because the binding constraint is elsewhere (below). Sensitivity row (informational only,
not the pre-registered rule): treating a series' first row, when flagged
`new`, as a genuine first rating rather than a gap.

**Cells that still block events (15 initial events excluded; 4 are pre-2005 and
irrelevant; 11 are dated 2005+):**

| blocker | events blocked | detail |
|---|---|---|
| Moody's / Fitch series that start late with a bare `new` row (not verified as first-ever rating; the second pass did not target them) | 10 | KEN Moody's from 2012-11-08, LKA Moody's from 2010-09-22, NGA Moody's from 2017-11-07, VNM Moody's from 2012-09-28, ZMB Moody's from 2016-04-19, PAK Fitch from 2015-09-15, KEN Fitch from 2007-12-12; blocked events: KEN S&P 2008, LKA Fitch 2008, NGA S&P 2009 / 2015 and Fitch 2016, PAK S&P 2008 and Moody's 2012, VNM Fitch 2010, ZMB Fitch 2013 and S&P 2015 |
| Moody's 3-notch step not covered by a second-pass window | 1 | ITA Moody's 2011 (blocks ITA S&P 2011-09-19) |

Full list: `blocking_cells_initial_events.csv` (by reason:
`blocking_cells_by_reason.csv`); all late-start series:
`late_start_series_unverified.csv`.

### g.6 Decisions on partly_resolved FC rows (amendment 5)
Rule: a window is complete if every letter-rating change in it is known at
least to the month. All five FC / S&P-unspecified partly_resolved rows come
out COMPLETE (reasons in `partly_resolved_decisions.csv`): Spain Fitch (row
39: A- throughout, upgrade dated to the day), Czech Fitch (64: AA-
throughout, only outlooks open), France S&P (76: every letter change known
to the day, A+ on 2025-10-17 is already in v2), Portugal S&P (113: the one
month-only letter change is the Sept 2022 BBB -> BBB+ upgrade, which meets the
month bar; the resulting 3-notch BBB -> A- step is accepted; upgrade only, no
downgrade event is affected), South Africa Fitch (116: BB- throughout). The
LC_LT partly_resolved rows are out of scope for the FC panel.

### g.7 Manual checklist
1. **Dates inferred from a weekday or "yesterday"** (in the candidate panel,
   verify against the agency release): Nigeria Fitch 2024-05-03 (outlook) and
   2025-04-11 (upgrade B-/B); Romania Fitch 2023-03-24 (outlook);
   **Colombia Fitch 2025-12-16 (BB+ -> BB, the only one that is a downgrade
   event)**; Vietnam Fitch 2023-12-08 (upgrade; Fitch's own date assumed same
   day as the ministry's); Czech Fitch 2022-05 (outlook, month precision,
   stored as 2022-05-01).
2. **12 unresolved Fitch rows** (stale tables; none blocks an initial event
   today, but they could hide a missed Fitch action): row 48 Australia, 56
   Canada, 77 Germany, 81 India, 83 Indonesia, 88 Japan, 90 Kazakhstan, 94
   Malaysia, 97 Netherlands, 102 Norway, 127 Sweden, 128 Switzerland.
   Pointers in `second_pass_unresolved.md`.
3. **Late-start Moody's / Fitch series** (new, the largest remaining lever,
   10 events): confirm first-ever rating date or recover the earlier history
   for KEN, LKA, NGA, VNM, ZMB (Moody's) and PAK, KEN (Fitch).
4. Moody's Italy 2011 downgrade step: confirm as a single action.
5. S&P Jul-2021 table: re-attempt the cross-check from a browser session
   (HTTP 403 from this environment).
