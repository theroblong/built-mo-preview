#!/usr/bin/env python
"""MO_98 - bounded extrapolation: make linear_tree usable.

MO_97 established both halves of the problem:
  - linear_tree DOES remove the extrapolation ceiling (controlled probe: max
    prediction 81.02 against a training max of 61.72, where constant leaves were
    stuck at 59.39 -- an exact replication of the README 204 number)
  - unbounded, it is catastrophic: in-sample raw log predictions reached 26.9,
    i.e. 498 BILLION units for a brand selling ~4M/month, which propagates to NaN
    through the recursive loop
  - regularizing helps but does not fix it: at linear_lambda=10 it scored 32.49
    against constant leaves' 32.97 on the SAME fold -- the first mechanism-driven
    win all week -- but some fold returns NaN at every lambda tried

The missing piece is a guardrail. Extrapolation should be ALLOWED but BOUNDED:
each step is capped at a multiple of what that series has actually ever done.
That keeps the growth headroom linear_tree exists to provide while removing the
runaway feedback that makes the recursive loop diverge.

Efficiency note: the cap is applied at INFERENCE, so one fit per (lambda, fold)
is scored at every cap level rather than refitting per cap.

Honest-comparison notes:
  - the constant-leaf baseline is scored under the SAME caps, so the cap itself
    cannot be what wins
  - every arm uses identical features, folds, tree budget and early stopping
  - a NaN is reported as NaN, never silently dropped from a mean
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

OUT = Path("outputs/mo98_linear_tree_guardrail.json")
TREES = 1200
CUTOFFS_BACK = (13, 26, 39, 52)
LAMBDAS = (1.0, 10.0, 100.0)
CAPS = (1.5, 2.0, 3.0, 5.0, float("inf"))
BASE = dict(num_leaves=63, min_child_samples=20, learning_rate=0.05,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1,
            alpha=0.5)


def recursive_wmape_capped(model, df, feats, cats, cut, weeks, caps):
    """R.recursive_wmape_fast, but each step is capped at cap x the series' own max.

    Returns {cap: wmape}. One forward pass per cap, sharing the fitted model.
    """
    fw = list(weeks[weeks > cut][:R.HORIZON])
    if not fw:
        return {c: float("nan") for c in caps}
    hist_df = df[df["__time"] <= cut]
    fut = df[(df["__time"] > cut) & (df["__time"] <= fw[-1])]
    truth = fut.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum()
    if truth.empty:
        return {c: float("nan") for c in caps}
    want = {(u, c, a, g) for (u, c, a, g, _t) in truth.index}
    tmap = {((u, c, a, g), t): v for (u, c, a, g, t), v in truth.items()}

    keys, states, hist0, smax = [], [], [], []
    for key, g in hist_df.groupby(GROUP_COLS, observed=True):
        if key not in want:
            continue
        g = g.sort_values("__time")
        if len(g) < 4:
            continue
        h = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
        keys.append(key); states.append(g.iloc[-1]); hist0.append(h)
        smax.append(max(h) if h else 0.0)
    if not keys:
        return {c: float("nan") for c in caps}
    smax = np.array(smax, dtype=float)

    out = {}
    for cap in caps:
        S = pd.DataFrame(states).reset_index(drop=True)
        hists = [list(h) for h in hist0]
        ceiling = smax * cap if np.isfinite(cap) else None
        acts, preds = [], []
        for fd in fw:
            t2 = float(fd.isocalendar().week)
            S["week_sin"] = np.sin(2 * np.pi * t2 / 52)
            S["week_cos"] = np.cos(2 * np.pi * t2 / 52)
            S["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
            S["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
            S["base_units_lag1"] = [h[-1] for h in hists]
            S["base_units_roll4_avg"] = [float(np.mean(h[-4:])) for h in hists]
            S["base_units_roll8_avg"] = [float(np.mean(h[-8:])) for h in hists]
            S["base_units_roll13_avg"] = [float(np.mean(h[-13:])) for h in hists]
            S["base_units_wow_delta"] = [h[-1] - h[-2] if len(h) > 1 else 0.0 for h in hists]
            X = S[feats].copy()
            for c, cc in cats.items():
                if c in X.columns:
                    X[c] = pd.Categorical(X[c], categories=cc)
            raw = model.predict(X)
            p = np.clip(np.expm1(np.clip(raw, -50, 50)), 0, None)   # -50/50 stops inf
            if ceiling is not None:
                p = np.minimum(p, ceiling)
            for i, key in enumerate(keys):
                hists[i].append(float(p[i]))
                k = (key, fd)
                if k in tmap:
                    acts.append(tmap[k]); preds.append(float(p[i]))
        out[cap] = R.wmape(acts, preds) if acts else float("nan")
    return out


def main() -> None:
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = R.load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    end = df["__time"].max()
    cuts = [end - pd.Timedelta(weeks=w) for w in CUTOFFS_BACK]

    print("MO_98 - bounded extrapolation for linear_tree")
    print(f"  {len(df):,} rows - folds {[str(c.date()) for c in cuts]} - {TREES} trees")
    print(f"  caps = multiples of each series' own historical max; inf = no cap\n")

    def run(label, extra):
        per_cap = {c: [] for c in CAPS}
        for cut in cuts:
            tr = df[df["__time"] <= cut]
            va = tr[tr["__time"] > cut - pd.Timedelta(weeks=R.HORIZON)]
            p = dict(BASE); p.update(extra)
            m = lgb.LGBMRegressor(objective="quantile", n_estimators=TREES, **p)
            m.fit(tr[feats], np.log1p(tr["base_units"]),
                  eval_set=[(va[feats], np.log1p(va["base_units"]))],
                  callbacks=[lgb.early_stopping(80, verbose=False),
                             lgb.log_evaluation(-1)])
            sc = recursive_wmape_capped(m, df, feats, cats, cut, weeks, CAPS)
            for c in CAPS:
                per_cap[c].append(sc[c])
        row = {}
        cells = []
        for c in CAPS:
            v = per_cap[c]
            mu = float(np.mean(v)) if all(np.isfinite(x) for x in v) else float("nan")
            row[str(c)] = {"folds": v, "mean": mu}
            cells.append(f"{mu:>7.2f}" if np.isfinite(mu) else f"{'nan':>7s}")
        print(f"  {label:<34s} " + " ".join(cells))
        return row

    hdr = " ".join(f"{('cap '+str(c)) if np.isfinite(c) else 'no cap':>7s}" for c in CAPS)
    print(f"  {'arm':<34s} {hdr}")
    results = {}
    results["constant leaves (production)"] = run("constant leaves (production)", {})
    for lam in LAMBDAS:
        results[f"linear_tree lambda={lam:g}"] = run(
            f"linear_tree lambda={lam:g}", dict(linear_tree=True, linear_lambda=lam))

    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT}")
    base = results["constant leaves (production)"]
    bb = min((v["mean"] for v in base.values() if np.isfinite(v["mean"])), default=float("nan"))
    print(f"\n  best constant-leaf cell: {bb:.2f}")
    best, where = float("inf"), None
    for k, row in results.items():
        if k.startswith("constant"):
            continue
        for c, v in row.items():
            if np.isfinite(v["mean"]) and v["mean"] < best:
                best, where = v["mean"], f"{k}, cap {c}"
    if where:
        print(f"  best linear_tree cell : {best:.2f}  ({where})  -> {best-bb:+.2f}pp vs constant")
    print("\n  A cell only counts if ALL FOUR folds are finite. NaN means the loop")
    print("  still diverged somewhere and the setting is not usable.")


if __name__ == "__main__":
    main()
