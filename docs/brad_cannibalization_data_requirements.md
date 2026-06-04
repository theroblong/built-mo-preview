# Brad's Cannibalization Data Requirements Spec

This document defines the data requirements for building product cannibalization prediction in Aevah. It is intended to complement:

- `docs/brad_cannibalization_plan.md`
- `docs/brad_cannibalization_plan_aevah.md`
- `docs/brad_cannibalization_implementation_blueprint.md`
- `docs/brad_cannibalization_diagrams.md`

The purpose of this spec is to make the project executable by clearly defining the required grain, history, tables, keys, fields, and quality checks.

## Objective

Provide the minimum governed dataset needed to:

- measure historical cannibalization
- train predictive models
- score future cannibalization risk
- support business-facing dashboards and agent workflows

## Primary analytical grain

The core fact grain should be:

- `UPC x Geography x Week`

This should represent one weekly observation for one item in one geography or retailer-market unit.

If retailer-specific analysis is required, the effective grain may become:

- `UPC x Retailer x Geography x Week`

That decision should be made before production feature engineering begins because it affects feature definitions, target logic, and model volume.

## Recommended history depth

Minimum recommended history:

- 104 weeks

Preferred history:

- 156 weeks or more

Reason:

- enough history is needed to capture launches, promotions, distribution changes, seasonality, and repeated demand-transfer patterns

## Required data domains

The data model should cover six domains:

1. product
2. market
3. calendar
4. POS demand
5. pricing, promotion, and distribution
6. derived business definitions and modeling features

## Required tables

Recommended minimum table set:

1. `fact_pos_weekly`
2. `dim_product`
3. `dim_market`
4. `dim_calendar_week`
5. `fact_product_events`
6. `bridge_competitive_set`
7. `fact_cannibalization_labels` or equivalent derived training table

## 1. `fact_pos_weekly`

This is the primary modeling fact table.

### Required keys

- `upc_id`
- `market_id`
- `week_end_date`

Optional additional keys:

- `retailer_id`
- `channel_id`

### Required raw or curated fields

#### Demand

- `units`
- `base_units`
- `eq_units`
- `dollars`
- `base_dollars`
- `incr_units`
- `incr_dollars`

#### Distribution

- `avg_acv`
- `max_acv`
- `tdp`
- `avg_weekly_tdp`
- `avg_items_selling`
- `weeks_selling`
- `weight_weeks`

#### Price

- `arp`
- `base_arp_tpr`
- `base_arp_any_feature`
- `base_arp_any_display`

If these base ARP variants are not consistently available, at minimum include:

- `arp`
- non-promoted price proxy if available

#### Promotion

- `promo_weeks`
- `units_promo`
- `units_non_promo`
- `dollars_promo`
- `dollars_non_promo`
- `units_pct_promo`
- `dollars_pct_promo`
- `avg_acv_any_promo`
- `avg_acv_non_promo`
- `tdp_any_promo`
- `tdp_non_promo`
- `arp_pct_discount_tpr_only`
- `arp_pct_discount_any_feature`
- `arp_pct_discount_any_display`
- `units_lift_tpr`
- `units_lift_any_feature`
- `units_lift_any_display`

### Required metadata fields

- `source_system`
- `load_date`
- `record_version`

### Data rules

- one row per analytical grain
- no duplicate `upc_id + market_id + week_end_date`
- numeric measures stored in numeric types
- missing values standardized consistently

## 2. `dim_product`

This table defines item identity and product hierarchy.

### Required keys

- `upc_id`

### Required fields

- `brand_name`
- `product_description`
- `pack_count`
- `flavor`
- `protein_grams`
- `protein_band`
- `size_oz` if available
- `subcategory`
- `segment`
- `manufacturer`
- `launch_date` if available
- `discontinue_date` if available

### Recommended additional fields

- `form_factor`
- `pack_type`
- `benefit_claims`
- `organic_flag`
- `gluten_free_flag`
- `protein_positioning_flag`
- any product attributes that help define substitution similarity

## 3. `dim_market`

This table standardizes markets and consumption regions.

### Required keys

- `market_id`

### Required fields

- `geography_name`
- `retailer_name` if retailer-specific
- `channel_name`
- `region_name`
- `market_type`

### Recommended additional fields

- `state`
- `division`
- `store_group`
- retailer cluster or channel cluster

## 4. `dim_calendar_week`

This table provides seasonality and time logic.

### Required keys

- `week_end_date`

### Required fields

- `week_start_date`
- `year`
- `quarter`
- `month`
- `week_of_year`
- `fiscal_period` if relevant
- `holiday_flag`
- `holiday_name` if relevant
- `season_name`

## 5. `fact_product_events`

