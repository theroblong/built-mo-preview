#!/usr/bin/env python
"""MO_124 - the two-stage model, built the way CONNOR builds it, scored at every level.

WHY MO_117'S VERDICT HAD TO BE REOPENED
---------------------------------------
MO_117 tested velocity x doors, found it lost by 0.61pp even with ORACLE doors, and the
direction was reported as closed. Reading Connor's workbook formulas then showed that
**his planning model is exactly that architecture**:

    Starting Base = IF(Override>0, Override, SUMIFS(K:O, K6:O6, Method) * AdjFactor)
    L4W/L12W/L24W/L52W = SUMIFS(SPINS!R:R, ...)   where SPINS col R = "Base U/S/W"

`Method` is a COLUMN SELECTOR (L12W on all 3,472 rows), and the columns it selects are
**Base Units per Store per Week** over trailing periods. That base is then multiplied by
a points-of-distribution forecast (Slotting Output) and adjusted by seasonality and macro
indices. Overrides appear on 11.9% of rows.

So the client plans with a two-stage velocity x distribution model. Two reasons MO_117's
verdict does not settle it:

  1. It scored at CELL x WEEK — the one level where a naive carry-forward dominates and
     where our own model also loses (MO_122: flat 32.3, model 35.9). At PORTFOLIO x MONTH
     the model wins (12.2 vs 16.4). The two-stage question has never been asked there.
  2. It forecast velocity with LIGHTGBM. Connor anchors velocity on a plain trailing SPINS
     figure — simpler, and plausibly more robust on a noisy series.

VELOCITY DEFINITION, derived from the workbook rather than assumed
------------------------------------------------------------------
SPINS row: Units 7418.6, Base Units 7368, Stores Selling 437, period 12 weeks.
  Avg Weekly Units Per Store = units / (weeks x stores)       = 1.415 (displayed 1.4)
  Base % of Blended          = base / units                   = 0.99318
  Base U/S/W                 = AvgWeekly x Base%              = 1.39045  ✓ reported

=> Base U/S/W = base_units / (weeks x stores). Our panel analog, with TDP standing in for
   store count: velocity_W = sum(base_units[-W:]) / sum(tdp[-W:]). The week count cancels
   because sum(tdp) over W weeks is W x average tdp.

ARMS
  flat              carry last week forward                      the benchmark
  model             production LightGBM path                     what we ship
  conn_L4W          velocity(4wk)  x doors                       his new-item rule
  conn_L12W         velocity(12wk) x doors                       HIS DEFAULT
  conn_L24W         velocity(24wk) x doors
  conn_median       median of the four velocities x doors        his Median column
  conn_L12W_oracle  velocity(12wk) x ACTUAL future doors         the ceiling

Doors are carried flat from the last observed TDP except in the oracle arm — Connor gets
them from a separate distribution forecast we do not have. All velocity arms carry the
same seasonal multiplier production applies, so the comparison isolates the anchor.

LEVELS: cell x week, account x month, portfolio x month — bottom-up, so they reconcile.
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

OUT = Path("outputs/mo124_connor_two_stage.json")
TREES = 800
WINDOWS = {"L4W": 4, "L12W": 12, "L24W": 24, "L52W": 52}
ARMS = ["flat", "model", "conn_L4W", "conn_L12W", "conn_L24W", "conn_median",
        "conn_L12W_oracle"]
TDP_FLOOR = 0.05


def velocity(bu: list[float], td: list[float], w: int) -> float:
    """Base U/S/W over the trailing w weeks: sum(base_units) / sum(tdp)."""
    b = np.asarray(bu[-w:], float)
    t = np.asarray(td[-w:], float)
    ok = np.isfinite(b) & np.isfinite(t)
    if not ok.any():
        return np.nan
    st = t[ok].sum()
    return float(b[ok].sum() / st) if st > TDP_FLOOR else np.nan


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=TREES)
    a = ap.parse_args()

    os.environ["MO_SEASONAL_MODE"] = "anchor"
    import MO_80_quarterly_honest_backtest as M
    importlib.reload(M)
    assert M.FEATURE_REFRESH == "freeze", "harness must match MO_27"
    GC = M.GROUP_COLS

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    seasonal = M.load_seasonal_index()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]

    print("MO_124 - Connor's two-stage construction, scored at every level")
    print(f"  mode={M.SEASONAL_MODE} refresh={M.FEATURE_REFRESH}")
    print("  velocity = sum(base_units[-W:]) / sum(tdp[-W:])  [= SPINS Base U/S/W]\n")

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
        atdp = {(k[:-1], k[-1]): float(v) for k, v in
                act.groupby(GC + ["__time"], observed=True)["tdp"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        tr = df[df["__time"] <= cut]
        model = M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, seasonal)

        for key, g in tr.groupby(GC, observed=True):
            if key not in ek:
                continue
            g = g.sort_values("__time")
            bu = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
            td = list(pd.to_numeric(g["tdp"], errors="coerce").ffill().fillna(0))
            if len(bu) < 4:
                continue
            vels = {k: velocity(bu, td, w) for k, w in WINDOWS.items()}
            vmed = float(np.nanmedian([v for v in vels.values() if np.isfinite(v)])) \
                if any(np.isfinite(v) for v in vels.values()) else np.nan
            doors_flat = float(td[-1]) if td else 0.0
            last = float(bu[-1])
            seas = M._resolve_seasonal(seasonal, key)
            for step, fd in enumerate(fw[:M.HORIZON], start=1):
                if not (qs <= fd <= qe) or (key, fd) not in truth:
                    continue
                mv = model.get((key, fd))
                if mv is None:
                    continue
                mult = M._seasonal_mult(seas, fd, cut)
                od = atdp.get((key, fd), np.nan)
                row = {"quarter": ql, "key": key, "date": fd, "h": step,
                       "account": key[GC.index("retail_account")],
                       "actual": truth[(key, fd)], "flat": last, "model": mv}
                for k2 in ("L4W", "L12W", "L24W"):
                    v = vels[k2]
                    row[f"conn_{k2}"] = (max(0.0, v * doors_flat * mult)
                                         if np.isfinite(v) else last)
                row["conn_median"] = (max(0.0, vmed * doors_flat * mult)
                                      if np.isfinite(vmed) else last)
                v12 = vels["L12W"]
                row["conn_L12W_oracle"] = (max(0.0, v12 * od * mult)
                                           if np.isfinite(v12) and np.isfinite(od)
                                           else row["conn_L12W"])
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
    print("THE SAME FORECASTS AT EVERY LEVEL (bottom-up, so they reconcile)\n")
    print(f"  {'level':<22s} {'n':>7s} " + " ".join(f"{x:>11s}" for x in ARMS))
    for lbl, keys in (("cell x week", None),
                      ("account x month", ["account", "month"]),
                      ("portfolio x month", ["month"])):
        g = r if keys is None else r.groupby(keys, as_index=False)[["actual"] + ARMS].sum()
        t = {arm: wmape(g, arm) for arm in ARMS}
        res[lbl] = {**t, "n": len(g)}
        best = min(ARMS, key=lambda x: t[x])
        print(f"  {lbl:<22s} {len(g):>7,} "
              + " ".join(f"{t[x]:>10.1f}{'*' if x == best else ' '}" for x in ARMS))

    print("\nBIAS at portfolio x month (forecast / actual)\n")
    pm = r.groupby("month", as_index=False)[["actual"] + ARMS].sum()
    print(f"  {'arm':<20s} {'bias':>8s}")
    res["portfolio_bias"] = {}
    for arm in ARMS:
        b = float(pm[arm].sum() / pm["actual"].sum())
        res["portfolio_bias"][arm] = b
        print(f"  {arm:<20s} {b:>8.3f}")

    print("\nVERDICT")
    pmr = res["portfolio x month"]
    best = min(ARMS, key=lambda x: pmr[x])
    conn_best = min([a for a in ARMS if a.startswith("conn")], key=lambda x: pmr[x])
    print(f"  portfolio x month: model {pmr['model']:.1f}, flat {pmr['flat']:.1f}, "
          f"best Connor-style {conn_best} {pmr[conn_best]:.1f}")
    if pmr[conn_best] < pmr["model"] - 0.3:
        print(f"  -> CONNOR'S CONSTRUCTION BEATS OURS at the planning level by "
              f"{pmr['model'] - pmr[conn_best]:.2f}pp.\n"
              f"     MO_117's verdict was an artifact of scoring at cell x week.")
    elif pmr["model"] < pmr[conn_best] - 0.3:
        print(f"  -> our model still wins at the planning level by "
              f"{pmr[conn_best] - pmr['model']:.2f}pp. MO_117's verdict holds, and now it\n"
              f"     holds against the client's ACTUAL construction rather than our proxy.")
    else:
        print("  -> the two are within noise at the planning level.")
    oc = pmr["conn_L12W_oracle"] - pmr["conn_L12W"]
    print(f"  oracle doors are worth {oc:+.2f}pp on the L12W arm "
          f"— the value of a distribution forecast we do not have.")

    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
