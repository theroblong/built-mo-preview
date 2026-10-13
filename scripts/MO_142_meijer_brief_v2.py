#!/usr/bin/env python
"""MO_142 - data for the Meijer assortment brief, version 2 (Brian's Oct 2026 comments).

PLAIN WORDS: rebuilds every number in the Meijer brief from Meijer's own stores (SPINS geography
'MEIJER CORP - RMA'; the v1 brief and its CSVs used the Meijer trade area, CRMA / MULTI OUTLET, which is
every store near Meijer, not Meijer) and adds what Brian asked for:
  1. own   Our own performance at Meijer first: weekly BUILT base units per store per week (Brian's metric),
           number of BUILT items selling, by pack size (4-count vs 1-count), and BUILT's share of the bar set.
  2. launch How much of a new item's sales came out of BUILT's existing items ("cannibalization"), measured the
           same way at every retailer: for each launch event, existing BUILT items' sales after the launch vs what
           they would have sold had the category moved the same way (category-adjusted expectation).
             rate = (expected - actual weekly base units of existing BUILT items) / new items' weekly base units
           Read as: "for every 100 units the new items sold, existing BUILT items sold <rate x 100> fewer".
           Split by pack (from existing 4-counts vs from existing 1-counts), by channel (Target and Walmart are
           Mass), trended by launch quarter, and Meijer vs the Food-channel average. A placebo (fake launch dates
           with no real launch nearby) shows how big the measure is by chance.
  3. newest The two newest of Meijer's five main 4-packs (Peanut Butter Cup, first sold 2026-04-19; Cookies N
           Cream, 2026-04-26) against the other three (Brownie Batter, Coconut, Cookie Dough): weekly chart data
           and the per-item profile (which existing items gave up sales).
  4. price Price sensitivity from weekly price and unit changes (promotions included -- most price changes are
           promotions): BUILT at Meijer overall; 4-count vs 1-count at peer Food retailers that sell both
           (Meijer sells almost no singles); the protein-bar competitive set at Meijer; BUILT's price per bar
           against each competitor.
NOT a cause-and-effect estimate: launches, delistings, displays and ads move together. Every table says so.

Druid: built_filtered_weekly (RMA rows are not affected by the MULO label issue; that is MULO geographies only).
Outputs: scripts/outputs/meijer_v2/*.csv + summary.json

PREDICTIONS (written 2026-10-13, before any run; two-sided where direction is not known):
  P1 Meijer April-2026 launch (Peanut Butter Cup + Cookies N Cream 4-packs): cannibalization rate between
     0.00 and 0.60 -- most of the newest pair's sales were new to BUILT.
  P2 Placebo: the median absolute 'loss' at fake launch dates is <= 15% of existing items' sales, at Meijer and
     in the Food channel (if not, per-event rates are too noisy to show; only pooled rates go in the brief).
  P3 Food channel, 4-count launches: the rate taken from existing 4-counts is larger than the rate taken from
     existing 1-counts (pooled).
  P4 Meijer's April-2026 rate lies within the middle half (25th-75th percentile) of Food-channel launch-event
     rates for 2025-2026 launches.
  P5 BUILT price sensitivity at Meijer (all BUILT items, promotions included): estimate between -3.0 and -0.3,
     and its 90% interval excludes 0.
  P6 The protein-bar competitive set at Meijer: median brand estimate between -3.0 and -0.3.
  No prediction (descriptive only): 1-count vs 4-count price sensitivity at peer Food retailers.

MO_142b (added 2026-10-13 AFTER the first run, BEFORE running this variant; first-run results: P1, P2, P3, P5,
P6 hold, P4 fails at the boundary; Mass/Drug/Club placebo noise 40-65% because launches coincide with store
expansions). Change: existing items are judged on base units PER STORE SELLING (Brian's metric), so an expansion
of existing items to more stores no longer counts as 'negative cannibalization':
  expected = sum over existing items of (pre base units per store selling x category factor x post stores selling)
Events are 'measurable' when the new items' weekly base units are at least 10% of existing items' pre sales.
The 4-count vs 1-count price model also drops one week dummy per retailer (it was rank-deficient: no interval).
PREDICTIONS for MO_142b (written before running it):
  Pb1 Velocity-based placebo median |loss|: <= 15% in Food and <= 25% in Mass.
  Pb2 Meijer April-2026 velocity-based rate between 0.00 and 0.60, and within 0.15 of the units-based 0.369.
  Pb3 Food channel pooled velocity-based rate over measurable events between 0.0 and 0.8.
  No prediction: 4-count vs 1-count price sensitivity (descriptive).
"""
from __future__ import annotations

