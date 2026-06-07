# Project Memory

Last synced: 2026-06-06 (session 3 — P3 added; Q2 all batches complete; next: Q2b → Q2c → Q3)

## Repository

- Local workspace: `/Users/jasonbrazeal/Documents/FirstAgent`
- GitHub repo: `https://github.com/theroblong/built-mo-preview.git`
- Main branch: `main`
- GitHub account used for pushes: `brazealboy1`
- Local git commit identity:
  - name: `theroblong`
  - email: `brazealboy1@gmail.com`

## Durable Instruction

Before every commit that is intended to be pushed to GitHub, update this file
with any meaningful new project context, artifacts created, decisions made,
open questions, and latest commit notes. Include the memory update in the same
commit as the related work.

## Current Project Context

This project is a planning, documentation, and mockup package for Mo by BUILT:
an intelligence suite that uses SPINS weekly POS data in Apache Druid to support
product cannibalization, price elasticity, pack-ladder, competitive pricing,
assortment, and launch decisions.

The project assumes approximately 97M SPINS records have been uploaded into
Druid in a single datasource using SPINS table format. The operating flow is:

1. Govern and audit the raw Druid datasource.
2. Normalize and enrich SPINS rows with product, flavor, pack, market, calendar,
   and event context.
3. Build Druid feature tables rather than sending raw rows directly to ML.
4. Assemble comparison pools, pre/post features, labels, event features, and
   price elasticity features.
5. Train focused ML models for cannibalization classification, donor ranking,
   event detection, and price elasticity/forecasting.
6. Validate with statistical fit testing and business review.
7. Publish scored outputs back to Druid.
8. Present the results through the Mo UI using Determine / Diagnose / Decide.
9. Monitor drift, user feedback, and retraining needs.

## Important Artifacts

- `README.md`: repository overview and documentation map.
- `agents/brad.yaml`: agent persona and durable working instructions.
- `agents/project_memory.md`: durable project memory and commit-time sync rule.
- `docs/mo_feature_hierarchy_chart.md`: feature hierarchy reference.
- `mockups/mo_feature_hierarchy_chart.html`: visual feature hierarchy chart.
- `docs/mo_query_purpose_intent_need_outcome.md`: query purpose explainer.
- `mockups/mo_query_purpose_intent_need_outcome.html`: visual query explainer.
- `docs/mo_ml_playbook_from_druid_to_ui.md`: Druid-to-UI ML playbook.
- `mockups/mo_ml_playbook_from_druid_to_ui.html`: visual stage-by-stage ML playbook.
- `docs/mo_druid_query_register.md`: actual Druid SQL register linked from playbook query IDs.
- `mockups/mo_druid_query_register.html`: browser-friendly query register for testing query-anchor navigation from the playbook.
- `docs/mo_druid_error_register.md`: running log of Druid query errors encountered during live testing, with root cause and remedy for each.
- `mockups/mo_druid_error_register.html`: browser-friendly version of the error register.
- `docs/Mo_Build_Field_Guide_price_elasticity_addendum.md`: price elasticity module guide.
- `docs/built_cannibalization_druid_ml_plan_3.md`: current detailed Druid/ML query plan.
- `mockups/mo_intelligence_suite_v12.html`: latest Mo intelligence suite mockup.

## Recent Commits

- `919431e` — Initial BUILT Mo preview project.
- `77717ec` — Add query purpose explainer page.
- `1a8c196` — Add Druid to UI ML playbook.
- `e3fe9e5` — Add durable project memory and commit-time memory sync instruction.
- `c0a560f` — Add actual Druid query register and wire playbook query IDs to register anchors.
- `20cdd21` — Add one-click SQL copy controls to the Druid query register mockup.
- `b9a7496` — Druid query/error register updates: maxNumTasks=4, durableShuffleStorage, E19/E20, Q0/Q1/QS complete, Q2 batch progress.
- Pending — P3 added to both registers; Q2 all 3 batches COMPLETE (29,813,824 rows total); Q2b queued next.

## Druid Cluster Constraints (discovered during live testing)

- Druid Lookup tab returns 403 — Lookup API is not accessible with current role.
- EXTERN function (inline or HTTP) returns FORBIDDEN — external data source reads are blocked.
- UNION ALL with literal SELECT rows (no FROM) returns INVALID_INPUT — only supported between real datasources.
- ORDER BY on non-time columns at the top level of a query is not supported, even ORDER BY __time, other_col. Only bare ORDER BY __time is allowed at the top level.
- Workaround for lookup table ingestion: read from spins_full using DISTINCT UPC/Brand subquery and embed all curated values as CASE expressions. No extra permissions needed.
- Q0 times out if run as OVERWRITE ALL on the full 62.9M-row WELLNESS & NUTRITION BARS dataset (~1.5h cluster limit). Use OVERWRITE WHERE with annual time-range batches.

## Druid Schema Facts (confirmed from spins_full)

