# Costco CRX → Druid Ingestion Guide

**Target table:** `costco_crx_weekly`  
**Source file:** `(BP222) Daily Inventory Status by Warehouse_Aevah (1-1-2023_8-30-2026).csv`  
**Prepared by:** MO_74 preprocessing script  
**Last updated:** 2026-09-15

---

## Step 1 — Run the preprocessing script

```bash
cd /path/to/FirstAgent
pip install pandas pyarrow   # if not already installed

python scripts/MO_74_crx_bp222_preprocess.py \
  "/path/to/(BP222) Daily Inventory Status by Warehouse_Aevah (1-1-2023_8-30-2026).csv" \
  --output outputs/costco_crx_weekly.parquet
```

Expected output:
```
Loaded  5,410,368 rows x 32 columns
Output  5,410,XXX rows
Dates   2023-01-08 → 2026-08-31
Items   29 distinct SKU descriptions
WHs     909 distinct warehouses
MVM wks ~XX,XXX rows flagged as MVM
Sparse  ~5,300,000 rows with null dollar_sales (~98.0%)
Written → outputs/costco_crx_weekly.parquet  (~XXX MB)
```

> **Note on sparsity:** ~98% of rows have null `dollar_sales`. This is expected —
> most warehouse × item × week combinations have no sales. Druid handles sparse
> data efficiently; do not pre-filter nulls. Keep all rows so distribution
> (Warehouses Selling) and inventory metrics are accurate.

---

## Step 2 — Upload Parquet to MinIO

```bash
# Upload to the Circana bucket (same bucket as BP222 source)
mc cp outputs/costco_crx_weekly.parquet \
   <minio-alias>/circana/costco/costco_crx_weekly.parquet
```

---

## Step 3 — Druid batch ingestion spec

Save the following as `costco_crx_ingest.json` and submit to the Druid console
(Load data → Local disk or S3/MinIO → Paste spec):

```json
{
  "type": "index_parallel",
  "spec": {
    "ioConfig": {
      "type": "index_parallel",
      "inputSource": {
        "type": "s3",
        "uris": ["s3://<bucket>/circana/costco/costco_crx_weekly.parquet"]
      },
      "inputFormat": {
        "type": "parquet"
      }
    },
    "dataSchema": {
      "dataSource": "costco_crx_weekly",
      "timestampSpec": {
        "column": "week_ending",
        "format": "yyyy-MM-dd"
      },
      "dimensionsSpec": {
        "dimensions": [
          { "type": "string", "name": "item_desc" },
          { "type": "string", "name": "warehouse_name" },
          { "type": "string", "name": "region" },
          { "type": "string", "name": "week_ending" },
          { "type": "string", "name": "flavor" },
          { "type": "string", "name": "flavor_scent" },
          { "type": "long",   "name": "is_mvm" }
        ]
      },
      "metricsSpec": [
        { "type": "doubleSum",  "name": "unit_sales",            "fieldName": "unit_sales" },
        { "type": "doubleSum",  "name": "dollar_sales",          "fieldName": "dollar_sales" },
        { "type": "doubleSum",  "name": "warehouses_selling",    "fieldName": "warehouses_selling" },
        { "type": "doubleSum",  "name": "num_warehouses",        "fieldName": "num_warehouses" },
        { "type": "doubleSum",  "name": "on_hand",               "fieldName": "on_hand" },
        { "type": "doubleSum",  "name": "on_order",              "fieldName": "on_order" },
        { "type": "doubleSum",  "name": "in_transit",            "fieldName": "in_transit" },
        { "type": "doubleSum",  "name": "qty_received",          "fieldName": "qty_received" },
        { "type": "doubleSum",  "name": "coupon_units",          "fieldName": "coupon_units" },
        { "type": "doubleSum",  "name": "coupon_dollars",        "fieldName": "coupon_dollars" },
        { "type": "doubleSum",  "name": "avg_coupon_value",      "fieldName": "avg_coupon_value" },
        { "type": "doubleSum",  "name": "avg_promoted_price",    "fieldName": "avg_promoted_price" },
        { "type": "doubleSum",  "name": "pct_discount",          "fieldName": "pct_discount" },
        { "type": "doubleSum",  "name": "promoted_units",        "fieldName": "promoted_units" },
        { "type": "doubleSum",  "name": "promoted_dollars",      "fieldName": "promoted_dollars" },
        { "type": "doubleSum",  "name": "non_promoted_units",    "fieldName": "non_promoted_units" },
        { "type": "doubleSum",  "name": "non_promoted_dollars",  "fieldName": "non_promoted_dollars" },
        { "type": "doubleSum",  "name": "dpwpw",                 "fieldName": "dpwpw" },
        { "type": "doubleSum",  "name": "fuel_price_regular",    "fieldName": "fuel_price_regular" }
      ],
      "granularitySpec": {
        "type": "uniform",
        "segmentGranularity": "MONTH",
        "queryGranularity": "DAY",
        "rollup": false
      }
    },
    "tuningConfig": {
      "type": "index_parallel",
      "maxRowsInMemory": 25000,
      "maxNumConcurrentSubTasks": 2
    }
  }
}
```

