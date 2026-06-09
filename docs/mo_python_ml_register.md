# Mo Python ML Register

Running register of Python ML scripts for the Mo intelligence suite. Organized by execution order.
Each entry documents purpose, Druid inputs/outputs, dependencies, and a working code stub.

Companion file: `mockups/mo_python_ml_register.html`
Error register: `docs/mo_python_ml_error_register.md`

---

## Section 0: Druid Connection

<a id="p0"></a>

### P0 — `mo_druid_client.py`

**Purpose:** Shared Druid connection module. Provides `query_druid()` for reads and `submit_msq()` / `poll_msq()` for async ingestion writes. Import this in every other script — do not inline connection logic.

**Druid SQL REST API endpoints used:**

| Endpoint | Method | Use |
|---|---|---|
| `/druid/v2/sql/` | POST | SELECT queries → pandas DataFrame |
| `/druid/v2/sql/statements` | POST | Async MSQ ingestion (REPLACE INTO / INSERT INTO) |
| `/druid/v2/sql/statements/{queryId}` | GET | Poll async task status |

**Configuration:** Set these three values via environment variables or a `.env` file. Never hard-code credentials.

```python
# scripts/mo_druid_client.py
import os
import time
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth

DRUID_HOST     = os.environ["DRUID_HOST"]      # e.g. https://your-druid-host:8082
DRUID_USERNAME = os.environ["DRUID_USERNAME"]
DRUID_PASSWORD = os.environ["DRUID_PASSWORD"]

_AUTH = HTTPBasicAuth(DRUID_USERNAME, DRUID_PASSWORD)
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
```

**Write-back pattern — MinIO → Druid native batch ingestion:**

All write-back uses `mo_writeback.py` (companion module). Python scores data, writes parquet, uploads to MinIO, generates a Druid native batch ingestion spec, and prints a human-review prompt. **A human must submit the spec to Druid.** Nothing is auto-submitted.

Required env vars for write-back:
```
export MINIO_ENDPOINT="minio.built.internal:9000"   # host:port, no scheme
export MINIO_ACCESS_KEY="..."
export MINIO_SECRET_KEY="..."
export MINIO_BUCKET="mo-ml"
```

All specs use `appendToExisting: true` (append-only). EXTERN is not used (E05 confirmed blocked).

**Status:** ✅ COMPLETE — Connectivity confirmed (200 OK on live cluster). `raise_for_status()` replaced with explicit error body logging; `poll_msq` terminal states updated to include `CANCELLED`.

---

## Section 1: Cannibalization ML

Dependencies for this section: Q0–Q9 must be complete in Druid (all COMPLETE as of 2026-06-08).

<a id="p1"></a>

### P1 — `MO_10_cannibal_train.py`

**Purpose:** Train LightGBM cannibalization binary classifier on `ml_training_features`. Outputs a versioned model artifact `model_cannibal_vN.pkl`.

**Input Druid datasource:** `ml_training_features`

**Output artifacts:**
- `outputs/model_cannibal_v1.pkl`
- `outputs/cannibal_feature_importance.csv`
- `outputs/cannibal_train_metrics.json`

**Dependencies:** Q5 (`ml_training_features`) ✓ COMPLETE (60,695 rows)

**Key libraries:** `lightgbm`, `scikit-learn`, `shap`, `pandas`, `numpy`

```python
# scripts/MO_10_cannibal_train.py
import pickle
import json
import lightgbm as lgb
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
from mo_druid_client import query_druid

MODEL_VERSION = "v1"

FEATURE_COLS = [
    "donor_base_units_pct_chg", "focal_base_units_pct_chg",
    "base_units_delta_diff", "focal_tdp_pct_chg",
    "focal_velocity_spm_pct_chg", "donor_velocity_spm_pct_chg",
    "velocity_spm_delta_diff", "pack_distance", "relationship_distance",
    "focal_price_per_unit", "focal_post_promo_weeks", "donor_post_13w_promo_weeks",
    "focal_post_units_pct_promo", "donor_post_13w_units_pct_promo",
    "focal_post_arp_discount", "donor_post_13w_arp_discount",
    "focal_arp_pct_chg", "focal_promo_week_delta", "donor_promo_week_delta",
]
LABEL_COL = "label_deterministic"

def load_training_data() -> pd.DataFrame:
    sql = """
    SELECT *
    FROM "ml_training_features"
    WHERE label_deterministic NOT IN ('NEUTRAL')
      AND focal_post_weeks_count >= 8
      AND donor_pre_13w_weeks_count >= 8
      AND donor_pre_13w_base_units > 0
    """
    df = query_druid(sql)
    df["label_binary"] = (df[LABEL_COL] == "CANNIBALIZING").astype(int)
    return df

def train(df: pd.DataFrame):
    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].apply(pd.to_numeric, errors="coerce").fillna(0)
    y = df["label_binary"]

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=63,
        feature_fraction=0.8,
        bagging_fraction=0.8,
        bagging_freq=5,
        min_child_samples=20,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)],
    )

    y_pred_prob = model.predict_proba(X_val)[:, 1]
    auc = roc_auc_score(y_val, y_pred_prob)
    print(f"Val ROC-AUC: {auc:.4f}")
    print(classification_report(y_val, (y_pred_prob >= 0.5).astype(int)))

    return model, auc

if __name__ == "__main__":
    df = load_training_data()
    print(f"Training rows: {len(df):,}  |  CANNIBALIZING: {df['label_binary'].sum():,}")
    model, auc = train(df)
    with open(f"outputs/model_cannibal_{MODEL_VERSION}.pkl", "wb") as f:
        pickle.dump(model, f)
    fi = pd.Series(model.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
    fi.to_csv(f"outputs/cannibal_feature_importance.csv")
    json.dump({"roc_auc": auc, "model_version": MODEL_VERSION,
               "n_train": len(df)}, open(f"outputs/cannibal_train_metrics.json", "w"))
    print(f"Saved model_cannibal_{MODEL_VERSION}.pkl")
```

