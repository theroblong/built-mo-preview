#!/usr/bin/env python
"""MO_134 - Fair settings for the recursive model: remove the caps, fix the year-ago, sweep the sliders.

WHERE THIS CAME FROM
--------------------
Roadmap step 2 ("fair training"; Jason, 2026-10-07: "throw off the shackles of arbitrary
ceilings and stopping short on training"). Status on 2026-10-09: the test bench is fixed, but
the recursive model (Jason's hunch for production) still (a) hits its 6,000-tree cap, (b) clips
the year-over-year ratio to 0.5-2.0 (MO_27:571), (c) looks up "a year ago" 52 ROWS back, which
lands on the wrong week for series with gaps, and (d) has never had its seasonal blend weight
or recency weight tuned on the honest bench. The sweeps double as evidence for the settings
guide's "what happens if you move this slider" (Jason: Aevah as data science in a box).
Every arm runs on the GPU worker (one machine per comparison), scored on the laptop.

PRIOR WORK (docs/SETTLED_FINDINGS.md incl. pending proposals; README 230-234)
  MO_29   q50 early stopping converges ~4,593 trees (old bench); production v11 q50 hits 6000.
  MO_27f  seasonal blend 0.10 beat 0.40 (old bench, pooled).
  MO_97/98 a 1.5x extrapolation cap was weak; linear trees worse (old bench).
  MO_133  recursive (worker) 35.46 / 22.89 / 13.75; combinations beat recursive (-3.42* cw);
          nothing beats last value on 13+ week series; P4 failed.
  docs/PRODUCTION_DECISION_PREREG.md -- written before this run; rec_fair is named here as a
          candidate before its results exist; sweep winners are post hoc and need forward
          confirmation.

ARMS (worker; all recursive MO_80.run_production unless noted; lapsed/new = 0)
  shared trained model (cap 6000, recency 0.02):
    rec           production settings (re-run in the same job for like-for-like comparisons)
    rec_noclip    YOY_CLIP = None (no clip on the year-over-year ratio)
    rec_cal       YEAR_AGO = "calendar" (same week last year by date; gaps -> missing)
    rec_fair      no clip + calendar year-ago + safety rail at 3x the series max (roadmap step 2)
    rec_w00/05/20/30   seasonal blend weight 0, 0.05, 0.20, 0.30 (production 0.10)
  retrained:
    rec_cap20k    tree cap 20,000 (production 6,000)
    rec_lam00/01/04    recency weight 0 (all weeks equal), 0.01, 0.04 (production 0.02)
  direct_served  MO_26D replica as served (for the production-decision rule, same machine)

LEVELS: cell x week, account x month, portfolio x month (complete months) + band-separated
portfolio x month + 13+-week-only results; bias; per-year Jan-Mar / Oct-Dec bias; shape with the
majority-direction baseline. The production-decision rule (docs/PRODUCTION_DECISION_PREREG.md)
is evaluated for rec and rec_fair against direct_served.

PREDICTIONS, RECORDED BEFORE ANY RUN:
  P1  Removing the clip barely matters: |rec_noclip - rec| < 0.5 at cell x week (the blend that
      uses the ratio has weight 0.10).
  P2  Calendar year-ago: |rec_cal - rec| < 0.5 at cell x week, and rec_cal <= rec in the 52+
      band at cell x week.
  P3  Tree cap 20,000: the best iteration exceeds 6,000 at most origins, and the cell x week
      gain is under 0.5.
  P4  Recency: 0.04 beats 0.02 at cell x week (a growth regime favors recent weeks), and
      recency 0 is the worst of the four.
  P5  Blend weight: the best of {0, 0.05, 0.10, 0.20, 0.30} at cell x week is 0.05, 0.10 or 0.20;
      0.30 is worse than 0.10.
  P6  No recursive variant beats last value at cell x week on 13+ week series.
  P7  rec passes the production-decision rule against direct_served on criteria 1 (item level)
      and 2 (no planning-level harm); rec_fair does too.
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
import MO_132_one_yardstick as P                     # direct replica, shape scoring
import MO_133_ensembles as E                         # band-separated scoring, panel loader

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

DEFAULTS = {"YOY_CLIP": (0.5, 2.0), "YEAR_AGO": "rows", "SAFETY_CAP_X_MAX": None,
            "SEASONAL_BLEND_WEIGHT": 0.10, "TREES_CAP": M.TREES_CAP, "RECENCY_LAMBDA": 0.02}
ARMS = {
    "rec": {},
    "rec_noclip": {"YOY_CLIP": None},
    "rec_cal": {"YEAR_AGO": "calendar"},
    "rec_fair": {"YOY_CLIP": None, "YEAR_AGO": "calendar", "SAFETY_CAP_X_MAX": 3.0},
    "rec_w00": {"SEASONAL_BLEND_WEIGHT": 0.0},
    "rec_w05": {"SEASONAL_BLEND_WEIGHT": 0.05},
    "rec_w20": {"SEASONAL_BLEND_WEIGHT": 0.20},
    "rec_w30": {"SEASONAL_BLEND_WEIGHT": 0.30},
    "rec_cap20k": {"TREES_CAP": 20000},
    "rec_lam00": {"RECENCY_LAMBDA": 0.0},
    "rec_lam01": {"RECENCY_LAMBDA": 0.01},
    "rec_lam04": {"RECENCY_LAMBDA": 0.04},
}
OUT = Path("outputs/mo134_fair_settings.json")
OUT_ROWS = Path("outputs/mo134_rows.parquet")
WINTER = ("2025-11", "2025-12", "2026-01")


def _apply(cfg: dict) -> None:
    for k, v in (DEFAULTS | cfg).items():
        setattr(M, k, v)


# ---------------------------------------------------------------- compute (worker)
def compute_origin(lbl: str, arms: list[str], out_dir: str, feats_r: list[str], feats_d: list[str],
                   threads: int) -> dict:
    P.D26.LGBM_BASE["n_jobs"] = threads
    M.PROD_LGBM["n_jobs"] = threads
    if os.environ.get("MO_PANEL_PARQUET"):
        import MO_59_stl_changepoints as S
        S.PARQUET = Path(os.environ["MO_PANEL_PARQUET"])
    t0 = time.time()
    df = E._panel(feats_r, feats_d)
    _, c, s, e = next(o for o in M.ORIGINS_MONTHLY if o[0] == lbl)
    cut, qs, qe = M._utc(c), M._utc(s), M._utc(e) + pd.Timedelta(days=6)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    fw = M.future_weeks(weeks, cut, M.HORIZON)
    ev = M.build_eval_rows(df, cut, s, e)
    ek = set(ev.loc[~ev["is_new"], "key"])
    seas = M.seasonal_index_at(cut)
    out, info = Path(out_dir), {}
    for arm in arms:
        p = out / f"mo134_{arm}_{lbl}.parquet"
        if p.exists():
            continue
        t1 = time.time()
        if arm == "direct_served":
            _apply({})
            res = P.run_direct(M.cutoff_frame(df, cut), feats_d, cut, refit=False,
                               calendar=False).rename(columns={"value": arm})
            info[arm] = {"s": round(time.time() - t1, 1)}
        else:
            _apply(ARMS[arm])
            M.RAIL_HITS.clear()
            n_fit = len(M.FIT_LOG)
            pr = M.run_production(df, feats_r, cut, qs, qe, ek, None, fw, seas)
            fit = M.FIT_LOG[-1] if len(M.FIT_LOG) > n_fit else {}
            res = pd.DataFrame({"series": P.sid_of([k for k, _ in pr]), "date": [d for _, d in pr],
                                arm: list(pr.values())})
            info[arm] = {"s": round(time.time() - t1, 1), "best_iteration": fit.get("best_iteration"),
                         "hit_cap": fit.get("hit_cap"), "cached": fit.get("cached"),
                         "rail_hits": len(M.RAIL_HITS)}
        _apply({})
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        res.to_parquet(tmp)
        os.replace(tmp, p)
        print(f"  {lbl} {arm}: {len(res):,} forecasts | {info[arm]}", flush=True)
    return {"origin": lbl, "arms": info, "total_s": round(time.time() - t0, 1)}


def compute(origins, arms, out_dir, feats_r, feats_d, threads, parallel):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    if parallel <= 1:
        return [compute_origin(o, arms, out_dir, feats_r, feats_d, threads) for o in origins]
    with ProcessPoolExecutor(max_workers=parallel, mp_context=get_context("spawn")) as ex:
        futs = [ex.submit(compute_origin, o, arms, out_dir, feats_r, feats_d, threads) for o in origins]
        return [f.result() for f in futs]


# ---------------------------------------------------------------- score (laptop)
def season_bias(ex: pd.DataFrame, arms: list[str]) -> dict:
    d = pd.to_datetime(ex["date"], utc=True)
    q = ex.assign(_y=d.dt.year, _m=d.dt.month)
    return {f"{name} {y}": {a: float(g[a].sum() / g["actual"].sum()) for a in arms}
            for name, mm in (("Jan-Mar", (1, 2, 3)), ("Oct-Dec", (10, 11, 12)))
            for y, g in q[q["_m"].isin(mm)].groupby("_y")}


def decision_check(ex: pd.DataFrame, y: str, x: str) -> dict:
    """docs/PRODUCTION_DECISION_PREREG.md criteria 1-5 for candidate y vs status quo x."""
    cw = M.bootstrap_diff(ex, y, x, level="cell x week", n=2000)
    am = M.bootstrap_diff(ex, y, x, level="account x month", n=2000)
    pmb = E.band_separated_diff(ex, y, x)
    e13 = ex[ex["band"].isin(E.ESTABLISHED)]
    cw13 = M.bootstrap_diff(e13, y, x, level="cell x week", n=2000)
    sb = season_bias(ex, [y, x])
    c4 = all(abs(v[y] - 1) <= 0.10 or abs(v[y] - 1) <= abs(v[x] - 1) for v in sb.values())
    nw = M.bootstrap_diff(ex[~ex["origin"].isin(WINTER)], y, x, level="cell x week", n=2000)
    top = ex.groupby("account")["actual"].sum().idxmax()
    na = M.bootstrap_diff(ex[ex["account"] != top], y, x, level="cell x week", n=2000)
    crit = {"1 item level win (CI < 0)": cw["ci95"][1] < 0,
            "2 no harm am / pm by band": am["ci95"][0] <= 0 and pmb["ci95"][0] <= 0,
            "3 13+ cw within +0.5": cw13["diff"] <= 0.5,
            "4 seasonal bias per year": c4,
            "5 robust w/o winter and w/o top account": nw["ci95"][1] < 0 and na["ci95"][1] < 0}
    return {"criteria": crit, "passes": all(crit.values()), "top_account": str(top),
            "numbers": {"cw": cw, "am": am, "pm_by_band": pmb, "cw_13plus": cw13,
                        "cw_no_winter": nw, "cw_no_top_account": na, "season_bias": sb}}


def score(result_dirs: list[str]) -> None:
    t0 = time.time()
    r = pd.read_parquet(E.BASE_ROWS).rename(columns={"model": "recursive_laptop"})
    r = r.drop(columns=[c for c in r.columns if c.startswith("model_seed")]).reset_index(drop=True)
    r["date"] = pd.to_datetime(r["date"], utc=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    arms = list(ARMS) + ["direct_served"]
    for arm in arms:
        parts = [pd.read_parquet(f).assign(origin=f.stem.rsplit("_", 1)[1])
                 for d in result_dirs for f in sorted(Path(d).glob(f"mo134_{arm}_????-??.parquet"))]   # exact arm: "rec" must not match "rec_noclip"
        if not parts:
            raise SystemExit(f"no results for {arm}")
        cp = pd.concat(parts, ignore_index=True)
        cp["date"] = pd.to_datetime(cp["date"], utc=True)
        assert not cp.duplicated(["origin", "series", "date"]).any(), arm
        n0 = len(r)
        r = r.merge(cp[["origin", "series", "date", arm]], on=["origin", "series", "date"], how="left")
        assert len(r) == n0
        miss = np.isnan(r[arm].values) & ~zero
        print(f"  {arm}: origins {cp['origin'].nunique()}, fell back to flat {int(miss.sum()):,}")
        r[arm] = np.where(zero, 0.0, np.where(miss, r["flat"], r[arm]))
    cols = ["flat", "conn_L4W"] + arms
    r.to_parquet(OUT_ROWS)
    ex = r[~r["is_new"]]
    res = {"existing": M.score_levels(ex, cols), "arms": cols}
    Ex = res["existing"]
    print("\n=== EXISTING SERIES: error (lower is better) | 13+ wks cell x week | bias ===")
    e13 = M.score_levels(ex[ex["band"].isin(E.ESTABLISHED)], cols)
    res["existing_13plus"] = e13
    for x in sorted(cols, key=lambda k: Ex["cell x week"][k]):
        print(f"  {x:<14s}{Ex['cell x week'][x]:>8.2f}{Ex['account x month'][x]:>8.2f}"
              f"{Ex['portfolio x month'][x]:>8.2f}   13+ {e13['cell x week'][x]:6.2f}   bias {Ex['portfolio_bias'][x]:.3f}")
    key_arms = ("flat", "conn_L4W", "rec", "rec_fair", "rec_cal", "rec_cap20k", "rec_lam04", "direct_served")
    for lvl, _ in M.LEVELS_V2:
        print(f"  BY HISTORY BAND, {lvl} (<13 / 13-25 / 26-51 / 52+ wks)")
        for b, v in Ex[lvl]["by_band"].items():
            print(f"    {b:<10s} n={v['n']:>7,}  " + "  ".join(f"{x}={v[x]:.1f}" for x in key_arms))
    res["ci"] = {}
    print("\nDIFFERENCES vs rec (production recursive, same job) and vs flat; pm by band; 13+ cw")
    for x in cols:
        for ref in ("rec", "flat"):
            if x == ref:
                continue
            row = [M.bootstrap_diff(ex, x, ref, level=l, n=2000) for l, _ in M.LEVELS_V2]
            pb = E.band_separated_diff(ex, x, ref)
            c13 = M.bootstrap_diff(ex[ex["band"].isin(E.ESTABLISHED)], x, ref, level="cell x week", n=2000)
            res["ci"][f"{x}-{ref}"] = {"levels": row, "pm_by_band": pb, "cw_13plus": c13}
            f = lambda b: f"{b['diff']:+6.2f} [{b['ci95'][0]:+.1f},{b['ci95'][1]:+.1f}]{'*' if b['significant'] else ' '}"
            print(f"  {x:>14s} - {ref:<5s} " + "  ".join(f(b) for b in row) + f"   pm/band {f(pb)}   13+ cw {f(c13)}")
    res["season_bias"] = season_bias(ex, cols)
    print("\nSEASONAL BIAS PER YEAR (1.00 = right level)")
    for k, v in res["season_bias"].items():
        print(f"  {k:<13s} " + "  ".join(f"{a}={v[a]:.2f}" for a in ("flat", "rec", "rec_fair", "rec_noclip",
                                                                    "rec_cal", "direct_served")))
    exs = M._prep_scoring(ex, cols)
    res["shape"] = {"portfolio x week": P.shape_scores(exs, cols, ["origin"], "date"),
                    "account x month": P.shape_scores(exs[exs["full_month"]], cols, ["origin", "account"], "month")}
    for lvl, Sl in res["shape"].items():
        print(f"\nSHAPE {lvl}: baseline {Sl['majority_baseline']:.1f}%  " + "  ".join(
            f"{a} {Sl[a]['precision']:.1f}/r{Sl[a]['change_r']:+.2f}{'*' if Sl[a]['beats_chance'] else ''}"
            for a in ("rec", "rec_fair", "rec_cal", "direct_served")))
    res["decision"] = {f"{y} vs direct_served": decision_check(ex, y, "direct_served") for y in ("rec", "rec_fair")}
    print("\nPRODUCTION-DECISION RULE (docs/PRODUCTION_DECISION_PREREG.md), status quo = direct_served")
    for k, v in res["decision"].items():
        print(f"  {k}: {'PASSES' if v['passes'] else 'does not pass'} -- " +
              "; ".join(f"{c} {'ok' if ok else 'NO'}" for c, ok in v["criteria"].items()))
    CW = "cell x week"
    d = lambda a, b: Ex[CW][a] - Ex[CW][b]
    sweep_w = {a: Ex[CW][a] for a in ("rec_w00", "rec_w05", "rec", "rec_w20", "rec_w30")}
    sweep_l = {a: Ex[CW][a] for a in ("rec_lam00", "rec_lam01", "rec", "rec_lam04")}
    checks = [
        ("P1", abs(d("rec_noclip", "rec")) < 0.5, f"rec_noclip - rec {d('rec_noclip', 'rec'):+.2f}"),
        ("P2", abs(d("rec_cal", "rec")) < 0.5 and Ex[CW]["by_band"]["52+ wks"]["rec_cal"] <= Ex[CW]["by_band"]["52+ wks"]["rec"],
         f"rec_cal - rec {d('rec_cal', 'rec'):+.2f}; 52+ {Ex[CW]['by_band']['52+ wks']['rec_cal']:.2f} vs {Ex[CW]['by_band']['52+ wks']['rec']:.2f}"),
        ("P3", None, f"rec_cap20k - rec {d('rec_cap20k', 'rec'):+.2f} (best-iteration check from the worker logs)"),
        ("P4", sweep_l["rec_lam04"] < sweep_l["rec"] and max(sweep_l, key=sweep_l.get) == "rec_lam00", f"{sweep_l}"),
        ("P5", min(sweep_w, key=sweep_w.get) in ("rec_w05", "rec", "rec_w20") and sweep_w["rec_w30"] > sweep_w["rec"], f"{sweep_w}"),
        ("P6", all(e13[CW][a] >= e13[CW]["flat"] for a in ARMS), "13+ cw: flat " + f"{e13[CW]['flat']:.2f}, best recursive " +
         f"{min(e13[CW][a] for a in ARMS):.2f}"),
        ("P7", all(v["criteria"]["1 item level win (CI < 0)"] and v["criteria"]["2 no harm am / pm by band"]
                   for v in res["decision"].values()), "criteria 1-2 for rec and rec_fair"),
    ]
    print("\nPREDICTIONS")
    res["predictions"] = {}
    for pid, ok, msg in checks:
        tag = "CHECK LOGS" if ok is None else ("HOLDS" if ok else "FAILS")
        res["predictions"][pid] = {"result": tag, "detail": msg}
        print(f"  {pid} {tag:<10s} {msg}")
    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT} and {OUT_ROWS} ({time.time() - t0:,.0f}s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["compute", "score"])
    ap.add_argument("--origins", default="")
    ap.add_argument("--arms", default=",".join(list(ARMS) + ["direct_served"]))
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo134_cache"))
    ap.add_argument("--feats-dir", default="outputs")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--results", default="")
    a = ap.parse_args()
    if a.cmd == "score":
        score([x for x in a.results.split(",") if x] or ["outputs/mo134_cache"])
        return
    origins = [o for o in a.origins.split(",") if o] or [o[0] for o in M.ORIGINS_MONTHLY]
    fd = Path(a.feats_dir)
    feats_r = json.loads((fd / "feats_recursive.json").read_text())
    feats_d = list(json.loads((fd / "direct_multihorizon_metrics_v11d.json").read_text())["features_used"])
    t0 = time.time()
    summary = compute(origins, a.arms.split(","), a.out, feats_r, feats_d, a.threads, a.parallel)
    Path(a.out, f"mo134_compute_{'_'.join(origins)}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done {len(origins)} origin(s) in {time.time() - t0:,.0f}s", flush=True)


if __name__ == "__main__":
    main()
