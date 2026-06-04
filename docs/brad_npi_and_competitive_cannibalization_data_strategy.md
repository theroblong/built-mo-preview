# Brad's NPI and Competitive Cannibalization Data Strategy

This document combines two related planning topics:

1. how to evaluate cannibalization for a new product or a new package size of an existing flavor
2. how to identify competitive brand products that cannibalize BUILT products

It is intended to complement:

- `docs/brad_cannibalization_plan.md`
- `docs/brad_cannibalization_plan_aevah.md`
- `docs/brad_cannibalization_prediction_capabilities.md`
- `docs/brad_npi_cannibalization_prediction_trust.md`
- `docs/brad_pack_size_feature_engineering.md`

## Objective

The goal is to define how a comprehensive cannibalization system should think about:

- new product introductions
- new package sizes for existing flavors
- within-brand substitution
- external competitive substitution
- market-specific and store-specific effects

The desired outcome is a framework for understanding where demand comes from, where it shifts, and how that changes across product, market, and execution contexts.

## Part 1: Ways to look at cannibalization for a new product or package size

Cannibalization should not be viewed as one single question. For a new SKU or new package size, the system should be able to analyze the effect from several perspectives.

### 1. Within-SKU-family cannibalization

Examples:

- a new 12-count steals volume from an existing 4-count
- a new package size of the same flavor redistributes volume across the same product family

This is often the clearest first cannibalization lens for innovation and assortment planning.

### 2. Within flavor and protein-range cannibalization

Examples:

- a new SKU competes with items sharing the same flavor family
- a new SKU competes with items in the same protein band
- a new package size changes how demand moves within a flavor / protein cluster

This helps define the closest substitution neighborhood around a focal SKU.

### 3. Within-brand cannibalization

Examples:

- a new SKU takes demand from sister BUILT items
- a launch grows gross brand sales but destroys net portfolio value

This is critical for understanding whether innovation is portfolio additive or self-destructive.

### 4. External competitive cannibalization

Examples:

- competitor items with similar flavor, protein level, and pack architecture take demand from BUILT
- competitor launch, promo, or distribution gains hurt BUILT sales

This matters because not all demand shifts are internal. Some launches attract demand from competing brands.

### 5. Market-specific cannibalization

Examples:

- the same launch is highly additive in one geography and highly cannibalistic in another
- local retailer mix changes the degree of substitution

This helps identify where product assortment and launch strategies should differ by market.

### 6. Store or store-cluster cannibalization

Examples:

- large-format stores support multiple pack sizes with limited conflict
- smaller-format stores create stronger substitution pressure

This is especially useful when assortment decisions are made at the store or cluster level.

### 7. Event-type cannibalization

The system should separate:

- launch cannibalization
- promo-driven cannibalization
- distribution-driven cannibalization
- assortment-change cannibalization

Different event types can create very different patterns of demand transfer.

## Part 2: Data needed to show cannibalization effects for a specific SKU within flavor and protein-range categories

If the business wants to show cannibalization effects for a certain SKU within a flavor and protein-range category associated to stores that roll up to geographies, then the data needs to support both detailed local analysis and broader rollups.

### 1. Core POS demand data

Best case grain:

- `UPC x Store x Week`

At minimum:

- `UPC`
- `store_id`
- `week_end_date`
- `units`
- `dollars`
- `base_units`
- `base_dollars`
- `ARP`
- promo metrics
- distribution or availability measures

If store-level data is not available, then `UPC x Geography x Week` can still work, but store-level data is much better for precise cannibalization analysis.

### 2. Product master data

Needed to define close substitutes:

- `UPC`
- brand
- description
- flavor
- flavor family
- protein grams
- protein range
- pack count
- net weight
- unit size
- package type
- launch date
- discontinue date

This is what allows a clean definition of "same flavor, same protein range, different pack size."

### 3. Store and geography hierarchy

Needed for market rollups:

- `store_id`
- store name
- retailer / banner
- channel
- region
- district
- geography / market id
- geography rollup names
- store open / close dates if available

This allows local effects to be rolled into market intelligence.

### 4. Assortment and distribution data

Critical for interpreting cannibalization correctly:

- item authorization by store
- first on-shelf week
- assortment adds / removes
- store-level distribution history
- ACV / TDP if direct store coverage is unavailable
- item availability or out-of-stock signals if available

Without this, it is easy to confuse distribution expansion with true demand transfer.

### 5. Pricing and merchandising data

Needed to explain why switching happened:

- regular price
- promo price
- discount depth
- TPR / feature / display support
- secondary placement if available
- merchandising calendar

### 6. Time and event data

Needed for event-based analysis:

- launch week
- first ship week
- first selling week
- promo start and end weeks
- assortment reset windows
- seasonal periods
- holiday flags

## Part 3: Should sales reps attached to geographies or stores be requested?

Yes, potentially, but as a secondary layer.

Sales rep or field execution data can help explain:

- why one geography launches better than another
- why some stores gain distribution faster
- why one market has stronger execution support
- whether differences are caused by execution rather than underlying demand

Useful fields would include:

- `sales_rep_id`
- rep-to-store mapping
- rep-to-market mapping
- assignment effective dates
- call frequency if available
- execution scorecards if available

This data is most useful when field execution meaningfully influences:

- authorization
- shelving
- displays
- promo compliance
- speed of distribution gains

It should be treated as a supporting contextual layer, not the primary basis for cannibalization logic.

## Part 4: How Brad would identify competitive brand products that cannibalize BUILT

External competitive cannibalization requires more than brand comparison. Brad would define competitors using a weighted similarity and observed-pressure framework.

## 4.1 The key external questions

The system should be able to answer:

- which competitor SKUs steal demand from BUILT
- which BUILT SKUs are most vulnerable to which competitor products
- when competitor launch, promo, or distribution changes threaten BUILT volume

## 4.2 Similarity framework for external competitors

Brad would define competitor similarity using:

- category / subcategory
- flavor family
- protein range
- pack count
- net weight or size band
- price tier
- product form
- channel presence
- distribution overlap
- promo behavior

The goal is to determine which external SKUs are true consumer-choice substitutes for each BUILT SKU.

## 4.3 Competitor tiers

For each BUILT SKU, competitors should be organized into concentric rings:

### Tier 1 competitors

- very close substitutes
- similar flavor family
- similar protein band
- similar pack architecture
- similar price tier

### Tier 2 competitors

- similar function but less direct substitution
- adjacent flavors or pack sizes
- somewhat different pricing

### Tier 3 competitors

- broad category competitors
- weaker direct substitution pressure

This keeps the analysis commercially realistic.

## 4.4 Product attributes needed for competitor matching

To identify likely competitive cannibalizers of BUILT, the system should ideally have for both BUILT and competitors:

- brand
- UPC
- flavor
- flavor family
- protein grams
- protein range
- pack count
- total net weight
- unit size
- form factor
- price
- price per count
- price per ounce
- claims or positioning
- channel and retailer presence

## 4.5 Evidence of actual competitive pressure

Similarity alone is not enough. Brad would also look for evidence such as:

- competitor promo spikes followed by BUILT decline
- competitor distribution gains followed by BUILT decline
- competitor launches followed by BUILT share loss
- negative relationship in residualized demand after controlling for BUILT's own drivers

This separates "looks similar" from "actually behaves like a cannibalizer."

## 4.6 External competitor pressure features

For each BUILT SKU by market-week, Brad would want features such as:

- number of close competitor SKUs active
- similarity-weighted competitor count
- weighted competitor ACV / TDP
- weighted competitor promo intensity
- weighted competitor average price
- minimum competitor price
- competitor assortment breadth
- competitor new-launch flags
- competitor similarity-weighted pressure score

## 4.7 Same-flavor versus same-need-state competition

Brad would explicitly model both:

- same-flavor substitution
- same-need-state substitution

Consumers may switch because a product has the same flavor, but they may also switch because it solves the same usage need even if flavor differs.

## 4.8 Market overlap and co-presence logic

A competitor only matters if it is present where BUILT is present. The system should therefore track:

- store overlap with BUILT
- market overlap with BUILT
- weeks of co-presence
- co-promo exposure
- co-distribution intensity

## 4.9 External competitor outputs

Useful outputs would include:

- top external competitor SKUs most likely to steal from each BUILT SKU
- competitor risk scores
- expected unit loss from competitor activity
- most dangerous brands by market
- most dangerous flavor or protein clusters by BUILT SKU

## Bottom line

To build a strong NPI and competitive cannibalization system, Brad would combine:

- internal substitution logic
- flavor and protein-range clustering
- pack-size-aware feature engineering
- market and store hierarchy
- distribution and promo context
- external competitor similarity
- observed demand-transfer pressure

That combination supports a much more complete view of how new items, new pack sizes, and competitive activity affect BUILT's assortment and portfolio outcomes.
