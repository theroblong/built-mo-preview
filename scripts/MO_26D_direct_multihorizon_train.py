"""MO_26D — Train DIRECT multi-horizon quantile models. Replaces the recursive AR loop.

WHY THIS EXISTS (all measured, 2026-10-01, four cutoffs)
--------------------------------------------------------
MO_27's recursive loop is a random walk wearing 56 features:
  * it reaches a fixed point by STEP 3 and flatlines — median ratio to last actual
    1.022 / 1.028 / 1.029, then 1.029-1.031 for steps 4-13
  * SD(forecast)/SD(actual) = 0.062 — it keeps 6% of real week-to-week variation
  * 31 of 56 features are FROZEN across the horizon, including every TDP and velocity
    feature, leaving week_sin/week_cos as the only exogenous time-varying inputs
  * it runs 7.9% HIGH (pooled bias 1.079)

Every exogenous patch failed:
  * TDP projection (MO_27g) — the stated #1 fix. A 14% TDP increase over 13 weeks moved the
    flattening ratio from 0.056 to 0.055. Dead.
  * STL index swap (MO_27e) — rejected at the gate, failed badly at 2026-03-08
  * YAGO blend weight (MO_27f) — W=0.40 never wins at any cutoff; it is an accidental bias
    corrector, not seasonality

That is the tell: `lag1` IS the previous prediction and the model's mapping on it is
near-identity, so no exogenous feature can get a word in. We were feeding better inputs into a
loop that structurally ignores them.

WHAT DIRECT MULTI-HORIZON CHANGES
---------------------------------
One model per horizon h = 1..13. Target = base_units at t+h; features = everything known at t.
No feedback, no self-reference.

  * `lag1` is a genuine lag, never a prediction. As h grows its informativeness decays and the
    model MUST lean on seasonality, TDP, promo character and lifecycle instead — the behavior
    the recursive loop suppressed.
  * Training matches production, so MO_28's 9x teacher-forced-vs-recursive gap closes and the
    tuning objective becomes valid for the first time.
  * SHORT SERIES ARE INCLUDED. The recursive loop needs a lag chain; this does not. A 6-week-old
    SKU carries NaN lags and LightGBM routes them natively. Excluding new items systematically
    under-predicts a brand whose growth comes from new items.

TARGET-WEEK SEASONALITY is passed explicitly: week_sin/cos describe t+h, NOT t. Without this the
model cannot know which week it is predicting and seasonality is unlearnable by construction.
This is the single most important detail in the file.

MO_30b prototype result at cutoff 2026-06-07, 2,126 series including short:
    h=1 wMAPE 10.67 | h=4 19.09 | h=8 26.82 | h=13 34.49 | POOLED 28.61
    bias 0.995  <-- versus recursive 1.064-1.165; the over-forecast disappears

Run:  python MO_26D_direct_multihorizon_train.py [--version v11d] [--val-weeks 13]
"""
from __future__ import annotations

import argparse
import json
import pickle
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

warnings.filterwarnings("ignore")

from mo_panel import (CAT_COLS, GROUP_COLS, drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_ak_hi_market_variants, warn_nested_rma_duplicates)

PARQUET        = Path("outputs/retailer_sales_weekly.parquet")
HORIZONS       = list(range(1, 14))
Q_ALPHAS       = {"q10": 0.10, "q50": 0.50, "q90": 0.90}
RECENCY_LAMBDA = 0.02
N_ESTIMATORS   = 3000
EARLY_STOP     = 100
SEASONAL_FEATS = ("week_sin", "week_cos", "week_sin26", "week_cos26")

LGBM_BASE = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20,
                 feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
                 reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)


def build_panel(feature_cols: list[str]) -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    if "week_of_year" in df.columns:
        woy = pd.to_numeric(df["week_of_year"], errors="coerce").fillna(1)
        df["week_sin26"] = np.sin(2 * np.pi * woy / 26)
        df["week_cos26"] = np.cos(2 * np.pi * woy / 26)
    for c in [c for c in feature_cols if c not in CAT_COLS]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c, fv in (("spins_flavor_canonical", "UNKNOWN"), ("source_brand", "UNKNOWN"),
                  ("geography_raw", "UNKNOWN"), ("spins_flavor_raw", "UNKNOWN"),
                  ("nfp_protein_range", "UNKNOWN")):
        if c in df.columns:
            df[c] = df[c].fillna(fv).astype(str).str.strip().replace("", fv)
    df = df.dropna(subset=["base_units"]).copy()

    print("  ── Panel rules (must match MO_26/MO_27) ──")
    df = fill_promo_mechanic_nulls(df)
    df = drop_military_accounts(df)
    df = drop_ak_hi_market_variants(df)
    df = drop_zero_volume_geographies(df, target="base_units")
    df = apply_rma_priority(df)
    warn_nested_rma_duplicates(df)
    # NOTE: drop_short_series is deliberately NOT called. Direct multi-horizon needs no lag
    # chain, so short series train and score natively instead of being excluded.
    for c in CAT_COLS:
        if c in df.columns:
            df[c] = df[c].astype("category")
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


