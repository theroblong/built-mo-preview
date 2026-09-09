# Aevah: SPINS Source-to-KPI Mapping for Seven Experience Packages

**Version:** 1.0 · **Date:** September 9, 2026  
**Source inspected:** `head.csv` — 214 exact columns and four data rows, plus the header.  
**Scope:** The seven numbered experiences remain unchanged. This document maps their 47 ranked KPIs and 22 supporting calculations to the provided schema. It is a design and implementation specification, not a certification of the full export or fitted forecasts.

## Executive conclusion

The export provides a substantial retail-demand and market-analysis foundation: retail sales, package units, equivalent units, distribution, selling-store counts, velocities, retail prices, promotional activity, baseline and incremental sales estimates, tactic-specific lift measures, and first-selling dates.

However, it does **not** directly provide manufacturer gross/net revenue, trade contract expenses, future forecasts, cannibalization, elasticity estimates, production capacity, material recipes, inventory, or purchase commitments. Those must be modeled or joined to explicit business inputs. The terms “Dollars,” “Base Dollars,” and “Incr Dollars” must not be renamed into manufacturer financial measures. [S1; S2]

The most important scope issue is that the four records mix `RMA` and `CRMA`. A retailer-named competitive area is not the same as sales exclusively through that retailer. Circana describes CRMA as including the retailer's stores and surrounding competitors. Preserve this distinction in the semantic model and do not add competitive areas together to produce total company demand. The exact SPINS export geography definitions still need certification. [S1; S7; S8]

## Status and priority legends

| Code | Meaning |
|---|---|
| **D — Reported** | An actual column exists. A reported field may itself be a provider estimate, not a directly observed fact. |
| **C — Calculated** | Deterministic calculation using valid source grain, coverage, and units. |
| **M — Modeled** | Aevah forecast, elasticity, or counterfactual output is needed; not present in the CSV. |
| **E — Additional input** | A business source, product/account mapping, plan, contract, or model registry is needed. |

Priority remains the screen classification from the numbered use case: **Primary** supports the principal decision; **Supporting** explains it. Classification is independent of data readiness. A primary KPI can still be blocked by missing inputs. Extraneous data remains excluded rather than being promoted merely because a source column exists.

## 1. What the sample establishes

The header contains **214 unique columns**: 24 dimensions/attributes including `First Week Selling`, plus 190 numeric fact columns. Ninety-five columns carry the `, Yago` suffix. The four rows all have 214 fields; 113 columns are blank in all four sample records. These blank counts describe this sample only. [S1]

The sample's observation dates in `Time Period End Date` range from **September 7, 2025 to July 19, 2026**. The text `2025-04-13,0.07` in the first data record spans two different fields: `First Week Selling = 2025-04-13` and `Dollars SPM = 0.07`. April 13, 2025 remains the user-stated history start, not a start date verified from these four records. Verify the full export's minimum observation date using `Time Period End Date`. [S1]

The four product rows are MUSH, MADE GOOD, ONCE UPON A FARM and THATS IT. They do not establish the scope of owned brands in the full file. In particular, the MADE GOOD description is an **oat cup**, so not every product in the broad category may safely be treated as a physical bar. [S1]

### Candidate source grain

```text
Channel/Outlet
× Geography Level
× Retail Account
× Retail Account Level
× Geography
× Time Period
× Time Period End Date
× Product Universe
× Product Level
× UPC
```

This is a **candidate natural key** to test on the full export, not a uniqueness claim established by four rows. Store all original headers in the raw layer and map them to explicit Aevah field names. Keep source filename/version and ingest timestamp. Restrict weekly UPC analysis to `Time Period = WEEK` and `Product Level = UPC`; do not mix weekly rows with rolling totals or UPC detail with parent summaries.

### Recommended source groups

| Business concept | Exact source columns | Treatment |
|---|---|---|
| Market/account context | `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography` | Preserve all fields. Certify retailer-only vs competitive-area meaning. |
| Time | `Time Period`, `Time Period End Date` | Parse period end as MM/DD/YYYY; join a documented retail/fiscal calendar. |
| Product | `UPC`, `Description`, `Brand`, `Department`, `Category`, `Subcategory`, `Product Level`, `Product Universe` | Preserve UPC as text and map to owned products/internal SKUs. |
| Pack and physical quantity | `Units`, `PACK COUNT`, `EQ Units` | Package count, pack composition and equivalent quantity are distinct. |
| Retail revenue | `Dollars` | Retail sell-through dollars, not manufacturer revenue. |
| Price | `ARP`, `ARP, Promo`, `ARP, Non-Promo`, `Base ARP`, `Base ARP, Promo` | Retain reported price semantics; do not average ratios. |
| Distribution | `Avg % ACV`, `Max % ACV`, `TDP`, `Average Weekly TDP` | Different non-additive/partially additive measures, not interchangeable store counts. |
| Stores | `# of Stores`, `# of Stores Selling`, `% of Stores Selling` | Reporting-universe denominator, item selling count and percentage are different. |
| Weekly store velocity | `Average Weekly Dollars per Store Selling`, `Average Weekly Units per Store Selling`, and their `Per Item` variants | Use at source grain; recompute only with matching exposure denominators. |
| Promotions | `Dollars, Promo`, `Dollars, Non-Promo`, `Units, Promo`, `Units, Non-Promo`, `Promo Weeks` | Observed/reported activity, not a future calendar or funding contract. |
| Provider-estimated decomposition | `Base Dollars`, `Base Units`, `Incr Dollars`, `Incr Units` | Keep SPINS provenance; not a future forecast or net portfolio counterfactual. |
| Tactic lift | `Dollar ,% Lift, TPR`, `Units ,% Lift, TPR` and corresponding Display/Feature/Feature & Display fields | Exact punctuation matters. Do not sum tactic lift percentages. |
| Lifecycle | `First Week Selling` | First-selling field at its certified scope, not automatically global launch. |
| Product attributes | `FLAVOR`, `STORAGE`, `NFP - PROTEIN`, `NFP RANGES - PROTEIN VALUE`, `NFP - SUGARS`, `NFP - CALORIES`, `UNIT OF MEASURE` | Useful segmentation/model features; not a BOM or net-weight master. |
| Prior year | Exact source fields ending `, Yago` | Prior-year values, not previous forecasts. Blanks are unknown. |

All exact column names above are from the uploaded header. [S1]

## 2. Shared calculations and mandatory semantic rules

### 2.1 Packages, equivalent units and physical bars

SPINS defines a unit as the sellable package represented by the barcode. One unit can therefore be a multipack rather than an individual bar. [S3]

For a **verified bar-only pack**:

```text
physical_bars = Units × validated_bars_per_pack
```

For a variety pack:

```text
component_sku_bars = Units × component_bars_per_pack
```

Use a product/component mapping rather than assigning the entire variety pack to one flavor. `PACK COUNT` can populate the conversion only after validation. `EQ Units` is a promising reported equivalent quantity; the four rows approximately match `Units × PACK COUNT`, but this is not a contractual definition. Never multiply `EQ Units` by pack count again.

A validated implementation can retain both `reported_equivalent_units` and `calculated_component_bars`, flag discrepancies, and choose an approved source of truth. Do not silently coalesce or overwrite one with the other. `UNIT OF MEASURE = OUNCE` does not provide a separate numeric net weight or prove that equivalent units are ounces. [S1]

### 2.2 Retail price and revenue

```text
aggregate retail ARP = SUM(Dollars) / SUM(Units)
retail price per bar = SUM(Dollars) / SUM(validated physical bars)
```

Use only compatible scopes and nonzero denominators. A manufacturer's price and trade deductions come from a different commercial relationship and are not recoverable by renaming retail price fields. [S2; S3]

Preserve `Base ARP` as reported. **Do not derive it as `Base Dollars / Base Units`.** In the ONCE UPON A FARM sample, that ratio is approximately 8.17 while reported `Base ARP` is 8.81. The discrepancy shows that this substitution is invalid for this extract without the provider's exact definition. [S1]

### 2.3 Sales, baseline and promotion calculations

The following reconcile in all four sample records at the displayed precision:

```text
Dollars = Dollars, Promo + Dollars, Non-Promo
Units   = Units, Promo   + Units, Non-Promo
Dollars = Base Dollars  + Incr Dollars
Units   = Base Units    + Incr Units
```

These are sample reconciliation tests, not claims about every future row. Missing data and provider methodology must be checked. [S1]

Two separate calculated ratios:

```text
promo unit share % = 100 × SUM(Units, Promo) / SUM(Units)
full-period unit uplift % = 100 × SUM(Incr Units) / SUM(Base Units)
```

The second is a clearly named **full-period uplift ratio**. It is not the same denominator as tactic-specific promotional lift, and it is not an elasticity or cannibalization rate.

At a documented matching promotional exposure, `Units, Promo − Incr Units` may be a candidate promotional baseline. That derivation is gated on the provider definition. The export does not contain additive base/total/incremental units for each separate tactic. Consequently, it cannot support arbitrary, exact cross-row tactic-lift rollups merely by averaging the supplied percentages.

Do not treat `Any Feature`, `Any Display`, `Feature & Display`, `Feature Only` and `Display Only` as mutually exclusive totals to add. Preserve the supplied taxonomy and obtain the matching denominator definitions before aggregation.

### 2.4 Store counts, ACV and TDP

`# of Stores Selling` is available at the reported UPC-market-period grain. Summing it across UPCs double-counts stores carrying multiple items; summing across weeks produces exposures, not unique stores. There is no store identifier in the sample schema. A true brand-wide unique-store count needs a certified source rollup or store-level membership. [S1]

For one UPC over complete, comparable weekly records:

```text
packs per selling-store-week = SUM(Units) / SUM(weekly # of Stores Selling)
```

Across multiple UPCs, the analogous denominator is **store-item-weeks**; the result must be labeled accordingly. It is not brand sales per unique store.

SPINS defines TDP as the sum of item distribution contributions, combining distribution breadth and assortment depth. It is **not a count of stores**. Within a certified market-week, distinct SKU TDP contributions may be added; across weeks, a sum is point-weeks; across overlapping markets, do not sum. Brand ACV is not the arithmetic average of SKU ACVs. [S4]

### 2.5 Growth, share and comparison bases

```text
growth % = 100 × (current_value / comparable_prior_value − 1)
market share % = 100 × selected_brand_sales / complete_category_sales
share change pp = current_share_pct − prior_share_pct
growth gap pp = brand_growth_pct − competitor_or_category_growth_pct
```

Compare identical market, time, product-universe and unit definitions. `TPL` denotes Total Product Library; it does not certify that the export includes all category UPCs. Label a partial denominator as “share of selected set,” not market share. [S1; S6]

A blank `Dollars, Yago`, `Units, Yago` or selling-store comparison is not zero. If full historical data exists, join to a documented comparable retail week; otherwise display unavailable. Do not sum a partial set of non-null Yago values and compare it to all current sales without disclosing and controlling matched coverage.

### 2.6 Shared forecast contract

Experiences 2 and 3 should reuse the same approved SKU-week forecast, changing the visible planning window rather than silently changing the underlying demand estimate. Experience 4 may reuse it as a demand input to financial/capacity scenarios.

Proposed outputs, **not columns in the CSV**:

```text
run_id, model_version, data_version, scenario_id, scope_id,
as_of, training_cutoff, target_week, internal_sku,
forecast_mean_bars, p10_bars, p50_bars, p90_bars,
basis, approved_status, joint_path_reference
```

Historical drivers can include lagged units, prices, distribution, promotional activity, lifecycle and attributes. Future driver values must be known at the forecast origin or supplied as an explicit assumption. Never backtest against future realized price, distribution or promotional outcomes. Same-period `Base Units`/`Incr Units` are decompositions of the target and should not be used to leak that target into prediction.

Sum forecast **means** over non-overlapping SKUs/weeks. For uncertainty of an aggregate, sum joint simulated paths first and then calculate quantiles; sums of individual P90s are not a portfolio P90. A P10–P90 range can be labeled a central 80% prediction interval when appropriately calibrated, not “80% probability the model is correct.”

Forecast error definitions proposed for Aevah:

```text
WAPE % = 100 × SUM(ABS(F − A)) / SUM(ABS(A))
bias % = 100 × SUM(F − A) / SUM(ABS(A))
MAE = MEAN(ABS(F − A))
```

Positive bias means overforecasting. Use matched origins, horizons, actuals, scopes and units. Zero aggregate actual denominator means WAPE/bias unavailable; MAE remains separately interpretable. `Yago` cannot replace an archived forecast.

