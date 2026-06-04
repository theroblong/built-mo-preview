# Mo Query Purpose, Intent, Need, and Outcome

This page explains why each query exists in the Mo solution and how it contributes
to the user-facing product. It separates the cannibalization pipeline from the
price elasticity extension so query numbering remains understandable.

Open the visual page here:

- [mo_query_purpose_intent_need_outcome.html](/Users/jasonbrazeal/Documents/FirstAgent/mockups/mo_query_purpose_intent_need_outcome.html)

## Cannibalization Pipeline

| Step | Query or action | Purpose | Intent | Need | Outcome |
|---|---|---|---|---|---|
| C0 | Category extract normalization | Normalize raw SPINS fields and narrow to BUILT plus relevant category context. | Create a stable, reusable base from the raw extract. | Raw column names and mixed retail/geography fields are too brittle for downstream logic. | `built_filtered_weekly` |
| C1 | Enriched weekly base table | Attach product, flavor, pack, brand, and direct retail context. | Make every weekly row business-readable and model-ready. | Cannibalization depends on accurate product hierarchy and geography/account scope. | `built_enriched_weekly` |
| C2 | Universal comparison pool | Build valid focal/candidate SKU pairs for relationship distances 1-5. | Give UI and ML one comparison pool that can be filtered by mode. | Separate pair queries would be slow, inconsistent, and harder to govern. | `comparison_pool_weekly` |
| C2b | On-demand competitive pool | Build cross-flavor competitive pairs when a user asks for a brand comparison. | Keep broad competitor analysis available without pre-materializing every pair. | Distance-6 comparisons can explode in size if built for all SKUs and markets. | Returned directly to UI |
| C2c | Cross-flavor heatmap aggregation | Aggregate pre/post change by SKU and geography for cross-flavor diagnosis. | Show where related flavors are falling, flat, or rising. | Users need a visual way to separate product-specific donor loss from broad category softness. | Returned directly to UI |
| C2d | Scope bar metadata | Summarize active pool type, relationship distance, SKU count, and pair direction. | Make every diagnosis screen transparent about what comparison set is active. | Users need to know whether they are viewing pack ladder, flavor, brand, or competitor evidence. | Returned directly to UI |
| C3 | Focal pre/post aggregation | Compute pre/post metrics for each focal SKU across multiple scoring windows. | Establish whether the focal item gained demand, distribution, velocity, price, or promo support. | Cannibalization cannot be scored from post-period performance alone. | `built_prepost_features` |
| C4 | Donor pre/post aggregation | Apply the same window logic to likely donor SKUs. | Measure what happened to candidates that may have lost demand. | A focal SKU lift is not cannibalization unless donor movement is visible. | `donor_prepost_features` |
| C5 | Final ML feature assembly | Join focal and donor features, compute deltas, labels, confounds, and incremental share. | Convert evidence into training-ready examples and user-facing signal columns. | Models need one coherent feature table with deterministic labels and guardrails. | `ml_training_features` |
| C6 | Rolling stats and z-scores | Compute rolling averages, standard deviations, z-scores, and week-over-week deltas. | Detect abnormal demand, velocity, or distribution movement. | Event detection needs trend context, not just static values. | `event_detection_weekly` |
| C7 | New UPC detection | Find BUILT UPCs in the current period that have no prior history. | Identify new launches automatically. | New products need ramp handling before normal cannibalization scoring. | `new_upc_candidates` |
| C8 | New UPC classification | Classify new UPCs as new pack size, new flavor candidate, or relaunch/duplicate. | Decide how the new item should enter comparison logic. | A new pack size behaves differently from a relaunch or new flavor. | `new_upc_classifications` |
| C9 | Ramp monitoring | Track first 16 weeks, distribution trend, velocity trend, scoring status, and underperformance. | Avoid false-positive cannibalization alerts during launch ramp. | Early weeks are dominated by TDP expansion and incomplete baseline history. | `new_product_ramp_monitor` |
| C10 | Train cannibalization classifier | Train a model to estimate cannibalization status from assembled features. | Add probabilistic support to deterministic evidence. | Rules alone are useful but cannot rank nuanced cases at scale. | `model_cannibal_v3.pkl` |
| C11 | Train donor ranker | Train a model to rank likely donor SKUs. | Help users see which SKU is probably losing demand first. | Donor lists need ordering, not just eligibility. | `model_ranker_v3.pkl` |
| C12 | Train event detector | Train a model to identify material events worth surfacing. | Reduce dashboard hunting by pushing important cases forward. | Users should not scan every SKU/geography combination manually. | `model_event_v3.pkl` |
| C13 | Score focal/account/geography/window pairs | Generate production cannibalization scores and driver fields. | Turn model outputs into queryable business records. | UI screens need scored records with confidence, action, and explanation support. | `scored_cannibalization` |
| C14 | Assemble event queue | Combine scored outputs, suppression rules, and event typing. | Create the prioritized work queue for Mo. | Recommendations need event-level packaging, not isolated model rows. | `event_queue` |
| C15 | Auto-enroll new pack sizes | Add new pack-size candidates into pack ladder monitoring. | Keep the system current as the portfolio changes. | New packs should not wait for manual setup before monitoring starts. | `pack_ladder_pairs_weekly` update |
| C16 | Write new-pack events | Add NEW_PACK_SIZE events to the event queue. | Surface new pack-size monitoring to users. | Launch events need visible onboarding and scoring status. | `event_queue` |
| C17 | Weekly rescore trigger | Refresh incremental scores after each data load. | Keep Mo current with the latest SPINS feed. | Stale scores can mislead launch, assortment, and pricing decisions. | Incremental update |