def main(version: str, val_weeks: int, horizons: list[int]):
    print(f"MO_26D — direct multi-horizon training | version {version}\n")
    base = pickle.load(open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb"))
    feats = list(base.feature_name_)
    print(f"  Feature set inherited from v10 booster: {len(feats)} features")

    df = build_panel(feats)
    g = df.groupby(GROUP_COLS, observed=True)
    n_series = g.ngroups
    cut = df["__time"].max() - pd.Timedelta(weeks=val_weeks)
    print(f"\n  Panel {len(df):,} rows | {n_series:,} series (short series INCLUDED) "
          f"| val cutoff {cut.date()}\n")

    meta = {"model_version": version, "method": "direct_multihorizon",
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "features_used": feats, "horizons": horizons,
            "panel_rows": int(len(df)), "panel_series": int(n_series),
            "val_cutoff": str(cut.date()), "short_series_included": True,
            "per_horizon": {}}

    print(f"  {'h':>3s} {'q':>4s} {'train':>9s} {'val':>7s} {'iters':>6s} {'pinball':>9s}  top-3 gain")
    for h in horizons:
        d = df.copy()
        d["y"] = g["base_units"].shift(-h)
        d["t_target"] = d["__time"] + pd.Timedelta(weeks=h)
        # ── target-week seasonality: describes t+h, not t ──
        tw = d["t_target"].dt.isocalendar().week.astype(float)
        d["week_sin"] = np.sin(2 * np.pi * tw / 52)
        d["week_cos"] = np.cos(2 * np.pi * tw / 52)
        d["week_sin26"] = np.sin(2 * np.pi * tw / 26)
        d["week_cos26"] = np.cos(2 * np.pi * tw / 26)
        d = d.dropna(subset=["y"])
        tr = d[d["t_target"] <= cut]
        va = d[(d["__time"] <= cut) & (d["t_target"] > cut)]
        if len(tr) < 500 or len(va) < 50:
            print(f"  {h:>3d}  SKIPPED — train {len(tr):,} val {len(va):,}")
            continue
        wk_ago = ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0)
        sw = np.exp(-RECENCY_LAMBDA * wk_ago)
        hm = {}
        for tag, alpha in Q_ALPHAS.items():
            m = lgb.LGBMRegressor(objective="quantile", alpha=alpha,
                                  n_estimators=N_ESTIMATORS, **LGBM_BASE)
            m.fit(tr[feats], np.log1p(tr["y"]), sample_weight=sw,
                  eval_set=[(va[feats], np.log1p(va["y"]))], eval_metric="quantile",
                  callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False),
                             lgb.log_evaluation(-1)])
            with open(f"outputs/model_direct_h{h:02d}_{tag}_{version}.pkl", "wb") as fh:
                pickle.dump(m, fh)
            imp = pd.Series(m.booster_.feature_importance("gain"),
                            index=feats).sort_values(ascending=False)
            score = float(min(m.evals_result_["valid_0"]["quantile"]))
            hm[tag] = {"best_iteration": int(m.best_iteration_ or N_ESTIMATORS),
                       "val_pinball_loss": score,
                       "top_features": {k: float(v) for k, v in imp.head(10).items()}}
            if tag == "q50":
                print(f"  {h:>3d} {tag:>4s} {len(tr):>9,} {len(va):>7,} "
                      f"{hm[tag]['best_iteration']:>6,} {score:>9.6f}  "
                      + ", ".join(imp.head(3).index))
        meta["per_horizon"][str(h)] = hm

    Path(f"outputs/direct_multihorizon_metrics_{version}.json").write_text(
        json.dumps(meta, indent=2))
    print(f"\n  → outputs/direct_multihorizon_metrics_{version}.json")
    print(f"  → outputs/model_direct_h{{01..13}}_{{q10,q50,q90}}_{version}.pkl")

    # Did exogenous signal actually take over as the horizon lengthened? This is the whole
    # point of the change — if lag1 still dominates at h=13 the method did not do its job.
    print(f"\n  Share of top-10 q50 gain, by horizon:")
    print(f"  {'h':>3s} {'lag1':>8s} {'seasonality':>12s} {'TDP/velocity':>13s} {'promo':>8s}")
    for h in sorted(meta["per_horizon"], key=int):
        t = meta["per_horizon"][h]["q50"]["top_features"]
        tot = sum(t.values()) or 1.0
        lag1 = t.get("base_units_lag1", 0) / tot
        seas = sum(v for k, v in t.items() if k.startswith("week_")) / tot
        tdp = sum(v for k, v in t.items() if "tdp" in k or "velocity" in k) / tot
        promo = sum(v for k, v in t.items() if "promo" in k or "lift" in k) / tot
        print(f"  {int(h):>3d} {lag1*100:>7.1f}% {seas*100:>11.1f}% "
              f"{tdp*100:>12.1f}% {promo*100:>7.1f}%")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v11d")
    ap.add_argument("--val-weeks", type=int, default=13)
    ap.add_argument("--horizons", type=int, nargs="*", default=HORIZONS)
    a = ap.parse_args()
    main(a.version, a.val_weeks, a.horizons)
