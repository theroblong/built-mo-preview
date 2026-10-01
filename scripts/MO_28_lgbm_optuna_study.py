"""MO_28 — Optuna hyperparameter search for LightGBM quantile models.

Uses 3-fold walk-forward time-series cross-validation to find optimal
LightGBM hyperparameters for the retailer sales forecast.

Objective: minimize mean q50 pinball loss (log-space) across 3 CV folds.
Each fold = 13-week validation window (mirrors production forecast horizon).

Outputs
-------
  outputs/lgbm_best_params.json      — best params for MO_26 v9 to consume
  outputs/lgbm_optuna_study.pkl      — full Optuna study for later analysis

Usage
-----
  python MO_28_lgbm_optuna_study.py [--trials 75] [--jobs 1]

After completion, update LGBM_BASE in MO_26 with the best params and bump
MODEL_VERSION to v9.
"""

import argparse
import json
import pickle
import warnings
import numpy as np
import pandas as pd
import lightgbm as lgb
import optuna
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)
optuna.logging.set_verbosity(optuna.logging.WARNING)

# ── Constants ────────────────────────────────────────────────────────────────

N_FOLDS          = 3          # walk-forward folds; each = 13-week val window
VAL_WEEKS        = 13         # mirrors production forecast horizon
EARLY_STOP       = 100        # more patience than current 50 — lets lr settle
N_ESTIMATORS_MAX = 2000       # hard cap; 5000 allowed ultra-low-lr trials to run 2+ hrs
RECENCY_LAMBDA   = 0.02       # fixed — same as MO_26; tune separately if needed
TARGET_QUANTILE  = 0.50       # optimize median; apply best params to q10/q90 too
RANDOM_STATE     = 42

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]

FEATURE_COLS = [
    "base_units_roll4_avg",
    "base_units_roll8_avg",  "base_units_roll8_std",
    "base_units_roll13_avg", "base_units_roll13_std",
    "base_units_wow_delta", "base_units_z8", "base_units_z13",
    "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
    "velocity_spm_z8", "velocity_spm_z13",
    "tdp", "tdp_z8", "tdp_wow_delta", "tdp_4w_momentum",
    "arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std",
    "arp_lag1", "arp_dollar_discount",
    "weeks_since_launch",
    "donor_count", "top_donor_tdp_sum", "competitor_price_gap",
    "promo_lift_ratio",
    "promo_lift_median", "promo_lift_p90", "promo_lift_n_events", "promo_lift_std",
    "is_promo_week", "promo_intensity",
    "units_lift_tpr", "units_lift_any_display", "units_lift_any_feature",
    "promo_52w_lag", "promo_rate_woy",
    "week_sin", "week_cos", "week_sin26", "week_cos26",
    "base_units_lag1", "base_units_lag4", "base_units_lag13",
    "base_units_lag52", "velocity_spm_lag52",
    "tdp_lag52", "velocity_per_tdp",
    "base_units_13wk_momentum", "base_units_4wk_momentum",
    "channel_outlet", "retail_account", "pack_count",
    "spins_flavor_canonical", "source_brand",
    # NOT added: spins_flavor_raw (un-normalised, duplicate levels) — superseded by
    #            spins_flavor_canonical, which now carries 35 corrected families.
    # NOT added: specific_flavor_normalized (76 levels) — ablation candidate.
    # NOT added: nfp_protein_range (constant — 95.3% "15 TO < 20G PROTEIN")
    # v9: geography_raw deliberately NOT a feature. Once zero-volume geographies are
    # filtered it is 1:1 with retail_account x channel_outlet for 99.1% of rows.
]

