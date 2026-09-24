# Finance View Schema Documentation

**Source:** `Finance View Schema.sql`  
**Database context:** `Finance`  
**Views documented:** 34  
**Generated:** 2026-09-22

## 1. Executive summary

This document catalogs the SQL views defined in the Finance database script. It explains each view’s reporting purpose, expected row grain, source dependencies, filters, and output columns. The views primarily expose NetSuite2 transaction, item, accounting, inventory, work-order, transfer-order, standard-cost, production, sales, BOM, and lot-trace data in reporting-friendly structures.

### Major subject areas

- **Core compatibility layer:** transaction headers, transaction lines, items, and accounting periods.
- **Cost and inventory:** standard cost, inventory on hand, item valuation, and revaluation.
- **Manufacturing:** assembly builds, work orders, bars produced, batch yield, BOM, and material usage.
- **Sales and supply visibility:** bars sold, open sales-order demand, transfer supply, work-order supply, and future supply coverage.
- **Traceability:** assembly lot detail and lot-trace views.

## 2. Schema and dependency architecture

### Source schemas

- `Finance.dbo`: reporting views and local reporting objects.
- `Source_NetSuite.ns2`: replicated NetSuite2 source tables such as `transaction`, `transactionLine`, `Item`, `TransactionAccountingLine`, `Account`, `accountingPeriod`, `InventoryAssignment`, `inventoryNumber`, `Location`, and status/classification tables.
- `finance..viewStdCostDetail` and `finance..viewItemLastProductionDate`: pre-existing Finance objects surfaced through pass-through compatibility views.

### Internal view-to-view dependencies

| Dependent view | Uses view |
|---|---|
| `vw_SCA_WorkOrderSupply` | `NetSuite2_View_AssemblyBuildSum` |
| `NetSuite2_View_WorkOrdersOpen` | `NetSuite2_View_AssemblyBuildSum` |
| `NetSuite2_View_StdCostByCategory` | `NetSuite2_View_StdCostDetail` |
| `NetSuite2_View_StdCostSum` | `NetSuite2_View_StdCostByCategory` |
| `NetSuite2_View_StdCostSumByLocation` | `NetSuite2_View_StdCostByCategory` |
| `NetSuite2_View_TransactionsJoin` | `NetSuite2_View_Transactions` |
| `NetSuite2_View_TransactionsJoin` | `NetSuite2_View_Transaction_Lines` |
| `NetSuite2_View_TransactionsJoin` | `NetSuite2_View_Items` |
| `NetSuite2_View_TransactionsJoin` | `NetSuite2_View_AccountingPeriod` |
| `NetSuite2_View_FutureOrderSupplyVisibility` | `NetSuite2_View_InventoryOnHand` |
| `NetSuite2_View_FutureOrderSupplyVisibility` | `NetSuite2_View_AssemblyBuildSum` |

## 3. View catalog

| View | Purpose | Grain | Columns | Dependencies |
|---|---|---|---:|---:|
| `NetSuite2_View_AssemblyBuildSum` | Aggregates assembly-build units, bars, and amount by originating work order and assembly item. | Aggregated at the GROUP BY dimensions defined in the view. | 9 | 3 |
| `vw_SCA_WorkOrderSupply` | Summarizes work-order demand, production, remaining units/bars, status grouping, and finished-good-line validation. | One row per work order and finished-good item. | 24 | 6 |
| `NetSuite2_View_WorkOrdersOpen` | Returns work-order quantities with assembly-build production and calculated remaining units. | Row grain follows the primary source and joins defined in the view. | 17 | 4 |
| `NetSuite2_View_StdCostDetail` | Compatibility/pass-through view over the existing standard-cost detail source. | Row grain follows the primary source and joins defined in the view. | 1 | 1 |
| `NetSuite2_View_StdCostByCategory` | Aggregates standard cost by item, location, and cost category. | Aggregated at the GROUP BY dimensions defined in the view. | 6 | 1 |
| `NetSuite2_View_StdCostSum` | Provides item-level standard cost totals for Main Warehouse. | Aggregated at the GROUP BY dimensions defined in the view. | 5 | 1 |
| `NetSuite2_View_InventoryOnHand` | Aggregates lot/location inventory quantities for on-order, on-hand, and available inventory. | One row per item, inventory number/lot attributes, and location after aggregation. | 10 | 3 |
| `NetSuite2_View_ItemLastProductionDate` | Compatibility/pass-through view over the existing item last-production-date source. | Row grain follows the primary source and joins defined in the view. | 1 | 1 |
| `NetSuite2_View_ItemsAll` | Enriches the item master with classification, inventory, standard cost, account category, and last production information. | Item-level, but joins to inventory/location sources may produce multiple rows per item. | 23 | 6 |
| `NetSuite2_View_StdCostSumByLocation` | Summarizes standard cost by item and location. | Aggregated at the GROUP BY dimensions defined in the view. | 5 | 1 |
| `NetSuite2_View_Items` | Maps NetSuite item attributes into a reporting compatibility view with explicit placeholders for unmapped legacy fields. | One row per item. | 46 | 1 |
| `NetSuite2_View_AccountingPeriod` | Maps NetSuite accounting-period attributes into a reporting-friendly structure and derives month/year. | One row per accounting period. | 25 | 1 |
| `NetSuite2_View_Transactions` | Maps NetSuite transaction headers into a reporting compatibility view, including explicit NULL placeholders for unmapped legacy fields. | One row per transaction header. | 78 | 1 |
| `NetSuite2_View_Transaction_Lines` | Maps NetSuite transaction lines and accounting-line accounts into a reporting compatibility view. | Transaction-line grain, subject to accounting-line join multiplicity. | 56 | 2 |
| `NetSuite2_View_TransactionsJoin` | Combines transactions, lines, items, accounts, periods, and classifications into a finance reporting dataset. | Row grain follows the primary source and joins defined in the view. | 19 | 7 |
| `NetSuite2_View_FutureOrderSupplyVisibility` | Unifies open sales-order demand with inventory, transfer-order, and work-order supply candidates to identify potentially uncovered quantities. | One row per sales-order line. | 37 | 10 |
| `NetSuite2_View_Assemblies` | Lists work-order and assembly-build transaction lines with item, quantity, amount, and lot number. | Row grain follows the primary source and joins defined in the view. | 8 | 3 |
| `NetSuite2_View_AssembliesLotCode` | Provides lot-level assembly build/unbuild output and consumption with item, account, period, and line context. | Transaction-line and inventory-assignment/lot grain. | 18 | 10 |
| `NetSuite2_View_BarsProdSummary` | Summarizes production units, bars, and amounts by date, assembly, and asset account. | Aggregated at the GROUP BY dimensions defined in the view. | 9 | 4 |
| `NetSuite2_View_BarsProduced` | Summarizes assembly build/unbuild activity by item and classifies output versus consumption. | Aggregated at the GROUP BY dimensions defined in the view. | 16 | 4 |
| `NetSuite2_View_BarsSold` | Aggregates units and bars sold by transaction date and sales channel using posting revenue-account filters. | Aggregated at the GROUP BY dimensions defined in the view. | 4 | 8 |
| `NetSuite2_View_Batchyield` | Provides lot-level assembly transaction detail intended for batch-yield analysis, including output/consumption, quantity, item group, and line. | Transaction-line and inventory-assignment/lot grain. | 18 | 8 |
| `NetSuite2_View_BillOfMaterials` | Returns active BOM revisions and their component quantities, yields, dates, and item details. | One row per active BOM revision component. | 16 | 4 |
| `NetSuite2_View_LastRevaluationByItem` | Identifies the latest inventory cost revaluation transaction ID by item and location. | Aggregated at the GROUP BY dimensions defined in the view. | 5 | 3 |
| `NetSuite2_View_LotTrace` | Provides lot-level transaction traceability across transaction lines, inventory assignments, bins, items, and accounts. | Transaction-line and inventory-assignment/lot grain. | 35 | 7 |
| `NetSuite2_View_LotTrace_Option2` | Provides an alternate lot-trace dataset without accounting-line dependency, retaining several unmapped placeholders. | Transaction-line and inventory-assignment/lot grain. | 35 | 6 |
| `NetSuite2_View_MaterialsUsage` | Aggregates recent assembly-build material consumption and amount by item and accounting period. | Aggregated at the GROUP BY dimensions defined in the view. | 11 | 5 |
| `NetSuite2_View_SOandCSTrans` | Lists cash-sale and sales-order transaction identifiers from the configured start date. | Row grain follows the primary source and joins defined in the view. | 2 | 1 |
| `NetSuite2_View_StandardCostBarsShipped` | Summarizes quantities, bars, and amount for selected shipment transaction types and cost account. | Aggregated at the GROUP BY dimensions defined in the view. | 13 | 6 |
| `NetSuite2_View_StdCostRevaluation` | Returns inventory cost revaluation line detail with old/new cost component classification. | Row grain follows the primary source and joins defined in the view. | 16 | 6 |
| `NetSuite2_View_TransactionLinesBasic` | Provides a broad transaction-line reporting dataset with account, period, department, class, item, customer, quantity, bars, amount, and location. | Transaction-line grain, subject to accounting-line join multiplicity. | 20 | 10 |
| `NetSuite2_vw_BarCount` | Aggregates bars made for assembly builds/unbuilds with account, item, and production-line context. | Aggregated at the GROUP BY dimensions defined in the view. | 15 | 7 |
| `vw_SCA_SalesOrderLines` | Provides open sales-order line demand and fulfillment allocation quantities at item and location grain. | One row per sales-order line. | 27 | 7 |
| `vw_SCA_TransferSupply` | Pairs transfer-order source and destination lines and classifies candidate inbound supply by approval/operational status. | One row per transfer transaction, item, source location, and destination location pairing. | 21 | 5 |

## 4. Detailed view dictionary

### 4.1 `NetSuite2_View_AssemblyBuildSum`

**Purpose:** Aggregates assembly-build units, bars, and amount by originating work order and assembly item.

**Expected grain:** Aggregated at the GROUP BY dimensions defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.item`

**Key filters found in the SQL:**
- `Record type: recordtype = 'assemblybuild'`
- `Date: trandate >= '2024-01-01'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `CREATED_FROM_ID` | Source | `tl.createdfrom AS CREATED_FROM_ID` |
| `AssemblyItem` | Source | `t.custbody_wo_assembly AS AssemblyItem` |
| `Item` | Source | `i.fullname AS Item` |
| `ItemDesc` | Derived | `COALESCE(i.displayname,i.description,i.purchasedescription) AS ItemDesc` |
| `ItemType` | Source | `i.itemtype AS ItemType` |
| `BarCount` | Derived | `ISNULL(i.custitem_bars, 0) AS BarCount` |
| `Units` | Aggregate | `SUM(tl.quantity) AS Units` |
| `Bars` | Aggregate | `SUM(tl.quantity * ISNULL(i.custitem_bars, 0)) AS Bars` |
| `Amount` | Aggregate | `SUM(tl.netamount) AS Amount` |

### 4.2 `vw_SCA_WorkOrderSupply`

**Purpose:** Summarizes work-order demand, production, remaining units/bars, status grouping, and finished-good-line validation.

**Expected grain:** One row per work order and finished-good item.

**Dependencies:**
- `Source_NetSuite.ns2.transactionstatus`
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.item`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.Location`
- `Finance.dbo.NetSuite2_View_AssemblyBuildSum`

**Key filters found in the SQL:**
- `Record type: recordtype = 'workorder'`
- `Status: fullname IN ( 'Work Order : Planned', 'Work Order : In Process', 'Work Order : Built', 'Work Order : Closed' )`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `WorkOrderTransactionID` | Source | `WorkOrderTransactionID` |
| `WorkOrderID` | Source | `WorkOrderID` |
| `WorkOrderDate` | Source | `WorkOrderDate` |
| `RawAssemblyValue` | Source | `RawAssemblyValue` |
| `ItemID` | Source | `ItemID` |
| `ItemSKU` | Source | `ItemSKU` |
| `ItemDescription` | Source | `ItemDescription` |
| `BarsPerFinishedGood` | Source | `BarsPerFinishedGood` |
| `UOM` | Source | `UOM` |
| `LocationID` | Source | `LocationID` |
| `LocationName` | Source | `LocationName` |
| `StartDate` | Source | `StartDate` |
| `ExpectedCompletionDate` | Source | `ExpectedCompletionDate` |
| `StatusID` | Source | `StatusID` |
| `WorkOrderStatus` | Source | `WorkOrderStatus` |
| `WorkOrderSupplyType` | Source | `WorkOrderSupplyType` |
| `WorkOrderQtyUnits` | Source | `WorkOrderQtyUnits` |
| `UnitsProduced` | Source | `UnitsProduced` |
| `UnitsRemaining` | Derived | `CASE WHEN WorkOrderQtyUnits - UnitsProduced > 0 THEN WorkOrderQtyUnits - UnitsProduced ELSE 0 END AS UnitsRemaining` |
| `WorkOrderQtyBars` | Derived | `WorkOrderQtyUnits * BarsPerFinishedGood AS WorkOrderQtyBars` |
| `BarsProduced` | Derived | `UnitsProduced * BarsPerFinishedGood AS BarsProduced` |
| `BarsRemaining` | Derived | `CASE WHEN WorkOrderQtyUnits - UnitsProduced > 0 THEN ( WorkOrderQtyUnits - UnitsProduced ) * BarsPerFinishedGood ELSE 0 END AS BarsRemaining` |
| `FinishedGoodLineCount` | Source | `FinishedGoodLineCount` |
| `WorkOrderValidationStatus` | Derived | `CASE WHEN FinishedGoodLineCount = 1 THEN 'Valid finished-good line' WHEN FinishedGoodLineCount = 0 THEN 'Missing finished-good line' ELSE 'Multiple finished-good lines' END AS WorkOrderValidationStatus` |

