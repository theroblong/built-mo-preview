# BUILT Cannibalization Tool — Druid Query Plan & ML Model Design

## Purpose

This document is the end-to-end technical plan for preparing data from the 95M-row
SPINS weekly POS dataset in Apache Druid and training the machine learning models
required to power the BUILT cannibalization tool, with a specific focus on
**pack-ladder cannibalization** — how different package sizes of the same flavor
impose demand on each other across geographies over time.

---

## Section 1. Data Architecture Overview

### Source table in Druid

```
datasource: spins_weekly_pos
grain:       UPC × Geography × __time (week-ending date)
volume:      ~95M rows, ~50GB
key dims:    UPC, Geography, __time
key facts:   Units, Base_Units, Dollars, Base_Dollars, TDP, Max_ACV,
             Avg_Weekly_Units_SPM, Units_SPM, ARP, Base_ARP,
             Promo_Weeks, Incr_Units, First_Week_Selling,
             Number_of_Weeks_Selling, Pack_Count, Flavor
```

### Reference tables (load as Druid lookups or join-time CSVs)

| Table | Source | Key | Use |
|---|---|---|---|
| `flavor_mapping` | built_specific_flavor_mapping.csv | UPC | Adds `specific_flavor_normalized`, `flavor_family`, `pack_count`, `size_oz`, `brand_line` |
| `item_catalog` | Item_list_BUILT_and_Category.xlsx | UPC | Adds `Department`, `Category`, `Subcategory`, `Positioning_Group`, `Product_Type`, `Functional_Ingredient`, `Health_Focus`, `Size_Positioning` |

**Critical join key:** `UPC` (present in all three). The flavor mapping has 91 BUILT
SKUs with pack ladder data already clean. The item catalog adds competitive context
(category, subcategory) needed for the wider donor pool logic.

---

## Section 2. Comparison Pool Design — Fully Flexible, User-Driven

The tool is built around a **pool-based, parameterized** architecture. No
comparison is hard-coded. A user can set any SKU as the focal item and compare
it against any combination of:

- other pack sizes of the same flavor (pack ladder)
- other flavors within the same brand (cross-flavor, same brand)
- competitor items with the same flavor profile (cross-brand same flavor)
- competitor items in the same family (cross-brand same family)
- any arbitrary competitor brand or SKU (full competitive)

The comparison pool query (Query 2) builds all valid pairs dynamically from
the data, assigns a `relationship_distance` to each, and lets the UI filter
to whatever scope the user needs. The ML model trains on all pair types
simultaneously and uses `relationship_distance` as a feature — so it learns
that a pack-ladder pair has a higher prior cannibalization probability than
a cross-family competitive pair without needing separate models per mode.

### 2.1 The five comparison modes

| Mode | User question | focal set | comparison set | distance |
|---|---|---|---|---|
| **Pack ladder** | "Is my 4pk cannibalizing my 1ct Brownie Batter?" | One flavor, one pack size | All other pack sizes of the same specific flavor, same brand | 1 |
| **Cross-brand same flavor** | "Is a competitor's Coconut flavor pulling from BUILT Coconut?" | One BUILT flavor | Same `specific_flavor_normalized`, different brand | 2 |
| **Cross-flavor same brand** | "Is Coconut pulling from Brownie Batter within BUILT?" | One BUILT flavor | Any other BUILT specific flavor, same or different family | 3 or 5 |
| **Cross-flavor cross-brand same family** | "Is RXBAR Chocolate Chip competing with BUILT Mint Chip?" | One or more BUILT SKUs | Same `flavor_family`, different brand | 4 |
| **Full competitive** | "How is BUILT performing against BAREBELLS or QUEST overall?" | One or more BUILT SKUs | Any competitor brand(s) or specific SKUs | 6 |

All five modes are supported by the same `comparison_pool_weekly` table.
Mode selection in the UI is a filter operation, not a different query.

### 2.2 Comparison type taxonomy

Every (focal_upc, candidate_upc, geography, week_end) pair is assigned one
of six `comparison_type` values and a corresponding `relationship_distance`.

| comparison_type | distance | Definition |
|---|---|---|
| `SAME_FLAVOR_SAME_BRAND_PACK_LADDER` | 1 | Same `specific_flavor_normalized` + same brand line + different `pack_count`. Tightest substitution — a shopper choosing between a 1ct and 4pk of the exact same item. |
| `SAME_FLAVOR_CROSS_BRAND` | 2 | Same `specific_flavor_normalized`, different brand. E.g. BUILT Coconut vs. a competitor Coconut bar. Flavor identity is shared; brand loyalty is the only separator. |
| `SAME_FAMILY_SAME_BRAND` | 3 | Same `flavor_family`, same brand, different `specific_flavor_normalized`. E.g. BUILT Brownie Batter vs. BUILT Mint Chip — both Chocolate Mint family. Cross-flavor cannibalization within the BUILT portfolio. |
| `SAME_FAMILY_CROSS_BRAND` | 4 | Same `flavor_family`, different brand. E.g. BUILT Cookies N Cream vs. RXBAR Chocolate Chip. Competitive substitution within a flavor family. |
| `CROSS_FAMILY_SAME_BRAND` | 5 | Different `flavor_family`, same brand. E.g. BUILT Brownie Batter vs. BUILT Salted Caramel. Widest intra-brand comparison — driven by user curiosity about portfolio balance, not typical cannibalization. |
| `CROSS_FAMILY_CROSS_BRAND` | 6 | Different `flavor_family`, different brand. Broadest competitive view — overall brand vs. brand. Built on-demand via Query 2b, not pre-materialized. |

### 2.3 How relationship_distance drives the ML model

`relationship_distance` is a first-class ML feature, not just a filter.
It encodes the prior substitution probability structurally:

- Distance 1 (pack ladder): a shopper switching from 1ct to 4pk of the same
  item is the most direct substitution possible. The model needs minimal
  additional evidence to score this as cannibalizing.
- Distance 2 (cross-brand same flavor): strong substitution signal, modulated
  by brand loyalty and price-per-unit differences.
- Distance 3–4 (cross-flavor or cross-brand family): weaker structural prior;
  the model relies more heavily on metric signals (base units deltas, velocity
  divergence) than on the relationship itself.
- Distance 5–6: the model's prior is essentially neutral — metric evidence
  is the only signal that matters. These pairs produce incrementality context,
  not cannibalization scores.

This means a single trained model handles all five modes correctly without
mode-specific thresholds or separate model versions.

### 2.4 User-selectable focal and comparison sets in the UI

The UI exposes three progressive selection steps:

**Step 1 — Focal item selection**
The user can set the focal item at any grain:
- A single UPC (e.g. Brownie Batter 4pk)
- All pack sizes of a specific flavor (e.g. all Brownie Batter SKUs)
- All SKUs in a flavor family (e.g. all CHOCOLATE MINT SKUs)
- All BUILT SKUs (portfolio-level view)

**Step 2 — Comparison set selection**
The user selects the comparison scope from a progressive disclosure menu:

```
[ Pack sizes of this flavor only ]      → distance = 1
[ Same flavor, any brand ]              → distance ≤ 2
[ Same family, BUILT only ]             → distance = 3
[ Same family, all brands ]             → distance ≤ 4
[ All BUILT flavors ]                   → distance ≤ 5
[ Specific competitor brand(s) ]        → Query 2b on-demand
[ Full category ]                       → all distances
```

Default view on first open: **Pack sizes of this flavor only** (distance = 1).
The user explicitly widens the scope rather than being shown everything at once.

**Step 3 — Geography and channel scope**
Standard geography filters apply across all comparison modes:
- geo_type (Total US / Region / Retailer / Sub-banner)
- channel (Natural/Reg&Indep / Conventional/Mass / Convenience/Drug)
- specific retailer or banner_name

### 2.5 Known BUILT pack ladder structure (reference documentation)

The flavor mapping confirms the following multi-pack ladders. These are
documented as reference — the pipeline discovers them dynamically from the
data. No pair needs to be hard-coded.

| Specific Flavor | Brand Line | Pack Sizes Present |
|---|---|---|
| Brownie Batter | BUILT PUFF | 1ct, 4pk, 8pk, 12pk |
| Coconut | BUILT PUFF | 1ct, 4pk, 8pk, 12pk |
| Coconut | BUILT BAR | 1ct, 12pk |
| Cookies N Cream | BUILT PUFF | 1ct, 4pk, 12pk |
| Cookie Dough | BUILT PUFF | 1ct, 4pk, 12pk |
| Salted Caramel | BUILT PUFF | 1ct, 4pk, 12pk |
| Salted Caramel | BUILT BAR | 1ct, 12pk |
| Mint Chip | BUILT PUFF | 1ct, 4pk, 12pk |
| Strawberries N Cream | BUILT PUFF | 1ct, 4pk, 12pk |
| Double Chocolate | BUILT BAR | 4pk, 12pk, 16pk |
| Cookies and Cream | BUILT BAR | 1ct, 4pk |
| Coconut Almond | BUILT BAR | 1ct, 18pk |
| Banana Cream Pie | BUILT PUFF | 1ct, 12pk |
| Chocolatey Hazelnut | BUILT PUFF | 1ct, 12pk |
| Churro | BUILT PUFF | 1ct, 12pk |
| Candy Cane Brownie | BUILT PUFF | 1ct, 12pk |
| Lemon Meringue Pie | BUILT PUFF | 1ct, 4pk |

These represent the highest-signal training examples (distance = 1) and will
be the default view when a user opens any BUILT flavor in the tool.

### 2.6 Competitive universe in the category

From `All_items_extract_100.csv`, the full subcategory contains 63 brands
available for competitive comparison via Query 2b. Priority tiers by likely
shopper substitution with BUILT:

**Tier 1 — Direct protein bar competitors**
RXBAR, BAREBELLS, QUEST, PERFECT BAR, THINK!, ALOHA, NO COW, FULFIL,
PURE PROTEIN, 1ST PHORM, SIMPLYPROTEIN, NUGO NUTRITION

**Tier 2 — Better-for-you snack bar adjacents**
KIND, LARABAR, CLIF BAR, CLIF BUILDERS, GOMACRO, BOBOS, PROBAR,
MEZCLA, TOSI, ORGAIN

**Tier 3 — Mainstream / mass adjacents**
NATURE VALLEY, QUAKER CHEWY, NUTRI-GRAIN, SPECIAL K, SUNBELT,
KODIAK CAKES, NATURES BAKERY

These tiers are metadata only — not filters. A user can always select any
competitor brand regardless of tier. The tier classification surfaces in the
UI as a suggested starting point for competitive analysis, not as a constraint.

---

## Section 3. Druid Query Plan

The 95M raw rows must never be passed to the ML pipeline directly.
Druid aggregates to feature vectors first. There are **five sequential queries**,
each producing a progressively richer intermediate table that feeds the next.

---

### Query 0 — BUILT SKU filter (run once, cache result)

**Purpose:** Narrow the full 95M-row corpus to BUILT brand rows only, plus
same-subcategory competitor rows needed for context. Without this filter every
downstream query scans the full dataset unnecessarily.

```sql
-- Druid native SQL
-- Result: ~500K–2M rows depending on geography × week depth

SELECT
  __time,                          -- week-ending date (Druid time column)
  "Geography",
  "UPC",
  "Description",
  "Brand",
  "PACK COUNT"                     AS pack_count,
  "FLAVOR",
  "Units",
  "Base Units"                     AS base_units,
  "Dollars",
  "Base Dollars"                   AS base_dollars,
  "TDP",
  "Max % ACV"                      AS max_acv,
  "Average Weekly Units SPM"       AS avg_weekly_units_spm,
  "ARP",
  "Base ARP"                       AS base_arp,
  "ARP % Discount, Any Promo"      AS arp_pct_discount_any_promo,
  "Units, Promo"                   AS units_promo,
  "Units, Non-Promo"               AS units_non_promo,
  "Promo Weeks"                    AS promo_weeks,
  "Incr Units"                     AS incr_units,
  "First Week Selling"             AS first_week_selling,
  "Number of Weeks Selling"        AS number_of_weeks_selling
FROM spins_weekly_pos
WHERE
  -- BUILT brand lines
  "Brand" IN (
    'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF', 'BUILT'
  )
  -- OR same subcategory for competitive context
  OR "Subcategory" = 'WELLNESS & NUTRITION BARS'
```

**Druid implementation note:** Run with `APPROX_COUNT_DISTINCT` on Geography and
UPC first to size the result before materializing. Write result to a new Druid
segment `built_filtered_weekly` for reuse.

---

### Query 1 — Flavor-enriched weekly base table

**Purpose:** Join the filtered weekly data against the flavor mapping to attach
`specific_flavor_normalized`, `flavor_family`, and clean `pack_count` and `size_oz`
to every BUILT row. This is the foundation all downstream queries build on.

