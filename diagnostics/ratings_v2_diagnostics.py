"""Intake diagnostics for the independent ratings collection in
data/raw/ratings_v2/ (2026-11-15) -- diagnostics ONLY, per the scope
decision in docs/stage1_h1_preregistration.md (v0.3): the collection is
NOT merged into data/processed/ratings_panel.csv, no Stage 1 labels are
regenerated, and no lead/lag outcome is computed here.

Five diagnostics, outputs to data/diagnostics/ratings/:

(a) Sanity checks, mirroring src/data_acquisition/sanity_check_ratings.py's
    source-agnostic designs on the v2 collection: implausible jumps
    (> 4 notches between consecutive actions of one country+agency+
    rating_type series), MAD-based range outliers (modified z > 3.5 per
    country against its full multi-agency FC_LT history), and
    single-source exposure (v2's own n_independent_sources column).

(b) The two pre-registration section 5.1 tests for S&P
    currency-unspecified rows (tradingeconomics does not state FC/LC):
    - Source test: among S&P actions where the labelled FC_LT and LC_LT
      ratings differ on the same date, how many tradingeconomics-backed
      rows carry the FC rating vs the LC rating (overall + per country).
    - Continuity test: per country, the last unspecified S&P rating
      before the first FC_LT-labelled row vs that row -- consistent if
      equal, or if the FC row is a recorded change computed against that
      exact unspecified rating (the collector's own note), else
      inconsistent.
    Also reports how many (country, date) pairs carry BOTH an
    unspecified and an FC_LT S&P row -- the sample the superseded
    same-date overlap test would have had.

(c) Comparison with the existing 13-country reconciled panel
    (data/processed/ratings_panel.csv): v2 FC_LT rows matched on
    country + agency + rating with dates within 3 days (exact-date and
    1-3-day matches reported separately); disagreements = same
    country+agency within 3 days, different rating. Matched rows resting
    on countryeconomy in BOTH collections are flagged as
    not-independent confirmations.

(d) Gap map: per country x agency x calendar year 2004-2025, FC_LT
    coverage complete / partial / missing, built twice -- (i) FC_LT rows
    only, (ii) FC_LT plus S&P unspecified rows for countries passing
    both section 5.1 tests. Partial = year intersects a multi-notch
    (>= 3) jump between consecutive rows (the collector's own
    possible-gap rule) or falls after a documented stale-table cutoff
    ("no action found after ..." in unresolved.md); missing = before the
    series' first knowable rating. Cells that are not complete block
    downgrade-event detection under pre-registration section 5.1 (an
    event needs its preceding 4 quarters outside documented gaps).

(e) Downgrade-event counts (counts only, NO risk scores): downgrade =
    increase in rating_numeric (worse) between consecutive actions of a
    country+agency FC_LT series, pooled across agencies, collapsed to
    at most one event per country-quarter at the earliest date
    (pre-registration section 5.2); initial downgrades = no collapsed
    event in the preceding 4 quarters. Built for the same two row sets
    as (d).

Run: python3 diagnostics/ratings_v2_diagnostics.py
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "data_acquisition"))
from ingest_ratings import RATING_MAP  # noqa: E402  (shared ordinal scale)

V2_DIR = REPO_ROOT / "data" / "raw" / "ratings_v2"
OUT_DIR = REPO_ROOT / "data" / "diagnostics" / "ratings"
OLD_PANEL = REPO_ROOT / "data" / "processed" / "ratings_panel.csv"

JUMP_NOTCH_THRESHOLD = 4          # same as sanity_check_ratings.py
RANGE_OUTLIER_Z = 3.5             # same as sanity_check_ratings.py
POSSIBLE_GAP_NOTCHES = 3          # the collector's own "GAP?" rule
SOURCE_TEST_PASS_SHARE = 0.95     # pre-registration section 5.1
YEARS = range(2004, 2026)

AGENCY_MAP = {"SP": "S&P", "Moodys": "Moody's", "Fitch": "Fitch"}


def load_v2() -> pd.DataFrame:
    df = pd.read_csv(V2_DIR / "ratings_history.csv")
    df["action_date"] = pd.to_datetime(df["action_date"])
    df = df[df["action_date"] <= "2025-12-31"].copy()
    df["rating_numeric"] = df["rating"].map(RATING_MAP)
    unmapped = df[df["rating_numeric"].isna()]
    if len(unmapped):
        print(f"WARNING: {len(unmapped)} rows with unmappable ratings "
              f"(excluded from numeric checks): "
              f"{sorted(unmapped['rating'].unique())}")
    df["sources_list"] = df["notes"].str.extract(r"sources: ([^;]+)$")[0]
    df["sources_set"] = df["sources_list"].fillna("").apply(
        lambda s: frozenset(x.strip() for x in s.split(",") if x.strip()))
    return df


# ---------------------------------------------------------------- (a) sanity
def sanity_checks(v2: pd.DataFrame) -> dict:
    jumps = []
    for (country, agency, rtype), g in v2.dropna(subset=["rating_numeric"]) \
            .groupby(["country", "agency", "rating_type"], sort=False):
        g = g.sort_values("action_date")
        prev = None
        for _, row in g.iterrows():
            if prev is not None:
                notches = row["rating_numeric"] - prev["rating_numeric"]
                if abs(notches) > JUMP_NOTCH_THRESHOLD:
                    jumps.append({
                        "country": country, "agency": agency,
                        "rating_type": rtype,
                        "from_date": prev["action_date"].date(),
                        "from_rating": prev["rating"],
                        "to_date": row["action_date"].date(),
                        "to_rating": row["rating"],
                        "notches": int(notches),
                        "flagged_by_collector": "GAP?" in str(row["notes"]),
                    })
            prev = row
    jumps_df = pd.DataFrame(jumps)

    outliers = []
    fc = v2[(v2["rating_type"] == "FC_LT")].dropna(subset=["rating_numeric"])
    for country, g in fc.groupby("country", sort=False):
        x = g["rating_numeric"].astype(float)
        med = x.median()
        mad = (x - med).abs().median()
        if mad == 0:
            continue
        z = 0.6745 * (x - med) / mad
        for idx in g.index[z.abs() > RANGE_OUTLIER_Z]:
            outliers.append({
                "country": country, "agency": g.loc[idx, "agency"],
                "date": g.loc[idx, "action_date"].date(),
                "rating": g.loc[idx, "rating"],
                "rating_numeric": int(g.loc[idx, "rating_numeric"]),
                "country_median_numeric": med,
                "modified_z": round(float(z.loc[idx]), 2),
            })
    outliers_df = pd.DataFrame(outliers)

    ss = (v2.assign(single=v2["n_independent_sources"] == 1)
            .groupby(["country", "agency", "rating_type"])
            .agg(n_rows=("single", "size"), n_single_source=("single", "sum"))
            .reset_index())
    ss["single_source_share"] = (ss["n_single_source"] / ss["n_rows"]).round(3)

    jumps_df.to_csv(OUT_DIR / "ratings_v2_sanity_jumps.csv", index=False)
    outliers_df.to_csv(OUT_DIR / "ratings_v2_sanity_range_outliers.csv",
                       index=False)
    ss.to_csv(OUT_DIR / "ratings_v2_single_source.csv", index=False)
    return {"jumps": jumps_df, "outliers": outliers_df, "single_source": ss}


# ------------------------------------------- (b) section 5.1 currency tests
def sp_currency_tests(v2: pd.DataFrame) -> dict:
    sp = v2[v2["agency"] == "SP"]
    fc = sp[sp["rating_type"] == "FC_LT"]
    lc = sp[sp["rating_type"] == "LC_LT"]
    unspec = sp[sp["rating_type"] == "unspecified"]

    # Source test: dates where FC and LC rows both exist and ratings differ.
    merged = fc.merge(lc, on=["country", "action_date"],
                      suffixes=("_fc", "_lc"))
    diff = merged[merged["rating_fc"] != merged["rating_lc"]]
    rows = []
    for _, m in diff.iterrows():
        for side in ("fc", "lc"):
            if "tradingeconomics" in m[f"sources_set_{side}"]:
                rows.append({
                    "country": m["country"], "date": m["action_date"].date(),
                    "te_backed_row_type": side.upper() + "_LT",
                    "te_row_rating": m[f"rating_{side}"],
                    "fc_rating": m["rating_fc"], "lc_rating": m["rating_lc"],
                    "carries": "FC" if m[f"rating_{side}"] == m["rating_fc"]
                               else "LC",
                })
    src_df = pd.DataFrame(rows)
    if len(src_df):
        per_country = (src_df.groupby("country")["carries"]
                       .value_counts().unstack(fill_value=0)
                       .reindex(columns=["FC", "LC"], fill_value=0)
                       .reset_index())
    else:
        per_country = pd.DataFrame(columns=["country", "FC", "LC"])
    n_fc_carry = int((src_df["carries"] == "FC").sum()) if len(src_df) else 0
    n_total = len(src_df)
    source_share = n_fc_carry / n_total if n_total else float("nan")
    source_test_pass = (n_total == 0) or (source_share >= SOURCE_TEST_PASS_SHARE)

    # Continuity test, per country.
    cont = []
    for country, g in sp.groupby("country", sort=False):
        g_fc = g[g["rating_type"] == "FC_LT"].sort_values("action_date")
        g_un = g[g["rating_type"] == "unspecified"].sort_values("action_date")
        if g_un.empty:
            continue
        if g_fc.empty:
            cont.append({"country": country, "verdict": "no_fc_rows"})
            continue
        first_fc = g_fc.iloc[0]
        before = g_un[g_un["action_date"] < first_fc["action_date"]]
        if before.empty:
            cont.append({
                "country": country, "verdict": "no_unspecified_before_fc",
                "first_fc_date": first_fc["action_date"].date(),
                "first_fc_rating": first_fc["rating"]})
            continue
        last_un = before.iloc[-1]
        m = re.search(r"action computed against currency-unspecified row "
                      r"([A-Za-z+\-]+) dated ([0-9-]+)",
                      str(first_fc["notes"]))
        if last_un["rating"] == first_fc["rating"]:
            verdict = "consistent_equal"
        elif m and m.group(1) == last_un["rating"]:
            verdict = "consistent_recorded_change"
        else:
            verdict = "inconsistent"
        cont.append({
            "country": country,
            "last_unspec_date": last_un["action_date"].date(),
            "last_unspec_rating": last_un["rating"],
            "first_fc_date": first_fc["action_date"].date(),
            "first_fc_rating": first_fc["rating"],
            "verdict": verdict,
        })
    cont_df = pd.DataFrame(cont)

    # Sample size the superseded same-date overlap test would have had.
    overlap = unspec.merge(fc, on=["country", "action_date"],
                           suffixes=("_un", "_fc"))
    n_overlap_pairs = len(overlap)

    passing = set()
    if source_test_pass:
        ok = {"consistent_equal", "consistent_recorded_change",
              "no_unspecified_before_fc"}
        passing = set(cont_df.loc[cont_df["verdict"].isin(ok), "country"])

    src_df.to_csv(OUT_DIR / "ratings_v2_sp_source_test_rows.csv", index=False)
    per_country.to_csv(OUT_DIR / "ratings_v2_sp_source_test_by_country.csv",
                       index=False)
    cont_df.to_csv(OUT_DIR / "ratings_v2_sp_continuity_test.csv", index=False)
    return {"source_rows": src_df, "source_by_country": per_country,
            "source_share": source_share, "source_test_pass": source_test_pass,
            "n_te_rows": n_total, "n_te_fc": n_fc_carry,
            "continuity": cont_df, "n_overlap_pairs": n_overlap_pairs,
            "passing_countries": passing}


# ------------------------------------------------- (c) old-panel comparison
def compare_with_panel(v2: pd.DataFrame) -> dict:
    old = pd.read_csv(OLD_PANEL)
    old["date"] = pd.to_datetime(old["date"])
    old["country_norm"] = old["country"].str.replace("_", " ")
    countries = sorted(old["country_norm"].unique())
    v2fc = v2[(v2["rating_type"] == "FC_LT")
              & (v2["country"].isin(countries))].copy()
    v2fc["agency_norm"] = v2fc["agency"].map(AGENCY_MAP)

    matched, disagreements = [], []
    used_v2 = set()
    old_only_idx = []
    for (country, agency), g_old in old.groupby(["country_norm", "agency"]):
        g_v2 = v2fc[(v2fc["country"] == country)
                    & (v2fc["agency_norm"] == agency)]
        for oi, orow in g_old.sort_values("date").iterrows():
            cand = g_v2[(~g_v2.index.isin(used_v2))
                        & ((g_v2["action_date"] - orow["date"]).abs()
                           <= pd.Timedelta(days=3))]
            same = cand[cand["rating"] == orow["rating"]]
            pick, kind = None, None
            if len(same):
                exact = same[same["action_date"] == orow["date"]]
                pick = (exact if len(exact) else same).iloc[0]
                kind = ("matched_exact" if len(exact) else "matched_1_3d")
            elif len(cand):
                pick, kind = cand.iloc[0], "disagreement"
            if pick is None:
                old_only_idx.append(oi)
                continue
            used_v2.add(pick.name)
            rec = {
                "country": country, "agency": agency,
                "old_date": orow["date"].date(), "old_rating": orow["rating"],
                "v2_date": pick["action_date"].date(),
                "v2_rating": pick["rating"],
                "date_diff_days": int(abs((pick["action_date"]
                                           - orow["date"]).days)),
                "old_source": orow["source"],
                "v2_sources": ",".join(sorted(pick["sources_set"])),
                "both_rest_on_countryeconomy": (
                    "countryeconomy" in str(orow["source"])
                    and pick["sources_set"] <= {"countryeconomy"}),
            }
            if kind == "disagreement":
                disagreements.append(rec)
            else:
                rec["match_kind"] = kind
                matched.append(rec)

    matched_df = pd.DataFrame(matched)
    dis_df = pd.DataFrame(disagreements)
    old_only = old.loc[old_only_idx,
                       ["country_norm", "agency", "date", "rating", "outlook",
                        "action", "source"]].rename(
                            columns={"country_norm": "country"})
    v2_only = v2fc[~v2fc.index.isin(used_v2)][
        ["country", "agency_norm", "action_date", "rating", "outlook",
         "action", "n_independent_sources"]].rename(
            columns={"agency_norm": "agency"})

    matched_df.to_csv(OUT_DIR / "ratings_v2_vs_panel_matched.csv", index=False)
    dis_df.to_csv(OUT_DIR / "ratings_v2_vs_panel_disagreements.csv",
                  index=False)
    old_only.to_csv(OUT_DIR / "ratings_v2_vs_panel_old_only.csv", index=False)
    v2_only.to_csv(OUT_DIR / "ratings_v2_vs_panel_v2_only.csv", index=False)
    return {"matched": matched_df, "disagreements": dis_df,
            "old_only": old_only, "v2_only": v2_only,
            "n_old": len(old), "n_v2": len(v2fc)}


# ------------------------------------------------------------- (d) gap map
def parse_stale_cutoffs() -> dict:
    """(iso3, agency, rating_type) -> stale-after date, from unresolved.md."""
    text = (V2_DIR / "unresolved.md").read_text()
    cutoffs = {}
    iso3 = None
    for line in text.splitlines():
        m = re.match(r"### .+ \(([A-Z]{3})\)", line)
        if m:
            iso3 = m.group(1)
            continue
        m = re.match(r"- \*\*(\w+) (FC_LT|LC_LT|unspecified)\*\*", line)
        if m and iso3 and "no action found after" in line:
            d = re.search(r"no action found after ([0-9-]+)", line)
            cutoffs[(iso3, m.group(1), m.group(2))] = pd.Timestamp(d.group(1))
    return cutoffs


def build_series(v2: pd.DataFrame, passing: set, augmented: bool) -> dict:
    """(country, agency) -> chronological FC_LT (+ passing unspecified) df."""
    out = {}
    for (country, agency), g in v2.groupby(["country", "agency"], sort=False):
        keep = g["rating_type"] == "FC_LT"
        if augmented and agency == "SP" and country in passing:
            keep |= g["rating_type"] == "unspecified"
        s = g[keep].dropna(subset=["rating_numeric"]) \
                   .sort_values("action_date")
        if len(s):
            out[(country, agency)] = s
    return out


def gap_map(v2: pd.DataFrame, passing: set) -> dict:
    cutoffs = parse_stale_cutoffs()
    variants = {"fc_only": build_series(v2, passing, augmented=False),
                "fc_plus_unspec": build_series(v2, passing, augmented=True)}
    records = {}
    for name, series in variants.items():
        for (country, agency), s in series.items():
            iso3 = s["iso3"].iloc[0]
            start = s["action_date"].iloc[0]
            stale = cutoffs.get((iso3, agency, "FC_LT"))
            gap_years = set()
            dates = s["action_date"].tolist()
            nums = s["rating_numeric"].tolist()
            for i in range(1, len(s)):
                if abs(nums[i] - nums[i - 1]) >= POSSIBLE_GAP_NOTCHES:
                    gap_years.update(range(dates[i - 1].year,
                                           dates[i].year + 1))
            for year in YEARS:
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
                records.setdefault((country, agency, year), {})[name] = status
    rows = [{"country": c, "agency": a, "year": y,
             "status_fc_only": v.get("fc_only", "missing"),
             "status_fc_plus_unspec": v.get("fc_plus_unspec", "missing")}
            for (c, a, y), v in sorted(records.items())]
    gm = pd.DataFrame(rows)
    blocking = gm[(gm["status_fc_only"] != "complete")
                  | (gm["status_fc_plus_unspec"] != "complete")]
    gm.to_csv(OUT_DIR / "ratings_v2_gap_map.csv", index=False)
    blocking.to_csv(OUT_DIR / "ratings_v2_gap_blocking_cells.csv", index=False)
    return {"gap_map": gm, "blocking": blocking}


# ------------------------------------------------------- (e) event counts
def event_counts(v2: pd.DataFrame, passing: set) -> dict:
    results = {}
    for name, augmented in (("fc_only", False), ("fc_plus_unspec", True)):
        series = build_series(v2, passing, augmented=augmented)
        events = []
        for (country, agency), s in series.items():
            dates = s["action_date"].tolist()
            nums = s["rating_numeric"].tolist()
            ratings = s["rating"].tolist()
            for i in range(1, len(s)):
                if nums[i] > nums[i - 1]:  # numerically worse = downgrade
                    events.append({"country": country, "agency": agency,
                                   "date": dates[i],
                                   "from_rating": ratings[i - 1],
                                   "to_rating": ratings[i]})
        ev = pd.DataFrame(events)
        if len(ev):
            ev["quarter"] = ev["date"].dt.to_period("Q")
            collapsed = (ev.sort_values("date")
                           .groupby(["country", "quarter"], as_index=False)
                           .first())
            collapsed = collapsed.sort_values(["country", "date"])
            initial_flags = []
            for country, g in collapsed.groupby("country"):
                prev_q = None
                for _, row in g.iterrows():
                    q = row["quarter"]
                    initial_flags.append(prev_q is None
                                         or (q - prev_q).n > 4)
                    prev_q = q
            collapsed["initial_downgrade"] = initial_flags
        else:
            collapsed = pd.DataFrame(columns=["country", "quarter", "date",
                                              "agency", "from_rating",
                                              "to_rating",
                                              "initial_downgrade"])
        collapsed.to_csv(OUT_DIR / f"ratings_v2_events_{name}.csv",
                         index=False)
        results[name] = collapsed

    counts = []
    for country in sorted(v2["country"].unique()):
        row = {"country": country}
        for name, collapsed in results.items():
            g = collapsed[collapsed["country"] == country]
            row[f"n_collapsed_{name}"] = len(g)
            row[f"n_initial_{name}"] = int(g["initial_downgrade"].sum()) \
                if len(g) else 0
        counts.append(row)
    counts_df = pd.DataFrame(counts)
    counts_df.to_csv(OUT_DIR / "ratings_v2_event_counts.csv", index=False)
    return {"events": results, "counts": counts_df}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    v2 = load_v2()
    print(f"ratings_v2: {len(v2)} rows, {v2['country'].nunique()} countries")

    a = sanity_checks(v2)
    print(f"(a) jumps > {JUMP_NOTCH_THRESHOLD} notches: {len(a['jumps'])}"
          f" | range outliers: {len(a['outliers'])}"
          f" | single-source rows: "
          f"{int(a['single_source']['n_single_source'].sum())}"
          f"/{int(a['single_source']['n_rows'].sum())}")

    b = sp_currency_tests(v2)
    print(f"(b) source test: {b['n_te_fc']}/{b['n_te_rows']} TE-backed rows "
          f"carry the FC rating (share={b['source_share']:.3f}, "
          f"pass={b['source_test_pass']}); superseded same-date overlap "
          f"sample: {b['n_overlap_pairs']} pairs")
    vc = b["continuity"]["verdict"].value_counts().to_dict() \
        if len(b["continuity"]) else {}
    print(f"    continuity verdicts: {vc}")
    print(f"    countries passing both tests: {len(b['passing_countries'])}")

    c = compare_with_panel(v2)
    mk = c["matched"]["match_kind"].value_counts().to_dict() \
        if len(c["matched"]) else {}
    print(f"(c) old panel {c['n_old']} rows vs v2 FC_LT {c['n_v2']} rows: "
          f"matched {len(c['matched'])} ({mk}), "
          f"disagreements {len(c['disagreements'])}, "
          f"old-only {len(c['old_only'])}, v2-only {len(c['v2_only'])}; "
          f"not-independent (countryeconomy both sides): "
          f"{int(c['matched']['both_rest_on_countryeconomy'].sum()) if len(c['matched']) else 0}")

    d = gap_map(v2, b["passing_countries"])
    for col in ("status_fc_only", "status_fc_plus_unspec"):
        s = d["gap_map"][col].value_counts().to_dict()
        print(f"(d) {col}: {s}")
    print(f"    blocking cells (either variant not complete): "
          f"{len(d['blocking'])}")

    e = event_counts(v2, b["passing_countries"])
    for name, collapsed in e["events"].items():
        print(f"(e) {name}: {len(collapsed)} collapsed country-quarter "
              f"downgrades, {int(collapsed['initial_downgrade'].sum()) if len(collapsed) else 0} initial")

    return a, b, c, d, e


if __name__ == "__main__":
    main()
