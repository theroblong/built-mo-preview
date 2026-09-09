# Aevah — Packaged Experiences by Use Case (v2)

## What changed from v1

- Each numbered use case is now a **packaged experience**: name, owner, cadence, grain, data basis, visibility rules, tabs, user actions, and outputs to other packages — not a datapoint list.
- **Sell-in vs. sell-through** made explicit. Sales sees both; Production/Procurement plan on shipment units only; BI/Marketing work on consumption/syndicated data.
- **Forecast versioning** is a platform primitive. Planning packages (2, 3, 4, 5) lock to a named version; insight packages (1, 6, 7) view latest and push overrides upstream.
- **Shared engines** identified with an experience × engine matrix, so cannibalization and elasticity are built once and rendered three ways.
- **KPI rankings revisited**; changes are noted per package.
- **Part 2 added:** KPI spec sheet (formula, source, grain, lag, aggregation) for all 54 KPIs, plus cross-package reconciliation rules and canonical definitions.

---

## Shared foundation (platform layer, not per-experience)

| Engine | What it does |
|---|---|
| **E1 Demand Forecast** | Consumption → shipment forecast by customer × SKU × week; versioned; confidence bands; override log |
| **E2 Price & Portfolio** | Own-price elasticity, cross-elasticity/cannibalization matrix, scenario runner (price, launch, delist) |
| **E3 Promo & Trade** | Baseline/lift decomposition, incrementality, trade cost by mechanic, accrual schedule with timing lag |
| **E4 Competitive Intelligence** | Syndicated share, distribution, price index, competitor launches, definable competitor sets |
| **E5 Supply Translation** | BOM explosion, UoM conversion (bars → cases → pallets → line hours), capacity model, lead times/MOQs |
| **E6 Trust & Governance** | Forecast accuracy/bias by lag, forecast churn, data freshness, version control, role-based masking |

### Experience × engine matrix

| Experience | E1 Demand | E2 Price/Portfolio | E3 Promo/Trade | E4 Competitive | E5 Supply | E6 Trust |
|---|---|---|---|---|---|---|
| 1 Customer Growth | Full (customer grain) | — | Trade $ by customer | Distribution only | — | Accuracy by customer |
| 2 Build Plan | Shipment units, masked | — | Demand events (timing only) | — | UoM + capacity | Accuracy/bias/churn by SKU |
| 3 Material Plan | Shipment units, masked | — | — | — | BOM + lead time | Delta vs. prior version |
| 4 Plan & Scenario | $ rolled to P&L | Full | Trade % of gross | Category context | Capacity threshold | Cycle accuracy |
| 5 Trade Accrual Planner | Gross $ base | — | Full (accrual + timing) | — | — | Accrual variance |
| 6 Analytics Workbench | Consumption grain | Method-level | Full (post-mortem) | Full | — | Model health, data ops |
| 7 Brand & Launch | Item grain + launch inputs | Item-level curves | Lift summary | Launches + price | — | — |

### Cross-package flow

BI + Marketing (consumption insight, launch plans) → **E1** → Sales (customer overrides, distribution events) → **version lock** → Finance / Accounting / Production → Procurement (BOM explosion).

---

## 1. Sales — "Customer Growth"

**Need:** Gross and net sales by customer, historical and forecast; store count.

| | |
|---|---|
| **Users** | Sales leadership, key account managers |
| **Cadence** | Weekly review; monthly forecast cycle; JBP / line-review prep |
| **Data basis** | Sell-in $ (gross, net) **and** sell-through (POS units, velocity) |
| **Grain** | Customer × SKU × month; 3 yrs history, 12–18 months forecast |
| **Version behavior** | Latest; overrides submitted with reason code, versioned into E1 |
| **Visibility** | Full customer detail, trade $ at customer level. Masked: COGS, BOM |

**Tabs:** Book of Business (all customers) · Customer Scorecard (one customer) · Distribution Tracker (doors, TDP, wins/losses) · Gross-to-Net Bridge

**Actions:** Override customer forecast · log distribution wins/losses/delists · tag risks and opportunities · export to JBP deck

**Outputs:** Overrides and distribution events → E1 → Production, Finance

**Primary:** Gross and net sales by customer (actual + forecast); store count / distribution and change events; forecast vs. commitment.
**Supporting:** Units; trade $ by customer; velocity; SKU mix per customer; promo calendar; sell-in vs. sell-through gap; prior forecast version.
**Extraneous:** BOM/COGS, production schedule, competitor SKU detail, capex, elasticity curves.

| # | KPI | Why this rank |
|---|---|---|
| 1 | Net sales by customer (actual + forecast) | What reps are measured on; the number every conversation ends at. |
| 2 | Gross sales / gross-to-net bridge | Separates demand from trade decisions; shows what was spent to get to net. |
| 3 | Distribution: doors/TDP and change events (wins, losses, delists) | Leading indicator of next quarter; the lever reps directly control. *Revised: change events added — a static store count hides the story.* |
| 4 | Forecast vs. commitment | *Moved up from 6.* Sales owns overrides, so weekly review is about variance to what they committed. |
| 5 | Sell-in vs. sell-through gap | *New.* Shipments ahead of POS = retailer inventory build = future order cut. The earliest warning available. |
| 6 | Velocity | Distinguishes growth from more doors vs. more demand per door. |
| 7 | YoY growth % | Standard comp; derivative of 1–2. |
| 8 | Trade rate (1 − net/gross) | Explains the gap; Accounting owns the detail. |

---

## 2. Production — "Build Plan"

**Need:** Future bars sold by SKU to plan production. No retailer data.

| | |
|---|---|
| **Users** | Production planners, plant scheduling |
| **Cadence** | Weekly for 0–13 weeks (frozen / slushy / liquid buckets); monthly for 3–18 months |
| **Data basis** | **Shipment** units (not consumption), converted bars → cases → pallets → line hours |
| **Grain** | SKU × week |
| **Version behavior** | Locked to a named forecast version; changes inside the frozen window flagged |
| **Visibility** | Masked: customer, retailer, price, $, trade, competitors. Promo spikes shown as "demand events" with timing and magnitude only |

**Tabs:** Demand Signal (SKU × week with bands) · Net Requirements · Line Load & Capacity · Forecast Health

**Actions:** Acknowledge version · set safety stock policy per SKU · flag capacity constraints to Sales/Finance · publish build plan

**Outputs:** Build plan → Procurement (timing) · capacity flags → Finance capex trigger

**Primary:** Forecast units by SKU × week; net production requirement (forecast − on-hand − WIP − scheduled); line load / capacity utilization.
**Supporting:** Confidence bands; demand events (timing/magnitude, anonymized); safety stock targets; shelf-life constraints; changeover groupings; SKU lifecycle (launch/discontinue dates); prior-version delta.
**Extraneous (masked):** Customer names, prices, $ sales, trade, competitor data, elasticity.

| # | KPI | Why this rank |
|---|---|---|
| 1 | Forecast units by SKU × week (shipment basis) | The reason the view exists. Must be shipment basis or the plan is offset by retailer inventory. |
| 2 | Net production requirement | Turns demand into a build decision. |
| 3 | Line load / capacity utilization | *Moved up from 4.* If it isn't producible, nothing downstream matters. |
| 4 | Forecast accuracy (wMAPE at planning lag, e.g., 4-week-ahead) | *Revised to lag-based.* Accuracy at the horizon they actually plan on sets safety stock. |
| 5 | Forecast bias | Noisy vs. consistently wrong need different fixes. |
| 6 | Days of supply / stock-out and expiry risk | Fast read on what's at risk. |
| 7 | Forecast churn inside frozen window | *New.* Planners need stability; a forecast that moves inside the frozen horizon is a process failure, not a demand signal. |
| 8 | Schedule adherence | Backward-looking; useful but not why they open the page. |

---

## 3. Procurement — "Material Plan"

**Need:** Future bars sold by SKU to plan raw material purchases.

| | |
|---|---|
| **Users** | Buyers, supply planners |
| **Cadence** | Weekly ordering; monthly for contracts and commodity positions |
| **Data basis** | Shipment units → BOM explosion → ingredient and packaging requirements, lead-time offset |
| **Grain** | Material × week |
| **Version behavior** | Locked to the same version as Production |
| **Visibility** | Masked as Production; sees SKU forecast only as drill-down to explain a material requirement |