```sql
-- Input: built_filtered_weekly (from Q0) + flavor_mapping lookup

SELECT
  w.__time                              AS week_end,
  w."Geography"                         AS geography_raw,
  w."UPC"                               AS upc,
  w."Brand"                             AS brand,
  w."Description"                       AS description,
  fm.specific_flavor_normalized,
  fm.flavor_family,
  COALESCE(fm.pack_count, w."PACK COUNT") AS pack_count,
  fm.size                               AS size_oz,
  fm.unit_of_measure,
  w.base_units,
  w.units,
  w.base_dollars,
  w.dollars,
  w.tdp,
  w.max_acv,
  w.avg_weekly_units_spm,
  w.arp,
  w.base_arp,
  w.arp_pct_discount_any_promo,
  w.units_promo,
  w.units_non_promo,
  w.promo_weeks,
  w.incr_units,
  w.first_week_selling,
  w.number_of_weeks_selling,

  -- ================================================================
  -- GEOGRAPHY PARSING — covers 134+ panel types across both files:
  -- TOTAL US rollups, Standard/Census regions, RMA retailer panels,
  -- SRMA cooperative panels, sub-banners, and bare names.
  -- ================================================================

  -- 1. geo_type: top-level classification for UI filtering
  CASE
    WHEN w."Geography" LIKE 'TOTAL US%'                        THEN 'Total US'
    WHEN w."Geography" LIKE '%STANDARD REGION%'
      OR w."Geography" LIKE '%CENSUS REGION%'                  THEN 'Region'
    WHEN w."Geography" LIKE 'AFS - %'
      OR w."Geography" LIKE 'INFRA - %'
      OR w."Geography" LIKE 'HAC INC - %'
      OR w."Geography" LIKE 'MAVERIK - %'
      OR w."Geography" LIKE 'COBORNS - %'
      OR w."Geography" LIKE 'GOOD FOOD HOLDINGS - %'
      OR w."Geography" LIKE 'NORTHEAST GROCERY - %'
      OR w."Geography" LIKE 'ASSOCIATED GROCERS OF NEW ENGLAND - %'
      OR w."Geography" LIKE 'STRACK AND VAN TIL - %'
      OR w."Geography" LIKE 'NORTH STATE GROCERY - %'
      OR w."Geography" LIKE 'BROOKSHIRE BROTHERS - %'          THEN 'Sub-banner'
    ELSE                                                            'Retailer'
  END AS geo_type,

  -- 2. panel_scope: SPINS panel type
  -- RMA  = Retailer Market Area (full individual retailer panel)
  -- SRMA = Sub-Retailer Market Area (co-op, distributor, sub-fleet)
  -- Sub-banner = named store within a parent group
  -- Bare Name  = no suffix (treat as equivalent to TOTAL US for that retailer)
  CASE
    WHEN w."Geography" LIKE '% - RMA'                          THEN 'RMA'
    WHEN w."Geography" LIKE '% - SRMA'                         THEN 'SRMA'
    WHEN w."Geography" LIKE '% - TOTAL US'
      OR w."Geography" LIKE '% - TOTAL US CA'
      OR w."Geography" LIKE '% - TOTAL US X-PCC'               THEN 'TOTAL US'
    WHEN w."Geography" LIKE 'TOTAL US%'                        THEN 'TOTAL US National'
    WHEN w."Geography" LIKE '%STANDARD REGION%'
      OR w."Geography" LIKE '%CENSUS REGION%'                  THEN 'Region'
    WHEN w."Geography" NOT LIKE '% - %'                        THEN 'Bare Name'
    ELSE                                                            'Sub-banner'
  END AS panel_scope,

  -- 3. parent_group: owning corporate entity
  CASE
    WHEN w."Geography" LIKE 'AFS -%'                           THEN 'AFS (Associated Food Stores)'
    WHEN w."Geography" LIKE 'AC - ALBERTSONSCO%'               THEN 'Albertsons Companies'
    WHEN w."Geography" LIKE 'AD - AHOLD%'
      OR w."Geography" LIKE 'AD - DELHAIZE%'                   THEN 'Ahold Delhaize'
    WHEN w."Geography" LIKE 'HAC INC%'                         THEN 'HAC Inc'
    WHEN w."Geography" LIKE 'INFRA%'                           THEN 'INFRA Cooperative'
    WHEN w."Geography" LIKE 'MAVERIK%'                         THEN 'Maverik'
    WHEN w."Geography" LIKE 'STRACK AND VAN TIL%'              THEN 'Strack and Van Til'
    WHEN w."Geography" LIKE 'COBORNS%'                         THEN 'Coborns'
    WHEN w."Geography" LIKE 'GOOD FOOD HOLDINGS%'              THEN 'Good Food Holdings'
    WHEN w."Geography" LIKE 'NORTHEAST GROCERY%'               THEN 'Northeast Grocery'
    WHEN w."Geography" LIKE 'ASSOCIATED GROCERS OF NEW ENGLAND%' THEN 'AGONE'
    WHEN w."Geography" LIKE 'WALMART%'                         THEN 'Walmart'
    WHEN w."Geography" LIKE 'KROGER%'                          THEN 'Kroger'
    WHEN w."Geography" LIKE 'BP %'
      OR w."Geography" LIKE 'BP THORNTONS%'                    THEN 'BP / Thorntons'
    WHEN w."Geography" LIKE 'UNFI%'                            THEN 'UNFI / SuperValu'
    WHEN w."Geography" LIKE 'TARGET%'                          THEN 'Target'
    WHEN w."Geography" LIKE 'NORTH STATE GROCERY%'             THEN 'North State Grocery'
    WHEN w."Geography" LIKE 'BROOKSHIRE BROTHERS%'             THEN 'Brookshire Brothers'
    ELSE TRIM(SPLIT_PART(w."Geography", ' - ', 1))
  END AS parent_group,

  -- 4. banner_name: the actual operating store banner
  -- For RMA/SRMA: strip the trailing code suffix
  -- For sub-banners: last segment after final ' - '
  -- For TOTAL US: first segment (retailer name)
  -- For Bare Name: the full string
  CASE
    WHEN w."Geography" LIKE '% - RMA'
      THEN TRIM(REGEXP_REPLACE(w."Geography", '\s*-\s*RMA$', ''))
    WHEN w."Geography" LIKE '% - SRMA'
      THEN TRIM(REGEXP_REPLACE(w."Geography", '\s*-\s*SRMA$', ''))
    WHEN w."Geography" LIKE '% - TOTAL US'
      THEN TRIM(REGEXP_REPLACE(w."Geography", '\s*-\s*TOTAL US$', ''))
    WHEN w."Geography" LIKE '% - TOTAL US CA'
      THEN TRIM(REGEXP_REPLACE(w."Geography", '\s*-\s*TOTAL US CA$', ''))
    WHEN w."Geography" LIKE '% - TOTAL US X-PCC'
      THEN TRIM(REGEXP_REPLACE(w."Geography", '\s*-\s*TOTAL US X-PCC$', ''))
    -- Sub-banner groups: extract last segment (the store name)
    WHEN w."Geography" LIKE 'AFS - %'
      OR w."Geography" LIKE 'HAC INC - %'
      OR w."Geography" LIKE 'INFRA - %'
      OR w."Geography" LIKE 'MAVERIK - %'
      OR w."Geography" LIKE 'COBORNS - %'
      OR w."Geography" LIKE 'GOOD FOOD HOLDINGS - %'
      OR w."Geography" LIKE 'NORTHEAST GROCERY - %'
      OR w."Geography" LIKE 'ASSOCIATED GROCERS OF NEW ENGLAND - %'
      OR w."Geography" LIKE 'STRACK AND VAN TIL - %'
      OR w."Geography" LIKE 'NORTH STATE GROCERY - %'
      OR w."Geography" LIKE 'BROOKSHIRE BROTHERS - %'
      THEN TRIM(SPLIT_PART(w."Geography", ' - ',
            CARDINALITY(STRING_TO_ARRAY(w."Geography", ' - '))))
    ELSE TRIM(w."Geography")   -- Bare Name or Region
  END AS banner_name,

  -- 5. channel: trade channel (retailer-knowledge-based, not suffix-based)
  CASE
    WHEN w."Geography" LIKE 'MCX CONUS%'
      OR w."Geography" LIKE 'CGX CONUS%'
      OR w."Geography" LIKE 'DECA CONUS%'
      THEN 'Military'
    WHEN w."Geography" LIKE 'UNFI%'
      OR w."Geography" LIKE 'ASSOCIATED WHOLESALE GROCERS CORP%'
      THEN 'Wholesale / Distribution'
    WHEN w."Geography" LIKE 'MAVERIK%'
      OR w."Geography" LIKE 'BP %'
      OR w."Geography" LIKE 'BP THORNTONS%'
      OR w."Geography" LIKE 'LOVES CORP%'
      OR w."Geography" LIKE 'PILOT FLYING%'
      OR w."Geography" LIKE 'JACKSONS FOOD STORES%'
      OR w."Geography" LIKE 'WAWA CORP%'
      OR w."Geography" LIKE 'PLAID PANTRY%'
      OR w."Geography" LIKE 'SPINX%'
      OR w."Geography" LIKE 'FIVESTAR%'
      OR w."Geography" LIKE 'QUICKCHEK%'
      OR w."Geography" LIKE 'RUTTERS CORP%'
      OR w."Geography" LIKE 'CVS CORP%'
      OR w."Geography" LIKE 'WALGREENS%'
      OR w."Geography" LIKE 'GOOD2GO CORP%'
      THEN 'Convenience / Drug'
    WHEN w."Geography" LIKE 'WALMART%'
      OR w."Geography" LIKE 'TARGET%'
      OR w."Geography" LIKE 'KROGER%'
      OR w."Geography" LIKE 'AC - ALBERTSONSCO%'
      OR w."Geography" LIKE 'AD - AHOLD%'
      OR w."Geography" LIKE 'AD - DELHAIZE%'
      OR w."Geography" LIKE 'PUBLIX CORP%'
      OR w."Geography" LIKE 'MEIJER CORP%'
      OR w."Geography" LIKE 'GIANT EAGLE CORP%'
      OR w."Geography" LIKE 'HY-VEE%'
      OR w."Geography" LIKE 'WEGMANS CORP%'
      OR w."Geography" LIKE 'WAKEFERN%'
      OR w."Geography" LIKE 'HAC INC%'
      OR w."Geography" LIKE 'BROOKSHIRE BROTHERS%'
      THEN 'Conventional / Mass'
    -- SPINS suffix-based detection for region and Total US rows
    WHEN w."Geography" LIKE '%NAT EXP CHNL%'
      OR w."Geography" LIKE '%NATURAL EXPANDED CHANNEL%'
      OR w."Geography" LIKE '%W/O PL%'
      THEN 'Natural Expanded'
    WHEN w."Geography" LIKE '%REG AND INDEP GROC CHNL%'
      OR w."Geography" LIKE '%REGIONAL AND INDEPENDENT GROCERY CHANNEL%'
      THEN 'Regional & Independent Grocery'
    -- Default: independents, co-ops, regional specialty
    ELSE 'Natural / Reg & Indep Grocery'
  END AS channel,

  -- 6. market_region: only for region-level and Total US rows
  CASE
    WHEN w."Geography" LIKE 'TOTAL US%'
      THEN 'Total US'
    WHEN w."Geography" LIKE '%STANDARD REGION%'
      OR w."Geography" LIKE '%CENSUS REGION%'
      THEN TRIM(SPLIT_PART(w."Geography", ' - ', 1))
    ELSE NULL
  END AS market_region

FROM built_filtered_weekly w
LEFT JOIN flavor_mapping fm
  ON w."UPC" = fm.upc
WHERE
  w."Brand" IN ('BUILT BAR','BUILT PUFF','BUILT SOUR PUFF','BUILT')
```

**Output table:** `built_enriched_weekly`
**Estimated rows:** ~200K–800K (BUILT SKUs × geographies × weeks)

**Geography parse coverage across both source files (134 panels analyzed):**

| Channel | Count | Examples |
|---|---|---|
| Natural / Reg & Indep Grocery | 74 | AFS banners, INFRA co-op, Raleys, Schnucks, NCG, New Seasons, independents |
| Conventional / Mass | 34 | Walmart divisions, Kroger divisions, Albertsons, Ahold Delhaize, Publix, HyVee |
| Convenience / Drug | 16 | Maverik, BP/Thorntons, Loves, Pilot Flying J, Wawa, CVS, Walgreens |
| Wholesale / Distribution | 3 | UNFI/SuperValu, Associated Wholesale Grocers |
| Military | 3 | MCX CONUS, CGX CONUS, DECA CONUS |

**Panel scope breakdown:**

