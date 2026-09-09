# Aevah — Client Internal Data Request

**Date:** September 9, 2026  
**Purpose:** Fill the internal-data gaps in the seven agreed Aevah experiences alongside the client's SPINS export.  
**Status:** Proposed request specification. Client application names, tables, named owners, and availability have not yet been confirmed.

## Scope and principles

Request a shared foundation once, then request the additional records needed by each numbered experience. Do not turn these into seven unrestricted departmental implementations.

SPINS retail dollars are consumer purchases at the register, not the manufacturer's gross or net revenue [1]. The existing source-to-KPI mapping also distinguishes reported retail metrics, calculations, modeled outputs, and additional business inputs. Forecasts, elasticity, and cannibalization are outputs Aevah must estimate unless the client already has suitable versioned models; they are not presumed missing source columns.

Use client-approved warehouse tables first when their lineage, business definitions, and reconciliation are established. Otherwise request the relevant operational exports. The application categories below describe where to look; they do not assert which software the client owns.

IT/Data should coordinate extraction. The relevant business owner should approve definitions, mappings, and control totals. Business facts used by a model are not automatically appropriate for every role's screen or conversational access.

## The seven packages remain unchanged

| # | Experience | Core internal inputs | Conditional additions |
|---|---|---|---|
| 1 | Customer Sales & Outlook | Product/customer mappings, invoice and financial-adjustment records, wholesale prices, approved sales forecast, distribution records | Retailer/distributor inventory and downstream sales to improve sell-through-to-shipment modeling |
| 2 | Production Demand Outlook | Product/bar mappings, forecast scope and calendar; order/shipment history and existing demand plans for business alignment | Finished-goods inventory, scheduled receipts, and stock policies only for a production-requirement extension |
| 3 | Procurement Demand Outlook | The same approved SKU bar forecast as #2, purchasing horizons, relevant forecast versions | Effective BOM/formulas, material inventory, supplier terms, and purchase commitments only for material/purchase calculations |
| 4 | Financial Forecast & CapEx Scenarios | Revenue/price inputs, financial plan versions, pricing/portfolio assumptions, capacity inputs and capital-project assumptions | Cost and cash-flow detail according to the financial outputs selected |
| 5 | Customer Trade Expense Outlook | Trade agreements, eligible sales/volume, future commitments, historical expense and prior expense forecasts | Open accruals and claims for validation/reconciliation, not posting functionality |
| 6 | Competitive & Promotional Analysis | Owned-product/competitive definitions, historical promotion and price events, distribution/availability, prior tests | Attributable manufacturer costs and spend for economic ROI |
| 7 | Item, Portfolio & Launch Strategy | Launch/retirement calendar, item relationships, rollout plans, launch expectations, marketing and price events | Comparable-launch studies and approved product economics |

## Priority definitions

- **Foundation:** Needed to identify, align, and interpret data across packages.
- **Core:** Needed to fulfill the relevant original package or a named KPI in it.
- **Supporting:** Improves validation, coverage, explanation, or planning quality.
- **Extension:** Request only when enabling additional operational calculations; it should not block a forecast-only release of #2 or #3.

# Shared foundation

## R01 — Product, UPC, packaging, and component master

**Priority:** Foundation. **Packages:** All, especially #2/#3.  
**Business owner:** Master Data or Product Operations, with Manufacturing validating physical conversions.  
**Where to look:** ERP item master, product-information system, product-lifecycle records, packaging specifications, approved warehouse dimensions.

**Request:** Retail UPC/GTIN as text; sellable internal SKU; manufacturing/component SKU where different; owned-brand flag; product family; flavor; format; bar versus non-bar classification; base unit; bars per sellable package; sellable packages per case; case/pallet hierarchy where needed; variety-pack component quantities; predecessor/successor relationships; active/discontinued status; effective-from/to dates and record version.

**Grain:** One effective-dated product record plus one row per parent/component relationship. Do not flatten a variety pack to a single flavor. Packaging levels may have distinct GTINs, so request the hierarchy, not just one barcode per product [2].

**Acceptance:** Every in-scope owned UPC either maps to an approved SKU/component conversion or appears in an unresolved queue. Preserve unmatched records; do not silently drop them. A bar-only product scope must not include non-bar products simply because they share a SPINS category.