# CAT_COLS + the zero-volume filter come from mo_panel so the tuning panel is
# IDENTICAL to the one MO_26 trains on. The first v9 attempt (killed at trial 25/60)
# tuned on the unfiltered panel, where 14.1% of rows were zero-volume phantom
# geographies — and since the target is log1p(base_units), that was a 14% point mass
# at exactly 0. Those rows are perfectly separable by geography, so capacity spent
# isolating them paid off in the loss and biased the search toward higher num_leaves
# and lower min_child_samples than the clean problem needs.
# Rule: tune on the panel you will train on.
from mo_panel import (CAT_COLS, drop_zero_volume_geographies,  # noqa: E402
                      apply_rma_priority, fill_promo_mechanic_nulls,
                      drop_military_accounts)


# ── Data prep ─────────────────────────────────────────────────────────────────

def load_and_prepare() -> pd.DataFrame:
    parquet_path = Path("outputs/retailer_sales_weekly.parquet")
    print(f"Loading {parquet_path} …")
    df = pd.read_parquet(parquet_path)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    # Semi-annual seasonality
    if "week_of_year" in df.columns:
        woy = pd.to_numeric(df["week_of_year"], errors="coerce").fillna(1)
        df["week_sin26"] = np.sin(2 * np.pi * woy / 26)
        df["week_cos26"] = np.cos(2 * np.pi * woy / 26)

    # Numeric coercion
    num_cols = [c for c in FEATURE_COLS if c not in CAT_COLS]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Categoricals
    if "spins_flavor_canonical" in df.columns:
        df["spins_flavor_canonical"] = df["spins_flavor_canonical"].fillna("UNKNOWN").astype(str)
    if "source_brand" in df.columns:
        # "UNKNOWN" not "BUILT BAR" — matches MO_26; filling with a real brand
        # asserts a fact the data does not support.
        df["source_brand"] = df["source_brand"].fillna("UNKNOWN").astype(str)
    for _c in ("geography_raw", "spins_flavor_raw", "nfp_protein_range"):
        if _c in df.columns:
            df[_c] = (df[_c].fillna("UNKNOWN").astype(str).str.strip()
                            .replace("", "UNKNOWN"))
    for cat_col in CAT_COLS:
        if cat_col in df.columns:
            df[cat_col] = df[cat_col].astype("category")

    df = df.dropna(subset=["base_units"]).copy()

    # v9: must match MO_26 exactly — see the CAT_COLS import comment above.
    print("\n  ── Panel rules (v9) — MUST match MO_26 exactly ──")
    df = fill_promo_mechanic_nulls(df)
    df = drop_military_accounts(df)
    df = drop_zero_volume_geographies(df, target="base_units")
    df = apply_rma_priority(df)
    for cat_col in CAT_COLS:
        if cat_col in df.columns and isinstance(df[cat_col].dtype, pd.CategoricalDtype):
            df[cat_col] = df[cat_col].cat.remove_unused_categories()

    df["log_base_units"] = np.log1p(df["base_units"])

    print(f"  Rows: {len(df):,} | Series: {df.groupby(GROUP_COLS).ngroups:,}")
    _zero = (df["base_units"] == 0).mean() * 100
    print(f"  Remaining zero-target rows: {_zero:.1f}% "
          f"(real out-of-stock / pre-launch weeks, not phantom markets)")
    return df


def make_folds(df: pd.DataFrame, n_folds: int, val_weeks: int):
    """Walk-forward CV: newest fold last; each val = val_weeks wide."""
    t_max = df["__time"].max()
    folds = []
    for i in range(n_folds, 0, -1):
        val_end   = t_max - pd.Timedelta(weeks=(i - 1) * val_weeks)
        val_start = val_end - pd.Timedelta(weeks=val_weeks)
        train_mask = df["__time"] <= val_start
        val_mask   = (df["__time"] > val_start) & (df["__time"] <= val_end)
        if train_mask.sum() < 100 or val_mask.sum() < 10:
            continue
        folds.append((train_mask, val_mask))
    return folds


def recency_weights(df_train: pd.DataFrame) -> np.ndarray:
    t_max = df_train["__time"].max()
    weeks_ago = (t_max - df_train["__time"]).dt.total_seconds() / (7 * 24 * 3600)
    return np.exp(-RECENCY_LAMBDA * weeks_ago.clip(lower=0).values)


