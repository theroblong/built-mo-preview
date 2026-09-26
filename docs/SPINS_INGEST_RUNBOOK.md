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

**⛔ MANDATORY gate after Q6 — do not proceed to P-series until this passes:**
```sql
SELECT
  MAX(__time)                          AS edw_latest_week,
  (SELECT MAX(__time) FROM "built_filtered_weekly") AS spins_latest_week
FROM "event_detection_weekly"
```
`edw_latest_week` must be within 14 days of `spins_latest_week`. If the gap is larger, Q6 failed or was skipped — stop, diagnose, and re-run Q6 before continuing.

Background: On 2026-09-25, Q6 was not re-run after a SPINS ingest. `event_detection_weekly` remained stale at 2026-04-12 while `built_filtered_weekly` was current through Sept 2026. This caused sparklines, cannibal rates, ramp monitor, and forecast pipeline to all silently serve stale data in a client demo.

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

**⚠️ MO_12 reads `event_detection_weekly`.** If Q6 was skipped or stale, the event detector model will be undertrained on incomplete data. Always confirm the Q6 gate passed before running MO_12.

**⚠️ MO_19 reads `event_detection_weekly`.** Same dependency — stale Q6 = stale cannibal rates.

**⚠️ After MO_19, immediately run the replacement ingest script** to prevent row accumulation:
```bash
python druid_ingest_cannibal_rate.py --poll
```
This submits the MO_19 spec with `appendToExisting=False`, fully replacing `cannibalization_rate_weekly`. Without this step, each MO_19 run appends ~814K duplicate rows. The historical dedup (3 stacked runs as of Sept 2026) was resolved by `druid_cannibal_rate_dedup.py`.

**After MO_13, verify coverage:**
```sql
SELECT COUNT(*) FROM "scored_cannibalization"
-- Baseline: scored combinations exist for ~48% of focal/donor pairs
-- (lower for new-launch SKUs due to 8-week data maturity gate in Q5)
```

### Forecast pipeline (MO_22–MO_27, MO_46, MO_55) — run after MO_10–MO_21

These steps were historically omitted from the P-series checklist and were missed in the Sept 24 2026 cycle. They are **required** on every SPINS ingest that extends the date range.

```
MO_22  → comparison_pool_prelaunch_baseline  (reads event_detection_weekly)
MO_24  → new_product_ramp_monitor            (reads event_detection_weekly)
MO_46  → rolling_signals_weekly.parquet      (reads event_detection_weekly; input to MO_25)
MO_25  → retailer_sales_weekly.parquet       (reads event_detection_weekly + MO_46 output)
MO_26  → forecast model retrain              (reads MO_25 output)
MO_27  → retailer_sales_forecast             (→ outputs/ spec only; MUST submit manually — see below)
MO_55  → portfolio constraint scoring        (reads event_detection_weekly)
```

**⚠️ MANDATORY after MO_27 — submit the forecast to Druid:**
```bash
cd scripts
python druid_ingest_forecast.py   # submits outputs/retailer_sales_forecast_ingest_spec.json
# Expect: 200 {"task":"index_parallel_retailer_sales_forecast_..."}
# Wait 60–90s, then verify SKU View forecast drawer shows correct forward dates.
```

MO_27's `write_back()` saves the ingest spec locally but does NOT submit to Druid (human review required). If this step is skipped, the `retailer_sales_forecast` Druid table remains stale from the prior cycle and the SKU View drawer will show forecast dates in the past.

`appendToExisting=False` is intentional: the table is a rolling 13-week forward window replaced each cycle. Appending would accumulate duplicate rows for overlapping forecast weeks (the API has no dedup).

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

## Post-cycle Druid audit checklist

After every pipeline cycle run, verify all datasources are current by running this query for each table. The expected latest date and row count are noted — anything older than expected = a spec was not submitted.

