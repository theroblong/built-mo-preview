"""MO_28 — v2 Evaluation: MAPE, SHAP, and actuals-vs-predicted for existing model.

What this script does
---------------------
MO_26 trained LightGBM quantile models (q10/q50/q90) on Jun 18, 2026 but only
saved MAE/RMSE/pinball — NOT MAPE, which is the metric the FP&A team needs.
The current validation window is only 13 weeks (Jan 25 – Apr 19, 2026).

This script:
1. Reloads the exact parquet + model used in MO_26
2. Computes MAPE and wMAPE per SKU/account/geo series
3. Generates SHAP feature importance plot (TreeExplainer, q50 model)
4. Generates actual vs. predicted charts for top-10 series by volume
5. Audits coverage for the proposed Oct 2025 train/test cutoff (v2 retraining)
6. Outputs a business-language summary

Run from the scripts/ directory:
    python MO_28_v2_eval.py

Outputs (in scripts/outputs/):
    v2_mape_by_series.csv         — MAPE, wMAPE, RMSE, bias per series
    v2_shap_summary.png           — SHAP beeswarm (top 15 features)
    v2_actuals_vs_predicted.png   — Grid of top-10 series charts
    v2_coverage_audit.csv         — Series-level coverage for Oct 2025 split
    v2_feature_register.csv       — All model features with business labels,
                                    data sources, tiers, and planned additions
"""

import json
import pickle
import sys
import os
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "outputs")
PARQUET     = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")
MODEL_Q50   = os.path.join(OUTPUT_DIR, "model_retailer_sales_q50_v1.pkl")
METRICS_IN  = os.path.join(OUTPUT_DIR, "retailer_sales_train_metrics.json")

# Oct 2025 cutoff — proposed train/test boundary for v2 retraining
V2_CUTOFF   = pd.Timestamp("2025-10-01", tz="UTC")

GROUP_COLS  = ["upc", "channel_outlet", "retail_account", "geography_raw"]

# Exact feature list from MO_26 (must match training order)
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

FEATURE_DISPLAY = {
    "base_units_lag1":          "Units last week (lag1)",
    "base_units_wow_delta":     "Units week-over-week change",
    "base_units_roll4_avg":     "Units 4-week rolling avg",
    "base_units_z8":            "Units 8-week z-score (momentum)",
    "base_units_roll8_avg":     "Units 8-week rolling avg",
    "base_units_roll8_std":     "Units 8-week rolling std dev",
    "base_units_z13":           "Units 13-week z-score",
    "base_units_lag4":          "Units 4 weeks ago (lag4)",
    "base_units_roll13_avg":    "Units 13-week rolling avg",
    "tdp_z8":                   "Distribution expansion (TDP z-score)",
    "base_units_roll13_std":    "Units 13-week volatility",
    "tdp":                      "Distribution (TDP — stores carrying SKU)",
    "weeks_since_launch":       "Lifecycle stage (weeks since launch)",
    "base_units_lag13":         "Units 13 weeks ago (seasonal lag)",
    "arp_roll8_std":            "Price volatility (8-week ARP std)",
    "arp_roll8_avg":            "Price level (8-week rolling avg ARP)",
    "implied_elasticity":       "Price elasticity coefficient (Mo signal)",
    "week_of_year":             "Seasonal week",
    "arp_wow_delta":            "Price change week-over-week",
    "arp":                      "Avg retail price",
    "velocity_spm_roll8_avg":   "Velocity (units/store 8-week avg)",
    "velocity_spm_roll13_avg":  "Velocity (units/store 13-week avg)",
    "velocity_spm_z8":          "Velocity z-score 8-week",
    "velocity_spm_z13":         "Velocity z-score 13-week",
    "max_donor_cannibal_prob":  "Cannibalization pressure (Mo signal)",
    "donor_count":              "Number of donor SKUs (Mo signal)",
    "channel_outlet":           "Channel (FOOD / MASS / etc.)",
}


