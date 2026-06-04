# BUILT 95M-Row SPINS Utilization Audit

This note checks whether the current Druid and ML plan is doing everything reasonable with the 51GB / 95M-row SPINS file currently being loaded into Druid.

Verdict:

The plan is directionally sound and uses the right architecture, but it should be expanded to carry more of the SPINS columns into the enriched Druid layer and ML feature tables. The current plan uses the core backbone well, but underuses several high-value SPINS fields already present in the sample extract:

- year-ago measures
- EQ units
- Avg ACV and promo/non-promo ACV
- Average Items Selling
- Weight Weeks
- promo type lift fields
- promo type discount fields
- promo type ARP and Base ARP fields
- Dollars/TDP and Dollars SPM/SPP revenue productivity
- non-promo versus promo decomposition beyond units

The fix is not to ask the client for more data. The first fix is to preserve and derive more from SPINS.

## What the Current Plan Already Uses Well

The plan already uses the most important core fields:

- `UPC`
- `Brand`
- `Description`
- `Geography`
- `Time Period End Date` / week
- `PACK COUNT`
- `FLAVOR`
- `Units`
- `Base Units`
- `Dollars`
- `Base Dollars`
- `TDP`
- `Max % ACV`
- `Average Weekly Units SPM`
- `ARP`
- promo weeks
- `Units, Promo`
- `Units, Non-Promo`
- `Incr Units`
- `First Week Selling`
- `Number of Weeks Selling`

These fields are enough to build:

- same-flavor pack ladder detection
- distribution-led growth flags
- base demand deltas
- promo confounding controls
- launch/ramp monitoring
- pairwise comparison pools
- win counts
- event detection
- Mo's first polished UI

## Main Gap: Query 0 Is Too Narrow

The sample extract has 167 columns. Query 0 in the current Druid plan selects only a subset.

That is okay for a first sketch, but for the real 95M-row load we should carry a wider curated SPINS field set into `weekly_enriched_items`.

The enriched Druid layer does not need every raw column forever, but it should preserve enough fields to calculate:

- year-over-year trends
- promo-type controls
- price and discount mechanics
- revenue versus unit tradeoffs
- distribution quality
- ACV-based reach changes
- normalized productivity
- category trend and noise baselines

## SPINS Fields We Should Add to the Enriched Table

### 1. Year-ago measures

Already in sample:

- `Dollars, Yago`
- `Units, Yago`
- `EQ Units, Yago`
- `Avg % ACV, Yago`
- `Max % ACV, Yago`
- `TDP, Yago`
- `Average Weekly TDP, Yago`
- `Average Items Selling, Yago`
- `Number of Weeks Selling, Yago`
- `Weight Weeks, Yago`
- promo, price, lift, ARP, and base measures with `Yago` variants

Use for:

- seasonality control
- year-over-year trend features
- category softness versus SKU-specific weakness
- noisy-week suppression
- forecast baselines

Derived features:

- `units_yoy_pct`
- `base_units_yoy_pct`
- `tdp_yoy_pct`
- `arp_yoy_pct`
- `velocity_yoy_pct`
- `promo_intensity_yoy_delta`

Recommendation:

Carry year-ago versions for core demand, distribution, price, promo, and productivity fields.

### 2. EQ units

Already in sample:

- `EQ Units`
- `EQ Units, Yago`

Use for:

- pack-size adjusted comparison
- 1ct versus multipack normalization
- fairer volume comparison across pack counts

Derived features:

- `eq_units_per_tdp`
- `eq_units_yoy_pct`
- `base_eq_units_proxy` if available in full extract

Recommendation:

Use `EQ Units` as a supporting model feature, especially for pack-ladder comparisons. Do not replace `Base Units` as the primary cannibalization signal.

### 3. Avg ACV and Max ACV

Already in sample:

- `Avg % ACV`
- `Max % ACV`
- promo/non-promo variants
- year-ago variants

Use for:

- reach controls
- availability proxy
- distinguishing broad distribution from strong store productivity
- promo availability context

Derived features:

- `avg_acv_pct_chg`
- `max_acv_pct_chg`
- `acv_gap = max_acv - avg_acv`
- `promo_acv_share`
- `nonpromo_acv_share`

Recommendation:

Keep both `TDP` and ACV fields. TDP alone is not enough to describe reach quality.

### 4. Average Items Selling and Weight Weeks

Already in sample:

- `Average Items Selling`
- `Weight Weeks`
- promo/non-promo weight weeks
- year-ago variants

Use for:

- assortment breadth proxy
- panel coverage / evidence strength
- denominator quality
- distribution reliability

Derived features:

