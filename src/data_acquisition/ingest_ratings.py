"""Consolidate manually-collected sovereign rating histories into one
ratings_panel table (issue #3).

Why this isn't a scripted pull like macro_pull.py / bond_data_pull_reconstructed.py:
`TR.IssuerRating` (Refinitiv) only returns a current snapshot under our
licence -- SDate/EDate are silently ignored -- so it's a confirmed dead end
for history, not just an untried option. Free public sources were
evaluated as replacements and rejected as direct, automatable pipeline
inputs:
  - Damodaran's country risk dataset (NYU Stern, ctryprem.xlsx) is a
    current-snapshot table refreshed periodically (last checked: updated
    January 2026) with one rating per country -- no historical time series
    at all. Not usable for a lead/lag test that needs dated rating
    actions; only useful as an independent point-in-time cross-check.
  - Trading Economics exposes historical ratings only through its paid
    API tier; the free website surfaces current ratings only.

Primary manual source: TheGlobalEconomy.com, not countryeconomy.com
(switched 2026-08-10, before any country was transcribed against either,
so no rework was needed). countryeconomy.com was the original pick --
real dated history back to the 1990s for many countries -- but turned out
to have a structural trap: each country page lays out four *independent*
chronological lists (Long-term Foreign Currency, Long-term Local
Currency, Short-term Foreign Currency, Short-term Local Currency) side by
side in one HTML table, positioned by row-index, not by shared date.
Adjacent columns on the same visual row are frequently different,
unrelated dates -- confirmed on Greece's page, where the row showing
"2022-04-22 BB+ (Stable)" in the Foreign Currency column pairs visually
with "2025-04-18 BBB" in the Local Currency column, a different action
three years apart. Only the Long-term, Foreign-Currency pair is relevant
to our USD-denominated universe -- the other three columns must be
ignored entirely, not read row-aligned, which is a real transcription-error
risk if missed. It also sometimes leaves the rating cell blank on an
outlook-only-change row, forcing inference from the row above -- another
error-prone spot. TheGlobalEconomy.com's per-country tables are flat,
single-list, multi-agency (agency | rating | outlook | date), and every
row carries an explicit rating value even when only the outlook changed
-- no blank-cell inference needed, and a near-exact structural match to
this script's raw-file schema below. countryeconomy.com is now a
fallback only, for countries/periods TheGlobalEconomy.com doesn't cover,
used with the column-alignment caveat above kept firmly in mind. Both
remain third-party aggregators, not primary agency sources, so citation
in the thesis should name them as such; their Terms of Use should be
checked before any bulk/automated (as opposed to manual, per-row)
extraction.
  - **Scope** is a 4th agency TheGlobalEconomy.com's tables include
    alongside S&P/Moody's/Fitch. It's out of scope for this thesis and
    for RATING_MAP -- drop Scope rows during transcription, don't ingest
    them. VALID_AGENCIES below rejects them defensively if one slips
    through.
  - **Date precision**: TheGlobalEconomy.com gives month/year precision
    only (e.g. "5/2026"), not exact day, unlike countryeconomy.com.
    Convention: use the 1st of the month as `date`, and append
    "(month-precision)" to `source` for traceability. This is coarser
    than exact-day but still well within thesis Sec 4.5.1's quarterly
    walk-forward fold granularity, so H1's quarter-level lead/lag windows
    lose no real resolution. It does not interact with
    test_lag_rules.py's zero-lag assertion for ratings either --
    `available_date` is always set equal to whatever `date` value is in
    the raw file (see build_ratings_panel below), exact-day or
    1st-of-month alike, so that check passes trivially regardless of
    precision; it was never validating precision, only that
    available_date == date. The real risk from mixing precisions is
    elsewhere: the same real-world action, transcribed once from an
    exact-day source and once from a month-precision source, would look
    like two distinct nearby rows instead of one -- see
    _warn_possible_duplicate_actions below, which flags same
    country+agency+rating_numeric pairs less than 35 days apart for
    manual review rather than silently double-counting them (and
    potentially inflating the lead/lag event count with a phantom
    action).

Given all that, this script does not scrape or call any API. It reads
whatever raw per-country rating-history files have already been manually
collected -- transcribed from TheGlobalEconomy.com (primary),
countryeconomy.com (fallback, mind the column-alignment caveat above), or
from S&P/Moody's/Fitch investor-relations and press-release pages -- and
dropped into data/raw/ratings/manual/<Country>.csv (see _TEMPLATE.csv
there for the exact format), then normalizes them into one consolidated
table at data/processed/ratings_panel.csv. It's meant to be re-run
incrementally: countries with no raw file yet are simply absent from the
output, not an error, so partial coverage can land over time as files are
added.

For a country where both GE and CE were transcribed (the recommended
approach going forward, since cross-referencing Greece surfaced real,
non-overlapping coverage in each -- see below), don't hand-merge them:
run reconcile_ratings_sources.py first, which applies a documented
priority policy (CE wins for default designations, conflicts get flagged
not silently resolved) and writes the <Country>.csv this script then
picks up.

`outlook` is carried through to the output panel as its own column, not
just used internally to help infer `action` -- outlook deterioration
(e.g. Stable -> Negative with no letter-grade change) often precedes an
actual downgrade by months, a potential leading-indicator signal beyond
letter-grade actions alone. Thesis Sec 1.5/4.2.4's formal H1 test is
defined against letter-grade downgrades specifically, so this isn't
required for that test, but it's captured now -- while the schema is
still young and the marginal transcription cost is ~zero (the outlook
value is already being read off the same row) -- rather than retrofitted
later if a future analysis wants it.

Deliberately does not touch data/raw/ratings/*.csv (the existing
header-only stubs from the never-recovered original pull) -- those are
read by nothing and kept only as provenance of the abandoned attempt; see
CLAUDE.md. This script only ever reads from data/raw/ratings/manual/ and
writes to data/processed/, consistent with "data/raw/ is READ-ONLY" for
processing scripts.

Run directly: python3 src/data_acquisition/ingest_ratings.py
"""

