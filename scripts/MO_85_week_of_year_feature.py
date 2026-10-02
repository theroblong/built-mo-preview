"""MO_85 — Does giving the model raw `week_of_year` let it learn the season itself?

THE DIAGNOSIS THIS TESTS
------------------------
The v11 model devotes only **4.1% of its total splitting power** to seasonality. Every seasonal
and year-ago feature ranks 27th or worse out of 56:

    week_cos 27 | week_sin26 30 | week_sin 31 | tdp_lag52 32 | base_units_lag52 33 | week_cos26 41

Two structural reasons, and this script tests the first:

1. REPRESENTATION. We supply only sin/cos of the week. That is correct for CONTINUITY — it is
   why December sits next to January and there is no wrap break — but it is a poor encoding for
   a TREE. Each of sin and cos is non-monotonic in week (sin peaks at wk 13, cos at wk 52/1), so
   isolating "weeks 1-13" requires several splits across two correlated features. Raw
   `week_of_year` makes it a single split: `week <= 13`. Trees are axis-aligned; they want the
   ordinal. The standard answer is to supply BOTH — sin/cos preserves the wrap, the raw ordinal
   is splittable — and let the model choose.

2. TRAINING TARGET (not tested here; see MO_28R). Training is one-step-ahead, where `lag1` is
   overwhelmingly the best predictor and seasonality genuinely adds little, so 4% is a CORRECT
   allocation for that task. We then run the model 13 weeks forward, where the AR features are
   its own output and seasonality is the only real information left. Proof this is a target
   problem rather than a capability problem: the DIRECT h=13 model puts week_sin and week_cos in
   its top 8 features. Same algorithm, same data — it learns the season when the target rewards it.

WHAT THIS MEASURES
------------------
A/B on identical panels, cutoffs, hyperparameters and recursive loop. The ONLY difference is
whether `week_of_year` is appended to the feature list. Reported per quarter so the Q1
turning-point quarters can be seen separately from the stable ones, plus where the new feature
lands by gain.

No blending policy is applied — this is the raw model, because the question is whether the MODEL
picks the season up, not whether we can correct it afterwards.

Run:  python MO_85_week_of_year_feature.py [--trees 800]
"""
from __future__ import annotations

import argparse
import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

warnings.filterwarnings("ignore")

from mo_panel import (CAT_COLS, GROUP_COLS, drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_ak_hi_market_variants)

PARQUET  = Path("outputs/retailer_sales_weekly.parquet")
OUT_JSON = Path("outputs/mo85_week_of_year_feature.json")
HORIZON  = 13
DYNAMIC_MOMENTUM = False   # True = also advance roll/z/momentum (production freezes them)
RECENCY_LAMBDA = 0.02
LGBM = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)

QUARTERS = [("Q1 2025", "2024-12-29"), ("Q2 2025", "2025-03-30"), ("Q3 2025", "2025-06-29"),
            ("Q4 2025", "2025-09-28"), ("Q1 2026", "2025-12-28"), ("Q2 2026", "2026-03-29"),
            ("Q3 2026", "2026-06-29")]

POLICIES = {"w0.10": ("const", 0.10), "w0.40": ("const", 0.40), "w0.60": ("const", 0.60),
            "w0.80": ("const", 0.80), "w1.00": ("const", 1.00),
            "turn_hi": ("turn", 0.60, 0.10), "turn_full": ("turn", 1.00, 0.10),
            # Jason's observation: even a FLAT line beats a downward slope, and last year's
            # arc suggests a climb then a gentle descent. Two arms that use no model at all:
            "flat_anchor": ("flat",),            # hold the anchor week constant, 13 weeks
            "yago_shape": ("shape",),            # anchor x (yago[t] / yago[anchor week])
            "shape_x_model": ("shapemix", 0.5)}  # half that arc, half the model


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = np.abs(a).sum()
    return float(np.abs(a - p).sum() / d * 100) if d > 0 else float("nan")