| Scope | Count | Meaning |
|---|---|---|
| TOTAL US | 48 | National rollup for a named retailer — primary UI view |
| RMA | 47 | Retailer Market Area — full individual retailer panel |
| Sub-banner | 29 | Named store within a parent group (AFS-MACEYS, MAVERIK-KUM&GO) |
| SRMA | 7 | Sub-Retailer Market Area — co-op or distributor sub-panel |
| Bare Name | 3 | No suffix (KINGS FOOD MARKETS, ROTHS FRESH MARKETS) — treat as TOTAL US |

**Key parsing decisions:**

- `AFS` (Associated Food Stores) is a cooperative with 13 entries spanning a parent panel plus 12 named sub-banners (Maceys, Ridleys, Lees, Broulims, Dans, Lins, Stokes, Atkinsons, Fresh Market, Dicks, Independents, Village Market). The `parent_group` column unifies them; `banner_name` extracts the individual store name.
- `MAVERIK - KUM & GO` is a sub-banner under Maverik after its acquisition of Kum & Go. Both roll up to parent_group = Maverik, channel = Convenience/Drug.
- `INFRA - MAMA JEANS NATURAL FOODS` and `INFRA - MAR-VAL FOOD STORES` are individual stores within the INFRA cooperative. Channel = Natural / Reg & Indep Grocery.
- `HAC INC` (Homeland, Cash Saver, County Mart) operates regional conventional grocery formats and is classified as Conventional / Mass rather than Natural / Reg & Indep.
- Bare names (`KINGS FOOD MARKETS`, `ROTHS FRESH MARKETS`, `HARDINGS FRIENDLY MARKET`) appear without any suffix — treat them as equivalent to the `TOTAL US` rollup for that retailer and deduplicate against the `-TOTAL US` version in downstream aggregations.
- `NCG - TOTAL US X-PCC` is the National Co+op Grocers panel excluding PCC Community Markets. Channel = Natural / Reg & Indep Grocery.
- Military commissaries (MCX, CGX, DECA CONUS) are excluded from cannibalization scoring — shopper behavior and distribution economics are structurally different.

---

### Query 2 — Universal comparison pool (all three modes)

**Purpose:** Build every valid (focal_upc, candidate_upc) pair across all three
comparison modes — pack ladder, cross-flavor, and competitive — in a single
self-join pass. The `comparison_type` and `relationship_distance` columns let
the UI and ML models filter to the right pool for any user question without
running separate queries per mode.

The join scope is controlled by three parameters:
- Same `specific_flavor_normalized` → pack ladder and cross-brand flavor pairs
- Same `flavor_family` → family-level substitution pairs
- Same `channel` + same `geography` → constrains competitive pairs to relevant
  retail context (a BUILT SKU in Natural Expanded should compare to competitors
  present in Natural Expanded, not Walmart)

```sql
-- Query 2: Universal comparison pool
-- One row per (focal_upc, candidate_upc, geography, week_end)
-- Covers all comparison_type values 1–6

SELECT
  f.week_end,
  f.geography_raw,
  f.geo_type,
  f.channel,
  f.banner_name,
  f.parent_group,

  -- Focal item
  f.upc                               AS focal_upc,
  f.brand                             AS focal_brand,
  f.description                       AS focal_description,
  f.specific_flavor_normalized        AS focal_flavor,
  f.flavor_family                     AS focal_flavor_family,
  f.pack_count                        AS focal_pack_count,
  f.size_oz                           AS focal_size_oz,

  -- Candidate item (potential donor or competitor)
  c.upc                               AS candidate_upc,
  c.brand                             AS candidate_brand,
  c.description                       AS candidate_description,
  c.specific_flavor_normalized        AS candidate_flavor,
  c.flavor_family                     AS candidate_flavor_family,
  c.pack_count                        AS candidate_pack_count,
  c.size_oz                           AS candidate_size_oz,

  -- Relationship classification
  CASE
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.brand                      = c.brand
     AND f.pack_count                != c.pack_count
      THEN 'SAME_FLAVOR_SAME_BRAND_PACK_LADDER'

    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.brand                     != c.brand
      THEN 'SAME_FLAVOR_CROSS_BRAND'

    WHEN f.flavor_family              = c.flavor_family
     AND f.brand                      = c.brand
     AND f.specific_flavor_normalized != c.specific_flavor_normalized
      THEN 'SAME_FAMILY_SAME_BRAND'

    WHEN f.flavor_family              = c.flavor_family
     AND f.brand                     != c.brand
      THEN 'SAME_FAMILY_CROSS_BRAND'

    WHEN f.flavor_family             != c.flavor_family
     AND f.brand                      = c.brand
      THEN 'CROSS_FAMILY_SAME_BRAND'

    ELSE 'CROSS_FAMILY_CROSS_BRAND'
  END AS comparison_type,

  -- Relationship distance (lower = stronger prior substitution probability)
  CASE
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.brand                      = c.brand
     AND f.pack_count                != c.pack_count
      THEN 1
    WHEN f.specific_flavor_normalized = c.specific_flavor_normalized
     AND f.brand                     != c.brand
      THEN 2
    WHEN f.flavor_family              = c.flavor_family
     AND f.brand                      = c.brand
     AND f.specific_flavor_normalized != c.specific_flavor_normalized
      THEN 3
    WHEN f.flavor_family              = c.flavor_family
     AND f.brand                     != c.brand
      THEN 4
    WHEN f.flavor_family             != c.flavor_family
     AND f.brand                      = c.brand
      THEN 5
    ELSE 6
  END AS relationship_distance,

  -- Pack distance (for pack-ladder pairs only; NULL otherwise)
  CASE
    WHEN f.brand = c.brand
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

  -- Candidate weekly metrics (same geography × week)
  c.base_units                        AS candidate_base_units,
  c.units                             AS candidate_units,
  c.tdp                               AS candidate_tdp,
  c.avg_weekly_units_spm              AS candidate_velocity,
  c.arp                               AS candidate_arp,
  c.promo_weeks                       AS candidate_promo_weeks,
  c.first_week_selling                AS candidate_first_week_selling,
  c.incr_units                        AS candidate_incr_units

FROM built_enriched_weekly f
JOIN built_enriched_weekly c
  ON  f.week_end    = c.week_end
  AND f.geography_raw = c.geography_raw
  AND f.upc        != c.upc             -- exclude self-join

  -- Scope control: only build pairs where at least one commonality exists,
  -- OR where both items are in the same channel (for competitive pairs).
  -- This prevents a cartesian explosion across 63 brands × all geographies.
  AND (
    -- Same specific flavor (pack ladder + cross-brand flavor)
    f.specific_flavor_normalized = c.specific_flavor_normalized

    -- Same flavor family (family-level substitution)
    OR f.flavor_family = c.flavor_family

    -- Cross-family same-brand (user-driven BUILT internal comparison)
    OR (f.brand = c.brand
        AND f.brand IN ('BUILT BAR','BUILT PUFF','BUILT SOUR PUFF','BUILT'))

    -- Cross-family competitive: same channel, focal is BUILT, candidate is competitor
    -- Limit to comparison_distance 6 only when user explicitly requests it —
    -- do NOT pre-build all 63-brand × all-geo pairs; too large.
    -- Instead, build on-demand via the scoring query (Query 2b below).
  )

WHERE
  -- At least one side must be BUILT
  (f.brand IN ('BUILT BAR','BUILT PUFF','BUILT SOUR PUFF','BUILT')
   OR c.brand IN ('BUILT BAR','BUILT PUFF','BUILT SOUR PUFF','BUILT'))

  -- Exclude military commissaries from all comparisons
  AND f.geo_type != 'Military'
```

**Output table:** `comparison_pool_weekly`
**Key columns:** `comparison_type`, `relationship_distance`, `pack_distance`,
`price_per_unit_ratio`, all focal and candidate metrics

**Row volume management:** Pre-building all six comparison types for all 95M
source rows would produce an unmanageable table. The scope control in the JOIN
limits pre-built pairs to types 1–5 (same flavor, same family, or same brand).
Type 6 (cross-family competitive) is built on-demand via Query 2b.

---

### Query 2b — On-demand competitive pool (type 6, user-triggered)

**Purpose:** When a user explicitly selects a competitor brand or SKU for
comparison in the UI, this query builds the type-6 cross-family competitive
pairs on the fly for that specific focal × competitor combination. It runs
against `built_enriched_weekly` at query time, not pre-materialized.

```sql
-- Query 2b: On-demand competitive comparison
-- Parameterized: :focal_upc, :competitor_brand, :geography, :window_weeks

SELECT
  f.week_end,
  f.geography_raw,
  f.channel,
  f.upc                               AS focal_upc,
  f.brand                             AS focal_brand,
  f.description                       AS focal_description,
  f.specific_flavor_normalized        AS focal_flavor,
  f.flavor_family                     AS focal_flavor_family,
  f.pack_count                        AS focal_pack_count,
  f.base_units                        AS focal_base_units,
  f.units                             AS focal_units,
  f.tdp                               AS focal_tdp,
  f.avg_weekly_units_spm              AS focal_velocity,
  f.arp                               AS focal_arp,

  c.upc                               AS competitor_upc,
  c.brand                             AS competitor_brand,
  c.description                       AS competitor_description,
  c.specific_flavor_normalized        AS competitor_flavor,
  c.flavor_family                     AS competitor_flavor_family,
  c.pack_count                        AS competitor_pack_count,
  c.base_units                        AS competitor_base_units,
  c.units                             AS competitor_units,
  c.tdp                               AS competitor_tdp,
  c.avg_weekly_units_spm              AS competitor_velocity,
  c.arp                               AS competitor_arp,

  'CROSS_FAMILY_CROSS_BRAND'          AS comparison_type,
  6                                   AS relationship_distance

FROM built_enriched_weekly f
JOIN built_enriched_weekly c
  ON  f.week_end      = c.week_end
  AND f.geography_raw = c.geography_raw
  AND f.channel       = c.channel      -- same channel (like-for-like)

WHERE
  f.upc              = :focal_upc
  AND c.brand        = :competitor_brand
  AND f.geography_raw IN (
    SELECT DISTINCT geography_raw
    FROM built_enriched_weekly
    WHERE upc = :focal_upc
      AND week_end >= TIMESTAMPADD(WEEK, -:window_weeks, CURRENT_TIMESTAMP)
  )
  AND f.week_end >= TIMESTAMPADD(WEEK, -:window_weeks, CURRENT_TIMESTAMP)
```

**Usage:** The UI passes `focal_upc`, `competitor_brand` (or a list of brands),
and `window_weeks`. Results are returned in seconds — this is a narrow query
against the pre-filtered `built_enriched_weekly` table, not the full 95M-row corpus.

---

### How comparison mode maps to the UI

Each user action in the tool maps to a specific filter on `comparison_pool_weekly`.
The default view always opens at distance = 1 (pack ladder). The user widens
the scope explicitly — the tool never dumps a full competitive universe on them
without being asked.

| User action / UI screen | comparison_type filter | Notes |
|---|---|---|
| Open any flavor → Pack ladder (default) | `= 'SAME_FLAVOR_SAME_BRAND_PACK_LADDER'` | Scoped to `focal_flavor` selected by user |
| Widen to same flavor, any brand | `IN ('SAME_FLAVOR_SAME_BRAND_PACK_LADDER', 'SAME_FLAVOR_CROSS_BRAND')` | Shows competitor packs of same flavor alongside BUILT packs |
| Cross-flavor within BUILT | `IN ('SAME_FAMILY_SAME_BRAND', 'CROSS_FAMILY_SAME_BRAND')` | User picks one or more BUILT flavors to compare against |
| Cross-flavor, include competitors in same family | `IN ('SAME_FAMILY_SAME_BRAND', 'SAME_FAMILY_CROSS_BRAND')` | Adds competitor items sharing the same flavor family |
| Specific competitor brand comparison | Query 2b on-demand | User selects brand(s) from dropdown; any family allowed |
| Analyst / full category view | All types, order by `relationship_distance ASC` | Sorted so tightest pairs surface first |

**Default focal item** is always the BUILT SKU. The comparison set is always
on the right-hand side. The ML score always answers: "is the focal SKU gaining
at the expense of the candidates?" A user can reverse the focal/candidate
relationship for any pair by flipping the selection in the UI — the underlying
data supports both directions because pairs are stored bidirectionally in
`comparison_pool_weekly` (focal A / candidate B AND focal B / candidate A).

---

### Query 3 — Pre/post window aggregation (the core training signal)

**Purpose:** For each focal SKU, compute the before/after metrics across a
configurable scoring window (default: 13 weeks pre vs. 13 weeks post a defined
event date). This produces the change-based features the ML model trains on.

The `event_date` is typically `first_week_selling` of the focal SKU (launch date),
but can also be a reset date or a distribution expansion event.

