"""Build the Stage 2 country x quarter signal panel (thesis Sec 4.3.2
target construction + Sec 3.3 Group A/B/C Stage-2-scoped features).

Population: (country, rebal_date) rows with dm_em_flag == "EM" and
risk_label == "satellite-candidate" in Stage 1's walk-forward output
(data/processed/stage1_risk_labels.parquet) -- see thesis Sec 4.4.1's
sleeve definition and stage2_utils.load_satellite_em_universe's docstring
for why the occasional DM row in satellite-candidate is excluded.

*** DATA GAP, CONFIRMED BEFORE BUILDING (see CLAUDE.md "Stage 2 signal")
    ***
No explicit coupon-rate/cashflow field exists anywhere in the raw bond
pull (11 fields total, confirmed against bond_data_pull_reconstructed.py's
own field list) -- the bond CSVs are generic benchmark composites
(XX10YT=RR RICs), not individual fixed-coupon issues with a cashflow
schedule. "Excess total return (price return + coupon)" per thesis
Sec 4.3.2 is therefore NOT constructible as a true coupon-inclusive total
return. What's built instead, and flagged per row rather than silently
presented as equivalent:
  - Where DIRTY_PRC (dirty price, embeds accrued interest) is available,
    its quarter-over-quarter return is the closest available proxy to
    total return -- accrued-interest accrual is a running approximation of
    coupon income, though it still misses the discrete coupon cash receipt
    itself. has_income_component=True for these rows.
  - Where only CLEAN_PRC, MID_PRICE, or a BID/ASK-derived synthetic mid is
    available, the return is a pure price-return proxy with NO income
    component at all -- has_income_component=False. This understates true
    total return, more severely for higher-coupon (typically higher-risk)
    EM sovereigns, a real and structural bias worth citing in thesis
    Appendix B alongside the ZSPREAD-vs-swap-curve caveat.
Also confirmed missing before this build: no 3-month US T-bill series was
pulled anywhere in the repo (needed for the "excess ... over the 3-month
US T-bill" risk-free leg). Closed by adding DGS3MO to macro_pull.py's
FRED_SERIES (key-free, same as every other FRED series) rather than
approximating it from us_10y/us_2y.

Writes: data/processed/stage2_signal_panel.parquet

Run directly: python3 src/stage2_signal/build_stage2_panel.py
"""

from __future__ import annotations

import logging

import pandas as pd

from stage2_utils import (
    STAGE1_CORE_PARQUET,
    STAGE2_PANEL_PARQUET,
    asof_lookback,
    best_price_series,
    load_params,
    load_raw_bond_daily,
    load_satellite_em_universe,
    load_us_3m_tbill,
    quarterly_last,
    rolling_zscore_asof,
)

logger = logging.getLogger("stage2_build_panel")