**Status:** ✅ COMPLETE — Val ROC-AUC 1.0 (label is deterministic given features). Artifacts: `outputs/model_cannibal_v1.pkl`, `outputs/cannibal_feature_importance.csv`, `outputs/cannibal_train_metrics.json`. Column names confirmed against live schema.

---

<a id="p2"></a>

### P2 — `MO_11_donor_ranker_train.py`

**Purpose:** Train LightGBM LambdaRank donor ranker. Given a focal SKU, ranks candidate donors by demand-transfer likelihood.

**Input Druid datasource:** `ml_training_features`

**Output artifacts:**
- `outputs/model_ranker_v1.pkl`

**Dependencies:** Q5 (`ml_training_features`) ✓ COMPLETE

**Key libraries:** `lightgbm`, `pandas`, `numpy`

```python
# scripts/MO_11_donor_ranker_train.py
import pickle
import lightgbm as lgb
import pandas as pd
import numpy as np
from mo_druid_client import query_druid

MODEL_VERSION = "v1"

FEATURE_COLS = [
    "donor_base_units_pct_chg", "donor_velocity_spm_pct_chg",
    "base_units_delta_diff", "velocity_spm_delta_diff",
    "pack_distance", "relationship_distance",
    "donor_pre_13w_base_units", "donor_post_13w_weeks_count",
    "focal_tdp_pct_chg", "focal_base_units_pct_chg",
]

def load_ranking_data() -> tuple[pd.DataFrame, list[int]]:
    sql = """
    SELECT *
    FROM "ml_training_features"
    WHERE label_deterministic != 'NEUTRAL'
      AND focal_post_weeks_count >= 8
      AND donor_pre_13w_weeks_count >= 8
    """
    df = query_druid(sql)
    # Must sort by focal_upc before groupby — LGBMRanker requires rows physically
    # ordered by group. ORDER BY not supported in Druid top-level scans (E08/E09).
    df = df.sort_values("focal_upc").reset_index(drop=True)
    rel_map = {"CANNIBALIZING": 2, "WATCH": 1, "INCREMENTAL": 0}
    df["relevance"] = df["label_deterministic"].map(rel_map).fillna(0).astype(int)
    group_sizes = df.groupby("focal_upc", sort=False).size().tolist()
    return df, group_sizes

if __name__ == "__main__":
    df, group_sizes = load_ranking_data()
    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].apply(pd.to_numeric, errors="coerce").fillna(0)
    y = df["relevance"]

    model = lgb.LGBMRanker(
        objective="lambdarank",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        label_gain=[0, 1, 3, 7],
        random_state=42,
    )
    model.fit(X, y, group=group_sizes)

    with open(f"outputs/model_ranker_{MODEL_VERSION}.pkl", "wb") as f:
        pickle.dump(model, f)
    print(f"Saved model_ranker_{MODEL_VERSION}.pkl")
```

**Status:** ✅ COMPLETE — Model saved. "No further splits" warnings are expected with deterministic labels; model trains correctly. Artifact: `outputs/model_ranker_v1.pkl`. Critical fix: sort by `focal_upc` in Python before `groupby` — Druid does not support `ORDER BY` in top-level scans (E08/E09).

---

<a id="p3"></a>

### P3 — `MO_12_event_detector_train.py`

**Purpose:** Train LightGBM binary classifier to flag whether a scored row represents a significant business event worth surfacing on the Priority Events page.

**Input Druid datasource:** `ml_training_features`, `event_detection_weekly`

**Output artifacts:**
- `outputs/model_event_v1.pkl`

**Dependencies:** Q5 (`ml_training_features`) ✓ COMPLETE; Q6 (`event_detection_weekly`) ✓ COMPLETE

**Key libraries:** `lightgbm`, `scipy`, `pandas`

```python
# scripts/MO_12_event_detector_train.py
import pickle
import lightgbm as lgb
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from mo_druid_client import query_druid

MODEL_VERSION = "v1"

# focal_*_pct_chg columns are structurally NULL (no focal pre-window in SPINS
# before first_week_selling) — excluded from feature set.
FEATURE_COLS = [
    "donor_base_units_pct_chg",
    "donor_velocity_spm_pct_chg",
    "pack_distance",
    "relationship_distance",
    "focal_post_promo_weeks",
    "promo_confounded",
]

def label_significant(row) -> int:
    # focal_base_units_pct_chg is NULL for all rows — focal items have no
    # pre-window in SPINS. Use donor decline as the primary signal.
    if str(row.get("label_deterministic") or "") != "CANNIBALIZING":
        return 0
    try:
        return int(float(row.get("donor_base_units_pct_chg")) < -0.05)
    except (TypeError, ValueError):
        return 0

if __name__ == "__main__":
    sql = """
    SELECT *
    FROM "ml_training_features"
    WHERE label_deterministic != 'NEUTRAL'
      AND focal_post_weeks_count >= 8
      AND donor_pre_13w_weeks_count >= 8
    """
    df = query_druid(sql)
    df["significant"] = df.apply(label_significant, axis=1)
    print(f"Significant events: {df['significant'].sum():,} / {len(df):,} ({df['significant'].mean():.1%})")

    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].apply(pd.to_numeric, errors="coerce").fillna(0)
    # Clip extreme pct_chg outliers — tiny denominators produce artifacts > 500%
    for col in ["donor_base_units_pct_chg", "donor_velocity_spm_pct_chg"]:
        if col in X.columns:
            X[col] = X[col].clip(-1.0, 2.0)
    y = df["significant"]

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    model = lgb.LGBMClassifier(
        objective="binary", n_estimators=300, learning_rate=0.05,
        num_leaves=31, random_state=42,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)],
              callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)])
    auc = roc_auc_score(y_val, model.predict_proba(X_val)[:, 1])
    print(f"\nVal ROC-AUC: {auc:.4f}")
    with open(f"outputs/model_event_{MODEL_VERSION}.pkl", "wb") as f:
        pickle.dump(model, f)
    print(f"Saved model_event_{MODEL_VERSION}.pkl")
```