**Tabs:** Material Requirements (ingredients + packaging × week) · Coverage & Order Board · Shared-Ingredient Exposure · Cost Watch

**Actions:** Accept/adjust requirements · generate PO recommendations · maintain MOQ/lead time · flag supply risk back to Production

**Outputs:** PO recommendations → ERP · supply risk → Build Plan

**Primary:** Material requirement by ingredient/packaging × period, net of on-hand and open POs; order-by dates.
**Supporting:** SKU drill-down per material; supplier lead times and MOQs; commodity price trends; confidence bands; upcoming launches introducing new materials; prior-version delta.
**Extraneous:** Customer detail, net sales, trade, competitors, store counts, promo mechanics.

| # | KPI | Why this rank |
|---|---|---|
| 1 | Material requirement by ingredient/packaging × period | Core translation of demand into buys. |
| 2 | Coverage (on hand + open PO vs. requirement) | Turns requirement into action: buy or don't. |
| 3 | Order-by date / lead-time risk | A requirement that can't be met in time is a production stop. |
| 4 | Forecast delta vs. prior version (in material units) | Procurement lives on change since the last order. |
| 5 | Shared-ingredient exposure | *New.* Materials feeding many SKUs concentrate risk but also pool forecast error — both matter for how much buffer to hold. |
| 6 | Cost per unit / commodity index | Timing and hedging; secondary to availability. |
| 7 | MOQ / over-buy exposure | Forecast uncertainty × MOQ = waste risk. |
| 8 | Supplier OTIF | Supplier management, not planning. |

---

## 4. Finance — "Plan & Scenario"

**Need:** Feed internal forecasts and capex planning; cannibalization and price elasticity.

| | |
|---|---|
| **Users** | FP&A, CFO |
| **Cadence** | Monthly cycle; quarterly re-plan; annual AOP |
| **Data basis** | Sell-in $ (gross, net), margin from BOM cost, trade % |
| **Grain** | SKU × customer × month rolled to P&L lines; 12–36 months |
| **Version behavior** | Locks a version as "plan feed"; scenarios branch from it and are compared, never overwrite |
| **Visibility** | Full |

**Tabs:** Revenue Forecast Feed (versioned export) · Gross-to-Net Waterfall · Scenario Studio (price, launch, delist, promo intensity) · Portfolio Net Growth (cannibalization-adjusted) · Capacity & Capex Trigger

**Actions:** Lock plan version · run and compare scenarios · export to FP&A/ERP · set capacity thresholds that trigger capex review

**Outputs:** Forecast feed → FP&A system · capex trigger memo · plan version → Accounting

**Primary:** Net and gross revenue forecast by period (drillable); contribution margin by SKU; elasticity curves; cannibalization matrix; volume vs. capacity trajectory.
**Supporting:** Trade $ forecast; scenario deltas; forecast vs. budget/AOP; cycle-level forecast accuracy; category growth context.
**Extraneous:** Store-level detail, promo mechanics, weekly retailer POS, competitor brand detail.

| # | KPI | Why this rank |
|---|---|---|
| 1 | Net revenue forecast vs. budget/AOP | Feeds the P&L; everything else is an input. |
| 2 | Contribution margin by SKU | Volume without margin is a capex mistake waiting to happen. |
| 3 | Price elasticity and revenue-optimal price | Direct lever on top line and margin; the highest-value model output for Finance. |
| 4 | Net incremental volume (post-cannibalization) | Prevents planning on gross launch volume that's stolen from existing SKUs. |
| 5 | Scenario delta vs. base (revenue and margin) | *New.* The scenario studio is only useful if the delta is a first-class number. |
| 6 | Capacity utilization trajectory / capex trigger date | The explicit capex use case; matters when it matters. |
| 7 | Forecast accuracy and bias (cycle-level) | How much to trust 1–6. |
| 8 | Trade as % of gross | Accounting owns the detail. |

---

## 5. Accounting — "Trade Accrual Planner"

**Need:** Plan future trade expense by customer.

| | |
|---|---|
| **Users** | Revenue accounting, controller |
| **Cadence** | Monthly close; quarterly review |
| **Data basis** | Trade $ by mechanic (off-invoice, bill-back, scan, slotting, MDF), gross $ base |
| **Grain** | Customer × month × trade type; mapped to GL accounts; promo period vs. deduction period |
| **Version behavior** | Locked to Finance's plan version |
| **Visibility** | Full customer and trade detail. Masked: COGS, BOM |

**Tabs:** Accrual Schedule · Promo Calendar Driver · Accrual vs. Actual Reconciliation · Deduction Aging · GL Mapping

**Actions:** Approve accrual amounts · adjust rates · map to GL · export journal entries · match deductions to promos

**Outputs:** Journal entries → GL · accrual variance → E3 (improves next cycle)

**Primary:** Forecast trade expense by customer × period × mechanic; accrual vs. actual deductions; open deduction balance.
**Supporting:** Promo calendar by customer; gross $ forecast (rate base); contracted rates/terms; historical trade rate; deduction aging; promo→deduction timing lag.
**Extraneous:** Elasticity, cannibalization, competitors, production, materials, store counts.

| # | KPI | Why this rank |
|---|---|---|
| 1 | Forecast trade expense by customer × period × mechanic | The accrual; the stated need. |
| 2 | Trade rate % of gross by customer | Sanity check on #1 and the auditor explanation. |
| 3 | Accrual vs. actual variance | Whether last period's accrual was right. |
| 4 | Promo → deduction timing lag | *New.* Determines *when* the liability hits, not just how much — the most common source of close-cycle surprises. |
| 5 | Open / unapplied deductions and aging | Cash and close exposure. |
| 6 | Period-end trade liability | Balance-sheet view. |
| 7 | Deduction resolution cycle time | Process health. |

---

## 6. BI — "Analytics Workbench"

**Need:** Competitor performance, incrementality, promo effectiveness, cannibalization.

| | |
|---|---|
| **Users** | BI / analytics; also stewards of the models |
| **Cadence** | Ad hoc + monthly post-mortems |
| **Data basis** | Consumption / syndicated (POS, panel), competitor sets defined by BI |
| **Grain** | SKU × retailer × week; category and segment |
| **Version behavior** | Latest + experimental branches; publishes findings to Marketing and Finance |
| **Visibility** | Full, including model internals |

**Tabs:** Competitive Landscape (share, distribution, price vs. defined sets) · Promo Post-Mortem (baseline / lift / ROI) · Incrementality Lab (promo, distribution, launch) · Cannibalization Matrix · Model Health & Data Ops

**Actions:** Define competitor sets · run baselines · publish findings · monitor model drift · manage data feeds and freshness

**Outputs:** Findings → Marketing, Finance · model health → E6 · competitor sets → E4

**Primary:** Market share vs. competitor sets; promo incrementality and ROI; cannibalization matrix; price gap vs. competitors.
**Supporting:** Distribution vs. competitors; baseline velocity trend; promo depth/frequency; halo effects; model diagnostics; data freshness/coverage.
**Extraneous:** Production, procurement, accruals, capacity.

| # | KPI | Why this rank |
|---|---|---|
| 1 | Incremental volume and ROI per promo | Most actionable output; changes what gets funded next. |
| 2 | Share and share change vs. defined sets | The scoreboard. |
| 3 | Cannibalization rate (source of volume) | Separates real growth from reshuffling. |
| 4 | Baseline velocity trend | Brand health with promo noise removed. |
| 5 | Price index vs. competitors | Explains share moves; feeds elasticity. |
| 6 | Distribution (TDP) vs. competitors | Explains share moves from the other side. |
| 7 | Model accuracy / drift and data freshness | BI owns credibility of the whole platform's numbers. |

---

## 7. Marketing — "Brand & Launch"

**Need:** Cannibalization, price elasticity, competition, general trends by item; launch information.

| | |
|---|---|
| **Users** | Brand managers, innovation |
| **Cadence** | Weekly during launches; monthly otherwise |
| **Data basis** | Consumption by item; category and segment trends |
| **Grain** | Item × week; category / segment |
| **Version behavior** | Latest; launch plans are inputs to E1 |
| **Visibility** | Item and category detail. Masked: trade $, customer-level net sales |

