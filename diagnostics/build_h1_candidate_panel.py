"""Build the CANDIDATE H1 ratings panel (NOT FROZEN).

Implements the panel definition of docs/stage1_h1_preregistration.md v0.4
section 5.1: ratings_v2 FC_LT rows plus qualifying S&P "unspecified" rows,
with the corrections file applied and the verified second-pass actions
added. Output: data/interim/ratings_h1_candidate.csv (status column
CANDIDATE_NOT_FROZEN on every row). Freezing is a later dated commit
(pre-registration section 6); no outcome is computed here.

Inputs (never edited):
  data/raw/ratings_v2/ratings_history.csv            first collection
  data/raw/ratings_v2_second_pass/*                  second pass, stored as received
  data/interim/_corrections_v2.csv                   corrections (tracked)

Rules implemented:
  * corrections: remove_row / correct_date / correct_rating, each must match
    exactly one v2 row (fail loudly otherwise);
  * second-pass rows: LC_LT dropped (LC is descriptive only), rows after
    2025-12-31 dropped;
  * dedupe: key (iso3, agency, action_date); for S&P FC_LT and unspecified
    rows share one key. Same rating -> one row labelled FC_LT, all sources
    listed. Different rating -> conflict, listed; the second-pass row wins
    when its source_type is agency/official and that choice must already be
    a correct_rating row in the corrections file (else this script stops);
  * same rating within 3 days -> listed as probable duplicates, not merged;
  * unspecified S&P rows are kept only for countries passing the two
    pre-registration section 5.1 tests (source test, continuity test), run
    on the corrected first-collection frame;
  * S&P rating in force on 2004-01-01 (stated in the second-pass
    resolution file) is added as an initial_state anchor when the series
    has nothing at or before that date.

Run: python3 diagnostics/build_h1_candidate_panel.py
"""

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "diagnostics"))
import ratings_v2_diagnostics as rv2  # noqa: E402

RATING_MAP = rv2.RATING_MAP
SP_DIR = REPO_ROOT / "data" / "raw" / "ratings_v2_second_pass"
INTERIM = REPO_ROOT / "data" / "interim"
CORR_PATH = INTERIM / "_corrections_v2.csv"
PANEL_PATH = INTERIM / "ratings_h1_candidate.csv"
DIAG_DIR = REPO_ROOT / "data" / "diagnostics" / "ratings" / "second_pass"
END = pd.Timestamp("2025-12-31")
ANCHOR_DATE = pd.Timestamp("2004-01-01")
NEAR_DUP_DAYS = 3

OUTLOOK_MAP = {"stable": "stable", "positive": "positive",
               "negative": "negative", "watch neg": "watch_neg",
               "rating watch negative": "watch_neg",
               "developing": "developing", "": np.nan}
ACTION_MAP = {"downgrade": "downgrade", "upgrade": "upgrade",
              "outlook_change": "outlook_change",
              "watch_placement": "watch", "initial_rating": "new"}
STRONG = {"agency", "official"}


# ------------------------------------------------------------ corrections
def load_corrections() -> pd.DataFrame:
    c = pd.read_csv(CORR_PATH, dtype=str, keep_default_na=False)
    need = {"iso3", "agency", "rating_type", "action_date", "correction_type",
            "field", "wrong_value", "corrected_value", "evidence_url", "note"}
    if need - set(c.columns):
        raise ValueError(f"{CORR_PATH}: missing columns {need - set(c.columns)}")
    if (c["evidence_url"] == "").any():
        raise ValueError("every correction needs an evidence_url")
    return c


