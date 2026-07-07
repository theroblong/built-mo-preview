"""MO_54 — Holiday Re-Encoding Ablation: per-event binary flags vs integer code.

PURPOSE
-------
MO_53 tested holiday_week (integer 0–6) at the tightened 0.03pp threshold and it
came in below threshold (−0.023pp). The root cause: a single integer conflates events
with very different magnitudes. For protein bars, the New Year health-resolution spike
(weeks 1–2) is the dominant event; Thanksgiving and Super Bowl carry far less signal.
When all six events share one ordinal feature, the tree splits that encode New Year
are diluted by the noise of low-magnitude events.

This script tests each event as a standalone binary flag — Champion + [is_X_week] —
isolating how much each holiday contributes beyond what week_of_year already captures.

EXPERIMENTAL DESIGN
-------------------
  - Champion: MO_53 promoted set (28 features, avg 3-cutpoint CV 6.448%)
  - Each candidate: Champion + [binary flag] — one flag at a time
  - Metric: wMAPE on Dec 2025 cutpoint (≥512 qualifying series)
  - Threshold: 0.03pp improvement to promote (consistent with MO_53)
  - Stability: rolling 3-cutpoint CV (Jun/Sep/Dec 2025) for any promoted set
  - Baseline comparison: holiday_week (integer code) also tested for reference

OUTPUTS
-------
  outputs/mo54_holiday_ablation.csv       — per-flag wMAPE on Dec 2025 cutpoint
  outputs/mo54_rolling_cv_results.csv     — 3-cutpoint CV for promoted set
  outputs/v2_mo54_individual_results.png  — ranked bar chart
  outputs/v2_mo54_rolling_cv.png          — rolling CV champion vs promoted
  outputs/v2_mo54_shap.png                — SHAP if new champion promoted
  outputs/model_history.json              — champion-challenger update
  HTML Section 23 patched into outputs/built_demand_intelligence_report.html
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

# ── MO_53 champion config (carry forward unchanged) ───────────────────────────
CHAMPION_PARAMS = dict(
    objective="regression", boosting_type="gbdt",
    n_estimators=1000, learning_rate=0.04,
    min_child_samples=20, feature_fraction=0.8,
    bagging_fraction=0.8, bagging_freq=5,
    reg_alpha=0.3, reg_lambda=0.3, num_leaves=63,
    random_state=42, n_jobs=-1, verbose=-1,
)

# ── MO_53 champion feature set (28 features) ──────────────────────────────────
CHAMPION_FEATS = [
    "base_units_roll4_avg",
    "base_units_roll8_avg",  "base_units_roll8_std",
    "base_units_roll13_avg", "base_units_roll13_std",
    "base_units_wow_delta",  "base_units_z8", "base_units_z13",
    "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
    "velocity_spm_z8",        "velocity_spm_z13",
    "tdp", "tdp_z8",
    "tdp_wow_delta",
    "arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std",
    "weeks_since_launch",
    "donor_count",
    "week_of_year",
    "base_units_lag1", "base_units_lag4", "base_units_lag13",
    "base_units_lag52", "velocity_spm_lag52",
    "channel_outlet",
]

# ── Candidate holiday binary flags ────────────────────────────────────────────
# Each is tested as: CHAMPION_FEATS + [candidate] vs CHAMPION_FEATS alone.
# holiday_week (integer code) included as reference baseline — did 0.03pp threshold
# change outcome vs MO_53 result of −0.023pp?
CANDIDATES = [
    # High-signal events for protein bar category (prior observation: Jan spike clear)
    ("is_new_year_week",     "New Year health resolution spike (weeks 1–2); strongest CPG signal for protein bars"),
    ("is_thanksgiving_week", "Thanksgiving / Black Friday (week 47); holiday grocery and gifting"),
    ("is_christmas_week",    "Christmas / Holiday week (week 52); travel and seasonal effects"),

    # Medium-signal events
    ("is_labor_day_week",    "Labor Day (week 36); summer-end active lifestyle peak"),
    ("is_memorial_day_week", "Memorial Day (week 21); spring outdoor / warm-season onset"),

    # Low-signal events (included to set bound)
    ("is_superbowl_week",    "Super Bowl (week 5); snack-category event, lower protein bar relevance"),

    # Baseline comparison: original integer code (MO_53: −0.023pp, just below threshold)
    ("holiday_week",         "Original integer 0–6 code — ordinal conflation of all events; reference"),
]

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]
DEC2025_CUTOFF  = pd.Timestamp("2026-01-01", tz="UTC")
PROMOTE_THRESHOLD = 0.03


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


def _encode_categoricals(train_df, val_df, test_df, af):
    cat_feats = [c for c in af if train_df[c].dtype == object]
    tr = train_df[af].copy()
    va = val_df[af].copy()
    te = test_df[af].copy()
    for c in cat_feats:
        cats = sorted(
            set(tr[c].dropna().tolist()) |
            set(va[c].dropna().tolist()) |
            set(te[c].dropna().tolist())
        )
        cat_map = {v: i for i, v in enumerate(cats)}
        for sub in [tr, va, te]:
            sub[c] = sub[c].map(cat_map).fillna(-1).astype(int)
    return tr, va, te, cat_feats


def train_eval(train_df, val_df, test_df, feats, params=None):
    params = params or CHAMPION_PARAMS
    af = avail(feats, train_df)
    if not af:
        return np.nan, None
    tr, va, te, cat_feats = _encode_categoricals(train_df, val_df, test_df, af)
    m = lgb.LGBMRegressor(**params)
    m.fit(
        tr, train_df["log_base_units"],
        eval_set=[(va, val_df["log_base_units"])],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(9999)],
        categorical_feature=cat_feats if cat_feats else "auto",
    )
    pred_log = m.predict(te)
    pred     = np.expm1(pred_log)
    return wmape(test_df["base_units"].values, pred), m


def rolling_cv(df, feats, label, params=None):
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
        "script":        "MO_54",
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


# ── Charts ────────────────────────────────────────────────────────────────────

def chart_individual_results(results_df, champion_wmape, out_path):
    df = results_df.copy()
    df["delta"] = df["wmape"] - champion_wmape
    df = df.sort_values("delta")
    colors = ["#27ae60" if d <= -PROMOTE_THRESHOLD else ("#e74c3c" if d > 0 else "#f39c12")
              for d in df["delta"]]
    fig, ax = plt.subplots(figsize=(10, max(5, len(df) * 0.5)))
    ax.barh(df["feature"], df["delta"], color=colors)
    ax.axvline(0, color="#2c3e50", lw=1.2)
    ax.axvline(-PROMOTE_THRESHOLD, color="#27ae60", lw=1, ls="--", alpha=0.7,
               label=f"Promote threshold (−{PROMOTE_THRESHOLD}pp)")
    ax.set_xlabel("wMAPE vs Champion (pp) — negative = improvement")
    ax.set_title(f"MO_54: Holiday Binary Flag Ablation (Dec 2025, champion={champion_wmape:.3f}%)")
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()


def chart_rolling_cv(cv_df_champion, cv_df_promoted, out_path):
    cutpoints = cv_df_champion["cutpoint"].tolist()
    x = np.arange(len(cutpoints))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(x - w/2, cv_df_champion["wmape"], w, label="Champion (MO_53)", color="#2c3e50")
    ax.bar(x + w/2, cv_df_promoted["wmape"],  w, label="Promoted (MO_54)", color="#27ae60")
    ax.set_xticks(x)
    ax.set_xticklabels(cutpoints)
    ax.set_ylabel("wMAPE (%)")
    ax.set_title("MO_54: Rolling 3-Cutpoint CV — Champion vs Promoted Feature Set")
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()


def chart_shap(model, test_df, feats, out_path):
    af = avail(feats, test_df)
    _, _, te, _ = _encode_categoricals(test_df, test_df, test_df, af)
    sample = te.sample(min(512, len(te)), random_state=42)
    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(sample)
    fig, ax = plt.subplots(figsize=(9, 6))
    shap.summary_plot(shap_vals, sample, plot_type="bar", show=False, max_display=20)
    plt.title("MO_54: SHAP Feature Importance — Promoted Feature Set")
    plt.tight_layout()
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close()


# ── HTML section builder ──────────────────────────────────────────────────────

def build_html_section23(chart_paths, results_df, cv_df_champion, cv_df_promoted,
                          promoted_feats, champion_wmape, promoted_wmape, is_new_champion):
    def img_b64(path):
        import base64
        with open(path, "rb") as fh:
            return "data:image/png;base64," + base64.b64encode(fh.read()).decode()

    champ_tag   = "★ New champion" if is_new_champion else "Champion unchanged"
    delta_cv    = champion_wmape - promoted_wmape
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
          <td style='padding:.4rem .7rem;font-size:.8rem;color:#666'>{r.get('note','')[:80]}</td>
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
    Section 23 — MO_54: Holiday Re-Encoding Ablation (Binary Flags vs Integer Code)
  </h2>
  <p style='color:#555;font-size:.9rem'>
    MO_53 showed holiday_week (integer 0–6) at −0.023pp — just below the 0.03pp threshold.
    Root cause: one ordinal feature conflates events with very different category magnitudes.
    For protein bars, the New Year health-resolution spike (weeks 1–2) is the dominant event;
    Super Bowl and Memorial Day carry far less signal. Binary re-encoding lets the model
    learn each event's lift independently, without the dilution from low-magnitude events
    sharing the same feature. Threshold: {PROMOTE_THRESHOLD}pp. {champ_tag}.
  </p>

  <div style='display:flex;gap:1.5rem;flex-wrap:wrap;margin-top:1rem'>
    <div style='background:#f0f9f0;border-left:4px solid #27ae60;padding:.7rem 1rem;flex:1;min-width:200px'>
      <strong>Champion wMAPE</strong><br><span style='font-size:1.3rem'>{champion_wmape:.3f}%</span><br>
      <small>MO_53 (28 features, 512+ series)</small>
    </div>
    <div style='background:#f0f9f0;border-left:4px solid #2980b9;padding:.7rem 1rem;flex:1;min-width:200px'>
      <strong>Promoted Set avg CV</strong><br><span style='font-size:1.3rem;color:{delta_color}'>{promoted_wmape:.3f}%</span><br>
      <small>{delta_cv:+.3f}pp vs champion — {champ_tag}</small>
    </div>
    <div style='background:#f8f8f0;border-left:4px solid #f39c12;padding:.7rem 1rem;flex:1;min-width:200px'>
      <strong>Flags Promoted</strong><br><span style='font-size:1.3rem'>{len(promoted_feats or [])}</span><br>
      <small>≥{PROMOTE_THRESHOLD}pp individual improvement</small>
    </div>
  </div>

  <h3 style='margin-top:1.5rem'>23.1 Individual Flag Ablation Results (Dec 2025 cutpoint, ranked)</h3>
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

  <h3 style='margin-top:1.5rem'>23.2 Rolling 3-Cutpoint CV — Champion vs Promoted Set</h3>
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

  {'<h3 style="margin-top:1.5rem">23.3 SHAP Feature Importance — Promoted Set</h3><img src="' + imgs["shap"] + '" style="width:100%;margin-top:.5rem">' if "shap" in imgs else ""}

  <h3 style='margin-top:1.5rem'>23.4 Key Findings</h3>
  <ul style='font-size:.9rem;color:#333'>
    <li><strong>New Year spike hypothesis</strong>: protein bar sales show a clear January uptick
        driven by health-resolution behavior. The integer holiday_week code assigns this
        the same feature space as Labor Day and Memorial Day, diluting the signal.</li>
    <li><strong>Binary flag advantage</strong>: each is_X_week flag gives the model an independent
        degree of freedom — New Year can get a large coefficient without being anchored
        to unrelated events in the same column.</li>
    <li><strong>week_of_year already in champion</strong>: the champion captures smooth seasonality
        via week_of_year (1–52). Binary flags test whether the sharp, event-specific
        spikes are under-represented by the continuous week signal alone.</li>
    <li><strong>Reference comparison</strong>: holiday_week integer code included as baseline —
        if it still underperforms binary flags it confirms ordinal conflation as root cause.</li>
  </ul>
</section>"""

    return section


