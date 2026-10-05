#!/usr/bin/env python
"""MO_96 - own-brand donor features, tested one at a time, on the RECURSIVE objective.

Two questions from Jason, answered in one run.

(1) CAN THE MODEL SEE A SIBLING PACK?
BUILT's pack mix shifted hard -- 1-pack went 57.0% -> 46.8% of units while 4-pack
went 24.1% -> 41.2%. That is a CROSS-SERIES shift: each declining 1-pack shows its
own decline in its own lags, so `pack_count` cannot help (see below). What would
help is seeing a sibling ramp at the same shelf BEFORE it reaches the 1-pack's
sales history. Every own-brand donor column exists in the panel and NONE is in the
model:

    built_donor_count       100.0% non-null   not used
    built_donor_units_sum    29.5%            not used
    built_donor_units_wow    29.1%            not used
    built_donor_tdp_sum      29.5%            not used

The two donor features that ARE in the model (donor_count, top_donor_tdp_sum) are
brand-agnostic: they cannot distinguish "a competitor is pressuring this item"
from "our own 4-pack is eating this 1-pack". That distinction is the whole
pack-mix story.

Tested ONE AT A TIME, not as a block, so each earns its place or does not.
Prior evidence is mixed -- built_tdp_share was tested before and HURT, and
aggregate donor_count beat split versions -- so this is not a foregone conclusion.

(2) IS pack_count INERT AT HORIZON TOO?
One-step tests say pack_count is completely redundant: alone it scores wMAPE
97.76, adding it to the lags moves 4.32 -> 4.28, and permuting it in the full
model moves error by +0.000pp. But those are TEACHER-FORCED. In the recursive loop
the lags decay into the model's own predictions, so a stable item attribute could
matter more at week 13 than at week 1. The pack_perm arm permutes pack_count and
re-scores on the RECURSIVE objective to settle that.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings

warnings.filterwarnings("ignore")

import MO_28R_recursive_objective_optuna as R
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo96_own_brand_donor_ablation.json")
TREES = 1200
CUTOFFS_BACK = (13, 26, 39, 52)
CANDIDATES = [
    "built_donor_count",
    "built_donor_units_sum",
    "built_donor_units_wow",
    "built_donor_tdp_sum",
]
LGBM = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)


def score_arm(df, base_feats, extra, cuts, weeks, cats, permute=None):
    feats = base_feats + [c for c in extra if c not in base_feats]
    scores = []
    for cut in cuts:
        tr = df[df["__time"] <= cut]
        if len(tr) < 1000:
            continue
        va = tr[tr["__time"] > cut - pd.Timedelta(weeks=R.HORIZON)]
        m = lgb.LGBMRegressor(objective="quantile", alpha=0.5,
                              n_estimators=TREES, **LGBM)
        m.fit(tr[feats], np.log1p(tr["base_units"]),
              eval_set=[(va[feats], np.log1p(va["base_units"]))],
              eval_metric="quantile",
              callbacks=[lgb.early_stopping(80, verbose=False), lgb.log_evaluation(-1)])
        d = df
        if permute:
            d = df.copy()
            rng = np.random.default_rng(0)
            d[permute] = rng.permutation(d[permute].values)
        s = R.recursive_wmape_fast(m, d, feats, cats, cut, weeks)
        if np.isfinite(s):
            scores.append(s)
    return scores


def main() -> None:
    base_feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = R.load_panel(base_feats + CANDIDATES)
    for c in CANDIDATES:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    end = df["__time"].max()
    cuts = [end - pd.Timedelta(weeks=w) for w in CUTOFFS_BACK]

    missing = [c for c in CANDIDATES if c not in df.columns]
    if missing:
        raise SystemExit(f"MO_96: candidates absent from the panel: {missing}")

    print("MO_96 - own-brand donor features, one at a time, RECURSIVE objective")
    print(f"  panel {len(df):,} rows - {df.groupby(GROUP_COLS, observed=True).ngroups:,} series")
    print(f"  folds {[str(c.date()) for c in cuts]} - {TREES} trees\n")

    arms = [("base (56 features)", [], None)]
    arms += [(f"+ {c}", [c], None) for c in CANDIDATES]
    arms.append(("+ all four own-brand donors", CANDIDATES, None))
    arms.append(("base, pack_count PERMUTED", [], "pack_count"))

    results, base_mean = {}, None
    print(f"  {'arm':<30s} {'mean':>7s} {'vs base':>9s}   per-fold")
    for label, extra, perm in arms:
        sc = score_arm(df, base_feats, extra, cuts, weeks, cats, permute=perm)
        if not sc:
            print(f"  {label:<30s} {'--':>7s}")
            continue
        mu = float(np.mean(sc))
        if base_mean is None:
            base_mean = mu
        results[label] = {"scores": sc, "mean": mu, "delta": mu - base_mean}
        print(f"  {label:<30s} {mu:>7.2f} {mu-base_mean:>+8.2f}pp   "
              + " ".join(f"{x:5.1f}" for x in sc))

    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT}")
    print("\n  Negative delta = better. A feature earns its place only if it beats")
    print("  base by more than fold-to-fold noise, not just on the mean.")


if __name__ == "__main__":
    main()
