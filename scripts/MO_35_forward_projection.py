"""MO_35 — Forward Projection: Where Is BUILT Today? (July 2026)

Our SPINS data ends April 27, 2026. As of today (June 2026) we are
~9 weeks past our last data point. This script trains on everything
we have through April 2026 and projects forward 13 weeks to
~July 20, 2026 — answering the FP&A question:

  "Where does the model think BUILT is RIGHT NOW,
   3 months after our latest SPINS data?"

Models:
  Rolling LightGBM (q10/q50/q90)  — primary, with confidence bands
  ETS (Holt linear trend)          — comparison / sanity check
  Naive                            — baseline

Output charts:
  1. Total portfolio forward projection (actuals + forecast)
  2. Top-5 retailer breakdown (small multiples)
  3. "Estimated current position" callout

Run:  python MO_35_forward_projection.py

Outputs (scripts/outputs/):
    v2_mo35_metrics.json
    v2_mo35_chart1_total_forward.png
    v2_mo35_chart2_retailer_breakdown.png
"""

import os
import json
import warnings
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

from statsmodels.tsa.holtwinters import ExponentialSmoothing

warnings.filterwarnings("ignore")
logging.getLogger("lightgbm").setLevel(logging.ERROR)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "outputs")
PARQUET    = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")

GROUP_COLS      = ["upc", "channel_outlet", "retail_account", "geography_raw"]
H               = 13
MIN_TRAIN_WEEKS = 52
LOCAL_VAL_WEEKS = 8

FEATURE_COLS = [
    "base_units_roll4_avg",
    "base_units_roll8_avg",  "base_units_roll8_std",
    "base_units_roll13_avg", "base_units_roll13_std",
    "base_units_wow_delta",  "base_units_z8", "base_units_z13",
    "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
    "velocity_spm_z8", "velocity_spm_z13",
    "tdp", "tdp_z8",
    "arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std",
    "weeks_since_launch",
    "implied_elasticity",
    "max_donor_cannibal_prob", "donor_count",
    "week_of_year",
    "base_units_lag1", "base_units_lag4", "base_units_lag13",
    "base_units_lag52",   # YAGO — needed for seasonal shape in forward forecast
    "channel_outlet",
]

# Blend weight for seasonal adjustment in autoregressive forecast.
# 0.0 = pure AR (flat); 1.0 = pure year-ago seasonal naive.  0.40 is default.
SEASONAL_BLEND_WEIGHT = 0.40

LGBM_BASE = dict(
    objective="quantile", alpha=0.5,
    boosting_type="gbdt", n_estimators=1500, learning_rate=0.04,
    num_leaves=63, min_child_samples=20,
    feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
    reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1,
)

C_ACTUAL   = "#1a1a2e"
C_FORECAST = "#1565c0"
C_BAND     = "#90caf9"
C_ETS      = "#f57c00"
C_NAIVE    = "#9e9e9e"


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_units(v, _):
    if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if v >= 1_000:     return f"{int(v/1_000)}K"
    return str(int(v))

def train_lgbm(train_df, avail, alpha=0.5):
    params = {**LGBM_BASE, "alpha": alpha}
    lval_cut = train_df["__time"].max() - pd.Timedelta(weeks=LOCAL_VAL_WEEKS)
    super_tr  = train_df[train_df["__time"] <  lval_cut]
    local_val = train_df[train_df["__time"] >= lval_cut]
    model = lgb.LGBMRegressor(**params)
    model.fit(
        super_tr[avail], super_tr["log_base_units"].values,
        eval_set=[(local_val[avail], local_val["log_base_units"].values)],
        callbacks=[lgb.early_stopping(50, verbose=False),
                   lgb.log_evaluation(10000)],
    )
    return model

