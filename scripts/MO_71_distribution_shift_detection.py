"""MO_71 — Input Distribution Shift Detection (Gap #6).

Audit question: Have the Tier 1 features (TDP, ARP, velocity) drifted structurally
between the training window (end of v3 training data) and the current/validation
period? If so, the model is being asked to predict in a distribution it hasn't
seen — accuracy will degrade silently even if aggregate wMAPE looks stable.

Method
------
1. Load retailer_sales_weekly.parquet; split at v3 train/val cutoff (13w from end).
2. For each feature in the v3 feature set, run a two-sample KS test:
   train distribution vs. val distribution.
3. Material threshold: KS p-value < 0.05 AND KS statistic > 0.05 on any Tier 1 feature.
   (Both conditions required — large samples make p-value hypersensitive to tiny shifts.)
4. Tier 1 features: raw signals directly used by the model: TDP, ARP, velocity SPM,
   and the unit-level rolling averages.
5. Secondary analysis: direction of shift (higher or lower in val vs. train).

Outputs
-------
  outputs/mo71_distribution_shift_scorecard.json  — per-feature KS results + verdict
  outputs/mo71_distribution_shift_chart.png       — 4-panel visualization

Run from the FirstAgent/ directory:
    python scripts/MO_71_distribution_shift_detection.py
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

ROOT       = Path(__file__).parent.parent
PARQUET    = ROOT / "outputs" / "retailer_sales_weekly.parquet"
METRICS_IN = ROOT / "outputs" / "retailer_sales_train_metrics.json"
OUT_JSON   = ROOT / "outputs" / "mo71_distribution_shift_scorecard.json"
OUT_PNG    = ROOT / "outputs" / "mo71_distribution_shift_chart.png"

# Material threshold: KS stat > this AND p < P_THRESHOLD
KS_STAT_THRESHOLD = 0.05
P_THRESHOLD       = 0.05

# Tier 1 features — raw signals, not engineered from the target
TIER1_FEATURES = [
    "tdp", "arp", "velocity_spm_roll13_avg", "velocity_spm_roll8_avg",
    "base_units_roll13_avg", "base_units_roll8_avg",
    "base_units_roll4_avg", "arp_roll8_avg",
    "arp_lag1", "tdp_z8",
]


def shift_direction(train_arr, val_arr):
    """Return 'higher' / 'lower' / 'same' for val relative to train."""
    delta = np.median(val_arr) - np.median(train_arr)
    if abs(delta) < 1e-6:
        return "same"
    return "higher" if delta > 0 else "lower"


if __name__ == "__main__":
    print("=" * 65)
    print("MO_71 — Input Distribution Shift Detection")
    print("=" * 65)

    with open(METRICS_IN) as f:
        meta = json.load(f)
    all_features = meta["features_used"]

    print(f"\nLoading parquet …")
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)

    cutoff = df["__time"].max() - pd.Timedelta(weeks=13)
    train  = df[df["__time"] <= cutoff].copy()
    val    = df[df["__time"] >  cutoff].copy()
    print(f"  Train: {len(train):,} rows  ({train['__time'].min().date()} → {train['__time'].max().date()})")
    print(f"  Val:   {len(val):,} rows  ({val['__time'].min().date()} → {val['__time'].max().date()})")

    # ── KS tests ──────────────────────────────────────────────────────────────
    print(f"\n── KS tests (Tier 1 + all model features) ───────────────────────────")

    results = []
    tier1_flags = []
    all_flags   = []

    features_to_test = list(dict.fromkeys(TIER1_FEATURES + all_features))  # tier1 first, no dups

    for feat in features_to_test:
        if feat not in df.columns or feat == "channel_outlet":
            continue
        t_arr = pd.to_numeric(train[feat], errors="coerce").dropna().values
        v_arr = pd.to_numeric(val[feat],   errors="coerce").dropna().values
        if len(t_arr) < 100 or len(v_arr) < 100:
            continue

        ks_stat, p_val = stats.ks_2samp(t_arr, v_arr)
        direction       = shift_direction(t_arr, v_arr)
        is_tier1        = feat in TIER1_FEATURES
        material        = ks_stat > KS_STAT_THRESHOLD and p_val < P_THRESHOLD

        rec = {
            "feature":   feat,
            "is_tier1":  is_tier1,
            "ks_stat":   round(float(ks_stat), 4),
            "p_value":   round(float(p_val), 4),
            "material":  material,
            "direction": direction,
            "train_median": round(float(np.median(t_arr)), 4),
            "val_median":   round(float(np.median(v_arr)), 4),
            "pct_shift":    round((np.median(v_arr) - np.median(t_arr)) / (abs(np.median(t_arr)) + 1e-6) * 100, 1),
        }
        results.append(rec)

        flag_str = "⚠ MATERIAL" if material else ""
        tier_str = "[T1]" if is_tier1 else "    "
        print(f"  {tier_str} {feat:35s}: KS={ks_stat:.4f}  p={p_val:.4f}  "
              f"shift={rec['pct_shift']:+.1f}% ({direction})  {flag_str}")

        if is_tier1:
            tier1_flags.append(material)
        all_flags.append(material)

    tier1_material = sum(tier1_flags)
    all_material   = sum(all_flags)

    verdict = "FAIL" if tier1_material > 0 else "PASS"
    print(f"\n{'='*65}")
    print(f"VERDICT: {verdict}  (threshold: KS>{KS_STAT_THRESHOLD} AND p<{P_THRESHOLD})")
    print(f"{'='*65}")
    print(f"  Tier 1 features material: {tier1_material}/{len(tier1_flags)}")
    print(f"  All features material:    {all_material}/{len(all_flags)}")

    material_tier1 = [r for r in results if r["is_tier1"] and r["material"]]
    if material_tier1:
        print(f"\n  Material Tier 1 shifts:")
        for r in material_tier1:
            print(f"    {r['feature']:35s}: KS={r['ks_stat']:.4f}  "
                  f"shift {r['pct_shift']:+.1f}% {r['direction']}  "
                  f"(train median={r['train_median']:.3f} → val median={r['val_median']:.3f})")

    # ── Scorecard ─────────────────────────────────────────────────────────────
    scorecard = {
        "verdict":              verdict,
        "ks_stat_threshold":    KS_STAT_THRESHOLD,
        "p_threshold":          P_THRESHOLD,
        "train_rows":           int(len(train)),
        "val_rows":             int(len(val)),
        "train_date_range":     f"{train['__time'].min().date()} → {train['__time'].max().date()}",
        "val_date_range":       f"{val['__time'].min().date()} → {val['__time'].max().date()}",
        "tier1_features_tested": len(tier1_flags),
        "tier1_material":       int(tier1_material),
        "all_features_tested":  len(all_flags),
        "all_material":         int(all_material),
        "results":              results,
    }

    def json_safe(obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj) if np.isfinite(obj) else None
        if isinstance(obj, np.bool_):
            return bool(obj)
        raise TypeError(f"Not serializable: {type(obj)}")

    # Sanitize pct_shift values (division by near-zero can produce huge numbers)
    for r in results:
        if r.get("pct_shift") is not None and abs(r["pct_shift"]) > 10000:
            r["pct_shift"] = None  # suppress infinite-looking values

    with open(OUT_JSON, "w") as f:
        json.dump(scorecard, f, indent=2, default=json_safe)
    print(f"\n  Scorecard → {OUT_JSON}")

    # ── Charts ─────────────────────────────────────────────────────────────────
    print("\n── Generating chart ──────────────────────────────────────────────────")
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.patch.set_facecolor("#1a1a2e")

    blue, green, red, amber, text, grid_c = (
        "#4a9eda", "#2ecc71", "#e74c3c", "#f39c12", "#e0e0e0", "#2a2a4a"
    )

    # Panel 1: KS stat by feature (Tier 1 only, sorted)
    ax = axes[0, 0]
    ax.set_facecolor("#12122a")
    t1 = [r for r in results if r["is_tier1"] and r.get("ks_stat") is not None]
    t1 = sorted(t1, key=lambda x: x["ks_stat"], reverse=True)
    y = range(len(t1))
    colors_t1 = [red if r["material"] else blue for r in t1]
    ax.barh(list(y), [r["ks_stat"] for r in t1], color=colors_t1, alpha=0.85)
    ax.axvline(KS_STAT_THRESHOLD, color=red, linewidth=1.2, linestyle="--",
               label=f"KS threshold {KS_STAT_THRESHOLD}")
    ax.set_yticks(list(y))
    ax.set_yticklabels([r["feature"][:28] for r in t1], color=text, fontsize=8)
    ax.set_xlabel("KS statistic", color=text, fontsize=9)
    ax.set_title("KS Statistic — Tier 1 Features\n(train vs. val distribution)",
                 color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    ax.legend(facecolor="#12122a", labelcolor=text, fontsize=8)
    for i, r in enumerate(t1):
        c = red if r["material"] else text
        ax.text(r["ks_stat"] + 0.002, i, f"{r['pct_shift']:+.1f}%", va="center",
                color=c, fontsize=7)

    # Panel 2: % shift (val median / train median − 1) for Tier 1
    ax = axes[0, 1]
    ax.set_facecolor("#12122a")
    t1_pct = sorted(t1, key=lambda x: x["pct_shift"])
    y2 = range(len(t1_pct))
    colors_pct = [red if r["material"] else (amber if abs(r["pct_shift"]) > 10 else blue)
                  for r in t1_pct]
    ax.barh(list(y2), [r["pct_shift"] for r in t1_pct], color=colors_pct, alpha=0.85)
    ax.axvline(0, color=text, linewidth=0.8, alpha=0.5)
    ax.axvline(10,  color=amber, linewidth=1, linestyle=":", alpha=0.6)
    ax.axvline(-10, color=amber, linewidth=1, linestyle=":", alpha=0.6, label="±10% shift")
    ax.set_yticks(list(y2))
    ax.set_yticklabels([r["feature"][:28] for r in t1_pct], color=text, fontsize=8)
    ax.set_xlabel("% shift in median (val vs. train)", color=text, fontsize=9)
    ax.set_title("Median Shift — Tier 1 Features\n(val − train) / |train|",
                 color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    ax.legend(facecolor="#12122a", labelcolor=text, fontsize=8)

    # Panel 3: TDP distribution (train vs val)
    ax = axes[1, 0]
    ax.set_facecolor("#12122a")
    tdp_t = pd.to_numeric(train["tdp"], errors="coerce").dropna().clip(0, 500)
    tdp_v = pd.to_numeric(val["tdp"],   errors="coerce").dropna().clip(0, 500)
    ax.hist(tdp_t, bins=60, alpha=0.6, color=blue,  label=f"Train (n={len(tdp_t):,})",
            density=True, edgecolor="none")
    ax.hist(tdp_v, bins=60, alpha=0.6, color=amber, label=f"Val   (n={len(tdp_v):,})",
            density=True, edgecolor="none")
    tdp_rec = next((r for r in results if r["feature"] == "tdp"), {})
    ax.set_xlabel("TDP (total distribution points)", color=text, fontsize=9)
    ax.set_ylabel("Density", color=text, fontsize=9)
    ax.set_title(f"TDP Distribution: Train vs. Val\n"
                 f"KS={tdp_rec.get('ks_stat', '?'):.4f}  "
                 f"shift={tdp_rec.get('pct_shift', 0):+.1f}%  "
                 f"{'⚠ MATERIAL' if tdp_rec.get('material') else 'OK'}",
                 color=red if tdp_rec.get("material") else text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    ax.legend(facecolor="#12122a", labelcolor=text, fontsize=8)

    # Panel 4: ARP distribution (train vs val)
    ax = axes[1, 1]
    ax.set_facecolor("#12122a")
    arp_t = pd.to_numeric(train["arp"], errors="coerce").dropna().clip(0, 10)
    arp_v = pd.to_numeric(val["arp"],   errors="coerce").dropna().clip(0, 10)
    ax.hist(arp_t, bins=60, alpha=0.6, color=blue,  label=f"Train (n={len(arp_t):,})",
            density=True, edgecolor="none")
    ax.hist(arp_v, bins=60, alpha=0.6, color=amber, label=f"Val   (n={len(arp_v):,})",
            density=True, edgecolor="none")
    arp_rec = next((r for r in results if r["feature"] == "arp"), {})
    ax.set_xlabel("ARP (average retail price)", color=text, fontsize=9)
    ax.set_ylabel("Density", color=text, fontsize=9)
    ax.set_title(f"ARP Distribution: Train vs. Val\n"
                 f"KS={arp_rec.get('ks_stat', '?'):.4f}  "
                 f"shift={arp_rec.get('pct_shift', 0):+.1f}%  "
                 f"{'⚠ MATERIAL' if arp_rec.get('material') else 'OK'}",
                 color=red if arp_rec.get("material") else text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    ax.legend(facecolor="#12122a", labelcolor=text, fontsize=8)

    verdict_color = green if verdict == "PASS" else red
    fig.suptitle(
        f"MO_71 — Distribution Shift Detection  |  "
        f"Tier 1 material: {tier1_material}/{len(tier1_flags)}  |  Verdict: {verdict}",
        color=verdict_color, fontsize=11, fontweight="bold", y=1.01,
    )
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Chart saved → {OUT_PNG}")
    print("\nDone.")
