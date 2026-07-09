"""MO_26 — Train LightGBM quantile models for retailer sales forecasting.

Reads outputs/retailer_sales_weekly.parquet (from MO_25).
Trains three quantile regressors (q10, q50, q90) using LightGBM.
Saves model PKLs and a metrics JSON to outputs/.

FEATURE DESIGN
--------------
Three groups:
  1. Backward-looking rolling stats — pre-computed in event_detection_weekly;
     no leakage risk (all shift(1)-based in Druid).
  2. ARP trend features — computed in MO_25 from built_filtered_weekly; captures
     price moves 1–8 weeks ahead of their demand impact.
  3. Autoregressive lags — lag1/4/13 of base_units; seeded with actuals at train
     time, fed from q50 predictions at forecast time (MO_27).
  4. External signals — elasticity, cannibal pressure, lifecycle stage.
  5. Seasonal — week_of_year.
  6. Categorical — channel_outlet (LightGBM native category support).

TRAIN / VAL SPLIT
-----------------
Last 13 weeks of each series = validation set (mirrors the forecast horizon).
Earlier data = training. This is a temporal holdout — no future data leaks into
training for any series.

OUTPUT
------
  outputs/model_retailer_sales_q{10,50,90}_v4.pkl
  outputs/model_total_units_q{10,50,90}_v4.pkl  (trained on correct SPINS units target)
  outputs/retailer_sales_train_metrics.json
"""

import json
import pickle
import numpy as np
import pandas as pd
import lightgbm as lgb
from datetime import datetime, timezone
from pathlib import Path

MODEL_VERSION = "v4"  # v4: total_units model retrained on correct SPINS units (not base+units_promo)
QUANTILES     = [0.10, 0.50, 0.90]
Q_TAGS        = ["q10", "q50", "q90"]

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]

FEATURE_COLS = [
    # Rolling demand stats (backward-looking, no leakage)
    "base_units_roll4_avg",
    "base_units_roll8_avg",  "base_units_roll8_std",
    "base_units_roll13_avg", "base_units_roll13_std",
    # Momentum
    "base_units_wow_delta", "base_units_z8", "base_units_z13",
    # Velocity
    "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
    "velocity_spm_z8", "velocity_spm_z13",
    # Distribution (level + week-over-week change — MO_53 champion: tdp_wow_delta promoted)
    "tdp", "tdp_z8",
    "tdp_wow_delta",
    # Price trend (from built_filtered_weekly — the spins_full lineage)
    "arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std",
    # Lifecycle
    "weeks_since_launch",
    # Competitive pool size (MO_53 champion: donor_count promoted at −0.081pp)
    # Total pool count (BUILT + competitor donors) = competitive complexity signal
    # Note: competitor_donor_count alone HURT (+0.090pp) — aggregate pool size is what matters
    "donor_count",
    # Seasonality
    "week_of_year",
    # Note: stl_seasonal_index (MO_59) is NOT a LightGBM feature — it is redundant
    # alongside week_of_year (zero importance in ablation). Applied instead as a
    # Layer 1 post-prediction multiplier in MO_27 for new SKUs lacking lag52.
    # Autoregressive lags (lagged at time T — no leakage)
    "base_units_lag1", "base_units_lag4", "base_units_lag13",
    # YAGO — year-ago lags (Bracken: "are 3 years of data comparable?")
    "base_units_lag52", "velocity_spm_lag52",
    # Categorical
    "channel_outlet",
    # Removed by ablation (hurt or below threshold): implied_elasticity, max_donor_cannibal_prob,
    # rolling_cannibal_pressure, rolling_cannibal_trend, rolling_elasticity (MO_50–MO_53)
    # MO_56: cannibal_rate (−0.104pp global, −0.073pp event) and price_elasticity_effect
    # (−0.092pp) also rejected. AR lags already encode cannibalization damage via lagged outcomes;
    # ARP pct changes too small (mean 0.33%) for elasticity interaction to carry signal.
    # MO_53 28-feature set is the CONFIRMED stopping point for feature engineering.
]

# Total-units model swaps base_units AR lags for total_units lags; same demand-driver features
TOTAL_UNIT_FEATURE_COLS = [
    c for c in FEATURE_COLS
    if not c.startswith("base_units_lag")
] + ["total_units_lag1", "total_units_lag4", "total_units_lag13", "total_units_lag52"]

