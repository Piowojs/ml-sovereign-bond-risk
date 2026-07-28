# Thesis Outline (Sovereign Bonds — Updated)
## Beyond Credit Ratings: ML-Driven Risk Classification and Portfolio Construction in Global Sovereign Bond Markets

---

## Preliminary pages

- Title page
- Abstract (300–500 words)
- Acknowledgements
- Table of contents
- List of figures and tables
- List of abbreviations

---

## Chapter 1 — Introduction
*Scope: ~8–10 pages. Purpose: motivate the problem, state the contribution, and signpost the thesis.*

### 1.1 Motivation and research context
Introduce the central tension: sovereign bond investors navigate a wide spectrum of risk — from near-default-free developed market (DM) governments to highly volatile emerging market (EM) sovereigns — yet most portfolio construction still relies on agency credit ratings that are demonstrably lagging, politically sensitive, and slow to reflect deteriorating fundamentals. Meanwhile, EM sovereign spreads over US Treasuries carry significant dispersion that is not fully explained by default risk alone, suggesting that some spread is compensated (a genuine risk premium) and some is not (noise, illiquidity, or temporary mispricing). Establish why a data-driven, systematic approach is timely: post-2022 rate volatility has reshuffled DM sovereign risk, and EM spread dispersion has widened dramatically, making risk stratification more valuable — and more difficult — than in the low-rate era.

### 1.2 Research objectives
State the three concrete objectives:
1. To evaluate whether unsupervised ML clustering of sovereign bonds — using macroeconomic and market-based features — produces a risk stratification that is more timely and less biased than agency credit ratings.
2. To assess whether supervised ML can identify, within the EM sovereign universe, bonds that carry a statistically significant and economically meaningful return premium.
3. To evaluate whether a sovereign bond portfolio built on ML-derived risk tiers and allocated via Hierarchical Risk Parity outperforms classical benchmarks on a risk-adjusted, out-of-sample basis.

### 1.3 Research questions
- RQ1: Do ML-derived sovereign risk clusters capture country-level credit deterioration more dynamically than agency ratings?
- RQ2: Can machine learning identify compensated sovereign spread risk within the EM universe?
- RQ3: Does the DM-core / EM-satellite HRP portfolio offer superior risk-adjusted performance compared to equal-weight, rating-based, and mean-variance optimised sovereign benchmarks?

### 1.4 Scope and delimitations
Universe: USD-denominated sovereign bonds issued by national governments across developed and emerging markets. No corporate, quasi-sovereign, supranational, or sub-national bonds. No currency hedging overlay (flagged as future work). Sample period: 2005–2023, capturing multiple sovereign stress regimes. Methodology is quantitative throughout.

### 1.5 Research hypotheses
Formal hypotheses derived directly from the three research questions. Each is stated as a null (H₀) and alternative (H₁) pair, which maps cleanly to the statistical tests performed in Chapters 4 and 5.

**H1 — Timeliness of ML risk classification (corresponds to RQ1)**
- H₁₀: ML-derived sovereign risk scores do not deteriorate ahead of agency rating downgrades; any observed lead is indistinguishable from chance.
- H₁₁: ML-derived sovereign risk scores deteriorate significantly *before* the corresponding agency rating downgrade, indicating that the model captures credit deterioration more dynamically than ratings.
- *Test*: For each sovereign downgrade event in the sample, compute the mean ML risk score in the 1–4 quarters preceding the downgrade date and compare it to the pre-event baseline using a paired t-test. A statistically significant increase in risk score ahead of the downgrade (p < 0.05) rejects H₁₀.

**H2 — Existence of a compensated EM sovereign return premium (corresponds to RQ2)**
- H₂₀: The supervised ML model has no out-of-sample predictive power over EM sovereign excess returns; the Information Coefficient is not significantly different from zero.
- H₂₁: The supervised ML model generates a statistically significant positive Information Coefficient out-of-sample, indicating that a detectable and exploitable return premium exists within the EM sovereign universe.
- *Test*: Compute the IC (Spearman rank correlation between predicted and realised excess returns) across all walk-forward test folds. Test whether the mean IC is significantly greater than zero using a one-sided t-test across fold observations. An IC above 0.05 with p < 0.05 rejects H₂₀ and constitutes evidence of economic as well as statistical significance.

