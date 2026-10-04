#!/usr/bin/env python
"""MO_94 - how much headroom is there in LightGBM hyperparameters ALONE?

Jason: "Can we do better with LightGBM alone if we adjust hyperparameter tuning?
... I don't want to Frankenstein a bunch of things together to look good on this
snapshot but not work well going forward."

Hyperparameter tuning is the least Frankenstein option available: no new features,
no blends, no routers, no post-hoc multipliers. But MO_28R's 22 completed trials
cannot answer the question on their own, because the CURRENT production parameters
were never scored on the same folds. A best-of-22 number with no baseline says
nothing about headroom.

This evaluates production params on MO_28R's exact folds and objective, so the
comparison is like-for-like:

  baseline   MO_26 LGBM_BASE (lr 0.04, 63 leaves, ...) + RECENCY_LAMBDA 0.02
  tuned      MO_28R's best completed trial

Objective is the RECURSIVE wMAPE -- the job production actually does -- not the
one-step teacher-forced score that earlier tuning optimized and that runs ~9x
optimistic.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb
import optuna
import warnings

warnings.filterwarnings("ignore")

import MO_28R_recursive_objective_optuna as R
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo94_tuning_headroom.json")
CUTOFFS_BACK = (13, 26, 39, 52)      # MO_28R default folds
STUDY = "sqlite:///outputs/mo28r_study.db"

PRODUCTION = dict(
    learning_rate=0.04, num_leaves=63, min_child_samples=20,
    feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
    reg_alpha=0.1, reg_lambda=0.2,
    random_state=42, n_jobs=-1, verbose=-1,
)
PRODUCTION_LAMBDA = 0.02


def score_params(df, feats, cats, weeks, cuts, params, lam, label):
    scores = []
    for cut in cuts:
        tr = df[df["__time"] <= cut]
        if len(tr) < 1000:
            continue
        va = tr[tr["__time"] > cut - pd.Timedelta(weeks=R.HORIZON)]
        wk = ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0)
        sw = np.exp(-lam * wk)
        m = lgb.LGBMRegressor(objective="quantile", alpha=0.5,
                              n_estimators=R.N_TREES, **params)
        m.fit(tr[feats], np.log1p(tr["base_units"]), sample_weight=sw,
              eval_set=[(va[feats], np.log1p(va["base_units"]))],
              eval_metric="quantile",
              callbacks=[lgb.early_stopping(R.EARLY_STOP, verbose=False),
                         lgb.log_evaluation(-1)])
        s = R.recursive_wmape(m, df, feats, cats, cut, weeks)
        if np.isfinite(s):
            scores.append(s)
            print(f"    {label:<10s} cut {str(cut.date()):<11s} recursive wMAPE {s:>6.2f}")
    return scores


def main() -> None:
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = R.load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    end = df["__time"].max()
    cuts = [end - pd.Timedelta(weeks=w) for w in CUTOFFS_BACK]

    study = optuna.load_study(study_name="mo28r_recursive_v1", storage=STUDY)
    done = [t for t in study.trials if t.state.name == "COMPLETE" and t.value is not None]
    best = min(done, key=lambda t: t.value)
    tuned = {k: v for k, v in best.params.items() if k != "recency_lambda"}
    tuned.update(bagging_freq=5, random_state=42, n_jobs=-1, verbose=-1)
    tuned_lam = best.params["recency_lambda"]

    print("MO_94 - tuning headroom, like-for-like on MO_28R's folds")
    print(f"  panel {len(df):,} rows - folds {[str(c.date()) for c in cuts]}")
    print(f"  {len(done)} completed MO_28R trials; best = trial {best.number} ({best.value:.2f})\n")

    base = score_params(df, feats, cats, weeks, cuts, PRODUCTION, PRODUCTION_LAMBDA, "PRODUCTION")
    tune = score_params(df, feats, cats, weeks, cuts, tuned, tuned_lam, "TUNED")

    mb, mt = float(np.mean(base)), float(np.mean(tune))
    print(f"\n  PRODUCTION mean recursive wMAPE {mb:6.2f}")
    print(f"  TUNED      mean recursive wMAPE {mt:6.2f}")
    print(f"  headroom from hyperparameters alone: {mb - mt:+.2f}pp "
          f"({(mb - mt) / mb * 100:+.1f}%)")
    if mt >= mb:
        print("  -> tuning has NOT beaten production on these folds. "
              "22 trials is thin; the spread across trials was 4.4pp.")
    else:
        print("  -> real headroom, with NO new features or post-hoc adjustment.")

    OUT.write_text(json.dumps({
        "folds": [str(c.date()) for c in cuts],
        "production": {"params": PRODUCTION, "recency_lambda": PRODUCTION_LAMBDA,
                       "scores": base, "mean": mb},
        "tuned": {"params": tuned, "recency_lambda": tuned_lam,
                  "scores": tune, "mean": mt, "trial": best.number},
        "headroom_pp": mb - mt,
        "n_completed_trials": len(done),
    }, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