```bash
# Run from scripts/ after each pipeline cycle:
cd scripts
python3 << 'EOF'
from dotenv import load_dotenv; load_dotenv('../.env')
from mo_druid_client import query_druid

EXPECTED = [
    # (datasource, expected_latest_approx, note)
    ('built_filtered_weekly',               'SPINS batch end date',    'Q0/Q1 — SPINS data'),
    ('event_detection_weekly',              'SPINS batch end date',    'Q6 — must match built_filtered_weekly'),
    ('scored_cannibalization',              'run date',                'MO_13'),
    ('event_queue',                         'run date',                'MO_14/15'),
    ('price_event_queue',                   'SPINS batch end date',    'Q22 MSQ — not a write_back spec'),
    ('scored_price_elasticity',             'run date',                'MO_17'),
    ('price_elasticity_forecast',           'run date',                'MO_18'),
    ('cannibalization_rate_weekly',         'SPINS batch end date',    'MO_19'),
    ('cannibalization_rate_forecast_weekly','13wk forward from run',   'MO_21'),
    ('comparison_pool_prelaunch_baseline',  'latest focal launch date','MO_22 — see note below'),
    ('competitor_pack_size_norms',          'run date',                'MO_23'),
    ('new_product_ramp_monitor',            'SPINS batch end date',    'MO_24'),
    ('retailer_sales_forecast',             '13wk forward from run',   'MO_27 — submit druid_ingest_forecast.py'),
    ('retailer_sales_tdp_velocity',         'run date',                'MO_64 — re-run if MO_25/27 updated'),
]
for ds, expected, note in EXPECTED:
    try:
        df = query_druid(
            f"SELECT TIME_FORMAT(__time, 'yyyy-MM-dd') AS wk, COUNT(*) AS n "
            f"FROM \"{ds}\" ORDER BY __time DESC LIMIT 1", timeout=20)
        latest = df.iloc[0]['wk'] if len(df) else 'EMPTY'
        rows_df = query_druid(f'SELECT COUNT(*) AS n FROM "{ds}"', timeout=20)
        rows = rows_df.iloc[0]['n']
        print(f"{'OK' if latest >= '2026-09' else 'CHECK':<5}  {ds:<48} latest={latest}  rows={rows:>9,}  [{note}]")
    except Exception as e:
        print(f"ERR    {ds:<48} {str(e)[:60]}")
EOF
```

### Sept 25 2026 audit findings

Full cycle ran Sept 24 2026. Findings:

| # | Datasource | Latest in Druid | Script | Status | Action |
|---|---|---|---|---|---|
| ✅ | built_filtered_weekly | 2026-09-06 | Q0/Q1 | Current | — |
| ✅ | event_detection_weekly | 2026-09-06 | Q6 | Current | — |
| ✅ | scored_cannibalization | 2026-09-24 | MO_13 | Current | — |
| ✅ | event_queue | 2026-09-24 | MO_14/15 | Current | — |
| ✅ | price_event_queue | 2026-09-06 | Q22 (MSQ) | Current | Q22 writes directly — no spec needed |
| ✅ | scored_price_elasticity | 2026-09-24 | MO_17 | Current | — |
| ✅ | price_elasticity_forecast | 2026-09-24 | MO_18 | Current | — |
| ✅ | cannibalization_rate_weekly | 2026-09-06 | MO_19 | Current | — |
| ✅ | cannibalization_rate_forecast_weekly | 2026-12-06 | MO_21 | Current | — |
| ✅ | competitor_pack_size_norms | 2026-09-24 | MO_23 | Current | — |
| ✅ | new_product_ramp_monitor | 2026-09-06 | MO_24 | Current | — |
| ✅ | retailer_sales_forecast | 2026-12-06 | MO_27 | **FIXED Sept 25** | Disable-all + kill + re-ingest (see Fix below) |
| ✅ | comparison_pool_prelaunch_baseline | 2026-07-19 | MO_22 | **FIXED Sept 25** | 330 accumulated segments cleared; re-ingested clean 57,231 rows from Sept 24 run |
| ✅ | retailer_sales_tdp_velocity | 2026-09-25 | MO_64 | **FIXED Sept 25** | Re-ran MO_64; 2,285 rows; appended to Jul 9 snapshot |
| ✅ | retailer_sales_forecast_adj | 2026-12-06 | MO_55 | **FIXED Sept 25** | Disable-all + kill + re-ingest; MO_55 now calls write_back() |
| ✅ | causal_impact_scores | 2026-04-19 | MO_72 | **FIXED Sept 25** | Disable-all + kill all + re-ingest with ISO timestamps |

### Fix: rolling forecast table contamination (retailer_sales_forecast + _adj)

**Root cause:** `appendToExisting=False` in native batch ingest only replaces Druid segments in the NEW data's time range. Old segments outside that range survive untouched across any number of cycles. The tables had stale data from prior runs (Apr–Sep 2026) co-existing with the current Sep 13–Dec 6 cycle.

**What didn't work:** `DELETE /druid/coordinator/v1/datasources/{ds}/intervals/{interval}` returns 404 — the interval-level mark-unused endpoint is not available in this Druid deployment.

