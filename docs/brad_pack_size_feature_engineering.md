# Brad's Pack Size Feature Engineering Guide

This document describes how Brad would engineer pack-size-related features from the current SPINS fields available in the sample data.

It is intended to answer a specific practical question:

How do we distinguish products such as a 12-count box of Cookie Dough Chunk from a 4-count box using the data currently available?

## Objective

The goal is to create features that help the model understand that two products may be:

- the same brand
- the same flavor
- close substitutes
- but different pack-size architectures with different demand roles

This matters because pack size often changes:

- shopper mission
- value perception
- pricing behavior
- promo sensitivity
- distribution patterns
- cannibalization intensity

## Fields available in the current sample that matter most

The most useful current fields are:

- `UPC`
- `Brand`
- `Description`
- `PACK COUNT`
- `FLAVOR`
- `ARP`
- `Units`
- `Base Units`
- `Dollars`
- `Avg % ACV`
- `Max % ACV`
- `TDP`
- `Average Weekly TDP`
- promo-related fields such as `Units, Promo`, `Units, Non-Promo`, `Promo Weeks`, and discount fields

## Core engineering approach

Brad would treat each `UPC` as a distinct item, then engineer pack-size features that help place the item in relation to similar SKUs in the same brand, flavor family, market, and week.

The approach would have five layers:

1. direct pack-size identity features
2. price-normalized pack features
3. same-product-family comparison features
4. distribution and promo behavior features by pack size
5. relative competitive pressure features

## 1. Direct pack-size identity features

These are the most basic features.

### `pack_count_numeric`

Derived from:

- `PACK COUNT`

Purpose:

- direct numeric representation of item count

Example:

- 4
- 12

### `pack_count_band`

Derived from:

- `PACK COUNT`

Example bands:

- single
- 2 to 4
- 5 to 8
- 9 to 12
- 13 plus

Purpose:

- reduce noise and help the model learn broad pack architecture rather than overly precise count effects

### `large_pack_flag`

Derived from:

- `PACK COUNT`

Example logic:

- 1 if `PACK COUNT >= 10`
- 0 otherwise

Purpose:

- separate stock-up or pantry packs from smaller packs

### `small_pack_flag`

Derived from:

- `PACK COUNT`

Example logic:

- 1 if `PACK COUNT <= 4`
- 0 otherwise

Purpose:

- identify likely trial, convenience, or smaller household packs

## 2. Price-normalized pack features

These help distinguish whether a larger pack is positioned as a value pack or just a larger absolute-price item.

### `price_per_count`

Derived from:

- `ARP / PACK COUNT`

Purpose:

- compare unit economics across pack sizes

Use:

- distinguish whether the 12-pack offers a lower per-count price than the 4-pack

### `base_dollars_per_count`

Derived from:

- `Base Dollars / PACK COUNT`

Purpose:

- rough normalized economic view at the pack-count level

### `units_per_count`

Derived from:

- `Units / PACK COUNT`

Purpose:

- proxy for demand normalized by pack size

Note:

- this is descriptive and should be tested carefully before direct use in modeling if the target is also demand-based

### `arp_vs_same_flavor_pack_avg`

Derived from:

- `ARP`
- comparison to same-brand, same-flavor items with different pack counts

Purpose:

- measure whether the focal item is premium or discounted relative to nearby pack-size variants

## 3. Same-product-family comparison features

These features are critical for distinguishing a 12-pack from a 4-pack when the products are otherwise very similar.

Brad would define a product family using fields such as:

- `Brand`
- `FLAVOR`
- normalized `Description`

Then engineer the following:

### `same_brand_same_flavor_diff_pack_flag`

Purpose:

- identify when there is another SKU in the catalog that matches on brand and flavor but differs on pack count

### `pack_count_gap_to_nearest_same_flavor`

Derived from:

- difference in `PACK COUNT` between focal SKU and nearest same-brand same-flavor SKU

Example:

- 12-pack versus 4-pack gives a gap of 8

### `price_gap_to_same_flavor_alt_pack`

Derived from:

- difference in `ARP` between two pack-size variants

