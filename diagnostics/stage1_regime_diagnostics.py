"""Stage 1 regime-artifact diagnostics (2026-11-15) — measurement pass on
the residual global-feature regime artifact flagged in CLAUDE.md's "Known
open problems" (`core-eligible` empty 2009-2017) before any Stage 3 design
decision is made.

Diagnostic only: writes exclusively to data/diagnostics/stage1/, touches
nothing in data/processed/ or src/. Part 2 re-runs the *production* labeler
(`build_risk_labels.label_panel`, same code path, expanding window) on
candidate feature-set repairs and judges them on STRUCTURE ONLY — no
return, portfolio, or lead/lag outcome is computed for any variant, by
explicit scope decision.

Parts (see data/diagnostics/stage1/summary.md for the narrative):
  1  Size of the artifact: per-rebal-date label counts and cross-sectional
     median/min/max of risk_score from the stored production parquet;
     between-date vs within-date variance decomposition of the score;
     median-score-over-time plot.
  2  Candidate repairs, structure only. Three expanding-window re-runs of
     label_panel (kmeans/core/k=3, random_state from params, unchanged):
       (a) current CORE features (also asserts exact reproduction of the
           stored stage1_risk_labels.parquet — same code path check);
       (b) CORE without us_10y / curve_slope (drops the global features);
       (c) the 8 country features z-scored within each rebal date
           (cross-sectional, point-in-time safe: uses only the same-date
           cross-section), globals dropped. Raw yield_spread_bps is left
           intact so cluster_labels_to_risk_tiers still ranks tiers on
           raw spreads.
     Per variant: label counts per year, dates with zero core-eligible,
     label turnover between consecutive dates, ARI vs DM/EM (pooled and
     mean per-date), between-date variance share of the score, and the
     per-date sleeve-size distribution (min/p10/median for core-eligible
     and satellite-candidate, plus dates with <5 countries in either).
  3  H1 confound check on the 13-country pilot — EXPLORATORY, run after
     the pilot results were seen (unlike the pilot's two surviving
     pre-registrations). For each status=="ok" downgrade event: the
     country's own near-minus-baseline risk_score change (the pilot's
     `diff`) vs the same change in the cross-sectional median score of
     all other countries over the identical window dates, two ways:
       (i)  median of all other countries;
       (ii) median of other countries with no downgrade event of their
            own within +/-4 quarters (365 days) of the event date.
     Control-set caveat for (ii): only the 13 pilot countries have
     ratings history, so the other 31 are "event-free" by data absence,
     not by verified absence of downgrades.

Run: python3 diagnostics/stage1_regime_diagnostics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "stage1_clustering"))

from build_risk_labels import label_panel  # noqa: E402
from clustering_utils import (  # noqa: E402
    RISK_TIERS_LOW_TO_HIGH,
    feature_columns_for_tier,
    load_feature_matrix,
    load_params,
)
from ratings_leadlag_stub import compute_lead_lag  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "diagnostics" / "stage1"
RISK_LABELS_PATH = REPO_ROOT / "data" / "processed" / "stage1_risk_labels.parquet"
RATINGS_PANEL_PATH = REPO_ROOT / "data" / "processed" / "ratings_panel.csv"

GLOBAL_FEATURES = ["us_10y", "curve_slope"]
REAL_TIERS = set(RISK_TIERS_LOW_TO_HIGH)
SLEEVE_MIN = 5          # "fewer than 5 countries in either sleeve" threshold
CONTROL_WINDOW_DAYS = 365  # +/-4 quarters for Part 3's clean-control variant

# The pilot's 7 positive-direction countries (state.md, 13-country pilot
# re-run 2026-08-12: the "macro-fundamental/persistent deterioration"
# bucket — 4 clear p<0.05, 2 borderline, 1 positive short of significance).
POSITIVE_DIRECTION_COUNTRIES = [
    "Greece", "Portugal", "South Africa", "Spain", "Sri Lanka", "Colombia", "Italy",
]


# ---------------------------------------------------------------- shared

def variance_decomposition(df: pd.DataFrame, score_col: str = "risk_score",
                           date_col: str = "rebal_date") -> dict:
    """ANOVA-style split of score variance into between-date and
    within-date sums of squares (NaN scores dropped)."""
    d = df[[date_col, score_col]].dropna()
    grand = d[score_col].mean()
    by_date = d.groupby(date_col)[score_col]
    n_d = by_date.count()
    mean_d = by_date.mean()
    ss_between = float((n_d * (mean_d - grand) ** 2).sum())
    ss_within = float(((d[score_col] - d[date_col].map(mean_d)) ** 2).sum())
    ss_total = ss_between + ss_within
    return {
        "n_obs": int(len(d)),
        "n_dates": int(len(n_d)),
        "grand_mean": grand,
        "ss_between": ss_between,
        "ss_within": ss_within,
        "between_share": ss_between / ss_total if ss_total > 0 else np.nan,
        "within_share": ss_within / ss_total if ss_total > 0 else np.nan,
    }


# ---------------------------------------------------------------- part 1

def part1(rl: pd.DataFrame) -> None:
    counts = (
        rl.pivot_table(index="rebal_date", columns="risk_label", values="country_code",
                       aggfunc="count", fill_value=0)
        .reindex(columns=RISK_TIERS_LOW_TO_HIGH + ["insufficient_data"], fill_value=0)
    )
    disp = rl.groupby("rebal_date")["risk_score"].agg(
        score_median="median", score_min="min", score_max="max", n_scored="count"
    )
    by_date = counts.join(disp).reset_index()
    by_date.to_csv(OUT_DIR / "part1_by_date.csv", index=False)

    decomp = variance_decomposition(rl)
    pd.DataFrame([decomp]).to_csv(OUT_DIR / "part1_variance_decomposition.csv", index=False)

    labeled_mask = by_date[RISK_TIERS_LOW_TO_HIGH].sum(axis=1) > 0
    zero_core = by_date[(by_date["core-eligible"] == 0) & labeled_mask]["rebal_date"]
    n_labeled_dates = int(labeled_mask.sum())

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.fill_between(disp.index, disp["score_min"], disp["score_max"],
                    color="#2563EB", alpha=0.12, linewidth=0, label="cross-sectional min–max")
    ax.plot(disp.index, disp["score_median"], color="#2563EB", linewidth=2,
            label="cross-sectional median")
    if len(zero_core):
        ax.axvspan(zero_core.min(), zero_core.max(), color="#9CA3AF", alpha=0.15, zorder=0)
        y_text = float(disp["score_min"].min()) + 0.01
        ax.annotate("zero core-eligible quarters\n"
                    f"({zero_core.min():%Y-%m} – {zero_core.max():%Y-%m}, "
                    f"{len(zero_core)} of {n_labeled_dates} labeled dates)",
                    xy=(zero_core.min() + pd.Timedelta(days=120), y_text),
                    fontsize=8, color="#4B5563")
    ax.set_ylabel("risk_score (0 = low-risk centroid, 1 = high-risk)")
    ax.set_title("Stage 1 walk-forward risk score: cross-sectional median over time", fontsize=11)
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.7)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_part1_median_score.png", dpi=160)
    plt.close(fig)

    print("\n=== Part 1: regime-artifact size (stored production labels) ===")
    print(f"between-date share of risk_score variance: {decomp['between_share']:.3f} "
          f"(within-date: {decomp['within_share']:.3f}; n={decomp['n_obs']})")
    print(f"dates with zero core-eligible (among dates with any real label): "
          f"{len(zero_core)} of {(by_date[RISK_TIERS_LOW_TO_HIGH].sum(axis=1) > 0).sum()}"
          + (f" ({zero_core.min():%Y-%m} to {zero_core.max():%Y-%m})" if len(zero_core) else ""))


# ---------------------------------------------------------------- part 2

def variant_metrics(labels: pd.DataFrame, name: str) -> dict:
    real = labels[labels["risk_label"].isin(REAL_TIERS)].copy()

    counts_year = (
        labels.assign(year=labels["rebal_date"].dt.year)
        .pivot_table(index="year", columns="risk_label", values="country_code",
                     aggfunc="count", fill_value=0)
        .reindex(columns=RISK_TIERS_LOW_TO_HIGH + ["insufficient_data"], fill_value=0)
    )
    counts_year.to_csv(OUT_DIR / f"part2_label_counts_by_year_{name}.csv")

    per_date = (
        real.pivot_table(index="rebal_date", columns="risk_label", values="country_code",
                         aggfunc="count", fill_value=0)
        .reindex(columns=RISK_TIERS_LOW_TO_HIGH, fill_value=0)
    )
    labeled_dates = per_date[per_date.sum(axis=1) > 0]
    zero_core_dates = int((labeled_dates["core-eligible"] == 0).sum())

    core_n = labeled_dates["core-eligible"]
    sat_n = labeled_dates["satellite-candidate"]
    sleeve = {
        "core_min": int(core_n.min()), "core_p10": float(core_n.quantile(0.1)),
        "core_median": float(core_n.median()),
        "sat_min": int(sat_n.min()), "sat_p10": float(sat_n.quantile(0.1)),
        "sat_median": float(sat_n.median()),
        "n_dates_either_sleeve_lt5": int(((core_n < SLEEVE_MIN) | (sat_n < SLEEVE_MIN)).sum()),
    }

    # turnover: among countries real-labeled at both of two consecutive dates
    dates = sorted(labeled_dates.index)
    turnovers = []
    lbl = real.set_index(["rebal_date", "country_code"])["risk_label"]
    for prev, cur in zip(dates[:-1], dates[1:]):
        a, b = lbl.loc[prev], lbl.loc[cur]
        common = a.index.intersection(b.index)
        if len(common):
            turnovers.append((a.loc[common] != b.loc[common]).mean())
    mean_turnover = float(np.mean(turnovers)) if turnovers else np.nan

    ari_pooled = adjusted_rand_score(real["dm_em_flag"], real["risk_label"])
    per_date_aris = []
    for _, g in real.groupby("rebal_date"):
        if len(g) >= 2:
            per_date_aris.append(adjusted_rand_score(g["dm_em_flag"], g["risk_label"]))
    ari_per_date_mean = float(np.mean(per_date_aris)) if per_date_aris else np.nan

    decomp = variance_decomposition(labels)

    return {
        "variant": name,
        "n_rows": len(labels),
        "n_real_labeled": len(real),
        "n_labeled_dates": len(labeled_dates),
        "n_dates_zero_core_eligible": zero_core_dates,
        **sleeve,
        "mean_label_turnover": mean_turnover,
        "ari_dmem_pooled": ari_pooled,
        "ari_dmem_mean_per_date": ari_per_date_mean,
        "risk_score_between_date_share": decomp["between_share"],
    }


def part2(rl_stored: pd.DataFrame) -> None:
    params = load_params()
    tier, algorithm, k, seed = "core", params["chosen_algorithm"], params["chosen_k"], params["random_state"]
    df = load_feature_matrix(tier)
    core_feats = feature_columns_for_tier(tier, params)
    country_feats = [f for f in core_feats if f not in GLOBAL_FEATURES]

    print("\n=== Part 2: candidate repairs (structure only; no outcomes computed) ===")
    rows = []

    # (a) current CORE features — must reproduce the stored parquet exactly
    labels_a = label_panel(df, core_feats, params, algorithm, k, seed, tier)
    stored = rl_stored.sort_values(["rebal_date", "country_code"]).reset_index(drop=True)
    rerun = labels_a.sort_values(["rebal_date", "country_code"]).reset_index(drop=True)
    assert (stored["risk_label"].values == rerun["risk_label"].values).all(), \
        "variant (a) failed to reproduce stored stage1_risk_labels.parquet labels"
    assert np.isclose(stored["risk_score"].values, rerun["risk_score"].values,
                      equal_nan=True).all(), \
        "variant (a) failed to reproduce stored risk_score values"
    print("variant (a): exact reproduction of stored parquet confirmed")
    rows.append(variant_metrics(labels_a, "a_current_core"))

    # (b) drop the global features
    labels_b = label_panel(df, country_feats, params, algorithm, k, seed, tier)
    rows.append(variant_metrics(labels_b, "b_no_global_features"))

    # (c) country features z-scored within each rebal date, globals dropped.
    # Point-in-time safe: each date's z-scores use only that date's own
    # cross-section. Raw yield_spread_bps stays untouched for tier ranking.
    df_c = df.copy()
    cs_cols = []
    for f in country_feats:
        g = df_c.groupby("rebal_date")[f]
        sd = g.transform("std")
        df_c[f"cs_z_{f}"] = (df_c[f] - g.transform("mean")) / sd.where(sd > 0)
        cs_cols.append(f"cs_z_{f}")
    labels_c = label_panel(df_c, cs_cols, params, algorithm, k, seed, tier)
    rows.append(variant_metrics(labels_c, "c_crosssectional_z"))

    comparison = pd.DataFrame(rows)
    comparison.to_csv(OUT_DIR / "part2_variant_comparison.csv", index=False)
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(comparison.round(3).to_string(index=False))


# ---------------------------------------------------------------- part 3

def part3(rl: pd.DataFrame) -> None:
    print("\n=== Part 3: H1 confound check (EXPLORATORY — run after pilot results were seen) ===")
    ratings = pd.read_csv(RATINGS_PANEL_PATH, parse_dates=["date", "available_date"])
    events = compute_lead_lag(rl, ratings)
    ok = events[events["status"] == "ok"].reset_index(drop=True)

    rl_sorted = rl.sort_values(["country_name", "rebal_date"])
    score_by_date = {d: g.set_index("country_name")["risk_score"]
                     for d, g in rl.groupby("rebal_date")}

    downgrades = ratings[ratings["action"] == "downgrade"].copy()
    downgrades["country_name"] = downgrades["country"].str.replace("_", " ")
    dg_dates_by_country = downgrades.groupby("country_name")["date"].apply(list).to_dict()

    def market_median(dates, exclude: set) -> float:
        meds = []
        for d in dates:
            s = score_by_date[d].drop(labels=[c for c in exclude if c in score_by_date[d].index])
            meds.append(s.dropna().median())
        return float(np.nanmean(meds))

    rows = []
    for _, ev in ok.iterrows():
        country, ev_date = ev["country"], pd.Timestamp(ev["downgrade_date"])
        cs = rl_sorted[rl_sorted["country_name"] == country]
        preceding = cs[cs["rebal_date"] < ev_date]
        near = preceding.tail(4)
        baseline = preceding.iloc[: len(preceding) - len(near)].tail(4)
        near_dates, base_dates = list(near["rebal_date"]), list(baseline["rebal_date"])

        own_diff = float(near["risk_score"].dropna().mean()
                         - baseline["risk_score"].dropna().mean())
        assert np.isclose(own_diff, ev["diff"]), \
            f"window replication mismatch for {country} {ev_date:%Y-%m-%d}"

        # (i) all other countries
        mkt_i = (market_median(near_dates, {country})
                 - market_median(base_dates, {country}))
        # (ii) exclude countries with their own downgrade within +/-365d
        contaminated = {
            c for c, ds in dg_dates_by_country.items()
            if c != country and any(abs((d - ev_date).days) <= CONTROL_WINDOW_DAYS for d in ds)
        }
        excl = contaminated | {country}
        mkt_ii = (market_median(near_dates, excl) - market_median(base_dates, excl))

        rows.append({
            "country": country, "agency": ev["agency"], "downgrade_date": ev_date,
            "own_diff": own_diff,
            "market_diff_all_others": mkt_i,
            "market_diff_clean_controls": mkt_ii,
            "abnormal_diff_all_others": own_diff - mkt_i,
            "abnormal_diff_clean_controls": own_diff - mkt_ii,
            "n_contaminated_excluded": len(contaminated),
        })

    ev_df = pd.DataFrame(rows)
    ev_df.to_csv(OUT_DIR / "part3_confound_events.csv", index=False)

    by_country = ev_df.groupby("country").agg(
        n_events=("own_diff", "size"),
        mean_own_diff=("own_diff", "mean"),
        mean_market_diff_all=("market_diff_all_others", "mean"),
        mean_abnormal_all=("abnormal_diff_all_others", "mean"),
        pct_abnormal_all_pos=("abnormal_diff_all_others", lambda s: (s > 0).mean() * 100),
        mean_market_diff_clean=("market_diff_clean_controls", "mean"),
        mean_abnormal_clean=("abnormal_diff_clean_controls", "mean"),
        pct_abnormal_clean_pos=("abnormal_diff_clean_controls", lambda s: (s > 0).mean() * 100),
    ).reset_index()
    by_country["pilot_positive_direction"] = by_country["country"].isin(POSITIVE_DIRECTION_COUNTRIES)
    by_country["sign_flips_all"] = (np.sign(by_country["mean_own_diff"])
                                    != np.sign(by_country["mean_abnormal_all"]))
    by_country["sign_flips_clean"] = (np.sign(by_country["mean_own_diff"])
                                      != np.sign(by_country["mean_abnormal_clean"]))
    by_country.to_csv(OUT_DIR / "part3_confound_by_country.csv", index=False)

    years = ev_df["downgrade_date"].dt.year.value_counts().sort_index()
    years.rename("n_ok_events").to_csv(OUT_DIR / "part3_event_counts_by_year.csv")

    pos = by_country[by_country["pilot_positive_direction"]]
    stay_all = int((pos["mean_abnormal_all"] > 0).sum())
    stay_clean = int((pos["mean_abnormal_clean"] > 0).sum())
    with pd.option_context("display.max_columns", None, "display.width", 220):
        print(by_country.round(3).to_string(index=False))
    print(f"\nOf the 7 positive-direction pilot countries, mean ABNORMAL diff stays "
          f"positive for {stay_all}/7 (vs all-others median) and {stay_clean}/7 "
          f"(vs clean controls, no downgrade within +/-{CONTROL_WINDOW_DAYS}d).")
    print(f"ok events: {len(ev_df)}; event counts by year written to "
          f"part3_event_counts_by_year.csv (top: {years.idxmax()} with {years.max()})")
    print("Caveat: 31 of 44 universe countries have no transcribed ratings, so the "
          "clean-control screen can only remove known-event countries among the 13.")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rl = pd.read_parquet(RISK_LABELS_PATH)
    part1(rl)
    part2(rl)
    part3(rl)
    print(f"\nAll outputs in {OUT_DIR}")


if __name__ == "__main__":
    main()
