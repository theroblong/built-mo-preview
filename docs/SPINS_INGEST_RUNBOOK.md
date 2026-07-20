# SPINS Data Ingest Runbook

**Purpose:** Step-by-step procedure for ingesting a new SPINS data drop into Druid and retraining the full Mo ML pipeline.

**Last validated:** 2026-07-20  
**Extract format reference:** `All_items_extract_41926-h100.csv` (214-column format, April 2026 sample)  
**Warning:** The older `All_items_extract_100.csv` (167-column format) is **missing 18 Q0 required fields** including Channel/Outlet, Geography Level, Retail Account, and Base ARP — it cannot be used.

---

## Overview

```
Brian exports SPINS → Rob ingests to spins_full → Jason runs Q-series (Druid) → Jason runs P-series (Python) → FP&A report
```

Total elapsed time (estimate): 3–5 hours end-to-end (mostly Druid compute + model training wait time)

---

## Part 0 — SPINS Export (Brian)

### Required extract format

The SPINS report must be exported with the **214-column configuration** used for the April 2026 extract (`All_items_extract_41926-h100.csv`). All 214 columns must be present. Q0 will silently produce nulls or fail if any of the 55 required columns below are absent.

**55 Q0-critical columns (must be present):**

| # | Column name |
|---|---|
| 1 | `Channel/Outlet` |
| 2 | `Geography Level` |
| 3 | `Retail Account` |
| 4 | `Retail Account Level` |
| 5 | `Geography` |
| 6 | `Time Period End Date` |
| 7 | `Department` |
| 8 | `Category` |
| 9 | `Subcategory` |
| 10 | `Brand` |
| 11 | `UPC` |
| 12 | `Description` |
| 13 | `PACK COUNT` |
| 14 | `FLAVOR` |
| 15 | `NFP - PROTEIN` |
| 16 | `NFP RANGES - PROTEIN VALUE` |
| 17 | `NFP - SUGARS` |
| 18 | `NFP - CALORIES` |
| 19 | `STORAGE` |
| 20 | `UNIT OF MEASURE` |
| 21 | `Units` |
| 22 | `Units, Yago` |
| 23 | `Base Units` |
| 24 | `Base Units, Yago` |
| 25 | `Dollars` |
| 26 | `Base Dollars` |
| 27 | `TDP` |
| 28 | `TDP, Yago` |
| 29 | `Average Weekly TDP` |
| 30 | `Max % ACV` |
| 31 | `Avg % ACV` |
| 32 | `# of Stores` |
| 33 | `# of Stores Selling` |
| 34 | `% of Stores Selling` |
| 35 | `Average Weekly Units SPM` |
| 36 | `Average Weekly Units Per Store Selling Per Item` |
| 37 | `Units SPM Per Item` |
| 38 | `Average Weekly Units per Store Selling` |
| 39 | `ARP` |
| 40 | `ARP, Yago` |
| 41 | `Base ARP` |
| 42 | `ARP % Discount, Any Promo` |
| 43 | `Units, Promo` |
| 44 | `Units, Non-Promo` |
| 45 | `Units, % Promo` |
| 46 | `TDP, Any Promo` |
| 47 | `TDP, Non-Promo` |
| 48 | `Promo Weeks` |
| 49 | `Incr Units` |
| 50 | `Incr Dollars` |
| 51 | `Units ,% Lift, TPR` |
| 52 | `Units ,% Lift, Any Display` |
| 53 | `Units ,% Lift, Any Feature` |
| 54 | `First Week Selling` |
| 55 | `Number of Weeks Selling` |

**Scope filters (must match original extract):**
- Product scope: BUILT (all brand lines) + Subcategory = `WELLNESS & NUTRITION BARS` + `GRANOLA & SNACK BARS`
- Geography levels: CRMA and RMA rows (do NOT filter these out at export time)
- Channels: CONVENTIONAL|FOOD, CONVENTIONAL|MASS MERCH, CONVENTIONAL|MULTI OUTLET, CONVENTIONAL|MILITARY, CONVENTIONAL|CONVENIENCE — all included
- Date range: **Full history from first available week through the new end date** (full refresh) OR new weeks only if doing a delta append (see Part 1B)
- Time Period End Date format: `MM/DD/YYYY`

