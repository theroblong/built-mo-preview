# Source_NetSuite ns2 Schema Architecture & Data Dictionary

**Server:** `bb-db`  
**Database:** `Source_NetSuite`  
**Scope:** `ns2` only  
**Source:** `Schema.sql`  
**Purpose:** BI modeling, migration planning, validation, and source-system discovery

---

## 1. Executive Summary

The `Source_NetSuite` database on `bb-db` contains a substantial `ns2` schema supporting transaction, item, inventory, customer, accounting, reference-data, and ETL processes. The supplied schema defines **57 ns2 tables**, **3,089 documented columns**, **24 stored procedures**, **6 primary-key constraints**, and **19 indexes**.

No explicit `ns2`-to-`ns2` foreign-key constraints were found. The relationship candidates documented in the source reference are naming-based hypotheses and must be validated for key uniqueness, cardinality, nulls, and unmatched records before they are used in SQL joins, Power BI relationships, migration logic, or KPI reporting.

| Component | Count |
|---|---:|
| Tables | 57 |
| Views | 0 |
| Stored procedures | 24 |
| Functions | 0 |
| Primary-key constraints | 6 |
| Foreign-key constraints | 0 |
| Indexes | 19 |
| Documented columns | 3,089 |

> **Leadership takeaway:** The export provides a reliable structural inventory, but it does not by itself prove business grain or table relationships. Relationship validation and reconciliation to accepted NetSuite outputs should precede production reporting or migration decisions.

## 2. How to Use This Document

1. Start with the object inventory to understand the `ns2` footprint.
2. Use the subject-area map to locate tables relevant to a business process.
3. Use the table data dictionary in the original detailed reference to verify column names, data types, nullability, identity behavior, and defaults.
4. Use the keys and indexes section to identify uniqueness and performance-supporting access paths.
5. Use explicit relationships first. Treat inferred join candidates as hypotheses requiring data validation.
6. Use the dependency catalog to understand which `ns2` objects are referenced by procedures.

## 3. ns2 Object Inventory

### Tables

1. Account
2. AddressBook
3. BomRevisionComponent
4. CUSTOMLIST2137
5. CUSTOMLIST_WO_LINE_NO
6. CUSTOMRECORD_CSEG_BB_SALES_CHANN
7. CUSTOMRECORD_CSEG_CCC_PROD_LINE
8. CUSTOMRECORD_CSEG_PRODUCT_TYPE
9. Customer
10. Customer_09092026
11. Customer_NewCol_05282026
12. FiscalCalendar
13. InventoryAssignment
14. InventoryItemLocations
15. InventoryNumberInventoryBalance
16. InventoryNumberLocation
17. Location
18. LocationMainAddress
19. SystemNote
20. TransactionAccountingLine
21. TransactionAccountingLineCostComponent
22. TransactionBinNumbers
23. accountingPeriod
24. bininventorybalance
25. bom
26. bomRevision
27. classification
28. costCategory
29. customerAddressbook
30. customerCategory
31. customeraddressbookentityaddress
32. customlist2398
33. customlist2401
34. customlist_bb_change_type
35. customlist_bb_shipping_region
36. customlist_revenue_recognition
37. department
38. etl_upsert_log
39. inventoryNumber
40. item
41. itemGroupMember
42. itemMember
43. itemVendor
44. itemtype
45. oa_columns
46. oa_tables
47. shipitem
48. transaction
49. transactionLine
50. transactionName
51. transactionShippingAddress
52. transaction_addcolumns_03162026
53. transaction_newcols_05262026
54. transaction_schemaonly_03112026
55. transaction_serv_carr_09102026
56. transaction_shippingaddress_09142026
57. transactionstatus

### Views

None found in the supplied script.

### Stored Procedures

1. proc_FreqUpdate_transaction
2. proc_FreqUpdate_transactionLine
3. proc_Load_NetSuite2_Account
4. proc_Load_NetSuite2_BomRevisionComponent
5. proc_Load_NetSuite2_CUSTOMLIST_WO_LINE_NO
6. proc_Load_NetSuite2_CUSTOMRECORD_CSEG_CCC_PROD_LINE
7. proc_Load_NetSuite2_CUSTOMRECORD_CSEG_PRODUCT_TYPE
8. proc_Load_NetSuite2_Customer
9. proc_Load_NetSuite2_InventoryAssignment
10. proc_Load_NetSuite2_Location
11. proc_Load_NetSuite2_TransactionAccountingLine
12. proc_Load_NetSuite2_TransactionAccountingLineCostComponent
13. proc_Load_NetSuite2_bom
14. proc_Load_NetSuite2_bomRevision
15. proc_Load_NetSuite2_classification
16. proc_Load_NetSuite2_customerCategory
17. proc_Load_NetSuite2_department
18. proc_Load_NetSuite2_inventoryNumber
19. proc_Load_NetSuite2_itemGroupMember
20. proc_Load_NetSuite2_transaction
21. proc_Load_NetSuite2_transactionLine
22. proc_Load_transactionShippingAddress
23. proc_NetSuite2_ProcessDeletes_transaction
24. proc_ProcessDeletes_transactionLine

