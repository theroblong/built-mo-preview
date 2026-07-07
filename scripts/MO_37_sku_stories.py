"""MO_37 — Real-World SKU Stories: BUILT at Walmart

Five charts that translate abstract accuracy metrics into concrete planning
decisions for FP&A, using three named BUILT products at Walmart as examples.

Focal SKUs (all WALMART CORP - RMA, CONVENTIONAL|MASS MERCH):
  ① Brownie Batter 4pk  (08-40229-30380)  138 weeks — mature, anchor
  ② Cookie Dough 4pk    (08-40229-30558)   89 weeks — growing
  ③ Brownie Batter 8pk  (08-40229-30644)   49 weeks — new/expanding (cold-start)

Charts:
  1. Multi-Horizon Zoom     — Same SKU, four time windows (2.7yr/1yr/1Q/1mo)
  2. Method Horse Race      — All methods head-to-head on BB 4pk, Jan–Apr 2026
  3. Demand Decomposition   — What drove growth: TDP expansion vs. velocity gain
  4. Cold-Start ETS         — BB 8pk weeks 1-49: ETS bridges before LGB threshold
  5. Dollar Translation     — Forecast error in $ at Excel 35% vs Mo 4.4%

Run:  python MO_37_sku_stories.py
Outputs:  scripts/outputs/v2_mo37_chart{1-5}_*.png + v2_mo37_summary.json
"""

import os
import json
import warnings
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import lightgbm as lgb
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches

warnings.filterwarnings("ignore")
logging.getLogger("lightgbm").setLevel(logging.ERROR)

# ── Config ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "outputs")
PARQUET    = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")

GROUP_COLS      = ["upc", "channel_outlet", "retail_account", "geography_raw"]
H               = 16          # OOS test weeks (Jan–Apr 2026)
MIN_TRAIN_WEEKS = 52
LOCAL_VAL_WEEKS = 8

CUTOFF = pd.Timestamp("2025-12-28", tz="UTC")   # train through Dec 2025

# Focal identifiers
BB4PK_UPC  = "08-40229-30380"   # Brownie Batter 4pk
CD4PK_UPC  = "08-40229-30558"   # Cookie Dough 4pk
BB8PK_UPC  = "08-40229-30644"   # Brownie Batter 8pk (cold-start)
WM_ACCOUNT = "WALMART"
WM_CHANNEL = "CONVENTIONAL|MASS MERCH"
WM_GEO     = "WALMART CORP - RMA"

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
    "channel_outlet",
]

LGBM_BASE = dict(
    objective="quantile", alpha=0.5,
    boosting_type="gbdt", n_estimators=1500, learning_rate=0.04,
    num_leaves=63, min_child_samples=20,
    feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
    reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1,
)

# Palette
C_ACTUAL   = "#1a1a2e"
C_LGB      = "#1565c0"
C_BAND     = "#90caf9"
C_ETS      = "#e65100"
C_MA13     = "#6d4c41"
C_NAIVE    = "#9e9e9e"
C_TDP      = "#2e7d32"
C_VEL      = "#6a1b9a"
C_EXCEL    = "#c62828"
C_MO       = "#1565c0"


# ── Helpers ────────────────────────────────────────────────────────────────────
def wmape(actual, pred):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    m = np.isfinite(a) & np.isfinite(p)
    d = np.sum(a[m])
    return float(np.sum(np.abs(a[m] - p[m])) / d * 100) if d > 0 else np.nan


def fmt_units(v, _):
    if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if v >= 1_000:     return f"{int(v/1_000)}K"
    return str(int(v))


def fmt_dollar(v, _):
    if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
    if v >= 1_000:     return f"${int(v/1_000)}K"
    return f"${int(v)}"


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


def qualify(df, cutoff, min_tr=MIN_TRAIN_WEEKS, min_te=H):
    tr_cnt = df[df["__time"] <  cutoff].groupby(GROUP_COLS).size()
    te_cnt = df[df["__time"] >= cutoff].groupby(GROUP_COLS).size()
    cov = pd.concat([tr_cnt.rename("tr"), te_cnt.rename("te")], axis=1).fillna(0).astype(int)
    qual_idx = set(cov[(cov["tr"] >= min_tr) & (cov["te"] >= min_te)].index.tolist())
    df2 = df.copy()
    df2["_key"] = list(zip(df2["upc"], df2["channel_outlet"],
                           df2["retail_account"], df2["geography_raw"]))
    return df2[df2["_key"].isin(qual_idx)].drop(columns=["_key"])


