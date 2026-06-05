# Mo Druid Error Register

Running log of errors encountered during live Druid query testing, with root cause and remedy for each. Add new entries as testing continues.

---

## E01 — Q0: Column names contain commas that do not exist in spins_full

**Query:** Q0  
**Error:** `INVALID_INPUT: Column 'Units, Yago' not found in any table`  
**Root cause:** The register was written with comma-separated SPINS column names (e.g., `"Units, Yago"`, `"TDP, Any Promo"`, `"Units ,% Lift, TPR"`). The actual column names in `spins_full` use spaces only.  
**Remedy:** Stripped commas from 13 column references in Q0. Full mapping:

| Was | Fixed to |
|-----|----------|
| `"Units, Yago"` | `"Units Yago"` |
| `"Base Units, Yago"` | `"Base Units Yago"` |
| `"TDP, Yago"` | `"TDP Yago"` |
| `"ARP, Yago"` | `"ARP Yago"` |
| `"ARP % Discount, Any Promo"` | `"ARP % Discount Any Promo"` |
| `"Units, Promo"` | `"Units Promo"` |
| `"Units, Non-Promo"` | `"Units Non-Promo"` |
| `"Units, % Promo"` | `"Units % Promo"` |
| `"TDP, Any Promo"` | `"TDP Any Promo"` |
| `"TDP, Non-Promo"` | `"TDP Non-Promo"` |
| `"Units ,% Lift, TPR"` | `"Units % Lift TPR"` |
| `"Units ,% Lift, Any Display"` | `"Units % Lift Any Display"` |
| `"Units ,% Lift, Any Feature"` | `"Units % Lift Any Feature"` |

**Same fix applied to:** Q7, Q8 (two additional occurrences of the wrong subcategory string found in those queries during the same scan).

---

## E02 — Q0: TIME_PARSE on "Time Period End Date" redundant

**Query:** Q0  
**Error:** Not a runtime error — a design improvement surfaced during testing.  
**Root cause:** The original Q0 used `TIME_PARSE("Time Period End Date", 'MM/dd/yyyy') AS __time`. The `spins_full` datasource already has a native `__time` column set to the correct week-end timestamp at ingestion (`2023-01-08T00:00:00.000Z`). Re-parsing a string column is slower and adds format-mismatch risk.  
**Remedy:** Replaced with `__time` directly. Eliminates the `TIME_PARSE` call and the dependency on the `"Time Period End Date"` string column.

---

## E03 — Q0: Task timeout (404) — 62.9M row OVERWRITE ALL exceeds cluster limit

**Query:** Q0  
**Error:** HTTP 404 after ~1.5 hours — Druid task record lost (cluster task duration limit reached).  
**Root cause:** Two compounding issues:
1. The original subcategory filter used `'WELLNESS & NUTRITION BARS'`, which is correct (99.8% of BUILT brand rows are in that subcategory), but the full subcategory contains ~62.9M rows across all brands — too large for a single REPLACE INTO OVERWRITE ALL task on this cluster (~1.5h limit).
2. Initial diagnosis incorrectly identified `GRANOLA & SNACK BARS` as the correct subcategory based on a single sample row. Confirmed via `SELECT Brand, Subcategory, COUNT(*)`: BUILT brand rows split as 912K in WELLNESS & NUTRITION BARS vs 1,788 in GRANOLA & SNACK BARS.

**Remedy:** Keep `'WELLNESS & NUTRITION BARS'` (correct subcategory). Replace `OVERWRITE ALL` with `OVERWRITE WHERE __time >= TIMESTAMP '...' AND __time < TIMESTAMP '...'` and run in annual batches (~20–25M rows per batch). Batch 1: 2023-01-01→2024-01-01; Batch 2: 2024-01-01→2025-01-01; Batch 3: 2025-01-01→present.  
**Note:** Q0 Batch 1 actually succeeded silently — `built_filtered_weekly` had data despite the 404 status. Always check `SELECT COUNT(*) FROM built_filtered_weekly` before re-running.

---

## E04 — QS1/QS2/QS3: Druid Lookup tab returns 403

**Query:** Setup (lookup ingestion)  
**Error:** HTTP 403 Unauthorized on the Druid Lookup tab.  
**Root cause:** Current user role lacks the `EXTERNAL` resource action required to manage Druid Lookups.  
**Remedy:** Abandon Druid Lookups entirely. Create `flavor_mapping`, `flavor_canonical_overrides`, and `item_catalog` as regular Druid datasources via SQL `REPLACE INTO`. Changed `item_catalog` from UPC-keyed to brand-keyed design to keep it maintainable (tier is a brand-level concept). Updated Q2 and Q2b joins from `c.upc = ic.upc` to `c.source_brand = ic.brand`.

