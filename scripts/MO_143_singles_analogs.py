#!/usr/bin/env python
"""MO_143 - singles (1-count) at Meijer: what happened where BUILT added singles to an established 4-pack set.

PLAIN WORDS: Meijer sells BUILT 4-packs but almost no singles, and the proposal is singles at the checkouts.
Every grocery account with BUILT singles had singles first, so none is a fair comparison. The only accounts that
went 4-packs first and then added singles are Target (singles in 10%+ of stores from 2025-10-05), Walmart
(from 2026-01-11) and DECA (military commissaries, from 2024-10-27); Target and Walmart are supercenters like
Meijer. This script answers, from each retailer's own stores (SPINS RMA):
  Q1 rollout  After singles arrived, did the established 4-pack set sell less per store than expected?
              Expected = the 4-pack set's per-store sales before x (a) the change in the rest of the bar category
              at the same retailer, or (b) the change in the same 4-pack items' per-store sales at grocery
              (Food-channel) retailers over the same weeks. Store-count changes of the 4-packs are not counted
              (Walmart expanded stores in Jan 2026). Measured in BARS (a 4-pack = 4 bars) and in regular-price
              dollars, at weeks 2-14, 15-27 and 28-40 after the rollout. Placebo: the same calculation at fake
              rollout dates with no singles change nearby.
  Q2 singles  How singles sold at Target and Walmart: per store per item per week as they ramped, by flavor,
              and price per bar vs the 4-pack.
  Q3 impulse  Convenience stores (singles only; closest to checkout buying): singles per store per item per week
              by flavor and price per bar, vs grocery and supercenter singles.
  Q4 mix      Grocery accounts that carry both: what share of BUILT bars comes from singles.
SPINS does not show where an item sits in the store, so checkout vs aisle cannot be separated anywhere.
Descriptive, not cause and effect. Inputs: MO_142's Druid pulls (scripts/outputs/meijer_v2/_cache_*.parquet,
built_filtered_weekly RMA geographies through 2026-09-06). Outputs: scripts/outputs/mo143/*.csv + summary.json

PREDICTIONS (written 2026-10-13, before any run; two-sided where direction is not known):
  P1 Target, weeks 2-14: the 4-pack set's per-store bar sales are within +/-10% of expected (control a).
  P2 Walmart, weeks 2-14: within +/-15% of expected (control a; the Jan 2026 store expansion adds noise).
  P3 Target singles, weeks 2-14: between 0.3 and 3.0 base units per store selling per item per week.
  P4 Convenience singles sell more per store selling per item per week than grocery (Food) singles (last 13 weeks).
  P5 At Target, singles cost at least 10% more per bar than 4-packs (regular price, last 13 weeks).
  P6 Placebo: median |4-pack per-store change| at fake dates is <= 10% at Target and at Walmart; where it is
     larger, Q1 for that retailer is reported as 'not measurable'.
"""
from __future__ import annotations

# protocol: not-a-forecast-arm (descriptive analysis for the Meijer brief; predictions above, written before running)
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path("outputs/meijer_v2")
OUT = Path("outputs/mo143")
ANALOGS = {"TARGET CORP - RMA": "Target", "WALMART CORP - RMA": "Walmart", "DECA CONUS - RMA": "DECA"}
W = pd.Timedelta(weeks=1)
PRE = 13
WINDOWS = ((2, 14), (15, 27), (28, 40))
L13 = pd.Timestamp("2026-06-14")


def load():
    b = pd.read_parquet(SRC / "_cache_built.parquet")
    c = pd.read_parquet(SRC / "_cache_category.parquet")
    g = pd.read_parquet(SRC / "_cache_geos.parquet")
    for d in (b, c):
        d["__time"] = pd.to_datetime(d["__time"])
    for k in ("base_units", "units", "stores_selling", "dollars", "base_dollars", "store_count", "source_pack_count"):
        b[k] = pd.to_numeric(b[k], errors="coerce").fillna(0)
    c["cat_bu"] = pd.to_numeric(c.cat_bu, errors="coerce")
    b["bars"] = b.base_units * b.source_pack_count
    b = b.merge(g[["geography_raw", "channel", "retail_account"]], on="geography_raw", how="left")
    return b, c, g