### 4.3 `NetSuite2_View_WorkOrdersOpen`

**Purpose:** Returns work-order quantities with assembly-build production and calculated remaining units.

**Expected grain:** Row grain follows the primary source and joins defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.item`
- `dbo.NetSuite2_View_AssemblyBuildSum`

**Key filters found in the SQL:**
- `Record type: recordtype = 'workorder'`
- `Date: trandate >= '2025-11-01'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `Date` | Source | `t.trandate AS [Date]` |
| `StartDate` | Source | `t.startdate AS StartDate` |
| `EndDate` | Source | `t.enddate AS EndDate` |
| `TransType` | Source | `t.recordtype AS TransType` |
| `WONum` | Source | `t.tranid AS WONum` |
| `TRANSACTION_ID` | Source | `t.id AS TRANSACTION_ID` |
| `AssemblyItem` | Source | `t.custbody_wo_assembly AS AssemblyItem` |
| `Item` | Source | `i.fullname AS Item` |
| `ItemDesc` | Derived | `COALESCE(i.displayname,i.[description],i.purchasedescription) AS ItemDesc` |
| `BarCount` | Derived | `ISNULL(i.custitem_bars, 0) AS BarCount` |
| `UOM` | Derived | `CASE WHEN i.unitstype = 2 THEN 'EA' WHEN i.unitstype = 1 THEN 'KG' ELSE '' END AS UOM` |
| `Units` | Source | `tl.quantity AS Units` |
| `Bars` | Derived | `ISNULL(tl.quantity * i.custitem_bars, 0) AS Bars` |
| `TranStatus` | Source | `t.status AS TranStatus` |
| `TRANSACTION_LINE_ID` | Source | `tl.id AS TRANSACTION_LINE_ID` |
| `UnitsProduced` | Derived | `ISNULL(vabs.Units, 0) AS UnitsProduced` |
| `UnitsRemaining` | Derived | `tl.quantity - ISNULL(vabs.Units, 0) AS UnitsRemaining` |

### 4.4 `NetSuite2_View_StdCostDetail`

**Purpose:** Compatibility/pass-through view over the existing standard-cost detail source.

**Expected grain:** Row grain follows the primary source and joins defined in the view.

**Dependencies:**
- `finance`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `*` | Derived | `*` |

### 4.5 `NetSuite2_View_StdCostByCategory`

**Purpose:** Aggregates standard cost by item, location, and cost category.

**Expected grain:** Aggregated at the GROUP BY dimensions defined in the view.

**Dependencies:**
- `Finance.dbo.NetSuite2_View_StdCostDetail`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `TOP (100) PERCENT ITEM_ID` | Source | `TOP (100) PERCENT ITEM_ID` |
| `Item` | Source | `Item` |
| `ItemDesc` | Source | `ItemDesc` |
| `Location` | Source | `Location` |
| `COST_CATEGORY` | Source | `COST_CATEGORY` |
| `StdCost` | Aggregate | `SUM(STANDARD_COST) AS StdCost` |

### 4.6 `NetSuite2_View_StdCostSum`

**Purpose:** Provides item-level standard cost totals for Main Warehouse.

**Expected grain:** Aggregated at the GROUP BY dimensions defined in the view.

**Dependencies:**
- `dbo.NetSuite2_View_StdCostByCategory`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `ITEM_ID` | Source | `ITEM_ID` |
| `Item` | Source | `Item` |
| `ItemDesc` | Source | `ItemDesc` |
| `Location` | Source | `Location` |
| `StandardCost` | Aggregate | `SUM(StdCost) AS StandardCost` |

### 4.7 `NetSuite2_View_InventoryOnHand`

**Purpose:** Aggregates lot/location inventory quantities for on-order, on-hand, and available inventory.

**Expected grain:** One row per item, inventory number/lot attributes, and location after aggregation.

**Dependencies:**
- `Source_NetSuite.ns2.inventoryNumber`
- `Source_NetSuite.ns2.Item`
- `Source_NetSuite.ns2.inventoryNumberLocation`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `ITEM_ID` | Source | `i.id AS ITEM_ID` |
| `FULL_NAME` | Source | `i.fullname AS FULL_NAME` |
| `DISPLAYNAME` | Derived | `COALESCE(i.displayname,i.description,i.purchasedescription) AS DISPLAYNAME` |
| `BARS` | Source | `i.custitem_bars AS BARS` |
| `MEMO` | Source | `inv.memo AS MEMO` |
| `LOCATION_ID` | Source | `inl.location AS LOCATION_ID` |
| `LOT_DATE` | Source | `inv.custitemnumber_wmsts_lot_date AS LOT_DATE` |
| `OnOrder` | Aggregate | `SUM(COALESCE(inl.quantityonorder, 0)) AS OnOrder` |
| `OnHand` | Aggregate | `SUM(COALESCE(inl.quantityonhand, 0)) AS OnHand` |
| `Available` | Aggregate | `SUM(COALESCE(inl.quantityavailable, 0)) AS Available` |

### 4.8 `NetSuite2_View_ItemLastProductionDate`

**Purpose:** Compatibility/pass-through view over the existing item last-production-date source.

**Expected grain:** Row grain follows the primary source and joins defined in the view.

**Dependencies:**
- `finance`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `*` | Derived | `*` |

### 4.9 `NetSuite2_View_ItemsAll`

**Purpose:** Enriches the item master with classification, inventory, standard cost, account category, and last production information.

**Expected grain:** Item-level, but joins to inventory/location sources may produce multiple rows per item.

**Dependencies:**
- `source_netsuite.ns2.item`
- `Source_NetSuite.ns2.itemtype`
- `source_netsuite.ns2.CUSTOMRECORD_CSEG_CCC_PROD_LINE`
- `source_netsuite.ns2.CUSTOMRECORD_CSEG_PRODUCT_TYPE`
- `finance`
- `source_netsuite.ns2.account`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `i.id item_id` | Source | `i.id item_id` |
| `i.fullname full_name` | Source | `i.fullname full_name` |
| `coalesce(i.displayname, i.description, i.purc` | Derived | `coalesce(i.displayname, i.description, i.purchasedescription) displayname` |
| `it.name type_name` | Source | `it.name type_name` |
| `i.stockunit stock_unit_id` | Source | `i.stockunit stock_unit_id` |
| `pt.name product_type_name` | Source | `pt.name product_type_name` |
| `pc.name product_class_name` | Source | `pc.name product_class_name` |
| `i.custitem1 flavor` | Source | `i.custitem1 flavor` |
| `i.custitem_bars barCount` | Source | `i.custitem_bars barCount` |
| `OnHand` | Source | `vioh.OnHand` |
| `i.custitem_bars * vioh.OnHand BarsOnHand` | Derived | `i.custitem_bars * vioh.OnHand BarsOnHand` |
| `i.lastpurchaseprice last_purchase_price` | Source | `i.lastpurchaseprice last_purchase_price` |
| `totalvalue` | Source | `i.totalvalue` |
| `i.lastmodifieddate date_last_modified` | Source | `i.lastmodifieddate date_last_modified` |
| `vilpd.tranDate lastAssemblyDate` | Source | `vilpd.tranDate lastAssemblyDate` |
| `a.acctnumber AssetAccount` | Source | `a.acctnumber AssetAccount` |
| `a.accountsearchdisplaynamecopy name` | Source | `a.accountsearchdisplaynamecopy name` |
| `case when a.acctnumber = 121010 then 'Ingredi` | Derived | `case when a.acctnumber = 121010 then 'Ingredients' when a.acctnumber = 121010 then 'Packaging' when a.acctnumber = 121060 and i.unitstype = 1 then 'Batch' when a.acctnumber = 121060 and i.unitstype = 2 then 'Loose Bar' when a.acctnumber = 121050 then 'Finished Goods' when it.name = 'Kit/Package' then 'Finished Goods' else 'unknown' end itemSubCat` |
| `case when i.unitstype = 2 then 'EA' when i.un` | Derived | `case when i.unitstype = 2 then 'EA' when i.unitstype = 1 then 'KG' else 'UN' end UOM` |
| `standardCost` | Source | `sc.standardCost` |
| `sc.StandardCost*vioh.OnHand value` | Derived | `sc.StandardCost*vioh.OnHand [value]` |
| `i.custitemitem_category item_category_id` | Source | `i.custitemitem_category item_category_id` |
| `isinactive` | Source | `i.isinactive` |

### 4.10 `NetSuite2_View_StdCostSumByLocation`

**Purpose:** Summarizes standard cost by item and location.

**Expected grain:** Aggregated at the GROUP BY dimensions defined in the view.

**Dependencies:**
- `dbo.NetSuite2_View_StdCostByCategory`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `ITEM_ID` | Source | `ITEM_ID` |
| `Item` | Source | `Item` |
| `ItemDesc` | Source | `ItemDesc` |
| `Location` | Source | `Location` |
| `StdCost` | Aggregate | `SUM(StdCost) AS StdCost` |

### 4.11 `NetSuite2_View_Items`

**Purpose:** Maps NetSuite item attributes into a reporting compatibility view with explicit placeholders for unmapped legacy fields.

**Expected grain:** One row per item.

**Dependencies:**
- `Source_NetSuite.ns2.Item`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `ASSET_ACCOUNT_ID` | Source | `i.assetaccount AS ASSET_ACCOUNT_ID` |
| `AVERAGECOST` | Source | `i.averagecost AS AVERAGECOST` |
| `BARS` | Source | `i.custitem_bars AS BARS` |
| `CLASS_ID` | Source | `i.class AS CLASS_ID` |
| `COSTING_METHOD` | Source | `i.costingmethod AS COSTING_METHOD` |
| `COST_0` | Source | `i.cost AS COST_0` |
| `COST_CATEGORY` | Source | `i.costcategory AS COST_CATEGORY` |
| `COST_ESTIMATE_TYPE` | Source | `i.costestimatetype AS COST_ESTIMATE_TYPE` |
| `CREATED` | Source | `i.createddate AS CREATED` |
| `DATE_LAST_MODIFIED` | Source | `i.lastmodifieddate AS DATE_LAST_MODIFIED` |
| `DATE_OF_LAST_TRANSACTION` | Placeholder | `CAST(NULL AS datetime) AS DATE_OF_LAST_TRANSACTION` |
| `DEMAND_TIME_FENCE` | Placeholder | `CAST(NULL AS nvarchar(255)) AS DEMAND_TIME_FENCE` |
| `DISPLAYNAME` | Derived | `CASE WHEN NULLIF(LTRIM(RTRIM(i.displayname)), '') IS NOT NULL AND NULLIF(LTRIM(RTRIM(i.description)), '') IS NOT NULL THEN i.displayname + ' - ' + i.description WHEN NULLIF(LTRIM(RTRIM(i.displayname)), '') IS NOT NULL THEN i.displayname ELSE i.description END AS DISPLAYNAME` |
| `EXPENSE_ACCOUNT_ID` | Source | `i.expenseaccount AS EXPENSE_ACCOUNT_ID` |
| `FULL_NAME` | Source | `i.fullname AS FULL_NAME` |
| `INCOME_ACCOUNT_ID` | Source | `i.incomeaccount AS INCOME_ACCOUNT_ID` |
| `INTERCO_EXPENSE_ACCOUNT_ID` | Placeholder | `CAST(NULL AS bigint) AS INTERCO_EXPENSE_ACCOUNT_ID` |
| `ISINACTIVE` | Source | `i.isinactive AS ISINACTIVE` |
| `ITEM_EXTID` | Source | `i.externalid AS ITEM_EXTID` |
| `ITEM_ID` | Source | `i.id AS ITEM_ID` |
| `ITEM_REVENUE_CATEGORY` | Placeholder | `CAST(NULL AS nvarchar(255)) AS ITEM_REVENUE_CATEGORY` |
| `LAST_PURCHASE_PRICE` | Source | `i.lastpurchaseprice AS LAST_PURCHASE_PRICE` |
| `LOCATION_ID` | Placeholder | `CAST(NULL AS bigint) AS LOCATION_ID` |
| `LOT_NUMBERED_ITEM` | Source | `i.islotitem AS LOT_NUMBERED_ITEM` |
| `MANUFACTURER` | Source | `i.manufacturer AS MANUFACTURER` |
| `NAME` | Source | `i.fullname AS NAME` |
| `OVERHEAD_TYPE` | Placeholder | `CAST(NULL AS nvarchar(255)) AS OVERHEAD_TYPE` |
| `PARENT_ID` | Placeholder | `CAST(NULL AS bigint) AS PARENT_ID` |
| `PRODUCT_CLASS_ID` | Source | `i.cseg_product_type AS PRODUCT_CLASS_ID` |
| `PROD_PRICE_VAR_ACCOUNT_ID` | Source | `i.prodpricevarianceacct AS PROD_PRICE_VAR_ACCOUNT_ID` |
| `PROD_QTY_VAR_ACCOUNT_ID` | Source | `i.prodqtyvarianceacct AS PROD_QTY_VAR_ACCOUNT_ID` |
| `PURCHASE_PRICE_VAR_ACCOUNT_ID` | Source | `i.purchasepricevarianceacct AS PURCHASE_PRICE_VAR_ACCOUNT_ID` |
| `PURCHASE_UNIT_ID` | Source | `i.purchaseunit AS PURCHASE_UNIT_ID` |
| `SALE_UNIT_ID` | Source | `i.saleunit AS SALE_UNIT_ID` |
| `SCRAP_ACCOUNT_ID` | Placeholder | `CAST(NULL AS bigint) AS SCRAP_ACCOUNT_ID` |
| `STOCK_UNIT_ID` | Source | `i.stockunit AS STOCK_UNIT_ID` |
| `TRANSFERPRICE` | Source | `i.transferprice AS TRANSFERPRICE` |
| `TYPE_NAME` | Source | `i.itemtype AS TYPE_NAME` |
| `UNBUILD_VARIANCE_ACCOUNT_ID` | Source | `i.unbuildvarianceaccount AS UNBUILD_VARIANCE_ACCOUNT_ID` |
| `UNITS_TYPE_ID` | Source | `i.unitstype AS UNITS_TYPE_ID` |
| `UPC_CODE` | Source | `i.upccode AS UPC_CODE` |
| `USE_COMPONENT_YIELD` | Placeholder | `CAST(NULL AS decimal(18,6)) AS USE_COMPONENT_YIELD` |
| `VENDORNAME` | Source | `i.vendorname AS VENDORNAME` |
| `VENDOR_ID` | Placeholder | `CAST(NULL AS bigint) AS VENDOR_ID` |
| `WEIGHT` | Source | `i.custitem_ccc_item_weight_lb AS WEIGHT` |
| `WIDTH` | Source | `i.custitem_ccc_item_width_in AS WIDTH` |

