import os
import time
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

DRUID_HOST     = os.environ["DRUID_HOST"]
DRUID_USERNAME = os.environ["DRUID_USERNAME"]
DRUID_PASSWORD = os.environ["DRUID_PASSWORD"]

_AUTH    = HTTPBasicAuth(DRUID_USERNAME, DRUID_PASSWORD)
_HEADERS = {"Content-Type": "application/json"}

_TERMINAL_FAIL_STATES = {"FAILED", "CANCELED", "CANCELLED"}


def query_druid(sql: str, context: dict | None = None, timeout: int = 120) -> pd.DataFrame:
    """Run a SELECT query and return results as a DataFrame."""
    payload: dict = {"query": sql}
    if context:
        payload["context"] = context
    resp = requests.post(
        f"{DRUID_HOST}/druid/v2/sql/",
        json=payload, auth=_AUTH, headers=_HEADERS, timeout=timeout,
    )
    if not resp.ok:
        raise RuntimeError(f"Druid query failed {resp.status_code}:\n{resp.text}")
    return pd.DataFrame(resp.json())


def submit_msq(sql: str, context: dict | None = None) -> str:
    """Submit an async MSQ ingestion query. Returns the queryId."""
    payload: dict = {"query": sql, "context": {"executionMode": "ASYNC"}}
    if context:
        payload["context"].update(context)
    resp = requests.post(
        f"{DRUID_HOST}/druid/v2/sql/statements",
        json=payload, auth=_AUTH, headers=_HEADERS, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["queryId"]


def poll_msq(query_id: str, interval: int = 15, timeout: int = 7200) -> dict:
    """Poll an async MSQ task until SUCCESS, terminal failure, or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{DRUID_HOST}/druid/v2/sql/statements/{query_id}",
            auth=_AUTH, headers=_HEADERS, timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        state = result.get("state")
        print(f"  MSQ {query_id}: {state}")
        if state == "SUCCESS":
            return result
        if state in _TERMINAL_FAIL_STATES:
            raise RuntimeError(f"MSQ task {query_id} entered state {state}:\n{result}")
        time.sleep(interval)
    raise TimeoutError(f"MSQ task {query_id} did not complete within {timeout}s")


def poll_task_api(task_id: str, label: str = "", interval: int = 30, timeout: int = 50400) -> bool:
    """
    Poll the Druid Tasks API until SUCCESS, FAILED/CANCELED, or timeout.

    Prefer this over poll_msq() for long-running ingestion queries:
    the MSQ statements API (/druid/v2/sql/statements/) expires after a few
    minutes and returns 404 even while the task is still running.  The Tasks
    API (/druid/indexer/v1/task/{id}/status) never expires.

    The task_id returned by submit_msq() is the same ID used here.
    Returns True on SUCCESS, False on failure or timeout.
    """
    url = f"{DRUID_HOST}/druid/indexer/v1/task/{task_id}/status"
    tag = label or task_id
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, auth=_AUTH, headers=_HEADERS, timeout=30)
            if resp.status_code == 404:
                print(f"  [{int(time.time()-start)}s] {tag}: task not yet in overlord, waiting...")
                time.sleep(interval)
                continue
            resp.raise_for_status()
            status_code = resp.json().get("status", {}).get("statusCode", "UNKNOWN")
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] {tag}: {status_code}")
            if status_code == "SUCCESS":
                return True
            if status_code in _TERMINAL_FAIL_STATES:
                return False
        except Exception as e:
            print(f"  poll_task_api error: {e}")
        time.sleep(interval)
    print(f"  poll_task_api TIMEOUT for {tag} after {timeout}s")
    return False


def wait_for_hwm(datasource: str, target_date: str, poll_interval: int = 60, timeout: int = 50400) -> bool:
    """
    Poll MAX(__time) on datasource until it reaches target_date.

    More reliable than task-status polling as a readiness gate: confirms that
    segments are committed to the Druid timeline and queryable, not just that
    the ingestion task finished.  Always use this before starting a step that
    reads from the datasource produced by the previous step.

    target_date: an ISO-8601 date string to match (e.g. '2026-09-06').
    Returns True when HWM ≥ target_date, False on timeout.
    """
    print(f"  Waiting for {datasource} HWM ≥ {target_date} ...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            df = query_druid(f'SELECT MAX(__time) AS max_t FROM "{datasource}"', timeout=60)
            max_t = str(df.iloc[0, 0]) if len(df) > 0 else None
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] {datasource} HWM = {max_t}")
            if max_t and target_date in max_t:
                return True
        except Exception as e:
            print(f"  wait_for_hwm error: {e}")
        time.sleep(poll_interval)
    print(f"  wait_for_hwm TIMEOUT for {datasource} after {timeout}s")
    return False
