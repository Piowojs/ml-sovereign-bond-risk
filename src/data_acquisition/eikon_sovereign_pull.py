"""
eikon_sovereign_pull.py
=======================
Pulls all Refinitiv Eikon data required for the sovereign bond thesis:
  - Bond prices, YTM, yield spread, duration, convexity
  - 5-year sovereign CDS spreads (USD)
  - Credit ratings history (S&P, Moody's, Fitch)

REQUIREMENTS
------------
  pip install eikon pandas numpy tqdm

Eikon desktop app must be open and logged in on the same machine.
Your app key is found in Eikon under: Help → Eikon API → Desktop API.

HOW TO RUN
----------
  1. Open Eikon on the university PC and log in.
  2. Open a terminal in the same session.
  3. Run:  python eikon_sovereign_pull.py
  4. If the session drops mid-run, re-run — already-saved files are skipped.

OUTPUT STRUCTURE
----------------
  data/
    raw/
      bonds/          ← one CSV per country (daily OHLCV + spread + duration)
      cds/            ← one CSV per country (daily CDS mid spread)
      ratings/        ← one CSV per agency per country (full rating history)
    logs/
      pull_log.txt    ← records successes and failures per country/series
      missing.txt     ← any gaps or errors flagged for manual follow-up

IMPORTANT NOTES
---------------
  - Raw files are NEVER overwritten once saved. Delete a file manually to re-pull it.
  - All dates are in YYYY-MM-DD format throughout.
  - CDS data for some smaller EM sovereigns may only start 2008+; gaps are logged.
  - Rating history uses a numeric mapping (see RATING_MAP below) for analysis.
  - Eikon limits: ~7,000 data points per request. Long time series are chunked
    automatically into 2-year windows and concatenated.
"""

import os
import time
import logging
import datetime
import traceback

import pandas as pd
import eikon as ek
from tqdm import tqdm

# ── CONFIGURATION ────────────────────────────────────────────────────────────

APP_KEY = "YOUR_APP_KEY_HERE"          # Replace with your key from Eikon Help → API

START_DATE = "2005-01-01"
END_DATE   = "2023-12-31"

OUTPUT_DIR = "data/raw"
LOG_DIR    = "data/logs"

# Chunk size for time-series pulls (Eikon limit: ~7000 points per request)
# 2-year windows at daily frequency = ~500 points — well within limits.
CHUNK_YEARS = 2

# Pause between API calls (seconds) — prevents rate-limit errors
API_PAUSE = 0.5

# ── SOVEREIGN UNIVERSE ───────────────────────────────────────────────────────
#
# RICs follow Refinitiv conventions. Bond RICs are benchmark on-the-run issues.
# CDS RICs use the format <ISO2><TENOR><CCY>=R for most sovereigns.
# Adjust any RIC that returns no data — use the Eikon search bar to verify.
#
# DM = Developed Markets  |  EM = Emerging Markets

