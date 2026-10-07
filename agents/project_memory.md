# Project Memory

Last synced: 2026-10-07 (afternoon: accuracy claims register, Mo Chat accuracy wording fixed (mo-api 8987c77), MO_127/MO_128 run and skeptic-checked, forecasting roadmap approved; committed and pushed at end of session)

## Repository

- Local workspace: `/Users/jasonbrazeal/Documents/FirstAgent`
- GitHub repo: `https://github.com/theroblong/built-mo-preview.git`
- Main branch: `main`
- GitHub account used for pushes: `brazealboy1`
- Local git commit identity:
  - name: `Jason Brazeal` (was `theroblong` until 2026-10-07, so earlier commits by Jason
    are labelled `theroblong <brazealboy1@gmail.com>`; Robert's own commits are
    `Robert Long <rclong@gmail.com>`)
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

- 2026-10-01 — **short-series filter moved out of the extract; MO_27 has no ETS fallback** (README update 196). Audit of "are we training on all valid BUILT data": the mo_panel rules lose **nothing real** — RMA units 53,550,044 -> 53,550,044 (100% retained) and KEY ACCOUNT 7,587,422 -> 7,587,422 (100%), with only CRMA removed; RMA rows fall 49,376 -> 37,639 purely from zero-unit AK/HI variants; 2 UPCs lost, both CRMA-only, 227 + 2,127 units over 3 years. BUT `MIN_WEEKS = 13` ran inside **MO_25 at extract**, so short series never reached the parquet and were invisible to MO_27, the ETS experiments and all analysis — not merely excluded from LightGBM training as intended. Cost: 7,291 series (23.9% of series, only 0.27% of volume) and **17 UPCs entirely**, including BUILT's newest launches: 08-40229-30766 (first week 2026-06-28, 150,141 units, 17 accounts, 11 wks), 08-40229-30687 (2026-07-19, 145,626 units, 17 accounts, 8 wks), 08-40229-30771 + 08-40229-30772 (PB S'mores 1-pk and 12-pk). Now `mo_panel.drop_short_series()` (MIN_SERIES_WEEKS=13), called by MO_26/27/28 — rows stay in the parquet, LightGBM still excludes them. **CORRECTION: MO_27 contains ZERO ETS code and had no minimum-history gate** (grep-verified); ETS lives only in MO_30/31/34/35/36/37 and build_forecast_chart_data.py; **there is no MO_75 script** despite earlier notes citing "ETS fallback (MO_75)"; MO_34's data-maturity router is analysis wired into nothing. So moving the filter without gating MO_27 would have replaced "no forecast" with "bad forecast" (LightGBM predicting from all-NaN lag13/roll13/lag52). MO_27 now skips sub-13-week series explicitly and logs each UPC with units + account count. **These SKUs still get no forecast** — the gap is visible, not closed. Version scheme simplified: v9a/v9b letters dropped (v9a's 157,902-row panel no longer exists, not comparable); **v9** = final panel + corrected features + v8 hyperparameters, **v10** = + Optuna params. Renaming surfaced a third drift instance: build_forecast_chart_data.py hardcoded PKL paths to _v8 while _model_tag said "v6" under a comment telling you to bump it — archived Bracken charts were labelled v6 while loading v8 models; both now derive from one MODEL_VERSION constant. MO_28 configured for the weekend: N_ESTIMATORS_MAX 2000->6000, EARLY_STOP 100->150, RECENCY_LAMBDA now TUNED (0.0-0.15) instead of a separate grid (lambda/lr/tree-count all govern recency leaning, so a sequential grid bakes in bias), min_child_samples 10->200, cat regularisation widened, 150 trials, SQLite storage. Two correctness fixes: lgbm_base_v9's n_estimators is now the best trial's ACTUAL converged count (not the cap) with hit_n_estimators_cap reported, and recency_lambda is excluded from LGBM_BASE (it drives sample weights) and surfaced as recency_lambda_tuned; output stamps panel_rows/panel_series/panel_rules. OPEN: ETS route for short series unbuilt; lag52 100% null where weeks_since_launch<52 (51.8% of rows) while SEASONAL_BLEND_WEIGHT=0.40 pulls toward lag52xYoY; Albertsons 50.3% needs re-measuring; panel is 61% KEY ACCOUNT rows but those are a minority of volume, so row-weighted log loss weights a small c-store equal to Walmart.