- Raw datasource: `spins_full` (~97M rows).
- BUILT brand rows: ~914K total; 99.8% in subcategory WELLNESS & NUTRITION BARS; 0.2% (BUILT BAR only) in GRANOLA & SNACK BARS.
- WELLNESS & NUTRITION BARS total rows: ~62.9M (BUILT + all competitors in that subcategory).
- GRANOLA & SNACK BARS total rows: ~34.9M.
- Column naming: SPINS columns use spaces not commas — e.g., "Units Yago" not "Units, Yago", "TDP Any Promo" not "TDP, Any Promo", "Units % Lift TPR" not "Units ,% Lift, TPR".
- __time in spins_full already holds the correct week-end date (ISO timestamp). Use __time directly; do not re-parse "Time Period End Date".
- "First Week Selling" in spins_full is ISO format (yyyy-MM-dd), not MM/dd/yyyy. Queries that TIME_PARSE this field must use 'yyyy-MM-dd' format.

## Lookup Table Design Decisions

- flavor_mapping: 91 BUILT SKUs from built_specific_flavor_mapping.csv. Ingested via QS1 using spins_full DISTINCT UPC subquery + CASE expressions.
- flavor_canonical_overrides: 4 rows fixing CSV errors: UPC 08-40229-30034 (CARAMEL), 08-40229-30115 (PEANUT BUTTER), 08-40229-30394 (BROWNIE), 08-40229-30395 (BROWNIE). Ingested via QS2.
- item_catalog: Changed from UPC-keyed to brand-keyed design. 30 competitor brands with tiers 1/2/3. Q2 and Q2b join on c.source_brand = ic.brand (not c.upc = ic.upc). Ingested via QS3.
- QS1v: validation query — runs after QS1, returns 0 rows if all 91 flavor_mapping rows match the CSV exactly. Confirmed clean.

## Decisions and Conventions

- Project memory now lives at `agents/project_memory.md`.
- Every commit intended for GitHub should first update `agents/project_memory.md`
  and include that memory update in the same commit.
- Use Druid to aggregate the raw 97M-row datasource into governed feature tables
  before ML utilization.
- Do not train directly on unprepared raw SPINS rows.
- Preserve competitor/category context; do not reduce the source to BUILT-only
  at ingestion.
- Keep deterministic evidence visible beside ML scores in the UI.
- Present user workflows as Determine / Diagnose / Decide.
- Treat `Units/TDP` carefully; prefer clearer store/productivity measures already
  selected in the UX-safe metric shortlist.
- Use explicit confidence, provenance, model version, scoring window, and source
  fields for every scored recommendation.
- Current raw Druid datasource name is `spins_full`; Q0 in the query register is
  the single place to update when that source name changes.
- Supporting Druid query explanations should live inside the relevant playbook
  stage, under the Executive View / Technical Work area, while query IDs link to
  the register for actual SQL testing.
- The browser-friendly Druid query register should include a copy control on
  each query card so users can copy a single query body for Druid console testing.

## Query Testing Status (as of 2026-06-04)

- QS1 (flavor_mapping, 91 rows): SUCCESS. QS1v validation returned 0 rows — perfect match.
- QS2 (flavor_canonical_overrides, 4 rows): queued — not yet confirmed.
- QS3 (item_catalog, 30 brands): queued — not yet confirmed.
- Q0 Batch 1 (2023): SUCCESS (succeeded silently despite 404 timeout error on status).
- Q0 Batches 2 and 3: not yet run.
- Q1: not yet run.
- Q2: STALLED — sortMerge resolves BroadcastTablesTooLarge but stalls at ~800K rows remaining out of ~62M due to local disk saturation from shuffle intermediate files. Email sent to Rob outlining root cause and 4 recommended SET commands. Awaiting his response before updating the register.

## Cluster Settings (approved and applied to Q2, Q4, Q5)

All four SET commands added to Q2, Q4, Q5 in the query register:
- SET sqlJoinAlgorithm = 'sortMerge' — switches from broadcast to shuffle-based sort-merge join
- SET durableShuffleStorage = 'true' — routes shuffle files to S3; also enabled cluster-wide by Rob
- SET sqlSortMergeDiskBuffered = 'true' — spills merge buffers to disk; complements durable shuffle
- SET maxNumTasks = 4 — adds parallelism (effective if cluster has multiple task slots)
- SET rowsPerSegment = 5000000 — increases output segment size from 3M to 5M rows

## Open Follow-Ups

- Reconfirm the raw Druid datasource name if it changes from `spins_full`.
- Decide whether the visual HTML pages should be linked from `README.md`.
- QS1, QS1v, QS2, QS3: ✓ COMPLETE
- Q0: ✓ COMPLETE (all 3 batches)
- Q1: ✓ COMPLETE
- Q2: ✓ COMPLETE (all 3 batches). Batch 1 (2023): 6,505,424 rows. Batch 2 (2024): 9,881,582 rows (+52%; BUILT SKU expansion). Batch 3 (2025-01-01→2027-01-01): 13,426,818 rows (2025: 9,633,392 / 2026: 3,793,426; 11h 12m). Grand total: 29,813,824 rows.
- Q2b, Q2c: QUEUED — will be tested immediately after Q2 completes, before Q3.
- Q8 subquery ORDER BY ABS(e.pack_count - n.pack_count) may fail — defer fix until Q8 is tested.
- Q9 and Q14–Q22 need CLUSTERED BY added when tested (same pattern as Q0–Q8).
- Q2b and Q2c ORDER BY clauses removed (cluster does not support non-time top-level sort); confirm UI behavior is acceptable.
