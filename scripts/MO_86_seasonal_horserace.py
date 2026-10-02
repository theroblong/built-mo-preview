"""MO_86 — Seasonal horse race. Can the single recursive LightGBM learn the Q1 pivot NATIVELY?

THE PROBLEM, IN FIVE MEASURED MECHANISMS
----------------------------------------
Q1 2026 (cutoff 2025-12-28): production forecast FELL 41% while actual demand ROSE 53%. Not
under-calling — pointing the wrong way, in BUILT's most important quarter. Five causes, all
mechanical:

  1. Momentum/rolling features are FROZEN at the anchor row for all 13 steps. The anchor is late
     December, so the model is shown trough momentum for every week of Jan-Mar.
  2. We forecast FROM the trough, and `lag1` becomes the model's own prior output.
  3. Exactly ONE feature of 56 knows what last January did (`base_units_lag52`), ranked 33rd.
     All seasonal + year-ago features together are ~4% of total gain.
  4. `lag52`'s LEVEL is wrong anyway. BUILT grew 4.01x then 1.63x, so a year-ago value
     understates current demand by ~39%. The model ignores it or is dragged down by it.
  5. ⭐ THE EXTRAPOLATION CEILING. A constant-leaf GBDT predicts a combination of leaf values
     taken from TRAINING TARGETS, so it resists producing anything beyond the observed range.
     Verified: trained to 60.1, max prediction 59.39 where truth needed 80.17. In Q1 2026,
     292 of 957 series (30.5%) peaked above their own pre-cutoff max, carrying 39.0% of the
     quarter's volume.

WHY SEASONAL DIFFERENCING IS ARM #1
-----------------------------------
`log1p(y_t) − log1p(y_{t−52})` fixes (4) and (5) together:
  * the TARGET becomes year-over-year GROWTH — a ratio that stays inside the training range even
    when the level does not, so the ceiling never binds;
  * the LEVEL is restored afterwards from `lag52`, not produced by a leaf constant, so the 39%
    growth drag disappears instead of pulling the forecast down.
This is exactly why SARIMA differences a trending seasonal series.

Leakage note: for horizon h after the cutoff, `lag52` is the actual at (cutoff + h − 52 weeks),
i.e. 39-51 weeks BEFORE the cutoff. Always a real pre-cutoff observation. No leakage.

ARMS
----
  baseline            production as it runs today (log1p level target)
  seasonal_diff   ⭐  target = log1p(y_t) − log1p(y_{t−52}); level restored from lag52
  seasonal_ratio_feat add `lag52 / trailing-52wk mean` as a FEATURE (the +0.66-stable shape,
                      expressed as a ratio instead of a level)
  harmonics_4         add Fourier at periods 52/3 and 52/4 (K=2 captures only 77% of the real
                      +48% Dec->Mar swing; K=4 reaches 87%)
  powerlaw_weight     sample weight t**0.5 instead of exp(-0.02*age) — preserves the mid-tail
                      where our only prior Januaries live (0.62 vs 0.18 at 87 weeks ago)
  recency_0           no recency weighting at all

Everything is NATIVE to the model. No post-hoc blending, no hard-coded seasonal correction — the
question is whether the MODEL picks the pivot up, per Jason's instruction.

Scored on the honest quarterly harness (both arms retrained at EVERY cutoff on pre-cutoff data
only). Baselines to beat: production 37.0 mean / 56.9 Q1 2026; flat_anchor 32.7; direct 34.0.

Run:  python MO_86_seasonal_horserace.py [--trees 800] [--arms baseline,seasonal_diff]
"""
from __future__ import annotations

import argparse
import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

warnings.filterwarnings("ignore")

from mo_panel import (CAT_COLS, GROUP_COLS, drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_ak_hi_market_variants)

PARQUET  = Path("outputs/retailer_sales_weekly.parquet")
OUT_JSON = Path("outputs/mo86_seasonal_horserace.json")
HORIZON  = 13
LGBM = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)
QUARTERS = [("Q1 2025", "2024-12-29"), ("Q2 2025", "2025-03-30"), ("Q3 2025", "2025-06-29"),
            ("Q4 2025", "2025-09-28"), ("Q1 2026", "2025-12-28"), ("Q2 2026", "2026-03-29"),
            ("Q3 2026", "2026-06-29")]
ARMS = ["baseline", "seasonal_diff", "seasonal_ratio_feat", "harmonics_4",
        "powerlaw_weight", "recency_0"]


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = np.abs(a).sum()
    return float(np.abs(a - p).sum() / d * 100) if d > 0 else float("nan")


