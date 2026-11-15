# Return-construction diagnostics (2026-11-15)

Produced by `diagnostics/returns_diagnostics.py`. Diagnostic only — nothing in
`data/processed/` or `src/` was touched. Motivated by CLAUDE.md's "Known open
problems" (no roll handling, missing coupon income, local-currency series);
this is the measurement pass behind the planned return rebuild. Context
decision recorded here: **the thesis is being re-scoped to local-currency
bonds with excess returns over local short rates**, which is why Part 4
treats the local 3M rate as a required series.

All outputs in `data/diagnostics/returns/`:
`roll_detection_events.csv`, `roll_detection_summary.csv`,
`income_gap_full_dm.csv`, `income_gap_summary.csv`,
`chainlinked_validation.csv`, `chainlinked_summary.csv`,
`yield_recovery_bmk_spd_coverage.csv`, `yield_recovery_error.csv`,
`free_yield_sources.csv`.

---

## Part 1 — Roll detection (MOD_DURTN day-on-day jumps)

2,283 events across 44 countries at the loosest threshold. At the 0.3y
threshold: **918 positive jumps (roll candidates) vs 298 negative/suspect
events** panel-wide. Sign convention: positive = roll candidate (new, longer
benchmark); negative or implausible duration values (|D|>15y or ≤0, e.g. the
US MOD_DURTN print of −20.9) = suspect data.

- Roll frequency is in the right ballpark for real benchmark rolls: US 1.07
  candidates/yr at 0.3y (expected ~4 new 10Y notes/yr — the 0.3y threshold
  only catches the larger rolls), Germany 1.91/yr, France/Italy 1.33/yr,
  Japan 0.19/yr at 0.3y but 75 events at 0.15y (JGB rolls are small in
  duration terms).
- **Contamination is severe where it matters most (EM):** median |price
  move| on a 0.3y roll-candidate day vs the country's median absolute daily
  move — Egypt **246×**, Philippines 110×, Kenya 90×, Sri Lanka 81×,
  Morocco 70×, Pakistan 64×. DM is lower but still real (UK 33×,
  Switzerland 30×, Japan 27×; US ~1× — US rolls are price-continuous).
- Only 8 roll candidates panel-wide land exactly on a quarter-end
  observation date, but any roll **inside** a quarter still contaminates
  that quarter's return (see Part 2's split) — 99 of 402 full-DM gap
  quarters contain one.

## Part 2 — Income gap on the 5 YLDTOMAT countries

Price-based quarterly return (current Stage-2 method, per-quarter field
fallback DIRTY→CLEAN→MID) vs the yield-based approximation
`y_t/4 − D·dy + 0.5·C·dy²`, with `y = YLDTOMAT/100` converted exactly once
and `dy = y_{t+1} − y_t` on decimals (no second division).

**Worked quarters (units check — each term printed from raw values):**

| Country | Quarter | y_t | dy | D | C | carry | duration | convexity | ret_yield | ret_price | gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Germany | 2021Q4→2022Q1 | −0.00179 | +0.00726 | 9.63 | 102.4 | −0.00045 | −0.06990 | +0.00270 | −0.06765 | −0.06861 | **−0.00096** |
| Japan | 2014Q3→Q4 | 0.00526 | −0.00198 | 9.71 | 100.6 | +0.00132 | +0.01922 | +0.00020 | +0.02073 | +0.01962 | **−0.00112** |
| Switzerland | 2014Q3→Q4 | 0.00478 | −0.00110 | 9.13 | 95.5 | +0.00120 | +0.01005 | +0.00006 | +0.01130 | +0.04380 | +0.03250 |
| UK | 2020Q1→Q2 | 0.00355 | −0.00183 | 8.83 | 92.2 | +0.00089 | +0.01616 | +0.00015 | +0.01720 | +0.00064 | −0.01657 |
| US | 2014Q4→2015Q1 | 0.02170 | −0.00244 | 8.79 | 87.0 | +0.00543 | +0.02141 | +0.00026 | +0.02710 | −0.00142 | −0.02852 |

Germany/Japan agree to ~0.1% in a ±7% quarter — units are right; the CH/UK/US
examples disagree because of price-data problems and rolls, which is the point
of the splits below.