**Tabs:** Item Trends · Launch Command Center (pre-launch: forecast + expected cannibalization; post-launch: distribution ramp, velocity vs. benchmark, repeat) · Pricing Lens (elasticity by item) · Competitor Watch · Category Trends

**Actions:** Create launch plans (forecast input) · set launch benchmarks · request promo analyses from BI · compare price scenarios

**Outputs:** Launch plans → E1 → Production, Procurement, Finance

**Primary:** Item-level trend (sales, share, velocity); elasticity by item; competitor launches and price moves; cannibalization for launch planning; launch tracker.
**Supporting:** Segment/consumer trends (flavor, protein, format); promo effectiveness summary from BI; regional differences; search/social signals if available.
**Extraneous:** Accruals, production schedule, raw materials, customer-level net sales.

| # | KPI | Why this rank |
|---|---|---|
| 1 | Launch performance vs. benchmark (distribution ramp, velocity, repeat) | Launches are the biggest bets and hardest to read early. |
| 2 | Net incremental contribution (post-cannibalization) | Proves the launch grew the franchise. |
| 3 | Share of category / segment | Whether the brand is winning where it competes. |
| 4 | Price elasticity by item | Informs item-level pricing and promo strategy. |
| 5 | Velocity trend by item | Portfolio health; invest vs. rationalize. |
| 6 | Competitor launch and price activity | Context for 1–5. |
| 7 | Category / segment trend | *New.* Where growth is happening tells Marketing where to launch next, not just how current items are doing. |
| 8 | Promo lift | Consumed as a summary from BI. |

---

## Packaging summary

| # | Experience | Data basis | Grain | Version behavior | Masked |
|---|---|---|---|---|---|
| 1 | Customer Growth | Sell-in $ + sell-through | Customer × SKU × month | Latest; can override | Costs, BOM |
| 2 | Build Plan | Shipment units | SKU × week | Locked | Customer, price, $, retailer |
| 3 | Material Plan | Shipment → BOM | Material × week | Locked | Same as Production |
| 4 | Plan & Scenario | Sell-in $, margin | SKU × customer × month → P&L | Locked as plan; scenarios branch | None |
| 5 | Trade Accrual Planner | Trade $ | Customer × month × mechanic | Locked | Costs, BOM |
| 6 | Analytics Workbench | Consumption / syndicated | SKU × retailer × week | Latest + experimental | None |
| 7 | Brand & Launch | Consumption | Item × week | Latest | Trade $, customer net sales |

## Design implications

- **One engine, three renderings** for cannibalization and elasticity: Finance wants the number, BI wants the method, Marketing wants the item story.
- **Forecast trust is platform-level.** Accuracy, bias, churn, and freshness appear in six of seven packages; make E6 a shared surface, not a per-app metric.
- **Masking is a feature, not a filter.** Production and Procurement consume the same forecast as Sales but must never see customer or price dimensions; this is a role/data-model rule, not a UI hide.
- **Versioning is the contract between packages.** Insight packages propose; planning packages lock; the version ID is what makes the seven experiences agree.

---
---

# Part 2 — KPI Spec Sheet

One row per KPI across all seven packages. IDs: S = Sales, P = Production, M = Material/Procurement, F = Finance, A = Accounting, B = BI, K = Marketing. "Source" is the data domain, not a system name. "Lag" is the forecast horizon or comparison basis where relevant.

## Canonical definitions (used everywhere)

| Term | Definition |
|---|---|
| **Gross sales** | Shipped units × invoice list price, before any deductions |
| **Net sales** | Gross − trade deductions (off-invoice, bill-back, scan, slotting, MDF) − returns/allowances |
| **Shipment units** | Units leaving our dock to a customer (sell-in). Basis for Production, Procurement, Finance $ |
| **Consumption units** | Units scanned at retail (sell-through, POS/syndicated). Basis for BI, Marketing, velocity, share |
| **Baseline** | Modeled non-promoted demand (E3). Lift = actual − baseline |
| **Velocity** | Units (or $) ÷ (stores selling × weeks); always weighted, never an average of averages |
| **TDP / ACV** | Total distribution points (Σ item ACV%); ACV = % of category-weighted all-commodity volume where item is present |
| **wMAPE at lag k** | Σ\|actual − forecast_k\| ÷ Σ actual, where forecast_k is the version published k periods before the actual |
| **Bias** | Σ(forecast − actual) ÷ Σ actual, signed |
| **Version** | A named, immutable forecast snapshot (e.g., `2026-09 v3`). Locked packages read one version; latest packages read the newest |
| **Frozen window** | Horizon (e.g., weeks 0–4) in which the plan is not expected to change |

## 1. Sales — Customer Growth

| ID | KPI | Formula / definition | Source | Grain | Lag / basis | Aggregation | Engine |
|---|---|---|---|---|---|---|---|
| S1 | Net sales by customer | Gross − all trade deductions − returns (actual); forecast = E1 units × price × (1 − trade rate) | ERP invoices; E1 + E3 | Customer × SKU × month | Actual at close; forecast 12–18 mo | Sum | E1, E3 |
| S2 | Gross sales / G2N bridge | Shipped units × list price; bridge = gross − each deduction type → net | ERP; E3 | Customer × SKU × month | Same as S1 | Sum per bridge step | E1, E3 |
| S3 | Distribution & change events | Store count = distinct stores scanning in period (POS) or authorized doors; TDP per canonical; events = logged wins/losses/delists with effective date | POS/syndicated; Sales-entered authorizations | Customer × SKU × week | Current + effective-dated future | Count (stores); Σ (TDP); list (events) | E1 input, E4 |
| S4 | Forecast vs. commitment | (Current version net $ − committed net $) ÷ committed; committed = version locked at cycle start | E1 versions | Customer × month | Current vs. cycle-start version | Ratio on sums | E1, E6 |
| S5 | Sell-in vs. sell-through gap | Shipment units − POS units, trailing 4 and 13 wks; implied retailer weeks of supply = est. retailer inventory ÷ avg weekly POS | ERP shipments; POS | Customer × SKU × week | Trailing | Difference on sums; WoS ratio | E1 |
| S6 | Velocity | POS $ (or units) ÷ (stores selling × weeks) | POS/syndicated | Customer × SKU × week | Trailing 4/13/52 | Weighted by store-weeks | E4 |
| S7 | YoY growth | (Net sales period ÷ net sales same period LY) − 1 | S1 | Customer × month | Same period LY | Ratio on sums | — |
| S8 | Trade rate | Total trade $ ÷ gross $ = 1 − net ÷ gross | E3; ERP | Customer × month | Same as S1 | Ratio on sums | E3 |

## 2. Production — Build Plan

| ID | KPI | Formula / definition | Source | Grain | Lag / basis | Aggregation | Engine |
|---|---|---|---|---|---|---|---|
| P1 | Forecast units by SKU × week | Locked-version shipment forecast Σ across customers; expressed as bars, cases, pallets via UoM table | E1 (locked); E5 UoM | SKU × week | 0–13 wks weekly, 3–18 mo monthly | Sum across customers (customer masked) | E1, E5 |
| P2 | Net production requirement | Projected: forecast − available on-hand − WIP − scheduled receipts + safety stock target, per bucket, cumulative | E1; ERP inventory; MES | SKU × week | Same as P1 | Cumulative projection | E5 |
| P3 | Line load / capacity utilization | (Σ forecast units ÷ line rate + changeover hours) ÷ available hours | E5 capacity model; P1 | Line × week | Same as P1 | Ratio | E5 |
| P4 | Forecast accuracy (wMAPE at lag 4) | Σ\|actual − forecast_4wk\| ÷ Σ actual, trailing 13 wks | E1 versions; ERP actual shipments | SKU × week | 4-week lag | Weighted by actual units | E6 |
| P5 | Forecast bias | Σ(forecast_4wk − actual) ÷ Σ actual, signed | Same as P4 | SKU × week | 4-week lag | Weighted | E6 |
| P6 | Days of supply / expiry risk | (On-hand + scheduled) ÷ avg daily forecast next 8 wks; expiry risk = units with remaining shelf life below customer minimum | ERP lot data; P1 | SKU | Forward 8 wks | Ratio; count | E5 |
| P7 | Forecast churn (frozen window) | Σ\|version_n − version_n−1\| ÷ Σ version_n−1, within weeks 0–4 | E1 versions | SKU × week | Version-over-version | Weighted | E6 |
| P8 | Schedule adherence | Produced units on plan ÷ planned units | MES | Line × week | Trailing | Ratio | — |

