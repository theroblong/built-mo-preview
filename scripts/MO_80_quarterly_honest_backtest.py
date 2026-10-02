"""MO_80 — HONEST quarterly backtest of the ENSEMBLE router, every quarter of 2025 and 2026.

THE PROBLEM THIS FIXES
----------------------
`build_forecast_chart_data.py`'s quarterly "retrospectives" call `run_single_backtest(cutoff)`
with the ALREADY-LOADED production models, trained through 2026-06-07. So "Q1 2025, cutoff
2024-12-29" is forecast by a model that already saw 18 months of the future it is predicting.
**Six of seven quarters leak.** Only Q3 2026 is genuinely out-of-sample — the chart's own comment
admits it while the badges present all seven as backtests. That is why the numbers wander
(45.4 / 30.1 / 13.9 / 35.1 / 36.5 / 23.3 / 23.1) instead of trending.

HOW MUCH DATA EACH MODEL SEES
-----------------------------
"Use all our data" and "do not leak" are both requirements and they are compatible:

  * EVERY arm at EVERY cutoff retrains on **ALL SPINS data available at that cutoff** — every
    retailer, channel and UPC, short series included, nothing sampled or capped. The only rows
    withheld are those dated after the cutoff, because those are the answer.
  * The production model (MO_26D / MO_27D) trains on **ALL data through the panel end,
    2026-09-06**, with no holdback. That is what ships.

Training a Q1-2025 backtest on data through Sep 2026 is not "using all our data", it is marking
your own homework — the quarter numbers would improve and mean nothing.

THE ENSEMBLE ROUTER (the thing being measured)
----------------------------------------------
    lapsed (no SPINS row in 9+ weeks) -> pre-gap level x P(resume|weeks silent) x 1.06
                                         (NOT a hard zero: 365 of 878 lapses resumed at ~1.06x)
    history < ROUTER_BOUNDARY weeks   -> DIRECT     multi-horizon, needs no lag chain
    history >= ROUTER_BOUNDARY weeks  -> RECURSIVE  LightGBM AR, the incumbent

The boundary is NOT assumed. Two candidates are reported, both grounded in a real cliff:
    13 weeks  lag13 / roll13 go NaN below this (MIN_SERIES_WEEKS, the old hard gate)
    52 weeks  lag52 / YAGO is 100% null below this, and that is 51.8% of panel rows — the
              documented Q4-2025 miss mechanism. The chart already routes <52wk away from
              LightGBM (to ETS, which MO_79 showed loses to naive).

Individual arms are scored alongside so the routing choice is evidence, not preference:
    direct      all series via direct multi-horizon
    recursive   all series via the AR loop
    naive       last observed value held flat — MO_79 showed this is hard to beat
    naive_yoy   lag52 x YoY — the "Excel-level" baseline, i.e. what BUILT can already do

QUARTERS
  Q1-Q4 2025 and Q1-Q3 2026 are scoreable. Q3 2026 has partial actuals (~9 of 13 weeks, SPINS
  through 2026-09-06). Q4 2026 lies entirely beyond the panel, so it is a pure forward forecast
  with nothing to score against — MO_27D produces it; it is listed here and skipped.

FAIRNESS
  * Both learned arms get identical n_estimators and early stopping, so neither wins on budget.
    Absolute wMAPE sits slightly above production (which trains longer); the BETWEEN-ARM
    comparison is the point.
  * A series is scored only if it has >=1 actual week in the quarter, applied to all arms alike.

Run:  python MO_80_quarterly_honest_backtest.py [--account KROGER] [--trees 800]
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
                      drop_ak_hi_market_variants, lapse_resume_probability,
                      LAPSE_RESUME_LEVEL)

PARQUET  = Path("outputs/retailer_sales_weekly.parquet")
OUT_JSON = Path("outputs/mo80_quarterly_honest_backtest.json")
HORIZON        = 13
RECENCY_LAMBDA = 0.02
LAPSE_WEEKS    = 9
BOUNDARIES     = [13, 52]

QUARTERS = [
    ("Q1 2025", "2024-12-29", "2025-01-05", "2025-03-30"),
    ("Q2 2025", "2025-03-30", "2025-04-06", "2025-06-29"),
    ("Q3 2025", "2025-06-29", "2025-07-06", "2025-09-28"),
    ("Q4 2025", "2025-09-28", "2025-10-05", "2025-12-28"),
    ("Q1 2026", "2025-12-28", "2026-01-04", "2026-03-29"),
    ("Q2 2026", "2026-03-29", "2026-04-05", "2026-06-28"),
    ("Q3 2026", "2026-06-29", "2026-07-06", "2026-09-28"),
    ("Q4 2026", "2026-09-06", "2026-10-05", "2026-12-28"),   # beyond panel — forward only
]

LGBM = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)


def future_weeks(weeks, cut, n):
    """The next `n` ACTUAL panel weeks strictly after `cut`, not cut + 1..n calendar weeks."""
    nxt = weeks[weeks > cut]        # both tz-aware; np.datetime64() would strip the offset
    return list(nxt[:n])


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
    # drop_short_series is deliberately NOT applied — every series the panel rules keep is used.
    for c in CAT_COLS:
        if c in df.columns:
            df[c] = df[c].astype("category")
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


def fit(X, y, Xv, yv, trees):
    m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=trees, **LGBM)
    if len(Xv) >= 50:
        m.fit(X, y, eval_set=[(Xv, yv)], eval_metric="quantile",
              callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])
    else:
        m.fit(X, y)
    return m


def run_direct(df, feats, cut, qs, qe, anchors, trees, fweeks):
    if anchors.empty:
        return {}
    g = df.groupby(GROUP_COLS, observed=True)
    out = {}
    for h in range(1, HORIZON + 1):
        if h > len(fweeks):
            break
        fd = fweeks[h - 1]
        if not (qs <= fd <= qe):
            continue
        d = df.copy()
        d["y"] = g["base_units"].shift(-h)
        d["t_target"] = d["__time"] + pd.Timedelta(weeks=h)
        tw = d["t_target"].dt.isocalendar().week.astype(float)
        d["week_sin"] = np.sin(2 * np.pi * tw / 52); d["week_cos"] = np.cos(2 * np.pi * tw / 52)
        d["week_sin26"] = np.sin(2 * np.pi * tw / 26); d["week_cos26"] = np.cos(2 * np.pi * tw / 26)
        tr = d.dropna(subset=["y"])
        tr = tr[tr["t_target"] <= cut]        # target week must also be in the past
        if len(tr) < 500:
            continue
        va = tr.tail(max(200, len(tr) // 10))
        m = fit(tr[feats], np.log1p(tr["y"]), va[feats], np.log1p(va["y"]), trees)
        X = anchors.copy()
        t2 = float(fd.isocalendar().week)
        X["week_sin"] = np.sin(2 * np.pi * t2 / 52); X["week_cos"] = np.cos(2 * np.pi * t2 / 52)
        X["week_sin26"] = np.sin(2 * np.pi * t2 / 26); X["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
        p = np.clip(np.expm1(m.predict(X[feats])), 0, None)
        for i, (_, r) in enumerate(X.iterrows()):
            out[(tuple(r[c] for c in GROUP_COLS), fd)] = float(p[i])
    return out


def run_recursive(df, feats, cut, qs, qe, eval_keys, trees, fweeks):
    tr = df[df["__time"] <= cut]
    if len(tr) < 500:
        return {}
    va = tr.tail(max(200, len(tr) // 10))
    m = fit(tr[feats], np.log1p(tr["base_units"]), va[feats], np.log1p(va["base_units"]), trees)
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    out = {}
    for key, g in tr.groupby(GROUP_COLS, observed=True):
        if key not in eval_keys:
            continue
        g = g.sort_values("__time")
        if len(g) < 4:
            continue
        state = g.iloc[-1].copy()
        hist = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
        for h in range(1, HORIZON + 1):
            if h > len(fweeks):
                break
            fd = fweeks[h - 1]
            t2 = float(fd.isocalendar().week)
            state["week_sin"] = np.sin(2 * np.pi * t2 / 52)
            state["week_cos"] = np.cos(2 * np.pi * t2 / 52)
            state["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
            state["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
            # Defining property of the recursive loop: lag1 IS the previous prediction.
            state["base_units_lag1"] = hist[-1]
            state["base_units_roll4_avg"] = float(np.mean(hist[-4:]))
            state["base_units_roll8_avg"] = float(np.mean(hist[-8:]))
            state["base_units_roll13_avg"] = float(np.mean(hist[-13:]))
            state["base_units_wow_delta"] = hist[-1] - hist[-2] if len(hist) > 1 else 0.0
            X = pd.DataFrame([state])[feats]
            for c, cc in cats.items():
                if c in X.columns:
                    X[c] = pd.Categorical(X[c], categories=cc)
            p = float(np.clip(np.expm1(m.predict(X))[0], 0, None))
            hist.append(p)
            if qs <= fd <= qe:
                out[(key, fd)] = p
    return out


def score(truth, pred):
    keys = [k for k in truth if k in pred]
    if not keys:
        return None
    a = np.array([truth[k] for k in keys]); p = np.array([pred[k] for k in keys])
    return {"wmape": wmape(a, p),
            "bias": float(p.sum() / a.sum()) if a.sum() else float("nan"),
            "n_points": len(keys)}


def main(account, channel, trees):
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = load_panel(feats)
    end = df["__time"].max()
    # SPINS weeks land on a fixed weekday grid. Deriving forecast dates as `cutoff + N weeks`
    # breaks whenever a quarter cutoff is not ON that grid (Q3 2026's 2026-06-29 is a Monday;
    # SPINS weeks are Sundays), producing dates that match no actual and scoring nothing.
    # Always step along the panel's real week sequence instead.
    WEEKS = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    ev = (df["retail_account"] == account) & (df["channel_outlet"] == channel)
    print("MO_80 — honest quarterly backtest, ENSEMBLE router (both arms retrained every cutoff)")
    print(f"  full panel {len(df):,} rows · {df.groupby(GROUP_COLS, observed=True).ngroups:,} "
          f"series · {df['upc'].nunique()} UPCs · through {end.date()}")
    print(f"  evaluate on {account} {channel}: {int(ev.sum()):,} rows")
    print(f"  router: lapsed->0 | history < N weeks -> DIRECT | >= N -> RECURSIVE  (N in {BOUNDARIES})\n")

    hdr = ["ENSEMBLE-13", "ENSEMBLE-52", "direct", "recursive", "naive", "naiveYoY"]
    print(f"  {'quarter':<9s} {'ser':>4s} {'actual':>10s} | " +
          " ".join(f"{h:>14s}" for h in hdr))
    results = {}
    for ql, qc, q1, q2 in QUARTERS:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[ev & (df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            print(f"  {ql:<9s}  beyond panel ({end.date()}) — forward forecast only, nothing to score")
            results[ql] = {"status": "forward_only_no_actuals", "cutoff": qc}
            continue
        # Key shape MUST match what run_direct/run_recursive emit: ((upc,ch,acct,geo), date).
        # groupby(GROUP_COLS+["__time"]) yields FLAT 5-tuples, which silently match nothing and
        # make every arm score empty while the run still exits 0.
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        eval_keys = {k[0] for k in truth}
        hist_at_cut = df[ev & (df["__time"] <= cut)]
        anchors = hist_at_cut.groupby(GROUP_COLS, observed=True).tail(1)
        nweeks = hist_at_cut.groupby(GROUP_COLS, observed=True)["base_units"].size().to_dict()
        lastseen = hist_at_cut.groupby(GROUP_COLS, observed=True)["__time"].max().to_dict()
        lapsed = {k for k, t in lastseen.items() if (cut - t).days / 7 >= LAPSE_WEEKS}
        lvl4 = (hist_at_cut.groupby(GROUP_COLS, observed=True)["base_units"]
                .apply(lambda s: float(pd.to_numeric(s.tail(4), errors="coerce").mean()))
                .to_dict())

        fweeks = future_weeks(WEEKS, cut, HORIZON)
        dpred = run_direct(df, feats, cut, qs, qe, anchors, trees, fweeks)
        rpred = run_recursive(df, feats, cut, qs, qe, eval_keys, trees, fweeks)
        lastv, yoy = {}, {}
        for key, g in hist_at_cut.groupby(GROUP_COLS, observed=True):
            if key not in eval_keys:
                continue
            g = g.sort_values("__time")
            lv = float(pd.to_numeric(g["base_units"], errors="coerce").fillna(0).iloc[-1])
            s = pd.to_numeric(g.set_index("__time")["base_units"], errors="coerce")
            for h in range(1, HORIZON + 1):
                if h > len(fweeks):
                    break
                fd = fweeks[h - 1]
                if not (qs <= fd <= qe):
                    continue
                lastv[(key, fd)] = lv
                ya = s.get(fd - pd.Timedelta(weeks=52), np.nan)
                yoy[(key, fd)] = float(ya) if np.isfinite(ya) else lv

        ens = {}
        for N in BOUNDARIES:
            e = {}
            for k in truth:
                key = k[0]
                if key in lapsed:
                    # expected value, not a hard zero — see mo_panel.lapse_resume_probability
                    e[k] = lvl4.get(key, 0.0) * lapse_resume_probability(
                        (cut - lastseen[key]).days / 7) * LAPSE_RESUME_LEVEL
                elif nweeks.get(key, 0) < N:
                    if k in dpred: e[k] = dpred[k]
                elif k in rpred:
                    e[k] = rpred[k]
                elif k in dpred:
                    e[k] = dpred[k]          # recursive could not seed -> direct covers it
            ens[N] = e

        if not any(k in dpred for k in truth) and not any(k in rpred for k in truth):
            raise SystemExit(
                f"\nFATAL: no prediction key matched any truth key for {ql}.\n"
                f"  truth key sample: {next(iter(truth))!r}\n"
                f"  direct key sample: {next(iter(dpred), None)!r}\n"
                f"  This is the 5-tuple vs ((4-tuple),date) mismatch. Fix before trusting output.")
        row = {"n_series": len(eval_keys), "actual_units": float(sum(truth.values())),
               "cutoff": qc, "window": [q1, q2], "n_lapsed": len(lapsed & eval_keys),
               "n_short_13": sum(nweeks.get(k, 0) < 13 for k in eval_keys),
               "n_short_52": sum(nweeks.get(k, 0) < 52 for k in eval_keys)}
        cells = []
        for name, pred in (("ensemble_13", ens[13]), ("ensemble_52", ens[52]),
                           ("direct", dpred), ("recursive", rpred),
                           ("naive", lastv), ("naive_yoy", yoy)):
            sc = score(truth, pred)
            row[name] = sc
            cells.append(f"{sc['wmape']:>8.1f} {sc['bias']:>5.3f}" if sc else f"{'--':>14s}")
        # Chart-ready weekly aggregates. The Accuracy Proof tab must plot the SAME honest
        # predictions it badges, otherwise the lines and the numbers disagree.
        wk = {}
        for name, pred in (("ensemble_13", ens[13]), ("ensemble_52", ens[52]),
                           ("direct", dpred), ("recursive", rpred),
                           ("naive", lastv), ("naive_yoy", yoy)):
            agg = {}
            for k, v in pred.items():
                if k in truth:
                    agg[str(k[1].date())] = agg.get(str(k[1].date()), 0.0) + float(v)
            wk[name] = agg
        wk["actual"] = {}
        for k, v in truth.items():
            wk["actual"][str(k[1].date())] = wk["actual"].get(str(k[1].date()), 0.0) + float(v)
        row["weekly"] = wk
        results[ql] = row
        print(f"  {ql:<9s} {row['n_series']:>4d} {row['actual_units']:>10,.0f} | " + " ".join(cells))

    ok = [q for q in results if results[q].get("recursive")]
    if ok:
        print(f"\n  MEAN over {len(ok)} honest quarters (every one a true holdout):")
        summ = {}
        for name in ("ensemble_13", "ensemble_52", "direct", "recursive", "naive", "naive_yoy"):
            vals = [results[q][name]["wmape"] for q in ok if results[q].get(name)]
            bias = [abs(results[q][name]["bias"] - 1) for q in ok if results[q].get(name)]
            if vals:
                summ[name] = {"mean_wmape": float(np.mean(vals)),
                              "mean_abs_bias": float(np.mean(bias))}
                print(f"    {name:<13s} wMAPE {np.mean(vals):>6.1f}   |bias-1| {np.mean(bias):.3f}")
        base = summ.get("recursive", {}).get("mean_wmape")
        if base:
            print(f"\n  vs the incumbent recursive model:")
            for k, v in summ.items():
                if k != "recursive":
                    print(f"    {k:<13s} {v['mean_wmape']-base:+6.1f}pp")
        for N in BOUNDARIES:
            w = sum(1 for q in ok if results[q].get(f"ensemble_{N}")
                    and results[q][f"ensemble_{N}"]["wmape"] < results[q]["recursive"]["wmape"])
            print(f"  ensemble_{N} beats recursive in {w} of {len(ok)} quarters")
        results["_summary"] = {"quarters": len(ok), "by_method": summ,
                               "account": account, "channel": channel, "trees": trees,
                               "panel_rows": int(len(df)), "panel_end": str(end.date()),
                               "router_boundaries": BOUNDARIES, "lapse_weeks": LAPSE_WEEKS,
                               "note": ("Every quarter retrains BOTH arms on all data available "
                                        "at that cutoff. No model sees any week after its own "
                                        "cutoff.")}
    OUT_JSON.write_text(json.dumps(results, indent=2, default=float))
    print(f"\n  → {OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="KROGER")
    ap.add_argument("--channel", default="CONVENTIONAL|FOOD")
    ap.add_argument("--trees", type=int, default=800)
    a = ap.parse_args()
    main(a.account, a.channel, a.trees)
