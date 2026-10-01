"""MO_30b — DIRECT multi-horizon forecasting prototype. Replaces the recursive AR loop.

WHY THE RECURSIVE LOOP HAS TO GO
  MO_27c/e/f/g measured, across four cutoffs:
    * the forecast collapses to last_actual x 1.03 by step 3 (SD ratio 0.062)
    * 31 of 56 features are frozen for the whole horizon, including ALL TDP/velocity
    * it runs 7.9% HIGH (pooled bias 1.079)
    * every exogenous fix failed: the STL swap (rejected at the gate), the YAGO blend weight
      (W=0.40 never wins; it is an accidental bias corrector), and TDP projection — where a
      14% TDP increase over 13 weeks moved the flattening ratio from 0.056 to 0.055.
  That last one is the tell: `lag1` IS the previous prediction, the model's mapping on it is
  near-identity, and no exogenous feature can get a word in. We were feeding better inputs into
  a loop that ignores them.

DIRECT MULTI-HORIZON
  Train one model per horizon h = 1..13: target = base_units at t+h, features = everything known
  at t. No feedback, no self-reference. Consequences:
    * lag1 is a genuine lag, never a prediction. As h grows its informativeness decays and the
      model must lean on seasonality, TDP, promo character and lifecycle instead — which is
      exactly the behaviour the recursive loop suppressed.
    * training matches production, so the 9x teacher-forced-vs-recursive gap closes and MO_28's
      objective becomes valid.
    * SHORT SERIES CAN BE INCLUDED. The recursive loop needs a lag chain; this does not. A
      6-week-old SKU simply carries NaN lags and LightGBM routes them. Excluding new items
      systematically under-predicts a brand whose growth comes from new items — nickels and
      dimes add up. This is swept as a variant.

  TARGET-WEEK seasonality is passed explicitly (week_sin/cos of t+h, not of t). Without it the
  model cannot know WHICH week it is predicting, and seasonality is unlearnable by construction.

Reports per-horizon wMAPE, bias, and gain importance so we can see whether seasonality / TDP /
promo features actually bubble up as the horizon lengthens.

Run:  python MO_30b_direct_multihorizon.py [--horizons 1 4 8 13] [--include-short]
"""
from __future__ import annotations
import argparse, json, warnings
from pathlib import Path
import numpy as np, pandas as pd, lightgbm as lgb
warnings.filterwarnings("ignore")
from mo_panel import (CAT_COLS, drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_short_series, GROUP_COLS)

OUT = Path("outputs/mo30b_direct_multihorizon.json")
RECENCY_LAMBDA = 0.02


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = np.abs(a).sum()
    return float(np.abs(a - p).sum() / d * 100) if d > 0 else float("nan")