def load_panel(feats):
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    if "week_of_year" in df.columns:
        woy = pd.to_numeric(df["week_of_year"], errors="coerce").fillna(1)
        df["week_sin26"] = np.sin(2 * np.pi * woy / 26)
        df["week_cos26"] = np.cos(2 * np.pi * woy / 26)
    for c in [c for c in feats if c not in CAT_COLS]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c, fv in (("spins_flavor_canonical", "UNKNOWN"), ("source_brand", "UNKNOWN"),
                  ("geography_raw", "UNKNOWN"), ("spins_flavor_raw", "UNKNOWN"),
                  ("nfp_protein_range", "UNKNOWN")):
        if c in df.columns:
            df[c] = df[c].fillna(fv).astype(str).str.strip().replace("", fv)
    df = df.dropna(subset=["base_units"]).copy()
    df = fill_promo_mechanic_nulls(df, verbose=False)
    df = drop_military_accounts(df, verbose=False)
    df = drop_ak_hi_market_variants(df, verbose=False)
    df = drop_zero_volume_geographies(df, target="base_units", verbose=False)
    df = apply_rma_priority(df, verbose=False)
    for c in CAT_COLS:
        if c in df.columns:
            df[c] = df[c].astype("category")
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    g = df.groupby(GROUP_COLS, observed=True)["base_units"]
    # lag52 on the TRAINING rows, and a trailing 52-week mean for the ratio feature.
    # Trailing (not centred) so it is computable at forecast time without peeking ahead.
    df["_lag52"] = g.shift(52)
    df["_roll52"] = g.transform(lambda s: s.shift(1).rolling(52, min_periods=26).mean())
    df["_seasonal_ratio"] = df["_lag52"] / df["_roll52"].replace(0, np.nan)
    return df


def build_arm(df, feats, arm):
    """Return (feature_list, target_series, sample_weight_fn) for this arm."""
    fl = list(feats)
    if arm == "seasonal_ratio_feat":
        fl = fl + ["_seasonal_ratio"]
    if arm == "harmonics_4":
        fl = fl + ["week_sin3", "week_cos3", "week_sin4", "week_cos4"]
    return fl


def seasonal_terms(woy):
    """Fourier terms for a given week-of-year, including the 3rd and 4th harmonics."""
    t = float(woy)
    return {"week_sin": np.sin(2 * np.pi * t / 52), "week_cos": np.cos(2 * np.pi * t / 52),
            "week_sin26": np.sin(2 * np.pi * t / 26), "week_cos26": np.cos(2 * np.pi * t / 26),
            "week_sin3": np.sin(2 * np.pi * 3 * t / 52), "week_cos3": np.cos(2 * np.pi * 3 * t / 52),
            "week_sin4": np.sin(2 * np.pi * 4 * t / 52), "week_cos4": np.cos(2 * np.pi * 4 * t / 52)}


