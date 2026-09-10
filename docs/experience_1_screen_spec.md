# Experience 1 — Customer Growth: Screen Spec

**Prepared:** September 10, 2026  
**For:** Rob Long + Jason (wireframe collaboration input)  
**Source docs:** `aevah-packaged-experiences-v2_Clauderesponse.md` · `aevah_full_process_description.md` · Sept 10 standup  

---

## What this experience is

Sales sees both sell-in (manufacturer revenue) and sell-through (POS/velocity). It covers 5 distinct personas with different primary questions, but they share 4 tabs. The experience is the container; the persona determines the landing state, default sort, and primary action.

**Users:** Connor (Demand Planner) · Chase (Sales Analyst) · Ethan (Forecast Ops) · Jeff (FSVP Finance) · Bracken (CFO)

**Cadence:** Weekly forecast review; monthly forecast cycle; JBP / line-review prep

**Actions available:** Override customer forecast · log distribution wins/losses/delists · tag risks and opportunities · lock forecast version · export to JBP deck

---

## Phase 1 vs. Phase 2 — what's available now

| KPI | Phase 1 (SPINS only) | Phase 2 (needs NetSuite + crosswalks) |
|-----|---------------------|--------------------------------------|
| E1 13-week forecast (units/bars) | ✓ | — |
| Base velocity (Base Units ÷ # Stores Selling) | ✓ | — |
| Distribution: # Stores Selling, TDP, ACV % | ✓ | — |
| Distribution change events (logged wins/losses/delists) | ✓ | — |
| Velocity (POS $ or units ÷ stores × weeks) | ✓ | — |
| ARP / price trend | ✓ | — |
| Promo lift (Base vs. Incr Units) | ✓ | — |
| Forecast vs. prior version (week-over-week delta) | ✓ | — |
| Week-over-week anomaly flags (>15% change) | ✓ | — |
| Forecast accuracy (wMAPE at 4-week lag) | ✓ | — |
| Gross sales (shipped units × list price) | — | ✓ |
| Net sales (gross − trade deductions) | — | ✓ |
| Trade rate / Gross-to-Net bridge | — | ✓ |
| Sell-in vs. sell-through gap | — | ✓ (needs ERP shipments) |
| YoY revenue % | — | ✓ |

**Implication:** Phase 1 delivers a strong velocity + forecast + distribution experience. Revenue $ figures and the Gross-to-Net Bridge tab come in Phase 2. The Distribution Tracker and Customer Scorecard (POS side) are fully buildable now.

---

## The 4 tabs

### Tab 1 — Book of Business
*All customers. The portfolio-level view.*

**What's on screen:**
- One row per customer, sortable by: Forecast vs. plan gap (default) · Net sales $ · YoY growth · Velocity trend · Distribution change
- Columns: Customer name · Forecast (next 4 / 13 weeks, units) · vs. prior version Δ · # SKUs · # Stores Selling · Distribution events this week · Base velocity (4-week avg) · [Phase 2: Net sales actual vs. plan · Trade rate]
- Risk flag chips inline per row: "forecast down >15%" / "stores lost" / "new delist" / "low confidence"
- Header summary tiles: Total forecast Δ vs. prior week · Accounts with distribution events · Accounts at risk vs. plan
- Download: cross-account demand summary table (SKU × customer × week, 13 weeks)

**Phase 1 fully buildable.** Revenue $ columns show placeholder until Phase 2.

---

### Tab 2 — Customer Scorecard
*One customer at a time. Connor's primary tab.*

**What's on screen:**
- Customer selector (search or click from Book of Business row)
- KPI tiles at top (6): Base velocity (4w) · Forecast next 13 weeks (units) · vs. prior version Δ · # Stores Selling · Distribution events (win/loss/delist count this week) · [Phase 2: Net sales vs. plan]
- Forecast chart: 52-week actuals + 13-week forward with confidence band; prior version overlaid as dotted line; anomaly weeks highlighted
- SKU breakdown table: one row per SKU; columns: units (4w actual) · base velocity · forecast (13w) · # Stores Selling · ARP · distribution event flag
- Distribution change panel: wins / losses / delists with effective date and stores affected
- Mo Chat entry: "What changed at Kroger this week?" → "What / So What / Now What" response
- Override panel: adjust any SKU × week cell with reason code; overrides versioned into E1 automatically
- Monday download button: CSV demand table for this customer (SKU × week × forecast, 13 weeks) — replaces Connor's Excel

**Phase 1 fully buildable.**

---

### Tab 3 — Distribution Tracker
*Doors, TDP, wins/losses. The leading indicator view.*

**What's on screen:**
- Distribution over time chart: # Stores Selling and TDP by SKU, trailing 52 weeks + events plotted
- Change event feed (most recent first): type (authorization / delist / reset / SKU swap) · effective date · customer · SKU · stores affected · entered by
- Heat map: SKU × account, color = distribution coverage (fully stocked / partial / not selling)
- New authorization tracker: SKUs recently authorized but not yet at full distribution — shows ramp progress vs. expected
- Log distribution event button: opens form → type, customer, SKU, effective date, stores, notes → stored with audit trail

**Phase 1 fully buildable.** No ERP dependency.

---

### Tab 4 — Gross-to-Net Bridge
*Revenue waterfall. Phase 2 only.*

**What's on screen (Phase 2):**
- Waterfall chart: Gross → off-invoice → bill-back → scan → slotting → MDF → returns → Net (per customer × period)
- Trade rate % by mechanic, trended over 12 months
- Forecast bridge: E1 units × list price = gross forecast; E3 trade rates applied → net forecast
- Sell-in vs. sell-through gap: ERP shipment units vs. SPINS POS units (trailing 4/13 weeks); implied retailer weeks of supply
- YoY net sales comparison

**Phase 2 only — requires NetSuite ERP invoices + trade deduction records + Customer ↔ Retail Account crosswalk.**

---

## Per-persona: landing state and primary action

### Connor — Demand Planner
**Lands on:** Customer Scorecard, last-viewed customer  
**First thing he sees:** Anomaly flags on the forecast vs. last week — which accounts moved >15%  
**Primary action:** Review changes → override if wrong → download Monday CSV  
**Key metric always visible:** Base velocity (4-week rolling, current vs. 13-week avg)  
**Mo Chat:** "What changed at Kroger for Cookies & Cream this week?" → narrative summary  
**Monday download:** CSV, same shape as his existing Excel output (SKU × customer × week × forecast, 13 weeks)  
**Does not need:** Revenue $, trade rate, Gross-to-Net tab  

### Chase — Sales Analyst
**Lands on:** Book of Business, sorted by forecast vs. plan gap (worst first)  
**First thing he sees:** Which accounts are most at risk this week  
**Primary action:** Triage risk list → log distribution events → tag risks/opportunities per account  
**Key metric:** Forecast vs. prior version Δ across all accounts; distribution event count this week  
**Download:** Cross-account demand summary by SKU × week  
**Does not need:** Revenue $, Gross-to-Net tab  

### Ethan — Forecast Ops / Consolidator
**Lands on:** Book of Business, all accounts, consolidated view  
**First thing he sees:** Aggregate forecast for the week; which accounts still have pending overrides  
**Primary action:** Review consolidated demand → lock as named version snapshot (e.g., "2026-09 v3") → one-click PDF  
**Key requirement:** Audit trail on every number — drill any cell to see source query + training run date  
**Version history panel:** Prior named versions with date, who locked, PDF link  
**Does not need:** Revenue $, Gross-to-Net tab  

### Jeff — FSVP Finance
**Lands on:** Custom dashboard — accuracy KPI at top, then risk-flagged accounts  
**First thing he sees:** wMAPE trend over past 12 cycles (is the model improving?); accounts flagged as high-risk this cycle  
**Primary action:** Review accuracy trend + risk flags → drill any suspicious number to audit trail  
**Receives separately:** Full demand intelligence report every 4 weeks (auto-generated, not the UI)  
**Does not need:** Distribution log, override panel  
**Phase 2 addition:** Revenue vs. AOP; Gross-to-Net bridge  

### Bracken — CFO
**Does not log in.**  
**Receives:** Auto-generated one-page PDF every 4 weeks, by email or shared link  
**PDF structure (What / So What / Now What):**
- **What:** Revenue forecast vs. plan — X weeks out, variance is +/−Y%; top 3 variance drivers by account
- **So What:** Cannibalization risk flag (if new SKU is taking from existing); distribution change impact; forecast accuracy trend (is confidence improving?)
- **Now What:** 1–3 recommended actions (e.g., "Accelerate 12-pack distribution at Kroger; reduce 4-pack promo spend — elasticity says it's not working")

**Status:** Not built. Requires demand intelligence report auto-generation + executive summary template + delivery mechanism.

---

## Shared UI rules for Experience 1

- **Version always visible:** Named forecast version in header; alert if viewing a non-current version
- **Phase badge on Phase 2 features:** Gray "Coming in Phase 2" chip on revenue $ columns and Gross-to-Net tab — not hidden, not broken-looking
- **Anomaly flags:** Inline chips, not a separate alerts page. Red = >15% forecast change or delist. Amber = >8% or store loss.
- **Audit trail:** Any number can be right-clicked → "Show source" → query lineage + training run date + model version
- **Mo Chat:** Persistent entry at bottom of Customer Scorecard. Grounded in account + SKU context of the current view. Responds in "What / So What / Now What" when asked about changes.
- **Override logging:** All overrides require reason code. Overrides are versioned and appear as a dotted overlay on the forecast chart.
- **Masking:** This experience is NOT masked. Full customer and trade detail. Costs and BOM are hidden.

---

## What's needed to build Phase 1 of this experience

| Component | Status | Notes |
|-----------|--------|-------|
| E1 demand forecast (units × account × week) | Done (MO_53) | Retrained weekly on SPINS refresh |
| Base velocity query | Prototype (MO_70) | Needs permanent Mo UI integration |
| Distribution change event log | Not built | Sales-entered; needs form + storage |
| Anomaly detection (>15% week-over-week flag) | Not built | Simple threshold query on forecast delta |
| Forecast version locking | Architecture defined | Implementation needed |
| Monday CSV download | Not built | Same shape as Connor's Excel output |
| Mo Chat (account + SKU context) | Exists in Mo | Needs account+geo proactive key wiring |
| Audit trail per number | Architecture defined | Implementation per cell |
| Executive summary PDF (Bracken) | Not built | Design first; What / So What / Now What |

---

*Companion documents:*  
- `docs/aevah-packaged-experiences-v2_Clauderesponse.md` — full KPI formulas, sources, grains for all 8 Sales KPIs  
- `docs/aevah_full_process_description.md` — per-persona primary question, output, format  
- `docs/aevah_process_strategy.html` — visual process overview (shareable)
