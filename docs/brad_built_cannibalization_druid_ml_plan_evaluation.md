# Brad's Evaluation of the BUILT Druid and ML Workflow Plan

This note evaluates the Druid query and ML workflow plan in:

- [brad_built_cannibalization_druid_ml_plan.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_cannibalization_druid_ml_plan.md)

The short version: the plan is directionally strong and already contains the right product idea, which is a flexible pairwise comparison system rather than a hard-coded list of primary cannibalization targets. Before implementation, a few table design and SQL assumptions should be tightened so the tool can compare any pack size, any specific flavor, and selected competitor items without being forced back into a narrow BUILT pack-ladder workflow.

## Product Requirement to Protect

The tool should not only answer "what are the primary cannibalization targets?"

It should let a user choose:

- any focal UPC
- any focal pack size within a specific flavor
- any comparison pack size from that same flavor
- one specific flavor versus another specific flavor
- one BUILT item or flavor versus one or more competitor items
- one brand, brand line, flavor family, or user-selected SKU basket against another

That means the core data product should be a reusable pairwise comparison layer:

```text
focal_item x comparison_item x geography x week
```

The default view can still surface the most likely cannibalization targets first. But the underlying system should preserve user-directed exploration.

## What Is Strong in the Plan

The plan's strongest choice is the universal comparison pool. It correctly frames comparisons as dynamic focal/candidate pairs with a `comparison_type` and `relationship_distance`, rather than as separate single-purpose reports.

The relationship taxonomy is also useful:

- same flavor, same brand, different pack count
- same flavor, different brand
- same family, same brand
- same family, different brand
- cross-family, same brand
- cross-family, different brand

That structure gives the UI a clean way to start narrow and widen scope only when the user asks. It also supports a sensible default: open on same-flavor pack ladder, then let the user expand to cross-flavor and competitive comparisons.

The model design also has a good conceptual split:

- a risk classifier for cannibalization likelihood
- a donor ranker for likely source SKUs
- an event detector for whether a change is material enough to show

That is better than trying to force all questions through a single "cannibalization score."

## Key Implementation Gaps

### 1. Competitor rows are filtered out too early

Query 0 says the filtered table should include BUILT rows plus same-subcategory competitor rows. But Query 1 ends with:

```sql
WHERE
  w."Brand" IN ('BUILT BAR','BUILT PUFF','BUILT SOUR PUFF','BUILT')
```

That makes `built_enriched_weekly` BUILT-only. Query 2 and Query 2b then join against `built_enriched_weekly`, so competitor comparisons cannot actually work as written.

Recommended fix:

- keep `weekly_enriched_items` as a category-level enriched table containing BUILT and eligible competitors
- add `is_built_brand`, `is_priority_competitor`, and `competitive_tier` flags
- filter the UI default to BUILT focal items, but do not remove competitor rows from the comparison source

### 2. The pair table should use neutral focal/comparison language

The artifact sometimes shifts between `candidate`, `donor`, and `competitor`. That is understandable analytically, but it can narrow the design too early.

Recommended naming:

```text
focal_upc
comparison_upc
comparison_type
relationship_distance
comparison_direction
```

Then donor status becomes an output of scoring, not an assumption baked into the table name.

This matters because the user may compare two flavors or two competitor items without knowing which one is the donor in advance.

### 3. Query 4 still assumes pack-ladder-only inputs

Query 4 references `pack_ladder_pairs_weekly`, while the flexible design is built around `comparison_pool_weekly`.

Recommended fix:

- replace `pack_ladder_pairs_weekly` with `comparison_pool_weekly`
- retain all `comparison_type` values
- make pack-specific fields nullable for non-pack-ladder comparisons
- aggregate comparison-side pre/post metrics for every selected pair type

This keeps the same machinery available for pack size, flavor, family, and competitor analysis.

### 4. Arbitrary user-selected comparisons need first-class support

The plan supports predefined relationship distances well, but client workflows may be more ad hoc:

- compare Brownie Batter 4pk against Coconut 12pk
- compare all Coconut SKUs against all Salted Caramel SKUs
- compare BUILT PUFF Mint Chip against selected QUEST and BAREBELLS SKUs
- compare one retailer-specific assortment basket against another

Recommended addition:

Create a `user_comparison_set` or request-time parameter model:

