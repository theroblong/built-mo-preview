"""MO_27 — Generate 13-week rolling retailer sales forecast.

Reads outputs/retailer_sales_weekly.parquet (MO_25) and model PKLs (MO_26).
Produces 13 forward weekly rows per (upc, retailer, channel, geo) series.

FORECAST METHOD
---------------
Autoregressive rolling forecast: same pattern as MO_21 (cannibal rate).
  • Seed each series from its last 13 actual weeks (enough for lag13).
  • At each step, build a feature row from static series attributes +
    autoregressive lags (lag1 comes from the PREVIOUS step's q50 prediction).
  • Clamp all forecasts to 0 (unit sales can't go negative).

DOLLAR CONVERSION
-----------------
Each forecast row carries `forecast_dollars_*` = forecast_units * arp.
ARP used is the last observed weekly arp for the series. If arp_fallback=1
for that series, the period-average post_13w_arp was used — noted in output.

OUTPUT TABLE: retailer_sales_forecast (Druid)
---------------------------------------------
__time                  ISO  — forecast week timestamp
upc                     str
description             str
channel_outlet          str
retail_account          str
geography_raw           str
geography_display       str
geography_level         str
anchor_date             str  — last actual week date (ISO)
anchor_base_units       float — last actual week's base_units
anchor_arp              float — last observed ARP
forecast_week_number    int  — 1 through 13
forecast_units_low      float — q10
forecast_units_base     float — q50
forecast_units_high     float — q90
forecast_dollars_low    float — q10 × arp
forecast_dollars_base   float — q50 × arp
forecast_dollars_high   float — q90 × arp
weeks_since_launch      int  — at the forecast week (increments per step)
elasticity_band         str
max_donor_cannibal_prob float
arp_fallback            int  — 1 if ARP came from post_13w_arp fallback
model_version           str
scored_at               str  ISO
"""

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

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]


def _load_models_and_meta() -> tuple[dict, dict]:
    models = {}
    for tag in Q_TAGS:
        path = f"outputs/model_retailer_sales_{tag}_{MODEL_VERSION}.pkl"
        with open(path, "rb") as f:
            models[tag] = pickle.load(f)
        print(f"  Loaded {path}")
    with open("outputs/retailer_sales_train_metrics.json") as f:
        meta = json.load(f)
    return models, meta


def _build_feature_row(state: dict, features_used: list[str]) -> pd.DataFrame:
    row = {col: state.get(col, np.nan) for col in features_used}
    df  = pd.DataFrame([row])
    if "channel_outlet" in df.columns:
        df["channel_outlet"] = df["channel_outlet"].astype("category")
    return df