```sql
-- Step 3a: pre-window aggregates
-- Replace :focal_upc, :geography, :event_date with parameterized values
-- In production: run as a templated query over all (focal_upc, geography) pairs

SELECT
  upc,
  geography,
  specific_flavor_normalized,
  pack_count,
  'pre'                          AS window_type,
  COUNT(DISTINCT week_end)       AS weeks_in_window,
  SUM(base_units)                AS sum_base_units,
  SUM(units)                     AS sum_units,
  SUM(base_dollars)              AS sum_base_dollars,
  SUM(dollars)                   AS sum_dollars,
  AVG(tdp)                       AS avg_tdp,
  AVG(max_acv)                   AS avg_max_acv,
  AVG(avg_weekly_units_spm)      AS avg_velocity_spm,
  AVG(arp)                       AS avg_arp,
  AVG(base_arp)                  AS avg_base_arp,
  AVG(arp_pct_discount_any_promo) AS avg_promo_depth,
  SUM(promo_weeks)               AS sum_promo_weeks,
  SUM(incr_units)                AS sum_incr_units
FROM built_enriched_weekly
WHERE
  upc          = :focal_upc
  AND geography = :geography
  AND week_end >= TIMESTAMPADD(WEEK, -13, CAST(:event_date AS TIMESTAMP))
  AND week_end <  CAST(:event_date AS TIMESTAMP)
GROUP BY upc, geography, specific_flavor_normalized, pack_count

-- Step 3b: post-window aggregates (same structure, different WHERE)
-- ...
  AND week_end >= CAST(:event_date AS TIMESTAMP)
  AND week_end <  TIMESTAMPADD(WEEK, +13, CAST(:event_date AS TIMESTAMP))
```

**Production approach:** Do not parameterize per-SKU. Instead run as a single
grouped query using `CASE WHEN` window logic:

```sql
-- Production version: single pass, all focal SKUs, all geographies

SELECT
  e.upc,
  e.geography,
  e.specific_flavor_normalized,
  e.pack_count,
  fm_launch.first_week_selling    AS event_date,

  -- PRE-WINDOW (weeks -13 to -1 relative to launch)
  SUM(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -13, fm_launch.first_week_selling)
            THEN e.base_units ELSE 0 END)   AS pre_base_units,
  SUM(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -13, fm_launch.first_week_selling)
            THEN e.units ELSE 0 END)         AS pre_units,
  AVG(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -13, fm_launch.first_week_selling)
            THEN e.tdp ELSE NULL END)        AS pre_avg_tdp,
  AVG(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -13, fm_launch.first_week_selling)
            THEN e.avg_weekly_units_spm ELSE NULL END) AS pre_avg_velocity,
  AVG(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -13, fm_launch.first_week_selling)
            THEN e.arp ELSE NULL END)        AS pre_avg_arp,
  SUM(CASE WHEN e.week_end < fm_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -13, fm_launch.first_week_selling)
            THEN e.promo_weeks ELSE 0 END)   AS pre_promo_weeks,

  -- POST-WINDOW (weeks 0 to +13 relative to launch)
  SUM(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end <  TIMESTAMPADD(WEEK, +13, fm_launch.first_week_selling)
            THEN e.base_units ELSE 0 END)   AS post_base_units,
  SUM(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end <  TIMESTAMPADD(WEEK, +13, fm_launch.first_week_selling)
            THEN e.units ELSE 0 END)         AS post_units,
  AVG(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end <  TIMESTAMPADD(WEEK, +13, fm_launch.first_week_selling)
            THEN e.tdp ELSE NULL END)        AS post_avg_tdp,
  AVG(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end <  TIMESTAMPADD(WEEK, +13, fm_launch.first_week_selling)
            THEN e.avg_weekly_units_spm ELSE NULL END) AS post_avg_velocity,
  AVG(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end <  TIMESTAMPADD(WEEK, +13, fm_launch.first_week_selling)
            THEN e.arp ELSE NULL END)        AS post_avg_arp,
  SUM(CASE WHEN e.week_end >= fm_launch.first_week_selling
            AND e.week_end <  TIMESTAMPADD(WEEK, +13, fm_launch.first_week_selling)
            THEN e.promo_weeks ELSE 0 END)   AS post_promo_weeks

FROM built_enriched_weekly e
-- Join to get each focal SKU's launch date
JOIN (
  SELECT upc, MIN(first_week_selling) AS first_week_selling
  FROM built_enriched_weekly
  WHERE first_week_selling IS NOT NULL
  GROUP BY upc
) fm_launch ON e.upc = fm_launch.upc
GROUP BY
  e.upc, e.geography, e.specific_flavor_normalized,
  e.pack_count, fm_launch.first_week_selling
```

**Output table:** `built_prepost_features`
**Estimated rows:** ~BUILT SKUs × geographies = ~10K–50K rows (very manageable)

---

### Query 4 — Donor pre/post aggregation (parallel to Query 3)

**Purpose:** Same window logic as Query 3 but applied to each **donor SKU**
in each pack ladder pair, keyed to the **focal SKU's** launch date.
This gives us the donor-side change features.

```sql
SELECT
  p.focal_upc,
  p.donor_upc,
  p.geography,
  p.specific_flavor_normalized,
  p.focal_pack_count,
  p.donor_pack_count,
  p.pack_distance,

  -- DONOR PRE-WINDOW metrics (keyed to focal launch date)
  SUM(CASE WHEN e.week_end < focal_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -13, focal_launch.first_week_selling)
            THEN e.base_units ELSE 0 END)   AS donor_pre_base_units,
  SUM(CASE WHEN e.week_end < focal_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -13, focal_launch.first_week_selling)
            THEN e.units ELSE 0 END)         AS donor_pre_units,
  AVG(CASE WHEN e.week_end < focal_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -13, focal_launch.first_week_selling)
            THEN e.tdp ELSE NULL END)        AS donor_pre_avg_tdp,
  AVG(CASE WHEN e.week_end < focal_launch.first_week_selling
            AND e.week_end >= TIMESTAMPADD(WEEK, -13, focal_launch.first_week_selling)
            THEN e.avg_weekly_units_spm ELSE NULL END) AS donor_pre_avg_velocity,

  -- DONOR POST-WINDOW metrics
  SUM(CASE WHEN e.week_end >= focal_launch.first_week_selling
            AND e.week_end <  TIMESTAMPADD(WEEK, +13, focal_launch.first_week_selling)
            THEN e.base_units ELSE 0 END)   AS donor_post_base_units,
  SUM(CASE WHEN e.week_end >= focal_launch.first_week_selling
            AND e.week_end <  TIMESTAMPADD(WEEK, +13, focal_launch.first_week_selling)
            THEN e.units ELSE 0 END)         AS donor_post_units,
  AVG(CASE WHEN e.week_end >= focal_launch.first_week_selling
            AND e.week_end <  TIMESTAMPADD(WEEK, +13, focal_launch.first_week_selling)
            THEN e.tdp ELSE NULL END)        AS donor_post_avg_tdp,
  AVG(CASE WHEN e.week_end >= focal_launch.first_week_selling
            AND e.week_end <  TIMESTAMPADD(WEEK, +13, focal_launch.first_week_selling)
            THEN e.avg_weekly_units_spm ELSE NULL END) AS donor_post_avg_velocity

FROM built_enriched_weekly e
-- Join against the pack ladder pair table to get focal/donor relationships
JOIN (
  SELECT DISTINCT focal_upc, donor_upc, geography,
                  specific_flavor_normalized,
                  focal_pack_count, donor_pack_count, pack_distance
  FROM pack_ladder_pairs_weekly
) p ON e.upc = p.donor_upc AND e.geography = p.geography
-- Get the focal SKU's launch date
JOIN (
  SELECT upc, MIN(first_week_selling) AS first_week_selling
  FROM built_enriched_weekly
  WHERE first_week_selling IS NOT NULL
  GROUP BY upc
) focal_launch ON p.focal_upc = focal_launch.upc
GROUP BY
  p.focal_upc, p.donor_upc, p.geography,
  p.specific_flavor_normalized,
  p.focal_pack_count, p.donor_pack_count, p.pack_distance
```

**Output table:** `donor_prepost_features`

---

### Query 5 — Final ML feature table assembly

**Purpose:** Join focal pre/post features (Q3) with donor pre/post features (Q4)
and compute all derived change signals. This is the final table passed to the
ML training pipeline. One row = one (focal_upc, donor_upc, geography) training
example.

```sql
SELECT
  -- Keys
  f.focal_upc,
  f.donor_upc,
  f.geography,
  f.specific_flavor_normalized,
  f.focal_pack_count,
  f.donor_pack_count,
  f.pack_distance,

  -- FOCAL CHANGE FEATURES
  SAFE_DIVIDE(f.post_base_units - f.pre_base_units,
              NULLIF(f.pre_base_units, 0))            AS focal_base_units_pct_chg,
  SAFE_DIVIDE(f.post_units - f.pre_units,
              NULLIF(f.pre_units, 0))                 AS focal_units_pct_chg,
  SAFE_DIVIDE(f.post_avg_tdp - f.pre_avg_tdp,
              NULLIF(f.pre_avg_tdp, 0))               AS focal_tdp_pct_chg,
  SAFE_DIVIDE(f.post_avg_velocity - f.pre_avg_velocity,
              NULLIF(f.pre_avg_velocity, 0))           AS focal_velocity_pct_chg,
  SAFE_DIVIDE(f.post_avg_arp - f.pre_avg_arp,
              NULLIF(f.pre_avg_arp, 0))               AS focal_arp_pct_chg,
  f.post_promo_weeks - f.pre_promo_weeks              AS focal_promo_week_delta,

  -- DONOR CHANGE FEATURES
  SAFE_DIVIDE(d.donor_post_base_units - d.donor_pre_base_units,
              NULLIF(d.donor_pre_base_units, 0))      AS donor_base_units_pct_chg,
  SAFE_DIVIDE(d.donor_post_units - d.donor_pre_units,
              NULLIF(d.donor_pre_units, 0))            AS donor_units_pct_chg,
  SAFE_DIVIDE(d.donor_post_avg_tdp - d.donor_pre_avg_tdp,
              NULLIF(d.donor_pre_avg_tdp, 0))          AS donor_tdp_pct_chg,
  SAFE_DIVIDE(d.donor_post_avg_velocity - d.donor_pre_avg_velocity,
              NULLIF(d.donor_pre_avg_velocity, 0))     AS donor_velocity_pct_chg,

  -- DIFFERENTIAL FEATURES (focal vs. donor — the core cannibalization signal)
  SAFE_DIVIDE(f.post_base_units - f.pre_base_units,
              NULLIF(f.pre_base_units, 0))
  - SAFE_DIVIDE(d.donor_post_base_units - d.donor_pre_base_units,
                NULLIF(d.donor_pre_base_units, 0))    AS base_units_delta_diff,

  SAFE_DIVIDE(f.post_avg_velocity - f.pre_avg_velocity,
              NULLIF(f.pre_avg_velocity, 0))
  - SAFE_DIVIDE(d.donor_post_avg_velocity - d.donor_pre_avg_velocity,
                NULLIF(d.donor_pre_avg_velocity, 0))  AS velocity_delta_diff,

  -- PACK LADDER CONTEXT
  f.focal_pack_count,
  d.donor_pack_count,
  f.pack_distance,
  -- Per-unit size ratio (controls for price-per-unit differences)
  SAFE_DIVIDE(f.post_avg_arp, NULLIF(f.focal_pack_count, 0))   AS focal_price_per_unit,
  SAFE_DIVIDE(d.donor_post_avg_velocity,
              NULLIF(d.donor_post_avg_tdp, 0))        AS donor_post_velocity_per_tdp,
  SAFE_DIVIDE(f.post_avg_velocity,
              NULLIF(f.post_avg_tdp, 0))              AS focal_post_velocity_per_tdp,

  -- PROMO CONTEXT (confound control)
  f.post_promo_weeks                                  AS focal_post_promo_weeks,
  d.donor_post_promo_weeks                            AS donor_post_promo_weeks,

  -- LABEL CONSTRUCTION (deterministic rule — see Section 4)
  CASE
    WHEN SAFE_DIVIDE(d.donor_post_base_units - d.donor_pre_base_units,
                     NULLIF(d.donor_pre_base_units, 0)) < -0.10
     AND SAFE_DIVIDE(f.post_base_units - f.pre_base_units,
                     NULLIF(f.pre_base_units, 0))     >  0.03
    THEN 'CANNIBALIZING'
    WHEN SAFE_DIVIDE(d.donor_post_base_units - d.donor_pre_base_units,
                     NULLIF(d.donor_pre_base_units, 0)) BETWEEN -0.10 AND -0.03
     AND SAFE_DIVIDE(f.post_base_units - f.pre_base_units,
                     NULLIF(f.pre_base_units, 0))     >  0.00
    THEN 'WATCH'
    WHEN SAFE_DIVIDE(d.donor_post_base_units - d.donor_pre_base_units,
                     NULLIF(d.donor_pre_base_units, 0)) >= -0.03
    THEN 'INCREMENTAL'
    ELSE 'NEUTRAL'
  END AS label_deterministic

FROM (
  SELECT
    fp.upc AS focal_upc,
    dp.donor_upc,
    fp.geography,
    fp.specific_flavor_normalized,
    fp.pack_count AS focal_pack_count,
    dp.donor_pack_count,
    dp.pack_distance,
    fp.pre_base_units,
    fp.post_base_units,
    fp.pre_units,
    fp.post_units,
    fp.pre_avg_tdp,
    fp.post_avg_tdp,
    fp.pre_avg_velocity,
    fp.post_avg_velocity,
    fp.pre_avg_arp,
    fp.post_avg_arp,
    fp.pre_promo_weeks,
    fp.post_promo_weeks
  FROM built_prepost_features fp
  JOIN donor_prepost_features dp
    ON fp.upc = dp.focal_upc AND fp.geography = dp.geography
) f
JOIN donor_prepost_features d
  ON f.focal_upc = d.focal_upc
  AND f.donor_upc = d.donor_upc
  AND f.geography = d.geography
```

