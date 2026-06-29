"""MO_31 — Dec 2025 cutoff backtest + walk-forward summary across all three cutpoints.

WHAT THIS ADDS
--------------
Third and final temporal cutpoint: train on all 2023–2025 SPINS data (~130 weeks),
test on Jan–Apr 2026 (~16 weeks of the most recent actuals).

Combined with MO_29 (Oct 2025 cutoff) and MO_30 (Dec 2024 cutoff), this completes
a three-point walk-forward evaluation that answers:
  1. Can we predict 2025 from 2024 history?       (MO_30: 68-week horizon)
  2. Can we predict early 2026 from mid-2025?     (MO_29: 29-week horizon)
  3. Can we predict Q1 2026 from full-year 2025?  (MO_31: 16-week horizon) ← this script

Key hypotheses to validate:
  • LightGBM accuracy improves as training data increases (more data = better model)
  • LightGBM accuracy improves as forecast horizon shortens (easier to predict near-term)
  • Prophet's growth-extrapolation bias decreases when model has seen actual 2025 demand
  • ETS convergence improves with 130 weeks of training data

Run from the scripts/ directory:
    python MO_31_walkforward_jan2026.py

Outputs (in scripts/outputs/):
    v2_mo31_model_lgbm_dec2025.pkl      — retrained LightGBM (Dec 2025 cutoff)
    v2_mo31_metrics.json                — aggregate metrics: all 6 models
    v2_mo31_by_series.csv               — per-series metrics: all 6 models
    v2_mo31_comparison_chart.png        — 6-panel horse-race (Jan–Apr 2026 test)
    v2_mo31_method_summary_chart.png    — bar chart: wMAPE by method
    v2_walkforward_summary_chart.png    — 3-cutpoint walk-forward: accuracy over time
    v2_walkforward_horizon_chart.png    — accuracy vs. forecast horizon length
"""

import json
import logging
import pickle
import os
import warnings
warnings.filterwarnings("ignore")
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

import numpy as np
import pandas as pd
import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime, timezone

# ── Constants ──────────────────────────────────────────────────────────────────
SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR      = os.path.join(SCRIPT_DIR, "outputs")
PARQUET         = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")

CUTOFF          = pd.Timestamp("2026-01-01", tz="UTC")   # train ≤ Dec 2025
LOCAL_VAL_WEEKS = 8
MIN_TRAIN_WEEKS = 26
MIN_TEST_WEEKS  = 4    # only ~16 weeks of test data available

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]

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

LGBM_PARAMS = dict(
    objective="quantile", alpha=0.5,
    boosting_type="gbdt", n_estimators=1500, learning_rate=0.04,
    num_leaves=63, min_child_samples=20,
    feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
    reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1,
)

METHOD_COLORS = {
    "Actual":    ("#111111", 2.2, "-"),
    "LightGBM": ("#d62728", 1.8, "--"),
    "Prophet":  ("#1f77b4", 1.5, "--"),
    "ETS":      ("#9467bd", 1.4, "-."),
    "MA 4wk":   ("#2ca02c", 1.3, ":"),
    "MA 13wk":  ("#ff7f0e", 1.3, ":"),
    "Naive":    ("#8c564b", 1.2, ":"),
}


# ── Metric helpers ──────────────────────────────────────────────────────────────
def _ok(p):
    return np.isfinite(np.asarray(p, dtype=float)).any()

def wmape(a, p):
    if not _ok(p): return np.nan
    t = np.nansum(a)
    return float(np.nansum(np.abs(a - p)) / t * 100) if t > 0 else np.nan

def mape_safe(a, p, z=1.0):
    if not _ok(p): return np.nan
    mask = (a >= z) & np.isfinite(np.asarray(p, dtype=float))
    if mask.sum() == 0: return np.nan
    return float(np.nanmean(np.clip(np.abs(a[mask] - p[mask]) / a[mask], 0, 5)) * 100)

def rmse(a, p):
    if not _ok(p): return np.nan
    return float(np.sqrt(np.nanmean((a - p) ** 2)))