### 2.7 Elasticity, cannibalization and net incrementality

Elasticity describes demand sensitivity to price, but no elasticity estimate appears in the CSV. [S5; S1] Aevah should estimate it using the full panel and validated assumptions, with item/market, distribution, promotion, lifecycle, seasonality and competitive effects accounted for. A log-link coefficient on log price is a candidate model representation, not an automatic causal fact. Use a zero-safe model where necessary and avoid pretending that controls alone establish causality.

A transparent constant-elasticity **scenario illustration**, when that model form is validated, is:

```text
Q1 = Q0 × (P1 / P0)^elasticity
retail revenue change = P1 × Q1 − P0 × Q0
```

Manufacturer net-revenue consequences additionally require shipment timing, manufacturer prices, retail pass-through and deduction assumptions.

Proposed portfolio definitions:

```text
net portfolio incrementality = paired with-action portfolio outcome
                             − paired without-action portfolio outcome

cannibalized incumbent volume = sum of attributable negative incumbent
                               horizon effects from that paired comparison

cannibalization rate = cannibalized volume / explicitly selected
                      launch-or-promoted-item volume
```

Use one common evaluation horizon, separate halo, publish the denominator, and retain uncertainty. A lower incumbent SKU's sales is not by itself proof that another SKU displaced it. SPINS `Incr Units`/`Incr Dollars` should remain separate reported analytical measures rather than being relabeled net launch/portfolio incrementality.

## 3. Ranked KPI mappings by numbered experience

The ranked KPI inventory below preserves the seven numbered packages. Each entry distinguishes exact raw fields, model outputs and additional inputs. Source fields listed as “context only” must not be used as direct financial measures.


### 1) Customer Sales & Outlook

#### 1.1 — Net sales: actual and forecast by customer

**Screen priority:** Primary  
**Readiness:** E + C; M for forecast  
**Proposed output:** `manufacturer_net_sales_actual_and_forecast`

**Exact source columns:** `Retail Account`, `UPC`, `Time Period End Date`, `Dollars`, `Units`. [S1]

**Source role:** context only.

**Calculation / model:** Actual: SUM(internal net_sales_amount), or approved internal gross less the specified deduction components. Forecast: SUM(forecast shipment quantities × manufacturer gross price) − forecast applicable trade and other deductions, aligned to the revenue period.

**Additional inputs:** Internal sales ledger / invoices; Customer and product crosswalks; Manufacturer price and deduction rules; Shipment/order forecast and revenue timing.

**Guardrails:** SPINS Dollars is retail sell-through, not manufacturer net revenue. CRMA labels do not identify customer-only transactions. Raw SPINS values are context/features only.

#### 1.2 — Gross sales: actual and forecast by customer

**Screen priority:** Primary  
**Readiness:** E + C; M for forecast  
**Proposed output:** `manufacturer_gross_sales_actual_and_forecast`

**Exact source columns:** `Retail Account`, `UPC`, `Time Period End Date`, `Units`, `Dollars`. [S1]

**Source role:** context only.

**Calculation / model:** Actual: SUM(internal gross_sales_amount). Forecast: SUM(forecast manufacturer shipment units × applicable manufacturer gross price per matching unit).

**Additional inputs:** Invoices or approved gross-sales ledger; Manufacturer gross price list; Customer/SKU/UOM crosswalks; Shipment forecast.

**Guardrails:** Do not label Dollars or Base Dollars as manufacturer gross sales. A retail ARP is not a manufacturer selling price.

#### 1.3 — Selling-store count and count change

**Screen priority:** Primary  
**Readiness:** D + C; E for certified customer/brand rollup  
**Proposed output:** `reported_selling_store_count`

**Exact source columns:** `# of Stores Selling`, `# of Stores Selling, Yago`, `# of Stores`, `# of Stores, Yago`, `% of Stores Selling`, `UPC`, `Time Period End Date`, `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** At a certified product-market-week grain: source # of Stores Selling; change = current selling count − comparable prior selling count. Penetration = 100 × selling stores / reporting-universe stores.

**Additional inputs:** Geography and reporting-universe definitions; Certified brand/customer rollup or store-level membership for unique-store totals.

**Guardrails:** Do not SUM selling-store counts across UPCs or weeks. # of Stores is the geography denominator, not selling stores. All four sample selling-store Yago values are blank. CRMA is competitive-area context, not an account store list.

#### 1.4 — Gross/net sales growth versus a comparable period

**Screen priority:** Primary  
**Readiness:** E + C; retail sell-through alternative C  
**Proposed output:** `manufacturer_sales_growth_pct`

**Exact source columns:** `Dollars`, `Dollars, Yago`, `Units`, `Units, Yago`, `Time Period End Date`, `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`. [S1]

**Source role:** context only for original kpi.

**Calculation / model:** For actual manufacturer gross or net: 100 × (current / comparable prior − 1). SPINS alternative, separately labeled: 100 × (SUM(Dollars) / SUM(Dollars, Yago) − 1) on complete matched coverage.

**Additional inputs:** Internal gross/net history for original KPI; Comparable retail/fiscal calendar and coverage metadata.

**Guardrails:** No denominator => unavailable, not zero growth. Sparse Yago cannot be treated as a complete base. Use full prior-period join if source Yago is absent and historical coverage is validated.

#### 1.5 — Sales or units per selling store per week

**Screen priority:** Supporting  
**Readiness:** D + C  
**Proposed output:** `weekly_retail_velocity`

**Exact source columns:** `Average Weekly Dollars per Store Selling`, `Average Weekly Units per Store Selling`, `Average Weekly Dollars Per Store Selling Per Item`, `Average Weekly Units Per Store Selling Per Item`, `Dollars`, `Units`, `PACK COUNT`, `# of Stores Selling`, `UPC`, `Time Period End Date`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** At native grain use reported weekly velocity. For one UPC over complete weekly data: SUM(Units) / SUM(weekly stores selling); bar velocity = SUM(Units × validated bars_per_pack) / SUM(weekly stores selling).

**Additional inputs:** Approved pack-to-bar mapping when bars requested; Unique-store rollup only when a brand-wide per-store metric is required.

**Guardrails:** A denominator summed over UPC × week is store-item-weeks, not unique store-weeks. Do not average row velocities or multiply an aggregate ratio by an average pack count.

#### 1.6 — Gross-to-net reduction percentage

**Screen priority:** Supporting  
**Readiness:** E + C  
**Proposed output:** `manufacturer_gross_to_net_pct`

**Exact source columns:** **None**. [S1]

**Source role:** no direct source.

**Calculation / model:** 100 × (SUM(internal gross_sales) − SUM(internal net_sales)) / SUM(internal gross_sales).

**Additional inputs:** Internal gross and net sales on a consistent customer-period basis; Approved deduction taxonomy.

**Guardrails:** No SPINS column implements this measure. ARP % Discount and promo mix are different measures. Return unavailable for a zero gross denominator.


---

### 2) Production Demand Outlook

**Retailer exclusion applies to this experience end-to-end:** no retailer identities in charts, drilldowns, exported files, explanations or conversational responses. The underlying pipeline still needs market-scope metadata to avoid duplication. Removing visible labels is not a valid aggregation method.

#### 2.1 — Forecast bars by SKU and period

**Screen priority:** Primary  
**Readiness:** M + E for item/master/scope mapping  
**Proposed output:** `forecast_mean_bars`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`, `ARP`, `ARP, Non-Promo`, `ARP, Promo`, `Units, % Promo`, `ARP % Discount, Any Promo`, `Avg % ACV`, `TDP`, `# of Stores Selling`, `First Week Selling`, `FLAVOR`, `STORAGE`, `NFP RANGES - PROTEIN VALUE`, `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Map historical retail packs to validated bar components, build SKU-week sell-through history, then fit/backtest an as-of forecast using lagged demand and available-at-origin drivers. Output forecast mean bars for each target week.

**Additional inputs:** UPC-to-SKU/component and bars-per-pack master; Owned-brand/UPC list; Non-overlapping scope certification; Future planned drivers or explicit assumptions.

**Guardrails:** Use only owned-product demand from a certified non-overlapping market scope. Map UPC to internal SKU and physical bar components. Keep forecast sell-through separate from shipment and production requirements. Future realized price/promo/distribution is prohibited as a forecasting input; use only as-of-known plans or explicit scenarios. No retailer labels, scope names, drilldowns or prompts may expose retailer identity in this experience.

#### 2.2 — Total forecast bars in the planning horizon

**Screen priority:** Primary  
**Readiness:** C on M  
**Proposed output:** `horizon_forecast_mean_bars`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** SUM(forecast_mean_bars) across the selected target weeks and owned SKUs for one forecast version, scenario, scope and unit basis.

**Additional inputs:** Forecast output registry.

**Guardrails:** Sum means, not P50 values mislabeled as means. Do not sum overlapping markets or multiple versions.

#### 2.3 — Peak period demand and timing

**Screen priority:** Primary  
**Readiness:** C on M  
**Proposed output:** `peak_week_forecast_bars`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** First sum forecast mean bars within each target week for the selected scope; then MAX(weekly total), retaining its target week. At a single SKU use that SKU weekly series.

**Additional inputs:** Forecast output registry.

**Guardrails:** Peak is a maximum across weeks, not the sum of SKU maxima. Report target date and scope.

#### 2.4 — Change versus the previous accepted forecast

**Screen priority:** Supporting  
**Readiness:** C on M + E  
**Proposed output:** `forecast_revision_bars`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** For the same target SKU/weeks/scenario/scope: current forecast mean − previous accepted forecast mean; percent change divides by previous accepted mean when positive.

**Additional inputs:** Immutable forecast snapshots; Acceptance/version metadata.

**Guardrails:** Yago is prior-year actual data, not a previous forecast. Do not compare different rolling target windows.

#### 2.5 — Upper/lower forecast range

**Screen priority:** Supporting  
**Readiness:** M  
**Proposed output:** `forecast_p10_p90_bars`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`, `ARP`, `ARP, Non-Promo`, `ARP, Promo`, `Units, % Promo`, `ARP % Discount, Any Promo`, `Avg % ACV`, `TDP`, `# of Stores Selling`, `First Week Selling`, `FLAVOR`, `STORAGE`, `NFP RANGES - PROTEIN VALUE`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Estimate calibrated predictive quantiles, e.g. P10/P90 for a central 80% prediction interval; evaluate empirical coverage at the relevant horizon.

**Additional inputs:** Forecast/backtest outputs with quantiles or joint simulation paths.

**Guardrails:** No confidence column exists in CSV. For horizon or cross-SKU totals, aggregate joint sample paths before taking quantiles; marginal P90s are not additive.

#### 2.6 — Forecast error and bias at the production horizon

**Screen priority:** Supporting  
**Readiness:** C on actuals + archived M  
**Proposed output:** `production_forecast_wape_and_bias`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** For forecasts issued at a fixed lead horizon: WAPE = 100 × SUM(ABS(F−A)) / SUM(ABS(A)); signed bias = 100 × SUM(F−A) / SUM(ABS(A)). Positive bias means overforecast. MAE = mean absolute error.

**Additional inputs:** Archived as-of forecasts at production lead time; Complete matched actuals and SKU/scope metadata.

**Guardrails:** Use the same bars/retail basis for F and A. Zero denominator => unavailable WAPE/bias, show MAE separately. Four unrelated rows cannot evaluate forecast skill.


---

### 3) Procurement Demand Outlook

**Do not replace this package with an MRP app.** Forecast bars by SKU remains its core; recipe and material purchasing calculations are supporting extensions.

#### 3.1 — Forecast bars by SKU and period

**Screen priority:** Primary  
**Readiness:** M + E for item/master/scope mapping  
**Proposed output:** `forecast_mean_bars`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`, `ARP`, `ARP, Non-Promo`, `ARP, Promo`, `Units, % Promo`, `ARP % Discount, Any Promo`, `Avg % ACV`, `TDP`, `# of Stores Selling`, `First Week Selling`, `FLAVOR`, `STORAGE`, `NFP RANGES - PROTEIN VALUE`, `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Reuse the approved forecast_mean_bars from experience 2; select procurement-relevant target weeks without silently producing a conflicting forecast.

**Additional inputs:** Same product/scope masters and approved forecast output.

**Guardrails:** Use only owned-product demand from a certified non-overlapping market scope. Map UPC to internal SKU and physical bar components. Keep forecast sell-through separate from shipment and production requirements. Future realized price/promo/distribution is prohibited as a forecasting input; use only as-of-known plans or explicit scenarios.

