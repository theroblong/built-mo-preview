# BUILT Druid Data Onboarding and ML Soundness Check

This note answers two implementation questions:

1. Once the latest 51GB / 95M-row SPINS weekly POS dataset is loaded into Druid, what else needs to be loaded?
2. Does the current ML plan remain sound if the goal is to use all BUILT and eligible competitor data for testing and training across historical patterns, seasonality, trends, noise, outliers, significant events, new item introductions, and successive demand-transfer patterns?

Short answer:

The ML plan remains directionally sound, but the Druid layer must preserve a category-level enriched universe containing BUILT and eligible competitors. The UI can default to BUILT same-flavor pack ladders, but the model and pairwise feature pipeline should not be trained only on BUILT rows.

## Step 0: Load the Raw SPINS Weekly POS Feed

Primary Druid datasource:

```text
spins_weekly_pos
```

Recommended grain:

```text
UPC x Geography x Week
```

If retailer-specific geography exists in the source, preserve it rather than collapsing too early:

```text
UPC x Retailer/Banner x Geography x Week
```

Core fields to retain:

- UPC
- Description
- Brand
- Geography
- week-ending date
- Units
- Base Units
- Dollars
- Base Dollars
- EQ Units if available
- TDP
- Average Weekly TDP
- Max ACV
- Stores Selling / % Stores Selling if available
- Units/TDP
- Dollars/TDP
- Units SPM / SPP
- Dollars SPM / SPP
- ARP
- Base ARP
- Promo Weeks
- Units Promo / Non-Promo
- Dollars Promo / Non-Promo
- Incr Units / Dollars
- First Week Selling
- Number of Weeks Selling
- Category / Subcategory if included
- Pack Count
- Flavor

Do not reduce the source to BUILT only at ingestion. The raw datasource should preserve the full category/subcategory history needed for competitor training and category context.

## Step 1: Load Product Master and Product Attribute Data

Datasource or lookup:

```text
dim_product
```

Load for:

- all BUILT UPCs
- all competitor UPCs in the eligible category/subcategory
- any category items needed for seasonality, noise, and trend baselines

Minimum fields:

- UPC
- brand
- manufacturer
- product description
- category
- subcategory
- pack count
- size
- unit of measure
- protein grams
- protein band
- functional ingredient
- health focus
- size positioning
- product type
- positioning group

BUILT-specific enrichments:

- brand line, such as BUILT PUFF or BUILT BAR
- product family
- format family, such as puff, bar, bites
- normalized specific flavor
- flavor family
- flavor cluster
- pack-size band
- active / discontinued status
- replacement SKU mapping

Competitor-specific enrichments:

- competitor tier
- competitor set membership
- normalized competitor brand
- comparable flavor family
- comparable product format
- protein / nutrition band if available

Why it matters:

This is the table that lets the model distinguish tight substitutes from broad category context.

## Step 2: Load Flavor and Similarity Mapping

Datasource or lookup:

```text
dim_product_similarity
```

This should be broader than the current BUILT-only flavor mapping.

Required fields:

- UPC
- normalized specific flavor
- flavor family
- flavor cluster
- product form / texture
- brand line
- protein band
- pack count
- pack-size band
- same-flavor match key
- same-family match key
- category substitute group
- need-state or usage occasion if available

For competitors, the mapping can be less perfect at first, but it should exist. Unknown competitor flavors should be flagged explicitly instead of silently dropped.

Why it matters:

The comparison pool depends on relationship features such as same flavor, same family, same format, same protein band, and pack-size distance.

## Step 3: Load Market, Retailer, Channel, and Geography Hierarchy

Datasource or lookup:

```text
dim_market
```

Required fields:

- geography id or name from SPINS
- standardized geography name
- retailer
- banner
- channel
- region
- division
- state / market where available
- store cluster or account cluster if available
- geography type, such as Total US, region, retailer, banner

Why it matters:

The same SKU relationship may be incremental in one channel and cannibalizing in another. The model needs stable market hierarchy to learn those differences.

## Step 4: Load Calendar and Seasonality Dimensions

Datasource or lookup:

```text
dim_calendar_week
```

Required fields:

- week end date
- week start date
- year
- quarter
- month
- week of year
- fiscal period if BUILT uses one
- holiday flags
- holiday name
- season
- merchandising season if relevant

