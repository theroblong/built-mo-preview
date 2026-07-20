"""MO_70 — BSTS / Elasticity Lift Magnitude Validation (Gap #8).

Audit question: When the model predicts a lift (or decline) from a price event,
does it get the magnitude right? 63% direction accuracy on clean events is known
(MO_47). But direction right + magnitude wrong → bad trade ROI decisions:
recommending a promo that returns 40% lift when the model says 15%.

Method
------
1. Load event_validation_cases.csv (30,876 events; 1,633 clean = promo_confounded=0).
2. Filter to clean events only.
3. Compute lift%: predicted = (post_pred - pre_baseline) / pre_baseline × 100
                  actual   = (post_actual - pre_baseline) / pre_baseline × 100
4. Compute signed error = pred_lift_pct − actual_lift_pct.
   Positive signed error → over-prediction of lift (model says bigger move than happened).
   Negative signed error → under-prediction of lift (model says smaller move than happened).
5. Material threshold: |mean_signed_error| > ±10% on p1–p99 trimmed distribution.
6. Segment cuts: elasticity band, direction-correct vs. wrong, retailer tier, maturity.
7. Separate analysis: price-down (typical promotion) vs. price-up (list price change) events.

Key caveat documented in output: the 13-week pre/post comparison window captures
seasonal effects, distribution changes, and competitive dynamics beyond the pure price
signal. The model predicts only the price-elasticity component; residual lift is
structural confounding even in "clean" events.

Outputs
-------
  outputs/mo70_magnitude_scorecard.json  — segment-level results + verdict
  outputs/mo70_magnitude_chart.png       — 4-panel visualization

Run from the FirstAgent/ directory:
    python scripts/MO_70_bsts_magnitude_validation.py
"""

import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

ROOT        = Path(__file__).parent.parent
EVENTS_CSV  = ROOT / "scripts" / "outputs" / "event_validation_cases.csv"
OUT_JSON    = ROOT / "outputs" / "mo70_magnitude_scorecard.json"
OUT_PNG     = ROOT / "outputs" / "mo70_magnitude_chart.png"

BIAS_THRESHOLD_PCT = 10.0   # |mean signed error %| above this → material
P_THRESHOLD        = 0.05


def signed_error_stats(signed_errs):
    """Return (mean, t, p, n, pct_over, pct_under) trimmed to p1-p99."""
    if len(signed_errs) < 10:
        return dict(mean=np.nan, t=np.nan, p=np.nan, n=len(signed_errs),
                    pct_over=np.nan, pct_under=np.nan)
    p1, p99 = np.percentile(signed_errs, [1, 99])
    trimmed = signed_errs[(signed_errs >= p1) & (signed_errs <= p99)]
    mean    = float(trimmed.mean())
    t, p    = stats.ttest_1samp(trimmed, 0.0)
    pct_over  = float((trimmed > 0).mean() * 100)
    pct_under = float((trimmed < 0).mean() * 100)
    return dict(mean=round(mean, 2), t=round(float(t), 3), p=round(float(p), 4),
                n=int(len(trimmed)), raw_n=int(len(signed_errs)),
                pct_over=round(pct_over, 1), pct_under=round(pct_under, 1))