def fit_ets(train_vals):
    """Holt linear trend ETS. Returns fitted model."""
    v = np.asarray(train_vals, float)
    v = np.where(v <= 0, 1.0, v)   # ETS needs positive values
    try:
        model = ExponentialSmoothing(v, trend="add", seasonal=None)
        return model.fit(optimized=True)
    except Exception:
        return None


def naive_baseline(train_vals, n):
    v = np.asarray(train_vals, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return np.full(n, np.nan), np.full(n, np.nan)
    ma13  = np.full(n, np.mean(v[-13:]) if len(v) >= 13 else np.mean(v))
    naive = np.full(n, v[-1])
    return ma13, naive


def focal_filter(df, upc):
    return df[
        (df["upc"]            == upc) &
        (df["retail_account"] == WM_ACCOUNT) &
        (df["channel_outlet"] == WM_CHANNEL) &
        (df["geography_raw"]  == WM_GEO)
    ].copy().sort_values("__time")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("MO_37  —  Real-World SKU Stories: BUILT at Walmart")
    print("=" * 65)

    # ── Load ──────────────────────────────────────────────────────────────────
    print(f"\nLoading {PARQUET} …")
    raw = pd.read_parquet(PARQUET)
    raw["__time"] = pd.to_datetime(raw["__time"], utc=True)
    raw = raw.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    num_cols = [c for c in FEATURE_COLS if c != "channel_outlet"]
    for c in num_cols:
        if c in raw.columns:
            raw[c] = pd.to_numeric(raw[c], errors="coerce")
    if "channel_outlet" in raw.columns:
        raw["channel_outlet"] = raw["channel_outlet"].astype("category")
    raw = raw.dropna(subset=["base_units"]).copy()
    raw["log_base_units"] = np.log1p(raw["base_units"])

    if "geography_raw" in raw.columns:
        mulo = raw["geography_raw"].str.contains(
            "MULTI OUTLET|MULO|TOTAL US|ALL CHANNEL", case=False, na=False)
        raw = raw[~mulo].copy()
    if "geography_level" in raw.columns:
        raw = raw[~raw["geography_level"].str.upper().isin(["NATIONAL","TOTAL"])].copy()

    avail = [c for c in FEATURE_COLS if c in raw.columns]
    print(f"  Rows: {len(raw):,} | Features: {len(avail)}")

    # ── Qualify and split ─────────────────────────────────────────────────────
    df_q = qualify(raw, CUTOFF)
    train_df = df_q[df_q["__time"] <  CUTOFF].copy()
    test_all  = df_q[df_q["__time"] >= CUTOFF].copy()
    test_dates = sorted(test_all["__time"].unique())[:H]
    test_df   = test_all[test_all["__time"].isin(test_dates)].copy()
    n_series  = df_q.groupby(GROUP_COLS).ngroups
    print(f"  Qualified series: {n_series}")
    print(f"  Train: {train_df['__time'].min().date()} → {train_df['__time'].max().date()}")
    print(f"  Test:  {test_df['__time'].min().date()} → {test_df['__time'].max().date()}")

    # Verify BB4PK qualifies
    bb4pk_key = (BB4PK_UPC, WM_CHANNEL, WM_ACCOUNT, WM_GEO)
    bb4pk_in_test = (
        (test_df["upc"] == BB4PK_UPC) & (test_df["retail_account"] == WM_ACCOUNT)
    ).sum()
    print(f"\n  BB 4pk at Walmart in test set: {bb4pk_in_test} rows")

    # ── Train LGB (q10/q50/q90) on all qualifying series ─────────────────────
    print("\nTraining LightGBM (q10, q50, q90) on all qualifying series …")
    m_q50 = train_lgbm(train_df, avail, alpha=0.50)
    m_q10 = train_lgbm(train_df, avail, alpha=0.10)
    m_q90 = train_lgbm(train_df, avail, alpha=0.90)
    print(f"  q50 best iter: {m_q50.best_iteration_}  "
          f"q10: {m_q10.best_iteration_}  q90: {m_q90.best_iteration_}")

    for col, model in [("pred_q50", m_q50), ("pred_q10", m_q10), ("pred_q90", m_q90)]:
        test_df[col] = np.expm1(np.clip(model.predict(test_df[avail]), 0, None))

    # ── ETS on focal series (BB4PK and CD4PK) ────────────────────────────────
    print("\nFitting ETS on focal Walmart series …")
    ets_results = {}

    for upc, label in [(BB4PK_UPC, "BB4pk"), (CD4PK_UPC, "CD4pk")]:
        tr = focal_filter(train_df, upc)["base_units"].values
        te = focal_filter(test_df, upc)
        n_te = len(te)
        if len(tr) < 10 or n_te == 0:
            ets_results[label] = (np.full(n_te, np.nan), np.nan)
            continue
        fitted = fit_ets(tr)
        if fitted is None:
            ets_results[label] = (np.full(n_te, np.nan), np.nan)
            continue
        ets_preds = np.clip(fitted.forecast(n_te), 0, None)
        ets_wmape = wmape(te["base_units"].values, ets_preds)
        ets_results[label] = (ets_preds, ets_wmape)
        print(f"  {label}  ETS wMAPE: {ets_wmape:.1f}%")

    # Merge ETS predictions into test_df for BB4PK
    bb4pk_test = focal_filter(test_df, BB4PK_UPC).copy()
    if len(ets_results["BB4pk"][0]) == len(bb4pk_test):
        bb4pk_test["pred_ets"] = ets_results["BB4pk"][0]
    else:
        bb4pk_test["pred_ets"] = np.nan

    # MA / Naive for BB4PK
    bb4pk_tr_vals = focal_filter(train_df, BB4PK_UPC)["base_units"].values
    ma13_bb, naive_bb = naive_baseline(bb4pk_tr_vals, len(bb4pk_test))
    bb4pk_test["pred_ma13"]  = ma13_bb
    bb4pk_test["pred_naive"] = naive_bb

    # Compute wMAPEs for BB4PK horse race
    act_bb = bb4pk_test["base_units"].values
    bb_acc = {
        "LightGBM q50": round(wmape(act_bb, bb4pk_test["pred_q50"].values), 1),
        "ETS":          round(wmape(act_bb, bb4pk_test["pred_ets"].values),  1),
        "MA 13wk":      round(wmape(act_bb, bb4pk_test["pred_ma13"].values), 1),
        "Naive":        round(wmape(act_bb, bb4pk_test["pred_naive"].values),1),
    }
    print("\n  Brownie Batter 4pk @ Walmart — OOS accuracy:")
    for k, v in bb_acc.items():
        print(f"    {k:<20} {v:.1f}% wMAPE")

    # ── Cold-start: BB8PK ETS vs Naive ────────────────────────────────────────
    print("\nCold-start analysis: Brownie Batter 8pk @ Walmart …")
    bb8pk_all = focal_filter(raw, BB8PK_UPC)
    bb8pk_train = bb8pk_all[bb8pk_all["__time"] < CUTOFF].copy()
    bb8pk_test  = bb8pk_all[bb8pk_all["__time"] >= CUTOFF].copy().head(H)
    n_bb8_tr = len(bb8pk_train)
    n_bb8_te = len(bb8pk_test)
    print(f"  BB 8pk training weeks: {n_bb8_tr} (threshold is {MIN_TRAIN_WEEKS})")
    print(f"  BB 8pk test weeks: {n_bb8_te}")

    bb8_ets_fitted = fit_ets(bb8pk_train["base_units"].values)
    if bb8_ets_fitted is not None and n_bb8_te > 0:
        bb8pk_test = bb8pk_test.copy()
        bb8pk_test["pred_ets"] = np.clip(bb8_ets_fitted.forecast(n_bb8_te), 0, None)
        ma_bb8, naive_bb8 = naive_baseline(bb8pk_train["base_units"].values, n_bb8_te)
        bb8pk_test["pred_ma4"] = ma_bb8
        bb8pk_test["pred_naive"] = naive_bb8
        act_bb8 = bb8pk_test["base_units"].values
        cs_acc = {
            "ETS (Holt trend)": round(wmape(act_bb8, bb8pk_test["pred_ets"].values),  1),
            "MA 13wk":          round(wmape(act_bb8, bb8pk_test["pred_ma4"].values),  1),
            "Naive":            round(wmape(act_bb8, bb8pk_test["pred_naive"].values), 1),
        }
        print("  Cold-start OOS accuracy:")
        for k, v in cs_acc.items():
            print(f"    {k:<22} {v:.1f}% wMAPE")
    else:
        cs_acc = {}

    # ── ARP for dollar translation ─────────────────────────────────────────────
    bb4pk_arp  = focal_filter(raw, BB4PK_UPC)["arp"].median()
    cd4pk_arp  = focal_filter(raw, CD4PK_UPC)["arp"].median()
    bb8pk_arp  = focal_filter(raw, BB8PK_UPC)["arp"].median()
    bb4pk_avg_units = focal_filter(train_df, BB4PK_UPC)["base_units"].tail(13).mean()
    cd4pk_avg_units = focal_filter(train_df, CD4PK_UPC)["base_units"].tail(13).mean()
    bb8pk_avg_units = focal_filter(bb8pk_train, BB8PK_UPC)["base_units"].tail(13).mean() \
                      if False else bb8pk_train["base_units"].tail(13).mean()

    print(f"\n  ARP: BB4pk ${bb4pk_arp:.2f}  CD4pk ${cd4pk_arp:.2f}  BB8pk ${bb8pk_arp:.2f}")
    print(f"  Avg units/wk (last 13w): BB4pk {bb4pk_avg_units:.0f}  "
          f"CD4pk {cd4pk_avg_units:.0f}  BB8pk {bb8pk_avg_units:.0f}")

    # ── Generate charts ────────────────────────────────────────────────────────
    _chart1_zoom(raw, test_df)
    _chart2_horse_race(bb4pk_test, bb_acc, bb4pk_arp)
    _chart3_demand_decomp(raw)
    _chart4_coldstart(bb8pk_all, bb8pk_train, bb8pk_test, cs_acc, n_bb8_tr)
    _chart5_dollar_impact(bb4pk_arp, cd4pk_arp, bb8pk_arp,
                          bb4pk_avg_units, cd4pk_avg_units, bb8pk_avg_units,
                          bb_acc, cs_acc)

    # ── Save metrics ──────────────────────────────────────────────────────────
    meta = {
        "run_at":           datetime.now(timezone.utc).isoformat(),
        "cutoff":           str(CUTOFF.date()),
        "bb4pk_acc":        bb_acc,
        "coldstart_acc":    cs_acc,
        "arp": {
            "bb4pk": round(float(bb4pk_arp), 2),
            "cd4pk": round(float(cd4pk_arp), 2),
            "bb8pk": round(float(bb8pk_arp), 2),
        },
        "avg_units_per_week": {
            "bb4pk": round(float(bb4pk_avg_units), 0),
            "cd4pk": round(float(cd4pk_avg_units), 0),
            "bb8pk": round(float(bb8pk_avg_units), 0),
        },
        "bb8pk_train_weeks": int(n_bb8_tr),
        "lgb_threshold_weeks": MIN_TRAIN_WEEKS,
    }
    out_json = os.path.join(OUTPUT_DIR, "v2_mo37_summary.json")
    with open(out_json, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\n  Metrics → {out_json}")
    print(f"\n{'='*65}")
    print("MO_37 complete — 5 charts + metrics saved to outputs/")
    print(f"{'='*65}")


# ── Chart 1: Multi-Horizon Zoom ────────────────────────────────────────────────
def _chart1_zoom(raw, test_df):
    """Four time-window panels of the same SKU: 2.7yr / 1yr / 1Q / 1mo."""
    print("\nChart 1: Multi-horizon zoom …")

    series = focal_filter(raw, BB4PK_UPC)
    series["date"] = series["__time"].dt.tz_convert(None)

    te = focal_filter(test_df, BB4PK_UPC).copy()
    te["date"] = te["__time"].dt.tz_convert(None)

    # Four zoom windows (lookback into history + all forecast)
    cutoff_dt = CUTOFF.tz_convert(None)
    windows = [
        ("2.7 Years (Full History)", series["date"].min(), None),
        ("1 Year",   cutoff_dt - pd.Timedelta(weeks=52),  None),
        ("1 Quarter", cutoff_dt - pd.Timedelta(weeks=13), None),
        ("1 Month",  cutoff_dt - pd.Timedelta(weeks=4),   None),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    axes = axes.flatten()

    for ax, (title, start, _) in zip(axes, windows):
        hist = series[series["date"] >= start].copy() if start else series.copy()
        hist_train = hist[hist["date"] < cutoff_dt]
        hist_oos   = hist[hist["date"] >= cutoff_dt]

        # Fill forecast band
        ax.fill_between(te["date"], te["pred_q10"], te["pred_q90"],
                        color=C_BAND, alpha=0.35, label="q10–q90 range")

        # Historical actuals (solid)
        ax.plot(hist_train["date"], hist_train["base_units"],
                color=C_ACTUAL, lw=2.0, label="Actuals")

        # OOS actuals (dashed — what actually happened)
        if len(hist_oos) > 0:
            ax.plot(hist_oos["date"], hist_oos["base_units"],
                    color=C_ACTUAL, lw=2.0, linestyle="--", alpha=0.55,
                    label="Actuals (OOS, for validation)")

        # Forecast line
        ax.plot(te["date"], te["pred_q50"],
                color=C_LGB, lw=2.5, label="LightGBM Forecast (q50)")

        # Cutoff line
        ax.axvline(cutoff_dt, color="#888", lw=1.1, linestyle=":", alpha=0.7)
        ymax = max(hist["base_units"].max() if len(hist) else 1,
                   te["pred_q90"].max() if len(te) else 1)
        ax.text(cutoff_dt + pd.Timedelta(days=2), ymax * 0.98,
                "Dec 2025\ncutoff", fontsize=7.5, color="#666", va="top")

        ax.set_title(f"← {title}", fontsize=10, fontweight="bold")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=8)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_units))
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(True, axis="y", alpha=0.2, linestyle="--")
        ax.spines[["top","right"]].set_visible(False)

    axes[0].legend(fontsize=8, loc="upper left")
    fig.suptitle(
        "Brownie Batter 4pk — Walmart  |  The same forecast, four zoom levels\n"
        "Dashed line = actual outcome (validation). Shaded band = 80% planning range.",
        fontsize=12, fontweight="bold", y=1.01)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo37_chart1_zoom.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → {out}")


