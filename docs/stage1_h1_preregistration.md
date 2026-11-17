# Stage 1 repair and H1 test: pre-registration (v0.5 draft)

Status: draft for review. Becomes binding when committed. Must be committed
before any lead/lag, return or portfolio outcome is computed on repaired
Stage 1 labels. Items marked PROVISIONAL are confirmed in a later commit,
still before any outcome is computed.

Evidence: `data/diagnostics/stage1/summary.md` (2026-11-15, commit 8dabc39);
`data/diagnostics/ratings/summary.md` sections (a)-(g) (2026-11-15 to
2026-11-17).
Thesis numbering: new scheme (Stage 1 = section 3.2).

Changes from v0.4:
- 5.1: coverage gaps defined on the letter-rating path; rule for series that
  start late; source-priority rule for conflicting ratings; panel location
  and corrections file updated to what was actually built.
- 5.4: supporting check 7 (fundamentals-only score) added.
- 5.5: interpretation rule for check 7 added.

## 1. Why the current labels are replaced

- 36 of 78 labelled dates have no core-eligible country (2009-03 to 2018-03).
- 44.6% of risk-score variance is between dates, not between countries.
- Cause: `us_10y` and `curve_slope` have no cross-sectional variance, so the
  expanding-window clustering partly separates time regimes.

## 2. Repair adopted

Primary specification, variant (c):
- Features: the 8 country-level CORE features, each z-scored within its
  rebalancing date. Global features are dropped from Stage 1.
- Everything else unchanged: `label_panel` code path, expanding window,
  K-Means, k = 3, random_state = 42, same data-sufficiency parameters.
- k = 3 is fixed by design (three tiers are required). It is not re-selected.

Robustness specification, variant (b): raw country features, global
features dropped.

Fundamentals-only specification, variant (c-f): as variant (c), but with
the market-based feature (the spread or local yield feature defined in
section 3) removed from the clustering features. Used only for supporting
check 7. Cluster orientation (which centroid is lowest and highest risk)
uses the same ranking variable as variant (c); this sets direction only,
and the score itself is computed from distances in the fundamentals-only
feature space.

The superseded specification (a) is reported in the thesis together with
the diagnostic that motivated the change.

Basis for the choice: structural criteria only (non-empty sleeves on every
date, sleeve-size stability, between-date variance share, label turnover).
No lead/lag, return or portfolio outcome had been computed for (b), (c) or
(c-f) when this choice was made.

Known consequence: the score is purely relative. A lowest-risk tier exists
on every date, including during global stress. Stated as a limitation.

## 3. Spread feature and tier ranking (PROVISIONAL)

Problem: `yield_spread_bps` is built from ZSPREAD (swap-based), is 56.8%
populated, and is missing entirely for 7 EM countries. It is both a feature
and the variable that orders clusters into low / middle / high risk.

Planned replacement, once the return rebuild provides yields
(`docs/return_construction_spec.md`):
- Feature: local 10-year yield, z-scored within date.
- Tier ranking: clusters ordered by the mean within-date z-score of the
  local 10-year yield of their members.

To be confirmed after the licence test. Labels are not regenerated for
downstream use until this item is fixed.

## 4. Risk score

Unchanged in form: d_low / (d_low + d_high), the normalised position
between the lowest-risk and highest-risk centroids, computed in the
repaired feature space.

## 5. H1 final test

### 5.1 Data

Rating type
- Foreign-currency long-term (FC_LT) for all countries and agencies.
  Reason: the 2026-11-15 collection found local-currency histories too
  incomplete for a 2005-2025 test (S&P local-currency series start
  2007-2011 for most countries, Moody's local-currency series are missing
  for 5 countries, no local-currency outlooks). Local-currency ratings are
  used descriptively only. The mismatch with the local-currency bond
  universe is stated as a limitation.
- S&P rows whose currency is not stated by the source ("unspecified") are
  treated as FC_LT only if both conditions hold; otherwise they are
  excluded:
  1. Source test: among S&P actions on which the labelled FC_LT and LC_LT
     ratings differ, at least 95% of the rows contributed by the
     unlabelled source carry the FC_LT rating.
  2. Continuity test, per country: the last unspecified rating before the
     first FC_LT-labelled row is consistent with that row (same rating,
     or the labelled row is itself a recorded change from it).
  A country failing the continuity test keeps its unspecified rows
  excluded even if the source test passes overall. Unspecified rows that
  have a matching FC_LT row from another source are merged into that row
  and are unaffected.

