"""MO_27b — Does the STL seasonal multiplier actually improve the forecast?

MO_27 applies the MO_59 portfolio seasonal index as a multiplier — units * (1 + stl_idx) —
but ONLY for series where the year-ago (YAGO) blend cannot fire, i.e. series with no lag52.
That is ~55% of series, including 51% of Target's volume.

Reasons to doubt it is helping:
  * MO_59d: the index correlates only ~0.48 with held-out series' own seasonality, gets the
    peak week right 29% of the time, and is NEGATIVELY correlated for 17% of series — for
    those, applying it moves the forecast the wrong way.
  * MO_59e: segmentation by channel or retailer makes it worse, and the panel cannot support
    retailer-level curves (Kroger 25 series, Walmart 5).
  * The model ALREADY has week_sin/week_cos/week_sin26/week_cos26 in FEATURE_COLS, so the
    multiplier is a SECOND seasonal layer on a model that already encodes seasonality.

So this measures the multiplier directly instead of arguing about it: take the v9 validation
predictions for no-YAGO series and compare error with and without the multiplier applied.

LIMITATION, stated plainly: this evaluates the multiplier on MO_26's validation split, where
predictions use ACTUAL lags (teacher-forced). MO_27 applies it inside a RECURSIVE loop where
the multiplier also feeds the next step's lag, so effects can compound there in a way this
does not capture. This answers "does the adjustment move predictions toward or away from
actuals", which is the precondition for it helping at all — not the full recursive effect.

Run:  python MO_27b_seasonal_multiplier_test.py
"""
from __future__ import annotations
import json, pickle, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

from mo_panel import (CAT_COLS, drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_short_series, GROUP_COLS)

MODEL_VERSION = "v9"
VAL_WEEKS     = 13
OUT           = Path("outputs/mo27b_seasonal_multiplier_test.json")


def wmape(a, p):
    d = np.abs(a).sum()
    return float(np.abs(a - p).sum() / d * 100) if d > 0 else float("nan")