import logging
from pathlib import Path

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / "ratings" / "manual"
UNIVERSE_YAML = REPO_ROOT / "configs" / "universe.yaml"
PARAMS_YAML = REPO_ROOT / "configs" / "params.yaml"

# Copied from the now-dead src/data_acquisition/eikon_sovereign_pull_deprecated.py
# (RATING_MAP) -- that script never produced any data, but the mapping itself
# is just a standard ordinal scale, independent of how the ratings were pulled.
RATING_MAP = {
    "AAA": 1, "Aaa": 1,
    "AA+": 2, "Aa1": 2,
    "AA": 3, "Aa2": 3,
    "AA-": 4, "Aa3": 4,
    "A+": 5, "A1": 5,
    "A": 6, "A2": 6,
    "A-": 7, "A3": 7,
    "BBB+": 8, "Baa1": 8,
    "BBB": 9, "Baa2": 9,
    "BBB-": 10, "Baa3": 10,
    "BB+": 11, "Ba1": 11,
    "BB": 12, "Ba2": 12,
    "BB-": 13, "Ba3": 13,
    "B+": 14, "B1": 14,
    "B": 15, "B2": 15,
    "B-": 16, "B3": 16,
    "CCC+": 17, "Caa1": 17,
    "CCC": 18, "Caa2": 18,
    "CCC-": 19, "Caa3": 19,
    "CC": 20, "Ca": 20,
    # "Ca-" is not a real Moody's notch -- confirmed against Moody's own
    # scale documentation (2026-08-11, Zambia): long-term modifiers
    # (1/2/3) only apply Aaa through Caa3; Ca and C are unmodified. Found
    # as a literal GE row for Zambia (2020-04, right in the default
    # window) -- a transcription/formatting artifact for "Ca", not a
    # distinct grade. Aliased here rather than corrected in the source
    # string, consistent with how RATING_MAP already aliases multiple
    # real notations (e.g. "AAA"/"Aaa") to one ordinal value.
    "Ca-": 20,
    "C": 21,
    "D": 22, "SD": 22, "RD": 22,
}

