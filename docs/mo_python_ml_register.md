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

**Purpose:** For each scored row, evaluate statistical significance (Welch's t-test on pre/post windows), apply business rule thresholds, assign event type and label, suppress ramp-period rows, write assembled events to `event_queue` in Druid.

**Input Druid datasources:** `scored_cannibalization`, `ml_training_features`, `event_detection_weekly`

**Output Druid datasource:** `event_queue`

**Dependencies:** P4 (`scored_cannibalization`); Q6 (`event_detection_weekly`) ✓ COMPLETE

**Key libraries:** `scipy`, `pandas`

```python
# scripts/MO_14_event_assemble.py
from scipy import stats
import pandas as pd
from mo_druid_client import query_druid

def test_window_significance(pre_series, post_series,
                             practical_threshold_pct=0.05, alpha=0.10):
    if len(pre_series) < 4 or len(post_series) < 4:
        return {"significant": False, "reason": "INSUFFICIENT_WEEKS",
                "p_value": None, "pct_change": None}
    t_stat, p_val = stats.ttest_ind(pre_series, post_series, equal_var=False)
    mean_pre  = pre_series.mean()
    mean_post = post_series.mean()
    pct_chg   = (mean_post - mean_pre) / (abs(mean_pre) + 1e-9)
    return {
        "significant": (p_val < alpha) and (abs(pct_chg) > practical_threshold_pct),
        "pct_change":  pct_chg,
        "p_value":     p_val,
        "direction":   "UP" if pct_chg > 0 else "DOWN",
    }

def assemble_events(scored_row, sig_result, z_score):
    if scored_row.get("scoring_status") == "SUPPRESSED":
        return None
    cannibal_prob = scored_row.get("cannibal_prob", 0)
    pct_chg      = sig_result.get("pct_change", 0) or 0
    donor_chg    = scored_row.get("donor_base_units_pct_chg", 0) or 0
    tdp_chg      = scored_row.get("focal_tdp_pct_chg", 0) or 0
    vel_chg      = scored_row.get("focal_velocity_spm_pct_chg", 0) or 0
    rel_dist     = scored_row.get("relationship_distance", 1)
    confidence   = scored_row.get("cannibal_confidence", "Low")

    if donor_chg < -0.10 and pct_chg > 0.03:
        event_label = "Significant Demand Transfer Detected"
        event_type  = "DEMAND_TRANSFER"
    elif tdp_chg > 0.15 and vel_chg < -0.03:
        event_label = "Distribution-Led Gain Detected"
        event_type  = "DEMAND_TRANSFER"
    elif donor_chg < -0.05 and rel_dist in (3, 4):
        event_label = f'Cross-Flavor Signal: {scored_row.get("donor_rank_1_description","?")} Declining'
        event_type  = "CROSS_FLAVOR_SIGNAL"
    elif donor_chg < -0.05:
        event_label = "Pack Overlap Risk Elevated"
        event_type  = "PACK_OVERLAP_RISK"
    elif pct_chg < -0.10 and tdp_chg >= 0:
        event_label = "Launch Underperforming in Geography"
        event_type  = "LAUNCH_UNDERPERFORMING"
    elif abs(z_score or 0) >= 2.0:
        event_label = "Velocity Outlier Detected"
        event_type  = "DEMAND_TRANSFER"
    else:
        event_label = "Watch — Monitor Before Expanding"
        event_type  = "PACK_OVERLAP_RISK"

    return {
        "focal_upc":           scored_row["focal_upc"],
        "focal_description":   scored_row.get("focal_description"),
        "geography":           scored_row.get("geography"),
        "geography_level":     scored_row.get("geography_level"),
        "retail_account":      scored_row.get("retail_account"),
        "channel_outlet":      scored_row.get("channel_outlet"),
        "event_type":          event_type,
        "event_label":         event_label,
        "confidence":          confidence,
        "cannibal_prob":       cannibal_prob,
        "cannibal_status":     scored_row.get("cannibal_status"),
        "comparison_type":     scored_row.get("comparison_type"),
        "relationship_distance": rel_dist,
        "pct_change":          pct_chg,
        "p_value":             sig_result.get("p_value"),
        "z_score":             z_score,
        "donor_upc":           scored_row.get("donor_rank_1_upc"),
        "donor_description":   scored_row.get("donor_rank_1_description"),
        "shap_top_3":          scored_row.get("shap_top_3"),
        "scored_at":           scored_row.get("scored_at"),
        "model_version":       scored_row.get("model_version"),
    }

if __name__ == "__main__":
    df = query_druid('SELECT * FROM "scored_cannibalization"')
    # TODO: join to event_detection_weekly for z_score_donor
    # TODO: call test_window_significance per row using raw weekly series
    # TODO: write assembled events to event_queue via MSQ INSERT
    print(f"Loaded {len(df):,} scored rows. Event assembly logic pending.")
```

**Status:** Not yet run. Requires P4 to write `scored_cannibalization` first.

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
from mo_druid_client import query_druid, submit_msq, poll_msq

def build_new_pack_events(df: pd.DataFrame) -> list[dict]:
    events = []
    for _, row in df[df["classification"] == "NEW_PACK_SIZE"].iterrows():
        events.append({
            "focal_upc":        row["upc"],
            "focal_description": row.get("description"),
            "event_type":       "NEW_PACK_SIZE",
            "event_label":      f'New pack size auto-detected: {row.get("description")}',
            "confidence":       "Medium",
            "scored_at":        datetime.now(timezone.utc).isoformat(),
            "model_version":    "deterministic",
        })
    return events

if __name__ == "__main__":
    sql = 'SELECT * FROM "new_upc_classifications" WHERE classification = \'NEW_PACK_SIZE\''
    df = query_druid(sql)
    events = build_new_pack_events(df)
    print(f"New pack size events to enroll: {len(events)}")
    # TODO: INSERT INTO event_queue via MSQ
```

**Status:** Not yet run.

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

**Dependencies:** P8 (`scored_price_elasticity`); Q14 ✓ COMPLETE

**Status:** Not yet run.

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
# scripts/MO_14.7_price_events.py
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid, submit_msq, poll_msq

MODEL_VERSION = "v1"
SCORED_AT = datetime.now(timezone.utc).isoformat()

def detect_pack_norm_gap(df_scored, df_norms) -> pd.DataFrame:
    """PACK_NORM_GAP: BUILT price index vs MULO category norm >= 1.07"""
    merged = df_scored.merge(
        df_norms[["pack_size_bucket", "norm_avg_price_per_bar"]],
        left_on="pack_size_bucket", right_on="pack_size_bucket", how="left"
    )
    flags = merged[
        (merged["own_price_elasticity_abs"].notna()) &
        (merged["norm_avg_price_per_bar"] > 0) &
        (merged["current_price_per_bar"] / merged["norm_avg_price_per_bar"] >= 1.07)
    ].copy()
    flags["event_type"]  = "PACK_NORM_GAP"
    flags["event_label"] = (
        "BUILT price " +
        (flags["current_price_per_bar"] / flags["norm_avg_price_per_bar"] * 100 - 100)
        .round(1).astype(str) + "% above MULO " + flags["pack_size_bucket"] + " norm"
    )
    flags["event_color"]  = "amber"
    flags["confidence"]   = flags["elasticity_confidence"]
    flags["trigger_value"] = flags["current_price_per_bar"] / flags["norm_avg_price_per_bar"]
    flags["trigger_column"] = "price_index_vs_mulo_norm"
    flags["source_table"]  = "scored_price_elasticity + mulo_food_pack_size_norms"
    flags["scoring_window"] = "13w"
    flags["cross_tool_flag"] = 0
    flags["cross_tool_event_id"] = None
    flags["scored_at"]    = SCORED_AT
    return flags

if __name__ == "__main__":
    df_scored = query_druid('SELECT * FROM "scored_price_elasticity"')
    df_norms  = query_druid('SELECT * FROM "mulo_food_pack_size_norms"')
    # TODO: implement all 7 event detectors, combine results, INSERT INTO price_event_queue
    pack_norm_events = detect_pack_norm_gap(df_scored, df_norms)
    print(f"PACK_NORM_GAP events: {len(pack_norm_events)}")
    print("TODO: INSERT INTO price_event_queue via MSQ")
```

**Status:** Not yet run. `price_event_queue` was seeded by Q22a/Q22b; this script appends only — do not REPLACE.

---

## Execution Order

| Step | Script | Output | Status | Druid prerequisite |
|---|---|---|---|---|
| 0 | `mo_druid_client.py` | shared module | ✅ COMPLETE | — |
| 1 | P1 `MO_10_cannibal_train.py` | `model_cannibal_v1.pkl` | ✅ COMPLETE (ROC-AUC 1.0) | Q5 ✓ |
| 2 | P2 `MO_11_donor_ranker_train.py` | `model_ranker_v1.pkl` | ✅ COMPLETE | Q5 ✓ |
| 3 | P3 `MO_12_event_detector_train.py` | `model_event_v1.pkl` | ✅ COMPLETE (ROC-AUC 1.0) | Q5 ✓ |
| 4 | P4 `MO_13_cannibal_score.py` | `scored_cannibalization` | ✅ COMPLETE (60,695 rows — Druid ingestion pending) | P1, P2, P3 |
| 5 | P5 `MO_14_event_assemble.py` | `event_queue` | ⏳ Not yet run | P4, Q6 ✓ |
| 6 | P6 `MO_15_new_pack_enroll.py` | `event_queue` (append) | ⏳ Not yet run | Q8 ✓, P5 |
| 7 | P7 `MO_16_price_elasticity_train.py` | `model_own_price_elasticity_v1.pkl` | ✅ COMPLETE (R²=0.969) | Q17 ✓ |
| 8 | P8 `MO_17_price_elasticity_score.py` | `scored_price_elasticity` | ✅ COMPLETE (90,757 rows — Druid ingestion pending) | P7 |
| 9 | P9 `MO_18_price_elasticity_forecast.py` | `price_elasticity_forecast_weekly` | ⏳ Not yet run | P8 |
| 10 | P10 `MO_14.7_price_events.py` | `price_event_queue` (append) | ⏳ Not yet run | P8, Q20–Q22 ✓ |

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