This table captures important business events at the product-market-week level.

### Required keys

- `upc_id`
- `market_id`
- `week_end_date`
- `event_type`

### Required event types

- `launch`
- `major_promo`
- `distribution_gain`
- `distribution_loss`
- `assortment_add`
- `assortment_remove`

### Required fields

- `event_flag`
- `event_start_date`
- `event_end_date`
- `event_magnitude`
- `event_definition_version`

This table is useful for both historical measurement and target construction.

## 6. `bridge_competitive_set`

This table defines the substitution universe for each focal SKU.

### Required keys

- `focal_upc_id`
- `competitor_upc_id`

### Required fields

- `competitive_set_type`
- `same_brand_flag`
- `same_segment_flag`
- `same_subcategory_flag`
- `same_pack_band_flag`
- `same_flavor_family_flag`
- `same_protein_band_flag`
- `price_tier_distance`
- `similarity_score`
- `rule_version`

This is a critical table. Cannibalization quality depends heavily on competitive-set quality.

## 7. `fact_cannibalization_labels`

This is the training label table or derived view.

### Required keys

- `upc_id`
- `market_id`
- `week_end_date`

### Required fields

- `target_units_cannibalized`
- `target_dollars_cannibalized`
- `target_cannibalization_event_flag`
- `donor_relationship_strength` if available
- `label_definition_version`

If direct cannibalization labels are not initially available, this table can begin as a derived training view based on event logic and observed demand transfer rules.

## Feature-view requirements

Before training, the project should publish reusable feature views with documented lineage.

### Required feature families

#### Own-item features

- current price
- base price
- promo depth
- ACV / TDP
- age since launch
- trailing demand
- seasonality signals

#### Competitive features

- competitor count in market-week
- weighted competitor price
- weighted competitor promo intensity
- weighted competitor distribution
- same-brand pressure count
- assortment breadth

#### Similarity features

- same brand
- same segment
- same flavor family
- same size band
- same protein band
- price-tier proximity

#### Market context features

- category demand trend
- category promo intensity
- retailer or channel effect
- geography effect
- holiday / seasonal effect

## Data quality requirements

The following checks should be required before modeling:

### Key integrity

- no duplicate rows at the chosen grain
- all fact keys resolve to dimensions
- all week values map to the calendar table

### Completeness

- `units`, `base_units`, `dollars`, `avg_acv`, `tdp`, and `arp` must meet agreed completeness thresholds
- critical product hierarchy fields must be populated for the majority of active UPCs

### Consistency

- metric definitions are stable across time
- geography naming is standardized
- promo measures are defined consistently across periods

### Reasonableness

- no impossible negative values in fields that should not be negative
- distribution and promo ranges are bounded appropriately
- extreme outliers are flagged for review, not silently discarded

## Leakage controls

This project needs explicit controls for leakage from derived POS metrics.

Fields that should be reviewed carefully before direct use:

- incrementality fields
- lift fields
- SPM and SPP style productivity ratios
- fields that may be calculated from the target itself

Recommended rule:

- raw and near-raw demand, price, promo, and distribution measures should be preferred for model inputs
- derived fields should be admitted only after review and documentation

## Recommended naming and governance standards

To support Aevah governance, each curated table or feature view should include:

- definition owner
- refresh cadence
- source lineage
- business description
- field-level definitions for critical measures
- version or effective-date tracking where logic changes over time

## Refresh and latency requirements

Recommended initial refresh cadence:

- weekly

Recommended scoring cadence:

- weekly after POS updates land

If near-real-time decisioning is not required, weekly scoring is usually sufficient for cannibalization planning in CPG POS workflows.

## Minimum viable delivery scope

For a first deployment, the minimum viable data scope should include:

- one category or subcategory
- 2 to 3 years of weekly history
- complete product hierarchy for that scope
- stable market and retailer mappings
- reliable price, promo, and distribution measures
- enough repeated launch and promo events to estimate substitution behavior

## Questions to resolve before implementation

Before build-out begins, the team should answer:

1. What is the exact production grain: geography-week or retailer-geography-week?
2. Which business question comes first: launch, promo, or assortment cannibalization?
3. Which product hierarchy fields are already available beyond the sample CSV?
4. Is margin data available or only unit and dollar measures?
5. How will competitive sets be governed and versioned?
6. What threshold defines a material cannibalization event for the business?

## Acceptance criteria for data readiness

The data foundation can be considered ready for modeling when:

- the weekly fact table is stable at the chosen grain
- all major keys are governed and consistently resolved
- competitive-set logic is defined and approved
- historical event views can be generated reproducibly
- required fields meet completeness and quality thresholds
- leakage-sensitive inputs have been reviewed and documented
