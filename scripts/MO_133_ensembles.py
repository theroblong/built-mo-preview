#!/usr/bin/env python
"""MO_133 - Can averaging and combining models beat last value? (Tier 2, step 4)

WHERE THIS CAME FROM
--------------------
Jason, 2026-10-09: "use ML & AI better to do a much better job forecasting than just last
value carry-forward." MO_132 (skeptic-checked) found: the direct model's item forecasts swing
~10% with the training seed (aggregates +/-0.15 at cell x week); the fixed direct model ties
recursive at cell x week but wins weeks 1-6 and loses 7-13; and a 50/50 recursive + fixed
direct average beat recursive at all three levels -- found post hoc, so it is re-tested here
with averaged seeds, on the GPU worker, before anyone relies on it. Combining forecasts is the
most reliable gain in the forecasting literature (M4/M5; the M5 LightGBM winner averaged
recursive and non-recursive models).

PRIOR WORK (docs/SETTLED_FINDINGS.md incl. "Proposed changes, PENDING review"; README 232)
  MO_132  existing cw/am/pm: flat 32.59/21.12/12.84; recursive 35.45/22.95/13.77; direct_fixed
          34.78/21.18/9.29; blend (mo130+flat) 30.70/19.83/10.73. Post hoc 50/50 recursive +
          direct_fixed 32.18/20.29/10.47 (vs recursive -3.27*/-2.67*/-3.31*; vs flat ns/ns/-2.37*).
  MO_132 skeptic: seed-7 retrain moved direct item forecasts 10-11.5% (median); MO_129's
          recursive seed range understates direct-model noise ~10x.
  Parity (jason-mo-parity-001..004): never mix laptop and worker LightGBM results in one
          comparison -> every model arm here runs on the worker. flat / conn_L4W / mo130 are
          taken from MO_129/MO_130 rows: flat and conn_L4W are arithmetic (machine-independent);
          mo130 and blend are LightGBM from the laptop and are reported for reference only.
  MO_107  routing among existing methods is worth <= 2.38pp at portfolio x month.

ARMS (worker; lapsed and new series = 0 for every arm, the MO_129/MO_132 convention)
  recursive_w        MO_80.run_production (production recursive path), honest seasonal index
  direct_fixed_s{k}  MO_132 direct_fixed with LightGBM random_state k in (42, 1, 2, 3, 4)
  combinations (scoring, laptop -- arithmetic on worker forecasts):
    direct_avg5      mean of the 5 direct_fixed seeds
    rec_dir1         0.5 recursive_w + 0.5 direct_fixed_s42 (the registered rec_dirfix definition)
    rec_dir5         0.5 recursive_w + 0.5 direct_avg5
    rec_dir5_flat    (recursive_w + direct_avg5 + flat) / 3
  references: flat, conn_L4W (arithmetic); recursive (laptop MO_129, for the cross-machine check)

LEVELS: cell x week, account x month, portfolio x month (complete months), bias, BY HISTORY
BAND and origin (MO_80.score_levels); block-bootstrap CIs vs flat and vs recursive_w; SHAPE
with the fixed MO_132 scoring (precision of up/down calls vs 50% chance, call rate, rank
change correlation, origin-bootstrap CIs, turn precision).

PREDICTIONS, RECORDED BEFORE ANY WORKER RUN:
  P1  Seed averaging helps: direct_avg5 beats direct_fixed_s42 at cell x week by >= 0.5 and
      at account x month (point estimates).
  P2  rec_dir5 beats recursive_w at all three levels with CIs excluding 0 (replicates the
      MO_132 post-hoc result).
  P3  rec_dir5 vs flat: tie at cell x week (|diff| < 1); beats flat at portfolio x month
      with a CI excluding 0.
  P4  rec_dir5_flat beats flat at cell x week AND account x month with CIs excluding 0.
  P5  Cross-machine check: |recursive_w - recursive (laptop)| < 0.5 at cell x week.
  P6  Shape: no arm beats chance (precision CI > 50 and r CI > 0) at account x month.

ADDED 2026-10-09, BEFORE any start-anchored arm was computed (Jason, on the v5 chart: the
lines' shape looks right but they start at the wrong level; "they could get even closer with
some adjustments"). START-ANCHORED SHAPE: keep a model's 13-week path, rescale it so its
week-1 value equals the last known level:
    <parent>_anchF   = parent_h x clip(flat / parent_week1, 0.25, 4)
    <parent>_anchL4W = parent_h x clip(conn_L4W / parent_week1, 0.25, 4)
  for parents recursive_w, direct_avg5, rec_dir5 (week 1 = the parent's own first forecast
  week for that series and origin; parent_week1 <= 0 -> the anchor value, i.e. flat / L4W).
  (MO_132's *_lvlL4W matched the 13-week MEAN instead, and did not help.)
  P7  At least one start-anchored arm beats flat at cell x week AND account x month with
      CIs excluding 0.
  P8  Start-anchored arms keep their parent's shape: portfolio x week precision CI above 50
      for direct_avg5_anchF and rec_dir5_anchF.
  P9  On the 2026 origins only (2025-12 .. 2026-05, when a 104-week seasonal index first
      exists), some arm beats chance on shape at account x month. Only 6 origins: wide CIs.
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
import MO_132_one_yardstick as P                     # direct arms, shape scoring

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

SEEDS = (42, 1, 2, 3, 4)
BASE_ROWS = Path("outputs/mo130_rows_full_v8.parquet")
OUT = Path("outputs/mo133_ensembles.json")
OUT_ROWS = Path("outputs/mo133_rows.parquet")


# ---------------------------------------------------------------- compute (worker)
def _panel(feats_r, feats_d):
    df = M.load_panel(list(dict.fromkeys(feats_r + feats_d)))
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    return df


def compute_origin(lbl: str, arms: list[str], out_dir: str, feats_r: list[str], feats_d: list[str],
                   threads: int) -> dict:
    P.D26.LGBM_BASE["n_jobs"] = threads
    M.PROD_LGBM["n_jobs"] = threads
    if os.environ.get("MO_PANEL_PARQUET"):           # worker: MO_59 reads <its own dir>/outputs/...
        import MO_59_stl_changepoints as S
        S.PARQUET = Path(os.environ["MO_PANEL_PARQUET"])
    t0 = time.time()
    df = _panel(feats_r, feats_d)
    _, c, s, e = next(o for o in M.ORIGINS_MONTHLY if o[0] == lbl)
    cut, qs, qe = M._utc(c), M._utc(s), M._utc(e) + pd.Timedelta(days=6)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    out, times = Path(out_dir), {}
    tr = None
    for arm in arms:
        p = out / f"mo133_{arm}_{lbl}.parquet"
        if p.exists():
            continue
        t1 = time.time()
        if arm == "recursive_w":
            ev = M.build_eval_rows(df, cut, s, e)
            ek = set(ev.loc[~ev["is_new"], "key"])
            pr = M.run_production(df, feats_r, cut, qs, qe, ek, None,
                                  M.future_weeks(weeks, cut, M.HORIZON), M.seasonal_index_at(cut))
            res = pd.DataFrame({"series": P.sid_of([k for k, _ in pr]), "date": [d for _, d in pr],
                                arm: list(pr.values())})
        else:
            seed = int(arm.rsplit("_s", 1)[1])
            P.D26.LGBM_BASE["random_state"] = seed
            tr = M.cutoff_frame(df, cut) if tr is None else tr
            res = P.run_direct(tr, feats_d, cut, refit=True, calendar=True).rename(columns={"value": arm})
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        res.to_parquet(tmp)
        os.replace(tmp, p)
        times[arm] = round(time.time() - t1, 1)
        print(f"  {lbl} {arm}: {len(res):,} forecasts | {times[arm]}s", flush=True)
    return {"origin": lbl, "times": times, "total_s": round(time.time() - t0, 1)}


def compute(origins: list[str], arms: list[str], out_dir: str, feats_r, feats_d, threads: int,
            parallel: int) -> list[dict]:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    if parallel <= 1:
        return [compute_origin(o, arms, out_dir, feats_r, feats_d, threads) for o in origins]
    with ProcessPoolExecutor(max_workers=parallel, mp_context=get_context("spawn")) as ex:
        futs = [ex.submit(compute_origin, o, arms, out_dir, feats_r, feats_d, threads) for o in origins]
        return [f.result() for f in futs]


# ---------------------------------------------------------------- score (laptop)
def score(result_dirs: list[str]) -> None:
    t0 = time.time()
    r = pd.read_parquet(BASE_ROWS).rename(columns={"model": "recursive"})
    r = r.drop(columns=[c for c in r.columns if c.startswith("model_seed")]).reset_index(drop=True)
    r["date"] = pd.to_datetime(r["date"], utc=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    worker_arms = ["recursive_w"] + [f"direct_fixed_s{k}" for k in SEEDS]
    week1 = {}                                       # (origin, series) -> each arm's first forecast week
    for arm in worker_arms:
        # origin comes from the file name: horizons overlap, so (series, date) alone is ambiguous
        parts = [pd.read_parquet(f).assign(origin=f.stem.rsplit("_", 1)[1])
                 for d in result_dirs for f in sorted(Path(d).glob(f"mo133_{arm}_*.parquet"))]
        if not parts:
            raise SystemExit(f"no results for {arm}")
        cp = pd.concat(parts, ignore_index=True)
        cp["date"] = pd.to_datetime(cp["date"], utc=True)
        assert not cp.duplicated(["origin", "series", "date"]).any(), f"{arm}: duplicate forecasts"
        week1[arm] = cp.sort_values("date").groupby(["origin", "series"])[arm].first()
        n0 = len(r)
        r = r.merge(cp[["origin", "series", "date", arm]], on=["origin", "series", "date"], how="left")
        assert len(r) == n0
        miss = np.isnan(r[arm].values) & ~zero
        print(f"  {arm}: origins {r.loc[~np.isnan(r[arm].values), 'origin'].nunique()}, "
              f"fell back to flat {int(miss.sum()):,}")
        r[arm] = np.where(zero, 0.0, np.where(miss, r["flat"], r[arm]))
    seeds = [f"direct_fixed_s{k}" for k in SEEDS]
    r["direct_avg5"] = r[seeds].mean(axis=1)
    r["rec_dir1"] = 0.5 * r["recursive_w"] + 0.5 * r["direct_fixed_s42"]
    r["rec_dir5"] = 0.5 * r["recursive_w"] + 0.5 * r["direct_avg5"]
    r["rec_dir5_flat"] = (r["recursive_w"] + r["direct_avg5"] + r["flat"]) / 3
    # start-anchored shape (pre-registered P7-P9): parent path x clip(anchor / parent week 1)
    w1 = pd.DataFrame(week1)
    w1["direct_avg5"] = w1[seeds].mean(axis=1)
    w1["rec_dir5"] = 0.5 * w1["recursive_w"] + 0.5 * w1["direct_avg5"]
    idx = pd.MultiIndex.from_arrays([r["origin"], r["series"]])
    anchored = []
    for parent in ("recursive_w", "direct_avg5", "rec_dir5"):
        p1 = w1[parent].reindex(idx).values
        for tag, anchor in (("anchF", "flat"), ("anchL4W", "conn_L4W")):
            ratio = np.clip(r[anchor].values / np.where(p1 > 0, p1, np.nan), 0.25, 4.0)
            name = f"{parent}_{tag}"
            r[name] = np.where(zero, 0.0, np.where(np.isfinite(ratio), r[parent].values * ratio, r[anchor].values))
            anchored.append(name)
    arms = ["flat", "conn_L4W", "recursive", "recursive_w", "direct_fixed_s42", "direct_avg5",
            "rec_dir1", "rec_dir5", "rec_dir5_flat", "mo130", "blend"] + anchored
    r.to_parquet(OUT_ROWS)
    ex = r[~r["is_new"]]
    res = {"existing": M.score_levels(ex, arms), "planning_total": M.score_levels(r, arms), "arms": arms}
    E = res["existing"]
    print("\n=== EXISTING SERIES: error (lower is better) and bias ===")
    for x in sorted(arms, key=lambda k: E["cell x week"][k]):
        print(f"  {x:<18s}{E['cell x week'][x]:>8.2f}{E['account x month'][x]:>8.2f}"
              f"{E['portfolio x month'][x]:>8.2f}   bias {E['portfolio_bias'][x]:.3f}")
    for lvl, _ in M.LEVELS_V2:
        print(f"  BY HISTORY BAND, {lvl}")
        for b, v in E[lvl]["by_band"].items():
            print(f"    {b:<10s} n={v['n']:>7,}  " + "  ".join(
                f"{x}={v[x]:.1f}" for x in ("flat", "recursive_w", "direct_avg5", "rec_dir5", "rec_dir5_flat")))
    res["ci"] = {}
    print("\nMARGINS OF ERROR (moving-block bootstrap over origins, block 3)")
    for x, y in (("direct_avg5", "direct_fixed_s42"), ("rec_dir5", "recursive_w"), ("rec_dir5", "flat"),
                 ("rec_dir5_flat", "flat"), ("rec_dir1", "recursive_w"), ("recursive_w", "flat"),
                 ("recursive_w", "recursive")) + tuple((a, "flat") for a in anchored):
        row = []
        for lvl, _ in M.LEVELS_V2:
            b = M.bootstrap_diff(ex, x, y, level=lvl, n=2000)
            res["ci"][f"{x}-{y} | {lvl}"] = b
            row.append(f"{b['diff']:+6.2f} [{b['ci95'][0]:+.1f},{b['ci95'][1]:+.1f}]{'*' if b['significant'] else ' '}")
        print(f"  {x:>14s} - {y:<16s} " + "  ".join(row))
    exs = M._prep_scoring(ex, arms)
    res["shape"] = {"portfolio x week": P.shape_scores(exs, arms, ["origin"], "date"),
                    "account x month": P.shape_scores(exs[exs["full_month"]], arms, ["origin", "account"], "month"),
                    "turns (portfolio x week)": P.turn_scores(exs, arms)}
    late = exs[exs["origin"] >= "2025-12"]           # first origins with a 104-week seasonal index
    res["shape"]["2026 origins: portfolio x week"] = P.shape_scores(late, arms, ["origin"], "date")
    res["shape"]["2026 origins: account x month"] = P.shape_scores(
        late[late["full_month"]], arms, ["origin", "account"], "month")
    print("\n=== SHAPE (chance: precision 50, r 0; * = beats chance on both) ===")
    for lvl in ("portfolio x week", "account x month", "2026 origins: portfolio x week",
                "2026 origins: account x month"):
        Sl = res["shape"][lvl]
        print(f"  {lvl}")
        for x in arms:
            v = Sl[x]
            print(f"    {x:<18s} precision {v['precision']:5.1f} [{v['precision_ci'][0]:5.1f},{v['precision_ci'][1]:5.1f}]"
                  f"  calls {v['call_rate']:5.1f}%  r {v['change_r']:+.2f} "
                  f"[{v['change_r_ci'][0]:+.2f},{v['change_r_ci'][1]:+.2f}]{'  *' if v['beats_chance'] else ''}")
    ci = lambda k: res["ci"][k]
    CW, AM, PM = "cell x week", "account x month", "portfolio x month"
    A = res["shape"]["account x month"]
    checks = [
        ("P1", E[CW]["direct_fixed_s42"] - E[CW]["direct_avg5"] >= 0.5 and E[AM]["direct_avg5"] < E[AM]["direct_fixed_s42"],
         f"cw s42 {E[CW]['direct_fixed_s42']:.2f} -> avg5 {E[CW]['direct_avg5']:.2f}; am {E[AM]['direct_fixed_s42']:.2f} -> {E[AM]['direct_avg5']:.2f}"),
        ("P2", all(ci(f"rec_dir5-recursive_w | {l}")["ci95"][1] < 0 for l in (CW, AM, PM)),
         "rec_dir5 - recursive_w: " + ", ".join(f"{ci(f'rec_dir5-recursive_w | {l}')['diff']:+.2f}" for l in (CW, AM, PM))),
        ("P3", abs(ci(f"rec_dir5-flat | {CW}")["diff"]) < 1 and ci(f"rec_dir5-flat | {PM}")["ci95"][1] < 0,
         f"rec_dir5 - flat cw {ci(f'rec_dir5-flat | {CW}')['diff']:+.2f}, pm {ci(f'rec_dir5-flat | {PM}')['diff']:+.2f}"),
        ("P4", ci(f"rec_dir5_flat-flat | {CW}")["ci95"][1] < 0 and ci(f"rec_dir5_flat-flat | {AM}")["ci95"][1] < 0,
         f"rec_dir5_flat - flat cw {ci(f'rec_dir5_flat-flat | {CW}')['diff']:+.2f}, am {ci(f'rec_dir5_flat-flat | {AM}')['diff']:+.2f}"),
        ("P5", abs(E[CW]["recursive_w"] - E[CW]["recursive"]) < 0.5,
         f"cw recursive_w {E[CW]['recursive_w']:.2f} vs laptop {E[CW]['recursive']:.2f}"),
        ("P6", not any(A[x]["beats_chance"] for x in arms),
         "beats chance at am: " + (", ".join(x for x in arms if A[x]["beats_chance"]) or "none")),
        ("P7", any(ci(f"{a}-flat | {CW}")["ci95"][1] < 0 and ci(f"{a}-flat | {AM}")["ci95"][1] < 0 for a in anchored),
         "anchored - flat cw/am: " + "; ".join(
             f"{a} {ci(f'{a}-flat | {CW}')['diff']:+.2f}/{ci(f'{a}-flat | {AM}')['diff']:+.2f}" for a in anchored)),
        ("P8", all(res["shape"]["portfolio x week"][a]["precision_ci"][0] > 50
                   for a in ("direct_avg5_anchF", "rec_dir5_anchF")),
         "pw precision CI low: " + ", ".join(
             f"{a} {res['shape']['portfolio x week'][a]['precision_ci'][0]:.1f}" for a in ("direct_avg5_anchF", "rec_dir5_anchF"))),
        ("P9", any(res["shape"]["2026 origins: account x month"][x]["beats_chance"] for x in arms),
         "2026 am beats chance: " + (", ".join(x for x in arms if res["shape"]["2026 origins: account x month"][x]["beats_chance"]) or "none")),
    ]
    print("\nPREDICTIONS")
    res["predictions"] = {}
    for pid, ok, msg in checks:
        tag = "HOLDS" if ok else "FAILS"
        res["predictions"][pid] = {"result": tag, "detail": msg}
        print(f"  {pid} {tag:<6s} {msg}")
    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT} and {OUT_ROWS} ({time.time() - t0:,.0f}s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["compute", "score"])
    ap.add_argument("--origins", default="", help="comma list (default: all 18)")
    ap.add_argument("--arms", default=",".join(["recursive_w"] + [f"direct_fixed_s{k}" for k in SEEDS]))
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo133_cache"))
    ap.add_argument("--feats-dir", default="outputs", help="feats_recursive.json + direct metrics json")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--parallel", type=int, default=1, help="origins computed at once (processes)")
    ap.add_argument("--results", default="", help="score: comma list of result folders")
    a = ap.parse_args()
    if a.cmd == "score":
        score([d for d in a.results.split(",") if d] or ["outputs/mo133_cache"])
        return
    origins = [o for o in a.origins.split(",") if o] or [o[0] for o in M.ORIGINS_MONTHLY]
    fd = Path(a.feats_dir)
    feats_r = json.loads((fd / "feats_recursive.json").read_text())
    feats_d = list(json.loads((fd / "direct_multihorizon_metrics_v11d.json").read_text())["features_used"])
    t0 = time.time()
    summary = compute(origins, a.arms.split(","), a.out, feats_r, feats_d, a.threads, a.parallel)
    Path(a.out, f"mo133_compute_{'_'.join(origins)}.json").write_text(json.dumps(summary, indent=2))
    print(f"done {len(origins)} origin(s) in {time.time() - t0:,.0f}s", flush=True)


if __name__ == "__main__":
    main()