def build_country_price_panel(country_name: str, rebal_dates: pd.DatetimeIndex, params: dict):
    """Returns a DataFrame indexed by rebal_date with the price-derived
    columns for one country, or None if the country has no usable price
    data at all (logged, not silently dropped)."""
    raw = load_raw_bond_daily(country_name)
    if raw is None:
        logger.warning("%s: no raw bond file / empty file -- excluded from Stage 2 entirely", country_name)
        return None

    price_daily, price_field = best_price_series(raw, params["price_field_priority"])
    if not price_field:
        logger.warning(
            "%s: no usable price field (checked %s) -- excluded from Stage 2 entirely",
            country_name, params["price_field_priority"],
        )
        return None

    price_q = quarterly_last(price_daily, rebal_dates)
    zspread_daily = raw["ZSPREAD"] if "ZSPREAD" in raw.columns else pd.Series(dtype=float)
    cds_daily = raw["INT_CDS"] if "INT_CDS" in raw.columns else pd.Series(dtype=float)
    cds_q = quarterly_last(cds_daily, rebal_dates)

    lookbacks = params["momentum_lookback_days"]
    tolerance = params["momentum_asof_tolerance_days"]
    zwindow = params["spread_zscore_window_days"]

    out = pd.DataFrame(index=rebal_dates)
    out.index.name = "rebal_date"
    out["price"] = price_q
    out["price_field_used"] = price_field
    out["has_income_component"] = price_field == "DIRTY_PRC"
    out["cds_5y"] = cds_q

    for date in rebal_dates:
        cur = price_q.get(date)
        for feat_name, days in lookbacks.items():
            past = asof_lookback(price_daily, date, days, tolerance)
            out.loc[date, feat_name] = (cur / past - 1) if (pd.notna(cur) and pd.notna(past) and past != 0) else float("nan")
        out.loc[date, "spread_zscore_52w"] = rolling_zscore_asof(zspread_daily, date, zwindow)

    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    params = load_params()

    satellite = load_satellite_em_universe()
    rebal_dates = pd.date_range(start=params["start_date"], end=params["end_date"], freq="QE")

    core = pd.read_parquet(STAGE1_CORE_PARQUET)
    rf = load_us_3m_tbill(rebal_dates, params)

    countries = sorted(satellite["country_name"].unique())
    logger.info("Building Stage 2 panel for %d EM satellite-candidate countries, %d quarters",
                len(countries), len(rebal_dates))

    country_panels = {}
    excluded_countries = []
    for name in countries:
        panel = build_country_price_panel(name, rebal_dates, params)
        if panel is None:
            excluded_countries.append(name)
        else:
            country_panels[name] = panel

    if excluded_countries:
        logger.warning(
            "%d countr(y/ies) excluded from Stage 2 entirely for lack of any usable price "
            "data: %s", len(excluded_countries), excluded_countries,
        )

    rows = []
    for _, srow in satellite.iterrows():
        name = srow["country_name"]
        if name not in country_panels:
            continue
        date = srow["rebal_date"]
        panel = country_panels[name]
        if date not in panel.index:
            continue

        idx = list(rebal_dates).index(date)
        next_date = rebal_dates[idx + 1] if idx + 1 < len(rebal_dates) else None

        row = {
            "country_code": srow["country_code"],
            "country_name": name,
            "dm_em_flag": srow["dm_em_flag"],
            "rebal_date": date,
            "target_period_end": next_date,
        }
        prow = panel.loc[date]
        row["price_field_used"] = prow["price_field_used"]
        row["has_income_component"] = prow["has_income_component"]
        row["cds_5y"] = prow["cds_5y"]
        row["mom_1m"] = prow["mom_1m"]
        row["mom_3m"] = prow["mom_3m"]
        row["mom_12m"] = prow["mom_12m"]
        row["spread_zscore_52w"] = prow["spread_zscore_52w"]

        p_t = prow["price"]
        p_t1 = panel.loc[next_date, "price"] if next_date is not None and next_date in panel.index else float("nan")
        rf_t = rf.get(date)
        if pd.notna(p_t) and pd.notna(p_t1) and p_t != 0:
            total_return = p_t1 / p_t - 1
        else:
            total_return = float("nan")
        rf_quarterly = rf_t / 4 / 100 if pd.notna(rf_t) else float("nan")
        excess_return = total_return - rf_quarterly if pd.notna(total_return) and pd.notna(rf_quarterly) else float("nan")

        row["price_t"] = p_t
        row["price_t1"] = p_t1
        row["us_3m_tbill_yield_pct"] = rf_t
        row["rf_quarterly"] = rf_quarterly
        row["total_return_proxy"] = total_return
        row["excess_return"] = excess_return
        row["excess_return_binary"] = (excess_return > 0) if pd.notna(excess_return) else None
        row["target_realized"] = pd.notna(excess_return)

        rows.append(row)

    panel_df = pd.DataFrame(rows)

    core_cols = core[
        ["country_code", "rebal_date", "yield_spread_bps", "debt_gdp", "fiscal_bal_gdp",
         "cpi_inflation", "real_gdp_growth", "us_10y", "curve_slope", "vix", "dxy_proxy"]
    ]
    panel_df = panel_df.merge(core_cols, on=["country_code", "rebal_date"], how="left")

    panel_df["carry"] = (
        panel_df["us_10y"] + panel_df["yield_spread_bps"] / 100.0
    ) - panel_df["us_3m_tbill_yield_pct"]
    panel_df["cds_bond_basis"] = panel_df["cds_5y"] - panel_df["yield_spread_bps"]

    output_dir = STAGE2_PANEL_PARQUET.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    panel_df.to_parquet(STAGE2_PANEL_PARQUET, index=False)
    logger.info("Wrote %d rows to %s", len(panel_df), STAGE2_PANEL_PARQUET)

    print("\n=== Stage 2 panel diagnostics ===")
    print(f"Rows: {len(panel_df)}  Countries: {panel_df['country_name'].nunique()}  "
          f"Quarters: {panel_df['rebal_date'].nunique()}")
    print(f"Rows with realized target: {panel_df['target_realized'].sum()} / {len(panel_df)}")
    print("\nprice_field_used counts:")
    print(panel_df["price_field_used"].value_counts())
    print(f"\nhas_income_component=True: {panel_df['has_income_component'].sum()} / {len(panel_df)}")
    model_features = load_params()["model_features"]
    print("\nModel feature missingness %:")
    miss = (panel_df[model_features].isna().mean() * 100).round(1).sort_values(ascending=False)
    for col, pct in miss.items():
        print(f"  {col:20s} {pct:5.1f}%")
    print(f"\ncds_5y missingness (excluded from model_features): {panel_df['cds_5y'].isna().mean() * 100:.1f}%")
    print(f"cds_bond_basis missingness (excluded from model_features): "
          f"{panel_df['cds_bond_basis'].isna().mean() * 100:.1f}%")


if __name__ == "__main__":
    main()