## R02 — Customer, channel, and partner crosswalk

**Priority:** Foundation. **Packages:** #1/#4/#5, with controlled modeling use elsewhere.  
**Business owner:** Sales Operations and Master Data.  
**Where to look:** ERP customer master, CRM account hierarchy, distributor records, retailer onboarding files, approved warehouse dimensions.

**Request:** Legal customer ID; sold-to, bill-to and ship-to IDs; parent account; retailer/banner; distributor relationship; channel; geography; retailer/DC/store identifier type; SPINS account and geography mapping where valid; mapping basis and effective dates; source identifier.

**Grain:** Account/location and effective-dated relationships; allow one-to-many relationships where the business actually has them.

**Acceptance:** Distinguish a direct retailer customer from a distributor serving multiple retailers. Do not allocate a distributor's revenue across retailers without a supporting downstream sales feed or an explicitly approved allocation. Do not map a competitive-market geography into a retailer-only sales fact.

## R03 — Fiscal calendar, metric definitions, and reporting controls

**Priority:** Foundation. **Packages:** All.  
**Business owner:** Controller/FP&A and BI, with role owners confirming planning horizons.  
**Where to look:** Finance calendar, approved management reports, chart-of-accounts mapping, data dictionary, reporting policies.

**Request:** Date-to-fiscal-week/month/quarter mapping; retail-week alignment; closed-period status; reporting currency; exchange-rate source and dates when relevant; current gross-sales/net-sales/trade-expense definitions; account classifications; sign conventions; exclusion and allocation rules; approved product/customer scope; demand basis; forecast horizon and refresh cadence by role.

**Acceptance:** Written agreement on what "customer," "bar," "gross sales," "net sales," "trade expense," and "forecast bars sold" mean. Preserve retail consumption, orders, shipments, production requirements, budgets, and scenarios as distinct measures.

# 1. Customer Sales & Outlook

## R04 — Posted invoices, credits, financial adjustments, and revenue controls

**Priority:** Core. **Packages:** #1/#4; eligibility and reconciliation support for #5.  
**Business owner:** Controller, Revenue Accounting, Accounts Receivable.  
**Where to look:** ERP order-to-cash and financial subledger; posted revenue/contra-revenue entries; certified finance warehouse.

**Request:** Legal entity; invoice/document ID and line ID; linked order/shipment IDs where available; customer, bill-to, ship-to, SKU; invoice, shipment and posting dates; fiscal period; invoiced quantity and unit; manufacturer price; gross invoiced amount; on-invoice discounts; credits/returns; posted net amount where available; separate off-invoice adjustments and true-ups; adjustment type/reason; original-document links; ledger account; status; currency; updated timestamp and reversal link.

**Grain:** Native posted document line and native adjustment grain. Preserve customer-period adjustments at that grain when no SKU allocation exists. Request the Controller's allocation rule separately rather than inventing SKU detail.

**Request control totals:** Approved gross/net sales by fiscal month and customer where available, plus the related ledger totals and known reconciliation exclusions. Invoice-level net amounts alone must not be assumed to include all off-invoice revenue adjustments.

**Unlocks:** Actual manufacturer gross/net sales, customer growth, gross-to-net bridge, historical realized manufacturer price, finance baseline.

## R05 — Orders, shipments, uncovered channels, and downstream demand bridge

**Priority:** Core for company-wide shipment/revenue forecasting; supporting for a clearly labeled SPINS-covered retail-demand forecast.  
**Packages:** #1/#2/#3/#4/#5.  
**Business owner:** Sales Operations, Customer Service, Demand Planning, Supply Chain.  
**Where to look:** ERP sales orders and fulfillment; warehouse/3PL shipment feeds; client-held distributor/retailer feeds; direct-to-consumer and marketplace order systems.

**Request:** Order and line IDs; linked shipment IDs; SKU/customer/channel/location; order date; requested/confirmed/actual ship and arrival dates; ordered, shipped, canceled and backordered quantities; units; document status; cancellation/short-shipment reason; return quantities; update timestamps. Include relevant non-SPINS channels. Where available, request retailer/distributor inventory, downstream sell-through, replenishment policy, initial pipeline-fill and distribution-change records.

