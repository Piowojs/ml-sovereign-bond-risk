"""Event survival under the pre-registration gap rule + second-pass
target list -- diagnostics ONLY, same scope boundary as
diagnostics/ratings_v2_diagnostics.py (no labels regenerated, no
lead/lag computed, nothing merged into ratings_panel.csv).

1. Event survival (FC_LT + passing S&P unspecified variant throughout):
   collapsed country-quarter downgrade events and initial events, total
   and by event year, under three gap-rule variants:
   (i)   no gap rule;
   (ii)  the current pre-registration rule (docs/
         stage1_h1_preregistration.md section 5.1): an event is excluded
         if any of its preceding 4 quarters falls in a documented
         coverage gap for the ISSUING agency;
   (iii) a stricter rule: gap for ANY of the three agencies in the
         preceding 4 quarters.
   "Documented coverage gap" = a country x agency x year cell that is
   not `complete` under the same classification as the gap map
   (missing before the series' first knowable rating; partial on a
   multi-notch >= 3 possible-gap span or after a stale-table cutoff),
   computed here for 2000-2025 so early events' lookback windows are
   classifiable (the published gap-map CSV stays 2004-2025). The
   `initial` flag is defined on the full collapsed event set (actual
   downgrade history), per the pre-registration -- the gap rules filter
   on top of it, they do not redefine it.

2. second_pass_targets.csv: one row per item a second collection pass
   should resolve -- stale Fitch FC_LT tables, MISSING ACTION SUSPECTED
   cases, multi-notch possible-gap spans, FC_LT series starting after
   2004 whose first row is not marked as a new rating, the two known
   cross-collection problems (Nigeria Moody's 2019-12, Sri Lanka S&P
   2007-01-23), and the undated latest-rating rows from
   excluded_source_rows.csv as hints. Priority ranks by
   n_events_affected under rule (iii) (events excluded by rule (iii)
   whose lookback window or event quarter overlaps the target span, same
   country).

Outputs (data/diagnostics/ratings/):
  ratings_v2_event_survival_by_year.csv
  ratings_v2_event_survival_events.csv
  second_pass_targets.csv

Run: python3 diagnostics/ratings_v2_event_survival.py
"""

import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "diagnostics"))
from ratings_v2_diagnostics import (  # noqa: E402
    OUT_DIR, POSSIBLE_GAP_NOTCHES, V2_DIR, build_series, load_v2,
    parse_stale_cutoffs, sp_currency_tests)

AGENCIES = ["SP", "Moodys", "Fitch"]
SURVIVAL_YEARS = range(2000, 2026)


# ------------------------------------------------- coverage status lookup
def year_status_lookup(v2: pd.DataFrame, passing: set) -> dict:
    """(country, agency, year) -> complete/partial/missing, 2000-2025,
    same classification as ratings_v2_diagnostics.gap_map but over the
    wider year range needed for early events' lookback windows."""
    cutoffs = parse_stale_cutoffs()
    series = build_series(v2, passing, augmented=True)
    lookup = {}
    for (country, agency), s in series.items():
        iso3 = s["iso3"].iloc[0]
        start = s["action_date"].iloc[0]
        stale = cutoffs.get((iso3, agency, "FC_LT"))
        gap_years = set()
        dates = s["action_date"].tolist()
        nums = s["rating_numeric"].tolist()
        for i in range(1, len(s)):
            if abs(nums[i] - nums[i - 1]) >= POSSIBLE_GAP_NOTCHES:
                gap_years.update(range(dates[i - 1].year, dates[i].year + 1))
        for year in SURVIVAL_YEARS:
            if year < start.year:
                status = "missing"
            elif (year == start.year
                  and not (start.month == 1 and start.day == 1)):
                status = "partial"
            elif year in gap_years:
                status = "partial"
            elif stale is not None and year > stale.year:
                status = "partial"
            else:
                status = "complete"
            lookup[(country, agency, year)] = status
    return lookup


def rebuild_events(v2: pd.DataFrame, passing: set) -> pd.DataFrame:
    """Collapsed country-quarter downgrades, augmented variant --
    identical logic to ratings_v2_diagnostics.event_counts."""
    series = build_series(v2, passing, augmented=True)
    events = []
    for (country, agency), s in series.items():
        dates = s["action_date"].tolist()
        nums = s["rating_numeric"].tolist()
        ratings = s["rating"].tolist()
        for i in range(1, len(s)):
            if nums[i] > nums[i - 1]:
                events.append({"country": country, "agency": agency,
                               "date": dates[i],
                               "from_rating": ratings[i - 1],
                               "to_rating": ratings[i]})
    ev = pd.DataFrame(events)
    ev["quarter"] = ev["date"].dt.to_period("Q")
    collapsed = (ev.sort_values("date")
                   .groupby(["country", "quarter"], as_index=False).first())
    collapsed = collapsed.sort_values(["country", "date"])
    flags = []
    for _, g in collapsed.groupby("country"):
        prev_q = None
        for _, row in g.iterrows():
            flags.append(prev_q is None or (row["quarter"] - prev_q).n > 4)
            prev_q = row["quarter"]
    collapsed["initial_downgrade"] = flags
    return collapsed.reset_index(drop=True)


