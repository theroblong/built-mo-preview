#!/usr/bin/env python
"""MO_129 - Measured honestly, how do the shipped model, flat and Connor's methods compare?

WHERE THIS CAME FROM
--------------------
Task C of the CPU plan (docs/FORECAST_ROADMAP.md step 1; Jason approved 2026-10-07). Every
backtest from MO_80 to MO_128 measured a different model from the one production ships:
  - an 800-tree cap with in-sample early stopping (production: 6000, time holdout, refit)
  - no recency weights and lr 0.05 (production: 0.02 recency, lr 0.04)
  - five promo features computed over the whole panel (look-ahead) and three donor
    features from a full-history cannibalization scoring
  - per-step inputs (lag4, lag13, ARP path, promo flags/cadence, weeks_since_launch)
    frozen at the anchor, which production updates every week
  - a Monday Q3 2026 cutoff, 7 quarterly origins (portfolio x month n=9-21), a seasonal
    index with look-ahead (MO_127), and history bands that counted rows
All of that is fixed in MO_80 (commits 08a7240 .. a21e9fb; two skeptic reviews). This run
is the honest reference every later experiment (MO_130 onward) is compared against.

PRIOR WORK (docs/SETTLED_FINDINGS.md, DRAFT; "Proposed changes, PENDING review")
--------------------------------------------------------------------------------
  MO_127  honest standings at 800 trees: cell x week conn_L4W 32.5, flat 32.8, model 36.7;
          portfolio x month ~tie (16.4 / 16.0 / 17.3). PROVISIONAL; old harness.
  MO_128  Connor L4W best on 52+ wk PUFF (27.4 vs model 33.9); L12W vs L4W flips by quarter.
          PROVISIONAL; old harness.
  MO_125 / MO_126 / README 223  proposed REVERSED / RE-SCOPED (look-ahead index).
  MO_29   q50 early stopping converges ~4,593 trees; production v11 q50 hits its 6000 cap.
  Reopen-if met: every one of these was scored on the pre-fix harness.
  Method rules (SETTLED): all 3 levels, history-band breakout, parity at import.

ARMS (lapsed series = 0 for every arm, production's rule; new series = 0 for every arm)
  model     REFERENCE: MO_27 production path via MO_80.run_production -- production
            training (train_like_production), MO_SEASONAL_MODE=step (asserted), honest
            seasonal index rebuilt at each cutoff, donor features neutralized
  flat      last reported base_units at or before the cutoff
  conn_L4W  Base U/S/W over the last 4 CALENDAR weeks to the cutoff x current TDP
  conn_L12W same over 12 calendar weeks (Connor's default)
  (Connor arms fall back to flat when the window has no usable TDP.)

LEVELS: cell x week, account x month, portfolio x month (complete months only), bias at
portfolio x month; every level by history band (new / lapsed / low-TDP / <13 / 13-25 /
26-51 / 52+ wks) and by origin. Headline = existing series; the planning total including
new series (scored at 0) is reported alongside. Moving-block bootstrap CIs (block = 3
origins) for model-flat, model-conn_L4W, conn_L4W-flat. Seed noise: the model retrained
with seeds 1 and 2 at every third origin.

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1  Existing series, cell x week: |flat - conn_L4W| < 1pp (MO_127: 32.8 vs 32.5).
      If it FAILS, Connor's anchor and flat genuinely separate at item level.
  P2  The model at production training scores at least 2pp better at cell x week than
      MO_127's honest 800-tree model (36.7). If it FAILS, under-training was not the
      main reason the model lost.
  P3  Model is still worse than conn_L4W at cell x week in BOTH the 26-51 and 52+ bands.
      If it FAILS, the fixed model catches Connor's anchor on established items.
  P4  Portfolio x month: none of the three CIs excludes 0. If it FAILS, one method
      genuinely wins at the planning level.
  P5  Seed noise: across seeds 42/1/2 the model's portfolio x month wMAPE varies by
      < 0.5pp (max - min, on the seed origins). If it FAILS, single-seed comparisons
      need wider margins.
  P6  Every arm under-forecasts Jan-Mar target months: portfolio bias < 0.8 for all four.
      If it FAILS, some method already handles the New Year turn.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"           # production (MO_27:780-803); blocker in review 2
import MO_80_quarterly_honest_backtest as M        # import asserts forecast + training parity

importlib.reload(M)
assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

OUT = Path("outputs/mo129_rebaseline.json")
OUT_ROWS = Path("outputs/mo129_rows.parquet")
ARMS = ["model", "flat", "conn_L4W", "conn_L12W"]
SEED_ORIGIN_STEP = 3
EXTRA_SEEDS = (1, 2)
TDP_FLOOR = 0.05


def connor(g: pd.DataFrame, cut_n: pd.Timestamp, w: int, fallback: float) -> float:
    """Base U/S/W over the last `w` calendar weeks to the cutoff x current TDP."""
    win = g[g["_t"] > cut_n - pd.Timedelta(weeks=w)]
    b = pd.to_numeric(win["base_units"], errors="coerce")
    t = pd.to_numeric(win["tdp"], errors="coerce")
    ok = b.notna() & t.notna()
    st = t[ok].sum()
    doors = pd.to_numeric(g["tdp"], errors="coerce").dropna()
    if st <= TDP_FLOOR or doors.empty:
        return fallback
    return max(0.0, float(b[ok].sum() / st) * float(doors.iloc[-1]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=None, help="None = production cap")
    ap.add_argument("--origins", default="", help="comma list of origin labels, e.g. 2026-01")
    ap.add_argument("--no-seeds", action="store_true", help="skip the seed-noise refits")
    a = ap.parse_args()

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v11_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    origins = M.ORIGINS_MONTHLY
    if a.origins:
        want = {s.strip() for s in a.origins.split(",")}
        origins = [o for o in origins if o[0] in want]
    seed_origins = {o[0] for i, o in enumerate(M.ORIGINS_MONTHLY) if i % SEED_ORIGIN_STEP == 0}

    print("MO_129 - honest re-baseline: shipped model vs flat vs Connor L4W / L12W")
    print(f"  {len(origins)} origins, trees cap {a.trees or M.TREES_CAP}, mode {M.SEASONAL_MODE}\n")
    recs, t0 = [], time.time()
    for i, (lbl, c, s, e) in enumerate(origins):
        cut, qs = M._utc(c), M._utc(s)
        qe = M._utc(e) + pd.Timedelta(days=6)
        ev = M.build_eval_rows(df, cut, s, e)
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        ek = set(ev.loc[~ev["is_new"], "key"])
        seas = M.seasonal_index_at(cut)
        M.TRAIN_SEED = None
        p = M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, seas)
        fit = M.FIT_LOG[-1]
        seeds = {}
        if lbl in seed_origins and not a.no_seeds:
            for sd in EXTRA_SEEDS:
                M.TRAIN_SEED = sd
                seeds[sd] = M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, seas)
            M.TRAIN_SEED = None

        tr = df[df["__time"] <= cut].copy()
        tr["_t"] = pd.to_datetime(tr["__time"], utc=True).dt.tz_localize(None)
        cut_n = cut.tz_localize(None)
        base = {}
        for key, g in tr.groupby(M.GROUP_COLS, observed=True):
            if key not in ek:
                continue
            bu = pd.to_numeric(g["base_units"], errors="coerce").dropna()
            last = float(bu.iloc[-1]) if len(bu) else 0.0
            base[key] = (last, connor(g, cut_n, 4, last), connor(g, cut_n, 12, last))

        ev["origin"] = lbl
        zero = ev["is_new"] | (ev["band"] == "lapsed")
        ev["model"] = [0.0 if z else p.get((k, d), np.nan)
                       for k, d, z in zip(ev["key"], ev["date"], zero)]
        for j, arm in enumerate(("flat", "conn_L4W", "conn_L12W")):
            ev[arm] = [0.0 if z else base.get(k, (np.nan,) * 3)[j]
                       for k, z in zip(ev["key"], zero)]
        for sd, ps in seeds.items():
            ev[f"model_seed{sd}"] = [0.0 if z else ps.get((k, d), np.nan)
                                     for k, d, z in zip(ev["key"], ev["date"], zero)]
        miss = int(ev[ARMS].isna().any(axis=1).sum())
        ev = ev[ev[ARMS].notna().all(axis=1)]
        recs.append(ev)
        print(f"  {lbl}: cutoff {c} | {len(ev):,} series-weeks, new {ev['is_new'].mean():.1%} "
              f"of rows | index {len(seas)} wks | fit best_iter {fit['best_iteration']}"
              f"{' (cap)' if fit['hit_cap'] else ''}{' cached' if fit.get('cached') else ''}"
              f" | dropped {miss} rows w/o a prediction | {time.time() - t0:,.0f}s")

    r = pd.concat(recs, ignore_index=True)
    r["series"] = [" | ".join(map(str, k)) for k in r["key"]]          # GROUP_COLS, readable
    r.drop(columns=["key"]).assign(account=lambda x: x["account"].astype(str)).to_parquet(OUT_ROWS)
    ex = r[~r["is_new"]]

    def show(sc, title):
        print(f"\n=== {title} ===")
        print(f"  {'arm':<11s}" + "".join(f"{l.split(' x ')[0][:10]:>12s}" for l, _ in M.LEVELS_V2)
              + "    bias")
        for arm in ARMS:
            print(f"  {arm:<11s}" + "".join(f"{sc[l][arm]:>12.2f}" for l, _ in M.LEVELS_V2)
                  + f"   {sc['portfolio_bias'][arm]:.3f}")
        print("  (n: " + ", ".join(f"{l} {sc[l]['n']:,}" for l, _ in M.LEVELS_V2)
              + f"; partial-month rows excluded from month levels {sc['partial_month_rows_excluded']:,})")
        for l, _ in M.LEVELS_V2:
            print(f"  BY HISTORY BAND, {l}")
            for b, v in sc[l]["by_band"].items():
                print(f"    {b:<10s} n={v['n']:>7,}  " + "  ".join(f"{arm}={v[arm]:.1f}" for arm in ARMS))
        print("  BY ORIGIN, portfolio x month")
        for o, v in sc["by_origin_pm"].items():
            print(f"    {o}  " + "  ".join(f"{arm}={v[arm]:.1f}" for arm in ARMS))

    res = {"existing": M.score_levels(ex, ARMS), "planning_total": M.score_levels(r, ARMS)}
    show(res["existing"], "EXISTING SERIES (headline)")
    show(res["planning_total"], "PLANNING TOTAL incl. new series at 0")

    print("\nMARGINS OF ERROR (existing series; moving-block bootstrap, block = 3 origins)")
    res["ci"] = {}
    for x, y in (("model", "flat"), ("model", "conn_L4W"), ("conn_L4W", "flat")):
        for l, _ in M.LEVELS_V2:
            b = M.bootstrap_diff(ex, x, y, level=l, n=2000)
            res["ci"][f"{x}-{y} | {l}"] = b
            print(f"  {x:>8s} - {y:<8s} {l:<18s} {b['diff']:+6.2f}pp  95% CI "
                  f"[{b['ci95'][0]:+.2f}, {b['ci95'][1]:+.2f}]{'  *' if b['significant'] else ''}")

    seed_cols = [f"model_seed{s}" for s in EXTRA_SEEDS if f"model_seed{s}" in ex.columns]
    if seed_cols:
        sx = ex[ex[seed_cols].notna().all(axis=1)]
        sc = M.score_levels(sx, ["model"] + seed_cols)
        vals = [sc["portfolio x month"][c] for c in ["model"] + seed_cols]
        res["seed_noise_pm"] = {"values": vals, "range": float(max(vals) - min(vals)),
                                "origins": sorted(sx["origin"].unique())}
        print(f"\nSEED NOISE (model, {len(res['seed_noise_pm']['origins'])} origins), portfolio x month: "
              + ", ".join(f"{v:.2f}" for v in vals) + f" -> range {res['seed_noise_pm']['range']:.2f}pp")

    q = ex.copy()
    q["m"] = pd.to_datetime(q["date"], utc=True).dt.month
    q1 = q[q["m"] <= 3]
    res["q1_bias"] = {arm: float(q1[arm].sum() / q1["actual"].sum()) for arm in ARMS} if len(q1) else {}
    print("\nJan-Mar target weeks, bias: " + ", ".join(f"{k}={v:.3f}" for k, v in res["q1_bias"].items()))

    E, CW, PM = res["existing"], "cell x week", "portfolio x month"
    checks = [
        ("P1", abs(E[CW]["flat"] - E[CW]["conn_L4W"]) < 1.0,
         f"cw flat {E[CW]['flat']:.2f} vs conn_L4W {E[CW]['conn_L4W']:.2f}"),
        ("P2", E[CW]["model"] <= 36.7 - 2.0, f"cw model {E[CW]['model']:.2f} vs MO_127 36.7 (pred <= 34.7)"),
        ("P3", all(E[CW]["by_band"].get(b, {}).get("model", np.nan) > E[CW]["by_band"].get(b, {}).get("conn_L4W", np.nan)
                   for b in ("26-51 wks", "52+ wks")),
         "cw by band model vs conn_L4W: " + ", ".join(
             f"{b} {E[CW]['by_band'].get(b, {}).get('model', np.nan):.1f}/{E[CW]['by_band'].get(b, {}).get('conn_L4W', np.nan):.1f}"
             for b in ("26-51 wks", "52+ wks"))),
        ("P4", not any(v["significant"] for k, v in res["ci"].items() if k.endswith(PM)),
         "pm CIs: " + ", ".join(f"{k.split(' |')[0]} {'*' if v['significant'] else 'ns'}"
                                for k, v in res["ci"].items() if k.endswith(PM))),
        ("P5", (res.get("seed_noise_pm", {}).get("range", np.nan) < 0.5) if seed_cols else None,
         f"seed range {res.get('seed_noise_pm', {}).get('range', float('nan')):.2f}pp"),
        ("P6", bool(res["q1_bias"]) and all(v < 0.8 for v in res["q1_bias"].values()),
         f"Jan-Mar bias {res['q1_bias']}"),
    ]
    print("\nPREDICTIONS")
    res["predictions"] = {}
    for pid, ok, msg in checks:
        tag = "UNTESTABLE" if ok is None else ("HOLDS" if ok else "FAILS")
        res["predictions"][pid] = {"result": tag, "detail": msg}
        print(f"  {pid} {tag:<10s} {msg}")
    b52 = E[CW]["by_band"].get("52+ wks", {})
    if b52 and b52["model"] > b52["flat"]:
        print(f"  ⚠️ BLOCKER still open: model worse than flat on 52+ wk series "
              f"({b52['model']:.1f} vs {b52['flat']:.1f})")
    res["fit_log"] = M.FIT_LOG
    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT} and {OUT_ROWS}  ({time.time() - t0:,.0f}s)")


if __name__ == "__main__":
    main()
