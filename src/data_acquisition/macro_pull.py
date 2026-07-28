"""Pull macro/fundamental (World Bank, IMF WEO) and global-macro (FRED)
data for the sovereign universe defined in configs/universe.yaml.

Re-runnable end to end with no manual steps and no API keys: World Bank,
the IMF DataMapper API, and FRED's public CSV endpoint are all key-free.
Raw responses are cached under data/raw/macro/_cache/ so re-runs don't
re-hit the APIs unless --refresh is passed.

Output: data/raw/macro/macro_fundamentals.csv (tidy long format) and
data/raw/macro/coverage_report.csv. See CLAUDE.md for indicator codes,
publication-lag assumptions, and known limitations (vintage/revision data,
central- vs general-government consolidation mismatch in fallback pairs).
"""

import argparse
import json
import logging
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# World Bank indicator = primary source. IMF WEO indicator (or None) = fallback.
WORLD_BANK_SERIES = {
    "debt_to_gdp": "GC.DOD.TOTL.GD.ZS",
    "fiscal_balance_to_gdp": "GC.BAL.CASH.GD.ZS",
    "current_account_to_gdp": "BN.CAB.XOKA.GD.ZS",
    "fx_reserves_months_imports": "FI.RES.TOTL.MO",
    "cpi_inflation_yoy": "FP.CPI.TOTL.ZG",
    "real_gdp_growth_yoy": "NY.GDP.MKTP.KD.ZG",
}
# Political stability lives in the separate WGI database (source=3), not the
# default WDI database (source=2) the other indicators above use.
WORLD_BANK_WGI_SERIES = {
    "political_stability": "GOV_WGI_PV.EST",
}
IMF_WEO_FALLBACK = {
    "debt_to_gdp": "GGXWDG_NGDP",
    "fiscal_balance_to_gdp": "GGXCNL_NGDP",
    "current_account_to_gdp": "BCA_NGDPD",
    "cpi_inflation_yoy": "PCPIPCH",
    "real_gdp_growth_yoy": "NGDP_RPCH",
    # fx_reserves_months_imports, political_stability: no IMF WEO equivalent.
}
# FRED series are global, not per-country. DTWEXBGS is a documented proxy
# for DXY (ICE's real DXY is proprietary and not on FRED).
FRED_SERIES = {
    "us_10y_yield": ("DGS10", "United States"),
    "us_2y_yield": ("DGS2", "United States"),
    "vix": ("VIXCLS", "GLOBAL"),
    "usd_index_broad_proxy": ("DTWEXBGS", "GLOBAL"),
}

WORLD_BANK_API = "https://api.worldbank.org/v2/country/{iso2}/indicator/{code}"
IMF_DATAMAPPER_API = "https://www.imf.org/external/datamapper/api/v1/{code}"
FRED_CSV_API = "https://fred.stlouisfed.org/graph/fredgraph.csv"

logger = logging.getLogger("macro_pull")


def load_config():
    with open(REPO_ROOT / "configs" / "universe.yaml") as f:
        universe_cfg = yaml.safe_load(f)
    with open(REPO_ROOT / "configs" / "params.yaml") as f:
        params_cfg = yaml.safe_load(f)
    return universe_cfg["universe"], params_cfg["macro_acquisition"]


def setup_logging(log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "macro_pull_log.txt"),
            logging.StreamHandler(),
        ],
    )


def log_missing(log_dir: Path, country: str, series: str, reason: str):
    with open(log_dir / "macro_missing.txt", "a") as f:
        f.write(f"{pd.Timestamp.now().isoformat()} | {country} | {series} | {reason}\n")


RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2


def _get_with_retry(url: str, params: dict) -> requests.Response:
    last_exc = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_exc = e
            if attempt < RETRY_ATTEMPTS:
                logger.info(
                    "Retrying %s (%s) after transient error [%d/%d]: %s",
                    url, params, attempt, RETRY_ATTEMPTS, e,
                )
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise last_exc


def _cached_get(url: str, params: dict, cache_path: Path, refresh: bool) -> dict | None:
    if cache_path.exists() and not refresh:
        with open(cache_path) as f:
            return json.load(f)
    try:
        resp = _get_with_retry(url, params)
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning("Request failed for %s (%s) after %d attempts: %s", url, params, RETRY_ATTEMPTS, e)
        return None
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(data, f)
    return data