if __name__ == "__main__":
    print("=" * 65)
    print("MO_70 — Lift Magnitude Validation (Gap #8)")
    print("=" * 65)

    df = pd.read_csv(EVENTS_CSV)
    clean = df[df["promo_confounded"] == 0].copy()
    print(f"\nAll events: {len(df):,}  |  Clean (TDP-unconfounded): {len(clean):,}")

    # ── Lift % computation ─────────────────────────────────────────────────────
    pre = clean["pre_13w_base_units"].abs().clip(lower=1.0)
    clean["pred_lift_pct"]   = (clean["post_units_pred"]   - pre) / pre * 100
    clean["actual_lift_pct"] = (clean["post_units_actual"] - pre) / pre * 100
    clean["signed_err_pct"]  = clean["pred_lift_pct"] - clean["actual_lift_pct"]

    # Price direction flag
    clean["price_direction"] = np.where(clean["price_per_bar_pct_chg"] < 0,
                                        "Price down (promo)", "Price up (list)")

    print(f"\n── Lift magnitude summary ───────────────────────────────────────────")
    print(f"  Pred lift  — mean: {clean['pred_lift_pct'].median():+.1f}% (median)  "
          f"{clean['pred_lift_pct'].mean():+.1f}% (mean)")
    print(f"  Actual lift — mean: {clean['actual_lift_pct'].median():+.1f}% (median)  "
          f"{clean['actual_lift_pct'].mean():+.1f}% (mean)")

    # ── Portfolio signed error ─────────────────────────────────────────────────
    port = signed_error_stats(clean["signed_err_pct"])
    port_material = abs(port["mean"]) > BIAS_THRESHOLD_PCT and port["p"] < P_THRESHOLD
    print(f"\n── Portfolio signed error (p1–p99 trimmed) ─────────────────────────")
    print(f"  Mean: {port['mean']:+.1f}%   t={port['t']}   p={port['p']}")
    print(f"  {port['pct_over']:.1f}% events: model over-predicted  |  "
          f"{port['pct_under']:.1f}% events: model under-predicted")
    print(f"  Material: {'YES' if port_material else 'no'}  (threshold: ±{BIAS_THRESHOLD_PCT}%, p<{P_THRESHOLD})")

    # ── Segment cuts ──────────────────────────────────────────────────────────
    cuts = {}

    # By price direction
    print(f"\n── By price direction ───────────────────────────────────────────────")
    dir_rows = []
    for level, grp in clean.groupby("price_direction"):
        s = signed_error_stats(grp["signed_err_pct"])
        mat = abs(s["mean"]) > BIAS_THRESHOLD_PCT and s["p"] < P_THRESHOLD if not np.isnan(s.get("mean", np.nan)) else False
        s.update({"level": level, "material": mat})
        dir_rows.append(s)
        print(f"  {level:28s}: mean={s['mean']:+.1f}%  under={s['pct_under']:.0f}%  "
              f"n={s['raw_n']}  {'⚠ MATERIAL' if mat else ''}")
    cuts["price_direction"] = dir_rows

    # By elasticity band
    print(f"\n── By elasticity band ───────────────────────────────────────────────")
    band_rows = []
    for level, grp in clean.groupby("elasticity_band"):
        s = signed_error_stats(grp["signed_err_pct"])
        mat = abs(s.get("mean", 0)) > BIAS_THRESHOLD_PCT and s.get("p", 1) < P_THRESHOLD
        s.update({"level": level, "material": mat,
                  "pred_lift_mean": round(grp["pred_lift_pct"].median(), 1),
                  "actual_lift_mean": round(grp["actual_lift_pct"].median(), 1)})
        band_rows.append(s)
        print(f"  {level:22s}: signed_err={s.get('mean', np.nan):+.1f}%  "
              f"pred_median={s['pred_lift_mean']:+.1f}%  actual_median={s['actual_lift_mean']:+.1f}%  "
              f"n={s.get('raw_n', 0)}  {'⚠ MATERIAL' if mat else ''}")
    cuts["elasticity_band"] = band_rows

    # By direction match
    print(f"\n── By direction accuracy ─────────────────────────────────────────────")
    dm_rows = []
    for level, grp in clean.groupby("dir_match"):
        s = signed_error_stats(grp["signed_err_pct"])
        mat = abs(s.get("mean", 0)) > BIAS_THRESHOLD_PCT and s.get("p", 1) < P_THRESHOLD
        s.update({"level": str(level), "material": mat})
        dm_rows.append(s)
        print(f"  dir_match={level}: mean={s.get('mean', np.nan):+.1f}%  "
              f"under={s.get('pct_under', np.nan):.0f}%  n={s.get('raw_n', 0)}  "
              f"{'⚠ MATERIAL' if mat else ''}")
    cuts["direction_match"] = dm_rows

    # Price-down only (most actionable for promo planning)
    price_down = clean[clean["price_direction"] == "Price down (promo)"].copy()
    pd_port = signed_error_stats(price_down["signed_err_pct"])
    pd_material = abs(pd_port.get("mean", 0)) > BIAS_THRESHOLD_PCT and pd_port.get("p", 1) < P_THRESHOLD
    print(f"\n── Price-down events only (most relevant to promo planning) ────────")
    print(f"  n={pd_port.get('raw_n', 0)}  mean signed error: {pd_port.get('mean', np.nan):+.1f}%  "
          f"Material: {'YES' if pd_material else 'no'}")
    print(f"  Pred lift median: {price_down['pred_lift_pct'].median():+.1f}%  "
          f"Actual lift median: {price_down['actual_lift_pct'].median():+.1f}%")

    # ── Verdict ───────────────────────────────────────────────────────────────
    any_material = port_material or pd_material
    verdict = "FAIL" if any_material else "PASS"
    print(f"\n{'='*65}")
    print(f"VERDICT: {verdict}  (threshold: |mean signed error| > ±{BIAS_THRESHOLD_PCT}%)")
    print(f"{'='*65}")
    print(f"  Portfolio mean signed error: {port.get('mean', np.nan):+.1f}%  "
          f"{'MATERIAL' if port_material else 'OK'}")
    print(f"  Price-down only:  {pd_port.get('mean', np.nan):+.1f}%  "
          f"{'MATERIAL' if pd_material else 'OK'}")

    # ── Interpretation note ───────────────────────────────────────────────────
    print(f"""
── Interpretation ───────────────────────────────────────────────────────
  The model predicts only the price-elasticity component of post-event lift.
  The 13-week pre/post window also captures: (1) seasonal effects, (2) subtle
  distribution changes not detected by TDP delta threshold, (3) competitive
  dynamics, (4) retailer-level promotional support beyond price.

  The "clean" flag removes large TDP changes, but residual confounders remain.
  The −{abs(port.get('mean', 0)):.0f}% mean signed error reflects both model under-prediction
  AND structural confounding. True price-only lift gap is likely smaller.

  Practical impact: if a planner sees "{price_down['pred_lift_pct'].median():+.1f}% expected lift
  from this price decrease" and actual is {price_down['actual_lift_pct'].median():+.1f}%,
  the model is still directionally useful for ranking events but the magnitude
  should be communicated with a wide uncertainty band.
""")

    # ── Scorecard ─────────────────────────────────────────────────────────────
    scorecard = {
        "verdict":             verdict,
        "bias_threshold_pct":  BIAS_THRESHOLD_PCT,
        "clean_events":        int(len(clean)),
        "price_down_events":   int(len(price_down)),
        "portfolio": {**port, "material": port_material},
        "price_down_only": {**pd_port, "material": pd_material,
                            "pred_lift_median_pct":  round(float(price_down["pred_lift_pct"].median()), 1),
                            "actual_lift_median_pct": round(float(price_down["actual_lift_pct"].median()), 1)},
        "cuts": cuts,
        "interpretation": (
            "Model predicts price-elasticity component only. 13-week pre/post window "
            "captures seasonal, distribution, and competitive confounders beyond price. "
            "Magnitude bias is real but partially structural — directional ranking is valid; "
            "absolute lift numbers should carry a wide uncertainty disclosure."
        ),
    }

    with open(OUT_JSON, "w") as f:
        json.dump(scorecard, f, indent=2, default=str)
    print(f"  Scorecard → {OUT_JSON}")

    # ── Charts ─────────────────────────────────────────────────────────────────
    print("\n── Generating chart ──────────────────────────────────────────────────")
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.patch.set_facecolor("#1a1a2e")

    blue, green, red, amber, text, grid_c = (
        "#4a9eda", "#2ecc71", "#e74c3c", "#f39c12", "#e0e0e0", "#2a2a4a"
    )

    # Panel 1: Scatter pred vs. actual lift% (price-down events, clipped)
    ax = axes[0, 0]
    ax.set_facecolor("#12122a")
    pd_clip_lo = price_down["actual_lift_pct"].quantile(0.02)
    pd_clip_hi = price_down["actual_lift_pct"].quantile(0.98)
    pd_plot = price_down[
        (price_down["actual_lift_pct"] >= pd_clip_lo) &
        (price_down["actual_lift_pct"] <= pd_clip_hi)
    ]
    ax.scatter(pd_plot["actual_lift_pct"], pd_plot["pred_lift_pct"],
               alpha=0.25, s=12, color=blue)
    lo = min(pd_plot["actual_lift_pct"].min(), pd_plot["pred_lift_pct"].min())
    hi = max(pd_plot["actual_lift_pct"].max(), pd_plot["pred_lift_pct"].max())
    ax.plot([lo, hi], [lo, hi], color=amber, linestyle="--", linewidth=1.2,
            label="Perfect calibration")
    ax.axhline(0, color=text, linewidth=0.5, alpha=0.4)
    ax.axvline(0, color=text, linewidth=0.5, alpha=0.4)
    ax.set_xlabel("Actual lift % (post/pre − 1)", color=text, fontsize=9)
    ax.set_ylabel("Predicted lift % (model)", color=text, fontsize=9)
    ax.set_title(f"Price-Down Events: Pred vs. Actual Lift\n(n={len(pd_plot)}, p2–p98 clipped)",
                 color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    ax.legend(facecolor="#12122a", labelcolor=text, fontsize=8)
    ax.text(0.02, 0.97,
            f"Pred median: {price_down['pred_lift_pct'].median():+.1f}%\n"
            f"Actual median: {price_down['actual_lift_pct'].median():+.1f}%",
            transform=ax.transAxes, color=text, fontsize=8, va="top")

    # Panel 2: Signed error distribution (all clean, p1-p99)
    ax = axes[0, 1]
    ax.set_facecolor("#12122a")
    p1, p99 = clean["signed_err_pct"].quantile([0.01, 0.99])
    err_clipped = clean["signed_err_pct"].clip(p1, p99)
    ax.hist(err_clipped, bins=80, color=blue, alpha=0.75, edgecolor="none")
    ax.axvline(0, color=amber, linewidth=1.5, linestyle="--", label="Zero error")
    ax.axvline(port["mean"], color=red, linewidth=2, linestyle="-",
               label=f"Mean {port['mean']:+.0f}%")
    ax.axvline(BIAS_THRESHOLD_PCT,  color=green, linewidth=1, linestyle=":", alpha=0.7)
    ax.axvline(-BIAS_THRESHOLD_PCT, color=green, linewidth=1, linestyle=":", alpha=0.7,
               label=f"±{BIAS_THRESHOLD_PCT:.0f}% threshold")
    ax.set_xlabel("Signed error % (pred − actual lift)", color=text, fontsize=9)
    ax.set_ylabel("Count", color=text, fontsize=9)
    ax.set_title("Signed Error Distribution\n(all 1,633 clean events, p1–p99 clipped)",
                 color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    ax.legend(facecolor="#12122a", labelcolor=text, fontsize=8)
    ax.text(0.02, 0.97,
            f"Under-predicting in {port['pct_under']:.0f}% of events",
            transform=ax.transAxes, color=red, fontsize=8, va="top", fontweight="bold")

    # Panel 3: Mean signed error by elasticity band (bar chart)
    ax = axes[1, 0]
    ax.set_facecolor("#12122a")
    b_labels = [r["level"] for r in band_rows if r.get("mean") is not None]
    b_means  = [r["mean"] for r in band_rows if r.get("mean") is not None]
    b_ns     = [r.get("raw_n", 0) for r in band_rows if r.get("mean") is not None]
    b_colors = [red if abs(m) > BIAS_THRESHOLD_PCT else amber if abs(m) > 5 else blue
                for m in b_means]
    x = range(len(b_labels))
    ax.bar(list(x), b_means, color=b_colors, alpha=0.85)
    ax.axhline(0, color=text, linewidth=0.8, alpha=0.5)
    ax.axhline(BIAS_THRESHOLD_PCT,  color=red, linewidth=1, linestyle="--", alpha=0.6)
    ax.axhline(-BIAS_THRESHOLD_PCT, color=red, linewidth=1, linestyle="--", alpha=0.6,
               label=f"±{BIAS_THRESHOLD_PCT:.0f}% threshold")
    ax.set_xticks(list(x))
    ax.set_xticklabels([l[:14] for l in b_labels], rotation=20, ha="right",
                       color=text, fontsize=8)
    ax.set_ylabel("Mean signed error %", color=text, fontsize=9)
    ax.set_title("Signed Error by Elasticity Band", color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    ax.legend(facecolor="#12122a", labelcolor=text, fontsize=8)
    for i, (m, n) in enumerate(zip(b_means, b_ns)):
        ax.text(i, m + 2 if m >= 0 else m - 6, f"{m:+.0f}%\nn={n}",
                ha="center", color=text, fontsize=7)

    # Panel 4: Pred vs. actual median lift by elasticity band (grouped bars)
    ax = axes[1, 1]
    ax.set_facecolor("#12122a")
    b_pred   = [r.get("pred_lift_mean", 0) for r in band_rows if r.get("mean") is not None]
    b_actual = [r.get("actual_lift_mean", 0) for r in band_rows if r.get("mean") is not None]
    w = 0.35
    xi = np.arange(len(b_labels))
    ax.bar(xi - w/2, b_pred,   w, label="Pred (median)",   color=blue,  alpha=0.8)
    ax.bar(xi + w/2, b_actual, w, label="Actual (median)", color=amber, alpha=0.8)
    ax.axhline(0, color=text, linewidth=0.5, alpha=0.4)
    ax.set_xticks(xi)
    ax.set_xticklabels([l[:14] for l in b_labels], rotation=20, ha="right",
                       color=text, fontsize=8)
    ax.set_ylabel("Median lift %", color=text, fontsize=9)
    ax.set_title("Predicted vs. Actual Median Lift\nby Elasticity Band",
                 color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    ax.legend(facecolor="#12122a", labelcolor=text, fontsize=8)

    verdict_color = green if verdict == "PASS" else red
    fig.suptitle(
        f"MO_70 — Lift Magnitude Validation  |  1,633 clean price events  |  "
        f"Portfolio signed error: {port['mean']:+.0f}%  |  Verdict: {verdict}",
        color=verdict_color, fontsize=10, fontweight="bold", y=1.01,
    )
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Chart saved → {OUT_PNG}")
    print("\nDone.")
