#!/usr/bin/env python
"""MO_120 - does source_brand rank higher on SHAP, under recency weighting, or in a
survival model?

JASON'S EXPECTATION, TAKEN SERIOUSLY
------------------------------------
    "I fully expect that source_brand should become a more important feature in the
     SHAP waterfall given what we know about BAR / PUFF / SOUR PUFF transition."

The transition is not in doubt. BUILT BAR fell from 34.1% of base units in 2023 to 0.3%
in 2026, its live series from 241 to 43, while PUFF went 144 -> 1,279 and SOUR PUFF
0 -> 277. Brand predicts whether a series still sells at all: exit rates are 91.9% for
BAR, 10.5% for PUFF and 1.0% for SOUR PUFF.

Yet source_brand ranks 54th of 56 by GAIN in the production level model. Three reasons
that ranking might be misleading, all tested here rather than argued:

PART 1 - GAIN IS NOT SHAP. Everything reported so far used
  `booster_.feature_importance("gain")`, which measures split quality during training.
  SHAP measures actual contribution to predictions and can rank differently, especially
  for a categorical that splits rarely but decisively. Computed exactly via LightGBM's
  `pred_contrib=True` (tree SHAP, not an approximation).

PART 2 - THE TRAINING MIX IS STALE. The model trains on all history, a third of which is
  a product now at 0.3% share. If brand's signal is being diluted by a regime that no
  longer exists, recency weighting should raise its SHAP rank. Two schemes, swept.

PART 3 - THE LEVEL MODEL ASKS THE WRONG QUESTION. A per-series conditional mean cannot
  represent "will this series still exist", which is what brand actually predicts. This
  fits the model the evidence implies -- P(series sells in the next 13 weeks) -- and
  reports where brand ranks THERE.

If brand stays low in Parts 1 and 2 but dominates Part 3, the conclusion is not that
brand is unimportant. It is that we have been modelling the wrong quantity, and brand's
rank is diagnostic of that rather than of brand.
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

import MO_80_quarterly_honest_backtest as M
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo120_brand_shap_and_survival.json")
CUT = pd.Timestamp("2026-06-07", tz="UTC")   # leaves 13 weeks of outcome for Part 3
HORIZON = 13
SHAP_SAMPLE = 30_000
TREES = 400
P = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20, feature_fraction=0.8,
         bagging_fraction=0.8, bagging_freq=5, reg_alpha=0.1, reg_lambda=0.2,
         random_state=42, n_jobs=-1, verbose=-1)


def shap_importance(model, X: pd.DataFrame) -> pd.Series:
    """Mean |SHAP| per feature. Exact tree SHAP via LightGBM, not an approximation."""
    sv = model.predict(X, pred_contrib=True)        # n x (n_features + 1); last = base
    imp = pd.Series(np.abs(sv[:, :-1]).mean(axis=0), index=list(X.columns))
    return (imp / imp.sum() * 100).sort_values(ascending=False)


def rank_of(s: pd.Series, name: str) -> tuple[int, float]:
    if name not in s.index:
        return (-1, float("nan"))
    return (int(s.rank(ascending=False)[name]), float(s[name]))


def fit_level(tr, feats, weights=None):
    m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=TREES, **P)
    m.fit(tr[feats], np.log1p(tr["base_units"]), sample_weight=weights)
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=SHAP_SAMPLE)
    a = ap.parse_args()

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    tr = df[df["__time"] <= CUT]
    res = {}

    # Sample for SHAP: it is O(n x trees x leaves), and 30k rows is ample for a ranking.
    Xs = tr.sample(min(a.sample, len(tr)), random_state=42)

    print("MO_120 - does source_brand rank higher on SHAP, with recency, or on survival?")
    print(f"  train through {CUT.date()} · {len(tr):,} rows · SHAP on {len(Xs):,}\n")

    # ── PART 1 ────────────────────────────────────────────────────────────────
    print("PART 1 — gain vs TRUE SHAP on the production level model\n")
    prod = pickle.load(open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb"))
    gain = pd.Series(prod.booster_.feature_importance("gain"), index=feats)
    gain = (gain / gain.sum() * 100).sort_values(ascending=False)
    sh = shap_importance(prod, Xs[feats])
    print(f"  {'feature':<26s} {'gain rank':>9s} {'gain %':>7s} {'SHAP rank':>10s} {'SHAP %':>7s}")
    watch = ["source_brand", "spins_flavor_canonical", "retail_account", "pack_count",
             "channel_outlet", "weeks_since_launch", "base_units_lag1",
             "base_units_roll4_avg", "tdp"]
    for c in watch:
        gr, gv = rank_of(gain, c); sr, svv = rank_of(sh, c)
        print(f"  {c:<26s} {gr:>9d} {gv:>6.2f}% {sr:>10d} {svv:>6.2f}%")
    res["part1"] = {"gain": {c: rank_of(gain, c) for c in watch},
                    "shap": {c: rank_of(sh, c) for c in watch},
                    "shap_top10": {k: float(v) for k, v in sh.head(10).items()}}
    br_g, br_s = rank_of(gain, "source_brand")[0], rank_of(sh, "source_brand")[0]
    print(f"\n  source_brand: gain rank {br_g} -> SHAP rank {br_s} of {len(feats)}"
          f"   {'MOVED UP' if br_s < br_g - 3 else 'essentially unchanged'}")

    # ── PART 2 ────────────────────────────────────────────────────────────────
    print("\nPART 2 — does recency weighting raise brand's SHAP rank?\n")
    age_wk = (CUT - tr["__time"]).dt.days / 7.0
    schemes = {"none": None,
               "halflife_26wk": np.power(0.5, age_wk / 26.0),
               "halflife_52wk": np.power(0.5, age_wk / 52.0),
               "linear_recent": 1.0 / (1.0 + age_wk / 52.0)}
    print(f"  {'weighting':<16s} {'brand SHAP rank':>16s} {'SHAP %':>8s} "
          f"{'BAR share of wt':>16s}")
    bar = (tr["source_brand"].astype(str) == "BUILT BAR").values
    res["part2"] = {}
    for name, w in schemes.items():
        wv = None if w is None else np.asarray(w, float)
        m = fit_level(tr, feats, wv)
        s = shap_importance(m, Xs[feats])
        r, v = rank_of(s, "source_brand")
        share = (bar.mean() if wv is None else wv[bar].sum() / wv.sum()) * 100
        res["part2"][name] = {"brand_rank": r, "brand_shap_pct": v, "bar_weight_pct": share}
        print(f"  {name:<16s} {r:>16d} {v:>7.3f}% {share:>15.1f}%")

    # ── PART 3 ────────────────────────────────────────────────────────────────
    print("\nPART 3 — the SURVIVAL model: P(series sells in the next 13 weeks)\n")
    fut = df[(df["__time"] > CUT) &
             (df["__time"] <= CUT + pd.Timedelta(weeks=HORIZON))]
    sold = set(fut[pd.to_numeric(fut["base_units"], errors="coerce").fillna(0) > 0]
               .groupby(GROUP_COLS, observed=True).groups.keys())
    # One row per series, taken at the cutoff: the state from which survival is predicted.
    last = tr.sort_values("__time").groupby(GROUP_COLS, observed=True).tail(1).copy()
    keys = list(zip(*[last[c] for c in GROUP_COLS]))
    last["survived"] = [1 if k in sold else 0 for k in keys]
    sfeats = [c for c in feats if c in last.columns]
    print(f"  {len(last):,} series at the cutoff · survival rate "
          f"{last['survived'].mean()*100:.1f}%")
    print("  by brand:")
    for b, g in last.groupby("source_brand", observed=True):
        if len(g) >= 30:
            print(f"    {str(b)[:24]:<26s} n={len(g):>5,}  survived {g['survived'].mean()*100:>5.1f}%")

    sm = lgb.LGBMClassifier(n_estimators=TREES, **P)
    sm.fit(last[sfeats], last["survived"])
    ss = shap_importance(sm, last[sfeats])
    print(f"\n  SURVIVAL model SHAP — top 12 of {len(sfeats)}:")
    for i, (c, v) in enumerate(ss.head(12).items(), 1):
        mark = "  <- source_brand" if c == "source_brand" else ""
        print(f"    {i:>2d}. {c:<30s} {v:>6.2f}%{mark}")
    r, v = rank_of(ss, "source_brand")
    res["part3"] = {"n_series": int(len(last)),
                    "survival_rate": float(last["survived"].mean()),
                    "brand_rank": r, "brand_shap_pct": v,
                    "shap_top12": {k: float(x) for k, x in ss.head(12).items()},
                    "by_brand": {str(b): float(g["survived"].mean())
                                 for b, g in last.groupby("source_brand", observed=True)
                                 if len(g) >= 30}}
    print(f"\n  source_brand in the SURVIVAL model: rank {r} of {len(sfeats)} ({v:.2f}%)"
          f"\n  source_brand in the LEVEL model:    rank {br_s} of {len(feats)}")

    print("\nVERDICT")
    if r <= 10 and br_s > 20:
        print("  Jason's expectation is right about the SIGNAL and the level model is the")
        print("  wrong place to look for it. Brand is a top-ranked SURVIVAL feature and a")
        print("  bottom-ranked LEVEL feature. The ranking is diagnostic of the question we")
        print("  are asking, not of the feature.")
    elif br_s <= 20:
        print("  Brand ranks materially higher on true SHAP than on gain — the earlier")
        print("  'inert' reading was an artifact of using gain as a proxy for SHAP.")
    else:
        print("  Brand stays low in both. The exit-rate signal is real but is not being")
        print("  captured by either model as specified; investigate before concluding.")

    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
