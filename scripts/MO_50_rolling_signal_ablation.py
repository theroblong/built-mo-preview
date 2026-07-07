"""MO_50 — Rolling vs. Static Mo Intelligence Feature Ablation

Tests whether MO_46 time-varying signals improve forecast accuracy beyond
the static Mo Intelligence features shown in MO_41, and where the gains
are largest by channel, retailer, and SKU maturity segment.

Three core questions:
  1. Portfolio-level: do rolling Mo signals (rolling_cannibal_pressure,
     rolling_cannibal_trend, rolling_elasticity) beat static Mo signals
     (implied_elasticity, max_donor_cannibal_prob, donor_count) at M5?
  2. Does adding YAGO lags (lag52) on top of rolling signals further help?
  3. Segment-level: where do rolling signals contribute most vs. least?
     → channel / retailer / SKU maturity breakdown

Extended ablation variants (same M1–M4 foundation as MO_41, then branch):
  MA 13wk  — baseline (Excel-equivalent)
  M1       — Demand Foundation (11 features)
  M2       — + Per-Store Velocity (15)
  M3       — + TDP & Price (21)
  M4       — + Lifecycle & Season (24)
  M5a      — + Static Mo (27) — current MO_41 M5; ICC=1.0 features
  M5b      — + Rolling Mo (27) — MO_46 signals replace static
  M6       — + Rolling Mo + YAGO lags (29) — full time-varying stack
  M7       — + All Mo features: static + rolling + YAGO (32)

Outputs:
  outputs/v2_mo50_ablation.png        — extended ablation waterfall
  outputs/v2_mo50_segment_channel.png — wMAPE delta by channel
  outputs/v2_mo50_segment_retailer.png — wMAPE delta by retailer (top 15)
  outputs/v2_mo50_segment_maturity.png — wMAPE delta by SKU age bucket
  outputs/v2_mo50_shap.png            — SHAP importance for best variant
  outputs/mo50_ablation_results.csv

HTML: patches Section 19 into built_demand_intelligence_report.html
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import base64
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

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "outputs")
PARQUET     = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")
HTML_IN     = os.path.join(OUTPUT_DIR, "built_demand_intelligence_report.html")
HTML_OUT    = os.path.join(OUTPUT_DIR, "built_demand_intelligence_report.html")

GROUP_COLS      = ["upc", "channel_outlet", "retail_account", "geography_raw"]
DEC2025_CUTOFF  = pd.Timestamp("2026-01-01")
MIN_TRAIN_WEEKS = 52
MIN_TEST_WEEKS  = 13
H               = 13   # forecast horizon (weeks)
BG              = "#f8f9fa"

# ── Feature layers ─────────────────────────────────────────────────────────────
LAYER_DEMAND = [
    "base_units_lag1", "base_units_lag4", "base_units_lag13",
    "base_units_roll4_avg", "base_units_roll8_avg", "base_units_roll13_avg",
    "base_units_roll8_std", "base_units_roll13_std",
    "base_units_wow_delta", "base_units_z8", "base_units_z13",
]
LAYER_VELOCITY = [
    "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
    "velocity_spm_z8", "velocity_spm_z13",
]
LAYER_TDP_PRICE = [
    "tdp", "tdp_z8",
    "arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std",
]
LAYER_LIFECYCLE = [
    "weeks_since_launch", "week_of_year", "channel_outlet",
]
LAYER_MO_STATIC = [
    "implied_elasticity", "max_donor_cannibal_prob", "donor_count",
]
LAYER_MO_ROLLING = [
    "rolling_cannibal_pressure", "rolling_cannibal_trend", "rolling_elasticity",
]
LAYER_YAGO = [
    "base_units_lag52", "velocity_spm_lag52",
]

FOUNDATION = LAYER_DEMAND + LAYER_VELOCITY + LAYER_TDP_PRICE + LAYER_LIFECYCLE

# Ablation variants — each entry: (tag, label, features_to_add_to_M4, color)
VARIANT_DEFS = [
    ("M5a", "+ Static Mo (current)",     LAYER_MO_STATIC,                                          "#e377c2"),
    ("M5b", "+ Rolling Mo",              LAYER_MO_ROLLING,                                         "#17becf"),
    ("M6",  "+ Rolling Mo + YAGO",       LAYER_MO_ROLLING + LAYER_YAGO,                            "#bcbd22"),
    ("M7",  "+ All Mo (static+rolling+YAGO)", LAYER_MO_STATIC + LAYER_MO_ROLLING + LAYER_YAGO,    "#9467bd"),
]

LGBM_PARAMS = dict(
    objective="regression", boosting_type="gbdt", n_estimators=1000,
    learning_rate=0.04, num_leaves=63, min_child_samples=20,
    feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
    reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def wmape(actual, predicted):
    total = np.nansum(actual)
    return float(np.nansum(np.abs(actual - predicted)) / total * 100) if total > 0 else np.nan

def img_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def encode_cats(df):
    df = df.copy()
    if "channel_outlet" in df.columns:
        df["channel_encoded"] = df["channel_outlet"].astype("category").cat.codes.astype(float)
    return df

def avail_feats(feats, df):
    """Return features that exist in df, replacing channel_outlet with channel_encoded."""
    out = []
    for f in feats:
        if f == "channel_outlet":
            if "channel_encoded" in df.columns:
                out.append("channel_encoded")
        elif f in df.columns:
            out.append(f)
    return out

def train_eval(train_df, val_df, test_df, feats, params=None):
    p = params or LGBM_PARAMS
    af = avail_feats(feats, train_df)
    model = lgb.LGBMRegressor(**p)
    model.fit(
        train_df[af], train_df["log_base_units"],
        eval_set=[(val_df[af], val_df["log_base_units"])],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(9999)],
    )
    preds_log = model.predict(test_df[af])
    preds     = np.expm1(np.clip(preds_log, 0, None))
    w = wmape(test_df["base_units"].values, preds)
    return w, preds, model, af


# ── Chart 1: Extended ablation waterfall ──────────────────────────────────────

def chart_ablation(super_tr, val_df, test_df, ma13_wmape, out_path):
    print("  Running stepwise ablation …")
    results = []

    # M1–M4: shared foundation steps
    foundation_steps = [
        ("M1", "Demand Foundation",    LAYER_DEMAND,    "#1f77b4"),
        ("M2", "+ Per-Store Velocity", LAYER_VELOCITY,  "#2ca02c"),
        ("M3", "+ TDP & Price",        LAYER_TDP_PRICE, "#ff7f0e"),
        ("M4", "+ Lifecycle & Season", LAYER_LIFECYCLE, "#8c564b"),
    ]
    cumulative = []
    for tag, name, layer, color in foundation_steps:
        cumulative = cumulative + layer
        w, preds, _, _ = train_eval(super_tr, val_df, test_df, cumulative)
        results.append({"tag": tag, "name": name, "color": color,
                        "wmape": w, "n_feats": len(avail_feats(cumulative, super_tr)),
                        "preds": preds})
        print(f"    {tag} ({name}): {w:.2f}%  [{len(avail_feats(cumulative, super_tr))} feats]")

    m4_feats = cumulative[:]
    m4_wmape = results[-1]["wmape"]

    # M5a–M7: branch variants on top of M4
    branch_results = []
    for tag, name, extra, color in VARIANT_DEFS:
        feats = m4_feats + extra
        w, preds, _, _ = train_eval(super_tr, val_df, test_df, feats)
        nf = len(avail_feats(feats, super_tr))
        branch_results.append({"tag": tag, "name": name, "color": color,
                                "wmape": w, "n_feats": nf, "preds": preds,
                                "feats": feats})
        print(f"    {tag} ({name}): {w:.2f}%  [{nf} feats]")

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(14, 10),
        gridspec_kw={"height_ratios": [3, 2]},
    )
    fig.patch.set_facecolor(BG)
    for ax in (ax_top, ax_bot):
        ax.set_facecolor(BG)

    # Top: foundation staircase
    all_labels  = ["MA 13wk\n(baseline)"] + [f"{r['tag']}\n{r['name']}" for r in results]
    all_wmapes  = [ma13_wmape] + [r["wmape"] for r in results]
    all_colors  = ["#9e9e9e"] + [r["color"] for r in results]
    all_nfeats  = [0] + [r["n_feats"] for r in results]

    bars = ax_top.bar(range(len(all_wmapes)), all_wmapes, color=all_colors, alpha=0.85,
                      edgecolor="white", linewidth=0.8, width=0.65)
    for i, (bar, w, nf) in enumerate(zip(bars, all_wmapes, all_nfeats)):
        ax_top.text(bar.get_x() + bar.get_width() / 2, w + 0.3,
                    f"{w:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")
        if nf > 0:
            ax_top.text(bar.get_x() + bar.get_width() / 2, 0.5,
                        f"{nf}f", ha="center", va="bottom", fontsize=8, color="#555")

    ax_top.set_xticks(range(len(all_labels)))
    ax_top.set_xticklabels(all_labels, fontsize=9)
    ax_top.set_ylabel("wMAPE % (lower = better)", fontsize=10)
    ax_top.set_title(
        "Stepwise Ablation — Foundation (M1–M4) · Dec 2025 cutpoint · 13-week OOS",
        fontsize=12, fontweight="bold"
    )
    ax_top.spines[["top", "right"]].set_visible(False)
    total_gain = ma13_wmape - results[-1]["wmape"]
    ax_top.text(0.98, 0.97, f"M1–M4 gain vs. baseline: −{total_gain:.1f}pp",
                transform=ax_top.transAxes, ha="right", va="top", fontsize=9,
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#e3f2fd", edgecolor="#1f77b4", alpha=0.9))

    # Bottom: branch comparison (M5a, M5b, M6, M7) vs M4 baseline
    branch_labels = [r["name"] for r in branch_results]
    branch_wmapes = [r["wmape"] for r in branch_results]
    branch_colors = [r["color"] for r in branch_results]
    branch_nfeats = [r["n_feats"] for r in branch_results]

    bars2 = ax_bot.bar(range(len(branch_wmapes)), branch_wmapes,
                       color=branch_colors, alpha=0.85, edgecolor="white", linewidth=0.8, width=0.55)
    ax_bot.axhline(m4_wmape, color="#8c564b", linewidth=1.4, linestyle="--", alpha=0.7,
                   label=f"M4 baseline ({m4_wmape:.1f}%)")
    ax_bot.axhline(ma13_wmape, color="#9e9e9e", linewidth=1.0, linestyle=":", alpha=0.6,
                   label=f"MA 13wk ({ma13_wmape:.1f}%)")

    for i, (bar, w, nf) in enumerate(zip(bars2, branch_wmapes, branch_nfeats)):
        delta = w - m4_wmape
        color_d = "#2ca02c" if delta < 0 else "#d62728"
        ax_bot.text(bar.get_x() + bar.get_width() / 2, w + 0.15,
                    f"{w:.2f}%", ha="center", va="bottom", fontsize=9.5, fontweight="bold")
        ax_bot.text(bar.get_x() + bar.get_width() / 2, w + 0.6,
                    f"{delta:+.2f}pp", ha="center", va="bottom", fontsize=8.5,
                    color=color_d, fontweight="bold")
        ax_bot.text(bar.get_x() + bar.get_width() / 2, 0.3,
                    f"{nf}f", ha="center", va="bottom", fontsize=8, color="#555")

    ax_bot.set_xticks(range(len(branch_labels)))
    ax_bot.set_xticklabels([f"{r['tag']}\n{r['name']}" for r in branch_results], fontsize=9)
    ax_bot.set_ylabel("wMAPE %", fontsize=10)
    ax_bot.set_title(
        "Mo Intelligence Variants Branching from M4 — Static vs. Rolling vs. YAGO",
        fontsize=11, fontweight="bold"
    )
    ax_bot.legend(fontsize=8.5, loc="upper right")
    ax_bot.spines[["top", "right"]].set_visible(False)

    plt.tight_layout(pad=2)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"    Saved: {os.path.basename(out_path)}")
    return results, branch_results, m4_wmape


# ── Chart 2: Segment breakdown — channel ──────────────────────────────────────

def chart_segment_channel(test_df, pred_static, pred_rolling, pred_best, out_path):
    print("  Channel segment breakdown …")
    channels = [c for c in test_df["channel_outlet"].astype(str).unique()
                if "MULO" not in c.upper() and "MULTI OUTLET" not in c.upper()]
    rows = []
    for ch in sorted(channels):
        mask = test_df["channel_outlet"].astype(str) == ch
        sub  = test_df[mask]
        if sub["base_units"].sum() < 100:
            continue
        rows.append({
            "channel": ch,
            "vol":     sub["base_units"].sum(),
            "ma13":    wmape(sub["base_units"].values, sub["ma13"].values),
            "static":  wmape(sub["base_units"].values, pred_static[mask]),
            "rolling": wmape(sub["base_units"].values, pred_rolling[mask]),
            "best":    wmape(sub["base_units"].values, pred_best[mask]),
        })
    if not rows:
        return pd.DataFrame()
    df_seg = pd.DataFrame(rows).sort_values("vol", ascending=False)

    fig, ax = plt.subplots(figsize=(13, max(5, len(df_seg) * 0.9)))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    y   = np.arange(len(df_seg))
    h   = 0.18
    ax.barh(y + h*1.5, df_seg["ma13"],    height=h, color="#9e9e9e", alpha=0.8, label="MA 13wk baseline")
    ax.barh(y + h*0.5, df_seg["static"],  height=h, color="#e377c2", alpha=0.8, label="M5a Static Mo")
    ax.barh(y - h*0.5, df_seg["rolling"], height=h, color="#17becf", alpha=0.8, label="M5b Rolling Mo")
    ax.barh(y - h*1.5, df_seg["best"],    height=h, color="#bcbd22", alpha=0.8, label="M6 Rolling+YAGO")

    for i, row in df_seg.reset_index(drop=True).iterrows():
        delta = row["rolling"] - row["static"]
        color = "#2ca02c" if delta < 0 else "#d62728"
        ax.text(max(row["ma13"], row["static"], row["rolling"], row["best"]) + 0.3,
                i, f"Δroll {delta:+.1f}pp", va="center", fontsize=7.5, color=color)

    ax.set_yticks(y)
    ax.set_yticklabels(df_seg["channel"], fontsize=9)
    ax.set_xlabel("wMAPE % (lower = better)", fontsize=10)
    ax.set_title("Channel-Level wMAPE: Static vs. Rolling Mo Intelligence\n"
                 "Δroll = M5b Rolling − M5a Static  (negative = rolling wins)",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=8.5, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout(pad=2)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"    Saved: {os.path.basename(out_path)}")
    return df_seg


# ── Chart 3: Segment breakdown — retailer ─────────────────────────────────────

def chart_segment_retailer(test_df, pred_static, pred_rolling, pred_best, out_path, top_n=15):
    print("  Retailer segment breakdown …")
    vol = test_df.groupby("retail_account")["base_units"].sum().sort_values(ascending=False)
    top_accounts = vol.head(top_n).index.tolist()
    rows = []
    for acct in top_accounts:
        mask = test_df["retail_account"] == acct
        sub  = test_df[mask]
        if sub["base_units"].sum() < 100:
            continue
        rows.append({
            "retailer": acct,
            "vol":      sub["base_units"].sum(),
            "static":   wmape(sub["base_units"].values, pred_static[mask]),
            "rolling":  wmape(sub["base_units"].values, pred_rolling[mask]),
            "best":     wmape(sub["base_units"].values, pred_best[mask]),
            "delta":    wmape(sub["base_units"].values, pred_rolling[mask])
                        - wmape(sub["base_units"].values, pred_static[mask]),
        })
    if not rows:
        return pd.DataFrame()
    df_ret = pd.DataFrame(rows).sort_values("vol", ascending=False)

    fig, ax = plt.subplots(figsize=(13, max(6, len(df_ret) * 0.7)))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    y = np.arange(len(df_ret))
    h = 0.28
    ax.barh(y + h*0.5, df_ret["static"],  height=h, color="#e377c2", alpha=0.85, label="M5a Static Mo")
    ax.barh(y - h*0.5, df_ret["rolling"], height=h, color="#17becf", alpha=0.85, label="M5b Rolling Mo")

    for i, row in df_ret.reset_index(drop=True).iterrows():
        color = "#2ca02c" if row["delta"] < 0 else "#d62728"
        ax.text(max(row["static"], row["rolling"]) + 0.2,
                i, f"{row['delta']:+.2f}pp", va="center", fontsize=8, color=color, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{r['retailer']}  ({r['vol']/1e3:.0f}K u)" for _, r in df_ret.iterrows()],
        fontsize=8.5,
    )
    ax.set_xlabel("wMAPE % (lower = better)", fontsize=10)
    ax.set_title(f"Top {top_n} Retailers — Static vs. Rolling Mo Intelligence\n"
                 "Sorted by total test volume  ·  Δ = rolling − static  (negative = rolling wins)",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=9, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout(pad=2)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"    Saved: {os.path.basename(out_path)}")
    return df_ret


# ── Chart 4: Segment breakdown — SKU maturity ─────────────────────────────────

def chart_segment_maturity(test_df, pred_static, pred_rolling, out_path):
    print("  SKU maturity segment breakdown …")
    if "weeks_since_launch" not in test_df.columns:
        print("    weeks_since_launch not available — skipping")
        return pd.DataFrame()
    bins   = [0, 13, 26, 52, 104, 9999]
    labels = ["0–13w\n(launch)", "14–26w\n(ramp)", "27–52w\n(1st yr)",
              "1–2yr\n(mature)", "2yr+\n(established)"]
    test_df = test_df.copy()
    test_df["maturity_bucket"] = pd.cut(test_df["weeks_since_launch"],
                                        bins=bins, labels=labels, right=True)
    rows = []
    for bucket in labels:
        mask = test_df["maturity_bucket"] == bucket
        sub  = test_df[mask]
        if sub["base_units"].sum() < 100:
            continue
        rows.append({
            "bucket":  bucket,
            "n":       mask.sum(),
            "vol":     sub["base_units"].sum(),
            "static":  wmape(sub["base_units"].values, pred_static[mask]),
            "rolling": wmape(sub["base_units"].values, pred_rolling[mask]),
            "delta":   wmape(sub["base_units"].values, pred_rolling[mask])
                       - wmape(sub["base_units"].values, pred_static[mask]),
        })
    if not rows:
        return pd.DataFrame()
    df_mat = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(11, 5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    x = np.arange(len(df_mat))
    w = 0.35
    ax.bar(x - w/2, df_mat["static"],  width=w, color="#e377c2", alpha=0.85, label="M5a Static Mo")
    ax.bar(x + w/2, df_mat["rolling"], width=w, color="#17becf", alpha=0.85, label="M5b Rolling Mo")
    for i, row in df_mat.reset_index(drop=True).iterrows():
        color = "#2ca02c" if row["delta"] < 0 else "#d62728"
        ax.text(i + w/2, row["rolling"] + 0.2,
                f"{row['delta']:+.1f}pp", ha="center", va="bottom",
                fontsize=9, color=color, fontweight="bold")
        ax.text(i, -1.5, f"n={row['n']}", ha="center", va="top", fontsize=7.5, color="#666",
                transform=ax.get_xaxis_transform())
    ax.set_xticks(x)
    ax.set_xticklabels(df_mat["bucket"], fontsize=9)
    ax.set_ylabel("wMAPE % (lower = better)", fontsize=10)
    ax.set_title("SKU Maturity × Mo Intelligence Mode\n"
                 "Rolling signals should help most for mature SKUs with sufficient price/cannibal history",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout(pad=2, rect=[0, 0.05, 1, 1])
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"    Saved: {os.path.basename(out_path)}")
    return df_mat


# ── Chart 5: SHAP for best variant ────────────────────────────────────────────

def chart_shap(model, test_df, feats_used, out_path):
    print("  Computing SHAP values for best variant …")
    try:
        explainer = shap.TreeExplainer(model)
        shap_vals = explainer.shap_values(test_df[feats_used])
        mean_abs  = np.abs(shap_vals).mean(axis=0)
        df_shap   = pd.DataFrame({"feature": feats_used, "mean_abs_shap": mean_abs})
        df_shap   = df_shap.sort_values("mean_abs_shap", ascending=True).tail(25)

        # Layer color mapping
        def feat_color(f):
            if f in LAYER_DEMAND:       return "#1f77b4"
            if f in LAYER_VELOCITY:     return "#2ca02c"
            if f in LAYER_TDP_PRICE:    return "#ff7f0e"
            if f in LAYER_LIFECYCLE:    return "#8c564b"
            if f in LAYER_MO_STATIC:    return "#e377c2"
            if f in LAYER_MO_ROLLING:   return "#17becf"
            if f in LAYER_YAGO:         return "#9467bd"
            return "#aaa"

        colors = [feat_color(f) for f in df_shap["feature"]]

        fig, ax = plt.subplots(figsize=(12, 9))
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(BG)
        bars = ax.barh(df_shap["feature"], df_shap["mean_abs_shap"],
                       color=colors, alpha=0.85, edgecolor="white", linewidth=0.4)
        for bar, v in zip(bars, df_shap["mean_abs_shap"]):
            ax.text(v + 0.0005, bar.get_y() + bar.get_height() / 2,
                    f"{v:.4f}", va="center", ha="left", fontsize=8)

        legend_handles = [
            mpatches.Patch(color="#1f77b4", label="Demand Foundation"),
            mpatches.Patch(color="#2ca02c", label="Per-Store Velocity"),
            mpatches.Patch(color="#ff7f0e", label="TDP & Price"),
            mpatches.Patch(color="#8c564b", label="Lifecycle & Season"),
            mpatches.Patch(color="#e377c2", label="Static Mo (legacy)"),
            mpatches.Patch(color="#17becf", label="Rolling Mo (MO_46)"),
            mpatches.Patch(color="#9467bd", label="YAGO lags"),
        ]
        ax.legend(handles=legend_handles, loc="lower right", fontsize=8.5,
                  title="Feature layer", title_fontsize=9)
        ax.set_xlabel("Mean |SHAP| impact on log-demand prediction", fontsize=10)
        ax.set_title("SHAP Feature Importance — Best Variant\n"
                     "Rolling Mo (teal) vs. Static Mo (pink) relative contribution",
                     fontsize=12, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)
        plt.tight_layout(pad=2)
        fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(fig)
        print(f"    Saved: {os.path.basename(out_path)}")
        return df_shap
    except Exception as e:
        print(f"    SHAP failed: {e}")
        return pd.DataFrame()


# ── HTML Section 19 ────────────────────────────────────────────────────────────

def build_html_section19(chart_paths, foundation_results, branch_results, m4_wmape, ma13_wmape,
                          df_channel, df_retailer, df_maturity):

    def b64(key):
        return img_b64(chart_paths[key]) if key in chart_paths and os.path.exists(chart_paths[key]) else ""

    # Best branch variant (lowest wMAPE)
    best = min(branch_results, key=lambda r: r["wmape"])
    m5a  = next((r for r in branch_results if r["tag"] == "M5a"), None)
    m5b  = next((r for r in branch_results if r["tag"] == "M5b"), None)

    rolling_delta = (m5b["wmape"] - m5a["wmape"]) if m5a and m5b else 0.0
    rolling_verdict = (
        f"Rolling Mo signals improve over static by <strong>{abs(rolling_delta):.2f}pp</strong> wMAPE."
        if rolling_delta < -0.05
        else f"Rolling Mo signals are within {abs(rolling_delta):.2f}pp of static (no material difference at this sample size)."
        if abs(rolling_delta) <= 0.05
        else f"Static Mo signals outperform rolling by <strong>{abs(rolling_delta):.2f}pp</strong> at this cutpoint — investigate rolling signal coverage."
    )

    branch_rows = ""
    for r in branch_results:
        delta = r["wmape"] - m4_wmape
        color = "#16a34a" if delta < -0.05 else "#dc2626" if delta > 0.05 else "#64748b"
        star  = " ★" if r["tag"] == best["tag"] else ""
        branch_rows += (
            f"<tr><td style='padding:.5rem .8rem;font-weight:600'>{r['tag']}{star}</td>"
            f"<td style='padding:.5rem .8rem'>{r['name']}</td>"
            f"<td style='padding:.5rem .8rem;text-align:center'>{r['n_feats']}</td>"
            f"<td style='padding:.5rem .8rem;text-align:center;font-weight:bold'>{r['wmape']:.2f}%</td>"
            f"<td style='padding:.5rem .8rem;text-align:center;color:{color};font-weight:bold'>"
            f"{delta:+.2f}pp</td></tr>"
        )

    channel_rows = ""
    if not df_channel.empty:
        for _, row in df_channel.iterrows():
            d = row.get("rolling", 0) - row.get("static", 0)
            color = "#16a34a" if d < 0 else "#dc2626"
            channel_rows += (
                f"<tr><td style='padding:.4rem .7rem'>{row['channel']}</td>"
                f"<td style='padding:.4rem .7rem;text-align:center'>{row.get('static',0):.2f}%</td>"
                f"<td style='padding:.4rem .7rem;text-align:center'>{row.get('rolling',0):.2f}%</td>"
                f"<td style='padding:.4rem .7rem;text-align:center;color:{color};font-weight:bold'>"
                f"{d:+.2f}pp</td></tr>"
            )

    return f"""