### 4.12 `NetSuite2_View_AccountingPeriod`

**Purpose:** Maps NetSuite accounting-period attributes into a reporting-friendly structure and derives month/year.

**Expected grain:** One row per accounting period.

**Dependencies:**
- `Source_NetSuite.ns2.accountingPeriod`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `ACCOUNTING_PERIOD_ID` | Source | `ap.id AS ACCOUNTING_PERIOD_ID` |
| `CLOSED` | Source | `ap.closed AS CLOSED` |
| `CLOSED_ACCOUNTS_PAYABLE` | Source | `ap.apLocked AS CLOSED_ACCOUNTS_PAYABLE` |
| `CLOSED_ACCOUNTS_RECEIVABLE` | Source | `ap.arLocked AS CLOSED_ACCOUNTS_RECEIVABLE` |
| `CLOSED_ALL` | Source | `ap.allLocked AS CLOSED_ALL` |
| `CLOSED_ON` | Source | `ap.closedondate AS CLOSED_ON` |
| `CLOSED_PAYROLL` | Placeholder | `CAST(NULL AS varchar(10)) AS CLOSED_PAYROLL` |
| `DATE_LAST_MODIFIED` | Source | `ap.lastmodifieddate AS DATE_LAST_MODIFIED` |
| `ENDING` | Source | `ap.enddate AS ENDING` |
| `FISCAL_CALENDAR_ID` | Placeholder | `CAST(NULL AS bigint) AS FISCAL_CALENDAR_ID` |
| `FULL_NAME` | Placeholder | `CAST(NULL AS varchar(10)) AS FULL_NAME` |
| `ISINACTIVE` | Source | `ap.isinactive AS ISINACTIVE` |
| `IS_ADJUSTMENT` | Source | `ap.isadjust AS IS_ADJUSTMENT` |
| `LOCKED_ACCOUNTS_PAYABLE` | Source | `ap.apLocked AS LOCKED_ACCOUNTS_PAYABLE` |
| `LOCKED_ACCOUNTS_RECEIVABLE` | Source | `ap.arLocked AS LOCKED_ACCOUNTS_RECEIVABLE` |
| `LOCKED_ALL` | Source | `ap.allLocked AS LOCKED_ALL` |
| `LOCKED_PAYROLL` | Placeholder | `CAST(NULL AS varchar(10)) AS LOCKED_PAYROLL` |
| `NAME` | Source | `ap.periodname AS NAME` |
| `PARENT_ID` | Source | `ap.parent AS PARENT_ID` |
| `QUARTER` | Source | `ap.isquarter AS QUARTER` |
| `STARTING` | Source | `ap.startdate AS STARTING` |
| `YEAR_0` | Source | `ap.isyear AS YEAR_0` |
| `YEAR_ID` | Source | `ap.[year] AS YEAR_ID` |
| `PERIOD` | Source | `MONTH(ap.enddate) AS PERIOD` |
| `YEAR` | Source | `YEAR(ap.enddate) AS [YEAR]` |

### 4.13 `NetSuite2_View_Transactions`

**Purpose:** Maps NetSuite transaction headers into a reporting compatibility view, including explicit NULL placeholders for unmapped legacy fields.

**Expected grain:** One row per transaction header.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `ACCOUNTING_BOOK_ID` | Placeholder | `CAST(NULL AS bigint) AS ACCOUNTING_BOOK_ID` |
| `ACCOUNTING_PERIOD_ID` | Source | `t.postingperiod AS ACCOUNTING_PERIOD_ID` |
| `ACTUAL_DELIVERY_DATE` | Source | `t.custbody_sps_deliverydate AS ACTUAL_DELIVERY_DATE` |
| `ACTUAL_SHIP_DATE` | Source | `t.actualshipdate AS ACTUAL_SHIP_DATE` |
| `AMOUNT_UNBILLED` | Source | `t.amountunbilled AS AMOUNT_UNBILLED` |
| `ASSEMBLY_ITEM` | Source | `t.custbody_wo_assembly AS ASSEMBLY_ITEM` |
| `CLOSED` | Source | `t.closedate AS CLOSED` |
| `COLLECTIONS_REP_ID` | Source | `t.custbody_ccc_collections_rep AS COLLECTIONS_REP_ID` |
| `CREATED_BY_ID` | Source | `t.createdby AS CREATED_BY_ID` |
| `CREATED_FROM_ID` | Placeholder | `CAST(NULL AS bigint) AS CREATED_FROM_ID` |
| `CREATE_DATE` | Source | `t.createddate AS CREATE_DATE` |
| `CUSTOMER_ACCOUNT_NUMBER` | Source | `t.custbody_sps_customeraccountnumber AS CUSTOMER_ACCOUNT_NUMBER` |
| `CUSTOMER_ORDER_DATE` | Placeholder | `CAST(NULL AS datetime) AS CUSTOMER_ORDER_DATE` |
| `CUSTOMER_ORDER_NUMBER` | Source | `t.custbody_sps_customerordernumber AS CUSTOMER_ORDER_NUMBER` |
| `DATE_LAST_MODIFIED` | Source | `t.lastmodifieddate AS DATE_LAST_MODIFIED` |
| `DATE_ORDER_RECEIVED_DATE` | Placeholder | `CAST(NULL AS datetime) AS DATE_ORDER_RECEIVED_DATE` |
| `DEPARTMENT` | Source | `t.custbody_sps_department AS DEPARTMENT` |
| `DEPARTMENT_DESCRIPTION` | Source | `t.custbody_sps_departmentdescription AS DEPARTMENT_DESCRIPTION` |
| `DUE_DATE` | Source | `t.duedate AS DUE_DATE` |
| `EARLIEST_DELIVERY_DATE` | Source | `t.custbody_sps_date_064 AS EARLIEST_DELIVERY_DATE` |
| `EARLIEST_SHIP_DATE` | Source | `t.custbody_sps_date_037 AS EARLIEST_SHIP_DATE` |
| `EFFECTIVE_DATE` | Source | `t.custbody_sps_date_007 AS EFFECTIVE_DATE` |
| `END_DATE` | Source | `t.enddate AS END_DATE` |
| `ESTIMATED_DELIVERY_DATE` | Placeholder | `CAST(NULL AS datetime) AS ESTIMATED_DELIVERY_DATE` |
| `FULFILLMENT_CREATED` | Source | `t.custbody_fulfillment_created AS FULFILLMENT_CREATED` |
| `GENERAL_NOTES` | Source | `t.custbody_sps_gen_noteinformationfield AS GENERAL_NOTES` |
| `IS_NON_POSTING` | Placeholder | `CAST(NULL AS bit) AS IS_NON_POSTING` |
| `LAST_MODIFIED_DATE` | Source | `t.lastmodifieddate AS LAST_MODIFIED_DATE` |
| `LOCATION_ID` | Source | `t.location AS LOCATION_ID` |
| `MEMO` | Source | `t.memo AS MEMO` |
| `QA` | Placeholder | `CAST(NULL AS nvarchar(255)) AS QA` |
| `START_DATE` | Source | `t.startdate AS START_DATE` |
| `STATUS` | Source | `t.status AS STATUS` |
| `STATUS_CODE` | Placeholder | `CAST(NULL AS nvarchar(255)) AS STATUS_CODE` |
| `TRACKING_NUMBER` | Placeholder | `CAST(NULL AS nvarchar(255)) AS TRACKING_NUMBER` |
| `TRANDATE` | Source | `t.trandate AS TRANDATE` |
| `TRANID` | Source | `t.tranid AS TRANID` |
| `TRANSACTION_EXTID` | Placeholder | `CAST(NULL AS nvarchar(255)) AS TRANSACTION_EXTID` |
| `TRANSACTION_ID` | Source | `t.id AS TRANSACTION_ID` |
| `TRANSACTION_NUMBER` | Source | `t.transactionnumber AS TRANSACTION_NUMBER` |
| `TRANSACTION_PARTNER` | Placeholder | `CAST(NULL AS nvarchar(255)) AS TRANSACTION_PARTNER` |
| `TRANSACTION_PURPOSE` | Placeholder | `CAST(NULL AS nvarchar(255)) AS TRANSACTION_PURPOSE` |
| `TRANSACTION_SOURCE` | Source | `t.sourcetransaction AS TRANSACTION_SOURCE` |
| `TRANSACTION_TYPE` | Source | `t.recordtype AS TRANSACTION_TYPE` |
| `TRANSACTION_WEBSITE` | Placeholder | `CAST(NULL AS nvarchar(255)) AS TRANSACTION_WEBSITE` |
| `TRANSFER_LOCATION` | Placeholder | `CAST(NULL AS bigint) AS TRANSFER_LOCATION` |
| `TRANSFER_STATUS_ID` | Placeholder | `CAST(NULL AS bigint) AS TRANSFER_STATUS_ID` |
| `VENDOR_ID` | Placeholder | `CAST(NULL AS bigint) AS VENDOR_ID` |
| `VENDOR_NUMBER` | Placeholder | `CAST(NULL AS nvarchar(255)) AS VENDOR_NUMBER` |
| `FULLY_APPROVED` | Source | `t.custbody_ccc_po_fully_approved AS FULLY_APPROVED` |
| `LAST_APPROVED_BY_ID` | Source | `t.custbody_ccc_po_last_approved_by AS LAST_APPROVED_BY_ID` |
| `LAST_APPROVED_ON` | Source | `t.custbody_ccc_po_last_approved_on AS LAST_APPROVED_ON` |
| `PO_APPROVAL_RESET` | Placeholder | `CAST(NULL AS nvarchar(255)) AS PO_APPROVAL_RESET` |
| `PO_APPROVAL_ROUTE` | Placeholder | `CAST(NULL AS nvarchar(255)) AS PO_APPROVAL_ROUTE` |
| `PO_APPROVAL_THRESHOLD_` | Placeholder | `CAST(NULL AS nvarchar(255)) AS PO_APPROVAL_THRESHOLD_` |
| `PO_APPROVAL_WORKFLOW_ID` | Placeholder | `CAST(NULL AS nvarchar(255)) AS PO_APPROVAL_WORKFLOW_ID` |
| `PO_CREATED_FROM_DATA` | Source | `t.custbody_ccc_po_created_from_data AS PO_CREATED_FROM_DATA` |
| `REJECTION_REASON` | Placeholder | `CAST(NULL AS nvarchar(255)) AS REJECTION_REASON` |
| `REQUESTOR_ID` | Placeholder | `CAST(NULL AS bigint) AS REQUESTOR_ID` |
| `BIN_TRANSFER_INVENTORY_STATUS` | Source | `t.custbody_ccc_bin_xfer_inv_status_val AS BIN_TRANSFER_INVENTORY_STATUS` |
| `PO_PREVIOUSLY_APPROVED` | Placeholder | `CAST(NULL AS nvarchar(255)) AS PO_PREVIOUSLY_APPROVED` |
| `SHOPIFY_NEW_CUSTOMER` | Placeholder | `CAST(NULL AS nvarchar(255)) AS SHOPIFY_NEW_CUSTOMER` |
| `SHOPIFY_SUBSCRIPTION` | Placeholder | `CAST(NULL AS nvarchar(255)) AS SHOPIFY_SUBSCRIPTION` |
| `STOP_` | Placeholder | `CAST(NULL AS nvarchar(255)) AS STOP_` |
| `TOTAL_NUMBER_OF_ITEM_LINES` | Placeholder | `CAST(NULL AS int) AS TOTAL_NUMBER_OF_ITEM_LINES` |
| `ENTITY_BANK_CUSTOMER_ID` | Source | `t.custbody_10184_customer_entity_bank AS ENTITY_BANK_CUSTOMER_ID` |
| `SHOPIFY_TAGS` | Placeholder | `CAST(NULL AS nvarchar(255)) AS SHOPIFY_TAGS` |
| `TOTAL_ITEM_WEIGHT_LBS` | Placeholder | `CAST(NULL AS decimal(18,4)) AS TOTAL_ITEM_WEIGHT_LBS` |
| `VENDOR_ADDRESS_CODE` | Placeholder | `CAST(NULL AS nvarchar(255)) AS VENDOR_ADDRESS_CODE` |
| `VENDOR_ADDRESS_QUALIFIER` | Placeholder | `CAST(NULL AS nvarchar(255)) AS VENDOR_ADDRESS_QUALIFIER` |
| `RELATED_PURCHASE_ORDER_ID` | Placeholder | `CAST(NULL AS bigint) AS RELATED_PURCHASE_ORDER_ID` |
| `CUSTOMER_NOTES` | Source | `t.custbody_ccc_customer_notes AS CUSTOMER_NOTES` |
| `BYPASS_LOCAL_DELIVERY` | Source | `t.custbody_ccc_bypas_local_delivery AS BYPASS_LOCAL_DELIVERY` |
| `NO_OLX_DELIVERY_TAG` | Source | `t.custbody_ccc_no_olx_delivery_tag AS NO_OLX_DELIVERY_TAG` |
| `SALES_ORDER_IS_DELIVERED` | Placeholder | `CAST(NULL AS nvarchar(255)) AS SALES_ORDER_IS_DELIVERED` |
| `TOTAL_ITEM_COMMITTED_QUANTITY` | Placeholder | `CAST(NULL AS decimal(18,4)) AS TOTAL_ITEM_COMMITTED_QUANTITY` |
| `TOTAL_ITEM_QUANTITY` | Placeholder | `CAST(NULL AS decimal(18,4)) AS TOTAL_ITEM_QUANTITY` |
| `MARKETING_ORDER_TYPE_ID` | Source | `t.custbody_marketing_order_type AS MARKETING_ORDER_TYPE_ID` |

