"""Submit cannibalization_rate_forecast_weekly ingest spec with appendToExisting=False.

RUN THIS after every MO_21_cannibal_rate_forecast.py execution to replace
the forecast table rather than accumulate duplicate runs.

WORKFLOW
--------
    python MO_20_cannibal_rate_train.py          # retrain model
    python MO_21_cannibal_rate_forecast.py       # forecast + uploads to MinIO
    python druid_ingest_cannibal_rate_forecast.py   # replaces table in Druid

    # Or with auto-poll:
    python druid_ingest_cannibal_rate_forecast.py --poll
"""

import json
import sys
from dotenv import load_dotenv
load_dotenv()
from mo_druid_client import DRUID_HOST, _AUTH, _HEADERS, poll_task_api
import requests

SPEC_PATH = "outputs/cannibalization_rate_forecast_weekly_ingest_spec.json"

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
        success = poll_task_api(task_id, label="cannibalization_rate_forecast-replace")
        if success:
            print("\n✓ cannibalization_rate_forecast_weekly replaced successfully.")
        else:
            print("\n✗ Task failed or timed out — check Druid console.")
