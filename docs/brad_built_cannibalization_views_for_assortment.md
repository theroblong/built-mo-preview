# BUILT Cannibalization Views for Geography and Assortment Decisions

This note outlines how a polished BUILT user experience could show cannibalization for:

- new product launches
- new package sizes
- same specific flavors
- geography-specific demand shifts

It also proposes the most useful user-facing views for informing assortment and product-mix decisions by channel.

## Core design principle

The experience should not try to answer every cannibalization question in one screen.

Instead, it should help the user move through a small set of tightly scoped views:

1. what changed
2. where it changed
3. which items likely lost demand
4. whether the shift looks demand-driven, distribution-driven, or promo-driven
5. what assortment action the business should consider

## 1. New Product / New Pack Cannibalization View

This is the most important view for launch evaluation.

### Primary question

When a new SKU enters the assortment, is it:

- incremental
- neutral
- mildly cannibalizing
- strongly cannibalizing

### Recommended view structure

Rows:

- focal launch SKU
- likely donor SKUs from the same brand
- optionally competitor SKUs for context

Columns:

- geography
- channel
- specific flavor
- pack count / package size
- launch timing
- `Base Units` change
- `Units` change
- `TDP` change
- `Units/TDP` change if true per-store metrics are unavailable
- cannibalization score or label

### Best logic for same-flavor pack-size analysis

If the new item is a new package size of an existing specific flavor, the donor pool should be narrowed to:

- same brand
- same specific flavor
- same product family / form factor
- different pack size or different weight architecture

Example:

- focal item: `Built Mint Brownie Bar 4pk`
- likely donor items: `Built Mint Brownie Bar 1ct`, `Built Mint Brownie Bar 12pk`

### Geography interpretation

The same launch can behave differently by geography, so the view should show:

- geography-level results first
- national rollup second

That lets users see:

- where a launch is truly incremental
- where it is just shifting demand across existing BUILT items
- where it may be failing because of weak reach rather than weak demand

## 2. Specific Flavor Cannibalization View

This view should focus on the exact flavor level rather than broad SPINS flavor family alone.

### Primary question

Are we cannibalizing ourselves within the same specific flavor?

### Why this matters

Broad SPINS flavor buckets can hide important differences.

For example:

- `CHOCOLATE MINT` could include `Mint Brownie`, `Mint Chip`, and `Grasshopper Cookie`

Those should not automatically be treated as the same substitution set.

### Recommended view structure

Filters:

- brand
- channel
- geography
- product family
- specific flavor

Rows:

- each SKU variant within the same specific flavor

Columns:

- pack count
- size
- launch date / first week selling
- `Base Units`
- `Units`
- `TDP`
- `Units/TDP`
- demand change versus pre-launch baseline
- likely donor / recipient role

### Best user outcome

This view should help a user answer:

- should we keep multiple sizes of this specific flavor
- is the new size incremental
- is one size simply displacing another

## 3. Geography Heatmap View

This is the best view for showing that cannibalization is not uniform.

### Primary question

Where is the product or pack architecture helping versus hurting the assortment?

### Recommended view structure

Rows:

- geographies

Columns:

- cannibalization label
- `Base Units` trend
- `Units` trend
- `TDP` trend
- reach-adjusted productivity trend
- share trend if available

Color logic:

- green: incremental or low cannibalization
- yellow: mixed / monitor
- red: likely destructive cannibalization

### Best user outcome

This lets BUILT see:

- which markets can support more variety
- which markets are over-assorted
- where a launch should expand next
- where a SKU should be reduced, resized, or replaced

## 4. Channel Assortment Mix View

This is where the experience becomes actionable for product-mix decisions.

### Primary question

What assortment mix works best by channel?

### Recommended channel slices

- club
- grocery
- convenience
- natural / specialty
- mass
- e-commerce if available

### Recommended view structure

For each channel:

- total assortment size
- top specific flavors
- top pack architectures
- SKUs that appear incremental
- SKUs that appear to cannibalize incumbents
- recommended keep / add / reduce / remove list

### Best user outcome

This helps channel teams avoid copying one assortment strategy into channels where shopper needs are different.

## 5. Pre/Post Launch Change View

This should be the simplest diagnostic view.

### Primary question

What changed before and after the launch or reset?

### Recommended view structure

Time windows:

- pre-launch baseline
- immediate launch window
- stabilized post-launch window

Metrics:

- focal SKU `Base Units`
- donor SKU `Base Units`
- focal SKU `Units`
- donor SKU `Units`
- `TDP`
- `Units/TDP`

### Best user outcome

This helps the user see whether:

- the new item added demand
- the new item only shifted demand
- the change was temporary
- the change was tied to distribution ramp

## Most useful assortment decision views by channel

If the goal is best product mix assortment by channel, the highest-value user views are:

1. new SKU / new pack cannibalization by geography and channel
2. same specific flavor pack-size view
3. geography heatmap of incremental versus destructive launches
4. channel assortment mix view
5. pre/post launch diagnostic view

## Recommended metric core for these views

To stay polished and trustworthy, the front-end metric core should stay narrow:

- `Base Units`
- `Units`
- `TDP`
- `Units/TDP` when per-store metrics are unavailable
- `ARP`
- launch timing such as `First Week Selling`
- specific flavor
- pack count / size
- geography
- channel

If richer SPINS or internal data becomes available, then also add:

- `# Stores Selling`
- `% of Stores Selling`
- `Average Weekly Units Per Store Selling Per Item`
- `Unit Shr, Sub-Cat`

## Final recommendation

For BUILT, the experience should present cannibalization in a decision sequence:

1. identify the focal new item or pack
2. narrow the likely donor set to same specific flavor and same family where appropriate
3. compare pre/post demand within each geography
4. separate demand change from distribution change
5. roll the result into a channel assortment recommendation

That approach keeps the experience narrow, interpretable, and useful for real product-mix decisions rather than turning it into a broad but noisy analytics tool.
