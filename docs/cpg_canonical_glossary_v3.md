# Canonical CPG Data Vendor Glossary
**Version:** 3.0.0  
**Last Updated:** 2026-04-06  
**Sources:** SPINS CPG Learning Center, NielsenIQ CPG Dictionary, Circana Liquid Data Go Dictionary, CPG Data Tip Sheet (cpgdatainsights.com), SPINS Market Level Measures (uploaded xlsx), Natural Language Descriptions / IRI Export Schema (uploaded docx), NielsenIQ CPG Dictionary (microsites.nielseniq.com/cpg-dictionary), SPINS SQL Export (sqllab CSV — real production column headers), Circana Druid Export (results CSV — real production column headers)

> **Purpose:** Unified reference mapping terms, definitions, formulas, and vendor aliases across SPINS, Circana (IRI), and NielsenIQ for ML model training and cross-vendor data alignment.

> **v3.0 additions:** SPINS SQL export schema (11 terms), Circana Druid export schema (13 terms), 6 new production data conflicts. **Total: 108 terms, 16 conflict records.**

---
## Table of Contents

- [Distribution Measures](#distribution) (15 terms)
- [Core Sales Metrics](#measures_metrics) (29 terms)
- [Promotions & Pricing](#promotions_pricing) (17 terms)
- [Channels & Geography](#channel_geography) (22 terms)
- [Product Hierarchy & Classification](#hierarchy_classification) (14 terms)
- [Panel & Shopper Metrics](#panel_shopper) (6 terms)
- [Product Attributes (SPINS)](#product_attributes) (5 terms)
- [Cross-Vendor Conflict Registry](#conflicts)
---

## Distribution Measures {#distribution}

### ACV `DIST_001`
**Full name:** All Commodity Volume  
**Domain:** `distribution`  **Data type:** currency (USD)  
**Reporting level:** store, retailer, market, channel  

**Definition:**  
The total annual dollar sales of all products sold through a given store or set of stores, regardless of category. Used as a size-weighting factor for stores when calculating distribution measures. A single store's ACV is the sum of all scanned sales across every category it carries.

**Formula:**  
`Sum of all dollar sales across all categories in a store (or group of stores) over a defined period`

**Example:**  
_A grocery store with $50M in annual total sales has an ACV of $50M._

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | ACV |
| Circana | ACV |
| NielsenIQ | ACV |
| legacy_IRI | ACV |
| legacy_Nielsen | Est Market ACV |

**Vendor notes / gotchas:**
- **NielsenIQ:** Also referred to as %ACV when used as a distribution measure. Total store ACV is the denominator for weighted distribution calculations.
- **SPINS:** Inherited from Circana partnership for conventional channel data; used identically.

**Tags:** `distribution` `store_size` `weighting` `foundational`

**Related terms:** DIST_002, DIST_003, DIST_007

---

### % ACV Distribution `DIST_002`
**Full name:** Percent All Commodity Volume Distribution  
**Domain:** `distribution`  **Data type:** percentage (0–100)  
**Reporting level:** item, brand, category  

**Definition:**  
The percentage of total market ACV represented by stores where a given product is sold (i.e., scanned at least once) during a defined period. Weights stores by size rather than count, so a product in large stores registers higher % ACV than one in small stores with the same count.

**Formula:**  
`ACV of stores where the product scans / Total ACV of all stores in market × 100`

**Example:**  
_A product selling in stores representing 65% of all grocery dollar volume has 65% ACV Distribution._

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | % ACV Distribution |
| Circana | % ACV Distribution |
| NielsenIQ | % ACV Distribution |
| legacy_IRI | % ACV |
| legacy_Nielsen | % ACV |

**Vendor notes / gotchas:**
- **all:** Requires at least one scan during the period to be counted as 'in distribution.' Authorization alone does not count.
- **NielsenIQ:** Not additive across products, markets, or time periods.

**Tags:** `distribution` `weighted` `foundational` `buyer_meeting`

**Related terms:** DIST_001, DIST_003, DIST_007

---

### TDP `DIST_003`
**Full name:** Total Distribution Points  
**Domain:** `distribution`  **Data type:** numeric (unbounded; 100 per item if fully distributed)  
**Reporting level:** brand, product_group, category  

**Definition:**  
The sum of the % ACV Distribution values for all individual items (SKUs) in a brand's portfolio within a market. Captures both the breadth (how many stores carry the brand) and depth (how many items per store) of distribution in a single number.

**Formula:**  
`Sum of Max % ACV for each SKU in the defined product set`

**Example:**  
_A brand with 3 SKUs each at 100% ACV has 300 TDP. If one SKU is only at 50% ACV, TDP = 250._

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | TDP |
| Circana | TDP |
| NielsenIQ | TDP |
| legacy_IRI | TDP |
| legacy_Nielsen | TDP |

**Vendor notes / gotchas:**
- **SPINS:** Illustrated as: 3 SKUs each at 100% ACV = 300 TDP.
- **NielsenIQ:** Items per store = TDP / % ACV Distribution.

**Tags:** `distribution` `portfolio` `depth` `breadth` `foundational`

**Related terms:** DIST_002, METR_003

---

### Numeric Distribution `DIST_004`
**Full name:** Numeric Distribution (% Stores Selling)  
**Domain:** `distribution`  **Data type:** percentage (0–100)  
**Reporting level:** item, brand  

**Definition:**  
The percentage of stores in a market where a product scans at least once during the defined period, counting each store equally regardless of size.

**Formula:**  
`Number of stores selling the product / Total number of stores in market × 100`

**Example:**  
_A product in 400 of 1,000 stores = 40% numeric distribution, regardless of store size._

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | % Stores Selling |
| Circana | % Stores Selling |
| NielsenIQ | % Stores Selling |
| legacy_IRI | % Stores Selling |
| legacy_Nielsen | % Stores Selling |

**Vendor notes / gotchas:**
- **all:** Contrast with % ACV Distribution which weights by store size. Numeric distribution treats a corner store equally with a Walmart Supercenter.

**Tags:** `distribution` `unweighted` `store_count`

**Related terms:** DIST_002

---

### PCV Distribution `DIST_005`
**Full name:** Product Category Volume Distribution  
**Domain:** `distribution`  **Data type:** percentage (0–100)  
**Reporting level:** item, brand  

**Definition:**  
Distribution measure weighted by the category's own dollar sales in each store, rather than total store ACV. Shows what percentage of category volume is covered by stores carrying the product.

**Formula:**  
`Category sales of stores where product scans / Total category sales across all stores × 100`

**Example:**  
_A specialty tea brand in stores representing 80% of all tea sales has 80% PCV Distribution._

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | PCV Distribution |
| Circana | PCV Distribution |
| NielsenIQ | PCV Weighted Distribution |
| legacy_Nielsen | PCV |

**Vendor notes / gotchas:**
- **NielsenIQ:** PCV stands for Product Class Value. More relevant than % ACV when category distribution within a store type varies widely.

**Tags:** `distribution` `category_weighted`

**Related terms:** DIST_002

---

### Max % ACV `DIST_006`
**Full name:** Maximum Percent ACV Distribution  
**Domain:** `distribution`  **Data type:** percentage (0–100)  
**Reporting level:** item, brand  

**Definition:**  
The highest point of % ACV distribution reached by a product at any point within the reporting period. Represents peak distribution, useful for identifying items that expanded and then contracted.

**Formula:**  
`Peak weekly % ACV observed during the defined time window`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Max % ACV |
| Circana | Max % ACV |
| NielsenIQ | Max % ACV |
| legacy_Nielsen | Max % ACV |

**Vendor notes / gotchas:**
- **SPINS:** Used in TDP calculation. Max ACV captures peak shelf presence and is preferred for TDP over average ACV.

**Tags:** `distribution` `peak` `item_health`

**Related terms:** DIST_002, DIST_003

---

### Avg % ACV `DIST_007`
**Full name:** Average Percent ACV Distribution  
**Domain:** `distribution`  **Data type:** percentage (0–100)  
**Reporting level:** item, brand  

**Definition:**  
The average of weekly % ACV Distribution values across all weeks in a reporting period. Shows how consistently a product was available—lower than Max % ACV if the product had gaps in distribution during the period.

**Formula:**  
`Sum of weekly % ACV values / Number of weeks in period`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Avg ACV |
| Circana | Avg % ACV |
| NielsenIQ | Average % ACV |

**Tags:** `distribution` `average` `consistency`

**Related terms:** DIST_002, DIST_006

---

### At-Risk Items `DIST_008`
**Full name:** At-Risk Items (Delist Risk)  
**Domain:** `distribution`  **Data type:** categorical flag / score  
**Reporting level:** item  

**Definition:**  
Products with a high probability of being removed from a retailer's assortment at the next line review. Typically identified by scoring below average on a combination of velocity, trend, and distribution metrics.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | At-Risk Items |
| Circana | At-Risk Items / Dollars at Risk |
| NielsenIQ | At-Risk Items |

**Tags:** `assortment` `delist` `item_health`

**Related terms:** DIST_002, METR_003

---

### Dropped Items `DIST_009`
**Full name:** Dropped / Discontinued Items  
**Domain:** `distribution`  **Data type:** categorical flag  
**Reporting level:** item, retailer  

**Definition:**  
Products that have been discontinued or removed from distribution in a given geography, either due to manufacturer supply chain rationalization or retailer delist decisions.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Dropped Items |
| Circana | Dropped Items |
| NielsenIQ | Dropped Items |

**Tags:** `assortment` `delist` `discontinuation`

**Related terms:** DIST_008

---

### TDP, Any Promo `DIST_010` `★v2`
**Full name:** Total Distribution Points, Any Promotion  
**Domain:** `distribution`  **Data type:** numeric  
**Reporting level:** brand  

**Definition:**  
Sum of Max % ACV across UPCs that had any promotional activity. Measures the promotional reach of a brand's portfolio — how many distribution points had at least one promotion during the period.

**Formula:**  
`Sum(Max % ACV across UPCs with any promotion)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | TDP, Any Promo |
| Circana | TDP on Promotion |
| NielsenIQ | TDP, Promoted |

**Tags:** `distribution` `promotion` `tdp`

**Related terms:** DIST_003, DIST_011

---

### TDP, Non-Promo `DIST_011` `★v2`
**Full name:** Total Distribution Points, Non-Promoted  
**Domain:** `distribution`  **Data type:** numeric  
**Reporting level:** brand  

**Definition:**  
Sum of Max % ACV across UPCs that had no promotional activity. Measures the non-promoted reach of a brand's distribution footprint.

**Formula:**  
`Sum(Max % ACV across UPCs with no promotion)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | TDP, Non-Promo |
| Circana | TDP Non-Promoted |
| NielsenIQ | TDP, Non-Promoted |

**Tags:** `distribution` `non_promoted` `tdp`

**Related terms:** DIST_003, DIST_010

---

### ACV_Weighted_Dist `SCHEMA_002` `★v2`
**Full name:** ACV Weighted Distribution (Schema Field)  
**Domain:** `distribution`  **Data type:** percentage (0–100) for ACV_Weighted_Dist; currency ($MM) for ACV_MM  
**Reporting level:** item  

**Definition:**  
The column name used in IRI/Circana data exports for the % ACV Distribution measure. Identical in meaning to % ACV Distribution. The '_MM' variant (ACV_MM) expresses the ACV of distributing stores in millions of dollars rather than as a percentage.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | ACV_Weighted_Dist (export field) |
| SPINS | % ACV Distribution |
| NielsenIQ | % ACV Distribution |

**Vendor notes / gotchas:**
- **Circana:** In IRI/Circana data exports the column is labeled 'ACV_Weighted_Dist'. The companion field 'ACV_MM' is the dollar ACV of distributing stores.
- **cross_vendor_alignment:** Map ACV_Weighted_Dist → canonical % ACV Distribution (DIST_002). Map ACV_MM → Market ACV subset (GEO_001 partial).

**Tags:** `schema_field` `IRI_export` `distribution` `mapping`

**Related terms:** DIST_002, GEO_001

---

### Items per Store `NIQ_010` `★v2`
**Domain:** `distribution`  **Data type:** numeric  
**Reporting level:** brand, category  

**Definition:**  
The average number of distinct UPCs or items selling per store within a market and product group. Measures the depth of assortment at shelf level. Calculated as TDP ÷ % ACV Distribution.

**Formula:**  
`TDP / % ACV Distribution`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Items per Store / Avg Items Carried |
| Circana | Items per Store |
| NielsenIQ | Items per Store |

**Tags:** `distribution` `depth` `assortment` `store_level`

**Related terms:** DIST_003, DIST_002

---

### '% of Stores Selling (SPINS) `SPINS_COL_011` `★v3`
**Full name:** Percent of Stores Selling — SPINS Column (note leading apostrophe)  
**Domain:** `distribution`  **Data type:** percentage (0–100)  
**Reporting level:** item, brand  

**Definition:**  
The numeric distribution measure in SPINS exports — the percentage of stores in the geography where the product scanned at least once. IMPORTANT: The column name in SPINS SQL/API exports includes a leading apostrophe character ("'% of Stores Selling") which must be handled in query parsing to avoid syntax errors. This is distinct from % ACV Distribution (DIST_002) which weights by store size.

**Formula:**  
`100 × (# Stores Selling / # Total Stores in Geography)`

**Example:**  
_Value of 1.4 means the product was selling in stores representing 1.4% of all stores in the geography_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | '% of Stores Selling (note: leading apostrophe in column name) |
| Circana | N/A (Circana uses acv_weighted_distribution, not numeric distribution, as primary column) |
| NielsenIQ | % Stores Selling |

**Vendor notes / gotchas:**
- **SPINS:** ⚠ The column header includes a leading single-quote character: "'% of Stores Selling". This is a data entry artifact in the SPINS SQL export system. Escape or strip this character in pandas (df.rename) or SQL before processing.
- **cross_vendor_alignment:** Circana's primary distribution column is 'acv_weighted_distribution' (ACV-weighted %, not store count). For a true numeric distribution equivalent from Circana, a separate calculation is required.

**Tags:** `schema_field` `SPINS_column` `distribution` `numeric_distribution` `gotcha` `leading_apostrophe`

**Related terms:** DIST_004, DIST_002

---

### acv_weighted_distribution (Circana) `CIRC_COL_003` `★v3`
**Full name:** ACV Weighted Distribution — Circana Column  
**Domain:** `distribution`  **Data type:** decimal proportion (0.0 to 1.0)  
**Reporting level:** item  

**Definition:**  
The primary distribution measure in Circana exports — equivalent to % ACV Distribution but expressed as a decimal proportion (0.0–1.0) rather than a percentage (0–100). Value of 0.015258 means the product is distributed in stores representing ~1.53% of total market ACV. Must be multiplied by 100 to match the SPINS '% of Stores Selling' scale (though note those measure different things — ACV-weighted vs. numeric).

**Formula:**  
`ACV of stores where product scans / Total Market ACV`

**Example:**  
_0.015258 → 1.53% ACV Distribution (multiply by 100)_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | acv_weighted_distribution |
| SPINS | % ACV (via Max % ACV / Avg % ACV — in percent form, not decimal) |
| NielsenIQ | % ACV Distribution (in percent form) |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** ⚠ SCALE MISMATCH: Circana 'acv_weighted_distribution' is a decimal (0–1). SPINS and NielsenIQ express % ACV as a percentage (0–100). Multiply Circana value × 100 before comparison. Also note: Circana's ACV distribution is ACV-weighted; SPINS ''% of Stores Selling' is count-weighted (numeric). These are different measures — do not equate them.
- **Circana:** The companion field 'acv_millions' is the total ACV of the geography (denominator), not the distributing stores' ACV.

**Tags:** `schema_field` `Circana_column` `distribution` `ACV` `decimal_vs_percent` `gotcha` `cross_vendor_alignment`

**Related terms:** DIST_002, DIST_004, CIRC_COL_004

---

## Core Sales Metrics {#measures_metrics}

### Dollar Sales `METR_001`
**Full name:** Dollar Sales (Retail)  
**Domain:** `measures_metrics`  **Data type:** currency (USD)  
**Reporting level:** item, brand, category, total store  

**Definition:**  
The total retail dollar value of products scanned at the register during a defined period and market. Represents consumer spending at the shelf price, not manufacturer revenue or cost.

**Formula:**  
`Units Sold × Average Retail Price`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Dollars / Dollar Sales |
| Circana | Dollar Sales |
| NielsenIQ | $ Sales |
| legacy_IRI | Dollar Sales |
| legacy_Nielsen | $ Sales |

**Vendor notes / gotchas:**
- **all:** One of five core POS facts (alongside units, price, UPC, and store location) from which all other measures derive.

**Tags:** `sales` `revenue` `foundational` `pos`

**Related terms:** METR_002, METR_004, PRCE_001

---

### Unit Sales `METR_002`
**Domain:** `measures_metrics`  **Data type:** integer  
**Reporting level:** item, brand, category  

**Definition:**  
The total number of individual product packages (each-count units, not cases) sold during a defined period and market.

**Formula:**  
`Count of scanned individual product units at register`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Units |
| Circana | Units |
| NielsenIQ | Units |
| legacy_IRI | Units |
| legacy_Nielsen | Units |

**Tags:** `sales` `volume` `foundational` `pos`

**Related terms:** METR_001, METR_004

---

### Velocity `METR_003`
**Full name:** Velocity (Sales per Point of Distribution)  
**Domain:** `measures_metrics`  **Data type:** currency per distribution point OR units per store-week  
**Reporting level:** item, brand  

**Definition:**  
A measure of how quickly a product sells relative to its distribution footprint. Normalizes sales by distribution so products in fewer stores can be compared fairly against broadly distributed items.

**Formula:**  
`Dollar Sales / TDP   OR   Dollar Sales / % ACV Distribution   OR   Units per Store per Week`

**Example:**  
_$500K in sales / 250 TDP = $2,000 per TDP velocity._

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Velocity / Sales per TDP |
| Circana | $/TDP |
| NielsenIQ | $/TDP (Dollars per TDP) / Unit Sales per MM ACV / SPPD |
| legacy_IRI | $/TDP |
| legacy_Nielsen | Sales per $MM ACV / Velocity |

**Vendor notes / gotchas:**
- **NielsenIQ:** Also expressed as 'unit sales per $MM ACV' for buyer meetings.
- **Circana:** $/TDP is the dominant form in Liquid Data outputs.
- **SPINS:** Satori platform shows velocity as Sales per TDP.

**Tags:** `velocity` `productivity` `distribution` `buyer_meeting` `foundational`

**Related terms:** DIST_003, METR_001, METR_002

---

### Market Share `METR_004`
**Domain:** `measures_metrics`  **Data type:** percentage (0–100)  
**Reporting level:** brand, manufacturer  

**Definition:**  
The percentage of total dollar (or unit) sales in a defined category, channel, and market that is held by a given brand or product.

**Formula:**  
`Brand Dollar Sales / Total Category Dollar Sales × 100`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Market Share |
| Circana | Market Share |
| NielsenIQ | Market Share / $ Share |

**Tags:** `share` `competitive` `category_management`

**Related terms:** METR_001, METR_002

---

### ARP `METR_005`
**Full name:** Average Retail Price  
**Domain:** `measures_metrics`  **Data type:** currency (USD) per unit  
**Reporting level:** item, brand  

**Definition:**  
The average price consumers actually paid at the register for a product over a defined period, blending promoted and non-promoted transactions weighted by volume.

**Formula:**  
`Total Dollar Sales / Total Units Sold`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | ARP (Average Retail Price) |
| Circana | Average Price |
| NielsenIQ | Average Price |
| legacy_Nielsen | Average Price |

**Vendor notes / gotchas:**
- **all:** Reflects the blended price across all promotions and regular price weeks, weighted by units sold.

**Tags:** `price` `average` `consumer_paid`

**Related terms:** PRCE_001, PRCE_002

---

### BDI `METR_006`
**Full name:** Brand Development Index  
**Domain:** `measures_metrics`  **Data type:** index (base 100 = national average)  
**Reporting level:** brand, market  

**Definition:**  
An index comparing a brand's share of sales in a specific market to that market's share of total US population (or ACV). Values above 100 indicate the brand over-indexes in that market; below 100 means under-index.

**Formula:**  
`% of Brand's US Sales in Market / % of US Population (or ACV) in Market × 100`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | BDI |
| Circana | BDI |
| NielsenIQ | Brand Development Index (BDI) |
| legacy_Nielsen | BDI |

**Vendor notes / gotchas:**
- **legacy_Nielsen:** Historically calculated on population; now more commonly uses ACV as denominator.
- **all:** Run on 52-week periods to eliminate seasonality. Opportunity signal: high CDI + low BDI.

**Tags:** `index` `regionality` `brand_strength`

**Related terms:** METR_007

---

### CDI `METR_007`
**Full name:** Category Development Index  
**Domain:** `measures_metrics`  **Data type:** index (base 100)  
**Reporting level:** category, market  

**Definition:**  
An index comparing a category's share of sales in a specific market to that market's share of total US population (or ACV). Identifies markets where a category is underdeveloped relative to population size.

**Formula:**  
`% of Category's US Sales in Market / % of US Population (or ACV) in Market × 100`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | CDI |
| Circana | CDI |
| NielsenIQ | Category Development Index (CDI) |
| legacy_Nielsen | CDI |

**Tags:** `index` `category` `regionality`

**Related terms:** METR_006

---

### POS Data `REPORT_001`
**Full name:** Point of Sale Data  
**Domain:** `measures_metrics`  **Data type:** transactional record  
**Reporting level:** transaction, store, item  

**Definition:**  
Transaction data captured at the checkout register when a product barcode is scanned. The five raw POS facts are: UPC, product description, dollar amount, unit quantity, and store location. All syndicated retail measures are derived from these five elements.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | POS Data / RMS (Retail Measurement Services) |
| Circana | POS Data / Retail Point of Sale |
| NielsenIQ | POS Data / Retail Measurement |

**Tags:** `data_type` `source` `foundational` `scanner` `pos`

**Related terms:** HIER_001, METR_001, METR_002

---

### Syndicated Data `REPORT_002`
**Full name:** Syndicated Retail Sales Data  
**Domain:** `measures_metrics`  **Data type:** aggregated report / data feed  

**Definition:**  
POS data aggregated from hundreds of retailers by a third-party vendor (SPINS, Circana, NielsenIQ) and sold to manufacturers and retailers as standardized reports. Enables cross-retailer performance benchmarking. Distinct from retailer direct data (one retailer only) or panel data (household-level).

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Syndicated Data / SPINS Data |
| Circana | Syndicated Data / Circana Data |
| NielsenIQ | Syndicated Data / NIQ Data |

**Tags:** `data_type` `source` `multi_retailer` `foundational`

**Related terms:** REPORT_001

---

### Category Review `REPORT_003`
**Domain:** `measures_metrics`  **Data type:** analytical deliverable / process  

**Definition:**  
A periodic data-driven assessment of how a product category is performing within a retailer or market. Typically conducted by retailer buyers and category captains to make decisions on assortment, shelf space, pricing, and promotions.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Category Review |
| Circana | Category Review |
| NielsenIQ | Category Review |

**Tags:** `category_management` `retail` `assortment` `buyer_meeting`

---

### EQ Units `METR_008` `★v2`
**Full name:** Equivalized Units  
**Domain:** `measures_metrics`  **Data type:** numeric (equivalized volume units)  
**Reporting level:** item, brand, category  

**Definition:**  
Unit sales converted to a common volume equivalent so that products of different package sizes can be compared fairly. Each unit is multiplied by its volume equivalency factor (e.g., ounces, liters) before summing. Should not be used when comparing products with different volume types (e.g., ounces vs. count items).

**Formula:**  
`Sum(Units × Volume Equivalency Factor)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | EQ Units |
| Circana | Equivalized Units / EQ Units |
| NielsenIQ | Equivalized Units / Volume |

**Vendor notes / gotchas:**
- **SPINS:** Do not use EQ Units across product sets that mix different volume types (oz vs. count).

**Tags:** `volume` `equivalized` `size_normalized` `measures`

**Related terms:** METR_002, METR_003

---

### Dollars SPM `METR_009` `★v2`
**Full name:** Dollar Sales Per $MM ACV  
**Domain:** `measures_metrics`  **Data type:** currency per $MM ACV  
**Reporting level:** item, brand  

**Definition:**  
Total dollar sales during a period per million dollars of annualized ACV of stores selling the product. Normalizes sales by the size-weighted distribution footprint, enabling comparison across geographies of different sizes. Because the denominator is always annualized (52-week ACV), do not use this measure to compare sales rates across periods of varying length.

**Formula:**  
`Dollar Sales / Sum(ACV of stores selling the product in $MM)`

**Example:**  
_$500K in sales in stores with $250MM total ACV = $2,000 per $MM ACV._

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Dollars SPM / Base Dollars SPM |
| Circana | $ per MM ACV |
| NielsenIQ | Unit Sales per $MM ACV / Sales Rate per $MM ACV |
| legacy_Nielsen | Sales per $MM ACV |

**Vendor notes / gotchas:**
- **SPINS:** Combined outlet geographies (e.g. MULO) report a weighted average of individual outlets based on all-item dollar sales. Denominator always = 52-week ACV regardless of period length.
- **NielsenIQ:** NIQ commonly expresses this in units rather than dollars for buyer meetings.

**Tags:** `velocity` `distribution_normalized` `sales_rate` `cross_geography`

**Related terms:** DIST_001, METR_001, METR_003

---

### Dollars SPP `METR_010` `★v2`
**Full name:** Dollar Sales Per Point of ACV  
**Domain:** `measures_metrics`  **Data type:** currency per ACV point  
**Reporting level:** item, brand  

**Definition:**  
Total dollar sales during a period per percentage point of Max % ACV. Controls for distribution within a single geography. Unlike SPM, SPP cannot be used to compare sales rates across geographies of different sizes.

**Formula:**  
`Dollar Sales / Max % ACV`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Dollars SPP |
| Circana | $ per Point of ACV |
| NielsenIQ | $ per Point of Distribution |

**Vendor notes / gotchas:**
- **SPINS:** Use SPM (not SPP) for cross-geography comparisons. SPP is only valid within a single geography.

**Tags:** `velocity` `distribution_normalized` `within_geography`

**Related terms:** DIST_006, METR_001, METR_009

---

### Avg Weekly Dollars Per Store Selling Per Item `METR_011` `★v2`
**Full name:** Average Weekly Dollar Sales Per Store Selling Per Item  
**Domain:** `measures_metrics`  **Data type:** currency per store per item per week  
**Reporting level:** item, brand  

**Definition:**  
Total dollar sales per store selling per item carried, averaged across weeks. Controls simultaneously for both the number of stores carrying a product and the number of distinct UPCs scanning within those stores. Useful for comparing brands with different assortment depths or geographies with different store counts.

**Formula:**  
`(Average Weekly Dollars / # Stores Selling) / (TDP / Max % ACV)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Average Weekly Dollars Per Store Selling Per Item |
| Circana | Avg Weekly $ per Store Selling per Item |
| NielsenIQ | Avg Weekly $ per Store Selling (item-adjusted) |

**Vendor notes / gotchas:**
- **SPINS:** Also available in Unit and EQ Unit variants. Most useful when comparing brands with different numbers of UPCs.

**Tags:** `velocity` `store_level` `item_adjusted` `weekly`

**Related terms:** METR_003, DIST_003, DIST_004

---

### Number of Weeks Selling `METR_012` `★v2`
**Domain:** `measures_metrics`  **Data type:** integer (weeks)  
**Reporting level:** item  

**Definition:**  
The count of distinct weeks within a reporting period in which a product recorded at least one unit of sales in the specified market. Used to assess product continuity and identify gaps in scanning (e.g., out-of-stocks, seasonal items).

**Formula:**  
`Sum across weeks (1 if Units > 0, else 0)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Number of Weeks Selling |
| Circana | Weeks Selling |
| NielsenIQ | Weeks Selling |

**Tags:** `distribution` `continuity` `item_health` `time`

---

### First Week Selling `METR_013` `★v2`
**Domain:** `measures_metrics`  **Data type:** date (week ending)  
**Reporting level:** item  

**Definition:**  
The earliest week in which a product recorded any sales anywhere in the database. Returns the same value regardless of the selected time period. If a product was selling before the database's first available week, the database start date is returned instead.

**Formula:**  
`First recorded week of sales across all available history`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | First Week Selling |
| Circana | First Week of Sales |
| NielsenIQ | First Sale Date |

**Vendor notes / gotchas:**
- **SPINS:** Value is constant across all time period selections. Cannot go earlier than the database start date.

**Tags:** `item_age` `new_item` `innovation` `time`

**Related terms:** METR_012

---

### Dollar Share, Category `SHARE_001` `★v2`
**Full name:** Dollar Market Share, Category  
**Domain:** `measures_metrics`  **Data type:** percentage (0–100)  
**Reporting level:** item, brand  

**Definition:**  
A product's or brand's total dollar sales expressed as a percentage of total category dollar sales in the same geography and period.

**Formula:**  
`100 × (Dollar Sales of selected product / Dollar Sales of Category)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Dol Shr, Category |
| Circana | $ Share, Category |
| NielsenIQ | Market Share / $ Share |

**Tags:** `share` `category` `competitive`

**Related terms:** SHARE_002, SHARE_003, METR_004

---

### Dollar Share, Sub-Category `SHARE_002` `★v2`
**Full name:** Dollar Market Share, Sub-Category  
**Domain:** `measures_metrics`  **Data type:** percentage (0–100)  
**Reporting level:** item, brand  

**Definition:**  
A product's or brand's total dollar sales expressed as a percentage of total sub-category dollar sales.

**Formula:**  
`100 × (Dollar Sales of selected product / Dollar Sales of Sub-Category)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Dol Shr, Sub-Cat |
| Circana | $ Share, Sub-Category |
| NielsenIQ | $ Share, Sub-Category |

**Tags:** `share` `sub_category` `competitive`

**Related terms:** SHARE_001, SHARE_003

---

### Dollar Share, Department `SHARE_003` `★v2`
**Full name:** Dollar Market Share, Department  
**Domain:** `measures_metrics`  **Data type:** percentage (0–100)  
**Reporting level:** item, brand  

**Definition:**  
A product's or brand's total dollar sales expressed as a percentage of total department dollar sales.

**Formula:**  
`100 × (Dollar Sales of selected product / Dollar Sales of Department)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Dol Shr, Department |
| Circana | $ Share, Department |
| NielsenIQ | $ Share, Department |

**Tags:** `share` `department` `competitive`

**Related terms:** SHARE_001, SHARE_002

---

### WeekEnding `SCHEMA_001` `★v2`
**Full name:** Week Ending Date  
**Domain:** `measures_metrics`  **Data type:** date (YYYY-MM-DD, Saturday)  
**Reporting level:** transaction, weekly  

**Definition:**  
The date of the Saturday (or last day of the measurement week) that closes a syndicated data reporting week. All major vendors (SPINS, Circana, NielsenIQ) use Saturday week endings for US retail data. Serves as the primary time key in syndicated data exports.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | WeekEnding / Period Ending |
| Circana | WeekEnding |
| NielsenIQ | Period Ending |

**Vendor notes / gotchas:**
- **all:** All US syndicated vendors use Saturday week endings. IRI/Circana historically labeled this 'WeekEnding'; NIQ uses 'Period Ending' in some extracts.

**Tags:** `time` `period` `weekly` `schema_field` `IRI_export`

---

### Hurdle Rate `NIQ_002` `★v2`
**Domain:** `measures_metrics`  **Data type:** threshold (variable by retailer)  
**Reporting level:** item, retailer  

**Definition:**  
A retailer-defined minimum performance threshold that products must meet to be stocked or retained on shelf. Products scoring below the hurdle rate on velocity, distribution, or trend are candidates for delist.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Hurdle Rate |
| Circana | Hurdle Rate |
| NielsenIQ | Hurdle Rate |

**Tags:** `assortment` `delist` `retailer` `line_review` `threshold`

**Related terms:** DIST_008, METR_003

---

### Demand Index `NIQ_009` `★v2`
**Domain:** `measures_metrics`  **Data type:** index (base 100 = perfect demographic fit)  
**Reporting level:** brand, geography  

**Definition:**  
A NielsenIQ measure estimating the expected sales of a product in a given geography based on the demographic fit between that product's known shopper profile and the demographics of the geography's shoppers. Helps identify geographies where a brand is under- or over-performing relative to demographic potential.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| NielsenIQ | Demand Index |
| SPINS | N/A |
| Circana | N/A |

**Vendor notes / gotchas:**
- **NielsenIQ:** Proprietary NIQ metric. No direct equivalent in SPINS or Circana standard outputs.

**Tags:** `index` `demographics` `opportunity` `NielsenIQ_exclusive`

**Related terms:** METR_006, METR_007

---

### Time Period / Time Period End Date (SPINS) `SPINS_COL_002` `★v3`
**Full name:** Time Period Type and End Date (SPINS Columns)  
**Domain:** `measures_metrics`  **Data type:** Time Period: categorical string; Time Period End Date: datetime (YYYY-MM-DD HH:MM:SS, always Saturday)  
**Reporting level:** weekly, periodic  

**Definition:**  
Two companion columns in SPINS exports. 'Time Period' defines the aggregation type (e.g., 'WEEK', '4 WEEK', '52 WEEK', 'YTD'). 'Time Period End Date' is the date of the last day (Saturday) in the reporting window. Together they fully define the temporal scope of each data row.

**Example:**  
_Time Period='WEEK', Time Period End Date='2022-05-29 00:00:00'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Time Period + Time Period End Date |
| Circana | __time (ISO 8601 timestamp) + week_ending_raw (human label) |
| NielsenIQ | Period + Period End Date |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** SPINS 'Time Period End Date' (YYYY-MM-DD 00:00:00) maps to Circana '__time' (ISO 8601: YYYY-MM-DDTHH:MM:SS.000Z) and 'week_ending_raw' (e.g. 'Week Ending 11-12-23'). Strip time component and normalize to YYYY-MM-DD Saturday for cross-vendor joins.
- **SPINS:** Time Period End Date always has a time of 00:00:00 — the date itself is the Saturday week-end.

**Tags:** `schema_field` `SPINS_column` `time` `period` `dimension`

**Related terms:** SCHEMA_001

---

### Dollars Per Store Selling Per Item (SPINS) `SPINS_COL_010` `★v3`
**Full name:** Dollar Sales Per Store Selling Per Item (SPINS Column)  
**Domain:** `measures_metrics`  **Data type:** currency (USD)  
**Reporting level:** item, brand  

**Definition:**  
SPINS export column measuring total dollar sales normalized by stores selling AND items (UPCs) in the period — NOT averaged across weeks. Distinct from 'Average Weekly Dollars Per Store Selling Per Item' (METR_011) which divides by week count. Used to compare product productivity controlling for both distribution breadth and depth.

**Formula:**  
`Dollar Sales / (# Stores Selling × Items per Store)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Dollars Per Store Selling Per Item |
| Circana | $ per Store per Item |
| NielsenIQ | $ per Store Selling (item-adjusted) |

**Vendor notes / gotchas:**
- **SPINS:** The weekly-averaged equivalent is 'Average Weekly Dollars per Store per Item' (column 33 in SPINS export). This non-averaged version represents the total-period figure.

**Tags:** `schema_field` `SPINS_column` `velocity` `store_level` `item_adjusted`

**Related terms:** METR_011, METR_003

---

### __time (Circana) `CIRC_COL_001` `★v3`
**Full name:** Timestamp Field — __time (Circana Column)  
**Domain:** `measures_metrics`  **Data type:** string (ISO 8601 timestamp, UTC)  
**Reporting level:** weekly  

**Definition:**  
Internal ISO 8601 timestamp column in Circana/Apache Druid exports representing the week ending date. Format: 'YYYY-MM-DDTHH:MM:SS.000Z' (UTC, always T00:00:00.000Z). The human-readable companion is 'week_ending_raw'. For date joins, normalize to YYYY-MM-DD by stripping the time component.

**Example:**  
_'2023-11-12T00:00:00.000Z' → week ending Saturday Nov 12, 2023_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | __time (Druid internal timestamp) |
| SPINS | Time Period End Date |
| NielsenIQ | Period End Date |

**Vendor notes / gotchas:**
- **Circana:** Double underscore prefix (__time) indicates this is an Apache Druid system column — the primary time dimension index. 'week_ending_raw' is the business-friendly label (e.g., 'Week Ending 11-12-23').
- **cross_vendor_alignment:** Strip 'T' and time component: '2023-11-12T00:00:00.000Z' → '2023-11-12'. Then match to SPINS 'Time Period End Date' (same Saturday date, stored as '2023-11-12 00:00:00').

**Tags:** `schema_field` `Circana_column` `time` `timestamp` `Druid` `dimension` `join_key`

**Related terms:** SCHEMA_001, SPINS_COL_002

---

### week_ending_raw (Circana) `CIRC_COL_002` `★v3`
**Full name:** Week Ending Raw Label (Circana Column)  
**Domain:** `measures_metrics`  **Data type:** string ('Week Ending MM-DD-YY')  
**Reporting level:** weekly  

**Definition:**  
Human-readable week ending label in Circana exports. Format: 'Week Ending MM-DD-YY'. Used for display purposes; use '__time' or a parsed date for programmatic joins.

**Example:**  
_'Week Ending 11-12-23'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | week_ending_raw |
| SPINS | Time Period End Date (parsed) |
| NielsenIQ | Period Label |

**Tags:** `schema_field` `Circana_column` `time` `display_label`

---

### volume_sales (Circana) `CIRC_COL_005` `★v3`
**Full name:** Volume Sales — Circana Column  
**Domain:** `measures_metrics`  **Data type:** numeric (equivalized volume)  
**Reporting level:** item, brand  

**Definition:**  
Equivalized volume sales in Circana exports — the EQ Units equivalent. Represents unit sales converted to a standardized volume measure (e.g., ounces or fluid ounces) based on each product's pack size. Equivalent to SPINS 'EQ Units'.

**Example:**  
_4.478 (ounces equivalized for a 33oz jar purchased at fractional unit sales)_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | volume_sales |
| SPINS | EQ Units |
| NielsenIQ | Equivalized Units / Volume |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** Map volume_sales (Circana) ↔ EQ Units (SPINS) ↔ Equivalized Units (NielsenIQ). Verify the volume equivalency base unit (ounces vs. lbs vs. liters) matches across products before aggregating.

**Tags:** `schema_field` `Circana_column` `EQ_units` `volume` `equivalized`

**Related terms:** METR_008

---

### dollar_sales_change_vs_ya / unit_sales_change_vs_ya (Circana) `CIRC_COL_006` `★v3`
**Full name:** Dollar / Unit Sales Change vs. Year Ago (Circana Columns)  
**Domain:** `measures_metrics`  **Data type:** numeric (absolute change in dollars/units — verify if % or absolute per feed)  
**Reporting level:** item  

**Definition:**  
Change in dollar or unit sales versus the same week in the prior year. In Circana exports these appear to be expressed as the absolute dollar/unit change (not percentage), based on the mock data values. A value of -59.70 on a $11.92 base would imply a prior-year value — confirm whether this is absolute change or percentage change in your specific extract.

**Example:**  
_dollar_sales_change_vs_ya = -59.70 (current $11.92 vs. ~$71.62 a year ago)_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | dollar_sales_change_vs_ya / unit_sales_change_vs_ya |
| SPINS | Dollar Sales % Change YA / Unit Sales % Change YA |
| NielsenIQ | $ Sales Chg YA / Unit Sales Chg YA |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** ⚠ Confirm unit (absolute vs. %) per data feed contract. In the mock data, dollar_sales_change_vs_ya = -59.70 on a current dollar_sales = 11.92, suggesting this is an absolute $ change, not a percentage.

**Tags:** `schema_field` `Circana_column` `year_over_year` `change` `verify_units`

**Related terms:** METR_001, METR_002

---

### row_count (Circana) `CIRC_COL_013` `★v3`
**Full name:** Row Count — Druid Aggregation Count (Circana Column)  
**Domain:** `measures_metrics`  **Data type:** integer  
**Reporting level:** record  

**Definition:**  
An internal Apache Druid aggregation counter indicating how many underlying source records were combined into each output row. A value of 1 indicates the row is a single atomic record. Values greater than 1 indicate rolled-up records. This is a system/ETL artifact and has no business meaning for CPG analysis; it should be dropped before model training.

**Example:**  
_1 (single record, no rollup)_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | row_count (Druid internal) |
| SPINS | N/A |
| NielsenIQ | N/A |

**Vendor notes / gotchas:**
- **Circana:** Druid system field. Drop this column in ETL preprocessing — it is not a CPG business measure.

**Tags:** `schema_field` `Circana_column` `system_field` `ETL_artifact` `drop_before_training`

---

## Promotions & Pricing {#promotions_pricing}

### Base Price `PRCE_001`
**Full name:** Base Price (Non-Promoted Price)  
**Domain:** `promotions_pricing`  **Data type:** currency (USD) per unit  
**Reporting level:** item  

**Definition:**  
The estimated regular (non-promoted) shelf price of a product. Modeled from historical scan data by removing periods of promotional activity. Serves as the reference point for measuring promotional lift and depth of discount.

**Formula:**  
`Modeled average price excluding weeks with feature, display, or price reduction activity`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Base Price |
| Circana | Base Price / Non-Promoted Price |
| NielsenIQ | Base Price |
| legacy_IRI | Non-Promoted Price |
| legacy_Nielsen | Base Price |

**Vendor notes / gotchas:**
- **legacy_Nielsen:** Modeled measure; may degrade accuracy if promotions run longer than 8 consecutive weeks.

**Tags:** `price` `baseline` `promotion` `modeling`

**Related terms:** PRCE_002, PRCE_003, PRCE_004

---

### Promoted Price `PRCE_002`
**Domain:** `promotions_pricing`  **Data type:** currency (USD) per unit  
**Reporting level:** item  

**Definition:**  
The average price paid by consumers during promotional periods (feature, display, or TPR). Contrast with base price.

**Formula:**  
`Total dollar sales during promoted weeks / Units sold during promoted weeks`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Promoted Price |
| Circana | Promoted Price |
| NielsenIQ | Promoted Price |
| legacy_Nielsen | Promoted Price |

**Tags:** `price` `promotion`

**Related terms:** PRCE_001, PRCE_003

---

### Depth of Discount `PRCE_003`
**Domain:** `promotions_pricing`  **Data type:** percentage (0–1 or 0–100%)  
**Reporting level:** item, brand  

**Definition:**  
The percentage price reduction from base price to promoted price. Measures how deeply a product is discounted when on promotion.

**Formula:**  
`1 − (Promoted Price / Base Price)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | % Discount / Depth of Discount |
| Circana | Depth of Discount |
| NielsenIQ | Depth of Discount |
| legacy_IRI | % Discount |

**Tags:** `price` `promotion` `discount`

**Related terms:** PRCE_001, PRCE_002

---

### Incremental Volume `PRCE_004`
**Full name:** Incremental Volume (Promotional Lift)  
**Domain:** `promotions_pricing`  **Data type:** units or currency  
**Reporting level:** item, brand, category  

**Definition:**  
The additional unit or dollar sales generated by a promotion above the expected baseline volume. Calculated as actual promoted sales minus modeled base sales during the same period.

**Formula:**  
`Actual Sales During Promotion − Modeled Base Sales`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Incremental Volume |
| Circana | Incremental Volume / Incremental $ Lift |
| NielsenIQ | Incremental Volume |
| legacy_IRI | Incremental Volume |
| legacy_Nielsen | Incremental Volume |

**Vendor notes / gotchas:**
- **Circana:** Also reported as 'Incremental $ lift per week of support' (lift divided by weeks of promotion).
- **all:** Subsidized volume = promoted sales − incremental volume; represents sales that would have occurred anyway.

**Tags:** `promotion` `lift` `baseline` `efficiency`

**Related terms:** PRCE_001, PRCE_005

---

### % Subsidized Volume `PRCE_005`
**Full name:** Percent Subsidized Volume  
**Domain:** `promotions_pricing`  **Data type:** percentage (0–100)  
**Reporting level:** item, brand  

**Definition:**  
The share of promoted sales that would have been purchased at regular price even without the promotion. High subsidized volume indicates an inefficient promotion that mainly discounts loyal buyers rather than driving incremental trips.

**Formula:**  
`(Promoted Sales − Incremental Sales) / Promoted Sales × 100`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | % Subsidized Volume |
| Circana | % Subsidized Volume |
| NielsenIQ | % Subsidized Volume |
| legacy_Nielsen | % Subsidized |

**Tags:** `promotion` `efficiency` `subsidy`

**Related terms:** PRCE_004

---

### EDLP `PRCE_006`
**Full name:** Everyday Low Price  
**Domain:** `promotions_pricing`  **Data type:** categorical (pricing strategy flag)  
**Reporting level:** retailer, item  

**Definition:**  
A pricing strategy in which a retailer or brand maintains consistently low prices without running temporary price promotions. Common in mass/club formats (e.g., Walmart, Costco).

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | EDLP |
| Circana | EDLP |
| NielsenIQ | Everyday Low Price (EDLP) |

**Tags:** `price` `strategy` `retailer_type`

---

### Price Elasticity `PRCE_007`
**Full name:** Price Elasticity of Demand  
**Domain:** `promotions_pricing`  **Data type:** numeric (typically −0.5 to −5.0 for CPG)  
**Reporting level:** item, brand, category  

**Definition:**  
The estimated percentage change in unit volume for every 1% change in price, holding all other variables constant. Negative values are typical (price up → volume down). Used in trade promotion optimization.

**Formula:**  
`% Volume Change / % Price Change`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Elasticity |
| Circana | Elasticity |
| NielsenIQ | Elasticity |
| legacy_Nielsen | Price Elasticity |

**Tags:** `price` `modeling` `sensitivity`

---

### Promo Effectiveness Index `PRCE_008` `★v2`
**Full name:** Promotional Effectiveness Index  
**Domain:** `promotions_pricing`  **Data type:** index (base 100)  
**Reporting level:** item, brand  

**Definition:**  
Index expressing the ratio of total promoted sales to the base (non-promoted) sales that would have occurred during the same promoted period. A value of 200 means promoted sales were twice the expected baseline. Equal to (% Lift + 100).

**Formula:**  
`100 × (Dollar Sales / Base Dollar Sales) with any promotion  |  Promo Effect Index = % Lift + 100`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Dollars, Promo Effect Index / Units, Promo Effect Index / EQ Units, Promo Effect Index |
| Circana | Promo Effectiveness Index |
| NielsenIQ | Promo Lift Index |

**Vendor notes / gotchas:**
- **SPINS:** Available in Dollar, Unit, and EQ Unit variants. Subtracting 100 yields % Lift.

**Tags:** `promotion` `efficiency` `lift` `index`

**Related terms:** PRCE_004, PRCE_009

---

### % Lift `PRCE_009` `★v2`
**Full name:** Percent Promotional Lift  
**Domain:** `promotions_pricing`  **Data type:** percentage  
**Reporting level:** item, brand  

**Definition:**  
The percentage by which promoted sales exceeded the expected base sales during a promotional period. A 50% lift means the promotion drove 50% more volume than baseline. Equal to (Promo Effectiveness Index − 100).

**Formula:**  
`100 × (Incremental Sales / Base Sales with any promotion)  |  % Lift = Promo Effect Index − 100`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Dollars, % Lift / Units, % Lift / EQ Units, % Lift |
| Circana | % Lift |
| NielsenIQ | Incremental % Lift |

**Tags:** `promotion` `efficiency` `lift`

**Related terms:** PRCE_008, PRCE_004

---

### Base Sales `PRCE_010` `★v2`
**Full name:** Base Sales (Dollars / Units / EQ Units)  
**Domain:** `promotions_pricing`  **Data type:** currency (Base Dollars) or units (Base Units / Base EQ Units)  
**Reporting level:** item, brand  

**Definition:**  
Modeled estimate of the dollar, unit, or EQ unit sales that would have occurred in the absence of any retailer promotion activity. Serves as the baseline from which incremental sales and promotional lift are calculated. Available in three variants: Base Dollars, Base Units, Base EQ Units.

**Formula:**  
`Sum(modeled base sales) — derived by removing promotion effects from actual sales`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Base Dollars / Base Units / Base EQ Units |
| Circana | Base Dollar Sales / Base Unit Sales |
| NielsenIQ | Base Sales / Baseline |
| legacy_Nielsen | Base |

**Vendor notes / gotchas:**
- **SPINS:** Also reported as 'Base Dollars, Promo' (base during promoted weeks only) and 'Base Dollars SPM/SPP' (distribution-normalized variants).

**Tags:** `baseline` `promotion` `modeling` `foundational`

**Related terms:** PRCE_004, PRCE_001, PRCE_008

---

### ARP, Promo `PRCE_011` `★v2`
**Full name:** Average Retail Price, Promoted  
**Domain:** `promotions_pricing`  **Data type:** currency (USD) per unit  
**Reporting level:** item  

**Definition:**  
The average unit price for units sold when any promotion (feature, display, or TPR) was present. Weighted by dollar sales, not a simple average across stores and weeks.

**Formula:**  
`(Dollar Sales / Unit Sales) with any promotion`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | ARP, Promo |
| Circana | Promoted Price |
| NielsenIQ | Promoted Price |

**Tags:** `price` `promoted` `average`

**Related terms:** METR_005, PRCE_012, PRCE_001

---

### ARP, Non-Promo `PRCE_012` `★v2`
**Full name:** Average Retail Price, Non-Promoted  
**Domain:** `promotions_pricing`  **Data type:** currency (USD) per unit  
**Reporting level:** item  

**Definition:**  
The average unit price for units sold when no promotion was present. Weighted by dollar sales. Closely related to Base ARP but represents actual scanned prices in non-promoted weeks rather than a modeled baseline.

**Formula:**  
`(Dollar Sales / Unit Sales) with no promotion`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | ARP, Non-Promo |
| Circana | Non-Promoted Price |
| NielsenIQ | Non-Promoted Price / Base Price (approximate) |

**Vendor notes / gotchas:**
- **all:** ARP Non-Promo reflects actual scanned prices in non-promoted weeks; Base ARP is a modeled estimate of what price would have been in the absence of promotion even where promotion occurred.

**Tags:** `price` `non_promoted` `average`

**Related terms:** PRCE_011, PRCE_001, METR_005

---

### Base ARP `PRCE_013` `★v2`
**Full name:** Base Average Retail Price  
**Domain:** `promotions_pricing`  **Data type:** currency (USD) per unit  
**Reporting level:** item  

**Definition:**  
Modeled unit price that would be expected in the complete absence of retailer promotion. Calculated as (Dollars + Markdown Dollars) / Units, incorporating markdown dollars to reconstruct the full non-promoted price even in weeks with a promotion.

**Formula:**  
`(Dollar Sales + Markdown Dollars) / Units`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Base ARP |
| Circana | Base Price |
| NielsenIQ | Base Price |

**Tags:** `price` `baseline` `modeled`

**Related terms:** PRCE_001, PRCE_012

---

### Dollar_Sales_Merch `SCHEMA_003` `★v2`
**Full name:** Dollar Sales with Merchandising (Schema Field)  
**Domain:** `promotions_pricing`  **Data type:** currency (USD)  
**Reporting level:** item  

**Definition:**  
Column in IRI/Circana exports representing dollar sales occurring when any merchandising support (feature, display, or price reduction) was active. Equivalent to 'Dollars, Any Promo' in SPINS terminology.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | Dollar_Sales_Merch (export field) |
| SPINS | Dollars, Promo |
| NielsenIQ | $ w/ Any Merch |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** Map Dollar_Sales_Merch (Circana export) → Dollars, Promo (SPINS) → $ w/ Any Merch (NIQ).

**Tags:** `schema_field` `IRI_export` `promotion` `mapping`

**Related terms:** PRCE_004

---

### Feature Weeks `NIQ_003` `★v2`
**Full name:** Feature Weeks (Ad Weeks)  
**Domain:** `promotions_pricing`  **Data type:** integer (weeks)  
**Reporting level:** item, brand  

**Definition:**  
The number of weeks during which a product appeared in a retailer's circular, leaflet, or weekly flyer (Feature Ad). Feature ads communicate promotional pricing to shoppers and are a primary driver of incremental sales lift.

**Formula:**  
`Count of weeks with Feature Ad activity`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Feature Weeks / Ad Weeks |
| Circana | Feature Weeks |
| NielsenIQ | Feature Weeks |

**Tags:** `promotion` `merchandising` `feature` `weekly`

---

### Display Weeks `NIQ_004` `★v2`
**Domain:** `promotions_pricing`  **Data type:** integer (weeks)  
**Reporting level:** item, brand  

**Definition:**  
The number of weeks during which a product had in-store secondary display placement outside its everyday shelf location (e.g., end cap, floor stand, pallet display). Display activity typically drives immediate purchase lift.

**Formula:**  
`Count of weeks with Display activity`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Display Weeks |
| Circana | Display Weeks |
| NielsenIQ | Display Weeks |

**Tags:** `promotion` `merchandising` `display` `weekly`

**Related terms:** NIQ_003, NIQ_005

---

### Feature and Display Weeks `NIQ_005` `★v2`
**Domain:** `promotions_pricing`  **Data type:** integer (weeks)  
**Reporting level:** item, brand  

**Definition:**  
The number of weeks during which a product had BOTH feature ad and in-store display support simultaneously. Feature + Display is the most powerful promotional condition and typically generates the highest incremental lift.

**Formula:**  
`Count of weeks with both Feature AND Display activity`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Feature & Display Weeks |
| Circana | Feature and Display Weeks |
| NielsenIQ | Feature and Display Weeks |

**Tags:** `promotion` `merchandising` `feature` `display` `weekly`

**Related terms:** NIQ_003, NIQ_004

---

## Channels & Geography {#channel_geography}

### MULO `CHAN_001`
**Full name:** Multi-Outlet  
**Domain:** `channel_geography`  **Data type:** channel definition / geographic scope  
**Reporting level:** channel_total, account  

**Definition:**  
A multi-channel retail aggregate covering Grocery/Food, Drug, Mass Merchandise (including Walmart), Club (excluding Costco for IRI), Dollar, and Military stores. Represents the broadest conventional retail view for CPG performance. Does not include natural/specialty retailers covered exclusively by SPINS.

**Example:**  
_A brand's MULO sales + SPINS Natural + SPINS Specialty Gourmet = Total US approximation._

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | MULO (sourced from Circana) |
| Circana | MULO |
| NielsenIQ | xAOC (equivalent) |
| legacy_IRI | MULO |

**Vendor notes / gotchas:**
- **Circana:** MULO-C adds Convenience channel. MULO is the standard multi-outlet market.
- **NielsenIQ:** xAOC (extended All Outlet Combined) is the NIQ equivalent of MULO. Both include Walmart. SPINS receives its conventional data from Circana, so SPINS MULO = Circana MULO.
- **SPINS:** Natural/Specialty channels are additive to MULO; they do NOT overlap.

**Tags:** `channel` `multi_outlet` `aggregate` `conventional` `geography`

**Related terms:** CHAN_002, CHAN_003, CHAN_004

---

### xAOC `CHAN_002`
**Full name:** Extended All Outlet Combined  
**Domain:** `channel_geography`  **Data type:** channel definition / geographic scope  
**Reporting level:** channel_total  

**Definition:**  
NielsenIQ's broadest US retail aggregate, equivalent to Circana's MULO. Includes Food/Grocery, Drug, Mass (Walmart included), Club, Dollar, and Military. The 'x' historically indicated the extension to include Walmart once they joined the NIQ panel.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| NielsenIQ | xAOC |
| Circana | MULO (equivalent) |
| SPINS | N/A (uses Circana MULO for conventional) |

**Vendor notes / gotchas:**
- **NielsenIQ:** xAOC + Convenience = xAOC Incl Conv. xAOC + WFM = a common custom market for brands with Whole Foods distribution.
- **legacy_Nielsen:** Preceded by FDMx (Food-Drug-Mass excluding Walmart). xAOC replaced this once Walmart cooperated.

**Tags:** `channel` `NielsenIQ` `multi_outlet` `aggregate` `geography`

**Related terms:** CHAN_001

---

### Natural Channel `CHAN_003`
**Full name:** Natural Supermarket Channel  
**Domain:** `channel_geography`  **Data type:** channel definition / geographic scope  
**Reporting level:** channel_total, account  

**Definition:**  
A SPINS-exclusive retail channel definition covering full-format supermarkets with more than $2M in annual sales where at least 50% of sales derive from natural and organic products (as defined by SPINS), and less than 50% from supplements. Does not include Whole Foods Market.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Natural Channel / Natural Supermarkets / SPINSscan Natural |
| Circana | N/A (not covered) |
| NielsenIQ | N/A (not covered) |

**Vendor notes / gotchas:**
- **SPINS:** Includes retailers such as Sprouts Farmers Market, Earth Fare, Natural Grocers. Whole Foods is NOT included here; it appears in NIQ/Circana Food totals.
- **cross_vendor_conflict:** Whole Foods is in Circana/NIQ Food channel, NOT in SPINS Natural. Sprouts is in SPINS Natural, NOT in Circana/NIQ totals.

**Tags:** `channel` `SPINS_exclusive` `natural` `organic` `geography`

**Related terms:** CHAN_004, CHAN_001

---

### Specialty Gourmet Channel `CHAN_004`
**Full name:** Specialty Gourmet Supermarket Channel  
**Domain:** `channel_geography`  **Data type:** channel definition / geographic scope  
**Reporting level:** channel_total, account  

**Definition:**  
A SPINS-exclusive channel covering high-end, experiential full-format supermarkets with more than $2M in annual sales featuring full-service and fresh departments (prepared foods, butcher, on-site bakery). Distinct from the Natural channel by emphasis on premium/gourmet rather than natural/organic as primary positioning.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Specialty Gourmet / SPINSscan Specialty Gourmet |
| Circana | N/A |
| NielsenIQ | N/A |

**Vendor notes / gotchas:**
- **SPINS:** Example retailers: The Fresh Market, Bristol Farms, King's, Fairway Market. Not in Circana/NIQ universe.

**Tags:** `channel` `SPINS_exclusive` `specialty` `gourmet` `geography`

**Related terms:** CHAN_003

---

### Grocery Channel `CHAN_005`
**Full name:** Grocery / Food Channel  
**Domain:** `channel_geography`  **Data type:** channel definition  
**Reporting level:** channel_total, account  

**Definition:**  
Stores primarily focused on selling food and consumable products with annual sales above $2M. The foundational channel for CPG measurement. Excludes natural/specialty-only retailers covered by SPINS.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Conventional (via Circana) |
| Circana | Grocery / Food |
| NielsenIQ | Total Food |
| legacy_IRI | Grocery |
| legacy_Nielsen | Total Food |

**Vendor notes / gotchas:**
- **cross_vendor_conflict:** NielsenIQ calls this 'Total Food'; Circana calls it 'Grocery.' Functionally identical market. Both exclude non-cooperators Aldi and Trader Joe's from direct data (estimates used for totals). NIQ receives WFM data directly; Circana projects it.
- **SPINS:** Conventional channel in SPINS is powered by Circana data, so coverage is equivalent.

**Tags:** `channel` `grocery` `food` `conventional`

**Related terms:** CHAN_001, CHAN_002

---

### Drug Channel `CHAN_006`
**Full name:** Drug / Pharmacy Channel  
**Domain:** `channel_geography`  **Data type:** channel definition  

**Definition:**  
Retail stores primarily focused on pharmacy and health products, including major chains such as CVS, Walgreens, and Rite Aid. Included in both MULO (Circana) and xAOC (NielsenIQ).

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Drug (via Circana) |
| Circana | Drug |
| NielsenIQ | Drug |

**Tags:** `channel` `drug` `pharmacy` `conventional`

---

### Mass Channel `CHAN_007`
**Full name:** Mass Merchandise Channel  
**Domain:** `channel_geography`  **Data type:** channel definition  

**Definition:**  
Large-format retailers selling general merchandise and grocery products at scale, including Walmart, Target, and similar chains. Walmart is the dominant component and is included in both MULO and xAOC.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Mass (via Circana) |
| Circana | Mass Merchandise / Mass |
| NielsenIQ | Mass / Walmart + Mass |

**Tags:** `channel` `mass` `walmart` `conventional`

---

### Market ACV `GEO_001` `★v2`
**Full name:** Market All Commodity Volume  
**Domain:** `channel_geography`  **Data type:** currency ($MM, annualized)  
**Reporting level:** geography, channel  

**Definition:**  
Total annualized dollar sales of all products across all stores in a selected geography, expressed in millions of dollars ($MM). Used to measure the relative size of geographies. Always represents a 52-week annualized figure regardless of the selected reporting period. For key accounts and RMAs, SPINS reports the midpoint of a predetermined ACV range rather than the actual retailer ACV.

**Formula:**  
`Sum(Annualized ACV across all stores in the geography)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Market ACV |
| Circana | Market ACV |
| NielsenIQ | Market ACV / Est Market ACV |

**Vendor notes / gotchas:**
- **SPINS:** Retail agreements prevent release of exact chain-level ACV; SPINS reports the midpoint of a predetermined range for key accounts.

**Tags:** `geography` `market_size` `acv` `annualized`

**Related terms:** DIST_001, CHAN_001

---

### # Stores `GEO_002` `★v2`
**Full name:** Number of Stores  
**Domain:** `channel_geography`  **Data type:** integer  
**Reporting level:** geography, channel  

**Definition:**  
The total count of stores within a specified geography. Used as a denominator in numeric distribution calculations and to contextualize the size of a market.

**Formula:**  
`Sum(# Stores in geography)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | # Stores |
| Circana | Store Count |
| NielsenIQ | Store Count / # Stores |

**Tags:** `geography` `store_count`

**Related terms:** DIST_004, GEO_001

---

### Households `GEO_003` `★v2`
**Full name:** Households (Geography)  
**Domain:** `channel_geography`  **Data type:** integer  
**Reporting level:** geography  

**Definition:**  
The number of households within a specified geography, sourced from the U.S. Census Bureau and updated annually. Returns the same value for all product hierarchy levels. Not available for Key Accounts or Retail Marketing Areas (RMAs).

**Formula:**  
`U.S. Census Bureau household count (annual)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Households |
| Circana | Households |
| NielsenIQ | Households / HH |

**Vendor notes / gotchas:**
- **SPINS:** Value is identical across all product levels. Not available for Key Accounts or RMAs.

**Tags:** `geography` `demographics` `census`

**Related terms:** GEO_004, PANEL_001

---

### Population `GEO_004` `★v2`
**Full name:** Population (Geography)  
**Domain:** `channel_geography`  **Data type:** integer  
**Reporting level:** geography  

**Definition:**  
The number of people within a specified geography, sourced from the U.S. Census Bureau and updated annually. Returns the same value for all product hierarchy levels. Not available for Key Accounts or RMAs.

**Formula:**  
`U.S. Census Bureau population count (annual)`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Population |
| Circana | Population |
| NielsenIQ | Population |

**Tags:** `geography` `demographics` `census`

**Related terms:** GEO_003

---

### Geography_Type / Outlet_Type / Retailer_Type `SCHEMA_004` `★v2`
**Full name:** Geography, Outlet, and Retailer Type Fields (IRI Export)  
**Domain:** `channel_geography`  **Data type:** categorical string  
**Reporting level:** geography, channel, retailer  

**Definition:**  
Three related column fields in IRI/Circana data exports that classify the geographic and retail context of a record. Geography_Type indicates the aggregation level (e.g., Total US, Region, Market). Outlet_Type indicates the channel (e.g., Grocery, Drug, Mass). Retailer_Type provides a more granular retailer classification.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | Geography_Type / Outlet_Type / Retailer_Type (export fields) |
| SPINS | Geography Name / Channel / Outlet |
| NielsenIQ | Geography Description / Geography Type / Channel |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** Geography_Name and Geography_Description are the human-readable equivalents; Geography_Key and Geography_Desciption [sic] are internal keys. Note the typo 'Desciption' (missing 'r') appears in the IRI export schema.

**Tags:** `schema_field` `IRI_export` `geography` `channel` `mapping`

**Related terms:** CHAN_001, CHAN_002, CHAN_005

---

### FMCG Regions `NIQ_011` `★v2`
**Full name:** FMCG Geographic Regions (NielsenIQ)  
**Domain:** `channel_geography`  **Data type:** categorical (4 values: East, South, Central, West)  
**Reporting level:** region  

**Definition:**  
NielsenIQ's four standard US geographic divisions used for regional performance analysis: East, South, Central, and West. Used to identify broad regional differences in brand or category performance.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| NielsenIQ | FMCG Regions |
| SPINS | Census Regions (approximate) |
| Circana | IRI Regions |

**Vendor notes / gotchas:**
- **cross_vendor_conflict:** NIQ uses 4 regions (East/South/Central/West). Circana uses a slightly different regional breakdown. Region definitions do not perfectly align across vendors.

**Tags:** `geography` `region` `NielsenIQ`

**Related terms:** GEO_001

---

### Major Markets `NIQ_012` `★v2`
**Full name:** Major Markets (Metro Markets)  
**Domain:** `channel_geography`  **Data type:** categorical (geographic boundary)  
**Reporting level:** metro_market  

**Definition:**  
Geographic reporting units built around key US cities and their surrounding suburbs (~50 metro markets available from NielsenIQ and Circana). Used to understand city-level performance differences and target retail investment.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| NielsenIQ | Major Markets |
| Circana | IRI Markets / Metro Markets |
| SPINS | Metro Markets |

**Tags:** `geography` `metro` `market` `DMA`

---

### Convenience Channel `NIQ_013` `★v2`
**Full name:** Convenience Store Channel  
**Domain:** `channel_geography`  **Data type:** channel definition  
**Reporting level:** channel_total, account  

**Definition:**  
Small-format retail stores selling everyday and immediate-consumption items, often co-located with fuel stations. Included in MULO-C (Circana) and xAOC Incl Conv (NielsenIQ) but excluded from standard MULO / xAOC aggregates.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Convenience (via Circana) |
| Circana | Convenience / C-Store |
| NielsenIQ | Convenience |

**Vendor notes / gotchas:**
- **Circana:** Add '-C' suffix to MULO for convenience inclusion (MULO-C).
- **NielsenIQ:** Add 'Incl Conv' to xAOC (xAOC Incl Conv).

**Tags:** `channel` `convenience` `c_store`

**Related terms:** CHAN_001, CHAN_002

---

### Club Channel `NIQ_014` `★v2`
**Full name:** Club / Warehouse Channel  
**Domain:** `channel_geography`  **Data type:** channel definition  
**Reporting level:** channel_total, account  

**Definition:**  
Large-format membership retailers (e.g., Costco, Sam's Club, BJ's Wholesale) that sell larger package sizes at lower equivalized prices. Included in MULO (Circana) and xAOC (NielsenIQ). Note: Costco does not cooperate with Circana; NIQ includes Costco.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Club (via Circana) |
| Circana | Club (excludes Costco) |
| NielsenIQ | Club (includes Costco) |

**Vendor notes / gotchas:**
- **cross_vendor_conflict:** Costco cooperates with NIQ but NOT Circana. This is a meaningful coverage gap for brands with heavy club distribution.

**Tags:** `channel` `club` `warehouse` `Costco`

**Related terms:** CHAN_001, CHAN_002

---

### Dollar Store Channel `NIQ_015` `★v2`
**Full name:** Dollar / Value Channel  
**Domain:** `channel_geography`  **Data type:** channel definition  
**Reporting level:** channel_total, account  

**Definition:**  
Small-format stores selling general merchandise and grocery in smaller packages at discounted price points. Major chains include Dollar General and Family Dollar. Included in both MULO and xAOC.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Dollar (via Circana) |
| Circana | Dollar |
| NielsenIQ | Dollar |

**Tags:** `channel` `dollar` `value` `discount`

**Related terms:** CHAN_001, CHAN_002

---

### Geography (SPINS) `SPINS_COL_001` `★v3`
**Full name:** Geography / Market Name (SPINS Column)  
**Domain:** `channel_geography`  **Data type:** string  
**Reporting level:** geography  

**Definition:**  
The named market or geographic scope of the data row in a SPINS export. Values represent predefined SPINS market definitions such as 'TOTAL US - FOOD', individual retail accounts, or regional composites. This is the human-readable market label; no separate geography_key column is present in standard SPINS exports (unlike Circana).

**Example:**  
_'TOTAL US - FOOD', 'EAST - FOOD', 'SPROUTS FARMERS MARKET'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Geography |
| Circana | geography + geography_description (two fields) |
| NielsenIQ | Geography / Market |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** SPINS uses a single 'Geography' column. Circana splits this into 'geography' (display name) and 'geography_key' (integer FK) and 'geography_description' (often identical to geography). Map SPINS Geography → Circana geography / geography_description for joins.
- **SPINS:** Example value: 'TOTAL US - FOOD'. The suffix '-FOOD' indicates the grocery/food outlet type is embedded in the geography string itself — unlike Circana which separates outlet type into projected_outlet_type_name.

**Tags:** `schema_field` `SPINS_column` `geography` `dimension`

**Related terms:** CHAN_005, GEO_001, SPINS_COL_002

---

### acv_millions (Circana) `CIRC_COL_004` `★v3`
**Full name:** Market ACV in Millions — Circana Column  
**Domain:** `channel_geography`  **Data type:** numeric (dollars — verify scale against known market ACV)  
**Reporting level:** geography  

**Definition:**  
Total annualized ACV of the entire geography in the Circana export, expressed in dollars (despite the 'millions' name, the raw value appears to be in actual dollars — e.g., 125760.57 = ~$125K, not $125M). Serves as the denominator for ACV distribution calculations. Returns the same value for all product rows within the same geography-week combination.

**Example:**  
_125760.565591 (verify unit: dollars vs. thousands vs. millions)_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | acv_millions |
| SPINS | Market ACV (GEO_001) |
| NielsenIQ | Est Market ACV |

**Vendor notes / gotchas:**
- **Circana:** ⚠ Despite the column name 'acv_millions', the mock data shows values like 125760.57 for an Ahold account — confirm whether this is actual dollars, thousands, or millions based on your specific data feed contract. The field name is misleading in small-account exports.
- **cross_vendor_alignment:** Same concept as SPINS Market ACV (GEO_001) and NIQ Est Market ACV, but scale/unit requires verification.

**Tags:** `schema_field` `Circana_column` `market_ACV` `geography` `scale_warning`

**Related terms:** GEO_001, CIRC_COL_003

---

### projected_geography_type_name (Circana) `CIRC_COL_007` `★v3`
**Full name:** Projected Geography Type Name (Circana Column)  
**Domain:** `channel_geography`  **Data type:** categorical string  
**Reporting level:** geography  

**Definition:**  
Circana's geographic hierarchy classification for the row's geography. Indicates the type of geographic aggregation used. Example value 'CRMA' (Customer Retail Market Area) indicates a retailer-defined geographic zone. Other values include 'Total US', 'Region', 'Market'.

**Example:**  
_'CRMA', 'Total US', 'Region', 'Market'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | projected_geography_type_name |
| SPINS | N/A (embedded in Geography string suffix) |
| NielsenIQ | Geography Type |

**Vendor notes / gotchas:**
- **Circana:** CRMA = Customer Retail Market Area — a Circana-specific geographic unit representing a retailer's trading zone. This column differentiates account-level geographies from channel totals.
- **cross_vendor_alignment:** Maps to SPINS Geography string parsing and NielsenIQ Geography Type. In SPINS, the geography type is embedded in the Geography column value (e.g., 'TOTAL US - FOOD' → type=Total US, outlet=FOOD).

**Tags:** `schema_field` `Circana_column` `geography_type` `CRMA` `dimension`

**Related terms:** CHAN_001, GEO_001, CIRC_COL_008

---

### projected_outlet_type_name (Circana) `CIRC_COL_008` `★v3`
**Full name:** Projected Outlet Type Name — Channel (Circana Column)  
**Domain:** `channel_geography`  **Data type:** categorical string  
**Reporting level:** channel  

**Definition:**  
The retail channel classification for the geography in a Circana export. Equivalent to the outlet type embedded in SPINS Geography strings. Example: 'FOOD' = Grocery/Food channel. Other values include 'DRUG', 'MASS', 'CLUB', 'DOLLAR', 'MILITARY', 'CONVENIENCE'.

**Example:**  
_'FOOD', 'DRUG', 'MASS', 'CLUB'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | projected_outlet_type_name |
| SPINS | Embedded in Geography string (e.g., 'TOTAL US - FOOD') |
| NielsenIQ | Channel |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** In SPINS exports, channel is embedded in the Geography column (suffix after ' - '). In Circana, it is a separate column. Parse SPINS Geography string to extract outlet type for cross-vendor channel alignment.

**Tags:** `schema_field` `Circana_column` `channel` `outlet_type` `dimension`

**Related terms:** CHAN_005, CIRC_COL_007, CIRC_COL_009

---

### projected_retailer_type_name (Circana) `CIRC_COL_009` `★v3`
**Full name:** Projected Retailer Type Name (Circana Column)  
**Domain:** `channel_geography`  **Data type:** categorical string  
**Reporting level:** retailer  

**Definition:**  
The specific retailer or retailer group for the data row in Circana exports. More granular than outlet type — identifies the actual retailer chain (e.g., 'AHOLD DELHAIZE', 'KROGER', 'WALMART'). Combined with projected_outlet_type_name and projected_geography_type_name, fully defines the retail context.

**Example:**  
_'AHOLD DELHAIZE', 'KROGER', 'WALMART', 'CVS'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | projected_retailer_type_name |
| SPINS | Embedded in Geography string |
| NielsenIQ | Retailer / Account |

**Tags:** `schema_field` `Circana_column` `retailer` `account` `dimension`

---

## Product Hierarchy & Classification {#hierarchy_classification}

### UPC `HIER_001`
**Full name:** Universal Product Code  
**Domain:** `hierarchy_classification`  **Data type:** string (12-digit numeric)  
**Reporting level:** item  

**Definition:**  
A 12-digit numeric barcode printed on consumer product packaging that uniquely identifies a specific product-size-variant combination at the point of sale. The most granular level of product hierarchy in syndicated CPG data. One of five core POS facts captured at the register.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | UPC |
| Circana | UPC |
| NielsenIQ | UPC |

**Vendor notes / gotchas:**
- **all:** An EAN-13 (European Article Number, 13 digits) is the international equivalent. In NIQ/Circana global data, EAN is used.

**Tags:** `product_id` `barcode` `item_level` `foundational` `pos`

**Related terms:** HIER_002, HIER_003

---

### SKU `HIER_002`
**Full name:** Stock Keeping Unit  
**Domain:** `hierarchy_classification`  **Data type:** string (alphanumeric, retailer-defined)  
**Reporting level:** item, retailer  

**Definition:**  
A retailer-specific internal identifier for a product variant at a given store or chain. While UPC is universal, SKUs vary by retailer. In syndicated data, UPC is the cross-retailer standard; SKU is used in retailer direct data.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | SKU |
| Circana | SKU / Item |
| NielsenIQ | SKU / Item |

**Vendor notes / gotchas:**
- **cross_vendor_conflict:** SKU is not universal; the same physical product has different SKUs at Target vs. Kroger. UPC is the canonical join key across vendors.

**Tags:** `product_id` `retailer_specific` `item_level`

**Related terms:** HIER_001

---

### Product Hierarchy `HIER_003`
**Full name:** CPG Product Classification Hierarchy  
**Domain:** `hierarchy_classification`  **Data type:** categorical taxonomy  

**Definition:**  
The nested classification structure used to organize products from broadest to most granular level. All three vendors use a similar multi-level hierarchy, though naming and levels differ.

**Vendor notes / gotchas:**
- **cross_vendor_conflict:** The same product may sit in different categories or segments depending on vendor taxonomy. Example: a kombucha may be in 'Functional Beverages' (SPINS) vs. 'Refrigerated Beverages' (Circana) vs. 'Shelf-Stable Juice' (NIQ). Category alignment is a critical pre-processing step for cross-vendor ML.
- **SPINS:** SPINS applies its own proprietary coding, distinct from Circana, even for the same conventional products.

**Tags:** `hierarchy` `classification` `taxonomy` `cross_vendor_alignment`

**Related terms:** HIER_001, HIER_004

---

### Brand `HIER_004`
**Domain:** `hierarchy_classification`  **Data type:** string  
**Reporting level:** brand  

**Definition:**  
A named product line under a single manufacturer identity. Sits above UPC and below manufacturer in the product hierarchy. Cross-vendor brand naming can differ in capitalization, abbreviation, and grouping of sub-brands.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Brand |
| Circana | Brand |
| NielsenIQ | Brand |

**Vendor notes / gotchas:**
- **cross_vendor_conflict:** Brand strings may differ across vendors (e.g., 'KIND' vs. 'Kind' vs. 'Kind Snacks'). Requires normalization/entity resolution for cross-vendor ML.

**Tags:** `brand` `hierarchy` `entity_resolution`

**Related terms:** HIER_001, HIER_003

---

### UPC_10 / UPC_13 `SCHEMA_005` `★v2`
**Full name:** UPC-10 and UPC-13 (Schema Fields)  
**Domain:** `hierarchy_classification`  **Data type:** string (numeric)  
**Reporting level:** item  

**Definition:**  
Two UPC format fields in IRI/Circana exports. UPC_10 is the 10-digit code (check digit stripped, leading zero stripped). UPC_13 is the 13-digit EAN/GTIN format used internationally. Both refer to the same physical product. NielsenIQ exports typically use a 14-digit GTIN.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | UPC_10 / UPC_13 |
| SPINS | UPC (12-digit) |
| NielsenIQ | UPC / GTIN-14 |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** Pad UPC_10 to 12 digits for SPINS join: add leading zero + check digit. UPC_13 = EAN-13 (international). NIQ uses 14-digit GTIN. Always confirm digit format before cross-vendor joins on UPC.

**Tags:** `schema_field` `IRI_export` `UPC` `GTIN` `mapping` `cross_vendor_alignment`

**Related terms:** HIER_001

---

### Assortment `NIQ_001` `★v2`
**Full name:** Retail Assortment  
**Domain:** `hierarchy_classification`  **Data type:** categorical/list  
**Reporting level:** retailer, category  

**Definition:**  
The set of products (items/SKUs) a retailer carries in a given category. Assortment decisions — adds, deletes, and retains — are made during line reviews. Key terminology: Add = item not currently carried; Delete = item being removed; Retain = item staying on shelf.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Assortment |
| Circana | Assortment |
| NielsenIQ | Assortment |

**Tags:** `assortment` `category_management` `retailer` `line_review`

---

### Product Universe (SPINS) `SPINS_COL_003` `★v3`
**Full name:** Product Universe (SPINS Column)  
**Domain:** `hierarchy_classification`  **Data type:** categorical string  
**Reporting level:** item, brand  

**Definition:**  
A SPINS-specific column indicating the product universe or panel from which the data was pulled. Example value 'TPL' refers to Total Product Line — the broadest SPINS product scope. Used to distinguish data pulled from different SPINS product universes within the same export.

**Example:**  
_'TPL'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Product Universe |
| Circana | N/A (no direct equivalent) |
| NielsenIQ | N/A |

**Vendor notes / gotchas:**
- **SPINS:** Common values: 'TPL' (Total Product Line), channel-specific universes. This column is SPINS-exclusive and has no mapping in Circana or NielsenIQ exports.

**Tags:** `schema_field` `SPINS_column` `SPINS_exclusive` `product_universe` `dimension`

---

### Product Level (SPINS) `SPINS_COL_004` `★v3`
**Full name:** Product Hierarchy Level (SPINS Column)  
**Domain:** `hierarchy_classification`  **Data type:** categorical string  
**Reporting level:** item, brand, category  

**Definition:**  
Indicates the granularity of the product dimension for the data row. Equivalent to 'standard_hierarchy_level' in Circana exports. Common values: 'UPC' (item level), 'BRAND', 'SUBCATEGORY', 'CATEGORY', 'DEPARTMENT'.

**Example:**  
_'UPC', 'BRAND', 'SUBCATEGORY'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Product Level |
| Circana | standard_hierarchy_level |
| NielsenIQ | Hierarchy Level |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** Direct mapping: SPINS 'Product Level' = Circana 'standard_hierarchy_level'. Both use 'UPC' as the item-level value.

**Tags:** `schema_field` `SPINS_column` `hierarchy_level` `dimension`

---

### UPC (SPINS format) `SPINS_COL_005` `★v3`
**Full name:** UPC — SPINS Formatted (Hyphenated 14-digit)  
**Domain:** `hierarchy_classification`  **Data type:** string (hyphenated: '00-XXXXX-XXXXX')  
**Reporting level:** item  

**Definition:**  
The product barcode in SPINS exports formatted as a hyphenated string: '00-XXXXX-XXXXX' (two leading zeros, five-digit manufacturer code, five-digit item code, no check digit visible). This is SPINS's display format and must be normalized before joining to Circana (upc10/upc13) or NielsenIQ (GTIN-14).

**Example:**  
_SPINS: '00-52000-01016' → Circana upc10: 5200001001 (strip hyphens, drop leading zeros and check digit)_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | UPC (format: '00-52000-01016') |
| Circana | upc10 (10-digit int) + upc13 (13-digit int) |
| NielsenIQ | UPC (12-digit) / GTIN-14 |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** To join SPINS UPC → Circana: strip hyphens → 14-digit string → drop leading '00' + last digit (check) to get upc10 (10-digit). Or: strip hyphens → drop leading '0' → upc13 (13-digit). To join SPINS UPC → NIQ: strip hyphens → standard 12-digit UPC. Example: SPINS '00-52000-01016' → upc10 '5200001016' (drop leading 00, drop check digit 6... verify with Luhn). Always validate with actual check digit logic.
- **SPINS:** The leading '00' prefix in SPINS hyphenated UPCs corresponds to the GS1 company prefix format. The last digit shown is the check digit.

**Tags:** `schema_field` `SPINS_column` `UPC` `GTIN` `cross_vendor_alignment` `join_key`

**Related terms:** HIER_001, SCHEMA_005

---

### UNIT OF MEASURE (SPINS) `SPINS_COL_007` `★v3`
**Full name:** Unit of Measure (SPINS Column)  
**Domain:** `hierarchy_classification`  **Data type:** categorical string  
**Reporting level:** UPC  

**Definition:**  
The physical measurement unit for the product's primary size dimension in SPINS exports. Examples: 'OUNCE', 'FLUID OUNCE', 'COUNT'. Used as the basis for EQ Unit (equivalized unit) calculations — products with different unit-of-measure types should not be combined into EQ Unit aggregates.

**Example:**  
_'OUNCE', 'FLUID OUNCE', 'COUNT', 'POUND'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | UNIT OF MEASURE |
| Circana | N/A (not in standard export; embedded in product description) |
| NielsenIQ | N/A |

**Vendor notes / gotchas:**
- **SPINS:** Critical for EQ Unit analysis — only aggregate EQ Units across products with the same UNIT OF MEASURE value.

**Tags:** `schema_field` `SPINS_column` `unit_of_measure` `EQ_units` `product_attribute`

---

### PACK COUNT (SPINS) `SPINS_COL_009` `★v3`
**Full name:** Pack Count (SPINS Column)  
**Domain:** `hierarchy_classification`  **Data type:** integer  
**Reporting level:** UPC  

**Definition:**  
The number of individual servings, pieces, or sub-units included in one sellable consumer package as tracked in SPINS Product Intelligence. A value of 1 indicates a single-serve or single-unit pack.

**Example:**  
_1 (single unit), 6 (6-pack), 24 (case pack)_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | PACK COUNT |
| Circana | N/A (not in standard export) |
| NielsenIQ | N/A |

**Tags:** `schema_field` `SPINS_column` `SPINS_exclusive` `pack_size` `product_attribute`

---

### product_fully_qualified_description (Circana) `CIRC_COL_010` `★v3`
**Full name:** Product Fully Qualified Description (Circana Column)  
**Domain:** `hierarchy_classification`  **Data type:** string (dot-delimited hierarchy path)  
**Reporting level:** item  

**Definition:**  
A dot-delimited string in Circana exports encoding the complete product hierarchy path from Standard Hierarchy root down to the individual UPC. Format: 'Standard Hierarchy.{Category}.{SubCategory}.{Manufacturer-SubCat}.{Manufacturer-SubCat}.{Brand-SubCat}.{Brand-SubCat}.{UPC Description}'. Each level is repeated with a manufacturer/brand suffix. Equivalent to SPINS 'Description' at UPC level but encodes the full ancestry path.

**Example:**  
_'Standard Hierarchy.PICKLES/RELISH/OLIVES.MARINATED VEGETABLE/FRUIT.ZAKUSON INC-...3AKYCOH PICKLED CUCUMBER 33 OZ - 0838396000591'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | product_fully_qualified_description |
| SPINS | Description (UPC level only; no path encoding) |
| NielsenIQ | Product Full Description / FQD |

**Vendor notes / gotchas:**
- **Circana:** Can be parsed by splitting on '.' to extract hierarchy levels. Example: 'Standard Hierarchy.PICKLES/RELISH/OLIVES.MARINATED VEGETABLE/FRUIT.ZAKUSON INC-MARINATED VEGETABLE/FRUIT.[...].3AKYCOH PICKLED CUCUMBER 33 OZ - 0838396000591'. The UPC is embedded in the last segment after ' - '.
- **cross_vendor_alignment:** The UPC can be extracted from this field as the substring after the last ' - ' separator in the final segment, providing a fallback UPC extraction method.

**Tags:** `schema_field` `Circana_column` `hierarchy_path` `FQD` `UPC_extraction`

**Related terms:** HIER_003, HIER_001, SPINS_COL_005

---

### brand_franchise_name (Circana) `CIRC_COL_011` `★v3`
**Full name:** Brand Franchise Name (Circana Column)  
**Domain:** `hierarchy_classification`  **Data type:** string  
**Reporting level:** brand_family  

**Definition:**  
The parent brand family or franchise in Circana's hierarchy, sitting above brand_name. Represents a brand umbrella that may contain multiple distinct brand names. Example: 'GATORADE' franchise may contain 'GATORADE G RECOVER', 'GATORADE ZERO', etc. as brand_name values.

**Example:**  
_'3AKYCOH', 'GATORADE', 'KIND'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | brand_franchise_name |
| SPINS | Brand (approximate — SPINS Brand maps closer to brand_franchise_name) |
| NielsenIQ | Brand Family / Major Brand |

**Vendor notes / gotchas:**
- **cross_vendor_alignment:** SPINS 'Brand' column maps more closely to Circana 'brand_franchise_name' than to 'brand_name'. Verify level alignment for your specific categories before joining.

**Tags:** `schema_field` `Circana_column` `brand_family` `franchise` `hierarchy`

**Related terms:** HIER_004, CIRC_COL_012

---

### brand_name (Circana) `CIRC_COL_012` `★v3`
**Full name:** Brand Name (Circana Column)  
**Domain:** `hierarchy_classification`  **Data type:** string  
**Reporting level:** brand  

**Definition:**  
The specific brand name at the most granular brand level in Circana's hierarchy, below brand_franchise_name. In the mock data, brand_name and brand_franchise_name are identical, which is common for single-brand companies but diverges for large CPG portfolios.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| Circana | brand_name |
| SPINS | Brand (sub-franchise level) |
| NielsenIQ | Brand |

**Tags:** `schema_field` `Circana_column` `brand` `hierarchy`

**Related terms:** CIRC_COL_011, HIER_004

---

## Panel & Shopper Metrics {#panel_shopper}

### Household Penetration `PANEL_001`
**Domain:** `panel_shopper`  **Data type:** percentage (0–100)  
**Reporting level:** brand, category  

**Definition:**  
The percentage of households that purchase a given category, brand, or product at least once during a defined time period. Derived from consumer panel (household) data, not POS scan data.

**Formula:**  
`Households buying the product at least once / Total measured households × 100`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Household Penetration |
| Circana | Household Penetration / HH Penetration |
| NielsenIQ | Household Penetration |

**Vendor notes / gotchas:**
- **all:** Panel-derived metric; requires panel data subscription separate from POS. Not available in basic scan data purchases.
- **SPINS:** Available through TriLens Panel product.

**Tags:** `panel` `shopper` `penetration` `consumer`

**Related terms:** PANEL_002, PANEL_003

---

### Buy Rate `PANEL_002`
**Domain:** `panel_shopper`  **Data type:** currency (USD) or units per buying household  
**Reporting level:** brand, category  

**Definition:**  
The average amount a buying household spends (or number of units they purchase) in a given category or for a given brand over a set time period. Measures the depth of purchase among buyers.

**Formula:**  
`Total Dollar Sales to Buyers / Number of Buying Households`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Buy Rate |
| Circana | Buy Rate / $ per Buying HH |
| NielsenIQ | Buy Rate / $ per Buyer |

**Tags:** `panel` `shopper` `spend_per_buyer`

**Related terms:** PANEL_001, PANEL_003

---

### Purchase Frequency `PANEL_003`
**Domain:** `panel_shopper`  **Data type:** numeric (times per year)  
**Reporting level:** brand, category  

**Definition:**  
The average number of times per year that a buying household purchases a given product, brand, or category. Measures how often loyal buyers return.

**Formula:**  
`Total Purchase Occasions / Number of Buying Households`

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Purchase Frequency |
| Circana | Purchase Frequency / Trips per Buyer |
| NielsenIQ | Frequency / Purchase Frequency |

**Tags:** `panel` `shopper` `loyalty` `repeat_purchase`

**Related terms:** PANEL_001, PANEL_002

---

### Loyal Shoppers `NIQ_006` `★v2`
**Domain:** `panel_shopper`  **Data type:** shopper segment (count or % of buyers)  
**Reporting level:** brand, category  

**Definition:**  
Panel-derived shopper segment: households that purchase in a given category at least twice during the period AND spend more than 65% of their category dollars on a single brand. Loyal shoppers are the most valuable segment for brand retention.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Loyal Shoppers (TriLens) |
| Circana | Loyal Shoppers |
| NielsenIQ | Loyal Shoppers |

**Tags:** `panel` `shopper` `loyalty` `segmentation`

**Related terms:** NIQ_007, PANEL_001

---

### Exclusive Buyers `NIQ_007` `★v2`
**Domain:** `panel_shopper`  **Data type:** shopper segment  
**Reporting level:** brand  

**Definition:**  
Panel-derived shopper segment: households that purchase in a category at least twice and buy exclusively from one brand (100% brand loyalty). Exclusive buyers represent the core loyalist base.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Exclusive Buyers |
| Circana | Exclusive Buyers |
| NielsenIQ | Exclusive Buyers |

**Tags:** `panel` `shopper` `loyalty` `segmentation` `exclusive`

**Related terms:** NIQ_006, PANEL_001

---

### Leakage `NIQ_008` `★v2`
**Domain:** `panel_shopper`  **Data type:** currency (USD)  
**Reporting level:** retailer, category  

**Definition:**  
The dollar amount spent on a product by a retailer's own shoppers at competing retailers. High leakage indicates that a retailer is not capturing its shoppers' full category spending — a key argument for distribution expansion.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Leakage |
| Circana | Leakage |
| NielsenIQ | Leakage |

**Tags:** `panel` `shopper` `retailer` `opportunity`

---

## Product Attributes (SPINS) {#product_attributes}

### Product Attribute `ATTR_001`
**Full name:** Product Attribute (SPINS)  
**Domain:** `product_attributes`  **Data type:** categorical flag (boolean or multi-value)  
**Reporting level:** UPC  

**Definition:**  
A structured tag applied to a product UPC describing a specific characteristic beyond standard category classification. SPINS maintains the industry's most extensive attribute taxonomy for health and wellness products, covering certifications, diet compatibility, ingredients, label claims, and more.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Product Attributes / Attribute Flags |
| Circana | Product Attributes (limited) |
| NielsenIQ | Product Attributes (limited) |

**Vendor notes / gotchas:**
- **SPINS:** Attribute types include: Certification (e.g., Non-GMO Project Verified, Certified Organic), Diet (e.g., Keto Compatible, Vegan), Ingredient (e.g., contains adaptogens, free-from gluten), Label Claim (e.g., Sustainably Sourced, Fair Trade), and Brand Positioning attributes. SPINS Product Intelligence applies thousands of attributes per UPC.
- **cross_vendor_conflict:** Attribute coverage is SPINS's primary differentiator. Circana and NIQ have attribute systems but with far less granularity in natural/organic/wellness dimensions.

**Tags:** `attributes` `SPINS_exclusive` `health_wellness` `natural` `organic`

**Related terms:** ATTR_002, ATTR_003

---

### Certification Attribute `ATTR_002`
**Full name:** Certification Attribute (SPINS)  
**Domain:** `product_attributes`  **Data type:** categorical flag (certified / not certified)  
**Reporting level:** UPC  

**Definition:**  
An attribute flag indicating that a product has received third-party verified certification against a defined standard. Examples include Non-GMO Project Verified, USDA Organic, Certified Paleo, and Rainforest Alliance.

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Certification Attribute |
| Circana | Certification (limited) |
| NielsenIQ | Certification (limited) |

**Tags:** `attributes` `certification` `third_party` `organic` `GMO`

**Related terms:** ATTR_001

---

### Label Claim Attribute `ATTR_003`
**Full name:** Label Claim Attribute (SPINS)  
**Domain:** `product_attributes`  **Data type:** categorical flag  
**Reporting level:** UPC  

**Definition:**  
An attribute flag capturing on-pack marketing language related to sustainability, corporate responsibility, or consumer lifestyle positioning that goes beyond ingredient or nutrition content (e.g., 'Woman-Owned,' 'Recyclable Packaging,' 'B-Corp Certified').

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | Label Claim Attribute |
| Circana | N/A |
| NielsenIQ | N/A |

**Tags:** `attributes` `SPINS_exclusive` `label_claim` `sustainability` `positioning`

**Related terms:** ATTR_001, ATTR_002

---

### NFP Columns (SPINS) `SPINS_COL_006` `★v3`
**Full name:** Nutrition Facts Panel Columns (SPINS)  
**Domain:** `product_attributes`  **Data type:** string (e.g., '20 g', '340 calories') for NFP columns; string range (e.g., '20 TO < 25G PROTEIN') for NFP RANGES columns  
**Reporting level:** UPC  

**Definition:**  
A family of SPINS columns prefixed 'NFP -' that carry specific Nutrition Facts Panel values per UPC. Derived from SPINS Product Intelligence attribute coding of physical product labels. Examples: 'NFP - PROTEIN' (e.g., '20 g'), 'NFP - CALORIES' (e.g., '340 calories'), 'NFP - SUGARS' (e.g., '26 g'). Range-bucketed companion columns (prefix 'NFP RANGES -') group the raw values into standardized tiers for filtering and segmentation.

**Example:**  
_NFP - PROTEIN: '20 g', NFP RANGES - PROTEIN VALUE: '20 TO < 25G PROTEIN', NFP - CALORIES: '340 calories'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | NFP - [NUTRIENT] / NFP RANGES - [NUTRIENT] VALUE |
| Circana | N/A (not included in standard POS exports) |
| NielsenIQ | N/A (not included in standard POS exports) |

**Vendor notes / gotchas:**
- **SPINS:** NFP columns are SPINS Product Intelligence attributes — not available in Circana or NielsenIQ standard POS exports. They must be joined in separately via SPINS's product content database if needed for cross-vendor enrichment.
- **cross_vendor_alignment:** To add NFP attributes to Circana/NIQ data: join on normalized UPC from SPINS Product Intelligence content API or SPINS-provided product content file.

**Tags:** `schema_field` `SPINS_column` `SPINS_exclusive` `nutrition` `NFP` `product_attribute`

---

### STORAGE (SPINS) `SPINS_COL_008` `★v3`
**Full name:** Storage / Temperature Zone (SPINS Column)  
**Domain:** `product_attributes`  **Data type:** categorical string  
**Reporting level:** UPC  

**Definition:**  
SPINS product attribute indicating the temperature storage requirement of the product. Common values: 'SHELF STABLE', 'REFRIGERATED', 'FROZEN'. Used to classify products into grocery store temperature zones and for category management.

**Example:**  
_'SHELF STABLE', 'REFRIGERATED', 'FROZEN'_

**Vendor aliases / column names:**

| Vendor | Term / Column |
|--------|--------------|
| SPINS | STORAGE |
| Circana | N/A (not in standard export) |
| NielsenIQ | N/A |

**Tags:** `schema_field` `SPINS_column` `SPINS_exclusive` `storage` `temperature_zone` `product_attribute`

---

## Cross-Vendor Conflict Registry {#conflicts}

> Known definitional, coverage, naming, and schema conflicts. v3 conflicts from production CSV analysis are marked ★v3.

### CVC_001: Whole Foods Market coverage
**Description:** Whole Foods Market (WFM) appears in NielsenIQ's Food/Total Food channel (NIQ has direct data partnership). Circana projects WFM sales; it is included in their Grocery/MULO totals but cannot be accessed separately from Circana. SPINS does NOT cover WFM in any channel.

**Resolution:** For WFM-specific data, use NielsenIQ exclusively. When summing SPINS + Circana for total US, WFM is captured in the Circana portion (projected).

**Affected terms:** CHAN_001, CHAN_002, CHAN_003, CHAN_005
---

### CVC_002: Grocery channel naming
**Description:** Circana calls the supermarket/food channel 'Grocery'. NielsenIQ calls the identical universe 'Total Food.' Both have $2M ACV minimum threshold and are functionally equivalent.

**Resolution:** Map 'Grocery' (Circana) ↔ 'Total Food' (NielsenIQ) as the same canonical channel.

**Affected terms:** CHAN_005
---

### CVC_003: MULO vs. xAOC naming
**Description:** Circana's multi-outlet aggregate is MULO. NielsenIQ's equivalent is xAOC. Both include Food, Drug, Mass (with Walmart), Club, Dollar, and Military. SPINS obtains its conventional data from Circana, so SPINS MULO = Circana MULO.

**Resolution:** Map MULO (Circana/SPINS) ↔ xAOC (NielsenIQ) as canonical equivalents.

**Affected terms:** CHAN_001, CHAN_002
---

### CVC_004: Product category taxonomy misalignment
**Description:** SPINS, Circana, and NielsenIQ use proprietary classification hierarchies. The same product may be classified into different categories or segments across vendors. This is the most impactful data alignment challenge for ML model training.

**Resolution:** Require UPC as the cross-vendor join key; never rely on category strings for cross-vendor joins. Build a UPC-to-canonical-category mapping table as a pre-processing step.

**Affected terms:** HIER_003
---

### CVC_005: Velocity metric formula variation
**Description:** SPINS and Circana express velocity primarily as $/TDP (dollars per total distribution point). NielsenIQ also uses 'Unit Sales per $MM ACV' and 'SPPD (Sales Per Point of Distribution)' interchangeably. The denominators differ: TDP is a sum of %ACV values; $MM ACV weights by store ACV volume.

**Resolution:** Standardize to $/TDP for cross-vendor comparisons. When NIQ outputs use per $MM ACV, convert: $/TDP ≈ ($/MM ACV × TDP / Total Market ACV in $MM). Document which formula was used in all training data.

**Affected terms:** METR_003
---

### CVC_006: Sprouts Farmers Market coverage
**Description:** Sprouts is covered exclusively by SPINS (Natural Channel). It is NOT included in Circana or NielsenIQ totals.

**Resolution:** Brands with significant Sprouts volume must use SPINS for Sprouts data. Cannot be obtained from Circana or NIQ.

**Affected terms:** CHAN_003
---

### CVC_007: Costco coverage `★v2`
**Description:** Costco cooperates with NielsenIQ but does NOT provide data to Circana. This means xAOC (NIQ) captures Costco; MULO (Circana/SPINS) does not. Brands with significant Costco volume will show higher sales in NIQ than Circana.

**Resolution:** Use NielsenIQ exclusively for Costco-inclusive club channel total. When comparing MULO vs. xAOC, account for the Costco delta in the club channel.

**Affected terms:** NIQ_014, CHAN_001, CHAN_002
---

### CVC_008: UPC digit format variation across vendors `★v2`
**Description:** SPINS uses 12-digit UPC. Circana exports contain both UPC_10 (10-digit) and UPC_13 (EAN-13). NielsenIQ uses 14-digit GTIN. Joining on UPC across vendors without normalization causes missed matches.

**Resolution:** Normalize all UPCs to GTIN-14 (pad left with zeros to 14 digits) as the canonical join key before any cross-vendor merge. Document the padding logic in the ETL pipeline.

**Affected terms:** HIER_001, SCHEMA_005
---

### CVC_009: Regional boundary misalignment (NIQ vs. Circana) `★v2`
**Description:** NielsenIQ divides the US into 4 FMCG Regions (East, South, Central, West). Circana uses its own regional definitions that do not map 1:1. State-level or metro-market data is the only level at which both vendors can be precisely aligned geographically.

**Resolution:** Avoid region-level cross-vendor comparisons. Use state or metro market as the common geographic join key.

**Affected terms:** NIQ_011, GEO_001
---

### CVC_010: IRI export schema field name discrepancies `★v2`
**Description:** The IRI/Circana raw export schema uses column names (e.g., ACV_Weighted_Dist, Dollar_Sales_Merch, Geography_Desciption [sic]) that differ from the human-readable measure names used in SPINS and NIQ interfaces. The field 'Geography_Desciption' contains a typo ('Desciption' vs. 'Description') that appears in production exports.

**Resolution:** Maintain a field-name mapping table: ACV_Weighted_Dist → % ACV Distribution; Dollar_Sales_Merch → Dollars, Any Promo; Geography_Desciption → Geography Description. Flag the typo in ETL documentation.

**Affected terms:** SCHEMA_002, SCHEMA_003, SCHEMA_004
---

### CVC_011: ACV distribution decimal vs. percentage scale mismatch `★v3`
**Description:** Circana 'acv_weighted_distribution' is a decimal proportion (0.0–1.0). SPINS % ACV measures and NielsenIQ % ACV Distribution are expressed as percentages (0–100). Combining without conversion yields values 100x too small for Circana.

**Resolution:** Multiply Circana acv_weighted_distribution × 100 to align with SPINS/NIQ scale before any cross-vendor distribution comparison or model training feature.

**Affected terms:** DIST_002, CIRC_COL_003, SPINS_COL_011
---

### CVC_012: SPINS '% of Stores Selling' is count-weighted; Circana acv_weighted_distribution is ACV-weighted `★v3`
**Description:** These are fundamentally different distribution measures. SPINS ''% of Stores Selling' counts stores equally (numeric distribution). Circana 'acv_weighted_distribution' weights stores by their ACV share (weighted distribution). They will always differ, sometimes substantially, for the same product.

**Resolution:** Never directly compare or join SPINS '% of Stores Selling' to Circana 'acv_weighted_distribution' as if they measure the same thing. For cross-vendor distribution comparison, use % ACV Distribution from SPINS (Max % ACV or Avg % ACV), which is the ACV-weighted equivalent.

**Affected terms:** DIST_002, DIST_004, CIRC_COL_003, SPINS_COL_011
---

### CVC_013: SPINS UPC hyphenated format vs. Circana upc10/upc13 integer format `★v3`
**Description:** SPINS exports UPC as a hyphenated string ('00-52000-01016'). Circana exports two integer fields: upc10 (10-digit, no check digit, no leading zeros) and upc13 (13-digit EAN). These require different normalization steps to produce a common join key. The leading apostrophe in SPINS column name ''% of Stores Selling' is an additional parsing hazard.

**Resolution:** For SPINS→Circana join: strip hyphens from SPINS UPC → 14-digit string. Drop first two chars ('00') and last char (check digit) → validate as upc10 (10-digit). Or strip hyphens, drop leading '0' → compare to upc13. Use upc13 (EAN-13) as the preferred join key. For SPINS→NIQ: strip hyphens → 12-digit standard UPC.

**Affected terms:** HIER_001, SCHEMA_005, SPINS_COL_005
---

### CVC_014: Geography channel embedded in SPINS string vs. separate Circana columns `★v3`
**Description:** In SPINS exports, the outlet/channel type is embedded in the Geography string (e.g., 'TOTAL US - FOOD' where 'FOOD' = grocery channel). In Circana exports, this information is split across three columns: geography, projected_geography_type_name, projected_outlet_type_name, and projected_retailer_type_name.

**Resolution:** Parse SPINS Geography string by splitting on ' - ' to extract: [0]=geography_scope, [1]=outlet_type. Map SPINS outlet_type ('FOOD','DRUG','MASS' etc.) to Circana projected_outlet_type_name values for cross-vendor channel grouping.

**Affected terms:** SPINS_COL_001, CIRC_COL_007, CIRC_COL_008, CHAN_005
---

### CVC_015: Week ending date format differences across vendors `★v3`
**Description:** SPINS: 'Time Period End Date' as 'YYYY-MM-DD 00:00:00' (datetime string). Circana: '__time' as 'YYYY-MM-DDTHH:MM:SS.000Z' (ISO 8601 UTC) + 'week_ending_raw' as 'Week Ending MM-DD-YY'. NielsenIQ: 'Period End Date' varies by extract. All are Saturday dates but string formats differ.

**Resolution:** Normalize all week-ending dates to ISO date string YYYY-MM-DD: strip time from SPINS, strip 'T...' from Circana __time. Use this as the temporal join key. Build a shared calendar table mapping all three formats.

**Affected terms:** SCHEMA_001, SPINS_COL_002, CIRC_COL_001, CIRC_COL_002
---

### CVC_016: SPINS NFP/attribute columns absent from Circana and NielsenIQ exports `★v3`
**Description:** SPINS exports include product intelligence attributes directly in the data export (NFP - PROTEIN, NFP RANGES - PROTEIN VALUE, NFP - CALORIES, NFP - SUGARS, UNIT OF MEASURE, STORAGE, PACK COUNT). These columns do not exist in standard Circana or NielsenIQ exports.

**Resolution:** Treat SPINS NFP/attribute columns as a separate product content layer. To enrich Circana/NIQ data with these attributes, build a UPC-keyed product content table from SPINS Product Intelligence and join on normalized UPC. Do not assume these fields will auto-populate in cross-vendor merged datasets.

**Affected terms:** SPINS_COL_006, SPINS_COL_007, SPINS_COL_008, SPINS_COL_009, ATTR_001
---
