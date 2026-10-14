#!/usr/bin/env python
"""MO_150 - Does BUILT's trade promotion calendar improve forecasts of TOTAL units (base + promotion lift)?

PLAIN WORDS: the forecast model predicts base units (sales with promotion lift removed), so a promotion calendar
cannot improve it by design. Finance plans with total units, though, which include promotion weeks. This tests a
"planned promotion lift" layer on top of the base forecast, using BUILT's trade promotion calendar (Brian's file,
loaded to Druid as built_trade_promotions: 890 promotions, Dec 2024 - Jan 2027, mostly retailer price reductions):
  1. Alignment: in the weeks the calendar says an item is on promotion at a retailer, do SPINS sales show it?
  2. Total-units forecasts, scored on the same honest test rows (forecast made at each date with only information
     up to it, except the calendar itself; see caveat):
       base_only        base forecast (direct_avg5), no promotion lift
       avg_uplift       base x (1 + the item's average uplift over the last 26 weeks); no calendar
       calendar_lift    base x (1 + the item's average NON-promotion-week uplift) in other weeks, and
                        base x (1 + the item's typical promotion-week lift x share of the week on promotion) in
                        calendar promotion weeks
Partial weeks: SPINS weeks end on Sunday; a promotion covering part of a week counts by the share of days covered
(Jason, 2026-10-12: promotions often run midweek to midweek).

WHERE THIS CAME FROM: plan approved by Jason 2026-10-14 (step 3); SIGNAL_REGISTER row 12 (trade calendar as a
known-future input: untested); forecast to be presented before 2026-12-06, and finance plans in total units.

PRIOR WORK (docs/SETTLED_FINDINGS.md, README, memory; scout 2026-10-14)
  - MO_73 (SETTLED/PROVISIONAL): lift ladder by discount depth (<10% ~20%, 10-20% ~31%, 20-30% ~46%, 30%+ ~76%).
  - MO_70: promotion lift under-predicted ~2x (structural); MO_58: SPINS units vs base_units semantics.
  - Memory (project_trade_vs_consumer_promo): Brian's calendar is trade commitments, not confirmed shelf
    promotions; do not use it as a hard promo flag -> here it is weighted and checked for alignment first.
  - SIGNAL_REGISTER row 12: "Untested; 61.6% of events ran off-schedule (older)". Not a base-model input test
    (base units exclude promotion lift by design); MO_54 holiday flags rejected (not related).
  - History bands: results are reported BY HISTORY BAND like every forecast arm.
CAVEAT (look-ahead): only the 2026-09-30 snapshot of the calendar exists, so backtests use promotions as recorded
then, including any entered after a forecast date. Results are an upper bound on what the calendar adds.

MAPPING: promotion customer -> SPINS geography through built_customer_bridge (retailer or BUILT customer name ->
spins_customer = geography_raw); product group -> line and pack: 'Puff 1CT' -> PUFF + SOUR PUFF singles,
'Puff 4CT' -> 4-packs, 'Puff 12CT' -> 12-packs, 'Bar 1CT' / 'Bar 4CT' -> BAR; shippers and club packs unmapped.
Distributor-level promotions that do not name a retailer are not mapped (reported).
LEVELS: cell x week, account x month, portfolio x month, bias, BY HISTORY BAND; recent (2025-12+), all, 2025;
all existing series and the subset of series the calendar covers.

PREDICTIONS, RECORDED BEFORE ANY RUN:
  P1 Alignment: for at least 60% of mapped promotions, SPINS promotion share of units on the covered series is
     higher in the promotion's weeks than in the 8 weeks before it.
  P2 On series the calendar covers, calendar_lift beats avg_uplift at recent account x month on total units.
  P3 avg_uplift beats base_only on total units by at least 3 points at recent account x month (all series).
  P4 calendar_lift's recent portfolio bias on total units is within 0.93-1.07 (all series).
Output: outputs/mo150_promo_layer.json, scripts/outputs/mo150_rows.parquet, scripts/outputs/mo150_promos.parquet
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"
import MO_80_quarterly_honest_backtest as M          # import asserts forecast + training parity
importlib.reload(M)
assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"
from mo_druid_client import query_druid

ROWS = Path("outputs/mo140_rows.parquet")
PANEL = Path("outputs/retailer_sales_weekly.parquet")
PROMOS = Path("outputs/mo150_promos.parquet")
RECENT = "2025-12"
ARMS = ["base_only", "avg_uplift", "calendar_lift"]
CW, AM, PM = "cell x week", "account x month", "portfolio x month"
PG = {"Puff 1CT": (("BUILT PUFF", "BUILT SOUR PUFF"), 1), "Puff 4CT": (("BUILT PUFF", "BUILT SOUR PUFF"), 4),
      "Puff 12CT": (("BUILT PUFF", "BUILT SOUR PUFF"), 12), "Bar 1CT": (("BUILT BAR", "BUILT"), 1),
      "Bar 4CT": (("BUILT BAR", "BUILT"), 4)}
W = pd.Timedelta(weeks=1)


def load_promos() -> pd.DataFrame:
    if PROMOS.exists():
        return pd.read_parquet(PROMOS)
    d = query_druid("""SELECT customer, promotion_id, promotion_status, promotion_start_date, promotion_end_date,
                       tactic, product_group, discount_pct, planned_lift_pct FROM built_trade_promotions""", timeout=300)
    cb = query_druid("SELECT retailer, built_customer, spins_customer FROM built_customer_bridge", timeout=300)
    d["start"] = pd.to_datetime(d.promotion_start_date, errors="coerce")
    d["end"] = pd.to_datetime(d.promotion_end_date, errors="coerce")
    by_ret = cb.dropna(subset=["spins_customer"]).assign(k=lambda x: x.retailer.str.upper())
    d["k"] = d.customer.str.upper()
    d = d.merge(by_ret[["k", "spins_customer"]].drop_duplicates("k"), on="k", how="left")
    d.to_parquet(PROMOS)
    return d


def week_weights(p: pd.DataFrame, weeks: pd.DatetimeIndex) -> pd.DataFrame:
    """Share of each SPINS week (ending Sunday, covering the 7 days up to it) inside each promotion window."""
    out = []
    for _, r in p.iterrows():
        if pd.isna(r.start) or pd.isna(r.end):
            continue
        for wk in weeks[(weeks >= r.start) & (weeks - pd.Timedelta(days=6) <= r.end)]:
            lo, hi = max(wk - pd.Timedelta(days=6), r.start), min(wk, r.end)
            share = ((hi - lo).days + 1) / 7
            if share > 0:
                out.append({"promotion_id": r.promotion_id, "geo": r.spins_customer, "pg": r.product_group,
                            "week": wk, "share": min(share, 1.0)})
    return pd.DataFrame(out)


def main() -> None:
    promos = load_promos()
    promos = promos[promos.product_group.isin(PG) & ((promos.end - promos.start).dt.days <= 63)]
    mapped = promos[promos.spins_customer.notna()]
    print(f"promotions with a 9-week-or-shorter window and a mapped product group: {promos.promotion_id.nunique()}; "
          f"mapped to a SPINS geography: {mapped.promotion_id.nunique()}")
    G = M.GROUP_COLS
    p = pd.read_parquet(PANEL, columns=G + ["__time", "units", "base_units", "pack_count", "source_brand"])
    p["__time"] = pd.to_datetime(p["__time"], utc=True)
    p["week"] = p["__time"].dt.tz_localize(None)
    p["series"] = p[G].astype(str).agg(" | ".join, axis=1)
    p["u"] = pd.to_numeric(p.units, errors="coerce")
    p["b"] = pd.to_numeric(p.base_units, errors="coerce")
    p["r"] = np.where(p.b > 0, p.u / p.b - 1, np.nan)               # uplift of total over base that week
    weeks = pd.DatetimeIndex(sorted(p.week.unique()))
    ww = week_weights(mapped, weeks)
    # series covered by each promotion: same geography, line and pack
    ser = p.drop_duplicates("series")[["series", "geography_raw", "source_brand", "pack_count"]]
    cov = []
    for (geo, pg), g in ww.groupby(["geo", "pg"]):
        brands, pack = PG[pg]
        s = ser[(ser.geography_raw == geo) & ser.source_brand.astype(str).isin(brands)
                & (pd.to_numeric(ser.pack_count, errors="coerce") == pack)].series
        for sid in s:
            cov.append(g.assign(series=sid))
    cov = pd.concat(cov, ignore_index=True) if cov else pd.DataFrame(columns=["series", "week", "share", "promotion_id"])
    print(f"covered series: {cov.series.nunique()}; promotion-series-weeks: {len(cov):,}")
    # 1. alignment: promotion weeks vs the 8 weeks before
    pr = p.set_index(["series", "week"])["r"]
    align = []
    for pid, g in cov.groupby("promotion_id"):
        inw = [pr.get((s, w), np.nan) for s, w in zip(g.series, g.week)]
        first = g.week.min()
        before = [pr.get((s, first - k * W), np.nan) for s in g.series.unique() for k in range(1, 9)]
        a, b = np.nanmean(inw) if len(inw) else np.nan, np.nanmean(before) if len(before) else np.nan
        if np.isfinite(a) and np.isfinite(b):
            align.append({"promotion_id": pid, "uplift_in": a, "uplift_before": b, "higher": a > b})
    align = pd.DataFrame(align)
    hit = float(align.higher.mean()) if len(align) else np.nan
    print(f"ALIGNMENT: promotions checked {len(align)}; SPINS uplift higher in promotion weeks for {100 * hit:.1f}%; "
          f"median uplift in-window {align.uplift_in.median():.3f} vs before {align.uplift_before.median():.3f}")
    # 2. total-units forecasts on the honest rows
    r = pd.read_parquet(ROWS)
    r["date"] = pd.to_datetime(r["date"], utc=True)
    r = r.merge(p[["series", "__time", "u"]].rename(columns={"__time": "date"}), on=["series", "date"], how="left")
    r["actual_base"] = r["actual"]
    r["actual"] = r["u"].fillna(r["actual_base"])                    # total units
    cuts = {lbl: M._utc(c) for lbl, c, *_ in M.ORIGINS_MONTHLY}
    cw_share = cov.assign(date=pd.to_datetime(cov.week).dt.tz_localize("UTC")).groupby(["series", "date"]).share.max()
    cw_share = {(s, d): v for (s, d), v in cw_share.items()}
    pcal = set(cov.series)
    rows = []
    for o, g in r.groupby("origin"):
        cut = cuts[o]
        h = p[(p.__time <= cut) & (p.__time > cut - 52 * W)]
        h26 = h[h.__time > cut - 26 * W]
        avg_up = h26.groupby("series").r.mean()
        cal_weeks = cov[(pd.to_datetime(cov.week).dt.tz_localize("UTC") <= cut)]
        is_cal = h.set_index(["series", "week"]).index.isin(list(zip(cal_weeks.series, cal_weeks.week)))
        promo_lift = h[is_cal].groupby("series").r.median()
        nonpromo_up = h[~is_cal & (h.__time > cut - 26 * W)].groupby("series").r.mean()
        acct_lift = h[is_cal].assign(acct=h[is_cal].series.str.split(" | ", regex=False).str[2]).groupby("acct").r.median()
        g = g.copy()
        base = g["direct_avg5"].values
        au = g.series.map(avg_up).fillna(0).clip(-0.5, 3).values
        npu = g.series.map(nonpromo_up).fillna(0).clip(-0.5, 3).values
        acct = g.series.str.split(" | ", regex=False).str[2]
        pl = g.series.map(promo_lift).fillna(acct.map(acct_lift)).fillna(0.3).clip(0, 3).values
        share = np.array([cw_share.get((s, d), 0.0) for s, d in zip(g.series, g.date)])
        g["base_only"] = base
        g["avg_uplift"] = base * (1 + au)
        g["calendar_lift"] = base * (1 + npu * (1 - share) + pl * share)
        g["cal_series"] = g.series.isin(pcal)
        rows.append(g)
    r = pd.concat(rows, ignore_index=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    for a in ARMS:
        r[a] = np.where(zero, 0.0, r[a])
    r[["origin", "series", "date", "actual", "actual_base", "account", "band", "is_new", "wmt", "cal_series"] + ARMS] \
        .to_parquet("outputs/mo150_rows.parquet")
    ex = r[~r["is_new"]]
    res = {"arms": ARMS, "alignment": {"checked": int(len(align)), "share_higher": hit},
           "coverage": {"promotions_mapped": int(mapped.promotion_id.nunique()), "series_covered": int(cov.series.nunique())}}
    for scope, sub0 in (("all series", ex), ("calendar series", ex[ex.cal_series])):
        res[scope] = {}
        for nm, sub in (("recent", sub0[sub0.origin >= RECENT]), ("all", sub0), ("2025", sub0[sub0.origin < RECENT])):
            Sx = M.score_levels(sub, ARMS)
            res[scope][nm] = Sx
            print(f"\n=== {scope.upper()}, {nm.upper()} origins, TOTAL units: cw / am / pm | bias ===")
            for x in ARMS:
                print(f"  {x:<14s}{Sx[CW][x]:7.2f}{Sx[AM][x]:7.2f}{Sx[PM][x]:7.2f}   bias {Sx['portfolio_bias'][x]:.3f}")
            if nm == "recent":
                print(f"  BY HISTORY BAND, {AM} (<13 / 13-25 / 26-51 / 52+ wks)")
                for b, v in Sx[AM]["by_band"].items():
                    print(f"    {b:<10s} n={v['n']:>6,}  " + "  ".join(f"{x}={v[x]:.1f}" for x in ARMS))
    RA, RC = res["all series"]["recent"], res["calendar series"]["recent"]
    preds = {
        "P1": {"share_higher": hit, "holds": bool(hit >= 0.6)},
        "P2": {"cal_series_am_calendar": RC[AM]["calendar_lift"], "cal_series_am_avg": RC[AM]["avg_uplift"],
               "holds": bool(RC[AM]["calendar_lift"] < RC[AM]["avg_uplift"])},
        "P3": {"am_avg": RA[AM]["avg_uplift"], "am_base": RA[AM]["base_only"],
               "holds": bool(RA[AM]["base_only"] - RA[AM]["avg_uplift"] >= 3)},
        "P4": {"bias_calendar": RA["portfolio_bias"]["calendar_lift"],
               "holds": bool(0.93 <= RA["portfolio_bias"]["calendar_lift"] <= 1.07)},
    }
    res["predictions"] = preds
    Path("../outputs/mo150_promo_layer.json").write_text(json.dumps(res, indent=2, default=float))
    print()
    for k, v in preds.items():
        print(k, "HOLDS" if v["holds"] else "FAILS", {kk: vv for kk, vv in v.items() if kk != "holds"})


if __name__ == "__main__":
    main()
