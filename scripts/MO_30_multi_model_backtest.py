"""MO_30 — Multi-model backtest: Jan 2025 cutoff, 69-week OOS test (all of 2025 + YTD).

WHY JAN 2025 CUTOFF
--------------------
Training on 2024 data and predicting 2025 actuals is the most persuasive proof
for the FP&A audience:
  • Connor has full-year 2025 actuals in Excel — direct side-by-side comparison
  • 69 OOS weeks (Jan 2025 – Apr 2026) vs. 29 weeks in MO_29
  • Full seasonal cycle in the test period (New Year spike, spring, summer, Q4)
  • Includes early-2025 new SKU launches — tests growth-mode generalization

MODELS
------
  1. LightGBM           — ML with Mo signals; primary model
  2. Prophet            — trend + seasonality decomposition; Facebook/Meta open source
  3. ETS                — Exponential Smoothing; weighted recent history
  4. Moving avg 4wk     — near-term naive
  5. Moving avg 13wk    — quarterly naive
  6. Naive last value   — flat-trend proxy (approximates basic Excel extrapolation)

Run from the scripts/ directory:
    python MO_30_multi_model_backtest.py

Outputs (in scripts/outputs/):
    v2_mo30_model_lgbm_jan2025.pkl     — retrained LightGBM
    v2_mo30_metrics.json               — aggregate metrics: all 6 models
    v2_mo30_by_series.csv              — per-series metrics: all 6 models
    v2_mo30_comparison_chart.png       — 6-panel horse-race chart
    v2_mo30_method_summary_chart.png   — bar chart: wMAPE by method (FP&A slide)
"""

import json
import pickle
import os
import warnings
warnings.filterwarnings("ignore")

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

CUTOFF          = pd.Timestamp("2025-01-01", tz="UTC")   # train ≤ Dec 2024
LOCAL_VAL_WEEKS = 8     # last N training weeks for LightGBM early stopping only
MIN_TRAIN_WEEKS = 26    # series must have this many weeks before CUTOFF
MIN_TEST_WEEKS  = 13    # series must have this many weeks after CUTOFF

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

# Chart colors per method
METHOD_COLORS = {
    "Actual":        ("#111111", 2.2, "-"),
    "LightGBM":      ("#d62728", 1.8, "--"),
    "Prophet":       ("#1f77b4", 1.5, "--"),
    "ETS":           ("#9467bd", 1.4, "-."),
    "MA 4wk":        ("#2ca02c", 1.3, ":"),
    "MA 13wk":       ("#ff7f0e", 1.3, ":"),
    "Naive":         ("#8c564b", 1.2, ":"),
}


# ── Metric helpers ──────────────────────────────────────────────────────────────
def _check_preds(predicted):
    """Return True if predictions are usable (not all NaN)."""
    arr = np.asarray(predicted, dtype=float)
    return np.isfinite(arr).any()

def wmape(actual, predicted):
    if not _check_preds(predicted):
        return np.nan
    t = np.nansum(actual)
    return float(np.nansum(np.abs(actual - predicted)) / t * 100) if t > 0 else np.nan

def mape_safe(actual, predicted, zero_thresh=1.0):
    if not _check_preds(predicted):
        return np.nan
    mask = (actual >= zero_thresh) & np.isfinite(np.asarray(predicted, dtype=float))
    if mask.sum() == 0:
        return np.nan
    err = np.clip(np.abs(actual[mask] - predicted[mask]) / actual[mask], 0, 5.0)
    return float(np.nanmean(err) * 100)

def rmse(actual, predicted):
    if not _check_preds(predicted):
        return np.nan
    return float(np.sqrt(np.nanmean((actual - predicted) ** 2)))

def bias_pct(actual, predicted):
    if not _check_preds(predicted):
        return np.nan
    t = np.nansum(actual)
    return float((np.nansum(np.where(np.isfinite(predicted), predicted, 0)) - t) / (t + 1) * 100)

def series_metrics(act, pred, label):
    return {
        f"wmape_{label}": wmape(act, pred),
        f"mape_{label}":  mape_safe(act, pred),
        f"rmse_{label}":  rmse(act, pred),
        f"bias_{label}":  bias_pct(act, pred),
    }