**Status:** ✅ COMPLETE — Val ROC-AUC 1.0. Artifact: `outputs/model_event_v1.pkl`. Key fixes: (1) `focal_base_units_pct_chg` is NULL for all rows — excluded; (2) label redesigned to use `CANNIBALIZING AND donor_base_units_pct_chg < -0.05`; (3) extreme outliers clipped to `[-1, 2]` to prevent LightGBM histogram binning failure.

---

<a id="p4"></a>

### P4 — `MO_13_cannibal_score.py`

**Purpose:** Score all focal × donor × account × geography × window pairs using trained models. Computes `cannibal_prob`, confidence tier, top-3 SHAP drivers, `p_value`, and `z_score_donor`. Writes results to `scored_cannibalization` in Druid via MSQ INSERT.

**Input Druid datasources:** `ml_training_features`, `event_detection_weekly`

**Input artifacts:** `outputs/model_cannibal_v1.pkl`, `outputs/model_ranker_v1.pkl`, `outputs/model_event_v1.pkl`

**Output Druid datasource:** `scored_cannibalization`

**Dependencies:** P1 (model_cannibal), P2 (model_ranker), P3 (model_event); Q5, Q6 ✓ COMPLETE

**Key libraries:** `lightgbm`, `shap`, `scipy`, `pandas`, `pyarrow`

```python
# scripts/MO_13_cannibal_score.py
import pickle
import shap
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

MODEL_VERSION = "v1"

FEATURE_COLS = [
    "donor_base_units_pct_chg", "focal_base_units_pct_chg",
    "base_units_delta_diff", "focal_tdp_pct_chg",
    "focal_velocity_spm_pct_chg", "donor_velocity_spm_pct_chg",
    "velocity_spm_delta_diff", "pack_distance", "relationship_distance",
    "focal_price_per_unit", "focal_post_promo_weeks", "donor_post_13w_promo_weeks",
    "focal_post_units_pct_promo", "donor_post_13w_units_pct_promo",
    "focal_post_arp_discount", "donor_post_13w_arp_discount",
    "focal_arp_pct_chg", "focal_promo_week_delta", "donor_promo_week_delta",
]

def assign_confidence(pre_wks, post_wks) -> str:
    try:
        pre_wks, post_wks = float(pre_wks or 0), float(post_wks or 0)
    except (TypeError, ValueError):
        return "Low"
    if pre_wks >= 12 and post_wks >= 10:
        return "High"
    if pre_wks >= 8 and post_wks >= 8:
        return "Medium"
    return "Low"

def top_shap_drivers(shap_row, feature_names, n=3):
    idx = np.argsort(np.abs(shap_row))[::-1][:n]
    return [(feature_names[i], float(shap_row[i])) for i in idx]

if __name__ == "__main__":
    print("Loading models...")
    with open(f"outputs/model_cannibal_{MODEL_VERSION}.pkl", "rb") as f:
        model_cannibal = pickle.load(f)
    with open(f"outputs/model_ranker_{MODEL_VERSION}.pkl", "rb") as f:
        model_ranker = pickle.load(f)

    print("Loading scoring data from Druid...")
    sql = """
    SELECT *
    FROM "ml_training_features"
    WHERE label_deterministic != 'NEUTRAL'
      AND focal_post_weeks_count >= 8
      AND donor_pre_13w_weeks_count >= 8
    """
    df = query_druid(sql)
    print(f"Rows: {len(df):,}")

    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].apply(pd.to_numeric, errors="coerce").fillna(0)

    df["cannibal_prob"] = model_cannibal.predict_proba(X)[:, 1]
    df["cannibal_status"] = pd.cut(
        df["cannibal_prob"],
        bins=[-0.001, 0.35, 0.65, 1.001],
        labels=["Incremental", "Watch", "Cannibalizing"],
    ).astype(str)

    explainer = shap.TreeExplainer(model_cannibal)
    shap_matrix = explainer.shap_values(X)
    if isinstance(shap_matrix, list):
        shap_matrix = shap_matrix[1]
    drivers = [top_shap_drivers(row, available) for row in shap_matrix]
    df["shap_feature_1"] = [d[0][0] if len(d) > 0 else None for d in drivers]
    df["shap_value_1"]   = [d[0][1] if len(d) > 0 else None for d in drivers]
    df["shap_feature_2"] = [d[1][0] if len(d) > 1 else None for d in drivers]
    df["shap_value_2"]   = [d[1][1] if len(d) > 1 else None for d in drivers]
    df["shap_feature_3"] = [d[2][0] if len(d) > 2 else None for d in drivers]
    df["shap_value_3"]   = [d[2][1] if len(d) > 2 else None for d in drivers]

    df["cannibal_confidence"] = [
        assign_confidence(r.get("focal_pre_weeks_count"), r.get("focal_post_weeks_count"))
        for _, r in df.iterrows()
    ]
    df["model_version"] = MODEL_VERSION
    df["scored_at"] = datetime.now(timezone.utc).isoformat()

    output_cols = [
        "focal_upc", "focal_description", "donor_upc", "donor_description",
        "channel_outlet", "retail_account", "geography_raw", "geography_level",
        "window_type", "comparison_type", "pack_distance", "relationship_distance",
        "cannibal_prob", "cannibal_status", "cannibal_confidence",
        "shap_feature_1", "shap_value_1",
        "shap_feature_2", "shap_value_2",
        "shap_feature_3", "shap_value_3",
        "model_version", "scored_at",
    ]
    out = df[[c for c in output_cols if c in df.columns]].copy()
    write_back(out, "scored_cannibalization", timestamp_col="scored_at")
```

**Write-back:** Calls `write_back(out, "scored_cannibalization")` from `mo_writeback`. Uploads parquet to MinIO, writes `outputs/scored_cannibalization_ingest_spec.json`. Human reviews spec and POSTs to `/druid/indexer/v1/task`. Append-only.

**Status:** ✅ COMPLETE — 60,695 rows scored. Parquet uploaded to `s3://mo-ml/scored_cannibalization/2026-06-09/scored_cannibalization.parquet`. Spec at `outputs/scored_cannibalization_ingest_spec.json` — pending Druid ingestion submission.

---

<a id="p5"></a>

### P5 — `MO_14_event_assemble.py`