UNIVERSE = {
    # ── DEVELOPED MARKETS ──────────────────────────────────────────────────
    # Country             Bond RIC (10y benchmark)    CDS RIC (5y USD)
    "United States":     ("US10YT=RR",               "US5YUSD=R"),
    "Germany":           ("DE10YT=RR",               "DE5YUSD=R"),
    "United Kingdom":    ("GB10YT=RR",               "GB5YUSD=R"),
    "Japan":             ("JP10YT=RR",               "JP5YUSD=R"),
    "France":            ("FR10YT=RR",               "FR5YUSD=R"),
    "Italy":             ("IT10YT=RR",               "IT5YUSD=R"),
    "Spain":             ("ES10YT=RR",               "ES5YUSD=R"),
    "Canada":            ("CA10YT=RR",               "CA5YUSD=R"),
    "Australia":         ("AU10YT=RR",               "AU5YUSD=R"),
    "Netherlands":       ("NL10YT=RR",               "NL5YUSD=R"),
    "Belgium":           ("BE10YT=RR",               "BE5YUSD=R"),
    "Sweden":            ("SE10YT=RR",               "SE5YUSD=R"),
    "Norway":            ("NO10YT=RR",               "NO5YUSD=R"),
    "Switzerland":       ("CH10YT=RR",               "CH5YUSD=R"),
    "Portugal":          ("PT10YT=RR",               "PT5YUSD=R"),
    "Greece":            ("GR10YT=RR",               "GR5YUSD=R"),
    "Austria":           ("AT10YT=RR",               "AT5YUSD=R"),
    "Finland":           ("FI10YT=RR",               "FI5YUSD=R"),

    # ── EMERGING MARKETS ───────────────────────────────────────────────────
    "Brazil":            ("BR10YT=RR",               "BR5YUSD=R"),
    "Mexico":            ("MX10YT=RR",               "MX5YUSD=R"),
    "Russia":            ("RU10YT=RR",               "RU5YUSD=R"),
    "South Africa":      ("ZA10YT=RR",               "ZA5YUSD=R"),
    "Turkey":            ("TR10YT=RR",               "TR5YUSD=R"),
    "Indonesia":         ("ID10YT=RR",               "ID5YUSD=R"),
    "India":             ("IN10YT=RR",               "IN5YUSD=R"),
    "China":             ("CN10YT=RR",               "CN5YUSD=R"),
    "Poland":            ("PL10YT=RR",               "PL5YUSD=R"),
    "Chile":             ("CL10YT=RR",               "CL5YUSD=R"),
    "Colombia":          ("CO10YT=RR",               "CO5YUSD=R"),
    "Peru":              ("PE10YT=RR",               "PE5YUSD=R"),
    "Hungary":           ("HU10YT=RR",               "HU5YUSD=R"),
    "Czech Republic":    ("CZ10YT=RR",               "CZ5YUSD=R"),
    "Romania":           ("RO10YT=RR",               "RO5YUSD=R"),
    "Malaysia":          ("MY10YT=RR",               "MY5YUSD=R"),
    "Thailand":          ("TH10YT=RR",               "TH5YUSD=R"),
    "Philippines":       ("PH10YT=RR",               "PH5YUSD=R"),
    "Argentina":         ("AR10YT=RR",               "AR5YUSD=R"),   # Include to default event
    "Ecuador":           ("EC10YT=RR",               "EC5YUSD=R"),   # Include to default event
    "Zambia":            ("ZM10YT=RR",               "ZM5YUSD=R"),   # Include to default event
    "Sri Lanka":         ("LK10YT=RR",               "LK5YUSD=R"),   # Include to default event
    "Egypt":             ("EG10YT=RR",               "EG5YUSD=R"),
    "Nigeria":           ("NG10YT=RR",               "NG5YUSD=R"),
    "Kenya":             ("KE10YT=RR",               "KE5YUSD=R"),
    "Ukraine":           ("UA10YT=RR",               "UA5YUSD=R"),
    "Kazakhstan":        ("KZ10YT=RR",               "KZ5YUSD=R"),
    "Qatar":             ("QA10YT=RR",               "QA5YUSD=R"),
    "Saudi Arabia":      ("SA10YT=RR",               "SA5YUSD=R"),
    "UAE":               ("AE10YT=RR",               "AE5YUSD=R"),
    "Morocco":           ("MA10YT=RR",               "MA5YUSD=R"),
    "Vietnam":           ("VN10YT=RR",               "VN5YUSD=R"),
    "Pakistan":          ("PK10YT=RR",               "PK5YUSD=R"),
    "Panama":            ("PA10YT=RR",               "PA5YUSD=R"),
    "Dominican Republic":("DO10YT=RR",               "DO5YUSD=R"),
}

# ── RATING NUMERIC MAP ───────────────────────────────────────────────────────
# Maps letter ratings → numeric scale (higher = worse credit quality).
# Moody's equivalents are mapped to the same numeric level as S&P for comparability.