---

## E05 — QS1: EXTERN FORBIDDEN

**Query:** QS1 (flavor_mapping seed)  
**Error:** `FORBIDDEN: Unauthorized`  
**Root cause:** The `EXTERN()` function (including `inline` type) requires a separate cluster permission that the current role does not have. EXTERN is restricted to prevent arbitrary external file reads.  
**Remedy:** Avoid EXTERN entirely. Read from `spins_full` (confirmed-accessible datasource) using a `SELECT DISTINCT "UPC"` subquery, then derive all curated values (flavor family, normalized names, pack count, size) via CASE expressions keyed on UPC. No new permissions required.

---

## E06 — QS1: UNION ALL with literal rows not supported

**Query:** QS1 (flavor_mapping seed), attempted as interim fix  
**Error:** `INVALID_INPUT: SQL requires union with input of a datasource type that is not supported. Union operation is only supported between regular tables.`  
**Root cause:** Druid MSQ does not support `UNION ALL` between literal `SELECT 'value' AS col` rows without a `FROM` clause. Only `UNION ALL` between real Druid datasource tables is allowed.  
**Remedy:** Same as E05 — use spins_full as the row source with CASE expressions.

---

## E07 — QS1: EXTERN AS t(col VARCHAR) type-declaration syntax not supported

**Query:** QS1 (flavor_mapping seed), attempted before E05 was encountered  
**Error:** `INVALID_INPUT: Received an unexpected token [VARCHAR] (line [21], column [9]), acceptable options: [")", ","]`  
**Root cause:** The query used the newer two-argument EXTERN syntax with type declarations in the `AS t(col TYPE, ...)` alias: `FROM TABLE(EXTERN(...)) AS t(brand VARCHAR, upc VARCHAR, ...)`. This Druid version requires the older three-argument EXTERN where the schema is the third JSON argument and there is no `AS t()` type list.  
**Status:** Moot — EXTERN is FORBIDDEN regardless of syntax (see E05). Documented for reference if permissions change.  
**Three-argument form (for reference):**
```sql
FROM TABLE(
  EXTERN(
    '{"type":"inline","data":"..."}',
    '{"type":"csv","findColumnsFromHeader":true}',
    '[{"name":"col1","type":"string"},...]'
  )
)
```

---

## E08 — QS1v: ORDER BY non-time column not supported

**Query:** QS1v (validation query)  
**Error:** `INVALID_INPUT: SQL query requires ordering a table by non-time column [[upc]], which is not supported.`  
**Root cause:** Druid does not support top-level `ORDER BY` on non-`__time` columns in scan queries against time-series datasources.  
**Attempted fix:** Changed to `ORDER BY __time, upc` — still failed (see E09).

---

## E09 — QS1v: ORDER BY __time, upc not supported in CTE context

**Query:** QS1v (validation query)  
**Error:** `INVALID_INPUT: SQL query requires ordering a table by non-time column [[__time, upc]], which is not supported.`  
**Root cause:** Inside a CTE, `__time` loses its special primary-time column status and is treated as a regular column. Any multi-column `ORDER BY` (even `ORDER BY __time, other_col`) is rejected. Only bare `ORDER BY __time` is permitted at the top level, and only when `__time` is the direct primary time column of the scanned datasource.  
**Remedy:** Remove `ORDER BY` entirely from QS1v. Mismatch rows are returned in any order — the validation purpose (zero rows = clean) is unaffected by ordering.  
**General rule for this cluster:** Remove `ORDER BY` from all top-level scan queries unless the sort is purely `ORDER BY __time`. Also removed from Q2b and Q2c for the same reason.

---

## E10 — Q2: BroadcastTablesTooLarge on self-join