**What worked — disable-all + kill + re-ingest (Sept 25 2026):**
```python
# From scripts/druid_cleanup_contamination.py — run this any time a rolling table is contaminated
import requests, time, json
from mo_druid_client import DRUID_HOST, _AUTH, _HEADERS

# Step 1: Mark ALL segments as unused
requests.delete(f"{DRUID_HOST}/druid/coordinator/v1/datasources/retailer_sales_forecast",
                auth=_AUTH, headers=_HEADERS)
time.sleep(2)

# Step 2: Kill all unused segments
requests.post(f"{DRUID_HOST}/druid/indexer/v1/task", auth=_AUTH, headers=_HEADERS,
    json={"type": "kill", "dataSource": "retailer_sales_forecast",
          "interval": "2026-04-01T00:00:00.000Z/2027-01-01T00:00:00.000Z"})
time.sleep(5)

# Step 3: Re-ingest clean data (appendToExisting=False in spec is fine — table is now empty)
spec = json.load(open("outputs/retailer_sales_forecast_ingest_spec.json"))
spec["spec"]["ioConfig"]["appendToExisting"] = False
requests.post(f"{DRUID_HOST}/druid/indexer/v1/task", auth=_AUTH, headers=_HEADERS, json=spec)
```

After fix, both tables verified clean: **Sep 13–Dec 6, 3,173 series/week, 41,249 rows each.**

**Prevent recurrence:** future pipeline runs should switch to MSQ `REPLACE INTO "retailer_sales_forecast" OVERWRITE ALL` instead of native batch. Until then, run the post-cycle audit checklist after every cycle and use `druid_cleanup_contamination.py` if stale segments are found.

### Fix: causal_impact_scores timestamp corruption

**Root cause:** PyArrow serializes `datetime64[ns]` columns as INT64 nanoseconds when not pre-converted to strings. Druid interprets INT64 values as epoch-milliseconds → year ~56,000,000 timestamps. These land in year-56M Druid segments outside any normal date range, so `appendToExisting=False` for the correct 2023–2026 data never touched them.

**Fix (Sept 25 2026):** Disable entire datasource → kill all intervals (including year-56M) → re-ingest from the ISO-timestamp parquet already in S3:
```python
requests.delete(f"{DRUID_HOST}/druid/coordinator/v1/datasources/causal_impact_scores", ...)
# kill interval: "1000-01-01T00:00:00.000Z/9999-12-31T00:00:00.000Z" covers year-56M segments
# Re-ingest: scripts/outputs/causal_impact_scores_ingest_spec.json (ISO timestamps via mo_writeback.py)
```
After fix: 2023-12-17 → 2026-04-19, **500 rows**, all valid years.

**Prevention:** `mo_writeback.py` `upload_parquet()` already serializes timestamp columns as ISO strings before writing to parquet. All scripts using `write_back()` are protected. Scripts that write parquet manually (without `write_back()`) must call `df[ts_col] = pd.to_datetime(df[ts_col], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")` before writing.

### MO_22 note: comparison_pool_prelaunch_baseline

MO_22 **ran Sept 24** and produced 57,231 rows (2023-03-12 → 2026-07-19, `scored_at: 2026-09-24`). The parquet is at `scripts/outputs/comparison_pool_prelaunch_baseline.parquet`.

The Druid table had 106,464 rows from 330 accumulated segments across multiple prior pipeline runs (appendToExisting=True was accumulating duplicates). Fixed Sept 25: disable-all → kill → re-ingest with appendToExisting=False → **57,231 clean rows**.

**Do NOT use appendToExisting=True for this table.** Each cycle produces a full snapshot of all (focal, candidate) pairs scored as of that run date. Use disable-all → kill → re-ingest (same pattern as the forecast tables). This table is standalone — no other pipeline scripts read from it, and no active API currently queries it (Pool Health lookup is a future TODO).

### MO_64 note: retailer_sales_tdp_velocity

MO_64 reads `scripts/outputs/retailer_sales_weekly.parquet` (MO_25 output) and `scripts/outputs/retailer_sales_forecast.parquet` (MO_27 output) — both Sept 24. Re-run is safe:
```bash
cd scripts
python MO_64_tdp_velocity_decomp.py
# Then submit the new spec:
python3 -c "
import json, requests
from mo_druid_client import DRUID_HOST, _AUTH, _HEADERS
spec = json.load(open('outputs/retailer_sales_tdp_velocity_ingest_spec.json'))
r = requests.post(f'{DRUID_HOST}/druid/indexer/v1/task', json=spec, auth=_AUTH, headers=_HEADERS)
print(r.status_code, r.text[:200])
"
```

Note: No API endpoint currently queries `retailer_sales_tdp_velocity` — this feeds future TDP decomposition views. Run when ready to wire it to the UI.

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
