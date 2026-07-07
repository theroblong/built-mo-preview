"""MO_56 — Time-Varying Mo Signal Ablation: cannibal_rate + price_elasticity_effect.

PURPOSE
-------
Previous Mo signals (cannibal_prob, implied_elasticity) are static per series —
same value every week, ICC=1.0, zero week-to-week predictive power (MO_41).
MO_25 v7 adds two correctly implemented time-varying signals:

  cannibal_rate            — from cannibalization_rate_weekly (MO_19), aggregated
                             per (focal, week), null→0. Rises at sibling launch,
                             decays as consumers habituate. 18.4% rows nonzero.

  price_elasticity_effect  — arp_pct_change × implied_elasticity. Nonzero only
                             in price-event weeks (53.4% rows nonzero). Causally
                             interpretable: expected demand response given this
                             SKU's sensitivity and this week's actual price move.

CONDITIONAL EVALUATION (new in MO_56)
--------------------------------------
Global wMAPE dilutes Mo signal improvement across ~2,200 stable series. These
signals are designed to help in event-context weeks. We evaluate separately:

  EVENT rows:  weeks_since_launch ≤ 26  OR  |arp_pct_change| ≥ 0.05
  STABLE rows: everything else

Both global and conditional wMAPE reported for every candidate.
Promotion requires global ≥ 0.03pp OR (event improvement ≥ 0.05pp AND stable
doesn't worsen > +0.05pp). A signal that specifically helps launch/price events
is worth keeping even at a neutral global impact.

CANDIDATES (each tested individually, then combined)
-----------------------------------------------------
  A. cannibal_rate alone
  B. price_elasticity_effect alone
  C. Both combined

Champion: MO_53 28-feature set (avg 3-cutpoint wMAPE 6.413%).

OUTPUTS
-------
  outputs/mo56_individual_ablation.csv   — per-candidate global + conditional wMAPE
  outputs/mo56_rolling_cv_results.csv    — 3-cutpoint CV for promoted/best set
  outputs/v2_mo56_results.png            — global wMAPE bar chart (all 3 candidates)
  outputs/v2_mo56_conditional.png        — event-context vs stable split comparison
  outputs/v2_mo56_rolling_cv.png         — rolling CV chart if promoted
  outputs/v2_mo56_shap.png               — SHAP if new champion
  outputs/model_history.json             — champion-challenger update
  HTML Section 24 patched into outputs/built_demand_intelligence_report.html
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

# ── Champion: MO_53 28-feature set ────────────────────────────────────────────
CHAMPION_PARAMS = dict(
    objective="regression", boosting_type="gbdt",
    n_estimators=1000, learning_rate=0.04,
    min_child_samples=20, feature_fraction=0.8,
    bagging_fraction=0.8, bagging_freq=5,
    reg_alpha=0.3, reg_lambda=0.3, num_leaves=63,
    random_state=42, n_jobs=-1, verbose=-1,
)

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
    "donor_count",       # MO_53 promoted (−0.081pp)
    "tdp_wow_delta",     # MO_53 promoted (−0.045pp)
]

# ── Candidates ────────────────────────────────────────────────────────────────
CANDIDATES = [
    ("cannibal_rate",
     "Time-varying cannibalization rate from MO_19 (null→0); rises at sibling launch"),
    ("price_elasticity_effect",
     "arp_pct_change × implied_elasticity; nonzero only in price-event weeks"),
    ("cannibal_rate+price_elasticity_effect",
     "Both signals combined — complementary: rate captures competitive pressure, "
     "effect captures price response"),
]

GROUP_COLS            = ["upc", "channel_outlet", "retail_account", "geography_raw"]
DEC2025_CUTOFF        = pd.Timestamp("2026-01-01", tz="UTC")
PROMOTE_THRESHOLD     = 0.03   # pp global improvement (consistent with MO_53)
PROMOTE_EVENT_THRESH  = 0.05   # pp event-context improvement (secondary criterion)
PENALIZE_STABLE_CAP   = 0.05   # pp — promote if event improves even if stable worsens < this
EVENT_LAUNCH_WINDOW   = 26     # weeks_since_launch ≤ N → event row
EVENT_PRICE_THRESHOLD = 0.05   # |arp_pct_change| ≥ N → event row


# ── Helpers ───────────────────────────────────────────────────────────────────

def wmape(actual, predicted):
    total = np.nansum(np.abs(actual))
    if total < 1e-9:
        return np.nan
    return np.nansum(np.abs(actual - predicted)) / total * 100


def avail(feats, df):
    return [f for f in feats if f in df.columns]


def event_mask_for(df):
    """True for rows that are in launch window OR significant price-change weeks."""
    launch = df["weeks_since_launch"] <= EVENT_LAUNCH_WINDOW
    price  = df["arp_pct_change"].abs() >= EVENT_PRICE_THRESHOLD if "arp_pct_change" in df.columns \
             else pd.Series(False, index=df.index)
    return (launch | price).values


def qualify_cutpoint(df, cutoff_utc, min_train=52, min_test=13, horizon=13):
    val_cut = cutoff_utc - pd.Timedelta(weeks=8)
    train_list, val_list, test_list = [], [], []
    for _, g in df.groupby(GROUP_COLS):
        g = g.sort_values("__time")
        tr = g[g["__time"] < val_cut]
        va = g[(g["__time"] >= val_cut) & (g["__time"] < cutoff_utc)]
        te = g[(g["__time"] >= cutoff_utc) &
               (g["__time"] < cutoff_utc + pd.Timedelta(weeks=horizon))]
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


def train_eval_conditional(train_df, val_df, test_df, feats, params=None):
    """Train model and return (global_wmape, event_wmape, stable_wmape, model)."""
    params = params or CHAMPION_PARAMS
    af = avail(feats, train_df)
    if not af:
        return np.nan, np.nan, np.nan, None
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
    actual   = test_df["base_units"].values

    global_wm = wmape(actual, pred)

    emask = event_mask_for(test_df)
    event_wm  = wmape(actual[emask],  pred[emask])  if emask.any()  else np.nan
    stable_wm = wmape(actual[~emask], pred[~emask]) if (~emask).any() else np.nan

    return global_wm, event_wm, stable_wm, m


def rolling_cv_global(df, feats, label, params=None):
    """3-cutpoint CV (global wMAPE only — used for champion-challenger update)."""
    cutpoints = [
        ("Jun 2025", pd.Timestamp("2025-07-01", tz="UTC")),
        ("Sep 2025", pd.Timestamp("2025-10-01", tz="UTC")),
        ("Dec 2025", pd.Timestamp("2026-01-01", tz="UTC")),
    ]
    rows = []
    for name, cutoff in cutpoints:
        tr, va, te, n = qualify_cutpoint(df, cutoff)
        wm, _, _, _ = train_eval_conditional(tr, va, te, feats, params)
        rows.append({"cutpoint": name, "n_series": n, "variant": label, "wmape": wm})
        print(f"    {name} (n={n}): {label} global={wm:.3f}%")
    dfcv = pd.DataFrame(rows)
    return dfcv, float(dfcv["wmape"].mean())


def should_promote(global_delta, event_delta, stable_delta):
    """Return True if candidate meets promotion criteria."""
    if global_delta <= -PROMOTE_THRESHOLD:
        return True, "global"
    if (not np.isnan(event_delta) and event_delta <= -PROMOTE_EVENT_THRESH and
            (np.isnan(stable_delta) or stable_delta <= PENALIZE_STABLE_CAP)):
        return True, "event-context"
    return False, None


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
        "script":        "MO_56",
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

def chart_global_results(results, champion_wmape, out_path):
    labels = [r["label"] for r in results]
    deltas = [r["global_wmape"] - champion_wmape for r in results]
    colors = ["#27ae60" if d <= -PROMOTE_THRESHOLD else ("#f39c12" if d <= 0 else "#e74c3c")
              for d in deltas]
    fig, ax = plt.subplots(figsize=(9, max(4, len(labels) * 0.7)))
    ax.barh(labels, deltas, color=colors)
    ax.axvline(0, color="#2c3e50", lw=1.2)
    ax.axvline(-PROMOTE_THRESHOLD, color="#27ae60", lw=1, ls="--", alpha=0.7,
               label=f"Global promote threshold (−{PROMOTE_THRESHOLD}pp)")
    ax.set_xlabel("wMAPE vs MO_53 Champion (pp) — negative = improvement")
    ax.set_title(f"MO_56: Time-Varying Mo Signals — Global wMAPE "
                 f"(Dec 2025, champion={champion_wmape:.3f}%)")
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()


def chart_conditional(results, champ_global, champ_event, champ_stable, out_path):
    n = len(results)
    labels     = ["Champion"] + [r["label"] for r in results]
    globals_   = [champ_global]  + [r["global_wmape"]  for r in results]
    events_    = [champ_event]   + [r["event_wmape"]   for r in results]
    stables_   = [champ_stable]  + [r["stable_wmape"]  for r in results]

    x = np.arange(len(labels))
    w = 0.25
    fig, ax = plt.subplots(figsize=(max(9, len(labels) * 1.8), 5))
    ax.bar(x - w, globals_, w, label="Global",        color="#2c3e50", alpha=0.85)
    ax.bar(x,     events_,  w, label="Event-context", color="#e74c3c", alpha=0.85)
    ax.bar(x + w, stables_, w, label="Stable",        color="#27ae60", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=9)
    ax.set_ylabel("wMAPE (%)")
    ax.set_title(f"MO_56: Conditional Accuracy — Event-Context vs Stable Series\n"
                 f"(Event: wsl≤{EVENT_LAUNCH_WINDOW} or |Δprice|≥{EVENT_PRICE_THRESHOLD*100:.0f}%)")
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()


def chart_rolling_cv(cv_champ, cv_prom, label, out_path):
    cutpoints = cv_champ["cutpoint"].tolist()
    x = np.arange(len(cutpoints))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(x - w/2, cv_champ["wmape"], w, label="Champion (MO_53)", color="#2c3e50")
    ax.bar(x + w/2, cv_prom["wmape"],  w, label=f"Promoted ({label})", color="#27ae60")
    ax.set_xticks(x)
    ax.set_xticklabels(cutpoints)
    ax.set_ylabel("wMAPE (%)")
    ax.set_title("MO_56: Rolling 3-Cutpoint CV — Champion vs Promoted")
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
    plt.title("MO_56: SHAP Feature Importance — Promoted Feature Set")
    plt.tight_layout()
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close()


# ── HTML section 24 ──────────────────────────────────────────────────────────

def build_html_section24(results, chart_paths, cv_champ, cv_prom,
                          promoted_label, champ_global, champ_event, champ_stable,
                          promoted_feats, avg_cv_champ, avg_cv_prom, is_new_champion):
    def img_b64(path):
        import base64
        with open(path, "rb") as fh:
            return "data:image/png;base64," + base64.b64encode(fh.read()).decode()

    imgs = {k: img_b64(v) for k, v in chart_paths.items() if v and os.path.exists(v)}

    rows_html = ""
    for r in results:
        gd = r["global_wmape"] - champ_global
        ed = (r["event_wmape"]  - champ_event)  if not np.isnan(r["event_wmape"])  else float("nan")
        sd = (r["stable_wmape"] - champ_stable) if not np.isnan(r["stable_wmape"]) else float("nan")
        gc = "#27ae60" if gd <= -PROMOTE_THRESHOLD else ("#e74c3c" if gd > 0 else "#888")
        ec = "#27ae60" if (not np.isnan(ed) and ed < 0) else ("#e74c3c" if (not np.isnan(ed) and ed > 0) else "#888")
        sc = "#e74c3c" if (not np.isnan(sd) and sd > 0) else ("#27ae60" if (not np.isnan(sd) and sd < 0) else "#888")
        prom_mark = " ✓" if r.get("promoted") else ""
        ed_str = f"{ed:+.3f}pp" if not np.isnan(ed) else "n/a"
        sd_str = f"{sd:+.3f}pp" if not np.isnan(sd) else "n/a"
        rows_html += f"""
        <tr>
          <td style='padding:.4rem .7rem'>{r['label']}{prom_mark}</td>
          <td style='padding:.4rem .7rem;text-align:right'>{r['global_wmape']:.3f}%</td>
          <td style='padding:.4rem .7rem;text-align:right;color:{gc}'>{gd:+.3f}pp</td>
          <td style='padding:.4rem .7rem;text-align:right'>{r['event_wmape']:.3f}%</td>
          <td style='padding:.4rem .7rem;text-align:right;color:{ec}'>{ed_str}</td>
          <td style='padding:.4rem .7rem;text-align:right'>{r['stable_wmape']:.3f}%</td>
          <td style='padding:.4rem .7rem;text-align:right;color:{sc}'>{sd_str}</td>
        </tr>"""

    cv_rows = ""
    if cv_champ is not None and cv_prom is not None:
        for (_, rc), (_, rp) in zip(cv_champ.iterrows(), cv_prom.iterrows()):
            d = rc["wmape"] - rp["wmape"]
            cv_rows += f"""
            <tr>
              <td style='padding:.4rem .7rem'>{rc['cutpoint']} (n={rc['n_series']})</td>
              <td style='padding:.4rem .7rem;text-align:right'>{rc['wmape']:.2f}%</td>
              <td style='padding:.4rem .7rem;text-align:right'>{rp['wmape']:.2f}%</td>
              <td style='padding:.4rem .7rem;text-align:right;color:{"#27ae60" if d>0 else "#e74c3c"}'>{d:+.3f}pp</td>
            </tr>"""

    champ_tag  = "★ New champion" if is_new_champion else "Champion unchanged"
    delta_cv   = avg_cv_champ - avg_cv_prom if avg_cv_prom else float("nan")

    section = f"""