```text
comparison_request_id
focal_selection_type       -- UPC, flavor, flavor_family, brand_line, brand, basket
focal_selection_values
comparison_selection_type  -- UPC, flavor, flavor_family, brand_line, brand, basket
comparison_selection_values
geography_scope
channel_scope
week_window
```

The query engine should expand those selections into UPC pairs, then score them using the same pairwise feature pipeline.

### 5. The ML labels risk becoming circular

The classifier is trained on labels generated directly from focal and donor pre/post percent changes, while those same percent changes are top model features. That can be useful for explainable triage, but it is not yet a true predictive model if the features are only known after the event.

Recommended framing:

- use the deterministic labels for historical scoring and training bootstrap
- separate historical measurement features from forward-looking scenario features
- for prediction, rely more heavily on pre-event similarity, price, distribution, promotion, velocity, seasonality, geography, and item relationship features
- keep post-event deltas for retrospective measurement and validation

### 6. Some SQL should be validated against Druid syntax

Several expressions may need Druid-specific adjustment before execution, including:

- `SAFE_DIVIDE`
- `STRING_TO_ARRAY`
- `CARDINALITY`
- some uses of `SPLIT_PART`
- regex syntax inside `REGEXP_REPLACE`
- list parameters in Query 2b

Recommended fix:

- create a Druid SQL compatibility pass before engineering starts
- test each query against a small Druid sample
- split complex geography parsing into a lookup or curated dimension if SQL support becomes brittle

### 7. Weekly win counts are a strong additive path

The weekly win-count idea fits well as an additive layer in the Druid plan. It should not replace units, dollars, base units, velocity, price, promotion, or distribution controls. Its value is that it gives business users a faster way to see whether a related SKU group is improving together.

Recommended positioning:

- compute deterministic `sku_week_win_flag` values from the enriched weekly table
- aggregate them into `weekly_win_count` and `weekly_win_pct` by flavor, pack ladder, brand line, channel, geography, or custom comparison basket
- create pairwise association metrics such as `co_win_rate`, `opposition_rate`, and `P(comparison_loses | focal_wins)`
- use the outputs as simple UI drilldowns and as additional ML features

This path is especially attractive because it bridges simple statistics and advanced modeling. In the UI, it can show approachable statements such as "5 of 7 SKUs won" or "the focal SKU won while 3 related SKUs lost." In the modeling layer, it can feed Bayesian win-rate estimates, correlation/association metrics, sequence models, or graph neural networks later.

The guardrail: win counts are pattern evidence, not causal proof. A low win percentage or high opposition rate should trigger drilldown into units, dollars, TDP, price, promotion, and model explanations before the tool claims cannibalization.

## Recommended Design Adjustment

The final implementation should use three layers:

### Layer 1: Enriched weekly item table

One row per:

```text
upc x geography x week
```

Includes BUILT and eligible competitor items. Adds normalized flavor, flavor family, brand line, pack count, size, channel, geography fields, category fields, and competitor flags.

### Layer 2: Flexible comparison pair table

One row per:

```text
focal_upc x comparison_upc x geography x week
```

Generated from default relationship rules or from a user-selected comparison request. This layer should not assume the comparison item is already a donor.

### Layer 3: Measurement and scoring outputs

One row per:

```text
focal_upc x comparison_upc x geography x scoring_window
```

Includes observed demand transfer metrics, cannibalization probability, likely donor ranking, confidence, materiality flags, and explanation drivers.

## UI Implication

The UX should default to the most useful question:

```text
Specific flavor -> compare pack sizes
```

But every default should be editable:

- focal selector: UPC, pack size, specific flavor, flavor family, brand line, brand, custom basket
- comparison selector: same options
- relationship filter: same flavor, same family, same brand, competitor brand, selected SKUs, full category
- geography selector: Total US, region, retailer, banner, channel
- scoring mode: historical measurement, current monitoring, scenario-style prediction

This keeps the primary targets visible while still giving the client the freedom to ask their own comparison questions.

## Bottom-Line Evaluation

The artifact is a good technical foundation and should be kept. Its central idea, a universal relationship-aware comparison pool, is exactly the right architecture for a flexible cannibalization tool.

The main implementation change is to stop treating pack-ladder cannibalization as the pipeline's hidden center of gravity. Pack ladder should be the default workflow and strongest prior, but not the data model. The data model should be neutral pairwise comparison. That will support the business question you raised: compare any pack size of any flavor against its other pack sizes, other flavors, and competitor items without rebuilding the pipeline for each question.