# --------------------------------------------------------- 1. survival
def event_survival(events: pd.DataFrame, lookup: dict) -> pd.DataFrame:
    def window_years(q):
        return {(q - k).year for k in range(1, 5)}

    def gap_in_window(country, agencies, q):
        for y in window_years(q):
            for ag in agencies:
                if lookup.get((country, ag, y), "missing") != "complete":
                    return True
        return False

    events = events.copy()
    events["survives_rule_agency"] = [
        not gap_in_window(r["country"], [r["agency"]], r["quarter"])
        for _, r in events.iterrows()]
    events["survives_rule_any"] = [
        not gap_in_window(r["country"], AGENCIES, r["quarter"])
        for _, r in events.iterrows()]
    events["year"] = events["date"].dt.year

    rows = []
    for year, g in events.groupby("year"):
        rows.append({
            "year": year,
            "collapsed_no_rule": len(g),
            "initial_no_rule": int(g["initial_downgrade"].sum()),
            "collapsed_rule_agency": int(g["survives_rule_agency"].sum()),
            "initial_rule_agency": int((g["survives_rule_agency"]
                                        & g["initial_downgrade"]).sum()),
            "collapsed_rule_any": int(g["survives_rule_any"].sum()),
            "initial_rule_any": int((g["survives_rule_any"]
                                     & g["initial_downgrade"]).sum()),
        })
    by_year = pd.DataFrame(rows).sort_values("year")
    by_year.to_csv(OUT_DIR / "ratings_v2_event_survival_by_year.csv",
                   index=False)
    events.to_csv(OUT_DIR / "ratings_v2_event_survival_events.csv",
                  index=False)
    return by_year, events


# ----------------------------------------------- 2. second-pass targets
def parse_unresolved_bullets() -> list:
    """Per-series bullet lines of unresolved.md with (iso3, country,
    agency, rating_type, line)."""
    text = (V2_DIR / "unresolved.md").read_text()
    out = []
    country, iso3 = None, None
    for line in text.splitlines():
        m = re.match(r"### (.+) \(([A-Z]{3})\)", line)
        if m:
            country, iso3 = m.group(1), m.group(2)
            continue
        m = re.match(r"- \*\*(\w+) (FC_LT|LC_LT|unspecified)\*\*", line)
        if m and iso3:
            out.append({"country": country, "iso3": iso3,
                        "agency": m.group(1), "rating_type": m.group(2),
                        "line": line})
    return out