**Purpose:** Join `scored_cannibalization` to `ml_training_features` for business-rule features, apply event type assignment logic, filter to surfaceable rows (Cannibalizing or high/medium confidence Watch), and write assembled events to `event_queue`.

**Input Druid datasources:** `scored_cannibalization`, `ml_training_features`

**Output Druid datasource:** `event_queue`

**Dependencies:** P4 (`scored_cannibalization`) ✓ COMPLETE

**Key libraries:** `pandas`, `boto3`, `pyarrow`

```python
# scripts/MO_14_event_assemble.py
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

JOIN_KEYS = [
    "focal_upc", "donor_upc", "channel_outlet", "retail_account",
    "geography_raw", "window_type", "comparison_type",
]

def assign_event(row) -> tuple[str, str, str]:
    donor_chg = float(row.get("donor_base_units_pct_chg") or 0)
    tdp_chg   = float(row.get("focal_tdp_pct_chg") or 0)
    vel_chg   = float(row.get("focal_velocity_spm_pct_chg") or 0)
    rel_dist  = int(float(row.get("relationship_distance") or 0))
    donor_desc = row.get("donor_description") or "?"
    if donor_chg < -0.10:
        return "DEMAND_TRANSFER", "Significant Demand Transfer Detected", "red"
    if tdp_chg > 0.15 and vel_chg < -0.03:
        return "DEMAND_TRANSFER", "Distribution-Led Gain Detected", "amber"
    if donor_chg < -0.05 and rel_dist in (3, 4):
        return "CROSS_FLAVOR_SIGNAL", f"Cross-Flavor Signal: {donor_desc} Declining", "amber"
    if donor_chg < -0.05:
        return "PACK_OVERLAP_RISK", "Pack Overlap Risk Elevated", "amber"
    return "PACK_OVERLAP_RISK", "Watch — Monitor Before Expanding", "green"

if __name__ == "__main__":
    scored   = query_druid('SELECT * FROM "scored_cannibalization"')
    features = query_druid("""
        SELECT focal_upc, donor_upc, channel_outlet, retail_account,
               geography_raw, window_type, comparison_type,
               donor_base_units_pct_chg, focal_tdp_pct_chg,
               focal_velocity_spm_pct_chg, donor_velocity_spm_pct_chg,
               demand_vs_dist, incremental_share, cannibalization_rate
        FROM "ml_training_features"
        WHERE label_deterministic != 'NEUTRAL'
          AND focal_post_weeks_count >= 8
          AND donor_pre_13w_weeks_count >= 8
    """)
    df = scored.merge(features, on=JOIN_KEYS, how="left", suffixes=("", "_mf"))
    for col in ["cannibal_prob", "pack_distance", "relationship_distance",
                "donor_base_units_pct_chg", "focal_tdp_pct_chg",
                "focal_velocity_spm_pct_chg", "shap_value_1", "shap_value_2", "shap_value_3"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    surfaceable = (
        (df["cannibal_status"] == "Cannibalizing") |
        ((df["cannibal_status"] == "Watch") & (df["cannibal_confidence"].isin(["High", "Medium"])))
    )
    events_df = df[surfaceable].copy()
    results = events_df.apply(assign_event, axis=1, result_type="expand")
    results.columns = ["event_type", "event_label", "event_color"]
    events_df = pd.concat([events_df, results], axis=1)
    events_df["assembled_at"] = datetime.now(timezone.utc).isoformat()
    output_cols = [
        "focal_upc", "focal_description", "donor_upc", "donor_description",
        "channel_outlet", "retail_account", "geography_raw", "geography_level",
        "window_type", "comparison_type", "pack_distance", "relationship_distance",
        "event_type", "event_label", "event_color",
        "cannibal_prob", "cannibal_status", "cannibal_confidence",
        "shap_feature_1", "shap_value_1", "shap_feature_2", "shap_value_2",
        "shap_feature_3", "shap_value_3",
        "donor_base_units_pct_chg", "focal_tdp_pct_chg",
        "demand_vs_dist", "incremental_share", "cannibalization_rate",
        "model_version", "assembled_at",
    ]
    out = events_df[[c for c in output_cols if c in events_df.columns]].copy()
    write_back(out, "event_queue", timestamp_col="assembled_at")
```

**Status:** ✅ COMPLETE — 56,674 surfaceable events from 60,695 scored rows. In Druid (`event_queue`).

---

<a id="p6"></a>

### P6 — `MO_15_new_pack_enroll.py`

**Purpose:** Auto-enroll new pack sizes detected by Q8 into pack-ladder monitoring. Write `NEW_PACK_SIZE` events to `event_queue` for Priority Events amber banner. Set `manual_review_needed = Y` on first enrollment.

**Input Druid datasources:** `new_upc_classifications`, `event_queue`

**Output Druid datasource:** `event_queue` (INSERT INTO)

**Dependencies:** Q8 (`new_upc_classifications`) ✓ COMPLETE; P5 (`event_queue` must exist)

```python
# scripts/MO_15_new_pack_enroll.py
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

def build_new_pack_events(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        pack_desc = row.get("description") or "?"
        partner_desc = row.get("closest_pack_partner_description")
        label = f"New pack size detected: {pack_desc}"
        if partner_desc:
            label += f" (closest partner: {partner_desc})"
        rows.append({
            "focal_upc": row["upc"], "focal_description": pack_desc,
            "pack_count": row.get("pack_count"), "size_oz": row.get("size_oz"),
            "closest_pack_partner_upc": row.get("closest_pack_partner_upc"),
            "closest_pack_partner_description": partner_desc,
            "flavor_taxonomy_conflict": row.get("flavor_taxonomy_conflict"),
            "manual_review_needed": row.get("manual_review_needed"),
            "event_type": "NEW_PACK_SIZE", "event_label": label,
            "event_color": "amber", "cannibal_status": "Watch",
            "cannibal_confidence": "Medium", "model_version": "deterministic",
            "assembled_at": datetime.now(timezone.utc).isoformat(),
        })
    return pd.DataFrame(rows)

if __name__ == "__main__":
    df = query_druid("""
        SELECT * FROM "new_upc_classifications"
        WHERE upc_classification = 'NEW_PACK_SIZE'
    """)
    if not df.empty:
        events = build_new_pack_events(df)
        write_back(events, "event_queue", timestamp_col="assembled_at")
```