- 2026-10-01 — **cold-start ramp: 41% of demand forecast with no ramp signal** (README update 197). Reliability audit before showing Bracken. **Lifecycle ramp curve** (each series indexed to its OWN weeks 5-8): demand 1-4wk 0.98 / 5-8 1.00 / 9-13 0.99 / 14-20 1.09 / 21-26 1.19 / 27-39 1.37 / 40-52 1.81 / 53-60 **2.09**, with TDP tracking closely 1.01 -> 1.69. Series DOUBLE over their first 60 weeks and distribution is the main engine (demand outruns TDP slightly, so velocity/store improves too). **CRITICAL measurement lesson:** a per-series CALENDAR comparison (last 4wks vs prior 4) shows median demand -6.5% and TDP -1% in EVERY history band with only ~33% of series showing TDP growth — which looks like it disproves the ramp but is just the Aug-Sep seasonal trough (STL Aug -14.8%) masking it. Measure ramp on weeks_since_launch, NEVER on a calendar window. **The gap, quantified** from the last 13 weeks of actuals: `<13wks` = 123,971 units (1.2%, 34 series) get NO forecast; `13-51wks` = 4,176,293 (40.9%, 761 series) get a forecast but have NO year-ago anchor; `>=52wks` = 5,915,975 (57.9%, 601 series) get the full YAGO blend. The 13-51 band should grow +66% across weeks 14->52 per the curve, but receives pure AR (MO_27's own comment: "collapses to a flat mean after ~4 steps") plus the MO_59 portfolio STL multiplier, which encodes month-of-year NOT lifecycle stage. So the forecast is structurally LOW for ~41% of demand — the Q4 2025 miss mechanism, still live. `<13wk` share compounding: 0.2% of Q2 2026 -> 1.5% of Q3. **Four candidate methods, none shipped:** TDP-adjusted naive (sound but blocked on forward TDP, which doesn't exist — NS2 sell-in was the intended source); weighted MA / naive LR (sidesteps forward TDP since recent trend implicitly contains ramp); ETS-Holt (already extrapolates trend — this finally explains MO_34's "ETS competitive for new/expanding series"); lifecycle-ramp prior keyed on weeks_since_launch, blended like the YAGO/STL layers (cheapest — feature exists, curve measured; = "cold-start proxy overlay", gap #9). RECOMMENDED: horse race on the 13-51wk band only using MO_34's existing harness; higher value than Optuna and non-conflicting. CAVEAT: the curve is a median mixing different launch patterns (new flavour at 17 accounts vs pack extension at 1) — check conditioning on pack_count or launch account breadth first. **MO_25 re-run with MIN_WEEKS at consumption: 190,375 rows / 134 UPCs** (was 186,427 / 122); all four newest launches now present in the parquet (30766/30687/30771/30772). **OPEN — seasonal index shape conflict:** MO_59 STL supplies the ENTIRE seasonal signal for the 55.5% of series without a year-ago anchor, incl. 51% of Target's volume, and peaks week 40 (Oct, +19.3%) / troughs week 36 (Sep, -19.5%) with Feb-Mar only +13.6% — a different SHAPE from the documented March peak +30% / Dec trough -28%, and STL is already flagged as not client-safe. It was computed 2026-09-24 on the old CRMA-inflated panel, so a recompute on the RMA-only panel may resolve it. Settle before any finance demo. **Reliability agenda before Bracken:** (1) resolve the seasonal shape conflict, (2) re-measure per-retailer error — the 50.3% Albertsons figure had flavour+brand NaN'd and half its slice phantom, so there is NO trustworthy per-retailer number today, (3) ship a cold-start method, (4) then tune. Version numbers are internal bookkeeping, not a client concern.

- 2026-10-01 — **v9 trained; tree budget measured; NS2 bridge received** (README update 198). **v9**: 186,427 -> 94,186 training rows through five panel rules; 77,609 train / 16,577 val / 56 features. best_iter / pinball: base q50 3998 / 0.0141, q10 1097 / 0.0099, q90 1203 / 0.0087; total q50 3997 / 0.0209, q10 3004 / 0.0125, q90 1645 / 0.0118. **spins_flavor_canonical now live at #12 by gain (6,078)** with 34 real families after being inert at inference since v8; retail_account still #1 (19,406); distribution signals cluster just below (tdp_4w_momentum 7,912 / tdp_wow_delta 6,812 / tdp_z8 6,558), consistent with TDP driving the lifecycle ramp. Metrics NOT comparable to v8 (different val composition) — only v9->v10 is clean. **TREE BUDGET (new scripts/MO_29_tree_budget_probe.py)**: q50 pegged its n_estimators cap at EVERY version (v6 2000, v7 2999/3000, v8 4000, v9 3998/4000) with loss still falling, which read as capacity starvation. Disproved: with min_delta=0 and patience 50 the curve **terminates at 4,593** — early stopping was never broken, the 4,000 cap never gave it room to fire. Four versions of apparent starvation were a ceiling artifact. Marginal value beyond 4,000: 6,000 +1.4%, 8,000 +2.2%, 12,000 +3.1%. Curve is **asymptotic, not convergent** — never flattens, only decays — so n_estimators is a COMPUTE BUDGET decision, not a tuned value. Set MO_26 n_estimators=6000 and MO_28 N_ESTIMATORS_MAX=6000; deliberately no higher since the 12,000 ceiling buys 2.62% for 2.6x compute. Only medians were ever near the cap. **NEGATIVE RESULT: min_delta is the wrong tool** — every nonzero value is worse than zero (1e-6 -> 4,416/2.73%; 5e-6 -> 2,523/5.66%; 1e-5 -> 2,153/**6.36%**; 1e-4 -> 778/16.34%); it was wired in before being measured, now 0.0 with the table left in the MO_26 comment. CAVEAT: 4,593 is NOT a constant — it is a property of lr=0.04/num_leaves=63; a higher lr reaches a given loss in fewer trees, so the stop point moves whenever Optuna moves lr, which is exactly why early stopping and not a tuned n_estimators must govern tree count per trial. **NS2 BRIDGE (docs/SalesRepTables.xlsx from Ebad)**: closes the 3rd of 3 open Ebad asks. SalesRepCustomerMap 116 rows (Retailer / Built Customer / NetSuite Customer ID / SPINS Customer / Channel / Sales Manager) + SalesRepDim 14 reps. **SPINS Customer joins on geography_raw NOT retail_account** (39 of 60 match geography_raw, 2 match retail_account) — the RMA-level identifier, aligning with RMA as the priority basis. 21 unmatched: divisional rollups we don't extract (ALBERTSONSCO JEWEL/HAGGENS/UNITED DIV, AHOLD GIANT CARLISLE/GIANT LANDOVER/STOP & SHOP DIV) and naming differences (ALEX LEE - LOWES FOODS, FAREWAY); KROGER BANNER TOTAL - RMA cited but absent from our panel. **Distributor fan-out severe**: 54 Built Customers -> 97 Retailers across only 52 NetSuite IDs; CORE-MARK serves 18 retailers under one ID (C0761137), UNFI 13, DOT FOODS 12, KEHE 10, MCLANE 8 — so distributor sell-in is one invoice stream across many retailers and needs an allocation rule. **BUT every data-dark retailer is DIRECT** (WINCO, H-E-B, ALDI GROCERY, COSTCO, COSTCO CANADA — all direct, no SPINS id), which removes the circularity that would otherwise sink the sell-in plan; and the pooled accounts mostly DO have SPINS (WALMART via MCLANE, SPROUTS via KEHE) so they don't need sell-in. By route: direct 45 rows/26 retailers/12 with SPINS; distributor 71/71/48. **14 direct-and-dark = cleanly addressable; 23 distributor-served-no-SPINS = hard bucket.** OPEN: no effective dating on customer.salesrep or the sheet (a customer that changed reps, or a retailer that changed distributor, has ALL history attributed to today's owner — same conclusion as the Level 1/Level 2 retailer bridge: hold it with effective dates; ask Ebad whether NS2 keeps change history, cheaper at initial load than reconstructing); no isinactive filter so terminated reps appear in the dimension. Remaining ItemDim asks still open (359/513 null UPCs; ProductType codes 1/2). Decisions register -> v0.5, 77 entries (+GRD-08, GEO-11, COV-06, OPN-11).

- 2026-10-01 — **seasonal index was stale and unreproducible; now volume-weighted over all series** (README update 199). Reliability item #1. `outputs/mo59_seasonal_index.csv` is the ONLY seasonal signal for the ~55% of series with no year-ago anchor (MO_27's `elif seasonal_lookup`, ~line 569), incl. 51% of Target's volume. **The live CSV is dated 2026-09-24, is UNTRACKED, peaks week 40 (October), and re-running MO_59's own n=20 logic today gives a week-6 peak on BOTH the Sep-30 and Oct-1 panels — it is not reproducible from any panel we still have.** Being untracked is the root cause: a file shaping most of the forecast had no version history. **TWO EARLIER CLAIMS WERE WRONG and are logged as register corrections (ANO-10 supersedes ANO-08):** (1) the index is built from `qualifying[:20]` = 20 series by volume with >=104 weeks, NOT from TOP_N=3 (which only picks decomposition-chart panels — Claude misread the call site and repeated "3" several times); (2) the October peak is NOT a CRMA artifact — MO_59 already excludes CRMA at load (EXCLUDE_GEO={"CRMA"}). **REAL MECHANISM: the curve is BIMODAL** with a March mode and an October mode nearly tied, so a median's argmax flips between them — n=20 wk6 / n=40 wk41 / n=80 wk10 (Oct-1) vs wk40 (Sep-30) / n=265 wk9 — while VOLUME-WEIGHTED is stable at wk 10-11 across every sample size and both panels. **⚠️ CORRELATION IS THE WRONG STABILITY METRIC: at n=80 the median's peak moved 30 weeks while correlation stayed 0.9851.** argmax is what matters because this index multiplies a forecast. Related: **single-series STL is numerically unstable at this history length** — period=52 with only ~2.9 cycles means one extra week of data (153->152 on a Walmart series) flipped a small-sample peak 30 weeks; averaging over hundreds of series is what makes it usable. **FIX APPLIED:** MO_59 now calls `compute_seasonal_index(df, qualifying, weighted=True)` — all qualifying series, volume-weighted by each series' own mean level. Full sample (265 of 281 fitted): primary peak **wk 10 (Mar 05) +0.199**; pre-summer shoulder **wk 17 (Apr 23) +0.089**; October secondary wk 41 +0.063; trough **wk 52 (Dec) -0.190**. Matches documented BUILT seasonality (March peak / December trough) at BOTH ends; the 20-series median agreed on the peak but put the trough in September (wk 36), so the full sample is specifically required for the trough. Three positive regions = New Year/spring fitness, pre-summer, back-to-school/Q4. **Jason's summer-bump recollection is half-right:** wk 17 late April is a real local max (April +0.068 to +0.140) but May declines monotonically and July is the deepest trough of the year (-0.134) — a spring shoulder, not a summer peak. October mode shrinks +0.104 (n=40) -> +0.063 (n=265), consistent with a mass/club pattern diluting in the full portfolio — likely why it won argmax in small samples. Amplitude ~0.39 vs documented ~0.58 is EXPECTED (STL strips trend), which is also why client charts must use the 12-month raw monthly index not the STL curve. **OUTSTANDING: production CSV NOT yet regenerated** — MO_59 is patched but running it end-to-end also does changepoint detection + HTML, so it is a deliberate separate step; after regeneration re-check the forecast for the 55% of series that depend on it, and version-control the CSV. New diagnostic `scripts/MO_59b_seasonal_index_rebuild.py` writes alongside and never overwrites; comparison in outputs/mo59b_seasonal_comparison.json. Register -> v0.6, 80 entries (+ANO-10, NRM-07, ANO-11). Next: #2 re-measure per-retailer error on the corrected panel, then #3 cold-start horse race.

- 2026-10-01 — **THE KEY FINDING: the recursive forecast collapses to a random walk; the tuning objective is 9x optimistic** (README update 200). For no-YAGO series (<52 wks = **40.9% of demand**) MO_27's recursive forecast reaches a FIXED POINT BY STEP 3 and flatlines: median ratio to last actual week 1.022 / 1.028 / 1.029 then 1.029-1.031 for steps 4-13 (±0.1%). **SD(forecast)/SD(actual) = 0.062** — it retains 6% of actual week-to-week variation. Production output for 41% of demand is functionally `last_actual_week x 1.03` held flat for 13 weeks. **CAUSE: 31 of 56 features are FROZEN at last observed value for the whole horizon**, including EVERY distribution/velocity feature (tdp, tdp_z8, tdp_wow_delta, tdp_4w_momentum, tdp_lag52, velocity_per_tdp, velocity_spm_*, donor_count, top_donor_tdp_sum). Of the 20 that vary: promo flags hardcoded 0, ARP flat, base_units lags self-referential — leaving week_sin/week_cos as the ONLY exogenous time-varying inputs, and they rank outside the top 20 by gain. So the model CANNOT produce a ramp: the lifecycle ramp is TDP-driven (TDP 1.01->1.69 over 60 wks) and TDP is pinned constant. Features are right (tdp #8, velocity_per_tdp #15 by gain) — the loop never moves them. **Jason's original proposal was the correct fix and Claude under-rated it**: "most recent week's demand adjusted for additional TDP expansion" — the model already does the first half; TDP projection is exactly the missing half. **NOT RECENCY_LAMBDA** (Jason asked; ruled out — it weights training rows and cannot make an AR loop converge; the fixed point is structural). **MO_28 OPTIMISES THE WRONG OBJECTIVE:** teacher-forced CV pinball **4.15%** vs recursive production **37.12%** — a 9x gap, and directional not noisy, because training rewards leaning on lag1 (best one-step predictor) while recursion punishes exactly that (lag1 becomes the model's own output). The objective actively selects for the collapse. FIX: recursive-backtest objective (554 series x 13 steps x 2 arms runs in ~1-2 min, so ~1-2 min/trial, 150 trials fits a weekend). This also answers whether Optuna can tune the seasonal-index n: NO and it shouldn't — MO_28's objective never sees the index (applied post-hoc in MO_27) and MO_59d showed n barely matters out-of-sample (corr 0.472->0.485 from n=20 to n=241). **SEASONAL MULTIPLIER: keep it, stop optimising it** — recursive OFF 37.12% -> ON 34.47% (-2.65pp HELPS), though per-series only 54% helped (aggregate gain comes from larger series). **SUPERSEDED TEST (instructive):** MO_27b evaluated the multiplier teacher-forced and reported it HURTING +8.53pp with 99% of series worse — INVALID, because the window sat in the seasonal trough (mean multiplier x0.890) and actual lags already carried the decline, so it double-counted; close to an arithmetic artifact of an 11% haircut. Claude built a test whose result it had predicted, got a large effect, and nearly reported it as confirmation. Teacher-forced evaluation cannot answer questions about a recursive forecast. Net: the seasonal index is a **2.65pp patch on a 37% problem** — the n/segmentation work (MO_59b-e) is CLOSED (use all qualifying, volume-weighted). **REVISED PRIORITIES: (1) project TDP forward in the recursive loop** — same 41% of demand, far larger lever; crude capped tdp_4w_momentum projection would let existing trained features generate ramp; caveat forward TDP is itself a forecast so a bad projection injects error (why NS2 sell-in was wanted); **(2) recursive Optuna objective; (3) horse race** with "last actual x TDP projection" vs "STL seasonal adjustment" as competing arms plus ETS-Holt / weighted MA / lifecycle-ramp prior — not "can simple methods beat LightGBM", it has already collapsed into one. **NOT YET MEASURED — do not assume:** the same recursive test on the YAGO band (>=52 wks). ~10% would mean 37% is the cold-start penalty; ~30% would mean recursive AR is weak everywhere and the problem is the method, a materially larger conclusion. One cutoff (2026-06-07), one window — reproduce at a second cutoff. New scripts: MO_27c (recursive test, reuses MO_27._build_feature_row, self-check that the OFF arm flattens — ratio 0.062, passed), MO_27b (superseded, kept with limitation documented), MO_59c/d/e. Register -> v0.7, 83 entries (+ANO-12/13/14). Also: **NS2 is MSSQL (bb-db), SPINS is Druid** — two engines, don't cross-apply constraints.

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


## Session 2026-10-01 — v10 forecast coverage, lapse gate, cold-start horse race

### Decisions made

- **MO_27 no longer skips any series.** The `<13`-week gate became a *method* router, not a
  coverage gate. Previously 473 of 2,137 series (110 of 133 focal UPCs) returned nothing.
  Output is now 2,137 x 13 = 27,781 rows with zero skips, every row tagged `forecast_method`.
- **Lapse gate added (`LAPSE_WEEKS = 9`), applied to ALL series.** 524 of 2,137 series (24.5%)
  had recorded no sale in 9+ weeks — 209 short-series and **315 that the autoregressive path was
  forecasting off a stale tail** (195 with no sale for over a year). All now forecast 0 with a
  zero-width band and method `lapsed_no_recent_sales`. Threshold chosen on a clean distribution
  gap (250 series within 4 weeks, only 14 in the 5-8 week zone, then 209 at 9+).
  Deliberately **not** labelled "delisted" — the TDP reading is as stale as the sales.
- **Lifecycle ramp REJECTED** and removed from MO_27. Real in aggregate (series double over 60
  weeks) but lost to flat carry-forward in every history band and carried +21 to +23% positive
  bias in the 13-51 bands. Aggregate truth is not per-series predictive signal.
- **Donor surrogate REJECTED.** Its apparent tier effect was a confound — `naive` is also better
  on the same easier subset.
- **Final MO_27 method split: 1,349 autoregressive + 264 carry-forward + 524 lapsed-zero.**

### Artifacts created

- `scripts/MO_79_coldstart_horserace.py` — 6-arm cold-start horse race, 4 cutoffs, all fits
  refit pre-cutoff only; reports pooled wMAPE, per-series win rate, bias and an oracle ceiling
  per history band. Outputs `outputs/mo79_coldstart_horserace.json` + `mo79_coldstart_per_series.csv`.
- `mockups/mo_decisions_register.html` v0.8 — 89 entries; new COV-07, COV-08, GRD-09, GRD-10,
  ANO-15, ANO-16. Header stats and section counts resynced (they were stale at v0.1 / 56).

### Bugs found and fixed

- `max(0.0, nan)` returns `0.0`, so a NaN level was presented as a confident zero forecast on 16
  series. `x or default` does not catch it either — NaN is truthy. Now an explicit `np.isfinite`
  test routes these to method `no_level_available`.
- Carry-forward dated forecast weeks from each series' own last observation instead of the global
  `anchor_date`, which for a 74-week-stale series emits rows dated 74 weeks **in the past**,
  overlapping actuals in the same datasource.

### Open questions

- **Stage B not yet run:** Chronos-2 and the production LightGBM recursive path as arms on the
  MO_79 harness. The bar to beat is naive at 94.7 (band 1-4) and 55.1 (5-12); the oracle says
  74.5 / 40.8 is the ceiling. `chronos-forecasting 2.3.1`, `statsforecast`, `mlforecast` and
  `autogluon.timeseries` are already installed — no new dependency, only a ~500MB HF weight fetch.
- MO_62 and MO_65 do **not** already answer this: both set `MIN_HISTORY = 52`, so every
  foundation-model result we have was measured on mature series only.
- The **+7.9% recursive over-forecast** remains the root defect and is untouched by this work.
- A router that picks the best arm *ex ante* is unproven — the 20.2pp oracle headroom is hindsight.
- TimeGPT would send BUILT's paid POS data to Nixtla's servers. Rob's call, not taken.
- NS2: why do 359/513 UPCs have a null `upccode`?

### Note on the MO_27 "HUMAN REVIEW REQUIRED" banner

That gate is our own code — `scripts/mo_writeback.py:208`, from the Druid schema-safety work.
MO_27 uploads the parquet to MinIO and writes an ingest spec but never POSTs to Druid, so running
it does **not** change what the Mo UI serves. Submitting is a separate explicit step.

## Session 2026-10-07 — Shared working setup (one rulebook for Robert and Jason)

### Decisions made

- Robert: committed repo files are the source of truth for working agreements; machine-local assistant memories are superseded.
- Robert: log-everything condensed -- same-turn note under `## Live session notes`, polished wiki/18 entry at `/end-session`; push only on confirmation.
- Robert: on any machine, Claude flags unreachable references (related repo not located, file committed nowhere) and works with the user to get them committed.
- Robert: onboarding a new machine is one prompt for a non-developer, at most one VS Code reload (marker `.claude/onboarding.local.json`, per machine, gitignored).
- Jason: agrees to push-on-confirmation (replaces "push all 4 repos, no exceptions"), and to the model/effort pin (`claude-opus-5-5[1m]`, effort high, `.claude/settings.json`).
- Jason: local copies of feedback_log_everything, feedback_four_repos, feedback_meeting_prep_process now hold only a pointer to the committed files (not deleted).

### Artifacts created

- `.claude/` shared config (commit 2297c57): settings.json (model pin, effort high, read-only permissions); hooks `require_memory_in_commit.py` (commit requires `agents/project_memory.md` staged), `protocol_gate.py` (MO_127+), `session_context.sh` + `check_refs.py` at session start; skills new-experiment, end-session, onboard; scribe agent; related-repos.json.
- `.claude/hooks/check_refs.py`: remote matching ignores trailing `.git`/slash/case (Jason's mo-api/mo-ui clones lacked `.git` and were reported not located). Commit e122e1a.
- Committed Jason's machine-only notes (e122e1a): `docs/working-agreements/feedback-meeting-prep-process.md`; `memory/` project_mo53_individual_ablation, project_portfolio_cannibalization (MO_55), project_mo52_feature_ablation, project_mo56_candidate, project_ml_architecture_roadmap, feedback_ml_feature_signals. check_refs.py reports nothing unresolved.
- Jason's machine onboarded and verified (context loaded, commit gate refused a dry-run commit without project_memory.md, model matches pin). Related repos found under ~/Documents.
- Commits: 12253dd (log-everything agreement), 2297c57 (shared config), e122e1a (onboard Jason's machine, pushed).

### Open questions

- Closed: Jason's machine-only files committed; model/effort pin and push-on-confirmation agreed.
- Pending: settled-findings list (scope/harness/reopen-if per entry) and scout/runner/skeptic agents -- approved by Robert; spec at docs/design/settled-findings-and-agents.md (2026-10-07); not built.
- Closed: Jason's FirstAgent commits were labelled with the author name `theroblong` (a repo-level git setting; email was Jason's, pushes go through his own GitHub account). Label only, not a credentials issue. Jason changed it to `Jason Brazeal` on 2026-10-07; earlier commits keep the old label.
- New (raised by Claude): Jason's machine-local MEMORY.md index is 31KB, over the 24.4KB load limit (~22 entries unloaded) -- trim index lines.
- No new forecast results; no async messages received.

## Session 2026-10-07 (afternoon) — accuracy claims register, MO_127/MO_128 skeptic-checked, forecasting roadmap

### Decisions made

- Jason: track accuracy corrections in `docs/ACCURACY_CLAIMS_REGISTER.md`; update affected files later with newer data. Accuracy is not the headline while forecasting is tuned (no 3 yrs PUFF/SOUR PUFF history; source_brand stratifier, BAR->PUFF chaining, TFT/RNN planned). **Demand velocity forecasting remains the main deliverable.**
- Jason: explain data-science acronyms (wMAPE etc.) in plain language for CFO/FP&A readers; CLAUDE.md points every session to the register.
- Jason (Rob agrees): Mo Chat stops quoting accuracy percentages; wording applied in customer-built-mo-api `app/routers/mo_chat.py` `_DATA_GLOSSARY` (commit 8987c77): accuracy + foundation-model sections replaced, "MA 13wk = BUILT's Excel baseline" fixed, MO_76 6.313%/6.505% replaced with words. Compiles; no Mo Chat tests exist; live on next Mo API redeploy.
- Jason, settled-findings review: load only key parts (~110 lines: open blockers, method rules, current position, REVERSED) into CLAUDE.md; FACT and pre-correction PROVISIONAL stay in file for lookup. Pending Robert's review.
- Jason (replaces his earlier MO_92 answer): portfolio x month model vs flat is NOT SETTLED; do not cite "ML beats naive at the planning level". MO_92 is differently scoped, not reversed.
- Jason: BUILT's "~7%" (Connor's 7-10%) moves FACT -> open question; do not compare our numbers to it until defined.
- Jason: Meijer brief needs no action (see correction below).
- Jason: MO_127 design = honest comparison (no seasonal at the four 2025 cutoffs; pre-cutoff-only 104w index at the three 2026 cutoffs; all 7 quarters; longest-history PUFF as a separate results view). MO_128 = head-to-head on long-history PUFF vs Connor L12W/L4W, flat, shipped model, model w/o BAR; per-SKU focal table for UPCs 30362/30037/30380/30381. Model-improvement versions held for MO_129.
- Jason (Brad/Claude advice; revised): forecasting roadmap in `docs/FORECAST_ROADMAP.md`:
  1. Fix the yardstick: Q3 2026 cutoff 2026-06-29 is a Monday -> 2026-06-28 (MO_80:206; Rob's OK needed; all 190,375 SPINS panel rows are Sunday week-ending); ~20 monthly origins; score new series; history = calendar span with distribution (e.g. TDP > 1); rebuild fitted inputs per cutoff; measure the noise floor.
  2. Fair training: no 800-tree cap (early stopping on time-based last-13-week block + refit; MO_29 converged ~4,593); fix validation split (MO_80:365 `va = tr.tail` takes the last series, not latest weeks; check MO_26); remove yoy clip 0.5-2.0 (MO_27:571); tune blend weight/recency/thresholds; calendar-aligned year-ago (MO_80:421); one loose logged 3x-max safety rail.
  3. MO_129: Connor anchor + learned corrections with seasonality LEARNED and pooled across all series (Jason: no forced bandaids; learn from existing and future patterns); direct multi-horizon; BAR as tunable weight; replaces the separate seasonal step.
  4. Structure factorial first, then Optuna TPE with pruning on the honest multi-origin 13-wk objective, confirmed on held-out origins.
  5. RunPod GPU (timing TBD): parallel Optuna/backtests now; one bounded deep-model challenger later (TFT/DeepAR/N-HiTS/Chronos-2).
  Shipping option after step 1: L4W velocity x doors for established items + last value for new items, no STL seasonal (L4W, not L12W).
- Advice (Brad/Claude): frame ML as "L4W anchor + learned corrections"; if it cannot beat L4W as a corrector, ship L4W and keep ML for explanation/scenarios; TFT/RNN deprioritised on data scale (~260 long series, <3 yrs).
- Jason: his local MEMORY.md index trimmed 32KB/171 -> 18KB/130 lines; 83 unindexed older notes reviewed, 56 now indexed (21.4KB / 139 lines), 27 left out. Backup MEMORY.backup-2026-10-07.md. (Closes the morning's open item.)

### Found

- Settled-findings draft: docs/SETTLED_FINDINGS.md ~75 entries (246 lines vs ~150 target); FACT status added (Robert, via build). Spec at docs/design/settled-findings-and-agents.md; agents scout (haiku/low), runner (sonnet/medium), skeptic (opus/high); protocol gate requires PRIOR WORK (MO_127+); commit hook blocks a recorded reversal unless SETTLED_FINDINGS.md is staged (escape `[no-findings-change]`).
- MO_63's 2.02-5.71% rolling-CV accuracy is teacher-forced (same class as the retired 3.4-4.3%); backs the "accuracy compounds" claim and is in the Mo Chat glossary (README.md:6447, 6764). "5x vs foundation models" (MO_62, reversed by MO_106) also still in FP&A report and glossary. Retired figures remain in 13 places (register section 4); Mo Chat was priority 1 and is fixed.
- Skeptic (opus/high, key claims verified): MO_92-vs-README 223 decision failed. MO_92 differently scoped: shipped target-mode loses to flat at portfolio x month on the corrected harness too (MO_125 20.07 vs 16.0). README 223's 12.2 vs 16.4 is the UNSHIPPED anchor mode, pooled over n=21; flat beats model in every band at portfolio x month (`scripts/outputs/mo126_band_breakdown.json`: <13 12.7 vs 17.7; 13-25 16.9 vs 22.2; 26-51 13.8 vs 14.9; 52+ 21.4 vs 22.7).
- The shipping config (MO_27 step-over-step main loop :794-800; anchor-relative in short-series router :508-514) has never been scored at portfolio x month; MO_125 "production" arm is the pre-Oct-6 target-only config. Seasonal mode is outside the parity contract (mo_panel.py:63-69). MO_126 script not committed.
- Production audit (MO_27 + v11, 56 features, trained 2026-10-01; v10/v11 lists identical). IMPLEMENTED: source_brand as categorical FEATURE (MO_26:168, mo_panel CAT_COLS, MO_27 `_cat_str`), parent_brand='BUILT' filter (MO_25:307), spins_flavor_canonical, step-over-step seasonal (blend 0.10), <13-wk last-value router, LAPSE_WEEKS=9, feature freeze + parity guard, yoy_ratio clip 0.5-2.0 (MO_27:571). NOT IMPLEMENTED: BAR exclusion / per-brand stratifier, conn_L4W velocity anchor, 1.5x series-max cap, BAR->PUFF chaining, per-store (velocity x doors) target. Suspect for growth under-forecast: yoy cap 2.0 vs BUILT growth 1.6-4x/yr, plus lag52 features.
- MO_127 step 1 (read-only, retailer_sales_weekly.parquet, CRMA excluded): panel starts 2023-10-15; series with >=104 wks pre-cutoff: 0 at 2024-12-29, 2025-03-30, 2025-06-29, 2025-09-28; 160/206/265 at 2025-12-28/2026-03-29/2026-06-29 (~28% of trailing-13-wk volume); >=52 wks 309-883. Full-panel index applied to 2025 quarters = CONFIRMED look-ahead. PUFF: 262 series >=104 wks, 461 >=78, 749 >=52.
- MO_127 (predictions committed eb3e300 before run; skeptic-reviewed, independent rebuild matched JSON): full-panel index cuts flat's pm error 15.99 -> 8.96 (all 7 qtrs), 14.97 -> 3.74 (2026); conn_L4W 10.71 headline -> 16.42 without seasonal. Honest MO_59-method index on ~2 yrs is worse than none (two-cycle STL absorbs growth; jump at cutoff week; range 0.87 at 2025-12-28 vs 0.42 full; trough -0.517 at wk 52; conn_pre bias 1.49). Index rebuild check exact (max diff 0.0000, 241 series). Honest all-quarter standings (conn_L4W_off / flat / model_off): cell x week 32.5 / 32.8 / 36.7; account x month 21.7 / 22.9 / 26.2; portfolio x month 16.4 / 16.0 / 17.3. By band cell x week: <13 53.9/48.2/48.2; 13-25 42.7/42.4/45.1; 26-51 27.2/26.9/31.1; 52+ 28.2/29.9/34.7. Conn beats model by 4-7pp on 26+, beats flat only at 52+; flat lowest pm error in 5 of 7 quarters; n=21 months too few to rank. Model worse than flat on 52+ (34.7 vs 29.9) is NOT an index artefact (blocker 0.3 open). Skeptic: C1/C2/C3 survive with scope change; C4 failed; C5 survives. Pre-cutoff r=+0.17 vs full index is mostly the artefact (equal-length series r=+0.54). model_step_pre beating model_off in 2026 pm (14.8 vs 18.1) = two errors cancelling. Predictions: P1 HOLDS, P2 HOLDS, P3 FAILS, P4 HOLDS, P5 FAILS, P6 FAILS as specified.
- Inherited in every MO_12x backtest (skeptic): Q3 2026 cutoff Monday (anchor ISO wk 27 vs last data wk 26; drops h=1; Sep 2026 is a 1-week month, flattering Q3 2026 month-level numbers); TREES=800 cap; MO_80:365 validation slice; 9-11% of 52+ volume in series with missing weeks so hist[n-52] is not the year-ago week (MO_80:421); 13.6% of puff52 rows have gaps.
- MO_128 (predictions committed 5ec7318; focal view narrowed to 52+ wk series before the real run, predictions unchanged; smoke test 80s; skeptic-reviewed, Connor/flat arms rebuilt row by row): PUFF 52+ all 7 qtrs cell x week / account x month: L4W 27.4/23.8, flat 29.2/25.2, L12W 29.9/26.5, model_noBAR 32.0/27.3, model 33.9/29.3. PUFF 104+ (2026 only): L12W 21.3/18.2, L4W 23.1/20.3, flat 26.5/23.5, noBAR 29.1/26.3, model 30.0/27.1 -- but D1 "L12W best" does NOT survive: carried by Q1 2026 plus Sam's and Walmart (46.6% of puff104 volume, 162 of 3,940 cell-weeks); without Q1 2026 flat best (18.3 cw); without those two accounts L4W beats L12W (19.1 vs 19.6); L4W best in 5 of 7 qtrs; L12W wins only Q1/Q2 2026 (D2). Q1 = 28% of puff52 volume but 37-60% of monthly error, every method 25-55% low (month bias 0.45-0.78); Q4 2025 every method 20-40% high (1.21-1.40) (D3). noBAR gain ~0 in 2026, 86% from Q3+Q4 2025, negative on puff104 pm (20.37 -> 21.00); BAR share of training base_units 17.6% -> 3.0% (D4). Focal: 210 retailer series, model beats L4W on 37 (7% of focal volume; volume-weighted model 6.0pp worse than L4W), L12W on 51, flat on 34 (D5). Pooled bias 0.91 = Q1 0.546 netted against ~1.065 elsewhere; not a general growth under-forecast (D6). On 104+ PUFF outside Q1 2026 the model had the lowest monthly error: 10.3 vs flat 11.5, L4W 13.7, L12W 14.0 (156 series, 2026 only, small sample; at item x week Connor still leads by ~7pp). Model beats L12W at PUFF month level in 4 of 7 qtrs. Predictions: P1 FAILS, P2 HOLDS, P3 HOLDS, P4 FAILS, P5 HOLDS, P6 HOLDS.
- Walmart PUFF 1.41oz singles (Brownie Batter 30362, Coconut 30037) are relaunches (~0.1 TDP, <60 units/month for two years, then ~40 TDP from Jan 2026) mislabelled 52+ because history is counted as rows. Brownie Batter 1.41oz @ Walmart anomalous in the preliminary run (all arms 80-97% error, model bias 0.43). Q1 under-forecast better explained by forecast anchored at the late-December trough week with no seasonal climb (YoY growth 1.56 / 1.02 / 0.70 in Q1/Q2/Q3 2026).
- Focal long-history PUFF SKUs (152 wks, 2023-10-15 to 2026-09-06): Brownie Batter 1.41oz single 08-40229-30362 (Kroger, Circle K, Publix, UNFI, Maverik, CVS, Wegmans, AWG, Albertsons, Hy-Vee); Coconut 1.41oz single 08-40229-30037 (Circle K, Kroger, Publix, Maverik, UNFI, CVS, Wegmans, Albertsons, AWG); Brownie Batter 4pk 08-40229-30380 (Walmart 1.18M base units last 52 wks, Meijer); Coconut 4pk 08-40229-30381 (Walmart 0.99M, Publix, Meijer).
- Mo Chat `_DATA_GLOSSARY` (~L2201-2222) had cited 2.0-5.7% (MO_63) and 6.1% / "5.1x" vs foundation models; also L2172-2178 seasonal description (STL top-20 series) looks out of date (not changed).
- Pitch material still carrying retracted accuracy: docs/aevah_marketing_notes_internal.md ("6.1%", "5.1x", "4.3% wMAPE"); mockups/aevah_forecast_horserace.html, mockups/mo_exec_brief.html (4% hero); also docs/aevah_llm_vs_ensemble_talking_points.md, docs/mo_python_ml_register.md, mockups/bracken_forecast_project_plan.html, mockups/meijer_cannibalization_brief.html, mockups/mo_data_model.html, mockups/mo_competitive_landscape.html (context not all checked). Tracked in the register.
- Skeptic-proposed SETTLED_FINDINGS changes (PENDING review; mirrored in docs/SETTLED_FINDINGS.md pending section): MO_113 anchor mode REVERSED (honest anchor worst arm: 55.30 cw / 32.71 pm); MO_125 conn_L4W 10.71 REVERSED (honest 16.42 vs flat 15.99 pm; cw 32.53 vs 32.82; am 21.71 vs 22.93) and README 226 "seasonality matters far more once anchored" reversed; MO_126 RE-SCOPED (honest conn_off - model_off by band +5.7 / -2.4 / -3.9 / -6.5; vs flat +5.7 / +0.3 / +0.3 / -1.7; conn beats flat only at 52+); README 223 REVERSED (settles MO_92 vs 223 in MO_92's favour; but see NOT SETTLED entry for portfolio x month); FACT seasonal-index addendum; MO_128 PROVISIONAL (L12W-vs-L4W flips by quarter, don't route 26+ to L12W, reopen if L12W wins 2 more non-Q1 quarters; amend "exclude BAR": gain fades as BAR share falls); new method rule "every fitted input (index, scaler, anchor) is rebuilt from data up to each cutoff"; method-rule candidate: count history as calendar span with real distribution.
- Runner agent returned an off-topic report without running MO_127; smoke test (Q3 2026, 50 trees, 188s) and full run done directly.

### Corrections (Claude's earlier statements, corrected in chat)

- Claude told Jason the Q1 PUFF under-forecast "matches year-ago anchoring of a fast-growing brand" -- NOT supported (skeptic C4): flat is equally bad (37.4 vs model 36.4); the YAGO blend pulls UP in Q1; it is trough anchoring at the late-December week.
- Claude told Jason L12W is best on the longest-history PUFF, noBAR helps 1-2pp, and the model under-forecasts ~9% -- all three narrowed or overturned by the skeptic (D1, D4, D6).
- Claude's suggestion to draft a settled-findings/agents proposal for Robert was superseded: Robert built them from his spec the same day.
- The Meijer re-verify decision rested on a stale README open item (README.md:3367). The brief was already rebuilt on Meijer RMA (CONVENTIONAL|FOOD) data on 2026-09-25 (commit 5f18832, "replace stale MULO CRMA data"; footer cites 211 Meijer RMA scored pairs; wiki/18 AI-20 "Done Sept 25"). No re-check or note to Brian needed unless Jason wants one. Stale: README 159 summary TDPs, README.md:3367 open item, SETTLED_FINDINGS "Open: re-verify the Meijer brief" (flagged for Robert).
- Clarification: "model did as well or better with more history" holds only at month level outside Q1 2026 on 104+ PUFF (10.3 vs 11.5/13.7/14.0); at item x week Connor leads ~7pp; 156 series, 2026 only.
- Clarification (Jason's goal, not explained clearly earlier by Claude): MO_127 is groundwork; the PUFF work is a head-to-head on focal SKUs to see whether the model (with recent enhancements) can beat Connor's L4W.

### Artifacts created

- FirstAgent: `docs/ACCURACY_CLAIMS_REGISTER.md` (plain-language metric glossary, 5-part rule for stating any accuracy number, honest numbers, retired figures, 13 locations; section 2 carries a do-not-quote warning, updated to MO_127 honest numbers); `docs/drafts/mo_chat_accuracy_wording_DRAFT.md` (applied); `docs/exec_summary_2026-10-07_for_rob.md` (rewritten with skeptic-checked results, audit, roadmap, asks); `docs/FORECAST_ROADMAP.md`; `scripts/MO_127_seasonal_index_lookahead.py` + `outputs/mo127_*.{log,json,csv}`; `scripts/MO_128_puff_long_history_vs_connor.py` + `outputs/mo128_*.{log,json,csv}`; CLAUDE.md pointer to the register; `docs/SETTLED_FINDINGS.md` pending-review section; docs/design/settled-findings-and-agents.md; check_refs.py `.git`-suffix fix (morning). Session scratchpad `step1_history_check.py` not committed.
- customer-built-mo-api: Mo Chat glossary corrected (8987c77).

### Open questions

- Rob: OK the MO_80 cutoff fix (6/29 -> 6/28) and the time-based validation split; review settled-findings answers + proposals (and docs/SETTLED_FINDINGS.md statuses/length before CLAUDE.md import); redeploy Mo API; is the MO_126 script on his machine (not committed)?
- BUILT's "7%" definition (Connor/Brian).
- RunPod GPU access timing unknown.
- Blocker 0.3 (model worse than flat on 52+) still open; candidates: misaligned year-ago for series with gaps, 800-tree cap, wrong validation slice.
- Higher-tree sensitivity planned for MO_128 (skeptic's 800-tree-cap flag); not run.
- Retired accuracy figures in the other 12 files (register section 4): correct, mark superseded, or retire.
- Closed: MO_92 vs README 223 (answered: not settled, differently scoped); Meijer brief re-verify (already rebuilt Sept 25); Mo Chat accuracy wording (applied).

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

## Live session notes

<!-- Same-turn capture per docs/working-agreements/log-everything.md. /end-session moves these into the permanent record and empties this section. -->
- 2026-10-07 Decision (Jason, answering the ask to Rob): OK to fix the Q3 2026 cutoff in MO_80. Done: QUARTERS Q3 2026 -> ("2026-06-28", "2026-07-05", "2026-09-27") (the whole row was Mondays, not just the cutoff) and Q4 2026 forward-only start/end -> 2026-10-04 / 2026-12-27; MO_80 now asserts at import that every QUARTERS date is a Sunday (SPINS week-ending). MO_80, MO_127 and MO_128 import clean. Effect: Q3 2026 now scores h=1 and a full September; MO_127/MO_128 results stand as recorded (run on the old date) and Q3 2026 figures will shift slightly on re-run. Left unchanged as historical record: MO_84-MO_90 carry their own copies of 2026-06-29. Roadmap step 1, item 1 done.
- 2026-10-07 Decision (Jason): fix the harness to train exactly like production. Done in scripts/MO_80_quarterly_honest_backtest.py: new train_like_production() reproduces MO_26 -- last 13 weeks held out (time-based; target week for direct arms), recency weights lambda 0.02, early stopping (patience 50, min_delta from MO_26) up to production's cap, then refit on all data at the best iteration; hyperparameters read from MO_26 (lr 0.04, cap 6000); q10/q90 band models trained the same way; default --trees = production cap. Training constants (RECENCY_LAMBDA, TRAIN_VAL_WEEKS, LEARNING_RATE, TREES_CAP, EARLY_STOP_PATIENCE, EARLY_STOP_MIN_DELTA) added to mo_panel.FORECAST_CONTRACT and asserted at MO_80 import. Legacy fit()/LGBM kept only so MO_95 reproduces. MO_127/MO_128 now train through it (fit cache re-pointed) and default to the production cap; their recorded results used the old 800-tree, in-sample-validated training. Before the fix the harness differed from production on: lr 0.05 vs 0.04, no recency weights, 800 vs 6000 cap, validation = tr.tail() (last series, in-sample), no refit, band models without early stopping.
- 2026-10-07 Found: one production-equivalent fit at the 2025-12-28 cutoff (54,199 rows; val 2025-10-05..2025-12-28, 9,939 rows) ran to the 6000-tree cap without early stopping (244 s incl. refit). Production v11 itself is capped too: q50 best_iteration 6000 (= cap), total_units q50 5999; q10/q90 stop naturally at ~1,170. So the binding ceiling is now PRODUCTION's cap (MO_26 n_estimators 6000, min_delta 0) -- next lever (roadmap step 2/4): test a higher cap and/or learning rate, judged on the honest multi-week backtest (MO_29: a 12,000-tree ceiling was only 2.62% better on one-step pinball for 2.6x compute). Compute note: a full MO_127/MO_128 re-run at production training will take several hours (6000-tree fits plus ~7x slower prediction loops) -- a candidate for RunPod / parallel CPU.
- 2026-10-07 Q&A (Jason): are older weeks used to learn seasonal crests/troughs while recency weighting tempers magnitude? Answer (Claude): only partly. (1) The recency weight (lambda 0.02, MO_26) applies to whole rows, so it mutes seasonal information too -- at the Dec 2025 cutoff, Jan 2025 weighs ~0.37 and Jan 2024 ~0.13, the only two New Year turns in the panel. (2) The recursive one-step design flattens learned turns across 13 steps (MO_127/MO_128: forecasts anchored at the December trough never climb). (3) Seasonal shape enters via side channels (10% YAGO blend capped at 2x growth; STL index for short series). Also corrected: under-forecasting is concentrated in Q1 (~0.55 bias), not chronic (~1.07 elsewhere). Roadmap step 3 amended (docs/FORECAST_ROADMAP.md): separate recency for size (recent anchor) and shape (relative target, all years weighted nearly equally), both tuned on the honest backtest.
- 2026-10-07 Found (Claude): MO_126 never existed as a file -- an earlier Claude session on Jason's machine ran it inline (python heredoc, 2026-10-07T13:01Z, session 359b344d) and wrote scripts/outputs/mo126_band_breakdown.json (never committed). Code recovered verbatim from that session record into scripts/MO_126_band_breakdown.py with a provenance docstring (Jason approved). It scored the model in ANCHOR seasonal mode with the full-panel (look-ahead) index under the old 800-tree, in-sample-validated harness -- confirming the skeptic's guess. Rob's ask #4 (find MO_126) resolved.
- 2026-10-07 Decision (Jason): no GPU access yet; approved CPU plan -- A speed up the harness (batch the per-series recursive predictions per step, verified identical; cache trained models per cutoff), B yardstick (~20 monthly origins, score new series, history = real selling weeks, noise floor), C re-baseline at production training (flat, L4W, L12W, shipped model; replaces re-running MO_127/MO_128), D fair-training fixes (calendar-aligned year-ago, yoy clip test, LR x tree-cap probe), E MO_129, F small Optuna (3-4 origins, pruning, overnight); GPU only for the deep-model challenger. Machine: Apple M3 MacBook Air, 8 cores (4P+4E), 16 GB; lightgbm 4.6.0, optuna 4.9.0. One production-style fit ~244 s. Suggest asking Rob about RunPod CPU pods (32-64 cores) for C-F confirmation runs. Start A now.
- 2026-10-07 Done (task A, harness speed-up; Jason approved the plan). Profile at the Q2 2026 cutoff: forecasting ~34-35 s per cutoff regardless of tree count (per-series model-call overhead; 1,516 series x 13 steps); training 34 s at 800 trees, 87 s at 2,000 (~260 s at the 6000 production cap). Changes in scripts/MO_80_quarterly_honest_backtest.py: (1) run_production now batches the autoregressive predictions -- all series predicted in one model call per step, per-series state/blend/fallback unchanged; the original loop kept as _run_production_rowwise (reference only); check_batched_equivalence() asserts identical output. Verified on Q2 2026 and Q1 2026, q50 and q10/q90 bands: max abs diff 0.0 over 27,508 forecasts. Forecasting 33.7 s -> 1.1 s (~30x). (2) On-disk trained-model cache in train_like_production (scripts/outputs/model_cache/, git-ignored): key = SHA1 of the exact training rows/values + all settings + LightGBM version; MO_MODEL_CACHE=0 disables. A cached fit loads instantly; at production settings that saves ~260 s per cutoff per reuse. Next: task B (yardstick).
