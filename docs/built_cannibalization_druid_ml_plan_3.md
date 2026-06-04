# BUILT Cannibalization Tool — Druid Query Plan & ML Model Design
## Version 3 — updated for expanded SPINS extract fields

### Changelog from v1

| Area | Change |
|---|---|
| Metric naming | `Units/TDP` replaced everywhere by `avg_weekly_units_spm` (Units SPM). `Units/TDP` is explicitly excluded from the UI per the metric shortlist. |
| Scored output schema | `scored_cannibalization` gains `incremental_share` score, `comparison_type` label, `relationship_distance`, `p_value`, `z_score_donor`. Context bar requires all five dimensions at render time. |
| Cross-flavor screen | Dist 3 (SAME_FLAVOR_SAME_BRAND) and dist 4 (SAME_FLAVOR_CROSS_BRAND) are now first-class UI screens, not just drilldowns. A geography × SKU heatmap is required. Query 2 pre-builds both; a new heatmap aggregation query (Query 2c) is added. |
| Competitive screen | Tier metadata (Tier 1 / Tier 2 / Tier 3) must be queryable — added to the item catalog reference table, not hard-coded in the UI. |
| Ramp monitor | Confidence ladder is now precisely defined: suppressed weeks 1–6, LOW weeks 7–8, MEDIUM+ week 9 onward. Ramp trend classification (RAMPING / STABLE / DECLINING) uses `distribution_trend` from Query 9. |
| Pool health | Win/loss matrix baseline is explicitly 8-week rolling average (not arbitrary). `0` cell = fewer than 8 prior weeks of data. |
| Pre/post screen | ARP pre/post and promo weeks pre/post are now first-class rows in the UI table, requiring `pre_avg_arp`, `post_avg_arp`, `pre_promo_weeks`, `post_promo_weeks` in `built_prepost_features`. |
| SKU summary | Second score bar added: `incremental_share` (complement of `cannibal_prob`, displayed separately). Both bars populate from `scored_cannibalization`. |
| Provenance panel | `p_value` and `z_score` are now surface-level fields in the Explanation screen, not buried in metadata. Both must be in `scored_cannibalization`. |
| Event queue | New event type: `NEW_PACK_SIZE` — surfaces as an amber alert banner on the Priority Events landing page, distinct from the five existing event types. Priority Events cards now carry `relationship_distance` badge. |
| Filter dimensions | Modal step 3 exposes four filter axes: channel, geography, window (4w/13w/26w/YTD), confidence floor (High only / Medium+ / All). Scoring pipeline must support all four window sizes. |
| Expanded SPINS extract | `All_items_extract_41926-h100.csv` adds direct `Channel/Outlet`, `Geography Level`, `Retail Account`, and `Retail Account Level` fields, so Query 1 no longer parses channel/market/retailer out of `Geography`. It also adds store-selling, promo lift, and YAGO fields that improve confound control. |

---

## Section 1. Data Architecture Overview

### Source table in Druid

```
datasource: spins_weekly_pos
grain:       UPC × Retail Account × Geography × __time (week-ending date)
volume:      ~95M rows, ~50GB
key dims:    UPC, Channel/Outlet, Geography Level, Retail Account,
             Retail Account Level, Geography, __time
key facts:   Units, Base_Units, Dollars, Base_Dollars, TDP, Max_ACV,
             Avg_Weekly_Units_SPM, Avg_Weekly_Units_Per_Store_Selling_Per_Item,
             Units_SPM, ARP, Base_ARP, Promo_Weeks, Incr_Units,
             First_Week_Selling, Number_of_Weeks_Selling, Pack_Count, FLAVOR,
             #_of_Stores, #_of_Stores_Selling, %_of_Stores_Selling,
             promo lift and YAGO companion metrics
```

### Expanded extract field usage

The partial sample `All_items_extract_41926-h100.csv` shows SPINS can now provide
fields that were previously inferred or unavailable. Use them as follows:

The sample has only 100 rows, so it should be used for schema and field-purpose
decisions, not for final coverage assumptions. The production ingestion should
be schema-first and scale to the later multi-GB extracts without hard-coding the
sample's retail accounts, channels, or geographies.

| Field family | Source columns | Best use in the cannibalization tool |
|---|---|---|
| Retail context | `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography` | Direct UI filters, scope bars, heatmap pivots, and model grouping keys. No channel/market/retailer parser is required. |
| Product hierarchy | `Department`, `Category`, `Subcategory`, `Brand`, `UPC`, `Description`, `PACK COUNT`, `FLAVOR` | Category filtering, parent-brand normalization, pack ladder construction, SPINS `FLAVOR` grouping. |
| Nutrition/product attributes | `NFP - PROTEIN`, `NFP RANGES - PROTEIN VALUE`, `NFP - SUGARS`, `NFP - CALORIES`, `STORAGE`, `UNIT OF MEASURE` | Competitor similarity and substitution priors. Useful for same-FLAVOR competitive matching and future analog launch selection. |
| Distribution | `Avg % ACV`, `Max % ACV`, `TDP`, `Average Weekly TDP`, `# of Stores`, `# of Stores Selling`, `% of Stores Selling` | Separate reach expansion from true demand transfer. Store-selling fields are preferred for retail execution diagnostics. |
| Velocity | `Average Weekly Units SPM`, `Units SPM Per Item`, `Average Weekly Units Per Store Selling Per Item`, `Average Weekly Units per Store Selling` | Primary demand-pull signals. Prefer `Average Weekly Units Per Store Selling Per Item` for the UI when available; keep `Average Weekly Units SPM` as a stable normalized model feature. |
| Price and base price | `ARP`, `Base ARP`, `ARP, Promo`, `ARP, Non-Promo`, `ARP % Discount, Any Promo` plus display/feature/TPR/SPK variants | Price confound control and promo-depth diagnostics in the Provenance panel. |
| Promo mechanics | `Dollars/Units Promo`, `Dollars/Units Non-Promo`, `% Promo`, `Promo Weeks`, promo ACV/TDP/Weight Weeks, promo lift fields | Distinguish cannibalization from promo-driven focal lift or donor defense activity. |
| Baselines | `Base Dollars`, `Base Units`, `Incr Dollars`, `Incr Units` | Core pre/post and incremental-share calculations. |
| YAGO companions | Any `, Yago` columns | Seasonality and retailer-specific baseline controls. Do not show by default in the UI, but use in feature engineering and QA. |

Fields still intentionally avoided in the final UX: `Units/TDP` and `Dollars/TDP`.
They may be retained for QA, but the model and UI should rely on store/SPM
velocity fields because those map better to the user question, "is each selling
store actually moving more units?"

### Reference tables (load as Druid lookups or join-time CSVs)

| Table | Source | Key | Use |
|---|---|---|---|
| `flavor_mapping` | built_specific_flavor_mapping.csv | UPC | Adds `parent_brand`, `brand_line`, `spins_flavor`, `specific_flavor_normalized`, `pack_count`, `size_oz`; validates which specific flavors belong under each SPINS `FLAVOR`. The CSV column currently named `brand` is treated as `brand_line`; the CSV column currently named `flavor_family` contains the SPINS `FLAVOR` value and is aliased to `spins_flavor`. |
| `item_catalog` | Item_list_BUILT_and_Category.xlsx | UPC | Adds `Department`, `Category`, `Subcategory`, `Positioning_Group`, `Product_Type`, `Functional_Ingredient`, `Health_Focus`, `Size_Positioning`, **`competitor_tier`** |

**`competitor_tier` remains a small external classification.** Added to
`item_catalog` as a static column
for non-BUILT brands. Values: `TIER_1_DIRECT` (RXBAR, BAREBELLS, QUEST, PERFECT BAR,
THINK!, ALOHA, NO COW, FULFIL, PURE PROTEIN, 1ST PHORM, SIMPLYPROTEIN, NUGO NUTRITION),
`TIER_2_BFY_ADJACENT` (KIND, LARABAR, CLIF BAR, CLIF BUILDERS, GOMACRO, BOBOS, PROBAR,
MEZCLA, TOSI, ORGAIN), `TIER_3_MAINSTREAM` (NATURE VALLEY, QUAKER CHEWY, NUTRI-GRAIN,
SPECIAL K, SUNBELT, KODIAK CAKES, NATURES BAKERY), `NULL` for BUILT brand lines.
This column surfaces in the Competitive screen's tier section labels and controls
default display order in Query 2b results (Tier 1 shown first).

**Critical join key:** `UPC` (present in all three). The flavor mapping has 91 BUILT
SKUs with pack ladder data already clean.

**Flavor hierarchy:** The canonical hierarchy is **Parent Brand > SPINS `FLAVOR` > Specific Flavor**.
`spins_flavor` is sourced strictly from the SPINS `FLAVOR` value: directly from
the Druid source table during production scoring, and from
`built_specific_flavor_mapping.csv` for mockup/reference validation. It is not
inferred from specific flavor text. `specific_flavor_normalized` is the child
value used to compare individual flavors and pack ladders within each SPINS
`FLAVOR` group.

For BUILT, `parent_brand = BUILT` spans `brand_line` values such as `BUILT PUFF`,
`BUILT BAR`, and `BUILT SOUR PUFF`. Brand line remains useful metadata and a
model feature, but it is not the hierarchy level used to decide whether a
specific flavor belongs inside a parent brand's SPINS `FLAVOR` group.

The UI examples must be validated against `built_specific_flavor_mapping.csv`.
For example, the current mapping places only these BUILT specific flavors under
`CHOCOLATE MINT`: `Mint Brownie`, `Mint Chip`, and `Grasshopper Cookie`.
`Brownie Batter` is mapped to `BROWNIE`, and `Double Chocolate` is mapped to
`CHOCOLATE`, so neither should appear inside a `CHOCOLATE MINT` comparison pool.

---

## Section 2. Comparison Pool Design — Fully Flexible, User-Driven

The tool is built around a **pool-based, parameterized** architecture. No
comparison is hard-coded. A user can set any SKU as the focal item and compare
it against any combination of:

- other pack sizes of the same specific flavor (pack ladder)
- other specific flavors within the same parent brand and SPINS `FLAVOR` (cross-flavor, same parent brand)
- competitor items with the same specific flavor profile (cross-brand same specific flavor)
- competitor items in the same SPINS FLAVOR (cross-brand same FLAVOR)
- any arbitrary competitor brand or SKU (full competitive)

The comparison pool query (Query 2) builds all valid pairs dynamically from
the data, assigns a `relationship_distance` to each, and lets the UI filter
to whatever scope the user needs. The ML model trains on all pair types
simultaneously and uses `relationship_distance` as a feature — so it learns
that a pack-ladder pair has a higher prior cannibalization probability than
a cross-FLAVOR competitive pair without needing separate models per mode.

### 2.1 The five comparison modes

| Mode | User question | Focal set | Comparison set | Distance |
|---|---|---|---|---|
| **Pack ladder** | "Is my 4pk cannibalizing my 1ct Brownie Batter?" | One specific flavor, one pack size | All other pack sizes of the same specific flavor, same parent brand | 1 |
| **Cross-brand same specific flavor** | "Is a competitor's Coconut flavor pulling from BUILT Coconut?" | One BUILT specific flavor | Same `specific_flavor_normalized`, different parent brand | 2 |
| **Cross-flavor same parent brand** | "Is Coconut pulling from Brownie Batter within BUILT?" | One BUILT specific flavor | Any other BUILT specific flavor under the same parent brand, same or different SPINS `FLAVOR` | 3 or 5 |
| **Cross-flavor cross-brand same SPINS FLAVOR** | "Is RXBAR Chocolate Chip competing with BUILT Mint Chip?" | One or more BUILT SKUs | Same `spins_flavor`, different parent brand | 4 |
| **Full competitive** | "How is BUILT performing against BAREBELLS or QUEST overall?" | One or more BUILT SKUs | Any competitor brand(s) or specific SKUs | 6 |

