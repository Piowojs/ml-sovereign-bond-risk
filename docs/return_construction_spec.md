# Return construction spec (v0.1 draft)
 
Status: draft for review. Becomes binding when committed. Must be committed
before any rebuilt return is used in Stage 2, 3 or 4.
Evidence: `data/diagnostics/returns/summary.md` (2026-11-15).
 
## 1. Scope decision
 
- Universe: local-currency 10-year benchmark government bonds (`XX10YT=RR`).
- Primary return measure: local-currency excess return over the local
  3-month rate (approximates a currency-hedged excess return).
- Robustness measure: USD-unhedged excess return over the US 3-month T-bill.
- The earlier "USD-denominated" scope and the price-based returns in
  `build_stage2_panel.py` are superseded.
## 2. Why prices are not the primary input
 
The diagnostic showed that the price series are the weak link:
- roll-day moves of up to 246x a normal day in EM;
- 51 of 402 DM quarters with physically impossible price moves;
- the chain-linked price fix reaches only 0.52 correlation with the
  yield-based return (MAE 1.49% per quarter).
A yield-based return needs no price data and is continuous across benchmark
rolls. It is therefore the primary construction.
 
## 3. Return formula
 
For a period from t to t+1 of length dt (in years):
 
    r = y_t * dt  -  D_t * dy  +  0.5 * C_t * dy^2
 
- y: 10Y yield in decimal; dy = y_{t+1} - y_t
- D: MOD_DURTN (years); C: CONVEXITY
- Base frequency: daily where a daily yield exists, otherwise monthly.
  Quarterly returns are compounded from the base frequency.
Excess returns:
 
    primary:    r_excess = r - s_t * dt              (s = local 3M rate)
    robustness: r_usd    = (1 + r) * (S_{t+1}/S_t) - 1 - us3m_t * dt
                                                     (S = USD per local unit)
 
## 4. Yield source tiers (per country, highest available wins)
 
| Tier | Yield source | Basis | Use |
|---|---|---|---|
| A | Refinitiv daily yield on the benchmark RIC (YLDTOMAT, or another yield field if the licence test in section 8 succeeds) | end of day | primary |
| B | Free monthly series (FRED/OECD `IRLTLT01`, IMF IFS, ECB, national central bank) | monthly average | primary if it passes section 6, flagged |
| C | No yield: chain-linked CLEAN/MID price, roll days (positive duration jump >= 0.15y) zeroed, carry omitted | end of day | robustness only |
 
A country with no Tier A or B yield is excluded from the primary
specification and listed in the thesis with the reason.
 
The tier used is stored per country-period in a `return_tier` column.
 
## 5. Data screens (fixed before the rebuild)
 
- Duration: valid range 0 < D <= 15. Values outside are set to missing.
  D and C are then replaced by their trailing 21-observation median.
- Convexity missing: drop the convexity term and set `no_convexity = True`.
- Yield spikes: a daily change that reverses by at least 80% within three
  observations is treated as a bad print and set to missing.
- Gaps: forward-fill up to 5 business days; longer gaps make the period's
  return missing (no interpolation).
- Tier C prices: same reversal rule applied to daily price returns.
- Every screened observation is logged with country, date and rule.
## 6. Validation gates (run before Stage 2 is touched)
 
On every country that has a Tier A yield:
1. Rebuild the return from the Tier B source and from the Tier C chain.
2. Report quarterly correlation, bias and MAE against the Tier A return,
   plus the ratio of return volatilities (monthly-average yields are
   expected to understate volatility).
Acceptance for the primary specification (**PROVISIONAL** — see below):
- correlation >= 0.90 and |bias| <= 0.25% per quarter.
A tier that fails is robustness-only.

**PROVISIONAL status of the two thresholds (0.90 correlation, 0.25%
bias)**: they are to be confirmed after the section 8 licence test and
before any rebuilt return is used downstream — the licence test
determines how many countries have a Tier A truth series to validate
against, which bears on what these gates can realistically demand. Once
confirmed they become fixed and are not revised after validation results
are seen (the same pre-commitment discipline as the Stage 2
pre-registrations in state.md).
## 7. Downstream changes this forces
 
- Stage 2 target: rebuilt from section 3.
- Stage 2 `carry` feature: local 10Y yield minus local 3M rate (the old
  `us_10y + ZSPREAD/100` proxy overstated yields by up to 2pp).
- Momentum features: recomputed from the rebuilt return series.
- Stage 1 `yield_spread_bps`: definition to be reviewed in the Stage 1
  batch; not changed by this spec.
- Stage 2 is re-run under the existing pre-registered protocol with no
  other change. Old and new results are both reported.
## 8. Open items before commit
 
1. Licence test on the university PC: call `ld.get_history` on one EM RIC
   with no `fields` argument and list every column returned; then request
   candidate yield fields explicitly (`MID_YLD_1`, `B_YLD_1`, `A_YLD_1`).
   If any returns data, Tier A covers far more than 5 countries.
2. In the same session, test 3M benchmark bill RICs (`XX3MT=RR`) and FX
   spot RICs, and re-pull Thailand after 2025-03-26.
3. For the 13 countries with no free 10Y series (Brazil, Egypt,
   Kazakhstan, Kenya, Morocco, Nigeria, Pakistan, Peru, Romania,
   Sri Lanka, Turkey, Vietnam, Zambia): check national central bank and
   ECB series before accepting exclusion.
 