RATING_MAP = {
    # S&P / Fitch       Moody's equivalent    Numeric
    "AAA":  1,          "Aaa":  1,
    "AA+":  2,          "Aa1":  2,
    "AA":   3,          "Aa2":  3,
    "AA-":  4,          "Aa3":  4,
    "A+":   5,          "A1":   5,
    "A":    6,          "A2":   6,
    "A-":   7,          "A3":   7,
    "BBB+": 8,          "Baa1": 8,
    "BBB":  9,          "Baa2": 9,
    "BBB-": 10,         "Baa3": 10,
    "BB+":  11,         "Ba1":  11,
    "BB":   12,         "Ba2":  12,
    "BB-":  13,         "Ba3":  13,
    "B+":   14,         "B1":   14,
    "B":    15,         "B2":   15,
    "B-":   16,         "B3":   16,
    "CCC+": 17,         "Caa1": 17,
    "CCC":  18,         "Caa2": 18,
    "CCC-": 19,         "Caa3": 19,
    "CC":   20,         "Ca":   20,
    "C":    21,         "C":    21,
    "D":    22,         "SD":   22,
    "SD":   22,         "RD":   22,
}

# ── SETUP ────────────────────────────────────────────────────────────────────

def setup_dirs_and_logging():
    """Create output directories and configure logging."""
    for d in [f"{OUTPUT_DIR}/bonds", f"{OUTPUT_DIR}/cds",
              f"{OUTPUT_DIR}/ratings", LOG_DIR]:
        os.makedirs(d, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.FileHandler(f"{LOG_DIR}/pull_log.txt"),
            logging.StreamHandler(),   # also prints to terminal
        ]
    )

def connect_eikon():
    """Connect to Eikon API. Raises clearly if Eikon is not open."""
    ek.set_app_key(APP_KEY)
    try:
        # Quick test call to verify connection
        ek.get_data("AAPL.O", ["TR.CompanyName"])
        logging.info("Eikon connection successful.")
    except Exception as e:
        logging.error(
            "Could not connect to Eikon. Make sure the Eikon desktop app "
            "is open and logged in on this machine."
        )
        raise

# ── DATE CHUNKING ────────────────────────────────────────────────────────────

def date_chunks(start: str, end: str, chunk_years: int = 2):
    """
    Yields (chunk_start, chunk_end) date string pairs.
    Splits the full range into windows to stay within Eikon's request limits.
    """
    s = datetime.date.fromisoformat(start)
    e = datetime.date.fromisoformat(end)
    while s < e:
        chunk_end = min(
            datetime.date(s.year + chunk_years, s.month, s.day) - datetime.timedelta(days=1),
            e
        )
        yield s.isoformat(), chunk_end.isoformat()
        s = chunk_end + datetime.timedelta(days=1)

# ── BOND DATA ────────────────────────────────────────────────────────────────

def pull_bond_data(country: str, ric: str):
    """
    Pulls daily time series for a benchmark bond:
      CLOSE  - clean price
      YIELD  - yield to maturity (%)
      YLDSPD - yield spread over US Treasury (bps)
      MDURATION - modified duration (years)
      CONVEXITY - convexity

    Saves to: data/raw/bonds/<country>.csv
    Skips if file already exists.
    """
    out_path = f"{OUTPUT_DIR}/bonds/{country.replace(' ', '_')}.csv"
    if os.path.exists(out_path):
        logging.info(f"[BONDS] {country} — already exists, skipping.")
        return

    logging.info(f"[BONDS] Pulling {country} ({ric}) ...")
    chunks = []

    for chunk_start, chunk_end in date_chunks(START_DATE, END_DATE, CHUNK_YEARS):
        try:
            df = ek.get_timeseries(
                ric,
                fields=["CLOSE", "YIELD", "YLDSPD", "MDURATION", "CONVEXITY"],
                start_date=chunk_start,
                end_date=chunk_end,
                interval="daily",
            )
            if df is not None and not df.empty:
                chunks.append(df)
            time.sleep(API_PAUSE)
        except Exception as e:
            logging.warning(f"[BONDS] {country} chunk {chunk_start}–{chunk_end}: {e}")
            _log_missing(country, "bond", chunk_start, chunk_end, str(e))

    if chunks:
        result = pd.concat(chunks)
        result.index.name = "date"
        result.columns = ["price", "ytm", "yield_spread_bps", "mod_duration", "convexity"]
        result["country"] = country
        result["ric"] = ric
        result.to_csv(out_path)
        logging.info(f"[BONDS] {country} — saved {len(result)} rows to {out_path}")
    else:
        logging.warning(f"[BONDS] {country} — no data returned. Check RIC: {ric}")
        _log_missing(country, "bond", START_DATE, END_DATE, "No data returned")

