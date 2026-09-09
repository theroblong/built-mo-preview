# Circana Costco Warehouse Field Glossary

**File:** `(BP222) Daily Inventory Status by Warehouse_Aevah (1-1-2023_8-30-2026).csv`  
**Data product:** Circana CRX (Costco-specific warehouse + WMS/EDI feed) — distinct from standard Circana OmniMarket/InfoScan POS scan data  
**Last updated:** 2026-09-09

**Sources:** Circana Liquid Data Go CPG Dictionary · CPG Data Insights (IRI/Circana measures guides) · Scout CPG Glossary · EIA Gasoline and Diesel Fuel Update · Circana On-Shelf Availability product page · Circana Liquid Supply Chain · other-project IRI Natural Language Definitions schema · BUILT Measure Dictionary (SPINS Measures tab) · pandas profiling of BP222 file (Sept 4 2026) · online research (Sept 9 2026)

**Confidence levels:** High = confirmed from official Circana or EIA source · Medium = confirmed from industry standard or cross-referenced CPG glossaries · Low = inferred or unconfirmed — verify with Justin Fisher

---

## Critical architectural note

Standard Circana syndicated POS (OmniMarket/InfoScan) observes **weekly scan data only** and has no direct view of inventory, OOS, On Order, or In Transit. The BP222 file is from Circana's **CRX product**, which pulls from Costco's own warehouse management system (WMS) and EDI. The inventory fields (F-07 through F-13, F-32) come from a supply chain feed, not POS scan data. This distinction is essential when reconciling BP222 data with SPINS.

---

## Dimension Fields (F-01 – F-04)

### F-01 · Item
**Definition:** Product identifier as assigned by Costco. Costco assigns a proprietary 7-digit item number that does not always map 1:1 to a UPC — the same UPC may appear under multiple item numbers across time periods or warehouse types, and a variety pack may have a single item number covering multiple component UPCs.  
**Confidence:** High  
**Observed in file:** String label (e.g., "Item XYZ"); 29 distinct item variants in BP222  
**SPINS crosswalk:** Must join to BUILT product master (Item_Assumptions tab) to resolve to SPINS UPC. See crosswalk gap documentation in `15-aevah-platform-architecture.md`.  
**Caveat:** Pandas profiling found the same physical SKU appears under `000120000000000`, `999999999999999`, `000000000000000`, and an actual UPC. Deduplicate before analysis.

---

### F-02 · Venue
**Definition:** The individual Costco warehouse location (a specific physical warehouse building, not a channel aggregate or region). Costco's term for a warehouse is "warehouse" or "club." Each venue is a distinct DC/retail combined location in Costco's floor-loaded model.  
**Confidence:** High  
**Observed in file:** String (e.g., "WAREHOUSE 25 RENO"); 909 distinct venues in BP222  
**SPINS crosswalk:** No direct SPINS equivalent — SPINS reports Costco at the retailer level, not individual warehouse level.

---

### F-03 · Time
**Definition:** The specific date or week-ending date of the record. Based on the BP222 format ("1 week ending MM-DD-YYYY"), this indicates a weekly supply chain snapshot, not a daily transaction. Despite the file name saying "Daily," the period grain is weekly — Costco likely generates WMS snapshots weekly.  
**Confidence:** Medium (verify with Justin Fisher whether grain is daily or weekly)  
**Observed in file:** String format "1 week ending MM-DD-YYYY"; Jan 2023–Aug 2026 (192 weeks)  
**Note:** The research agent confirmed CRX is a daily-capable product, but our file header format ("1 week ending") suggests BUILT's extract is weekly-aggregated.

---

### F-04 · Region [Region_warehouse]
**Definition:** Costco's internal warehouse cluster groupings — NOT Circana's standard geographic markets (DMA, IRI Region, etc.). Costco divides its warehouses into regional operating groups for supply chain management.  
**Confidence:** Medium  
**Observed in file:** 11 regions including E-Commerce (largest by volume in file), Midwest, Northeast, etc.  
**SPINS crosswalk:** Does not map to SPINS geography hierarchy. Costco reports as a single retail account in SPINS.

