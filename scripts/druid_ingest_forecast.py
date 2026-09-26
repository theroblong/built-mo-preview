"""Submit retailer_sales_forecast ingest spec with appendToExisting=False.

RUN THIS after every MO_27_retailer_sales_forecast.py execution to replace
the forecast table rather than accumulate duplicate rows for overlapping
forecast weeks.

WORKFLOW
--------
    python MO_27_retailer_sales_forecast.py        # generates forecast + uploads to MinIO
    python druid_ingest_forecast.py --poll         # replaces table in Druid
    python MO_55_portfolio_constraint.py           # reads from Druid — wait for ingest first
    python druid_ingest_forecast_adj.py --poll     # replaces adj table in Druid
"""

import json
import sys
from dotenv import load_dotenv
load_dotenv()
from mo_druid_client import DRUID_HOST, _AUTH, _HEADERS, poll_task_api
import requests

SPEC_PATH = "outputs/retailer_sales_forecast_ingest_spec.json"

with open(SPEC_PATH) as f:
    spec = json.load(f)

# appendToExisting=False is intentional: retailer_sales_forecast is a rolling
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
        success = poll_task_api(task_id, label="retailer_sales_forecast-replace")
        if success:
            print("\n✓ retailer_sales_forecast replaced successfully.")
        else:
            print("\n✗ Task failed or timed out — check Druid console.")