# ── CDS DATA ─────────────────────────────────────────────────────────────────

def pull_cds_data(country: str, ric: str):
    """
    Pulls daily 5-year USD CDS mid spread (bps).

    Saves to: data/raw/cds/<country>.csv
    Skips if file already exists.
    Note: many EM sovereigns only have CDS data from ~2008 onwards.
    """
    out_path = f"{OUTPUT_DIR}/cds/{country.replace(' ', '_')}.csv"
    if os.path.exists(out_path):
        logging.info(f"[CDS]   {country} — already exists, skipping.")
        return

    logging.info(f"[CDS]   Pulling {country} ({ric}) ...")
    chunks = []

    for chunk_start, chunk_end in date_chunks(START_DATE, END_DATE, CHUNK_YEARS):
        try:
            df = ek.get_timeseries(
                ric,
                fields=["CLOSE"],
                start_date=chunk_start,
                end_date=chunk_end,
                interval="daily",
            )
            if df is not None and not df.empty:
                chunks.append(df)
            time.sleep(API_PAUSE)
        except Exception as e:
            logging.warning(f"[CDS]   {country} chunk {chunk_start}–{chunk_end}: {e}")
            _log_missing(country, "cds", chunk_start, chunk_end, str(e))

    if chunks:
        result = pd.concat(chunks)
        result.index.name = "date"
        result.columns = ["cds_5y_usd_bps"]
        result["country"] = country
        result["ric"] = ric
        result.to_csv(out_path)
        logging.info(f"[CDS]   {country} — saved {len(result)} rows to {out_path}")
    else:
        logging.warning(f"[CDS]   {country} — no data returned. Check RIC: {ric}")
        _log_missing(country, "cds", START_DATE, END_DATE, "No data returned")

# ── RATINGS DATA ─────────────────────────────────────────────────────────────

# Eikon field codes for sovereign ratings history.
# These return the full action history (upgrades, downgrades, affirmations).
RATINGS_FIELDS = {
    "SP":    "TR.RatingSPLongTermFC",      # S&P foreign currency long-term
    "MOODYS":"TR.RatingMoodysLongTermFC",  # Moody's foreign currency long-term
    "FITCH": "TR.RatingFitchLongTermFC",   # Fitch foreign currency long-term
}

def pull_ratings_data(country: str, ric: str):
    """
    Pulls the full sovereign credit rating history from all three agencies.
    Uses the bond RIC as the identifier (ratings are issuer-level, not bond-level).

    Saves to: data/raw/ratings/<country>.csv
    Skips if file already exists.
    """
    out_path = f"{OUTPUT_DIR}/ratings/{country.replace(' ', '_')}.csv"
    if os.path.exists(out_path):
        logging.info(f"[RTGS]  {country} — already exists, skipping.")
        return

    logging.info(f"[RTGS]  Pulling {country} ratings ({ric}) ...")
    all_agency_dfs = []

    for agency, field in RATINGS_FIELDS.items():
        try:
            df, err = ek.get_data(
                ric,
                fields=[
                    field,
                    f"{field}.date",       # date of each rating action
                    f"{field}.action",     # upgrade / downgrade / affirm
                ],
                parameters={"SDate": START_DATE, "EDate": END_DATE}
            )
            if err:
                logging.warning(f"[RTGS]  {country} {agency} partial error: {err}")

            if df is not None and not df.empty:
                df.columns = ["instrument", "rating", "date", "action"]
                df["agency"]   = agency
                df["country"]  = country
                # Add numeric equivalent for quantitative analysis
                df["rating_numeric"] = df["rating"].map(RATING_MAP)
                all_agency_dfs.append(df)

            time.sleep(API_PAUSE)

        except Exception as e:
            logging.warning(f"[RTGS]  {country} {agency}: {e}")
            _log_missing(country, f"ratings_{agency}", START_DATE, END_DATE, str(e))

    if all_agency_dfs:
        result = pd.concat(all_agency_dfs, ignore_index=True)
        result = result.sort_values(["agency", "date"]).reset_index(drop=True)
        result.to_csv(out_path, index=False)
        logging.info(f"[RTGS]  {country} — saved {len(result)} rows to {out_path}")
    else:
        logging.warning(f"[RTGS]  {country} — no ratings data returned.")
        _log_missing(country, "ratings_all", START_DATE, END_DATE, "No data returned")