**Grain:** Order line, shipment line, and partner SKU-location-period snapshots as separate facts.

**Acceptance:** Record which demand is SPINS retail consumption and which is manufacturer shipment demand. Do not add SPINS retail units to shipments of the same goods. Retain order-to-shipment-to-invoice links so multiple records of one transaction do not become multiple sales.

**Unlocks:** Retail-to-shipment timing, company coverage, supply-constrained sales interpretation, future customer gross/net sales inputs.

## R06 — Manufacturer price agreements and approved future price changes

**Priority:** Core for forecast gross/net sales and manufacturer price scenarios.  
**Packages:** #1/#4/#5; supporting for #7.  
**Business owner:** Sales Operations, Pricing/Revenue Growth Management, Finance.  
**Where to look:** ERP pricing tables, signed customer agreements, approved price lists, pricing-planning records.

**Request:** Customer/SKU; manufacturer list and contracted prices; currency; price unit; customer exceptions; off-invoice price treatment; effective dates; approved future changes; approval date/status; expected retailer pass-through assumption and its owner when used in a retail-price scenario.

**Acceptance:** Keep manufacturer prices, suggested retail prices, planned checkout prices, and observed SPINS checkout prices separate.

## R07 — Distribution, store authorization, and retail availability

**Priority:** Core for exact customer/brand store coverage beyond the export's source grain; supporting for demand and causal models.  
**Packages:** #1/#2/#4/#6/#7.  
**Business owner:** Sales Operations, Key Account teams, BI/Category Insights.  
**Where to look:** Client-held retailer portal extracts, retailer feeds in the warehouse, distribution plans, assortment/authorization trackers.

**Request:** Retailer, store ID or verified account-level coverage count, UPC/SKU, week/date, authorization status, planned/actual on-shelf dates, observed selling status, distribution starts/stops, authorized/selling/planned store counts with definitions, shelf availability or out-of-stock flags, and inventory where licensed and available.

**Grain:** Prefer UPC × retailer × store × week for deduplication and analysis. Preserve source-provided rollups where row-level store data is unavailable.

**Acceptance:** Distinguish authorized stores, planned stores, stores with sales, and the reporting-universe denominator. Preserve missing versus zero versus not-authorized states. Exact brand-wide unique-store counts need store-level identities or a certified provider rollup.

# 2. Production Demand Outlook

## R08 — Existing forecast versions, approved plans, and overrides

**Priority:** Supporting to start a new statistical forecast; core for comparison with an existing approved forecast, forecast-change KPIs, and historical operational forecast accuracy.  
**Packages:** #1/#2/#3/#4/#5/#7.  
**Business owner:** Demand Planning/S&OP, FP&A, Sales Operations.  
**Where to look:** Demand-planning system, planning workbook archive, approved forecast tables, budget files, version history.

**Request:** Forecast ID/version; created/issued timestamp; approval timestamp and status; target week/period; product/customer/market scope; forecast quantity and unit; dollars and currency where relevant; demand basis; constrained/unconstrained flag; model/statistical forecast versus override; override reason and author role; assumption/scenario ID; expected range when the source genuinely supplies one. Obtain original and revised budget versions and prior customer trade-expense plans separately.

**Grain:** Forecast origin/version × target period × documented product/customer scope × measure.

**Acceptance:** Do not treat the latest rewritten plan as the forecast that existed months ago. Forecast evaluation should use only information available at the forecast origin and the lead time relevant to the decision [5]. Where historic versions do not exist, start archiving now; label rolling-origin backtests separately from archived operational performance.

**Production package scope:** Request the planning horizon, weekly cutoff, accepted forecast version, unit convention, and covered channels. Do not require BOMs or a production scheduler just to display future bars. Never expose retailer identities through #2 screens, downloads, explanations, or conversational access.

## R14 — Finished-goods supply position and stock policies

**Priority:** Extension for "how many to make" or inventory-risk calculations; not a prerequisite for #2's forecast-only screen.  
**Packages:** #2/#3; selected #4 scenarios.  
**Business owner:** Supply Planning and Inventory Control.  
**Where to look:** ERP inventory/planning, warehouse system, 3PL feeds, co-manufacturer production commitments.

