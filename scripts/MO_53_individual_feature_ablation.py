"""MO_53 — Individual Feature Ablation: v5 signals + brand-split donor tests.

PURPOSE
-------
MO_52 tested features in groups, which masked individual winners — notably
donor_count (−0.081pp win) buried inside G4 (+0.052pp combined with bad signals).
This script tests each candidate individually against the MO_52 champion and
promotes features clearing a tightened 0.03pp threshold (recalibrated for 512 series
vs 0.05pp at 164 series).

New in MO_25 v5 (all tested here for the first time):
  • Brand-split donor signals: competitor_donor_count vs built_donor_count
    (intra-BUILT cannibalization ≠ cross-brand competition — must track separately)
  • TDP change signals: tdp_wow_delta, tdp_4w_momentum
    (CPG-proven: distribution expansion leads unit sales; the level is in champion already)
  • Promo v2: arp_dollar_discount ($0.05 absolute vs 5% percentage — correct nickel standard)
              promo_lift_ratio (display lift independent of price)
  • Rolling elasticity v2: fixed guardrail applied to arp/pack_count in MO_46
    (multi-packs previously passed trivially; now requires real $/bar variation)

EXPERIMENTAL DESIGN
-------------------
  - Champion features: MO_52 feature_set (26 features, avg 3-cutpoint wMAPE 6.537%)
  - Each candidate: Champion + [feature] — one feature at a time
  - Metric: wMAPE on Dec 2025 cutpoint (≥512 qualifying series)
  - Threshold: 0.03pp improvement to promote (down from 0.05pp — justified by 3x series count)
  - Stability: rolling 3-cutpoint CV (Jun/Sep/Dec 2025) for any promoted set
  - Champion-challenger: if promoted set avg CV < current champion − 0.03pp → new champion

OUTPUTS
-------
  outputs/mo53_individual_ablation.csv      — per-feature wMAPE on Dec 2025 cutpoint
  outputs/mo53_rolling_cv_results.csv       — 3-cutpoint CV for promoted set
  outputs/v2_mo53_individual_results.png    — ranked bar chart
  outputs/v2_mo53_brand_split_detail.png    — competitor vs BUILT donor comparison
  outputs/v2_mo53_tdp_promo_detail.png      — TDP change and promo v2 detail
  outputs/v2_mo53_rolling_cv.png            — rolling CV champion vs promoted
  outputs/v2_mo53_shap.png                  — SHAP if new champion promoted
  outputs/model_history.json               — champion-challenger update
  HTML Section 22 patched into outputs/built_demand_intelligence_report.html
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

# ── Paths ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR    = os.path.join(os.path.dirname(__file__), "outputs")
HTML_IN       = os.path.join(OUTPUT_DIR, "built_demand_intelligence_report.html")
HTML_OUT      = os.path.join(OUTPUT_DIR, "built_demand_intelligence_report.html")
MODEL_HISTORY = os.path.join(OUTPUT_DIR, "model_history.json")

# ── MO_52 champion config (carry forward unchanged) ───────────────────────────
CHAMPION_PARAMS = dict(
    objective="regression", boosting_type="gbdt",
    n_estimators=1000, learning_rate=0.04,
    min_child_samples=20, feature_fraction=0.8,
    bagging_fraction=0.8, bagging_freq=5,
    reg_alpha=0.3, reg_lambda=0.3, num_leaves=63,
    random_state=42, n_jobs=-1, verbose=-1,
)

# ── MO_52 champion feature set (26 features) ──────────────────────────────────
CHAMPION_FEATS = [
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
    "week_of_year",
]

# ── Individual candidate features ─────────────────────────────────────────────
# Each is tested as: CHAMPION_FEATS + [candidate] vs CHAMPION_FEATS alone.
# Skip features already in CHAMPION_FEATS.
# Group annotations explain the hypotheses being tested.

CANDIDATES = [
    # ── Brand-split donor signals (MO_25 v5 new) ─────────────────────────────
    # User finding: intra-BUILT cannibalization ≠ cross-brand competition.
    # Testing competitor and BUILT donor signals independently is more precise
    # than the mixed donor_count from MO_52's G4 group test.
    ("competitor_donor_count",    "Competitor donors: market share pressure count"),
    ("built_donor_count",         "BUILT sibling donors: own-brand cannibalization count"),
    ("donor_count",               "Total donor count (re-test individually; −0.081pp in G4 detail)"),
    ("competitor_donor_units_wow","Competitor unit acceleration (market share timing signal)"),
    ("competitor_donor_tdp_sum",  "Competitor shelf presence (TDP sum of top-3 rivals)"),
    ("built_donor_units_wow",     "BUILT sibling unit acceleration (cannibalization risk)"),
    ("max_donor_cannibal_prob",   "Peak cannibalization probability (static; −0.013pp in G4)"),
    ("rolling_cannibal_pressure", "Live competitive tension (8w Pearson; not tested individually in MO_52)"),

    # ── TDP change signals (MO_25 v5 new) ────────────────────────────────────
    # CPG research: distribution growth is a leading indicator of unit sales.
    # tdp and tdp_z8 (level + z-score) are in the champion already.
    # These capture the *change rate* — different from level.
    ("tdp_wow_delta",     "WoW distribution change (stores gained/lost this week)"),
    ("tdp_4w_momentum",   "4-week distribution trend (monthly expansion direction)"),

    # ── Promo signals v2 (MO_25 v5 fixes) ───────────────────────────────────
    # v4 promo signals all hurt (G1: +0.048pp). Root cause: arp_discount_pct
    # used 5% threshold which = $0.50 for a $10 4-pack (too wide for TPR detection).
    # v5 fixes: absolute $0.05 dollar threshold and display-lift ratio.
    ("arp_dollar_discount", "Absolute ARP drop vs 8w baseline ($0.05 = nickel standard)"),
    ("promo_lift_ratio",    "Promo display lift = total_units/base_units − 1 (price-independent)"),
    ("promo_intensity",     "Promo units fraction (re-test individually from v4 G1)"),
    ("is_promo_week",       "Promo binary flag (re-test individually from v4 G1)"),

    # ── Rolling elasticity v2 (MO_46 guardrail fix) ──────────────────────────
    # v4 rolling_elasticity hurt (+0.099pp). Root cause: PRICE_GUARDRAIL=$0.05
    # was applied to raw ARP, not arp/pack_count. Multi-packs passed trivially.
    # MO_46 now normalizes by pack_count — re-test to see if fix helps.
    ("rolling_elasticity",  "Price elasticity v2 (guardrail now applied to $/bar, not raw ARP)"),

    # ── Seasonal / format signals ─────────────────────────────────────────────
    ("holiday_week",  "Holiday week code (was −0.023pp in G2; below 0.05 threshold, test at 0.03)"),
    ("pack_count",    "Pack format (was −0.008pp in G3; below both thresholds — expect noise)"),
]

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]
DEC2025_CUTOFF  = pd.Timestamp("2026-01-01", tz="UTC")
PROMOTE_THRESHOLD = 0.03   # pp — tightened from 0.05pp justified by 3x series count (512 vs 164)


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
    train_list, val_list, test_list = [], [], []
    for _, g in df.groupby(GROUP_COLS):
        g = g.sort_values("__time")
        tr = g[g["__time"] < val_cut]
        va = g[(g["__time"] >= val_cut) & (g["__time"] < cutoff_utc)]
        te = g[(g["__time"] >= cutoff_utc) & (g["__time"] < cutoff_utc + pd.Timedelta(weeks=horizon))]
        if len(tr) >= min_train and len(te) >= min_test:
            train_list.append(tr)
            val_list.append(va)
            test_list.append(te)
    if not train_list:
        raise ValueError(f"No qualifying series at cutpoint {cutoff_utc}")
    return pd.concat(train_list), pd.concat(val_list), pd.concat(test_list), len(train_list)


def train_eval(train_df, val_df, test_df, feats, params=None):
    params = params or CHAMPION_PARAMS
    af = avail(feats, train_df)
    if not af:
        return np.nan, None
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
    return wmape(test_df["base_units"].values, pred), m


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
    dfcv = pd.DataFrame(rows)
    return dfcv, float(dfcv["wmape"].mean())


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
        "script":        "MO_53",
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


# ── Charts ─────────────────────────────────────────────────────────────────────

def chart_individual_results(results_df, champion_wmape, out_path):
    """Ranked horizontal bar chart of individual feature test results."""
    df = results_df.copy()
    df["delta"] = df["wmape"] - champion_wmape
    df = df.sort_values("delta")

    colors = ["#27ae60" if d <= -PROMOTE_THRESHOLD else ("#e74c3c" if d > 0 else "#f39c12")
              for d in df["delta"]]

    fig, ax = plt.subplots(figsize=(10, max(6, len(df) * 0.42)))
    bars = ax.barh(df["feature"], df["delta"], color=colors)
    ax.axvline(0, color="#2c3e50", lw=1.2)
    ax.axvline(-PROMOTE_THRESHOLD, color="#27ae60", lw=1, ls="--", alpha=0.7,
               label=f"Promote threshold (−{PROMOTE_THRESHOLD}pp)")
    ax.set_xlabel("wMAPE vs Champion (pp) — negative = improvement")
    ax.set_title(f"MO_53: Individual Feature Ablation (Dec 2025, champion={champion_wmape:.3f}%)")
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()


def chart_group_detail(results_df, champion_wmape, feature_group, title, out_path):
    """Detail chart for a subset of features."""
    sub = results_df[results_df["feature"].isin(feature_group)].copy()
    if sub.empty:
        return
    sub["delta"] = sub["wmape"] - champion_wmape
    sub = sub.sort_values("delta")
    colors = ["#27ae60" if d <= -PROMOTE_THRESHOLD else ("#e74c3c" if d > 0 else "#f39c12")
              for d in sub["delta"]]
    fig, ax = plt.subplots(figsize=(9, max(4, len(sub) * 0.5)))
    ax.barh(sub["feature"], sub["delta"], color=colors)
    ax.axvline(0, color="#2c3e50", lw=1.2)
    ax.axvline(-PROMOTE_THRESHOLD, color="#27ae60", lw=1, ls="--", alpha=0.7)
    ax.set_xlabel("wMAPE vs Champion (pp)")
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()


def chart_rolling_cv(cv_df_champion, cv_df_promoted, out_path):
    cutpoints = cv_df_champion["cutpoint"].tolist()
    x = np.arange(len(cutpoints))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(x - w/2, cv_df_champion["wmape"], w, label="Champion (MO_52)", color="#2c3e50")
    ax.bar(x + w/2, cv_df_promoted["wmape"],  w, label="Promoted (MO_53)", color="#27ae60")
    ax.set_xticks(x)
    ax.set_xticklabels(cutpoints)
    ax.set_ylabel("wMAPE (%)")
    ax.set_title("MO_53: Rolling 3-Cutpoint CV — Champion vs Promoted Feature Set")
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()


def chart_shap(model, test_df, feats, out_path):
    af = avail(feats, test_df)
    sample = test_df[af].sample(min(512, len(test_df)), random_state=42)
    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(sample)
    fig, ax = plt.subplots(figsize=(9, 6))
    shap.summary_plot(shap_vals, sample, plot_type="bar", show=False, max_display=20)
    plt.title("MO_53: SHAP Feature Importance — Promoted Feature Set")
    plt.tight_layout()
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close()


# ── HTML section builder ──────────────────────────────────────────────────────

def build_html_section22(chart_paths, results_df, cv_df_champion, cv_df_promoted,
                          promoted_feats, champion_wmape, promoted_wmape, is_new_champion):
    def img_b64(path):
        import base64
        with open(path, "rb") as fh:
            return "data:image/png;base64," + base64.b64encode(fh.read()).decode()

    champ_tag  = "★ New champion" if is_new_champion else "Champion unchanged"
    delta_cv   = champion_wmape - promoted_wmape
    delta_color = "#27ae60" if delta_cv > 0 else "#e74c3c"

    rows_html = ""
    for _, r in results_df.sort_values("wmape").iterrows():
        delta = r["wmape"] - champion_wmape
        color = "#27ae60" if delta <= -PROMOTE_THRESHOLD else (
                "#e74c3c" if delta > 0 else "#888")
        promoted_marker = " ✓" if r["feature"] in (promoted_feats or []) else ""
        rows_html += f"""
        <tr>
          <td style='padding:.4rem .7rem'>{r['feature']}{promoted_marker}</td>
          <td style='padding:.4rem .7rem;font-size:.8rem;color:#666'>{r.get('note','')[:70]}</td>
          <td style='padding:.4rem .7rem;text-align:right'>{r['wmape']:.3f}%</td>
          <td style='padding:.4rem .7rem;text-align:right;color:{color}'>{delta:+.3f}pp</td>
        </tr>"""

    cv_rows = ""
    for (_, rc), (_, rp) in zip(cv_df_champion.iterrows(), cv_df_promoted.iterrows()):
        d = rc["wmape"] - rp["wmape"]
        cv_rows += f"""
        <tr>
          <td style='padding:.4rem .7rem'>{rc['cutpoint']} (n={rc['n_series']})</td>
          <td style='padding:.4rem .7rem;text-align:right'>{rc['wmape']:.2f}%</td>
          <td style='padding:.4rem .7rem;text-align:right'>{rp['wmape']:.2f}%</td>
          <td style='padding:.4rem .7rem;text-align:right;color:{"#27ae60" if d>0 else "#e74c3c"}'>{d:+.3f}pp</td>
        </tr>"""

    imgs = {k: img_b64(v) for k, v in chart_paths.items() if os.path.exists(v)}

    section = f"""
