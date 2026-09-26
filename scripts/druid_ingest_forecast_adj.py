"""Submit retailer_sales_forecast_adj ingest spec with appendToExisting=False.

RUN THIS after every MO_55_portfolio_constraint.py execution to replace
the adjusted forecast table rather than accumulate duplicate rows.

WORKFLOW
--------
    python druid_ingest_forecast.py --poll         # must complete first
    python MO_55_portfolio_constraint.py           # generates adj forecast + uploads to MinIO
    python druid_ingest_forecast_adj.py --poll     # replaces table in Druid
"""

import json
import sys
from dotenv import load_dotenv
load_dotenv()
from mo_druid_client import DRUID_HOST, _AUTH, _HEADERS, poll_task_api
import requests

SPEC_PATH = "outputs/retailer_sales_forecast_adj_ingest_spec.json"

with open(SPEC_PATH) as f:
    spec = json.load(f)

# appendToExisting=False is intentional: retailer_sales_forecast_adj is a rolling
# 13-week window replaced each cycle. Appending accumulates duplicate rows for
# overlapping forecast weeks.
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
        success = poll_task_api(task_id, label="retailer_sales_forecast_adj-replace")
        if success:
            print("\n✓ retailer_sales_forecast_adj replaced successfully.")
        else:
            print("\n✗ Task failed or timed out — check Druid console.")