**Request:** SKU/location/as-of date; usable on-hand; reserved quantity; blocked/quarantined inventory; lot expiry where relevant; scheduled production or replenishment receipts and due dates/status; in-transit stock and ownership; stock targets and service assumptions; planned yield/loss convention; demand-consumption rules. For relevant partner stock, distinguish client-owned from retailer/distributor-owned inventory.

**Acceptance:** Net only compatible quantities and locations, with appropriate timing and availability. Do not count the same in-transit or committed supply twice. Production requirement is a separate derived measure from forecast retail sales.

# 3. Procurement Demand Outlook

**Core request for the original package:** R01/R03/R08 plus the approved forecast shared with #2. Ask Procurement to supply the purchasing horizon and commitment/review window by SKU or product family. Detailed supplier data is only necessary when those windows are to be derived from material lead times.

## R15 — Effective manufacturing formula/BOM and packaging requirements

**Priority:** Extension for material requirements.  
**Packages:** #3; selected #2/#4 extensions.  
**Business owner:** Manufacturing Engineering, R&D/Formulation, Master Data; Supply Chain owns co-manufacturer requests.  
**Where to look:** Approved ERP production BOM/formula, formulation/product-lifecycle system, controlled manufacturing specifications, authorized co-manufacturer data.

**Request:** Parent SKU and site; formula/BOM ID and version; approval status; effective dates; batch output basis; component material ID; quantity and unit; yield/scrap convention; wrappers, cartons, and other packaging; approved alternatives and their validity. Define whether supplied quantities already include expected losses.

**Grain:** Parent SKU × site × version × component material, with effective dates and batch basis.

**Acceptance:** Use the approved production/planning formula for the intended period and site, not an arbitrary current recipe. BOM/formula validity can depend on time, site and quantity, and formula versions can specify yield [3]. Nutrition labels are not manufacturing recipes.

**Commercial boundary:** For externally manufactured products, first establish whether the client purchases raw materials, supplies selected materials, or buys finished goods only. Request only the material responsibilities relevant to its decisions.

## R16 — Material availability, supplier terms, and purchase commitments

**Priority:** Extension for net purchase quantities/dates.  
**Packages:** #3; selected #4 cost/cash scenarios.  
**Business owner:** Procurement and Inventory Control.  
**Where to look:** Purchasing/ERP inventory, supplier master, sourcing agreements, purchase-order confirmations, material warehouse records.

**Request:** Material/location inventory with usable/held/expired status; supplier/material mapping; purchase unit and conversion; supplier production/transit/receiving lead times; calendars; order minimums and multiples; shelf-life rules; committed and confirmed PO quantities/dates; received and canceled quantities; price/currency/effective date; approved substitutes; material safety-stock and ownership conventions.

**Grain:** Material/location snapshot; supplier-material agreement version; PO line and receipt records.

**Acceptance:** Gross material requirement must follow time-phased production demand and effective formulas before netting available materials and receipts. No purchase order is created or released by this data request.

# 4. Financial Forecast & CapEx Scenarios

Reuse R01-R06, R08-R12 as relevant rather than requesting duplicate copies from Finance.

## R13 — Approved financial assumptions, product costs, capacity, and capital projects

**Priority:** Core for CapEx gap/scenario KPIs; cost detail is conditional on margin/return outputs.  
**Packages:** #4; economic effectiveness in #6/#7.

| Subset | Owner and source target | Fields to request | Grain/use |
|---|---|---|---|
| Financial plan and assumptions | FP&A; planning application, approved budget/forecast workbook | Original/revised plan, scenario, version/approval dates, target period, units/revenue, pricing and trade assumptions, growth/distribution assumptions, currency | Version × period × existing business grain; forecast comparisons |
| Product economics | Cost Accounting; costing records and finance warehouse | SKU/site, standard versus actual cost, effective period, variable/fixed classification, materials, conversion, freight and other approved contribution components | Cost version × SKU/site/period; defined margin/ROI bridge |
| Existing capacity | Operations/Industrial Engineering; line calendars, routing/rate tables, production history, co-manufacturer capacity commitments | SKU/family-to-resource mapping, throughput basis, run rates, available hours/shifts, downtime, yield/efficiency conventions, bottlenecks, existing load, contract limits | Resource/site/period plus SKU rate; demand-to-capacity comparison |
| Capital scenarios | Finance and Engineering; approved project register/business cases | Project ID, investment/timing, commissioning and ramp dates, incremental capacity by relevant resource, recurring costs/savings, utilization assumptions, approved evaluation horizon and discount assumptions | Project/scenario/time; explicitly assumption-driven capital comparison |