---

## Sales Fields (F-05 – F-06)

### F-05 · Dollar Sales
**Definition:** Total dollar amount of retail sales recorded at the warehouse for the period. Reflects units × retail price at checkout. Retailer-applied discounts (Costco instant savings / coupon book) are reflected in the price at scan. Manufacturer coupons are NOT reflected — they are redeemed at the clearing house and invisible to Circana scan data.  
**Confidence:** High  
**Source:** Circana Liquid Data Go CPG Dictionary; other-project IRI schema  
**Observed in file:** String-formatted `$X,XXX.XX` and `($X.XX)` for negatives — must strip before numeric use. ~5.3M of 5.4M rows are null; useful signal in ~86K rows.  
**SPINS equivalent:** `Dollars` (direct match in concept; methodology identical)  
**Canonical rule:** SPINS `Dollars` = retail scanner revenue, NOT BUILT's manufacturer revenue. Never substitute for NetSuite gross sales.

---

### F-06 · Unit Sales
**Definition:** Total number of units sold at retail scan during the period. In Costco's context, "unit" = one club pack (e.g., a 4-pack or 12-pack), not an individual bar.  
**Confidence:** High  
**Source:** Circana Liquid Data Go CPG Dictionary; other-project IRI schema  
**Observed in file:** String-formatted — must strip before numeric use  
**SPINS crosswalk:** SPINS `Units` at Costco = club packs. To convert to bars: `Unit Sales × PACK COUNT`. For BUILT products, use EQ Units convention (Units × PACK COUNT = bars). **Cannot compare F-06 directly to SPINS Unit Sales at other retailers without pack normalization.**  
**Canonical rule:** EQ Units = Units × PACK COUNT = bars. The atomic unit for consumption-side analysis.

---

## Inventory Fields (F-07 – F-13)

> These fields come from Costco's WMS/EDI system feed (CRX product), not POS scan. All inventory measures are at the **warehouse DC level**, not the retail floor. Costco uses a floor-loaded model where back-room and floor stock are not separated — "on hand" includes all warehouse stock.

### F-07 · Days of Supply
**Definition:** Estimated number of days of inventory remaining before stockout, calculated as: `On Hand ÷ Daily demand rate`. The daily demand rate is typically derived from recent average daily unit sales.  
**Confidence:** High (standard supply chain KPI)  
**Source:** Standard supply chain terminology (APQC, Profit.co, Infor)  
**Observed in file:** ~100% null in BP222. Field exists in schema but Costco may not populate it for BUILT's items or in this extract configuration.  
**Important:** Warehouse DOS ≠ store shelf DOS. A warehouse showing 14 DOS may have floor inventory already picked for customer carts.  
**Ask Justin Fisher:** Whether Costco populates this field for BUILT's SKUs, or whether it's calculated by Circana and suppressed below a threshold.

---

### F-08 · Inventory Turns
**Definition:** Rate at which inventory is sold and replaced over a period. In scan data context (no COGS): `Annualized Unit Sales ÷ Average On Hand Units`. Higher = faster-moving inventory.  
**Confidence:** Medium  
**Source:** Standard supply chain KPI; methodology varies by provider  
**Observed in file:** Mostly null in BP222  
**Note:** Circana likely calculates this from unit sales ÷ average on hand in the WMS feed. Costco's floor-loaded model makes this metric meaningful at the warehouse level.

---