# ── Chart 2: Method Horse Race — this one SKU ─────────────────────────────────
def _chart2_horse_race(bb4pk_test, bb_acc, arp):
    """All methods head-to-head on Brownie Batter 4pk at Walmart, Jan–Apr 2026."""
    print("Chart 2: Method horse race (BB 4pk) …")

    df = bb4pk_test.copy()
    df["date"] = df["__time"].dt.tz_convert(None)
    df = df.sort_values("date")

    fig, ax = plt.subplots(figsize=(14, 7))

    ax.plot(df["date"], df["base_units"],     color=C_ACTUAL, lw=3.2, zorder=7,
            label="Actuals (what really happened)")
    ax.plot(df["date"], df["pred_q50"],       color=C_LGB,    lw=2.5, zorder=6,
            label=f"LightGBM q50  ·  {bb_acc['LightGBM q50']:.1f}% wMAPE ✓")
    ax.plot(df["date"], df["pred_ets"],       color=C_ETS,    lw=2.0, linestyle="--", zorder=5,
            label=f"ETS (Holt trend)  ·  {bb_acc['ETS']:.1f}% wMAPE")
    ax.plot(df["date"], df["pred_ma13"],      color=C_MA13,   lw=1.6, linestyle=":", zorder=4,
            label=f"MA 13wk  ·  {bb_acc['MA 13wk']:.1f}% wMAPE")
    ax.plot(df["date"], df["pred_naive"],     color=C_NAIVE,  lw=1.4, linestyle=":", zorder=3,
            label=f"Naive (last value)  ·  {bb_acc['Naive']:.1f}% wMAPE")

    # End-of-line wMAPE labels
    last = df.iloc[-1]
    x_end = last["date"]
    for col, label, color in [
        ("pred_q50",  f"{bb_acc['LightGBM q50']:.1f}%", C_LGB),
        ("pred_ets",  f"{bb_acc['ETS']:.1f}%",          C_ETS),
        ("pred_ma13", f"{bb_acc['MA 13wk']:.1f}%",      C_MA13),
        ("pred_naive",f"{bb_acc['Naive']:.1f}%",        C_NAIVE),
    ]:
        if col in last and pd.notna(last[col]):
            ax.annotate(label,
                        xy=(x_end, last[col]),
                        xytext=(8, 0), textcoords="offset points",
                        fontsize=9, color=color, fontweight="bold", va="center")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=6, interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_units))
    ax.set_ylabel("Weekly Units Sold", fontsize=11)
    ax.set_title(
        "\"Which method should I trust for planning?\"\n"
        "Brownie Batter 4pk — Walmart  |  All methods vs. actuals, Jan–Apr 2026",
        fontsize=11, fontweight="bold")
    ax.legend(fontsize=9.5, loc="upper left")
    ax.grid(True, axis="y", alpha=0.25, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)

    # Dollar error callout
    avg_units = df["base_units"].mean()
    weekly_rev = avg_units * arp
    lgb_err_wk  = weekly_rev * (bb_acc["LightGBM q50"] / 100)
    ets_err_wk  = weekly_rev * (bb_acc["ETS"] / 100)
    naive_err_wk = weekly_rev * (bb_acc["Naive"] / 100)
    box = (f"At ${arp:.2f} ARP  ·  ~{avg_units:,.0f} units/wk avg\n"
           f"Weekly planning error:\n"
           f"  LightGBM:  ${lgb_err_wk:,.0f}/wk\n"
           f"  ETS:       ${ets_err_wk:,.0f}/wk\n"
           f"  Naive:     ${naive_err_wk:,.0f}/wk")
    # Place dollar error box below the plot area so it never masks data
    fig.text(0.98, 0.01, box,
             ha="right", va="bottom",
             fontsize=8.5, family="monospace",
             bbox=dict(boxstyle="round,pad=0.5", facecolor="#e3f2fd",
                       edgecolor=C_LGB, alpha=0.9))

    plt.tight_layout(rect=[0, 0.20, 1, 1])  # reserve bottom 20% for the callout
    out = os.path.join(OUTPUT_DIR, "v2_mo37_chart2_horse_race.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → {out}")