def fit_holt(train_vals, h):
    v = np.asarray(train_vals, float)
    v = v[np.isfinite(v)]
    if len(v) < 4:
        return np.full(h, float(np.mean(v)) if len(v) else np.nan)
    try:
        v_fit = np.maximum(v, 0.01)
        mdl = ExponentialSmoothing(v_fit, trend="add", seasonal=None,
                                   initialization_method="estimated")
        fit = mdl.fit(optimized=True, remove_bias=True)
        return np.maximum(fit.forecast(h), 0.0).astype(float)
    except Exception:
        return np.full(h, float(np.mean(v[-13:]) if len(v) >= 13 else np.mean(v)))

def naive_ma(train_vals, h):
    v = np.asarray(train_vals, float)
    v = v[np.isfinite(v)]
    return np.full(h, float(np.mean(v[-13:]) if len(v) >= 13 else np.mean(v)))

def qualify(df, cutoff, min_tr=MIN_TRAIN_WEEKS):
    """Qualify series that have min_tr weeks of training data (no OOS check — future projection)."""
    tr_cnt = df[df["__time"] <= cutoff].groupby(GROUP_COLS).size()
    idx = set(tr_cnt[tr_cnt >= min_tr].index)
    df2 = df.copy()
    df2["_k"] = list(zip(df2["upc"], df2["channel_outlet"],
                         df2["retail_account"], df2["geography_raw"]))
    return df2[df2["_k"].isin(idx)].drop(columns=["_k"])