<section style='font-family:sans-serif;max-width:1100px;margin:3rem auto;padding:0 1rem'>
  <h2 style='font-size:1.4rem;border-bottom:2px solid #2c3e50;padding-bottom:.5rem'>
    Section 24 — MO_56: Time-Varying Mo Intelligence Signals
  </h2>
  <p style='color:#555;font-size:.9rem'>
    Root cause fix for prior Mo signal failures: <code>cannibal_prob</code> and
    <code>implied_elasticity</code> (both ICC=1.0, constant per series) are replaced by
    <code>cannibal_rate</code> (weekly rate from MO_19, null→0) and
    <code>price_elasticity_effect</code> (arp_pct_change × ε — nonzero only when price moves).
    New conditional evaluation split: <em>event-context rows</em>
    (wsl≤{EVENT_LAUNCH_WINDOW} or |Δprice|≥{EVENT_PRICE_THRESHOLD*100:.0f}%) vs <em>stable rows</em>.
    Global wMAPE is reported alongside each subset. {champ_tag}.
  </p>

  <div style='display:flex;gap:1.5rem;flex-wrap:wrap;margin-top:1rem'>
    <div style='background:#f0f0f8;border-left:4px solid #2c3e50;padding:.7rem 1rem;flex:1;min-width:180px'>
      <strong>Champion (MO_53)</strong><br>
      Global: <span style='font-size:1.2rem'>{champ_global:.3f}%</span><br>
      Event:  {champ_event:.3f}%&nbsp;&nbsp;Stable: {champ_stable:.3f}%<br>
      <small>28 features, 3-cutpoint avg {avg_cv_champ:.3f}%</small>
    </div>
    <div style='background:#f0f9f0;border-left:4px solid #27ae60;padding:.7rem 1rem;flex:1;min-width:180px'>
      <strong>Best promoted set</strong><br>
      <span style='font-size:1.1rem;color:{"#27ae60" if delta_cv>0 else "#e74c3c"}'>{avg_cv_prom:.3f}%</span>
      &nbsp;<small>({delta_cv:+.3f}pp avg CV)</small><br>
      <small>{promoted_label}</small>
    </div>
  </div>

  <h3 style='margin-top:1.5rem'>24.1 Individual Candidate Results — Global + Conditional (Dec 2025)</h3>
  <p style='color:#555;font-size:.88rem'>
    Champion baseline: Global={champ_global:.3f}%  Event-context={champ_event:.3f}%  Stable={champ_stable:.3f}%.
    ✓ = promoted (global ≥{PROMOTE_THRESHOLD}pp OR event ≥{PROMOTE_EVENT_THRESH}pp with stable worsening &lt;{PENALIZE_STABLE_CAP}pp).
  </p>
  <table style='width:100%;border-collapse:collapse;font-size:.85rem'>
    <thead>
      <tr style='background:#2c3e50;color:#fff'>
        <th style='padding:.5rem .7rem;text-align:left'>Candidate</th>
        <th style='padding:.5rem .7rem;text-align:right'>Global</th>
        <th style='padding:.5rem .7rem;text-align:right'>Δ Global</th>
        <th style='padding:.5rem .7rem;text-align:right'>Event</th>
        <th style='padding:.5rem .7rem;text-align:right'>Δ Event</th>
        <th style='padding:.5rem .7rem;text-align:right'>Stable</th>
        <th style='padding:.5rem .7rem;text-align:right'>Δ Stable</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>

  {'<img src="' + imgs["global_results"] + '" style="width:100%;margin-top:1rem">' if "global_results" in imgs else ""}

  <h3 style='margin-top:1.5rem'>24.2 Conditional Accuracy: Event-Context vs Stable Series</h3>
  <p style='color:#555;font-size:.88rem'>
    Event-context rows are where Mo signals are designed to add value — new launches
    (wsl ≤ {EVENT_LAUNCH_WINDOW}w) and significant price-change weeks (|Δprice| ≥ {EVENT_PRICE_THRESHOLD*100:.0f}%).
    Stable rows are mature SKUs with flat pricing — AR lags dominate there.
  </p>
  {'<img src="' + imgs["conditional"] + '" style="width:100%;margin-top:.5rem">' if "conditional" in imgs else ""}

  {'<h3 style="margin-top:1.5rem">24.3 Rolling 3-Cutpoint CV — Champion vs Promoted</h3>' +
   '<table style="width:100%;border-collapse:collapse;font-size:.88rem;margin-bottom:1rem"><thead><tr style="background:#2c3e50;color:#fff"><th style="padding:.5rem .7rem;text-align:left">Cutpoint</th><th style="padding:.5rem .7rem;text-align:right">Champion</th><th style="padding:.5rem .7rem;text-align:right">Promoted</th><th style="padding:.5rem .7rem;text-align:right">Δ</th></tr></thead><tbody>' + cv_rows + '</tbody></table>' if cv_rows else ""}
  {'<img src="' + imgs["rolling_cv"] + '" style="width:100%;margin-top:.5rem">' if "rolling_cv" in imgs else ""}

  {'<h3 style="margin-top:1.5rem">24.4 SHAP Feature Importance — Promoted Set</h3><img src="' + imgs["shap"] + '" style="width:100%;margin-top:.5rem">' if "shap" in imgs else ""}

  <h3 style='margin-top:1.5rem'>24.5 Signal Design Notes</h3>
  <ul style='font-size:.9rem;color:#333'>
    <li><strong>cannibal_rate</strong>: sourced from cannibalization_rate_weekly (MO_19).
        Already aggregated per (focal, week) as sum(cannibal_prob × max(0, −donor_wow_delta)) / focal_units.
        MO_50 failure was a missing fillna(0) — null = no active pair = 0 pressure, not missing data.
        18.4% of training rows nonzero; mean active rate = 0.431.</li>
    <li><strong>price_elasticity_effect</strong>: arp_pct_change × implied_elasticity.
        ε is static but acts as a multiplier on actual price movements — the interaction is time-varying.
        53.4% of training rows nonzero (all weeks with meaningful price change and known elasticity).</li>
    <li><strong>Conditional evaluation</strong>: Mo signals should help most on event rows.
        If global wMAPE is neutral but event-context improves ≥ 0.05pp without hurting stable,
        the signal is worth keeping for forecast explainability and launch-period accuracy.</li>
  </ul>
