# Mo Data Catalog — Transformation & Derivation Register

Living register of all field-level transformations, derivations, and data quirks across Mo data sources.
Every derived metric used in queries or the Mo API must have an entry here.

**Principle:** Druid tables store source data faithfully. Derived fields are computed at query/API time
using the canonical formulas below. Where a pre-computed column exists in Druid for performance,
the catalog formula is authoritative — if the stored value diverges from the formula, the formula wins.

---

## Source: `built_costco_crx_weekly` (Circana CRX BP222)

**Raw file:** Circana BP222 — Costco weekly POS data by item × warehouse × week  
**Preprocessing script:** `scripts/MO_74_crx_bp222_preprocess.py`  
**Druid table:** `built_costco_crx_weekly`  
**Grain:** item_desc × warehouse_name × week_ending  
**History:** 2023-01-01 → current (193 weeks as of Sept 2026)  
**Row count:** ~5.4M (28 item_desc variants × 918 warehouses × 193 weeks)

### Column Renames (BP222 → Druid)

All BP222 headers are renamed to snake_case at ingest. No values are changed.

| BP222 Header | Druid Column | Type | Notes |
|---|---|---|---|
| Item | `item_desc` | string | Full UPC-prefix + description string; join key |
| Venue | `warehouse_name` | string | Costco warehouse name |
| Time | `week_ending` → `__time` | timestamp | Parsed from "N week ending MM-DD-YYYY"; always a Sunday |
| Region [ Region_warehouse ] | `region` | string | 11 Costco regions |
| Dollar Sales | `dollar_sales` | double | Circana currency format parsed: "$1,234.56" → 1234.56; "($19.99)" → -19.99 |
| Unit Sales | `unit_sales` | double | 1 unit = 1 Club Pack (13 bars for original; 14 for Puffs) |
| Days of Supply | `days_of_supply` | double | Currently all null — Circana investigating |
| Inventory Turns | `inventory_turns` | double | Currently all null |
| Inventory On Hand | `on_hand` | double | Currently all null |
| On Order | `on_order` | double | Currently all null |
| In Transit | `in_transit` | double | Currently all null |
| Quantity Received | `qty_received` | double | |
| OOS | `oos` | double | Currently all null — Circana investigating |
| Warehouses Selling | `warehouses_selling` | double | = 1 per row (each row is one warehouse); sum across rows = total WH-weeks |
| Number of Warehouses | `num_warehouses` | double | |
| Flavor | `flavor` | string | |
| Flavor / Scent | `flavor_scent` | string | |
| % Discount | `pct_discount` | double | |
| Average Coupon Value | `avg_coupon_value` | double | |
| Average Promoted Price | `avg_promoted_price` | double | |
| Coupon Dollars | `coupon_dollars` | double | |
| Coupon Units | `coupon_units` | double | ⚠️ **Stored as NEGATIVE by Circana** — see quirks below |
| Non Promoted Dollars | `non_promoted_dollars` | double | |
| Non Promoted Units | `non_promoted_units` | double | |
| Promoted Dollars | `promoted_dollars` | double | |
| Promoted Units | `promoted_units` | double | Positive value; use this for MVM detection |
| Total Discount Dollars | `total_discount_dollars` | double | |
| Average Diesel Fuel Price per gallon | `fuel_price_diesel` | double | |
| Average Regular Gas Price per gallon | `fuel_price_regular` | double | |
| Average Mid-grade Gas Price per gallon | `fuel_price_midgrade` | double | |
| Average Premium Gas Price per gallon | `fuel_price_premium` | double | |
| In Stock % | `in_stock_pct` | double | Currently all null |

### Derived Fields

These are computed at query/API time. Pre-computed columns exist in Druid for performance but the
formula below is canonical.

---

#### `is_mvm`

**Definition:** 1 if this row represents a week when the item was on MVM (Multi-Vendor Mailer / Instant Rebate Coupon), 0 otherwise.

**Formula:**
```sql
CASE WHEN promoted_units > 0 THEN 1 ELSE 0 END AS is_mvm
```

**Source columns:** `promoted_units`

