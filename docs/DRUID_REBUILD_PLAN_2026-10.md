# Druid rebuild plan: MULO label fix (DRAFT for Jason's approval, 2026-10-12)

**Why:** `built_filtered_weekly` double-counts MULO W/ Convenience totals for 2025-08-17 → 2026-04-12 (old and
new SPINS labels both present), and holds stale rows for 2025-10-05 → 2026-04-12. Q0 is fixed in the query
register (MULO FIX 1-3). Every downstream table is built from it, so the whole chain is re-run once.

**Goal (Jason):** run it once, correctly. No pseudo-errors, no rework.

## Timing (Jason, 2026-10-12: "unnecessary until next SPINS update? Rob may be importing data")
**Recommended: run this with the next SPINS update, not now.**
- Nothing in forecasting needs it now. The training panel and the MO_136 category pull use retailer rows,
  which are within ~0.5% in both versions. The doubling is confined to MULO+C rollup rows (Trends, Q20 norms,
  MULO-level comparison pools).
- Every SPINS update already re-runs Q1 → Q22 (Q1 and most steps replace whole tables). Doing the fix now means
  two full chain runs (now and at the update); doing it with the update means one, with Q0 run as the full
  four-year rebuild instead of the usual new-weeks batch.
- Rob loads into the same 8-slot cluster. Running a 1.5-3 day chain alongside his loads competes for slots and,
  if he loads new SPINS weeks into `spins_full`, the rebuild would have to be redone anyway.
- Until then: finish and test the runner (dry runs, register corrections), and agree the start with Rob so
  nothing else runs on the cluster during the chain. The current backup is harmless (a copy into a new table);
  keep it as the pre-fix snapshot.

## Facts checked live on 2026-10-12 (not taken from old notes)
| Fact | Result | Consequence |
|---|---|---|
| Task slots | 2 middle managers x 4 = **8 slots** | `maxNumTasks` (controller + workers) can never exceed 8; 8 takes the whole cluster |
| Durable shuffle storage (E14) | **Configured**: a test query with `durableShuffleStorage=true` succeeded | Keep it on for Q2, Q4, Q5, Q16 (the runbook's "pending" note is stale) |
| Tasks API polling | Works on long tasks; statements API is unsafe (2026-09-23 incident) | Runner polls the Tasks API only |
| Code that filters on old MULO geography names | None (API, UI, scripts, register) | Rename breaks nothing; Trends excluded-channel list needs the new label (API follow-up) |
| Baseline row counts | `scripts/outputs/druid_baseline_20261012.csv` (all 20 tables) | Used for the after-step checks |

## Global rules the runner enforces
1. **Write mode.** Every step uses `REPLACE INTO`. `OVERWRITE WHERE` (batched steps Q0, Q2) replaces only the
   batch window; `OVERWRITE ALL` replaces the table. This is the SQL equivalent of `appendToExisting: false`.
   The only append is **Q22b `INSERT INTO`**, which runs only immediately after Q22a succeeds (E26). Any other
   INSERT is refused.
2. **maxNumTasks = 4** for every step (1 controller + 3 workers). Evidence: Q2 took 11h 12m at 4 and ~11.4h at 8
   (README 145); 8 uses the entire cluster; 16 is impossible on 8 slots. The register's "8 is ~2x faster"
   comment is wrong and gets corrected.
3. **Settings come from the register's SET lines** for each step (sortMerge, disk buffering, durable shuffle,
   rowsPerSegment), passed as query context, except `maxNumTasks`, which is fixed at 4 by rule 2.
4. **One step at a time.** Each step waits for the previous step's task to succeed **and** its data check to pass.
5. **Polling:** Tasks API only. A 404 means "not visible yet", never success. No spot checks.
6. **A data check after every step** (task success alone is not trusted: README 142, E03):
   - batched steps: the window's row count equals the expected count (Q0) or is non-zero and printed per year (Q2);
   - whole-table steps: rows > 0, latest week = 2026-09-06 where the table is weekly, and the change against the
     baseline is printed. A change outside -50% / +50% **pauses the run** for review rather than continuing.
7. **Timeouts** per step = about 3x the longest recorded run, so a slow step is never mistaken for a failure.
8. **Resume, never redo.** Each finished-and-checked step is written to `scripts/outputs/druid_rebuild_state.json`.
   After any stop, the runner starts at the first unfinished step. Every step is a REPLACE, so re-running a failed
   step is safe.
9. **Date bounds are day-aligned** and substituted into every `__time` clause of the step (E17, E20), with an
   assert that each bound appears the expected number of times.
10. **Backup first.** `built_filtered_weekly_bak_20261012` must exist and match the source before Q0 runs.