<section id="section19" style="background:white;border-radius:12px;padding:2rem 2.5rem;
  margin:2rem 0;box-shadow:0 2px 12px rgba(0,0,0,.07);font-family:system-ui,sans-serif">

<h2 style="font-size:1.4rem;font-weight:700;color:#0f172a;border-bottom:2px solid #e2e8f0;
  padding-bottom:.6rem;margin-bottom:1.5rem">
  19 · Rolling vs. Static Mo Intelligence — Feature Ablation Study (MO_50)
</h2>

<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:1rem 1.4rem;margin-bottom:1.5rem">
  <strong>Research question:</strong> MO_41 established that the three static Mo Intelligence
  signals (implied_elasticity, max_donor_cannibal_prob, donor_count) have ICC = 1.0 — they
  act as fixed-effect intercept adjustments, not time-varying signals. MO_46 replaced these
  with rolling weekly signals (rolling_cannibal_pressure, rolling_cannibal_trend,
  rolling_elasticity). This study tests whether the time-varying replacements improve
  portfolio-level wMAPE, and where the gains are largest by channel, retailer, and SKU maturity.
</div>

<h3 style="font-size:1.1rem;margin-top:1.5rem">19.1 Foundation Ablation (M1–M4) — Baseline Established</h3>
<p style="font-size:.9rem;color:#475569">Same M1–M4 steps as MO_41. M4 (Lifecycle & Season, 24 features)
is the branching point for Mo Intelligence variants.</p>
<table style="width:100%;border-collapse:collapse;font-size:.88rem;margin-bottom:1.2rem">
  <thead><tr style="background:#1e293b;color:white">
    <th style="padding:.5rem .8rem">Step</th><th style="padding:.5rem .8rem">Name</th>
    <th style="padding:.5rem .8rem;text-align:center">Features</th>
    <th style="padding:.5rem .8rem;text-align:center">wMAPE</th>
    <th style="padding:.5rem .8rem;text-align:center">vs. Prior</th>
  </tr></thead>
  <tbody>
    <tr style="background:#f1f5f9"><td style="padding:.5rem .8rem">MA 13wk</td>
      <td style="padding:.5rem .8rem">Baseline (Excel-equivalent)</td>
      <td style="padding:.5rem .8rem;text-align:center">0</td>
      <td style="padding:.5rem .8rem;text-align:center;font-weight:bold;color:#dc2626">{ma13_wmape:.2f}%</td>
      <td style="padding:.5rem .8rem;text-align:center">—</td></tr>
    {"".join(
        f"<tr style='background:{'white' if i%2==0 else '#f8fafc'}'>"
        f"<td style='padding:.5rem .8rem;font-weight:600'>{r['tag']}</td>"
        f"<td style='padding:.5rem .8rem'>{r['name']}</td>"
        f"<td style='padding:.5rem .8rem;text-align:center'>{r['n_feats']}</td>"
        f"<td style='padding:.5rem .8rem;text-align:center;font-weight:bold'>{r['wmape']:.2f}%</td>"
        f"<td style='padding:.5rem .8rem;text-align:center;color:#16a34a;font-weight:bold'>"
        f"{r['wmape'] - (ma13_wmape if i == 0 else foundation_results[i-1]['wmape']):+.2f}pp</td></tr>"
        for i, r in enumerate(foundation_results)
    )}
  </tbody>
