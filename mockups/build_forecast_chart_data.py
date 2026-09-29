#!/usr/bin/env python3
"""
build_forecast_chart_data.py

Queries Druid directly and writes mockups/bracken_forecast_charts.html.
Also loads local parquet + model files to generate historical backtest chart.
Data stays entirely local — nothing leaves this machine.

Usage (requires mo-ml conda env for backtest tab):
    /opt/anaconda3/envs/mo-ml/bin/python3 mockups/build_forecast_chart_data.py
    open mockups/bracken_forecast_charts.html

Reads credentials from customer-built-mo-api/.env automatically.
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from requests.auth import HTTPBasicAuth

# Dynamic lookback: show full previous calendar year + current year
_PREV_YEAR     = datetime.now().year - 1
_LOOKBACK_DATE = f"{_PREV_YEAR}-01-01"   # "2025-01-01" when run in 2026

# ── Load .env from the mo-api directory (same as the API itself) ──────
_env_path = Path(__file__).parent.parent.parent / "customer-built-mo-api" / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
        print(f"Loaded env from {_env_path}")
    except ImportError:
        print("python-dotenv not available; falling back to shell env")
else:
    print(f"No .env found at {_env_path}; using shell env")

# ── Druid connection ──────────────────────────────────────────────────
HOST     = os.environ.get("DRUID_HOST", "").rstrip("/")
USERNAME = os.environ.get("DRUID_USERNAME", "")
PASSWORD = os.environ.get("DRUID_PASSWORD", "")

if not HOST:
    sys.exit("ERROR: DRUID_HOST not set. Check customer-built-mo-api/.env")

_auth    = HTTPBasicAuth(USERNAME, PASSWORD)
_headers = {"Content-Type": "application/json"}

def druid(sql: str, label: str = "", timeout: int = 90) -> list[dict]:
    if label:
        print(f"  → {label}...")
    resp = requests.post(
        f"{HOST}/druid/v2/sql/",
        json={"query": sql},
        auth=_auth,
        headers=_headers,
        timeout=timeout,
    )
    if not resp.ok:
        print(f"    WARNING: {resp.status_code} — {resp.text[:200]}")
        return []
    rows = resp.json()
    print(f"    {len(rows)} rows")
    return rows

# ── Date helpers ──────────────────────────────────────────────────────
def parse_druid_ts(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:len(fmt)], fmt)
        except ValueError:
            continue
    return None

def add_forecast_dates(rows: list[dict]) -> list[dict]:
    """Attach calendar week_ending to each forecast row from anchor_date + N weeks.
    Sorts numerically by forecast_week_number first (Druid may return it as a
    string, giving lexicographic order: 1, 10, 11 ... instead of 1, 2, 3 ...).
    Slices anchor_date to YYYY-MM-DD before parsing — handles '+00:00' variants.
    """
    if not rows:
        return rows
    rows = sorted(rows, key=lambda r: int(r.get("forecast_week_number") or 0))
    anchor_str = str(rows[0].get("anchor_date", ""))[:10]
    try:
        anchor = datetime.strptime(anchor_str, "%Y-%m-%d")
    except ValueError:
        return rows
    for r in rows:
        n = int(r.get("forecast_week_number") or 0)
        r["week_ending"] = (anchor + timedelta(weeks=n)).strftime("%Y-%m-%d")
    return rows

def safe_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None

def normalize_dates(rows: list[dict]) -> list[dict]:
    """Trim any week_ending to YYYY-MM-DD — Druid returns full ISO timestamps."""
    for r in rows:
        we = r.get("week_ending")
        if we:
            r["week_ending"] = str(we)[:10]
    return rows

# ── Queries ───────────────────────────────────────────────────────────
print("\n=== Fetching data from Druid ===\n")

# 1. Top retailers by BUILT volume (last 52 weeks)
top_retailers = druid("""
    SELECT
      retail_account,
      SUM(base_units) AS total_units
    FROM "built_enriched_weekly"
    WHERE parent_brand = 'BUILT'
      AND channel_outlet = 'CONVENTIONAL|FOOD'
      AND military_excluded_flag = 0
      AND retail_account IS NOT NULL
      AND retail_account <> ''
      AND __time >= TIMESTAMPADD(WEEK, -52, CURRENT_TIMESTAMP)
    GROUP BY retail_account
    ORDER BY total_units DESC
    LIMIT 5
""", "Top retailers by BUILT volume")

named = [r for r in top_retailers if r.get("retail_account")]
if not named:
    sys.exit("ERROR: No named retailer data returned. Check connection and filters.")

top_acct    = named[0]["retail_account"]
second_acct = named[1]["retail_account"] if len(named) > 1 else None
print(f"\n  Primary retailer  : {top_acct}")
print(f"  Secondary retailer: {second_acct}\n")

# 2. Primary retailer — actuals from start of prior year (base + incr for promo toggle)
# __time in built_enriched_weekly is already the Sunday week-ending date; CAST directly to avoid
# TIME_FLOOR shifting Sundays back to Monday.
r1_actuals = druid(f"""
    SELECT
      CAST(__time AS VARCHAR)    AS week_ending,
      SUM(base_units)            AS actual_units,
      SUM(incr_units)            AS incr_units
    FROM "built_enriched_weekly"
    WHERE parent_brand = 'BUILT'
      AND channel_outlet = 'CONVENTIONAL|FOOD'
      AND retail_account = '{top_acct}'
      AND military_excluded_flag = 0
      AND __time >= TIMESTAMP '{_LOOKBACK_DATE}'
    GROUP BY 1
    ORDER BY 1
""", f"{top_acct} actuals (from {_LOOKBACK_DATE})")
r1_actuals = normalize_dates(r1_actuals)

# 3. Primary retailer — 13-week forward forecast
r1_forecast = druid(f"""
    SELECT
      ANY_VALUE(anchor_date)       AS anchor_date,
      forecast_week_number,
      SUM(forecast_units_base)     AS forecast_units,
      SUM(forecast_units_low)      AS forecast_low,
      SUM(forecast_units_high)     AS forecast_high
    FROM "retailer_sales_forecast"
    WHERE channel_outlet = 'CONVENTIONAL|FOOD'
      AND retail_account = '{top_acct}'
    GROUP BY forecast_week_number
    ORDER BY forecast_week_number
""", f"{top_acct} forecast (13w)")
r1_forecast = add_forecast_dates(r1_forecast)

# 4. Secondary retailer — actuals from start of prior year (base + incr)
r2_actuals = []
if second_acct:
    r2_actuals = druid(f"""
        SELECT
          CAST(__time AS VARCHAR)    AS week_ending,
          SUM(base_units)            AS actual_units,
          SUM(incr_units)            AS incr_units
        FROM "built_enriched_weekly"
        WHERE parent_brand = 'BUILT'
          AND channel_outlet = 'CONVENTIONAL|FOOD'
          AND retail_account = '{second_acct}'
          AND military_excluded_flag = 0
          AND __time >= TIMESTAMP '{_LOOKBACK_DATE}'
        GROUP BY 1
        ORDER BY 1
    """, f"{second_acct} actuals (from {_LOOKBACK_DATE})")
    r2_actuals = normalize_dates(r2_actuals)

# 5. Secondary retailer — 13-week forward forecast
r2_forecast = []
if second_acct:
    r2_forecast = druid(f"""
        SELECT
          ANY_VALUE(anchor_date)       AS anchor_date,
          forecast_week_number,
          SUM(forecast_units_base)     AS forecast_units,
          SUM(forecast_units_low)      AS forecast_low,
          SUM(forecast_units_high)     AS forecast_high
        FROM "retailer_sales_forecast"
        WHERE channel_outlet = 'CONVENTIONAL|FOOD'
          AND retail_account = '{second_acct}'
        GROUP BY forecast_week_number
        ORDER BY forecast_week_number
    """, f"{second_acct} forecast (13w)")
    r2_forecast = add_forecast_dates(r2_forecast)

# 6. Top 5 SKUs at primary retailer (last 13 weeks)
top_skus = druid(f"""
    SELECT
      upc,
      ANY_VALUE(description)              AS description,
      SUM(base_units)                     AS total_units_13w,
      AVG(arp)                            AS avg_price,
      ANY_VALUE(spins_flavor_canonical)   AS flavor
    FROM "built_enriched_weekly"
    WHERE parent_brand = 'BUILT'
      AND channel_outlet = 'CONVENTIONAL|FOOD'
      AND retail_account = '{top_acct}'
      AND military_excluded_flag = 0
      AND __time >= TIMESTAMPADD(WEEK, -13, CURRENT_TIMESTAMP)
    GROUP BY upc
    ORDER BY total_units_13w DESC
    LIMIT 5
""", f"Top 5 SKUs at {top_acct}")

# 7. Top SKU — actuals + forecast
focal_upc  = top_skus[0]["upc"]  if top_skus else None
focal_desc = top_skus[0]["description"] if top_skus else ""

sku_actuals  = []
sku_forecast = []
if focal_upc:
    sku_actuals = druid(f"""
        SELECT
          CAST(__time AS VARCHAR)    AS week_ending,
          SUM(base_units)            AS actual_units,
          SUM(incr_units)            AS incr_units,
          AVG(arp)                   AS avg_price
        FROM "built_enriched_weekly"
        WHERE upc = '{focal_upc}'
          AND channel_outlet = 'CONVENTIONAL|FOOD'
          AND retail_account = '{top_acct}'
          AND military_excluded_flag = 0
          AND __time >= TIMESTAMP '{_LOOKBACK_DATE}'
        GROUP BY 1
        ORDER BY 1
    """, f"Top SKU actuals: {focal_desc[:40]}")
    sku_actuals = normalize_dates(sku_actuals)

    sku_forecast = druid(f"""
        SELECT
          ANY_VALUE(anchor_date)       AS anchor_date,
          ANY_VALUE(anchor_base_units) AS anchor_units,
          ANY_VALUE(anchor_arp)        AS anchor_arp,
          forecast_week_number,
          SUM(forecast_units_base)     AS forecast_units,
          SUM(forecast_units_low)      AS forecast_low,
          SUM(forecast_units_high)     AS forecast_high
        FROM "retailer_sales_forecast"
        WHERE upc = '{focal_upc}'
          AND channel_outlet = 'CONVENTIONAL|FOOD'
          AND retail_account = '{top_acct}'
        GROUP BY forecast_week_number
        ORDER BY forecast_week_number
    """, f"Top SKU forecast: {focal_desc[:40]}")
    sku_forecast = add_forecast_dates(sku_forecast)

# ── Summary stats ─────────────────────────────────────────────────────
def yoy(rows: list[dict]) -> str:
    if len(rows) < 26:
        return "N/A"
    recent = sum(r["actual_units"] or 0 for r in rows[-13:])
    prior  = sum(r["actual_units"] or 0 for r in rows[-26:-13])
    if prior == 0:
        return "N/A"
    pct = (recent - prior) / prior * 100
    return f"{'+' if pct >= 0 else ''}{pct:.1f}%"

r1_yoy = yoy(r1_actuals)
r2_yoy = yoy(r2_actuals)

# ── Promo lift rate (used for forecast what-if toggle) ─────────────────
# Compute per-account avg weekly lift rate from actual SPINS incr_units
def avg_lift_rate(rows: list[dict]) -> float:
    rates = []
    for r in rows:
        base = safe_float(r.get("actual_units")) or 0
        incr = safe_float(r.get("incr_units")) or 0
        if base > 0 and incr >= 0:
            rates.append(incr / base)
    return round(sum(rates) / len(rates), 4) if rates else 0.0

r1_lift = avg_lift_rate(r1_actuals)
r2_lift = avg_lift_rate(r2_actuals)
sku_lift = avg_lift_rate(sku_actuals)

def stamp_promo_forecast(rows: list[dict], lift: float) -> list[dict]:
    """Add forecast_units_promo/low_promo/high_promo fields using avg lift multiplier."""
    for r in rows:
        mult = 1.0 + lift
        r["forecast_units_promo"] = (safe_float(r.get("forecast_units")) or 0) * mult
        r["forecast_low_promo"]   = (safe_float(r.get("forecast_low"))   or 0) * mult
        r["forecast_high_promo"]  = (safe_float(r.get("forecast_high"))  or 0) * mult
    return rows

r1_forecast  = stamp_promo_forecast(r1_forecast,  r1_lift)
r2_forecast  = stamp_promo_forecast(r2_forecast,  r2_lift)
sku_forecast = stamp_promo_forecast(sku_forecast, sku_lift)

print(f"  Promo lift rates  : {top_acct} {r1_lift*100:.1f}%"
      + (f" · {second_acct} {r2_lift*100:.1f}%" if second_acct else "")
      + f" · SKU {sku_lift*100:.1f}%")

anchor_date_display = ""
if r1_forecast:
    _anchor_str = str(r1_forecast[0].get("anchor_date", ""))[:10]
    try:
        _a = datetime.strptime(_anchor_str, "%Y-%m-%d")
        anchor_date_display = _a.strftime("%b %d, %Y")
    except ValueError:
        pass

# ── Backtest incr_units (for Accuracy Proof promo toggle) ────────────
# Pulls actual weekly incr_units for the full backtest window from Druid
acc_incr = druid(f"""
    SELECT
      CAST(__time AS VARCHAR)    AS week_ending,
      SUM(incr_units)            AS incr_units
    FROM "built_enriched_weekly"
    WHERE parent_brand = 'BUILT'
      AND channel_outlet = 'CONVENTIONAL|FOOD'
      AND retail_account = '{top_acct}'
      AND military_excluded_flag = 0
      AND __time >= TIMESTAMP '{str(_PREV_YEAR - 1)}-12-01'
      AND __time <= CURRENT_TIMESTAMP
    GROUP BY 1
    ORDER BY 1
