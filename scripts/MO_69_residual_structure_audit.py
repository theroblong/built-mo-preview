"""MO_69 — Residual Structure Analysis (Gap #7).

Audit question: Are the v3 q50 forecast errors (residuals) random, or do they
cluster systematically by retailer, maturity bucket, quarter, or promo week?
Systematic bias is more dangerous than random error — it won't show up in
aggregate wMAPE but will consistently push planning decisions in one direction.

Method
------
1. Load v3 val set (Jan–Apr 2026, same split as MO_67/68).
2. Generate q50 predictions; compute residual = actual − pred and bias_pct = residual / actual.
3. Segment cuts: retail_account, maturity bucket, week_of_year (quarter proxy),
   promo flag (units_promo > 0), retailer_tier, pack_format.
4. For each segment, test mean bias_pct against zero using a one-sample t-test.
5. Material threshold: |mean_bias_pct| > ±5% AND t-test p < 0.05.
6. Also report: % of rows with positive residual (are we systematically under-forecasting?).

Outputs
-------
  outputs/mo69_residual_scorecard.json      — per-segment bias results + verdict
  outputs/mo69_residual_chart.png           — 4-panel visualization
  outputs/mo69_biased_segments.csv          — segments exceeding threshold

Run from the FirstAgent/ directory:
    python scripts/MO_69_residual_structure_audit.py
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
from scipy import stats

warnings.filterwarnings("ignore")

ROOT        = Path(__file__).parent.parent
PARQUET     = ROOT / "outputs" / "retailer_sales_weekly.parquet"
METRICS_IN  = ROOT / "outputs" / "retailer_sales_train_metrics.json"
MODEL_DIR   = ROOT / "outputs"
OUT_JSON    = ROOT / "outputs" / "mo69_residual_scorecard.json"
OUT_PNG     = ROOT / "outputs" / "mo69_residual_chart.png"
OUT_CSV     = ROOT / "outputs" / "mo69_biased_segments.csv"

GROUP_COLS  = ["upc", "channel_outlet", "retail_account", "geography_raw"]

BIAS_THRESHOLD_PCT = 5.0   # |mean bias %| above this → material
P_THRESHOLD        = 0.05  # t-test significance


def load_model(tag="q50", version="v3"):
    p = MODEL_DIR / f"model_retailer_sales_{tag}_{version}.pkl"
    with open(p, "rb") as f:
        return pickle.load(f)


def build_val(df, feature_cols):
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


def pack_format(pc):
    try:
        pc = int(pc)
    except (TypeError, ValueError):
        return "Single (1ct)"
    if pc == 1:
        return "Single (1ct)"
    elif pc <= 12:
        return "Multipack (2-12ct)"
    else:
        return "Bulk (13ct+)"


def maturity_label(w):
    if w < 13:
        return "New (<13w)"
    elif w < 52:
        return "Growing (13–51w)"
    else:
        return "Mature (52w+)"


def quarter_label(woy):
    if woy <= 13:
        return "Q1"
    elif woy <= 26:
        return "Q2"
    elif woy <= 39:
        return "Q3"
    else:
        return "Q4"


def test_segment(bias_pct_arr):
    """Return (mean_bias_pct, t_stat, p_value, n, pct_positive)."""
    n = len(bias_pct_arr)
    if n < 5:
        return np.nan, np.nan, np.nan, n, np.nan
    mean_b = float(np.mean(bias_pct_arr))
    t_stat, p_val = stats.ttest_1samp(bias_pct_arr, 0.0)
    pct_pos = float(np.mean(bias_pct_arr > 0) * 100)
    return mean_b, float(t_stat), float(p_val), n, pct_pos


def audit_cut(val, cut_col, label=""):
    """Return DataFrame with bias stats per level of cut_col."""
    rows = []
    for level, grp in val.groupby(cut_col):
        mean_b, t_stat, p_val, n, pct_pos = test_segment(grp["bias_pct"].values)
        material = (abs(mean_b) > BIAS_THRESHOLD_PCT and p_val < P_THRESHOLD
                    if not np.isnan(mean_b) else False)
        rows.append({
            "cut": label or cut_col,
            "level": str(level),
            "n": n,
            "mean_bias_pct": round(mean_b, 2) if not np.isnan(mean_b) else None,
            "t_stat": round(t_stat, 3) if not np.isnan(t_stat) else None,
            "p_value": round(p_val, 4) if not np.isnan(p_val) else None,
            "pct_positive_residual": round(pct_pos, 1) if not np.isnan(pct_pos) else None,
            "material": material,
        })
    return pd.DataFrame(rows)


# ── main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("MO_69 — Residual Structure Audit")
    print("=" * 65)

    with open(METRICS_IN) as f:
        feature_cols = json.load(f)["features_used"]

    print("\nLoading v3 q50 model …")
    model = load_model("q50", "v3")

    print("Loading parquet and building val set …")
    df = pd.read_parquet(PARQUET)
    val, cutoff = build_val(df, feature_cols)
    print(f"  Val rows: {len(val):,}  ({val['__time'].min().date()} → {val['__time'].max().date()})")

    # ── Predictions and residuals ──────────────────────────────────────────────
    available = [c for c in feature_cols if c in val.columns]
    pred_log  = model.predict(val[available])
    val = val.copy()
    val["pred_units"] = np.expm1(np.clip(pred_log, 0, None))
    val["residual"]   = val["base_units"] - val["pred_units"]

    # bias_pct = residual / actual; exclude zero-actual rows (undefined)
    nonzero = val["base_units"] > 0
    val.loc[nonzero, "bias_pct"] = val.loc[nonzero, "residual"] / val.loc[nonzero, "base_units"] * 100
    val_nz = val[nonzero].copy()  # analysis on non-zero actual rows only

    # ── Derived segment columns ────────────────────────────────────────────────
    val_nz["maturity"]    = val_nz["weeks_since_launch"].apply(maturity_label)
    val_nz["quarter"]     = val_nz["week_of_year"].apply(quarter_label)
    val_nz["pack_format"] = val_nz["pack_count"].apply(pack_format)
    val_nz["is_promo"]    = (val_nz["units_promo"] > 0).map({True: "Promo week", False: "Non-promo"})

    print(f"  Non-zero actual rows (used for bias): {len(val_nz):,}")

    # ── Portfolio-level ────────────────────────────────────────────────────────
    port_mean = float(val_nz["bias_pct"].mean())
    port_t, port_p = stats.ttest_1samp(val_nz["bias_pct"].values, 0.0)
    port_pct_pos = float((val_nz["bias_pct"] > 0).mean() * 100)
    print(f"\n── Portfolio bias ────────────────────────────────────────────────────")
    print(f"  Mean bias: {port_mean:+.2f}%   p={port_p:.4f}   "
          f"% positive residual: {port_pct_pos:.1f}%")
    port_material = abs(port_mean) > BIAS_THRESHOLD_PCT and port_p < P_THRESHOLD

    # ── Segment cuts ──────────────────────────────────────────────────────────
    cuts = {
        "Retailer":     audit_cut(val_nz, "retail_account", "Retailer"),
        "Maturity":     audit_cut(val_nz, "maturity",       "Maturity"),
        "Quarter":      audit_cut(val_nz, "quarter",        "Quarter"),
        "Promo flag":   audit_cut(val_nz, "is_promo",       "Promo flag"),
        "Pack format":  audit_cut(val_nz, "pack_format",    "Pack format"),
    }

    all_results = pd.concat(cuts.values(), ignore_index=True)
    biased = all_results[all_results["material"] == True].copy()

    print(f"\n── Segment bias summary ──────────────────────────────────────────────")
    for cut_name, df_cut in cuts.items():
        mat_count = df_cut["material"].sum()
        flag = "  ⚠ " if mat_count else "  ✓ "
        print(f"{flag}{cut_name}: {mat_count}/{len(df_cut)} segments material")
        for _, row in df_cut[df_cut["material"]].iterrows():
            print(f"      {row['level']:35s}  bias={row['mean_bias_pct']:+.1f}%  "
                  f"p={row['p_value']:.4f}  n={row['n']:,}")

    any_fail = port_material or len(biased) > 0
    verdict  = "FAIL" if any_fail else "PASS"
    print(f"\n{'='*65}")
    print(f"VERDICT: {verdict}  (material threshold: |bias| > ±{BIAS_THRESHOLD_PCT}%, p < {P_THRESHOLD})")
    print(f"{'='*65}")
    print(f"  Portfolio: mean bias {port_mean:+.2f}%  {'MATERIAL' if port_material else 'OK'}")
    print(f"  Biased segments: {len(biased)}")

    # ── Save CSV ───────────────────────────────────────────────────────────────
    if len(biased) > 0:
        biased.to_csv(OUT_CSV, index=False)
        print(f"\n  Biased segments CSV → {OUT_CSV}")

    # ── Scorecard ──────────────────────────────────────────────────────────────
    def df_to_list(df_cut):
        return df_cut.to_dict(orient="records")

    scorecard = {
        "verdict":         verdict,
        "bias_threshold_pct": BIAS_THRESHOLD_PCT,
        "p_threshold":     P_THRESHOLD,
        "val_rows":        int(len(val)),
        "nonzero_rows":    int(len(val_nz)),
        "portfolio": {
            "mean_bias_pct":       round(port_mean, 2),
            "p_value":             round(float(port_p), 4),
            "pct_positive_residual": round(port_pct_pos, 1),
            "material":            port_material,
        },
        "cuts":            {k: df_to_list(v) for k, v in cuts.items()},
        "biased_segments": len(biased),
    }

    with open(OUT_JSON, "w") as f:
        json.dump(scorecard, f, indent=2)
    print(f"\n  Scorecard → {OUT_JSON}")

    # ── Charts ─────────────────────────────────────────────────────────────────
    print("\n── Generating chart ──────────────────────────────────────────────────")
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.patch.set_facecolor("#1a1a2e")

    blue, green, red, amber, text, grid_c, orange = (
        "#4a9eda", "#2ecc71", "#e74c3c", "#f39c12", "#e0e0e0", "#2a2a4a", "#e67e22"
    )

    def bar_color(bias):
        if abs(bias) > BIAS_THRESHOLD_PCT:
            return red
        elif abs(bias) > 2.5:
            return amber
        return blue

    # Panel 1: Bias by retailer (top 15 by |bias|, min 50 rows)
    ax = axes[0, 0]
    ax.set_facecolor("#12122a")
    ret_df = cuts["Retailer"]
    ret_df = ret_df[ret_df["n"] >= 50].copy()
    ret_df["abs_bias"] = ret_df["mean_bias_pct"].abs()
    ret_df = ret_df.nlargest(15, "abs_bias")
    ret_df = ret_df.sort_values("mean_bias_pct")
    y = range(len(ret_df))
    colors_ret = [bar_color(b) for b in ret_df["mean_bias_pct"]]
    ax.barh(list(y), ret_df["mean_bias_pct"].tolist(), color=colors_ret, alpha=0.85)
    ax.axvline(0, color=text, linewidth=0.8, alpha=0.5)
    ax.axvline(BIAS_THRESHOLD_PCT, color=red, linewidth=1, linestyle="--", alpha=0.6)
    ax.axvline(-BIAS_THRESHOLD_PCT, color=red, linewidth=1, linestyle="--", alpha=0.6)
    ax.set_yticks(list(y))
    ax.set_yticklabels([r[:18] for r in ret_df["level"]], color=text, fontsize=7)
    ax.set_xlabel("Mean bias % (actual − pred) / actual", color=text, fontsize=8)
    ax.set_title("Retailer-level Bias\n(top 15 by |bias|, n≥50)", color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    # Annotate material ones
    for i, (_, row) in enumerate(ret_df.iterrows()):
        if row["material"]:
            ax.text(row["mean_bias_pct"] + 0.3, i, f"{row['mean_bias_pct']:+.1f}%*",
                    va="center", color=red, fontsize=7, fontweight="bold")

    # Panel 2: Bias by maturity bucket
    ax = axes[0, 1]
    ax.set_facecolor("#12122a")
    mat_df = cuts["Maturity"].sort_values("mean_bias_pct")
    y = range(len(mat_df))
    colors_mat = [bar_color(b) for b in mat_df["mean_bias_pct"]]
    bars = ax.barh(list(y), mat_df["mean_bias_pct"].tolist(), color=colors_mat, alpha=0.85)
    ax.axvline(0, color=text, linewidth=0.8, alpha=0.5)
    ax.axvline(BIAS_THRESHOLD_PCT, color=red, linewidth=1, linestyle="--", alpha=0.6)
    ax.axvline(-BIAS_THRESHOLD_PCT, color=red, linewidth=1, linestyle="--", alpha=0.6)
    ax.set_yticks(list(y))
    ax.set_yticklabels(mat_df["level"].tolist(), color=text, fontsize=9)
    ax.set_xlabel("Mean bias %", color=text, fontsize=8)
    ax.set_title("Bias by Maturity Bucket", color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    for i, (_, row) in enumerate(mat_df.iterrows()):
        ax.text(row["mean_bias_pct"] + 0.2 if row["mean_bias_pct"] >= 0 else row["mean_bias_pct"] - 0.2,
                i, f"{row['mean_bias_pct']:+.1f}%  n={row['n']:,}",
                va="center", ha="left" if row["mean_bias_pct"] >= 0 else "right",
                color=text, fontsize=8)

    # Panel 3: Bias by pack format + promo flag (grouped)
    ax = axes[1, 0]
    ax.set_facecolor("#12122a")
    pack_df = cuts["Pack format"]
    promo_df = cuts["Promo flag"]
    combined = pd.concat([pack_df, promo_df], ignore_index=True).sort_values("mean_bias_pct")
    y = range(len(combined))
    colors_comb = [bar_color(b) for b in combined["mean_bias_pct"]]
    ax.barh(list(y), combined["mean_bias_pct"].tolist(), color=colors_comb, alpha=0.85)
    ax.axvline(0, color=text, linewidth=0.8, alpha=0.5)
    ax.axvline(BIAS_THRESHOLD_PCT, color=red, linewidth=1, linestyle="--", alpha=0.6)
    ax.axvline(-BIAS_THRESHOLD_PCT, color=red, linewidth=1, linestyle="--", alpha=0.6)
    ax.set_yticks(list(y))
    ax.set_yticklabels(combined["level"].tolist(), color=text, fontsize=9)
    ax.set_xlabel("Mean bias %", color=text, fontsize=8)
    ax.set_title("Bias by Pack Format + Promo Flag", color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    for i, (_, row) in enumerate(combined.iterrows()):
        label_x = row["mean_bias_pct"] + 0.2 if row["mean_bias_pct"] >= 0 else row["mean_bias_pct"] - 0.2
        ax.text(label_x, i, f"{row['mean_bias_pct']:+.1f}%  n={row['n']:,}",
                va="center", ha="left" if row["mean_bias_pct"] >= 0 else "right",
                color=text, fontsize=8)

    # Panel 4: Residual distribution (histogram)
    ax = axes[1, 1]
    ax.set_facecolor("#12122a")
    bias_vals = val_nz["bias_pct"].values
    clip_lo, clip_hi = np.percentile(bias_vals, [1, 99])
    bias_clipped = np.clip(bias_vals, clip_lo, clip_hi)
    ax.hist(bias_clipped, bins=80, color=blue, alpha=0.75, edgecolor="none")
    ax.axvline(0, color=amber, linewidth=1.5, linestyle="--", label="Zero bias")
    ax.axvline(port_mean, color=green if abs(port_mean) <= BIAS_THRESHOLD_PCT else red,
               linewidth=2, linestyle="-",
               label=f"Mean {port_mean:+.2f}% ({'OK' if not port_material else 'MATERIAL'})")
    ax.axvline(BIAS_THRESHOLD_PCT, color=red, linewidth=0.8, linestyle=":", alpha=0.6)
    ax.axvline(-BIAS_THRESHOLD_PCT, color=red, linewidth=0.8, linestyle=":", alpha=0.6)
    ax.set_xlabel("Bias % per row (actual − pred) / actual", color=text, fontsize=8)
    ax.set_ylabel("Count", color=text, fontsize=8)
    ax.set_title("Residual Distribution (1st–99th pct clipped)", color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    ax.legend(facecolor="#12122a", labelcolor=text, fontsize=8)
    ax.text(0.98, 0.97, f"{port_pct_pos:.1f}% rows: actual > pred\n(under-forecast)",
            transform=ax.transAxes, color=text, fontsize=8, ha="right", va="top")

    verdict_color = green if verdict == "PASS" else red
    fig.suptitle(
        f"MO_69 — Residual Structure Audit  |  {len(biased)} biased segments  |  Verdict: {verdict}",
        color=verdict_color, fontsize=11, fontweight="bold", y=1.01,
    )
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Chart saved → {OUT_PNG}")
    print("\nDone.")