<section style='font-family:sans-serif;max-width:1100px;margin:3rem auto;padding:0 1rem'>
  <h2 style='font-size:1.4rem;border-bottom:2px solid #2c3e50;padding-bottom:.5rem'>
    Section 22 — MO_53: Individual Feature Ablation + Brand-Split Donor Signals
  </h2>
  <p style='color:#555;font-size:.9rem'>
    MO_52 tested groups — this script tests each candidate individually to eliminate
    signal masking (e.g., donor_count −0.081pp was buried in G4 +0.052pp combined).
    Threshold tightened to {PROMOTE_THRESHOLD}pp (from 0.05pp) justified by 3× series count (512 vs 164).
    New signals: brand-split donors (competitor vs BUILT), TDP change, promo v2 (absolute $),
    rolling elasticity with fixed $/bar guardrail. {champ_tag}.
  </p>

  <div style='display:flex;gap:1.5rem;flex-wrap:wrap;margin-top:1rem'>
    <div style='background:#f0f9f0;border-left:4px solid #27ae60;padding:.7rem 1rem;flex:1;min-width:200px'>
      <strong>Champion wMAPE</strong><br><span style='font-size:1.3rem'>{champion_wmape:.3f}%</span><br>
      <small>MO_52 (26 features, 512 series)</small>
    </div>
    <div style='background:#f0f9f0;border-left:4px solid #2980b9;padding:.7rem 1rem;flex:1;min-width:200px'>
      <strong>Promoted Set avg CV</strong><br><span style='font-size:1.3rem;color:{delta_color}'>{promoted_wmape:.3f}%</span><br>
      <small>{delta_cv:+.3f}pp vs champion — {champ_tag}</small>
    </div>
    <div style='background:#f8f8f0;border-left:4px solid #f39c12;padding:.7rem 1rem;flex:1;min-width:200px'>
      <strong>Features Promoted</strong><br><span style='font-size:1.3rem'>{len(promoted_feats or [])}</span><br>
      <small>≥{PROMOTE_THRESHOLD}pp individual improvement</small>
    </div>
  </div>

  <h3 style='margin-top:1.5rem'>22.1 Individual Ablation Results (Dec 2025 cutpoint, ranked)</h3>
  <table style='width:100%;border-collapse:collapse;font-size:.85rem'>
    <thead>
      <tr style='background:#2c3e50;color:#fff'>
        <th style='padding:.5rem .7rem;text-align:left'>Feature (✓ = promoted)</th>
        <th style='padding:.5rem .7rem;text-align:left'>Hypothesis</th>
        <th style='padding:.5rem .7rem;text-align:right'>wMAPE</th>
        <th style='padding:.5rem .7rem;text-align:right'>vs Champion</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  {'<img src="' + imgs["individual_results"] + '" style="width:100%;margin-top:1rem">' if "individual_results" in imgs else ""}

  <h3 style='margin-top:1.5rem'>22.2 Brand-Split Donor Signal Comparison</h3>
  <p style='color:#555;font-size:.88rem'>
    Key insight: intra-BUILT cannibalization (shifting demand between own SKUs = zero-sum)
    must be separated from competitor cannibalization (gaining market share = value creation).
  </p>
  {'<img src="' + imgs["brand_split"] + '" style="width:100%;margin-top:.5rem">' if "brand_split" in imgs else ""}

  <h3 style='margin-top:1.5rem'>22.3 TDP Change + Promo v2 Signal Detail</h3>
  {'<img src="' + imgs["tdp_promo"] + '" style="width:100%;margin-top:.5rem">' if "tdp_promo" in imgs else ""}

  <h3 style='margin-top:1.5rem'>22.4 Rolling 3-Cutpoint CV — Champion vs Promoted Set</h3>
  <table style='width:100%;border-collapse:collapse;font-size:.88rem;margin-bottom:1rem'>
    <thead>
      <tr style='background:#2c3e50;color:#fff'>
        <th style='padding:.5rem .7rem;text-align:left'>Cutpoint</th>
        <th style='padding:.5rem .7rem;text-align:right'>Champion</th>
        <th style='padding:.5rem .7rem;text-align:right'>Promoted</th>
        <th style='padding:.5rem .7rem;text-align:right'>Δ</th>
      </tr>
    </thead>
    <tbody>{cv_rows}</tbody>
  </table>
  {'<img src="' + imgs["rolling_cv"] + '" style="width:100%;margin-top:.5rem">' if "rolling_cv" in imgs else ""}

  {'<h3 style="margin-top:1.5rem">22.5 SHAP Feature Importance — Promoted Set</h3><img src="' + imgs["shap"] + '" style="width:100%;margin-top:.5rem">' if "shap" in imgs else ""}

  <h3 style='margin-top:1.5rem'>22.6 Key Findings</h3>
  <ul style='font-size:.9rem;color:#333'>
    <li><strong>Brand-split hypothesis</strong>: competitor_donor_count and competitor_donor_units_wow
        isolate market share dynamics from intra-BUILT portfolio noise — see Section 22.2 detail.</li>
    <li><strong>TDP level vs. change</strong>: tdp and tdp_z8 (level) are in the champion.
        tdp_wow_delta and tdp_4w_momentum test whether distribution <em>growth rate</em>
        adds incremental predictive power beyond the level already captured.</li>
    <li><strong>Promo v2 fix</strong>: arp_discount_pct at 5% = $0.50 for a $10 4-pack.
        arp_dollar_discount ($0.05 absolute) and promo_lift_ratio (display lift) are
        more precise signals for TPR event detection.</li>
    <li><strong>Elasticity guardrail fix</strong>: rolling_elasticity v2 now applies the
        $0.05 guardrail to arp/pack_count ($/bar), not raw ARP. Previously multi-packs
        passed with scanner-level noise ($0.06 on a $10 package).</li>
  </ul>
