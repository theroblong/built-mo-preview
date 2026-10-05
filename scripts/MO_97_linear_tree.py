#!/usr/bin/env python
"""MO_97 - does linear_tree remove the extrapolation ceiling, and does it help?

README 204 measured the mechanism: a constant-leaf GBDT predicts combinations of
leaf constants taken from training targets, so it cannot project a trend. On a
controlled trending series, trained to 60.1, the highest prediction was 59.39
when truth required 80.17. It binds hard -- 39% of Q1 2026 volume came from
series that exceeded their own pre-cutoff maximum.

`linear_tree=True` fits a LINEAR MODEL in each leaf instead of a constant, which
is the one LightGBM setting that can produce values outside the training range.
This tests it two ways, because wMAPE alone would not tell us whether the ceiling
actually lifted:

  PART A  controlled extrapolation check -- synthetic trending series, train on
          the first stretch, ask for predictions beyond the training max. This is
          a direct replication of the README 204 probe with linear_tree on.
  PART B  the real objective -- recursive wMAPE on MO_28R's 4 folds, same panel,
          same features, so the only change is the leaf model.

Caveats that have to be handled rather than assumed:
  - LightGBM does not support linear_tree with L1-type objectives. Production
    uses objective="quantile" (an L1-type), so the quantile arm is expected to
    fail and l2/tweedie arms are run alongside. A failure is reported, not hidden.
  - linear_tree substantially increases memory use.
  - Categorical features interact with linear_tree in ways the docs leave vague,
    so the categorical set is held identical across arms and any warning is shown.
"""
from __future__ import annotations

import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

warnings.filterwarnings("ignore")

import MO_28R_recursive_objective_optuna as R
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo97_linear_tree.json")
TREES = 1200
CUTOFFS_BACK = (13, 26, 39, 52)
BASE = dict(num_leaves=63, min_child_samples=20, learning_rate=0.05,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)


def part_a():
    """Replicate the README 204 extrapolation probe, with and without linear_tree."""
    print("PART A - controlled extrapolation probe")
    n = 400
    t = np.arange(n, dtype=float)
    y = 10 + 0.18 * t + np.sin(2 * np.pi * t / 52) * 2.0
    X = pd.DataFrame({"t": t, "lag1": np.r_[y[0], y[:-1]],
                      "roll4": pd.Series(y).rolling(4, min_periods=1).mean().values})
    cut = 280
    Xtr, ytr = X.iloc[:cut], y[:cut]
    Xte, yte = X.iloc[cut:], y[cut:]
    print(f"  training max target {ytr.max():.2f} | truth needed up to {yte.max():.2f}")
    for label, lt in (("constant leaves", False), ("linear_tree=True", True)):
        p = dict(BASE)
        if lt:
            p["linear_tree"] = True
            p["linear_lambda"] = 0.0
        m = lgb.LGBMRegressor(objective="regression", n_estimators=300, **p)
        m.fit(Xtr, ytr)
        pr = m.predict(Xte)
        over = (pr > ytr.max()).mean()
        print(f"    {label:<18s} max prediction {pr.max():7.2f}   "
              f"share above training max {over:5.0%}   "
              f"{'CEILING LIFTED' if pr.max() > ytr.max() * 1.02 else 'still capped'}")
    return None


def part_b():
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = R.load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    end = df["__time"].max()
    cuts = [end - pd.Timedelta(weeks=w) for w in CUTOFFS_BACK]

    print(f"\nPART B - recursive objective, {len(df):,} rows, folds "
          f"{[str(c.date()) for c in cuts]}\n")

    arms = [
        ("quantile, constant leaves (production)", "quantile", False),
        ("quantile, linear_tree",                  "quantile", True),
        ("l2, constant leaves",                    "regression", False),
        ("l2, linear_tree",                        "regression", True),
        ("tweedie, constant leaves",               "tweedie", False),
        ("tweedie, linear_tree",                   "tweedie", True),
    ]
    results = {}
    print(f"  {'arm':<40s} {'mean':>7s}   per-fold")
    for label, obj, lt in arms:
        p = dict(BASE)
        if obj == "quantile":
            p["alpha"] = 0.5
        if lt:
            p["linear_tree"] = True
            p["linear_lambda"] = 0.0
        scores, err = [], None
        for cut in cuts:
            tr = df[df["__time"] <= cut]
            if len(tr) < 1000:
                continue
            va = tr[tr["__time"] > cut - pd.Timedelta(weeks=R.HORIZON)]
            try:
                m = lgb.LGBMRegressor(objective=obj, n_estimators=TREES, **p)
                m.fit(tr[feats], np.log1p(tr["base_units"]),
                      eval_set=[(va[feats], np.log1p(va["base_units"]))],
                      callbacks=[lgb.early_stopping(80, verbose=False),
                                 lgb.log_evaluation(-1)])
                s = R.recursive_wmape_fast(m, df, feats, cats, cut, weeks)
            except Exception as e:                      # report, never hide
                err = f"{type(e).__name__}: {str(e)[:110]}"
                break
            if np.isfinite(s):
                scores.append(s)
        if err:
            print(f"  {label:<40s} {'FAILED':>7s}   {err}")
            results[label] = {"error": err}
            continue
        mu = float(np.mean(scores))
        results[label] = {"scores": scores, "mean": mu}
        print(f"  {label:<40s} {mu:>7.2f}   " + " ".join(f"{x:5.1f}" for x in scores))

    base = results.get("quantile, constant leaves (production)", {}).get("mean")
    if base:
        print(f"\n  {'arm':<40s} {'vs production':>14s}")
        for k, v in results.items():
            if "mean" in v:
                print(f"  {k:<40s} {v['mean']-base:>+13.2f}pp")
    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    part_a()
    part_b()
