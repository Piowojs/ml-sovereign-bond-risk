# Stage 1 regime-artifact diagnostics (2026-11-15)

Produced by `diagnostics/stage1_regime_diagnostics.py`. Diagnostic only —
nothing in `data/processed/` or `src/` was touched, and **no return,
portfolio, or lead/lag outcome was computed for any Part 2 variant** (explicit
scope decision). Motivated by CLAUDE.md's "Known open problems": the
walk-forward labels assign zero countries to `core-eligible` for ~9 years, the
residual global-feature regime artifact. All findings here are **diagnostic
results pending a design decision** — no repair variant is adopted.

All outputs in `data/diagnostics/stage1/`: `part1_by_date.csv`,
`part1_variance_decomposition.csv`, `fig_part1_median_score.png`,
`part2_variant_comparison.csv`, `part2_label_counts_by_year_{a,b,c}.csv`,
`part3_confound_events.csv`, `part3_confound_by_country.csv`,
`part3_event_counts_by_year.csv`.

Thesis references use the new (2026-11-15) numbering — Stage 1 = §3.2.

---

## Part 1 — Size of the regime artifact (stored production labels)

- **36 of 78 labeled rebal dates (46%) have zero `core-eligible` countries**,
  spanning 2009-03 to 2018-03 continuously except a single-country blip in
  2013 — slightly wider than the "2009–2017" previously documented (the span
  ends 2018-03, not 2017-12).
- **Between-date share of `risk_score` variance: 44.6%** (within-date 55.4%;
  n=3,432 scored rows). Nearly half the variance of a score meant to rank
  *countries* is calendar-time level shift — the quantified size of the
  artifact.
- The median-score plot (`fig_part1_median_score.png`) shows the mechanism:
  the cross-sectional median jumps ~0.10 entering 2009, stays elevated
  (0.53–0.60) through the whole zero-core span, and drops back ~0.10 in 2018.

## Part 2 — Candidate repairs, judged on structure only

Same code path (`build_risk_labels.label_panel`), same expanding window, same
params (kmeans / core / k=3 / random_state=42). Variant (a) reproduced the
stored `stage1_risk_labels.parquet` **exactly** (labels and scores) before
anything else was compared.

| Metric | (a) current CORE | (b) no us_10y/curve_slope | (c) cross-sectional z, no globals |
|---|---|---|---|
| Dates with zero core-eligible | **36** | **0** | **0** |
| Dates with <5 countries in either sleeve | 44 | 0 | 0 |
| Core sleeve size min / p10 / median | 0 / 0 / 4.5 | 5 / 6 / 12 | 8 / 12 / 14 |
| Satellite sleeve size min / p10 / median | 0 / 6.7 / 15 | 7 / 10 / 13 | 8 / 9 / 11 |
| Between-date variance share of score | 0.446 | 0.048 | 0.018 |
| Mean label turnover between dates | 0.098 | 0.102 | 0.124 |
| ARI vs DM/EM, pooled | 0.085 | 0.104 | 0.170 |
| ARI vs DM/EM, mean per-date | 0.446 | 0.382 | 0.397 |

Reading: **both repairs fully eliminate the empty-core problem** and collapse
the between-date variance share by an order of magnitude, at modest turnover
cost. The pooled-vs-per-date ARI split is informative: variant (a)'s pooled
ARI (0.085) is far below its per-date ARI (0.446) precisely because the
regime artifact scrambles tiers *across* quarters; (b)/(c) nearly close that
gap. Per-date DM/EM agreement is somewhat *higher* under the current feature
set (0.446 vs 0.382/0.397) — the global features do contribute some
within-date discrimination, so the repairs are not free. (c) dominates (b) on
sleeve-size stability and pooled ARI; (b) is the minimal change and stays
closest to thesis §2.3's declared feature groups.

**Tier-ranking dependency to note**: cluster-to-tier ranking uses raw
`yield_spread_bps`, which is sourced from the raw bond CSVs' **ZSPREAD**
column (spread over swap, not UST — see CLAUDE.md "Stage 1 feature matrix")
and is only **56.8% populated** in the core feature matrix (43.2% missing; 7
EM countries have zero coverage ever). All three variants inherit this
identically — it is held fixed, not varied, here. In variant (c), the
within-date z-score of `yield_spread_bps` is additionally undefined for
early dates where <2 countries have any spread (sklearn's imputer then skips
the all-NaN column in those training windows — a logged warning, not an
error; deterministic and consistent between fit and apply).

## Part 3 — H1 confound check on the 13-country pilot (EXPLORATORY)

**Run after the pilot results were seen** — unlike the pilot's two surviving
pre-registrations, this is post-hoc and must be labeled as such wherever
cited. Question: is a country's pre-downgrade score rise just the global
level rising (the Part 1 artifact), rather than country-specific
deterioration? For each of the 211 `status=="ok"` downgrade events: own
near-minus-baseline score change (the pilot's `diff`) minus the same change
in the cross-sectional median of other countries over the identical window
dates, computed (i) vs all other countries and (ii) vs "clean controls"
(countries with no own downgrade within ±4 quarters / 365 days).

- **Headline: 6 of the 7 positive-direction pilot countries stay positive
  after the market adjustment — under both (i) and (ii).** The exception is
  **Greece**: mean own diff +0.021, but the market median rose +0.030 over
  the same windows, so Greece's mean abnormal change is **−0.009** — its
  pilot signal is fully absorbed by the global level shift (its 34 events
  cluster in 2010–2012, exactly when the Part 1 artifact's level jump
  occurs). Portugal (+0.015), Sri Lanka (+0.010), Spain (+0.007), Colombia
  (+0.007), Italy (+0.006), South Africa (+0.003) all survive, though the
  surviving magnitudes are small.
- The null-bucket countries stay broadly null or slightly positive-abnormal
  (Pakistan's +0.075 abnormal is the largest anywhere — driven by its
  events falling when the market median *fell* — a reminder these are
  descriptive decompositions, not tests).
- **Event clustering confirms the exposure**: 2011 alone has 34 of 211
  events; 2010–2012 together have 71 (34%), sitting inside the zero-core
  regime window.
- Variants (i) and (ii) give nearly identical answers everywhere —
  unsurprising, since removing up to 12 contaminated countries barely moves
  a 43-country median. **Caveat on (ii)**: only the 13 pilot countries have
  transcribed ratings, so the other 31 are "event-free" by data absence,
  not verified absence.

## Implications (pending a design decision — nothing adopted here)

1. The artifact is real, large (44.6% between-date variance share; 46% of
   labeled dates with an empty core sleeve), and mechanically fixable:
   either repair variant yields a non-empty, size-stable core sleeve on
   every date, which is what Stage 3's 70% core sleeve (§3.4.1) needs.
2. The choice between (b) and (c) — or a methodology-level override of
   §2.3's global-feature scoping for Stage 1 — is a design decision that
   should also weigh the per-date ARI give-up and the H1 re-run.
3. The H1 pilot's positive signal is **not** explained away by the global
   level shift for 6 of 7 countries, but Greece — the thesis's flagship
   crisis case (§1.3, §5.4) — is exactly the case where it is. Any H1
   result on a repaired Stage 1 should be re-run under the existing
   pre-registered protocol, not patched post-hoc.
