#!/usr/bin/env python
"""MO_144 - Can we forecast item x retailer series that do not exist yet at the forecast date?

PLAIN WORDS: every test so far scores only series that already sell at the forecast date; brand-new series
(an item reaching a new retailer after the forecast date) are set to zero. They are a large part of BUILT's
growth (14% of actual volume 13 weeks out, provisional MO_91/92). This tests two ways to add them:
  B  "arrival layer" (no plan needed): each account gets roughly as many new series as it got lately, and each
     sells like that account's past launches did -- an account-level number, not item-specific;
  C  "with a launch plan": suppose BUILT tells us which items launch at which retailer and when (simulated here by
     using the actual launch weeks); each launch is sized from the same item's early sales per distribution point
     at retailers that launched it earlier, times this account's typical early distribution; if the item has never
     launched anywhere, the account's (or channel's) average launch curve is used.
     C shows what a launch calendar from BUILT would be worth; it is not available to the forecast today.

WHERE THIS CAME FROM: MO_140 (skeptic, 2026-10-13): brand-new items were forced to zero and never scored, so
"new items borrow from similar products" was untested; Jason approved MO_144 in the 2026-10-13 plan.

PRIOR WORK (docs/SETTLED_FINDINGS.md, README):
  - MO_91 / MO_92 (PROVISIONAL, pre-fix bench, README 207): arrival layer cut the 13-week portfolio bias from
    -10.7% to -1.3% but did not improve month-to-month error ("do not ship as an accuracy improvement"); never
    re-run on the corrected bench -> re-tested here as arm B.
  - MO_140 (PROVISIONAL, README 241): reopen-if "a cold-start test (items with no history at the forecast date)";
    this is that test.
  - MO_79 (SETTLED: cold start, naive_last wins every band) concerns young series WITH some history; not re-tested.
  - SETTLED decomposition rule (MO_91/92): split any miss into existing-series error and unseen-series coverage.

ARMS (all share the production existing-series forecast direct_avg5 = MO_133's 5-seed fixed direct model, already
in scripts/outputs/mo140_rows.parquet with new/lapsed rows at 0):
  A  existing_only  production reference: new series = 0
  B  arrival        A + account-level arrival layer (rows added per origin x account x week with actual 0)
  C  plan_analog    A + per-series forecasts for the actual new series (oracle launch timing)
LEVELS: cell x week (A vs C only; B has no cells) · account x month · portfolio x month, plus portfolio bias;
BY HISTORY BAND (<13 / 13-25 / 26-51 / 52+ wks, plus new / lapsed / low-TDP); with and without Walmart;
recent origins (2025-12 on), all 18, and 2025. New-series-only accuracy for C at series x month.
Only information before each forecast date is used for curves, analog velocities and arrival rates.

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1 B moves the recent portfolio x month bias closer to 1 than A, into 0.93-1.07.
     (fails -> the arrival layer does not carry over to the corrected bench)
  P2 B changes recent account x month error by less than 1.0 point vs A (either direction).
     (fails upward -> account-level arrivals hurt; fails downward -> they help more than MO_91 found)
  P3 C lowers recent account x month error by at least 1.0 point vs A and is better on at least 4 of 6 recent
     origins. (fails -> even a launch calendar would not help monthly account accuracy much)
  P4 For the new series themselves, C's series x month miss is below 70% (recent origins).
  P5 Without Walmart, C still lowers recent account x month error vs A (Walmart does not decide it).
Output: outputs/mo144_new_series.json, scripts/outputs/mo144_rows.parquet
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import MO_80_quarterly_honest_backtest as M
importlib.reload(M)
assert M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

ROWS = Path("outputs/mo140_rows.parquet")
PANEL = Path("outputs/retailer_sales_weekly.parquet")
OUT_JSON = Path("../outputs/mo144_new_series.json")
OUT_ROWS = Path("outputs/mo144_rows.parquet")
RECENT = "2025-12"
BANDS = [(0, 13, "<13 wks"), (13, 26, "13-25 wks"), (26, 52, "26-51 wks"), (52, 10_000, "52+ wks")]
W = pd.Timedelta(weeks=1)
AGES = 13                       # launch ages 0..12 weeks (a new series is at most 12 weeks old in a horizon)
ARRIVAL_LOOKBACK = 26           # weeks of past launches used for the arrival rate
ARMS = ["existing_only", "arrival", "plan_analog"]


def load():
    r = pd.read_parquet(ROWS)
    r["date"] = pd.to_datetime(r["date"], utc=True)
    G = M.GROUP_COLS
    p = pd.read_parquet(PANEL, columns=G + ["__time", "base_units", "tdp"])
    p["__time"] = pd.to_datetime(p["__time"], utc=True)
    p["series"] = p[G].astype(str).agg(" | ".join, axis=1)
    p = p[p.series.isin(set(r.series))].copy()
    p["base_units"] = p.base_units.fillna(0)
    sold = p[p.base_units > 0]
    launch = sold.groupby("series").__time.min().rename("launch")
    p = p.merge(launch, on="series")
    p["age"] = ((p.__time - p.launch).dt.days // 7).astype(int)
    meta = p.drop_duplicates("series").set_index("series")[["upc", "channel_outlet", "retail_account"]]
    return r, p, launch, meta


def curves(p: pd.DataFrame, cut) -> dict:
    """Launch statistics from weeks <= cut only (ages 0..12)."""
    h = p[(p.__time <= cut) & (p.age.between(0, AGES - 1))].copy()
    h["vel"] = np.where(h.tdp > 0, h.base_units / h.tdp, np.nan)
    c = {}
    c["units_acct"] = h.groupby(["retail_account", "age"]).base_units.mean()
    c["units_chan"] = h.groupby(["channel_outlet", "age"]).base_units.mean()
    c["units_all"] = h.groupby("age").base_units.mean()
    c["tdp_acct"] = h.groupby(["retail_account", "age"]).tdp.median()
    c["tdp_chan"] = h.groupby(["channel_outlet", "age"]).tdp.median()
    c["vel_upc_chan"] = h.groupby(["upc", "channel_outlet", "age"]).vel.mean()
    c["vel_upc"] = h.groupby(["upc", "age"]).vel.mean()
    return c


def get(s: pd.Series, key, default=np.nan):
    try:
        v = s.loc[key]
        return float(v) if np.isfinite(v) else default
    except KeyError:
        return default


def plan_forecast(c, upc, chan, acct, age) -> tuple[float, str]:
    v = get(c["vel_upc_chan"], (upc, chan, age))
    if not np.isfinite(v):
        v = get(c["vel_upc"], (upc, age))
    t = get(c["tdp_acct"], (acct, age))
    if not np.isfinite(t):
        t = get(c["tdp_chan"], (chan, age))
    if np.isfinite(v) and np.isfinite(t):
        return v * t, "analog"
    for key, s in (((acct, age), c["units_acct"]), ((chan, age), c["units_chan"]), (age, c["units_all"])):
        u = get(s, key)
        if np.isfinite(u):
            return u, "curve"
    return 0.0, "none"


def main() -> None:
    r, p, launch, meta = load()
    cuts = {lbl: M._utc(c) for lbl, c, *_ in M.ORIGINS_MONTHLY}
    r["existing_only"] = r["direct_avg5"]
    r["arrival"] = r["direct_avg5"]
    r["plan_analog"] = r["direct_avg5"]
    r["plan_source"] = ""
    synth = []
    for o, cut in cuts.items():
        c = curves(p, cut)
        # C: new series rows (is_new) at this origin, oracle launch week
        idx = r.index[(r.origin == o) & r.is_new]
        for i in idx:
            s = r.at[i, "series"]
            if s not in meta.index or s not in launch.index:
                continue
            age = int((r.at[i, "date"] - launch[s]).days // 7)
            if age < 0:
                f, src = 0.0, "pre-launch"
            else:
                m = meta.loc[s]
                f, src = plan_forecast(c, m.upc, m.channel_outlet, m.retail_account, min(age, AGES - 1))
            r.at[i, "plan_analog"], r.at[i, "plan_source"] = f, src
        # B: arrival layer per account x horizon week
        recent_launch = launch[(launch > cut - ARRIVAL_LOOKBACK * W) & (launch <= cut)]
        rate = meta.loc[recent_launch.index].groupby("retail_account").size() / ARRIVAL_LOOKBACK
        dates = sorted(r[r.origin == o].date.unique())
        acct_wmt = r[r.origin == o].drop_duplicates("account").set_index("account").wmt
        for acct, lam in rate.items():
            chan = meta[meta.retail_account == acct].channel_outlet.mode().iloc[0]
            for k, d in enumerate(dates):            # horizon week k = 0..12; launches at weeks j <= k
                tot = 0.0
                for j in range(k + 1):
                    age = k - j
                    u = get(c["units_acct"], (acct, age))
                    if not np.isfinite(u):
                        u = get(c["units_chan"], (chan, age), get(c["units_all"], age, 0.0))
                    tot += lam * u
                synth.append({"origin": o, "series": f"ARRIVAL | {acct}", "account": acct, "date": d, "actual": 0.0,
                              "is_new": True, "band": "new", "hist_wks": 0, "wmt": bool(acct_wmt.get(acct, False)),
                              "existing_only": 0.0, "arrival": tot, "plan_analog": 0.0, "plan_source": "arrival-row"})
    s = pd.DataFrame(synth)
    s["date"] = pd.to_datetime(s["date"], utc=True)
    allr = pd.concat([r, s], ignore_index=True)
    allr.to_parquet(OUT_ROWS)

    res = {"arms": ARMS, "plan_source_counts": r[r.is_new].plan_source.value_counts().to_dict(),
           "new_share_of_actual": {}}
    CW, AM, PM = "cell x week", "account x month", "portfolio x month"
    for scope, sub0 in (("with Walmart", allr), ("without Walmart", allr[~allr.wmt.astype(bool)])):
        res[scope] = {}
        for name, sub in (("recent", sub0[sub0.origin >= RECENT]), ("all", sub0), ("2025", sub0[sub0.origin < RECENT])):
            Sx = M.score_levels(sub, ARMS)
            res[scope][name] = Sx
            nw = sub[sub.is_new & ~sub.series.str.startswith("ARRIVAL")].actual.sum() / sub.actual.sum()
            res["new_share_of_actual"][f"{scope}/{name}"] = float(nw)
            print(f"\n=== {scope.upper()}, {name.upper()} origins, ALL volume (new series share of actual {100 * nw:.1f}%): "
                  f"am / pm | bias  (cw for A and C only) ===")
            for x in ARMS:
                cw = "   n/a" if x == "arrival" else f"{Sx[CW][x]:6.2f}"
                print(f"  {x:<14s} cw {cw}  am {Sx[AM][x]:6.2f}  pm {Sx[PM][x]:6.2f}   bias {Sx['portfolio_bias'][x]:.3f}")
            if scope == "with Walmart":
                for lvl in (AM, PM):
                    print(f"  BY HISTORY BAND, {lvl} (<13 / 13-25 / 26-51 / 52+ wks, new, lapsed, low-TDP)")
                    for b, v in Sx[lvl]["by_band"].items():
                        print(f"    {b:<10s} n={v['n']:>6,}  " + "  ".join(f"{x}={v[x]:.1f}" for x in ARMS))

    # per-origin account x month, recent
    rec = allr[allr.origin >= RECENT]
    per = {}
    for o, g in rec.groupby("origin"):
        Sx = M.score_levels(g, ARMS)
        per[o] = {x: Sx[AM][x] for x in ARMS}
    res["per_origin_am_recent"] = per
    print("\nPER-ORIGIN account x month (recent):")
    for o, v in per.items():
        print(f"  {o}: " + "  ".join(f"{x}={v[x]:.2f}" for x in ARMS))

    # new series only, series x month (C vs actual), recent
    nr = r[(r.origin >= RECENT) & r.is_new].copy()
    nr["month"] = nr.date.dt.tz_localize(None).dt.to_period("M").astype(str)
    sm = nr.groupby(["origin", "series", "month"])[["actual", "plan_analog"]].sum()
    new_miss = float(100 * (sm.plan_analog - sm.actual).abs().sum() / sm.actual.sum())
    new_bias = float(sm.plan_analog.sum() / sm.actual.sum())
    res["new_series_only_recent"] = {"series_x_month_miss_pct": new_miss, "bias": new_bias}
    print(f"\nNEW SERIES ONLY (recent), C plan_analog: series x month miss {new_miss:.1f}%, bias {new_bias:.3f}")
    print("plan sources:", res["plan_source_counts"])

    R = res["with Walmart"]["recent"]
    Rx = res["without Walmart"]["recent"]
    bA, bB = R["portfolio_bias"]["existing_only"], R["portfolio_bias"]["arrival"]
    wins = sum(v["plan_analog"] < v["existing_only"] for v in per.values())
    preds = {
        "P1": {"bias_A": bA, "bias_B": bB, "holds": bool(abs(bB - 1) < abs(bA - 1) and 0.93 <= bB <= 1.07)},
        "P2": {"am_A": R[AM]["existing_only"], "am_B": R[AM]["arrival"],
               "holds": bool(abs(R[AM]["arrival"] - R[AM]["existing_only"]) < 1.0)},
        "P3": {"am_A": R[AM]["existing_only"], "am_C": R[AM]["plan_analog"], "wins": wins,
               "holds": bool(R[AM]["existing_only"] - R[AM]["plan_analog"] >= 1.0 and wins >= 4)},
        "P4": {"new_series_miss": new_miss, "holds": bool(new_miss < 70)},
        "P5": {"am_A_exWMT": Rx[AM]["existing_only"], "am_C_exWMT": Rx[AM]["plan_analog"],
               "holds": bool(Rx[AM]["plan_analog"] < Rx[AM]["existing_only"])},
    }
    res["predictions"] = preds
    OUT_JSON.write_text(json.dumps(res, indent=2, default=float))
    print()
    for k, v in preds.items():
        print(k, "HOLDS" if v["holds"] else "FAILS", {kk: (round(vv, 3) if isinstance(vv, float) else vv)
                                                    for kk, vv in v.items() if kk != "holds"})


if __name__ == "__main__":
    main()
