# Aevah Platform — Full Process Description

**Prepared:** September 9, 2026  
**For:** Rob Long / BUILT team  
**Purpose:** End-to-end description of data in → models → outputs, including what each persona receives and in what form. To be reviewed before design or build begins.

---

## The shape of the problem

The 4 ML models are largely in hand. What's been missing from the plan is the output layer — the reports, narratives, velocity metrics, and delivery cadence that turn model numbers into decisions. Brian has named this explicitly: *"You need to know the context"* and *"So what, now what?"* The models are the engine. This document describes what the driver touches.

---

## Part 1 — Data into Druid

Three data tables feed everything downstream. They load in phases.

### Table 1: `built_filtered_weekly` — SPINS (Phase 1, available now)
- **Source:** SPINS weekly POS export → MinIO → Druid ingestion
- **Grain:** UPC × Retail Account × week
- **Scope:** BUILT own-brand + same-subcategory competitors, all ~80 SPINS retailers
- **Key columns:** EQ Units, Base Units, Incr Units, TDP, ARP, ARP Promo, ARP Non-Promo, # Stores Selling, First Week Selling, Dollars, Base Dollars, Incr Dollars, promo flags, 214 columns total
- **Refresh cadence:** Weekly (SPINS monthly export processed weekly)
- **Status:** Live

### Table 2: `costco_warehouse_weekly` — Circana CRX (Phase 1, parallel track)
- **Source:** BP222 CSV → pre-processing → MinIO → Druid ingestion
- **Grain:** Item × Costco Warehouse × week
- **Scope:** BUILT own-brand only; 909 warehouses; Jan 2023–Aug 2026 in hand
- **Pre-processing required before ingest:**
  1. Strip `$`, `,`, `( )` from all money columns → cast to float
  2. Resolve UPC duplicates (Costco item numbers → real UPCs via Item_Assumptions crosswalk)
  3. Parse "1 week ending MM-DD-YYYY" → `__time` timestamp
  4. Normalize Unit Sales → bars (× PACK COUNT from Item_Assumptions)
- **Key columns post-processing:** unit_sales_bars, dollar_sales, warehouses_selling, number_of_warehouses, inventory_on_hand, on_order, quantity_received, avg_coupon_value, promoted_units, pct_discount, gas price series (4 grades, EIA weekly national averages)
- **Status:** File in hand; ingest pipeline not yet built. Justin Fisher is BUILT's action owner.

### Table 3: ERP tables — NetSuite (Phase 2, Connor + Justin Fisher project)
- **Source:** NetSuite → MinIO → Druid ingestion
- **Tables:** `erp_invoices` (gross/net revenue by customer), `erp_shipments` (sell-in units), `erp_cost` (COGS, AOP)
- **Gate:** Requires 3 crosswalks in Druid first:
  1. SKU ↔ UPC with effective dates (pack changes, variety pack components)
  2. Customer ↔ Retail Account (ERP bill-to → SPINS Retail Account)
  3. Customer-Retailer-Distributor bridge (Level 1 = DotFoods/UNFI/Coremark → Level 2 = YesWay/etc.) with effective dates
- **Status:** Active project (Justin Fisher). Not yet in Druid.

---

## Part 2 — The 4 ML models

### Model 1: E1 Global — Demand Forecast
- **What it does:** Predicts bars by SKU × retailer × week, 13 weeks forward, with confidence bands
- **Algorithm:** LightGBM (MO_53), globally trained across all BUILT SKUs and retailers
- **Training data extract from Druid:**
  - Table: `built_filtered_weekly`
  - Target: `eq_units` (bars)
  - Features: lagged eq_units (1w, 4w, 13w), TDP, ARP, Base Units, Incr Units, promo week flag, # Stores Selling, First Week Selling (weeks since launch), FRED macro signals (CPI, gas, consumer sentiment)
  - Filter: BUILT own-brand rows only
  - Approx rows: ~1M (156 SKUs × 80 retailers × 78 weeks)
- **Output table:** `demand_forecast` (SKU × retailer × week × forecast value × confidence interval)
- **Training cadence:** Weekly, triggered on SPINS refresh
- **Status:** Done (MO_53). Retrained weekly.
- **New items:** ETS statistical fallback (MO_75) for items with fewer than 52 actuals; activates automatically

---