Purpose:

- capture whether the larger pack has a materially different absolute price

### `price_per_count_gap_to_same_flavor_alt_pack`

Derived from:

- difference in `price_per_count`

Purpose:

- capture whether one pack is positioned as a value option relative to another

### `same_flavor_pack_rank_within_brand`

Derived from:

- ranking `PACK COUNT` across same-brand same-flavor items

Example:

- smallest pack
- mid pack
- largest pack

Purpose:

- make pack architecture ordinal inside a product family

## 4. Distribution and promo behavior by pack size

Pack sizes often differ not just in size, but in where and how they are sold.

### `acv_by_pack_count`

Derived from:

- `Avg % ACV`
- `PACK COUNT`

Purpose:

- learn whether larger packs tend to have wider or narrower distribution

### `tdp_by_pack_count`

Derived from:

- `TDP`
- `Average Weekly TDP`
- `PACK COUNT`

Purpose:

- distinguish shelf support differences across pack sizes

### `promo_share_by_pack_count`

Derived from:

- `Units, % Promo`
- `Dollars, % Promo`
- `PACK COUNT`

Purpose:

- identify whether smaller or larger packs are more promo dependent

### `promo_discount_by_pack_count`

Derived from:

- `ARP % Discount` fields
- `PACK COUNT`

Purpose:

- measure whether the 4-pack and 12-pack rely on different discount mechanics

### `base_vs_promo_mix_by_pack`

Derived from:

- `Units, Promo`
- `Units, Non-Promo`
- `Base Units`

Purpose:

- distinguish steady stock-up demand from promo-reactive demand

## 5. Relative competitive pressure features

These features tell the model how each pack size sits inside its competitive neighborhood.

### `share_of_brand_pack_architecture`

Derived from:

- item demand or distribution divided by total same-brand family demand or distribution

Purpose:

- quantify whether the item is the dominant pack format or a niche alternative

### `same_brand_alt_pack_count`

Derived from:

- count of alternative same-brand SKUs with same flavor but different pack sizes

Purpose:

- more internal alternatives often means more cannibalization risk

### `same_brand_alt_pack_distribution_pressure`

Derived from:

- combined ACV or TDP of alternative pack-size variants

Purpose:

- capture how much sibling pack pressure exists in the market

### `same_brand_alt_pack_promo_pressure`

Derived from:

- combined promo intensity of alternative pack variants

Purpose:

- identify whether sibling packs are likely to pull demand during promo periods

## Example interpretation

For a Cookie Dough Chunk 12-pack versus 4-pack, Brad would want the model to learn patterns like:

- same flavor and same brand means likely substitution risk
- much larger `PACK COUNT` means different pack architecture
- lower `price_per_count` on the 12-pack may signal stock-up behavior
- higher promo share on the 4-pack may signal trial or convenience behavior
- broader ACV on one pack may indicate a different market role

This gives the model a more realistic understanding than simply treating both items as "Cookie Dough Chunk."

## Most important first-release features

If Brad had to prioritize only a few pack-size features from the current data, he would start with:

1. `pack_count_numeric`
2. `pack_count_band`
3. `price_per_count`
4. `same_brand_same_flavor_diff_pack_flag`
5. `price_per_count_gap_to_same_flavor_alt_pack`
6. `same_flavor_pack_rank_within_brand`
7. `same_brand_alt_pack_distribution_pressure`
8. `same_brand_alt_pack_promo_pressure`

## Limitations of the current data

The current sample does not appear to provide:

- net weight per package
- unit size per bar
- shopper-level purchase mission
- basket context
- household switching behavior

Because of that, these engineered features are still proxies. They can help the model distinguish 12-pack and 4-pack roles, but they do not fully capture why shoppers choose one over the other.

## Bottom line

From the current SPINS fields, Brad can distinguish a 12-pack from a 4-pack by combining:

- explicit pack count
- product family matching
- price normalization
- promo behavior
- distribution behavior
- sibling pack competitive pressure

That is enough to build meaningful pack-size-aware cannibalization features, even before adding richer shopper or product-attribute data.
