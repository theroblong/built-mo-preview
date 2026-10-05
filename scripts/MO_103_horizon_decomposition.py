#!/usr/bin/env python
"""MO_103 - error BY HORIZON: recursive vs direct vs flat, and the hybrid crossover.

This is the experiment the whole week has been pointing at. Everything measured so
far says the inputs are not the problem and the recursive application is: the model
scores 4.15% teacher-forced and 37% recursive, and flat carry-forward beats it with
IDENTICAL bias (1.066 vs 1.065) — same bias, more variance, which is what error
compounding looks like.

Mean wMAPE hides the mechanism. If compounding is the defect, error must grow with
horizon for the recursive arm and NOT for flat or direct. That is a falsifiable
prediction, and this measures it.

Arms, all on identical folds, features and tree budget:
  recursive  the production loop, each step fed its own previous prediction
  direct     a separate model per horizon h, predicted from anchor features, NO lag
             chain — so nothing compounds and nothing goes stale mid-forecast
  flat       carry the last observed value forward — the thing to beat

Then the HYBRID: use whichever arm is better up to step k and flat beyond it.
**k is chosen leave-one-fold-out** — selected on the other three folds and applied
to the held-out one — because picking k on the same folds it is scored against
would be fitting the crossover to the answer.

Seasonal factor is OFF for every arm: MO_102's sweep showed zero seasonal is
optimal (40.46 against 41.19 at the mildest non-zero setting), so leaving it on
would handicap the recursive arm rather than test it.
"""
from __future__ import annotations

import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import MO_80_quarterly_honest_backtest as M
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo103_horizon_decomposition.json")
TREES = 800
CUTOFFS_BACK = (13, 26, 39, 52)
H = 13


def flat_pred(df, cut, fw, eval_keys):
    out = {}
    for key, g in df[df["__time"] <= cut].groupby(GROUP_COLS, observed=True):
        if key not in eval_keys:
            continue
        v = pd.to_numeric(g.sort_values("__time")["base_units"], errors="coerce").fillna(0)
        if not len(v):
            continue
        last = float(v.iloc[-1])
        for fd in fw:
            out[(key, fd)] = last
    return out


def by_horizon(truth, pred, fw):
    """wMAPE and bias at each horizon step."""
    rows = {}
    for h, fd in enumerate(fw, start=1):
        a = [v for (k, t), v in truth.items() if t == fd and (k, t) in pred]
        p = [pred[(k, t)] for (k, t), v in truth.items() if t == fd and (k, t) in pred]
        if not a:
            rows[h] = (float("nan"), float("nan"), 0)
            continue
        a_, p_ = np.array(a), np.array(p)
        rows[h] = (float(np.abs(a_ - p_).sum() / np.abs(a_).sum() * 100),
                   float(p_.sum() / a_.sum()), len(a_))
    return rows


def main() -> None:
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    end = df["__time"].max()
    cuts = [end - pd.Timedelta(weeks=w) for w in CUTOFFS_BACK]

    print("MO_103 - error by horizon: does the recursive arm DEGRADE with h?")
    print(f"  {len(df):,} rows - folds {[str(c.date()) for c in cuts]} - {TREES} trees")
    print("  seasonal factor OFF for all arms (MO_102: zero is optimal)\n")

    per_fold = []
    for cut in cuts:
        fw = M.future_weeks(weeks, cut, H)
        qs, qe = fw[0], fw[-1]
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        anchors = df[df["__time"] <= cut].groupby(GROUP_COLS, observed=True).tail(1)
        anchors = anchors[anchors.apply(
            lambda r: tuple(r[c] for c in GROUP_COLS) in ek, axis=1)]

        rec = M.run_production(df, feats, cut, qs, qe, ek, TREES, fw, {})
        rec = {k: (v["q50"] if isinstance(v, dict) else v) for k, v in rec.items()}
        dir_ = M.run_direct(df, feats, cut, qs, qe, anchors, TREES, fw)
        fla = flat_pred(df, cut, fw, ek)

        per_fold.append({"cut": str(cut.date()), "fw": [str(x.date()) for x in fw],
                         "recursive": by_horizon(truth, rec, fw),
                         "direct": by_horizon(truth, dir_, fw),
                         "flat": by_horizon(truth, fla, fw)})
        print(f"  fold {str(cut.date())} done "
              f"(rec {len(rec):,} / dir {len(dir_):,} / flat {len(fla):,} preds)")

    # ---- by-horizon table, averaged over folds ----
    print(f"\n  {'h':>3s} " + " ".join(f"{a:>17s}" for a in ("recursive", "direct", "flat")))
    curve = {}
    for h in range(1, H + 1):
        cells, curve[h] = [], {}
        for arm in ("recursive", "direct", "flat"):
            w = np.nanmean([f[arm][h][0] for f in per_fold if h in f[arm]])
            b = np.nanmean([f[arm][h][1] for f in per_fold if h in f[arm]])
            curve[h][arm] = {"wmape": float(w), "bias": float(b)}
            cells.append(f"{w:>9.1f} {b:>7.3f}")
        print(f"  {h:>3d} " + " ".join(cells))

    print("\n  Degradation from h=1 to h=13:")
    for arm in ("recursive", "direct", "flat"):
        a, z = curve[1][arm]["wmape"], curve[H][arm]["wmape"]
        print(f"    {arm:<10s} {a:5.1f} -> {z:5.1f}   ({z-a:+.1f}pp, {z/a:.2f}x)")

    # ---- hybrid with leave-one-fold-out crossover ----
    print("\n  HYBRID: model up to step k, flat beyond. k chosen leave-one-fold-out.")
    hyb, ks = [], []
    for i, fold in enumerate(per_fold):
        others = [f for j, f in enumerate(per_fold) if j != i]
        best_k, best_err = 0, float("inf")
        for k in range(0, H + 1):
            errs = []
            for f in others:
                a_tot = p_tot = 0.0
                for h in range(1, H + 1):
                    arm = "direct" if h <= k else "flat"
                    w, _, n = f[arm][h]
                    if n:
                        a_tot += n; p_tot += w * n
                errs.append(p_tot / a_tot if a_tot else np.nan)
            e = np.nanmean(errs)
            if e < best_err:
                best_err, best_k = e, k
        a_tot = p_tot = 0.0
        for h in range(1, H + 1):
            arm = "direct" if h <= best_k else "flat"
            w, _, n = fold[arm][h]
            if n:
                a_tot += n; p_tot += w * n
        hyb.append(p_tot / a_tot if a_tot else np.nan); ks.append(best_k)
        print(f"    fold {fold['cut']}: k={best_k:<2d} -> {hyb[-1]:.2f}")

    print(f"\n  {'arm':<12s} {'mean wMAPE':>11s}")
    overall = {}
    for arm in ("recursive", "direct", "flat"):
        v = np.nanmean([np.nanmean([f[arm][h][0] for h in range(1, H + 1)]) for f in per_fold])
        overall[arm] = float(v)
        print(f"  {arm:<12s} {v:>11.2f}")
    overall["hybrid"] = float(np.nanmean(hyb))
    print(f"  {'hybrid':<12s} {np.nanmean(hyb):>11.2f}   (k per fold: {ks})")

    OUT.write_text(json.dumps({"curve": curve, "overall": overall,
                               "hybrid_k": ks, "folds": per_fold}, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