#### 3.2 — Cumulative bars over the purchasing horizon

**Screen priority:** Primary  
**Readiness:** C on M; E for automatic lead-time windows  
**Proposed output:** `purchasing_horizon_mean_bars`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** SUM(forecast_mean_bars) over the selected purchasing window for each SKU or approved aggregate.

**Additional inputs:** Selected horizon, or material/supplier lead-time master for automatic windows.

**Guardrails:** Do not call bar demand a raw-material purchase quantity. Select different windows when supplier lead times differ.

#### 3.3 — Demand change over the purchasing horizon

**Screen priority:** Primary  
**Readiness:** C on M + E  
**Proposed output:** `purchasing_horizon_revision_bars`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** SUM(current forecast_mean_bars − previous accepted forecast_mean_bars) over an identical purchasing target window.

**Additional inputs:** Forecast versions and purchase-planning reference snapshot.

**Guardrails:** Compare identical SKU scope, target weeks and unit basis; distinguish scenario changes from new observations.

#### 3.4 — Upper/lower demand exposure

**Screen priority:** Supporting  
**Readiness:** M  
**Proposed output:** `purchasing_horizon_p10_p90_bars`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`, `ARP`, `ARP, Non-Promo`, `ARP, Promo`, `Units, % Promo`, `ARP % Discount, Any Promo`, `Avg % ACV`, `TDP`, `# of Stores Selling`, `First Week Selling`, `FLAVOR`, `STORAGE`, `NFP RANGES - PROTEIN VALUE`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** From joint forecast paths, calculate quantiles of cumulative bars over the purchasing window.

**Additional inputs:** Joint predictive paths or a separately calibrated cumulative-demand model.

**Guardrails:** Never SUM weekly P90 or SKU P90 values and label the result cumulative P90.

#### 3.5 — Change in SKU demand mix

**Screen priority:** Supporting  
**Readiness:** C on M  
**Proposed output:** `forecast_sku_mix_change_pp`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** SKU mix = SKU horizon forecast mean bars / total horizon forecast mean bars; change = 100 × (current mix − prior accepted mix), in percentage points.

**Additional inputs:** Approved current and comparison forecast snapshots.

**Guardrails:** Sum component bar quantities only across compatible definitions. Equal bar counts do not imply equal ingredient weights.

#### 3.6 — Forecast error at the procurement horizon

**Screen priority:** Supporting  
**Readiness:** C on actuals + archived M  
**Proposed output:** `procurement_forecast_wape_and_bias`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** WAPE/bias as in 2.6, evaluated at the purchase-commitment lead time or cumulative purchase window.

**Additional inputs:** Archived forecasts; Procurement lead-time/window definition; Matching actuals.

**Guardrails:** Do not reuse a one-week accuracy score as evidence for a twelve-week purchasing commitment.


---

### 4) Financial Forecast & CapEx Scenarios

**Keep forecast, CapEx drivers, elasticity and cannibalization inside this single numbered package.** A forecast-feed view, CapEx view and scenario view may be internal tabs.

#### 4.1 — Forecast net sales

**Screen priority:** Primary  
**Readiness:** M + E + C  
**Proposed output:** `forecast_manufacturer_net_sales`

**Exact source columns:** `Retail Account`, `UPC`, `Units`, `PACK COUNT`, `Dollars`, `Time Period End Date`. [S1]

**Source role:** context only.

**Calculation / model:** Aggregate forecast manufacturer shipment revenue at applicable manufacturer prices, less approved forecast deductions; reconcile by period to financial-plan definitions.

**Additional inputs:** Shipment-demand bridge; Manufacturer pricing; Trade/other deductions; Customer and period mappings.

**Guardrails:** Retail POS Dollars is a separate supporting outcome; do not replace internal net revenue with retail revenue.

#### 4.2 — Forecast bar volume over the planning horizon

**Screen priority:** Primary  
**Readiness:** M + C; E for mapping  
**Proposed output:** `finance_horizon_forecast_bars`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`, `ARP`, `ARP, Non-Promo`, `ARP, Promo`, `Units, % Promo`, `ARP % Discount, Any Promo`, `Avg % ACV`, `TDP`, `# of Stores Selling`, `First Week Selling`, `FLAVOR`, `STORAGE`, `NFP RANGES - PROTEIN VALUE`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Reuse approved forecast_mean_bars; aggregate by fiscal period and capacity-relevant product grouping where supplied.

**Additional inputs:** Product/capacity group crosswalk; Fiscal calendar; Approved forecast output.

**Guardrails:** Label as retail sell-through until a validated shipment/production bridge exists. Label weeks that straddle fiscal periods and the allocation convention.

#### 4.3 — Net portfolio incremental sales/units

**Screen priority:** Primary  
**Readiness:** M; E for manufacturer-dollar impact  
**Proposed output:** `net_portfolio_incrementality`

**Exact source columns:** `UPC`, `Brand`, `Time Period End Date`, `Units`, `PACK COUNT`, `Dollars`, `ARP`, `Units, Promo`, `Units, Non-Promo`, `Avg % ACV`, `# of Stores Selling`, `First Week Selling`, `FLAVOR`, `Subcategory`, `Base Units`, `Base Dollars`, `Incr Units`, `Incr Dollars`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Across a defined owned portfolio and common evaluation horizon: observed or scenario outcome − modeled no-action counterfactual. Sum paired portfolio outcomes before reporting net effect.

**Additional inputs:** Owned-portfolio mapping; Launch/promotion/pricing intervention definition; Validated counterfactual design; Manufacturer price/deductions for financial impact.

**Guardrails:** SPINS Incr Units/Dollars are supplied incremental measures, not proof of net portfolio growth. Do not subtract cannibalization twice if already captured by the counterfactual.

#### 4.4 — Modeled net revenue impact of a price scenario

**Screen priority:** Primary  
**Readiness:** M + E + C  
**Proposed output:** `price_scenario_net_revenue_delta`

**Exact source columns:** `UPC`, `Brand`, `Time Period End Date`, `Units`, `PACK COUNT`, `Dollars`, `ARP`, `ARP, Promo`, `ARP, Non-Promo`, `Base ARP`, `Base ARP, Promo`, `ARP % Discount, Any Promo`, `Units, % Promo`, `Avg % ACV`, `# of Stores Selling`, `TDP`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** For a constant-elasticity retail illustration: Q1=Q0×(P1/P0)^e; retail revenue delta=P1×Q1−P0×Q0. For manufacturer net revenue, use modeled shipment quantities and manufacturer net-price/deduction rules instead.

**Additional inputs:** Validated elasticity model; Approved scenario price and retail pass-through assumption; Manufacturer price and deduction inputs.

**Guardrails:** Retail and manufacturer price changes are not interchangeable. Restrict extrapolation to defensible ranges and show uncertainty and scope.

#### 4.5 — Demand-to-capacity gap

**Screen priority:** Primary in CapEx view  
**Readiness:** M + E + C  
**Proposed output:** `capacity_gap_hours`

**Exact source columns:** `UPC`, `Time Period End Date`, `Time Period`, `Units`, `PACK COUNT`, `EQ Units`, `Product Level`, `Product Universe`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Demand-related required standard hours = SUM(required production bars / validated effective bars per hour); gap = required standard hours − available standard hours for the corresponding resources/periods.

**Additional inputs:** Production-requirement bridge; SKU/resource rates; Available hours, yield and capacity assumptions.

**Guardrails:** SPINS has no line capacity, equipment, investment cost or manufacturing yield. Keep as a demand-input view until these exist.

#### 4.6 — Change versus approved financial forecast

**Screen priority:** Primary  
**Readiness:** C on M + E  
**Proposed output:** `financial_forecast_revision`

**Exact source columns:** `UPC`, `Retail Account`, `Time Period End Date`, `Dollars`, `Units`. [S1]

**Source role:** context only.

**Calculation / model:** Current financial forecast − approved reference forecast, for the same manufacturer revenue/unit basis and target fiscal periods.

**Additional inputs:** Approved finance forecast snapshot; Comparable current finance scenario.

**Guardrails:** Dollars, Yago is not an approved financial plan. Preserve assumption version and approval status.

#### 4.7 — Estimated price elasticity

**Screen priority:** Primary  
**Readiness:** M  
**Proposed output:** `own_price_elasticity_estimate`

**Exact source columns:** `UPC`, `Brand`, `Time Period End Date`, `Units`, `PACK COUNT`, `Dollars`, `ARP`, `ARP, Promo`, `ARP, Non-Promo`, `Base ARP`, `Base ARP, Promo`, `ARP % Discount, Any Promo`, `Units, % Promo`, `Avg % ACV`, `# of Stores Selling`, `TDP`, `Subcategory`, `First Week Selling`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Estimate price response within stable UPC/market series, controlling for distribution, promotion, lifecycle, seasonality and competitive conditions. A log-link model coefficient on log(price) is a candidate elasticity under explicit identification assumptions.

**Additional inputs:** Full panel history; Scope/product definitions; Sufficient price variation; Validation design and known-future scenario assumptions.

**Guardrails:** Not a one-row ratio, correlation or ARP discount. Use a zero-safe model where units are zero. Observational controls alone do not establish causality; withhold decision-grade estimates if identification fails.

#### 4.8 — Cannibalized volume and cannibalization rate

**Screen priority:** Primary  
**Readiness:** M  
**Proposed output:** `cannibalized_bars_and_rate`

**Exact source columns:** `UPC`, `Brand`, `Time Period End Date`, `Units`, `PACK COUNT`, `Dollars`, `ARP`, `Units, Promo`, `Units, Non-Promo`, `Avg % ACV`, `# of Stores Selling`, `First Week Selling`, `FLAVOR`, `Subcategory`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Using paired with-action and without-action models: displaced incumbent volume = SUM over affected incumbents of MAX(0, counterfactual horizon units − with-action horizon units). Rate = displaced units / defined launch-or-promoted-item units over that same horizon.

**Additional inputs:** Affected-portfolio and intervention definitions; Counterfactual model and uncertainty; Explicit denominator policy.

**Guardrails:** Aggregate effects over the evaluation horizon before classifying displacement. Treat halo separately. A simple decline in another SKU or SPINS Incr Units is not cannibalization.


---

### 5) Customer Trade Expense Outlook

**This remains trade-expense planning, not accrual booking.** No contract-rate, fixed-fee, confirmed-terms or expense-ledger fields exist in the source schema.

#### 5.1 — Forecast trade expense by customer and period

**Screen priority:** Primary  
**Readiness:** E + M + C  
**Proposed output:** `forecast_trade_expense`

**Exact source columns:** `Retail Account`, `UPC`, `Time Period End Date`, `Units`, `Units, Promo`, `Dollars`, `Dollars, Promo`, `Promo Weeks`, `ARP % Discount, Any Promo`. [S1]

**Source role:** context or scan driver only.

**Calculation / model:** For each eligible program, calculate the applicable basis: forecast eligible manufacturer gross sales × contract rate; OR forecast eligible scan units × allowance per scan unit; plus fixed commitments, applying contract dates, caps, tiers and non-duplicative stacking rules.

**Additional inputs:** Customer/program contracts; Eligibility, dates, rates, fixed fees, caps and tiers; Matching sales/scan forecasts; Customer/SKU/period mappings.

**Guardrails:** POS promo dollars and discount percentage do not identify manufacturer-funded expense. CRMA cannot serve as an account-only scanback quantity.

#### 5.2 — Change versus previous forecast or trade plan

**Screen priority:** Primary  
**Readiness:** C on E/M  
**Proposed output:** `trade_expense_revision`

**Exact source columns:** `Retail Account`, `UPC`, `Time Period End Date`, `Units`, `Units, Promo`, `Dollars`, `Dollars, Promo`, `Promo Weeks`, `ARP % Discount, Any Promo`. [S1]

**Source role:** context only.

**Calculation / model:** Current forecast_trade_expense − previous approved trade-expense forecast, over identical customer/program/period scope.

**Additional inputs:** Immutable trade forecast and plan versions.

**Guardrails:** Distinguish sales-volume, rate, program and timing changes. No suitable prior-plan column is present.

#### 5.3 — Forecast exposure covered by confirmed trade assumptions

**Screen priority:** Primary  
**Readiness:** E + C  
**Proposed output:** `trade_terms_coverage_pct`

**Exact source columns:** **None**. [S1]

**Source role:** no direct source.

**Calculation / model:** Within each comparable contract-basis group: 100 × forecast eligible exposure with confirmed applicable terms / total forecast eligible exposure. Report unresolved fixed-fee programs separately.