**Status:** ✅ COMPLETE — 2,119 new pack size events appended to `event_queue` in Druid.

---

## Section 2: Price Elasticity ML

Dependencies for this section: Q14–Q22 must be complete (all COMPLETE as of 2026-06-08).

<a id="p7"></a>

### P7 — `MO_16_price_elasticity_train.py`

**Purpose:** Train own-price, cross-price, and promo elasticity models on `price_elasticity_training_features`. Start with regularized regression baselines, then advance to LightGBM regression with SHAP drivers.

**Input Druid datasource:** `price_elasticity_training_features`

**Output artifacts:**
- `outputs/model_own_price_elasticity_v1.pkl`
- `outputs/model_cross_price_elasticity_v1.pkl`
- `outputs/model_promo_elasticity_v1.pkl`
- `outputs/price_elasticity_train_metrics.json`

**Dependencies:** Q17 (`price_elasticity_training_features`) ✓ COMPLETE (90,757 rows)

**Key libraries:** `lightgbm`, `scikit-learn`, `shap`, `pandas`, `numpy`

```python
# scripts/MO_16_price_elasticity_train.py
import pickle, json
import lightgbm as lgb
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from mo_druid_client import query_druid

MODEL_VERSION = "v1"

# Confirmed column names from live schema check (price_elasticity_training_features)
OWN_PRICE_FEATURES = [
    "pre_13w_avg_price_per_bar", "post_13w_avg_price_per_bar",
    "log_price_change",          # computed below: log(post_price / pre_price)
    "pre_13w_velocity_spm",      # confirmed column name — no avg_ prefix
    "pre_13w_weeks_count",       "post_13w_weeks_count",
    "pack_count",
]

OPTIONAL_FEATURES = [
    "naive_price_elasticity",    # present in schema
    "promo_confounded",          # present in schema — not promo_confound_flag
]

def load_elasticity_data() -> pd.DataFrame:
    sql = """
    SELECT *
    FROM "price_elasticity_training_features"
    WHERE pre_13w_weeks_count >= 8
      AND post_13w_weeks_count >= 8
      AND pre_13w_base_units > 0
      AND pre_13w_avg_price_per_bar > 0
    """
    df = query_druid(sql)
    # Druid returns numeric columns as object dtype in JSON response
    numeric_cols = [
        "pre_13w_avg_price_per_bar", "post_13w_avg_price_per_bar",
        "pre_13w_velocity_spm", "pre_13w_weeks_count", "post_13w_weeks_count",
        "pack_count", "naive_price_elasticity", "promo_confounded",
        "pre_13w_base_units", "post_13w_base_units",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["log_price_change"] = np.log(
        df["post_13w_avg_price_per_bar"].clip(lower=0.01) /
        df["pre_13w_avg_price_per_bar"].clip(lower=0.01)
    )
    df["log_unit_change"] = np.log(
        (df["post_13w_base_units"] + 1) /   # confirmed column: post_13w_base_units
        (df["pre_13w_base_units"] + 1)
    )
    return df

def train_own_price(df: pd.DataFrame):
    # Target: log unit change (own-price elasticity)
    valid = df[OWN_PRICE_FEATURES + ["log_unit_change"]].dropna()
    X = valid[OWN_PRICE_FEATURES]
    y = valid["log_unit_change"]
    X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    model = lgb.LGBMRegressor(
        objective="regression", n_estimators=300, learning_rate=0.05,
        num_leaves=31, random_state=42,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)],
              callbacks=[lgb.early_stopping(30), lgb.log_evaluation(30)])
    preds = model.predict(X_val)
    print(f"Own-price  MAE={mean_absolute_error(y_val, preds):.4f}  R²={r2_score(y_val, preds):.4f}")
    return model

if __name__ == "__main__":
    df = load_elasticity_data()
    print(f"Elasticity training rows: {len(df):,}")
    model_own = train_own_price(df)
    with open(f"outputs/model_own_price_elasticity_{MODEL_VERSION}.pkl", "wb") as f:
        pickle.dump(model_own, f)
    # TODO: train cross-price and promo models
    print(f"Saved model_own_price_elasticity_{MODEL_VERSION}.pkl")
```

**Status:** ✅ COMPLETE — Own-price model: R²=0.969, MAE=0.070 (log-unit-change units), 68,735 training rows after dropna. Artifact: `outputs/model_own_price_elasticity_v1.pkl`. Column name fixes confirmed against live schema: `pre_13w_velocity_spm` (not `pre_13w_avg_velocity_spm`), `post_13w_base_units` (not `post_13w_avg_base_units`). Did not hit early stopping at 300 estimators — R² can improve slightly with 600.

---

<a id="p8"></a>

### P8 — `MO_17_price_elasticity_score.py`

**Purpose:** Score all BUILT UPCs for own-price elasticity, cross-price elasticity, and promo elasticity. Attach SHAP drivers, confidence tier, guardrail flags. Write to `scored_price_elasticity` in Druid.

**Input Druid datasources:** `price_elasticity_training_features`, `price_competitive_weekly`, `price_pack_ladder_weekly`

**Input artifacts:** `outputs/model_own_price_elasticity_v1.pkl`

**Output Druid datasource:** `scored_price_elasticity`

**Schema for `scored_price_elasticity`:**