def _autoreg_forecast(train_df, avail, models, last_date, h):
    """True per-group autoregressive forecast with YAGO seasonal blend.

    Replaces the old ``build_future_features`` + batch-predict pattern.

    At each step the blended q50 prediction is appended to units_history and
    used as lag1 for the next step — so the model's own recent outputs feed
    forward, exactly matching the training regime.  Without this the AR lags
    collapse to the same anchor value for all 13 steps, producing a flat line.

    Seasonal blend (SEASONAL_BLEND_WEIGHT):
        Each prediction is nudged toward ``lag52 × yoy_ratio`` — the year-ago
        actual for that calendar week, scaled by how current demand is tracking
        relative to last year.  This injects the real seasonal curve (summer
        uptick, winter dip, etc.) into the flat AR extrapolation without
        requiring a retraining step.

    Returns a DataFrame with GROUP_COLS + __time + pred_q10/q50/q90
    (pred_ets / pred_naive are added by the caller).
    """
    all_rows = []
    future_dates = [last_date + pd.Timedelta(weeks=i + 1) for i in range(h)]

    for key, grp in train_df.groupby(GROUP_COLS):
        grp = grp.sort_values("__time")
        last_row = grp.iloc[-1].copy()

        units_hist = grp["base_units"].tolist()
        arp_hist   = grp["arp"].tolist() if "arp" in grp.columns else []
        N = len(units_hist)

        # Precompute YAGO for each of the h forecast steps from actuals only.
        # Step k (1-indexed): lag52 = units_hist at index N - 53 + k
        lag52_seq = [
            float(units_hist[N - 53 + k])
            if 0 <= (N - 53 + k) < N else np.nan
            for k in range(1, h + 1)
        ]

        # YoY ratio at anchor: scales the year-ago curve to current demand level.
        _yago_anchor = float(units_hist[N - 52]) if N >= 52 else None
        if _yago_anchor and _yago_anchor > 0:
            yoy_ratio = float(np.clip(float(units_hist[-1]) / _yago_anchor, 0.5, 2.0))
        else:
            yoy_ratio = None

        for step, fd in enumerate(future_dates):
            fr = last_row.copy()
            fr["__time"] = fd
            fr["week_of_year"] = int(fd.isocalendar()[1])
            lag52 = lag52_seq[step]

            # Autoregressive lags — drawn from running history (actuals + predictions)
            if "base_units_lag1" in avail:
                fr["base_units_lag1"]  = units_hist[-1]  if len(units_hist) >= 1  else np.nan
            if "base_units_lag4" in avail:
                fr["base_units_lag4"]  = units_hist[-4]  if len(units_hist) >= 4  else units_hist[-1]
            if "base_units_lag13" in avail:
                fr["base_units_lag13"] = units_hist[-13] if len(units_hist) >= 13 else units_hist[-1]
            if "base_units_lag52" in avail:
                fr["base_units_lag52"] = lag52
            if "weeks_since_launch" in avail and pd.notna(fr.get("weeks_since_launch")):
                fr["weeks_since_launch"] = float(fr["weeks_since_launch"]) + step + 1

            # ARP features — hold flat (no external signal); delta = 0
            if arp_hist:
                arp_cur = arp_hist[-1]
                if "arp" in avail:           fr["arp"]           = arp_cur
                if "arp_lag1" in avail:      fr["arp_lag1"]      = arp_cur
                if "arp_lag4" in avail:      fr["arp_lag4"]      = (arp_hist[-4]
                                                                     if len(arp_hist) >= 4
                                                                     else arp_cur)
                if "arp_wow_delta" in avail: fr["arp_wow_delta"] = 0.0
                if "arp_roll8_avg" in avail: fr["arp_roll8_avg"] = float(np.nanmean(arp_hist[-8:]))
                if "arp_roll8_std" in avail: fr["arp_roll8_std"] = float(np.nanstd(arp_hist[-8:])) if len(arp_hist) > 1 else 0.0

            X = pd.DataFrame([dict(fr)])
            if "channel_outlet" in X.columns:
                X["channel_outlet"] = X["channel_outlet"].astype("category")
            X_feat = X[[c for c in avail if c in X.columns]]

            q10 = float(np.expm1(max(0, models["q10"].predict(X_feat)[0])))
            q50 = float(np.expm1(max(0, models["q50"].predict(X_feat)[0])))
            q90 = float(np.expm1(max(0, models["q90"].predict(X_feat)[0])))

            # Seasonal blend: bend the flat AR mean toward the year-ago curve.
            if yoy_ratio is not None and pd.notna(lag52) and lag52 > 0 and q50 > 0:
                seasonal_ref = lag52 * yoy_ratio
                blend_mult = (
                    (1.0 - SEASONAL_BLEND_WEIGHT) * q50
                    + SEASONAL_BLEND_WEIGHT * seasonal_ref
                ) / q50
                q10 = max(0.0, q10 * blend_mult)
                q50 = max(0.0, q50 * blend_mult)
                q90 = max(0.0, q90 * blend_mult)

            # Feed blended q50 back so future steps see a realistic lag1
            units_hist.append(q50)
            if arp_hist:
                arp_hist.append(arp_hist[-1])

            all_rows.append({
                **{c: fr.get(c) for c in GROUP_COLS},
                "__time":    fd,
                "pred_q10":  q10,
                "pred_q50":  q50,
                "pred_q90":  q90,
                "pred_ets":  np.nan,
                "pred_naive": np.nan,
            })

    return pd.DataFrame(all_rows)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("MO_35  —  Forward Projection to July 2026")
    print("=" * 65)

    # ── Load ──────────────────────────────────────────────────────────────────
    print(f"\nLoading {PARQUET} …")
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    for c in [x for x in FEATURE_COLS if x != "channel_outlet"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "channel_outlet" in df.columns:
        df["channel_outlet"] = df["channel_outlet"].astype("category")
    df = df.dropna(subset=["base_units"]).copy()
    df["log_base_units"] = np.log1p(df["base_units"])

    if "geography_raw" in df.columns:
        mulo = df["geography_raw"].str.contains(
            "MULTI OUTLET|MULO|TOTAL US|ALL CHANNEL", case=False, na=False)
        df = df[~mulo].copy()
    if "geography_level" in df.columns:
        df = df[~df["geography_level"].str.upper().isin(["NATIONAL","TOTAL"])].copy()

    avail = [c for c in FEATURE_COLS if c in df.columns]
    last_data_date = df["__time"].max()
    print(f"  Latest SPINS data:  {last_data_date.date()}")
    print(f"  Projecting forward: {H} weeks → ~{(last_data_date + pd.Timedelta(weeks=H)).date()}")

    # ── Qualify on all available data ─────────────────────────────────────────
    train_df = qualify(df, last_data_date)
    n_series = train_df.groupby(GROUP_COLS).ngroups
    print(f"  Qualifying series:  {n_series}")
    print(f"  Train range:        {train_df['__time'].min().date()} → {last_data_date.date()}")

    # ── Train q10 / q50 / q90 ────────────────────────────────────────────────
    print("\nTraining LightGBM (q10, q50, q90) on full data …")
    m_q50 = train_lgbm(train_df, avail, 0.50)
    print(f"  q50 best iter: {m_q50.best_iteration_}")
    m_q10 = train_lgbm(train_df, avail, 0.10)
    print(f"  q10 best iter: {m_q10.best_iteration_}")
    m_q90 = train_lgbm(train_df, avail, 0.90)
    print(f"  q90 best iter: {m_q90.best_iteration_}")

    # ── Autoregressive forecast (per-group, with YAGO seasonal blend) ─────────
    print("\nRunning autoregressive forecast (per series, with seasonal blend) …")
    _models = {"q10": m_q10, "q50": m_q50, "q90": m_q90}
    future_df = _autoreg_forecast(train_df, avail, _models, last_data_date, H)
    future_df["__time"] = pd.to_datetime(future_df["__time"], utc=True)

    # ── ETS + Naive per series ─────────────────────────────────────────────────
    print("Fitting ETS (Holt) and Naive per series …")
    # Map future_df rows to series predictions
    future_df["pred_ets"]   = np.nan
    future_df["pred_naive"] = np.nan
    for key, grp_tr in train_df.groupby(GROUP_COLS):
        train_vals = grp_tr.sort_values("__time")["base_units"].values
        ets_fc   = fit_holt(train_vals, H)
        naive_fc = naive_ma(train_vals, H)

        mask = (
            (future_df["upc"]            == key[0]) &
            (future_df["channel_outlet"] == key[1]) &
            (future_df["retail_account"] == key[2]) &
            (future_df["geography_raw"]  == key[3])
        )
        grp_fut = future_df[mask].sort_values("__time")
        if len(grp_fut) == 0:
            continue
        steps = min(len(grp_fut), H)
        future_df.loc[grp_fut.index[:steps], "pred_ets"]   = ets_fc[:steps]
        future_df.loc[grp_fut.index[:steps], "pred_naive"] = naive_fc[:steps]

    # ── Weekly aggregates ─────────────────────────────────────────────────────
    fwd_wk = (future_df.groupby("__time")
               .agg(pred_q50=("pred_q50","sum"),
                    pred_q10=("pred_q10","sum"),
                    pred_q90=("pred_q90","sum"),
                    pred_ets=("pred_ets","sum"),
                    pred_naive=("pred_naive","sum"))
               .reset_index().sort_values("__time"))
    fwd_wk["date"] = fwd_wk["__time"].dt.tz_convert(None)

    # Historical actuals (last 26 weeks)
    hist_wk = (train_df.groupby("__time")["base_units"].sum()
                .reset_index().sort_values("__time").tail(26))
    hist_wk["date"] = hist_wk["__time"].dt.tz_convert(None)

    # Summary stats
    q50_total   = fwd_wk["pred_q50"].sum()
    q10_total   = fwd_wk["pred_q10"].sum()
    q90_total   = fwd_wk["pred_q90"].sum()
    q50_avg_wk  = fwd_wk["pred_q50"].mean()
    hist_avg_wk = hist_wk["base_units"].tail(13).mean()
    growth_vs_hist = (q50_avg_wk - hist_avg_wk) / hist_avg_wk * 100

    weeks_since_data = 9  # approximate weeks since SPINS cutoff

    print(f"\n  Q3 2026 Projection Summary ({H}-week horizon):")
    print(f"    Floor (q10):     {fmt_units(q10_total, None)} total units")
    print(f"    Plan  (q50):     {fmt_units(q50_total, None)} total units")
    print(f"    Ceiling (q90):   {fmt_units(q90_total, None)} total units")
    print(f"    Avg weekly (q50): {fmt_units(q50_avg_wk, None)} units/wk")
    print(f"    vs prior 13w avg: {growth_vs_hist:+.1f}%")

    # ── Save ─────────────────────────────────────────────────────────────────
    meta = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "last_data_date": str(last_data_date.date()),
        "forecast_end": str((last_data_date + pd.Timedelta(weeks=H)).date()),
        "n_series": n_series,
        "h": H,
        "weeks_since_data": weeks_since_data,
        "projection": {
            "q10_total": round(q10_total, 0),
            "q50_total": round(q50_total, 0),
            "q90_total": round(q90_total, 0),
            "q50_avg_weekly": round(q50_avg_wk, 0),
            "growth_vs_prior_13w_pct": round(growth_vs_hist, 2),
        },
    }
    with open(os.path.join(OUTPUT_DIR, "v2_mo35_metrics.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # ── Charts ────────────────────────────────────────────────────────────────
    _chart1_total_forward(hist_wk, fwd_wk, meta)
    _chart2_retailer_breakdown(train_df, future_df, last_data_date)

    print(f"\n{'='*65}")
    print("MO_35 complete.")
    print(f"{'='*65}")


def _chart1_total_forward(hist_wk, fwd_wk, meta):
    """Total portfolio: actuals through Apr 2026 + projection to Jul 2026."""
    fig, ax = plt.subplots(figsize=(14, 7))

    cutoff_date = pd.to_datetime(meta["last_data_date"])
    fwd_end     = pd.to_datetime(meta["forecast_end"])
    today_approx = cutoff_date + pd.Timedelta(weeks=meta["weeks_since_data"])

    # Historical actuals
    ax.plot(hist_wk["date"], hist_wk["base_units"],
            color=C_ACTUAL, lw=2.8, label="Actuals (SPINS data)", zorder=6)

    # Confidence band
    ax.fill_between(fwd_wk["date"], fwd_wk["pred_q10"], fwd_wk["pred_q90"],
                    color=C_BAND, alpha=0.35, label="Forecast range (q10–q90)", zorder=3)

    # Forecast lines
    ax.plot(fwd_wk["date"], fwd_wk["pred_q50"],
            color=C_FORECAST, lw=2.8, linestyle="--",
            label=f"LightGBM forecast (q50)", zorder=5)
    ax.plot(fwd_wk["date"], fwd_wk["pred_ets"],
            color=C_ETS, lw=1.6, linestyle=":",
            label="ETS (Holt trend)", zorder=4)

    # Data cutoff line
    ax.axvline(cutoff_date, color="#555", lw=1.5, linestyle=":",
               label=f"Last SPINS data ({meta['last_data_date']})")

    # "You are here" marker
    today_q50 = np.interp(
        (today_approx - fwd_wk["date"].min()).days,
        (fwd_wk["date"] - fwd_wk["date"].min()).dt.days.values,
        fwd_wk["pred_q50"].values,
    )
    today_q10 = np.interp(
        (today_approx - fwd_wk["date"].min()).days,
        (fwd_wk["date"] - fwd_wk["date"].min()).dt.days.values,
        fwd_wk["pred_q10"].values,
    )
    today_q90 = np.interp(
        (today_approx - fwd_wk["date"].min()).days,
        (fwd_wk["date"] - fwd_wk["date"].min()).dt.days.values,
        fwd_wk["pred_q90"].values,
    )
    ax.axvline(today_approx, color="#c62828", lw=2, linestyle="--", alpha=0.8)
    ax.annotate(
        f"TODAY (est.)\n{today_approx.strftime('%b %Y')}\n"
        f"~{fmt_units(today_q50, None)} units/wk\n"
        f"(range: {fmt_units(today_q10, None)}–{fmt_units(today_q90, None)})",
        xy=(today_approx, today_q50),
        xytext=(30, -60), textcoords="offset points",
        fontsize=9, color="#c62828",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#ffebee", edgecolor="#c62828", alpha=0.9),
        arrowprops=dict(arrowstyle="->", color="#c62828", lw=1.5),
        zorder=10)

    # Horizon reference lines
    q50_val = fwd_wk["pred_q50"].mean()
    ax.axhline(q50_val, color=C_FORECAST, lw=1, linestyle="--", alpha=0.35)
    ax.text(fwd_end + pd.Timedelta(days=2), q50_val,
            f"  Plan avg\n  {fmt_units(q50_val, None)}/wk",
            fontsize=8.5, color=C_FORECAST, va="center")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_units))
    ax.set_ylabel("Total Weekly Units — All Retailers, All SKUs", fontsize=11)
    ax.set_title(
        "Where Is BUILT Today?\n"
        "Historical SPINS actuals through April 2026  ·  LightGBM projection to July 2026",
        fontsize=11, fontweight="bold")
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(True, axis="y", alpha=0.25, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo35_chart1_total_forward.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Chart 1 (total forward) → {out}")


def _chart2_retailer_breakdown(train_df, future_df, last_date):
    """Top-6 retailers: actuals + q50 forecast with q10/q90 band."""
    # Aggregate per retailer
    hist_ret = (train_df.groupby(["retail_account", "__time"])["base_units"]
                .sum().reset_index())
    fwd_ret = (future_df.groupby(["retail_account", "__time"])
               .agg(pred_q50=("pred_q50","sum"),
                    pred_q10=("pred_q10","sum"),
                    pred_q90=("pred_q90","sum"))
               .reset_index())

    top_ret = (fwd_ret.groupby("retail_account")["pred_q50"].sum()
               .nlargest(6).index.tolist())

    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharey=False)
    axes = axes.flatten()

    for ax, ret in zip(axes, top_ret):
        hr = hist_ret[hist_ret["retail_account"] == ret].copy()
        fr = fwd_ret[fwd_ret["retail_account"] == ret].copy()
        hr["date"] = pd.to_datetime(hr["__time"]).dt.tz_convert(None)
        fr["date"] = pd.to_datetime(fr["__time"]).dt.tz_convert(None)

        hr_recent = hr.nlargest(13, "__time").sort_values("date")

        ax.fill_between(fr["date"], fr["pred_q10"], fr["pred_q90"],
                        color=C_BAND, alpha=0.35)
        ax.plot(hr_recent["date"], hr_recent["base_units"],
                color=C_ACTUAL, lw=2.0, label="Actuals")
        ax.plot(fr["date"], fr["pred_q50"],
                color=C_FORECAST, lw=2.2, linestyle="--", label="Forecast (q50)")

        ax.axvline(pd.to_datetime(last_date).tz_convert(None),
                   color="#555", lw=1, linestyle=":", alpha=0.7)

        ret_label = ret if len(ret) <= 20 else ret[:18] + "…"
        ax.set_title(ret_label, fontsize=10, fontweight="bold")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b'%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=8)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_units))
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(True, axis="y", alpha=0.25, linestyle="--")
        ax.spines[["top","right"]].set_visible(False)
        if ret == top_ret[0]:
            ax.legend(fontsize=8, loc="upper left")

    fig.suptitle(
        "Where Is BUILT Today? — Retailer Breakdown\n"
        "Actuals through April 2026  ·  Projected to July 2026  |  Shaded band = q10–q90",
        fontsize=11, fontweight="bold", y=1.01)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo35_chart2_retailer_breakdown.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Chart 2 (retailer breakdown) → {out}")


if __name__ == "__main__":
    main()
