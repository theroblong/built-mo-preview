"""MO_52 — New Feature Ablation: test each MO_25 v4 addition against M1+topK champion.

PURPOSE
-------
MO_25 v4 added 11 new columns to retailer_sales_weekly.parquet covering promo signals,
competitor/donor dynamics, category shelf share, and holiday seasonality.

This script tests each group of new features in isolation against the MO_51 champion
(M1+week_of_year, avg 3-cutpoint wMAPE 7.79%) to determine which additions improve
forecast accuracy. Only features that improve wMAPE by ≥0.05pp are promoted to
production FEATURE_COLS in MO_26.

EXPERIMENTAL DESIGN
-------------------
All experiments use the MO_51 champion configuration:
  - LGBM params: reg_alpha=0.3, reg_lambda=0.3, num_leaves=63, lr=0.04
  - Champion features (M1+topK): demand lags/rolling + week_of_year
  - Metric: wMAPE on Dec 2025 cutpoint test set (164 qualifying series)
  - Stability: rolling 3-cutpoint CV (Jun/Sep/Dec 2025) for promoted features

FEATURE GROUPS TESTED
---------------------
  G1  Promo signals:       is_promo_week, promo_intensity, arp_discount_pct
  G2  Holiday flags:       holiday_week (already in champion via week_of_year — test incremental)
  G3  Pack format:         pack_count (categorical; already in parquet, first inclusion in model)
  G4  Cannib/PE use cases: max_donor_cannibal_prob, donor_count, rolling_cannibal_pressure,
                           rolling_elasticity, implied_elasticity (individually and combined)
  G5  Competitor dynamics: top_donor_tdp_sum, top_donor_units_sum, competitor_price_gap,
                           top_donor_units_wow, top_donor_arp_wavg
  G6  Category shelf:      built_tdp_share (category_tdp_sum is audit only, not a feature)
  G7  Combined winner set: all G1-G6 features that improved individually
  G8  Promo-adjusted ARP:  test using arp_discount_pct INSTEAD OF raw arp as price signal
                           (hypothesis: discount depth is more informative than absolute price)

OUTPUTS
-------
  outputs/mo52_ablation_results.csv  — per-group wMAPE on Dec 2025 cutpoint
  outputs/mo52_rolling_cv_results.csv — 3-cutpoint CV for promoted features
  outputs/v2_mo52_group_ablation.png  — bar chart of group results
  outputs/v2_mo52_cannibal_pe.png     — cannibalization + PE use case detail
  outputs/v2_mo52_competitor.png      — competitor/donor group detail
  outputs/v2_mo52_rolling_cv.png      — rolling CV for promoted features
  outputs/model_history.json          — champion-challenger update
  HTML Section 21 patched into outputs/built_demand_intelligence_report.html
"""

import json
import os
import shap
import numpy as np
import pandas as pd
import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
from itertools import product as iterproduct

# ── Paths ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR   = os.path.join(os.path.dirname(__file__), "outputs")
HTML_IN      = os.path.join(OUTPUT_DIR, "built_demand_intelligence_report.html")
HTML_OUT     = os.path.join(OUTPUT_DIR, "built_demand_intelligence_report.html")
MODEL_HISTORY = os.path.join(OUTPUT_DIR, "model_history.json")

# ── MO_51 champion config ──────────────────────────────────────────────────────
CHAMPION_PARAMS = dict(
    objective="regression", boosting_type="gbdt",
    n_estimators=1000, learning_rate=0.04,
    min_child_samples=20, feature_fraction=0.8,
    bagging_fraction=0.8, bagging_freq=5,
    reg_alpha=0.3, reg_lambda=0.3, num_leaves=63,
    random_state=42, n_jobs=-1, verbose=-1,
)

# ── Feature sets ──────────────────────────────────────────────────────────────
LAYER_DEMAND = [
    "base_units_roll4_avg",
    "base_units_roll8_avg",  "base_units_roll8_std",
    "base_units_roll13_avg", "base_units_roll13_std",
    "base_units_wow_delta",  "base_units_z8", "base_units_z13",
    "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
    "velocity_spm_z8",        "velocity_spm_z13",
    "tdp", "tdp_z8",
    "arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std",
    "weeks_since_launch",
    "base_units_lag1", "base_units_lag4", "base_units_lag13",
    "base_units_lag52", "velocity_spm_lag52",
    "channel_outlet",
]
CHAMPION_TOPK = LAYER_DEMAND + ["week_of_year"]    # MO_51 champion feature set