### 4.14 `NetSuite2_View_Transaction_Lines`

**Purpose:** Maps NetSuite transaction lines and accounting-line accounts into a reporting compatibility view.

**Expected grain:** Transaction-line grain, subject to accounting-line join multiplicity.

**Dependencies:**
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.TransactionAccountingLine`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `ACCOUNT_ID` | Source | `tal.account AS ACCOUNT_ID` |
| `AMOUNT` | Source | `tl.netamount AS AMOUNT` |
| `BOM_QUANTITY` | Source | `tl.bomquantity AS BOM_QUANTITY` |
| `CLASS_ID` | Source | `tl.class AS CLASS_ID` |
| `COMPONENT_ID` | Source | `tl.assemblycomponent AS COMPONENT_ID` |
| `COMPONENT_YIELD` | Source | `tl.componentyield AS COMPONENT_YIELD` |
| `CONVERSION_RATE` | Source | `tl.custcol_sps_tp_conversion_rate AS CONVERSION_RATE` |
| `COST_ESTIMATE_TYPE` | Source | `tl.costestimatetype AS COST_ESTIMATE_TYPE` |
| `CREATED_FROM` | Source | `tl.createdfrom AS CREATED_FROM` |
| `DATE_CLEARED` | Source | `tl.cleareddate AS DATE_CLEARED` |
| `DATE_CLOSED` | Source | `tl.closedate AS DATE_CLOSED` |
| `DATE_CREATED` | Source | `tl.linecreateddate AS DATE_CREATED` |
| `DEPARTMENT_DESCRIPTION` | Source | `tl.custcol_sps_departmentdescription AS DEPARTMENT_DESCRIPTION` |
| `DEPARTMENT_ID` | Source | `tl.department AS DEPARTMENT_ID` |
| `DEPT_CODE` | Source | `tl.custcol_sps_department AS DEPT_CODE` |
| `EXPENSE_CATEGORY_ID` | Placeholder | `CAST(NULL AS bigint) AS EXPENSE_CATEGORY_ID` |
| `GL_NUMBER` | Placeholder | `CAST(NULL AS nvarchar(255)) AS GL_NUMBER` |
| `GL_SEQUENCE` | Placeholder | `CAST(NULL AS int) AS GL_SEQUENCE` |
| `GL_SEQUENCE_ID` | Placeholder | `CAST(NULL AS bigint) AS GL_SEQUENCE_ID` |
| `GROSS_AMOUNT` | Placeholder | `CAST(NULL AS decimal(18,4)) AS GROSS_AMOUNT` |
| `HAS_COST_LINE` | Source | `tl.hascostline AS HAS_COST_LINE` |
| `ISCLEARED` | Source | `tl.cleared AS ISCLEARED` |
| `IS_LANDED_COST` | Placeholder | `CAST(NULL AS bit) AS IS_LANDED_COST` |
| `IS_ORDER_LINE_ITEM` | Placeholder | `CAST(NULL AS bit) AS IS_ORDER_LINE_ITEM` |
| `IS_SCRAP` | Placeholder | `CAST(NULL AS bit) AS IS_SCRAP` |
| `ITEM_COUNT` | Source | `tl.quantity AS ITEM_COUNT` |
| `ITEM_ID` | Source | `tl.item AS ITEM_ID` |
| `ITEM_SOURCE` | Source | `tl.itemsource AS ITEM_SOURCE` |
| `ITEM_UNIT_PRICE` | Source | `tl.custcol_ccc_ehub_item_price AS ITEM_UNIT_PRICE` |
| `ITEM_WEIGHT` | Placeholder | `CAST(NULL AS decimal(18,4)) AS ITEM_WEIGHT` |
| `KIT_PART_NUMBER` | Source | `tl.kitcomponent AS KIT_PART_NUMBER` |
| `LANDED_COST_SOURCE_LINE_ID` | Source | `tl.landedcostsourcelineid AS LANDED_COST_SOURCE_LINE_ID` |
| `LANDED_COST_TEMPLATE_ID` | Placeholder | `CAST(NULL AS bigint) AS LANDED_COST_TEMPLATE_ID` |
| `LOCATION_ID` | Source | `tl.location AS LOCATION_ID` |
| `LOT_NUMBER` | Source | `tl.custcol_ccc_lot_number AS LOT_NUMBER` |
| `MEMO` | Source | `tl.memo AS MEMO` |
| `PERIOD_CLOSED` | Source | `tl.periodclosed AS PERIOD_CLOSED` |
| `SUBSIDIARY_ID` | Source | `tl.subsidiary AS SUBSIDIARY_ID` |
| `TRANSACTION_DATE` | Placeholder | `CAST(NULL AS datetime) AS TRANSACTION_DATE` |
| `TRANSACTION_ID` | Source | `tl.[transaction] AS TRANSACTION_ID` |
| `TRANSACTION_LINE_ID` | Source | `tl.id AS TRANSACTION_LINE_ID` |
| `TRANSACTION_ORDER` | Placeholder | `CAST(NULL AS int) AS TRANSACTION_ORDER` |
| `TRANSFER_ORDER_ITEM_LINE` | Source | `tl.transferorderitemlineid AS TRANSFER_ORDER_ITEM_LINE` |
| `TRANSFER_ORDER_LINE_TYPE` | Source | `tl.transactionlinetype AS TRANSFER_ORDER_LINE_TYPE` |
| `UNIQUE_KEY` | Source | `tl.uniquekey AS UNIQUE_KEY` |
| `UNIT_OF_MEASURE_ID` | Source | `tl.units AS UNIT_OF_MEASURE_ID` |
| `UPC` | Source | `tl.custcol_sps_upc AS UPC` |
| `CheckSumVal` | Placeholder | `CAST(NULL AS varbinary(8000)) AS CheckSumVal` |
| `UNIT_QTY_CONVERTED` | Source | `tl.custcol_sps_uom_qty_converted AS UNIT_QTY_CONVERTED` |
| `IS_ITEM_LINE` | Source | `tl.custcol_ccc_is_item_line AS IS_ITEM_LINE` |
| `ITEM_WEIGHT_LBS` | Source | `tl.custcol_ccc_item_weight_lbs AS ITEM_WEIGHT_LBS` |
| `TOTAL_ITEM_WEIGHT_LBS` | Source | `tl.custcol_ccc_total_item_weight_lbs AS TOTAL_ITEM_WEIGHT_LBS` |
| `GROSS_AMOUNT1` | Placeholder | `CAST(NULL AS decimal(18,4)) AS GROSS_AMOUNT1` |
| `GROSS_AMOUNT_0` | Placeholder | `CAST(NULL AS decimal(18,4)) AS GROSS_AMOUNT_0` |
| `NET_WEIGHT` | Placeholder | `CAST(NULL AS decimal(18,4)) AS NET_WEIGHT` |
| `UNIT_OF_MEASURE` | Source | `tl.custcol_sps_orderqtyuom AS UNIT_OF_MEASURE` |

### 4.15 `NetSuite2_View_TransactionsJoin`

**Purpose:** Combines transactions, lines, items, accounts, periods, and classifications into a finance reporting dataset.

**Expected grain:** Row grain follows the primary source and joins defined in the view.

**Dependencies:**
- `Finance.dbo.NetSuite2_View_Transactions`
- `Finance.dbo.NetSuite2_View_Transaction_Lines`
- `Source_NetSuite.ns2.TransactionAccountingLine`
- `Source_NetSuite.ns2.Account`
- `Finance.dbo.NetSuite2_View_Items`
- `Finance.dbo.NetSuite2_View_AccountingPeriod`
- `Finance.dbo.Classification`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `TRANID` | Source | `vt.TRANID` |
| `TRANSACTION_NUMBER` | Source | `vt.TRANSACTION_NUMBER` |
| `Type` | Source | `vt.TRANSACTION_TYPE AS [Type]` |
| `Date` | Source | `vt.TRANDATE AS [Date]` |
| `PERIOD` | Source | `vap.PERIOD` |
| `YEAR` | Source | `vap.[YEAR]` |
| `SalesOrderNum` | Source | `vt.CREATED_FROM_ID AS SalesOrderNum` |
| `ACCOUNT_ID` | Source | `tal.account AS ACCOUNT_ID` |
| `Account` | Source | `a.acctnumber AS Account` |
| `AccountName` | Source | `a.accountsearchdisplayname AS AccountName` |
| `Qty` | Source | `vtl.ITEM_COUNT AS Qty` |
| `BarCount` | Source | `vi.BARS AS BarCount` |
| `Bars` | Derived | `vi.BARS * vtl.ITEM_COUNT AS Bars` |
| `Amount` | Source | `vtl.AMOUNT AS Amount` |
| `Item` | Source | `vi.FULL_NAME AS Item` |
| `ItemDesc` | Source | `vi.DISPLAYNAME AS ItemDesc` |
| `ItemType` | Source | `vi.TYPE_NAME AS ItemType` |
| `Class` | Source | `c.FULLNAME AS Class` |
| `ItemClass` | Source | `ci.FULLNAME AS ItemClass` |

### 4.16 `NetSuite2_View_FutureOrderSupplyVisibility`

**Purpose:** Unifies open sales-order demand with inventory, transfer-order, and work-order supply candidates to identify potentially uncovered quantities.

**Expected grain:** One row per sales-order line.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.Customer`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.item`
- `Source_NetSuite.ns2.transactionstatus`
- `Source_NetSuite.ns2.Location`
- `Source_NetSuite.ns2.customerCategory`
- `dbo.NetSuite2_View_InventoryOnHand`
- `dbo.NetSuite2_View_AssemblyBuildSum`
- `inventory`

**Key filters found in the SQL:**
- `Record type: recordtype = 'salesorder'`
- `Record type: recordtype IN ('transfer', 'transferorder')`
- `Record type: recordtype = 'workorder'`
- `Status: status IN ('A', 'B', 'C', 'H', 'Y', 'D')`
- `Status: fullname IN ( 'Sales Order : Pending Approval', 'Sales Order : Pending Fulfillment', 'Sales Order : Pending Billing', 'Sales Order : Pending Billing/Partially Fulfilled' )`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `SalesOrderTransactionID` | Source | `so.SalesOrderTransactionID` |
| `SalesOrderLineID` | Source | `so.SalesOrderLineID` |
| `SalesOrderDate` | Source | `so.SalesOrderDate` |
| `SalesOrderID` | Source | `so.SalesOrderID` |
| `PlannedShipDate` | Source | `so.PlannedShipDate` |
| `MABD` | Source | `so.MABD` |
| `SalesOrderStatus` | Source | `so.SalesOrderStatus` |
| `CustomerID` | Source | `so.CustomerID` |
| `CustomerName` | Source | `so.CustomerName` |
| `CustomerEntityID` | Source | `so.CustomerEntityID` |
| `CustomerCategory` | Source | `so.CustomerCategory` |
| `ItemID` | Source | `so.ItemID` |
| `ItemFullName` | Source | `so.ItemFullName` |
| `ItemDescription` | Source | `so.ItemDescription` |
| `SalesOrderLocationID` | Source | `so.SalesOrderLocationID` |
| `SalesOrderLocation` | Source | `so.SalesOrderLocation` |
| `QuantityOrdered` | Source | `so.QuantityOrdered` |
| `QuantityCommitted` | Source | `so.QuantityCommitted` |
| `QuantityAllocated` | Source | `so.QuantityAllocated` |
| `QuantityDemandAllocated` | Source | `so.QuantityDemandAllocated` |
| `NetSuiteBackorderedQty` | Source | `so.NetSuiteBackorderedQty` |
| `OnHandAtOrderLocation` | Derived | `COALESCE(inv.OnHandQty, 0) AS OnHandAtOrderLocation` |
| `AvailableAtOrderLocation` | Derived | `COALESCE(inv.AvailableQty, 0) AS AvailableAtOrderLocation` |
| `OnOrderAtOrderLocation` | Derived | `COALESCE(inv.OnOrderQty, 0) AS OnOrderAtOrderLocation` |
| `CandidateTransferQty` | Derived | `COALESCE(tr.OpenTransferQty, 0) AS CandidateTransferQty` |
| `OpenTransferOrderCount` | Source | `tr.OpenTransferOrderCount` |
| `EarliestTransferOrderDate` | Source | `tr.EarliestTransferOrderDate` |
| `RelatedTransferOrders` | Source | `tr.RelatedTransferOrders` |
| `CandidateActiveWOQty` | Derived | `COALESCE(wo.ActiveWOQty, 0) AS CandidateActiveWOQty` |
| `CandidatePlannedWOQty` | Derived | `COALESCE(wo.PlannedWOQty, 0) AS CandidatePlannedWOQty` |
| `EarliestWOCompletionDate` | Source | `wo.EarliestWOCompletionDate` |
| `RelatedWorkOrders` | Source | `wo.RelatedWorkOrders` |
| `CommittedPercent` | Derived | `CASE WHEN NULLIF(ABS(so.QuantityOrdered), 0) IS NULL THEN 0 ELSE ABS(so.QuantityCommitted) / NULLIF(ABS(so.QuantityOrdered), 0) END AS CommittedPercent` |
| `AllocatedPercent` | Derived | `CASE WHEN NULLIF(ABS(so.QuantityOrdered), 0) IS NULL THEN 0 ELSE ABS(so.QuantityAllocated) / NULLIF(ABS(so.QuantityOrdered), 0) END AS AllocatedPercent` |
| `CalculatedAllocationGapQty` | Derived | `CASE WHEN ABS(so.QuantityOrdered) - ABS(so.QuantityAllocated) > 0 THEN ABS(so.QuantityOrdered) - ABS(so.QuantityAllocated) ELSE 0 END AS CalculatedAllocationGapQty` |
| `CandidateUncoveredQty` | Derived | `CASE WHEN COALESCE(inv.AvailableQty, 0) + COALESCE(tr.OpenTransferQty, 0) + COALESCE(wo.ActiveWOQty, 0) + COALESCE(wo.PlannedWOQty, 0) < ABS(so.QuantityOrdered) THEN ABS(so.QuantityOrdered) - ( COALESCE(inv.AvailableQty, 0) + COALESCE(tr.OpenTransferQty, 0) + COALESCE(wo.ActiveWOQty, 0) + COALESCE(wo.PlannedWOQty, 0) ) ELSE 0 END AS CandidateUncoveredQty` |
| `CandidateSupplyStatus` | Derived | `CASE WHEN ABS(so.QuantityCommitted) >= ABS(so.QuantityOrdered) THEN 'Committed from inventory' WHEN COALESCE(inv.AvailableQty, 0) >= ABS(so.QuantityOrdered) THEN 'Inventory available' WHEN COALESCE(inv.AvailableQty, 0) + COALESCE(tr.OpenTransferQty, 0) >= ABS(so.QuantityOrdered) THEN 'Potentially covered by transfer' WHEN COALESCE(inv.AvailableQty, 0) + COALESCE(tr.OpenTransferQty, 0) + COALESCE(wo.ActiveWOQty, 0) >= ABS(so.QuantityOrdered) THEN 'Potentially covered by active WO' WHEN COALESCE(inv.AvailableQty, 0) + COALESCE(tr.OpenTransferQty, 0) + COALESCE(wo.ActiveWOQty, 0) + COALESCE(wo.PlannedWOQty, 0) >= ABS(so.QuantityOrdered) THEN 'Potentially covered by planned WO' ELSE 'No sufficient supply identified' END AS CandidateSupplyStatus` |

### 4.17 `NetSuite2_View_Assemblies`

**Purpose:** Lists work-order and assembly-build transaction lines with item, quantity, amount, and lot number.

**Expected grain:** Row grain follows the primary source and joins defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.item`

