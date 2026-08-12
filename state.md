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

## Open items (as of 2026-08-11)

| Item | Blocks | Whose action | Status |
|---|---|---|---|
| Manually collect per-country rating-action history into `data/raw/ratings/manual/<Country>.csv` | §4.2.3, §4.2.4, RQ1/H1 | User (transcribe both TheGlobalEconomy.com and countryeconomy.com per country as a two-sheet workbook, then run `reconcile_ratings_sources.py` — see the 2026-08-10/2026-08-11 reconciliation entries below; agency IR pages for gaps neither source covers). **Tier 1 fully done — continue with Tier 2**, see the transcription priority list below. **Reminder for multi-word countries**: pass the underscore form (`Sri_Lanka`, not `Sri Lanka`) as the script's `country` argument — it's used verbatim as the output filename and must match `configs/universe.yaml`'s `name.replace(" ", "_")` for `ingest_ratings.py`'s coverage check to recognize it (caught once on Sri Lanka, fixed before anything downstream ran on the wrong filename). **CE raw-paste reminder**: as of the pre-Portugal fix, both `LETTER_GRADE (Outlook)` and letter-grade-less `(Outlook)`-only CE cells are handled automatically — paste CE's raw combined rating+outlook text straight into the `rating` column and leave `outlook` blank, no manual pre-splitting needed. | **In progress — 13/44 (Greece, Turkey, Sri Lanka, Portugal, Zambia, South Africa, Brazil, Colombia, Egypt, Pakistan, Nigeria, Italy, Spain) done — Tier 2 fully complete**, all reconciled via `reconcile_ratings_sources.py` (172 + 170 + 118 + 108 + 45 + 137 + 137 + 94 + 138 + 84 + 67 + 132 + 110 = 1,512 rows, 5 conflicts total found and resolved — Greece 1, Turkey 2, South Africa 1, Brazil 1; Colombia, Egypt, Pakistan, Nigeria, Italy, and Spain all reconciled without a resolutions.csv entry). Italy and Spain both reconciled under a pre-registration (`12f9a3e`) predicting positive-direction lead/lag signal for both; both had zero conflicts, full 3-agency CE coverage, and — checked systematically across all 13 countries reconciled so far — neither crossed the IG/junk boundary, which now shows a **perfect 13-for-13 split** with the GE/CE conflict hypothesis (every IG-boundary-crosser produced a conflict, every non-crosser didn't) — see the Source factual-error tracking section below for the full table. **2026-08-12 audit + fix**: the Sri Lanka anomaly flagged above turned out to be a real CE transcription error (S&P `A` should be `B+`), corrected via a new re-run-safe `_corrections.csv` mechanism; a source-agnostic `sanity_check_ratings.py` was then built and run across all 13 countries specifically because this error had never surfaced as a conflict (single-source rows are structurally invisible to conflict detection) — found the Sri Lanka case was isolated (1 real problem of 26 total flags) and quantified 46.0% (695/1512) of all rows as never cross-validated against anything. See the 2026-08-12 chronological entry for full detail. **Panel changed — the 13-country lead/lag pilot below was run before this fix and needs re-confirming**, though a direct before/after check shows Sri Lanka's own result is unaffected (p=0.051515 either way). 31 to go — starting Tier 3. |
| §4.2.4 lead/lag analysis (`ratings_leadlag_stub.py`) | §4.2.4, RQ1/H1 | Full-universe version still blocked on the remaining 31 countries' ratings transcription | **13-country pilot re-run 2026-08-12 (Italy + Spain added) — Tier 2 complete, both pre-registrations (`d23fd6e`, `12f9a3e`) survived without a single exception.** Eurozone pair landed precisely as predicted: **Spain clears p<0.05 (0.018)**, **Italy doesn't (0.107) but is clearly positive-direction** (84.6% of events increase) — the specific "Spain more cleanly than Italy" call, not just a vague positive/negative one, hit. Full 13-country picture now shows a **clean two-bucket split with zero exceptions**: all 7 "macro-fundamental/persistent deterioration" countries (Greece, Portugal, South Africa, Spain, Sri Lanka, Colombia, Italy) are positive-direction (4 clear, 2 borderline, 1 short of significance); all 6 "other pathway" countries (Turkey, Zambia, Brazil, Egypt, Pakistan, Nigeria) are null or near-null, none clearing p<0.05 positive. Second genuine pre-registered test survived intact. Still not citable — 13 of 44 countries, no formal multiple-testing correction, and only 5 of 13 countries' bucket assignment was genuinely pre-registered before reconciliation (the original 5-country pilot's classification was post hoc). See the 2026-08-12 "Lead/lag pilot re-run at 13 countries" chronological entry for the full table, decomposition, and H1 status read. |
| Residual global-regime sensitivity in Stage 1 clustering (`core-eligible` = 0 for several consecutive quarters, 2009-2017) | §5.5 candidate robustness check; not blocking Stage 3/4 | Open — see CLAUDE.md "Stage 1 clustering" for the full diagnosis (us_10y/curve_slope are global-only features, thesis §3.3 keeps them in Stage 1 regardless) | Documented, not fixed further without a methodology-level call to override the thesis's own feature-group spec |
| Execution-verify `bond_data_pull_reconstructed.py` (does it actually run/chunk/return data as designed) | Appendix A reproducibility only — not blocking, since existing bond data already feeds Stage 1 | User (requires a session on the university-library Windows PC with Refinitiv Workspace) | Not started |
| CDS data (`data/raw/cds/`) never successfully pulled | Nothing currently — Stage 1 extended tier gates on duration/convexity, not CDS (see CLAUDE.md) | Would also require the library-PC session if pursued | Open, not currently prioritized |
| `docs/thesis_outline_sovereign.md` §1.4 still says "2005–2023"; actual pipeline uses 2005–2025 | Consistency of the written thesis, not the code | User (thesis text edit) | Open, tracked separately from code |
| Stage 2 (`src/stage2_signal/`) built — see 2026-08-11 chronological entries below | §4.3, RQ2/H2 | — | **Done.** H2 not rejected (LASSO mean IC +0.076 but p=0.205, doesn't clear the p<0.05 bar). Two follow-up diagnostics (2026-08-11) tested whether this is a power problem — both point away from that reading (AUC collapses to ~0.50 on 4.4x the observations); see CLAUDE.md "Stage 2 signal" for the full picture and the "this specification, not this universe" distinction that should carry into §6.2/§7.4. |
| No coupon-rate/cashflow field exists anywhere in the raw bond pull — Stage 2's "total return" is a documented price-return proxy, not true coupon-inclusive total return | §4.3.2, Appendix B | Structural licence/data limitation (generic benchmark composite RICs, not individual bond issues) — not fixable without different source data | Documented and flagged per-row (`has_income_component`), not silently approximated — see CLAUDE.md "Stage 2 signal" |
| Stage 2 EM satellite population is small-N by construction (median 4-8 countries/quarter, EM rows in only 65/84 quarters) | §4.3.3/§4.3.4 result reliability | Inherited from Stage 1's clustering output — would require revisiting Stage 1's residual global-regime sensitivity (already an open item above) to change | Documented as a first-order caveat on every Stage 2 result. **Update (2026-08-11 diagnostics)**: the small-N caveat still applies to *precision* of the estimate, but two diagnostics found no evidence it's suppressing a real signal — see the Stage 2 row above. |
| H2 multi-horizon robustness check (pre-registered 2026-08-11, run 2026-08-11) — monthly (30d) / quarterly (~91d) / semi-annual (182d), 3 models x 2 framings = 18 combinations | §2.8 (Harvey/Liu/Zhu multiple-testing standard), §5.5, §6.2/§7.4 framing of H2 | — | **Done. 0 of 9 regression combinations clear H2's bar** (IC>0.05 and p<0.05) — not even before any multiple-testing correction, so correction only reinforces the null, doesn't change it. Best regression IC is still quarterly/LASSO (+0.076, p=0.205); monthly is ~flat (+0.001, p=0.495); semi-annual goes negative (-0.049, p=0.714). One genuinely interesting, NOT pre-specified-as-a-bar observation: monthly/LASSO classification AUC=0.617, the highest AUC anywhere in Stage 2's investigation (vs quarterly 0.560, semi-annual 0.467 — below chance) — flagged for §7.4 as suggestive, unvalidated (H2's formal test is the IC/regression framing only, no significance test was pre-specified for AUC), not promoted into a conclusion. See CLAUDE.md "Stage 2 signal" and `data/processed/stage2_multi_horizon_robustness_summary.csv`. |
| Stage 3/4 (`stage3_portfolio/`, `stage4_evaluation/`) not started | Everything downstream of Stage 2 | — | Not started — Stage 1 and Stage 2 are now fully built; this is the next major phase |

---

## Ratings transcription priority (for issue #3)

Suggested sequencing for manually transcribing `data/raw/ratings/manual/<Country>.csv`
files, ranked by how much a country is likely to contribute to H1's
lead/lag test — countries with real rating changes during 2005–2025
matter; countries that sat at one rating the whole window contribute
little. Based on general knowledge of major sovereign rating events, not
yet verified against the actual transcribed data.

- **Tier 1 (done — explicit crisis case studies named in the thesis
  outline itself)**: ~~Greece~~ (done, 2026-08-10), ~~Turkey~~ (done,
  2026-08-11), ~~Sri Lanka~~ (done, 2026-08-11), ~~Portugal~~ (done,
  2026-08-11), ~~Zambia~~ (done, 2026-08-11). **All 5 of 5 complete.**