**Acceptance:** Bar volume alone is not a resource capacity measure. Keep rated and demonstrated capacity separate; avoid applying efficiency/yield reductions again when they are already included in supplied rates. Identify existing capacity, approved additions, proposed projects, and third-party capacity separately.

# 5. Customer Trade Expense Outlook

## R10 — Customer trade terms and future commitments

**Priority:** Core. **Packages:** #5, with #1/#4 financial use.  
**Business owner:** Trade Finance, Revenue Accounting, Sales Operations.  
**Where to look:** Trade-promotion/rebate system, signed customer agreements, approved program spreadsheets, contract repository.

**Request:** Program/agreement/version ID; customer, bill-to, ship-to or beneficiary eligibility; eligible/excluded SKUs and channels; start/end dates; governing date basis; rate or amount; denominator and unit; gross/net/scan/ship basis; thresholds, retrospective tiers and caps; fixed fees and allocation period; overlap/stacking rules; funding responsibility; event linkage; confirmation and approval status/date; expected settlement timing when used; source agreement reference.

**Grain:** Agreement/program version with customer/product eligibility and rule tables. Request actual agreement terms, not a single blended historical trade percentage.

Programs can use different eligibility dates and customer/product rules, percentage or per-unit amounts, tiers, and fixed commitments; these are distinct from their resulting accruals and claims [4].

**Acceptance:** Unconfirmed terms are visible assumptions, not zero expense. Separate planned shelf-price reductions from the manufacturer's contractual funding obligation.

## R11 — Historical trade expense, adjustments, accruals, claims, and settlements

**Priority:** Core for validating forecasts; reconciliation detail is supporting to a forecast-only screen.  
**Packages:** #5; net-sales reconciliation in #1/#4.  
**Business owner:** Trade Accounting, Accounts Receivable/Deductions, Controller.  
**Where to look:** Trade subledger, financial journals, deductions/claims workbench, credit-memo and settlement records, approved finance warehouse.

**Request:** Program/customer identifiers; expense-service period where known; posting period/date; transaction amount/currency; entry type; accrual creation/adjustment/reversal/relief; true-ups; claim and deduction IDs/reasons/status; settlement date/amount; linked invoice/credit/journal; approved classification; original and revised expense forecast versions.

**Grain:** Native financial/program transaction and linked claim/settlement records. Preserve links rather than merging every money movement into "expense."

**Acceptance:** Reconcile to the Controller-approved trade-expense totals. Keep expected expense, booked expense, open liability, deductions and cash settlement separate; a settlement must not automatically become a second expense. Keep financial posting functions outside the scope of this experience.

# 6. Competitive & Promotional Analysis

## R09 — Historical and planned price, promotion, marketing, and availability events

**Priority:** Core to event-specific analyses and forward scenarios; supporting to baseline SPINS competitive views.  
**Packages:** #6/#7/#4, forecast drivers for #1/#2/#3, event links for #5.  
**Business owner:** Trade Marketing, Sales Operations, Revenue Growth Management, BI/Insights.  
**Where to look:** Promotion calendar, trade-management application, pricing-change log, campaign planning tools, account execution reports, experimentation records.

**Request:** Event ID/version; affected UPC/SKU and product groups; retailer/market/channel scope; planned and actual dates; planned/approved/confirmed/executed/canceled status; regular and promotional retail price assumptions; wholesale-price event linkage; promotion tactic; feature/display execution; campaign objective; investment/funding classification; known stockouts, distribution changes and other disruptions; event decisions and approval timestamps. For existing tests, request treatment/control definitions, assignment/timing, pre/post outcome extracts, uncertainty and methodology.

**Grain:** Event × item × market/customer with effective dates, plus actual execution observations. Store planned and executed events separately.