def bias_pct(a, p):
    if not _ok(p): return np.nan
    t = np.nansum(a)
    return float((np.nansum(np.where(np.isfinite(p), p, 0)) - t) / (t + 1) * 100)

def series_metrics(act, pred, label):
    return {f"wmape_{label}": wmape(act, pred), f"mape_{label}": mape_safe(act, pred),
            f"rmse_{label}": rmse(act, pred), f"bias_{label}": bias_pct(act, pred)}


# ── Prophet ─────────────────────────────────────────────────────────────────────
_prophet_logged = False
def fit_prophet(train_times, train_values, test_times):
    global _prophet_logged
    try:
        from prophet import Prophet
        pdf = pd.DataFrame({
            "ds": pd.to_datetime(train_times, utc=True).tz_convert(None),
            "y":  np.clip(train_values.astype(float), 0, None),
        }).dropna()
        if len(pdf) < 10: return np.full(len(test_times), np.nan)
        m = Prophet(yearly_seasonality=True, weekly_seasonality=False,
                    daily_seasonality=False, seasonality_mode="multiplicative",
                    interval_width=0.80, changepoint_prior_scale=0.15)
        m.fit(pdf, iter=300)
        future = pd.DataFrame({"ds": pd.to_datetime(test_times, utc=True).tz_convert(None)})
        return np.clip(m.predict(future)["yhat"].values, 0, None)
    except Exception as e:
        if not _prophet_logged:
            print(f"\n  [Prophet] error: {e}"); _prophet_logged = True
        return np.full(len(test_times), np.nan)


# ── ETS ─────────────────────────────────────────────────────────────────────────
_ets_logged = False
def fit_ets(train_values, n_test):
    global _ets_logged
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        clean = pd.Series(train_values.astype(float)).ffill().bfill().fillna(0).clip(lower=0).values
        if len(clean) < 10: return np.full(n_test, np.nan)
        use_seasonal = len(clean) >= 104
        model = ExponentialSmoothing(
            clean, trend="add",
            seasonal="add" if use_seasonal else None,
            seasonal_periods=52 if use_seasonal else None,
            initialization_method="estimated",
        ).fit(optimized=True)
        return np.clip(model.forecast(n_test), 0, None)
    except Exception as e:
        if not _ets_logged:
            print(f"\n  [ETS] error: {e}"); _ets_logged = True
        return np.full(n_test, np.nan)