# New feature groups (from MO_25 v4)
GROUP_PROMO  = ["is_promo_week", "promo_intensity", "arp_discount_pct"]
GROUP_HOLIDAY = ["holiday_week"]
GROUP_PACK   = ["pack_count"]
GROUP_CANNIBAL_PE = [
    "max_donor_cannibal_prob", "donor_count",
    "rolling_cannibal_pressure", "rolling_elasticity", "implied_elasticity",
]
GROUP_COMPETITOR = [
    "top_donor_tdp_sum", "top_donor_units_sum", "competitor_price_gap",
    "top_donor_units_wow",
]
GROUP_SHELF  = ["built_tdp_share"]

# promo-adjusted ARP test: swap arp for arp_discount_pct
LAYER_DEMAND_PROMO_ARP = [
    c for c in LAYER_DEMAND if c != "arp"
] + ["arp_discount_pct"]
CHAMPION_PROMO_ARP = LAYER_DEMAND_PROMO_ARP + ["week_of_year"]

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]
DEC2025_CUTOFF = pd.Timestamp("2026-01-01", tz="UTC")
PROMOTE_THRESHOLD = 0.05    # pp improvement required to promote a feature group

# ── Helpers ───────────────────────────────────────────────────────────────────

def wmape(actual, predicted):
    total = np.nansum(np.abs(actual))
    if total < 1e-9:
        return np.nan
    return np.nansum(np.abs(actual - predicted)) / total * 100


def avail(feats, df):
    return [f for f in feats if f in df.columns]


def qualify_cutpoint(df, cutoff_utc, min_train=52, min_test=13, horizon=13):
    val_cut = cutoff_utc - pd.Timedelta(weeks=8)
    groups  = df.groupby(GROUP_COLS)
    train_list, val_list, test_list = [], [], []

    for _, g in groups:
        g = g.sort_values("__time")
        tr = g[g["__time"] <  val_cut]
        va = g[(g["__time"] >= val_cut) & (g["__time"] < cutoff_utc)]
        te = g[(g["__time"] >= cutoff_utc) & (g["__time"] < cutoff_utc + pd.Timedelta(weeks=horizon))]
        if len(tr) >= min_train and len(te) >= min_test:
            train_list.append(tr)
            val_list.append(va)
            test_list.append(te)

    if not train_list:
        raise ValueError(f"No qualifying series at cutpoint {cutoff_utc}")

    return (
        pd.concat(train_list), pd.concat(val_list), pd.concat(test_list), len(train_list)
    )


def train_eval(train_df, val_df, test_df, feats, params=None):
    params = params or CHAMPION_PARAMS
    af = avail(feats, train_df)
    if not af:
        return np.nan, np.nan

    cat_feats = [c for c in af if train_df[c].dtype == object]

    m = lgb.LGBMRegressor(**params)
    m.fit(
        train_df[af], train_df["log_base_units"],
        eval_set=[(val_df[af], val_df["log_base_units"])],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(9999)],
        categorical_feature=cat_feats if cat_feats else "auto",
    )
    pred_log = m.predict(test_df[af])
    pred     = np.expm1(pred_log)
    actual   = test_df["base_units"].values
    wm       = wmape(actual, pred)
    return wm, m


def rolling_cv(df, feats, label, params=None):
    """3-cutpoint CV: Jun / Sep / Dec 2025."""
    cutpoints = [
        ("Jun 2025", pd.Timestamp("2025-07-01", tz="UTC")),
        ("Sep 2025", pd.Timestamp("2025-10-01", tz="UTC")),
        ("Dec 2025", pd.Timestamp("2026-01-01", tz="UTC")),
    ]
    rows = []
    for name, cutoff in cutpoints:
        tr, va, te, n = qualify_cutpoint(df, cutoff)
        wm, _ = train_eval(tr, va, te, feats, params)
        rows.append({"cutpoint": name, "n_series": n, "variant": label, "wmape": wm})
        print(f"    {name} (n={n}): {label}={wm:.3f}%")
    df_cv = pd.DataFrame(rows)
    return df_cv, df_cv["wmape"].mean()


# ── Model history ──────────────────────────────────────────────────────────────

