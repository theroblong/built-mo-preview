#!/usr/bin/env python
"""MO_137 - Teach the fixed direct model the sales fade that follows a distribution expansion.

WHERE THIS CAME FROM
--------------------
MO_136b Walmart diagnostic (2026-10-12): Walmart grows in step changes (store count ~340 -> ~600 on 2025-08-17;
~740 -> ~1,100 on 2026-01-18), then sales per store fade (~40% from the August peak by late December with store
count flat). Every model over-forecast Walmart in Oct-Dec 2025 (bias 1.13-1.27, even last value 1.22) because each
starts from the post-expansion peak, and Walmart (27% of recent volume) then decides model comparisons (MO_136
skeptic). The fade is visible in history, so the model can be given it. Jason approved the test 2026-10-12.
(MO_137 was earlier pencilled in for item attributes; that test is now MO_138.)

PRIOR WORK (docs/SETTLED_FINDINGS.md incl. pending; README; MO_136 prior-work scout)
  Store count (TDP) level, 8-week z-score, week-over-week change and 4-week momentum are already inputs (feature
  list in direct_multihorizon_metrics_v11d.json). Nothing measures time since an expansion or the fade since it.
  Future store counts were worth < 1 pt even with perfect foresight (MO_95/105, pre-fix) -- this test is about
  the velocity fade AFTER a known past jump, not future store counts.
  TDP growth is the launch ramp (memory: tdp_growth_is_launch_ramp); growth is distribution (SETTLED).
  MO_136: category / other-retailer / 26-week signals improved portfolio totals only; Walmart decided the
  comparisons; no production switch.

SIGNALS (per series and per account, calendar-trailing only, so no look-ahead)
  A jump at week s: store count >= 1.25 x its maximum over weeks s-8..s-1 (and that maximum >= 1 store), i.e. a
  sustained expansion, not the launch (launch is already covered by weeks_since_launch).
  fade_wks_since_jump       weeks since the series' last jump (104 if none in history)
  fade_jump_size            store count after / before that jump
  fade_vel_vs_post_peak     4-week sales per store now vs the highest 4-week sales per store since that jump
  fade_vel_vs_peak26        4-week sales per store now vs its highest over the last 26 weeks
  fade_acct_wks_since_jump  weeks since the retailer-level BUILT store count (same account x channel x
                            geography, all items) last jumped (the Walmart-wide reset)
  fade_acct_jump_size       size of that retailer-level jump

ARMS (fixed direct model, MO_132.run_direct(refit=True, calendar=True), GPU worker)
  base_s42                      production features; must equal MO_133 direct_fixed_s42 exactly (parity)
  fade_s42, fade_s1, fade_s2, fade_s3, fade_s4    + fade signals (5 seeds; compared with MO_133 direct_avg5)

LEVELS: item x week (cw), account x month (am), portfolio x month (pm, also within history bands); BY HISTORY
BAND (<13 / 13-25 / 26-51 / 52+ wks); recent (2025-12+) first, all 18, 2025 no-harm; per-origin account x month
wins with an exact sign test (the 6 recent dates overlap, so p-values are optimistic); every comparison also
WITHOUT WALMART (MO_136 skeptic must-fix).

DEFINITION OF "BEATS" (recorded before the run): fade_avg5 beats direct_avg5 if, on the recent dates, it is better
at account x month AND at portfolio x month scored within bands, and not worse by more than 0.3 at item x week.
Any production use still needs docs/PRODUCTION_DECISION_PREREG.md Amendment 1 (fade_avg5 is named there before
results).

PREDICTIONS, RECORDED BEFORE ANY RUN:
  P1  Parity: base_s42 equals MO_133 direct_fixed_s42 exactly on every origin.
  P2  Walmart Oct-Dec 2025 bias: fade_avg5 is closer to 1.00 than direct_avg5 (1.21).
  P3  fade_avg5 beats direct_avg5 (definition above) on the recent dates.
  P4  No harm: fade_avg5 is within 0.5 of direct_avg5 at item x week over all 18 dates.
  P5  Walmart recent account x month: fade_avg5 below direct_avg5 (15.9).
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
import MO_133_ensembles as E                         # band-separated scoring, base rows, panel loader
import MO_134_recursive_fair_settings as B           # seasonal bias by year
import MO_136_signals as S                           # dense weekly helpers, sign test

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

OUT = Path("outputs/mo137_expansion_fade.json")
OUT_ROWS = Path("outputs/mo137_rows.parquet")
RECENT = "2025-12"
G, K = S.G, S.K
FADE = ["fade_wks_since_jump", "fade_jump_size", "fade_vel_vs_post_peak", "fade_vel_vs_peak26",
        "fade_acct_wks_since_jump", "fade_acct_jump_size"]
ARMS = ["base_s42"] + [f"fade_s{s}" for s in (42, 1, 2, 3, 4)]
JUMP, FLOOR, CAP = 1.25, 1.0, 104


# ---------------------------------------------------------------- signals
def _jumps(tdp: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """weeks since the last jump and its size, per column of a dense weekly store-count matrix."""
    prev = tdp.shift(1).rolling(8, min_periods=1).max()
    jump = (tdp >= JUMP * prev) & (prev >= FLOOR)
    idx = np.arange(len(tdp), dtype=float)[:, None] * np.ones((1, tdp.shape[1]))
    last = pd.DataFrame(np.where(jump.values, idx, np.nan), index=tdp.index, columns=tdp.columns).ffill()
    wks = (pd.DataFrame(idx, index=tdp.index, columns=tdp.columns) - last).fillna(CAP).clip(upper=CAP)
    size = pd.DataFrame(np.where(jump.values, (tdp / prev).values, np.nan), index=tdp.index,
                        columns=tdp.columns).ffill()
    return wks, size


def add_fade(df: pd.DataFrame) -> pd.DataFrame:
    n0, cols0 = len(df), list(df.columns)
    df = df.copy()
    keycat = {c: df[c].dtype for c in G}
    for c in G:
        df[c] = df[c].astype(str)
    tdp = S._wide(df[G + ["__time", "tdp"]], G, "tdp")
    base = S._wide(df[G + ["__time", "base_units"]], G, "base_units")
    wks, size = _jumps(tdp)
    vel4 = (base / tdp.where(tdp > 0)).rolling(4, min_periods=1).mean()
    # highest 4-week velocity since the last jump (segment-wise running max, reset at each jump)
    seg = (wks == 0).cumsum()
    post_peak = vel4.copy()
    for c in vel4.columns:
        post_peak[c] = vel4[c].groupby(seg[c]).cummax()
    feats = {"fade_wks_since_jump": wks, "fade_jump_size": size,
             "fade_vel_vs_post_peak": vel4 / post_peak.where(post_peak > 0),
             "fade_vel_vs_peak26": vel4 / vel4.rolling(26, min_periods=1).max().where(lambda x: x > 0)}
    f = None
    for name, w in feats.items():
        s = S._stack(w, name, G)
        f = s if f is None else f.merge(s, on=["__time"] + G, how="outer")
    df = df.merge(f, on=["__time"] + G, how="left")
    # retailer-level BUILT store count (all items at the same account x channel x geography)
    acct = df.groupby(["__time"] + K, as_index=False)["tdp"].sum()
    at = S._wide(acct, K, "tdp")
    awks, asize = _jumps(at)
    af = S._stack(awks, "fade_acct_wks_since_jump", K).merge(S._stack(asize, "fade_acct_jump_size", K),
                                                             on=["__time"] + K, how="outer")
    df = df.merge(af, on=["__time"] + K, how="left")
    for c, dt in keycat.items():
        df[c] = df[c].astype(dt)
    assert len(df) == n0, "signals changed the row count"
    assert list(df.columns[:len(cols0)]) == cols0, "signals changed existing columns"
    for c in FADE:
        df[c] = df[c].replace([np.inf, -np.inf], np.nan).astype("float64")
    return df


# ---------------------------------------------------------------- compute (worker)
def compute_origin(lbl: str, arms: list[str], out_dir: str, feats_r: list[str], feats_d: list[str],
                   threads: int) -> dict:
    P.D26.LGBM_BASE["n_jobs"] = threads
    t0 = time.time()
    df = add_fade(E._panel(feats_r, feats_d))
    _, c, _, _ = next(o for o in M.ORIGINS_MONTHLY if o[0] == lbl)
    cut = M._utc(c)
    tr = M.cutoff_frame(df, cut)
    out, times = Path(out_dir), {}
    for arm in arms:
        p = out / f"mo137_{arm}_{lbl}.parquet"
        if p.exists():
            continue
        t1 = time.time()
        group, seed = arm.rsplit("_s", 1)
        feats = list(feats_d) + ([] if group == "base" else FADE)
        P.D26.LGBM_BASE["random_state"] = int(seed)
        res = P.run_direct(tr, feats, cut, refit=True, calendar=True).rename(columns={"value": arm})
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
def _am(d: pd.DataFrame, arms: list[str]) -> pd.DataFrame:
    pm = M._prep_scoring(d, arms)
    return pm[pm["full_month"]].groupby(["origin", "account", "month"])[["actual"] + arms].sum().reset_index()


def _pct(d: pd.DataFrame, c: str) -> float:
    return 100 * np.abs(d["actual"] - d[c]).sum() / d["actual"].sum()


def score(dirs137, dirs133) -> None:
    t0 = time.time()
    r = pd.read_parquet(E.BASE_ROWS).reset_index(drop=True)
    r = r.drop(columns=[c for c in r.columns if c.startswith("model_seed")] + ["model"], errors="ignore")
    r["date"] = pd.to_datetime(r["date"], utc=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    for arm, dirs, prefix in [(a, dirs137, "mo137") for a in ARMS] + \
                             [(f"direct_fixed_s{k}", dirs133, "mo133") for k in (42, 1, 2, 3, 4)]:
        cp = S._load(arm, dirs, prefix)
        n0 = len(r)
        r = r.merge(cp[["origin", "series", "date", arm]], on=["origin", "series", "date"], how="left")
        assert len(r) == n0
        miss = np.isnan(r[arm].values) & ~zero
        print(f"  {arm}: origins {cp['origin'].nunique()}, fell back to flat {int(miss.sum()):,}")
        r[arm] = np.where(zero, 0.0, np.where(miss, r["flat"], r[arm]))
    served = pd.read_parquet("outputs/mo135_rows.parquet")[["origin", "series", "date", "direct_served"]]
    served["date"] = pd.to_datetime(served["date"], utc=True)
    r = r.merge(served, on=["origin", "series", "date"], how="left")
    assert r["direct_served"].notna().all()
    d = (r["base_s42"] - r["direct_fixed_s42"]).abs()
    parity = {o: float(v) for o, v in d.groupby(r["origin"]).max().items()}
    print(f"\nPARITY base_s42 vs MO_133 direct_fixed_s42: max abs diff {d.max():.6f}")
    r["direct_avg5"] = r[[f"direct_fixed_s{k}" for k in (42, 1, 2, 3, 4)]].mean(axis=1)
    r["fade_avg5"] = r[[f"fade_s{s}" for s in (42, 1, 2, 3, 4)]].mean(axis=1)
    r["wmt"] = r["account"].astype(str).str.upper().eq("WALMART")
    arms = ["flat", "conn_L4W", "direct_served", "direct_avg5", "fade_avg5"]
    r.to_parquet(OUT_ROWS)
    ex = r[~r["is_new"]]
    res = {"parity_max_abs_diff_by_origin": parity, "arms": arms}
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
    print("\nPER-ORIGIN account x month, recent origins (candidate - comparison; negative = better); exact sign test "
          "(the 6 dates overlap: p-values are optimistic)")
    res["per_origin"] = {}
    for scope, sub0 in (("with Walmart", ex), ("without Walmart", ex[~ex["wmt"]])):
        rec = sub0[sub0.origin >= RECENT]
        g = _am(rec, arms)
        for x, y in (("fade_avg5", "direct_avg5"), ("fade_avg5", "direct_served"), ("direct_avg5", "direct_served")):
            diffs = {o: round(_pct(dd, x) - _pct(dd, y), 2) for o, dd in g.groupby("origin")}
            wins = sum(v < 0 for v in diffs.values())
            pb = E.band_separated_diff(rec, x, y)["diff"]
            res["per_origin"][f"{scope}: {x}-{y}"] = {"diffs": diffs, "wins": wins, "sign_p": S.sign_test(wins, len(diffs)),
                                                      "pm_by_band": pb}
            print(f"  [{scope}] {x:>11s} - {y:<13s} wins {wins}/{len(diffs)} (p={S.sign_test(wins, len(diffs)):.2f})  "
                  f"pm-by-band {pb:+.2f}  " + " ".join(f"{o}:{v:+.2f}" for o, v in diffs.items()))
    res["season_bias"] = B.season_bias(ex, arms)
    od = ex[(ex.date >= "2025-10-01") & (ex.date < "2026-01-01")]
    wb = {x: float(od.loc[od.wmt, x].sum() / od.loc[od.wmt, "actual"].sum()) for x in arms}
    res["walmart_oct_dec_2025_bias"] = wb
    print("\nSEASONAL BIAS PER YEAR (all accounts)")
    for k, v in res["season_bias"].items():
        print(f"  {k:<13s} " + "  ".join(f"{a}={v[a]:.3f}" for a in arms))
    print("WALMART Oct-Dec 2025 bias: " + "  ".join(f"{a}={wb[a]:.3f}" for a in arms))
    wrec = ex[(ex.origin >= RECENT) & ex.wmt]
    wam = {x: _pct(_am(wrec, arms), x) for x in arms}
    print("WALMART recent account x month: " + "  ".join(f"{a}={wam[a]:.2f}" for a in arms))
    R, A = res["with Walmart"]["recent"], res["with Walmart"]["all"]
    pbr = res["per_origin"]["with Walmart: fade_avg5-direct_avg5"]["pm_by_band"]
    beats = R[AM]["fade_avg5"] < R[AM]["direct_avg5"] and pbr < 0 and R[CW]["fade_avg5"] <= R[CW]["direct_avg5"] + 0.3
    checks = [
        ("P1", max(parity.values()) == 0.0, f"max abs diff {max(parity.values()):.6f}"),
        ("P2", abs(wb["fade_avg5"] - 1) < abs(wb["direct_avg5"] - 1),
         f"Walmart Oct-Dec 2025 bias fade_avg5 {wb['fade_avg5']:.3f} vs direct_avg5 {wb['direct_avg5']:.3f}"),
        ("P3", beats, f"recent am {R[AM]['fade_avg5']:.2f} vs {R[AM]['direct_avg5']:.2f}; pm-by-band {pbr:+.2f}; "
                      f"cw {R[CW]['fade_avg5']:.2f} vs {R[CW]['direct_avg5']:.2f}"),
        ("P4", abs(A[CW]["fade_avg5"] - A[CW]["direct_avg5"]) <= 0.5,
         f"all cw {A[CW]['fade_avg5']:.2f} vs {A[CW]['direct_avg5']:.2f}"),
        ("P5", wam["fade_avg5"] < wam["direct_avg5"], f"Walmart recent am {wam['fade_avg5']:.2f} vs {wam['direct_avg5']:.2f}"),
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
    ap.add_argument("cmd", choices=["compute", "score", "check-signals"])
    ap.add_argument("--origins", default="")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo137_cache"))
    ap.add_argument("--feats-dir", default="outputs")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--results137", default="")
    ap.add_argument("--results133", default="")
    a = ap.parse_args()
    sp = lambda s: [x for x in s.split(",") if x]
    fd = Path(a.feats_dir)
    feats_r = json.loads((fd / "feats_recursive.json").read_text())
    feats_d = list(json.loads((fd / "direct_multihorizon_metrics_v11d.json").read_text())["features_used"])
    if a.cmd == "score":
        score(sp(a.results137), sp(a.results133))
        return
    if a.cmd == "check-signals":
        df = add_fade(E._panel(feats_r, feats_d))
        d = df[FADE].describe(percentiles=[0.01, 0.5, 0.99]).T
        d["non_null"] = df[FADE].notna().mean().round(3)
        print(d.round(3).to_string())
        w = df[df["retail_account"].astype(str).str.upper().eq("WALMART")]
        print("\nWalmart retailer-level jumps (weeks where fade_acct_wks_since_jump == 0):")
        print(sorted({str(t)[:10] for t in w.loc[w["fade_acct_wks_since_jump"] == 0, "__time"]}))
        return
    origins = sp(a.origins) or [o[0] for o in M.ORIGINS_MONTHLY]
    t0 = time.time()
    summary = compute(origins, a.arms.split(","), a.out, feats_r, feats_d, a.threads, a.parallel)
    Path(a.out, f"mo137_compute_{'_'.join(origins)}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done {len(origins)} origin(s) in {time.time() - t0:,.0f}s", flush=True)


if __name__ == "__main__":
    main()