All five modes are supported by the same `comparison_pool_weekly` table.
Mode selection in the UI is a filter operation, not a different query.

### 2.2 Comparison type taxonomy

Every (focal_upc, candidate_upc, geography, week_end) pair is assigned one
of six `comparison_type` values and a corresponding `relationship_distance`.

| comparison_type | distance | Definition |
|---|---|---|
| `SAME_SPECIFIC_FLAVOR_SAME_BRAND_PACK_LADDER` | 1 | Same parent brand + same `specific_flavor_normalized` + different `pack_count`. Tightest substitution. |
| `SAME_SPECIFIC_FLAVOR_CROSS_BRAND` | 2 | Same `specific_flavor_normalized`, different parent brand. |
| `SAME_FLAVOR_SAME_BRAND` | 3 | Same parent brand + same `spins_flavor`, different `specific_flavor_normalized`. Cross-flavor within the parent brand portfolio. |
| `SAME_FLAVOR_CROSS_BRAND` | 4 | Same `spins_flavor`, different parent brand. Competitive substitution within a SPINS FLAVOR. |
| `CROSS_FLAVOR_SAME_BRAND` | 5 | Different `spins_flavor`, same parent brand. Widest intra-brand comparison. |
| `CROSS_FLAVOR_CROSS_BRAND` | 6 | Different `spins_flavor`, different parent brand. Broadest competitive view. Built on-demand via Query 2b. |

### 2.3 How relationship_distance drives the ML model

`relationship_distance` is a first-class ML feature, not just a filter.
It encodes the prior substitution probability structurally:

- Distance 1 (pack ladder): the most direct substitution possible. The model needs minimal additional evidence to score this as cannibalizing.
- Distance 2 (cross-brand same specific flavor): strong substitution signal, modulated by brand loyalty and price-per-unit differences.
- Distance 3–4 (cross-flavor or cross-brand same SPINS `FLAVOR`): weaker structural prior; the model relies more heavily on metric signals than on the relationship itself.
- Distance 5–6: the model's prior is essentially neutral — metric evidence is the only signal that matters.

This means a single trained model handles all five modes correctly without
mode-specific thresholds or separate model versions.

### 2.4 User-selectable focal and comparison sets in the UI

The UI exposes a three-step modal (click the focal pill in the topbar):

**Step 1 — Focal item selection**
The user selects a focal SKU from a SPINS `FLAVOR` accordion with search.
Accordions are grouped by SPINS `FLAVOR` values carried as `spins_flavor`
(CHOCOLATE MINT, CARAMEL, COCONUT, etc.). Each SKU row shows its current
cannibalization badge.
The initially selected SKU is the one already loaded in the tool.

**Step 2 — Comparison set selection**
Five scope options presented as radio buttons, each showing the distance
value and `comparison_type` it activates:

```
[ Pack sizes of this flavor only ]      → distance = 1
[ Same specific flavor, any brand ]      → distance ≤ 2
[ Same SPINS FLAVOR, BUILT only ]       → distance = 3
[ Same SPINS FLAVOR, all brands ]       → distance ≤ 4
[ Specific competitor brand(s) ]        → Query 2b on-demand (distance 6)
```

Default view on first open: **Pack sizes of this flavor only** (distance = 1).
The user explicitly widens the scope rather than being shown everything at once.

**Step 3 — Scope and filters**
Six filter dimensions, each rendered as a dropdown. `Channel/Outlet`,
`Retail Account`, and `Geography Level` now come directly from SPINS rather
than from parsing `Geography`.

| Filter | Options | Default |
|---|---|---|
| Channel / Outlet | All / Conventional\|Food / Conventional\|Multi Outlet / Conventional\|Convenience / Conventional\|Mass Merch / other SPINS values | All |
| Retail Account | All / Kroger / Publix / Target / Walmart / CVS / other SPINS accounts | All |
| Geography Level | All / CRMA / RMA / other SPINS levels | All |
| Geography | Any SPINS geography value for the selected account and level | All |
| Window | 4 weeks vs prior 4 / 13 weeks vs prior 13 / 26 weeks vs prior 26 / YTD vs prior YTD | 13 vs 13 |
| Confidence floor | High only / Medium + High / All (includes Low) | Medium + High |

**Window implications for the scoring pipeline:** All four window sizes must be
pre-computed in `built_prepost_features`. The production version of Query 3 runs
four parallel CASE WHEN aggregations (4w, 13w, 26w, and YTD) in a single pass,
writing `window_type` as a grouping column. The UI filters to the selected window
at render time. YTD is anchored to January 1 of the current year regardless of
`first_week_selling`.

**Context bar** (rendered below the topbar, above main content) displays the
current selections at all times:

```
Focal: [sku_name] · Pool: [scope_label (dist N)] · Channel/Outlet: [channel] · Retail Account: [account] · Window: [window] · Geography: [geo]
```

All five values must be queryable from `scored_cannibalization` at render time
without a secondary lookup. They are stored as denormalized columns:
`focal_description`, `comparison_scope_label`, `channel_outlet`, `retail_account`,
`geography_level`, `window_type`, `geography_display`.

### 2.5 Known BUILT pack ladder structure (reference documentation)

The flavor mapping confirms the following multi-pack ladders. These are
documented as reference — the pipeline discovers them dynamically from the
data. No pair needs to be hard-coded.

| Brand | SPINS `FLAVOR` | Specific Flavor | Pack Sizes Present |
|---|---|---|---|
| BUILT PUFF | BROWNIE | Brownie Batter | 1ct, 4pk, 8pk, 12pk |
| BUILT PUFF | COCONUT | Coconut | 1ct, 4pk, 8pk, 12pk |
| BUILT BAR | COCONUT | Coconut | 1ct, 12pk |
| BUILT PUFF | COOKIES AND CREAM | Cookies N Cream | 1ct, 4pk, 12pk |
| BUILT PUFF | COOKIE DOUGH | Cookie Dough | 1ct, 4pk, 12pk |
| BUILT PUFF | CARAMEL | Salted Caramel | 4pk, 12pk |
| BUILT BAR | CARAMEL | Salted Caramel | 1ct, 12pk |
| BUILT PUFF | CHOCOLATE MINT | Mint Chip | 1ct, 4pk, 12pk |
| BUILT PUFF | STRAWBERRY | Strawberries N Cream | 1ct, 4pk, 12pk |
| BUILT BAR | CHOCOLATE | Double Chocolate | 4pk, 12pk, 16pk |
| BUILT BAR | COOKIES AND CREAM | Cookies and Cream | 1ct, 4pk |
| BUILT BAR | COCONUT | Coconut Almond | 1ct, 18pk |
| BUILT PUFF | BANANA | Banana Cream Pie | 1ct, 12pk |
| BUILT PUFF | CHOCOLATE NUT | Chocolatey Hazelnut | 1ct, 12pk |
| BUILT PUFF | OTHER | Churro | 1ct, 12pk |
| Candy Cane Brownie | BUILT PUFF | 1ct, 12pk |
| Lemon Meringue Pie | BUILT PUFF | 1ct, 4pk |

### 2.6 Competitive universe in the category

From the category extract, the full subcategory contains the competitive brand
universe available for comparison via Query 2b. The `competitor_tier` column in
`item_catalog` classifies them — see Section 1 for the tier lists.

Tier classification is metadata only, not a filter. A user can always select
any competitor brand regardless of tier. The tier classification surfaces in
the Competitive screen as visual section labels and controls default sort order
in Query 2b results.

---

## Section 3. Druid Query Plan

The 95M raw rows must never be passed to the ML pipeline directly.
Druid aggregates to feature vectors first. There are **twelve sequential queries**
(up from ten in v1 — Query 2c and Query 2d are new).

---

### Query 0 — Category extract normalization (run once, cache result)

**Purpose:** Normalize the raw SPINS extract into stable snake_case columns and
narrow to BUILT rows plus same-subcategory competitor rows needed for context.
This step preserves the direct retail/geography fields from the expanded extract.

```sql
SELECT
  TIME_PARSE("Time Period End Date")   AS week_end,
  "Channel/Outlet"                     AS channel_outlet,
  "Geography Level"                    AS geography_level,
  "Retail Account"                     AS retail_account,
  "Retail Account Level"               AS retail_account_level,
  "Geography"                          AS geography_raw,
  "Product Universe"                   AS product_universe,
  "Product Level"                      AS product_level,
  "Department"                         AS department,
  "Category"                           AS category,
  "Subcategory"                        AS subcategory,
  "UPC",
  "Description",
  "Brand"                             AS source_brand,
  "PACK COUNT"                     AS pack_count,
  "FLAVOR"                         AS spins_flavor,

  -- Nutrition and product attributes for competitor similarity
  "NFP - PROTEIN"                   AS nfp_protein,
  "NFP RANGES - PROTEIN VALUE"      AS nfp_protein_range,
  "NFP - SUGARS"                    AS nfp_sugars,
  "NFP - CALORIES"                  AS nfp_calories,
  "STORAGE"                         AS storage,
  "UNIT OF MEASURE"                 AS unit_of_measure,

  -- Demand and distribution
  "Units",
  "Units, Yago"                     AS units_yago,
  "EQ Units"                        AS eq_units,
  "Base Units"                     AS base_units,
  "Base Units, Yago"                AS base_units_yago,
  "Dollars",
  "Dollars, Yago"                   AS dollars_yago,
  "Base Dollars"                   AS base_dollars,
  "Base Dollars, Yago"              AS base_dollars_yago,
  "TDP",
  "TDP, Yago"                       AS tdp_yago,
  "Average Weekly TDP"              AS avg_weekly_tdp,
  "Max % ACV"                      AS max_acv,
  "Avg % ACV"                       AS avg_acv,
  "# of Stores"                     AS store_count,
  "# of Stores Selling"             AS stores_selling,
  "% of Stores Selling"             AS pct_stores_selling,
  "Average Weekly Units SPM"       AS avg_weekly_units_spm,
  "Average Weekly Units Per Store Selling Per Item"
                                    AS avg_weekly_units_per_store_selling_per_item,
  "Units SPM Per Item"              AS units_spm_per_item,
  "ARP",
  "ARP, Yago"                       AS arp_yago,
  "Base ARP"                       AS base_arp,
  "ARP % Discount, Any Promo"      AS arp_pct_discount_any_promo,
  "ARP % Discount, TPR Only"        AS arp_pct_discount_tpr_only,
  "Units, Promo"                   AS units_promo,
  "Units, Non-Promo"               AS units_non_promo,
  "Units, % Promo"                  AS units_pct_promo,
  "TDP, Any Promo"                  AS tdp_any_promo,
  "TDP, Non-Promo"                  AS tdp_non_promo,
  "Promo Weeks"                    AS promo_weeks,
  "Incr Units"                     AS incr_units,
  "Incr Dollars"                   AS incr_dollars,
  "Units ,% Lift, TPR"              AS units_lift_tpr,
  "Units ,% Lift, Any Display"      AS units_lift_any_display,
  "Units ,% Lift, Any Feature"      AS units_lift_any_feature,
  "First Week Selling"             AS first_week_selling,
  "Number of Weeks Selling"        AS number_of_weeks_selling
FROM spins_weekly_pos
WHERE
  "Brand" IN ('BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF', 'BUILT')
  OR "Subcategory" = 'WELLNESS & NUTRITION BARS'
```

**Output table:** `built_filtered_weekly`

---

### Query 1 — Enriched weekly base table

**Purpose:** Join filtered weekly data against the flavor mapping to attach
`parent_brand`, `brand_line`, source SPINS `FLAVOR` as `spins_flavor`, plus
`specific_flavor_normalized`, clean `pack_count`, and `size_oz`.
No geography parser is required. `channel_outlet`, `geography_level`,
`retail_account`, `retail_account_level`, and `geography_raw` are already source
columns in the expanded extract. For backward compatibility with later queries,
`channel` is an alias of `channel_outlet`, and `geography_display` is an alias
of `geography_raw`.

