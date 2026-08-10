"""
bond_data_pull_reconstructed.py  [v4 — final consolidated]
============================================================
Pulls Refinitiv Workspace bond analytics for the sovereign bond thesis.
This is the canonical single-file version produced by consolidating all
incremental fixes applied during development. See CHANGELOG at the bottom.

*** PROVENANCE / HONESTY NOTE — READ BEFORE TRUSTING THIS FILE ***
--------------------------------------------------------------------
This is a BEST-EFFORT RECONSTRUCTION, not a recovery of the original
script. The original pull was actually run as `data_pull.py` from
`C:\\Users\\Bloomberg\\Desktop\\DANE UŻYTKOWNIKÓW\\auto_download\\` on a
university-library Windows PC (per `data/logs/pull_log.txt`'s 2026-06-08
traceback); that file itself was never recovered. This file was rebuilt
in a separate conversation from a design-level trace of the incremental
fixes applied during that script's development (see CHANGELOG below) —
it is not a byte-for-byte or even line-for-line recovery.

Verification performed (2026-08-10, this environment): STRUCTURAL ONLY.
  - BOND_FIELDS (11 fields) was diffed against the union of columns
    actually present across every file in data/raw/bonds/ (44 CSVs):
    exact match, no extra or missing fields either direction.
  - Per-country column-presence pattern matches the 4 coverage tiers
    build_feature_matrix.py already infers from these files (full_dm /
    dm_standard / em_standard / em_minimal) — confirmed on one DM example
    (United_States/Germany/Japan/Switzerland/United_Kingdom.csv, 11 cols
    incl. YLDTOMAT) and one EM example (Poland.csv, 8 cols, no
    CLEAN_PRC/DIRTY_PRC/YLDTOMAT). The "save whatever subset the API
    returns, never hardcode" logic in pull_bond_data() below is
    consistent with that observed variability.
  - CHANGELOG v3's "removed hardcoded column renaming" fix independently
    matches the actual crash seen in pull_log.txt (a hardcoded 5-name
    `result.columns = [...]` assignment failing because the real frame
    had a different column count) — corroborating evidence the traced
    fix history is genuine, not fabricated after the fact.
  - CORRECTED (2026-08-10, full 44-country coverage check): YLDTOMAT is
    present only for the 5 countries in the full_dm coverage tier —
    Germany, Japan, Switzerland, United Kingdom, United States —
    populated at 98.5–100%. It is absent (not sparse — the column itself
    does not exist) for all other 39 countries, including unambiguous DM
    sovereigns such as Australia, Canada, France, and Italy. This is not
    a DM-vs-EM split; it is a licence/entitlement boundary that happens
    to coincide with the pre-existing full_dm tier definition. The
    previously documented claim that YLDTOMAT is "US-only" was incorrect
    and is superseded by this finding. Downstream code must continue to
    check column presence per country rather than assuming YLDTOMAT
    availability from DM/EM status alone.
  - NOT verified: this file has not been executed. Field availability,
    rate limits, chunking behaviour, and the RDP/EDP transport itself are
    unconfirmed by execution — only the call shape (`ld.open_session` +
    `ld.get_history(universe=, fields=, start=, end=, interval="daily")`)
    is consistent with the `localhost:9000/api/rdp/data/historical-pricing/
    v1/views/interday-summaries/...` pattern seen in pull_log.txt; this is
    a shape check, not proof.
  - UNRESOLVED GAP (accepted, same tier as the vintage/revision-data and
    WB/IMF consolidation-mismatch caveats already documented in
    CLAUDE.md): the `auto_download` wrapper context the original script
    ran inside on the Windows machine (scheduling, retry/session-refresh
    behaviour, any pre/post-processing outside this file) is unknown and
    cannot be reconstructed from pull_log.txt alone.
  - Live execution-level verification requires Refinitiv Workspace /
    lseg-data, available only on the university library PC — it cannot
    be performed from this environment. Do not attempt to run this file
    here; schedule that check for the next library session.


WHAT THIS SCRIPT PULLS
-----------------------
BONDS  →  data/raw/bonds/<Country_Name>.csv
  Daily time series via ld.get_history() on XX10YT=RR benchmark RICs.
  Fields requested (11 total):
    MID_PRICE   — mid price
    BID         — bid price
    ASK         — ask price
    YLDTOMAT    — yield to maturity (full_dm tier only — DE/JP/CH/UK/US,
                  98.5–100% populated; column absent for all other 39
                  countries; not a DM-vs-EM split, see honesty note above)
    BMK_SPD     — benchmark spread (bps vs local benchmark, not vs UST)
    MOD_DURTN   — modified duration (years)
    CONVEXITY   — convexity
    CLEAN_PRC   — clean price
    DIRTY_PRC   — dirty price (with accrued interest)
    ZSPREAD     — Z-spread (bps vs OIS swap curve)
    INT_CDS     — CDS-implied spread (bps); proxy for 5Y sovereign CDS
  The script saves whatever subset the API returns per country.
  Column presence varies: DM gets 8–11 columns, EM gets 8–10 columns.
  Do NOT hardcode column names downstream — always check presence first.

RATINGS  →  data/raw/ratings/<Country_Name>.csv
  *** KNOWN LIMITATION — READ BEFORE RUNNING ***
  TR.IssuerRating was confirmed to return only a current-snapshot NaN
  for all 44 countries under this university licence (SDate/EDate params
  silently ignored). The ratings pull function is retained for
  documentation purposes but will produce empty placeholder files.
  ACTION REQUIRED: Download rating histories directly from agencies:
    S&P:    spglobal.com/ratings → Research → Sovereign Rating History
    Moody's: moodys.com → Research → Sovereign → Rating History
    Fitch:  fitchratings.com → Research → Sovereigns → Rating History

CONFIRMED LICENCE LIMITATIONS
------------------------------
  YLDTOMAT    — available only for the full_dm tier (DE/JP/CH/UK/US);
                column absent (not just null) for all other 39 countries —
                not a DM-vs-EM boundary, see honesty note above
  TRDPRC_1    — not available on any bond RIC under this licence
  YIELD       — not available (use YLDTOMAT for US, IMF WEO for others)
  YLDSPD      — not available (use BMK_SPD as substitute)
  MDURATION   — not available (use MOD_DURTN)
  Standalone CDS RICs (e.g. BR5YUSD=R) — all return universe-not-found
  TR.IssuerRating history — SDate/EDate ignored; snapshot only, returns NaN
  ISIN-based get_history — universe-not-found for all ISINs tested

EXCLUDED COUNTRIES (document in thesis Section 3.2)
-----------------------------------------------------
  Russia           — UserNotPermission 92000 (sanctions-related restriction)
  Argentina        — no benchmark RIC available in Workspace
  Ecuador          — no benchmark RIC available in Workspace
  Panama           — no benchmark RIC available in Workspace
  Dominican Rep.   — no benchmark RIC available in Workspace
  Qatar            — no benchmark RIC available in Workspace
  Saudi Arabia     — no benchmark RIC available in Workspace
  UAE              — no benchmark RIC available in Workspace
  Ukraine          — no benchmark RIC available in Workspace

REQUIREMENTS
------------
  pip install lseg-data pandas tqdm

HOW TO RUN
----------
  1. Open Refinitiv Workspace on the university PC and log in.
  2. Get your app key: Help → App Key Generator → select "EDP API"
     (NOT "Eikon Data API" — these generate different key types).
  3. Paste the key into APP_KEY below.
  4. Run: python bond_data_pull_reconstructed.py
  5. If the session drops mid-run, re-run — existing files are skipped.
  6. After the run, copy data/ to USB or cloud storage immediately.

OUTPUT STRUCTURE
----------------
  data/
    raw/
      bonds/       ← one CSV per country, daily rows, variable columns
      ratings/     ← placeholder files only (see KNOWN LIMITATION above)
    logs/
      pull_log.txt ← full run log (INFO + WARNING + ERROR)
      missing.txt  ← pipe-delimited gap log for manual follow-up

CHANGELOG (v1 → v4)
--------------------
  v1: Initial draft using `eikon` library (legacy Eikon desktop app).
  v2: Switched to `lseg-data` library for Refinitiv Workspace.
      Added EDP API key note. connect() used test call on 2024-01-02.
  v3: Fixed field names after diagnostics (TRDPRC_1→MID_PRICE etc).
      Removed separate CDS pull (INT_CDS embedded in bond pull).
      Removed hardcoded column renaming (flexible column save).
      Added MultiIndex column flattening. Added YLDTOMAT warning.
      Ratings switched to TR.IssuerRating after field name failures.
      connect() test date still used broken 2024-01-02 holiday date
      (user fixed locally; file on disk was not updated).
  v4: Fixed connect() — removed broken test call entirely; bare
      ld.open_session() only (raises its own clear error on failure).
      Updated YLDTOMAT warning — now logged once at startup rather than
      per-country (it fires for 43/44 countries; per-country is noise).
      Updated ratings function — added runtime warning that output is
      empty placeholder; directs user to agency downloads.
      Updated docstrings to reflect confirmed licence reality.
      No changes to UNIVERSE, BOND_FIELDS, date chunking, or file I/O.
"""