## 3. Procurement — Material Plan

| ID | KPI | Formula / definition | Source | Grain | Lag / basis | Aggregation | Engine |
|---|---|---|---|---|---|---|---|
| M1 | Material requirement | Σ_SKU (P1 units × BOM qty per unit × (1 + scrap%)), placed at need week | E5 BOM; P1 | Material × week | Same horizon as P1 | Sum across SKUs | E5 |
| M2 | Coverage (weeks) | (On-hand + open PO) ÷ avg weekly M1 over next 8 wks | ERP inventory & POs; M1 | Material | Forward 8 wks | Ratio | E5 |
| M3 | Order-by date / lead-time risk | Order-by = need date − supplier lead time − receiving/QA days; at-risk = requirements with order-by ≤ today + X days and no PO | M1; supplier master | Material × requirement | Forward | Date; count and $ at risk | E5 |
| M4 | Delta vs. prior version | M1_v(n) − M1_v(n−1), units and % | E1 versions via E5 | Material × week | Version-over-version | Difference on sums | E6 |
| M5 | Shared-ingredient exposure | # SKUs consuming material; % of demand from top SKU; pooled forecast CV vs. mean single-SKU CV | E5 BOM; E1 bands | Material | Current | Count; ratio | E5, E6 |
| M6 | Cost per unit / commodity index | PO-weighted avg price; external index rebased to 100 | ERP POs; market feed | Material × month | Trailing 12 mo | Weighted avg | — |
| M7 | MOQ / over-buy exposure | Where MOQ > requirement in lead-time window: (MOQ − requirement) × unit cost, flagged if material shelf life < consumption horizon | M1; supplier master | Material | Forward | Sum $ | E5 |
| M8 | Supplier OTIF | POs received on time and in full ÷ POs due | ERP receipts | Supplier × month | Trailing | Ratio | — |

## 4. Finance — Plan & Scenario

| ID | KPI | Formula / definition | Source | Grain | Lag / basis | Aggregation | Engine |
|---|---|---|---|---|---|---|---|
| F1 | Net revenue vs. budget/AOP | Plan-version net $ (S1 rolled to P&L lines) − budget | E1 locked; budget | SKU × customer × month → P&L line | Plan horizon 12–36 mo | Sum; variance | E1, E3 |
| F2 | Contribution margin by SKU | Net sales − COGS (BOM cost + conversion) − variable logistics; per unit and total | ERP standard cost; E5 BOM; F1 | SKU × month | Same as F1 | Sum; per-unit weighted | E5 |
| F3 | Price elasticity / optimal price | ε = %Δ units ÷ %Δ price, estimated from POS with promo and distribution controls; optimal price = argmax_p units(p) × margin(p) | E2 | SKU (and customer where data allows) | Trailing 104 wks estimation | Model output | E2 |
| F4 | Net incremental volume | Launch volume − Σ cannibalized volume from existing SKUs (source-of-volume matrix), in units and net $ | E2 cross-elasticity; E3 | Launch item × month | Launch horizon | Sum | E2, E3 |
| F5 | Scenario delta vs. base | Scenario net $ − base net $; scenario margin − base margin, over horizon | E2 scenarios; F1, F2 | Scenario × month | Plan horizon | Sum | E2 |
| F6 | Capacity trajectory / capex trigger | P3 rolled to month; trigger date = first month utilization > threshold for N consecutive months | E5; P3 | Line × month | Plan horizon | Max/avg per month | E5 |
| F7 | Cycle forecast accuracy | \|actual net $ − plan-version net $\| ÷ actual at plan lag (quarter-ahead); plus bias | E1 versions; ERP | Consolidated and by P&L line | Quarter-ahead | Weighted by $ | E6 |
| F8 | Trade % of gross | A2 rolled up | E3 | Consolidated × month | Same as F1 | Ratio on sums | E3 |

## 5. Accounting — Trade Accrual Planner

| ID | KPI | Formula / definition | Source | Grain | Lag / basis | Aggregation | Engine |
|---|---|---|---|---|---|---|---|
| A1 | Forecast trade expense | Σ (gross $ forecast × contracted rate by mechanic) + scheduled fixed programs (slotting, MDF), recognized in the promo-activity period | E3; contracts; promo calendar; S2 | Customer × month × mechanic | Plan version | Sum | E3 |
| A2 | Trade rate by customer | A1 ÷ gross $ | A1; S2 | Customer × month | Same | Ratio on sums | E3 |
| A3 | Accrual vs. actual variance | Actual deductions matched to period − accrual for that period | A1; deduction ledger | Customer × month × mechanic | Post-close | Difference | E3, E6 |
| A4 | Promo → deduction timing lag | Median days from promo end date to deduction post date | Promo calendar; deduction ledger | Customer × mechanic | Trailing 12 mo | Median | E3 |
| A5 | Open deductions & aging | Unmatched deduction balance in buckets 0–30 / 31–60 / 61–90 / 90+ | Deduction ledger | Customer | Current | Sum per bucket | — |
| A6 | Period-end trade liability | Cumulative accrual − cumulative settled deductions | A1; ledger | Customer; consolidated | Period end | Sum | E3 |
| A7 | Deduction resolution cycle time | Median days from post to resolution (matched, repaid, written off) | Deduction ledger | Customer × mechanic | Trailing | Median | — |

## 6. BI — Analytics Workbench

| ID | KPI | Formula / definition | Source | Grain | Lag / basis | Aggregation | Engine |
|---|---|---|---|---|---|---|---|
| B1 | Promo incrementality & ROI | Incremental units = actual − baseline over promo window; lift % = incremental ÷ baseline; ROI = (incremental net margin − promo cost incl. trade) ÷ promo cost | E3; POS; A1 actuals | Promo event (SKU × retailer × window) | Per event; post-window | Sum; ratio | E3 |
| B2 | Share & share change | Brand $ (or units) ÷ competitor-set $; change in points vs. prior period and YA | Syndicated | Category/segment × retailer × 4/13/52 wk | Trailing | Ratio on sums | E4 |
| B3 | Cannibalization rate | Σ volume lost from own existing items ÷ volume gained by new item (source-of-volume) | E2 | Launch item × period | Launch horizon | Ratio | E2 |
| B4 | Baseline velocity trend | Baseline units ÷ (stores × weeks), trailing 13/52 wk slope | E3 baseline; POS | SKU × retailer × week | Trailing | Weighted; slope | E3, E4 |
| B5 | Price index vs. competitors | Own avg unit price (per bar and per oz) ÷ competitor-set avg × 100; everyday and promoted separately | Syndicated | SKU × retailer × week | Trailing | Weighted avg | E4 |
| B6 | Distribution vs. competitors | Own TDP ÷ competitor TDP; ACV % side by side | Syndicated | SKU/brand × retailer × week | Current | Σ TDP | E4 |
| B7 | Model health & data ops | E1 wMAPE/bias at lags 1/4/13; E3 baseline holdout error; drift = error slope; freshness = days since last load; coverage = % ACV represented | E6 | Model × lag; feed | Trailing | Model output | E6 |

## 7. Marketing — Brand & Launch

| ID | KPI | Formula / definition | Source | Grain | Lag / basis | Aggregation | Engine |
|---|---|---|---|---|---|---|---|
| K1 | Launch performance vs. benchmark | ACV/TDP build at week n vs. benchmark curve; velocity as % of comparable launches at same week; repeat rate = repeat buyers ÷ trial buyers | Syndicated; panel; benchmark library | Launch item × week since launch | Weeks 1–52 | Curve comparison | E4, E1 |
| K2 | Net incremental contribution | F4 at item level, $ and units | E2, E3 | Launch item × month | Launch horizon | Sum | E2 |
| K3 | Share of segment | B2 at segment level (e.g., protein, snack, kids) | Syndicated | Segment × 13/52 wk | Trailing | Ratio on sums | E4 |
| K4 | Elasticity by item | F3 at item level; shelf-price basis | E2 | Item | Trailing 104 wks | Model output | E2 |
| K5 | Velocity trend by item | S6 by item (total) and B4 (baseline), trailing slope | POS/syndicated; E3 | Item × week | Trailing 13/52 | Weighted; slope | E3, E4 |
| K6 | Competitor activity | Count of competitor new items; avg price change %; promo frequency in set | Syndicated; E4 | Competitor set × month | Trailing 13 wks | Count; avg | E4 |
| K7 | Category / segment trend | Segment $ growth YoY; segment share of category | Syndicated | Segment × 13/52 wk | YoY | Ratio on sums | E4 |
| K8 | Promo lift | B1 lift % summarized by item | E3 | Item × event | Per event | Ratio | E3 |

