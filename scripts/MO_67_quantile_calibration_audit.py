"""MO_67 — Quantile Calibration Audit (Gap #5).

Audit question: Do the v3 q10/q50/q90 LightGBM models produce calibrated
quantile bands? A well-calibrated q10 prediction means ~10% of actuals fall
below it. If P90 only covers 70% of actuals, bands are too narrow — the
inventory floor/ceiling story is undermined even if P50 wMAPE looks good.

Method
------
1. Load retailer_sales_weekly.parquet (actuals through Apr 2026).
2. Reproduce the exact val split used in v3 training: last 13 weeks per series.
3. Load v3 q10/q50/q90 pkl models; generate predictions on val set.
4. Compute coverage rate per quantile: coverage_q = mean(actual < pred_q).
5. Report calibration error = actual_coverage - target_coverage.
6. Material threshold: any quantile >±5pp off target → FAIL.
7. Secondary cuts: coverage by maturity bucket, by channel, by retailer tier.
8. Outputs: JSON scorecard + 2-panel PNG (reliability diagram + segment heatmap).

Run from the FirstAgent/ directory:
    python scripts/MO_67_quantile_calibration_audit.py
"""

import json
import pickle
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent.parent
PARQUET    = ROOT / "outputs" / "retailer_sales_weekly.parquet"
METRICS_IN = ROOT / "outputs" / "retailer_sales_train_metrics.json"
MODEL_DIR  = ROOT / "outputs"
OUT_JSON   = ROOT / "outputs" / "mo67_calibration_scorecard.json"
OUT_PNG    = ROOT / "outputs" / "mo67_calibration_chart.png"

QUANTILES  = [0.10, 0.50, 0.90]
Q_TAGS     = ["q10", "q50", "q90"]
GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]

# Material threshold: any quantile more than this many pp off target → FAIL
MATERIAL_THRESHOLD_PP = 5.0


def load_models(version: str = "v3") -> dict:
    models = {}
    for tag in Q_TAGS:
        path = MODEL_DIR / f"model_retailer_sales_{tag}_{version}.pkl"
        with open(path, "rb") as f:
            models[tag] = pickle.load(f)
        print(f"  Loaded {path.name}")
    return models


