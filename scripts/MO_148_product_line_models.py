#!/usr/bin/env python
"""MO_148 - Do separate models per product line (PUFF, SOUR PUFF, BAR), or a model trained without old BAR history,
forecast better than one pooled model?

PLAIN WORDS: today one fixed direct model (5 seeds averaged) is trained on all BUILT items together: BAR (a line
being phased out: 34% of base units in 2023, 0.3% now), PUFF (the core line) and SOUR PUFF (launched 2025). This
tests two alternatives on the corrected benchmark (18 forecast dates, honest scoring, the full switching rule):
  per-line models: one model for each product line, trained only on that line's history;
  no-BAR model: one model for PUFF and SOUR PUFF trained without any BAR history (BAR items keep the current model).

WHERE THIS CAME FROM: plan approved by Jason 2026-10-14 (steps 1-3 before tuning; forecast to be presented before
2026-12-06). MO_121 (old benchmark) found per-brand models beat pooled in all 7 quarters (~1.1 points) and excluding
BAR improved PUFF/SOUR PUFF (~1.3 points); never re-run on the corrected benchmark.

PRIOR WORK (docs/SETTLED_FINDINGS.md, README, memory; scout 2026-10-14)
  - MO_121 (PROVISIONAL, pre-fix bench; memory project_brand_stratification): per-brand +1.14 pp, exclude-BAR +1.34 pp.
    Reopen-if: re-test on the corrected harness -- this is that re-test.
  - MO_140 (PROVISIONAL): product line as a static input (attr_majority_type) did not help; source_brand is already
    an input -- a stratifier can matter even when the input ranks low (MO_121's framing).
  - MO_146 / MO_147 (PROVISIONAL): blends do not pass Amendment 2; production unchanged at direct_avg5.
  - BAR -> PUFF stitching (memory): matchable but not concatenable; not attempted here.
  - Amendment 1 + 2 rule: docs/PRODUCTION_DECISION_PREREG.md (candidates line_avg5 and nobar_avg5 named before results).

ARMS (MO_132.run_direct(refit=True, calendar=True), same inputs as production; GPU worker; seeds 42, 1, 2, 3, 4):
  base_s42          production model, all lines pooled; must equal MO_133 direct_fixed_s42 exactly (parity)
  line_s{seed}      one model per line (BAR = 'BUILT BAR' + legacy 'BUILT'; PUFF; SOUR PUFF), each on its own rows
  nobar_s{seed}     one model on PUFF + SOUR PUFF rows only; BAR items not forecast by this arm
Any item an arm does not forecast (a line with too little data at an early date; BAR items in the no-BAR arm) uses
the production model's forecast with the same seed, so every arm is scored on identical rows.
LEVELS: cell x week, account x month, portfolio x month (+ within each history band), bias; BY HISTORY BAND
(<13 / 13-25 / 26-51 / 52+ wks); BY PRODUCT LINE; with and without Walmart; recent (2025-12+), all 18, 2025.
RULE: Amendment 1 criteria 1-4 + Amendment 2 criterion 7, each candidate vs direct_avg5.

PREDICTIONS, RECORDED BEFORE ANY RUN (two-sided where a size is predicted):
  P1 Parity: base_s42 equals MO_133 direct_fixed_s42 exactly on every origin.
  P2 line_avg5 recent account x month is within +/-0.5 of direct_avg5 (with BAR now 0.3% of volume, stratifying
     mostly means splitting PUFF from SOUR PUFF, which shares most patterns).
  P3 nobar_avg5 improves recent cell x week on PUFF items by at least 0.3 point (old BAR history adds noise).
  P4 On SOUR PUFF items, line_avg5 is worse than direct_avg5 at recent cell x week (a SOUR-only model has little
     history to learn from).
  P5 Neither candidate passes the full backtest rule (criteria 1-4 and 7).
Usage:
  worker:  python mo148_job.py --origins 2025-01,2025-02 [--parallel 3 --threads 8]
  laptop:  python MO_148_product_line_models.py score --results <dir1,dir2,...>
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
import MO_132_one_yardstick as P                     # direct arms
import MO_133_ensembles as E                         # band-separated scoring, panel loader
import MO_134_recursive_fair_settings as B           # seasonal bias by year
import MO_136_signals as S                           # result loader, sign test

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

PREFIX = "mo148"
ROWS_IN = Path("outputs/mo140_rows.parquet")         # honest-harness rows with direct_fixed_s* and direct_avg5
RECENT = "2025-12"
SEEDS = (42, 1, 2, 3, 4)
ESTABLISHED = ("13-25 wks", "26-51 wks", "52+ wks")
CW, AM, PM = "cell x week", "account x month", "portfolio x month"
BAR = ("BUILT BAR", "BUILT")
LINES = {"BAR": BAR, "PUFF": ("BUILT PUFF",), "SOUR PUFF": ("BUILT SOUR PUFF",)}


# ---------------------------------------------------------------- variants (one function per arm group)
def v_base(tr, feats, cut):
    return P.run_direct(tr, feats, cut, refit=True, calendar=True)


def v_line(tr, feats, cut):
    parts = []
    for name, brands in LINES.items():
        sub = tr[tr["source_brand"].astype(str).isin(brands)]
        if len(sub):
            print(f"      line {name}: {sub[M.GROUP_COLS].drop_duplicates().shape[0]} series", flush=True)
            parts.append(P.run_direct(sub, feats, cut, refit=True, calendar=True))
    return pd.concat(parts, ignore_index=True)


def v_nobar(tr, feats, cut):
    return P.run_direct(tr[~tr["source_brand"].astype(str).isin(BAR)], feats, cut, refit=True, calendar=True)


VARIANTS = {"base": v_base, "line": v_line, "nobar": v_nobar}
ARMS = ["base_s42"] + [f"{g}_s{s}" for g in ("line", "nobar") for s in SEEDS]
CANDIDATES = ("line", "nobar")


# ---------------------------------------------------------------- compute (worker)
def compute_origin(lbl, arms, out_dir, feats_r, feats_d, threads, prefix=PREFIX, variants=None, prep=None,
                   extra_feats=()):
    variants = variants or VARIANTS
    P.D26.LGBM_BASE["n_jobs"] = threads
    t0 = time.time()
    df = E._panel(feats_r, feats_d)
    if prep is not None:
        df = prep(df)
    _, c, _, _ = next(o for o in M.ORIGINS_MONTHLY if o[0] == lbl)
    cut = M._utc(c)
    tr = M.cutoff_frame(df, cut)
    out, times = Path(out_dir), {}
    for arm in arms:
        p = out / f"{prefix}_{arm}_{lbl}.parquet"
        if p.exists():
            continue
        t1 = time.time()
        group, seed = arm.rsplit("_s", 1)
        feats = list(feats_d) + ([] if group == "base" else list(extra_feats))
        P.D26.LGBM_BASE["random_state"] = int(seed)
        res = variants[group](tr, feats, cut).rename(columns={"value": arm})
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        res.to_parquet(tmp)
        os.replace(tmp, p)
        times[arm] = round(time.time() - t1, 1)
        print(f"  {lbl} {arm}: {len(res):,} forecasts | {times[arm]}s", flush=True)
    return {"origin": lbl, "times": times, "total_s": round(time.time() - t0, 1)}


def compute(origins, arms, out_dir, feats_r, feats_d, threads, parallel, **kw):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    if parallel <= 1:
        return [compute_origin(o, arms, out_dir, feats_r, feats_d, threads, **kw) for o in origins]
    with ProcessPoolExecutor(max_workers=parallel, mp_context=get_context("spawn")) as ex:
        futs = [ex.submit(compute_origin, o, arms, out_dir, feats_r, feats_d, threads, **kw) for o in origins]
        return [f.result() for f in futs]


# ---------------------------------------------------------------- score (laptop)
def series_lines(feats_r, feats_d) -> pd.Series:
    df = E._panel(feats_r, feats_d)
    k = df[M.GROUP_COLS].astype(str).agg(" | ".join, axis=1)
    b = df["source_brand"].astype(str)
    line = np.select([b.isin(BAR), b.eq("BUILT SOUR PUFF")], ["BAR", "SOUR PUFF"], "PUFF")
    return pd.Series(line, index=k).groupby(level=0).first()


def score_candidates(dirs, prefix, candidates, out_json, out_rows, feats_r, feats_d) -> dict:
    t0 = time.time()
    r = pd.read_parquet(ROWS_IN).reset_index(drop=True)
    r["date"] = pd.to_datetime(r["date"], utc=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    cp = S._load("base_s42", dirs, prefix)
    r = r.merge(cp[["origin", "series", "date", "base_s42"]], on=["origin", "series", "date"], how="left")
    miss = r["base_s42"].isna().values & ~zero
    r["base_s42"] = np.where(zero, 0.0, np.where(miss, r["flat"], r["base_s42"]))
    d = (r["base_s42"] - r["direct_fixed_s42"]).abs()
    parity = {o: float(v) for o, v in d.groupby(r["origin"]).max().items()}
    print(f"PARITY base_s42 vs MO_133 direct_fixed_s42: max abs diff {d.max():.6f}; base fell back {int(miss.sum()):,}")
    fallback = {}
    for g in candidates:
        for s in SEEDS:
            arm = f"{g}_s{s}"
            cp = S._load(arm, dirs, prefix)
            n0 = len(r)
            r = r.merge(cp[["origin", "series", "date", arm]], on=["origin", "series", "date"], how="left")
            assert len(r) == n0
            miss = r[arm].isna().values & ~zero
            fallback[arm] = int(miss.sum())
            r[arm] = np.where(zero, 0.0, np.where(miss, r[f"direct_fixed_s{s}"], r[arm]))
        r[f"{g}_avg5"] = r[[f"{g}_s{s}" for s in SEEDS]].mean(axis=1)
    print("rows using the production model's same-seed forecast (arm did not forecast them):", fallback)
    r["line"] = r["series"].map(series_lines(feats_r, feats_d)).fillna("PUFF")
    arms = ["direct_avg5"] + [f"{g}_avg5" for g in candidates]
    keep = ["origin", "series", "date", "actual", "account", "band", "is_new", "wmt", "line", "flat"] + arms
    r[keep].to_parquet(out_rows)
    ex = r[~r["is_new"]]
    res = {"arms": arms, "parity_max_abs_diff_by_origin": parity, "fallback_rows": fallback}
    for scope, sub0 in (("with Walmart", ex), ("without Walmart", ex[~ex["wmt"]])):
        res[scope] = {}
        for nm, sub in (("recent", sub0[sub0.origin >= RECENT]), ("all", sub0), ("2025", sub0[sub0.origin < RECENT])):
            Sx = M.score_levels(sub, arms)
            res[scope][nm] = Sx
            print(f"\n=== {scope.upper()}, {nm.upper()} origins, existing series: cw / am / pm | bias ===")
            for x in arms:
                print(f"  {x:<14s}{Sx[CW][x]:7.2f}{Sx[AM][x]:7.2f}{Sx[PM][x]:7.2f}   bias {Sx['portfolio_bias'][x]:.3f}")
            if scope == "with Walmart":
                for lvl, _ in M.LEVELS_V2:
                    print(f"  BY HISTORY BAND, {lvl} (<13 / 13-25 / 26-51 / 52+ wks)")
                    for b, v in Sx[lvl]["by_band"].items():
                        print(f"    {b:<10s} n={v['n']:>7,}  " + "  ".join(f"{x}={v[x]:.1f}" for x in arms))
    rec = ex[ex.origin >= RECENT]
    res["by_line_recent"] = {}
    print("\nBY PRODUCT LINE, recent (cw / am / pm):")
    for ln, g in rec.groupby("line"):
        Sx = M.score_levels(g, arms)
        res["by_line_recent"][ln] = {lvl: {x: Sx[lvl][x] for x in arms} for lvl in (CW, AM, PM)}
        print(f"  {ln:<10s} actual {g.actual.sum():>12,.0f}  " + "  ".join(
            f"{x} {Sx[CW][x]:.1f}/{Sx[AM][x]:.1f}/{Sx[PM][x]:.1f}" for x in arms))
    print("\nPER-ORIGIN account x month, recent (candidate - direct_avg5; negative = better)")
    res["per_origin"] = {}
    for scope, sub0 in (("with Walmart", ex), ("without Walmart", ex[~ex["wmt"]])):
        rc = sub0[sub0.origin >= RECENT]
        per = {o: M.score_levels(g, arms)[AM] for o, g in rc.groupby("origin")}
        for y in arms[1:]:
            diffs = {o: round(v[y] - v["direct_avg5"], 2) for o, v in per.items()}
            wins = sum(dd < 0 for dd in diffs.values())
            pb = E.band_separated_diff(rc, y, "direct_avg5")["diff"]
            res["per_origin"][f"{scope}: {y}"] = {"diffs": diffs, "wins": wins, "sign_p": S.sign_test(wins, len(diffs)),
                                                  "pm_by_band": pb}
            print(f"  [{scope}] {y:<13s} wins {wins}/{len(diffs)}  pm-by-band {pb:+.2f}  "
                  + " ".join(f"{o}:{dd:+.2f}" for o, dd in diffs.items()))
    res["season_bias"] = B.season_bias(ex, arms)
    print("\nSEASONAL BIAS (forecast / actual):")
    for k, v in res["season_bias"].items():
        print(f"  {k}: " + "  ".join(f"{a}={v[a]:.3f}" for a in arms))
    R, R25 = res["with Walmart"]["recent"], res["with Walmart"]["2025"]
    rule = {}
    for y in arms[1:]:
        po = res["per_origin"][f"with Walmart: {y}"]
        c1 = R[AM][y] < R[AM]["direct_avg5"] and po["pm_by_band"] < 0 and R[CW][y] <= R[CW]["direct_avg5"]
        c2 = po["wins"] >= 5
        c3 = R25[AM][y] <= R25[AM]["direct_avg5"] + 2.0
        c4 = all(abs(v[y] - 1) <= 0.10 or abs(v[y] - 1) <= abs(v["direct_avg5"] - 1) for v in res["season_bias"].values())
        bands = R[PM]["by_band"]
        c7d = {b: round(bands[b][y] - bands[b]["direct_avg5"], 2) for b in ESTABLISHED if b in bands}
        c7 = all(v <= 0 for v in c7d.values())
        rule[y] = {"1 recent accuracy": bool(c1), "2 consistency >=5/6": bool(c2), "3 2025 no-harm": bool(c3),
                   "4 seasonal bias": bool(c4), "7 no established band worse": bool(c7), "7 detail": c7d,
                   "passes backtest part": bool(c1 and c2 and c3 and c4 and c7)}
    res["rule"] = rule
    print("\nAMENDMENT 1 + 2 (backtest part; forward confirmation still required):")
    for y, v in rule.items():
        print(f"  {y:<13s} " + "  ".join(f"{k}={'Y' if b else 'n'}" for k, b in v.items() if isinstance(b, bool))
              + f"  band diffs {v['7 detail']}")
    res["elapsed_s"] = round(time.time() - t0, 1)
    Path(out_json).write_text(json.dumps(res, indent=2, default=float))
    return res


def predictions(res: dict) -> dict:
    R = res["with Walmart"]["recent"]
    L = res["by_line_recent"]
    p = {
        "P1": {"max_parity_diff": max(res["parity_max_abs_diff_by_origin"].values()),
               "holds": max(res["parity_max_abs_diff_by_origin"].values()) == 0.0},
        "P2": {"line_avg5": R[AM]["line_avg5"], "direct_avg5": R[AM]["direct_avg5"],
               "holds": abs(R[AM]["line_avg5"] - R[AM]["direct_avg5"]) <= 0.5},
        "P3": {"puff_cw_nobar": L["PUFF"][CW]["nobar_avg5"], "puff_cw_direct": L["PUFF"][CW]["direct_avg5"],
               "holds": L["PUFF"][CW]["direct_avg5"] - L["PUFF"][CW]["nobar_avg5"] >= 0.3},
        "P4": {"sour_cw_line": L["SOUR PUFF"][CW]["line_avg5"], "sour_cw_direct": L["SOUR PUFF"][CW]["direct_avg5"],
               "holds": L["SOUR PUFF"][CW]["line_avg5"] > L["SOUR PUFF"][CW]["direct_avg5"]},
        "P5": {"passing": [y for y, v in res["rule"].items() if v["passes backtest part"]],
               "holds": not any(v["passes backtest part"] for v in res["rule"].values())},
    }
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["compute", "score"])
    ap.add_argument("--origins", default="")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo148_cache"))
    ap.add_argument("--feats-dir", default="outputs")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--results", default="")
    a = ap.parse_args()
    sp = lambda s: [x for x in s.split(",") if x]
    fd = Path(a.feats_dir)
    feats_r = json.loads((fd / "feats_recursive.json").read_text())
    feats_d = list(json.loads((fd / "direct_multihorizon_metrics_v11d.json").read_text())["features_used"])
    if a.cmd == "score":
        res = score_candidates(sp(a.results), PREFIX, CANDIDATES, "../outputs/mo148_product_lines.json",
                               "outputs/mo148_rows.parquet", feats_r, feats_d)
        res["predictions"] = predictions(res)
        Path("../outputs/mo148_product_lines.json").write_text(json.dumps(res, indent=2, default=float))
        print()
        for k, v in res["predictions"].items():
            print(k, "HOLDS" if v["holds"] else "FAILS", {kk: vv for kk, vv in v.items() if kk != "holds"})
        return
    origins = sp(a.origins) or [o[0] for o in M.ORIGINS_MONTHLY]
    t0 = time.time()
    summary = compute(origins, a.arms.split(","), a.out, feats_r, feats_d, a.threads, a.parallel)
    Path(a.out, f"{PREFIX}_compute_{'_'.join(origins)}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done {len(origins)} origin(s) in {time.time() - t0:,.0f}s", flush=True)


if __name__ == "__main__":
    main()