**Additional inputs:** Contract confirmation status; Eligibility coverage matrix; Forecast exposure in a consistent basis.

**Guardrails:** Do not combine dollars and scan units into one denominator. No terms or status fields exist in this export.

#### 5.4 — Expected trade expense as percentage of relevant gross sales

**Screen priority:** Supporting  
**Readiness:** E + C  
**Proposed output:** `forecast_trade_rate_of_gross_pct`

**Exact source columns:** **None**. [S1]

**Source role:** no direct source.

**Calculation / model:** 100 × forecast_trade_expense / matching forecast manufacturer gross sales.

**Additional inputs:** Forecast trade expense; Matching manufacturer gross sales forecast.

**Guardrails:** The denominator is not SPINS Dollars. Return unavailable for missing or zero denominator.

#### 5.5 — Expected expense by program or commitment

**Screen priority:** Supporting  
**Readiness:** E + M + C  
**Proposed output:** `forecast_trade_expense_by_program`

**Exact source columns:** `Retail Account`, `UPC`, `Time Period End Date`, `Units`, `Units, Promo`, `Dollars`, `Dollars, Promo`, `Promo Weeks`, `ARP % Discount, Any Promo`. [S1]

**Source role:** context or scan driver only.

**Calculation / model:** Group forecast program-level expense by customer, program_id, commitment type and expense period.

**Additional inputs:** Program IDs, contract terms and fixed commitments; Program-level forecast calculation.

**Guardrails:** Promo Weeks and retailer dates are not a unique trade agreement or event ID. Future promo calendars are not provided.

#### 5.6 — Historical expense forecast versus actual

**Screen priority:** Supporting  
**Readiness:** E + C  
**Proposed output:** `trade_expense_forecast_error`

**Exact source columns:** **None**. [S1]

**Source role:** no direct source.

**Calculation / model:** On aligned expense/customer/program periods: actual recorded trade expense − the historical forecast issued at the selected planning origin. Optionally calculate WAPE with a nonzero absolute-actual denominator.

**Additional inputs:** Historical trade-expense forecasts; Actual expense ledger and adjustment mapping.

**Guardrails:** Keep expense, accrual balance and settlement cash flow separate. Retail incremental dollars is not expense.


---

### 6) Competitive & Promotional Analysis

#### 6.1 — Market-share change

**Screen priority:** Primary  
**Readiness:** C; complete denominator required  
**Proposed output:** `market_share_change_pp`

**Exact source columns:** `Dollars`, `Dollars, Yago`, `Units`, `Units, Yago`, `EQ Units`, `Brand`, `UPC`, `Category`, `Subcategory`, `Product Universe`, `Product Level`, `Time Period End Date`, `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Dollar share=100×SUM(brand Dollars)/SUM(all category Dollars) within identical market/time/universe scope. Share change = current share − comparable prior share, in percentage points. For unit share select packs or validated equivalent/bar units explicitly.

**Additional inputs:** Complete category universe or certified category totals; Brand ownership and comparison definitions; Comparable calendar.

**Guardrails:** TPL is a product-universe label, not proof the export contains every category item. Never denominator=only selected own products. Do not combine UPC detail and category totals.

#### 6.2 — Net incremental portfolio units/revenue

**Screen priority:** Primary  
**Readiness:** M  
**Proposed output:** `net_portfolio_incrementality`

**Exact source columns:** `UPC`, `Brand`, `Time Period End Date`, `Units`, `PACK COUNT`, `Dollars`, `ARP`, `Units, Promo`, `Units, Non-Promo`, `Avg % ACV`, `# of Stores Selling`, `First Week Selling`, `FLAVOR`, `Subcategory`, `Base Dollars`, `Base Units`, `Incr Dollars`, `Incr Units`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Use the net portfolio counterfactual calculation in 4.3. Display SUM(Incr Units) and SUM(Incr Dollars) separately as SPINS-reported incremental performance, after valid scope/coverage filtering.

**Additional inputs:** Full affected portfolio; Intervention/counterfactual model and validation.

**Guardrails:** Provider-reported incrementality is not interchangeable with Aevah net portfolio incrementality. Missing model estimates are not zero.

#### 6.3 — Promotional incremental units and lift

**Screen priority:** Primary  
**Readiness:** D (provider-estimated) + C  
**Proposed output:** `reported_incremental_units_and_promo_lift`

**Exact source columns:** `Incr Units`, `Incr Dollars`, `Base Units`, `Base Dollars`, `Units`, `Dollars`, `Units, Promo`, `Units, Non-Promo`, `Dollars, Promo`, `Dollars, Non-Promo`, `Promo Weeks`, `Units ,% Lift, TPR`, `Dollar ,% Lift, TPR`, `Units ,% Lift, Any Display`, `Dollar ,% Lift, Any Display`, `Units ,% Lift, Any Feature`, `Dollar ,% Lift, Any Feature`, `Units ,% Lift, Feature & Display`, `Dollar ,% Lift, Feature & Display`, `ARP % Discount, Any Promo`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** At native grain use supplied incremental and tactic-specific lift values. A separately named full-period unit uplift ratio = 100×SUM(Incr Units)/SUM(Base Units). Promo unit mix = 100×SUM(Units, Promo)/SUM(Units).

**Additional inputs:** Provider fact definitions for event-baseline and tactic lift denominators; Event/eligible exposure mapping if event analysis is required.

**Guardrails:** Full-period uplift is not the source TPR/feature/display lift. Do not SUM or average lift percentages. Any Feature/Any Display/Feature & Display can overlap. This export lacks tactic-specific additive bases/volumes for exact tactic-level rollups.

#### 6.4 — Cannibalized units/sales and rate

**Screen priority:** Primary  
**Readiness:** M  
**Proposed output:** `cannibalized_units_and_rate`

**Exact source columns:** `UPC`, `Brand`, `Time Period End Date`, `Units`, `PACK COUNT`, `Dollars`, `ARP`, `Units, Promo`, `Units, Non-Promo`, `Avg % ACV`, `# of Stores Selling`, `First Week Selling`, `FLAVOR`, `Subcategory`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Reuse paired counterfactual displacement and explicit-denominator rate from 4.8; choose bar, pack or retail-dollar basis consistently.

**Additional inputs:** Intervention, affected portfolio and counterfactual model.

**Guardrails:** Do not infer causal displacement from simultaneous sales declines. Preserve confidence/interval and counterfactual provenance.

#### 6.5 — Growth gap versus competitors and category

**Screen priority:** Primary  
**Readiness:** C  
**Proposed output:** `growth_gap_pp`

**Exact source columns:** `Dollars`, `Dollars, Yago`, `Units`, `Units, Yago`, `EQ Units`, `Brand`, `UPC`, `Category`, `Subcategory`, `Product Universe`, `Product Level`, `Time Period End Date`, `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** For brand, competitor and full category separately: growth=100×(current/comparable prior−1). Gap=brand growth−comparison growth, in percentage points.

**Additional inputs:** Defined competitor set; Matched category coverage and calendar.

**Guardrails:** Incomplete Yago is not a valid total denominator. Match geography, assortment and retail unit basis; do not average per-item growth percentages.

#### 6.6 — Distribution-adjusted velocity

**Screen priority:** Supporting  
**Readiness:** D + C  
**Proposed output:** `distribution_adjusted_velocity`

**Exact source columns:** `Dollars/TDP`, `Units/TDP`, `Average Weekly TDP`, `TDP`, `Avg % ACV`, `Max % ACV`, `Dollars`, `Units`, `# of Stores Selling`, `Average Weekly Units per Store Selling`, `Average Weekly Dollars per Store Selling`, `Average Weekly Units Per Store Selling Per Item`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Use source weekly velocity at its native grain. For a single comparable market over weekly item rows: SUM(Units)/SUM(weekly SKU TDP) is units per distribution-point-week; label separately from per-store velocity.

**Additional inputs:** Certified comparable market scope and full exposure weeks.

**Guardrails:** TDP is not a store count. TDP sums across distinct SKU distribution contributions within one market/week, not across overlapping markets; summing across time creates point-weeks.

#### 6.7 — Incremental contribution / promotion ROI

**Screen priority:** Supporting  
**Readiness:** E + M + C  
**Proposed output:** `net_promotion_roi`

**Exact source columns:** `Incr Units`, `Incr Dollars`, `Units, Promo`, `Dollars, Promo`, `ARP, Promo`, `Base ARP, Promo`, `UPC`, `Time Period End Date`. [S1]

**Source role:** context and model inputs.

**Calculation / model:** Net promotion ROI = (incremental manufacturer contribution before separately counted promotion expense − attributable promotion expense) / attributable promotion expense.

**Additional inputs:** Manufacturer revenue and variable cost inputs; Actual trade/media/promotion cost; Portfolio counterfactual; Cost double-counting policy.

**Guardrails:** Incr Dollars is retail revenue, not manufacturer contribution. Ensure promoted prices and expense treatment do not charge a discount twice; zero cost => no ratio.


---

### 7) Item, Portfolio & Launch Strategy

**Launch stays within this package.** Launch trajectory moves to first priority only when the launch subview is selected.

#### 7.1 — Net portfolio incremental sales/units

**Screen priority:** Primary  
**Readiness:** M  
**Proposed output:** `net_portfolio_incrementality`

**Exact source columns:** `UPC`, `Brand`, `Time Period End Date`, `Units`, `PACK COUNT`, `Dollars`, `ARP`, `Units, Promo`, `Units, Non-Promo`, `Avg % ACV`, `# of Stores Selling`, `First Week Selling`, `FLAVOR`, `Subcategory`, `Incr Units`, `Incr Dollars`, `Base Units`, `Base Dollars`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Same governed portfolio counterfactual as 4.3 and 6.2, presented for the selected item/launch decision and affected portfolio.

**Additional inputs:** Defined launch/item intervention; Owned portfolio mapping; Validated counterfactual.

**Guardrails:** Do not use Incr Dollars as net launch incrementality. Include halo and displaced incumbent demand once.

#### 7.2 — Distribution-adjusted item velocity

**Screen priority:** Primary  
**Readiness:** D + C  
**Proposed output:** `marketing_item_velocity`

**Exact source columns:** `Average Weekly Units per Store Selling`, `Average Weekly Dollars per Store Selling`, `Average Weekly Units Per Store Selling Per Item`, `Units`, `Dollars`, `PACK COUNT`, `# of Stores Selling`, `Units/TDP`, `Dollars/TDP`, `TDP`, `UPC`, `Time Period End Date`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** At native item-market-week grain show reported packs/store/week; for verified bar packs show Units×bars_per_pack / stores selling. Compare like product forms and package sizes.

**Additional inputs:** Validated bar conversion where required.

**Guardrails:** Do not treat oat cups as bars because their EQ Units resembles component count. Keep store and TDP denominators distinct.

#### 7.3 — Modeled volume/revenue impact of a price scenario

**Screen priority:** Primary  
**Readiness:** M + C; E for financial translation  
**Proposed output:** `marketing_price_scenario_impact`

**Exact source columns:** `UPC`, `Brand`, `Time Period End Date`, `Units`, `PACK COUNT`, `Dollars`, `ARP`, `ARP, Promo`, `ARP, Non-Promo`, `Base ARP`, `Base ARP, Promo`, `ARP % Discount, Any Promo`, `Units, % Promo`, `Avg % ACV`, `# of Stores Selling`, `TDP`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Apply the validated demand model to paired current-price and scenario-price inputs. Simple constant-elasticity illustration: Q1=Q0×(P1/P0)^e; retail revenue delta=P1Q1−P0Q0.

**Additional inputs:** Elasticity model; Scenario inputs and pass-through assumptions; Manufacturer price/cost inputs only for financial outcomes.

**Guardrails:** Report retail revenue as retail revenue; confidence and model-validity limits are part of the result.

#### 7.4 — Cannibalized sales/units and rate

**Screen priority:** Primary  
**Readiness:** M  
**Proposed output:** `cannibalized_units_and_rate`

**Exact source columns:** `UPC`, `Brand`, `Time Period End Date`, `Units`, `PACK COUNT`, `Dollars`, `ARP`, `Units, Promo`, `Units, Non-Promo`, `Avg % ACV`, `# of Stores Selling`, `First Week Selling`, `FLAVOR`, `Subcategory`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Use the same governed displacement model and explicit denominator as 4.8/6.4 for selected items or launches.

**Additional inputs:** Affected portfolio; Intervention and counterfactual model.

**Guardrails:** Raw correlations or negative growth do not establish cannibalization.

#### 7.5 — Estimated price elasticity