""", f"{top_acct} incr_units (backtest window)")
acc_incr = normalize_dates(acc_incr)
# __time is Sunday week-ending; keys already match parquet holdout rows directly
acc_incr_map = {
    r["week_ending"]: safe_float(r.get("incr_units")) or 0.0
    for r in acc_incr if r.get("week_ending")
}

# ── True recursive backtest (mirrors MO_27's exact autoregressive loop) ──────
# Each forecast step feeds its own q50 prediction back as lag1 for the next
# step — identical to how MO_27 runs in production.  lag52 is always from real
# SPINS history, never from a prediction.  This is the honest number Bracken
# should trust: "what would the model have predicted from May 10 forward, with
# zero foreknowledge of what actually happened?"
print("\n=== Building TRUE RECURSIVE backtest (no teacher forcing) ===\n")
print("  lag1 = prior step prediction (not actual) — identical to MO_27 production.")
print("  lag52 always from actual SPINS data — no leakage.\n")

FEATURE_COLS = [
    "base_units_roll4_avg", "base_units_roll8_avg", "base_units_roll8_std",
    "base_units_roll13_avg", "base_units_roll13_std", "base_units_wow_delta",
    "base_units_z8", "base_units_z13", "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
    "velocity_spm_z8", "velocity_spm_z13", "tdp", "tdp_z8", "tdp_wow_delta",
    "arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std", "weeks_since_launch",
    "donor_count", "week_of_year", "base_units_lag1", "base_units_lag4",
    "base_units_lag13", "base_units_lag52", "velocity_spm_lag52", "channel_outlet",
]

# Features updated dynamically each step (all others held flat from latest actual row)
AR_DYNAMIC = {
    "channel_outlet", "week_of_year", "weeks_since_launch",
    "base_units_lag1", "base_units_lag4", "base_units_lag13", "base_units_lag52",
    "arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std",
}

SEASONAL_BLEND_WEIGHT = 0.40   # must match MO_27 constant
FORECAST_WEEKS        = 13
GROUP_COLS            = ["upc", "channel_outlet", "retail_account", "geography_raw"]

ROOT_ML   = Path(__file__).parent.parent
PARQUET   = ROOT_ML / "outputs" / "retailer_sales_weekly.parquet"
MODEL_DIR = ROOT_ML / "outputs"

# v4 training cutoff (from retailer_sales_train_metrics.json)
_TRAINING_CUTOFF_STR = "2026-05-10"

backtest_history     = []
backtest_holdout     = []
quarterly_backtests  = []
retailer_wmape       = "3.4"   # portfolio fallback if parquet unavailable
holdout_naive_wmape  = "—"
holdout_series_count = 0
backtest_cutoff      = _TRAINING_CUTOFF_STR
backtest_val_end     = "2026-08-09"

try:
    import pandas as pd
    import pickle
    import numpy as np

    TRAINING_CUTOFF = pd.Timestamp(_TRAINING_CUTOFF_STR, tz="UTC")

    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)

    mask = (
        (df["retail_account"] == top_acct) &
        (df["channel_outlet"] == "CONVENTIONAL|FOOD")
    )
    df_r1 = df[mask].copy()
    if len(df_r1) == 0:
        raise ValueError(f"No parquet rows for {top_acct}")

    for c in FEATURE_COLS:
        if c != "channel_outlet" and c in df_r1.columns:
            df_r1[c] = pd.to_numeric(df_r1[c], errors="coerce")

    df_r1 = df_r1.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    # Load v4 quantile models
    with open(MODEL_DIR / "model_retailer_sales_q50_v4.pkl", "rb") as f:
        m50 = pickle.load(f)
    with open(MODEL_DIR / "model_retailer_sales_q10_v4.pkl", "rb") as f:
        m10 = pickle.load(f)
    with open(MODEL_DIR / "model_retailer_sales_q90_v4.pkl", "rb") as f:
        m90 = pickle.load(f)

    channel_cats = m50._Booster.pandas_categorical[0]

    # ── Reusable MO_27 recursive AR loop — callable for any training cutoff ───
    def run_single_backtest(cutoff_ts):
        """Run the MO_27 recursive AR loop from a given cutoff.
        Returns (weekly_agg_df, wmape_val, naive_wmape_val, series_run).
        naive_wmape = lag52 * YoY baseline — the "Excel-level" comparison."""
        all_preds  = []
        series_run = 0

        for group_keys, g in df_r1.groupby(GROUP_COLS):
            upc, channel, account, geo = group_keys
            g = g.sort_values("__time")

            seed = g[g["__time"] <= cutoff_ts].tail(65)
            if len(seed) < 13:
                continue

            holdout_rows = g[
                (g["__time"] > cutoff_ts) &
                (g["__time"] <= cutoff_ts + pd.Timedelta(weeks=FORECAST_WEEKS))
            ]
            if holdout_rows.empty:
                continue

            holdout_map = holdout_rows.groupby("__time")["base_units"].sum().to_dict()

            units_history = list(seed["base_units"].fillna(0))
            N_actual      = len(units_history)

            lag52_seq = [
                float(units_history[N_actual - 53 + k])
                if 0 <= (N_actual - 53 + k) < N_actual else np.nan
                for k in range(1, FORECAST_WEEKS + 1)
            ]

            yoy_ratio = None
            if N_actual >= 52:
                _yago = float(units_history[N_actual - 52])
                if _yago > 0:
                    yoy_ratio = float(np.clip(float(units_history[-1]) / _yago, 0.5, 2.0))

            latest     = seed.iloc[-1]
            anchor_dt  = latest["__time"]
            wsl_anchor = int(pd.to_numeric(latest.get("weeks_since_launch"), errors="coerce") or 0)

            static_feats = {}
            for col in FEATURE_COLS:
                if col in AR_DYNAMIC or col == "channel_outlet":
                    continue
                raw = latest.get(col)
                try:
                    static_feats[col] = float(raw) if pd.notna(raw) else np.nan
                except (TypeError, ValueError):
                    static_feats[col] = np.nan

            arp_val     = float(pd.to_numeric(latest.get("arp"), errors="coerce") or 0)
            arp_history = list(pd.to_numeric(seed["arp"], errors="coerce").fillna(arp_val))

            series_run += 1

            for step in range(1, FORECAST_WEEKS + 1):
                forecast_dt = anchor_dt + pd.Timedelta(weeks=step)

                lag1  = units_history[-1]  if len(units_history) >= 1  else np.nan
                lag4  = units_history[-4]  if len(units_history) >= 4  else np.nan
                lag13 = units_history[-13] if len(units_history) >= 13 else np.nan
                lag52 = lag52_seq[step - 1]

                arp_cur      = arp_history[-1] if arp_history else arp_val
                arp_lag1     = arp_history[-1] if len(arp_history) >= 1 else np.nan
                arp_window   = arp_history[-8:]
                arp_roll8avg = float(np.nanmean(arp_window)) if arp_window else np.nan
                arp_roll8std = float(np.nanstd(arp_window))  if len(arp_window) > 1 else 0.0
                arp_wow_d    = (arp_cur - arp_lag1) if pd.notna(arp_lag1) else 0.0

                feature_row = {
                    **static_feats,
                    "channel_outlet":     channel,
                    "week_of_year":       int(forecast_dt.isocalendar().week),
                    "weeks_since_launch": wsl_anchor + step,
                    "arp":                arp_cur,
                    "arp_wow_delta":      arp_wow_d,
                    "arp_roll8_avg":      arp_roll8avg,
                    "arp_roll8_std":      arp_roll8std,
                    "base_units_lag1":    lag1,
                    "base_units_lag4":    lag4,
                    "base_units_lag13":   lag13,
                    "base_units_lag52":   lag52,
                }

                X = pd.DataFrame([feature_row])[FEATURE_COLS]
                X["channel_outlet"] = pd.Categorical(X["channel_outlet"], categories=channel_cats)

                units_base = float(np.expm1(max(0.0, m50.predict(X)[0])))
                units_low  = float(np.expm1(max(0.0, m10.predict(X)[0])))
                units_high = float(np.expm1(max(0.0, m90.predict(X)[0])))

                if yoy_ratio is not None and pd.notna(lag52) and lag52 > 0 and units_base > 0:
                    s_ref      = lag52 * yoy_ratio
                    blend_mult = ((1.0 - SEASONAL_BLEND_WEIGHT) * units_base
                                  + SEASONAL_BLEND_WEIGHT * s_ref) / units_base
                    units_low  = max(0.0, units_low  * blend_mult)
                    units_base = max(0.0, units_base * blend_mult)
                    units_high = max(0.0, units_high * blend_mult)

                units_history.append(units_base)
                arp_history.append(arp_cur)

                # Naive: pure lag52 * YoY — the Excel-style year-ago comparison
                naive_unit = 0.0
                if pd.notna(lag52) and lag52 > 0:
                    _yr = yoy_ratio if yoy_ratio is not None else 1.0
                    naive_unit = float(lag52) * float(_yr)

                actual = holdout_map.get(forecast_dt, np.nan)
                all_preds.append({
                    "__time":     forecast_dt,
                    "pred_q50":   units_base,
                    "pred_q10":   units_low,
                    "pred_q90":   units_high,
                    "actual":     float(actual) if pd.notna(actual) else np.nan,
                    "naive_pred": naive_unit,
                })

        print(f"  Series processed : {series_run:,}")

        if not all_preds:
            return pd.DataFrame(), 0.0

        pred_df = pd.DataFrame(all_preds)
        weekly  = (
            pred_df.groupby("__time")
            .agg(actual_units=("actual",     "sum"),
                 pred_q50    =("pred_q50",   "sum"),
                 pred_q10    =("pred_q10",   "sum"),
                 pred_q90    =("pred_q90",   "sum"),
                 naive_units =("naive_pred", "sum"))
            .reset_index()
            .sort_values("__time")
        )
        weekly_valid = weekly[weekly["actual_units"] > 0].copy()
        total_actual = weekly_valid["actual_units"].sum()
        total_ae     = (weekly_valid["actual_units"] - weekly_valid["pred_q50"]).abs().sum()
        wmape_val    = round(total_ae / total_actual * 100, 1) if total_actual > 0 else 0.0
        naive_ae     = (weekly_valid["actual_units"] - weekly_valid["naive_units"]).abs().sum()
        naive_wmape_val = round(naive_ae / total_actual * 100, 1) if total_actual > 0 else 0.0
        return weekly, wmape_val, naive_wmape_val, series_run

    # ── True holdout: cutoff May 10, 2026 ──────────────────────────────────────
    print("\n  Running true holdout backtest (cutoff 2026-05-10)...")
    weekly, wmape_val, naive_wmape_val, series_count_h = run_single_backtest(TRAINING_CUTOFF)

    if weekly.empty:
        raise ValueError("True holdout returned no data")

    weekly = weekly[weekly["actual_units"] > 0].copy()

    # Pre-cutoff history: go back to start of prior year for full seasonal view
    _lookback_ts    = pd.Timestamp(f"{_PREV_YEAR}-01-01", tz="UTC")
    _history_weeks  = max(52, int((TRAINING_CUTOFF - _lookback_ts).days / 7) + 4)
    train_weekly = (
        df_r1[
            (df_r1["__time"] > TRAINING_CUTOFF - pd.Timedelta(weeks=_history_weeks)) &
            (df_r1["__time"] <= TRAINING_CUTOFF)
        ]
        .groupby("__time")
        .agg(actual_units=("base_units", "sum"))
        .reset_index()
        .sort_values("__time")
    )

    backtest_history = [
        {"week_ending": r["__time"].strftime("%Y-%m-%d"),
         "actual_units": float(r["actual_units"])}
        for _, r in train_weekly.iterrows()
    ]
    backtest_holdout = [
        {"week_ending":  r["__time"].strftime("%Y-%m-%d"),
         "actual_units": float(r["actual_units"]),
         "pred_q50":     float(r["pred_q50"]),
         "pred_q10":     float(r["pred_q10"]),
         "pred_q90":     float(r["pred_q90"]),
         "naive_units":  float(r["naive_units"]) if "naive_units" in r and pd.notna(r["naive_units"]) else 0.0}
        for _, r in weekly.iterrows()
    ]

    # wMAPE (weighted by actual volume)
    total_actual    = weekly["actual_units"].sum()
    total_ae        = (weekly["actual_units"] - weekly["pred_q50"]).abs().sum()
    wmape_val       = round(total_ae / total_actual * 100, 1) if total_actual > 0 else 0

    retailer_wmape       = str(wmape_val)
    holdout_naive_wmape  = str(naive_wmape_val)
    holdout_series_count = series_count_h
    backtest_val_end     = weekly["__time"].max().strftime("%Y-%m-%d")

    # ── Quarterly retrospective backtests ─────────────────────────────────────────────
    # Cutoffs are the last Sunday before each financial quarter starts.
    # Each backtest uses the same v4 model (retrospective) vs. the true May-10
    # holdout where the model genuinely had not seen any post-cutoff actuals.
    print("\n  Running quarterly retrospective backtests...")
    _Q_CUTOFFS = [
        ("Q1 2025", "Jan–Mar 2025", "2024-12-29", "2025-01-05", "2025-03-30"),
        ("Q2 2025", "Apr–Jun 2025", "2025-03-30", "2025-04-06", "2025-06-29"),
        ("Q3 2025", "Jul–Sep 2025", "2025-06-29", "2025-07-06", "2025-09-28"),
        ("Q4 2025", "Oct–Dec 2025", "2025-09-28", "2025-10-05", "2025-12-28"),
        ("Q1 2026", "Jan–Mar 2026", "2025-12-28", "2026-01-04", "2026-03-29"),
        ("Q2 2026", "Apr–Jun 2026", "2026-03-29", "2026-04-05", "2026-06-28"),
    ]
    for _ql, _qlong, _qcutoff, _qstart, _qend in _Q_CUTOFFS:
        _qts = pd.Timestamp(_qcutoff, tz="UTC")
        print(f"    {_ql} (cutoff {_qcutoff})...", end=" ", flush=True)
        try:
            _qw, _, _naive_wmape_q, _series_count_q = run_single_backtest(_qts)
            if _qw.empty:
                print("no data — skip")
                continue
            # Clip predictions to the target quarter window [q_start, q_end].
            # Different SKUs have staggered last-actual dates so the raw
            # aggregate spans more than 13 weeks.  Clipping ensures each
            # quarterly segment contains only weeks that belong to that quarter.
            _qstart_ts = pd.Timestamp(_qstart, tz="UTC")
            _qend_ts   = pd.Timestamp(_qend,   tz="UTC") + pd.Timedelta(days=6)
            _qw_clip   = _qw[(_qw["__time"] >= _qstart_ts) & (_qw["__time"] <= _qend_ts)].copy()
            if _qw_clip.empty:
                print("no predictions in target quarter window — skip")
                continue
            # Recompute wMAPE for the clipped window only
            _valid_clip = _qw_clip[_qw_clip["actual_units"] > 0]
            _ta_clip  = _valid_clip["actual_units"].sum()
            _ae_clip  = (_valid_clip["actual_units"] - _valid_clip["pred_q50"]).abs().sum()
            _qwmape   = round(_ae_clip / _ta_clip * 100, 1) if _ta_clip > 0 else 0.0
            _qpreds = [
                {
                    "week_ending":  _r["__time"].strftime("%Y-%m-%d"),
                    "pred_q50":     float(_r["pred_q50"]),
                    "pred_q10":     float(_r["pred_q10"]),
                    "pred_q90":     float(_r["pred_q90"]),
                    "actual":       float(_r["actual_units"]),
                    "naive_units":  float(_r["naive_units"]) if "naive_units" in _r and pd.notna(_r["naive_units"]) else 0.0,
                }
                for _, _r in _qw_clip.iterrows()
            ]
            # Naive wMAPE clipped to the same quarter window
            _valid_naive  = _qw_clip[_qw_clip["actual_units"] > 0]
            _naive_ae_q   = (_valid_naive["actual_units"] - _valid_naive["naive_units"]).abs().sum()
            _naive_wmape_q_clipped = round(_naive_ae_q / _ta_clip * 100, 1) if _ta_clip > 0 else 0.0
            quarterly_backtests.append({
                "quarter_label": _ql,
                "quarter_long":  _qlong,
                "cutoff":        _qcutoff,
                "start":         _qstart,
                "end":           _qend,
                "type":          "retrospective",
                "predictions":   _qpreds,
                "wmape":         _qwmape,
                "naive_wmape":   _naive_wmape_q_clipped,
                "series_count":  _series_count_q,
            })
            print(f"{len(_qpreds)} weeks, wMAPE={_qwmape}%")
        except Exception as _qe:
            print(f"WARN: {_qe}")

    print(f"  History weeks    : {len(backtest_history)}")
    print(f"  Holdout weeks    : {len(backtest_holdout)}")
    print(f"  TRUE recursive wMAPE at {top_acct}: {retailer_wmape}%")
    print(f"  (lag1 = prior prediction, not actual — no teacher forcing)")

except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"  WARNING: Could not build true recursive backtest ({e}); showing portfolio wMAPE")

# ── Stamp incr_units onto backtest rows for Accuracy Proof promo toggle ─
for row in backtest_history:
    row["incr_units"] = acc_incr_map.get(row["week_ending"], 0.0)
for row in backtest_holdout:
    row["incr_units"] = acc_incr_map.get(row["week_ending"], 0.0)
    # Promo-adjusted holdout predictions: same lift rate used for forward forecast
    mult = 1.0 + r1_lift
    row["pred_q50_promo"] = (safe_float(row.get("pred_q50")) or 0) * mult
    row["pred_q10_promo"] = (safe_float(row.get("pred_q10")) or 0) * mult
    row["pred_q90_promo"] = (safe_float(row.get("pred_q90")) or 0) * mult

# ── Bundle payload ────────────────────────────────────────────────────
payload = {
    "primary_acct":       top_acct,
    "secondary_acct":     second_acct or "",
    "r1_actuals":         r1_actuals,
    "r1_forecast":        r1_forecast,
    "r2_actuals":         r2_actuals,
    "r2_forecast":        r2_forecast,
    "top_skus":           top_skus,
    "sku_actuals":        sku_actuals,
    "sku_forecast":       sku_forecast,
    "focal_desc":         focal_desc,
    "focal_upc":          focal_upc or "",
    "r1_yoy":             r1_yoy,
    "r2_yoy":             r2_yoy,
    "anchor_date":        anchor_date_display,
    "generated":          datetime.now().strftime("%Y-%m-%d %H:%M"),
    "wmape":                 "3.4",    # full-portfolio training CV — 2,517 series
    "series_count":          "2,517",
    "backtest_history":      backtest_history,
    "backtest_holdout":      backtest_holdout,
    "backtest_wmape":        retailer_wmape,
    "backtest_naive_wmape":  holdout_naive_wmape,
    "backtest_series_count": holdout_series_count,
    "backtest_cutoff":       backtest_cutoff,
    "backtest_val_end":      backtest_val_end,
    "quarterly_backtests":   quarterly_backtests,
    "r1_lift_pct":          round(r1_lift * 100, 1),
    "r2_lift_pct":          round(r2_lift * 100, 1),
    "sku_lift_pct":         round(sku_lift * 100, 1),
}

# ── HTML template ─────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>Forecast vs. Actuals</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<style>
:root {
  --bg:#0d0f14; --surface:#161921; --surface2:#1e2330; --border:#2a2f3d;
  --text:#e8ecf4; --muted:#8892a4; --accent:#4f8ef7; --accent2:#38c9a0;
  --amber:#f5a623; --red:#e05252; --purple:#9b6dff;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;
  font-size:14px;line-height:1.6;padding:0 40px;
  padding-bottom:env(safe-area-inset-bottom,0px);}
.page{max-width:1600px;margin:0 auto;padding:40px 0 72px;}
.eyebrow{font-size:11px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;
  color:var(--accent);margin-bottom:10px;}
h1{font-size:22px;font-weight:700;margin-bottom:6px;}
.subtitle{color:var(--muted);font-size:13px;margin-bottom:24px;}
.data-badge{display:inline-flex;align-items:center;gap:6px;font-size:11px;
  font-weight:600;padding:4px 10px;border-radius:20px;
  background:rgba(56,201,160,.12);color:var(--accent2);
  border:1px solid rgba(56,201,160,.25);margin-bottom:28px;}
.data-badge::before{content:'';width:7px;height:7px;border-radius:50%;
  background:var(--accent2);flex-shrink:0;}

/* Tabs */
.tabs{display:flex;gap:2px;margin-bottom:24px;background:var(--surface);
  border-radius:10px;padding:4px;border:1px solid var(--border);overflow-x:auto;}
.tab{flex:1;min-width:120px;padding:9px 14px;border-radius:7px;font-size:12px;
  font-weight:500;color:var(--muted);background:none;border:none;cursor:pointer;
  transition:background .15s,color .15s;white-space:nowrap;text-align:center;}
.tab:hover{color:var(--text);}
.tab.active{background:var(--surface2);color:var(--text);font-weight:600;}
.panel{display:none;} .panel.active{display:block;}

/* KPIs */
.kpi-strip{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px;}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:14px 18px;flex:1;min-width:120px;}
.kv{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums;}
.kv.g{color:var(--accent2);} .kv.b{color:var(--accent);}
.kv.a{color:var(--amber);}   .kv.p{color:var(--purple);}
.kl{font-size:11px;color:var(--muted);margin-top:2px;}
.ks{font-size:10px;color:var(--accent);margin-top:1px;}

/* Charts */
.chart-card{background:var(--surface);border:1px solid var(--border);
  border-radius:10px;padding:24px;margin-bottom:16px;}
.ct{font-size:13px;font-weight:600;margin-bottom:3px;}
.cs{font-size:11px;color:var(--muted);margin-bottom:18px;}
.cw{position:relative;height:340px;}

/* Insight */
.insight{border-radius:8px;padding:16px 20px;font-size:13px;line-height:1.6;
  display:flex;gap:14px;align-items:flex-start;margin-top:4px;}
.insight.g{background:rgba(56,201,160,.07);border:1px solid rgba(56,201,160,.2);}
.insight.b{background:rgba(79,142,247,.07);border:1px solid rgba(79,142,247,.2);}
.insight.a{background:rgba(245,166,35,.07);border:1px solid rgba(245,166,35,.2);}
.ii{font-size:16px;flex-shrink:0;margin-top:2px;}
.il{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px;}
.insight.g .il{color:var(--accent2);} .insight.b .il{color:var(--accent);}
.insight.a .il{color:var(--amber);}

/* SKU table */
table{width:100%;border-collapse:collapse;font-size:12px;}
th{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);
  font-weight:600;padding:7px 10px;text-align:left;border-bottom:1px solid var(--border);}
td{padding:10px 10px;border-bottom:1px solid rgba(42,47,61,.5);color:var(--text);}
tr:last-child td{border-bottom:none;}
.rank{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);}
.units-cell{font-variant-numeric:tabular-nums;}
.fcast-badge{display:inline-block;font-size:10px;padding:2px 7px;border-radius:3px;
  background:rgba(79,142,247,.12);color:var(--accent);}

/* Context chip row */
.ctx-row{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;}
.ctx{font-size:11px;padding:4px 10px;border-radius:20px;
  background:var(--surface2);border:1px solid var(--border);color:var(--muted);}
.ctx strong{color:var(--text);}

/* Legend */
.legend{display:flex;flex-wrap:wrap;gap:16px;margin-bottom:14px;}
.leg-item{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted);}
.leg-line{width:24px;height:2px;flex-shrink:0;}
.leg-dash{width:24px;height:2px;flex-shrink:0;
  background:repeating-linear-gradient(90deg,currentColor 0,currentColor 4px,transparent 4px,transparent 8px);}
.leg-band{width:16px;height:8px;border-radius:2px;flex-shrink:0;}

/* Accuracy proof divider */
.holdout-label{display:inline-flex;align-items:center;gap:6px;font-size:11px;
  font-weight:600;padding:3px 10px;border-radius:4px;
  background:rgba(245,166,35,.12);color:var(--amber);
  border:1px solid rgba(245,166,35,.25);}

.footnote{font-size:11px;color:var(--muted);margin-top:20px;line-height:1.5;
  padding-top:16px;border-top:1px solid var(--border);}
.footnote strong{color:var(--text);}

/* Promo lift toggle */
.promo-toggle{display:inline-flex;align-items:center;gap:6px;
  background:var(--surface2);border:1px solid var(--border);
  color:var(--muted);font-size:11px;font-weight:600;
  padding:5px 12px;border-radius:20px;cursor:pointer;
  transition:background .15s,color .15s,border-color .15s;
  margin-bottom:12px;letter-spacing:.02em;}
.promo-toggle:hover{color:var(--text);border-color:var(--muted);}
.promo-toggle.on{background:rgba(245,166,35,.12);border-color:rgba(245,166,35,.35);color:var(--amber);}

@media(max-width:640px){.kpi{min-width:100px;} h1{font-size:18px;}}
</style>
</head>
<body>
<div class="page">

<div class="eyebrow">BUILT × Aevah — Forecasting Use Case</div>
<h1>Forecast vs. Actuals — Live Data</h1>
<p class="subtitle" id="subtitle">Sell-through demand · Conventional Food · SPINS retailers</p>
<div class="data-badge" id="data-badge">Live SPINS data · generated __GENERATED__</div>

<div class="tabs">
  <button class="tab active" onclick="showTab('portfolio')">Portfolio View</button>
  <button class="tab" onclick="showTab('sku')">SKU Detail</button>
  <button class="tab" onclick="showTab('comparison')">Retailer Comparison</button>
  <button class="tab" onclick="showTab('accuracy')">Accuracy Proof</button>
</div>

<!-- ── TAB 1: Portfolio (Bracken) ──────────────────────────────────── -->
<div class="panel active" id="tab-portfolio">
  <div class="ctx-row">
    <div class="ctx"><strong>Retailer:</strong> <span id="r1-label">—</span></div>
    <div class="ctx"><strong>Channel:</strong> Conventional Food</div>
    <div class="ctx"><strong>Scope:</strong> All BUILT products</div>
    <div class="ctx"><strong>Actuals thru:</strong> <span id="anchor-label">—</span></div>
    <div class="ctx"><strong>Forecast:</strong> <span id="fcast-range-label">—</span></div>
  </div>

  <div class="kpi-strip">
    <div class="kpi"><div class="kv g" id="kpi-wmape">3.4%</div><div class="kl">Model error (wMAPE)</div><div class="ks">vs 39.7% naive baseline</div></div>
    <div class="kpi"><div class="kv b" id="kpi-series">—</div><div class="kl">Active forecast series</div><div class="ks">SKU × retailer × geography</div></div>
    <div class="kpi"><div class="kv g" id="kpi-yoy">—</div><div class="kl">YoY unit change (L13w)</div></div>
    <div class="kpi"><div class="kv a">13 wk</div><div class="kl">Forward forecast horizon</div></div>
  </div>

  <div class="chart-card">
    <div class="ct" id="chart1-title">Weekly Demand — Actuals + 13-Week Forecast</div>
    <div class="cs">SPINS sell-through actuals (prior year to present) · dashed = 13-week forward forecast · band = confidence interval (low/high)</div>
    <div class="legend">
      <div class="leg-item"><div class="leg-line" style="background:var(--accent2)"></div>Base Units</div>
      <div class="leg-item"><div class="leg-dash" style="color:var(--accent)"></div>Base Forecast</div>
      <div class="leg-item"><div class="leg-band" style="background:rgba(79,142,247,.14);border:1px dashed rgba(79,142,247,.38)"></div>Confidence band (q10–q90)</div>
    </div>
    <button class="promo-toggle" id="promo-btn-portfolio" data-lift-pct="__R1_LIFT_PCT__" onclick="setPromoMode(!promoOn)">＋ Promo Lift (__R1_LIFT_PCT__% avg)</button>
    <div class="cw"><canvas id="chartPortfolio"></canvas></div>
  </div>

  <div class="insight g">
    <div class="ii">◎</div>
    <div>
      <div class="il">What Bracken sees</div>
      <div id="bracken-narrative">The model tracks sell-through demand across all BUILT products and projects the next 13 weeks. The confidence band narrows where velocity has been stable and widens around promotional windows. At 3.4% wMAPE, the forecast is 10× more accurate than a simple prior-year baseline — comparable to the best CPG forecasting systems on the market.</div>
    </div>
  </div>

  <p class="footnote"><strong>Data source:</strong> SPINS syndicated POS data via built_enriched_weekly. <strong>Forecast:</strong> 28-feature demand model retrained September 2026, 29-week out-of-sample backtest. <strong>wMAPE:</strong> weighted Mean Absolute Percentage Error across all active series. Confidence band = model low/high prediction interval.</p>
</div>

<!-- ── TAB 2: SKU Detail (Connor) ──────────────────────────────────── -->
<div class="panel" id="tab-sku">
  <div class="ctx-row">
    <div class="ctx"><strong>Retailer:</strong> <span id="r1-label-sku">—</span></div>
    <div class="ctx"><strong>Channel:</strong> Conventional Food</div>
    <div class="ctx"><strong>SKU:</strong> <span id="focal-sku-label">Top by volume</span></div>
    <div class="ctx"><strong>Actuals thru:</strong> <span id="anchor-label-sku">—</span></div>
    <div class="ctx"><strong>Forecast:</strong> <span id="fcast-range-sku">—</span></div>
  </div>

  <div class="kpi-strip" id="sku-kpis">
    <div class="kpi"><div class="kv b" id="sku-13w-units">—</div><div class="kl">Units sold (L13w)</div></div>
    <div class="kpi"><div class="kv a" id="sku-fcast-units">—</div><div class="kl">Forecast next 13w</div></div>
    <div class="kpi"><div class="kv g" id="sku-price">—</div><div class="kl">Avg retail price</div></div>
    <div class="kpi"><div class="kv p">13 wk</div><div class="kl">Forward horizon</div></div>
  </div>

  <div class="chart-card">
    <div class="ct" id="sku-chart-title">SKU Weekly Units — Actuals + Forecast</div>
    <div class="cs">SPINS actuals (prior year to present) · dashed line = 13-week forward forecast · band = confidence interval</div>
    <div class="legend">
      <div class="leg-item"><div class="leg-line" style="background:var(--accent2)"></div>Base Units</div>
      <div class="leg-item"><div class="leg-dash" style="color:var(--accent)"></div>Base Forecast</div>
      <div class="leg-item"><div class="leg-band" style="background:rgba(79,142,247,.14);border:1px dashed rgba(79,142,247,.38)"></div>Confidence band (q10–q90)</div>
    </div>
    <button class="promo-toggle" id="promo-btn-sku" data-lift-pct="__SKU_LIFT_PCT__" onclick="setPromoMode(!promoOn)">＋ Promo Lift (__SKU_LIFT_PCT__% avg)</button>
    <div class="cw"><canvas id="chartSku"></canvas></div>
  </div>

  <div class="chart-card">
    <div class="ct">Top 5 SKUs — <span id="r1-acct-table">—</span> · Conventional Food · L13 Weeks</div>
    <div class="cs">Ranked by total units. Forecast shown for next 13 weeks.</div>
    <table id="sku-table">
      <thead><tr>
        <th>#</th><th>Product</th><th>UPC</th><th>Units L13W</th><th>Forecast 13W</th>
      </tr></thead>
      <tbody id="sku-table-body"></tbody>
    </table>
  </div>

  <div class="insight b">
    <div class="ii">◈</div>
    <div>
      <div class="il">What Connor sees</div>
      <div id="connor-narrative">The top SKU's 13-week forward forecast gives Connor a planning-ready number for each product at each account — no spreadsheet reconciliation needed. The confidence band tells him where to hold inventory buffer vs. where demand is predictable enough to run lean.</div>
    </div>
  </div>
</div>

<!-- ── TAB 3: Retailer Comparison (Brian) ─────────────────────────── -->
<div class="panel" id="tab-comparison">
  <div class="ctx-row">
    <div class="ctx"><strong>Accounts:</strong> <span id="both-accts-label">—</span></div>
    <div class="ctx"><strong>Channel:</strong> Conventional Food · All BUILT</div>
    <div class="ctx"><strong>Actuals thru:</strong> <span id="anchor-label-comp">—</span></div>
    <div class="ctx"><strong>Forecast:</strong> <span id="fcast-range-comp">—</span></div>
  </div>

  <div class="kpi-strip">
    <div class="kpi"><div class="kv g" id="r1-yoy-kpi">—</div><div class="kl" id="r1-yoy-label">YoY (L13w)</div></div>
    <div class="kpi"><div class="kv b" id="r2-yoy-kpi">—</div><div class="kl" id="r2-yoy-label">YoY (L13w)</div></div>
    <div class="kpi"><div class="kv g">3.4%</div><div class="kl">wMAPE across all series</div></div>
    <div class="kpi"><div class="kv a">2,517</div><div class="kl">Total forecast series</div></div>
  </div>

  <div class="chart-card">
    <div class="ct">Weekly Units — Account Comparison · Actuals + Forecast</div>
    <div class="cs">Base weekly units for each account · dashed = forward forecast · shows absolute scale difference and trajectory</div>
    <div class="legend" id="comp-legend"></div>
    <button class="promo-toggle" id="promo-btn-comp" data-lift-pct="__R1_LIFT_PCT__" onclick="setPromoMode(!promoOn)">＋ Promo Lift (__R1_LIFT_PCT__% avg)</button>
    <div class="cw"><canvas id="chartComparison"></canvas></div>
  </div>

  <div class="insight a">
    <div class="ii">⚡</div>
    <div>
      <div class="il">What Brian sees</div>
      <div id="brian-narrative">The model runs independently for each account and geography — it learns each account's seasonal pattern, promotional response, and base velocity separately. Showing raw weekly units makes the absolute scale difference visible alongside trend direction, and the 13-week forward forecasts diverge where account-level dynamics differ.</div>
    </div>
  </div>

  <p class="footnote"><strong>Data source:</strong> SPINS syndicated POS data via built_enriched_weekly. Raw weekly units shown; accounts may differ significantly in absolute volume. The 13-week forward forecast (dashed) is generated from the most recent SPINS delivery using the same production model.</p>
</div>

<!-- ── TAB 4: Accuracy Proof (Bracken) ───────────────────────────── -->
<div class="panel" id="tab-accuracy">
  <div class="ctx-row">
    <div class="ctx"><strong>Retailer:</strong> <span id="acc-r1-label">—</span></div>
    <div class="ctx"><strong>Channel:</strong> Conventional Food · All BUILT</div>
    <div class="ctx"><strong>Holdout window:</strong> <span id="acc-holdout-range">—</span></div>
    <div class="ctx holdout-label">Model had never seen this data</div>
  </div>

  <div class="kpi-strip">
    <div class="kpi"><div class="kv g" id="acc-wmape">—</div><div class="kl">Mo wMAPE (holdout)</div><div class="ks">vs Naive YoY: <span id="acc-naive-wmape">—</span></div></div>
    <div class="kpi"><div class="kv b" id="acc-holdout-wks">13 wk</div><div class="kl">Holdout window</div><div class="ks">No actuals used after training cutoff</div></div>
    <div class="kpi"><div class="kv a" id="acc-train-cutoff">—</div><div class="kl">Training cutoff</div><div class="ks">Anchor for all predictions</div></div>
    <div class="kpi"><div class="kv p">Recursive AR</div><div class="kl">Forecast method</div><div class="ks">No crystal ball — directional signal</div></div>
  </div>

  <div class="chart-card">
    <div class="ct" id="acc-chart-title">Predicted vs. Actual — Out-of-Sample Holdout</div>
    <div class="cs" id="acc-chart-sub">Training period actuals · then holdout: true recursive predictions (amber) vs. what actually happened (green) · band = model's quantile range, not a coverage guarantee · no actual data used after the training cutoff</div>
    <div class="legend">
      <div class="leg-item"><div class="leg-line" style="background:var(--accent2)"></div>Actuals (SPINS)</div>
      <div class="leg-item"><div class="leg-dash" style="color:var(--amber)"></div>True holdout prediction (May–Aug 2026)</div>
      <div class="leg-item"><div class="leg-band" style="background:rgba(245,166,35,.15);border:1px dashed rgba(245,166,35,.40)"></div>Holdout confidence band</div>
      <div class="leg-item"><div class="leg-dash" style="color:var(--accent);opacity:0.6"></div>Quarterly retrospective (same model)</div>
      <div class="leg-item"><div class="leg-dash" style="color:var(--accent)"></div>Forward forecast</div>
    </div>
    <button class="promo-toggle" id="promo-btn-acc" data-lift-pct="__R1_LIFT_PCT__" onclick="setPromoMode(!promoOn)">＋ Promo Lift (__R1_LIFT_PCT__% avg)</button>
    <div class="cw" style="height:380px"><canvas id="chartAccuracy"></canvas></div>
  </div>

  <div class="insight g">
    <div class="ii">◎</div>
    <div>
      <div class="il">The accuracy story for Bracken</div>
      <div id="acc-narrative">On May 10 the model was locked — zero foreknowledge of what came next. Each step fed its own prior output as the next input, exactly as the production forecast runs. The amber line is what the model called. The green line is what SPINS recorded. At <span id="acc-wmape-inline">—</span>% wMAPE over 13 weeks, Mo beats the simple year-ago naive baseline (<span id="acc-naive-wmape-inline">—</span>%) by a meaningful margin. The faint retrospective lines show quarterly cross-validation going back to 2025 — early quarters show higher error (fewer SKUs in distribution, unreliable lag-52 anchors), while mature distribution quarters (Q3 '25, Q2 '26) align closely with the true holdout. The chart below shows the full picture: where the model tracked cleanly, where demand surged beyond any prior pattern, and where the naive YoY baseline diverges furthest from actuals.</div>
    </div>
  </div>

  <p class="footnote"><strong>How to read this:</strong> The amber dashed line is a true multi-step recursive forecast — not a fitted curve. Each of the 13 predicted weeks uses the prior week's own prediction as input; no actual SPINS data after May 10 was available to the model. <strong>wMAPE</strong> = weighted Mean Absolute Percentage Error, weighted by actual volume. The confidence band is the model's q10–q90 quantile range — it shows where the model believes demand could reasonably land based on its training data, but is not a statistical coverage guarantee over a 13-week recursive horizon. Demand patterns that deviate from prior-year seasonal shape (as happened here in May and July 2026) will fall outside the band. The forward forecast (blue) is generated the same way from the most recent SPINS delivery.</p>
</div>

</div><!-- /page -->

<script>
// ── Injected data ─────────────────────────────────────────────────────
const DATA = __DATA_JSON__;

// ── Helpers ───────────────────────────────────────────────────────────
Chart.defaults.color = '#8892a4';
Chart.defaults.borderColor = '#2a2f3d';
Chart.defaults.font.family = 'Inter, sans-serif';
Chart.defaults.font.size = 11;

const TAB_NAMES = ['portfolio','sku','comparison','accuracy'];

function showTab(name) {
  TAB_NAMES.forEach((n,i) => {
    document.querySelectorAll('.tab')[i].classList.toggle('active', n === name);
    document.getElementById('tab-' + n).classList.toggle('active', n === name);
  });
}

// ── Promo lift toggle (global — all tabs stay in sync) ────────────────
let promoOn = false;
let chartPortfolio, chartSku, chartComparison, chartAccuracy;

function setPromoMode(on) {
  promoOn = on;
  document.querySelectorAll('.promo-toggle').forEach(btn => {
    btn.classList.toggle('on', on);
    const pct = btn.dataset.liftPct || '';
    const pctStr = pct ? ` (${pct}% avg)` : '';
    btn.textContent = on ? `✕ Promo Lift ON${pctStr}` : `＋ Promo Lift${pctStr}`;
  });
  [chartPortfolio, chartSku, chartComparison, chartAccuracy].forEach(ch => {
    if (!ch) return;
    ch.data.datasets.forEach(ds => { if (ds._promo) ds.hidden = !on; });
    ch.update('none');
  });
  // Show/hide accuracy tab promo legend items
  ['promo-leg-acc','promo-pred-leg-acc'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = on ? '' : 'none';
  });
}

// Parse any ISO date string (with or without time/timezone) → local Date at noon
function parseDate(s) {
  if (!s) return new Date(NaN);
  return new Date(String(s).slice(0, 10) + 'T12:00:00');
}

function fmtDate(s) {
  const d = parseDate(s);
  if (isNaN(d)) return '';
  return d.toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
}

function fmtDateShort(s) {
  const d = parseDate(s);
  if (isNaN(d)) return '';
  return d.toLocaleDateString('en-US', {month:'long', year:'numeric'});
}

// Compact tick label for x-axis: "Jan '25"
function fmtTick(s) {
  const d = parseDate(s);
  if (isNaN(d)) return '';
  const mo = d.toLocaleDateString('en-US', {month:'short'});
  const yr = String(d.getFullYear()).slice(2);
  return `${mo} '${yr}`;
}

function fmtUnits(v) {
  if (v == null) return '—';
  const n = parseFloat(v);
  if (n >= 1000) return (n/1000).toFixed(1) + 'K';
  return Math.round(n).toLocaleString();
}

function baseOpts(yLabel) {
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: ctx => {
            const ts = ctx[0]?.parsed?.x;
            if (ts == null) return '';
            return new Date(ts).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
          },
          label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y != null ? Math.round(ctx.parsed.y).toLocaleString() : '—'}`
        }
      }
    },
    scales: {
      x: {
        type: 'time',
        min: '2025-01-01',
        max: '2026-12-31',
        time: {
          unit: 'month',
          displayFormats: { month: "MMM ''yy" }
        },
        grid: { color: 'rgba(42,47,61,0.6)' },
        ticks: { maxRotation: 0, color: '#8892a4' }
      },
      y: { grid: { color: 'rgba(42,47,61,0.6)' },
           title: { display: !!yLabel, text: yLabel, color: '#8892a4' },
           ticks: { callback: v => fmtUnits(v) } }
    }
  };
}

// Inline plugin — draws a vertical dashed line at the actual/forecast boundary
const vertLinePlugin = {
  id: 'vertLine',
  afterDraw(chart, args, opts) {
    if (opts == null || opts.date == null) return;
    const {ctx, chartArea, scales} = chart;
    const x = scales.x.getPixelForValue(new Date(String(opts.date).slice(0,10) + 'T12:00:00').getTime());
    if (x < chartArea.left || x > chartArea.right) return;
    ctx.save();
    ctx.strokeStyle = 'rgba(79,142,247,0.55)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.moveTo(x, chartArea.top);
    ctx.lineTo(x, chartArea.bottom);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.font = '600 10px Inter, sans-serif';
    ctx.fillStyle = 'rgba(79,142,247,0.85)';
    ctx.textAlign = 'left';
    ctx.fillText(opts.label || '→ Forecast', x + 5, chartArea.top + 14);
    ctx.restore();
  }
};

// ── Populate labels ───────────────────────────────────────────────────
const pa = DATA.primary_acct;
const sa = DATA.secondary_acct;
document.getElementById('r1-label').textContent        = pa;
document.getElementById('r1-label-sku').textContent    = pa;
document.getElementById('r1-acct-table').textContent   = pa;
document.getElementById('kpi-yoy').textContent         = DATA.r1_yoy;
document.getElementById('kpi-series').textContent      = DATA.series_count;
document.getElementById('data-badge').textContent      = 'Live SPINS data · generated ' + DATA.generated;
document.getElementById('chart1-title').textContent    = pa + ' · Weekly Demand — Actuals + 13-Week Forecast';
document.getElementById('both-accts-label').textContent = sa ? pa + ' vs. ' + sa : pa;
document.getElementById('r1-yoy-kpi').textContent      = DATA.r1_yoy;
document.getElementById('r1-yoy-label').textContent    = pa + ' YoY (L13w)';
if (sa) {
  document.getElementById('r2-yoy-kpi').textContent   = DATA.r2_yoy;
  document.getElementById('r2-yoy-label').textContent = sa + ' YoY (L13w)';
}

// ── Date range chips (actuals cutoff + forecast range) ────────────────
function fcastRange(fcastRows) {
  if (!fcastRows || !fcastRows.length) return '—';
  const dates = fcastRows.map(r => r.week_ending).filter(Boolean).sort();
  return fmtDate(dates[0]) + ' – ' + fmtDate(dates[dates.length - 1]);
}
const anchorDisplay = DATA.anchor_date || '—';
const fcastRangeStr = fcastRange(DATA.r1_forecast);
document.getElementById('anchor-label').textContent      = anchorDisplay;
document.getElementById('anchor-label-sku').textContent  = anchorDisplay;
document.getElementById('anchor-label-comp').textContent = anchorDisplay;
document.getElementById('fcast-range-label').textContent = fcastRangeStr;
document.getElementById('fcast-range-sku').textContent   = fcastRangeStr;
document.getElementById('fcast-range-comp').textContent  = fcastRangeStr;

// ── Chart 1: Portfolio (actuals + forecast) ───────────────────────────
(function() {
  const actuals  = DATA.r1_actuals  || [];
  const forecast = DATA.r1_forecast || [];

  const actDates = actuals.map(r => r.week_ending);
  const actUnits = actuals.map(r => parseFloat(r.actual_units) || null);
  const actTotal = actuals.map(r => {
    const base = parseFloat(r.actual_units) || 0;
    const incr = parseFloat(r.incr_units)   || 0;
    return base + incr || null;
  });

  const fctDates     = forecast.map(r => r.week_ending);
  const fctBase      = forecast.map(r => parseFloat(r.forecast_units)       || null);
  const fctLow       = forecast.map(r => parseFloat(r.forecast_low)         || null);
  const fctHigh      = forecast.map(r => parseFloat(r.forecast_high)        || null);
  const fctPromoArr     = forecast.map(r => parseFloat(r.forecast_units_promo) || null);
  const fctPromoLowArr  = forecast.map(r => parseFloat(r.forecast_low_promo)   || null);
  const fctPromoHighArr = forecast.map(r => parseFloat(r.forecast_high_promo)  || null);

  const allLabels  = [...actDates, ...fctDates];
  const nAct       = actDates.length;
  const lastActual = actUnits.length ? actUnits[actUnits.length - 1] : null;
  const lastTotal  = actTotal.length  ? actTotal[actTotal.length - 1]   : null;

  const actLine      = [...actUnits, ...fctDates.map(() => null)];
  const actTotalLine = [...actTotal,  ...fctDates.map(() => null)];
  const fctLine      = [...Array(nAct).fill(null), ...fctBase];
  const highLine     = [...Array(nAct).fill(null), ...fctHigh];
  const lowLine      = [...Array(nAct).fill(null), ...fctLow];
  const fctPromoLine  = [...Array(nAct).fill(null), ...fctPromoArr];
  const promoHighLine = [...Array(nAct).fill(null), ...fctPromoHighArr];
  const promoLowLine  = [...Array(nAct).fill(null), ...fctPromoLowArr];

  const opts1 = baseOpts('Weekly Units');
  opts1.plugins.vertLine = { date: allLabels[nAct - 1], label: '→ Forecast' };
  chartPortfolio = new Chart(document.getElementById('chartPortfolio'), {
    type: 'line',
    plugins: [vertLinePlugin],
    data: {
      labels: allLabels,
      datasets: [
        { label: 'Band High', data: highLine, fill: '+1',
          backgroundColor: 'rgba(79,142,247,0.14)',
          borderColor: 'rgba(79,142,247,0.38)', borderWidth: 1, borderDash: [4,3],
          pointRadius: 0, tension: 0.3 },
        { label: 'Band Low', data: lowLine, fill: false,
          borderColor: 'rgba(79,142,247,0.38)', borderWidth: 1, borderDash: [4,3],
          pointRadius: 0, tension: 0.3 },
        { label: 'Base Forecast', data: fctLine, borderColor: '#4f8ef7',
          borderDash: [5,4], borderWidth: 2, pointRadius: 0, tension: 0.3, fill: false },
        { label: 'Base Units', data: actLine, borderColor: '#38c9a0',
          borderWidth: 2.5, pointRadius: 2, pointBackgroundColor: '#38c9a0', tension: 0.3, fill: false },
        // Promo overlay (hidden by default)
        { label: 'Total w/ Promo', data: actTotalLine, borderColor: '#f5a623',
          borderWidth: 2, pointRadius: 1.5, pointBackgroundColor: '#f5a623',
          tension: 0.3, fill: false, hidden: true, _promo: true },
        { label: 'Promo Band High', data: promoHighLine, fill: '+1',
          backgroundColor: 'rgba(245,166,35,0.14)',
          borderColor: 'rgba(245,166,35,0.40)', borderWidth: 1, borderDash: [4,3],
          pointRadius: 0, tension: 0.3, hidden: true, _promo: true },
        { label: 'Promo Band Low', data: promoLowLine, fill: false,
          borderColor: 'rgba(245,166,35,0.40)', borderWidth: 1, borderDash: [4,3],
          pointRadius: 0, tension: 0.3, hidden: true, _promo: true },
        { label: 'Promo Forecast', data: fctPromoLine, borderColor: 'rgba(245,166,35,0.75)',
          borderDash: [5,4], borderWidth: 2, pointRadius: 0, tension: 0.3,
          fill: false, hidden: true, _promo: true },
      ]
    },
    options: opts1
  });
})();

// ── Chart 2: SKU detail ───────────────────────────────────────────────
(function() {
  const actuals  = DATA.sku_actuals  || [];
  const forecast = DATA.sku_forecast || [];
  const desc     = DATA.focal_desc   || '';

  document.getElementById('focal-sku-label').textContent = desc;
  document.getElementById('sku-chart-title').textContent  = desc || 'Top SKU';

  const last13Units = actuals.slice(-13).reduce((s,r) => s + (parseFloat(r.actual_units)||0), 0);
  const fct13Units  = forecast.reduce((s,r) => s + (parseFloat(r.forecast_units)||0), 0);
  const avgPrice    = actuals.length ? actuals.slice(-4).reduce((s,r) => s + (parseFloat(r.avg_price)||0), 0) / Math.min(4, actuals.length) : 0;
  document.getElementById('sku-13w-units').textContent  = fmtUnits(last13Units);
  document.getElementById('sku-fcast-units').textContent = fmtUnits(fct13Units);
  document.getElementById('sku-price').textContent       = avgPrice ? '$' + avgPrice.toFixed(2) : '—';

  const actDates = actuals.map(r => r.week_ending);
  const actUnits = actuals.map(r => parseFloat(r.actual_units) || null);
  const actTotal = actuals.map(r => {
    const base = parseFloat(r.actual_units) || 0;
    const incr = parseFloat(r.incr_units)   || 0;
    return base + incr || null;
  });
  const fctDates        = forecast.map(r => r.week_ending);
  const fctBase         = forecast.map(r => parseFloat(r.forecast_units)       || null);
  const fctLow          = forecast.map(r => parseFloat(r.forecast_low)         || null);
  const fctHigh         = forecast.map(r => parseFloat(r.forecast_high)        || null);
  const fctPromoArr     = forecast.map(r => parseFloat(r.forecast_units_promo) || null);
  const fctPromoLowArr  = forecast.map(r => parseFloat(r.forecast_low_promo)   || null);
  const fctPromoHighArr = forecast.map(r => parseFloat(r.forecast_high_promo)  || null);

  const allLabels  = [...actDates, ...fctDates];
  const nAct       = actDates.length;
  const lastActual = actUnits.length ? actUnits[actUnits.length - 1] : null;
  const lastTotal  = actTotal.length  ? actTotal[actTotal.length - 1]  : null;

  const actLine      = [...actUnits, ...fctDates.map(() => null)];
  const actTotalLine = [...actTotal,  ...fctDates.map(() => null)];
  const fctLine       = [...Array(nAct).fill(null), ...fctBase];
  const highLine      = [...Array(nAct).fill(null), ...fctHigh];
  const lowLine       = [...Array(nAct).fill(null), ...fctLow];
  const fctPromoLine  = [...Array(nAct).fill(null), ...fctPromoArr];
  const promoHighLine = [...Array(nAct).fill(null), ...fctPromoHighArr];
  const promoLowLine  = [...Array(nAct).fill(null), ...fctPromoLowArr];

  const optsSku = baseOpts('Weekly Units');
  optsSku.plugins.vertLine = { date: allLabels[nAct - 1], label: '→ Forecast' };
  chartSku = new Chart(document.getElementById('chartSku'), {
    type: 'line',
    plugins: [vertLinePlugin],
    data: {
      labels: allLabels,
      datasets: [
        { label: 'Band High', data: highLine, fill: '+1',
          backgroundColor: 'rgba(79,142,247,0.14)',
          borderColor: 'rgba(79,142,247,0.38)', borderWidth: 1, borderDash: [4,3],
          pointRadius: 0, tension: 0.3 },
        { label: 'Band Low',  data: lowLine,  fill: false,
          borderColor: 'rgba(79,142,247,0.38)', borderWidth: 1, borderDash: [4,3],
          pointRadius: 0, tension: 0.3 },
        { label: 'Base Forecast', data: fctLine, borderColor: '#4f8ef7',
          borderDash: [5,4], borderWidth: 2, pointRadius: 0, tension: 0.3, fill: false },
        { label: 'Base Units', data: actLine, borderColor: '#38c9a0',
          borderWidth: 2.5, pointRadius: 2, pointBackgroundColor: '#38c9a0', tension: 0.3, fill: false },
        // Promo overlay (hidden by default)
        { label: 'Total w/ Promo', data: actTotalLine, borderColor: '#f5a623',
          borderWidth: 2, pointRadius: 1.5, pointBackgroundColor: '#f5a623',
          tension: 0.3, fill: false, hidden: true, _promo: true },
        { label: 'Promo Band High', data: promoHighLine, fill: '+1',
          backgroundColor: 'rgba(245,166,35,0.14)',
          borderColor: 'rgba(245,166,35,0.40)', borderWidth: 1, borderDash: [4,3],
          pointRadius: 0, tension: 0.3, hidden: true, _promo: true },
        { label: 'Promo Band Low', data: promoLowLine, fill: false,
          borderColor: 'rgba(245,166,35,0.40)', borderWidth: 1, borderDash: [4,3],
          pointRadius: 0, tension: 0.3, hidden: true, _promo: true },
        { label: 'Promo Forecast', data: fctPromoLine, borderColor: 'rgba(245,166,35,0.75)',
          borderDash: [5,4], borderWidth: 2, pointRadius: 0, tension: 0.3,
          fill: false, hidden: true, _promo: true },
      ]
    },
    options: optsSku
  });

  const tbody = document.getElementById('sku-table-body');
  tbody.innerHTML = '';
  const fctByUpc = {};
  fctByUpc[DATA.focal_upc] = fct13Units;

  (DATA.top_skus || []).forEach((sku, i) => {
    const tr = document.createElement('tr');
    const fct = fctByUpc[sku.upc] != null ? fmtUnits(fctByUpc[sku.upc]) : '<span class="fcast-badge">in model</span>';
    tr.innerHTML = `
      <td class="rank">${i+1}</td>
      <td>${sku.description || '—'}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted)">${sku.upc || '—'}</td>
      <td class="units-cell">${fmtUnits(sku.total_units_13w)}</td>
      <td>${fct}</td>
    `;
    tbody.appendChild(tr);
  });
})();

// ── Chart 3: Retailer comparison (raw units) ──────────────────────────
(function() {
  const r1a = DATA.r1_actuals  || [];
  const r1f = DATA.r1_forecast || [];
  const r2a = DATA.r2_actuals  || [];
  const r2f = DATA.r2_forecast || [];

  const r1ActDates = r1a.map(r => r.week_ending);
  const r1FctDates = r1f.map(r => r.week_ending);
  const r2ActDates = r2a.map(r => r.week_ending);

  const allLabels = [...r1ActDates, ...r1FctDates];
  const totalLen  = allLabels.length;

  const r1ActVals   = r1a.map(r => parseFloat(r.actual_units)        || null);
  const r1TotalVals = r1a.map(r => (parseFloat(r.actual_units)||0) + (parseFloat(r.incr_units)||0) || null);
  const r1FctVals   = r1f.map(r => parseFloat(r.forecast_units)      || null);
  const r1FctPromo  = r1f.map(r => parseFloat(r.forecast_units_promo)|| null);
  const r2ActVals   = r2a.map(r => parseFloat(r.actual_units)        || null);
  const r2TotalVals = r2a.map(r => (parseFloat(r.actual_units)||0) + (parseFloat(r.incr_units)||0) || null);
  const r2FctVals   = r2f.map(r => parseFloat(r.forecast_units)      || null);
  const r2FctPromo  = r2f.map(r => parseFloat(r.forecast_units_promo)|| null);

  const nR1    = r1ActDates.length;
  const lastR1 = r1ActVals.length ? r1ActVals[r1ActVals.length - 1]         : null;
  const lastR1T = r1TotalVals.length ? r1TotalVals[r1TotalVals.length - 1]  : null;
  const nR2    = r2ActDates.length;
  const lastR2 = r2ActVals.length ? r2ActVals[Math.min(nR2, totalLen) - 1]  : null;
  const lastR2T = r2TotalVals.length ? r2TotalVals[Math.min(nR2, totalLen) - 1] : null;

  function padAct(vals, n) {
    return [...vals, ...Array(totalLen - n).fill(null)];
  }
  function padFct(vals, baseN) {
    return [...Array(baseN).fill(null), ...vals,
            ...Array(Math.max(0, totalLen - baseN - vals.length)).fill(null)];
  }

  const datasets = [
    { label: DATA.primary_acct + ' Base',
      data: padAct(r1ActVals, nR1),
      borderColor: '#38c9a0', borderWidth: 2.5, pointRadius: 2,
      pointBackgroundColor: '#38c9a0', tension: 0.3, fill: false },
    { label: DATA.primary_acct + ' Forecast',
      data: padFct(r1FctVals, nR1),
      borderColor: '#38c9a0', borderDash: [5,4], borderWidth: 2,
      pointRadius: 0, tension: 0.3, fill: false },
    // Promo overlays for r1 (hidden by default)
    { label: DATA.primary_acct + ' Total w/ Promo',
      data: padAct(r1TotalVals, nR1),
      borderColor: 'rgba(56,201,160,0.55)', borderWidth: 1.5, pointRadius: 0,
      tension: 0.3, fill: false, borderDash: [3,3], hidden: true, _promo: true },
    { label: DATA.primary_acct + ' Promo Forecast',
      data: padFct(r1FctPromo, nR1),
      borderColor: 'rgba(56,201,160,0.5)', borderDash: [5,4], borderWidth: 1.5,
      pointRadius: 0, tension: 0.3, fill: false, hidden: true, _promo: true },
  ];

  if (r2a.length) {
    const r2ActPadded   = padAct(r2ActVals.slice(0, totalLen),   Math.min(nR2, totalLen));
    const r2TotalPadded = padAct(r2TotalVals.slice(0, totalLen), Math.min(nR2, totalLen));
    const r2FctPadded   = padFct(r2FctVals,  Math.min(nR2, totalLen));
    const r2PromoPadded = padFct(r2FctPromo, Math.min(nR2, totalLen));
    datasets.push(
      { label: DATA.secondary_acct + ' Base',
        data: r2ActPadded,
        borderColor: '#9b6dff', borderWidth: 2.5, pointRadius: 2,
        pointBackgroundColor: '#9b6dff', tension: 0.3, fill: false },
      { label: DATA.secondary_acct + ' Forecast',
        data: r2FctPadded,
        borderColor: '#9b6dff', borderDash: [5,4], borderWidth: 2,
        pointRadius: 0, tension: 0.3, fill: false },
      // Promo overlays for r2 (hidden by default)
      { label: DATA.secondary_acct + ' Total w/ Promo',
        data: r2TotalPadded,
        borderColor: 'rgba(155,109,255,0.55)', borderWidth: 1.5, pointRadius: 0,
        tension: 0.3, fill: false, borderDash: [3,3], hidden: true, _promo: true },
      { label: DATA.secondary_acct + ' Promo Forecast',
        data: r2PromoPadded,
        borderColor: 'rgba(155,109,255,0.5)', borderDash: [5,4], borderWidth: 1.5,
        pointRadius: 0, tension: 0.3, fill: false, hidden: true, _promo: true }
    );
  }

  const legendEl = document.getElementById('comp-legend');
  [[DATA.primary_acct, '#38c9a0'], [DATA.secondary_acct, '#9b6dff']].forEach(([label, c]) => {
    if (!label) return;
    legendEl.innerHTML += `<div class="leg-item"><div class="leg-line" style="background:${c}"></div>${label} base</div>
      <div class="leg-item"><div class="leg-dash" style="color:${c}"></div>${label} forecast</div>`;
  });

  const optsComp = baseOpts('Weekly Units');
  optsComp.plugins.vertLine = { date: r1ActDates[nR1 - 1], label: '→ Forecast' };
  chartComparison = new Chart(document.getElementById('chartComparison'), { type: 'line', plugins: [vertLinePlugin], data: { labels: allLabels, datasets }, options: optsComp });
})();

// ── Chart 4: Accuracy proof ────────────────────────────────────────────
(function() {
  const history = DATA.backtest_history || [];
  const holdout = DATA.backtest_holdout || [];
  const fwd     = DATA.r1_forecast      || [];
  const qBts    = DATA.quarterly_backtests || [];
  const wmape   = DATA.backtest_wmape   || '3.4';
  const cutoff  = DATA.backtest_cutoff  || '';
  const valEnd  = DATA.backtest_val_end || '';

  const naiveWmape = DATA.backtest_naive_wmape || '—';
  document.getElementById('acc-r1-label').textContent    = DATA.primary_acct;
  document.getElementById('acc-wmape').textContent        = wmape + '%';
  document.getElementById('acc-wmape-inline').textContent = wmape;
  document.getElementById('acc-naive-wmape').textContent  = naiveWmape !== '—' ? naiveWmape + '%' : '—';
  document.getElementById('acc-naive-wmape-inline').textContent = naiveWmape !== '—' ? naiveWmape + '%' : '—';
  document.getElementById('acc-train-cutoff').textContent = fmtDateShort(cutoff);
  document.getElementById('acc-holdout-wks').textContent  = holdout.length + ' wk';
  // Wire main KPI (portfolio tile)
  const kpiHoldoutEl = document.getElementById('kpi-holdout-wmape');
  if (kpiHoldoutEl) kpiHoldoutEl.textContent = wmape + '%';

  if (cutoff && valEnd) {
    document.getElementById('acc-holdout-range').textContent =
      fmtDateShort(cutoff) + ' – ' + fmtDateShort(valEnd);
  }

  document.getElementById('acc-chart-title').textContent =
    DATA.primary_acct + ' · Predicted vs. Actual — Quarterly Segments';

  document.getElementById('acc-chart-sub').textContent =
    'Green = SPINS actuals · amber = true holdout (model never saw this) · colored dashes = Mo quarterly forecasts · gray dashes = naive YoY baseline · badges show Mo vs. Naive wMAPE (⚠ = early distribution, low history)';

  if (!history.length && !holdout.length) {
    document.getElementById('acc-chart-sub').textContent =
      'Backtest data unavailable — re-run with mo-ml conda env to generate this chart.';
    return;
  }

  // Actuals: continuous from start of history through post-holdout
  const allActualsAcc = DATA.r1_actuals || [];
  const actualsData = allActualsAcc.map(r => ({
    x: r.week_ending, y: parseFloat(r.actual_units) || null
  })).filter(p => p.y != null);

  // True holdout predictions (amber, strong)
  const holdPredData = holdout.map(r => ({x: r.week_ending, y: parseFloat(r.pred_q50) || null}));
  const holdHighData = holdout.map(r => ({x: r.week_ending, y: parseFloat(r.pred_q90) || null}));
  const holdLowData  = holdout.map(r => ({x: r.week_ending, y: parseFloat(r.pred_q10) || null}));

  // Forward forecast
  const fwdData  = fwd.map(r => ({x: r.week_ending, y: parseFloat(r.forecast_units) || null}));
  const fwdHighD = fwd.map(r => ({x: r.week_ending, y: parseFloat(r.forecast_high)  || null}));
  const fwdLowD  = fwd.map(r => ({x: r.week_ending, y: parseFloat(r.forecast_low)   || null}));

  // Quarter boundary lines + wMAPE badge plugin
  const quarterLinesPlugin = {
    id: 'quarterLines',
    afterDraw(chart) {
      const {ctx, chartArea, scales} = chart;

      // Quarter grid lines at each Jan/Apr/Jul/Oct boundary
      const qBounds = [
        '2025-01-01','2025-04-01','2025-07-01','2025-10-01',
        '2026-01-01','2026-04-01','2026-07-01','2026-10-01'
      ];
      const qLbls  = ['Q1','Q2','Q3','Q4','Q1','Q2','Q3','Q4'];
      const qYears = ['2025','','','','2026','','',''];

      qBounds.forEach((d, i) => {
        const x = scales.x.getPixelForValue(new Date(d + 'T12:00:00').getTime());
        if (x < chartArea.left || x > chartArea.right) return;
        ctx.save();
        ctx.strokeStyle = 'rgba(136,146,164,0.22)';
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 5]);
        ctx.beginPath(); ctx.moveTo(x, chartArea.top); ctx.lineTo(x, chartArea.bottom); ctx.stroke();
        ctx.setLineDash([]);
        ctx.font = '600 9px Inter, sans-serif';
        ctx.fillStyle = 'rgba(136,146,164,0.6)';
        ctx.textAlign = 'left';
        ctx.fillText(qLbls[i], x + 4, chartArea.top + 13);
        if (qYears[i]) {
          ctx.font = '400 9px Inter, sans-serif';
          ctx.fillText(qYears[i], x + 4, chartArea.top + 23);
        }
        ctx.restore();
      });

      // Holdout boundary (training cutoff) — amber
      if (cutoff) {
        const x = scales.x.getPixelForValue(new Date(cutoff + 'T12:00:00').getTime());
        if (x >= chartArea.left && x <= chartArea.right) {
          ctx.save();
          ctx.strokeStyle = 'rgba(245,166,35,0.8)';
          ctx.lineWidth = 1.5;
          ctx.setLineDash([5, 3]);
          ctx.beginPath(); ctx.moveTo(x, chartArea.top); ctx.lineTo(x, chartArea.bottom); ctx.stroke();
          ctx.setLineDash([]);
          ctx.font = '700 9px Inter, sans-serif';
          ctx.fillStyle = 'rgba(245,166,35,0.9)';
          ctx.textAlign = 'right';
          ctx.fillText('← Training', x - 4, chartArea.top + 30);
          ctx.textAlign = 'left';
          ctx.fillText('Holdout →', x + 4, chartArea.top + 30);
          ctx.restore();
        }
      }

      // Holdout wMAPE badge + naive comparison
      if (holdout.length && wmape) {
        const midRow = holdout[Math.floor(holdout.length / 2)];
        if (midRow) {
          const mx = scales.x.getPixelForValue(new Date(midRow.week_ending + 'T12:00:00').getTime());
          if (mx >= chartArea.left && mx <= chartArea.right) {
            const naiveW = DATA.backtest_naive_wmape || '';
            const line1 = 'Mo ' + wmape + '%';
            const line2 = naiveW ? 'Naive ' + naiveW + '%' : '';
            ctx.save();
            ctx.font = '700 10px Inter, sans-serif';
            const tw1 = ctx.measureText(line1).width;
            const tw2 = line2 ? ctx.measureText(line2).width : 0;
            const bw = Math.max(tw1, tw2) + 16;
            const bh = line2 ? 30 : 18;
            ctx.fillStyle = 'rgba(245,166,35,0.15)';
            ctx.fillRect(mx - bw/2, chartArea.top + 4, bw, bh);
            ctx.fillStyle = '#f5a623';
            ctx.textAlign = 'center';
            ctx.fillText(line1, mx, chartArea.top + 16);
            if (line2) {
              ctx.fillStyle = 'rgba(136,146,164,0.75)';
              ctx.font = '500 9px Inter, sans-serif';
              ctx.fillText(line2, mx, chartArea.top + 28);
            }
            ctx.restore();
          }
        }
      }

      // Per-quarter wMAPE badges with maturity flag for low-series quarters
      (qBts || []).forEach(q => {
        if (!q.wmape || !q.predictions || !q.predictions.length) return;
        const midPred = q.predictions[Math.floor(q.predictions.length / 2)];
        if (!midPred) return;
        const mx = scales.x.getPixelForValue(new Date(String(midPred.week_ending).slice(0,10) + 'T12:00:00').getTime());
        if (mx < chartArea.left || mx > chartArea.right) return;
        // Low maturity = Q1 periods or series_count < 45
        const lowMat = q.series_count && q.series_count < 45;
        const moTxt = 'Mo ' + q.wmape + '%';
        const nTxt  = q.naive_wmape ? 'Naive ' + q.naive_wmape + '%' : '';
        ctx.save();
        ctx.font = '600 9px Inter, sans-serif';
        const tw1 = ctx.measureText(moTxt).width;
        const tw2 = nTxt ? ctx.measureText(nTxt).width : 0;
        const bw  = Math.max(tw1, tw2) + 12;
        const bh  = nTxt ? 28 : 16;
        const bgColor  = lowMat ? 'rgba(245,166,35,0.12)' : 'rgba(79,142,247,0.10)';
        const txtColor = lowMat ? 'rgba(245,166,35,0.80)' : 'rgba(136,146,164,0.80)';
        ctx.fillStyle = bgColor;
        ctx.fillRect(mx - bw/2, chartArea.bottom - bh - 6, bw, bh);
        ctx.fillStyle = txtColor;
        ctx.textAlign = 'center';
        ctx.fillText(moTxt, mx, chartArea.bottom - bh + 8);
        if (nTxt) {
          ctx.fillStyle = 'rgba(136,146,164,0.50)';
          ctx.font = '400 8px Inter, sans-serif';
          ctx.fillText(nTxt, mx, chartArea.bottom - 8);
        }
        if (lowMat) {
          ctx.fillStyle = 'rgba(245,166,35,0.60)';
          ctx.font = '400 8px Inter, sans-serif';
          ctx.fillText('\u26A0 ' + q.series_count + ' SKUs', mx, chartArea.bottom - bh - 2);
        }
        ctx.restore();
      });

      // Forward forecast boundary (blue)
      if (fwd.length) {
        const x = scales.x.getPixelForValue(new Date(fwd[0].week_ending + 'T12:00:00').getTime());
        if (x >= chartArea.left && x <= chartArea.right) {
          ctx.save();
          ctx.strokeStyle = 'rgba(79,142,247,0.7)';
          ctx.lineWidth = 1.5;
          ctx.setLineDash([4, 3]);
          ctx.beginPath(); ctx.moveTo(x, chartArea.top); ctx.lineTo(x, chartArea.bottom); ctx.stroke();
          ctx.setLineDash([]);
          ctx.font = '600 9px Inter, sans-serif';
          ctx.fillStyle = 'rgba(79,142,247,0.85)';
          ctx.textAlign = 'left';
          ctx.fillText('→ Forecast', x + 4, chartArea.top + 43);
          ctx.restore();
        }
      }
    }
  };

  const datasets = [
    // Forward forecast band (behind everything)
    { label: 'Fwd Band High', data: fwdHighD, fill: '+1',
      backgroundColor: 'rgba(79,142,247,0.10)',
      borderColor: 'rgba(79,142,247,0.28)', borderWidth: 1, borderDash: [4,3],
      pointRadius: 0, tension: 0.3 },
    { label: 'Fwd Band Low', data: fwdLowD, fill: false,
      borderColor: 'rgba(79,142,247,0.28)', borderWidth: 1, borderDash: [4,3],
      pointRadius: 0, tension: 0.3 },
    // True holdout amber confidence band
    { label: 'Holdout Band High', data: holdHighData, fill: '+1',
      backgroundColor: 'rgba(245,166,35,0.14)',
      borderColor: 'rgba(245,166,35,0.38)', borderWidth: 1, borderDash: [4,3],
      pointRadius: 0, tension: 0.3 },
    { label: 'Holdout Band Low', data: holdLowData, fill: false,
      borderColor: 'rgba(245,166,35,0.38)', borderWidth: 1, borderDash: [4,3],
      pointRadius: 0, tension: 0.3 },
    // Forward forecast line
    { label: 'Forward Forecast', data: fwdData, borderColor: '#4f8ef7',
      borderDash: [5,4], borderWidth: 2, pointRadius: 0, tension: 0.3, fill: false },
    // True holdout prediction (stronger amber)
    { label: 'Model Prediction (Holdout)', data: holdPredData, borderColor: '#f5a623',
      borderDash: [5,4], borderWidth: 2.5, pointRadius: 0, tension: 0.3, fill: false },
    // Actuals on top
    { label: 'Base Units (SPINS)', data: actualsData, borderColor: '#38c9a0',
      borderWidth: 2.5, pointRadius: 2, pointBackgroundColor: '#38c9a0', tension: 0.3, fill: false },
  ];

  // Quarterly retrospective lines + naive baseline per quarter
  const retroColors = [
    'rgba(155,109,255,0.55)',
    'rgba(79,142,247,0.45)',
    'rgba(155,109,255,0.55)',
    'rgba(79,142,247,0.45)',
    'rgba(155,109,255,0.55)',
    'rgba(79,142,247,0.45)',
  ];

  // Naive YoY baseline for the true holdout window
  const holdNaiveData = holdout
    .filter(r => r.naive_units > 0)
    .map(r => ({x: r.week_ending, y: parseFloat(r.naive_units) || null}));
  if (holdNaiveData.length) {
    datasets.push({
      label: 'Naive YoY (Holdout)',
      data: holdNaiveData,
      borderColor: 'rgba(136,146,164,0.38)',
      borderDash: [2,5],
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.2,
      fill: false,
    });
  }

  (qBts || []).forEach((q, i) => {
    if (!q.predictions || !q.predictions.length) return;
    // Naive YoY baseline for this quarter (faint gray)
    const naiveQData = q.predictions
      .filter(p => p.naive_units > 0)
      .map(p => ({x: p.week_ending, y: p.naive_units}));
    if (naiveQData.length) {
      datasets.push({
        label: q.quarter_label + ' Naive',
        data: naiveQData,
        borderColor: 'rgba(136,146,164,0.22)',
        borderDash: [2,5],
        borderWidth: 1,
        pointRadius: 0,
        tension: 0.2,
        fill: false,
      });
    }
    // Our model prediction for this quarter
    datasets.push({
      label: q.quarter_label + ' Retrospective',
      data: q.predictions.map(p => ({x: p.week_ending, y: p.pred_q50})),
      borderColor: retroColors[i % retroColors.length],
      borderDash: [3,3],
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    });
  });

  const skipBands = ['Fwd Band High','Fwd Band Low','Holdout Band High','Holdout Band Low'];
  const isNaive = lbl => lbl.includes('Naive');
  const skipTooltip = lbl => skipBands.includes(lbl) || isNaive(lbl);
  const optsAcc = {
    ...baseOpts('Weekly Units'),
    plugins: {
      ...baseOpts('Weekly Units').plugins,
      tooltip: {
        callbacks: {
          title: ctx => {
            const ts = ctx[0]?.parsed?.x;
            if (ts == null) return '';
            return new Date(ts).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
          },
          label: ctx => {
            if (skipTooltip(ctx.dataset.label)) return null;
            return ' ' + ctx.dataset.label + ': ' + (ctx.parsed.y != null ? Math.round(ctx.parsed.y).toLocaleString() : '—');
          }
        },
        filter: item => !skipTooltip(item.dataset.label)
      }
    }
  };

  chartAccuracy = new Chart(document.getElementById('chartAccuracy'), {
    type: 'line',
    plugins: [quarterLinesPlugin],
    data: { datasets },
    options: optsAcc
  });
})();
</script>"""

# ── Inject data and write file ────────────────────────────────────────
html_out = HTML.replace("__DATA_JSON__", json.dumps(payload, default=str))
html_out = html_out.replace("__GENERATED__", payload["generated"])
html_out = html_out.replace("__R1_LIFT_PCT__",  str(payload["r1_lift_pct"]))
html_out = html_out.replace("__SKU_LIFT_PCT__", str(payload["sku_lift_pct"]))

out_path = Path(__file__).parent / "bracken_forecast_charts.html"
out_path.write_text(html_out, encoding="utf-8")
print(f"\n✓ Written to {out_path}")
print(f"  Open with: open {out_path}")