def _cached_get_csv(url: str, params: dict, cache_path: Path, refresh: bool) -> pd.DataFrame | None:
    if cache_path.exists() and not refresh:
        return pd.read_csv(cache_path)
    try:
        resp = _get_with_retry(url, params)
    except requests.RequestException as e:
        logger.warning("Request failed for %s (%s) after %d attempts: %s", url, params, RETRY_ATTEMPTS, e)
        return None
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(resp.content)
    return pd.read_csv(cache_path)


def annual_available_date(year: int, lag_months: int) -> date:
    period_end = date(year, 12, 31)
    month = period_end.month + lag_months
    y, m = period_end.year, month
    while m > 12:
        m -= 12
        y += 1
    return date(y, m, 1)


def pull_world_bank(universe, params, cache_dir, log_dir, refresh) -> list[dict]:
    rows = []
    start_year = int(params["start_date"][:4])
    end_year = int(params["end_date"][:4])
    date_range = f"{start_year}:{end_year}"
    lag_months = params["lag_months_world_bank"]

    all_series = {**WORLD_BANK_SERIES, **WORLD_BANK_WGI_SERIES}
    wgi_names = set(WORLD_BANK_WGI_SERIES)

    for country in universe:
        for series_name, code in all_series.items():
            source_id = 3 if series_name in wgi_names else 2
            cache_path = cache_dir / "world_bank" / f"{country['iso2']}_{code}.json"
            data = _cached_get(
                WORLD_BANK_API.format(iso2=country["iso2"], code=code),
                params={"format": "json", "date": date_range, "per_page": 200, "source": source_id},
                cache_path=cache_path,
                refresh=refresh,
            )
            if not data or len(data) < 2 or not data[1]:
                log_missing(log_dir, country["name"], series_name, "no World Bank data returned")
                continue
            found_years = set()
            for obs in data[1]:
                if obs["value"] is None:
                    continue
                year = int(obs["date"])
                found_years.add(year)
                rows.append(
                    {
                        "country": country["name"],
                        "series": series_name,
                        "period_date": date(year, 12, 31),
                        "available_date": annual_available_date(year, lag_months),
                        "value": obs["value"],
                        "source": "world_bank",
                    }
                )
            missing_years = set(range(start_year, end_year + 1)) - found_years
            for year in sorted(missing_years):
                log_missing(log_dir, country["name"], series_name, f"no World Bank value for {year}")
    logger.info("World Bank pull complete: %d rows", len(rows))
    return rows


def pull_imf_weo(universe, params, cache_dir, log_dir, refresh) -> list[dict]:
    rows = []
    start_year = int(params["start_date"][:4])
    end_year = int(params["end_date"][:4])
    lag_months = params["lag_months_imf_weo"]
    iso3_lookup = {c["iso3"]: c["name"] for c in universe}

    for series_name, code in IMF_WEO_FALLBACK.items():
        cache_path = cache_dir / "imf_weo" / f"{code}.json"
        data = _cached_get(
            IMF_DATAMAPPER_API.format(code=code),
            params={},
            cache_path=cache_path,
            refresh=refresh,
        )
        if not data or "values" not in data or code not in data["values"]:
            for iso3, name in iso3_lookup.items():
                log_missing(log_dir, name, series_name, "IMF WEO indicator payload unavailable")
            continue
        indicator_values = data["values"][code]
        for iso3, name in iso3_lookup.items():
            country_values = indicator_values.get(iso3, {})
            for year_str, value in country_values.items():
                if not year_str.isdigit() or value is None:
                    continue
                year = int(year_str)
                if not (start_year <= year <= end_year):
                    continue
                rows.append(
                    {
                        "country": name,
                        "series": series_name,
                        "period_date": date(year, 12, 31),
                        "available_date": annual_available_date(year, lag_months),
                        "value": value,
                        "source": "imf_weo",
                    }
                )
    logger.info("IMF WEO pull complete: %d rows", len(rows))
    return rows