**Screen priority:** Primary  
**Readiness:** M  
**Proposed output:** `own_price_elasticity_estimate`

**Exact source columns:** `UPC`, `Brand`, `Time Period End Date`, `Units`, `PACK COUNT`, `Dollars`, `ARP`, `ARP, Promo`, `ARP, Non-Promo`, `Base ARP`, `Base ARP, Promo`, `ARP % Discount, Any Promo`, `Units, % Promo`, `Avg % ACV`, `# of Stores Selling`, `TDP`, `First Week Selling`, `Subcategory`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Same versioned elasticity estimate as 4.7; segment by item/market and supported price regime; show interval and evidence status.

**Additional inputs:** Full panel history and identification/backtest design.

**Guardrails:** Do not substitute ARP % Discount or a two-point observed percentage change ratio.

#### 7.6 — Item/brand growth versus category

**Screen priority:** Primary  
**Readiness:** C  
**Proposed output:** `marketing_growth_gap_pp`

**Exact source columns:** `Dollars`, `Dollars, Yago`, `Units`, `Units, Yago`, `EQ Units`, `Brand`, `UPC`, `Category`, `Subcategory`, `Product Universe`, `Product Level`, `Time Period End Date`, `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Compute matched item/brand growth and category growth separately, then subtract growth percentages to obtain a percentage-point gap.

**Additional inputs:** Complete relevant category and comparable calendar.

**Guardrails:** A category-like selection containing only a few competitors must be labeled selected-set growth.

#### 7.7 — Market-share change

**Screen priority:** Primary  
**Readiness:** C; complete denominator required  
**Proposed output:** `market_share_change_pp`

**Exact source columns:** `Dollars`, `Dollars, Yago`, `Units`, `Units, Yago`, `EQ Units`, `Brand`, `UPC`, `Category`, `Subcategory`, `Product Universe`, `Product Level`, `Time Period End Date`, `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Reuse 6.1 share and share-change metric with the selected item/brand as numerator.

**Additional inputs:** Complete comparable denominator.

**Guardrails:** Use percentage points for share change. A broad universe tag alone does not certify a complete denominator.

#### 7.8 — Launch actual versus expected trajectory

**Screen priority:** Primary for launches; rank 1 in launch subview  
**Readiness:** D + C for actual trajectory; M/E for expected  
**Proposed output:** `launch_trajectory_variance`

**Exact source columns:** `First Week Selling`, `Time Period End Date`, `UPC`, `Description`, `Brand`, `Units`, `PACK COUNT`, `EQ Units`, `Dollars`, `# of Stores Selling`, `Avg % ACV`, `TDP`, `Average Weekly Units per Store Selling`. [S1]

**Source role:** direct or model inputs.

**Calculation / model:** Observed-market launch age = 1+floor((week_end−First Week Selling)/7). Compare cumulative actual packs/bars/dollars against the saved expected trajectory over the same age weeks and scope; variance=(actual/expected−1) when expected>0.

**Additional inputs:** Official launch dates and planned store rollout if requested; Saved launch forecast or approved analogue model; Product and market-scope mapping.

**Guardrails:** First Week Selling is an observed selling-date field whose market/product scope needs validation, not guaranteed global launch date. Missing launch weeks are unknown unless confirmed zero. Expectations must not be fitted retrospectively and presented as original plans.


---

## 4. Supporting datapoints and extensions

These preserve scope: a supporting extension does not redefine the numbered package. Exact raw sources are from the uploaded header; calculation designs are proposed for Aevah. [S1]

### Retail sell-through dollars

**Packages:** 1, 4, 6, 7 · **Priority:** Supporting in 1/4; Primary analysis in 6/7 · **Readiness:** D + C

**Sources:** `Dollars`, `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`, `Time Period`, `Time Period End Date`, `Product Universe`, `Product Level`, `UPC`.

**Calculation:** SUM(Dollars) over certified non-overlapping detail.

**Rules:** Separate from manufacturer gross/net sales.

### Retail packs sold

**Packages:** 1, 2, 3, 4, 6, 7 · **Priority:** Supporting actual; model target · **Readiness:** D + C

**Sources:** `Units`, `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`, `Time Period`, `Time Period End Date`, `Product Universe`, `Product Level`, `UPC`.

**Calculation:** SUM(Units) over certified detail.

**Rules:** Keep decimals; do not interpret packs as bars.

### Validated historical bars

**Packages:** 1, 2, 3, 4, 6, 7 · **Priority:** Primary historical foundation for demand · **Readiness:** C + E

**Sources:** `Units`, `PACK COUNT`, `EQ Units`, `UPC`, `Description`, `Subcategory`.

**Calculation:** Simple verified bar pack: Units × bars_per_pack. Variety pack: Units × component_bars_per_pack for each internal component SKU.

**Rules:** EQ Units may be used as bar quantity only after its unit definition is certified. Do not multiply EQ Units by PACK COUNT again.

**Other inputs:** Product component/UOM master and bar eligibility.

### Average retail price

**Packages:** 1, 4, 6, 7 · **Priority:** Supporting / Primary for pricing · **Readiness:** D + C

**Sources:** `Dollars`, `Units`, `ARP`.

**Calculation:** Aggregate ARP=SUM(Dollars)/SUM(Units) with nonzero denominator. Native ARP remains available as reported.

**Rules:** Weighted package price; mixed packages confound comparisons. Never average ARP arithmetically across rows.

### Retail price per physical bar

**Packages:** 4, 6, 7 · **Priority:** Supporting pricing comparison · **Readiness:** C + E

**Sources:** `Dollars`, `Units`, `PACK COUNT`, `EQ Units`.

**Calculation:** SUM(Dollars)/SUM(validated bars).

**Rules:** Use comparable product forms; no per-ounce price without validated product net weights.

**Other inputs:** Validated bar conversion.

### Promotional sales mix

**Packages:** 1, 6, 7 · **Priority:** Supporting · **Readiness:** C

**Sources:** `Dollars, Promo`, `Dollars`, `Units, Promo`, `Units`, `Dollars, % Promo`, `Units, % Promo`.

**Calculation:** Dollar promo share=100×SUM(Dollars, Promo)/SUM(Dollars); unit promo share=100×SUM(Units, Promo)/SUM(Units).

**Rules:** Source percentage fields are already percentage points (e.g. 30.8), not fractions. Recompute weighted shares; null is not zero.

### Reported baseline and incremental decomposition

**Packages:** 6, 7 · **Priority:** Primary BI; Supporting Marketing · **Readiness:** D (provider estimate)

**Sources:** `Base Dollars`, `Base Units`, `Incr Dollars`, `Incr Units`, `Dollars`, `Units`.

**Calculation:** Preserve reported Base and Incr; test Dollars≈Base Dollars+Incr Dollars and Units≈Base Units+Incr Units.

**Rules:** Provider estimates are not a future forecast or an Aevah net-portfolio counterfactual. Methodology and attribution quality are not supplied.

### Full-period uplift ratio

**Packages:** 6, 7 · **Priority:** Supporting · **Readiness:** C

**Sources:** `Incr Units`, `Base Units`, `Incr Dollars`, `Base Dollars`.

**Calculation:** 100×SUM(Incr Units)/SUM(Base Units), or dollar equivalent.

**Rules:** Label full-period baseline uplift. Not interchangeable with tactic/event lift.

### Promotional baseline units (conditional derivation)

**Packages:** 6, 7 · **Priority:** Supporting diagnostic pending definition · **Readiness:** C — gated

**Sources:** `Units, Promo`, `Incr Units`.

**Calculation:** Units, Promo − Incr Units, only if provider documentation confirms incremental units apply to that same promo exposure.

**Rules:** Not an exact exported field. Do not use to reconstruct tactic-specific baselines; no tactic-specific incremental volumes are supplied.

### Reported promo price/discount

**Packages:** 4, 6, 7 · **Priority:** Primary pricing context · **Readiness:** D

**Sources:** `Base ARP, Promo`, `ARP, Promo`, `ARP, Non-Promo`, `ARP % Discount, Any Promo`.

**Calculation:** Use reported values at their native grain. A diagnostic discount is 100×(1−promo_price/base_promo_price), subject to source precision and definition.

**Rules:** Do not infer actual trade funding. Do not derive Base ARP from Base Dollars/Base Units or overwrite it on mismatch.

### Launch selling age

**Packages:** 7 · **Priority:** Primary for launches · **Readiness:** D + C

**Sources:** `First Week Selling`, `Time Period End Date`, `UPC`, `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`.

**Calculation:** 1+floor((Time Period End Date−First Week Selling)/7) for aligned weekly dates.

**Rules:** Preserve geography-specific scope; not automatically official launch age.

### Planned vs observed launch distribution

**Packages:** 7 · **Priority:** Primary for launches · **Readiness:** D + E + C

**Sources:** `# of Stores Selling`, `Avg % ACV`, `TDP`, `UPC`, `Time Period End Date`.

**Calculation:** Compare actual distribution with the approved planned measure using the same denominator and scope.

**Rules:** Store count, ACV and TDP are not interchangeable.

**Other inputs:** Launch distribution plan with matching grain.

### Attribute-based item and category trends

**Packages:** 6, 7 · **Priority:** Supporting / Primary selected analysis · **Readiness:** C

**Sources:** `FLAVOR`, `STORAGE`, `NFP - PROTEIN`, `NFP RANGES - PROTEIN VALUE`, `NFP - SUGARS`, `NFP - CALORIES`, `PACK COUNT`, `Brand`, `Subcategory`, `Dollars`, `Units`, `EQ Units`, `Time Period End Date`.

**Calculation:** Group selected sales/growth/share metrics by validated attributes and matched reporting scope.

**Rules:** Parse nutrition amounts separately from units; serving basis is not explicit. Nutrition facts are not a recipe/BOM.

### Relative price index

**Packages:** 6, 7 · **Priority:** Supporting · **Readiness:** C

**Sources:** `ARP`, `Dollars`, `Units`, `EQ Units`, `PACK COUNT`, `Brand`, `UPC`, `Subcategory`.

**Calculation:** 100 × own comparable unit price / selected comparable competitor-set weighted unit price.

**Rules:** Use a declared comparison unit (pack, validated bar, or supplied net-weight unit). Do not compare a single bar price to a multipack price.

### Future raw-material requirement

**Packages:** 3 · **Priority:** Supporting extension · **Readiness:** M + E + C

**Sources:** `Units`, `PACK COUNT`, `EQ Units`, `UPC`, `Time Period End Date`.

**Calculation:** Explode a time-phased production requirement through the effective recipe/BOM, adjusting quantities for defined yield/scrap and unit conversions.

**Rules:** Do not explode retail sales directly into purchase quantities; inventory and production timing must be bridged first.

**Other inputs:** Time-phased production requirements; Effective recipe/BOM; Yields and unit conversions.

### Suggested material purchase quantity/date

**Packages:** 3 · **Priority:** Optional extension outside initial demand-review core · **Readiness:** M + E + C

**Sources:** No direct source field.

**Calculation:** Time-phase net material demand after usable stock and dated receipts, then apply safety stock, lead times, MOQ and order multiples.

**Rules:** No procurement inputs in the CSV. Do not fabricate purchase advice from nutrition fields.

**Other inputs:** Material inventory/open POs; Supplier lead times; MOQ/order multiples; Safety stock and shelf-life rules.

### Production requirement

**Packages:** 2 · **Priority:** Supporting extension · **Readiness:** M + E + C

**Sources:** No direct source field.

**Calculation:** Time-phase operational demand plus stock targets, net usable finished-goods inventory and scheduled receipts under the approved planning rules.

**Rules:** Forecast bars sold is not a production order; explicit schedule, yield and inventory inputs are needed.

**Other inputs:** Demand/shipment bridge; Usable finished-goods inventory; Scheduled production receipts; Stock targets and timing.

### CapEx NPV/payback

**Packages:** 4 · **Priority:** Supporting extension · **Readiness:** E + M + C

**Sources:** No direct source field.

**Calculation:** Use the investment model and forecast incremental cash flows with supplied investment timing and discount rate.

**Rules:** No equipment costs, rates, operating cash flows, or discount rates in CSV.

**Other inputs:** CapEx costs and dates; Capacity/cost model; Incremental cash-flow assumptions; Discount-rate policy.

### Gross/contribution margin

**Packages:** 4 · **Priority:** Supporting · **Readiness:** E + M + C

**Sources:** No direct source field.

**Calculation:** Manufacturer net revenue minus the cost categories defined for the chosen margin measure.

**Rules:** Gross margin and contribution margin must have distinct cost definitions.

