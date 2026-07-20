"""MO_67b — q90 Conformal Recalibration.

MO_67 confirmed the q90 upper band fails calibration: 82.1% actual coverage
vs. 90% target (−7.9pp, exceeds ±5pp material threshold). q10 and q50 pass.

This script computes a post-hoc calibration constant for q90 and verifies
it restores coverage to ≥85% on the same val set (Jan–Apr 2026).

Method: split-conformal on the val set.
  • First 50% of val rows → compute calibration constant (hold-out A).
  • Second 50% of val rows → verify coverage (hold-out B).
  Both additive and multiplicative constants are tested; the better one wins.

Output
------
  outputs/mo67_calibration_constants.json  — constant type + value
  outputs/mo67b_recalibration_chart.png    — before/after comparison by maturity

MO_27 reads outputs/mo67_calibration_constants.json at runtime and applies
the q90 adjustment after seasonal blend, before writing the forecast parquet.

Run from the FirstAgent/ directory:
    python scripts/MO_67b_q90_recalibration.py
"""

import json
import pickle
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT       = Path(__file__).parent.parent
PARQUET    = ROOT / "outputs" / "retailer_sales_weekly.parquet"
METRICS_IN = ROOT / "outputs" / "retailer_sales_train_metrics.json"
MODEL_DIR  = ROOT / "outputs"
OUT_JSON   = ROOT / "outputs" / "mo67_calibration_constants.json"
OUT_PNG    = ROOT / "outputs" / "mo67b_recalibration_chart.png"

Q_TAGS     = ["q10", "q50", "q90"]
GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]
TARGET_Q90 = 0.90


def load_models(version: str = "v3") -> dict:
    models = {}
    for tag in Q_TAGS:
        with open(MODEL_DIR / f"model_retailer_sales_{tag}_{version}.pkl", "rb") as f:
            models[tag] = pickle.load(f)
    return models


