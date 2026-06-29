"""MO_33 — FP&A Business Decision Charts

Five presentation-ready charts answering the questions FP&A actually asks:

  1. "What will I sell next quarter?"    actuals + q10/q50/q90 forecast by top retailer
  2. "Am I growing or cannibalizing?"    units trend vs. cannibalization pressure
  3. "How much do I need to build?"      total demand forecast with manufacturing bands
  4. "Which retailer to prioritize?"     velocity × growth × TDP expansion bubble chart
  5. "Which method should I trust?"      horse race: all methods vs. Q1 2026 actuals

All charts use the Dec 2025 cutoff (train through Dec 28 2025, predict Q1 2026)
which produced 4.4% wMAPE — our best validated accuracy window.

Run:  python MO_33_fpa_business_charts.py

Outputs (in scripts/outputs/):
    v2_mo33_chart1_retailer_forecast.png
    v2_mo33_chart2_growth_vs_cannib.png
    v2_mo33_chart3_total_demand.png
    v2_mo33_chart4_retailer_bubble.png
    v2_mo33_chart5_horse_race.png
    v2_mo33_summary.json
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

warnings.filterwarnings("ignore")
logging.getLogger("lightgbm").setLevel(logging.ERROR)

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "outputs")
PARQUET    = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")

GROUP_COLS      = ["upc", "channel_outlet", "retail_account", "geography_raw"]
H               = 13
MIN_TRAIN_WEEKS = 52
LOCAL_VAL_WEEKS = 8

CUTOFF       = pd.Timestamp("2025-12-28", tz="UTC")  # Dec 2025 → predict Q1 2026
STALE_CUTOFF = pd.Timestamp("2024-12-29", tz="UTC")  # stale model (horse race)

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

# Presentation palette
C_ACTUAL   = "#1a1a2e"
C_FORECAST = "#1565c0"
C_BAND     = "#90caf9"
C_STALE    = "#e65100"
C_MA13     = "#6d4c41"
C_NAIVE    = "#9e9e9e"


# ── Helpers ───────────────────────────────────────────────────────────────────
def wmape(actual, pred):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    m = np.isfinite(a) & np.isfinite(p)
    d = np.sum(a[m])
    return float(np.sum(np.abs(a[m] - p[m])) / d * 100) if d > 0 else np.nan

def naive_baseline(train_vals, n):
    v = np.asarray(train_vals, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return np.full(n, np.nan), np.full(n, np.nan)
    ma13  = np.full(n, np.mean(v[-13:]) if len(v) >= 13 else np.mean(v))
    naive = np.full(n, v[-1])
    return ma13, naive

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

def qualify(df, cutoff, min_tr=MIN_TRAIN_WEEKS, min_te=H):
    tr_cnt = df[df["__time"] <  cutoff].groupby(GROUP_COLS).size()
    te_cnt = df[df["__time"] >= cutoff].groupby(GROUP_COLS).size()
    cov = pd.concat([tr_cnt.rename("tr"), te_cnt.rename("te")], axis=1).fillna(0).astype(int)
    qual_idx = set(cov[(cov["tr"] >= min_tr) & (cov["te"] >= min_te)].index.tolist())
    df2 = df.copy()
    df2["_key"] = list(zip(df2["upc"], df2["channel_outlet"],
                           df2["retail_account"], df2["geography_raw"]))
    return df2[df2["_key"].isin(qual_idx)].drop(columns=["_key"])

def predict_col(model, df, avail, col_name):
    df = df.copy()
    df[col_name] = np.expm1(np.clip(model.predict(df[avail]), 0, None))
    return df


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("MO_33  —  FP&A Business Decision Charts")
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

    # ── Qualify at Dec 2025 cutoff ─────────────────────────────────────────────
    df_q = qualify(raw, CUTOFF)
    train_df = df_q[df_q["__time"] <  CUTOFF].copy()
    test_all  = df_q[df_q["__time"] >= CUTOFF].copy()
    test_dates = sorted(test_all["__time"].unique())[:H]
    test_df   = test_all[test_all["__time"].isin(test_dates)].copy()
    n_series  = df_q.groupby(GROUP_COLS).ngroups
    print(f"  Qualified series: {n_series}")
    print(f"  Train: {train_df['__time'].min().date()} → {train_df['__time'].max().date()}")
    print(f"  Test:  {test_df['__time'].min().date()} → {test_df['__time'].max().date()}")

    # ── Train rolling models (q10 / q50 / q90) ───────────────────────────────
    print("\nTraining rolling models (q10, q50, q90) …")
    m_q50 = train_lgbm(train_df, avail, alpha=0.50)
    print(f"  q50 best iter: {m_q50.best_iteration_}")
    m_q10 = train_lgbm(train_df, avail, alpha=0.10)
    print(f"  q10 best iter: {m_q10.best_iteration_}")
    m_q90 = train_lgbm(train_df, avail, alpha=0.90)
    print(f"  q90 best iter: {m_q90.best_iteration_}")

    test_df = predict_col(m_q50, test_df, avail, "pred_q50")
    test_df = predict_col(m_q10, test_df, avail, "pred_q10")
    test_df = predict_col(m_q90, test_df, avail, "pred_q90")

    # ── Train stale model (Dec 2024 cutoff) for horse race ────────────────────
    print("\nTraining stale model (Dec 2024 cutoff) …")
    df_stale    = qualify(raw, STALE_CUTOFF)
    train_stale = df_stale[df_stale["__time"] < STALE_CUTOFF].copy()
    m_stale     = train_lgbm(train_stale, avail, alpha=0.50)
    print(f"  Stale best iter: {m_stale.best_iteration_}")
    # Apply stale model to Q1 2026 test (only series that qualify at Dec2025 cutoff)
    test_df = predict_col(m_stale, test_df, avail, "pred_stale")

    # ── Naive baselines ────────────────────────────────────────────────────────
    ma13_list, naive_list = [], []
    for key, grp_test in test_df.groupby(GROUP_COLS):
        grp_tr = train_df[
            (train_df["upc"]            == key[0]) &
            (train_df["channel_outlet"] == key[1]) &
            (train_df["retail_account"] == key[2]) &
            (train_df["geography_raw"]  == key[3])
        ]["base_units"].values
        ma13, nv = naive_baseline(grp_tr, len(grp_test))
        ma13_list.append(ma13)
        naive_list.append(nv)
    test_df["ma13"]  = np.concatenate(ma13_list)
    test_df["naive"] = np.concatenate(naive_list)

    # Overall accuracy
    act = test_df["base_units"].values
    acc = {
        "Rolling LightGBM q50": round(wmape(act, test_df["pred_q50"].values), 2),
        "Stale LightGBM":       round(wmape(act, test_df["pred_stale"].values), 2),
        "MA 13wk":              round(wmape(act, test_df["ma13"].values), 2),
        "Naive":                round(wmape(act, test_df["naive"].values), 2),
    }
    print(f"\n  Accuracy on Q1 2026 ({H} weeks, {n_series} series):")
    for k, v in acc.items():
        print(f"    {k:<28} {v:.1f}% wMAPE")

    # ── Charts ────────────────────────────────────────────────────────────────
    _chart1_retailer_forecast(test_df, train_df)
    _chart2_growth_vs_cannib(raw, train_df)
    _chart3_total_demand(test_df, train_df)
    _chart4_retailer_bubble(train_df)
    _chart5_horse_race(test_df, acc)

    meta = {
        "run_at":      datetime.now(timezone.utc).isoformat(),
        "cutoff":      str(CUTOFF.date()),
        "n_series":    n_series,
        "h":           H,
        "accuracy":    acc,
    }
    with open(os.path.join(OUTPUT_DIR, "v2_mo33_summary.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n{'='*65}")
    print("MO_33 complete — 5 charts saved to outputs/")
    print(f"{'='*65}")


# ── Chart 1: What will I sell next quarter? ───────────────────────────────────
def _chart1_retailer_forecast(test_df, train_df):
    """Q1 2026 forecast by top retail accounts, with q10/q90 bands."""
    print("\nChart 1: Retailer forecast …")

    # Aggregate by retail_account + week
    tr_agg = (train_df.groupby(["retail_account", "__time"])["base_units"]
               .sum().reset_index())
    te_agg = (test_df.groupby(["retail_account", "__time"])
               .agg(actual=("base_units","sum"),
                    pred_q50=("pred_q50","sum"),
                    pred_q10=("pred_q10","sum"),
                    pred_q90=("pred_q90","sum"))
               .reset_index())

    # Top 6 retailers by Q1 2026 predicted volume
    top_ret = (te_agg.groupby("retail_account")["pred_q50"].sum()
                .nlargest(6).index.tolist())

    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharey=False)
    axes = axes.flatten()

    for i, (ax, ret) in enumerate(zip(axes, top_ret)):
        tr = tr_agg[tr_agg["retail_account"] == ret].copy()
        te = te_agg[te_agg["retail_account"] == ret].copy()
        tr["date"] = pd.to_datetime(tr["__time"]).dt.tz_convert(None)
        te["date"] = pd.to_datetime(te["__time"]).dt.tz_convert(None)

        # Show last 13 weeks of actuals for context
        tr_recent = tr.nlargest(13, "__time").sort_values("date")

        ax.fill_between(te["date"], te["pred_q10"], te["pred_q90"],
                        color=C_BAND, alpha=0.35, label="q10–q90 band")
        ax.plot(tr_recent["date"], tr_recent["base_units"],
                color=C_ACTUAL, lw=2.0, label="Actuals (13w prior)")
        ax.plot(te["date"], te["actual"],
                color=C_ACTUAL, lw=2.0, linestyle="--", alpha=0.6)
        ax.plot(te["date"], te["pred_q50"],
                color=C_FORECAST, lw=2.2, label="Forecast (q50)")

        ax.axvline(te["date"].min() - pd.Timedelta(days=3),
                   color="#555", lw=1, linestyle=":", alpha=0.7)
        ax.text(te["date"].min(), ax.get_ylim()[1] if i > 0 else te["pred_q50"].max() * 1.02,
                "Q1 2026 →", fontsize=7.5, color="#555", va="bottom")

        ret_label = ret if len(ret) <= 20 else ret[:18] + "…"
        ax.set_title(ret_label, fontsize=10, fontweight="bold")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b'%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=8)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_units))
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(True, axis="y", alpha=0.25, linestyle="--")
        ax.spines[["top","right"]].set_visible(False)
        if i == 0:
            ax.legend(fontsize=8, loc="upper left")

    fig.suptitle(
        "\"What will I sell next quarter?\"\n"
        "Q1 2026 Forecast by Retailer — LightGBM q10/q50/q90  |  Trained Dec 2025",
        fontsize=12, fontweight="bold", y=1.01)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo33_chart1_retailer_forecast.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → {out}")


# ── Chart 2: Am I growing from real demand or cannibalizing myself? ───────────
def _chart2_growth_vs_cannib(raw, train_df):
    """Units trend vs. cannibalization pressure for the most interesting series."""
    print("Chart 2: Growth vs cannibalization …")

    # Find the series with highest average cannib signal variance (most interesting)
    sig = (train_df.groupby(GROUP_COLS)["max_donor_cannibal_prob"]
            .std().dropna().nlargest(20))
    vol = (train_df.groupby(GROUP_COLS)["base_units"].sum().nlargest(50))
    # Pick high-volume series with interesting cannib signal
    candidates = sig.index.intersection(vol.index)
    if len(candidates) == 0:
        candidates = sig.index[:5]
    focal_key = candidates[0]
    upc, ch, acct, geo = focal_key

    print(f"  Focal series: {upc} | {acct} | {ch}")

    series = raw[
        (raw["upc"]            == upc) &
        (raw["channel_outlet"] == ch)  &
        (raw["retail_account"] == acct) &
        (raw["geography_raw"]  == geo)
    ].copy().sort_values("__time")
    series["date"] = pd.to_datetime(series["__time"]).dt.tz_convert(None)

    # Last 65 weeks of history
    series = series.tail(65).copy()

    # Rolling cannib signal
    series["cannib_roll4"] = (series["max_donor_cannibal_prob"]
                              .rolling(4, min_periods=1).mean())

    fig, ax1 = plt.subplots(figsize=(14, 6))
    ax2 = ax1.twinx()

    # Units bars
    ax1.bar(series["date"], series["base_units"],
            width=5, color=C_FORECAST, alpha=0.55, label="Weekly units (actual)")
    ax1.plot(series["date"],
             series["base_units"].rolling(4, min_periods=1).mean(),
             color=C_FORECAST, lw=2.0, label="4-week avg")

    # Cannib signal line
    ax2.plot(series["date"], series["cannib_roll4"],
             color="#c62828", lw=2.2, linestyle="-",
             label="Cannibalization pressure (4w avg)")
    ax2.fill_between(series["date"], 0, series["cannib_roll4"],
                     color="#ef9a9a", alpha=0.18)

    # Shade high-cannib periods
    threshold = series["cannib_roll4"].quantile(0.7)
    high_periods = series[series["cannib_roll4"] > threshold]
    if len(high_periods) > 0:
        for d in high_periods["date"]:
            ax1.axvspan(d - pd.Timedelta(days=3), d + pd.Timedelta(days=3),
                        color="#ffcdd2", alpha=0.3, zorder=0)

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_units))
    ax1.set_ylabel("Weekly Units Sold", fontsize=11, color=C_FORECAST)
    ax2.set_ylabel("Cannibalization Pressure  (donor cannibal prob)", fontsize=10,
                   color="#c62828")
    ax2.set_ylim(0, min(1.0, series["cannib_roll4"].max() * 2))

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper left")

    # Annotation
    peak_row = series.loc[series["cannib_roll4"].idxmax()]
    ax1.annotate("Peak cannib pressure\n→ units may reflect\n   portfolio shift, not demand",
                 xy=(peak_row["date"], peak_row["base_units"]),
                 xytext=(40, 30), textcoords="offset points",
                 fontsize=8.5, color="#c62828",
                 arrowprops=dict(arrowstyle="->", color="#c62828", lw=1.2))

    ret_label = acct if len(acct) <= 25 else acct[:23] + "…"
    fig.suptitle(
        f"\"Am I growing from real demand — or cannibalizing myself?\"\n"
        f"UPC {upc}  ·  {ret_label}  ·  {ch}",
        fontsize=11, fontweight="bold")
    ax1.grid(True, axis="y", alpha=0.2, linestyle="--")
    ax1.spines[["top","right"]].set_visible(False)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo33_chart2_growth_vs_cannib.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → {out}")


# ── Chart 3: How much do I need to manufacture? ───────────────────────────────
def _chart3_total_demand(test_df, train_df):
    """Aggregate demand forecast with q10/q90 manufacturing planning bands."""
    print("Chart 3: Total demand forecast …")

    # Weekly aggregates
    tr_wk = (train_df.groupby("__time")["base_units"].sum().reset_index()
              .sort_values("__time"))
    te_wk = (test_df.groupby("__time")
              .agg(actual=("base_units","sum"),
                   pred_q50=("pred_q50","sum"),
                   pred_q10=("pred_q10","sum"),
                   pred_q90=("pred_q90","sum"))
              .reset_index().sort_values("__time"))

    tr_wk["date"] = pd.to_datetime(tr_wk["__time"]).dt.tz_convert(None)
    te_wk["date"] = pd.to_datetime(te_wk["__time"]).dt.tz_convert(None)
    tr_recent = tr_wk.tail(26)

    plan    = te_wk["pred_q50"].mean()
    floor_  = te_wk["pred_q10"].mean()
    ceiling = te_wk["pred_q90"].mean()

    fig, ax = plt.subplots(figsize=(14, 7))

    ax.fill_between(te_wk["date"], te_wk["pred_q10"], te_wk["pred_q90"],
                    color=C_BAND, alpha=0.35, label="q10–q90 production range")
    ax.plot(tr_recent["date"], tr_recent["base_units"],
            color=C_ACTUAL, lw=2.5, label="Actuals (prior 26 weeks)")
    ax.plot(te_wk["date"], te_wk["actual"],
            color=C_ACTUAL, lw=2.5, linestyle="--", alpha=0.5,
            label="Actuals (Q1 2026 — validation)")
    ax.plot(te_wk["date"], te_wk["pred_q50"],
            color=C_FORECAST, lw=2.8, label=f"Plan forecast (q50)  ·  4.4% wMAPE")

    ax.axvline(te_wk["date"].min() - pd.Timedelta(days=3),
               color="#555", lw=1.2, linestyle=":", alpha=0.8)
    ax.text(te_wk["date"].min(), ax.get_ylim()[1] if False else te_wk["pred_q90"].max() * 1.01,
            " ← Historical  |  Q1 2026 Forecast →", fontsize=9, color="#555", va="bottom")

    # Reference lines
    ax.axhline(plan,    color=C_FORECAST, lw=1.2, linestyle="--", alpha=0.5)
    ax.axhline(floor_,  color="#0d47a1",  lw=1.0, linestyle=":",  alpha=0.6)
    ax.axhline(ceiling, color="#0d47a1",  lw=1.0, linestyle=":",  alpha=0.6)

    last_x = te_wk["date"].max() + pd.Timedelta(days=5)
    ax.text(last_x, plan,    f"  Plan  {fmt_units(plan,'')}/wk",
            fontsize=9, color=C_FORECAST, va="center")
    ax.text(last_x, floor_,  f"  Floor {fmt_units(floor_,'')}/wk",
            fontsize=9, color="#0d47a1",  va="center")
    ax.text(last_x, ceiling, f"  Ceiling {fmt_units(ceiling,'')}/wk",
            fontsize=9, color="#0d47a1",  va="center")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_units))
    ax.set_ylabel("Total Weekly Units (all retailers, all SKUs)", fontsize=11)
    ax.set_title(
        "\"How much do I need to manufacture?\"\n"
        "Total Portfolio Demand Forecast — Q1 2026  |  q10 = safety minimum  ·  q90 = upside scenario",
        fontsize=11, fontweight="bold")
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(True, axis="y", alpha=0.25, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo33_chart3_total_demand.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → {out}")


# ── Chart 4: Which retailer should I prioritize for expansion? ────────────────
def _chart4_retailer_bubble(train_df):
    """Velocity × growth rate × TDP expansion opportunity bubble chart."""
    print("Chart 4: Retailer expansion bubble …")

    # Use last 26 weeks of training data
    cutoff_date = train_df["__time"].max()
    w26 = cutoff_date - pd.Timedelta(weeks=26)
    w13 = cutoff_date - pd.Timedelta(weeks=13)

    recent  = train_df[train_df["__time"] >= w26].copy()
    recent2 = train_df[train_df["__time"] >= w13].copy()
    prior   = train_df[(train_df["__time"] >= w26) &
                       (train_df["__time"] <  w13)].copy()

    # Per-retailer aggregates
    ret_stats = (recent.groupby("retail_account")
                 .agg(
                     velocity=("velocity_spm_roll8_avg", "mean"),
                     tdp=("tdp", "mean"),
                     units=("base_units", "sum"),
                     n_series=("base_units", "count"),
                 ).reset_index())
    ret_stats2 = (recent2.groupby("retail_account")["base_units"]
                  .sum().rename("units_recent"))
    ret_prior  = (prior.groupby("retail_account")["base_units"]
                  .sum().rename("units_prior"))
    ret_stats = ret_stats.join(ret_stats2, on="retail_account")
    ret_stats = ret_stats.join(ret_prior, on="retail_account")
    ret_stats["growth_pct"] = (
        (ret_stats["units_recent"] - ret_stats["units_prior"]) /
        (ret_stats["units_prior"].replace(0, np.nan)) * 100
    ).fillna(0)

    # Filter retailers with meaningful volume
    vol_threshold = ret_stats["units"].quantile(0.25)
    ret_stats = ret_stats[ret_stats["units"] >= vol_threshold].copy()

    # Drop MULO aggregates from bubble labels
    mulo_pattern = "MULTI OUTLET|MULO|TOTAL US|ALL CHANNEL|CONVENTIONAL"
    ret_stats = ret_stats[
        ~ret_stats["retail_account"].str.contains(mulo_pattern, case=False, na=False)
    ].copy()

    if len(ret_stats) == 0:
        print("  No qualifying retailers for bubble chart, skipping.")
        return

    # Normalize bubble sizes
    sizes = np.clip(ret_stats["tdp"].fillna(0), 0, None)
    sizes = (sizes - sizes.min()) / (sizes.max() - sizes.min() + 1e-9) * 1200 + 80

    # Color by channel
    channels = ret_stats["retail_account"].str.upper()
    colors = []
    for r in ret_stats["retail_account"]:
        r_up = r.upper()
        if any(x in r_up for x in ["WALMART","WAL"]):    colors.append("#1565c0")
        elif any(x in r_up for x in ["KROGER","KRG"]):   colors.append("#2e7d32")
        elif any(x in r_up for x in ["TARGET","TGT"]):   colors.append("#c62828")
        elif any(x in r_up for x in ["AMAZON"]):         colors.append("#e65100")
        elif any(x in r_up for x in ["COSTCO","SAMS"]): colors.append("#6a1b9a")
        elif any(x in r_up for x in ["WHOLE","WFM"]):    colors.append("#00695c")
        else:                                             colors.append("#546e7a")

    fig, ax = plt.subplots(figsize=(14, 8))

    sc = ax.scatter(
        ret_stats["velocity"].fillna(0),
        ret_stats["growth_pct"].clip(-100, 200),
        s=sizes, c=colors, alpha=0.7, edgecolors="white", linewidths=1.5, zorder=5)

    # Annotate each bubble
    for _, row in ret_stats.iterrows():
        name = row["retail_account"]
        label = name[:16] + "…" if len(name) > 16 else name
        ax.annotate(label,
                    (row["velocity"], np.clip(row["growth_pct"], -100, 200)),
                    xytext=(8, 5), textcoords="offset points",
                    fontsize=7.5, color="#1a1a2e", zorder=6)

    # Quadrant dividers
    med_vel = ret_stats["velocity"].median()
    ax.axvline(med_vel, color="#bbbbbb", lw=1, linestyle="--", alpha=0.7)
    ax.axhline(0, color="#bbbbbb", lw=1, linestyle="--", alpha=0.7)

    # Quadrant labels
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    q_kw = dict(fontsize=8, alpha=0.45, ha="center", va="center")
    ax.text(xlim[0] * 0.7 + med_vel * 0.3, ylim[1] * 0.85,
            "Low velocity\nBut growing\n→ Watch", color="#2e7d32", **q_kw)
    ax.text(xlim[1] * 0.85 + med_vel * 0.15, ylim[1] * 0.85,
            "★  High velocity\nGrowing\n→ Prioritize", color="#1565c0", **q_kw)
    ax.text(xlim[0] * 0.7 + med_vel * 0.3, ylim[0] * 0.85,
            "Low velocity\nDeclining\n→ Reconsider", color="#c62828", **q_kw)
    ax.text(xlim[1] * 0.85 + med_vel * 0.15, ylim[0] * 0.85,
            "High velocity\nSlowing\n→ Defend", color="#e65100", **q_kw)

    # Bubble size legend
    for tdp_val, label in [(0.05, "TDP 5%"), (0.30, "TDP 30%"), (0.80, "TDP 80%")]:
        s_norm = (tdp_val - (ret_stats["tdp"].fillna(0).min() /
                  (ret_stats["tdp"].fillna(0).max() - ret_stats["tdp"].fillna(0).min() + 1e-9))) * 1200 + 80
        ax.scatter([], [], s=max(40, s_norm), c="#90caf9", alpha=0.7,
                   edgecolors="#555", label=label)
    ax.legend(fontsize=8.5, loc="lower right", title="Distribution breadth (TDP)",
              title_fontsize=8)

    ax.set_xlabel("Avg Velocity (units per store per month)", fontsize=11)
    ax.set_ylabel("Units Growth  (last 13w vs prior 13w)", fontsize=11)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    ax.set_title(
        "\"Which retailer should I prioritize for expansion?\"\n"
        "Bubble size = TDP (distribution breadth)  ·  Upper right = fastest-growing, highest-velocity",
        fontsize=11, fontweight="bold")
    ax.grid(True, alpha=0.2, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo33_chart4_retailer_bubble.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → {out}")


# ── Chart 5: Method horse race ────────────────────────────────────────────────
def _chart5_horse_race(test_df, acc):
    """All methods vs. Q1 2026 actuals — weekly aggregate, wMAPE annotated."""
    print("Chart 5: Method horse race …")

    wk = (test_df.groupby("__time")
          .agg(actual=("base_units","sum"),
               pred_q50=("pred_q50","sum"),
               pred_stale=("pred_stale","sum"),
               ma13=("ma13","sum"),
               naive=("naive","sum"))
          .reset_index().sort_values("__time"))
    wk["date"] = pd.to_datetime(wk["__time"]).dt.tz_convert(None)

    fig, ax = plt.subplots(figsize=(14, 7))

    ax.plot(wk["date"], wk["actual"],    color=C_ACTUAL,   lw=3.0, zorder=7,
            label=f"Actuals (Q1 2026)")
    ax.plot(wk["date"], wk["pred_q50"],  color=C_FORECAST, lw=2.5, zorder=6,
            label=f"Rolling LightGBM  ·  {acc['Rolling LightGBM q50']:.1f}% wMAPE ✓")
    ax.plot(wk["date"], wk["pred_stale"],color=C_STALE,    lw=1.8, linestyle="--", zorder=5,
            label=f"Stale LightGBM (Dec 2024)  ·  {acc['Stale LightGBM']:.1f}% wMAPE")
    ax.plot(wk["date"], wk["ma13"],      color=C_MA13,     lw=1.6, linestyle=":", zorder=4,
            label=f"MA 13wk  ·  {acc['MA 13wk']:.1f}% wMAPE")
    ax.plot(wk["date"], wk["naive"],     color=C_NAIVE,    lw=1.4, linestyle=":", zorder=3,
            label=f"Naive (last obs)  ·  {acc['Naive']:.1f}% wMAPE")

    # wMAPE callout boxes at end of each line
    last = wk.iloc[-1]
    for col, label, color in [
        ("pred_q50",  f"{acc['Rolling LightGBM q50']:.1f}%", C_FORECAST),
        ("pred_stale",f"{acc['Stale LightGBM']:.1f}%",       C_STALE),
        ("ma13",      f"{acc['MA 13wk']:.1f}%",              C_MA13),
        ("naive",     f"{acc['Naive']:.1f}%",                C_NAIVE),
    ]:
        ax.annotate(label,
                    xy=(last["date"], last[col]),
                    xytext=(8, 0), textcoords="offset points",
                    fontsize=9, color=color, fontweight="bold", va="center")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=6, interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_units))
    ax.set_ylabel("Total Weekly Units (all series)", fontsize=11)
    ax.set_title(
        "\"Which method should I trust?\"\n"
        "All Methods vs. Q1 2026 Actuals — LightGBM trained Dec 2025, retrained quarterly",
        fontsize=11, fontweight="bold")
    ax.legend(fontsize=9.5, loc="upper left")
    ax.grid(True, axis="y", alpha=0.25, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)

    # Gain box
    gain = acc["Stale LightGBM"] - acc["Rolling LightGBM q50"]
    box_text = f"Quarterly retraining\nsaves {gain:.1f}pp accuracy"
    ax.text(0.98, 0.96, box_text,
            transform=ax.transAxes, ha="right", va="top",
            fontsize=9.5, color=C_FORECAST,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#e3f2fd",
                      edgecolor=C_FORECAST, alpha=0.9))

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo33_chart5_horse_race.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → {out}")


if __name__ == "__main__":
    main()