### F-09 · Inventory On Hand
**Definition:** Total units of the product currently in stock at the warehouse, including all back-room and floor-loaded inventory. This is a point-in-time snapshot (end of period).  
**Confidence:** High  
**Source:** Standard WMS field; Circana CRX supply chain feed  
**Observed in file:** Values appear in multiples of 525 — consistent with pallet-level ordering (525 = case/pallet unit for Costco BUILT items per Brands LE Costco_Build tab)  
**Reconciliation check:** `On Hand(t) ≈ On Hand(t-1) + Quantity Received(t) − Unit Sales(t)` — use this to validate data integrity  
**Caveat:** Warehouse on hand ≠ shelf availability. A warehouse showing positive on hand may still have floor stockout if product hasn't been pulled from back room.

---

### F-10 · On Order
**Definition:** Open purchase order quantity committed by Costco to BUILT but not yet received. This is Costco's pending order, not BUILT's production plan or ERP sales order.  
**Confidence:** High  
**Source:** Standard EDI/WMS field; Circana CRX  
**Observed in file:** Multiples of 525 (0, 525, 1050, 1575…) — confirms pallet-level ordering  
**Important:** On Order comes from Costco's purchase order system (EDI), not from BUILT's NetSuite. These two systems should agree but may differ due to timing.

---

### F-11 · In Transit
**Definition:** Units that have been shipped by BUILT (or a distributor) but not yet received at the Costco warehouse. Represents inventory in the supply chain pipeline.  
**Confidence:** Medium  
**Source:** Standard supply chain term; exact leg definition (BUILT-to-DC or DC-to-warehouse) requires confirmation  
**Observed in file:** Present (not profiled in detail)  
**Ask Justin Fisher:** Which leg does "In Transit" capture — BUILT dock to Costco DC, or Costco DC to individual warehouse?

---

### F-12 · Quantity Received
**Definition:** Units received at the warehouse during the reporting period. Expected to be zero most periods, with spikes on delivery dates.  
**Confidence:** High  
**Source:** Standard WMS receiving field; Circana CRX  
**Observed in file:** Multiples of 525 — pallet receipts  
**Validation:** Use `On Hand(t) ≈ On Hand(t-1) + Quantity Received(t) − Unit Sales(t)` to verify

---

### F-13 · OOS
**Definition:** Out-of-Stock indicator. In WMS-sourced data, OOS is derived from `On Hand = 0`, not from a physical shelf observation or sensor. **Warehouse OOS ≠ floor OOS** — a warehouse can show OOS while floor display still has product from a prior delivery.  
**Confidence:** High  
**Source:** Circana On-Shelf Availability product page; standard WMS derivation  
**Observed in file:** ~100% null in BP222 — field exists in schema but not populated for BUILT's extract  
**Note:** May be populated only for items with sufficient on-hand history, or may require a separate Circana On-Shelf Availability module.

---

## Distribution Fields (F-14 – F-15)

### F-14 · Warehouses Selling
**Definition:** Number of Costco warehouses that recorded at least one unit sale of the item during the period. Costco's equivalent of "% of stores selling" but expressed as a count.  
**Confidence:** High  
**SPINS equivalent:** `# of Stores Selling` (conceptually identical; count-based, not ACV-weighted)  
**Note:** `Warehouses Selling ÷ Number of Warehouses` = BUILT's numeric distribution within Costco. This is the best TDP proxy available for Costco.

---

### F-15 · Number of Warehouses
**Definition:** Total number of Costco warehouses in the reporting scope. The denominator for distribution calculations.  
**Confidence:** High  
**Observed in file:** 909 warehouses in BP222 (includes all Costco US + Canada locations in scope)  
**Note:** Costco opens new warehouses quarterly. As of late 2024, US location count is approximately 580–600; 909 may include Canada and other international. Confirm scope with Justin Fisher.  
**Usage:** `Warehouses Selling ÷ Number of Warehouses × 100` = % distribution at Costco

---

## Product Attribute Fields (F-16 – F-17)

### F-16 · Flavor
**Definition:** Product flavor attribute as classified by Circana's product hierarchy. May differ from BUILT's internal flavor naming.  
**Confidence:** Medium  
**SPINS crosswalk:** Map to `spins_flavor_raw` and then apply `flavor_mapping` lookup (built_specific_flavor_mapping.csv) for canonical flavor.

