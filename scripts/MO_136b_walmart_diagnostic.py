#!/usr/bin/env python
"""MO_136b - Why does Walmart decide the model comparisons? (diagnostic on existing results; no training)

WHERE THIS CAME FROM
--------------------
MO_136 skeptic (2026-10-12): Walmart (27% of recent volume, one account, 38 item series at WALMART CORP - RMA,
counted once) decides the category signals' portfolio gain, the all-signals consistency failure (5/6 without
Walmart) and the seasonal-bias failure (1.073 without Walmart vs 1.1019 with). Jason asked for the Walmart look
before further signal tests.

HYPOTHESES, WRITTEN BEFORE LOOKING
  H1 Walmart's error is concentrated in a few large series (top 5 series > 50% of Walmart's absolute error).
  H2 Walmart's large misses line up with distribution changes (store count / TDP jumps of 20%+ in the forecast
     window: resets or new items), which no model can see from history.
  H3 The models differ more at Walmart than elsewhere (the spread between models' account-month errors is larger
     at Walmart than at the average account).
  H4 Walmart is over-forecast in Oct-Dec 2025 (bias > 1.10) by the direct models, and that is what pushes the
     portfolio Oct-Dec bias past the limit.

Inputs: scripts/outputs/mo136_rows.parquet (actual, flat, L4W, direct seeds, all-signal seeds),
scripts/outputs/mo135_rows.parquet (served direct, recursive), scripts/outputs/retailer_sales_weekly.parquet (TDP).
Output: scripts/outputs/mo136b_walmart.json and the printed tables.
"""
from __future__ import annotations

# protocol: not-a-forecast-arm (diagnostic on stored forecasts; no model is trained)
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("outputs/mo136b_walmart.json")
MODELS = ["flat", "conn_L4W", "direct_served", "rec", "direct_avg5", "all_avg5"]
RECENT = "2025-12"


def load() -> pd.DataFrame:
    a = pd.read_parquet("outputs/mo136_rows.parquet")
    a["direct_avg5"] = a[[f"direct_fixed_s{k}" for k in (42, 1, 2, 3, 4)]].mean(axis=1)
    a["all_avg5"] = a[[f"all_s{s}" for s in (42, 1, 2, 3, 4)]].mean(axis=1)
    b = pd.read_parquet("outputs/mo135_rows.parquet")[["origin", "series", "date", "direct_served", "rec"]]
    b["date"] = pd.to_datetime(b["date"], utc=True)
    a = a.merge(b, on=["origin", "series", "date"], how="left")
    assert a[["direct_served", "rec"]].notna().all().all()
    a = a[~a["is_new"]].copy()
    a["wmt"] = a["account"].str.upper().eq("WALMART")
    a["month"] = a["date"].dt.to_period("M").astype(str)
    a["upc"] = a["series"].str.split(" \\| ").str[0]
    return a


def err(d: pd.DataFrame, m: str) -> float:
    return 100 * np.abs(d["actual"] - d[m]).sum() / d["actual"].sum()


def acct_month(d: pd.DataFrame) -> pd.DataFrame:
    return d.groupby(["origin", "account", "month", "wmt"], as_index=False)[["actual"] + MODELS].sum()