# ── Prophet helper ──────────────────────────────────────────────────────────────
_prophet_error_logged = False

def fit_prophet_series(train_times, train_values, test_times):
    """Fit Prophet on one series; return predictions for test_times."""
    global _prophet_error_logged
    try:
        from prophet import Prophet
        # tz_convert(None) removes UTC tz info — required for Prophet ds column;
        # tz_localize(None) raises TypeError on already-tz-aware timestamps in pandas 2+
        pdf = pd.DataFrame({
            "ds": pd.to_datetime(train_times, utc=True).tz_convert(None),
            "y":  np.clip(train_values.astype(float), 0, None),
        }).dropna()
        if len(pdf) < 10:
            return np.full(len(test_times), np.nan)
        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            seasonality_mode="multiplicative",
            interval_width=0.80,
            changepoint_prior_scale=0.15,
        )
        m.fit(pdf, iter=300)
        future = pd.DataFrame({"ds": pd.to_datetime(test_times, utc=True).tz_convert(None)})
        forecast = m.predict(future)
        preds = np.clip(forecast["yhat"].values, 0, None)
        return preds
    except Exception as e:
        if not _prophet_error_logged:
            print(f"\n  [Prophet] first error: {e}")
            _prophet_error_logged = True
        return np.full(len(test_times), np.nan)


# ── ETS helper ──────────────────────────────────────────────────────────────────
_ets_error_logged = False

def fit_ets_series(train_values, n_test):
    """Fit Exponential Smoothing (Holt-Winters) on one series."""
    global _ets_error_logged
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        # ffill/bfill so statsmodels gets a clean float array with no NaN gaps
        clean = pd.Series(train_values.astype(float)).ffill().bfill().fillna(0).clip(lower=0).values
        n = len(clean)
        if n < 10:
            return np.full(n_test, np.nan)
        seasonal_periods = 52
        use_seasonal = n >= seasonal_periods * 2

        model = ExponentialSmoothing(
            clean,
            trend="add",
            seasonal="add" if use_seasonal else None,
            seasonal_periods=seasonal_periods if use_seasonal else None,
            initialization_method="estimated",
        ).fit(optimized=True)

        preds = np.clip(model.forecast(n_test), 0, None)
        return preds
    except Exception as e:
        if not _ets_error_logged:
            print(f"\n  [ETS] first error: {e}")
            _ets_error_logged = True
        return np.full(n_test, np.nan)


