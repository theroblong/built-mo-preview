"""MO_65 — AutoGluon-TimeSeries benchmark vs. existing LightGBM horse race.

Two questions:
  1. Accuracy: Can AutoGluon's auto-ensemble match the LightGBM champion
     (4.3% wMAPE at Dec 2025) on the same 3 temporal cutpoints as MO_38?
  2. Explainability: Which models drive the ensemble, with what weights,
     and what features does the tabular component use internally?

Run A: raw base_units series only — zero-shot AutoGluon (no domain features).
This is the honest starting comparison.  If results are promising, MO_66 will
add our 28 Mo domain features as past / known covariates.

Cutpoints: Dec 2024 / Oct 2025 / Dec 2025  (identical to MO_38 horse race).

Usage:
  python scripts/MO_65_autogluon_benchmark.py            # medium_quality (~30 min/cutpoint)
  python scripts/MO_65_autogluon_benchmark.py --fast     # fast_training   (< 5 min/cutpoint)
  python scripts/MO_65_autogluon_benchmark.py --cutpoint dec2025  # single cutpoint

Outputs:
  outputs/mo65_autogluon_metrics.json
  outputs/mo65_leaderboard_{tag}.csv           (one per cutpoint)
  outputs/mo65_accuracy_comparison.png         (horse race bar chart)
  outputs/mo65_explainability.png              (leaderboard + feature importance)
"""

import argparse
import json
import os
import shutil
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor

# ── Constants ──────────────────────────────────────────────────────────────────

PARQUET        = "outputs/retailer_sales_weekly.parquet"
GROUP_COLS     = ["upc", "channel_outlet", "retail_account", "geography_raw"]
H              = 13     # quarterly forecast horizon (weeks)
MIN_TRAIN_ROWS = 52     # minimum history rows to include a series

CUTPOINTS = [
    {"tag": "dec2024", "label": "Dec 2024", "cutoff": pd.Timestamp("2025-01-01")},
    {"tag": "oct2025", "label": "Oct 2025", "cutoff": pd.Timestamp("2025-10-01")},
    {"tag": "dec2025", "label": "Dec 2025", "cutoff": pd.Timestamp("2026-01-01")},
]

# MO_38 reference wMAPE — same 3 cutpoints, identical series filter
# Dec 2024 / Oct 2025 / Dec 2025
HORSE_RACE = {
    "LightGBM\n(Aevah)": (28.7, 7.0,  4.3),
    "MA 13wk":            (50.4, 40.2, 24.6),
    "Naive":              (56.9, 37.5, 42.1),
    "N-BEATS":            (55.6, 117.9, 46.4),
}

# ── Metric helpers ─────────────────────────────────────────────────────────────

def wmape(actual: np.ndarray, predicted: np.ndarray) -> float:
    denom = np.nansum(np.abs(actual))
    if denom == 0:
        return np.nan
    return float(np.nansum(np.abs(actual - predicted)) / denom * 100)


# ── Data helpers ───────────────────────────────────────────────────────────────

def make_item_id(df: pd.DataFrame) -> pd.Series:
    return (
        df["upc"].astype(str) + "|" +
        df["channel_outlet"].astype(str) + "|" +
        df["retail_account"].astype(str) + "|" +
        df["geography_raw"].astype(str)
    )


def build_ts_df(df: pd.DataFrame) -> TimeSeriesDataFrame:
    """Build a TimeSeriesDataFrame from a pre-filtered, tz-naive dataframe."""
    d = (
        df[["item_id", "ds", "base_units"]]
        .copy()
        .dropna(subset=["base_units"])
    )
    d["base_units"] = pd.to_numeric(d["base_units"], errors="coerce").clip(lower=0)
    # Rename to AutoGluon's expected column names before construction
    d = d.rename(columns={"item_id": "item_id", "ds": "timestamp"})
    return TimeSeriesDataFrame.from_data_frame(
        d,
        id_column="item_id",
        timestamp_column="timestamp",
    )


def filter_min_rows(ts: TimeSeriesDataFrame, min_rows: int) -> TimeSeriesDataFrame:
    lengths = ts.num_timesteps_per_item()
    valid   = lengths[lengths >= min_rows].index
    return ts.loc[valid]