def second_pass_targets(v2: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    bullets = parse_unresolved_bullets()
    iso3_to_country = dict(v2[["iso3", "country"]].drop_duplicates().values)
    targets = []

    # (1) stale Fitch FC_LT tables
    for b in bullets:
        if b["agency"] == "Fitch" and b["rating_type"] == "FC_LT":
            m = re.search(r"no action found after ([0-9-]+)", b["line"])
            if m:
                targets.append({**{k: b[k] for k in
                                   ("country", "iso3", "agency",
                                    "rating_type")},
                                "date_from": m.group(1),
                                "date_to": "2025-12-31",
                                "reason": "stale Fitch table: no action "
                                          f"found after {m.group(1)}"})

    # (2) MISSING ACTION SUSPECTED
    for b in bullets:
        m = re.search(r"MISSING ACTION SUSPECTED: countryeconomy shows "
                      r"current \w+ rating ([A-Za-z+\-]+) \(undated\) but "
                      r"latest dated row in any source is ([A-Za-z+\-]+) "
                      r"on ([0-9-]+)", b["line"])
        if m:
            targets.append({**{k: b[k] for k in
                               ("country", "iso3", "agency", "rating_type")},
                            "date_from": m.group(3), "date_to": "2025-12-31",
                            "reason": "missing action suspected: current "
                                      f"{m.group(1)} vs last dated "
                                      f"{m.group(2)} on {m.group(3)}"})

    # (3) multi-notch possible-gap flags (collector's own GAP? notes)
    gap_rows = v2[v2["notes"].str.contains("GAP\\?", na=False)]
    for _, r in gap_rows.iterrows():
        m = re.search(r"GAP\?: moves (\d+) notches from previous row "
                      r"\(([A-Za-z+\-]+) on ([0-9-]+)\)", str(r["notes"]))
        if m:
            targets.append({"country": r["country"], "iso3": r["iso3"],
                            "agency": r["agency"],
                            "rating_type": r["rating_type"],
                            "date_from": m.group(3),
                            "date_to": str(r["action_date"].date()),
                            "reason": f"possible gap: {m.group(1)}-notch "
                                      f"move {m.group(2)} -> {r['rating']}"})

    # (4) FC_LT series starting after 2004, first row not marked new
    for (country, agency), g in v2[v2["rating_type"] == "FC_LT"] \
            .groupby(["country", "agency"]):
        first = g.sort_values("action_date").iloc[0]
        if (first["action_date"].year > 2004
                and first["action"] not in ("new", "initial_state")):
            targets.append({"country": country, "iso3": first["iso3"],
                            "agency": agency, "rating_type": "FC_LT",
                            "date_from": "2004-01-01",
                            "date_to": str(first["action_date"].date()),
                            "reason": "FC_LT history starts "
                                      f"{first['action_date'].date()} with "
                                      f"action '{first['action']}' -- "
                                      "earlier FC history missing"})

    # (5) the two known cross-collection problems
    targets.append({"country": "Nigeria", "iso3": "NGA", "agency": "Moodys",
                    "rating_type": "FC_LT", "date_from": "2019-12-01",
                    "date_to": "2019-12-04",
                    "reason": "cross-collection disagreement: old panel "
                              "(GE, month-precision) B3 vs v2 (fxempire) "
                              "B2 -- needs primary-source check"})
    targets.append({"country": "Sri Lanka", "iso3": "LKA", "agency": "SP",
                    "rating_type": "FC_LT", "date_from": "2007-01-23",
                    "date_to": "2007-01-23",
                    "reason": "known countryeconomy transcription error: "
                              "A should be B+ (corrected in old panel via "
                              "_corrections.csv)"})

    # (6) undated latest-rating rows as hints
    excl = pd.read_csv(V2_DIR / "excluded_source_rows.csv")
    undated = excl[excl["reason"].str.startswith("undated row")]
    for _, r in undated.iterrows():
        targets.append({"country": iso3_to_country.get(r["iso3"], ""),
                        "iso3": r["iso3"], "agency": r["agency"],
                        "rating_type": r["type"], "date_from": "",
                        "date_to": "",
                        "reason": "hint: source shows undated latest "
                                  f"rating '{r['rating_raw']}' -- the "
                                  "missing action likely ends there"})

    tdf = pd.DataFrame(targets)

    # n_events_affected under rule (iii): rule-(iii)-excluded events of the
    # same country whose event quarter or 4-quarter lookback overlaps the
    # target span (dateless hint rows get 0).
    excluded = events[~events["survives_rule_any"]]
    n_aff = []
    for _, t in tdf.iterrows():
        if not t["date_from"]:
            n_aff.append(0)
            continue
        d_from = pd.Timestamp(t["date_from"])
        d_to = pd.Timestamp(t["date_to"])
        g = excluded[excluded["country"] == t["country"]]
        n = 0
        for _, ev in g.iterrows():
            lb_start = (ev["quarter"] - 4).start_time
            ev_end = ev["quarter"].end_time
            if (lb_start <= d_to) and (ev_end >= d_from):
                n += 1
        n_aff.append(n)
    tdf["n_events_affected"] = n_aff
    tdf["priority"] = tdf["n_events_affected"] \
        .rank(method="dense", ascending=False).astype(int)
    tdf = tdf.sort_values(["priority", "country", "agency"]) \
             .reset_index(drop=True)
    tdf.to_csv(OUT_DIR / "second_pass_targets.csv", index=False)
    return tdf


def main():
    v2 = load_v2()
    b = sp_currency_tests(v2)
    passing = b["passing_countries"]
    lookup = year_status_lookup(v2, passing)
    events = rebuild_events(v2, passing)

    by_year, events = event_survival(events, lookup)
    tot = {
        "collapsed_no_rule": len(events),
        "initial_no_rule": int(events["initial_downgrade"].sum()),
        "collapsed_rule_agency": int(events["survives_rule_agency"].sum()),
        "initial_rule_agency": int((events["survives_rule_agency"]
                                    & events["initial_downgrade"]).sum()),
        "collapsed_rule_any": int(events["survives_rule_any"].sum()),
        "initial_rule_any": int((events["survives_rule_any"]
                                 & events["initial_downgrade"]).sum()),
    }
    print("event survival totals:", tot)
    for rule, mask in (
            ("no_rule", events["initial_downgrade"]),
            ("rule_agency", events["survives_rule_agency"]
                            & events["initial_downgrade"]),
            ("rule_any", events["survives_rule_any"]
                         & events["initial_downgrade"])):
        n = events.loc[mask, "country"].nunique()
        print(f"countries with >=1 surviving initial event, {rule}: {n}")

    tdf = second_pass_targets(v2, events)
    print(f"second_pass_targets.csv: {len(tdf)} rows; by reason class:")
    print(tdf["reason"].str.split(":").str[0].value_counts().to_string())
    print("top priorities:")
    print(tdf[tdf["priority"] <= 3][["country", "agency", "date_from",
                                     "date_to", "n_events_affected",
                                     "priority"]].head(12).to_string(
                                         index=False))


if __name__ == "__main__":
    main()
