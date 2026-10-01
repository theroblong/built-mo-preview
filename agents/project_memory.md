# Project Memory

Last synced: 2026-09-30 (MO_77 v6 COMPLETE — 12 new features + n_estimators 2000 + full-data final retrain; retail_account #2 feature; Kroger holdout 14.3%; v6 chart archived)

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

## Documentation Artifacts (added 2026-06-16)

Five new reference documents added to `docs/` with browser-friendly HTML companions in `mockups/`:

- `docs/mo_messages_register.md` — canonical system prompts and user message templates (M1 Brad system prompt, M2–M4 parameterized invocation templates)
- `docs/mo_ml_field_notes.md` — operational ML findings: DQ1 focal pct_chg NULL; DQ2 Druid object dtype; DQ3 outlier histogram collapse; DQ4 ORDER BY forbidden; DQ5 column name mismatches in price_elasticity_training_features; LG1 LambdaRank sort; LG2 degenerate label warnings
- `docs/mo_built_spins_hierarchy.md` — SPINS attribute codes: pack size 1–4, protein 5–9, sugars 10–13, calories 14–18, sugar alcohols 19–20; panel data fields (Trips, HH Count, Buy Rate)
- `docs/mo_cannibalization_model_reference.md` — scored_cannibalization status thresholds; relationship_distance 1/3/4 meanings; cannibal_confidence = data maturity not model certainty; scoring coverage by channel; MinIO write-back pattern
- `docs/mo_vision_framework.md` — Brian's 7 questions; design principles; 4-question frame; Brian-style narrative template; priority screens; vision gaps backlog

README.md updated: all new docs added to core documents list (positions 18–22 in reading order) and to repo structure tree.

## Recent Commits

- `919431e` — Initial BUILT Mo preview project.
- `77717ec` — Add query purpose explainer page.
- `1a8c196` — Add Druid to UI ML playbook.
- `e3fe9e5` — Add durable project memory and commit-time memory sync instruction.
- `c0a560f` — Add actual Druid query register and wire playbook query IDs to register anchors.
- `20cdd21` — Add one-click SQL copy controls to the Druid query register mockup.
- `b9a7496` — Druid query/error register updates: maxNumTasks=4, durableShuffleStorage, E19/E20, Q0/Q1/QS complete, Q2 batch progress.
- `b9a7496` — (prior) Druid query/error register updates: Q2 batch progress, E19/E20.
- Latest push — Q2c COMPLETE (subquery + null-bucket fixes); Q3 COMPLETE (131 UPCs, 14,939 rows); flavor_mapping refresh needed (131 vs 91 UPCs); next: Q2d.
- Pending push — Q6–Q22 COMPLETE; full price elasticity section done; price_event_queue seeded with 3,345 deterministic events.
- 2026-09-30 — MO_77 v5: 4 new features (tdp_lag52, velocity_per_tdp, base_units_13wk_momentum, base_units_4wk_momentum) + recency-weighted training (λ=0.02). Full pipeline: MO_25 → MO_26 (v5 PKLs) → build_forecast_chart_data.py. Kroger holdout 15.7% (vs v4 15.5%) — flat within noise; Q1 2026 improved 41.2%→40.5%; recent quarters stable. velocity_per_tdp ranked #6 by split importance; 4wk_momentum ranked #7 — both new features immediately signal-bearing. Druid retry logic added to mo_druid_client.py (3× with exponential backoff). Auto-versioning added to build_forecast_chart_data.py; versions archived at mockups/versions/. SPINS actuals through Sept 6 2026.
- 2026-09-30 — MO_77 v6: 12 new v6 features — pack_count, retail_account, tdp_4w_momentum, top_donor_tdp_sum, competitor_price_gap, promo_lift_ratio, arp_dollar_discount, arp_lag1, week_sin/cos (annual), week_sin26/cos26 (semi-annual). n_estimators bumped 1500→2000; full-data _full.pkl retrain for production deployment. retail_account = #2 feature (gain 9,742) for base_units; #1 for total_units (gain 11,462). promo_lift_ratio = #5 for total_units. All models still hit n_estimators cap — v7 should bump to 3000. Results: Kroger holdout 14.3% (vs v5 15.7%, −1.4pp); Q4 2025 33.6% (vs 37.2%, −3.6pp); Publix holdout 12.0%; UNFI holdout 11.8%; Albertsons holdout 50.7% (structural NS2 issue unchanged). MO_27 updated: arp_lag1 bug fixed (was using [-1] instead of [-2]), week_sin/cos/26 dynamic, retail_account + pack_count categoricals, loads _full models for production. Backtest channel logic: RMA (CONVENTIONAL|FOOD) first; MASS MERCH RMA for club/mass; MULO fallback only. Per-retailer promo lift ratios logged (Kroger 153.1%, Publix 52.8%) — Brian wants these surfaced. Next: n_estimators 3000 for v7.

- 2026-10-01 — **v9 panel definition** (README update 195). New `scripts/mo_panel.py` holds ONE definition of `CAT_COLS` plus four panel rules, called in the same order by MO_26/27/28 and build_forecast_chart_data.py; applied at consumption so MO_25's parquet keeps every row. Rules: (1) **RMA priority** — retailer has RMA → use RMA only, CRMA only if no RMA, else keep KEY ACCOUNT/other store-level. Validated: CRMA UPC-set Jaccard across *different* retailers = 0.796 (shared MULO aggregate, not retailer-specific), and RMA pack mix matches each retail model (Kroger FOOD 78% singles; Walmart/Target MASS MERCH ~80% 4-pk; Sam's/BJ's CLUB 99–100% 13-pk). Volume check: implied bars/yr 515.7M (≈$1.3B retail) → 70.5M (≈$176M) — CRMA was a ~7.3× double-count. (2) military exclusion (AAFES/COAST GUARD/NEXCOM — 14,450 rows, exactly 0 units). (3) zero-volume geographies (17, incl. phantom AK/HI twins duplicating a real market's series key with 0 units). (4) conditional promo-mechanic null fill — `units_lift_*` null means 0 when no promo ran (79.8–99.3% of non-promo weeks) but genuinely unknown when a promo ran (41.6–86.6%); `units_lift_any_feature` 92.7% → 43.7% null. Panel: 186,427 → 96,153 rows, 1,716 series, 120 UPCs, 61.1M units, 23 real zero-sales weeks kept. **Flavour join fixed**: MO_25 filtered `source_brand = 'BUILT'` on built_enriched_weekly and got **2 UPCs** (that column holds the sub-brand); `parent_brand = 'BUILT'` → 146 UPCs. So v8–v9a had almost no flavour resolution; in v9a even un-normalised `spins_flavor_raw` ranked #3 by gain (8,680). Use `spins_flavor_canonical` (35, override-corrected) as the feature; `specific_flavor_normalized` (76, typo-corrected) for within-flavour pack comparison; never `spins_flavor_mapped` (misfiles Salted Caramel as CHOCOLATE). **`geography_raw` REJECTED as a feature** (supersedes updates 190/194): once phantoms are filtered it is 1:1 with retail_account × channel_outlet for 99.1% of rows. **Four divergent `CAT_COLS` copies** had silently killed `spins_flavor_canonical` + `source_brand` at inference since v8 (`str(nan or "UNKNOWN")` returns `"nan"` — NaN is truthy in Python). Guards added: version-stamped metrics + `model_version` assertion, `features_used` read from the booster, hard-fail on missing declared feature / zero series, unseen-category report. MO_28 killed at 25/60 (in-memory; v9 adds SQLite) — it was tuning on the unfiltered panel where 14.1% of rows were a point mass at log1p(0). OPEN: tree-budget mismatch (MO_26 n_estimators=4000 and hits the cap still improving; MO_28 caps at 2000 and writes that into lgbm_base_v9); `lag52` 100% null where weeks_since_launch<52 and 51.8% of rows are that young, yet SEASONAL_BLEND_WEIGHT=0.40 pulls toward lag52×YoY — the Q4 2025 miss mechanism, live; metrics NOT comparable across panels (v9a 0.01261 vs v8 0.01145 differ by val-set composition), so Albertsons 50.3% must be re-measured before justifying Prophet.

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

