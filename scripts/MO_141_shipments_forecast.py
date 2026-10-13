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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    monthly, orders = load()
    rows = []
    for acct in monthly.columns:
        s, o = monthly[acct], orders[orders.account == acct]
        for origin in ORIGINS:
            months = pd.date_range(origin, periods=H, freq="MS")
            if months[-1] > LAST_FULL or s[s.index < origin].sum() == 0:
                continue
            fc = forecast(s, o, origin)
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