</table>

<h3 style="font-size:1.1rem;margin-top:1.5rem">19.2 Mo Intelligence Variants — Branching from M4 ({m4_wmape:.2f}%)</h3>
<div style="background:#fefce8;border:1px solid #fde047;border-radius:8px;
  padding:.8rem 1.2rem;margin-bottom:1rem;font-size:.88rem">
  {rolling_verdict}
  Best variant: <strong>{best['tag']} — {best['name']}</strong> at {best['wmape']:.2f}% wMAPE.
  ★ marks best performer.
</div>
<table style="width:100%;border-collapse:collapse;font-size:.88rem;margin-bottom:1.2rem">
  <thead><tr style="background:#1e293b;color:white">
    <th style="padding:.5rem .8rem">Variant</th><th style="padding:.5rem .8rem">Mo Signals Used</th>
    <th style="padding:.5rem .8rem;text-align:center">Total Features</th>
    <th style="padding:.5rem .8rem;text-align:center">wMAPE</th>
    <th style="padding:.5rem .8rem;text-align:center">vs. M4 baseline</th>
  </tr></thead>
  <tbody>{branch_rows}</tbody>
</table>
<img src="data:image/png;base64,{b64('ablation')}"
  style="width:100%;max-width:1100px;display:block;margin:0 auto 2rem"
  alt="Extended ablation waterfall">