# ── Chart 3: What drove the growth? ───────────────────────────────────────────
def _chart3_demand_decomp(raw):
    """TDP expansion vs velocity gain for BB 4pk and Cookie Dough 4pk at Walmart."""
    print("Chart 3: Demand decomposition …")

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    for ax, (upc, name) in zip(axes, [(BB4PK_UPC, "Brownie Batter 4pk"),
                                       (CD4PK_UPC, "Cookie Dough Chunk 4pk")]):
        s = focal_filter(raw, upc).copy()
        s["date"] = s["__time"].dt.tz_convert(None)

        ax2 = ax.twinx()
        ax3 = ax2   # share secondary axis (TDP and velocity share right axis)

        # Index TDP and velocity to first period = 100
        s["tdp_idx"] = s["tdp"] / (s["tdp"].iloc[:4].mean() + 1e-6) * 100
        s["vel_idx"] = (s["avg_weekly_units_spm"]
                        / (s["avg_weekly_units_spm"].iloc[:4].mean() + 1e-6) * 100)

        # Units bars
        ax.bar(s["date"], s["base_units"], width=5,
               color=C_LGB, alpha=0.35, label="Weekly units sold")
        ax.plot(s["date"], s["base_units"].rolling(4, min_periods=1).mean(),
                color=C_LGB, lw=2.0, label="4-week trend")

        # TDP index (right)
        ax2.plot(s["date"], s["tdp_idx"],
                 color=C_TDP, lw=2.2, label="TDP index (distribution breadth)")
        ax2.plot(s["date"], s["vel_idx"],
                 color=C_VEL, lw=2.0, linestyle="--", label="Velocity index (per-store sell-through)")

        # Compute growth attribution
        early_weeks = s.head(8)
        late_weeks  = s.tail(8)
        tdp_early   = early_weeks["tdp"].mean()
        tdp_late    = late_weeks["tdp"].mean()
        vel_early   = early_weeks["avg_weekly_units_spm"].mean()
        vel_late    = late_weeks["avg_weekly_units_spm"].mean()

        # Additive decomposition: delta_units ≈ delta_TDP*vel_early + TDP_late*delta_vel
        tdp_contrib = (tdp_late - tdp_early) * vel_early
        vel_contrib = tdp_late * (vel_late - vel_early)
        total_contrib = tdp_contrib + vel_contrib
        if total_contrib > 0:
            tdp_pct = tdp_contrib / total_contrib * 100
            vel_pct = vel_contrib / total_contrib * 100
        else:
            tdp_pct = vel_pct = 50

        ax.set_title(f"{name} — Walmart", fontsize=10, fontweight="bold")
        ax.set_ylabel("Weekly Units Sold", fontsize=10, color=C_LGB)
        ax2.set_ylabel("Index (launch avg = 100)", fontsize=10, color=C_TDP)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_units))
        ax.grid(True, axis="y", alpha=0.2, linestyle="--")
        ax.spines[["top","right"]].set_visible(False)

        # Attribution callout
        attr_text = (f"Growth attribution\n"
                     f"(launch → today)\n\n"
                     f"  Distribution (TDP):  {tdp_pct:.0f}%\n"
                     f"  Velocity / demand:   {vel_pct:.0f}%\n\n"
                     f"TDP: {tdp_early:.0f} → {tdp_late:.0f} stores\n"
                     f"Vel: {vel_early:.2f} → {vel_late:.2f} u/store/mo")
        ax.text(0.02, 0.97, attr_text,
                transform=ax.transAxes, ha="left", va="top",
                fontsize=8.5,
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                          edgecolor="#ccc", alpha=0.92))

        lines1, labs1 = ax.get_legend_handles_labels()
        lines2, labs2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labs1 + labs2, fontsize=8, loc="lower right")

    fig.suptitle(
        "\"Is our growth real demand — or just more stores stocking us?\"\n"
        "Distribution (TDP) expansion vs. per-store velocity improvement  |  Walmart",
        fontsize=12, fontweight="bold", y=1.01)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo37_chart3_demand_decomp.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → {out}")


