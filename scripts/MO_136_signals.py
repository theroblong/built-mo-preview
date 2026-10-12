#!/usr/bin/env python
"""MO_136 - New input signals for the fixed direct model: category/competitor, other-retailer, 26-week history.

WHERE THIS CAME FROM
--------------------
Rob's growth-signals proposal (docs/forecasting_growth_signals.md) and the signal register
(docs/drafts/SIGNAL_REGISTER_DRAFT.md, rows 1, 5, 6): signals that are untested, available now, and leak-free.
Competitor data on cloud compute cleared by Rob 2026-10-09. Category data: scripts/MO_136_category_extract.py
(spins_full, retailer rows only; outputs/mo136_category_weekly.parquet). Candidate model: the fixed direct model
(calendar targets + refit), the best 2026 candidate in MO_133/MO_135. Judged by docs/PRODUCTION_DECISION_PREREG.md
Amendment 1: recent forecast dates (2025-12 on) first, consistency counts, 2025 is a no-harm check.

PRIOR WORK (docs/SETTLED_FINDINGS.md incl. pending; README; prior-work scout 2026-10-12)
  Category/competitor level, trend, seasonal shape as inputs: never tested (register row 5). MO_53 tested only a
  competitor donor COUNT (pre-fix, hurt +0.09pp).
  Same UPC at other retailers as a direct-model input: never tested; MO_79's cold-start donor surrogate (incl. same
  UPC elsewhere) lost to last value (pre-fix, provisional).
  Sister BUILT items at the same retailer: NOT tested here -- MO_96 rejected own-brand donor features three times
  and SETTLED says do not re-add (SETTLED:340-341).
  Holiday flags: NOT tested here -- MO_54 rejected all 7 (SETTLED:291).
  Lag 26 / 26-week average: never tested.
  MO_107 'method space exhausted' and MO_52-57 'feature engineering closed' are pre-fix (provisional).
  MO_133/MO_135: direct_avg5 (5 seeds) recent 28.79/16.17/6.45; fails Amendment 1 consistency 4/6 vs served.

SIGNALS (all built from weeks <= the row's week, by calendar date, so no look-ahead; NaN where history is short)
  cat:  competitor base units at the same retailer x channel x geography (nutrition bars, non-BUILT):
        cat_comp_roll4, cat_comp_mom4_13 (4 vs 13-wk average), cat_comp_yoy4 (4-wk avg vs same 4 weeks a year
        earlier), cat_ly_next4 / cat_ly_next13 (last year's next 4 / 13 weeks vs last year's trailing 4: the
        category's seasonal step from competitors, uses weeks t-51..t-39), item_share_comp4 (item vs competitors).
  xret: the same UPC at the other retailers in the panel: xret_mom4_13, xret_share4 (this series' share of the
        UPC's total), xret_n_series (other series selling this week).
  l26:  base_units_lag26 (calendar), base_units_roll26_avg.

ARMS (fixed direct model, MO_132.run_direct(refit=True, calendar=True), on the GPU worker)
  base_s42                       production features; must equal MO_133's direct_fixed_s42 exactly (parity)
  cat_s42, cat_s1                + cat        (2 seeds; compared with MO_133 seeds 42 and 1 averaged)
  xret_s42, xret_s1              + xret
  l26_s42, l26_s1                + l26
  all_s42, all_s1, all_s2, all_s3, all_s4   + cat + xret + l26 (5 seeds; compared with direct_avg5)

LEVELS: item x week (cw), account x month (am), portfolio x month (pm, also scored within history bands);
BY HISTORY BAND (<13 / 13-25 / 26-51 / 52+ wks); recent (2025-12+) first, all 18, 2025 no-harm; per-origin
account x month wins with an exact sign test (fewer than 10 origins: no bootstrap intervals, MO_135 rule).

PREDICTIONS, RECORDED BEFORE ANY RUN:
  P1  Parity: base_s42 equals MO_133 direct_fixed_s42 exactly (max abs diff 0) on every origin.
  P2  cat (2-seed) beats the 2-seed base at band-separated portfolio x month on the recent origins.
  P3  xret (2-seed) beats the 2-seed base at item x week in the <13 and 13-25 bands (all origins).
  P4  l26 (2-seed) is within +/-0.3 of the 2-seed base at item x week (all origins): little effect.
  P5  all_avg5 is within +/-0.5 of direct_avg5 at account x month on the recent origins (no meaningful change).
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

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"
import MO_80_quarterly_honest_backtest as M        # import asserts forecast + training parity
import MO_132_one_yardstick as P                     # direct arms
import MO_133_ensembles as E                         # band-separated scoring, base rows

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

CAT_PATH = Path("outputs/mo136_category_weekly.parquet")
OUT = Path("outputs/mo136_signals.json")
OUT_ROWS = Path("outputs/mo136_rows.parquet")
RECENT = "2025-12"
G = ["upc", "channel_outlet", "retail_account", "geography_raw"]
K = ["channel_outlet", "retail_account", "geography_raw"]
GROUPS = {
    "cat": ["cat_comp_roll4", "cat_comp_mom4_13", "cat_comp_yoy4", "cat_ly_next4", "cat_ly_next13", "item_share_comp4"],
    "xret": ["xret_mom4_13", "xret_share4", "xret_n_series"],
    "l26": ["base_units_lag26", "base_units_roll26_avg"],
}
GROUPS["all"] = GROUPS["cat"] + GROUPS["xret"] + GROUPS["l26"]
ARMS = ["base_s42"] + [f"{g}_s{s}" for g in ("cat", "xret", "l26") for s in (42, 1)] + \
       [f"all_s{s}" for s in (42, 1, 2, 3, 4)]


# ---------------------------------------------------------------- signals
def _wide(long: pd.DataFrame, keys: list[str], val: str) -> pd.DataFrame:
    """Dense weekly matrix (weeks x key) so windows and lags follow the calendar, not row order."""
    w = long.pivot_table(index="__time", columns=keys, values=val, aggfunc="sum", observed=True)
    full = pd.date_range(w.index.min(), w.index.max(), freq="7D", tz="UTC")
    return w.reindex(full)


def _back(w: pd.DataFrame, n: int) -> pd.DataFrame:
    return w.rolling(n, min_periods=1).mean()


def _stack(w: pd.DataFrame, name: str, keys: list[str]) -> pd.DataFrame:
    s = w.stack(list(range(len(keys))), future_stack=True).rename(name).reset_index()
    return s.rename(columns={"level_0": "__time"}) if "__time" not in s.columns else s


def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    n0, cols0 = len(df), list(df.columns)
    df = df.copy()
    keycat = {c: df[c].dtype for c in G}
    for c in G:
        df[c] = df[c].astype(str)
    # --- cat: competitor base units at the same retailer x channel x geography
    cat = pd.read_parquet(CAT_PATH)
    cat = cat[(cat["subcategory"] == "WELLNESS & NUTRITION BARS") & (cat["is_built"] == 0)]
    cat = cat.groupby(["__time"] + K, as_index=False)["base_units"].sum()
    for c in K:
        cat[c] = cat[c].astype(str)
    cw = _wide(cat, K, "base_units")
    r4, r13 = _back(cw, 4), _back(cw, 13)
    fwd4 = cw[::-1].rolling(4, min_periods=1).mean()[::-1].shift(-1)     # mean of weeks s+1..s+4
    fwd13 = cw[::-1].rolling(13, min_periods=1).mean()[::-1].shift(-1)   # mean of weeks s+1..s+13
    feats = {
        "cat_comp_roll4": r4,
        "cat_comp_mom4_13": r4 / r13.where(r13 > 0),
        "cat_comp_yoy4": r4 / r4.shift(52).where(r4.shift(52) > 0),
        "cat_ly_next4": (fwd4 / r4.where(r4 > 0)).shift(52),     # uses weeks t-51..t-48 and t-55..t-52
        "cat_ly_next13": (fwd13 / r4.where(r4 > 0)).shift(52),   # uses weeks t-51..t-39
    }
    catf = None
    for name, w in feats.items():
        s = _stack(w, name, K)
        catf = s if catf is None else catf.merge(s, on=["__time"] + K, how="outer")
    df = df.merge(catf, on=["__time"] + K, how="left")
    df["item_share_comp4"] = df["base_units_roll4_avg"] / df["cat_comp_roll4"].where(df["cat_comp_roll4"] > 0)
    # --- xret: the same UPC at the other retailers in the panel
    own = _wide(df[G + ["__time", "base_units"]], G, "base_units")
    upc_level = own.columns.get_level_values(0)
    tot = own.T.groupby(upc_level).sum(min_count=1).T                       # weeks x upc
    sell = (own > 0).T.groupby(upc_level).sum().T
    tot_b = tot.reindex(columns=upc_level).set_axis(own.columns, axis=1)
    sell_b = sell.reindex(columns=upc_level).set_axis(own.columns, axis=1)
    other = tot_b.sub(own.fillna(0))
    o4, o13 = _back(other, 4), _back(other, 13)
    own4, tot4 = _back(own.fillna(0), 4), _back(tot_b.fillna(0), 4)   # same weeks on both sides: share <= 1
    xfe = {"xret_mom4_13": o4 / o13.where(o13 > 0), "xret_share4": own4 / tot4.where(tot4 > 0),
           "xret_n_series": sell_b - (own > 0).astype(float)}
    # --- l26: own history, calendar-aligned
    xfe["base_units_lag26"] = own.shift(26)
    xfe["base_units_roll26_avg"] = own.rolling(26, min_periods=1).mean()
    xf = None
    for name, w in xfe.items():
        s = _stack(w, name, G)
        xf = s if xf is None else xf.merge(s, on=["__time"] + G, how="outer")
    df = df.merge(xf, on=["__time"] + G, how="left")
    for c, dt in keycat.items():
        df[c] = df[c].astype(dt)
    assert len(df) == n0, "signals changed the row count"
    assert list(df.columns[:len(cols0)]) == cols0, "signals changed existing columns"
    new = GROUPS["all"]
    for c in new:
        df[c] = df[c].replace([np.inf, -np.inf], np.nan).astype("float64")
    return df


# ---------------------------------------------------------------- compute (worker)
def compute_origin(lbl: str, arms: list[str], out_dir: str, feats_r: list[str], feats_d: list[str],
                   threads: int) -> dict:
    P.D26.LGBM_BASE["n_jobs"] = threads
    t0 = time.time()
    df = add_signals(E._panel(feats_r, feats_d))
    _, c, _, _ = next(o for o in M.ORIGINS_MONTHLY if o[0] == lbl)
    cut = M._utc(c)
    tr = M.cutoff_frame(df, cut)
    out, times = Path(out_dir), {}
    for arm in arms:
        p = out / f"mo136_{arm}_{lbl}.parquet"
        if p.exists():
            continue
        t1 = time.time()
        group, seed = arm.rsplit("_s", 1)
        feats = list(feats_d) + ([] if group == "base" else GROUPS[group])
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
def _load(arm, dirs, prefix):
    parts = [pd.read_parquet(f).assign(origin=f.stem.rsplit("_", 1)[1])
             for d in dirs for f in sorted(Path(d).glob(f"{prefix}_{arm}_????-??.parquet"))]
    if not parts:
        raise SystemExit(f"no results for {prefix} {arm}")
    cp = pd.concat(parts, ignore_index=True)
    cp["date"] = pd.to_datetime(cp["date"], utc=True)
    assert not cp.duplicated(["origin", "series", "date"]).any(), arm
    return cp


def sign_test(wins: int, n: int) -> float:
    """Two-sided exact binomial p-value for wins out of n at p = 0.5."""
    k = min(wins, n - wins)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def score(dirs136, dirs133) -> None:
    t0 = time.time()
    r = pd.read_parquet(E.BASE_ROWS).reset_index(drop=True)
    r = r.drop(columns=[c for c in r.columns if c.startswith("model_seed")] + ["model"], errors="ignore")
    r["date"] = pd.to_datetime(r["date"], utc=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    parity = {}
    sources = [(a, dirs136, "mo136") for a in ARMS] + [(f"direct_fixed_s{k}", dirs133, "mo133") for k in (42, 1, 2, 3, 4)]
    for arm, dirs, prefix in sources:
        cp = _load(arm, dirs, prefix)
        n0 = len(r)
        r = r.merge(cp[["origin", "series", "date", arm]], on=["origin", "series", "date"], how="left")
        assert len(r) == n0
        miss = np.isnan(r[arm].values) & ~zero
        print(f"  {arm}: origins {cp['origin'].nunique()}, fell back to flat {int(miss.sum()):,}")
        r[arm] = np.where(zero, 0.0, np.where(miss, r["flat"], r[arm]))
    d = (r["base_s42"] - r["direct_fixed_s42"]).abs()
    parity = {o: float(v) for o, v in d.groupby(r["origin"]).max().items()}
    print(f"\nPARITY base_s42 vs MO_133 direct_fixed_s42: max abs diff {d.max():.6f}")
    r["base2"] = r[["direct_fixed_s42", "direct_fixed_s1"]].mean(axis=1)
    r["direct_avg5"] = r[[f"direct_fixed_s{k}" for k in (42, 1, 2, 3, 4)]].mean(axis=1)
    for g in ("cat", "xret", "l26"):
        r[f"{g}2"] = r[[f"{g}_s42", f"{g}_s1"]].mean(axis=1)
    r["all_avg5"] = r[[f"all_s{s}" for s in (42, 1, 2, 3, 4)]].mean(axis=1)
    arms = ["flat", "conn_L4W", "base2", "cat2", "xret2", "l262", "direct_avg5", "all_avg5"]
    r.to_parquet(OUT_ROWS)
    ex = r[~r["is_new"]]
    rec, old = ex[ex["origin"] >= RECENT], ex[ex["origin"] < RECENT]
    res = {"parity_max_abs_diff_by_origin": parity, "arms": arms,
           "all": M.score_levels(ex, arms), "recent": M.score_levels(rec, arms), "2025": M.score_levels(old, arms)}
    CW, AM, PM = "cell x week", "account x month", "portfolio x month"
    for name, sub in (("recent", rec), ("all", ex), ("2025", old)):
        S = res[name]
        print(f"\n=== {name.upper()} origins, existing series: cw / am / pm | bias ===")
        for x in arms:
            print(f"  {x:<12s}{S[CW][x]:7.2f}{S[AM][x]:7.2f}{S[PM][x]:7.2f}   bias {S['portfolio_bias'][x]:.3f}")
        for lvl, _ in M.LEVELS_V2:
            print(f"  BY HISTORY BAND, {lvl} (<13 / 13-25 / 26-51 / 52+ wks)")
            for b, v in S[lvl]["by_band"].items():
                print(f"    {b:<10s} n={v['n']:>7,}  " + "  ".join(f"{x}={v[x]:.1f}" for x in arms))
    pm = M._prep_scoring(rec, arms)
    g = pm[pm["full_month"]].groupby(["origin", "account", "month"])[["actual"] + arms].sum().reset_index()
    w = lambda dd, c: np.abs(dd["actual"] - dd[c]).sum() / dd["actual"].sum()
    res["per_origin_recent_am"] = {}
    print("\nPER-ORIGIN account x month, recent origins (candidate - comparison; negative = better), exact sign test")
    for x, y in (("cat2", "base2"), ("xret2", "base2"), ("l262", "base2"), ("all_avg5", "direct_avg5"),
                 ("all_avg5", "flat")):
        diffs = {o: round(100 * (w(dd, x) - w(dd, y)), 2) for o, dd in g.groupby("origin")}
        wins = sum(v < 0 for v in diffs.values())
        pb = E.band_separated_diff(rec, x, y)["diff"]
        res["per_origin_recent_am"][f"{x}-{y}"] = {"diffs": diffs, "wins": wins, "n": len(diffs),
                                                   "sign_p": sign_test(wins, len(diffs)), "pm_by_band": pb}
        print(f"  {x:>9s} - {y:<11s} wins {wins}/{len(diffs)} (p={sign_test(wins, len(diffs)):.2f})  "
              f"pm-by-band {pb:+.2f}  " + " ".join(f"{o}:{v:+.2f}" for o, v in diffs.items()))
    A, R = res["all"], res["recent"]
    band = lambda S, lvl, b, x: S[lvl]["by_band"].get(b, {}).get(x, np.nan)
    p3 = all(band(A, CW, b, "xret2") < band(A, CW, b, "base2") for b in ("<13 wks", "13-25 wks"))
    checks = [
        ("P1", max(parity.values()) == 0.0, f"max abs diff {max(parity.values()):.6f}"),
        ("P2", res["per_origin_recent_am"]["cat2-base2"]["pm_by_band"] < 0,
         f"recent pm-by-band cat2 - base2 {res['per_origin_recent_am']['cat2-base2']['pm_by_band']:+.2f}"),
        ("P3", p3, "all-origin cw <13: xret2 {:.2f} vs base2 {:.2f}; 13-25: {:.2f} vs {:.2f}".format(
            band(A, CW, "<13 wks", "xret2"), band(A, CW, "<13 wks", "base2"),
            band(A, CW, "13-25 wks", "xret2"), band(A, CW, "13-25 wks", "base2"))),
        ("P4", abs(A[CW]["l262"] - A[CW]["base2"]) <= 0.3, f"all cw l262 {A[CW]['l262']:.2f} vs base2 {A[CW]['base2']:.2f}"),
        ("P5", abs(R[AM]["all_avg5"] - R[AM]["direct_avg5"]) <= 0.5,
         f"recent am all_avg5 {R[AM]['all_avg5']:.2f} vs direct_avg5 {R[AM]['direct_avg5']:.2f}"),
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
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo136_cache"))
    ap.add_argument("--feats-dir", default="outputs")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--results136", default="")
    ap.add_argument("--results133", default="")
    a = ap.parse_args()
    sp = lambda s: [x for x in s.split(",") if x]
    fd = Path(a.feats_dir)
    feats_r = json.loads((fd / "feats_recursive.json").read_text())
    feats_d = list(json.loads((fd / "direct_multihorizon_metrics_v11d.json").read_text())["features_used"])
    if a.cmd == "score":
        score(sp(a.results136), sp(a.results133))
        return
    if a.cmd == "check-signals":                     # laptop sanity check of the new columns (no training)
        df = add_signals(E._panel(feats_r, feats_d))
        d = df[GROUPS["all"]].describe(percentiles=[0.01, 0.5, 0.99]).T
        d["non_null"] = df[GROUPS["all"]].notna().mean().round(3)
        print(d.round(3).to_string())
        return
    origins = sp(a.origins) or [o[0] for o in M.ORIGINS_MONTHLY]
    t0 = time.time()
    summary = compute(origins, a.arms.split(","), a.out, feats_r, feats_d, a.threads, a.parallel)
    Path(a.out, f"mo136_compute_{'_'.join(origins)}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done {len(origins)} origin(s) in {time.time() - t0:,.0f}s", flush=True)


if __name__ == "__main__":
    main()