### Model 2: E1 Costco — Demand Forecast (Costco-specific)
- **What it does:** Predicts bars by BUILT item × week at Costco aggregate level, incorporating supply chain signals unavailable in SPINS
- **Algorithm:** LightGBM (separate from MO_53 — different feature set, different promo mechanics)
- **Why separate:** Costco is warehouse-level (not store-level), club-pack units (not individual bars), coupon-book-only promotions (no TPR/feature/display), and has inventory signals (On Hand, On Order, In Transit) with no SPINS equivalent
- **Training data extract from Druid:**
  - Table: `costco_warehouse_weekly` aggregated to item × week
  - Target: `unit_sales_bars` (units × pack count)
  - Features: lagged unit_sales_bars, warehouses_selling, on_order (lag 1 week — forward demand signal), quantity_received (lag 1 week), inventory_on_hand (inventory pressure), avg_coupon_value (coupon week flag: > $0 = promo), pct_discount, gas price series
  - Approx rows: ~5,600 (29 items × 192 weeks) — small dataset; use regularization
- **Output table:** `demand_forecast_costco` (item × week × forecast value × confidence interval)
- **Training cadence:** Monthly, triggered on new CRX file receipt
- **Status:** Not yet built. Blocked on CRX → Druid ingest pipeline.

---

### Model 3: E2a — Cannibalization Rates
- **What it does:** Produces a cross-SKU displacement matrix — for every (focal SKU, donor SKU) pair, what fraction of the donor's volume loss is attributable to the focal SKU's gain
- **Algorithm:** LightGBM classifier + ranker (MO_55), trained on same-retailer × same-week pairs
- **Training data extract from Druid:**
  - Table: `built_filtered_weekly`, all own-brand UPCs simultaneously
  - Features: cross-UPC lagged units at same retailer × week, distribution overlap (both SKUs selling in same stores), promo confound flag, weeks since launch (focal), comparison distance (flavor / pack / format)
  - Same table, pivoted wide across UPC pairs
- **Output table:** `cannibalization_rates` (focal_upc × donor_upc × retailer × rate × confidence)
- **Training cadence:** Weekly with SPINS refresh
- **Status:** 48% of valid pairs scored (MO_55). Architecture complete.
- **Note:** Does NOT apply to Costco — no competitor data, BUILT-only within-Costco cannibalization is small enough for deterministic calculation

---

### Model 4: E2b — Price Elasticity
- **What it does:** Estimates own-price elasticity (ε) per SKU — for every $0.10 increase in ARP, how many units are lost?
- **Algorithm:** Per-SKU regression with guardrails (MO_16/17). ~156 individual fitted models run as one batch job.
- **Training data extract from Druid:**
  - Table: `built_filtered_weekly`, per-SKU subsets
  - Features: ARP, ARP Promo, ARP Non-Promo, EQ Units, TDP, promo_week indicator, First Week Selling (controls for launch effects)
  - Guardrail: $0.05 minimum price change threshold to filter noise
  - Approx rows per SKU: ~80 retailers × 78 weeks = ~6,240
- **Output table:** `elasticity_estimates` (upc × retailer × ε × optimal_price_range × confidence)
- **Training cadence:** Monthly (price changes slowly relative to weekly demand)
- **Status:** ~156 fits complete (MO_16/17). Temporal holdout validation pending (MO_16 uses random 80/20 split only).
- **Note:** Does NOT apply to Costco — price variation is binary (coupon on/off, $4 or $5), not a continuous price curve. Costco elasticity is a before/after coupon comparison, computable as a simple ratio.

---

## Part 3 — The 3 non-ML outputs (equally important)

These are Druid queries and pipeline scripts, not trained models. They are missing from prior versions of this plan but are what Brian's team actually uses day-to-day.

### Output A: Base Velocity
- **What it is:** `Base Units ÷ # Stores Selling` per SKU × retailer × week — the non-promoted demand rate. Answers: "What does this product sell in a normal week at a typical store, with no promotional support?"
- **Why it matters:** Brian has asked for this explicitly in two separate meetings. It's the starting point for Connor's Excel forecast. It's the signal that separates genuine demand growth from promo-inflated volume. When velocity goes down as new items launch, base velocity isolates whether that's real demand erosion or a promo comparison artifact.
- **Source:** `built_filtered_weekly`, columns `base_units` + `stores_selling`
- **Output:** Query result available in Mo UI and as CSV download — by SKU, by retailer, by time window (4w, 13w, 26w, 52w), with trend direction and YoY comparison
- **Relationship to models:** Base velocity is the input to E1 (features), the context for E2a (cannibalization explains velocity drops), and the primary KPI for Sales (Experience 1) and BI (Experience 6)
- **Status:** MO_70 velocity extract was a one-off prototype. Needs to be a permanent, queryable output in Mo UI.

