"""Gap map and event survival on the CANDIDATE H1 panel, before vs after the
second pass, under the pre-registration v0.4 strict any-agency rule.

COUNTS ONLY -- no risk score, return or portfolio outcome is loaded or
computed. Outputs go to data/diagnostics/ratings/second_pass/.

Rule (pre-registration v0.4 section 5.1): an event is excluded from the
primary set if its event quarter OR any of its preceding 4 quarters falls
in a documented coverage gap for ANY of the three agencies. Cells are
calendar years per (country, agency); a year-cell is the finest grain the
collection supports.

A cell counts as COMPLETE when the letter-rating path is established, even
if the outlook path is unverified:
  * a multi-notch (>= 3) step between consecutive rows is not a gap when a
    second-pass resolution row for that country/agency (status resolved_*
    or partly_resolved, rating type FC_LT or S&P unspecified) covers the
    step (+-3 days) -- the single action is then confirmed, or the
    intermediate actions were added;
  * a documented stale-table cutoff is lifted when its second-pass row is
    resolved or partly_resolved (letter path known; only outlooks open);
    the 12 unresolved Fitch rows keep their cutoff;
  * the series start year is partial unless the series starts on 1 January
    (S&P series carry a 2004-01-01 anchor from the second pass);
  * years before the series start are missing.
The "before" figures use the first-collection logic unchanged (ratings_v2_
diagnostics / ratings_v2_event_survival) but the v0.4 window, so before and
after are like for like; the old-window figures are also printed to show
the old numbers (185 / 88 / 36) are reproduced.

Run: python3 diagnostics/second_pass_event_survival.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "diagnostics"))
import ratings_v2_diagnostics as rv2  # noqa: E402
import ratings_v2_event_survival as old_surv  # noqa: E402

SP_DIR = REPO_ROOT / "data" / "raw" / "ratings_v2_second_pass"
PANEL = REPO_ROOT / "data" / "interim" / "ratings_h1_candidate.csv"
DIAG_DIR = REPO_ROOT / "data" / "diagnostics" / "ratings" / "second_pass"
AGENCIES = ["SP", "Moodys", "Fitch"]
YEARS = range(2000, 2026)
TOL = pd.Timedelta(days=3)
RESOLVED = {"resolved_no_action", "resolved_actions_found", "partly_resolved"}

# Decisions for every partly_resolved FC row (amendment 5): a window is
# complete when every letter-rating change inside it is known at least to
# the month, even if outlook actions are unverified.
PARTLY_DECISIONS = {
    39: ("Spain Fitch FC 2018-01-19..2025-12-31", "COMPLETE",
         "letter rating A- throughout 2018-2024 (press 'A- since 2018'); the "
         "only letter change, upgrade to A, is dated to the day (2025-09-26); "
         "only outlook actions 2018-2024 are unverified"),
    64: ("Czech Fitch FC 2018-08-03..2025-12-31", "COMPLETE",
         "letter rating AA- throughout (affirmations); no letter change in the "
         "window; outlook moves (Negative May 2022, later back to Stable) are "
         "month-precision or undated but are not letter changes"),
    76: ("France S&P FC 2011-12-05..2025-02-28", "COMPLETE",
         "every letter change known to the day: AAA->AA+ 2012-01-13, AA "
         "2013-11-08 (S&P history to 2021-06-30), AA- 2024-05-31 ('from AA' "
         "means no letter change 2021-2024); outlook actions 2021-2024 and "
         "the 2025-02-28 endpoint unverified"),
    113: ("Portugal S&P FC 2013-09-18..2025-02-28", "COMPLETE",
          "letter changes known to the day through 2021-06-30 (S&P history), "
          "A- 2024-03-01 and A 2025-02-28 to the day; the BBB->BBB+ upgrade "
          "(Sept 2022) is known to the month only, which meets the month "
          "bar. The 3-notch BBB (2020-04-24) -> A- (2024-03-01) step in the "
          "panel is therefore accepted. Upgrade only: no downgrade event is "
          "affected"),
    116: ("South Africa Fitch FC 2021-12-15..2025-12-31", "COMPLETE",
          "letter rating BB- throughout (upgrade to BB on 2026-06-05 is "
          "'from BB-' and the first in ~21 years); no letter change in the "
          "window; outlook path 2022-2025 unverified"),
}


def load_resolution() -> pd.DataFrame:
    r = pd.read_csv(SP_DIR / "second_pass_resolution.csv", dtype=str,
                    keep_default_na=False)
    r["target_row"] = r["target_row"].astype(int)
    r["df"] = pd.to_datetime(r["date_from"].replace("", np.nan))
    r["dt"] = pd.to_datetime(r["date_to"].replace("", np.nan))
    return r


def accepted_windows(res: pd.DataFrame) -> dict:
    ok = res[res["status"].isin(RESOLVED)
             & res["rating_type"].isin(["FC_LT", "unspecified"])
             & res["df"].notna() & res["dt"].notna() & (res["df"] <= res["dt"])]
    out = {}
    for _, x in ok.iterrows():
        out.setdefault((x["iso3"], x["agency"]), []).append(
            (x["df"], x["dt"], int(x["target_row"])))
    return out


def lifted_stale(res: pd.DataFrame) -> set:
    s = res[res["reason"].str.startswith("stale Fitch table")
            & res["status"].isin(RESOLVED)]
    return {(x["iso3"], x["agency"], "FC_LT") for _, x in s.iterrows()}


# ----------------------------------------------------------------- new map
def new_gap_map(panel, windows, lifted):
    cutoffs = rv2.parse_stale_cutoffs()
    rows = []
    series = {k: g.sort_values("action_date")
              for k, g in panel.groupby(["iso3", "agency"])}
    countries = sorted(panel["iso3"].unique())
    for iso3 in countries:
        for ag in AGENCIES:
            s = series.get((iso3, ag))
            if s is None:
                for y in YEARS:
                    rows.append((iso3, ag, y, "missing", "no_series", False))
                continue
            start = s["action_date"].iloc[0]
            genuine_first = s["action"].iloc[0] in ("new", "initial_rating")
            dates = s["action_date"].tolist()
            nums = s["rating_numeric"].tolist()
            bad_years = set()
            for i in range(1, len(s)):
                if abs(nums[i] - nums[i - 1]) >= 3:
                    p, c = dates[i - 1], dates[i]
                    cover = any(df - TOL <= p and c <= dt + TOL
                                for df, dt, _ in windows.get((iso3, ag), []))
                    if not cover:
                        bad_years.update(range(p.year, c.year + 1))
            key = (iso3, ag, "FC_LT")
            stale = cutoffs.get(key)
            if key in lifted:
                stale = None
            for y in YEARS:
                if y < start.year:
                    rows.append((iso3, ag, y, "missing", "before_series_start",
                                 genuine_first))
                elif y == start.year and not (start.month == 1 and start.day == 1):
                    rows.append((iso3, ag, y, "partial", "start_year_partial",
                                 genuine_first))
                elif y in bad_years:
                    rows.append((iso3, ag, y, "partial",
                                 "multi_notch_step_unresolved", False))
                elif stale is not None and y > stale.year:
                    rows.append((iso3, ag, y, "partial", "stale_table", False))
                else:
                    rows.append((iso3, ag, y, "complete", "", False))
    return pd.DataFrame(rows, columns=["iso3", "agency", "year", "status",
                                       "reason", "not_yet_rated"])


def events_from(panel, key):
    ev = []
    for (k, ag), s in panel.sort_values("action_date").groupby([key, "agency"]):
        n = s["rating_numeric"].tolist()
        d = s["action_date"].tolist()
        r = s["rating"].tolist()
        for i in range(1, len(s)):
            if n[i] > n[i - 1]:
                ev.append({key: k, "agency": ag, "date": d[i],
                           "from_rating": r[i - 1], "to_rating": r[i]})
    ev = pd.DataFrame(ev)
    ev["quarter"] = ev["date"].dt.to_period("Q")
    col = (ev.sort_values("date").groupby([key, "quarter"], as_index=False)
             .first().sort_values([key, "date"]))
    flags = []
    for _, g in col.groupby(key):
        prev = None
        for _, row in g.iterrows():
            flags.append(prev is None or (row["quarter"] - prev).n > 4)
            prev = row["quarter"]
    col["initial"] = flags
    return col.reset_index(drop=True)


def window_years(q, include_event_quarter):
    ks = range(0 if include_event_quarter else 1, 5)
    return {(q - k).year for k in ks}


def survive(events, status_of, key, include_event_quarter):
    """status_of(country, agency, year) -> 'complete' or not."""
    surv, blockers = [], []
    for _, r in events.iterrows():
        bl = [(ag, y) for y in sorted(window_years(r["quarter"], include_event_quarter))
              for ag in AGENCIES if status_of(r[key], ag, y) != "complete"]
        surv.append(not bl)
        blockers.append(bl)
    out = events.rename(columns={"initial_downgrade": "initial"}).copy()
    out["survives"] = surv
    out["blockers"] = blockers
    return out


def tally(ev, key):
    s = ev[ev["survives"]]
    si = s[s["initial"]]
    return {
        "collapsed_events_all": len(ev),
        "initial_events_all": int(ev["initial"].sum()),
        "collapsed_surviving": len(s),
        "initial_surviving": len(si),
        "countries_with_surviving_initial": int(si[key].nunique()),
        "initial_surviving_2005_plus": int((si["date"] >= "2005-01-01").sum()),
        "countries_surviving_initial_2005_plus": int(
            si[si["date"] >= "2005-01-01"][key].nunique()),
    }


def main():
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    rv2.OUT_DIR = DIAG_DIR / "currency_tests_old"
    rv2.OUT_DIR.mkdir(exist_ok=True)

    # -------- BEFORE: first collection, old gap logic, both windows
    v2 = rv2.load_v2()
    passing_old = rv2.sp_currency_tests(v2)["passing_countries"]
    lookup_old = old_surv.year_status_lookup(v2, passing_old)
    ev_old = old_surv.rebuild_events(v2, passing_old)
    old_status = lambda c, a, y: lookup_old.get((c, a, y), "missing")  # noqa: E731
    before_oldwin = tally(survive(ev_old, old_status, "country", False), "country")
    before_v04 = tally(survive(ev_old, old_status, "country", True), "country")

    # -------- AFTER: candidate panel, new gap logic
    panel = pd.read_csv(PANEL, parse_dates=["action_date"])
    res = load_resolution()
    windows = accepted_windows(res)
    lifted = lifted_stale(res)
    gm = new_gap_map(panel, windows, lifted)
    look = {(r.iso3, r.agency, r.year): r.status for r in gm.itertuples()}
    new_status = lambda c, a, y: look.get((c, a, y), "missing")  # noqa: E731
    ev_new = events_from(panel, "iso3")
    surv_new = survive(ev_new, new_status, "iso3", True)
    after_v04 = tally(surv_new, "iso3")
    after_oldwin = tally(survive(ev_new, new_status, "iso3", False), "iso3")

    # sensitivity: genuine first ratings (not yet rated) are not a gap
    nyr = {(r.iso3, r.agency, r.year) for r in gm.itertuples()
           if r.not_yet_rated and r.status != "complete"}
    sens_status = lambda c, a, y: ("complete" if (c, a, y) in nyr  # noqa: E731
                                   else new_status(c, a, y))
    after_sens = tally(survive(ev_new, sens_status, "iso3", True), "iso3")

    table = pd.DataFrame({
        "before_old_window_(reproduction)": before_oldwin,
        "before_v04_window": before_v04,
        "after_v04_window": after_v04,
        "after_old_window_(info)": after_oldwin,
        "after_v04_not_yet_rated_sensitivity": after_sens}).T
    table.to_csv(DIAG_DIR / "event_survival_before_after.csv")
    print(table.to_string())

    # -------- blocking cells
    init = surv_new[surv_new["initial"]]
    cell_rows = []
    for _, e in init.iterrows():
        for ag, y in e["blockers"]:
            cell_rows.append({"iso3": e["iso3"], "agency": ag, "year": y,
                              "sole_blocker": len(e["blockers"]) == 1,
                              "event_date": e["date"].date()})
    cells = pd.DataFrame(cell_rows)
    if len(cells):
        agg = (cells.groupby(["iso3", "agency", "year"])
                    .agg(initial_events_blocked=("event_date", "nunique"),
                         events_blocked_only_by_this_cell=("sole_blocker", "sum"))
                    .reset_index())
        agg = agg.merge(gm[["iso3", "agency", "year", "status", "reason"]],
                        on=["iso3", "agency", "year"], how="left")
        agg = agg.sort_values(["initial_events_blocked", "iso3"],
                              ascending=[False, True])
    else:
        agg = pd.DataFrame()
    agg.to_csv(DIAG_DIR / "blocking_cells_initial_events.csv", index=False)

    # reason breakdown, by agency x reason, over cells that block >=1 initial event
    if len(agg):
        by_reason = (agg.groupby(["agency", "reason"])
                        .agg(cells=("year", "size"),
                             sum_initial_events_blocked=("initial_events_blocked", "sum"))
                        .reset_index())
        by_reason.to_csv(DIAG_DIR / "blocking_cells_by_reason.csv", index=False)
        print("\nblocking cells by agency x reason:\n", by_reason.to_string(index=False))

    # series whose first row is a bare "new" after 2004: either a genuine
    # first rating or missing early history (not verified by the second
    # pass, which only targeted rows flagged as non-initial). Flag the ones
    # that block an initial event dated 2005 or later.
    blk05 = set()
    if len(cells):
        c05 = cells[pd.to_datetime(cells["event_date"]) >= "2005-01-01"]
        blk05 = set(zip(c05["iso3"], c05["agency"]))
    late = []
    for (iso3, ag), g in panel.sort_values("action_date").groupby(["iso3", "agency"]):
        f = g.iloc[0]
        if f["action_date"] > pd.Timestamp("2004-01-01") and f["action"] in ("new", "initial_rating"):
            late.append({"iso3": iso3, "agency": ag,
                         "first_row_date": f["action_date"].date(),
                         "first_row_rating": f["rating"],
                         "first_row_action": f["action"],
                         "provenance": f["provenance"],
                         "blocks_initial_event_2005_plus": (iso3, ag) in blk05})
    pd.DataFrame(late).sort_values(
        ["blocks_initial_event_2005_plus", "iso3"], ascending=[False, True]
    ).to_csv(DIAG_DIR / "late_start_series_unverified.csv", index=False)

    # PROXY for the S&P Jul-2021 cross-check (the S&P URL returns HTTP 403,
    # so the table itself cannot be parsed): compare panel S&P rows <=
    # 2021-06-30 with the second pass's transcription of that table. The
    # transcribed windows are the resolved second-pass S&P windows; v2-only
    # rows INSIDE a window are candidate mismatches, rows outside are
    # unverified.
    sp_act = pd.read_csv(SP_DIR / "second_pass_actions.csv", dtype=str,
                         keep_default_na=False)
    sp_act = sp_act[sp_act["source_url_1"].str.contains("spglobal.com")
                    & (sp_act["rating_type"] == "FC_LT")]
    sp_act["d"] = pd.to_datetime(sp_act["action_date"])
    sp_panel = panel[(panel["agency"] == "SP")
                     & (panel["action_date"] <= "2021-06-30")].copy()
    def klass(r):
        if "second_pass" in r["provenance"]:
            return "confirmed_by_S&P_table_transcription"
        if any(df <= r["action_date"] <= dt
               for df, dt, _ in windows.get((r["iso3"], "SP"), [])):
            return "CANDIDATE_MISMATCH_v2_only_inside_transcribed_span"
        return "unverified_outside_transcribed_span"
    sp_panel["check"] = sp_panel.apply(klass, axis=1)
    sp_panel[["iso3", "action_date", "rating", "outlook", "provenance", "check"]] \
        .to_csv(DIAG_DIR / "sp_history_proxy_check.csv", index=False)
    print("\nS&P proxy check (rows <= 2021-06-30):",
          sp_panel["check"].value_counts().to_dict())

    gm.to_csv(DIAG_DIR / "gap_map_candidate.csv", index=False)
    out = surv_new.copy()
    out["blockers"] = out["blockers"].apply(
        lambda b: ";".join(f"{a}:{y}" for a, y in b))
    out.to_csv(DIAG_DIR / "event_survival_events_candidate.csv", index=False)
    by_year = (surv_new.assign(year=surv_new["date"].dt.year)
               .groupby("year").apply(lambda g: pd.Series({
                   "collapsed": len(g), "initial": int(g["initial"].sum()),
                   "collapsed_surviving": int(g["survives"].sum()),
                   "initial_surviving": int((g["survives"] & g["initial"]).sum())}),
                   include_groups=False))
    by_year.to_csv(DIAG_DIR / "event_survival_by_year_candidate.csv")

    # decisions for partly_resolved FC rows
    dec = []
    for tr, (label, verdict, why) in PARTLY_DECISIONS.items():
        row = res[res["target_row"] == tr].iloc[0]
        assert row["status"] == "partly_resolved", tr
        dec.append({"target_row": tr, "series_window": label,
                    "decision": verdict, "reason": why})
    pd.DataFrame(dec).to_csv(DIAG_DIR / "partly_resolved_decisions.csv", index=False)
    pr = res[(res["status"] == "partly_resolved")
             & res["rating_type"].isin(["FC_LT", "unspecified"])]
    missing = set(pr["target_row"]) - set(PARTLY_DECISIONS)
    # partly_resolved rows with no window (hint rows) are LC / undated and
    # carry no gap decision; anything else must have an explicit decision.
    unexpected = [t for t in missing
                  if res.loc[res["target_row"] == t, "df"].notna().iloc[0]]
    assert not unexpected, f"partly_resolved FC rows without decision: {unexpected}"

    meta = {
        "accepted_windows": sum(len(v) for v in windows.values()),
        "stale_cutoffs_in_v2": len(rv2.parse_stale_cutoffs()),
        "stale_cutoffs_lifted": len([k for k in rv2.parse_stale_cutoffs() if k in lifted]),
        "stale_cutoffs_remaining": len([k for k in rv2.parse_stale_cutoffs() if k not in lifted]),
        "candidate_panel_rows": len(panel),
        "candidate_events_collapsed": len(ev_new),
    }
    (DIAG_DIR / "event_survival_meta.json").write_text(json.dumps(meta, indent=2))
    print("\n", meta)


if __name__ == "__main__":
    main()
