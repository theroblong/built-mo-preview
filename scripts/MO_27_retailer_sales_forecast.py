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
forecast_units_low      float — q10 (base units, promo-stripped)
forecast_units_base     float — q50
forecast_units_high     float — q90
forecast_dollars_low    float — q10 × arp
forecast_dollars_base   float — q50 × arp
forecast_dollars_high   float — q90 × arp
forecast_total_units_low  float — q10 total scan volume (base + promo); null if total_units model not trained
forecast_total_units_base float — q50 total
forecast_total_units_high float — q90 total
weeks_since_launch      int  — at the forecast week (increments per step)
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

MODEL_VERSION  = "v4"
FORECAST_WEEKS = 13
Q_TAGS         = ["q10", "q50", "q90"]

# Seasonal blend weight: fraction of each forecast step pulled toward the
# year-ago seasonal reference (lag52 × current-YoY-ratio).  Without this,
# autoregressive convergence causes the 13-week forward forecast to collapse
# to a flat mean after ~4 steps — the AR lags become self-predictions and
# drown out the weekly seasonal variation in lag52.
# 0.0 = pure AR (flat); 1.0 = pure seasonal naive.  0.40 is the default.
SEASONAL_BLEND_WEIGHT = 0.40

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]


def _load_models_and_meta() -> tuple[dict, dict, dict]:
    models = {}
    for tag in Q_TAGS:
        path = f"outputs/model_retailer_sales_{tag}_{MODEL_VERSION}.pkl"
        with open(path, "rb") as f:
            models[tag] = pickle.load(f)
        print(f"  Loaded {path}")
    with open("outputs/retailer_sales_train_metrics.json") as f:
        meta = json.load(f)
    models_total = {}
    if meta.get("total_units_trained"):
        for tag in Q_TAGS:
            path = f"outputs/model_total_units_{tag}_{MODEL_VERSION}.pkl"
            if Path(path).exists():
                with open(path, "rb") as f:
                    models_total[tag] = pickle.load(f)
                print(f"  Loaded {path}")
    return models, meta, models_total


def _build_feature_row(state: dict, features_used: list[str]) -> pd.DataFrame:
    row = {col: state.get(col, np.nan) for col in features_used}
    df  = pd.DataFrame([row])
    if "channel_outlet" in df.columns:
        df["channel_outlet"] = df["channel_outlet"].astype("category")
    return df


