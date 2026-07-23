# Aevah: Platform, Pipeline, and the LLM Boundary

**What Aevah is, what it does that an LLM cannot, and how raw third-party CPG data becomes a live predictive decision surface.**

Status: living reference · Audience: internal, stakeholder, finance/sales enablement

---

## 1. The one-sentence thesis

Aevah is a governed data-and-ML platform that turns raw third-party syndicated CPG data (SPINS / Circana / IRI), fused with the client's live enterprise systems (ERP, POS), into predictive, explainable, operational decision surfaces. **The LLM handles language — interface, narration, code generation — and is deliberately barred from computing or serving any number a business decision rests on.**

**Aevah is the product.** *Mo* (for BUILT) and *Oliver* (for Mt Olive) are branded experiences layered on the same platform.

---

## 2. Two customers, one architecture

The clearest proof that Aevah is a platform and not a prompt: two customers run on the same spine, with the LLM swapped like a faceplate.

|                       | **BUILT**                     | **Mt Olive**                                 |
| --------------------- | ----------------------------- | -------------------------------------------- |
| Branded experience    | **Mo**                        | **Oliver**                                   |
| POS data vendor       | SPINS (~95–97M rows, ~51GB)   | Circana / IRI                                |
| UI                    | `customer-built-mo-ui`        | `mtolive-oliver` (React/Vite)                |
| API                   | `customer-built-mo-api` (FastAPI) | `mtolive-api` (NestJS gateway)           |
| Extra app             | —                             | `mtolive-promo-hub` (promo planning)         |
| Store                 | Apache Druid                  | Apache Druid (star schema: `dim_*`/`fact_*`/`map_*`) |
| LLM surface           | Mo Chat                       | `src/lib/llmProvider.ts`                     |
| ML build-out          | Full ensemble pipeline (live) | Governed gateway + salesplan forecasts; ML pipeline on roadmap |

**Same spine every time:** `Druid → governed SQL/ML → thin API gateway → React → one narrow, branded LLM lane.` The vendor, schema, and brand change; the architecture does not.

---

## 3. Why not just have Claude do this?

Every layer between raw data and a served result resists the LLM for a concrete reason:

| Layer | Why an LLM can't own it |
| --- | --- |
| Aggregating tens of millions of POS rows | Exceeds any context window; this is columnar OLAP (Druid) work |
| Producing the numbers (probabilities, elasticities, forecasts) | Models are *fit* to data and calibrated; an LLM emits plausible, not correct, numbers. PRD goal: **"No fabricated numbers anywhere in the UI."** |
| Reproducibility & audit | Same input → same output, with `model_version`, `scored_at`, provenance, confidence, scoring window. LLMs are non-deterministic and can't be tied to lineage |
| Governed data access | Query whitelisting, credential isolation, injection-safe params — no free-form generator touches the engine |
| Deterministic state | Append-only event persistence, async ingestion tasks, task-status polling |
| Automation & live integration | Schedulers, connectors, CDC, drift monitors, retraining triggers |
| Enterprise plumbing | SSO (Azure AD/OAuth/MSAL), deploys (Azure SWA, ArgoCD), caching, rate limiting |

**Where the LLM legitimately lives:** Mo Chat / Oliver's `llmProvider.ts` (natural-language interface and narration of numbers the pipeline already computed), and the dev-time agents (e.g. "Brad") that generate code, SQL, and docs — which are then executed and reviewed by deterministic systems.

Mt Olive's API encodes the boundary as architecture, not just intent. From `mtolive-api/BLUEPRINT.md` / `AI_CONTEXT.md`:

- *"Not a direct proxy that lets the browser run arbitrary SQL."*
- Whitelisted query keys only; **reject unknown keys.**
- *"Do not expose Druid credentials or allow direct browser SQL execution."*
- Escape params / injection handling; stable `{ rows: [...] }` contracts.

The query whitelist **is** the anti-"let Claude write the SQL" pattern, expressed in code: a generated query is untrusted by construction; only pre-authored, reviewed templates run.

---

## 4. The pipeline: raw feed → predictive decision surface

Seven stages take a syndicated data drop to an operational interface. (BUILT/Mo is the fully built-out instance; references below are to `docs/`, `../scripts/`, and `../specs/`.)