- **Tier 2 (high value — sharp multi-notch moves)**: Italy, Spain, South
  Africa, Brazil, Colombia, Egypt, Pakistan, Nigeria. **Sequencing within
  Tier 2 revised 2026-08-11 based on the lead/lag pilot's actual open
  question** (see the pilot's chronological entry below) — transcribe in
  this order, not the list order above:
  1. **South Africa, Brazil, Colombia first** — non-Eurozone,
     fiscal-deterioration-driven downgrade histories. These are the pair
     that actually tests the open question the pilot raised: does the
     lead/lag mechanism generalize beyond Eurozone-style crises (like
     Greece/Portugal), or is it specific to that crisis shape?
  2. **Egypt, Pakistan, Nigeria second** — currency/commodity-driven
     downgrade histories, the other half of the open question: do these
     fail like Turkey (also currency/political-risk-driven), or was
     Turkey's null idiosyncratic?
  3. **Italy, Spain last within Tier 2** — deprioritized for *this*
     question specifically, not dropped: both are Eurozone-crisis cases
     structurally similar to Greece/Portugal (same 2010-2012 shock, same
     debt/fiscal-driven deterioration shape), so they're likely to
     confirm what's already been observed rather than test it. Still
     valuable for other reasons (both are thesis-named DM stress cases,
     §2.3/§6.4) — just not the next-highest-information transcription
     targets for H1's generalization question.
- **Tier 3 (moderate — real notches, plus two "even safe sovereigns
  react" DM cases)**: United States, United Kingdom, France, Hungary,
  Romania, China, Kenya, Indonesia, Philippines, Vietnam, Mexico,
  Kazakhstan, Japan.
- **Tier 4 (lower value — mostly stable, do later)**: Poland, India, Peru,
  Czech Republic, Thailand, Chile, Malaysia, Morocco, Belgium, Austria.
- **Tier 5 (lowest value — essentially flat the whole window, do last or
  skip under time pressure)**: Germany, Netherlands, Finland, Norway,
  Sweden, Switzerland, Canada, Australia.

Tier 1 + Tier 2 (13 countries) covers every default/restructuring event
and every crisis case study the thesis outline names explicitly — the
highest-leverage stopping point for a first pass at H1 if the full 44
isn't feasible before a deadline.

---

## Source factual-error tracking (data quality note, both sources)

A living list of confirmed cases where a source carried a value a
primary source (or, for case 5, direct domain knowledge plus internal
plausibility checking) shows was **factually wrong** for that date —
distinct from either source's much more common failure modes (coarser
month-only precision, default-designation/multi-year-blackout gaps, or
CE's missing-agency gaps, all documented per-country above). Those other
modes are *incompleteness*; the cases below are a source actively
asserting something incorrect. Originally scoped to GE only (hence the
table's early entries), renamed 2026-08-12 after case 5 confirmed CE can
carry the same kind of error. Add a row here every time an error is
confirmed — via conflict adjudication *or* via
`sanity_check_ratings.py` — not every resolved conflict belongs here,
only ones where the value was actually wrong, not just less precise.

| # | Country | Source wrong | Agency | Date | Wrong value | Confirmed correct | Failure type | Found via |
|---|---|---|---|---|---|---|---|---|
| 1 | Turkey | GE | Moody's | 2015-12 | `Ba3` | `Baa3` (Reuters/Business Standard, Sept 2016 downgrade-from-Baa3 reporting) | Rating-level error | Conflict adjudication |
| 2 | South Africa | GE | Fitch | 2020-11-20 | `BB-`/`Stable` | `BB-`/`Negative` (Fitch's own release title; South Africa National Treasury statement) | Outlook-level error, rating correct | Conflict adjudication |
| 3 | Brazil | GE | Moody's | 2018-04-09 | `Ba2`/`Negative` | `Ba2`/`Stable` (Itaú BBA reporting; Trading Economics' rating history; Brazil National Treasury's 2024 statement referencing this 2018 move) | Outlook-level error, rating correct | Conflict adjudication |
| 5 | Sri Lanka | **CE** | S&P | 2007-01-23 | `A` | `B+` (GE confirms B+ on both sides, Apr 2006 and Aug 2007; Sri Lanka was never remotely A-rated) | Rating-level error, large (~9 notches) | `sanity_check_ratings.py` (implausible jump + range outlier) plus the user's own domain knowledge — **not** conflict adjudication, since GE had no competing row that date to disagree with |

**Case count is numbered 1/2/3/5 deliberately, not renumbered to
1/2/3/4** — case 4 doesn't exist; there is no confirmed case between
Brazil and Sri Lanka, the numbering just reflects chronological
discovery order across sessions and skipping to 5 here avoids implying a
case 4 was found and omitted.

**Explicit caveat on what this table can and can't say, stated directly
because it matters for how this reads (2026-08-12)**: the tally above is
**4 GE-wrong, 1 CE-wrong** — but that ratio is an artifact of *how*
errors get found, not evidence about which source is more reliable
overall. Cases 1-3 were found by conflict adjudication, a mechanism that
structurally can only catch an error when the *other* source has a
competing row to disagree with. Case 5 was found by a completely
different mechanism (`sanity_check_ratings.py`'s internal-consistency
checks) specifically *because* conflict adjudication couldn't see it —
CE's bad row had no GE counterpart that month to collide with. Given
that 46% of all rows across the 13 countries reconciled so far are
single-sourced (see the single-source exposure figures in the
2026-08-12 audit entry below) and this audit has so far only been run
once, on the full current panel, there is no basis yet for a claim like
"GE is wrong more often than CE" — only "GE has been caught wrong more
often by the mechanism that catches disagreements, and CE has been
caught wrong once by the mechanism that catches internal
implausibility." Those are different measurements of different things.

**Revised characterization (2026-08-12, after Brazil), superseding the
original multi-agency-clustering hypothesis**: the clustering idea (does
GE err specifically when several agencies act close together?) was
tested and did *not* hold up on Brazil — no other agency acted anywhere
near the April 2018 date, ruling out a coincident-round explanation for
that case, yet it turned out to be the same broader symptom as South
Africa anyway. The pattern that actually holds across cases 2 and 3: in
both, **GE got the rating right and the outlook wrong**, and in both the
wrong outlook was a value that was correct *somewhere else* — case 2
borrowed a different agency's concurrent outlook, case 3 carried forward
the *same* agency's own prior outlook instead of picking up the
outlook-only revision. Two different proximate mechanisms (cross-agency
vs. stale same-agency), one shared symptom: **GE does not reliably
update the outlook field specifically when a change is outlook-only**
(no accompanying letter-grade move to signal "something changed here").
Case 1 (Turkey) remains a genuine outlier under this revised
characterization — a rating-level error, not an outlook-level one — and
isn't folded into this pattern; it stays open as a separate, unexplained
case unless a similar rating-level error recurs.

If this "reliable on rating levels, unreliable on outlook-only updates"
characterization continues to hold as the remaining Tier 2 countries
land (Italy, Spain), it becomes a clean, describable, and reasonably
well-evidenced source-reliability limitation for the thesis's
data-quality discussion (Appendix B candidate): **trust GE's letter
ratings; verify its outlooks against CE or a primary source, especially
on outlook-only actions with no accompanying rating change.** Watch
specifically for outlook-only conflicts (rating agrees, outlook doesn't,
no watch-qualifier asymmetry) going forward — that's the exact shape
both confirmed cases took.

**Still at 2 confirmed cases after Colombia (2026-08-12) — deliberately
not a 3rd data point.** Colombia's one candidate conflict (S&P, 2025-06:
GE outlook `NR` vs CE `Negative`) looked superficially like the same
shape (rating agrees, outlook differs) but isn't the same phenomenon:
GE was *declining to assert* an outlook (a recurring convention — 8 of
33 GE S&P rows in that file carry `outlook="NR"`), not *asserting a
wrong one* the way South Africa and Brazil did. Confirmed by checking
how frequent `NR` was in that file before concluding anything — a single
occurrence might have been a one-off error, but 8 of 33 rules that out.
Encoded as a permanent reconciliation policy (module docstring point 11:
`NR` in the outlook field is treated as absent, same as blank), not
folded into this tracking table. The hypothesis remains open, unmoved by
Colombia either way.

**Still at 2 confirmed cases after Egypt, Pakistan, and Nigeria too
(2026-08-12) — but now for a different, more notable reason: three
straight zero-conflict countries.** None of the currency/commodity-group
countries produced a single candidate conflict, so none tested the
outlook-reliability hypothesis at all (a hypothesis about disagreements
can't be tested by countries that produce none). Worth flagging as its
own pattern, distinct from the outlook-reliability one: every country in
the fiscal-deterioration group (South Africa, Brazil, Colombia) produced
at least one candidate conflict, while zero of three in the
currency/commodity group (Egypt, Pakistan, Nigeria) did. One plausible
explanation, not yet tested: GE and CE may agree more readily on
countries with fewer investment-grade-boundary crossings — all three
fiscal-deterioration countries crossed the IG/junk line at least once
during the sample (Greece, Portugal, South Africa, Brazil, Colombia all
did), while Egypt, Pakistan, and Nigeria have sat sub-investment-grade
throughout, with no boundary crossing to generate the kind of
close-in-time, easy-to-conflate multi-agency action that produced South
Africa's and Brazil's errors. Untested, not yet a finding — would need a
country that crosses the IG boundary from a low starting point (or
doesn't) to actually probe it, which isn't guaranteed by transcription
order alone.

**Italy (2026-08-12) is a genuinely informative data point for the
crossing-specific version of this hypothesis, not just another
zero-conflict case to tally.** Italy had substantial multi-agency
downgrade *density* — five Moody's notches in ~13 months during 2011-12
alone, comparable in intensity to the fiscal-deterioration group's
crisis periods — yet **never actually crossed the IG/junk boundary**
(bottomed out at Fitch `BBB-`/Moody's `Baa3`, the lowest investment-grade
notch, multiple times, but never into junk) and had **zero conflicts**.
This matters because it distinguishes two different versions of the
hypothesis: a "general downgrade turbulence" version (which Italy would
contradict — lots of activity, no conflict) versus the original
"boundary-crossing specifically" version (which Italy is consistent
with).

**Spain (2026-08-12) turned out to be a second non-crosser, not the
crossing-with-conflict test case initially expected.** Correcting an
assumption made in the Italy entry above: Spain, like Italy, **never
crossed the IG/junk boundary** either — its worst points are Moody's
`Baa3` and S&P `BBB-` (2012-13, during the banking-sector bailout
period), the same bottom investment-grade rung Italy touched, despite an
even sharper collapse (Moody's alone fell roughly eight notches, `Aaa`
to `Baa3`, between mid-2010 and mid-2012). Zero conflicts, full 3-agency
CE coverage, no SD/RD/D — all as expected, and all consistent with (not
yet a new test of) the crossing-specific hypothesis.

**Full pattern across all 13 countries reconciled so far, checked
systematically rather than by recollection (2005-2025 scope, since an
unscoped first pass wrongly flagged Egypt as a crosser using pre-2005
history)**:

| Crossed IG boundary within 2005-2025? | Countries | Ever produced a GE/CE conflict? |
|---|---|---|
| Yes (6) | Greece, Turkey, Portugal, South Africa, Brazil, Colombia | **6 of 6** — every one, including Portugal and Colombia, whose original candidate conflicts are now auto-resolved by policies introduced *because of* their cases (watch-qualifier asymmetry, NR-outlook), so today's conflicts.csv shows 0 for them but a real disagreement did occur historically |
| No (7) | Sri Lanka, Zambia, Egypt, Pakistan, Nigeria, Italy, Spain | **0 of 7** |

**This is a perfect 13-for-13 split in the current sample** — worth
taking seriously as a working hypothesis for the thesis's data-quality
discussion, but explicitly *not* yet a settled causal claim: 13
countries, reconciled in an order chosen for thesis relevance (Tier 1/2
priority), not to test this specific hypothesis, and "crossing the IG
boundary" could easily be a proxy for something else correlated with it
(e.g. crossing events tend to draw denser, more compressed multi-agency
news coverage that's inherently harder for any aggregator to transcribe
consistently) rather than a direct cause. Worth checking explicitly on
each remaining country rather than assumed to hold.

**Side discovery while running this check, unrelated to Italy/Spain
specifically, flagged and NOT fixed**: Sri Lanka's `Sri_Lanka.csv` has
one row -- `S&P, A, (blank outlook), 2007-01-23`, sourced from CE --
that is very likely a transcription error, not real history. It sits
isolated (no GE row to compare against, so it never triggered a
conflict), has a blank outlook, and is historically implausible (Sri
Lanka has never been remotely A-rated; Fitch shows `BB-` for the same
period). Excluding that one row, Sri Lanka's actual best rating in
2005-2025 is `BB-` (Fitch, Dec 2005) -- meaning Sri Lanka never crossed
the IG boundary either, consistent with the general historical
understanding of Sri Lanka as a persistently junk-rated frontier
sovereign until its 2022 default. Left as-is in `Sri_Lanka.csv` pending
the user's decision on whether to verify and correct it -- not touched
by this session, since it falls outside the Italy/Spain scope and every
prior data anomaly in this project has been held for confirmation before
any value was changed.

---

## CE agency-coverage gap tracking (data quality note, watch across remaining countries)

A living list of countries where countryeconomy.com (CE) has **zero
rows for an entire agency** that TheGlobalEconomy.com (GE) does cover —
distinct from GE's per-row gaps (month-precision, default-designation
omission) documented elsewhere in this file: this is CE's *entire
agency coverage* being absent for a country, not a per-date gap. Handled
correctly by the existing union-of-months policy with no code change
needed both times it's occurred — flagged here purely as a data-quality
observation for the thesis's Chapter 3 characterization of sources, not
a reconciliation bug.

| # | Country | Missing agency (CE) | GE rows for that agency | Confirmed how |
|---|---|---|---|---|
| 1 | Zambia | Moody's (0 CE rows) | 11, all GE-only | Discovered during reconciliation (2026-08-11) |
| 2 | Nigeria | Moody's (0 CE rows) | 15, all GE-only | User checked CE's page directly before reconciling (2026-08-12) |

**Two cases isn't a pattern yet, but the shared characteristics are
worth naming explicitly**: both are African, and both have sat
sub-investment-grade for their entire sample-period history (no IG
crossing at all, in either direction) — the same "sits in junk
throughout" profile as the zero-conflict currency/commodity countries
noted in the GE factual-error tracking section above, though this is a
different phenomenon (CE's coverage breadth, not GE/CE agreement).
Missing exactly Moody's specifically both times is also worth noting,
though two data points can't distinguish "CE systematically has thinner
Moody's coverage for frontier sovereigns" from "coincidence, two of our
lowest-rated countries happened to both be Moody's gaps."

**If this holds across the remaining 33 countries** (worth checking
explicitly on the next several, not just noting when it happens to
recur), it becomes a describable, citable limitation for Chapter 3:
**CE cannot be treated as a uniform baseline "primary manual source"
across the full 44-country universe** — for frontier/lower-rated
sovereigns specifically, GE may be the *only* available source for a
given agency, which matters for how the thesis frames "CE primary, GE
fallback" (the general framing) versus what actually happens in
practice for a meaningful subset of the universe. Not yet enough
evidence to write that claim into Chapter 3 — 2 of 44 countries, both
found opportunistically rather than through a systematic check — but
worth deciding whether to check this explicitly (grep each remaining
country's CE sheet for agency coverage before reconciling, the way the
user did for Nigeria) once a few more countries land, rather than
continuing to rely on stumbling into it per-country.

**Italy and Spain (2026-08-12) both checked explicitly and show full
3-agency CE coverage** (Fitch, S&P, and Moody's all present in both
sheets, for both countries), consistent with the "frontier/lower-rated
sovereigns specifically" framing — both are investment-grade-throughout
and developed-market, with none of Zambia's or Nigeria's coverage gaps.
Not new disconfirming or confirming evidence on their own (a DM country
having full coverage was the expected, unremarkable case, not a test of
the hypothesis the way a third frontier/lower-rated country would be) —
but keeps the running count clean: 2 of 2 lower-rated/frontier countries
checked so far show the gap (Zambia, Nigeria), 0 of 2 DM countries
checked show it (Italy, Spain). Tier 2 is now complete; the next real
test of this hypothesis is whichever Tier 3/4/5 country turns out to be
frontier/lower-rated.

---

## Lead/lag pilot decomposition principle (standing rule)

**For every country in every pilot re-run, report the event-level
agreement rate (% of events with an increase) and event clustering/
independence alongside the p-value — not only when the headline number
looks surprising or borderline.** Established 2026-08-12 after Pakistan:
its p=0.080 read as a near-miss null on the p-value alone, but the
event-level breakdown showed the opposite of a near-miss story — only
38.5% of events showed any increase, and the positive `mean_diff` was
entirely carried by three non-independent events in one crisis cluster
(2008), while the most representative episode (2022-23) was cleanly
negative. That decomposition happened to make the pre-registered
prediction look *more* supported, not less. The rule has to apply
regardless of which direction the decomposition cuts, or it isn't a
methodology — it's picking which results get scrutinized based on
whether scrutiny helps the story already being told. So: every country,
every re-run, the same decomposition, reported before any interpretation
of the p-value — a favorable-looking p-value gets the same scrutiny as
an unfavorable one, and a country whose decomposition doesn't change the
headline read still gets it reported, not skipped as unnecessary. Applies
starting with the 11-country re-run below (Nigeria) and going forward.

---

## Chronological log

### 2026-08-12 — Sri Lanka CE error corrected, source-agnostic sanity-check tool built and run across all 13 countries — **panel changed, 13-country pilot is now stale**

**What, part 1 — the Sri Lanka fix**: user confirmed `S&P, A, 2007-01-23`
in `Sri_Lanka.csv` (carried by CE) is factually wrong — Sri Lanka was in
the B range throughout that period, never remotely single-A; GE's `B+`
for the same window is correct. Fixed via a new, re-run-safe mechanism —
`_corrections.csv`, modeled directly on the existing `_resolutions.csv`
pattern — rather than a hand-edit, since `Sri_Lanka.csv` is mechanically
regenerated by `reconcile_ratings_sources.py` on every session's
regression check and a hand-edit would be silently reverted.
`reconcile_ratings_sources.py` gained `_load_corrections()` /
`_apply_corrections()`, applied to each source's raw dataframe *before*
any cleaning or matching runs, and a `--corrections` CLI flag (defaults
to `_reconciliation/<Country>_corrections.csv`) mirroring `--resolutions`.
Raises loudly if a correction matches no row (stale/mistyped entry
should fail, not silently no-op). New file:
`data/raw/ratings/manual/_reconciliation/Sri_Lanka_corrections.csv`
(1 row, full reasoning in the note field). Re-ran Sri Lanka through
`reconcile_ratings_sources.py` then `ingest_ratings.py`: 118 rows
unchanged, phantom `downgrade` event at 2007-08-01 now correctly reads
`outlook_change`. Full regression check across the other 12 countries
confirmed byte-identical output (the correction only touches Sri Lanka).

**Significant framing point**: this is CE carrying the wrong value,
against the pipeline's CE-preferred default policy — see the "Source
factual-error tracking" section above (renamed from "GE factual-error
tracking") for the full entry (case 5) and the explicit caveat this
prompted about what the GE-4/CE-1 tally can and can't say.

**Diagnostic check requested: does Sri Lanka's borderline p=0.052
lead/lag result change?** Answer: **no — byte-identical, p=0.051515 both
before and after** (n=19, mean_diff=0.020964). Checked without touching
any shared pilot artifact or running `ratings_leadlag_stub.py`'s main
script (per explicit scope instruction) — imported `compute_lead_lag`/
`summarize_lead_lag` directly, used `git show HEAD:...` to reconstruct
the pre-correction panel in memory, ran both through the same functions.
My own prior hypothesis that the spurious A-grade could be affecting the
baseline was wrong: the phantom event's `status` was already
`insufficient_history` in *both* versions — it sits too close to the
2005-2006 panel start to have enough training-window quarters, so it was
already excluded from the actual t-test regardless of its value. The
correction is still correct to make for data integrity (case 5 above,
and it fixes the event log itself — a real `outlook_change` where a fake
`downgrade` used to be), it just doesn't move this particular number.

**What, part 2 — the audit the error exposed**: the user's key
observation was that this error never surfaced as a *conflict* — GE had
no row for 2007-01-23 to disagree with, so conflict detection
structurally couldn't see it. That's a real blind spot: conflict
detection only checks rows where both sources have overlapping entries;
single-sourced rows (CE-only, GE-only, or entire agencies — Zambia's and
Nigeria's Moody's history is 100% GE-only) have never been checked by
anything else. Built `src/data_acquisition/sanity_check_ratings.py`, a
source-agnostic diagnostic (not a re-transcription tool) with three
checks, all reading `data/processed/ratings_panel.csv`:
1. **Implausible jumps** — per (country, agency), flag any consecutive
   `rating_numeric` change >4 notches (Sri Lanka's B+→A was ~9).
2. **Range outliers** — per country, MAD-based modified z-score (3.5
   threshold, Iglewicz & Hoaglin) of `rating_numeric` against that
   country's whole multi-agency history — robust to being dragged toward
   the outlier itself.
3. **Single-source exposure** — per (country, agency), what % of rows
   were never cross-validated (no "confirmed by"/"conflict resolved" in
   `source`).

**Findings (pre-correction run, then confirmed post-correction)**:
9→7 implausible jumps, 17→16 range outliers, both drops accounted for
exactly by Sri Lanka's fixed row disappearing from both lists (it had
been flagged by *both* checks independently, at modified z=-5.40, the
single most extreme outlier in the pre-fix panel). Manual review of the
remaining 7 jumps + 16 outliers: all explainable — SD/RD/D
default-designation transitions produce structurally large jumps by
construction (not transcription errors), and cases like Italy's genuine
1980s-90s AAA/AA+ history only look like an outlier relative to Italy's
*own* whole-history median given its long secular decline. **Conclusion:
Sri Lanka's error looks isolated, not symptomatic — 1 real problem out
of 26 total flags across 13 countries.** No further country files need
revisiting on this basis. Single-source exposure: **695/1512 rows
(46.0%) across all 13 countries have never been cross-validated against
anything** — this is the honest size of what conflict detection alone
was blind to; the sanity-check script is now the only thing checking it
and should be re-run after every future country reconciliation, not just
once. Outputs tracked in `data/processed/ratings_sanity_jumps.csv`,
`ratings_sanity_range_outliers.csv`, `ratings_sanity_single_source.csv`.

**Cross-thread flag — read this if you're the clustering thread on
issue #4**: `data/processed/ratings_panel.csv` changed (Sri Lanka's
2007-08-01 event type flipped from `downgrade` to `outlook_change`) as
of this commit, **after** the 2026-08-12 "Lead/lag pilot re-run at 13
countries" entry below was written — that pilot run used the
pre-correction panel. The diagnostic check above shows the *aggregate
statistic* for Sri Lanka is unchanged (p=0.051515 either way, since the
phantom event was already excluded via `insufficient_history`), but the
*event log itself* is different, and `ratings_leadlag_stub.py` was not
re-run here per explicit scope instruction (that's this thread's
boundary, not this one's). The 13-country pilot and
`stage1_leadlag_pilot_events.csv` should be regenerated against the
current panel before being treated as final — likely a no-op given the
diagnostic result, but should be confirmed by an actual re-run rather
than assumed.

### 2026-08-12 — Spain reconciled: closes Tier 2, corrects an assumption, and completes a perfect 13-for-13 boundary-crossing pattern
**What**: Spain -- second of the Eurozone pair, closes Tier 2 entirely
(13 of the thesis-priority countries now done). No new
reconciliation-logic edge case -- all forward-fills and drops are
already-known categories.

**Trajectory, confirmed per the specific scrutiny requested**: 2010-2012
is a severe collapse -- Moody's alone fell roughly eight notches (`Aaa`
-> `Baa3`) between mid-2010 and mid-2012, densely covered by both
sources, including the 2012 banking-sector bailout period specifically
(S&P/Fitch both down to their lowest points in 2012). The 2014-2019
recovery is equally well captured -- a clear, gradual climb back from
`BBB`/`Baa2` to `A-`/`A` by 2018-2019, matching the well-known recovery
narrative. Confirmed **no** SD/RD/D anywhere, as expected.

**Correcting an assumption from the Italy entry**: that entry speculated
Spain would be "the crossing-with-conflict test case... since it did
cross into the lower end of the same crisis window structurally." That
assumption was wrong. Checking the actual data: Spain's worst points are
Moody's `Baa3` and S&P `BBB-` -- the exact same bottom investment-grade
rung Italy touched. **Spain never crossed the IG/junk boundary either**,
despite a sharper collapse than Italy's. Zero conflicts, full 3-agency
CE coverage, exactly as the non-crossing pattern would predict --
worth explicitly noting the correction rather than quietly dropping the
earlier wrong claim, since getting this kind of thing right by checking
rather than assuming is the entire point of the tracking sections.

**This completes a systematic, corrected check across all 13 countries
reconciled so far (see the GE factual-error tracking section above for
the full table): every one of the 6 countries that crossed the IG/junk
boundary within 2005-2025 produced at least one GE/CE conflict; every
one of the 7 that didn't produced zero.** A perfect 13-for-13 split.
Explicitly flagged as a striking pattern worth taking seriously for the
thesis's data-quality discussion, not yet a settled causal claim -- 13
countries in a thesis-relevance-ordered (not hypothesis-testing-ordered)
sample, and "IG-boundary-crossing" could be a proxy for something else
correlated with it rather than a direct cause.

**Side discovery while running this systematic check, unrelated to
Italy/Spain, flagged and explicitly NOT fixed**: `Sri_Lanka.csv` has one
row -- CE-sourced, `S&P, A, 2007-01-23`, blank outlook -- that's very
likely a transcription error (isolated, no GE row to compare against so
it never surfaced as a conflict, and historically implausible; Sri Lanka
has never been remotely A-rated). Excluding it, Sri Lanka's real best
rating in 2005-2025 is `BB-` (junk), meaning it never crossed the IG
boundary either -- consistent with its known history as a persistently
junk-rated frontier sovereign until its 2022 default, and consistent
with (not contradicting) the 13-for-13 pattern once corrected. Held for
the user's decision on whether to verify and fix -- outside this
session's scope and consistent with how every prior anomaly in this
project has been handled (flag, don't silently change).

**Verified**: 110 reconciled rows in `Spain.csv`. All twelve prior
countries re-run as regression checks -- unchanged. Combined 1,512 rows
pass through `ingest_ratings.py` with only the now-seven known-category
duplicate-action warnings; `test_lag_rules.py` 10/10.

**13-country lead/lag pilot re-run, evaluated against both
pre-registrations (`d23fd6e` and `12f9a3e`)**: next chronological entry
immediately below.

Commit: (pending, this session) · Issue: #3

### 2026-08-12 — Lead/lag pilot re-run at 13 countries: Tier 2 complete, both pre-registrations survive intact, and the working explanation now shows a clean two-bucket split with zero exceptions
**What**: `ratings_leadlag_stub.py` re-run with `ratings_panel.csv` now
covering all 13 countries reconciled so far (the prior 11 plus Italy and
Spain). Evaluated against both pre-registrations now in the record:
`d23fd6e` (currency/commodity trio should be null) and `12f9a3e`
(Eurozone pair should be positive, Spain more cleanly than Italy).

**Results, full 13 countries**:

| country | n_events_tested | mean_diff | % events with increase | p (one-sided) |
|---|---|---|---|---|
| Greece | 34 | +0.0208 | 76.5% | 0.00017 |
| Portugal | 16 | +0.0374 | 93.8% | 0.010 |
| **Spain** | **16** | **+0.0354** | **93.8%** | **0.018** |
| South Africa | 15 | +0.0074 | 80.0% | 0.020 |
| Sri Lanka | 19 | +0.0210 | 78.9% | 0.052 |
| Colombia | 7 | +0.0094 | 71.4% | 0.062 |
| Pakistan | 13 | +0.0312 | 38.5% | 0.080 |
| **Italy** | **13** | **+0.0120** | **84.6%** | **0.107** |
| Nigeria | 13 | +0.0004 | 53.8% | 0.478 |
| Zambia | 18 | -0.0006 | 66.7% | 0.536 |
| Turkey | 15 | -0.0032 | 53.3% | 0.771 |
| Egypt | 22 | -0.0058 | 45.5% | 0.776 |
| Brazil | 10 | -0.0163 | 10.0% | 0.973 |

Pooled (still non-independent, not a real test): p=0.0000121, 67.3% of
all 211 tested events show an increase.

**Against `12f9a3e`, precisely**: the prediction wasn't just "both
positive" -- it specifically called Spain more likely to clear cleanly
than Italy. **Both hits landed**: Spain clears p<0.05 (0.018), Italy
doesn't (0.107) but is still clearly positive-direction (84.6% of events
increase, no negative mean) -- not the "clean negative-direction null"
that would have falsified the prediction. This is a more precise
confirmation than a simple positive/negative call would have been.

**Decomposition for both, per the standing rule**: neither shows a
Pakistan-style divergence -- in both cases the majority direction and
the mean direction agree, and the positive signal is broad-based, not
propped up by one or two outliers. Italy: 11 of 13 events positive,
spread across the whole 2011-2014 window (including a notably large
+0.102 in Dec 2014), with the only 2 negative events both from the later
2017-19 populist-coalition episode. Spain: 15 of 16 events positive,
spread across 2009-2012, with the single negative event being the
earliest one (Jan 2009, pre-dating the main crisis). **Both show
substantial event clustering worth naming explicitly**, not just
inherited as a generic caveat: several dates in each country have 2-3
agencies acting within days to a few weeks of each other (Italy:
Oct 2011, Jan-Feb 2012; Spain: Apr-Jun 2010, Oct 2011, Jan-Feb 2012,
Apr-Jun 2012) -- real non-independence reducing the effective sample
size below the nominal 13/16, consistent with the module's documented
"events are not independent" limitation, concretely instantiated here
rather than left abstract.

**Where H1 stands across all 13 countries -- the requested read**: a
genuinely clean two-bucket split has emerged, with **zero exceptions on
either side**:
- **7 countries classified under "macro-fundamental/persistent
  deterioration" (Greece, Portugal, South Africa, Spain, Sri Lanka,
  Colombia, Italy)**: every single one is positive-direction. 4 clear
  p<0.05 (Greece, Portugal, Spain, South Africa), 2 borderline-positive
  underpowered rather than null (Sri Lanka, Colombia), 1 positive but
  short of significance (Italy). **Not one null or negative-direction
  result in this entire group.**
- **6 countries classified under "other pathway" (political/currency
  shock, commodity-linked distress, or already-priced/entangled
  deterioration): Turkey, Zambia, Brazil, Egypt, Pakistan, Nigeria**:
  every single one is null or near-null. **Not one clears p<0.05
  positive.** Pakistan's raw p=0.080 is the closest to the boundary, but
  its own decomposition (2026-08-12, 11-country entry) showed the
  positive mean was carried by one non-independent 2008 cluster while
  its most representative episode (2022-23) was cleanly negative --
  once decomposed, it reinforces rather than weakens the null bucket.

**This is the second genuine pre-registered test the working explanation
has now survived without a single exception**, following the
currency/commodity trio. That's a real, if still small-sample, result --
worth taking seriously for the thesis's Chapter 5/6 discussion -- but
still not a citable §5.1 result: 13 of 44 countries, non-independent
pooled/within-country events, no formal multiple-testing correction
across 13 country-level tests, and the classification into the two
buckets, while genuinely pre-registered for 5 of the 13 countries
(the trio and the Eurozone pair), was fitted post hoc for the original
5-country pilot (Greece, Portugal, Turkey, Zambia, Sri Lanka). A truly
citable version of this pattern would need it to keep holding on
countries chosen for reasons unrelated to testing it, ideally with a
pre-registered classification for the *next* several countries before
they're reconciled, not just before each pair.

Commit: (pending, this session) · Issue: #4

### 2026-08-12 — Italy reconciled: first of the Eurozone pair, zero conflicts, full CE coverage, never crossed IG boundary despite severe turbulence
**What**: Italy -- first of the Eurozone-crisis pair (Spain closes
Tier 2), reconciled after a written prediction (`12f9a3e`) that both
should show positive-direction lead/lag signal. No new
reconciliation-logic edge case -- one Moody's short-term-scale drop and
one exact-duplicate drop, both already-known categories.

**Trajectory, confirmed per the specific scrutiny requested**: the
2011-12 window is severe and dense -- Moody's alone moved five notches
in about 13 months (Aa2 -> Baa2), with S&P and Fitch also multi-notch
over the same period, all captured with no gaps. The 2018-19
populist-coalition budget standoff shows renewed, well-covered pressure
(Fitch/S&P/Moody's all down to the bottom investment-grade rung). **Italy
never crossed the IG/junk boundary** -- Fitch bottomed at `BBB-` (from
April 2020) and Moody's at `Baa3` (from October 2018, recurring through
2023), the lowest investment-grade notch on each scale, but neither ever
reached the first junk notch (`BB+`/`Ba1`). Confirmed **no** SD/RD/D
anywhere, as expected.

**Zero conflicts, and full 3-agency CE coverage** -- both now recorded
against their respective tracking sections above with Italy-specific
nuance, not just tallied as another data point:
- The **CE coverage-gap hypothesis** (frontier/lower-rated sovereigns
  specifically) is unremarkably consistent: Italy has full Fitch/S&P/
  Moody's coverage in CE, as expected for a DM country and not itself
  new evidence either way.
- The **GE/CE conflict hypothesis** (IG-boundary crossings specifically,
  not general downgrade turbulence) gets a genuinely useful test from
  Italy specifically because of *how* it stayed zero-conflict: despite
  downgrade density comparable to the fiscal-deterioration group's
  crisis periods, Italy never crossed into junk, and had no conflicts --
  consistent with the boundary-crossing-specific version of the
  hypothesis (not just "lots of activity" causing conflicts, since Italy
  had plenty of activity without a crossing and without a conflict).

**Verified**: 132 reconciled rows in `Italy.csv`. All eleven prior
countries re-run as regression checks -- unchanged. Combined 1,402 rows
pass through `ingest_ratings.py` with only the now-seven known-category
duplicate-action warnings (one new Italy/S&P instance); `test_lag_rules.py`
10/10.

**Pilot re-run held for Spain**, per the pair cadence established for
every prior group.

Commit: (pending, this session) · Issue: #3

### 2026-08-12 — PRE-REGISTRATION: Italy/Spain lead/lag prediction (committed before either is reconciled)
**This entry is written and committed before Italy or Spain's ratings
data has been reconciled, and before `ratings_leadlag_stub.py` has been
re-run on either.** The commit timestamp/hash is the audit trail that
the prediction below was fixed in advance -- same discipline as the
currency/commodity trio's pre-registration (`d23fd6e`) and the Stage 2
multi-horizon protocol.

**The prediction**: Italy and Spain are Eurozone sovereign debt crisis
cases structurally similar to Greece and Portugal, both of which cleared
p<0.05 positive. Under the current working explanation (positive
lead/lag signal appears when downgrades follow visible, persistent
macro-fundamental deterioration), **both should show positive-direction
signal**, with **Spain more likely to clear cleanly than Italy** --
Spain's 2010-2012 deterioration was sharper and more fiscally driven,
while Italy's downgrades were more entangled with political instability
and a long-standing, not newly-deteriorating, debt stock. **If either
comes back a clean negative-direction null, the explanation needs
revising.**

**Explicitly recorded: this is a confirmatory test, not a discriminating
one, and carries less evidentiary weight than the currency/commodity
trio did.** Greece, Portugal, Italy, and Spain are four draws from one
correlated event (the Eurozone sovereign debt crisis, roughly the same
years, overlapping macro and market conditions), not four independent
tests of the working explanation -- unlike the trio, which tested the
explanation against three structurally *different* crisis types
(political/currency shock, commodity-linked distress, and this trio's
own internal split on already-priced/entangled deterioration). A
positive result here is consistent with the explanation but doesn't
extend it to new territory the way a currency/commodity-trio positive
would have; a negative result would still be a real problem for the
explanation, since it's specifically predicted to hold in exactly this
kind of case.

**Both will be reported regardless of outcome.**

Not yet run as of this commit. See later chronological entries (above,
since newest-first) for results as each country lands.

Commit: (pending, this session) · Issue: #4 — pre-registration only,
precedes the check

---

### 2026-08-12 — Nigeria reconciled: third and decisive currency/commodity-driven country, zero conflicts (3rd straight), second CE-missing-agency case
**What**: Nigeria -- third and decisive leg of the pre-registered
trio (`d23fd6e`). Flagged in advance by the user: CE has zero Moody's
rows for Nigeria (checked directly on CE's page before reconciling),
the same situation as Zambia. Confirmed this flows through cleanly, no
code change needed -- 15 Moody's rows survive into `Nigeria.csv`, all
GE-sourced, via the same general union-of-months policy that handled
Zambia. Verified explicitly (not just assumed from the Zambia
precedent) by checking the reconciled output's per-agency row counts
directly. No new reconciliation-logic edge case otherwise -- the 3
exact-duplicate drops and the forward-fills are all already-known
categories.

**All three oil-price-driven windows confirmed present with no gaps**:
2015-16 (oil collapse) shows dense multi-agency downgrades -- Fitch
BB- -> B+, Moody's Ba3 -> B1, S&P BB- -> B; 2020 (COVID + oil) is
captured across all three agencies; 2023 (naira devaluation/fuel-subsidy
removal) shows ratings *stabilizing and improving* -- Fitch reaches
`Positive` outlook by mid-2024, Moody's `Positive` by Dec 2023 -- despite
the reforms being domestically painful in the near term. Confirmed
**no** SD/RD/D anywhere, as expected.

**On the IMF-programme-flat-rating question, per the specific ask**:
the 2023 window shows the same qualitative shape Egypt (2016) and
Pakistan (2019) showed during their IMF programmes -- but as far as
could be determined without an independent primary-source check,
Nigeria's 2023 reforms were not under a large formal IMF EFF/standby
arrangement comparable to Egypt's or Pakistan's. If that holds up, it
points toward the pattern being about **credible policy reform signal
generally**, not **IMF programme** specifically -- useful evidence
toward disentangling the two, though flagged as unverified rather than
confirmed, since Nigeria's exact IMF engagement status in this window
wasn't independently checked against a primary source.

**Zero conflicts -- third straight** in the currency/commodity group
(after Egypt and Pakistan), meaning three countries in a row have
produced no test of the GE outlook-reliability hypothesis at all. Now
tracked explicitly as its own pattern in the "GE factual-error tracking"
section above, alongside a specific, checkable hypothesis for *why*:
none of Egypt/Pakistan/Nigeria ever crossed the investment-grade
boundary during the sample, unlike every country in the
fiscal-deterioration group that did -- untested, not yet a finding.

**Second CE-missing-agency case, tracked in a new dedicated section**
(see "CE agency-coverage gap tracking" above): Zambia and Nigeria both
have zero CE rows for Moody's specifically, both African, both
sub-investment-grade throughout the sample. Two cases, explicitly not
yet claimed as a pattern -- but worth deciding whether to check this
proactively on remaining countries rather than continuing to find it
opportunistically, since if it holds it changes how Chapter 3 should
characterize CE as a "primary" source across the full universe.

**Verified**: 67 reconciled rows in `Nigeria.csv`. All ten prior
countries re-run as regression checks -- unchanged. Combined 1,270 rows
pass through `ingest_ratings.py` with only the now-six known-category
duplicate-action warnings (one new Nigeria/S&P instance);
`test_lag_rules.py` 10/10.

**11-country lead/lag pilot re-run, evaluated against the pre-registered
prediction (`d23fd6e`) with the full trio now complete, and against the
new decomposition-principle standing rule** (see that section above):
next chronological entry immediately below.

Commit: (pending, this session) · Issue: #3

### 2026-08-12 — Lead/lag pilot re-run at 11 countries: pre-registered trio complete, none falsify the prediction; decomposition principle applied for the first time as a standing rule
**What**: `ratings_leadlag_stub.py` re-run with `ratings_panel.csv` now
covering 11 countries (the prior 10 plus Nigeria). This completes the
pre-registered trio (`d23fd6e`: Egypt, Pakistan, Nigeria) and is the
first re-run where the new decomposition-principle standing rule (see
that section above) is applied deliberately across multiple countries,
not just the one that happened to look surprising.

**Results**:

| country | n_events_tested | mean_diff | % events with increase | p (one-sided) |
|---|---|---|---|---|
| Greece | 34 | +0.0208 | 76.5% | 0.00017 |
| Portugal | 16 | +0.0374 | 93.8% | 0.010 |
| South Africa | 15 | +0.0074 | 80.0% | 0.020 |
| Sri Lanka | 19 | +0.0210 | 78.9% | 0.052 |
| Colombia | 7 | +0.0094 | 71.4% | 0.062 |
| Pakistan | 13 | +0.0312 | 38.5% | 0.080 |
| **Nigeria** | **13** | **+0.0004** | **53.8%** | **0.478** |
| Zambia | 18 | -0.0006 | 66.7% | 0.536 |
| Turkey | 15 | -0.0032 | 53.3% | 0.771 |
| Egypt | 22 | -0.0058 | 45.5% | 0.776 |
| Brazil | 10 | -0.0163 | 10.0% | 0.973 |

Pooled (still non-independent, not a real test): p=0.00026, 63.7% of
all 182 tested events show an increase.

**Against the prediction, literally**: none of Egypt (p=0.776), Pakistan
(p=0.080), or Nigeria (p=0.478) clears p<0.05 positive. The
pre-registered trio is complete and **the prediction is not falsified**
-- all three currency/commodity-driven countries came back null or
near-null, exactly as committed to in `d23fd6e` before any of the three
was reconciled.

**Nigeria's decomposition, per the specific request and the new standing
rule**: unlike Pakistan, Nigeria's is a genuinely clean, unremarkable
null -- `mean_diff` essentially zero (+0.0004), 53.8% of events showing
an increase (close to an even split, not a lopsided minority propped up
by outliers the way Pakistan's 38.5% was). No dramatic reinterpretation
needed; the p-value and the event-level shape agree with each other.

**Single-sourcing check, per the specific request (Nigeria's Moody's
events are 100% GE-only, 6 of its 13 tested events)**: re-ran the test
excluding those 6 single-sourced events. **Including** them: n=13,
mean_diff=+0.0004, p=0.478. **Excluding** them: n=7, mean_diff=+0.0061,
p=0.324 -- still nowhere near significant either way, but notably the
single-sourced Moody's events pull the mean *down* slightly (4 of the 6
are negative), not up. So single-sourcing is not inflating a spurious
positive result for Nigeria; if anything the opposite. This directly
answers the concern that mattered most here, since Nigeria is the
decisive leg of the trio: the null result does not depend on, or get
manufactured by, the single-sourced Moody's data.

**Turkey and Zambia checked too, per the standing rule applying to every
country, not just the surprising one this time**: both show the same
kind of mean-vs-majority divergence Pakistan did, but in both cases the
decomposition *confirms* the existing null reading rather than
overturning it, unlike Pakistan. Turkey's negative diffs cluster
specifically in the 2018-19 crisis (5 of 7 negative events), its most
representative "political/currency shock" episode -- if anything this
sharpens the null into "the risk score didn't rise ahead of Turkey's
defining crisis specifically," not a diluted average across unrelated
episodes. Zambia's 12-of-18 majority-positive count is offset by 6
negative events spread across its multi-year default saga (2013, 2016,
2018 cluster) with no single dominant outlier cluster -- consistent with
genuine noise across a long, multi-episode history rather than a masked
signal in either direction. Greece, Portugal, South Africa, Sri Lanka,
Colombia, and Brazil were not re-decomposed this round since their
mean-direction and majority-direction already agree (no divergence to
explain) -- per the standing rule this should still be confirmed
explicitly on a future pass rather than assumed indefinitely.

**Event coverage**: Nigeria 13/17 testable (4 excluded, consistent with
prior truncation patterns -- not re-verified in detail this round since
the country-level check was already the focus).

**Trio complete, prediction holds up so far.** This doesn't confirm the
underlying explanation (macro-fundamental-driven downgrades predict the
lead/lag signal; other pathways don't) -- 3 null/near-null results
consistent with a prediction isn't proof the prediction is *right*, only
that it survived a real test where it could have failed. Still not
citable: 11 of 44 countries, still a selected high-signal subset. Italy
and Spain (the remaining Tier 2 countries, both Eurozone-crisis cases
structurally similar to Greece/Portugal) are the next natural check, on
a different axis than this trio.

Commit: (pending, this session) · Issue: #4

### 2026-08-12 — Pakistan reconciled: second currency/commodity-driven country, zero conflicts, IMF-flat pattern replicates
**What**: Pakistan -- second of the currency/commodity-driven trio
(Nigeria closes it out). No new reconciliation-logic edge case; the one
NR-rating drop, three exact-duplicate drops, and NR-outlook occurrences
are all already-known categories.

**All three downgrade waves confirmed present with no gaps**: the 2007-
2009 crisis is dense across all three agencies, and notably shows
Pakistan already brushing near-default territory once before -- S&P hit
`CCC`/`CCC+` (Nov-Dec 2008) before recovering to `B-` by Aug 2009. The
2018-19 wave (Fitch `B`->`B-`, Moody's `B3`/Negative) is captured, and the
2022-2024 balance-of-payments crisis is the deepest of the three --
Fitch reached `CCC-` (Feb 2023), Moody's `Caa3` (Feb 2023) -- genuinely
close to default, consistent with the well-known 2023 near-miss, but
never crossing into SD/RD.

**Critical check, per the specific ask**: confirmed **no** SD/RD/D
anywhere in either source. Pakistan came close to default in 2022-23 but
the data correctly shows it never happened -- no primary-source check
needed since nothing contradicted the expectation.

**IMF-programme-flat-rating pattern replicates, with a caveat on
duration**: during Pakistan's 2019 EFF arrangement, ratings hold roughly
steady rather than showing a fresh downgrade wave -- Fitch `B-`/Stable
(Dec 2018) stays `B-`/Stable (June 2019); Moody's outlook actually
*improves* from Negative (June 2018) to Stable (Dec 2019); S&P holds
`B-`/Stable through the period. Directionally the same pattern Egypt
showed during its 2016 programme (agencies don't downgrade further, and
outlooks stabilize or improve, during/immediately after IMF engagement),
now seen in a second country -- worth treating as a real, repeatable
pattern rather than a one-off, though with a real difference in scale:
Egypt's flat period ran a full ~3 years (2015-2017) before the next
episode; Pakistan's is a much shorter window before the 2022-23 crisis
hit. Worth watching for a third instance if Nigeria's IMF engagement
history shows the same shape.

**Zero conflicts again** -- no test of the GE outlook-reliability
hypothesis this round either, same as Egypt. Two countries into the
currency/commodity group and neither has produced a single conflict,
notably different from every country in the fiscal-deterioration group
(all three of which had at least one candidate conflict). Not
over-reading this yet, but flagged: it's possible GE and CE agree more
often on volatile/frequently-reviewed names than on slower-moving
gradual-deterioration cases, or it could just be these two countries'
specific transcriptions -- not enough data to distinguish those
explanations.

**Verified**: 84 reconciled rows in `Pakistan.csv`. All nine prior
countries re-run as regression checks -- unchanged. Combined 1,203 rows
pass through `ingest_ratings.py` with only the now-five known-category
duplicate-action warnings (one new Pakistan/Moody's instance);
`test_lag_rules.py` 10/10.

**10-country lead/lag pilot re-run, read against the pre-registered
prediction (`d23fd6e`)**: see the next chronological entry immediately
below.

Commit: (pending, this session) · Issue: #3

### 2026-08-12 — Lead/lag pilot re-run at 10 countries: read against the pre-registered prediction (`d23fd6e`) -- neither Egypt nor Pakistan falsifies it, but Pakistan needs unpacking, not just a p-value
**What**: `ratings_leadlag_stub.py` re-run with `ratings_panel.csv` now
covering 10 countries (the prior 8 plus Egypt and Pakistan). This is the
first pilot re-run explicitly evaluated against a pre-registered
prediction rather than assessed after the fact -- the prediction
(`d23fd6e`, committed before either country was reconciled) said Egypt
and Pakistan should both come back null or near-null, and that any one
clearing p<0.05 positive would mean the explanation needs revising.

**Results**:

| country | n_events_tested | mean_diff | % events with increase | p (one-sided) |
|---|---|---|---|---|
| Greece | 34 | +0.0208 | 76.5% | 0.00017 |
| Portugal | 16 | +0.0374 | 93.8% | 0.010 |
| South Africa | 15 | +0.0074 | 80.0% | 0.020 |
| Sri Lanka | 19 | +0.0210 | 78.9% | 0.052 |
| Colombia | 7 | +0.0094 | 71.4% | 0.062 |
| **Pakistan** | **13** | **+0.0312** | **38.5%** | **0.080** |
| Turkey | 15 | -0.0032 | 53.3% | 0.771 |
| **Egypt** | **22** | **-0.0058** | **45.5%** | **0.776** |
| Brazil | 10 | -0.0163 | 10.0% | 0.973 |
| Zambia | 18 | -0.0006 | 66.7% | 0.536 |

Pooled (still non-independent, not a real test): p=0.00022, 64.5% of all
169 tested events show an increase.

**Against the prediction, literally**: neither Egypt (p=0.776) nor
Pakistan (p=0.080) clears p<0.05, so the prediction is **not falsified**
by either country. That's the headline result the pre-registration asked
for, reported as committed to regardless of outcome.

**Pakistan needs unpacking, not just the p-value** -- this is the more
interesting finding of the two, and taking it at face value (p=0.080,
"near-miss, roughly consistent with null") would miss something real.
Pakistan's `mean_diff` is positive, but only 38.5% of its 13 events show
an increase -- *below half* -- meaning the positive mean is being pulled
up by a small number of large outliers while most individual events go
the other way. Checking the event-level detail explains why: three large
positive diffs (+0.136, +0.112, +0.112) all cluster in the 2008 crisis
window (May-Oct 2008, the run-up to Pakistan's first near-default, S&P
`CCC`/`CCC+` by Nov-Dec 2008) -- one crisis episode, non-independent
events sharing overlapping near/baseline windows. Every *other* Pakistan
downgrade -- 2012, 2018-19, and critically **2022-23 (the balance-of-
payments crisis, the episode most archetypally "currency/commodity-
driven," the exact category this prediction is about)** -- shows a
small **negative** diff (-0.02 to -0.04). So the honest read is not "Pakistan
is a near-miss for a positive effect" -- it's "Pakistan's one older,
partially fiscal-flavored crisis (2008) shows a positive signal, and its
newest, most representative currency-crisis episode shows none at all,
consistent with (if anything, more supportive of) the pre-registered
prediction than the raw p-value alone suggests." A reader who only saw
"p=0.080" without this breakdown would draw a weaker or even backwards
conclusion.

**Egypt's within-country pattern shows something similar, worth noting
for future countries even though the aggregate result is unambiguous**:
the 2011 Arab Spring *onset* downgrades show small positive diffs
(+0.039, +0.027), but downgrades later in the same broader episode
(2012-2013) and the entire 2022-24 episode are negative. Aggregate p=0.776
is a clean null regardless, so this doesn't change Egypt's read -- but
combined with Pakistan's pattern, there's a speculative, NOT yet a
finding, observation worth flagging for whoever reads this later: the
positive signal (where it appears at all) seems concentrated in the
*acute onset* of a crisis type a country hasn't been through before,
and weaker or absent on a country's Nth recurrence of a similar stress
pattern -- plausible if agencies/markets have less to be "surprised" by
once a playbook is established, but this is pattern-matching across two
countries' event tables, not a tested hypothesis. Not promoted beyond
this note.

**Event coverage**: Egypt 22/23 testable (1 excluded, pre-2005); Pakistan
13/21 testable (8 excluded, all pre-2005 except none post-panel) --
neither exclusion pattern reflects a coverage gap in either country's
`.csv`, consistent with every prior truncation check in this file.

**Nigeria remains the decisive third data point** the pre-registration
committed to reporting regardless of outcome -- two null/near-null
results don't confirm the hypothesis on their own (that would need the
full trio, and even then this is 10-of-44 countries, not a §5.1 result),
but nothing so far contradicts it either.

Commit: (pending, this session) · Issue: #4

### 2026-08-12 — Egypt reconciled: first currency/commodity-driven country, zero conflicts, three stress episodes confirmed
**What**: Egypt -- first of the currency/commodity-driven trio
(Pakistan, Nigeria to follow) the pre-registration above predicts should
come back null on the lead/lag pilot. Reconciled *after* that
prediction was committed, per the discipline the pre-registration
entry describes. No new reconciliation-logic edge case.

**All three stress episodes, confirmed present with no gaps**: the Arab
Spring downgrade cascade (2011-2013) is extremely dense across all three
agencies -- Fitch BB+ -> B-, Moody's Ba2 -> Caa1, S&P BB -> B-, essentially
a downgrade every 1-3 months for two straight years. The 2016
currency-float/IMF-programme period shows something worth noting
explicitly rather than assuming a gap: ratings stayed *flat* (Fitch/
Moody's/S&P all sat at B/B-/B3 through 2015-2017, with S&P's outlook
even improving to Positive by late 2017) rather than showing a fresh
downgrade wave -- consistent with the real history (the 2016 IMF deal
was a credibility anchor markets and agencies read positively, not a
credit-negative shock), not a data coverage problem. The 2022-2024
currency crisis shows renewed, well-covered downgrade activity across
all three agencies (Fitch B+ -> B, Moody's B2 -> Caa1, S&P B -> B-).
Confirmed **no** SD/RD/D anywhere, as expected.

**Zero conflicts** -- the cleanest reconciliation run since Sri Lanka.
No test of the GE outlook-reliability hypothesis this round; a hypothesis
about *disagreements* can't be tested by a country that produced none.
`NR` appears 3 times, all as S&P outlook values on GE-only rows (no CE
counterpart in that month to compare against) -- correctly left as the
literal string in those rows, since `_normalize_outlook`'s blank
treatment only applies during comparison/merge, not as a blanket scrub
of unmatched single-source data. One of those three (2025-04-01) sits
10 days from a CE-confirmed row with the same rating, correctly flagged
by `ingest_ratings.py`'s duplicate-action warning -- the same known
category as Sri Lanka/South Africa/Colombia's instances, not a new one.

**Verified**: 138 reconciled rows in `Egypt.csv`. All eight prior
countries re-run as regression checks -- unchanged. Combined 1,119 rows
pass through `ingest_ratings.py` with only the four already-known-
category duplicate-action warnings (one new Egypt/S&P instance among
them); `test_lag_rules.py` 10/10.

**Pilot re-run intentionally held** -- per the pair cadence, waits for
Pakistan.

Commit: (pending, this session) · Issue: #3

### 2026-08-12 — PRE-REGISTRATION: Egypt/Pakistan/Nigeria lead/lag prediction (committed before any of the three is reconciled)
**This entry is written and committed before Egypt, Pakistan, or
Nigeria's ratings data has been reconciled, and before
`ratings_leadlag_stub.py` has been re-run on any of them.** The commit
timestamp/hash on this entry is the audit trail that the prediction
below was fixed in advance, not fitted after seeing which of the three
clears p<0.05 -- the same discipline as the H2 multi-horizon
pre-registration (2026-08-11, below), applied here because the
explanation this entry is testing was itself built *post hoc* from the
5-, 7-, and 8-country pilot results already observed (Greece, Portugal,
South Africa, Sri Lanka, Colombia positive/borderline-positive; Turkey,
Zambia, Brazil null/negative) -- a genuine prediction, made before new
data, is the only way to tell whether that explanation is real or just a
story that fits what's already been seen.

**The working explanation being tested**: the ML risk score deteriorates
ahead of a downgrade when that downgrade is preceded by visible,
persistent **macro-fundamental** deterioration -- Greece, Portugal, and
South Africa all clear p<0.05 positive; Sri Lanka and Colombia are
directionally consistent (borderline-positive, underpowered rather than
null) -- and does *not* when the downgrade's driver runs through a
pathway Stage 1's feature set doesn't observe: **political/currency
shock** (Turkey), **commodity-linked chronic distress** (Zambia), or
deterioration that was **already priced in or entangled with political
events** by the time it showed up as a downgrade (Brazil).

**The prediction, fixed now**: Egypt, Pakistan, and Nigeria are all
currency- and commodity-driven cases, the same category the explanation
says should fail. If the explanation holds, **all three should come back
null or near-null** (p not clearing 0.05, and/or `mean_diff` flat or
negative) when reconciled and run through the pilot. **If any one of the
three clears p<0.05 with a positive direction, the explanation needs
revising, not extending** -- it would mean "currency/commodity-driven"
isn't actually the operative distinction, and whatever the real
distinction is would need to be re-derived from scratch rather than
patched with a new post-hoc carve-out for the exception.

**All three will be reported regardless of outcome** -- a clean 3-for-3
null, a mixed result, or a clean miss for the hypothesis are all
reportable results, not just the one that confirms the explanation.
Consistent with how the H2 multi-horizon protocol and every lead/lag
pilot addition so far (including Colombia, which did not confirm South
Africa outright) have been reported unconditionally.

Not yet run as of this commit -- Egypt is next, reconciled immediately
after this entry is committed. See later chronological entries (above,
since newest-first) for results as each of the three lands.

Commit: (pending, this session) · Issue: #4 — pre-registration only,
precedes the check

---

### 2026-08-12 — Colombia reconciled: tie-breaker for the fiscal-deterioration trio, new NR-outlook policy
**What**: Colombia -- third of Tier 2, the tie-breaker within the
fiscal-deterioration/non-Eurozone group after South Africa (positive
lead/lag signal) and Brazil (null). No new reconciliation-logic edge
case in the sense of a bug -- the one conflict it produced turned into a
genuine, permanent policy addition instead.

**Trajectory, confirmed per the specific scrutiny requested**: pre-2021
investment-grade period is dense with no gaps in either source. The 2021
crossing is a clean, tight, single boundary event -- **S&P first** into
junk (BB+, 2021-05-19), **Fitch follows** about two months later (BB+,
2021-07) -- and critically, **Moody's held Baa2 continuously through
2021** (Baa2/Negative Dec 2020 -> Baa2/Stable Oct 2021), only crossing
into junk much later, June 2025 (Baa3). So this was a **partial**, not
universal, loss of investment grade in 2021 -- 2 of 3 agencies, not all
3 -- a real structural difference from Greece/Portugal/South
Africa/Brazil, all of which eventually lost IG across all three
agencies. Confirmed **no** SD/RD/D anywhere, as expected.

**One conflict, resolved by a new permanent policy rather than a
one-off resolutions.csv entry**: S&P, 2025-06 -- GE's outlook was the
literal string `NR`, CE's was `Negative`, same rating (`BB`). Before
treating this like South Africa/Brazil's "GE asserted something wrong"
cases, checked how often GE uses `NR` as an outlook in this file: 8 of
33 GE S&P rows -- frequent enough to be a convention ("no outlook
currently tracked"), not a one-off error. The user's call: encode `NR`
in the *outlook* field as equivalent to blank in `_outlook_eq` and
`_prefer_outlook`, explicitly and permanently distinguished in the
module docstring (point 11) from `NR` in the *rating* field (which still
means withdrawn coverage and is dropped outright by `_drop_not_rated`,
point 5) -- same token, two fields, two unrelated meanings, kept
deliberately unconflated. Verified with synthetic tests covering both
directions (GE-side NR, CE-side NR) and the both-NR edge case (must
yield blank, not the literal string `"NR"`) before touching real data.
Applied the policy, re-ran Colombia: the conflict **dissolved
automatically** -- CE's `Negative` won, no resolutions.csv entry needed,
exactly as predicted before implementing anything.

**GE factual-error hypothesis: explicitly NOT extended by this case**
(see the "GE factual-error tracking" section above, now with a dedicated
note on this). South Africa and Brazil were GE *asserting* an
incorrect outlook; Colombia was GE *declining to assert one at all* --
a different failure mode, arguably not an error in the same sense. Kept
out of the tracking table on purpose, per the user's explicit
instruction not to count it as a third data point. The hypothesis
remains at 2 confirmed cases, untested by Colombia in either direction.

**Verified**: 94 reconciled rows in `Colombia.csv` (93 before the NR
policy resolved the one conflict, +1 after). All seven prior countries
re-run as regression checks -- unchanged (172/1, 170/2, 118/0, 108/0,
45/0, 137/1, 137/1) -- confirming the `_outlook_eq`/`_prefer_outlook`
change is correctly scoped and doesn't touch any already-settled case.
Verified specifically with synthetic tests that every existing
`_outlook_eq` behavior (watch-qualifier equivalence, blank-agrees-with-
anything, genuine conflicts staying conflicts) is unaffected, since this
change touches genuinely shared code paths every country's reconciliation
runs through. Combined 981 rows pass through `ingest_ratings.py` with
only the three already-known duplicate-action warnings (Sri Lanka,
South Africa, and a new Colombia/Fitch instance of the same category,
31 days apart); `test_lag_rules.py` 10/10.

**Completes the fiscal-deterioration/non-Eurozone trio.** Lead/lag pilot
re-run (8 countries) follows immediately below.

Commit: (pending, this session) · Issue: #3

### 2026-08-12 — Lead/lag pilot re-run at 8 countries: Colombia leans positive but doesn't clear the bar, tilts the tie-break toward "Brazil is the outlier"
**What**: `ratings_leadlag_stub.py` re-run with `ratings_panel.csv` now
covering 8 countries (the prior 7 plus Colombia, committed immediately
before this run). No code changes needed.

**Results**:

| country | n_events_tested | mean_diff | % events with increase | p (one-sided) |
|---|---|---|---|---|
| Greece | 34 | +0.0208 | 76.5% | 0.00017 |
| Portugal | 16 | +0.0374 | 93.8% | 0.010 |
| South Africa | 15 | +0.0074 | 80.0% | 0.020 |
| Sri Lanka | 19 | +0.0210 | 78.9% | 0.052 |
| **Colombia** | **7** | **+0.0094** | **71.4%** | **0.062** |
| Turkey | 15 | -0.0032 | 53.3% | 0.771 |
| Brazil | 10 | -0.0163 | 10.0% | 0.973 |
| Zambia | 18 | -0.0006 | 66.7% | 0.536 |

Pooled (still non-independent, not a real test): p=0.0000936, 70.1% of
all 134 tested events show an increase.

**Colombia's event coverage, per the standing practice of reporting this
explicitly**: 7 tested, 8 excluded -- 7 `no_preceding_data` (all
pre-2005: 1999-2002, before the panel window, same story as Brazil's
exclusions) and 1 `event_after_panel_end` (a 2026-04 S&P downgrade dated
beyond the risk-labels panel's coverage). Neither of Colombia's
exclusion reasons reflects a real coverage gap in `Colombia.csv` itself.

**Reading the tie-break** (the specific question this country was
chosen to answer, per the 2026-08-12 Colombia entry above): Colombia
does not cleanly resolve it, but leans toward one side. It doesn't clear
the informal p<0.05 bar the way South Africa did, but it's directionally
consistent with South Africa -- positive `mean_diff`, 71% of events
showing an increase -- sitting in the same borderline-positive territory
as Sri Lanka (p=0.052) rather than anywhere near Brazil's actual
negative-direction null (10% of events increasing, `mean_diff`
negative). So the fiscal-deterioration group is now 2-of-3 positive-
leaning (one confirmed, one borderline) against 1-of-3 clean null,
rather than an even split. That's meaningfully different from "the
framing doesn't work" -- it reads more like "Brazil is the country that
needs a separate explanation" than like "graduated fiscal deterioration
doesn't predict the lead/lag mechanism."

**On whether small-N is confounding these comparisons** (the user's
explicit concern, given Brazil's 10/19 and now Colombia's 7/15): worth
taking seriously but not the whole story. Colombia (n=7) is the smallest
n so far and sits right at the p<0.05 boundary from below -- a few
events flipping direction could move it either side, so "underpowered
to confirm a real but modest effect" is a more honest read than "null."
But n alone doesn't explain the pattern: Portugal has only 16 events and
the single strongest p-value in the pilot, because its effect size
(`mean_diff` +0.037, the largest of any country) is large enough to
clear the bar even at modest n. So event count affects *precision* of
the estimate (consistent with the Stage 2 EM-satellite small-N caveat
already documented elsewhere in this file), but the underlying effect
size still looks like the dominant factor in which countries clear the
bar or not.

**Still not citable**: 8 of 44 countries, still a selected high-signal
subset, same caveats as before (non-independent pooled events, Zambia/
Moody's GE-only single-sourcing, feasibility check only).

Commit: (pending, this session) · Issue: #4

### 2026-08-12 — Lead/lag pilot re-run at 7 countries: South Africa/Brazil split, doesn't resolve the generalization question
**What**: `ratings_leadlag_stub.py` re-run with `ratings_panel.csv` now
covering 7 countries (the original 5 plus South Africa and Brazil,
committed immediately before this run). No code changes needed -- the
script already reads whichever countries are present in the panel
dynamically.

**Results**:

| country | n_events_tested | mean_diff | % events with increase | p (one-sided) |
|---|---|---|---|---|
| Greece | 34 | +0.0208 | 76.5% | 0.00017 |
| Portugal | 16 | +0.0374 | 93.8% | 0.010 |
| **South Africa** | **15** | **+0.0074** | **80.0%** | **0.020** |
| Sri Lanka | 19 | +0.0210 | 78.9% | 0.052 |
| Turkey | 15 | -0.0032 | 53.3% | 0.771 |
| **Brazil** | **10** | **-0.0163** | **10.0%** | **0.973** |
| Zambia | 18 | -0.0006 | 66.7% | 0.536 |

Pooled (still non-independent per the module's documented limitation,
not a real test): p=0.00016, 70.1% of all 127 tested events show an
increase.

**Coverage check, per the specific ask**: South Africa has **full event
coverage** -- all 15 downgrade events fall within the panel window and
are testable, zero excluded. Brazil has 19 downgrade events total but
only 10 testable -- the other 9 are excluded as `no_preceding_data`, and
all 9 are pre-2005 (1987-2002), i.e. they predate the Stage 1 panel's
2005 start entirely. This is Brazil's rating history genuinely extending
further back than the thesis's sample window, not a transcription or
coverage gap -- Brazil's `Brazil.csv` itself has no missing-history
problem, the panel just correctly can't test an event it has no
pre-event quarters for. Neither South Africa nor Brazil hit the script's
separate `insufficient_history` flag (too few valid quarters *within* an
otherwise-present window) -- that hit only Portugal (1 event) and Sri
Lanka (1 event) in this run, unchanged from the 5-country pilot.

**What this does and doesn't say about generalization beyond
Eurozone-style crises** -- the specific question this pair was chosen to
test: the result is a **split, not a resolution**. South Africa clears
the informal p<0.05 bar with the expected positive direction (comparable
in significance to Portugal, though a noticeably smaller effect size --
`mean_diff` +0.007 vs Portugal's +0.037 and Greece's +0.021). Brazil
shows no effect at all, and not just a null -- its `mean_diff` is
*negative* and only 1 of its 10 events shows any pre-downgrade increase,
a result that reads more like Turkey's null than like South Africa's
positive signal. So within the same crisis-type category (graduated
fiscal deterioration, non-Eurozone) the mechanism shows up in one country
and not the other. That's a genuinely different and more specific
finding than either "the mechanism generalizes beyond Eurozone crises"
or "it doesn't": it suggests **crisis-type category alone doesn't
predict whether the mechanism shows up** -- country-specific factors
(possibly: how gradual/anticipated the deterioration was, how much the
market/ML risk score had already priced in before the first agency
moved, or something about Brazil's specific 2015-2016 sequence) may
matter as much as or more than the Eurozone/non-Eurozone distinction the
pilot was designed around. Not something to resolve from 2 additional
countries -- flagged as the open question the *next* pair (Egypt/
Pakistan/Nigeria, the currency/commodity-driven group) should be read
against, alongside Colombia (the third fiscal-deterioration country,
still pending) as a tie-breaker within this same category.

**Still not citable**: 7 of 44 countries, still a selected high-signal
subset, same caveats as the 5-country pilot (non-independent pooled
events, GE-only single-sourcing for Zambia/Moody's, feasibility check
only).

**Not yet committed** -- this entry and the Open Items table update are
staged locally; `data/processed/stage1_leadlag_pilot_events.csv` was
regenerated by the re-run. Ratings reconciliation work is committed
separately under "Refs #3"; this is a Stage 1 pilot-analysis update, a
different concern, held here pending direction on how to commit it.

### 2026-08-12 — Brazil reconciled: completes the South Africa/Brazil pair, revises the GE factual-error hypothesis
**What**: Brazil -- second of Tier 2, the pair with South Africa
specifically chosen to test whether H1's lead/lag mechanism generalizes
beyond Eurozone-style crises (Greece/Portugal) to a different kind of
graduated fiscal-deterioration case. No new reconciliation-logic edge
case surfaced (raw-paste CE format continues to work cleanly on real
data, one routine NR drop, one routine exact-duplicate drop).

**Trajectory, confirmed per the specific scrutiny requested**: pre-2015
investment-grade period captured cleanly by all three agencies
(2008-2014), and the 2015-2016 downgrade-to-junk sequence lands exactly
as the well-known Petrobras/recession story describes -- **S&P first**
into junk (BB+, 2015-09-09), **Fitch next** (BB+, 2015-12-16), **Moody's
last** (Ba2, 2016-02-24), all three within a ~5-month window. No SD/RD/D
anywhere, as expected -- the default-designation override correctly
never fired (Brazil has no default history in the 2005-2025 window).

**One genuine conflict, resolved via primary-source research**: Moody's,
2018-04-09 -- GE said `Ba2/Negative`, CE said `Ba2/Stable`. Confirmed CE
correct at high confidence (Itaú BBA reporting; Trading Economics'
rating history; independently corroborated by Brazil's National
Treasury referencing this exact 2018 move in a 2024 statement). Checked
this specific conflict against the South-Africa-derived
multi-agency-clustering hypothesis before assuming it applied: no other
agency acted anywhere near April 2018 (nearest are Jan/Feb 2018, both
`Stable`, both S&P/Fitch) -- so the clustering mechanism does **not**
explain this case, which turned the investigation in a different,
better-supported direction (see below).

**GE factual-error hypothesis revised, not just extended** (see the "GE
factual-error tracking" section above for the full table and rationale):
the original multi-agency-clustering idea was specifically tested here
and failed to explain Brazil's case, but Brazil's error turned out to
share a *different*, more precise commonality with South Africa's: in
both, **GE got the letter rating right and only the outlook wrong** --
South Africa borrowed a different agency's concurrent outlook; Brazil
carried forward the *same* agency's own prior outlook (Ba2/Negative from
May 2017) instead of picking up the April 2018 outlook-only revision.
One shared symptom (GE unreliable on outlook-only updates specifically,
reliable on rating levels), two different proximate mechanisms getting
there. Turkey's original case (a rating-level error, `Ba3`/`Baa3`)
remains a separate, unexplained outlier under this revised
characterization -- not forced into the pattern just because it's also
a GE error. This is now the standing hypothesis to watch across the rest
of Tier 2: outlook-only conflicts (rating agrees, outlook doesn't, not a
watch-qualifier asymmetry) are the specific shape to look for.

**Verified**: 137 reconciled rows in `Brazil.csv`. All six prior
countries re-run as regression checks -- unchanged. Combined 887 rows
pass through `ingest_ratings.py` with only the two already-known
duplicate-action warnings; `test_lag_rules.py` 10/10.

**Completes the first Tier 2 pair.** Lead/lag pilot re-run (7 countries:
the original 5 plus South Africa and Brazil) follows immediately in the
next entry below, per the user's plan to re-run after each pair rather
than after every single country.

Commit: (pending, this session) · Issue: #3

### 2026-08-12 — South Africa reconciled: first Tier 2 country, raw-paste path validated on real data, second confirmed GE factual error
**What**: South Africa -- first of Tier 2, resequenced ahead of the rest
per the lead/lag pilot's open generalization question (see the
2026-08-11 pilot entry below: does the lead/lag mechanism hold outside
Eurozone-style crises?). Also the first country transcribed entirely via
the raw-paste workflow (CE's combined `rating (Outlook)` text pasted
straight into the `rating` column, no manual pre-splitting) -- validating
both branches of the pre-Portugal fix on real production data for the
first time: `Ba2 (Stable)` (letter+outlook) and bare `(Positive)`
(outlook-only, no letter) both split and forward-filled cleanly, no new
edge case, no crash.

**Trajectory check, per the specific scrutiny requested**: confirmed the
full 2012-2020 graduated downgrade is captured densely by both sources
across all three agencies, no suspicious gaps -- Fitch BBB+(2012) ->
BBB(2013) -> BBB-(2015) -> BB+(2017) -> BB(2020); Moody's the last to
lose investment grade (Ba1, March 2020), consistent with the well-known
history. Confirmed **no** SD/RD/D anywhere -- the default-designation
override correctly never triggered, since South Africa has no default
history for it to (mis)fire on.

**One genuine conflict, resolved via primary-source research (not
auto-resolved)**: Fitch, 2020-11-20 -- GE said `BB-/Stable`, CE said
`BB-/Negative`. Confirmed CE correct at high confidence: Fitch's own
release was titled "Fitch Downgrades South Africa to 'BB-'; Outlook
Negative," independently corroborated by South Africa's National
Treasury media statement the next day. The user's diagnosis for *why*
GE was wrong, not just *that* it was: November 2020 was a multi-agency
round -- Fitch and Moody's both downgraded with Negative outlooks while
S&P separately affirmed BB- with a Stable outlook -- and GE's `Stable`
looks like cross-attribution from S&P's action onto Fitch's.

**New tracking thread started, not just a one-off note**: this is the
**second** confirmed case (after Turkey's 2015-12 Moody's `Ba3`-vs-`Baa3`)
of GE carrying a value primary sources show was factually *wrong*, not
just coarser or incomplete -- a different failure mode from the
month-precision and default-blackout gaps already well-documented
per-country. Added a new **"GE factual-error tracking"** section above
(before this log) to track future instances against a specific,
checkable hypothesis: do GE's factual errors cluster around
multi-agency rounds where several agencies move close together? South
Africa's case has direct evidence for that mechanism (the S&P/Fitch
cross-attribution); Turkey's doesn't have confirming or disconfirming
evidence either way. Two points isn't a pattern -- explicitly flagged as
open, to be watched across the rest of Tier 2 (Brazil, Colombia, Egypt,
Pakistan, Nigeria, Italy, Spain), not asserted as a finding yet. If it
holds up, this becomes a citable, mechanism-specific reliability
statement for the thesis's data-quality discussion (Appendix B
candidate) rather than an unquantified "GE is sometimes wrong" caveat.

**Also confirmed, no code change needed**: one new *instance* (not a new
category) of the known duplicate-action-warning pattern -- S&P, a
confirmed CE+GE November row followed by an unconfirmed GE-only December
row 17 days later, same rating. Structurally identical to Sri Lanka's
month-boundary case, just a new occurrence.

**Verified**: 137 reconciled rows in `South_Africa.csv` (136 before the
conflict resolution, +1 after). All five prior countries re-run as
regression checks -- unchanged (172/1, 170/2, 118/0, 108/0, 45/0).
Combined 750 rows pass through `ingest_ratings.py` with only the two
known duplicate-action warnings (Sri Lanka's and this session's new
South Africa one); `test_lag_rules.py` 10/10 (suite has grown with Stage
2 checks since Zambia, unrelated to this work).

**Explicitly held per the user's instruction**: the lead/lag pilot
(`ratings_leadlag_stub.py`) is not being re-run on South Africa alone --
it re-runs after Brazil, the second half of this specific pair, per the
resequencing rationale above.

Commit: (pending, this session) · Issue: #3

### 2026-08-11 — H2 multi-horizon robustness check: results (0 of 9 regression combinations clear the bar)
**What**: Ran the protocol pre-registered and committed in the entry
directly below this one (`354afdb`/`99d118e`, both preceding this run).
`src/stage2_signal/multi_horizon_robustness.py` reuses the exact
satellite-candidate population and feature columns already in
`stage2_signal_panel.parquet`, recomputes only the target return for
monthly (30d) and semi-annual (182d) horizons via a new forward as-of
daily-price lookup (`stage2_utils.forward_price_asof`), reuses the
existing quarterly target as-is, and runs the identical, NOT re-tuned
LASSO/Random Forest/XGBoost walk-forward comparison
(`model_comparison.run_walk_forward`, imported directly rather than
reimplemented) at all three. Population size is stable across horizons
(monthly 265 / quarterly 274 / semi-annual 263 target-realized rows out
of 554), so differences below reflect the horizon, not a smaller sample.

**Full results** (`data/processed/stage2_multi_horizon_robustness_summary.csv`,
all 18 horizon x model x framing combinations, all reported per the
pre-registered commitment):

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

**H2 bar (IC>0.05 and p<0.05, thesis §1.5) -- 0 of 9 regression
combinations clear it.** Quarterly/LASSO remains the closest (already
reported: +0.076, p=0.205). Monthly is essentially flat (+0.0015,
p=0.495) rather than stronger, and semi-annual actually turns negative
(-0.049, p=0.714) with an AUC (0.467) below chance. Since none of the 9
regression tests reach significance even before any multiple-testing
adjustment, the Harvey/Liu/Zhu (thesis §2.8) correction that would be
needed if something *had* looked significant across this 9-test family
isn't the operative issue here -- the finding is a clean, uncorrected
null across the whole pre-registered family, which is a *stronger*, not
weaker, form of "H2 not rejected" than the single-horizon quarterly
result alone.

**One flagged, non-bar observation**: monthly/LASSO's classification AUC
(0.617) is the highest AUC value seen anywhere across Stage 2's full
investigation (quarterly 0.560; the full-EM-universe power diagnostic's
best was ~0.50). This is genuinely interesting but explicitly **not**
promoted into a claim here: thesis §1.5's H2 test is defined via the
regression/IC framing only -- no significance threshold was ever
pre-specified for AUC, and with 9 model x horizon combinations now in
play, treating one AUC number as a finding without a matching
significance test and multiple-testing accounting would be exactly the
kind of post-hoc mining §2.8 warns against. Recorded as a lead for §7.4
future work (a monthly-horizon classification-only follow-up would need
its own pre-registration), not folded into the H2 conclusion.

**Bottom line for §6.2/§7.4**: "this specification doesn't recover a
premium" (already the conclusion from the earlier power-vs-absence
diagnostics) now generalizes across three pre-registered horizons, not
just the one originally built to match rebalancing frequency -- horizon
choice was a plausible alternative explanation for the null and this
check closes it off, at least for the monthly-to-semi-annual range and
this fixed model specification.

Commit: `9f8e99f` · issue #5 (already closed) — results of the
pre-registered check below

---

### 2026-08-11 — PRE-REGISTRATION: H2 multi-horizon robustness check (committed before running)
**This entry is written and committed before the check below it is run or
its results are known.** The commit timestamp/hash on this entry is the
audit trail that the protocol below was fixed in advance, not adjusted
after seeing which horizon(s), if any, clear H2's bar — the standard
thesis §2.8 (Harvey, Liu & Zhu, 2016) argues for on multiple testing in
financial ML, applied here to our own testing rather than only cited
against the literature.

**Motivation**: Stage 2's target return horizon (thesis §4.3.2, "excess
total return ... in the subsequent quarter") was set to match the
pipeline's quarterly rebalancing frequency (thesis §4.4.3's base case),
not derived from any theoretical claim about which horizon sovereign
return predictability should appear at. Thesis §2.4's factor literature
(Ilmanen 1995; Koijen, Moskowitz, Pedersen & Vrugt 2018 on carry;
Asness, Moskowitz & Pedersen 2013) documents fixed-income
momentum/carry effects across a 1-12 month range, not specifically at
~3 months — so it's a legitimate open question whether Stage 2's
already-built quarterly-horizon result (mean IC +0.076, p=0.205 -- not
significant; AUC 0.560) would look different at a shorter or longer
horizon.

**Protocol, fixed now**:
- Three horizons: monthly (30 calendar days forward), quarterly (the
  existing ~91-day/next-rebalancing-date target, reused as-is from
  `stage2_signal_panel.parquet` -- not recomputed), semi-annual (182
  days forward).
- **Same population** at all three horizons: the identical (country,
  rebal_date) rows already in the quarterly panel (Stage 1's EM
  `satellite-candidate` cross-sections) -- only the forward-return
  window changes, not the observation calendar (which stays quarterly;
  this is not a re-run of Stage 1 at monthly/semi-annual frequency).
- **Same features** at all three horizons -- reused unchanged from the
  existing panel (features are as-of `rebal_date`, horizon-independent
  by construction).
- **Same model specification** at all three horizons -- identical LASSO/
  Random Forest/XGBoost hyperparameters as the production Stage 2
  pipeline (`configs/params.yaml: stage2_signal`), explicitly NOT
  re-tuned per horizon, so any IC/AUC difference reflects the horizon,
  not a better-fit model.
- **All three results will be reported, unconditionally.** If exactly
  one horizon clears IC>0.05 and p<0.05, that will be reported as "1 of
  3 pre-registered horizons clears H2's bar" (with the appropriate
  multiple-testing caveat), not as "H2 holds at horizon X" in isolation.
  If none clear it, that's reported too, consistent with how the
  quarterly-only result and the two power-vs-absence diagnostics were
  already reported without adjustment.

Not yet run as of this commit. See the next chronological entry (above,
since newest-first) for results.

Commit: `354afdb` · issue #5 (already closed) — pre-registration only,
precedes the check

---

### 2026-08-11 — Stage 2 power-vs-absence diagnostics: two exploratory runs, not part of the tracked pipeline
**What**: Immediately after Stage 2's build (entry below — read that one
first), ran two scratch diagnostics to answer one question before H2's
result gets written up: is the weak AUC (0.560) / non-significant IC
(+0.076, p=0.205) a **statistical-power problem** (Stage 1's
`satellite-candidate` gate leaves too few EM rows per quarter, median
4-8, to detect a real premium) or an **absence of premium** this
specification can find? Both scripts live only in the session scratchpad
(not committed) — they reuse `stage2_utils` primitives and the identical
production feature set/hyperparameters (deliberately no re-tuning), so
the finding is scoped to "this specification," not a general claim.

**Diagnostic 1 — full 26-country EM universe**, not gated by Stage 1's
`satellite-candidate` tier: 72 walk-forward folds, ~14-15 names/quarter
median, 1,100 pooled test observations (4.4x the real pipeline's 251). If
the null were a power problem, this should show a materially stronger
signal. It doesn't: LASSO regression mean IC goes **negative** (-0.092,
one-sided p=0.941 — wrong-signed relative to H2), Random Forest also
negative (-0.027), XGBoost weakly positive but non-significant (+0.019,
p=0.292). Classification AUC for all three models collapses to
**0.48-0.50** — indistinguishable from chance, despite 4.4x the data.
This breaks the pipeline's own logical chain deliberately (thesis
§4.4.1's satellite sleeve is explicitly gated on Stage 1's output; this
diagnostic isn't a candidate replacement for that design) — it's a probe,
not a pipeline change.

**Diagnostic 2 — split the real pipeline's existing 52 folds by quarter
population size** (`n_test`, already stored in
`stage2_model_comparison.csv` — no re-fitting). Better-populated quarters
do not show a stronger signal: `n_test>=8` (8 folds, 99 obs) gives mean
IC **-0.004** vs the full sample's +0.076; `n_test>=15` (2 folds, 38 obs)
gives +0.085 — no clean monotonic strengthening with population size.
(These sub-splits are only 2-8 folds each, limited standalone power — the
*direction*, not the magnitude, is the informative part.)

**Reading**: both diagnostics point away from "insufficient power" and
toward "this specification doesn't recover a detectable premium" — a
narrower, more defensible claim than "no EM excess-return premium
exists." The AUC-to-~0.50 collapse on 4.4x the observations is the single
strongest piece of evidence, since it's less sensitive than the IC
numbers to the one real confound diagnostic 1 introduces: scoring the
full EM universe isn't a clean "same population, more data" scale-up, it
also dilutes toward calmer, lower-dispersion EM countries Stage 1 never
flags as high-risk — so a weaker IC there is *consistent with* a power
story without fully ruling it out on composition grounds alone.
**Because neither the feature set nor the hyperparameters were re-tuned
for the different population**, the honest scope of this finding is "this
feature set + these three fixed-hyperparameter models don't recover a
premium here" — not "no premium is recoverable by any specification."
That distinction should carry directly into how §6.2 (does a premium
exist / what drives it) and §7.4 (future work) characterize the result —
richer market-based features, re-tuned hyperparameters per population, or
an alternative EM universe definition are all still open, untested
alternatives, not ruled out by this pilot.

**This also revises the SHAP caveat from the build entry below**: that
entry hedged the "macro fundamentals dominate, market signals shrink to
zero" SHAP result as "plausibly just a data-richness artifact" of
market-feature missingness. These two diagnostics undercut that hedge —
if it were purely a richness artifact, the full-universe diagnostic
(same feature set, same richness limitation, just more rows) should have
at least moved AUC off of chance; it didn't. CLAUDE.md's "Stage 2 signal"
section has been rewritten to carry this fuller picture rather than the
original single-sentence hedge.

Commit: `efcbbd1` · issue #5 (already closed) — informational follow-up,
no code/pipeline changes

---

### 2026-08-11 — Stage 2 (compensated EM sovereign risk identification) built
**What**: `src/stage2_signal/` built end to end — `stage2_utils.py`
(shared primitives, mirroring Stage 1's `clustering_utils.py` split
between full-sample diagnostic and walk-forward production modes),
`build_stage2_panel.py` (§4.3.2 target + §3.3 Stage-2-scoped feature
construction), `model_comparison.py` (§4.3.3 walk-forward LASSO/RF/XGBoost
comparison), `build_return_signals.py` (§4.3.5 walk-forward-safe
production signal + top-5/10/15 output), `feature_importance.py` (§4.3.4
SHAP). Independent of the ratings-transcription/lead-lag-pilot work above
— reads only Stage 1's already-built `stage1_risk_labels.parquet` and
`stage1_feature_matrix_core.parquet`, doesn't touch either. Full writeup
in CLAUDE.md "Stage 2 signal"; summarized here.

**Confirmed before building, per standing instruction not to approximate
data gaps silently**:
- No coupon-rate/cashflow field exists anywhere in the raw bond pull (11
  fields total, confirmed against `bond_data_pull_reconstructed.py`'s
  field list) — the bonds are generic benchmark composites (`XX10YT=RR`),
  not individually-cashflowed issues. Thesis §4.3.2's "price return +
  coupon" total return is therefore not literally constructible. Built
  instead: a price-return proxy, using `DIRTY_PRC` (embeds accrued
  interest, closest available proxy) where available, `CLEAN_PRC`/
  `MID_PRICE`/a BID-ASK synthetic mid otherwise — flagged per row via
  `has_income_component`, not presented as equivalent. Real, structural,
  and now documented rather than glossed over.
- No 3-month US T-bill series existed anywhere in the repo (needed for
  the risk-free leg). Closed cleanly: added `DGS3MO` to `macro_pull.py`'s
  `FRED_SERIES` (key-free, same pattern as every other FRED series) and
  re-ran the macro pull — not a Stage-2-local hack.
- Kazakhstan and Morocco (the 2 EM countries with no `MID_PRICE`/
  `CLEAN_PRC` at all) were nearly excluded from Stage 2 entirely; checking
  their raw columns found BID (~99-100% coverage) and ASK (74-100%),
  added as a last-resort synthetic-mid fallback so all 26 EM countries get
  a price-based target instead of 24.

**Population-size finding, confirmed before going deep on any one
algorithm (per the standing instruction)**: Stage 1's EM
`satellite-candidate` tier only has rows in 65 of 84 quarters, median 4 /
mean 8.5 countries per quarter. Market-based Stage 2 features are 49-64%
missing within that population (vs 0% for macro fundamentals) — driven by
the same ZSPREAD-sparse EM countries (Chile, Nigeria, Sri Lanka, Zambia,
Peru, etc. — see "Stage 1 feature matrix" in CLAUDE.md) disproportionately
landing in the highest-risk tier. Answer to "is the feature set rich
enough": yes, a real model is buildable, but sample size — not feature
richness — is the binding constraint on result reliability.

**Model comparison (§4.3.3) result**: LASSO won both framings across 52
walk-forward folds (classification AUC 0.560 vs RF 0.546/XGB 0.550;
regression mean IC +0.076, t=0.83, one-sided p=0.205, vs RF -0.168/XGB
-0.261 — both *negative*). Not a default choice — the more flexible
tree-based models measurably overfit the small per-fold sample (median
~4-8 rows) and generalized worse than a linear, heavily-regularized model.
Per H2's own bar (IC>0.05 *and* p<0.05, thesis §1.5), **H2 is not
rejected** — economic significance (0.076) without statistical
significance (p=0.205). Reported as-is, not adjusted to force a positive
result.

**SHAP (§4.3.4) result, with caveat attached**: at LASSO's near-CV-optimal
alpha, only 3 of 14 features survive shrinkage — `cpi_inflation`,
`fiscal_bal_gdp`, `real_gdp_growth` — all macro fundamentals; every
market-based and global feature shrinks to exactly zero. Flagged
explicitly (in both CLAUDE.md and the script's own printed output) as
plausibly a data-richness artifact (market features are majority-missing
in this population) rather than proof markets carry no signal — this
distinction matters for how §6.2 can honestly characterize the result.

**Leakage discipline**: `stage2_utils.build_expanding_train_mask`
requires `target_period_end <= as_of_date` for training eligibility, one
quarter stricter than Stage 1's plain `rebal_date <= date`, because the
Stage 2 target is itself a forward `(t, t+1]` return. Added 3 checks to
`test_lag_rules.py` (10 total now, all passing): two structural checks
plus a truncation-invariance check that verifies predictions for **every**
date up to a mid-panel cutoff (not just the cutoff date itself) — the
exact gap the task flagged as having been a real bug caught and fixed in
Stage 1's equivalent test, deliberately not repeated here.

Commit: `fee1d1e` · issue #5 (Stage 2 signal) closed by this work —
references #2, #4 as predecessors

---

### 2026-08-11 — §4.2.4 lead/lag pilot run on the 5 Tier-1 countries: mixed result
**What**: With Tier 1 (Greece, Turkey, Sri Lanka, Portugal, Zambia)
reconciled, `src/stage1_clustering/ratings_leadlag_stub.py`'s
`compute_lead_lag()` was implemented for real -- a scoped **pilot**, not
the full §4.2.4 result, explicitly to answer one question before
prioritizing the remaining 39 countries' manual transcription: does H1's
mechanism (ML risk score deteriorates ahead of the agency downgrade) show
up at all in the highest-signal cases? Uses
`build_risk_labels.py`'s walk-forward output only (never
`algorithm_comparison.py`'s full-sample diagnostic fit -- see that
module's docstring for why that distinction matters here specifically:
testing a downgrade-anticipation hypothesis against a model that already
saw the downgrade and everything after it when fitting would be the
exact look-ahead bias H1 exists to rule out).

**Prerequisite added**: `build_risk_labels.py` previously only emitted
the categorical `risk_label`; H1's paired t-test needs a continuous
score. Added `risk_score` (0 = sitting on the low-risk centroid, 1 = on
the high-risk centroid; `d_low / (d_low + d_high)` in standardized
feature space from the same walk-forward K-Means fit) -- walk-forward-safe
by construction, same as `risk_label`. Only implemented for K-Means (the
chosen production algorithm); flagged in code as needing a real extension,
not a patch, if the chosen algorithm ever changes.
`data/processed/stage1_risk_labels.parquet` regenerated with the new
column; `test_lag_rules.py`'s truncation-invariance check still passes
(7/7).

**Test design**: paired, one-sided t-test (near window = up to 4 quarters
strictly before the downgrade date; baseline = the up to 4 quarters before
that), per thesis §1.5's H1 statement. 121 downgrade events across the 5
countries; 17 fall entirely before the panel starts (`no_preceding_data`
-- e.g. Greece 1990/1994/2004, Turkey 1994-2003, all correctly excluded,
not silently dropped) and 2 fall too close to the panel's 2005-2006 start
for a full baseline window (`insufficient_history` -- Portugal
2005-06-01, Sri Lanka 2007-08-01). 102 events actually tested.

**Result -- genuinely mixed, not a clean positive**:

| Country | n tested | mean Δ (risk_score) | Cohen's dz | p (one-sided) |
|---|---|---|---|---|
| Greece | 34 | +0.021 | 0.685 | **0.00017** |
| Portugal | 16 | +0.037 | 0.647 | **0.0103** |
| Sri Lanka | 19 | +0.021 | 0.394 | 0.0515 (borderline) |
| Turkey | 15 | -0.003 | -0.197 | 0.771 (null, wrong sign) |
| Zambia | 18 | -0.001 | -0.021 | 0.536 (null) |
| Pooled (all 5) | 102 | +0.016 | 0.397 | 5.8e-05 |

Greece and Portugal show a real, moderate-to-large effect (both the
2010-2012 sovereign debt crisis case studies the thesis names explicitly
-- the mechanism clearly shows up for compressed, front-loaded crisis
deterioration). Sri Lanka is directionally consistent but doesn't clear
p<0.05. Turkey and Zambia show essentially nothing -- Turkey's sign is
even reversed. Checked whether Zambia's null is an artifact of its
Moody's-GE-only coverage gap (see 2026-08-11 Zambia entry below): no --
excluding the 6 GE-only-sourced events, n=12, mean Δ=+0.002, p=0.386,
same null result. Also checked whether Turkey/Zambia's null is a ceiling
effect (already persistently high-risk, no room to move): no clear
evidence -- their full risk_score ranges (Turkey 0.28-0.67, Zambia
0.39-0.65) aren't meaningfully narrower or more saturated than Greece's
(0.39-0.67) or Portugal's (0.32-0.71). The more plausible read, not
confirmed further here: Greece/Portugal's downgrades followed a sharp,
compressed single-crisis deterioration that this feature set (debt/GDP,
fiscal balance, spread, etc.) captures well, while Turkey's (currency/
political-risk-driven) and Zambia's (chronic, serial, commodity-linked)
downgrade paths may be more gradual or driven by dynamics this feature
set represents less directly -- a genuinely open question, not resolved
by this pilot.

**Pooled result should not be read at face value**: pooling all 102
events (dominated by Greece's 34) treats them as independent, which they
aren't -- during acute crisis windows multiple agencies downgraded the
same country within weeks (visible directly in the event table: several
Zambia events from different agencies share near-identical Δ values
because they share almost the same near/baseline quarters). The pooled
p=5.8e-05 is real but optimistic; the per-country breakdown is the more
honest read.

**Bottom line for prioritization**: not a clean "yes, continue
transcription" nor a clean "no, don't bother" -- it's a real, 2-of-5
significant, 1-of-5 borderline, 2-of-5 null result. Worth continuing Tier
2, but **not** by transcribing it in its original listed order --
revised 2026-08-11 (see the transcription priority list above for the
full reasoning): Italy/Spain are Eurozone-crisis cases structurally like
Greece/Portugal and would likely just confirm the existing positive
result rather than test anything new. The pilot's actual open question is
whether the mechanism is Eurozone-crisis-specific or general, and that
needs two different comparison groups: South Africa/Brazil/Colombia
(non-Eurozone, fiscal-deterioration-driven -- do these behave like
Greece, or like Turkey?) and Egypt/Pakistan/Nigeria (currency/commodity-
driven -- do these fail like Turkey, or was Turkey's null idiosyncratic?).
Italy/Spain moved to the end of Tier 2 for this specific purpose (still
valuable for other reasons, just not the next-highest-information
transcription targets for H1's generalization question).

**Re-run the pilot incrementally, not only at the end of Tier 2**:
`src/stage1_clustering/ratings_leadlag_stub.py` should be re-run after
each pair of newly-transcribed Tier 2 countries lands (i.e. after South
Africa+Brazil, then +Colombia, then +Egypt+Pakistan, then +Nigeria --
roughly every 2 countries, not batched to all 8), so the fiscal-
deterioration-vs-currency/commodity split becomes visible incrementally
rather than as one late verdict. Concretely: after `ingest_ratings.py`
picks up each new country's manual file, rerun
`build_risk_labels.py` only if the underlying feature matrix or Stage 1
config changed (it currently doesn't depend on ratings, so this is
usually unnecessary) and always rerun `ratings_leadlag_stub.py` to
regenerate `stage1_leadlag_pilot_events.csv` and the per-country table.

**Explicitly not a §5.1 result**: 5 countries, chosen because they're the
highest-signal cases (Tier 1 = "explicit crisis case studies named in the
thesis outline itself" per the transcription priority list) -- citing
this pilot's numbers in the thesis proper without the full 44-country
run (or at least Tier 1+2) would be a selection-bias problem the real
result must not have. Outputs (`data/processed/stage1_leadlag_pilot_events.csv`)
kept for audit but treated as scratch, not a tracked deliverable.

Commit: (pending, this session)

---

### 2026-08-11 — Zambia reconciled: Tier 1 fully closed out, Moody's GE-only, a confirmed RATING_MAP alias, and the deepest GE blackout yet
**What**: Zambia -- last of the five Tier 1 countries -- run through
`reconcile_ratings_sources.py`. Closes Tier 1 (every default/
restructuring and crisis case study the thesis outline names explicitly
by name is now reconciled: Greece, Turkey, Sri Lanka, Portugal, Zambia).

**Moody's-coverage asymmetry, confirmed before running anything**: the
user flagged in advance that CE's Moody's page for Zambia was completely
empty (screenshot-confirmed, not a transcription gap). Checked GE first:
GE has 12 Moody's rows CE lacks entirely -- the opposite asymmetry from
the usual pattern, and the first time in this project GE has been the
*sole* source for an entire agency rather than the supplementary one.
Required no code change: the general union-of-months policy already
handles an agency with zero rows in one source correctly (every month
just becomes a single-source addition), confirmed by running it. Worth
noting as newly-verified behavior, not previously exercised by
Greece/Turkey/Sri Lanka/Portugal, all of which had at least partial
CE coverage for every agency.

**One blocking bug, held for user confirmation rather than guessed**: a
GE Moody's row had `rating="Ca-"`, unmappable, crashing the run. Unlike
`NR`/`NP` (systematic tokens worth a permanent drop-and-warn rule), this
looked like an isolated transcription artifact -- Moody's Ca/C tier
doesn't take +/- or numeric modifiers (those only apply Aaa through
Caa3), and a real, valid `Ca` entry appears later in the same GE
sequence (2022-11), with the malformed `Ca-` sitting in between a real
`Caa2` (2019-05) and that later `Ca` -- consistent with `Ca-` being a
mis-transcription of `Ca`, not a distinct grade. Ran a diagnostic pass
excluding just that one row (nothing written to disk) to deliver the
rest of the report while holding the actual fix for confirmation. User
confirmed against Moody's own scale documentation before any change was
made. Added `"Ca-": 20` to `RATING_MAP` in `ingest_ratings.py` (the
canonical location `reconcile_ratings_sources.py` imports from) as a
documented alias -- consistent with how the dict already aliases
multiple real notations (`"AAA"`/`"Aaa"`, etc.) to one ordinal value.
Deliberately narrow: only the numeric mapping is aliased; the raw string
`Ca-` is left exactly as transcribed in `Zambia.csv`, not silently
rewritten to `Ca`, since that's the scope the user actually asked for.

**Default-designation check, per the same scrutiny applied to Sri
Lanka**: CE captures a single SD (S&P, 2020-10-21) and a single RD
(Fitch, 2020-11-18) -- the same one-flag-per-agency pattern as Greece
and Sri Lanka. Moody's has no SD/RD-equivalent in either source,
consistent with Moody's real-world convention of expressing distress via
low letter grades rather than a distinct default flag.

**A genuinely new pattern beyond Sri Lanka's**: Fitch has a *second* RD
row -- this one from GE itself, dated 2024-12-01 with outlook `NR`,
followed by `CCC+` (2023-12, chronologically earlier in the printout but
worth reading as part of the same late recovery) and a `B-/Stable` exit
in 2025-11. Unlike Greece/Sri Lanka, where GE omitted the default
designation entirely, GE actually captured Zambia still sitting in RD
years after the initial 2020 default -- plausible and likely correct:
Zambia's sovereign debt restructuring didn't formally close until 2024
(after a multi-year G20 Common Framework process), and Fitch
conventionally keeps an issuer in Restricted Default status until a
distressed exchange fully completes, only reassigning a post-
restructuring rating afterward. Required no code change -- this GE row
flows through the ordinary union-of-months policy as a normal addition,
correctly retaining real information rather than needing any special
default-adjacent handling.

**GE blackout check, extended further than Sri Lanka's**: confirmed and,
for one agency, *more severe*. **S&P**: GE's last row is 2019-08-23
(`CCC+`); nothing again until 2025-11-21 -- over **6 years**, longer than
Sri Lanka's 3.5-year gap. **Fitch**: GE's gap runs 2020-09 -> 2023-12,
about **3 years** -- still substantial, but ending sooner than S&P's and
punctuated by that late RD snapshot. Read together with Sri Lanka and
Portugal, the emerging picture is that the GE blackout isn't a fixed
duration tied to "a default happened" -- it appears to track how long
each specific agency itself kept the issuer in distressed/default status
before reassigning a real rating, which varies by agency and by how long
the underlying restructuring actually took.

**Verified**: 45 reconciled rows in `Zambia.csv` (44 diagnostic + the
now-resolved `Ca-` row), zero conflicts (S&P and Fitch agreed on
everything with a CE counterpart; Moody's has no CE counterpart to
conflict with at all). Greece, Turkey, Sri Lanka, and Portugal re-run as
regression checks -- all four identical to before (172/1, 170/2, 118/0,
108/0), confirming the `Ca-` alias doesn't touch any already-settled
case. Combined 613 rows pass through `ingest_ratings.py` with only the
one known (Sri Lanka month-boundary) warning; `test_lag_rules.py` 7/7.

**Tier 1 complete.** Next up is Tier 2 (Italy, Spain, South Africa,
Brazil, Colombia, Egypt, Pakistan, Nigeria) -- see the transcription
priority list above.

Commit: (pending, this session) · Issue: #3

### 2026-08-11 — Portugal reconciled: Moody's short-term scale (NP), and a new standing policy for asymmetric watch qualifiers
**What**: Portugal run through `reconcile_ratings_sources.py` as-is
(fourth of five Tier 1 countries; Zambia is the last one left). Confirmed
no SD/RD/D anywhere in either source -- matching the expectation that
Portugal's 2011 crisis was a bailout, not a default, unlike Greece and
Sri Lanka. Also confirmed no GE multi-year blackout across 2011-2014 for
any agency (largest per-agency gap ~9-14 months, nowhere near Sri
Lanka's 3.5-year void) -- together with the Sri Lanka/Greece findings,
this narrows the earlier "GE systematically omits default-designation
periods" observation to something more precise: the blackout tracks
*default events specifically*, not sovereign crises in general. A
country can have a severe multi-year crisis (Portugal's bailout/
austerity years) with continuous GE coverage throughout, as long as it
never crosses into an actual default/restructuring.

**One new bug, structurally similar to Sri Lanka's `NR` but a different
root cause**: a CE row with `rating="NP"` (Moody's, 2013-07-26, no
outlook) crashed `RATING_MAP` lookup. `NP` ("Not Prime") is Moody's
**short-term** issuer-rating scale (Prime-1/2/3, Not Prime) -- an
entirely different scale from the long-term one `RATING_MAP` is built
on, not a missing/withdrawn rating like Sri Lanka's `NR`. CE's page
evidently interleaves short-term-scale actions into the same column as
long-term ones. Fixed with a new `_drop_short_term_scale()` step
(`SHORT_TERM_SCALE_TOKENS = {"NP","P-1","P-2","P-3","P1","P2","P3"}`),
documented as policy point 8, deliberately kept as a separate function
and warning message from `_drop_not_rated` even though the mechanical
handling is identical (drop, warn, don't forward-fill from or to it) --
worth being honest in the code about *why* a row is unmappable, not just
that it is. Verified the fix also corrected a real downstream
correctness issue, not just the crash: pre-fix, the CE row after `NP`
(2013-11-08, blank rating) would have forward-filled from the bogus
`NP` value; post-fix it correctly forward-fills to `Ba3`, the last real
long-term rating.

**New standing policy (point 9), requested by the user after reviewing
Portugal's 2 conflicts**: both were S&P, same rating on both sides, with
GE saying e.g. `Negative watch` and CE saying plain `Negative` -- an
*asymmetric* watch qualifier, not a disagreement about direction. The
user's read: GE tracks formal CreditWatch/under-review placements that
CE's site apparently doesn't surface at all, so this is an information
asymmetry to fold in automatically, not something to keep asking about
country after country. Implemented as a **standing rule**, not a
one-off resolution: `_outlook_eq` now also treats two outlooks as
agreeing when stripping any watch/review qualifier from both
(`_strip_watch_qualifier`) leaves the same non-empty base direction, and
`_prefer_outlook` (new helper, replaces the old inline "prefer CE's
outlook if populated" ternary in the merge step) keeps the
watch-qualified wording specifically, regardless of which source had it
-- the exact date still comes from CE per the pre-existing date-
preference rule. Deliberately scoped narrowly: `"Under Review"` alone
(no direction word) still does *not* count as matching a bare directional
outlook -- that remains governed by the pre-existing point-3 rule (both
sides mention watch/review), unchanged. Verified with synthetic
before-and-after checks on both Portugal cases plus every pre-existing
`_outlook_eq` regression case (both-watch, blank-side, genuine conflict,
watch-with-no-direction) -- all unchanged except the two new true
positives. Applying the rule folded both of Portugal's conflicts in
automatically (no manual resolutions.csv entry needed for either) --
`Portugal_conflicts.csv` went from 2 OPEN to 0 rows, and the reconciled
row count went from 106 to 108 as the previously-excluded conflict pairs
became normal merged rows.

**Verified**: 108 reconciled rows in `Portugal.csv`, zero conflicts.
Greece, Turkey, and Sri Lanka re-run as regression checks -- all three
identical to before (172/1, 170/2, 118/0), confirming policy 9 doesn't
change any already-settled case. Combined 568 rows pass through
`ingest_ratings.py` with only the one known (Sri Lanka month-boundary)
warning; `test_lag_rules.py` 7/7.

**Closes 4 of 5 Tier 1 countries.** Zambia remains -- the last Tier 1
default/restructuring case (2020), expected to exercise the
default-designation and possibly the GE-blackout findings again, this
time on a different agency mix and a different restructuring timeline
than Sri Lanka's.

Commit: (pending, this session) · Issue: #3

### 2026-08-11 — Pre-Portugal check-in surfaced a real bug: outlook-only rating cells ("(Negative)", no letter grade)
**What**: Before handing off Portugal, the user asked a direct
confirmation question -- does `reconcile_ratings_sources.py` already
handle CE's `LETTER_GRADE (Outlook)` pattern (e.g. `B2 (Stable)`) *and*
its `(Outlook)`-only variant (e.g. `(Negative)`, no letter grade), so
they could stop manually pre-splitting the rating column by hand for
every remaining country? Checked empirically rather than answering from
memory of the code, since exactly this kind of edge case had bitten
before (the NR/`(P)` bugs, both found by reading actual behavior, not by
assuming the docstring was still accurate). Confirmed:
- `B2 (Stable)` -- **worked correctly already** (point 2's
  `EMBEDDED_OUTLOOK_RE`, in place since Greece).
- `(Negative)` alone -- **broken**, and not just "unhandled." The regex
  still matches (an empty rating group before the parens), so
  `_clean_rating_outlook` returned rating `""` -- not `NA`. Since
  `pd.notna("")` is `True`, this empty string slipped straight past
  `_forward_fill_rating`'s blank-detection: it was treated as if it were
  a real rating, which both failed `RATING_MAP` lookup on its own *and*
  overwrote `last_rating` with `""` for that agency group, so the
  *next* row -- even a genuinely blank one that should have forward-filled
  correctly to the last real rating -- also came out `""`. Reproduced
  with a synthetic 3-row case (letter+outlook, outlook-only, then a
  truly blank row) before touching the code: pre-fix, the third row's
  rating was corrupted to `""` too and the whole run crashed at
  `_validate_ratings_mappable` with `unmapped rating value(s) ['']`.

**Fix**: in `_clean_rating_outlook`'s regex-extraction step, an empty
extracted rating is now converted to true `NA` rather than left as `""`,
so it flows into the *existing* forward-fill path (point 3's policy,
in place since Greece) instead of masquerading as data. Documented as
policy point 7 in the script's docstring, framed correctly as "the same
outlook-only case point 3 already handles for a blank cell, just spelled
differently by CE" -- not a new category of quirk, a gap in how an
existing one was implemented.

**Verified**: re-ran Greece, Turkey, and Sri Lanka as regression checks
-- identical row and conflict counts to before (172/1, 170/2, 118/0),
confirming none of the three real files actually hit this pattern (a run
would have crashed already if they had). Combined 460 rows still pass
cleanly through `ingest_ratings.py` with only the one expected
(month-boundary) warning; `test_lag_rules.py` 7/7.

**Answer given to the user**: yes, both patterns are now handled
generically in the pipeline -- safe to stop manually pre-splitting CE's
rating column from Portugal onward and paste the raw combined text
straight into the `rating` column, leaving `outlook` blank.

Commit: (pending, this session) · Issue: #3

### 2026-08-11 — Sri Lanka reconciled: three more edge cases (NR rating, (P) prefix, month-boundary blind spot), zero conflicts
**What**: Sri Lanka run through `reconcile_ratings_sources.py` as-is
(same two-sheet workbook format as Greece/Turkey). Zero genuine
cross-source conflicts -- a first, after Greece's 1 and Turkey's 2 -- but
three new structural findings, two of them real bugs (not false
positives like Turkey's duplicate-warning noise):

1. **GE used a not-rated/withdrawn token as the rating itself, not just
   the outlook.** A literal GE row: `S&P, rating="NR", outlook="NR",
   2019-04`. Crashed the run outright (`_validate_ratings_mappable`
   correctly refused to invent a numeric position for "not rated" on the
   ordinal scale) -- a loud failure, not a silent one, but still blocking.
   Fixed with `_drop_not_rated()`: rows are dropped only when the
   *rating* field itself is a not-rated token (`NOT_RATED_TOKENS`,
   currently just `NR`), with a warning naming the row. Deliberately
   scoped to the rating field only -- several of Sri Lanka's Fitch rows
   legitimately carry `outlook="NR"` (a real rating, just no outlook
   given) and are untouched by this filter, which only inspects `rating`.
2. **The `(P)`-provisional-prefix quirk the user flagged in advance**
   (CE's Moody's ratings sometimes read `(P)B1`, a leading qualifier
   meaning "provisional," not an outlook -- unlike point 2's *trailing*
   `(Outlook)` pattern) turned out not to appear in this file (manually
   pre-cleaned before transcription, as the user noted), so it wasn't
   exercised on real data. Implemented anyway per the user's explicit
   ask, since it's a documented recurring risk for future countries, not
   a hypothetical: `PROVISIONAL_PREFIX_RE` strips the prefix in
   `_clean_rating_outlook` and folds a `(provisional)` note into `source`
   rather than leaving `(P)B1` to fail `RATING_MAP` lookup. Verified
   against a synthetic `(P)B1` input (`_clean_rating_outlook` output:
   rating `B1`, source `... (provisional)`, `rating_numeric` 14) before
   touching real data.
3. **A genuine cross-month-boundary duplicate, structurally invisible to
   the reconciliation script itself.** CE has one Fitch row, `CCC`, dated
   2020-11-27 (exact day); GE has one Fitch row, `CCC`, dated 2020-12-01
   (month-precision) -- almost certainly the same real action, 4 days
   apart, straddling a month boundary. Because
   `reconcile_ratings_sources.py` buckets matching candidates by calendar
   month, these two rows were never even compared against each other --
   each landed in its own month's bucket as an "only one source has it"
   addition, so both survived into the merged output as two rows.
   `ingest_ratings.py`'s duplicate-action warning caught it downstream,
   exactly the case it exists for. Deliberately **not** fixed by widening
   the matching window across month boundaries -- that risks the opposite
   failure (silently conflating two genuinely distinct actions that
   happen to fall a few days apart on either side of a boundary), which
   is a worse outcome than one redundant `affirm` row surviving with a
   visible warning attached. Documented in the reconciliation script's
   docstring as a known, accepted limitation, not an open bug.

**Default-designation behavior, directly checked per the user's specific
ask**: Sri Lanka's 2022 default was a single SD (S&P, 2022-04-25) and a
single RD (Fitch, 2022-05-19) in CE, each preceded by an ordinary
graduated descent through lower ratings (S&P: CCC -> CC -> SD; Fitch: CC
-> C -> RD) -- i.e. CE represents the prolonged distress as a normal
sequence of downgrades terminating in one default flag per agency, not as
multiple SD/RD-type designations. This matches Greece's pattern (one
default flag per agency) even though the real-world restructuring
dragged on for over two years. GE showed the same systematic gap seen on
Greece, but *more severe*: GE has zero rows at all for S&P or Fitch
between Jan 2022 and Dec 2024 respectively (S&P: Jan 2022 -> Sep 2025
directly; Fitch: Jun 2021 -> Dec 2024 directly) -- a multi-year
blackout spanning the entire distressed/default/restructuring window for
both agencies, not just a missing single-date row at the SD/RD moment
itself. Required no code change (the existing default-designation
override and general union-of-months policy already handle this
correctly), but strengthens the case for treating GE as structurally
unreliable around any default/restructuring episode, worth keeping in
mind for Zambia (still pending, also a 2020 default).

**Also caught, an operational mistake of my own**: first invocation used
`"Sri Lanka"` (with a space) as the script's country argument, producing
`Sri Lanka.csv` -- which doesn't match `configs/universe.yaml`'s
`Sri_Lanka` (underscore) naming convention that `ingest_ratings.py`'s
coverage check keys off. Caught before anything downstream ran against
the wrong filename; re-ran with `Sri_Lanka`. Noted in the Open Items table
above as a reminder for future multi-word countries (Czech Republic,
South Africa, United Kingdom, United States).

**Verified**: 118 reconciled rows in `Sri_Lanka.csv`; combined with
Greece and Turkey, 460 rows run through `ingest_ratings.py` with exactly
the one expected duplicate-action warning (the month-boundary case above)
and no others; `test_lag_rules.py` passes 7/7. Greece and Turkey re-run
as regression checks -- both unaffected by all three new fixes (172/1
resolved and 170/2 resolved, unchanged).

**Running tally after 3 of 44 countries**: 7 reconciliation-logic edge
cases found across Greece/Turkey/Sri Lanka (2 false-positive-matching
bugs fixed on Greece, 1 exact-duplicate bug fixed on Turkey, 2 real bugs
fixed on Sri Lanka [NR rating, (P)-prefix handling], 1 accepted
structural limitation documented on Sri Lanka [month-boundary blind
spot], 1 of my own operational mistakes caught [country-argument
naming]). 3 genuine cross-source conflicts found total (Greece 1, Turkey
2), zero on Sri Lanka.

Commit: (pending, this session) · Issue: #3

### 2026-08-11 — Turkey reconciled: a fourth reconciliation edge case found and fixed, two conflicts resolved via primary-source research
**What**: Turkey transcribed against both GE and CE (same two-sheet
workbook format as Greece) and run through
`reconcile_ratings_sources.py` as-is, no changes expected going in. It
surfaced a genuinely new problem Greece hadn't: **GE's raw sheet had the
exact same row transcribed twice** -- `Fitch, BB-, Stable, 2020-02-01`,
byte-for-byte identical, appearing twice (there were actually two such
duplicate pairs in total, not just the one first spotted). This is a
copy-paste duplicate within a single source, not a cross-source
precision mismatch. Left alone, the extra copy survived cross-source
matching as a spurious "addition" once its twin had already been paired
against a CE row, and then tripped `ingest_ratings.py`'s duplicate-action
warning as a downstream symptom -- the warning was doing its job
correctly (flagging something that deserved a look), but the actual fix
belonged upstream. Added `_drop_exact_duplicates()` to
`reconcile_ratings_sources.py` -- drops byte-for-byte duplicate rows
(same agency/rating/outlook/date) within each source before any
cross-source matching, documented as the module docstring's 4th policy
point. Re-ran Greece as a regression check: unaffected (still 172 rows,
1 resolved conflict, zero duplicates found there) -- confirms the fix is
narrowly targeted, not something that happens to change results for
sources without this problem.

**Two genuine cross-source conflicts found, both resolved via primary-source
research** (not inferred or guessed, and not auto-resolved by the
script):
- **Moody's, Dec 2015**: GE said `Ba3/Negative`, CE said `Baa3/Negative`
  -- a 3-notch difference crossing the investment-grade line. Resolved to
  CE (Baa3) at **high confidence**: multiple sources (Reuters/Business
  Standard, Sept 2016) confirm Moody's downgraded Turkey *from Baa3* to
  Ba1 in September 2016, post-coup -- directly inconsistent with GE's
  claim that Turkey was already at Ba3 nine months earlier.
- **Moody's, Feb 2005**: GE said `Ba3/Positive`, CE said `B1/Positive`.
  Resolved to CE (B1) at **moderate-good confidence**: dated bracketing
  points confirm Moody's held Turkey at Ba3 in Nov 1999 and at B1 by Nov
  2008, consistent with a downgrade during/after the 2001 financial
  crisis persisting through the mid-2000s -- but no source was found
  dated specifically to Feb 2005, so this is trajectory inference, not a
  direct primary-source hit the way the Dec 2015 case and Greece's April
  2021 case were. The confidence distinction is recorded verbatim in
  `_reconciliation/Turkey_resolutions.csv`'s `note` field and carries
  through into the merged row's `source` field, so a future reader of
  `Turkey.csv` doesn't have to guess how solid each resolved conflict is.

**Verified**: 170 reconciled rows in `Turkey.csv` (168 before the two
conflicts were folded in); combined with Greece, 342 rows run cleanly
through `ingest_ratings.py` into `ratings_panel.csv` with zero warnings;
`test_lag_rules.py` passes 7/7.

**Running tally after 2 of 44 countries**: 4 reconciliation edge cases
found and fixed so far (Greece: over-strict outlook comparison,
over-broad duplicate-warning heuristic; Turkey: exact in-source
duplicates), plus one policy point that hasn't needed a fix yet
(default-designation override, exercised cleanly on Greece's SD/RD
events, not yet re-exercised on Turkey since Turkey's history in this
workbook didn't include any). Two genuine cross-source conflicts found on
Turkey, both resolved.

Commit: (pending, this session) · Issue: #3

### 2026-08-10 — Greece: first country reconciled (GE + CE), reconcile_ratings_sources.py built
**What**: Greece transcribed against both TheGlobalEconomy.com (GE) and
countryeconomy.com (CE), as two sheets of one workbook, and
cross-referenced -- the first time both sources were compared directly
for the same country rather than picking one. This surfaced three
structural disagreements a naive single-source pick would have gotten
wrong, all now encoded as an explicit, documented policy in the new
`src/data_acquisition/reconcile_ratings_sources.py`:

1. **CE captures default-designation events GE omits entirely.** For
   Greece: S&P's Feb 2012 and Dec 2012 SD, and Fitch's March 2012 RD, are
   in CE and absent from GE -- not sparse, absent. Policy: CE's
   default-designation rows (SD/RD/D) are always kept, never treated as a
   conflict candidate (GE has nothing to compare them against).
2. **CE sometimes embeds outlook text inside the rating field** (e.g.
   `BBB (Positive)`) and leaves the rating field blank on
   watch/under-review rows. Both cleaned before comparison: embedded
   outlook extracted (when the outlook column is itself blank), and blank
   ratings forward-filled from the most recent non-null rating for that
   agency within the same source.
3. **A real cross-source conflict**: April 2021, S&P -- GE says BB-
   /Stable, CE says BB/Positive. Confirmed via cross-check against the
   original screenshot: CE was correct. This is exactly the case the
   script's conflict-resolution mechanism is for -- it does not silently
   pick a side; it writes both to `<Country>_conflicts.csv` and only
   folds a resolution into the merged output once a matching row exists
   in `<Country>_resolutions.csv`, so the resolution and its rationale
   are on record, not just applied invisibly.

**Two bugs the real data caught, both fixed and re-verified before the
output was presented**:
- **Outlook comparison was too strict.** The first version of the
  reconciliation script's "do these rows agree" check used exact string
  equality on outlook, which produced 11 false-positive conflicts --
  every one of them had the *same rating* on both sides, differing only
  in outlook wording (CE simply left outlook blank in several cases; in
  others, GE said "Negative watch" where CE said "Under Review" -- the
  same review-status, described differently by each aggregator). Fixed
  by loosening `_outlook_eq`: a blank side agrees with anything, and any
  pair where both sides mention "watch"/"review" agrees regardless of
  exact wording -- documented in the function's docstring as a
  deliberate, non-obvious rule, not silent. This also fixed a real data
  loss: those 11 pairs (22 rows) had been excluded from the merged output
  entirely under the old logic, since unresolved conflicts don't make it
  into the merged file -- after the fix, they correctly collapse into 11
  merged rows (161 -> 172 total).
- **`ingest_ratings.py`'s existing duplicate-action warning fired on
  legitimate data, not just real duplicates.** Running the reconciled
  Greece.csv through `ingest_ratings.py` produced ~25 warnings, almost
  all Fitch, all from 2013-2014 -- CE turned out to re-affirm Greece's
  Fitch rating every 1-4 weeks with no change throughout that period
  (genuine dense surveillance reporting during the crisis, not a
  transcription artifact). The original warning logic (same rating within
  35 days = suspicious) couldn't tell that apart from an actual
  mixed-precision duplicate. Narrowed to only fire when exactly one side
  of the pair is an *unconfirmed* month-precision row (a GE row with no
  CE corroboration) -- the specific failure mode it was built for --
  which correctly silences the crisis-era CE cadence while still catching
  genuine GE/CE precision mismatches. Re-running after the fix: 0
  warnings on Greece's 172 rows.

**Reconciliation policy in one place** (also in the script's docstring):
union of both sources' months; a source-only month is used as-is; an
agreeing month collapses to one row preferring CE's exact date; a
disagreeing month is a conflict, never auto-resolved. Every merged row's
`source` field carries how it got there (e.g. "countryeconomy.com
(confirmed by theglobaleconomy.com (month-precision))",
"countryeconomy.com (default designation; theglobaleconomy.com omits
this event)", "countryeconomy.com (conflict resolved: ...)") -- fully
auditable without cross-referencing the conflicts file.

**Verified**: `data/raw/ratings/manual/Greece.csv` (172 rows) runs
cleanly through `ingest_ratings.py` into `data/processed/ratings_panel.csv`
with zero warnings; `test_lag_rules.py` passes 7/7, including the ratings
zero-lag check now validating real (not skipped) data for the first time.

**Reusability for the remaining 43 countries**: the same workflow applies
unchanged -- transcribe both sources into a two-sheet workbook, run
`reconcile_ratings_sources.py <Country> --xlsx <path>`, review
`_reconciliation/<Country>_conflicts.csv`, fill in
`_reconciliation/<Country>_resolutions.csv` for anything genuinely
disagreeing, re-run. `outlook`-wording variation and CE's blank-rating
watch rows should need no manual intervention going forward (both handled
generically, not Greece-specific); default-designation coverage and
dense-affirm periods should also just work the same way for other
default/restructuring-heavy Tier 1 countries (Zambia, Sri Lanka).

Commit: (pending, this session) · Issue: #3

### 2026-08-10 — Ratings manual source switched to TheGlobalEconomy.com; schema gains `outlook`
**What**: Before any country was actually transcribed against
countryeconomy.com (the source picked in the previous ratings-sourcing
session, see the entry below this one), inspecting its actual page
structure surfaced a disqualifying problem: each country page renders
**four independent chronological rating lists** (Long-term Foreign
Currency, Long-term Local Currency, Short-term Foreign Currency,
Short-term Local Currency) side by side in one HTML table, aligned by
row-index, not by shared date. On Greece's page, the row pairing
`2022-04-22 BB+ (Stable)` (Foreign Currency) with `2025-04-18 BBB` (Local
Currency) is actually two unrelated actions three years apart — reading
it row-aligned would silently corrupt the transcription. Only the
Long-term/Foreign-Currency column pair is relevant to our USD-denominated
universe, so using this source safely requires deliberately ignoring
three of its four columns — a real, easy-to-miss transcription-error
risk, not a hypothetical one. It also sometimes leaves the rating cell
blank on outlook-only-change rows, forcing error-prone inference from the
row above.

**Switched to TheGlobalEconomy.com as primary** instead: flat,
single-list, multi-agency tables (`agency | rating | outlook | date`),
every row's rating cell populated even when only outlook changed — a
near-exact structural match to the manual CSV schema, with none of
countryeconomy.com's column-misalignment risk. countryeconomy.com is
retained as a fallback only, for countries/periods TheGlobalEconomy.com
doesn't cover, with the column-alignment caveat kept firmly documented
(now in `ingest_ratings.py`'s module docstring and in CLAUDE.md) so it
isn't rediscovered from scratch on a future country.

**Two structural consequences of the switch, both handled in
`ingest_ratings.py`**:
- **Scope exclusion**: TheGlobalEconomy.com's tables include a 4th
  agency, Scope, alongside S&P/Moody's/Fitch. Out of scope for the
  thesis and for `RATING_MAP` — dropped during transcription, and
  `VALID_AGENCIES` rejects it defensively if one slips through (verified:
  a synthetic Scope row raised `ValueError` as expected).
- **Month-only date precision**: TheGlobalEconomy.com gives month/year
  only (e.g. `5/2026`), not exact day. Convention: 1st-of-month as
  `date`, `source` annotated `(month-precision)`. Confirmed this does
  *not* create an edge case in `test_lag_rules.py`'s zero-lag assertion —
  `available_date` is always derived as `date` verbatim inside
  `build_ratings_panel()`, so the check is tautologically satisfied
  regardless of the date's precision; it was only ever asserting
  `available_date == date`, never validating precision. The real risk
  is elsewhere: the *same* real-world action transcribed once from an
  exact-day source and once from a month-precision source would look like
  two distinct nearby rows rather than one. Added
  `_warn_possible_duplicate_actions()` — flags same
  country+agency+rating_numeric rows less than 35 days apart as a
  logged warning (not a hard failure) for manual review. Verified against
  a synthetic Greece file with a 13-day-apart same-rating pair (one row
  dated via the month-precision convention, one via an exact day) — the
  warning fired correctly, and the file was otherwise unaffected (both
  rows kept, correctly inferred as `affirm` of each other).

**Schema change: `outlook` is now an output column**, not just an input
used internally to help infer `action`. It had been silently dropped from
`ratings_panel.csv` in the first version of this script despite being
accepted in the raw-file format. Reasoning: outlook deterioration (e.g.
Stable → Negative with no letter-grade change) often precedes an actual
downgrade by months — a plausible leading-indicator signal beyond
letter-grade actions alone. Thesis §1.5/§4.2.4's formal H1 test is
defined against letter-grade downgrades specifically, so capturing
outlook isn't required for that test to run, but the marginal
transcription cost is ~zero (the value is already being read off the same
row), so it's captured now rather than retrofitted later. `action`
inference was extended to match: an unchanged rating with a changed
`outlook` now infers `outlook_change` instead of collapsing into
`affirm` — verified against the same synthetic Greece file (a
Negative→Stable outlook move with no rating change correctly produced
`outlook_change`, and a subsequent unchanged row correctly produced
`affirm`).

**Also added to this entry**: a country-transcription priority list (see
"Ratings transcription priority" section above) ranking the 44-country
universe by expected rating-change density in 2005–2025, so manual
transcription work can start with the countries most likely to actually
move H1's lead/lag test rather than proceeding alphabetically.

**Status**: still 0/44 countries collected — this was schema/pipeline
hardening ahead of transcription starting, not transcription itself. All
changes verified with synthetic test files only (created, exercised, then
deleted — `data/processed/ratings_panel.csv` is back to 0 rows).

Commit: (pending, this session) · Issue: #3

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
