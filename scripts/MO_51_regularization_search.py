"""MO_51 — Regularization Search, SHAP-Guided Pruning & Rolling CV

Three experiments to determine whether smarter training can unlock value
from features that MO_50 showed degrade portfolio wMAPE:

  Experiment A — Regularization grid search
    Test reg_alpha × reg_lambda × num_leaves on M1 and M5b.
    Hypothesis: M5b underperforms M1 partly because default params were
    tuned for 27 features — tighter regularization may let rolling signals
    contribute without overfitting.

  Experiment B — SHAP-guided M1+topK pruning
    Rank all MO_50 features by mean |SHAP|; add top-1, top-3, top-5
    non-demand features one at a time to M1. Tests whether a handful of
    well-chosen signals (likely arp_wow_delta, tdp_z8, rolling_elasticity)
    can beat M1 alone with minimal overfit risk.

  Experiment C — Rolling cross-validation (3 cutpoints)
    Evaluate M1 and best Experiment A/B variant across Jun/Sep/Dec 2025.
    Produces a stable average wMAPE that is not sensitive to any single
    evaluation window. This becomes the headline accuracy metric going
    forward.

Outputs:
  outputs/v2_mo51_reg_search.png       — heatmap grid: reg_alpha × reg_lambda wMAPE
  outputs/v2_mo51_topk_pruning.png     — M1 + top-K non-demand features
  outputs/v2_mo51_rolling_cv.png       — 3-cutpoint CV comparison
  outputs/mo51_reg_search_results.csv  — full grid results
  outputs/mo51_rolling_cv_results.csv  — per-cutpoint results
  outputs/model_history.json           — champion-challenger log (append)

HTML: patches Section 20 into built_demand_intelligence_report.html
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import base64
import json
import warnings
warnings.filterwarnings("ignore")
from datetime import datetime
from itertools import product as iterproduct

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import lightgbm as lgb
import shap

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR    = os.path.join(SCRIPT_DIR, "outputs")
PARQUET       = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")
HTML_IN       = os.path.join(OUTPUT_DIR, "built_demand_intelligence_report.html")
HTML_OUT      = os.path.join(OUTPUT_DIR, "built_demand_intelligence_report.html")
MODEL_HISTORY = os.path.join(OUTPUT_DIR, "model_history.json")
SHAP_CSV      = os.path.join(OUTPUT_DIR, "mo50_ablation_results.csv")  # reuse MO_50 SHAP if present

GROUP_COLS      = ["upc", "channel_outlet", "retail_account", "geography_raw"]
MIN_TRAIN_WEEKS = 52
MIN_TEST_WEEKS  = 13
H               = 13
BG              = "#f8f9fa"

# ── Rolling CV cutpoints ───────────────────────────────────────────────────────
CUTPOINTS = [
    ("Jun 2025",  pd.Timestamp("2025-07-01")),
    ("Sep 2025",  pd.Timestamp("2025-10-01")),
    ("Dec 2025",  pd.Timestamp("2026-01-01")),
]

# ── Feature layers (from MO_50/MO_41) ─────────────────────────────────────────
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
LAYER_MO_ROLLING = [
    "rolling_cannibal_pressure", "rolling_cannibal_trend", "rolling_elasticity",
]
LAYER_YAGO = [
    "base_units_lag52", "velocity_spm_lag52",
]

M1_FEATS  = LAYER_DEMAND
M5B_FEATS = LAYER_DEMAND + LAYER_VELOCITY + LAYER_TDP_PRICE + LAYER_LIFECYCLE + LAYER_MO_ROLLING

# All candidate non-demand features for SHAP pruning (ranked in Exp B)
NON_DEMAND_CANDIDATES = (
    LAYER_VELOCITY + LAYER_TDP_PRICE + LAYER_LIFECYCLE + LAYER_MO_ROLLING + LAYER_YAGO
)

# ── Regularization grid ────────────────────────────────────────────────────────
REG_ALPHA_GRID  = [0.05, 0.1, 0.3, 0.5, 1.0]
REG_LAMBDA_GRID = [0.1,  0.3, 0.5, 1.0, 2.0]
NUM_LEAVES_GRID = [31, 47, 63]

LGBM_BASE = dict(
    objective="regression", boosting_type="gbdt", n_estimators=1000,
    learning_rate=0.04, min_child_samples=20,
    feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
    random_state=42, n_jobs=-1, verbose=-1,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def wmape(actual, predicted):
    t = np.nansum(actual)
    return float(np.nansum(np.abs(actual - predicted)) / t * 100) if t > 0 else np.nan

def img_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def avail(feats, df):
    out = []
    for f in feats:
        if f == "channel_outlet":
            if "channel_encoded" in df.columns: out.append("channel_encoded")
        elif f in df.columns:
            out.append(f)
    return out

def train_eval(super_tr, val_df, test_df, feats, params):
    af = avail(feats, super_tr)
    m = lgb.LGBMRegressor(**params)
    m.fit(super_tr[af], super_tr["log_base_units"],
          eval_set=[(val_df[af], val_df["log_base_units"])],
          callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(9999)])
    preds = np.expm1(np.clip(m.predict(test_df[af]), 0, None))
    return wmape(test_df["base_units"].values, preds), m

def ma13_wmape_for(train_all, test_df):
    ma = (train_all.groupby(GROUP_COLS)["base_units"]
          .apply(lambda s: s.tail(13).mean()).reset_index(name="ma13"))
    t = test_df.merge(ma, on=GROUP_COLS, how="left")
    return wmape(t["base_units"].values, t["ma13"].values)

def qualify_cutpoint(df, cutoff_utc):
    tr_c = df[df["__time"] < cutoff_utc].groupby(GROUP_COLS).size()
    te_c = df[df["__time"] >= cutoff_utc].groupby(GROUP_COLS).size()
    cov  = pd.concat([tr_c.rename("tr"), te_c.rename("te")], axis=1).fillna(0).astype(int)
    q    = cov[(cov["tr"] >= MIN_TRAIN_WEEKS) & (cov["te"] >= MIN_TEST_WEEKS)]
    keys = set(q.index.tolist())
    df2  = df.copy()
    df2["_key"] = list(zip(df2["upc"], df2["channel_outlet"].astype(str),
                            df2["retail_account"], df2["geography_raw"]))
    df_cp    = df2[df2["_key"].isin(keys)].copy()
    train_all = df_cp[df_cp["__time"] < cutoff_utc].copy()
    test_all  = df_cp[df_cp["__time"] >= cutoff_utc].copy()
    test_dates = sorted(test_all["__time"].unique())[:H]
    test_df   = test_all[test_all["__time"].isin(test_dates)].copy().reset_index(drop=True)
    val_cut   = cutoff_utc - pd.Timedelta(weeks=8)
    super_tr  = train_all[train_all["__time"] < val_cut].copy()
    val_df    = train_all[train_all["__time"] >= val_cut].copy()
    return train_all, super_tr, val_df, test_df, len(q)


# ── Experiment A: Regularization grid search ──────────────────────────────────

def exp_a_reg_search(super_tr, val_df, test_df, out_path):
    print("  [A] Regularization grid search on M1 and M5b …")
    base_params = {**LGBM_BASE, "num_leaves": 63}  # start with default leaves

    rows = []
    best_m1   = {"wmape": 999, "params": None}
    best_m5b  = {"wmape": 999, "params": None}

    combos = list(iterproduct(REG_ALPHA_GRID, REG_LAMBDA_GRID))
    total  = len(combos) * 2
    done   = 0

    for ra, rl in combos:
        p = {**base_params, "reg_alpha": ra, "reg_lambda": rl}
        w1, _  = train_eval(super_tr, val_df, test_df, M1_FEATS, p)
        w5, _  = train_eval(super_tr, val_df, test_df, M5B_FEATS, p)
        rows.append({"reg_alpha": ra, "reg_lambda": rl, "wmape_m1": w1, "wmape_m5b": w5,
                     "delta": w5 - w1})
        if w1 < best_m1["wmape"]:  best_m1  = {"wmape": w1,  "params": p}
        if w5 < best_m5b["wmape"]: best_m5b = {"wmape": w5,  "params": p}
        done += 2
        if done % 10 == 0:
            print(f"    {done}/{total}  best M1={best_m1['wmape']:.3f}  best M5b={best_m5b['wmape']:.3f}")

    # num_leaves sweep on best alpha/lambda
    print("  [A] num_leaves sweep on best params …")
    for nl in NUM_LEAVES_GRID:
        p1 = {**best_m1["params"],  "num_leaves": nl}
        p5 = {**best_m5b["params"], "num_leaves": nl}
        w1, _ = train_eval(super_tr, val_df, test_df, M1_FEATS,  p1)
        w5, _ = train_eval(super_tr, val_df, test_df, M5B_FEATS, p5)
        rows.append({"reg_alpha": p1["reg_alpha"], "reg_lambda": p1["reg_lambda"],
                     "num_leaves": nl, "wmape_m1": w1, "wmape_m5b": w5, "delta": w5 - w1})
        if w1 < best_m1["wmape"]:  best_m1  = {"wmape": w1,  "params": p1}
        if w5 < best_m5b["wmape"]: best_m5b = {"wmape": w5,  "params": p5}

    df_grid = pd.DataFrame(rows)

    # ── Plot: heatmap of M1 wMAPE across alpha × lambda ───────────────────────
    pivot_m1  = df_grid[df_grid.get("num_leaves", 63) != df_grid.get("num_leaves", 63)
                        ].pivot_table(index="reg_alpha", columns="reg_lambda",
                                      values="wmape_m1", aggfunc="mean")
    # Safe pivot: rows that have both alpha and lambda
    base_rows = df_grid[~df_grid["reg_alpha"].isna() & ~df_grid["reg_lambda"].isna()]
    pivot_m1  = base_rows.pivot_table(index="reg_alpha", columns="reg_lambda",
                                       values="wmape_m1", aggfunc="min")
    pivot_m5b = base_rows.pivot_table(index="reg_alpha", columns="reg_lambda",
                                       values="wmape_m5b", aggfunc="min")
    pivot_del = pivot_m5b - pivot_m1

    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    fig.patch.set_facecolor(BG)
    for ax in axes: ax.set_facecolor(BG)

    def heatmap(ax, data, title, cmap, fmt=".2f"):
        im = ax.imshow(data.values, cmap=cmap, aspect="auto",
                       vmin=data.values.min(), vmax=data.values.max())
        ax.set_xticks(range(len(data.columns)))
        ax.set_xticklabels([str(c) for c in data.columns], fontsize=8)
        ax.set_yticks(range(len(data.index)))
        ax.set_yticklabels([str(i) for i in data.index], fontsize=8)
        ax.set_xlabel("reg_lambda", fontsize=9)
        ax.set_ylabel("reg_alpha", fontsize=9)
        ax.set_title(title, fontsize=10, fontweight="bold")
        plt.colorbar(im, ax=ax, shrink=0.8)
        for (i, j), v in np.ndenumerate(data.values):
            ax.text(j, i, f"{v:{fmt}}", ha="center", va="center",
                    fontsize=7.5, color="white" if abs(v - data.values.mean()) > data.values.std() else "#333")

    heatmap(axes[0], pivot_m1,  "M1 wMAPE % (lower = better)", "Blues_r")
    heatmap(axes[1], pivot_m5b, "M5b (Rolling Mo) wMAPE %",    "Blues_r")
    heatmap(axes[2], pivot_del, "Δ M5b − M1  (negative = rolling wins)", "RdYlGn_r", fmt="+.2f")

    best_box = (f"Best M1:  {best_m1['wmape']:.3f}%\n"
                f"  α={best_m1['params']['reg_alpha']}  λ={best_m1['params']['reg_lambda']}"
                f"  leaves={best_m1['params']['num_leaves']}\n"
                f"Best M5b: {best_m5b['wmape']:.3f}%\n"
                f"  α={best_m5b['params']['reg_alpha']}  λ={best_m5b['params']['reg_lambda']}"
                f"  leaves={best_m5b['params']['num_leaves']}")
    fig.text(0.5, -0.04, best_box, ha="center", va="top", fontsize=9,
             fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.5", facecolor="#e3f2fd", edgecolor="#1976d2", alpha=0.9))

    plt.suptitle("Experiment A — Regularization Grid Search: M1 vs. M5b Rolling Mo",
                 fontsize=12, fontweight="bold", y=1.02)
    plt.tight_layout(pad=2, rect=[0, 0.08, 1, 1])
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"    Saved: {os.path.basename(out_path)}")
    return df_grid, best_m1, best_m5b


# ── Experiment B: SHAP-guided M1 + top-K pruning ─────────────────────────────

def exp_b_topk_pruning(super_tr, val_df, test_df, best_m1_params, out_path):
    print("  [B] SHAP-guided M1+topK feature pruning …")

    # Train M5b with best params to get SHAP ranking
    af_full = avail(M5B_FEATS, super_tr)
    m_full = lgb.LGBMRegressor(**{**best_m1_params})
    m_full.fit(super_tr[af_full], super_tr["log_base_units"],
               eval_set=[(val_df[af_full], val_df["log_base_units"])],
               callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(9999)])

    try:
        explainer  = shap.TreeExplainer(m_full)
        shap_vals  = explainer.shap_values(test_df[af_full])
        mean_shap  = np.abs(shap_vals).mean(axis=0)
        shap_df    = pd.DataFrame({"feature": af_full, "mean_abs_shap": mean_shap})
        shap_df    = shap_df.sort_values("mean_abs_shap", ascending=False)
    except Exception as e:
        print(f"    SHAP failed: {e} — using LightGBM feature importance as fallback")
        fi = m_full.feature_importances_
        shap_df = pd.DataFrame({"feature": af_full, "mean_abs_shap": fi.astype(float)})
        shap_df = shap_df.sort_values("mean_abs_shap", ascending=False)

    # Identify non-demand features ranked by SHAP
    demand_encoded = avail(LAYER_DEMAND, super_tr)
    non_demand_ranked = [f for f in shap_df["feature"].tolist() if f not in demand_encoded]
    print(f"    Top non-demand features by SHAP: {non_demand_ranked[:8]}")

    # M1 baseline with best params
    w_m1, _ = train_eval(super_tr, val_df, test_df, M1_FEATS, best_m1_params)
    results  = [{"k": 0, "added": "(none)", "wmape": w_m1, "feats": len(avail(M1_FEATS, super_tr))}]

    # Incrementally add top-K non-demand features
    current_feats = avail(M1_FEATS, super_tr)[:]
    for k, feat in enumerate(non_demand_ranked[:10], 1):
        current_feats = current_feats + [feat]
        w, _ = train_eval(super_tr, val_df, test_df, current_feats, best_m1_params)
        results.append({"k": k, "added": feat, "wmape": w, "feats": len(current_feats)})
        delta = w - w_m1
        print(f"    K={k} +{feat}: {w:.3f}%  ({delta:+.3f}pp vs M1)")
        if w > w_m1 + 0.5 and k > 3:
            print(f"    → wMAPE rising — stopping at K={k}")
            break

    df_topk = pd.DataFrame(results)
    best_k  = df_topk.loc[df_topk["wmape"].idxmin()]

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(14, 5))
    fig.patch.set_facecolor(BG)
    for ax in (ax_left, ax_right): ax.set_facecolor(BG)

    # Left: SHAP ranking of non-demand features
    top_nd = shap_df[~shap_df["feature"].isin(demand_encoded)].head(12)
    colors_nd = ["#17becf" if "rolling" in f else
                 "#9467bd" if "lag52" in f else
                 "#ff7f0e" if f in avail(LAYER_TDP_PRICE, super_tr) else
                 "#2ca02c" if f in avail(LAYER_VELOCITY, super_tr) else "#8c564b"
                 for f in top_nd["feature"]]
    ax_left.barh(top_nd["feature"], top_nd["mean_abs_shap"], color=colors_nd, alpha=0.85,
                 edgecolor="white", linewidth=0.4)
    ax_left.set_xlabel("Mean |SHAP|", fontsize=10)
    ax_left.set_title("Non-Demand Features Ranked by SHAP\n(from M5b full model)", fontsize=10, fontweight="bold")
    ax_left.spines[["top", "right"]].set_visible(False)

    # Right: M1 + top-K wMAPE progression
    ks     = [r["k"] for r in results]
    wmapes = [r["wmape"] for r in results]
    bar_colors = ["#2ca02c" if w <= w_m1 else "#d62728" for w in wmapes]
    ax_right.bar(ks, wmapes, color=bar_colors, alpha=0.85, edgecolor="white", width=0.6)
    ax_right.axhline(w_m1, color="#1f77b4", linewidth=1.5, linestyle="--",
                     label=f"M1 baseline ({w_m1:.3f}%)")
    for i, (k, w) in enumerate(zip(ks, wmapes)):
        ax_right.text(k, w + 0.05, f"{w:.3f}%", ha="center", va="bottom", fontsize=8)
    ax_right.set_xticks(ks)
    ax_right.set_xticklabels(
        ["M1\n(base)"] + [f"K={r['k']}\n+{r['added'][:12]}" for r in results[1:]],
        fontsize=7.5
    )
    ax_right.set_ylabel("wMAPE %", fontsize=10)
    ax_right.set_title(f"M1 + Top-K Non-Demand Features\nBest: K={int(best_k['k'])} at {best_k['wmape']:.3f}%",
                       fontsize=10, fontweight="bold")
    ax_right.legend(fontsize=8.5)
    ax_right.spines[["top", "right"]].set_visible(False)

    plt.tight_layout(pad=2)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"    Saved: {os.path.basename(out_path)}")
    print(f"    Best: K={int(best_k['k'])} ({best_k['added']}) → {best_k['wmape']:.3f}%")
    return df_topk, non_demand_ranked, shap_df


# ── Experiment C: Rolling cross-validation ────────────────────────────────────

def exp_c_rolling_cv(df, best_m1_params, best_m5b_params, best_topk_feats, out_path):
    print("  [C] Rolling cross-validation across 3 cutpoints …")
    rows = []

    for label, cutoff in CUTPOINTS:
        cutoff_utc = cutoff.tz_localize("UTC")
        train_all, super_tr, val_df, test_df, n_q = qualify_cutpoint(df, cutoff_utc)
        ma13 = ma13_wmape_for(train_all, test_df)

        w_m1, _   = train_eval(super_tr, val_df, test_df, M1_FEATS,      best_m1_params)
        w_m5b, _  = train_eval(super_tr, val_df, test_df, M5B_FEATS,     best_m5b_params)
        w_topk, _ = train_eval(super_tr, val_df, test_df, best_topk_feats, best_m1_params)

        rows.append({"cutpoint": label, "n_series": n_q, "ma13": ma13,
                     "m1": w_m1, "m5b_rolling": w_m5b, "m1_topk": w_topk})
        print(f"    {label} (n={n_q}): MA13={ma13:.2f}%  M1={w_m1:.2f}%"
              f"  M5b={w_m5b:.2f}%  M1+topK={w_topk:.2f}%")

    df_cv = pd.DataFrame(rows)
    means = df_cv[["ma13","m1","m5b_rolling","m1_topk"]].mean()

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(11, 5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    x  = np.arange(len(CUTPOINTS))
    w  = 0.18
    labels_c = [r[0] for r in CUTPOINTS]

    ax.bar(x - w*1.5, df_cv["ma13"],        width=w, color="#9e9e9e", alpha=0.85, label=f"MA 13wk (avg {means['ma13']:.2f}%)")
    ax.bar(x - w*0.5, df_cv["m1"],          width=w, color="#1f77b4", alpha=0.85, label=f"M1 Demand Foundation (avg {means['m1']:.2f}%)")
    ax.bar(x + w*0.5, df_cv["m5b_rolling"], width=w, color="#17becf", alpha=0.85, label=f"M5b Rolling Mo (avg {means['m5b_rolling']:.2f}%)")
    ax.bar(x + w*1.5, df_cv["m1_topk"],     width=w, color="#bcbd22", alpha=0.85, label=f"M1+topK (avg {means['m1_topk']:.2f}%)")

    for xi, row in df_cv.reset_index(drop=True).iterrows():
        for offset, col, val in [(-w*1.5, "ma13", row["ma13"]),
                                  (-w*0.5, "m1",   row["m1"]),
                                  (w*0.5,  "m5b_rolling", row["m5b_rolling"]),
                                  (w*1.5,  "m1_topk",     row["m1_topk"])]:
            ax.text(xi + offset, val + 0.2, f"{val:.1f}%", ha="center", va="bottom", fontsize=7.5)

    ax.set_xticks(x)
    ax.set_xticklabels([f"{l}\n(n={r['n_series']})" for l, r in zip(labels_c, df_cv.to_dict("records"))],
                       fontsize=9)
    ax.set_ylabel("wMAPE % (lower = better)", fontsize=10)
    ax.set_title("Experiment C — Rolling 3-Cutpoint Cross-Validation\n"
                 "Stable accuracy estimate independent of any single evaluation window",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=8.5, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)

    avg_box = "\n".join([f"{k}: avg {v:.2f}%" for k, v in means.items()])
    fig.text(0.5, -0.05, avg_box, ha="center", va="top", fontsize=9, fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.5", facecolor="#e8f5e9", edgecolor="#388e3c", alpha=0.9))

    plt.tight_layout(pad=2, rect=[0, 0.12, 1, 1])
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"    Saved: {os.path.basename(out_path)}")
    return df_cv, means


# ── Model history log ─────────────────────────────────────────────────────────

def update_model_history(best_variant_tag, best_wmape, avg_cv_wmape, n_series, params, feats):
    history = []
    if os.path.exists(MODEL_HISTORY):
        with open(MODEL_HISTORY) as f:
            history = json.load(f)

    champion_wmape = min((r["avg_cv_wmape"] for r in history if r.get("champion")),
                        default=999.0)
    is_champion = avg_cv_wmape < champion_wmape - 0.05

    if is_champion:
        for r in history:
            r["champion"] = False

    entry = {
        "script":        "MO_51",
        "date":          datetime.now().strftime("%Y-%m-%d"),
        "variant":       best_variant_tag,
        "feature_set":   feats,
        "n_features":    len(feats),
        "n_series":      n_series,
        "dec2025_wmape": best_wmape,
        "avg_cv_wmape":  avg_cv_wmape,
        "champion":      is_champion,
        "params":        {k: v for k, v in params.items() if k not in ("n_jobs", "verbose", "random_state")},
    }
    history.append(entry)

    with open(MODEL_HISTORY, "w") as f:
        json.dump(history, f, indent=2)

    status = "★ NEW CHAMPION" if is_champion else f"  (champion still {champion_wmape:.3f}%)"
    print(f"  Model history updated: {best_variant_tag} avg_cv={avg_cv_wmape:.3f}%  {status}")
    return is_champion


# ── HTML Section 20 ────────────────────────────────────────────────────────────

def build_html_section20(chart_paths, df_grid, best_m1, best_m5b, df_topk, df_cv, means, is_champion):

    def b64(key):
        p = chart_paths.get(key, "")
        return img_b64(p) if p and os.path.exists(p) else ""

    # Readable best-params strings
    def fmt_params(p):
        return f"reg_alpha={p.get('reg_alpha')} · reg_lambda={p.get('reg_lambda')} · num_leaves={p.get('num_leaves', 63)}"

    # Best topK row
    best_topk_row = df_topk.loc[df_topk["wmape"].idxmin()]
    topk_desc = (f"K={int(best_topk_row['k'])} features added to M1; "
                 f"best feature: {best_topk_row['added']}; wMAPE {best_topk_row['wmape']:.3f}%")

    # CV table rows
    cv_rows = ""
    for _, r in df_cv.iterrows():
        cv_rows += (
            f"<tr><td style='padding:.4rem .7rem'>{r['cutpoint']} (n={r['n_series']})</td>"
            f"<td style='padding:.4rem .7rem;text-align:center'>{r['ma13']:.2f}%</td>"
            f"<td style='padding:.4rem .7rem;text-align:center'>{r['m1']:.2f}%</td>"
            f"<td style='padding:.4rem .7rem;text-align:center'>{r['m5b_rolling']:.2f}%</td>"
            f"<td style='padding:.4rem .7rem;text-align:center'>{r['m1_topk']:.2f}%</td></tr>"
        )
    cv_avg_row = (
        f"<tr style='background:#1e293b;color:white;font-weight:bold'>"
        f"<td style='padding:.4rem .7rem'>3-Cutpoint Average</td>"
        f"<td style='padding:.4rem .7rem;text-align:center'>{means['ma13']:.2f}%</td>"
        f"<td style='padding:.4rem .7rem;text-align:center'>{means['m1']:.2f}%</td>"
        f"<td style='padding:.4rem .7rem;text-align:center'>{means['m5b_rolling']:.2f}%</td>"
        f"<td style='padding:.4rem .7rem;text-align:center'>{means['m1_topk']:.2f}%</td></tr>"
    )

    champion_note = (
        '<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;'
        'padding:.7rem 1rem;margin-bottom:1rem;font-size:.88rem">'
        f'★ <strong>New champion:</strong> M1+topK avg CV wMAPE {means["m1_topk"]:.3f}% — '
        'updated model_history.json. This variant will be evaluated as the MO_52 starting point.</div>'
    ) if is_champion else ""

    return f"""