VALID_AGENCIES = {"S&P", "Moody's", "Fitch"}  # Scope (TheGlobalEconomy.com's 4th) deliberately excluded
REQUIRED_COLUMNS = {"date", "agency", "rating"}
OUTPUT_COLUMNS = [
    "country", "agency", "date", "rating", "rating_numeric", "outlook",
    "action", "source", "available_date",
]
# Same country+agency+rating_numeric rows closer together than this are
# flagged as a likely duplicate of one real action transcribed twice from
# sources with different date precision (see module docstring). Wider than
# a calendar month to absorb the "1st of month" rounding on month-precision
# sources versus an exact day elsewhere.
DUPLICATE_ACTION_WINDOW_DAYS = 35


def _load_country_file(path: Path) -> pd.DataFrame:
    """Read and validate one manually-collected raw rating file."""
    country = path.stem
    df = pd.read_csv(path, parse_dates=["date"])

    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(f"{path}: missing required column(s) {missing_cols}")

    df["agency"] = df["agency"].str.strip()
    unknown_agencies = set(df["agency"]) - VALID_AGENCIES
    if unknown_agencies:
        raise ValueError(
            f"{path}: unknown agency value(s) {unknown_agencies}, "
            f"expected one of {VALID_AGENCIES}"
        )

    df["rating"] = df["rating"].str.strip()
    df["rating_numeric"] = df["rating"].map(RATING_MAP)
    unmapped = df.loc[df["rating_numeric"].isna(), "rating"]
    if not unmapped.empty:
        raise ValueError(
            f"{path}: unmapped rating value(s) {sorted(unmapped.unique())} "
            f"-- add to RATING_MAP if this is a legitimate notch"
        )

    df["country"] = country
    if "outlook" not in df.columns:
        df["outlook"] = pd.NA
    if "action" not in df.columns:
        df["action"] = pd.NA
    if "source" not in df.columns:
        df["source"] = pd.NA
    return df


def _fill_missing_actions(df: pd.DataFrame) -> pd.DataFrame:
    """Infer action (upgrade/downgrade/outlook_change/affirm) for rows left
    blank in the raw file, chronologically per country+agency. Explicit
    values in the raw file are always kept as-is -- only blanks are
    filled. When the letter rating is unchanged but `outlook` differs from
    the previous row (e.g. Stable -> Negative), infers "outlook_change"
    rather than a blanket "affirm" -- outlook moves are a plausible
    leading indicator ahead of an eventual letter-grade action (see module
    docstring), so collapsing them into "affirm" would throw that signal
    away for free."""
    filled_groups = []
    for _, group in df.groupby(["country", "agency"], sort=False):
        group = group.sort_values("date").copy()
        prev_numeric = None
        prev_outlook = None
        inferred = []
        for _, row in group.iterrows():
            explicit = row["action"]
            has_explicit = pd.notna(explicit) and str(explicit).strip() != ""
            outlook = row["outlook"]
            has_outlook = pd.notna(outlook) and str(outlook).strip() != ""

            if has_explicit:
                inferred.append(str(explicit).strip())
            elif prev_numeric is None:
                inferred.append("initial")
            elif row["rating_numeric"] < prev_numeric:
                inferred.append("upgrade")
            elif row["rating_numeric"] > prev_numeric:
                inferred.append("downgrade")
            elif (
                has_outlook
                and prev_outlook is not None
                and str(outlook).strip() != str(prev_outlook).strip()
            ):
                inferred.append("outlook_change")
            else:
                inferred.append("affirm")

            prev_numeric = row["rating_numeric"]
            if has_outlook:
                prev_outlook = outlook
        group["action"] = inferred
        filled_groups.append(group)
    return pd.concat(filled_groups, ignore_index=True)


def _is_month_precision_only(source) -> bool:
    """True only for a row whose date is actually imprecise -- rounded to
    the 1st of its month, straight from a month-precision source with no
    exact-day corroboration. Rows produced by
    reconcile_ratings_sources.py's cross-source matching always carry an
    exact CE date even when a GE month-precision row helped confirm it
    (their source string reads "... (confirmed by ... month-precision
    ...)"), so those don't count as imprecise -- only an unconfirmed,
    still-just-GE row does."""
    s = str(source)
    return "(month-precision)" in s and "confirmed by" not in s


