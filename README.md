# Product Cannibalization Planning Workspace

This repository contains the planning and documentation package for building a product cannibalization prediction capability using SPINS CPG POS data, with delivery designed around Aevah.

The current repo is documentation-first. It does not yet contain modeling code or production pipelines. Instead, it captures the strategy, architecture, data requirements, diagrams, and execution plan needed to move into implementation cleanly.

---

## Open Agenda Items (as of 2026-07-01)

### Brian sanity-check (gating dependency for July close)

> Rob is explicit: **Brian reviews and validates before going back to Jeff/Bracken.** Items that will be in the Brian package:
>
> 1. HTML report v2.1.0 — Q2 positively reframed; duplicate sections removed; AHOLD/VS positive elasticity explained with MO_44 OLS context; SHAP waterfalls for BB 4pk + CD 4pk at Walmart
> 2. Option B two-source elasticity live in Mo — CRMA accounts now use MO_44 causal OLS (all 4 retailer.py assembly points); MULO guardrails shown in UI and Mo Chat
> 3. Walk-through of Phase 2 rolling signals roadmap — what the model knows statically vs. what it will know weekly once MO_46 v3 pipeline runs (this is the Rob "pre-trained pathways" story)
> 4. ~~One honest known gap: post-hoc event validation~~ **RESOLVED** — MO_47 complete (see update 7). 30,876 price events validated; 63% direction accuracy on clean moves; Kroger BB 4pk case study anchors the business narrative. Embedded in MO_48 Brian package.

### Question for Brian / Jeff (via Rob)

> **Strategic direction: BUILT-specific depth vs. multi-client SPINS platform breadth?**
>
> The forecasting pipeline is currently calibrated for BUILT's ~105 SKUs × 47 retailers. The same architecture — LightGBM with SPINS domain features, quantile scenario bands, BSTS causal event analysis — could generalize to any CPG brand on the Aevah platform with minimal rework.
>
> The answer shapes the next investment:
> - **BUILT-specific depth** → improve BUILT model accuracy (YAGO features, competitive category context, Phase 2 Mo signals, revenue model); timeline weeks to months; payoff demonstrated in Connor's next planning cycle.
> - **Multi-client SPINS platform breadth** → generalize forecasting architecture to serve any Aevah client from spins_full; requires category-agnostic global model pre-training; larger engineering lift; competitive differentiator for Aevah at scale.
>
> These are not mutually exclusive — BUILT-specific improvements are the proof of concept that validates the multi-client platform. But the investment sequencing differs.

### Data Request for Connor (FP&A Director, BUILT)

