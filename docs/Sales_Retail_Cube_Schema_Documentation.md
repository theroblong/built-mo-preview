# Sales & Retail Cube Schema Documentation

Source: Sales and Retail Cube Schema.sql

## Executive Summary

The Built_EDW Sales and Retail Cube architecture follows a dimensional star-schema design centered around FactTransactions. The solution contains three schema layers:

- NetSuite2 (Core Enterprise Warehouse)
- NetSuite2_Sales (Sales analytical model)
- NetSuite2_Retail (Retail / OTIF analytical model)

## Core Architecture

### Central Fact Table

#### NetSuite2.FactTransactions
Primary transactional fact table containing financial, sales, shipment, allocation, fulfillment, and OTIF-related measures.

Key Measures:
- Amount
- NetAmount
- SalesAmount
- ShippedAmount
- ItemCount
- Bars
- BarsSold
- BarsShipped
- QuantityAllocated
- QuantityCommitted
- QuantityPacked
- QuantityPicked

Key Foreign Keys:
- DimAccountingPeriodId
- DimChartOfAccountsId
- DimItemId
- DimDepartmentId
- DimCustomerId
- DimLocationId
- DimSalesChannelId
- DimSalesRepId
- DimTransactionTypeId
- DimTransactionStatusId
- DimComplianceFlagsId
- DimShippingMethodId
- DimShippingRegionId
- DimDeviationReasonId
- DimTransitDaysId

## Dimension Tables

### DimAccountingPeriod
| Column | Description |
|----------|----------|
| DimAccountingPeriodId | Surrogate Key |
| Id | NetSuite Period ID |
| StartDate | Period Start Date |
| EndDate | Period End Date |
| PeriodName | Accounting Period Name |

### DimChartOfAccounts
| Column | Description |
|----------|----------|
| DimChartOfAccountsId | Surrogate Key |
| Id | NetSuite Account ID |
| Parent | Parent Account |
| AccountNumber | GL Account Number |
| ExternalId | External Identifier |
| FullName | Full Account Name |
| Name | Account Name |
| AccountType | Income Statement / Balance Sheet Category |

### DimCustomer
| Column | Description |
|----------|----------|
| DimCustomerId | Surrogate Key |
| Country | Customer Country |
| State | Customer State |
| City | Customer City |
| CustomerType | Customer Classification |

Retail extension adds:
- CustomerId
- CompanyName
- Name
- FullName
- DeliveryTypeName
- LeadTime

### DimItem
| Column | Description |
|----------|----------|
| DimItemId | Surrogate Key |
| Id | Item ID |
| DisplayName | Display Name |
| PurchaseDescription | Purchase Description |
| CostCategory | Cost Bucket |
| CostEstimateType | Cost Estimation Method |
| FullName | Full Item Name |
| Bars | Bars Per Case |
| ItemType | Item Type |
| Flavor | Flavor |
| FullNameDisplayName | Calculated Combined Display Field |

### DimDepartment
- DimDepartmentId
- Id
- ExternalId
- Name
- FullName

### DimLocation
- DimLocationId
- Id
- Name

### DimProductType
- DimProductTypeId
- Id
- Name

### DimProductClass
- DimProductClassId
- Id
- Name

### DimSalesChannel
- DimSalesChannelId
- Id
- FullName
- Name

### DimSalesRep
- DimSalesRepId
- Id
- FullName
- FirstName
- LastName
- Email
- Title

### DimTransactionType
- DimTransactionTypeId
- Name
- Type

### DimTransactionStatus
- DimTransactionStatusId
- Id
- Name
- FullName
- TranType

### DimTransactionEntryType
- DimTransactionEntryTypeId
- Name

### DimCreatedFromTransactionType
- DimCreatedFromTransactionTypeId
- CreatedFromTransactionType

## Retail-Specific Dimensions

### DimComplianceFlags
| Column | Description |
|----------|----------|
| MABDCalculatedFlag | MABD Logic Applied |
| ChangeCommunicatedFlag | Delivery Change Communicated |
| WasOnTimeFlag | OTIF On-Time Indicator |
| WasInFullFlag | OTIF In-Full Indicator |
| MABDCalculatedDesc | Label |
| ChangeCommunicatedDesc | Label |
| WasOnTimeDesc | Label |
| WasInFullDesc | Label |

### DimDeviationReason
- Id
- Name

### DimChangeType
- Id
- Name

### DimShippingMethod
- Id
- Name

### DimShippingRegion
- Id
- Name

### DimTransitDays
- TransitDays
- SortOrder

## Role Playing Date Dimensions

The cube exposes multiple views over Corp.DimDate:

- vDimTranDate
- vDimShipDate
- vDimActualShipDate
- vDimActualDeliveryDate
- vDimRequestedDeliveryDate
- vDimPlannedDeliveryDate
- vDimPlannedShipByDate
- vDimShipByDate
- vDimPurchaseOrderDate
- vDimMustArriveByDate
- vDimCancelDate

Common columns:
- DateKey
- Date
- Day
- WeekOfYear
- Month
- MonthName
- Quarter
- QuarterName
- Year
- YearNumber
- IsWeekend
- IsHoliday

## Subject Area Models

### NetSuite2_Sales
Purpose:
- Revenue Reporting
- Customer Analytics
- Product Mix Analysis
- Sales Channel Reporting
- Financial Reporting

### NetSuite2_Retail
Purpose:
- OTIF Reporting
- MABD Analysis
- Customer Compliance
- Shipment Performance
- Requested vs Actual Delivery Analysis

## Star Schema Relationship

FactTransactions
├── DimAccountingPeriod
├── DimChartOfAccounts
├── DimItem
├── DimDepartment
├── DimCustomer
├── DimSalesChannel
├── DimSalesRep
├── DimLocation
├── DimTransactionType
├── DimTransactionStatus
├── DimProductType
├── DimProductClass
├── DimComplianceFlags
├── DimShippingMethod
├── DimShippingRegion
├── DimDeviationReason
├── DimChangeType
└── DimTransitDays

## Supporting Tables

### TrialBalance
Stores summarized general-ledger balances by period, department, class, and account.

### ETL_ProcedureLog
Stores ETL audit history, runtime metrics, inserted rows, deleted rows, exceptions, and execution diagnostics.