### Output B: Launch Ramp Benchmarks
- **What it is:** A lookup table of historical launch curves — median velocity ramp by segment/format across BUILT's past launches. Answers: "Is this new item tracking above or below what a comparable launch looked like at this point?"
- **Why it matters:** BUILT has gone from 3.5 items to 7.5 items in one year. New items don't have 52 weeks of history for E1 to train on. The ETS fallback (MO_75) handles forecasting. But it doesn't answer "is this launch working?" — that requires a benchmark. Brian said this is the context that's missing.
- **Source:** Historical `built_filtered_weekly` grouped by `First Week Selling` — compute median velocity curve at weeks 1, 2, 4, 8, 13, 26 post-launch, segmented by format (bar vs. puff), pack size (1-pack, 4-pack, 12-pack), and flavor family
- **Output table:** `launch_benchmarks` (segment × format × pack × weeks_since_launch → median_velocity_p25_p75)
- **Refresh:** Quarterly (launch curves don't change quickly)
- **Feeds:** Experience 7 (Marketing — launch tracker), Experience 2 (Production — ramp planning), Experience 1 (Sales — "is this account tracking?")
- **Status:** Not built. Data to build it is available in `built_filtered_weekly` today.

### Output C: Demand Intelligence Report
- **What it is:** An auto-generated report produced after every SPINS refresh and model training run. Brian called it the thing that "gets generated automatically every time data came in." Rob described it as what replaces Connor's manual Monday process.
- **Contents per report run:**
  1. Forecast accuracy this cycle vs. prior cycle vs. baseline (wMAPE at 4-week lag, by SKU and in aggregate) — shows the model is improving
  2. Base velocity trends — top movers (up and down), with "So What" annotation
  3. Cannibalization alerts — pairs where rate has materially changed this cycle
  4. Distribution changes — SKUs that gained or lost meaningful TDP (≥5 points)
  5. New item ramp status — all items launched in last 26 weeks vs. benchmark
  6. Promo performance — incremental lift this cycle vs. historical baseline
  7. Forecast vs. actuals reconciliation — what was forecast last cycle, what actually happened, why the gap
- **Format:** Two versions:
  - **Full report (Connor/Chase/Jeff):** HTML with drill-down, downloadable as PDF and CSV per section. 50-page depth available. Audit trail embedded (query lineage per number).
  - **Executive summary (Brian/Bracken):** One-page "What / So What / Now What" per major signal, PDF. No more than 5 items. Action-oriented.
- **Delivery:** Auto-triggered on SPINS refresh → E1 retrains → report generates → distributed to named recipients
- **Cadence:** Every 4 weeks (SPINS monthly cycle), or more frequently if SPINS refresh accelerates
- **Status:** The 22-script `run_fpa_report.sh` chain produces a 50-page HTML report (v2.2.0). It needs: (a) auto-trigger wiring, (b) base velocity section added, (c) executive summary version, (d) "What / So What / Now What" narrative structure throughout, (e) delivery mechanism (email or shared URL).

---

## Part 4 — The output layer: what each persona receives

The experience names and engine dependencies are documented in `docs/aevah_platform_model_summary.md`. This section maps what each persona receives as their primary output — the thing they actually use.

---

### Persona 1: Connor (Sales / Demand Planner)
**Primary question:** "What is the forecast by customer by SKU for the next 13 weeks, and how does it compare to what I had before?"

**Primary outputs:**
- Live Mo UI: SKU × account demand view with 13-week forecast, base velocity trend, distribution changes, promo calendar
- **Monday morning download:** CSV or Excel-formatted demand table by SKU × customer × week — replaces the spreadsheet Connor updates manually today. Same shape as Connor's existing output so it drops into whatever downstream system he feeds.
- Cannibalization alert when a new launch is materially affecting an existing SKU at a specific account
- On-demand: "Mo, what changed at Kroger for Cookies & Cream this week?" → "What / So What / Now What" response

**Key metric:** Base velocity (base units per store per week) + 13-week forecast + distribution (% ACV or # stores)

**Format:** Live UI + scheduled CSV download + Mo Chat narrative

---

### Persona 2: Chase (Sales Analyst / Forecast Ops)
**Primary question:** "Across all accounts, which SKUs are at risk vs. plan, and what's the aggregate picture?"

**Primary outputs:**
- Cross-account portfolio view: all BUILT SKUs, all retailers, ordered by forecast vs. plan gap
- Distribution change events (gains/losses) as a priority queue
- Download: cross-account demand summary table by SKU × week for the planning horizon

**Format:** Live UI + CSV download

---

### Persona 3: Ethan (Forecast Consolidator, per Brian's July 24 mention)
**Primary question:** "What is the official forecast to hand to Jeff this week?"

**Primary outputs:**
- Consolidated demand view (all SKUs, all accounts) with version lock — named snapshot (e.g., "2026-09 v3")
- One-click PDF of the consolidated forecast for distribution
- Audit trail: every number traces back to source query and training run date

**Format:** Locked forecast snapshot + PDF export

---

### Persona 4: Jeff (FSVP Finance / Forecast Owner)
**Primary question:** "Is the forecast credible? What are the risks? How accurate have we been?"

**Primary outputs:**
- Forecast accuracy KPI trend over time (wMAPE, by SKU and aggregate) — shows improvement trajectory
- Risk flags: items where model confidence is low (new items, high recent volatility, data quality issues)
- Scenario view: "what if we add a new item? what if we lose Target distribution?"
- Audit trail: query lineage for any number he questions
- Demand intelligence report (full version, every 4 weeks)

**Format:** Live UI executive view + demand intelligence report (full) + audit trail

---

### Persona 5: Bracken (CFO)
**Primary question:** "Are we going to hit our revenue plan? What do I need to know this month?"

**Primary outputs:**
- One-page executive summary (PDF), auto-generated every 4 weeks:
  - **What:** Revenue forecast vs. plan, key variance drivers
  - **So What:** Cannibalization risk, distribution change impact, forecast accuracy trend
  - **Now What:** 1–3 recommended actions (e.g., "Accelerate 12-pack distribution; reduce 4-pack promo spend at Kroger")
- No login required — receives the PDF by email or shared link

**Format:** Auto-generated one-page PDF, "What / So What / Now What" structure

---

### Persona 6: Production S&OP Team
**Primary question:** "How many bars of each SKU do I need to produce in the next 13 weeks?"

**Primary outputs:**
- Bars by SKU × week (no retailer detail — masked to protect customer relationships)
- Converted to cases and pallets (E5 UoM conversion: bars ÷ units per case ÷ cases per pallet)
- Promo events shown as demand spikes (timing and magnitude only — no customer name)
- Production load vs. line capacity view (if line hours per case is provided)
- Download: production planning table by SKU × week in bars/cases/pallets

**Key rule:** Must never expose retailer identity through screens, downloads, or Mo Chat responses.

**Format:** Live UI (masked) + production planning download

---

### Persona 7: Procurement Team
**Primary question:** "What raw materials and packaging do I need to order, and by when?"

**Primary outputs:**
- BOM explosion: bars by SKU × week → ingredient requirements × week (Phase 3, requires BOM data in Druid)
- Coverage view: on-hand + open POs vs. material requirement — flags coverage gaps by ingredient × period
- Order-by date alerts: lead-time-aware trigger (e.g., "Need to order whey protein by Oct 3 to cover the Nov 1 production run")
- In Phase 1 (before BOM): shows bars forecast only — still useful for high-level planning horizon visibility

**Format:** Live UI + BOM requirements download (Phase 3)

---

### Persona 8: Finance / Scenario Planning (Jeff + Bracken)
**Primary question:** "What does revenue look like if we change price on the 4-pack? What's the net cannibalization impact?"

**Primary outputs:**
- Scenario Studio: "Raise ARP $0.50 on 4-pack" → E2b calculates demand response → E2a calculates cannibalization impact on 12-pack → net revenue + contribution margin delta
- Sensitivity table: revenue impact at 3 price points × 3 distribution scenarios
- Download: scenario comparison as Excel (the format Bracken's team uses for budget submissions)

**Format:** Live interactive UI + Excel scenario export

---

### Persona 9: BI / Analytics Team (Experience 6)
**Primary question:** "Why did our share change? Is our promo working? Where is the competitive pressure coming from?"

**Primary outputs:**
- Full competitive view: BUILT vs. defined competitor set — share, TDP, velocity, price index
- Promo post-mortem: incremental lift per event, ROI (requires trade cost from Phase 2 for full ROI)
- Cannibalization heat map: cross-SKU rate matrix, trend over time
- Base velocity trend: own-brand baseline, category baseline, competitor baseline
- Download: full analytic export (everything in the view, as CSV)

**Format:** Live UI (richest data access) + CSV export

---

### Persona 10: Marketing Team (Experience 7)
**Primary question:** "Is our launch working? How are competitors responding? What is the price opportunity?"

**Primary outputs:**
- Launch tracker: new item velocity vs. benchmark curve, distribution ramp vs. prior launches
- Net incremental contribution: post-cannibalization volume — "Is this new item actually growing the portfolio?"
- Competitive response: competitor price and distribution moves around BUILT's launch window
- Brand health view: category/segment trend, BUILT share trend

**Format:** Live UI + launch report (shareable PDF per launch)

---

## Part 5 — The Monday morning cadence

What happens each week when SPINS data arrives:

```
Monday morning:
  SPINS weekly export arrives → lands in MinIO
  ↓
  Druid ingestion runs (Q0–Q9 query chain, 2–4 hours)
  ↓
  E1 Global retrains on updated data (~30 min)
  E2a Cannibalization rates update (~60 min)
  ↓
  Forecast, base velocity, distribution change queries run
  ↓
  Anomaly detection: flags items with >15% forecast change vs. prior week
  ↓
  Demand intelligence report generates (auto, no manual trigger)
  ↓
  Connor receives: updated demand table (CSV download) + report link
  Chase receives: cross-account alert digest
  Jeff receives: accuracy KPI update + risk flag summary
  ↓
  Connor reviews → overrides if needed → locks version
  ↓
  Production and Procurement see updated bars (from locked version)
  ↓
  Every 4 weeks: full demand intelligence report + executive summary → Brian/Bracken
```

The CRX (Costco) track runs monthly on a separate cadence when Justin Fisher provides a new file. It does not block the weekly SPINS cycle.

---

## Part 6 — What needs to be built vs. what exists

| Component | Status | Blocked on |
|-----------|--------|-----------|
| E1 Global (SPINS forecast) | Done (MO_53) | — |
| E2a Cannibalization rates | 48% scored (MO_55) | Data maturity on remaining pairs |
| E2b Price elasticity | ~156 fits (MO_16/17) | Temporal holdout validation |
| ETS fallback for new items | Done (MO_75) | — |
| E1 Costco (CRX forecast) | Not built | CRX → Druid ingest pipeline |
| CRX ingest pipeline | Not built | Justin Fisher getting file into MinIO |
| Base velocity query + Mo UI | Prototype only (MO_70) | Needs permanent integration |
| Launch ramp benchmarks | Not built | Design + data available |
| Demand intelligence report (full) | Done (run_fpa_report.sh, v2.2.0) | Auto-trigger wiring; base velocity section; audit trail |
| Executive summary (one-page PDF) | Not built | Design first |
| "What / So What / Now What" narrative | Mo Chat capability exists | Needs to be structured to this pattern per screen |
| Monday delivery mechanism | Not built | Email / URL delivery wiring |
| Forecast version locking | Architecture defined | Implementation |
| Scenario Studio (price/cannib) | Not built | E2b + E2a wired to UI |
| BOM explosion (Procurement) | Not built | BOM data → Druid (Phase 3) |
| NetSuite ERP ingest | Not built | Justin Fisher / Phase 2 crosswalks |
| Audit trail / lineage | Architecture defined | Implementation per number |

---

*Companion documents:*  
- `docs/aevah_platform_model_summary.md` — 3-engine model answer for Rob  
- `docs/aevah_client_internal_data_request.md` — data request spec (R01–R16)  
- `docs/circana_costco_field_glossary.md` — BP222 field definitions  
- `wiki/15-aevah-platform-architecture.md` — full architecture detail