def run_backtest(df, cutoff, min_train, min_test, label):
    """Core backtest logic reused for the Dec 2025 cutpoint."""
    train_df = df[df["__time"] <  cutoff].copy()
    test_df  = df[df["__time"] >= cutoff].copy()

    tr_counts = train_df.groupby(GROUP_COLS).size()
    te_counts  = test_df.groupby(GROUP_COLS).size()
    cov = pd.concat([tr_counts.rename("tr"), te_counts.rename("te")], axis=1).fillna(0).astype(int)
    qual = cov[(cov["tr"] >= min_train) & (cov["te"] >= min_test)]
    qual_set = set(qual.index.tolist())

    df["_k"] = list(zip(df["upc"], df["channel_outlet"], df["retail_account"], df["geography_raw"]))
    df_q = df[df["_k"].isin(qual_set)].drop(columns=["_k"])
    train_df = df_q[df_q["__time"] <  cutoff].copy()
    test_df  = df_q[df_q["__time"] >= cutoff].copy()

    print(f"\n  [{label}] qualifying series: {len(qual):,}  "
          f"| train rows: {len(train_df):,}  | test rows: {len(test_df):,}")
    print(f"  [{label}] train: {train_df['__time'].min().date()} → {train_df['__time'].max().date()}  "
          f"| test: {test_df['__time'].min().date()} → {test_df['__time'].max().date()}")

    available = [c for c in FEATURE_COLS if c in df_q.columns]

    # LightGBM
    lval_cut = cutoff - pd.Timedelta(weeks=LOCAL_VAL_WEEKS)
    sup = train_df[train_df["__time"] <  lval_cut]
    lval= train_df[train_df["__time"] >= lval_cut]
    model = lgb.LGBMRegressor(**LGBM_PARAMS)
    model.fit(sup[available], sup["log_base_units"].values,
              eval_set=[(lval[available], lval["log_base_units"].values)],
              callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(500)])
    print(f"  [{label}] LightGBM best iter: {model.best_iteration_}")
    test_df = test_df.copy()
    test_df["pred_lgbm"] = np.expm1(np.clip(model.predict(test_df[available]), 0, None))

    # Naive baselines
    base_recs = []
    for key, grp in train_df.groupby(GROUP_COLS):
        g = grp.sort_values("__time")
        base_recs.append({
            "upc": key[0], "channel_outlet": key[1],
            "retail_account": key[2], "geography_raw": key[3],
            "naive_last": g["base_units"].iloc[-1],
            "ma4":        g["base_units"].iloc[-4:].mean(),
            "ma13":       g["base_units"].iloc[-13:].mean(),
        })
    test_df = test_df.merge(pd.DataFrame(base_recs), on=GROUP_COLS, how="left")

    # Prophet + ETS
    print(f"  [{label}] Fitting Prophet + ETS …", flush=True)
    test_df = test_df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    test_df["pred_prophet"] = np.nan
    test_df["pred_ets"]     = np.nan
    groups = list(test_df.groupby(GROUP_COLS))
    for idx, (key, grp_test) in enumerate(groups):
        if (idx + 1) % 50 == 0 or idx == 0:
            print(f"    series {idx+1}/{len(groups)} …", flush=True)
        grp_tr = train_df[
            (train_df["upc"] == key[0]) & (train_df["channel_outlet"] == key[1]) &
            (train_df["retail_account"] == key[2]) & (train_df["geography_raw"] == key[3])
        ].sort_values("__time")
        idxs = grp_test.index
        n    = len(grp_test)
        test_df.loc[idxs, "pred_prophet"] = fit_prophet(
            grp_tr["__time"].values, grp_tr["base_units"].values,
            grp_test.sort_values("__time")["__time"].values)[:n]
        test_df.loc[idxs, "pred_ets"] = fit_ets(grp_tr["base_units"].values, n)[:n]

    # Metrics
    METHOD_COLS = {"LightGBM": "pred_lgbm", "Prophet": "pred_prophet", "ETS": "pred_ets",
                   "MA 4wk": "ma4", "MA 13wk": "ma13", "Naive": "naive_last"}
    act_all = test_df["base_units"].values
    agg = {}
    for lbl, col in METHOD_COLS.items():
        pred = test_df[col].values if col in test_df.columns else np.full(len(act_all), np.nan)
        agg[lbl] = {"wmape": round(wmape(act_all, pred), 2),
                    "mape":  round(mape_safe(act_all, pred), 2),
                    "rmse":  round(rmse(act_all, pred), 1),
                    "bias":  round(bias_pct(act_all, pred), 2)}

    records = []
    for key, grp in test_df.groupby(GROUP_COLS):
        act  = grp["base_units"].values
        row  = {"upc": key[0], "channel_outlet": key[1],
                "retail_account": key[2], "geography_raw": key[3],
                "description": grp["description"].iloc[0] if "description" in grp.columns else "",
                "test_weeks": len(grp), "total_actual": act.sum(), "avg_weekly": act.mean()}
        for lbl, col in METHOD_COLS.items():
            pred = grp[col].values if col in grp.columns else np.full(len(act), np.nan)
            row.update(series_metrics(act, pred, lbl))
        records.append(row)
    series_df = pd.DataFrame(records).sort_values("total_actual", ascending=False)

    return model, agg, series_df, test_df, train_df, available