# protocol: not-a-forecast-arm (descriptive analysis for a client brief; predictions above, written before running)
import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from mo_druid_client import query_druid

OUT = Path("outputs/meijer_v2")
MEIJER = "MEIJER CORP - RMA"
START, END = "2023-01-01", "2026-09-07"
SUBCAT = "WELLNESS & NUTRITION BARS"
PRE, GAP, POST, MIN_POST = 13, 2, 13, 8          # weeks: pre window, ramp weeks skipped, post window, minimum post
JOIN_DAYS = 21                                   # launches within 3 weeks of the first one form one event
NEW2 = {"08-40229-30646": "Peanut Butter Cup 4pk", "08-40229-30581": "Cookies N Cream 4pk"}
OLD3 = {"08-40229-30380": "Brownie Batter 4pk", "08-40229-30381": "Coconut 4pk", "08-40229-30558": "Cookie Dough 4pk"}
WHOLESALERS = {"UNFI", "ASSOCIATED WHOLESALE GROCERS"}
CHANNEL = {"CONVENTIONAL|FOOD": "Food", "CONVENTIONAL|MASS MERCH": "Mass", "CONVENTIONAL|DRUG": "Drug",
           "CONVENTIONAL|CONVENIENCE": "Convenience", "CONVENTIONAL|MILITARY": "Military", "CONVENTIONAL|CLUB": "Club"}
W = pd.Timedelta(weeks=1)


def q(sql: str) -> pd.DataFrame:
    return query_druid(sql, timeout=900)


def years():
    return [("2023-01-01", "2024-01-01"), ("2024-01-01", "2025-01-01"), ("2025-01-01", "2026-01-01"), ("2026-01-01", END)]