**Simplification from v2:** delete the old `geo_type`, `panel_scope`,
`parent_group`, `banner_name`, and `market_region` parser logic. Military rows
can be excluded directly with `channel_outlet != 'CONVENTIONAL|MILITARY'` or by
filtering out `retail_account = 'DECA'`.

**Output table:** `built_enriched_weekly`

**Note on `Units/TDP`:** This column is **not computed** in Query 1 or any
downstream query. The UI metric shortlist explicitly flags `Units/TDP` as
"Avoid in Final UX" because users confuse it with per-store productivity.
Velocity signals use `avg_weekly_units_spm` for stable normalization and
`avg_weekly_units_per_store_selling_per_item` when the user needs the cleanest
read on stores that actually sold the item.

---

### Query 2 — Universal comparison pool (dist 1–5, pre-built)

**Purpose:** Build every valid (focal_upc, candidate_upc) pair across all
comparison modes in a single self-join pass. `comparison_type` and
`relationship_distance` columns let the UI and ML models filter to the right
pool without running separate queries per mode.

**v2 change:** `price_per_unit_ratio` calculation now uses `avg_weekly_units_spm`
instead of the removed velocity-per-TDP derived metric. The candidate metrics
block now includes `avg_weekly_units_spm` as `candidate_velocity_spm` (renamed
from `candidate_velocity` to make the metric identity unambiguous).

```sql
SELECT
  f.week_end,
  f.geography_raw,
  f.geography_display,
  f.geography_level,
  f.channel_outlet,
  f.channel,
  f.retail_account,
  f.retail_account_level,

  -- Focal item
  f.upc                               AS focal_upc,
  f.parent_brand                      AS focal_brand,
  f.brand_line                        AS focal_brand_line,
  f.description                       AS focal_description,
  f.specific_flavor_normalized        AS focal_flavor,
  f.spins_flavor                     AS focal_spins_flavor,
  f.pack_count                        AS focal_pack_count,
  f.size_oz                           AS focal_size_oz,

  -- Candidate item
  c.upc                               AS candidate_upc,
  c.parent_brand                      AS candidate_brand,
  c.brand_line                        AS candidate_brand_line,
  c.description                       AS candidate_description,
  c.specific_flavor_normalized        AS candidate_flavor,
  c.spins_flavor                     AS candidate_spins_flavor,
  c.pack_count                        AS candidate_pack_count,
  c.size_oz                           AS candidate_size_oz,

  -- Relationship classification
  CASE
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand = c.parent_brand AND f.pack_count != c.pack_count
      THEN 'SAME_SPECIFIC_FLAVOR_SAME_BRAND_PACK_LADDER'
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand != c.parent_brand
      THEN 'SAME_SPECIFIC_FLAVOR_CROSS_BRAND'
    WHEN f.spins_flavor = c.spins_flavor AND f.parent_brand = c.parent_brand
     AND f.specific_flavor_normalized != c.specific_flavor_normalized
      THEN 'SAME_FLAVOR_SAME_BRAND'
    WHEN f.spins_flavor = c.spins_flavor AND f.parent_brand != c.parent_brand
      THEN 'SAME_FLAVOR_CROSS_BRAND'
    WHEN f.spins_flavor != c.spins_flavor AND f.parent_brand = c.parent_brand
      THEN 'CROSS_FLAVOR_SAME_BRAND'
    ELSE 'CROSS_FLAVOR_CROSS_BRAND'
  END AS comparison_type,

  -- Relationship distance
  CASE
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand = c.parent_brand AND f.pack_count != c.pack_count THEN 1
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.parent_brand != c.parent_brand THEN 2
    WHEN f.spins_flavor = c.spins_flavor AND f.parent_brand = c.parent_brand
     AND f.specific_flavor_normalized != c.specific_flavor_normalized THEN 3
    WHEN f.spins_flavor = c.spins_flavor AND f.parent_brand != c.parent_brand THEN 4
    WHEN f.spins_flavor != c.spins_flavor AND f.parent_brand = c.parent_brand THEN 5
    ELSE 6
  END AS relationship_distance,

  -- Pack distance (pack ladder pairs only; NULL otherwise)
  CASE
    WHEN f.parent_brand = c.parent_brand
     AND f.specific_flavor_normalized = c.specific_flavor_normalized
      THEN ABS(f.pack_count - c.pack_count)
    ELSE NULL
  END AS pack_distance,

  -- Price-per-unit ratio (controls for pack size value differences)
  CASE
    WHEN c.pack_count > 0 AND f.pack_count > 0
      THEN (f.arp / NULLIF(f.pack_count, 0))
         / NULLIF((c.arp / NULLIF(c.pack_count, 0)), 0)
    ELSE NULL
  END AS price_per_unit_ratio,

  -- Candidate weekly metrics
  c.base_units                        AS candidate_base_units,
  c.units                             AS candidate_units,
  c.tdp                               AS candidate_tdp,
  c.avg_weekly_units_spm              AS candidate_velocity_spm,   -- renamed from v1
  c.avg_weekly_units_per_store_selling_per_item
                                      AS candidate_velocity_store_selling,
  c.arp                               AS candidate_arp,
  c.store_count                       AS candidate_store_count,
  c.stores_selling                    AS candidate_stores_selling,
  c.pct_stores_selling                AS candidate_pct_stores_selling,
  c.tdp_any_promo                     AS candidate_tdp_any_promo,
  c.tdp_non_promo                     AS candidate_tdp_non_promo,
  c.promo_weeks                       AS candidate_promo_weeks,
  c.units_pct_promo                   AS candidate_units_pct_promo,
  c.arp_pct_discount_any_promo        AS candidate_arp_discount_any_promo,
  c.units_lift_tpr                    AS candidate_units_lift_tpr,
  c.units_lift_any_display            AS candidate_units_lift_any_display,
  c.units_lift_any_feature            AS candidate_units_lift_any_feature,
  c.first_week_selling                AS candidate_first_week_selling,
  c.incr_units                        AS candidate_incr_units,
  -- competitor_tier from item_catalog join (NULL for BUILT SKUs)
  ic.competitor_tier                  AS candidate_competitor_tier

FROM built_enriched_weekly f
JOIN built_enriched_weekly c
  ON  f.week_end = c.week_end
  AND f.geography_raw = c.geography_raw
  AND f.retail_account = c.retail_account
  AND f.channel_outlet = c.channel_outlet
  AND f.upc != c.upc
  AND (
    f.specific_flavor_normalized = c.specific_flavor_normalized
    OR f.spins_flavor = c.spins_flavor
    OR (f.parent_brand = c.parent_brand
        AND f.parent_brand = 'BUILT')
  )
LEFT JOIN item_catalog ic ON c.upc = ic.upc
WHERE
  (f.parent_brand = 'BUILT'
   OR c.parent_brand = 'BUILT')
  AND f.channel_outlet != 'CONVENTIONAL|MILITARY'
  AND f.retail_account != 'DECA'
```

**Output table:** `comparison_pool_weekly`
**Key columns added in v3:** direct retail context, store-selling velocity,
promo lift/depth controls, `candidate_competitor_tier`

---

### Query 2b — On-demand competitive pool (dist 6, user-triggered)

**Purpose:** When a user explicitly selects a competitor brand for comparison,
this query builds type-6 cross-FLAVOR competitive pairs on the fly. It runs
against `built_enriched_weekly` at query time. Results are sorted by
`competitor_tier` ascending (Tier 1 surfaces first) so the Competitive screen
renders the most actionable comparisons at the top without user resorting.

```sql
SELECT
  f.week_end,
  f.geography_raw,
  f.geography_level,
  f.channel_outlet,
  f.channel,
  f.retail_account,
  f.upc                               AS focal_upc,
  f.parent_brand                      AS focal_brand,
  f.brand_line                        AS focal_brand_line,
  f.description                       AS focal_description,
  f.specific_flavor_normalized        AS focal_flavor,
  f.spins_flavor                     AS focal_spins_flavor,
  f.pack_count                        AS focal_pack_count,
  f.base_units                        AS focal_base_units,
  f.units                             AS focal_units,
  f.tdp                               AS focal_tdp,
  f.avg_weekly_units_spm              AS focal_velocity_spm,
  f.arp                               AS focal_arp,

  c.upc                               AS competitor_upc,
  c.parent_brand                      AS competitor_brand,
  c.brand_line                        AS competitor_brand_line,
  c.description                       AS competitor_description,
  c.specific_flavor_normalized        AS competitor_flavor,
  c.spins_flavor                     AS competitor_spins_flavor,
  c.pack_count                        AS competitor_pack_count,
  c.base_units                        AS competitor_base_units,
  c.units                             AS competitor_units,
  c.tdp                               AS competitor_tdp,
  c.avg_weekly_units_spm              AS competitor_velocity_spm,
  c.arp                               AS competitor_arp,
  ic.competitor_tier,

  'CROSS_FLAVOR_CROSS_BRAND'          AS comparison_type,
  6                                   AS relationship_distance

FROM built_enriched_weekly f
JOIN built_enriched_weekly c
  ON  f.week_end = c.week_end
  AND f.geography_raw = c.geography_raw
  AND f.retail_account = c.retail_account
  AND f.channel_outlet = c.channel_outlet
LEFT JOIN item_catalog ic ON c.upc = ic.upc

WHERE
  f.upc = :focal_upc
  AND c.parent_brand = :competitor_brand
  AND f.geography_raw IN (
    SELECT DISTINCT geography_raw
    FROM built_enriched_weekly
    WHERE upc = :focal_upc
      AND week_end >= TIMESTAMPADD(WEEK, -:window_weeks, CURRENT_TIMESTAMP)
  )
  AND (:retail_account IS NULL OR f.retail_account = :retail_account)
  AND (:channel_outlet IS NULL OR f.channel_outlet = :channel_outlet)
  AND f.week_end >= TIMESTAMPADD(WEEK, -:window_weeks, CURRENT_TIMESTAMP)

ORDER BY ic.competitor_tier ASC NULLS LAST
```

---

### Query 2c — Cross-flavor heatmap aggregation (new in v2)

**Purpose:** Power the geography × SKU heatmap on the Cross-flavor screen.
The heatmap shows `base_units_pct_chg` for each (SKU, geography) cell, colored
by the standard five-bucket scheme used in the UI:
`strong_neg` (< −10%), `mild_neg` (−10% to −3%), `neutral` (−3% to +3%),
`mild_pos` (+3% to +10%), `strong_pos` (> +10%).

This query aggregates the pre/post features already computed in Query 3 and
reshapes them into the (SKU × geography) pivot structure the heatmap needs.
It runs at render time against `built_prepost_features`, not pre-materialized,
because the focal SPINS `FLAVOR`, retail account, channel/outlet, and geography
list are user-selected.

