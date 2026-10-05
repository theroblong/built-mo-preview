#!/usr/bin/env python
"""MO_102 - shrinkage sweep with NO arbitrary floor, and the "bells and whistles" test.

Jason, 2026-10-05: "sweep the shrinkage. don't impose arbitrary limits that
adversely affect results... Perhaps we have too many bells and whistles and need
to simplify with what we've learned to get a comparative baseline? ... it's
embarrassing to have a ML model that gets beat out by just carrying forward the
most recent week's value."

PART A - SHRINKAGE SWEEP, unconstrained.
MO_100 shrank each month toward 1.0 with SHRINK_K=1.5, giving amplitude 0.296
against the live mo59 curve's 0.424. In the A/B the arm that most helped Q1 bias
was the one that swung HARDEST, so the shrinkage may have been throwing away the
part that works. K is swept from 0 (raw, no shrinkage at all) upward. No floor is
imposed on amplitude.

PART B - FEATURE SIMPLIFICATION.
Measured fact: only 10 of 56 features UPDATE during the 13-step recursive
forecast. The other 46 are frozen at their anchor-row value for the whole
horizon. The model learned to use them as dynamic signals and then reads them as
constants. That is a concrete reason a simpler model might beat a richer one in
the recursive setting specifically -- and a concrete reason flat carry-forward,
which has nothing to go stale, is hard to beat.

Arms, each a strict subset so the comparison is about COUNT not cherry-picking:
  full_56     everything production uses today
  dynamic_10  ONLY the features that actually update each step
  dynamic+id  the 10 dynamic ones plus the stable identifiers (account, flavor)
  lag_only    the autoregressive core alone
  flat        carry the last observed value forward -- the thing to beat

Everything is scored on the RECURSIVE objective, which is the job production
actually does, with wMAPE and bias, portfolio-wide.
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
import MO_80_quarterly_honest_backtest as M
import MO_100_monthly_seasonal_index as S
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo102_shrinkage_and_simplification.json")
TREES = 1200
CUTOFFS_BACK = (13, 26, 39, 52)
SHRINK_KS = (0.0, 0.25, 0.75, 1.5, 3.0)
BASE = dict(num_leaves=63, min_child_samples=20, learning_rate=0.05,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1,
            alpha=0.5)

DYNAMIC = ["base_units_lag1", "base_units_roll4_avg", "base_units_roll8_avg",
           "base_units_roll13_avg", "base_units_wow_delta", "base_units_lag52",
           "week_sin", "week_cos", "week_sin26", "week_cos26"]
IDENTIFIERS = ["retail_account", "spins_flavor_canonical", "channel_outlet"]
LAG_ONLY = ["base_units_lag1", "base_units_roll4_avg", "base_units_roll8_avg",
            "base_units_roll13_avg", "base_units_wow_delta"]


def index_at(raw, cutoff, k):
    old = S.SHRINK_K
    S.SHRINK_K = k
    try:
        idx, _ = S.monthly_index(raw, cutoff=cutoff, verbose=False)
    finally:
        S.SHRINK_K = old
    if idx is None:
        return {}, 0.0
    wk = S.to_weekly(idx)
    amp = float(wk.seasonal_index.max() - wk.seasonal_index.min())
    return {int(a): b - 1.0 for a, b in zip(wk.week_of_year, wk.seasonal_index)}, amp


def score(truth, pred):
    keys = [k for k in truth if k in pred]
    if not keys:
        return float("nan"), float("nan")
    a = np.array([truth[k] for k in keys]); p = np.array([pred[k] for k in keys])
    return (float(np.abs(a - p).sum() / np.abs(a).sum() * 100), float(p.sum() / a.sum()))


def flat_pred(df, cut, qs, qe, eval_keys, fw):
    out = {}
    hist = df[df["__time"] <= cut]
    for key, g in hist.groupby(GROUP_COLS, observed=True):
        if key not in eval_keys:
            continue
        v = pd.to_numeric(g.sort_values("__time")["base_units"], errors="coerce").fillna(0)
        if not len(v):
            continue
        last = float(v.iloc[-1])
        for fd in fw:
            if qs <= fd <= qe:
                out[(key, fd)] = last
    return out


def main() -> None:
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    raw = S.load_panel()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]

    print("MO_102 - PART A: shrinkage sweep, no floor imposed\n")
    print(f"  {'K':>6s} {'amplitude':>10s}   (mo59 reference amplitude 0.424)")
    for k in SHRINK_KS:
        _, amp = index_at(raw, None, k)
        print(f"  {k:>6.2f} {amp:>10.3f}")

    results = {"shrinkage": {}, "features": {}}
    print(f"\n  {'quarter':<9s} " + " ".join(f"{'K='+format(k,'g'):>14s}" for k in SHRINK_KS)
          + f" {'none':>14s}")
    acc = {k: [] for k in SHRINK_KS}; acc["none"] = []
    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC"); qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        cells = []
        for k in list(SHRINK_KS) + ["none"]:
            seas = {} if k == "none" else index_at(raw, cut, k)[0]
            p = M.run_production(df, feats, cut, qs, qe, ek, TREES, fw, seas)
            p = {a: (b["q50"] if isinstance(b, dict) else b) for a, b in p.items()}
            w, b = score(truth, p)
            acc[k].append((w, b)); cells.append(f"{w:>7.1f} {b:>6.3f}")
        print(f"  {ql:<9s} " + " ".join(cells))
    print(f"\n  {'arm':<8s} {'wMAPE':>8s} {'bias':>7s}")
    for k in list(SHRINK_KS) + ["none"]:
        v = acc[k]; lbl = "none" if k == "none" else f"K={k:g}"
        w = np.nanmean([x[0] for x in v]); b = np.nanmean([x[1] for x in v])
        results["shrinkage"][lbl] = {"wmape": w, "bias": b}
        print(f"  {lbl:<8s} {w:>8.2f} {b:>7.3f}")

    # ---------------- PART B ----------------
    print("\n\nMO_102 - PART B: does SIMPLIFYING beat the full feature set?\n")
    sets = {
        "full_56": feats,
        "dynamic_10": [f for f in DYNAMIC if f in feats],
        "dynamic+id": [f for f in DYNAMIC + IDENTIFIERS if f in feats],
        "lag_only": [f for f in LAG_ONLY if f in feats],
    }
    for n, s in sets.items():
        print(f"  {n:<12s} {len(s)} features")
    end = df["__time"].max()
    cuts = [end - pd.Timedelta(weeks=w) for w in CUTOFFS_BACK]
    print(f"\n  {'arm':<12s} {'wMAPE':>8s} {'bias':>7s}   per-fold wMAPE")
    for name, fs in list(sets.items()) + [("flat", None)]:
        rows = []
        for cut in cuts:
            fw = M.future_weeks(weeks, cut, M.HORIZON)
            qs, qe = fw[0], fw[-1]
            act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
            truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                     act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
            ek = {k[0] for k in truth}
            if fs is None:
                p = flat_pred(df, cut, qs, qe, ek, fw)
            else:
                # run_production fits internally on exactly `fs`, so every arm gets
                # the same training and inference path and differs ONLY in features.
                raw_p = M.run_production(df, fs, cut, qs, qe, ek, TREES, fw, {})
                p = {a: (b["q50"] if isinstance(b, dict) else b) for a, b in raw_p.items()}
            w, b = score(truth, p)
            rows.append((w, b))
        w = np.nanmean([x[0] for x in rows]); b = np.nanmean([x[1] for x in rows])
        results["features"][name] = {"wmape": w, "bias": b,
                                     "folds": [list(x) for x in rows]}
        print(f"  {name:<12s} {w:>8.2f} {b:>7.3f}   "
              + " ".join(f"{x[0]:5.1f}" for x in rows))

    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
