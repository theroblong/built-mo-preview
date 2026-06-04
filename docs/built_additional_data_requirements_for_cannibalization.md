# BUILT Additional Data Requirements for a Full Cannibalization View

This document lists the additional data requested from BUILT beyond the SPINS POS CSV data in order to build a comprehensive cannibalization intelligence capability.

It also takes into account the supplemental SPINS workbook [Item list BUILT and Category.xlsx](/Users/jasonbrazeal/Documents/FirstAgent/Item%20list%20BUILT%20and%20Category.xlsx), which adds useful product attributes beyond the base POS extracts.

The goal is to support a holistic view of product sales and understand how introducing certain products into the same mix affects outcomes across different contexts, especially those that influence:

- product assortment quality
- launch decisions
- package-size strategy
- market-specific portfolio performance
- profit-growing actions

This document focuses only on what additional data is required for a full view of cannibalization. It does not yet prescribe implementation details.

## Why SPINS data alone is not enough

The SPINS dataset provides a strong foundation for demand, price, promotion, and distribution signals. However, a full cannibalization tool requires additional data to answer questions such as:

- which BUILT products are truly close substitutes for each other
- which competitor products are the most realistic alternatives
- what assortment each store was actually carrying
- whether a sales shift was caused by product overlap, promo support, distribution expansion, or execution quality
- whether an innovation is incremental, self-cannibalizing, or margin-destructive

The newly added SPINS workbook improves the product-attribute layer because it includes fields such as:

- `Category`
- `Subcategory`
- `Brand`
- `UPC`
- `Description`
- `PACK COUNT`
- `FLAVOR`
- `NFP - PROTEIN`
- `NFP RANGES - PROTEIN VALUE`
- `FUNCTIONAL INGREDIENT`
- `HEALTH FOCUS`
- `SIZE POSITIONING`
- `SIZE`
- `UNIT OF MEASURE`
- `POSITIONING GROUP`
- `PRODUCT TYPE`

The separate measure dictionary workbook [BUILT- SPINS MEASURES.xlsx](/Users/jasonbrazeal/Documents/FirstAgent/BUILT-%20SPINS%20MEASURES.xlsx) also clarifies that SPINS already provides a meaningful set of modeling-ready measures for:

- distribution and selling breadth
- pricing and promo depth
- base versus incremental sales decomposition
- velocity normalized for distribution
- category and subcategory share
- first selling timing

To answer those questions well, additional product, store, assortment, execution, and profitability data is needed.

### High-value SPINS measures now explicitly documented

The measure dictionary suggests that the following SPINS measures are especially valuable for cannibalization analysis and should be considered part of the usable current-state data layer:

- distribution and reach: `# Stores Selling`, `% of Stores Selling`, `TDP`, `TDP, Any Promo`, `TDP, Non-Promo`
- per-store-style productivity: `Average Weekly Dollars Per Store Selling Per Item`, `Average Weekly Units Per Store Selling Per Item`
- launch timing: `First Week Selling`, `Number of Weeks Selling`
- pricing: `ARP`, `Base ARP`, `ARP, Promo`, `ARP, Non-Promo`, `ARP % Discount, Any Promo`
- promo decomposition: `Base Dollars`, `Incr Dollars`, `Base Units`, `Incr Units`, `Base EQ Units`, `Incr EQ Units`
- promo responsiveness: `Dollars, Promo Effect Index`, `Units, Promo Effect Index`, `EQ Units, Promo Effect Index`
- distribution-adjusted productivity: `Dollars SPM`, `Units SPM`, `EQ Units SPM`, `Dollars SPP`, `Units SPP`, `EQ Units SPP`, `Dollars/TDP`, `Units/TDP`, `EQ Units/TDP`
- share tracking: `Dol Shr, Category`, `Dol Shr, Sub-Cat`, `Unit Shr, Category`, `Unit Shr, Sub-Cat`, `EQ Unit Shr, Category`, `EQ Unit Shr, Sub-Cat`

These measures are important because they help distinguish true cannibalization from:

- promo-driven switching
- distribution-driven growth or decline
- launch ramp effects
- share changes caused by market expansion rather than substitution

### Important note on per-store versus distribution-normalized measures