**H3 — Portfolio outperformance of the HRP core/satellite framework (corresponds to RQ3)**
- H₃₀: The ML-driven HRP core/satellite portfolio does not produce a Sharpe ratio superior to that of the benchmark portfolios; any difference is attributable to sampling variation.
- H₃₁: The ML-driven HRP core/satellite portfolio produces a statistically and economically superior risk-adjusted return (Sharpe ratio) relative to at least the equal-weight benchmark and the rating-stratified portfolio on an out-of-sample basis.
- *Test*: Apply the Jobson-Korkie test (corrected by Memmel, 2003) for pairwise Sharpe ratio comparison between the proposed portfolio and each benchmark. A statistically significant positive difference (p < 0.05) in favour of the proposed portfolio rejects H₃₀. The rating-stratified portfolio is the most important comparator — outperforming it isolates the contribution of ML classification over the existing ratings-based approach.

### 1.6 Thesis structure
Brief one-paragraph signpost of chapters 2–7.

---

## Chapter 2 — Literature Review
*Scope: ~20–25 pages. Purpose: anchor every methodological choice in peer-reviewed finance and ML literature.*

### 2.1 Sovereign debt markets: structure and risk
Overview of the sovereign bond market as an asset class: how governments issue debt, the distinction between local-currency and hard-currency (USD/EUR) debt, and why USD-denominated EM sovereign bonds are appropriate for systematic analysis (liquidity, comparability). Introduce the concept of sovereign spread as a composite of default risk premium, liquidity premium, and global risk appetite (Longstaff et al., 2011). Establish that not all spread is compensated risk — this is the core motivation for Stage 2.

### 2.2 Determinants of sovereign credit risk
Survey the empirical literature on what drives sovereign spreads and default probability. Key macro variables identified across studies: debt-to-GDP (Reinhart & Rogoff, 2010), fiscal balance, current account, FX reserves, inflation, GDP growth, political stability. Edwards (1984) is the foundational empirical paper on EM spread determinants. More recent contributions: Longstaff et al. (2011) on the role of global risk factors vs country-specific factors; Borri & Verdelhan (2011) on the consumption risk explanation of EM sovereign spreads.

### 2.3 Limitations of sovereign credit ratings
Document the academic critique specific to sovereign ratings: ratings are slow to adjust (Mora, 2006), subject to political and relationship pressures (Fuchs & Gehring, 2017), and systematically downgrade during crises rather than anticipating them. Case studies: Greece maintained investment-grade rating until mid-2010 despite visible fiscal deterioration from 2008; Turkey's rating trajectory vs CDS market divergence 2018–2021. This is the academic justification for your clustering approach in Stage 1 — the ratings critique is actually sharper for sovereigns than for corporates.

### 2.4 Factor investing in sovereign fixed income
Review of factor premia in sovereign bond markets. Key papers: Ilmanen (1995) on return predictability in government bonds; Koijen et al. (2018) on carry across asset classes including sovereign bonds; Asness, Moskowitz & Pedersen (2013) on value and momentum everywhere, including fixed income. Establish that carry, momentum, and value signals exist in sovereign bonds — this grounds Stage 2 in factor theory rather than pure ML.

### 2.5 Machine learning in sovereign risk and fixed income
Survey ML applications to sovereign credit and portfolio management. Relevant areas: ML-based default prediction for sovereigns (Feder et al., 2021; Piczak et al., 2022), clustering of countries by macro risk profile, and ML for bond return prediction. Note that ML applications to sovereign portfolios specifically are underdeveloped relative to corporate credit and equities — this is part of your contribution.

### 2.6 Portfolio optimisation: from Markowitz to HRP
Brief treatment of mean-variance optimisation (Markowitz, 1952) and its practical failings in a sovereign bond context: the covariance matrix of sovereign returns is highly unstable across regimes, making MVO weights extremely sensitive to the estimation period. Review risk parity as an alternative (Qian, 2005). Conclude with López de Prado (2016) — Hierarchical Risk Parity — as the methodological foundation. For sovereign bonds specifically, HRP has an additional appeal: the dendrogram naturally groups countries by regional and macro-regime similarity, providing a geopolitically interpretable allocation structure.