def load_panel(feats):
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    if "week_of_year" in df.columns:
        woy = pd.to_numeric(df["week_of_year"], errors="coerce").fillna(1)
        df["week_sin26"] = np.sin(2 * np.pi * woy / 26)
        df["week_cos26"] = np.cos(2 * np.pi * woy / 26)
    for c in [c for c in feats if c not in CAT_COLS]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c, fv in (("spins_flavor_canonical", "UNKNOWN"), ("source_brand", "UNKNOWN"),
                  ("geography_raw", "UNKNOWN"), ("spins_flavor_raw", "UNKNOWN"),
                  ("nfp_protein_range", "UNKNOWN")):
        if c in df.columns:
            df[c] = df[c].fillna(fv).astype(str).str.strip().replace("", fv)
    df = df.dropna(subset=["base_units"]).copy()
    df = fill_promo_mechanic_nulls(df, verbose=False)
    df = drop_military_accounts(df, verbose=False)
    df = drop_ak_hi_market_variants(df, verbose=False)
    df = drop_zero_volume_geographies(df, target="base_units", verbose=False)
    df = apply_rma_priority(df, verbose=False)
    for c in CAT_COLS:
        if c in df.columns:
            df[c] = df[c].astype("category")
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


def main(trees, account, channel):
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v11_full.pkl", "rb")).feature_name_)
    df = load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    ev = (df["retail_account"] == account) & (df["channel_outlet"] == channel)
    print(f"MO_85 — raw week_of_year A/B | {account} {channel}")
    print(f"  one model fit per cutoff; every weight policy scored on the same predictions\n")

    results = {}
    for ql, qc in QUARTERS:
        cut = pd.Timestamp(qc, tz="UTC")
        fw = list(weeks[weeks > cut][:HORIZON])
        if not fw:
            continue
        hist_all = df[df["__time"] <= cut]
        fut = df[ev & (df["__time"] > cut) & (df["__time"] <= fw[-1])]
        if fut.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 fut.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        eval_keys = {k[0] for k in truth}
        row = {"cutoff": qc, "n_series": len(eval_keys)}
        for arm, fl in (("baseline", feats), ("plus_woy", feats + ["week_of_year"])):
            tr = hist_all
            va = tr.tail(max(200, len(tr) // 10))
            m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=trees, **LGBM)
            wkago = ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0)
            m.fit(tr[fl], np.log1p(tr["base_units"]), sample_weight=np.exp(-RECENCY_LAMBDA * wkago),
                  eval_set=[(va[fl], np.log1p(va["base_units"]))], eval_metric="quantile",
                  callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])
            preds = {}
            for key, g in hist_all[ev.reindex(hist_all.index, fill_value=False)].groupby(
                    GROUP_COLS, observed=True):
                if key not in eval_keys:
                    continue
                g = g.sort_values("__time")
                if len(g) < 4:
                    continue
                s_ = pd.to_numeric(g.set_index("__time")["base_units"], errors="coerce").fillna(0)
                hist = list(s_.values)
                n_act = len(hist)
                lag52_seq = [float(hist[n_act - 53 + i]) if 0 <= (n_act - 53 + i) < n_act else np.nan
                             for i in range(1, len(fw) + 1)]
                state = g.iloc[-1].copy(); h2 = list(hist)
                arp_hist = list(pd.to_numeric(g["arp"], errors="coerce").ffill().values)
                for i, fd in enumerate(fw):
                    t2 = float(fd.isocalendar().week)
                    state["week_of_year"] = t2
                    state["week_sin"] = np.sin(2 * np.pi * t2 / 52)
                    state["week_cos"] = np.cos(2 * np.pi * t2 / 52)
                    state["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
                    state["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
                    state["base_units_lag1"]  = h2[-1]
                    state["base_units_lag4"]  = h2[-4]  if len(h2) >= 4  else np.nan
                    state["base_units_lag13"] = h2[-13] if len(h2) >= 13 else np.nan
                    state["base_units_lag52"] = lag52_seq[i]
                    if arp_hist:
                        _ac = arp_hist[-1]; _aw = arp_hist[-8:]
                        state["arp"] = _ac
                        state["arp_lag1"] = arp_hist[-2] if len(arp_hist) >= 2 else _ac
                        state["arp_roll8_avg"] = float(np.nanmean(_aw))
                        state["arp_roll8_std"] = float(np.nanstd(_aw)) if len(_aw) > 1 else 0.0
                        state["arp_wow_delta"] = 0.0
                    X = pd.DataFrame([state])[fl]
                    for c, cc in cats.items():
                        if c in X.columns:
                            X[c] = pd.Categorical(X[c], categories=cc)
                    p = float(np.clip(np.expm1(m.predict(X))[0], 0, None))
                    h2.append(p); preds[(key, fd)] = p
            ks = [k for k in truth if k in preds]
            a = np.array([truth[k] for k in ks]); p = np.array([preds[k] for k in ks])
            imp = pd.Series(m.booster_.feature_importance("gain"), index=fl).sort_values(ascending=False)
            tot = float(imp.sum()) or 1.0
            seas = float(sum(v for k, v in imp.items()
                             if k.startswith("week_") or "lag52" in k or "52w" in k))
            row[arm] = {"wmape": wmape(a, p),
                        "bias": float(p.sum() / a.sum()) if a.sum() else float("nan"),
                        "seasonal_gain_pct": seas / tot * 100,
                        "woy_rank": (int(list(imp.index).index("week_of_year")) + 1
                                     if "week_of_year" in imp.index else None)}
        results[ql] = row
        b, w_ = row["baseline"], row["plus_woy"]
        print(f"  {ql:<9s} baseline={b['wmape']:>5.1f} (season {b['seasonal_gain_pct']:.1f}%)   "
              f"plus_woy={w_['wmape']:>5.1f} (season {w_['seasonal_gain_pct']:.1f}%, "
              f"woy rank {w_['woy_rank']})   {w_['wmape']-b['wmape']:+.1f}pp")

    print(f"\n{'='*86}")
    print(f"  {'arm':<12s} " + " ".join(f"{q.split()[0]+q.split()[1][-2:]:>7s}" for q, _ in QUARTERS) + f" {'MEAN':>7s}")
    summary = {}
    for name in ("baseline", "plus_woy"):
        vals = [results[q][name]["wmape"] for q, _ in QUARTERS
                if q in results and name in results[q]]
        if not vals:
            continue
        summary[name] = {"mean_wmape": float(np.mean(vals)),
                         "per_quarter": {q: results[q][name]["wmape"] for q, _ in QUARTERS
                                         if q in results and name in results[q]}}
        cells = " ".join(f"{results[q][name]['wmape']:>7.1f}" for q, _ in QUARTERS
                         if q in results and name in results[q])
        print(f"  {name:<12s} {cells} {np.mean(vals):>7.1f}")
    if summary and "baseline" in summary and "plus_woy" in summary:
        d = summary["plus_woy"]["mean_wmape"] - summary["baseline"]["mean_wmape"]
        print(f"\n  VERDICT: adding raw week_of_year is {abs(d):.2f}pp "
              f"{'BETTER' if d < 0 else 'WORSE'} on average")
        print(f"  Seasonal share of gain: baseline "
              f"{np.mean([results[q]['baseline']['seasonal_gain_pct'] for q in results]):.1f}%"
              f"  ->  plus_woy "
              f"{np.mean([results[q]['plus_woy']['seasonal_gain_pct'] for q in results]):.1f}%")
    if summary:
        best = min(summary, key=lambda k: summary[k]["mean_wmape"])
        cur = summary.get("w0.10", {}).get("mean_wmape")
        print(f"\n  BEST: {best} at {summary[best]['mean_wmape']:.1f}")
        if cur:
            print(f"  Current production (w0.10) {cur:.1f}  -> "
                  f"{cur - summary[best]['mean_wmape']:+.1f}pp available")
        q1 = {n: summary[n]["per_quarter"].get("Q1 2026") for n in summary}
        print(f"\n  Q1 2026 specifically (the black eye):")
        for n, v in sorted(q1.items(), key=lambda x: (x[1] is None, x[1])):
            if v is not None:
                print(f"    {n:<12s} {v:>6.1f}")
    OUT_JSON.write_text(json.dumps({"per_quarter": results, "summary": summary,
                                    "policies": {k: list(v) for k, v in POLICIES.items()}},
                                   indent=2, default=float))
    print(f"\n  → {OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=800)
    ap.add_argument("--dynamic-momentum", action="store_true")
    ap.add_argument("--account", default="KROGER")
    ap.add_argument("--channel", default="CONVENTIONAL|FOOD")
    a = ap.parse_args()
    DYNAMIC_MOMENTUM = a.dynamic_momentum
    globals()["DYNAMIC_MOMENTUM"] = DYNAMIC_MOMENTUM
    print(f"  DYNAMIC_MOMENTUM = {DYNAMIC_MOMENTUM}\n")
    main(a.trees, a.account, a.channel)
