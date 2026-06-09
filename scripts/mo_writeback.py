"""Shared MinIO upload and Druid native batch ingestion spec utilities.

All write-back is APPEND ONLY (appendToExisting=true). Nothing is overwritten
automatically. Every call to write_back() generates a spec file in outputs/
and prints a human-review prompt — a human must submit the spec to Druid.

Required env vars (in addition to mo_druid_client vars):
  MINIO_ENDPOINT    host:port with no scheme, e.g. minio.built.internal:9000
  MINIO_ACCESS_KEY
  MINIO_SECRET_KEY
  MINIO_BUCKET      e.g. mo-ml
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


def upload_parquet(df: pd.DataFrame, minio_key: str) -> str:
    """Write df to parquet locally, upload to MinIO, return s3:// URI."""
    local_path = f"outputs/{Path(minio_key).name}"
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
    uri = upload_parquet(df, minio_key)
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
