"""MO_83 — Hierarchical top-down allocation for short-history items, vs every simpler option.

THE PROBLEM, RESTATED FROM MEASUREMENT
--------------------------------------
Short-history series (<13 weeks) are 7.7% of forecast volume and LightGBM cannot forecast them
well. MO_82 settled that decisively:

    SHORT series, pooled over 4 cutoffs
        naive (last value)                        65.6
        carry-forward (4-week mean)  <- shipping  68.9
        LightGBM trained WITHOUT short series     78.0
        LightGBM trained WITH short series        77.5   (and costs mature series +1.2pp)

So the gap-filler stays. Two questions follow, and this script answers both.

QUESTION 1 — are we even using the right simple method?
We ship a 4-week mean times a seasonal index. Plain last-value beat the 4-week mean by 3.3pp in
MO_82 and by the same margin in MO_79. The seasonal overlay has never been tested on THIS band in
isolation. Arms: `naive_last`, `mean4`, `naive_x_seasonal`, `mean4_x_seasonal`.

QUESTION 2 — does hierarchical top-down allocation beat all of them?
This is the one standard CPG approach we have never tried, and it is mechanically different from
the donor surrogate we already rejected:

    donor surrogate (REJECTED)  borrowed another item's SHAPE and rescaled it
    hierarchical allocation     borrows the SHELF's LEVEL and applies this item's SHARE

A new SKU at Kroger has no history, but the Kroger shelf it sits on has three years of it. So we
forecast the thing that HAS data and allocate down:

    forecast[item, week] = share(item) x shelf_total[week]

    shelf       = all series at the same retailer x channel x geography. This is the right
                  grain because distribution, promotion and seasonality are shelf-level
                  realities, and it is the level the planner actually buys for.
    share       = the item's observed share of its shelf across the weeks it HAS been selling.
                  Even 2 weeks gives a usable share when the denominator is a mature shelf.
    shelf_total = carried forward from the shelf's own recent level. The shelf is mature, so
                  this is a far easier quantity to forecast than the new item directly.

Why it should work where the item-level methods fail: a 3-week-old SKU has no trend or
seasonality of its own to extrapolate, but the shelf does, and the item inherits it. Noise that
swamps a single new item averages out across the shelf.

Two variants are scored, because the share estimate is the whole ballgame:
    hier_own_share    share from this item's own observed weeks only
    hier_blend_share  that share shrunk toward the typical first-13-week share of new items on
                      that shelf (shrinkage weight by number of weeks observed). With 1-2 weeks
                      of data an item's own share is extremely noisy; borrowing the launch norm
                      is the classic partial-pooling correction.

Run:  python MO_83_hierarchical_allocation.py [--cutoffs 13,26,39,52]
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from mo_panel import (GROUP_COLS, MIN_SERIES_WEEKS, drop_zero_volume_geographies,
                      apply_rma_priority, fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_ak_hi_market_variants)

PARQUET  = Path("outputs/retailer_sales_weekly.parquet")
OUT_JSON = Path("outputs/mo83_hierarchical_allocation.json")
SEASONAL = Path("outputs/mo59_seasonal_index.csv")
HORIZON  = 13
SHRINK_K = 6.0     # weeks of own data at which own-share and launch-norm are weighted equally


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = np.abs(a).sum()
    return float(np.abs(a - p).sum() / d * 100) if d > 0 else float("nan")


def load_panel():
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    for c in ("base_units", "week_of_year"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["base_units"]).copy()
    df = fill_promo_mechanic_nulls(df, verbose=False)
    df = drop_military_accounts(df, verbose=False)
    df = drop_ak_hi_market_variants(df, verbose=False)
    df = drop_zero_volume_geographies(df, target="base_units", verbose=False)
    df = apply_rma_priority(df, verbose=False)
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


def load_seasonal():
    if not SEASONAL.exists():
        return {}
    c = pd.read_csv(SEASONAL)
    col = "seasonal_index" if "seasonal_index" in c.columns else c.columns[-1]
    return {int(w): float(v) for w, v in zip(c["week_of_year"], c[col])}


def main(cutoffs_back):
    df = load_panel()
    seas = load_seasonal()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    end = df["__time"].max()
    print("MO_83 — hierarchical allocation vs the simple gap-fillers, on SHORT series only")
    print(f"  panel {len(df):,} rows · {df.groupby(GROUP_COLS, observed=True).ngroups:,} series")
    print(f"  seasonal index: {len(seas)} weeks loaded\n")

    ARMS = ["naive_last", "mean4", "naive_x_seasonal", "mean4_x_seasonal",
            "hier_own_share", "hier_blend_share"]
    per_cut = {}
    for wb in cutoffs_back:
        cut = end - pd.Timedelta(weeks=wb)
        fw = list(weeks[weeks > cut][:HORIZON])
        if not fw:
            continue
        hist = df[df["__time"] <= cut]
        fut = df[(df["__time"] > cut) & (df["__time"] <= fw[-1])]
        if hist.empty or fut.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 fut.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        nwk = hist.groupby(GROUP_COLS, observed=True)["base_units"].size().to_dict()
        short = {k[0] for k in truth if nwk.get(k[0], 0) < MIN_SERIES_WEEKS}
        if not short:
            continue

        # ── shelf = retailer x channel x geography ──
        hist = hist.copy()
        hist["_shelf"] = list(zip(hist["channel_outlet"], hist["retail_account"],
                                  hist["geography_raw"]))
        shelf_wk = hist.groupby(["_shelf", "__time"], observed=True)["base_units"].sum()
        # shelf level carried forward from its own last 4 observed weeks (the shelf is mature,
        # so this is a far easier quantity to forecast than any single new item on it)
        shelf_lvl = {}
        for sh, s in shelf_wk.groupby(level=0):
            shelf_lvl[sh] = float(s.tail(4).mean())
        # Membership MUST go through a set. `tuple in index.get_level_values(0)` returns False
        # even when the tuple is present, because pandas reads a tuple as a multi-level lookup
        # rather than a containment test — which silently skipped every shelf and zeroed the arm.
        shelf_keys = set(shelf_wk.index.get_level_values(0))

        # launch norm: typical share a <13-week item holds of its shelf, pooled across shelves
        own_share, launch_norm = {}, []
        for key, g in hist.groupby(GROUP_COLS, observed=True):
            if key[0] not in {k for k in short}:
                pass
            sh = (key[1], key[2], key[3])
            if sh not in shelf_keys:
                continue
            tot = shelf_wk.loc[sh]
            gi = g.set_index("__time")["base_units"]
            common = gi.index.intersection(tot.index)
            if len(common) == 0:
                continue
            denom = float(tot.loc[common].sum())
            if denom <= 0:
                continue
            sshare = float(gi.loc[common].sum()) / denom
            own_share[key] = sshare
            if nwk.get(key, 0) < MIN_SERIES_WEEKS:
                launch_norm.append(sshare)
        norm = float(np.median(launch_norm)) if launch_norm else 0.0

        preds = {a: {} for a in ARMS}
        for key, g in hist.groupby(GROUP_COLS, observed=True):
            if key not in short:
                continue
            g = g.sort_values("__time")
            u = pd.to_numeric(g["base_units"], errors="coerce").fillna(0)
            lv1, lv4 = float(u.iloc[-1]), float(u.tail(4).mean())
            n = len(u)
            sh = (key[1], key[2], key[3])
            lvl = shelf_lvl.get(sh, 0.0)
            s_own = own_share.get(key, 0.0)
            w = n / (n + SHRINK_K)                      # more own weeks -> trust own share more
            s_bl = w * s_own + (1 - w) * norm
            for fd in fw:
                woy = int(fd.isocalendar().week)
                sf = 1.0 + seas.get(woy, 0.0)
                sf = max(0.1, sf)
                preds["naive_last"][(key, fd)] = lv1
                preds["mean4"][(key, fd)] = lv4
                preds["naive_x_seasonal"][(key, fd)] = lv1 * sf
                preds["mean4_x_seasonal"][(key, fd)] = lv4 * sf
                preds["hier_own_share"][(key, fd)] = max(0.0, s_own * lvl * sf)
                preds["hier_blend_share"][(key, fd)] = max(0.0, s_bl * lvl * sf)

        sub = {k: v for k, v in truth.items() if k[0] in short}
        row = {"cutoff": str(cut.date()), "n_short": len(short),
               "units": float(sum(sub.values())), "launch_norm_share": norm}
        cells = []
        for a in ARMS:
            ks = [k for k in sub if k in preds[a]]
            if not ks:
                row[a] = None; cells.append(f"{a}=--"); continue
            av = np.array([sub[k] for k in ks]); pv = np.array([preds[a][k] for k in ks])
            row[a] = {"wmape": wmape(av, pv),
                      "bias": float(pv.sum() / av.sum()) if av.sum() else float("nan"),
                      "units": float(av.sum())}
            cells.append(f"{a}={row[a]['wmape']:.1f}")
        per_cut[str(cut.date())] = row
        print(f"  cutoff {cut.date()} | {len(short):>3d} short series | " + "  ".join(cells))

    print(f"\n{'='*78}")
    print("  POOLED (unit-weighted) — SHORT series only")
    print(f"  {'arm':<20s} {'wMAPE':>8s} {'|bias-1|':>10s}")
    summary = {}
    for a in ARMS:
        ws = [per_cut[c][a]["wmape"] * per_cut[c][a]["units"] for c in per_cut if per_cut[c].get(a)]
        us = [per_cut[c][a]["units"] for c in per_cut if per_cut[c].get(a)]
        bs = [abs(per_cut[c][a]["bias"] - 1) for c in per_cut if per_cut[c].get(a)]
        if us:
            summary[a] = {"wmape": float(sum(ws) / sum(us)), "mean_abs_bias": float(np.mean(bs))}
            print(f"  {a:<20s} {summary[a]['wmape']:>8.1f} {summary[a]['mean_abs_bias']:>10.3f}")
    if summary:
        best = min(summary, key=lambda k: summary[k]["wmape"])
        ship = summary.get("mean4_x_seasonal", summary.get("mean4"))
        print(f"\n  BEST ARM: {best} at {summary[best]['wmape']:.1f}")
        if ship:
            print(f"  Currently shipping ~{ship['wmape']:.1f} -> "
                  f"{ship['wmape'] - summary[best]['wmape']:+.1f}pp available")
        print(f"  MO_82 reference on the same band: naive 65.6 · LightGBM 77.5-78.0")
    OUT_JSON.write_text(json.dumps({"per_cutoff": per_cut, "summary": summary,
                                    "shrink_k": SHRINK_K, "horizon": HORIZON},
                                   indent=2, default=float))
    print(f"\n  → {OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoffs", type=str, default="13,26,39,52")
    a = ap.parse_args()
    main([int(x) for x in a.cutoffs.split(",")])
