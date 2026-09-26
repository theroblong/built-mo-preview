"""Submit cannibalization_rate_weekly ingest spec with appendToExisting=False.

RUN THIS after every MO_19_cannibal_rate_actuals.py execution to replace
the cannibalization_rate_weekly table rather than accumulate duplicate runs.

WHY
---
mo_writeback.write_back() always generates specs with appendToExisting=True.
For cannibalization_rate_weekly that is wrong: MO_19 re-computes ALL focal
UPCs across the full 2-year lookback on each run, so the correct behaviour
is full replacement (appendToExisting=False). Without this step, each MO_19
run accumulates a full duplicate of ~814K rows.

USAGE
-----
    # After MO_19_cannibal_rate_actuals.py finishes and write_back() has run:
    python druid_ingest_cannibal_rate.py

    # Or with auto-poll:
    python druid_ingest_cannibal_rate.py --poll

WORKFLOW
--------
    python MO_19_cannibal_rate_actuals.py       # computes + uploads to MinIO
    python druid_ingest_cannibal_rate.py        # replaces table in Druid

The one-time historical dedup is handled by druid_cannibal_rate_dedup.py.
"""

import json
import sys
from dotenv import load_dotenv
load_dotenv()
from mo_druid_client import DRUID_HOST, _AUTH, _HEADERS, poll_task_api
import requests

SPEC_PATH = "outputs/cannibalization_rate_weekly_ingest_spec.json"

with open(SPEC_PATH) as f:
    spec = json.load(f)

spec["spec"]["ioConfig"]["appendToExisting"] = False

r = requests.post(
    f"{DRUID_HOST}/druid/indexer/v1/task",
    json=spec, auth=_AUTH, headers=_HEADERS,
)
print(f"Druid response: {r.status_code}")
resp_json = r.json()
print(resp_json)

if "--poll" in sys.argv:
    task_id = resp_json.get("task")
    if task_id:
        success = poll_task_api(task_id, label="cannibalization_rate_weekly-replace")
        if success:
            print("\n✓ cannibalization_rate_weekly replaced successfully.")
        else:
            print("\n✗ Task failed or timed out — check Druid console.")