def main():
    print("=" * 65)
    print("MO_30  —  Multi-Model Backtest  (Jan 2025 cutoff)")
    print("=" * 65)
    print(f"  Training: through {CUTOFF.date()}  |  Test: Jan 2025 → Apr 2026")

    # ── 1. Load and encode ────────────────────────────────────────────────────
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

    # ── 2. Filter MULO / national aggregates ─────────────────────────────────
    if "geography_raw" in df.columns:
        mulo = df["geography_raw"].str.contains(
            "MULTI OUTLET|MULO|TOTAL US|ALL CHANNEL", case=False, na=False
        )
        df = df[~mulo].copy()
    if "geography_level" in df.columns:
        df = df[~df["geography_level"].str.upper().isin(["NATIONAL", "TOTAL"])].copy()

    # ── 3. Qualify series ─────────────────────────────────────────────────────
    train_counts = df[df["__time"] <  CUTOFF].groupby(GROUP_COLS).size()
    test_counts  = df[df["__time"] >= CUTOFF].groupby(GROUP_COLS).size()
    coverage     = pd.concat([train_counts.rename("tr"),
                              test_counts.rename("te")], axis=1).fillna(0).astype(int)
    qualifying   = coverage[(coverage["tr"] >= MIN_TRAIN_WEEKS) &
                            (coverage["te"] >= MIN_TEST_WEEKS)]

    qual_set = set(qualifying.index.tolist())
    df["_key"] = list(zip(df["upc"], df["channel_outlet"],
                          df["retail_account"], df["geography_raw"]))
    df = df[df["_key"].isin(qual_set)].drop(columns=["_key"])

    n_series = len(qualifying)
    print(f"  Qualifying series (≥{MIN_TRAIN_WEEKS} train + ≥{MIN_TEST_WEEKS} test): "
          f"{n_series:,}  |  rows: {len(df):,}")

    train_df = df[df["__time"] <  CUTOFF].copy()
    test_df  = df[df["__time"] >= CUTOFF].copy()
    print(f"  Train: {len(train_df):,} rows  "
          f"({train_df['__time'].min().date()} → {train_df['__time'].max().date()})")
    print(f"  Test:  {len(test_df):,} rows  "
          f"({test_df['__time'].min().date()} → {test_df['__time'].max().date()})")

    # ── 4. LightGBM ──────────────────────────────────────────────────────────
    print("\n[1/4] Training LightGBM …")
    lval_cutoff = CUTOFF - pd.Timedelta(weeks=LOCAL_VAL_WEEKS)
    super_train = train_df[train_df["__time"] <  lval_cutoff]
    local_val   = train_df[train_df["__time"] >= lval_cutoff]

    available = [c for c in FEATURE_COLS if c in df.columns]
    model_lgbm = lgb.LGBMRegressor(**LGBM_PARAMS)
    model_lgbm.fit(
        super_train[available], super_train["log_base_units"].values,
        eval_set=[(local_val[available], local_val["log_base_units"].values)],
        callbacks=[lgb.early_stopping(50, verbose=False),
                   lgb.log_evaluation(300)],
    )
    print(f"  Best iteration: {model_lgbm.best_iteration_}")

    preds_log = model_lgbm.predict(test_df[available])
    test_df = test_df.copy()
    test_df["pred_lgbm"] = np.expm1(np.clip(preds_log, 0, None))

    lgbm_path = os.path.join(OUTPUT_DIR, "v2_mo30_model_lgbm_jan2025.pkl")
    with open(lgbm_path, "wb") as f:
        pickle.dump(model_lgbm, f)
    print(f"  Saved → {lgbm_path}")

    # ── 5. Naive baselines + Prophet + ETS per series ────────────────────────
    print("\n[2/4] Computing naive baselines …")
    base_records = []
    for key, grp in train_df.groupby(GROUP_COLS):
        grp_s = grp.sort_values("__time")
        base_records.append({
            "upc":            key[0],
            "channel_outlet": key[1],
            "retail_account": key[2],
            "geography_raw":  key[3],
            "naive_last": grp_s["base_units"].iloc[-1],
            "ma4":        grp_s["base_units"].iloc[-4:].mean(),
            "ma13":       grp_s["base_units"].iloc[-13:].mean(),
        })
    baselines = pd.DataFrame(base_records)
    test_df = test_df.merge(baselines, on=GROUP_COLS, how="left")

    # Prophet and ETS run per series — show progress
    print("\n[3/4] Fitting Prophet + ETS per series …")
    prophet_preds = {}
    ets_preds     = {}
    groups = list(test_df.groupby(GROUP_COLS))
    n_total = len(groups)

    for idx, (key, grp_test) in enumerate(groups):
        if (idx + 1) % 25 == 0 or idx == 0:
            print(f"  Series {idx+1}/{n_total} …", flush=True)

        grp_train = train_df[
            (train_df["upc"]            == key[0]) &
            (train_df["channel_outlet"] == key[1]) &
            (train_df["retail_account"] == key[2]) &
            (train_df["geography_raw"]  == key[3])
        ].sort_values("__time")

        train_times  = grp_train["__time"].values
        train_values = grp_train["base_units"].values
        test_times   = grp_test.sort_values("__time")["__time"].values
        n_test       = len(test_times)

        prophet_preds[key] = fit_prophet_series(train_times, train_values, test_times)
        ets_preds[key]     = fit_ets_series(train_values, n_test)

    # Map predictions back to test_df rows
    test_df = test_df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    prophet_col = []
    ets_col     = []
    for key, grp in test_df.groupby(GROUP_COLS, sort=False):
        n = len(grp)
        prophet_col.extend(prophet_preds.get(key, [np.nan]*n))
        ets_col.extend(ets_preds.get(key,     [np.nan]*n))

    # Reindex after groupby reordering
    test_df_sorted = test_df.copy()
    test_df_sorted["pred_prophet"] = np.nan
    test_df_sorted["pred_ets"]     = np.nan
    idx_cursor = 0
    for key, grp in test_df_sorted.groupby(GROUP_COLS):
        n     = len(grp)
        idxs  = grp.index
        pp    = prophet_preds.get(key, np.full(n, np.nan))
        ep    = ets_preds.get(key,     np.full(n, np.nan))
        test_df_sorted.loc[idxs, "pred_prophet"] = pp[:n]
        test_df_sorted.loc[idxs, "pred_ets"]     = ep[:n]
    test_df = test_df_sorted

    # ── 6. Per-series metrics ─────────────────────────────────────────────────
    print("\n[4/4] Computing metrics …")
    METHOD_COLS = {
        "LightGBM":  "pred_lgbm",
        "Prophet":   "pred_prophet",
        "ETS":       "pred_ets",
        "MA 4wk":    "ma4",
        "MA 13wk":   "ma13",
        "Naive":     "naive_last",
    }
    records = []
    for key, grp in test_df.groupby(GROUP_COLS):
        act  = grp["base_units"].values
        desc = grp["description"].iloc[0] if "description" in grp.columns else ""
        row  = {
            "upc": key[0], "channel_outlet": key[1],
            "retail_account": key[2], "geography_raw": key[3],
            "description": desc,
            "test_weeks":  len(grp),
            "total_actual":   act.sum(),
            "avg_weekly":     act.mean(),
        }
        for label, col in METHOD_COLS.items():
            pred = grp[col].values if col in grp.columns else np.full(len(act), np.nan)
            row.update(series_metrics(act, pred, label))
        records.append(row)

    series_df = pd.DataFrame(records).sort_values("total_actual", ascending=False)
    series_df.to_csv(os.path.join(OUTPUT_DIR, "v2_mo30_by_series.csv"), index=False)

    # ── 7. Aggregate metrics ──────────────────────────────────────────────────
    act_all = test_df["base_units"].values
    agg = {}
    for label, col in METHOD_COLS.items():
        pred = test_df[col].values if col in test_df.columns else np.full(len(act_all), np.nan)
        agg[label] = {
            "wmape": round(wmape(act_all, pred), 2),
            "mape":  round(mape_safe(act_all, pred), 2),
            "rmse":  round(rmse(act_all, pred), 1),
            "bias":  round(bias_pct(act_all, pred), 2),
        }

    meta = {
        "run_at":            datetime.now(timezone.utc).isoformat(),
        "train_cutoff":      str(CUTOFF.date()),
        "test_start":        str(test_df["__time"].min().date()),
        "test_end":          str(test_df["__time"].max().date()),
        "test_weeks":        int(test_df["__time"].nunique()),
        "qualifying_series": n_series,
        "train_rows":        int(len(train_df)),
        "test_rows":         int(len(test_df)),
        "lgbm_best_iter":    int(model_lgbm.best_iteration_),
        "aggregate_metrics": agg,
    }
    with open(os.path.join(OUTPUT_DIR, "v2_mo30_metrics.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # ── 8. Print results ──────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("MULTI-MODEL BACKTEST RESULTS  (Jan 2025 cutoff)")
    print("=" * 65)
    print(f"\n  Test period: {meta['test_start']} → {meta['test_end']}  "
          f"({meta['test_weeks']} weeks OOS)")
    print(f"  Series: {n_series:,}  |  Test rows: {len(test_df):,}")

    print(f"\n  {'METHOD':<16}  {'wMAPE':>7}  {'MAPE':>7}  "
          f"{'RMSE':>8}  {'BIAS':>7}  {'vs best naive':>14}")
    print("  " + "─" * 62)
    naive_wmape = min(agg[m]["wmape"] for m in ["Naive", "MA 4wk", "MA 13wk"])
    for label in ["LightGBM", "Prophet", "ETS", "MA 4wk", "MA 13wk", "Naive"]:
        s   = agg[label]
        delta = naive_wmape - s["wmape"]
        marker = f"  +{delta:.1f}pp" if delta > 0 else f"  {delta:.1f}pp"
        is_ml  = label in ("LightGBM", "Prophet", "ETS")
        print(f"  {label:<16}  {s['wmape']:>6.1f}%  {s['mape']:>6.1f}%  "
              f"{s['rmse']:>8.0f}  {s['bias']:>+6.1f}%  "
              f"{marker if is_ml else '':>14}")

    # Best ML model
    best_ml = min(("LightGBM", "Prophet", "ETS"), key=lambda m: agg[m]["wmape"])
    best_ml_wmape = agg[best_ml]["wmape"]
    improvement = naive_wmape - best_ml_wmape
    print(f"\n  Best ML model: {best_ml}  ({best_ml_wmape:.1f}% wMAPE)")
    print(f"  Improvement vs. best naive: {improvement:+.1f} pp wMAPE")
    est_roi = improvement * 1_000_000
    print(f"  Estimated ROI (at $1M/1pp): ~${est_roi:,.0f}")

    print(f"\n  Top 10 series by volume:")
    print(f"  {'UPC':>14}  {'Description':28}  {'Account':18}  "
          + "  ".join(f"{m:>7}" for m in ["LGBM", "Prophet", "ETS", "Naive"]))
    print("  " + "─" * 85)
    for _, r in series_df.head(10).iterrows():
        desc = str(r["description"])[:28].ljust(28)
        acct = str(r["retail_account"])[:18].ljust(18)
        vals = "  ".join(
            f"{r.get(f'wmape_{m}', np.nan):>6.1f}%"
            for m in ["LightGBM", "Prophet", "ETS", "Naive"]
        )
        print(f"  {r['upc']:>14}  {desc}  {acct}  {vals}")

    # Prophet/ETS coverage (NaN = failed to fit)
    for label, col in [("Prophet", "pred_prophet"), ("ETS", "pred_ets")]:
        if col in test_df.columns:
            nan_pct = test_df[col].isna().mean() * 100
            if nan_pct > 5:
                print(f"\n  NOTE: {label} failed to fit on {nan_pct:.0f}% of test rows "
                      f"— series with insufficient training data.")

    # ── 9. Horse-race comparison chart (top 6 series) ────────────────────────
    print("\nGenerating comparison chart …")
    top_keys = (series_df.head(6)
                .apply(lambda r: (r["upc"], r["channel_outlet"],
                                  r["retail_account"], r["geography_raw"]), axis=1)
                .tolist())

    context_start = CUTOFF - pd.Timedelta(weeks=26)
    fig = plt.figure(figsize=(22, 18))
    gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.55, wspace=0.30)

    for i, key in enumerate(top_keys):
        ax = fig.add_subplot(gs[i // 2, i % 2])

        # Full context window (26 weeks training + all test)
        mask_ctx = (
            (df["upc"] == key[0]) & (df["channel_outlet"] == key[1]) &
            (df["retail_account"] == key[2]) & (df["geography_raw"] == key[3]) &
            (df["__time"] >= context_start)
        )
        grp_ctx = df[mask_ctx].sort_values("__time")

        mask_tst = (
            (test_df["upc"] == key[0]) & (test_df["channel_outlet"] == key[1]) &
            (test_df["retail_account"] == key[2]) & (test_df["geography_raw"] == key[3])
        )
        grp_tst = test_df[mask_tst].sort_values("__time")

        c, lw, ls = METHOD_COLORS["Actual"]
        ax.plot(grp_ctx["__time"], grp_ctx["base_units"],
                color=c, linewidth=lw, linestyle=ls, label="Actual", zorder=6)

        if len(grp_tst) > 0:
            for method_label, col in [
                ("LightGBM", "pred_lgbm"),
                ("Prophet",  "pred_prophet"),
                ("ETS",      "pred_ets"),
                ("MA 4wk",   "ma4"),
                ("Naive",    "naive_last"),
            ]:
                if col not in grp_tst.columns:
                    continue
                c2, lw2, ls2 = METHOD_COLORS[method_label]
                ax.plot(grp_tst["__time"], grp_tst[col],
                        color=c2, linewidth=lw2, linestyle=ls2,
                        label=method_label, alpha=0.85)

        ax.axvline(CUTOFF, color="gray", linestyle=":", linewidth=1.4, alpha=0.8)
        ax.axvspan(CUTOFF, test_df["__time"].max(),
                   alpha=0.04, color="red")

        sr = series_df[
            (series_df["upc"] == key[0]) &
            (series_df["retail_account"] == key[2])
        ]
        desc = str(grp_ctx["description"].iloc[0])[:26] if len(grp_ctx) > 0 else key[0]
        lgbm_w = sr["wmape_LightGBM"].iloc[0] if len(sr) > 0 else np.nan
        naive_w = sr["wmape_Naive"].iloc[0]    if len(sr) > 0 else np.nan

        ax.set_title(
            f"{desc} | {str(key[2])[:18]}\n"
            f"LightGBM {lgbm_w:.1f}%   Naive {naive_w:.1f}%   wMAPE",
            fontsize=9,
        )
        ax.set_ylabel("Base Units / Week", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.22)
        if i == 0:
            ax.legend(fontsize=7, loc="upper left", ncol=2)

    test_end_str = test_df["__time"].max().strftime("%b %Y")
    fig.suptitle(
        f"Multi-Model Horse Race — Train: through Dec 2024  |  "
        f"Test: Jan 2025 → {test_end_str}  ({meta['test_weeks']} OOS weeks)\n"
        "Shaded area = out-of-sample test  |  Vertical line = Jan 1, 2025 cutoff",
        fontsize=10, y=0.99,
    )
    chart_path = os.path.join(OUTPUT_DIR, "v2_mo30_comparison_chart.png")
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Comparison chart → {chart_path}")

    # ── 10. Summary bar chart (FP&A slide artifact) ───────────────────────────
    methods_ordered = ["Naive", "MA 4wk", "MA 13wk", "ETS", "Prophet", "LightGBM"]
    wmapes = [agg[m]["wmape"] for m in methods_ordered]
    bar_colors = [
        "#8c564b", "#ff7f0e", "#e377c2",
        "#9467bd", "#1f77b4", "#d62728",
    ]
    fig2, ax2 = plt.subplots(figsize=(10, 5))
    bars = ax2.bar(methods_ordered, wmapes, color=bar_colors, width=0.55,
                   edgecolor="white", linewidth=0.8)
    for bar, val in zip(bars, wmapes):
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 0.3,
                 f"{val:.1f}%", ha="center", va="bottom", fontsize=11,
                 fontweight="bold")
    ax2.set_ylabel("wMAPE — lower is better", fontsize=11)
    ax2.set_title(
        f"Forecast Accuracy by Method — {meta['test_weeks']}-Week Backtest "
        f"(Jan 2025 → {test_end_str})\n"
        f"Trained on SPINS history through Dec 2024  |  "
        f"Tested on actual 2025 sell-through data",
        fontsize=11, pad=12,
    )
    ax2.set_ylim(0, max(wmapes) * 1.18)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax2.grid(True, axis="y", alpha=0.3, linestyle="--")
    ax2.spines[["top", "right"]].set_visible(False)

    # Annotate improvement arrow from best naive to LightGBM
    best_naive_idx  = methods_ordered.index("MA 4wk")
    lgbm_idx        = methods_ordered.index("LightGBM")
    best_naive_wmape = agg["MA 4wk"]["wmape"]
    lgbm_wmape_val   = agg["LightGBM"]["wmape"]
    ax2.annotate(
        f"−{best_naive_wmape - lgbm_wmape_val:.1f} pp improvement",
        xy=(lgbm_idx, lgbm_wmape_val + 0.5),
        xytext=(lgbm_idx - 0.8, max(wmapes) * 0.75),
        fontsize=10, color="#d62728", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.5),
    )
    plt.tight_layout()
    summary_path = os.path.join(OUTPUT_DIR, "v2_mo30_method_summary_chart.png")
    plt.savefig(summary_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Summary bar chart → {summary_path}")

    print(f"\n  Outputs saved to: {OUTPUT_DIR}")
    print(f"    v2_mo30_model_lgbm_jan2025.pkl")
    print(f"    v2_mo30_metrics.json")
    print(f"    v2_mo30_by_series.csv")
    print(f"    v2_mo30_comparison_chart.png   ← horse-race chart")
    print(f"    v2_mo30_method_summary_chart.png  ← FP&A slide bar chart")
    print("=" * 65)


if __name__ == "__main__":
    main()