def main():
    meta = json.loads(Path(f"outputs/retailer_sales_train_metrics_{MODEL_VERSION}.json").read_text())
    with open(f"outputs/model_retailer_sales_q50_{MODEL_VERSION}.pkl", "rb") as f:
        model = pickle.load(f)
    feats = list(model.feature_name_)
    seas = pd.read_csv("outputs/mo59_seasonal_index.csv")
    stl = dict(zip(seas["week_of_year"].astype(int), seas["seasonal_index"]))
    smeta = json.loads(Path("outputs/mo59_seasonal_index_meta.json").read_text())
    print(f"seasonal index: n_series={smeta['n_series']} peak wk {smeta['peak_week']} "
          f"trough wk {smeta['trough_week']}")

    df = pd.read_parquet("outputs/retailer_sales_weekly.parquet")
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    if "week_of_year" in df.columns:
        woy = pd.to_numeric(df["week_of_year"], errors="coerce").fillna(1)
        df["week_sin26"] = np.sin(2 * np.pi * woy / 26); df["week_cos26"] = np.cos(2 * np.pi * woy / 26)
    for c in [c for c in feats if c not in CAT_COLS]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    for c, fv in (("spins_flavor_canonical","UNKNOWN"),("source_brand","UNKNOWN"),
                  ("geography_raw","UNKNOWN"),("spins_flavor_raw","UNKNOWN"),
                  ("nfp_protein_range","UNKNOWN")):
        if c in df.columns: df[c] = df[c].fillna(fv).astype(str).str.strip().replace("", fv)
    df = df.dropna(subset=["base_units"]).copy()
    df = fill_promo_mechanic_nulls(df, verbose=False)
    df = drop_military_accounts(df, verbose=False)
    df = drop_zero_volume_geographies(df, verbose=False)
    df = apply_rma_priority(df, verbose=False)
    df = drop_short_series(df, verbose=False)
    for c in CAT_COLS:
        if c in df.columns:
            df[c] = df[c].astype("category")
            pc = model._Booster.pandas_categorical
            names = [x for x in feats if x in CAT_COLS]
            if c in names:
                i = names.index(c)
                if i < len(pc):
                    df[c] = pd.Categorical(df[c].astype(str), categories=pc[i])

    cutoff = df["__time"].max() - pd.Timedelta(weeks=VAL_WEEKS)
    hist = df[df["__time"] <= cutoff]
    val  = df[df["__time"] > cutoff].copy()
    # series history length AT the cutoff decides whether YAGO could fire in production
    wk = hist.groupby(GROUP_COLS, observed=True)["base_units"].count().rename("hist_wks")
    val = val.merge(wk, on=GROUP_COLS, how="left")
    val["hist_wks"] = val["hist_wks"].fillna(0)
    val["pred"] = np.expm1(model.predict(val[feats]))
    val["pred"] = val["pred"].clip(lower=0)
    val["woy"] = pd.to_numeric(val["week_of_year"], errors="coerce").fillna(1).astype(int)
    val["mult"] = val["woy"].map(lambda w: max(0.1, 1.0 + stl.get(w, 0.0)))
    val["pred_seas"] = (val["pred"] * val["mult"]).clip(lower=0)

    print(f"\nval window {val['__time'].min().date()} .. {val['__time'].max().date()} "
          f"| {len(val):,} rows")
    print(f"\n{'band':>26s} {'rows':>7s} {'wMAPE off':>10s} {'wMAPE ON':>10s} {'delta':>8s} {'verdict':>9s}")
    res = {}
    bands = [("NO-YAGO (<52 wks)  *applies*", val[val.hist_wks < 52]),
             ("  13-25 wks", val[(val.hist_wks >= 13) & (val.hist_wks < 26)]),
             ("  26-51 wks", val[(val.hist_wks >= 26) & (val.hist_wks < 52)]),
             ("YAGO (>=52) *not applied*", val[val.hist_wks >= 52]),
             ("ALL", val)]
    for lbl, s in bands:
        if len(s) == 0: continue
        off = wmape(s["base_units"].values, s["pred"].values)
        on  = wmape(s["base_units"].values, s["pred_seas"].values)
        verdict = "HELPS" if on < off else "HURTS"
        res[lbl.strip()] = {"rows": int(len(s)), "wmape_off": off, "wmape_on": on,
                            "delta_pp": on - off, "verdict": verdict}
        print(f"{lbl:>26s} {len(s):>7,} {off:>10.2f} {on:>10.2f} {on-off:>+8.2f} {verdict:>9s}")

    # per-series: for how many does it help vs hurt?
    tgt = val[val.hist_wks < 52]
    g = tgt.groupby(GROUP_COLS, observed=True)
    per = g.apply(lambda d: pd.Series({
        "off": wmape(d["base_units"].values, d["pred"].values),
        "on":  wmape(d["base_units"].values, d["pred_seas"].values)})).dropna()
    helped = (per["on"] < per["off"]).mean()
    print(f"\n  Per-series within the no-YAGO band ({len(per)} series):")
    print(f"    multiplier HELPS {helped*100:.0f}%   HURTS {(1-helped)*100:.0f}%")
    print(f"    median wMAPE off {per['off'].median():.2f}  on {per['on'].median():.2f}")
    res["_per_series"] = {"n": int(len(per)), "helped_frac": float(helped),
                          "median_off": float(per["off"].median()),
                          "median_on": float(per["on"].median())}
    res["_limitation"] = ("Teacher-forced validation split, not MO_27's recursive loop. "
                          "Measures whether the adjustment moves predictions toward actuals, "
                          "which is the precondition for it helping; does not capture "
                          "compounding through the AR lag feed.")
    OUT.write_text(json.dumps(res, indent=2)); print(f"\n  → {OUT}")


if __name__ == "__main__":
    main()