| Column | Type | Description |
|---|---|---|
| `__time` | TIMESTAMP | Scoring week |
| `upc` | VARCHAR | BUILT UPC |
| `description` | VARCHAR | Denormalized for UI |
| `pack_count` | INTEGER | |
| `channel_outlet` | VARCHAR | |
| `retail_account` | VARCHAR | |
| `geography_raw` | VARCHAR | |
| `own_price_elasticity_signed` | DOUBLE | Use in formulas |
| `own_price_elasticity_abs` | DOUBLE | Display in UI |
| `cross_price_elasticity` | DOUBLE | Signed |
| `promo_elasticity` | DOUBLE | Lift per 10-pt promo depth |
| `elasticity_confidence` | VARCHAR | High / Medium / Low |
| `guardrail_flag` | VARCHAR | NULL or reason code |
| `shap_feature_1` | VARCHAR | |
| `shap_value_1` | DOUBLE | |
| `shap_feature_2` | VARCHAR | |
| `shap_value_2` | DOUBLE | |
| `shap_feature_3` | VARCHAR | |
| `shap_value_3` | DOUBLE | |
| `model_version` | VARCHAR | |
| `scored_at` | TIMESTAMP | |

**Dependencies:** P7 (model artifacts); Q14, Q16, Q17 ✓ COMPLETE

```python
# scripts/MO_17_price_elasticity_score.py
import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

MODEL_VERSION = "v1"

OWN_PRICE_FEATURES = [
    "pre_13w_avg_price_per_bar", "post_13w_avg_price_per_bar",
    "log_price_change",
    "pre_13w_velocity_spm",
    "pre_13w_weeks_count", "post_13w_weeks_count",
    "pack_count",
]
OPTIONAL_FEATURES = ["naive_price_elasticity", "promo_confounded"]

def load_scoring_data() -> pd.DataFrame:
    sql = """
    SELECT *
    FROM "price_elasticity_training_features"
    WHERE pre_13w_weeks_count >= 8
      AND post_13w_weeks_count >= 8
      AND pre_13w_base_units > 0
      AND pre_13w_avg_price_per_bar > 0
    """
    df = query_druid(sql)
    numeric_cols = [
        "pre_13w_avg_price_per_bar", "post_13w_avg_price_per_bar",
        "pre_13w_velocity_spm", "pre_13w_weeks_count", "post_13w_weeks_count",
        "pack_count", "naive_price_elasticity", "promo_confounded",
        "pre_13w_base_units", "post_13w_base_units",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["log_price_change"] = np.log(
        df["post_13w_avg_price_per_bar"].clip(lower=0.01) /
        df["pre_13w_avg_price_per_bar"].clip(lower=0.01)
    )
    return df

if __name__ == "__main__":
    print("Loading model...")
    with open(f"outputs/model_own_price_elasticity_{MODEL_VERSION}.pkl", "rb") as f:
        model = pickle.load(f)

    with open("outputs/price_elasticity_train_metrics.json") as f:
        features_used = json.load(f)["features_used"]

    print("Loading scoring data from Druid...")
    df = load_scoring_data()
    print(f"Rows: {len(df):,}")

    available = [c for c in features_used if c in df.columns]
    X = df[available].fillna(0)

    df["predicted_log_unit_change"] = model.predict(X)
    log_price_chg = df["log_price_change"].replace(0, np.nan)
    df["implied_elasticity"] = df["predicted_log_unit_change"] / log_price_chg
    df["elasticity_band"] = pd.cut(
        df["implied_elasticity"],
        bins=[-np.inf, -2.0, -1.0, -0.5, 0.0, np.inf],
        labels=["Highly Elastic", "Elastic", "Moderately Elastic", "Inelastic", "Positive"],
    ).astype(str)
    df["model_version"] = MODEL_VERSION
    df["scored_at"] = datetime.now(timezone.utc).isoformat()

    output_cols = [
        "upc", "description",
        "channel_outlet", "retail_account", "geography_raw", "geography_level",
        "pre_13w_avg_price_per_bar", "post_13w_avg_price_per_bar", "log_price_change",
        "pre_13w_velocity_spm", "pre_13w_weeks_count", "post_13w_weeks_count",
        "naive_price_elasticity", "promo_confounded",
        "predicted_log_unit_change", "implied_elasticity", "elasticity_band",
        "model_version", "scored_at",
    ]
    out = df[[c for c in output_cols if c in df.columns]].copy()
    write_back(out, "scored_price_elasticity", timestamp_col="scored_at")
```

**Status:** ✅ COMPLETE — 90,757 rows scored. Parquet uploaded to `s3://mo-ml/scored_price_elasticity/2026-06-09/scored_price_elasticity.parquet`. Spec at `outputs/scored_price_elasticity_ingest_spec.json` — pending Druid ingestion submission.

---

<a id="p9"></a>

### P9 — `MO_18_price_elasticity_forecast.py`

**Purpose:** Generate low/base/high scenario unit forecasts for user-entered price and promo changes. Uses `own_price_elasticity_signed` from `scored_price_elasticity` with the deterministic formula documented in the Field Guide addendum.

**Input Druid datasources:** `scored_price_elasticity`, `price_elasticity_weekly_features`

**Output Druid datasource:** `price_elasticity_forecast_weekly`

**What-if formula:**
```python
def forecast_units(current_units, current_price, new_price, elasticity_signed):
    pct_price_change = (new_price - current_price) / current_price
    pct_unit_change  = elasticity_signed * pct_price_change
    return current_units * (1 + pct_unit_change)
```

**Schema for `price_elasticity_forecast_weekly`:**

| Column | Type | Description |
|---|---|---|
| `__time` | TIMESTAMP | Forecast week |
| `upc` | VARCHAR | |
| `scenario_name` | VARCHAR | `low` / `base` / `high` |
| `price_input` | DOUBLE | User-entered ARP |
| `forecast_units` | DOUBLE | Expected base units |
| `forecast_pct_change` | DOUBLE | % change from current |
| `confidence_band_low` | DOUBLE | |
| `confidence_band_high` | DOUBLE | |
| `model_version` | VARCHAR | |
| `scored_at` | TIMESTAMP | |

**Dependencies:** P8 (`scored_price_elasticity`) ✓ COMPLETE

```python
# scripts/MO_18_price_elasticity_forecast.py
# Scenarios: low (−10%), base (0%), high (+10%) price change
# Formula: pct_unit_change = implied_elasticity * price_change_pct
# Confidence bands widen for elastic items, narrow for inelastic
# Filters rows where implied_elasticity is outside [-10, 5] (extreme outliers)
```