- `avg_items_selling_yoy_pct`
- `weight_weeks_coverage_ratio`
- `evidence_weight`
- `promo_weight_week_share`

Recommendation:

Use these in guardrails and confidence scoring. They are especially useful when store counts are not present.

### 5. Promo decomposition and promo type detail

Already in sample:

- `Dollars, Promo`
- `Dollars, Non-Promo`
- `Dollars, % Promo`
- `Units, Promo`
- `Units, Non-Promo`
- `Units, % Promo`
- `Promo Weeks`
- `Incr Dollars`
- `Incr Units`
- lift fields for TPR, display, feature, feature + display, feature only, display only, SPK

Use for:

- promo confounding controls
- promo-driven cannibalization
- donor defense promo detection
- separating promotion lift from base demand transfer

Derived features:

- `units_pct_promo`
- `dollars_pct_promo`
- `incr_units_share`
- `promo_lift_max`
- `feature_display_lift_flag`
- `donor_promo_defense_flag`
- `focal_promo_advantage_vs_comparison`

Recommendation:

Do not only carry `promo_weeks` and `incr_units`. The model should also see promo depth/type and promo/non-promo decomposition.

### 6. Discount, ARP, and Base ARP by promo type

Already in sample:

- `ARP`
- `ARP % Discount, Any Display`
- `ARP % Discount, Any Feature`
- `ARP % Discount, Display Only`
- `ARP % Discount, Feature & Display`
- `ARP % Discount, Feature Only`
- `ARP % Discount, TPR Only`
- `ARP % Discount, SPK`
- `Base ARP, ...`
- `ARP, ...`

Use for:

- price-driven switching controls
- promotion context
- pack value comparison
- scenario forecasting assumptions

Derived features:

- `max_discount_depth`
- `discount_depth_any_feature`
- `discount_depth_tpr`
- `promo_price_gap_vs_comparison`
- `base_price_gap_vs_comparison`
- `price_per_eq_unit`
- `price_per_pack_unit`

Recommendation:

Carry the promo-type discount and ARP fields into an analyst/model layer. The UI should still show only a small price set: ARP, Base ARP, and discount summary.

### 7. Revenue productivity

Already in sample:

- `Dollars SPM`
- `Average Weekly Dollars SPM`
- `Dollars SPM Per Item`
- `Dollars SPP`
- `Dollars/TDP`

Use for:

- revenue tradeoff detection
- premiumization versus unit loss
- pack mix value effects
- forecasted commercial impact

Derived features:

- `dollars_per_tdp_pct_chg`
- `base_dollars_per_tdp`
- `revenue_productivity_delta_diff`
- `dollar_velocity_yoy_pct`

Recommendation:

Use revenue productivity in the model and explanation layer, especially for multipack trade-up analysis.

## Important Clarification: Store-Selling Measures

Some planning docs mention:

- `# Stores Selling`
- `% of Stores Selling`
- `Average Weekly Units Per Store Selling Per Item`

The current `All_items_extract_100.csv` sample does not include true `# Stores Selling`.

It does include:

- `Average Items Selling`
- `Units SPM`
- `Average Weekly Units SPM`
- `Units SPM Per Item`
- `Units SPP`
- `Units/TDP`

Recommendation:

- If the full 51GB SPINS file includes true store-selling fields, ingest them.
- If it does not, do not label any metric as true units per store.
- Use `Units/TDP`, `Units SPM`, `Average Weekly Units SPM`, and `Units SPM Per Item` as reach-adjusted productivity proxies.
- In the polished UI, label them carefully as productivity or reach-adjusted velocity, not literal store productivity.

## Recommended Query 0 Expansion

Query 0 should carry these additional field groups into the filtered/enriched layer:

### Demand and year-ago

- `EQ Units`
- `Dollars, Yago`
- `Units, Yago`
- `EQ Units, Yago`
- `Base Dollars, Yago`
- `Base Units, Yago`
- `Incr Dollars, Yago`
- `Incr Units, Yago`

### Distribution and coverage

- `Avg % ACV`
- `Avg % ACV, Yago`
- `Max % ACV, Yago`
- `TDP, Yago`
- `Average Weekly TDP`
- `Average Weekly TDP, Yago`
- `Average Items Selling`
- `Average Items Selling, Yago`
- `Weight Weeks`
- `Weight Weeks, Yago`
- promo/non-promo ACV, TDP, and weight-week fields

### Productivity

- `Dollars SPM`
- `Dollars SPM, Yago`
- `Units SPM`
- `Units SPM, Yago`
- `Average Weekly Dollars SPM`
- `Average Weekly Units SPM`
- `Dollars SPM Per Item`
- `Units SPM Per Item`
- `Dollars SPP`
- `Units SPP`
- `Dollars/TDP`
- `Units/TDP`

