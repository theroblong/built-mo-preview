#!/usr/bin/env python
"""MO_149 - Does giving the fixed direct model the "recent sales rate x current stores" numbers as inputs help?

PLAIN WORDS: the simple planning rule "sales per store over the last 4 weeks x stores carrying the item now" (L4W
velocity x stores; also the 12-week version) did well on its own and as a blend partner (MO_146/147), but blending
made established items' monthly totals worse. Here the two rule values are handed to the model as inputs instead, so
the trees can use them where they help. The model already sees the ingredients (4-week average units, sales per
distribution point, current distribution), but decision trees cannot multiply two inputs, so the products are new
information to them. Each value at week t uses only weeks up to t.

WHERE THIS CAME FROM: plan approved by Jason 2026-10-14 (step 2); docs/FORECAST_TEST_PLAN_V12.md:86-88 lists the
anchor "as a FEATURE" as "UNTESTED and the most natural answer".

PRIOR WORK (docs/SETTLED_FINDINGS.md, README, memory; scout 2026-10-14)
  - MO_127 / MO_128 / MO_129: L4W velocity x stores ties flat on the honest bench; strongest on 52+ week PUFF.
  - MO_125 (PROVISIONAL): "ship L4W alone, not blended"; MO_126: blend only in a band. MO_147: no blend passes.
  - FORECAST_TEST_PLAN_V12 mode D (anchor as a feature): untested -> this test.
  - SETTLED do-not-re-test: lag2/lag3, holiday flags, Fourier, pack_count -- not touched here.
  - Candidate l4wf_avg5 named in docs/PRODUCTION_DECISION_PREREG.md before results.

INPUTS ADDED (per series, per week t): l4w_vxs = sum(base units, last 4 weeks to t) / sum(TDP, same weeks) x TDP at
t; l12w_vxs = the same over 12 weeks. Missing when the TDP sum is 0.
ARMS (MO_132.run_direct(refit=True, calendar=True); GPU worker; seeds 42, 1, 2, 3, 4):
  base_s42          production inputs; must equal MO_133 direct_fixed_s42 exactly (parity)
  l4wf_s{seed}      production inputs + l4w_vxs + l12w_vxs
LEVELS: cell x week, account x month, portfolio x month (+ within each history band), bias; BY HISTORY BAND
(<13 / 13-25 / 26-51 / 52+ wks); BY PRODUCT LINE; with and without Walmart; recent (2025-12+), all 18, 2025.
RULE: Amendment 1 criteria 1-4 + Amendment 2 criterion 7, l4wf_avg5 vs direct_avg5.

PREDICTIONS, RECORDED BEFORE ANY RUN (two-sided where a size is predicted):
  P1 Parity: base_s42 equals MO_133 direct_fixed_s42 exactly on every origin.
  P2 l4wf_avg5 recent account x month is within +/-0.5 of direct_avg5 (the trees already have the ingredients).
  P3 l4wf_avg5 is better than direct_avg5 at recent portfolio x month within the 52+ week band (where L4W is
     strongest).
  P4 l4wf_avg5 does not pass the full backtest rule (criteria 1-4 and 7).
Usage:
  worker:  python mo149_job.py --origins 2025-01,2025-02 [--parallel 6 --threads 6]
  laptop:  python MO_149_velocity_inputs.py score --results <dir1,dir2,...>
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"               # same harness settings as MO_133..MO_148
import MO_80_quarterly_honest_backtest as M          # import asserts forecast + training parity
import MO_148_product_line_models as L               # shared engine (same harness settings)

assert M is L.M
assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

PREFIX = "mo149"
EXTRA = ("l4w_vxs", "l12w_vxs")
ARMS = ["base_s42"] + [f"l4wf_s{s}" for s in L.SEEDS]
CANDIDATES = ("l4wf",)


def add_velocity_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """Rolling 4- and 12-calendar-week base units per TDP x current TDP, per series, using weeks <= t only."""
    n0, cols0 = len(df), list(df.columns)
    d = df[M.GROUP_COLS + ["__time", "base_units", "tdp"]].copy()
    d["_i"] = np.arange(n0)
    d["_b"] = pd.to_numeric(d["base_units"], errors="coerce").fillna(0.0)
    d["_t"] = pd.to_numeric(d["tdp"], errors="coerce").fillna(0.0)
    v4, v12 = np.full(n0, np.nan), np.full(n0, np.nan)
    for _, g in d.groupby(M.GROUP_COLS, observed=True, sort=False):
        g = g.sort_values("__time").set_index("__time")
        idx, tdp_now = g["_i"].values, g["_t"].values
        for w, dest in ((4, v4), (12, v12)):
            rb = g["_b"].rolling(f"{7 * w}D").sum().values
            rt = g["_t"].rolling(f"{7 * w}D").sum().values
            dest[idx] = np.where(rt > 0, rb / np.where(rt > 0, rt, 1.0) * tdp_now, np.nan)
    df = df.copy()
    df["l4w_vxs"], df["l12w_vxs"] = v4, v12
    assert len(df) == n0 and list(df.columns[:len(cols0)]) == cols0, "velocity inputs changed rows or columns"
    return df


def v_l4wf(tr, feats, cut):
    return L.P.run_direct(tr, feats, cut, refit=True, calendar=True)


VARIANTS = {"base": L.v_base, "l4wf": v_l4wf}


def predictions(res: dict) -> dict:
    R = res["with Walmart"]["recent"]
    b52 = R[L.PM]["by_band"].get("52+ wks", {})
    return {
        "P1": {"max_parity_diff": max(res["parity_max_abs_diff_by_origin"].values()),
               "holds": max(res["parity_max_abs_diff_by_origin"].values()) == 0.0},
        "P2": {"l4wf_avg5": R[L.AM]["l4wf_avg5"], "direct_avg5": R[L.AM]["direct_avg5"],
               "holds": abs(R[L.AM]["l4wf_avg5"] - R[L.AM]["direct_avg5"]) <= 0.5},
        "P3": {"pm_52plus_l4wf": b52.get("l4wf_avg5"), "pm_52plus_direct": b52.get("direct_avg5"),
               "holds": bool(b52 and b52["l4wf_avg5"] < b52["direct_avg5"])},
        "P4": {"passes": res["rule"]["l4wf_avg5"]["passes backtest part"],
               "holds": not res["rule"]["l4wf_avg5"]["passes backtest part"]},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["compute", "score", "check-inputs"])
    ap.add_argument("--origins", default="")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo149_cache"))
    ap.add_argument("--feats-dir", default="outputs")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--results", default="")
    a = ap.parse_args()
    sp = lambda s: [x for x in s.split(",") if x]
    fd = Path(a.feats_dir)
    feats_r = json.loads((fd / "feats_recursive.json").read_text())
    feats_d = list(json.loads((fd / "direct_multihorizon_metrics_v11d.json").read_text())["features_used"])
    if a.cmd == "check-inputs":
        df = add_velocity_inputs(L.E._panel(feats_r, feats_d))
        print(df[list(EXTRA) + ["base_units_roll4_avg", "base_units"]].describe().round(2).to_string())
        print("corr l4w_vxs vs base_units_roll4_avg:", round(df["l4w_vxs"].corr(df["base_units_roll4_avg"]), 3))
        return
    if a.cmd == "score":
        res = L.score_candidates(sp(a.results), PREFIX, CANDIDATES, "../outputs/mo149_velocity_inputs.json",
                                 "outputs/mo149_rows.parquet", feats_r, feats_d)
        res["predictions"] = predictions(res)
        Path("../outputs/mo149_velocity_inputs.json").write_text(json.dumps(res, indent=2, default=float))
        print()
        for k, v in res["predictions"].items():
            print(k, "HOLDS" if v["holds"] else "FAILS", {kk: vv for kk, vv in v.items() if kk != "holds"})
        return
    origins = sp(a.origins) or [o[0] for o in M.ORIGINS_MONTHLY]
    t0 = time.time()
    summary = L.compute(origins, a.arms.split(","), a.out, feats_r, feats_d, a.threads, a.parallel,
                        prefix=PREFIX, variants=VARIANTS, prep=add_velocity_inputs, extra_feats=EXTRA)
    Path(a.out, f"{PREFIX}_compute_{'_'.join(origins)}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done {len(origins)} origin(s) in {time.time() - t0:,.0f}s", flush=True)


if __name__ == "__main__":
    main()