### Functions

None found in the supplied script.

## 4. Suggested Business Subject Areas

> The following grouping is a naming-based organizational suggestion, not metadata declared by SQL Server.

### Customers & Parties

`AddressBook`, `Customer`, `Customer_09092026`, `Customer_NewCol_05282026`, `customerAddressbook`, `customerCategory`, `customeraddressbookentityaddress`

### ETL & Audit

`etl_upsert_log`

### Finance & Accounting

`Account`, `FiscalCalendar`, `accountingPeriod`, `costCategory`

### Inventory & Fulfillment

`InventoryAssignment`, `InventoryNumberInventoryBalance`, `InventoryNumberLocation`, `Location`, `LocationMainAddress`, `bininventorybalance`, `inventoryNumber`

### Items, BOM & Manufacturing

`BomRevisionComponent`, `InventoryItemLocations`, `bom`, `bomRevision`, `item`, `itemGroupMember`, `itemMember`, `itemVendor`, `itemtype`

### Other / General

`SystemNote`, `oa_columns`, `oa_tables`

### Reference & Classification

`CUSTOMLIST2137`, `CUSTOMLIST_WO_LINE_NO`, `CUSTOMRECORD_CSEG_BB_SALES_CHANN`, `CUSTOMRECORD_CSEG_CCC_PROD_LINE`, `CUSTOMRECORD_CSEG_PRODUCT_TYPE`, `classification`, `customlist2398`, `customlist2401`, `customlist_bb_change_type`, `customlist_revenue_recognition`, `department`

### Transactions & Orders

`TransactionAccountingLine`, `TransactionAccountingLineCostComponent`, `TransactionBinNumbers`, `customlist_bb_shipping_region`, `shipitem`, `transaction`, `transactionLine`, `transactionName`, `transactionShippingAddress`, `transaction_addcolumns_03162026`, `transaction_newcols_05262026`, `transaction_schemaonly_03112026`, `transaction_serv_carr_09102026`, `transaction_shippingaddress_09142026`, `transactionstatus`

## 5. Relationship Map

### Explicit Foreign Keys

No explicit `ns2`-to-`ns2` foreign-key constraints were found in the supplied schema script.

### Inferred Join Candidates

Inferred joins are not enforced relationships. Before use, validate:

- Parent-key uniqueness
- Child-key null rate
- Matched and unmatched key counts
- One-to-many versus many-to-many behavior
- Grain alignment between parent and child tables
- Reconciliation to accepted NetSuite outputs

Common high-value relationship areas to test include:

| Child / Detail | Candidate Link | Parent / Header |
|---|---|---|
| transactionLine | `transaction` | transaction.`id` |
| TransactionAccountingLine | `transaction`, `transactionline` | transaction / transactionLine |
| TransactionAccountingLineCostComponent | transaction-related identifiers | TransactionAccountingLine |
| TransactionBinNumbers | `transactionid`, `transactionline` | transaction / transactionLine |
| InventoryAssignment | transaction and line identifiers | transaction / transactionLine |
| transactionShippingAddress | `recordowner` | transaction shipping-address reference |
| BomRevisionComponent | `bomrevision`, `item` | bomRevision / item |
| InventoryItemLocations | item and location identifiers | item / Location |
| Inventory-number balance tables | inventory number, item, and location identifiers | inventoryNumber / item / Location |

## 6. Keys and Indexes

### Declared Primary Keys

| Table | Constraint | Column(s) |
|---|---|---|
| etl_upsert_log | PK_etl_upsert_log | etl_upsert_log_id |
| InventoryAssignment | PK_ns2_InventoryAssignment | id |
| transaction | PK_transaction_id | id |
| TransactionAccountingLine | PK_ns2_TransactionAccountingLine | transaction, transactionline |
| transactionLine | PK_transactionLine_transaction_id | transaction, id |
| transactionShippingAddress | PK_transactionShippingAddress | recordowner |

