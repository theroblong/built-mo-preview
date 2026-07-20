"""MO_68 — Per-Series Accuracy Drift Detection (Gap #1).

Audit question: Are specific retail_account × maturity × pack_format segments
consistently drifting harder to forecast even as overall portfolio accuracy
improves? A gap here means MO_63's portfolio headline wMAPE masks degradation
in specific sub-populations.

Method
------
1. Load scripts/outputs/mo63_rolling_cv_per_series.csv (6 cutpoints, segment level).
2. Compute portfolio median wMAPE per cutpoint (reference baseline).
3. Compute relative ratio = segment_wMAPE / portfolio_median at same cutpoint.
4. For each segment with ≥3 cutpoints: detect drift.
   Drift criterion: relative ratio ≥2.0 in at least 2 of the most recent 3 cutpoints
   AND final cutpoint relative ratio ≥2.0.
5. Add v3 Jan–Apr 2026 as 7th cutpoint (UPC-level predictions → aggregate to segment).
6. Report: drifting segments, magnitude, directional trend.
7. Material threshold: FAIL if any segment meets drift criterion in final cutpoint.

Outputs
-------
  outputs/mo68_drift_scorecard.json     — per-segment classification + verdict
  outputs/mo68_drift_chart.png          — 3-panel visualization
  outputs/mo68_drifting_segments.csv    — flagged segments with details

Run from the FirstAgent/ directory:
    python scripts/MO_68_per_series_drift_detection.py
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
ROLLING_CSV = ROOT / "scripts" / "outputs" / "mo63_rolling_cv_per_series.csv"
PARQUET     = ROOT / "outputs" / "retailer_sales_weekly.parquet"
METRICS_IN  = ROOT / "outputs" / "retailer_sales_train_metrics.json"
MODEL_DIR   = ROOT / "outputs"
OUT_JSON    = ROOT / "outputs" / "mo68_drift_scorecard.json"
OUT_PNG     = ROOT / "outputs" / "mo68_drift_chart.png"
OUT_CSV     = ROOT / "outputs" / "mo68_drifting_segments.csv"

CUTPOINT_ORDER = ["Sep 2024", "Dec 2024", "Mar 2025", "Jun 2025", "Sep 2025", "Dec 2025"]
SEG_COLS       = ["retail_account", "maturity", "pack_format"]
GROUP_COLS     = ["upc", "channel_outlet", "retail_account", "geography_raw"]

DRIFT_RATIO_THRESHOLD = 2.0   # relative ratio ≥ this = "hard to forecast"
DRIFT_MIN_CUTPOINTS   = 2     # must exceed threshold in this many of last 3 cutpoints
DRIFT_SLOPE_THRESHOLD = 0.15  # linear slope of rel-ratio over MO_63 cutpoints
DRIFT_P_THRESHOLD     = 0.10  # p-value for slope significance


# ── helpers ────────────────────────────────────────────────────────────────────

def seg_key(row):
    return f"{row['retail_account']}|{row['maturity']}|{row['pack_format']}"


def load_v3_models():
    models = {}
    for tag in ["q50"]:   # median only needed for wMAPE
        p = MODEL_DIR / f"model_retailer_sales_{tag}_v3.pkl"
        if not p.exists():
            return None
        with open(p, "rb") as f:
            models[tag] = pickle.load(f)
    return models


def pack_count_to_format(pc):
    """Map numeric pack_count to MO_63 pack_format labels."""
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


def build_val_segment_wmape(models, feature_cols):
    """Compute wMAPE on v3 val set (Jan–Apr 2026) aggregated to SEG_COLS granularity."""
    if models is None:
        print("  [skip] v3 models not found — using 6-cutpoint MO_63 data only")
        return None

    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    for c in feature_cols:
        if c != "channel_outlet" and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "channel_outlet" in df.columns:
        df["channel_outlet"] = df["channel_outlet"].astype("category")
    df = df.dropna(subset=["base_units"]).copy()

    cutoff = df["__time"].max() - pd.Timedelta(weeks=13)
    val = df[df["__time"] > cutoff].copy()
    print(f"  v3 val: {len(val):,} rows  ({val['__time'].min().date()} → {val['__time'].max().date()})")

    available = [c for c in feature_cols if c in val.columns]
    pred_log  = models["q50"].predict(val[available])
    val["pred_units"] = np.expm1(np.clip(pred_log, 0, None))
    val["abs_err"]    = (val["base_units"] - val["pred_units"]).abs()

    # Maturity labels matching MO_63: Growing (27-78w), Mature (>78w)
    # Series with <27w are excluded (not present in MO_63 rolling CV)
    val["maturity"] = pd.cut(
        val["weeks_since_launch"],
        bins=[26, 78, 9999],
        labels=["Growing (27-78w)", "Mature (>78w)"],
    ).astype(str)
    val = val[val["maturity"].isin(["Growing (27-78w)", "Mature (>78w)"])].copy()

    # Pack format matching MO_63 labels
    val["pack_format"] = val["pack_count"].apply(pack_count_to_format)

    # Aggregate to SEG_COLS
    grp = val.groupby(SEG_COLS)

    def wmape_agg(g):
        denom = g["base_units"].sum()
        return pd.Series({
            "wmape": g["abs_err"].sum() / denom * 100 if denom > 0 else np.nan,
            "test_units": g["base_units"].sum(),
            "n_test_rows": len(g),
        })

    seg_metrics = grp.apply(wmape_agg, include_groups=False).reset_index()
    seg_metrics["cutpoint"] = "Jan 2026"   # 7th point label
    seg_metrics = seg_metrics.dropna(subset=["wmape"])
    print(f"  v3 segments (Jan 2026 cutpoint): {len(seg_metrics)}")
    return seg_metrics


def detect_drift(series_wm, portfolio_med_by_cp, mo63_cps_only=True):
    """
    series_wm : dict {cutpoint -> wmape}
    Returns: rel_ratios (dict), is_drifting (bool), drift_score (float), slope (float)

    Primary criterion (MO_63 cutpoints only):
      slope > DRIFT_SLOPE_THRESHOLD AND p < DRIFT_P_THRESHOLD AND final_rr > 1.5

    Fallback criterion (all cutpoints including Jan 2026):
      ≥2 of last 3 cutpoints above DRIFT_RATIO_THRESHOLD AND final above threshold

    Explicitly NOT drifting if MO_63 slope is negative (segment improving).
    """
    # Build relative ratios for all cutpoints
    all_present = [c for c in CUTPOINT_ORDER + ["Jan 2026"] if c in series_wm]
    rel_ratios = {}
    for cp in all_present:
        pm = portfolio_med_by_cp.get(cp, np.nan)
        if pm > 0 and not np.isnan(pm):
            rel_ratios[cp] = series_wm[cp] / pm

    if len(rel_ratios) < 3:
        return rel_ratios, False, 0.0, 0.0

    # ── Primary: slope-based on MO_63 cutpoints only ──────────────────────────
    mo63_rr = [(cp, rel_ratios[cp]) for cp in CUTPOINT_ORDER if cp in rel_ratios]
    slope, pvalue = 0.0, 1.0
    slope_drift = False
    if len(mo63_rr) >= 4:
        xi = [CUTPOINT_ORDER.index(cp) for cp, _ in mo63_rr]
        yi = [rr for _, rr in mo63_rr]
        if len(set(xi)) >= 2:
            res = stats.linregress(xi, yi)
            slope, pvalue = float(res.slope), float(res.pvalue)
            final_mo63_rr = yi[-1]
            slope_drift = (slope > DRIFT_SLOPE_THRESHOLD
                           and pvalue < DRIFT_P_THRESHOLD
                           and final_mo63_rr > 1.5)

    # ── Fallback: threshold-based (all cutpoints) ─────────────────────────────
    last3 = list(rel_ratios.items())[-3:]
    above_threshold = sum(1 for _, r in last3 if r >= DRIFT_RATIO_THRESHOLD)
    final_above = list(rel_ratios.values())[-1] >= DRIFT_RATIO_THRESHOLD
    # Only trigger fallback if MO_63 slope is NOT strongly negative (improving)
    threshold_drift = (above_threshold >= DRIFT_MIN_CUTPOINTS
                       and final_above
                       and slope >= -0.5)   # exclude strongly improving segments

    is_drifting = slope_drift or threshold_drift
    drift_score = float(np.mean([r for _, r in last3]))
    return rel_ratios, is_drifting, drift_score, slope


# ── main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("MO_68 — Per-Series Accuracy Drift Detection")
    print("=" * 65)

    # ── 1. Load MO_63 rolling CV data ─────────────────────────────────────────
    print("\n── Loading MO_63 rolling CV per-series data ─────────────────────────")
    df63 = pd.read_csv(ROLLING_CSV)
    df63["seg"] = df63.apply(seg_key, axis=1)
    print(f"  Rows: {len(df63):,}  |  Cutpoints: {sorted(df63['cutpoint'].unique())}")
    print(f"  Unique segments: {df63['seg'].nunique()}")

    # ── 2. Maturity labels: keep as-is (MO_63 uses long form) ───────────────────
    # MO_63: 'Growing (27-78w)', 'Mature (>78w)' — already in correct form

    # ── 3. Load v3 models and build 7th cutpoint ──────────────────────────────
    print("\n── Building v3 Jan–Apr 2026 segment-level wMAPE (7th cutpoint) ───────")
    with open(METRICS_IN) as f:
        feature_cols = json.load(f)["features_used"]
    models = load_v3_models()
    df_v3 = build_val_segment_wmape(models, feature_cols)

    # Merge 7th cutpoint into main df
    if df_v3 is not None:
        df_v3["seg"] = df_v3.apply(seg_key, axis=1)
        all_cps = CUTPOINT_ORDER + ["Jan 2026"]
        df_all = pd.concat([
            df63[["seg", "cutpoint", "wmape", "test_units", "n_test_rows"] + SEG_COLS],
            df_v3[["seg", "cutpoint", "wmape", "test_units", "n_test_rows"] + SEG_COLS],
        ], ignore_index=True)
    else:
        all_cps = CUTPOINT_ORDER
        df_all = df63[["seg", "cutpoint", "wmape", "test_units", "n_test_rows"] + SEG_COLS].copy()

    # ── 4. Portfolio median per cutpoint ──────────────────────────────────────
    print("\n── Portfolio median wMAPE per cutpoint ──────────────────────────────")
    portfolio_med = {}
    for cp in all_cps:
        sub = df_all[df_all["cutpoint"] == cp]
        if len(sub) > 0:
            med = sub["wmape"].median()
            portfolio_med[cp] = med
            print(f"  {cp:10s}: median={med:.3f}%  n={len(sub)}")

    # ── 5. Per-segment drift analysis ─────────────────────────────────────────
    print("\n── Per-segment drift analysis ────────────────────────────────────────")
    seg_results = []
    all_segs = df_all["seg"].unique()

    drifting_segs = []
    for seg in all_segs:
        sub = df_all[df_all["seg"] == seg].sort_values(
            "cutpoint",
            key=lambda s: s.map({cp: i for i, cp in enumerate(all_cps)})
        )
        series_wm = dict(zip(sub["cutpoint"], sub["wmape"]))
        rel_ratios, is_drifting, drift_score, slope = detect_drift(series_wm, portfolio_med)

        row = sub.iloc[0]
        rec = {
            "seg": seg,
            "retail_account": row.get("retail_account", ""),
            "maturity":       row.get("maturity", ""),
            "pack_format":    row.get("pack_format", ""),
            "n_cutpoints":    len(series_wm),
            "wmape_by_cutpoint": series_wm,
            "rel_ratio_by_cutpoint": {k: round(v, 3) for k, v in rel_ratios.items()},
            "is_drifting":   is_drifting,
            "drift_score":   round(drift_score, 3),
            "slope":         round(slope, 4),
            "final_wmape":   series_wm.get(all_cps[-1] if all_cps[-1] in series_wm
                                           else list(series_wm.keys())[-1], np.nan),
        }
        seg_results.append(rec)
        if is_drifting:
            drifting_segs.append(rec)

    drifting_segs.sort(key=lambda x: x["drift_score"], reverse=True)
    print(f"  Total segments evaluated: {len(seg_results)}")
    print(f"  Drifting segments (score ≥{DRIFT_RATIO_THRESHOLD}× in 2+ of last 3 cutpoints): "
          f"{len(drifting_segs)}")

    if drifting_segs:
        print("\n  Top drifting segments:")
        for d in drifting_segs[:10]:
            final_cp = list(d["rel_ratio_by_cutpoint"].keys())[-1]
            print(f"    {d['seg'][:55]:55s}  "
                  f"drift_score={d['drift_score']:.2f}×  "
                  f"final_wMAPE={d['final_wmape']:.1f}%")

    verdict = "FAIL" if drifting_segs else "PASS"

    # ── 6. Save drifting segments CSV ─────────────────────────────────────────
    if drifting_segs:
        csv_rows = []
        for d in drifting_segs:
            base = {k: v for k, v in d.items()
                    if k not in ("wmape_by_cutpoint", "rel_ratio_by_cutpoint", "seg")}
            for cp in all_cps:
                base[f"wmape_{cp.replace(' ', '_')}"] = d["wmape_by_cutpoint"].get(cp, np.nan)
                base[f"rr_{cp.replace(' ', '_')}"] = d["rel_ratio_by_cutpoint"].get(cp, np.nan)
            csv_rows.append(base)
        pd.DataFrame(csv_rows).to_csv(OUT_CSV, index=False)
        print(f"\n  Drifting segments CSV → {OUT_CSV}")

    # ── 7. Scorecard ──────────────────────────────────────────────────────────
    scorecard = {
        "verdict": verdict,
        "total_segments": len(seg_results),
        "segments_evaluated_min3_cutpoints": sum(
            1 for r in seg_results if r["n_cutpoints"] >= 3
        ),
        "drifting_segments": len(drifting_segs),
        "drift_threshold": {
            "relative_ratio": DRIFT_RATIO_THRESHOLD,
            "min_cutpoints":  DRIFT_MIN_CUTPOINTS,
        },
        "portfolio_median_by_cutpoint": {k: round(v, 4) for k, v in portfolio_med.items()},
        "top_drifting_segments": [
            {
                "seg": d["seg"],
                "retail_account": d["retail_account"],
                "maturity":       d["maturity"],
                "pack_format":    d["pack_format"],
                "drift_score":    d["drift_score"],
                "slope":          d["slope"],
                "final_wmape_pct": round(d["final_wmape"], 2),
                "rel_ratios":     d["rel_ratio_by_cutpoint"],
            }
            for d in drifting_segs[:15]
        ],
    }

    with open(OUT_JSON, "w") as f:
        json.dump(scorecard, f, indent=2)
    print(f"\n  Scorecard → {OUT_JSON}")

    # ── 8. Charts ─────────────────────────────────────────────────────────────
    print("\n── Generating chart ──────────────────────────────────────────────────")
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.patch.set_facecolor("#1a1a2e")

    blue, green, red, amber, text, grid_c = (
        "#4a9eda", "#2ecc71", "#e74c3c", "#f39c12", "#e0e0e0", "#2a2a4a"
    )
    orange = "#e67e22"

    # Panel 1: Portfolio median wMAPE trend over time
    ax = axes[0]
    ax.set_facecolor("#12122a")
    cps_present = [c for c in all_cps if c in portfolio_med]
    meds = [portfolio_med[c] for c in cps_present]
    x_idx = list(range(len(cps_present)))
    ax.plot(x_idx, meds, color=blue, linewidth=2.5, marker="o", markersize=7, zorder=5)
    # Shade improvement region
    ax.fill_between(x_idx, meds, max(meds) * 1.1, alpha=0.1, color=blue)
    ax.set_xticks(x_idx)
    ax.set_xticklabels(cps_present, rotation=30, ha="right", color=text, fontsize=8)
    ax.set_ylabel("Median wMAPE (%)", color=text)
    ax.set_title("Portfolio Median wMAPE\nby Cutpoint", color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)
    for i, (cp, m) in enumerate(zip(cps_present, meds)):
        ax.annotate(f"{m:.2f}%", (i, m), textcoords="offset points",
                    xytext=(0, 8), ha="center", color=text, fontsize=7.5)
    if "Jan 2026" in cps_present:
        ax.axvline(len(cps_present) - 1, color=amber, linestyle="--",
                   linewidth=1, alpha=0.6, label="v3 Jan 2026")
        ax.legend(facecolor="#12122a", labelcolor=text, fontsize=8)

    # Panel 2: Relative ratio distribution at final cutpoint (boxplot by retail_account)
    ax = axes[1]
    ax.set_facecolor("#12122a")
    final_cp = cps_present[-1]
    final_data = df_all[df_all["cutpoint"] == final_cp].copy()
    final_data["rel_ratio"] = final_data["wmape"] / portfolio_med[final_cp]
    final_data["rel_ratio"] = final_data["rel_ratio"].clip(0, 8)

    accounts = final_data["retail_account"].value_counts().head(10).index.tolist()
    plot_data = [
        final_data[final_data["retail_account"] == acc]["rel_ratio"].dropna().values
        for acc in accounts
    ]
    plot_data_clean = [d for d in plot_data if len(d) > 0]
    accounts_clean  = [a for a, d in zip(accounts, plot_data) if len(d) > 0]

    if plot_data_clean:
        bp = ax.boxplot(plot_data_clean, vert=True, patch_artist=True,
                        medianprops=dict(color=amber, linewidth=2))
        for patch in bp["boxes"]:
            patch.set_facecolor("#1e3a5f")
            patch.set_alpha(0.7)
        for flier in bp["fliers"]:
            flier.set(marker=".", color=red, alpha=0.5, markersize=4)
        ax.set_xticks(range(1, len(accounts_clean) + 1))
        ax.set_xticklabels(
            [a[:12] for a in accounts_clean], rotation=35, ha="right",
            color=text, fontsize=7
        )
        ax.axhline(DRIFT_RATIO_THRESHOLD, color=red, linestyle="--",
                   linewidth=1.2, label=f"{DRIFT_RATIO_THRESHOLD}× drift threshold")
        ax.axhline(1.0, color=green, linestyle=":", linewidth=0.9, alpha=0.7,
                   label="Portfolio median")
        ax.legend(facecolor="#12122a", labelcolor=text, fontsize=7.5)

    ax.set_ylabel("Relative wMAPE ratio", color=text)
    ax.set_title(f"Relative wMAPE Ratio Distribution\n({final_cp} by Retailer)",
                 color=text, fontsize=10, pad=8)
    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)

    # Panel 3: Top drifting segments (horizontal bar)
    ax = axes[2]
    ax.set_facecolor("#12122a")

    if drifting_segs:
        top_n = drifting_segs[:10]
        labels = [
            f"{d['retail_account'][:14]}\n{d['maturity']} / {d['pack_format']}"
            for d in top_n
        ]
        scores = [d["drift_score"] for d in top_n]
        colors_bars = [red if s >= 3.0 else orange if s >= 2.0 else amber for s in scores]
        y_pos = list(range(len(top_n)))

        ax.barh(y_pos, scores, color=colors_bars, alpha=0.85)
        ax.axvline(DRIFT_RATIO_THRESHOLD, color=red, linestyle="--", linewidth=1.2,
                   alpha=0.7, label=f"{DRIFT_RATIO_THRESHOLD}× threshold")
        ax.axvline(1.0, color=green, linestyle=":", linewidth=0.9, alpha=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, color=text, fontsize=7)
        ax.set_xlabel("Avg relative ratio (last 3 cutpoints)", color=text, fontsize=8)
        ax.set_title(f"Top {len(top_n)} Drifting Segments\n(relative wMAPE ≥ {DRIFT_RATIO_THRESHOLD}× median)",
                     color=text, fontsize=10, pad=8)
        for i, (score, c) in enumerate(zip(scores, colors_bars)):
            ax.text(score + 0.05, i, f"{score:.2f}×", va="center", color=c, fontsize=8)
        ax.legend(facecolor="#12122a", labelcolor=text, fontsize=7.5)
    else:
        ax.text(0.5, 0.5, "No drifting segments\ndetected",
                transform=ax.transAxes, ha="center", va="center",
                color=green, fontsize=14, fontweight="bold")
        ax.set_title("Drifting Segments", color=text, fontsize=10)

    ax.tick_params(colors=text)
    for sp in ax.spines.values():
        sp.set_edgecolor(grid_c)

    verdict_color = green if verdict == "PASS" else red
    fig.suptitle(
        f"MO_68 — Per-Series Accuracy Drift Detection  |  "
        f"{len(drifting_segs)}/{len(seg_results)} segments drifting  |  "
        f"Verdict: {verdict}",
        color=verdict_color if drifting_segs else text,
        fontsize=11, fontweight="bold", y=1.01,
    )
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Chart saved → {OUT_PNG}")

    # ── 9. Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"MO_68 VERDICT: {verdict}")
    print(f"{'='*65}")
    print(f"  Segments evaluated: {len(seg_results)}")
    print(f"  Drifting (≥{DRIFT_RATIO_THRESHOLD}× in 2+ of last 3 cutpoints): {len(drifting_segs)}")
    if drifting_segs:
        print(f"\n  Top drifter: {drifting_segs[0]['seg']}")
        print(f"    drift_score={drifting_segs[0]['drift_score']:.2f}×  "
              f"final_wMAPE={drifting_segs[0]['final_wmape']:.1f}%")
    print("\nDone.")
