"""
MO_16b — Price Elasticity Temporal Backtest

Validates whether the MO_16 v2 elasticity model generalizes across time,
not just within a random cross-section (the 80/20 split in MO_16).

Each row in price_elasticity_training_features represents a 13-week
post-window for a (UPC × account × channel × geo) combination.
__time = window_end_date (end of the post period). Splitting on this
column tests: "can the model predict elasticity for more recent windows
when trained only on older ones?"

Two evaluations on the temporal test set:
  1. Pre-trained v2 model (MO_16 production model) — tests real-world
     generalization without retraining
  2. Model retrained on temporal train only — upper bound achievable
     with purely temporal training data

Key metrics: R², MAE, direction accuracy (sign match between predicted
and actual log_unit_change).

Output: outputs/pe_backtest_results.json
         outputs/pe_backtest_per_account.json
"""

import json
import os
import pickle

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from mo_druid_client import query_druid

os.makedirs("outputs", exist_ok=True)

MODEL_VERSION = "v2"
# Train: window_end_date < TEMPORAL_CUTOFF
# Test:  window_end_date >= TEMPORAL_CUTOFF
# ~Oct 2025 puts ~26 weeks of post-windows in the test set given data through Apr 2026.
TEMPORAL_CUTOFF = "2025-10-01"
MIN_PRICE_BAR_DELTA = 0.05  # matches MO_16 / MO_17 guardrail

# Must match MO_16 v2 OWN_PRICE_FEATURES exactly
OWN_PRICE_FEATURES = [
    "pre_13w_avg_price_per_bar",
    "post_13w_avg_price_per_bar",
    "log_price_change",
    "pre_13w_velocity_spm",
    "pre_13w_weeks_count",
    "post_13w_weeks_count",
    "pack_count",
    "pre_13w_tdp",
    "post_13w_tdp",
    "tdp_pct_chg",
]
OPTIONAL_FEATURES = ["naive_price_elasticity", "promo_confounded"]

