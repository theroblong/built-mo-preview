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