SPINS appears to provide both per-store-style productivity measures and distribution-normalized productivity measures, and they should not be treated as interchangeable.

- `Average Weekly Dollars Per Store Selling Per Item` and `Average Weekly Units Per Store Selling Per Item` are the closest available measures to a true dollars-per-store-selling-item and units-per-store-selling-item view
- `Dollars SPM` and `Units SPM` are normalized per million dollars of ACV of stores selling the product
- `Dollars SPP` and `Units SPP` are normalized per percentage point of ACV
- `Dollars/TDP` and `Units/TDP` are normalized per total distribution points

For cannibalization analysis, the per-store-style measures are often easier to interpret as store productivity signals, while the SPM, SPP, and TDP-normalized measures are more useful for controlling for differences in distribution reach.

### Important caveat on `Incr Units`

`Incr Units` should not be interpreted as a generic week-over-week change in unit sales.

Based on the SPINS measure definition, `Incr Units` is specifically the portion of unit sales attributed to retailer merchandising or promotion. That makes it useful for separating promo lift from underlying demand, but not for measuring simple week-to-week movement in observed sales.

In practice, that means:

- `Incr Units` is best treated as a promo-attributed increment
- `Base Units` is best treated as underlying non-promo demand
- `Units` is still the observed real-world sales outcome
- a separate weekly change feature is still needed if we want to measure sharp shifts around launches, assortment changes, or cannibalization events

### Recommended derived weekly delta columns

If weekly SPINS data is available at the intended grain, the model should add explicit LAG-based change fields such as:

- `units_wow_delta` = `Units - LAG(Units, 1)`
- `base_units_wow_delta` = `Base Units - LAG(Base Units, 1)`
- `units_wow_pct` = `(Units / NULLIF(LAG(Units, 1), 0)) - 1`
- `base_units_wow_pct` = `(Base Units / NULLIF(LAG(Base Units, 1), 0)) - 1`

Those fields should be calculated within the correct partition, typically by:

- `upc`
- geography or market
- retailer or store if the source grain supports it

and ordered by weekly end date.

This is important because a LAG-based weekly delta can capture sudden demand shifts that are not caused by promotion alone, including:

- cannibalization after a new item enters the same assortment
- recovery after an out-of-stock period
- declines after assortment deletion or reduced shelf support
- launch ramp and post-launch decay

## Summary of additional data needed from BUILT

The additional data should ideally be provided in the following categories:

1. product master and product hierarchy
2. item lifecycle and launch history
3. inventory availability and out-of-stock data
4. store and market hierarchy
5. assortment and authorization data
6. store assortment rules and shelf-capacity constraints
7. pricing and trade support data
8. field execution and account coverage
9. profitability and finance data
10. customer, shopper, and basket data if available
11. qualitative business metadata

## 1. Product master and product hierarchy

This is one of the most important missing layers.

### What is now partially covered by the added SPINS workbook

The added workbook already gives us a stronger starting point for product normalization than the POS CSVs alone. In particular, it appears to provide:

- `upc`
- brand
- product description
- flavor
- protein grams
- protein range or protein band
- pack count
- segment / subcategory via `Category` and `Subcategory`
- functional ingredient
- health focus
- size positioning
- total net weight via `SIZE`
- unit of measure
- product type / positioning group

That means part of the product-master requirement has already been satisfied from SPINS and does not need to be re-requested from BUILT unless BUILT has cleaner internal versions.

It also suggests a practical two-level flavor structure for cannibalization analysis:

- `flavor_family`: the broader SPINS `FLAVOR` grouping such as `CHOCOLATE MINT` or `CARAMEL`
- `specific_flavor_normalized`: a more exact description-level flavor such as `Mint Brownie`, `Mint Chip`, or `Salted Caramel`

Both should be preserved as separate analytical fields rather than collapsed into a single flavor value.

### Why it matters

It lets the system define which items are truly close substitutes, such as:

- same flavor
- same protein range
- same pack architecture
- same usage occasion
- same innovation family

### Requested fields

