# Druid load list (for Rob, weekend of 2026-10-10)

Prepared 2026-10-09 from BUILT-provided files. All load-ready files are in the FirstAgent repo
(github.com/theroblong/built-mo-preview) under **`data/druid_loads/`**, built by
**`scripts/build_druid_loads.py`** (re-run it whenever BUILT sends a newer source file).
Format: CSV, snake_case columns, ISO dates, UTC. `__time` is filled where the table is time-based.

## 1. Datasources (time-based)

| # | Proposed datasource | Load file | Rows | `__time` | Key dimensions | Metrics | Source (who / file / tab) |
|---|---|---|---|---|---|---|---|
| 1 | `trade_promotions` | `data/druid_loads/trade_promotions.csv` | 1,306 | `promotion_start_date` (2024-12-22 .. 2027-01-31) | customer, promotion_id, promotion_name, promotion_status, tactic, deal, product_group, promotion/shipment start-end dates, last_deduction_date, as_of_date | regular/promoted shopper price, discount usd/pct, list / net supply price, allowances (off invoice, bill back, scan, club scan, co-op, processing fee), base_volumes, planned_lift_pct, planned spending by type, total_planned_spending, actual_spending | Brian, `docs/Promotions,_Sep_30,_2026  FULL HISTORY For Aevah.xlsx`, tab **Details** |
| 2 | `trade_promotions_overview` | `data/druid_loads/trade_promotions_overview.csv` | 892 | `run_dates_start` (2024-12-22 .. 2027-01-31) | customer, promotion_id, promotion_name, contract, status, run/shipment dates | gross_revenue, cogs, incremental_trade_spend, volume_based_estimate, actual_spending, latest_estimate, total_trade_allowances, net_revenues, profit, retail_revenue, retail_profit, roi | Brian, same file, tab **Overview** |
| 3 | `forecast_versions` | `data/druid_loads/forecast_versions.csv.gz` (gzip CSV) | 220,168 | forecast target week | version_id, cutoff, model, upc, channel_outlet, retail_account, geography_raw, series, h (weeks ahead), lapsed | forecast_units | Aevah, `forecasts_registered/2026-09-06*.parquet` (saved before the outcomes existed) |

**`forecast_versions` must be append-only** (`appendToExisting: true`). Each new save adds a new
`version_id`; never replace older versions. This table is what makes "budget vs latest estimate vs
actuals" possible (Clark's request), and it is the forward test of every model. Models in this first
version: served_direct_v11d (what BUILT is served today), recursive, last_week_carried_forward,
l4w_velocity_x_stores, mo130, blend, direct_fixed, recursive_plus_direct_fixed.

## 2. Lookups / small dimension tables (no time)

| # | Proposed name | Load file | Rows | Key | Contents | Source |
|---|---|---|---|---|---|---|
| 4 | `item_attributes` | `data/druid_loads/item_attributes.csv` | 235 | **`key11`** = 11-digit UPC key (see below) | Connor's item number, description, Built UPC, SPINS UPC, product line (`majority_type`: Puff / Sour Puff / Chunk Puff / Duos Puff / Bar), bars per unit, retail price per bar and per unit, notes, flags (`exclusive_to`, `is_shipper_or_display`, `is_inner_caddy`, `is_discontinued`, `is_2027_innovation`, `is_tbd`), NetSuite item id / SKU / flavor / product line / inactive, SPINS description, `match_method` | Connor `Item_Assumptions` (updated 7/22/26) + Ebad `docs/ItemDim.xlsx` + SPINS panel |
| 5 | `item_master_rows` | `data/druid_loads/item_master_rows.csv` | 162 | Connor `built_item_no` | Every row of Connor's item tab with the NetSuite and SPINS joins (audit trail; includes shippers, caddies, TBD future items) | as above |
| 6 | `customer_bridge` | `data/druid_loads/customer_bridge.csv` | 116 | `netsuite_customer_id` / `retailer` | retailer <-> BUILT customer <-> NetSuite customer ID <-> SPINS customer <-> channel <-> sales manager | Ebad, `docs/SalesRepTables.xlsx`, tab **SalesRepCustomerMap** |
| 7 | `sales_reps` | `data/druid_loads/sales_reps.csv` | 14 | `salesrepid` | rep id, employee code, name, title, department (**email removed**) | Ebad, `docs/SalesRepTables.xlsx`, tab **SalesRepDim** |

### The UPC key (`key11`)
SPINS writes UPCs as `08-40229-30119` ("0" + the first 11 digits of the retail UPC, no check digit);
Connor's Built UPC and NetSuite write the full 12-digit retail UPC (`840229301195`). The join key is
**11 digits**: SPINS -> last 11 digits; 12-digit UPC -> first 11 digits. To join from
`built_filtered_weekly`, strip non-digits from `upc` and take the last 11.
`match_method` says how each key was found: `connor_spins_upc` (preferred; maps cases and inner
caddies to the consumer unit), `connor_built_upc`, `netsuite_upc`, or `spins_only` (in SPINS but in
neither BUILT list: mostly discontinued BARs, plus 2026 launches and 12-pack cartons not yet on
Connor's sheet). Coverage: the BUILT lists cover 99.4% of the last 26 weeks of SPINS volume.

## 3. Notes and caveats
- **Snapshots, not live feeds.** Connor's items are as of 7/22/26; ItemDim as of 2026-10-01; promotions as
  of 2026-09-30. Re-run the builder when newer files arrive; keep `as_of_date` / `built_on` so versions
  are traceable.
- **Promotions are trade commitments,** not confirmed shelf promotions (Brian, 2026-09-30). 52 rows
  start in 2027 (forward plans). Only 2 Costco rows: Costco MVM history comes from CRX (`is_mvm`).
- **No BAR -> PUFF mapping from BUILT.** Nothing here links BAR items to PUFF items.
- **People data:** sales rep emails are deliberately excluded.
- **Not included (already in Druid or not needed):** SPINS weekly (`built_filtered_weekly`), Costco CRX
  (`built_costco_crx_weekly`). Data-dark retailer shipments (`docs/Shipment Data.xlsx`, Ebad) and the
  customer dimension (`docs/CustomerDim*.xlsx`) can be added if they are not already in Druid; tell us.
- **Editable inputs** (the single promotion table BUILT may maintain, forward distribution plans, a
  new-item form, budget version locks) need a small relational store published to Druid; Druid alone
  has no row-level edits.