def num(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ---------------------------------------------------------------- data pulls (cached as parquet)
def geographies() -> pd.DataFrame:
    g = q(f"""SELECT geography_raw, channel_outlet, retail_account, SUM(base_units) bu
              FROM built_filtered_weekly WHERE geography_level = 'RMA' AND source_brand LIKE 'BUILT%'
                AND __time >= TIMESTAMP '2025-09-07' GROUP BY 1, 2, 3""")
    g = g[(g.bu > 5000) & ~g.retail_account.isin(WHOLESALERS)
          & ~g.geography_raw.str.contains(r"W/ AK|W/ HAWAII|W/ HI|TOTAL W/ ALASKA", regex=True)]
    g["channel"] = g.channel_outlet.map(CHANNEL).fillna("Other")
    return g.reset_index(drop=True)


def pull_built(geos: list[str]) -> pd.DataFrame:
    inlist = ", ".join("'" + x.replace("'", "''") + "'" for x in geos)
    parts = [q(f"""SELECT __time, geography_raw, upc, description, source_brand, source_pack_count,
                          SUM(base_units) base_units, SUM(units) units, SUM(stores_selling) stores_selling,
                          SUM(dollars) dollars, SUM(base_dollars) base_dollars, MAX(store_count) store_count
                   FROM built_filtered_weekly
                   WHERE geography_raw IN ({inlist}) AND source_brand LIKE 'BUILT%'
                     AND __time >= TIMESTAMP '{a}' AND __time < TIMESTAMP '{b}'
                   GROUP BY 1, 2, 3, 4, 5, 6""") for a, b in years()]
    d = num(pd.concat(parts, ignore_index=True), ["base_units", "units", "stores_selling", "dollars",
                                                  "base_dollars", "store_count", "source_pack_count"])
    d["__time"] = pd.to_datetime(d["__time"]).dt.tz_localize(None)
    return d


def pull_category(geos: list[str]) -> pd.DataFrame:
    inlist = ", ".join("'" + x.replace("'", "''") + "'" for x in geos)
    parts = [q(f"""SELECT __time, geography_raw, SUM(base_units) cat_bu FROM built_filtered_weekly
                   WHERE geography_raw IN ({inlist}) AND source_brand NOT LIKE 'BUILT%' AND subcategory = '{SUBCAT}'
                     AND __time >= TIMESTAMP '{a}' AND __time < TIMESTAMP '{b}' GROUP BY 1, 2""") for a, b in years()]
    d = num(pd.concat(parts, ignore_index=True), ["cat_bu"])
    d["__time"] = pd.to_datetime(d["__time"]).dt.tz_localize(None)
    return d


def pull_meijer_all() -> pd.DataFrame:
    parts = [q(f"""SELECT __time, upc, description, source_brand, source_pack_count, nfp_protein,
                          SUM(base_units) base_units, SUM(units) units, SUM(stores_selling) stores_selling,
                          SUM(dollars) dollars, SUM(base_dollars) base_dollars
                   FROM built_filtered_weekly WHERE geography_raw = '{MEIJER}' AND subcategory = '{SUBCAT}'
                     AND __time >= TIMESTAMP '{a}' AND __time < TIMESTAMP '{b}'
                   GROUP BY 1, 2, 3, 4, 5, 6""") for a, b in years()]
    d = num(pd.concat(parts, ignore_index=True), ["base_units", "units", "stores_selling", "dollars",
                                                  "base_dollars", "source_pack_count"])
    d["__time"] = pd.to_datetime(d["__time"]).dt.tz_localize(None)
    return d


def load(name: str, fn):
    p = OUT / f"_cache_{name}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    d = fn()
    d.to_parquet(p)
    return d


# ---------------------------------------------------------------- 1. own performance
def own(m: pd.DataFrame, built: pd.DataFrame) -> pd.DataFrame:
    b = built[built.geography_raw == MEIJER].copy()
    stores = b.groupby("__time").store_count.max()
    rows = []
    for (t, pk), g in b.groupby(["__time", "source_pack_count"]):
        rows.append({"week": t, "pack": int(pk), "base_units": g.base_units.sum(), "units": g.units.sum(),
                     "items_selling": int((g.base_units > 0).sum()), "stores_selling_sum": g.stores_selling.sum()})
    o = pd.DataFrame(rows)
    tot = o.groupby("week").agg(base_units=("base_units", "sum"), units=("units", "sum"),
                                items_selling=("items_selling", "sum"), ss=("stores_selling_sum", "sum")).reset_index()
    tot["pack"] = 0  # 0 = all BUILT
    o = pd.concat([o.rename(columns={"stores_selling_sum": "ss"}), tot], ignore_index=True)
    o["meijer_stores"] = o.week.map(stores)
    o["base_units_per_store_week"] = o.base_units / o.meijer_stores            # per Meijer store, all items
    o["base_units_per_item_store_week"] = o.base_units / o.ss.replace(0, np.nan)  # per store selling, per item
    cat = m[~m.source_brand.str.startswith("BUILT")].groupby("__time").base_units.sum()
    o["built_share_of_bars_pct"] = np.where(o.pack == 0, 100 * o.base_units / (o.week.map(cat) + o.base_units), np.nan)
    return o.sort_values(["pack", "week"])


# ---------------------------------------------------------------- 2. launch events and cannibalization rate
def launches(built: pd.DataFrame) -> pd.DataFrame:
    s = built[built.base_units > 0]
    first = s.groupby(["geography_raw", "upc"]).agg(first=("__time", "min")).reset_index()
    geo_first = s.groupby("geography_raw").__time.min()
    first["geo_first"] = first.geography_raw.map(geo_first)
    ok = (first["first"] - first.geo_first >= (PRE + 2) * W) & (first["first"] >= pd.Timestamp("2023-04-23"))
    return first[ok].sort_values(["geography_raw", "first"])


def events(launch: pd.DataFrame) -> pd.DataFrame:
    out = []
    for geo, g in launch.groupby("geography_raw"):
        anchor, members = None, []
        for _, r in g.iterrows():
            if anchor is not None and (r["first"] - anchor).days <= JOIN_DAYS:
                members.append(r.upc)
                continue
            if anchor is not None:
                out.append({"geography_raw": geo, "anchor": anchor, "new_upcs": members})
            anchor, members = r["first"], [r.upc]
        if anchor is not None:
            out.append({"geography_raw": geo, "anchor": anchor, "new_upcs": members})
    e = pd.DataFrame(out).sort_values(["geography_raw", "anchor"])
    e["next_anchor"] = e.groupby("geography_raw").anchor.shift(-1)
    return e.reset_index(drop=True)


def geo_pivot(built_geo: pd.DataFrame):
    piv = built_geo.pivot_table(index="__time", columns="upc", values="base_units", aggfunc="sum")
    piv = piv.reindex(pd.date_range(piv.index.min(), piv.index.max(), freq="7D")).fillna(0)
    packs = built_geo.drop_duplicates("upc").set_index("upc").source_pack_count
    ss = built_geo.pivot_table(index="__time", columns="upc", values="stores_selling", aggfunc="sum")
    ss = ss.reindex(piv.index).reindex(columns=piv.columns).fillna(0)
    return piv, packs, (piv > 0).idxmax(), ss


def measure(gp, cat_geo: pd.Series, anchor, new_upcs, next_anchor, end) -> dict:
    pre_w = pd.date_range(anchor - PRE * W, anchor - W, freq="7D")
    post_end = anchor + (GAP + POST - 1) * W
    if next_anchor is not None and not pd.isna(next_anchor):
        post_end = min(post_end, next_anchor - W)
    post_end = min(post_end, end)
    post_w = pd.date_range(anchor + GAP * W, post_end, freq="7D") if post_end >= anchor + GAP * W else pd.DatetimeIndex([])
    if len(post_w) < MIN_POST:
        return {"status": "too early or overlapping", "post_weeks": len(post_w)}
    piv, packs, first_sold, ss = gp
    pre = piv.reindex(pre_w).fillna(0)
    post = piv.reindex(post_w).fillna(0)
    existing = [u for u in piv.columns if u not in new_upcs and (pre[u] > 0).sum() >= 10
                and (pre[u].tail(4) > 0).all() and first_sold[u] <= anchor - 26 * W]
    if not existing:
        return {"status": "no established BUILT items", "post_weeks": len(post_w)}
    c_pre, c_post = cat_geo.reindex(pre_w).mean(), cat_geo.reindex(post_w).mean()
    f = c_post / c_pre if c_pre and c_pre > 0 else np.nan
    new_w = post[[u for u in new_upcs if u in post]].sum(axis=1).mean()
    res = {"status": "ok", "post_weeks": len(post_w), "category_factor": f, "new_weekly": new_w,
           "new_packs": sorted({int(packs.get(u, 0)) for u in new_upcs}), "n_existing": len(existing),
           "per_item": []}
    for side in ("all", 4, 1):
        us = existing if side == "all" else [u for u in existing if int(packs.get(u, 0)) == side]
        e_pre = pre[us].sum(axis=1).mean() if us else 0.0
        e_post = post[us].sum(axis=1).mean() if us else 0.0
        lost = e_pre * f - e_post
        res[f"existing_pre_{side}"], res[f"existing_post_{side}"], res[f"lost_{side}"] = e_pre, e_post, lost
        res[f"rate_{side}"] = lost / new_w if new_w > 0 else np.nan
        # MO_142b: per-store velocity version (existing items' store-count changes are not counted)
        exp_v = sum(pre[u].sum() / ss.reindex(pre_w)[u].sum() * f * ss.reindex(post_w)[u].mean()
                    for u in us if ss.reindex(pre_w)[u].sum() > 0) if us else 0.0
        lost_v = exp_v - e_post
        res[f"lost_v_{side}"] = lost_v
        res[f"rate_v_{side}"] = lost_v / new_w if new_w > 0 else np.nan
    res["measurable"] = bool(new_w >= 0.10 * res["existing_pre_all"]) if res["existing_pre_all"] > 0 else False
    for u in existing:
        e_pre, e_post = pre[u].mean(), post[u].mean()
        v_pre = pre[u].sum() / ss.reindex(pre_w)[u].sum() if ss.reindex(pre_w)[u].sum() > 0 else np.nan
        st_post = ss.reindex(post_w)[u].mean()
        res["per_item"].append({"upc": u, "pre_weekly": e_pre, "expected_weekly": e_pre * f, "post_weekly": e_post,
                                "lost_weekly": e_pre * f - e_post, "pre_per_store": v_pre,
                                "post_per_store": e_post / st_post if st_post > 0 else np.nan,
                                "stores_pre": ss.reindex(pre_w)[u].mean(), "stores_post": st_post,
                                "lost_v_weekly": v_pre * f * st_post - e_post})
    return res


def placebo(gp, cat_geo: pd.Series, launch_dates: list, end) -> list[dict]:
    weeks = pd.date_range(gp[0].index.min() + (PRE + 26) * W, end - (GAP + POST) * W, freq="28D")
    out = []
    for a in weeks:
        if any(abs((a - d).days) <= 16 * 7 for d in launch_dates):
            continue
        r = measure(gp, cat_geo, a, [], None, end)
        if r and r["status"] == "ok" and r["existing_pre_all"] > 0:
            out.append({"anchor": a, "lost_pct": 100 * r["lost_all"] / r["existing_pre_all"],
                        "lost_v_pct": 100 * r["lost_v_all"] / r["existing_pre_all"]})
    return out


def launch_analysis(built, cat, geos):
    end = built.__time.max()
    lau = launches(built)
    ev = events(lau)
    names = built.drop_duplicates("upc").set_index("upc").description
    rows, items, plac = [], [], []
    gps = {g: geo_pivot(built[built.geography_raw == g]) for g in geos.geography_raw}
    cgs = {g: cat[cat.geography_raw == g].set_index("__time").cat_bu for g in geos.geography_raw}
    for _, e in ev.iterrows():
        r = measure(gps[e.geography_raw], cgs[e.geography_raw], e.anchor, e.new_upcs, e.next_anchor, end)
        row = {"geography_raw": e.geography_raw, "anchor": e.anchor, "n_new": len(e.new_upcs),
               "new_items": "; ".join(names.get(u, u) for u in e.new_upcs)}
        row.update({k: v for k, v in r.items() if k != "per_item"})
        rows.append(row)
        for it in r.get("per_item", []):
            items.append({"geography_raw": e.geography_raw, "anchor": e.anchor, "item": names.get(it["upc"], it["upc"]), **it})
    for geo in geos.geography_raw:
        for p in placebo(gps[geo], cgs[geo], list(lau[lau.geography_raw == geo]["first"]), end):
            plac.append({"geography_raw": geo, **p})
    ev = pd.DataFrame(rows).merge(geos[["geography_raw", "channel", "retail_account"]], on="geography_raw", how="left")
    ev["new_packs"] = ev.new_packs.astype(str)
    ev["launch_type"] = ev.new_packs.map({"[4]": "4-count launch", "[1]": "1-count launch"}).fillna("mixed packs")
    ev["quarter"] = pd.PeriodIndex(ev.anchor, freq="Q").astype(str)
    pl = pd.DataFrame(plac).merge(geos[["geography_raw", "channel"]], on="geography_raw", how="left")
    return ev, pd.DataFrame(items), pl


def pooled(ev: pd.DataFrame, keys: list[str], side="all", n_boot=2000, seed=0, lost="lost") -> pd.DataFrame:
    ok = ev[(ev.status == "ok") & (ev.new_weekly > 0) & np.isfinite(ev[f"{lost}_{side}"])]
    if lost == "lost_v":
        ok = ok[ok.measurable.astype(bool)]
    rng = np.random.default_rng(seed)
    out = []
    for k, g in ok.groupby(keys):
        lost_a, new = g[f"{lost}_{side}"].to_numpy(), g.new_weekly.to_numpy()
        rate = lost_a.sum() / new.sum()
        bs = [lost_a[i].sum() / new[i].sum() for i in (rng.integers(0, len(g), len(g)) for _ in range(n_boot))]
        rcol = "rate_v" if lost == "lost_v" else "rate"
        out.append({**dict(zip(keys, k if isinstance(k, tuple) else (k,))), "side": side, "measure": lost,
                    "events": len(g), "rate": rate, "rate_p05": np.percentile(bs, 5),
                    "rate_p95": np.percentile(bs, 95), "median_event_rate": g[f"{rcol}_{side}"].median()})
    return pd.DataFrame(out)


# ---------------------------------------------------------------- 4. price sensitivity
def fe_slopes(d: pd.DataFrame, group_col: str, time_col: str, nest_col: str | None = None) -> pd.DataFrame:
    """ln(units per store selling) on ln(price per bar) with item and time fixed effects (exact two-way
    within-item demeaning + time dummies); one slope per group; standard errors clustered by item."""
    d = d.copy()
    d["y"] = np.log(d.units / d.stores_selling)
    d["x"] = np.log(d.price_per_bar)
    groups = sorted(d[group_col].unique())
    X = pd.DataFrame({f"x_{g}": np.where(d[group_col] == g, d.x, 0.0) for g in groups}, index=d.index)
    T = pd.get_dummies(d[time_col], prefix="t", drop_first=True, dtype=float)
    if nest_col is not None:   # items nest within retailers: drop one time dummy per retailer (rank)
        first_per = d.groupby(nest_col)[time_col].min()
        T = T.drop(columns=[f"t_{v}" for v in first_per if f"t_{v}" in T.columns])
    Z = pd.concat([d[["y"]], X, T], axis=1)
    Zd = Z - Z.groupby(d.upc_key).transform("mean")
    fit = sm.OLS(Zd.y, Zd.drop(columns="y")).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.upc_key)[0]})
    rows = []
    for g in groups:
        b, se = fit.params[f"x_{g}"], fit.bse[f"x_{g}"]
        sub = d[d[group_col] == g]
        rows.append({"group": g, "estimate": b, "p05": b - 1.645 * se, "p95": b + 1.645 * se, "items": sub.upc_key.nunique(),
                     "item_weeks": len(sub), "price_cv_within_item": float(sub.groupby("upc_key").price_per_bar.agg(
                         lambda s: s.std() / s.mean()).median())})
    return pd.DataFrame(rows)


