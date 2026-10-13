#!/usr/bin/env python
"""MO_141 - forecasting the four data-dark retailers from billed shipments (NetSuite), monthly.

PLAIN WORDS: WinCo, ALDI, H-E-B and Trader Joe's have no SPINS or Circana store sales, only BUILT's billed
shipments to them (docs/Shipment Data.xlsx, 4,681 billed sales-order lines, Jan 2023 - Sep 11 2026). For these
accounts the forecast target is bars shipped per month (sell-in, which is also what drives BUILT revenue).
Orders are lumpy (truckloads, replenishment orders, sometimes to a distributor), so this tests simple, explainable
monthly methods by backtest:
  last_month      next months = last full month
  avg3, avg6      next months = average of the last 3 / 6 full months
  seasonal_trend  same month last year x (last 3 months / same 3 months last year), capped 0.5-2.0
  replenish       orders per month over the last 6 months x median bars per order over the last 6 months
Each forecast date ("origin") is the first day of a month from 2024-07 to 2026-06; horizons are the next 3 months.
Scored at account x month and on the 3-month total (lumpy orders make single months noisy), as average miss %
(sum |forecast - actual| / sum actual), plus bias (forecast / actual). Product lines: only shipped product lines
(itemtype Assembly / InvtPart, TotalBars > 0); allowance, discount and non-inventory lines are excluded.
Out of scope here: item-level forecasts, open orders (not available), distributor routing.
Outputs: scripts/outputs/mo141/*.csv + summary.json

PREDICTIONS (written 2026-10-13, before any run):
  P1 WinCo (the steadiest account): avg3 has a lower account x month miss % than last_month, and is better on at
     least 60% of origins.
  P2 For every account, every method misses less on the 3-month total than on single months.
  P3 ALDI and H-E-B: replenish has a lower 3-month-total miss % than avg3.
  P4 Bias: avg6 under-forecasts (bias < 1) for WinCo, because WinCo's shipments grew over 2023-2026.
  No prediction for seasonal_trend or Trader Joe's (62 lines; too few orders to judge).

MO_141b (--corrected; added 2026-10-13 after the skeptic review, applying its corrections; NO new predictions --
it re-states the numbers the corrections imply, from committed code):
  - each account is scored and forecast only from its "regular since" month: the first month of its first run of
    3+ consecutive months with shipments (ALDI's Oct-Nov 2023 test order and H-E-B's ramp are not zero-filled history);
    a forecast date needs 3 regular months before it;
  - August 2026 is dropped (H-E-B's last shipment Aug 17, WinCo's Aug 26: likely incomplete);
  - replenish is dropped (it equals avg6 x median/mean order size, so it under-forecasts by construction; P3 untested);
  - seasonal_trend is marked not applicable where there is no prior regular year;
  - Trader Joe's is excluded (June 2026 = one-time load-in: 2.52M bars, 27 orders in 9 days to 6 DCs);
  - adds the median per-origin miss next to the pooled miss (WinCo's ranking flips between them).
"""
from __future__ import annotations

# protocol: not-a-forecast-arm (shipments are a separate target from the SPINS forecast harness; predictions above)
import json
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path("../docs/Shipment Data.xlsx")
OUT = Path("outputs/mo141")
ORIGINS = pd.date_range("2024-07-01", "2026-06-01", freq="MS")
H = 3
LAST_FULL = pd.Timestamp("2026-08-01")   # September 2026 is partial (data to Sep 11)
SHORT = {"Winco": "WinCo", "ALDI Grocery": "ALDI", "H-E-B": "H-E-B", "Trader Joe's Company": "Trader Joe's"}


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    d = pd.read_excel(SRC)
    d["ship_date"] = pd.to_datetime(d.ship_date)
    d = d[d.itemtype.isin(["Assembly", "InvtPart"]) & (d.TotalBars > 0)].copy()
    d["account"] = d.customer_name.map(SHORT)
    d["month"] = d.ship_date.dt.to_period("M").dt.to_timestamp()
    monthly = d.groupby(["account", "month"]).TotalBars.sum().unstack(0).reindex(
        pd.date_range(d.month.min(), LAST_FULL, freq="MS")).fillna(0)
    orders = d.groupby(["account", "SalesOrdersID"]).agg(month=("month", "min"), bars=("TotalBars", "sum")).reset_index()
    return monthly, orders


def forecast(monthly: pd.Series, orders: pd.DataFrame, origin) -> dict[str, float]:
    """Per-month forecast for the H months starting at origin, using only months before origin."""
    hist = monthly[monthly.index < origin]
    last3, last6 = hist.iloc[-3:], hist.iloc[-6:]
    f = {"last_month": hist.iloc[-1], "avg3": last3.mean(), "avg6": last6.mean()}
    ly = monthly.reindex(pd.date_range(origin - pd.DateOffset(months=12), periods=H, freq="MS")).fillna(0)
    ly3 = monthly.reindex(pd.date_range(origin - pd.DateOffset(months=15), periods=3, freq="MS")).fillna(0).sum()
    trend = np.clip(last3.sum() / ly3, 0.5, 2.0) if ly3 > 0 else 1.0
    f["seasonal_trend"] = list(ly.values * trend) if ly.sum() > 0 else [last3.mean()] * H
    o = orders[(orders.month < origin) & (orders.month >= origin - pd.DateOffset(months=6))]
    f["replenish"] = (len(o) / 6) * o.bars.median() if len(o) else 0.0
    return {k: (v if isinstance(v, list) else [v] * H) for k, v in f.items()}