# ── Main evaluation loop ───────────────────────────────────────────────────────

def run_cutpoint(df: pd.DataFrame, cp: dict, preset: str) -> dict:
    tag    = cp["tag"]
    cutoff = cp["cutoff"]

    print(f"\n{'='*60}")
    print(f"Cutpoint: {cp['label']}  (cutoff={cutoff.date()}, preset={preset})")
    print(f"{'='*60}")

    df_train = df[df["ds"] <= cutoff].copy()
    test_end = cutoff + pd.Timedelta(weeks=H)
    df_test  = df[(df["ds"] > cutoff) & (df["ds"] <= test_end)].copy()

    if len(df_test) == 0:
        print(f"  No test data after {cutoff.date()} — skipping")
        return {}

    train_ts = build_ts_df(df_train)
    train_ts = filter_min_rows(train_ts, MIN_TRAIN_ROWS)

    n_series = len(train_ts.item_ids)
    print(f"  Train series : {n_series:,}  (≥{MIN_TRAIN_ROWS} wk history)")
    print(f"  Train rows   : {len(train_ts):,}")
    print(f"  Test rows    : {len(df_test):,}")

    model_path = f"outputs/ag_models_{tag}"
    if os.path.exists(model_path):
        shutil.rmtree(model_path)

    predictor = TimeSeriesPredictor(
        prediction_length=H,
        path=model_path,
        target="base_units",
        quantile_levels=[0.1, 0.5, 0.9],
        eval_metric="MASE",
        freq="W-SUN",
        verbosity=1,
    )

    print(f"\nFitting AutoGluon ({preset}) …")
    predictor.fit(train_ts, presets=preset, time_limit=1800)

    print("Predicting …")
    preds = predictor.predict(train_ts)

    # Flatten predictions → join to actuals
    preds_df = preds.reset_index()
    # preds index levels are (item_id, timestamp); rename + clean quantile columns
    new_cols = []
    for i, c in enumerate(preds_df.columns):
        if i == 0:
            new_cols.append("item_id")
        elif i == 1:
            new_cols.append("timestamp")
        elif isinstance(c, float):
            new_cols.append(f"q{int(c * 100)}")
        else:
            new_cols.append(str(c))
    preds_df.columns = new_cols

    # actuals keyed on same item_id + timestamp (tz-naive)
    actuals_df = df_test[["item_id", "ds", "base_units"]].rename(columns={"ds": "timestamp"}).copy()
    merged = pd.merge(preds_df, actuals_df, on=["item_id", "timestamp"], how="inner")
    n_matched = len(merged)
    print(f"  Matched {n_matched:,} forecast × actual pairs")

    pred_col = "q50" if "q50" in merged.columns else "mean" if "mean" in merged.columns else None
    wm = wmape(merged["base_units"].values, merged[pred_col].values) if pred_col else np.nan
    print(f"  wMAPE (q50)  : {wm:.2f}%")

    # Save leaderboard
    lb = None
    try:
        lb = predictor.leaderboard()
        lb["cutpoint"] = tag
        lb.to_csv(f"outputs/mo65_leaderboard_{tag}.csv", index=False)
        print(f"\nLeaderboard ({cp['label']}):")
        display_cols = [c for c in ["model", "score_val", "pred_time_val_marginal", "fit_time_marginal"] if c in lb.columns]
        print(lb[display_cols].head(15).to_string(index=False))
    except Exception as e:
        print(f"  Leaderboard failed: {e}")

    # Feature importance (tabular component — best effort)
    fi_df = None
    try:
        fi_df = predictor.feature_importance(data=train_ts)
        if fi_df is not None and len(fi_df) > 0:
            print(f"\nFeature importance (tabular component, top 15):")
            print(fi_df.head(15).to_string())
    except Exception as e:
        print(f"  Feature importance unavailable: {e}")

    return {
        "label":     cp["label"],
        "preset":    preset,
        "n_series":  n_series,
        "n_matched": n_matched,
        "wmape":     round(wm, 2) if not np.isnan(wm) else None,
        "leaderboard": lb.to_dict("records") if lb is not None else None,
        "fi_df":     fi_df,
    }