def main(trees, arms, account, channel):
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v11_full.pkl", "rb")).feature_name_)
    df = load_panel(feats)
    for k, v in seasonal_terms(1).items():
        if k not in df.columns:
            woy = pd.to_numeric(df["week_of_year"], errors="coerce").fillna(1).astype(float)
            for kk in ("week_sin3", "week_cos3", "week_sin4", "week_cos4"):
                h = 3 if "3" in kk else 4
                df[kk] = (np.sin if "sin" in kk else np.cos)(2 * np.pi * h * woy / 52)
            break
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    ev = (df["retail_account"] == account) & (df["channel_outlet"] == channel)
    print(f"MO_86 — seasonal horse race | {account} {channel}")
    print(f"  arms: {arms}")
    print(f"  baselines: production 37.0 mean / 56.9 Q1 2026 | flat 32.7 | direct 34.0\n")

    results = {}
    for ql, qc in QUARTERS:
        cut = pd.Timestamp(qc, tz="UTC")
        fw = list(weeks[weeks > cut][:HORIZON])
        if not fw:
            continue
        hist_all = df[df["__time"] <= cut]
        fut = df[ev & (df["__time"] > cut) & (df["__time"] <= fw[-1])]
        if fut.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 fut.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        eval_keys = {k[0] for k in truth}
        row = {"cutoff": qc, "n_series": len(eval_keys)}

        for arm in arms:
            fl = build_arm(df, feats, arm)
            tr = hist_all
            if arm == "seasonal_diff":
                tr = tr[tr["_lag52"].notna() & (tr["_lag52"] > 0)]
                y = np.log1p(tr["base_units"]) - np.log1p(tr["_lag52"])
            else:
                y = np.log1p(tr["base_units"])
            if len(tr) < 500:
                continue
            age = ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0)
            if arm == "recency_0":
                sw = np.ones(len(tr))
            elif arm == "powerlaw_weight":
                t_idx = (age.max() - age) + 1.0          # 1 = oldest, max = newest
                sw = (t_idx ** 0.5).values
            else:
                sw = np.exp(-0.02 * age).values
            va = tr.tail(max(200, len(tr) // 10))
            m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=trees, **LGBM)
            m.fit(tr[fl], y, sample_weight=sw,
                  eval_set=[(va[fl], y.loc[va.index])], eval_metric="quantile",
                  callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])

            preds = {}
            for key, g in hist_all[ev.reindex(hist_all.index, fill_value=False)].groupby(
                    GROUP_COLS, observed=True):
                if key not in eval_keys:
                    continue
                g = g.sort_values("__time")
                if len(g) < 4:
                    continue
                s_ = pd.to_numeric(g.set_index("__time")["base_units"], errors="coerce").fillna(0)
                hist = list(s_.values); n_act = len(hist)
                lag52_seq = [float(hist[n_act - 53 + i]) if 0 <= (n_act - 53 + i) < n_act else np.nan
                             for i in range(1, len(fw) + 1)]
                roll52 = float(np.mean(hist[-52:])) if len(hist) >= 26 else np.nan
                state = g.iloc[-1].copy(); h2 = list(hist)
                arp_h = list(pd.to_numeric(g["arp"], errors="coerce").ffill().values)
                for i, fd in enumerate(fw):
                    state.update(seasonal_terms(int(fd.isocalendar().week)))
                    state["base_units_lag1"]  = h2[-1]
                    state["base_units_lag4"]  = h2[-4]  if len(h2) >= 4  else np.nan
                    state["base_units_lag13"] = h2[-13] if len(h2) >= 13 else np.nan
                    state["base_units_lag52"] = lag52_seq[i]
                    state["_seasonal_ratio"] = (lag52_seq[i] / roll52
                                                if (np.isfinite(lag52_seq[i]) and roll52
                                                    and np.isfinite(roll52) and roll52 > 0)
                                                else np.nan)
                    if arp_h:
                        _ac = arp_h[-1]; _aw = arp_h[-8:]
                        state["arp"] = _ac
                        state["arp_lag1"] = arp_h[-2] if len(arp_h) >= 2 else _ac
                        state["arp_roll8_avg"] = float(np.nanmean(_aw))
                        state["arp_roll8_std"] = float(np.nanstd(_aw)) if len(_aw) > 1 else 0.0
                        state["arp_wow_delta"] = 0.0
                    X = pd.DataFrame([state])[fl]
                    for c, cc in cats.items():
                        if c in X.columns:
                            X[c] = pd.Categorical(X[c], categories=cc)
                    raw = float(m.predict(X)[0])
                    if arm == "seasonal_diff":
                        l52 = lag52_seq[i]
                        if np.isfinite(l52) and l52 > 0:
                            p = float(np.clip(np.expm1(np.log1p(l52) + raw), 0, None))
                        else:
                            p = h2[-1]        # no year-ago anchor -> hold last value
                    else:
                        p = float(np.clip(np.expm1(raw), 0, None))
                    h2.append(p); preds[(key, fd)] = p
            ks = [k for k in truth if k in preds]
            if not ks:
                continue
            a = np.array([truth[k] for k in ks]); p = np.array([preds[k] for k in ks])
            row[arm] = {"wmape": wmape(a, p),
                        "bias": float(p.sum() / a.sum()) if a.sum() else float("nan")}
        results[ql] = row
        print(f"  {ql:<9s} " + "  ".join(
            f"{a}={row[a]['wmape']:.1f}" for a in arms if a in row))

    print(f"\n{'='*92}")
    print(f"  {'arm':<22s} " + " ".join(f"{q.split()[0]+q.split()[1][-2:]:>7s}" for q, _ in QUARTERS) + f" {'MEAN':>7s}")
    summary = {}
    for a in arms:
        vals = [results[q][a]["wmape"] for q, _ in QUARTERS if q in results and a in results[q]]
        if not vals:
            continue
        summary[a] = {"mean_wmape": float(np.mean(vals)),
                      "q1_2026": results.get("Q1 2026", {}).get(a, {}).get("wmape"),
                      "per_quarter": {q: results[q][a]["wmape"] for q, _ in QUARTERS
                                      if q in results and a in results[q]}}
        cells = " ".join(f"{results[q][a]['wmape']:>7.1f}" for q, _ in QUARTERS
                         if q in results and a in results[q])
        print(f"  {a:<22s} {cells} {np.mean(vals):>7.1f}")
    if summary:
        best = min(summary, key=lambda k: summary[k]["mean_wmape"])
        base = summary.get("baseline", {}).get("mean_wmape")
        print(f"\n  BEST MEAN: {best} at {summary[best]['mean_wmape']:.1f}"
              + (f"   (baseline {base:.1f}, {summary[best]['mean_wmape']-base:+.1f}pp)" if base else ""))
        print(f"\n  Q1 2026 — the quarter that matters:")
        for a, v in sorted(((a, s["q1_2026"]) for a, s in summary.items() if s["q1_2026"]),
                           key=lambda x: x[1]):
            print(f"    {a:<22s} {v:>6.1f}")
    OUT_JSON.write_text(json.dumps({"per_quarter": results, "summary": summary,
                                    "trees": trees, "arms": arms}, indent=2, default=float))
    print(f"\n  → {OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=800)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--account", default="KROGER")
    ap.add_argument("--channel", default="CONVENTIONAL|FOOD")
    a = ap.parse_args()
    main(a.trees, [x.strip() for x in a.arms.split(",")], a.account, a.channel)
