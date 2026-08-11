"""Reconcile TheGlobalEconomy (GE) and countryeconomy.com (CE) rating
transcriptions for one country into data/raw/ratings/manual/<Country>.csv
(issue #3).

Why this exists: cross-referencing both sources for the same country
(first done for Greece, 2026-08-10) surfaced structural disagreements
between them that a naive "pick a primary source" merge would get wrong:

1. **CE captures default-designation events that GE systematically omits.**
   For Greece, S&P's Feb 2012 and Dec 2012 SD, and Fitch's March 2012 RD,
   are present in CE and entirely absent from GE -- not sparse, absent.
   Policy: any CE row whose rating is a default designation (SD/RD/D) is
   always kept, regardless of general source priority elsewhere, and is
   never treated as a conflict candidate against GE (GE has nothing to
   compare it to in the first place).
2. **CE sometimes embeds outlook text inside the rating field** (e.g.
   `BBB (Positive)`), duplicating the separate outlook column. Stripped
   before any comparison logic runs, via `_clean_rating_outlook`, along
   with whitespace-trimming every rating/outlook string from both
   sources.
3. **CE has extra watch/under-review rows with a blank rating field**
   (e.g. a "Negative watch" or "Under Review" outlook entry with no
   letter grade given) -- these represent a real state at that date and
   are forward-filled from the most recent non-null rating for that
   agency within the same source, not dropped or left null. Applied
   independently per source (GE and CE are never cross-filled from each
   other).
4. **A single source can contain an exact-duplicate row.** Found on
   Turkey: GE's raw sheet had the byte-for-byte identical row (Fitch,
   BB-, Stable, 2020-02-01) transcribed twice -- a copy-paste duplicate
   in the source workbook, not a second real action. Left alone, the
   extra copy survives cross-source matching as a spurious "addition"
   once its twin has already been paired against the other source, and
   then gets flagged by ingest_ratings.py's duplicate-action warning --
   a symptom, not the actual bug. `_drop_exact_duplicates` removes
   byte-for-byte duplicates (same agency/rating/outlook/date) within
   each source before any cross-source matching runs, so it only ever
   removes true transcription duplicates, never two genuinely close but
   distinct actions (which always differ in at least date).
5. **GE can use a "not rated"/withdrawn token as the *rating itself*, not
   just as an outlook.** Found on Sri Lanka: a literal GE row with
   `rating="NR"` (S&P, 2019-04) -- distinct from the many GE rows that
   legitimately carry `outlook="NR"` (rating still a real letter grade,
   just no outlook given, e.g. several of Sri Lanka's Fitch rows). "Not
   rated" isn't a point on the ordinal `RATING_MAP` scale -- it means the
   agency withdrew coverage, not that the country is worse than D -- so
   `_drop_not_rated` removes rows where the *rating* field (never
   outlook) matches a token in `NOT_RATED_TOKENS` (currently just `NR`),
   with a loud warning, before anything tries to map it to a number and
   crashes.
6. **CE prefixes some Moody's ratings with `(P)`** (e.g. `(P)B1`) to mark
   a provisional rating -- a rating qualifier, not an outlook, and a
   *leading* prefix, unlike point 2's trailing `(Outlook)` pattern.
   `PROVISIONAL_PREFIX_RE` strips it in `_clean_rating_outlook` and
   folds a `(provisional)` note into the row's `source` field instead of
   leaving it stuck to the rating string where it would fail
   `RATING_MAP` lookup. Not yet exercised by a merged row (Sri Lanka's
   transcription had already been manually pre-cleaned of this pattern
   before reconciliation), but verified against a synthetic input.
7. **A rating cell that's *only* a parenthetical outlook, with no letter
   grade** (e.g. `(Negative)`, as opposed to point 2's `BBB (Positive)`)
   is a legitimate CE pattern -- the same "outlook-only" case point 3
   handles when the cell is fully blank, just spelled differently. Point
   2's regex still matches it (an empty rating group before the parens),
   but the empty-string result is a real bug, not a no-op: `pd.notna("")`
   is `True`, so an unconverted `""` slips past point 3's blank-detection
   in `_forward_fill_rating` -- it gets treated as if it were a real
   rating, which both fails `RATING_MAP` lookup itself *and* corrupts
   `last_rating` for every subsequent row in that agency's group, turning
   what should have forward-filled correctly into more `""` values. Fixed
   in `_clean_rating_outlook`: an empty extracted rating is converted to
   true `NA`, so it flows into point 3's existing forward-fill path
   instead of silently masquerading as data. Caught before landing on
   real data -- verified against a synthetic 3-row case (letter+outlook,
   outlook-only, then a genuinely blank row) showing the cascading
   corruption pre-fix and the correct forward-fill chain post-fix.
8. **CE can interleave Moody's short-term-scale ratings into the same
   column as long-term ones.** Found on Portugal: a literal Moody's row
   with `rating="NP"` ("Not Prime") sitting between two ordinary
   long-term `Ba3` entries, no outlook. `NP`/`P-1`/`P-2`/`P-3` are
   Moody's short-term issuer-rating scale -- a different scale entirely
   from the long-term scale `RATING_MAP` is built on, not a
   missing/withdrawn rating like point 5's `NR`. `_drop_short_term_scale`
   removes rows on `SHORT_TERM_SCALE_TOKENS` before anything tries to
   map them, with a warning distinguishing this from the `NR` case even
   though the handling (drop, don't forward-fill from or to it) is
   identical.
9. **A watch/under-review qualifier present on only one side is an
   information asymmetry, not a disagreement.** Found on Portugal, S&P
   2011-12 and 2013-09: GE said `BBB-/Negative watch` and `BB/Negative
   watch`, CE said the plain `BBB-/Negative` and `BB/Negative` for the
   same rating and month -- GE evidently tracks formal CreditWatch/
   under-review placements that CE's site doesn't surface at all, not two
   aggregators disagreeing about direction. Policy: when the ratings
   agree and stripping any watch/review qualifier from both outlooks
   (`_strip_watch_qualifier`) leaves the same non-empty base direction,
   `_outlook_eq` treats them as agreeing -- and when merging, the
   *watch-qualified* wording wins regardless of which source it came
   from (`_prefer_outlook`), keeping the exact-day date from whichever
   source has it per the general date-preference rule above. `"Under
   Review"` alone (no direction word to compare) still does *not* count
   as agreeing with a bare directional outlook this way -- point 3's
   both-sides-mention-watch/review rule is what covers that case, and
   this point deliberately doesn't widen it further.

Given all that, the merge policy for non-conflicting (agency, month)
buckets is: union of both sources' months; where only one source has a
row, use it; where both have a row and agree (same rating_numeric, same
outlook after cleanup) keep one merged row, preferring CE's exact-day
date over GE's 1st-of-month convention. Where both cover the same month
with genuinely different values -- not just a precision/formatting
difference -- this script does **not** silently pick one. It writes both
sides to `<Country>_conflicts.csv` for manual review (the April 2021 S&P
case for Greece -- GE: BB-/Stable vs CE: BB/Positive -- is exactly this;
CE was confirmed correct via cross-check against the original
screenshot). A conflict is only folded into the merged output once a
matching row appears in `<Country>_resolutions.csv` (see
_reconciliation/ below) recording which source was chosen and why --
every merged row's `source` field carries that provenance, so nothing in
the output CSV is resolved invisibly.

Every row's `source` field documents *how* it got there:
  - GE-only / CE-only:          the original source string, as transcribed
  - agreeing pair:               "<CE source> (confirmed by <GE source>)"
  - CE default designation:      "<CE source> (default designation; theglobaleconomy.com omits this event)"
  - resolved conflict:           "<chosen source> (conflict resolved: <note>)"

Inputs/outputs (per country):
  Input:  one .xlsx with two sheets (GE and CE transcriptions), each in
          the same 8-column layout as data/raw/ratings/manual/<Country>.csv
          plus a redundant `country`/`rating_numeric`/`action` column
          (only date, agency, rating, outlook, source are actually used
          here -- rating_numeric/action are computed downstream by
          ingest_ratings.py, not by this script).
  Output: data/raw/ratings/manual/<Country>.csv -- the reconciled file,
          in the same 6-column schema as _TEMPLATE.csv
          (date,agency,rating,outlook,action,source), ready for
          ingest_ratings.py to pick up.
          data/raw/ratings/manual/_reconciliation/<Country>_conflicts.csv
          -- every conflict found, resolved or not, for review/audit.
  Optional input, same _reconciliation/ dir:
          <Country>_resolutions.csv -- one row per conflict you've
          adjudicated (agency, ge_date, ce_date, chosen_source, note).
          Auto-loaded if present at that conventional path; re-running
          the script after adding a row there folds that conflict into
          the merged output on the next pass.

Run: python3 src/data_acquisition/reconcile_ratings_sources.py <Country> --xlsx <path>
"""