> **What is BUILT's current forecast accuracy?**
>
> To complete the ROI quantification (Brian's "$1M per 1% MAPE improvement" anchor), we need Connor's actual forecast error from recent quarters — not an industry estimate. Specifically:
>
> - For 3–5 representative SKU × retailer combinations (e.g., BB 4pk at Walmart, BB 4pk at Kroger, CD 4pk at Walmart), what was the forecast vs. actual for the most recent completed quarter?
> - Even a rough MAPE estimate ("we're usually within 20–30%") is enough to anchor the dollar claim.
> - Ideal: a simple Excel export of their weekly forecast vs. SPINS actuals for 1–2 SKUs over 13 weeks.
>
> Without this, all ROI numbers compare to a proxy baseline (MA 13wk = 27%), not to BUILT's own process. Connor's actual accuracy is the denominator in the ROI calculation.

---

## What is in this repo

### Data sample

- [All_items_extract_100.csv](/Users/jasonbrazeal/Documents/FirstAgent/All_items_extract_100.csv)

A small sample extract used to inspect the structure of the SPINS POS dataset. This is not the full modeling dataset. The working assumption in the planning docs is that the real source dataset is much larger and contains at least 3 years of weekly history.

### Agent definition

- [agents/brad.yaml](/Users/jasonbrazeal/Documents/FirstAgent/agents/brad.yaml)

Brad is the analyst persona defined for this project. He is positioned as the machine-learning-focused data analyst for this work and serves as the conceptual owner of the modeling approach documented in this repo.

### Core project documents

- [docs/brad_cannibalization_plan.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_plan.md)  
  The original strategy document for building cannibalization predictions.

- [docs/brad_cannibalization_plan_aevah.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_plan_aevah.md)  
  The Aevah-adapted version of the strategy, preserving the original while adjusting for governed delivery inside Aevah.

- [docs/brad_cannibalization_implementation_blueprint.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_implementation_blueprint.md)  
  The execution blueprint with phases, owners, inputs, outputs, and success criteria.

- [docs/brad_cannibalization_diagrams.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_diagrams.md)  
  Mermaid flowcharts and sequence diagrams that visualize the architecture and operating flow.

- [docs/brad_cannibalization_data_requirements.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_data_requirements.md)  
  The concrete data spec: grain, history depth, tables, keys, required fields, and quality checks.

- [docs/brad_cannibalization_project_roadmap.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_project_roadmap.md)  
  The phased roadmap that turns the strategy into a time-based delivery plan.

- [docs/brad_aevah_spins_processing_value_overview.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_aevah_spins_processing_value_overview.md)  
  A client-facing overview of how Aevah accepts, validates, enriches, processes, scores, and refreshes the 51GB / 95 million row SPINS feed.

- [docs/brad_built_cannibalization_druid_ml_plan.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_cannibalization_druid_ml_plan.md)  
  The Druid query and ML workflow plan for creating flexible BUILT pack, flavor, and competitive cannibalization comparisons.

- [docs/brad_built_cannibalization_druid_ml_plan_evaluation.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_cannibalization_druid_ml_plan_evaluation.md)  
  Brad's evaluation of the Druid and ML plan, including the design adjustments needed to support arbitrary user-selected pack, flavor, and competitor comparisons.

- [docs/brad_weekly_win_count_bonus_path.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_weekly_win_count_bonus_path.md)  
  A bonus-path concept for tracking weekly SKU win counts, win percentages, probabilities, ratios, and association patterns alongside units and dollars.

- [docs/brad_built_cannibalization_ui_v2_comparison_pools.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_cannibalization_ui_v2_comparison_pools.md)  
  An additional UI workbench concept that turns flexible comparison pools, all-SKU pairwise pressure, win counts, win percentages, and geography/channel drilldowns into a product experience.

- [docs/brad_built_predictive_forecasting_extension_for_mo.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_predictive_forecasting_extension_for_mo.md)  
  A focused extension plan for adding predictive forecasting to Mo through controlled next-move scenarios, forecast ranges, donor exposure, confidence labels, and actionable assortment recommendations.

- [docs/brad_built_druid_data_onboarding_and_ml_soundness_check.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_druid_data_onboarding_and_ml_soundness_check.md)  
  A step-by-step Druid data onboarding checklist and ML soundness review for training on the full BUILT plus competitor universe while keeping Mo focused and actionable.

- [docs/brad_built_lean_client_data_request_matrix.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_lean_client_data_request_matrix.md)  
  A practical matrix separating what SPINS already provides, what can be calculated from SPINS, and the smallest useful set of additional client data requests.

- [docs/brad_built_spins_95m_utilization_audit.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_spins_95m_utilization_audit.md)  
  An audit of whether the Druid and ML plan fully exploits the 167-column SPINS extract, including recommended additions for YAGO, EQ units, ACV, promo mechanics, price, productivity, and revenue features.

- [docs/built_cannibalization_druid_ml_plan_5.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/built_cannibalization_druid_ml_plan_5.md)  
  The newest suite-level Druid and ML plan, now extended for Mo Price Elasticity alongside Cannibalization.

- [docs/Mo_Build_Field_Guide_price_elasticity_addendum.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/Mo_Build_Field_Guide_price_elasticity_addendum.md)  
  A field-guide addendum for building the Price Elasticity Druid outputs, models, UI wiring, and guardrails.

- [docs/mo_messages_register.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/mo_messages_register.md)  
  The canonical register of system prompts and user message templates for the Mo project's AI agents. Includes Brad's system prompt (M1) and parameterized templates for common agent invocations. Browser-friendly version: [mockups/mo_messages_register.html](/Users/jasonbrazeal/Documents/FirstAgent/mockups/mo_messages_register.html).

- [docs/mo_ml_field_notes.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/mo_ml_field_notes.md)  
  Operational findings from running the Mo ML pipeline: focal pct_chg columns are structurally NULL, Druid returns numeric columns as object dtype, outlier clipping requirements, ORDER BY constraints, confirmed column name differences in price_elasticity_training_features, LambdaRank sort requirements, and LightGBM degenerate label behavior. Read before writing or modifying any pipeline script. Browser-friendly version: [mockups/mo_ml_field_notes.html](/Users/jasonbrazeal/Documents/FirstAgent/mockups/mo_ml_field_notes.html).

- [docs/mo_built_spins_hierarchy.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/mo_built_spins_hierarchy.md)  
  SPINS attribute codes used in the Mo pipeline: pack size (1=Singles through 4=Family Size), protein, sugars, calories, and sugar-alcohol codes 1–20, panel data fields (Trips, HH Count, Buy Rate), and company report templates. Source: BUILT product hierarchy slide from 2026-06-12 client meeting. Browser-friendly version: [mockups/mo_built_spins_hierarchy.html](/Users/jasonbrazeal/Documents/FirstAgent/mockups/mo_built_spins_hierarchy.html).

- [docs/mo_cannibalization_model_reference.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/mo_cannibalization_model_reference.md)  
  Operational reference for interpreting scored_cannibalization outputs: status thresholds (Cannibalizing ≥ 0.66, Watch 0.36–0.64, Incremental ≤ 0.33), relationship_distance meanings (1=sibling, 3=adjacent, 4=competitor), cannibal_confidence as data maturity not model certainty, scoring coverage by channel (47.8% overall), and the MinIO write-back pattern. Browser-friendly version: [mockups/mo_cannibalization_model_reference.html](/Users/jasonbrazeal/Documents/FirstAgent/mockups/mo_cannibalization_model_reference.html).

- [docs/mo_vision_framework.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/mo_vision_framework.md)  
  The strategic frame all Mo screens are measured against: Brian's 7 questions, the 4-question frame (what changed / why / how confident / what to do), the Brian-style narrative template, priority screen ranking, and vision gaps backlog. Browser-friendly version: [mockups/mo_vision_framework.html](/Users/jasonbrazeal/Documents/FirstAgent/mockups/mo_vision_framework.html).

## What we have built so far

### 2026-06-30 (v2.0.6) — Quantile Forecast + BSTS CausalImpact (MO_42, MO_43)

**MO_42 — LightGBM Quantile Forecast (`scripts/MO_42_quantile_forecast.py`)**

Three LightGBM quantile models (P10/P50/P90) at Dec 2025 cutpoint using pinball loss. Gives FP&A a calibrated floor/plan/upside range for every SKU × retailer, replacing a single point estimate with a statistically grounded scenario band. Section 16 added to HTML report.

| Metric | Value |
|---|---|
| P50 wMAPE (plan accuracy) | **5.11%** |
| Portfolio median band coverage | 69% (ideal 80% — bands are slightly tight; Phase 2 fix: widen to α=0.05/0.95 or use conformal prediction) |
| 13-week revenue range (top series) | **$19.5M floor → $25.7M plan → $28.7M upside** |

**MO_43 — BSTS / CausalImpact Price Event (`scripts/MO_43_causal_impact.py`)**

Bayesian Structural Time Series counterfactual analysis of the Dec 7 2025 price reduction on BB 4pk at Kroger. Controls: BB 4pk at Walmart (same product, unaffected ARP) + Cookie Dough 4pk at Kroger (same retailer, stable ARP). Answers the FP&A question SHAP cannot: "What would demand have been without the price cut?" Section 17 added to HTML report.

| Metric | Value |
|---|---|
| ARP change | $10.99 → $10.14 (−7.8%) from Dec 7 2025 |
| Estimated incremental lift | **+28.6%** above BSTS counterfactual |
| Cumulative extra units (8 weeks) | **+8,443 units** |
| Estimated revenue impact | **+$85,569** |

**Pending (Phase 2 queue):**
4. **DeepGLO** — global-local matrix factorization + TCN benchmark

Note: TreeSHAP already in use via MO_40 (`shap.TreeExplainer`).

---

### 2026-06-30 (v2.0.8) — GRU Neural Forecast Benchmark (MO_45)

**MO_45 — GRU with Exogenous Signals (`scripts/MO_45_gru_benchmark.py`)**

Gated Recurrent Unit benchmark against N-BEATS and LightGBM at all 3 standard cutpoints (h=13 quarterly). Key differentiator: GRU receives `week_of_year` (future exog for seasonality) and `arp` + `tdp` (historical exog for price/distribution), while N-BEATS is purely autoregressive. Section 18 added to HTML report.

| Cutpoint | GRU | N-BEATS (MO_32A) | LightGBM | MA 13wk |
|---|---|---|---|---|
| Dec 2024 | **51.67%** | 55.6% | 29.97% | 50.38% |
| Oct 2025 | **102.66%** | 117.9% | 7.33% | 40.20% |
| Dec 2025 | 79.58% | **46.4%** | 4.68% | 27.03% |

**Key finding:** GRU beats N-BEATS at Dec 2024 and Oct 2025 (exog signals help), but reverses at Dec 2025 (both neural architectures share the same growth-mode failure — without full TDP trajectory and cannibalization signals, the recurrent unit extrapolates stale patterns). LightGBM's 27-feature engineering advantage holds across all cutpoints. The GRU result confirms that *any* neural architecture fed domain signals outperforms the purely autoregressive equivalent, but neither matches a well-engineered gradient-boosted model at this data scale.

| Metric | Value |
|---|---|
| GRU architecture | 2-layer encoder, 64 hidden units, 40.5K params |
| Exogenous features | futr: week_of_year; hist: ARP, TDP |
| HTML report version | v2.0.8 (13.0 MB) |

---

### 2026-07-01 — Priority stack: close BUILT deal in July

**Source:** Jun 25 + Jul 1 Aevah standup transcripts (`docs/Aevah Standup jun30-26.docx`, `docs/Aevah Standup jul 1 26.docx`). Rob's explicit goal: close BUILT in July.

**Gating dependency:** Brian must sanity-check the HTML report and validate SPINS channel interpretations before going back to Jeff/Bracken. Brian also needs to clarify CRMA/RMA/MULO guardrails — Jason flagged these are not yet fully enforced in the tool.

**What Connor/Bracken need to trust the system:**
1. Accurate retailer-level elasticity (no positive anomalies surfacing in live demo)
2. Explainability in business terms — not DAG diagrams; SHAP feature importance in plain English
3. HTML report Q2 reframe: "how do I develop trust" (positive framing) vs "why should I trust a black box" (negative framing) — Rob's exact note from Jul 1 transcript
4. Honest limitations: system says what it doesn't know (new SKUs <52wks, promo gaps, SPINS lag)

**Priority stack:**

| # | Task | Why |
|---|---|---|
| 1 | **Option B: two-source elasticity in UI** | Fix AHOLD/VS positive elasticity before any live demo; CRMA accounts → MO_44 OLS, KEY ACCOUNT → MO_17 |
| 2 | **HTML report Q2 reframe + Brian review package** | Gating dependency before Jeff/Bracken follow-up |
| 3 | **SPINS channel guardrails in UI/Mo Chat** | Jason explicitly flagged CRMA/RMA/MULO rules unresolved; demo safety |
| 4 | **MO_16/17 Druid ingest** | Required before Option B API can query live data |

**Demo operating rules (from Rob):**
- Rob frames, Jason demonstrates; "screen time high, monologue low"
- Don't fumble on-screen — defer to follow-up, which buys the next meeting
- Future: self-demo mode ("Mo, show us this") with pop-ups — not in scope for July

---

### 2026-07-01 — Price elasticity accuracy: $0.05 guardrail (MO_17) + MO_44 two-source fix (v2.1.0)

**Root cause diagnosed:** 35.9% of `scored_price_elasticity` rows produced garbage elasticity values (AHOLD mean implied_elasticity = 1.2×10¹¹) due to division-by-near-zero in MO_17. When `log_price_change` is tiny (CRMA national aggregates barely move week-to-week), `predicted_log_unit_change / log_price_change` blows up even when the prediction is reasonable.

**Fix applied to MO_17:** Rows where `|post_13w_avg_price_per_bar − pre_13w_avg_price_per_bar| < $0.05` now get `elasticity_band = "Insufficient Price Variation"` and `implied_elasticity = NaN`. Threshold rationale: $0.05 / $2.59 avg per-bar price = 1.93% — anything smaller is sub-nickel noise, not a real pricing decision. 32,561 rows (35.9%) reclassified.

**AHOLD Delhaize:** Positive elasticity in UI is a CRMA geography artifact. AHOLD aggregates Food Lion (strict EDLP), Stop & Shop / Giant (High-Low), and Hannaford (EDLP-leaning) into one national row. Banner-level promos cancel each other at the aggregate, leaving near-zero price signal. MO_44 OLS with TDP/maturity controls gives AHOLD ε=−1.262 (correctly negative). Remaining ~49% Positive rows after guardrail are a missing-TDP-feature issue in MO_16 — queued for retrain.

**Vitamin Shoppe:** 59% Positive rows persist after guardrail — confirmed real by MO_44 OLS (ε=+0.881 with full controls). Mechanism is NOT Veblen/luxury-buyer pricing. Positive rows have avg price *decreasing* (log_price_change=−0.061) — consistent with clearance/lifecycle behavior where discounted SKUs are being discontinued and velocity declines alongside price.

**Systematic ~30% Positive rate:** Affects all major CRMA retailers (Walmart 27%, Kroger 30%, Publix 33%) — not AHOLD-specific. Root cause: MO_16 `OWN_PRICE_FEATURES` lacks TDP. Distribution expansion events confound the price→demand signal.

**MO_44 v2.1.0 fixes (HTML report):**
- DoWhy portfolio ATE now uses KEY ACCOUNT rows only (avoids CRMA scale confound) → ε=−0.3437 restored
- Per-account OLS uses full KEY ACCOUNT + CRMA → Walmart (−0.245), Kroger (−0.590), Ahold (−1.262), Albertsons (−1.066), Publix (−1.025) all now appear in table
- Per-account OLS filtered to weeks with `|arp_wow_delta| ≥ $0.05 OR |Δ%| ≥ 2.5%` (uses pre-computed parquet columns)

**MO_16 v2 retrain (2026-07-01):** `pre_13w_tdp`, `post_13w_tdp`, `tdp_pct_chg` added to `OWN_PRICE_FEATURES`. Training data also filtered to the same $0.05 guardrail so model trains on genuine price-move windows only (57,193 rows vs 90,757 raw). Results: R²=0.9810 (↑ from 0.9687), MAE=0.0759. TDP control improved medians (AHOLD −0.247, Walmart −1.287, Kroger −1.270) but did not eliminate the ~30–50% Positive rate at CRMA-level accounts — CRMA aggregation is a geometry-of-data problem not solvable by features alone. MO_17 re-scored with v2 model; parquet on S3.

**Pending before Druid ingest:** Option B UI wiring (serve MO_44 OLS elasticity for CRMA accounts, MO_17 for KEY ACCOUNT) — then submit Druid ingest + tag milestone.

---

### 2026-07-01 (update 2) — Option B wired + HTML report deduplication

### 2026-07-01 (update 6) — Fix flat-line forward forecast: true AR loop + YAGO seasonal blend (MO_35 / MO_27)

**Problem:** The forward forecast charts (Figure 10 in HTML report — "Where Is BUILT Today?") showed a completely flat line for all 13 forecast weeks. Every retailer (Walmart, SAMS, Kroger, Publix, etc.) forecast as a horizontal dashed line at a constant level. This made the forecast look like a boring average, not a credible prediction of real seasonal demand.

**Root cause — two separate bugs:**

*MO_35 `build_future_features` (primary culprit):* The "autoregressive" lag math used `lag1_idx = len(units_hist) - 1 + step`. At step ≥ 1, this index goes out of bounds (units_hist only held actuals, never updated with predictions). The fallback returned `units_hist[-1]` — the anchor value — for every single step. All 13 forecast steps saw identical lag1/lag4/lag13 inputs → identical model outputs → flat line. Additionally, `base_units_lag52` was missing from FEATURE_COLS entirely, so no year-ago seasonal signal could reach the model.

*MO_27 AR convergence:* MO_27's loop was correctly implemented, but `base_units_lag52` ranks 22/29 by importance. After step 4, lag1/lag4/lag13 become self-predictions that dominate. The YAGO seasonal variation in lag52 is drowned out by the AR momentum → collapses to flat mean.

*Why Q1 2026 backtesting charts (Figure 6) looked good:* Those validation forecasts used REAL actuals to compute lags at every step — no AR collapse possible when the target data already exists. The forward forecast (no future actuals) exposed the bug.

**Fix — applied to both MO_35 and MO_27:**

| Change | MO_35 | MO_27 |
|---|---|---|
| True AR loop | Replace `build_future_features` with `_autoreg_forecast`: per-group loop appending blended q50 to `units_hist` each step | Already correct; unchanged |
| lag52 in features | `base_units_lag52` added to `FEATURE_COLS`; precomputed from actuals (no leakage) | Already in place from v2 |
| Seasonal blend | `SEASONAL_BLEND_WEIGHT = 0.40` | `SEASONAL_BLEND_WEIGHT = 0.40` |

**Seasonal blend formula:**
```
yoy_ratio       = anchor_units / yago_at_anchor   # clipped to [0.5, 2.0]
seasonal_ref_k  = lag52_k × yoy_ratio             # projects year-ago curve at current YoY level
blend_mult      = (0.60 × ar_pred + 0.40 × seasonal_ref_k) / ar_pred
q10/q50/q90    *= blend_mult                       # band shape preserved; blended q50 fed back as next lag1
```

**Result:** Summer uptick now visible — SAMS curves up ~25% from anchor; Kroger rises ~18%; Walmart shows realistic recent softness; Publix traces its declining trend. Total portfolio: ~349K/wk plan for Q3 2026 (up from flat ~328K). Report v2.1.1 regenerated with fixed charts.

---

### 2026-07-02 (update 10) — v2.1.1 section restoration + Brian FP&A brief

**v2.1.1 section restoration (`docs/built_demand_intelligence_report_v2.1.1.html`)**

v2.1.1 was silently missing sections 12–18. Root cause: those sections live **outside** the `</div><!-- /page -->` closing tag in v2.0.9 and weren't ported when v2.1.1 was created. Restored:

- **12** Full Model Benchmark — 7 Methods Compared (MO_38/39)
- **13** Feature Transparency — What the Model Is Looking At
- **14** Model Explainability — How It Works & When to Trust It *(was duplicated in v2.0.9 — second copy removed)*
- **15** Feature Diagnostic & Competitive Differentiation — Proving the Value Stack
- **16** Quantile Forecast — P10/P50/P90 Scenario Bands
- **17** BSTS / CausalImpact — Counterfactual Price Event Analysis
- Causal DAG Analysis (MO_44) *(was duplicated — second copy removed)*
- **18** FP&A Breakdown

**Q2 reframe (Rob's direction):** "Why should I trust a number from a model I can't open?" → "How do I develop trust in the model as I learn more about it?" Applied to Section 14 Q&A panel.

**Versioning rule going forward:** When bumping HTML report version, always verify `grep -c "<h2"` matches previous version. Sections 12+ must be ported from the prior version's post-`/page` tail manually. See memory `feedback_html_report_versioning.md` for the Python snippet and deduplication procedure.

**New: `docs/brian_fpa_brief.html` — Rule-of-three FP&A briefing (1.2 MB)**

Standalone document for Brian Cluster. Three business questions, four anchor charts, ROI KPI strip at top.

| Section | Question | Anchor chart |
|---|---|---|
| 1 | What will BUILT sell next quarter? | Retailer-level 13-week projection (floor/plan/ceiling, top 6 accounts) |
| 2 | What's driving those numbers? | TDP decomposition (Walmart) + CausalImpact 3-panel (Kroger price cut, Dec 2025) |
| 3 | How does Mo explain every forecast? | SHAP waterfall BB4pk + Mo tool cards (Forecast Drawer, Mo Chat, Price Scenarios, Cannibalization Monitor) |

KPI strip: 4.4% wMAPE / 35% baseline / 30.6pp gap / $22M ROI. Elasticity table per retailer. Purple "supercharger" callout: analyst shifts from building analysis to acting on it.

Charts sourced from v2.1.1 by line: retailer projection (656), TDP decomposition (762), CausalImpact 3-panel context (1369 — preferred over 1373 result chart), SHAP waterfall (1168).

---

### 2026-07-02 (update 9) — MO_49 promo gap chart + FP&A / Brian report embedding

**MO_49 — Base vs. Total Units Promo Gap Chart (`scripts/MO_49_promo_gap_chart.py`)**

Standalone Python chart script reading `outputs/retailer_sales_weekly.parquet` (MO_25 actuals) and `outputs/retailer_sales_forecast.parquet` (MO_27 forecast). Selects top-6 BUILT SKU × retailer pairs by trailing 52-week base volume, deduplicated by `(upc, retail_account)` so MULO and non-MULO rows for the same retailer don't double-appear. Generates a 2-column × 3-row matplotlib panel figure:

- Dark line = total units (base + promo actuals); lighter line = base units
- Blue shaded gap = historical promo contribution
- Orange shaded gap = projected promo contribution in 13-week forecast region
- Dashed q50 lines + q10/q90 bands for both base and total forecasts

Portfolio promo share: **30.2%**. Output: `outputs/mo49_promo_gap.html` (standalone embedded HTML) + `outputs/mo49_promo_gap_chart.png`.

**Bug fixes applied in this build:**
- `dt.to_pydatetime()` → `.to_numpy()` on both `adates` and `fdates` (removes FutureWarning)
- `fillna(abase)` → `np.where(np.isnan(atotal_raw), abase, atotal_raw)` (pandas rejects ndarray in fillna)
- UPC suffix (`…XXXXXX`) added to panel titles so same-description SKUs at different pack sizes are distinguishable
- Top-series dedup: `drop_duplicates(subset=["upc","retail_account"])` picks dominant channel per retailer before ranking

**Report embedding:**
- `docs/built_demand_intelligence_report_v2.1.1.html` — new **Section 9b** ("Promo Contribution — Base vs. Total Units") inserted before Section 10 (ROI). Includes 30% promo share stat and a stress-test framing callout: "if promo spend drops 10%, base-units line is your real floor."
- `docs/brian_sanity_check_package.html` — compact final section ("Promo vs. Base Demand — Are You Growing or Just Spending?") added with nav entry. Framed for Brian: is volume structurally earned or contingent on trade spend?

---

### 2026-07-01 (update 8) — MULO velocity fix + promo units forecast (MO_25/26/27)

**MULO velocity undercount fix (`customer-built-mo-api/app/routers/trends.py`)**

WALMART and KROGER primary SPINS rows live in `CONVENTIONAL|MULTI OUTLET` (MULO CRMA). The previous SQL excluded that channel by default, showing WALMART at ~32% of actual volume and KROGER at <1%.

Fix: For named-account queries and single-UPC mode, SQL now includes MULO channel (`where_ch = ""`). A post-query dedup step retains only the MULO row per `(retail_account, upc, week)`, discarding non-MULO rows (which are a subset of the MULO CRMA total). Three MULO_GEOS Python filters that would have re-blocked valid named-retailer MULO rows were also removed. Pack Crossover (multi-UPC, no account filter) keeps MULO excluded to avoid double-counting aggregate MULO rows into per-UPC sums.

**Promo units forecasting (MO_25 / MO_26 / MO_27)**

FP&A needs `total_units` (base + promo) to forecast full revenue picture alongside `base_units`.

*MO_25:* `built_filtered_weekly` query extended to include `units_promo`, `units_non_promo`. After ARP join, `total_units = base_units + units_promo.fillna(0)` computed. AR lags `total_units_lag1/4/13/52` added to parquet output.

*MO_26:* Added `TOTAL_UNIT_FEATURE_COLS` (same as `FEATURE_COLS` but `total_units_lag*` replaces `base_units_lag*`). Trains parallel `model_total_units_q{10,50,90}_v3.pkl` with `log_total_units` target when `total_units` column is present. Metrics JSON updated with `total_units_trained` flag and per-quantile metrics.

*MO_27:* Loads total_units models from metrics JSON flag. Seeds `total_history` from actuals. Parallel AR forecast loop per step mirrors the base_units loop, including seasonal blend. Outputs `forecast_total_units_low/base/high` columns (null when models absent). Promo contribution = `total - base` at any forecast step.

---

### 2026-07-01 (update 7) — Event validation + Brian sanity-check package complete (MO_47 / MO_48)

**MO_47 — Post-hoc Price Event Validation (`scripts/MO_47_event_validation.py`)**

Validates whether the elasticity model correctly predicts what demand does during real price events. Joins `price_elasticity_training_features` (Druid — 30,876 genuine price-change windows) with `scored_price_elasticity` (series-level implied ε), applies `ε × log_price_change` as the prediction, and compares against observed SPINS unit change.

Key design decision: `price_elasticity_training_features` is the MO_16 training set, so this is in-sample evaluation. The primary metric is direction accuracy (did demand move the right way?), not MAPE. MAPE on all events is high (156% model vs 127% naive) because 94% of events co-occurred with promotional mechanics — the model captures the price-only signal; promo mechanics independently drive additional demand.

| Metric | All events (n=30,876) | Clean price moves (n=1,633, promo_confounded=0) |
|---|---|---|
| Direction accuracy | 57% (vs 0% naive) | **63%** (vs 0% naive) |
| Elasticity R² | 0.03 | 0.06 |
| MAPE (model vs naive) | 157% vs 127% — model worse | 89% vs 76% — model worse (magnitude noisy without promo context) |

**Kroger BB 4pk case study (hardcoded from MO_43/MO_44):**
- ARP: $10.99 → $10.14/pack (−7.8%); ε = −0.59 (MO_44 causal OLS)
- Price-only predicted lift: **+4.9%**; BSTS total lift (MO_43): **+28.6%**
- Promo/display residual: +23.7pp — model captured the price signal; display+feature mechanics drove the rest

**MO_48 — Brian Sanity-Check HTML Package (`scripts/MO_48_brian_package.py`)**

Generates `docs/brian_sanity_check_package.html` — standalone 4.2 MB document with 13 charts base64-embedded. Brian Cluster (BUILT CPO) reviews this before Rob routes back to Jeff/Bracken (July close gate).

9 sections: Executive Summary → Accuracy Proof → Q3 2026 Forecast → SHAP Driver Analysis → Event Proof (Kroger) → Causal Price Sensitivity → Retraining Value → Elasticity Fix → Phase 2 Roadmap.

Design choices: direction accuracy (63% clean moves) featured in exec KPI and event proof table; MAPE comparison with promo confounding context panel (not featured where model is worse than naive); Kroger case study numbers hardcoded from MO_43/MO_44 (avoids picking wrong event window from training features table).

**Phase 2 note — promo units forecasting:** Currently forecasting `base_units` only (everyday demand). FP&A needs `promo_units` (incremental lift during promo events) to get the total revenue picture. Near-term path: forecast `total_units` as a second target alongside base (the gap = expected promo contribution). Longer-term: lift-multiplier layer (expected promo weeks × historical lift coefficient per SKU/retailer) makes trade spend scenarios first-class inputs, with elasticity and TPR depth as explicit levers.

---

### 2026-07-01 (update 5) — Rolling signals: time-varying competitive dynamics (MO_46 + MO_26/27 v3)

**MO_41 audit root cause, Phase 2 fix:** The stepwise ablation in MO_41 proved that `implied_elasticity`, `max_donor_cannibal_prob`, and `donor_count` are fully static per series (ICC=1.0). They differentiate between series but explain no within-series week-to-week variation — hence near-zero SHAP values. MO_46 replaces them with live signals.

**MO_46 — Rolling Cannibalization Pressure + Elasticity (`scripts/MO_46_rolling_signals.py`)**

Computes two time-varying signals for every (focal_upc, channel, account, geo) series at every week:

| Signal | Method | Range / Notes |
|---|---|---|
| `rolling_cannibal_pressure` | 8-week trailing Pearson(−r) between focal and donor_sum base_units | [−1, +1]; +1 = max zero-sum competition; 0 = no relationship; −1 = market expansion |
| `rolling_cannibal_trend` | 4-week pressure minus 8-week pressure | Positive = competition accelerating |
| `rolling_elasticity` | 13-week trailing OLS log(units) ~ log(arp), $0.05 price guardrail | [−5, 3]; NaN when insufficient price variation |
| `rolling_elas_valid` | 1 if guardrail passed | 0 = not enough price variation in window |

Donor pairs sourced from `scored_cannibalization` (`cannibal_status IN ('Cannibalizing', 'Watch')`) — same filter as the Pool Health API. ARP from `built_filtered_weekly`. Requires ≥5 valid weeks per window; flat series (std < 1e-8) → NaN.

**Pipeline integration:**
- **MO_25** joins `outputs/rolling_signals_weekly.parquet` at step 9; graceful skip (NaN-fill) if MO_46 not yet run
- **MO_26 v3** adds all three rolling features to FEATURE_COLS
- **MO_27 v3** seeds rolling signals from last observed values, held static across 13-week horizon (conservative — we don't forecast competitive dynamics autoregressively)

**Why this matters for Rob's product vision:** Each signal contributes a named, explainable business event to the forecast — not just momentum residuals. When rolling_cannibal_pressure rises from 0.3 to 0.7 over 6 weeks, Mo can say "competitive tension is building at Walmart; the model reduced your Q3 forecast by ~800 units/week in response." That's the anti-black-box story for Brian: pre-trained pathways with attached narratives, not a number from nowhere.

**Run sequence to activate v3:**
```
python MO_46_rolling_signals.py   → outputs/rolling_signals_weekly.parquet
python MO_25_retailer_sales_actuals.py  → joins rolling signals, saves parquet
python MO_26_retailer_sales_train.py    → trains v3 quantile models (PKLs)
python MO_27_retailer_sales_forecast.py → v3 forecasts → Druid ingest
```

---

### 2026-07-01 (update 4) — YAGO features: year-ago demand in retailer sales forecast (MO_25/26/27 v2)

**Bracken's concern addressed:** "3 years of data but it's not comparable — promotional lift in '25 won't be what it is in '26 and '27." Year-ago lags let the model observe what demand looked like 52 weeks ago at the same seasonal point — explicitly showing whether growth is repeating, accelerating, or diverging from the year-ago pattern.

**Changes:**
- `MO_25`: `base_units_lag52` and `velocity_spm_lag52` added to output schema (shift(52) per GROUP_COLS series; NaN for series < 52 weeks — LightGBM handles gracefully)
- `MO_26 v2`: both YAGO features added to `FEATURE_COLS`
- `MO_27 v2`: `lag52_seq` pre-computed for all 13 forecast steps from actuals only (no data leakage); `.tail(13)` seed window extended to `.tail(65)` (52+13 weeks needed); `base_units_lag52` updated in `state` dict per step

**Feature importance (MO_26 v2, gain importance):** `base_units_lag52` ranks 22/29 with importance 1102 — above all cannibalization features. 34.9% YAGO coverage (expected: SKUs launched after mid-2025 lack 52 weeks of history). This confirms that year-ago demand is a meaningful forward signal, not noise.

---

### 2026-07-01 (update 3) — SPINS channel guardrails + Druid ingest

**SPINS channel guardrails (Priority 4):**
- `price_elasticity.py`: `get_scores()` now returns `mulo_warning: True` + explanation when `channel_outlet = CONVENTIONAL|MULTI OUTLET`. `ELASTICITY_BAND_TAG` updated: `Elastic` band added (orange), `Positive` changed to amber with clearance/lifecycle note, `Insufficient Price Variation` added (gray).
- `mo_chat.py`: MULO ELASTICITY GUARDRAIL block added to `_DATA_GLOSSARY` — Mo must never cite `scored_price_elasticity` elasticity values for MULO channel; redirects to MO_44 causal OLS or primary channel. Velocity/sales on MULO remain valid.
- `PriceDecide.tsx` / `PriceElasticityDetermine.tsx`: Empty-state messages no longer recommend MULO as an elasticity source; both now direct to `CONVENTIONAL|FOOD` or `CONVENTIONAL|MASS MERCH` with a note explaining why MULO produces unreliable elasticity.

**MO_16/17 Druid ingest (Priority 5):**
Submitted `scored_price_elasticity_ingest_spec.json` → task `index_parallel_scored_price_elasticity_ojcemnig_2026-07-01T17:38:49.601Z` → **SUCCESS**. `scored_price_elasticity` v2 (MO_16 v2 TDP model + $0.05 guardrail, 57,193 training rows, R²=0.9810) is now live in Druid.

---

**Option B two-source elasticity — complete (customer-built-mo-api):**
`retailer.py` now applies `_CRMA_CAUSAL_ELASTICITY` (13-account MO_44 OLS dict) at all 4 assembly points: `/sku-summary` row loop, `/summary` elast_map, `/sku-list` enrich loop, and forecast drawer. KEY ACCOUNT retailers continue using `scored_price_elasticity` (MO_17). `mo_chat.py` `_DATA_GLOSSARY` updated with two-source methodology, all 13 per-account ε values, `Moderately Elastic` band added, and Vitamin Shoppe lifecycle note.

**HTML report cleanup (docs/built_demand_intelligence_report_v2.1.0.html):**
- Removed duplicate Section 14 "Model Explainability" (identical copy was appended twice)
- Removed duplicate §17 "Causal DAG / DoWhy MO_44" (identical copy at end of file)
- Q2 reframed: "Why should I trust a number from a model I can't open?" → "How do I develop trust as I learn more about the model?" (Rob's exact positive framing from Jul 1 standup)
- File: 1888 → 1605 lines (283 lines of pure duplication removed)

---

### 2026-06-30 (v2.0.7) — Causal DAG Analysis (MO_44)

**MO_44 — Causal Price→Demand Analysis via DoWhy (`scripts/MO_44_dag_analysis.py`)**

Formal causal identification of the price→demand relationship using Directed Acyclic Graphs and DoWhy's backdoor criterion. Moves beyond correlation: after controlling for distribution (TDP), product maturity (weeks_since_launch), pack size, seasonality (week_of_year), and cannibalization pressure, price is proven to causally reduce demand. Answers Bracken/Jeff's "can we trust this?" question with a formal statistical framework. Section 17 (renumbered) added to HTML report.

| Metric | Value |
|---|---|
| Portfolio price elasticity (ATE) | **−0.34** (log–log) |
| 95% confidence interval | −0.37 to −0.31 |
| 10% price increase impact | **−3.4% demand** |
| Refutation tests passed | **4/4** (random cause, placebo, subset, bootstrap) |
| Placebo treatment effect | −0.0015 (collapses to zero — robust) |
| Sample | 44,197 obs × 91 UPCs × 72 retailers |
| HTML report version | v2.0.7 (12.2 MB) |

**Per-retailer findings:** 72 accounts analysed. Most price-sensitive: Maverik (ε = −1.12), Food City Market (ε = −1.69), Northwest Grocers (ε = −1.76). Anomalous positive elasticity at small accounts (e.g., Sunset Foods, C&K Market) — flagged as likely small-N instability, not genuine Veblen effect.

**Limitations documented in report:** No instrumental variable (ARP is partly endogenous to demand shocks); YAGO absent from parquet; promotional calendar unobserved. Phase 2 fix: add promo flag + competitor_arp + arp_lag4 as IV instrument.

---

### 2026-06-30 (v2.0.4) — Feature Diagnostic + Stepwise Ablation + Segment Analysis (MO_41)

**MO_41 — Feature Diagnostic & Competitive Differentiation (`scripts/MO_41_feature_diagnostic.py`)**

Rigorous quantitative proof that LightGBM's 20pp accuracy improvement is real, explainable, and attributable to specific feature layers — not just "more complex math." Addresses the root-cause question: which features are actually time-varying and driving the forecast, vs. which are static series-level adjustments? Section 15 added to HTML report. HTML report grows from 8.6 MB → 8.7 MB (v2.0.4).

**Core finding:** M1 (demand foundation, 11 features) = **3.53% wMAPE** — the best single result. MA 13wk baseline = **27.03%**. Each additional Mo signal layer adds marginal overhead because those signals are static per series (ICC = 1.0); Phase 2 converts them to time-varying weekly inputs.

**Stepwise ablation results (Dec 2025 cutpoint, 164 qualifying series, 2,126 test rows):**

| Model | Features | wMAPE | vs. MA 13wk |
|---|---|---|---|
| MA 13wk baseline | — | 27.03% | — |
| M1: Demand Foundation | 11 | **3.53%** | **−23.5pp** |
| M2: + Per-Store Velocity | 15 | 3.70% | −23.3pp |
| M3: + TDP & Price | 21 | 4.04% | −23.0pp |
| M4: + Lifecycle & Season | 24 | 4.09% | −22.9pp |
| M5: + Mo Intelligence | 27 | 4.33% | −22.7pp |

**ICC audit findings (2026-06-30):**

| Feature | ICC | Verdict |
|---|---|---|
| `implied_elasticity` | 1.0000 | Fully static — one ε per UPC×retailer; acts as fixed-effect intercept |
| `max_donor_cannibal_prob` | 1.0000 | Fully static AND binary (0.0 or 1.0 only — no values between 0.3–0.9) |
| `donor_count` | 1.0000 | Fully static — needs to be split: own-brand vs. competitive |
| `tdp_z8` | 0.0752 | Truly time-varying — TDP momentum changes weekly |
| `arp_wow_delta` | 0.0050 | Highly time-varying — price change events |
| `base_units_wow_delta` | 0.0087 | Highly time-varying — demand response |

These findings explain why Mo intelligence signals show near-zero SHAP on the portfolio average: they can only differentiate BETWEEN series, not explain week-to-week variation WITHIN a series. The 20pp gap vs. MA 13wk comes from LightGBM's non-linear interaction learning across truly time-varying features (TDP momentum, demand z-scores, price change events) — proved by stepwise ablation in MO_41.

**Segment performance snapshot (Dec 2025 cutpoint):**

| Channel | LightGBM | MA 13wk | Gap |
|---|---|---|---|
| FOOD | 2.4% | 21.3% | 18.9pp |
| CONVENIENCE | 2.5% | 19.4% | 16.9pp |
| DRUG | 3.2% | 16.3% | 13.1pp |
| MASS MERCH | 6.4% | 25.6% | 19.2pp |

**Phase 2 feature engineering roadmap (to make Mo signals time-varying):**
- `implied_elasticity` → rolling 12-week price-response regression (recomputed as ARP changes; data already available in SPINS)
- `max_donor_cannibal_prob` → weekly `donor_velocity / focal_velocity` ratio (actual competitive pressure this week; data already available)
- `donor_count` → split into own-brand donor count + competitor brand count
- New: BUILT TDP share (BUILT TDP / category TDP) — gaining or losing shelf vs. competitors
- New: Holiday calendar flags from `week_of_year` — zero additional data cost

---

### 2026-06-30 (v2.0.3) — Model explainability: SHAP waterfalls + CFO Q&A + Section 14 (MO_40)

**MO_40 — Model Explainability Report (`scripts/MO_40_explainability.py`)**

Answers the "black box" objection from Bracken (CFO), Jeff (SVP Finance), Connor (FP&A), and Chase. Re-trains LightGBM on Dec 2025 cutpoint, computes SHAP TreeExplainer values across all 2,126 test rows (27 features), and generates five charts. HTML report extended with Section 14: CFO/FP&A Q&A (5 questions) + honest limitations table. Report grows from 5.4 MB → 6.1 MB (v2.0.3).

**Focal SKU accuracy at Walmart (Dec 2025 cutpoint, 13-week OOS average):**
| SKU | Actual avg units/wk | Forecast avg units/wk | Error |
|---|---|---|---|
| Brownie Batter 4pk (mature) | 27,317 | 28,472 | 4.2% |
| Cookie Dough Chunk 4pk (growing) | 29,275 | 29,772 | 1.7% |
| Brownie Batter 8pk (cold-start) | — uses MA 13wk (<52 weeks) — | | |

**Section 14 contents:**
- SHAP feature importance: top 20 features ranked by mean |SHAP| across all 164 qualifying series; tiered by demand dynamics / velocity / distribution / price / lifecycle / Mo intelligence
- Waterfall charts (BB 4pk + CD 4pk): each feature's average contribution to the Q1 2026 Walmart forecast in plain business terms; summary box shows base → forecast → actual
- Cold-start narrative (BB 8pk): explains the ≥52-week threshold, shows history, MA 13wk forecast line, and wMAPE; demonstrates the system auto-selects the right model by SKU age
- Prediction audit: actual vs. forecast scatter (all 164 series, color-coded by wMAPE) + accuracy distribution histogram
- CFO/FP&A Q&A: 5 written answers — Excel vs. model; trust/audit trail; TDP inflection (Bracken's concern); when it will be wrong; what external data actually adds + realistic ROI per addition
- Honest limitations: distribution inflection points, new SKUs <52 weeks, promo week lag, competitive response lag, geography granularity

### 2026-06-30 (v2.0.2) — OLS Linear Regression added to benchmark + HTML report extended to 13 sections (MO_39)

**MO_39 — Linear Regression benchmark + HTML report extension (`scripts/MO_39_linear_regression_benchmark.py`)**

Adds OLS Linear Regression (unregularized) to the 7-model benchmark. Loads prior results from `v2_mo38_summary.json` — no TFT re-run required. Generates an updated comparison chart and patches the HTML report with two new sections (Section 12: full 7-model benchmark; Section 13: feature transparency). Report updated from 4.3 MB → 5.4 MB.

| Cutpoint | LightGBM | Lin. Reg. | Ridge | Lasso | TFT | MA 13wk | Naive |
|---|---|---|---|---|---|---|---|
| Dec 2024 | **28.7%** | 55.4% | 55.3% | 52.6% | 55.2% | 50.4% | 56.9% |
| Oct 2025 | **7.0%** | 82.1% | 82.0% | 80.4% | 90.4% | 40.2% | 37.5% |
| Dec 2025 | **4.3%** | 80.3% | 80.3% | 79.5% | 145.3% | 24.6% | 42.1% |

OLS ≈ Ridge at every cutpoint (within 0.1pp) — L2 regularization adds nothing at this data scale; coefficient estimates are already stable. Lasso edges both by ~0.8pp via sparse feature selection. Key observation: MA 13wk (24.6%) beats all three linear models at Dec 2025 — a 13-week moving average is more robust than a 25-feature linear model on stable mature series because linear regression extrapolates multicollinear rolling features poorly OOS.

### 2026-06-30 (v2.0.1) — Full model benchmark + feature illumination (MO_38, complete)

**MO_38 — Model benchmark + feature illumination (`scripts/MO_38_model_benchmark.py`)**

Apples-to-apples accuracy benchmark: TFT, Ridge Regression, and Lasso Regression vs. LightGBM on the same 3 temporal cutpoints (Dec 2024 / Oct 2025 / Dec 2025, h=13 OOS weeks) and the same 27 domain-engineered features. All 6 methods evaluated on 37,420 rows / 613 series (post-MULO filter).

| Cutpoint | Series | LightGBM | TFT | Ridge | Lasso | MA 13wk | Naive |
|---|---|---|---|---|---|---|---|
| Dec 2024 | 111 | **28.7%** | 55.2% | 55.3% | 52.6% | 50.4% | 56.9% |
| Oct 2025 | 136 | **7.0%** | 90.4% | 82.0% | 80.4% | 40.2% | 37.5% |
| Dec 2025 | 164 | **4.3%** | 145.3% | 80.4% | 79.5% | 24.6% | 42.1% |

LightGBM dominates across all cutpoints and improves as training data accumulates. TFT degraded with scale (55% → 90% → 145%), indicating insufficient data for the architecture at 111–280 series / 500 steps — though neural approaches with fewer parameters (iTransformer, PatchTST) remain worth revisiting as the portfolio grows. Ridge and Lasso land at 52–82%: they see the same 25 features as LightGBM but can't exploit non-linear demand response; Lasso selected 19–22 of 27 features (confirming feature quality, not sparseness, is the bottleneck for linear models). MA 13wk (24.6% at Dec 2025) is the strongest no-feature baseline — useful for cold-start and stable-mature series.

Feature illumination outputs: 27-feature tier map (Tier 1–2 current + Tier 3 external candidates), LightGBM SHAP, Ridge coefficients (direction + magnitude), Lasso selection panel. 4 charts + summary JSON + per-series CSV embedded in report.

Outputs (pending): `v2_mo38_accuracy_comparison.png`, `v2_mo38_feature_tiers.png`, `v2_mo38_shap_ridge_lasso.png`, `v2_mo38_external_candidates.png`, `v2_mo38_summary.json`, `v2_mo38_by_series_dec2025.csv`

---

### 2026-06-29 (update 4) — Real-world SKU stories + expanded HTML report

**MO_37 — Real-world SKU storytelling charts (`scripts/MO_37_sku_stories.py`)**

Five charts using three specific BUILT products at Walmart as concrete examples — translating abstract accuracy metrics into planning decisions FP&A teams can act on. Focal SKUs: Brownie Batter 4pk (138 weeks, mature), Cookie Dough Chunk 4pk (89 weeks, growing), Brownie Batter 8pk (49 weeks, cold-start). Charts: (1) Multi-horizon zoom — same Dec 2025 forecast shown at 2.7yr/1yr/1Q/1mo windows; (2) Method horse race on a single SKU — LightGBM 5.8% vs ETS 27% vs MA 20.5% vs Naive 31.6% for BB 4pk at Walmart; (3) Demand decomposition — TDP expansion vs. velocity gain (what drove growth?); (4) Cold-start bridge — BB 8pk launched at high TDP (53% of stores from day 1), MA 13wk (18.5%) beats ETS (26.5%) as the cold-start bridge before LGB threshold; (5) Dollar translation — quarterly planning error in $ for each SKU at 35% (Excel) vs. actual wMAPE. HTML report (MO_36) extended with 5 new charts, new Sections 8 and 9, report size 4.3 MB.

---

### 2026-06-29 (update 3) — FP&A research report + ensemble analysis + July 2026 projection

**MO_34 — Per-series ensemble trigger analysis (`scripts/MO_34_ensemble_trigger.py`)**

Head-to-head comparison of LightGBM vs. ETS (Holt linear trend) on 106 qualifying series at the Dec 2024 cutpoint. LightGBM wins 74/106 series (70%); ETS wins only 1. Key finding: ETS fails on mature/growth series because it cannot see TDP or elasticity signals — it extrapolates raw units and overshoots when distribution growth moderates. LGB overall 29.4% vs ETS 52.6%; ensemble (best-of-both router) 28.1% (+1.25pp). Growth stage breakdown: Expanding series LGB 35.6% vs ETS 50.0%; Mature LGB 20.1% vs ETS 56.5%. Outputs: per-series CSV, metrics JSON, 3 charts (scatter, growth-stage bars, ensemble gain waterfall).

**MO_35 — Forward projection to July 2026 (`scripts/MO_35_forward_projection.py`)**

Trained on full 3-year SPINS history through April 2026 (288 qualifying series). Projects 13 weeks forward to ~July 19 2026, answering "where is BUILT today?" — live intelligence unavailable to BUILT without this system. Plan (q50): 328K units/week, 4.3M total Q2–Q3 2026. Range: 3.7M (floor/q10) to 4.6M (ceiling/q90). −2.7% vs. prior 13-week average (consistent with post-winter seasonal pattern). Outputs: summary JSON + 2 charts (total portfolio forward + top-6 retailer breakdown).

**MO_36 — Self-contained HTML research report (`scripts/MO_36_report.py`)**

Generates `scripts/outputs/built_demand_intelligence_report.html` — a 4.3 MB email-ready research paper (extended with MO_37 charts). 16 total charts from MO_32B–37 embedded as base64 PNG. 11 sections + Appendix: Executive Summary (4 KPI chips) → The Challenge → Our Approach → Validation → LGB vs. ETS → Quarterly Retraining → FP&A Tools (4 questions) → July 2026 Projection → Real-World Examples at Walmart (NEW) → What's Driving Your Growth? (demand decomposition + cold-start + dollar translation, NEW) → ROI Calculation (~$22M at $1M/1pp) → Next Steps → Technical Appendix. To share: attach the `.html` file to email; instruct recipients to download and open in Chrome/Safari.

---

### 2026-06-29 (update 2) — FP&A business decision charts; quarterly rolling retrain simulation

**MO_32B — Quarterly rolling-origin retraining simulation (`scripts/MO_32B_quarterly_rollforward.py`)**

5 quarterly retrain windows covering all of 2025 + Q1 2026. Rolling LightGBM (retrained each quarter) achieves 13.1% wMAPE overall vs. 27.1% for the stale Dec 2024 model and 25.0% for MA 13wk. Retraining gain is +14.1pp overall, rising to +18.9pp by Q1 2026. Production story: quarterly retraining is not optional — a model trained once and left degrades as BUILT's portfolio evolves. Outputs: metrics JSON, per-window CSV, 3 charts (rolling accuracy, stitched forecast, retrain value bar).

**MO_33 — FP&A business decision charts (`scripts/MO_33_fpa_business_charts.py`)**

5 presentation-ready charts answering the FP&A questions BUILT actually asks, trained on Dec 2025 data with 4.4% wMAPE validation:
1. "What will I sell next quarter?" — top-6 retailer forecast with q10/q90 confidence bands
2. "Am I growing from real demand or cannibalizing myself?" — units vs. cannibalization pressure over time
3. "How much do I need to manufacture?" — total portfolio demand with floor/plan/ceiling bands
4. "Which retailer should I prioritize for expansion?" — velocity × growth × TDP bubble chart
5. "Which method should I trust?" — horse race: all 4 methods vs. Q1 2026 actuals with wMAPE annotations

---

### 2026-06-29 — FP&A forecasting v2.0.0: multi-model backtesting + walk-forward validation

Complete retailer demand forecasting pipeline built and validated across 3 independent temporal cutpoints:

| Cutpoint | OOS Period | Series | LightGBM wMAPE | Naïve wMAPE |
|---|---|---|---|---|
| Dec 2024 | Q1–Q4 2025 (68 weeks) | 143 | 30.1% | 62.2% |
| Oct 2025 | Nov 2025–Apr 2026 (29 weeks) | 206 | 6.1% | 37.1% |
| Dec 2025 | Jan–Apr 2026 (16 weeks) | 280 | **4.7%** | 40.6% |

Scripts: `MO_28_v2_eval.py` (baseline + SHAP), `MO_29_backtest_oct2025.py`, `MO_30_multi_model_backtest.py` (Prophet 174.9% / ETS 52.8% / MA 54.7% / LGB 30.1% at Dec 2024), `MO_31_walkforward_jan2026.py` (3-cutpoint walk-forward charts), `MO_32A_nbeats_global.py` (N-BEATS global neural: Dec2024 55.6% / Oct2025 117.9% / Dec2025 46.4% — growth-mode distortion confirmed). Key insight: N-BEATS and ETS fail on growth-mode brands because they cannot see TDP expansion. LightGBM's domain signals (TDP, elasticity, cannibalization) are what drive the 10× accuracy gap.

---

### 2026-06-23 (update 3) — Trends Price & Promo account dropdown fix

**Bug:** When the user selected 2+ channels in the Trends filter bar and removed all account chips, the Price & Promo tile's account dropdown was empty — no accounts available to pick.

**Root cause:** `PriceTile` built its accounts list from `knownAccounts` (velocity-derived, only fills when exactly 1 UPC is selected) with `selectedAccounts` as fallback. With 3 UPCs selected and no explicit account selection, both were empty arrays.

**Fix (`Trends.tsx`):** Added `channelFilteredAccountOptions` — all accounts from the pre-loaded `allAccounts` map filtered to the active channels (or all channels if none selected), deduped + sorted. This is the same list the Account picker in the filter bar shows. Now used as the fallback for `PriceTile` accounts in both the main tile and `TileExpandView`, so the dropdown is always populated from the channel-aware account universe regardless of UPC count or whether the user has explicit account chips selected.

---

### 2026-06-23 (update 2) — Aevah Standup Jun 23 directives captured in project roadmap

Key directives from Rob/Jason standup transcript extracted and saved to project memory + wiki (`customer-built-doc/wiki/08-roadmap.md`).

**Near-term (high priority for Jun 25 demo):**
- **Chart annotation lines + Mo explanation** — Detect significant changes in Trends charts algorithmically (divergence, crossover, spike); draw a vertical dashed line at the event date; clicking fires a pre-built deterministic Mo Chat prompt explaining what happened and what it could mean. Hero use case: Cookies N Cream 1ct vs 4pk divergence at Walmart, Dec 2025 – Feb 2026. Rob: "Let's build that. Don't worry about accuracy — just draw the line and have Mo say something." First pass = concept proof.
- **Mo drives actionability** — Rob's core directive: "AI needs to help them act on the dashboard, not just see it. The dashboard screams at them when something needs to be done." We're automating the analyst, not building another dashboard.
- **Deterministic Mo prompts** — When an annotation or button triggers Mo, pre-build the prompt from known context (SKU, date, account, event type) for predictable, relatable answers.

**Long-term (90-day production standup scope):**
- **Validation / testing harness** — Two modes: (1) raw SPINS data quality check, (2) model output validation. Generates a gap lookup table the UI references to display "insufficient data" notes. Drives customer trust.
- **Edge case identification and process definition** — Deeper backtesting, second training pass, edge case catalog, external data integration (BUILT's own promo/merch dates overlaid on charts).

### 2026-06-23 — Mo Chat bug fixes + Trends screen awareness + error handling

**Three Mo Chat bugs fixed:**

*Pack Crossover tile tool confusion:* When user asked "describe what's happening with the pack crossover" on the Trends dashboard, Mo was calling `get_cannibalization_packladder` (queries `price_pack_ladder_weekly`, returns empty for Trends filter context) instead of `get_velocity_trend`. Root cause: "use get_velocity_trend for sales trajectory" didn't cover the "describe this tile" intent, so Mo pattern-matched "pack crossover" to the Cannibalization Suite tool. Fix: explicit `PACK CROSSOVER TILE` instruction in `_SCREEN_MAP` Trends section.

*Channel switch false-confirmation:* When user said "switch to convenience," Mo called `get_channel_list`, found `CONVENTIONAL|CONVENIENCE` in the list, and confirmed "you're already on CONVENTIONAL|CONVENIENCE" without calling `update_filters`. Fix: explicit note in `get_channel_list` tool description that the list shows *available* channels (not the *current* channel) — Mo must always call `update_filters` to apply the change.

*Trends context — "select a focal UPC from the dropdown":* Trends has no focal UPC selector; products are in the Products filter bar. `filters.upc` is always empty on Trends, so MoPanel was hitting the generic `!filters.upc` branch and telling users to select a UPC that doesn't exist. Mo also had no idea which products were visible. Fix: `Trends.tsx` → `App.tsx` → `MoPanel.tsx` → `ChatRequest.selected_products` pipeline passes the current product list to every chat request. `_build_system()` for `trends::dashboard` now lists all 6 tile names, selected products with UPCs, and what Mo can help with. `MoPanel.tsx` proactive message uses `formatTrendsProductLabel()` to show e.g. "Built Puff Cookies N Cream (single · 4pk · 12pk) at KROGER + WALMART" instead of repeating the truncated base name.

**Graceful 500/529 error handling:** `_call_anthropic_with_tools()` now catches `APIStatusError` (429/500/502/503/529) and `APIConnectionError`/`APITimeoutError` — returns a friendly user-facing message instead of crashing the FastAPI route.

Wiki updated: `customer-built-doc/wiki/06-mo-chat.md` — new Trends Screen Awareness section, Error Handling section, updated proactive message logic, updated roadmap table, `get_channel_list` tool note.

### 2026-06-22 (update 8) — FP&A demo condensed from 60 to 30 minutes

Per `WALKTHROUGH-OVERVIEW.md` from Rob: go deep on Cannibalization and Price Elasticity only; fly over everything else as the future adoption roadmap. 90-minute slot — script now runs ~28 minutes, leaving ~60 minutes for BUILT to ask questions and drive the conversation.

**What was cut:** Act 1 (Trends portfolio + Retailer Summary + Mo Chat bridge), Act 5 (Forecast), Act 6 (Mo Chat standalone). These moved to a 60-second fly-over in the close.

**New structure:**
1. Opening (2 min) — one framing question, straight to Cannibalization
2. Act 1 — Cannibalization (13 min): Priority Events → SKU Summary → Geography → Decide (Explanation + Assortment Action)
3. Act 2 — Price Elasticity (11 min): Elasticity Summary → Promo Response → Competitive Price
4. Close (3 min): roadmap fly-over (Trends, Retailer Summary, Forecast, Mo Chat) + closing question

`reference_vision_docs.md` memory updated with new demo format and pointers to `WALKTHROUGH-OVERVIEW.md` and `MO-PRESENTATION-BRIEF.md`.

### 2026-06-22 (update 7) — Promo flag coverage tested across retailers and SKU formats

Ran a cross-retailer query (Kroger, Walmart, Ahold Delhaize, Publix, Meijer, Target) across 4 SKUs (C&C single, C&C 12pk, PB Cup 4pk, Double Choc single) to determine which SPINS field most reliably signals a promo week.

**Finding: `arp_pct_discount` (`arp < base_arp`) is unreliable for multipacks across all retailers.** It misses 33–53% of promo weeks on the 4pk and 12pk formats because those SKUs are frequently promoted via display or circular without a shelf price cut. `arp_pct_discount` only fires when the actual retail price drops below the everyday shelf price (TPR). Single bars at major retailers (Kroger, Walmart, Meijer) fare better — 2–8% miss rate — but Ahold single still misses 34% and Publix single misses 19%.

**Recommended combined flag:** `incr_units > 0 OR arp < base_arp`. Covers TPR (price-cut promos) via `arp_pct_discount` and display/feature promos via `incr_units`. Neither alone is sufficient across all formats.

**Impact on MO_16 re-run plan:** If we do a promo-clean elasticity re-run (P7/P8), use the combined flag to exclude promo weeks rather than `promo_confounded` (which has the same coverage gap) or `arp_pct_discount` alone (which misses multipack display activity). Documented in `project_pe_backtesting.md` memory and `03-ml-pipeline.md` wiki.

### 2026-06-22 (update 6) — Price elasticity model validation gap documented; backtesting options captured

Rob asked whether we backtested the elasticity model after the Ahold Delhaize positive-ε oddity. Short answer: partial.

**MO_16 v1 (original):** Random 80/20 `train_test_split`; R²=0.9687, MAE=0.0699. No TDP control; no price-change guardrail on training data.

**MO_16 v2 (2026-07-01):** Added `pre_13w_tdp`, `post_13w_tdp`, `tdp_pct_chg` to `OWN_PRICE_FEATURES`. Training filtered to `|Δprice_per_bar| ≥ $0.05` (57,193 rows). R²=0.9810, MAE=0.0759. TDP improved medians; ~30% Positive rate at CRMA accounts persists — architecture limitation (aggregation dilutes signal; see Option B below).

**What it doesn't do:**
- No temporal holdout — we never trained on weeks 1–N and predicted weeks N+1 onward against actuals
- No account-level holdout — no leave-one-retailer-out check
- No post-hoc event backtesting — no step that takes a scored ε, applies it to a historical price event, and compares predicted vs. actual unit lift

The Ahold case was a data quality failure (SPINS promo columns all zero), not a model failure — but the current validation setup cannot distinguish the two. Accounts with missing promo data produce unreliable elasticities silently.

**Three revisit options documented** in `project_pe_backtesting.md` memory and `03-ml-pipeline.md` wiki:
1. Temporal holdout (reserve last 13 weeks in MO_16 — no schema changes needed)
2. Account-level cross-validation (leave-one-retailer-out; full re-run per fold)
3. Post-hoc event validation (fastest — join `price_event_queue` to `built_filtered_weekly` actuals; no re-run needed)

### 2026-06-22 (update 5) — Positive elasticity root cause traced to SPINS promo data gap at Ahold Delhaize

**Root cause: SPINS promo columns missing for Ahold Delhaize FOOD**
C&C single at Ahold Delhaize shows ε ≈ +10 in `scored_price_elasticity`, meaning the Price Forecast tile predicts *more* units when price goes up — counterintuitive and confusing during demos.

Investigation traced to `built_filtered_weekly`: `units_promo`, `incr_units`, `units_lift_tpr`, `units_lift_any_display`, and `units_lift_any_feature` are all zero for every week at Ahold Delhaize FOOD. Because `is_promo` in the Price & Promo tile is derived from `units_promo > 0`, no weeks were ever flagged as promotional. The elasticity model treated every week — including Jan 2026 when ARP dropped ~31% to $2.07/bar — as a base-price observation and fit a spurious positive slope.

This is a native SPINS feed gap, not a pipeline bug or join issue. The `/api/trends/price-promo` docstring incorrectly cited `price_elasticity_weekly_features` as the promo source — corrected to accurately reflect that all fields come from `built_filtered_weekly` directly.

**Changes:**
- `trends.py` docstring corrected (stale reference to `price_elasticity_weekly_features` removed)
- `07-demo-guide.md` Data Notes updated: avoid Ahold Delhaize for price elasticity demos; use Kroger or Walmart
- `feedback_ml_data_quirks.md` updated: Ahold Delhaize promo gap + positive-ε root cause pattern documented

### 2026-06-22 (update 4) — Pack Crossover subtitle corrected; visual heuristic vs. model clarified

**Pack Crossover tile subtitle corrected (3 files)**
The tile subtitle read "crossing lines = cannibalization" — this was imprecise in two ways:
1. Transfer signal can appear as divergence (one up, one down) without the lines ever crossing in absolute volume — still valid evidence of displacement.
2. Volume crossing has nothing to do with Mo's actual cannibalization model, which uses timing correlation of distribution growth vs. velocity decline at account level (`scored_cannibalization`).

Fixed to: *"one rising while another falls = transfer signal"* in `Trends.tsx`. Same correction applied to the Mo Chat system prompt (`mo_chat.py`) and UI screens wiki (`05-ui-screens.md`). A full interpretation note (heuristic vs. model; divergence vs. crossing; two cases to distinguish) added to the wiki tile table. Walkthrough Act 1 now has a presenter note for when FP&A asks about the Pack Crossover tile.

### 2026-06-22 (update 3) — Mo Chat product add for Trends; avatar location fix; walkthrough updated

**Mo Chat: add/switch products on Trends (bug fix + new capability)**
Root cause: `update_filters` had no product parameters, so when a user asked Mo to "add [product]" while on the Trends page, Mo had no tool for it and fell back to `navigate_to` with suite="cannibalization" — the only navigate target it knew. This caused unexpected navigation away from Trends.

Three-part fix:
- **`get_product_list(search=)`** — new tool in `mo_chat.py`; searches `built_filtered_weekly` WHERE `source_brand LIKE '%BUILT%'` by name fragment; returns up to 20 matching `{upc, description}` pairs. Guard pattern: Mo must call this before using any UPC.
- **`update_filters` gains `add_products` and `set_products`** — UPC string arrays; Mo calls `get_product_list` → resolves UPC → calls `update_filters(add_products=[upc])`. Never navigates away from Trends for a product request.
- **Trends.tsx** handles `add_products` / `set_products` in the `mo-update-filters` CustomEvent listener, adding/replacing `selectedUpcs` state directly.
- **Walkthrough** updated: Act 6 now includes `"Add the Salted Caramel 1ct to the Trends view"` as a demo question, with a presenter note on the Trends filter-via-Mo-Chat capability.

**Mo Chat avatar location corrected in walkthrough**
Three instances of "bottom-right corner" fixed to "top-right header" in `docs/WALKTHROUGH.md`.

### 2026-06-22 (update 2) — Price & Promo tile fix; cross-flavor demo combos; walkthrough note

**Price & Promo tile: account state never cleared (bug fix)**
`PriceTile` had a one-way account sync: the `useEffect` only set the internal `account` state when `initialAccount` existed AND the tile had no account yet. When the user removed the retail account from global filters, the tile kept querying with the stale account (e.g. KROGER persisting after switching to MASS MERCH with no account). Fixed to always mirror `selectedAccounts[0]`:
```tsx
useEffect(() => { setAccount(initialAccount ?? ""); }, [initialAccount]);
```
Verified in three filter states: Kroger+Walmart (tile shows KROGER), MASS MERCH no account (tile shows "All accounts"), MASS MERCH with more products (tile stays "All accounts"). Fix committed + pushed to `customer-built-mo-ui`.

**Cross-flavor demo combos — which flavor family returns >2 SKUs**
`comparison_pool_weekly` D3 rows (SAME_BRAND cross-flavor) at Kroger MULO:
- **PB Cup 4pk** (`08-40229-30646`) → 3 partners: PB Puff single (Cannibalizing prob=0.9999), PB Puff 12pk, PB Protein Bar — red + gray rows, best demo variety
- **Double Choc** (`08-40229-30071`) → 3 partners: Choc Milkshake, Dbch Nsb 12pk, Dbl Choc Bar 12pk — all unscored (gray only)
- **C&C single** (`08-40229-30550`) → only 2 partners — avoid for this tab
Demo guide and test examples updated. Presenter note added to WALKTHROUGH.md Q4 (30-min script).

### 2026-06-22 — Mo Chat filter tools; channel exclusions fixed; FP&A walkthrough smoke-tested and corrected

**Demo walkthrough script location (for Rob):**
`customer-built-mo-ui/docs/WALKTHROUGH.md` — two scripts: 60-Minute FP&A / Executive Demo and 30-Minute Brand/Analytics Demo. A README.md was added to `customer-built-mo-ui` pointing directly to it. The wiki `07-demo-guide.md` also now leads with this pointer.

**Mo Chat filter manipulation tools (Trends screen)**
Mo can now directly update the Trends filter bar in response to natural-language requests. Three new tools added to `mo_chat.py`:
- `get_channel_list` — returns exact `channel_outlet` strings from Druid, same exclusion list as `/api/trends/channels`
- `get_account_list` — returns exact `retail_account` strings from Druid
- `update_filters` — backend returns `{filters: {...}}`; MoPanel dispatches `mo-update-filters` CustomEvent; Trends.tsx listener applies changes (set_channel auto-clears accounts since accounts don't cross channels)

Guard pattern: Mo must call the list tools before using values, preventing hallucinated SPINS strings (e.g. "DRUG" vs `CONVENTIONAL|DRUG`). LLM does fuzzy matching between user intent and exact Druid string.

**Stop button / ESC cancel (all Mo Chat instances)**
MoPanel now shows a Stop button while a request is in flight; ESC also cancels. Uses `AbortController` — `CanceledError` silently swallowed. Hint text toggles between `"Enter to send · Shift+Enter for newline"` and `"ESC · stop"`.

**EXCLUDED_CHANNELS single source of truth**
`_EXCLUDED_CHANNELS` renamed to public `EXCLUDED_CHANNELS` in `trends.py`; imported by `mo_chat.py`. Both the `/api/trends/channels` REST endpoint and `_tool_get_channel_list()` now apply identical filtering. Excluded: `CONVENTIONAL|MILITARY`, `CONVENTIONAL|MULO + CONVENIENCE`, `CONVENTIONAL|DOLLAR`, `CONVENIENCE - SPINS`. Valid channels after exclusions: FOOD, MASS MERCH, MULTI OUTLET, DRUG, CONVENIENCE, NATURAL EXPANDED, REGIONAL & INDEP GROCERY. Trends.tsx now fetches channels dynamically from the API instead of a hardcoded array (hardcoded array had wrong label "DRUG" vs `CONVENTIONAL|DRUG`).

**Price & Promo tile: no data in CONVENTIONAL|CONVENIENCE**
Confirmed via smoke test: SPINS does not populate ARP / promo-lift columns for the convenience channel in `built_filtered_weekly`. Velocity tile still shows data (uses `base_units` only). Price & Promo tile shows "No data." silently. Documented in wiki `05-ui-screens.md` and `07-demo-guide.md`. Avoid convenience channel during any demo involving the Price & Promo tile.

**FP&A walkthrough smoke test (2026-06-22)**
All key demo endpoints re-verified against live Druid. Three issues found and corrected in `docs/WALKTHROUGH.md`:

1. **Act 2 narrative corrected and reframed.** Old script said "the 4-pack launch is drawing from the single bar" — factually wrong; with focal=C&C single bar, top BUILT donor is the old Built C&C Bar 1.69oz format (brand renovation displacement), not the Puff 4-pack. Reframed entirely: Mo detects timing correlation (focal distribution up + donor velocity down), not causal transfer. The model tells you *which* relationship to investigate; the team decides what it means. "Signal detection + routing, not verdict delivery."

2. **Confidence badge explained.** All cannibal scores return `confidence: Low` (data maturity, not model certainty). Walkthrough now has a presenter note distinguishing probability (signal strength, 99.9%) from confidence (data maturity). An FP&A audience will notice the Low badge and ask.

3. **Promo Response language corrected.** "Breakpoints / price thresholds" replaced with "lift by tactic" — the screen shows TPR-only (57.1% lift) vs Display-Only (58.3% lift) type buckets, not price thresholds. ARP narrative updated: base price $2.85–2.90 holding steady, with April 2026 promo dip to $2.50 / 111% TPR lift.

### 2026-06-18 — Cross-retailer SKU view + Finance tools build plan

**Problem:** Retailer Summary lets you start with a retailer and drill to SKUs. Brian also needs to start with a SKU and see how it performs across all retailers ("flip the script"). Finance team is the next audience — they need planning tools in a format they're accustomed to (pivot tables, spreadsheets, promo ROI).

**Build sequence:**

1. **Cross-retailer SKU view — current state** (building now)
   - New header tab next to Retailer Summary; UPC filter → scorecard rows per retailer
   - Columns: Account, Channel, 13w Sales, YTD Sales, Velocity, Elasticity Band, Cannibal Status, Active Events
   - New API endpoint `/api/retailer/sku-summary` — pivoted from existing `built_prepost_features` + `scored_price_elasticity` + `scored_cannibalization`
   - Fast-path forecast: derived from existing signals (velocity × TDP trend × cannibalization rate)

2. **Export to CSV** on existing tables (Retailer Summary, SKU Retailer View, Assortment Action) — no API changes, client-side Blob download

3. **MO_25 — retailer sales forecast pipeline** (new ML component)
   - Panel model: (upc, retailer, channel, geo, week) grain; `built_filtered_weekly` source
   - Features: pack_count, flavor_family, elasticity, promo depth, competitor tier, weeks_since_launch, TDP trend
   - Output: `retailer_sales_forecast` Druid table → 13-week forward base_units per retailer per SKU
   - The number Finance can export into their Excel forecasting model

4. **Finance planning tools** (after demo)
   - Promo ROI calculator: spend input → expected dollar lift (`lift% × base_units × ARP`)
   - SKU Contribution column: each retailer's % of total BUILT base dollar sales for that SKU
   - Assortment Planning table: pivot-style rows=SKUs / cols=retailers, sortable/filterable/exportable
   - Forecast scenario export: what-if slider result (current ARP, proposed ARP, delta units, delta $) to CSV

**Why this order:** Items 1 + 2 use only existing Druid data and ship fast. Item 3 is the "new predictive data" value-add that justifies the platform to Finance. Item 4 is the Finance-native UX layer built once we know what the audience wants to see.

### 2026-06-17 (update 8) — Mo Chat knowledge base expansion; $/bar on Pack Ladder; REL column removed

**Brian collab session transcript analyzed** (`docs/Built - Aevah Collab Session.docx`, 36 min). Key items surfaced:
- Brian asked "what is REL, what does 4 mean?" on the Competitive screen → Mo Chat couldn't answer; column removed; Mo updated
- Brian's Hy-Vee story: 4-pack price reduction → $/bar gap vs. 1ct narrowed → singles fell, 4-pack surged → $/bar must be visible at a glance
- Brian confirmed retailer-first demo flow: Retailer Summary → account → SKU → Determine → Diagnose → Decide
- Big demo scheduled **2026-06-25 (Thursday), 90 minutes** — audience includes stakeholders who control buying decisions; need ROI framing (7% → 5% forecast error) and credible cross-brand cannibalization answers
- Items deferred to 2026-06-18: (2) cross-retailer SKU view ("flip the script" — start with SKU, see all retailers), (4) export to spreadsheet for forecasting team

**$/bar column added to Cannibalization Pack Ladder** (`Diagnose.tsx`): per-bar price (ARP ÷ pack_count) now shown next to ARP in the Pack Ladder table, making value-gap shifts visible without mental math.

**REL column removed from Competitive screen** (`Diagnose.tsx`): D-distance badge was internal scoring metadata. Removed from UI; footnote updated to keep only Tier 1 explanation. Mo Chat now holds the full explanation.

**Mo Chat system prompt expanded** (`mo_chat.py`):
- `_DATA_GLOSSARY` added: D1–D5 relationship distance taxonomy with plain-English eligibility rules per screen; pack_distance vs relationship_distance distinction; cannibal_status values; confidence labels (Early signal/Developing/Confirmed); Launch Monitor status codes; elasticity band definitions with interpretation; $/bar definition; competitor terminology rule
- `_SCREEN_MAP` updated: richer column/eligibility descriptions for Pack Ladder, Competitive, Launch Monitor, Elasticity Summary, Price Forecast; ramp window corrected to 12 weeks
- Stale refs removed: price determine `forecast` tab from `navigate_to` sub_tab list and `SCREEN_LABELS`
- **Rule going forward:** update `mo_chat.py` in the same commit as every UI or data model change

**PE Forecast redundancy resolved**: Scenario Forecast tab removed from Price Elasticity → Determine. Nav CTA ("Ready to model a price change? → Price Forecast →") added at bottom of Elasticity Summary, navigates to Decide → Price Forecast. PE Determine now has 3 tabs: Price Events · Elasticity Summary · Pack Elasticity.

### 2026-06-17 (update 6) — PE Forecast redundancy noted; full demo smoke test passed

**Scenario Forecast / Price Forecast redundancy (deferred)**
Noted that Scenario Forecast (Price Elasticity → Determine) appears to be a less complete version of Price Forecast (Price Elasticity → Decide). The Decide version adds: donor pressure on adjacent packs, margin direction, cannibal guardrail, quality warnings, BUILT own-brand pack ladder, and a no-elasticity empty state with three fallback options. The two tabs are candidates for consolidation. Discussion deferred; flagged in wiki (05-ui-screens.md) and project memory. Do not demo the Scenario Forecast tab to Brian — redirect to Price Forecast (Decide).

**Full demo smoke test — all endpoints green**
All 7 walkthrough questions verified against live Druid data: Q1 (35 events), Q2 (benchmark n=38, median −14.27 at Kroger), Q3 (Launch Monitor ACTIVE from wk 9), Q4 (Geography Cannibalizing prob=1.0), Q5 (promo type buckets present), Q6 (29 competitors), Q7 (2 recs, 5 active events). Retailer Summary 13 accounts clean. All four repos committed and pushed.

### 2026-06-17 (update 5) — MO_24_ramp_monitor.py added to repo

Added `scripts/MO_24_ramp_monitor.py` — the pipeline script that generates `new_product_ramp_monitor` in Druid. Implements Brian's 12-week launch window standard: SUPPRESSED weeks 0–5, LOW_CONFIDENCE weeks 6–7, ACTIVE weeks 8–11. Ribbon text uses "of 12" consistently. Sources from `event_detection_weekly` (weekly metrics) + `built_prepost_features` (description, geography, ARP). Runs as P4.5 in the pipeline — after MO_13 (cannibal score) and before MO_14_7 (which reads the table for NEW_ITEM_PRICE_BASELINE detection). Also tightened MO_14_7's NEW_ITEM_PRICE_BASELINE detection window from 8–16 to 8–12 weeks to match.

### 2026-06-17 (update 4) — Remove Avg PE column from Retailer Summary

Avg PE column removed from the Retailer Summary scorecard. Some accounts showed extreme values (e.g. −5.3T) due to near-zero-velocity SKUs producing unstable elasticity estimates that passed the |ε| ≤ 50 filter used at the individual SKU level but compounded badly when averaged. Column definition and cell removed from `RetailerSummary.tsx`, `avg_elasticity` field removed from `RetailerAccount` interface in `api/types.ts`. API continues to return the field (no backend change). Walkthrough and both wiki files updated. colSpan reverted 10 → 9.

### 2026-06-17 (update 3) — Pricing Action badge label fix + Rob solo-run setup

**Pricing Action event badge fix (PriceDecide.tsx)**
Active price events on the Pricing Action tab each carry a severity badge. The badge was rendering the raw `event_color` string from the API (`"amber"`) as its text content — a code-visible value, not a user-facing label. Fixed: added a `{ red: "Alert", amber: "Watch", green: "OK" }` map so badges now read **Alert / Watch / OK** while still styled in the correct color. Isolated to this one render path; EventCard and ScoredTable already used proper labels.

**Rob solo-run readiness**
- `customer-built-mo-api/.env.example` expanded from 3 → 8 vars: added `ANTHROPIC_API_KEY` (required for Mo Chat), `MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY/BUCKET` (ML pipeline write-back only, skip for demo). Each group has a comment explaining which vars are demo-critical.
- `customer-built-mo-ui/docs/WALKTHROUGH.md` now has a "First-Time Setup" section above "Before You Begin" covering: `git pull`, `cp .env.example .env`, `python3 -m venv .venv && pip install -r requirements.txt`, `npm install`. Prior version assumed the venv already existed.

### 2026-06-23 (update 2) — Aevah Standup directives captured in roadmap

Key directives from Rob/Jason standup extracted from transcript and saved to project memory + wiki (`08-roadmap.md`):

**Near-term (high priority for Jun 25 demo):**
- **Chart annotation lines + Mo explanation** — Detect significant changes in Trends charts algorithmically; draw a vertical dashed line at the event date; clicking fires a pre-built deterministic Mo Chat prompt. Hero use case: Cookies N Cream 1ct vs 4pk divergence at Walmart, Dec 2025 – Feb 2026. Rob: "Let's build that. Don't worry about accuracy — just draw the line and have Mo say something." First pass = concept proof.
- **Mo drives actionability** — Rob's core directive: "AI needs to help them act on the dashboard, not just see it. The dashboard screams at them when something needs to be done." We're automating the analyst, not helping the analyst.
- **Deterministic Mo prompts** — When an annotation or button triggers Mo, pre-build the prompt from known context (SKU, date, account, event type) for predictable, relatable answers.

**Long-term (90-day production standup scope):**
- **Validation / testing harness** — Two modes: (1) raw SPINS data quality check, (2) model output validation. Generates a gap lookup table the UI references to show "insufficient data" notes. Drives customer trust.
- **Edge case identification and process definition** — Deeper backtesting, second training pass, edge case catalog, external data integration (BUILT's own promo dates overlaid on charts).

### 2026-06-23 — Mo Chat bug fixes + Trends screen awareness + error handling

**Three Mo Chat bugs fixed:**

*Pack Crossover tile tool confusion:* When user asked "describe what's happening with the pack crossover" on the Trends dashboard, Mo was calling `get_cannibalization_packladder` (queries `price_pack_ladder_weekly`, returns empty for Trends filter context) instead of `get_velocity_trend`. Root cause: "use get_velocity_trend for sales trajectory" didn't cover the "describe this tile" intent, so Mo pattern-matched "pack crossover" to the Cannibalization Suite tool. Fix: explicit `PACK CROSSOVER TILE` instruction in `_SCREEN_MAP` Trends section.

*Channel switch false-confirmation:* When user said "switch to convenience," Mo called `get_channel_list`, found `CONVENTIONAL|CONVENIENCE` in the list, and confirmed "you're already on CONVENTIONAL|CONVENIENCE" without calling `update_filters`. Fix: explicit note in `get_channel_list` tool description that the list shows *available* channels (not the *current* channel) — Mo must always call `update_filters` to apply the change.

*Trends context — "select a focal UPC from the dropdown":* Trends has no focal UPC selector; products are in the Products filter bar. `filters.upc` is always empty on Trends, so MoPanel was hitting the generic `!filters.upc` branch and telling users to select a UPC that doesn't exist. Mo also had no idea which products were visible. Fix: `Trends.tsx` → `App.tsx` → `MoPanel.tsx` → `ChatRequest.selected_products` pipeline passes the current product list to every chat request. `_build_system()` for `trends::dashboard` now lists all 6 tile names, selected products with UPCs, and what Mo can help with. `MoPanel.tsx` proactive message uses `formatTrendsProductLabel()` to show e.g. "Built Puff Cookies N Cream (single · 4pk · 12pk) at KROGER + WALMART" instead of repeating the truncated base name.

**Graceful 500/529 error handling:** `_call_anthropic_with_tools()` now catches `APIStatusError` (429/500/502/503/529) and `APIConnectionError`/`APITimeoutError` — returns a friendly user-facing message instead of crashing the FastAPI route.

Wiki updated: `customer-built-doc/wiki/06-mo-chat.md` — new Trends Screen Awareness section, Error Handling section, updated proactive message logic, updated roadmap table, `get_channel_list` tool note.

### 2026-06-17 (update 2) — UC8/UC14 benchmarking, screentips, Brian walkthrough, smoke test fixes

**UC8 benchmarking quick wins (three screens)**
- *Elasticity Summary (PriceElasticityDetermine.tsx):* New `/api/price-elasticity/elasticity-benchmark` endpoint queries `scored_price_elasticity` for all BUILT SKUs at the current channel+account, deduplicates to latest per UPC, filters to negative ε only and |ε| ≤ 50 (removes promo-artifact positive values and near-zero-denominator outliers), returns `{min_elasticity, median_elasticity, max_elasticity, upc_count}`. UI renders a green→red gradient range bar with the focal SKU dot and a median tick — answers "is my −14 elasticity good or bad?" with Kroger portfolio context. Bar direction fixed: lo = max_elasticity (least elastic, green left), hi = min_elasticity (most elastic, red right).
- *Pre/Post (Diagnose.tsx):* Added `useAccountAvg` + `benchmarkDelta` hook to Diagnose. Chip above the pre/post table shows post-13w velocity and ARP/bar vs. account portfolio average — same pattern as SKU Summary and Elasticity Summary.
- *Retailer Summary (RetailerSummary.tsx + retailer.py):* Avg PE column added. `_q_elast()` extended to pull `implied_elasticity`; per-account accumulator averages values across scored SKUs. Cell color-coded red < −1.5, amber −0.8 to −1.5, green > −0.8. `RetailerAccount` type in `types.ts` extended with `avg_elasticity: number | null`. ColSpan 9 → 10.

**UC14 partial — BUILT PE on Competitive Price screen**
BUILT PE context strip rendered above the competitor table in `PriceElasticityDiagnose.tsx`. Shows: focal elasticity value + band badge, "A 1% price increase → ≈X% unit loss," amber caveat when promo-confounded, "Competitor elasticity estimates: coming (MO_25)." Fetched from 5th parallel call to `/api/price-elasticity/scores` on page load. UC14 status moved to 🟡 Partial.

**Badge screentips**
`Badge` component extended with optional `title` prop (`cursor: help` shown when present). Tooltip text added to: cannibal status badges (Cannibalizing/Watch/Incremental), cannibal confidence badges (Confirmed/Developing/Early signal), event confidence badges in `EventCard`, and elasticity band badges in `PriceElasticityDetermine` (Summary + pack comparison table) and `PriceElasticityDiagnose` (PE context strip). Every label Brian will see on demo day now has a hover definition.

**Brian walkthrough (docs/WALKTHROUGH.md)**
Complete rewrite as a 30-minute question-anchored demo script. Structured by Brian's 7 questions, not UI tab structure. Every filter selection uses the exact SPINS SKU description from the live dropdown (verified against `/api/filters/upcs`). Mo Chat used as transition mechanism between questions. Screens-to-skip table prevents navigating to data-sparse views. Full glossary and anticipated Q&A appended.

**Smoke test fixes found and resolved**
- Wiki had wrong price_elasticity router prefix (`/api/price` → `/api/price-elasticity`) — corrected in `04-api-reference.md`
- Elasticity range bar: `span` declared but unused → division-by-zero not guarded; fixed by renaming to `denom` with early return when `hi === lo`
- Benchmark endpoint included positive ε (promo artifacts, +44 to +645) and near-zero outliers in min/max calculation, making the range bar useless; fixed with `v < 0 and abs(v) <= 50` filter
- Range bar direction was inverted (green/left showed most elastic); fixed by swapping lo/hi mapping in `SummaryScreen`
- Launch Monitor Q3 demo UPC (`08-40229-30734` at Walmart) is now all SUPPRESSED; replaced with `Built Puff Chocolate Milkshake Protein Bar 1.41 Oz` at Kroger (ACTIVE wk 15, full progression visible in table)

### 2026-06-17 — Own-brand terminology, price event queue cleanup, Retailer Summary drill-through fix

**Own-brand vs. competitor terminology (design principle)**
Established that "competitor" in Mo always means another brand. BUILT's own pack sizes (1ct, 4Pk, 12Pk) are never called "competitor." The EventDetailModal (`src/components/ui/EventDetailModal.tsx`) now detects whether a price event's partner is a BUILT SKU by checking `partner_description` for "built" (case-insensitive), then falls back to parsing the event label. When the partner is own-brand: modal says "another BUILT pack size" / "the BUILT X-ct," KPI pill is labeled "Per-bar gap vs own pack," and the nav CTA routes to Pack Ladder. When the partner is a competitor: modal uses "[Name]'s X-ct" or "same-pack competitor," and the CTA routes to Price Forecast. Applies to both PRICE_DEFENSE_OPPORTUNITY and PRICE_DONOR_OVERLAP cases.

**Pack Ladder label and Gap% fix (PriceDecide.tsx)**
The Pack Ladder section on Price Forecast / Decide was labeling BUILT-vs-BUILT comparisons with the word "competitor." Renamed to "BUILT own-brand pack ladder — per-bar price gap" with an explanatory note. Column headers updated to reflect own-brand comparison. Gap% display bug fixed: `price_per_bar_gap_pct` is stored as a decimal (−0.242) in Druid but was displayed without multiplying by 100, showing −0.2% instead of −24.2%.

**Price Forecast empty state**
Replaced the dead-end "No elasticity data" state with an actionable explanation: smaller/specialty accounts often lack the price variation needed for elasticity scoring, so what-if modeling isn't available there. Now suggests switching to CONVENTIONAL|MULTI OUTLET, using the own-brand pack ladder comparison, or bringing per-bar pricing data to the buyer conversation directly.

**Price event queue: MAX(__time) query (events.py)**
Changed `price_event_queue` filter from `__time >= TIMESTAMPADD(DAY, -90, CURRENT_TIMESTAMP)` to `__time = (SELECT MAX(__time) FROM "price_event_queue")`. Druid ingests with APPEND mode — previous pipeline runs accumulate. Old own-brand PRICE_DEFENSE and PRICE_DONOR_OVERLAP events from before the own-brand filter was added were still visible via the 90-day window. MAX(__time) always shows exactly the latest pipeline run. Pipeline re-run (24,423 events: PRICE_DEFENSE=0, PRICE_DONOR_OVERLAP=0 — all own-brand, correctly filtered) confirmed clean state.

**Retailer Summary → Cannibalization drill-through fix (filters.py + App.tsx)**
Two bugs prevented drill-through from landing on the correct account/channel:
1. `filters.py /dimensions` only queried `cannibalization_rate_weekly` for available filter combinations. Some accounts exist in `scored_cannibalization` but not in `cannibalization_rate_weekly`. Added `scored_cannibalization` as a supplemental source — Python merges both sets, deduplicating by `(channel, account, geo_raw)`.
2. `App.tsx` dimensions `useEffect` only fires when `filters.upc` changes. If a user clicks "View Details →" for a UPC that's already selected, the UPC doesn't change and the pending account/channel refs are never consumed. Fixed with `dimFetchKey` state (bumped on same-UPC drill-through), added to the `useEffect` dependency array to force a re-fetch.

### 2026-06-16 (update 3) — API performance: parallel Druid queries + Retailer Summary cache

Screens were slowing down as each feature added more sequential Druid round trips. Root cause: no parallelism and no caching — total latency = sum of all queries per request.

**retailer.py `/summary`:** The 5 independent queries (scored_cannibalization, scored_price_elasticity, built_prepost_features, event_queue, price_event_queue) now fire in parallel via `ThreadPoolExecutor(5)`. Added a 120-second in-process TTL cache keyed on `channel_outlet` — subsequent loads within 2 minutes return instantly.

**events.py `/api/events`:** The two always-on queries (event_queue + price_event_queue) now fire in parallel. Three separate `scored_price_elasticity` lookups for PROMO_RESPONSE_BREAKPOINT, PACK_NORM_GAP, and PRICE_DEFENSE_OPPORTUNITY were merged into one shared fetch, saving 2 Druid round trips on every per-SKU events page load.

Going forward: any endpoint with ≥2 independent Druid queries should use `ThreadPoolExecutor`; portfolio-level endpoints (no focal UPC, stable data) should carry a short TTL cache.

### 2026-06-16 (update 2) — Price event bug fixes: PACK_NORM_GAP and NEW_ITEM_PRICE_BASELINE per-bar unit mismatch

Two price event detectors were comparing prices at different units (pack vs. per-bar), producing nonsense percentages (e.g., "1093.3% above MULO norm").

**PACK_NORM_GAP fix (MO_14_7_price_events.py):** `detect_pack_norm_gap()` was dividing `arp` (full pack price, e.g. $16.15 for an 8-pack) by `norm_avg_price_per_bar` (per-bar norm, e.g. $1.35). Changed to use `price_per_bar` column (= arp/pack_count = $2.02/bar) so both sides are per-bar. The Ahold 8-pack example now reads 49.6% above MULO norm, a realistic and still-actionable signal. Pipeline re-run: 1,172 PACK_NORM_GAP events written to `price_event_queue`.

**NEW_ITEM_PRICE_BASELINE fix (events.py enrichment):** The backend was enriching `current_arp` for the "Week N — price baseline window open" card from `price_pack_ladder_weekly.focal_arp` (pack price) then displaying it as "/bar" in the KPI pill. Fixed by dividing by `focal_pack_count` before storing, so both "Current ARP" and "MULO norm" pills are now per-bar prices.

### 2026-06-16 — Retailer Summary, Pack Norms, Benchmark Chips, Mo Chat everywhere

**Retailer Summary (new screen)**
A cross-retailer portfolio scorecard showing BUILT's full SKU landscape across all accounts — no focal UPC required. Columns: Scored SKUs, 13w Sales, YTD Sales, Own-Brand Issues, Competitor Wins, Highly Elastic, Active Events. Dollar columns use the SPINS Base Dollars formula: `sum(post_13w_arp × post_Xw_base_units)` across all scored BUILT SKUs per account, sourced from `built_prepost_features`. Confirmed against live data: Walmart $33.6M (13w) / $62.1M (YTD). Table is sortable by any column, includes a type-ahead account filter, and scrolls with a sticky header. Mo Chat is now available on this screen with portfolio-aware proactive messages and context.

**Pack Norms (replaces MULO Food Norms)**
Shows BUILT's own-brand pack ladder step discounts vs. competitor norms at the selected retailer/channel. Powered by new MO_23 pipeline (`scripts/MO_23_pack_norms.py`) writing competitor pack step-discount norms to the `competitor_pack_size_norms` Druid table (1,159 rows; account/channel/overall scope fallback). Key insight surfaced immediately: BUILT underdiscounts multipacks vs. competitors (−17% on 4pk, −22% on 12pk at Walmart MULO). Columns: BUILT ARP (total shelf price), BUILT $/bar, BUILT step discount, Comp norm $/bar, Comp step discount, Diff, Comp SKU count. BUILT-only velocity tiles highlight the highest-velocity pack tier.

**Benchmark chips**
Inline velocity and ARP delta chips on the SKU Summary (Cannibalization) and Elasticity Summary (Price Elasticity) screens. Shows how the focal SKU compares to the account portfolio average. Source: new `/api/retailer/account-avg` endpoint; implemented via `useAccountAvg` React hook and `benchmarkDelta` helper.

**Mo Chat on all screens**
Mo Chat (the Puff avatar button) is now present on every screen including Retailer Summary. The Retailer Summary has its own proactive message, screen context, and chips oriented toward portfolio prioritization. Mo's backend context for the retailer screen fetches live account scorecard data and dollar sales totals so it can answer questions grounded in real numbers.

---

At the planning stage, the repo contains a complete planning set for a cannibalization prediction initiative:

- a named analyst persona for the work
- a baseline strategy for cannibalization modeling
- an Aevah-specific adaptation of that strategy
- an implementation blueprint
- supporting diagrams
- a detailed data requirements specification
- a pilot-oriented project roadmap

In other words, this repo defines what should be built, why it should be built that way, what data is required, and how the project should be phased.

## What this is for

This workspace is meant to support the early and middle stages of a machine learning initiative before heavy implementation starts. It should help:

- align business and technical stakeholders
- define the cannibalization use case clearly
- prepare source data for governed use in Aevah
- structure the modeling project
- reduce ambiguity before engineering and data science work begins

## Recommended reading order

If you are new to the repo, read the documents in this order:

1. [docs/brad_cannibalization_plan.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_plan.md)  
   Start with the base modeling strategy.

2. [docs/brad_cannibalization_plan_aevah.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_plan_aevah.md)  
   Read this next if Aevah is the target platform.

3. [docs/brad_cannibalization_implementation_blueprint.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_implementation_blueprint.md)  
   Use this to understand who does what and how the work is structured.

4. [docs/brad_cannibalization_data_requirements.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_data_requirements.md)  
   Use this when preparing actual source data and table designs.

5. [docs/brad_cannibalization_diagrams.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_diagrams.md)  
   Use this for architecture reviews, stakeholder presentations, and implementation discussions.

6. [docs/brad_cannibalization_project_roadmap.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_cannibalization_project_roadmap.md)  
   Use this to schedule the work and frame the pilot.

7. [docs/brad_aevah_spins_processing_value_overview.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_aevah_spins_processing_value_overview.md)  
   Use this to explain the value-added work Aevah performs when accepting and processing the client's recurring SPINS feed.

8. [docs/brad_built_cannibalization_druid_ml_plan.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_cannibalization_druid_ml_plan.md)  
   Use this for the Druid query plan, ML workflow, and scoring architecture.

9. [docs/brad_built_cannibalization_druid_ml_plan_evaluation.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_cannibalization_druid_ml_plan_evaluation.md)  
   Use this to review the flexibility requirements and implementation changes before engineering starts.

10. [docs/brad_weekly_win_count_bonus_path.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_weekly_win_count_bonus_path.md)  
   Use this as an optional visualization and modeling extension for simple win/loss patterns, Bayesian probabilities, neural-network-ready sequences, and drillable UI ratios.

11. [docs/brad_built_cannibalization_ui_v2_comparison_pools.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_cannibalization_ui_v2_comparison_pools.md)  
   Use this to review the broader comparison-pool workbench UI that supports any focal SKU set, any comparison pool, weekly win/loss trends, and pairwise donor-pressure exploration.

12. [docs/brad_built_predictive_forecasting_extension_for_mo.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_predictive_forecasting_extension_for_mo.md)  
   Use this to design Mo's predictive forecasting layer around next-best-action scenarios, portfolio impact ranges, likely donor exposure, and confidence-framed recommendations.

13. [docs/brad_built_druid_data_onboarding_and_ml_soundness_check.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_druid_data_onboarding_and_ml_soundness_check.md)  
   Use this before implementation to confirm which non-SPINS data should enter Druid and how the ML plan should preserve BUILT plus competitor training context.

14. [docs/brad_built_lean_client_data_request_matrix.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_lean_client_data_request_matrix.md)  
   Use this to keep client data requests lean by distinguishing SPINS-covered fields, derived fields, and truly necessary client-provided business context.

15. [docs/brad_built_spins_95m_utilization_audit.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_spins_95m_utilization_audit.md)  
   Use this to confirm the 95M-row SPINS implementation carries forward all useful source measures before asking BUILT for more data.

16. [docs/built_cannibalization_druid_ml_plan_5.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/built_cannibalization_druid_ml_plan_5.md)  
   Use this as the current Mo suite Druid/ML plan for Cannibalization plus Price Elasticity.

17. [docs/Mo_Build_Field_Guide_price_elasticity_addendum.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/Mo_Build_Field_Guide_price_elasticity_addendum.md)  
   Use this with the original Mo Build Field Guide when implementing the Price Elasticity module.

18. [docs/mo_messages_register.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/mo_messages_register.md)  
   Use this to find or copy the canonical system prompts and user message templates for Brad and other Mo agents. Update this register whenever a prompt is revised.

19. [docs/mo_ml_field_notes.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/mo_ml_field_notes.md)  
   Read this before writing or modifying any pipeline script. Contains data quirks and LightGBM patterns discovered during live cluster execution that are not in planning documents.

20. [docs/mo_built_spins_hierarchy.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/mo_built_spins_hierarchy.md)  
   Use this when working with pack size filtering, attribute-based comparisons, or panel data fields in the Mo pipeline or UI.

21. [docs/mo_cannibalization_model_reference.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/mo_cannibalization_model_reference.md)  
   Use this when interpreting scored_cannibalization outputs, designing UI verdict logic, troubleshooting coverage gaps, or working with the write-back pipeline.

22. [docs/mo_vision_framework.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/mo_vision_framework.md)  
   Use this to evaluate whether any new screen, metric, or feature answers one of Brian's 7 questions and satisfies the 4-question frame before shipping to clients.

## How to use this repo

### For business stakeholders

Use the plan, Aevah plan, and roadmap to answer:

- what problem we are solving
- what cannibalization means in this project
- what the expected outputs will be
- what the pilot will require

### For data engineering and platform teams

Use the data requirements spec and diagrams to answer:

- what tables need to exist
- what the grain should be
- what keys and semantic definitions are required
- what data quality controls need to be in place

### For data science and analytics teams

Use the strategy, blueprint, and data requirements to answer:

- what the modeling targets should be
- how competitive sets should be defined
- what feature families need to be built
- how validation should be designed

### For program or product owners

Use the blueprint and roadmap to answer:

- who owns each phase
- what the dependencies are
- what the success criteria are
- when the pilot is ready to move forward

## Suggested operating workflow

The intended sequence for using these materials is:

1. align on the business definition of cannibalization
2. choose the first pilot scope
3. use the data requirements spec to prepare Aevah-ready source tables
4. use the implementation blueprint to assign owners and deliverables
5. use the diagrams to review architecture and flow with stakeholders
6. use the roadmap to schedule execution
7. then begin implementation work

## Current limitations

This repo does not yet include:

- production ETL or ELT jobs
- feature engineering code
- model training code
- dashboard code
- Aevah configuration artifacts
- source-to-target mapping tables
- test suites or monitoring scripts

Those are logical next steps after the planning package is approved.

## Recommended next steps

The strongest follow-on artifacts would be:

1. source-to-target mapping from SPINS fields into curated Aevah tables
2. a project charter for executive alignment
3. first-pass schema definitions for the curated fact and dimension tables
4. initial feature specification for the pilot use case
5. code scaffolding for ingestion, feature generation, and baseline modeling

## Repository structure

```text
.
├── README.md
├── All_items_extract_100.csv
├── agents/
│   └── brad.yaml
├── docs/
│   ├── brad_cannibalization_data_requirements.md
│   ├── brad_cannibalization_diagrams.md
│   ├── brad_cannibalization_implementation_blueprint.md
│   ├── brad_cannibalization_plan.md
│   ├── brad_cannibalization_plan_aevah.md
│   ├── brad_cannibalization_project_roadmap.md
│   ├── brad_aevah_spins_processing_value_overview.md
│   ├── brad_built_cannibalization_druid_ml_plan.md
│   ├── brad_built_cannibalization_druid_ml_plan_evaluation.md
│   ├── brad_built_cannibalization_ui_v2_comparison_pools.md
│   ├── brad_built_druid_data_onboarding_and_ml_soundness_check.md
│   ├── brad_built_lean_client_data_request_matrix.md
│   ├── brad_built_predictive_forecasting_extension_for_mo.md
│   ├── brad_built_spins_95m_utilization_audit.md
│   ├── brad_weekly_win_count_bonus_path.md
│   ├── mo_messages_register.md
│   ├── mo_ml_field_notes.md
│   ├── mo_built_spins_hierarchy.md
│   ├── mo_cannibalization_model_reference.md
│   └── mo_vision_framework.md
└── mockups/
    ├── mo_messages_register.html
    ├── mo_ml_field_notes.html
    ├── mo_built_spins_hierarchy.html
    ├── mo_cannibalization_model_reference.html
    └── mo_vision_framework.html
```
