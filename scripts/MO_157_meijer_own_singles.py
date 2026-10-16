"""MO_157 - What happened when Meijer itself carried BUILT singles (Oct 2023 - Jun 2024)?
# protocol: not-a-forecast-arm  (descriptive analysis of SPINS sales; no forecasting model is trained or scored)

WHERE THIS CAME FROM: Jason asked (2026-10-16) to double-check the Meijer Singles Addendum claim "Meijer is the only
grocery account that sells BUILT 4-packs with essentially no singles". The check found the claim true for the last 13
weeks but showed that Meijer carried BUILT singles in about 20-25 of its ~280 stores from October 2023 to June 2024,
which the addendum does not mention. Jason approved this analysis of Meijer's own singles period for the addendum.

PRIOR WORK (docs/SETTLED_FINDINGS.md / README; topic words: singles, 1-count, Meijer, checkout, cannibalization):
- MO_142 / MO_143 (README 2026-10-13, skeptic-corrected wording): Target and Walmart singles programs; singles per
  item per store selling per week: typical grocer ~3.3, convenience ~2.0 (Wawa ~4.5), Target ~4.8 (last 13 weeks to
  2026-09-06); singles ~13% more per bar than 4-packs; at Target between none and just under half of singles bars came
  out of 4-packs. None of this used Meijer's own 2023-24 singles period (MO_143 excluded Meijer as a benchmark).
- Reference: no store-level visibility (Brian & Rob, Oct 5): SPINS RMA gives retailer totals and stores selling, not
  which stores. So any effect on Meijer's 4-packs can only be bounded, not measured.

QUESTIONS (Meijer's own stores, SPINS RMA "MEIJER CORP - RMA", BUILT items; source outputs/meijer_v2 cache):
  Q1 How did singles sell: weeks with sales, stores selling (peak / median), items, and singles base units per item per
     store selling per week (the addendum's measure), for the period 2023-10-01 .. 2024-06-30.
  Q2 Which singles items (flavors) sold.
  Q3 Price per bar of singles vs 4-packs at Meijer in the same weeks (base dollars / bars).
  Q4 Bound on any 4-pack effect: singles bars as a share of Meijer's BUILT 4-pack bars in the same weeks; with singles
     in ~9% of stores, the largest possible take from 4-packs is that share x 100%.
  Q5 How it ended: singles stores and units by quarter after June 2024.
  (History bands are not applicable: this is not a forecast arm; results are reported by period instead.)

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1  Meijer singles sold between 1.5 and 5.0 base units per item per store selling per week in Oct 2023 - Jun 2024
      (within the range of today's grocers, convenience chains and Target).
  P2  Singles bars were under 2% of Meijer's BUILT 4-pack bars over the same weeks (too small to detect any 4-pack
      effect in Meijer's account totals).
  P3  Meijer singles cost at least 5% more per bar than its 4-packs in the same weeks.
  P4  No more than 4 different singles items sold at Meijer in the period.
  If P1 fails low, Meijer's own singles test sold below other retailers' rates (relevant to the scenarios); if P2 fails,
  a 4-pack effect could in principle be visible and should be examined before drawing a conclusion.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

SRC = Path("outputs/meijer_v2")
OUT = Path("../outputs/mo157_meijer_own_singles.json")
ACCOUNT = "MEIJER"
START, END = pd.Timestamp("2023-10-01"), pd.Timestamp("2024-06-30")


def load() -> pd.DataFrame:
    b = pd.read_parquet(SRC / "_cache_built.parquet")
    g = pd.read_parquet(SRC / "_cache_geos.parquet")
    b["__time"] = pd.to_datetime(b["__time"])
    for k in ("base_units", "units", "stores_selling", "base_dollars", "dollars", "store_count", "source_pack_count"):
        b[k] = pd.to_numeric(b[k], errors="coerce").fillna(0)
    b["bars"] = b.base_units * b.source_pack_count
    b = b.merge(g[["geography_raw", "retail_account"]], on="geography_raw", how="left")
    return b[b.retail_account == ACCOUNT].copy()


def main() -> None:
    m = load()
    per = m[(m.__time >= START) & (m.__time <= END)]
    s1 = per[(per.source_pack_count == 1) & (per.base_units > 0) & (per.stores_selling > 0)]
    s4 = per[per.source_pack_count == 4]
    stores = m.groupby("__time").store_count.max()
    wk = s1.groupby("__time").agg(bu=("base_units", "sum"), stores=("stores_selling", "max"), items=("upc", "nunique"))
    q1 = {
        "weeks_with_singles_sales": int(wk.shape[0]),
        "weeks_in_period": int(per.__time.nunique()),
        "stores_selling_peak": float(wk.stores.max()), "stores_selling_median": float(wk.stores.median()),
        "meijer_stores_median": float(stores[(stores.index >= START) & (stores.index <= END)].median()),
        "singles_items": int(s1.upc.nunique()),
        "singles_base_units": float(s1.base_units.sum()),
        "per_item_per_store_selling_per_week": float(s1.base_units.sum() / s1.stores_selling.sum()),
    }
    q2 = (s1.groupby(["upc", "description"]).agg(base_units=("base_units", "sum"), weeks=("__time", "nunique"),
                                                   per_store_wk=("base_units", "sum"))
          .reset_index().sort_values("base_units", ascending=False))
    q2["per_store_wk"] = [float(s1[s1.upc == u].base_units.sum() / s1[s1.upc == u].stores_selling.sum()) for u in q2.upc]
    ppb1 = float(s1.base_dollars.sum() / max(s1.bars.sum(), 1))
    ppb4 = float(s4.base_dollars.sum() / max(s4.bars.sum(), 1))
    q3 = {"price_per_bar_singles": ppb1, "price_per_bar_4pk": ppb4, "singles_premium_pct": 100 * (ppb1 / ppb4 - 1)}
    q4 = {"singles_bars": float(s1.bars.sum()), "fourpack_bars": float(s4.bars.sum()),
          "singles_share_of_4pk_bars_pct": 100 * float(s1.bars.sum() / max(s4.bars.sum(), 1)),
          "share_of_stores_with_singles_peak_pct": 100 * q1["stores_selling_peak"] / q1["meijer_stores_median"]}
    after = m[(m.source_pack_count == 1) & (m.base_units > 0)].copy()
    after["q"] = after.__time.dt.to_period("Q").astype(str)
    q5 = (after.groupby("q").agg(weeks=("__time", "nunique"), base_units=("base_units", "sum"),
                                 max_stores=("stores_selling", "max")).reset_index().to_dict("records"))
    preds = {
        "P1 per item per store selling per week 1.5-5.0": {"value": q1["per_item_per_store_selling_per_week"],
                                                           "holds": 1.5 <= q1["per_item_per_store_selling_per_week"] <= 5.0},
        "P2 singles bars < 2% of 4-pack bars": {"value": q4["singles_share_of_4pk_bars_pct"],
                                               "holds": q4["singles_share_of_4pk_bars_pct"] < 2.0},
        "P3 singles >= 5% more per bar": {"value": q3["singles_premium_pct"], "holds": q3["singles_premium_pct"] >= 5.0},
        "P4 <= 4 singles items": {"value": q1["singles_items"], "holds": q1["singles_items"] <= 4},
    }
    res = {"period": [str(START.date()), str(END.date())], "Q1": q1, "Q2": q2.to_dict("records"), "Q3": q3, "Q4": q4,
           "Q5_by_quarter": q5, "predictions": preds}
    OUT.write_text(json.dumps(res, indent=2, default=float))
    print(json.dumps({k: v for k, v in res.items() if k != "Q2"}, indent=2, default=float))
    print("\nQ2 items:\n" + q2.to_string(index=False))
    for k, v in preds.items():
        print(k, "HOLDS" if v["holds"] else "FAILS", round(v["value"], 3))


if __name__ == "__main__":
    main()