**Query:** Q2 (comparison_pool_weekly)  
**Error:** `BroadcastTablesTooLarge: Size of broadcast tables in JOIN exceeds reserved memory limit (memory reserved for broadcast tables = [311,387,750] bytes). Increase available memory, or set [sqlJoinAlgorithm: sortMerge] in query context to use a shuffle-based join.`  
**Root cause:** Q2 self-joins `built_enriched_weekly` with itself. Druid's default join algorithm broadcasts the smaller (right) side into each worker's memory. `built_enriched_weekly` exceeds the ~311 MB broadcast limit on this cluster (1 GB max memory, ~29% reserved for broadcast tables, single middlemanager).  
**Remedy:** Add `SET sqlJoinAlgorithm = 'sortMerge';` at the top of the query. Sort-merge join streams and shuffles both sides by the join key instead of broadcasting one side into memory. Also applied proactively to Q4 (`comparison_pool_weekly` × `built_enriched_weekly`) and Q5 (`built_prepost_features` × `donor_prepost_features`) which have the same large-table join pattern.

---

## E11 — Q3/Q4/Q5: TIME_PARSE format mismatch for first_week_selling

**Query:** Q3, Q4, Q5  
**Error:** Not yet encountered at runtime — identified proactively during code review.  
**Root cause:** Q3, Q4, and Q5 call `TIME_PARSE(first_week_selling, 'MM/dd/yyyy')`. However, `first_week_selling` is stored in `spins_full` as ISO format (`2023-01-08`, `yyyy-MM-dd`), not MM/dd/yyyy. The field is passed through Q0 and Q1 without any format conversion.  
**Remedy:** Changed all `TIME_PARSE(first_week_selling, 'MM/dd/yyyy')` to `TIME_PARSE(first_week_selling, 'yyyy-MM-dd')` in Q3, Q4, and Q5 (9 occurrences total across both files).

---

## E12 — All pipeline queries: missing CLUSTERED BY

**Query:** Q0–Q8  
**Error:** Not a runtime error — a structural performance gap.  
**Root cause:** All `REPLACE INTO … PARTITIONED BY DAY` queries were missing `CLUSTERED BY`. Without it, rows within each day's segment are in arbitrary order. Downstream JOINs and GROUP BYs on `upc`, `focal_upc`, `geography_raw`, etc. cannot range-scan — they must full-segment-scan.  
**Remedy:** Added `CLUSTERED BY <join-key columns>` after `PARTITIONED BY DAY` in Q0–Q8. Clustering columns chosen to match the primary join keys used in downstream queries:

| Query | Table | CLUSTERED BY |
|-------|-------|--------------|
| Q0 | `built_filtered_weekly` | `upc, channel_outlet, retail_account, geography_raw` |
| Q1 | `built_enriched_weekly` | `upc, channel_outlet, retail_account, geography_raw` |
| Q2 | `comparison_pool_weekly` | `focal_upc, channel_outlet, retail_account, geography_raw` |
| Q3 | `built_prepost_features` | `upc, channel_outlet, retail_account, geography_raw` |
| Q4 | `donor_prepost_features` | `focal_upc, candidate_upc, channel_outlet, retail_account, geography_raw` |
| Q5 | `ml_training_features` | `focal_upc, donor_upc, channel_outlet, retail_account, geography_raw` |
| Q6 | `event_detection_weekly` | `upc, channel_outlet, retail_account, geography_raw` |
| Q7 | `new_upc_candidates` | `upc` |
| Q8 | `new_upc_classifications` | `upc` |

**Note:** Q9 and Q14–Q22 should follow the same pattern when tested. Apply `CLUSTERED BY upc` (or `focal_upc` for pair-based tables) as a minimum.

---

## E13 — Q2/Q4/Q5: Sort-merge stalls at ~800K rows — local disk saturation

**Query:** Q2 (comparison_pool_weekly); proactively applied to Q4 and Q5  
**Error:** Query stalls near completion after fast initial progress. No error message — task simply stops advancing row count at ~800K rows remaining out of ~62M.  
**Root cause:** Sort-merge join writes large intermediate shuffle files to local disk per partition. On a single middlemanager worker processing 62M rows, those files accumulate and eventually saturate local disk I/O. The task does not fail — it stalls waiting for disk I/O that has nowhere to go.  
**Remedy:** Four SET commands added to Q2, Q4, Q5:

```sql
SET sqlJoinAlgorithm      = 'sortMerge';
SET sqlSortMergeDiskBuffered = 'true';
SET durableShuffleStorage = 'true';    -- also enabled at cluster level
SET maxNumTasks           = 16;        -- effective if cluster has multiple task slots
SET rowsPerSegment        = 5000000;
```