### Index Summary

The source script documents **19 indexes**. Important indexed access paths include transaction dates and IDs, transaction numbers, transaction types, transaction-line composite keys, item identifiers, accounting-line transaction keys, bin-number transaction/line keys, and shipping-address keys.

## 7. Dependency Catalog Summary

The procedure inventory shows a repeated ETL pattern:

- Frequency-update procedures trigger transaction and transaction-line loads.
- Load procedures insert, update, or merge data into individual `ns2` target tables.
- Several load procedures write to `etl_upsert_log`.
- Delete-processing procedures remove or reconcile dependent transaction records across transaction detail, accounting, inventory-assignment, cost-component, and bin-number tables.
- Dynamic SQL or runtime-constructed references may not be detectable from static schema text.

## 8. Recommended Validation Workflow

| Step | Validation action |
|---|---|
| Grain | Write one sentence defining the row grain of each high-value table. |
| Key quality | Test duplicate counts for each declared or candidate key. |
| Relationship coverage | Calculate matched, unmatched, and null foreign-key rates for every intended join. |
| Cardinality | Confirm one-to-many versus many-to-many behavior before creating Power BI relationships. |
| Date coverage | Profile minimum and maximum dates and missing periods for transaction-oriented tables. |
| Data volume | Capture row counts and change rates to inform refresh and incremental-load design. |
| Business logic | Prefer validated views or procedures when they encode approved transformations; document replacement logic. |
| Reconciliation | Tie totals back to NetSuite reports or accepted SQL outputs before publishing KPIs. |

## 9. Reusable SQL Validation Patterns

### Row count

```sql
SELECT COUNT_BIG(*) AS RowCount
FROM [ns2].[TableName];
```

### Duplicate key

```sql
SELECT [KeyColumn], COUNT(*) AS Cnt
FROM [ns2].[TableName]
GROUP BY [KeyColumn]
HAVING COUNT(*) > 1;
```

### Null key rate

```sql
SELECT
    COUNT_BIG(*) AS TotalRows,
    SUM(CASE WHEN [KeyColumn] IS NULL THEN 1 ELSE 0 END) AS NullKeys
FROM [ns2].[TableName];
```

### Unmatched join

```sql
SELECT COUNT_BIG(*) AS UnmatchedRows
FROM [ns2].[Child] AS c
LEFT JOIN [ns2].[Parent] AS p
    ON c.[ParentId] = p.[Id]
WHERE c.[ParentId] IS NOT NULL
  AND p.[Id] IS NULL;
```

### Candidate-key uniqueness

```sql
SELECT
    COUNT_BIG(*) AS TotalRows,
    COUNT_BIG(DISTINCT [CandidateKey]) AS DistinctKeys,
    COUNT_BIG(*) - COUNT_BIG(DISTINCT [CandidateKey]) AS DuplicateRows
FROM [ns2].[TableName];
```

### Join coverage

```sql
SELECT
    COUNT_BIG(*) AS ChildRows,
    SUM(CASE WHEN c.[ParentId] IS NULL THEN 1 ELSE 0 END) AS NullChildKeys,
    SUM(CASE WHEN c.[ParentId] IS NOT NULL AND p.[Id] IS NULL THEN 1 ELSE 0 END) AS UnmatchedRows,
    SUM(CASE WHEN p.[Id] IS NOT NULL THEN 1 ELSE 0 END) AS MatchedRows
FROM [ns2].[Child] AS c
LEFT JOIN [ns2].[Parent] AS p
    ON c.[ParentId] = p.[Id];
```

## Appendix A. Data Dictionary Scope

The complete source documentation contains the detailed table-level data dictionary for all **57 tables** and **3,089 columns**, including column order, data type, nullability, default, and available key or identity flags.

Because the full column dictionary is exceptionally large, this Markdown edition preserves the architecture, inventory, subject areas, key structures, relationship cautions, dependency summary, validation workflow, and reusable SQL patterns in a portable and readable format. The original DOCX remains the authoritative detailed column-by-column reference.

---

## Documentation Notes

- Scope intentionally excludes `dbo` and other schemas.
- Object and column details originate from the supplied `Schema.sql` export.
- Subject-area groupings and inferred relationships are analytical aids, not enforced SQL Server metadata.
- Every inferred relationship should be validated before production use.