**Output table:** `ml_training_features`
**Estimated rows:** ~50K–200K training examples (manageable for LightGBM)

---

## Section 4. Label Construction

Labels cannot be sourced directly from SPINS — they must be constructed
deterministically from the data, then used as ML training targets.

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
| `DEMAND_LED` | Focal velocity (units per TDP) rose alongside base units |
| `DISTRIBUTION_LED` | Focal TDP rose >15% but focal velocity flat or fell |
| `MIXED` | Both TDP and velocity changed but neither cleanly dominates |

### Label quality guardrails

- **Minimum weeks required:** Both pre and post windows must have ≥8 non-null weeks.
  Rows with fewer are labeled `NEUTRAL` and excluded from training.
- **Promo contamination flag:** If donor `post_promo_weeks` increased by >2 relative
  to pre, mark `promo_confounded = TRUE`. These rows train in a secondary pass only.
- **Pack distance normalization:** Weight training examples inversely by
  `pack_distance` — closer pack sizes (1ct vs. 4pk) are stronger prior signals
  than 1ct vs. 18pk.

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
| `focal_velocity_pct_chg` | Per-store demand signal — separates reach from pull |
| `donor_velocity_pct_chg` | Donor productivity — did it also lose per-store? |
| `velocity_delta_diff` | Net productivity transfer signal |
| `pack_distance` | Closer sizes cannibalise more; controls substitutability |
| `focal_price_per_unit` | Price-per-bar relationship across pack formats |
| `focal_post_promo_weeks` | Controls for promo-driven launch lift |
| `donor_post_promo_weeks` | Controls for donor promo defense activity |

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
    min_child_samples=20,   # small dataset — lower than default
    class_weight='balanced', # handle label imbalance
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
of being the primary demand source.

**Training construction:** Group by `(focal_upc, geography)`.
Within each group, rank donor SKUs by their `donor_base_units_pct_chg`
(largest decline = rank 1 = most likely donor). LambdaRank learns to reproduce
this ranking from features.

```python
import lightgbm as lgb

model_ranker = lgb.LGBMRanker(
    objective='lambdarank',
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=31,
    label_gain=[0, 1, 3, 7]   # 4-level relevance: none/minor/moderate/strong donor
)

model_ranker.fit(
    X_rank_train,
    y_rank_labels,
    group=group_sizes,        # number of donors per focal × geography group
    eval_set=[(X_rank_val, y_rank_val)],
    eval_group=[val_group_sizes]
)
```

---

### Model 3 — Significant event detector

**Type:** LightGBM binary classifier
**Purpose:** Determine whether a week-over-week or window-level metric shift
clears a statistical significance threshold worth surfacing as an event callout.

**Training target:** Construct a label using a two-sample t-test or a
bootstrap confidence interval on the pre vs. post base units distribution
for both focal and donor. Events that clear p<0.10 and practical significance
(>5% absolute change) are labeled `SIGNIFICANT=1`.

```python
from scipy import stats

def build_event_label(pre_weekly_base_units, post_weekly_base_units,
                      threshold_pct=0.05, alpha=0.10):
    if len(pre_weekly_base_units) < 4 or len(post_weekly_base_units) < 4:
        return None  # insufficient data
    t_stat, p_val = stats.ttest_ind(pre_weekly_base_units,
                                     post_weekly_base_units)
    mean_pre  = pre_weekly_base_units.mean()
    mean_post = post_weekly_base_units.mean()
    pct_chg   = (mean_post - mean_pre) / (mean_pre + 1e-9)
    if p_val < alpha and abs(pct_chg) > threshold_pct:
        return 1
    return 0
```

This requires pulling weekly-grain arrays per (focal_upc, geography, window),
which is a sixth Druid query returning the raw time series:

```sql
-- Query 5b: weekly grain for significance testing (lightweight)
SELECT
  upc, geography, week_end, base_units, units, tdp, avg_weekly_units_spm
FROM built_enriched_weekly
WHERE upc IN (<focal_upc_list>)
  AND geography IN (<geography_list>)
ORDER BY upc, geography, week_end
```

---

## Section 6. Scoring Pipeline (Druid → Model → Back to Druid)

Once trained, the models score new weeks on-demand.

### Scoring frequency
- Full rescore: weekly, triggered after the new SPINS data segment lands in Druid
- Partial rescore: on-demand per focal SKU when a user opens the tool

### Scoring flow

```
1. New week data appended to spins_weekly_pos in Druid
2. Trigger Q1 enrichment for new rows only (incremental segment)
3. Re-run Q3/Q4 for the trailing 13+13 week window for affected UPC × geo pairs
4. Recompute derived features from Q5
5. Score with model_cannibal → cannibal_prob
6. Score with model_ranker → donor_rank_1, donor_rank_2
7. Score with model_event → significant_event_flag
8. Write scores to scored_cannibalization Druid segment:
```

```sql
-- scored_cannibalization schema
CREATE TABLE scored_cannibalization (
  __time              TIMESTAMP,   -- week-ending date of scoring
  focal_upc           VARCHAR,
  geography           VARCHAR,
  specific_flavor_normalized VARCHAR,
  focal_pack_count    INTEGER,
  cannibal_prob       DOUBLE,
  cannibal_status     VARCHAR,     -- Incremental / Watch / Cannibalizing
  cannibal_confidence VARCHAR,     -- High / Medium / Low
  demand_vs_dist      VARCHAR,     -- Demand_Led / Distribution_Led / Mixed
  donor_rank_1_upc    VARCHAR,
  donor_rank_2_upc    VARCHAR,
  significant_event   BOOLEAN,
  event_label         VARCHAR,
  shap_feature_1      VARCHAR,
  shap_value_1        DOUBLE,
  shap_feature_2      VARCHAR,
  shap_value_2        DOUBLE,
  shap_feature_3      VARCHAR,
  shap_value_3        DOUBLE,
  model_version       VARCHAR,
  scored_at           TIMESTAMP
)
```

The UI joins `scored_cannibalization` with live deterministic metrics from
`built_enriched_weekly` at render time. Scores never replace raw metrics —
they are always shown alongside them.

---

## Section 7. SHAP Explainability

Every scored row must carry its top-3 SHAP drivers to power the Explanation screen.

```python
import shap

explainer = shap.TreeExplainer(model_cannibal)
shap_values = explainer.shap_values(X_score)

# For each scored row, extract top 3 contributors
import numpy as np

def top_shap_drivers(shap_row, feature_names, n=3):
    idx = np.argsort(np.abs(shap_row))[::-1][:n]
    return [(feature_names[i], float(shap_row[i])) for i in idx]

# Attach to scored output
scores['shap_drivers'] = [
    top_shap_drivers(shap_values[i], X_score.columns.tolist())
    for i in range(len(X_score))
]
```

This maps directly to the "Top drivers" bar chart in the Explanation screen and
the plain-language narrative template:

```
"{focal_description} is flagged as {status} in {geography} because
{shap_feature_1} changed by {shap_value_1_pct}% while
{donor_description} {donor_direction} over the same period."
```

---

## Section 8. Data Quality Guardrails

### Minimum evidence thresholds before scoring

| Check | Threshold | Action if fails |
|---|---|---|
| Pre-window weeks | ≥8 weeks | Label NEUTRAL, exclude from training |
| Post-window weeks | ≥8 weeks | Label NEUTRAL, exclude from training |
| Donor pre base units | >0 | Exclude pair — donor not established |
| Focal TDP post | >0 | Exclude — focal never distributed |
| Geography data coverage | ≥4 geographies per UPC | Flag as data-sparse |

### Confidence tiers

| Tier | Criteria |
|---|---|
| High | ≥12 pre-weeks, ≥10 post-weeks, ≥2 donors in pool, event p<0.05 |
| Medium | 8–12 pre-weeks OR 1 donor in pool OR p<0.10 |
| Low | <8 weeks either window, or below significance threshold |

---

## Section 9. Significant Event Detection & Outlier Flagging

This section expands on the brief treatment of Model 3 in Section 5 and covers
the full detection architecture — both the statistical layer and the rule-based
layer that determines what actually gets surfaced in the Priority Events landing page.

### 9.1 The two-layer detection design

Significant events are not produced by the ML model alone. The most reliable
design uses **two complementary layers** that must both agree before an event
is surfaced:

```
Layer 1: Statistical significance   →  did this metric shift more than noise?
Layer 2: Business rule thresholds   →  is the shift large enough to matter?
Both must fire                       →  event is surfaced with a confidence label
Either fires alone                   →  event is suppressed or downgraded to Low
```

This prevents two failure modes: surfacing statistically significant but
operationally trivial shifts (a 1% decline that cleared p<0.05 due to many weeks
of data), and surfacing large but noisy moves in thin geographies where there is
not enough data to trust the signal.

---

### 9.2 Druid query for the event detection base table

**Purpose:** Pull the rolling weekly time series needed to compute both
statistical tests and rolling baseline comparisons. This is the Query 5b
from Section 5, formalized and extended.

```sql
-- Query 6: Event detection base — rolling weekly grain with rolling stats
-- One row per UPC × Geography × week_end
-- Covering trailing 26 weeks at time of scoring

SELECT
  e.upc,
  e.geography,
  e.week_end,
  e.specific_flavor_normalized,
  e.pack_count,
  e.base_units,
  e.units,
  e.tdp,
  e.avg_weekly_units_spm                      AS velocity,
  e.arp,
  e.promo_weeks,
  e.incr_units,

  -- Rolling 4-week trailing average (smoothed baseline)
  AVG(e.base_units) OVER (
    PARTITION BY e.upc, e.geography
    ORDER BY e.week_end
    ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
  )                                            AS rolling_4w_avg_base_units,

  -- Rolling 8-week trailing average (longer baseline for outlier detection)
  AVG(e.base_units) OVER (
    PARTITION BY e.upc, e.geography
    ORDER BY e.week_end
    ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
  )                                            AS rolling_8w_avg_base_units,

  -- Rolling stddev (for z-score outlier detection)
  STDDEV(e.base_units) OVER (
    PARTITION BY e.upc, e.geography
    ORDER BY e.week_end
    ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
  )                                            AS rolling_8w_stddev_base_units,

  -- Same rolling stats for velocity
  AVG(e.avg_weekly_units_spm) OVER (
    PARTITION BY e.upc, e.geography
    ORDER BY e.week_end
    ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
  )                                            AS rolling_8w_avg_velocity,

  STDDEV(e.avg_weekly_units_spm) OVER (
    PARTITION BY e.upc, e.geography
    ORDER BY e.week_end
    ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
  )                                            AS rolling_8w_stddev_velocity,

  -- TDP rolling for distribution-led gain detection
  AVG(e.tdp) OVER (
    PARTITION BY e.upc, e.geography
    ORDER BY e.week_end
    ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
  )                                            AS rolling_8w_avg_tdp,

  -- Week-over-week changes (raw delta signals)
  e.base_units - LAG(e.base_units, 1) OVER (
    PARTITION BY e.upc, e.geography ORDER BY e.week_end
  )                                            AS base_units_wow_delta,

  e.tdp - LAG(e.tdp, 1) OVER (
    PARTITION BY e.upc, e.geography ORDER BY e.week_end
  )                                            AS tdp_wow_delta

FROM built_enriched_weekly e
WHERE e.week_end >= TIMESTAMPADD(WEEK, -26, CURRENT_TIMESTAMP)
```

