"""Return-construction diagnostics (2026-11-15) — the measurement pass
motivating the return rebuild, run after the status-audit added CLAUDE.md's
"Known open problems" section (local-currency series vs USD scope, no
benchmark-roll handling, missing coupon income).

Diagnostic only: writes exclusively to data/diagnostics/returns/, touches
nothing in data/processed/ or src/. Reuses src/stage2_signal/stage2_utils.py
helpers read-only (best_price_series, load_raw_bond_daily) so the "current
method" numbers reflect exactly what Stage 2 does today.

Parts (see data/diagnostics/returns/summary.md for the narrative):
  1  Roll detection: day-on-day MOD_DURTN jumps at 0.15/0.3/0.5y thresholds,
     split by sign (positive = roll candidate, negative = suspect data),
     with the same-day price change vs the normal daily move.
  2  Income gap: on the 5 YLDTOMAT countries, price-based quarterly return
     vs the yield-based approximation y/4 - D*dy + 0.5*C*dy^2
     (y = YLDTOMAT/100 converted exactly ONCE; dy = y_{t+1} - y_t on
     decimals, no second division).
  2b Chain-linked candidate fix: CLEAN_PRC (fallback MID_PRICE, never
     DIRTY_PRC — carry y/4 is added separately) daily chain with price
     return zeroed on roll-candidate days, run at both 0.15y and 0.3y
     zeroing thresholds, scored against the Part 2 yield-based return.
  3  Yield recovery: what the existing fields can/cannot recover for the
     39 YLDTOMAT-less countries, with the us_10y + ZSPREAD/100 proxy's
     error measured on the 5 countries where truth is known.
  4  Free monthly sources per country (10Y yield, local 3M rate, FX spot
     vs USD) — compiled table, no downloads; confidence flagged per cell.

Run: python3 diagnostics/returns_diagnostics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "stage2_signal"))

from stage2_utils import best_price_series, load_raw_bond_daily  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "diagnostics" / "returns"
BONDS_DIR = REPO_ROOT / "data" / "raw" / "bonds"
CORE_PARQUET = REPO_ROOT / "data" / "processed" / "stage1_feature_matrix_core.parquet"

THRESHOLDS = [0.15, 0.3, 0.5]
ROLL_THRESHOLD_MAIN = 0.3          # Part 2's roll-in-quarter split
CHAIN_THRESHOLDS = [0.15, 0.3]     # Part 2b run twice
SUSPECT_DURATION_BOUNDS = (0.0, 15.0)  # outside -> suspect data, not a roll
YLDTOMAT_COUNTRIES = ["Germany", "Japan", "Switzerland", "United_Kingdom", "United_States"]

# Expected benchmark issuance rhythm, where there is an obvious prior.
# (US: new 10Y note auctioned quarterly with reopenings -> ~4 genuinely new
# bonds/yr; DM G7 issuers broadly similar. Left blank where no clear prior.)
EXPECTED_ROLLS_PER_YEAR = {
    "United_States": "~4 (quarterly new 10Y note)",
    "Germany": "~2-4 (new Bund 2-4x/yr)",
    "United_Kingdom": "~2-4",
    "Japan": "~4 (quarterly JGB rhythm)",
    "France": "~2-4",
    "Italy": "~2-4",
}


def load_params():
    with open(REPO_ROOT / "configs" / "params.yaml") as f:
        return yaml.safe_load(f)


def rebal_grid(params) -> pd.DatetimeIndex:
    p = params["stage2_signal"]
    return pd.date_range(p["start_date"], p["end_date"], freq="QE")


# ---------------------------------------------------------------- Part 1

def detect_events(country: str, priority: list[str]):
    """Returns (events_df, summary_dict, roll_day_sets) for one country.
    roll_day_sets: {threshold: set of roll-candidate (positive) dates}."""
    raw = load_raw_bond_daily(country)
    if raw is None or "MOD_DURTN" not in raw.columns:
        return None, None, {t: set() for t in THRESHOLDS}

    md = raw["MOD_DURTN"].dropna()
    if len(md) < 2:
        return None, None, {t: set() for t in THRESHOLDS}
    diff = md.diff()
    gap_days = md.index.to_series().diff().dt.days

    price, price_field = best_price_series(raw, priority)
    price = price.dropna()
    price_ret = price.pct_change()
    median_abs_daily_ret = float(price_ret.abs().median())

    lo, hi = SUSPECT_DURATION_BOUNDS
    rows = []
    for date in diff.index[diff.abs() > min(THRESHOLDS)]:
        d = float(diff.loc[date])
        before = float(md.loc[:date].iloc[-2]) if len(md.loc[:date]) >= 2 else np.nan
        after = float(md.loc[date])
        suspect_values = not (lo < before <= hi and lo < after <= hi)
        rows.append({
            "country": country,
            "date": date,
            "durtn_before": before,
            "durtn_after": after,
            "diff_years": d,
            "abs_diff_bucket": (0.5 if abs(d) > 0.5 else 0.3 if abs(d) > 0.3 else 0.15),
            "event_class": ("suspect_data" if (d < 0 or suspect_values) else "roll_candidate"),
            "suspect_values": suspect_values,
            "gap_days_since_prev_obs": float(gap_days.loc[date]),
            "price_field": price_field,
            "same_day_price_ret_pct": (float(price_ret.loc[date]) * 100
                                        if date in price_ret.index and pd.notna(price_ret.loc[date])
                                        else np.nan),
        })
    events = pd.DataFrame(rows)

    roll_day_sets = {}
    for t in THRESHOLDS:
        if events.empty:
            roll_day_sets[t] = set()
        else:
            m = (events["event_class"] == "roll_candidate") & (events["diff_years"] > t)
            roll_day_sets[t] = set(events.loc[m, "date"])

    years = (md.index[-1] - md.index[0]).days / 365.25
    # quarter-end observation dates actually used by a QE-last resample
    q_last_dates = set(price.groupby(price.index.to_period("Q")).apply(lambda s: s.index[-1]))
    summary = {"country": country, "years_of_data": round(years, 1),
               "median_abs_daily_price_ret_pct": round(median_abs_daily_ret * 100, 4)}
    for t in THRESHOLDS:
        if events.empty:
            npos = nneg = 0
        else:
            npos = int(((events["diff_years"] > t) & (events["event_class"] == "roll_candidate")).sum())
            nneg = int(((events["diff_years"] < -t) | ((events["diff_years"] > t) & events["suspect_values"])).sum())
        summary[f"n_pos_gt_{t}"] = npos
        summary[f"n_neg_or_suspect_gt_{t}"] = nneg
    summary["roll_candidates_per_year_0.3"] = round(summary["n_pos_gt_0.3"] / years, 2) if years else np.nan
    summary["expected_rhythm"] = EXPECTED_ROLLS_PER_YEAR.get(country, "")
    main_rolls = roll_day_sets[ROLL_THRESHOLD_MAIN]
    if main_rolls:
        on_roll = price_ret.reindex(sorted(main_rolls)).abs().dropna()
        summary["median_abs_price_ret_on_roll_pct"] = round(float(on_roll.median()) * 100, 4) if len(on_roll) else np.nan
        summary["roll_vs_normal_ratio"] = (round(float(on_roll.median()) / median_abs_daily_ret, 1)
                                            if len(on_roll) and median_abs_daily_ret else np.nan)
        summary["n_rolls_on_quarter_end_obs"] = int(len(main_rolls & q_last_dates))
    else:
        summary["median_abs_price_ret_on_roll_pct"] = np.nan
        summary["roll_vs_normal_ratio"] = np.nan
        summary["n_rolls_on_quarter_end_obs"] = 0
    return events, summary, roll_day_sets


def part1(params):
    priority = params["stage2_signal"]["price_field_priority"]
    countries = sorted(p.stem for p in BONDS_DIR.glob("*.csv"))
    all_events, summaries, roll_sets = [], [], {}
    for c in countries:
        ev, summ, rolls = detect_events(c, priority)
        roll_sets[c] = rolls
        if ev is not None and len(ev):
            all_events.append(ev)
        if summ is not None:
            summaries.append(summ)
    events_df = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    summary_df = pd.DataFrame(summaries)
    events_df.to_csv(OUT_DIR / "roll_detection_events.csv", index=False)
    summary_df.to_csv(OUT_DIR / "roll_detection_summary.csv", index=False)
    print(f"[part1] {len(events_df)} events across {len(summary_df)} countries "
          f"-> roll_detection_{{events,summary}}.csv")
    return events_df, summary_df, roll_sets


# ---------------------------------------------------------------- Part 2

def quarterly_last_with_dates(series: pd.Series, grid: pd.DatetimeIndex):
    """(values on grid, actual last-observation date per grid quarter)."""
    s = series.dropna()
    if s.empty:
        return pd.Series(index=grid, dtype=float), pd.Series(index=grid, dtype="datetime64[ns]")
    vals = s.resample("QE").last().reindex(grid)
    dates = s.groupby(s.index.to_period("Q")).apply(lambda x: x.index[-1])
    dates.index = dates.index.to_timestamp("Q")
    dates = dates.reindex(grid)
    return vals, dates


def part2(params, roll_sets):
    grid = rebal_grid(params)
    priority = params["stage2_signal"]["price_field_priority"]
    rows, worked_examples = [], {}
    for c in YLDTOMAT_COUNTRIES:
        raw = load_raw_bond_daily(c)
        y_q, _ = quarterly_last_with_dates(raw["YLDTOMAT"] / 100.0, grid)  # decimal, converted ONCE
        d_q, _ = quarterly_last_with_dates(raw["MOD_DURTN"], grid)
        cx_q, _ = quarterly_last_with_dates(raw["CONVEXITY"], grid)
        field_q = {}
        for f in priority:
            if f == "synthetic_mid":
                if "BID" in raw.columns and "ASK" in raw.columns:
                    field_q[f] = quarterly_last_with_dates((raw["BID"] + raw["ASK"]) / 2, grid)[0]
                continue
            if f in raw.columns:
                field_q[f] = quarterly_last_with_dates(raw[f], grid)[0]
        rolls = roll_sets[c][ROLL_THRESHOLD_MAIN]
        for i in range(len(grid) - 1):
            t, t1 = grid[i], grid[i + 1]
            price_field, ret_price = "", np.nan
            for f, series in field_q.items():
                if pd.notna(series.loc[t]) and pd.notna(series.loc[t1]) and series.loc[t] != 0:
                    price_field = f
                    ret_price = float(series.loc[t1] / series.loc[t] - 1)
                    break
            y_t, y_t1 = y_q.loc[t], y_q.loc[t1]
            D, C = d_q.loc[t], cx_q.loc[t]
            if pd.notna(y_t) and pd.notna(y_t1) and pd.notna(D) and pd.notna(C):
                dy = float(y_t1 - y_t)  # difference of decimals, no second division
                carry_term = float(y_t) / 4
                duration_term = -float(D) * dy
                convexity_term = 0.5 * float(C) * dy ** 2
                ret_yield = carry_term + duration_term + convexity_term
            else:
                dy = carry_term = duration_term = convexity_term = ret_yield = np.nan
            roll_in_quarter = any(t < r <= t1 for r in rolls)
            row = {"country": c, "rebal_date": t, "next_date": t1,
                   "price_field_used": price_field, "ret_price": ret_price,
                   "y_t": y_t, "y_t1": y_t1, "dy": dy, "D_t": D, "C_t": C,
                   "carry_term": carry_term, "duration_term": duration_term,
                   "convexity_term": convexity_term, "ret_yield": ret_yield,
                   "gap": (ret_price - ret_yield
                            if pd.notna(ret_price) and pd.notna(ret_yield) else np.nan),
                   "roll_in_quarter": roll_in_quarter}
            rows.append(row)
            if c not in worked_examples and price_field == "DIRTY_PRC" and pd.notna(row["gap"]):
                worked_examples[c] = row
        if c not in worked_examples:  # fall back to any complete quarter
            for row in rows:
                if row["country"] == c and pd.notna(row["gap"]):
                    worked_examples[c] = row
                    break
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "income_gap_full_dm.csv", index=False)

    def stats(sub):
        g = sub["gap"].dropna()
        if g.empty:
            return {}
        both = sub.dropna(subset=["ret_price", "ret_yield"])
        return {"n": len(g), "mean_gap_pct": g.mean() * 100, "median_gap_pct": g.median() * 100,
                "std_gap_pct": g.std() * 100, "iqr_gap_pct": (g.quantile(0.75) - g.quantile(0.25)) * 100,
                "min_gap_pct": g.min() * 100, "max_gap_pct": g.max() * 100,
                "corr_price_vs_yield": both["ret_price"].corr(both["ret_yield"])}

    summary_rows = []
    for keys, sub in df.groupby(["country", "price_field_used", "roll_in_quarter"]):
        s = stats(sub)
        if s:
            summary_rows.append({"country": keys[0], "price_field_used": keys[1],
                                 "roll_in_quarter": keys[2], **s})
    for c, sub in df.groupby("country"):
        s = stats(sub)
        if s:
            summary_rows.append({"country": c, "price_field_used": "ALL",
                                 "roll_in_quarter": "ALL", **s})
    s = stats(df)
    summary_rows.append({"country": "POOLED", "price_field_used": "ALL", "roll_in_quarter": "ALL", **s})
    rf = df[~df["roll_in_quarter"]]
    s = stats(rf)
    summary_rows.append({"country": "POOLED_ROLL_FREE", "price_field_used": "ALL",
                         "roll_in_quarter": False, **s})
    summary = pd.DataFrame(summary_rows).round(4)
    summary.to_csv(OUT_DIR / "income_gap_summary.csv", index=False)
    print(f"[part2] {df['gap'].notna().sum()} gap quarters -> income_gap_full_dm.csv, income_gap_summary.csv")
    return df, summary, worked_examples


# --------------------------------------------------------------- Part 2b

def part2b(params, part2_df, roll_sets):
    grid = rebal_grid(params)
    rows = []
    for c in YLDTOMAT_COUNTRIES:
        raw = load_raw_bond_daily(c)
        # CLEAN_PRC preferred (income-free, matching the separately-added
        # carry), but only when it actually covers the sample: Germany's
        # CLEAN_PRC exists only ~2021-2025 (1,054/5,364 rows), which would
        # shrink the validation to ~17 quarters. Below 50% coverage fall
        # back to MID_PRICE (also income-free). Never DIRTY_PRC.
        clean_cov = raw["CLEAN_PRC"].notna().mean() if "CLEAN_PRC" in raw.columns else 0.0
        chain_field = "CLEAN_PRC" if clean_cov >= 0.5 else "MID_PRICE"
        price = raw[chain_field].dropna()
        r_daily = price.pct_change()
        y_q, _ = quarterly_last_with_dates(raw["YLDTOMAT"] / 100.0, grid)
        for thr in CHAIN_THRESHOLDS:
            r = r_daily.copy()
            zero_days = [d for d in roll_sets[c][thr] if d in r.index]
            r.loc[zero_days] = 0.0
            bucket = pd.Series(np.searchsorted(grid.values, r.index.values, side="left"), index=r.index)
            for i in range(len(grid) - 1):
                in_q = r[(bucket == i + 1)]
                if in_q.empty:
                    continue
                price_chain = float((1 + in_q.dropna()).prod() - 1)
                y_t = y_q.loc[grid[i]]
                if pd.isna(y_t):
                    continue
                rows.append({"country": c, "rebal_date": grid[i], "zero_threshold": thr,
                             "chain_field": chain_field, "n_days_zeroed": len([d for d in zero_days
                                                                               if grid[i] < d <= grid[i + 1]]),
                             "ret_chain": price_chain + float(y_t) / 4})
    chain = pd.DataFrame(rows)
    merged = chain.merge(
        part2_df[["country", "rebal_date", "ret_yield", "ret_price", "roll_in_quarter"]],
        on=["country", "rebal_date"], how="left")
    merged["err_chain"] = merged["ret_chain"] - merged["ret_yield"]
    merged["err_naive"] = merged["ret_price"] - merged["ret_yield"]
    merged.to_csv(OUT_DIR / "chainlinked_validation.csv", index=False)

    summary_rows = []
    for (c, thr), sub in merged.groupby(["country", "zero_threshold"]):
        e, en = sub["err_chain"].dropna(), sub["err_naive"].dropna()
        both = sub.dropna(subset=["ret_chain", "ret_yield"])
        summary_rows.append({
            "country": c, "zero_threshold": thr, "n": len(e),
            "chain_bias_pct": e.mean() * 100, "chain_mae_pct": e.abs().mean() * 100,
            "chain_corr_vs_yield": both["ret_chain"].corr(both["ret_yield"]),
            "naive_bias_pct": en.mean() * 100, "naive_mae_pct": en.abs().mean() * 100,
        })
    for thr, sub in merged.groupby("zero_threshold"):
        e, en = sub["err_chain"].dropna(), sub["err_naive"].dropna()
        both = sub.dropna(subset=["ret_chain", "ret_yield"])
        summary_rows.append({
            "country": "POOLED", "zero_threshold": thr, "n": len(e),
            "chain_bias_pct": e.mean() * 100, "chain_mae_pct": e.abs().mean() * 100,
            "chain_corr_vs_yield": both["ret_chain"].corr(both["ret_yield"]),
            "naive_bias_pct": en.mean() * 100, "naive_mae_pct": en.abs().mean() * 100,
        })
    summary = pd.DataFrame(summary_rows).round(4)
    summary.to_csv(OUT_DIR / "chainlinked_summary.csv", index=False)
    print(f"[part2b] {len(merged)} chain quarters -> chainlinked_{{validation,summary}}.csv")
    return merged, summary


# ---------------------------------------------------------------- Part 3

def part3(params):
    grid = rebal_grid(params)
    core = pd.read_parquet(CORE_PARQUET)
    us10 = core[["rebal_date", "us_10y"]].drop_duplicates().set_index("rebal_date")["us_10y"]

    cov_rows = []
    for p in sorted(BONDS_DIR.glob("*.csv")):
        raw = load_raw_bond_daily(p.stem)
        bs = raw["BMK_SPD"] if raw is not None and "BMK_SPD" in raw.columns else pd.Series(dtype=float)
        nn = bs.dropna()
        cov_rows.append({"country": p.stem, "bmk_spd_nonnull_pct": round(100 * len(nn) / len(raw), 1) if raw is not None and len(raw) else 0.0,
                         "bmk_spd_nonzero_pct_of_nonnull": round(100 * float((nn != 0).mean()), 1) if len(nn) else np.nan})
    cov = pd.DataFrame(cov_rows)

    err_rows = []
    for c in YLDTOMAT_COUNTRIES:
        raw = load_raw_bond_daily(c)
        y_true, _ = quarterly_last_with_dates(raw["YLDTOMAT"], grid)  # in %
        z_q, _ = quarterly_last_with_dates(raw["ZSPREAD"], grid)
        proxy = us10.reindex(grid) + z_q / 100.0  # % + bps/100 = %
        both = pd.DataFrame({"true": y_true, "proxy": proxy}).dropna()
        d_true, d_proxy = both["true"].diff().dropna(), both["proxy"].diff().dropna()
        err_rows.append({
            "country": c, "n_quarters": len(both),
            "bias_pct_pts": round(float((both["proxy"] - both["true"]).mean()), 3),
            "mae_pct_pts": round(float((both["proxy"] - both["true"]).abs().mean()), 3),
            "corr_levels": round(float(both["true"].corr(both["proxy"])), 3),
            "corr_quarterly_changes": round(float(d_true.corr(d_proxy)), 3),
        })
    err = pd.DataFrame(err_rows)
    cov.to_csv(OUT_DIR / "yield_recovery_bmk_spd_coverage.csv", index=False)
    err.to_csv(OUT_DIR / "yield_recovery_error.csv", index=False)
    print(f"[part3] proxy error on {len(err)} known-yield countries -> yield_recovery_{{bmk_spd_coverage,error}}.csv")
    return cov, err


# ---------------------------------------------------------------- Part 4
# Compiled from catalog knowledge, NO data downloaded. Confidence:
#   verified = series id pattern well-established for this country
#   likely   = catalog should cover it but id/history not individually confirmed
#   not found = no free monthly series believed to exist in FRED/OECD/IMF IFS
# basis column: period average (avg) vs end of period (eop).
# OECD MEI long-term yields (FRED IRLTLT01{ISO2}M156N) are monthly AVERAGES.
# IMF IFS government bond yields (FIGB_PA) / T-bill rates (FITB_PA) are
# period averages. FRED DEX FX series are daily noon buying rates.

OECD_10Y = {  # ISO2 for IRLTLT01{iso2}M156N, approx first date
    "Australia": ("AU", "1969"), "Austria": ("AT", "1990"), "Belgium": ("BE", "1960"),
    "Canada": ("CA", "1960"), "Chile": ("CL", "2004"), "Colombia": ("CO", "2003"),
    "Czech_Republic": ("CZ", "2000"), "Finland": ("FI", "1988"), "France": ("FR", "1960"),
    "Germany": ("DE", "1960"), "Greece": ("GR", "1997"), "Hungary": ("HU", "1999"),
    "Italy": ("IT", "1991"), "Japan": ("JP", "1989"), "Mexico": ("MX", "2001"),
    "Netherlands": ("NL", "1960"), "Norway": ("NO", "1985"), "Poland": ("PL", "2001"),
    "Portugal": ("PT", "1993"), "Spain": ("ES", "1980"), "Sweden": ("SE", "1986"),
    "Switzerland": ("CH", "1960"), "United_Kingdom": ("GB", "1960"), "United_States": ("US", "1954"),
}
# Non-OECD partners with an OECD/FRED long-term yield series (to confirm ids)
PARTNER_10Y_LIKELY = {"India": "2011", "Indonesia": "2000s", "South_Africa": "1960"}
IFS_10Y_LIKELY = {"China": "2000s", "Malaysia": "1990s", "Thailand": "1990s", "Philippines": "1990s"}
NO_FREE_10Y = ["Brazil", "Egypt", "Kazakhstan", "Kenya", "Morocco", "Nigeria",
               "Pakistan", "Peru", "Romania", "Sri_Lanka", "Turkey", "Vietnam", "Zambia"]
# ECB / national-central-bank fallbacks for the 13 countries with no free
# 10Y in FRED/OECD/IMF IFS (added 2026-11-15, task follow-up). Verified:
# Romania (ECB Data Portal convergence-purposes series
# IRS.M.RO.L.L40.CI.0000.RON.N.Z, monthly avg, lei, ~2005; EU-wide
# programme so it predates everything else available for RO) and Morocco
# (Bank Al-Maghrib "Taux de référence des bons du Trésor", secondary
# market, daily, downloadable by date at bkam.ma). The rest are
# knowledge-compiled `likely` entries -- national CB statistics portals
# known to publish government-securities yields; ids/history depth not
# individually confirmed without fetching.
CB_10Y_FALLBACK = {
    # country: (source, confidence, basis, first date approx)
    "Romania": ("ECB Data Portal IRS.M.RO.L.L40.CI.0000.RON.N.Z (convergence LTIR)",
                "verified", "avg", "2005"),
    "Morocco": ("Bank Al-Maghrib secondary-market Treasury reference rates (bkam.ma)",
                "verified", "eop (daily curve)", "2000s"),
    "Brazil": ("BCB SGS / ANBIMA secondary-market NTN-F 10Y yields", "likely", "eop (daily)", "~2007"),
    "Egypt": ("CBE T-bond auction cut-off yields (10Y auctions)", "likely", "auction dates", "2000s"),
    "Kazakhstan": ("KASE / NBK government securities yields", "likely (partial)", "", "2010s"),
    "Kenya": ("CBK Treasury bond auction + secondary yields", "likely", "auction dates", "2000s"),
    "Nigeria": ("CBN statistics / DMO FGN bond yields", "likely", "", "2000s"),
    "Pakistan": ("SBP PIB 10Y cut-off yields", "likely", "auction dates", "2000s"),
    "Peru": ("BCRP statistics (BCRPData) 10Y sovereign bond yield", "likely", "avg", "2000s"),
    "Sri_Lanka": ("CBSL Treasury bond yields", "likely", "", "2000s"),
    "Turkey": ("CBRT EVDS government securities yields", "likely", "", "~2010 (first 10Y TRY issue Jan 2010)"),
    "Vietnam": ("HNX bond market / SBV", "likely (partial)", "", "2010s"),
    "Zambia": ("BoZ government bond auction yields", "likely (partial)", "auction dates", "2010s"),
}
# Local 3M: FRED IR3TIB (3m interbank, OECD members) / IFS T-bill (FITB_PA)
IFS_TBILL_LIKELY = ["Brazil", "Egypt", "Kenya", "Malaysia", "Mexico", "Nigeria", "Pakistan",
                    "Philippines", "Peru", "Romania", "South_Africa", "Sri_Lanka", "Thailand",
                    "Turkey", "Zambia", "Kazakhstan", "Morocco", "Vietnam", "China", "India",
                    "Indonesia", "Colombia", "Chile", "Hungary", "Poland", "Czech_Republic", "Greece"]
FRED_DEX = {  # countries with a FRED daily DEX… USD pair (euro members -> DEXUSEU)
    "Australia": "DEXUSAL", "Brazil": "DEXBZUS", "Canada": "DEXCAUS", "China": "DEXCHUS",
    "India": "DEXINUS", "Japan": "DEXJPUS", "Malaysia": "DEXMAUS", "Mexico": "DEXMXUS",
    "Norway": "DEXNOUS", "South_Africa": "DEXSFUS", "Sweden": "DEXSDUS", "Switzerland": "DEXSZUS",
    "Thailand": "DEXTHUS", "United_Kingdom": "DEXUSUK", "Sri_Lanka": "DEXSLUS",
}
EURO_MEMBERS = ["Austria", "Belgium", "Finland", "France", "Germany", "Greece", "Italy",
                "Netherlands", "Portugal", "Spain"]


def part4():
    countries = sorted(p.stem for p in BONDS_DIR.glob("*.csv"))
    rows = []
    for c in countries:
        if c in OECD_10Y:
            iso2, first = OECD_10Y[c]
            y10 = (f"FRED IRLTLT01{iso2}M156N (OECD MEI)", "verified", "avg", first)
        elif c in PARTNER_10Y_LIKELY:
            y10 = ("FRED/OECD partner long-term yield series", "likely", "avg", PARTNER_10Y_LIKELY[c])
        elif c in IFS_10Y_LIKELY:
            y10 = ("IMF IFS govt bond yield (FIGB_PA)", "likely", "avg", IFS_10Y_LIKELY[c])
        else:
            y10 = ("none known in FRED/OECD/IMF IFS (check local CB / investing aggregators)",
                   "not found", "", "")
        cb = CB_10Y_FALLBACK.get(c, ("", "", "", ""))
        if c in OECD_10Y:
            iso2 = OECD_10Y[c][0]
            r3m = (f"FRED IR3TIB01{iso2}M156N (3m interbank) or IFS T-bill", "likely", "avg")
        elif c in IFS_TBILL_LIKELY:
            r3m = ("IMF IFS T-bill (FITB_PA) / money market (FIMM_PA)", "likely", "avg")
        else:
            r3m = ("IMF IFS money market or central bank policy rate (BIS)", "likely", "avg")
        if c == "United_States":
            fx = ("n/a (USD)", "verified")
        elif c in FRED_DEX:
            fx = (f"FRED {FRED_DEX[c]} (daily)", "verified")
        elif c in EURO_MEMBERS:
            fx = ("FRED DEXUSEU (EUR, daily)", "verified")
        else:
            fx = ("IMF IFS exchange rate (ENDA avg / ENDE eop)", "likely")
        rows.append({"country": c,
                     "yld10y_monthly_source": y10[0], "yld10y_confidence": y10[1],
                     "yld10y_basis": y10[2], "yld10y_first_date_approx": y10[3],
                     "yld10y_cb_fallback_source": cb[0], "yld10y_cb_fallback_confidence": cb[1],
                     "yld10y_cb_fallback_basis": cb[2], "yld10y_cb_fallback_first_date": cb[3],
                     "rate3m_local_source": r3m[0], "rate3m_confidence": r3m[1], "rate3m_basis": r3m[2],
                     "fx_spot_usd_source": fx[0], "fx_confidence": fx[1]})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "free_yield_sources.csv", index=False)
    n_nf = (df["yld10y_confidence"] == "not found").sum()
    print(f"[part4] 10Y coverage: {sum(df['yld10y_confidence']=='verified')} verified, "
          f"{sum(df['yld10y_confidence']=='likely')} likely, {n_nf} not found -> free_yield_sources.csv")
    return df


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    params = load_params()
    events, roll_summary, roll_sets = part1(params)
    gap_df, gap_summary, worked = part2(params, roll_sets)
    chain_df, chain_summary = part2b(params, gap_df, roll_sets)
    cov, err = part3(params)
    sources = part4()

    print("\n=== Part 1: top contamination ratios (0.3y roll-candidate day move vs normal day) ===")
    cols = ["country", "n_pos_gt_0.15", "n_pos_gt_0.3", "n_pos_gt_0.5",
            "n_neg_or_suspect_gt_0.3", "roll_candidates_per_year_0.3", "expected_rhythm",
            "roll_vs_normal_ratio", "n_rolls_on_quarter_end_obs"]
    print(roll_summary[cols].sort_values("roll_vs_normal_ratio", ascending=False).head(15).to_string(index=False))

    print("\n=== Part 2: worked quarter per country (units check) ===")
    for c, row in worked.items():
        print(f"  {c} {row['rebal_date'].date()} -> {row['next_date'].date()} [{row['price_field_used']}]: "
              f"y_t={row['y_t']:.6f} y_t1={row['y_t1']:.6f} dy={row['dy']:.6f} D={row['D_t']:.3f} C={row['C_t']:.2f}")
        print(f"      carry={row['carry_term']:.6f} duration={row['duration_term']:.6f} "
              f"convexity={row['convexity_term']:.8f} ret_yield={row['ret_yield']:.6f} "
              f"ret_price={row['ret_price']:.6f} gap={row['gap']:.6f}")

    print("\n=== Part 2: per-country and pooled summaries ===")
    print(gap_summary[gap_summary["price_field_used"] == "ALL"].to_string(index=False))
    print("\n=== Part 2: split by price field / roll-in-quarter ===")
    print(gap_summary[gap_summary["price_field_used"] != "ALL"].to_string(index=False))
    print("\n=== Part 2b: chain-linked vs naive error ===")
    print(chain_summary.to_string(index=False))
    print("\n=== Part 3: BMK_SPD coverage (worst 10) ===")
    print(cov.sort_values("bmk_spd_nonnull_pct").head(10).to_string(index=False))
    print("\n=== Part 3: us_10y + ZSPREAD/100 proxy vs true YLDTOMAT ===")
    print(err.to_string(index=False))


if __name__ == "__main__":
    main()