### Stage 1 — Ingest & govern
Syndicated extract lands in Druid at grain **UPC × geography/account/channel × week** (~97M rows for BUILT). Audit completeness, row counts by week/brand/geo, null rates, duplicate keys, impossible prices, UPC-format quirks. The feed is **kept whole** — competitor/category rows preserved, never filtered to the client's own brand, because cannibalization and price response are only measurable against the category.
→ `mo_ml_playbook_from_druid_to_ui.md` (Stages 1–2), `mo_ml_field_notes.md`

### Stage 2 — Enrich & build feature tables *in the database*
Raw rows become business language (product families, pack ladders, flavors, accounts, calendar, promo events), materialized into governed Druid feature tables (`built_filtered_weekly` → `built_enriched_weekly` → `built_prepost_features`, `comparison_pool_weekly`, `price_elasticity_training_features`). **Rule: do not train directly on unprepared raw rows.** The heavy aggregation happens in Druid via MSQ (`../scripts/mo_druid_client.py`), not in Python and never in a model.

### Stage 3 — Train a model *stack*
A model zoo, each matched to a job (`../scripts/MO_10`–`MO_49`):

- **LightGBM classifiers** — cannibalization (CANNIBALIZING / INCREMENTAL / WATCH). Labels are feature-derived → ROC-AUC ≈ 1.0; "no further splits" warnings are expected (`feedback_ml_lgbm_patterns.md`).
- **LGBMRanker / LambdaRank** — donor ranking (which existing SKU is losing sales).
- **LightGBM quantile regression (q10/q50/q90)** — demand forecasting with confidence bands.
- **Price-elasticity regression** — implied elasticity, promo-confounding flags.
- **Classical time series** — Prophet, ETS (Holt linear trend), 4wk/13wk moving averages, naive.
- **Deep-learning benchmarks** — N-BEATS global (`MO_32A`), GRU; plus causal-impact, DAG analysis.

### Stage 4 — The ensemble pattern: a data-maturity *router*
Aevah's ensemble is **not a blended average — it's a router keyed on data maturity** (`../scripts/MO_34_ensemble_trigger.py`):

> *"Route new/expanding series to ETS, mature series to LightGBM… use ETS when it wins, LGB otherwise."*

- New SKUs (short history) → ETS wins; a boosted model has no signal to learn.
- Mature series (≥52 weeks) → LightGBM reaches **~4.4% wMAPE**; ETS can't compete.
- Trigger rule = *weeks-of-training-history*, mapping directly to the product's three-tier confidence model **EARLY / PARTIAL / FULL**.

A single SKU is automatically served by a different model as it ages, and the UI never shows a blank screen — it shows a lower-confidence method with an honest label. This routing logic is real IP.

### Stage 5 — Validate to a finance-defensible standard
Out-of-sample backtesting the way an FP&A skeptic would demand:

- `MO_30` — train on 2024, predict all of 2025: **69 OOS weeks, full seasonal cycle**, a 6-model horse race including a naive baseline that stands in for "basic Excel extrapolation," scored side-by-side against the finance team's actual spreadsheet.
- `MO_31` — walk-forward validation.
- `MO_28` — MAPE / wMAPE / pinball + SHAP + actuals-vs-predicted per series.

The point is not just accuracy — it's *proving* accuracy out-of-sample so the number survives scrutiny from a VP of Finance.

### Stage 6 — Explain every prediction
SHAP (TreeExplainer) runs per prediction, and the **top-3 SHAP features are written into the scored rows** (`shap_feature_1/2/3`, `shap_value_1/2/3` — see `../specs/scored_cannibalization_ingest_spec.json`). Every ML output ships with its own reasons attached.

### Stage 7 — Score, write back, serve
Two deliberately separate pipelines: **training** excludes undercooked SKUs (<8 weeks) so they don't distort weights; **inference/scoring** includes *all* active UPCs (LightGBM handles NULLs natively). Scored outputs land in MinIO/S3 as parquet, ingest back into Druid via MSQ, each row carrying `model_version`, `scored_at`, `confidence`, scoring window, provenance. FastAPI reads the scored tables; the React UI presents them through **Determine / Diagnose / Decide** with confidence bands and deterministic evidence beside the ML scores. Forward projection (`MO_35`) even carries the forecast past the data's edge — *"where is BUILT right now, 9 weeks after our last SPINS week"* — with q10/q50/q90 bands.

---

## 5. Live integration & automation: a standing machine, not a one-time build

Per `brad_aevah_spins_processing_value_overview.md`, this is delivered as **"operational rather than one-time analysis."**