import os
import time
import logging
import datetime
import traceback

import pandas as pd
import lseg.data as ld
from tqdm import tqdm

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

APP_KEY    = "YOUR_APP_KEY_HERE"   # Help → App Key Generator → select "EDP API"

START_DATE = "2005-01-01"
END_DATE   = "2025-12-31"

OUTPUT_DIR = "data/raw"
LOG_DIR    = "data/logs"

# Pause between API calls (seconds) — prevents rate-limit errors.
API_PAUSE  = 0.5

# ── SOVEREIGN UNIVERSE ────────────────────────────────────────────────────────
# Format: "Country name": "XX10YT=RR benchmark RIC"
# 44 countries. 9 excluded — see module docstring for reasons.

UNIVERSE = {
    # ── DEVELOPED MARKETS (18) ─────────────────────────────────────────
    "United States":   "US10YT=RR",
    "Germany":         "DE10YT=RR",
    "United Kingdom":  "GB10YT=RR",
    "Japan":           "JP10YT=RR",
    "France":          "FR10YT=RR",
    "Italy":           "IT10YT=RR",
    "Spain":           "ES10YT=RR",
    "Canada":          "CA10YT=RR",
    "Australia":       "AU10YT=RR",
    "Netherlands":     "NL10YT=RR",
    "Belgium":         "BE10YT=RR",
    "Sweden":          "SE10YT=RR",
    "Norway":          "NO10YT=RR",
    "Switzerland":     "CH10YT=RR",
    "Portugal":        "PT10YT=RR",
    "Greece":          "GR10YT=RR",
    "Austria":         "AT10YT=RR",
    "Finland":         "FI10YT=RR",

    # ── EMERGING MARKETS (26) ──────────────────────────────────────────
    "Brazil":          "BR10YT=RR",
    "Mexico":          "MX10YT=RR",
    "South Africa":    "ZA10YT=RR",
    "Turkey":          "TR10YT=RR",
    "Indonesia":       "ID10YT=RR",
    "India":           "IN10YT=RR",
    "China":           "CN10YT=RR",
    "Poland":          "PL10YT=RR",
    "Chile":           "CL10YT=RR",
    "Colombia":        "CO10YT=RR",
    "Peru":            "PE10YT=RR",
    "Hungary":         "HU10YT=RR",
    "Czech Republic":  "CZ10YT=RR",
    "Romania":         "RO10YT=RR",
    "Malaysia":        "MY10YT=RR",
    "Thailand":        "TH10YT=RR",
    "Philippines":     "PH10YT=RR",
    "Egypt":           "EG10YT=RR",
    "Nigeria":         "NG10YT=RR",
    "Kenya":           "KE10YT=RR",
    "Kazakhstan":      "KZ10YT=RR",
    "Morocco":         "MA10YT=RR",
    "Vietnam":         "VN10YT=RR",
    "Pakistan":        "PK10YT=RR",
    "Zambia":          "ZM10YT=RR",
    "Sri Lanka":       "LK10YT=RR",
}

