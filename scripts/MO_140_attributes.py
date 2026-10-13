#!/usr/bin/env python
"""MO_140 - Give the fixed direct model fixed product attributes: product line, nutrition, price per bar, exclusivity.

PLAIN WORDS: tests whether telling the forecast model what each product IS -- Connor's product line (Puff / Sour
Puff / Chunk Puff / Duos Puff / Bar), its nutrition label (protein, sugar, calories), Connor's retail price per bar,
and whether it is a retailer exclusive -- improves forecasts, especially for new items, which could borrow from
similar products. These facts do not change week to week, so they carry no look-ahead (discontinued and
2027-innovation flags are excluded for that reason).

WHERE THIS CAME FROM
--------------------
Rob's Druid loads of Connor's item sheet (built_item_attributes, verified 2026-10-12); Jason's roadmap item (item
attributes, incl. Majority Type and direct protein grams rather than ranges). MO_137b/138/139: new items are the
direct model's weak spot. Attribute table: scripts/MO_140_attribute_table.py -> outputs/mo140_item_attributes.parquet
(249 keys; nutrition and price cover >= 98.8% of forecast volume; little variation: protein 15-19 g, sugar 4-10 g,
calories 110-180, price per bar 0.70-1.72 with 7 distinct values, 29 exclusives). Jason approved 2026-10-13.

PRIOR WORK (docs/SETTLED_FINDINGS.md incl. pending; README; scout 2026-10-13)
  No past test of product line, numeric nutrition, list price or exclusivity as inputs. nfp_protein_range was
  dropped as a near-constant (95.3% one level, README ~4377). Already inputs: pack_count, spins_flavor_canonical,
  source_brand (product line overlaps source_brand: BUILT PUFF / SOUR PUFF / BAR). MO_96: do not re-add pack_count
  (bars per unit excluded). v9 categorical drift: categorical inputs must keep identical categories at training and
  forecast time (one category list here, set once on the whole panel).

INPUTS ADDED: attr_majority_type (categorical), attr_protein_g, attr_sugar_g, attr_calories, attr_price_per_bar,
attr_exclusive -- joined on the 11-digit UPC key; unknown -> 'UNKNOWN' / missing.

ARMS (fixed direct model, MO_132.run_direct(refit=True, calendar=True), GPU worker)
  base_s42                      production inputs; must equal MO_133 direct_fixed_s42 exactly (parity)
  attr_s42, attr_s1, attr_s2, attr_s3, attr_s4   + attributes (5 seeds; compared with MO_133 direct_avg5)

LEVELS: item x week (cw), account x month (am), portfolio x month (pm; also within history bands); BY HISTORY BAND
(<13 / 13-25 / 26-51 / 52+ wks); recent (2025-12+) first, all 18 dates, 2025 no-harm; per-origin am, am within bands
and pm within bands with an exact sign test (6 recent dates overlap); all also without Walmart.

DEFINITION OF "BEATS" (recorded before the run): attr_avg5 beats direct_avg5 if, on the recent dates, it is better at
account x month AND at portfolio x month scored within bands, and not worse by more than 0.3 at item x week.
attr_avg5 is named in docs/PRODUCTION_DECISION_PREREG.md before results.

PREDICTIONS, RECORDED BEFORE ANY RUN (two-sided where a size is predicted):
  P1  Parity: base_s42 equals MO_133 direct_fixed_s42 exactly on every origin.
  P2  No meaningful overall change: recent account x month within +/-0.3 of direct_avg5 (so it does not "beat" it).
  P3  New items: recent item x week in the <13-week band improves by at least 0.5 point.
  P4  2025 no harm: account x month within +/-0.5 of direct_avg5 on 2025 dates.
  P5  Without Walmart, recent account x month within +/-0.3 of direct_avg5.
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
import MO_136_signals as S                           # file loader, sign test

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

OUT = Path("outputs/mo140_attributes.json")
OUT_ROWS = Path("outputs/mo140_rows.parquet")
RECENT = "2025-12"
G, K = S.G, S.K
ARMS = ["base_s42"] + [f"attr_s{s}" for s in (42, 1, 2, 3, 4)]


# ---------------------------------------------------------------- signals
ATTR_PATH = Path("outputs/mo140_item_attributes.parquet")
ATTR = ["attr_majority_type", "attr_protein_g", "attr_sugar_g", "attr_calories", "attr_price_per_bar", "attr_exclusive"]
MAJORITY = ["Puff", "Sour Puff", "Chunk Puff", "Duos Puff", "Bar", "UNKNOWN"]


def add_attrs(df: pd.DataFrame) -> pd.DataFrame:
    n0, cols0 = len(df), list(df.columns)
    t = pd.read_parquet(ATTR_PATH).set_index("key11")
    k = df["upc"].astype(str).str.replace(r"\D", "", regex=True).str[-11:]
    df = df.copy()
    df["attr_majority_type"] = pd.Categorical(k.map(t["majority_type"]).fillna("UNKNOWN").values, categories=MAJORITY)
    for src, dst in (("protein_g", "attr_protein_g"), ("sugar_g", "attr_sugar_g"), ("calories", "attr_calories"),
                     ("price_per_bar", "attr_price_per_bar")):
        df[dst] = k.map(t[src]).astype("float64").values
    df["attr_exclusive"] = k.map(t["exclusive"]).fillna(0).astype("float64").values
    assert len(df) == n0 and list(df.columns[:len(cols0)]) == cols0, "attributes changed rows or existing columns"
    assert df["attr_majority_type"].notna().all(), "unexpected product line value"
    return df


# ---------------------------------------------------------------- compute (worker)
def compute_origin(lbl: str, arms: list[str], out_dir: str, feats_r: list[str], feats_d: list[str],
                   threads: int) -> dict:
    P.D26.LGBM_BASE["n_jobs"] = threads
    t0 = time.time()
    df = add_attrs(E._panel(feats_r, feats_d))
    _, c, _, _ = next(o for o in M.ORIGINS_MONTHLY if o[0] == lbl)
    cut = M._utc(c)
    tr = M.cutoff_frame(df, cut)
    out, times = Path(out_dir), {}
    for arm in arms:
        p = out / f"mo140_{arm}_{lbl}.parquet"
        if p.exists():
            continue
        t1 = time.time()
        group, seed = arm.rsplit("_s", 1)
        feats = list(feats_d) + ([] if group == "base" else ATTR)
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


def score(dirs140, dirs133) -> None:
    t0 = time.time()
    r = pd.read_parquet(E.BASE_ROWS).reset_index(drop=True)
    r = r.drop(columns=[c for c in r.columns if c.startswith("model_seed")] + ["model"], errors="ignore")
    r["date"] = pd.to_datetime(r["date"], utc=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    for arm, dirs, prefix in [(a, dirs140, "mo140") for a in ARMS] + \
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
    r["attr_avg5"] = r[[f"attr_s{s}" for s in (42, 1, 2, 3, 4)]].mean(axis=1)
    r["wmt"] = r["account"].astype(str).str.upper().eq("WALMART")
    arms = ["flat", "conn_L4W", "direct_served", "direct_avg5", "attr_avg5"]
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
        for x, y in (("attr_avg5", "direct_avg5"), ("attr_avg5", "direct_served"), ("direct_avg5", "direct_served")):
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
    R, A, Y = res["with Walmart"]["recent"], res["with Walmart"]["all"], res["with Walmart"]["2025"]
    RX = res["without Walmart"]["recent"]
    y13 = R[CW]["by_band"].get("<13 wks", {})
    checks = [
        ("P1", max(parity.values()) == 0.0, f"max abs diff {max(parity.values()):.6f}"),
        ("P2", abs(R[AM]["attr_avg5"] - R[AM]["direct_avg5"]) <= 0.3,
         f"recent am attr_avg5 {R[AM]['attr_avg5']:.2f} vs direct_avg5 {R[AM]['direct_avg5']:.2f}"),
        ("P3", y13.get("direct_avg5", np.nan) - y13.get("attr_avg5", np.nan) >= 0.5,
         f"recent cw <13 band attr {y13.get('attr_avg5', np.nan):.2f} vs direct {y13.get('direct_avg5', np.nan):.2f}"),
        ("P4", abs(Y[AM]["attr_avg5"] - Y[AM]["direct_avg5"]) <= 0.5,
         f"2025 am attr {Y[AM]['attr_avg5']:.2f} vs direct {Y[AM]['direct_avg5']:.2f}"),
        ("P5", abs(RX[AM]["attr_avg5"] - RX[AM]["direct_avg5"]) <= 0.3,
         f"recent am without Walmart attr {RX[AM]['attr_avg5']:.2f} vs direct {RX[AM]['direct_avg5']:.2f}"),
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
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo140_cache"))
    ap.add_argument("--feats-dir", default="outputs")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--results140", default="")
    ap.add_argument("--results133", default="")
    a = ap.parse_args()
    sp = lambda s: [x for x in s.split(",") if x]
    fd = Path(a.feats_dir)
    feats_r = json.loads((fd / "feats_recursive.json").read_text())
    feats_d = list(json.loads((fd / "direct_multihorizon_metrics_v11d.json").read_text())["features_used"])
    if a.cmd == "score":
        score(sp(a.results140), sp(a.results133))
        return
    if a.cmd == "check-signals":
        df = add_attrs(E._panel(feats_r, feats_d))
        d = df[ATTR].describe(percentiles=[0.01, 0.5, 0.99]).T
        d["non_null"] = df[ATTR].notna().mean().round(3)
        print(d.round(3).to_string())
        print("\nproduct line by share of rows:", df["attr_majority_type"].value_counts(normalize=True).round(3).to_dict())
        return
    origins = sp(a.origins) or [o[0] for o in M.ORIGINS_MONTHLY]
    t0 = time.time()
    summary = compute(origins, a.arms.split(","), a.out, feats_r, feats_d, a.threads, a.parallel)
    Path(a.out, f"mo140_compute_{'_'.join(origins)}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done {len(origins)} origin(s) in {time.time() - t0:,.0f}s", flush=True)


if __name__ == "__main__":
    main()
