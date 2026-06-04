# BUILT Lean Client Data Request Matrix

This note separates the Druid data needs into three practical buckets:

1. already included in SPINS or the supplemental SPINS workbooks
2. calculable from SPINS after ingestion
3. must be requested from BUILT, with a deliberately lean first ask

The goal is to avoid asking the client for more than we need before the first polished Mo release.

## Executive Summary

SPINS already covers a large portion of the modeling foundation:

- demand
- dollars
- base versus incremental demand
- price
- promotion
- distribution
- velocity / productivity
- first selling timing
- pack count
- broad flavor
- protein range
- many product attributes
- category and subcategory context

The client should not be asked to recreate those fields.

The lean client ask should focus on what SPINS cannot reliably know:

1. internal product hierarchy and normalized SKU roles
2. lifecycle / launch / discontinuation context
3. actual assortment and authorization
4. inventory availability or out-of-stock flags
5. margin / profitability fields

Everything else should be deferred unless the first model shows a specific gap.

## What SPINS Already Gives Us

Based on the sample extract and measure documentation, SPINS already appears to provide these domains.

### 1. Demand and sales outcomes

Already included:

- `Units`
- `Dollars`
- `EQ Units`
- year-ago versions

Use for:

- observed sales movement
- trend detection
- portfolio lift
- year-over-year comparison

### 2. Base and incremental demand

Already included:

- `Base Units`
- `Base Dollars`
- `Incr Units`
- `Incr Dollars`

Use for:

- separating underlying demand from promo-attributed lift
- retrospective cannibalization measurement
- training labels and event summaries

Important:

`Incr Units` is promo-attributed incremental volume, not simple week-over-week unit change.

### 3. Distribution and reach

Already included:

- `Avg % ACV`
- `Max % ACV`
- `TDP`
- `Average Weekly TDP`
- `Average Items Selling`
- `Number of Weeks Selling`
- `Weight Weeks`
- promo and non-promo TDP / ACV variants

Use for:

- controlling for distribution expansion
- identifying distribution-led growth
- launch ramp monitoring
- geography/channel comparisons

### 4. Productivity and velocity

Already included:

- `Dollars SPM`
- `Units SPM`
- `Average Weekly Dollars SPM`
- `Average Weekly Units SPM`
- `Dollars SPM Per Item`
- `Units SPM Per Item`
- `Dollars SPP`
- `Units SPP`
- `Dollars/TDP`
- `Units/TDP`

Use for:

- reach-adjusted productivity
- separating true demand from broader distribution
- Mo's current status and forecast screens

### 5. Pricing and promo detail

Already included:

- `ARP`
- promo and non-promo dollars / units
- promo percentages
- promo weeks
- lift by TPR, display, feature, feature + display, SPK
- ARP discounts by promo type
- base ARP by promo type
- ARP by promo type

Use for:

- promo confounding flags
- price-driven switching controls
- forecast assumptions
- event suppression when promo explains the movement

### 6. Launch timing proxy

Already included:

- `First Week Selling`
- `Number of Weeks Selling`

Use for:

- first-pass launch detection
- weeks-since-launch features
- new product ramp monitoring

Limit:

This tells us when SPINS first observed selling, not necessarily when BUILT intended the launch, shipped the SKU, authorized the SKU, or reset the shelf.

### 7. Product attributes from SPINS

Already included or available from the supplemental workbook:

- `Brand`
- `UPC`
- `Description`
- `PACK COUNT`
- `FLAVOR`
- `NFP - PROTEIN`
- `NFP RANGES - PROTEIN VALUE`
- `Category`
- `Subcategory`
- `FUNCTIONAL INGREDIENT`
- `HEALTH FOCUS`
- `SIZE POSITIONING`
- `SIZE`
- `UNIT OF MEASURE`
- `POSITIONING GROUP`
- `PRODUCT TYPE`

Use for:

- first-pass product hierarchy
- competitor filtering
- flavor family
- protein-band similarity
- pack-ladder discovery

## What We Can Calculate From SPINS

These should be calculated in Druid or downstream feature jobs rather than requested from the client.

### 1. Weekly deltas and trend features

Derived fields:

- `units_wow_delta`
- `base_units_wow_delta`
- `units_wow_pct`
- `base_units_wow_pct`
- `tdp_wow_delta`
- `units_tdp_wow_pct`
- rolling 4-week / 13-week averages
- rolling volatility
- rolling z-scores

### 2. Launch and lifecycle indicators

Derived fields:

- `weeks_since_first_selling`
- `new_sku_flag`
- `new_pack_size_flag`
- `launch_ramp_period_flag`
- `post_launch_stabilized_flag`
- `mature_sku_flag`

Limit:

These are observed-selling lifecycle fields. Client-provided lifecycle context is still better when available.

### 3. Promo and price confounding flags

Derived fields:

- `promo_confounded_week_flag`
- `high_discount_week_flag`
- `feature_display_week_flag`
- `price_gap_vs_pool`
- `price_per_unit_proxy`
- `base_arp_change_pct`

### 4. Distribution-led growth flags

Derived fields:

- `tdp_expansion_flag`
- `acv_expansion_flag`
- `distribution_led_gain_flag`
- `productivity_decline_with_distribution_gain_flag`

### 5. Pairwise comparison features

Derived fields:

- `comparison_type`
- `relationship_distance`
- same brand flag
- same flavor flag
- same flavor family flag
- pack count difference
- price distance
- velocity similarity
- distribution overlap
- promo overlap

### 6. Win-count and association features