**Key filters found in the SQL:**
- `Record type: recordtype IN ('workorder', 'assemblybuild')`
- `Date: trandate >= '2024-11-01'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `tranid` | Source | `t.tranid` |
| `trandate` | Source | `t.trandate` |
| `TRANSACTION_TYPE` | Source | `t.recordtype AS TRANSACTION_TYPE` |
| `FULL_NAME` | Source | `i.fullname AS FULL_NAME` |
| `DISPLAYNAME` | Derived | `CASE WHEN NULLIF(LTRIM(RTRIM(i.displayname)), '') IS NOT NULL AND NULLIF(LTRIM(RTRIM(i.description)), '') IS NOT NULL THEN i.displayname + ' - ' + i.description WHEN NULLIF(LTRIM(RTRIM(i.displayname)), '') IS NOT NULL THEN i.displayname ELSE i.description END AS DISPLAYNAME` |
| `ITEM_COUNT` | Source | `tl.quantity AS ITEM_COUNT` |
| `AMOUNT` | Source | `tl.netamount AS AMOUNT` |
| `LOT_NUMBER` | Source | `tl.custcol_ccc_lot_number AS LOT_NUMBER` |

### 4.18 `NetSuite2_View_AssembliesLotCode`

**Purpose:** Provides lot-level assembly build/unbuild output and consumption with item, account, period, and line context.

**Expected grain:** Transaction-line and inventory-assignment/lot grain.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.TransactionAccountingLine`
- `Source_NetSuite.ns2.Account`
- `Source_NetSuite.ns2.item`
- `Source_NetSuite.ns2.accountingPeriod`
- `Source_NetSuite.ns2.CUSTOMLIST_WO_LINE_NO`
- `Source_NetSuite.ns2.InventoryAssignment`
- `Source_NetSuite.ns2.inventoryNumber`
- `Source_NetSuite.ns2.TransactionBinNumbers`

**Key filters found in the SQL:**
- `Record type: recordtype IN ('assemblybuild', 'assemblyunbuild')`
- `Date: trandate >= '2026-04-01'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `PeriodEnding` | Source | `ap.enddate AS PeriodEnding` |
| `Date` | Source | `t.trandate AS [Date]` |
| `DocumentNumber` | Source | `t.tranid AS DocumentNumber` |
| `memo` | Source | `t.memo` |
| `TransactionType` | Source | `t.recordtype AS TransactionType` |
| `CREATE_DATE` | Source | `t.createddate AS CREATE_DATE` |
| `AssemblyItem` | Source | `t.custbody_wo_assembly AS AssemblyItem` |
| `Quantity` | Aggregate | `SUM( CASE WHEN t.custbody_wo_assembly = i.fullname THEN ia.quantity ELSE -1 * ia.quantity END ) As Quantity` |
| `EntryType` | Derived | `CASE WHEN t.custbody_wo_assembly = i.fullname THEN 'OUTPUT' ELSE 'CONSUMPTION' END AS EntryType` |
| `UOM` | Derived | `CASE WHEN i.unitstype = 2 THEN 'EA' WHEN i.unitstype = 1 THEN 'KG' ELSE '' END AS UOM` |
| `ItemGroup` | Derived | `CASE WHEN a.acctnumber = '121050' THEN 'FG' WHEN a.acctnumber = '121020' THEN 'Packaging' WHEN a.acctnumber = '121010' THEN 'Ingredient' WHEN a.acctnumber = '121060' AND i.custitem_bars <= 1 THEN 'Bar' WHEN i.itemtype = 'Assembly' AND i.unitstype = 1 THEN 'Batch' ELSE '' END AS ItemGroup` |
| `INVENTORY_NUMBER` | Source | `inu.inventorynumber AS INVENTORY_NUMBER` |
| `AMOUNT` | Source | `tl.netamount AS AMOUNT` |
| `ItemID` | Source | `tl.item AS ItemID` |
| `Item` | Source | `i.fullname AS Item` |
| `ItemDescription` | Derived | `COALESCE( NULLIF(LTRIM(RTRIM(i.displayname)), ''), NULLIF(LTRIM(RTRIM(i.description)), ''), NULLIF(LTRIM(RTRIM(i.purchasedescription)), '') ) AS ItemDescription` |
| `BarCount` | Source | `i.custitem_bars AS BarCount` |
| `LineName` | Source | `ln2.name AS LineName` |

### 4.19 `NetSuite2_View_BarsProdSummary`

**Purpose:** Summarizes production units, bars, and amounts by date, assembly, and asset account.

**Expected grain:** Aggregated at the GROUP BY dimensions defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.Item`
- `Source_NetSuite.ns2.Account`

**Key filters found in the SQL:**
- `Record type: recordtype IN ('assemblybuild', 'assemblyunbuild')`
- `Date: trandate >= '2024-01-01'`
- `Date: trandate <= '2024-02-29'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `Period` | Source | `MONTH(t.trandate) AS Period` |
| `Trandate` | Source | `t.trandate AS Trandate` |
| `TransType` | Source | `t.recordtype AS TransType` |
| `AssemblyItem` | Source | `t.custbody_wo_assembly AS AssemblyItem` |
| `Account` | Source | `a.externalid AS Account` |
| `AccountName` | Source | `a.accountsearchdisplaynamecopy AS AccountName` |
| `Units` | Aggregate | `SUM(tl.quantity) AS Units` |
| `Bars` | Aggregate | `SUM(tl.quantity * i.custitem_bars) AS Bars` |
| `Amount` | Aggregate | `SUM(tl.netamount) AS Amount` |

### 4.20 `NetSuite2_View_BarsProduced`

**Purpose:** Summarizes assembly build/unbuild activity by item and classifies output versus consumption.

**Expected grain:** Aggregated at the GROUP BY dimensions defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.Item`
- `Source_NetSuite.ns2.Account`