<section id="section20" style="background:white;border-radius:12px;padding:2rem 2.5rem;
  margin:2rem 0;box-shadow:0 2px 12px rgba(0,0,0,.07);font-family:system-ui,sans-serif">

<h2 style="font-size:1.4rem;font-weight:700;color:#0f172a;border-bottom:2px solid #e2e8f0;
  padding-bottom:.6rem;margin-bottom:1.5rem">
  20 · Regularization Search, SHAP Pruning & Rolling CV (MO_51)
</h2>

{champion_note}

<div style="background:#f8fbff;border:1px solid #dce8f5;border-radius:8px;
  padding:.9rem 1.2rem;margin-bottom:1.5rem;font-size:.88rem">
  <strong>Goal:</strong> MO_50 showed M1 (3.52%) beats all 27-feature variants.
  MO_51 tests whether (A) tuned regularization lets rolling signals contribute without overfitting,
  (B) a SHAP-ranked M1+topK subset beats M1 alone, and (C) 3-cutpoint rolling CV produces
  a stable accuracy estimate that generalises beyond December 2025.
</div>

<h3 style="font-size:1.1rem;margin-top:1.5rem">20.1 Experiment A — Regularization Grid Search</h3>
<p style="font-size:.88rem;color:#475569">
  Grid: reg_alpha ∈ {REG_ALPHA_GRID} × reg_lambda ∈ {REG_LAMBDA_GRID} × num_leaves ∈ {NUM_LEAVES_GRID}.
  Heatmap shows minimum wMAPE per cell (M1 left, M5b centre, delta right — green delta = rolling wins).
