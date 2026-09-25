"""One-time cleanup: deduplicate scored_cannibalization in Druid.

PROBLEM
-------
MO_13_cannibal_score.py uses appendToExisting=True (the default) and sets
scored_at = datetime.now() each run. When MO_13 is re-run (e.g. after a
SPINS update), it appends new rows for the SAME logical pairs rather than
replacing them. Each re-run accumulates a full copy of all scored pairs.

As of 2026-09-25: 227,207 rows / 91,903 unique pairs = 2.47× average bloat.
Three pipeline run timestamps:
  2026-06-09  (initial scoring)
  2026-09-14  (post-SPINS-update re-score)
  2026-09-24  (post-pipeline-cleanup re-score)

WHAT THIS SCRIPT DOES
---------------------
1. Downloads all rows from scored_cannibalization.
2. Deduplicates: keeps the latest-run row per unique
   (focal_upc, donor_upc, comparison_type, retail_account,
    channel_outlet, geography_raw, geography_level, window_type).
3. Uploads deduplicated data to MinIO.
4. Generates a Druid native batch ingest spec with appendToExisting=False
   (full replacement — safe because MO_13 scores ALL retailers each run).
5. Prints the spec path and a curl command.  Jason reviews and submits.

FUTURE PREVENTION
-----------------
After any MO_13 run, submit the generated spec via druid_ingest_cannibal_score.py
(appendToExisting=False) instead of letting write_back() accumulate rows.
The API-level dedup guard in cannibalization.py remains as a safety net.
"""

import json
import os
import sys
import pandas as pd
import requests
from dotenv import load_dotenv
load_dotenv()
from mo_druid_client import query_druid, DRUID_HOST, _AUTH, _HEADERS, poll_task_api
from mo_writeback import write_back

KEY_COLS = [
    "focal_upc", "donor_upc", "comparison_type",
    "retail_account", "channel_outlet", "geography_raw",
    "geography_level", "window_type",
]

print("=" * 65)
print("  scored_cannibalization dedup — one-time cleanup")
print("=" * 65)

# ── 1. Download all rows ──────────────────────────────────────────────────────
print("\nStep 1: Downloading all scored_cannibalization rows from Druid...")
print("  (this may take 30–60s for ~227K rows)")

df = query_druid("""
SELECT __time, focal_upc, focal_description, donor_upc, donor_description,
       channel_outlet, retail_account, geography_raw, geography_level,
       window_type, comparison_type, pack_distance, relationship_distance,
       cannibal_prob, cannibal_status, cannibal_confidence,
       shap_feature_1, shap_value_1,
       shap_feature_2, shap_value_2,
       shap_feature_3, shap_value_3,
       model_version
FROM scored_cannibalization
""", timeout=300)

print(f"  Downloaded: {len(df):,} rows")

# ── 2. Deduplicate ────────────────────────────────────────────────────────────
print("\nStep 2: Deduplicating — keeping latest run per unique pair...")
df["__time"] = pd.to_datetime(df["__time"])

# For each unique pair, keep the row with the most recent __time
df = df.sort_values("__time")
df_dedup = df.drop_duplicates(subset=KEY_COLS, keep="last").reset_index(drop=True)

n_before = len(df)
n_after  = len(df_dedup)
print(f"  Before: {n_before:,} rows | After: {n_after:,} rows | Removed: {n_before - n_after:,} duplicates")
print(f"  Unique run timestamps retained:")
for t in sorted(df_dedup["__time"].unique()):
    cnt = (df_dedup["__time"] == t).sum()
    print(f"    {str(t)[:19]}: {cnt:,} pairs")

# Rename __time → scored_at so write_back() can use it as the Druid timestamp
df_dedup = df_dedup.rename(columns={"__time": "scored_at"})

# ── 3. Upload to MinIO and generate ingest spec ───────────────────────────────
print("\nStep 3: Uploading to MinIO and generating ingest spec...")
spec_path = write_back(df_dedup, "scored_cannibalization", timestamp_col="scored_at")

# ── 4. Patch spec → appendToExisting=False ───────────────────────────────────
print("Step 4: Patching spec to appendToExisting=False (full replacement)...")
with open(spec_path) as f:
    spec = json.load(f)
spec["spec"]["ioConfig"]["appendToExisting"] = False
with open(spec_path, "w") as f:
    json.dump(spec, f, indent=2)
print(f"  Spec updated: {spec_path}")

# ── 5. Submit or prompt ───────────────────────────────────────────────────────
AUTO_SUBMIT = "--submit" in sys.argv

if AUTO_SUBMIT:
    print("\nStep 5: Submitting ingest spec to Druid (appendToExisting=False)...")
    r = requests.post(
        f"{DRUID_HOST}/druid/indexer/v1/task",
        json=spec, auth=_AUTH, headers=_HEADERS,
    )
    print(f"  Druid response: {r.status_code}")
    resp_json = r.json()
    print(f"  {resp_json}")
    task_id = resp_json.get("task")
    if task_id:
        print(f"\n  Polling task {task_id} ...")
        success = poll_task_api(task_id, label="scored_cannibalization-dedup")
        if success:
            print("\n  ✓ Dedup complete — scored_cannibalization now has clean unique pairs.")
        else:
            print("\n  ✗ Task failed or timed out — check Druid console.")
else:
    print("\n" + "=" * 65)
    print("  READY TO SUBMIT — review spec first, then re-run with --submit")
    print("  Or submit manually:")
    druid_host = os.environ.get("DRUID_HOST", "<DRUID_HOST>")
    print(f"    curl -X POST {druid_host}/druid/indexer/v1/task \\")
    print(f"         -H 'Content-Type: application/json' \\")
    print(f"         -d @{spec_path}")
    print("=" * 65)
    print(f"\n  Row reduction: {n_before:,} → {n_after:,} ({round(100*(n_before-n_after)/n_before,1)}% removed)")
    print(f"\nSpec is at: {spec_path}")
    print("Re-run with --submit to execute automatically, or POST the spec manually.")