def _warn_possible_duplicate_actions(
    panel: pd.DataFrame, window_days: int = DUPLICATE_ACTION_WINDOW_DAYS
) -> None:
    """Flag same country+agency+rating_numeric rows within window_days of
    each other where exactly one side is an unconfirmed month-precision
    row (see _is_month_precision_only) -- the actual mixed-precision
    duplicate risk this guards against: one real action transcribed once
    from an exact-day source and once from a "1st of month" source.
    Deliberately does NOT fire on two same-precision rows close together
    (e.g. two exact-day CE rows a few weeks apart) -- on real data
    (Greece), that pattern turned out to be legitimate dense surveillance
    reporting during the 2013-2014 crisis (CE re-affirmed Fitch's rating
    every 1-4 weeks with no change), not duplicates; an earlier version of
    this check fired on every one of those ~25 pairs, which would have
    buried the one warning that actually mattered under noise. Logged as
    a warning, not a hard error -- kept advisory since a few genuinely
    mixed-precision-and-close actions are possible and shouldn't block a
    build."""
    for (country, agency), group in panel.groupby(["country", "agency"], sort=False):
        group = group.sort_values("date")
        dates = group["date"].tolist()
        numerics = group["rating_numeric"].tolist()
        sources = group["source"].tolist()
        for i in range(1, len(dates)):
            gap_days = (dates[i] - dates[i - 1]).days
            if numerics[i] != numerics[i - 1] or not (0 < gap_days <= window_days):
                continue
            if _is_month_precision_only(sources[i]) == _is_month_precision_only(sources[i - 1]):
                continue
            logging.warning(
                f"Possible duplicate action: {country}/{agency} has two rows at "
                f"rating_numeric={numerics[i]} only {gap_days} day(s) apart, one "
                f"unconfirmed month-precision and one exact-day "
                f"({dates[i - 1].date()} [{sources[i - 1]}] and "
                f"{dates[i].date()} [{sources[i]}]) -- check whether this is "
                f"one real action transcribed from two differently-precise "
                f"sources rather than two genuine reviews"
            )


def build_ratings_panel(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    if not raw_dir.exists():
        raise FileNotFoundError(
            f"{raw_dir} does not exist -- create it and add manually "
            f"collected per-country files (see _TEMPLATE.csv)"
        )

    files = sorted(p for p in raw_dir.glob("*.csv") if not p.name.startswith("_"))
    if not files:
        logging.warning(f"No raw rating files found in {raw_dir} yet -- returning empty panel")
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    panel = pd.concat([_load_country_file(p) for p in files], ignore_index=True)
    panel = _fill_missing_actions(panel)

    # Rating actions are same-day public announcements (agency press
    # releases / RNS filings) -- unlike World Bank/IMF's multi-month
    # publication lag for periodic macro releases, there's no lag to
    # model. Asserted by test_lag_rules.py.
    panel["available_date"] = panel["date"]

    panel = panel.sort_values(["country", "agency", "date"]).reset_index(drop=True)
    _warn_possible_duplicate_actions(panel)
    return panel[OUTPUT_COLUMNS]


def _log_coverage(panel: pd.DataFrame) -> None:
    with open(UNIVERSE_YAML) as f:
        universe = yaml.safe_load(f)["universe"]
    all_countries = {c["name"].replace(" ", "_") for c in universe}
    covered = set(panel["country"].unique()) if not panel.empty else set()
    missing = sorted(all_countries - covered)

    logging.info(f"Ratings coverage: {len(covered)}/{len(all_countries)} universe countries have a raw file")
    if missing:
        logging.info(f"No raw ratings file yet for: {', '.join(missing)}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    panel = build_ratings_panel()

    output_dir = REPO_ROOT / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "ratings_panel.csv"
    panel.to_csv(output_path, index=False)
    logging.info(f"Wrote {len(panel)} row(s) to {output_path}")

    _log_coverage(panel)


if __name__ == "__main__":
    main()