```sql
-- Query 2c: Cross-flavor heatmap
-- Parameterized: :spins_flavor, :channel_outlet, :retail_account, :window_type
-- Returns one row per (upc, geography) with pct_chg columns

SELECT
  p.upc,
  e.description,
  e.specific_flavor_normalized,
  e.spins_flavor,
  e.pack_count,
  e.parent_brand,
  e.brand_line,
  p.retail_account,
  p.geography_level,
  p.geography,
  p.channel_outlet,
  p.window_type,

  -- Base units % change (pre vs post)
  SAFE_DIVIDE(p.post_base_units - p.pre_base_units,
              NULLIF(p.pre_base_units, 0))          AS base_units_pct_chg,

  -- Velocity % change
  SAFE_DIVIDE(p.post_avg_velocity_spm - p.pre_avg_velocity_spm,
              NULLIF(p.pre_avg_velocity_spm, 0))    AS velocity_spm_pct_chg,

  -- Heatmap bucket (matches UI CSS class names)
  CASE
    WHEN SAFE_DIVIDE(p.post_base_units - p.pre_base_units,
                     NULLIF(p.pre_base_units, 0)) < -0.10  THEN 'hm-strong-neg'
    WHEN SAFE_DIVIDE(p.post_base_units - p.pre_base_units,
                     NULLIF(p.pre_base_units, 0)) < -0.03  THEN 'hm-mild-neg'
    WHEN SAFE_DIVIDE(p.post_base_units - p.pre_base_units,
                     NULLIF(p.pre_base_units, 0)) <=  0.03 THEN 'hm-neutral'
    WHEN SAFE_DIVIDE(p.post_base_units - p.pre_base_units,
                     NULLIF(p.pre_base_units, 0)) <=  0.10 THEN 'hm-mild-pos'
    ELSE                                                        'hm-strong-pos'
  END AS heatmap_bucket,

  -- Comparison type and distance for scope bar
  cp.comparison_type,
  cp.relationship_distance

FROM built_prepost_features p
JOIN built_enriched_weekly e
  ON p.upc = e.upc AND p.geography = e.geography_raw
JOIN comparison_pool_weekly cp
  ON p.upc = cp.candidate_upc
  AND p.geography = cp.geography_raw
  AND cp.focal_upc = :focal_upc

WHERE
  e.spins_flavor = :spins_flavor
  AND (:channel_outlet IS NULL OR p.channel_outlet = :channel_outlet)
  AND (:retail_account IS NULL OR p.retail_account = :retail_account)
  AND p.window_type = :window_type
  AND cp.relationship_distance IN (1, 2, 3, 4, 5)  -- exclude on-demand dist 6

ORDER BY cp.relationship_distance ASC, p.upc
```

**Output:** Returned directly to the UI at render time. Not materialized.
The UI pivot is done client-side: rows are (SKU × geography), columns are
the geography list from the current retail account / channel / geography-level
filter selection.

---

### Query 2d — Scope bar metadata query (new in v2)

**Purpose:** Every diagnosis screen (Pack ladder, Cross-flavor, Competitive,
Pre/post, Pool health) renders a scope bar showing the active `comparison_type`,
`relationship_distance`, SKU count in pool, and bidirectionality flag. This
metadata comes from a lightweight aggregate against `comparison_pool_weekly`.

```sql
-- Query 2d: Scope bar metadata
-- Parameterized: :focal_upc, :geography, :retail_account, :comparison_type_list, :window_weeks

SELECT
  cp.comparison_type,
  MIN(cp.relationship_distance)       AS relationship_distance,
  COUNT(DISTINCT cp.candidate_upc)    AS pool_sku_count,
  'bidirectional'                     AS pair_direction,
  STRING_AGG(DISTINCT c.description, ' · '
    ORDER BY cp.relationship_distance, c.description)
                                      AS pool_sku_names

FROM comparison_pool_weekly cp
JOIN built_enriched_weekly c
  ON cp.candidate_upc = c.upc AND cp.geography_raw = c.geography_raw

WHERE
  cp.focal_upc = :focal_upc
  AND cp.geography_raw = :geography
  AND (:retail_account IS NULL OR cp.retail_account = :retail_account)
  AND cp.comparison_type IN (:comparison_type_list)
  AND cp.week_end >= TIMESTAMPADD(WEEK, -:window_weeks, CURRENT_TIMESTAMP)

GROUP BY cp.comparison_type
```

**Output:** Returned directly to the UI. Used to populate:
- `scope-bar-value` (the `comparison_type` string)
- `scope-bar-dist` (`dist N · N SKUs in pool · pairs bidirectional`)

---

### Query 3 — Pre/post window aggregation (updated in v2)

**Purpose:** For each focal SKU, compute before/after metrics across
configurable scoring windows. **v2 change:** Now computes all four window
sizes (4w, 13w, 26w, YTD) in a single pass using `window_type` as a
grouping column. Also adds `pre_avg_arp`, `post_avg_arp` (for the ARP row
in the Pre/post screen) and explicitly uses `avg_weekly_units_spm` for all
velocity columns, renamed with `_spm` suffix throughout.

```sql
-- Production version: single pass, all focal SKUs, all geographies, all windows

SELECT
  e.upc,
  e.geography_raw                       AS geography,
  e.geography_display,
  e.geography_level,
  e.retail_account,
  e.retail_account_level,
  e.channel_outlet,
  e.channel,
  e.specific_flavor_normalized,
  e.spins_flavor,
  e.pack_count,
  fm_launch.first_week_selling          AS event_date,
  w.window_label                        AS window_type,   -- '4w', '13w', '26w', 'ytd'

  -- PRE-WINDOW metrics
  SUM(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, fm_launch.first_week_selling)
            THEN e.base_units ELSE 0 END)           AS pre_base_units,
  SUM(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, fm_launch.first_week_selling)
            THEN e.units ELSE 0 END)                AS pre_units,
  AVG(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, fm_launch.first_week_selling)
            THEN e.tdp ELSE NULL END)               AS pre_avg_tdp,
  AVG(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, fm_launch.first_week_selling)
            THEN e.avg_weekly_units_spm ELSE NULL END) AS pre_avg_velocity_spm,
  AVG(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, fm_launch.first_week_selling)
            THEN e.avg_weekly_units_per_store_selling_per_item ELSE NULL END)
                                                        AS pre_avg_velocity_store_selling,
  AVG(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, fm_launch.first_week_selling)
            THEN e.pct_stores_selling ELSE NULL END)    AS pre_pct_stores_selling,
  AVG(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, fm_launch.first_week_selling)
            THEN e.arp ELSE NULL END)               AS pre_avg_arp,
  SUM(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, fm_launch.first_week_selling)
            THEN e.promo_weeks ELSE 0 END)          AS pre_promo_weeks,
  AVG(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, fm_launch.first_week_selling)
            THEN e.units_pct_promo ELSE NULL END)    AS pre_units_pct_promo,
  AVG(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, fm_launch.first_week_selling)
            THEN e.arp_pct_discount_any_promo ELSE NULL END)
                                                        AS pre_arp_discount_any_promo,
  COUNT(CASE WHEN e.week_end < fm_launch.first_week_selling
              AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, fm_launch.first_week_selling)
              AND e.base_units IS NOT NULL
              THEN 1 END)                           AS pre_weeks_count,

  -- POST-WINDOW metrics (same structure)
  SUM(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, fm_launch.first_week_selling)
            THEN e.base_units ELSE 0 END)           AS post_base_units,
  SUM(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, fm_launch.first_week_selling)
            THEN e.units ELSE 0 END)                AS post_units,
  AVG(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, fm_launch.first_week_selling)
            THEN e.tdp ELSE NULL END)               AS post_avg_tdp,
  AVG(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, fm_launch.first_week_selling)
            THEN e.avg_weekly_units_spm ELSE NULL END) AS post_avg_velocity_spm,
  AVG(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, fm_launch.first_week_selling)
            THEN e.avg_weekly_units_per_store_selling_per_item ELSE NULL END)
                                                        AS post_avg_velocity_store_selling,
  AVG(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, fm_launch.first_week_selling)
            THEN e.pct_stores_selling ELSE NULL END)    AS post_pct_stores_selling,
  AVG(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, fm_launch.first_week_selling)
            THEN e.arp ELSE NULL END)               AS post_avg_arp,
  SUM(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, fm_launch.first_week_selling)
            THEN e.promo_weeks ELSE 0 END)          AS post_promo_weeks,
  AVG(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, fm_launch.first_week_selling)
            THEN e.units_pct_promo ELSE NULL END)    AS post_units_pct_promo,
  AVG(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, fm_launch.first_week_selling)
            THEN e.arp_pct_discount_any_promo ELSE NULL END)
                                                        AS post_arp_discount_any_promo,
  COUNT(CASE WHEN e.week_end >= fm_launch.first_week_selling
              AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, fm_launch.first_week_selling)
              AND e.base_units IS NOT NULL
              THEN 1 END)                           AS post_weeks_count

FROM built_enriched_weekly e
JOIN (
  SELECT upc, MIN(first_week_selling) AS first_week_selling
  FROM built_enriched_weekly
  WHERE first_week_selling IS NOT NULL
  GROUP BY upc
) fm_launch ON e.upc = fm_launch.upc

-- Window definition table (inline values for four window types)
CROSS JOIN (
  SELECT '4w'  AS window_label, 4   AS pre_weeks, 4   AS post_weeks UNION ALL
  SELECT '13w' AS window_label, 13  AS pre_weeks, 13  AS post_weeks UNION ALL
  SELECT '26w' AS window_label, 26  AS pre_weeks, 26  AS post_weeks UNION ALL
  SELECT 'ytd' AS window_label,
    DATEDIFF('week', DATE_TRUNC('year', CURRENT_DATE), fm_launch.first_week_selling)
                                    AS pre_weeks,
    DATEDIFF('week', fm_launch.first_week_selling,
             LEAST(CURRENT_DATE, TIMESTAMPADD(WEEK, 52, DATE_TRUNC('year', CURRENT_DATE))))
                                    AS post_weeks
) w

GROUP BY
  e.upc, e.geography_raw, e.geography_display, e.geography_level,
  e.retail_account, e.retail_account_level, e.channel_outlet, e.channel,
  e.specific_flavor_normalized, e.spins_flavor,
  e.pack_count, fm_launch.first_week_selling, w.window_label, w.pre_weeks, w.post_weeks
```

**Output table:** `built_prepost_features`
**Key columns added in v2:** `pre_avg_arp`, `post_avg_arp`, `pre_promo_weeks`,
`post_promo_weeks`, `pre_weeks_count`, `post_weeks_count`, `window_type`,
`channel_outlet`, `retail_account`, `geography_level`,
`pre/post_avg_velocity_store_selling`, `pre/post_pct_stores_selling`,
`pre/post_units_pct_promo`, `pre/post_arp_discount_any_promo`

**Note on column naming:** All velocity columns use the `_spm` suffix throughout
this table and all downstream tables. `avg_velocity` from v1 is now
`avg_velocity_spm` everywhere. This is enforced at the table schema level to
prevent accidental `Units/TDP` confusion.

---

### Query 4 — Donor pre/post aggregation (updated in v2)

**Purpose:** Same window logic as Query 3 applied to each donor SKU, keyed to
the focal SKU's launch date. **v2 change:** `window_type` grouping column added
(matches Query 3). `donor_pre_avg_velocity` → `donor_pre_avg_velocity_spm`.
`donor_post_avg_velocity` → `donor_post_avg_velocity_spm`. `pre_promo_weeks`
and `post_promo_weeks` added for the donor side (needed by the pre/post screen's
donor cards, which now show promo context).

