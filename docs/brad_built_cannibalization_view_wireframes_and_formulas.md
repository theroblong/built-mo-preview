# BUILT Cannibalization View Wireframes and Formulas

This artifact translates the proposed focused BUILT cannibalization views into:

- a simple visual layout
- the data fields that support each view
- the formulas or calculations behind each metric

It is grounded in what is available now from:

- [All_items_extract_100.csv](/Users/jasonbrazeal/Documents/FirstAgent/All_items_extract_100.csv)
- [built_specific_flavor_review.csv](/Users/jasonbrazeal/Documents/FirstAgent/outputs/built_specific_flavor_review.csv)

## What data we can support now

The following fields needed for a focused first-pass experience are present in `All_items_extract_100.csv`:

- `Geography`
- `Time Period`
- `Time Period End Date`
- `Brand`
- `UPC`
- `Description`
- `PACK COUNT`
- `FLAVOR`
- `Dollars`
- `Units`
- `TDP`
- `Average Weekly TDP`
- `Units SPM`
- `Average Weekly Units SPM`
- `Units SPP`
- `Units/TDP`
- `ARP`
- `Dollars, Promo`
- `Dollars, Non-Promo`
- `Units, Promo`
- `Units, Non-Promo`
- `Promo Weeks`
- `Base Dollars`
- `Base Units`
- `Incr Dollars`
- `Incr Units`
- `First Week Selling`
- `Number of Weeks Selling`

The following important flavor-enrichment fields can be supported from the review file:

- `specific_flavor_normalized`
- `flavor_family`

## View 1: New SKU / New Pack Cannibalization by Geography

### What the user sees

```text
+--------------------------------------------------------------------------------------+
| Focal Item: BUILT Mint Brownie 4pk | Specific Flavor: Mint Brownie | Channel: Grocery |
+--------------------------------------------------------------------------------------+
| Geography        | Base Units Chg | Units Chg | TDP Chg | Units/TDP Chg | Status     |
|------------------|----------------|-----------|---------|---------------|------------|
| TOTAL US         | +8%            | +12%      | +10%    | +2%           | Incremental|
| Texas            | -3%            | +2%       | +12%    | -9%           | Watch      |
| Mountain West    | -12%           | -6%       | +1%     | -7%           | Cannibal   |
+--------------------------------------------------------------------------------------+
| Likely donor SKUs in selected geography                                               |
| 1ct Mint Brownie | 12pk Mint Brownie | nearby same-family donor items                |
+--------------------------------------------------------------------------------------+
```

### Purpose

Show whether a new SKU or new pack size is adding demand or mostly shifting demand from existing items within each geography.

### Supporting data

From `All_items_extract_100.csv`:

- `Geography`
- `UPC`
- `Description`
- `PACK COUNT`
- `Units`
- `Base Units`
- `TDP`
- `Units/TDP`
- `First Week Selling`

From `built_specific_flavor_review.csv`:

- `specific_flavor_normalized`

### Useful formulas

If multiple time windows are available:

- `base_units_change_pct = (post_base_units / pre_base_units) - 1`
- `units_change_pct = (post_units / pre_units) - 1`
- `tdp_change_pct = (post_tdp / pre_tdp) - 1`
- `units_tdp_change_pct = (post_units_tdp / pre_units_tdp) - 1`

Suggested interpretation:

- if `Base Units` rises and `Units/TDP` rises, demand likely improved
- if `Units` rises but `Units/TDP` is flat or down while `TDP` rises, the gain may be reach-driven
- if focal SKU rises while same-flavor donor SKUs fall in the same geography, cannibalization is more likely

## View 2: Same Specific Flavor Pack-Size Ladder

### What the user sees

```text
Specific Flavor: Mint Brownie | Geography: Texas | Channel: Grocery

+----------------------------------------------------------------------------+
| SKU / Pack               | Pack Count | Base Units | Units | TDP | Units/TDP |
|--------------------------|------------|------------|-------|-----|-----------|
| Mint Brownie 1ct         | 1          | 1,240      | 1,320 | 80  | 16.5      |
| Mint Brownie 4pk         | 4          | 840        | 910   | 62  | 14.7      |
| Mint Brownie 12pk        | 12         | 410        | 455   | 28  | 16.3      |
+----------------------------------------------------------------------------+
| Insight: 4pk appears to be pulling more from 1ct than from 12pk            |
+----------------------------------------------------------------------------+
```

### Purpose

Help users evaluate whether multiple pack sizes of the same specific flavor should coexist in the assortment.

### Supporting data

- `Description`
- `PACK COUNT`
- `Units`
- `Base Units`
- `TDP`
- `Units/TDP`
- `First Week Selling`
- `specific_flavor_normalized`

### Useful formulas

For each specific flavor and geography:

- `pack_mix_share = sku_units / sum(units across same specific flavor pack set)`
- `pack_mix_base_share = sku_base_units / sum(base_units across same specific flavor pack set)`

Potential donor logic:

- same brand
- same `specific_flavor_normalized`
- different `PACK COUNT`
- same form family if available later

## View 3: Geography Heatmap

### What the user sees

```text
Rows = geographies
Columns = cannibalization signals

+----------------------------------------------------------------------------------+
| Geography     | Base Units Chg | Units Chg | TDP Chg | Units/TDP Chg | Heat Label |
|---------------|----------------|-----------|---------|---------------|------------|
| TOTAL US      | +              | +         | +       | +             | Green      |
| Southeast     | -              | flat      | +       | -             | Red        |
| Northeast     | flat           | +         | +       | flat          | Yellow     |
+----------------------------------------------------------------------------------+
```

### Purpose

Reveal where an item or pack architecture is truly helping versus where it is only expanding distribution or shifting existing demand.

### Supporting data