**Key filters found in the SQL:**
- `Record type: recordtype IN ('assemblybuild', 'assemblyunbuild')`
- `Date: trandate >= '2025-01-01'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `Period` | Source | `MONTH(t.trandate) AS Period` |
| `Trandate` | Source | `t.trandate AS Trandate` |
| `TransType` | Source | `t.recordtype AS TransType` |
| `AssemblyItem` | Source | `t.custbody_wo_assembly AS AssemblyItem` |
| `Item` | Source | `i.fullname AS Item` |
| `ItemDesc` | Derived | `COALESCE( NULLIF(LTRIM(RTRIM(i.displayname)), ''), NULLIF(LTRIM(RTRIM(i.description)), ''), NULLIF(LTRIM(RTRIM(i.purchasedescription)), '') ) AS ItemDesc` |
| `ItemType` | Source | `i.itemtype AS ItemType` |
| `Account` | Source | `a.externalid AS Account` |
| `AccountName` | Source | `a.accountsearchdisplayname AS AccountName` |
| `BarCount` | Derived | `ISNULL(i.custitem_bars, 0) AS BarCount` |
| `EntryType` | Derived | `CASE WHEN t.custbody_wo_assembly = i.fullname THEN 'OUTPUT' ELSE 'CONSUMPTION' END AS EntryType` |
| `UOM` | Derived | `CASE WHEN i.unitstype = 2 THEN 'EA' WHEN i.unitstype = 1 THEN 'KG' ELSE '' END AS UOM` |
| `ItemGroup` | Derived | `CASE WHEN a.externalid = '121050' THEN 'FG' WHEN a.externalid = '121020' THEN 'Packaging' WHEN a.externalid = '121010' THEN 'Ingredient' WHEN a.externalid = '121060' AND i.custitem_bars <= 1 THEN 'Bar' WHEN i.itemtype = 'Assembly' AND i.unitstype = 1 THEN 'Batch' ELSE '' END AS ItemGroup` |
| `Units` | Aggregate | `SUM(tl.quantity) AS Units` |
| `Bars` | Aggregate | `SUM(tl.quantity * ISNULL(i.custitem_bars, 0)) AS Bars` |
| `Amount` | Aggregate | `SUM(tl.netamount) AS Amount` |

### 4.21 `NetSuite2_View_BarsSold`

**Purpose:** Aggregates units and bars sold by transaction date and sales channel using posting revenue-account filters.

**Expected grain:** Aggregated at the GROUP BY dimensions defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.TransactionAccountingLine`
- `Source_NetSuite.ns2.item`
- `Source_NetSuite.ns2.Account`
- `Source_NetSuite.ns2.customer`
- `Source_NetSuite.ns2.classification`
- `Source_NetSuite.ns2.CUSTOMRECORD_CSEG_BB_SALES_CHANN`

**Key filters found in the SQL:**
- `Date: trandate >= '2023-07-01'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `Trandate` | Source | `CAST(t.trandate AS date) AS Trandate` |
| `Sales_Channel` | Source | `sc.[name] AS Sales_Channel` |
| `Total_Units` | Aggregate | `SUM(ABS(tl.quantity)) AS Total_Units` |
| `Total_Bars` | Aggregate | `SUM(ABS(tl.quantity)*i.custitem_bars) AS Total_Bars` |

### 4.22 `NetSuite2_View_Batchyield`

**Purpose:** Provides lot-level assembly transaction detail intended for batch-yield analysis, including output/consumption, quantity, item group, and line.

**Expected grain:** Transaction-line and inventory-assignment/lot grain.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.InventoryAssignment`
- `Source_NetSuite.ns2.inventoryNumber`
- `Source_NetSuite.ns2.item`
- `Source_NetSuite.ns2.accountingPeriod`
- `Source_NetSuite.ns2.Account`
- `Source_NetSuite.ns2.CUSTOMLIST_WO_LINE_NO`

**Key filters found in the SQL:**
- `Record type: recordtype IN ('assemblybuild', 'assemblyunbuild')`
- `Date: trandate >= '2026-04-01'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `PeriodEnding` | Source | `ap.enddate AS PeriodEnding` |
| `Date` | Source | `t.trandate AS [Date]` |
| `DocumentNumber` | Source | `t.tranid AS DocumentNumber` |
| `memo` | Source | `t.memo` |
| `TransactionType` | Source | `t.recordtype AS TransactionType` |
| `CREATE_DATE` | Source | `t.createddate AS CREATE_DATE` |
| `AssemblyItem` | Source | `t.custbody_wo_assembly AS AssemblyItem` |
| `Quantity` | Source | `tl.quantity AS Quantity` |
| `EntryType` | Derived | `CASE WHEN t.custbody_wo_assembly = i.fullname THEN 'OUTPUT' ELSE 'CONSUMPTION' END AS EntryType` |
| `UOM` | Derived | `CASE WHEN i.unitstype = 2 THEN 'EA' WHEN i.unitstype = 1 THEN 'KG' ELSE '' END AS UOM` |
| `ItemGroup` | Derived | `CASE WHEN a.acctnumber = '121050' THEN 'FG' WHEN a.acctnumber = '121020' THEN 'Packaging' WHEN a.acctnumber = '121010' THEN 'Ingredient' WHEN a.acctnumber = '121060' AND i.custitem_bars <= 1 THEN 'Bar' WHEN i.itemtype = 'Assembly' AND i.unitstype = 1 THEN 'Batch' ELSE '' END AS ItemGroup` |
| `INVENTORY_NUMBER` | Source | `inv.inventorynumber AS INVENTORY_NUMBER` |
| `AMOUNT` | Source | `tl.netamount AS AMOUNT` |
| `ItemID` | Source | `tl.item AS ItemID` |
| `Item` | Source | `i.fullname AS Item` |
| `ItemDescription` | Derived | `COALESCE( NULLIF(LTRIM(RTRIM(i.displayname)), ''), NULLIF(LTRIM(RTRIM(i.description)), ''), NULLIF(LTRIM(RTRIM(i.purchasedescription)), '') ) AS ItemDescription` |
| `BarCount` | Source | `i.custitem_bars AS BarCount` |
| `LineName` | Source | `ln2.name AS LineName` |

### 4.23 `NetSuite2_View_BillOfMaterials`

**Purpose:** Returns active BOM revisions and their component quantities, yields, dates, and item details.

**Expected grain:** One row per active BOM revision component.

**Dependencies:**
- `Source_NetSuite.ns2.bom`
- `Source_NetSuite.ns2.bomRevision`
- `Source_NetSuite.ns2.BomRevisionComponent`
- `Source_NetSuite.ns2.Item`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `DISPLAYNAME` | Derived | `CASE WHEN NULLIF(LTRIM(RTRIM(i.displayname)), '') IS NOT NULL AND NULLIF(LTRIM(RTRIM(i.description)), '') IS NOT NULL THEN i.displayname + ' - ' + i.description WHEN NULLIF(LTRIM(RTRIM(i.displayname)), '') IS NOT NULL THEN i.displayname ELSE i.description END AS DISPLAYNAME` |
| `BILL_OF_MATERIALS_ID` | Source | `bom.id AS BILL_OF_MATERIALS_ID` |
| `DateCreatedBOM` | Source | `bom.createddate AS DateCreatedBOM` |
| `memo` | Source | `bom.memo` |
| `Assembly/BOMName` | Derived | `bom.name AS [Assembly/BOMName]` |
| `RevName` | Source | `br.name AS RevName` |
| `DateCreatedRev` | Source | `br.createddate AS DateCreatedRev` |
| `DateEffective` | Source | `br.effectivestartdate AS DateEffective` |
| `DateObsolete` | Source | `br.effectiveenddate AS DateObsolete` |
| `ItemID` | Source | `brc.item AS ItemID` |
| `Quantity` | Source | `brc.bomquantity AS Quantity` |
| `Yield` | Source | `brc.componentyield AS Yield` |
| `ComponentName` | Source | `brc.id AS ComponentName` |
| `UOM` | Source | `brc.units AS UOM` |
| `ItemSource` | Source | `brc.itemsource AS ItemSource` |
| `NULL AS Item ID Key` | Placeholder | `NULL AS [Item ID Key]` |

### 4.24 `NetSuite2_View_LastRevaluationByItem`

**Purpose:** Identifies the latest inventory cost revaluation transaction ID by item and location.

**Expected grain:** Aggregated at the GROUP BY dimensions defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.Item`

**Key filters found in the SQL:**
- `Record type: recordtype = 'inventorycostrevaluation'`
- `Date: trandate >= CONVERT(datetime,`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `LastTransaction_ID` | Aggregate | `MAX(t.id) AS LastTransaction_ID` |
| `ITEM_ID` | Source | `tl.item AS ITEM_ID` |
| `FULL_NAME` | Source | `i.fullname AS FULL_NAME` |
| `DISPLAYNAME` | Derived | `COALESCE(i.displayname,i.description,i.purchasedescription) AS DISPLAYNAME` |
| `LOCATION_ID` | Source | `t.location AS LOCATION_ID` |

### 4.25 `NetSuite2_View_LotTrace`

**Purpose:** Provides lot-level transaction traceability across transaction lines, inventory assignments, bins, items, and accounts.

**Expected grain:** Transaction-line and inventory-assignment/lot grain.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.TransactionAccountingLine`
- `Source_NetSuite.ns2.Item`
- `Source_NetSuite.ns2.InventoryAssignment`
- `Source_NetSuite.ns2.inventoryNumber`
- `Source_NetSuite.ns2.TransactionBinNumbers`

**Key filters found in the SQL:**
- `Date: trandate >= '2025-01-01'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `TRANID` | Source | `t.tranid AS TRANID` |
| `TRANSACTION_NUMBER` | Source | `t.transactionnumber AS TRANSACTION_NUMBER` |
| `TRANSACTION_LINE_ID` | Source | `tl.id AS TRANSACTION_LINE_ID` |
| `TRANSACTION_TYPE` | Source | `t.recordtype AS TRANSACTION_TYPE` |
| `TRANDATE` | Source | `t.trandate AS TRANDATE` |
| `ASSEMBLY_ITEM` | Source | `t.custbody_wo_assembly AS ASSEMBLY_ITEM` |
| `ACCOUNT_ID` | Source | `tal.account AS ACCOUNT_ID` |
| `ITEM_COUNT` | Source | `tl.quantity AS ITEM_COUNT` |
| `QUANTITY` | Source | `ia.quantity AS QUANTITY` |
| `TOTAL_QUANTITY_OF_MEMBERS` | Placeholder | `CAST(NULL AS decimal(18,4)) AS TOTAL_QUANTITY_OF_MEMBERS` |
| `TOTAL_ITEM_QUANTITY_OF_MEMBER` | Placeholder | `CAST(NULL AS decimal(18,4)) AS TOTAL_ITEM_QUANTITY_OF_MEMBER` |
| `QTY__PACKED` | Source | `tl.quantitypacked AS QTY__PACKED` |
| `INVENTORY_NUMBER` | Source | `inu.inventorynumber AS INVENTORY_NUMBER` |
| `TP_ORDER_QTY` | Source | `tl.custcol_sps_tp_order_qty AS TP_ORDER_QTY` |
| `TP_QTY` | Source | `tl.custcol_sps_tpqty AS TP_QTY` |
| `UNIT_QTY_CONVERTED` | Source | `tl.custcol_sps_uom_qty_converted AS UNIT_QTY_CONVERTED` |
| `QUANTITY_ALLOCATED` | Source | `tl.quantityallocated AS QUANTITY_ALLOCATED` |
| `QUANTITY_COMMITTED` | Source | `tl.quantitycommitted AS QUANTITY_COMMITTED` |
| `QUANTITY_PACKED` | Source | `tl.quantitypacked AS QUANTITY_PACKED` |
| `QUANTITY_PICKED` | Source | `tl.quantitypicked AS QUANTITY_PICKED` |
| `QUANTITY_RECEIVED_IN_SHIPMENT` | Source | `tl.quantityshiprecv AS QUANTITY_RECEIVED_IN_SHIPMENT` |
| `BOM_QUANTITY` | Source | `tl.bomquantity AS BOM_QUANTITY` |
| `AMOUNT` | Source | `tl.netamount AS AMOUNT` |
| `GROSS_AMOUNT` | Placeholder | `CAST(NULL AS decimal(18,4)) AS GROSS_AMOUNT` |
| `ITEM_ID` | Source | `tl.item AS ITEM_ID` |
| `FULL_NAME` | Source | `i.fullname AS FULL_NAME` |
| `DISPLAYNAME` | Derived | `COALESCE( NULLIF(LTRIM(RTRIM(i.displayname)), ''), NULLIF(LTRIM(RTRIM(i.description)), ''), NULLIF(LTRIM(RTRIM(i.purchasedescription)), '') ) AS DISPLAYNAME` |
| `EXPENSE_CATEGORY_ID` | Placeholder | `CAST(NULL AS nvarchar(255)) AS EXPENSE_CATEGORY_ID` |
| `GL_NUMBER` | Placeholder | `CAST(NULL AS nvarchar(255)) AS GL_NUMBER` |
| `HAS_COST_LINE` | Source | `tl.hascostline AS HAS_COST_LINE` |
| `IS_COST_LINE` | Source | `tl.iscogs AS IS_COST_LINE` |
| `INVENTORY_STATUS_ID` | Source | `ia.inventorystatus AS INVENTORY_STATUS_ID` |
| `BIN_ID` | Source | `ia.bin AS BIN_ID` |
| `TBN_BIN_ID` | Source | `tbn.binnumber AS TBN_BIN_ID` |
| `TBN_QUANTITY` | Source | `tbn.quantity AS TBN_QUANTITY` |

### 4.26 `NetSuite2_View_LotTrace_Option2`

**Purpose:** Provides an alternate lot-trace dataset without accounting-line dependency, retaining several unmapped placeholders.