def apply_corrections(v2: pd.DataFrame, corr: pd.DataFrame):
    v2 = v2.copy()
    removed, log = [], []
    for _, c in corr.iterrows():
        d = pd.Timestamp(c["action_date"])
        m = ((v2["iso3"] == c["iso3"]) & (v2["agency"] == c["agency"])
             & (v2["rating_type"] == c["rating_type"])
             & (v2["action_date"] == d))
        if c["correction_type"] in ("remove_row", "correct_rating"):
            m &= v2["rating"] == c["wrong_value"]
        elif c["correction_type"] == "correct_date":
            if c["wrong_value"] != str(d.date()):
                raise ValueError(f"correct_date wrong_value != action_date: {dict(c)}")
        else:
            raise ValueError(f"unknown correction_type {c['correction_type']}")
        if m.sum() != 1:
            raise ValueError(f"correction matched {int(m.sum())} rows "
                             f"(stale or mistyped entry): {dict(c)}")
        if c["correction_type"] == "remove_row":
            removed.append(v2[m].assign(correction_note=c["note"]))
            v2 = v2[~m]
        elif c["correction_type"] == "correct_date":
            v2.loc[m, "action_date"] = pd.Timestamp(c["corrected_value"])
        else:
            v2.loc[m, "rating"] = c["corrected_value"]
            v2.loc[m, "rating_numeric"] = RATING_MAP[c["corrected_value"]]
        log.append({**c.to_dict(), "matched": 1})
    removed = pd.concat(removed) if removed else v2.iloc[0:0]
    return v2, removed, pd.DataFrame(log)


# ------------------------------------------------------------ second pass
def load_second_pass():
    a = pd.read_csv(SP_DIR / "second_pass_actions.csv", dtype=str,
                    keep_default_na=False)
    stats = {"rows_in_file": len(a)}
    a["action_date"] = a["action_date"].apply(pd.Timestamp)
    a["outlook_n"] = a["outlook"].str.lower().map(OUTLOOK_MAP)
    bad = a[a["outlook"].str.lower().map(lambda x: x not in OUTLOOK_MAP)]
    if len(bad):
        raise ValueError(f"unmapped outlook values: {bad['outlook'].unique()}")
    a["action_n"] = a["action"].map(ACTION_MAP)
    if a["action_n"].isna().any():
        raise ValueError(f"unmapped actions: {a.loc[a['action_n'].isna(), 'action'].unique()}")
    unk = set(a["rating"]) - set(RATING_MAP)
    if unk:
        raise ValueError(f"ratings not in RATING_MAP: {unk}")
    stats["dropped_LC_LT"] = int((a["rating_type"] == "LC_LT").sum())
    a = a[a["rating_type"] != "LC_LT"]
    stats["dropped_after_2025_12_31"] = int((a["action_date"] > END).sum())
    a = a[a["action_date"] <= END]
    # same action may be listed once per target row; identical rows collapse
    n = len(a)
    a = a.drop_duplicates(["iso3", "agency", "action_date", "rating"])
    stats["identical_rows_collapsed"] = n - len(a)
    stats["kept_FC_rows"] = len(a)
    return a.reset_index(drop=True), stats


ANCH1 = re.compile(r"[Ii]n force (?:on )?2004-01-01(?::| was) "
                   r"([A-Za-z][A-Za-z0-9+\-]*)/(\w+)")
ANCH2 = re.compile(r"\b([A-Z]{1,3}[+\-]?)/(Stable|Positive|Negative)\w* "
                   r"since (\d{4}-\d{2}-\d{2})")


def load_anchors() -> pd.DataFrame:
    r = pd.read_csv(SP_DIR / "second_pass_resolution.csv", dtype=str,
                    keep_default_na=False)
    rows = []
    for _, x in r.iterrows():
        if x["agency"] != "SP" or x["status"] != "resolved_actions_found":
            continue
        m = ANCH1.search(x["explanation"])
        since = ""
        if m:
            s = re.search(r"\(since (\d{4}-\d{2}-\d{2})\)", x["explanation"])
            since = s.group(1) if s else ""
        else:
            m = ANCH2.search(x["explanation"])
            if m:
                since = m.group(3)
        if not m:
            continue
        rating = m.group(1)
        if rating not in RATING_MAP:
            raise ValueError(f"anchor rating {rating} not in RATING_MAP (row {x['target_row']})")
        rows.append({"iso3": x["iso3"], "country": x["country"],
                     "rating": rating,
                     "outlook_n": OUTLOOK_MAP[m.group(2).lower()],
                     "since": since, "target_row": x["target_row"],
                     "url": x["evidence_urls"].split(" | ")[0]})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ merge
