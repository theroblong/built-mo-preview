"""MO_32B — Quarterly Rolling-Origin Retraining Simulation

Simulates production use: retrain every quarter as new SPINS data arrives,
predict the next 13 weeks, advance. Covers all of 2025 + Q1 2026 (5 windows).

This directly answers the FP&A question: "If Connor retrains every quarter,
what accuracy can he expect?" and "Is the model getting better over time?"

Also runs a stale-model comparison: one model trained Dec 2024, never
retrained, predicting all 5 quarters. Quantifies the value of retraining.

QUARTERLY WINDOWS
-----------------
  Q4 2024 → predict Q1 2025  (Jan 5  – Mar 30, 2025)
  Q1 2025 → predict Q2 2025  (Apr 6  – Jun 29, 2025)
  Q2 2025 → predict Q3 2025  (Jul 6  – Sep 28, 2025)
  Q3 2025 → predict Q4 2025  (Oct 5  – Dec 28, 2025)
  Q4 2025 → predict Q1 2026  (Jan 4  – Mar 29, 2026)

Run from scripts/:
    python MO_32B_quarterly_rollforward.py

Outputs (in scripts/outputs/):
    v2_mo32b_metrics.json              — per-window + overall wMAPE
    v2_mo32b_by_window.csv             — aggregate metrics per quarter
    v2_mo32b_rolling_accuracy.png      — wMAPE per quarter: rolling vs stale vs baseline
    v2_mo32b_stitched_forecast.png     — actuals vs rolling prediction (full 2025 timeline)
    v2_mo32b_retrain_value.png         — rolling retrain vs stale model accuracy gap
"""

import os
import json
import warnings
import logging

import numpy as np
import pandas as pd
import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from datetime import datetime, timezone

warnings.filterwarnings("ignore")
logging.getLogger("lightgbm").setLevel(logging.ERROR)

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "outputs")
PARQUET     = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")

GROUP_COLS  = ["upc", "channel_outlet", "retail_account", "geography_raw"]
H           = 13          # one quarter ahead
MIN_TRAIN_WEEKS = 52
LOCAL_VAL_WEEKS = 8

# Five quarterly retrain cutpoints covering all of 2025 + Q1 2026
WINDOWS = [
    {"label": "Q4 2024", "cutoff": pd.Timestamp("2024-12-29", tz="UTC"),
     "predict_label": "Q1 2025"},
    {"label": "Q1 2025", "cutoff": pd.Timestamp("2025-03-30", tz="UTC"),
     "predict_label": "Q2 2025"},
    {"label": "Q2 2025", "cutoff": pd.Timestamp("2025-06-29", tz="UTC"),
     "predict_label": "Q3 2025"},
    {"label": "Q3 2025", "cutoff": pd.Timestamp("2025-09-28", tz="UTC"),
     "predict_label": "Q4 2025"},
    {"label": "Q4 2025", "cutoff": pd.Timestamp("2025-12-28", tz="UTC"),
     "predict_label": "Q1 2026"},
]

STALE_CUTOFF = pd.Timestamp("2024-12-29", tz="UTC")  # train once, never retrain

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


# ── Metric helpers ─────────────────────────────────────────────────────────────
def wmape(actual, pred):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    mask = np.isfinite(a) & np.isfinite(p)
    if not mask.any(): return np.nan
    d = np.sum(a[mask])
    return float(np.sum(np.abs(a[mask] - p[mask])) / d * 100) if d > 0 else np.nan

def mape_safe(actual, pred, clip=500):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    mask = np.isfinite(a) & np.isfinite(p) & (a > 0)
    if not mask.any(): return np.nan
    return float(np.mean(np.clip(np.abs(a[mask] - p[mask]) / a[mask] * 100, 0, clip)))

def rmse(actual, pred):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    mask = np.isfinite(a) & np.isfinite(p)
    if not mask.any(): return np.nan
    return float(np.sqrt(np.mean((a[mask] - p[mask]) ** 2)))

def bias_pct(actual, pred):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    mask = np.isfinite(a) & np.isfinite(p)
    if not mask.any(): return np.nan
    d = np.sum(a[mask])
    return float((np.sum(p[mask]) - d) / (d + 1) * 100)