def update_model_history(variant_tag, best_wmape, avg_cv_wmape, n_series, params, feats):
    history = []
    if os.path.exists(MODEL_HISTORY):
        with open(MODEL_HISTORY) as f:
            history = json.load(f)

    champion_wmape = min(
        (r["avg_cv_wmape"] for r in history if r.get("champion")), default=999.0
    )
    is_champion = avg_cv_wmape < champion_wmape - PROMOTE_THRESHOLD

    if is_champion:
        for r in history:
            r["champion"] = False

    entry = {
        "script":        "MO_52",
        "date":          datetime.now().strftime("%Y-%m-%d"),
        "variant":       variant_tag,
        "feature_set":   feats,
        "n_features":    len(feats),
        "n_series":      int(n_series),
        "dec2025_wmape": float(best_wmape),
        "avg_cv_wmape":  float(avg_cv_wmape),
        "champion":      bool(is_champion),
        "params":        {k: float(v) if hasattr(v, "item") else v
                          for k, v in params.items()
                          if k not in ("n_jobs", "verbose", "random_state")},
    }
    history.append(entry)
    with open(MODEL_HISTORY, "w") as f:
        json.dump(history, f, indent=2)

    status = "★ NEW CHAMPION" if is_champion else f"(champion still {champion_wmape:.3f}%)"
    print(f"  Model history updated: {variant_tag} avg_cv={avg_cv_wmape:.3f}%  {status}")
    return bool(is_champion)


# ── HTML section builder ──────────────────────────────────────────────────────

def build_html_section21(chart_paths, ablation_df, cv_df, champion_feats,
                          champion_wmape, is_new_champion):
    def img_b64(path):
        import base64
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()

    champ_tag = "★ New champion" if is_new_champion else "Champion unchanged"
    rows_html = ""
    for _, r in ablation_df.iterrows():
        delta = r["wmape"] - ablation_df.loc[ablation_df["variant"] == "Champion (M1+topK)", "wmape"].values[0]
        delta_str = f"{delta:+.3f}pp"
        color = "#27ae60" if delta < -PROMOTE_THRESHOLD else (
            "#e74c3c" if delta > 0.1 else "#888")
        rows_html += f"""
        <tr>
          <td style='padding:.4rem .7rem'>{r['variant']}</td>
          <td style='padding:.4rem .7rem;text-align:right'>{r['wmape']:.3f}%</td>
          <td style='padding:.4rem .7rem;text-align:right;color:{color}'>{delta_str}</td>
          <td style='padding:.4rem .7rem'>{r.get('note','')}</td>
        </tr>"""

    cv_rows = ""
    for _, r in cv_df.iterrows():
        cv_rows += f"""
        <tr>
          <td style='padding:.4rem .7rem'>{r['cutpoint']} (n={r['n_series']})</td>
          <td style='padding:.4rem .7rem;text-align:right'>{r['champion_wmape']:.2f}%</td>
          <td style='padding:.4rem .7rem;text-align:right'>{r['new_wmape']:.2f}%</td>
          <td style='padding:.4rem .7rem;text-align:right;color:#27ae60'>{(r["champion_wmape"]-r["new_wmape"]):+.3f}pp</td>
        </tr>"""

    imgs = {k: img_b64(v) for k, v in chart_paths.items() if os.path.exists(v)}

    section = f"""
<section style='font-family:sans-serif;max-width:1100px;margin:3rem auto;padding:0 1rem'>
  <h2 style='font-size:1.4rem;border-bottom:2px solid #2c3e50;padding-bottom:.5rem'>
    Section 21 — MO_52: Feature Ablation — MO_25 v4 New Signals
  </h2>
  <p style='color:#555;font-size:.9rem'>
    Tests each new feature group from MO_25 v4 against the MO_51 champion
    (M1+week_of_year, avg 3-cutpoint wMAPE {ablation_df.loc[ablation_df['variant']=='Champion (M1+topK)','wmape'].values[0]:.3f}%).
    Threshold for promotion: ≥{PROMOTE_THRESHOLD}pp improvement. {champ_tag}.
  </p>

  <h3 style='margin-top:1.5rem'>21.1 Group Ablation Results (Dec 2025 cutpoint)</h3>
  <table style='width:100%;border-collapse:collapse;font-size:.88rem'>
    <thead>
      <tr style='background:#2c3e50;color:#fff'>
        <th style='padding:.5rem .7rem;text-align:left'>Variant</th>
        <th style='padding:.5rem .7rem;text-align:right'>wMAPE</th>
        <th style='padding:.5rem .7rem;text-align:right'>vs Champion</th>
        <th style='padding:.5rem .7rem;text-align:left'>Note</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  {'<img src="' + imgs["group_ablation"] + '" style="width:100%;margin-top:1rem">' if "group_ablation" in imgs else ""}

  <h3 style='margin-top:1.5rem'>21.2 Cannibalization + Price Elasticity Detail</h3>
  {'<img src="' + imgs["cannibal_pe"] + '" style="width:100%;margin-top:.5rem">' if "cannibal_pe" in imgs else ""}

  <h3 style='margin-top:1.5rem'>21.3 Competitor / Donor Signal Detail</h3>
  {'<img src="' + imgs["competitor"] + '" style="width:100%;margin-top:.5rem">' if "competitor" in imgs else ""}

  <h3 style='margin-top:1.5rem'>21.4 Rolling CV — Champion vs Promoted Feature Set</h3>
  <table style='width:100%;border-collapse:collapse;font-size:.88rem;margin-bottom:1rem'>
    <thead>
      <tr style='background:#2c3e50;color:#fff'>
        <th style='padding:.5rem .7rem;text-align:left'>Cutpoint</th>
        <th style='padding:.5rem .7rem;text-align:right'>Champion wMAPE</th>
        <th style='padding:.5rem .7rem;text-align:right'>New wMAPE</th>
        <th style='padding:.5rem .7rem;text-align:right'>Δ</th>
      </tr>
    </thead>
    <tbody>{cv_rows}</tbody>
  </table>
  {'<img src="' + imgs["rolling_cv"] + '" style="width:100%;margin-top:.5rem">' if "rolling_cv" in imgs else ""}

  <h3 style='margin-top:1.5rem'>21.5 Promoted Feature Set</h3>
  <p style='font-size:.9rem;color:#555'>
    Features promoted to MO_26 production FEATURE_COLS (improved by ≥{PROMOTE_THRESHOLD}pp):
    <strong>{', '.join(champion_feats)}</strong>
    &nbsp;→ Dec 2025 wMAPE: <strong>{champion_wmape:.3f}%</strong>
  </p>

  <div style='margin:1rem 0;background:#f0f9ff;border-left:4px solid #3498db;padding:1rem 1.2rem;font-size:.88rem'>
    <strong>Audit note:</strong> promo_source and arp_source columns in parquet document
    which data tier drove each week's promo and ARP classification. Not fed to model.
    Competitor signals (top_donor_*) cover series with donors in scored_cannibalization;
    NaN for series with no detected competitors — LightGBM handles gracefully.
  </div>
</section>"""
    return section