**Output table:** `event_detection_weekly`
**Note:** Druid supports window functions (`OVER`) as of version 26+.
For earlier Druid versions, compute rolling stats in a Python post-processing
step after pulling the raw 26-week series.

---

### 9.3 Outlier detection — z-score method

Once `event_detection_weekly` is materialized, Python computes z-scores
to classify each week's observation as normal, watch, or outlier.

```python
import pandas as pd
import numpy as np

df = pull_from_druid("SELECT * FROM event_detection_weekly")

# Z-score for base units
df['base_units_zscore'] = (
    (df['base_units'] - df['rolling_8w_avg_base_units'])
    / df['rolling_8w_stddev_base_units'].replace(0, np.nan)
)

# Z-score for velocity
df['velocity_zscore'] = (
    (df['velocity'] - df['rolling_8w_avg_velocity'])
    / df['rolling_8w_stddev_velocity'].replace(0, np.nan)
)

# Outlier classification
def classify_outlier(z):
    if pd.isna(z):              return 'INSUFFICIENT_DATA'
    if abs(z) >= 3.0:           return 'EXTREME_OUTLIER'
    if abs(z) >= 2.0:           return 'OUTLIER'
    if abs(z) >= 1.5:           return 'WATCH'
    return 'NORMAL'

df['base_units_outlier_class'] = df['base_units_zscore'].apply(classify_outlier)
df['velocity_outlier_class']   = df['velocity_zscore'].apply(classify_outlier)

# Direction flag (up vs. down outlier)
df['base_units_outlier_dir'] = np.where(df['base_units_zscore'] > 0, 'UP', 'DOWN')
```

**Thresholds and their meaning:**

| Z-score | Classification | Typical action |
|---|---|---|
| ≥ 3.0 or ≤ −3.0 | EXTREME_OUTLIER | Always surface if practical threshold also met |
| ≥ 2.0 or ≤ −2.0 | OUTLIER | Surface if corroborated by business rule |
| ≥ 1.5 or ≤ −1.5 | WATCH | Queue for monitoring, do not surface unless persistent |
| < 1.5 | NORMAL | Suppress |

---

### 9.4 Statistical significance — two-sample t-test on windows

For pre/post launch events (not just single-week outliers), a two-sample
Welch's t-test compares the pre-launch baseline distribution against the
post-launch window distribution. This is the primary significance test for
pack-ladder cannibalization events.

```python
from scipy import stats

def test_window_significance(
        pre_series: pd.Series,
        post_series: pd.Series,
        practical_threshold_pct: float = 0.05,
        alpha: float = 0.10
) -> dict:
    """
    Returns significance result for a single (focal_upc, geography) pair.
    pre_series:  weekly base_units values in the pre-launch window
    post_series: weekly base_units values in the post-launch window
    """
    if len(pre_series) < 4 or len(post_series) < 4:
        return {'significant': False, 'reason': 'INSUFFICIENT_WEEKS',
                'p_value': None, 'pct_change': None}

    # Welch's t-test — does not assume equal variance
    t_stat, p_val = stats.ttest_ind(pre_series, post_series, equal_var=False)
    mean_pre  = pre_series.mean()
    mean_post = post_series.mean()
    pct_chg   = (mean_post - mean_pre) / (abs(mean_pre) + 1e-9)

    stat_sig   = p_val < alpha
    pract_sig  = abs(pct_chg) > practical_threshold_pct

    return {
        'significant':   stat_sig and pract_sig,
        'stat_sig_only': stat_sig and not pract_sig,
        'pct_change':    pct_chg,
        'p_value':       p_val,
        'direction':     'UP' if pct_chg > 0 else 'DOWN',
        'reason':        'BOTH' if (stat_sig and pract_sig)
                         else ('STAT_ONLY' if stat_sig
                         else ('PRACT_ONLY' if pract_sig else 'NEITHER'))
    }
```

---

### 9.5 Business rule thresholds (Layer 2)

Statistical significance alone does not make a surfaceable event.
The following business rules define the practical significance floor:

| Event type | Statistical gate | Business rule gate |
|---|---|---|
| Demand transfer detected | Focal p<0.10, donor p<0.10 | Focal base units +3%, donor base units −10% |
| Launch underperforming | Focal base units p<0.10 | TDP +15% AND velocity −5% (distribution-led) |
| Pack overlap risk elevated | Donor p<0.10 | Donor base units −5% with focal in same flavor/geo |
| Distribution-led gain | TDP p<0.10 | TDP +15% AND base units +3% AND velocity flat/down |
| Donor decline detected | Donor p<0.10 | Donor base units −10% in ≥2 geographies concurrently |
| Extreme velocity outlier | Velocity z ≥ 2.0 | Velocity deviation ≥ 25% from 8-week rolling average |

---

### 9.6 Event assembly and suppression logic

After both layers fire, events are assembled into the `event_queue` table
and filtered through a suppression step before reaching the UI.

```python
def assemble_events(scored_row: dict, sig_result: dict,
                    outlier_result: dict) -> dict | None:
    """
    Combines ML score, significance test, and outlier classification
    into a single surfaceable event record. Returns None if suppressed.
    """
    cannibal_status = scored_row['cannibal_status']   # Cannibalizing/Watch/Incremental
    cannibal_prob   = scored_row['cannibal_prob']
    sig             = sig_result['significant']
    pct_chg         = sig_result['pct_change']
    z_score         = outlier_result.get('base_units_zscore', 0)

    # --- Suppression rules ---

    # 1. Never surface if significance test failed and z-score is normal
    if not sig and abs(z_score) < 1.5:
        return None

    # 2. Never surface if ML score is below minimum threshold
    if cannibal_prob < 0.25 and cannibal_status == 'Incremental':
        return None

    # 3. Suppress promo-contaminated events unless very strong signal
    if scored_row.get('promo_confounded') and abs(z_score) < 2.5:
        return None

    # --- Confidence assignment ---
    if sig and abs(z_score) >= 2.0 and cannibal_prob >= 0.60:
        confidence = 'High'
    elif sig or abs(z_score) >= 2.0:
        confidence = 'Medium'
    else:
        confidence = 'Low'

    # --- Event label selection ---
    donor_pct_chg = scored_row.get('donor_base_units_pct_chg', 0)
    tdp_pct_chg   = scored_row.get('focal_tdp_pct_chg', 0)
    vel_pct_chg   = scored_row.get('focal_velocity_pct_chg', 0)

    if donor_pct_chg < -0.10 and pct_chg > 0.03:
        event_label = 'Significant Demand Transfer Detected'
    elif tdp_pct_chg > 0.15 and vel_pct_chg < -0.03:
        event_label = 'Distribution-Led Gain Detected'
    elif donor_pct_chg < -0.05:
        event_label = 'Pack Overlap Risk Elevated'
    elif pct_chg < -0.10 and tdp_pct_chg >= 0:
        event_label = 'Launch Underperforming in Geography'
    elif abs(z_score) >= 2.0:
        event_label = 'Velocity Outlier Detected'
    else:
        event_label = 'Watch — Monitor Before Expanding'

    return {
        'focal_upc':     scored_row['focal_upc'],
        'geography':     scored_row['geography'],
        'event_label':   event_label,
        'confidence':    confidence,
        'cannibal_prob': cannibal_prob,
        'pct_change':    pct_chg,
        'p_value':       sig_result['p_value'],
        'z_score':       z_score,
        'donor_upc':     scored_row.get('donor_rank_1_upc'),
        'shap_top_3':    scored_row.get('shap_drivers'),
        'scored_at':     scored_row['scored_at'],
        'model_version': scored_row['model_version']
    }
```

**Output table:** `event_queue` — written back to Druid as a segment,
queryable by the Priority Events landing page with a simple filter on
`confidence IN ('High', 'Medium')` and `scored_at >= CURRENT_TIMESTAMP - 7 DAYS`.

---

### 9.7 How events surface in the tool

Each event record maps directly to one card on the Priority Events landing page:

```
event_label    →  Card title
geography      →  Card subtitle geography slot
focal_upc      →  Focal SKU name (joined from built_enriched_weekly)
donor_upc      →  Donor SKU name (joined)
confidence     →  Dot color + label (High=red, Medium=amber, Low=blue)
cannibal_status →  Badge (Cannibalizing / Watch / Incremental / Neutral)
shap_top_3     →  Pre-populated into the Explanation drawer on drill-down
p_value        →  Shown in the Provenance panel as significance level
z_score        →  Shown in the Provenance panel as deviation from baseline
```

The tool never surfaces Low confidence events on the landing page.
They are available in a "View all" drill-down for analysts only.

---

## Section 10. New Product & New Pack Size Detection

This section defines how the system identifies new entries into the BUILT
assortment — both entirely new flavors and new package sizes of existing flavors
— so they can be automatically enrolled into the cannibalization monitoring pipeline
before a human notices them.

### 10.1 Why this matters

Without automated new-product detection, the tool has a blind spot:
a new 4pk of an existing flavor launches into Grocery in Texas, and the
cannibalization pipeline never fires because the focal UPC was never added
to the `flavor_mapping` lookup. Detection closes this gap.

There are two distinct detection problems with different logic:

```
Problem A: New specific flavor (net new taste/format)
           → No prior UPCs with same specific_flavor_normalized exist
           → Requires flavor taxonomy classification

Problem B: New pack size of existing flavor (pack ladder extension)
           → Same specific_flavor_normalized already has UPCs in the system
           → Detected by first appearance of a new (UPC, pack_count) pair
```

---

### 10.2 Druid query — new UPC detection

**Purpose:** Identify UPCs appearing in `spins_weekly_pos` for the first time
in the current week's data load that were not present in any prior week.
This is the entry point for both Problem A and Problem B.

```sql
-- Query 7: New UPC detection — runs weekly after each data load

SELECT
  n.upc,
  n.geography,
  n.__time                          AS first_seen_week,
  n."Brand"                         AS brand,
  n."Description"                   AS description,
  n."PACK COUNT"                    AS raw_pack_count,
  n."FLAVOR"                        AS spins_flavor,
  n."First Week Selling"            AS first_week_selling,
  n.base_units                      AS launch_week_base_units,
  n.tdp                             AS launch_week_tdp,
  -- Flag whether this UPC already exists in the flavor mapping
  CASE WHEN fm.upc IS NOT NULL THEN 'KNOWN' ELSE 'UNKNOWN' END AS flavor_map_status
FROM spins_weekly_pos n
LEFT JOIN flavor_mapping fm ON n."UPC" = fm.upc
WHERE
  n.__time = (SELECT MAX(__time) FROM spins_weekly_pos)   -- current week only
  AND n."Brand" IN ('BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF', 'BUILT')
  AND n."UPC" NOT IN (
    -- UPCs seen in any prior week
    SELECT DISTINCT "UPC"
    FROM spins_weekly_pos
    WHERE __time < (SELECT MAX(__time) FROM spins_weekly_pos)
      AND "Brand" IN ('BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF', 'BUILT')
  )
```

**Output table:** `new_upc_candidates`
**Typical volume:** 0–5 rows per weekly run for a focused brand like BUILT

---

### 10.3 New pack size detection (Problem B — the pack ladder case)

Once new UPCs are identified, the system checks whether they represent a
new pack size of an already-known flavor or an entirely new flavor.

```sql
-- Query 8: Classify new UPCs as new-pack vs. new-flavor

SELECT
  c.upc                             AS new_upc,
  c.description                     AS new_description,
  c.raw_pack_count                  AS new_pack_count,
  c.spins_flavor,
  c.first_seen_week,
  -- Does any existing BUILT UPC share the same normalized SPINS flavor?
  existing.specific_flavor_normalized,
  existing.existing_pack_counts,
  existing.existing_upc_count,
  CASE
    WHEN existing.specific_flavor_normalized IS NOT NULL
     AND c.raw_pack_count NOT IN (
           -- Unpack the existing_pack_counts array to check membership
           SELECT value FROM UNNEST(existing.existing_pack_counts) AS t(value)
         )
    THEN 'NEW_PACK_SIZE'
    WHEN existing.specific_flavor_normalized IS NOT NULL
    THEN 'DUPLICATE_OR_RELAUNCH'
    ELSE 'NEW_FLAVOR_CANDIDATE'
  END AS classification
FROM new_upc_candidates c
LEFT JOIN (
  SELECT
    spins_flavor_raw,
    specific_flavor_normalized,
    ARRAY_AGG(DISTINCT pack_count) AS existing_pack_counts,
    COUNT(DISTINCT upc)            AS existing_upc_count
  FROM flavor_mapping
  GROUP BY spins_flavor_raw, specific_flavor_normalized
) existing ON UPPER(c.spins_flavor) = UPPER(existing.spins_flavor_raw)
```

**Output table:** `new_upc_classifications`

The three classification outcomes drive different downstream actions:

| Classification | Meaning | Action |
|---|---|---|
| `NEW_PACK_SIZE` | Same flavor, new pack count seen for first time | Auto-enroll in pack ladder monitoring; flag for flavor_mapping update |
| `NEW_FLAVOR_CANDIDATE` | No matching flavor found in existing mapping | Queue for manual flavor taxonomy review; create tentative entry |
| `DUPLICATE_OR_RELAUNCH` | Same flavor AND same pack count as existing UPC | Check if prior UPC has been discontinued; merge or track as reformulation |

---

### 10.4 New product velocity ramp monitoring

New products and new pack sizes follow a ramp curve in their first 8–12 weeks
of selling. The system must distinguish between "this item is genuinely weak"
and "this item is still ramping distribution." The ramp monitoring query
tracks this weekly.

```sql
-- Query 9: New product ramp tracker
-- Covers all UPCs with first_week_selling in the trailing 16 weeks

SELECT
  e.upc,
  e.geography,
  e.week_end,
  e.specific_flavor_normalized,
  e.pack_count,
  e.tdp,
  e.base_units,
  e.avg_weekly_units_spm            AS velocity,
  e.first_week_selling,
  -- Weeks since launch (age of the SKU at this observation)
  DATEDIFF('week',
    CAST(e.first_week_selling AS DATE),
    CAST(e.week_end AS DATE))       AS weeks_since_launch,
  -- Cumulative TDP expansion since launch
  SUM(e.tdp) OVER (
    PARTITION BY e.upc, e.geography
    ORDER BY e.week_end
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  )                                 AS cumulative_tdp,
  -- Peak TDP reached so far
  MAX(e.tdp) OVER (
    PARTITION BY e.upc, e.geography
    ORDER BY e.week_end
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  )                                 AS peak_tdp,
  -- Velocity trend: current week vs. 4-week rolling avg
  e.avg_weekly_units_spm
  / NULLIF(AVG(e.avg_weekly_units_spm) OVER (
      PARTITION BY e.upc, e.geography
      ORDER BY e.week_end
      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ), 0)                           AS velocity_vs_4w_avg_ratio,
  -- Is this UPC still ramping (TDP growing week-over-week)?
  CASE
    WHEN e.tdp > LAG(e.tdp, 1) OVER (
           PARTITION BY e.upc, e.geography ORDER BY e.week_end
         ) THEN 'RAMPING'
    WHEN e.tdp = LAG(e.tdp, 1) OVER (
           PARTITION BY e.upc, e.geography ORDER BY e.week_end
         ) THEN 'STABLE'
    ELSE 'DECLINING'
  END                               AS distribution_trend
FROM built_enriched_weekly e
WHERE
  e.first_week_selling >= TIMESTAMPADD(WEEK, -16, CURRENT_TIMESTAMP)
  AND e.first_week_selling IS NOT NULL
ORDER BY e.upc, e.geography, e.week_end
```

**Output table:** `new_product_ramp_monitor`

The ramp monitor feeds two specific event types:
- **"Launch underperforming"** — fired when `weeks_since_launch >= 6`
  AND `velocity_vs_4w_avg_ratio < 0.85` AND `distribution_trend = 'STABLE'`
  (TDP has plateaued but velocity is declining — weak genuine demand)
- **"Early ramp, no clear cannibalization"** — fired when `weeks_since_launch < 6`
  AND `distribution_trend = 'RAMPING'` (too early to score; suppress cannibalization
  scoring and show neutral status)

---

### 10.5 Automatic enrollment into the cannibalization pipeline

When a new UPC is classified as `NEW_PACK_SIZE`, it is automatically enrolled
into the cannibalization monitoring pipeline without waiting for a human to update
the flavor mapping. The enrollment logic:

```python
def enroll_new_pack_size(new_upc_record: dict, flavor_mapping_df: pd.DataFrame):
    """
    Auto-enrolls a new pack size UPC into the cannibalization pipeline
    by creating a provisional flavor_mapping entry and triggering
    pair construction for all existing ladder members.
    """
    flavor = new_upc_record['specific_flavor_normalized']
    new_pack = new_upc_record['new_pack_count']
    new_upc  = new_upc_record['new_upc']

    # Find all existing ladder members for this flavor
    existing_ladder = flavor_mapping_df[
        flavor_mapping_df['specific_flavor_normalized'] == flavor
    ][['upc', 'pack_count', 'description']].to_dict('records')

    # Create provisional mapping entry (flagged for manual review)
    provisional = {
        'upc':                      new_upc,
        'specific_flavor_normalized': flavor,
        'pack_count':               new_pack,
        'manual_review_needed':     'Y',   # flag for human confirmation
        'enrolled_at':              pd.Timestamp.now(),
        'enrollment_source':        'AUTO_DETECT'
    }

    # Emit (focal, donor) pairs for this new UPC against all existing ladder members
    new_pairs = []
    for existing in existing_ladder:
        new_pairs.append({
            'focal_upc':   new_upc,
            'donor_upc':   existing['upc'],
            'pack_distance': abs(new_pack - existing['pack_count'])
        })
        # Also enroll reverse pair: existing SKU as focal, new as potential donor
        new_pairs.append({
            'focal_upc':   existing['upc'],
            'donor_upc':   new_upc,
            'pack_distance': abs(new_pack - existing['pack_count'])
        })

    return provisional, new_pairs
```

New pairs are inserted into `pack_ladder_pairs_weekly` on the next weekly
scoring run. Because the new UPC has only launch-week data, the pre/post
features use a **shortened pre-window** (whatever history is available,
minimum 4 weeks) and carry a `LOW` confidence label until 8+ post-launch weeks
accumulate.

---

### 10.6 How new product detection surfaces in the tool

New product events feed directly into the Priority Events landing page
and the SKU Summary screen with special callout logic:

**Priority Events — new product callout cards:**
- `"New Pack Size Detected — [Flavor] [Pack]ct in [Geography]"`
  → Confidence: Medium (always, until post-window data matures)
  → Recommended action: "Monitor — pre-launch cannibalization baseline being established"
  → Badge: Neutral

- `"New Flavor Launched — [Description] · Pending Taxonomy Review"`
  → Confidence: Low
  → Action: "Requires manual flavor classification before cannibalization scoring"
  → Badge: Neutral

**SKU Summary screen — ramp status ribbon:**
When a SKU is in its first 12 weeks, the summary screen shows a ramp ribbon
above the metric tiles:

```
[ RAMP WEEK 6 of 12 ]  Distribution still expanding · Cannibalization scoring
                         will activate at week 8 with available baseline data
```

This prevents users from acting on a false-alarm cannibalization score during
the ramp window when TDP expansion is the dominant driver of all metric movement.

---

## Section 11. Bonus Path — Weekly Win Counts, Probabilities, and Pairwise Association

This optional path adds the weekly win-count concept from
[brad_weekly_win_count_bonus_path.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_weekly_win_count_bonus_path.md)
to the Druid and ML workflow.

It should be treated as an **additive interpretability and pattern-detection layer**.
It does not replace the core units, dollars, base units, distribution, price,
promotion, and velocity metrics. Instead, it converts those metrics into simple
weekly true/false indicators that are easier to visualize and drill into.

### 11.1 Why this belongs in the Druid plan

The win-count layer is a natural fit for Druid because it is:

- weekly-grain
- aggregation-heavy
- easy to compute from `built_enriched_weekly`
- easy to roll up by flavor, pack ladder, brand line, geography, and channel
- useful as both a UI metric and a modeling feature

The core idea:

```text
sku_week_win = TRUE when a SKU improves versus its relevant baseline
weekly_win_count = number of related SKUs that won
weekly_win_pct = weekly_win_count / active_sku_count
```

This gives the UI a simple way to show whether related products are winning
together or whether one focal SKU is growing while the rest of the set weakens.

### 11.2 Query 10 — SKU weekly win flags

**Purpose:** Calculate a deterministic weekly win/loss/neutral flag for each
SKU in each geography using a trailing baseline.

Recommended default baseline:

- current `avg_weekly_units_spm` versus trailing 4-week average
- use `base_units` or `base_units_per_tdp` as secondary options
- carry promo and distribution flags so wins can be interpreted correctly

```sql
-- Query 10: SKU weekly win flags
-- Input: built_enriched_weekly
-- Output: sku_weekly_win_flags

WITH weekly_with_baseline AS (
  SELECT
    week_end,
    geography_raw,
    geo_type,
    channel,
    banner_name,
    parent_group,
    upc,
    brand,
    description,
    specific_flavor_normalized,
    flavor_family,
    pack_count,
    base_units,
    units,
    dollars,
    base_dollars,
    tdp,
    max_acv,
    avg_weekly_units_spm,
    arp,
    promo_weeks,
    incr_units,

    AVG(avg_weekly_units_spm) OVER (
      PARTITION BY upc, geography_raw
      ORDER BY week_end
      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS trailing_4w_avg_velocity,

    AVG(base_units) OVER (
      PARTITION BY upc, geography_raw
      ORDER BY week_end
      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS trailing_4w_avg_base_units,

    AVG(dollars) OVER (
      PARTITION BY upc, geography_raw
      ORDER BY week_end
      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS trailing_4w_avg_dollars,

    AVG(tdp) OVER (
      PARTITION BY upc, geography_raw
      ORDER BY week_end
      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS trailing_4w_avg_tdp

  FROM built_enriched_weekly
)
SELECT
  *,

  CASE
    WHEN trailing_4w_avg_velocity IS NULL THEN NULL
    WHEN avg_weekly_units_spm > trailing_4w_avg_velocity THEN TRUE
    ELSE FALSE
  END AS velocity_win_flag,

  CASE
    WHEN trailing_4w_avg_base_units IS NULL THEN NULL
    WHEN base_units > trailing_4w_avg_base_units THEN TRUE
    ELSE FALSE
  END AS base_units_win_flag,

  CASE
    WHEN trailing_4w_avg_dollars IS NULL THEN NULL
    WHEN dollars > trailing_4w_avg_dollars THEN TRUE
    ELSE FALSE
  END AS dollars_win_flag,

  CASE
    WHEN trailing_4w_avg_tdp IS NULL THEN NULL
    WHEN tdp > trailing_4w_avg_tdp * 1.15 THEN TRUE
    ELSE FALSE
  END AS distribution_jump_flag,

  CASE
    WHEN promo_weeks > 0 OR incr_units > 0 THEN TRUE
    ELSE FALSE
  END AS promo_confounded_flag,

  -- Default business-facing win flag:
  -- productivity improved, and the week is not obviously promo-only.
  CASE
    WHEN trailing_4w_avg_velocity IS NULL THEN NULL
    WHEN avg_weekly_units_spm > trailing_4w_avg_velocity
     AND NOT (promo_weeks > 0 OR incr_units > 0)
      THEN TRUE
    ELSE FALSE
  END AS sku_week_win_flag

FROM weekly_with_baseline
```

**Output table:** `sku_weekly_win_flags`

This table is deterministic and UI-safe. It can be refreshed weekly alongside
the event-detection tables.

### 11.3 Query 11 — Group weekly win counts

**Purpose:** Summarize the SKU-level win flags across a selected product group.

Useful groupings:

- same specific flavor + brand line
- same flavor family
- user-selected SKU basket
- pack ladder
- competitor comparison set
- focal item plus all comparison items from `comparison_pool_weekly`

```sql
-- Query 11: Group weekly win counts
-- Input: sku_weekly_win_flags
-- Output: group_weekly_win_counts

SELECT
  week_end,
  geography_raw,
  channel,
  specific_flavor_normalized,
  flavor_family,
  brand,

  COUNT(*) FILTER (
    WHERE sku_week_win_flag IS NOT NULL
  ) AS active_sku_count,

  COUNT(*) FILTER (
    WHERE sku_week_win_flag = TRUE
  ) AS weekly_win_count,

  COUNT(*) FILTER (
    WHERE sku_week_win_flag = FALSE
  ) AS weekly_loss_count,

  CAST(COUNT(*) FILTER (
    WHERE sku_week_win_flag = TRUE
  ) AS DOUBLE)
  / NULLIF(COUNT(*) FILTER (
    WHERE sku_week_win_flag IS NOT NULL
  ), 0) AS weekly_win_pct,

  SUM(units) AS group_units,
  SUM(dollars) AS group_dollars,
  SUM(base_units) AS group_base_units,
  AVG(avg_weekly_units_spm) AS group_avg_velocity,
  SUM(tdp) AS group_tdp

FROM sku_weekly_win_flags
GROUP BY
  week_end,
  geography_raw,
  channel,
  specific_flavor_normalized,
  flavor_family,
  brand
```

**Output table:** `group_weekly_win_counts`

**Druid syntax note:** If `FILTER` is unavailable in the target Druid SQL
version, replace each filtered count with `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`.