import argparse
import logging
import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
MANUAL_DIR = REPO_ROOT / "data" / "raw" / "ratings" / "manual"
RECONCILIATION_DIR = MANUAL_DIR / "_reconciliation"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest_ratings import RATING_MAP, VALID_AGENCIES  # noqa: E402

DEFAULT_GE_SHEET = "the global economy"
DEFAULT_CE_SHEET = "country economy"

# Default-designation notches -- CE captures these, GE systematically
# doesn't (see module docstring, point 1).
DEFAULT_DESIGNATIONS = {"SD", "RD", "D"}

# "Not rated"/withdrawn tokens seen in the rating field itself (found on
# Sri Lanka: GE has a literal S&P row with rating="NR", not just as an
# outlook value). Not a point on the ordinal scale, so unmappable --
# extend this set if another token (e.g. "WD") shows up on a future
# country (see module docstring, point 5).
NOT_RATED_TOKENS = {"NR"}

# Moody's short-term rating scale (Prime-1/2/3, Not Prime) -- a different
# scale from the long-term issuer ratings RATING_MAP is built on, not a
# missing/withdrawn rating. Found on Portugal: CE has a literal
# Moody's row with rating="NP" (2013-07-26, no outlook, sitting between
# two ordinary long-term Ba3 entries) -- CE's page evidently interleaves
# short-term-scale actions into the same column as long-term ones. See
# module docstring, point 8.
SHORT_TERM_SCALE_TOKENS = {"NP", "P-1", "P-2", "P-3", "P1", "P2", "P3"}

