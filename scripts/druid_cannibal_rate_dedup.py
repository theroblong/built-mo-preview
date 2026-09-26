"""One-time cleanup: deduplicate cannibalization_rate_weekly in Druid.

PROBLEM
-------
MO_19_cannibal_rate_actuals.py uses write_back() which defaults to
appendToExisting=True. Each re-run of MO_19 appends a full copy of all
weekly rows rather than replacing them.

As of 2026-09-26: 2,185,805 total rows / three pipeline run timestamps:
  2026-06-09  (583,262 rows)
  2026-09-14  (788,027 rows)
  2026-09-24  (814,516 rows)  ← latest / correct run to keep

WHAT THIS SCRIPT DOES
---------------------
The Sept 24 parquet is already clean on S3 (written by MO_19).
This script resubmits it to Druid with appendToExisting=False,
which fully replaces the table with the 814,516-row clean set.
No re-download or re-upload required.

FUTURE PREVENTION
-----------------
After every MO_19 run, immediately run druid_ingest_cannibal_rate.py
instead of relying on write_back() to accumulate rows.
"""

import json
import os
import sys
import requests
from dotenv import load_dotenv
load_dotenv()
from mo_druid_client import DRUID_HOST, _AUTH, _HEADERS, poll_task_api, query_druid

SPEC_PATH = "outputs/cannibalization_rate_weekly_ingest_spec.json"

print("=" * 65)
print("  cannibalization_rate_weekly dedup — one-time cleanup")
print("=" * 65)

# ── 1. Show current state ──────────────────────────────────────────────────────
print("\nStep 1: Current row counts per pipeline run in Druid...")
runs = query_druid("""
    SELECT
        scored_at,
        COUNT(*) AS row_count
    FROM "cannibalization_rate_weekly"
    GROUP BY scored_at
    ORDER BY scored_at
""")
total = 0
for _, row in runs.iterrows():
    print(f"  {str(row['scored_at'])[:19]}  {int(row['row_count']):>10,} rows")
    total += int(row['row_count'])
print(f"  {'TOTAL':19}  {total:>10,} rows")
print(f"\n  After dedup: will keep only the Sept 24 run (814,516 rows)")

# ── 2. Load Sept 24 spec and patch appendToExisting=False ─────────────────────
print("\nStep 2: Loading ingest spec and patching appendToExisting=False...")
with open(SPEC_PATH) as f:
    spec = json.load(f)

s3_path = spec["spec"]["ioConfig"]["inputSource"]["uris"][0]
print(f"  S3 source: {s3_path}")

if "2026-09-24" not in s3_path:
    print(f"\n  ERROR: Expected Sept 24 path in spec but found: {s3_path}")
    print("  Aborting — verify SPEC_PATH points to the latest MO_19 run.")
    sys.exit(1)

spec["spec"]["ioConfig"]["appendToExisting"] = False

dedup_spec_path = "outputs/cannibalization_rate_weekly_dedup_spec.json"
with open(dedup_spec_path, "w") as f:
    json.dump(spec, f, indent=2)
print(f"  Dedup spec written: {dedup_spec_path}")

# ── 3. Submit or prompt ───────────────────────────────────────────────────────
AUTO_SUBMIT = "--submit" in sys.argv

if AUTO_SUBMIT:
    print("\nStep 3: Submitting to Druid (appendToExisting=False — full replacement)...")
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
        success = poll_task_api(task_id, label="cannibalization_rate_weekly-dedup")
        if success:
            print("\n  ✓ Dedup complete — cannibalization_rate_weekly now has 814,516 clean rows.")
        else:
            print("\n  ✗ Task failed or timed out — check Druid console.")
else:
    print("\n" + "=" * 65)
    print("  READY TO SUBMIT — review output above, then re-run with --submit")
    print("  Or submit manually:")
    druid_host = os.environ.get("DRUID_HOST", "<DRUID_HOST>")
    print(f"    curl -X POST {druid_host}/druid/indexer/v1/task \\")
    print(f"         -H 'Content-Type: application/json' \\")
    print(f"         -d @{dedup_spec_path}")
    print("=" * 65)
    print("\nRe-run with --submit to execute, or POST the spec manually.")