**Expected grain:** Transaction-line and inventory-assignment/lot grain.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.Item`
- `Source_NetSuite.ns2.InventoryAssignment`
- `Source_NetSuite.ns2.inventoryNumber`
- `Source_NetSuite.ns2.TransactionBinNumbers`

**Key filters found in the SQL:**
- `Date: trandate >= '2025-01-01'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `TRANID` | Source | `t.tranid AS TRANID` |
| `TRANSACTION_NUMBER` | Source | `t.transactionnumber AS TRANSACTION_NUMBER` |
| `TRANSACTION_LINE_ID` | Source | `tl.id AS TRANSACTION_LINE_ID` |
| `TRANSACTION_TYPE` | Source | `t.recordtype AS TRANSACTION_TYPE` |
| `TRANDATE` | Source | `t.trandate AS TRANDATE` |
| `ASSEMBLY_ITEM` | Source | `t.custbody_wo_assembly AS ASSEMBLY_ITEM` |
| `ACCOUNT_ID` | Placeholder | `NULL AS ACCOUNT_ID` |
| `ITEM_COUNT` | Source | `tl.quantity AS ITEM_COUNT` |
| `QUANTITY` | Source | `ia.quantity AS QUANTITY` |
| `TOTAL_QUANTITY_OF_MEMBERS` | Placeholder | `CAST(NULL AS decimal(18,4)) AS TOTAL_QUANTITY_OF_MEMBERS` |
| `TOTAL_ITEM_QUANTITY_OF_MEMBER` | Placeholder | `CAST(NULL AS decimal(18,4)) AS TOTAL_ITEM_QUANTITY_OF_MEMBER` |
| `QTY__PACKED` | Source | `tl.quantitypacked AS QTY__PACKED` |
| `INVENTORY_NUMBER` | Source | `inu.inventorynumber AS INVENTORY_NUMBER` |
| `TP_ORDER_QTY` | Source | `tl.custcol_sps_tp_order_qty AS TP_ORDER_QTY` |
| `TP_QTY` | Source | `tl.custcol_sps_tpqty AS TP_QTY` |
| `UNIT_QTY_CONVERTED` | Source | `tl.custcol_sps_uom_qty_converted AS UNIT_QTY_CONVERTED` |
| `QUANTITY_ALLOCATED` | Source | `tl.quantityallocated AS QUANTITY_ALLOCATED` |
| `QUANTITY_COMMITTED` | Source | `tl.quantitycommitted AS QUANTITY_COMMITTED` |
| `QUANTITY_PACKED` | Source | `tl.quantitypacked AS QUANTITY_PACKED` |
| `QUANTITY_PICKED` | Source | `tl.quantitypicked AS QUANTITY_PICKED` |
| `QUANTITY_RECEIVED_IN_SHIPMENT` | Source | `tl.quantityshiprecv AS QUANTITY_RECEIVED_IN_SHIPMENT` |
| `BOM_QUANTITY` | Source | `tl.bomquantity AS BOM_QUANTITY` |
| `AMOUNT` | Source | `tl.netamount AS AMOUNT` |
| `GROSS_AMOUNT` | Placeholder | `CAST(NULL AS decimal(18,4)) AS GROSS_AMOUNT` |
| `ITEM_ID` | Source | `tl.item AS ITEM_ID` |
| `FULL_NAME` | Source | `i.fullname AS FULL_NAME` |
| `DISPLAYNAME` | Derived | `CASE WHEN NULLIF(LTRIM(RTRIM(i.displayname)), '') IS NOT NULL AND NULLIF(LTRIM(RTRIM(i.description)), '') IS NOT NULL THEN i.displayname + ' - ' + i.description WHEN NULLIF(LTRIM(RTRIM(i.displayname)), '') IS NOT NULL THEN i.displayname ELSE i.description END AS DISPLAYNAME` |
| `EXPENSE_CATEGORY_ID` | Placeholder | `CAST(NULL AS nvarchar(255)) AS EXPENSE_CATEGORY_ID` |
| `GL_NUMBER` | Placeholder | `CAST(NULL AS nvarchar(255)) AS GL_NUMBER` |
| `HAS_COST_LINE` | Source | `tl.hascostline AS HAS_COST_LINE` |
| `IS_COST_LINE` | Source | `tl.iscogs AS IS_COST_LINE` |
| `INVENTORY_STATUS_ID` | Source | `ia.inventorystatus AS INVENTORY_STATUS_ID` |
| `BIN_ID` | Source | `ia.bin AS BIN_ID` |
| `TBN_BIN_ID` | Source | `tbn.binnumber AS TBN_BIN_ID` |
| `TBN_QUANTITY` | Source | `tbn.quantity AS TBN_QUANTITY` |

### 4.27 `NetSuite2_View_MaterialsUsage`

**Purpose:** Aggregates recent assembly-build material consumption and amount by item and accounting period.

**Expected grain:** Aggregated at the GROUP BY dimensions defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.Item`
- `Source_NetSuite.ns2.accountingPeriod`
- `Source_NetSuite.ns2.Account`

**Key filters found in the SQL:**
- `Record type: recordtype = 'assemblybuild'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `ITEM_ID` | Source | `tl.item AS ITEM_ID` |
| `FULL_NAME` | Source | `i.fullname AS FULL_NAME` |
| `DISPLAYNAME` | Derived | `CASE WHEN NULLIF(LTRIM(RTRIM(i.displayname)), '') IS NOT NULL AND NULLIF(LTRIM(RTRIM(i.description)), '') IS NOT NULL THEN i.displayname + ' - ' + i.description WHEN NULLIF(LTRIM(RTRIM(i.displayname)), '') IS NOT NULL THEN i.displayname ELSE i.description END AS DISPLAYNAME` |
| `ACCOUNTNUMBER` | Source | `a.acctnumber AS ACCOUNTNUMBER` |
| `ACCOUNTNAME` | Source | `a.accountsearchdisplayname AS ACCOUNTNAME` |
| `PeriodEnding` | Source | `ap.enddate AS PeriodEnding` |
| `Year` | Source | `YEAR(ap.enddate) AS [Year]` |
| `Period` | Source | `MONTH(ap.enddate) AS Period` |
| `Used` | Aggregate | `-SUM(tl.quantity) AS Used` |
| `Amount` | Aggregate | `SUM(tl.netamount) AS Amount` |
| `ITEMTYPE` | Source | `i.itemtype AS ITEMTYPE` |

### 4.28 `NetSuite2_View_SOandCSTrans`

**Purpose:** Lists cash-sale and sales-order transaction identifiers from the configured start date.

**Expected grain:** Row grain follows the primary source and joins defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`

**Key filters found in the SQL:**
- `Record type: recordtype IN ('cashsale', 'salesorder')`
- `Date: trandate >= '2024-01-01'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `TRANSACTION_ID` | Source | `t.id AS TRANSACTION_ID` |
| `TRANID` | Source | `t.tranid AS TRANID` |

### 4.29 `NetSuite2_View_StandardCostBarsShipped`

**Purpose:** Summarizes quantities, bars, and amount for selected shipment transaction types and cost account.

**Expected grain:** Aggregated at the GROUP BY dimensions defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.TransactionAccountingLine`
- `Source_NetSuite.ns2.Account`
- `Source_NetSuite.ns2.Item`
- `Source_NetSuite.ns2.accountingPeriod`

**Key filters found in the SQL:**
- `Record type: recordtype IN ('itemfulfillment', 'cashsale')`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `PeriodEnding` | Source | `ap.enddate AS PeriodEnding` |
| `ACCOUNT_EXTID` | Source | `a.externalid AS ACCOUNT_EXTID` |
| `CLASS_ID` | Source | `tl.class AS CLASS_ID` |
| `ITEM_ID` | Source | `tl.item AS ITEM_ID` |
| `FULL_NAME` | Source | `i.fullname AS FULL_NAME` |
| `DISPLAYNAME` | Derived | `COALESCE( NULLIF(LTRIM(RTRIM(i.displayname)), ''), NULLIF(LTRIM(RTRIM(i.description)), ''), NULLIF(LTRIM(RTRIM(i.purchasedescription)), '') ) AS DISPLAYNAME` |
| `PRODUCT_TYPE_ID` | Source | `tl.cseg_ccc_prod_line AS PRODUCT_TYPE_ID` |
| `PRODUCT_CLASS_ID` | Source | `tl.cseg_product_type AS PRODUCT_CLASS_ID` |
| `Qty` | Aggregate | `SUM(tl.quantity) AS Qty` |
| `BarCount` | Derived | `ISNULL(i.custitem_bars, 0) AS BarCount` |
| `Bars` | Aggregate | `SUM(ISNULL(i.custitem_bars, 0) * tl.quantity) AS Bars` |
| `TRANSACTION_TYPE` | Source | `t2.recordtype AS TRANSACTION_TYPE` |
| `Total` | Aggregate | `SUM(tl.netamount) AS Total` |

### 4.30 `NetSuite2_View_StdCostRevaluation`

**Purpose:** Returns inventory cost revaluation line detail with old/new cost component classification.

**Expected grain:** Row grain follows the primary source and joins defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.TransactionAccountingLine`
- `Source_NetSuite.ns2.Account`
- `Source_NetSuite.ns2.item`
- `Source_NetSuite.ns2.accountingPeriod`

**Key filters found in the SQL:**
- `Record type: recordtype = 'Inventory Cost Revaluation'`
- `Date: trandate >= CONVERT(datetime,`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `TRANID` | Source | `t.tranid AS TRANID` |
| `TRANSACTION_NUMBER` | Source | `t.transactionnumber AS TRANSACTION_NUMBER` |
| `TRANSACTION_LINE_ID` | Source | `tl.id AS TRANSACTION_LINE_ID` |
| `TRANSACTION_TYPE` | Source | `t.recordtype AS TRANSACTION_TYPE` |
| `TRANDATE` | Source | `t.trandate AS TRANDATE` |
| `PeriodEnding` | Source | `ap.enddate AS PeriodEnding` |
| `ACCOUNT_ID` | Source | `tal.account AS ACCOUNT_ID` |
| `ACCOUNTNUMBER` | Source | `a.acctnumber AS ACCOUNTNUMBER` |
| `NAME` | Source | `a.accountsearchdisplayname AS NAME` |
| `AMOUNT` | Source | `tl.netamount AS AMOUNT` |
| `GROSS_AMOUNT` | Placeholder | `CAST(NULL AS decimal(18, 4)) AS GROSS_AMOUNT` |
| `CostComp` | Derived | `CASE WHEN tl.id = 1 THEN 'OldStdCost' ELSE 'NewStdCost' END AS CostComp` |
| `ITEM_UNIT_PRICE` | Source | `tl.custcol_ccc_ehub_item_price AS ITEM_UNIT_PRICE` |
| `ITEM_ID` | Source | `tl.item AS ITEM_ID` |
| `FULL_NAME` | Source | `i.fullname AS FULL_NAME` |
| `DISPLAYNAME` | Derived | `COALESCE( NULLIF(LTRIM(RTRIM(i.displayname)), ''), NULLIF(LTRIM(RTRIM(i.description)), ''), NULLIF(LTRIM(RTRIM(i.purchasedescription)), '') ) AS DISPLAYNAME` |

### 4.31 `NetSuite2_View_TransactionLinesBasic`

**Purpose:** Provides a broad transaction-line reporting dataset with account, period, department, class, item, customer, quantity, bars, amount, and location.

**Expected grain:** Transaction-line grain, subject to accounting-line join multiplicity.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.TransactionAccountingLine`
- `Source_NetSuite.ns2.Account`
- `Source_NetSuite.ns2.Item`
- `Source_NetSuite.ns2.accountingPeriod`
- `Source_NetSuite.ns2.Location`
- `Source_NetSuite.ns2.department`
- `Source_NetSuite.ns2.classification`
- `Source_NetSuite.ns2.Customer`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `TransactionDate` | Source | `distinct t.trandate AS TransactionDate` |
| `DocumentNumber` | Source | `t.transactionnumber AS DocumentNumber` |
| `AccountingPeriod` | Source | `ap.periodname AS AccountingPeriod` |
| `AccountNumber` | Source | `a.acctnumber AS AccountNumber` |
| `AccountName` | Source | `a.accountsearchdisplaynamecopy AS AccountName` |
| `TransactionType` | Source | `t.recordtype AS TransactionType` |
| `DepartmentName` | Source | `d.fullname AS DepartmentName` |
| `ClassName` | Source | `c.name AS ClassName` |
| `ItemID` | Source | `tl.item AS ItemID` |
| `Item` | Source | `i.fullname AS Item` |
| `ItemDescription` | Derived | `COALESCE( NULLIF(LTRIM(RTRIM(i.displayname)), ''), NULLIF(LTRIM(RTRIM(i.description)), ''), NULLIF(LTRIM(RTRIM(i.purchasedescription)), '') ) AS ItemDescription` |
| `PRODUCT_TYPE_ID` | Source | `tl.cseg_ccc_prod_line AS PRODUCT_TYPE_ID` |
| `PRODUCT_CLASS_ID` | Source | `tl.cseg_product_type AS PRODUCT_CLASS_ID` |
| `CustomerName` | Source | `c2.entityid AS CustomerName` |
| `CreatedFromType` | Source | `t2.recordtype AS CreatedFromType` |
| `Qty` | Source | `tl.quantity AS Qty` |
| `BarCount` | Source | `i.custitem_bars AS BarCount` |
| `Bars` | Derived | `tl.quantity * i.custitem_bars AS Bars` |
| `Amount` | Source | `tl.netamount AS Amount` |
| `Location` | Source | `l.name AS Location` |

### 4.32 `NetSuite2_vw_BarCount`

**Purpose:** Aggregates bars made for assembly builds/unbuilds with account, item, and production-line context.

**Expected grain:** Aggregated at the GROUP BY dimensions defined in the view.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.TransactionAccountingLine`
- `Source_NetSuite.ns2.Account`
- `Source_NetSuite.ns2.item`
- `Source_NetSuite.ns2.accountingPeriod`
- `Source_NetSuite.ns2.CUSTOMLIST_WO_LINE_NO`