<h3 style="font-size:1.1rem;margin-top:1.5rem">19.3 Channel-Level Breakdown — Where Rolling Signals Help</h3>
<p style="font-size:.88rem;color:#475569">Negative Δ = rolling Mo outperforms static Mo for that channel.</p>
{"<table style='width:100%;border-collapse:collapse;font-size:.86rem;margin-bottom:1rem'><thead><tr style='background:#1e293b;color:white'><th style='padding:.4rem .7rem'>Channel</th><th style='padding:.4rem .7rem;text-align:center'>Static wMAPE</th><th style='padding:.4rem .7rem;text-align:center'>Rolling wMAPE</th><th style='padding:.4rem .7rem;text-align:center'>Δ (rolling − static)</th></tr></thead><tbody>" + channel_rows + "</tbody></table>" if channel_rows else "<p style='color:#64748b;font-size:.88rem'>Channel breakdown not available.</p>"}
<img src="data:image/png;base64,{b64('channel')}"
  style="width:100%;max-width:1000px;display:block;margin:0 auto 2rem"
  alt="Channel segment breakdown">

<h3 style="font-size:1.1rem;margin-top:1.5rem">19.4 Retailer-Level Breakdown — Top 15 by Volume</h3>
<img src="data:image/png;base64,{b64('retailer')}"
  style="width:100%;max-width:1000px;display:block;margin:0 auto 2rem"
  alt="Retailer segment breakdown">