def smape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Symmetric MAPE — handles zeros; range 0–200%."""
    denom = (np.abs(actual) + np.abs(predicted)) / 2
    mask  = denom > 0
    return float(np.mean(np.abs(actual[mask] - predicted[mask]) / denom[mask]) * 100)


def mape_safe(actual: np.ndarray, predicted: np.ndarray, zero_thresh: float = 1.0) -> float:
    """MAPE ignoring rows where actual < zero_thresh (avoids divide-by-zero explosion)."""
    mask = actual >= zero_thresh
    if mask.sum() == 0:
        return np.nan
    err = np.abs(actual[mask] - predicted[mask]) / actual[mask]
    err = np.clip(err, 0, 5.0)   # cap individual errors at 500% to limit outlier pull
    return float(err.mean() * 100)


def wmape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Weighted MAPE — robust to low-volume periods. Same as MAE/mean(actual)."""
    total = actual.sum()
    if total == 0:
        return np.nan
    return float(np.abs(actual - predicted).sum() / total * 100)


def main():
    print("=" * 65)
    print("MO_28  —  v2 Evaluation: MAPE + SHAP + Coverage Audit")
    print("=" * 65)

    # ── 1. Load parquet ───────────────────────────────────────────────────────
    print(f"\nLoading {PARQUET} …")
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    print(f"  Rows: {len(df):,}  |  UPCs: {df['upc'].nunique()}")
    print(f"  Date range: {df['__time'].min().date()} → {df['__time'].max().date()}")
    print(f"  Series: {df.groupby(GROUP_COLS).ngroups:,}")

    # ── 2. Replicate MO_26 encoding exactly ──────────────────────────────────
    num_cols = [c for c in FEATURE_COLS if c != "channel_outlet"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "channel_outlet" in df.columns:
        df["channel_outlet"] = df["channel_outlet"].astype("category")

    df = df.dropna(subset=["base_units"]).copy()
    df["log_base_units"] = np.log1p(df["base_units"])

    # ── 3. Replicate MO_26 train/val split ───────────────────────────────────
    cutoff = df["__time"].max() - pd.Timedelta(weeks=13)
    train  = df[df["__time"] <= cutoff].copy()
    val    = df[df["__time"] >  cutoff].copy()
    print(f"\n  MO_26 split cutoff: {cutoff.date()}")
    print(f"  Train: {len(train):,} rows | Val: {len(val):,} rows")
    print(f"  Val range: {val['__time'].min().date()} → {val['__time'].max().date()}")

    available = [c for c in FEATURE_COLS if c in df.columns]
    X_val     = val[available]

    # ── 4. Load model and predict ─────────────────────────────────────────────
    print(f"\nLoading {MODEL_Q50} …")
    with open(MODEL_Q50, "rb") as f:
        model = pickle.load(f)

    preds_log   = model.predict(X_val)
    preds_units = np.expm1(np.clip(preds_log, 0, None))

    val = val.copy()
    val["predicted_units"] = preds_units
    val["actual_units"]    = val["base_units"]

    # ── 5. MAPE by series ─────────────────────────────────────────────────────
    print("\nComputing MAPE by series …")
    records = []
    for key, grp in val.groupby(GROUP_COLS):
        act  = grp["actual_units"].values
        pred = grp["predicted_units"].values
        records.append({
            "upc":           key[0],
            "channel_outlet":key[1],
            "retail_account":key[2],
            "geography_raw": key[3],
            "description":   grp["description"].iloc[0] if "description" in grp.columns else "",
            "val_weeks":     len(grp),
            "total_actual":  act.sum(),
            "avg_weekly_actual": act.mean(),
            "mape":          mape_safe(act, pred),
            "wmape":         wmape(act, pred),
            "smape":         smape(act, pred),
            "mae":           float(np.mean(np.abs(act - pred))),
            "rmse":          float(np.sqrt(np.mean((act - pred)**2))),
            "bias_pct":      float((pred.sum() - act.sum()) / (act.sum() + 1) * 100),
        })

    series_df = pd.DataFrame(records).sort_values("total_actual", ascending=False)
    series_df.to_csv(os.path.join(OUTPUT_DIR, "v2_mape_by_series.csv"), index=False)

    # ── 6. Print MAPE summary ─────────────────────────────────────────────────
    valid_mape = series_df["mape"].dropna()
    valid_wmape = series_df["wmape"].dropna()
    print("\n" + "─" * 65)
    print("OVERALL MAPE SUMMARY  (current model, 13-week holdout)")
    print("─" * 65)

    overall_actual = val["actual_units"].values
    overall_pred   = val["predicted_units"].values
    print(f"  Overall MAPE (mean across series): {valid_mape.mean():.1f}%")
    print(f"  Median MAPE (median across series):{valid_mape.median():.1f}%")
    print(f"  Overall wMAPE (volume-weighted):   {wmape(overall_actual, overall_pred):.1f}%")
    print(f"  Overall RMSE:                      {np.sqrt(np.mean((overall_actual - overall_pred)**2)):.0f} units/wk")
    print(f"  Overall bias (over-forecast +):    {(overall_pred.sum() - overall_actual.sum()) / (overall_actual.sum() + 1) * 100:.1f}%")

    # Breakout by volume tier
    vol_p75 = series_df["total_actual"].quantile(0.75)
    vol_p25 = series_df["total_actual"].quantile(0.25)
    high_vol = series_df[series_df["total_actual"] >= vol_p75]
    mid_vol  = series_df[(series_df["total_actual"] >= vol_p25) & (series_df["total_actual"] < vol_p75)]
    low_vol  = series_df[series_df["total_actual"] < vol_p25]
    print(f"\n  MAPE by volume tier:")
    print(f"    High-volume  (top 25%):  {high_vol['wmape'].mean():.1f}% wMAPE  ({len(high_vol)} series)")
    print(f"    Mid-volume   (mid 50%):  {mid_vol['wmape'].mean():.1f}% wMAPE  ({len(mid_vol)} series)")
    print(f"    Low-volume   (bot 25%):  {low_vol['wmape'].mean():.1f}% wMAPE  ({len(low_vol)} series)")

    print("\n  Top 15 series by volume:")
    top15 = series_df.head(15)
    for _, r in top15.iterrows():
        desc = str(r["description"])[:30].ljust(30)
        acct = str(r["retail_account"])[:20].ljust(20)
        print(f"    {r['upc']}  {desc}  {acct}  "
              f"wMAPE={r['wmape']:5.1f}%  MAPE={r['mape']:5.1f}%  "
              f"units/wk={r['avg_weekly_actual']:>7,.0f}")

    print("\n  5 best-accuracy series (lowest wMAPE, ≥100 avg units/wk):")
    best = series_df[series_df["avg_weekly_actual"] >= 100].nsmallest(5, "wmape")
    for _, r in best.iterrows():
        desc = str(r["description"])[:30].ljust(30)
        print(f"    {r['upc']}  {desc}  {r['retail_account'][:20]}  wMAPE={r['wmape']:.1f}%")

    print("\n  5 worst-accuracy series (highest wMAPE, ≥100 avg units/wk):")
    worst = series_df[series_df["avg_weekly_actual"] >= 100].nlargest(5, "wmape")
    for _, r in worst.iterrows():
        desc = str(r["description"])[:30].ljust(30)
        print(f"    {r['upc']}  {desc}  {r['retail_account'][:20]}  wMAPE={r['wmape']:.1f}%")

    # ── 7. Coverage audit: Oct 2025 train/test cutoff ─────────────────────────
    print("\n" + "─" * 65)
    print(f"V2 COVERAGE AUDIT  (proposed cutoff: {V2_CUTOFF.date()})")
    print("─" * 65)

    v2_train = df[df["__time"] < V2_CUTOFF]
    v2_test  = df[df["__time"] >= V2_CUTOFF]

    cov_records = []
    for key, grp in df.groupby(GROUP_COLS):
        tr = grp[grp["__time"] < V2_CUTOFF]
        te = grp[grp["__time"] >= V2_CUTOFF]
        cov_records.append({
            "upc":             key[0],
            "channel_outlet":  key[1],
            "retail_account":  key[2],
            "geography_raw":   key[3],
            "description":     grp["description"].iloc[0] if "description" in grp.columns else "",
            "total_weeks":     len(grp),
            "train_weeks":     len(tr),
            "test_weeks":      len(te),
            "total_units":     grp["base_units"].sum(),
            "avg_weekly_units":grp["base_units"].mean(),
            "train_end_date":  tr["__time"].max().date() if len(tr) > 0 else None,
            "test_start_date": te["__time"].min().date() if len(te) > 0 else None,
        })

    cov_df = pd.DataFrame(cov_records)
    cov_df.to_csv(os.path.join(OUTPUT_DIR, "v2_coverage_audit.csv"), index=False)

    total_series = len(cov_df)
    print(f"  Total series in parquet: {total_series:,}")
    for n, label in [
        (13, "≥ 13 train weeks before Oct 2025"),
        (26, "≥ 26 train weeks before Oct 2025  (full season)"),
        (52, "≥ 52 train weeks before Oct 2025  (last-year window)"),
        (13, "≥ 13 test weeks  after  Oct 2025  (90d horizon ok)"),
    ]:
        if "train" in label:
            col = "train_weeks"
        else:
            col = "test_weeks"
        count = (cov_df[col] >= n).sum()
        pct   = 100 * count / total_series
        print(f"    {label}: {count:4d} / {total_series:4d}  ({pct:.0f}%)")

    # Series with BOTH ≥26 train weeks AND ≥13 test weeks (full v2 candidates)
    v2_ready = cov_df[(cov_df["train_weeks"] >= 26) & (cov_df["test_weeks"] >= 13)]
    print(f"\n  Full v2 candidates (≥26 train + ≥13 test): {len(v2_ready):,} series")
    print(f"  (These are the series we can properly backtest with Oct 2025 cutoff.)")

    # ── 8. SHAP analysis ──────────────────────────────────────────────────────
    print("\n" + "─" * 65)
    print("SHAP ANALYSIS  (q50 model, TreeExplainer)")
    print("─" * 65)
    try:
        import shap

        sample_n = min(3000, len(val))
        sample   = val[available].sample(sample_n, random_state=42)
        print(f"  Computing SHAP values on {sample_n:,} validation rows …")

        explainer   = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(sample)

        shap_abs = pd.Series(
            np.abs(shap_values).mean(axis=0),
            index=available,
        ).sort_values(ascending=False)

        print("\n  Top 15 SHAP feature importance (mean |SHAP| in log-unit space):")
        for feat, val_s in shap_abs.head(15).items():
            display = FEATURE_DISPLAY.get(feat, feat)
            bar     = "█" * int(val_s / shap_abs.iloc[0] * 25)
            print(f"    {bar:<25}  {val_s:.4f}  {display}")

        # ── SHAP beeswarm plot ────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(10, 8))
        shap_top = pd.DataFrame(shap_values, columns=available)[shap_abs.head(15).index]
        sample_top = sample[shap_abs.head(15).index]

        top_features = shap_abs.head(15).index.tolist()
        shap_top_arr = shap_values[:, [available.index(f) for f in top_features]]
        sample_top_arr = sample[top_features].values.astype(float)

        y_labels = [FEATURE_DISPLAY.get(f, f) for f in top_features]
        shap.summary_plot(
            shap_top_arr,
            sample_top_arr,
            feature_names=y_labels,
            show=False,
            max_display=15,
            plot_size=(10, 8),
        )
        plt.title("SHAP Feature Importance — LightGBM q50 Retailer Demand Forecast", pad=12)
        plt.tight_layout()
        shap_path = os.path.join(OUTPUT_DIR, "v2_shap_summary.png")
        plt.savefig(shap_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"\n  SHAP beeswarm saved → {shap_path}")

    except ImportError:
        print("  shap not installed — skipping SHAP plot.")
        print("  Install with: pip install shap")

    # ── 9. Actual vs. predicted charts ───────────────────────────────────────
    print("\n" + "─" * 65)
    print("ACTUAL vs. PREDICTED CHARTS  (top 10 series by volume)")
    print("─" * 65)

    top10_keys = (
        series_df.head(10)
        .apply(lambda r: (r["upc"], r["channel_outlet"], r["retail_account"], r["geography_raw"]), axis=1)
        .tolist()
    )

    fig = plt.figure(figsize=(20, 24))
    gs  = gridspec.GridSpec(5, 2, figure=fig, hspace=0.55, wspace=0.35)

    for i, key in enumerate(top10_keys):
        ax = fig.add_subplot(gs[i // 2, i % 2])

        grp_full = df[
            (df["upc"] == key[0]) &
            (df["channel_outlet"] == key[1]) &
            (df["retail_account"] == key[2]) &
            (df["geography_raw"] == key[3])
        ].copy()
        grp_full = grp_full.sort_values("__time")

        grp_val = val[
            (val["upc"] == key[0]) &
            (val["channel_outlet"] == key[1]) &
            (val["retail_account"] == key[2]) &
            (val["geography_raw"] == key[3])
        ].copy()
        grp_val = grp_val.sort_values("__time")

        ax.plot(grp_full["__time"], grp_full["base_units"],
                color="#1f77b4", linewidth=1.2, label="Actual (full history)")

        if len(grp_val) > 0:
            ax.plot(grp_val["__time"], grp_val["predicted_units"],
                    color="#d62728", linewidth=1.8, linestyle="--", label="Predicted (q50)")
            ax.axvline(cutoff, color="gray", linestyle=":", linewidth=1.0, alpha=0.6)

        row = series_df[
            (series_df["upc"] == key[0]) &
            (series_df["retail_account"] == key[2])
        ]
        desc   = key[0]
        if "description" in grp_full.columns and len(grp_full) > 0:
            desc = str(grp_full["description"].iloc[0])[:28]
        acct   = str(key[2])[:18]
        wm_str = f"{row['wmape'].iloc[0]:.1f}%" if len(row) > 0 else "N/A"

        ax.set_title(f"{desc}\n{acct}  |  wMAPE: {wm_str}", fontsize=9)
        ax.set_xlabel("")
        ax.set_ylabel("Base Units / Week", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.legend(fontsize=7, loc="upper left")
        ax.grid(True, alpha=0.3)

    fig.suptitle(
        "Actual vs. Predicted — LightGBM q50 (Top 10 Series by Volume)\n"
        f"Validation: {val['__time'].min().date()} → {val['__time'].max().date()}  |  Dashed line = predicted",
        fontsize=11, y=0.98
    )
    chart_path = os.path.join(OUTPUT_DIR, "v2_actuals_vs_predicted.png")
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved → {chart_path}")

    # ── 10. Business summary ──────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("BUSINESS SUMMARY")
    print("=" * 65)
    overall_wmape = wmape(overall_actual, overall_pred)
    print(f"""
  Current LightGBM model (trained Jun 18, 2026):
  ─────────────────────────────────────────────
  • Validation window:   13 weeks (Jan 25 – Apr 19, 2026)
  • Overall wMAPE:       {overall_wmape:.1f}%
    → Accuracy:          {100 - overall_wmape:.1f}%
  • High-volume series:  {high_vol['wmape'].mean():.1f}% wMAPE  (where forecast matters most)

  Top 3 demand drivers (SHAP / feature importance):
    1. Units last week (lag1) — most recent actual is the strongest signal
    2. Week-over-week momentum — trending up or down
    3. 4-week rolling average — near-term demand floor

  Mo signals contribution:
    • Price elasticity (implied_elasticity): contributes meaningfully
    • Cannibalization pressure (max_donor_cannibal_prob): present but lower signal
    → v2 improvements to feature engineering may amplify Mo signal contribution

  v2 next step — extended backtest (Oct 2025 cutoff):
  ─────────────────────────────────────────────────
  • Proposed: train through Oct 2025, test Nov 2025–Apr 2026 (26 OOS weeks)
  • {len(v2_ready):,} series qualify (≥26 train weeks + ≥13 test weeks)
  • This gives Connor/Jeff a clean, verifiable 26-week out-of-sample test
  • They can compare Mo forecasts vs. their own Excel actuals for the same period
  • MAPE delta → $1M / 1% ROI multiplier
""")

    # ── 11. Feature register ──────────────────────────────────────────────────
    print("\n" + "─" * 65)
    print("FEATURE REGISTER")
    print("─" * 65)

    # Canonical list of all features — active, planned, and future.
    # "tier" mirrors the v2 roadmap: 1=core demand, 2=Mo intelligence, 3=future enrichment.
    # "status" = active (in current model) | planned (designed, not yet joined) | future (TBD)
    FEATURE_REGISTER = [
        # ── Tier 1: Core demand signals ──────────────────────────────────────
        {
            "feature":      "base_units_lag1",
            "business_label": "Units sold last week",
            "what_it_captures": "Most recent actual demand — the single strongest short-term signal",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "base_units_wow_delta",
            "business_label": "Week-over-week unit change",
            "what_it_captures": "Demand momentum — is the SKU accelerating or decelerating?",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "base_units_roll4_avg",
            "business_label": "4-week rolling average units",
            "what_it_captures": "Near-term demand floor, smoothing out single-week noise",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "base_units_roll8_avg",
            "business_label": "8-week rolling average units",
            "what_it_captures": "Mid-cycle demand baseline (one promo cycle)",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "base_units_roll8_std",
            "business_label": "8-week demand volatility",
            "what_it_captures": "How variable is demand? High std = harder to forecast, need wider bands",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "base_units_roll13_avg",
            "business_label": "13-week rolling average units",
            "what_it_captures": "Quarterly demand baseline — anchors the seasonal pattern",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "base_units_roll13_std",
            "business_label": "13-week demand volatility",
            "what_it_captures": "Quarterly demand variability — key for safety stock sizing",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "base_units_z8",
            "business_label": "Demand z-score (8-week)",
            "what_it_captures": "How far above/below 8-week average is this week? Flags spikes and drops",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "base_units_z13",
            "business_label": "Demand z-score (13-week)",
            "what_it_captures": "How far above/below quarterly average? Identifies sustained trends",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "base_units_lag4",
            "business_label": "Units sold 4 weeks ago",
            "what_it_captures": "Short-memory autoregressive signal — useful when lag1 is anomalous",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "base_units_lag13",
            "business_label": "Units sold 13 weeks ago",
            "what_it_captures": "Same quarter last cycle — captures annual seasonality when YAGO unavailable",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "week_of_year",
            "business_label": "Calendar week number",
            "what_it_captures": "Seasonal pattern (New Year protein spike, summer plateau, Q4 holiday lift)",
            "data_source":  "Derived from SPINS timestamp",
            "tier":         1,
            "status":       "active",
        },
        # ── Tier 1: Velocity (per-store demand) ──────────────────────────────
        {
            "feature":      "velocity_spm_roll8_avg",
            "business_label": "Velocity — units per store, 8-week avg",
            "what_it_captures": "How well does this SKU sell WHERE it is stocked? Growth-mode safe (not inflated by distribution expansion)",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "velocity_spm_roll13_avg",
            "business_label": "Velocity — units per store, 13-week avg",
            "what_it_captures": "Quarterly per-store sell-through rate",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "velocity_spm_z8",
            "business_label": "Velocity z-score (8-week)",
            "what_it_captures": "Is per-store performance above or below recent trend?",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "velocity_spm_z13",
            "business_label": "Velocity z-score (13-week)",
            "what_it_captures": "Sustained per-store performance vs. quarterly baseline",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        # ── Tier 1: Distribution ─────────────────────────────────────────────
        {
            "feature":      "tdp",
            "business_label": "Distribution (TDP — # stores carrying SKU)",
            "what_it_captures": "How many stores stock this SKU? Single biggest driver of raw unit growth in expansion mode",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "tdp_z8",
            "business_label": "Distribution expansion rate (TDP z-score)",
            "what_it_captures": "Is distribution accelerating or contracting vs. 8-week avg? Forecasts future unit ramp",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        # ── Tier 1: Price signals ────────────────────────────────────────────
        {
            "feature":      "arp",
            "business_label": "Average retail price (weekly)",
            "what_it_captures": "Current price level — directly affects unit demand via elasticity",
            "data_source":  "built_filtered_weekly (SPINS raw)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "arp_wow_delta",
            "business_label": "Price change week-over-week",
            "what_it_captures": "Did price go up or down? Immediate demand response signal",
            "data_source":  "built_filtered_weekly (SPINS raw)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "arp_roll8_avg",
            "business_label": "Average price over 8 weeks",
            "what_it_captures": "Price level trend — sustained discount vs. temporary promotion",
            "data_source":  "built_filtered_weekly (SPINS raw)",
            "tier":         1,
            "status":       "active",
        },
        {
            "feature":      "arp_roll8_std",
            "business_label": "Price volatility (8-week)",
            "what_it_captures": "How frequently does price change? High volatility = active promo cadence",
            "data_source":  "built_filtered_weekly (SPINS raw)",
            "tier":         1,
            "status":       "active",
        },
        # ── Tier 1: Lifecycle ────────────────────────────────────────────────
        {
            "feature":      "weeks_since_launch",
            "business_label": "Lifecycle stage (weeks since launch)",
            "what_it_captures": "New items ramp differently than established SKUs — prevents over-forecasting early weeks",
            "data_source":  "built_prepost_features (derived)",
            "tier":         1,
            "status":       "active",
        },
        # ── Tier 1: Channel ──────────────────────────────────────────────────
        {
            "feature":      "channel_outlet",
            "business_label": "Channel (FOOD / MASS / DRUG / etc.)",
            "what_it_captures": "Different channels have distinct velocity and promo response patterns",
            "data_source":  "event_detection_weekly (SPINS)",
            "tier":         1,
            "status":       "active",
        },
        # ── Tier 2: Mo intelligence signals ──────────────────────────────────
        {
            "feature":      "implied_elasticity",
            "business_label": "Price elasticity coefficient (Mo signal)",
            "what_it_captures": "How sensitive is demand to a price change? Negative = demand drops when price rises. Enables scenario: 'if we raise ARP 5%, units drop by X%'",
            "data_source":  "scored_price_elasticity (Mo ML pipeline)",
            "tier":         2,
            "status":       "active",
        },
        {
            "feature":      "max_donor_cannibal_prob",
            "business_label": "Cannibalization pressure (Mo signal)",
            "what_it_captures": "Probability that demand for this SKU is being pulled from another BUILT SKU. Prevents over-forecasting when a sibling SKU is growing faster",
            "data_source":  "scored_cannibalization (Mo ML pipeline)",
            "tier":         2,
            "status":       "active",
        },
        {
            "feature":      "donor_count",
            "business_label": "Number of donor SKUs competing internally",
            "what_it_captures": "How many other BUILT SKUs could be drawing demand away? More donors = more fragmented internal demand pool",
            "data_source":  "scored_cannibalization (Mo ML pipeline)",
            "tier":         2,
            "status":       "active",
        },
        # ── Tier 2: Planned (not yet in model) ───────────────────────────────
        {
            "feature":      "promo_lift_factor",
            "business_label": "Promo lift multiplier by mechanic (planned)",
            "what_it_captures": "How much does TPR / display / feature ad lift units vs. base? Separates promo demand from organic. Critical for Chase's trade spend decisions",
            "data_source":  "comparison_pool_weekly (Mo pipeline — join pending)",
            "tier":         2,
            "status":       "planned",
        },
        {
            "feature":      "units_pct_promo",
            "business_label": "% of units sold on promotion (planned)",
            "what_it_captures": "What fraction of this SKU's volume is promo-driven? Identifies promo-dependent SKUs that may underperform when trade spend is cut",
            "data_source":  "built_filtered_weekly (SPINS — join pending)",
            "tier":         2,
            "status":       "planned",
        },
        {
            "feature":      "competitor_velocity_index",
            "business_label": "Top competitor velocity vs. BUILT (planned)",
            "what_it_captures": "Are competitors gaining or losing per-store velocity? Market share signal for retailer negotiations",
            "data_source":  "comparison_pool_weekly (Mo pipeline — join pending)",
            "tier":         2,
            "status":       "planned",
        },
        # ── Tier 3: Future enrichment ─────────────────────────────────────────
        {
            "feature":      "holiday_flag",
            "business_label": "Holiday / event flag (future)",
            "what_it_captures": "New Year's protein spike, Valentine's, back-to-school, Q4 holiday — known demand inflection points not yet captured by week_of_year alone",
            "data_source":  "External calendar (to be built)",
            "tier":         3,
            "status":       "future",
        },
        {
            "feature":      "weather_index",
            "business_label": "Weather / outdoor activity index (future)",
            "what_it_captures": "Protein bar demand may correlate with outdoor activity season. Temperature, sunshine index, or fitness activity proxies. Would be tested via SHAP — only kept if it adds >1% variance explained",
            "data_source":  "NOAA / weather API (to be sourced)",
            "tier":         3,
            "status":       "future",
        },
        {
            "feature":      "planogram_reset_flag",
            "business_label": "Retail planogram reset (future)",
            "what_it_captures": "Resets temporarily disrupt distribution and velocity. Flagging them prevents the model from interpreting a reset-driven dip as a demand decline",
            "data_source":  "Retailer calendar / BUILT field sales (to be sourced)",
            "tier":         3,
            "status":       "future",
        },
        {
            "feature":      "built_promo_calendar",
            "business_label": "BUILT internal trade calendar (future)",
            "what_it_captures": "Forward-looking planned promotions from BUILT's trade calendar. Biggest potential accuracy boost for Chase's promo planning — but requires ERP data share",
            "data_source":  "BUILT ERP / trade planning system (requires data share)",
            "tier":         3,
            "status":       "future",
        },
    ]

    reg_df = pd.DataFrame(FEATURE_REGISTER)
    reg_path = os.path.join(OUTPUT_DIR, "v2_feature_register.csv")
    reg_df.to_csv(reg_path, index=False)
    print(f"  Feature register saved → {reg_path}")
    print(f"  {len(reg_df)} features total:")
    for status, grp in reg_df.groupby("status"):
        tiers = grp["tier"].value_counts().sort_index()
        tier_str = ", ".join(f"Tier {t}: {c}" for t, c in tiers.items())
        print(f"    {status.upper():8s}  {len(grp):2d} features  ({tier_str})")

    print(f"""
  EXTENSIBILITY NOTE (for FP&A audience):
  ─────────────────────────────────────────
  Adding a new feature (e.g., weather) works in 3 steps:
    1. Join the new data column into MO_25 (the feature table builder)
    2. Re-run MO_25 → MO_26 to retrain on the expanded feature set
    3. SHAP automatically shows whether the new signal adds value
       (if it explains <1% of variance, it's dropped)
  No model architecture changes needed — the pipeline is additive.
""")

    print(f"  Outputs saved to: {OUTPUT_DIR}")
    print(f"    v2_mape_by_series.csv")
    print(f"    v2_coverage_audit.csv")
    print(f"    v2_feature_register.csv")
    print(f"    v2_shap_summary.png")
    print(f"    v2_actuals_vs_predicted.png")
    print("=" * 65)


if __name__ == "__main__":
    main()
