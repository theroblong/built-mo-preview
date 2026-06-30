"""MO_38 — Full model benchmark: LightGBM vs TFT vs Ridge vs Lasso vs baselines
           + Feature illumination: tier map, SHAP, Lasso selection, external candidates

Two goals:
  1. Prove out TFT (Temporal Fusion Transformer), Ridge, and Lasso as comparisons
     to the LightGBM ensemble — all on the same 3 temporal cutpoints (MO_32A identical).
     Key question: does giving TFT the same 25 domain-engineered features that make
     LightGBM beat N-BEATS close the gap? Do linear models give us interpretable
     feature importance at acceptable accuracy?

  2. Illuminate the feature set for FP&A stakeholders — directly addresses Connor Lain's
     Jun 26 question about external data integration (weather, sentiment, ERP calendar).
     Deliverables: tier map, SHAP (LightGBM), Lasso coefficient chart, external candidates.

Cutpoints (identical to MO_32A for apples-to-apples comparison):
  Dec 2024 → h=13 OOS (2025 annual horizon)
  Oct 2025 → h=13 OOS
  Dec 2025 → h=13 OOS (Jan–Apr 2026)

TFT setup (neuralforecast 3.1.9, same env var fixes as MO_32A):
  hist_exog_list: all 25 numeric FEATURE_COLS
  input_size=52, h=13, hidden_size=64, n_head=4, max_steps=500

Ridge/Lasso: sklearn, same feature matrix as LightGBM, StandardScaler.

Outputs:
  v2_mo38_accuracy_comparison.png  — wMAPE by model × cutpoint
  v2_mo38_feature_tiers.png        — tier map of all 27 features + Tier 3 candidates
  v2_mo38_shap_ridge_lasso.png     — SHAP (LGB) + Ridge coefs + Lasso selection
  v2_mo38_external_candidates.png  — external data candidates table
  v2_mo38_metrics.json             — all accuracy numbers
  v2_mo38_by_series_dec2025.csv    — per-series results at Dec 2025 cutpoint
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import json
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import lightgbm as lgb
import shap
from sklearn.linear_model import Ridge, Lasso
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from neuralforecast import NeuralForecast
from neuralforecast.models import TFT

# ── Constants ──────────────────────────────────────────────────────────────────

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "outputs")
PARQUET     = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")

GROUP_COLS  = ["upc", "channel_outlet", "retail_account", "geography_raw"]

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

# Numeric-only features for TFT hist_exog (exclude channel_outlet categorical)
HIST_EXOG = [c for c in FEATURE_COLS if c != "channel_outlet"]

# Feature tier groupings for visualization
FEATURE_TIERS = {
    "Demand Dynamics\n(lags + rolling)": [
        "base_units_lag1", "base_units_lag4", "base_units_lag13",
        "base_units_roll4_avg", "base_units_roll8_avg", "base_units_roll13_avg",
        "base_units_roll8_std", "base_units_roll13_std",
        "base_units_wow_delta", "base_units_z8", "base_units_z13",
    ],
    "Velocity\n(per-store SPM)": [
        "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
        "velocity_spm_z8", "velocity_spm_z13",
    ],
    "Distribution\n(TDP)": ["tdp", "tdp_z8"],
    "Price\n(ARP)": [
        "arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std",
    ],
    "Lifecycle &\nSeasonality": ["weeks_since_launch", "week_of_year", "channel_outlet"],
    "Mo Intelligence\n(Tier 2)": [
        "implied_elasticity", "max_donor_cannibal_prob", "donor_count",
    ],
}

TIER_COLORS = {
    "Demand Dynamics\n(lags + rolling)": "#1f77b4",
    "Velocity\n(per-store SPM)":         "#2ca02c",
    "Distribution\n(TDP)":               "#ff7f0e",
    "Price\n(ARP)":                       "#9467bd",
    "Lifecycle &\nSeasonality":           "#8c564b",
    "Mo Intelligence\n(Tier 2)":          "#e377c2",
}

EXTERNAL_CANDIDATES = [
    {
        "name": "Holiday Calendar Flags",
        "tier": "3A",
        "source": "Static (computed from ds)",
        "join": "Binary flags on week_of_year — no external feed needed",
        "hypothesis": "New Year's = protein bar spike; Nov–Dec = dip",
        "effort": "Low",
        "priority": "High",
    },
    {
        "name": "Weather Index",
        "tier": "3B",
        "source": "NOAA / OpenMeteo API",
        "join": "Weekly avg temp by retail DMA → join to SPINS geo_raw",
        "hypothesis": "Cold months suppress outdoor exercise → lower velocity",
        "effort": "Medium",
        "priority": "Medium",
    },
    {
        "name": "Consumer Sentiment (UMich / FRED)",
        "tier": "3B",
        "source": "FRED API (Federal Reserve)",
        "join": "Monthly score broadcast to weekly; national signal only",
        "hypothesis": "Low sentiment → trading down from premium $9 bars",
        "effort": "Low",
        "priority": "Medium",
    },
    {
        "name": "BUILT ERP Promo / Merch Calendar",
        "tier": "3C",
        "source": "BUILT internal ERP / trade promotion system",
        "join": "Date + retailer → week-level promo flags overlaid on SPINS",
        "hypothesis": "Known planned events dramatically improve promo-week accuracy",
        "effort": "High (requires BUILT data share)",
        "priority": "High",
    },
]

# Model / training params (match MO_32A exactly for fair comparison)
H             = 13    # quarterly horizon
INPUT_SIZE    = 52    # 1-year lookback
MAX_STEPS     = 500
EARLY_STOP    = 25
VAL_SIZE      = 13
MIN_TRAIN_WEEKS = 52
MIN_TEST_WEEKS  = 13

CUTPOINTS = [
    {"tag": "dec2024", "short": "Dec 2024", "cutoff": pd.Timestamp("2025-01-01")},
    {"tag": "oct2025", "short": "Oct 2025", "cutoff": pd.Timestamp("2025-10-01")},
    {"tag": "dec2025", "short": "Dec 2025", "cutoff": pd.Timestamp("2026-01-01")},
]

LGBM_PARAMS = dict(
    objective="regression",
    boosting_type="gbdt",
    n_estimators=1500,
    learning_rate=0.04,
    num_leaves=63,
    min_child_samples=20,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=5,
    reg_alpha=0.1,
    reg_lambda=0.2,
    random_state=42,
    n_jobs=-1,
    verbose=-1,
)

# ── Metric helpers ─────────────────────────────────────────────────────────────

def wmape(actual, predicted):
    total = np.nansum(actual)
    return float(np.nansum(np.abs(actual - predicted)) / total * 100) if total > 0 else np.nan

def naive_baselines(train_vals, n):
    arr = np.asarray(train_vals, float)
    last = arr[-1] if len(arr) > 0 else 0.0
    ma4  = float(np.mean(arr[-4:]))  if len(arr) >= 4  else last
    ma13 = float(np.mean(arr[-13:])) if len(arr) >= 13 else last
    return (np.full(n, ma4), np.full(n, ma13), np.full(n, last))

# ── Chart 1: Feature tier map ──────────────────────────────────────────────────

def chart_feature_tiers(out_path):
    fig, (ax_tiers, ax_ext) = plt.subplots(1, 2, figsize=(16, 8),
                                             gridspec_kw={"width_ratios": [1, 1.1]})
    fig.patch.set_facecolor("#f8f9fa")

    # ── Left: current 27 features by tier ─────────────────────────────────────
    ax_tiers.set_facecolor("#f8f9fa")
    y = 0
    tier_patches = []
    tick_positions, tick_labels = [], []

    for tier_name, features in FEATURE_TIERS.items():
        color = TIER_COLORS[tier_name]
        for feat in features:
            ax_tiers.barh(y, 1, color=color, alpha=0.8, edgecolor="white", linewidth=0.5)
            ax_tiers.text(1.02, y, feat, va="center", fontsize=8.5,
                          fontfamily="monospace", color="#222")
            tick_positions.append(y)
            tick_labels.append("")
            y += 1
        y += 0.4  # gap between tiers
        tier_patches.append(mpatches.Patch(color=color, label=tier_name.replace("\n", " ")))

    ax_tiers.set_xlim(0, 4.5)
    ax_tiers.set_ylim(-0.5, y - 0.4 + 0.5)
    ax_tiers.invert_yaxis()
    ax_tiers.set_xticks([])
    ax_tiers.set_yticks([])
    ax_tiers.set_title("Current Feature Set — 27 Inputs\n(Tiers 1 & 2)",
                        fontsize=13, fontweight="bold", pad=12)
    ax_tiers.legend(handles=tier_patches, loc="lower right", fontsize=8.5,
                    framealpha=0.85, title="Tier", title_fontsize=9)
    ax_tiers.spines[:].set_visible(False)

    total_t1 = sum(len(v) for k, v in FEATURE_TIERS.items() if "Mo Intelligence" not in k)
    total_t2 = len(FEATURE_TIERS["Mo Intelligence\n(Tier 2)"])
    ax_tiers.text(0.02, 1.01, f"Tier 1: {total_t1} features  |  Tier 2 (Mo): {total_t2} features",
                  transform=ax_tiers.transAxes, fontsize=9, color="#555")

    # ── Right: external candidates (Tier 3) ───────────────────────────────────
    ax_ext.set_facecolor("#f8f9fa")
    ax_ext.set_xlim(0, 10)
    ax_ext.set_ylim(0, 10)
    ax_ext.axis("off")
    ax_ext.set_title("Tier 3 — External Data Candidates\n(Connor's Jun 26 integration question)",
                     fontsize=13, fontweight="bold", pad=12)

    priority_colors = {"High": "#d62728", "Medium": "#ff7f0e", "Low": "#2ca02c"}
    effort_colors   = {"Low": "#2ca02c", "Medium": "#ff7f0e", "High (requires BUILT data share)": "#d62728"}

    headers = ["Name", "Data Source", "Join Strategy", "Hypothesis", "Effort", "Priority"]
    col_x   = [0.0,   2.0,           3.5,             5.5,          7.8,      8.9]
    col_w   = [2.0,   1.5,           2.0,             2.3,          1.1,      1.1]

    row_h = 1.8
    for ci, hdr in enumerate(headers):
        ax_ext.text(col_x[ci], 9.5, hdr, fontsize=8.5, fontweight="bold", color="#333",
                    va="top", wrap=True)

    for ri, cand in enumerate(EXTERNAL_CANDIDATES):
        y_row = 9.5 - (ri + 1) * row_h
        bg_color = "#e8f4e8" if ri % 2 == 0 else "#f4f4f4"
        ax_ext.add_patch(mpatches.FancyBboxPatch(
            (-0.1, y_row - 0.1), 10.2, row_h - 0.2,
            boxstyle="round,pad=0.05", facecolor=bg_color, edgecolor="#ddd", linewidth=0.5
        ))
        vals = [
            cand["name"],
            cand["source"],
            cand["join"],
            cand["hypothesis"],
            cand["effort"],
            cand["priority"],
        ]
        for ci, val in enumerate(vals):
            kwargs = dict(fontsize=8, va="center", wrap=True, color="#222")
            if ci == 4:  # effort
                kwargs["color"] = effort_colors.get(val, "#222")
                kwargs["fontweight"] = "bold"
            elif ci == 5:  # priority
                kwargs["color"] = priority_colors.get(val, "#222")
                kwargs["fontweight"] = "bold"
            ax_ext.text(col_x[ci], y_row + (row_h - 0.2) / 2 - 0.05, val,
                        fontsize=8, va="center", color=kwargs.get("color", "#222"),
                        fontweight=kwargs.get("fontweight", "normal"),
                        ha="left")

    ax_ext.text(0, -0.2, "How to apply: Holiday flags can be added immediately (no data feed).\n"
                "Weather + Sentiment = Phase 3. ERP calendar = requires BUILT data share agreement.",
                fontsize=8, color="#555", va="top", transform=ax_ext.transAxes)

    plt.tight_layout(pad=2)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")

# ── Chart 2: SHAP + Ridge + Lasso ─────────────────────────────────────────────

def chart_feature_importance(lgbm_model, ridge_model, lasso_model,
                              test_df, avail, scaler, out_path):
    fig, axes = plt.subplots(1, 3, figsize=(18, 7))
    fig.patch.set_facecolor("#f8f9fa")
    fig.suptitle("Feature Importance — Three Lenses\n(Dec 2025 cutpoint, Jan–Apr 2026 OOS)",
                 fontsize=14, fontweight="bold", y=1.01)

    numeric_avail = [c for c in avail if c != "channel_outlet"]

    # ── Panel 1: LightGBM SHAP ────────────────────────────────────────────────
    ax = axes[0]
    ax.set_facecolor("#f8f9fa")
    try:
        explainer  = shap.TreeExplainer(lgbm_model)
        shap_vals  = explainer.shap_values(test_df[avail])
        mean_abs   = pd.Series(np.abs(shap_vals).mean(axis=0), index=avail)
        mean_abs   = mean_abs.sort_values(ascending=True).tail(20)
        colors_shap = [TIER_COLORS.get(
            next((t for t, fs in FEATURE_TIERS.items() if f in fs), ""), "#aaa"
        ) for f in mean_abs.index]
        ax.barh(range(len(mean_abs)), mean_abs.values, color=colors_shap, alpha=0.85)
        ax.set_yticks(range(len(mean_abs)))
        ax.set_yticklabels(mean_abs.index, fontsize=8, fontfamily="monospace")
        ax.set_xlabel("Mean |SHAP value| (log units)", fontsize=9)
    except Exception as e:
        ax.text(0.5, 0.5, f"SHAP unavailable:\n{e}", ha="center", va="center",
                transform=ax.transAxes, fontsize=9)
    ax.set_title("LightGBM\nSHAP (non-linear, interaction-aware)", fontsize=10, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_facecolor("#f8f9fa")

    # ── Panel 2: Ridge coefficients ───────────────────────────────────────────
    ax = axes[1]
    ax.set_facecolor("#f8f9fa")
    try:
        ridge_coefs = pd.Series(ridge_model.named_steps["ridge"].coef_,
                                index=numeric_avail).sort_values(key=abs, ascending=True).tail(20)
        bar_colors = ["#d62728" if v < 0 else "#2ca02c" for v in ridge_coefs.values]
        ax.barh(range(len(ridge_coefs)), ridge_coefs.values, color=bar_colors, alpha=0.85)
        ax.set_yticks(range(len(ridge_coefs)))
        ax.set_yticklabels(ridge_coefs.index, fontsize=8, fontfamily="monospace")
        ax.axvline(0, color="gray", linewidth=0.8, linestyle="--")
        ax.set_xlabel("Coefficient (standardized; green=positive, red=negative)", fontsize=9)
    except Exception as e:
        ax.text(0.5, 0.5, f"Ridge unavailable:\n{e}", ha="center", va="center",
                transform=ax.transAxes, fontsize=9)
    ax.set_title("Ridge Regression\nStandardized coefficients (linear, directional)", fontsize=10, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)

    # ── Panel 3: Lasso selected features ──────────────────────────────────────
    ax = axes[2]
    ax.set_facecolor("#f8f9fa")
    try:
        lasso_coefs = pd.Series(lasso_model.named_steps["lasso"].coef_,
                                index=numeric_avail)
        n_selected  = (lasso_coefs != 0).sum()
        selected    = lasso_coefs[lasso_coefs != 0].sort_values(key=abs, ascending=True)
        bar_colors  = ["#d62728" if v < 0 else "#2ca02c" for v in selected.values]
        ax.barh(range(len(selected)), selected.values, color=bar_colors, alpha=0.85)
        ax.set_yticks(range(len(selected)))
        ax.set_yticklabels(selected.index, fontsize=8, fontfamily="monospace")
        ax.axvline(0, color="gray", linewidth=0.8, linestyle="--")
        ax.set_xlabel("Coefficient (standardized; green=positive, red=negative)", fontsize=9)
        ax.set_title(f"Lasso Regression\nAuto-selected {n_selected}/{len(numeric_avail)} features "
                     f"(sparse, L1-penalized)", fontsize=10, fontweight="bold")
        zeroed = (lasso_coefs == 0).sum()
        ax.text(0.98, 0.02, f"{zeroed} features zeroed out", transform=ax.transAxes,
                fontsize=8.5, ha="right", va="bottom", color="#555",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7))
    except Exception as e:
        ax.text(0.5, 0.5, f"Lasso unavailable:\n{e}", ha="center", va="center",
                transform=ax.transAxes, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_facecolor("#f8f9fa")

    plt.tight_layout(pad=2)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")

# ── Chart 3: Accuracy comparison ──────────────────────────────────────────────

def chart_accuracy(all_results, out_path):
    methods   = ["LightGBM", "TFT", "Ridge", "Lasso", "MA 13wk", "Naive"]
    cutpoints = ["Dec 2024", "Oct 2025", "Dec 2025"]
    colors    = {
        "LightGBM": "#1f77b4",
        "TFT":      "#e377c2",
        "Ridge":    "#2ca02c",
        "Lasso":    "#ff7f0e",
        "MA 13wk":  "#8c564b",
        "Naive":    "#d62728",
    }
    linestyles = {
        "LightGBM": "-",  "TFT": "--",  "Ridge": "-.",
        "Lasso":    ":",  "MA 13wk": "--", "Naive": ":",
    }
    markers = {
        "LightGBM": "o", "TFT": "s", "Ridge": "^",
        "Lasso": "D", "MA 13wk": "v", "Naive": "x",
    }

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    for method in methods:
        vals = []
        for cp in cutpoints:
            key = f"{cp}|{method}"
            vals.append(all_results.get(key, np.nan))
        ax.plot(cutpoints, vals,
                color=colors[method], linestyle=linestyles[method],
                marker=markers[method], markersize=8, linewidth=2.2,
                label=f"{method} ({vals[-1]:.1f}%)" if not np.isnan(vals[-1]) else method)
        for xi, v in enumerate(vals):
            if not np.isnan(v):
                ax.annotate(f"{v:.1f}%", (xi, v),
                            textcoords="offset points", xytext=(6, 4),
                            fontsize=8.5, color=colors[method], fontweight="bold")

    ax.set_ylabel("wMAPE (lower = better)", fontsize=11)
    ax.set_xlabel("Training cutpoint  (h = 13 weeks OOS each)", fontsize=11)
    ax.set_title("Model Accuracy Benchmark\nwMAPE at 3 temporal cutpoints — same h=13 quarterly horizon",
                 fontsize=13, fontweight="bold")
    ax.legend(fontsize=9.5, loc="upper right", framealpha=0.9,
              title="Model (Dec 2025 wMAPE)", title_fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    note = ("Feature advantage: LightGBM + TFT receive all 25 domain-engineered features.\n"
            "Ridge + Lasso receive same features but assume linear relationships only.\n"
            "MA 13wk + Naive = no features. Gap between these groups = value of domain intelligence.")
    ax.text(0.01, -0.18, note, transform=ax.transAxes, fontsize=8.5,
            color="#555", va="top", style="italic")

    plt.tight_layout(pad=2)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("MO_38 — Full model benchmark + Feature illumination")
    print("=" * 70)

    # ── Load data ──────────────────────────────────────────────────────────────
    print(f"\nLoading {PARQUET} …")
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df["__time_naive"] = df["__time"].dt.tz_convert(None)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    df["log_base_units"] = np.log1p(df["base_units"].clip(lower=0))

    # Encode channel_outlet for LightGBM / Ridge / Lasso
    df["channel_outlet"] = df["channel_outlet"].astype("category")
    df["channel_encoded"] = df["channel_outlet"].cat.codes.astype(float)

    # Unique ID for neuralforecast
    df["unique_id"] = (df["upc"].astype(str) + "|" + df["channel_outlet"].astype(str) +
                       "|" + df["retail_account"].astype(str) + "|" + df["geography_raw"].astype(str))

    # MULO filter
    mulo_mask = df["channel_outlet"].astype(str).str.contains(
        "MULTI OUTLET|MULO", case=False, na=False
    ) | df["geography_raw"].astype(str).str.contains(
        "MULTI OUTLET|MULO|TOTAL US|ALL CHANNEL", case=False, na=False
    )
    df = df[~mulo_mask].reset_index(drop=True)
    print(f"  Rows after MULO filter: {len(df):,}  "
          f"| Series: {df.groupby(GROUP_COLS).ngroups:,}")

    # Numeric fill (NaN → 0 for Mo signals that may be missing)
    numeric_feat = [c for c in FEATURE_COLS if c != "channel_outlet"]
    for c in numeric_feat:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # Replace channel_outlet with encoded for sklearn models
    SKLEARN_FEAT = [c if c != "channel_outlet" else "channel_encoded" for c in FEATURE_COLS]
    SKLEARN_FEAT = [c for c in SKLEARN_FEAT if c in df.columns]

    all_results     = {}
    all_cp_metrics  = []
    dec2025_series  = None
    saved_models    = {}  # for feature importance (Dec 2025)

    # ── Chart 1: Feature tiers (static, no model needed) ──────────────────────
    print("\n[Chart 1/4] Feature tier map …")
    chart_feature_tiers(os.path.join(OUTPUT_DIR, "v2_mo38_feature_tiers.png"))

    # ── Loop cutpoints ─────────────────────────────────────────────────────────
    for ci, cp in enumerate(CUTPOINTS):
        cutoff     = cp["cutoff"]
        cutoff_utc = cutoff.tz_localize("UTC")
        tag        = cp["tag"]
        short      = cp["short"]
        is_dec25   = (tag == "dec2025")

        print(f"\n{'─'*70}")
        print(f"CUTPOINT {ci+1}/3: {short}  (h={H} OOS weeks)")
        print(f"{'─'*70}")

        # Qualify series
        train_counts = df[df["__time"] <  cutoff_utc].groupby(GROUP_COLS).size()
        test_counts  = df[df["__time"] >= cutoff_utc].groupby(GROUP_COLS).size()
        coverage = pd.concat([train_counts.rename("tr"),
                               test_counts.rename("te")], axis=1).fillna(0).astype(int)
        qualifying = coverage[
            (coverage["tr"] >= MIN_TRAIN_WEEKS) &
            (coverage["te"] >= MIN_TEST_WEEKS)
        ]
        qual_keys = set(qualifying.index.tolist())
        df["_key"] = list(zip(df["upc"], df["channel_outlet"],
                              df["retail_account"], df["geography_raw"]))
        df_cp = df[df["_key"].isin(qual_keys)].copy()

        train_all = df_cp[df_cp["__time"] <  cutoff_utc].copy()
        test_all  = df_cp[df_cp["__time"] >= cutoff_utc].copy()
        test_dates = sorted(test_all["__time"].unique())[:H]
        test_df   = test_all[test_all["__time"].isin(test_dates)].copy()

        n_series = len(qualifying)
        print(f"  Qualifying series: {n_series:,}")
        print(f"  Train: {len(train_all):,} rows  "
              f"({train_all['__time'].min().date()} → {train_all['__time'].max().date()})")
        print(f"  Test (first {H}w): {len(test_df):,} rows")

        avail        = [c for c in FEATURE_COLS if c in df_cp.columns]
        avail_sklearn = [c if c != "channel_outlet" else "channel_encoded"
                         for c in avail]
        avail_sklearn = [c for c in avail_sklearn if c in df_cp.columns]
        avail_hist   = [c for c in HIST_EXOG if c in df_cp.columns]

        # ── 1. LightGBM ───────────────────────────────────────────────────────
        print(f"  [1/4] LightGBM …")
        lval_cut  = cutoff_utc - pd.Timedelta(weeks=8)
        super_tr  = train_all[train_all["__time"] <  lval_cut]
        local_val = train_all[train_all["__time"] >= lval_cut]

        lgbm_model = lgb.LGBMRegressor(**LGBM_PARAMS)
        lgbm_model.fit(
            super_tr[avail], super_tr["log_base_units"].values,
            eval_set=[(local_val[avail], local_val["log_base_units"].values)],
            callbacks=[lgb.early_stopping(50, verbose=False),
                       lgb.log_evaluation(500)],
        )
        preds_log = lgbm_model.predict(test_df[avail])
        test_df = test_df.copy()
        test_df["pred_lgbm"] = np.expm1(np.clip(preds_log, 0, None))
        lgbm_wmape = wmape(test_df["base_units"].values, test_df["pred_lgbm"].values)
        print(f"       LightGBM wMAPE: {lgbm_wmape:.1f}%  "
              f"(best iter: {lgbm_model.best_iteration_})")

        # ── 2. Ridge Regression ───────────────────────────────────────────────
        print(f"  [2/4] Ridge Regression …")
        # Drop NaN targets (sklearn doesn't tolerate them; LightGBM does)
        train_sk = train_all[train_all["log_base_units"].notna()].copy()
        for c in avail_sklearn:
            train_sk[c] = train_sk[c].fillna(0.0)
        test_sk = test_df.copy()
        for c in avail_sklearn:
            if c in test_sk.columns:
                test_sk[c] = test_sk[c].fillna(0.0)

        # Cap for log-space predictions — prevents expm1 blowup on OOS extrapolation
        log_cap = float(np.percentile(train_sk["log_base_units"].values, 99.9))

        ridge_model = Pipeline([
            ("scaler", StandardScaler()),
            ("ridge",  Ridge(alpha=1.0, random_state=42)),
        ])
        ridge_model.fit(train_sk[avail_sklearn].values,
                        train_sk["log_base_units"].values)
        ridge_pred_log = ridge_model.predict(test_sk[avail_sklearn].values)
        test_df["pred_ridge"] = np.expm1(np.clip(ridge_pred_log, 0, log_cap))
        ridge_wmape = wmape(test_df["base_units"].values, test_df["pred_ridge"].values)
        print(f"       Ridge wMAPE: {ridge_wmape:.1f}%")

        # ── 3. Lasso Regression ───────────────────────────────────────────────
        print(f"  [3/4] Lasso Regression …")
        lasso_model = Pipeline([
            ("scaler", StandardScaler()),
            ("lasso",  Lasso(alpha=0.01, max_iter=5000, random_state=42)),
        ])
        lasso_model.fit(train_sk[avail_sklearn].values,
                        train_sk["log_base_units"].values)
        lasso_pred_log = lasso_model.predict(test_sk[avail_sklearn].values)
        test_df["pred_lasso"] = np.expm1(np.clip(lasso_pred_log, 0, log_cap))
        lasso_wmape = wmape(test_df["base_units"].values, test_df["pred_lasso"].values)
        n_selected = int((lasso_model.named_steps["lasso"].coef_ != 0).sum())
        print(f"       Lasso wMAPE: {lasso_wmape:.1f}%  "
              f"({n_selected}/{len(avail_sklearn)} features selected)")

        # ── 4. TFT (global, h=13) ─────────────────────────────────────────────
        print(f"  [4/4] TFT (global, {n_series} series, "
              f"h={H}, input_size={INPUT_SIZE}, max_steps={MAX_STEPS}) …")
        train_nf = (
            train_all[["unique_id", "__time_naive", "log_base_units"] + avail_hist]
            .rename(columns={"__time_naive": "ds", "log_base_units": "y"})
            .sort_values(["unique_id", "ds"])
            .reset_index(drop=True)
            .copy()
        )
        # Drop NaN targets and fill any remaining NaNs in hist exog
        train_nf = train_nf[train_nf["y"].notna()].reset_index(drop=True)
        for c in avail_hist:
            if c in train_nf.columns:
                train_nf[c] = train_nf[c].fillna(0.0)

        tft = TFT(
            h=H,
            input_size=INPUT_SIZE,
            hidden_size=64,
            n_head=4,
            hist_exog_list=avail_hist,
            max_steps=MAX_STEPS,
            early_stop_patience_steps=EARLY_STOP,
            val_check_steps=25,
            scaler_type="standard",
            random_seed=42,
            accelerator="cpu",
            start_padding_enabled=True,
            enable_progress_bar=False,
            enable_model_summary=False,
        )
        nf = NeuralForecast(models=[tft], freq="W")
        nf.fit(train_nf, val_size=VAL_SIZE)
        preds_tft = nf.predict().rename(columns={"TFT": "pred_log"})
        preds_tft["pred_tft"] = np.expm1(np.clip(preds_tft["pred_log"].values, 0, None))
        preds_tft["ds"] = pd.to_datetime(preds_tft["ds"]).dt.normalize()

        test_df["ds"] = pd.to_datetime(test_df["__time_naive"]).dt.normalize()
        merged = test_df.merge(
            preds_tft[["unique_id", "ds", "pred_tft"]],
            on=["unique_id", "ds"], how="left"
        )
        n_matched = merged["pred_tft"].notna().sum()
        print(f"       TFT predictions matched: {n_matched:,}/{len(merged):,}")
        tft_wmape = wmape(merged["base_units"].values,
                          merged["pred_tft"].fillna(0).values)
        print(f"       TFT wMAPE: {tft_wmape:.1f}%")

        # ── Naive baselines ───────────────────────────────────────────────────
        ma4_list, ma13_list, naive_list = [], [], []
        for key, grp_test in merged.groupby(GROUP_COLS):
            uid = grp_test["unique_id"].iloc[0]
            grp_train = train_all[train_all["unique_id"] == uid]["base_units"].values
            n = len(grp_test)
            ma4, ma13, nv = naive_baselines(grp_train, n)
            ma4_list.append(ma4); ma13_list.append(ma13); naive_list.append(nv)

        merged["ma4"]   = np.concatenate(ma4_list)
        merged["ma13"]  = np.concatenate(ma13_list)
        merged["naive"] = np.concatenate(naive_list)

        act = merged["base_units"].values
        ma13_wmape  = wmape(act, merged["ma13"].values)
        naive_wmape = wmape(act, merged["naive"].values)
        print(f"       MA 13wk wMAPE: {ma13_wmape:.1f}%  |  Naive: {naive_wmape:.1f}%")

        # ── Store results ─────────────────────────────────────────────────────
        for method, val in [
            ("LightGBM", lgbm_wmape), ("TFT", tft_wmape),
            ("Ridge", ridge_wmape),   ("Lasso", lasso_wmape),
            ("MA 13wk", ma13_wmape),  ("Naive", naive_wmape),
        ]:
            all_results[f"{short}|{method}"] = round(val, 2)

        cp_row = {
            "cutpoint": short, "n_series": n_series,
            "wmape_lgbm": round(lgbm_wmape, 2),
            "wmape_tft":  round(tft_wmape, 2),
            "wmape_ridge": round(ridge_wmape, 2),
            "wmape_lasso": round(lasso_wmape, 2),
            "wmape_ma13": round(ma13_wmape, 2),
            "wmape_naive": round(naive_wmape, 2),
            "lasso_n_selected": n_selected,
        }
        all_cp_metrics.append(cp_row)
        print(f"\n  ┌─ {short} summary ─────────────────────────────")
        for m, v in [("LightGBM", lgbm_wmape), ("TFT", tft_wmape),
                     ("Ridge", ridge_wmape), ("Lasso", lasso_wmape),
                     ("MA 13wk", ma13_wmape), ("Naive", naive_wmape)]:
            print(f"  │  {m:<12} {v:>6.1f}%")
        print(f"  └──────────────────────────────────────────────")

        if is_dec25:
            dec2025_series = merged.copy()
            saved_models = {
                "lgbm":  lgbm_model,
                "ridge": ridge_model,
                "lasso": lasso_model,
                "avail": avail,
                "avail_sklearn": avail_sklearn,
            }

    # ── Chart 2: Feature importance (Dec 2025 models) ─────────────────────────
    if saved_models and dec2025_series is not None:
        print("\n[Chart 2/4] Feature importance (SHAP + Ridge + Lasso, Dec 2025) …")
        chart_feature_importance(
            saved_models["lgbm"], saved_models["ridge"], saved_models["lasso"],
            dec2025_series, saved_models["avail"], None,
            os.path.join(OUTPUT_DIR, "v2_mo38_shap_ridge_lasso.png")
        )

    # ── Chart 3: Accuracy comparison ──────────────────────────────────────────
    print("\n[Chart 3/4] Accuracy comparison chart …")
    chart_accuracy(all_results, os.path.join(OUTPUT_DIR, "v2_mo38_accuracy_comparison.png"))

    # ── Chart 4: External candidates (standalone table) ───────────────────────
    print("[Chart 4/4] External candidates chart …")
    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor("#f8f9fa")
    ax.axis("off")
    ax.set_title("Tier 3 — External Feature Candidates for FP&A Integration\n"
                 "(addresses Connor Lain's Jun 26 question about external data)",
                 fontsize=13, fontweight="bold", pad=12)

    cols = ["Name", "Tier", "Data Source", "Join Strategy", "Business Hypothesis",
            "Effort", "Priority"]
    rows = [[c["name"], c["tier"], c["source"], c["join"], c["hypothesis"],
             c["effort"], c["priority"]] for c in EXTERNAL_CANDIDATES]

    tbl = ax.table(cellText=rows, colLabels=cols,
                   loc="center", cellLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.5)
    tbl.auto_set_column_width(list(range(len(cols))))

    priority_map = {"High": "#ffe4e4", "Medium": "#fff3e0"}
    for ri in range(len(rows)):
        priority = rows[ri][6]
        bg = priority_map.get(priority, "#f9f9f9")
        for ci in range(len(cols)):
            tbl[(ri + 1, ci)].set_facecolor(bg)
    for ci in range(len(cols)):
        tbl[(0, ci)].set_facecolor("#dce8f5")
        tbl[(0, ci)].set_text_props(fontweight="bold")

    plt.tight_layout(pad=2)
    fig.savefig(os.path.join(OUTPUT_DIR, "v2_mo38_external_candidates.png"),
                dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: v2_mo38_external_candidates.png")

    # ── Save JSON ──────────────────────────────────────────────────────────────
    summary = {
        "script": "MO_38",
        "h": H, "input_size": INPUT_SIZE, "max_steps": MAX_STEPS,
        "min_train_weeks": MIN_TRAIN_WEEKS,
        "n_features": len(FEATURE_COLS),
        "n_hist_exog": len(HIST_EXOG),
        "cutpoints": all_cp_metrics,
        "all_results": all_results,
    }
    json_path = os.path.join(OUTPUT_DIR, "v2_mo38_summary.json")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Saved: v2_mo38_summary.json")

    if dec2025_series is not None:
        dec2025_series[GROUP_COLS + ["__time", "base_units",
                                     "pred_lgbm", "pred_tft", "pred_ridge",
                                     "pred_lasso", "ma13", "naive"]].to_csv(
            os.path.join(OUTPUT_DIR, "v2_mo38_by_series_dec2025.csv"), index=False
        )
        print(f"  Saved: v2_mo38_by_series_dec2025.csv")

    # ── Final summary table ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS (wMAPE — lower is better)")
    print("=" * 70)
    hdr = f"{'Cutpoint':<12} {'LightGBM':>9} {'TFT':>7} {'Ridge':>7} {'Lasso':>7} {'MA13':>7} {'Naive':>7}"
    print(hdr)
    print("─" * len(hdr))
    for row in all_cp_metrics:
        print(f"{row['cutpoint']:<12} "
              f"{row['wmape_lgbm']:>8.1f}% "
              f"{row['wmape_tft']:>6.1f}% "
              f"{row['wmape_ridge']:>6.1f}% "
              f"{row['wmape_lasso']:>6.1f}% "
              f"{row['wmape_ma13']:>6.1f}% "
              f"{row['wmape_naive']:>6.1f}%")
    print("=" * 70)
    print("\nDone.")


if __name__ == "__main__":
    main()