def print_results(agg, series_df, test_df, label, test_weeks):
    act_all = test_df["base_units"].values
    naive_best = min(agg[m]["wmape"] for m in ["Naive", "MA 4wk", "MA 13wk"]
                     if not np.isnan(agg[m]["wmape"]))

    print(f"\n{'=' * 65}")
    print(f"RESULTS  [{label}]  ({test_weeks} OOS weeks)")
    print(f"{'=' * 65}")
    print(f"\n  {'METHOD':<16}  {'wMAPE':>7}  {'MAPE':>7}  {'RMSE':>8}  {'BIAS':>7}  {'vs naive':>9}")
    print("  " + "─" * 60)
    for meth in ["LightGBM", "Prophet", "ETS", "MA 4wk", "MA 13wk", "Naive"]:
        s = agg[meth]
        delta = naive_best - s["wmape"] if not np.isnan(s["wmape"]) else np.nan
        marker = f"  +{delta:.1f}pp" if (not np.isnan(delta) and meth in ("LightGBM","Prophet","ETS")) else ""
        wmape_str = f"{s['wmape']:>6.1f}%" if not np.isnan(s['wmape']) else "    nan%"
        bias_str  = f"{s['bias']:>+6.1f}%" if not np.isnan(s['bias']) else "    nan%"
        print(f"  {meth:<16}  {wmape_str}  {s['mape']:>6.1f}%  "
              f"{s['rmse']:>8.0f}  {bias_str}{marker}"
              if not np.isnan(s.get('mape', np.nan)) else
              f"  {meth:<16}  {wmape_str}  {'nan%':>7}  {'nan':>8}  {bias_str}{marker}")

    best_ml_name = min(("LightGBM","Prophet","ETS"),
                       key=lambda m: agg[m]["wmape"] if not np.isnan(agg[m]["wmape"]) else 999)
    best_ml_wmape = agg[best_ml_name]["wmape"]
    imp = naive_best - best_ml_wmape
    print(f"\n  Best ML: {best_ml_name} ({best_ml_wmape:.1f}% wMAPE)  |  "
          f"vs. best naive: +{imp:.1f}pp  |  "
          f"Est. ROI: ~${imp*1e6:,.0f}")

    print(f"\n  Top 10 by volume:")
    print(f"  {'UPC':>14}  {'Description':26}  {'Account':18}  "
          + "  ".join(f"{m:>7}" for m in ["LGBM","Prophet","ETS","Naive"]))
    print("  " + "─" * 82)
    for _, r in series_df.head(10).iterrows():
        vals = "  ".join(
            f"{r.get(f'wmape_{m}', np.nan):>6.1f}%" if not np.isnan(r.get(f'wmape_{m}', np.nan))
            else "   nan%"
            for m in ["LightGBM","Prophet","ETS","Naive"])
        print(f"  {r['upc']:>14}  {str(r['description'])[:26]:<26}  "
              f"{str(r['retail_account'])[:18]:<18}  {vals}")