### Two data velocities, fused

| Source | Velocity | Contributes |
| --- | --- | --- |
| SPINS / Circana / IRI (syndicated) | Weekly / monthly / quarterly, lagged | Category + competitor truth, market context |
| **ERP** (orders, shipments, revenue alloc) | Live / transactional | What actually moved, ahead of syndicated reporting |
| **POS** (retailer scan feeds) | Daily / weekly | Real sell-through before it appears in syndicated data |
| Enterprise (sales plans, launch calendars, promo commitments) | Live | Operational intent — what the team is about to do |

Syndicated tells you *where you stand in the category*; ERP/POS tells you *what's happening right now*; the models close the gap. Mt Olive already runs a live first-party loop: `POST /plans/:planId/save` → async MSQ ingestion → append-only `app_plan_events`, sitting beside `fact_salesplan_forecast` / `fact_salesplan_revenue_alloc`.

### Automated refresh on the data's own cadence

```
new feed arrives
  → intake & register (source, date, version, row count, status)   ← auditable lineage per feed
  → validate schema & completeness (columns, row-count ranges, week-ending dates, dupes)
  → incremental load into Druid (MSQ)
  → rebuild feature tables + weekly delta / LAG signals             ← brad_druid_sql_weekly_delta_features.sql
  → repopulate scored tables (cannibalization, elasticity, forecast)
  → retrain / roll forward per the data-maturity router
  → publish governed, versioned outputs to Mo / Oliver
  → monitor feed freshness, data quality, model freshness, scoring stability
```

### Cadence-matched retraining is validated, not aspirational
`MO_32B_quarterly_rollforward.py` is a **rolling-origin retraining simulation**: retrain each quarter as new SPINS arrives, predict the next 13 weeks, advance, repeat across five windows — with a **stale-model comparison** that puts a number on what automated retraining is worth. It answers the client's operational question directly: *"if we retrain every quarter, does accuracy improve, and by how much?"* A SKU's serving model, confidence tier, and retrain cadence all advance automatically as history accumulates.

### Build state (honest)
- **Live / built:** recurring syndicated-feed reprocessing, versioned intake, feature/score repopulation, Mt Olive transactional plan-save loop.
- **Validated in simulation:** quarterly rolling retrain + stale-model value (`MO_32B`), forward projection past data edge (`MO_35`).
- **Architected / roadmap:** full streaming ingestion from ERP/POS via **Kafka + Python feature pipelines** — per `mtolive-api/BLUEPRINT.md`, plugs in *"without changing the browser-to-DB contract"*; `ROADMAP.md` "Later." The thin-gateway design exists so live sources can be added under the API the UI already consumes.

---

## 6. Bottom line

Aevah converts a static third-party data drop into a **living predictive system** — governed at ingest, modeled by an ensemble that adapts to each SKU's data maturity, validated out-of-sample against real actuals, explained per-prediction, written back as versioned auditable facts, and **kept continuously current** against both syndicated and live enterprise data.

None of that is LLM work: an LLM can't aggregate 97M rows, fit a quantile model, run a 69-week backtest, route by data maturity, detect a dropped column in this week's feed, run an idempotent incremental load, or decide a model has gone stale and retrain it. What Aevah sells is the standing, self-refreshing machine. **Mo and Oliver are how each customer talks to theirs — Aevah is the thing that's actually working.**

---

### Source artifacts

- Pipeline & governance: `mo_ml_playbook_from_druid_to_ui.md`, `mo_ml_field_notes.md`, `mo_python_ml_register.md`
- Value / operational model: `brad_aevah_spins_processing_value_overview.md`, `brad_druid_sql_weekly_delta_features.sql`
- Models & ensemble: `../scripts/MO_30_multi_model_backtest.py`, `MO_32B_quarterly_rollforward.py`, `MO_34_ensemble_trigger.py`, `MO_35_forward_projection.py`, `MO_28_v2_eval.py`, `MO_32A_nbeats_global.py`
- Scored contracts: `../specs/scored_cannibalization_ingest_spec.json`, `../specs/scored_price_elasticity_ingest_spec.json`
- LLM boundary (Mt Olive): `mtolive-api/BLUEPRINT.md`, `mtolive-api/AI_CONTEXT.md`, `mtolive-api/ROADMAP.md`
- Product framing: `customer-built-doc/PRD.md`
