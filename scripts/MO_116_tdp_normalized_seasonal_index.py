#!/usr/bin/env python
"""MO_116 - build the seasonal index on Brian's metric, per account, and score it.

THE ARGUMENT
------------
MO_115 found that the year-over-year repeatability of the detrended week-of-year
profile -- the property that decides whether a seasonal factor can work at all --
improves sharply when base units are divided by TDP:

                  base units    base per store-week
  portfolio         +0.249            +0.367
  KROGER            -0.393            +0.424

Kroger's raw profile ANTI-correlates across years: last year's shape actively
mispredicts this year's. Nothing about Kroger's demand differs between those two
numbers, only the denominator. The seasonal signal was there; door count growing
326%/yr was burying it.

So every index we have ever shipped was estimated on the contaminated series. This
script builds it on the normalized series instead, and -- because MO_115 also showed the
shape is NOT uniform across accounts -- at per-account granularity as well as global.

ARMS (all scored inside the real production path, SEASONAL_MODE=step)
  off            no seasonal factor                           control
  mo59_global    the shipped STL index                        incumbent, 44.56 in MO_113
  tdp_global     detrended base-per-TDP, one global index
  tdp_account    detrended base-per-TDP, per retail_account, global fallback
  raw_global     detrended base UNITS, one global index        isolates the TDP
                                                              normalization from the
                                                              detrending method, so a
                                                              win cannot be credited to
                                                              the wrong cause

HONESTY
  Every index is estimated ONLY from data <= cutoff, rebuilt at each of the 7 quarter
  cutoffs. The detrending is log-linear rather than a centred rolling mean precisely
  because a centred window needs 26 weeks of future and so cannot be computed at a
  cutoff -- the method has to be the same in the backtest and in production or the
  backtest is measuring something that cannot ship.

  Per-account indices need enough history to estimate; an account with fewer than
  MIN_WEEKS observed weeks or fewer than MIN_POINTS usable residuals falls back to the
  global index rather than fitting noise.
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

OUT = Path("outputs/mo116_tdp_normalized_seasonal_index.json")
MIN_WEEKS = 78        # ~1.5 years before an account gets its own index
MIN_POINTS = 60       # usable residual points for a log-linear fit
TREES = 800
ARMS = ["off", "mo59_global", "raw_global", "tdp_global", "tdp_account"]


def _profile(frame: pd.DataFrame, num: str, den: str | None):
    """Log-linear-detrended week-of-year OFFSETS, matching the mo59 CSV convention.

    Returns {week_of_year: offset} where the multiplier production applies is
    1.0 + offset, or None when there is not enough signal to estimate.
    """
    g = frame.groupby("__time", as_index=False).agg(
        n=(num, "sum"), **({"d": (den, "sum")} if den else {}))
    g = g.sort_values("__time")
    y = g["n"].to_numpy(float)
    if den:
        d = g["d"].to_numpy(float)
        y = np.divide(y, d, out=np.full_like(y, np.nan), where=d > 0)
    ok = np.isfinite(y) & (y > 0)
    if ok.sum() < MIN_POINTS:
        return None
    t = np.arange(len(y), dtype=float)
    b = np.polyfit(t[ok], np.log(y[ok]), 1)
    r = y / np.exp(np.polyval(b, t))
    wk = g["__time"].dt.isocalendar().week.to_numpy()
    d2 = pd.DataFrame({"wk": wk, "r": r}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(d2) < MIN_POINTS:
        return None
    prof = d2.groupby("wk")["r"].mean()
    prof = prof / prof.mean()
    return {int(k): float(v - 1.0) for k, v in prof.items()}


def build_index(df: pd.DataFrame, cut: pd.Timestamp, kind: str, mo59: dict):
    """One index, estimated honestly from data <= cut."""
    tr = df[df["__time"] <= cut]
    if kind == "off":
        return {}
    if kind == "mo59_global":
        return mo59
    if kind == "raw_global":
        return _profile(tr, "base_units", None) or {}
    if kind == "tdp_global":
        return _profile(tr, "base_units", "tdp") or {}
    if kind == "tdp_account":
        g = _profile(tr, "base_units", "tdp") or {}
        out = {"__global__": g}
        wks = tr.groupby("retail_account")["__time"].nunique()
        for acct in wks[wks >= MIN_WEEKS].index:
            p = _profile(tr[tr["retail_account"] == acct], "base_units", "tdp")
            if p:
                out[acct] = p
        return out
    raise ValueError(kind)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default=None, help="restrict EVAL to one account")
    ap.add_argument("--channel", default="CONVENTIONAL|FOOD")
    ap.add_argument("--trees", type=int, default=TREES)
    a = ap.parse_args()

    os.environ["MO_SEASONAL_MODE"] = "step"       # MO_113's winner; fixed across arms
    import MO_80_quarterly_honest_backtest as M
    importlib.reload(M)
    assert M.SEASONAL_MODE == "step"

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    mo59 = M.load_seasonal_index()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]

    ev = df["channel_outlet"] == a.channel
    if a.account:
        ev &= df["retail_account"] == a.account
    scope = f"{a.account} {a.channel}" if a.account else "PORTFOLIO-WIDE"

    print(f"MO_116 - seasonal index built on base-per-TDP · {scope} · mode=step\n")
    print(f"  {'quarter':<9s} " + "  ".join(f"{k:>15s}" for k in ARMS))

    res = {k: {} for k in ARMS}
    meta = {}
    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[ev & (df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {(k[:-1], k[-1]): float(v) for k, v in
                 act.groupby(M.GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)

        cells, m = [], {}
        for kind in ARMS:
            idx = build_index(df, cut, kind, mo59)
            if kind == "tdp_account":
                m["n_account_indices"] = max(0, len(idx) - 1)
            pred = M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, idx)
            s = M.score(truth, pred)
            res[kind][ql] = s
            cells.append(f"{s['wmape']:>8.1f} {s['bias']:>6.3f}" if s else f"{'--':>15s}")
        meta[ql] = m
        print(f"  {ql:<9s} " + "  ".join(cells))

    print(f"\n  {'arm':<14s} {'wMAPE':>8s} {'bias':>7s}  {'|bias-1|':>8s}")
    means = {}
    for k in ARMS:
        vals = [v for v in res[k].values() if v]
        w = float(np.nanmean([v["wmape"] for v in vals]))
        b = float(np.nanmean([v["bias"] for v in vals]))
        ab = float(np.nanmean([abs(v["bias"] - 1) for v in vals]))
        means[k] = {"wmape": w, "bias": b, "abs_bias_err": ab}
        print(f"  {k:<14s} {w:>8.2f} {b:>7.3f}  {ab:>8.3f}")

    base = means["mo59_global"]["wmape"]
    print(f"\n  vs the shipped index ({base:.2f}):")
    for k in ARMS:
        if k != "mo59_global":
            print(f"    {k:<14s} {means[k]['wmape'] - base:+.2f}pp")
    best = min(ARMS, key=lambda k: means[k]["wmape"])
    print(f"\n  BEST: {best} ({means[best]['wmape']:.2f})")
    # Separating the two possible causes matters: if raw_global already captures most of
    # the gain, the win is the DETRENDING METHOD, not Brian's normalization.
    dn = means["tdp_global"]["wmape"] - means["raw_global"]["wmape"]
    print(f"  attribution: TDP normalization alone is worth {dn:+.2f}pp "
          f"(tdp_global vs raw_global, same detrending)")
    da = means["tdp_account"]["wmape"] - means["tdp_global"]["wmape"]
    print(f"               per-account granularity is worth {da:+.2f}pp")
    if best == "off":
        print("  -> even on the normalized series seasonality does not pay in production.")

    OUT.write_text(json.dumps({"scope": scope, "mode": "step", "by_quarter": res,
                               "means": means, "meta": meta,
                               "tdp_vs_raw_pp": dn, "account_vs_global_pp": da},
                              indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