**Key filters found in the SQL:**
- `Record type: recordtype IN ('assemblybuild', 'assemblyunbuild')`
- `Date: trandate >= '2026-01-01'`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `Date` | Source | `t.trandate AS [Date]` |
| `DocumentNumber` | Source | `t.tranid AS DocumentNumber` |
| `memo` | Source | `t.memo` |
| `TransactionType` | Source | `t.recordtype AS TransactionType` |
| `CREATE_DATE` | Source | `t.createddate AS CREATE_DATE` |
| `AssemblyItem` | Source | `t.custbody_wo_assembly AS AssemblyItem` |
| `AccountNumber` | Source | `a.acctnumber AS AccountNumber` |
| `BarsMade` | Aggregate | `SUM(ISNULL(tl.quantity, 0) * ISNULL(i.custitem_bars, 0)) AS BarsMade` |
| `AMOUNT` | Source | `tl.netamount AS AMOUNT` |
| `ItemID` | Source | `tl.item AS ItemID` |
| `Item` | Source | `i.fullname AS Item` |
| `ItemDescription` | Derived | `COALESCE(i.displayname, i.description, i.purchasedescription) AS ItemDescription` |
| `BarCount` | Source | `i.custitem_bars AS BarCount` |
| `LineName` | Source | `ln2.name AS LineName` |
| `InventoryNumber` | Placeholder | `CAST(NULL AS nvarchar(255)) AS InventoryNumber` |

### 4.33 `vw_SCA_SalesOrderLines`

**Purpose:** Provides open sales-order line demand and fulfillment allocation quantities at item and location grain.

**Expected grain:** One row per sales-order line.

**Dependencies:**
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.item`
- `Source_NetSuite.ns2.transactionstatus`
- `Source_NetSuite.ns2.Customer`
- `Source_NetSuite.ns2.customerCategory`
- `Source_NetSuite.ns2.Location`

**Key filters found in the SQL:**
- `Record type: recordtype = 'salesorder'`
- `Status: fullname IN ( 'Sales Order : Pending Approval', 'Sales Order : Pending Fulfillment' )`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `SalesOrderTransactionID` | Source | `t.id AS SalesOrderTransactionID` |
| `SalesOrderLineID` | Source | `tl.id AS SalesOrderLineID` |
| `SalesOrderLineKey` | Derived | `CONCAT( CAST(t.id AS varchar(30)), '-', CAST(tl.id AS varchar(30)) ) AS SalesOrderLineKey` |
| `SalesOrderDate` | Source | `t.trandate AS SalesOrderDate` |
| `SalesOrderID` | Source | `t.tranid AS SalesOrderID` |
| `PlannedShipDate` | Source | `t.custbody_bb_planned_ship_date AS PlannedShipDate` |
| `MABD` | Source | `t.custbodymabd_date AS MABD` |
| `StatusID` | Source | `t.status AS StatusID` |
| `SalesOrderStatus` | Source | `ts.fullname AS SalesOrderStatus` |
| `CustomerID` | Source | `c.id AS CustomerID` |
| `CustomerName` | Source | `c.fullname AS CustomerName` |
| `CustomerEntityID` | Source | `c.entityid AS CustomerEntityID` |
| `CustomerCategory` | Source | `cc.name AS CustomerCategory` |
| `ItemID` | Source | `tl.item AS ItemID` |
| `ItemFullName` | Source | `i.fullname AS ItemFullName` |
| `ItemDescription` | Derived | `COALESCE( i.displayname, i.description, i.purchasedescription ) AS ItemDescription` |
| `LocationID` | Source | `tl.location AS LocationID` |
| `LocationName` | Source | `l.fullname AS LocationName` |
| `QuantityOrdered` | Derived | `ABS(COALESCE(tl.quantity, 0)) AS QuantityOrdered` |
| `QuantityCommitted` | Derived | `ABS(COALESCE(tl.quantitycommitted, 0)) AS QuantityCommitted` |
| `QuantityAllocated` | Derived | `ABS(COALESCE(tl.quantityallocated, 0)) AS QuantityAllocated` |
| `QuantityDemandAllocated` | Derived | `ABS(COALESCE(tl.quantitydemandallocated, 0)) AS QuantityDemandAllocated` |
| `NetSuiteBackorderedQty` | Derived | `ABS(COALESCE(tl.quantitybackordered, 0)) AS NetSuiteBackorderedQty` |
| `QuantityPicked` | Derived | `ABS(COALESCE(tl.quantitypicked, 0)) AS QuantityPicked` |
| `QuantityPacked` | Derived | `ABS(COALESCE(tl.quantitypacked, 0)) AS QuantityPacked` |
| `IsClosed` | Source | `tl.isclosed AS IsClosed` |
| `LineAmount` | Source | `tl.netamount AS LineAmount` |

### 4.34 `vw_SCA_TransferSupply`

**Purpose:** Pairs transfer-order source and destination lines and classifies candidate inbound supply by approval/operational status.

**Expected grain:** One row per transfer transaction, item, source location, and destination location pairing.

**Dependencies:**
- `Source_NetSuite.ns2.transactionstatus`
- `Source_NetSuite.ns2.transaction`
- `Source_NetSuite.ns2.transactionLine`
- `Source_NetSuite.ns2.item`
- `Source_NetSuite.ns2.Location`

**Key filters found in the SQL:**
- `Record type: recordtype IN ( 'transfer', 'transferorder' )`
- `Status: fullname IN ( 'Transfer Order : Pending Fulfillment', 'Transfer Order : Pending Receipt' )`
- `Status: fullname IN ( 'Transfer Order : Closed', 'Transfer Order : Pending Approval', 'Transfer Order : Pending Fulfillment', 'Transfer Order : Pending Receipt', 'Transfer Order : Received', 'Transfer Order : Rejected' )`

**Output columns:**

| Column | Type | Definition / lineage |
|---|---|---|
| `TransferTransactionID` | Source | `destination.TransferTransactionID` |
| `TransferSupplyKey` | Source | `CONCAT ( CAST( destination.TransferTransactionID AS varchar(30) ), '-', CAST( destination.ItemID AS varchar(30) ), '-', COALESCE ( CAST( source.FromLocationID AS varchar(30) ), 'UNKNOWN' ), '-', CAST( destination.ToLocationID AS varchar(30) ) ) AS TransferSupplyKey` |
| `TransferOrderID` | Source | `destination.TransferOrderID` |
| `TransferOrderDate` | Source | `destination.TransferOrderDate` |
| `TransferStatusID` | Source | `destination.TransferStatusID` |
| `TransferStatus` | Source | `destination.TransferStatus` |
| `TransferStatusGroup` | Source | `destination.TransferStatusGroup` |
| `ItemID` | Source | `destination.ItemID` |
| `ItemFullName` | Source | `item.fullname AS ItemFullName` |
| `FromLocationID` | Source | `source.FromLocationID` |
| `FromLocationName` | Source | `fromlocation.fullname AS FromLocationName` |
| `ToLocationID` | Source | `destination.ToLocationID` |
| `ToLocationName` | Source | `tolocation.fullname AS ToLocationName` |
| `OutboundTransferQty` | Derived | `COALESCE( source.OutboundTransferQty, 0 ) AS OutboundTransferQty` |
| `ExpectedInboundTransferQty` | Source | `destination.ExpectedInboundTransferQty` |
| `CandidateTransferSupplyQty` | Derived | `CASE WHEN destination.TransferStatus IN ( 'Transfer Order : Pending Fulfillment', 'Transfer Order : Pending Receipt' ) THEN destination.ExpectedInboundTransferQty ELSE 0 END AS CandidateTransferSupplyQty` |
| `PendingApprovalTransferQty` | Derived | `CASE WHEN destination.TransferStatus = 'Transfer Order : Pending Approval' THEN destination.ExpectedInboundTransferQty ELSE 0 END AS PendingApprovalTransferQty` |
| `ExpectedReceiptDate` | Placeholder | `CAST(NULL AS date) AS ExpectedReceiptDate` |
| `SourceLineCount` | Source | `source.SourceLineCount` |
| `DestinationLineCount` | Source | `destination.DestinationLineCount` |
| `TransferValidationStatus` | Derived | `CASE WHEN source.FromLocationID IS NULL THEN 'Missing source location' WHEN ABS ( COALESCE( source.OutboundTransferQty, 0 ) - destination.ExpectedInboundTransferQty ) > 0.0001 THEN 'Source and destination quantities differ' WHEN destination.TransferStatus = 'Transfer Order : Pending Approval' THEN 'Valid pair, awaiting approval' WHEN destination.TransferStatus IN ( 'Transfer Order : Received', 'Transfer Order : Closed', 'Transfer Order : Rejected' ) THEN 'Valid pair, not open supply' ELSE 'Valid open transfer pair' END AS TransferValidationStatus` |

## 5. Validation and maintenance observations

The following are code-review observations based solely on the SQL definition. They should be validated against NetSuite2 source behavior and expected row counts before changes are made.

- **`NetSuite2_View_ItemsAll`:** The itemSubCat CASE repeats account 121010 for both Ingredients and Packaging. The Packaging branch is therefore unreachable as written.
- **`NetSuite2_View_Batchyield`:** The Account join uses tl.id = a.id rather than an accounting-line/account key. This may associate unrelated accounts and should be validated.
- **`NetSuite2_View_StdCostRevaluation`:** The record-type filter uses 'Inventory Cost Revaluation', while other migrated views use lowercase internal IDs such as 'inventorycostrevaluation'. Validate the exact ns2 recordtype value.
- **`NetSuite2_View_TransactionsJoin`:** NetSuite2_View_Transaction_Lines already joins TransactionAccountingLine; joining TransactionAccountingLine again can multiply rows if more than one accounting row exists per transaction line.
- **`NetSuite2_View_AssembliesLotCode`:** TransactionBinNumbers is joined but no selected field uses it. If multiple bin rows exist, the join can multiply rows before grouping.
- **`NetSuite2_View_LotTrace`:** Joining both InventoryAssignment and TransactionBinNumbers at transaction-line grain can create a many-to-many multiplication when multiple lot and bin rows exist.
- **`NetSuite2_View_StandardCostBarsShipped`:** The view is fixed to PeriodEnding = 2024-07-31, so it behaves like a period-specific snapshot rather than a reusable ongoing view.
- **`NetSuite2_View_BarsProdSummary`:** The view is fixed to 2024-01-01 through 2024-02-29.
- **`NetSuite2_View_LotTrace`:** The inventory-number WHERE clause is limited to three hard-coded lot numbers.
- **`NetSuite2_View_LotTrace_Option2`:** The inventory-number WHERE clause is limited to three hard-coded lot numbers.
- **`NetSuite2_View_FutureOrderSupplyVisibility`:** The SQL comments state assumptions about transfer location mapping and the work-order assembly item key. These mappings require business validation.
- **`vw_SCA_TransferSupply`:** ExpectedReceiptDate is intentionally returned as NULL until the actual source field is confirmed.

## 6. Recommended validation checklist

1. Confirm each view’s intended row grain with duplicate-key checks.
2. Compare aggregate quantities and amounts to the underlying NetSuite2 tables for a controlled date range.
3. Test joins to `TransactionAccountingLine`, `InventoryAssignment`, and `TransactionBinNumbers` for row multiplication.
4. Review all hard-coded dates, statuses, accounts, customers, locations, and lot numbers.
5. Validate all columns typed as **Placeholder**; these intentionally return NULL and may represent unmapped legacy fields.
6. Confirm internal NetSuite2 record-type and status values rather than display labels.
7. For supply visibility, validate item/location mapping and ensure candidate supply is not interpreted as confirmed availability.

## 7. Column classification legend

- **Source:** direct source field or simple rename.
- **Derived:** CASE, COALESCE, arithmetic, concatenation, absolute value, or other transformation.
- **Aggregate:** SUM, MAX, MIN, COUNT, or STRING_AGG.
- **Placeholder:** explicit NULL cast retained for compatibility or future mapping.
