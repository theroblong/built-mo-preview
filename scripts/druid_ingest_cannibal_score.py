"""Submit scored_cannibalization ingest spec with appendToExisting=False.

RUN THIS after every MO_13_cannibal_score.py execution to replace the
scored_cannibalization table rather than accumulate duplicate runs.

WHY
---
mo_writeback.write_back() always generates specs with appendToExisting=True
(to avoid accidental column drops in other tables). For scored_cannibalization
that is wrong: MO_13 re-scores ALL retailer-flavor pairs on each run, so the
correct behaviour is full replacement (appendToExisting=False). Without this
step, each MO_13 run accumulates a full duplicate of ~92K rows.

USAGE
-----
    # After MO_13_cannibal_score.py finishes and write_back() has run:
    python druid_ingest_cannibal_score.py

    # Or with auto-poll:
    python druid_ingest_cannibal_score.py --poll

WORKFLOW
--------
    python MO_13_cannibal_score.py       # scores + uploads to MinIO
    python druid_ingest_cannibal_score.py   # replaces scored_cannibalization in Druid

The one-time historical dedup is handled by druid_cannibal_dedup.py.
"""

import json
import sys
from dotenv import load_dotenv
load_dotenv()
from mo_druid_client import DRUID_HOST, _AUTH, _HEADERS, poll_task_api
import requests

SPEC_PATH = "outputs/scored_cannibalization_ingest_spec.json"

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
        success = poll_task_api(task_id, label="scored_cannibalization-replace")
        if success:
            print("\n✓ scored_cannibalization replaced successfully.")
        else:
            print("\n✗ Task failed or timed out — check Druid console.")
