"""MO_59e — Does segmenting the seasonal index beat one portfolio curve?

MO_59d showed that a single portfolio curve predicts held-out series poorly — mean
correlation ~0.48, peak week right only 29% of the time, and NEGATIVE correlation for some
Albertsons series (applying it moves their forecast the wrong way). It also showed that
sample size barely matters out-of-sample: n=20 scored 0.472, n=241 scored 0.485.

The named examples pointed at why: the SAME UPC peaks in different weeks at different
retailers. Product 30362 peaks week 40 at Kroger, week 4 at Publix, week 38 at Albertsons.
That is a retailer effect (promo calendars, shelf resets, club cycles), not a product one.

So this tests segmentation against the same holdout:
    portfolio          one curve for everything (today's behaviour)
    by channel         one curve per channel_outlet
    by retailer        one curve per retail_account, falling back when a segment is thin
    by retailer+chan   finest grain, most fallback

A segment needs enough series to be stable — MO_59c showed small samples make the peak a coin
flip — so each scheme declares MIN_SEG_SERIES and falls back down the hierarchy when short.
Fallback usage is reported, because a scheme that "wins" by falling back to portfolio most of
the time has not actually demonstrated anything.

Every holdout series is excluded from every curve, so all scores are out-of-sample.

Run:  python MO_59e_segmented_index.py [--min-seg 25]
"""
from __future__ import annotations
import argparse, json, pickle, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

import importlib.util
_s = importlib.util.spec_from_file_location("m59b", str(Path(__file__).parent / "MO_59b_seasonal_index_rebuild.py"))
m59b = importlib.util.module_from_spec(_s); _s.loader.exec_module(m59b)
_d = importlib.util.spec_from_file_location("m59d", str(Path(__file__).parent / "MO_59d_index_holdout_validation.py"))
m59d = importlib.util.module_from_spec(_d); _d.loader.exec_module(m59d)

OUT = Path("outputs/mo59e_segmented_validation.json")


def main(min_seg: int, per_retailer: int):
    fits, _ = m59d.fit_all()
    df = m59b.load()
    # dominant channel per (acct, upc) — MO_59's grain collapses channel, so pick the one
    # carrying the most volume for that series
    ch = (df.groupby(["retail_account", "upc", "channel_outlet"])["base_units"].sum()
            .reset_index().sort_values("base_units", ascending=False)
            .drop_duplicates(["retail_account", "upc"])
            .set_index(["retail_account", "upc"])["channel_outlet"].to_dict())
    for f in fits:
        f["chan"] = ch.get((f["acct"], f["upc"]), "UNKNOWN")

    by_acct: dict[str, list] = {}
    for f in sorted(fits, key=lambda x: -x["vol"]):
        by_acct.setdefault(f["acct"], []).append(f)
    accts = [a for a, v in sorted(by_acct.items(), key=lambda kv: -sum(x["vol"] for x in kv[1]))
             if len(v) >= per_retailer][:8]
    holdout = [f for a in accts for f in by_acct[a][:per_retailer]]
    hkeys = {(f["acct"], f["upc"]) for f in holdout}
    pool = [f for f in fits if (f["acct"], f["upc"]) not in hkeys]
    truth = {(f["acct"], f["upc"]): m59d.series_curve(f["rows"]) for f in holdout}
    print(f"Holdout {len(holdout)} series / {len(accts)} retailers | pool {len(pool)} | "
          f"MIN_SEG_SERIES={min_seg}\n")

    portfolio = m59b.build_index([f["rows"] for f in pool], weighted=True)
    chan_idx, acct_idx, pair_idx = {}, {}, {}
    for key, store in (("chan", chan_idx), ("acct", acct_idx)):
        for f in pool:
            store.setdefault(f[key], []).append(f["rows"])
        for k in list(store):
            store[k] = (m59b.build_index(store[k], weighted=True)
                        if len(store[k]) >= min_seg else None)
    tmp: dict = {}
    for f in pool:
        tmp.setdefault((f["acct"], f["chan"]), []).append(f["rows"])
    for k, v in tmp.items():
        pair_idx[k] = m59b.build_index(v, weighted=True) if len(v) >= min_seg else None

    def pick(scheme, f):
        if scheme == "portfolio": return portfolio, "portfolio"
        if scheme == "channel":
            return (chan_idx.get(f["chan"]), "channel") if chan_idx.get(f["chan"]) is not None else (portfolio, "fallback")
        if scheme == "retailer":
            if acct_idx.get(f["acct"]) is not None: return acct_idx[f["acct"]], "retailer"
            if chan_idx.get(f["chan"]) is not None: return chan_idx[f["chan"]], "fallback:channel"
            return portfolio, "fallback:portfolio"
        if pair_idx.get((f["acct"], f["chan"])) is not None:
            return pair_idx[(f["acct"], f["chan"])], "retailer+chan"
        if acct_idx.get(f["acct"]) is not None: return acct_idx[f["acct"]], "fallback:retailer"
        if chan_idx.get(f["chan"]) is not None: return chan_idx[f["chan"]], "fallback:channel"
        return portfolio, "fallback:portfolio"

    print(f"  {'scheme':>16s} {'mean corr':>10s} {'mean MAE':>9s} {'peak<=2wk':>10s} {'neg corr':>9s} {'fallback':>9s}")
    res = {}
    for scheme in ("portfolio", "channel", "retailer", "retailer+chan"):
        corrs, maes, hits, lvls = [], [], [], []
        for f in holdout:
            idx, lvl = pick(scheme, f); tc = truth[(f["acct"], f["upc"])]
            c = float(idx.corr(tc)); corrs.append(c); lvls.append(lvl)
            maes.append(float((idx - tc).abs().mean()))
            d = abs(int(idx.idxmax()) - int(tc.idxmax())); hits.append(d <= 2 or d >= 50)
        fb = float(np.mean([l.startswith("fallback") for l in lvls]))
        neg = float(np.mean([c < 0 for c in corrs]))
        res[scheme] = {"mean_corr": float(np.mean(corrs)), "mean_mae": float(np.mean(maes)),
                       "peak_within_2wk": float(np.mean(hits)), "neg_corr_frac": neg,
                       "fallback_frac": fb}
        print(f"  {scheme:>16s} {np.mean(corrs):>10.3f} {np.mean(maes):>9.4f} "
              f"{np.mean(hits)*100:>9.0f}% {neg*100:>8.0f}% {fb*100:>8.0f}%")

    base = res["portfolio"]["mean_corr"]
    print(f"\n  vs portfolio baseline ({base:.3f}):")
    for k, v in res.items():
        if k != "portfolio":
            print(f"    {k:>14s}  corr {v['mean_corr']-base:+.3f}  "
                  f"MAE {v['mean_mae']-res['portfolio']['mean_mae']:+.4f}  "
                  f"(fallback {v['fallback_frac']*100:.0f}%)")
    print(f"\n  segments built: {sum(1 for v in chan_idx.values() if v is not None)} channels, "
          f"{sum(1 for v in acct_idx.values() if v is not None)} retailers, "
          f"{sum(1 for v in pair_idx.values() if v is not None)} retailer+channel")
    res["_config"] = {"min_seg_series": min_seg, "holdout": len(holdout), "pool": len(pool)}
    OUT.write_text(json.dumps(res, indent=2)); print(f"\n  → {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-seg", type=int, default=25)
    ap.add_argument("--holdout-per-retailer", type=int, default=3)
    a = ap.parse_args(); main(a.min_seg, a.holdout_per_retailer)
