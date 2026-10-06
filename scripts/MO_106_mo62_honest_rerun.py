#!/usr/bin/env python
"""MO_106 - recompute the MO_62 foundation-model comparison HONESTLY.

MO_62 (July 2026) is quoted in client-facing material -- FP&A report section 31
and Mo Chat's _DATA_GLOSSARY -- as "Aevah 6.1% vs foundation models 27.7-38.1%,
a 5x gap." That comparison does not hold up:

  MO_62 line 54:  LGBM_WMAPE = 6.14   # from outputs/v2_backtest_metrics.json (MO_38)

**MO_62 never ran Mo's model.** It hardcoded a constant from a DIFFERENT
experiment (MO_38) on a DIFFERENT series set, and ran the four foundation models
fresh. Three problems compound:

  1. MO_38's backtest was later found to LEAK -- README 202 (Oct 1) established
     that 6 of 7 quarters were scored by a model that had seen the future. MO_62
     ran three months before that discovery.
  2. 6.14% is in teacher-forced territory. Every honest number since is ~33%.
  3. MO_62 headlines MEDIAN-across-series; our standard metric is VOLUME-WEIGHTED
     wMAPE. Those are different quantities and the published figure uses the one
     that flatters a per-series average.

This script fixes the Mo side: same cutoff, same selection rules, same horizon,
but Mo is TRAINED ON DATA <= CUTOFF and scored in this run rather than quoted.
Both metrics are reported so the metric choice stops being a hidden variable.

Foundation models are NOT re-run here -- only TimesFM's row survived on disk, and
re-running Chronos/Moirai/Granite needs a clean env (README: they are blocked by a
torchvision conflict, and `mo-ml` must not be broken). Their PUBLISHED medians are
carried in for reference and clearly labelled as previously measured.
"""
from __future__ import annotations

import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import MO_80_quarterly_honest_backtest as M
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo106_mo62_honest.json")
CUTOFF = pd.Timestamp("2025-10-01", tz="UTC")
N_AHEAD, MIN_HISTORY, MIN_TEST, TOP_N = 13, 52, 10, 100
EXCLUDE_GEO = {"CRMA"}
TREES = 1200

# Previously published by MO_62 (median-across-series). Carried for reference only.
PUBLISHED = {"Chronos (Amazon)": 27.7, "Granite TTM (IBM)": 27.7,
             "Moirai (Salesforce)": 32.3, "TimesFM (Google)": 38.1}


def select_series(df):
    """MO_62's exact selection rules, applied to the same actuals parquet."""
    d = df[~df["geography_raw"].isin(EXCLUDE_GEO)]
    d = d[d["base_units"] >= 0]
    out = []
    for (acct, upc), grp in d.groupby(["retail_account", "upc"], observed=True):
        grp = grp.sort_values("__time")
        pre = grp[grp["__time"] <= CUTOFF]
        post = grp[grp["__time"] > CUTOFF].head(N_AHEAD + 4)
        if len(pre) < MIN_HISTORY or len(post) < MIN_TEST:
            continue
        if pre["base_units"].sum() < 100:
            continue
        act = (post.set_index("__time")["base_units"].resample("W-SUN").sum()
               .fillna(0).iloc[:N_AHEAD])
        if len(act) < MIN_TEST:
            continue
        out.append({"acct": acct, "upc": upc,
                    "vol": float(pre["base_units"].sum()), "actuals": act})
    out.sort(key=lambda x: -x["vol"])
    return out[:TOP_N]


def both_metrics(per_series):
    """MO_62's median-across-series AND our volume-weighted wMAPE."""
    rows = [r for r in per_series if r["denom"] > 0]
    if not rows:
        return float("nan"), float("nan"), 0
    med = float(np.median([r["wmape"] for r in rows]))
    vw = float(sum(r["abs_err"] for r in rows) / sum(r["denom"] for r in rows) * 100)
    return med, vw, len(rows)


