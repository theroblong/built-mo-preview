"""MO_155 - Does computing the promotion-history inputs as of each training week (no peeking at later
promotions) change the production model's accuracy?

WHERE THIS CAME FROM: the MO_151 skeptic found promo_lift_n_events acts as an item-tenure proxy and is
look-ahead in the served model; the harness rebuilds the five promotion statistics once per cutoff and
copies them onto every training row (MO_80 cutoff_frame), so a 2024 training row "sees" promotions that
happened later (before the cutoff). Jason (2026-10-15) asked for a valid temporal split that generalizes
without over-fitting; this fix comes before Optuna so the tuning does not tune around the flaw.

PRIOR WORK (docs/SETTLED_FINDINGS.md / README; topic words: promo_lift, look-ahead, leaky, cutoff features):
- SETTLED method rule (SETTLED): every fitted input is rebuilt from data up to each cutoff -- met per
  cutoff, but not per training row; this test extends the rule to row level.
- README ~1983-1985 lists the five promotion statistics and donor/competitor inputs as look-ahead in the
  served model; the harness neutralizes donor/competitor inputs (MO_80 NEUTRALIZE_DONOR_FEATURES) and
  rebuilds promotion statistics per cutoff. MO_151 skeptic (PROVISIONAL): tenure proxy, look-ahead.
- None found that tests per-row promotion statistics.

LAPTOP CHECK BEFORE WRITING (2025-12 cutoff): with MO_PROMO_ASOF=1 the forecast row of every series is
identical to the per-cutoff version; 74-79% of training rows change for the promotion statistics; every
other column is identical.

ARMS (same harness, same features, LightGBM settings unchanged):
  base_s42          per-cutoff promotion statistics (current), seed 42 -- parity with MO_133 direct_fixed_s42
  asof_s{42,1,2,3,4}  promotion statistics as of each row's week (MO_PROMO_ASOF=1), 5 seeds -> asof_avg5
REFERENCE: direct_avg5 (5-seed fixed direct model, outputs/mo140_rows.parquet).

LEVELS: cell x week, account x month, portfolio x month (band-separated), bias at portfolio x month; BY HISTORY
BAND (<13, 13-25, 26-51, 52+); recent (2025-12..2026-05) and 2025 origins; with and without Walmart.

DECISION RULE (written before running; this is a correctness fix, not a new signal): use the as-of
construction for the December retrain and for Optuna if asof_avg5 is not worse than direct_avg5 by more
than 0.3 points at account x month over all 18 origins AND no established band (13-25, 26-51, 52+) is worse
by more than 0.5 at recent portfolio x month. Otherwise stop and investigate before tuning.

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1  base_s42 equals MO_133 direct_fixed_s42 exactly (parity; the switch is off for it).
  P2  asof_avg5 is within +/-0.5 of direct_avg5 at recent account x month (a small effect).
  P3  asof_avg5 is not worse than direct_avg5 by more than 0.3 at all-origin account x month.
  P4  asof_avg5's Jan-Mar 2026 portfolio bias is within 0.03 of direct_avg5's (no seasonal effect).
  If P2/P3 fail toward worse, the leaked statistics were carrying real signal the as-of version lacks
  (e.g. too few events early in a series); if they fail toward better, the leak was hurting generalization.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

os.environ["MO_SEASONAL_MODE"] = "step"               # same harness settings as MO_133..MO_149
import importlib                                      # noqa: E402

import MO_80_quarterly_honest_backtest as M           # noqa: E402  import asserts forecast + training parity

importlib.reload(M)
import MO_148_product_line_models as L                # noqa: E402  shared engine (same harness settings)

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

PREFIX = "mo155"
SEEDS = (42, 1, 2, 3, 4)
ARMS = ["base_s42"] + [f"asof_s{s}" for s in SEEDS]
CANDIDATES = ("asof",)
BANDS = [(0, 13, "<13 wks"), (13, 26, "13-25 wks"), (26, 52, "26-51 wks"), (52, 10_000, "52+ wks")]


def compute_origin(lbl, arms, out_dir, feats_r, feats_d, threads):
    """Base arm with the switch off, as-of arms with it on (module flag read inside cutoff_frame)."""
    res = {}
    for flag, group in ((False, "base"), (True, "asof")):
        mine = [a for a in arms if a.startswith(group + "_")]
        if not mine:
            continue
        L.M.PROMO_ASOF = flag
        res[group] = L.compute_origin(lbl, mine, out_dir, feats_r, feats_d, threads, prefix=PREFIX,
                                      variants={group: L.v_base})
    L.M.PROMO_ASOF = False
    return {"origin": lbl, **res}


def compute(origins, arms, out_dir, feats_r, feats_d, threads, parallel):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    if parallel <= 1:
        return [compute_origin(o, arms, out_dir, feats_r, feats_d, threads) for o in origins]
    with ProcessPoolExecutor(max_workers=parallel, mp_context=get_context("spawn")) as ex:
        futs = [ex.submit(compute_origin, o, arms, out_dir, feats_r, feats_d, threads) for o in origins]
        return [f.result() for f in futs]


def predictions(res: dict) -> dict:
    R, A = res["with Walmart"]["recent"], res["with Walmart"]["all"]
    am = L.AM
    sb = res["season_bias"]
    q1 = next((v for k, v in sb.items() if "Jan-Mar 2026" in k), None)
    return {
        "P1 parity": {"max_abs_diff": max(res["parity_max_abs_diff_by_origin"].values()),
                      "holds": max(res["parity_max_abs_diff_by_origin"].values()) < 1e-6},
        "P2 recent am within 0.5": {"asof_avg5": R[am]["asof_avg5"], "direct_avg5": R[am]["direct_avg5"],
                                    "holds": abs(R[am]["asof_avg5"] - R[am]["direct_avg5"]) <= 0.5},
        "P3 all-origin am not worse by >0.3": {"asof_avg5": A[am]["asof_avg5"], "direct_avg5": A[am]["direct_avg5"],
                                               "holds": A[am]["asof_avg5"] - A[am]["direct_avg5"] <= 0.3},
        "P4 Jan-Mar 2026 bias within 0.03": {"asof_avg5": q1 and q1["asof_avg5"], "direct_avg5": q1 and q1["direct_avg5"],
                                             "holds": bool(q1) and abs(q1["asof_avg5"] - q1["direct_avg5"]) <= 0.03},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["compute", "score"])
    ap.add_argument("--origins", default="")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo155_cache"))
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
        out = "../outputs/mo155_promo_stats_asof.json"
        res = L.score_candidates(sp(a.results), PREFIX, CANDIDATES, out, "outputs/mo155_rows.parquet", feats_r, feats_d)
        res["predictions"] = predictions(res)
        A, R = res["with Walmart"]["all"], res["with Walmart"]["recent"]
        band = R[L.PM]["by_band"]
        worst = max(band[b]["asof_avg5"] - band[b]["direct_avg5"] for b in ("13-25 wks", "26-51 wks", "52+ wks") if b in band)
        res["decision"] = {"all_am_diff": A[L.AM]["asof_avg5"] - A[L.AM]["direct_avg5"], "worst_established_pm_diff": worst,
                           "adopt": (A[L.AM]["asof_avg5"] - A[L.AM]["direct_avg5"] <= 0.3) and worst <= 0.5}
        Path(out).write_text(json.dumps(res, indent=2, default=float))
        print("\nBY HISTORY BAND (<13 / 13-25 / 26-51 / 52+ wks), recent origins, asof_avg5 vs direct_avg5:")
        for lvl in (L.CW, L.AM, L.PM):
            for b, v in R[lvl]["by_band"].items():
                if b in [x[2] for x in BANDS]:
                    print(f"  {lvl:<18s} {b:<10s} n={v['n']:>7,}  direct_avg5={v['direct_avg5']:.2f}  asof_avg5={v['asof_avg5']:.2f}")
        print()
        for k, v in res["predictions"].items():
            print(k, "HOLDS" if v["holds"] else "FAILS", {kk: vv for kk, vv in v.items() if kk != "holds"})
        print("DECISION:", res["decision"])
        return
    origins = sp(a.origins) or [o[0] for o in M.ORIGINS_MONTHLY]
    t0 = time.time()
    summary = compute(origins, a.arms.split(","), a.out, feats_r, feats_d, a.threads, a.parallel)
    Path(a.out, f"{PREFIX}_compute_{'_'.join(origins)}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done {len(origins)} origin(s) in {time.time() - t0:,.0f}s", flush=True)


if __name__ == "__main__":
    main()