def price_frame(d: pd.DataFrame, since: str) -> pd.DataFrame:
    d = d[(d.__time >= pd.Timestamp(since)) & (d.units > 0) & (d.stores_selling >= 5) & (d.dollars > 0)
          & (d.source_pack_count > 0)].copy()
    d["price_per_bar"] = d.dollars / d.units / d.source_pack_count
    return d[np.isfinite(np.log(d.price_per_bar))]


def protein_g(s) -> float:
    mt = re.search(r"\d*\.?\d+", str(s or ""))
    return float(mt.group()) if mt else np.nan


def wmedian(v: pd.Series, w: pd.Series) -> float:
    ok = v.notna() & (w > 0)
    if not ok.any():
        return np.nan
    v, w = v[ok].to_numpy(), w[ok].to_numpy()
    o = np.argsort(v)
    c = np.cumsum(w[o])
    return float(v[o][np.searchsorted(c, c[-1] / 2)])


def price_analysis(m: pd.DataFrame, built: pd.DataFrame, geos: pd.DataFrame) -> dict:
    since = "2024-09-08"   # last 104 weeks
    # competitive set: bar brands at Meijer with sales-weighted median protein >= 15 g and >= 20k base units in 52 weeks
    last52 = m[m.__time >= pd.Timestamp("2025-09-07")].copy()
    last52["protein"] = last52.nfp_protein.map(protein_g)
    br = last52.groupby("source_brand").apply(lambda g: pd.Series({
        "base_units_52w": g.base_units.sum(),
        "protein_g": wmedian(g.protein, g.base_units)}))
    comp = br[(br.protein_g >= 15) & (br.base_units_52w >= 20000) & ~br.index.str.startswith("BUILT")].index.tolist()
    mm = price_frame(m, since)
    mm["upc_key"] = mm.upc
    mm["brand_grp"] = np.where(mm.source_brand.str.startswith("BUILT"), "BUILT",
                               np.where(mm.source_brand.isin(comp), mm.source_brand, "OTHER BARS"))
    meijer = fe_slopes(mm, "brand_grp", "__time")
    # 4-count vs 1-count: BUILT at peer Food retailers that sell both pack sizes (Meijer included)
    food = geos[geos.channel == "Food"].geography_raw
    b = price_frame(built[built.geography_raw.isin(food)], since)
    mix = b[b.__time >= pd.Timestamp("2025-09-07")].groupby(["geography_raw", "source_pack_count"]).base_units.sum().unstack(fill_value=0)
    both = mix[(mix.get(1, 0) >= 5000) & (mix.get(4, 0) >= 5000)].index.tolist()
    b = b[b.geography_raw.isin(both) & b.source_pack_count.isin([1, 4])].copy()
    b["upc_key"] = b.geography_raw + "|" + b.upc
    b["pack"] = b.source_pack_count.astype(int).astype(str) + "-count"
    b["geo_week"] = b.geography_raw + "|" + b.__time.astype(str)
    packs = fe_slopes(b, "pack", "geo_week", nest_col="geography_raw")
    # price position: base price per bar, last 13 weeks, sales-weighted
    l13 = m[(m.__time >= pd.Timestamp("2026-06-14")) & (m.base_units > 0) & (m.source_pack_count > 0)].copy()
    l13["bars"] = l13.base_units * l13.source_pack_count
    l13["grp"] = np.where(l13.source_brand.str.startswith("BUILT"), "BUILT", l13.source_brand)
    pos = l13[l13.grp.isin(comp + ["BUILT"])].groupby("grp").agg(base_dollars=("base_dollars", "sum"), bars=("bars", "sum"))
    pos["base_price_per_bar"] = pos.base_dollars / pos.bars
    pos["index_vs_built"] = 100 * pos.base_price_per_bar / pos.loc["BUILT", "base_price_per_bar"]
    return {"competitive_set": comp, "brand_protein": br.reset_index(), "meijer": meijer,
            "peer_food_retailers_both_packs": both, "packs": packs, "position": pos.reset_index()}


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-pull from Druid instead of the parquet cache")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.refresh:
        for p in OUT.glob("_cache_*.parquet"):
            p.unlink()
    geos = load("geos", geographies)
    gl = geos.geography_raw.tolist()
    built = load("built", lambda: pull_built(gl))
    cat = load("category", lambda: pull_category(gl))
    m = load("meijer_all", pull_meijer_all)
    for d in (built, cat, m):
        d["__time"] = pd.to_datetime(d["__time"])
    print(f"geographies {len(gl)}; BUILT rows {len(built):,}; Meijer bar rows {len(m):,}; weeks to {built.__time.max().date()}")

    o = own(m, built)
    o.to_csv(OUT / "own_weekly.csv", index=False)

    ev, items, pl = launch_analysis(built, cat, geos)
    ev.to_csv(OUT / "launch_events.csv", index=False)
    items.to_csv(OUT / "launch_per_item.csv", index=False)
    pl.to_csv(OUT / "placebo.csv", index=False)
    pooled_rows = [pooled(ev, ["channel"]), pooled(ev, ["channel", "launch_type"], "all"),
                   pooled(ev, ["channel", "launch_type"], 4), pooled(ev, ["channel", "launch_type"], 1),
                   pooled(ev, ["channel", "quarter"])]
    pooled_v = [pooled(ev, ["channel"], lost="lost_v"), pooled(ev, ["channel", "launch_type"], 4, lost="lost_v"),
                pooled(ev, ["channel", "launch_type"], 1, lost="lost_v"), pooled(ev, ["channel", "quarter"], lost="lost_v")]
    pooled_rows += pooled_v
    pooled_all = pd.concat(pooled_rows, ignore_index=True)
    pooled_all.to_csv(OUT / "launch_pooled.csv", index=False)

    mj = m[m.upc.isin(list(NEW2) + list(OLD3))].copy()
    mj["item"] = mj.upc.map({**NEW2, **OLD3})
    mj["group"] = np.where(mj.upc.isin(list(NEW2)), "newest two", "other three")
    mj["base_units_per_store_selling"] = mj.base_units / mj.stores_selling.replace(0, np.nan)
    catw = m[~m.source_brand.str.startswith("BUILT")].groupby("__time").base_units.sum().rename("bars_ex_built_base_units")
    mj = mj.merge(catw, left_on="__time", right_index=True, how="left")
    mj[["__time", "item", "group", "upc", "base_units", "stores_selling", "base_units_per_store_selling",
        "bars_ex_built_base_units"]].sort_values(["item", "__time"]).to_csv(OUT / "newest_two_weekly.csv", index=False)

    pr = price_analysis(m, built, geos)
    pr["meijer"].to_csv(OUT / "price_meijer_brands.csv", index=False)
    pr["packs"].to_csv(OUT / "price_4ct_vs_1ct_peer_food.csv", index=False)
    pr["position"].to_csv(OUT / "price_position_meijer.csv", index=False)
    pr["brand_protein"].to_csv(OUT / "brand_protein_meijer.csv", index=False)

    # ------------------------------------------------ predictions
    ok = ev[ev.status == "ok"]
    apr = ok[(ok.geography_raw == MEIJER) & (ok.anchor == pd.Timestamp("2026-04-19"))]
    r_apr = float(apr.rate_all.iloc[0]) if len(apr) else np.nan
    food = ok[(ok.channel == "Food") & (ok.anchor >= pd.Timestamp("2025-01-01")) & (ok.new_weekly > 0)]
    q25, q75 = food.rate_all.quantile([0.25, 0.75])
    pm = pl[pl.geography_raw == MEIJER].lost_pct.abs().median()
    pf = pl[pl.channel == "Food"].lost_pct.abs().median()
    f4 = ok[(ok.channel == "Food") & (ok.launch_type == "4-count launch") & (ok.new_weekly > 0)]
    r44, r41 = f4.lost_4.sum() / f4.new_weekly.sum(), f4.lost_1.sum() / f4.new_weekly.sum()
    bm = pr["meijer"].set_index("group")
    built_est = bm.loc["BUILT"]
    comp_med = bm.drop(index=[i for i in ("BUILT", "OTHER BARS") if i in bm.index]).estimate.median()
    preds = {
        "P1": {"value": r_apr, "holds": bool(0.0 <= r_apr <= 0.60)},
        "P2": {"meijer_median_abs_pct": pm, "food_median_abs_pct": pf, "holds": bool(pm <= 15 and pf <= 15)},
        "P3": {"from_4ct": r44, "from_1ct": r41, "events": len(f4), "holds": bool(r44 > r41)},
        "P4": {"meijer": r_apr, "food_q25": q25, "food_q75": q75, "events": len(food), "holds": bool(q25 <= r_apr <= q75)},
        "P5": {"estimate": built_est.estimate, "p05": built_est.p05, "p95": built_est.p95,
               "holds": bool(-3.0 <= built_est.estimate <= -0.3 and built_est.p95 < 0)},
        "P6": {"median": comp_med, "brands": len(bm) - 2, "holds": bool(-3.0 <= comp_med <= -0.3)},
    }
    apr_v = float(apr.rate_v_all.iloc[0]) if len(apr) else np.nan
    pvf = pl[pl.channel == "Food"].lost_v_pct.abs().median()
    pvm = pl[pl.channel == "Mass"].lost_v_pct.abs().median()
    fv = ok[(ok.channel == "Food") & ok.measurable.astype(bool) & (ok.new_weekly > 0)]
    food_v = fv.lost_v_all.sum() / fv.new_weekly.sum() if len(fv) else np.nan
    preds.update({
        "Pb1": {"food_median_abs_pct": pvf, "mass_median_abs_pct": pvm, "holds": bool(pvf <= 15 and pvm <= 25)},
        "Pb2": {"meijer_v": apr_v, "meijer_units": r_apr, "holds": bool(0 <= apr_v <= 0.6 and abs(apr_v - r_apr) <= 0.15)},
        "Pb3": {"food_pooled_v": food_v, "events": len(fv), "holds": bool(0.0 <= food_v <= 0.8)},
    })
    summary = {"weeks_to": str(built.__time.max().date()), "geographies": gl, "events_ok": int(len(ok)),
               "events_total": int(len(ev)), "competitive_set": pr["competitive_set"],
               "peer_food_retailers_both_packs": pr["peer_food_retailers_both_packs"], "predictions": preds}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    pd.set_option("display.width", 220)
    print(ev[ev.geography_raw == MEIJER].drop(columns=["geography_raw"]).to_string())
    print(pooled_rows[0].round(3).to_string())
    print(pooled_rows[2].round(3).to_string())
    print(pooled_rows[3].round(3).to_string())
    for pv in pooled_v:
        print(pv.round(3).to_string())
    print(pr["meijer"].round(3).to_string())
    print(pr["packs"].round(3).to_string())
    print(pr["position"].round(2).to_string())
    for k, v in preds.items():
        print(k, "HOLDS" if v["holds"] else "FAILS", {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk != "holds"})


if __name__ == "__main__":
    main()