**Headline numbers** (402 quarters; `income_gap_summary.csv`):
- Pooled mean gap −0.25%/quarter, median −0.37%, std 6.6% — the std, not the
  mean, is the story.
- **Roll-in-quarter split is decisive**: quarters containing a 0.3y roll
  candidate have strongly negative gaps everywhere (US −4.9% to −5.6% mean,
  UK −6.9% to −9.1%, Switzerland −3.5% to −6.5%) — the naive price return
  loses several percent per roll quarter, exactly the contamination
  signature. Roll-free quarters center near 0 to +1.5%.
- **Price-field split**: DIRTY_PRC roll-free quarters have small positive
  mean gaps (Japan +0.30%, US +1.49%) — consistent with accrued interest
  carrying income the yield approximation also carries; MID/CLEAN quarters
  sit lower. The income bias is modest for these low-coupon DM issuers
  (~0.3–1.5%/quarter mean); it will be larger for high-coupon EM.
- **Sanity check**: pooled correlation is only 0.35, but this is driven by
  51/402 quarters with |gap|>5% that are plainly corrupt price data, not
  units (e.g. UK MID_PRICE quarters with ±39–45% "price moves" on a gilt —
  2019Q4 +45%, 2006Q4 +39%; Switzerland ±29%). Excluding |gap|>5% and
  roll-contaminated quarters: **correlation 0.906 (n=284) — the >0.9 bar is
  met on clean, roll-free quarters.** The outlier list itself is a finding:
  the raw price series need a data-quality screen (impossible quarterly
  moves) before any return construction.

## Part 2b — Chain-linked candidate fix (validated where truth is known)

Daily chain from an income-free price field (CLEAN_PRC preferred, but its
coverage is <50% for all 5 countries — e.g. Germany 1,054/5,364 rows,
~2021-25 only — so **all 5 chains used MID_PRICE**), with price return
zeroed on roll-candidate days, plus carry `y_t/4`. Scored against the
yield-based approximation (`chainlinked_summary.csv`):

| Variant | Pooled bias | Pooled MAE | Corr vs yield-based |
|---|---|---|---|
| Naive price return (current method) | −0.25% | **2.98%** | 0.35 |
| Chain, zeroing rolls > 0.3y | +1.15% | 1.70% | 0.49 |
| Chain, zeroing rolls > 0.15y | +1.04% | **1.49%** | 0.52 |

- The chain **halves the error** of the current method, and the looser 0.15y
  threshold is uniformly as good or better than 0.3y — more rolls caught,
  essentially no cost.
- Residual +1% positive bias: zeroing a roll day also deletes that day's
  genuine market move, and MID_PRICE outlier days still leak through.
  Per-country: Germany MAE 0.58%/corr 0.85 and US 1.78%/0.84 are good;
  UK (3.0%/0.39) is dragged by the same corrupt price stretches as Part 2.
- Verdict: chain-link + roll-zeroing at 0.15y is a viable construction for
  the 39 YLDTOMAT-less countries **provided** a price-outlier screen is
  added; the carry leg needs a recovered yield (Parts 3–4).

## Part 3 — Yield recovery for the other 39 countries

- **`BMK_SPD`: unusable.** 0% coverage for Morocco/Kazakhstan, 7.6% Zambia;
  where populated it is ~100% zeros for most countries (US all-zero; Peru/
  Sweden/Colombia/Norway 0% nonzero of nonnull). Full table:
  `yield_recovery_bmk_spd_coverage.csv`.
- **ZSPREAD + swap curve: not derivable from the repo as-is** — no swap
  curve in any currency exists in the data. One new external input (local
  swap or government benchmark curve) is required.
