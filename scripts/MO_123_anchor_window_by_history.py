#!/usr/bin/env python
"""MO_123 - what is the right velocity anchor, by how much history a series has?

WHERE THIS CAME FROM — the client's own workbook, not our invention
-------------------------------------------------------------------
Rob: "this feels like the sort of thing that's wired into the excel book." It is, though
not in the form expected. Connor's Retail_Build tab (3,472 item x retailer rows) has no
predecessor mapping at all. What it has is:

    Method        L12W on 100% of rows — a 12-week velocity anchor is the default
    Override      manual, on 413 rows (11.9%)
    Notes         "L4W SPINS - new item ramping up"

So his entire cold-start method is: SHORTEN THE AVERAGING WINDOW from 12 weeks to 4 when
an item has no history, then override by hand where it looks wrong.

Our production router sends series with under 13 weeks of history to
`last_value_seasonal` -- effectively an L1W anchor. Connor uses L4W. A four-week mean is
less noisy than a single week, so in exactly the regime where noise dominates we may be
doing worse than the spreadsheet we are trying to improve on.

And ramping series are our worst segment by a distance (MO_122): 19,095 of 58,388
cell-weeks, flat 43.3 wMAPE, model 44.9.

ARMS — every naive arm carries the SAME seasonal multiplier production applies to
`last_value_seasonal`, so the comparison isolates the WINDOW and nothing else.

  L1W         last observed value          <- production today, for <13wk series
  L4W         mean of last 4 weeks         <- Connor's new-item rule
  L8W         mean of last 8
  L12W        mean of last 12              <- Connor's default for established items
  med12       MEDIAN of last 12            <- Retail_Build also carries a Median column
  model       the production LightGBM path

Scored by HISTORY BAND, because the whole question is whether the right window depends on
how much history a series has:

  <13 wks   the cohort production currently routes to last_value_seasonal
  13-25     ramping, routed to LightGBM today
  26-51     maturing
  52+       established, has lag52

If L4W beats L1W in the <13wk band, that is a direct, one-line improvement to MO_27's
router taken from the client's own domain practice.
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

OUT = Path("outputs/mo123_anchor_window.json")
TREES = 800
ARMS = ["L1W", "L4W", "L8W", "L12W", "med12", "model"]
BANDS = [(0, 13, "<13 wks"), (13, 26, "13-25 wks"), (26, 52, "26-51 wks"), (52, 10_000, "52+ wks")]


def band_of(n: int) -> str:
    for lo, hi, lbl in BANDS:
        if lo <= n < hi:
            return lbl
    return BANDS[-1][2]


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
    df["_brand"] = df["source_brand"].astype(str)
    seasonal = M.load_seasonal_index()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]

    print("MO_123 - velocity anchor window by history length")
    print(f"  mode={M.SEASONAL_MODE} refresh={M.FEATURE_REFRESH} · "
          "all naive arms carry the same seasonal multiplier\n")

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
        model = M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, seasonal)

        for key, g in tr.groupby(GC, observed=True):
            if key not in ek:
                continue
            g = g.sort_values("__time")
            h = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
            if not h:
                continue
            n = len(h)
            anchors = {
                "L1W": float(h[-1]),
                "L4W": float(np.mean(h[-4:])),
                "L8W": float(np.mean(h[-8:])),
                "L12W": float(np.mean(h[-12:])),
                "med12": float(np.median(h[-12:])),
            }
            seas = M._resolve_seasonal(seasonal, key)
            for step, fd in enumerate(fw[:M.HORIZON], start=1):
                if not (qs <= fd <= qe) or (key, fd) not in truth:
                    continue
                mv = model.get((key, fd))
                if mv is None:
                    continue
                # Same seasonal treatment production gives last_value_seasonal: a
                # multiplier relative to the anchor week, applied to a fixed level.
                mult = M._seasonal_mult(seas, fd, cut)
                row = {"quarter": ql, "band": band_of(n), "hist_wks": n,
                       "brand": str(g["_brand"].iloc[-1]), "h": step,
                       "actual": truth[(key, fd)], "model": mv}
                for k2, v in anchors.items():
                    row[k2] = max(0.0, v * mult)
                recs.append(row)

    r = pd.DataFrame(recs)
    if r.empty:
        print("no rows"); return
    print(f"  scored {len(r):,} cell-weeks\n")

    def wmape(g, arm):
        d = np.abs(g["actual"]).sum()
        return float(np.abs(g["actual"] - g[arm]).sum() / d * 100) if d > 0 else np.nan

    res = {}
    print("BY HISTORY BAND\n")
    print(f"  {'band':<12s} {'n':>8s} " + " ".join(f"{x:>9s}" for x in ARMS))
    for _, _, lbl in BANDS:
        g = r[r["band"] == lbl]
        if len(g) < 100:
            continue
        t = {arm: wmape(g, arm) for arm in ARMS}
        res[lbl] = {**t, "n": len(g)}
        best = min(ARMS, key=lambda x: t[x])
        print(f"  {lbl:<12s} {len(g):>8,} "
              + " ".join(f"{t[x]:>8.1f}{'*' if x == best else ' '}" for x in ARMS))

    print("\nBY BRAND (ramping cohort, <26 wks of history)\n")
    rr = r[r["hist_wks"] < 26]
    print(f"  {'brand':<20s} {'n':>8s} " + " ".join(f"{x:>9s}" for x in ARMS))
    res["ramping_by_brand"] = {}
    for b, g in rr.groupby("brand"):
        if len(g) < 200:
            continue
        t = {arm: wmape(g, arm) for arm in ARMS}
        res["ramping_by_brand"][b] = {**t, "n": len(g)}
        best = min(ARMS, key=lambda x: t[x])
        print(f"  {b[:19]:<20s} {len(g):>8,} "
              + " ".join(f"{t[x]:>8.1f}{'*' if x == best else ' '}" for x in ARMS))

    print("\nOVERALL\n")
    t = {arm: wmape(r, arm) for arm in ARMS}
    res["overall"] = {**t, "n": len(r)}
    best = min(ARMS, key=lambda x: t[x])
    print(f"  {'all series':<12s} {len(r):>8,} "
          + " ".join(f"{t[x]:>8.1f}{'*' if x == best else ' '}" for x in ARMS))

    print("\nVERDICT")
    sub = res.get("<13 wks")
    if sub:
        b = min(ARMS, key=lambda x: sub[x])
        d = sub["L1W"] - sub["L4W"]
        print(f"  <13wk cohort (production routes these to last_value = L1W):")
        print(f"    L1W {sub['L1W']:.1f}  L4W {sub['L4W']:.1f}  L12W {sub['L12W']:.1f}  "
              f"model {sub['model']:.1f}   best = {b}")
        if d > 0.5:
            print(f"  -> CONNOR'S RULE WINS by {d:.2f}pp. Change MO_27's short-series router\n"
                  f"     from last value to a 4-week mean. One line, taken from the client's\n"
                  f"     own practice.")
        elif d < -0.5:
            print(f"  -> L1W is better by {-d:.2f}pp; production is already right and the\n"
                  f"     spreadsheet rule does not transfer.")
        else:
            print("  -> L1W and L4W are within noise; no change justified on this evidence.")

    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