<h3 style="font-size:1.1rem;margin-top:1.5rem">19.5 SKU Maturity — Rolling Signals Need History</h3>
<p style="font-size:.88rem;color:#475569">Rolling cannibalization pressure requires ≥ 8 weeks of
donor history; rolling elasticity requires ≥ 13 weeks. Launch-phase SKUs (0–13w) will have mostly
NaN rolling features — LightGBM handles NaN natively by learning a split direction.</p>
<img src="data:image/png;base64,{b64('maturity')}"
  style="width:100%;max-width:900px;display:block;margin:0 auto 2rem"
  alt="SKU maturity breakdown">

<h3 style="font-size:1.1rem;margin-top:1.5rem">19.6 SHAP Feature Importance — Best Variant</h3>
<p style="font-size:.88rem;color:#475569">Teal bars = MO_46 rolling signals.
  Pink bars = legacy static Mo signals. Purple = YAGO lags.
  Rolling Mo features with high mean |SHAP| confirm genuine week-to-week predictive contribution.</p>
<img src="data:image/png;base64,{b64('shap')}"
  style="width:100%;max-width:1000px;display:block;margin:0 auto 2rem"
  alt="SHAP feature importance">

<h3 style="font-size:1.1rem;margin-top:1.5rem">19.7 Coverage Notes</h3>
<ul style="font-size:.88rem;line-height:1.8;color:#374151">
  <li><strong>rolling_cannibal_pressure:</strong> available only for series with ≥ 1 active donor in
      scored_cannibalization — approximately 27% of rows. NaN rows are handled natively by LightGBM.</li>
  <li><strong>rolling_elasticity:</strong> requires ≥ 13 weeks of price variation above $0.05 guardrail —
      approximately 68% of rows valid.</li>
  <li><strong>YAGO lags (lag52):</strong> require ≥ 52 weeks of history — excluded for all 2024+ launches.</li>
  <li>Segment-level wMAPE differences below ±0.5pp at this sample size should be treated as noise,
      not signal. Material improvements (≥ 1pp) on high-volume segments are actionable.</li>