def main() -> None:
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}

    sel = select_series(df)
    print("MO_106 - MO_62 recomputed honestly")
    print(f"  cutoff {CUTOFF.date()} | horizon {N_AHEAD} | {len(sel)} series selected "
          f"(MO_62 selected {TOP_N})")
    print(f"  Mo is TRAINED ON DATA <= CUTOFF and scored here, not quoted.\n")

    keys = {(r["upc"], None, r["acct"], None) for r in sel}
    # the panel key is (upc, channel, account, geography); match on upc+account
    want_pairs = {(r["upc"], r["acct"]) for r in sel}
    fw = M.future_weeks(weeks, CUTOFF, N_AHEAD)
    qs, qe = fw[0], fw[-1]

    hist = df[df["__time"] <= CUTOFF]
    eval_keys = {k for k in hist.groupby(GROUP_COLS, observed=True).groups
                 if (k[0], k[2]) in want_pairs}
    print(f"  {len(eval_keys)} panel cells map to those {len(want_pairs)} upc x account pairs")

    act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
    truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
             act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()
             if (u, a) in want_pairs}

    arms = {}
    print("  training direct multi-horizon...")
    arms["Mo direct (honest)"] = M.run_direct(
        df, feats, CUTOFF, qs, qe,
        hist[hist.apply(lambda r: (r["upc"], r["retail_account"]) in want_pairs, axis=1)]
            .groupby(GROUP_COLS, observed=True).tail(1),
        TREES, fw)
    print("  training recursive...")
    rec = M.run_production(df, feats, CUTOFF, qs, qe, eval_keys, TREES, fw, {})
    arms["Mo recursive (honest)"] = {k: (v["q50"] if isinstance(v, dict) else v)
                                     for k, v in rec.items()}
    flat = {}
    for key, g in hist.groupby(GROUP_COLS, observed=True):
        if key not in eval_keys:
            continue
        v = pd.to_numeric(g.sort_values("__time")["base_units"], errors="coerce").fillna(0)
        if len(v):
            for fd in fw:
                flat[(key, fd)] = float(v.iloc[-1])
    arms["flat carry-forward"] = flat

    print(f"\n  {'arm':<24s} {'median wMAPE':>13s} {'vol-weighted':>13s} {'n series':>9s}")
    results = {}
    for name, pred in arms.items():
        per = {}
        for (key, t), a in truth.items():
            p = pred.get((key, t))
            if p is None:
                continue
            r = per.setdefault(key, {"abs_err": 0.0, "denom": 0.0})
            r["abs_err"] += abs(a - p); r["denom"] += abs(a)
        for k, r in per.items():
            r["wmape"] = r["abs_err"] / r["denom"] * 100 if r["denom"] else float("nan")
        med, vw, n = both_metrics(list(per.values()))
        results[name] = {"median_wmape": med, "volume_weighted_wmape": vw, "n_series": n}
        print(f"  {name:<24s} {med:>12.1f}% {vw:>12.1f}% {n:>9d}")

    print(f"\n  Previously PUBLISHED foundation medians (MO_62, not re-run here):")
    for k, v in PUBLISHED.items():
        print(f"    {k:<22s} {v:>5.1f}%")
    print(f"    {'MO_62 quoted for Mo':<22s} {6.14:>5.1f}%   <- hardcoded from MO_38, "
          f"a backtest later found to LEAK")

    best = min(results.values(), key=lambda r: r["median_wmape"])["median_wmape"]
    print(f"\n  Honest Mo median on these series: {best:.1f}%")
    cheapest_fm = min(PUBLISHED.values())
    if best <= cheapest_fm:
        print(f"  -> Mo still beats the best foundation model ({cheapest_fm:.1f}%). "
              f"Claim survives, but the MAGNITUDE must be restated.")
    else:
        print(f"  -> Mo does NOT beat the best foundation model ({cheapest_fm:.1f}%). "
              f"The section-31 claim must be withdrawn and corrected with BUILT.")

    OUT.write_text(json.dumps({"cutoff": str(CUTOFF.date()), "n_selected": len(sel),
                               "arms": results, "published_foundation": PUBLISHED,
                               "mo62_quoted_for_mo": 6.14}, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
