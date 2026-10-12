#!/usr/bin/env python
"""MO_139 - Fix the fixed direct model's log-scale ("retransformation") bias: Duan smearing and a Tweedie objective.

PLAIN WORDS: the direct model learns on a log scale and predicts the middle outcome for each item. Converting a
log-scale middle back to units gives a forecast that runs low whenever outcomes are lopsided (a few items take off).
This test tries the two standard fixes:
  1. Duan smearing: keep the model, and scale each forecast by how far THIS model ran low on its own check period
     (the last 13 weeks held back at the same forecast date), separately for each item-age group and weeks ahead.
     Learned at the same forecast date from data before it, so no lag (MO_138's failure) and no look-ahead.
  2. Tweedie: train the same model to predict the average outcome directly on the original units scale.

WHERE THIS CAME FROM
--------------------
Open blocker in docs/SETTLED_FINDINGS.md:293-295 ("Retransformation bias ... median of log1p ... != mean units. Fix
with Duan smearing or tweedie"). MO_137b (item-age diagnostic, descriptive): direct_avg5 runs low on items new at a
retailer (2025 without Walmart 0.805; recent, Walmart's new items systematically low, median actual/forecast 1.38).
MO_138 (lagged age x weeks-ahead multipliers) failed: the factors carried an old seasonal miss forward. MO_138 skeptic
named this test as the first remedy. Jason approved 2026-10-12.

PRIOR WORK (docs/SETTLED_FINDINGS.md incl. pending; README)
  Objectives tally (PROVISIONAL, pre-fix, SETTLED:352-360): quantile, l2, huber, poisson, tweedie, mape tried; flat
  beat them. Reopen condition: re-run under harness parity, broken out by band -- this test does that.
  MO_107: hierarchical top-down failed (not tested here). MO_67b: a single q90 constant for the recursive model's
  high forecast (not the central forecast).

DESIGN, FIXED BEFORE ANY RUN
  Base path identical to MO_132.run_direct(refit=True, calendar=True) (MO_133's direct_fixed): the smearing arm
  re-trains exactly that model and saves both the plain forecast (must equal MO_133 for every seed -> parity) and the
  smeared forecast.
  Smearing factor for weeks-ahead h and item-age group g (weeks_since_launch at the row: <13, 13-25, 26-51, 52+):
    S = mean(exp(log1p(y) - prediction)) over that horizon's check rows in group g, from the early-stopped model
    before the final refit; at least 200 check rows, else the horizon's all-group factor; capped to [0.8, 1.6].
    Smeared forecast = max(0, S x exp(prediction) - 1).
  Tweedie arm: objective tweedie (variance power 1.5) on raw units, same inputs, recency weights, early stopping on
  the same check period (eval metric tweedie), refit on all targets <= cutoff; forecast = model output (mean).
  Seeds 42, 1, 2, 3, 4 for both arms -> smear_avg5, tweedie_avg5, and base_avg5 (= MO_133 direct_avg5).

LEVELS: item x week (cw), account x month (am), portfolio x month (pm; also within history bands); BY HISTORY BAND
(<13 / 13-25 / 26-51 / 52+ wks); recent (2025-12+) first, all 18 dates, 2025 no-harm; per-origin am, am within bands
and pm within bands, each with an exact sign test (the 6 recent dates overlap); all also without Walmart.

DEFINITION OF "BEATS" (recorded before the run): a candidate beats direct_avg5 if, on the recent dates, it is better at
account x month AND at portfolio x month scored within bands, and not worse by more than 0.3 at item x week.
smear_avg5 and tweedie_avg5 are named in docs/PRODUCTION_DECISION_PREREG.md before results.

PREDICTIONS, RECORDED BEFORE ANY RUN:
  P1  Parity: the plain forecasts from the smearing arm equal MO_133 direct_fixed for all 5 seeds (max abs diff 0).
  P2  smear_avg5 raises the recent bias of items under 13 weeks from 0.865 to at least 0.95.
  P3  smear_avg5 is better than direct_avg5 at account x month and at within-band portfolio x month on recent dates.
  P4  smear_avg5 is worse than direct_avg5 at item x week on recent dates by more than 0.3 (the expected trade-off),
      so it does not "beat" it under the definition.
  P5  tweedie_avg5 is worse than direct_avg5 at item x week on recent dates (as in the provisional objectives tally),
      but its recent bias for items under 13 weeks is closer to 1.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"
import MO_80_quarterly_honest_backtest as M        # import asserts forecast + training parity
import MO_132_one_yardstick as P                     # direct model pieces (direct_frame, constants)
import MO_133_ensembles as E                         # panel loader, band-separated scoring
import MO_134_recursive_fair_settings as B           # seasonal bias by year

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

OUT = Path("outputs/mo139_retransformation.json")
OUT_ROWS = Path("outputs/mo139_rows.parquet")
RECENT = "2025-12"
SEEDS = (42, 1, 2, 3, 4)
ARMS = [f"smear_s{s}" for s in SEEDS] + [f"tweedie_s{s}" for s in SEEDS]
AGE_EDGES, AGE_NAMES = [-np.inf, 13, 26, 52, np.inf], ["<13 wks", "13-25 wks", "26-51 wks", "52+ wks"]
MIN_ROWS, S_LO, S_HI = 200, 0.8, 1.6
BANDS = AGE_NAMES


def _age(x: pd.DataFrame) -> pd.Series:
    return pd.cut(pd.to_numeric(x["weeks_since_launch"], errors="coerce").fillna(0), AGE_EDGES, right=False,
                  labels=AGE_NAMES).astype(str)


def _w(x: pd.DataFrame) -> np.ndarray:
    wk = ((x["__time"].max() - x["__time"]).dt.days / 7).clip(lower=0)
    return np.exp(-P.D26.RECENCY_LAMBDA * wk)


def fit_smear(d: pd.DataFrame, feats: list[str], cut):
    """MO_132.fit_direct(refit=True) exactly, plus Duan factors by age group from the pre-refit check period."""
    val_cut = cut - pd.Timedelta(weeks=P.D26_VAL_WEEKS)
    tr, va = d[d["t_target"] <= val_cut], d[(d["__time"] <= val_cut) & (d["t_target"] > val_cut)]
    if len(tr) < 500 or len(va) < 50:
        return None, 0, {}
    m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=P.D26.N_ESTIMATORS, **P.D26.LGBM_BASE)
    m.fit(tr[feats], np.log1p(tr["y"]), sample_weight=_w(tr),
          eval_set=[(va[feats], np.log1p(va["y"]))], eval_metric="quantile",
          callbacks=[lgb.early_stopping(P.D26.EARLY_STOP, verbose=False), lgb.log_evaluation(-1)])
    best = int(m.best_iteration_ or P.D26.N_ESTIMATORS)
    e = np.exp(np.log1p(va["y"].clip(lower=0)).values - m.predict(va[feats]))
    grp = _age(va).values
    s_all = float(np.clip(np.mean(e), S_LO, S_HI))
    fac = {g: (float(np.clip(np.mean(e[grp == g]), S_LO, S_HI)) if (grp == g).sum() >= MIN_ROWS else s_all)
           for g in AGE_NAMES}
    al = d[d["t_target"] <= cut]
    m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=best, **P.D26.LGBM_BASE)
    m.fit(al[feats], np.log1p(al["y"]), sample_weight=_w(al))
    return m, best, fac


def fit_tweedie(d: pd.DataFrame, feats: list[str], cut):
    val_cut = cut - pd.Timedelta(weeks=P.D26_VAL_WEEKS)
    tr, va = d[d["t_target"] <= val_cut], d[(d["__time"] <= val_cut) & (d["t_target"] > val_cut)]
    if len(tr) < 500 or len(va) < 50:
        return None, 0
    kw = dict(objective="tweedie", tweedie_variance_power=1.5, **P.D26.LGBM_BASE)
    m = lgb.LGBMRegressor(n_estimators=P.D26.N_ESTIMATORS, **kw)
    m.fit(tr[feats], tr["y"].clip(lower=0), sample_weight=_w(tr), eval_set=[(va[feats], va["y"].clip(lower=0))],
          eval_metric="tweedie",
          callbacks=[lgb.early_stopping(P.D26.EARLY_STOP, verbose=False), lgb.log_evaluation(-1)])
    best = int(m.best_iteration_ or P.D26.N_ESTIMATORS)
    al = d[d["t_target"] <= cut]
    m = lgb.LGBMRegressor(n_estimators=best, **kw)
    m.fit(al[feats], al["y"].clip(lower=0), sample_weight=_w(al))
    return m, best


def run_variant(tr: pd.DataFrame, feats: list[str], cut, mode: str) -> pd.DataFrame:
    """MO_132.run_direct(refit=True, calendar=True) loop, with the smear or tweedie fit."""
    last = tr.groupby(P.G, observed=True).tail(1).reset_index(drop=True)
    out = []
    for h in range(1, P.H + 1):
        fd = cut + pd.Timedelta(weeks=h)
        d = P.direct_frame(tr, h, True, False)
        X = last.copy()
        tw = float(fd.isocalendar().week)
        X["week_sin"], X["week_cos"] = np.sin(2 * np.pi * tw / 52), np.cos(2 * np.pi * tw / 52)
        X["week_sin26"], X["week_cos26"] = np.sin(2 * np.pi * tw / 26), np.cos(2 * np.pi * tw / 26)
        sids = P.sid_of(X[P.G].itertuples(index=False))
        if mode == "smear":
            m, _, fac = fit_smear(d, feats, cut)
            if m is None:
                continue
            raw = m.predict(X[feats])
            base = np.clip(np.expm1(raw), 0, None)
            s = _age(X).map(fac).astype(float).values
            sm = np.clip(s * np.exp(raw) - 1, 0, None)
            out.append(pd.DataFrame({"series": sids, "date": fd, "base": base, "smear": sm, "factor": s}))
        else:
            m, _ = fit_tweedie(d, feats, cut)
            if m is None:
                continue
            out.append(pd.DataFrame({"series": sids, "date": fd, "value": np.clip(m.predict(X[feats]), 0, None)}))
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------- compute (worker)
def compute_origin(lbl: str, arms: list[str], out_dir: str, feats_r: list[str], feats_d: list[str],
                   threads: int) -> dict:
    P.D26.LGBM_BASE["n_jobs"] = threads
    t0 = time.time()
    df = E._panel(feats_r, feats_d)
    _, c, _, _ = next(o for o in M.ORIGINS_MONTHLY if o[0] == lbl)
    cut = M._utc(c)
    tr = M.cutoff_frame(df, cut)
    out, times = Path(out_dir), {}
    for arm in arms:
        p = out / f"mo139_{arm}_{lbl}.parquet"
        if p.exists():
            continue
        t1 = time.time()
        mode, seed = arm.rsplit("_s", 1)
        P.D26.LGBM_BASE["random_state"] = int(seed)
        res = run_variant(tr, feats_d, cut, mode)
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        res.to_parquet(tmp)
        os.replace(tmp, p)
        times[arm] = round(time.time() - t1, 1)
        print(f"  {lbl} {arm}: {len(res):,} forecasts | {times[arm]}s", flush=True)
    return {"origin": lbl, "times": times, "total_s": round(time.time() - t0, 1)}


def compute(origins, arms, out_dir, feats_r, feats_d, threads, parallel):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    if parallel <= 1:
        return [compute_origin(o, arms, out_dir, feats_r, feats_d, threads) for o in origins]
    with ProcessPoolExecutor(max_workers=parallel, mp_context=get_context("spawn")) as ex:
        futs = [ex.submit(compute_origin, o, arms, out_dir, feats_r, feats_d, threads) for o in origins]
        return [f.result() for f in futs]


# ---------------------------------------------------------------- score (laptop)
def _load(prefix: str, arm: str, dirs: list[str]) -> pd.DataFrame:
    parts = [pd.read_parquet(f).assign(origin=f.stem.rsplit("_", 1)[1])
             for d in dirs for f in sorted(Path(d).glob(f"{prefix}_{arm}_????-??.parquet"))]
    if not parts:
        raise SystemExit(f"no results for {prefix} {arm}")
    cp = pd.concat(parts, ignore_index=True)
    cp["date"] = pd.to_datetime(cp["date"], utc=True)
    assert not cp.duplicated(["origin", "series", "date"]).any(), arm
    return cp


def sign_test(wins: int, n: int) -> float:
    k = min(wins, n - wins)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def score(dirs139: list[str], dirs133: list[str]) -> None:
    t0 = time.time()
    r = pd.read_parquet(E.BASE_ROWS).reset_index(drop=True)
    r = r.drop(columns=[c for c in r.columns if c.startswith("model_seed")] + ["model"], errors="ignore")
    r["date"] = pd.to_datetime(r["date"], utc=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    k = ["origin", "series", "date"]

    def merge(cp, col_src, col):
        nonlocal r
        n0 = len(r)
        r = r.merge(cp[k + [col_src]].rename(columns={col_src: col}), on=k, how="left")
        assert len(r) == n0
        miss = np.isnan(r[col].values) & ~zero
        r[col] = np.where(zero, 0.0, np.where(miss, r["flat"], r[col]))
        return int(miss.sum())

    parity = {}
    for s in SEEDS:
        sm = _load("mo139", f"smear_s{s}", dirs139)
        print(f"  smear_s{s}: fell back base {merge(sm, 'base', f'base_s{s}')}, smear {merge(sm, 'smear', f'smear_s{s}')}")
        tw = _load("mo139", f"tweedie_s{s}", dirs139)
        print(f"  tweedie_s{s}: fell back {merge(tw, 'value', f'tweedie_s{s}')}")
        d133 = _load("mo133", f"direct_fixed_s{s}", dirs133)
        merge(d133, f"direct_fixed_s{s}", f"direct_fixed_s{s}")
        parity[s] = float((r[f"base_s{s}"] - r[f"direct_fixed_s{s}"]).abs().max())
    print(f"\nPARITY plain forecasts vs MO_133 direct_fixed, max abs diff by seed: {parity}")
    served = pd.read_parquet("outputs/mo135_rows.parquet")[k + ["direct_served"]]
    served["date"] = pd.to_datetime(served["date"], utc=True)
    r = r.merge(served, on=k, how="left")
    assert r["direct_served"].notna().all()
    r["direct_avg5"] = r[[f"direct_fixed_s{s}" for s in SEEDS]].mean(axis=1)
    r["smear_avg5"] = r[[f"smear_s{s}" for s in SEEDS]].mean(axis=1)
    r["tweedie_avg5"] = r[[f"tweedie_s{s}" for s in SEEDS]].mean(axis=1)
    r["wmt"] = r["account"].astype(str).str.upper().eq("WALMART")
    arms = ["flat", "conn_L4W", "direct_served", "direct_avg5", "smear_avg5", "tweedie_avg5"]
    r.to_parquet(OUT_ROWS)
    res = {"parity_by_seed": parity, "arms": arms}
    ex = r[~r["is_new"]]
    CW, AM, PM = "cell x week", "account x month", "portfolio x month"
    for scope, sub0 in (("with Walmart", ex), ("without Walmart", ex[~ex["wmt"]])):
        res[scope] = {}
        for name, sub in (("recent", sub0[sub0.origin >= RECENT]), ("all", sub0), ("2025", sub0[sub0.origin < RECENT])):
            Sx = M.score_levels(sub, arms)
            res[scope][name] = Sx
            print(f"\n=== {scope.upper()}, {name.upper()} origins, existing series: cw / am / pm | bias ===")
            for x in arms:
                print(f"  {x:<14s}{Sx[CW][x]:7.2f}{Sx[AM][x]:7.2f}{Sx[PM][x]:7.2f}   bias {Sx['portfolio_bias'][x]:.3f}")
            if scope == "with Walmart":
                for lvl, _ in M.LEVELS_V2:
                    print(f"  BY HISTORY BAND, {lvl} (<13 / 13-25 / 26-51 / 52+ wks)")
                    for b, v in Sx[lvl]["by_band"].items():
                        print(f"    {b:<10s} n={v['n']:>7,}  " + "  ".join(f"{x}={v[x]:.1f}" for x in arms))
    rec = ex[ex.origin >= RECENT]
    bias_age = {b: {x: float(rec.loc[rec.band == b, x].sum() / rec.loc[rec.band == b, "actual"].sum()) for x in arms}
                for b in BANDS}
    res["recent_bias_by_age"] = bias_age
    print("\nRECENT bias (forecast / actual) by item age:")
    print(pd.DataFrame(bias_age).T.round(3).to_string())

    def pct(d, c):
        return 100 * np.abs(d["actual"] - d[c]).sum() / d["actual"].sum()

    print("\nPER-ORIGIN, recent dates (candidate - direct_avg5; negative = better); exact sign test (dates overlap)")
    res["per_origin"] = {}
    for scope, sub0 in (("with Walmart", rec), ("without Walmart", rec[~rec["wmt"]])):
        pm = M._prep_scoring(sub0, arms)
        g = pm[pm["full_month"]].groupby(["origin", "account", "month"])[["actual"] + arms].sum().reset_index()
        gb = pm[pm["full_month"]].groupby(["origin", "account", "month", "band"])[["actual"] + arms].sum().reset_index()
        for x in ("smear_avg5", "tweedie_avg5"):
            am = {o: round(pct(d, x) - pct(d, "direct_avg5"), 2) for o, d in g.groupby("origin")}
            amb = {o: round(pct(d, x) - pct(d, "direct_avg5"), 2) for o, d in gb.groupby("origin")}
            pbo = {o: round(E.band_separated_diff(d, x, "direct_avg5")["diff"], 2) for o, d in sub0.groupby("origin")}
            pb = E.band_separated_diff(sub0, x, "direct_avg5")["diff"]
            w = [sum(v < 0 for v in z.values()) for z in (am, amb, pbo)]
            res["per_origin"][f"{scope}: {x}"] = {"am": am, "am_within_bands": amb, "pm_within_bands_per_date": pbo,
                                                  "pm_within_bands": pb, "wins": w}
            print(f"  [{scope}] {x:<13s} am wins {w[0]}/6 (p={sign_test(w[0], 6):.2f}) {am}")
            print(f"  [{scope}] {x:<13s} am within bands wins {w[1]}/6 {amb}")
            print(f"  [{scope}] {x:<13s} pm within bands wins {w[2]}/6 (pooled {pb:+.2f}) {pbo}")
    res["season_bias"] = B.season_bias(ex, arms)
    print("\nSEASONAL BIAS PER YEAR")
    for kk, v in res["season_bias"].items():
        print(f"  {kk:<13s} " + "  ".join(f"{a}={v[a]:.3f}" for a in arms))
    R = res["with Walmart"]["recent"]
    pbr = res["per_origin"]["with Walmart: smear_avg5"]["pm_within_bands"]
    checks = [
        ("P1", max(parity.values()) == 0.0, f"max abs diff by seed {parity}"),
        ("P2", bias_age["<13 wks"]["smear_avg5"] >= 0.95,
         f"recent <13-wk bias smear_avg5 {bias_age['<13 wks']['smear_avg5']:.3f} (direct_avg5 {bias_age['<13 wks']['direct_avg5']:.3f})"),
        ("P3", R[AM]["smear_avg5"] < R[AM]["direct_avg5"] and pbr < 0,
         f"recent am {R[AM]['smear_avg5']:.2f} vs {R[AM]['direct_avg5']:.2f}; pm within bands {pbr:+.2f}"),
        ("P4", R[CW]["smear_avg5"] > R[CW]["direct_avg5"] + 0.3,
         f"recent cw {R[CW]['smear_avg5']:.2f} vs {R[CW]['direct_avg5']:.2f}"),
        ("P5", R[CW]["tweedie_avg5"] > R[CW]["direct_avg5"]
         and abs(bias_age["<13 wks"]["tweedie_avg5"] - 1) < abs(bias_age["<13 wks"]["direct_avg5"] - 1),
         f"recent cw tweedie {R[CW]['tweedie_avg5']:.2f} vs {R[CW]['direct_avg5']:.2f}; <13 bias "
         f"{bias_age['<13 wks']['tweedie_avg5']:.3f} vs {bias_age['<13 wks']['direct_avg5']:.3f}"),
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
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo139_cache"))
    ap.add_argument("--feats-dir", default="outputs")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--results139", default="")
    ap.add_argument("--results133", default="")
    a = ap.parse_args()
    sp = lambda s: [x for x in s.split(",") if x]
    fd = Path(a.feats_dir)
    feats_r = json.loads((fd / "feats_recursive.json").read_text())
    feats_d = list(json.loads((fd / "direct_multihorizon_metrics_v11d.json").read_text())["features_used"])
    if a.cmd == "score":
        score(sp(a.results139), sp(a.results133))
        return
    origins = sp(a.origins) or [o[0] for o in M.ORIGINS_MONTHLY]
    t0 = time.time()
    summary = compute(origins, a.arms.split(","), a.out, feats_r, feats_d, a.threads, a.parallel)
    Path(a.out, f"mo139_compute_{'_'.join(origins)}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done {len(origins)} origin(s) in {time.time() - t0:,.0f}s", flush=True)


if __name__ == "__main__":
    main()
