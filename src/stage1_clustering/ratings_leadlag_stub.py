"""Thesis Sec 4.2.4 lead/lag analysis vs agency ratings -- PILOT, not the
full implementation. Retains the original "stub" filename deliberately
(see note at the bottom of this docstring) even though `compute_lead_lag`
is now real code, because this is still explicitly scoped to a 5-country
pilot, not the full-universe §4.2.4 result the thesis will actually cite.

## Why a pilot, and why now
As of this writing, `data/processed/ratings_panel.csv` covers exactly 5 of
44 countries -- Greece, Turkey, Sri Lanka, Portugal, Zambia ("Tier 1" in
state.md's ratings transcription priority list: the crisis case studies
and both default-event countries the thesis outline names explicitly).
The remaining 39 countries have not been transcribed yet. This script
exists to answer one question before committing more time to manual
transcription: does H1's mechanism (ML risk score deteriorates ahead of
the agency downgrade) show up at all in the best-case, highest-signal
countries? A "no" or "mixed" result here is exactly as useful as a "yes"
for planning purposes -- see the pooled/per-country results this script
prints for the actual read.

## Two pipelines, and this script only trusts one of them
`src/stage1_clustering/algorithm_comparison.py` fits its clustering ONCE
on the full 2005-2025 panel, pooled across all quarters -- diagnostic
only, and explicitly NOT point-in-time safe (see clustering_utils.py's
module docstring and CLAUDE.md's "Stage 1 clustering" section). This
script deliberately does NOT use that pipeline's output. It uses
`data/processed/stage1_risk_labels.parquet`, written by
`build_risk_labels.py`'s `label_panel()`, which refits at every
rebalancing date using only rows with `rebal_date <= that date`. A
downgrade-date test that used the diagnostic fit would be testing a model
that implicitly already "knows" about the downgrade (and everything
after it) when scoring the quarters before it -- exactly the look-ahead
bias H1's test is supposed to rule out, not commit.

## What changed to make this possible
`build_risk_labels.py` previously only emitted a categorical `risk_label`
(core-eligible / excluded / satellite-candidate / insufficient_data).
H1's test needs a continuous score to average over 1-4 quarters and
paired-t-test, so `build_risk_labels.py` was extended with a `risk_score`
column (0 = sitting on the low-risk centroid, 1 = sitting on the
high-risk centroid, walk-forward-safe by the same construction as
`risk_label`) -- see that module's `_continuous_risk_score` docstring.
Only implemented for K-Means (the chosen production algorithm); if the
chosen algorithm ever changes, this needs a real extension, not a patch.

## Test design (thesis Sec 1.5, H1)
For each downgrade event (one row of the ratings panel with
action == "downgrade"): the "near window" is the up-to-4 rebalancing
quarters with rebal_date strictly before the downgrade date (i.e. the
1st-4th quarters preceding it); the "pre-event baseline" is the up-to-4
quarters immediately before that. A paired, one-sided t-test (H1 as
stated is directional -- "a statistically significant *increase* in risk
score ahead of the downgrade") compares near-window means to
baseline-window means across events. Reported per-country and pooled.

## Known limitations of this pilot (read before citing anything from it)
- **5 countries, several with short histories.** Zambia's first
  downgrade-eligible history starts 2011; several of its events fall too
  close to the 2005-2006 insufficient_data period for a full 8-quarter
  lookback -- flagged per-event, not silently dropped or forced through.
- **Events are not independent.** A "downgrade event" here is one ratings
  panel row (one agency, one date) -- during acute crises (Greece
  2010-2012, Portugal 2011) multiple agencies downgraded within weeks of
  each other, so several "events" share almost the same near/baseline
  windows. The paired t-test as specified in thesis Sec 1.5 does not
  address this; treat any pooled p-value as optimistic, not a real
  independent-events test.
- **Agency source-coverage gaps.** Some (country, agency) pairs in the
  ratings panel are single-sourced (TheGlobalEconomy.com only, no
  countryeconomy.com corroboration) rather than the cross-checked default
  -- most notably Zambia/Moody's, which is 100% GE-only (11/11 rows; see
  state.md's 2026-08-11 Zambia entry). Events built from single-sourced
  agency data are flagged, not excluded.
- **This is a feasibility check, not a §5.1 result.** Even a clean
  positive finding here should not be written into CLAUDE.md's "settled
  facts" style documentation or cited in the thesis yet -- it's 5 of 44
  countries, chosen specifically because they're the highest-signal
  cases, which is a form of selection that a real §5.1 result must not
  have.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[2]
RISK_LABELS_PATH = REPO_ROOT / "data" / "processed" / "stage1_risk_labels.parquet"
RATINGS_PANEL_PATH = REPO_ROOT / "data" / "processed" / "ratings_panel.csv"

NEAR_WINDOW_QUARTERS = 4
BASELINE_WINDOW_QUARTERS = 4
MIN_VALID_QUARTERS_PER_WINDOW = 2  # below this, an event is "insufficient_history"


def _normalize_country_name(raw: str) -> str:
    """ratings_panel.csv's `country` column uses the underscore form
    (e.g. "Sri_Lanka") -- the output filename convention documented in
    state.md, matching configs/universe.yaml's `name.replace(' ', '_')`.
    stage1_risk_labels.parquet's `country_name` uses the space form."""
    return raw.replace("_", " ")


