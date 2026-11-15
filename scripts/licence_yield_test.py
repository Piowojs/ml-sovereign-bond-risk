"""Licence/field-scope test for the return rebuild — FOR THE UNIVERSITY
LIBRARY PC ONLY. Do NOT run in the normal dev environment (no Refinitiv
Workspace / lseg-data access there — standing constraint, see CLAUDE.md).

Written 2026-11-15 alongside the return-construction diagnostics
(diagnostics/returns_diagnostics.py, data/diagnostics/returns/summary.md).
Purpose: before the return rebuild, establish what the university licence
actually returns for (a) yield fields on benchmark RICs beyond the 11
fields of the original pull, (b) 3-month benchmark RICs, (c) FX RICs —
and (e) close the Thailand data gap (its bond CSV stops 2025-03-26 while
every other country runs to late Dec 2025; see CLAUDE.md "Data
acquisition status").

Conventions copied from src/data_acquisition/bond_data_pull_reconstructed.py:
lseg.data (NOT the old eikon package), ld.open_session with an app key
generated via Help -> App Key Generator -> "EDP API" (not "Eikon Data
API"), ld.get_history for time series. Every test is wrapped so one
failure (licence denial, bad RIC) is logged and the rest still run.

ALL output goes to one log file: data/logs/licence_yield_test_log.txt
(plus terminal). Test (e) additionally saves the re-pulled Thailand data
to data/diagnostics/licence_test/TH10YT_repull.csv for later merging —
it does NOT touch data/raw/.

Run (university PC, Workspace open and logged in):
    python scripts/licence_yield_test.py
"""

from __future__ import annotations

import datetime
import logging
import os

import lseg.data as ld
import pandas as pd

APP_KEY = "YOUR_APP_KEY_HERE"  # Help -> App Key Generator -> select "EDP API"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(REPO_ROOT, "data", "logs", "licence_yield_test_log.txt")
OUT_DIR = os.path.join(REPO_ROOT, "data", "diagnostics", "licence_test")

BOND_RICS_10Y = ["PL10YT=RR", "EG10YT=RR", "TR10YT=RR", "DE10YT=RR"]
YIELD_FIELDS = ["MID_YLD_1", "B_YLD_1", "A_YLD_1"]
BOND_RICS_3M = ["PL3MT=RR", "EG3MT=RR"]
FX_RICS = ["PLN=", "EGP="]
TEST_START, TEST_END = "2024-01-01", "2024-12-31"
THAILAND_RIC = "TH10YT=RR"
THAILAND_START = "2025-03-01"


def setup_logging():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
    )


def describe(df: pd.DataFrame | None, label: str):
    """Log shape, columns, per-column coverage %, and first/last date."""
    if df is None or len(df) == 0:
        logging.warning("%s: EMPTY RESULT", label)
        return
    logging.info("%s: %d rows, index %s -> %s", label, len(df), df.index.min(), df.index.max())
    logging.info("%s: columns = %s", label, list(df.columns))
    for col in df.columns:
        cov = 100.0 * df[col].notna().mean()
        logging.info("%s:   %-20s %5.1f%% non-null", label, str(col), cov)


def try_history(label: str, **kwargs):
    """ld.get_history wrapped so a licence denial logs and returns None."""
    try:
        df = ld.get_history(**kwargs)
        describe(df, label)
        return df
    except Exception as err:  # noqa: BLE001 -- log every failure mode verbatim
        logging.error("%s: FAILED -- %s: %s", label, type(err).__name__, err)
        return None


def main():
    setup_logging()
    logging.info("=== licence_yield_test start (see module docstring for purpose) ===")
    ld.open_session(app_key=APP_KEY)
    logging.info("Workspace session opened successfully.")

    # (a) 10Y benchmark RICs, NO fields argument: what does the licence
    #     return by default? (The original pull always passed an explicit
    #     field list; the default field set was never observed.)
    for ric in BOND_RICS_10Y:
        try_history(f"(a) {ric} no-fields 2024", universe=ric,
                    start=TEST_START, end=TEST_END, interval="daily")

    # (b) Explicit yield fields on the same RICs. YLDTOMAT is known to be
    #     licence-gated to 5 full_dm countries (see CLAUDE.md); the open
    #     question is whether the quote-level yield fields are gated the
    #     same way. DE10YT=RR is the known-good control (full_dm member).
    for ric in BOND_RICS_10Y:
        try_history(f"(b) {ric} explicit yield fields 2024", universe=ric,
                    fields=YIELD_FIELDS, start=TEST_START, end=TEST_END,
                    interval="daily")

    # (c) 3-month benchmark RICs — the local short rate is the planned
    #     excess-return denominator under the local-currency re-scope.
    for ric in BOND_RICS_3M:
        try_history(f"(c) {ric} no-fields 2024", universe=ric,
                    start=TEST_START, end=TEST_END, interval="daily")
        try_history(f"(c) {ric} explicit yield fields 2024", universe=ric,
                    fields=YIELD_FIELDS, start=TEST_START, end=TEST_END,
                    interval="daily")

    # (d) FX spot RICs — needed for the USD-unhedged robustness leg.
    for ric in FX_RICS:
        try_history(f"(d) {ric} no-fields 2024", universe=ric,
                    start=TEST_START, end=TEST_END, interval="daily")

    # (e) Thailand re-pull from 2025-03-01: its raw CSV stops 2025-03-26.
    #     No fields argument first (maximum chance of rows), then the
    #     original pull's call shape can be replayed later if this works.
    today = datetime.date.today().isoformat()
    df = try_history(f"(e) {THAILAND_RIC} re-pull {THAILAND_START} -> today",
                     universe=THAILAND_RIC, start=THAILAND_START, end=today,
                     interval="daily")
    if df is not None and len(df):
        out_path = os.path.join(OUT_DIR, "TH10YT_repull.csv")
        df.to_csv(out_path)
        logging.info("(e) saved %d rows to %s (NOT merged into data/raw -- "
                     "merge is a separate, reviewed step)", len(df), out_path)
    else:
        logging.warning("(e) Thailand re-pull returned nothing -- the "
                        "2025-03-26 stop may be a licence/RIC issue, not a "
                        "one-off pull gap. Record whatever error appears "
                        "above in CLAUDE.md after this session.")

    logging.info("=== licence_yield_test complete -- copy %s back to the "
                 "main machine ===", LOG_PATH)


if __name__ == "__main__":
    main()
