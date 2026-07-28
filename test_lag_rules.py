"""
The project's core bias-prevention check (see CLAUDE.md, "Bias-prevention
rules"). Covers macro data acquisition today (src/data_acquisition/macro_pull.py);
extend with walk-forward / feature-construction checks as those are built:
  - no test-window data leaks into training-window fitting, normalization,
    or feature selection stats

Run directly: python3 test_lag_rules.py
Exits 0 on pass, 1 on failure (so it can gate a pre-commit / hook check).
"""

import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parent
MACRO_CSV = REPO_ROOT / "data" / "raw" / "macro" / "macro_fundamentals.csv"
PARAMS_YAML = REPO_ROOT / "configs" / "params.yaml"


def _add_months(d: date, months: int) -> date:
    y, m = d.year, d.month + months
    while m > 12:
        m -= 12
        y += 1
    return date(y, m, 1)


def test_macro_available_date_never_precedes_period_date():
    """No macro observation may claim to be usable before the period it
    describes has even ended."""
    if not MACRO_CSV.exists():
        print(f"SKIP: {MACRO_CSV} does not exist yet")
        return
    df = pd.read_csv(MACRO_CSV, parse_dates=["period_date", "available_date"])
    violations = df[df["available_date"] < df["period_date"]]
    assert violations.empty, (
        f"{len(violations)} row(s) have available_date before period_date, "
        f"e.g.:\n{violations.head()}"
    )


def test_macro_available_date_respects_configured_publication_lag():
    """For World Bank / IMF WEO rows, available_date must equal period_date
    (year-end) shifted forward by the source's configured lag in
    configs/params.yaml -- not same-day, not an arbitrary/looser gap."""
    if not MACRO_CSV.exists():
        print(f"SKIP: {MACRO_CSV} does not exist yet")
        return
    with open(PARAMS_YAML) as f:
        params = yaml.safe_load(f)["macro_acquisition"]

    df = pd.read_csv(MACRO_CSV, parse_dates=["period_date", "available_date"])
    lag_months = {
        "world_bank": params["lag_months_world_bank"],
        "imf_weo": params["lag_months_imf_weo"],
    }
    violations = []
    for source, months in lag_months.items():
        subset = df[df["source"] == source]
        for _, row in subset.iterrows():
            expected = _add_months(row["period_date"].date(), months)
            if row["available_date"].date() != expected:
                violations.append((source, row["country"], row["series"], row["period_date"]))
    assert not violations, f"{len(violations)} row(s) don't match configured lag: {violations[:5]}"


def test_macro_fred_available_date_respects_lag_days():
    """FRED (daily) rows must be lagged by exactly lag_days_fred, not
    available same-day."""
    if not MACRO_CSV.exists():
        print(f"SKIP: {MACRO_CSV} does not exist yet")
        return
    with open(PARAMS_YAML) as f:
        params = yaml.safe_load(f)["macro_acquisition"]
    lag_days = params["lag_days_fred"]

    df = pd.read_csv(MACRO_CSV, parse_dates=["period_date", "available_date"])
    subset = df[df["source"] == "fred"]
    if subset.empty:
        print("SKIP: no FRED rows present")
        return
    gaps = (subset["available_date"] - subset["period_date"]).dt.days
    assert (gaps == lag_days).all(), (
        f"FRED rows with unexpected lag (expected {lag_days} day(s)): "
        f"{sorted(gaps.unique())}"
    )


CHECKS = [
    test_macro_available_date_never_precedes_period_date,
    test_macro_available_date_respects_configured_publication_lag,
    test_macro_fred_available_date_respects_lag_days,
]


def main():
    failures = []
    for check in CHECKS:
        try:
            check()
            print(f"PASS: {check.__name__}")
        except AssertionError as e:
            failures.append((check.__name__, str(e)))
            print(f"FAIL: {check.__name__}: {e}")

    if failures:
        print(f"\n{len(failures)} check(s) failed.")
        return 1

    print(f"\nAll {len(CHECKS)} check(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
