import json
import pickle
import numpy as np
import pandas as pd
import lightgbm as lgb
from datetime import datetime, timezone
from pathlib import Path

MODEL_VERSION = "v1"
QUANTILES     = [0.10, 0.50, 0.90]
Q_TAGS        = ["q10", "q50", "q90"]

GROUP_COLS = ["focal_upc", "channel_outlet", "retail_account", "geography_raw"]

FEATURE_COLS = [
    # Backward-looking rolling trend (no leakage)
    "base_units_roll4_avg",
    "base_units_roll8_avg",  "base_units_roll8_std",
    "base_units_roll13_avg", "base_units_roll13_std",
    # Z-scores / anomaly signal
    "base_units_z8", "base_units_z13",
    # Momentum
    "base_units_wow_delta",
    # Velocity rolling
    "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
    "velocity_spm_z8", "velocity_spm_z13",
    # Distribution
    "tdp", "tdp_z8",
    # Cannibal signal (static from scored_cannibalization)
    "max_donor_cannibal_prob", "donor_count",
    # Time
    "week_of_year",
    # Autoregressive — lagged rate (safe: past observations only)
    "cannibal_rate_lag1", "cannibal_rate_lag4", "cannibal_rate_lag8",
    # Categorical
    "channel_outlet",
]

LGBM_BASE = dict(
    boosting_type="gbdt",
    n_estimators=500,
    learning_rate=0.05,
    num_leaves=63,
    min_child_samples=20,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=5,
    reg_alpha=0.1,
    reg_lambda=0.1,
    random_state=42,
    n_jobs=-1,
    verbose=-1,
)

# ── Pinball / quantile loss ──────────────────────────────────────────────────
def pinball(y_true, y_pred, q):
    err = y_true - y_pred
    return float(np.mean(np.where(err >= 0, q * err, (q - 1) * err)))


if __name__ == "__main__":
    # ── 1. Load actuals ──────────────────────────────────────────────────────
    parquet_path = Path("outputs/cannibalization_rate_weekly.parquet")
    print(f"Loading {parquet_path} ...")
    df = pd.read_parquet(parquet_path)
    print(f"  Rows: {len(df):,}  |  UPCs: {df['focal_upc'].nunique()}")

    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    # ── 2. Feature engineering ───────────────────────────────────────────────
    df["week_of_year"] = df["__time"].dt.isocalendar().week.astype(int)

    for col in FEATURE_COLS:
        if col in df.columns and col != "channel_outlet":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Autoregressive lags (sorted within each series)
    for lag, col in [(1, "cannibal_rate_lag1"), (4, "cannibal_rate_lag4"), (8, "cannibal_rate_lag8")]:
        df[col] = df.groupby(GROUP_COLS)["cannibalization_rate"].shift(lag)

    # Drop rows where all lag features are NaN (early in each series)
    df = df.dropna(subset=["cannibal_rate_lag1"]).copy()
    print(f"  Rows after lag drop: {len(df):,}")

    # Encode categorical
    if "channel_outlet" in df.columns:
        df["channel_outlet"] = df["channel_outlet"].astype("category")

    # ── 3. Time-based train / val split (last 13 weeks = val) ───────────────
    cutoff = df["__time"].max() - pd.Timedelta(weeks=13)
    train = df[df["__time"] <= cutoff].copy()
    val   = df[df["__time"] >  cutoff].copy()
    print(f"  Train: {len(train):,} rows  |  Val: {len(val):,} rows  (cutoff {cutoff.date()})")

    available_features = [c for c in FEATURE_COLS if c in df.columns]
    X_train = train[available_features]
    y_train = train["cannibalization_rate"].values
    X_val   = val[available_features]
    y_val   = val["cannibalization_rate"].values

    # ── 4. Train one model per quantile ─────────────────────────────────────
    models  = {}
    metrics = {}

    for q, tag in zip(QUANTILES, Q_TAGS):
        print(f"\nTraining quantile={q} ({tag})...")
        model = lgb.LGBMRegressor(
            objective="quantile",
            alpha=q,
            **LGBM_BASE,
        )
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(100)],
        )
        preds = model.predict(X_val)
        pb    = pinball(y_val, preds, q)
        mae   = float(np.mean(np.abs(y_val - preds))) if q == 0.50 else None
        print(f"  Best iter: {model.best_iteration_}  |  Pinball loss: {pb:.5f}"
              + (f"  |  MAE: {mae:.5f}" if mae else ""))

        models[tag] = model
        metrics[tag] = {
            "quantile": q,
            "best_iteration": int(model.best_iteration_),
            "val_pinball_loss": pb,
            **({"val_mae": mae} if mae else {}),
        }

    # ── 5. Save models ───────────────────────────────────────────────────────
    for tag, model in models.items():
        out_path = f"outputs/model_cannibal_rate_{tag}_{MODEL_VERSION}.pkl"
        with open(out_path, "wb") as f:
            pickle.dump(model, f)
        print(f"  Saved {out_path}")

    # ── 6. Save metrics + feature list ──────────────────────────────────────
    meta = {
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "features_used": available_features,
        "train_rows": int(len(train)),
        "val_rows": int(len(val)),
        "train_date_range": [str(train["__time"].min().date()), str(train["__time"].max().date())],
        "val_date_range":   [str(val["__time"].min().date()),   str(val["__time"].max().date())],
        "quantile_metrics": metrics,
    }
    meta_path = f"outputs/cannibal_rate_train_metrics.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\n  Metrics → {meta_path}")

    # Top features by importance (q50 model)
    imp = pd.Series(
        models["q50"].feature_importances_,
        index=models["q50"].feature_name_,
    ).sort_values(ascending=False)
    print("\nTop 10 features (q50 gain importance):")
    print(imp.head(10).to_string())
