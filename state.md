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
| Manually collect per-country rating-action history into `data/raw/ratings/manual/<Country>.csv` | §4.2.3, §4.2.4, RQ1/H1 | User (transcribe both TheGlobalEconomy.com and countryeconomy.com per country as a two-sheet workbook, then run `reconcile_ratings_sources.py` — see the 2026-08-10/2026-08-11 reconciliation entries below; agency IR pages for gaps neither source covers). See the transcription priority list below for sequencing. **Reminder for multi-word countries**: pass the underscore form (`Sri_Lanka`, not `Sri Lanka`) as the script's `country` argument — it's used verbatim as the output filename and must match `configs/universe.yaml`'s `name.replace(" ", "_")` for `ingest_ratings.py`'s coverage check to recognize it (caught once on Sri Lanka, fixed before anything downstream ran on the wrong filename). | **In progress — 3/44 (Greece, Turkey, Sri Lanka) done**, all reconciled via `reconcile_ratings_sources.py` (172 + 170 + 118 = 460 rows, 3 conflicts total found and resolved, all on Greece/Turkey). 41 to go, continuing with the rest of Tier 1. |
| §4.2.4 lead/lag analysis (`ratings_leadlag_stub.py`) | §4.2.4, RQ1/H1 | Blocked on the ratings item above; also needs `build_risk_labels.py` extended to emit a continuous risk score, not just the categorical tier (see CLAUDE.md "Stage 1 clustering") | Interface stubbed, not implemented |
| Residual global-regime sensitivity in Stage 1 clustering (`core-eligible` = 0 for several consecutive quarters, 2009-2017) | §5.5 candidate robustness check; not blocking Stage 3/4 | Open — see CLAUDE.md "Stage 1 clustering" for the full diagnosis (us_10y/curve_slope are global-only features, thesis §3.3 keeps them in Stage 1 regardless) | Documented, not fixed further without a methodology-level call to override the thesis's own feature-group spec |
| Execution-verify `bond_data_pull_reconstructed.py` (does it actually run/chunk/return data as designed) | Appendix A reproducibility only — not blocking, since existing bond data already feeds Stage 1 | User (requires a session on the university-library Windows PC with Refinitiv Workspace) | Not started |
| CDS data (`data/raw/cds/`) never successfully pulled | Nothing currently — Stage 1 extended tier gates on duration/convexity, not CDS (see CLAUDE.md) | Would also require the library-PC session if pursued | Open, not currently prioritized |
| `docs/thesis_outline_sovereign.md` §1.4 still says "2005–2023"; actual pipeline uses 2005–2025 | Consistency of the written thesis, not the code | User (thesis text edit) | Open, tracked separately from code |
| Stage 2/3/4 (`src/stage2_signal/`, `stage3_portfolio/`, `stage4_evaluation/`) not started | Everything downstream of Stage 1 | — | Not started — Stage 1 (feature matrix + clustering + walk-forward labels) is now fully built; this is the next major phase |

---

## Ratings transcription priority (for issue #3)

Suggested sequencing for manually transcribing `data/raw/ratings/manual/<Country>.csv`
files, ranked by how much a country is likely to contribute to H1's
lead/lag test — countries with real rating changes during 2005–2025
matter; countries that sat at one rating the whole window contribute
little. Based on general knowledge of major sovereign rating events, not
yet verified against the actual transcribed data.

- **Tier 1 (do first — explicit crisis case studies named in the thesis
  outline itself)**: ~~Greece~~ (done, 2026-08-10), ~~Turkey~~ (done,
  2026-08-11), ~~Sri Lanka~~ (done, 2026-08-11), Portugal, Zambia.
- **Tier 2 (high value — sharp multi-notch moves)**: Italy, Spain, South
  Africa, Brazil, Colombia, Egypt, Pakistan, Nigeria.
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

## Chronological log

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