# Pass/warn thresholds for temporal holdout R²
PASS_R2  = 0.90
WARN_R2  = 0.80
PASS_DIR = 0.70  # direction accuracy: fraction where sign(pred) == sign(actual)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    """Fetch training features with window_end_date for temporal split."""
    sql = f"""
    SELECT
      TIME_FORMAT(__time, 'yyyy-MM-dd') AS window_end_date,
      pre_13w_avg_price_per_bar, post_13w_avg_price_per_bar,
      pre_13w_base_units,       post_13w_base_units,
      pre_13w_velocity_spm,
      pre_13w_weeks_count,      post_13w_weeks_count,
      pre_13w_tdp,              post_13w_tdp,       tdp_pct_chg,
      pack_count,
      naive_price_elasticity,   promo_confounded,
      upc, description,
      channel_outlet, retail_account, geography_raw, geography_level
    FROM "price_elasticity_training_features"
    WHERE pre_13w_weeks_count  >= 8
      AND post_13w_weeks_count >= 8
      AND pre_13w_base_units    > 0
      AND pre_13w_avg_price_per_bar > 0
    """
    df = query_druid(sql)

    numeric_cols = [
        "pre_13w_avg_price_per_bar", "post_13w_avg_price_per_bar",
        "pre_13w_base_units", "post_13w_base_units",
        "pre_13w_velocity_spm", "pre_13w_weeks_count", "post_13w_weeks_count",
        "pre_13w_tdp", "post_13w_tdp", "tdp_pct_chg",
        "pack_count", "naive_price_elasticity", "promo_confounded",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["window_end_date"] = pd.to_datetime(df["window_end_date"], errors="coerce")

    df["log_price_change"] = np.log(
        df["post_13w_avg_price_per_bar"].clip(lower=0.01) /
        df["pre_13w_avg_price_per_bar"].clip(lower=0.01)
    )
    df["log_unit_change"] = np.log(
        (df["post_13w_base_units"] + 1) /
        (df["pre_13w_base_units"] + 1)
    )

    # Apply same price-move guardrail as MO_16 / MO_17:
    # rows with near-zero price change are noise at CRMA level and
    # produce astronomically wrong implied elasticity on division.
    before = len(df)
    df = df[
        (df["post_13w_avg_price_per_bar"] - df["pre_13w_avg_price_per_bar"]).abs()
        >= MIN_PRICE_BAR_DELTA
    ].copy()
    print(f"  Price guardrail (|Δ$/bar| >= ${MIN_PRICE_BAR_DELTA}): "
          f"removed {before - len(df):,} rows → {len(df):,} retained")

    return df


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def direction_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Fraction of rows where sign(pred) matches sign(actual)."""
    mask = y_true != 0
    if mask.sum() == 0:
        return float("nan")
    return (np.sign(y_pred[mask]) == np.sign(y_true[mask])).mean()


def evaluate(model, X: pd.DataFrame, y: pd.Series, label: str) -> dict:
    preds = model.predict(X)
    mae = mean_absolute_error(y, preds)
    r2  = r2_score(y, preds)
    da  = direction_accuracy(y.values, preds)
    verdict = (
        "PASS"    if r2 >= PASS_R2  else
        "MARGINAL" if r2 >= WARN_R2  else
        "FAIL"
    )
    print(f"\n  [{label}]  R²={r2:.4f}  MAE={mae:.4f}  "
          f"DirAcc={da:.1%}  n={len(y):,}  → {verdict}")
    return {"r2": round(r2, 4), "mae": round(mae, 4),
            "direction_accuracy": round(da, 4), "n": len(y), "verdict": verdict}


def per_account_breakdown(model, df: pd.DataFrame, features: list, label: str) -> list:
    """R², direction accuracy by retail_account on the test set."""
    rows = []
    for acct, grp in df.groupby("retail_account"):
        Xa = grp[features].fillna(0)
        ya = grp["log_unit_change"]
        if len(ya) < 5:
            continue
        preds = model.predict(Xa)
        r2 = r2_score(ya, preds) if len(ya) > 1 else float("nan")
        da = direction_accuracy(ya.values, preds)
        rows.append({
            "retail_account": acct,
            "n": len(ya),
            "r2": round(r2, 4),
            "direction_accuracy": round(da, 4),
            "label": label,
        })
    rows.sort(key=lambda x: x["r2"])
    return rows


# ---------------------------------------------------------------------------
# Training helper
# ---------------------------------------------------------------------------

def train_lgbm(X_tr, y_tr, X_val, y_val):
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
    )
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(30), lgb.log_evaluation(50)],
    )
    return model


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 65)
    print("MO_16b — Price Elasticity Temporal Backtest")
    print(f"  Temporal cutoff: {TEMPORAL_CUTOFF}")
    print(f"  Train: window_end_date < {TEMPORAL_CUTOFF}")
    print(f"  Test:  window_end_date >= {TEMPORAL_CUTOFF}")
    print("=" * 65)

    # -----------------------------------------------------------------------
    # 1. Load and prepare data
    # -----------------------------------------------------------------------
    print("\nLoading price_elasticity_training_features from Druid...")
    df = load_data()
    print(f"  Total rows after guardrail: {len(df):,}")
    print(f"  Date range: {df['window_end_date'].min().date()} → "
          f"{df['window_end_date'].max().date()}")

    # Feature set: use same as MO_16 v2 (optional features only if present)
    optional_available = [c for c in OPTIONAL_FEATURES if c in df.columns]
    features = OWN_PRICE_FEATURES + optional_available
    missing = [c for c in OWN_PRICE_FEATURES if c not in df.columns]
    if missing:
        print(f"  WARNING: missing required features: {missing}")
        features = [f for f in features if f in df.columns]

    valid = df[features + ["log_unit_change", "window_end_date",
                           "retail_account", "upc"]].dropna(
        subset=features + ["log_unit_change"]
    )
    print(f"  Rows after dropna: {len(valid):,} "
          f"(dropped {len(df) - len(valid):,} null rows)")

    # -----------------------------------------------------------------------
    # 2. Temporal split
    # -----------------------------------------------------------------------
    cutoff = pd.Timestamp(TEMPORAL_CUTOFF)
    train_df = valid[valid["window_end_date"] <  cutoff]
    test_df  = valid[valid["window_end_date"] >= cutoff]

    print(f"\nTemporal split:")
    print(f"  Train rows: {len(train_df):,}  "
          f"({train_df['window_end_date'].min().date()} → "
          f"{train_df['window_end_date'].max().date()})")
    print(f"  Test rows:  {len(test_df):,}  "
          f"({test_df['window_end_date'].min().date()} → "
          f"{test_df['window_end_date'].max().date()})")

    if len(test_df) < 50:
        print("  WARNING: fewer than 50 test rows — adjust TEMPORAL_CUTOFF")

    X_train = train_df[features]
    y_train = train_df["log_unit_change"]
    X_test  = test_df[features]
    y_test  = test_df["log_unit_change"]

    # -----------------------------------------------------------------------
    # 3. Load production v2 model and evaluate on temporal test
    # -----------------------------------------------------------------------
    print("\n--- Evaluating pre-trained v2 model on temporal test ---")
    model_path = f"outputs/model_own_price_elasticity_{MODEL_VERSION}.pkl"
    with open(model_path, "rb") as f:
        model_v2 = pickle.load(f)

    metrics_v2_temporal = evaluate(
        model_v2, X_test.fillna(0), y_test, "v2 pre-trained → temporal test"
    )

    # -----------------------------------------------------------------------
    # 4. Train a fresh model on temporal train, evaluate on temporal test
    # -----------------------------------------------------------------------
    print("\n--- Training fresh model on temporal train set ---")
    # Use a small random validation split within the temporal train for early stopping
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train, y_train, test_size=0.15, random_state=42
    )
    model_temporal = train_lgbm(
        X_tr.fillna(0), y_tr, X_val.fillna(0), y_val
    )

    print("\n--- Evaluating retrained temporal model on temporal test ---")
    metrics_retrained_temporal = evaluate(
        model_temporal, X_test.fillna(0), y_test, "retrained temporal → temporal test"
    )

    # -----------------------------------------------------------------------
    # 5. Load random-split baseline (from MO_16 saved metrics)
    # -----------------------------------------------------------------------
    random_metrics = {}
    random_metrics_path = "outputs/price_elasticity_train_metrics.json"
    if os.path.exists(random_metrics_path):
        with open(random_metrics_path) as f:
            saved = json.load(f)
        random_metrics = {
            "r2":  saved.get("r2"),
            "mae": saved.get("mae"),
            "n":   saved.get("n_train"),
            "model_version": saved.get("model_version"),
        }
        print(f"\n--- Random split baseline (MO_16 {MODEL_VERSION}) ---")
        print(f"  R²={random_metrics['r2']}  MAE={random_metrics['mae']}  "
              f"n={random_metrics['n']:,}")
    else:
        print(f"\n  WARNING: {random_metrics_path} not found — run MO_16 first")

    # -----------------------------------------------------------------------
    # 6. Gap analysis
    # -----------------------------------------------------------------------
    r2_gap = None
    if random_metrics.get("r2") and metrics_v2_temporal.get("r2") is not None:
        r2_gap = round(float(random_metrics["r2"]) - metrics_v2_temporal["r2"], 4)
        print(f"\n  Temporal generalization gap (random R² − temporal R²): {r2_gap:+.4f}")
        if abs(r2_gap) < 0.03:
            print("  → Model generalizes well across time (gap < 3pp)")
        elif r2_gap < 0.10:
            print("  → Mild temporal degradation (3–10pp gap) — investigate which accounts")
        else:
            print("  → Material temporal degradation (>10pp gap) — model overfits to training period")

    # -----------------------------------------------------------------------
    # 7. Per-account breakdown on temporal test
    # -----------------------------------------------------------------------
    print("\n--- Per-account breakdown (temporal test, v2 model) ---")
    acct_rows = per_account_breakdown(
        model_v2, test_df.assign(**{f: test_df[f].fillna(0) for f in features}),
        features, "v2 pre-trained"
    )
    bottom5 = acct_rows[:5]
    top5    = acct_rows[-5:]
    print(f"  Bottom 5 accounts (lowest R²):")
    for r in bottom5:
        print(f"    {r['retail_account']:<40} R²={r['r2']:>7.4f}  "
              f"DirAcc={r['direction_accuracy']:.1%}  n={r['n']}")
    print(f"  Top 5 accounts (highest R²):")
    for r in top5:
        print(f"    {r['retail_account']:<40} R²={r['r2']:>7.4f}  "
              f"DirAcc={r['direction_accuracy']:.1%}  n={r['n']}")

    # -----------------------------------------------------------------------
    # 8. Save results
    # -----------------------------------------------------------------------
    results = {
        "temporal_cutoff": TEMPORAL_CUTOFF,
        "n_train": len(train_df),
        "n_test":  len(test_df),
        "features_used": features,
        "random_split_baseline": random_metrics,
        "temporal_test_pretrained_v2": metrics_v2_temporal,
        "temporal_test_retrained": metrics_retrained_temporal,
        "r2_generalization_gap": r2_gap,
        "pass_thresholds": {"r2": PASS_R2, "r2_warn": WARN_R2, "direction_accuracy": PASS_DIR},
    }
    out_path = "outputs/pe_backtest_results.json"
    json.dump(results, open(out_path, "w"), indent=2)
    print(f"\nSaved {out_path}")

    acct_path = "outputs/pe_backtest_per_account.json"
    json.dump(acct_rows, open(acct_path, "w"), indent=2)
    print(f"Saved {acct_path}")

    # -----------------------------------------------------------------------
    # 9. Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)
    print(f"  Random split R²      : {random_metrics.get('r2', 'n/a')}")
    print(f"  Temporal test R²     : {metrics_v2_temporal['r2']}  "
          f"({metrics_v2_temporal['verdict']})")
    print(f"  Retrained temporal R²: {metrics_retrained_temporal['r2']}  "
          f"({metrics_retrained_temporal['verdict']})")
    print(f"  Direction accuracy   : {metrics_v2_temporal['direction_accuracy']:.1%}")
    if r2_gap is not None:
        print(f"  Generalization gap   : {r2_gap:+.4f}")
    print()
    if metrics_v2_temporal["verdict"] == "PASS":
        print("  PASS — v2 model generalizes across time.")
        print("  No retraining required for temporal robustness.")
    elif metrics_v2_temporal["verdict"] == "MARGINAL":
        print("  MARGINAL — some temporal drift detected.")
        print("  Schedule v4 retrain when next SPINS drop is available.")
    else:
        print("  FAIL — model does not generalize to recent windows.")
        print("  Investigate per-account breakdown; consider temporal training split.")
    print("=" * 65)
