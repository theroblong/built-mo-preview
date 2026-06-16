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