## New Product Design Principles (established 2026-06-07)

BUILT is a growing brand requiring near-real-time insight into new product performance. These principles apply specifically to products in `new_upc_candidates` (Q7) and any UPC with < 13 post-launch weeks.

**Mo must never show empty results.** Blank screens read as broken tools. Every product surfaces something actionable in Determine, Diagnose, and Decide regardless of history length.

**Two separate flows — training vs. inference:**
- Training pipeline (Q3 → Q5 → LightGBM fit): correctly excludes products with < 8 post-launch weeks. Exclusion is intentional — undercooked products distort model weights.
- Inference/scoring pipeline: includes ALL active UPCs from `built_enriched_weekly`. LightGBM handles NULL features natively. Scoring queries pull from `built_enriched_weekly` directly, not from `built_prepost_features`. New focal UPCs can still have full donor pre/post features because donors are established products.

**Three-tier confidence model (computed at query time from first_week_selling):**
- `FULL`: 13+ post-launch weeks — full pre/post diagnostics, LightGBM score, price elasticity
- `PARTIAL`: 8–12 weeks — LightGBM score with available features, partial diagnostics, elasticity with wider CIs
- `EARLY`: < 8 weeks (current state of all 70 Puff/Sour Puff UPCs) — non-parametric and heuristic methods only