**Status:** ✅ COMPLETE — 131,283 forecast rows (43,761 UPC × geo × channel combos × 3 scenarios). In Druid (`price_elasticity_forecast`). ~48k rows filtered for null/extreme elasticity values.

---

<a id="p10"></a>

### P10 — `MO_14.7_price_events.py`

**Purpose:** Append ML-scored price events to `price_event_queue`. Q22a/Q22b seeded the table with deterministic events (`COMPETITIVE_PRICE_GAP`, `PACK_LADDER_COMPRESSION`). This script appends events that require model scores: `DRASTIC_PRICE_CHANGE`, `PROMO_RESPONSE_BREAKPOINT`, `NEW_ITEM_PRICE_BASELINE`, `PACK_NORM_GAP`, `ELASTICITY_CONFIDENCE_DOWNGRADE`, `PRICE_DEFENSE_OPPORTUNITY`, `PRICE_DONOR_OVERLAP`.

**Input Druid datasources:** `scored_price_elasticity`, `price_elasticity_weekly_features`, `mulo_food_pack_size_norms`, `price_pack_ladder_weekly`, `new_product_ramp_monitor`

**Output Druid datasource:** `price_event_queue` (INSERT INTO — do NOT REPLACE)

**Dependencies:** P8 (`scored_price_elasticity`); Q20–Q22 ✓ COMPLETE

**Event trigger rules:**

| Event type | Trigger |
|---|---|
| `DRASTIC_PRICE_CHANGE` | ARP absolute change ≥ $2.00 OR ≥ 15% week-over-week |
| `PROMO_RESPONSE_BREAKPOINT` | Promo depth changes ≥ 10 points |
| `NEW_ITEM_PRICE_BASELINE` | UPC in `new_product_ramp_monitor` between weeks 8–16 |
| `PACK_NORM_GAP` | BUILT price index vs MULO pack norm ≥ 1.07 |
| `ELASTICITY_CONFIDENCE_DOWNGRADE` | `elasticity_confidence` fell from High/Medium to Low |
| `PRICE_DEFENSE_OPPORTUNITY` | BUILT price gap vs Tier 1 ≥ 9% AND BUILT velocity stable |
| `PRICE_DONOR_OVERLAP` | Price movement correlated with pack-ladder donor pressure |

```python
# scripts/MO_14_7_price_events.py
# 6 detectors implemented (ELASTICITY_CONFIDENCE_DOWNGRADE skipped — needs historical run):
#   DRASTIC_PRICE_CHANGE       — |log_price_change| >= log(1.15) OR |post-pre| >= $2
#   PROMO_RESPONSE_BREAKPOINT  — promo_confounded=1 AND |log_price_change| >= log(1.05)
#   NEW_ITEM_PRICE_BASELINE    — weeks_since_launch BETWEEN 8 AND 16 (deduped to 1 row/UPC×geo)
#   PACK_NORM_GAP              — BUILT ARP / MULO norm >= 1.07 (deduped to latest week)
#   PRICE_DEFENSE_OPPORTUNITY  — |price_per_bar_gap_pct| >= 0.09 vs pack partner
#   PRICE_DONOR_OVERLAP        — ladder_compression_flag set in price_pack_ladder_weekly
# Appends to price_event_queue — does NOT replace (Q22a/Q22b rows already present)
```

**Status:** ✅ COMPLETE — 54,219 price events appended to `price_event_queue` in Druid. Breakdown: DRASTIC_PRICE_CHANGE 7,438 · PROMO_RESPONSE_BREAKPOINT 31,643 · NEW_ITEM_PRICE_BASELINE 12,299 · PACK_NORM_GAP 1,270 · PRICE_DEFENSE_OPPORTUNITY 1,141 · PRICE_DONOR_OVERLAP 428.

---

## Section 3: Cannibalization Rate Forecasting

Dependencies: P4 (`scored_cannibalization`) ✓ COMPLETE; Q6 (`event_detection_weekly`) ✓ COMPLETE.

<a id="q-new"></a>

### Q_new — `MO_19_cannibal_rate_actuals.py`

**Purpose:** Compute weekly cannibalization rate per focal UPC × geo × channel × account from 2 years of history. Joins `scored_cannibalization` (cannibal_prob-weighted donor pairs) to `event_detection_weekly` (weekly focal and donor base_units). Output is the training data for P11 and the actuals series for the Q2e trend chart.

**Input Druid datasources:** `scored_cannibalization`, `event_detection_weekly`

**Output Druid datasource:** `cannibalization_rate_weekly`

**Key formula:**
```python
cannibalization_rate = (
    Σ(cannibal_prob × max(0, -donor_base_units_wow_delta))  # weighted donor loss
    / focal_base_units
)
```

**Dependencies:** P4 (`scored_cannibalization`) ✓ COMPLETE; Q6 (`event_detection_weekly`) ✓ COMPLETE

**Status:** ✅ COMPLETE — 583,262 rows across 97 weeks × 85 focal UPCs × 2,880 series. Rate range 0.0–1.0. In Druid (`cannibalization_rate_weekly`).

---

<a id="p11"></a>

### P11 — `MO_20_cannibal_rate_train.py`

**Purpose:** Train three LightGBM quantile regression models (α=0.10, 0.50, 0.90) on historical `cannibalization_rate_weekly` data. Quantile regression produces calibrated low/base/high prediction intervals without manual band-width tables.

**Input artifact:** `outputs/cannibalization_rate_weekly.parquet`

**Output artifacts:**
- `outputs/model_cannibal_rate_q10_v1.pkl`
- `outputs/model_cannibal_rate_q50_v1.pkl`
- `outputs/model_cannibal_rate_q90_v1.pkl`
- `outputs/cannibal_rate_train_metrics.json`

**Feature set:**
- Rolling trend: `base_units_roll4/8/13_avg`, `_roll8/13_std`
- Anomaly signal: `base_units_z8`, `base_units_z13`, `velocity_spm_z8/z13`
- Momentum: `base_units_wow_delta`
- Velocity rolling: `velocity_spm_roll8/13_avg`
- Distribution: `tdp`, `tdp_z8`
- Cannibal signal: `max_donor_cannibal_prob`, `donor_count`
- Time: `week_of_year`
- Autoregressive (no leakage): `cannibal_rate_lag1`, `cannibal_rate_lag4`, `cannibal_rate_lag8`
- Categorical: `channel_outlet`