# ── MISSING DATA LOG ─────────────────────────────────────────────────────────

def _log_missing(country, data_type, start, end, reason):
    """Appends an entry to missing.txt for manual follow-up."""
    with open(f"{LOG_DIR}/missing.txt", "a") as f:
        f.write(f"{datetime.datetime.now().isoformat()}  |  {country}  |  "
                f"{data_type}  |  {start} to {end}  |  {reason}\n")

# ── VALIDATION ───────────────────────────────────────────────────────────────

def run_validation():
    """
    After all pulls, produces a summary of what was collected vs expected.
    Prints a coverage table so you can spot gaps before closing the session.
    """
    print("\n" + "="*60)
    print("COVERAGE SUMMARY")
    print("="*60)
    print(f"{'Country':<25} {'Bonds':>8} {'CDS':>8} {'Ratings':>10}")
    print("-"*60)

    for country in UNIVERSE:
        safe = country.replace(' ', '_')
        bond_rows = _count_rows(f"{OUTPUT_DIR}/bonds/{safe}.csv")
        cds_rows  = _count_rows(f"{OUTPUT_DIR}/cds/{safe}.csv")
        rtg_rows  = _count_rows(f"{OUTPUT_DIR}/ratings/{safe}.csv")
        print(f"{country:<25} {bond_rows:>8} {cds_rows:>8} {rtg_rows:>10}")

    print("="*60)
    print(f"Missing log: {LOG_DIR}/missing.txt")
    print(f"Full log:    {LOG_DIR}/pull_log.txt")

def _count_rows(path):
    """Returns row count of a CSV file, or 'MISSING' if it doesn't exist."""
    if not os.path.exists(path):
        return "MISSING"
    try:
        return len(pd.read_csv(path))
    except Exception:
        return "ERROR"

# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    setup_dirs_and_logging()
    logging.info("="*60)
    logging.info("Eikon sovereign data pull — starting")
    logging.info(f"Universe: {len(UNIVERSE)} countries | {START_DATE} to {END_DATE}")
    logging.info("="*60)

    connect_eikon()

    countries = list(UNIVERSE.items())

    # ── PULL BONDS ───────────────────────────────────────────────────────────
    print("\n--- BOND DATA ---")
    for country, (bond_ric, _) in tqdm(countries, desc="Bonds"):
        try:
            pull_bond_data(country, bond_ric)
        except Exception:
            logging.error(f"[BONDS] {country} — unexpected error:\n{traceback.format_exc()}")

    # ── PULL CDS ─────────────────────────────────────────────────────────────
    print("\n--- CDS DATA ---")
    for country, (_, cds_ric) in tqdm(countries, desc="CDS"):
        try:
            pull_cds_data(country, cds_ric)
        except Exception:
            logging.error(f"[CDS]   {country} — unexpected error:\n{traceback.format_exc()}")

    # ── PULL RATINGS ─────────────────────────────────────────────────────────
    print("\n--- RATINGS DATA ---")
    for country, (bond_ric, _) in tqdm(countries, desc="Ratings"):
        try:
            pull_ratings_data(country, bond_ric)
        except Exception:
            logging.error(f"[RTGS]  {country} — unexpected error:\n{traceback.format_exc()}")

    # ── VALIDATE ─────────────────────────────────────────────────────────────
    run_validation()
    logging.info("Pull complete. Review missing.txt for any gaps.")

if __name__ == "__main__":
    main()