---

## Cross-package reconciliation rules

KPIs that appear in more than one package must either share one definition or differ explicitly. This is where seven views stop agreeing if it isn't nailed down.

| Concept | Appears in | Rule |
|---|---|---|
| **Forecast accuracy** | P4, F7, B7 (and S4 as variance) | One function: wMAPE and bias at lag k, computed at the atomic grain (customer × SKU × week, units) and rolled up. Packages differ only by parameters: Production = SKU units, lag 4 wks; Finance = consolidated $, lag 1 quarter; BI = all lags. Never compute accuracy separately in $ and units and expect them to match. |
| **Net sales** | S1, F1, A1 (base) | One number. S1 is the atomic; F1 is S1 rolled to P&L lines; A1 uses S2 gross as its base. |
| **Trade rate** | S8, F8, A2 | One definition (trade $ ÷ gross $). Accounting owns actuals; E3 owns forecast; Sales and Finance read, never recompute. |
| **Cannibalization** | F4, B3, K2 | One source-of-volume matrix (E2). Finance renders net $ at portfolio level; BI renders the rate and method; Marketing renders per item. |
| **Elasticity** | F3, K4 | Same E2 output. Flag basis explicitly: Finance may use net-price elasticity for margin scenarios; Marketing uses shelf-price. Label which on every chart. |
| **Net incremental** | F4, K2 | Identical; K2 is F4 filtered to item. |
| **Promo lift** | B1, K8 | Identical; K8 is B1's lift % without the ROI decomposition. |
| **Share** | B2, K3 | Same formula; competitor set is BI-defined and versioned. Marketing cannot define its own set. |
| **Velocity** | S6, B4, K5 | One formula, always store-week weighted. Sales uses total velocity; BI uses baseline (non-promo); Marketing shows both, labeled. |
| **Distribution** | S3, B6 | Deliberately different sources: S3 = doors and authorization events (customer-facing, actionable); B6 = TDP/ACV from syndicated (market-facing, comparable). Keep both; never present S3 store counts as "distribution" next to competitor TDP. |
| **Capacity** | P3, F6 | F6 is P3 aggregated to month; same line model and rates. |
| **Forecast version** | All | Every KPI derived from E1 carries its version ID. Locked packages (2, 3, 4, 5) display it; latest packages (1, 6, 7) display "latest" plus the version timestamp. |
| **Units of measure** | P1, M1, S1 | Bars are the atomic unit. Cases, pallets, line hours, and material quantities are derived via the E5 UoM/BOM table — one table, no local conversion factors. |

## Build notes