## Steps, in order
| # | Step | Writes | Mode | Settings | Check after | Recorded time | Timeout |
|---|---|---|---|---|---|---|---|
| 0 | Backup | `built_filtered_weekly_bak_20261012` | 4 year windows | defaults | each window = source count | running now | 4h each |
| 1 | Q0 R1-R4 | `built_filtered_weekly` | OVERWRITE WHERE, 4 years | maxNumTasks 4 | window = expected (16,659,184 / 20,466,010 / 19,419,157 / 11,916,524); then `verify_built_filtered_weekly.py` | ~10-30 min each | 2h each |
| 2 | Q1 | `built_enriched_weekly` | OVERWRITE ALL | defaults | rows = `built_filtered_weekly` rows (68,460,875); latest week 2026-09-06 | 22 min - 1h51m | 6h |
| 3 | Q2 x4 years | `comparison_pool_weekly` | OVERWRITE WHERE, **2023, 2024, 2025, 2026 separately** | sortMerge, disk-buffered, durable shuffle, maxNumTasks 4 | each year > 0, printed vs baseline (6.48M / 9.87M / 9.51M / 22.57M) | 11h 12m for 2025-26 together | 20h each |
| 4 | Q3 | `built_prepost_features` | OVERWRITE ALL | defaults | rows, latest week | 19 min | 2h |
| 5 | Q4 | `donor_prepost_features` | OVERWRITE ALL | register SETs | rows, latest week | 28-51 min | 4h |
| 6 | Q5 | `ml_training_features` | OVERWRITE ALL | register SETs | rows | 2-16 min | 2h |
| 7 | Q6, Q7, Q8, Q9 | event / new UPC / ramp tables | OVERWRITE ALL each | defaults | rows, latest week | 8-16 min each | 2h each |
| 8 | Q14, Q15 | price elasticity weekly, pack ladder | OVERWRITE ALL | defaults | rows, latest week | 3-7 min | 2h |
| 9 | Q16 | `price_competitive_weekly` | OVERWRITE ALL | register SETs | rows (447M today), latest week | 2h 16m | 8h |
| 10 | Q17 | `price_elasticity_training_features` | OVERWRITE ALL | defaults | rows; `MAX(post_13w_weeks_count) <= 13` | 7 min | 2h |
| 11 | Q20, Q21 | pack-size norms, flavor-protein drivers | OVERWRITE ALL | defaults | rows, latest week | 2 min, 43 min | 3h |
| 12 | Q22a then Q22b | `price_event_queue` | REPLACE ALL, then INSERT | defaults | rows after each | ~3 min | 1h |

Not in this run: QS1-QS3 seeds (their inputs, `spins_full`, are unchanged; QS1's new-UPC check runs first as a
read-only gate and stops the run if it finds UPCs missing from `flavor_mapping`). Q10-Q13, Q18, Q19 do not
exist in the register. Python steps afterward: MO_14.7 (appends events to `price_event_queue`), the training-panel
rebuild (MO_25) as a new labeled version, and model scoring, each run and checked separately.

**Expected total:** about 1.5-3 days of Druid time, most of it Q2 (four year-batches) and Q16. Everything after
Q2 is a few hours.

## Decisions for Jason
1. **Q2 in four one-year batches** (recommended; E16 showed large windows fail and smaller ones are safer to
   retry) instead of 2023 / 2024 / 2025-26.
2. **Pause on a change outside -50% / +50%** (recommended) vs. stop on any change.
3. Approve the plan, then the runner is written, dry-run printed for review, and only then started.

## Runner status (2026-10-12)
- Built: `scripts/druid_pipeline.py` (`plan` = read-only; `run --execute` = writes; `status`; `accept`).
  The Q0-only `scripts/run_q0_rebuild.py rebuild` now also requires `--execute`.
- Dry run (`plan`, log `scripts/outputs/druid_pipeline_plan_20261012.log`): **all 25 steps pass Druid's MSQ
  EXPLAIN** (parsed and planned without running), with the bounds, write mode and settings shown per step; full SQL
  per step in `scripts/outputs/druid_pipeline_dryrun/`. Only `Q22b.sql` contains INSERT.
- Safety check after the dry run: all 20 pipeline tables have the same row counts as the baseline; no probe table
  was created; the only Druid task running was the backup.
- Gates run today (read-only): no BUILT UPCs missing from `flavor_mapping`; no duplicate UPCs.
- Stale notes corrected: register Q2 `maxNumTasks` 8 -> 4; runbook Q2/Q4/Q5 `maxNumTasks` 16 -> 4 and E14
  (S3 shuffle) marked resolved.