**Acceptance:** Keep source-reported SPINS lift separate from Aevah's event/portfolio counterfactual. An event calendar improves attribution inputs but does not prove causal effects by itself. Existing studies are benchmark evidence, not automatic truth for every retailer/item/time.

**BI-specific requests:** Ask the Insights team for the approved competitor set, category/subcategory boundaries, comparable pack rules, and market definitions. For promotion ROI, obtain R13's relevant manufacturer contribution inputs and attributable spend, with rules preventing the same trade cost from being counted twice.

# 7. Item, Portfolio & Launch Strategy

## R12 — Launch, assortment, retirement, and portfolio strategy records

**Priority:** Core for launch views; supporting for lifecycle/portfolio scenarios.  
**Packages:** #7/#6/#4; forecast drivers for #1/#2/#3.  
**Business owner:** Brand/Innovation, Product Management, Sales Operations, FP&A.  
**Where to look:** Launch/stage-gate records, product lifecycle system, launch business cases, assortment/rollout trackers, approved forecast files.

**Request:** Launch ID; UPC/internal SKU; official launch date; actual/planned retailer availability dates; pilot versus broad release; approved rollout stores by retailer/week; baseline launch forecast by selling age and market; forecast issue/version date; cumulative expectations; intended audience/occasion/positioning; comparable launches; predecessor/successor and replacement relationships; reformulation/pack-size changes; planned delist dates; campaign and price-event IDs; initial fill versus expected recurring demand; launch success criteria and approved assumptions about substitution.

**Grain:** Launch × item × retailer/market × week and version; effective-dated portfolio relationships.

**Acceptance:** Keep the official launch, first observed sale, initial shipment, and on-shelf date distinct. A planned replacement should be identified explicitly when evaluating portfolio effects. Keep the original launch business case separate from later revised expectations.

# Delivery, history, and refresh requirements

These are proposed request defaults, not assertions about what the client has available.

| Topic | Request |
|---|---|
| Historical coverage | At minimum, align relevant internal history to the verified SPINS observation window. The user-stated start is April 13, 2025; validate the export's observation-date minimum. Request 24-36 months of internal sales/events when readily available, but do not block an initial release on unavailable older history. |
| Completed periods | Deliver through the latest completed internal period, identifying which dates align with the latest completed SPINS week. Do not present partially loaded weeks as complete. |
| Future horizon | All approved future price/trade/promotion/launch commitments; initial 52-week planning extract where available, longer if procurement lead times or Finance's approved capital horizon require it. Preserve approved plan coverage rather than manufacturing missing future values. |
| Detail | Native transaction line, effective-dated master relationship, SKU-period, resource-period, or plan-version grain as appropriate. Do not request only slide decks or monthly totals; control reports are still useful for reconciliation. |
| File/access format | Read-only client-approved views or structured extracts with stable headers. Obtain contracts/calculation workbooks as supporting evidence, not as the sole recurring transaction feed. No production write credentials are required. |
| Technical fields | Source system/table/export name; stable primary and relationship keys; schema dictionary; extract/as-of timestamp; business effective dates; created/updated timestamps where available; deletes/reversals; units; currencies; timezone/date conventions; record status. |
| Coverage and missing values | State included/excluded entities, brands, channels, markets, and periods; distinguish missing/not-applicable/zero/not-authorized. Do not fabricate UPC, customer, date, or quantity mappings. |
| Version history | Preserve both the effective business date and the date the information became known/approved. Capture recurring forecast and plan snapshots from first ingest. |
| Refresh | Proposed starting cadence: daily sales/shipments; weekly aligned retail forecasts; financial actuals at close plus adjustments; master/price/contract/event changes as approved; inventory/commitment refresh according to any enabled operational extension. |
| Controls | Record counts, source totals, invoice/credit and revenue reconciliations, trade-expense controls, UPC mapping coverage, forecast scope checks, and owner sign-off. |
| Access | Restrict commercial terms, recipes, and sensitive costs by role. #2 must not expose retailer data through screens, exports, or chat. Do not request consumer identities, payment details, payroll, or unrelated employee records. |

# Gaps that require a different action