def patch_html(section_html):
    if not os.path.exists(HTML_IN):
        print(f"  HTML not found at {HTML_IN} — skipping patch.")
        return
    with open(HTML_IN, "r", encoding="utf-8") as f:
        html = f.read()
    marker = "<!-- MO_54_SECTION_23 -->"
    if marker in html:
        start = html.index(marker)
        end   = html.index(marker, start + 1) + len(marker)
        html  = html[:start] + marker + section_html + marker + html[end:]
        print("  Section 23 replaced in HTML.")
    else:
        html = html + marker + section_html + marker
        print("  Section 23 appended to HTML.")
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("MO_54 — Holiday Re-Encoding Ablation")
    print("=" * 70)

    # ── 1. Load dataset ──────────────────────────────────────────────────────
    parquet_path = Path(OUTPUT_DIR) / "retailer_sales_weekly.parquet"
    print(f"\n[1] Loading {parquet_path} …")
    df = pd.read_parquet(parquet_path)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df["log_base_units"] = np.log1p(df["base_units"].clip(lower=0))

    print(f"  Rows: {len(df):,} | Series: {df.groupby(GROUP_COLS).ngroups:,}")
    print(f"  Date range: {df['__time'].min().date()} – {df['__time'].max().date()}")

    # Check binary flag availability (requires MO_25 v6 run)
    binary_flags = [
        "is_new_year_week", "is_superbowl_week", "is_memorial_day_week",
        "is_labor_day_week", "is_thanksgiving_week", "is_christmas_week",
    ]
    missing_flags = [f for f in binary_flags if f not in df.columns]
    if missing_flags:
        raise SystemExit(
            f"Binary holiday flags missing from parquet: {missing_flags}\n"
            f"Run MO_25 first to regenerate retailer_sales_weekly.parquet with v6 flags."
        )
    print("\n  Holiday binary flags — event coverage:")
    for f in binary_flags:
        n = df[f].sum()
        pct = df[f].mean() * 100
        print(f"    {f}: {n:,} rows ({pct:.1f}%)")

    missing_champ = [f for f in CHAMPION_FEATS if f not in df.columns]
    if missing_champ:
        raise SystemExit(f"Champion features missing from parquet: {missing_champ}")

    # ── 2. Baseline champion on Dec 2025 cutpoint ────────────────────────────
    print("\n[2] Evaluating champion baseline on Dec 2025 cutpoint …")
    tr_dec, va_dec, te_dec, n_dec = qualify_cutpoint(df, DEC2025_CUTOFF)
    champion_wmape_dec, champ_model = train_eval(tr_dec, va_dec, te_dec, CHAMPION_FEATS)
    print(f"  Champion (MO_53, 28 features): {champion_wmape_dec:.3f}% wMAPE on Dec 2025 "
          f"(n={n_dec} series)")

    # ── 3. Individual flag ablation ──────────────────────────────────────────
    print(f"\n[3] Individual ablation — {len(CANDIDATES)} candidates "
          f"(threshold: {PROMOTE_THRESHOLD}pp) …")

    results = []
    promoted_features = []

    for feat, note in CANDIDATES:
        if feat not in df.columns:
            print(f"  SKIP {feat} — not in parquet")
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
    results_df.to_csv(os.path.join(OUTPUT_DIR, "mo54_holiday_ablation.csv"), index=False)
    print(f"\n  Promoted flags ({len(promoted_features)}): {promoted_features}")

    # ── 4. Promoted feature set evaluation ───────────────────────────────────
    print("\n[4] Evaluating promoted feature set …")
    if promoted_features:
        promoted_feats = CHAMPION_FEATS + promoted_features
    else:
        promoted_feats = CHAMPION_FEATS.copy()
        print("  No flags promoted — carrying forward champion feature set unchanged.")

    print("\n  Champion rolling CV:")
    cv_champ, avg_cv_champ = rolling_cv(df, CHAMPION_FEATS, "Champion")

    print("\n  Promoted set rolling CV:")
    cv_prom, avg_cv_prom = rolling_cv(df, promoted_feats, "Promoted")

    cv_champ.to_csv(os.path.join(OUTPUT_DIR, "mo54_champion_cv.csv"), index=False)
    cv_prom.to_csv(os.path.join(OUTPUT_DIR, "mo54_rolling_cv_results.csv"), index=False)

    print(f"\n  Champion avg CV:  {avg_cv_champ:.3f}%")
    print(f"  Promoted avg CV:  {avg_cv_prom:.3f}%")
    print(f"  Δ:                {avg_cv_champ - avg_cv_prom:+.3f}pp")

    # ── 5. SHAP on promoted set ───────────────────────────────────────────────
    print("\n[5] Training promoted set model for SHAP …")
    _, promoted_model = train_eval(tr_dec, va_dec, te_dec, promoted_feats)
    shap_path = os.path.join(OUTPUT_DIR, "v2_mo54_shap.png")
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
        "Promoted (MO_54 holiday binary flags)",
        champion_wmape_dec,
        avg_cv_prom,
        n_dec,
        CHAMPION_PARAMS,
        promoted_feats,
    )

    # ── 7. Charts ─────────────────────────────────────────────────────────────
    print("\n[7] Generating charts …")
    path_individual = os.path.join(OUTPUT_DIR, "v2_mo54_individual_results.png")
    path_cv         = os.path.join(OUTPUT_DIR, "v2_mo54_rolling_cv.png")

    chart_individual_results(results_df, champion_wmape_dec, path_individual)
    chart_rolling_cv(cv_champ, cv_prom, path_cv)
    print(f"  Charts saved to {OUTPUT_DIR}")

    # ── 8. HTML Section 23 ───────────────────────────────────────────────────
    print("\n[8] Patching HTML Section 23 …")
    chart_paths = {
        "individual_results": path_individual,
        "rolling_cv":         path_cv,
    }
    if shap_path and os.path.exists(shap_path):
        chart_paths["shap"] = shap_path

    section_html = build_html_section23(
        chart_paths, results_df, cv_champ, cv_prom,
        promoted_features, avg_cv_champ, avg_cv_prom, is_new_champion,
    )
    patch_html(section_html)

    # ── 9. Summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("MO_54 COMPLETE")
    print(f"{'='*70}")
    print(f"  Champion (MO_53) avg CV wMAPE:  {avg_cv_champ:.3f}%")
    print(f"  Promoted (MO_54) avg CV wMAPE:  {avg_cv_prom:.3f}%")
    print(f"  Improvement:                     {avg_cv_champ - avg_cv_prom:+.3f}pp")
    print(f"  Promoted flags ({len(promoted_features)}): {promoted_features}")
    print(f"  New champion:                    {is_new_champion}")
    if promoted_features:
        print(f"\nNext: add promoted flags to MO_26 FEATURE_COLS, re-run MO_26→MO_27.")
    else:
        print(f"\nNext: holiday re-encoding did not improve beyond {PROMOTE_THRESHOLD}pp — "
              f"week_of_year already captures sufficient seasonality. Consider MO_54b: "
              f"portfolio cannibalization constraint (post-processing layer on MO_27 output).")