### 11.4 Query 12 — Focal versus comparison win association

**Purpose:** Calculate pairwise win/loss association patterns for focal and
comparison items. This creates simple, drillable statistics such as:

```text
P(comparison loses | focal wins)
co_win_rate
opposition_rate
conditional_loss_lift
```

```sql
-- Query 12: Focal/comparison weekly win association
-- Input: comparison_pool_weekly + sku_weekly_win_flags
-- Output: pairwise_win_association

WITH pair_week_flags AS (
  SELECT
    p.focal_upc,
    p.candidate_upc AS comparison_upc,
    p.comparison_type,
    p.relationship_distance,
    p.geography_raw,
    p.channel,
    p.week_end,

    f.sku_week_win_flag AS focal_win_flag,
    c.sku_week_win_flag AS comparison_win_flag,

    f.units AS focal_units,
    c.units AS comparison_units,
    f.base_units AS focal_base_units,
    c.base_units AS comparison_base_units,
    f.avg_weekly_units_spm AS focal_velocity,
    c.avg_weekly_units_spm AS comparison_velocity

  FROM comparison_pool_weekly p
  JOIN sku_weekly_win_flags f
    ON p.focal_upc = f.upc
   AND p.geography_raw = f.geography_raw
   AND p.week_end = f.week_end
  JOIN sku_weekly_win_flags c
    ON p.candidate_upc = c.upc
   AND p.geography_raw = c.geography_raw
   AND p.week_end = c.week_end
)
SELECT
  focal_upc,
  comparison_upc,
  comparison_type,
  relationship_distance,
  geography_raw,
  channel,

  COUNT(*) AS active_pair_weeks,

  SUM(CASE WHEN focal_win_flag = TRUE THEN 1 ELSE 0 END) AS focal_win_weeks,
  SUM(CASE WHEN comparison_win_flag = TRUE THEN 1 ELSE 0 END) AS comparison_win_weeks,

  SUM(CASE
        WHEN focal_win_flag = TRUE AND comparison_win_flag = TRUE THEN 1
        ELSE 0
      END) AS co_win_weeks,

  SUM(CASE
        WHEN focal_win_flag = TRUE AND comparison_win_flag = FALSE THEN 1
        ELSE 0
      END) AS focal_win_comparison_loss_weeks,

  CAST(SUM(CASE
        WHEN focal_win_flag = TRUE AND comparison_win_flag = TRUE THEN 1
        ELSE 0
      END) AS DOUBLE) / NULLIF(COUNT(*), 0) AS co_win_rate,

  CAST(SUM(CASE
        WHEN focal_win_flag = TRUE AND comparison_win_flag = FALSE THEN 1
        ELSE 0
      END) AS DOUBLE) / NULLIF(COUNT(*), 0) AS opposition_rate,

  -- P(comparison loses | focal wins)
  CAST(SUM(CASE
        WHEN focal_win_flag = TRUE AND comparison_win_flag = FALSE THEN 1
        ELSE 0
      END) AS DOUBLE)
  / NULLIF(SUM(CASE WHEN focal_win_flag = TRUE THEN 1 ELSE 0 END), 0)
    AS comparison_loss_given_focal_win,

  -- Lift versus unconditional comparison loss rate
  (
    CAST(SUM(CASE
          WHEN focal_win_flag = TRUE AND comparison_win_flag = FALSE THEN 1
          ELSE 0
        END) AS DOUBLE)
    / NULLIF(SUM(CASE WHEN focal_win_flag = TRUE THEN 1 ELSE 0 END), 0)
  )
  /
  NULLIF(
    CAST(SUM(CASE WHEN comparison_win_flag = FALSE THEN 1 ELSE 0 END) AS DOUBLE)
    / NULLIF(COUNT(*), 0),
    0
  ) AS conditional_loss_lift

FROM pair_week_flags
GROUP BY
  focal_upc,
  comparison_upc,
  comparison_type,
  relationship_distance,
  geography_raw,
  channel
```

**Output table:** `pairwise_win_association`

This table is not causal proof. It is a high-signal drill-down aid. High
`opposition_rate` or `conditional_loss_lift` tells the user where to inspect
deeper units, dollars, distribution, promo, and model evidence.

### 11.5 ML feature additions

The win-count layer can feed the existing LightGBM models as additional features:

| Feature | Use |
|---|---|
| `focal_recent_win_rate_4w` | Momentum of the focal SKU |
| `comparison_recent_win_rate_4w` | Momentum of the candidate/donor SKU |
| `group_weekly_win_pct` | Whether the broader group is healthy |
| `related_loss_pct_when_focal_wins` | Simple cannibalization pattern signal |
| `co_win_rate` | Complementarity signal |
| `opposition_rate` | Substitution or cannibalization signal |
| `conditional_loss_lift` | Pairwise association signal |
| `win_concentration_ratio` | Whether gains are concentrated in one SKU |

These features are especially useful for:

- donor ranking
- event callouts
- watch-list prioritization
- UI explanation text
- Bayesian or neural-network extensions

### 11.6 Bayesian extension

The win-count layer is naturally compatible with a binomial/Beta-binomial
Bayesian model:

```text
weekly_win_count ~ Binomial(active_sku_count, portfolio_health_probability)
```

Potential outputs:

- probability a SKU group is broadly healthy this week
- probability focal growth is concentrated rather than broad-based
- credible intervals around win percentage for sparse geographies
- probability of related SKU loss when the focal SKU wins

Recommended user-facing language:

```text
This SKU group has a 78% estimated probability of broad-based growth this week.
The credible range is 62% to 89% because only four SKUs had enough evidence.
```

### 11.7 Neural network extension

The SKU win matrix can become a compact sequence input for later-stage ML:

```text
SKU x Week matrix:
win / loss / neutral + units + dollars + TDP + promo + price
```

Potential model classes:

- sequence models for week-by-week product interaction patterns
- graph neural networks where SKUs are nodes and substitution/complementarity
  relationships are edges
- multi-task models that predict both numeric demand and win/loss state
- embeddings that learn which SKUs tend to win or lose together

This should remain a later-stage enhancement. The first implementation should
keep the win layer deterministic and visible, then use it as a feature source
for the existing LightGBM and event-detection workflows.

### 11.8 UI outputs enabled by this path

User-facing outputs should stay simple:

- `"5 of 7 SKUs won this week"`
- `"71% group win rate"`
- `"Focal SKU won while 3 related SKUs lost"`
- `"Win rate fell from 86% to 29% after the 4pk gained"`
- `"Growth is concentrated in one pack size"`

Recommended views:

- SKU win matrix
- portfolio win-count trend
- focal versus basket contribution
- drillable probability panel
- pairwise association table

This makes the cannibalization story easier to see before the user dives into
full units, dollars, TDP, price, promo, SHAP, or model-score details.

---

## Section 12. Updated Execution Order Summary

| Step | Query / Action | Output | Tool |
|---|---|---|---|
| 0 | BUILT + category filter | `built_filtered_weekly` | Druid SQL |
| 1 | Flavor enrichment join | `built_enriched_weekly` | Druid SQL + lookup |
| 2 | Pack ladder pair construction | `pack_ladder_pairs_weekly` | Druid SQL self-join |
| 3 | Focal pre/post CASE aggregation | `built_prepost_features` | Druid SQL |
| 4 | Donor pre/post aggregation | `donor_prepost_features` | Druid SQL |
| 5 | Feature table assembly + labels | `ml_training_features` | Druid SQL or Spark |
| 6 | Rolling stats + z-scores | `event_detection_weekly` | Druid SQL (window fns) |
| 7 | New UPC detection | `new_upc_candidates` | Druid SQL |
| 8 | New UPC classification | `new_upc_classifications` | Druid SQL |
| 9 | Ramp monitoring | `new_product_ramp_monitor` | Druid SQL |
| 10 | SKU weekly win flags | `sku_weekly_win_flags` | Druid SQL |
| 11 | Group weekly win counts | `group_weekly_win_counts` | Druid SQL |
| 12 | Pairwise win association | `pairwise_win_association` | Druid SQL |
| 13 | Train cannibalization classifier | `model_cannibal_v1.pkl` | Python / LightGBM |
| 14 | Train donor ranker | `model_ranker_v1.pkl` | Python / LightGBM |
| 15 | Train event detector | `model_event_v1.pkl` | Python / LightGBM |
| 16 | Optional Bayesian win-rate model | `portfolio_health_probability` | Python / Bayesian stats |
| 17 | Score all focal × geo pairs | `scored_cannibalization` | Python → Druid ingest |
| 18 | Assemble events + suppression | `event_queue` | Python → Druid ingest |
| 19 | Auto-enroll new pack sizes | `pack_ladder_pairs_weekly` update | Python |
| 20 | Weekly rescore trigger | Incremental update | Druid supervisor task |

---

## Section 13. Key Design Decisions

**Why `Base Units` rather than `Units` as the primary label signal?**
`Base Units` strips promo lift (`Units − Incr Units`). A donor SKU may appear
stable in raw `Units` while running aggressive promotions to defend share against
a new pack launch. `Base Units` surfaces the underlying demand transfer that promo
activity is masking. This distinction is central to the SPINS measures glossary
and is why the UX metric shortlist flags `Base Units` as the #1 signal.

**Why `Average Weekly Units Per Store Selling Per Item` (velocity) over `Units/TDP`?**
The SPINS glossary defines `Units/TDP` as units per total distribution point — not
per store. The UX metric shortlist explicitly marks `Units/TDP` as "Avoid in Final
UX" because users confuse it with per-store productivity. `avg_weekly_units_spm`
(Units SPM) is the distribution-normalized velocity signal used in training because
it controls for ACV properly. The UI surfaces it as "Average Weekly Units Per Store
Selling Per Item" per the shortlist guidance.

**Why pack_distance as a feature?**
A 1ct vs. 4pk pair are far more substitutable than 1ct vs. 18pk.
The 18pk is typically a warehouse club format serving a different occasion entirely.
Pack distance quantifies this directly and gives the model a structural prior on
substitution probability without requiring occasion-level data.

**Why LightGBM over a neural network?**
Training set after aggregation is ~50K–200K rows — well within tree model territory.
SHAP explanations are exact for tree models. Training runs in minutes on a single
machine. The provenance and explainability requirements of this tool are better
served by a model whose feature attributions are trustworthy, not approximate.

**Why Druid for aggregation rather than exporting raw rows to Spark?**
Exporting 50GB of raw weekly rows to Spark, S3, or a training cluster is slow,
expensive, and unnecessary. Druid's OLAP engine was built for exactly this
aggregation pattern. The CASE WHEN window approach in Query 3 runs a full
pre/post aggregation in a single Druid scan and returns a table of ~10K–50K rows —
the size the model actually needs.

**Why two layers for event detection rather than ML alone?**
A pure ML event classifier trained on historical launches will miss event types
it was never trained on — a reformulation, a shelf reset, a competitor exit.
The statistical layer (z-score + t-test) is distribution-agnostic and catches
anomalies regardless of their cause. The business rule layer ensures that only
operationally meaningful shifts reach the user. The combination gives both
sensitivity and precision.

**Why suppress cannibalization scoring during the ramp window?**
In the first 6–8 weeks post-launch, TDP is the dominant driver of virtually all
metric movement for a new pack size. Base Units, velocity, and donor metrics
all shift in this window for reasons unrelated to true cannibalization. Scoring
during the ramp period produces high false-positive rates that erode user trust
in the tool. The ramp ribbon and automatic suppression prevent this while still
showing the user that monitoring is active and will activate on schedule.

**Why auto-enroll new pack sizes rather than waiting for manual flavor mapping updates?**
Manual updates create a lag of days to weeks during which new launches go unmonitored.
For a pack-ladder cannibalization tool, the first 4–8 weeks post-launch are the most
important monitoring window. Auto-enrollment with `manual_review_needed = Y` gives
the system immediate coverage while preserving human oversight of the taxonomy.

**Why add weekly win counts if units and dollars are still the economic truth?**
Units, dollars, base units, and velocity remain the primary commercial measures.
The weekly win layer is a visualization and pattern-detection layer that makes
multi-SKU behavior easier to scan. A user can immediately understand "5 of 7 SKUs
won this week" or "the focal SKU won while 3 related SKUs lost," then drill into
the underlying unit, dollar, distribution, price, and promotion evidence. This is
especially useful for complementary product sets where the business goal is broad
group health, not just isolated SKU growth.

**Why make win counts deterministic before using Bayesian or neural-network methods?**
The first version should be auditable and easy to explain. A deterministic win flag
creates a stable signal that can power simple UI percentages, ratios, and pairwise
association metrics. Once the signal is trusted, the same win/loss sequences can
feed Bayesian probability estimates or neural-network sequence models without
turning the initial user experience into a black-box workflow.