| Gap | Correct next action |
|---|---|
| Retailer-only versus competitive-market geography | BI/data-license owner confirms the SPINS/Circana export scope and obtains the appropriate authorized geography or client-held retailer-only feed. A customer crosswalk alone does not resolve scope. |
| Meaning of EQ Units, store-count universe, baseline price, or tactic-lift denominators | Obtain the provider dictionary/methodology for this exact export and certify calculations. Do not replace provider definitions with convenient formulas. |
| Incomplete category/competitor coverage | Confirm licensed export coverage and a complete appropriate denominator. Internal own-brand sales cannot supply missing competitor sales. |
| Elasticity and cannibalization outputs | Supply usable outcomes, prices, promotion/distribution history, lifecycle context, and existing tests; estimate and validate models. Publish uncertainty and limitations. |
| Missing historical forecast snapshots | Start archiving now. Use explicitly labeled rolling-origin backtests with contemporaneously available inputs where possible; do not call them previously issued forecasts. |
| Missing manufacturer commercial/financial records | Label financial KPIs unavailable or assumption-driven until the client supplies them. Do not substitute retail dollars or retailer price discounts. |

# Recommended request sequence

| Stage | Request | Release consequence |
|---|---|---|
| 1 — Foundation and scope | R01-R03, with certified SPINS market/quantity definitions | Establishes products, bars, customers, calendars, and boundaries before KPI publication. |
| 2 — Commercial truth | R04-R06 and R10-R11 | Prioritizes the missing manufacturer sales and trade-expense foundation for #1/#4/#5. |
| 3 — Forward plans and context | R07-R09 and R12 | Adds distribution, forecast version comparisons, future events, launch expectations and model context. |
| 4 — Capital-planning inputs | R13 | Required before publishing the corresponding #4 capacity/CapEx outputs. |
| Optional operational extension | R14-R16 | Enables manufacture/material/purchase calculations beyond #2/#3's original demand-forecast screens. |

Stages can run in parallel by owner. They describe dependency and scope, not mandatory calendar phases. No numbered package should be marked complete while its required outputs still lack inputs.

# Client-facing request cover note

> We are connecting your existing SPINS retail data to seven role-specific Aevah experiences. Please identify one IT/Data coordinator and a business owner for each applicable data area below.
>
> Our first request is for product/UPC/pack mappings, customer/channel mappings, the fiscal calendar and approved metric definitions, posted manufacturer sales and adjustments, order/shipment history, current and future customer prices/trade agreements, trade-expense history, and existing forecast/plan versions. Please also provide the distribution, promotion, pricing, and launch calendars used by your commercial teams, plus the capacity and investment assumptions used for capital planning.
>
> For each dataset, please identify the source application or certified warehouse table, business owner, available history, record grain, keys, refresh cadence, and known gaps. Provide source totals or approved reports we can reconcile against. Existing controlled spreadsheets are acceptable for planning assumptions when version and approval information are preserved.
>
> Recipes, raw-material inventory, and purchase commitments are a separate optional request if we enable material/purchase calculations; they are not prerequisites for the initial bar-demand views. We are requesting read-only data for analysis and planning, not authority to post financial entries, release orders, or change operational plans.

## Source notes

The requests above are Aevah design recommendations; cited documentation supports specific distinctions, not claims about the client's installed systems.

[1] SPINS, Dollars glossary — retail-register sales definition. https://www.spins.com/cpg-learning-center/glossary/dollars/

[2] GS1 US, Packaging Level Definitions — packaging hierarchy and identifiers. https://www.help.gs1us.org/packaging-level

[3] Microsoft, Bills of materials and formulas — components, effective versions, site/quantity validity and yield. https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/bill-of-material-bom

[4] Oracle, Overview of Customer Programs — eligibility, date bases, tiers, percentage/per-unit and fixed programs, and separate program/accrual/claim records. https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25d/faccm/overview-of-managing-customer-programs.html

[5] Hyndman and Athanasopoulos, Forecasting: Principles and Practice, Time series cross-validation — forecast-origin and horizon-specific evaluation. https://otexts.com/fpp3/tscv.html

Companion conversation artifact: aevah_spins_kpi_source_mapping.md, version 1.0, September 9, 2026. This request follows its seven packages and does not certify the full SPINS export or any fitted model.
