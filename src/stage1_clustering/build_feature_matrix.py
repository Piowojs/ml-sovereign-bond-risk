"""Build the Stage 1 country x quarter feature matrix (thesis Sec 4.2 input).

Produces two wide, country x quarter-end panels for the sovereign universe in
configs/universe.yaml:
  - data/processed/stage1_feature_matrix_core.parquet     (all 44 countries)
  - data/processed/stage1_feature_matrix_extended.parquet  (DM + duration/
    convexity-rich EM; adds mod_duration, convexity, cds_5y)

Market columns come from data/raw/bonds/*.csv, resampled to quarter-end using
the last observation in-quarter. Macro columns come from
data/raw/macro/macro_fundamentals.csv and are joined via a backward as-of
merge on available_date <= rebal_date -- never a plain date match -- so no
macro figure enters a quarter before it was actually publishable. See
CLAUDE.md for the full column mapping, the ZSPREAD-vs-BMK_SPD field choice,
and the duration/convexity-based extended-tier gating rationale.

Agency ratings are intentionally excluded from both tiers (they're a Stage 1
validation target, not a clustering input) and are not built here -- see
CLAUDE.md for the ratings-pull gap.
"""

import argparse
import logging
from pathlib import Path

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# output column name -> raw macro `series` value (World Bank primary, IMF WEO fallback)
WB_IMF_FEATURES = {
    "debt_gdp": "debt_to_gdp",
    "fiscal_bal_gdp": "fiscal_balance_to_gdp",
    "current_acct_gdp": "current_account_to_gdp",
    "fx_reserves_mo": "fx_reserves_months_imports",
    "cpi_inflation": "cpi_inflation_yoy",
    "real_gdp_growth": "real_gdp_growth_yoy",
    "political_stability": "political_stability",
}
# output column name -> (raw macro `series` value, `country` tag used for it in macro_fundamentals.csv)
GLOBAL_FEATURES = {
    "us_10y": ("us_10y_yield", "United States"),
    "us_2y": ("us_2y_yield", "United States"),
    "vix": ("vix", "GLOBAL"),
    "dxy_proxy": ("usd_index_broad_proxy", "GLOBAL"),
}

CORE_NUMERIC_COLUMNS = (
    ["yield_spread_bps"] + list(WB_IMF_FEATURES) + list(GLOBAL_FEATURES) + ["curve_slope"]
)
EXTENDED_ONLY_NUMERIC_COLUMNS = ["mod_duration", "convexity", "cds_5y"]

logger = logging.getLogger("stage1_feature_matrix")


def load_config():
    with open(REPO_ROOT / "configs" / "universe.yaml") as f:
        universe_cfg = yaml.safe_load(f)
    with open(REPO_ROOT / "configs" / "params.yaml") as f:
        params_cfg = yaml.safe_load(f)
    return universe_cfg["universe"], params_cfg["stage1_feature_matrix"]


def setup_logging(log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "stage1_feature_matrix_log.txt"),
            logging.StreamHandler(),
        ],
        force=True,
    )


def log_missing(log_dir: Path, country: str, item: str, reason: str):
    with open(log_dir / "stage1_feature_matrix_missing.txt", "a") as f:
        f.write(f"{pd.Timestamp.now().isoformat()} | {country} | {item} | {reason}\n")


def bond_file_path(country_name: str) -> Path:
    return REPO_ROOT / "data" / "raw" / "bonds" / f"{country_name.replace(' ', '_')}.csv"


def classify_coverage_tier(columns) -> str:
    """Which of the 4 raw bond-field-richness variants a country's file has.
    Metadata only -- separate from CORE/EXTENDED tier membership."""
    has_clean_dirty = "CLEAN_PRC" in columns and "DIRTY_PRC" in columns
    has_ytm = "YLDTOMAT" in columns
    has_mid = "MID_PRICE" in columns
    if has_clean_dirty and has_ytm:
        return "full_dm"
    if has_clean_dirty:
        return "dm_standard"
    if has_mid:
        return "em_standard"
    return "em_minimal"


def load_bond_quarterly(country_name: str, rebal_dates: pd.DatetimeIndex, log_dir: Path):
    """Returns (quarterly_df indexed by rebal_date, coverage_tier, dur_conv_coverage)."""
    path = bond_file_path(country_name)
    if not path.exists():
        log_missing(log_dir, country_name, "bonds", f"file not found: {path}")
        return None, "em_minimal", 0.0

    df = pd.read_csv(path, parse_dates=["date"])
    if df.empty:
        log_missing(log_dir, country_name, "bonds", "file exists but empty")
        return None, "em_minimal", 0.0

    coverage_tier = classify_coverage_tier(df.columns)
    dur_conv_coverage = float((df["MOD_DURTN"].notna() & df["CONVEXITY"].notna()).mean())

    df = df.set_index("date").sort_index()
    quarterly = df.resample("QE").last()
    quarterly = quarterly.reindex(rebal_dates)
    quarterly.index.name = "rebal_date"
    return quarterly, coverage_tier, dur_conv_coverage