# ── Optuna objective ──────────────────────────────────────────────────────────

def make_objective(df: pd.DataFrame, folds, available: list):

    def objective(trial: optuna.Trial) -> float:
        params = dict(
            boosting_type    = "gbdt",
            objective        = "quantile",
            alpha            = TARGET_QUANTILE,
            n_estimators     = N_ESTIMATORS_MAX,
            learning_rate    = trial.suggest_float("learning_rate",    0.01,  0.08, log=True),
            num_leaves       = trial.suggest_int(  "num_leaves",       31,    191),
            min_child_samples= trial.suggest_int(  "min_child_samples",10,    80),
            feature_fraction = trial.suggest_float("feature_fraction", 0.5,   1.0),
            bagging_fraction = trial.suggest_float("bagging_fraction", 0.5,   1.0),
            bagging_freq     = 5,
            reg_alpha        = trial.suggest_float("reg_alpha",        0.0,   2.0),
            reg_lambda       = trial.suggest_float("reg_lambda",       0.0,   2.0),
            # ── v9: categorical regularisation ───────────────────────────────
            # Previously untuned, which was fine at 5 categoricals topping out at
            # 132 levels. v9 adds spins_flavor_raw (43 levels), and retail_account
            # is the #1 feature by gain, so the split search over category subsets
            # is where overfitting will show up first. These four knobs control it:
            #   min_data_per_group — rows a category needs before it can be split out
            #   cat_smooth         — shrinks thin categories toward the global mean
            #   cat_l2             — L2 penalty on categorical split gain
            #   max_cat_threshold  — caps levels on one side of a split
            min_data_per_group= trial.suggest_int(  "min_data_per_group", 20,  300, log=True),
            cat_smooth        = trial.suggest_float("cat_smooth",         1.0, 200.0, log=True),
            cat_l2            = trial.suggest_float("cat_l2",             1.0, 50.0,  log=True),
            max_cat_threshold = trial.suggest_int(  "max_cat_threshold",  8,   64),
            random_state     = RANDOM_STATE,
            n_jobs           = -1,
            verbose          = -1,
        )

        fold_scores = []
        for train_mask, val_mask in folds:
            train_df = df[train_mask]
            val_df   = df[val_mask]

            X_tr = train_df[available]
            y_tr = train_df["log_base_units"].values
            X_vl = val_df[available]
            y_vl = val_df["log_base_units"].values

            sw = recency_weights(train_df)

            model = lgb.LGBMRegressor(**params)
            model.fit(
                X_tr, y_tr,
                sample_weight=sw,
                eval_set=[(X_vl, y_vl)],
                callbacks=[
                    lgb.early_stopping(EARLY_STOP, verbose=False),
                    lgb.log_evaluation(-1),
                ],
            )
            preds   = model.predict(X_vl)
            err     = y_vl - preds
            pinball = float(np.mean(np.where(
                err >= 0, TARGET_QUANTILE * err, (TARGET_QUANTILE - 1) * err
            )))
            fold_scores.append(pinball)

            # Prune unpromising trials early (after first fold)
            trial.report(np.mean(fold_scores), step=len(fold_scores))
            if trial.should_prune():
                raise optuna.TrialPruned()

        return float(np.mean(fold_scores))

    return objective


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=75,
                        help="Number of Optuna trials (default 75)")
    parser.add_argument("--jobs", type=int, default=1,
                        help="Parallel jobs for Optuna (default 1; set >1 carefully with LightGBM n_jobs=-1)")
    args = parser.parse_args()

    df = load_and_prepare()

    available = [c for c in FEATURE_COLS if c in df.columns]
    missing   = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"  WARNING — features not in parquet (skipped): {missing}")

    folds = make_folds(df, N_FOLDS, VAL_WEEKS)
    print(f"\n  Walk-forward folds: {len(folds)}")
    for i, (tr_mask, vl_mask) in enumerate(folds, 1):
        tr_df = df[tr_mask]; vl_df = df[vl_mask]
        print(f"    Fold {i}: train {tr_df['__time'].min().date()} – {tr_df['__time'].max().date()} "
              f"({len(tr_df):,} rows) | val {vl_df['__time'].min().date()} – {vl_df['__time'].max().date()} "
              f"({len(vl_df):,} rows)")

    print(f"\nStarting Optuna study — {args.trials} trials, {len(folds)} folds each …\n")

    sampler = optuna.samplers.TPESampler(seed=RANDOM_STATE)
    pruner  = optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=1)
    # Persistent storage. The first v9 attempt ran in-memory, so when it had to be
    # killed at trial 25/60 its best params were unrecoverable — they are only
    # written to JSON at completion. SQLite makes a multi-hour study resumable and
    # inspectable mid-run (`optuna.load_study(...).trials_dataframe()`).
    _study_name = f"lgbm_quantile_q50_v9_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
    _storage    = "sqlite:///outputs/mo28_optuna_study.db"
    study   = optuna.create_study(
        direction="minimize",
        sampler=sampler,
        pruner=pruner,
        study_name=_study_name,
        storage=_storage,
        load_if_exists=True,
    )
    print(f"  Study:   {_study_name}")
    print(f"  Storage: {_storage}  (resumable)")

    objective = make_objective(df, folds, available)
    study.optimize(
        objective,
        n_trials=args.trials,
        n_jobs=args.jobs,
        show_progress_bar=True,
    )

    best  = study.best_trial
    print(f"\n{'='*60}")
    print(f"Best trial #{best.number}  |  Pinball (log, q50, mean 3 folds): {best.value:.4f}")
    print(f"Best params:")
    for k, v in best.params.items():
        print(f"  {k:25s} = {v}")

    # Suggested LGBM_BASE for MO_26 v9
    best_params_full = {
        "boosting_type":     "gbdt",
        "n_estimators":      N_ESTIMATORS_MAX,    # cap; early stopping governs
        "early_stop_rounds": EARLY_STOP,
        **best.params,
        "bagging_freq":      5,
        "random_state":      RANDOM_STATE,
        "n_jobs":            -1,
        "verbose":           -1,
    }

    # Current v8 baseline for comparison
    v8_baseline = {
        "learning_rate": 0.04, "num_leaves": 63, "min_child_samples": 20,
        "feature_fraction": 0.8, "bagging_fraction": 0.8,
        "reg_alpha": 0.1, "reg_lambda": 0.2,
    }

    out = {
        "study_name":      study.study_name,
        "completed_at":    datetime.now(timezone.utc).isoformat(),
        "n_trials":        len(study.trials),
        "n_folds":         N_FOLDS,
        "val_weeks":       VAL_WEEKS,
        "target_quantile": TARGET_QUANTILE,
        "early_stop_rounds": EARLY_STOP,
        "n_estimators_max":  N_ESTIMATORS_MAX,
        "recency_lambda":    RECENCY_LAMBDA,
        "best_value":      best.value,
        "best_params":     best.params,
        "lgbm_base_v9":    best_params_full,
        "v8_baseline":     v8_baseline,
    }

    params_path = Path("outputs/lgbm_best_params.json")
    with open(params_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Best params → {params_path}")

    study_path = Path("outputs/lgbm_optuna_study.pkl")
    with open(study_path, "wb") as f:
        pickle.dump(study, f)
    print(f"  Full study  → {study_path}")

    print(f"\nTop 10 trials by pinball loss:")
    completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    for t in sorted(completed, key=lambda x: x.value)[:10]:
        print(f"  Trial {t.number:3d}  pinball={t.value:.4f}  "
              f"lr={t.params.get('learning_rate', '?'):.4f}  "
              f"leaves={t.params.get('num_leaves', '?')}")

    print(f"\nNext step: update LGBM_BASE in MO_26 with lgbm_base_v9 params and bump to MODEL_VERSION='v9'.")
    print(f"MO_28 COMPLETE")