def _domains(*urls):
    return {urlparse(u).netloc.lower().removeprefix("www.")
            for u in urls if u}


def build_union(v2c: pd.DataFrame, sp: pd.DataFrame) -> pd.DataFrame:
    keep = (v2c["rating_type"] == "FC_LT") | \
           ((v2c["agency"] == "SP") & (v2c["rating_type"] == "unspecified"))
    a = v2c[keep]
    u1 = pd.DataFrame({
        "country": a["country"], "iso3": a["iso3"], "agency": a["agency"],
        "orig_rating_type": a["rating_type"], "action_date": a["action_date"],
        "rating": a["rating"], "outlook": a["outlook"], "action": a["action"],
        "urls": [[x for x in (p, q) if isinstance(x, str) and x]
                 for p, q in zip(a["source_url_1"], a["source_url_2"])],
        "n_src": a["n_independent_sources"].astype(float),
        "evidence": "aggregator", "prov": "v2",
        "date_precision": a["date_precision"], "notes": ""})
    u2 = pd.DataFrame({
        "country": sp["country"], "iso3": sp["iso3"], "agency": sp["agency"],
        "orig_rating_type": sp["rating_type"],
        "action_date": sp["action_date"], "rating": sp["rating"],
        "outlook": sp["outlook_n"], "action": sp["action_n"],
        "urls": [[x for x in (p, q) if x]
                 for p, q in zip(sp["source_url_1"], sp["source_url_2"])],
        "n_src": [float(len(_domains(p, q)))
                  for p, q in zip(sp["source_url_1"], sp["source_url_2"])],
        "evidence": sp["source_type"], "prov": "second_pass",
        "date_precision": sp["date_precision"], "notes": sp["notes"]})
    return pd.concat([u1, u2], ignore_index=True)


def merge_groups(U: pd.DataFrame, passing: set):
    out, conflicts, dropped_unspec = [], [], 0
    for (iso3, agency, d), g in U.groupby(["iso3", "agency", "action_date"],
                                          sort=False):
        spr = g[g["prov"] == "second_pass"]
        v2r = g[g["prov"] == "v2"]
        conflict = False
        if g["rating"].nunique() > 1:
            conflict = True
            strong = spr[spr["evidence"].isin(STRONG)]
            if len(strong) and len(v2r):
                status = "NEEDS_CORRECT_RATING_ROW"
                chosen = strong.iloc[0]
            elif len(strong):
                status = "second_pass_internal_conflict"
                chosen = strong.iloc[0]
            elif len(spr):
                status = "kept_v2_second_pass_is_news"
                chosen = v2r.iloc[0]
            else:
                # conflict inside the first collection (FC_LT vs unspecified
                # label on one date): keep the explicitly FC_LT-labelled row
                status = "v2_internal_kept_FC_LT_label"
                fcl = v2r[v2r["orig_rating_type"] == "FC_LT"]
                chosen = (fcl if len(fcl) else v2r).iloc[0]
            conflicts.append({
                "iso3": iso3, "country": g["country"].iloc[0],
                "agency": agency, "action_date": d.date(),
                "v2_rating": "|".join(sorted(v2r["rating"].unique())),
                "v2_types": "|".join(sorted(v2r["orig_rating_type"].unique())),
                "second_pass_rating": "|".join(sorted(spr["rating"].unique())),
                "second_pass_source_type": "|".join(sorted(spr["evidence"].unique())),
                "resolution": status})
        else:
            chosen = (spr if len(spr) else v2r).iloc[0]
        # unspecified-only rows need the country to qualify
        if (not len(spr) and (v2r["orig_rating_type"] == "unspecified").all()
                and g["country"].iloc[0] not in passing):  # passing = names
            dropped_unspec += 1
            continue
        # S&P rows keep their own outlook, second pass preferred
        urls = []
        for lst in list(spr["urls"]) + list(v2r["urls"]):
            urls += [x for x in lst if x not in urls]
        nsrc = (spr["n_src"].sum() if len(spr) else 0) + \
               (v2r["n_src"].max() if len(v2r) else 0)
        ev_rank = {"agency": 0, "official": 1, "news": 2, "aggregator": 3}
        best = min(g["evidence"], key=lambda e: ev_rank.get(e, 9))
        out.append({
            "country": g["country"].iloc[0], "iso3": iso3, "agency": agency,
            "rating_type": "FC_LT", "action_date": d, "rating": chosen["rating"],
            "outlook": chosen["outlook"], "action": chosen["action"],
            "date_precision": chosen["date_precision"],
            "provenance": "+".join(sorted(g["prov"].unique())),
            "evidence_class": best, "n_sources": int(nsrc),
            "source_urls": " | ".join(urls),
            "orig_rating_type": "|".join(sorted(g["orig_rating_type"].unique())),
            "conflict_flag": conflict,
            "notes": " ; ".join(n for n in spr["notes"] if n)})
    return pd.DataFrame(out), pd.DataFrame(conflicts), dropped_unspec