def flavor(desc: str) -> str:
    s = desc.lower().replace("&", " n ").replace("cookies n cream", "cookies n cream")
    s = re.sub(r"\(\s*\d+\s*pk\s*\)|\d+\s*pk\b|\d+(\.\d+)?\s*oz", " ", s)
    s = re.sub(r"\b(built|puff|protein|bars?|crush|blast|squeeze)\b", " ", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip().title()


def rollout_week(d: pd.DataFrame, stores: pd.Series) -> pd.Timestamp | None:
    p1 = (d[d.source_pack_count == 1].groupby("__time").stores_selling.max() / stores).reindex(stores.index).fillna(0)
    hit = p1[p1 >= 0.10]
    return hit.index.min() if len(hit) else None


def established_4pk(d: pd.DataFrame, anchor) -> list[str]:
    pre = pd.date_range(anchor - PRE * W, anchor - W, freq="7D")
    f = d[d.source_pack_count == 4]
    first = f[f.base_units > 0].groupby("upc").__time.min()
    piv = f.pivot_table(index="__time", columns="upc", values="base_units", aggfunc="sum").reindex(pre).fillna(0)
    return [u for u in piv.columns if (piv[u] > 0).sum() >= 10 and first.get(u, anchor) <= anchor - 26 * W]


def window_sum(d: pd.DataFrame, weeks, col: str) -> float:
    return d[d.__time.isin(weeks)].groupby("__time")[col].sum().reindex(weeks).fillna(0).mean()


def q1_event(b, c, geo, anchor, label, food_geos) -> list[dict]:
    d = b[b.geography_raw == geo]
    est = established_4pk(d, anchor)
    pre = pd.date_range(anchor - PRE * W, anchor - W, freq="7D")
    end = b.__time.max()
    cat = c[c.geography_raw == geo].set_index("__time").cat_bu
    f4 = d[d.upc.isin(est)]
    s1 = d[d.source_pack_count == 1]
    food = b[b.geography_raw.isin(food_geos) & b.upc.isin(est)]
    out = []
    for lo, hi in WINDOWS:
        post = pd.date_range(anchor + lo * W, min(anchor + hi * W, end), freq="7D")
        if len(post) < 8:
            out.append({"retailer": label, "window": f"weeks {lo}-{hi}", "status": "not enough weeks"})
            continue
        r = {"retailer": label, "anchor": anchor.date(), "window": f"weeks {lo}-{hi}", "post_weeks": len(post),
             "n_established_4pk": len(est), "status": "ok"}
        # 4-pack set: per-store bars (bars / stores selling summed over items), then times post stores
        v_pre = f4[f4.__time.isin(pre)].bars.sum() / max(f4[f4.__time.isin(pre)].stores_selling.sum(), 1)
        st_post = f4[f4.__time.isin(post)].stores_selling.sum()
        bars_post = f4[f4.__time.isin(post)].bars.sum()
        v_post = bars_post / max(st_post, 1)
        fa = cat.reindex(post).mean() / cat.reindex(pre).mean()
        fv_pre = food[food.__time.isin(pre)].bars.sum() / max(food[food.__time.isin(pre)].stores_selling.sum(), 1)
        fv_post = food[food.__time.isin(post)].bars.sum() / max(food[food.__time.isin(post)].stores_selling.sum(), 1)
        fb = fv_post / fv_pre if fv_pre > 0 else np.nan
        price_4 = f4[f4.__time.isin(post)].base_dollars.sum() / max(bars_post, 1)
        for tag, fac in (("cat", fa), ("food", fb)):
            exp_v = v_pre * fac
            r[f"change_pct_{tag}"] = 100 * (v_post / exp_v - 1)
            r[f"lost_bars_wk_{tag}"] = (exp_v - v_post) * st_post / len(post)
            r[f"lost_dollars_wk_{tag}"] = r[f"lost_bars_wk_{tag}"] * price_4
        r["category_factor"], r["food_4pk_factor"] = fa, fb
        r["fourpk_bars_wk"] = bars_post / len(post)
        r["fourpk_stores_change_pct"] = 100 * (f4[f4.__time.isin(post)].groupby("__time").stores_selling.max().mean()
                                               / f4[f4.__time.isin(pre)].groupby("__time").stores_selling.max().mean() - 1)
        sb_pre, sb_post = window_sum(s1, pre, "bars"), window_sum(s1, post, "bars")
        sd_pre, sd_post = window_sum(s1, pre, "base_dollars"), window_sum(s1, post, "base_dollars")
        r["singles_bars_wk_gain"], r["singles_dollars_wk_gain"] = sb_post - sb_pre, sd_post - sd_pre
        for tag in ("cat", "food"):
            g_ = r["singles_bars_wk_gain"]
            r[f"share_of_singles_from_4pk_{tag}"] = r[f"lost_bars_wk_{tag}"] / g_ if g_ > 0 else np.nan
        out.append(r)
    return out


def placebo(b, c, geo, anchor_real) -> list[float]:
    d = b[b.geography_raw == geo]
    cat = c[c.geography_raw == geo].set_index("__time").cat_bu
    weeks = pd.date_range(d.__time.min() + (PRE + 26) * W, b.__time.max() - 14 * W, freq="28D")
    out = []
    for a in weeks:
        if abs((a - anchor_real).days) <= 16 * 7:
            continue
        est = established_4pk(d, a)
        if not est:
            continue
        f4 = d[d.upc.isin(est)]
        pre = pd.date_range(a - PRE * W, a - W, freq="7D")
        post = pd.date_range(a + 2 * W, a + 14 * W, freq="7D")
        v_pre = f4[f4.__time.isin(pre)].bars.sum() / max(f4[f4.__time.isin(pre)].stores_selling.sum(), 1)
        v_post = f4[f4.__time.isin(post)].bars.sum() / max(f4[f4.__time.isin(post)].stores_selling.sum(), 1)
        fa = cat.reindex(post).mean() / cat.reindex(pre).mean()
        if v_pre > 0 and np.isfinite(fa):
            out.append(100 * (v_post / (v_pre * fa) - 1))
    return out


def singles_profile(b: pd.DataFrame, rows: pd.DataFrame, label: str) -> dict:
    s = rows[rows.source_pack_count == 1]
    sold = s[(s.base_units > 0) & (s.stores_selling > 0)]
    return {"group": label, "retailers": sold.geography_raw.nunique(), "items": sold.upc.nunique(),
            "units_per_store_item_wk": sold.base_units.sum() / sold.stores_selling.sum() if len(sold) else np.nan,
            "singles_price_per_bar": sold.base_dollars.sum() / max(sold.bars.sum(), 1)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    b, c, g = load()
    food_geos = g[(g.channel == "Food") & (g.retail_account != "MEIJER")].geography_raw.tolist()
    stores = b.groupby(["geography_raw", "__time"]).store_count.max()
    q1, plac, anchors = [], {}, {}
    for geo, label in ANALOGS.items():
        a = rollout_week(b[b.geography_raw == geo], stores.loc[geo])
        anchors[label] = str(a.date()) if a is not None else None
        if a is None:
            continue
        q1 += q1_event(b, c, geo, a, label, food_geos)
        plac[label] = placebo(b, c, geo, a)
    q1 = pd.DataFrame(q1)
    q1.to_csv(OUT / "q1_rollouts.csv", index=False)
    pl = pd.DataFrame([{"retailer": k, "n": len(v), "median_abs_pct": float(np.median(np.abs(v))) if v else np.nan,
                        "values": ";".join(f"{x:.1f}" for x in v)} for k, v in plac.items()])
    pl.to_csv(OUT / "q1_placebo.csv", index=False)

    # Q2 singles at Target / Walmart: ramp by week since rollout, flavor ranking (last 13 weeks), price per bar
    ramp, flav = [], []
    for geo, label in list(ANALOGS.items())[:2]:
        d = b[(b.geography_raw == geo)]
        a = pd.Timestamp(anchors[label])
        s = d[(d.source_pack_count == 1) & (d.stores_selling > 0)]
        wk = s.groupby("__time").agg(bu=("base_units", "sum"), ss=("stores_selling", "sum"), items=("upc", "nunique"),
                                     maxst=("stores_selling", "max"))
        wk["weeks_since"] = ((wk.index - a).days // 7)
        wk["units_per_store_item_wk"] = wk.bu / wk.ss
        wk["share_of_stores"] = wk.maxst / stores.loc[geo].reindex(wk.index).values
        wk["retailer"] = label
        ramp.append(wk.reset_index())
        l = d[(d.__time >= L13) & (d.stores_selling > 0)].copy()
        l["flavor"] = l.description.map(flavor)
        for pk in (1, 4):
            x = l[l.source_pack_count == pk].groupby("flavor").agg(bu=("base_units", "sum"), ss=("stores_selling", "sum"),
                                                                  bars=("bars", "sum"), bd=("base_dollars", "sum"))
            x["units_per_store_wk"] = x.bu / x.ss
            x["price_per_bar"] = x.bd / x.bars
            x["pack"], x["retailer"] = pk, label
            flav.append(x.reset_index())
    pd.concat(ramp).to_csv(OUT / "q2_singles_ramp.csv", index=False)
    flav = pd.concat(flav)
    flav.to_csv(OUT / "q2_flavors_l13.csv", index=False)

    # Q3 / Q4: channel singles benchmarks and grocery pack mix, last 13 weeks
    l13 = b[b.__time >= L13]
    bench = [singles_profile(b, l13[l13.channel == ch], ch) for ch in ("Convenience", "Food", "Mass", "Drug")]
    for geo, label in list(ANALOGS.items())[:2]:
        bench.append(singles_profile(b, l13[l13.geography_raw == geo], label))
    bench = pd.DataFrame(bench)
    bench.to_csv(OUT / "q3_channel_singles.csv", index=False)
    cv = l13[(l13.channel == "Convenience") & (l13.source_pack_count == 1) & (l13.stores_selling > 0)].copy()
    cv["flavor"] = cv.description.map(flavor)
    cflav = cv.groupby("flavor").agg(bu=("base_units", "sum"), ss=("stores_selling", "sum"), retailers=("geography_raw", "nunique"))
    cflav["units_per_store_wk"] = cflav.bu / cflav.ss
    cflav.sort_values("units_per_store_wk", ascending=False).to_csv(OUT / "q3_convenience_flavors.csv")
    mix = l13[l13.channel == "Food"].groupby(["retail_account", "source_pack_count"]).bars.sum().unstack(fill_value=0)
    mix["singles_share_of_bars_pct"] = 100 * mix.get(1, 0) / mix.sum(axis=1)
    mix.to_csv(OUT / "q4_food_pack_mix.csv")

    # predictions
    def q1v(label, col="change_pct_cat", window="weeks 2-14"):
        r = q1[(q1.retailer == label) & (q1.window == window)]
        return float(r[col].iloc[0]) if len(r) and col in r and pd.notna(r[col].iloc[0]) else np.nan
    rp = pd.concat(ramp)
    tgt = rp[(rp.retailer == "Target") & rp.weeks_since.between(2, 14)]
    t_vel = tgt.bu.sum() / tgt.ss.sum()
    bm = bench.set_index("group")
    tf = flav[(flav.retailer == "Target")].groupby("pack").apply(lambda x: x.bd.sum() / x.bars.sum())
    pmed = pl.set_index("retailer").median_abs_pct
    preds = {
        "P1": {"target_change_pct": q1v("Target"), "holds": bool(abs(q1v("Target")) <= 10)},
        "P2": {"walmart_change_pct": q1v("Walmart"), "holds": bool(abs(q1v("Walmart")) <= 15)},
        "P3": {"target_singles_units_per_store_item_wk": t_vel, "holds": bool(0.3 <= t_vel <= 3.0)},
        "P4": {"convenience": bm.loc["Convenience", "units_per_store_item_wk"], "food": bm.loc["Food", "units_per_store_item_wk"],
               "holds": bool(bm.loc["Convenience", "units_per_store_item_wk"] > bm.loc["Food", "units_per_store_item_wk"])},
        "P5": {"target_singles_ppb": float(tf.get(1, np.nan)), "target_4pk_ppb": float(tf.get(4, np.nan)),
               "holds": bool(tf.get(1, np.nan) >= 1.10 * tf.get(4, np.nan))},
        "P6": {"target_median_abs": float(pmed.get("Target", np.nan)), "walmart_median_abs": float(pmed.get("Walmart", np.nan)),
               "holds": bool(pmed.get("Target", 99) <= 10 and pmed.get("Walmart", 99) <= 10)},
    }
    (OUT / "summary.json").write_text(json.dumps({"anchors": anchors, "predictions": preds}, indent=2, default=float))
    pd.set_option("display.width", 230)
    print("rollout weeks:", anchors)
    print(q1.round(3).to_string())
    print(pl.drop(columns="values").round(1).to_string())
    print(bench.round(3).to_string())
    print(mix.round(1).to_string())
    for k, v in preds.items():
        print(k, "HOLDS" if v["holds"] else "FAILS", {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk != "holds"})


if __name__ == "__main__":
    main()