- `upc`
- internal `sku_id` if different from UPC
- brand
- sub-brand if applicable
- product description
- short description if available
- long description if available
- flavor
- raw flavor text if available
- normalized flavor
- flavor detail or variant
- flavor family
- protein grams
- protein range or protein band
- pack count
- total net weight
- unit size
- package type
- format or form factor
- claim tags such as low sugar, high protein, keto, etc.
- product family or platform name
- normalized product family
- texture or format family such as puff, bar, bites, etc.
- innovation family if relevant
- segment / subcategory
- size band
- pack-size band
- active / discontinued status
- replacement sku mapping if applicable

### Fields still most important to request from BUILT even after the added workbook

The workbook is helpful, but it still does not appear to provide several attributes that are important for cannibalization logic and product substitution mapping:

- internal `sku_id`
- sub-brand
- short and long descriptions if maintained internally
- raw flavor text when it differs from the normalized SPINS flavor
- normalized flavor
- flavor detail or variant
- flavor family
- package type
- format or form factor
- normalized claim tags
- product family or platform name
- normalized product family
- texture or format family
- innovation family
- size band and pack-size band if not derived analytically
- active / discontinued status
- replacement SKU mapping

### Product hierarchy guidance

The product hierarchy should not rely only on a single general flavor field.

For example, a product such as `BUILT Puff Salted Caramel Bar` may appear in multiple descriptions that contain the string `Salted Caramel`, while the available structured flavor field might only say `CARAMEL`.

To support accurate cannibalization analysis, BUILT should ideally provide several hierarchy layers:

- raw product description
- normalized product name
- raw flavor text
- normalized flavor
- flavor family
- flavor cluster if used internally
- brand
- sub-brand
- product family
- form factor or format family

Example hierarchy:

- brand: `BUILT`
- sub-brand: `BUILT Puff`
- product family: `Protein Bar`
- raw flavor text: `Salted Caramel`
- normalized flavor: `Salted Caramel`
- flavor family: `Caramel`
- format family: `Puff Bar`

This is important because the model needs to distinguish:

- exact same-flavor substitution
- same flavor-family substitution
- same format substitution
- same need-state substitution

If BUILT does not already maintain this structure, then a mapping file from `UPC` to normalized hierarchy attributes should be requested or created and reviewed with the business.

### Why this is essential

Without the remaining hierarchy layer, the model cannot reliably distinguish:

- a new pack size from a new product concept
- a close substitute from a distant one
- same-flavor internal switching from broader portfolio effects

### Recommended analytical flavor fields

For BUILT specifically, the working product hierarchy should retain both a broad flavor-family field and a specific flavor field:

- `flavor_family`: the structured SPINS flavor bucket
- `specific_flavor_raw`: first-pass flavor text parsed from product description
- `specific_flavor_normalized`: cleaned and standardized flavor name used for analysis

This matters because items that share the same broad family may still behave differently in cannibalization analysis. For example:

- `CHOCOLATE MINT` may include `Mint Brownie`, `Mint Chip`, and `Grasshopper Cookie`
- `CARAMEL` may include `Salted Caramel` and `Salted Caramel Chocolate`

That separation supports analysis at both levels:

- broad flavor-family substitution
- exact specific-flavor substitution

## 2. Item lifecycle and launch history

### Why it matters

Cannibalization is often event-driven. The model needs to know when products were introduced, expanded, changed, or discontinued.

### Requested fields

- launch date
- first ship date
- first authorized date
- first selling date by retailer or market if available
- reformulation date if applicable
- package change date if applicable
- discontinuation date
- reset date or assortment-change date
- innovation type flag such as new product, new flavor, new pack size, renovation, seasonal item

### Why this is essential

It helps distinguish:

- normal sales variation
- a true launch event
- a package-size introduction
- a reformulation or product replacement

## 3. Inventory availability and out-of-stock data

This should be added explicitly because cannibalization is easy to misread when one item is unavailable.

### Why it matters

If a SKU declines while another rises, that may reflect true substitution, but it may also be forced switching caused by stockouts or low availability.

Without availability data, the system can overstate cannibalization and misinterpret assortment effects.

### Requested fields

- store-level in-stock flag by week or day if available
- store-level out-of-stock flag by week or day if available
- beginning inventory
- ending inventory
- on-hand inventory
- units shipped to store if available
- units shipped to distribution center if relevant
- fill rate
- service level
- weeks of supply if available
- backorder flag if available
- replenishment delay or gap if available
- temporary unavailable flag
- void or distribution void flag