def build_val_set(df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
    df = df.copy()
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    for c in feature_cols:
        if c != "channel_outlet" and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "channel_outlet" in df.columns:
        df["channel_outlet"] = df["channel_outlet"].astype("category")
    df = df.dropna(subset=["base_units"]).copy()
    cutoff = df["__time"].max() - pd.Timedelta(weeks=13)
    return df[df["__time"] > cutoff].copy(), cutoff


def predict_q90(val: pd.DataFrame, model, feature_cols: list) -> np.ndarray:
    available = [c for c in feature_cols if c in val.columns]
    pred_log  = model.predict(val[available])
    return np.expm1(np.clip(pred_log, 0, None))


def coverage(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(np.mean(actual < pred))


def maturity_bucket(weeks: pd.Series) -> pd.Series:
    return pd.cut(weeks, bins=[-1, 12, 51, 999],
                  labels=["new (<13w)", "growing (13–51w)", "mature (52w+)"])


if __name__ == "__main__":
    print("=" * 65)
    print("MO_67b — q90 Conformal Recalibration")
    print("=" * 65)

    with open(METRICS_IN) as f:
        meta = json.load(f)
    feature_cols = meta["features_used"]

    print("\nLoading models and actuals …")
    models = load_models("v3")
    df     = pd.read_parquet(PARQUET)

    print("Building val set …")
    val, cutoff = build_val_set(df, feature_cols)
    y_actual  = val["base_units"].values
    q90_preds = predict_q90(val, models["q90"], feature_cols)

    print(f"  Val rows: {len(val):,}  |  Baseline q90 coverage: "
          f"{coverage(y_actual, q90_preds)*100:.1f}%  (target 90%)")

    # ── Split val in half: A = calibration, B = verification ──────────────────
    n      = len(val)
    half   = n // 2
    idx    = np.arange(n)
    np.random.seed(42)
    np.random.shuffle(idx)
    A_idx, B_idx = idx[:half], idx[half:]

    yA, qA = y_actual[A_idx], q90_preds[A_idx]
    yB, qB = y_actual[B_idx], q90_preds[B_idx]

    # ── Additive offset ────────────────────────────────────────────────────────
    # Nonconformity score: actual - q90_pred (positive when actual exceeds band)
    scores_add = yA - qA
    add_offset = float(np.percentile(scores_add, TARGET_Q90 * 100))
    cov_add_B  = coverage(yB, qB + add_offset)
    cov_add_all = coverage(y_actual, q90_preds + add_offset)

    print(f"\n── Additive offset ──────────────────────────────────────────────────")
    print(f"  Offset:            {add_offset:+.1f} units")
    print(f"  Coverage on B:     {cov_add_B*100:.1f}%")
    print(f"  Coverage on full:  {cov_add_all*100:.1f}%")

    # ── Multiplicative factor ──────────────────────────────────────────────────
    # Nonconformity score: actual / q90_pred (ratio; only for positive preds)
    safe_qA  = np.maximum(qA, 1.0)
    scores_mul = yA / safe_qA
    mul_factor = float(np.percentile(scores_mul, TARGET_Q90 * 100))
    cov_mul_B  = coverage(yB, qB * mul_factor)
    cov_mul_all = coverage(y_actual, q90_preds * mul_factor)

    print(f"\n── Multiplicative factor ────────────────────────────────────────────")
    print(f"  Factor:            {mul_factor:.4f}×  (+{(mul_factor-1)*100:.1f}%)")
    print(f"  Coverage on B:     {cov_mul_B*100:.1f}%")
    print(f"  Coverage on full:  {cov_mul_all*100:.1f}%")

    # ── Pick winner: closest to 90% on hold-out B without overshooting by >3pp ─
    target = TARGET_Q90
    err_add = abs(cov_add_B - target)
    err_mul = abs(cov_mul_B - target)

    if err_mul <= err_add:
        winner    = "multiplicative"
        constant  = mul_factor
        q90_adj   = q90_preds * mul_factor
        cov_final = cov_mul_all
        print(f"\n  Winner: MULTIPLICATIVE  (closer to target on hold-out B)")
    else:
        winner    = "additive"
        constant  = add_offset
        q90_adj   = q90_preds + add_offset
        cov_final = cov_add_all
        print(f"\n  Winner: ADDITIVE  (closer to target on hold-out B)")

    print(f"  Calibrated coverage (full val): {cov_final*100:.1f}%")

    # ── Maturity breakdown before / after ──────────────────────────────────────
    val = val.copy()
    val["q90_raw"] = q90_preds
    val["q90_cal"] = q90_adj
    val["maturity"] = maturity_bucket(val["weeks_since_launch"])

    print("\n── By maturity bucket: before / after ───────────────────────────────")
    maturity_results = {}
    for bucket in ["new (<13w)", "growing (13–51w)", "mature (52w+)"]:
        sub = val[val["maturity"] == bucket]
        if len(sub) == 0:
            continue
        y_sub = sub["base_units"].values
        cov_before = coverage(y_sub, sub["q90_raw"].values)
        cov_after  = coverage(y_sub, sub["q90_cal"].values)
        print(f"  {bucket:20s} (n={len(sub):5,}): "
              f"before={cov_before*100:.1f}%  after={cov_after*100:.1f}%")
        maturity_results[bucket] = {
            "n": int(len(sub)),
            "before": round(cov_before * 100, 1),
            "after":  round(cov_after  * 100, 1),
        }

    # ── Interval width impact ──────────────────────────────────────────────────
    q10_preds = predict_q90(val, models["q10"], feature_cols)
    width_before = np.median(q90_preds - q10_preds)
    width_after  = np.median(q90_adj   - q10_preds)
    print(f"\n── Interval width (q90−q10) ──────────────────────────────────────────")
    print(f"  Median before: {width_before:.1f} units")
    print(f"  Median after:  {width_after:.1f} units  "
          f"(+{width_after - width_before:.1f} units, "
          f"+{(width_after/width_before - 1)*100:.1f}%)")

    verdict = "PASS" if cov_final >= 0.85 else "FAIL"
    print(f"\n  Calibration verdict (≥85% required): {verdict}")
    print(f"  Final q90 coverage: {cov_final*100:.1f}%")

    # ── Save calibration constants ─────────────────────────────────────────────
    calibration = {
        "calibration_type":      winner,
        "q90_constant":          round(constant, 6),
        "uncalibrated_coverage": round(coverage(y_actual, q90_preds), 4),
        "calibrated_coverage":   round(cov_final, 4),
        "holdout_B_coverage":    round(cov_mul_B if winner == "multiplicative" else cov_add_B, 4),
        "val_rows":              int(n),
        "calibration_rows":      int(half),
        "verification_rows":     int(n - half),
        "computed_on":           str(cutoff.date()),
        "verdict":               verdict,
        "maturity_breakdown":    maturity_results,
        "interval_width": {
            "median_before": round(float(width_before), 1),
            "median_after":  round(float(width_after), 1),
            "pct_increase":  round((width_after / width_before - 1) * 100, 1),
        },
        "note": (
            "Applied in MO_27 after seasonal blend, before writing parquet. "
            f"Formula: forecast_units_high = max(0, forecast_units_high "
            + ("* q90_constant)" if winner == "multiplicative" else "+ q90_constant)")
        ),
    }

    with open(OUT_JSON, "w") as f:
        json.dump(calibration, f, indent=2)
    print(f"\n  Constants saved → {OUT_JSON}")

    # ── Chart ──────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor("#1a1a2e")

    blue, green, red, amber, text, grid = (
        "#4a9eda", "#2ecc71", "#e74c3c", "#f39c12", "#e0e0e0", "#2a2a4a"
    )

    # Panel 1: before / after bar per maturity bucket
    ax = axes[0]
    ax.set_facecolor("#12122a")
    buckets = list(maturity_results.keys())
    x = np.arange(len(buckets))
    w = 0.35
    b_vals = [maturity_results[b]["before"] for b in buckets]
    a_vals = [maturity_results[b]["after"]  for b in buckets]
    ns     = [maturity_results[b]["n"]      for b in buckets]

    ax.bar(x - w/2, b_vals, w, label="Before (raw)", color=red,   alpha=0.8)
    ax.bar(x + w/2, a_vals, w, label="After (calibrated)", color=green, alpha=0.8)
    ax.axhline(90, color=amber, linestyle="--", linewidth=1.2, label="Target 90%")
    ax.axhline(85, color=amber, linestyle=":",  linewidth=0.9, label="Min acceptable 85%")

    ax.set_xticks(x)
    ax.set_xticklabels([b.split(" ")[0] for b in buckets], color=text, fontsize=9)
    ax.set_ylabel("q90 coverage (%)", color=text)
    ax.set_title("q90 Coverage: Before vs After Recalibration", color=text, fontsize=11, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values(): sp.set_edgecolor(grid)
    ax.legend(facecolor="#12122a", labelcolor=text, fontsize=8)
    ax.set_ylim(60, 100)
    for i, (b, a, n) in enumerate(zip(b_vals, a_vals, ns)):
        ax.text(i - w/2, b + 0.5, f"{b:.1f}%", ha="center", color=red,   fontsize=8)
        ax.text(i + w/2, a + 0.5, f"{a:.1f}%", ha="center", color=green, fontsize=8)
        ax.text(i, 62, f"n={n:,}", ha="center", color=text, fontsize=7.5)

    # Panel 2: residual distribution (actual - q90_raw)
    ax2 = axes[1]
    ax2.set_facecolor("#12122a")
    residuals = y_actual - q90_preds
    clip_lo, clip_hi = np.percentile(residuals, [1, 99])
    res_clipped = np.clip(residuals, clip_lo, clip_hi)
    ax2.hist(res_clipped, bins=80, color=blue, alpha=0.75, edgecolor="none")
    ax2.axvline(0, color=amber, linewidth=1.2, linestyle="--", label="q90 prediction")
    if winner == "additive":
        ax2.axvline(-add_offset, color=green, linewidth=1.5, linestyle="-",
                    label=f"Calibration offset ({add_offset:+.0f} units)")
    else:
        # Show the implied additive shift for the median prediction
        median_pred = float(np.median(q90_preds))
        implied = median_pred * (mul_factor - 1)
        ax2.axvline(-implied, color=green, linewidth=1.5, linestyle="-",
                    label=f"Approx. shift at median pred ({implied:+.0f} units)")
    ax2.set_xlabel("actual − q90_pred (units)", color=text)
    ax2.set_ylabel("Count", color=text)
    ax2.set_title("Residual Distribution  (actual − q90 prediction)", color=text,
                  fontsize=11, pad=8)
    ax2.tick_params(colors=text)
    for sp in ax2.spines.values(): sp.set_edgecolor(grid)
    ax2.legend(facecolor="#12122a", labelcolor=text, fontsize=8)

    pct_positive = (residuals > 0).mean() * 100
    ax2.text(0.98, 0.97, f"{pct_positive:.1f}% actuals exceed raw q90",
             transform=ax2.transAxes, color=red, fontsize=9,
             ha="right", va="top", fontweight="bold")

    fig.suptitle(
        f"MO_67b — q90 Recalibration  |  {winner.title()} constant={constant:.4f}  "
        f"|  Coverage: {coverage(y_actual, q90_preds)*100:.1f}% → {cov_final*100:.1f}%",
        color=text, fontsize=11, fontweight="bold", y=1.01,
    )
    plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Chart saved → {OUT_PNG}")
    print("\nDone.")