def _ge_only_flag(ratings_panel_df: pd.DataFrame) -> dict:
    """(country, agency) -> True if every row for that pair is sourced
    solely from TheGlobalEconomy.com (no countryeconomy.com
    corroboration) -- the single-source coverage gap flagged in this
    module's docstring."""
    is_ge_only = ratings_panel_df["source"].str.fullmatch(
        r"theglobaleconomy\.com \(month-precision\)", na=False
    )
    by_pair = ratings_panel_df.assign(is_ge_only=is_ge_only).groupby(["country", "agency"])["is_ge_only"]
    return {pair: bool(all_ge) for pair, all_ge in by_pair.all().items()}


def compute_lead_lag(risk_labels_df: pd.DataFrame, ratings_panel_df: pd.DataFrame,
                      near_window_quarters: int = NEAR_WINDOW_QUARTERS,
                      baseline_window_quarters: int = BASELINE_WINDOW_QUARTERS,
                      min_valid_quarters_per_window: int = MIN_VALID_QUARTERS_PER_WINDOW
                      ) -> pd.DataFrame:
    """One row per downgrade event in ratings_panel_df, with the near-
    window / baseline-window risk_score means and a status flag. Does NOT
    run the t-test itself (see summarize_lead_lag below) -- this is the
    per-event building block, kept separate so the event table can be
    inspected/audited on its own.

    Required risk_labels_df columns: country_name, rebal_date, risk_score.
    Required ratings_panel_df columns: country, agency, date, action,
    source. Only action == "downgrade" rows are used.
    """
    downgrades = ratings_panel_df[ratings_panel_df["action"] == "downgrade"].copy()
    downgrades["country_name"] = downgrades["country"].map(_normalize_country_name)
    ge_only = _ge_only_flag(ratings_panel_df)

    risk_labels_df = risk_labels_df.sort_values(["country_name", "rebal_date"])
    max_rebal_date = risk_labels_df["rebal_date"].max()

    rows = []
    for _, ev in downgrades.iterrows():
        country = ev["country_name"]
        event_date = ev["date"]
        row = {
            "country": country,
            "agency": ev["agency"],
            "downgrade_date": event_date,
            "rating": ev["rating"],
            "single_sourced_ge_only": ge_only.get((ev["country"], ev["agency"]), False),
        }

        if event_date > max_rebal_date:
            row["status"] = "event_after_panel_end"
            rows.append(row)
            continue

        country_scores = risk_labels_df[risk_labels_df["country_name"] == country]
        preceding = country_scores[country_scores["rebal_date"] < event_date]

        if preceding.empty:
            row["status"] = "no_preceding_data"
            rows.append(row)
            continue

        near = preceding.tail(near_window_quarters)
        remaining = preceding.iloc[: len(preceding) - len(near)]
        baseline = remaining.tail(baseline_window_quarters)

        near_valid = near["risk_score"].dropna()
        baseline_valid = baseline["risk_score"].dropna()

        row.update({
            "n_near_available": len(near),
            "n_near_valid": len(near_valid),
            "n_baseline_available": len(baseline),
            "n_baseline_valid": len(baseline_valid),
        })

        if len(near_valid) < min_valid_quarters_per_window or len(baseline_valid) < min_valid_quarters_per_window:
            row["status"] = "insufficient_history"
            rows.append(row)
            continue

        near_mean = float(near_valid.mean())
        baseline_mean = float(baseline_valid.mean())
        row.update({
            "status": "ok",
            "near_mean_risk_score": near_mean,
            "baseline_mean_risk_score": baseline_mean,
            "diff": near_mean - baseline_mean,
        })
        rows.append(row)

    return pd.DataFrame(rows)