### 2.7 Core/satellite portfolio construction for sovereign bonds
Academic and practitioner basis for splitting sovereign portfolios into a DM core and EM satellite. Key reference: IMF working papers on DM/EM sovereign debt differentiation; practitioner frameworks from PIMCO and BlackRock fixed income research on EM allocation as a satellite overlay. Connect to DFA's systematic tilts toward compensated risk (Davis, Fama & French, 2000) as the conceptual inspiration.

### 2.8 Backtesting methodology and bias in financial ML
Review of the specific biases that invalidate backtests: survivorship bias (Brown, Goetzmann & Ross, 1995) — particularly relevant for EM sovereigns given defaults and restructurings in the sample period; look-ahead bias; and multiple testing (Harvey, Liu & Zhu, 2016). This section justifies the walk-forward design and conservative approach to model selection.

### 2.9 Research gap and contribution
Synthesise the review: HRP applied primarily to equities; sovereign-specific ML risk stratification has not been combined with modern portfolio construction; the DM/EM split is taken as given in most frameworks rather than discovered and validated from data. Your thesis occupies this gap — and the validation of ML clusters against ratings (with a focus on lead/lag dynamics) is a concrete empirical contribution.

---

## Chapter 3 — Data
*Scope: ~10–12 pages. Purpose: define the universe, justify sources, and document all preprocessing decisions.*

