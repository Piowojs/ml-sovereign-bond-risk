"""Source-agnostic sanity check on data/processed/ratings_panel.csv
(issue #3) -- a diagnostic, not a re-transcription tool. Built after
discovering that a factually wrong Sri Lanka row (S&P, "A", 2007-01-23 --
Sri Lanka was in the B range throughout that period) had survived
undetected since the country was first reconciled (2026-08-11), because
it never collided with a GE row to produce a conflict.

That discovery exposed a real blind spot in the reconciliation pipeline's
validation: `reconcile_ratings_sources.py`'s conflict detection only
checks rows where *both* sources have an entry for the same (agency,
month) -- it says nothing about rows carried by only one source, which is
most rows in most countries, and the entirety of some agencies (Zambia's
and Nigeria's Moody's history is 100% GE-only, never cross-validated
against anything). This script checks single-sourced rows against
*internal* consistency instead -- a country's own rating history has to
be internally plausible even where there's no second source to compare
against.

Three independent checks, all source-agnostic (a bad row from either GE
or CE looks the same to this script):

1. **Implausible jumps**: for each (country, agency), sorted
   chronologically, flag any consecutive rating_numeric change of more
   than `JUMP_NOTCH_THRESHOLD` notches. Sri Lanka's B+ -> A was ~9
   notches in one transcribed action -- agencies essentially never move
   that fast (a genuine multi-notch collapse, like Portugal's 2011-12 or
   Spain's 2010-12, still happens over several separate actions spread
   across months, each individually only 1-3 notches).
2. **Range outliers**: for each country, flag any single row whose
   rating_numeric is a robust statistical outlier (modified z-score,
   MAD-based so one bad row doesn't drag the reference range toward
   itself) against that country's *entire* multi-agency history. Catches
   the same Sri Lanka case from a different angle -- an isolated "A" sitting
   in an otherwise B-range history -- and would also catch a bad row that
   didn't happen to look like a "jump" (e.g. if the surrounding rows
   themselves were sparse or irregularly dated).
3. **Single-source exposure**: per (country, agency), what fraction of
   rows were never cross-validated against the other source at all (no
   "confirmed by" and no "conflict resolved" in the `source` field) --
   quantifies how much of the panel this audit is the *only* check on,
   since conflict detection structurally can't see these rows.

Output: three CSVs in data/processed/ (ratings_sanity_jumps.csv,
ratings_sanity_range_outliers.csv, ratings_sanity_single_source.csv) plus
a printed summary. Flags things for human review; corrects nothing.

Run: python3 src/data_acquisition/sanity_check_ratings.py
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RATINGS_PANEL_PATH = REPO_ROOT / "data" / "processed" / "ratings_panel.csv"
OUTPUT_DIR = REPO_ROOT / "data" / "processed"

JUMP_NOTCH_THRESHOLD = 4
# Modified z-score threshold (Iglewicz & Hoaglin's standard rule of thumb
# for MAD-based outlier detection) -- widely used, not specific to this
# script.
RANGE_OUTLIER_Z_THRESHOLD = 3.5


def _is_cross_validated(source: str) -> bool:
    """True if this row was checked against the other source at all --
    either they agreed ("confirmed by") or they disagreed and it was
    adjudicated ("conflict resolved"). False means single-sourced: never
    seen by anything except this diagnostic."""
    s = str(source)
    return "confirmed by" in s or "conflict resolved" in s


def find_implausible_jumps(df: pd.DataFrame, threshold: int = JUMP_NOTCH_THRESHOLD) -> pd.DataFrame:
    rows = []
    for (country, agency), group in df.groupby(["country", "agency"], sort=False):
        group = group.sort_values("date")
        dates = group["date"].tolist()
        nums = group["rating_numeric"].tolist()
        ratings = group["rating"].tolist()
        sources = group["source"].tolist()
        for i in range(1, len(dates)):
            jump = nums[i] - nums[i - 1]
            if abs(jump) > threshold:
                rows.append(
                    {
                        "country": country,
                        "agency": agency,
                        "date_from": dates[i - 1],
                        "rating_from": ratings[i - 1],
                        "date_to": dates[i],
                        "rating_to": ratings[i],
                        "notch_jump": jump,
                        "source_from": sources[i - 1],
                        "source_to": sources[i],
                    }
                )
    return pd.DataFrame(rows).sort_values("notch_jump", key=lambda s: s.abs(), ascending=False) if rows else pd.DataFrame(
        columns=["country", "agency", "date_from", "rating_from", "date_to", "rating_to", "notch_jump", "source_from", "source_to"]
    )


def find_range_outliers(df: pd.DataFrame, z_threshold: float = RANGE_OUTLIER_Z_THRESHOLD) -> pd.DataFrame:
    rows = []
    for country, group in df.groupby("country", sort=False):
        nums = group["rating_numeric"].to_numpy(dtype=float)
        median = np.median(nums)
        mad = np.median(np.abs(nums - median))
        if mad == 0:
            continue  # every row identical -- no meaningful outlier concept
        modified_z = 0.6745 * (nums - median) / mad
        outlier_mask = np.abs(modified_z) > z_threshold
        for (_, row), z in zip(group[outlier_mask].iterrows(), modified_z[outlier_mask]):
            rows.append(
                {
                    "country": country,
                    "agency": row["agency"],
                    "date": row["date"],
                    "rating": row["rating"],
                    "rating_numeric": row["rating_numeric"],
                    "country_median_numeric": median,
                    "modified_z_score": round(float(z), 2),
                    "source": row["source"],
                }
            )
    return pd.DataFrame(rows).sort_values("modified_z_score", key=lambda s: s.abs(), ascending=False) if rows else pd.DataFrame(
        columns=["country", "agency", "date", "rating", "rating_numeric", "country_median_numeric", "modified_z_score", "source"]
    )


def single_source_exposure(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (country, agency), group in df.groupby(["country", "agency"], sort=False):
        n_total = len(group)
        n_cross_validated = group["source"].apply(_is_cross_validated).sum()
        n_single_sourced = n_total - n_cross_validated
        rows.append(
            {
                "country": country,
                "agency": agency,
                "n_rows": n_total,
                "n_single_sourced": int(n_single_sourced),
                "pct_single_sourced": round(100 * n_single_sourced / n_total, 1),
            }
        )
    return pd.DataFrame(rows).sort_values(["pct_single_sourced", "n_rows"], ascending=[False, False])


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    df = pd.read_csv(RATINGS_PANEL_PATH, parse_dates=["date"])

    jumps = find_implausible_jumps(df)
    outliers = find_range_outliers(df)
    exposure = single_source_exposure(df)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    jumps_path = OUTPUT_DIR / "ratings_sanity_jumps.csv"
    outliers_path = OUTPUT_DIR / "ratings_sanity_range_outliers.csv"
    exposure_path = OUTPUT_DIR / "ratings_sanity_single_source.csv"
    jumps.to_csv(jumps_path, index=False)
    outliers.to_csv(outliers_path, index=False)
    exposure.to_csv(exposure_path, index=False)

    print(f"=== Implausible jumps (>{JUMP_NOTCH_THRESHOLD} notches between consecutive same-agency actions) ===")
    print(f"{len(jumps)} flagged, written to {jumps_path}")
    if not jumps.empty:
        with pd.option_context("display.max_columns", None, "display.width", 200):
            print(jumps.to_string(index=False))

    print(f"\n=== Range outliers (modified z-score > {RANGE_OUTLIER_Z_THRESHOLD} vs country's own history) ===")
    print(f"{len(outliers)} flagged, written to {outliers_path}")
    if not outliers.empty:
        with pd.option_context("display.max_columns", None, "display.width", 200):
            print(outliers.to_string(index=False))

    print(f"\n=== Single-source exposure (never cross-validated against the other source), written to {exposure_path} ===")
    overall_single = exposure["n_single_sourced"].sum()
    overall_total = exposure["n_rows"].sum()
    print(f"Overall: {overall_single}/{overall_total} rows ({100*overall_single/overall_total:.1f}%) never cross-validated")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(exposure.to_string(index=False))


if __name__ == "__main__":
    main()
