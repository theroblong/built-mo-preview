#!/usr/bin/env python
"""MO_105 - the coherent / projected TDP arms, PORTFOLIO-WIDE this time.

MO_95 measured four TDP-handling arms but only on KROGER Conventional Food --
20 to 39 series per quarter. Jason: "I want to preserve the Kroger accuracy proof
for comparison, but I do want to see what we can figure out portfolio-wide rather
than just solving for Kroger." This is the portfolio-wide version, with the Kroger
cut reported alongside so the earlier proof stays comparable.

Arms (identical to MO_95 so the two are directly comparable):
  frozen     production today -- every TDP feature held at its anchor value
  coherent   level held, momentum/delta features ZEROED so the model is not told
             distribution is moving while the level never changes. Free: no new
             data, no projector, no leakage.
  projected  per-cell damped linear TDP trend, fit on data <= cut only
  oracle     ACTUAL future TDP -- not shippable, it is the CEILING

MO_95's Kroger result: oracle was worth only 0.6pp, coherent -0.7pp, projected
-0.5pp. If those hold portfolio-wide, the whole direction is closed. If they do
not, 20-39 series was simply too small a sample to conclude from.
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
import MO_95_tdp_unfreeze as T
from mo_panel import GROUP_COLS

OUT = Path("outputs/mo105_tdp_arms_portfolio.json")
ARMS = ("frozen", "coherent", "projected", "oracle")


def main() -> None:
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    seasonal = M.load_seasonal_index()
    df = M.load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    kr = df[(df["retail_account"] == "KROGER") & (df["channel_outlet"] == "CONVENTIONAL|FOOD")]
    kroger_keys = set(map(tuple, kr[GROUP_COLS].drop_duplicates().values))

    print("MO_105 - TDP arms PORTFOLIO-WIDE (Kroger reported alongside)")
    print(f"  {df.groupby(GROUP_COLS, observed=True).ngroups:,} series total, "
          f"{len(kroger_keys)} at KROGER Conventional Food\n")
    print(f"  {'quarter':<9s} " + " ".join(f"{a:>15s}" for a in ARMS))

    acc = {a: {"portfolio": [], "kroger": []} for a in ARMS}
    detail = {}
    for ql, qc, q1, q2 in [q for q in M.QUARTERS if q[0] != "Q4 2026"]:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}            # ALL series, not just Kroger
        fw = M.future_weeks(weeks, cut, M.HORIZON)

        cells, row = [], {}
        for arm in ARMS:
            pred = T.run_arm(arm, df, feats, cut, qs, qe, ek, fw, seasonal)
            for scope, keys in (("portfolio", None), ("kroger", kroger_keys)):
                A = [truth[k] for k in truth if k in pred and (keys is None or k[0] in keys)]
                P = [pred[k] for k in truth if k in pred and (keys is None or k[0] in keys)]
                if A:
                    A_, P_ = np.array(A), np.array(P)
                    w = float(np.abs(A_ - P_).sum() / np.abs(A_).sum() * 100)
                    b = float(P_.sum() / A_.sum())
                else:
                    w = b = float("nan")
                acc[arm][scope].append((w, b))
                row[f"{arm}_{scope}"] = {"wmape": w, "bias": b, "n": len(A)}
            cells.append(f"{row[f'{arm}_portfolio']['wmape']:>8.1f} "
                         f"{row[f'{arm}_portfolio']['bias']:>6.3f}")
        detail[ql] = row
        print(f"  {ql:<9s} " + " ".join(cells))

    results = {}
    for scope, title in (("portfolio", "PORTFOLIO-WIDE"),
                         ("kroger", "KROGER CONVENTIONAL|FOOD (MO_95's sample)")):
        print(f"\n=== {title} ===")
        print(f"  {'arm':<11s} {'wMAPE':>8s} {'bias':>7s} {'vs frozen':>11s}")
        base = np.nanmean([x[0] for x in acc["frozen"][scope]])
        for arm in ARMS:
            v = acc[arm][scope]
            w = np.nanmean([x[0] for x in v]); b = np.nanmean([x[1] for x in v])
            results.setdefault(scope, {})[arm] = {"wmape": float(w), "bias": float(b),
                                                  "delta": float(w - base)}
            print(f"  {arm:<11s} {w:>8.2f} {b:>7.3f} {w-base:>+10.2f}pp")

    OUT.write_text(json.dumps({"by_quarter": detail, "means": results},
                              indent=2, default=str))
    print(f"\nwrote {OUT}")
    print("\n  MO_95 on Kroger gave: oracle -0.6pp, coherent -0.7pp, projected -0.5pp.")
    print("  If portfolio-wide agrees, the direction is closed. If not, 20-39 series")
    print("  was too small a sample to have concluded from.")


if __name__ == "__main__":
    main()