```sql
SELECT
  p.focal_upc,
  p.donor_upc,
  p.geography,
  p.channel,
  p.specific_flavor_normalized,
  p.focal_pack_count,
  p.donor_pack_count,
  p.pack_distance,
  w.window_label                          AS window_type,

  -- DONOR PRE-WINDOW metrics
  SUM(CASE WHEN e.week_end < focal_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, focal_launch.first_week_selling)
            THEN e.base_units ELSE 0 END)   AS donor_pre_base_units,
  SUM(CASE WHEN e.week_end < focal_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, focal_launch.first_week_selling)
            THEN e.units ELSE 0 END)         AS donor_pre_units,
  AVG(CASE WHEN e.week_end < focal_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, focal_launch.first_week_selling)
            THEN e.tdp ELSE NULL END)        AS donor_pre_avg_tdp,
  AVG(CASE WHEN e.week_end < focal_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, focal_launch.first_week_selling)
            THEN e.avg_weekly_units_spm ELSE NULL END) AS donor_pre_avg_velocity_spm,
  AVG(CASE WHEN e.week_end < focal_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, focal_launch.first_week_selling)
            THEN e.arp ELSE NULL END)        AS donor_pre_avg_arp,
  SUM(CASE WHEN e.week_end < focal_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, focal_launch.first_week_selling)
            THEN e.promo_weeks ELSE 0 END)   AS donor_pre_promo_weeks,
  COUNT(CASE WHEN e.week_end < focal_launch.first_week_selling
              AND e.week_end >= TIMESTAMPADD(WEEK, -w.pre_weeks, focal_launch.first_week_selling)
              AND e.base_units IS NOT NULL THEN 1 END) AS donor_pre_weeks_count,

  -- DONOR POST-WINDOW metrics (same structure)
  SUM(CASE WHEN e.week_end >= focal_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, focal_launch.first_week_selling)
            THEN e.base_units ELSE 0 END)   AS donor_post_base_units,
  SUM(CASE WHEN e.week_end >= focal_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, focal_launch.first_week_selling)
            THEN e.units ELSE 0 END)         AS donor_post_units,
  AVG(CASE WHEN e.week_end >= focal_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, focal_launch.first_week_selling)
            THEN e.tdp ELSE NULL END)        AS donor_post_avg_tdp,
  AVG(CASE WHEN e.week_end >= focal_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, focal_launch.first_week_selling)
            THEN e.avg_weekly_units_spm ELSE NULL END) AS donor_post_avg_velocity_spm,
  AVG(CASE WHEN e.week_end >= focal_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, focal_launch.first_week_selling)
            THEN e.arp ELSE NULL END)        AS donor_post_avg_arp,
  SUM(CASE WHEN e.week_end >= focal_launch.first_week_selling
            AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, focal_launch.first_week_selling)
            THEN e.promo_weeks ELSE 0 END)   AS donor_post_promo_weeks,
  COUNT(CASE WHEN e.week_end >= focal_launch.first_week_selling
              AND e.week_end < TIMESTAMPADD(WEEK, w.post_weeks, focal_launch.first_week_selling)
              AND e.base_units IS NOT NULL THEN 1 END) AS donor_post_weeks_count

FROM built_enriched_weekly e
JOIN (
  SELECT DISTINCT focal_upc, donor_upc, geography, channel,
                  specific_flavor_normalized,
                  focal_pack_count, donor_pack_count, pack_distance
  FROM pack_ladder_pairs_weekly
) p ON e.upc = p.donor_upc AND e.geography_raw = p.geography
JOIN (
  SELECT upc, MIN(first_week_selling) AS first_week_selling
  FROM built_enriched_weekly
  WHERE first_week_selling IS NOT NULL
  GROUP BY upc
) focal_launch ON p.focal_upc = focal_launch.upc
CROSS JOIN (
  SELECT '4w' AS window_label, 4 AS pre_weeks, 4 AS post_weeks UNION ALL
  SELECT '13w', 13, 13 UNION ALL
  SELECT '26w', 26, 26
  -- YTD window omitted for donor table; donor window always matches focal window
) w
GROUP BY
  p.focal_upc, p.donor_upc, p.geography, p.channel,
  p.specific_flavor_normalized, p.focal_pack_count,
  p.donor_pack_count, p.pack_distance,
  focal_launch.first_week_selling, w.window_label, w.pre_weeks, w.post_weeks
```

**Output table:** `donor_prepost_features`

---

### Query 5 — Final ML feature table assembly (updated in v2)

**Purpose:** Join focal and donor pre/post features; compute all derived change
signals. One row = one (focal_upc, donor_upc, geography, window_type) training
example. **v2 changes:** All `_velocity_` columns renamed to `_velocity_spm_`.
`focal_post_velocity_per_tdp` removed (was the `Units/TDP` proxy — excluded
by policy). `incremental_share` computed and stored as a label-adjacent column
(not a ML target, but passed to `scored_cannibalization` for the second score bar).

```sql
SELECT
  -- Keys
  f.focal_upc,
  f.donor_upc,
  f.geography,
  f.channel,
  f.specific_flavor_normalized,
  f.focal_pack_count,
  f.donor_pack_count,
  f.pack_distance,
  f.window_type,

  -- FOCAL CHANGE FEATURES
  SAFE_DIVIDE(f.post_base_units - f.pre_base_units,
              NULLIF(f.pre_base_units, 0))              AS focal_base_units_pct_chg,
  SAFE_DIVIDE(f.post_units - f.pre_units,
              NULLIF(f.pre_units, 0))                   AS focal_units_pct_chg,
  SAFE_DIVIDE(f.post_avg_tdp - f.pre_avg_tdp,
              NULLIF(f.pre_avg_tdp, 0))                 AS focal_tdp_pct_chg,
  SAFE_DIVIDE(f.post_avg_velocity_spm - f.pre_avg_velocity_spm,
              NULLIF(f.pre_avg_velocity_spm, 0))        AS focal_velocity_spm_pct_chg,
  SAFE_DIVIDE(f.post_avg_arp - f.pre_avg_arp,
              NULLIF(f.pre_avg_arp, 0))                 AS focal_arp_pct_chg,
  f.post_promo_weeks - f.pre_promo_weeks                AS focal_promo_week_delta,

  -- DONOR CHANGE FEATURES
  SAFE_DIVIDE(d.donor_post_base_units - d.donor_pre_base_units,
              NULLIF(d.donor_pre_base_units, 0))        AS donor_base_units_pct_chg,
  SAFE_DIVIDE(d.donor_post_units - d.donor_pre_units,
              NULLIF(d.donor_pre_units, 0))              AS donor_units_pct_chg,
  SAFE_DIVIDE(d.donor_post_avg_tdp - d.donor_pre_avg_tdp,
              NULLIF(d.donor_pre_avg_tdp, 0))            AS donor_tdp_pct_chg,
  SAFE_DIVIDE(d.donor_post_avg_velocity_spm - d.donor_pre_avg_velocity_spm,
              NULLIF(d.donor_pre_avg_velocity_spm, 0))   AS donor_velocity_spm_pct_chg,
  d.donor_post_promo_weeks - d.donor_pre_promo_weeks    AS donor_promo_week_delta,

  -- DIFFERENTIAL FEATURES (focal vs. donor — the core cannibalization signal)
  SAFE_DIVIDE(f.post_base_units - f.pre_base_units,
              NULLIF(f.pre_base_units, 0))
  - SAFE_DIVIDE(d.donor_post_base_units - d.donor_pre_base_units,
                NULLIF(d.donor_pre_base_units, 0))      AS base_units_delta_diff,

  SAFE_DIVIDE(f.post_avg_velocity_spm - f.pre_avg_velocity_spm,
              NULLIF(f.pre_avg_velocity_spm, 0))
  - SAFE_DIVIDE(d.donor_post_avg_velocity_spm - d.donor_pre_avg_velocity_spm,
                NULLIF(d.donor_pre_avg_velocity_spm, 0)) AS velocity_spm_delta_diff,

  -- PACK LADDER CONTEXT
  f.pack_distance,
  SAFE_DIVIDE(f.post_avg_arp, NULLIF(f.focal_pack_count, 0)) AS focal_price_per_unit,

  -- PROMO CONTEXT
  f.post_promo_weeks                                    AS focal_post_promo_weeks,
  d.donor_post_promo_weeks                              AS donor_post_promo_weeks,

  -- PROMO CONFOUND FLAG (used by event suppression logic)
  CASE WHEN (d.donor_post_promo_weeks - d.donor_pre_promo_weeks) > 2
       THEN TRUE ELSE FALSE END                         AS promo_confounded,

  -- INCREMENTAL SHARE (not a training target; passed to scored output for second score bar)
  -- Defined as: focal base unit gain / (focal gain + absolute donor loss), clamped [0,1]
  CASE
    WHEN (f.post_base_units - f.pre_base_units) <= 0 THEN 0.0
    WHEN (d.donor_pre_base_units - d.donor_post_base_units) <= 0
      THEN 1.0
    ELSE LEAST(1.0,
           SAFE_DIVIDE(f.post_base_units - f.pre_base_units,
             (f.post_base_units - f.pre_base_units)
             + ABS(d.donor_pre_base_units - d.donor_post_base_units)))
  END                                                   AS incremental_share,

  -- LABEL CONSTRUCTION (deterministic rule — see Section 4)
  CASE
    WHEN SAFE_DIVIDE(d.donor_post_base_units - d.donor_pre_base_units,
                     NULLIF(d.donor_pre_base_units, 0)) < -0.10
     AND SAFE_DIVIDE(f.post_base_units - f.pre_base_units,
                     NULLIF(f.pre_base_units, 0)) > 0.03
    THEN 'CANNIBALIZING'
    WHEN SAFE_DIVIDE(d.donor_post_base_units - d.donor_pre_base_units,
                     NULLIF(d.donor_pre_base_units, 0)) BETWEEN -0.10 AND -0.03
     AND SAFE_DIVIDE(f.post_base_units - f.pre_base_units,
                     NULLIF(f.pre_base_units, 0)) > 0.00
    THEN 'WATCH'
    WHEN SAFE_DIVIDE(d.donor_post_base_units - d.donor_pre_base_units,
                     NULLIF(d.donor_pre_base_units, 0)) >= -0.03
    THEN 'INCREMENTAL'
    ELSE 'NEUTRAL'
  END AS label_deterministic

FROM built_prepost_features f
JOIN donor_prepost_features d
  ON f.upc = d.focal_upc
  AND f.geography = d.geography
  AND f.window_type = d.window_type
```

**Output table:** `ml_training_features`
**Removed in v2:** `focal_post_velocity_per_tdp` (was a `Units/TDP` proxy — excluded)
**Added in v2:** `incremental_share`, `donor_promo_week_delta`, `promo_confounded`,
`focal_arp_pct_chg`, `window_type`, `channel`

---

### Query 6 — Rolling stats + z-scores for event detection (unchanged from v1)

Rolling 4-week and 8-week averages, standard deviations, z-scores, and WoW
deltas for `base_units`, `avg_weekly_units_spm`, and `tdp`. Output table:
`event_detection_weekly`. See v1 plan Section 9.2 for full SQL.

---

### Query 7 — New UPC detection (unchanged from v1)

Anti-join of current week BUILT UPCs against all prior weeks.
Output table: `new_upc_candidates`.

---

### Query 8 — New UPC classification (unchanged from v1)

Classifies new UPCs as `NEW_PACK_SIZE`, `NEW_FLAVOR_CANDIDATE`, or
`DUPLICATE_OR_RELAUNCH`. Output table: `new_upc_classifications`.

---

### Query 9 — Ramp monitoring (updated in v2)

**Purpose:** Track all BUILT SKUs in their first 16 weeks post-launch.
**v2 change:** `velocity_vs_4w_avg_ratio` now uses `avg_weekly_units_spm`
(renamed from generic velocity). Output columns aligned with the Ramp Monitor
screen columns: `distribution_trend` (RAMPING / STABLE / DECLINING), `peak_tdp`,
`current_tdp`, `weeks_since_launch`. The `scoring_status` column is now computed
directly in this query (previously derived in Python) for consistency with the
badge values rendered in the UI.

