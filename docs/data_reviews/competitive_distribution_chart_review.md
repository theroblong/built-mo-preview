# Review: BUILT "Competitive Distribution Chart 2026_ 10_12_26.xlsx" (received 2026-10-14)

Source: Brian, via Jason. Not committed to git (78 MB; contains individual buyer names). Read-only profiling scripts were
kept outside the repo. Brian's note: singles can appear both in Grocery Distribution (regular aisle) and in Grocery
CheckLane (front end); if in both, the item is available in both areas of the store.

## What the workbook is

A point-in-time account tracker. Each row is a retailer account; each product column holds that account's **points of
distribution (PODs)**, i.e. the number of stores carrying that item. "Total PODs (Current)" sums them, and "Total # of
Items" counts the items carried. It has **no weekly or monthly history**, only year-end POD totals for 2024, 2025 and
2026 in summary rows. The only date is the file name (2026-10-12).

## Tabs (8; Brian's description lists 9 -- "Distribution Gaps" and "2025 FC Accounts" are not in this copy)

| Tab | Visible | Rows | Content |
|---|---|---|---|
| Grocery Distribution | yes | 90 accounts (r10-r99), header r9 | Account fields + 37 Puff item/pack columns + totals |
| Grocery CheckLane | yes | same 90 accounts | Front-end (checklane) placement: Yes/No + 13 single-Puff columns |
| Canada | yes | 6 accounts | Same layout as Grocery; 8 columns hidden |
| C-Store Distribution | yes | 64 accounts | Account fields + 14 Puff columns; "Disco" (discontinued) slots; "2018 Goals" row |
| Alt Channel | yes | 10 accounts | Drug, fitness, hardware, e-commerce |
| Syndication List | yes | 5 routes | 1WS, Syndigo, IX-One/RIVIR, Broker, Special Portal |
| Monthly Change | **hidden** | 64 retailers x 48 products | **Kodiak products** (Power Cakes, muffins, waffles, oatmeal); every formula **#REF!** |
| Prior Month | **hidden** | 64 retailers | Kodiak product store counts, dated "April 18" |

## Fields (Grocery Distribution, header row 9)

| Column | Filled (of 90) | Notes |
|---|---|---|
| Retailer | 90 | Banner-level names (e.g. 15 Albertsons divisions, 8 Costco regions) |
| Content Support | 49 | Syndication route (Syndigo, 1WS, IX-One/RIVIR) |
| Direct Link | 84 | Retailer website / search links |
| Distributor or Direct | 78 | Direct, KeHE, UNFI, McLane... |
| Broker | 59 | Firm, sometimes with a named person |
| Buyer | 52 | **Individual retailer buyer names (personal data)** |
| Category Review Date / Category Reset | 30 / 28 | Month text ("January", "On Going", "May & December") |
| Account Manager | 87 | BUILT staff first names |
| Store Region | 88 | National/East/Midwest/... |
| Retailer Store Count | 88 | Integer (3 text values) |
| 37 product columns | 1-48 each | Integer PODs; a few "x" text cells |
| Total # of Items / Total PODs (Current) | 70 / 90 | Formulas: COUNT and SUM across the item columns |

Product columns are flavor x pack: 16 single Puffs (incl. SOUR), 14 4-counts, 4 8-counts, mixed boxes and cartons. Names
do not match SPINS UPC descriptions exactly ("Min Chip Puff 8CT", "Brownie Bater Puff 8CT", "Salted Caramel" vs "Milk
Chocolate Salted Caramel"); a name-to-UPC map is needed.

## Formulas

- Row totals: `=SUM(N10:AX10)` (PODs) and `=COUNT(U14:AV14)` (items). Several COUNT ranges start at different columns
  (U, P, M), so "Total # of Items" may undercount some rows.
- Year summary rows (Grocery r101 / r103 / r105): 2024 / 2025 / 2026 PODs by item; all-channel totals in column K
  (`=BA105+'C-Store Distribution'!Y77+'Alt Channel'!X62+'Grocery CheckLane'!W105`).
  - Grocery PODs: 2024 33,348 · 2025 100,642 · 2026 215,414. All channels: 68,580 · 234,219 · 412,171.
  - CheckLane PODs: 2025 9,059 · 2026 10,804 (matches Brian).
- Broken references: row 412 ("+/- 2021") and parts of C-Store r383 / Canada r326 use `#REF!`; the hidden Monthly
  Change tab is entirely `#REF!`. Hard-coded arithmetic in a few cells (`=1175*2`, `=4+79`).

## Data-quality flags

1. 92 of 528 filled Grocery item cells exceed that account's Retailer Store Count (e.g. Albertsons 1,750 vs 1,200 stores):
   either the store count is stale/partial or some cells are not store counts.
2. Text in numeric columns ("x", "X", " ", "June Reset").
3. Row colors carry meaning (yellow/orange/blue/green/peach = content-syndication status) but are theme colors that
   do not survive CSV export; they must be read from the file if kept.
4. Leftover template content from another brand (Kodiak) and old goals (2018); hidden columns in Canada and C-Store.
5. One snapshot only; old dates suppressed by Brian.

## Potential uses (checked against docs/SETTLED_FINDINGS.md)

- **Not a forecast input.** SETTLED (FACT, line ~783): "the door-count / planned-distribution data ask is dead: a 0.6pp
  ceiling, and BUILT ships to warehouses" (README 215, MO_95; oracle test on the pre-fix benchmark). This file is a
  single current snapshot with no history, so it cannot be backtested either.
- **Distribution coverage check:** compare BUILT's own POD counts per item x retailer with SPINS distribution (TDP) for
  the same accounts, to flag gaps or stale data on either side.
- **Assortment white space:** which flavors/packs each account does not carry (item x retailer matrix), for Mo's retailer
  views and account planning.
- **Channels SPINS does not see:** C-store (64 accounts), Alt Channel (10), Canada (6) and checklane placement.
- **Account metadata:** distributor/direct, broker, region and syndication route per account, to align with the NetSuite
  customer bridge.
- **Category review and reset months:** a planning calendar per account (text months; no years).

## Druid preparation (proposal, not started)

Long format, one snapshot per upload: `built_distribution_chart` (snapshot_date, channel/tab, retailer, product name,
pack, pods, flags) plus an account table (retailer, channel, distributor, broker firm, account manager, region, store
count, syndication route, review/reset months, color status). Exclude individual buyer names and comments. Needs a
retailer-to-SPINS-geography map and a product-name-to-UPC map. Do not add Kodiak tabs.
