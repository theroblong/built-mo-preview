#!/usr/bin/env python
"""MO_137b - Does the forecast under-forecast young, growing items and over-forecast established ones?

PLAIN WORDS: a check on stored forecasts (no model is trained). For each model, compare total forecast with total
actual sales (bias = forecast / actual; above 1 = over-forecast) for items grouped by how long they have sold at that
retailer (under 13 weeks, 13-25, 26-51, 52+), by how many weeks ahead the forecast is, and by retailer.

WHERE THIS CAME FROM
--------------------
MO_137 skeptic (2026-10-12): Walmart's January 2026 account total was right only because young items were badly
under-forecast (actual about 1.7-2x the forecast on two of them) while established items were slightly over-forecast,
and the errors cancelled. If that pattern is general, it is a real model weakness hidden by offsetting errors in
account totals, and the next model change should target it.

HYPOTHESES, WRITTEN BEFORE LOOKING
  H1 On the recent forecast dates (2025-12 on), the 5-seed fixed direct model (direct_avg5) under-forecasts items with
     under 26 weeks of history (bias < 0.95) and over-forecasts items with 52+ weeks (bias > 1.05).
  H2 The pattern holds at most of the five largest accounts (Walmart, Target, Sam's, Kroger, Publix), not only Walmart.
  H3 For young items the under-forecast grows with weeks ahead (bias at weeks 10-13 below bias at weeks 1-4).
  H4 Last week carried forward and L4W velocity x stores show the same pattern (a shared cause: young items keep
     growing and old ones fade), so it is not specific to the machine-learning model.

Inputs: scripts/outputs/mo137_rows.parquet (actual, band, account, flat, conn_L4W, direct_served, direct_avg5 seeds,
fade seeds). Output: scripts/outputs/mo137b_age_bias.json and the printed tables.
"""
from __future__ import annotations

# protocol: not-a-forecast-arm (diagnostic on stored forecasts; no model is trained)
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"
import MO_80_quarterly_honest_backtest as M  # noqa: E402 -- forecast cutoff dates per origin

OUT = Path("outputs/mo137b_age_bias.json")
MODELS = ["flat", "conn_L4W", "direct_served", "direct_avg5"]
BANDS = ["<13 wks", "13-25 wks", "26-51 wks", "52+ wks"]
TOP = ["WALMART", "TARGET", "SAMS", "KROGER", "PUBLIX"]
RECENT = "2025-12"


def bias(d: pd.DataFrame, m: str) -> float:
    a = d["actual"].sum()
    return float(d[m].sum() / a) if a > 0 else np.nan


def main() -> None:
    r = pd.read_parquet("outputs/mo137_rows.parquet")
    r = r[~r["is_new"] & r["band"].isin(BANDS)].copy()
    r["acct"] = r["account"].astype(str).str.upper()
    cut = {o[0]: M._utc(o[1]) for o in M.ORIGINS_MONTHLY}          # the real forecast date of each origin
    r["h"] = ((r["date"] - r["origin"].map(cut)).dt.days // 7).astype(int)
    assert r["h"].between(1, 13).all(), f"weeks ahead outside 1-13: {r['h'].min()}..{r['h'].max()}"
    r["hgrp"] = pd.cut(r["h"], [0, 4, 9, 13], labels=["wks 1-4", "wks 5-9", "wks 10-13"])
    res: dict = {}
    for name, sub in (("recent", r[r.origin >= RECENT]), ("2025", r[r.origin < RECENT])):
        print(f"\n=== {name.upper()} forecast dates: bias (forecast / actual) by item age ===")
        t = pd.DataFrame({m: [bias(sub[sub.band == b], m) for b in BANDS] for m in MODELS}, index=BANDS)
        t["share_of_volume"] = [sub.loc[sub.band == b, "actual"].sum() / sub["actual"].sum() for b in BANDS]
        print(t.round(3).to_string())
        print("\nby weeks ahead (direct_avg5):")
        th = sub.groupby(["band", "hgrp"], observed=True).apply(lambda d: bias(d, "direct_avg5")).unstack()
        print(th.reindex(BANDS).round(3).to_string())
        print("\nby retailer (direct_avg5), item-age groups:")
        rows = {}
        for a in TOP + ["ALL OTHER"]:
            s = sub[~sub.acct.isin(TOP)] if a == "ALL OTHER" else sub[sub.acct == a]
            rows[a] = {b: bias(s[s.band == b], "direct_avg5") for b in BANDS}
            rows[a]["volume_share"] = s["actual"].sum() / sub["actual"].sum()
        ta = pd.DataFrame(rows).T
        print(ta.round(3).to_string())
        res[name] = {"by_age": t.round(4).to_dict(), "by_horizon": th.round(4).to_dict(), "by_retailer": ta.round(4).to_dict()}
        # how much offsetting: account-month absolute error vs the sum of the four age groups' absolute errors
        g = sub.assign(month=sub["date"].dt.to_period("M").astype(str))
        acct = g.groupby(["origin", "acct", "month"])[["actual", "direct_avg5"]].sum()
        acct_err = np.abs(acct["actual"] - acct["direct_avg5"]).sum()
        band_err = np.abs(g.groupby(["origin", "acct", "month", "band"])[["actual", "direct_avg5"]].sum()
                          .pipe(lambda x: x["actual"] - x["direct_avg5"])).sum()
        print(f"\noffsetting: account-month absolute error {acct_err:,.0f} vs the same split by item age {band_err:,.0f} "
              f"-> {1 - acct_err / band_err:.1%} of the age-group error cancels inside account totals")
        res[name]["offset_share"] = float(1 - acct_err / band_err)
    rec = res["recent"]["by_age"]["direct_avg5"]
    young = min(rec["<13 wks"], rec["13-25 wks"])
    checks = [
        ("H1", rec["<13 wks"] < 0.95 and rec["13-25 wks"] < 0.95 and rec["52+ wks"] > 1.05,
         f"recent direct_avg5 bias <13 {rec['<13 wks']:.3f}, 13-25 {rec['13-25 wks']:.3f}, 52+ {rec['52+ wks']:.3f}"),
        ("H2", sum(1 for a in TOP if res["recent"]["by_retailer"]["<13 wks"].get(a, np.nan) < 0.95
                   and res["recent"]["by_retailer"]["52+ wks"].get(a, np.nan) > 1.0) >= 3,
         "count of top-5 accounts with <13-week bias < 0.95 and 52+ bias > 1.0"),
        ("H3", all(res["recent"]["by_horizon"]["wks 10-13"].get(b, np.nan) < res["recent"]["by_horizon"]["wks 1-4"].get(b, np.nan)
                   for b in ["<13 wks", "13-25 wks"]), "young items: bias weeks 10-13 below weeks 1-4"),
        ("H4", all(res["recent"]["by_age"][m]["<13 wks"] < 1 and res["recent"]["by_age"][m]["52+ wks"] > 1
                   for m in ("flat", "conn_L4W")), "last value and L4W also under young / over established"),
    ]
    print("\nHYPOTHESES")
    res["hypotheses"] = {}
    for hid, ok, msg in checks:
        res["hypotheses"][hid] = {"result": "HOLDS" if ok else "FAILS", "detail": msg}
        print(f"  {hid} {'HOLDS' if ok else 'FAILS':<6s} {msg}")
    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