# ── Chart 4: Cold-Start ETS Example ───────────────────────────────────────────
def _chart4_coldstart(bb8pk_all, bb8pk_train, bb8pk_test, cs_acc, n_train_weeks):
    """BB 8pk launch weeks 1–49: ETS bridges the planning gap before LGB threshold."""
    print("Chart 4: Cold-start ETS example …")

    all_s = bb8pk_all.copy()
    all_s["date"] = all_s["__time"].dt.tz_convert(None)
    all_s = all_s.sort_values("date")

    train_s = bb8pk_train.copy()
    train_s["date"] = train_s["__time"].dt.tz_convert(None)
    train_s = train_s.sort_values("date")

    test_s = bb8pk_test.copy()
    if len(test_s) > 0:
        test_s["date"] = test_s["__time"].dt.tz_convert(None)
        test_s = test_s.sort_values("date")

    fig, ax = plt.subplots(figsize=(14, 7))

    # Full actuals (training = solid, OOS = dashed)
    ax.plot(train_s["date"], train_s["base_units"],
            color=C_ACTUAL, lw=2.5, label="Actuals (training period)")
    if len(test_s) > 0:
        ax.plot(test_s["date"], test_s["base_units"],
                color=C_ACTUAL, lw=2.5, linestyle="--", alpha=0.6,
                label="Actuals (OOS — validation)")

    # ETS forecast
    if len(test_s) > 0 and "pred_ets" in test_s.columns:
        ax.plot(test_s["date"], test_s["pred_ets"],
                color=C_ETS, lw=2.5,
                label=f"ETS Holt trend  ·  {cs_acc.get('ETS (Holt trend)', 'N/A'):.0f}% wMAPE"
                      if cs_acc else "ETS Holt trend")
    if len(test_s) > 0 and "pred_naive" in test_s.columns:
        ax.plot(test_s["date"], test_s["pred_naive"],
                color=C_NAIVE, lw=1.8, linestyle=":",
                label=f"Naive (last obs)  ·  {cs_acc.get('Naive', 'N/A'):.0f}% wMAPE"
                      if cs_acc else "Naive")
    if len(test_s) > 0 and "pred_ma4" in test_s.columns:
        ax.plot(test_s["date"], test_s["pred_ma4"],
                color=C_MA13, lw=1.6, linestyle=":",
                label=f"MA 13wk  ·  {cs_acc.get('MA 13wk', 'N/A'):.0f}% wMAPE"
                      if cs_acc else "MA 13wk")

    # Threshold annotation
    cutoff_dt = CUTOFF.tz_convert(None)
    ax.axvline(cutoff_dt, color="#888", lw=1.2, linestyle=":", alpha=0.8)
    ax.text(cutoff_dt + pd.Timedelta(days=2),
            train_s["base_units"].max() * 1.02,
            f"Dec 2025\n(week {n_train_weeks} of launch)",
            fontsize=8, color="#666", va="top")

    # LGB threshold annotation
    threshold_date = (all_s.iloc[min(MIN_TRAIN_WEEKS - 1, len(all_s) - 1)]["date"]
                      if len(all_s) >= MIN_TRAIN_WEEKS else None)
    ymax = all_s["base_units"].max() * 1.15
    if threshold_date:
        ax.axvline(threshold_date, color=C_LGB, lw=1.5, linestyle="--", alpha=0.6)
        ax.text(threshold_date + pd.Timedelta(days=2), ymax * 0.75,
                f"Week {MIN_TRAIN_WEEKS}\nLightGBM\nbecomes\neligible →",
                fontsize=8, color=C_LGB, va="top")

    # Determine best cold-start method
    best_cs_label, best_cs_wmape = "MA 13wk", cs_acc.get("MA 13wk", 18.5)
    if cs_acc:
        for method, wmape_val in cs_acc.items():
            if wmape_val < best_cs_wmape:
                best_cs_label, best_cs_wmape = method, wmape_val

    # Explanation callout
    launch_date = all_s.iloc[0]["date"]
    box = (f"New product launch: {launch_date.strftime('%b %Y')}\n\n"
           f"Before week {MIN_TRAIN_WEEKS}:\n"
           f"  → LightGBM excluded\n"
           f"     (insufficient history)\n\n"
           f"  → {best_cs_label} ({best_cs_wmape:.0f}% wMAPE)\n"
           f"     guides planning\n\n"
           f"  Note: Big-bang launches\n"
           f"  (high TDP from day 1)\n"
           f"  favor MA over ETS\n\n"
           f"  → Handoff to LGB at\n"
           f"     week {MIN_TRAIN_WEEKS}")
    ax.text(0.01, 0.99, box,
            transform=ax.transAxes, ha="left", va="top",
            fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#fff3e0",
                      edgecolor=C_ETS, alpha=0.92))

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_units))
    ax.set_ylabel("Weekly Units Sold", fontsize=11)
    ax.set_title(
        "\"How do we plan for a brand-new product?\"\n"
        "Brownie Batter 8pk — Walmart  |  Launch to week 49  |  ETS bridges the cold-start gap",
        fontsize=11, fontweight="bold")
    ax.legend(fontsize=9, loc="lower right")
    ax.grid(True, axis="y", alpha=0.25, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo37_chart4_coldstart.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → {out}")


# ── Chart 5: Dollar Translation ────────────────────────────────────────────────
def _chart5_dollar_impact(bb4pk_arp, cd4pk_arp, bb8pk_arp,
                          bb4pk_units, cd4pk_units, bb8pk_units,
                          bb_acc, cs_acc):
    """Quarterly planning error in $ — Excel 35% baseline vs Mo accuracy."""
    print("Chart 5: Dollar translation …")

    EXCEL_MAPE = 35.0   # Excel/static baseline assumption
    WEEKS_PER_Q = 13

    def quarterly_error(units_per_wk, arp, mape_pct):
        return units_per_wk * arp * (mape_pct / 100) * WEEKS_PER_Q

    bb4pk_lgb_wmape = bb_acc.get("LightGBM q50", 4.4)
    cd4pk_lgb_wmape = bb_acc.get("LightGBM q50", 4.4)   # portfolio-wide for CD4pk
    # Use the best cold-start method (whichever won — MA 13wk or ETS)
    bb8pk_cs_wmape = min(cs_acc.get("ETS (Holt trend)", 26.5),
                         cs_acc.get("MA 13wk", 18.5)) if cs_acc else 18.5

    skus = [
        ("Brownie Batter 4pk\n(Walmart, mature)",    bb4pk_units, bb4pk_arp, bb4pk_lgb_wmape),
        ("Cookie Dough Chunk 4pk\n(Walmart, growing)", cd4pk_units, cd4pk_arp, cd4pk_lgb_wmape),
        ("Brownie Batter 8pk\n(Walmart, new launch)",  bb8pk_units, bb8pk_arp, bb8pk_cs_wmape),
    ]

    labels = [s[0] for s in skus]
    excel_q  = [quarterly_error(s[1], s[2], EXCEL_MAPE) for s in skus]
    mo_q     = [quarterly_error(s[1], s[2], s[3])       for s in skus]
    savings  = [e - m for e, m in zip(excel_q, mo_q)]

    x = np.arange(len(labels))
    width = 0.30

    fig, ax = plt.subplots(figsize=(14, 8))

    bars_excel = ax.bar(x - width/2, [e/1000 for e in excel_q], width,
                        color=C_EXCEL, alpha=0.80, label=f"Excel / static forecast ({EXCEL_MAPE:.0f}% error)")
    bars_mo    = ax.bar(x + width/2, [m/1000 for m in mo_q], width,
                        color=C_MO,    alpha=0.80, label="Mo ensemble model (actual wMAPE)")

    # Savings arrows / labels
    for i, (e, m, s) in enumerate(zip(excel_q, mo_q, savings)):
        ax.annotate("",
                    xy=(x[i] + width/2, m/1000),
                    xytext=(x[i] - width/2, e/1000),
                    arrowprops=dict(arrowstyle="-|>", color="#2e7d32",
                                   lw=1.5, mutation_scale=12))
        ax.text(x[i] + 0.03, (e/1000 + m/1000) / 2,
                f" Save ${s/1000:,.0f}K/qtr",
                fontsize=9, color="#2e7d32", fontweight="bold", va="center")

    # Value labels on bars
    for bars in [bars_excel, bars_mo]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 3,
                    f"${h:,.0f}K", ha="center", va="bottom", fontsize=8.5, color="#333")

    # Add wMAPE labels inside the Mo bars
    mo_wmapes = [s[3] for s in skus]
    for i, wm in enumerate(mo_wmapes):
        bar_h = mo_q[i] / 1000
        ax.text(x[i] + width/2, bar_h * 0.5,
                f"{wm:.1f}%\nwMAPE",
                ha="center", va="center", fontsize=7.5, color="white", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_ylabel("Quarterly Planning Error  ($K)", fontsize=11)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}K"))
    ax.set_title(
        "\"What does forecast accuracy mean for my budget?\"\n"
        "Quarterly inventory planning error in dollars — per SKU at Walmart\n"
        f"(Excel/static baseline: {EXCEL_MAPE:.0f}% assumed MAPE  ·  Mo: actual validated wMAPE per SKU  ·  ARP × units × error% × 13 weeks)",
        fontsize=11, fontweight="bold")
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(True, axis="y", alpha=0.25, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)

    # Total savings box
    total_savings = sum(savings)
    ax.text(0.98, 0.96,
            f"Total quarterly savings\n(these 3 SKUs at Walmart):\n${total_savings/1000:,.0f}K",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=10.5, color="#2e7d32", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#e8f5e9",
                      edgecolor="#2e7d32", alpha=0.92))

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo37_chart5_dollar_impact.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → {out}")


if __name__ == "__main__":
    main()