def pull_fred(params, cache_dir, log_dir, refresh) -> list[dict]:
    rows = []
    lag_days = params["lag_days_fred"]
    start_date = pd.Timestamp(params["start_date"])
    end_date = pd.Timestamp(params["end_date"])

    for series_name, (code, country) in FRED_SERIES.items():
        cache_path = cache_dir / "fred" / f"{code}.csv"
        df = _cached_get_csv(
            FRED_CSV_API,
            params={"id": code},
            cache_path=cache_path,
            refresh=refresh,
        )
        if df is None or df.empty:
            log_missing(log_dir, country, series_name, "no FRED data returned")
            continue
        df["observation_date"] = pd.to_datetime(df["observation_date"])
        df = df[(df["observation_date"] >= start_date) & (df["observation_date"] <= end_date)]
        df = df[df[code].apply(lambda v: isinstance(v, (int, float)))]
        for _, r in df.iterrows():
            period_date = r["observation_date"].date()
            rows.append(
                {
                    "country": country,
                    "series": series_name,
                    "period_date": period_date,
                    "available_date": period_date + pd.Timedelta(days=lag_days),
                    "value": r[code],
                    "source": "fred",
                }
            )
        # Flag the requested sample start if the series doesn't cover it
        # (e.g. DTWEXBGS only starts 2006-01-02, so 2005 is missing).
        if not df.empty and df["observation_date"].min() > start_date:
            log_missing(
                log_dir,
                country,
                series_name,
                f"series starts {df['observation_date'].min().date()}, "
                f"no data for requested start {start_date.date()}",
            )
    logger.info("FRED pull complete: %d rows", len(rows))
    return rows


def merge_with_fallback(wb_rows: list[dict], imf_rows: list[dict]) -> list[dict]:
    """For series with an IMF WEO fallback, fill (country, series, year) gaps
    left by World Bank with IMF WEO values. WB rows are kept as-is otherwise."""
    wb_keys = {(r["country"], r["series"], r["period_date"]) for r in wb_rows}
    merged = list(wb_rows)
    for r in imf_rows:
        key = (r["country"], r["series"], r["period_date"])
        if key not in wb_keys:
            merged.append(r)
    return merged


def build_coverage_report(rows: list[dict], universe, params) -> pd.DataFrame:
    start_year = int(params["start_date"][:4])
    end_year = int(params["end_date"][:4])
    n_expected_years = end_year - start_year + 1

    df = pd.DataFrame(rows)
    all_series = list(WORLD_BANK_SERIES) + list(WORLD_BANK_WGI_SERIES)
    all_countries = [c["name"] for c in universe]

    records = []
    for country in all_countries:
        for series in all_series:
            n_present = df[(df["country"] == country) & (df["series"] == series)].shape[0]
            records.append(
                {
                    "country": country,
                    "series": series,
                    "coverage_pct": round(n_present / n_expected_years, 3),
                }
            )
    # FRED series: coverage vs. trading/calendar days is not directly
    # comparable to annual series, so report presence/absence separately.
    for series_name, (_, country) in FRED_SERIES.items():
        n_present = df[(df["country"] == country) & (df["series"] == series_name)].shape[0]
        records.append(
            {
                "country": country,
                "series": series_name,
                "coverage_pct": 1.0 if n_present > 0 else 0.0,
            }
        )
    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Bypass cache and re-fetch from APIs")
    args = parser.parse_args()

    universe, params = load_config()
    output_dir = REPO_ROOT / params["output_dir"]
    cache_dir = REPO_ROOT / params["cache_dir"]
    log_dir = REPO_ROOT / "data" / "logs"

    setup_logging(log_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting macro pull for %d countries", len(universe))

    wb_rows = pull_world_bank(universe, params, cache_dir, log_dir, args.refresh)
    imf_rows = pull_imf_weo(universe, params, cache_dir, log_dir, args.refresh)
    fred_rows = pull_fred(params, cache_dir, log_dir, args.refresh)

    fundamentals_rows = merge_with_fallback(wb_rows, imf_rows)
    all_rows = fundamentals_rows + fred_rows

    out_df = pd.DataFrame(all_rows).sort_values(["country", "series", "period_date"])
    out_path = output_dir / "macro_fundamentals.csv"
    out_df.to_csv(out_path, index=False)
    logger.info("Wrote %d rows to %s", len(out_df), out_path)

    coverage_df = build_coverage_report(all_rows, universe, params)
    coverage_path = output_dir / "coverage_report.csv"
    coverage_df.to_csv(coverage_path, index=False)

    threshold = params["coverage_warning_threshold"]
    low_coverage = coverage_df[coverage_df["coverage_pct"] < threshold]
    logger.info(
        "Coverage report written to %s (%d/%d cells below %.0f%% coverage)",
        coverage_path,
        len(low_coverage),
        len(coverage_df),
        threshold * 100,
    )
    if not low_coverage.empty:
        logger.warning("Cells below %.0f%% coverage:", threshold * 100)
        for _, r in low_coverage.iterrows():
            logger.warning("  %s / %s: %.0f%%", r["country"], r["series"], r["coverage_pct"] * 100)

    logger.info("Macro pull complete.")


if __name__ == "__main__":
    main()