- **Atomic fact grain:** customer × SKU × week, in bars, with version ID. Everything above rolls up from this.
- **Two demand facts, not one:** shipment (ERP) and consumption (POS/syndicated). S5 is the bridge; Production and Procurement read shipment only.
- **Deduction ledger is a first-class fact** (A3–A7 and B1's promo cost depend on it), not an Accounting-only extract.
- **Benchmark library** (K1) is a maintained asset: comparable launch curves by segment and format, updated as launches mature.

---
---

# Part 3 — SPINS Source Mapping

Based on the SPINS export structure (214 columns; UPC × Retail Account × week, weeks ending Sunday; history from 2025-04-13; all brands in `WELLNESS & SNACK BARS`).

## What SPINS is in this model

SPINS is the **consumption fact** (sell-through). It feeds packages 1 (partially), 6, and 7 fully, and is the estimation dataset for E2 (elasticity) and E3 (baseline/lift). It does **not** contain sell-in $, trade $, deductions, shipments, inventory, BOM, COGS, or capacity — packages 2, 3, 4 ($), and 5 come from ERP, the trade system, and the deduction ledger.

### Column families in the export

| Family | Columns | Role |
|---|---|---|
| Geography | `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography` | Retailer dimension. Sample shows MULO CRMA (Walmart, Meijer, Publix) and FOOD RMA (Ahold Delhaize), all `TOTAL CORPORATE` |
| Time | `Time Period` (= WEEK), `Time Period End Date` | Week ending Sunday |
| Product | `Product Level` (= UPC), `UPC`, `Brand`, `Description`, `Department`, `Category`, `Subcategory` | Item dimension, all brands |
| Attributes | `PACK COUNT`, `FLAVOR`, `NFP - PROTEIN`, `NFP RANGES - PROTEIN VALUE`, `STORAGE`, `UNIT OF MEASURE`, `NFP - SUGARS`, `NFP - CALORIES` | Segment dimensions for share, benchmarks, competitor sets |
| Volume | `Dollars`, `Units`, `EQ Units` | **`EQ Units` = `Units` × `PACK COUNT` = bars.** This is the canonical atomic unit on the consumption side |
| Distribution | `Avg % ACV`, `Max % ACV`, `TDP`, `Average Weekly TDP`, `Average Items Selling`, `Number of Weeks Selling`, `Weight Weeks`, `First Week Selling`, `# of Stores`, `# of Stores Selling`, `% of Stores Selling` | S3, B6, K1 |
| Velocity | `Units per Store Selling`, `Dollars per Store Selling` (and `Average Weekly …` variants), `Units SPP` (= `Units/TDP`), `Dollars SPP` (= `Dollars/TDP`), `Units SPM`, `Dollars SPM`, `… Per Item` variants | S6, B4, K5 |
| Price | `ARP`, `ARP, Promo`, `ARP, Non-Promo`, `Base ARP`, `Base ARP, Promo`, `ARP % Discount, Any Promo` | B5, F3, K4 |
| Promo split | `Dollars, Promo`, `Dollars, Non-Promo`, `Dollars, % Promo`, `Units, Promo`, `Units, Non-Promo`, `Units, % Promo`, `Promo Weeks`, `Avg/Max % ACV, Any Promo / Non-Promo`, `TDP, Any Promo / Non-Promo` | B1, K6, A3 validation |
| Baseline | `Base Dollars`, `Base Units`, `Incr Dollars`, `Incr Units` | SPINS' own baseline model; `Base + Incr = Dollars` |
| Tactic detail | `Dollar ,% Lift, {TPR, Any Display, Any Feature, Display Only, Feature Only, Feature & Display, SPK}`, `Units ,% Lift, {…}`, `ARP % Discount, {…}`, `Base ARP, {…}`, `ARP, {…}` | Sparse — populated only when the tactic ran that week |
| Yago | `<measure>, Yago` for nearly every measure | 52-week-prior values. NaN until the item has 52 wks of in-window history (from ~Apr 2026 onward) |

### Identities verified in the sample

- `EQ Units` = `Units` × `PACK COUNT` (1×, 5×, 6×, 12× all check)
- `Dollars` = `Dollars, Promo` + `Dollars, Non-Promo` = `Base Dollars` + `Incr Dollars`
- `ARP` = `Dollars` ÷ `Units` (per pack, not per bar)
- `Dollars per Store Selling` = `Dollars` ÷ `# of Stores Selling`; on weekly rows the `Average Weekly …` variants are identical
- `Dollars SPP` = `Dollars` ÷ `TDP` (rounding aside); for a single UPC row `TDP` = `Avg % ACV`

---

## KPI → SPINS column mapping

Coverage: **Full** = computable from SPINS alone; **Partial** = SPINS supplies one side; **None** = not a SPINS KPI (source listed).

### 1. Sales — Customer Growth

| ID | KPI | SPINS columns | Derivation | Coverage | Also needs |
|---|---|---|---|---|---|
| S1 | Net sales | — (`Dollars` is retail consumption $, shown as comparator only) | — | None | ERP invoices, E3 |
| S2 | Gross / G2N | — | — | None | ERP, trade system |
| S3 | Distribution & change events | `# of Stores Selling`, `% of Stores Selling`, `# of Stores`, `Avg % ACV`, `Max % ACV`, `TDP`, `First Week Selling` | Store count = `# of Stores Selling` by Retail Account × week; change event = Δ `# of Stores Selling` WoW and new `First Week Selling`; universe = `# of Stores` | Full (POS side) | Internal authorization list for wins/losses not yet scanning |
| S4 | Forecast vs. commitment | — | — | None | E1 versions |
| S5 | Sell-in vs. sell-through gap | `EQ Units` by Retail Account × week | Sell-through = `EQ Units` (bars); align ERP shipments to the same customer and Sunday-ending week; gap = Σ shipments − Σ `EQ Units` trailing 4/13 wks | Partial | ERP shipments; retailer inventory not in SPINS — estimate from cumulative gap |
| S6 | Velocity | `Units per Store Selling`, `Dollars per Store Selling` (weekly); `Units SPP`, `Units SPM` for cross-retailer | Canonical velocity = `Units per Store Selling` (use `EQ Units` ÷ `# of Stores Selling` for bars); cross-retailer comparisons use `Units SPP` | Full | — |
| S7 | YoY growth (consumption) | `Dollars`, `Dollars, Yago`, `EQ Units`, `EQ Units, Yago` | Use Yago where populated; otherwise lag 52 wks in the fact table | Full from Apr 2026 | Net-sales YoY is ERP |
| S8 | Trade rate | — (`Dollars, % Promo`, `ARP % Discount, Any Promo` are the retail-side proxy of promo intensity) | — | None | E3, ERP |

### 2. Production — Build Plan

| ID | KPI | SPINS columns | Coverage | Source |
|---|---|---|---|---|
| P1 | Forecast units | `EQ Units` feeds E1 as the consumption actual (bars); shipment conversion is E1 + ERP | Partial (input only) | E1 locked, ERP |
| P2–P3, P6, P8 | Requirements, capacity, DoS, adherence | — | None | ERP, MES, E5 |
| P4–P5, P7 | Accuracy, bias, churn | — (a consumption-forecast accuracy variant can use `EQ Units` as actual) | None | E1 versions vs. ERP shipments |

### 3. Procurement — Material Plan

| ID | KPI | Coverage | Source |
|---|---|---|---|
| M1–M8 | All | None | E5 BOM, ERP inventory/POs, supplier master, E1 bands (M5) |

### 4. Finance — Plan & Scenario

| ID | KPI | SPINS columns | Derivation | Coverage | Also needs |
|---|---|---|---|---|---|
| F1, F2, F5–F8 | Revenue, margin, scenario, capacity, accuracy, trade % | — | — | None | ERP, E1, E2, E5 |
| F3 | Price elasticity | `ARP`, `ARP, Non-Promo`, `ARP, Promo`, `Base ARP`, `EQ Units`, `Units, % Promo`, `TDP`, tactic-lift columns (presence = tactic active), competitor `ARP` | Weekly UPC × Retail Account panel: log(`EQ Units`) on log(`ARP`) with `TDP`, promo tactic flags, seasonality, competitor `ARP` as controls | Full (estimation data) | E2 model |
| F4 | Net incremental (launch) | `EQ Units` for launch item and existing own items by Retail Account × week; `First Week Selling` | Launch volume from `EQ Units`; cannibalization estimated by pre/post regression on existing own UPCs at same retailer. **`Incr Units` is promo-incremental, not launch-incremental — do not use it here** | Partial | SPINS shopper panel or Numerator for true source-of-volume |

### 5. Accounting — Trade Accrual Planner

| ID | KPI | SPINS columns | Coverage | Note |
|---|---|---|---|---|
| A1–A2, A4–A7 | Accruals, rates, timing, deductions, liability | — | None | E3, contracts, deduction ledger |
| A3 | Accrual vs. actual variance | `Promo Weeks`, `Dollars, % Promo`, `ARP % Discount, Any Promo`, `ARP, Promo` by Retail Account × week | Validation only | Confirms the promo actually ran at the retailer before a scan/bill-back deduction is accepted; flags deductions with no matching promo activity |

### 6. BI — Analytics Workbench

| ID | KPI | SPINS columns | Derivation | Coverage | Also needs |
|---|---|---|---|---|---|
| B1 | Promo incrementality & ROI | `Base Dollars`, `Base Units`, `Incr Dollars`, `Incr Units`, `Dollars, Promo`, `Units, Promo`, `Promo Weeks`, `Dollar ,% Lift, {tactic}`, `Units ,% Lift, {tactic}`, `ARP % Discount, {tactic}`, `ARP, {tactic}`, `Base ARP, {tactic}` | Lift % = `Incr Units` ÷ `Base Units`; tactic attribution from the sparse `% Lift` columns; discount depth from `ARP % Discount, {tactic}`. Adopt SPINS baseline as the retail-side source of truth for E3 | Full (lift); Partial (ROI) | Promo cost from E3/A1; margin from F2 |
| B2 | Share & share change | `Dollars`, `EQ Units`, `Dollars, Yago`, `Brand`, `Category`, `Subcategory`, `Geography` | Σ own-brand `Dollars` ÷ Σ all-brand `Dollars` at same Category × Geography × week; EQ share via `EQ Units`; change vs. Yago | Full | Confirm export is full-category, not a filtered brand list; confirm a total-market geography row exists |
| B3 | Cannibalization rate | As F4 | Source-of-volume from cross-UPC regression | Partial | Panel data for true switching |
| B4 | Baseline velocity trend | `Base Units`, `# of Stores Selling`, `TDP` | `Base Units` ÷ `# of Stores Selling` per week (or `Base Units` ÷ `TDP` for SPP form); trailing 13/52 wk slope | Full | — |
| B5 | Price index vs. competitors | `ARP`, `ARP, Non-Promo`, `ARP, Promo`, `PACK COUNT`, `Description`, `Brand` | Per bar = `Dollars` ÷ `EQ Units` (= `ARP` ÷ `PACK COUNT`); everyday = `ARP, Non-Promo`; promoted = `ARP, Promo`; index = own ÷ competitor-set weighted avg × 100. **Per oz requires size parsed from `Description`** (e.g., "2.3oz") — no size column exists | Full | Parsed size field |
| B6 | Distribution vs. competitors | `TDP`, `Avg % ACV`, `Max % ACV`, `Average Items Selling`, `# of Stores Selling`, `Brand` | Brand `TDP` = Σ item `Avg % ACV` at Geography × week; ratio vs. competitor set | Full | — |
| B7 | Model health & data ops | `Time Period End Date`, `# of Stores`, `Geography`, Yago columns | Freshness = today − max `Time Period End Date`; coverage = geography list and `# of Stores` universe; restatement check = `<measure>, Yago` vs. stored 52-wk-prior value | Partial | E6 for model accuracy |

### 7. Marketing — Brand & Launch

| ID | KPI | SPINS columns | Derivation | Coverage | Also needs |
|---|---|---|---|---|---|
| K1 | Launch performance vs. benchmark | `First Week Selling`, `Avg % ACV`, `TDP`, `# of Stores Selling`, `Units per Store Selling`, `EQ Units`; attributes `Subcategory`, `NFP RANGES - PROTEIN VALUE`, `STORAGE`, `PACK COUNT` | Weeks since launch = `Time Period End Date` − `First Week Selling` (per Geography); ACV build curve and velocity ramp indexed to week n; benchmark = same curves for comparable UPCs matched on attributes | Full (distribution, velocity); None (repeat) | Panel data for trial/repeat |
| K2 | Net incremental contribution | As F4 | — | Partial | Panel |
| K3 | Share of segment | `Subcategory`, `NFP RANGES - PROTEIN VALUE`, `STORAGE`, `PACK COUNT`, `Dollars` | B2 with segment defined by attribute columns | Full | — |
| K4 | Elasticity by item | As F3, shelf-price basis (`ARP, Non-Promo`) | — | Full (data) | E2 |
| K5 | Velocity trend by item | As S6 / B4 | Total and baseline, labeled | Full | — |
| K6 | Competitor activity | `First Week Selling`, `Brand`, `ARP, Non-Promo`, `Promo Weeks`, `Dollars, % Promo` | New items = competitor UPCs with `First Week Selling` in period; price moves = Δ `ARP, Non-Promo` vs. prior 13 wks; promo frequency = `Promo Weeks` ÷ weeks or avg `Dollars, % Promo` | Full | — |
| K7 | Category / segment trend | `Dollars`, `Dollars, Yago`, `EQ Units`, `Category`, `Subcategory`, attributes | Σ by segment vs. Yago; segment share of category | Full | — |
| K8 | Promo lift | As B1 | `Incr Units` ÷ `Base Units` by item | Full | — |

---

## Recommended SPINS fact model

**Grain:** UPC × Geography × week ending Sunday. Store one row per row in the export; do not pre-aggregate.

**Dimensions (normalize out):**
- `dim_product`: `UPC`, `Brand`, `Description`, `Department`, `Category`, `Subcategory`, `PACK COUNT`, `FLAVOR`, `STORAGE`, `UNIT OF MEASURE`, `protein_g` (parsed from `NFP - PROTEIN`), `NFP RANGES - PROTEIN VALUE`, `sugars_g`, `calories`, `size_oz` (parsed from `Description`), `is_own_brand`, `competitor_set_id` (BI-maintained)
- `dim_geography`: `Channel/Outlet`, `Geography Level`, `Retail Account`, `Retail Account Level`, `Geography`, `customer_id` (map to ERP customer for S5)
- `dim_week`: `Time Period End Date`, fiscal period, `week_minus_52`

**Measures (keep raw):** `Dollars`, `Units`, `EQ Units`, `Avg % ACV`, `Max % ACV`, `TDP`, `Weight Weeks`, `# of Stores`, `# of Stores Selling`, `ARP`, `ARP, Promo`, `ARP, Non-Promo`, `Base ARP`, `Dollars, Promo`, `Units, Promo`, `Promo Weeks`, `Base Dollars`, `Base Units`, `Incr Dollars`, `Incr Units`, `First Week Selling`.

**Drop or derive:** the `Average Weekly …`, `… Per Item`, `SPP`, `SPM`, `Dollars/TDP`, `% Promo`, `Non-Promo` columns are all derivable from the raw measures on weekly rows — derive in the semantic layer rather than storing 100+ redundant columns.

**Tactic columns:** unpivot the 7 tactics × 5 metrics (`% Lift $`, `% Lift units`, `ARP % Discount`, `Base ARP`, `ARP`) into a long table `fact_spins_tactic` (UPC × Geography × week × tactic × metric). They are sparse; a wide table is mostly NaN.

**Yago columns:** load them for validation and restatement detection, but compute YoY from `dim_week.week_minus_52` in the semantic layer. Yago is NaN for any item without 52 weeks of in-window history, so it is unusable before ~April 2026 and misleading for launches.

**Derived fields (semantic layer):**

| Field | Formula |
|---|---|
| `bars` | `EQ Units` |
| `arp_per_bar` | `Dollars` ÷ `EQ Units` |
| `velocity_units_psw` | `EQ Units` ÷ `# of Stores Selling` |
| `velocity_spp` | `EQ Units` ÷ `TDP` |
| `lift_pct` | `Incr Units` ÷ `Base Units` |
| `promo_pct_units` | `Units, Promo` ÷ `Units` |
| `weeks_since_launch` | `Time Period End Date` − `First Week Selling` |
| `share_dollars` | own `Dollars` ÷ Σ category `Dollars` at same Geography × week |
| `brand_tdp` | Σ item `Avg % ACV` by Brand × Geography × week |
| `price_index_everyday` | own `ARP, Non-Promo` per bar ÷ competitor-set weighted `ARP, Non-Promo` per bar × 100 |

---

## Gaps and data-quality items to resolve

| Item | Why it matters | Action |
|---|---|---|
| **No size (oz) column** | Per-oz price index (B5) and EQ comparisons across formats | Parse from `Description`; maintain override table for failures |
| **`NFP` fields are strings** ("15 g", "270 calories") | Segment filters and benchmarks | Parse to numeric on load |
| **Yago sparsity** | YoY breaks for launches and pre-Apr-2026 | Compute from lag; treat Yago as validation |
| **Geography completeness** | Share needs a consistent denominator | Confirm the full file includes a total-market row (e.g., Total US MULO) and whether sub-corporate divisions exist; sample is `TOTAL CORPORATE` only |
| **Full-category export?** | Share (B2, K3) is wrong if the export is a filtered brand list | Confirm with SPINS that all `WELLNESS & SNACK BARS` UPCs are included, not a custom set |
| **Retailer inventory not in SPINS** | S5 weeks-of-supply is an estimate | Use cumulative shipment − cumulative `EQ Units` with a lag; refine with retailer portal data where available (Walmart Retail Link, etc.) |
| **No panel data** | True source-of-volume (F4, B3, K2) and repeat rate (K1) | Evaluate SPINS shopper panel or Numerator; until then, label cannibalization as POS-estimated |
| **`Incr Units` ≠ launch incrementality** | Easy to misuse in F4/K2 | Enforce in semantic layer: `Incr Units` is promo-only |
| **ERP customer ↔ `Retail Account` mapping** | S5 and any sell-in/sell-through view | Build and maintain `customer_id` crosswalk in `dim_geography` |
| **Week calendar alignment** | ERP shipments must roll to Sunday-ending weeks | Adopt SPINS week as the platform week; convert ERP daily to it |

---
---

# Part 4 — Internal Data Request (to fill SPINS gaps)

Organized by client source system. Each dataset lists the fields needed, grain, history, refresh cadence, and which KPIs it unblocks. History target is **3 years** wherever it exists (E1 needs 2+ years for seasonality; SPINS only goes back to April 2025, so internal history is what makes the forecast credible).

## Two crosswalks that gate everything

| Crosswalk | Why it's first | Owner |
|---|---|---|
| **SKU ↔ UPC** | SPINS is keyed on UPC; ERP is keyed on internal SKU/item code. Multipacks, variety packs, club packs, and UPC changes must all resolve. Without this, no consumption metric can sit next to any internal metric | Product master / Sales Ops |
| **Customer ↔ `Retail Account`** | ERP bill-to/ship-to hierarchies must roll to SPINS `Retail Account` (e.g., all Kroger banners → KROGER). Distributor customers (UNFI, KeHE) need a separate treatment — see below | Sales Ops / Finance |

**Distributor question to ask immediately:** if a meaningful share of volume ships to UNFI/KeHE rather than direct to retailers, ERP shipments are sell-in to the distributor, not the retailer. Request distributor sell-through reports (UNFI/KeHE customer-level shipment reports) to bridge distributor → retailer, or S5 and customer-level forecasts will be wrong for those accounts.

---

## A. ERP — Order-to-Cash (invoicing, AR)

| Dataset | Fields | Grain | History | Refresh | Unblocks |
|---|---|---|---|---|---|
| **Invoice lines** | Invoice #, date, bill-to, ship-to, SKU, qty (cases, eaches), list price, gross $, off-invoice allowance $, net invoice $, returns/credits, currency | Line × day | 3 yrs | Daily | S1, S2, S7 (net-sales basis), F1, A1 base |
| **Price list history** | SKU, customer (or price group), list price, effective from/to | SKU × customer × effective date | 3 yrs | On change | S2, F3 (net-price basis), E1 |
| **Customer master** | Customer ID, name, bill-to/ship-to hierarchy, channel, parent account, terms, distributor flag | Customer | Current + change log | On change | Customer ↔ `Retail Account` crosswalk |
| **Product master** | SKU, description, UPC(s) with effective dates, case pack, pallet config, brand, sub-brand, status (active/discontinued), launch date, discontinue date, shelf life days | SKU | Current + change log | On change | SKU ↔ UPC crosswalk, E5 UoM table, K1 launch dates, P6 shelf life |

## B. ERP — Fulfillment / Logistics

| Dataset | Fields | Grain | History | Refresh | Unblocks |
|---|---|---|---|---|---|
| **Shipments** | Ship date, ship-to, SKU, qty shipped (cases, eaches), order date, requested date, order qty (for fill rate), warehouse/DC | Line × day | 3 yrs | Daily | **The shipment fact.** P1 basis, S5, E1 training data, P4/P5 actuals |
| **Open orders** | Order #, customer, SKU, qty, requested ship date, status | Line | Current | Daily | P2 (near-term demand), S5 |
| **Finished goods inventory** | SKU, location, lot, qty on hand, qty allocated, production date, expiry date | SKU × location × lot | Current + monthly snapshots (2 yrs) | Daily | P2, P6, S5 |

## C. Production — MES / Scheduling

| Dataset | Fields | Grain | History | Refresh | Unblocks |
|---|---|---|---|---|---|
| **Production actuals** | Date, line, SKU, planned qty, produced qty, run hours, downtime, scrap | Run | 2 yrs | Daily | P8, P3 (actual rates), E5 |
| **Production schedule** | Line, SKU, scheduled qty, start/end, status | Scheduled run | Current + 13 wks | Weekly | P2 (scheduled receipts) |
| **WIP** | SKU, stage, qty | Current | — | Daily | P2 |
| **Line master** | Line, SKUs runnable, standard rate (bars/hr or cases/hr), changeover matrix (SKU-to-SKU minutes), shifts/available hours by week, planned maintenance | Line | Current | On change | P3, F6, E5 capacity model |
| **Safety stock policy** | SKU, target (days or units), method | SKU | Current | On change | P2, P6 |
| **Customer shelf-life requirements** | Customer, min remaining shelf life at delivery (days or %) | Customer × SKU or category | Current | On change | P6 expiry risk |

## D. Procurement — Materials

| Dataset | Fields | Grain | History | Refresh | Unblocks |
|---|---|---|---|---|---|
| **Bill of materials** | Parent SKU, component material, qty per unit, UoM, scrap %, effective from/to, BOM level | SKU × component | Current + history | On change | M1, F2, M5, E5 |
| **Material master** | Material ID, description, type (ingredient/packaging), UoM, supplier(s), lead time days, MOQ, order multiple, shelf life, storage requirements | Material | Current | On change | M2, M3, M7 |
| **Raw/pack inventory** | Material, location, lot, qty on hand, expiry | Material × lot | Current + monthly snapshots | Daily | M2 |
| **Open POs** | PO #, material, supplier, qty, unit price, order date, promised date | PO line | Current | Daily | M2, M3 |
| **PO / receipt history** | PO line, qty ordered, qty received, receipt date, promised date, unit price | PO line | 2 yrs | Weekly | M6 (cost), M8 (OTIF) |
| **Supplier master** | Supplier, materials supplied, terms, contracted price/volume, hedge or contract coverage | Supplier | Current | On change | M6, M7 |

## E. Finance — FP&A / Cost Accounting

| Dataset | Fields | Grain | History | Refresh | Unblocks |
|---|---|---|---|---|---|
| **Budget / AOP** | Customer, SKU, month, gross $, trade $, net $, units | Customer × SKU × month | Current year + prior | Annual + re-forecasts | F1, S4 (commitment basis) |
| **Standard cost / COGS** | SKU, material cost, conversion cost, packaging, freight/logistics, total standard cost, effective date | SKU × effective date | 2 yrs | Quarterly | F2, B1 (ROI margin), F4 |
| **Actual P&L by SKU** | SKU, month, net sales, COGS, gross margin | SKU × month | 3 yrs | Monthly | F2 validation, F7 |
| **Capex plan and capacity thresholds** | Line, current capacity, planned additions, cost, lead time, trigger utilization % | Line | Current | On change | F6 |
| **Fiscal calendar** | Fiscal periods, week ending convention | — | 3 yrs + 2 fwd | Annual | dim_week alignment |
| **Existing forecast versions** | If a demand-planning tool or spreadsheet forecast exists: version date, customer, SKU, period, qty | Version × customer × SKU × period | Whatever exists | Monthly | Backfill for P4/P5/F7 accuracy history; S4 |

## F. Trade Promotion Management / Deductions (may be in ERP, a TPM tool, or spreadsheets)

| Dataset | Fields | Grain | History | Refresh | Unblocks |
|---|---|---|---|---|---|
| **Promo plans / events** | Event ID, customer, SKU(s), mechanic (TPR, display, feature, scan, bill-back, off-invoice, slotting, MDF), start/end, planned rate or $, planned volume, status | Event | 3 yrs | Weekly | A1, A4, B1 (promo cost), E3, S2 bridge |
| **Contracts / rate agreements** | Customer, program, rate % or $/case, effective dates, funding type | Customer × program | Current + history | On change | A1, A2 |
| **Accrual history** | Period, customer, mechanic, GL account, accrued $ | Customer × period × mechanic | 3 yrs | Monthly | A3, A6 |
| **Deduction ledger** | Deduction ID, customer, post date, amount, reason code, referenced promo/event, match status, resolution date, resolution type (matched, repaid, written off), invoice reference | Deduction | 3 yrs | Daily | A3, A4, A5, A6, A7 |
| **Settlements** | Credit memos, check payments to customers, date, amount, promo reference | Settlement | 3 yrs | Weekly | A6 |
| **GL mapping** | Trade GL accounts, mechanic → account mapping | — | Current | On change | A1 GL Mapping tab |

## G. Sales / Customer Management

| Dataset | Fields | Grain | History | Refresh | Unblocks |
|---|---|---|---|---|---|
| **Customer item authorizations** | Customer, SKU, authorized (Y/N), authorized store count or banner list, effective date, planogram reset date | Customer × SKU × effective date | 2 yrs | On change | S3 (authorized doors; wins/losses ahead of scan) |
| **Distribution wins/losses log** | Customer, SKU, event type (new item, expansion, delist, reset), effective date, expected store count, source (line review, JBP) | Event | 2 yrs | On change | S3 change events, E1 input |
| **Sales targets / commitments** | Customer, period, committed net $ or units | Customer × period | Current + prior | Per cycle | S4 |
| **Launch calendar** | SKU, launch date, target customers, planned ACV, planned support | Launch | 2 yrs + forward | On change | K1 planned vs. actual, E1 launch input |

## H. Retailer Portals (external but client-accessed)

| Source | Dataset | Unblocks |
|---|---|---|
| Walmart Retail Link, Kroger Stratum/84.51°, Target POL, Costco, Publix, Meijer, etc. | Store-level POS, **retailer on-hand inventory**, in-stock %, forecast/order projections | S5 (true weeks-of-supply), store-level S3, validation of SPINS at the account level |
| UNFI / KeHE | Distributor sell-through by retailer, distributor inventory | Bridges distributor sell-in to retailer sell-through |

## I. External data to evaluate (not internal)

| Source | Unblocks |
|---|---|
| SPINS shopper panel or Numerator | F4/B3/K2 true source-of-volume; K1 trial/repeat |
| Commodity price feeds (cocoa, nuts, whey, oats, sugar; packaging films) | M6 |

---

## Request sequencing

**Wave 1 — unblocks the forecast and Sales package**
Product master (SKU ↔ UPC), customer master (↔ `Retail Account`), shipments (3 yrs), invoice lines (3 yrs), price list history, promo plans/events, distributor sell-through if applicable, fiscal calendar.

**Wave 2 — unblocks Production and Procurement**
Finished goods inventory, open orders, production schedule and actuals, line master, BOM, material master, raw/pack inventory, open POs, safety stock policy, shelf-life requirements.

**Wave 3 — unblocks Finance and Accounting**
Budget/AOP, standard cost, actual P&L by SKU, capex plan, contracts/rate agreements, accrual history, deduction ledger, settlements, GL mapping, existing forecast versions.

**Wave 4 — refinements**
Customer authorizations, wins/losses log, sales targets, launch calendar, retailer portal extracts, panel data evaluation.

## Questions to ask in the kickoff

1. Which ERP, and is TPM/deduction management inside it, in a separate tool, or in spreadsheets?
2. What share of volume goes through distributors vs. direct?
3. Is there an existing forecast process, and does version history exist?
4. Does one internal SKU ever map to multiple UPCs (or vice versa) — variety packs, club, UPC changes?
5. What is the fiscal calendar, and does anyone already report on SPINS Sunday-ending weeks?
6. Which retailer portals does the client have logins for, and who owns them?
7. Are standard costs maintained by SKU with a BOM roll-up, or only at a category level?
8. How are deductions currently matched to promotions — by event reference, or manually?
