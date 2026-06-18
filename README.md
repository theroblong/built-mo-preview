# Product Cannibalization Planning Workspace

This repository contains the planning and documentation package for building a product cannibalization prediction capability using SPINS CPG POS data, with delivery designed around Aevah.

The current repo is documentation-first. It does not yet contain modeling code or production pipelines. Instead, it captures the strategy, architecture, data requirements, diagrams, and execution plan needed to move into implementation cleanly.

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