**Tip for Brian:** If the SPINS report template from the April 2026 extract is still saved, open it, update the end date, and re-export. This avoids re-selecting all 214 columns manually. Verify column count = 214 before depositing.

### Deposit to MinIO

Upload the exported CSV to the MinIO bucket. Coordinate with Rob for the bucket path and credentials. File naming convention: `All_items_extract_MMDDYY.csv` (e.g., `All_items_extract_72026.csv` for a July 20, 2026 export).

---

## Part 1 — Pre-Ingest Baseline Check (Rob)

Before touching `spins_full`, record the current state:

```sql
-- 1. Record current high-water mark
SELECT MIN(__time), MAX(__time) FROM "spins_full";
-- Current state: 2023-01-08 → 2026-04-19 (approximately)

-- 2. Record row count per year (use as post-ingest sanity check)
SELECT FLOOR(__time TO YEAR) AS yr, COUNT(*) AS rows
FROM "spins_full"
GROUP BY 1
ORDER BY 1;

-- 3. Record distinct BUILT UPC count (spot new items after ingest)
SELECT COUNT(DISTINCT "UPC") FROM "spins_full" WHERE "Brand" LIKE 'BUILT%';
```

Save these numbers before proceeding.

---

## Part 1 — Druid Ingest: New Weeks Only (Rob)

**DO NOT use `OVERWRITE ALL` or `INSERT INTO` for `spins_full`.** `OVERWRITE ALL` times out on this cluster at ~97M rows (cluster task duration limit ~1.5h — see error register E03). `INSERT INTO` creates duplicate rows if re-run.

**The safe pattern:** `REPLACE INTO … OVERWRITE WHERE` on the new period only. This replaces only the Druid segments covering the new date range; all historical segments (2023–prior end date) remain untouched on disk and are not re-read or re-written.

### Step 1 — Confirm the gap boundary

```sql
SELECT MAX(__time) AS current_max FROM "spins_full";
-- Example result: 2026-04-19T00:00:00.000Z
```

Brian's new file should start at or before this date (one week of overlap is fine — the OVERWRITE will cleanly replace that boundary week). If there is a gap (e.g., current max is April 19 but Brian's new file starts at June 1), **stop and resolve with Brian** before ingesting — a gap in `spins_full` becomes a gap in `built_filtered_weekly` and breaks all rolling-window features (lag52, velocity z-scores) at that boundary.

### Step 2 — Ingest new weeks via OVERWRITE WHERE

```sql
-- Replace only the new period. Start 1 week before current MAX to cleanly
-- handle the boundary; future bound must be explicit and DAY-aligned (E20).
-- Column names in spins_full have commas stripped (E01):
--   "Units, Yago" in CSV → "Units Yago" in Druid
--   "ARP % Discount, Any Promo" → "ARP % Discount Any Promo"  (etc.)
-- Rob's original native batch ingest spec maps these — use the same spec.

REPLACE INTO "spins_full"
OVERWRITE WHERE __time >= TIMESTAMP '2026-04-12'   -- one week before current MAX
            AND __time <  TIMESTAMP '2028-01-01'   -- explicit future bound (E20)
SELECT
  __time,                                      -- already a Druid timestamp from prior ingest
  "Channel/Outlet"          AS channel_outlet,
  -- ... (all column mappings from original ingest spec)
FROM EXTERN(
  '{"type":"s3","uris":["s3://mo-ml/spins/All_items_extract_MMDDYY.csv"],...}',
  '{"type":"csv","findColumnsFromHeader":true}'
)
WHERE __time >= TIMESTAMP '2026-04-12'
  AND __time <  TIMESTAMP '2028-01-01'
PARTITIONED BY DAY
CLUSTERED BY "UPC", "Channel/Outlet", "Retail Account", "Geography";
```

