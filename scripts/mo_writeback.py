"""Shared MinIO upload and Druid native batch ingestion spec utilities.

All write-back is APPEND ONLY (appendToExisting=true). Nothing is overwritten
automatically. Every call to write_back() generates a spec file in outputs/
and prints a human-review prompt — a human must submit the spec to Druid.

Required env vars (in addition to mo_druid_client vars):
  MINIO_ENDPOINT    host:port with no scheme, e.g. minio.built.internal:9000
  MINIO_ACCESS_KEY
  MINIO_SECRET_KEY
  MINIO_BUCKET      e.g. mo-ml

SCHEMA SAFETY
-------------
SCHEMA_REGISTRY maps each Druid datasource → columns the API SELECTs from it.
write_back() validates the output DataFrame against this registry before uploading.
If required columns are missing the script raises immediately — nothing is uploaded,
nothing is ingested, and Druid is never poisoned with a schema change.

When appendToExisting=false is used for a full segment replacement, Druid permanently
drops any column not present in the new parquet. API queries for dropped columns return
HTTP 400, which the API catches as an empty list — causing silent total UI failure
(e.g., all forecast lines disappear). The registry prevents this at source.

Update SCHEMA_REGISTRY whenever:
  - A new column is added to a pipeline script's output
  - A column is removed from a pipeline script's output
  - The API SELECT for a datasource changes
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()

os.makedirs("outputs", exist_ok=True)

# ---------------------------------------------------------------------------
# Schema registry — columns the API SELECTs from each Druid datasource.
# write_back() checks the output DataFrame against this before any upload.
# ---------------------------------------------------------------------------
SCHEMA_REGISTRY: dict[str, list[str]] = {
    "retailer_sales_forecast": [
        # retailer.py _q_forecast() SELECT — update if either side changes
        "upc", "description", "retail_account", "channel_outlet",
        "geography_raw", "geography_display",
        "anchor_date", "anchor_base_units", "anchor_arp", "arp_fallback",
        "forecast_week_number",
        "forecast_units_low", "forecast_units_base", "forecast_units_high",
        "forecast_dollars_low", "forecast_dollars_base", "forecast_dollars_high",
        "forecast_total_units_low", "forecast_total_units_base", "forecast_total_units_high",
    ],
    "retailer_sales_tdp_velocity": [
        # retailer.py (future /sku-tdp-velocity endpoint) — MO_64 output
        "upc", "description", "retail_account", "channel_outlet",
        "geography_raw", "geography_display", "geography_level",
        "hist_delta_units", "hist_tdp_contrib", "hist_vel_contrib",
        "hist_tdp_contrib_pct", "hist_vel_contrib_pct",
        "fwd_delta_units", "fwd_tdp_contrib", "fwd_vel_contrib",
        "fwd_tdp_contrib_pct", "fwd_vel_contrib_pct",
        "growth_driver", "growth_driver_detail",
        "hist_tdp_last13w_avg", "hist_vel_last13w_avg",
        "anchor_units", "forecast_units_base",
    ],
}


def _validate_schema(df: pd.DataFrame, datasource: str) -> None:
    """Raise if df is missing columns required by the API for this datasource."""
    required = SCHEMA_REGISTRY.get(datasource)
    if required is None:
        return  # no registry entry → no check (new datasource, opt-in)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"\nSCHEMA GUARD — '{datasource}' output is missing required columns:\n"
            f"  {missing}\n"
            f"The API SELECTs these columns from Druid. If this column was intentionally\n"
            f"removed from the pipeline output, also remove it from the API SELECT and\n"
            f"update SCHEMA_REGISTRY in mo_writeback.py before re-running.\n"
            f"Nothing was uploaded. Druid schema is unchanged."
        )


MINIO_ENDPOINT   = os.environ["MINIO_ENDPOINT"]
MINIO_ACCESS_KEY = os.environ["MINIO_ACCESS_KEY"]
MINIO_SECRET_KEY = os.environ["MINIO_SECRET_KEY"]
MINIO_BUCKET     = os.environ["MINIO_BUCKET"]
DRUID_HOST       = os.environ["DRUID_HOST"]


def _endpoint_url() -> str:
    if MINIO_ENDPOINT.startswith(("http://", "https://")):
        return MINIO_ENDPOINT
    return f"http://{MINIO_ENDPOINT}"


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=_endpoint_url(),
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def upload_parquet(df: pd.DataFrame, minio_key: str, timestamp_col: str | None = None) -> str:
    """Write df to parquet locally, upload to MinIO, return s3:// URI."""
    local_path = f"outputs/{Path(minio_key).name}"
    df = df.copy()
    # Serialize timestamp column as ISO string so Druid "format":"iso" always works.
    # PyArrow otherwise writes datetime64[ns] as INT64 nanoseconds, which Druid can
    # misinterpret as epoch-milliseconds and produce year-56-million timestamps.
    if timestamp_col and timestamp_col in df.columns:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col], utc=True).dt.strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
    df.to_parquet(local_path, engine="pyarrow", index=False)
    print(f"  Wrote {len(df):,} rows → {local_path}")
    _s3_client().upload_file(local_path, MINIO_BUCKET, minio_key)
    uri = f"s3://{MINIO_BUCKET}/{minio_key}"
    print(f"  Uploaded → {uri}")
    return uri


