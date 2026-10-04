#!/usr/bin/env python
"""MO_93 - which production component costs Q3 2026 20 points?

Adding production parity to MO_80 helped the ramp quarters (Q1 2025 -2.6pp,
Q3 2025 -14.6pp, Q1 2026 -7.2pp) and hurt others, worst of all Q3 2026 at
+20.5pp with bias falling 0.825 -> 0.650. The lapsed hard-zero was the obvious
suspect and is ruled out: lapsed series carry ~0% of KROGER Food volume in every
quarter. So the cost is in one of the other three pieces.

Arms, each removing exactly one thing from run_production:
  full         everything MO_27 does
  no_blend     SEASONAL_BLEND_WEIGHT = 0 (YAGO blend off, STL fallback still on)
  no_stl       STL fallback off (YAGO blend still on)
  no_lag52     stop refreshing base_units_lag52 per step (what bare recursive did)
  no_router    short/lapsed series go through the AR path instead

Reports wMAPE and bias per quarter so the damage is attributable rather than guessed.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

import MO_80_quarterly_honest_backtest as M
from mo_panel import GROUP_COLS

OUT = Path("outputs/mo93_production_ablation.json")
TREES = 800
QUARTERS = [q for q in M.QUARTERS if q[0] != "Q4 2026"]
ARMS = ("full", "no_blend", "no_stl", "no_lag52", "no_router")


def run_arm(arm, df, feats, cut, qs, qe, eval_keys, fweeks, seasonal):
    """run_production with one component disabled, by patching module state."""
    blend, stl = M.SEASONAL_BLEND_WEIGHT, seasonal
    if arm == "no_blend":
        M.SEASONAL_BLEND_WEIGHT = 0.0
    if arm == "no_stl":
        stl = {}
    if arm == "no_router":
        M.MIN_SERIES_WEEKS_LOCAL, M.LAPSE_WEEKS = 0, 10 ** 6
    if arm == "no_lag52":
        feats_eff = [f for f in feats]
        M._SKIP_LAG52 = True
    try:
        out = M.run_production(df, feats, cut, qs, qe, eval_keys, TREES, fweeks, stl)
    finally:
        M.SEASONAL_BLEND_WEIGHT = blend
        M.MIN_SERIES_WEEKS_LOCAL, M.LAPSE_WEEKS = 13, 9
        M._SKIP_LAG52 = False
    return out


def main() -> None:
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    seasonal = M.load_seasonal_index()
    df = M.load_panel(feats)
    WEEKS = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    ev = (df["retail_account"] == "KROGER") & (df["channel_outlet"] == "CONVENTIONAL|FOOD")

    print("MO_93 - production component ablation (KROGER CONVENTIONAL|FOOD)\n")
    print(f"  {'quarter':<9s} " + " ".join(f"{a:>16s}" for a in ARMS))
    results = {}
    for ql, qc, q1, q2 in QUARTERS:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[ev & (df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        eval_keys = {k[0] for k in truth}
        fweeks = M.future_weeks(WEEKS, cut, M.HORIZON)
        row, cells = {}, []
        for arm in ARMS:
            pred = run_arm(arm, df, feats, cut, qs, qe, eval_keys, fweeks, seasonal)
            pred = {k: (v["q50"] if isinstance(v, dict) else v) for k, v in pred.items()}
            sc = M.score(truth, pred)
            row[arm] = sc
            cells.append(f"{sc['wmape']:>9.1f} {sc['bias']:>6.3f}" if sc else f"{'--':>16s}")
        results[ql] = row
        print(f"  {ql:<9s} " + " ".join(cells))

    print(f"\n  {'arm':<10s} {'mean wMAPE':>11s} {'mean |bias-1|':>14s}")
    for arm in ARMS:
        w = [results[q][arm]["wmape"] for q in results if results[q].get(arm)]
        b = [abs(results[q][arm]["bias"] - 1) for q in results if results[q].get(arm)]
        print(f"  {arm:<10s} {np.mean(w):>11.1f} {np.mean(b):>14.3f}")

    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