LGBM_BASE = dict(
    boosting_type="gbdt",
    n_estimators=1500,
    learning_rate=0.04,
    num_leaves=63,
    min_child_samples=20,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=5,
    reg_alpha=0.1,
    reg_lambda=0.2,
    random_state=42,
    n_jobs=-1,
    verbose=-1,
)


def pinball(y_true: np.ndarray, y_pred: np.ndarray, q: float) -> float:
    err = y_true - y_pred
    return float(np.mean(np.where(err >= 0, q * err, (q - 1) * err)))


if __name__ == "__main__":
    parquet_path = Path("outputs/retailer_sales_weekly.parquet")
    print(f"Loading {parquet_path} …")
    df = pd.read_parquet(parquet_path)
    print(f"  Rows: {len(df):,} | UPCs: {df['upc'].nunique()} "
          f"| Series: {df.groupby(GROUP_COLS).ngroups:,}")

    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    # ── Numeric coercion ────────────────────────────────────────────────────
    num_cols = [c for c in FEATURE_COLS if c != "channel_outlet"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # ── Categorical encoding ─────────────────────────────────────────────────
    if "channel_outlet" in df.columns:
        df["channel_outlet"] = df["channel_outlet"].astype("category")

    # ── Drop rows where target is null (can't train or evaluate on these) ──────
    before = len(df)
    df = df.dropna(subset=["base_units"]).copy()
    if len(df) < before:
        print(f"  Dropped {before - len(df):,} rows with null base_units")

    # ── Log-transform target: log1p compresses heavy tail, forces positivity ───
    # Predictions are in log-space; MO_27 inverts with expm1 before output.
    p99 = df["base_units"].quantile(0.99)
    print(f"  p99 base_units: {p99:.0f}  (no clip needed — log transform handles scale)")
    df["log_base_units"] = np.log1p(df["base_units"])

    has_total = bool("total_units" in df.columns and df["total_units"].notna().any())
    if has_total:
        df["log_total_units"] = np.log1p(df["total_units"].clip(lower=0).fillna(0))

    # ── Temporal train / val split (last 13 weeks = val) ────────────────────
    cutoff = df["__time"].max() - pd.Timedelta(weeks=13)
    train  = df[df["__time"] <= cutoff].copy()
    val    = df[df["__time"] >  cutoff].copy()
    print(f"\n  Train: {len(train):,} rows | Val: {len(val):,} rows "
          f"(cutoff {cutoff.date()})")

    available = [c for c in FEATURE_COLS if c in df.columns]
    missing   = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"  WARNING — feature columns not found (will be skipped): {missing}")

    X_train = train[available]
    y_train = train["log_base_units"].values          # log-space target
    X_val   = val[available]
    y_val_log   = val["log_base_units"].values        # log-space for pinball
    y_val_units = val["base_units"].values            # original units for MAE/RMSE

    # ── Train base_units models (q10/q50/q90) ────────────────────────────────
    models  = {}
    metrics = {}

    for q, tag in zip(QUANTILES, Q_TAGS):
        print(f"\nTraining base_units quantile={q} ({tag}) …")
        model = lgb.LGBMRegressor(
            objective="quantile",
            alpha=q,
            **LGBM_BASE,
        )
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val_log)],
            callbacks=[
                lgb.early_stopping(50, verbose=False),
                lgb.log_evaluation(100),
            ],
        )
        preds_log   = model.predict(X_val)
        preds_units = np.expm1(np.clip(preds_log, 0, None))   # back to unit scale
        pb   = pinball(y_val_log, preds_log, q)                # pinball in log-space
        mae  = float(np.mean(np.abs(y_val_units - preds_units))) if q == 0.50 else None
        rmse = float(np.sqrt(np.mean((y_val_units - preds_units) ** 2))) if q == 0.50 else None
        print(f"  Best iter: {model.best_iteration_}  |  Pinball (log): {pb:.4f}"
              + (f"  |  MAE: {mae:.1f}  |  RMSE: {rmse:.1f}" if mae is not None else ""))

        models[tag] = model
        metrics[tag] = {
            "quantile": q,
            "best_iteration": int(model.best_iteration_),
            "val_pinball_loss": pb,
            **({"val_mae": mae, "val_rmse": rmse} if mae is not None else {}),
        }

    # ── Save base_units models ───────────────────────────────────────────────
    for tag, model in models.items():
        path = f"outputs/model_retailer_sales_{tag}_{MODEL_VERSION}.pkl"
        with open(path, "wb") as f:
            pickle.dump(model, f)
        print(f"  Saved {path}")

    # ── Feature importance (q50 model) ───────────────────────────────────────
    imp = pd.Series(
        models["q50"].feature_importances_,
        index=models["q50"].feature_name_,
    ).sort_values(ascending=False)
    print("\nTop 15 features — base_units q50:")
    print(imp.head(15).to_string())

    # ── Train total_units models (q10/q50/q90) ────────────────────────────────
    models_total  = {}
    metrics_total = {}

    if has_total:
        avail_total = [c for c in TOTAL_UNIT_FEATURE_COLS if c in df.columns]
        miss_total  = [c for c in TOTAL_UNIT_FEATURE_COLS if c not in df.columns]
        if miss_total:
            print(f"  WARNING — total_units features missing: {miss_total}")

        X_train_t = train[avail_total]
        y_train_t = train["log_total_units"].values
        X_val_t   = val[avail_total]
        y_val_log_t   = val["log_total_units"].values
        y_val_total   = val["total_units"].clip(lower=0).fillna(0).values

        for q, tag in zip(QUANTILES, Q_TAGS):
            print(f"\nTraining total_units quantile={q} ({tag}) …")
            model_t = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                **LGBM_BASE,
            )
            model_t.fit(
                X_train_t, y_train_t,
                eval_set=[(X_val_t, y_val_log_t)],
                callbacks=[
                    lgb.early_stopping(50, verbose=False),
                    lgb.log_evaluation(100),
                ],
            )
            preds_log_t   = model_t.predict(X_val_t)
            preds_total   = np.expm1(np.clip(preds_log_t, 0, None))
            pb_t  = pinball(y_val_log_t, preds_log_t, q)
            mae_t = float(np.mean(np.abs(y_val_total - preds_total))) if q == 0.50 else None
            rmse_t= float(np.sqrt(np.mean((y_val_total - preds_total) ** 2))) if q == 0.50 else None
            print(f"  Best iter: {model_t.best_iteration_}  |  Pinball (log): {pb_t:.4f}"
                  + (f"  |  MAE: {mae_t:.1f}  |  RMSE: {rmse_t:.1f}" if mae_t is not None else ""))

            models_total[tag] = model_t
            metrics_total[tag] = {
                "quantile": q,
                "best_iteration": int(model_t.best_iteration_),
                "val_pinball_loss": pb_t,
                **({"val_mae": mae_t, "val_rmse": rmse_t} if mae_t is not None else {}),
            }

        for tag, model_t in models_total.items():
            path = f"outputs/model_total_units_{tag}_{MODEL_VERSION}.pkl"
            with open(path, "wb") as f:
                pickle.dump(model_t, f)
            print(f"  Saved {path}")

        imp_t = pd.Series(
            models_total["q50"].feature_importances_,
            index=models_total["q50"].feature_name_,
        ).sort_values(ascending=False)
        print("\nTop 15 features — total_units q50:")
        print(imp_t.head(15).to_string())
    else:
        print("\n  Skipping total_units training (column not found in parquet).")
        avail_total = []
        miss_total  = []

    # ── Save metrics + feature list ──────────────────────────────────────────
    meta = {
        "model_version":    MODEL_VERSION,
        "trained_at":       datetime.now(timezone.utc).isoformat(),
        "features_used":    available,
        "features_missing": missing,
        "train_rows":       int(len(train)),
        "val_rows":         int(len(val)),
        "train_date_range": [str(train["__time"].min().date()), str(train["__time"].max().date())],
        "val_date_range":   [str(val["__time"].min().date()),   str(val["__time"].max().date())],
        "target_p99_clip":  float(p99 * 2),
        "quantile_metrics": metrics,
        "top_features_q50": imp.head(20).to_dict(),
        "total_units_trained":        has_total,
        "total_units_features_used":  avail_total,
        "total_units_features_missing": miss_total,
        "total_units_quantile_metrics": metrics_total,
    }
    meta_path = "outputs/retailer_sales_train_metrics.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\n  Metrics → {meta_path}")
