"""Reconcile TheGlobalEconomy (GE) and countryeconomy.com (CE) rating
transcriptions for one country into data/raw/ratings/manual/<Country>.csv
(issue #3).

Why this exists: cross-referencing both sources for the same country
(first done for Greece, 2026-08-10) surfaced three structural
disagreements between them that a naive "pick a primary source" merge
would get wrong:

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

EMBEDDED_OUTLOOK_RE = re.compile(r"^(?P<rating>.*?)\s*\((?P<outlook>[^)]+)\)\s*$")


def _rating_numeric(rating) -> int | None:
    if pd.isna(rating) or not str(rating).strip():
        return None
    return RATING_MAP.get(str(rating).strip())


_WATCH_TOKENS = ("watch", "review")


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
    mention "watch"/"review" agrees regardless of exact wording. Anything
    else (e.g. "Stable" vs "Positive", both non-blank, neither a
    watch/review state) is a genuine disagreement."""
    a = "" if pd.isna(a) else str(a).strip().lower()
    b = "" if pd.isna(b) else str(b).strip().lower()
    if a == "" or b == "":
        return True
    if a == b:
        return True
    if any(tok in a for tok in _WATCH_TOKENS) and any(tok in b for tok in _WATCH_TOKENS):
        return True
    return False


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


def _clean_rating_outlook(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace on rating/outlook, and strip an outlook embedded in
    the rating field (e.g. "BBB (Positive)") out into the outlook column
    when outlook itself is otherwise blank."""
    df = df.copy()

    def _strip(v):
        return str(v).strip() if pd.notna(v) and str(v).strip() else pd.NA

    df["rating"] = df["rating"].apply(_strip)
    df["outlook"] = df["outlook"].apply(_strip)

    def _extract(row):
        rating = row["rating"]
        if pd.isna(rating):
            return rating, row["outlook"]
        m = EMBEDDED_OUTLOOK_RE.match(str(rating))
        if not m:
            return rating, row["outlook"]
        extracted_rating = m.group("rating").strip()
        extracted_outlook = m.group("outlook").strip()
        outlook = row["outlook"] if pd.notna(row["outlook"]) else extracted_outlook
        return extracted_rating, outlook

    df[["rating", "outlook"]] = df.apply(lambda r: pd.Series(_extract(r)), axis=1)
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
    ge_df = _clean_rating_outlook(ge_df)
    ce_df = _clean_rating_outlook(ce_df)

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
                    # _outlook_eq treats a blank side as agreeing with anything, so
                    # "matched" doesn't mean both sides said the same thing -- prefer
                    # whichever side actually has a value (CE first) rather than
                    # blindly taking CE's, which could be the blank one and silently
                    # drop real information GE captured (e.g. CE blank vs GE "Stable").
                    outlook = c["outlook"] if pd.notna(c["outlook"]) else g["outlook"]
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