**Note:** Rob should use the same native batch ingest spec structure that was used for the original `spins_full` load (E01 column mapping is already baked in). The only change is the `OVERWRITE WHERE` bounds and the MinIO URI pointing to Brian's new file.

### Step 3 — Post-ingest validation

```sql
-- A. New high-water mark
SELECT MIN(__time), MAX(__time) FROM "spins_full";
-- MAX should now reflect the new end date from Brian's export.

-- B. Historical data intact — year counts should not change for 2023/2024/2025
SELECT FLOOR(__time TO YEAR) AS yr, COUNT(*) AS rows
FROM "spins_full"
GROUP BY 1
ORDER BY 1;
-- Rows for 2023, 2024, 2025 must match the pre-ingest baseline exactly.
-- Only the year(s) covered by the new file should show changed/new counts.

-- C. No duplicate weeks (most important)
SELECT __time, COUNT(*) AS row_count
FROM "spins_full"
WHERE __time >= TIMESTAMP '2026-04-01'   -- the boundary zone
GROUP BY __time
ORDER BY __time;
-- Each week-end date should appear exactly once more than in the prior count.
-- If any week shows double the expected row count, REPLACE ran over an
-- existing segment that wasn't fully replaced — escalate to Rob.

-- D. No gap in weekly cadence
SELECT __time
FROM "spins_full"
WHERE __time >= TIMESTAMP '2026-01-01'
GROUP BY __time
ORDER BY __time;
-- Dates should be consecutive Sundays (or your week-end day). Any missing
-- week in the sequence is a gap that must be resolved before running Q0.

-- E. New BUILT UPCs (expect growth if BUILT launched any items)
SELECT COUNT(DISTINCT "UPC") FROM "spins_full" WHERE "Brand" LIKE 'BUILT%';
-- Compare to pre-ingest baseline. Unexpected shrink = ingest error.

-- F. Row count in new period is plausible
SELECT COUNT(*) FROM "spins_full"
WHERE __time > TIMESTAMP '2026-04-19';  -- weeks beyond prior end date
-- Should be: (number of new weeks) × ~(prior average weekly row count ±20%)
```

All six checks must pass before proceeding to Part 2.

---

## Part 2 — New UPC Check (Jason)

**Run before QS1.** New BUILT UPCs that appeared in the latest SPINS drop will have `NULL` flavor, pack count, and size in `flavor_mapping` unless QS1 is updated first.

```sql
-- Find BUILT UPCs in spins_full that are NOT yet in flavor_mapping
SELECT DISTINCT s."UPC", s."Description", s."PACK COUNT", s."FLAVOR"
FROM "spins_full" s
LEFT JOIN "flavor_mapping" fm ON s."UPC" = fm.upc
WHERE s."Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF')
  AND fm.upc IS NULL
ORDER BY s."UPC"
```

If this returns rows: add a `WHEN '<new_upc>' THEN ...` block to each CASE expression in QS1 for:
- `brand` (BUILT BAR / BUILT PUFF / BUILT SOUR PUFF)
- `flavor_family` (e.g., CHOCOLATE MINT, COOKIES AND CREAM)
- `specific_flavor_raw` (e.g., 'Mint Chip')
- `specific_flavor_normalized` (same as raw unless overridden)
- `pack_count` (integer: 1, 4, 8, 12, 13, 16, 18...)
- `size` (oz, decimal)

If this returns 0 rows: skip ahead to QS1 re-run (no edits needed).

---

## Part 3 — Q-Series: Druid Derived Tables (Jason)

Run queries in this exact order. Each depends on the output of the previous.

**Estimated total time: 60–120 minutes**

### Lookup seeds (always re-run in full)