</section>"""

    return section


def patch_html(section_html):
    if not os.path.exists(HTML_IN):
        print(f"  HTML not found at {HTML_IN} — skipping patch.")
        return
    with open(HTML_IN, "r", encoding="utf-8") as f:
        html = f.read()
    marker = "<!-- MO_53_SECTION_22 -->"
    if marker in html:
        start = html.index(marker)
        end   = html.index(marker, start + 1) + len(marker)
        html  = html[:start] + marker + section_html + marker + html[end:]
        print("  Section 22 replaced in HTML.")
    else:
        html = html + marker + section_html + marker
        print("  Section 22 appended to HTML.")
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("MO_53 — Individual Feature Ablation + Brand-Split Donor Signals")
    print("=" * 70)

    # ── 1. Load dataset ──────────────────────────────────────────────────────
    parquet_path = Path(OUTPUT_DIR) / "retailer_sales_weekly.parquet"
    print(f"\n[1] Loading {parquet_path} …")
    df = pd.read_parquet(parquet_path)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df["log_base_units"] = np.log1p(df["base_units"].clip(lower=0))

    print(f"  Rows: {len(df):,} | Series: {df.groupby(GROUP_COLS).ngroups:,}")
    print(f"  Columns: {len(df.columns):,}")
    print(f"  Date range: {df['__time'].min().date()} – {df['__time'].max().date()}")

    # Audit new v5 columns
    v5_new = [
        "competitor_donor_count", "built_donor_count",
        "competitor_donor_tdp_sum", "competitor_donor_units_wow",
        "built_donor_units_wow",
        "tdp_wow_delta", "tdp_4w_momentum",
        "arp_dollar_discount", "promo_lift_ratio",
    ]
    print("\n  MO_25 v5 new column availability:")
    for c in v5_new:
        if c in df.columns:
            cov = df[c].notna().mean() * 100
            print(f"    {c}: {cov:.1f}% coverage, mean={df[c].mean():.4f}")
        else:
            print(f"    {c}: MISSING — run MO_25 v5 first")

    missing_champ = [f for f in CHAMPION_FEATS if f not in df.columns]
    if missing_champ:
        raise SystemExit(f"Champion features missing from parquet: {missing_champ}")

    # ── 2. Baseline: evaluate champion on Dec 2025 cutpoint ─────────────────
    print("\n[2] Evaluating champion baseline on Dec 2025 cutpoint …")
    tr_dec, va_dec, te_dec, n_dec = qualify_cutpoint(df, DEC2025_CUTOFF)
    champion_wmape_dec, champ_model = train_eval(tr_dec, va_dec, te_dec, CHAMPION_FEATS)
    print(f"  Champion (MO_52 feature set): {champion_wmape_dec:.3f}% wMAPE on Dec 2025 "
          f"(n={n_dec} series)")

    # ── 3. Individual feature ablation ───────────────────────────────────────
    print(f"\n[3] Individual ablation — {len(CANDIDATES)} candidates "
          f"(threshold: {PROMOTE_THRESHOLD}pp) …")

    results = []
    promoted_features = []

    for feat, note in CANDIDATES:
        if feat not in df.columns:
            print(f"  SKIP {feat} — not in parquet (need MO_25 v5 run)")
            results.append({"feature": feat, "note": note, "wmape": np.nan, "delta": np.nan})
            continue
        if feat in CHAMPION_FEATS:
            print(f"  SKIP {feat} — already in champion feature set")
            continue

        test_feats = CHAMPION_FEATS + [feat]
        wm, _ = train_eval(tr_dec, va_dec, te_dec, test_feats)
        delta = wm - champion_wmape_dec
        promoted = delta <= -PROMOTE_THRESHOLD
        marker = " ✓ PROMOTED" if promoted else f" (Δ={delta:+.3f}pp)"
        print(f"  {feat}: {wm:.3f}% {marker}")
        results.append({"feature": feat, "note": note, "wmape": float(wm), "delta": float(delta)})
        if promoted:
            promoted_features.append(feat)

    results_df = pd.DataFrame(results).dropna(subset=["wmape"])
    results_df.to_csv(os.path.join(OUTPUT_DIR, "mo53_individual_ablation.csv"), index=False)
    print(f"\n  Promoted features ({len(promoted_features)}): {promoted_features}")

    # ── 4. Promoted feature set evaluation ───────────────────────────────────
    print("\n[4] Evaluating promoted feature set (if any) …")
    if promoted_features:
        promoted_feats = CHAMPION_FEATS + promoted_features
    else:
        promoted_feats = CHAMPION_FEATS.copy()
        print("  No features promoted — carrying forward champion feature set unchanged.")

    # Rolling 3-cutpoint CV on champion
    print("\n  Champion rolling CV:")
    cv_champ, avg_cv_champ = rolling_cv(df, CHAMPION_FEATS, "Champion")

    # Rolling 3-cutpoint CV on promoted set
    print("\n  Promoted set rolling CV:")
    cv_prom, avg_cv_prom = rolling_cv(df, promoted_feats, "Promoted")

    cv_champ.to_csv(os.path.join(OUTPUT_DIR, "mo53_champion_cv.csv"), index=False)
    cv_prom.to_csv(os.path.join(OUTPUT_DIR, "mo53_rolling_cv_results.csv"), index=False)

    print(f"\n  Champion avg CV:  {avg_cv_champ:.3f}%")
    print(f"  Promoted avg CV:  {avg_cv_prom:.3f}%")
    print(f"  Δ:                {avg_cv_champ - avg_cv_prom:+.3f}pp")

    # ── 5. SHAP on promoted set ───────────────────────────────────────────────
    print("\n[5] Training promoted set model for SHAP …")
    _, promoted_model = train_eval(tr_dec, va_dec, te_dec, promoted_feats)
    shap_path = os.path.join(OUTPUT_DIR, "v2_mo53_shap.png")
    if promoted_model is not None:
        try:
            chart_shap(promoted_model, te_dec, promoted_feats, shap_path)
            print(f"  SHAP chart saved → {shap_path}")
        except Exception as e:
            print(f"  SHAP failed: {e}")
            shap_path = None
    else:
        shap_path = None

    # ── 6. Champion-challenger update ────────────────────────────────────────
    print("\n[6] Champion-challenger update …")
    is_new_champion = update_model_history(
        "Promoted (MO_53 individual ablation)",
        champion_wmape_dec if not promoted_features else float(results_df.loc[
            results_df["feature"].isin(promoted_features), "wmape"
        ].min()) if promoted_features else champion_wmape_dec,
        avg_cv_prom,
        n_dec,
        CHAMPION_PARAMS,
        promoted_feats,
    )

    # ── 7. Charts ────────────────────────────────────────────────────────────
    print("\n[7] Generating charts …")
    path_individual = os.path.join(OUTPUT_DIR, "v2_mo53_individual_results.png")
    path_brand      = os.path.join(OUTPUT_DIR, "v2_mo53_brand_split_detail.png")
    path_tdp_promo  = os.path.join(OUTPUT_DIR, "v2_mo53_tdp_promo_detail.png")
    path_cv         = os.path.join(OUTPUT_DIR, "v2_mo53_rolling_cv.png")

    chart_individual_results(results_df, champion_wmape_dec, path_individual)

    brand_split_feats = [
        "competitor_donor_count", "built_donor_count", "donor_count",
        "competitor_donor_units_wow", "built_donor_units_wow",
        "competitor_donor_tdp_sum", "max_donor_cannibal_prob",
        "rolling_cannibal_pressure",
    ]
    chart_group_detail(
        results_df, champion_wmape_dec, brand_split_feats,
        "MO_53: Brand-Split Donor Signals (competitor vs BUILT sibling)",
        path_brand,
    )

    tdp_promo_feats = [
        "tdp_wow_delta", "tdp_4w_momentum",
        "arp_dollar_discount", "promo_lift_ratio", "promo_intensity", "is_promo_week",
        "rolling_elasticity", "holiday_week", "pack_count",
    ]
    chart_group_detail(
        results_df, champion_wmape_dec, tdp_promo_feats,
        "MO_53: TDP Change + Promo v2 + Elasticity (fixed guardrail)",
        path_tdp_promo,
    )

    chart_rolling_cv(cv_champ, cv_prom, path_cv)
    print(f"  Charts saved to {OUTPUT_DIR}")

    # ── 8. HTML Section 22 ───────────────────────────────────────────────────
    print("\n[8] Patching HTML Section 22 …")
    chart_paths = {
        "individual_results": path_individual,
        "brand_split":        path_brand,
        "tdp_promo":          path_tdp_promo,
        "rolling_cv":         path_cv,
    }
    if shap_path and os.path.exists(shap_path):
        chart_paths["shap"] = shap_path

    section_html = build_html_section22(
        chart_paths, results_df, cv_champ, cv_prom,
        promoted_features, avg_cv_champ, avg_cv_prom, is_new_champion,
    )
    patch_html(section_html)

    # ── 9. Summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("MO_53 COMPLETE")
    print(f"{'='*70}")
    print(f"  Champion (MO_52) avg CV wMAPE:  {avg_cv_champ:.3f}%")
    print(f"  Promoted (MO_53) avg CV wMAPE:  {avg_cv_prom:.3f}%")
    print(f"  Improvement:                     {avg_cv_champ - avg_cv_prom:+.3f}pp")
    print(f"  Promoted features ({len(promoted_features)}): {promoted_features}")
    print(f"  New champion:                    {is_new_champion}")
    print(f"\nNext: update MO_26 FEATURE_COLS with promoted set, re-run MO_26→MO_27.")
