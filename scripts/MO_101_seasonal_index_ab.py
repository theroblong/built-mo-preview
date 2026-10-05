#!/usr/bin/env python
"""MO_101 - does the rebuilt seasonal index actually help? wMAPE AND bias.

MO_100 rebuilt the seasonal index at the monthly/pooled level, where the signal
demonstrably lives (March positive in all three years, leave-one-year-out
correlation +0.939 to +0.974). Building a better-looking curve is not the same as
improving a forecast, so this A/Bs it inside the production recursive loop.

Arms:
  none        no seasonal factor at all
  mo59        the live index, built on ALL data -> LEAKS inside a backtest of an
              earlier period; reported for comparison and labelled as such
  mo100_leaky MO_100 built on all data, same leak, to isolate "new curve" from
              "honest curve"
  mo100       MO_100 rebuilt from data <= each cutoff. The honest arm.

Reported with BIAS as well as wMAPE, and split portfolio vs KROGER, because the
requirement is not just lower error. Jason: "We really don't want a downward
trending line underforecast for Q1 2026." Every bias figure we have is already
below 1.0, so an arm that lowers error while pushing bias further down is making
the stated problem worse. bias = sum(pred)/sum(actual); 1.0 is unbiased.
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
import MO_100_monthly_seasonal_index as S
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo101_seasonal_ab.json")
TREES = 1200
QUARTERS = [q for q in M.QUARTERS if q[0] != "Q4 2026"]


def weekly_from(df, cutoff):
    idx, _ = S.monthly_index(df, cutoff=cutoff, verbose=False)
    if idx is None:
        return {}
    wk = S.to_weekly(idx)
    return dict(zip(wk["week_of_year"].astype(int), wk["seasonal_index"]))


def as_offsets(d):
    """MO_27/MO_80 expect week -> OFFSET where the factor is (1 + offset)."""
    return {k: v - 1.0 for k, v in d.items()}


def main() -> None:
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    raw = S.load_panel()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))

    mo59 = M.load_seasonal_index()
    mo100_all = as_offsets(weekly_from(raw, None))
    print("MO_101 - seasonal index A/B inside the production loop")
    print(f"  mo59 weeks loaded: {len(mo59)} | mo100 weeks: {len(mo100_all)}")
    if mo59:
        a = np.array([mo59.get(w, 0.0) for w in range(1, 53)])
        b = np.array([mo100_all.get(w, 0.0) for w in range(1, 53)])
        print(f"  correlation between the two curves: {np.corrcoef(a, b)[0,1]:+.3f}")
        print(f"  amplitude  mo59 {a.max()-a.min():.3f}   mo100 {b.max()-b.min():.3f}")

    kr = df[(df["retail_account"] == "KROGER") & (df["channel_outlet"] == "CONVENTIONAL|FOOD")]
    kroger_keys = set(map(tuple, kr[GROUP_COLS].drop_duplicates().values))

    arms = ["none", "mo59", "mo100_leaky", "mo100"]
    acc = {a: {"portfolio": [], "kroger": []} for a in arms}
    detail = {}

    print(f"\n  {'quarter':<9s} " + " ".join(f"{a:>15s}" for a in arms))
    for ql, qc, q1, q2 in QUARTERS:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        eval_keys = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        honest = as_offsets(weekly_from(raw, cut))

        cells, row = [], {}
        for arm in arms:
            seas = {"none": {}, "mo59": mo59,
                    "mo100_leaky": mo100_all, "mo100": honest}[arm]
            pred = M.run_production(df, feats, cut, qs, qe, eval_keys, TREES, fw, seas)
            pred = {k: (v["q50"] if isinstance(v, dict) else v) for k, v in pred.items()}
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
                row[f"{arm}_{scope}"] = {"wmape": w, "bias": b}
            cells.append(f"{row[f'{arm}_portfolio']['wmape']:>8.1f} "
                         f"{row[f'{arm}_portfolio']['bias']:>6.3f}")
        detail[ql] = row
        print(f"  {ql:<9s} " + " ".join(cells))

    for scope, title in (("portfolio", "PORTFOLIO-WIDE"),
                         ("kroger", "KROGER CONVENTIONAL|FOOD (accuracy proof)")):
        print(f"\n=== {title} — mean over {len(QUARTERS)} honest quarters ===")
        print(f"  {'arm':<13s} {'wMAPE':>8s} {'bias':>7s}   note")
        for arm in arms:
            v = acc[arm][scope]
            w = np.nanmean([x[0] for x in v]); b = np.nanmean([x[1] for x in v])
            note = {"mo59": "LEAKS (built on all data)",
                    "mo100_leaky": "LEAKS (built on all data)",
                    "mo100": "honest, rebuilt per cutoff",
                    "none": "no seasonal factor"}[arm]
            print(f"  {arm:<13s} {w:>8.2f} {b:>7.3f}   {note}")

    OUT.write_text(json.dumps({"by_quarter": detail,
                               "means": {a: {s: {"wmape": float(np.nanmean([x[0] for x in acc[a][s]])),
                                                 "bias": float(np.nanmean([x[1] for x in acc[a][s]]))}
                                             for s in ("portfolio", "kroger")} for a in arms}},
                              indent=2, default=str))
    print(f"\nwrote {OUT}")
    print("\n  Compare 'mo100' (honest) against 'none'. The leaky arms only show how")
    print("  much of any gain came from seeing the future when the curve was built.")


if __name__ == "__main__":
    main()