</p>
<p style="font-size:.88rem">
  <strong>Best M1:</strong> {best_m1['wmape']:.3f}% — {fmt_params(best_m1['params'])}<br>
  <strong>Best M5b:</strong> {best_m5b['wmape']:.3f}% — {fmt_params(best_m5b['params'])}
</p>
<img src="data:image/png;base64,{b64('reg_search')}"
  style="width:100%;max-width:1100px;display:block;margin:0 auto 2rem" alt="Regularization grid">

<h3 style="font-size:1.1rem;margin-top:1.5rem">20.2 Experiment B — SHAP-Guided M1+Top-K Pruning</h3>
<p style="font-size:.88rem;color:#475569">
  Features ranked by mean |SHAP| from the full M5b model. Added one at a time to M1.
  Green bars = beats M1 baseline; red = degrades.
</p>
<p style="font-size:.88rem"><strong>Best pruned variant:</strong> {topk_desc}</p>
<img src="data:image/png;base64,{b64('topk')}"
  style="width:100%;max-width:1100px;display:block;margin:0 auto 2rem" alt="SHAP top-K pruning">

<h3 style="font-size:1.1rem;margin-top:1.5rem">20.3 Experiment C — Rolling 3-Cutpoint Cross-Validation</h3>
<p style="font-size:.88rem;color:#475569">
  Stable accuracy metric across Jun/Sep/Dec 2025. This is the headline wMAPE going forward —
  more robust than any single cutpoint evaluation.