**Other inputs:** Manufacturer net sales; COGS or variable-cost definitions and amounts.

### Account sales target variance

**Packages:** 1 · **Priority:** Supporting · **Readiness:** E + C

**Sources:** No direct source field.

**Calculation:** Actual/forecast manufacturer customer sales − matching approved target.

**Rules:** Targets are absent; source Yago is not a target.

**Other inputs:** Approved customer targets; Internal actual/forecast sales.

### Source coverage and availability

**Packages:** 1, 2, 3, 4, 5, 6, 7 · **Priority:** Supporting; blocking when incomplete · **Readiness:** C + E

**Sources:** `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`, `Time Period`, `Time Period End Date`, `Product Universe`, `Product Level`, `UPC`.

**Calculation:** Profile min/max week_end, distinct expected/missing weeks, product/market coverage, duplicate keys and ingest age.

**Rules:** Row absence is not automatically zero sales. The sample validates a schema only.

**Other inputs:** Expected coverage contract; Ingest timestamp/export metadata.

### Forecast and causal model provenance

**Packages:** 1, 2, 3, 4, 5, 6, 7 · **Priority:** Supporting; mandatory for modeled metrics · **Readiness:** E

**Sources:** No direct source field.

**Calculation:** Attach run_id, model_version, as_of, scenario_id, target period, training cutoff, data version, scope_id, unit basis and validation status.

**Rules:** These are proposed Aevah metadata fields, not columns present in head.csv.

**Other inputs:** Aevah model and forecast registries.

## 5. Worked checks from the four sample records

These are calculations on the supplied sample, not real-world customer-performance claims, company totals or model results. Rows represent different products, dates and scopes and **must not be summed into a business total**. [S1]

### 5.1 Pack normalization


| Sample product | Units (retail packs) | PACK COUNT | Units × PACK COUNT | Reported EQ Units |
| --- | --- | --- | --- | --- |
| MUSH | 2089.2 | 1 | 2089.2 | 2089.2 |
| MADE GOOD | 487.0 | 5 | 2435.0 | 2435.0 |
| ONCE UPON A FARM | 1888.0 | 6 | 11328.0 | 11328.2 |
| THATS IT | 364.0 | 12 | 4368.0 | 4368.0 |

Three samples reconcile exactly at the exported precision. ONCE UPON A FARM differs by 0.2 equivalent units: 11,328.0 calculated versus 11,328.2 reported. Rounding of projected inputs is one possible explanation, not a verified diagnosis. Retain the discrepancy and confirm the definition. The MADE GOOD row counts oat-cup components, not bars. [S1]

### 5.2 Promotional sales are not incremental sales

In the MUSH row:

```text
Units                    2,089.2
Units, Promo               644.1
Units, Non-Promo         1,445.1
Base Units               1,849.1
Incr Units                 240.1
```

Its promotional unit share is approximately **30.83%**, matching the reported 30.8 after rounding. Its full-period baseline uplift is approximately **12.98%**. The source `Units ,% Lift, TPR` is **62.6%**. These are different denominators and different questions. Do not substitute one for another. [S1]

### 5.3 Base ARP is not a naive base-volume quotient

In the ONCE UPON A FARM row:

```text
Base Dollars / Base Units = 11,540.42 / 1,412.4 ≈ 8.17
reported Base ARP = 8.81
```

Preserve the provider's baseline-price fact rather than silently rebuilding it. [S1]

### 5.4 CRMA scope and store denominators

The WALMART-labeled row is `WALMART CORP - MULO CRMA`; its `# of Stores` is 105,642, `# of Stores Selling` is 951, and reported `% of Stores Selling` is 0.9. The arithmetic is about 0.9002%. This is internally consistent as a scope denominator, not evidence that the named customer operates 105,642 stores. The geography definition must govern the UI label. [S1; S7]

## 6. Required additional datasets and joins


### `product_component_map`

**Proposed key:** UPC × effective_date × internal_component_sku  
**Minimum fields:** `owned_product_flag`, `internal_sellable_sku`, `component_bars_per_pack`, `bar_product_flag`, `uom_conversion`, `effective_from`, `effective_to`

Components handle variety packs; NFP fields are not a substitute.

### `market_scope_registry`

**Proposed key:** scope_id / raw geography fields  
**Minimum fields:** `scope_type`, `is_retailer_only`, `customer_mapping_valid`, `scope_version`, `coverage_start`, `coverage_end`, `approved_nonoverlap_group`, `denominator_definition`

Mapping is not authorization to sum overlapping scopes.

### `customer_account_map`

**Proposed key:** raw retailer-only account × effective_date  
**Minimum fields:** `internal_customer_id`, `account_scope`, `effective_dates`

Do not map CRMA totals to customer invoice totals.

### `forecast_output`

**Proposed key:** run_id × scenario_id × scope_id × sku × target_week  
**Minimum fields:** `as_of`, `training_cutoff`, `forecast_mean_bars`, `p10_bars`, `p50_bars`, `p90_bars`, `model_version`, `data_version`, `basis`, `approved_status`, `joint_path_reference`

Quantile aggregation uses joint paths, not sums of quantiles.

### `manufacturer_sales_and_prices`

**Proposed key:** customer × internal_sku × period  
**Minimum fields:** `gross_sales_amount`, `net_sales_amount`, `deduction_components`, `shipment_units`, `price_per_matching_uom`, `valid_dates`

Source for original gross/net KPIs.

### `trade_programs`

**Proposed key:** customer × program_id × sku_eligibility × effective_dates  
**Minimum fields:** `basis_type`, `rate`, `allowance_per_unit`, `fixed_commitment`, `caps`, `tiers`, `stacking_policy`, `confirmed_status`, `expense_timing`

Required for trade expense. Raw promo discount is not a funding contract.

### `plan_snapshots`

**Proposed key:** plan_type × version × target_scope/period  
**Minimum fields:** `approved_status`, `as_of`, `forecast_or_target_values`, `assumption_version`

Forecast comparisons need historic snapshots.

### `operational_planning_inputs`

**Proposed key:** resource/material/sku × effective_period  
**Minimum fields:** `inventory`, `scheduled_receipts`, `BOM`, `yield`, `lead_time`, `line_rate`, `available_capacity`, `material_cost`, `capex_cost`

Optional extensions for 2–4, not inferred from SPINS.

### `launch_plan`

**Proposed key:** launch_id × sku × scope × target_week  
**Minimum fields:** `official_launch_date`, `planned_distribution`, `expected_trajectory`, `forecast_origin`, `approved_version`

Separates first observed selling from planned global launch.

## 7. Validation and activation gates

These are requirements for implementation, not checks already completed on the unseen full file.


**G1 — Source coverage:** Profile full MIN/MAX period-end date, expected weekly continuity, UPC and market coverage; user-stated 2025-04-13 is not verified by first-selling date.

**G2 — Scope and additivity:** Certify retailer-only vs competitive areas; use disjoint scopes or approved total-market records. Exclude overlapping totals and nested product universes.

**G3 — Bars and owned items:** Certify EQ conversion, pack composition, eligible bar products, owned UPCs and effective-dated SKU mappings. Do not infer all wellness/snack rows are bars.

**G4 — Non-additive metrics:** Define store/ACV/TDP/rate rollups; block unique-store totals without rollup evidence and tactic lift aggregates without denominators.

**G5 — Provider-model fields:** Obtain exact definitions for Base/Incr, Base ARP, tactic lift, SPM/SPP, Weight Weeks and SPK. Retain unresolved fields without business relabeling.

**G6 — Forecast/causal readiness:** Rolling-origin tests by horizon, no future-driver leakage, adequate variation, counterfactual assumptions and uncertainty. Withhold weak causal estimates.

**G7 — Business financial inputs:** Link approved internal revenue and trade program data before gross/net/expense KPI activation.


### Additional implementation checks

**Ingestion:** Verify row lengths and exact headers; parse dates with explicit formats; keep UPCs as strings; preserve numeric precision; convert blanks to null. Preserve the original source field alongside a normalized alias. Do not silently remove punctuation from headers without an exact-name mapping.

**Availability:** Profile missing weeks per certified series. Distinguish out-of-scope, absent reporting, missing values, prelaunch and confirmed zero sales. Backtests must reflect source latency and the values actually available at their forecast origins.

**Reconciliation:** Test promo/non-promo and base/incremental identities with tolerances that account for displayed precision. Investigate exceptions; do not force every row to balance by overwriting source values.

**Non-additive facts:** No generic SUM for every numeric field. No sum of store counts to produce brand doors; no arithmetic mean of ARPs or lift percentages; no ACV used as a store percentage; no TDP used as a store count; no EQ Units multiplied by pack count again.

**Product scope:** Keep competitor items in BI/Marketing analysis and demand-driver datasets where appropriate, but not in the manufacturer's production/procurement demand totals. Effective-date changes in pack counts and component mappings.

**Time scope:** A full export beginning April 13, 2025 does not give every new SKU a full year of history. Evaluate continuity and length per series. Avoid unsupported seasonal/causal certainty merely because the overall extract is large.

**Financial scope:** Retail POS dollars, manufacturer invoice revenue, estimated demand and recorded expense must have separate semantic metric IDs, not merely different display labels over the same source field.

**Promotional scope:** Historical `Promo Weeks` is not an event ID or a future promotional plan. `SPK` and specialized `SPM`, `SPP`, `Weight Weeks` fields are retained but not expanded into invented business definitions. Obtain the contractual data dictionary before primary use.

**Model governance:** A scenario does not overwrite the approved forecast. Every prediction or counterfactual carries the model/data version, source scope, as-of date, output units, expected range, validation status and assumptions. A low-evidence estimate should be unavailable or exploratory, not disguised as a confirmed KPI.

## 8. Practical delivery order inside the seven packages

| Experience | Source-ready foundation after scope checks | Still needs models or other inputs |
|---|---|---|
| 1. Customer Sales & Outlook | Retail sales context, reported item-store counts, velocity, retail growth | Actual customer-only scope, manufacturer gross/net revenue, customer forecasts, unique-store rollups |
| 2. Production Demand Outlook | Validated owned-product historical bars | Forecasts and intervals; operational bridge only for production requirements |
| 3. Procurement Demand Outlook | Same historical bar foundation | Shared forecasts and purchasing windows; BOM/inventory/PO inputs only for extensions |
| 4. Financial Forecast & CapEx Scenarios | Retail-demand and pricing inputs | Manufacturer financial forecast, elasticity/cannibalization models, capacity and investment assumptions |
| 5. Customer Trade Expense Outlook | Historical promotional activity as context | Customer contracts, financial/eligible scan forecasts, expense history and plan versions |
| 6. Competitive & Promotional Analysis | Sales, properly scoped share/growth, reported baseline/incremental, promotional mix and native tactic lift | Net portfolio causal effects, cannibalization, economic ROI inputs |
| 7. Item, Portfolio & Launch Strategy | Item/attribute trends, price positioning, reported velocity and first-selling trajectories | Elasticity/cannibalization, saved launch expectation and distribution plans |

**Recommendation:** Preserve the seven experience packages. Implement a common governed metric and forecast layer, but activate only the measures whose scope, unit, denominator and provenance are established. SPINS supplies much of the retail evidence; Aevah supplies modeled outputs and integration with the specific business facts required by each experience.

## 9. Complete source-column inventory

This is the exact 214-column header inventory and proposed ingestion classification. The companion JSON dictionary contains sample non-null counts, exact observed values, related KPI IDs and per-column guardrails. Aliases are proposed Aevah names, not existing export columns.