```sql
SELECT
  e.upc,
  e.geography_raw,
  e.week_end,
  e.specific_flavor_normalized,
  e.spins_flavor,
  e.pack_count,
  e.tdp,
  e.base_units,
  e.avg_weekly_units_spm,
  e.first_week_selling,

  DATEDIFF('week',
    CAST(e.first_week_selling AS DATE),
    CAST(e.week_end AS DATE))               AS weeks_since_launch,

  MAX(e.tdp) OVER (
    PARTITION BY e.upc, e.geography_raw
    ORDER BY e.week_end
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  )                                          AS peak_tdp,

  AVG(e.avg_weekly_units_spm) OVER (
    PARTITION BY e.upc, e.geography_raw
    ORDER BY e.week_end
    ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
  )                                          AS rolling_4w_avg_velocity_spm,

  CASE
    WHEN e.tdp > LAG(e.tdp, 1) OVER (
           PARTITION BY e.upc, e.geography_raw ORDER BY e.week_end)
      THEN 'RAMPING'
    WHEN e.tdp = LAG(e.tdp, 1) OVER (
           PARTITION BY e.upc, e.geography_raw ORDER BY e.week_end)
      THEN 'STABLE'
    ELSE 'DECLINING'
  END                                        AS distribution_trend,

  -- Scoring status (maps to badge in Ramp Monitor UI)
  -- Weeks 1–6: suppressed; 7–8: LOW confidence; 9+: MEDIUM+ if data quality passes
  CASE
    WHEN DATEDIFF('week',
           CAST(e.first_week_selling AS DATE),
           CAST(e.week_end AS DATE)) <= 6
      THEN 'SUPPRESSED'
    WHEN DATEDIFF('week',
           CAST(e.first_week_selling AS DATE),
           CAST(e.week_end AS DATE)) BETWEEN 7 AND 8
      THEN 'LOW_CONFIDENCE'
    ELSE 'ACTIVE'
  END                                        AS scoring_status,

  -- Underperforming flag (fires the "Launch underperforming" event rule)
  CASE
    WHEN DATEDIFF('week',
           CAST(e.first_week_selling AS DATE),
           CAST(e.week_end AS DATE)) >= 6
     AND (e.avg_weekly_units_spm / NULLIF(
            AVG(e.avg_weekly_units_spm) OVER (
              PARTITION BY e.upc, e.geography_raw
              ORDER BY e.week_end
              ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING), 0)) < 0.85
     AND (CASE
           WHEN e.tdp = LAG(e.tdp, 1) OVER (
                  PARTITION BY e.upc, e.geography_raw ORDER BY e.week_end)
             THEN 'STABLE'
           WHEN e.tdp < LAG(e.tdp, 1) OVER (
                  PARTITION BY e.upc, e.geography_raw ORDER BY e.week_end)
             THEN 'DECLINING'
           ELSE 'RAMPING' END) IN ('STABLE', 'DECLINING')
    THEN TRUE ELSE FALSE
  END                                        AS underperforming_flag

FROM built_enriched_weekly e
WHERE
  e.first_week_selling >= TIMESTAMPADD(WEEK, -16, CURRENT_TIMESTAMP)
  AND e.first_week_selling IS NOT NULL
ORDER BY e.upc, e.geography_raw, e.week_end
```

**Output table:** `new_product_ramp_monitor`
**Key columns added in v2:** `scoring_status`, `underperforming_flag`
(both were previously Python-computed; now in Druid for consistency with
UI badge values)

---

## Section 4. Label Construction

Labels are constructed deterministically from the data and used as ML training
targets. No ground truth exists in SPINS.

### Primary label: `cannibalization_status`

| Label | Rule |
|---|---|
| `CANNIBALIZING` | Donor base units fell >10% AND focal base units rose >3% in same window |
| `WATCH` | Donor base units fell 3–10% AND focal base units positive |
| `INCREMENTAL` | Donor base units flat or positive (≤−3% change) regardless of focal |
| `NEUTRAL` | Insufficient evidence — suppress from training; do not score |

### Secondary label: `demand_vs_distribution`

Used to train the "Distribution-Led Gain" callout detector.

| Label | Rule |
|---|---|
| `DEMAND_LED` | Focal `avg_weekly_units_spm` rose alongside base units |
| `DISTRIBUTION_LED` | Focal TDP rose >15% but focal `avg_weekly_units_spm` flat or fell |
| `MIXED` | Both TDP and velocity changed but neither cleanly dominates |

### Incremental share (not a label — a scored output)

`incremental_share` is computed in Query 5 as a ratio: focal base unit gain
divided by (focal gain + absolute donor loss). It is clamped to [0, 1] and
stored in `scored_cannibalization` as a separate column from `cannibal_prob`.
The UI renders it as a second score bar on the SKU Summary screen with a green
fill and its own badge (e.g. "63% · Mixed").

### Label quality guardrails

- **Minimum weeks required:** Both pre and post windows must have ≥8 non-null weeks (checked via `pre_weeks_count` and `post_weeks_count` in Query 3/4). Rows with fewer are labeled `NEUTRAL` and excluded from training.
- **Promo contamination flag:** If donor `post_promo_weeks` increased by >2 relative to pre, donor `post_units_pct_promo` rises sharply, or donor `post_arp_discount_any_promo` deepens by >5 points, mark `promo_confounded = TRUE`. These rows train in a secondary pass only.
- **Retail/account coverage:** Require enough observations within the selected `retail_account` + `channel_outlet` + `geography_level` grain. If sparse, roll up one level in the UI filter before scoring rather than mixing unrelated retailers.
- **Pack distance normalization:** Weight training examples inversely by `pack_distance` — closer pack sizes (1ct vs. 4pk) are stronger prior signals than 1ct vs. 18pk.
- **Ramp window exclusion:** Rows where `scoring_status = 'SUPPRESSED'` (weeks 1–6 post-launch) are excluded from training and from the scored output entirely. Rows where `scoring_status = 'LOW_CONFIDENCE'` (weeks 7–8) are included in training with a weight of 0.5 and scored with confidence = `LOW`.

---

## Section 5. ML Model Architecture

### Model 1 — Cannibalization risk classifier

**Type:** LightGBM binary classifier (CANNIBALIZING=1, INCREMENTAL+NEUTRAL=0)
**Input:** `ml_training_features` table
**Output:** `cannibal_prob` (0.0–1.0), converted to Watch/Incremental/Cannibalizing status

**Key features (in priority order):**

| Feature | Why it matters |
|---|---|
| `donor_base_units_pct_chg` | Primary signal — did the incumbent actually lose? |
| `focal_base_units_pct_chg` | Confirmation — did the focal actually gain? |
| `base_units_delta_diff` | Net transfer signal — focal gain minus donor loss |
| `focal_tdp_pct_chg` | Distribution expansion confounder |
| `focal_pct_stores_selling_pct_chg` | Separates new doors from better selling in existing doors |
| `focal_velocity_spm_pct_chg` | Per-store demand signal — separates reach from pull |
| `donor_velocity_spm_pct_chg` | Donor productivity — did it also lose per-store? |
| `focal_velocity_store_selling_pct_chg` | Cleaner store-selling productivity signal when available |
| `donor_velocity_store_selling_pct_chg` | Donor productivity among stores actually selling the item |
| `velocity_spm_delta_diff` | Net productivity transfer signal |
| `pack_distance` | Closer sizes cannibalise more; controls substitutability |
| `relationship_distance` | Structural prior by comparison type |
| `focal_price_per_unit` | Price-per-bar relationship across pack formats |
| `focal_post_promo_weeks` | Controls for promo-driven launch lift |
| `donor_post_promo_weeks` | Controls for donor promo defense activity |
| `focal_post_units_pct_promo` / `donor_post_units_pct_promo` | Controls for promo-mix changes |
| `focal_post_arp_discount_any_promo` / `donor_post_arp_discount_any_promo` | Controls for promo depth |
| `units_lift_tpr`, `units_lift_any_display`, `units_lift_any_feature` | Flags display/feature/TPR-driven movement that should not be overread as cannibalization |
| `base_units_yago_pct_chg`, `units_yago_pct_chg` | Retailer-specific seasonality and year-ago baseline controls |
| `channel_outlet`, `retail_account`, `geography_level` | Context features; prevents one retailer/channel pattern from being learned as universal |
| `focal_arp_pct_chg` | Price change as a demand shift confound |
| `window_type` | Feature encoding for the four window sizes (4w/13w/26w/YTD) |

**Note:** `Units/TDP` is not used as a feature. Velocity is carried by
`avg_weekly_units_spm` and, where populated, by
`avg_weekly_units_per_store_selling_per_item`.

```python
import lightgbm as lgb

model_cannibal = lgb.LGBMClassifier(
    objective='binary',
    n_estimators=500,
    learning_rate=0.05,
    num_leaves=63,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=5,
    min_child_samples=20,
    class_weight='balanced',
    random_state=42
)

model_cannibal.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)]
)
```

---

### Model 2 — Donor SKU ranker

