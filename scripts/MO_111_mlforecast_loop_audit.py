#!/usr/bin/env python
"""MO_111 - audit our hand-rolled recursive loop against an independent implementation.

THE ARGUMENT FOR DOING THIS AT ALL IS NOT ACCURACY
--------------------------------------------------
Nixtla's MLForecast was suggested as a scaling tool. We do not have a scaling problem
-- 96,369 rows, 122 UPCs. What we DO have is a correctness problem with a track
record:

  MO_109  the seasonal index was applied against the year's mean instead of the
          anchor week, in the recursive loop. Cost ~3pp. Shipped for months.
  MO_113  the SAME bug existed in a second place in the same loop -- the short/lapsed
          router -- and the first fix missed it.
  v9      four divergent copies of CAT_COLS silently killed flavor and brand at
          inference.
  MO_92   the white paper's numbers scored a strawman because a helper imported
          `run_recursive` instead of the production path.

Every one of those is the same species of defect: a recursion we wrote by hand, in
more than one file, that has to stay in lockstep with itself. MO_27 and MO_80 must
NOW be patched identically or the chart's retrospective and forward lines diverge.
That is a standing hazard, and the honest way to decide whether to hand the recursion
to a library is to find out whether the library and our loop AGREE.

WHAT THIS MEASURES
  parity      do the two implementations produce the same wMAPE on the same features?
              A gap means one of them is wrong, and it is worth finding out which.
  cost        is MLForecast's recursion slower or faster than ours?

DESIGN - parity is the whole point, so everything is held identical:
  * same restricted feature set in both arms: lags 1/2/3/52, rolling means of lag1
    over 4/8/13 weeks, and week-of-year sin/cos
  * same LightGBM hyperparameters, same seed, same n_estimators, no early stopping
    (early stopping on a tail split is not reproducible across the two data layouts)
  * NO log1p in either arm. Production logs the target; dropping it in both keeps
    parity, which is what is being tested here. This is therefore NOT a production
    accuracy number and must not be quoted as one.
  * same honest cutoffs, same eval cohort, same scoring function

A material gap in EITHER direction is the finding. If MLForecast wins, our loop has a
bug. If ours wins, the library is doing something different from what we assume and
should not be adopted blindly.
"""
from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

warnings.filterwarnings("ignore")

from mlforecast import MLForecast
from mlforecast.lag_transforms import RollingMean

import MO_80_quarterly_honest_backtest as M
from mo_panel import GROUP_COLS

OUT = Path("outputs/mo111_mlforecast_audit.json")
LAGS = [1, 2, 3, 52]
ROLLS = [4, 8, 13]
TREES = 400
FREQ = "W-SUN"          # SPINS weeks land on Sunday; asserted below rather than assumed
PARAMS = dict(n_estimators=TREES, learning_rate=0.05, num_leaves=63,
              min_child_samples=20, feature_fraction=0.8, bagging_fraction=0.8,
              bagging_freq=5, reg_alpha=0.1, reg_lambda=0.2,
              random_state=42, n_jobs=-1, verbose=-1)


# date_features must be named callables -- MLForecast uses __name__ as the column name,
# so a lambda would collide.
def week_sin(dates):
    return np.sin(2 * np.pi * pd.DatetimeIndex(dates).isocalendar().week.values / 52)


def week_cos(dates):
    return np.cos(2 * np.pi * pd.DatetimeIndex(dates).isocalendar().week.values / 52)


def long_frame(df):
    """Panel -> Nixtla long format. unique_id is the 4-part series key, joined."""
    d = df[GROUP_COLS + ["__time", "base_units"]].copy()
    d["unique_id"] = d[GROUP_COLS].astype(str).agg("␟".join, axis=1)
    d["ds"] = d["__time"].dt.tz_localize(None)
    d["y"] = pd.to_numeric(d["base_units"], errors="coerce").fillna(0.0)
    return d[["unique_id", "ds", "y"]].sort_values(["unique_id", "ds"])


def build_features(d):
    """Our OWN construction of the restricted feature set, for training rows."""
    g = d.groupby("unique_id", sort=False)["y"]
    out = d.copy()
    for L in LAGS:
        out[f"lag{L}"] = g.shift(L)
    s1 = g.shift(1)
    for w in ROLLS:
        out[f"roll{w}"] = s1.groupby(d["unique_id"], sort=False).transform(
            lambda x, w=w: x.rolling(w, min_periods=1).mean())
    iso = out["ds"].dt.isocalendar()
    out["week_sin"] = np.sin(2 * np.pi * iso.week.values / 52)
    out["week_cos"] = np.cos(2 * np.pi * iso.week.values / 52)
    return out


FEATS = [f"lag{L}" for L in LAGS] + [f"roll{w}" for w in ROLLS] + ["week_sin", "week_cos"]