# ── Charts ─────────────────────────────────────────────────────────────────────

def chart_accuracy(results: dict):
    tags   = ["dec2024", "oct2025", "dec2025"]
    labels = ["Dec 2024", "Oct 2025", "Dec 2025"]

    fig, axes = plt.subplots(1, 3, figsize=(17, 6))
    fig.patch.set_facecolor("#f8f9fa")
    fig.suptitle(
        "AutoGluon-TimeSeries vs. MO_38 Horse Race  |  wMAPE — lower is better\n"
        "(AutoGluon Run A: raw time series only, no domain features)",
        fontsize=12, y=1.01,
    )

    for ax, tag, label, (hr_dec, hr_oct, hr_dec25) in zip(
        axes, tags, labels,
        [(r[0], r[1], r[2]) for r in zip(*[HORSE_RACE[k] for k in HORSE_RACE])]
    ):
        # Build per-cutpoint reference
        ref_vals = {k: HORSE_RACE[k][["dec2024","oct2025","dec2025"].index(tag)]
                    for k in HORSE_RACE}

        ag_wm = results.get(tag, {}).get("wmape")
        model_names = list(ref_vals.keys()) + (["AutoGluon\n(medium)"] if ag_wm is not None else [])
        values      = list(ref_vals.values()) + ([ag_wm] if ag_wm is not None else [])
        colors      = [
            "#1f4e79" if "Aevah" in m else
            "#e84444" if "AutoGluon" in m else
            "#aaaaaa"
            for m in model_names
        ]

        bars = ax.bar(model_names, values, color=colors, width=0.6,
                      edgecolor="white", linewidth=0.5)
        for bar, v in zip(bars, values):
            if v is not None and not np.isnan(v):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        v + max(values) * 0.015,
                        f"{v:.1f}%",
                        ha="center", va="bottom", fontsize=8, fontweight="bold")

        ax.set_title(label, fontsize=11, pad=8)
        ax.set_ylabel("wMAPE (%)" if tag == "dec2024" else "")
        ax.set_ylim(0, max(v for v in values if v is not None) * 1.25 + 3)
        ax.tick_params(axis="x", labelsize=8)
        ax.set_facecolor("#f8f9fa")
        ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    path = "outputs/mo65_accuracy_comparison.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#f8f9fa")
    plt.close()
    print(f"\nSaved {path}")