def naive_baselines(train_vals, n):
    v = np.asarray(train_vals, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return np.full(n, np.nan), np.full(n, np.nan)
    ma13  = np.full(n, np.mean(v[-13:]) if len(v) >= 13 else np.mean(v))
    naive = np.full(n, v[-1])
    return ma13, naive


# ── Train LightGBM ─────────────────────────────────────────────────────────────
def train_lgbm(train_df, avail):
    lval_cut = train_df["__time"].max() - pd.Timedelta(weeks=LOCAL_VAL_WEEKS)
    super_tr  = train_df[train_df["__time"] <  lval_cut]
    local_val = train_df[train_df["__time"] >= lval_cut]
    model = lgb.LGBMRegressor(**LGBM_PARAMS)
    model.fit(
        super_tr[avail], super_tr["log_base_units"].values,
        eval_set=[(local_val[avail], local_val["log_base_units"].values)],
        callbacks=[lgb.early_stopping(50, verbose=False),
                   lgb.log_evaluation(500)],
    )
    return model


# ── Qualify and split ──────────────────────────────────────────────────────────
def qualify(df, cutoff, min_train=MIN_TRAIN_WEEKS, min_test=H):
    train_counts = df[df["__time"] <  cutoff].groupby(GROUP_COLS).size()
    test_counts  = df[df["__time"] >= cutoff].groupby(GROUP_COLS).size()
    cov = pd.concat([train_counts.rename("tr"),
                     test_counts.rename("te")], axis=1).fillna(0).astype(int)
    qual = cov[(cov["tr"] >= min_train) & (cov["te"] >= min_test)]
    qual_keys = set(qual.index.tolist())
    df2 = df.copy()
    df2["_key"] = list(zip(df2["upc"], df2["channel_outlet"],
                           df2["retail_account"], df2["geography_raw"]))
    return df2[df2["_key"].isin(qual_keys)].drop(columns=["_key"]), len(qual)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("MO_32B  —  Quarterly Rolling-Origin Retraining Simulation")
    print("=" * 65)

    # ── Load ──────────────────────────────────────────────────────────────────
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

    if "geography_raw" in df.columns:
        mulo = df["geography_raw"].str.contains(
            "MULTI OUTLET|MULO|TOTAL US|ALL CHANNEL", case=False, na=False)
        df = df[~mulo].copy()
    if "geography_level" in df.columns:
        df = df[~df["geography_level"].str.upper().isin(["NATIONAL","TOTAL"])].copy()

    avail = [c for c in FEATURE_COLS if c in df.columns]
    print(f"  Rows: {len(df):,} | Features: {len(avail)}")

    # ── Train stale model once on Q4 2024 data ────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"STALE MODEL  (train once on Q4 2024, never retrain)")
    print(f"{'─'*65}")
    df_stale, n_stale = qualify(df, STALE_CUTOFF)
    train_stale = df_stale[df_stale["__time"] < STALE_CUTOFF]
    model_stale = train_lgbm(train_stale, avail)
    print(f"  Stale model trained: {n_stale} series, "
          f"best iter {model_stale.best_iteration_}")

    # ── Rolling windows ────────────────────────────────────────────────────────
    window_results = []
    all_preds = []   # for stitched chart

    for w in WINDOWS:
        cutoff = w["cutoff"]
        label  = w["label"]
        plabel = w["predict_label"]

        print(f"\n{'─'*65}")
        print(f"WINDOW: trained through {label}  → predicting {plabel}")
        print(f"{'─'*65}")

        df_w, n_series = qualify(df, cutoff)
        train_df = df_w[df_w["__time"] <  cutoff].copy()
        test_all = df_w[df_w["__time"] >= cutoff].copy()

        # First H=13 OOS weeks only
        test_dates = sorted(test_all["__time"].unique())[:H]
        test_df = test_all[test_all["__time"].isin(test_dates)].copy()

        print(f"  Series: {n_series}  |  "
              f"Train: {train_df['__time'].min().date()} → {train_df['__time'].max().date()}  |  "
              f"Test: {test_df['__time'].min().date()} → {test_df['__time'].max().date()}")

        # Rolling LightGBM (retrained this quarter)
        model_roll = train_lgbm(train_df, avail)
        print(f"  Rolling model best iter: {model_roll.best_iteration_}")
        test_df = test_df.copy()
        test_df["pred_rolling"] = np.expm1(
            np.clip(model_roll.predict(test_df[avail]), 0, None))

        # Stale model (never retrained) — uses same test features
        test_df["pred_stale"] = np.expm1(
            np.clip(model_stale.predict(test_df[avail]), 0, None))

        # Naive baselines per series
        ma13_list, naive_list = [], []
        for key, grp_test in test_df.groupby(GROUP_COLS):
            grp_tr = train_df[
                (train_df["upc"] == key[0]) &
                (train_df["channel_outlet"] == key[1]) &
                (train_df["retail_account"] == key[2]) &
                (train_df["geography_raw"] == key[3])
            ]["base_units"].values
            ma13, nv = naive_baselines(grp_tr, len(grp_test))
            ma13_list.append(ma13)
            naive_list.append(nv)
        test_df["ma13"]  = np.concatenate(ma13_list)
        test_df["naive"] = np.concatenate(naive_list)

        # Aggregate metrics
        act = test_df["base_units"].values
        metrics = {}
        for name, col in [("Rolling LightGBM", "pred_rolling"),
                           ("Stale LightGBM",   "pred_stale"),
                           ("MA 13wk",          "ma13"),
                           ("Naive",            "naive")]:
            p = test_df[col].values
            metrics[name] = {
                "wmape": round(wmape(act, p), 2),
                "mape":  round(mape_safe(act, p), 2),
                "rmse":  round(rmse(act, p), 1),
                "bias":  round(bias_pct(act, p), 2),
            }

        print(f"\n  {'METHOD':<22}  {'wMAPE':>7}  {'MAPE':>7}  {'RMSE':>8}  {'BIAS':>7}")
        print("  " + "─" * 56)
        for name, m in metrics.items():
            print(f"  {name:<22}  {m['wmape']:>6.1f}%  {m['mape']:>6.1f}%  "
                  f"{m['rmse']:>8.0f}  {m['bias']:>+6.1f}%")

        retrain_gain = metrics["Stale LightGBM"]["wmape"] - metrics["Rolling LightGBM"]["wmape"]
        print(f"\n  Retraining gain vs stale: {retrain_gain:+.1f}pp "
              f"({'better' if retrain_gain > 0 else 'worse'})")

        window_results.append({
            "label": label, "predict_label": plabel,
            "cutoff": str(cutoff.date()),
            "test_start": str(test_df["__time"].min().date()),
            "test_end":   str(test_df["__time"].max().date()),
            "n_series": n_series,
            "metrics": metrics,
        })

        # Collect weekly aggregates for stitched chart
        weekly = (test_df.groupby("__time")
                  .agg(actual=("base_units","sum"),
                       pred_rolling=("pred_rolling","sum"),
                       pred_stale=("pred_stale","sum"),
                       ma13=("ma13","sum"))
                  .reset_index())
        weekly["window"] = label
        all_preds.append(weekly)

    # ── Overall metrics ───────────────────────────────────────────────────────
    all_preds_df = pd.concat(all_preds, ignore_index=True).sort_values("__time")

    overall = {}
    for name, col in [("Rolling LightGBM", "pred_rolling"),
                      ("Stale LightGBM",   "pred_stale"),
                      ("MA 13wk",          "ma13")]:
        overall[name] = round(wmape(all_preds_df["actual"].values,
                                    all_preds_df[col].values), 2)

    print(f"\n{'='*65}")
    print("OVERALL  (all 5 windows combined)")
    print(f"{'='*65}")
    for name, wm in overall.items():
        print(f"  {name:<22}  {wm:.1f}% wMAPE")
    roll_vs_stale = overall["Stale LightGBM"] - overall["Rolling LightGBM"]
    print(f"\n  Quarterly retraining improves accuracy by {roll_vs_stale:+.1f}pp overall")

    # ── Save JSON ─────────────────────────────────────────────────────────────
    meta = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "h": H, "n_windows": len(WINDOWS),
        "overall_wmape": overall,
        "retrain_gain_pp": round(roll_vs_stale, 2),
        "windows": window_results,
    }
    with open(os.path.join(OUTPUT_DIR, "v2_mo32b_metrics.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # Per-window summary CSV
    rows = []
    for w in window_results:
        row = {"window": w["label"], "predicts": w["predict_label"],
               "n_series": w["n_series"]}
        for name, m in w["metrics"].items():
            row[f"wmape_{name.replace(' ','_')}"] = m["wmape"]
        rows.append(row)
    pd.DataFrame(rows).to_csv(
        os.path.join(OUTPUT_DIR, "v2_mo32b_by_window.csv"), index=False)

    # ── Charts ────────────────────────────────────────────────────────────────
    _chart_rolling_accuracy(window_results)
    _chart_stitched(all_preds_df)
    _chart_retrain_value(window_results, overall)

    print(f"\n{'='*65}")
    print("MO_32B complete.")
    print(f"{'='*65}")


def _chart_rolling_accuracy(window_results):
    """wMAPE per quarter for rolling model, stale model, MA 13wk, Naive."""
    labels  = [f"{w['label']}\n→{w['predict_label']}" for w in window_results]
    methods = {
        "Rolling LightGBM": ("#d62728", "o-", 2.2),
        "Stale LightGBM":   ("#ff7f0e", "s--", 1.8),
        "MA 13wk":          ("#8c564b", "^:", 1.4),
        "Naive":            ("#aaaaaa", "v:", 1.2),
    }
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(12, 6))
    for name, (color, style, lw) in methods.items():
        vals = [w["metrics"][name]["wmape"] for w in window_results]
        ax.plot(x, vals, style, color=color, lw=lw, ms=8, label=name)
        for xi, v in enumerate(vals):
            ax.annotate(f"{v:.0f}%", (xi, v), xytext=(0, 8),
                        textcoords="offset points", ha="center",
                        fontsize=8, color=color,
                        fontweight="bold" if "Rolling" in name else "normal")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("wMAPE — lower is better", fontsize=11)
    ax.set_title(
        "Quarterly Rolling Retrain: Accuracy Per Quarter\n"
        "Rolling = retrained each quarter  |  Stale = trained Dec 2024 only, never retrained",
        fontsize=11, pad=12)
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo32b_rolling_accuracy.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Rolling accuracy chart  → {out}")


def _chart_stitched(df):
    """Aggregated weekly actual vs. rolling prediction across full 2025 timeline."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["__time"]).dt.tz_convert(None)

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df["date"], df["actual"],       color="#111111", lw=2.5,
            label="Actual (SPINS)", zorder=5)
    ax.plot(df["date"], df["pred_rolling"], color="#d62728", lw=2.0,
            linestyle="--", label="Rolling LightGBM (retrained quarterly)", zorder=4)
    ax.plot(df["date"], df["pred_stale"],   color="#ff7f0e", lw=1.6,
            linestyle=":", label="Stale LightGBM (Dec 2024 only)", zorder=3)
    ax.plot(df["date"], df["ma13"],         color="#8c564b", lw=1.4,
            linestyle=":", alpha=0.7, label="MA 13wk baseline", zorder=2)

    # Shade each quarter window
    colors_q = ["#fff3f3","#f3fff3","#f3f3ff","#fffff3","#f3ffff"]
    for i, (w, c) in enumerate(zip(
            [pd.Timestamp("2025-01-05"), pd.Timestamp("2025-04-06"),
             pd.Timestamp("2025-07-06"), pd.Timestamp("2025-10-05"),
             pd.Timestamp("2026-01-04")],
            colors_q)):
        end = (pd.Timestamp("2025-04-06") if i == 0 else
               pd.Timestamp("2025-07-06") if i == 1 else
               pd.Timestamp("2025-10-05") if i == 2 else
               pd.Timestamp("2026-01-04") if i == 3 else
               pd.Timestamp("2026-04-01"))
        ax.axvspan(w, end, alpha=0.25, color=c, zorder=0)
        ax.text(w + (end - w) / 2, ax.get_ylim()[1] if i == 0 else 0,
                ["Q1'25","Q2'25","Q3'25","Q4'25","Q1'26"][i],
                ha="center", fontsize=8, color="#666", va="bottom")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{int(v/1000)}K" if v >= 1000 else str(int(v))))
    ax.set_ylabel("Total Weekly Units (all series)", fontsize=11)
    ax.set_title(
        "Actual vs. Forecast — Full 2025 Rolling Retrain\n"
        "Each shaded band = one quarterly retrain window; model retrained at band boundary",
        fontsize=11, pad=12)
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo32b_stitched_forecast.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Stitched forecast chart → {out}")


def _chart_retrain_value(window_results, overall):
    """Bar chart: retraining gain (stale wMAPE - rolling wMAPE) per quarter."""
    labels = [w["predict_label"] for w in window_results]
    gains  = [w["metrics"]["Stale LightGBM"]["wmape"] -
              w["metrics"]["Rolling LightGBM"]["wmape"]
              for w in window_results]
    colors = ["#2ca02c" if g > 0 else "#d62728" for g in gains]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, gains, color=colors, width=0.5, edgecolor="white")
    for bar, g in zip(bars, gains):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + (0.3 if g >= 0 else -1.5),
                f"{g:+.1f}pp", ha="center", fontsize=10, fontweight="bold",
                color="#2ca02c" if g > 0 else "#d62728")

    ax.axhline(0, color="#333", lw=1)
    overall_gain = overall["Stale LightGBM"] - overall["Rolling LightGBM"]
    ax.axhline(overall_gain, color="#2ca02c" if overall_gain > 0 else "#d62728",
               lw=1.5, linestyle="--",
               label=f"Overall avg: {overall_gain:+.1f}pp")
    ax.set_ylabel("Accuracy improvement from retraining (pp wMAPE)\nPositive = retraining helps",
                  fontsize=10)
    ax.set_title(
        "Value of Quarterly Retraining vs. Stale Dec 2024 Model\n"
        "Green = retraining improved accuracy  |  Red = stale model was better",
        fontsize=11, pad=12)
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo32b_retrain_value.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Retrain value chart     → {out}")


if __name__ == "__main__":
    main()