**⚠️ Do NOT use `coupon_units` for this.** Circana stores `coupon_units` as a negative number. Using `coupon_units > 0` never fires on real MVM rows. Confirmed via profiling: `SUM(coupon_units) = -937,695`; `SUM(promoted_units) = +937,695` (exact mirror). The two columns are complementary, not independent.

**Identity check:**
```sql
-- Must hold true: non_promoted_units + promoted_units = unit_sales
SUM(non_promoted_units) + SUM(promoted_units) = SUM(unit_sales)
-- Verified: 11,819,713 + 937,695 = 12,757,408 ✓
```

---

#### `dpwpw`

**Definition:** Dollar Sales Per Warehouse Per Week — the primary Costco velocity metric. Normalizes revenue by the number of actively selling warehouses to produce a comparable per-location rate.

**Formula:**
```sql
CASE
  WHEN warehouses_selling > 0 AND dollar_sales IS NOT NULL
  THEN dollar_sales / warehouses_selling
  ELSE NULL
END AS dpwpw
```

**Source columns:** `dollar_sales`, `warehouses_selling`

**Why DPWPW and not raw dollar_sales:** Costco unit = Club Pack (13–14 bars); units are not directly comparable to SPINS base_units. Dollar velocity normalizes across the growing warehouse count, making trend analysis valid across the distribution build-out period.

**Why not "Average $/WH Selling":** Circana's native "Average $/WH Selling" metric aggregates over the full report period and overcounts. DPWPW computed week-by-week then averaged is the correct approach.

---

### Data Quirks — Query-Time Handling Required

#### 1. UPC Prefix Filtering

BP222 `item_desc` contains 4 prefix variants per item. Only the real UPC prefix carries actual sales:

| Prefix | Meaning | Action |
|--------|---------|--------|
| `000840229...` | Real UPC — actual POS scan sales | **Include** |
| `000000000...` | Cashier key-in / e-commerce placeholder | Exclude from sales analysis |
| `999999999...` | Returns / credit adjustments (negative values) | Exclude from sales analysis |
| `000120000...` | Returns / credit adjustments (negative values) | Exclude from sales analysis |

**Filter for real sales:**
```sql
WHERE item_desc LIKE '000840229%'
```

#### 2. UPC Extraction for SPINS Join

To join `built_costco_crx_weekly` to `built_filtered_weekly` on UPC:
```sql
CAST(SUBSTRING(item_desc, 1, 15) AS BIGINT) AS upc
-- '000840229305933-...' → 840229305933
-- Joins to built_filtered_weekly.upc directly
```

#### 3. Sparsity Pattern

98.4% of rows have null `dollar_sales`. This is by design — the table holds all item × warehouse × week combinations regardless of sales activity. Always filter `WHERE dollar_sales IS NOT NULL` for sales analysis.

#### 4. `coupon_units` Sign

`coupon_units` is a negative number in Circana's data. Do not use for any positive-value comparison. Raw value stored as-is per data stewardship policy; the sign is a Circana convention, not a data error.

#### 5. Unit Definition

1 CRX unit = 1 Club Pack. Pack sizes:
- Original bar (item 1664930): 13 bars per Club Pack
- All Puff variants: 14 bars per Club Pack

Do not compare `unit_sales` directly to SPINS `base_units` without pack conversion.

---

## Source: `built_filtered_weekly` (SPINS)

*Full derivation register TBD — document as Mo API queries are built out.*

Key known derivations:
- `upc` — SPINS join key to `built_costco_crx_weekly` via UPC extraction above
- `week_ending` — Sunday; direct join to CRX `__time` (both are Sunday week-end dates)

---

## Source: NS2 Shipment Data (`ns2.transaction` + `ns2.transactionLine`)

*Full derivation register TBD — document as NS2 queries are built.*

Key known derivations:
- **Bars shipped** = `SUM(transactionLine.custcolbars_per_line)` per customer per week — equivalized unit; do not use raw `quantity`
- **QA cross-check** = `transaction.custbody1` ("Bars Per Order") should equal `SUM(custcolbars_per_line)` across lines
- **Filter** = `transaction.abbrevtype = 'Invoice'` and `transactionLine.mainline = 'F'` and `item.isinactive = 'F'`

---

*Last updated: 2026-09-17*  
*Maintained by: Aevah / Jason Brazeal*