### 3.1 Data sources
**Market data (Refinitiv Eikon / LSEG):** bond-level price history, yield to maturity, yield spread over US Treasury benchmark, modified duration, convexity, credit ratings history (S&P, Moody's, Fitch), sovereign CDS spreads (5-year, USD). **Macro data (World Bank, IMF, BIS — freely available):** debt/GDP, fiscal balance, current account balance, FX reserves, CPI inflation, real GDP growth, political stability index (World Bank Governance Indicators). **Global macro (FRED):** US Treasury yield curve (2y, 10y, 30y), VIX, DXY (USD index). Document exact series identifiers for full reproducibility.

### 3.2 Sovereign universe construction
Define inclusion criteria: sovereign bonds with at least 24 months of price history at each rebalancing date; USD-denominated (for cross-country comparability); minimum outstanding issue size of $500m (liquidity filter). DM universe: G10 countries plus selected high-grade sovereigns (approximately 15–20 countries). EM universe: JP Morgan EMBI Global constituent countries as the starting pool (approximately 60–70 countries), filtered to those meeting the liquidity and data availability criteria (expected ~35–45 countries). Critically: document that sovereigns that defaulted or restructured during the sample period (Argentina 2014/2020, Ecuador 2020, Zambia 2020, Sri Lanka 2022) are included up to their credit event date — excluding them would create survivorship bias and understate tail risk.

### 3.3 Feature construction

**Group A — Market-based features (high frequency, from Refinitiv)**

| Feature | Description | Stage |
|---|---|---|
| Yield spread over US Treasury | Sovereign risk premium | 1 & 2 |
| Modified duration | Interest rate sensitivity | 1 |
| Convexity | Non-linearity of price-yield | 1 |
| 5-year sovereign CDS spread | Market-implied default probability | 1 & 2 |
| 1m / 3m / 12m return momentum | Price trend signal | 2 |
| Carry (yield minus 3m T-bill) | Net income signal | 2 |
| Spread z-score (52-week) | Mean-reversion signal | 2 |
| CDS-bond basis | Relative mispricing signal | 2 |

**Group B — Macroeconomic fundamentals (low frequency, annual/quarterly)**

| Feature | Description | Stage |
|---|---|---|
| Government debt / GDP | Fiscal stock measure | 1 & 2 |
| Fiscal balance / GDP | Flow sustainability | 1 & 2 |
| Current account balance / GDP | External vulnerability | 1 |
| FX reserves (months of imports) | Liquidity buffer | 1 |
| CPI inflation (YoY) | Monetary stability | 1 & 2 |
| Real GDP growth (YoY) | Growth trajectory | 1 & 2 |
| Political stability index (WGI) | Governance quality | 1 |

**Group C — Global macro factors**

| Feature | Description | Stage |
|---|---|---|
| US 10y–2y yield curve slope | Global rate regime | 1 & 2 |
| VIX level | Global risk appetite | 2 |
| DXY (USD index) | EM funding cost pressure | 2 |
| US 10y yield level | Global rate anchor | 1 & 2 |

### 3.4 Handling of macro data frequency mismatch
Macro fundamentals are annual or quarterly, while market prices are daily. Document the interpolation approach: annual macro data is carried forward quarterly (last observation carried forward), with the critical constraint that only data published *before* a given rebalancing date is used — IMF and World Bank publication lags (typically 3–6 months) are explicitly modelled to avoid look-ahead bias in macro features.

### 3.5 Data cleaning and preprocessing
Missing prices: forward-fill up to 5 business days, then exclude from that rebalancing period. Outlier treatment: winsorise yield spreads and CDS at 1st and 99th percentile. Normalisation: z-score using expanding window statistics (training window only — no future leakage). Stale pricing: bonds without a new price quote for more than 5 days are flagged as illiquid and excluded for that period.

### 3.6 Descriptive statistics
Summary table by DM/EM classification: number of countries, average yield spread, duration, CDS level, debt/GDP. Time-series chart of average EM spreads over US Treasuries across the sample period, annotating the 2008, 2010–2012, 2015–2016, 2020, and 2022 stress episodes. Correlation heatmap of the full feature set. Distribution comparison: DM vs EM on each key feature.

---

## Chapter 4 — Methodology
*Scope: ~20–25 pages. The technical core. Each stage maps to one section.*

### 4.1 Overview of the four-stage pipeline
One-page summary with a pipeline diagram. Establishes the logical chain: feature engineering → sovereign risk classification (Stage 1) → EM return signal (Stage 2) → portfolio construction (Stage 3) → evaluation (Stage 4).

### 4.2 Stage 1: Unsupervised sovereign risk classification
**4.2.1 Algorithm selection rationale** — compare K-Means (fast, interpretable, requires k), Gaussian Mixture Models (soft cluster assignments, handles elliptical clusters), and HDBSCAN (no k required, handles noise, robust to non-spherical clusters). All three applied and compared. Note that HDBSCAN is particularly motivated here: sovereign risk does not form neat spherical clusters — there are genuine outliers (countries in idiosyncratic distress) that K-Means would force into a cluster incorrectly.

**4.2.2 Optimal cluster count** — for K-Means/GMM: silhouette score and BIC/AIC across k = 2…8. Economic interpretation of resulting clusters is required alongside statistical metrics — a k=3 solution (low risk / moderate risk / high risk) is the expected and most interpretable outcome.

**4.2.3 DM/EM label validation** — the primary validation test: does the ML clustering recover the DM/EM structure without being given that label? Compute Adjusted Rand Index between ML clusters and DM/EM classification. More importantly, examine the *disagreements*: which EM countries are clustered with the safe group (stable EMs — Poland, Chile, Czech Republic)? Which DM countries migrate toward the risky cluster in certain periods (Italy 2011–2012, Japan at extreme debt/GDP)?

**4.2.4 Lead/lag analysis vs ratings** — for countries that experienced a rating downgrade during the sample period, test whether the ML risk score deteriorated *before* the downgrade date. This is the central empirical claim of Stage 1.

**4.2.5 Output** — each sovereign at each rebalancing date receives a label: core-eligible (low risk), excluded (moderate risk, too uncertain for either sleeve), or satellite-candidate (high risk, enters Stage 2).

### 4.3 Stage 2: Compensated EM sovereign risk identification
**4.3.1 Motivation** — not all EM sovereign spread is a return premium. Some reflects genuine near-term default risk (Argentina 2019), some reflects global risk appetite (VIX spikes hitting all EM simultaneously), and some reflects genuine compensation for bearing systematic EM risk. Stage 2 attempts to identify which high-risk sovereigns have positive *expected* excess return.

**4.3.2 Target variable construction** — excess total return (price return + coupon) over the 3-month US T-bill in the subsequent quarter. Constructed separately for each country-bond-quarter observation. Binary classification (positive / negative excess return) and continuous regression (return magnitude) both tested.

**4.3.3 Model selection** — LASSO regression (interpretable, embedded feature selection, connects directly to factor literature), Random Forest (non-linear, robust to outliers), XGBoost (gradient-boosted trees, state-of-the-art for tabular financial data). Compare out-of-sample predictive accuracy (AUC for classification, information coefficient for regression).

**4.3.4 Feature importance** — SHAP values for the best-performing model. Key interpretive question: do fundamental macro factors (debt/GDP, current account) or market-based signals (CDS, momentum, carry) dominate the return prediction? This connects empirically to the debate in the literature between fundamental and market-based approaches to sovereign risk.

**4.3.5 Output** — ranked list of satellite-candidate sovereigns with positive expected excess return signal at each rebalancing date. Top N countries (sensitivity tested at N = 5, 10, 15) enter the satellite sleeve.

### 4.4 Stage 3: Portfolio construction
**4.4.1 Sleeve definition** — core sleeve: all sovereigns labelled core-eligible in Stage 1 (DM-dominant, occasionally including stable EM countries). Satellite sleeve: top-N sovereigns from Stage 2 signal. Target core weight: 70% (sensitivity tested at 60%, 75%, 80%).

**4.4.2 Two-stage allocation** — macro-level split between sleeves determined by inverse volatility of each sleeve's trailing 12-month return volatility. Within each sleeve, weights allocated via Hierarchical Risk Parity: correlation matrix of sovereign returns → distance metric d = √(½(1−ρ)) → hierarchical clustering via Ward linkage → recursive bisection weighting inverse to cluster variance. Note: the HRP dendrogram within the core sleeve will naturally reflect regional groupings (Eurozone, Anglosphere, Asia-Pacific) — this is an interpretable and geopolitically meaningful allocation structure worth visualising in the results.

**4.4.3 Rebalancing** — quarterly as base case; monthly and semi-annual in robustness checks.

**4.4.4 Transaction cost modelling** — round-trip costs: 5 bps for DM sovereigns (US Treasuries, Bunds, Gilts), 25 bps for EM sovereigns. Turnover-adjusted net returns reported alongside gross.

### 4.5 Stage 4: Evaluation framework
**4.5.1 Walk-forward backtest design** — expanding window, training start 2005, first test fold beginning 2010 (allowing 5 years of initial training data), folds advancing 18 months. ML models fully retrained at each fold boundary. No data from the test window enters any training computation. Publication lag for macro data respected at each fold.

**4.5.2 Performance metrics** — annualised total return, excess return vs JP Morgan EMBI Global Diversified Index and Bloomberg Global Treasury Index, Sharpe ratio, Sortino ratio, Calmar ratio, maximum drawdown, time to recovery, annual turnover.

**4.5.3 Benchmark portfolios:**
1. JP Morgan EMBI Global Diversified (standard EM sovereign benchmark — passive)
2. Bloomberg Global Treasury Index (DM sovereign benchmark — passive)
3. 70/30 blend of the above two indices (naive DM/EM mix)
4. Rating-stratified sovereign portfolio: same universe, weights determined by agency ratings rather than ML clusters
5. Mean-variance optimised sovereign portfolio with Ledoit-Wolf shrinkage covariance estimator

**4.5.4 Stress testing scenarios:**

| Scenario | Period | Primary risk tested |
|---|---|---|
| Global Financial Crisis | Sep 2008 – Mar 2009 | EM spread blowout, flight to DM quality |
| European sovereign debt crisis | Apr 2010 – Jul 2012 | DM sovereign risk (core sleeve stress) |
| EM taper tantrum | May 2013 – Sep 2013 | EM-specific capital flight, USD strength |
| COVID crash | Feb 2020 – Apr 2020 | Broad liquidity shock, EM more severe |
| Global rate shock | Jan 2022 – Oct 2022 | Duration risk across DM and EM |

The European sovereign debt crisis is a particularly valuable test: it stresses the *core* sleeve rather than the satellite, which is the scenario most sovereign-focused investors fail to model.

**4.5.5 Regime-conditional analysis** — split full sample by: NBER recession/expansion, rising vs falling US 10-year yield, VIX above/below 20, strong vs weak USD (DXY above/below 12-month moving average). The USD regime is specifically important for EM sovereign bonds — a strong dollar historically compresses EM returns. Report Sharpe ratio conditional on each regime bucket.

---

## Chapter 5 — Results
*Scope: ~20–25 pages.*

### 5.1 Stage 1 results: sovereign risk cluster quality
Cluster characteristics table: average yield spread, CDS, duration, debt/GDP, fiscal balance, and political stability by cluster. World map visualisation of cluster assignments at three points in time (2008, 2015, 2022) — this is a highly readable visual that clearly communicates the portfolio's risk geography. DM/EM agreement matrix (ARI scores). Lead/lag analysis: for sovereign rating downgrades in the sample, plot the average ML risk score trajectory in the 8 quarters before and after the downgrade date — does the score deteriorate ahead of the agency action?

### 5.2 Stage 2 results: EM return predictability
Out-of-sample AUC and Information Coefficient across model types. SHAP feature importance: which features dominate — fundamental macro or market signals? Is carry the strongest predictor (consistent with Koijen et al., 2018)? Does CDS-bond basis add independent information? IC stability across folds: is predictability consistent, or concentrated in particular macro regimes?

### 5.3 Stage 3 results: portfolio characteristics
Average allocation by DM/EM and by region. HRP dendrogram visualisation for a representative rebalancing date — show that the core sleeve naturally clusters into regional blocs. Average portfolio duration and spread vs benchmarks. Average annual turnover. Geographic concentration (HHI index) vs the passive benchmarks.

### 5.4 Stage 4 results: backtesting performance
Full out-of-sample equity curves for your portfolio and all five benchmarks. Performance metric table. Drawdown comparison chart. Stress scenario table with all five regimes (drawdown, recovery time, correlation to benchmark during stress). Regime-conditional Sharpe table.

### 5.5 Sensitivity analysis
Heatmap or table of Sharpe ratios across: (a) core/satellite split ratio, (b) number of satellite countries N, (c) rebalancing frequency, (d) transaction cost assumption, (e) training window length. Demonstrates robustness rather than parameter-fitting.

---

## Chapter 6 — Discussion
*Scope: ~10–12 pages.*

### 6.1 Does ML clustering add value over sovereign credit ratings?
Interpret Stage 1 in light of Section 2.3 (ratings limitations for sovereigns). If the model flags fiscal or CDS deterioration 2–4 quarters before a rating downgrade, this is a concrete, citable finding. Discuss the DM/EM boundary cases — which countries cross it dynamically, and does this make economic sense?

### 6.2 What drives EM sovereign return premia?
Interpret Stage 2 SHAP results in light of Section 2.4 (factor literature). Is the dominant signal carry, momentum, or fundamentals? Is predictability higher in certain macro regimes? This speaks to whether EM sovereign premia are compensation for systematic or idiosyncratic risk.

### 6.3 Does HRP core/satellite outperform?
Compare to all five benchmarks. Specific focus on: does the ML-based satellite outperform the rating-based portfolio (validates Stage 1 & 2 contribution)? Does HRP add value over MVO (validates Stage 3 contribution)? Does the core sleeve provide genuine downside protection in the 2008 and 2020 scenarios?

### 6.4 The European sovereign debt crisis as an edge case
The 2010–2012 scenario uniquely stresses the core DM sleeve. Discuss whether the ML clustering flagged the peripheral Eurozone countries (Greece, Portugal, Ireland, Italy) as elevated risk ahead of the crisis — if so, this is a strong validation of Stage 1. If not, it is an honest limitation worth discussing: some sovereign crises are genuinely difficult to anticipate from macro data alone.

### 6.5 Regime dependency and practical implications
The 2022 rate shock affects DM and EM alike through duration — discuss whether duration management is outside the scope of the framework (it is) and what overlay (interest rate swaps, duration-adjusted benchmarking) a practitioner would add.

### 6.6 Limitations
Survivorship bias residual: defaulted sovereigns are included up to their credit event, but post-restructuring returns are difficult to model and are excluded — this slightly understates tail risk. Macro data publication lags are approximated and may differ by country. The model is trained on one globalisation regime; structural breaks (de-dollarisation, shifting reserve currency status) are not modelled. Currency risk is excluded entirely — USD-denomination normalises this, but local-currency investors face additional risk not captured here.

---

## Chapter 7 — Conclusion
*Scope: ~5–6 pages.*

### 7.1 Summary of findings
Concise restatement of results against RQ1–RQ3.

### 7.2 Theoretical contributions
ML-based sovereign risk stratification as a complement to ratings; discovery rather than assumption of the DM/EM risk structure from data; application of HRP to a sovereign-only multi-country bond portfolio; empirical evidence on which factors drive EM sovereign return premia using a global dataset spanning multiple crisis regimes.

### 7.3 Practical contributions
A fully implementable systematic sovereign bond portfolio framework replicable from public data sources (World Bank, IMF, FRED) and Refinitiv. A Python codebase that can be re-run with updated data. Actionable insight on which macro regimes favour the strategy and where it requires supplementary risk management.

### 7.4 Directions for future research
Local-currency sovereign bond extension; currency hedging overlay; inclusion of quasi-sovereign and supranational issuers; real-time macro nowcasting using high-frequency proxies (satellite data, trade flows); reinforcement learning for dynamic core/satellite rebalancing; extension of the framework to a multi-asset portfolio adding equities.

---

## References
*Target: 50–80 references.*

**Essential citations by chapter:**

- Ch. 2.1 — Longstaff, Pan, Pedersen & Singleton (2011) "How Sovereign is Sovereign Credit Risk?"
- Ch. 2.2 — Edwards (1984); Reinhart & Rogoff (2010) *This Time Is Different*; Borri & Verdelhan (2011)
- Ch. 2.3 — Mora (2006); Fuchs & Gehring (2017) on political bias in sovereign ratings
- Ch. 2.4 — Ilmanen (1995); Koijen, Moskowitz, Pedersen & Vrugt (2018) "Carry"; Asness, Moskowitz & Pedersen (2013)
- Ch. 2.5 — Feder, Just & Ross (1981) foundational EM default model; recent ML sovereign credit papers
- Ch. 2.6 — Markowitz (1952); Qian (2005); López de Prado (2016) HRP paper
- Ch. 2.7 — Davis, Fama & French (2000); IMF working papers on EM sovereign allocation
- Ch. 2.8 — Brown, Goetzmann & Ross (1995); Harvey, Liu & Zhu (2016)
- Ch. 4.3 — López de Prado (2018) *Advances in Financial Machine Learning* (SHAP, walk-forward methodology)

---

## Appendices

### Appendix A — Python codebase structure
Repository layout, key modules, and dependencies: `pandas`, `numpy`, `scikit-learn`, `scipy`, `hdbscan`, `PyPortfolioOpt`, `shap`, `xgboost`, `wbdata` (World Bank API). Instructions to reproduce all results from raw data pulls.

### Appendix B — Full feature list with construction formulas
Complete feature engineering specifications including macro data publication lag assumptions by country/source.

### Appendix C — Cluster diagnostics
Silhouette plots, BIC curves, HDBSCAN dendrogram for the full sovereign universe. World map cluster assignments at five representative dates.

### Appendix D — Additional robustness tables
Full sensitivity analysis tables not included in the main body. Results by rebalancing frequency.

### Appendix E — Sovereign default and restructuring events
List of credit events in the sample universe, dates, treatment in the dataset, and impact on portfolio if held through the event.

### Appendix F — Stress scenario detailed charts
Month-by-month drawdown profiles for all five stress scenarios across all benchmarks.

---

*Estimated total length: 80–110 pages excluding appendices and references.*
*Recommended writing order: Ch. 3 → Ch. 4 → Ch. 5 → Ch. 2 → Ch. 1 → Ch. 6 → Ch. 7*
*Data pipeline: Refinitiv Eikon (market + CDS + ratings) · World Bank API · IMF WEO · FRED*