- `Geography`
- `Units`
- `Base Units`
- `TDP`
- `Units/TDP`

### Useful formulas

Simple scorecard logic:

- `demand_signal = sign(base_units_change_pct)`
- `reach_signal = sign(tdp_change_pct)`
- `productivity_signal = sign(units_tdp_change_pct)`

Example label rules:

- `Green`: `Base Units` up and `Units/TDP` up
- `Yellow`: `Units` up but `TDP` also up and productivity is flat
- `Red`: donor SKU down, focal SKU up, and net productivity weak or declining

## View 4: Channel Assortment Mix View

### What the user sees

```text
Channel: Grocery

+--------------------------------------------------------------------------------------+
| Flavor / Pack Group      | Demand Role   | Reach Role   | Assortment Guidance        |
|--------------------------|---------------|--------------|----------------------------|
| Mint Brownie 1ct         | Stable donor  | Broad        | Keep core                  |
| Mint Brownie 4pk         | Incremental   | Growing      | Expand selectively         |
| Mint Brownie 12pk        | Low velocity  | Narrow       | Monitor / reduce           |
+--------------------------------------------------------------------------------------+
```

### Purpose

Help the business decide the best product mix by channel without overloading the user with raw diagnostics.

### Supporting data

- channel field when available in the production dataset

## Bonus View: Weekly SKU Win Count Matrix

For an optional, easier-to-scan pattern view, add a weekly win/loss layer beside the core units and dollars views. This bonus path is documented in detail in [brad_weekly_win_count_bonus_path.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_weekly_win_count_bonus_path.md).

### What the user sees

```text
SKU group: Brownie Batter pack ladder | Geography: Total US

+------------------------------------------------------------------+
| SKU / Week             | W1 | W2 | W3 | W4 | Win % | Pattern     |
|------------------------|----|----|----|----|-------|-------------|
| Brownie Batter 1ct     | +  | -  | -  | +  | 50%   | Mixed       |
| Brownie Batter 4pk     | +  | +  | +  | +  | 100%  | Strong      |
| Brownie Batter 12pk    | +  | -  | -  | -  | 25%   | Losing      |
+------------------------------------------------------------------+
| Group weekly win count | 3  | 1  | 1  | 2  |       | Concentrated|
+------------------------------------------------------------------+
```

### Purpose

Reveal whether related SKUs are winning together or whether growth is concentrated in one SKU while related SKUs lose.

### Useful formulas

- `sku_week_win = current_units_per_store_or_tdp > trailing_4_week_avg_units_per_store_or_tdp`
- `weekly_win_count = count(sku_week_win = TRUE)`
- `weekly_win_pct = weekly_win_count / active_sku_count`
- `related_loss_pct = related_loss_count / related_active_sku_count`

Suggested interpretation:

- high group win percentage plus rising units/dollars = broad complementary growth
- focal SKU wins while related SKUs lose = possible cannibalization pattern
- group dollars rise while group units are flat = possible trade-up or premiumization
- group units rise while win percentage falls = concentrated growth that deserves drill-down
- `specific_flavor_normalized`
- `PACK COUNT`
- `Units`
- `Base Units`
- `TDP`
- `Units/TDP`
- `ARP`

### Useful formulas

Suggested assortment-support metrics:

- `channel_mix_share = sku_units / total_channel_units_for_relevant_set`
- `incrementality_proxy = focal_base_units_change_pct - avg_donor_base_units_change_pct`
- `reach_adjusted_productivity = Units/TDP`

Suggested action logic:

- `Keep`: strong `Base Units`, stable productivity, broad reach
- `Add / Expand`: rising `Base Units`, rising productivity, limited but growing reach
- `Reduce`: weak `Base Units`, declining productivity, overlapping donor set
- `Remove`: persistent low productivity and no clear incremental role

## View 5: Pre/Post Launch Diagnostic

### What the user sees

```text
Focal SKU: BUILT Mint Brownie 4pk | Geography: Texas

+----------------------------------------------------------------------------------+
| Metric          | Pre Launch | Post Launch | Change | Interpretation             |
|-----------------|------------|-------------|--------|----------------------------|
| Base Units      | 820        | 910         | +11%   | Underlying demand up       |
| Units           | 860        | 980         | +14%   | Observed sales up          |
| TDP             | 50         | 63          | +26%   | Distribution expanded      |
| Units/TDP       | 17.2       | 15.6        | -9%    | Productivity down          |
+----------------------------------------------------------------------------------+
```

### Purpose

Give the user a simple before/after diagnostic to explain whether a launch succeeded because of true demand or just because of wider distribution.

### Supporting data

- `Time Period End Date`
- `Units`
- `Base Units`
- `TDP`
- `Units/TDP`

### Useful formulas

For any metric:

- `change_abs = post_value - pre_value`
- `change_pct = (post_value / pre_value) - 1`

Interpretation pattern:

- `Base Units` up + `Units/TDP` down = mixed result, reach expanded but store productivity weakened
- `Base Units` up + `Units/TDP` up = strongest launch outcome
- `Units` up + `Base Units` flat = likely promo or reach effect rather than pure demand gain

## What supports same-specific-flavor geography cannibalization today

A strong first-pass geography cannibalization view can be built from the current assets by joining:

- `All_items_extract_100.csv` on `UPC`
- `built_specific_flavor_review.csv` on `upc`

That allows:

- grouping items by exact specific flavor
- narrowing donor sets within geography
- comparing pack sizes of the same specific flavor

## Recommended first polished view set

If the goal is a narrow and strong BUILT experience, start with:

1. New SKU / New Pack Cannibalization by Geography
2. Same Specific Flavor Pack-Size Ladder
3. Geography Heatmap
4. Pre/Post Launch Diagnostic

These four views are enough to tell a coherent story without becoming too experimental.