Panel construction
- Source: `data/raw/ratings_v2/` (first collection) plus
  `data/raw/ratings_v2_second_pass/` (second pass), with
  `data/interim/_corrections_v2.csv` applied. Built by
  `diagnostics/build_h1_candidate_panel.py`.
- Every panel row used must pass the ratings sanity checker.
- Same action, different dates: the earliest date is used. Rows of the same
  agency with the same rating within 3 days are treated as one action.
- Same agency and date, different ratings: a row from the agency itself or
  an official source takes precedence over an aggregator; the choice is
  recorded in the corrections file. If neither row is from the agency or an
  official source, the event involving it is excluded from the primary set.
- The earlier 13-country panel serves as a cross-check only.

Coverage gaps
- A country x agency x year cell is complete when the letter-rating path
  through that year is established, with every letter-rating change known
  at least to the month. Unverified outlook or watch actions do not make a
  cell incomplete.
- A period before an agency's first rating of a country is "not rated", not
  a gap, but only if a source states that the first row is the agency's
  initial rating of that country (an agency release, an official source, or
  an agency history table that starts the series with an assignment). A
  series whose first row is not verified this way is treated as a gap
  before that row.
- An event is excluded from the primary set if its event quarter or any of
  its preceding 4 quarters falls in a gap cell for ANY of the three
  agencies for that country. Reason: a downgrade missing from one agency's
  series can make a later downgrade by another agency look initial when it
  is not.
- These rules were chosen on data completeness and event counts only. No
  score or outcome had been computed.

Freezing
- The panel and gap map are frozen in a dated commit, written to
  `data/processed/ratings_h1_panel.csv` and
  `data/processed/ratings_h1_gap_map.csv`, before section 5 is run.

### 5.2 Events
- Downgrade: a decrease in the letter rating by any of the three agencies.
  Outlook and watch changes are not events.
- Collapsing: at most one event per country per quarter, dated at the
  earliest downgrade in that quarter.
- Primary event set: initial downgrades only, defined as events with no
  downgrade of the same country in the preceding 4 quarters.
- Secondary event set: all collapsed events.

### 5.3 Statistic
- Near window: the last 4 rebalancing dates before the event.
- Baseline window: the 4 rebalancing dates before the near window.
- Delta = mean risk score (near) minus mean risk score (baseline).
- An event is used only if the country has a valid score on at least 3 of
  4 dates in each window.

### 5.4 Test
- Unit of inference: the country. Each country's Delta is the mean over
  its events.
- H0: mean country Delta <= 0. H1: mean country Delta > 0.
- Primary test: one-sided t-test across countries on the primary event
  set, alpha = 0.05.
- Supporting checks, reported whatever the result:
  1. Wilcoxon signed-rank test on the same country Deltas.
  2. Placebo test: 1,000 draws assigning each event's date to a country
     with no downgrade within 4 quarters either side; report the share of
     draws with a mean Delta at least as large as observed.
  3. The same test on the secondary event set.
  4. The same test under robustness specification (b).
  5. The same test restricted to the 31 countries outside the pilot.
  6. The same test restricted to events confirmed by at least two
     independent sources or by an agency's own published history.
  7. The same test using the fundamentals-only score, variant (c-f).
     Reason: ratings respond to market spreads (Mora, 2006), so a score
     that contains a market-based feature may lead ratings partly by
     construction. A lead in the fundamentals-only score is the stronger
     evidence that the model anticipates deterioration rather than
     following prices.

### 5.5 Verdict rule
- H1 is treated as supported only if the primary test rejects H0.
- If the primary test does not reject, the thesis reports H1 as not
  supported, whatever the supporting checks show.
- Check 5 is reported as the cleanest out-of-sample evidence, because the
  13 pilot countries were examined before this document was written.
- If the primary test rejects and check 7 does not, the thesis states that
  the lead may be driven by the market-based feature and does not claim
  that fundamentals anticipate downgrades.

### 5.6 Out of scope
- Upgrades: described, not tested (H1 concerns downgrades).
- The fiscal-versus-other-pathway explanation from the pilot: exploratory
  only, and labelled as such wherever it appears.
- The 13-country pilot and the confound check: reported as exploratory.

## 6. Order of operations

1. Commit this document.
2. Complete the manual checks, freeze the 44-country ratings panel and gap
   map (section 5.1, Freezing).
3. Run the licence test; rebuild yields; confirm section 3 in a dated
   commit.
4. Regenerate Stage 1 labels under (c), (b) and (c-f).
5. Run section 5 once. No re-runs with altered definitions.