Why it matters:

Training on all historical data is useful only if the model can separate repeatable seasonality from true cannibalization.

## Step 5: Load Product Lifecycle and Event History

Datasource:

```text
fact_product_events
```

Recommended grain:

```text
UPC x geography/channel/account x event_date x event_type
```

Required events:

- new item launch
- new pack size launch
- new flavor launch
- reformulation
- package change
- discontinued item
- replacement item
- reset / assortment change
- major distribution expansion
- major distribution loss
- major promotion
- known supply disruption

Required fields:

- UPC
- event type
- event date
- affected geography / retailer / channel
- related prior UPC if replacement
- planned launch scope
- event confidence or source

Why it matters:

This lets the model learn from true historical events rather than treating every demand change as random time-series movement.

## Step 6: Load Assortment and Authorization Data

Datasource:

```text
fact_assortment_authorization
```

Recommended grain:

```text
UPC x store/retailer/geography x effective_start_date x effective_end_date
```

Requested fields:

- authorized item flag
- actual carried item flag if available
- planned assortment flag
- item add date
- item delete date
- reset date
- retailer / banner / store or geography
- assortment tier
- planogram name or shelf set if available
- facings or shelf allocation if available
- void status if available

Why it matters:

Cannibalization is only interpretable if we know which items were actually available in the same assortment.

## Step 7: Load Store Assortment Rules and Shelf Constraints

Datasource:

```text
dim_assortment_rules
```

Requested fields:

- retailer / banner / channel
- store cluster or assortment tier
- rule effective dates
- max total BUILT SKUs
- max SKUs by brand line
- max SKUs by flavor family
- allowed pack sizes
- required core SKUs
- optional SKUs
- replacement rules
- planogram version
- shelf-space limits or facings if available

Why it matters:

This separates true consumer demand transfer from forced substitution caused by shelf capacity or assortment rules.

## Step 8: Load Inventory Availability and Out-of-Stock Data

Datasource:

```text
fact_inventory_availability
```

Best grain:

```text
UPC x store x day/week
```

Acceptable fallback:

```text
UPC x retailer/geography x week
```

Requested fields:

- in-stock flag
- out-of-stock flag
- on-hand inventory
- beginning / ending inventory
- weeks of supply
- fill rate
- service level
- backorder flag
- replenishment gap
- low inventory flag

Why it matters:

Without availability data, the model can mistake forced switching from stockouts for cannibalization.

## Step 9: Load Pricing, Trade Support, and Promo Calendar Data

Datasource:

```text
fact_trade_promo
```

Recommended grain:

```text
UPC x retailer/geography/channel x week
```

Requested fields:

- regular price
- promoted price
- discount depth
- trade spend
- TPR flag
- feature flag
- display flag
- secondary placement flag
- promo start / end dates
- customer-specific price agreement if available

Why it matters:

This separates price-driven switching and promo-driven switching from product or assortment cannibalization.

## Step 10: Load Profitability and Finance Data

Datasource or secured lookup:

```text
dim_product_finance
```

Requested fields:

- unit cost
- gross margin
- contribution margin
- net revenue adjustment
- trade spend allocation
- retailer-specific margin if available
- cost effective dates

Why it matters:

Mo should eventually recommend profit-growing actions, not only volume-growing actions.

## Step 11: Load Field Execution and Account Coverage Data

Datasource:

```text
fact_field_execution
```

Requested fields:

- sales rep id
- rep-to-store mapping
- rep-to-geography mapping
- account manager mapping
- broker / distributor mapping
- assignment effective dates
- call frequency
- display compliance
- shelf placement audit
- void audit
- in-stock audit

Priority:

Medium overall, high if BUILT believes execution varies materially by geography or account.

Why it matters:

Execution differences can explain why one market looks additive and another looks cannibalizing.

## Step 12: Load Shopper, Basket, or Loyalty Data if Available

Datasource:

```text
fact_shopper_basket
```

Requested fields:

- household or anonymized shopper id
- basket id
- trip date
- UPCs purchased together
- repeat rate
- buyer overlap
- household penetration
- trip / occasion markers

Priority:

Optional but highly valuable.

Why it matters:

Basket or loyalty data is the best way to validate whether two pack sizes serve the same shopper mission or different missions.

## Step 13: Load Qualitative Strategy Metadata

Datasource or governed reference file:

```text
dim_sku_strategy
```

Requested fields:

- intended SKU role
- target shopper
- usage occasion
- innovation objective
- strategic account priority
- known product replacement
- intended pack architecture
- known retailer-specific strategy notes

Why it matters:

This lets Mo explain recommendations in business terms and avoid recommending against a strategically necessary SKU without context.

## Step 14: Build Derived Druid Tables

After the raw and reference data are loaded, build these curated Druid outputs.

### 14.1 `weekly_enriched_items`

Grain:

```text
UPC x geography/channel/retailer x week
```

Contains:

- all BUILT rows
- eligible competitor rows
- product hierarchy
- normalized flavor and family
- pack attributes
- category/subcategory attributes
- calendar fields
- market hierarchy
- competitor flags
- availability flags
- promo and price fields
- lifecycle/event flags

Important:

This table should not be BUILT-only. It is the main training universe.

### 14.2 `comparison_pool_weekly`

Grain:

```text
focal_upc x comparison_upc x geography/channel/retailer x week
```

Contains:

- focal metrics
- comparison metrics
- relationship type
- relationship distance
- similarity features
- price distance
- distribution overlap
- promo overlap
- availability controls

Important:

Use neutral naming. The comparison SKU is not a donor until the scoring layer infers that role.

### 14.3 `event_windows`

Grain:

```text
event_id x focal_upc x comparison_upc x geography/channel/retailer x window
```

Contains:

- pre-window features
- launch or event-window features
- post-window outcomes
- event type
- event confidence
- materiality flags

Use this for historical measurement and training labels.

### 14.4 `weekly_win_features`

Grain:

```text
UPC or comparison group x geography/channel/retailer x week
```

Contains:

- SKU weekly win flag
- weekly loss flag
- active SKU count
- weekly win count
- weekly win percentage
- co-win rate
- opposition rate
- focal win / comparison loss patterns

Use this as pattern evidence, not causal proof.

### 14.5 `ml_feature_table`

Grain:

```text
focal_upc x comparison_upc x geography/channel/retailer x scoring_window
```

Contains:

- historical measurement features
- forward-looking features
- labels for training
- feature snapshot metadata

Important:

Separate retrospective measurement features from predictive scenario features to prevent leakage.

### 14.6 `scenario_forecast_outputs`

Grain:

```text
scenario_id x focal_upc x comparison_pool x geography/channel x forecast_horizon
```

Contains:

- scenario assumptions
- forecasted focal units range
- forecasted donor loss range
- net incremental range
- incremental share range
- likely donor exposure
- confidence label
- recommended action

Use this for Mo's predictive "Forecast next move" experience.

## ML Plan Soundness Check

The current ML plan is sound if the following implementation rules are enforced.

### 1. Train on a broad category universe, not only BUILT

Use all BUILT plus eligible competitor/category rows to learn:

- seasonality
- category trends
- retailer noise
- promo response
- distribution effects
- launch patterns
- outliers
- competitor pressure
- normal volatility

The UI can default to BUILT-focused questions, but the model should learn from the wider category.

### 2. Keep BUILT focal defaults, but do not remove competitor rows

Recommended pattern:

- default focal universe: BUILT SKUs
- default comparison pool: same specific flavor pack ladder
- training universe: BUILT plus eligible competitors
- comparison universe: relationship-aware category pool
- full category rows: used for trend, noise, seasonality, and competitive baselines

This keeps the product narrow while keeping the model informed.

### 3. Fix the Query 1 risk from the current plan

The current evaluation correctly notes that Query 1 can accidentally filter competitors out too early.

Required correction:

```text
Do not create built_enriched_weekly as BUILT-only if downstream competitor comparison is required.
Create weekly_enriched_items containing BUILT and eligible competitor/category rows.
Add is_built_brand, is_competitor, competitive_tier, and competitor_set flags.
```

Then let the UI and scoring request filter to BUILT focal SKUs when needed.

### 4. Use separate feature sets for retrospective measurement and forecasting

Retrospective measurement can use:

- observed pre/post deltas
- realized donor declines
- post-event demand transfer
- statistical significance tests

Predictive forecasting must use only features known before the forecast horizon:

- trailing demand
- trailing productivity
- current distribution
- planned distribution change
- current and planned price / promo
- product similarity
- relationship distance
- seasonality
- geography history
- launch age
- historical analog outcomes

This avoids circular labels and leakage.

### 5. Preserve event history for new item introductions and successive patterns

The plan remains sound for new item introductions if events are explicitly represented.

Required event features:

- weeks since launch
- launch cohort
- new flavor flag
- new pack flag
- replacement flag
- distribution ramp
- velocity ramp
- post-launch stabilization period
- prior related SKU trajectory
- successive launch sequence, such as 1ct then 4pk then 12pk

Successive patterns matter because the second or third pack launch often behaves differently from the first.

### 6. Use all historical data, but validate like the future

Training can use the full history, but validation should mimic real use:

- time-based holdouts
- holdout launch cohorts
- holdout geographies
- holdout competitor brands if feasible
- backtesting on future periods

Avoid random train/test splits as the primary validation method because they leak time and event context.

### 7. Keep pairwise comparison neutral until scoring

The feature table should use:

```text
focal_upc
comparison_upc
```

not:

```text
donor_upc
```

Donor status is an output of scoring, not a table assumption.

### 8. Control for noise, outliers, and missing evidence

The plan should continue to include:

- minimum active weeks
- minimum distribution threshold
- outlier detection
- promo confounding flags
- stockout or availability controls
- sparse-data suppression
- confidence labels
- event materiality thresholds

This is especially important when training on a broad competitor universe because noisy competitor rows can otherwise dominate weak signals.

### 9. Use competitor data in three distinct ways

Competitor data should support:

1. Baseline category context:
   - seasonality
   - trend
   - noise
   - category expansion / contraction

2. Competitive pressure modeling:
   - cross-brand same flavor
   - same family cross-brand
   - competitor launch pressure
   - competitor promo pressure

3. Negative and weak-signal examples:
   - unrelated pairs
   - weak relationships
   - normal non-cannibalizing movement

This helps the model learn both what cannibalization looks like and what it does not look like.

### 10. Keep Mo polished by filtering outputs, not inputs

The model can train broadly. The UI should still surface narrowly:

- priority events
- same-flavor pack ladder diagnosis
- likely donor SKUs
- geography-specific recommendations
- forecast next move
- assortment action

The product should not expose every possible competitor pair by default.

## Recommended Druid Load Order

Use this order:

1. `spins_weekly_pos`
2. `dim_product`
3. `dim_product_similarity`
4. `dim_market`
5. `dim_calendar_week`
6. `fact_product_events`
7. `fact_assortment_authorization`
8. `dim_assortment_rules`
9. `fact_inventory_availability`
10. `fact_trade_promo`
11. `dim_product_finance`
12. `fact_field_execution`
13. `fact_shopper_basket` if available
14. `dim_sku_strategy`
15. `weekly_enriched_items`
16. `comparison_pool_weekly`
17. `event_windows`
18. `weekly_win_features`
19. `ml_feature_table`
20. `scenario_forecast_outputs`

## Minimum Viable Druid Additions Beyond SPINS

If BUILT cannot provide every table at once, request these first:

1. Product master and normalized flavor/pack/format mapping for BUILT and competitors
2. Market / retailer / channel hierarchy
3. Calendar week dimension
4. Product lifecycle and launch events
5. Assortment authorization and item add/delete history
6. Inventory / OOS or availability flags
7. Pricing and promo calendar detail
8. Profitability fields if Mo will recommend profit-growing actions

With those eight additions, the current ML plan can support a strong first production version.

## Bottom Line

The plan remains sound if the implementation treats the 95M SPINS rows as a category training universe, not merely a BUILT extract.

The correct architecture is:

```text
Full SPINS category history
+ product, market, calendar, lifecycle, assortment, availability, promo, and finance enrichments
-> weekly_enriched_items
-> comparison_pool_weekly
-> event_windows and win features
-> ML feature table
-> Mo scoring, forecasting, and recommendations
```

That preserves all the historical patterns BUILT wants the model to learn while keeping the client-facing tool narrow, polished, and action-oriented.