---

### F-17 · Flavor / Scent
**Definition:** Combined flavor and scent descriptor at a more granular level than F-16. In the BP222 file, this includes values like "VARIETY PACK" and "COCONUT & COOKIE & CREAM."  
**Confidence:** Medium  
**Observed in file:** Values: "VARIETY PACK", "COCONUT & COOKIE & CREAM" — confirmed BUILT product descriptors  
**Note:** Variety packs complicate unit-to-bar conversion; each variety pack item number covers multiple component UPCs.

---

## Promotion Fields (F-18 – F-27)

> Costco's promotional model is almost entirely Instant Savings / coupon book events — typically 4-week blocks of a fixed dollar discount ($4 or $5 for BUILT). Traditional TPR, feature ad, and display promotions as used by conventional grocery retailers do not apply in the same way. This affects how Promoted/Non-Promoted decomposition should be interpreted.

### F-18 · % Discount
**Definition:** The percentage discount applied to the item during promoted periods. Formula: `(Base Price − Promotional Price) ÷ Base Price × 100`. IRI/Circana defines a TPR (Temporary Price Reduction) threshold as ≥5% reduction from base price.  
**Confidence:** High  
**Source:** CPG Data Insights; Circana Liquid Data Go CPG Dictionary

---

### F-19 · Average Coupon Value
**Definition:** The average dollar value of the coupon applied per unit during the period. At Costco, this corresponds to the Instant Savings coupon book discount (e.g., $4.00 or $5.00 off per club pack).  
**Confidence:** High  
**Source:** CPG Data Insights glossary; Circana promo methodology  
**Observed in file:** $4.00 or $5.00 values — confirms Costco instant savings events  
**Important:** This is the Costco coupon book (retailer-funded), NOT manufacturer coupons (which are invisible to scan data).

---

### F-20 · Average Promoted Price
**Definition:** The average retail price paid by customers during weeks when any promotional support (TPR, coupon, feature, display) was active.  
**Confidence:** High  
**Source:** Circana Liquid Data Go CPG Dictionary  
**SPINS equivalent:** `ARP, Promo` (direct match)

---

### F-21 · Coupon Dollars
**Definition:** The total dollar value of coupon discounts applied during the period. In the BP222 file, negative values indicate the discount being backed out of revenue (i.e., the coupon value is subtracted from Dollar Sales).  
**Confidence:** High  
**Observed in file:** Negative values present — discount backed out convention

---

### F-22 · Coupon Units
**Definition:** Total number of units sold using a coupon during the period.  
**Confidence:** High

---

### F-23 · Non Promoted Dollars
**Definition:** Dollar sales occurring during weeks when no promotional support was active. This is an observed fact (no promo activity detected), NOT the same as Base Dollar Sales (which is a modeled estimate of what sales would have been without promotion in any week). Non-Promoted is a filter; Base is a model output.  
**Confidence:** High  
**Source:** Circana Liquid Data Go CPG Dictionary; CPG Data Insights  
**SPINS equivalent:** Closest to filtering on non-promo weeks; not directly equivalent to `Base Dollars`  
**Critical distinction:** `Non Promoted ≠ Base Sales`. Base Sales is a statistical model estimating demand absent promotion in all weeks. Non Promoted simply sums sales in weeks with no promo flag.

---

### F-24 · Non Promoted Units
**Definition:** Unit sales occurring during weeks when no promotional support was active.  
**Confidence:** High  
**Source:** Circana Liquid Data Go CPG Dictionary  
**Same Non-Promoted ≠ Base caveat applies as F-23.**

---

