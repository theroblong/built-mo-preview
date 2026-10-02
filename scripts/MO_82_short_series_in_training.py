"""MO_82 — Can ONE recursive LightGBM handle short-history items, if we train it on them?

THE ARCHITECTURE QUESTION
-------------------------
v11 production is not one model. It is:

    lightgbm_autoregressive   1,340 series   92.3% of forecast volume
    carry_forward_seasonal      264 series    7.7% of forecast volume
    lapsed_no_recent_sales      524 series    0.0%

The carry-forward path exists for series with fewer than 13 weeks of history. Two reasons are
usually given, and only one of them is real:

  1. "Their lags are NaN."  TRUE BUT NOT A BLOCKER. LightGBM handles missing values natively —
     it learns which side of each split NaN goes to. The direct trainer (MO_26D) already trains
     on short series without issue.
  2. "The model never learns that regime."  THIS is the real reason: `drop_short_series()` runs
     inside MO_26, so sub-13-week rows are excluded from TRAINING. The model has never seen an
     early-lifecycle series.

So the question has never actually been tested: **if we stop dropping them, can the single
recursive model take them, and can we delete the ensemble entirely?**

That matters beyond accuracy. One model means one thing to tune, one thing to serve over MCP, and
any horizon on demand — versus a router with a second code path to keep in sync.

WHAT THIS MEASURES — two questions, because one can be won while the other is lost
----------------------------------------------------------------------------------
  A. Does training on short series HELP the short series?
     Arms, all scored on series with <13 weeks of history AT THE CUTOFF:
       lgb_without_short   current production training, forced to predict them anyway
       lgb_with_short      identical, except short series stay in the training set
       carry_forward       what production ships today (flat level x seasonal index)
       naive               last observed value held flat — MO_79 showed this is hard to beat

  B. Does training on short series HURT the mature series?
     The same two trained models, scored on series with >=13 weeks. This is the real risk:
     adding noisy early-lifecycle rows could degrade the 92.3% of volume that currently works.
     A win on (A) that costs more on (B) is a net loss.

Everything else is held identical — same features, same hyperparameters, same tree budget, same
panel rules, same cutoffs. The ONLY difference between the two learned arms is whether
`drop_short_series()` is called.

Run:  python MO_82_short_series_in_training.py [--cutoffs 13,26,39,52] [--trees 1500]
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

from mo_panel import (CAT_COLS, GROUP_COLS, MIN_SERIES_WEEKS, drop_zero_volume_geographies,
                      apply_rma_priority, fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_ak_hi_market_variants, drop_short_series)

PARQUET  = Path("outputs/retailer_sales_weekly.parquet")
OUT_JSON = Path("outputs/mo82_short_series_in_training.json")
HORIZON  = 13
RECENCY_LAMBDA = 0.02
LGBM = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)


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
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


def fit(tr, feats, trees):
    va = tr.tail(max(200, len(tr) // 10))
    wk = ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0)
    sw = np.exp(-RECENCY_LAMBDA * wk)
    m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=trees, **LGBM)
    m.fit(tr[feats], np.log1p(tr["base_units"]), sample_weight=sw,
          eval_set=[(va[feats], np.log1p(va["base_units"]))], eval_metric="quantile",
          callbacks=[lgb.early_stopping(60, verbose=False), lgb.log_evaluation(-1)])
    return m


def recursive_predict(model, hist_df, feats, cats, keys, fweeks):
    """Production's AR loop: lag1 is the model's own previous prediction."""
    out = {}
    for key, g in hist_df.groupby(GROUP_COLS, observed=True):
        if key not in keys:
            continue
        g = g.sort_values("__time")
        if len(g) < 1:
            continue
        state = g.iloc[-1].copy()
        hist = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
        for fd in fweeks:
            t2 = float(fd.isocalendar().week)
            state["week_sin"] = np.sin(2 * np.pi * t2 / 52)
            state["week_cos"] = np.cos(2 * np.pi * t2 / 52)
            state["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
            state["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
            state["base_units_lag1"] = hist[-1]
            state["base_units_roll4_avg"] = float(np.mean(hist[-4:]))
            state["base_units_roll8_avg"] = float(np.mean(hist[-8:]))
            state["base_units_roll13_avg"] = float(np.mean(hist[-13:]))
            state["base_units_wow_delta"] = hist[-1] - hist[-2] if len(hist) > 1 else 0.0
            X = pd.DataFrame([state])[feats]
            for c, cc in cats.items():
                if c in X.columns:
                    X[c] = pd.Categorical(X[c], categories=cc)
            p = float(np.clip(np.expm1(model.predict(X))[0], 0, None))
            hist.append(p)
            out[(key, fd)] = p
    return out


def main(cutoffs_back, trees):
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v11_full.pkl", "rb")).feature_name_)
    df = load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    end = df["__time"].max()
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    print("MO_82 — can ONE recursive LightGBM take the short-history items?")
    print(f"  panel {len(df):,} rows · {df.groupby(GROUP_COLS, observed=True).ngroups:,} series")
    print(f"  the ONLY difference between the learned arms is drop_short_series()\n")

    results = {}
    for wback in cutoffs_back:
        cut = end - pd.Timedelta(weeks=wback)
        fweeks = list(weeks[weeks > cut][:HORIZON])
        if not fweeks:
            continue
        hist = df[df["__time"] <= cut]
        fut = df[(df["__time"] > cut) & (df["__time"] <= fweeks[-1])]
        if hist.empty or fut.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 fut.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        nwk = hist.groupby(GROUP_COLS, observed=True)["base_units"].size().to_dict()
        eval_keys = {k[0] for k in truth}
        short = {k for k in eval_keys if nwk.get(k, 0) < MIN_SERIES_WEEKS}
        mature = eval_keys - short
        print(f"  cutoff {cut.date()}  |  {len(short)} short series, {len(mature)} mature")
        if not short:
            continue

        tr_all = hist.copy()
        tr_drop = drop_short_series(hist.copy(), verbose=False)
        m_with = fit(tr_all, feats, trees)
        m_without = fit(tr_drop, feats, trees)
        print(f"      trained WITH short: {len(tr_all):,} rows | WITHOUT: {len(tr_drop):,} rows")

        p_with = recursive_predict(m_with, hist, feats, cats, eval_keys, fweeks)
        p_without = recursive_predict(m_without, hist, feats, cats, eval_keys, fweeks)

        # carry-forward + naive, exactly as production builds them for short series
        cf, nv = {}, {}
        for key, g in hist.groupby(GROUP_COLS, observed=True):
            if key not in eval_keys:
                continue
            g = g.sort_values("__time")
            u = pd.to_numeric(g["base_units"], errors="coerce").fillna(0)
            lv4, lv1 = float(u.tail(4).mean()), float(u.iloc[-1])
            for fd in fweeks:
                cf[(key, fd)] = lv4
                nv[(key, fd)] = lv1

        row = {"cutoff": str(cut.date()), "n_short": len(short), "n_mature": len(mature)}
        for band, keys in (("short", short), ("mature", mature)):
            sub = {k: v for k, v in truth.items() if k[0] in keys}
            if not sub:
                continue
            row[band] = {}
            for name, pred in (("lgb_with_short", p_with), ("lgb_without_short", p_without),
                               ("carry_forward", cf), ("naive", nv)):
                ks = [k for k in sub if k in pred]
                if not ks:
                    continue
                a = np.array([sub[k] for k in ks]); p = np.array([pred[k] for k in ks])
                row[band][name] = {"wmape": wmape(a, p),
                                   "bias": float(p.sum() / a.sum()) if a.sum() else float("nan"),
                                   "units": float(a.sum())}
            b = row[band]
            print(f"      {band.upper():<7s} " + "  ".join(
                f"{n.replace('lgb_','')}={b[n]['wmape']:.1f}" for n in
                ("lgb_with_short", "lgb_without_short", "carry_forward", "naive") if n in b))
        results[str(cut.date())] = row

    print(f"\n{'='*86}")
    print("  A. DOES TRAINING ON SHORT SERIES HELP THE SHORT SERIES?  (pooled, unit-weighted)")
    print("  B. DOES IT HURT THE MATURE SERIES?  (the 92.3% of volume that already works)")
    summary = {}
    for band in ("short", "mature"):
        print(f"\n  {band.upper()} series")
        print(f"    {'arm':<20s} {'wMAPE':>8s} {'|bias-1|':>10s}")
        summary[band] = {}
        for name in ("lgb_with_short", "lgb_without_short", "carry_forward", "naive"):
            ws, bs, us = [], [], []
            for r in results.values():
                if band in r and name in r[band]:
                    ws.append(r[band][name]["wmape"] * r[band][name]["units"])
                    bs.append(abs(r[band][name]["bias"] - 1))
                    us.append(r[band][name]["units"])
            if us:
                w = float(sum(ws) / sum(us))
                summary[band][name] = {"wmape": w, "mean_abs_bias": float(np.mean(bs))}
                print(f"    {name:<20s} {w:>8.1f} {np.mean(bs):>10.3f}")
    s, mt = summary.get("short", {}), summary.get("mature", {})
    if "lgb_with_short" in s and "carry_forward" in s:
        d_short = s["lgb_with_short"]["wmape"] - s["carry_forward"]["wmape"]
        print(f"\n  VERDICT A: training on short series makes LightGBM "
              f"{abs(d_short):.1f}pp {'BETTER' if d_short < 0 else 'WORSE'} than carry-forward "
              f"on short series")
    if "lgb_with_short" in mt and "lgb_without_short" in mt:
        d_mat = mt["lgb_with_short"]["wmape"] - mt["lgb_without_short"]["wmape"]
        print(f"  VERDICT B: including them changes mature-series error by {d_mat:+.1f}pp "
              f"({'HURTS' if d_mat > 0 else 'helps'} the 92.3% of volume)")
        print(f"\n  -> Collapse to ONE model only if A is better AND B does not get worse.")
    out = {"results": results, "summary": summary, "trees": trees,
           "cutoffs_weeks_back": cutoffs_back,
           "note": ("Only difference between learned arms is drop_short_series(). Same features, "
                    "hyperparameters, tree budget, panel rules and cutoffs.")}
    OUT_JSON.write_text(json.dumps(out, indent=2, default=float))
    print(f"\n  → {OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoffs", type=str, default="13,26,39,52")
    ap.add_argument("--trees", type=int, default=1500)
    a = ap.parse_args()
    main([int(x) for x in a.cutoffs.split(",")], a.trees)
