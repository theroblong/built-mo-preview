#!/usr/bin/env python
"""MO_135 - A per-store year-over-year ratio for the recursive seasonal blend (replacing the clip).

WHERE THIS CAME FROM
--------------------
MO_134 skeptic (2026-10-10): removing the 0.5-2.0 clip on the year-over-year ratio looked harmful
(+13.24 at item x week), but 95% of that came from ~116 series-origins whose year-ago week predates
distribution (1-20 units in a handful of stores -> ratios of 200-1,375). Where distribution was
comparable a year ago, no-clip cost only +0.14. So the clip is a crude guard against distribution
change; the principled fix compares SALES PER STORE year over year and rescales last year's week
to today's store count. MO_134 also found blend weight 0.30 best within 4 of 5 bands at portfolio
x month -- a safer ratio may make a stronger seasonal pull affordable (Jason: learn seasonal shape,
not bandaids). Judged by docs/PRODUCTION_DECISION_PREREG.md Amendment 1 (2026-10-10, Jason): the
recent forecast dates (2025-12 on) first, consistency counts, 2025 is a no-harm check.

PRIOR WORK (docs/SETTLED_FINDINGS.md incl. pending proposals; README 233-235)
  MO_134  rec 35.46/22.89/13.75; no-clip 48.70 (artifact); rec_fair 37.78; blend 0.30 wins 4/5 bands
          at band-separated pm; production row anchor is 51 weeks back (off-by-one).
  MO_133  2026-only: direct_avg5 28.8/16.2/6.5; rec_dir5 28.5/17.2/8.9 (beats last value at am 6/6);
          recursive alone 34.6/22.5/14.1 (0/6).
  MO_115 / history-length FACT candidate: per-store (TDP-normalized) comparisons are the stable unit.

ARMS (recursive MO_80.run_production on the GPU worker; one trained model per origin, shared)
  rec          production (YOY_MODE units, clip 0.5-2.0, blend 0.10, rows year-ago)
  rec_w30      production but blend weight 0.30 (units ratio) -- isolates the weight change
  rec_velc     per-store ratio, calendar year-ago rescaled to today's stores, clip 0.5-2.0 kept
  rec_vel      per-store ratio, no clip
  rec_vel_w20  per-store ratio, no clip, blend 0.20
  rec_vel_w30  per-store ratio, no clip, blend 0.30
  combinations at scoring (50/50 with MO_133's worker direct_avg5): rec_dir5 (existing), vel_dir5
  (rec_vel), velw30_dir5 (rec_vel_w30). Status quo: MO_134's worker direct_served.

LEVELS: cell x week, account x month, portfolio x month scored within history bands; BY HISTORY
BAND; 13+ weeks; per-year Jan-Mar / Oct-Dec bias; per-origin consistency; recent (2025-12 on)
first, all origins and 2025 as the no-harm check.

PREDICTIONS, RECORDED BEFORE ANY RUN:
  P1  The per-store ratio removes the catastrophe: |rec_vel - rec| < 0.5 at item x week, all origins
      (unclipped units ratio was +13.24).
  P2  rec_vel_w30 beats rec at band-separated portfolio x month on the recent origins.
  P3  No recursive variant beats direct_avg5 at account x month on the recent origins.
  P4  vel_dir5 is within 0.3 of rec_dir5 (or better) at account x month on the recent origins.
  P5  Jan-Mar 2026 bias: rec_vel_w30 is closer to 1.00 than rec (0.90).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"
import MO_80_quarterly_honest_backtest as M        # import asserts forecast + training parity
import MO_133_ensembles as E                         # band-separated scoring, panel loader
import MO_134_recursive_fair_settings as B           # compute machinery (worker), decision helpers

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

ARMS = {
    "rec": {},
    "rec_w30": {"SEASONAL_BLEND_WEIGHT": 0.30},
    "rec_velc": {"YOY_MODE": "velocity"},
    "rec_vel": {"YOY_MODE": "velocity", "YOY_CLIP": None},
    "rec_vel_w20": {"YOY_MODE": "velocity", "YOY_CLIP": None, "SEASONAL_BLEND_WEIGHT": 0.20},
    "rec_vel_w30": {"YOY_MODE": "velocity", "YOY_CLIP": None, "SEASONAL_BLEND_WEIGHT": 0.30},
}
# Module-level so spawned worker processes (which import this module) get the same settings.
B.ARMS, B.PREFIX = ARMS, "mo135"
OUT = Path("outputs/mo135_per_store_yoy.json")
OUT_ROWS = Path("outputs/mo135_rows.parquet")
RECENT = "2025-12"


def compute_origin(*args, **kw):                     # top-level so spawn can pickle it
    return B.compute_origin(*args, **kw)


def compute(origins, arms, out_dir, feats_r, feats_d, threads, parallel):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    if parallel <= 1:
        return [compute_origin(o, arms, out_dir, feats_r, feats_d, threads) for o in origins]
    with ProcessPoolExecutor(max_workers=parallel, mp_context=get_context("spawn")) as ex:
        futs = [ex.submit(compute_origin, o, arms, out_dir, feats_r, feats_d, threads) for o in origins]
        return [f.result() for f in futs]


def _load(arm, dirs, prefix):
    parts = [pd.read_parquet(f).assign(origin=f.stem.rsplit("_", 1)[1])
             for d in dirs for f in sorted(Path(d).glob(f"{prefix}_{arm}_????-??.parquet"))]
    if not parts:
        raise SystemExit(f"no results for {prefix} {arm}")
    cp = pd.concat(parts, ignore_index=True)
    cp["date"] = pd.to_datetime(cp["date"], utc=True)
    assert not cp.duplicated(["origin", "series", "date"]).any(), arm
    return cp


def score(dirs135, dirs134, dirs133) -> None:
    t0 = time.time()
    r = pd.read_parquet(E.BASE_ROWS).reset_index(drop=True)
    r = r.drop(columns=[c for c in r.columns if c.startswith("model_seed")] + ["model"], errors="ignore")
    r["date"] = pd.to_datetime(r["date"], utc=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    sources = [(a, dirs135, "mo135") for a in ARMS] + [("direct_served", dirs134, "mo134")] + \
              [(f"direct_fixed_s{k}", dirs133, "mo133") for k in (42, 1, 2, 3, 4)]
    for arm, dirs, prefix in sources:
        cp = _load(arm, dirs, prefix)
        n0 = len(r)
        r = r.merge(cp[["origin", "series", "date", arm]], on=["origin", "series", "date"], how="left")
        assert len(r) == n0
        miss = np.isnan(r[arm].values) & ~zero
        print(f"  {arm}: origins {cp['origin'].nunique()}, fell back to flat {int(miss.sum()):,}")
        r[arm] = np.where(zero, 0.0, np.where(miss, r["flat"], r[arm]))
    r["direct_avg5"] = r[[f"direct_fixed_s{k}" for k in (42, 1, 2, 3, 4)]].mean(axis=1)
    r["rec_dir5"] = 0.5 * r["rec"] + 0.5 * r["direct_avg5"]
    r["vel_dir5"] = 0.5 * r["rec_vel"] + 0.5 * r["direct_avg5"]
    r["velw30_dir5"] = 0.5 * r["rec_vel_w30"] + 0.5 * r["direct_avg5"]
    arms = ["flat", "conn_L4W", "direct_served", "direct_avg5"] + list(ARMS) + ["rec_dir5", "vel_dir5", "velw30_dir5"]
    r.to_parquet(OUT_ROWS)
    ex = r[~r["is_new"]]
    rec = ex[ex["origin"] >= RECENT]
    old = ex[ex["origin"] < RECENT]
    res = {"all": M.score_levels(ex, arms), "recent": M.score_levels(rec, arms), "2025": M.score_levels(old, arms),
           "arms": arms}
    for name in ("recent", "all"):
        S = res[name]
        print(f"\n=== {name.upper()} origins, existing series: cw / am / pm / pm-by-band | bias ===")
        sub = rec if name == "recent" else ex
        for x in sorted(arms, key=lambda k: S["account x month"][k]):
            pb = 0.0 if x == "flat" else E.band_separated_diff(sub, x, "flat")["diff"]  # by-band diff vs flat
            print(f"  {x:<14s}{S['cell x week'][x]:7.2f}{S['account x month'][x]:7.2f}{S['portfolio x month'][x]:7.2f}"
                  f"   (pm by band vs flat {pb:+.2f})   bias {S['portfolio_bias'][x]:.3f}")
        for lvl, _ in M.LEVELS_V2:
            print(f"  BY HISTORY BAND, {lvl} (<13 / 13-25 / 26-51 / 52+ wks)")
            for b, v in S[lvl]["by_band"].items():
                print(f"    {b:<10s} n={v['n']:>7,}  " + "  ".join(
                    f"{x}={v[x]:.1f}" for x in ("flat", "rec", "rec_vel", "rec_vel_w30", "direct_avg5", "rec_dir5", "vel_dir5")))
    # consistency on the recent origins: per-origin account x month wins vs the status quo and vs rec
    pm = M._prep_scoring(rec, arms)
    g = pm[pm["full_month"]].groupby(["origin", "account", "month"])[["actual"] + arms].sum().reset_index()
    w = lambda d, c: np.abs(d["actual"] - d[c]).sum() / d["actual"].sum()
    res["consistency_recent_am"] = {x: {"vs_direct_served": int(sum(w(d, x) < w(d, "direct_served") for _, d in g.groupby("origin"))),
                                        "vs_flat": int(sum(w(d, x) < w(d, "flat") for _, d in g.groupby("origin"))),
                                        "n": int(g["origin"].nunique())} for x in arms}
    print("\nCONSISTENCY, recent origins, account x month wins (vs served direct / vs last value):")
    for x in arms:
        c = res["consistency_recent_am"][x]
        print(f"  {x:<14s} {c['vs_direct_served']}/{c['n']}  {c['vs_flat']}/{c['n']}")
    res["season_bias"] = B.season_bias(ex, arms)
    print("\nSEASONAL BIAS PER YEAR")
    for k, v in res["season_bias"].items():
        print(f"  {k:<13s} " + "  ".join(f"{a}={v[a]:.2f}" for a in ("flat", "rec", "rec_w30", "rec_vel", "rec_vel_w30",
                                                                     "direct_served", "direct_avg5", "rec_dir5", "vel_dir5")))
    res["ci_recent"] = {}
    print("\nDIFFERENCES on recent origins (block bootstrap; 6 overlapping origins = indicative only)")
    for x, y in (("rec_vel", "rec"), ("rec_vel_w30", "rec"), ("rec_w30", "rec"), ("vel_dir5", "rec_dir5"),
                 ("velw30_dir5", "rec_dir5"), ("rec_dir5", "direct_served"), ("direct_avg5", "direct_served")):
        row = [M.bootstrap_diff(rec, x, y, level=l, n=2000) for l, _ in M.LEVELS_V2]
        pb = E.band_separated_diff(rec, x, y)
        res["ci_recent"][f"{x}-{y}"] = {"levels": row, "pm_by_band": pb}
        f = lambda b: f"{b['diff']:+6.2f} [{b['ci95'][0]:+.1f},{b['ci95'][1]:+.1f}]"
        print(f"  {x:>12s} - {y:<13s} " + "  ".join(f(b) for b in row) + f"   pm/band {f(pb)}")
    A, R = res["all"], res["recent"]
    CW, AM, PM = "cell x week", "account x month", "portfolio x month"
    jm26 = res["season_bias"].get("Jan-Mar 2026", {})
    checks = [
        ("P1", abs(A[CW]["rec_vel"] - A[CW]["rec"]) < 0.5, f"all cw rec_vel {A[CW]['rec_vel']:.2f} vs rec {A[CW]['rec']:.2f}"),
        ("P2", res["ci_recent"]["rec_vel_w30-rec"]["pm_by_band"]["diff"] < 0,
         f"recent pm-by-band rec_vel_w30 - rec {res['ci_recent']['rec_vel_w30-rec']['pm_by_band']['diff']:+.2f}"),
        ("P3", all(R[AM][x] >= R[AM]["direct_avg5"] for x in ARMS),
         f"recent am direct_avg5 {R[AM]['direct_avg5']:.2f}, best recursive {min(R[AM][x] for x in ARMS):.2f}"),
        ("P4", R[AM]["vel_dir5"] <= R[AM]["rec_dir5"] + 0.3, f"recent am vel_dir5 {R[AM]['vel_dir5']:.2f} vs rec_dir5 {R[AM]['rec_dir5']:.2f}"),
        ("P5", bool(jm26) and abs(jm26["rec_vel_w30"] - 1) < abs(jm26["rec"] - 1),
         f"Jan-Mar 2026 bias rec_vel_w30 {jm26.get('rec_vel_w30', np.nan):.3f} vs rec {jm26.get('rec', np.nan):.3f}"),
    ]
    print("\nPREDICTIONS")
    res["predictions"] = {}
    for pid, ok, msg in checks:
        res["predictions"][pid] = {"result": "HOLDS" if ok else "FAILS", "detail": msg}
        print(f"  {pid} {'HOLDS' if ok else 'FAILS':<6s} {msg}")
    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT} and {OUT_ROWS} ({time.time() - t0:,.0f}s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["compute", "score"])
    ap.add_argument("--origins", default="")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo135_cache"))
    ap.add_argument("--feats-dir", default="outputs")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--results135", default="")
    ap.add_argument("--results134", default="")
    ap.add_argument("--results133", default="")
    a = ap.parse_args()
    if a.cmd == "score":
        sp = lambda s: [x for x in s.split(",") if x]
        score(sp(a.results135), sp(a.results134), sp(a.results133))
        return
    origins = [o for o in a.origins.split(",") if o] or [o[0] for o in M.ORIGINS_MONTHLY]
    fd = Path(a.feats_dir)
    feats_r = json.loads((fd / "feats_recursive.json").read_text())
    feats_d = list(json.loads((fd / "direct_multihorizon_metrics_v11d.json").read_text())["features_used"])
    t0 = time.time()
    summary = compute(origins, a.arms.split(","), a.out, feats_r, feats_d, a.threads, a.parallel)
    Path(a.out, f"mo135_compute_{'_'.join(origins)}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done {len(origins)} origin(s) in {time.time() - t0:,.0f}s", flush=True)


if __name__ == "__main__":
    main()