### F-25 · Promoted Dollars
**Definition:** Dollar sales occurring during weeks when any promotional support was active (Circana calls this "Any Merch"; NielsenIQ calls it "Any Promo"). Includes TPR, feature ad, display, or coupon-active weeks. For Costco, this primarily means Instant Savings coupon book event weeks. Negative values in some rows indicate coupon discount adjustments.  
**Confidence:** High  
**Source:** Circana Liquid Data Go CPG Dictionary; CPG Data Insights; other-project IRI schema (`Dollar_Sales_Merch`)  
**SPINS equivalent:** `Dollars, Any Promo` / `Incr Dollars + Base Dollars during promo weeks` — not identical

---

### F-26 · Promoted Units
**Definition:** Unit sales occurring during weeks when any promotional support was active.  
**Confidence:** High  
**Source:** Circana Liquid Data Go CPG Dictionary  
**SPINS equivalent:** `Units, Any Promo`  
**Important:** Promoted Units ≠ Incremental Units. Promoted Units is total units during promo weeks (includes baseline demand). Incremental Units is the lift above modeled baseline. Do not substitute.

---

### F-27 · Total Discount Dollars
**Definition:** Total dollar value of all discounts applied during the period, combining coupon and any other price reductions.  
**Confidence:** Medium  
**Note:** Likely `Coupon Dollars + any TPR markdown dollars`. At Costco, primarily driven by Instant Savings coupon book value × units sold.

---

## Macro Signal Fields (F-28 – F-31)