if __name__ == "__main__":
    # ── 1. Load models ───────────────────────────────────────────────────────
    print("Loading models and metadata …")
    models, meta, models_total = _load_models_and_meta()
    features_used       = meta["features_used"]
    features_used_total = meta.get("total_units_features_used", [])
    forecast_total      = bool(models_total)

    # ── 1b. Load MO_59 seasonal index (week_of_year → stl_seasonal_index) ───
    _seas_path = Path("outputs/mo59_seasonal_index.csv")
    if _seas_path.exists():
        _seas_df = pd.read_csv(_seas_path)
        seasonal_lookup: dict[int, float] = dict(
            zip(_seas_df["week_of_year"].astype(int), _seas_df["seasonal_index"])
        )
        print(f"  Loaded STL seasonal index ({len(seasonal_lookup)} weeks)")
    else:
        seasonal_lookup = {}
        print("  STL seasonal index not found — stl_seasonal_index will be 0.0")

    # ── 2. Load actuals panel (seed data) ────────────────────────────────────
    print("\nLoading retailer_sales_weekly.parquet …")
    df_actual = pd.read_parquet("outputs/retailer_sales_weekly.parquet")
    df_actual["__time"] = pd.to_datetime(df_actual["__time"], utc=True)

    num_cols = [c for c in features_used if c not in ("channel_outlet", "week_of_year")]
    for c in num_cols:
        if c in df_actual.columns:
            df_actual[c] = pd.to_numeric(df_actual[c], errors="coerce")

    df_actual = df_actual.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    # Keep enough trailing weeks: lag13 needs 13, YAGO (lag52) needs 52 + 13 = 65
    df_seed = (
        df_actual
        .groupby(GROUP_COLS)
        .tail(65)
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
        # total_units history (base + promo); mirrors units_history structure
        total_history = g["total_units"].fillna(g["base_units"]).tolist() if forecast_total and "total_units" in g.columns else []

        # YAGO: precompute year-ago base_units for each of the 13 forecast steps.
        # At step k (1-indexed), lag52 = actual at anchor - (52 - k) weeks.
        # Index in units_history: N_actual - 53 + k  (always an actual, never a prediction)
        N_actual  = len(units_history)
        lag52_seq = [
            float(units_history[N_actual - 53 + k])
            if 0 <= (N_actual - 53 + k) < N_actual else np.nan
            for k in range(1, FORECAST_WEEKS + 1)
        ]

        # Year-over-year ratio at the anchor point.
        # Used in the forecast loop to scale lag52_seq into a seasonal reference:
        #   seasonal_ref[k] = lag52_seq[k] * yoy_ratio
        # This projects the actual year-ago weekly curve forward, adjusted for
        # how current demand is tracking relative to last year (up/down/flat).
        _yago_anchor = float(units_history[N_actual - 52]) if N_actual >= 52 else None
        if _yago_anchor and _yago_anchor > 0:
            _anchor_units = float(units_history[-1])
            # Sanity-clamp: cap at 2× up or down to avoid outlier series blowing up
            yoy_ratio = float(np.clip(_anchor_units / _yago_anchor, 0.5, 2.0))
        else:
            yoy_ratio = None

        # Parallel YAGO seq + ratio for total_units
        N_total = len(total_history)
        if forecast_total and N_total > 0:
            lag52_total_seq = [
                float(total_history[N_total - 53 + k])
                if 0 <= (N_total - 53 + k) < N_total else np.nan
                for k in range(1, FORECAST_WEEKS + 1)
            ]
            _yago_total = float(total_history[N_total - 52]) if N_total >= 52 else None
            if _yago_total and _yago_total > 0:
                yoy_ratio_total = float(np.clip(float(total_history[-1]) / _yago_total, 0.5, 2.0))
            else:
                yoy_ratio_total = None
        else:
            lag52_total_seq = []
            yoy_ratio_total = None

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
            "arp_fallback":         int(latest.get("arp_fallback") or 0),
        }

        # MO_46 rolling signals — static seed values (last observed; held flat across horizon)
        _cp  = latest.get("rolling_cannibal_pressure")
        _ct  = latest.get("rolling_cannibal_trend")
        _re  = latest.get("rolling_elasticity")
        rolling_seed = {
            "rolling_cannibal_pressure": float(_cp) if pd.notna(_cp) else np.nan,
            "rolling_cannibal_trend":    float(_ct) if pd.notna(_ct) else np.nan,
            "rolling_elasticity":        float(_re) if pd.notna(_re) else np.nan,
        }

        # Static features (unchanged across forecast horizon)
        static_feats = {}
        skip = {"channel_outlet", "week_of_year",
                "base_units_lag1", "base_units_lag4", "base_units_lag13",
                "base_units_lag52",                          # dynamic — updated per step
                "total_units_lag1", "total_units_lag4", "total_units_lag13",
                "total_units_lag52",                         # dynamic — updated per step
                "arp_lag1", "arp_lag4", "arp_wow_delta",
                "arp_roll8_avg", "arp_roll8_std", "arp",
                # MO_46 rolling signals — held static at last observed values;
                # no autoregressive update (we don't forecast competitive dynamics)
                "rolling_cannibal_pressure", "rolling_cannibal_trend", "rolling_elasticity"}
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
            lag52 = lag52_seq[step - 1]     # precomputed from actuals — no leakage

            arp_cur  = arp_history[-1] if arp_history else forecast_arp
            arp_lag1 = arp_history[-1] if len(arp_history) >= 1 else np.nan
            arp_lag4 = arp_history[-4] if len(arp_history) >= 4 else np.nan

            # ARP rolling stats (trailing 8 prior ARP values)
            arp_window = arp_history[-8:]
            arp_roll8_avg = float(np.nanmean(arp_window)) if arp_window else np.nan
            arp_roll8_std = float(np.nanstd(arp_window))  if len(arp_window) > 1 else 0.0
            arp_wow_delta = (arp_cur - arp_lag1) if pd.notna(arp_lag1) else 0.0

            # total_units AR lags (from combined actuals + prior predictions)
            t_lag1  = total_history[-1]  if len(total_history) >= 1  else np.nan
            t_lag4  = total_history[-4]  if len(total_history) >= 4  else np.nan
            t_lag13 = total_history[-13] if len(total_history) >= 13 else np.nan
            t_lag52 = lag52_total_seq[step - 1] if lag52_total_seq else np.nan

            state = {
                **static_feats,
                **rolling_seed,             # MO_46: static competitive signals
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
                "base_units_lag52":     lag52,
                "total_units_lag1":     t_lag1,
                "total_units_lag4":     t_lag4,
                "total_units_lag13":    t_lag13,
                "total_units_lag52":    t_lag52,
            }

            X = _build_feature_row(state, features_used)

            # Models predict in log1p space — invert with expm1
            units_low  = float(np.expm1(max(0, models["q10"].predict(X)[0])))
            units_base = float(np.expm1(max(0, models["q50"].predict(X)[0])))
            units_high = float(np.expm1(max(0, models["q90"].predict(X)[0])))

            # Seasonal blend: prevent the AR collapse-to-flat problem.
            # After ~4 steps, lag1/lag4/lag13 become self-predictions and the
            # dominant AR signal drowns out lag52's weekly seasonal variation.
            # We bend each step toward a seasonal reference:
            #   seasonal_ref = this_week's_yago × yoy_ratio
            # which projects the year-ago seasonal curve forward at the current
            # year-over-year level.  All three quantiles shift by the same
            # multiplicative factor to preserve the band shape.
            if (yoy_ratio is not None and pd.notna(lag52)
                    and lag52 > 0 and units_base > 0):
                seasonal_ref = lag52 * yoy_ratio
                blend_mult = (
                    (1.0 - SEASONAL_BLEND_WEIGHT) * units_base
                    + SEASONAL_BLEND_WEIGHT * seasonal_ref
                ) / units_base
                units_low  = max(0.0, units_low  * blend_mult)
                units_base = max(0.0, units_base * blend_mult)
                units_high = max(0.0, units_high * blend_mult)

            # Layer 1 — STL seasonal index (portfolio-level pattern from MO_59).
            # Applied ONLY when the YAGO blend above did not fire (lag52 unavailable).
            # For new SKUs without a year-ago reference, this borrows the portfolio
            # seasonal curve as the sole seasonal signal — complementary to YAGO,
            # not a replacement.
            elif seasonal_lookup and units_base > 0:
                woy = int(forecast_date.isocalendar().week)
                stl_idx = seasonal_lookup.get(woy, 0.0)
                if stl_idx != 0.0:
                    stl_mult = max(0.1, 1.0 + stl_idx)
                    units_low  = max(0.0, units_low  * stl_mult)
                    units_base = max(0.0, units_base * stl_mult)
                    units_high = max(0.0, units_high * stl_mult)

            # Feed blended q50 back as next step's lag seed (keeps AR and
            # seasonal blend consistent across the full 13-step horizon)
            units_history.append(units_base)
            arp_history.append(arp_cur)  # hold ARP flat (no external signal yet)

            # ── Parallel total_units forecast ────────────────────────────────
            total_low = total_base = total_high = None
            if forecast_total and features_used_total:
                X_t = _build_feature_row(state, features_used_total)
                total_low  = float(np.expm1(max(0, models_total["q10"].predict(X_t)[0])))
                total_base = float(np.expm1(max(0, models_total["q50"].predict(X_t)[0])))
                total_high = float(np.expm1(max(0, models_total["q90"].predict(X_t)[0])))
                if (yoy_ratio_total is not None and pd.notna(t_lag52)
                        and t_lag52 > 0 and total_base > 0):
                    s_ref_t = t_lag52 * yoy_ratio_total
                    bm_t = ((1.0 - SEASONAL_BLEND_WEIGHT) * total_base
                            + SEASONAL_BLEND_WEIGHT * s_ref_t) / total_base
                    total_low  = max(0.0, total_low  * bm_t)
                    total_base = max(0.0, total_base * bm_t)
                    total_high = max(0.0, total_high * bm_t)
                # Coherence clamp: total_units >= base_units (promo units cannot be negative)
                if total_low  is not None: total_low  = max(total_low,  units_low)
                if total_base is not None: total_base = max(total_base, units_base)
                if total_high is not None: total_high = max(total_high, units_high)
                total_history.append(total_base)

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
                "forecast_total_units_low":  total_low,
                "forecast_total_units_base": total_base,
                "forecast_total_units_high": total_high,
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
    if forecast_total and "forecast_total_units_base" in out.columns and out["forecast_total_units_base"].notna().any():
        print(f"  q50 total_units range: {out['forecast_total_units_base'].min():.0f} – {out['forecast_total_units_base'].max():.0f}")
        promo_est = out["forecast_total_units_base"] - out["forecast_units_base"]
        print(f"  Median promo contribution: {promo_est.median():.0f} units/week")

    if out.empty:
        print("No rows to write.")
    else:
        out.to_parquet("outputs/retailer_sales_forecast.parquet", index=False)
        print("  Saved → outputs/retailer_sales_forecast.parquet")
        write_back(out, "retailer_sales_forecast", timestamp_col="__time")