**Non-parametric and heuristic methods for EARLY-tier products:**
- k-NN similarity: top-5 most similar established BUILT UPCs by flavor, pack, channel, first-week velocity → surface their labels as "similar product benchmark"
- Launch trajectory percentile: rank week-N velocity vs. all established BUILT products at same N post-launch weeks
- Category benchmark: velocity and TDP vs. category norms from `built_filtered_weekly` — available from day 1
- Heuristic assortment flag: pack-count variant of existing flavor → likely cannibalistic; new flavor, no existing match → likely incremental
- Trend extrapolation: simple trend fit to available weeks, project to 13w with uncertainty band, updated weekly

**Determine / Diagnose / Decide for EARLY-tier:**
- Determine: k-NN benchmark prediction + similarity confidence. Never hide the card. Label: "Prediction based on similar established products — model score available after 8 post-launch weeks."
- Diagnose: launch trajectory chart + percentile vs. launch cohort. Pre/post panel replaced with: "Pre/post comparison requires 13+ post-launch weeks. Estimated available [first_week_selling + 13 weeks]. Showing N-week launch trend."
- Decide: category-norm price positioning + heuristic assortment recommendation. Elasticity flagged as "category prior — refines after 8+ weeks of own-product data."

**`new_upc_candidates` (Q7) is the product registry** that drives UI routing and tier assignment. Tier upgrades automatically as `first_week_selling + N weeks` passes — no manual intervention. The 70 Built Puff UPCs (first_week_selling 2026-04-19) are the primary test case for this system.

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
- Q2b: ✓ COMPLETE — E21 (Gateway Timeout) fixed with subquery pre-filter pattern; confirmed 4.06s at Kroger/CONVENTIONAL|FOOD.
- Q2c: ✓ COMPLETE — subquery pre-filter pattern (same as E21/Q2b) confirmed working. Null bucket bug fixed: added `WHEN f.pre_13w_base_units = 0 THEN 'hm-no-data'` guard so new launches don't incorrectly fall through to `hm-strong-pos`. UI must render `hm-no-data` distinctly (grey).
- Q2d: ✓ COMPLETE — STRING_AGG removed (E22); returns count + scope label only. focal_upc stored without check digit in comparison_pool_weekly; geography_raw is RMA-level not TOTAL US.
- Q2d-names: ✓ COMPLETE — companion query; SELECT DISTINCT candidate_upc, candidate_description; 61 rows for CARAMEL/Kroger pool.
- Q2e: PENDING — cannibalization_rate_weekly and cannibalization_rate_forecast_weekly don't exist yet; re-test after ML pipeline runs.
- Q4: ✓ COMPLETE — 28 minutes. Revised to join built_filtered_weekly (not built_enriched_weekly) so competitor donors are included. candidate_brand_line = source_brand (no flavor_mapping override). UPC format 2-5-5 without check digit confirmed consistent across built_prepost_features and donor_prepost_features.
- Q5: ✓ COMPLETE — 60,695 rows, ~2 minutes. CANNIBALIZING 28,344 / INCREMENTAL 26,836 / WATCH 5,515. Focal pre-window is structurally 0 in SPINS (no data before first_week_selling); focal pre filters removed from WHERE. Labels valid using donor pre/post + focal post only.
- Q6: ✓ COMPLETE — two runs. 8w z-score ceiling 7√2/4 ≈ 2.475 blocked EXTREME_OUTLIER (threshold 3.0). Fixed: outlier classification uses 13w z-scores (ceiling 12/√13 ≈ 3.328); EXTREME_OUTLIER now fires. 8w z-scores retained as signal. Adds velocity_spm_roll13_avg/std, tdp_roll13_avg/std, base_units_z13, velocity_spm_z13, tdp_z13.
- Q3: ✓ COMPLETE — 131 distinct UPCs, 14,939 rows, 4 minutes. Note: 131 UPCs vs 91 in flavor_mapping (extra 40 = newer BUILT products/pack variants not in original CSV). Flag for flavor_mapping refresh.
- Q8 subquery ORDER BY ABS(e.pack_count - n.pack_count) may fail — defer fix until Q8 is tested.
- Q9: ✓ COMPLETE — CLUSTERED BY upc added; 177,516 rows; validated.
- Q14: ✓ COMPLETE — SPINS ARP data quality issues found and fixed (00-40962 prefix UPCs excluded, $0.50/bar floor added, 08-40229-30143 and 08-40229-30071 excluded). 711,427 rows across pack sizes 1/4/8/12/13/14.
- Q15: ✓ COMPLETE — pack price ladder weekly populated.
- Q16: ✓ COMPLETE — competitive price weekly populated; sortMerge required (BroadcastTablesTooLarge on built_filtered_weekly); hundreds of competitor brands present (all non-BUILT brands in extract); competitor_tier=NULL for brands outside curated 30 — filter in UI or Q17.
- Q17: ✓ COMPLETE — no sortMerge needed; self-join on ~700K rows within broadcast limit; 75,844 rows; 78 UPCs trained; 53 excluded (lack 25w price history, primarily Puff/Sour Puff cohort). STDDEV_SAMP fixed with SUM/SUM_SQ/COUNT + std_cte pattern (same as Q6/E23).
- Q20: ✓ COMPLETE — 246,317 rows / 172 segments / 54.82 MB; CLUSTERED BY pack_size_bucket, pack_count added; median dropped (E24).
- Q21: ✓ COMPLETE — 11,188,447 rows / 172 segments / 375.21 MB; all WELLNESS & NUTRITION BARS brands with nfp_protein populated; CLUSTERED BY source_brand, upc.
- Q22: ✓ COMPLETE — split into Q22a (REPLACE INTO, 2,559 COMPETITIVE_PRICE_GAP events / 104 UPCs) + Q22b (INSERT INTO, 786 PACK_LADDER_COMPRESSION events / 29 UPCs). UNION ALL between aggregated CTEs unsupported in MSQ (E26); MIN on STRING unsupported (E25); competitive_flavor_relationship stale values fixed. CLUSTERED BY focal_upc.
- Q10–Q13 need CLUSTERED BY added when tested (same pattern as Q0–Q22).
- Q2b and Q2c ORDER BY clauses removed (cluster does not support non-time top-level sort); confirm UI behavior is acceptable.