```
QS1  → flavor_mapping           OVERWRITE ALL  (update CASE blocks first if new UPCs found in Part 2)
QS1v → validation               (expect 0 rows)
QS2  → flavor_canonical_overrides  OVERWRITE ALL  (re-run if any flavor normalization changed)
QS3  → item_catalog             OVERWRITE ALL  (re-run if a new competitor brand needs tier assignment)
```

QS1–QS3 are small lookup tables (< 200 rows). `OVERWRITE ALL` is fast and safe here.

### Q0 and Q1 — passthrough/enrichment (incremental WHERE, same pattern as spins_full)

Q0 reads `spins_full` and filters/renames. Q1 enriches with the lookup tables. Both are pure passthrough — no rolling windows, no lag features. **Run these incrementally, covering only the new period plus one week of overlap:**

```sql
-- Q0 — new period only
REPLACE INTO "built_filtered_weekly"
OVERWRITE WHERE __time >= TIMESTAMP '2026-04-12'
            AND __time <  TIMESTAMP '2028-01-01'
SELECT __time, channel_outlet, retail_account, ...
FROM "spins_full"
WHERE __time >= TIMESTAMP '2026-04-12'
  AND __time <  TIMESTAMP '2028-01-01'
  AND ("Brand" LIKE 'BUILT%' OR "Subcategory" = 'WELLNESS & NUTRITION BARS')
PARTITIONED BY DAY
CLUSTERED BY upc, channel_outlet, retail_account, geography_raw;
```

Same pattern for Q1. Historical segments from 2023–2025 are untouched.

**Verify after Q0:**
```sql
SELECT MAX(__time) FROM "built_filtered_weekly";
-- Should match the new end date from Brian's export

SELECT FLOOR(__time TO YEAR) AS yr, COUNT(*) AS rows
FROM "built_filtered_weekly" GROUP BY 1 ORDER BY 1;
-- 2023/2024/2025 row counts unchanged from prior run
```

**Note — Q0 batch size:** If the new period spans more than one year, Q0 will time out with `OVERWRITE ALL` (E03). Run it in annual batches using annual `OVERWRITE WHERE` bounds, the same pattern used for the original build. Each batch takes ~10–25 minutes.

### Q2 — comparison pool (OVERWRITE ALL, requires special settings)

Q2 self-joins `built_enriched_weekly` on flavor/brand to build all focal/candidate pairs. It **must** be re-run in full because new UPCs (both BUILT and competitor) enter the pair set. Running it on only the new period would leave historical pairs missing the new SKUs.

Q2 requires these SET commands (see E10, E13, E14, E16 in error register — without them the query fails):

```sql
SET sqlJoinAlgorithm = 'sortMerge';
SET maxNumTasks = 16;
SET rowsPerSegment = 5000000;
-- SET durableShuffleStorage = 'true';  -- uncomment if Rob has completed MSQ S3 config (E14)
```

Q2 must be run in **annual batches** with explicit `__time` filters on BOTH sides of the join (E17):

```sql
-- Batch 1
REPLACE INTO "comparison_pool_weekly"
OVERWRITE WHERE __time >= TIMESTAMP '2023-01-01' AND __time < TIMESTAMP '2024-01-01'
SELECT ...
FROM "built_enriched_weekly" c
JOIN  "built_enriched_weekly" f ON ...
WHERE c.__time >= TIMESTAMP '2023-01-01' AND c.__time < TIMESTAMP '2024-01-01'
  AND f.__time >= TIMESTAMP '2023-01-01' AND f.__time < TIMESTAMP '2024-01-01'
...

-- Batch 2: 2024-01-01 → 2025-01-01
-- Batch 3: 2025-01-01 → 2026-01-01
-- Batch 4: 2026-01-01 → 2028-01-01  (new period; adjust annually)
```

Wait for each batch to complete before starting the next.

### Q3, Q4, Q5 — pre/post features and ML training table (OVERWRITE ALL)

These compute pre/post windows anchored to `first_week_selling` and rolling averages that span up to 52 weeks. They must be re-run in full — a new week of data can change the post-window aggregate for any SKU whose post window now includes that week.