def build_ingest_spec(
    datasource: str,
    minio_uri: str,
    timestamp_col: str,
    columns: list[str],
) -> dict:
    """Build a Druid native batch ingestion spec (append-only, parquet from MinIO)."""
    dimensions = [c for c in columns if c != timestamp_col]
    return {
        "type": "index_parallel",
        "spec": {
            "dataSchema": {
                "dataSource": datasource,
                "timestampSpec": {"column": timestamp_col, "format": "iso"},
                "dimensionsSpec": {"dimensions": dimensions},
                "granularitySpec": {
                    "type": "uniform",
                    "segmentGranularity": "DAY",
                    "rollup": False,
                },
            },
            "ioConfig": {
                "type": "index_parallel",
                "inputSource": {
                    "type": "s3",
                    "uris": [minio_uri],
                    "properties": {
                        "accessKeyId": MINIO_ACCESS_KEY,
                        "secretAccessKey": MINIO_SECRET_KEY,
                    },
                    "endpointConfig": {
                        "url": _endpoint_url(),
                        "signingRegion": "us-east-1",
                        "enablePathStyleAccess": True,
                    },
                },
                "inputFormat": {"type": "parquet"},
                "appendToExisting": True,
            },
            "tuningConfig": {
                "type": "index_parallel",
                "partitionsSpec": {"type": "dynamic"},
            },
        },
    }


def write_back(
    df: pd.DataFrame,
    datasource: str,
    timestamp_col: str = "scored_at",
    minio_key: str | None = None,
) -> str:
    """
    Upload df to MinIO as parquet, generate Druid ingestion spec, prompt for review.

    Returns path to the saved spec file.
    Human must review the spec and POST it to /druid/indexer/v1/task.
    """
    if minio_key is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        minio_key = f"{datasource}/{date_str}/{datasource}.parquet"

    print(f"\nWrite-back: {datasource}")
    _validate_schema(df, datasource)  # raises before upload if API columns are missing
    uri = upload_parquet(df, minio_key, timestamp_col=timestamp_col)
    spec = build_ingest_spec(datasource, uri, timestamp_col, list(df.columns))

    spec_path = f"outputs/{datasource}_ingest_spec.json"
    with open(spec_path, "w") as f:
        json.dump(spec, f, indent=2)

    print(f"\n{'=' * 62}")
    print(f"  HUMAN REVIEW REQUIRED — do not auto-submit")
    print(f"  Datasource : {datasource}")
    print(f"  Rows       : {len(df):,}")
    print(f"  Mode       : APPEND ONLY (appendToExisting=true)")
    print(f"  Parquet    : s3://{MINIO_BUCKET}/{minio_key}")
    print(f"  Spec       : {spec_path}")
    print(f"  Submit to  : POST {DRUID_HOST}/druid/indexer/v1/task")
    print(f"{'=' * 62}\n")
    return spec_path