# ── BOND FIELDS ───────────────────────────────────────────────────────────────
# All fields confirmed available under this licence via diagnostic testing.
# The API silently omits fields it cannot return — no error is raised.
# YLDTOMAT returns data only for the full_dm tier (DE/JP/CH/UK/US) —
# not a DM-vs-EM boundary, see module docstring honesty note.

BOND_FIELDS = [
    "MID_PRICE",    # mid price — available all 44 countries
    "BID",          # bid price — available most countries
    "ASK",          # ask price — available most countries
    "YLDTOMAT",     # yield to maturity — full_dm tier only (DE/JP/CH/UK/US); included for future-proofing
    "BMK_SPD",      # benchmark spread (bps vs local benchmark) — all 44
    "MOD_DURTN",    # modified duration (years) — all 44
    "CONVEXITY",    # convexity — all 44
    "CLEAN_PRC",    # clean price — most countries
    "DIRTY_PRC",    # dirty price — most countries
    "ZSPREAD",      # Z-spread (bps vs OIS) — most countries
    "INT_CDS",      # CDS-implied spread (bps) — most countries; CDS proxy
]

# ── RATING NUMERIC MAP ────────────────────────────────────────────────────────
# Numeric scale: 1 = AAA/Aaa (best), 22 = D/SD/RD (worst).
# Used if rating history is ever successfully retrieved.