### Promo decomposition

- `Dollars, Promo`
- `Dollars, Non-Promo`
- `Dollars, % Promo`
- `Units, Promo`
- `Units, Non-Promo`
- `Units, % Promo`
- `Promo Weeks`
- `Incr Dollars`
- `Incr Units`

### Promo lift and discount

- dollar lift fields by TPR, feature, display, feature + display, SPK
- unit lift fields by TPR, feature, display, feature + display, SPK
- ARP discount fields by TPR, feature, display, feature + display, SPK
- ARP and Base ARP fields by promo type

## Recommended New Derived Feature Families

### 1. Seasonality and trend features

Use:

- year-ago measures
- week-of-year
- rolling 4-week and 13-week averages

Features:

- `units_yoy_pct`
- `base_units_yoy_pct`
- `tdp_yoy_pct`
- `velocity_yoy_pct`
- `category_units_yoy_pct`
- `subcategory_units_yoy_pct`

Why:

This prevents the model from mistaking normal seasonal softness for cannibalization.

### 2. Distribution quality features

Use:

- `TDP`
- `Avg % ACV`
- `Max % ACV`
- `Average Items Selling`
- `Weight Weeks`

Features:

- `distribution_expansion_flag`
- `acv_expansion_flag`
- `tdp_vs_acv_gap`
- `coverage_quality_score`
- `evidence_weight`

Why:

This improves confidence scoring and reduces false positives.

### 3. Promo mechanics features

Use:

- promo/non-promo units and dollars
- lift fields
- discount fields
- promo and non-promo TDP / ACV

Features:

- `promo_intensity_score`
- `max_discount_depth`
- `display_or_feature_flag`
- `promo_lift_response`
- `focal_promo_advantage`
- `donor_promo_defense`

Why:

Promo can create apparent cannibalization even when product preference did not change.

### 4. Pack-normalized features

Use:

- pack count
- EQ units
- ARP
- Base ARP

Features:

- `eq_units_per_tdp`
- `price_per_eq_unit`
- `price_per_pack_unit`
- `pack_value_gap`
- `eq_units_delta_diff`

Why:

Pack-ladder cannibalization needs pack-normalized demand, not only raw units.

### 5. Revenue and premiumization features

Use:

- Dollars
- Base Dollars
- Dollars/TDP
- Dollars SPM
- ARP

Features:

- `base_dollars_pct_chg`
- `dollars_per_tdp_pct_chg`
- `revenue_productivity_delta_diff`
- `unit_loss_but_dollar_gain_flag`

Why:

A pack can cannibalize units while still improving portfolio dollars.

## ML Plan Check

The ML plan remains sound if these amendments are made.

### Keep

- Druid-first aggregation
- broad BUILT plus competitor training universe
- pairwise comparison pool
- relationship distance
- donor ranker
- event detector
- win-count layer
- forecast next move layer
- SHAP / explanation
- confidence thresholds

### Fix or expand

1. Rename `built_enriched_weekly` to `weekly_enriched_items`.
   - It should contain BUILT plus eligible competitors.

2. Do not filter competitors out in Query 1.
   - Filter to BUILT focal items at scoring/UI time, not enrichment time.

3. Expand Query 0 and Query 1 to preserve the SPINS field groups listed above.

4. Replace pack-ladder-only Query 4 references with `comparison_pool_weekly`.
   - Keep pack-specific fields nullable for non-pack comparisons.

5. Split features into:
   - retrospective measurement features
   - predictive scenario features
   - leakage-safe forecast features

6. Add year-ago, promo-type, ACV, EQ, and revenue-productivity features to the model.

7. Treat `Units/TDP`, `Units SPM`, and `Average Weekly Units SPM` as productivity proxies unless true store-selling fields exist in the full file.

## What This Means Practically

Before requesting more client data, the Druid build should make full use of SPINS by producing:

1. `weekly_enriched_items`
2. `weekly_spins_derived_features`
3. `comparison_pool_weekly`
4. `event_windows`
5. `promo_price_control_features`
6. `seasonality_trend_features`
7. `weekly_win_features`
8. `ml_feature_table`
9. `scenario_forecast_outputs`

## Bottom Line

We should not ask BUILT for more data until we have fully exploited the SPINS file.

The current plan has the right architecture, but the real 95M-row implementation should widen the SPINS feature capture. SPINS already contains enough demand, distribution, price, promo, productivity, year-ago, launch, and product-attribute fields to support a strong first version of Mo.

Client data should be reserved for things SPINS cannot know:

- internal product role
- intended launch / discontinuation context
- actual authorization
- stockouts / inventory availability
- margin