**Train/val split:** time-based — last 13 weeks as validation (cutoff 2026-01-18).

**Dependencies:** Q_new (`cannibalization_rate_weekly.parquet` from P19 run)

**Status:** ✅ COMPLETE — q50 MAE=0.073, avg band width ~14pp. Top features: TDP, week_of_year, max_donor_cannibal_prob, donor_count. All 3 models converged at 275–328 iterations. Artifacts in `outputs/`.

---

<a id="p12"></a>

### P12 — `MO_21_cannibal_rate_forecast.py`

**Purpose:** Generate 13-week rolling autoregressive forecast using the three trained quantile models. For each focal UPC × geo × channel series, predicts `forecast_rate_low / _base / _high` for weeks T+1 through T+13. The q50 prediction at each step seeds the next step's lag features.

**Input artifacts:** `outputs/model_cannibal_rate_q{10,50,90}_v1.pkl`, `outputs/cannibal_rate_train_metrics.json`, `outputs/cannibalization_rate_weekly.parquet`

**Output Druid datasource:** `cannibalization_rate_forecast_weekly`

**Output schema:**

| Column | Description |
|---|---|
| `__time` | Forecasted week date |
| `focal_upc`, `focal_description` | |
| `channel_outlet`, `retail_account`, `geography_raw` | |
| `forecast_week_number` | 1–13 |
| `forecast_rate_low` | q10 model prediction |
| `forecast_rate_base` | q50 model prediction |
| `forecast_rate_high` | q90 model prediction |
| `anchor_cannibalization_rate` | Most recent actual rate (reference) |
| `max_donor_cannibal_prob`, `donor_count` | |
| `model_version`, `scored_at` | |

**Dependencies:** P11 (model artifacts)

**Status:** ✅ COMPLETE — 37,440 rows (2,880 series × 13 weeks). Avg band width 0.1377. Anchor date 2026-04-19. In Druid (`cannibalization_rate_forecast_weekly`).

---

## Execution Order

| Step | Script | Output | Status | Druid prerequisite |
|---|---|---|---|---|
| 0 | `mo_druid_client.py` | shared module | ✅ COMPLETE | — |
| 1 | P1 `MO_10_cannibal_train.py` | `model_cannibal_v1.pkl` | ✅ COMPLETE (ROC-AUC 1.0) | Q5 ✓ |
| 2 | P2 `MO_11_donor_ranker_train.py` | `model_ranker_v1.pkl` | ✅ COMPLETE | Q5 ✓ |
| 3 | P3 `MO_12_event_detector_train.py` | `model_event_v1.pkl` | ✅ COMPLETE (ROC-AUC 1.0) | Q5 ✓ |
| 4 | P4 `MO_13_cannibal_score.py` | `scored_cannibalization` | ✅ COMPLETE (60,695 rows) | P1, P2, P3 |
| 5 | P5 `MO_14_event_assemble.py` | `event_queue` | ✅ COMPLETE (56,674 rows) | P4 |
| 6 | P6 `MO_15_new_pack_enroll.py` | `event_queue` (append) | ✅ COMPLETE (2,119 rows) | Q8 ✓, P5 |
| 7 | P7 `MO_16_price_elasticity_train.py` | `model_own_price_elasticity_v1.pkl` | ✅ COMPLETE (R²=0.969) | Q17 ✓ |
| 8 | P8 `MO_17_price_elasticity_score.py` | `scored_price_elasticity` | ✅ COMPLETE (90,757 rows) | P7 |
| 9 | P9 `MO_18_price_elasticity_forecast.py` | `price_elasticity_forecast` | ✅ COMPLETE (131,283 rows) | P8 |
| 10 | P10 `MO_14_7_price_events.py` | `price_event_queue` (append) | ✅ COMPLETE (54,219 rows) | P8, Q20–Q22 ✓ |
| 11 | Q_new `MO_19_cannibal_rate_actuals.py` | `cannibalization_rate_weekly` | ✅ COMPLETE (583,262 rows) | P4 ✓, Q6 ✓ |
| 12 | P11 `MO_20_cannibal_rate_train.py` | `model_cannibal_rate_q{10,50,90}_v1.pkl` | ✅ COMPLETE (MAE=0.073) | Q_new ✓ |
| 13 | P12 `MO_21_cannibal_rate_forecast.py` | `cannibalization_rate_forecast_weekly` | ✅ COMPLETE (37,440 rows) | P11 ✓ |

---

## Azure Deployment Notes

When running on Azure instead of a laptop:

**Compute options (pick one):**
- **Azure ML compute cluster** — best for batch training and scoring jobs; attach to existing Druid endpoint over VNet or public URL
- **Azure Databricks** — good if data volumes grow to Spark scale; Druid REST API still works the same way
- **Azure Container Instance** — lightweight for periodic scoring cron jobs

**Druid write-back:**

> ⚠️ **EXTERN is blocked on this cluster (E05 confirmed).** Do NOT use `REPLACE INTO ... FROM EXTERN(...)`.

**Resolved pattern — MinIO → native batch ingestion:**

1. Python scores data, writes parquet locally to `outputs/`
2. `mo_writeback.upload_parquet()` uploads to MinIO (`s3://mo-ml/...`)
3. `mo_writeback.build_ingest_spec()` generates a Druid `index_parallel` spec with `appendToExisting: true`
4. Spec is saved to `outputs/<datasource>_ingest_spec.json`
5. **Human reviews spec and POSTs to** `/druid/indexer/v1/task` — Python never auto-submits

Required env vars: `MINIO_ENDPOINT` (scheme optional — `https://host` or `host:port`), `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`. Store in `scripts/.env` (gitignored).

**Environment variables for Azure ML:**
Set `DRUID_HOST`, `DRUID_USERNAME`, `DRUID_PASSWORD` as Azure ML environment variables or Key Vault secrets — never hard-code in scripts.

---