def regular_since(s: pd.Series):
    pos = (s > 0).astype(int)
    run = pos.groupby((pos == 0).cumsum()).cumsum()
    hit = run[run >= 3]
    return hit.index[0] - pd.DateOffset(months=2) if len(hit) else None


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--corrected", action="store_true", help="MO_141b corrections (see docstring)")
    corrected = ap.parse_args().corrected
    global OUT, LAST_FULL
    if corrected:
        OUT, LAST_FULL = Path("outputs/mo141b"), pd.Timestamp("2026-07-01")
    OUT.mkdir(parents=True, exist_ok=True)
    monthly, orders = load()
    rows, starts = [], {}
    for acct in monthly.columns:
        s, o = monthly[acct], orders[orders.account == acct]
        if corrected:
            if acct == "Trader Joe's":
                continue
            st = regular_since(s[s.index <= LAST_FULL])
            starts[acct] = str(st.date()) if st is not None else None
            if st is None:
                continue
            s, o = s[s.index >= st], o[o.month >= st]
        for origin in ORIGINS:
            months = pd.date_range(origin, periods=H, freq="MS")
            if months[-1] > LAST_FULL or s[s.index < origin].sum() == 0:
                continue
            if corrected and (s.index < origin).sum() < 3:
                continue
            fc = forecast(s, o, origin)
            if corrected:
                fc.pop("replenish")
                if (s.index < origin - pd.DateOffset(months=12)).sum() == 0:
                    fc.pop("seasonal_trend")
            for m_i, m in enumerate(months):
                for meth, vals in fc.items():
                    rows.append({"account": acct, "origin": origin, "month": m, "h": m_i + 1, "method": meth,
                                 "forecast": float(vals[m_i]), "actual": float(s[m])})
    r = pd.DataFrame(rows)
    r.to_csv(OUT / "forecasts.csv", index=False)

    def miss(g):
        return 100 * (g.forecast - g.actual).abs().sum() / g.actual.sum() if g.actual.sum() > 0 else np.nan
    am = r.groupby(["account", "method"]).apply(miss).rename("month_miss_pct")
    tot = r.groupby(["account", "method", "origin"])[["forecast", "actual"]].sum().reset_index()
    tm = tot.groupby(["account", "method"]).apply(miss).rename("total3_miss_pct")
    bias = r.groupby(["account", "method"]).apply(lambda g: g.forecast.sum() / g.actual.sum()).rename("bias")
    summ = pd.concat([am, tm, bias], axis=1).reset_index()
    summ.to_csv(OUT / "scores.csv", index=False)
    po = r.groupby(["account", "method", "origin"]).apply(miss).unstack("method")
    po.to_csv(OUT / "per_origin_month_miss.csv")
    hist = monthly.copy()
    hist.to_csv(OUT / "monthly_bars.csv")

    if corrected:
        med = po.stack().groupby(level=["account", "method"]).median().rename("median_origin_month_miss_pct")
        n = r.groupby(["account", "method"]).origin.nunique().rename("origins")
        summ = summ.merge(med.reset_index(), on=["account", "method"]).merge(n.reset_index(), on=["account", "method"])
        summ.to_csv(OUT / "scores.csv", index=False)
        (OUT / "summary.json").write_text(json.dumps({"regular_since": starts, "last_month_scored": str(LAST_FULL.date())}, indent=2))
        pd.set_option("display.width", 200)
        print("regular since:", starts)
        print(summ.round(2).to_string())
        return
    s = summ.set_index(["account", "method"])
    w = po.loc["WinCo"]
    p1_share = float((w["avg3"] < w["last_month"]).mean())
    preds = {
        "P1": {"winco_avg3": s.loc[("WinCo", "avg3"), "month_miss_pct"], "winco_last": s.loc[("WinCo", "last_month"), "month_miss_pct"],
               "share_origins_better": p1_share,
               "holds": bool(s.loc[("WinCo", "avg3"), "month_miss_pct"] < s.loc[("WinCo", "last_month"), "month_miss_pct"] and p1_share >= 0.6)},
        "P2": {"violations": [f"{a}/{m}" for (a, m), x in s.iterrows() if not x.total3_miss_pct < x.month_miss_pct],
               "holds": bool((s.total3_miss_pct < s.month_miss_pct).all())},
        "P3": {a: {"replenish": s.loc[(a, "replenish"), "total3_miss_pct"], "avg3": s.loc[(a, "avg3"), "total3_miss_pct"]}
               for a in ("ALDI", "H-E-B")},
        "P4": {"winco_avg6_bias": s.loc[("WinCo", "avg6"), "bias"], "holds": bool(s.loc[("WinCo", "avg6"), "bias"] < 1)},
    }
    preds["P3"]["holds"] = bool(all(v["replenish"] < v["avg3"] for k, v in preds["P3"].items() if k != "holds"))
    (OUT / "summary.json").write_text(json.dumps({"origins": [str(o.date()) for o in ORIGINS], "predictions": preds},
                                                 indent=2, default=float))
    pd.set_option("display.width", 200)
    print("monthly bars, last 12 full months:\n", monthly.tail(12).round(0).to_string())
    print(summ.round(2).to_string())
    for k, v in preds.items():
        print(k, "HOLDS" if v["holds"] else "FAILS", {kk: vv for kk, vv in v.items() if kk != "holds"})


if __name__ == "__main__":
    main()