RATING_MAP = {
    "AAA": 1,  "Aaa": 1,
    "AA+": 2,  "Aa1": 2,
    "AA":  3,  "Aa2": 3,
    "AA-": 4,  "Aa3": 4,
    "A+":  5,  "A1":  5,
    "A":   6,  "A2":  6,
    "A-":  7,  "A3":  7,
    "BBB+": 8,  "Baa1": 8,
    "BBB":  9,  "Baa2": 9,
    "BBB-": 10, "Baa3": 10,
    "BB+":  11, "Ba1":  11,
    "BB":   12, "Ba2":  12,
    "BB-":  13, "Ba3":  13,
    "B+":   14, "B1":   14,
    "B":    15, "B2":   15,
    "B-":   16, "B3":   16,
    "CCC+": 17, "Caa1": 17,
    "CCC":  18, "Caa2": 18,
    "CCC-": 19, "Caa3": 19,
    "CC":   20, "Ca":   20,
    "C":    21,
    "D":    22, "SD":   22, "RD": 22,
}

# ── SETUP ─────────────────────────────────────────────────────────────────────

def setup():
    """Create output directories and configure logging to file + terminal."""
    for d in [f"{OUTPUT_DIR}/bonds", f"{OUTPUT_DIR}/ratings", LOG_DIR]:
        os.makedirs(d, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.FileHandler(f"{LOG_DIR}/pull_log.txt"),
            logging.StreamHandler(),
        ]
    )

def connect():
    """
    Open a Workspace desktop session via lseg.data.
    Workspace must be running and logged in on the same machine.
    APP_KEY must be generated via Help → App Key Generator → EDP API.

    Note: ld.open_session() raises its own clear exception if Workspace
    is not running or the key is wrong. No additional connectivity test
    is needed — the first get_history() call will surface any issue.
    """
    ld.open_session(app_key=APP_KEY)
    logging.info("Workspace session opened successfully.")

# ── DATE CHUNKING ─────────────────────────────────────────────────────────────

def date_chunks(start: str, end: str, chunk_years: int = 2):
    """
    Yields (chunk_start, chunk_end) ISO date string pairs covering the
    full start→end range in chunk_years windows.
    2-year chunks at daily frequency (~500 rows) stay well within
    the Refinitiv RDP API limit per request.
    """
    s = datetime.date.fromisoformat(start)
    e = datetime.date.fromisoformat(end)
    while s < e:
        chunk_end = min(
            datetime.date(s.year + chunk_years, s.month, s.day)
            - datetime.timedelta(days=1),
            e
        )
        yield s.isoformat(), chunk_end.isoformat()
        s = chunk_end + datetime.timedelta(days=1)

# ── BOND PULL ─────────────────────────────────────────────────────────────────

