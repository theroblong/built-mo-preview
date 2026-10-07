---
name: project_portfolio_cannibalization
description: "MO_55 COMPLETE: portfolio constraint post-processing — 833K units redistributed (1.18%), zero-sum satisfied 2026-07-07"
metadata: 
  node_type: memory
  type: project
  originSessionId: 70625339-057c-4722-beac-97654503740f
---

**Status: DONE (2026-07-07)**

`scripts/MO_55_portfolio_constraint.py` applies post-forecast demand redistribution using the BUILT-to-BUILT scored_cannibalization transition matrix.

**Algorithm:**
- For each focal UPC in launch window (wsl ≤ 26): pull sibling donors with cannibal_prob ≥ 0.30
- Transfer decays linearly: `1 − (wsl / 26)` — strongest at launch, fades as AR lags build history
- Three caps: `MIN_FOCAL_UNITS=10` (skip near-zero presence), `MAX_TRANSFER_PCT=20%` (global per donor, tracked via `portfolio_adj_delta`), `MAX_RECEIVE_PCT=50%` (focal per week)

**Results:**
- Total BUILT portfolio: 70,316,011 units (conserved)
- Units redistributed: 833,153 (1.18%)
- Focal series adjusted: 200; donors giving 19–20%; focals receiving 42–50%
- Zero-sum constraint: max delta = 0.0000 units ✓
- Top focal: `08-40229-30651` at Walmart +2,380 units (+49.6%, wsl=17)
- Top donor: `08-40229-30546` at Walmart −96,767 units (−11.5%)

**Output:** `outputs/retailer_sales_forecast_adj.parquet` (32,448 rows). New columns: `portfolio_adj_delta`, `portfolio_adj_type`, `portfolio_adj_source_upc`, `forecast_dollars_base_adj`.

**Druid status (2026-07-07 DONE):** `retailer_sales_forecast_adj` datasource live. 32,448 rows, 30 dimensions. Adjusted rows: 3,204 (DONOR: 2,135 + FOCAL_LAUNCH: 1,069). NONE: 29,244.

**Two-datasource comparison plan:**
- `retailer_sales_forecast` = series-blind base; each of 2,496 series modeled independently
- `retailer_sales_forecast_adj` = portfolio-aware; `portfolio_adj_delta` captures exact unit transfer per row
- **Validation question 1:** Are DONOR rows already declining in the base forecast? If yes (AR lags encoded cannibalization), adj deltas will be small — confirming MO_56's architectural conclusion. Large deltas = the model missed it.
- **Validation question 2:** Once actuals arrive, compute wMAPE on raw vs. adj for FOCAL_LAUNCH rows. If adj is better, the portfolio layer is adding real signal.
- **Validation question 3:** Are the 30% cannibal_prob threshold, 20% MAX_TRANSFER_PCT, wsl≤26 launch window calibrated correctly? Raw-vs-adj accuracy gap reveals whether caps are too tight or too loose.

**FP&A / explainability use:**
- `portfolio_adj_delta` + `portfolio_adj_source_upc` answer "organic growth vs. redistributed volume" for Connor/Jeff/Bracken
- Mo Chat event card: "Adjusted 13w forecast +X units offset by −Y units from [donor UPCs] — reflects cannibalization, not pure demand"
- Honest caveat: zero-sum assumes no category expansion; may not hold for all launches

**UI wire-up (deferred):** Forecast drawer raw-vs-adj comparison line — 3-file change: retailer.py SELECT, types.ts ForecastPoint, Recharts second series.

**Longer-term:** Category-level top-down anchor (Layer 1 of 4-layer architecture) replaces this post-hoc constraint.

**Links:** [[project_mo53_individual_ablation]]; [[project_ml_architecture_roadmap]]; [[project_mo56_candidate]] (MO_56 architectural conclusion re AR lags encoding cannibalization)