> Circana embeds national average fuel prices from the U.S. Energy Information Administration (EIA) Gasoline and Diesel Fuel Update, released each Monday. All four fuel grades reflect **weekly national averages** — all days within a given week share the same EIA value. PADD district and state-level breakdowns are available from EIA if needed.
> 
> These are included as macro demand signals — fuel costs correlate with consumer purchasing behavior (drive-time trade area effects, disposable income pressure). The Brands LE Macro_Index model ranks Gas Price as a macro indicator with r=0.438 (weakest of the 17 macro indicators; CPI is #1 at r=0.983).

### F-28 · Average Diesel Fuel Price per gallon
**Definition:** National average retail price for diesel fuel (per gallon), weekly.  
**EIA Series:** `EMD_EPD2D_PTE_NUS_DPG`  
**Confidence:** High  
**Observed in file:** ~93K non-null of 5.4M rows (sparse — appears for a subset of time/geography combinations)

---

### F-29 · Average Regular Gas Price per gallon
**Definition:** National average retail price for regular unleaded gasoline (per gallon), weekly.  
**EIA Series:** `EMM_EPMR_PTE_NUS_DPG`  
**Confidence:** High

---

### F-30 · Average Mid-grade Gas Price per gallon
**Definition:** National average retail price for mid-grade unleaded gasoline (per gallon), weekly.  
**EIA Series:** `EMM_EPMM_PTE_NUS_DPG`  
**Confidence:** High

---

### F-31 · Average Premium Gas Price per gallon
**Definition:** National average retail price for premium unleaded gasoline (per gallon), weekly.  
**EIA Series:** `EMM_EPMP_PTE_NUS_DPG`  
**Confidence:** High  
**Note:** EIA data is freely available via API. If Circana's embedded values need to be refreshed or back-filled, use the FRED API series `GASDESW` (weekly U.S. regular conventional gas price) as a proxy — already integrated into Mo's FRED macro context tile.

---

## Availability Field (F-32)

### F-32 · In Stock %
**Definition:** Percentage of authorized Costco warehouse locations that have the item in stock (On Hand > 0) during the period. Formula: `Locations In Stock ÷ Total Authorized Locations × 100`. Based on WMS on-hand data, not physical shelf observation. Industry target: ≥95%.  
**Confidence:** Medium  
**Source:** Circana On-Shelf Availability product page; standard retail availability KPI  
**Observed in file:** ~100% null in BP222 — same situation as F-13 (OOS); either unpopulated for BUILT or requires a separate Circana OSA module  
**Relationship to OOS:** `In Stock % = 100% − OOS Rate`. If one is populated, the other can be derived.  
**Caveat:** Warehouse WMS view. A warehouse showing 100% in stock may still have shelf-level stockout if replenishment hasn't been picked.

---

## Open questions for Justin Fisher

1. **Grain:** Is BP222 a daily or weekly snapshot? The "1 week ending" format suggests weekly, but the file name says "Daily."
2. **Venue scope:** Does the 909-warehouse count include international? Costco US alone is ~580–600 locations.
3. **In Transit definition:** Which leg — BUILT to Costco DC, or Costco DC to individual warehouse?
4. **OOS / In Stock % / Days of Supply:** Why are these 100% null for BUILT's items? Is this a module/subscription question or a data availability question?
5. **Item number → UPC mapping:** Does Circana provide a reference table linking Costco 7-digit item numbers to UPCs, or does BUILT need to maintain this crosswalk?
6. **Coupon timing:** Are the $4/$5 coupon book events flagged by week, or derived from the Promoted/Non-Promoted split? (Needed to align with BUILT's promo calendar for E1 feature engineering.)

---

## Field summary table

| # | Field | Category | Confidence | SPINS equivalent | Null rate |
|---|-------|----------|-----------|-----------------|-----------|
| F-01 | Item | Dimension | High | UPC (after crosswalk) | — |
| F-02 | Venue | Dimension | High | (none) | — |
| F-03 | Time | Dimension | Medium | `Time Period End Date` | — |
| F-04 | Region [Region_warehouse] | Dimension | Medium | (none — Costco-internal) | — |
| F-05 | Dollar Sales | Sales | High | `Dollars` | ~98% null |
| F-06 | Unit Sales | Sales | High | `Units` (club pack, not bar) | needs strip |
| F-07 | Days of Supply | Inventory | High | (none) | ~100% null |
| F-08 | Inventory Turns | Inventory | Medium | (none) | mostly null |
| F-09 | Inventory On Hand | Inventory | High | (none) | pallet multiples |
| F-10 | On Order | Inventory | High | (none) | pallet multiples |
| F-11 | In Transit | Inventory | Medium | (none) | — |
| F-12 | Quantity Received | Inventory | High | (none) | pallet multiples |
| F-13 | OOS | Inventory | High | (none) | ~100% null |
| F-14 | Warehouses Selling | Distribution | High | `# of Stores Selling` | — |
| F-15 | Number of Warehouses | Distribution | High | (total store count) | — |
| F-16 | Flavor | Product | Medium | `spins_flavor_raw` | — |
| F-17 | Flavor / Scent | Product | Medium | (flavor canonical) | — |
| F-18 | % Discount | Promo | High | (derived) | — |
| F-19 | Average Coupon Value | Promo | High | (none direct) | — |
| F-20 | Average Promoted Price | Promo | High | `ARP, Promo` | — |
| F-21 | Coupon Dollars | Promo | High | (none direct) | negative values |
| F-22 | Coupon Units | Promo | High | (none direct) | — |
| F-23 | Non Promoted Dollars | Promo | High | ≠ `Base Dollars` | — |
| F-24 | Non Promoted Units | Promo | High | ≠ `Base Units` | — |
| F-25 | Promoted Dollars | Promo | High | `Dollars, Any Promo` | negative in some rows |
| F-26 | Promoted Units | Promo | High | `Units, Any Promo` | — |
| F-27 | Total Discount Dollars | Promo | Medium | (derived) | — |
| F-28 | Average Diesel Fuel Price per gallon | Macro | High | FRED `GASDESW` (proxy) | sparse |
| F-29 | Average Regular Gas Price per gallon | Macro | High | FRED `GASDESW` | sparse |
| F-30 | Average Mid-grade Gas Price per gallon | Macro | High | (EIA only) | sparse |
| F-31 | Average Premium Gas Price per gallon | Macro | High | (EIA only) | sparse |
| F-32 | In Stock % | Availability | Medium | (none) | ~100% null |