| # | Exact source column | Proposed Aevah alias | Family | Sample non-null / 4 |
| --- | --- | --- | --- | --- |
| 1 | `Channel/Outlet` | `channel_outlet` | dimension | 4 |
| 2 | `Geography Level` | `geography_level` | dimension | 4 |
| 3 | `Retail Account` | `retail_account` | dimension | 4 |
| 4 | `Retail Account Level` | `retail_account_level` | dimension | 4 |
| 5 | `Geography` | `geography` | dimension | 4 |
| 6 | `Time Period` | `time_period` | dimension | 4 |
| 7 | `Time Period End Date` | `week_end_date` | dimension | 4 |
| 8 | `Product Universe` | `product_universe` | dimension | 4 |
| 9 | `Product Level` | `product_level` | dimension | 4 |
| 10 | `Department` | `department` | dimension | 4 |
| 11 | `Category` | `category` | dimension | 4 |
| 12 | `Subcategory` | `subcategory` | dimension | 4 |
| 13 | `Brand` | `brand` | dimension | 4 |
| 14 | `UPC` | `upc` | dimension | 4 |
| 15 | `Description` | `description` | dimension | 4 |
| 16 | `PACK COUNT` | `reported_pack_count` | product_attribute | 4 |
| 17 | `FLAVOR` | `flavor` | dimension | 4 |
| 18 | `NFP - PROTEIN` | `nfp_protein` | dimension | 4 |
| 19 | `NFP RANGES - PROTEIN VALUE` | `nfp_ranges_protein_value` | dimension | 4 |
| 20 | `STORAGE` | `storage` | dimension | 4 |
| 21 | `UNIT OF MEASURE` | `unit_of_measure` | dimension | 4 |
| 22 | `NFP - SUGARS` | `nfp_sugars` | dimension | 4 |
| 23 | `NFP - CALORIES` | `nfp_calories` | dimension | 4 |
| 24 | `Dollars` | `retail_sales_dollars` | additive_volume | 4 |
| 25 | `Dollars, Yago` | `retail_sales_dollars_yago` | additive_volume | 0 |
| 26 | `Units` | `retail_pack_units` | additive_volume | 4 |
| 27 | `Units, Yago` | `retail_pack_units_yago` | additive_volume | 0 |
| 28 | `EQ Units` | `reported_equivalent_units` | additive_volume | 4 |
| 29 | `EQ Units, Yago` | `reported_equivalent_units_yago` | additive_volume | 0 |
| 30 | `Avg % ACV` | `reported_avg_acv_pct` | distribution | 4 |
| 31 | `Avg % ACV, Yago` | `reported_avg_acv_pct_yago` | distribution | 0 |
| 32 | `Max % ACV` | `reported_max_acv_pct` | distribution | 4 |
| 33 | `Max % ACV, Yago` | `reported_max_acv_pct_yago` | distribution | 0 |
| 34 | `TDP` | `tdp` | distribution | 4 |
| 35 | `TDP, Yago` | `tdp_yago` | distribution | 0 |
| 36 | `Average Weekly TDP` | `average_weekly_tdp` | distribution | 4 |
| 37 | `Average Weekly TDP, Yago` | `average_weekly_tdp_yago` | distribution | 0 |
| 38 | `Average Items Selling` | `average_items_selling` | exposure | 4 |
| 39 | `Average Items Selling, Yago` | `average_items_selling_yago` | exposure | 0 |
| 40 | `Number of Weeks Selling` | `number_of_weeks_selling` | exposure | 4 |
| 41 | `Number of Weeks Selling, Yago` | `number_of_weeks_selling_yago` | exposure | 0 |
| 42 | `Weight Weeks` | `weight_weeks` | specialized_provider_measure | 4 |
| 43 | `Weight Weeks, Yago` | `weight_weeks_yago` | specialized_provider_measure | 0 |
| 44 | `First Week Selling` | `first_week_selling` | lifecycle | 4 |
| 45 | `Dollars SPM` | `dollars_spm` | specialized_provider_measure | 4 |
| 46 | `Dollars SPM, Yago` | `dollars_spm_yago` | specialized_provider_measure | 0 |
| 47 | `Units SPM` | `units_spm` | specialized_provider_measure | 4 |
| 48 | `Units SPM, Yago` | `units_spm_yago` | specialized_provider_measure | 0 |
| 49 | `Average Weekly Dollars SPM` | `average_weekly_dollars_spm` | specialized_provider_measure | 4 |
| 50 | `Average Weekly Dollars SPM, Yago` | `average_weekly_dollars_spm_yago` | specialized_provider_measure | 0 |
| 51 | `Average Weekly Units SPM` | `average_weekly_units_spm` | specialized_provider_measure | 4 |
| 52 | `Average Weekly Units SPM, Yago` | `average_weekly_units_spm_yago` | specialized_provider_measure | 0 |
| 53 | `Dollars SPM Per Item` | `dollars_spm_per_item` | specialized_provider_measure | 4 |
| 54 | `Dollars SPM Per Item, Yago` | `dollars_spm_per_item_yago` | specialized_provider_measure | 0 |
| 55 | `Units SPM Per Item` | `units_spm_per_item` | specialized_provider_measure | 4 |
| 56 | `Units SPM Per Item, Yago` | `units_spm_per_item_yago` | specialized_provider_measure | 0 |
| 57 | `Dollars SPP` | `dollars_spp` | specialized_provider_measure | 4 |
| 58 | `Dollars SPP, Yago` | `dollars_spp_yago` | specialized_provider_measure | 0 |
| 59 | `Units SPP` | `units_spp` | specialized_provider_measure | 4 |
| 60 | `Units SPP, Yago` | `units_spp_yago` | specialized_provider_measure | 0 |
| 61 | `Dollars/TDP` | `dollars_per_tdp` | velocity_or_weekly_average | 4 |
| 62 | `Dollars/TDP, Yago` | `dollars_per_tdp_yago` | velocity_or_weekly_average | 0 |
| 63 | `Units/TDP` | `units_per_tdp` | velocity_or_weekly_average | 4 |
| 64 | `Units/TDP, Yago` | `units_per_tdp_yago` | velocity_or_weekly_average | 0 |
| 65 | `ARP` | `reported_average_retail_price` | price | 4 |
| 66 | `ARP, Yago` | `reported_average_retail_price_yago` | price | 0 |
| 67 | `Dollars, Promo` | `dollars_promo` | additive_volume | 4 |
| 68 | `Dollars, Promo, Yago` | `dollars_promo_yago` | additive_volume | 0 |
| 69 | `Dollars, Non-Promo` | `dollars_non_promo` | additive_volume | 4 |
| 70 | `Dollars, Non-Promo, Yago` | `dollars_non_promo_yago` | additive_volume | 0 |
| 71 | `Dollars, % Promo` | `dollars_pct_promo` | promotion_percentage | 4 |
| 72 | `Dollars, % Promo, Yago` | `dollars_pct_promo_yago` | promotion_percentage | 0 |
| 73 | `Units, Promo` | `units_promo` | additive_volume | 4 |
| 74 | `Units, Promo, Yago` | `units_promo_yago` | additive_volume | 0 |
| 75 | `Units, Non-Promo` | `units_non_promo` | additive_volume | 4 |
| 76 | `Units, Non-Promo, Yago` | `units_non_promo_yago` | additive_volume | 0 |
| 77 | `Units, % Promo` | `units_pct_promo` | promotion_percentage | 4 |
| 78 | `Units, % Promo, Yago` | `units_pct_promo_yago` | promotion_percentage | 0 |
| 79 | `Avg % ACV, Any Promo` | `avg_pct_acv_any_promo` | distribution | 4 |
| 80 | `Avg % ACV, Any Promo, Yago` | `avg_pct_acv_any_promo_yago` | distribution | 0 |
| 81 | `Avg % ACV, Non-Promo` | `avg_pct_acv_non_promo` | distribution | 4 |
| 82 | `Avg % ACV, Non-Promo, Yago` | `avg_pct_acv_non_promo_yago` | distribution | 0 |
| 83 | `Max % ACV, Any Promo` | `max_pct_acv_any_promo` | distribution | 4 |
| 84 | `Max % ACV, Any Promo, Yago` | `max_pct_acv_any_promo_yago` | distribution | 0 |
| 85 | `Max % ACV, Non-Promo` | `max_pct_acv_non_promo` | distribution | 4 |
| 86 | `Max % ACV, Non-Promo, Yago` | `max_pct_acv_non_promo_yago` | distribution | 0 |
| 87 | `TDP, Any Promo` | `tdp_any_promo` | distribution | 4 |
| 88 | `TDP, Any Promo, Yago` | `tdp_any_promo_yago` | distribution | 0 |
| 89 | `TDP, Non-Promo` | `tdp_non_promo` | distribution | 4 |
| 90 | `TDP, Non-Promo, Yago` | `tdp_non_promo_yago` | distribution | 0 |
| 91 | `Weight Weeks, Any Promo` | `weight_weeks_any_promo` | specialized_provider_measure | 4 |
| 92 | `Weight Weeks, Any Promo, Yago` | `weight_weeks_any_promo_yago` | specialized_provider_measure | 0 |
| 93 | `Weight Weeks, Non-Promo` | `weight_weeks_non_promo` | specialized_provider_measure | 4 |
| 94 | `Weight Weeks, Non-Promo, Yago` | `weight_weeks_non_promo_yago` | specialized_provider_measure | 0 |
| 95 | `Average Weekly TDP, Any Promo` | `average_weekly_tdp_any_promo` | distribution | 4 |
| 96 | `Average Weekly TDP, Any Promo, Yago` | `average_weekly_tdp_any_promo_yago` | distribution | 0 |
| 97 | `Average Weekly TDP, Non-Promo` | `average_weekly_tdp_non_promo` | distribution | 4 |
| 98 | `Average Weekly TDP, Non-Promo, Yago` | `average_weekly_tdp_non_promo_yago` | distribution | 0 |
| 99 | `Promo Weeks` | `promo_weeks` | exposure | 4 |
| 100 | `Promo Weeks, Yago` | `promo_weeks_yago` | exposure | 4 |
| 101 | `Base Dollars` | `reported_baseline_dollars` | provider_estimated_volume | 4 |
| 102 | `Base Dollars, Yago` | `reported_baseline_dollars_yago` | provider_estimated_volume | 0 |
| 103 | `Base Units` | `reported_baseline_pack_units` | provider_estimated_volume | 4 |
| 104 | `Base Units, Yago` | `reported_baseline_pack_units_yago` | provider_estimated_volume | 0 |
| 105 | `Incr Dollars` | `reported_incremental_dollars` | provider_estimated_volume | 4 |
| 106 | `Incr Dollars, Yago` | `reported_incremental_dollars_yago` | provider_estimated_volume | 0 |
| 107 | `Incr Units` | `reported_incremental_pack_units` | provider_estimated_volume | 4 |
| 108 | `Incr Units, Yago` | `reported_incremental_pack_units_yago` | provider_estimated_volume | 0 |
| 109 | `Base ARP` | `reported_base_arp` | price | 4 |
| 110 | `Base ARP, Yago` | `reported_base_arp_yago` | price | 0 |
| 111 | `Base ARP, Promo` | `base_arp_promo` | price | 4 |
| 112 | `Base ARP, Promo, Yago` | `base_arp_promo_yago` | price | 0 |
| 113 | `ARP % Discount, Any Promo` | `arp_pct_discount_any_promo` | promotion_percentage | 4 |
| 114 | `ARP % Discount, Any Promo, Yago` | `arp_pct_discount_any_promo_yago` | promotion_percentage | 0 |
| 115 | `ARP, Promo` | `arp_promo` | price | 4 |
| 116 | `ARP, Promo, Yago` | `arp_promo_yago` | price | 0 |
| 117 | `ARP, Non-Promo` | `arp_non_promo` | price | 4 |
| 118 | `ARP, Non-Promo, Yago` | `arp_non_promo_yago` | price | 0 |
| 119 | `# of Stores` | `reported_universe_store_count` | distribution | 4 |
| 120 | `# of Stores, Yago` | `reported_universe_store_count_yago` | distribution | 4 |
| 121 | `# of Stores Selling` | `reported_selling_store_count` | distribution | 4 |
| 122 | `# of Stores Selling, Yago` | `reported_selling_store_count_yago` | distribution | 0 |
| 123 | `% of Stores Selling` | `reported_stores_selling_pct` | distribution | 4 |
| 124 | `% of Stores Selling, Yago` | `reported_stores_selling_pct_yago` | distribution | 0 |
| 125 | `Average Weekly Dollars Per Store Selling Per Item` | `average_weekly_dollars_per_store_selling_per_item` | velocity_or_weekly_average | 4 |
| 126 | `Average Weekly Dollars Per Store Selling Per Item, Yago` | `average_weekly_dollars_per_store_selling_per_item_yago` | velocity_or_weekly_average | 0 |
| 127 | `Average Weekly Units Per Store Selling Per Item` | `average_weekly_units_per_store_selling_per_item` | velocity_or_weekly_average | 4 |
| 128 | `Average Weekly Units Per Store Selling Per Item, Yago` | `average_weekly_units_per_store_selling_per_item_yago` | velocity_or_weekly_average | 0 |
| 129 | `Average Weekly Dollars` | `average_weekly_dollars` | velocity_or_weekly_average | 4 |
| 130 | `Average Weekly Dollars, Yago` | `average_weekly_dollars_yago` | velocity_or_weekly_average | 0 |
| 131 | `Average Weekly Dollars per Store Selling` | `average_weekly_dollars_per_store_selling` | velocity_or_weekly_average | 4 |
| 132 | `Average Weekly Dollars per Store Selling, Yago` | `average_weekly_dollars_per_store_selling_yago` | velocity_or_weekly_average | 0 |
| 133 | `Average Weekly Units` | `average_weekly_units` | velocity_or_weekly_average | 4 |
| 134 | `Average Weekly Units, Yago` | `average_weekly_units_yago` | velocity_or_weekly_average | 0 |
| 135 | `Average Weekly Units per Store Selling` | `average_weekly_units_per_store_selling` | velocity_or_weekly_average | 4 |
| 136 | `Average Weekly Units per Store Selling, Yago` | `average_weekly_units_per_store_selling_yago` | velocity_or_weekly_average | 0 |
| 137 | `Dollars per Store Selling` | `dollars_per_store_selling` | velocity_or_weekly_average | 4 |
| 138 | `Dollars per Store Selling, Yago` | `dollars_per_store_selling_yago` | velocity_or_weekly_average | 0 |
| 139 | `Dollars Per Store Selling Per Item` | `dollars_per_store_selling_per_item` | velocity_or_weekly_average | 4 |
| 140 | `Dollars Per Store Selling Per Item, Yago` | `dollars_per_store_selling_per_item_yago` | velocity_or_weekly_average | 0 |
| 141 | `Units per Store Selling` | `units_per_store_selling` | velocity_or_weekly_average | 4 |
| 142 | `Units per Store Selling, Yago` | `units_per_store_selling_yago` | velocity_or_weekly_average | 0 |
| 143 | `Units Per Store Selling Per Item` | `units_per_store_selling_per_item` | velocity_or_weekly_average | 4 |
| 144 | `Units Per Store Selling Per Item, Yago` | `units_per_store_selling_per_item_yago` | velocity_or_weekly_average | 0 |
| 145 | `Dollar ,% Lift, TPR` | `dollar_pct_lift_tpr` | promotion_tactic_lift | 4 |
| 146 | `Dollar ,% Lift, TPR, Yago` | `dollar_pct_lift_tpr_yago` | promotion_tactic_lift | 0 |
| 147 | `Dollar ,% Lift, Any Display` | `dollar_pct_lift_any_display` | promotion_tactic_lift | 1 |
| 148 | `Dollar ,% Lift, Any Display, Yago` | `dollar_pct_lift_any_display_yago` | promotion_tactic_lift | 0 |
| 149 | `Dollar ,% Lift, Any Feature` | `dollar_pct_lift_any_feature` | promotion_tactic_lift | 0 |
| 150 | `Dollar ,% Lift, Any Feature, Yago` | `dollar_pct_lift_any_feature_yago` | promotion_tactic_lift | 0 |
| 151 | `Dollar ,% Lift, Display Only` | `dollar_pct_lift_display_only` | promotion_tactic_lift | 1 |
| 152 | `Dollar ,% Lift, Display Only, Yago` | `dollar_pct_lift_display_only_yago` | promotion_tactic_lift | 0 |
| 153 | `Dollar ,% Lift, Feature & Display` | `dollar_pct_lift_feature_and_display` | promotion_tactic_lift | 0 |
| 154 | `Dollar ,% Lift, Feature & Display, Yago` | `dollar_pct_lift_feature_and_display_yago` | promotion_tactic_lift | 0 |
| 155 | `Dollar ,% Lift, Feature Only` | `dollar_pct_lift_feature_only` | promotion_tactic_lift | 0 |
| 156 | `Dollar ,% Lift, Feature Only, Yago` | `dollar_pct_lift_feature_only_yago` | promotion_tactic_lift | 0 |
| 157 | `Dollar ,% Lift, SPK` | `dollar_pct_lift_spk` | promotion_tactic_lift | 0 |
| 158 | `Dollar ,% Lift, SPK, Yago` | `dollar_pct_lift_spk_yago` | promotion_tactic_lift | 0 |
| 159 | `Units ,% Lift, Any Display` | `units_pct_lift_any_display` | promotion_tactic_lift | 1 |
| 160 | `Units ,% Lift, Any Display, Yago` | `units_pct_lift_any_display_yago` | promotion_tactic_lift | 0 |
| 161 | `Units ,% Lift, Any Feature` | `units_pct_lift_any_feature` | promotion_tactic_lift | 0 |
| 162 | `Units ,% Lift, Any Feature, Yago` | `units_pct_lift_any_feature_yago` | promotion_tactic_lift | 0 |
| 163 | `Units ,% Lift, Display Only` | `units_pct_lift_display_only` | promotion_tactic_lift | 1 |
| 164 | `Units ,% Lift, Display Only, Yago` | `units_pct_lift_display_only_yago` | promotion_tactic_lift | 0 |
| 165 | `Units ,% Lift, Feature Only` | `units_pct_lift_feature_only` | promotion_tactic_lift | 0 |
| 166 | `Units ,% Lift, Feature Only, Yago` | `units_pct_lift_feature_only_yago` | promotion_tactic_lift | 0 |
| 167 | `Units ,% Lift, Feature & Display` | `units_pct_lift_feature_and_display` | promotion_tactic_lift | 0 |
| 168 | `Units ,% Lift, Feature & Display, Yago` | `units_pct_lift_feature_and_display_yago` | promotion_tactic_lift | 0 |
| 169 | `Units ,% Lift, SPK` | `units_pct_lift_spk` | promotion_tactic_lift | 0 |
| 170 | `Units ,% Lift, SPK, Yago` | `units_pct_lift_spk_yago` | promotion_tactic_lift | 0 |
| 171 | `Units ,% Lift, TPR` | `units_pct_lift_tpr` | promotion_tactic_lift | 4 |
| 172 | `Units ,% Lift, TPR, Yago` | `units_pct_lift_tpr_yago` | promotion_tactic_lift | 0 |
| 173 | `ARP % Discount, Any Display` | `arp_pct_discount_any_display` | promotion_percentage | 1 |
| 174 | `ARP % Discount, Any Display, Yago` | `arp_pct_discount_any_display_yago` | promotion_percentage | 0 |
| 175 | `ARP % Discount, Any Feature` | `arp_pct_discount_any_feature` | promotion_percentage | 0 |
| 176 | `ARP % Discount, Any Feature, Yago` | `arp_pct_discount_any_feature_yago` | promotion_percentage | 0 |
| 177 | `ARP % Discount, Display Only` | `arp_pct_discount_display_only` | promotion_percentage | 1 |
| 178 | `ARP % Discount, Display Only, Yago` | `arp_pct_discount_display_only_yago` | promotion_percentage | 0 |
| 179 | `ARP % Discount, Feature & Display` | `arp_pct_discount_feature_and_display` | promotion_percentage | 0 |
| 180 | `ARP % Discount, Feature & Display, Yago` | `arp_pct_discount_feature_and_display_yago` | promotion_percentage | 0 |
| 181 | `ARP % Discount, Feature Only` | `arp_pct_discount_feature_only` | promotion_percentage | 0 |
| 182 | `ARP % Discount, Feature Only, Yago` | `arp_pct_discount_feature_only_yago` | promotion_percentage | 0 |
| 183 | `ARP % Discount, TPR Only` | `arp_pct_discount_tpr_only` | promotion_percentage | 4 |
| 184 | `ARP % Discount, TPR Only, Yago` | `arp_pct_discount_tpr_only_yago` | promotion_percentage | 0 |
| 185 | `ARP % Discount, SPK` | `arp_pct_discount_spk` | promotion_percentage | 0 |
| 186 | `ARP % Discount, SPK, Yago` | `arp_pct_discount_spk_yago` | promotion_percentage | 0 |
| 187 | `Base ARP, Any Display` | `base_arp_any_display` | price | 1 |
| 188 | `Base ARP, Any Display, Yago` | `base_arp_any_display_yago` | price | 0 |
| 189 | `Base ARP, Any Feature` | `base_arp_any_feature` | price | 0 |
| 190 | `Base ARP, Any Feature, Yago` | `base_arp_any_feature_yago` | price | 0 |
| 191 | `Base ARP, Display Only` | `base_arp_display_only` | price | 1 |
| 192 | `Base ARP, Display Only, Yago` | `base_arp_display_only_yago` | price | 0 |
| 193 | `Base ARP, Feature & Display` | `base_arp_feature_and_display` | price | 0 |
| 194 | `Base ARP, Feature & Display, Yago` | `base_arp_feature_and_display_yago` | price | 0 |
| 195 | `Base ARP, Feature Only` | `base_arp_feature_only` | price | 0 |
| 196 | `Base ARP, Feature Only, Yago` | `base_arp_feature_only_yago` | price | 0 |
| 197 | `Base ARP, SPK` | `base_arp_spk` | price | 0 |
| 198 | `Base ARP, SPK, Yago` | `base_arp_spk_yago` | price | 0 |
| 199 | `Base ARP, TPR` | `base_arp_tpr` | price | 4 |
| 200 | `Base ARP, TPR, Yago` | `base_arp_tpr_yago` | price | 0 |
| 201 | `ARP, Any Display` | `arp_any_display` | price | 1 |
| 202 | `ARP, Any Display, Yago` | `arp_any_display_yago` | price | 0 |
| 203 | `ARP, Any Feature` | `arp_any_feature` | price | 0 |
| 204 | `ARP, Any Feature, Yago` | `arp_any_feature_yago` | price | 0 |
| 205 | `ARP, Display Only` | `arp_display_only` | price | 1 |
| 206 | `ARP, Display Only, Yago` | `arp_display_only_yago` | price | 0 |
| 207 | `ARP, Feature & Display` | `arp_feature_and_display` | price | 0 |
| 208 | `ARP, Feature & Display, Yago` | `arp_feature_and_display_yago` | price | 0 |
| 209 | `ARP, Feature Only` | `arp_feature_only` | price | 0 |
| 210 | `ARP, Feature Only, Yago` | `arp_feature_only_yago` | price | 0 |
| 211 | `ARP, SPK` | `arp_spk` | price | 0 |
| 212 | `ARP, SPK, Yago` | `arp_spk_yago` | price | 0 |
| 213 | `ARP, TPR` | `arp_tpr` | price | 4 |
| 214 | `ARP, TPR, Yago` | `arp_tpr_yago` | price | 0 |