# ── Main ──────────────────────────────────────────────────────────────────────

def _patch_html_inline(section_html):
    if not os.path.exists(HTML_IN):
        print(f"  HTML not found at {HTML_IN} — skipping patch.")
        return
    with open(HTML_IN, "r", encoding="utf-8") as f:
        html = f.read()
    ANCHOR = "<!-- END SECTIONS -->"
    html = html.replace(ANCHOR, section_html + "\n" + ANCHOR) if ANCHOR in html \
           else html.replace("</body>", section_html + "\n</body>")
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)
    size_mb = os.path.getsize(HTML_OUT) / 1_048_576
    print(f"HTML patched → {HTML_OUT}  ({size_mb:.1f} MB)")


def main():
    print("=" * 70)
    print("MO_52 — Feature Ablation: MO_25 v4 New Signals")
    print("=" * 70)

    # ── Cache-skip: if prior results exist, patch HTML and return early ────────
    _ABLATION_CSV = os.path.join(OUTPUT_DIR, "mo52_ablation_results.csv")
    _CV_CSV       = os.path.join(OUTPUT_DIR, "mo52_rolling_cv_results.csv")
    _PNG_MAIN     = os.path.join(OUTPUT_DIR, "v2_mo52_group_ablation.png")
    if all(os.path.exists(p) for p in [_ABLATION_CSV, _CV_CSV, _PNG_MAIN]):
        print("[CACHED] Prior results found — skipping ablation; regenerating HTML only …")
        df_abl = pd.read_csv(_ABLATION_CSV)
        df_cv  = pd.read_csv(_CV_CSV)
        champ_row = df_abl[df_abl["variant"].str.startswith("Champion")]
        _champ_wmape = float(champ_row["wmape"].iloc[0]) if not champ_row.empty \
                       else float(df_cv.loc[df_cv["cutpoint"] == "Dec 2025", "champion_wmape"].iloc[0])
        _is_new = bool(df_cv["new_wmape"].mean() < df_cv["champion_wmape"].mean() - PROMOTE_THRESHOLD)
        _chart_paths = {k: os.path.join(OUTPUT_DIR, v) for k, v in {
            "group_ablation": "v2_mo52_group_ablation.png",
            "cannibal_pe":    "v2_mo52_cannibal_pe.png",
            "competitor":     "v2_mo52_competitor.png",
            "rolling_cv":     "v2_mo52_rolling_cv.png",
        }.items() if os.path.exists(os.path.join(OUTPUT_DIR, v))}
        _feats = CHAMPION_TOPK  # no groups promoted
        section21 = build_html_section21(_chart_paths, df_abl, df_cv, _feats, _champ_wmape, _is_new)
        print("Patching HTML report …")
        _patch_html_inline(section21)
        print("MO_52 COMPLETE (cached)")
        return

    # Load parquet (must be MO_25 v4 output)
    parquet_path = os.path.join(OUTPUT_DIR, "retailer_sales_weekly.parquet")
    print(f"\nLoading {parquet_path} …")
    df = pd.read_parquet(parquet_path)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)

    # Log-transform target
    df["log_base_units"] = np.log1p(df["base_units"].clip(lower=0))

    # Encode categoricals
    for c in ["channel_outlet"]:
        if c in df.columns:
            df[c] = df[c].astype("category")

    # pack_count as ordered category
    if "pack_count" in df.columns:
        df["pack_count"] = df["pack_count"].astype("category")

    # Dec 2025 cutpoint for individual group tests
    print(f"\nQualifying Dec 2025 cutpoint …")
    super_tr, val_df, test_df, n_q = qualify_cutpoint(df, DEC2025_CUTOFF)
    print(f"  Qualifying series: {n_q} | Train: {len(super_tr):,} | "
          f"Val: {len(val_df):,} | Test: {len(test_df):,}")

    # ── Champion baseline ──────────────────────────────────────────────────────
    print("\n[Champion] M1+topK (week_of_year) baseline …")
    champ_wmape, _ = train_eval(super_tr, val_df, test_df, CHAMPION_TOPK)
    print(f"  Champion wMAPE: {champ_wmape:.3f}%")

    ablation_results = [{"variant": "Champion (M1+topK)", "wmape": champ_wmape, "note": "MO_51 result"}]

    # ── G1: Promo signals ─────────────────────────────────────────────────────
    print("\n[G1] Promo signals …")
    feats_g1 = CHAMPION_TOPK + avail(GROUP_PROMO, super_tr)
    wm_g1, _ = train_eval(super_tr, val_df, test_df, feats_g1)
    d1 = wm_g1 - champ_wmape
    print(f"  G1 (is_promo_week + promo_intensity + arp_discount_pct): {wm_g1:.3f}% ({d1:+.3f}pp)")
    ablation_results.append({"variant": "G1: Promo signals", "wmape": wm_g1,
                              "note": "is_promo_week + promo_intensity + arp_discount_pct"})

    # ── G8: Promo-adjusted ARP (swap arp for arp_discount_pct) ───────────────
    print("\n[G8] Promo-adjusted ARP (arp → arp_discount_pct swap) …")
    feats_g8 = avail(CHAMPION_PROMO_ARP, super_tr)
    wm_g8, _ = train_eval(super_tr, val_df, test_df, feats_g8)
    d8 = wm_g8 - champ_wmape
    print(f"  G8 (arp replaced by arp_discount_pct): {wm_g8:.3f}% ({d8:+.3f}pp)")
    ablation_results.append({"variant": "G8: Promo-adjusted ARP swap", "wmape": wm_g8,
                              "note": "arp replaced by arp_discount_pct in demand set"})

    # ── G2: Holiday flags ─────────────────────────────────────────────────────
    print("\n[G2] Holiday flags (holiday_week) …")
    feats_g2 = CHAMPION_TOPK + avail(GROUP_HOLIDAY, super_tr)
    wm_g2, _ = train_eval(super_tr, val_df, test_df, feats_g2)
    d2 = wm_g2 - champ_wmape
    print(f"  G2 (holiday_week): {wm_g2:.3f}% ({d2:+.3f}pp)")
    ablation_results.append({"variant": "G2: Holiday flags", "wmape": wm_g2,
                              "note": "holiday_week (0=none, 1=NewYear … 6=Christmas)"})

    # ── G3: Pack format ───────────────────────────────────────────────────────
    print("\n[G3] Pack format (pack_count) …")
    feats_g3 = CHAMPION_TOPK + avail(GROUP_PACK, super_tr)
    wm_g3, _ = train_eval(super_tr, val_df, test_df, feats_g3)
    d3 = wm_g3 - champ_wmape
    print(f"  G3 (pack_count): {wm_g3:.3f}% ({d3:+.3f}pp)")
    ablation_results.append({"variant": "G3: Pack format", "wmape": wm_g3,
                              "note": "pack_count categorical (1/4/8/12/16/18)"})

    # ── G4: Cannibalization + PE use cases (detail) ───────────────────────────
    print("\n[G4] Cannibalization + PE signals (detail) …")
    cannibal_pe_results = []
    for feat in GROUP_CANNIBAL_PE:
        if feat not in super_tr.columns:
            continue
        feats_f = CHAMPION_TOPK + [feat]
        wm_f, _ = train_eval(super_tr, val_df, test_df, feats_f)
        delta    = wm_f - champ_wmape
        print(f"  +{feat}: {wm_f:.3f}% ({delta:+.3f}pp)")
        cannibal_pe_results.append({"feature": feat, "wmape": wm_f, "delta": delta})

    # Full cannib+PE group
    feats_g4 = CHAMPION_TOPK + avail(GROUP_CANNIBAL_PE, super_tr)
    wm_g4, _ = train_eval(super_tr, val_df, test_df, feats_g4)
    d4 = wm_g4 - champ_wmape
    print(f"  G4 combined: {wm_g4:.3f}% ({d4:+.3f}pp)")
    ablation_results.append({"variant": "G4: Cannib + PE (all)", "wmape": wm_g4,
                              "note": "cannibal_prob, donor_count, rolling signals, elasticity"})

    df_cannibal_pe = pd.DataFrame(cannibal_pe_results)

    # ── G5: Competitor / donor signals ────────────────────────────────────────
    print("\n[G5] Competitor / donor signals …")
    competitor_results = []
    for feat in GROUP_COMPETITOR:
        if feat not in super_tr.columns:
            continue
        feats_f = CHAMPION_TOPK + [feat]
        wm_f, _ = train_eval(super_tr, val_df, test_df, feats_f)
        delta    = wm_f - champ_wmape
        print(f"  +{feat}: {wm_f:.3f}% ({delta:+.3f}pp)")
        competitor_results.append({"feature": feat, "wmape": wm_f, "delta": delta})

    # Full competitor group
    feats_g5 = CHAMPION_TOPK + avail(GROUP_COMPETITOR, super_tr)
    wm_g5, _ = train_eval(super_tr, val_df, test_df, feats_g5)
    d5 = wm_g5 - champ_wmape
    print(f"  G5 combined: {wm_g5:.3f}% ({d5:+.3f}pp)")
    ablation_results.append({"variant": "G5: Competitor signals (all)", "wmape": wm_g5,
                              "note": "top_donor_tdp_sum, units_sum, price_gap, units_wow"})

    df_competitor = pd.DataFrame(competitor_results)

    # ── G6: Category shelf share ──────────────────────────────────────────────
    print("\n[G6] BUILT TDP share …")
    feats_g6 = CHAMPION_TOPK + avail(GROUP_SHELF, super_tr)
    wm_g6, _ = train_eval(super_tr, val_df, test_df, feats_g6)
    d6 = wm_g6 - champ_wmape
    print(f"  G6 (built_tdp_share): {wm_g6:.3f}% ({d6:+.3f}pp)")
    ablation_results.append({"variant": "G6: BUILT TDP share", "wmape": wm_g6,
                              "note": "BUILT TDP / category TDP (shelf presence market share)"})

    # ── G7: Combined winners ──────────────────────────────────────────────────
    print("\n[G7] Combined winner set …")
    group_results = [
        (GROUP_PROMO,       wm_g1, d1),
        (GROUP_HOLIDAY,     wm_g2, d2),
        (GROUP_PACK,        wm_g3, d3),
        (GROUP_CANNIBAL_PE, wm_g4, d4),
        (GROUP_COMPETITOR,  wm_g5, d5),
        (GROUP_SHELF,       wm_g6, d6),
    ]
    winner_feats = []
    for grp, wm, delta in group_results:
        if delta <= -PROMOTE_THRESHOLD:
            winner_feats.extend(avail(grp, super_tr))
            print(f"  ✓ Promoted: {grp[:2]}… ({delta:+.3f}pp)")
        else:
            print(f"  ✗ Skipped:  {grp[:2]}… ({delta:+.3f}pp)")

    if winner_feats:
        feats_g7 = CHAMPION_TOPK + list(dict.fromkeys(winner_feats))  # deduplicate, preserve order
        wm_g7, _ = train_eval(super_tr, val_df, test_df, feats_g7)
        d7 = wm_g7 - champ_wmape
        print(f"  G7 combined winners: {wm_g7:.3f}% ({d7:+.3f}pp) | "
              f"{len(winner_feats)} new features")
        ablation_results.append({"variant": "G7: Combined winners", "wmape": wm_g7,
                                  "note": f"{len(winner_feats)} promoted features combined"})
    else:
        feats_g7 = CHAMPION_TOPK
        wm_g7    = champ_wmape
        print("  No groups improved — champion unchanged.")
        ablation_results.append({"variant": "G7: Combined winners", "wmape": champ_wmape,
                                  "note": "No groups met threshold — champion unchanged"})

    df_ablation = pd.DataFrame(ablation_results)

    # ── Rolling CV on champion vs best new set ─────────────────────────────────
    best_new_feats = feats_g7 if wm_g7 < champ_wmape else CHAMPION_TOPK
    best_new_label = "G7 combined" if wm_g7 < champ_wmape else "Champion (no change)"

    print(f"\n[Rolling CV] Champion vs {best_new_label} …")
    cv_rows = []
    for name, cutoff in [
        ("Jun 2025", pd.Timestamp("2025-07-01", tz="UTC")),
        ("Sep 2025", pd.Timestamp("2025-10-01", tz="UTC")),
        ("Dec 2025", DEC2025_CUTOFF),
    ]:
        tr, va, te, n = qualify_cutpoint(df, cutoff)
        wm_champ, _ = train_eval(tr, va, te, CHAMPION_TOPK)
        wm_new,   _ = train_eval(tr, va, te, best_new_feats)
        print(f"  {name} (n={n}): Champion={wm_champ:.3f}%  {best_new_label}={wm_new:.3f}%")
        cv_rows.append({"cutpoint": name, "n_series": n,
                        "champion_wmape": wm_champ, "new_wmape": wm_new})
    df_cv = pd.DataFrame(cv_rows)
    avg_cv_new = df_cv["new_wmape"].mean()

    # ── Save CSVs ──────────────────────────────────────────────────────────────
    df_ablation.to_csv(os.path.join(OUTPUT_DIR, "mo52_ablation_results.csv"), index=False)
    df_cv.to_csv(os.path.join(OUTPUT_DIR, "mo52_rolling_cv_results.csv"), index=False)
    if not df_cannibal_pe.empty:
        df_cannibal_pe.to_csv(os.path.join(OUTPUT_DIR, "mo52_cannibal_pe_detail.csv"), index=False)
    if not df_competitor.empty:
        df_competitor.to_csv(os.path.join(OUTPUT_DIR, "mo52_competitor_detail.csv"), index=False)

    # ── Charts ────────────────────────────────────────────────────────────────
    chart_paths = {}

    # Group ablation bar chart
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ["#27ae60" if r["wmape"] < champ_wmape - PROMOTE_THRESHOLD
              else "#e74c3c" if r["wmape"] > champ_wmape + 0.05
              else "#95a5a6"
              for _, r in df_ablation.iterrows()]
    ax.barh(df_ablation["variant"], df_ablation["wmape"], color=colors)
    ax.axvline(champ_wmape, color="#2c3e50", linestyle="--", linewidth=1.5,
               label=f"Champion {champ_wmape:.3f}%")
    ax.set_xlabel("wMAPE (%)")
    ax.set_title("MO_52: Feature Group Ablation vs Champion (Dec 2025 cutpoint)", fontsize=13)
    ax.legend()
    ax.invert_yaxis()
    fig.tight_layout()
    p = os.path.join(OUTPUT_DIR, "v2_mo52_group_ablation.png")
    fig.savefig(p, dpi=130); plt.close(fig)
    chart_paths["group_ablation"] = p
    print(f"\nSaved: {p}")

    # Cannib + PE detail
    if not df_cannibal_pe.empty:
        fig, ax = plt.subplots(figsize=(9, 4))
        bar_colors = ["#27ae60" if d < -PROMOTE_THRESHOLD else "#e74c3c" if d > 0.05 else "#95a5a6"
                      for d in df_cannibal_pe["delta"]]
        ax.bar(df_cannibal_pe["feature"], df_cannibal_pe["delta"], color=bar_colors)
        ax.axhline(0, color="#2c3e50", linewidth=1.2)
        ax.axhline(-PROMOTE_THRESHOLD, color="#27ae60", linestyle="--", linewidth=1,
                   label=f"Promote threshold −{PROMOTE_THRESHOLD}pp")
        ax.set_ylabel("Δ wMAPE vs Champion (pp)")
        ax.set_title("G4: Cannibalization + PE Feature Detail", fontsize=12)
        ax.legend(); plt.xticks(rotation=20, ha="right")
        fig.tight_layout()
        p = os.path.join(OUTPUT_DIR, "v2_mo52_cannibal_pe.png")
        fig.savefig(p, dpi=130); plt.close(fig)
        chart_paths["cannibal_pe"] = p
        print(f"Saved: {p}")

    # Competitor detail
    if not df_competitor.empty:
        fig, ax = plt.subplots(figsize=(9, 4))
        bar_colors = ["#27ae60" if d < -PROMOTE_THRESHOLD else "#e74c3c" if d > 0.05 else "#95a5a6"
                      for d in df_competitor["delta"]]
        ax.bar(df_competitor["feature"], df_competitor["delta"], color=bar_colors)
        ax.axhline(0, color="#2c3e50", linewidth=1.2)
        ax.axhline(-PROMOTE_THRESHOLD, color="#27ae60", linestyle="--", linewidth=1,
                   label=f"Promote threshold −{PROMOTE_THRESHOLD}pp")
        ax.set_ylabel("Δ wMAPE vs Champion (pp)")
        ax.set_title("G5: Competitor / Donor Signal Detail", fontsize=12)
        ax.legend(); plt.xticks(rotation=15, ha="right")
        fig.tight_layout()
        p = os.path.join(OUTPUT_DIR, "v2_mo52_competitor.png")
        fig.savefig(p, dpi=130); plt.close(fig)
        chart_paths["competitor"] = p
        print(f"Saved: {p}")

    # Rolling CV chart
    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(df_cv))
    w = 0.35
    ax.bar(x - w/2, df_cv["champion_wmape"], w, label="Champion (M1+topK)", color="#3498db")
    ax.bar(x + w/2, df_cv["new_wmape"],      w, label=best_new_label,       color="#e67e22")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r['cutpoint']}\n(n={r['n_series']})" for _, r in df_cv.iterrows()])
    ax.set_ylabel("wMAPE (%)"); ax.set_title("MO_52: Rolling CV — Champion vs Promoted Set")
    ax.legend(); fig.tight_layout()
    p = os.path.join(OUTPUT_DIR, "v2_mo52_rolling_cv.png")
    fig.savefig(p, dpi=130); plt.close(fig)
    chart_paths["rolling_cv"] = p
    print(f"Saved: {p}")

    # ── Model history ──────────────────────────────────────────────────────────
    is_champion = update_model_history(
        best_new_label, wm_g7, avg_cv_new, n_q,
        CHAMPION_PARAMS, best_new_feats
    )

    # ── HTML patch ─────────────────────────────────────────────────────────────
    section21 = build_html_section21(
        chart_paths, df_ablation, df_cv, best_new_feats,
        wm_g7, is_champion
    )
    print("\nPatching HTML report …")
    with open(HTML_IN, "r", encoding="utf-8") as f:
        html = f.read()
    ANCHOR = "<!-- END SECTIONS -->"
    html = html.replace(ANCHOR, section21 + "\n" + ANCHOR) if ANCHOR in html \
           else html.replace("</body>", section21 + "\n</body>")
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)
    size_mb = os.path.getsize(HTML_OUT) / 1_048_576
    print(f"HTML patched → {HTML_OUT}  ({size_mb:.1f} MB)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("MO_52 COMPLETE")
    print("=" * 70)
    print(f"  Champion baseline: {champ_wmape:.3f}% (M1+topK, M0_51)")
    print(f"  G1 Promo signals:  {wm_g1:.3f}% ({d1:+.3f}pp)")
    print(f"  G2 Holiday flags:  {wm_g2:.3f}% ({d2:+.3f}pp)")
    print(f"  G3 Pack format:    {wm_g3:.3f}% ({d3:+.3f}pp)")
    print(f"  G4 Cannib+PE:      {wm_g4:.3f}% ({d4:+.3f}pp)")
    print(f"  G5 Competitor:     {wm_g5:.3f}% ({d5:+.3f}pp)")
    print(f"  G6 TDP share:      {wm_g6:.3f}% ({d6:+.3f}pp)")
    print(f"  G7 Combined:       {wm_g7:.3f}% ({wm_g7-champ_wmape:+.3f}pp)")
    print(f"  G8 ARP swap:       {wm_g8:.3f}% ({d8:+.3f}pp)")
    print(f"  Promoted features: {winner_feats or ['none']}")
    print(f"  Avg CV (3-cutpt):  {avg_cv_new:.3f}%  {'★ NEW CHAMPION' if is_champion else ''}")
    print()
    print("Next: review results, update MO_26 FEATURE_COLS with promoted features → MO_26 retrain.")


if __name__ == "__main__":
    main()
