#!/usr/bin/env python
"""MO_130 - Can a model that starts from Connor's anchor and learns corrections beat flat?

WHERE THIS CAME FROM
--------------------
MO_129 (clean, honest re-baseline, 2026-10-07): on existing items the shipped recursive
model trails flat by +2.86pp at cell x week and +1.83pp at account x month (both outside
the margin of error) and ties at portfolio x month. Flat and Connor L4W are
indistinguishable. Every method runs 16-18% low on Jan-Mar target weeks. Jason's direction
(docs/FORECAST_ROADMAP.md step 3): seasonal turns must be LEARNED from existing and future
patterns, not bolted on; size comes from a recent anchor, shape is learned across all
items with every year counting.

PRIOR WORK (docs/SETTLED_FINDINGS.md, DRAFT; live notes 2026-10-07)
--------------------------------------------------------------------
  MO_129  clean baseline: model 35.45 / 22.95 / 13.77, flat 32.59 / 21.12 / 12.84,
          conn_L4W 32.93 / 20.69 / 12.61 (cw / am / pm, existing items). The reference.
  MO_103  direct beats recursive at every horizon (old harness). PROVISIONAL -> this is a
          direct model, with targets matched by calendar date (the MO_80/MO_26D shift(-h)
          defect is avoided by construction).
  MO_125/MO_126  conn_L4W edge was look-ahead (proposed REVERSED / RE-SCOPED); here the
          anchor is used as a starting point, not as a competitor.
  MO_127  per-cutoff STL index unusable on ~2 years; here no index is used -- seasonal
          shape is learned from week-of-year features and the item's own year-ago ratio.
  MO_54 / MO_57 (week_of_year sufficient for trees; holiday flags hurt). PROVISIONAL, old
          harness -> calendar features are week-of-year based.
  MO_29 / MO_129 review: tree count >= ~3,800 does not change results.

ARMS
  mo130     REFERENCE NEW ARM: one LightGBM for h = 1..13 predicting
            z = log1p(actual[t+h]) - log1p(anchor[t]); forecast = expm1(log1p(anchor)+z).
            anchor = Base U/S/W over the last 4 calendar weeks x current TDP (flat if the
            window has no usable TDP). Lapsed (>= 9 wks silent) and new series = 0.
  model     shipped production model -- MO_129 clean run, read from mo129_rows.parquet
  flat      last reported week (MO_129)
  conn_L4W  the anchor itself, no corrections (MO_129)

FEATURES (all from data <= the anchor week t; the target week t+h is <= the cutoff in
training): h; week-of-year of t and of t+h (int + sin/cos); month of t+h; log anchor;
last week vs anchor; L4W/L12W velocity trend; TDP level and 4/13-week change; ARP vs its
8-week mean; 13-week promo rate; promo flag one year before the target week; the item's
own year-ago shape log1p(base[t+h-52]) - log1p(base[t-52]); weeks since first sale; total
real selling weeks; channel, account, pack, brand, flavor. Recency weight RECENCY_SHAPE
(default 0: every year's turns count equally).

LEVELS: cell x week, account x month, portfolio x month (complete months), bias; by history
band (new / lapsed / low-TDP / <13 / 13-25 / 26-51 / 52+) and by origin; Jan-Mar and
Oct-Dec target weeks separately. Same 18 origins and scorer as MO_129 (MO_80 yardstick v2).

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1  Cell x week, existing items: mo130 beats flat by >= 1pp with a CI excluding 0.
      If it FAILS, learned corrections do not add item-level skill over last week.
  P2  Account x month: mo130 <= conn_L4W (the anchor it starts from). If it FAILS, the
      corrections hurt the level they were built on.
  P3  Jan-Mar target weeks: mo130 bias >= 0.92 (others ~0.83). If it FAILS, pooled
      week-of-year learning does not capture the New Year step-up.
  P4  mo130 beats the shipped model at cell x week in every band of 13+ weeks. If it
      FAILS, the direct anchor design does not fix the established-item deficit.
  P5  Portfolio x month: no significant difference between mo130 and flat. If it FAILS
      (mo130 significantly better), the planning level gains too.
  P6  A week-of-year feature (anchor or target) ranks in the top 5 by gain. If it FAILS,
      the model is not using seasonality the way the design intends.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import pickle
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"
import MO_80_quarterly_honest_backtest as M        # import asserts forecast + training parity

importlib.reload(M)
assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

OUT = Path("outputs/mo130_anchor_corrections.json")
OUT_ROWS = Path("outputs/mo130_rows.parquet")
MO129_ROWS = Path("outputs/mo129_rows.parquet")
ARMS = ["mo130", "model", "flat", "conn_L4W"]
H = M.HORIZON
TDP_FLOOR = 0.05
RECENCY_SHAPE = 0.0
CATS = ["channel_outlet", "retail_account", "pack_count", "source_brand", "spins_flavor_canonical"]
NUM_FEATS = ["h", "woy_t", "woy_y", "woy_y_sin", "woy_y_cos", "woy_t_sin", "woy_t_cos", "month_y",
             "log_anchor", "last_vs_anchor", "trend_4_12", "log_tdp", "tdp_chg4", "tdp_chg13",
             "arp_rel8", "promo_rate13", "promo_yago_target", "yago_shape", "wks_since_first",
             "selling_wks"]
FEATS = NUM_FEATS + CATS


def series_grid(tr: pd.DataFrame, cut_n: pd.Timestamp) -> pd.DataFrame:
    """Calendar-complete weekly grid per series up to the cutoff, with trailing features.

    Every quantity on row t uses only rows <= t (rolling windows end at t; shifts are
    backward), except the targets built later with an explicit forward shift.
    """
    cols = ["base_units", "tdp", "arp", "is_promo_week"]
    t = tr[M.GROUP_COLS + ["__time"] + cols + CATS].copy()
    t["__time"] = pd.to_datetime(t["__time"], utc=True).dt.tz_localize(None)
    for c in cols:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    out = []
    for key, g in t.groupby(M.GROUP_COLS, observed=True):
        g = g.set_index("__time").sort_index()
        idx = pd.date_range(g.index.min(), cut_n, freq="W-SUN")
        x = g[cols].reindex(idx)
        x["reported"] = g["base_units"].reindex(idx).notna()
        for c in CATS:
            x[c] = str(g[c].iloc[-1])
        x["key"] = [key] * len(x)
        out.append(x)
    x = pd.concat(out)
    x.index.name = "t"
    x = x.reset_index()
    G = lambda: x.groupby("key", sort=False)                 # fresh grouping after each add
    roll = lambda col, w, f: G()[col].transform(lambda s: getattr(s.rolling(w, min_periods=1), f)())
    ok = x["base_units"].notna() & x["tdp"].notna()
    x["_b"] = x["base_units"].where(ok, 0.0)
    x["_d"] = x["tdp"].where(ok, 0.0)
    for w in (4, 12):
        sb, sd = roll("_b", w, "sum"), roll("_d", w, "sum")
        x[f"vel{w}"] = np.where(sd > TDP_FLOOR, sb / sd.where(sd > 0, np.nan), np.nan)
    x["tdp_ff"] = G()["tdp"].ffill()
    x["base_ff"] = G()["base_units"].ffill()
    anchor = x["vel4"] * x["tdp_ff"]
    x["anchor"] = np.where(np.isfinite(anchor), anchor, x["base_ff"]).clip(min=0)
    x["log_anchor"] = np.log1p(x["anchor"])
    x["last_vs_anchor"] = np.log1p(x["base_ff"].fillna(0)) - x["log_anchor"]
    x["trend_4_12"] = np.log((x["vel4"] + 1e-6) / (x["vel12"] + 1e-6))
    x["log_tdp"] = np.log1p(x["tdp_ff"])
    for w in (4, 13):
        x[f"tdp_chg{w}"] = x["log_tdp"] - np.log1p(G()["tdp_ff"].shift(w))
    x["arp_ff"] = G()["arp"].ffill()
    x["arp_rel8"] = x["arp_ff"] / roll("arp_ff", 8, "mean")
    x["_p"] = x["is_promo_week"].fillna(0)
    x["promo_rate13"] = roll("_p", 13, "mean")
    x["wks_since_first"] = G().cumcount() + 1
    x["_s"] = (x["tdp"] > M.DIST_MIN_TDP).astype(int)
    x["selling_wks"] = G()["_s"].cumsum()
    x["base_lag52"] = G()["base_units"].shift(52)
    x["promo_lag52"] = G()["is_promo_week"].shift(52)
    x["woy_t"] = x["t"].dt.isocalendar().week.astype(int)
    return x


def add_horizon(x: pd.DataFrame, h: int, with_target: bool) -> pd.DataFrame:
    """Rows (anchor t, horizon h). Target = base_units at t+h on the CALENDAR grid."""
    gb = x.groupby("key", sort=False)
    r = x.copy()
    r["h"] = h
    ty = r["t"] + pd.Timedelta(weeks=h)
    r["date_y"] = ty
    r["woy_y"] = ty.dt.isocalendar().week.astype(int).values
    r["month_y"] = ty.dt.month.values
    for c in ("woy_y", "woy_t"):
        r[f"{c}_sin"] = np.sin(2 * np.pi * r[c] / 52)
        r[f"{c}_cos"] = np.cos(2 * np.pi * r[c] / 52)
    # own year-ago shape for the same two weeks: base[t+h-52] vs base[t-52] (both <= t)
    r["yago_shape"] = (np.log1p(gb["base_units"].shift(52 - h)) - np.log1p(r["base_lag52"]))
    r["promo_yago_target"] = gb["is_promo_week"].shift(52 - h)
    if with_target:
        r["y"] = gb["base_units"].shift(-h)          # calendar grid: exactly week t+h
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origins", default="", help="comma list of origin labels")
    ap.add_argument("--trees", type=int, default=None, help="cap; None = production cap")
    ap.add_argument("--recency", type=float, default=RECENCY_SHAPE)
    a = ap.parse_args()
    cap = a.trees or M.TREES_CAP

    feats_prod = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v11_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats_prod)
    base = pd.read_parquet(MO129_ROWS)
    origins = M.ORIGINS_MONTHLY
    if a.origins:
        want = {s.strip() for s in a.origins.split(",")}
        origins = [o for o in origins if o[0] in want]

    print("MO_130 - Connor anchor + learned corrections (direct, h = 1..13)")
    print(f"  {len(origins)} origins | cap {cap} | recency {a.recency}\n")
    params = dict(objective="quantile", alpha=0.5, **M.PROD_LGBM)
    out_rows, imp_tot, t0 = [], pd.Series(dtype=float), time.time()
    for lbl, c, s, e in origins:
        cut = M._utc(c)
        cut_n = cut.tz_localize(None)
        tr = df[df["__time"] <= cut]
        x = series_grid(tr, cut_n)
        rows = []
        for h in range(1, H + 1):
            r = add_horizon(x, h, with_target=True)
            r = r[r["reported"] & r["y"].notna() & np.isfinite(r["log_anchor"])]
            rows.append(r)
        d = pd.concat(rows, ignore_index=True)
        assert (d["date_y"] <= cut_n).all(), "a training target lies after the cutoff"
        d["z"] = np.log1p(d["y"].clip(lower=0)) - d["log_anchor"]
        for cc in CATS:
            d[cc] = d[cc].astype("category")
        wk = (cut_n - d["t"]).dt.days / 7
        w = np.exp(-a.recency * wk.clip(lower=0).values)
        is_val = (d["date_y"] > cut_n - pd.Timedelta(weeks=M.TRAIN_VAL_WEEKS)).values
        m = lgb.LGBMRegressor(n_estimators=cap, **params)
        m.fit(d.loc[~is_val, FEATS], d.loc[~is_val, "z"], sample_weight=w[~is_val],
              eval_set=[(d.loc[is_val, FEATS], d.loc[is_val, "z"])], eval_metric="quantile",
              callbacks=[lgb.early_stopping(M.EARLY_STOP_PATIENCE, verbose=False),
                         lgb.log_evaluation(-1)])
        best = int(m.best_iteration_ or cap)
        fm = lgb.LGBMRegressor(n_estimators=best, **params).fit(d[FEATS], d["z"], sample_weight=w)
        imp = pd.Series(fm.booster_.feature_importance("gain"), index=FEATS)
        imp_tot = imp_tot.add(imp / imp.sum(), fill_value=0)

        # forecast from the cutoff week for every series
        fx = x[x["t"] == cut_n]
        preds = []
        for h in range(1, H + 1):
            r = add_horizon(x, h, with_target=False)
            r = r[r["t"] == cut_n].copy()
            for cc in CATS:
                r[cc] = pd.Categorical(r[cc], categories=d[cc].cat.categories)
            z = fm.predict(r[FEATS])
            r["mo130"] = np.clip(np.expm1(r["log_anchor"].values + z), 0, None)
            preds.append(r[["key", "date_y", "mo130"]])
        p = pd.concat(preds)
        p["series"] = [" | ".join(map(str, k)) for k in p["key"]]
        p["date"] = pd.to_datetime(p["date_y"]).dt.tz_localize("UTC")
        b = base[base["origin"] == lbl].copy()
        b["date"] = pd.to_datetime(b["date"], utc=True)
        b = b.merge(p[["series", "date", "mo130"]], on=["series", "date"], how="left")
        zero = b["is_new"] | (b["band"] == "lapsed")
        b.loc[zero, "mo130"] = 0.0
        miss = int(b["mo130"].isna().sum())
        b = b[b["mo130"].notna()]
        out_rows.append(b)
        print(f"  {lbl}: {len(d):,} training rows ({is_val.mean():.0%} val) | best_iter {best}"
              f"{' (cap)' if best >= cap else ''} | {len(fx):,} series forecast | "
              f"{miss} eval rows w/o forecast | {time.time() - t0:,.0f}s")

    r = pd.concat(out_rows, ignore_index=True)
    r.to_parquet(OUT_ROWS)
    ex = r[~r["is_new"]]
    res = {"existing": M.score_levels(ex, ARMS), "planning_total": M.score_levels(r, ARMS)}
    E = res["existing"]
    print("\n=== EXISTING SERIES (headline) ===")
    print(f"  {'arm':<9s}" + "".join(f"{l.split(' x ')[0][:10]:>12s}" for l, _ in M.LEVELS_V2) + "    bias")
    for arm in ARMS:
        print(f"  {arm:<9s}" + "".join(f"{E[l][arm]:>12.2f}" for l, _ in M.LEVELS_V2)
              + f"   {E['portfolio_bias'][arm]:.3f}")
    for l, _ in M.LEVELS_V2:
        print(f"  BY HISTORY BAND, {l}")
        for bnd, v in E[l]["by_band"].items():
            print(f"    {bnd:<10s} n={v['n']:>7,}  " + "  ".join(f"{arm}={v[arm]:.1f}" for arm in ARMS))
    print("  BY ORIGIN, portfolio x month")
    for o, v in E["by_origin_pm"].items():
        print(f"    {o}  " + "  ".join(f"{arm}={v[arm]:.1f}" for arm in ARMS))

    q = ex.copy()
    q["mth"] = pd.to_datetime(q["date"], utc=True).dt.month
    res["season_bias"] = {}
    for name, mm in (("Jan-Mar", (1, 2, 3)), ("Oct-Dec", (10, 11, 12))):
        sub = q[q["mth"].isin(mm)]
        if len(sub):
            res["season_bias"][name] = {arm: float(sub[arm].sum() / sub["actual"].sum()) for arm in ARMS}
            print(f"  {name} target weeks, bias: "
                  + ", ".join(f"{k}={v:.3f}" for k, v in res["season_bias"][name].items()))

    print("\nMARGINS OF ERROR (existing; moving-block bootstrap, block = 3 origins)")
    res["ci"] = {}
    for y in ("flat", "conn_L4W", "model"):
        for l, _ in M.LEVELS_V2:
            bb = M.bootstrap_diff(ex, "mo130", y, level=l, n=2000)
            res["ci"][f"mo130-{y} | {l}"] = bb
            print(f"  mo130 - {y:<9s} {l:<18s} {bb['diff']:+6.2f}pp  95% CI "
                  f"[{bb['ci95'][0]:+.2f}, {bb['ci95'][1]:+.2f}]{'  *' if bb['significant'] else ''}")

    imp = (imp_tot / len(origins)).sort_values(ascending=False)
    res["importance"] = imp.round(4).to_dict()
    print("\nTOP FEATURES by mean gain share: " + ", ".join(f"{k} {v:.2f}" for k, v in imp.head(8).items()))

    CW, AM, PM = "cell x week", "account x month", "portfolio x month"
    ci = res["ci"]
    checks = [
        ("P1", ci[f"mo130-flat | {CW}"]["diff"] <= -1.0 and ci[f"mo130-flat | {CW}"]["ci95"][1] < 0,
         f"cw mo130 - flat {ci[f'mo130-flat | {CW}']['diff']:+.2f} CI {ci[f'mo130-flat | {CW}']['ci95']}"),
        ("P2", E[AM]["mo130"] <= E[AM]["conn_L4W"], f"am mo130 {E[AM]['mo130']:.2f} vs L4W {E[AM]['conn_L4W']:.2f}"),
        ("P3", res["season_bias"].get("Jan-Mar", {}).get("mo130", 0) >= 0.92,
         f"Jan-Mar bias mo130 {res['season_bias'].get('Jan-Mar', {}).get('mo130', float('nan')):.3f}"),
        ("P4", all(E[CW]["by_band"].get(bnd, {}).get("mo130", np.inf) < E[CW]["by_band"].get(bnd, {}).get("model", -np.inf)
                   for bnd in ("13-25 wks", "26-51 wks", "52+ wks")),
         "cw mo130/model by band: " + ", ".join(
             f"{bnd} {E[CW]['by_band'].get(bnd, {}).get('mo130', np.nan):.1f}/{E[CW]['by_band'].get(bnd, {}).get('model', np.nan):.1f}"
             for bnd in ("13-25 wks", "26-51 wks", "52+ wks"))),
        ("P5", not ci[f"mo130-flat | {PM}"]["significant"], f"pm mo130 - flat {ci[f'mo130-flat | {PM}']['diff']:+.2f}"),
        ("P6", any(f in list(imp.head(5).index) for f in ("woy_t", "woy_y", "woy_y_sin", "woy_y_cos", "woy_t_sin", "woy_t_cos")),
         "top 5: " + ", ".join(imp.head(5).index)),
    ]
    print("\nPREDICTIONS")
    res["predictions"] = {}
    for pid, ok, msg in checks:
        tag = "HOLDS" if ok else "FAILS"
        res["predictions"][pid] = {"result": tag, "detail": msg}
        print(f"  {pid} {tag:<6s} {msg}")
    b52 = E[CW]["by_band"].get("52+ wks", {})
    if b52 and b52["mo130"] > b52["flat"]:
        print(f"  ⚠️ blocker 0.3 analog: mo130 worse than flat on 52+ ({b52['mo130']:.1f} vs {b52['flat']:.1f})")
    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT} and {OUT_ROWS}  ({time.time() - t0:,.0f}s)")


if __name__ == "__main__":
    main()
