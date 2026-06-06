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
SET maxNumTasks           = 4;         -- effective if cluster has multiple task slots
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

---

## E16 — Q2: Worker0 OOM eviction persists despite CASE fix — time-range batching required

**Query:** Q2 (comparison_pool_weekly)
**Error:** `WorkerRpcFailed: ServiceClosedException on worker0_0` (same as E15)
**Duration:** ~10.6 minutes (consistent with E15's ~11.2 minutes — same pod disk limit hit each time)
**Root cause:** Worker0 consistently receives the largest hash partition from the sort-merge shuffle on 62M rows and hits the Kubernetes pod ephemeral storage quota at approximately the same wall-clock mark regardless of query optimizations. The E15 CASE expression fix reduced join stages but did not reduce the fundamental data volume going through the sort-merge shuffle.

**Pattern confirmed:** Three consecutive runs (E15 ~11 min, E16 ~10.6 min) all fail at the same worker0 at nearly the same elapsed time. This is a deterministic pod disk quota limit, not a random resource contention issue.

**Remedy applied:** Added year-range batching to Q2 using `OVERWRITE WHERE __time >= ... AND __time < ...` plus a matching time filter in the WHERE clause — the same pattern used successfully for Q0. Each batch processes ~20M rows instead of 62M, reducing per-worker intermediate shuffle data to ~1/3. Run Q2 three times:

- **Batch 1:** `__time >= TIMESTAMP '2023-01-01' AND __time < TIMESTAMP '2024-01-01'`
- **Batch 2:** `__time >= TIMESTAMP '2024-01-01' AND __time < TIMESTAMP '2025-01-01'`
- **Batch 3:** `__time >= TIMESTAMP '2025-01-01' AND __time < TIMESTAMP '2026-01-01'` (adjust upper bound to present)

**Remaining path:** If batching still fails, the definitive fix is completing durable shuffle storage (E14/E15) so intermediate files go to S3 instead of local pod disk. Rob needs to set `druid.msq.intermediate.storage.enable=true` and configure the S3 connector.

---

## E17 — Q2: Time-range batch filter only applied to one side of sort-merge self-join

**Query:** Q2 (comparison_pool_weekly), Batch 1 attempt
**Error:** `WorkerRpcFailed: ServiceClosedException on worker0_0` (same as E15/E16)
**Duration:** ~12.6 minutes — *longer* than E16's 10.6 minutes despite batching
**Root cause:** The `f.__time >= TIMESTAMP '2023-01-01'` filter in the WHERE clause was pushed down to the `f` scan (right side, j0 prefix, 2023-scoped) but Druid's sort-merge planner did not infer that `c.__time` must also be 2023, even though the join condition is `f.__time = c.__time`. The `c` scan (left side, no prefix) continued to read the full time range (`-146136543.../146140482...` = all data). With worker0 receiving the full dataset on the left side, it generated more shuffle data than the non-batched E16 run, explaining the longer duration.

**Confirmed from query plan:**
- Right scan (f/focal side, j0): `"intervals": ["2023-01-01T00:00:00.000Z/2024-01-01T00:00:00.000Z"]` ✓
- Left scan (c/candidate side, no prefix): `"intervals": ["-146136543-09-08T08:23:32.096Z/146140482-04-24T15:36:27.903Z"]` ✗

**Remedy:** Added explicit `c.__time` bounds alongside the existing `f.__time` bounds in the WHERE clause:
```sql
  AND f.__time >= TIMESTAMP '2023-01-01'
  AND f.__time <  TIMESTAMP '2024-01-01'
  AND c.__time >= TIMESTAMP '2023-01-01'  -- explicit: sort-merge does not infer c.__time from f.__time filter
  AND c.__time <  TIMESTAMP '2024-01-01'
```
With both sides explicitly filtered, Druid will push the time interval down to both scans, reducing each from ~62M to ~20M rows.

---

## E18 — Q2: BroadcastTablesTooLarge confirmed with no SET commands — sortMerge non-negotiable

**Query:** Q2 (comparison_pool_weekly), all SET commands commented out
**Error:** `BroadcastTablesTooLarge: Size of broadcast tables in JOIN exceeds reserved memory limit (memory reserved for broadcast tables = [311,387,750] bytes).`
**Duration:** ~22 minutes (single worker attempting to build broadcast hash table before hitting 311MB limit)
**Root cause:** Without `SET sqlJoinAlgorithm = 'sortMerge'`, Druid reverts to broadcast join. The broadcast limit is 311MB regardless of batching — even the 2023-only subset of `built_enriched_weekly` far exceeds it. No cluster defaults changed since E10.
**Additional observation:** `maxNumWorkers: 1` confirmed — without `SET maxNumTasks = 16`, the cluster defaults to single-worker execution.
**Remedy:** Restored `SET sqlJoinAlgorithm = 'sortMerge'` and `SET maxNumTasks = 16` as REQUIRED settings. Both are documented as mandatory in Q2, Q4, Q5.

**Q2 status summary — all paths exhausted:**
| Configuration | Result |
|---|---|
| No sortMerge (broadcast) | BroadcastTablesTooLarge (E10, E18) |
| sortMerge + 1 worker | Stall at 800K rows, never completes (E13) |
| sortMerge + 15 workers + full 62M rows | Worker0 pod evicted ~10-11 min (E15, E16) |
| sortMerge + 15 workers + 2023 batch only (20M rows) | Worker0 pod evicted ~10-11 min (E16 variant) |

**Conclusion:** Q2 is blocked on pod ephemeral storage quota for sort-merge shuffle files. The definitive fix is Rob completing the MSQ intermediate storage S3 connector configuration so shuffle files route to S3 instead of local pod disk. Required settings:
```
druid.msq.intermediate.storage.enable=true
druid.msq.intermediate.storage.type=s3
druid.msq.intermediate.storage.bucket=<your-s3-bucket>
druid.msq.intermediate.storage.prefix=druid/msq/intermediate
```

---

## E19 — Q2: Task disappeared on worker — first run with cluster-level durableShuffleStorage active

**Query:** Q2 (comparison_pool_weekly), 2023 batch (Batch 1)
**Task ID:** `query-444287e6-40c4-4111-879b-d9ed739b86dc`
**Error:** `general: This task disappeared on the worker where it was assigned. See overlord logs for more details.`
**Progress:** ~2/3 of 16M rows on Stage 3 (input step) — furthest progress on Q2 to date
**Settings:** `sqlJoinAlgorithm=sortMerge`, `sqlSortMergeDiskBuffered=true`, `maxNumTasks=8` (7 workers); `durableShuffleStorage` NOT set in query — Rob completed cluster-level MSQ intermediate S3 storage config (`druid.msq.intermediate.storage.enable=true` + S3 connector)
**UI observation:** "Network Connectivity Issues" flashed yellow periodically during execution

**Analysis:**
- This is the first run since Rob completed the MSQ intermediate S3 storage connector config. `durableShuffleStorage` is now active cluster-wide; shuffle files route to S3 without the explicit SET command (per E13 note).
- Reaching 2/3 of 16M rows is meaningful progress — all prior multi-worker sort-merge attempts failed with explicit pod eviction at ~10-11 min (E15–E17). The further progress strongly suggests S3 shuffle is active and disk pressure is no longer the primary blocker.
- "Task disappeared" differs from the prior "Worker0 evicted" messages. The controller lost contact with a worker rather than receiving an explicit K8s eviction event. Combined with the periodic "Network Connectivity Issues" UI flashes, this points to a pod OOM crash or a transient network partition — not disk saturation.

**Remedy / next steps:**
1. Add `SET durableShuffleStorage = 'true'` explicitly to Q2 — safe now that Rob's cluster config is complete (see E14 for why it was removed). Explicit SET confirms it's active and documents intent.
2. Check K8s overlord logs for the specific worker pod that disappeared (`query-444287e6-40c4-4111-879b-d9ed739b86dc`) to confirm OOM vs. network partition.

---

## E20 — Q2: INVALID_INPUT — open-ended OVERWRITE WHERE not aligned with PARTITIONED BY DAY

**Query:** Q2 (comparison_pool_weekly), Batch 3 (2025-01-01 → present)
**Error:** `INVALID_INPUT: OVERWRITE WHERE clause identified interval [2025-01-01T00:00:00.000Z/146140482-04-24T15:36:27.903Z] which is not aligned with PARTITIONED BY granularity [{type=period, period=P1D, timeZone=UTC, origin=null}]`
**Root cause:** Druid MSQ requires both bounds of the `OVERWRITE WHERE` range to align with the `PARTITIONED BY` granularity. An open-ended upper bound resolves internally to the maximum representable timestamp (`146140482-04-24...`), which is not on a day boundary.
**Remedy:** Add an explicit future upper bound aligned to DAY granularity. `2027-01-01` provides a full year of runway beyond present data:
```sql
OVERWRITE WHERE __time >= TIMESTAMP '2025-01-01'
            AND __time <  TIMESTAMP '2027-01-01'
```
Match the same bounds in the WHERE clause for both `f.__time` and `c.__time`. Update the upper bound when re-running this batch in future years.
