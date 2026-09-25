"""
One-shot cleanup for three contaminated datasources discovered in the Sept 25 audit.

Run from scripts/ directory:
    python druid_cleanup_contamination.py

What it does (mark-unused then kill for each):
  1. retailer_sales_forecast    - removes Apr 26–Sep 12 stale data; keeps Sep 13–Dec 6
  2. retailer_sales_forecast_adj - removes Apr 26–Sep 12 stale data; keeps Sep 13–Dec 6
  3. causal_impact_scores       - disables entire datasource, kills all segments (incl.
                                   year-56M bad-timestamp data), then re-ingests from
                                   the clean ISO-timestamp spec already in S3

After this script: verify with druid_post_cycle_audit.py
"""
import json, time
from dotenv import load_dotenv; load_dotenv('../.env')
from mo_druid_client import DRUID_HOST, _AUTH, _HEADERS
import requests

def coordinator_delete_interval(datasource, interval):
    """Mark segments in interval as unused via coordinator API."""
    url = f"{DRUID_HOST}/druid/coordinator/v1/datasources/{datasource}/intervals/{interval}"
    r = requests.delete(url, auth=_AUTH, headers=_HEADERS, timeout=30)
    print(f"  coordinator DELETE ({interval}): {r.status_code} {r.text[:120]}")
    return r.status_code in (200, 204)

def coordinator_disable_datasource(datasource):
    """Mark ALL segments in datasource as unused."""
    url = f"{DRUID_HOST}/druid/coordinator/v1/datasources/{datasource}"
    r = requests.delete(url, auth=_AUTH, headers=_HEADERS, timeout=30)
    print(f"  coordinator DISABLE datasource: {r.status_code} {r.text[:120]}")
    return r.status_code in (200, 204)

def submit_kill(datasource, interval):
    """Submit a kill task to physically remove unused segments."""
    r = requests.post(
        f"{DRUID_HOST}/druid/indexer/v1/task",
        auth=_AUTH, headers=_HEADERS, timeout=30,
        json={"type": "kill", "dataSource": datasource, "interval": interval}
    )
    print(f"  kill task submitted: {r.status_code} {r.text[:200]}")
    return r.status_code == 200

def submit_ingest(spec_path):
    """Re-submit an ingest spec (for causal_impact_scores re-ingest)."""
    spec = json.load(open(spec_path))
    spec["spec"]["ioConfig"]["appendToExisting"] = False
    r = requests.post(
        f"{DRUID_HOST}/druid/indexer/v1/task",
        auth=_AUTH, headers=_HEADERS, timeout=30,
        json=spec
    )
    print(f"  ingest task submitted: {r.status_code} {r.text[:200]}")
    return r.status_code == 200


# ── 1. retailer_sales_forecast ──────────────────────────────────────────────
print("\n[1/3] retailer_sales_forecast — removing Apr 26–Sep 12 contamination")
STALE_INTERVAL = "2026-04-01T00:00:00.000Z/2026-09-13T00:00:00.000Z"
coordinator_delete_interval("retailer_sales_forecast", STALE_INTERVAL)
time.sleep(2)
submit_kill("retailer_sales_forecast", STALE_INTERVAL)


# ── 2. retailer_sales_forecast_adj ──────────────────────────────────────────
print("\n[2/3] retailer_sales_forecast_adj — removing Apr 26–Sep 12 contamination")
coordinator_delete_interval("retailer_sales_forecast_adj", STALE_INTERVAL)
time.sleep(2)
submit_kill("retailer_sales_forecast_adj", STALE_INTERVAL)


# ── 3. causal_impact_scores — full reset + clean re-ingest ──────────────────
# The previous ingest used PyArrow INT64 nanoseconds, which Druid stored as
# year-56M timestamps. Those segments are in a completely different time range
# than the new ISO-correct data, so appendToExisting=False didn't remove them.
# Fix: disable entire datasource → kill all intervals → re-ingest clean spec.
print("\n[3/3] causal_impact_scores — full reset (year-56M bad segments + re-ingest)")
coordinator_disable_datasource("causal_impact_scores")
time.sleep(3)
# Kill the full valid date range (covers both the correct 2023-2026 range AND
# the year-56M segments — Druid normalizes far-future kill intervals internally)
FULL_RANGE = "1000-01-01T00:00:00.000Z/9999-12-31T00:00:00.000Z"
submit_kill("causal_impact_scores", FULL_RANGE)
# Wait briefly before re-ingesting
time.sleep(5)
print("  waiting 8s for kill task to register before re-ingest...")
time.sleep(8)
submit_ingest("outputs/causal_impact_scores_ingest_spec.json")

print("\nDone. Allow 1–2 min for tasks to complete, then run druid_post_cycle_audit.py to verify.")
