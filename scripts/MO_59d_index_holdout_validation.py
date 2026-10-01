"""MO_59d — Which n best matches ACTUAL observed seasonality? (out-of-sample test)

MO_59c measured internal stability (how much the index moves when you resample). That is
necessary but not sufficient: a stable index can still be stably wrong. This script asks the
question that matters instead — build the index from n series, then check how well it predicts
the observed seasonal pattern of series it has NEVER seen.

METHOD
------
  1. Fit STL once per qualifying series, keeping the (retail_account, upc) label.
  2. Hold out a stratified sample of real series spread across different retailers, so the
     test is not dominated by one account's rhythm.
  3. For each candidate n, build the index from the top-n by volume EXCLUDING every holdout
     series.
  4. Score against each holdout series' own STL seasonal component:
       corr        — shape agreement
       MAE         — level agreement (in index units)
       peak match  — does the index's peak week land within +/-2 weeks of the series' own?
  5. Print named examples so the result is inspectable rather than just a summary number.

A larger n is only better if it predicts held-out series better. This will show whether it does.

Run:  python MO_59d_index_holdout_validation.py [--holdout-per-retailer 3]
"""
from __future__ import annotations
import argparse, json, pickle, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

import importlib.util
_s = importlib.util.spec_from_file_location("m59b", str(Path(__file__).parent / "MO_59b_seasonal_index_rebuild.py"))
m59b = importlib.util.module_from_spec(_s); _s.loader.exec_module(m59b)

CACHE = Path("outputs/mo59d_labelled_cache.pkl")
OUT   = Path("outputs/mo59d_holdout_validation.json")
NS    = [20, 60, 200, 241, 265]


def fit_all(min_weeks: int = 104):
    if CACHE.exists():
        d = pickle.loads(CACHE.read_bytes())
        if d.get("min_weeks") == min_weeks:
            print(f"Loaded {len(d['fits'])} cached labelled fits"); return d["fits"], d["vols"]
    df = m59b.load()
    lens = df.groupby(m59b.GRAIN)["base_units"].size()
    vols = df.groupby(m59b.GRAIN)["base_units"].sum()
    qual = list(vols.loc[lens[lens >= min_weeks].index].sort_values(ascending=False).index)
    print(f"Fitting STL for {len(qual)} qualifying series …")
    fits = []
    for i, (a, u) in enumerate(qual, 1):
        r = m59b.seasonal_rows(m59b.extract(df, a, u))
        if r is not None:
            fits.append({"acct": a, "upc": u, "rows": r,
                         "vol": float(vols.loc[(a, u)]),
                         "level": float(r["level"].iloc[0])})
        if i % 50 == 0: print(f"  {i}/{len(qual)}")
    v = {(f["acct"], f["upc"]): f["vol"] for f in fits}
    CACHE.write_bytes(pickle.dumps({"min_weeks": min_weeks, "fits": fits, "vols": v}))
    print(f"Fitted {len(fits)}"); return fits, v


def series_curve(rows: pd.DataFrame) -> pd.Series:
    """One series' own seasonal shape, by week, centred — the ground truth to predict."""
    g = rows.groupby("week_of_year")["seasonal_norm"].mean().reindex(range(1, 53))
    g = g.interpolate().bfill().ffill()
    return g - g.mean()


def main(per_retailer: int):
    fits, _ = fit_all()
    N = len(fits)

    # Stratified holdout: top `per_retailer` series by volume from each of several retailers,
    # so no single account's rhythm dominates the test.
    by_acct: dict[str, list] = {}
    for f in sorted(fits, key=lambda x: -x["vol"]):
        by_acct.setdefault(f["acct"], []).append(f)
    accts = [a for a, v in sorted(by_acct.items(), key=lambda kv: -sum(x["vol"] for x in kv[1]))
             if len(v) >= per_retailer][:8]
    holdout = [f for a in accts for f in by_acct[a][:per_retailer]]
    hkeys = {(f["acct"], f["upc"]) for f in holdout}
    pool = [f for f in fits if (f["acct"], f["upc"]) not in hkeys]
    print(f"\nHoldout: {len(holdout)} series across {len(accts)} retailers "
          f"({', '.join(a[:12] for a in accts)})")
    print(f"Pool available to build the index: {len(pool)}\n")

    truth = {(f["acct"], f["upc"]): series_curve(f["rows"]) for f in holdout}

    print(f"  {'n':>5s} {'mean corr':>10s} {'mean MAE':>9s} {'peak within 2wk':>16s} {'index peak':>11s}")
    results = {}
    for n in NS:
        use = pool[:min(n, len(pool))]
        idx = m59b.build_index([f["rows"] for f in use], weighted=True)
        corrs, maes, hits = [], [], []
        for k, tc in truth.items():
            corrs.append(float(idx.corr(tc)))
            maes.append(float((idx - tc).abs().mean()))
            hits.append(abs(int(idx.idxmax()) - int(tc.idxmax())) <= 2
                        or abs(int(idx.idxmax()) - int(tc.idxmax())) >= 50)
        results[str(n)] = {"n_used": len(use), "mean_corr": float(np.mean(corrs)),
                           "mean_mae": float(np.mean(maes)),
                           "peak_within_2wk_frac": float(np.mean(hits)),
                           "index_peak_week": int(idx.idxmax())}
        print(f"  {len(use):>5d} {np.mean(corrs):>10.3f} {np.mean(maes):>9.4f} "
              f"{np.mean(hits)*100:>15.0f}% {int(idx.idxmax()):>11d}")

    best = max(results, key=lambda k: results[k]["mean_corr"])
    print(f"\n  Best mean correlation to held-out reality: n={results[best]['n_used']}")
    low = min(results, key=lambda k: results[k]["mean_mae"])
    print(f"  Lowest mean absolute error:                n={results[low]['n_used']}")

    print(f"\n  NAMED EXAMPLES — each holdout series' own peak vs the n=265 index")
    big = m59b.build_index([f["rows"] for f in pool], weighted=True)
    print(f"  {'retailer':>22s} {'upc':>16s} {'own peak':>9s} {'own trough':>11s} {'corr to index':>14s}")
    for f in holdout[:14]:
        tc = truth[(f["acct"], f["upc"])]
        print(f"  {f['acct'][:22]:>22s} {f['upc']:>16s} "
              f"{int(tc.idxmax()):>9d} {int(tc.idxmin()):>11d} {float(big.corr(tc)):>14.3f}")
    print(f"\n  (index peak wk {int(big.idxmax())}, trough wk {int(big.idxmin())})")

    results["_holdout"] = [{"acct": f["acct"], "upc": f["upc"],
                            "own_peak_week": int(truth[(f['acct'], f['upc'])].idxmax()),
                            "own_trough_week": int(truth[(f['acct'], f['upc'])].idxmin())}
                           for f in holdout]
    results["_note"] = ("Out-of-sample: the index is built EXCLUDING every holdout series. "
                        "Individual series are noisy, so per-series correlation is expected to "
                        "be modest; what matters is whether it IMPROVES with n.")
    OUT.write_text(json.dumps(results, indent=2)); print(f"\n  → {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout-per-retailer", type=int, default=3)
    a = ap.parse_args(); main(a.holdout_per_retailer)