## 10. Sources and limits

**S1 — Uploaded `head.csv`.** Exact 214-column header at physical line 1; four records at physical lines 2–5. SHA-256: `bd5d07e897bd2b0bcc6f96102520c9e2aece4a63aace9fa87353ee41fe9a945c`. The header supports presence/absence mappings; sample arithmetic does not establish full-history completeness, projection methodology, or causal validity.

**S2 — SPINS, Dollars.** https://www.spins.com/cpg-learning-center/glossary/dollars/ — retail dollar-sales meaning.

**S3 — SPINS, Units.** https://www.spins.com/cpg-learning-center/glossary/units/ — a unit is the sellable package represented by the barcode.

**S4 — SPINS, Total Distribution Points.** https://www.spins.com/cpg-learning-center/glossary/tdp/ — TDP is not store count and combines item distribution contributions.

**S5 — SPINS, Price Elasticity.** https://www.spins.com/cpg-learning-center/glossary/price-elasticity/ — demand sensitivity to price. The model architecture in this specification is an Aevah design proposal, not a claim that the CSV already contains elasticity.

**S6 — SPINS, Product Universe.** https://www.spins.com/cpg-learning-center/glossary/product-universe/ — TPL means Total Product Library, a product universe rather than an export-completeness guarantee.

**S7 — Circana, Competitive Retailer Marketing Area.** https://www.circana.com/liquid-data-go/cpg-dictionary/competitive-retailer-marketing-area-%28crma%29 — competitive scope includes the retailer and surrounding competitors. Exact application to this SPINS export requires the source geography dictionary.

**S8 — Circana, Retailer Marketing Area.** https://www.circana.com/liquid-data-go/cpg-dictionary/retailer-marketing-area-%28rma%29 — planning-area definition; source-specific account scope still needs confirmation.

The public references support general metric meanings, not every contractual SPINS fact. Exact definitions for equivalent units, store-universe scope, baseline-price construction, tactic-lift denominators, SPM/SPP, Weight Weeks and SPK were not established from the available material. Those fields are retained with explicit definition gates rather than assigned unsupported formulas.

No company-wide totals, predictive results, elasticity estimates, cannibalization results or trade liabilities were computed from these four unrelated rows. All formulas beyond the sample checks are specifications for implementation against the full appropriate datasets.