EMBEDDED_OUTLOOK_RE = re.compile(r"^(?P<rating>.*?)\s*\((?P<outlook>[^)]+)\)\s*$")
# CE's Moody's provisional-rating prefix, e.g. "(P)B1" -- (P) means
# "provisional", not an outlook, and it's a *leading* prefix, unlike
# EMBEDDED_OUTLOOK_RE's trailing "(Outlook)" pattern (see module
# docstring, point 6).
PROVISIONAL_PREFIX_RE = re.compile(r"^\(P\)\s*(?P<rating>.+)$", re.IGNORECASE)


def _rating_numeric(rating) -> int | None:
    if pd.isna(rating) or not str(rating).strip():
        return None
    return RATING_MAP.get(str(rating).strip())


_WATCH_TOKENS = ("watch", "review")
_WATCH_TOKEN_RE = re.compile(r"\b(under\s+review|watch|review)\b", re.IGNORECASE)


def _strip_watch_qualifier(s: str) -> str:
    """Remove a watch/under-review qualifier from an outlook string,
    leaving just the base direction (e.g. "Negative watch" -> "Negative").
    Returns "" if the string is entirely a watch descriptor with no
    direction word of its own (e.g. "Under Review")."""
    return re.sub(r"\s+", " ", _WATCH_TOKEN_RE.sub("", s)).strip()


