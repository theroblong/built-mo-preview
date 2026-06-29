"""MO_29 — Rigorous backtest: fixed Oct 2025 temporal cutoff, 26-week OOS holdout.

WHY THIS IS MORE RIGOROUS THAN MO_26
--------------------------------------
MO_26 used a rolling cutoff (last 13 weeks = val) trained through Jan 2026.
Problems:
  1. Only 13 OOS weeks — not long enough to prove seasonal generalization
  2. Dynamic cutoff means the test period changes every rerun
  3. No comparison against naive baselines — can't prove the model beats Excel

This script:
  1. Fixes the train/test boundary at Oct 1, 2025 (immovable)
  2. Tests on Nov 2025 – Apr 2026: 26 OOS weeks Connor/Jeff can verify against
     their own Excel actuals for the same period
  3. Adds three baselines: naive (last value), 4-week MA, 13-week MA
  4. Filters out MULO/national aggregate geographies (data artifact from MO_28)
  5. Uses a local-val window (last 8 training weeks) for early stopping so the
     test set is never touched during training
  6. Generates a multi-method comparison chart and full per-series metrics

Run from the scripts/ directory:
    python MO_29_backtest_oct2025.py

Outputs (in scripts/outputs/):
    v2_backtest_model_q50_oct2025.pkl   — retrained LightGBM (Oct 2025 cutoff)
    v2_backtest_metrics.json            — aggregate metrics: all methods
    v2_backtest_by_series.csv           — per-series metrics: all methods
    v2_backtest_comparison_chart.png    — 6-panel actual vs. all-methods chart
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
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR       = os.path.join(SCRIPT_DIR, "outputs")
PARQUET          = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")

V2_CUTOFF        = pd.Timestamp("2025-10-01", tz="UTC")   # fixed train/test boundary
LOCAL_VAL_WEEKS  = 8    # last N training weeks carved out for early stopping
MIN_TRAIN_WEEKS  = 26   # series must have this many weeks before V2_CUTOFF
MIN_TEST_WEEKS   = 13   # series must have this many weeks after V2_CUTOFF

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]

# Exact feature list from MO_26 (must match)
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
    objective="quantile",
    alpha=0.5,
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


# ── Metric helpers ─────────────────────────────────────────────────────────────
def wmape(actual, predicted):
    total = actual.sum()
    return float(np.abs(actual - predicted).sum() / total * 100) if total > 0 else np.nan

def mape_safe(actual, predicted, zero_thresh=1.0):
    mask = actual >= zero_thresh
    if mask.sum() == 0:
        return np.nan
    err = np.clip(np.abs(actual[mask] - predicted[mask]) / actual[mask], 0, 5.0)
    return float(err.mean() * 100)

def rmse(actual, predicted):
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))

def bias_pct(actual, predicted):
    total = actual.sum()
    return float((predicted.sum() - total) / (total + 1) * 100)


def main():
    print("=" * 65)
    print("MO_29  —  Rigorous Backtest  (Oct 2025 fixed cutoff)")
    print("=" * 65)

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

    print(f"  Total rows: {len(df):,}  |  Series: {df.groupby(GROUP_COLS).ngroups:,}")
    print(f"  Date range: {df['__time'].min().date()} → {df['__time'].max().date()}")

    # ── 2. Filter out MULO/national aggregate geographies ─────────────────────
    before = df.groupby(GROUP_COLS).ngroups
    if "geography_level" in df.columns:
        mulo_mask = df["geography_level"].str.upper().isin(["NATIONAL", "TOTAL"])
        df = df[~mulo_mask].copy()
        after = df.groupby(GROUP_COLS).ngroups
        print(f"\n  Excluded MULO/national geo rows: {mulo_mask.sum():,} rows "
              f"({before - after} series removed)")
    # Also exclude any geography_raw that looks like a MULO aggregate
    if "geography_raw" in df.columns:
        mulo_raw = df["geography_raw"].str.contains(
            "MULTI OUTLET|MULO|TOTAL US|ALL CHANNEL", case=False, na=False
        )
        df = df[~mulo_raw].copy()
        print(f"  After MULO raw string filter: {df.groupby(GROUP_COLS).ngroups:,} series")

    # ── 3. Filter to qualifying series ────────────────────────────────────────
    train_all = df[df["__time"] < V2_CUTOFF]
    test_all  = df[df["__time"] >= V2_CUTOFF]

    train_counts = train_all.groupby(GROUP_COLS).size().rename("train_weeks")
    test_counts  = test_all.groupby(GROUP_COLS).size().rename("test_weeks")
    coverage     = pd.concat([train_counts, test_counts], axis=1).fillna(0).astype(int)
    qualifying   = coverage[
        (coverage["train_weeks"] >= MIN_TRAIN_WEEKS) &
        (coverage["test_weeks"]  >= MIN_TEST_WEEKS)
    ]
    print(f"\n  Qualifying series (≥{MIN_TRAIN_WEEKS} train + ≥{MIN_TEST_WEEKS} test): "
          f"{len(qualifying):,} / {len(coverage):,}")

    qual_keys = set(qualifying.index.tolist())
    df["_key"] = list(zip(df["upc"], df["channel_outlet"],
                          df["retail_account"], df["geography_raw"]))
    df = df[df["_key"].isin(qual_keys)].copy()
    df = df.drop(columns=["_key"])
    print(f"  Rows after qualifying filter: {len(df):,}")

    # ── 4. Split ──────────────────────────────────────────────────────────────
    train_df = df[df["__time"] <  V2_CUTOFF].copy()
    test_df  = df[df["__time"] >= V2_CUTOFF].copy()

    # Carve local-val from end of training (for early stopping — never touches test)
    local_val_cutoff = V2_CUTOFF - pd.Timedelta(weeks=LOCAL_VAL_WEEKS)
    super_train = train_df[train_df["__time"] <  local_val_cutoff].copy()
    local_val   = train_df[train_df["__time"] >= local_val_cutoff].copy()

    print(f"\n  Super-train rows: {len(super_train):,}  "
          f"({super_train['__time'].min().date()} → {super_train['__time'].max().date()})")
    print(f"  Local-val rows:   {len(local_val):,}  "
          f"({local_val['__time'].min().date()} → {local_val['__time'].max().date()})")
    print(f"  Test rows:        {len(test_df):,}  "
          f"({test_df['__time'].min().date()} → {test_df['__time'].max().date()})")

    available = [c for c in FEATURE_COLS if c in df.columns]
    X_super   = super_train[available]
    y_super   = super_train["log_base_units"].values
    X_lval    = local_val[available]
    y_lval    = local_val["log_base_units"].values
    X_test    = test_df[available]

    # ── 5. Train LightGBM ─────────────────────────────────────────────────────
    print("\nTraining LightGBM q50  (Oct 2025 cutoff) …")
    model = lgb.LGBMRegressor(**LGBM_PARAMS)
    model.fit(
        X_super, y_super,
        eval_set=[(X_lval, y_lval)],
        callbacks=[
            lgb.early_stopping(50, verbose=False),
            lgb.log_evaluation(200),
        ],
    )
    print(f"  Best iteration: {model.best_iteration_}")

    preds_log   = model.predict(X_test)
    preds_units = np.expm1(np.clip(preds_log, 0, None))
    test_df     = test_df.copy()
    test_df["pred_lgbm"] = preds_units

    model_path = os.path.join(OUTPUT_DIR, "v2_backtest_model_q50_oct2025.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"  Model saved → {model_path}")

    # ── 6. Naive baselines ────────────────────────────────────────────────────
    # All baselines computed from the last available training observations per
    # series — same information cutoff as the model, no future data leakage.
    print("\nComputing naive baselines …")

    baseline_records = []
    for key, grp in train_df.groupby(GROUP_COLS):
        grp_s = grp.sort_values("__time")
        last_val   = grp_s["base_units"].iloc[-1]
        ma4_val    = grp_s["base_units"].iloc[-4:].mean()
        ma13_val   = grp_s["base_units"].iloc[-13:].mean()
        baseline_records.append({
            "upc":            key[0],
            "channel_outlet": key[1],
            "retail_account": key[2],
            "geography_raw":  key[3],
            "naive_last":     last_val,
            "ma4":            ma4_val,
            "ma13":           ma13_val,
        })

    baselines = pd.DataFrame(baseline_records)
    test_df = test_df.merge(baselines, on=GROUP_COLS, how="left")

    # ── 7. Per-series metrics ─────────────────────────────────────────────────
    print("Computing per-series metrics …")
    records = []
    for key, grp in test_df.groupby(GROUP_COLS):
        act  = grp["base_units"].values
        desc = grp["description"].iloc[0] if "description" in grp.columns else ""
        row  = {
            "upc":            key[0],
            "channel_outlet": key[1],
            "retail_account": key[2],
            "geography_raw":  key[3],
            "description":    desc,
            "test_weeks":     len(grp),
            "total_actual":   act.sum(),
            "avg_weekly":     act.mean(),
        }
        for method in ["pred_lgbm", "naive_last", "ma4", "ma13"]:
            pred = grp[method].values
            row[f"wmape_{method}"]  = wmape(act, pred)
            row[f"mape_{method}"]   = mape_safe(act, pred)
            row[f"rmse_{method}"]   = rmse(act, pred)
            row[f"bias_{method}"]   = bias_pct(act, pred)
        records.append(row)

    series_df = pd.DataFrame(records).sort_values("total_actual", ascending=False)
    series_path = os.path.join(OUTPUT_DIR, "v2_backtest_by_series.csv")
    series_df.to_csv(series_path, index=False)

    # ── 8. Aggregate metrics ──────────────────────────────────────────────────
    act_all = test_df["base_units"].values
    methods = {
        "LightGBM_v2_oct2025": "pred_lgbm",
        "Naive_last_value":     "naive_last",
        "Moving_avg_4wk":       "ma4",
        "Moving_avg_13wk":      "ma13",
    }

    agg = {}
    for label, col in methods.items():
        pred = test_df[col].values
        agg[label] = {
            "wmape":  round(wmape(act_all, pred), 2),
            "mape":   round(mape_safe(act_all, pred), 2),
            "rmse":   round(rmse(act_all, pred), 1),
            "bias":   round(bias_pct(act_all, pred), 2),
        }

    meta = {
        "backtest_run_at":    datetime.now(timezone.utc).isoformat(),
        "train_cutoff":       str(V2_CUTOFF.date()),
        "test_start":         str(test_df["__time"].min().date()),
        "test_end":           str(test_df["__time"].max().date()),
        "test_weeks":         int(test_df["__time"].nunique()),
        "qualifying_series":  len(qualifying),
        "super_train_rows":   int(len(super_train)),
        "local_val_rows":     int(len(local_val)),
        "test_rows":          int(len(test_df)),
        "lgbm_best_iter":     int(model.best_iteration_),
        "aggregate_metrics":  agg,
    }
    metrics_path = os.path.join(OUTPUT_DIR, "v2_backtest_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(meta, f, indent=2)

    # ── 9. Print results ──────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("BACKTEST RESULTS  (Oct 2025 cutoff, 26-week OOS test)")
    print("=" * 65)
    print(f"\n  Test period: {meta['test_start']} → {meta['test_end']}  "
          f"({meta['test_weeks']} weeks)")
    print(f"  Series:      {len(qualifying):,}  "
          f"(filtered to account-level geos, ≥26 train + ≥13 test weeks)")

    print(f"\n  {'METHOD':<25}  {'wMAPE':>7}  {'MAPE':>7}  {'RMSE':>8}  {'BIAS':>7}")
    print("  " + "─" * 55)
    for label, stats in agg.items():
        marker = " ◄" if label.startswith("LightGBM") else ""
        print(f"  {label:<25}  {stats['wmape']:>6.1f}%  "
              f"{stats['mape']:>6.1f}%  {stats['rmse']:>8.0f}  "
              f"{stats['bias']:>+6.1f}%{marker}")

    lgbm_wmape = agg["LightGBM_v2_oct2025"]["wmape"]
    naive_wmape = agg["Naive_last_value"]["wmape"]
    ma4_wmape   = agg["Moving_avg_4wk"]["wmape"]
    best_base   = min(naive_wmape, ma4_wmape, agg["Moving_avg_13wk"]["wmape"])
    improvement = best_base - lgbm_wmape

    print(f"\n  LightGBM improvement vs. best baseline:  "
          f"{improvement:+.1f} pp wMAPE  "
          f"({'better' if improvement > 0 else 'worse — investigate'})")

    # Volume-tier breakdown
    vol_p75 = series_df["total_actual"].quantile(0.75)
    vol_p25 = series_df["total_actual"].quantile(0.25)
    tiers = {
        "High-volume (top 25%)":   series_df[series_df["total_actual"] >= vol_p75],
        "Mid-volume  (mid 50%)":   series_df[(series_df["total_actual"] >= vol_p25) & (series_df["total_actual"] < vol_p75)],
        "Low-volume  (bot 25%)":   series_df[series_df["total_actual"] < vol_p25],
    }
    print(f"\n  wMAPE by volume tier  (LightGBM vs. best naive):")
    for tier_name, tier_df in tiers.items():
        lgbm_t  = tier_df["wmape_pred_lgbm"].mean()
        naive_t = tier_df[["wmape_naive_last", "wmape_ma4", "wmape_ma13"]].min(axis=1).mean()
        delta   = naive_t - lgbm_t
        print(f"    {tier_name}:  LightGBM {lgbm_t:.1f}%  |  "
              f"Best naive {naive_t:.1f}%  |  delta {delta:+.1f} pp")

    print(f"\n  Top 10 series by volume (LightGBM wMAPE):")
    print(f"  {'UPC':>14}  {'Description':30}  {'Account':22}  "
          f"{'LGBM':>6}  {'Naive':>6}  {'MA4':>6}")
    print("  " + "─" * 85)
    for _, r in series_df.head(10).iterrows():
        desc = str(r["description"])[:30].ljust(30)
        acct = str(r["retail_account"])[:22].ljust(22)
        print(f"  {r['upc']:>14}  {desc}  {acct}  "
              f"{r['wmape_pred_lgbm']:>5.1f}%  "
              f"{r['wmape_naive_last']:>5.1f}%  "
              f"{r['wmape_ma4']:>5.1f}%")

    # ROI frame
    print(f"\n  ROI FRAME  ($1M per 1pp wMAPE improvement vs. Excel baseline):")
    print(f"    LightGBM wMAPE:     {lgbm_wmape:.1f}%")
    print(f"    Best naive wMAPE:   {best_base:.1f}%  (proxy for current Excel process)")
    print(f"    Improvement:        {improvement:+.1f} pp")
    est_roi = improvement * 1_000_000
    if est_roi > 0:
        print(f"    Estimated ROI:      ~${est_roi:,.0f}  (at Brian's $1M/1pp multiplier)")
    else:
        print(f"    Note: model underperforms naive — investigate data quality / features")

    # ── 10. Comparison chart ─────────────────────────────────────────────────
    print("\nGenerating comparison chart …")
    top_keys = series_df.head(6).apply(
        lambda r: (r["upc"], r["channel_outlet"], r["retail_account"], r["geography_raw"]),
        axis=1,
    ).tolist()

    colors = {
        "Actual":          ("#1f77b4", 2.0, "-"),
        "LightGBM v2":     ("#d62728", 1.8, "--"),
        "Naive last value":("#2ca02c", 1.4, ":"),
        "4-week MA":       ("#ff7f0e", 1.4, "-."),
        "13-week MA":      ("#9467bd", 1.2, ":"),
    }

    # Show last 26 training weeks + all test weeks for context
    context_cutoff = V2_CUTOFF - pd.Timedelta(weeks=26)

    fig = plt.figure(figsize=(20, 18))
    gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.55, wspace=0.30)

    for i, key in enumerate(top_keys):
        ax = fig.add_subplot(gs[i // 2, i % 2])

        mask_full = (
            (df["upc"] == key[0]) &
            (df["channel_outlet"] == key[1]) &
            (df["retail_account"] == key[2]) &
            (df["geography_raw"]  == key[3])
        )
        grp_full  = df[mask_full & (df["__time"] >= context_cutoff)].sort_values("__time")

        mask_test = (
            (test_df["upc"] == key[0]) &
            (test_df["channel_outlet"] == key[1]) &
            (test_df["retail_account"] == key[2]) &
            (test_df["geography_raw"]  == key[3])
        )
        grp_test = test_df[mask_test].sort_values("__time")

        ax.plot(grp_full["__time"], grp_full["base_units"],
                color=colors["Actual"][0], linewidth=colors["Actual"][1],
                linestyle=colors["Actual"][2], label="Actual", zorder=5)

        if len(grp_test) > 0:
            for method_label, col, color_key in [
                ("LightGBM v2",      "pred_lgbm",  "LightGBM v2"),
                ("Naive last value", "naive_last",  "Naive last value"),
                ("4-week MA",        "ma4",         "4-week MA"),
                ("13-week MA",       "ma13",        "13-week MA"),
            ]:
                c, lw, ls = colors[color_key]
                ax.plot(grp_test["__time"], grp_test[col],
                        color=c, linewidth=lw, linestyle=ls,
                        label=method_label, alpha=0.85)

        ax.axvline(V2_CUTOFF, color="gray", linestyle=":", linewidth=1.2,
                   alpha=0.7, label="Train/test cutoff")
        ax.axvspan(V2_CUTOFF, test_df["__time"].max(),
                   alpha=0.04, color="red", label="_nolegend_")

        sr = series_df[
            (series_df["upc"] == key[0]) &
            (series_df["retail_account"] == key[2])
        ]
        desc = str(grp_full["description"].iloc[0])[:28] if len(grp_full) > 0 else key[0]
        acct = str(key[2])[:18]
        lgbm_w  = sr["wmape_pred_lgbm"].iloc[0]  if len(sr) > 0 else np.nan
        naive_w = sr["wmape_naive_last"].iloc[0] if len(sr) > 0 else np.nan

        ax.set_title(
            f"{desc}\n{acct}  |  LightGBM {lgbm_w:.1f}%  Naive {naive_w:.1f}%  wMAPE",
            fontsize=9
        )
        ax.set_ylabel("Base Units / Week", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.25)
        if i == 0:
            ax.legend(fontsize=7, loc="upper left", ncol=2)

    fig.suptitle(
        "Backtest: Actual vs. All Methods — Oct 2025 Fixed Cutoff  "
        f"({meta['test_start']} → {meta['test_end']})\n"
        "Shaded region = out-of-sample test period  |  "
        "Dotted vertical line = train/test boundary",
        fontsize=10, y=0.98,
    )
    chart_path = os.path.join(OUTPUT_DIR, "v2_backtest_comparison_chart.png")
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved → {chart_path}")

    print(f"\n  Outputs saved to: {OUTPUT_DIR}")
    print(f"    v2_backtest_model_q50_oct2025.pkl")
    print(f"    v2_backtest_metrics.json")
    print(f"    v2_backtest_by_series.csv")
    print(f"    v2_backtest_comparison_chart.png")
    print("=" * 65)


if __name__ == "__main__":
    main()
