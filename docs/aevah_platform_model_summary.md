# Aevah Platform — Model & Data Architecture Summary

**Prepared:** September 9, 2026  
**For:** Rob Long / BUILT team  
**Context:** Response to Rob's standup question — "For each of the 7 use cases, what is the process? Data into Druid, what to extract for each model, how many models to train?"

---

## The short answer

**3 ML engines, not 21 models.** All 7 experiences share the same 3 engines and render their outputs differently per audience. Everything else is deterministic SQL calculation against Druid.

---

## The 3 engines

| Engine | What it produces | Current status |
|--------|----------------|----------------|
| **E1 — Demand Forecast** | Bars by SKU × week, 13-week forward, confidence bands | Built (MO_53 global LightGBM) — retrained weekly on SPINS refresh |
| **E2a — Cannibalization** | Cross-SKU displacement matrix: who steals volume from whom, and how much | 48% of combos scored (MO_55); architecture complete |
| **E2b — Price Elasticity** | Own-price elasticity (ε) per SKU; optimal price range | ~156 fitted models (MO_16/17); architecture complete |

Everything else — promo baseline (SPINS provides this directly), competitive share/distribution, BOM explosion, accuracy metrics — is **Druid SQL at query time**. No additional models.

---

## What each of the 7 experiences needs

| # | Experience | Audience | Engines needed | Phase | Blocking gap |
|---|-----------|----------|---------------|-------|-------------|
| 1 | Customer Growth | Sales team | E1 + ERP invoices | 2 | NetSuite → Druid (Justin Fisher) |
| 2 | Build Plan | Production S&OP | E1 only (masked) | **1 — ready now** | None |
| 3 | Material Plan | Procurement | E1 + BOM data | 3 | BOM/recipes → Druid |
| 4 | Financial Scenarios | Finance / CFO | All 3 + ERP cost | 2 | NetSuite cost + AOP → Druid |
| 5 | Trade Accrual Planner | Accounting | E1 + trade contracts | 2 | Trade terms + deduction ledger |
| 6 | Analytics Workbench | BI team | All 3 + SPINS competitive | **1 — ready now** | None |
| 7 | Brand & Launch | Marketing | E1 + E2 + SPINS | **1 — ready now** | None |

---

## What goes into each model (Druid extract)

All three engines pull from the same Druid table — `built_filtered_weekly` (SPINS data, all brands).

| Engine | Key columns extracted | Approx rows |
|--------|----------------------|-------------|
| E1 Demand | EQ Units (target), TDP, ARP, Base Units, Incr Units, promo week flags, # Stores Selling, First Week Selling, FRED macros | ~1M rows (156 SKUs × 80 retailers × 78 weeks) |
| E2a Cannibalization | All own-brand UPCs simultaneously; cross-UPC lagged units at same retailer × week | Same table, pivoted wide |
| E2b Elasticity | ARP, ARP_promo, ARP_non_promo, EQ Units, TDP, promo_week indicator | Per-SKU subset; ~80 retailers × 78 weeks each |

**Costco / Circana** feeds E1 only via a separate table (pallet-level, 909 warehouses, 192 weeks). No competitive data, no E2 needed.

---

## Phase sequencing

**Phase 1 — SPINS data (available now):**  
Experiences 2 (Production), 6 (BI), 7 (Marketing) are fully enabled. Experience 1 (Sales) gets velocity + distribution but not manufacturer revenue. All 3 ML engines can train and score.

**Phase 2 — NetSuite → Druid (Connor + Justin Fisher's active project):**  
Enables Experiences 1 (full gross/net sales by customer), 4 (Finance scenarios), 5 (Accounting trade accrual). Requires 3 crosswalks in Druid first (see below).

**Phase 3 — BOM + supply data → Druid:**  
Enables Experience 3 (Procurement full material requirements), Finance capacity triggers.

---

## The 3 crosswalks that gate ERP data

These must exist in Druid with effective dates before NetSuite data can flow into the right experiences:

1. **SKU ↔ UPC** — BUILT internal item code to SPINS barcode (including pack hierarchy, variety pack components, effective dates for UPC changes). Source: Item_Assumptions tab from Brands LE model.

2. **Customer ↔ Retail Account** — ERP bill-to/ship-to to SPINS Retail Account (e.g., all Kroger banners → KROGER). Source: Customer_Assumptions tab.

3. **Customer-Retailer-Distributor bridge** — Level 1 (who BUILT ships to: DotFoods, UNFI, Coremark) → Level 2 (where it ends up: YesWay, etc.). This is the most important architectural gap. Revenue is only visible at Level 1. SPINS maps to Level 2. Connor maintains this manually today; it needs to live in Druid with effective dates so historical attributions stay correct when retailers switch distributors.

---

## What "the data wrangling" actually is

The ML pipelines are largely built. The bottleneck is not model training — it's the crosswalks and the ERP ingest. In order:

1. Crosswalk 1 (SKU↔UPC): formalize what's in Item_Assumptions → load to Druid
2. Crosswalk 2 (Customer↔Retail Account): formalize Customer_Assumptions → load to Druid  
3. Crosswalk 3 (Distributor bridge): Connor's manually maintained tab → Druid with effective dates
4. NetSuite invoices + shipments → MinIO → Druid (Phase 2 unlock)
5. BOM/recipes → MinIO → Druid (Phase 3 unlock)

Each step above unlocks a new set of experiences.

---

*Full detail in wiki: `wiki/15-aevah-platform-architecture.md`*  
*Data request spec: `docs/aevah_client_internal_data_request.md`*  
*SPINS source mapping: `docs/aevah_spins_kpi_source_mapping.md`*