def chart_explainability(results: dict):
    dec_res = results.get("dec2025", {})
    lb_records = dec_res.get("leaderboard")
    fi_df      = dec_res.get("fi_df")

    if lb_records is None:
        print("  No leaderboard data — skipping explainability chart")
        return

    lb = pd.DataFrame(lb_records)
    has_fi = fi_df is not None and len(fi_df) > 0
    n_panels = 2 if has_fi else 1

    fig, axes = plt.subplots(1, n_panels, figsize=(8 * n_panels, 7))
    fig.patch.set_facecolor("#f8f9fa")
    if n_panels == 1:
        axes = [axes]

    fig.suptitle(
        "AutoGluon-TimeSeries: Explainability  |  Dec 2025 cutpoint",
        fontsize=12, y=1.01,
    )

    # Panel 1: Leaderboard — model scores
    ax = axes[0]
    score_col = "score_val" if "score_val" in lb.columns else lb.columns[1]
    lb_sorted = lb.dropna(subset=[score_col]).sort_values(score_col).head(12)
    scores    = lb_sorted[score_col].abs().values
    model_names = lb_sorted["model"].tolist()

    colors = ["#2ecc71" if i == 0 else "#1f77b4" if i < 4 else "#aaaaaa"
              for i in range(len(model_names))]
    bars = ax.barh(range(len(model_names)), scores, color=colors, edgecolor="white")
    ax.set_yticks(range(len(model_names)))
    ax.set_yticklabels(model_names, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel(f"|{score_col}| (MASE — lower is better)")
    ax.set_title("Model Leaderboard\n(validation scores; top = ensemble winner)", fontsize=10)
    ax.set_facecolor("#f8f9fa")
    ax.spines[["top", "right"]].set_visible(False)

    for bar, v in zip(bars, scores):
        ax.text(v + max(scores) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{v:.3f}", va="center", fontsize=8)

    # Panel 2: Feature importance from tabular model
    if has_fi:
        ax2 = axes[1]
        imp_col = fi_df.columns[0]
        top_fi  = fi_df[[imp_col]].head(15).sort_values(imp_col)
        ax2.barh(range(len(top_fi)), top_fi[imp_col].values,
                 color="#1f77b4", edgecolor="white")
        ax2.set_yticks(range(len(top_fi)))
        ax2.set_yticklabels(top_fi.index.tolist(), fontsize=9, fontfamily="monospace")
        ax2.set_xlabel("Importance")
        ax2.set_title(
            "Tabular Model: AutoGluon-Generated Features\n"
            "(auto-lags + seasonal dummies — no Mo domain features in Run A)",
            fontsize=9,
        )
        ax2.set_facecolor("#f8f9fa")
        ax2.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    path = "outputs/mo65_explainability.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#f8f9fa")
    plt.close()
    print(f"Saved {path}")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MO_65 — AutoGluon-TimeSeries benchmark")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use fast_training preset (statistical models only, < 5 min per cutpoint)",
    )
    parser.add_argument(
        "--cutpoint",
        choices=["dec2024", "oct2025", "dec2025"],
        default=None,
        help="Run a single cutpoint only (default: all three)",
    )
    args = parser.parse_args()
    preset = "fast_training" if args.fast else "medium_quality"

    print(f"Loading {PARQUET} …")
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    # tz-naive timestamps (AutoGluon requires tz-naive or consistent tz)
    df["ds"]      = df["__time"].dt.tz_localize(None)
    df["item_id"] = make_item_id(df)

    print(f"  Rows: {len(df):,} | Series: {df['item_id'].nunique():,} | "
          f"Date range: {df['ds'].min().date()} → {df['ds'].max().date()}")

    cutpoints_to_run = (
        [cp for cp in CUTPOINTS if cp["tag"] == args.cutpoint]
        if args.cutpoint
        else CUTPOINTS
    )

    results = {}
    for cp in cutpoints_to_run:
        res = run_cutpoint(df, cp, preset)
        if res:
            results[cp["tag"]] = res

    # ── Summary table ──────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("SUMMARY — wMAPE comparison")
    print("="*60)
    header = f"{'Model':<22}  {'Dec 2024':>10}  {'Oct 2025':>10}  {'Dec 2025':>10}"
    print(header)
    print("-" * len(header))
    for model, vals in HORSE_RACE.items():
        print(f"  {model.replace(chr(10), ' '):<20}  {vals[0]:>9.1f}%  {vals[1]:>9.1f}%  {vals[2]:>9.1f}%")
    ag_row = "  AutoGluon (med)     "
    for tag in ["dec2024", "oct2025", "dec2025"]:
        wm = results.get(tag, {}).get("wmape")
        ag_row += f"  {wm:>9.1f}%" if wm is not None else f"  {'—':>9}"
    print(ag_row)

    # ── Save metrics JSON ──────────────────────────────────────────────────────
    meta = {
        "script": "MO_65",
        "preset": preset,
        "prediction_length": H,
        "min_train_rows": MIN_TRAIN_ROWS,
        "horse_race_reference_wmape": {k: list(v) for k, v in HORSE_RACE.items()},
        "autogluon_results": {
            tag: {k: v for k, v in res.items() if k not in ("leaderboard", "fi_df")}
            for tag, res in results.items()
        },
        "leaderboard_dec2025": results.get("dec2025", {}).get("leaderboard"),
    }
    with open("outputs/mo65_autogluon_metrics.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)
    print("\nSaved outputs/mo65_autogluon_metrics.json")

    # ── Charts ─────────────────────────────────────────────────────────────────
    if results:
        chart_accuracy(results)
        chart_explainability(results)

    print("\nMO_65 complete.")