def pull_bond_data(country: str, ric: str):
    """
    Pulls daily bond analytics for one country via ld.get_history().

    Key behaviours:
    - Requests all BOND_FIELDS; saves whatever subset is returned.
    - Does NOT rename or enforce a fixed column set — column presence
      varies by country and licence. Check columns before use downstream.
    - Flattens MultiIndex columns if the API returns them.
    - Deduplicates dates at chunk boundaries.
    - Skips if the output file already exists (safe to re-run).
    - Logs errors per chunk to missing.txt without crashing the run.

    Output: data/raw/bonds/<Country_Name>.csv
    Columns: date (index), any subset of BOND_FIELDS, country, ric
    """
    out_path = f"{OUTPUT_DIR}/bonds/{country.replace(' ', '_')}.csv"
    if os.path.exists(out_path):
        logging.info(f"[BONDS] {country} — already exists, skipping.")
        return

    logging.info(f"[BONDS] Pulling {country} ({ric}) ...")
    chunks = []

    for chunk_start, chunk_end in date_chunks(START_DATE, END_DATE):
        try:
            df = ld.get_history(
                universe=ric,
                fields=BOND_FIELDS,
                start=chunk_start,
                end=chunk_end,
                interval="daily",
            )
            if df is not None and not df.empty:
                # Flatten MultiIndex columns (instrument × field) if present
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(-1)
                chunks.append(df)
            time.sleep(API_PAUSE)

        except Exception as e:
            err = str(e)[:120]
            logging.warning(
                f"[BONDS] {country} chunk {chunk_start}–{chunk_end}: {err}"
            )
            _log_missing(country, "bond", chunk_start, chunk_end, err)

    if not chunks:
        logging.warning(
            f"[BONDS] {country} — no data returned. Check RIC: {ric}"
        )
        _log_missing(country, "bond", START_DATE, END_DATE, "No data returned")
        return

    result = pd.concat(chunks)
    result.index.name = "date"
    result = result[~result.index.duplicated(keep="first")]
    result.sort_index(inplace=True)
    result["country"] = country
    result["ric"] = ric
    result.to_csv(out_path)

    data_cols = [c for c in result.columns if c not in ("country", "ric")]
    logging.info(
        f"[BONDS] {country} — saved {len(result)} rows, "
        f"{len(data_cols)} data columns: {data_cols}"
    )

# ── RATINGS PULL ──────────────────────────────────────────────────────────────

def pull_ratings_data(country: str, ric: str):
    """
    Attempts to pull issuer rating history via TR.IssuerRating.

    *** THIS FUNCTION IS KNOWN TO PRODUCE EMPTY OUTPUT ***
    TR.IssuerRating with SDate/EDate parameters was confirmed to return
    NaN for all 44 countries under this university Workspace licence.
    The SDate/EDate parameters are silently ignored by the API.

    The function is retained so that:
    (a) the output directory structure is created for easy manual placement
        of agency-downloaded rating files.
    (b) the skip-if-exists logic works correctly if this function is
        replaced with working logic in future.

    ACTION: Download rating histories directly from agencies and place
    them in data/raw/ratings/ with the naming convention
    <Country_Name>_SP.csv, <Country_Name>_Moodys.csv, <Country_Name>_Fitch.csv
    or a combined <Country_Name>.csv following the column format below:
      country, agency, date, rating, rating_numeric, action

    Saves placeholder to: data/raw/ratings/<country>.csv
    """
    out_path = f"{OUTPUT_DIR}/ratings/{country.replace(' ', '_')}.csv"
    if os.path.exists(out_path):
        logging.info(f"[RTGS]  {country} — already exists, skipping.")
        return

    logging.warning(
        f"[RTGS]  {country} — TR.IssuerRating is licence-blocked for history. "
        f"Saving placeholder. Download ratings from agency websites instead."
    )

    try:
        df = ld.get_data(
            universe=ric,
            fields=[
                "TR.IssuerRating",
                "TR.IssuerRating.Date",
                "TR.IssuerRating.RatingSourceCode",
            ],
            parameters={"SDate": START_DATE, "EDate": END_DATE}
        )

        if df is not None and not df.empty:
            df.columns = [c.strip() for c in df.columns]
            df["country"] = country
            df["ric"] = ric
            rating_col = [
                c for c in df.columns
                if "issuerrating" in c.lower()
                and "date" not in c.lower()
                and "source" not in c.lower()
            ]
            if rating_col:
                df["rating_numeric"] = df[rating_col[0]].map(RATING_MAP)
            df.to_csv(out_path, index=False)
        else:
            # Write an explicit placeholder so the file exists
            pd.DataFrame(columns=[
                "country", "ric", "agency", "date",
                "rating", "rating_numeric", "action"
            ]).to_csv(out_path, index=False)

    except Exception as e:
        err = str(e)[:150]
        logging.warning(f"[RTGS]  {country}: {err}")
        _log_missing(country, "ratings", START_DATE, END_DATE, err)
        pd.DataFrame(columns=[
            "country", "ric", "agency", "date",
            "rating", "rating_numeric", "action"
        ]).to_csv(out_path, index=False)

