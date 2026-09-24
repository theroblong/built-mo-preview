import json
from mo_druid_client import DRUID_HOST, _AUTH, _HEADERS
import requests

spec = json.load(open("outputs/retailer_sales_forecast_ingest_spec.json"))
spec["spec"]["ioConfig"]["appendToExisting"] = False
r = requests.post(
    f"{DRUID_HOST}/druid/indexer/v1/task",
    json=spec,
    auth=_AUTH,
    headers=_HEADERS,
)
print(r.status_code, r.text[:300])