def build(include_short: bool):
    import pickle
    feats = list(pickle.load(open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = pd.read_parquet("outputs/retailer_sales_weekly.parquet")
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    if "week_of_year" in df.columns:
        woy = pd.to_numeric(df["week_of_year"], errors="coerce").fillna(1)
        df["week_sin26"] = np.sin(2*np.pi*woy/26); df["week_cos26"] = np.cos(2*np.pi*woy/26)
    for c in [c for c in feats if c not in CAT_COLS]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    for c, fv in (("spins_flavor_canonical","UNKNOWN"),("source_brand","UNKNOWN"),
                  ("geography_raw","UNKNOWN"),("spins_flavor_raw","UNKNOWN"),
                  ("nfp_protein_range","UNKNOWN")):
        if c in df.columns: df[c] = df[c].fillna(fv).astype(str).str.strip().replace("", fv)
    df = df.dropna(subset=["base_units"]).copy()
    for fn in (fill_promo_mechanic_nulls, drop_military_accounts,
               drop_zero_volume_geographies, apply_rma_priority):
        df = fn(df, verbose=False)
    n_all = df.groupby(GROUP_COLS, observed=True).ngroups
    if not include_short:
        df = drop_short_series(df, verbose=False)
    n_use = df.groupby(GROUP_COLS, observed=True).ngroups
    for c in CAT_COLS:
        if c in df.columns: df[c] = df[c].astype("category")
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True), feats, n_all, n_use


def main(horizons, include_short, cutoff_back):
    df, feats, n_all, n_use = build(include_short)
    print(f"series: {n_use} used of {n_all} available "
          f"({'INCLUDING' if include_short else 'excluding'} short series)")
    g = df.groupby(GROUP_COLS, observed=True)
    # target-week seasonality must describe t+h, not t
    base_feats = [f for f in feats if f not in ("week_sin","week_cos","week_sin26","week_cos26")]
    cut = df["__time"].max() - pd.Timedelta(weeks=cutoff_back)
    print(f"cutoff {cut.date()} | horizons {horizons}\n")
    print(f"  {'h':>3s} {'train':>8s} {'test':>7s} {'wMAPE':>8s} {'bias':>7s}  top gain features")
    res, preds_by_h = {}, {}
    for h in horizons:
        d = df.copy()
        d["y"] = g["base_units"].shift(-h)                     # target at t+h
        d["t_target"] = d["__time"] + pd.Timedelta(weeks=h)
        tw = d["t_target"].dt.isocalendar().week.astype(float)
        d["week_sin"] = np.sin(2*np.pi*tw/52); d["week_cos"] = np.cos(2*np.pi*tw/52)
        d["week_sin26"] = np.sin(2*np.pi*tw/26); d["week_cos26"] = np.cos(2*np.pi*tw/26)
        d = d.dropna(subset=["y"])
        tr = d[d["t_target"] <= cut]; te = d[(d["__time"] <= cut) & (d["t_target"] > cut)]
        if len(tr) < 500 or len(te) < 50: continue
        sw = np.exp(-RECENCY_LAMBDA * ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0))
        m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=1200,
                              learning_rate=0.05, num_leaves=63, min_child_samples=20,
                              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
                              reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)
        m.fit(tr[feats], np.log1p(tr["y"]), sample_weight=sw,
              eval_set=[(te[feats], np.log1p(te["y"]))],
              callbacks=[lgb.early_stopping(60, verbose=False), lgb.log_evaluation(-1)])
        p = np.clip(np.expm1(m.predict(te[feats])), 0, None)
        w, b = wmape(te["y"].values, p), float(p.sum()/te["y"].sum())
        imp = pd.Series(m.booster_.feature_importance("gain"), index=feats).sort_values(ascending=False)
        res[h] = {"wmape": w, "bias": b, "n_train": int(len(tr)), "n_test": int(len(te)),
                  "best_iter": int(m.best_iteration_ or 0),
                  "top": {k: float(v) for k, v in imp.head(8).items()}}
        preds_by_h[h] = (te["y"].values, p)
        print(f"  {h:>3d} {len(tr):>8,} {len(te):>7,} {w:>8.2f} {b:>7.3f}  "
              + ", ".join(imp.head(3).index))
    if res:
        A = np.concatenate([preds_by_h[h][0] for h in res])
        P = np.concatenate([preds_by_h[h][1] for h in res])
        pooled_w, pooled_b = wmape(A, P), float(P.sum()/A.sum())
        print(f"\n  POOLED across horizons: wMAPE {pooled_w:.2f}  bias {pooled_b:.3f}")
        print(f"  RECURSIVE baseline (same cutoff, MO_27f W=0.10): ~24.2 (YAGO) / ~33.7 (no-YAGO)")
        # does the model lean on seasonality/TDP more as h grows?
        print(f"\n  Does exogenous signal take over as the horizon lengthens?")
        print(f"  {'h':>3s} {'lag1 share':>11s} {'seasonality':>12s} {'TDP family':>11s}")
        for h in sorted(res):
            t = res[h]["top"]; tot = sum(t.values()) or 1
            lag1 = t.get("base_units_lag1", 0)/tot
            seas = sum(v for k, v in t.items() if k.startswith("week_"))/tot
            tdp = sum(v for k, v in t.items() if "tdp" in k or "velocity" in k)/tot
            print(f"  {h:>3d} {lag1*100:>10.1f}% {seas*100:>11.1f}% {tdp*100:>10.1f}%")
        res["_pooled"] = {"wmape": pooled_w, "bias": pooled_b,
                          "include_short": include_short, "n_series": n_use,
                          "cutoff": str(cut.date())}
    OUT.write_text(json.dumps(res, indent=2, default=float)); print(f"\n  → {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizons", type=int, nargs="+", default=[1, 2, 4, 6, 8, 10, 13])
    ap.add_argument("--include-short", action="store_true")
    ap.add_argument("--cutoff-back", type=int, default=13)
    a = ap.parse_args(); main(a.horizons, a.include_short, a.cutoff_back)
