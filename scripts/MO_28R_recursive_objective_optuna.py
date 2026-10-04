"""MO_28R — Optuna tuned against the RECURSIVE 13-week forecast, not one-step pinball loss.

WHY THIS IS THE LEVER WE NEVER PULLED
-------------------------------------
Every Optuna run this project has done (MO_28) optimises **cross-validated one-step pinball
loss** — the error of predicting next week with ACTUAL lags supplied. Production does something
completely different: it predicts 13 weeks forward, feeding each prediction back in as `lag1`.

The same model, measured both ways:

      teacher-forced (what MO_28 optimises)    4.15%
      recursive (what production does)        37.12%

A 9x gap. So every hyperparameter we have ever chosen was selected to be good at a task we do not
perform. Worse, the one-step objective actively **rewards leaning on `lag1`**, because lag1 is far
and away the best one-step predictor — and that is precisely the behaviour that makes the 13-week
recursive forecast collapse to `last_actual x 1.03` by step 3.

**The tuning objective has been selecting for the failure mode.**

This script fixes that: each trial trains a model, runs the FULL recursive 13-week loop on a
holdout, and scores wMAPE the way production is actually judged. Hyperparameters that make a model
good at one-step-ahead but brittle under recursion are now penalised instead of rewarded.

Honest expectation: this may not close the whole gap. The recursive collapse is partly structural
(31 of 56 features are frozen across the horizon, so the loop has little exogenous signal to move
on) and no hyperparameter can unfreeze them. But it is the only untested lever that can make the
SINGLE recursive model better, which is the architecture we want to keep — one model, any horizon,
simple to serve.

Baseline to beat (MO_80, 7 true holdout quarters, Kroger CONVENTIONAL|FOOD):
      recursive (current params)   40.6
      direct multi-horizon         34.0
      naive (hold last flat)       32.9
      naiveYoY (Excel)             62.0

WHAT IS TUNED
  learning_rate, num_leaves, min_child_samples, feature_fraction, bagging_fraction,
  reg_alpha, reg_lambda, min_data_per_group, cat_smooth, cat_l2, and RECENCY_LAMBDA
  (sample weighting — it drives how hard the model leans on recent weeks, which is exactly the
  behaviour that governs recursive stability, so it must be tuned jointly, not fixed).

  n_estimators is NOT tuned. It is a compute budget with early stopping; MO_29 measured the
  curve as asymptotic, so a tuned value would just encode the cap.

Run:  python MO_28R_recursive_objective_optuna.py [--trials 60] [--cutoffs 13,26,39]
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
import optuna

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

from mo_panel import (CAT_COLS, GROUP_COLS, drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_ak_hi_market_variants, drop_short_series)

PARQUET   = Path("outputs/retailer_sales_weekly.parquet")
OUT_JSON  = Path("outputs/mo28r_recursive_optuna.json")
STORAGE   = "sqlite:///outputs/mo28r_study.db"
HORIZON   = 13
N_TREES   = 3000
EARLY_STOP = 80


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
    # Identical rule stack to MO_26 — tuning on a different panel than training is how
    # hyperparameters get applied to data they were never validated on.
    df = fill_promo_mechanic_nulls(df, verbose=False)
    df = drop_military_accounts(df, verbose=False)
    df = drop_ak_hi_market_variants(df, verbose=False)
    df = drop_zero_volume_geographies(df, target="base_units", verbose=False)
    df = apply_rma_priority(df, verbose=False)
    df = drop_short_series(df, verbose=False)
    for c in CAT_COLS:
        if c in df.columns:
            df[c] = df[c].astype("category")
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


def recursive_wmape_fast(model, df, feats, cats, cut, weeks):
    """Vectorized twin of recursive_wmape — identical math, one predict per STEP.

    The scalar version issues a single-row predict per series per step: ~2,000
    series x 13 steps = ~26,000 predict calls per fold, which dominates trial
    wall-clock and made a few-hundred-trial search cost >100 hours. Series are
    independent within a step, so all of them can be advanced together: 13
    predicts per fold instead of 26,000. Verified equal to the scalar version
    before use (see --verify).
    """
    fw = list(weeks[weeks > cut][:HORIZON])
    if not fw:
        return float("nan")
    hist_df = df[df["__time"] <= cut]
    fut = df[(df["__time"] > cut) & (df["__time"] <= fw[-1])]
    truth = fut.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum()
    if truth.empty:
        return float("nan")
    want = {(u, c, a, g) for (u, c, a, g, _t) in truth.index}
    tmap = {((u, c, a, g), t): v for (u, c, a, g, t), v in truth.items()}

    keys, states, hists = [], [], []
    for key, g in hist_df.groupby(GROUP_COLS, observed=True):
        if key not in want:
            continue
        g = g.sort_values("__time")
        if len(g) < 4:
            continue
        keys.append(key)
        states.append(g.iloc[-1])
        hists.append(list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0)))
    if not keys:
        return float("nan")

    S = pd.DataFrame(states).reset_index(drop=True)
    acts, preds = [], []
    for fd in fw:
        t2 = float(fd.isocalendar().week)
        S["week_sin"] = np.sin(2 * np.pi * t2 / 52)
        S["week_cos"] = np.cos(2 * np.pi * t2 / 52)
        S["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
        S["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
        S["base_units_lag1"] = [h[-1] for h in hists]
        S["base_units_roll4_avg"] = [float(np.mean(h[-4:])) for h in hists]
        S["base_units_roll8_avg"] = [float(np.mean(h[-8:])) for h in hists]
        S["base_units_roll13_avg"] = [float(np.mean(h[-13:])) for h in hists]
        S["base_units_wow_delta"] = [h[-1] - h[-2] if len(h) > 1 else 0.0 for h in hists]
        X = S[feats].copy()
        for c, cc in cats.items():
            if c in X.columns:
                X[c] = pd.Categorical(X[c], categories=cc)
        p = np.clip(np.expm1(model.predict(X)), 0, None)
        for i, key in enumerate(keys):
            hists[i].append(float(p[i]))
            k = (key, fd)
            if k in tmap:
                acts.append(tmap[k]); preds.append(float(p[i]))
    return wmape(acts, preds) if acts else float("nan")


def recursive_wmape(model, df, feats, cats, cut, weeks):
    """Run the production recursive loop and score it. THIS is the objective."""
    fw = list(weeks[weeks > cut][:HORIZON])
    if not fw:
        return float("nan")
    hist_df = df[df["__time"] <= cut]
    fut = df[(df["__time"] > cut) & (df["__time"] <= fw[-1])]
    truth = fut.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum()
    if truth.empty:
        return float("nan")
    want = {(u, c, a, g) for (u, c, a, g, _t) in truth.index}
    acts, preds = [], []
    tmap = {((u, c, a, g), t): v for (u, c, a, g, t), v in truth.items()}
    for key, g in hist_df.groupby(GROUP_COLS, observed=True):
        if key not in want:
            continue
        g = g.sort_values("__time")
        if len(g) < 4:
            continue
        state = g.iloc[-1].copy()
        hist = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
        for h, fd in enumerate(fw, 1):
            t2 = float(fd.isocalendar().week)
            state["week_sin"] = np.sin(2 * np.pi * t2 / 52)
            state["week_cos"] = np.cos(2 * np.pi * t2 / 52)
            state["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
            state["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
            # lag1 = the model's OWN previous prediction. This is the whole point.
            state["base_units_lag1"] = hist[-1]
            state["base_units_roll4_avg"] = float(np.mean(hist[-4:]))
            state["base_units_roll8_avg"] = float(np.mean(hist[-8:]))
            state["base_units_roll13_avg"] = float(np.mean(hist[-13:]))
            state["base_units_wow_delta"] = hist[-1] - hist[-2] if len(hist) > 1 else 0.0
            X = pd.DataFrame([state])[feats]
            for c, cc in cats.items():
                if c in X.columns:
                    X[c] = pd.Categorical(X[c], categories=cc)
            p = float(np.clip(np.expm1(model.predict(X))[0], 0, None))
            hist.append(p)
            k = (key, fd)
            if k in tmap:
                acts.append(tmap[k]); preds.append(p)
    return wmape(acts, preds) if acts else float("nan")


def main(trials, cutoffs_back, study_name, timeout=None, seed_from=None):
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    end = df["__time"].max()
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    cuts = [end - pd.Timedelta(weeks=w) for w in cutoffs_back]
    print(f"MO_28R — Optuna on the RECURSIVE objective (what production is actually judged on)")
    print(f"  panel {len(df):,} rows · {df.groupby(GROUP_COLS, observed=True).ngroups:,} series")
    print(f"  folds: {[str(c.date()) for c in cuts]} | {trials} trials")
    print(f"  baseline to beat (MO_80, 7 honest quarters): recursive 40.6 · direct 34.0 · naive 32.9\n")

    def objective(trial):
        p = dict(
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            num_leaves=trial.suggest_int("num_leaves", 15, 191),
            min_child_samples=trial.suggest_int("min_child_samples", 10, 200, log=True),
            feature_fraction=trial.suggest_float("feature_fraction", 0.5, 1.0),
            bagging_fraction=trial.suggest_float("bagging_fraction", 0.5, 1.0),
            bagging_freq=5,
            reg_alpha=trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
            reg_lambda=trial.suggest_float("reg_lambda", 1e-3, 100.0, log=True),
            min_data_per_group=trial.suggest_int("min_data_per_group", 20, 500),
            cat_smooth=trial.suggest_float("cat_smooth", 1.0, 400.0, log=True),
            cat_l2=trial.suggest_float("cat_l2", 1.0, 100.0, log=True),
            random_state=42, n_jobs=-1, verbose=-1)
        lam = trial.suggest_float("recency_lambda", 0.0, 0.15)
        scores = []
        for cut in cuts:
            tr = df[df["__time"] <= cut]
            if len(tr) < 1000:
                continue
            va = tr[tr["__time"] > cut - pd.Timedelta(weeks=HORIZON)]
            wk = ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0)
            sw = np.exp(-lam * wk)
            m = lgb.LGBMRegressor(objective="quantile", alpha=0.5,
                                  n_estimators=N_TREES, **p)
            m.fit(tr[feats], np.log1p(tr["base_units"]), sample_weight=sw,
                  eval_set=[(va[feats], np.log1p(va["base_units"]))], eval_metric="quantile",
                  callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False),
                             lgb.log_evaluation(-1)])
            s = recursive_wmape_fast(m, df, feats, cats, cut, weeks)
            if np.isfinite(s):
                scores.append(s)
            trial.report(float(np.mean(scores)) if scores else 1e9, len(scores))
            if trial.should_prune():
                raise optuna.TrialPruned()
        return float(np.mean(scores)) if scores else 1e9

    study = optuna.create_study(direction="minimize", study_name=study_name,
                                storage=STORAGE, load_if_exists=True,
                                sampler=optuna.samplers.TPESampler(seed=42),
                                pruner=optuna.pruners.MedianPruner(n_warmup_steps=1))

    def cb(st, tr):
        if tr.value is not None:
            print(f"  trial {tr.number:>3d}  recursive wMAPE {tr.value:>6.2f}   "
                  f"best {st.best_value:>6.2f}")

    if seed_from:
        src = optuna.load_study(study_name=seed_from, storage=STORAGE)
        done = [t for t in src.trials if t.state.name == "COMPLETE"]
        for t in done:
            study.enqueue_trial(t.params, skip_if_exists=True)
        print(f"  seeded {len(done)} parameter sets from '{seed_from}' "
              f"(re-scored on these folds, not imported as values)\n")
    folds_tag = ",".join(str(w) for w in cutoffs_back)
    prior = study.user_attrs.get("cutoffs_back")
    if prior is not None and prior != folds_tag:
        raise SystemExit(
            f"\nFATAL: study '{study_name}' was built on folds [{prior}] but this run asks for "
            f"[{folds_tag}].\n  Different folds = a different objective; resuming would mix two "
            f"scales in one study.\n  Use a new --study-name, or pass --cutoffs {prior}.")
    study.set_user_attr("cutoffs_back", folds_tag)
    study.set_user_attr("scorer", "recursive_wmape_fast")
    study.optimize(objective, n_trials=trials, callbacks=[cb], show_progress_bar=False,
                   timeout=timeout)

    best = dict(study.best_params)
    lam = best.pop("recency_lambda")
    out = {"study": study_name, "n_trials": len(study.trials),
           "best_recursive_wmape": float(study.best_value),
           "lgbm_base_v11r": {**best, "bagging_freq": 5, "random_state": 42,
                              "n_jobs": -1, "verbose": -1},
           "recency_lambda_tuned": float(lam),
           "folds": [str(c.date()) for c in cuts],
           "panel_rows": int(len(df)),
           "baseline_mo80": {"recursive": 40.6, "direct": 34.0, "naive": 32.9,
                             "naive_yoy": 62.0},
           "note": ("Objective is the FULL recursive 13-week loop, matching production. "
                    "Not comparable to MO_28's one-step pinball values. recency_lambda is "
                    "returned SEPARATELY because it drives sample weights, not LightGBM — "
                    "applying lgbm_base and forgetting it silently discards a tuned dimension.")}
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\n  BEST recursive wMAPE: {study.best_value:.2f}  "
          f"(incumbent 40.6 · direct 34.0 · naive 32.9)")
    print(f"  recency_lambda_tuned: {lam:.4f}")
    print(f"  → {OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=60)
    ap.add_argument("--cutoffs", type=str, default="13,26,39")
    ap.add_argument("--study-name", default="mo28r_recursive_v1")
    ap.add_argument("--timeout", type=float, default=None, help="wall-clock seconds")
    ap.add_argument("--seed-from", default=None, help="study whose params to enqueue first")
    a = ap.parse_args()
    main(a.trials, [int(x) for x in a.cutoffs.split(",")], a.study_name, a.timeout, a.seed_from)