</ul>
</section>
"""


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("MO_50 — Rolling vs. Static Mo Intelligence Feature Ablation")
    print("=" * 70)

    # ── Load data ──────────────────────────────────────────────────────────────
    print(f"\nLoading {PARQUET} …")
    df = pd.read_parquet(PARQUET)
    df["__time"]       = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    df["log_base_units"] = np.log1p(df["base_units"].clip(lower=0))

    # Encode categoricals
    df["channel_outlet"] = df["channel_outlet"].astype("category")
    df["channel_encoded"] = df["channel_outlet"].cat.codes.astype(float)

    # Drop MULO rows (same as MO_41)
    mulo_mask = (
        df["channel_outlet"].astype(str).str.contains("MULTI OUTLET|MULO", case=False, na=False) |
        df["geography_raw"].astype(str).str.contains("MULTI OUTLET|MULO|TOTAL US|ALL CHANNEL", case=False, na=False)
    )
    df = df[~mulo_mask].reset_index(drop=True)

    # Numeric coercion for all non-channel features
    all_feats = (LAYER_DEMAND + LAYER_VELOCITY + LAYER_TDP_PRICE + LAYER_LIFECYCLE
                 + LAYER_MO_STATIC + LAYER_MO_ROLLING + LAYER_YAGO)
    for c in all_feats:
        if c != "channel_outlet" and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            # Rolling signals: leave NaN (LightGBM handles natively)
            # Non-rolling: fill NaN with 0
            if c not in LAYER_MO_ROLLING:
                df[c] = df[c].fillna(0.0)

    print(f"  Rows: {len(df):,}  |  Series: {df.groupby(GROUP_COLS).ngroups:,}")

    # ── Dec 2025 cutpoint qualification (same as MO_41) ───────────────────────
    cutoff_utc = DEC2025_CUTOFF.tz_localize("UTC")
    train_counts = df[df["__time"] <  cutoff_utc].groupby(GROUP_COLS).size()
    test_counts  = df[df["__time"] >= cutoff_utc].groupby(GROUP_COLS).size()
    coverage = pd.concat([train_counts.rename("tr"), test_counts.rename("te")],
                          axis=1).fillna(0).astype(int)
    qualifying = coverage[(coverage["tr"] >= MIN_TRAIN_WEEKS) & (coverage["te"] >= MIN_TEST_WEEKS)]
    qual_keys  = set(qualifying.index.tolist())
    df["_key"] = list(zip(df["upc"], df["channel_outlet"].astype(str),
                           df["retail_account"], df["geography_raw"]))
    df_cp = df[df["_key"].isin(qual_keys)].copy()

    train_all = df_cp[df_cp["__time"] <  cutoff_utc].copy()
    test_all  = df_cp[df_cp["__time"] >= cutoff_utc].copy()
    test_dates = sorted(test_all["__time"].unique())[:H]
    test_df    = test_all[test_all["__time"].isin(test_dates)].copy().reset_index(drop=True)

    val_cut  = cutoff_utc - pd.Timedelta(weeks=8)
    super_tr = train_all[train_all["__time"] <  val_cut].copy()
    val_df   = train_all[train_all["__time"] >= val_cut].copy()

    # MA 13wk baseline
    ma13_by_series = (
        train_all.groupby(GROUP_COLS)["base_units"]
        .apply(lambda s: s.tail(13).mean()).reset_index(name="ma13")
    )
    test_df = test_df.merge(ma13_by_series, on=GROUP_COLS, how="left")
    ma13_wmape_val = wmape(test_df["base_units"].values, test_df["ma13"].values)

    print(f"  Qualifying series: {len(qualifying):,}")
    print(f"  Train: {len(super_tr):,}  |  Val: {len(val_df):,}  |  Test: {len(test_df):,}")
    print(f"  MA 13wk wMAPE: {ma13_wmape_val:.2f}%")

    # ── Rolling signal coverage report ────────────────────────────────────────
    for sig in LAYER_MO_ROLLING:
        if sig in test_df.columns:
            cov = test_df[sig].notna().mean() * 100
            print(f"  {sig} coverage in test: {cov:.1f}%")

    # ── Chart 1: Ablation ─────────────────────────────────────────────────────
    print("\n[1/5] Extended ablation study …")
    abl_out = os.path.join(OUTPUT_DIR, "v2_mo50_ablation.png")
    foundation_results, branch_results, m4_wmape = chart_ablation(
        super_tr, val_df, test_df, ma13_wmape_val, abl_out
    )

    # Identify predictions for segment charts
    best_br = min(branch_results, key=lambda r: r["wmape"])
    m5a_br  = next((r for r in branch_results if r["tag"] == "M5a"), branch_results[0])
    m5b_br  = next((r for r in branch_results if r["tag"] == "M5b"), branch_results[1])
    m6_br   = next((r for r in branch_results if r["tag"] == "M6"),  best_br)

    # ── Enrich test_df with predictions ───────────────────────────────────────
    test_df = test_df.reset_index(drop=True)
    pred_static  = np.array(m5a_br["preds"])
    pred_rolling = np.array(m5b_br["preds"])
    pred_best    = np.array(m6_br["preds"])

    # ── Chart 2: Channel ──────────────────────────────────────────────────────
    print("\n[2/5] Channel segment breakdown …")
    ch_out = os.path.join(OUTPUT_DIR, "v2_mo50_segment_channel.png")
    df_channel = chart_segment_channel(test_df, pred_static, pred_rolling, pred_best, ch_out)

    # ── Chart 3: Retailer ─────────────────────────────────────────────────────
    print("\n[3/5] Retailer segment breakdown …")
    ret_out = os.path.join(OUTPUT_DIR, "v2_mo50_segment_retailer.png")
    df_retailer = chart_segment_retailer(test_df, pred_static, pred_rolling, pred_best, ret_out)

    # ── Chart 4: SKU maturity ─────────────────────────────────────────────────
    print("\n[4/5] SKU maturity breakdown …")
    mat_out = os.path.join(OUTPUT_DIR, "v2_mo50_segment_maturity.png")
    df_maturity = chart_segment_maturity(test_df, pred_static, pred_rolling, mat_out)

    # ── Chart 5: SHAP ─────────────────────────────────────────────────────────
    print("\n[5/5] SHAP analysis on best variant …")
    shap_out = os.path.join(OUTPUT_DIR, "v2_mo50_shap.png")
    # Retrain best variant on full train (not super_tr) for SHAP
    best_feats = best_br["feats"]
    _, _, best_model, feats_used = train_eval(train_all, val_df, test_df, best_feats)
    df_shap = chart_shap(best_model, test_df, feats_used, shap_out)

    # ── Save CSV ──────────────────────────────────────────────────────────────
    csv_rows = []
    for r in foundation_results:
        csv_rows.append({"phase": "foundation", **{k: v for k, v in r.items() if k != "preds"}})
    for r in branch_results:
        csv_rows.append({"phase": "branch", **{k: v for k, v in r.items() if k not in ("preds", "feats")}})
    pd.DataFrame(csv_rows).to_csv(
        os.path.join(OUTPUT_DIR, "mo50_ablation_results.csv"), index=False
    )
    print("  Saved: mo50_ablation_results.csv")

    # ── Patch HTML ────────────────────────────────────────────────────────────
    chart_paths = {
        "ablation": abl_out,
        "channel":  ch_out,
        "retailer": ret_out,
        "maturity": mat_out,
        "shap":     shap_out,
    }
    section19 = build_html_section19(
        chart_paths, foundation_results, branch_results, m4_wmape, ma13_wmape_val,
        df_channel, df_retailer, df_maturity,
    )

    print("\n[MO_50] Patching HTML report …")
    with open(HTML_IN, "r", encoding="utf-8") as f:
        html = f.read()
    ANCHOR = "<!-- END SECTIONS -->"
    if ANCHOR in html:
        html = html.replace(ANCHOR, section19 + "\n" + ANCHOR)
    else:
        html = html.replace("</body>", section19 + "\n</body>")
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)
    size_mb = os.path.getsize(HTML_OUT) / 1_048_576
    print(f"[MO_50] HTML patched → {HTML_OUT}  ({size_mb:.1f} MB)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("MO_50 COMPLETE")
    print("=" * 70)
    print(f"  MA 13wk baseline wMAPE:  {ma13_wmape_val:.2f}%")
    print(f"  M4 foundation wMAPE:     {m4_wmape:.2f}%")
    for r in branch_results:
        delta = r["wmape"] - m4_wmape
        star  = " ← BEST" if r["tag"] == best_br["tag"] else ""
        print(f"  {r['tag']} ({r['name']}): {r['wmape']:.2f}%  ({delta:+.2f}pp vs M4){star}")
    print()
    print("Next: review results, then wire best variant into MO_26 FEATURE_COLS")
    print("      if rolling signals show material improvement.")


if __name__ == "__main__":
    main()