def build_val_set(df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
    """Reproduce v3 val split: last 13 weeks of each series."""
    df = df.copy()
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    # Numeric coercion (matches MO_26 preprocessing)
    for c in feature_cols:
        if c != "channel_outlet" and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "channel_outlet" in df.columns:
        df["channel_outlet"] = df["channel_outlet"].astype("category")

    df = df.dropna(subset=["base_units"]).copy()
    df["log_base_units"] = np.log1p(df["base_units"])

    cutoff = df["__time"].max() - pd.Timedelta(weeks=13)
    val = df[df["__time"] > cutoff].copy()
    print(f"  Val set: {len(val):,} rows | {val['__time'].min().date()} → {val['__time'].max().date()}")
    return val, cutoff


def maturity_bucket(weeks: pd.Series) -> pd.Series:
    return pd.cut(
        weeks,
        bins=[-1, 12, 51, 999],
        labels=["new (<13w)", "growing (13–51w)", "mature (52w+)"],
    )


def coverage_rate(actuals: np.ndarray, preds: np.ndarray) -> float:
    """Fraction of actuals that fall strictly below the predicted quantile."""
    return float(np.mean(actuals < preds))


def run_audit(val: pd.DataFrame, models: dict, feature_cols: list) -> dict:
    available = [c for c in feature_cols if c in val.columns]
    missing   = [c for c in feature_cols if c not in val.columns]
    if missing:
        print(f"  WARNING — features missing from parquet (will be NaN): {missing}")

    X_val     = val[available]
    y_actual  = val["base_units"].values

    preds = {}
    for tag, model in models.items():
        pred_log   = model.predict(X_val)
        pred_units = np.expm1(np.clip(pred_log, 0, None))
        preds[tag] = pred_units

    # ── Portfolio-level coverage ───────────────────────────────────────────────
    results = {}
    any_fail = False
    print("\n── Portfolio-level calibration ──────────────────────────────────────")
    for q, tag in zip(QUANTILES, Q_TAGS):
        cov  = coverage_rate(y_actual, preds[tag])
        err  = (cov - q) * 100           # pp deviation from target
        flag = "FAIL" if abs(err) > MATERIAL_THRESHOLD_PP else "PASS"
        if flag == "FAIL":
            any_fail = True
        print(f"  {tag}: target={q*100:.0f}%  actual={cov*100:.1f}%  "
              f"error={err:+.1f}pp  [{flag}]")
        results[tag] = {"target": q, "actual_coverage": round(cov, 4),
                        "error_pp": round(err, 2), "verdict": flag}

    overall = "FAIL" if any_fail else "PASS"

    # ── Coverage by maturity bucket ────────────────────────────────────────────
    val = val.copy()
    for tag in Q_TAGS:
        val[f"pred_{tag}"] = preds[tag]
    val["maturity"] = maturity_bucket(val["weeks_since_launch"])

    print("\n── Coverage by maturity bucket ──────────────────────────────────────")
    maturity_results = {}
    for bucket in ["new (<13w)", "growing (13–51w)", "mature (52w+)"]:
        subset = val[val["maturity"] == bucket]
        if len(subset) == 0:
            continue
        y_sub = subset["base_units"].values
        row = {"n": int(len(subset))}
        for q, tag in zip(QUANTILES, Q_TAGS):
            cov = coverage_rate(y_sub, subset[f"pred_{tag}"].values)
            row[tag] = round(cov * 100, 1)
        maturity_results[bucket] = row
        print(f"  {bucket:20s} (n={len(subset):5,}): "
              f"q10={row['q10']}%  q50={row['q50']}%  q90={row['q90']}%")

    # ── Coverage by channel ────────────────────────────────────────────────────
    print("\n── Coverage by channel ───────────────────────────────────────────────")
    channel_results = {}
    for ch in sorted(val["channel_outlet"].astype(str).unique()):
        subset = val[val["channel_outlet"].astype(str) == ch]
        if len(subset) < 100:
            continue
        y_sub = subset["base_units"].values
        row = {"n": int(len(subset))}
        for q, tag in zip(QUANTILES, Q_TAGS):
            cov = coverage_rate(y_sub, subset[f"pred_{tag}"].values)
            row[tag] = round(cov * 100, 1)
        channel_results[ch] = row
        print(f"  {ch[:40]:42s} (n={len(subset):5,}): "
              f"q10={row['q10']}%  q50={row['q50']}%  q90={row['q90']}%")

    # ── Interval width analysis ────────────────────────────────────────────────
    interval_width = preds["q90"] - preds["q10"]
    actual_nonzero = y_actual[y_actual > 0]
    width_nonzero  = interval_width[y_actual > 0]
    median_width_pct = float(np.median(width_nonzero / actual_nonzero) * 100)
    print(f"\n── Interval width (q90−q10) ──────────────────────────────────────────")
    print(f"  Median width as % of actual: {median_width_pct:.1f}%")
    print(f"  Rows where q10 > actual (under-prediction of lower band): "
          f"{(preds['q10'] > y_actual).mean()*100:.1f}%")
    print(f"  Rows where q90 < actual (over-prediction of upper band): "
          f"{(preds['q90'] < y_actual).mean()*100:.1f}%")

    return {
        "overall_verdict": overall,
        "material_threshold_pp": MATERIAL_THRESHOLD_PP,
        "val_rows": int(len(val)),
        "portfolio": results,
        "maturity_breakdown": maturity_results,
        "channel_breakdown": channel_results,
        "interval_width": {
            "median_width_pct_of_actual": round(median_width_pct, 1),
            "pct_rows_q10_exceeds_actual": round((preds["q10"] > y_actual).mean()*100, 1),
            "pct_rows_q90_below_actual": round((preds["q90"] < y_actual).mean()*100, 1),
        },
    }, val, preds, y_actual


def plot_results(audit: dict, val: pd.DataFrame, preds: dict, y_actual: np.ndarray):
    fig = plt.figure(figsize=(14, 6))
    fig.patch.set_facecolor("#1a1a2e")
    gs = gridspec.GridSpec(1, 2, figure=fig, wspace=0.35)

    blue  = "#4a9eda"
    green = "#2ecc71"
    red   = "#e74c3c"
    amber = "#f39c12"
    text  = "#e0e0e0"
    grid  = "#2a2a4a"

    # ── Panel 1: Reliability diagram ──────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0])
    ax1.set_facecolor("#12122a")
    targets  = [q * 100 for q in QUANTILES]
    actuals  = [audit["portfolio"][t]["actual_coverage"] * 100 for t in Q_TAGS]
    errors   = [audit["portfolio"][t]["error_pp"] for t in Q_TAGS]
    verdicts = [audit["portfolio"][t]["verdict"] for t in Q_TAGS]
    colors   = [green if v == "PASS" else red for v in verdicts]

    ax1.plot([0, 100], [0, 100], color=grid, linestyle="--", linewidth=1.2,
             label="Perfect calibration", zorder=1)
    for t, a, e, c, tag in zip(targets, actuals, errors, colors, Q_TAGS):
        ax1.scatter(t, a, color=c, s=160, zorder=5)
        ax1.annotate(f"{tag}\n{a:.1f}% ({e:+.1f}pp)",
                     (t, a), textcoords="offset points",
                     xytext=(10, -5), color=c, fontsize=9, fontweight="bold")

    ax1.fill_between([0, 100],
                     [0 - MATERIAL_THRESHOLD_PP, 100 - MATERIAL_THRESHOLD_PP],
                     [0 + MATERIAL_THRESHOLD_PP, 100 + MATERIAL_THRESHOLD_PP],
                     alpha=0.12, color=blue, label=f"±{MATERIAL_THRESHOLD_PP:.0f}pp tolerance band")
    ax1.set_xlim(-5, 105); ax1.set_ylim(-5, 105)
    ax1.set_xlabel("Target quantile (%)", color=text, fontsize=10)
    ax1.set_ylabel("Actual coverage (%)", color=text, fontsize=10)
    ax1.set_title("Reliability Diagram — Quantile Calibration", color=text, fontsize=11, pad=10)
    ax1.tick_params(colors=text)
    for sp in ax1.spines.values():
        sp.set_edgecolor(grid)
    ax1.legend(facecolor="#12122a", labelcolor=text, fontsize=8)

    verdict_color = green if audit["overall_verdict"] == "PASS" else red
    ax1.text(0.02, 0.97, f"Overall: {audit['overall_verdict']}",
             transform=ax1.transAxes, color=verdict_color,
             fontsize=12, fontweight="bold", va="top")

    # ── Panel 2: Maturity breakdown ────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[1])
    ax2.set_facecolor("#12122a")

    buckets = list(audit["maturity_breakdown"].keys())
    x = np.arange(len(buckets))
    w = 0.25

    q_colors = [blue, amber, green]
    for i, (tag, qc) in enumerate(zip(Q_TAGS, q_colors)):
        target = QUANTILES[i] * 100
        vals = [audit["maturity_breakdown"][b][tag] for b in buckets]
        bars = ax2.bar(x + (i - 1) * w, vals, w, label=tag, color=qc, alpha=0.8)
        ax2.axhline(target, color=qc, linestyle=":", linewidth=0.8, alpha=0.5)

    ax2.set_xticks(x)
    ax2.set_xticklabels([b.split(" ")[0] for b in buckets], color=text, fontsize=9)
    ax2.set_ylabel("Actual coverage (%)", color=text, fontsize=10)
    ax2.set_title("Coverage by Maturity Bucket", color=text, fontsize=11, pad=10)
    ax2.tick_params(colors=text)
    for sp in ax2.spines.values():
        sp.set_edgecolor(grid)
    ax2.legend(facecolor="#12122a", labelcolor=text, fontsize=8)
    ax2.set_ylim(0, 110)

    # Add n= labels
    for i, b in enumerate(buckets):
        n = audit["maturity_breakdown"][b]["n"]
        ax2.text(i, 103, f"n={n:,}", ha="center", color=text, fontsize=7.5)

    fig.suptitle("MO_67 — Quantile Calibration Audit  |  v3 models, Jan–Apr 2026 holdout",
                 color=text, fontsize=12, fontweight="bold", y=1.01)

    plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"\n  Chart saved → {OUT_PNG}")


