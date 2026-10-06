#!/usr/bin/env python
"""MO_125 - do the day's candidates combine, and does conn_L4W replace or complement?

THREE CANDIDATES CAME OUT OF 2026-10-06, EACH MEASURED ALONE
-------------------------------------------------------------
  anchor seasonal mode   40.08 vs 41.25 shipped (-1.17pp)   MO_113, corrected harness
  exclude BAR from training  -1.34pp on non-BAR series      MO_121, all 7 quarters
  conn_L4W velocity x doors   wins at ALL THREE levels      MO_124

Stacking changes measured in isolation is exactly how this loop has surprised us twice
already, so they are tested together here before anything ships.

THE REAL QUESTION is the last one. `conn_L4W` -- trailing 4-week Base U/S/W times current
doors, seasonally adjusted -- beat our LightGBM path at every level, including cell x week
where nothing had beaten flat all day:

                      flat    model   conn_L4W
  cell x week         32.8     36.3     28.4
  account x month     22.9     24.7     17.7
  portfolio x month   16.0     11.8     10.7

So: does it REPLACE the model, or do the two carry different information and combine? A
blend sweep answers that directly. If the best blend weight is 0 or 1, one of them is
redundant. If it is interior, they are complementary and the gain is larger than either.

ARMS
  production        shipped config: target-only seasonal, pooled training
  model_anchor      + anchor seasonal mode                     candidate 1
  model_anchor_noBAR  + BAR excluded from training             candidate 2
  conn_L4W          trailing 4wk velocity x current doors      candidate 3
  conn_L4W_noseas   same, seasonal factor OFF                  is seasonality helping it?
  blend_25/50/75    w*model_anchor + (1-w)*conn_L4W            replace or complement?

Scored at all three levels, bottom-up so they reconcile, with bias reported because the
day's headline defect was a -5% systematic under-forecast that conn_L4W appears to fix.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("outputs/mo125_combined_candidates.json")
TREES = 800
TDP_FLOOR = 0.05
BLENDS = [0.25, 0.50, 0.75]
ARMS = (["production", "model_anchor", "model_anchor_noBAR", "conn_L4W", "conn_L4W_noseas"]
        + [f"blend_{int(w*100)}" for w in BLENDS])


def velocity(bu, td, w=4):
    b = np.asarray(bu[-w:], float); t = np.asarray(td[-w:], float)
    ok = np.isfinite(b) & np.isfinite(t)
    if not ok.any():
        return np.nan
    st = t[ok].sum()
    return float(b[ok].sum() / st) if st > TDP_FLOOR else np.nan


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=TREES)
    a = ap.parse_args()

    import MO_80_quarterly_honest_backtest as M
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)

    # The two seasonal modes need separate module states; reload between them.
    def load(mode):
        os.environ["MO_SEASONAL_MODE"] = mode
        importlib.reload(M)
        assert M.SEASONAL_MODE == mode and M.FEATURE_REFRESH == "freeze"
        return M

    load("target")
    df = M.load_panel(feats)
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    df["_brand"] = df["source_brand"].astype(str)
    seasonal = M.load_seasonal_index()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]
    GC = M.GROUP_COLS
    nb = df[df["_brand"] != "BUILT BAR"]

    print("MO_125 - do the day's candidates combine?")
    print("  production = target-only seasonal, pooled training (what ships today)\n")

    recs = []
    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {(k[:-1], k[-1]): float(v) for k, v in
                 act.groupby(GC + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        tr = df[df["__time"] <= cut]

        load("target")
        p_prod = M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, seasonal)
        load("anchor")
        p_anch = M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, seasonal)
        nonbar = {k for k in ek if k not in set()}
        p_nobar = M.run_production(nb, feats, cut, qs, qe, ek, a.trees, fw, seasonal)

        for key, g in tr.groupby(GC, observed=True):
            if key not in ek:
                continue
            g = g.sort_values("__time")
            bu = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
            td = list(pd.to_numeric(g["tdp"], errors="coerce").ffill().fillna(0))
            if len(bu) < 4:
                continue
            v4 = velocity(bu, td)
            doors = float(td[-1]) if td else 0.0
            last = float(bu[-1])
            seas = M._resolve_seasonal(seasonal, key)
            for step, fd in enumerate(fw[:M.HORIZON], start=1):
                if not (qs <= fd <= qe) or (key, fd) not in truth:
                    continue
                pa = p_anch.get((key, fd))
                pp = p_prod.get((key, fd))
                if pa is None or pp is None:
                    continue
                mult = M._seasonal_mult(seas, fd, cut)
                base_v = v4 * doors if np.isfinite(v4) else last
                row = {"quarter": ql, "date": fd,
                       "account": key[GC.index("retail_account")],
                       "actual": truth[(key, fd)],
                       "production": pp, "model_anchor": pa,
                       "model_anchor_noBAR": p_nobar.get((key, fd), pa),
                       "conn_L4W": max(0.0, base_v * mult),
                       "conn_L4W_noseas": max(0.0, base_v)}
                for w in BLENDS:
                    row[f"blend_{int(w*100)}"] = w * row["model_anchor"] + (1 - w) * row["conn_L4W"]
                recs.append(row)

    r = pd.DataFrame(recs)
    if r.empty:
        print("no rows"); return
    r["month"] = pd.to_datetime(r["date"]).dt.to_period("M").astype(str)
    print(f"  scored {len(r):,} cell-weeks\n")

    def wmape(g, arm):
        d = np.abs(g["actual"]).sum()
        return float(np.abs(g["actual"] - g[arm]).sum() / d * 100) if d > 0 else np.nan

    res = {}
    for lbl, keys in (("cell x week", None),
                      ("account x month", ["account", "month"]),
                      ("portfolio x month", ["month"])):
        g = r if keys is None else r.groupby(keys, as_index=False)[["actual"] + ARMS].sum()
        t = {arm: wmape(g, arm) for arm in ARMS}
        res[lbl] = {**t, "n": len(g)}
        best = min(ARMS, key=lambda x: t[x])
        print(f"{lbl.upper()}  (n={len(g):,})")
        for arm in ARMS:
            print(f"    {arm:<22s} {t[arm]:>7.2f}{'  <- best' if arm == best else ''}")
        print()

    pm = r.groupby("month", as_index=False)[["actual"] + ARMS].sum()
    print("BIAS at portfolio x month")
    res["portfolio_bias"] = {}
    for arm in ARMS:
        b = float(pm[arm].sum() / pm["actual"].sum())
        res["portfolio_bias"][arm] = b
        print(f"    {arm:<22s} {b:>7.3f}")

    print("\nVERDICT")
    pmr = res["portfolio x month"]
    bb = min([f"blend_{int(w*100)}" for w in BLENDS], key=lambda x: pmr[x])
    print(f"  portfolio x month: production {pmr['production']:.2f}  "
          f"conn_L4W {pmr['conn_L4W']:.2f}  best blend {bb} {pmr[bb]:.2f}")
    if pmr[bb] < min(pmr["conn_L4W"], pmr["model_anchor"]) - 0.2:
        print("  -> COMPLEMENTARY: a blend beats either alone, so the two carry different\n"
              "     information. Ship the blend, not a replacement.")
    elif pmr["conn_L4W"] <= pmr["model_anchor"]:
        print("  -> conn_L4W dominates; the LightGBM path adds nothing at this level.")
    else:
        print("  -> the model dominates conn_L4W at this level.")
    d = pmr["conn_L4W_noseas"] - pmr["conn_L4W"]
    print(f"  seasonality is worth {d:+.2f}pp on conn_L4W")

    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