def asof_join_country_series(macro_df: pd.DataFrame, country_name: str, raw_series: str,
                              rebal_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Backward as-of join of a single (country, series) macro time series onto
    the rebalancing-date grid. Returns a DataFrame indexed by rebal_date with
    columns `value`, `source`, `available_date` (the last two carried through
    so callers can build the source-tracking and leakage-diagnostic columns)."""
    sub = (
        macro_df[(macro_df["country"] == country_name) & (macro_df["series"] == raw_series)]
        [["available_date", "value", "source"]]
        .sort_values("available_date")
    )
    left = pd.DataFrame({"rebal_date": rebal_dates})
    merged = pd.merge_asof(
        left, sub, left_on="rebal_date", right_on="available_date", direction="backward"
    )
    return merged.set_index("rebal_date")


def build_global_series(macro_df: pd.DataFrame, raw_series: str, tag_country: str,
                         rebal_dates: pd.DatetimeIndex) -> pd.Series:
    sub = (
        macro_df[(macro_df["country"] == tag_country) & (macro_df["series"] == raw_series)]
        [["available_date", "value"]]
        .sort_values("available_date")
    )
    left = pd.DataFrame({"rebal_date": rebal_dates})
    merged = pd.merge_asof(
        left, sub, left_on="rebal_date", right_on="available_date", direction="backward"
    )
    return merged.set_index("rebal_date")["value"]


def build_country_panel(country: dict, macro_df: pd.DataFrame, global_series: dict,
                         rebal_dates: pd.DatetimeIndex, log_dir: Path) -> tuple[pd.DataFrame, str, float]:
    name = country["name"]
    bond_q, coverage_tier, dur_conv_coverage = load_bond_quarterly(name, rebal_dates, log_dir)

    out = pd.DataFrame(index=rebal_dates)
    out.index.name = "rebal_date"
    out["country_code"] = country["iso3"]
    out["country_name"] = name
    out["dm_em_flag"] = country["classification"]
    out["rebal_date"] = rebal_dates

    if bond_q is not None:
        out["yield_spread_bps"] = bond_q["ZSPREAD"]
        out["mod_duration"] = bond_q["MOD_DURTN"]
        out["convexity"] = bond_q["CONVEXITY"]
        out["cds_5y"] = bond_q["INT_CDS"]
    else:
        out["yield_spread_bps"] = float("nan")
        out["mod_duration"] = float("nan")
        out["convexity"] = float("nan")
        out["cds_5y"] = float("nan")

    avail_cols = []
    for out_col, raw_series in WB_IMF_FEATURES.items():
        joined = asof_join_country_series(macro_df, name, raw_series, rebal_dates)
        if joined["value"].isna().all():
            log_missing(log_dir, name, out_col, f"no as-of match for series '{raw_series}' at any rebal date")
        out[out_col] = joined["value"].values
        out[f"{out_col}_source"] = joined["source"].values
        avail_col = f"_avail_{out_col}"
        out[avail_col] = joined["available_date"].values
        avail_cols.append(avail_col)

    for out_col, (raw_series, tag_country) in GLOBAL_FEATURES.items():
        out[out_col] = global_series[out_col].reindex(rebal_dates).values

    out["curve_slope"] = out["us_10y"] - out["us_2y"]

    out["asof_max_available_date"] = out[avail_cols].max(axis=1, skipna=True)
    out["data_asof_ok"] = out["asof_max_available_date"].isna() | (
        out["asof_max_available_date"] <= out["rebal_date"]
    )
    out = out.drop(columns=avail_cols)
    out["coverage_tier"] = coverage_tier

    out = out.reset_index(drop=True)
    return out, coverage_tier, dur_conv_coverage


def compute_missing_flag(df: pd.DataFrame, numeric_columns: list) -> pd.Series:
    present = [c for c in numeric_columns if c in df.columns]
    return df[present].isna().any(axis=1)


def print_diagnostics(tier_name: str, df: pd.DataFrame, numeric_columns: list, n_dropped: int):
    print(f"\n=== {tier_name} tier diagnostics ===")
    print(f"Rows: {len(df)}")
    print(f"Countries: {df['country_code'].nunique()}")
    print(f"Rows dropped for data_asof_ok=False: {n_dropped}")
    print("Per-column missingness %:")
    cols = [c for c in numeric_columns if c in df.columns]
    miss_pct = (df[cols].isna().mean() * 100).round(1).sort_values(ascending=False)
    for col, pct in miss_pct.items():
        print(f"  {col:20s} {pct:5.1f}%")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    universe, params = load_config()
    output_dir = REPO_ROOT / params["output_dir"]
    log_dir = REPO_ROOT / "data" / "logs"
    setup_logging(log_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    macro_csv = REPO_ROOT / "data" / "raw" / "macro" / "macro_fundamentals.csv"
    macro_df = pd.read_csv(macro_csv, parse_dates=["period_date", "available_date"])

    rebal_dates = pd.date_range(start=params["start_date"], end=params["end_date"], freq="QE")
    logger.info("Building feature matrix for %d countries x %d quarters", len(universe), len(rebal_dates))

    global_series = {
        out_col: build_global_series(macro_df, raw_series, tag_country, rebal_dates)
        for out_col, (raw_series, tag_country) in GLOBAL_FEATURES.items()
    }

    panels = []
    dur_conv_coverage_by_country = {}
    for country in universe:
        panel, coverage_tier, dur_conv_coverage = build_country_panel(
            country, macro_df, global_series, rebal_dates, log_dir
        )
        panels.append(panel)
        dur_conv_coverage_by_country[country["name"]] = dur_conv_coverage
        logger.info(
            "%s: coverage_tier=%s dur/convexity coverage=%.1f%%",
            country["name"], coverage_tier, dur_conv_coverage * 100,
        )

    full = pd.concat(panels, ignore_index=True)

    min_cov = params["extended_tier_min_duration_convexity_coverage"]
    extended_countries = {
        c["name"]
        for c in universe
        if c["classification"] == "DM" or dur_conv_coverage_by_country[c["name"]] >= min_cov
    }
    excluded_em = {
        c["name"] for c in universe
        if c["classification"] == "EM" and c["name"] not in extended_countries
    }
    if excluded_em:
        logger.info(
            "Extended tier excludes %d EM countr(y/ies) below %.0f%% duration/convexity coverage: %s",
            len(excluded_em), min_cov * 100, sorted(excluded_em),
        )

    core_meta_cols = (
        ["country_code", "country_name", "dm_em_flag", "rebal_date"]
        + [f"{c}_source" for c in WB_IMF_FEATURES]
        + ["asof_max_available_date", "data_asof_ok", "missing_flag", "coverage_tier"]
    )

    # --- CORE tier: all 44 countries ---
    core_numeric = CORE_NUMERIC_COLUMNS
    core = full.copy()
    core["missing_flag"] = compute_missing_flag(core, core_numeric)
    n_dropped_core = int((~core["data_asof_ok"]).sum())
    if n_dropped_core:
        log_missing(log_dir, "ALL", "data_asof_ok", f"{n_dropped_core} core rows dropped (available_date > rebal_date)")
    core = core[core["data_asof_ok"]].reset_index(drop=True)
    core_cols = ["country_code", "country_name", "dm_em_flag", "rebal_date", "yield_spread_bps"]
    core_cols += list(WB_IMF_FEATURES) + list(GLOBAL_FEATURES) + ["curve_slope"]
    core_cols += [f"{c}_source" for c in WB_IMF_FEATURES]
    core_cols += ["asof_max_available_date", "data_asof_ok", "missing_flag", "coverage_tier"]
    core = core[core_cols]

    core_path = output_dir / "stage1_feature_matrix_core.parquet"
    core.to_parquet(core_path, index=False)
    logger.info("Wrote %d rows to %s", len(core), core_path)
    print_diagnostics("CORE", core, core_numeric, n_dropped_core)

    # --- EXTENDED tier: DM + duration/convexity-rich EM ---
    extended_numeric = CORE_NUMERIC_COLUMNS + EXTENDED_ONLY_NUMERIC_COLUMNS
    extended = full[full["country_name"].isin(extended_countries)].copy()
    extended["missing_flag"] = compute_missing_flag(extended, extended_numeric)
    n_dropped_extended = int((~extended["data_asof_ok"]).sum())
    if n_dropped_extended:
        log_missing(log_dir, "ALL", "data_asof_ok", f"{n_dropped_extended} extended rows dropped (available_date > rebal_date)")
    extended = extended[extended["data_asof_ok"]].reset_index(drop=True)
    extended_cols = ["country_code", "country_name", "dm_em_flag", "rebal_date"]
    extended_cols += ["yield_spread_bps", "mod_duration", "convexity", "cds_5y"]
    extended_cols += list(WB_IMF_FEATURES) + list(GLOBAL_FEATURES) + ["curve_slope"]
    extended_cols += [f"{c}_source" for c in WB_IMF_FEATURES]
    extended_cols += ["asof_max_available_date", "data_asof_ok", "missing_flag", "coverage_tier"]
    extended = extended[extended_cols]

    extended_path = output_dir / "stage1_feature_matrix_extended.parquet"
    extended.to_parquet(extended_path, index=False)
    logger.info("Wrote %d rows to %s", len(extended), extended_path)
    print_diagnostics("EXTENDED", extended, extended_numeric, n_dropped_extended)

    logger.info("Stage 1 feature matrix build complete.")


if __name__ == "__main__":
    main()