### Helpful derived fields if BUILT can provide them

- `in_stock_rate`
- `oos_days`
- `stockout_week_flag`
- `low_inventory_flag`
- `replenishment_gap_days`
- `availability_adjusted_velocity`

### Why this is essential

It helps separate:

- true cannibalization
- forced substitution due to stockouts
- weak demand caused by lack of inventory
- poor execution caused by replenishment issues

If store-level inventory is not available, then DC-level or region-level availability is still worth requesting as a second-best option.

## 4. Store and market hierarchy

### Why it matters

BUILT wants to understand how product mix affects outcomes across contexts, especially by geography and market.

### Requested fields

- `store_id`
- retailer / banner
- channel
- store format
- region
- district
- division
- geographic market id
- geography rollup names
- store open date
- store close date if applicable
- cluster or segment codes used internally by BUILT

### Why this is essential

It allows local store outcomes to roll up into meaningful geographical and account-level insights.

## 5. Assortment and authorization data

This is one of the most important additions for assortment-focused cannibalization analysis.

### Why it matters

To evaluate ideal assortment, the system needs to know not just what sold, but what was actually ranged and intended to be sold.

### Requested fields

- store-level authorized assortment by week or effective period
- item authorization start and end dates
- planned assortment versus actual assortment
- resets or assortment changes by store or account
- item adds and deletes
- planogram or shelf-set information if available
- facings or shelf-space information if available
- void status if available

### Why this is essential

Without assortment and authorization data, it is difficult to distinguish:

- demand transfer caused by overlapping assortment
- missing demand caused by lack of authorization
- true cannibalization versus simple assortment expansion

## 6. Store assortment rules and shelf-capacity constraints

This should be requested separately from authorization data because stores and retailers may have explicit rules governing how many BUILT items, flavors, or pack levels they are allowed to carry.

### Why it matters

Authorization data tells us what a store could carry or did carry. Store rules tell us what the shelf was designed to carry.

That distinction is critical for assortment optimization and cannibalization interpretation.

For example:

- a store may be limited to a maximum number of BUILT SKUs
- a retailer may require a specific mix of pack sizes
- a shelf set may allow only a certain number of flavors
- a new SKU may displace an old one because of space rules rather than pure demand substitution

Without this layer, the system may overstate cannibalization when the underlying issue is shelf capacity or assortment design.

### Requested fields

- retailer or banner
- store format
- assortment tier or cluster
- effective start and end dates for the rule set
- max total BUILT SKUs allowed
- min total BUILT SKUs required if relevant
- max SKUs by sub-brand
- max SKUs by flavor family
- max SKUs by protein range if relevant
- allowed pack sizes or pack-size levels
- required core SKUs
- optional SKUs
- substitution or replacement rules
- planogram set name or version
- facings or shelf-space limits if available
- linear shelf space if available
- reset rules or assortment review windows

### Examples of useful rule logic

- must carry all 4-pack core items before adding 12-pack items
- may carry only 2 caramel-family flavors at a time
- may carry only 1 item per flavor at each pack-size level
- shelf supports 8 total BUILT facings
- innovation SKU can enter only if a low-velocity incumbent is removed

### Why this is essential

It helps distinguish:

- true demand cannibalization
- forced assortment substitution
- shelf-capacity constraints
- retailer-specific assortment design effects

This is especially important if BUILT wants the system to recommend ideal product assortment rather than only describe observed sales shifts.

## 7. Pricing and trade support data

### Why it matters

If one item outperforms another, it may be because of pricing or support rather than intrinsic product preference.

### Requested fields

- regular list price
- retailer-specific everyday price if available
- promoted price
- discount depth
- trade spend by SKU / retailer / week if available
- TPR events
- feature events
- display events
- secondary placement support
- promotional calendar
- customer-specific pricing agreements if relevant

### Why this is essential

It allows the system to separate:

- price-driven switching
- promotion-driven switching
- assortment-driven cannibalization

## 8. Field execution and account coverage data

Yes, this is where sales reps tied to stores or geographies can help.

### Why it matters

Geography-level differences may be driven partly by execution quality rather than pure consumer demand.

### Requested fields