</section>"""
    return section


def patch_html(section_html):
    if not os.path.exists(HTML_IN):
        print(f"  HTML not found at {HTML_IN} — skipping patch.")
        return
    with open(HTML_IN, "r", encoding="utf-8") as f:
        html = f.read()
    marker = "<!-- MO_56_SECTION_24 -->"
    if marker in html:
        start = html.index(marker)
        end   = html.index(marker, start + 1) + len(marker)
        html  = html[:start] + marker + section_html + marker + html[end:]
        print("  Section 24 replaced in HTML.")
    else:
        html = html + marker + section_html + marker
        print("  Section 24 appended to HTML.")
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("MO_56 — Time-Varying Mo Signal Ablation")
    print("=" * 70)

    # ── Cache-skip: if prior results exist, patch HTML and exit early ─────────
    _ABLATION_CSV  = Path(OUTPUT_DIR) / "mo56_individual_ablation.csv"
    _CHAMP_CV_CSV  = Path(OUTPUT_DIR) / "mo56_champion_cv.csv"
    _PROM_CV_CSV   = Path(OUTPUT_DIR) / "mo56_rolling_cv_results.csv"
    _COND_CSV      = Path(OUTPUT_DIR) / "mo56_champion_conditional.csv"
    _PNG_MAIN      = Path(OUTPUT_DIR) / "v2_mo56_results.png"
    if all(p.exists() for p in [_ABLATION_CSV, _CHAMP_CV_CSV, _PROM_CV_CSV, _COND_CSV, _PNG_MAIN]):
        print("[CACHED] Prior results found — skipping ablation; regenerating HTML only …")
        import sys
        results_df = pd.read_csv(_ABLATION_CSV)
        cv_champ   = pd.read_csv(_CHAMP_CV_CSV)
        cv_prom    = pd.read_csv(_PROM_CV_CSV)
        cond_df    = pd.read_csv(_COND_CSV).set_index("subset")
        _champ_global = float(cond_df.loc["global",  "wmape"])
        _champ_event  = float(cond_df.loc["event",   "wmape"])
        _champ_stable = float(cond_df.loc["stable",  "wmape"])
        _avg_cv_champ = float(cv_champ["wmape"].mean())
        _avg_cv_prom  = float(cv_prom["wmape"].mean())
        _is_new = bool(_avg_cv_prom < _avg_cv_champ - PROMOTE_THRESHOLD)
        _best_label = "Champion (no promotion)"
        _best_feats = CHAMPION_FEATS
        _chart_paths = {k: str(Path(OUTPUT_DIR) / v) for k, v in {
            "global_results": "v2_mo56_results.png",
            "conditional":    "v2_mo56_conditional.png",
            "rolling_cv":     "v2_mo56_rolling_cv.png",
            "shap":           "v2_mo56_shap.png",
        }.items() if (Path(OUTPUT_DIR) / v).exists()}
        _valid_results = results_df.to_dict("records")
        _sec = build_html_section24(
            _valid_results, _chart_paths, cv_champ, cv_prom,
            _best_label, _champ_global, _champ_event, _champ_stable,
            _best_feats, _avg_cv_champ, _avg_cv_prom, _is_new,
        )
        patch_html(_sec)
        print("MO_56 COMPLETE (cached)")
        sys.exit(0)

    # ── 1. Load dataset ──────────────────────────────────────────────────────
    parquet_path = Path(OUTPUT_DIR) / "retailer_sales_weekly.parquet"
    print(f"\n[1] Loading {parquet_path} …")
    df = pd.read_parquet(parquet_path)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df["log_base_units"] = np.log1p(df["base_units"].clip(lower=0))

    print(f"  Rows: {len(df):,} | Series: {df.groupby(GROUP_COLS).ngroups:,}")
    print(f"  Date range: {df['__time'].min().date()} – {df['__time'].max().date()}")

    for col in ["cannibal_rate", "price_elasticity_effect", "arp_pct_change"]:
        if col in df.columns:
            nz = (df[col].abs() > 0.001).sum()
            print(f"  {col}: {nz:,} nonzero rows ({nz/len(df)*100:.1f}%)"
                  f"  mean(nonzero)={df.loc[df[col].abs()>0.001, col].mean():.4f}")
        else:
            print(f"  {col}: MISSING — run MO_25 v7 first")

    missing_champ = [f for f in CHAMPION_FEATS if f not in df.columns]
    if missing_champ:
        raise SystemExit(f"Champion features missing: {missing_champ}")

    # ── 2. Baseline on Dec 2025 cutpoint ────────────────────────────────────
    print("\n[2] Champion baseline — Dec 2025 cutpoint (global + conditional) …")
    tr_dec, va_dec, te_dec, n_dec = qualify_cutpoint(df, DEC2025_CUTOFF)

    emask_dec = event_mask_for(te_dec)
    n_event  = emask_dec.sum()
    n_stable = (~emask_dec).sum()
    print(f"  Test rows: {len(te_dec):,}  |  Event-context: {n_event:,} ({n_event/len(te_dec)*100:.1f}%)"
          f"  |  Stable: {n_stable:,} ({n_stable/len(te_dec)*100:.1f}%)")

    champ_global, champ_event, champ_stable, champ_model = train_eval_conditional(
        tr_dec, va_dec, te_dec, CHAMPION_FEATS
    )
    print(f"  Champion — Global: {champ_global:.3f}%  "
          f"Event-context: {champ_event:.3f}%  Stable: {champ_stable:.3f}%")

    # ── 3. Individual candidate ablation ─────────────────────────────────────
    print(f"\n[3] Candidate ablation ({len(CANDIDATES)} candidates) …")
    results = []
    for label, note in CANDIDATES:
        # Handle combined candidate
        feats_to_add = label.split("+")
        missing = [f for f in feats_to_add if f not in df.columns]
        if missing:
            print(f"  SKIP {label} — column(s) missing: {missing}")
            results.append({"label": label, "note": note,
                             "global_wmape": np.nan, "event_wmape": np.nan,
                             "stable_wmape": np.nan, "promoted": False})
            continue

        test_feats = CHAMPION_FEATS + feats_to_add
        g_wm, e_wm, s_wm, _ = train_eval_conditional(tr_dec, va_dec, te_dec, test_feats)

        g_delta = g_wm - champ_global
        e_delta = (e_wm - champ_event)  if not np.isnan(e_wm) else float("nan")
        s_delta = (s_wm - champ_stable) if not np.isnan(s_wm) else float("nan")

        promoted, reason = should_promote(g_delta, e_delta, s_delta)
        marker = f" ✓ PROMOTED ({reason})" if promoted else f" (Δglobal={g_delta:+.3f}pp)"
        print(f"  {label}: Global={g_wm:.3f}% ({g_delta:+.3f}pp) | "
              f"Event={e_wm:.3f}% ({e_delta:+.3f}pp) | "
              f"Stable={s_wm:.3f}% ({s_delta:+.3f}pp){marker}")
        results.append({
            "label": label, "note": note,
            "global_wmape": float(g_wm),
            "event_wmape":  float(e_wm),
            "stable_wmape": float(s_wm),
            "promoted": promoted, "promote_reason": reason,
        })

    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(OUTPUT_DIR, "mo56_individual_ablation.csv"), index=False)

    promoted_results = [r for r in results if r.get("promoted")]
    print(f"\n  Promoted candidates: {[r['label'] for r in promoted_results]}")

    # ── 4. Rolling CV on best promoted set (or champion if none) ─────────────
    print("\n[4] Rolling 3-cutpoint CV …")
    if promoted_results:
        # Pick the promoted set with best global wMAPE
        best = min(promoted_results, key=lambda r: r["global_wmape"])
        best_feats = CHAMPION_FEATS + best["label"].split("+")
        best_label = best["label"]
        print(f"  Running CV on promoted set: {best_label}")
    else:
        best_feats = CHAMPION_FEATS
        best_label = "Champion (no promotion)"
        print("  No candidates promoted — running CV on champion for reference.")

    print("\n  Champion rolling CV:")
    cv_champ, avg_cv_champ = rolling_cv_global(df, CHAMPION_FEATS, "Champion (MO_53)")

    print(f"\n  Promoted set rolling CV ({best_label}):")
    cv_prom, avg_cv_prom = rolling_cv_global(df, best_feats, best_label)

    cv_champ.to_csv(os.path.join(OUTPUT_DIR, "mo56_champion_cv.csv"), index=False)
    cv_prom.to_csv(os.path.join(OUTPUT_DIR, "mo56_rolling_cv_results.csv"), index=False)

    print(f"\n  Champion avg CV:  {avg_cv_champ:.3f}%")
    print(f"  Promoted avg CV:  {avg_cv_prom:.3f}%")
    print(f"  Δ:                {avg_cv_champ - avg_cv_prom:+.3f}pp")

    # ── 5. SHAP on best set ───────────────────────────────────────────────────
    print("\n[5] Training best set for SHAP …")
    _, _, _, best_model = train_eval_conditional(tr_dec, va_dec, te_dec, best_feats)
    shap_path = os.path.join(OUTPUT_DIR, "v2_mo56_shap.png")
    if best_model:
        try:
            chart_shap(best_model, te_dec, best_feats, shap_path)
            print(f"  SHAP saved → {shap_path}")
        except Exception as e:
            print(f"  SHAP failed: {e}")
            shap_path = None
    else:
        shap_path = None

    # ── 6. Champion-challenger update ─────────────────────────────────────────
    print("\n[6] Champion-challenger update …")
    best_global = min((r["global_wmape"] for r in promoted_results), default=champ_global)
    is_new_champion = update_model_history(
        f"MO_56 promoted ({best_label})",
        best_global, avg_cv_prom, n_dec, CHAMPION_PARAMS, best_feats,
    )

    # ── 7. Charts ─────────────────────────────────────────────────────────────
    print("\n[7] Generating charts …")
    valid_results = [r for r in results if not np.isnan(r["global_wmape"])]
    path_global = os.path.join(OUTPUT_DIR, "v2_mo56_results.png")
    path_cond   = os.path.join(OUTPUT_DIR, "v2_mo56_conditional.png")
    path_cv     = os.path.join(OUTPUT_DIR, "v2_mo56_rolling_cv.png")

    chart_global_results(valid_results, champ_global, path_global)
    chart_conditional(valid_results, champ_global, champ_event, champ_stable, path_cond)
    chart_rolling_cv(cv_champ, cv_prom, best_label, path_cv)
    print(f"  Charts saved to {OUTPUT_DIR}")

    # ── 8. HTML Section 24 ────────────────────────────────────────────────────
    print("\n[8] Patching HTML Section 24 …")
    chart_paths = {
        "global_results": path_global,
        "conditional":    path_cond,
        "rolling_cv":     path_cv,
    }
    if shap_path and os.path.exists(shap_path):
        chart_paths["shap"] = shap_path

    section_html = build_html_section24(
        valid_results, chart_paths, cv_champ, cv_prom,
        best_label, champ_global, champ_event, champ_stable,
        best_feats, avg_cv_champ, avg_cv_prom, is_new_champion,
    )
    patch_html(section_html)

    # ── 9. Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("MO_56 COMPLETE")
    print(f"{'='*70}")
    print(f"  Champion (MO_53) — Global: {champ_global:.3f}%  "
          f"Event: {champ_event:.3f}%  Stable: {champ_stable:.3f}%")
    print(f"  Promoted set ({best_label}):")
    print(f"    Champion avg CV: {avg_cv_champ:.3f}%")
    print(f"    Promoted avg CV: {avg_cv_prom:.3f}%")
    print(f"    Δ:               {avg_cv_champ - avg_cv_prom:+.3f}pp")
    print(f"  New champion: {is_new_champion}")
    print(f"\n  Promoted candidates ({len(promoted_results)}):")
    for r in promoted_results:
        print(f"    {r['label']} — promoted via {r.get('promote_reason','?')}")
    if not promoted_results:
        print("    None — champion unchanged")
    print(f"\nNext: if promoted → update MO_26 FEATURE_COLS and re-run MO_26→MO_27.")
    print(f"      Conditional breakdown shows Mo value on event series regardless of global result.")