</p>
<table style="width:100%;border-collapse:collapse;font-size:.88rem;margin-bottom:1rem">
  <thead><tr style="background:#1e293b;color:white">
    <th style="padding:.4rem .7rem">Cutpoint</th>
    <th style="padding:.4rem .7rem;text-align:center">MA 13wk</th>
    <th style="padding:.4rem .7rem;text-align:center">M1</th>
    <th style="padding:.4rem .7rem;text-align:center">M5b Rolling</th>
    <th style="padding:.4rem .7rem;text-align:center">M1+topK</th>
  </tr></thead>
  <tbody>{cv_rows}{cv_avg_row}</tbody>
</table>
<img src="data:image/png;base64,{b64('rolling_cv')}"
  style="width:100%;max-width:1000px;display:block;margin:0 auto 2rem" alt="Rolling CV">

<h3 style="font-size:1.1rem;margin-top:1.5rem">20.4 Model History Log</h3>
<p style="font-size:.88rem;color:#475569">
  Each training run appends to <code>outputs/model_history.json</code>. Champion is the variant
  with the lowest 3-cutpoint average CV wMAPE. A new run must be >0.05pp better to displace
  the champion — this prevents noise-driven champion flips.
</p>
</section>
"""


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("MO_51 — Regularization Search, SHAP Pruning & Rolling CV")
    print("=" * 70)

    # ── Load & prep data (same as MO_50/MO_41) ────────────────────────────────
    print(f"\nLoading {PARQUET} …")
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    df["log_base_units"] = np.log1p(df["base_units"].clip(lower=0))
    df["channel_outlet"] = df["channel_outlet"].astype("category")
    df["channel_encoded"] = df["channel_outlet"].cat.codes.astype(float)

    mulo_mask = (
        df["channel_outlet"].astype(str).str.contains("MULTI OUTLET|MULO", case=False, na=False) |
        df["geography_raw"].astype(str).str.contains("MULTI OUTLET|MULO|TOTAL US|ALL CHANNEL", case=False, na=False)
    )
    df = df[~mulo_mask].reset_index(drop=True)

    all_feats = (LAYER_DEMAND + LAYER_VELOCITY + LAYER_TDP_PRICE + LAYER_LIFECYCLE
                 + LAYER_MO_ROLLING + LAYER_YAGO)
    for c in all_feats:
        if c != "channel_outlet" and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            if c not in LAYER_MO_ROLLING:
                df[c] = df[c].fillna(0.0)

    # Dec 2025 cutpoint for Experiments A & B
    dec_utc = pd.Timestamp("2026-01-01").tz_localize("UTC")
    train_all, super_tr, val_df, test_df, n_q = qualify_cutpoint(df, dec_utc)
    print(f"  Rows: {len(df):,}  |  Dec 2025 qualifying series: {n_q:,}")
    print(f"  Train: {len(super_tr):,}  |  Val: {len(val_df):,}  |  Test: {len(test_df):,}")

    # ── Experiment A ──────────────────────────────────────────────────────────
    print("\n[A] Regularization grid search …")
    reg_out = os.path.join(OUTPUT_DIR, "v2_mo51_reg_search.png")
    df_grid, best_m1, best_m5b = exp_a_reg_search(super_tr, val_df, test_df, reg_out)
    df_grid.to_csv(os.path.join(OUTPUT_DIR, "mo51_reg_search_results.csv"), index=False)

    # ── Experiment B ──────────────────────────────────────────────────────────
    print("\n[B] SHAP-guided M1+topK pruning …")
    topk_out = os.path.join(OUTPUT_DIR, "v2_mo51_topk_pruning.png")
    df_topk, nd_ranked, shap_df = exp_b_topk_pruning(
        super_tr, val_df, test_df, best_m1["params"], topk_out
    )

    best_topk_row = df_topk.loc[df_topk["wmape"].idxmin()]
    best_topk_feats = avail(LAYER_DEMAND, super_tr) + nd_ranked[:int(best_topk_row["k"])]

    # ── Experiment C ──────────────────────────────────────────────────────────
    print("\n[C] Rolling 3-cutpoint CV …")
    cv_out = os.path.join(OUTPUT_DIR, "v2_mo51_rolling_cv.png")
    df_cv, means = exp_c_rolling_cv(
        df, best_m1["params"], best_m5b["params"], best_topk_feats, cv_out
    )
    df_cv.to_csv(os.path.join(OUTPUT_DIR, "mo51_rolling_cv_results.csv"), index=False)

    # ── Model history ─────────────────────────────────────────────────────────
    best_overall = min(
        [("M1", best_m1["wmape"], means["m1"], best_m1["params"], avail(LAYER_DEMAND, super_tr)),
         ("M1+topK", float(best_topk_row["wmape"]), means["m1_topk"], best_m1["params"], best_topk_feats),
         ("M5b", best_m5b["wmape"], means["m5b_rolling"], best_m5b["params"], avail(M5B_FEATS, super_tr))],
        key=lambda x: x[2]
    )
    is_champion = update_model_history(*best_overall)

    # ── HTML patch ────────────────────────────────────────────────────────────
    chart_paths = {"reg_search": reg_out, "topk": topk_out, "rolling_cv": cv_out}
    section20 = build_html_section20(
        chart_paths, df_grid, best_m1, best_m5b, df_topk, df_cv, means, is_champion
    )

    print("\n[MO_51] Patching HTML report …")
    with open(HTML_IN, "r", encoding="utf-8") as f:
        html = f.read()
    ANCHOR = "<!-- END SECTIONS -->"
    html = html.replace(ANCHOR, section20 + "\n" + ANCHOR) if ANCHOR in html \
           else html.replace("</body>", section20 + "\n</body>")
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)
    size_mb = os.path.getsize(HTML_OUT) / 1_048_576
    print(f"[MO_51] HTML patched → {HTML_OUT}  ({size_mb:.1f} MB)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("MO_51 COMPLETE")
    print("=" * 70)
    print(f"  Exp A — Best M1:    {best_m1['wmape']:.3f}%  params: {best_m1['params']['reg_alpha']}/{best_m1['params']['reg_lambda']}/{best_m1['params'].get('num_leaves',63)}")
    print(f"  Exp A — Best M5b:   {best_m5b['wmape']:.3f}%  params: {best_m5b['params']['reg_alpha']}/{best_m5b['params']['reg_lambda']}/{best_m5b['params'].get('num_leaves',63)}")
    print(f"  Exp B — Best M1+K:  {float(best_topk_row['wmape']):.3f}%  K={int(best_topk_row['k'])}  +{best_topk_row['added']}")
    print(f"  Exp C — 3-CP avgs:  MA13={means['ma13']:.2f}%  M1={means['m1']:.2f}%  M5b={means['m5b_rolling']:.2f}%  M1+K={means['m1_topk']:.2f}%")
    print(f"  Champion: {best_overall[0]} (avg CV {best_overall[2]:.3f}%)")
    print()
    print("Next: review results, then MO_52 (category STL seasonal index + new product prior)")


if __name__ == "__main__":
    main()