Derived fields:

- `sku_week_win_flag`
- `sku_week_loss_flag`
- `weekly_win_count`
- `weekly_win_pct`
- `co_win_rate`
- `opposition_rate`
- `P(comparison_loses | focal_wins)`

### 7. Seasonality and calendar features

Derived or added from a public/internal calendar:

- week of year
- month
- quarter
- holiday window flags
- seasonal period

This does not require a heavy client data request unless BUILT has a special fiscal or merchandising calendar.

## What We Should Ask the Client For Now

This is the lean first request. It is intentionally small.

## Ask 1: Internal Product Master and SKU Role File

Why ask:

SPINS gives a good product foundation, but BUILT knows its own product architecture better than SPINS.

Requested file grain:

```text
UPC
```

Fields:

- internal SKU ID if different from UPC
- official SKU name
- brand line, such as BUILT PUFF, BUILT BAR, BUILT SOUR
- product family
- format / texture family
- normalized specific flavor
- flavor family
- pack-size band
- active / discontinued status
- replacement SKU if applicable
- intended SKU role, such as core, innovation, seasonal, trial, stock-up

Why this is high value:

It improves same-flavor pack-ladder accuracy and makes Mo's recommendations more credible.

## Ask 2: Launch, Discontinuation, and Product Change History

Why ask:

SPINS first selling is useful, but it does not tell us the intended launch, ship, authorization, reset, reformulation, or discontinuation context.

Requested file grain:

```text
UPC x event
```

Fields:

- UPC
- event type
- event date
- launch date
- first ship date if available
- first authorized date if available
- discontinuation date
- reformulation or packaging-change date
- replacement SKU if relevant
- intended launch scope, such as national, retailer, channel, region

Why this is high value:

It prevents the model from guessing event context from POS alone.

## Ask 3: Assortment / Authorization / Add-Delete History

Why ask:

This is the biggest missing piece for assortment cannibalization. SPINS can tell us what sold, but not what was authorized, intended, or removed.

Requested file grain, best case:

```text
UPC x retailer/banner/store or geography x effective period
```

Lean acceptable version:

```text
UPC x retailer/banner/channel x start_date x end_date
```

Fields:

- UPC
- retailer / banner / channel
- authorized flag
- item add date
- item delete date
- reset date if available
- assortment tier or store cluster if available
- planned versus actual assortment if available

Why this is high value:

It distinguishes true cannibalization from simple authorization changes.

## Ask 4: Inventory Availability or Out-of-Stock Indicator

Why ask:

Without availability, the model may mistake stockouts for cannibalization.

Requested file grain, best case:

```text
UPC x store x week
```

Lean acceptable version:

```text
UPC x retailer/banner/geography x week
```

Fields:

- in-stock rate
- out-of-stock flag
- low inventory flag
- weeks of supply if available
- fill rate or service level if available

Fallback if client cannot provide:

Ask only for known major supply disruption periods by SKU.

Why this is high value:

It protects Mo from making bad cannibalization claims when the real problem was availability.

## Ask 5: Margin / Profitability by SKU

Why ask:

Mo should eventually recommend profitable actions, not just volume actions.

Requested file grain:

```text
UPC x effective period
```

Fields:

- unit cost
- gross margin
- contribution margin if available
- net revenue adjustment if available

Lean acceptable version:

- current gross margin by SKU
- margin tier if exact margin cannot be shared

Why this is high value:

It lets Mo distinguish volume-accretive but profit-destructive actions.

## What We Should Not Ask For Yet

To keep the client ask light, defer these unless the pilot reveals a clear need:

- full shopper loyalty data
- household-level buyer overlap
- basket-level transaction data
- detailed field rep execution data
- display compliance audits
- shelf photos or store audits
- detailed trade spend allocation
- facings / shelf-space data
- every retailer's full planogram history
- qualitative strategy notes for every SKU

These can all improve the model later, but they are not required for a strong first Mo release.

## What Can Be Inferred If Client Data Is Missing

If BUILT cannot provide the lean ask immediately, we can still proceed with approximations.

| Missing client data | SPINS-based fallback |
|---|---|
| launch date | `First Week Selling` |
| discontinued status | sustained zero sales / no distribution |
| item add date | first meaningful TDP / ACV week |
| item delete date | last meaningful TDP / ACV week |
| product family | parse from `Brand`, `Description`, `Product Type` |
| normalized flavor | parse from `Description` and `FLAVOR` |
| pack-size band | derive from `PACK COUNT` |
| promo calendar | use SPINS promo, lift, discount, feature/display fields |
| price support | use ARP and discount measures |
| broad availability | use TDP, ACV, stores selling, and weight weeks |

These fallbacks are good enough for a pilot, but they should be labeled as inferred.

## Recommended Client Request Package

Ask for only five files first:

1. `built_product_master.csv`
2. `built_product_events.csv`
3. `built_assortment_authorization.csv`
4. `built_inventory_availability_or_oos.csv`
5. `built_sku_margin.csv`

If they push back, reduce to three:

1. product master
2. product events
3. assortment authorization

If they push back again, reduce to one:

1. product master with launch/discontinue/status fields included

## Bottom Line

SPINS already covers the quantitative modeling foundation. We should not ask BUILT for fields SPINS already provides.

The lean client ask should focus on context SPINS cannot know:

- what the product is intended to be
- when the product was intentionally launched, changed, or discontinued
- where the product was authorized or removed
- whether it was actually available
- whether the outcome was profitable

That is enough to make Mo meaningfully smarter without burdening the client.