- **The computable proxy `us_10y + ZSPREAD/100`** (Stage 2's carry proxy),
  scored against true YLDTOMAT (`yield_recovery_error.csv`): US bias +0.01pp
  / MAE 0.16pp / level-corr 0.98 (fine — USD rates vs USD swap);
  UK +0.15pp / 0.55pp / 0.88 (usable); **Germany +0.93pp MAE 1.01pp, Japan
  and Switzerland +1.99pp MAE 1.99pp** — a 2-percentage-point systematic
  overstatement of yield for low-rate non-USD countries. This doubles as a
  measured error bar on Stage 2's existing `carry` feature. Conclusion: the
  proxy is **not** an acceptable yield recovery for local-currency carry;
  local 10Y yields must come from external sources (Part 4).

## Part 4 — Free monthly sources per country (`free_yield_sources.csv`)

No data downloaded; confidence per cell is `verified` (well-established
series pattern) / `likely` (catalog should cover, id not individually
confirmed) / `not found`. Columns include basis (period-average vs
end-of-period) and approximate first date. All OECD MEI yields (FRED
`IRLTLT01{ISO2}M156N`) are **monthly averages**, as are IMF IFS rates —
an averaging-vs-end-of-quarter mismatch the rebuild must handle explicitly.

- **10Y monthly yield**: 24/44 verified via FRED/OECD `IRLTLT01…` (all DM
  plus Chile, Colombia, Czech R., Hungary, Mexico, Poland, Greece,
  Portugal…); 7 likely (India, Indonesia, South Africa via OECD partner
  series; China, Malaysia, Thailand, Philippines via IMF IFS);
  **13 not found** in FRED/OECD/IFS: Brazil, Egypt, Kazakhstan, Kenya,
  Morocco, Nigeria, Pakistan, Peru, Romania, Sri Lanka, Turkey, Vietnam,
  Zambia.
- **ECB / national-central-bank fallbacks for those 13** (added
  2026-11-15; `yld10y_cb_fallback_*` columns): two **verified** — Romania
  via the ECB Data Portal's convergence-purposes long-term rate
  (`IRS.M.RO.L.L40.CI.0000.RON.N.Z`, monthly average, RON, from ~2005)
  and Morocco via Bank Al-Maghrib's downloadable secondary-market
  Treasury reference rates (daily curve incl. 10Y, bkam.ma). The other
  11 have `likely` national-CB sources (BCB/ANBIMA for Brazil ~2007+,
  CBE Egypt, CBK Kenya, CBN/DMO Nigeria, SBP Pakistan, BCRP Peru, CBSL
  Sri Lanka, CBRT EVDS Turkey from ~2010, and partial-confidence
  KASE/NBK Kazakhstan, HNX/SBV Vietnam, BoZ Zambia) — several are
  auction-date series rather than continuous monthly, which the rebuild
  must handle. Net: only Kazakhstan, Vietnam, and Zambia remain genuinely
  uncertain for a free local 10Y.
- **Local 3M rate (now required under the local-currency re-scope)**: OECD
  members likely covered by FRED `IR3TIB01…` 3m interbank; the EM/frontier
  set by IMF IFS T-bill (`FITB_PA`) / money-market (`FIMM_PA`) rates —
  T-bill rates are the one series frontier markets (Egypt, Kenya, Nigeria,
  Pakistan, Sri Lanka, Zambia) historically do have in IFS. No country is
  expected to be entirely without a local short rate, but confidence is
  `likely`, not verified, outside the OECD.
- **FX spot vs USD**: FRED `DEX…` daily pairs for ~15 currencies incl. EUR
  (covers the 10 euro members); IMF IFS (`ENDA` avg / `ENDE` eop) for the
  rest — effectively full coverage.

## Implications for the return rebuild

1. Rolls are frequent (≈1–2/yr/country at 0.3y) and, in EM, catastrophic for
   naive returns (roll-day moves up to 246× a normal day). Any return built
   from these composites must neutralize roll days.
2. The chain-linked construction (income-free price chain, roll days zeroed
   at 0.15y, carry y/4 added) halves the current method's error on the 5
   countries where truth is known — it is the right starting template,
   **plus a price-outlier screen** (51/402 DM quarters show physically
   impossible price moves; EM will be worse).
3. Carry cannot come from `us_10y + ZSPREAD/100` (up to 2pp systematic
   error); local 10Y yields exist free for ~31/44 countries, and local 3M
   rates (the new excess-return denominator) plausibly for all 44 via
   FRED/IFS — the 13 missing-10Y countries are the real acquisition problem.
4. Monthly-average vs end-of-period basis of the free yield sources needs an
   explicit convention when they feed quarter-end rebalancing.