def _paired_ttest_greater(near: np.ndarray, baseline: np.ndarray):
    """One-sided paired t-test, alternative = near > baseline, matching
    thesis Sec 1.5 H1's directional statement ("a statistically
    significant *increase* in risk score ahead of the downgrade").
    Returns (t_stat, p_value) or (nan, nan) if fewer than 2 pairs."""
    if len(near) < 2:
        return float("nan"), float("nan")
    result = stats.ttest_rel(near, baseline, alternative="greater")
    return float(result.statistic), float(result.pvalue)


def summarize_lead_lag(events_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Returns (per_country_summary_df, pooled_summary_dict). Only
    status == "ok" events feed the t-test; every other status is counted
    but excluded, per-status, from both tables so nothing silently
    disappears."""
    status_counts = events_df["status"].value_counts().to_dict()
    ok = events_df[events_df["status"] == "ok"]

    per_country_rows = []
    for country, g in ok.groupby("country"):
        t_stat, p_value = _paired_ttest_greater(
            g["near_mean_risk_score"].values, g["baseline_mean_risk_score"].values
        )
        per_country_rows.append({
            "country": country,
            "n_events_tested": len(g),
            "n_events_single_sourced_ge_only": int(g["single_sourced_ge_only"].sum()),
            "mean_diff": g["diff"].mean(),
            "pct_events_with_increase": (g["diff"] > 0).mean() * 100,
            "t_stat": t_stat,
            "p_value_one_sided": p_value,
        })
    per_country_df = pd.DataFrame(per_country_rows).sort_values("country")

    t_stat, p_value = _paired_ttest_greater(
        ok["near_mean_risk_score"].values, ok["baseline_mean_risk_score"].values
    )
    pooled = {
        "n_events_tested": len(ok),
        "n_events_total": len(events_df),
        "status_counts": status_counts,
        "mean_diff": ok["diff"].mean() if len(ok) else float("nan"),
        "pct_events_with_increase": (ok["diff"] > 0).mean() * 100 if len(ok) else float("nan"),
        "t_stat": t_stat,
        "p_value_one_sided": p_value,
    }
    return per_country_df, pooled


def main():
    risk_labels = pd.read_parquet(RISK_LABELS_PATH)
    ratings_panel = pd.read_csv(RATINGS_PANEL_PATH, parse_dates=["date", "available_date"])

    pilot_countries_underscore = sorted(ratings_panel["country"].unique())
    print(f"Pilot countries (from ratings_panel.csv): {pilot_countries_underscore}")

    events = compute_lead_lag(risk_labels, ratings_panel)
    events_path = REPO_ROOT / "data" / "processed" / "stage1_leadlag_pilot_events.csv"
    events.to_csv(events_path, index=False)
    print(f"\nWrote {len(events)} event rows to {events_path}")
    print("\n=== Event status counts ===")
    print(events["status"].value_counts())

    print("\n=== Single-sourced (GE-only) coverage flags, by (country, agency) ===")
    ge_only = _ge_only_flag(ratings_panel)
    for (country, agency), flag in sorted(ge_only.items()):
        if flag:
            n = len(ratings_panel[(ratings_panel["country"] == country) & (ratings_panel["agency"] == agency)])
            print(f"  {country} / {agency}: 100% GE-only ({n} rows, no countryeconomy.com corroboration)")

    per_country, pooled = summarize_lead_lag(events)
    print("\n=== Per-country summary (status == 'ok' events only) ===")
    with pd.option_context("display.max_columns", None, "display.width", 160):
        print(per_country.to_string(index=False))

    print("\n=== Pooled summary (status == 'ok' events only, ALL 5 countries together) ===")
    for k, v in pooled.items():
        print(f"  {k}: {v}")
    print(
        "\nNOTE: pooled test pools non-independent events (see module docstring's "
        "'Events are not independent' limitation) -- read as a feasibility check, not "
        "a citable §5.1 result."
    )


if __name__ == "__main__":
    main()
