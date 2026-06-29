"""MO_32A — N-BEATS Global Neural Forecast  (13-week quarterly horizon)

Trains a single global N-BEATS model across all BUILT series per cutpoint.
All three cutpoints use h=13 (one quarter) for apples-to-apples comparison.
LightGBM is also re-evaluated on the same 13-week window at each cutpoint.

Why h=13 for N-BEATS (not the full OOS horizon from MO_29/30/31):
  • neuralforecast requires val_size >= h; h=68 with ~72 training weeks per
    series (Dec 2024 cutpoint) leaves no room for a validation split.
  • 13 weeks = one quarter: the natural planning horizon for FP&A (Connor's
    team refreshes forecasts quarterly as new SPINS data arrives).
  • h=13 with input_size=52 gives a 4:1 lookback:horizon ratio — ideal for
    neural forecasters.
  • LightGBM is re-evaluated on the same 13-week window so the comparison
    is true apples-to-apples (same cutpoints, same series, same horizon).

Key difference from MO_29/30/31:
  • N-BEATS is a neural architecture — no hand-crafted features required.
  • One global model learns cross-series patterns simultaneously.
  • Purely autoregressive (lookback window only, no exogenous covariates).

Run from scripts/:
    python MO_32A_nbeats_global.py

Outputs (in scripts/outputs/):
    v2_mo32a_metrics.json                — wMAPE all methods, all 3 cutpoints
    v2_mo32a_by_series_<tag>.csv         — per-series metrics per cutpoint
    v2_mo32a_walkforward_chart.png       — N-BEATS vs LightGBM vs Naive walk-forward
    v2_mo32a_horizon_chart.png           — accuracy vs training data size (13-week horizon)
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

warnings.filterwarnings("ignore")
logging.getLogger("pytorch_lightning").setLevel(logging.ERROR)
logging.getLogger("lightning").setLevel(logging.ERROR)
logging.getLogger("lightning_fabric").setLevel(logging.ERROR)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from neuralforecast import NeuralForecast
from neuralforecast.models import NBEATS
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "outputs")
PARQUET     = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")

GROUP_COLS  = ["upc", "channel_outlet", "retail_account", "geography_raw"]

H           = 13    # standardized quarterly horizon for N-BEATS and LightGBM
INPUT_SIZE  = 52    # 1-year lookback (4:1 ratio)
MAX_STEPS   = 500
EARLY_STOP  = 25
VAL_SIZE    = 13    # satisfies neuralforecast requirement: val_size >= h

MIN_TRAIN_WEEKS = 52    # ensures adequate lookback per series
MIN_TEST_WEEKS  = 13    # must have at least one full quarter of OOS data

CUTPOINTS = [
    {"label": "Dec 2024\n+13w", "short": "Dec 2024", "tag": "dec2024",
     "cutoff": pd.Timestamp("2025-01-01")},
    {"label": "Oct 2025\n+13w", "short": "Oct 2025", "tag": "oct2025",
     "cutoff": pd.Timestamp("2025-10-01")},
    {"label": "Dec 2025\n+13w", "short": "Dec 2025", "tag": "dec2025",
     "cutoff": pd.Timestamp("2026-01-01")},
]

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
def _ok(arr):
    return np.isfinite(np.asarray(arr, float)).any()

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

def naive_baselines(train_vals, n_test):
    v = np.asarray(train_vals, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return np.full(n_test, np.nan), np.full(n_test, np.nan), np.full(n_test, np.nan)
    ma4  = np.full(n_test, np.mean(v[-4:])  if len(v) >= 4  else np.mean(v))
    ma13 = np.full(n_test, np.mean(v[-13:]) if len(v) >= 13 else np.mean(v))
    naive = np.full(n_test, v[-1])
    return ma4, ma13, naive


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("MO_32A  —  N-BEATS Global Neural Forecast  (h=13 quarterly)")
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

    # MULO filter
    if "geography_raw" in df.columns:
        mulo = df["geography_raw"].str.contains(
            "MULTI OUTLET|MULO|TOTAL US|ALL CHANNEL", case=False, na=False)
        df = df[~mulo].copy()
    if "geography_level" in df.columns:
        df = df[~df["geography_level"].str.upper().isin(["NATIONAL", "TOTAL"])].copy()

    # tz-naive time + unique_id for neuralforecast
    df["__time_naive"] = df["__time"].dt.tz_convert(None)
    df["unique_id"] = (df["upc"].astype(str) + "|" + df["channel_outlet"].astype(str) +
                       "|" + df["retail_account"].astype(str) + "|" + df["geography_raw"].astype(str))

    print(f"  Rows after MULO filter: {len(df):,}  "
          f"| Date range: {df['__time'].min().date()} → {df['__time'].max().date()}")

    all_results = []

    # ── Loop cutpoints ────────────────────────────────────────────────────────
    for cp in CUTPOINTS:
        cutoff    = cp["cutoff"]
        cutoff_utc = cutoff.tz_localize("UTC")
        tag       = cp["tag"]
        short     = cp["short"]

        print(f"\n{'─'*65}")
        print(f"CUTPOINT: {short}  (h={H} OOS weeks)")
        print(f"{'─'*65}")

        # Qualify series
        train_counts = df[df["__time"] <  cutoff_utc].groupby(GROUP_COLS).size()
        test_counts  = df[df["__time"] >= cutoff_utc].groupby(GROUP_COLS).size()
        coverage = pd.concat([train_counts.rename("tr"),
                               test_counts.rename("te")], axis=1).fillna(0).astype(int)
        qualifying = coverage[(coverage["tr"] >= MIN_TRAIN_WEEKS) &
                              (coverage["te"] >= MIN_TEST_WEEKS)]
        qual_keys = set(qualifying.index.tolist())
        df["_key"] = list(zip(df["upc"], df["channel_outlet"],
                              df["retail_account"], df["geography_raw"]))
        df_cp = df[df["_key"].isin(qual_keys)].copy()

        train_all = df_cp[df_cp["__time"] <  cutoff_utc].copy()
        test_all  = df_cp[df_cp["__time"] >= cutoff_utc].copy()

        # Restrict test to first H=13 weeks (standardized quarterly horizon)
        test_dates = sorted(test_all["__time"].unique())[:H]
        test_df = test_all[test_all["__time"].isin(test_dates)].copy()

        n_series = len(qualifying)
        print(f"  Qualifying series (≥{MIN_TRAIN_WEEKS}tr / ≥{MIN_TEST_WEEKS}te): {n_series:,}")
        print(f"  Train: {len(train_all):,} rows  "
              f"({train_all['__time'].min().date()} → {train_all['__time'].max().date()})")
        print(f"  Test (first {H}w): {len(test_df):,} rows  "
              f"({test_df['__time'].min().date()} → {test_df['__time'].max().date()})")

        # ── LightGBM (13-week window) ─────────────────────────────────────────
        print(f"  [1/2] Training LightGBM …")
        lval_cut = cutoff_utc - pd.Timedelta(weeks=8)
        super_tr = train_all[train_all["__time"] <  lval_cut]
        local_val = train_all[train_all["__time"] >= lval_cut]
        avail = [c for c in FEATURE_COLS if c in df.columns]
        model_lgbm = lgb.LGBMRegressor(**LGBM_PARAMS)
        model_lgbm.fit(
            super_tr[avail], super_tr["log_base_units"].values,
            eval_set=[(local_val[avail], local_val["log_base_units"].values)],
            callbacks=[lgb.early_stopping(50, verbose=False),
                       lgb.log_evaluation(500)],
        )
        preds_log = model_lgbm.predict(test_df[avail])
        test_df = test_df.copy()
        test_df["pred_lgbm"] = np.expm1(np.clip(preds_log, 0, None))
        print(f"       best iter: {model_lgbm.best_iteration_}")

        # ── N-BEATS (global, h=13) ────────────────────────────────────────────
        print(f"  [2/2] Training N-BEATS (global, {n_series} series, "
              f"h={H}, input_size={INPUT_SIZE}, max_steps={MAX_STEPS}) …")

        train_nf = (train_all[["unique_id", "__time_naive", "log_base_units"]]
                    .rename(columns={"__time_naive": "ds", "log_base_units": "y"})
                    .sort_values(["unique_id", "ds"])
                    .copy())

        nbeats = NBEATS(
            h=H, input_size=INPUT_SIZE,
            max_steps=MAX_STEPS,
            early_stop_patience_steps=EARLY_STOP,
            val_check_steps=25,
            scaler_type="standard",
            random_seed=42,
            accelerator="cpu",
            enable_progress_bar=False,
            enable_model_summary=False,
        )
        nf = NeuralForecast(models=[nbeats], freq="W")
        nf.fit(train_nf, val_size=VAL_SIZE)
        preds_nf = nf.predict().rename(columns={"NBEATS": "pred_log"})
        preds_nf["pred_nbeats"] = np.expm1(np.clip(preds_nf["pred_log"].values, 0, None))
        preds_nf["ds"] = pd.to_datetime(preds_nf["ds"]).dt.normalize()

        # Align with test_df
        test_df["ds"] = pd.to_datetime(test_df["__time_naive"]).dt.normalize()
        merged = test_df.merge(
            preds_nf[["unique_id", "ds", "pred_nbeats"]],
            on=["unique_id", "ds"], how="left"
        )
        n_matched = merged["pred_nbeats"].notna().sum()
        print(f"       N-BEATS predictions matched: {n_matched:,}/{len(merged):,} rows")

        # ── Naive baselines ───────────────────────────────────────────────────
        ma4_list, ma13_list, naive_list = [], [], []
        for key, grp_test in merged.groupby(GROUP_COLS):
            uid = (grp_test["unique_id"].iloc[0])
            grp_train = train_all[train_all["unique_id"] == uid]["base_units"].values
            n = len(grp_test)
            ma4, ma13, nv = naive_baselines(grp_train, n)
            ma4_list.append(ma4); ma13_list.append(ma13); naive_list.append(nv)

        merged["ma4"]   = np.concatenate(ma4_list)
        merged["ma13"]  = np.concatenate(ma13_list)
        merged["naive"] = np.concatenate(naive_list)

        # ── Aggregate metrics ─────────────────────────────────────────────────
        act = merged["base_units"].values
        method_preds = {
            "LightGBM": merged["pred_lgbm"].values,
            "N-BEATS":  merged["pred_nbeats"].values,
            "MA 4wk":   merged["ma4"].values,
            "MA 13wk":  merged["ma13"].values,
            "Naive":    merged["naive"].values,
        }
        agg = {}
        for name, pred in method_preds.items():
            agg[name] = {
                "wmape": round(wmape(act, pred), 2),
                "mape":  round(mape_safe(act, pred), 2),
                "rmse":  round(rmse(act, pred), 1),
                "bias":  round(bias_pct(act, pred), 2),
            }

        # ── Per-series CSV ────────────────────────────────────────────────────
        records = []
        for key, grp in merged.groupby(GROUP_COLS):
            a = grp["base_units"].values
            rec = {
                "upc": key[0], "channel_outlet": key[1],
                "retail_account": key[2], "geography_raw": key[3],
                "description": grp["description"].iloc[0] if "description" in grp.columns else "",
                "test_weeks": len(grp), "total_actual": a.sum(),
                "wmape_LightGBM": wmape(a, grp["pred_lgbm"].values),
                "wmape_NBEATS":   wmape(a, grp["pred_nbeats"].values),
                "wmape_MA4":      wmape(a, grp["ma4"].values),
                "wmape_Naive":    wmape(a, grp["naive"].values),
            }
            records.append(rec)
        series_df = pd.DataFrame(records).sort_values("total_actual", ascending=False)
        series_df.to_csv(
            os.path.join(OUTPUT_DIR, f"v2_mo32a_by_series_{tag}.csv"), index=False)

        # ── Print results ─────────────────────────────────────────────────────
        naive_wm = agg["Naive"]["wmape"]
        print(f"\n  RESULTS  [{short} → first {H} OOS weeks]")
        print(f"  {'METHOD':<14}  {'wMAPE':>7}  {'MAPE':>7}  {'RMSE':>8}  {'BIAS':>7}  vs naive")
        print("  " + "─" * 62)
        for name in ["LightGBM", "N-BEATS", "MA 4wk", "MA 13wk", "Naive"]:
            s = agg[name]
            delta = naive_wm - s["wmape"]
            marker = f"+{delta:.1f}pp" if delta > 0 else f"{delta:.1f}pp"
            print(f"  {name:<14}  {s['wmape']:>6.1f}%  {s['mape']:>6.1f}%  "
                  f"{s['rmse']:>8.0f}  {s['bias']:>+6.1f}%  {marker if name != 'Naive' else ''}")

        print(f"\n  Top 10 by volume  (13-week actuals):")
        print(f"  {'UPC':<14}  {'Account':<20}  {'LGBM':>7}  {'N-BEATS':>8}  {'Naive':>7}")
        print("  " + "─" * 64)
        for _, row in series_df.head(10).iterrows():
            upc = str(row["upc"])[-11:]
            acct = str(row["retail_account"])[:18]
            print(f"  {upc:<14}  {acct:<20}  "
                  f"{row['wmape_LightGBM']:>6.1f}%  "
                  f"{row['wmape_NBEATS']:>7.1f}%  "
                  f"{row['wmape_Naive']:>6.1f}%")

        all_results.append({
            "label": cp["label"], "short": short, "tag": tag,
            "n_series": n_series, "agg": agg,
        })

    # ── Save JSON ─────────────────────────────────────────────────────────────
    meta = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "h": H, "input_size": INPUT_SIZE, "max_steps": MAX_STEPS,
        "note": f"All methods evaluated on first {H} OOS weeks per cutpoint",
        "cutpoints": [
            {"label": r["short"], "n_series": r["n_series"],
             **{k: r["agg"][k]["wmape"] for k in r["agg"]}}
            for r in all_results
        ],
    }
    with open(os.path.join(OUTPUT_DIR, "v2_mo32a_metrics.json"), "w") as f:
        json.dump(meta, f, indent=2)

    _make_walkforward_chart(all_results)
    _make_horizon_chart(all_results)

    print("\n" + "=" * 65)
    print("MO_32A complete.")
    print("=" * 65)


def _make_walkforward_chart(results):
    labels  = [r["label"] for r in results]
    methods = ["LightGBM", "N-BEATS", "Naive"]
    colors  = {"LightGBM": "#d62728", "N-BEATS": "#e377c2", "Naive": "#8c564b"}
    x       = np.arange(len(labels))
    width   = 0.22

    fig, ax = plt.subplots(figsize=(11, 6))
    offsets = [-width, 0, width]
    for method, offset in zip(methods, offsets):
        vals = [r["agg"][method]["wmape"] for r in results]
        bars = ax.bar(x + offset, vals, width, label=method,
                      color=colors[method], alpha=0.85)
        for bar, v in zip(bars, vals):
            if np.isfinite(v) and v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, v + 0.3,
                        f"{v:.0f}%", ha="center", fontsize=8, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"{r['label']}\n({r['n_series']} series)" for r in results], fontsize=9)
    ax.set_ylabel("wMAPE — lower is better", fontsize=11)
    ax.set_title(
        f"Walk-Forward: LightGBM vs N-BEATS vs Naive  (standardized {H}-week horizon)\n"
        "LightGBM uses 27 engineered features; N-BEATS is purely autoregressive",
        fontsize=11, pad=12)
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo32a_walkforward_chart.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Walk-forward chart → {out}")


def _make_horizon_chart(results):
    """Accuracy vs. training data size (all at h=13)."""
    n_series_vals = [r["n_series"] for r in results]
    labels = [r["short"] for r in results]
    methods = {
        "LightGBM": ("#d62728", "o-", 2.2),
        "N-BEATS":  ("#e377c2", "s-", 2.0),
        "Naive":    ("#8c564b", "^--", 1.5),
    }

    fig, ax = plt.subplots(figsize=(9, 5))
    for method, (color, style, lw) in methods.items():
        vals = [r["agg"][method]["wmape"] for r in results]
        ax.plot(n_series_vals, vals, style, color=color, lw=lw, ms=9,
                label=method, alpha=0.9 if method != "Naive" else 0.7)
        for n, v, lab in zip(n_series_vals, vals, labels):
            ax.annotate(f"{v:.1f}%", (n, v),
                        xytext=(6, 4 if method != "Naive" else -13),
                        textcoords="offset points",
                        fontsize=9, color=color, fontweight="bold" if method != "Naive" else "normal")

    ax.set_xlabel("Number of qualifying series (proxy for training data available)", fontsize=11)
    ax.set_ylabel("wMAPE (13-week horizon)", fontsize=11)
    ax.set_title(
        "Forecast Accuracy vs. Training Coverage  (h=13 weeks, all methods)\n"
        "More series = richer global model training for N-BEATS; "
        "more history = better features for LightGBM",
        fontsize=10, pad=12)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.spines[["top", "right"]].set_visible(False)

    for n, lab in zip(n_series_vals, labels):
        ax.annotate(lab, (n, ax.get_ylim()[0] - 1), ha="center", fontsize=8,
                    color="#555", annotation_clip=False)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "v2_mo32a_horizon_chart.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Training coverage chart → {out}")


if __name__ == "__main__":
    main()