def make_comparison_chart(df, test_df, series_df, cutoff, label, out_path, context_weeks=26):
    top_keys = (series_df.head(6)
                .apply(lambda r: (r["upc"], r["channel_outlet"],
                                  r["retail_account"], r["geography_raw"]), axis=1)
                .tolist())
    context_start = cutoff - pd.Timedelta(weeks=context_weeks)

    fig = plt.figure(figsize=(22, 18))
    gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.55, wspace=0.30)

    METHOD_COLS = {"LightGBM": "pred_lgbm", "Prophet": "pred_prophet",
                   "ETS": "pred_ets", "MA 4wk": "ma4", "Naive": "naive_last"}

    for i, key in enumerate(top_keys):
        ax = fig.add_subplot(gs[i // 2, i % 2])
        mask_ctx = ((df["upc"] == key[0]) & (df["channel_outlet"] == key[1]) &
                    (df["retail_account"] == key[2]) & (df["geography_raw"] == key[3]) &
                    (df["__time"] >= context_start))
        grp_ctx = df[mask_ctx].sort_values("__time")
        mask_tst = ((test_df["upc"] == key[0]) & (test_df["channel_outlet"] == key[1]) &
                    (test_df["retail_account"] == key[2]) & (test_df["geography_raw"] == key[3]))
        grp_tst = test_df[mask_tst].sort_values("__time")

        c, lw, ls = METHOD_COLORS["Actual"]
        ax.plot(grp_ctx["__time"], grp_ctx["base_units"],
                color=c, linewidth=lw, linestyle=ls, label="Actual", zorder=6)

        if len(grp_tst) > 0:
            for mlabel, col in METHOD_COLS.items():
                if col not in grp_tst.columns: continue
                c2, lw2, ls2 = METHOD_COLORS[mlabel]
                ax.plot(grp_tst["__time"], grp_tst[col],
                        color=c2, linewidth=lw2, linestyle=ls2, label=mlabel, alpha=0.85)

        ax.axvline(cutoff, color="gray", linestyle=":", linewidth=1.4, alpha=0.8)
        ax.axvspan(cutoff, test_df["__time"].max(), alpha=0.04, color="red")

        sr = series_df[(series_df["upc"] == key[0]) & (series_df["retail_account"] == key[2])]
        desc = str(grp_ctx["description"].iloc[0])[:24] if len(grp_ctx) > 0 else key[0]
        lgbm_w = sr["wmape_LightGBM"].iloc[0] if len(sr) > 0 else np.nan
        naive_w = sr["wmape_Naive"].iloc[0] if len(sr) > 0 else np.nan
        ax.set_title(f"{desc} | {str(key[2])[:16]}\n"
                     f"LightGBM {lgbm_w:.1f}%   Naive {naive_w:.1f}%   wMAPE", fontsize=9)
        ax.set_ylabel("Base Units / Week", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.22)
        if i == 0:
            ax.legend(fontsize=7, loc="upper left", ncol=2)

    fig.suptitle(f"Multi-Model Horse Race — {label}\n"
                 "Shaded = OOS test  |  Dotted line = train/test boundary",
                 fontsize=10, y=0.99)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Comparison chart → {out_path}")


def make_summary_bar(agg, label, test_weeks, out_path):
    methods = ["Naive", "MA 4wk", "MA 13wk", "ETS", "Prophet", "LightGBM"]
    wmapes  = [agg[m]["wmape"] if not np.isnan(agg[m]["wmape"]) else 0 for m in methods]
    colors  = ["#8c564b","#ff7f0e","#e377c2","#9467bd","#1f77b4","#d62728"]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(methods, wmapes, color=colors, width=0.55, edgecolor="white")
    for bar, val in zip(bars, wmapes):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    f"{val:.1f}%", ha="center", fontsize=11, fontweight="bold")
    ax.set_ylabel("wMAPE — lower is better", fontsize=11)
    ax.set_title(f"Forecast Accuracy by Method — {label}  ({test_weeks} OOS weeks)",
                 fontsize=11, pad=12)
    ax.set_ylim(0, max(v for v in wmapes if v > 0) * 1.18)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def make_walkforward_charts(all_results):
    """Two charts: wMAPE by cutpoint per method + wMAPE vs. horizon length."""
    cutpoints = [r["label"] for r in all_results]
    horizons  = [r["test_weeks"] for r in all_results]
    methods   = ["LightGBM", "Prophet", "ETS", "MA 4wk", "Naive"]
    mcolors   = {"LightGBM":"#d62728","Prophet":"#1f77b4","ETS":"#9467bd",
                 "MA 4wk":"#2ca02c","Naive":"#8c564b"}

    # ── Chart 1: wMAPE by training cutpoint ──────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(cutpoints))
    width = 0.14
    for j, method in enumerate(methods):
        vals = [r["agg"].get(method, {}).get("wmape", np.nan) for r in all_results]
        offset = (j - len(methods)/2 + 0.5) * width
        bars = ax.bar(x + offset, [v if not np.isnan(v) else 0 for v in vals],
                      width, label=method, color=mcolors[method], alpha=0.85)
        for bar, val in zip(bars, vals):
            if not np.isnan(val) and val > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                        f"{val:.0f}%", ha="center", fontsize=7, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{r['label']}\n({r['test_weeks']}w OOS)" for r in all_results], fontsize=10)
    ax.set_ylabel("wMAPE — lower is better", fontsize=11)
    ax.set_title("Walk-Forward Validation: Forecast Accuracy Across Training Cutpoints\n"
                 "As training data grows and horizon shortens, accuracy improves",
                 fontsize=11, pad=12)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout()
    path1 = os.path.join(OUTPUT_DIR, "v2_walkforward_summary_chart.png")
    plt.savefig(path1, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Walk-forward summary chart → {path1}")

    # ── Chart 2: LightGBM accuracy vs. forecast horizon length ───────────────
    lgbm_wmapes = [r["agg"].get("LightGBM", {}).get("wmape", np.nan) for r in all_results]
    naive_wmapes = [r["agg"].get("Naive", {}).get("wmape", np.nan) for r in all_results]
    fig2, ax2 = plt.subplots(figsize=(9, 5))
    ax2.plot(horizons, lgbm_wmapes, "o-", color="#d62728", linewidth=2.2,
             markersize=9, label="LightGBM", zorder=5)
    ax2.plot(horizons, naive_wmapes, "s--", color="#8c564b", linewidth=1.5,
             markersize=7, label="Naive (last value)", alpha=0.8)
    for h, lv, nv in zip(horizons, lgbm_wmapes, naive_wmapes):
        ax2.annotate(f"{lv:.1f}%", (h, lv), textcoords="offset points",
                     xytext=(6, 4), fontsize=10, color="#d62728", fontweight="bold")
        ax2.annotate(f"{nv:.1f}%", (h, nv), textcoords="offset points",
                     xytext=(6, -12), fontsize=9, color="#8c564b")
    ax2.invert_xaxis()
    ax2.set_xlabel("Forecast Horizon (OOS weeks — shorter = closer to today)", fontsize=11)
    ax2.set_ylabel("wMAPE", fontsize=11)
    ax2.set_title("LightGBM Accuracy vs. Forecast Horizon\n"
                  "Shorter horizons with more training data yield dramatically better accuracy",
                  fontsize=11, pad=12)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3, linestyle="--")
    ax2.spines[["top","right"]].set_visible(False)
    plt.tight_layout()
    path2 = os.path.join(OUTPUT_DIR, "v2_walkforward_horizon_chart.png")
    plt.savefig(path2, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Horizon accuracy chart     → {path2}")


def main():
    print("=" * 65)
    print("MO_31  —  Dec 2025 Cutoff + Walk-Forward Summary")
    print("=" * 65)

    # ── Load and prep ─────────────────────────────────────────────────────────
    print(f"\nLoading {PARQUET} …")
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    num_cols = [c for c in FEATURE_COLS if c != "channel_outlet"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "channel_outlet" in df.columns:
        df["channel_outlet"] = df["channel_outlet"].astype("category")
    df = df.dropna(subset=["base_units"]).copy()
    df["log_base_units"] = np.log1p(df["base_units"])

    # Filter MULO
    if "geography_raw" in df.columns:
        df = df[~df["geography_raw"].str.contains(
            "MULTI OUTLET|MULO|TOTAL US|ALL CHANNEL", case=False, na=False)].copy()
    if "geography_level" in df.columns:
        df = df[~df["geography_level"].str.upper().isin(["NATIONAL","TOTAL"])].copy()

    print(f"  Rows after MULO filter: {len(df):,}  "
          f"| Date range: {df['__time'].min().date()} → {df['__time'].max().date()}")

    # ── Run Dec 2025 backtest ─────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"BACKTEST: Dec 2025 cutoff  (test = Jan–Apr 2026)")
    print(f"{'─'*65}")
    model31, agg31, series31, test31, train31, available = run_backtest(
        df.copy(), CUTOFF, MIN_TRAIN_WEEKS, MIN_TEST_WEEKS, "Dec2025"
    )

    print_results(agg31, series31, test31,
                  label="Dec 2025 cutoff → Jan–Apr 2026",
                  test_weeks=int(test31["__time"].nunique()))

    # Save outputs
    with open(os.path.join(OUTPUT_DIR, "v2_mo31_model_lgbm_dec2025.pkl"), "wb") as f:
        pickle.dump(model31, f)

    meta31 = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "train_cutoff": str(CUTOFF.date()),
        "test_start": str(test31["__time"].min().date()),
        "test_end":   str(test31["__time"].max().date()),
        "test_weeks": int(test31["__time"].nunique()),
        "lgbm_best_iter": int(model31.best_iteration_),
        "aggregate_metrics": agg31,
    }
    with open(os.path.join(OUTPUT_DIR, "v2_mo31_metrics.json"), "w") as f:
        json.dump(meta31, f, indent=2)
    series31.to_csv(os.path.join(OUTPUT_DIR, "v2_mo31_by_series.csv"), index=False)

    test_weeks31 = int(test31["__time"].nunique())
    make_comparison_chart(df, test31, series31, CUTOFF,
                          f"Dec 2025 cutoff → Jan–Apr 2026 ({test_weeks31}w OOS)",
                          os.path.join(OUTPUT_DIR, "v2_mo31_comparison_chart.png"),
                          context_weeks=20)
    make_summary_bar(agg31, "Dec 2025 Cutoff", test_weeks31,
                     os.path.join(OUTPUT_DIR, "v2_mo31_method_summary_chart.png"))

    # ── Load prior backtest metrics + build walk-forward summary ─────────────
    print(f"\n{'─'*65}")
    print("WALK-FORWARD SUMMARY  (all three cutpoints)")
    print(f"{'─'*65}")

    # Canonical key aliases so older JSONs with different naming still resolve
    _KEY_ALIASES = {
        "LightGBM_v2_oct2025": "LightGBM",
        "Naive_last_value": "Naive",
        "Moving_avg_4wk": "MA 4wk",
        "Moving_avg_13wk": "MA 13wk",
    }

    def _normalize_agg(raw):
        out = {}
        for k, v in raw.items():
            out[_KEY_ALIASES.get(k, k)] = v
        return out

    prior = [
        ("v2_mo30_metrics.json", "Dec 2024\n→ 68w OOS"),
        ("v2_backtest_metrics.json", "Oct 2025\n→ 29w OOS"),
    ]
    all_results = []
    for fname, label in prior:
        fpath = os.path.join(OUTPUT_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath) as f:
                m = json.load(f)
            all_results.append({
                "label": label,
                "test_weeks": m.get("test_weeks", 0),
                "agg": _normalize_agg(m.get("aggregate_metrics", {})),
            })
        else:
            print(f"  WARNING: {fname} not found — skipping from walk-forward chart")

    all_results.append({
        "label": "Dec 2025\n→ 16w OOS",
        "test_weeks": test_weeks31,
        "agg": agg31,
    })

    if len(all_results) >= 2:
        make_walkforward_charts(all_results)

    # Print consolidated walk-forward table
    print(f"\n  {'CUTPOINT':<20}  {'HORIZON':>8}  "
          + "  ".join(f"{'LGBM':>7}  {'Naive':>7}" for _ in all_results[:1])
          + f"\n  {'CUTPOINT':<20}  {'(OOS wks)':>8}  "
          + "  ".join(f"{'wMAPE':>7}  {'wMAPE':>7}" for _ in all_results))
    print("  " + "─" * 65)
    for r in all_results:
        lgbm_w  = r["agg"].get("LightGBM", {}).get("wmape", np.nan)
        naive_w = r["agg"].get("Naive",     {}).get("wmape", np.nan)
        imp = naive_w - lgbm_w if not (np.isnan(lgbm_w) or np.isnan(naive_w)) else np.nan
        label_clean = r["label"].replace("\n", " ")
        print(f"  {label_clean:<20}  {r['test_weeks']:>8}w  "
              f"  LGBM {lgbm_w:>5.1f}%  Naive {naive_w:>5.1f}%  "
              f"  delta +{imp:.1f}pp" if not np.isnan(imp) else
              f"  {label_clean:<20}  {r['test_weeks']:>8}w  LGBM nan  Naive nan")

    print(f"\n  Outputs saved to: {OUTPUT_DIR}")
    print(f"    v2_mo31_model_lgbm_dec2025.pkl")
    print(f"    v2_mo31_metrics.json")
    print(f"    v2_mo31_by_series.csv")
    print(f"    v2_mo31_comparison_chart.png")
    print(f"    v2_mo31_method_summary_chart.png")
    print(f"    v2_walkforward_summary_chart.png   ← 3-cutpoint bar comparison")
    print(f"    v2_walkforward_horizon_chart.png   ← LightGBM accuracy vs. horizon")
    print("=" * 65)


if __name__ == "__main__":
    main()
