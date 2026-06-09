import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from mo_writeback import write_back

MODEL_VERSION  = "v1"
FORECAST_WEEKS = 13
Q_TAGS         = ["q10", "q50", "q90"]

GROUP_COLS = ["focal_upc", "channel_outlet", "retail_account", "geography_raw"]


def _load_models_and_meta() -> tuple[dict, dict]:
    models = {}
    for tag in Q_TAGS:
        path = f"outputs/model_cannibal_rate_{tag}_{MODEL_VERSION}.pkl"
        with open(path, "rb") as f:
            models[tag] = pickle.load(f)
        print(f"  Loaded {path}")
    with open(f"outputs/cannibal_rate_train_metrics.json") as f:
        meta = json.load(f)
    return models, meta


def _build_feature_row(state: dict, features_used: list[str]) -> pd.DataFrame:
    """Convert a state dict to a single-row DataFrame ready for prediction."""
    row = {col: state.get(col, np.nan) for col in features_used}
    df = pd.DataFrame([row])
    if "channel_outlet" in df.columns:
        df["channel_outlet"] = df["channel_outlet"].astype("category")
    return df


if __name__ == "__main__":
    # ── 1. Load models ───────────────────────────────────────────────────────
    print("Loading models and metadata...")
    models, meta = _load_models_and_meta()
    features_used = meta["features_used"]

    # ── 2. Load actuals — last 8 weeks per series (enough for all lags) ──────
    print("\nLoading cannibalization_rate_weekly actuals...")
    df_actual = pd.read_parquet("outputs/cannibalization_rate_weekly.parquet")
    df_actual["__time"] = pd.to_datetime(df_actual["__time"], utc=True)

    num_cols = [c for c in features_used if c not in ("channel_outlet", "week_of_year")]
    for col in num_cols:
        if col in df_actual.columns:
            df_actual[col] = pd.to_numeric(df_actual[col], errors="coerce")

    df_actual = df_actual.sort_values(GROUP_COLS + ["__time"])

    # Keep last 8 actual weeks per series to seed autoregressive lags
    df_seed = (
        df_actual
        .sort_values(GROUP_COLS + ["__time"])
        .groupby(GROUP_COLS)
        .tail(8)
        .reset_index(drop=True)
    )
    anchor_date = df_actual["__time"].max()
    print(f"  Anchor date: {anchor_date.date()}")
    print(f"  Series (focal × geo × channel): {df_seed.groupby(GROUP_COLS).ngroups:,}")

    # ── 3. Rolling 13-week autoregressive forecast ───────────────────────────
    scored_at = datetime.now(timezone.utc).isoformat()
    all_rows   = []

    for group_keys, g in df_seed.groupby(GROUP_COLS):
        g = g.sort_values("__time")
        focal_upc, channel, account, geo = group_keys

        # Keep a trailing deque of actual + predicted rates for lag generation
        # Index 0 = oldest, -1 = most recent
        rate_history = g["cannibalization_rate"].tolist()

        # Static features — use the most recent actual row
        latest = g.iloc[-1]

        # Metadata for output rows
        meta_fields = {
            "focal_upc":         focal_upc,
            "focal_description": latest.get("focal_description", None),
            "channel_outlet":    channel,
            "retail_account":    account,
            "geography_raw":     geo,
            "geography_display": latest.get("geography_display", geo),
            "geography_level":   latest.get("geography_level", None),
            "anchor_cannibalization_rate": float(latest["cannibalization_rate"]),
            "max_donor_cannibal_prob": float(latest.get("max_donor_cannibal_prob") or 0),
            "donor_count":       int(latest.get("donor_count") or 0),
        }

        # Static features that don't change week to week within a series
        static_feats = {
            col: float(pd.to_numeric(latest.get(col), errors="coerce") or 0)
            for col in features_used
            if col not in ("week_of_year", "cannibal_rate_lag1",
                           "cannibal_rate_lag4", "cannibal_rate_lag8",
                           "channel_outlet")
        }

        for step in range(1, FORECAST_WEEKS + 1):
            forecast_date = anchor_date + pd.Timedelta(weeks=step)

            # Autoregressive lags from rate_history
            lag1 = rate_history[-1]  if len(rate_history) >= 1 else np.nan
            lag4 = rate_history[-4]  if len(rate_history) >= 4 else np.nan
            lag8 = rate_history[-8]  if len(rate_history) >= 8 else np.nan

            state = {
                **static_feats,
                "channel_outlet":       channel,
                "week_of_year":         int(forecast_date.isocalendar().week),
                "cannibal_rate_lag1":   lag1,
                "cannibal_rate_lag4":   lag4,
                "cannibal_rate_lag8":   lag8,
            }
            X = _build_feature_row(state, features_used)

            rate_low  = float(np.clip(models["q10"].predict(X)[0], 0, 1))
            rate_base = float(np.clip(models["q50"].predict(X)[0], 0, 1))
            rate_high = float(np.clip(models["q90"].predict(X)[0], 0, 1))

            # Feed q50 prediction back as next step's lag
            rate_history.append(rate_base)

            all_rows.append({
                **meta_fields,
                "__time":               forecast_date,
                "forecast_week_number": step,
                "forecast_rate_low":    rate_low,
                "forecast_rate_base":   rate_base,
                "forecast_rate_high":   rate_high,
                "model_version":        MODEL_VERSION,
                "scored_at":            scored_at,
            })

    # ── 4. Assemble output ───────────────────────────────────────────────────
    out = pd.DataFrame(all_rows)
    print(f"\n  Total forecast rows: {len(out):,}")
    print(f"  Forecast weeks:      {out['forecast_week_number'].max()}")
    print(f"  Focal UPCs:          {out['focal_upc'].nunique()}")
    print(f"  Base rate range:     {out['forecast_rate_base'].min():.4f} – {out['forecast_rate_base'].max():.4f}")
    print(f"  Avg band width:      {(out['forecast_rate_high'] - out['forecast_rate_low']).mean():.4f}")

    if out.empty:
        print("No rows to write.")
    else:
        write_back(out, "cannibalization_rate_forecast_weekly", timestamp_col="__time")