## Price Elasticity Extension

| Query | Output table | Purpose | Intent | Need | Outcome |
|---|---|---|---|---|---|
| Q14 | `price_elasticity_weekly_features` | Add price per bar, log price, log units, promo depth bucket, and seasonality controls. | Build the core weekly feature layer for elasticity modeling. | Raw ARP and units are not enough to model price response cleanly. | Weekly price-response features ready for modeling and diagnosis. |
| Q15 | `price_pack_ladder_weekly` | Compare price levels between pack sizes of the same specific flavor. | Show whether the pack ladder has healthy or risky price gaps. | Pack-size pricing can create internal switching or collapse a pack role. | Pack ladder price diagnostics by flavor, account, geography, and week. |
| Q16 | `price_competitive_weekly` | Compare BUILT price per bar against Tier 1 competitors. | Separate competitive price pressure from internal BUILT switching. | Users need to know whether softness is caused by competitors or BUILT's own pricing. | Competitive price gap diagnostics for selected markets and accounts. |
| Q17 | `price_elasticity_training_features` | Build regression-ready windows for own-price, cross-price, and promo elasticity. | Prepare clean model inputs with guardrail context. | Elasticity models need usable price movement, adequate weeks, and confound controls. | Training set for own-price, cross-price, promo, and forecast models. |
| Q18 | `scored_price_elasticity` | Store model outputs, confidence, drivers, and recommended actions. | Make elasticity results queryable by the UI and Mo explanations. | Users need scored records, not notebook-only model results. | Elasticity summary, confidence, drivers, and action labels. |
| Q19 | `price_elasticity_forecast_weekly` | Store scenario forecasts for price and promo decisions. | Power the what-if calculator and low/base/high outcomes. | Pricing decisions need forecasted impact before action is taken. | Forecast records for planned ARP, promo, and competitor-gap scenarios. |
| Q20 | `mulo_food_pack_size_norms` | Create MULO FOOD protein bar norms for 1ct, 4pk, 8pk, and 12pk. | Benchmark BUILT pack pricing and productivity against category norms. | A value pack may look strong internally but still be mispriced against category expectations. | Norm table for ARP, price per bar, velocity, store selling, and distribution indexes. |
| Q21 | `flavor_protein_driver_features` | Compare flavor and protein content against sales, velocity, and store penetration. | Explain whether flavor, protein content, price, or distribution better explains demand. | Protein content can be a driver, but it should not be overclaimed without controls. | Driver features for MULO norms, explanation, and pricing context. |
| Q22 | `price_event_queue` | Store significant price, promo, new item, benchmark, confidence, and price-defense events. | Push important pricing situations to the user proactively. | Analysts should not inspect every price chart to find meaningful movement. | Prioritized pricing events with trigger, confidence, provenance, drivers, and action. |

## Shared Design Pattern

Every query supports one of four jobs:

- Prepare: normalize, enrich, and structure raw source data.
- Compare: create focal, donor, competitor, geography, and pack-ladder context.
- Score: convert evidence into model-ready features, confidence, and recommendations.
- Explain: surface events, provenance, guardrails, and plain-language actions.
