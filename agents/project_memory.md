# Project Memory

Last synced: 2026-06-04

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
- `docs/Mo_Build_Field_Guide_price_elasticity_addendum.md`: price elasticity module guide.
- `docs/built_cannibalization_druid_ml_plan_3.md`: current detailed Druid/ML query plan.
- `mockups/mo_intelligence_suite_v12.html`: latest Mo intelligence suite mockup.

## Recent Commits

- `919431e` — Initial BUILT Mo preview project.
- `77717ec` — Add query purpose explainer page.
- `1a8c196` — Add Druid to UI ML playbook.
- Pending — Add durable project memory and commit-time memory sync instruction.

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

## Open Follow-Ups

- Confirm the actual Druid datasource name for the uploaded 97M-record SPINS table.
- Confirm production field names and whether they match the expanded SPINS extract.
- Confirm which Druid outputs will be materialized first for the pilot.
- Decide whether the visual HTML pages should be linked from `README.md`.
