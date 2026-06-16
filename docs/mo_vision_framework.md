# Mo Vision Framework

The strategic frame that all Mo screens, metrics, and UX decisions are measured against.
Sourced from Brian Cluster (Director of Analytics, BUILT) across product design sessions.

Companion file: `mockups/mo_vision_framework.html`

---

## Brian's 7 Questions

Every Mo screen should answer at least one of these questions. If a screen cannot be
mapped to one of them, it either needs an InsightBox added or should not be built yet.

| # | Question | Primary screen(s) |
|---|---|---|
| Q1 | Is the 4pk cannibalizing the 1ct? | Cannibalization → Determine (Priority Events) + Decide (Explanation) |
| Q2 | Which pack size is most price sensitive? | Price Elasticity → Determine (Elasticity Summary) |
| Q3 | Is the 4pk ramping normally? | Cannibalization → Diagnose (Launch Monitor) |
| Q4 | Will adding distribution help or hurt? | Cannibalization → Diagnose (Geography — Expand / Hold / Reduce verdict) |
| Q5 | Are our promotions working or just discounting? | Price Elasticity → Diagnose (Promo Response) |
| Q6 | Where are we vs. competitors on price? | Price Elasticity → Diagnose (Competitive Price) + MULO Norms |
| Q7 | What should I actually do? | Decide phase — Assortment Action + Pricing Action |

---

## Design Principles (non-negotiable)

- **Base Units, not raw Units** — always strip promotions from the headline demand signal
- **avg_weekly_units_spm, not Units/TDP** — velocity is units per store with movement; `Units/TDP` must never appear in the UI
- **Military excluded** — DECA CONUS excluded everywhere (WHERE clause in all queries)
- **Ramp suppression** — scoring suppressed weeks 1–6, surfaced as SUPPRESSED in status
- **Incremental vs. transfer** — every cannibalization verdict must distinguish new demand from demand shift
- **SHAP specificity** — narratives must use actual measured values from `ml_training_features`, not log-odds alone
- **Promo confound flag** — always surface when promo weeks overlap the measurement window

---

## The 4-Question Frame

Every chart or metric on every screen should answer all four questions. If a screen does
not answer all four, it is incomplete — add an InsightBox or synthesis verdict before
shipping to clients.

| # | Question |
|---|---|
| 1 | What changed? |
| 2 | Why did it change? |
| 3 | How confident are we? |
| 4 | What should we do? |

---

## Brian-Style Narrative Template

Every Explanation-tab narrative must follow this sentence pattern:

> "[Focal SKU] is scoring [X%] [cannibalizing / watching / incremental] against
> [Donor SKU] at [Account] ([Channel]) because [donor base units fell/grew X%]
> in the [13-week] measurement window [that focal TDP expanded/contracted X%]."

Every specific number in the narrative must come from `ml_training_features` pct_chg
columns, not inferred from SHAP log-odds. Narratives that invent numbers from model
coefficients erode client trust.

---

## Priority Screens (highest client value, in order)

| Rank | Screen | Reason |
|---|---|---|
| 1 | Explanation tab (Cannibalization Decide) | Brian narrative with actual pct_chg values; most defensible, most differentiating |
| 2 | Pack Size Elasticity Comparison | Directly answers Brian's Q2 |
| 3 | Geography (Cannibalization Diagnose) | Directly answers Brian's Q4 with Expand / Hold / Reduce verdict |
| 4 | Competitive screens | Answers comparison validity question with expandable volume context |
| 5 | Rate Forecast | Quantifies risk trajectory, gives something to act on |

---

## Vision Gaps (backlog)

| Gap | Notes |
|---|---|
| Revenue impact estimates | Lost dollar value from cannibalization — not yet built |
| Incremental demand vs. demand transfer in promo | Beyond the confound flag — not yet built |
| SHAP for price elasticity model | MO_17 does not yet store SHAP values |
| Retailer benchmarking | Item vs. retailer avg + retailer vs. retailer comparisons; `built_filtered_weekly` and `scored_price_elasticity` support both without new ingestion |