- `sales_rep_id`
- rep-to-store mapping
- rep-to-geography mapping
- account manager mapping
- broker or distributor mapping if relevant
- assignment effective dates
- call frequency if available
- execution scorecards if available
- display compliance audits if available
- shelf placement audits if available
- in-stock or void audits if available

### Why this is useful

This helps explain:

- why launches succeed more in some markets
- why distribution ramps faster in some territories
- whether execution quality is affecting cannibalization outcomes

### Priority

- medium priority overall
- high priority if BUILT believes field execution differs significantly by market or account

## 9. Profitability and finance data

This is essential if the goal is not just to measure units moved, but to discover profit-growing insights.

### Why it matters

A product can look successful on volume while destroying portfolio profit.

### Requested fields

- unit cost
- gross margin per SKU
- contribution margin per SKU
- trade spend allocation if available
- retailer-specific margin adjustments if relevant
- net revenue definitions
- cost changes over time if material

### Why this is essential

It allows the system to estimate:

- margin cannibalization
- whether a launch is revenue-accretive but profit-destructive
- ideal assortment from a profit perspective, not just a volume perspective

## 10. Customer, shopper, and basket data if available

This is not always available, but it can materially improve interpretation.

### Why it matters

It helps separate:

- true substitution
- separate shopper missions
- trial behavior
- stock-up behavior

### Requested fields

- loyalty-linked household purchase data
- basket-level transaction data
- repeat rate data
- buyer overlap across SKUs
- household penetration
- trips or occasions if available

### Why this is useful

It helps show whether a 4-pack and a 12-pack compete for the same shoppers or serve different purchase occasions.

### Priority

- optional but highly valuable

## 11. Qualitative business metadata

### Why it matters

Not everything important is visible in POS numbers alone. Business context improves interpretation and scenario design.

### Requested fields or inputs

- internal product strategy notes
- intended role of each SKU in the assortment
- target shopper or usage occasion
- innovation objective such as acquisition, premiumization, or basket growth
- known product replacements
- known retailer-specific assortment strategy
- strategic accounts and priority markets

### Why this is useful

It helps the system understand whether an item was intended to:

- drive trial
- support stock-up
- fill a flavor gap
- trade shoppers up
- defend against competitors

## Most important additional data to request first

If BUILT cannot provide everything at once, the highest-priority additions beyond SPINS are:

1. product master enrichment beyond the added SPINS workbook, especially normalized flavor, sub-brand, family, format, lifecycle status, and replacement mappings
2. item lifecycle and launch history
3. inventory availability and out-of-stock data
4. store-to-market hierarchy
5. assortment and authorization data
6. store assortment rules and shelf-capacity constraints
7. pricing and trade support data
8. margin and profitability data

The next tier would be:

9. field execution and sales coverage data
10. shopper, basket, or loyalty data
11. qualitative assortment strategy context

## Why sales rep or geography ownership data can matter

To answer the specific question directly: yes, it may be worth requesting sales reps attached to geographies or stores.

That data is especially useful if:

- rep quality differs across markets
- rep involvement influences launches
- rep involvement affects display compliance, shelf presence, or distribution gains
- BUILT wants to separate consumer response from execution differences

It is not the first dataset I would request, but it is absolutely worth asking for if execution is believed to be a meaningful driver of performance variation.

## What a full-view cannibalization system should ultimately be able to answer

With the right additional data, the system should be able to answer questions like:

- which BUILT SKUs are cannibalizing each other
- which competitor SKUs are cannibalizing BUILT
- whether a new flavor or pack size is incremental or destructive
- which assortments are too crowded
- which stores or markets can support more variety
- which SKUs should be added, kept, resized, promoted, or removed
- where BUILT can grow profit, not just gross sales

## Bottom line

The added SPINS workbook closes part of the product-attribute gap by providing category, subcategory, UPC, description, pack count, flavor, protein, functional ingredient, health focus, and size-related fields.

The most important remaining missing pieces are:

- richer product hierarchy with normalized flavor mapping and internal family structure
- lifecycle and launch history
- inventory availability and out-of-stock data
- store-to-market hierarchy
- assortment and authorization data
- store assortment rules and shelf-capacity constraints
- pricing and trade support detail
- profitability data

If BUILT can also provide field execution, shopper, and strategic context data, the cannibalization tool will be much stronger and more actionable for ideal assortment decisions.