Q4 and Q5 also require the sort-merge settings (same as Q2, large-table joins).

```
Q3  → built_prepost_features      OVERWRITE ALL
Q4  → donor_prepost_features      OVERWRITE ALL  (sortMerge + maxNumTasks = 16)
Q5  → ml_training_features        OVERWRITE ALL  (sortMerge + maxNumTasks = 16)
```

### Q6–Q9 and Q14–Q22 (OVERWRITE ALL)

```
Q6   → event_detection_weekly          OVERWRITE ALL  (rolling z-scores; re-run full)
Q7   → new_upc_candidates              OVERWRITE ALL
Q8   → new_upc_classifications         OVERWRITE ALL
Q9   → new_product_ramp_monitor        OVERWRITE ALL

Q14  → price_elasticity_weekly_features   OVERWRITE ALL
Q15  → price_pack_ladder_weekly           OVERWRITE ALL
Q16  → price_competitive_weekly           OVERWRITE ALL
Q17  → price_elasticity_training_features OVERWRITE ALL
Q20  → mulo_food_pack_size_norms          OVERWRITE ALL
Q21  → flavor_protein_driver_features     OVERWRITE ALL
Q22a → price_event_queue (COMPETITIVE_PRICE_GAP)   REPLACE INTO OVERWRITE ALL
Q22b → price_event_queue (PACK_LADDER_COMPRESSION) INSERT INTO  (append to Q22a output — E26)
```

All SQL blocks are in `docs/mo_druid_query_register.md`.

**Spot-check after Q5:**
```sql
SELECT COUNT(*) FROM "ml_training_features";
-- Baseline: ~60,695 rows (2026-06-08); will grow with new launch events and new weeks
```

---

## Part 4 — P-Series: Python ML Retrain and Score (Jason)

Run in order. All scripts are in `scripts/`. All write-backs go through `mo_writeback.py` — each script prints a Druid ingest spec that must be submitted manually.

```
MO_10  → model_cannibal_vN.pkl          (retrain cannibalization classifier)
MO_11  → model_donor_ranker_vN.pkl      (retrain donor ranker)
MO_12  → model_event_detector_vN.pkl    (retrain event detector)
MO_13  → scored_cannibalization         (score → Druid write-back)
MO_14  → event_queue                    (assemble events)
MO_15  → event_queue                    (new pack enrollment)
MO_16  → price_elasticity_training_features  (build regression features)
MO_17  → scored_price_elasticity        (score → Druid write-back)
MO_18  → price_elasticity_forecast_weekly   (→ Druid write-back)
MO_14.7→ price_event_queue              (price events → Druid write-back)
MO_19  → cannibalization_rate_weekly    (→ Druid write-back)
MO_20  → model_cannibal_rate_vN.pkl     (retrain cannib rate model)
MO_21  → cannibalization_rate_forecast_weekly  (→ Druid write-back)
```

**For each write-back:** Review the printed ingest spec, then POST it to Druid (or use the Druid console). The spec uses `appendToExisting: true`.

**After MO_13, verify coverage:**
```sql
SELECT COUNT(*) FROM "scored_cannibalization"
-- Baseline: scored combinations exist for ~48% of focal/donor pairs
-- (lower for new-launch SKUs due to 8-week data maturity gate in Q5)
```

---

## Part 5 — FP&A Report Rebuild (Jason)

```bash
# Requires authorization from Jason, Rob, or Brian before running
bash run_fpa_report.sh
```

**Then re-run quantile calibration** (constants must be refreshed after new forecasts):
```bash
python scripts/MO_67_quantile_calibration_audit.py
python scripts/MO_67b_q90_recalibration.py
```

Updated calibration constants write to `outputs/mo67_calibration_constants.json` and are picked up by MO_27 on the next report run.

---

## Part 6 — Post-Ingest Validation (Jason)

Run the Phase A/B audit scripts to confirm the new model version is not drifting or biased:

```bash
python scripts/MO_68_per_series_drift_detection.py   # drift scorecard
python scripts/MO_69_residual_structure_audit.py      # bias audit
python scripts/MO_71_distribution_shift_detection.py  # feature shift audit
```

Check outputs in `outputs/mo68_*.json`, `mo69_*.json`, `mo71_*.json`. Any FAIL verdict warrants investigation before releasing the new model version to users.

---

## Contacts and access

| Step | Owner | Access needed |
|---|---|---|
| SPINS export | Brian | SPINS platform credentials |
| MinIO deposit | Brian (or Rob) | MinIO bucket write access |
| Druid ingest (spins_full) | Rob | Druid cluster admin + MinIO read |
| Q-series SQL | Jason | Druid cluster write (REPLACE INTO) |
| P-series Python | Jason | Druid cluster read/write + MinIO write |
| Druid ingest specs (MO_xx write-backs) | Jason (submit) | Druid cluster write |

---

## Known constraints and risks

| Risk | Detail | Mitigation |
|---|---|---|
| `OVERWRITE ALL` timeout | Cluster task limit ~1.5h; `spins_full` at 97M rows will always fail (E03) | Use `OVERWRITE WHERE` with year-range batches only — never `OVERWRITE ALL` for spins_full |
| `INSERT INTO` duplicates | `INSERT INTO` is not idempotent; re-running doubles every row in the period | Use `REPLACE INTO … OVERWRITE WHERE` for all spins_full updates |
| Data gap in new file | Brian's export start date doesn't connect to current `MAX(__time)` | Run Step 1 gap check before ingest; stop and resolve if gap found |
| Column names (E01) | CSV has commas: `"Units, Yago"` — Druid stores `"Units Yago"` (no comma) | Rob's original ingest spec already maps these; use the same spec |
| Wrong extract format | `All_items_extract_100.csv` (167 cols) is missing 18 Q0 required fields | Always use the 214-column format; verify column count = 214 before depositing |
| New BUILT UPCs | Appear as NULL in `flavor_mapping` if QS1 not updated | Run the new-UPC check query (Part 2) before QS1 |
| New competitor brands | New Tier 1/2/3 competitor entering the category won't have a tier in `item_catalog` | Compare `SELECT DISTINCT source_brand FROM built_filtered_weekly` after Q0 against current QS3 list |
| Q2 sort-merge OOM | Self-join on 62M rows; worker pods OOM-evicted without durable shuffle (E13–E19) | Required settings: `SET sqlJoinAlgorithm='sortMerge'; SET maxNumTasks=16;`; annual batches; Rob to complete MSQ S3 shuffle config (E14) |
| Q2 OVERWRITE WHERE alignment | Open-ended upper bound fails with INVALID_INPUT (E20) | Always use explicit future upper bound: `AND __time < TIMESTAMP '2028-01-01'` |
| Q2 filter must cover both join sides | Time filter on one side not inferred by sort-merge planner (E17) | Add explicit `c.__time` AND `f.__time` bounds in WHERE clause |
| Druid `appendToExisting: false` | Silently drops columns → UI returns empty arrays | All MO_xx write-backs use `appendToExisting: true`; never override this |
| Data maturity gates | Q5 filters `focal_post_weeks_count >= 8`; new SKUs under 8 weeks won't score | Expected behavior; new SKUs enter scoring automatically on next refresh |
| v4 retrain trigger | No new SPINS data → retraining is pointless (same training rows, collapsed holdout) | Only retrain when new data extends the date range in `spins_full` |
| `first_week_selling` format (E11) | Stored in spins_full as ISO (`2023-01-08`), not MM/dd/yyyy | Q3/Q4/Q5 use `TIME_PARSE(first_week_selling, 'yyyy-MM-dd')` — already fixed |
| Q22 UNION ALL blocked (E26) | MSQ doesn't support UNION ALL between aggregated CTEs | Q22 is split into Q22a (REPLACE) + Q22b (INSERT) — already implemented |
