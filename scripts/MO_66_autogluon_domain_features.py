"""MO_66 — AutoGluon-TimeSeries Run B: 28 Mo domain features as covariates.

Builds on MO_65 (Run A: raw base_units only). Adds 25 past covariates
(rolling stats, z-scores, lags, TDP, ARP, donor_count) and 2 known-future
covariates (week_of_year, weeks_since_launch) to test whether Mo's domain
signals improve AutoGluon beyond its pure time-series baseline.

Key question: do TDP, price, and donor-count signals give AutoGluon a
meaningful lift vs. MO_65's zero-shot baseline? If Run B wMAPE approaches
LightGBM's, it confirms the features — not the architecture — drive Mo's edge.

Same cutpoints / evaluation protocol as MO_38 and MO_65.

Usage:
  python scripts/MO_66_autogluon_domain_features.py           # medium_quality
  python scripts/MO_66_autogluon_domain_features.py --fast
  python scripts/MO_66_autogluon_domain_features.py --cutpoint dec2025

Outputs:
  outputs/mo66_autogluon_metrics.json
  outputs/mo66_leaderboard_{tag}.csv
  outputs/mo66_accuracy_comparison.png
  outputs/mo66_explainability.png
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
H              = 13
MIN_TRAIN_ROWS = 52

CUTPOINTS = [
    {"tag": "dec2024", "label": "Dec 2024", "cutoff": pd.Timestamp("2025-01-01")},
    {"tag": "oct2025", "label": "Oct 2025", "cutoff": pd.Timestamp("2025-10-01")},
    {"tag": "dec2025", "label": "Dec 2025", "cutoff": pd.Timestamp("2026-01-01")},
]

# MO_38 LightGBM + baselines reference wMAPE
HORSE_RACE_REF = {
    "LightGBM\n(Aevah)": (28.7, 7.0,  4.3),
    "MA 13wk":            (50.4, 40.2, 24.6),
    "Naive":              (56.9, 37.5, 42.1),
    "N-BEATS":            (55.6, 117.9, 46.4),
}

# Past covariates — numeric, known only up to forecast origin
# tdp_wow_delta is not in the parquet; computed on load.
PAST_COVARIATES = [
    "base_units_roll4_avg",
    "base_units_roll8_avg",   "base_units_roll8_std",
    "base_units_roll13_avg",  "base_units_roll13_std",
    "base_units_wow_delta",   "base_units_z8",    "base_units_z13",
    "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
    "velocity_spm_z8",        "velocity_spm_z13",
    "tdp",      "tdp_z8",    "tdp_wow_delta",
    "arp",      "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std",
    "donor_count",
    "base_units_lag1",  "base_units_lag4",  "base_units_lag13",
    "base_units_lag52", "velocity_spm_lag52",
]

# Known covariates — values we can compute for the full forecast horizon
KNOWN_COVARIATES = ["week_of_year", "weeks_since_launch"]


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


def load_and_prepare(parquet_path: str) -> pd.DataFrame:
    """Load parquet, compute tdp_wow_delta, strip timezone for AutoGluon."""
    df = pd.read_parquet(parquet_path)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    df["ds"]      = df["__time"].dt.tz_localize(None)
    df["item_id"] = make_item_id(df)

    # tdp_wow_delta is absent from the parquet — compute it now
    if "tdp_wow_delta" not in df.columns:
        df["tdp_wow_delta"] = df.groupby("item_id")["tdp"].diff().fillna(0)

    return df


def build_ts_df(df: pd.DataFrame) -> TimeSeriesDataFrame:
    """Build TimeSeriesDataFrame with target + all past + known covariate columns."""
    all_feat = PAST_COVARIATES + KNOWN_COVARIATES
    available = [c for c in all_feat if c in df.columns]
    missing   = [c for c in all_feat if c not in df.columns]
    if missing:
        print(f"  WARNING: missing covariate columns: {missing}")

    keep = ["item_id", "timestamp", "base_units"] + available
    d    = (
        df[["item_id", "ds", "base_units"] + available]
        .rename(columns={"ds": "timestamp"})
        .copy()
        .dropna(subset=["base_units"])
    )
    d["base_units"] = pd.to_numeric(d["base_units"], errors="coerce").clip(lower=0)
    for c in available:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)

    return TimeSeriesDataFrame.from_data_frame(
        d,
        id_column="item_id",
        timestamp_column="timestamp",
    )


def filter_min_rows(ts: TimeSeriesDataFrame, min_rows: int) -> TimeSeriesDataFrame:
    lengths = ts.num_timesteps_per_item()
    valid   = lengths[lengths >= min_rows].index
    return ts.loc[valid]


def make_future_known_covariates(train_ts: TimeSeriesDataFrame,
                                 df_train: pd.DataFrame) -> TimeSeriesDataFrame:
    """Generate H future weeks of KNOWN_COVARIATES for each series.

    week_of_year   — derived from future calendar date
    weeks_since_launch — last observed value + forecast step (1..H)
    """
    last_ts_per_item = (
        train_ts.reset_index()
        .groupby("item_id")["timestamp"]
        .max()
        .to_dict()
    )
    last_wsl_per_item = (
        df_train[["item_id", "ds", "weeks_since_launch"]]
        .sort_values("ds")
        .groupby("item_id")
        .last()["weeks_since_launch"]
        .to_dict()
    )

    rows = []
    for item_id in train_ts.item_ids:
        last_ts  = last_ts_per_item[item_id]
        base_wsl = int(last_wsl_per_item.get(item_id, 0))
        for h in range(1, H + 1):
            future_ts = last_ts + pd.Timedelta(weeks=h)
            rows.append({
                "item_id":            item_id,
                "timestamp":          future_ts,
                "week_of_year":       int(future_ts.isocalendar().week),
                "weeks_since_launch": base_wsl + h,
            })

    future_df = pd.DataFrame(rows)
    return TimeSeriesDataFrame.from_data_frame(
        future_df,
        id_column="item_id",
        timestamp_column="timestamp",
    )


# ── Main evaluation loop ───────────────────────────────────────────────────────

def run_cutpoint(df: pd.DataFrame, cp: dict, preset: str) -> dict:
    tag    = cp["tag"]
    cutoff = cp["cutoff"]

    print(f"\n{'='*60}")
    print(f"Cutpoint: {cp['label']}  (cutoff={cutoff.date()}, preset={preset})")
    print(f"{'='*60}")

    df_train = df[df["ds"] <= cutoff].copy()
    test_end  = cutoff + pd.Timedelta(weeks=H)
    df_test   = df[(df["ds"] > cutoff) & (df["ds"] <= test_end)].copy()

    if len(df_test) == 0:
        print(f"  No test data after {cutoff.date()} — skipping")
        return {}

    train_ts = build_ts_df(df_train)
    train_ts = filter_min_rows(train_ts, MIN_TRAIN_ROWS)

    n_series = len(train_ts.item_ids)
    print(f"  Train series  : {n_series:,}  (≥{MIN_TRAIN_ROWS} wk history)")
    print(f"  Train rows    : {len(train_ts):,}")
    print(f"  Test rows     : {len(df_test):,}")
    print(f"  Past covs     : {len(PAST_COVARIATES)} features")
    print(f"  Known covs    : {KNOWN_COVARIATES}")

    model_path = f"outputs/ag_models_mo66_{tag}"
    if os.path.exists(model_path):
        shutil.rmtree(model_path)

    predictor = TimeSeriesPredictor(
        prediction_length=H,
        path=model_path,
        target="base_units",
        quantile_levels=[0.1, 0.5, 0.9],
        eval_metric="MASE",
        freq="W-SUN",
        known_covariates_names=KNOWN_COVARIATES,
        verbosity=1,
    )

    print(f"\nFitting AutoGluon ({preset}) with Mo domain features …")
    predictor.fit(train_ts, presets=preset, time_limit=1800)

    print("Generating future known covariates …")
    future_cov = make_future_known_covariates(train_ts, df_train)

    print("Predicting …")
    preds = predictor.predict(train_ts, known_covariates=future_cov)

    # Flatten predictions → join to actuals
    preds_df = preds.reset_index()
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

    actuals_df = (
        df_test[["item_id", "ds", "base_units"]]
        .rename(columns={"ds": "timestamp"})
        .copy()
    )
    merged    = pd.merge(preds_df, actuals_df, on=["item_id", "timestamp"], how="inner")
    n_matched = len(merged)
    print(f"  Matched {n_matched:,} forecast × actual pairs")

    pred_col = "q50" if "q50" in merged.columns else "mean" if "mean" in merged.columns else None
    wm = wmape(merged["base_units"].values, merged[pred_col].values) if pred_col else np.nan
    print(f"  wMAPE (q50)   : {wm:.2f}%")

    lb = None
    try:
        lb = predictor.leaderboard()
        lb["cutpoint"] = tag
        lb.to_csv(f"outputs/mo66_leaderboard_{tag}.csv", index=False)
        print(f"\nLeaderboard ({cp['label']}):")
        display_cols = [c for c in ["model", "score_val", "pred_time_val_marginal",
                                    "fit_time_marginal"] if c in lb.columns]
        print(lb[display_cols].head(15).to_string(index=False))
    except Exception as e:
        print(f"  Leaderboard failed: {e}")

    fi_df = None
    try:
        fi_df = predictor.feature_importance(data=train_ts)
        if fi_df is not None and len(fi_df) > 0:
            print(f"\nFeature importance (tabular component, top 15):")
            print(fi_df.head(15).to_string())
    except Exception as e:
        print(f"  Feature importance unavailable: {e}")

    return {
        "label":       cp["label"],
        "preset":      preset,
        "n_series":    n_series,
        "n_matched":   n_matched,
        "wmape":       round(wm, 2) if not np.isnan(wm) else None,
        "leaderboard": lb.to_dict("records") if lb is not None else None,
        "fi_df":       fi_df,
    }


# ── Charts ─────────────────────────────────────────────────────────────────────

def load_mo65_wmape() -> dict:
    """Load MO_65 Run A wMAPE values if the metrics file exists."""
    path = "outputs/mo65_autogluon_metrics.json"
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        d = json.load(f)
    return {
        tag: res.get("wmape")
        for tag, res in d.get("autogluon_results", {}).items()
    }


def chart_accuracy(results: dict):
    tags   = ["dec2024", "oct2025", "dec2025"]
    labels = ["Dec 2024", "Oct 2025", "Dec 2025"]

    mo65 = load_mo65_wmape()

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.patch.set_facecolor("#f8f9fa")
    fig.suptitle(
        "AutoGluon-TimeSeries vs. MO_38 Horse Race  |  wMAPE — lower is better\n"
        "Run A = raw series only · Run B = +28 Mo domain features",
        fontsize=12, y=1.01,
    )

    for ax, tag, label in zip(axes, tags, labels):
        ref_vals   = {k: HORSE_RACE_REF[k][tags.index(tag)] for k in HORSE_RACE_REF}
        ag_a_wm    = mo65.get(tag)
        ag_b_wm    = results.get(tag, {}).get("wmape")

        model_names = list(ref_vals.keys())
        values      = list(ref_vals.values())
        colors      = [
            "#1f4e79" if "Aevah" in m else "#aaaaaa" for m in model_names
        ]

        if ag_a_wm is not None:
            model_names.append("AutoGluon\nRun A")
            values.append(ag_a_wm)
            colors.append("#f4a261")

        if ag_b_wm is not None:
            model_names.append("AutoGluon\nRun B")
            values.append(ag_b_wm)
            colors.append("#e84444")

        safe_vals = [v for v in values if v is not None and not np.isnan(v)]
        y_max     = max(safe_vals) * 1.25 + 3 if safe_vals else 100

        bars = ax.bar(model_names, values, color=colors, width=0.6,
                      edgecolor="white", linewidth=0.5)
        for bar, v in zip(bars, values):
            if v is not None and not np.isnan(v):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        v + y_max * 0.012,
                        f"{v:.1f}%",
                        ha="center", va="bottom", fontsize=8, fontweight="bold")

        ax.set_title(label, fontsize=11, pad=8)
        ax.set_ylabel("wMAPE (%)" if tag == "dec2024" else "")
        ax.set_ylim(0, y_max)
        ax.tick_params(axis="x", labelsize=8)
        ax.set_facecolor("#f8f9fa")
        ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    path = "outputs/mo66_accuracy_comparison.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#f8f9fa")
    plt.close()
    print(f"\nSaved {path}")


def chart_explainability(results: dict):
    dec_res    = results.get("dec2025", {})
    lb_records = dec_res.get("leaderboard")
    fi_df      = dec_res.get("fi_df")

    if lb_records is None:
        print("  No leaderboard data — skipping explainability chart")
        return

    lb      = pd.DataFrame(lb_records)
    has_fi  = fi_df is not None and len(fi_df) > 0
    n_panels = 2 if has_fi else 1

    fig, axes = plt.subplots(1, n_panels, figsize=(8 * n_panels, 7))
    fig.patch.set_facecolor("#f8f9fa")
    if n_panels == 1:
        axes = [axes]

    fig.suptitle(
        "AutoGluon Run B: Explainability  |  Dec 2025 cutpoint",
        fontsize=12, y=1.01,
    )

    # Panel 1: leaderboard
    ax = axes[0]
    score_col = "score_val" if "score_val" in lb.columns else lb.columns[1]
    lb_sorted = lb.dropna(subset=[score_col]).sort_values(score_col).head(12)
    scores      = lb_sorted[score_col].abs().values
    model_names = lb_sorted["model"].tolist()

    colors = ["#2ecc71" if i == 0 else "#1f77b4" if i < 4 else "#aaaaaa"
              for i in range(len(model_names))]
    bars = ax.barh(range(len(model_names)), scores, color=colors, edgecolor="white")
    ax.set_yticks(range(len(model_names)))
    ax.set_yticklabels(model_names, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel(f"|{score_col}| (MASE — lower is better)")
    ax.set_title("Model Leaderboard\n(top = ensemble winner)", fontsize=10)
    ax.set_facecolor("#f8f9fa")
    ax.spines[["top", "right"]].set_visible(False)
    for bar, v in zip(bars, scores):
        ax.text(v + max(scores) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{v:.3f}", va="center", fontsize=8)

    # Panel 2: feature importance from tabular model
    if has_fi:
        ax2     = axes[1]
        imp_col = fi_df.columns[0]
        top_fi  = fi_df[[imp_col]].head(15).sort_values(imp_col)
        ax2.barh(range(len(top_fi)), top_fi[imp_col].values,
                 color="#1f77b4", edgecolor="white")
        ax2.set_yticks(range(len(top_fi)))
        ax2.set_yticklabels(top_fi.index.tolist(), fontsize=9, fontfamily="monospace")
        ax2.set_xlabel("Importance")
        ax2.set_title(
            "Tabular Model: Feature Importance\n(Mo domain features as past/known covariates)",
            fontsize=9,
        )
        ax2.set_facecolor("#f8f9fa")
        ax2.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    path = "outputs/mo66_explainability.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#f8f9fa")
    plt.close()
    print(f"Saved {path}")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MO_66 — AutoGluon Run B (domain features)")
    parser.add_argument("--fast", action="store_true",
                        help="Use fast_training preset (< 5 min per cutpoint)")
    parser.add_argument("--cutpoint", choices=["dec2024", "oct2025", "dec2025"],
                        default=None, help="Run a single cutpoint only")
    args   = parser.parse_args()
    preset = "fast_training" if args.fast else "medium_quality"

    print("=" * 60)
    print("MO_66 — AutoGluon-TimeSeries Run B (Mo domain features)")
    print(f"  Preset: {preset}")
    print(f"  Past covariates  : {len(PAST_COVARIATES)}")
    print(f"  Known covariates : {KNOWN_COVARIATES}")
    print("=" * 60)

    print(f"\nLoading {PARQUET} …")
    df = load_and_prepare(PARQUET)
    print(f"  Rows: {len(df):,} | Series: {df['item_id'].nunique():,} | "
          f"Date range: {df['ds'].min().date()} → {df['ds'].max().date()}")
    print(f"  tdp_wow_delta present: {'tdp_wow_delta' in df.columns}")

    cutpoints_to_run = (
        [cp for cp in CUTPOINTS if cp["tag"] == args.cutpoint]
        if args.cutpoint else CUTPOINTS
    )

    results = {}
    for cp in cutpoints_to_run:
        res = run_cutpoint(df, cp, preset)
        if res:
            results[cp["tag"]] = res

    # ── Summary table ──────────────────────────────────────────────────────────
    mo65 = load_mo65_wmape()
    print("\n" + "=" * 60)
    print("SUMMARY — wMAPE comparison")
    print("=" * 60)
    header = f"{'Model':<24}  {'Dec 2024':>10}  {'Oct 2025':>10}  {'Dec 2025':>10}"
    print(header)
    print("-" * len(header))
    for model, vals in HORSE_RACE_REF.items():
        label = model.replace("\n", " ")
        print(f"  {label:<22}  {vals[0]:>9.1f}%  {vals[1]:>9.1f}%  {vals[2]:>9.1f}%")

    # Run A row
    a_row = f"  {'AutoGluon Run A':<22}"
    for tag in ["dec2024", "oct2025", "dec2025"]:
        wm = mo65.get(tag)
        a_row += f"  {wm:>9.1f}%" if wm is not None else f"  {'—':>9}"
    print(a_row)

    # Run B row
    b_row = f"  {'AutoGluon Run B':<22}"
    for tag in ["dec2024", "oct2025", "dec2025"]:
        wm = results.get(tag, {}).get("wmape")
        b_row += f"  {wm:>9.1f}%" if wm is not None else f"  {'—':>9}"
    print(b_row)

    # ── Lift analysis ──────────────────────────────────────────────────────────
    print("\nRun B improvement vs. Run A (positive = domain features help):")
    for tag in ["dec2024", "oct2025", "dec2025"]:
        a = mo65.get(tag)
        b = results.get(tag, {}).get("wmape")
        if a is not None and b is not None:
            delta = a - b
            label = next(cp["label"] for cp in CUTPOINTS if cp["tag"] == tag)
            direction = "improvement" if delta > 0 else "regression"
            print(f"  {label}: {a:.2f}% → {b:.2f}% ({delta:+.2f}pp, {direction})")

    # ── Save metrics JSON ──────────────────────────────────────────────────────
    meta = {
        "script":               "MO_66",
        "preset":               preset,
        "prediction_length":    H,
        "min_train_rows":       MIN_TRAIN_ROWS,
        "past_covariates":      PAST_COVARIATES,
        "known_covariates":     KNOWN_COVARIATES,
        "horse_race_reference": {k: list(v) for k, v in HORSE_RACE_REF.items()},
        "mo65_run_a_wmape":     mo65,
        "autogluon_results": {
            tag: {k: v for k, v in res.items() if k not in ("leaderboard", "fi_df")}
            for tag, res in results.items()
        },
        "leaderboard_dec2025": results.get("dec2025", {}).get("leaderboard"),
    }
    out_path = "outputs/mo66_autogluon_metrics.json"
    with open(out_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"\nSaved {out_path}")

    if results:
        chart_accuracy(results)
        chart_explainability(results)

    print("\nMO_66 complete.")