def ours(tr, horizon, fweeks, eval_ids):
    """Our loop: predict one step, append it to history, recompute lags, repeat."""
    m = lgb.LGBMRegressor(**PARAMS)
    f = build_features(tr)
    # lag52 is NaN for the first year of every series. Dropping those rows would train on
    # a different population than MLForecast does (it drops them too), so this is parity,
    # not convenience.
    f = f.dropna(subset=[c for c in FEATS if c.startswith("lag")])
    m.fit(f[FEATS], f["y"])

    hist = {k: list(v) for k, v in tr.groupby("unique_id", sort=False)["y"]}
    out = {}
    for uid in eval_ids:
        h = list(hist.get(uid, []))
        if len(h) < max(LAGS) + 1:
            continue
        for fd in fweeks[:horizon]:
            row = {}
            for L in LAGS:
                row[f"lag{L}"] = h[-L]
            for w in ROLLS:
                row[f"roll{w}"] = float(np.mean(h[-w:]))
            wk = int(pd.Timestamp(fd).isocalendar().week)
            row["week_sin"] = np.sin(2 * np.pi * wk / 52)
            row["week_cos"] = np.cos(2 * np.pi * wk / 52)
            p = float(np.clip(m.predict(pd.DataFrame([row])[FEATS])[0], 0, None))
            h.append(p)
            out[(uid, fd)] = p
    return out


def theirs(tr, horizon, eval_ids):
    """MLForecast's loop, same features, same model, same data."""
    f = MLForecast(
        models=[lgb.LGBMRegressor(**PARAMS)],
        freq=FREQ,
        lags=LAGS,
        lag_transforms={1: [RollingMean(window_size=w) for w in ROLLS]},
        date_features=[week_sin, week_cos],
    )
    f.fit(tr, id_col="unique_id", time_col="ds", target_col="y",
          static_features=[])          # no statics: parity with `ours`
    p = f.predict(h=horizon)
    col = [c for c in p.columns if c not in ("unique_id", "ds")][0]
    p = p[p["unique_id"].isin(eval_ids)]
    return {(r.unique_id, pd.Timestamp(r.ds, tz="UTC")): max(0.0, float(getattr(r, col)))
            for r in p.itertuples()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default=None, help="restrict EVAL to one account")
    ap.add_argument("--channel", default="CONVENTIONAL|FOOD")
    a = ap.parse_args()

    import pickle
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)

    wd = sorted(set(pd.to_datetime(pd.unique(df["__time"])).dayofweek))
    assert wd == [6], f"panel weeks are not all Sunday ({wd}); FREQ={FREQ} would be wrong"

    d = long_frame(df)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]

    scope = "PORTFOLIO-WIDE" if not a.account else f"{a.account} {a.channel}"
    print(f"MO_111 - our recursive loop vs MLForecast, identical features · {scope}")
    print(f"  features: {', '.join(FEATS)}")
    print(f"  {len(d['unique_id'].unique()):,} series · {len(d):,} rows · freq {FREQ}")
    print("  NOTE no log1p in either arm -- this is a PARITY test, not a production number\n")
    print(f"  {'quarter':<9s} {'ours':>16s} {'mlforecast':>16s} {'gap':>8s} "
          f"{'t_ours':>8s} {'t_mlf':>8s}")

    rows, acc = {}, {"ours": [], "mlf": []}
    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        ev = df["channel_outlet"] == a.channel
        if a.account:
            ev &= df["retail_account"] == a.account
        act = df[ev & (df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {}
        for k, v in act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items():
            uid = "␟".join(str(x) for x in k[:-1])
            truth[(uid, k[-1])] = float(v)
        eval_ids = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        tr = d[d["ds"] <= pd.Timestamp(qc)]

        t0 = time.time(); po = ours(tr, M.HORIZON, fw, eval_ids); t_o = time.time() - t0
        t0 = time.time(); pt = theirs(tr, M.HORIZON, eval_ids); t_t = time.time() - t0

        # Score on the intersection only. Scoring each arm on its own key set would let a
        # difference in COVERAGE masquerade as a difference in accuracy.
        common = [k for k in truth if k in po and k in pt]
        if not common:
            print(f"  {ql:<9s} no overlapping keys")
            continue
        A = np.array([truth[k] for k in common])
        so = M.wmape(A, np.array([po[k] for k in common]))
        st = M.wmape(A, np.array([pt[k] for k in common]))
        acc["ours"].append(so); acc["mlf"].append(st)
        rows[ql] = {"ours": so, "mlforecast": st, "gap": st - so, "n_points": len(common),
                    "t_ours_s": t_o, "t_mlf_s": t_t,
                    "coverage_ours": len(po), "coverage_mlf": len(pt)}
        print(f"  {ql:<9s} {so:>16.2f} {st:>16.2f} {st - so:>+8.2f} "
              f"{t_o:>7.1f}s {t_t:>7.1f}s")

    mo, mt = float(np.nanmean(acc["ours"])), float(np.nanmean(acc["mlf"]))
    print(f"\n  MEAN   ours {mo:.2f}   mlforecast {mt:.2f}   gap {mt - mo:+.2f}pp")
    verdict = ("AGREE - the two implementations are within 0.5pp, so our hand-rolled "
               "recursion is doing what a reference implementation does. Adopting "
               "MLForecast would buy maintainability, not accuracy."
               if abs(mt - mo) < 0.5 else
               ("MLFORECAST WINS by {:.2f}pp - our loop very likely has a defect. "
                "Find it before shipping anything else.".format(mo - mt) if mt < mo else
                "OURS WINS by {:.2f}pp - MLForecast is not reproducing our setup; do not "
                "adopt it on this evidence, and find out what differs.".format(mt - mo)))
    print(f"  {verdict}")

    OUT.write_text(json.dumps({"scope": scope, "features": FEATS, "by_quarter": rows,
                               "mean_ours": mo, "mean_mlforecast": mt,
                               "gap_pp": mt - mo, "verdict": verdict},
                              indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