- `durableShuffleStorage = 'true'` — routes shuffle files to S3 instead of local disk. **Primary fix.** Also enabled cluster-wide in Druid runtime config by cluster admin.
- `sqlSortMergeDiskBuffered = 'true'` — spills sort-merge merge buffers to disk rather than holding in memory. Complements durable shuffle by covering the in-memory merge phase.
- `maxNumTasks = 16` — adds parallelism. Safe with durable shuffle on (S3 absorbs the shuffle load, so more workers don't add local disk pressure).
- `rowsPerSegment = 5000000` — increases output segment size from 3M to 5M rows. Minor quality-of-life improvement; does not affect shuffle or stall.

**Note:** With `durableShuffleStorage` now on at cluster level, the shuffle saturation stall is resolved even without the SET command. The SET command is kept for explicitness and documentation.

---

## E14 — Q2: durableShuffleStorage fails — MSQ intermediate storage connector not configured

**Query:** Q2 (comparison_pool_weekly); same applies to Q4 and Q5  
**Error:** `DurableStorageConfiguration: Durable storage mode can only be enabled when druid.msq.intermediate.storage.enable is set to true and the connector is configured correctly. Got error java.lang.Exception: Storage connector not configured.`  
**Root cause:** `SET durableShuffleStorage = 'true'` requires two things at the cluster level, both of which must be in place before the query-level SET takes effect:
1. `druid.msq.intermediate.storage.enable = true` in Druid runtime.properties
2. The MSQ intermediate storage connector fully configured (S3 bucket, path, credentials)

The S3 *extension* modules are loaded (`S3StorageConnectorModule`, `S3StorageDruidModule`) but the MSQ-specific intermediate storage backend path and connector settings were not configured. The cluster admin enabled the feature flag but did not complete the storage connector wiring.

**Remedy:** Remove `SET durableShuffleStorage = 'true'` from Q2, Q4, Q5 for now. Replaced with a comment explaining what needs to be configured before re-enabling. The query runs without it using the remaining settings.

**Silver lining from this attempt:** `maxNumTasks = 16` confirmed working — cluster scaled to **15 workers** (`maxNumWorkers: 15` in tuningConfig). With 15 workers splitting the sort-merge shuffle, each worker handles ~1/15th of the disk load that caused the earlier single-worker stall (E13). This parallelism improvement may be sufficient to complete Q2 without durable shuffle storage at all.

**To enable durableShuffleStorage later (for Rob):** Set `druid.msq.intermediate.storage.enable=true` in runtime.properties and configure the MSQ S3 intermediate storage connector with bucket name, path prefix, and credentials. Then the `SET durableShuffleStorage = 'true'` line can be uncommented in Q2/Q4/Q5.

---

## E15 — Q2: WorkerRpcFailed — worker pod OOM-evicted by Kubernetes

**Query:** Q2 (comparison_pool_weekly)
**Error:** `WorkerRpcFailed: RPC to worker[...-worker0_0] failed: ServiceClosedException: Service [...-worker0_0] is closed`
**Duration:** ~11 minutes (longer than E13's stall, confirming incremental progress with 15 workers)
**Root cause:** Worker0's Kubernetes pod was killed mid-execution — most likely OOM-evicted due to ephemeral storage or memory pressure from sort-merge disk buffers accumulating on the pod's local disk. Kubernetes evicts pods that exceed ephemeral storage or memory limits, closing the worker service and causing the controller's RPC to fail.

Contributing factor identified: `SET sqlJoinAlgorithm = 'sortMerge'` was applying sort-merge to ALL joins in Q2, including the `LEFT JOIN "item_catalog"` which is only 30 rows. Forcing sort-merge on a 30-row table creates an unnecessary shuffle stage and adds extra intermediate data per worker.

**Remedy applied:** Removed `LEFT JOIN "item_catalog" ic ON c.source_brand = ic.brand` from Q2 and Q2b entirely. Replaced `ic.competitor_tier` with an inline `CASE c.source_brand WHEN ... END` expression containing all 30 tier assignments. This eliminates one sort-merge join stage and reduces per-worker intermediate data volume.

**Remaining issue:** The main self-join sort-merge still generates large intermediate shuffle files on worker local disk. Until `durableShuffleStorage` is fully configured (E14), worker pods may still be evicted under heavy ephemeral storage pressure. Rob should complete the MSQ intermediate storage S3 connector configuration to route shuffle files off local disk entirely.

**For Rob — what's needed to complete durable shuffle storage:**
```
druid.msq.intermediate.storage.enable=true
druid.msq.intermediate.storage.type=s3
druid.msq.intermediate.storage.bucket=<your-s3-bucket>
druid.msq.intermediate.storage.prefix=druid/msq/intermediate
```