if __name__ == "__main__":
    # ── 1. Load models ───────────────────────────────────────────────────────
    print("Loading models and metadata …")
    models, meta = _load_models_and_meta()
    features_used = meta["features_used"]

    # ── 2. Load actuals panel (seed data) ────────────────────────────────────
    print("\nLoading retailer_sales_weekly.parquet …")
    df_actual = pd.read_parquet("outputs/retailer_sales_weekly.parquet")
    df_actual["__time"] = pd.to_datetime(df_actual["__time"], utc=True)

    num_cols = [c for c in features_used if c not in ("channel_outlet", "week_of_year")]
    for c in num_cols:
        if c in df_actual.columns:
            df_actual[c] = pd.to_numeric(df_actual[c], errors="coerce")

    df_actual = df_actual.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    # Keep enough trailing weeks to seed all lags (lag13 needs 13 weeks of history)
    df_seed = (
        df_actual
        .groupby(GROUP_COLS)
        .tail(13)
        .reset_index(drop=True)
    )
    anchor_date = df_actual["__time"].max()
    print(f"  Anchor date:      {anchor_date.date()}")
    print(f"  Series to forecast: {df_seed.groupby(GROUP_COLS).ngroups:,}")

    # ── 3. Rolling 13-week autoregressive forecast ───────────────────────────
    scored_at = datetime.now(timezone.utc).isoformat()
    all_rows  = []

    for group_keys, g in df_seed.groupby(GROUP_COLS):
        g = g.sort_values("__time")
        upc, channel, account, geo = group_keys

        # Seed lag history from actuals
        units_history = g["base_units"].tolist()
        arp_history   = g["arp"].tolist()

        # Latest row for static features
        latest = g.iloc[-1]

        meta_fields = {
            "upc":                  upc,
            "description":          latest.get("description"),
            "channel_outlet":       channel,
            "retail_account":       account,
            "geography_raw":        geo,
            "geography_display":    latest.get("geography_display", geo),
            "geography_level":      latest.get("geography_level"),
            "anchor_date":          latest["__time"].isoformat(),
            "anchor_base_units":    float(latest["base_units"]) if pd.notna(latest["base_units"]) else 0.0,
            "anchor_arp":           float(latest["arp"]) if pd.notna(latest["arp"]) else 0.0,
            "elasticity_band":      latest.get("elasticity_band"),
            "max_donor_cannibal_prob": float(latest.get("max_donor_cannibal_prob") or 0),
            "arp_fallback":         int(latest.get("arp_fallback") or 0),
        }

        # Static features (unchanged across forecast horizon)
        static_feats = {}
        skip = {"channel_outlet", "week_of_year",
                "base_units_lag1", "base_units_lag4", "base_units_lag13",
                "arp_lag1", "arp_lag4", "arp_wow_delta",
                "arp_roll8_avg", "arp_roll8_std", "arp"}
        for col in features_used:
            if col not in skip:
                val = latest.get(col)
                static_feats[col] = float(pd.to_numeric(val, errors="coerce") or 0)

        # ARP for dollar conversion — assume flat (user can slide in UI)
        forecast_arp = meta_fields["anchor_arp"] or float(latest.get("post_13w_arp") or 0)

        for step in range(1, FORECAST_WEEKS + 1):
            forecast_date = anchor_date + pd.Timedelta(weeks=step)
            wsl = int(latest.get("weeks_since_launch") or 0) + step

            # Autoregressive lags from combined actuals + prior predictions
            lag1  = units_history[-1]  if len(units_history) >= 1  else np.nan
            lag4  = units_history[-4]  if len(units_history) >= 4  else np.nan
            lag13 = units_history[-13] if len(units_history) >= 13 else np.nan

            arp_cur  = arp_history[-1] if arp_history else forecast_arp
            arp_lag1 = arp_history[-1] if len(arp_history) >= 1 else np.nan
            arp_lag4 = arp_history[-4] if len(arp_history) >= 4 else np.nan

            # ARP rolling stats (trailing 8 prior ARP values)
            arp_window = arp_history[-8:]
            arp_roll8_avg = float(np.nanmean(arp_window)) if arp_window else np.nan
            arp_roll8_std = float(np.nanstd(arp_window))  if len(arp_window) > 1 else 0.0
            arp_wow_delta = (arp_cur - arp_lag1) if pd.notna(arp_lag1) else 0.0

            state = {
                **static_feats,
                "channel_outlet":       channel,
                "week_of_year":         int(forecast_date.isocalendar().week),
                "weeks_since_launch":   wsl,
                "arp":                  arp_cur,
                "arp_lag1":             arp_lag1,
                "arp_lag4":             arp_lag4,
                "arp_roll8_avg":        arp_roll8_avg,
                "arp_roll8_std":        arp_roll8_std,
                "arp_wow_delta":        arp_wow_delta,
                "base_units_lag1":      lag1,
                "base_units_lag4":      lag4,
                "base_units_lag13":     lag13,
            }

            X = _build_feature_row(state, features_used)

            # Models predict in log1p space — invert with expm1
            units_low  = float(np.expm1(max(0, models["q10"].predict(X)[0])))
            units_base = float(np.expm1(max(0, models["q50"].predict(X)[0])))
            units_high = float(np.expm1(max(0, models["q90"].predict(X)[0])))

            # Feed q50 back as next step's lag seed
            units_history.append(units_base)
            arp_history.append(arp_cur)  # hold ARP flat (no external signal yet)

            all_rows.append({
                **meta_fields,
                "__time":               forecast_date,
                "forecast_week_number": step,
                "forecast_units_low":   units_low,
                "forecast_units_base":  units_base,
                "forecast_units_high":  units_high,
                "forecast_dollars_low":  round(units_low  * forecast_arp, 2),
                "forecast_dollars_base": round(units_base * forecast_arp, 2),
                "forecast_dollars_high": round(units_high * forecast_arp, 2),
                "weeks_since_launch":   wsl,
                "model_version":        MODEL_VERSION,
                "scored_at":            scored_at,
            })

    # ── 4. Assemble + diagnostics ────────────────────────────────────────────
    out = pd.DataFrame(all_rows)
    print(f"\n  Total forecast rows:   {len(out):,}")
    print(f"  Forecast weeks:        {out['forecast_week_number'].max()}")
    print(f"  Unique UPCs:           {out['upc'].nunique()}")
    print(f"  Series forecast:       {out.groupby(GROUP_COLS).ngroups:,}")
    print(f"  q50 unit range:        {out['forecast_units_base'].min():.0f} – {out['forecast_units_base'].max():.0f}")
    print(f"  q50 dollar range:      ${out['forecast_dollars_base'].min():.0f} – ${out['forecast_dollars_base'].max():.0f}")
    print(f"  Median band width:     {(out['forecast_units_high'] - out['forecast_units_low']).median():.0f} units")

    if out.empty:
        print("No rows to write.")
    else:
        write_back(out, "retailer_sales_forecast", timestamp_col="__time")