def near_duplicates(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (iso3, agency), g in panel.sort_values("action_date").groupby(
            ["iso3", "agency"]):
        r = g.reset_index(drop=True)
        for i in range(1, len(r)):
            gap = (r.loc[i, "action_date"] - r.loc[i - 1, "action_date"]).days
            if 0 < gap <= NEAR_DUP_DAYS and r.loc[i, "rating"] == r.loc[i - 1, "rating"]:
                rows.append({"iso3": iso3, "agency": agency,
                             "rating": r.loc[i, "rating"],
                             "date_1": r.loc[i - 1, "action_date"].date(),
                             "date_2": r.loc[i, "action_date"].date(),
                             "gap_days": gap,
                             "prov_1": r.loc[i - 1, "provenance"],
                             "prov_2": r.loc[i, "provenance"]})
    return pd.DataFrame(rows)


def add_anchors(panel: pd.DataFrame, anchors: pd.DataFrame) -> pd.DataFrame:
    new = []
    for _, a in anchors.iterrows():
        s = panel[(panel["iso3"] == a["iso3"]) & (panel["agency"] == "SP")]
        if len(s) and (s["action_date"] <= ANCHOR_DATE).any():
            continue
        new.append({
            "country": a["country"], "iso3": a["iso3"], "agency": "SP",
            "rating_type": "FC_LT", "action_date": ANCHOR_DATE,
            "rating": a["rating"], "outlook": a["outlook_n"],
            "action": "initial_state", "date_precision": "day",
            "provenance": "second_pass_resolution", "evidence_class": "agency",
            "n_sources": 1, "source_urls": a["url"],
            "orig_rating_type": "FC_LT", "conflict_flag": False,
            "notes": f"rating in force on 2004-01-01 per S&P history; "
                     f"in force since {a['since'] or 'n/a'} "
                     f"(resolution row {a['target_row']}); anchor date is the "
                     f"panel window start, not an action date"})
    return pd.concat([panel, pd.DataFrame(new)], ignore_index=True), len(new)


def finalize(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    p["rating_numeric"] = p["rating"].map(RATING_MAP)
    p = p.sort_values(["iso3", "agency", "action_date"]).reset_index(drop=True)
    rec = []
    for _, g in p.groupby(["iso3", "agency"], sort=False):
        prev = None
        for n in g["rating_numeric"]:
            rec.append("first" if prev is None else
                       "downgrade" if n > prev else
                       "upgrade" if n < prev else "no_letter_change")
            prev = n
    p["action_recomputed"] = rec
    p["panel_status"] = "CANDIDATE_NOT_FROZEN"
    cols = ["country", "iso3", "agency", "rating_type", "action_date",
            "rating", "rating_numeric", "outlook", "action",
            "action_recomputed", "date_precision", "provenance",
            "evidence_class", "n_sources", "source_urls", "orig_rating_type",
            "conflict_flag", "panel_status", "notes"]
    return p[cols]


# ---------------------------------------------------- removal neighbours
# Expected rating before / after each removed row, from the second-pass
# evidence (amendment 4). after_min_date: the next action must not be
# earlier than this (None = no constraint).
EXPECTED = {
    ("GRC", "SP", "FC", "2014-12-12"): ("B", "B", None),
    ("PRT", "Fitch", "FC", "2011-10-07"): ("BBB-", "BB+", "2011-11-24"),
    ("PHL", "SP", "LC", "2009-08-17"): ("BB+", None, "2010-11-12"),
    ("LKA", "SP", "FC", "2007-01-23"): ("B+", "B+", "2007-08-08"),
    ("LKA", "SP", "LC", "2007-01-23"): (None, "BB-", "2007-08-08"),
}


def removal_neighbours(removed, v2c, sp_all):
    cls = lambda t: "LC" if t == "LC_LT" else "FC"  # noqa: E731
    a = v2c[["iso3", "agency", "rating_type", "action_date", "rating"]].copy()
    a["src"] = "v2"
    b = sp_all[["iso3", "agency", "rating_type", "action_date", "rating"]].copy()
    b["src"] = "second_pass"
    full = pd.concat([a, b], ignore_index=True)
    full["cls"] = full["rating_type"].map(cls)
    full = full[full["action_date"] <= END]
    rows = []
    for _, r in removed.iterrows():
        c = cls(r["rating_type"])
        d = r["action_date"]
        s = full[(full["iso3"] == r["iso3"]) & (full["agency"] == r["agency"])
                 & (full["cls"] == c)]
        before = s[s["action_date"] < d].sort_values("action_date")
        after = s[s["action_date"] > d].sort_values("action_date")
        bf = before.iloc[-1] if len(before) else None
        af = after.iloc[0] if len(after) else None
        exp = EXPECTED.get((r["iso3"], r["agency"], c, str(d.date())))
        verdict, why = "OK", ""
        if exp is None:
            verdict, why = "NO_EXPECTATION", "no expected neighbours defined"
        else:
            eb, ea, amin = exp
            if eb is None and bf is not None:
                verdict, why = "FAIL", "expected no earlier row"
            if eb is not None and (bf is None or bf["rating"] != eb):
                verdict, why = "FAIL", f"before rating != {eb}"
            if ea is not None and (af is None or af["rating"] != ea):
                verdict, why = "FAIL", f"after rating != {ea}"
            if amin and (af is None or af["action_date"] < pd.Timestamp(amin)):
                verdict, why = "FAIL", f"after row earlier than {amin}"
            if bf is None and verdict == "OK":
                verdict = "FLAG_NO_STARTING_ACTION"
                why = ("series has no row before the removed date; its first "
                       "remaining row is not an initial rating -- flagged, "
                       "not patched")
        rows.append({
            "iso3": r["iso3"], "agency": r["agency"], "class": c,
            "removed_date": d.date(), "removed_rating": r["rating"],
            "before_date": bf["action_date"].date() if bf is not None else "",
            "before_rating": bf["rating"] if bf is not None else "",
            "before_src": bf["src"] if bf is not None else "",
            "after_date": af["action_date"].date() if af is not None else "",
            "after_rating": af["rating"] if af is not None else "",
            "after_src": af["src"] if af is not None else "",
            "verdict": verdict, "why": why})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------- main
def main():
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM.mkdir(parents=True, exist_ok=True)
    rv2.OUT_DIR = DIAG_DIR / "currency_tests"       # never overwrite old outputs
    rv2.OUT_DIR.mkdir(exist_ok=True)

    v2 = rv2.load_v2()
    corr = load_corrections()
    v2c, removed, corr_log = apply_corrections(v2, corr)
    print(f"v2 rows {len(v2)} -> after corrections {len(v2c)} "
          f"({len(removed)} removed, {len(corr)} corrections applied)")

    sp, sp_stats = load_second_pass()
    anchors = load_anchors()
    print("second pass:", sp_stats, f"| anchors parsed: {len(anchors)}")

    ct = rv2.sp_currency_tests(v2c)
    passing = ct["passing_countries"]
    print(f"section 5.1 tests on corrected v2: source test pass="
          f"{ct['source_test_pass']} ({ct['n_te_fc']}/{ct['n_te_rows']} FC), "
          f"{len(passing)} countries qualify")
    cont = ct["continuity"]
    print("continuity verdicts:", cont["verdict"].value_counts().to_dict())

    U = build_union(v2c, sp)
    panel, conflicts, dropped_unspec = merge_groups(U, passing)
    panel, n_anchor = add_anchors(panel, anchors)
    panel = finalize(panel)

    # --- checks
    if len(conflicts):
        conflicts.to_csv(DIAG_DIR / "conflicts.csv", index=False)
    need = conflicts[conflicts["resolution"] == "NEEDS_CORRECT_RATING_ROW"] \
        if len(conflicts) else conflicts
    dups = near_duplicates(panel)
    dups.to_csv(DIAG_DIR / "probable_duplicates.csv", index=False)
    sp_all = pd.read_csv(SP_DIR / "second_pass_actions.csv", dtype=str,
                         keep_default_na=False)
    sp_all["action_date"] = sp_all["action_date"].apply(pd.Timestamp)
    rem = removal_neighbours(removed, v2c, sp_all)
    rem.to_csv(DIAG_DIR / "removal_neighbours.csv", index=False)
    corr_log.to_csv(DIAG_DIR / "corrections_applied.csv", index=False)
    cont.to_csv(DIAG_DIR / "currency_continuity_after_corrections.csv", index=False)

    jumps = []
    for (iso3, ag), g in panel.groupby(["iso3", "agency"]):
        g = g.sort_values("action_date")
        for i in range(1, len(g)):
            n = g["rating_numeric"].iloc[i] - g["rating_numeric"].iloc[i - 1]
            if abs(n) > rv2.JUMP_NOTCH_THRESHOLD:
                jumps.append({"iso3": iso3, "agency": ag,
                              "from": g["action_date"].iloc[i - 1].date(),
                              "from_rating": g["rating"].iloc[i - 1],
                              "to": g["action_date"].iloc[i].date(),
                              "to_rating": g["rating"].iloc[i],
                              "notches": int(n)})
    pd.DataFrame(jumps).to_csv(DIAG_DIR / "panel_jumps_gt4.csv", index=False)

    stats = {
        "v2_rows": len(v2), "v2_rows_after_corrections": len(v2c),
        "second_pass": sp_stats, "anchors_added": n_anchor,
        "unspecified_only_rows_dropped_nonqualifying": dropped_unspec,
        "qualifying_countries": len(passing),
        "panel_rows": len(panel),
        "panel_rows_by_provenance": panel["provenance"].value_counts().to_dict(),
        "conflicts_total": len(conflicts),
        "conflicts_by_resolution": (conflicts["resolution"].value_counts().to_dict()
                                    if len(conflicts) else {}),
        "probable_duplicate_pairs": len(dups),
        "jumps_gt4_notches": len(jumps),
        "removal_verdicts": rem["verdict"].value_counts().to_dict(),
    }
    pd.Series(stats).to_json(DIAG_DIR / "panel_build_stats.json", indent=2)
    print(pd.Series(stats).to_string())

    if len(need):
        print("\nSTOP: conflicts where second pass (agency/official) disagrees "
              "with v2 and no correct_rating row exists yet:")
        print(need.to_string(index=False))
        sys.exit(2)
    if (rem["verdict"] == "FAIL").any():
        print("\nSTOP: a removal is inconsistent with the second-pass evidence:")
        print(rem[rem["verdict"] == "FAIL"].to_string(index=False))
        sys.exit(3)

    panel.to_csv(PANEL_PATH, index=False, date_format="%Y-%m-%d")
    (INTERIM / "ratings_h1_candidate.README.md").write_text(
        "# ratings_h1_candidate.csv -- CANDIDATE, NOT FROZEN\n\n"
        "Built by `diagnostics/build_h1_candidate_panel.py` from "
        "`data/raw/ratings_v2/` + `_corrections_v2.csv` + the second-pass "
        "files in `data/raw/ratings_v2_second_pass/` (pre-registration v0.4 "
        "section 5.1). Not frozen: the freeze is a later dated commit "
        "(section 6). Do not compute any lead/lag, return or portfolio "
        "outcome on it. Every row carries `panel_status = "
        "CANDIDATE_NOT_FROZEN`.\n")
    print(f"\nwrote {PANEL_PATH} ({len(panel)} rows)")


if __name__ == "__main__":
    main()