def main() -> None:
    a = load()
    res: dict = {}
    for name, sub in (("recent", a[a.origin >= RECENT]), ("2025", a[a.origin < RECENT])):
        print(f"\n=== {name.upper()} forecast dates ===")
        vol = sub.groupby("wmt")["actual"].sum()
        print(f"Walmart share of actual volume: {vol[True] / vol.sum():.3f}")
        rows = []
        am = acct_month(sub)
        for m in MODELS:
            ae = np.abs(sub["actual"] - sub[m])
            share_err = ae[sub.wmt].sum() / ae.sum()
            rows.append({"model": m, "item_week_wmt": err(sub[sub.wmt], m), "item_week_rest": err(sub[~sub.wmt], m),
                         "acct_month_wmt": err(am[am.wmt], m), "acct_month_rest": err(am[~am.wmt], m),
                         "wmt_share_of_item_err": share_err,
                         "bias_wmt": sub.loc[sub.wmt, m].sum() / sub.loc[sub.wmt, "actual"].sum(),
                         "bias_rest": sub.loc[~sub.wmt, m].sum() / sub.loc[~sub.wmt, "actual"].sum()})
        t = pd.DataFrame(rows).set_index("model")
        print("average miss % (item x week, account x month), Walmart vs the other accounts; bias = forecast/actual")
        print(t.round(3).to_string())
        # H3: spread between models at the account-month level, Walmart vs the typical account
        spread = am.assign(spread=am[MODELS].sub(am["actual"], axis=0).abs().max(axis=1)
                           - am[MODELS].sub(am["actual"], axis=0).abs().min(axis=1))
        sw = spread.groupby("wmt").apply(lambda d: d["spread"].sum() / d["actual"].sum() * 100)
        print(f"H3 model spread (max-min abs error, % of actual) at account x month: Walmart {sw[True]:.1f} vs rest {sw[False]:.1f}")
        # per-origin Walmart account-month error by model
        po = am[am.wmt].groupby("origin").apply(lambda d: pd.Series({m: err(d, m) for m in MODELS}))
        print("Walmart account x month miss % by forecast date:")
        print(po.round(1).to_string())
        # H1: concentration of Walmart error in series (direct_avg5)
        wm = sub[sub.wmt]
        se = wm.assign(ae=np.abs(wm["actual"] - wm["direct_avg5"])).groupby("upc").agg(
            abs_err=("ae", "sum"), actual=("actual", "sum")).sort_values("abs_err", ascending=False)
        top5 = se["abs_err"].head(5).sum() / se["abs_err"].sum()
        print(f"H1 top-5 Walmart items' share of Walmart absolute error (direct_avg5): {top5:.2f}; "
              f"their share of Walmart volume: {se['actual'].head(5).sum() / se['actual'].sum():.2f}")
        print(se.head(8).assign(miss_pct=lambda d: 100 * d.abs_err / d.actual).round(1).to_string())
        res[name] = {"table": t.round(4).to_dict(), "spread": {"walmart": float(sw[True]), "rest": float(sw[False])},
                     "per_origin": po.round(3).to_dict(), "top5_err_share": float(top5),
                     "top_items": se.head(8).round(1).to_dict()}
    # H4: Oct-Dec 2025 bias, Walmart vs rest, by model
    od = a[(a.date >= "2025-10-01") & (a.date < "2026-01-01")]
    h4 = {m: {"walmart": od.loc[od.wmt, m].sum() / od.loc[od.wmt, "actual"].sum(),
              "rest": od.loc[~od.wmt, m].sum() / od.loc[~od.wmt, "actual"].sum(),
              "all": od[m].sum() / od["actual"].sum()} for m in MODELS}
    print("\nH4 Oct-Dec 2025 bias (forecast/actual), all forecast dates covering those weeks:")
    print(pd.DataFrame(h4).T.round(3).to_string())
    res["oct_dec_2025_bias"] = h4
    # H2: Walmart TDP jumps vs big misses (forecast window weeks where store count moved 20%+ from the cutoff)
    p = pd.read_parquet("outputs/retailer_sales_weekly.parquet", columns=["__time", "upc", "retail_account", "tdp", "base_units"])
    p = p[p.retail_account.str.upper().eq("WALMART")].copy()
    p["date"] = pd.to_datetime(p["__time"], utc=True)
    tdp = p.groupby(["upc", "date"])["tdp"].sum()
    wm = a[a.wmt].copy()
    wm["tdp_now"] = [tdp.get((u, d), np.nan) for u, d in zip(wm.upc, wm.date)]
    cut = {o: pd.Timestamp(o + "-01", tz="UTC") for o in wm.origin.unique()}
    last = p.sort_values("date").groupby("upc")
    wm["tdp_cut"] = [tdp[u][tdp[u].index < cut[o]].iloc[-1] if u in tdp.index.get_level_values(0)
                     and (tdp[u].index < cut[o]).any() else np.nan for u, o in zip(wm.upc, wm.origin)]
    wm["tdp_move"] = wm["tdp_now"] / wm["tdp_cut"] - 1
    wm["ae"] = np.abs(wm["actual"] - wm["direct_avg5"])
    big = wm["tdp_move"].abs() >= 0.20
    print(f"\nH2 Walmart item-weeks whose store count moved 20%+ from the forecast date: {big.mean():.2f} of rows, "
          f"{wm.loc[big, 'actual'].sum() / wm['actual'].sum():.2f} of volume, "
          f"{wm.loc[big, 'ae'].sum() / wm['ae'].sum():.2f} of Walmart's absolute error (direct_avg5)")
    res["h2"] = {"rows": float(big.mean()), "volume": float(wm.loc[big, "actual"].sum() / wm["actual"].sum()),
                 "abs_err": float(wm.loc[big, "ae"].sum() / wm["ae"].sum())}
    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