def _outlook_eq(a, b) -> bool:
    """Outlook "agreement" is deliberately looser than exact string
    equality -- on real data (Greece), an exact-match rule flagged 11
    false-positive conflicts where the rating fully agreed and only the
    outlook *wording* differed: one source simply left outlook blank
    while the other recorded one (e.g. CE blank vs GE "Stable" -- not a
    contradiction, just a field CE didn't capture for that dated entry),
    or the two aggregators described the same active-review state
    differently ("Negative watch" vs "Under Review"). Both patterns are
    the "just a precision/formatting difference" case the module
    docstring's merge policy says should NOT be flagged -- so: blank on
    either side agrees with anything, and any pair where both sides
    mention "watch"/"review" agrees regardless of exact wording.

    A third case, found on Portugal (see module docstring, point 9): one
    side has a watch/review qualifier and the other has only the plain
    base direction -- e.g. GE "Negative watch" vs CE "Negative". This
    isn't a disagreement, it's an information asymmetry (GE tracks formal
    CreditWatch/under-review placements that CE's site apparently
    doesn't), so it agrees too whenever stripping the qualifier from both
    sides leaves the same non-empty base direction. "Under Review" alone
    (no direction word) does NOT count as agreeing with a plain
    directional outlook this way -- there's no direction to compare, so
    that stays governed by the both-sides-mention-watch/review rule above.

    Anything else (e.g. "Stable" vs "Positive", both non-blank, neither a
    watch/review state, no shared base direction) is a genuine
    disagreement."""
    a = "" if pd.isna(a) else str(a).strip().lower()
    b = "" if pd.isna(b) else str(b).strip().lower()
    if a == "" or b == "":
        return True
    if a == b:
        return True
    if any(tok in a for tok in _WATCH_TOKENS) and any(tok in b for tok in _WATCH_TOKENS):
        return True
    a_base, b_base = _strip_watch_qualifier(a), _strip_watch_qualifier(b)
    if a_base and b_base and a_base == b_base:
        return True
    return False


def _prefer_outlook(primary, secondary):
    """Pick which outlook wording survives into a merged row. Prefers
    `primary` (the row whose date is used -- see the merge policy below)
    when populated, EXCEPT when the two are the same base direction (per
    _outlook_eq's watch-qualifier equivalence) and only `secondary`
    carries the watch/review qualifier -- then the more specific wording
    wins regardless of which source it came from (module docstring,
    point 9): an asymmetric watch designation is real information, not
    noise to discard just because it happened to be on the
    lower-priority side."""
    def _has_watch(v):
        return pd.notna(v) and any(tok in str(v).lower() for tok in _WATCH_TOKENS)

    if _has_watch(secondary) and not _has_watch(primary):
        return secondary
    return primary if pd.notna(primary) else secondary