> **rollup: false** — keep all rows at item × warehouse × week grain. Mo needs
> warehouse-level filtering (Status=3 selling WHs, region drill-down, WH 847
> e-commerce separate). Do not roll up.

---

## Step 4 — Post-load verification queries

Run these in the Druid console after ingestion:

```sql
-- Row count and date range
SELECT COUNT(*) AS rows,
       MIN(__time) AS earliest,
       MAX(__time) AS latest
FROM costco_crx_weekly

-- Expected: ~5.4M rows, 2023-01-08 to 2026-08-31

-- Distinct items and warehouses
SELECT COUNT(DISTINCT item_desc) AS items,
       COUNT(DISTINCT warehouse_name) AS warehouses
FROM costco_crx_weekly

-- Expected: 29 items, ~909 warehouses

-- MVM weeks flagged
SELECT SUM(is_mvm) AS mvm_rows
FROM costco_crx_weekly

-- Selling WH filter (Status=3 proxy: non-RCTR, non-DDC, non-MDO, non-INN names)
-- Until warehouse status lookup is loaded, approximate by excluding known non-selling patterns:
SELECT warehouse_name, SUM(unit_sales) AS total_units
FROM costco_crx_weekly
WHERE warehouse_name NOT LIKE '%RCTR%'
  AND warehouse_name NOT LIKE '%DDC%'
  AND warehouse_name NOT LIKE '%MDO%'
  AND warehouse_name NOT LIKE '%INN%'
  AND unit_sales > 0
GROUP BY warehouse_name
ORDER BY total_units DESC
LIMIT 20

-- DPWPW by week (velocity trend)
SELECT TIME_FLOOR(__time, 'P1W') AS week,
       SUM(dollar_sales) / NULLIF(SUM(warehouses_selling), 0) AS dpwpw_avg
FROM costco_crx_weekly
WHERE unit_sales > 0
GROUP BY 1
ORDER BY 1
```

---

## Schema reference

| Column | Type | Source | Notes |
|---|---|---|---|
| `week_ending` | string (date) | BP222 "Time" | Sunday of Costco Mon–Sun week. Direct join to SPINS `week_ending`. |
| `item_desc` | string | BP222 "Item" | SKU description. Join to item table (pending Justin) for UPC. |
| `warehouse_name` | string | BP222 "Venue" | Full WH name (e.g., "WAREHOUSE 25 RENO"). |
| `region` | string | BP222 "Region" | 11 Costco regions incl. E-Commerce. |
| `is_mvm` | long (0/1) | derived | 1 = Promoted Units > 0 = MVM/instant savings week. ⚠️ Do NOT use `coupon_units` — Circana stores it as a negative value. |
| `dpwpw` | double | derived | Dollar Sales ÷ Warehouses Selling. Best velocity metric for Costco. |
| `unit_sales` | double | BP222 | 1 unit = 1 Club Pack (16 or 18 bars). NOT individual bars. |
| `dollar_sales` | double | BP222 | ~98% null (most WH × item × week have no sales). Expected. |
| `warehouses_selling` | double | BP222 | Count of WHs with sales. TDP proxy when divided by 702 total selling WHs. |
| `on_hand` | double | BP222 | Multiples of 525 = pallet-level inventory. Not consumer demand. |
| `on_order` | double | BP222 | Pallet ordering pattern. |
| `coupon_units` | double | BP222 | ⚠️ Stored as a **negative value** by Circana. Do NOT use for MVM detection — use `is_mvm` or `promoted_units > 0`. |
| `avg_coupon_value` | double | BP222 | $4.00 or $5.00 for BUILT instant savings. |
| `fuel_price_regular` | double | BP222 | Circana embedded macro signal. ~93K of 5.4M non-null. |
| `oos` / `in_stock_pct` | double | BP222 | ~100% null. Circana investigating. Do not use. |

---

## Pending before full integration

| Item | Owner | Status |
|---|---|---|
| Item table MinIO path (item# → UPC crosswalk) | Justin Fisher | Added to bucket Sept 15; path not yet shared |
| Warehouse status lookup (Status=3 filter) | Can load from `docs/Costco US Warehouses.xlsx` | Ready to load now |
| BP222 refresh cadence | Justin Fisher | How/when extract updates in MinIO |
| OOS / In Stock% data | Circana | Investigating ~100% null |