**Type:** LightGBM ranking model (LambdaRank / pairwise)
**Purpose:** Given a focal SKU, rank all candidate donor SKUs by likelihood
of being the primary demand source. Donor ranking by LambdaRank model is
now surfaced explicitly in the SKU Summary screen ("Donor ranking by LambdaRank
model. Primary: 1ct (−14% base units post-launch).").

```python
model_ranker = lgb.LGBMRanker(
    objective='lambdarank',
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=31,
    label_gain=[0, 1, 3, 7]
)
```

---

### Model 3 — Significant event detector

**Type:** LightGBM binary classifier
**Purpose:** Determine whether a metric shift clears a statistical significance
threshold worth surfacing as an event callout. The output feeds the Priority
Events landing page — both the five existing event card types and the new
`NEW_PACK_SIZE` alert banner.

---

## Section 6. Scoring Pipeline

### Scoring frequency
- Full rescore: weekly, triggered after new SPINS data lands in Druid
- Partial rescore: on-demand per focal SKU when a user opens the tool

### Scored output schema: `scored_cannibalization`

**v3 additions marked with ★**

```sql
CREATE TABLE scored_cannibalization (
  __time                    TIMESTAMP,    -- week-ending date of scoring
  focal_upc                 VARCHAR,
  focal_description         VARCHAR,      -- ★ denormalized for context bar
  geography                 VARCHAR,
  geography_display         VARCHAR,      -- ★ human-readable geo label for context bar
  geography_level           VARCHAR,      -- ★ CRMA / RMA / future SPINS levels
  retail_account            VARCHAR,      -- ★ direct from SPINS
  retail_account_level      VARCHAR,      -- ★ e.g. TOTAL CORPORATE
  channel_outlet            VARCHAR,      -- ★ direct from SPINS, e.g. CONVENTIONAL|FOOD
  channel                   VARCHAR,      -- compatibility alias for channel_outlet
  specific_flavor_normalized VARCHAR,
  spins_flavor               VARCHAR,
  focal_pack_count          INTEGER,
  window_type               VARCHAR,      -- ★ '4w' / '13w' / '26w' / 'ytd'
  comparison_type           VARCHAR,      -- ★ e.g. SAME_SPECIFIC_FLAVOR_SAME_BRAND_PACK_LADDER
  comparison_scope_label    VARCHAR,      -- ★ human-readable e.g. 'Pack ladder (dist 1)'
  relationship_distance     INTEGER,      -- ★ 1–6
  cannibal_prob             DOUBLE,
  cannibal_status           VARCHAR,      -- Incremental / Watch / Cannibalizing
  cannibal_confidence       VARCHAR,      -- High / Medium / Low
  incremental_share         DOUBLE,       -- ★ second score bar on SKU Summary
  demand_vs_dist            VARCHAR,      -- Demand_Led / Distribution_Led / Mixed
  focal_pct_stores_selling_pct_chg DOUBLE, -- ★ distribution quality
  focal_velocity_store_selling_pct_chg DOUBLE, -- ★ store-selling productivity
  donor_velocity_store_selling_pct_chg DOUBLE, -- ★ donor store-selling productivity
  focal_post_units_pct_promo DOUBLE,      -- ★ promo-mix control
  donor_post_units_pct_promo DOUBLE,      -- ★ promo defense control
  focal_post_arp_discount_any_promo DOUBLE, -- ★ promo depth control
  donor_post_arp_discount_any_promo DOUBLE, -- ★ promo depth control
  donor_rank_1_upc          VARCHAR,
  donor_rank_1_description  VARCHAR,      -- ★ denormalized for donor chips
  donor_rank_2_upc          VARCHAR,
  donor_rank_2_description  VARCHAR,      -- ★ denormalized for donor chips
  significant_event         BOOLEAN,
  event_label               VARCHAR,
  p_value                   DOUBLE,       -- ★ surfaced in Provenance panel
  z_score_donor             DOUBLE,       -- ★ surfaced in Provenance panel
  promo_confounded          BOOLEAN,      -- ★ surfaced in Provenance panel
  scoring_status            VARCHAR,      -- ★ SUPPRESSED / LOW_CONFIDENCE / ACTIVE
  shap_feature_1            VARCHAR,
  shap_value_1              DOUBLE,
  shap_feature_2            VARCHAR,
  shap_value_2              DOUBLE,
  shap_feature_3            VARCHAR,
  shap_value_3              DOUBLE,
  model_version             VARCHAR,
  scored_at                 TIMESTAMP
)
```

### Event queue schema: `event_queue`

**v3 additions marked with ★**

```sql
CREATE TABLE event_queue (
  __time                    TIMESTAMP,
  focal_upc                 VARCHAR,
  focal_description         VARCHAR,
  geography                 VARCHAR,
  geography_level           VARCHAR,      -- ★ direct SPINS field
  retail_account            VARCHAR,      -- ★ direct SPINS field
  channel_outlet            VARCHAR,      -- ★ direct SPINS field
  event_type                VARCHAR,      -- ★ NEW: includes 'NEW_PACK_SIZE'
  event_label               VARCHAR,
  confidence                VARCHAR,
  cannibal_prob             DOUBLE,
  cannibal_status           VARCHAR,
  comparison_type           VARCHAR,      -- ★ for relationship_distance badge on event cards
  relationship_distance     INTEGER,      -- ★ for relationship_distance badge on event cards
  pct_change                DOUBLE,
  p_value                   DOUBLE,
  z_score                   DOUBLE,
  donor_upc                 VARCHAR,
  donor_description         VARCHAR,
  shap_top_3                VARCHAR,      -- JSON array of [{feature, value}]
  scored_at                 TIMESTAMP,
  model_version             VARCHAR
)
```

**`event_type` values (v2):**

| event_type | UI surface | Badge color |
|---|---|---|
| `DEMAND_TRANSFER` | "Significant demand transfer detected" | Red |
| `LAUNCH_UNDERPERFORMING` | "Launch underperforming in [geo]" | Amber |
| `PACK_OVERLAP_RISK` | "Same-flavor pack overlap risk elevated" | Amber |
| `CROSS_FLAVOR_SIGNAL` | "Cross-flavor signal: [SKU] declining in [geo]" | Amber |
| `INCREMENTAL_CHANNEL` | "Club channel is behaving incrementally" | Green |
| `FORECAST_RISK` | "Forecasted risk if Grocery expands broadly" | Blue |
| `NEW_PACK_SIZE` | ★ Alert banner (not a card): "New pack size auto-detected: [SKU]" | Amber banner |

**`NEW_PACK_SIZE` event handling:**
The new-pack-size alert renders as a fixed amber banner above the event cards
on the Priority Events page (not as a scrollable card). It maps from
`new_upc_classifications` where `classification = 'NEW_PACK_SIZE'`, not from
the standard ML scoring pipeline. It is written to `event_queue` with
`event_type = 'NEW_PACK_SIZE'` and `confidence = 'Medium'` (always) so it
passes the confidence floor filter in the UI.

The banner text template:
```
"New pack size auto-detected: [focal_description]"
"First seen [first_seen_week] · provisionally enrolled in pack ladder
monitoring · pending taxonomy review · cannibalization scoring active
at week 8"
```

---

## Section 7. SHAP Explainability

Every scored row carries its top-3 SHAP drivers. These populate:
- The driver bar chart in the Explanation screen (5 drivers shown in UI — top 3
  from SHAP, then `pack_distance` as a structural prior row, then
  `promo_week_delta` as a confound-control row; the latter two are always shown
  even if not in the top-3 SHAP list)
- The Provenance panel (`p_value`, `z_score_donor`, `promo_confounded`)
- The Mo narrative template

**v2 narrative template** (updated to include promo and pack distance explicitly):

```
"{focal_description} is flagged as {cannibal_status} in {geography} because
{shap_feature_1} changed by {shap_value_1_pct}% while {donor_description}
{donor_direction} over the same period. Pack distance = {pack_distance}
({substitution_read}). {promo_note}."
```

Where:
- `substitution_read`: "high substitution prior" if pack_distance ≤ 4, "low substitution prior" if > 4
- `promo_note`: "Promo weeks delta: +{n} — not confounded." if `promo_confounded = FALSE`, "Promo activity increased — interpret with caution." if `TRUE`

```python
import shap

explainer = shap.TreeExplainer(model_cannibal)
shap_values = explainer.shap_values(X_score)

def top_shap_drivers(shap_row, feature_names, n=3):
    import numpy as np
    idx = np.argsort(np.abs(shap_row))[::-1][:n]
    return [(feature_names[i], float(shap_row[i])) for i in idx]
```

**Fixed explanation rows (always shown in UI, regardless of SHAP rank):**

| Row | Feature | Tag style |
|---|---|---|
| Variable | `shap_feature_1` | Depends on sign |
| Variable | `shap_feature_2` | Depends on sign |
| Variable | `shap_feature_3` | Depends on sign |
| Fixed | Pack distance (`pack_distance`) | Blue (structural prior) |
| Fixed | Promo weeks delta (`focal_promo_week_delta`) | Gray if not confounded, amber if confounded |

---

## Section 8. Data Quality Guardrails

### Minimum evidence thresholds before scoring

| Check | Threshold | Action if fails |
|---|---|---|
| Pre-window weeks (`pre_weeks_count`) | ≥8 weeks | Label NEUTRAL, exclude from training |
| Post-window weeks (`post_weeks_count`) | ≥8 weeks | Label NEUTRAL, exclude from training |
| Donor pre base units | >0 | Exclude pair — donor not established |
| Focal TDP post | >0 | Exclude — focal never distributed |
| Geography data coverage | ≥4 geographies per UPC | Flag as data-sparse |
| Ramp status | `scoring_status != 'SUPPRESSED'` | Exclude entirely from scoring |

### Confidence tiers (updated in v2)

| Tier | Criteria |
|---|---|
| High | ≥12 pre-weeks, ≥10 post-weeks, ≥2 donors in pool, p<0.05, `scoring_status = 'ACTIVE'` |
| Medium | 8–12 pre-weeks OR 1 donor in pool OR p<0.10 OR `scoring_status = 'LOW_CONFIDENCE'` |
| Low | <8 weeks either window, or below significance threshold — visible in analyst drill-down only |
| Suppressed | `scoring_status = 'SUPPRESSED'` (weeks 1–6 post-launch) — not scored, not shown |

**UI confidence floor filter** maps to these tiers:
- "High only" → `cannibal_confidence = 'High'`
- "Medium + High" (default) → `cannibal_confidence IN ('High', 'Medium')`
- "All (includes Low)" → no confidence filter applied

---

## Section 9. Significant Event Detection & Outlier Flagging

### 9.1 The two-layer detection design

```
Layer 1: Statistical significance   →  did this metric shift more than noise?
Layer 2: Business rule thresholds   →  is the shift large enough to matter?
Both must fire                       →  event is surfaced with a confidence label
Either fires alone                   →  event is suppressed or downgraded to Low
```

### 9.2 Outlier detection (z-score method)

Z-score computed against 8-week rolling baseline in `event_detection_weekly`.
The win/loss matrix in the Pool Health screen explicitly shows `0` for weeks
where fewer than 8 prior weeks of data exist — this is now a formal rule:
`win_cell = NULL` (rendered as `0` in UI) when `rolling_8w_stddev_base_units IS NULL`.

| Z-score | Classification | UI action |
|---|---|---|
| ≥ 3.0 or ≤ −3.0 | EXTREME_OUTLIER | Always surface if practical threshold also met |
| ≥ 2.0 or ≤ −2.0 | OUTLIER | Surface if corroborated by business rule |
| ≥ 1.5 or ≤ −1.5 | WATCH | Queue for monitoring, do not surface |
| < 1.5 | NORMAL | Suppress |

### 9.3 Statistical significance (Welch's t-test on windows)

```python
from scipy import stats

def test_window_significance(pre_series, post_series,
                              practical_threshold_pct=0.05, alpha=0.10):
    if len(pre_series) < 4 or len(post_series) < 4:
        return {'significant': False, 'reason': 'INSUFFICIENT_WEEKS',
                'p_value': None, 'pct_change': None}
    t_stat, p_val = stats.ttest_ind(pre_series, post_series, equal_var=False)
    mean_pre  = pre_series.mean()
    mean_post = post_series.mean()
    pct_chg   = (mean_post - mean_pre) / (abs(mean_pre) + 1e-9)
    stat_sig  = p_val < alpha
    pract_sig = abs(pct_chg) > practical_threshold_pct
    return {
        'significant':   stat_sig and pract_sig,
        'pct_change':    pct_chg,
        'p_value':       p_val,
        'direction':     'UP' if pct_chg > 0 else 'DOWN',
    }
```

The `p_value` returned here maps directly to the `p_value` column in
`scored_cannibalization` and is surfaced in the Provenance panel as
"p-value (donor)". The z-score from `event_detection_weekly` maps to
`z_score_donor`.

### 9.4 Business rule thresholds (unchanged from v1)

| Event type | Statistical gate | Business rule gate |
|---|---|---|
| Demand transfer detected | Focal p<0.10, donor p<0.10 | Focal base units +3%, donor base units −10% |
| Launch underperforming | Focal base units p<0.10 | TDP +15% AND velocity_spm −5% |
| Pack overlap risk elevated | Donor p<0.10 | Donor base units −5% with focal in same specific flavor/geo |
| Distribution-led gain | TDP p<0.10 | TDP +15% AND base units +3% AND velocity_spm flat/down |
| Cross-flavor signal ★ | Dist-3/4 candidate p<0.10 | Candidate base units −5% in ≥1 geography concurrent with focal launch |
| Velocity outlier | Velocity z ≥ 2.0 | velocity_spm deviation ≥ 25% from 8-week rolling average |

**Cross-flavor signal is new in v2.** It fires when a dist-3 or dist-4 candidate
(same SPINS FLAVOR, different specific flavor or different parent brand) shows a
statistically significant concurrent decline during the focal SKU's launch
window. The event surfaces with `relationship_distance` badge on the Priority
Events card ("dist 3 · Cross-flavor").

### 9.5 Event assembly (updated in v2)

The `assemble_events` function is extended to handle `event_type = 'CROSS_FLAVOR_SIGNAL'`
and to write `comparison_type` and `relationship_distance` to every assembled event
record (needed for the `dist N · [type]` badge on Priority Events cards):

```python
def assemble_events(scored_row, sig_result, outlier_result):
    # ... (suppression logic unchanged from v1) ...

    # Event label and type selection
    donor_pct_chg = scored_row.get('donor_base_units_pct_chg', 0)
    tdp_pct_chg   = scored_row.get('focal_tdp_pct_chg', 0)
    vel_pct_chg   = scored_row.get('focal_velocity_spm_pct_chg', 0)
    rel_dist      = scored_row.get('relationship_distance', 1)

    if donor_pct_chg < -0.10 and pct_chg > 0.03:
        event_label = 'Significant Demand Transfer Detected'
        event_type  = 'DEMAND_TRANSFER'
    elif tdp_pct_chg > 0.15 and vel_pct_chg < -0.03:
        event_label = 'Distribution-Led Gain Detected'
        event_type  = 'DEMAND_TRANSFER'
    elif donor_pct_chg < -0.05 and rel_dist in (3, 4):
        event_label = f'Cross-Flavor Signal: {scored_row.get("donor_description","?")} Declining'
        event_type  = 'CROSS_FLAVOR_SIGNAL'
    elif donor_pct_chg < -0.05:
        event_label = 'Pack Overlap Risk Elevated'
        event_type  = 'PACK_OVERLAP_RISK'
    elif pct_chg < -0.10 and tdp_pct_chg >= 0:
        event_label = 'Launch Underperforming in Geography'
        event_type  = 'LAUNCH_UNDERPERFORMING'
    elif abs(z_score) >= 2.0:
        event_label = 'Velocity Outlier Detected'
        event_type  = 'DEMAND_TRANSFER'
    else:
        event_label = 'Watch — Monitor Before Expanding'
        event_type  = 'PACK_OVERLAP_RISK'

    return {
        'focal_upc':           scored_row['focal_upc'],
        'focal_description':   scored_row['focal_description'],
        'geography':           scored_row['geography'],
        'event_type':          event_type,
        'event_label':         event_label,
        'confidence':          confidence,
        'cannibal_prob':       cannibal_prob,
        'cannibal_status':     scored_row['cannibal_status'],
        'comparison_type':     scored_row['comparison_type'],
        'relationship_distance': scored_row['relationship_distance'],
        'pct_change':          pct_chg,
        'p_value':             sig_result['p_value'],
        'z_score':             z_score,
        'donor_upc':           scored_row.get('donor_rank_1_upc'),
        'donor_description':   scored_row.get('donor_rank_1_description'),
        'shap_top_3':          scored_row.get('shap_drivers'),
        'scored_at':           scored_row['scored_at'],
        'model_version':       scored_row['model_version']
    }
```

### 9.6 How events surface in the tool (updated in v2)

Each event record maps to one card on the Priority Events landing page:

```
event_type         →  Card border color (red/amber/green/blue)
event_label        →  Card title
geography          →  Card subtitle geography slot
focal_description  →  Focal SKU name (denormalized — no secondary join needed)
donor_description  →  Donor SKU name (denormalized)
confidence         →  Dot color + label
cannibal_status    →  Status badge (Cannibalizing / Watch / Incremental)
comparison_type +
relationship_distance → Relationship badge ("dist 1 · Pack ladder",
                         "dist 3 · Cross-flavor") — ★ new in v2
shap_top_3         →  Pre-populated into Explanation drawer on drill-down
p_value            →  Shown in Provenance panel as "significance level"
z_score            →  Shown in Provenance panel as "deviation from baseline"
promo_confounded   →  Shown in Provenance panel as "Promo confounded"
```

`NEW_PACK_SIZE` events are filtered from the standard card rendering loop and
rendered as a fixed amber banner above the cards instead. The banner is always
shown when any `NEW_PACK_SIZE` event exists with `scored_at >= CURRENT_TIMESTAMP - 7 DAYS`.

---

## Section 10. New Product & New Pack Size Detection

### Confidence ladder by ramp week (formalized in v2)

The ramp monitor UI shows a precise week-by-week scoring status. The rules
are now formally encoded in Query 9's `scoring_status` column and enforced
at both the scoring pipeline and the UI render layer:

| Weeks since launch | `scoring_status` | `cannibal_confidence` | UI badge | UI ramp ribbon |
|---|---|---|---|---|
| 1–6 | `SUPPRESSED` | n/a (not scored) | "Ramp · no score" | "RAMP WEEK N of 13 · Cannibalization scoring suppressed" |
| 7–8 | `LOW_CONFIDENCE` | `Low` | "Active · Low confidence" | "RAMP WEEK N of 13 · Early signal · Low confidence" |
| 9–12 | `ACTIVE` | `Medium` (data-dependent) | "Active" | "RAMP WEEK N of 13 · Signal maturing" |
| 13+ | `ACTIVE` | `Medium` or `High` | Standard badge | "RAMP WEEK N of 13 · Scoring fully active" |

The SKU Summary screen's ramp ribbon reads from `scoring_status` and
`weeks_since_launch` in `new_product_ramp_monitor` and renders the appropriate
text. The ramp ribbon is hidden once `weeks_since_launch > 16` (item ages out
of the ramp monitor).

### Underperforming vs. still-ramping distinction

The ramp monitor screen (v2) distinguishes two late-stage patterns that the
`underperforming_flag` in Query 9 captures:

- **STABLE + declining velocity** (`distribution_trend = 'STABLE'`, `underperforming_flag = TRUE`):
  "Launch underperforming" event fires. TDP has plateaued; velocity still falling.
  This is a genuine demand weakness signal, not a ramp artifact.

- **DECLINING distribution** (`distribution_trend = 'DECLINING'`, `underperforming_flag = TRUE`):
  TDP peaked and is now contracting (retailer cutting space). Also fires
  "Launch underperforming" but with a different interpretation note in the
  event sub-text: "TDP peaked at [peak_tdp], now declining."

Both patterns are shown in the Ramp Monitor's two-column card section below
the main table, keyed to specific SKUs.

### Auto-enrollment flow (unchanged from v1 except confidence ladder)

New `NEW_PACK_SIZE` UPCs auto-enroll into `pack_ladder_pairs_weekly` with
`manual_review_needed = Y`. First scoring run uses shortened pre-window
(whatever history is available, minimum 4 weeks) and assigns `LOW_CONFIDENCE`
for weeks 7–8 automatically, upgrading to `Medium` at week 9 if data quality
checks pass.

---

## Section 11. Updated Execution Order Summary

| Step | Query / Action | Output | Tool |
|---|---|---|---|
| 0 | Category extract normalization + BUILT/category filter | `built_filtered_weekly` | Druid SQL |
| 1 | Flavor/product enrichment using direct SPINS retail fields | `built_enriched_weekly` | Druid SQL + lookup |
| 2 | Comparison pair construction (dist 1–5) | `comparison_pool_weekly` | Druid SQL self-join |
| 2b | On-demand competitive pairs (dist 6) | Returned to UI directly | Druid SQL parameterized |
| 2c | Cross-flavor heatmap aggregation ★ | Returned to UI directly | Druid SQL parameterized |
| 2d | Scope bar metadata ★ | Returned to UI directly | Druid SQL parameterized |
| 3 | Focal pre/post aggregation (4 windows) ★ | `built_prepost_features` | Druid SQL |
| 4 | Donor pre/post aggregation (4 windows) ★ | `donor_prepost_features` | Druid SQL |
| 5 | Feature table + labels + incremental_share ★ | `ml_training_features` | Druid SQL or Spark |
| 6 | Rolling stats + z-scores | `event_detection_weekly` | Druid SQL (window fns) |
| 7 | New UPC detection | `new_upc_candidates` | Druid SQL |
| 8 | New UPC classification | `new_upc_classifications` | Druid SQL |
| 9 | Ramp monitoring + scoring_status ★ | `new_product_ramp_monitor` | Druid SQL |
| 10 | Train cannibalization classifier | `model_cannibal_v3.pkl` | Python / LightGBM |
| 11 | Train donor ranker | `model_ranker_v3.pkl` | Python / LightGBM |
| 12 | Train event detector | `model_event_v3.pkl` | Python / LightGBM |
| 13 | Score all focal × retail account × geography × window pairs ★ | `scored_cannibalization` | Python → Druid ingest |
| 14 | Assemble events + suppression + cross-flavor type ★ | `event_queue` | Python → Druid ingest |
| 15 | Auto-enroll new pack sizes | `pack_ladder_pairs_weekly` update | Python |
| 16 | Write NEW_PACK_SIZE events to event_queue ★ | `event_queue` | Python → Druid ingest |
| 17 | Weekly rescore trigger | Incremental update | Druid supervisor task |

★ = new or materially changed in v3

---

## Section 12. Key Design Decisions

**Why SPM / store-selling velocity and never `Units/TDP`?**
The SPINS metric shortlist explicitly flags `Units/TDP` as "Avoid in Final UX"
because users confuse it with per-store productivity. `Units/TDP` is
distribution-point-normalized (a TDP counts ACV-weighted points, not stores),
whereas `avg_weekly_units_spm` and
`avg_weekly_units_per_store_selling_per_item` map cleanly to the intuition
"is each store actually selling this?". The expanded extract lets us use
store-selling productivity directly while retaining SPM for continuity.

**Why four window sizes pre-computed rather than on-demand?**
The modal filter exposes 4w, 13w, 26w, and YTD. If window-switching triggered
a new Druid scan, latency would break the interactive feel. Pre-computing all
four in a single CASE WHEN pass (Query 3) adds ~3× to the row count of
`built_prepost_features` (~30K–150K rows total) — still trivially small.
The UI filters to the selected window at render time via a simple `WHERE window_type = ?`.

**Why `incremental_share` as a scored output rather than a label?**
`incremental_share` (focal gain / focal gain + donor loss) is not a training
target — it depends on knowing both focal and donor outcomes simultaneously,
which is only available at score time, not at label construction time for
individual pairs. It is computed deterministically in Query 5 and stored in
`scored_cannibalization` for the second score bar. The two bars together give
the user richer signal: high `cannibal_prob` + low `incremental_share` = strong
zero-sum transfer; high `cannibal_prob` + moderate `incremental_share` = partial
transfer with some genuine new demand.

**Why are cross-flavor signals (dist 3/4) now surfaced on the Priority Events page?**
The v2 UI introduced an amber event card for "Cross-flavor signal: Grasshopper Cookie
1ct declining in Texas." This is a new event type (`CROSS_FLAVOR_SIGNAL`) that the
v1 plan did not cover. The business justification: a dist-3 concurrent decline in
the same geography during the focal SKU's launch window is evidence of the same-SPINS-FLAVOR
cannibalization, not just a pack-ladder issue. Surfacing it at Medium confidence
(never High — the structural prior at dist 3 is weaker) lets the user decide
whether to investigate the Cross-flavor screen.

**Why pre-build dist 3 pairs but not dist 6?**
Dist 3 (SAME_FLAVOR_SAME_BRAND) involves a bounded set of BUILT × BUILT pairs —
at most ~91 SKUs × ~91 SKUs, constrained further by SPINS `FLAVOR`. Pre-building
this is cheap and enables the heatmap query (Query 2c) to run against materialized
data. Dist 6 (CROSS_FLAVOR_CROSS_BRAND) would involve 63 competitor brands ×
all BUILT SKUs × all geographies — an unacceptably large pre-build. Query 2b
handles dist 6 on demand in seconds because it queries against the pre-filtered
`built_enriched_weekly` table, not the 95M-row source.

**Why `competitor_tier` in `item_catalog` rather than hard-coded in the UI?**
The Competitive screen needs tier labels to sort and group results. Hard-coding
them in the UI creates a maintenance problem whenever a new competitor enters
or exits the category. Storing them in `item_catalog` means a single CSV update
propagates everywhere. The UI reads the tier from `candidate_competitor_tier`
in the Query 2b result and uses it only for display grouping — it is never a filter.

**Why denormalize `focal_description` and `donor_rank_1_description` into `scored_cannibalization`?**
The context bar and Priority Events cards need to display human-readable SKU names
without a secondary join at render time. A join against `built_enriched_weekly`
at every page load would add latency. Denormalizing five context bar fields and
two donor description fields into the scored output keeps every screen render
to a single table lookup.

**Why encode `scoring_status` in Druid (Query 9) rather than Python?**
In v1, scoring_status was computed in the Python scoring pipeline. Moving it
into Query 9's SQL means the Druid `new_product_ramp_monitor` table is the
single source of truth for ramp state. The Python pipeline reads
`scoring_status` from Druid rather than recomputing it, eliminating the risk
of Python and Druid disagreeing about whether a SKU is in the suppression window.