# ── MISSING LOG ───────────────────────────────────────────────────────────────

def _log_missing(country: str, data_type: str,
                 start: str, end: str, reason: str):
    """Appends one pipe-delimited line to missing.txt for manual follow-up."""
    with open(f"{LOG_DIR}/missing.txt", "a") as f:
        f.write(
            f"{datetime.datetime.now().isoformat()}  |  {country}  |  "
            f"{data_type}  |  {start} to {end}  |  {reason}\n"
        )

# ── VALIDATION SUMMARY ────────────────────────────────────────────────────────

def run_validation():
    """
    Prints a coverage table after the run completes.
    Shows row count and which data columns were saved per country.
    """
    print("\n" + "=" * 80)
    print("COVERAGE SUMMARY")
    print("=" * 80)
    print(f"{'Country':<25} {'Rows':>7}  {'Columns present'}")
    print("-" * 80)

    for country in UNIVERSE:
        safe = country.replace(" ", "_")
        bond_path = f"{OUTPUT_DIR}/bonds/{safe}.csv"
        if not os.path.exists(bond_path):
            print(f"{country:<25} {'MISSING':>7}")
            continue
        try:
            df = pd.read_csv(bond_path, nrows=1)
            n_rows = sum(1 for _ in open(bond_path)) - 1
            data_cols = [
                c for c in df.columns
                if c not in ("date", "country", "ric", "Unnamed: 0")
            ]
            print(f"{country:<25} {n_rows:>7}  {data_cols}")
        except Exception:
            print(f"{country:<25} {'ERROR':>7}")

    print("=" * 80)
    print(f"\nLogs : {LOG_DIR}/pull_log.txt")
    print(f"Gaps : {LOG_DIR}/missing.txt")
    print("\nNOTE: Ratings files are placeholders — see pull_ratings_data docstring.")

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    setup()

    logging.info("=" * 60)
    logging.info("Sovereign data pull v4 — starting")
    logging.info(
        f"Universe: {len(UNIVERSE)} countries | {START_DATE} to {END_DATE}"
    )
    logging.info("=" * 60)
    logging.info(
        "NOTE: YLDTOMAT is available only for the full_dm tier "
        "(DE/JP/CH/UK/US). All other 39 countries will return 10 columns "
        "(YLDTOMAT absent). This is expected behaviour, not an error."
    )
    logging.info(
        "NOTE: Ratings pull produces placeholder files only. "
        "Download rating histories from S&P, Moody's, and Fitch directly."
    )

    connect()

    countries = list(UNIVERSE.items())

    # ── BOND DATA ────────────────────────────────────────────────────────
    print("\n--- BOND DATA ---")
    for country, ric in tqdm(countries, desc="Bonds"):
        try:
            pull_bond_data(country, ric)
        except Exception:
            logging.error(
                f"[BONDS] {country} — unexpected error:\n"
                f"{traceback.format_exc()}"
            )

    # ── RATINGS DATA (placeholders) ──────────────────────────────────────
    print("\n--- RATINGS (placeholders — see docstring) ---")
    for country, ric in tqdm(countries, desc="Ratings"):
        try:
            pull_ratings_data(country, ric)
        except Exception:
            logging.error(
                f"[RTGS]  {country} — unexpected error:\n"
                f"{traceback.format_exc()}"
            )

    run_validation()
    logging.info("Pull complete. Review missing.txt for any gaps.")

if __name__ == "__main__":
    main()