def _load_sheet(xlsx_path: Path, sheet_name: str, source_label: str) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
    required = {"agency", "rating", "outlook", "date", "source"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{xlsx_path} [{sheet_name}]: missing required column(s) {missing}")
    df = df[["agency", "rating", "outlook", "date", "source"]].copy()
    df["date"] = pd.to_datetime(df["date"])

    df["agency"] = df["agency"].astype(str).str.strip()
    unknown_agencies = set(df["agency"]) - VALID_AGENCIES
    if unknown_agencies:
        logging.warning(
            f"{source_label}: dropping unknown/out-of-scope agency row(s) {unknown_agencies} "
            f"(e.g. Scope) -- not in {VALID_AGENCIES}"
        )
        df = df[df["agency"].isin(VALID_AGENCIES)]
    return df.reset_index(drop=True)


def _drop_not_rated(df: pd.DataFrame, source_label: str) -> pd.DataFrame:
    """Drop rows whose *rating* field (not outlook) is a not-rated/
    withdrawn token (see NOT_RATED_TOKENS). Found on Sri Lanka: GE had a
    literal S&P row with rating="NR" -- "not rated" isn't a point on the
    ordinal RATING_MAP scale (it means the agency withdrew coverage, not
    that the country is worse than D), so it can't be given a
    rating_numeric without inventing a meaningless value. Dropped with a
    loud warning rather than crashing the whole reconciliation run on an
    unmappable rating. Does NOT touch "NR" appearing as an *outlook*
    value (e.g. GE's Fitch rows carry outlook="NR" meaning "no outlook
    given" -- a legitimate, if uninformative, outlook string, left as-is)."""
    is_nr = df["rating"].apply(lambda r: pd.notna(r) and str(r).strip().upper() in NOT_RATED_TOKENS)
    n = int(is_nr.sum())
    if n:
        first = df[is_nr].iloc[0]
        logging.warning(
            f"{source_label}: dropped {n} row(s) with a not-rated/withdrawn rating token "
            f"(e.g. {first['agency']} on {first['date'].date()}) -- not a point on the "
            f"ordinal scale, so not representable as rating_numeric"
        )
    return df[~is_nr].reset_index(drop=True)


def _drop_short_term_scale(df: pd.DataFrame, source_label: str) -> pd.DataFrame:
    """Drop rows whose rating is on Moody's short-term scale (see
    SHORT_TERM_SCALE_TOKENS). Found on Portugal: CE has a literal
    Moody's row with rating="NP" sitting between two ordinary long-term
    entries -- a different scale from RATING_MAP's long-term issuer
    ratings, not a missing or withdrawn one, so it's just as unmappable
    as NR but for a different reason (worth distinguishing in the
    warning message, even though the handling -- drop, warn, don't
    forward-fill from or to it -- is identical)."""
    is_st = df["rating"].apply(lambda r: pd.notna(r) and str(r).strip().upper() in SHORT_TERM_SCALE_TOKENS)
    n = int(is_st.sum())
    if n:
        first = df[is_st].iloc[0]
        logging.warning(
            f"{source_label}: dropped {n} row(s) with a Moody's short-term-scale rating "
            f"(e.g. {first['agency']} on {first['date'].date()}) -- different scale from "
            f"RATING_MAP's long-term issuer ratings, so not representable as rating_numeric"
        )
    return df[~is_st].reset_index(drop=True)


def _clean_rating_outlook(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace on rating/outlook; strip a leading "(P)" (Moody's
    provisional-rating prefix, e.g. "(P)B1") into a "(provisional)" note
    on `source` rather than leaving it stuck to the rating string; and
    strip a trailing outlook embedded in the rating field (e.g.
    "BBB (Positive)") out into the outlook column when outlook itself is
    otherwise blank."""
    df = df.copy()

    def _strip(v):
        return str(v).strip() if pd.notna(v) and str(v).strip() else pd.NA

    df["rating"] = df["rating"].apply(_strip)
    df["outlook"] = df["outlook"].apply(_strip)

    def _extract(row):
        rating = row["rating"]
        source = row["source"]
        if pd.isna(rating):
            return rating, row["outlook"], source

        rating = str(rating)
        m_prov = PROVISIONAL_PREFIX_RE.match(rating)
        if m_prov:
            rating = m_prov.group("rating").strip()
            source = f"{source} (provisional)" if pd.notna(source) else "(provisional)"

        m = EMBEDDED_OUTLOOK_RE.match(rating)
        if not m:
            return rating, row["outlook"], source
        extracted_rating = m.group("rating").strip()
        extracted_outlook = m.group("outlook").strip()
        outlook = row["outlook"] if pd.notna(row["outlook"]) else extracted_outlook
        # A cell that's *only* a parenthetical outlook (e.g. "(Negative)",
        # no letter grade before it) matches with an empty rating group --
        # must become true NaN, not "". pd.notna("") is True, so an empty
        # string would silently skip _forward_fill_rating's blank-detection
        # (treating "" as a real rating and even overwriting last_rating
        # with it, corrupting the fill for every row after it) and then
        # crash _validate_ratings_mappable on an unmappable "" instead of
        # forward-filling correctly.
        if not extracted_rating:
            extracted_rating = pd.NA
        return extracted_rating, outlook, source

    df[["rating", "outlook", "source"]] = df.apply(lambda r: pd.Series(_extract(r)), axis=1)
    return df


def _forward_fill_rating(df: pd.DataFrame, source_label: str) -> pd.DataFrame:
    """Forward-fill blank rating cells (watch/under-review rows) from the
    most recent non-null rating for the same agency, chronologically,
    within this source only. Rows that can't be filled (blank with no
    prior value) are dropped with a loud warning, since an unfillable
    rating can't be represented in the downstream schema."""
    kept = []
    for agency, group in df.groupby("agency", sort=False):
        group = group.sort_values("date")
        last_rating = None
        for _, row in group.iterrows():
            row = row.copy()
            r = row["rating"]
            if pd.notna(r):
                last_rating = str(r).strip()
                kept.append(row)
            elif last_rating is not None:
                row["rating"] = last_rating
                logging.info(
                    f"{source_label}: forward-filled blank rating for {agency} on "
                    f"{row['date'].date()} -> {last_rating} (outlook: {row['outlook']})"
                )
                kept.append(row)
            else:
                logging.warning(
                    f"{source_label}: dropping {agency} row on {row['date'].date()} -- "
                    f"blank rating with no prior value to forward-fill from"
                )
    return pd.DataFrame(kept).reset_index(drop=True) if kept else df.iloc[0:0]


def _drop_exact_duplicates(df: pd.DataFrame, source_label: str) -> pd.DataFrame:
    """Drop byte-for-byte duplicate rows (same agency/rating/outlook/date)
    within a single source. Found on Turkey: TheGlobalEconomy's raw sheet
    had the identical row (Fitch, BB-, Stable, 2020-02-01) transcribed
    twice -- a copy-paste duplicate in the source workbook, not a second
    real action and not a cross-source precision mismatch (the thing
    ingest_ratings.py's duplicate-action warning targets). Left
    undeduplicated, the extra copy survives matching as a spurious
    unmatched "addition" once its twin has already been paired against
    the other source. Applied per-source, before any cross-source
    matching, so it only ever removes true transcription duplicates, not
    two genuinely close-but-distinct actions (which always differ in at
    least date)."""
    before = len(df)
    df = df.drop_duplicates(subset=["agency", "rating", "outlook", "date"]).reset_index(drop=True)
    n_dropped = before - len(df)
    if n_dropped:
        logging.warning(
            f"{source_label}: dropped {n_dropped} exact-duplicate row(s) "
            f"(identical agency/rating/outlook/date) -- likely a copy-paste "
            f"duplicate in the source sheet, not a genuine second action"
        )
    return df


def _validate_ratings_mappable(df: pd.DataFrame, label: str) -> None:
    unmapped = df.loc[df["rating"].apply(lambda r: _rating_numeric(r) is None), "rating"]
    if not unmapped.empty:
        raise ValueError(
            f"{label}: unmapped rating value(s) {sorted(unmapped.dropna().unique())} "
            f"-- add to RATING_MAP (ingest_ratings.py) if legitimate"
        )


def _load_resolutions(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["agency", "ge_date", "ce_date", "chosen_source", "note"])
    df = pd.read_csv(path)
    required = {"agency", "ge_date", "ce_date", "chosen_source", "note"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing required column(s) {missing}")
    for col in ("ge_date", "ce_date"):
        df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d")
    df["chosen_source"] = df["chosen_source"].str.strip().str.upper()
    return df


def reconcile(ge_df: pd.DataFrame, ce_df: pd.DataFrame, resolutions_df: pd.DataFrame):
    ge_df = _drop_not_rated(ge_df, "GE")
    ce_df = _drop_not_rated(ce_df, "CE")

    ge_df = _drop_short_term_scale(ge_df, "GE")
    ce_df = _drop_short_term_scale(ce_df, "CE")

    ge_df = _clean_rating_outlook(ge_df)
    ce_df = _clean_rating_outlook(ce_df)

    ge_df = _drop_exact_duplicates(ge_df, "GE")
    ce_df = _drop_exact_duplicates(ce_df, "CE")

    # Point 1: CE default-designation rows are always kept, never paired
    # against GE (which has nothing to compare them to).
    is_default = ce_df["rating"].apply(
        lambda r: pd.notna(r) and str(r).strip().upper() in DEFAULT_DESIGNATIONS
    )
    default_rows = ce_df[is_default].copy()
    ce_df = ce_df[~is_default].copy()

    ge_df = _forward_fill_rating(ge_df, "GE")
    ce_df = _forward_fill_rating(ce_df, "CE")

    _validate_ratings_mappable(ge_df, "GE")
    _validate_ratings_mappable(ce_df, "CE")
    _validate_ratings_mappable(default_rows, "CE (default designation)")

    ge_df["_month"] = ge_df["date"].dt.to_period("M")
    ce_df["_month"] = ce_df["date"].dt.to_period("M")

    merged_rows = []
    conflict_rows = []

    for row in default_rows.itertuples():
        merged_rows.append(
            {
                "date": row.date,
                "agency": row.agency,
                "rating": row.rating,
                "outlook": row.outlook if pd.notna(row.outlook) else "",
                "action": "",
                "source": f"{row.source} (default designation; theglobaleconomy.com omits this event)",
            }
        )

    all_agencies = sorted(set(ge_df["agency"]) | set(ce_df["agency"]) | set(default_rows["agency"]))
    for agency in all_agencies:
        months = sorted(
            set(ge_df.loc[ge_df["agency"] == agency, "_month"])
            | set(ce_df.loc[ce_df["agency"] == agency, "_month"])
        )
        for month in months:
            ge_bucket = ge_df[(ge_df["agency"] == agency) & (ge_df["_month"] == month)].sort_values("date").to_dict("records")
            ce_bucket = ce_df[(ce_df["agency"] == agency) & (ce_df["_month"] == month)].sort_values("date").to_dict("records")

            matched_ce_idx = set()
            leftover_ge = []
            for g in ge_bucket:
                match_idx = None
                for i, c in enumerate(ce_bucket):
                    if i in matched_ce_idx:
                        continue
                    if _rating_numeric(g["rating"]) == _rating_numeric(c["rating"]) and _outlook_eq(g["outlook"], c["outlook"]):
                        match_idx = i
                        break
                if match_idx is not None:
                    matched_ce_idx.add(match_idx)
                    c = ce_bucket[match_idx]
                    # _outlook_eq treats a blank side, or a watch-qualifier-only
                    # difference, as agreeing -- "matched" doesn't mean both sides
                    # said the exact same thing. _prefer_outlook picks CE's wording
                    # when populated (so a genuinely blank CE side doesn't silently
                    # drop GE's real value), except when only the *other* side
                    # carries a watch/review qualifier on the same base direction,
                    # in which case the more specific wording wins regardless of
                    # source (module docstring, point 9).
                    outlook = _prefer_outlook(c["outlook"], g["outlook"])
                    merged_rows.append(
                        {
                            "date": c["date"],
                            "agency": agency,
                            "rating": c["rating"],
                            "outlook": outlook if pd.notna(outlook) else "",
                            "action": "",
                            "source": f"{c['source']} (confirmed by {g['source']})",
                        }
                    )
                else:
                    leftover_ge.append(g)
            leftover_ce = [c for i, c in enumerate(ce_bucket) if i not in matched_ce_idx]

            if leftover_ge and not leftover_ce:
                for g in leftover_ge:
                    merged_rows.append(
                        {"date": g["date"], "agency": agency, "rating": g["rating"],
                         "outlook": g["outlook"] if pd.notna(g["outlook"]) else "",
                         "action": "", "source": g["source"]}
                    )
            elif leftover_ce and not leftover_ge:
                for c in leftover_ce:
                    merged_rows.append(
                        {"date": c["date"], "agency": agency, "rating": c["rating"],
                         "outlook": c["outlook"] if pd.notna(c["outlook"]) else "",
                         "action": "", "source": c["source"]}
                    )
            elif leftover_ge and leftover_ce:
                # Genuine value conflicts -- pair positionally by date order.
                # Any surplus beyond the shorter list has no counterpart to
                # conflict against, so it's an addition, not a conflict.
                n = min(len(leftover_ge), len(leftover_ce))
                for i in range(n):
                    g, c = leftover_ge[i], leftover_ce[i]
                    ge_date_str = g["date"].strftime("%Y-%m-%d")
                    ce_date_str = c["date"].strftime("%Y-%m-%d")
                    res = resolutions_df[
                        (resolutions_df["agency"] == agency)
                        & (resolutions_df["ge_date"] == ge_date_str)
                        & (resolutions_df["ce_date"] == ce_date_str)
                    ]
                    if not res.empty:
                        chosen = res.iloc[0]["chosen_source"]
                        note = res.iloc[0]["note"]
                        winner = c if chosen == "CE" else g
                        merged_rows.append(
                            {
                                "date": winner["date"], "agency": agency, "rating": winner["rating"],
                                "outlook": winner["outlook"] if pd.notna(winner["outlook"]) else "",
                                "action": "",
                                "source": f"{winner['source']} (conflict resolved: {note})",
                            }
                        )
                        status, resolution_source, resolution_note = "resolved", chosen, note
                    else:
                        status, resolution_source, resolution_note = "OPEN", "", ""
                    conflict_rows.append(
                        {
                            "agency": agency, "month": str(month),
                            "ge_date": ge_date_str, "ge_rating": g["rating"], "ge_outlook": g["outlook"], "ge_source": g["source"],
                            "ce_date": ce_date_str, "ce_rating": c["rating"], "ce_outlook": c["outlook"], "ce_source": c["source"],
                            "status": status, "resolution_source": resolution_source, "resolution_note": resolution_note,
                        }
                    )
                for g in leftover_ge[n:]:
                    merged_rows.append(
                        {"date": g["date"], "agency": agency, "rating": g["rating"],
                         "outlook": g["outlook"] if pd.notna(g["outlook"]) else "",
                         "action": "", "source": g["source"]}
                    )
                for c in leftover_ce[n:]:
                    merged_rows.append(
                        {"date": c["date"], "agency": agency, "rating": c["rating"],
                         "outlook": c["outlook"] if pd.notna(c["outlook"]) else "",
                         "action": "", "source": c["source"]}
                    )

    merged_df = pd.DataFrame(merged_rows, columns=["date", "agency", "rating", "outlook", "action", "source"])
    merged_df = merged_df.sort_values(["agency", "date"]).reset_index(drop=True)
    merged_df["date"] = pd.to_datetime(merged_df["date"]).dt.strftime("%Y-%m-%d")

    conflicts_df = pd.DataFrame(
        conflict_rows,
        columns=["agency", "month", "ge_date", "ge_rating", "ge_outlook", "ge_source",
                 "ce_date", "ce_rating", "ce_outlook", "ce_source",
                 "status", "resolution_source", "resolution_note"],
    )
    if not conflicts_df.empty:
        conflicts_df = conflicts_df.sort_values(["agency", "month"]).reset_index(drop=True)

    return merged_df, conflicts_df


def main():
    parser = argparse.ArgumentParser(
        description="Reconcile TheGlobalEconomy (GE) and countryeconomy.com (CE) rating "
        "transcriptions for one country into data/raw/ratings/manual/<Country>.csv"
    )
    parser.add_argument("country", help="Country name, e.g. Greece (matches configs/universe.yaml)")
    parser.add_argument("--xlsx", required=True, help="Path to the two-sheet workbook")
    parser.add_argument("--ge-sheet", default=DEFAULT_GE_SHEET)
    parser.add_argument("--ce-sheet", default=DEFAULT_CE_SHEET)
    parser.add_argument(
        "--resolutions",
        default=None,
        help="CSV of conflict resolutions (agency,ge_date,ce_date,chosen_source,note). "
        "Defaults to _reconciliation/<Country>_resolutions.csv if present.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    country = args.country
    xlsx_path = Path(args.xlsx)
    RECONCILIATION_DIR.mkdir(parents=True, exist_ok=True)

    resolutions_path = Path(args.resolutions) if args.resolutions else RECONCILIATION_DIR / f"{country}_resolutions.csv"
    resolutions_df = _load_resolutions(resolutions_path)
    if not resolutions_df.empty:
        logging.info(f"Loaded {len(resolutions_df)} conflict resolution(s) from {resolutions_path}")

    ge_df = _load_sheet(xlsx_path, args.ge_sheet, "GE")
    ce_df = _load_sheet(xlsx_path, args.ce_sheet, "CE")

    merged_df, conflicts_df = reconcile(ge_df, ce_df, resolutions_df)

    country_path = MANUAL_DIR / f"{country}.csv"
    merged_df.to_csv(country_path, index=False)
    logging.info(f"Wrote {len(merged_df)} reconciled row(s) to {country_path}")

    conflicts_path = RECONCILIATION_DIR / f"{country}_conflicts.csv"
    conflicts_df.to_csv(conflicts_path, index=False)
    n_open = (conflicts_df["status"] == "OPEN").sum() if not conflicts_df.empty else 0
    n_resolved = (conflicts_df["status"] == "resolved").sum() if not conflicts_df.empty else 0
    logging.info(
        f"Wrote {len(conflicts_df)} conflict(s) to {conflicts_path} "
        f"({n_resolved} resolved, {n_open} open)"
    )
    if n_open:
        logging.warning(
            f"{n_open} OPEN conflict(s) need review -- add a matching row to "
            f"{resolutions_path} and re-run to fold them in"
        )


if __name__ == "__main__":
    main()