if __name__ == "__main__":
    print("=" * 65)
    print("MO_67 — Quantile Calibration Audit")
    print("=" * 65)

    # Load feature list from training metrics (must match model exactly)
    with open(METRICS_IN) as f:
        metrics_meta = json.load(f)
    feature_cols = metrics_meta["features_used"]
    print(f"\nFeature set: {len(feature_cols)} features (from {METRICS_IN.name})")

    print("\nLoading models …")
    models = load_models("v3")

    print("\nLoading actuals parquet …")
    df = pd.read_parquet(PARQUET)
    print(f"  Rows: {len(df):,}")

    print("\nBuilding val set (last 13 weeks per series) …")
    val, cutoff = build_val_set(df, feature_cols)

    print("\nRunning calibration audit …")
    audit, val_enriched, preds, y_actual = run_audit(val, models, feature_cols)

    print(f"\n{'='*65}")
    print(f"OVERALL VERDICT: {audit['overall_verdict']}")
    print(f"{'='*65}")
    for tag in Q_TAGS:
        p = audit["portfolio"][tag]
        print(f"  {tag}: {p['actual_coverage']*100:.1f}% coverage "
              f"(target {p['target']*100:.0f}%) — {p['error_pp']:+.1f}pp — {p['verdict']}")

    print("\nGenerating chart …")
    plot_results(audit, val_enriched, preds, y_actual)

    with open(OUT_JSON, "w") as f:
        json.dump(audit, f, indent=2)
    print(f"  Scorecard saved → {OUT_JSON}")
    print("\nDone.")
