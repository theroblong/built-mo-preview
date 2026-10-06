#!/usr/bin/env python
"""MO_121 - pooled vs BRAND-STRATIFIED models. Is one model fitting three processes?

JASON'S FRAMING, WHICH IS SHARPER THAN THE SHAP QUESTION
--------------------------------------------------------
    "In order to make a viable prediction for PUFF and SOUR PUFF versus BAR rather than
     all blended together, source_brand distinction seems essential to accurate
     forecasting."

This is a question about SPECIFICATION, not feature importance, and the distinction
matters. A feature can rank near-last on SHAP and still be essential as a STRATIFIER:
with 56 features and limited tree depth, a pooled model may never spend the splits
needed to isolate a regime even when the regimes genuinely differ. Feature importance
measures what the model DID use; it does not measure what a differently-specified model
WOULD have gained.

And the three regimes do differ, measured on the panel and harness-independent:

                     doors 0-13wk   doors 52+wk   exit rate   series 2023Q4 -> 2026Q3
    BUILT BAR          -1.16%/wk     -3.36%/wk      91.9%            241 -> 43
    BUILT PUFF         +2.56%/wk     +0.04%/wk      10.5%          144 -> 1,279
    BUILT SOUR PUFF    +0.91%/wk        --           1.0%            0 -> 277

Base-unit share moved from 34.1% BAR in 2023 to 0.3% in 2026. A pooled model trained on
all history is fitting an average of a dying line, a maturing line and a launching line.

ARMS, all scored through the REAL production path (M.run_production) so the harness
cannot differ between them -- the defect that invalidated a day of results:

  pooled        one model on all rows, as production does today
  per_brand     one model per source_brand, each trained ONLY on its own rows, routed
                at inference. The direct test of stratification.
  exclude_bar   one model trained WITHOUT any BAR rows, scored on non-BAR series only.
                The sharpest form of the hypothesis: does BAR's presence in training
                actively CONTAMINATE forecasts for PUFF and SOUR PUFF? Compared against
                pooled restricted to the same keys, so the comparison is like-for-like.

Results are broken out PER BRAND as well as overall, because stratification could help
one line and hurt another and an overall mean would hide it.

⚠️ Sample-size caveat, stated up front: by the later cutoffs BAR is thin (43 live series
by 2026Q3). A per-brand BAR model may be worse simply for lack of data, which is itself
an argument about whether stratification is viable rather than whether it is correct.
Per-arm training row counts are printed so that can be judged rather than assumed.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("outputs/mo121_brand_stratified.json")
TREES = 800
MIN_TRAIN_ROWS = 500          # below this a per-brand model is not trainable
BRANDS = ["BUILT PUFF", "BUILT BAR", "BUILT SOUR PUFF"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=TREES)
    a = ap.parse_args()

    os.environ["MO_SEASONAL_MODE"] = "anchor"       # MO_113's winner at production parity
    import MO_80_quarterly_honest_backtest as M
    importlib.reload(M)
    assert M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    df["_brand"] = df["source_brand"].astype(str)
    seasonal = M.load_seasonal_index()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]
    GC = M.GROUP_COLS

    print("MO_121 - pooled vs brand-stratified · PORTFOLIO-WIDE · "
          f"mode={M.SEASONAL_MODE} · refresh={M.FEATURE_REFRESH}\n")

    rows = {"pooled": {}, "per_brand": {}, "exclude_bar": {}}
    per_brand_detail = {}
    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {(k[:-1], k[-1]): float(v) for k, v in
                 act.groupby(GC + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        # brand of each series, from history at the cutoff only
        bmap = (df[df["__time"] <= cut].groupby(GC, observed=True)["_brand"]
                .agg(lambda s: s.mode().iat[0] if len(s.mode()) else "UNKNOWN"))

        # ── pooled: production as it runs today ───────────────────────────────
        pooled = M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, seasonal)

        # ── per_brand: one model per brand, each on its own rows ──────────────
        per = {}
        trained = {}
        for b in sorted(set(bmap.loc[list(ek & set(bmap.index))].unique())):
            sub = df[df["_brand"] == b]
            n_tr = int((sub["__time"] <= cut).sum())
            keys_b = {k for k in ek if bmap.get(k, "UNKNOWN") == b}
            if not keys_b:
                continue
            trained[b] = n_tr
            if n_tr < MIN_TRAIN_ROWS:
                # Not trainable alone -> fall back to pooled for those keys, so the arm is
                # scored on identical keys and a coverage gap cannot look like accuracy.
                per.update({k: v for k, v in pooled.items() if k[0] in keys_b})
                continue
            p = M.run_production(sub, feats, cut, qs, qe, keys_b, a.trees, fw, seasonal)
            per.update(p)
            per.update({k: v for k, v in pooled.items()
                        if k[0] in keys_b and k not in p})      # anything the sub-model skipped

        # ── exclude_bar: train without BAR, score non-BAR series ──────────────
        nonbar_keys = {k for k in ek if bmap.get(k, "UNKNOWN") != "BUILT BAR"}
        nb = df[df["_brand"] != "BUILT BAR"]
        exb = M.run_production(nb, feats, cut, qs, qe, nonbar_keys, a.trees, fw, seasonal)

        truth_nb = {k: v for k, v in truth.items() if k[0] in nonbar_keys}
        rows["pooled"][ql] = M.score(truth, pooled)
        rows["per_brand"][ql] = M.score(truth, per)
        rows["exclude_bar"][ql] = {
            "vs_pooled_same_keys": M.score(truth_nb, pooled),
            "excluded": M.score(truth_nb, exb)}

        # per-brand breakdown of pooled vs per_brand
        det = {}
        for b in BRANDS:
            kb = {k for k in ek if bmap.get(k, "UNKNOWN") == b}
            if not kb:
                continue
            tb = {k: v for k, v in truth.items() if k[0] in kb}
            sp, sb = M.score(tb, pooled), M.score(tb, per)
            if sp and sb:
                det[b] = {"n_series": len(kb), "train_rows": trained.get(b),
                          "pooled": sp["wmape"], "per_brand": sb["wmape"],
                          "delta": sb["wmape"] - sp["wmape"]}
        per_brand_detail[ql] = det

        pb = rows["pooled"][ql]; qb = rows["per_brand"][ql]
        eb = rows["exclude_bar"][ql]
        print(f"  {ql:<9s} pooled {pb['wmape']:>6.1f}  per_brand {qb['wmape']:>6.1f}  "
              f"({qb['wmape']-pb['wmape']:+5.2f})   "
              f"non-BAR: pooled {eb['vs_pooled_same_keys']['wmape']:>6.1f} "
              f"vs excl-BAR {eb['excluded']['wmape']:>6.1f} "
              f"({eb['excluded']['wmape']-eb['vs_pooled_same_keys']['wmape']:+5.2f})")

    def mean(d, f=lambda x: x["wmape"]):
        v = [f(x) for x in d.values() if x]
        return float(np.nanmean(v)) if v else float("nan")

    mp, mq = mean(rows["pooled"]), mean(rows["per_brand"])
    me_p = mean(rows["exclude_bar"], lambda x: x["vs_pooled_same_keys"]["wmape"])
    me_e = mean(rows["exclude_bar"], lambda x: x["excluded"]["wmape"])
    print(f"\n  {'arm':<34s} {'wMAPE':>8s}")
    print(f"  {'pooled (production today)':<34s} {mp:>8.2f}")
    print(f"  {'per_brand (stratified)':<34s} {mq:>8.2f}   {mq-mp:+.2f}pp")
    print(f"  {'non-BAR keys · pooled':<34s} {me_p:>8.2f}")
    print(f"  {'non-BAR keys · BAR excluded':<34s} {me_e:>8.2f}   {me_e-me_p:+.2f}pp")

    print("\n  Per-brand breakdown (pooled -> per_brand, mean over quarters):")
    print(f"    {'brand':<20s} {'pooled':>8s} {'per_brand':>10s} {'delta':>8s} {'train rows':>11s}")
    agg = {}
    for b in BRANDS:
        vals = [(d[b]["pooled"], d[b]["per_brand"], d[b].get("train_rows"))
                for d in per_brand_detail.values() if b in d]
        if not vals:
            continue
        p = float(np.nanmean([v[0] for v in vals]))
        q = float(np.nanmean([v[1] for v in vals]))
        tr = int(np.nanmean([v[2] for v in vals if v[2] is not None])) if any(
            v[2] is not None for v in vals) else None
        agg[b] = {"pooled": p, "per_brand": q, "delta": q - p, "mean_train_rows": tr}
        print(f"    {b:<20s} {p:>8.2f} {q:>10.2f} {q-p:>+8.2f} {str(tr):>11s}")

    print("\nVERDICT")
    if mq < mp - 0.5 or me_e < me_p - 0.5:
        print("  STRATIFICATION HELPS. One model was fitting three processes; brand is")
        print("  essential as a stratifier even though it ranks near-last on SHAP.")
    elif mq > mp + 0.5 and me_e > me_p + 0.5:
        print("  Stratification HURTS — the pooled model is borrowing strength across")
        print("  brands and the regimes are not different enough to pay for the split,")
        print("  or the per-brand samples are too thin. Check the train-row column.")
    else:
        print("  Neutral overall. Check the per-brand breakdown: stratification may help")
        print("  one line and hurt another, which an overall mean hides.")

    OUT.write_text(json.dumps({"by_quarter": rows, "per_brand": per_brand_detail,
                               "means": {"pooled": mp, "per_brand": mq,
                                         "nonbar_pooled": me_p, "nonbar_excl_bar": me_e},
                               "per_brand_means": agg}, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
