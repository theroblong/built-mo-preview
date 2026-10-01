"""MO_26 — Train LightGBM quantile models for retailer sales forecasting.

Reads outputs/retailer_sales_weekly.parquet (from MO_25).
Trains three quantile regressors (q10, q50, q90) using LightGBM.
Saves model PKLs and a metrics JSON to outputs/.

FEATURE DESIGN
--------------
Three groups:
  1. Backward-looking rolling stats — pre-computed in event_detection_weekly;
     no leakage risk (all shift(1)-based in Druid).
  2. ARP trend features — computed in MO_25 from built_filtered_weekly; captures
     price moves 1–8 weeks ahead of their demand impact.
  3. Autoregressive lags — lag1/4/13 of base_units; seeded with actuals at train
     time, fed from q50 predictions at forecast time (MO_27).
  4. External signals — elasticity, cannibal pressure, lifecycle stage.
  5. Seasonal — week_of_year.
  6. Categorical — channel_outlet (LightGBM native category support).

TRAIN / VAL SPLIT
-----------------
Last 13 weeks of each series = validation set (mirrors the forecast horizon).
Earlier data = training. This is a temporal holdout — no future data leaks into
training for any series.

OUTPUT
------
  outputs/model_retailer_sales_q{10,50,90}_v8.pkl
  outputs/model_total_units_q{10,50,90}_v8.pkl  (trained on correct SPINS units target)
  outputs/retailer_sales_train_metrics.json
"""

import json
import pickle
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb
from datetime import datetime, timezone
from pathlib import Path

# Opt-out for the declared-feature guard below. Training on fewer features than
# FEATURE_COLS declares should be a deliberate choice, never a silent default.
ALLOW_MISSING_FEATURES = "--allow-missing-features" in sys.argv

MODEL_VERSION = "v9"
                      # v9: DATA + FEATURE run — final panel, corrected features, v8 hyperparameters.
                      #     Deliberately keeps v8's LGBM_BASE so that v8->v9 measures the data and
                      #     feature work alone, and v9->v10 measures the Optuna retune alone. One
                      #     combined jump could not be attributed between the two.
                      #     Panel (mo_panel.py, applied at consumption): promo-mechanic null fill,
                      #     military exclusion, zero-volume geographies, RMA priority.
                      #     186,427 -> 96,153 rows | 1,716 series | 120 UPCs | 61.1M units.
                      #     Features: spins_flavor_canonical now carries 35 override-corrected SPINS
                      #     families instead of 2 — MO_25 was filtering source_brand='BUILT' against
                      #     built_enriched_weekly, which matched 2 UPCs; parent_brand='BUILT' matches
                      #     146. source_brand nulls fill "UNKNOWN" not "BUILT BAR" (2,750 rows).
                      #     geography_raw deliberately NOT a feature (1:1 with retail_account x
                      #     channel_outlet for 99.1% of rows once phantoms are filtered);
                      #     nfp_protein_range is constant for BUILT, so extracted but not modelled.
                      # v10 (next): v9 panel + Optuna params from outputs/lgbm_best_params.json.
                      #     THREE edits, not one — LGBM_BASE, RECENCY_LAMBDA (a separate constant;
                      #     it drives the sample weights, not LightGBM), and MODEL_VERSION.
                      #     Check hit_n_estimators_cap first. See MO_28's docstring.
                      # (A discarded intermediate labelled v9a sits in outputs/ — trained before the
                      #  RMA/military/promo-null rules and on spins_flavor_raw. Not comparable.)
                      # v8: is_promo_week + promo_intensity + units_lift_tpr/display/feature +
                      #     promo_52w_lag + promo_rate_woy + spins_flavor_canonical (from MO_25 v11) +
                      #     drop is_bogo_week (0.06% gain, redundant w/ arp_dollar_discount) +
                      #     n_estimators 3000→4000 (v7 q50 still climbing at cap 2999/3000)
                      # v7: is_bogo_week + promo_lift_median/p90/n_events/std (from MO_25 v10) +
                      #     n_estimators 2000→3000 (v6 still climbing at cap)
                      # v6: pack_count + retail_account + tdp_4w_momentum + top_donor_tdp_sum +
                      #     competitor_price_gap + promo_lift_ratio + arp_dollar_discount +
                      #     arp_lag1 + week_sin/cos annual + week_sin26/cos26 semi-annual +
                      #     n_estimators 1500→2000 + full-data final retrain
QUANTILES     = [0.10, 0.50, 0.90]
Q_TAGS        = ["q10", "q50", "q90"]

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]

# CAT_COLS + the zero-volume filter live in mo_panel so training, forecasting and
# backtesting cannot drift apart again (four divergent copies shipped a silent v8 bug).
from mo_panel import (CAT_COLS, drop_zero_volume_geographies,  # noqa: E402
                      apply_rma_priority, fill_promo_mechanic_nulls,
                      drop_military_accounts, drop_short_series)

FEATURE_COLS = [
    # Rolling demand stats (backward-looking, no leakage)
    "base_units_roll4_avg",
    "base_units_roll8_avg",  "base_units_roll8_std",
    "base_units_roll13_avg", "base_units_roll13_std",
    # Momentum
    "base_units_wow_delta", "base_units_z8", "base_units_z13",
    # Velocity
    "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
    "velocity_spm_z8", "velocity_spm_z13",
    # Distribution — level, rate, and acceleration
    "tdp", "tdp_z8", "tdp_wow_delta",
    "tdp_4w_momentum",            # v6: distribution acceleration (monthly trend direction)
    # Price — level, trend, discount depth, stickiness
    "arp", "arp_wow_delta", "arp_roll8_avg", "arp_roll8_std",
    "arp_lag1",                   # v6: price stickiness; AR loop updates dynamically
    "arp_dollar_discount",        # v6: absolute $ discount vs 8w baseline (catalog-preferred)
    # Lifecycle
    "weeks_since_launch",
    # Competitive signals
    "donor_count",
    "top_donor_tdp_sum",          # v6: TDP weight of top-3 competitive donors
    "competitor_price_gap",       # v6: focal ARP minus competitor TDP-weighted ARP
    # Promo character — event-level and distributional
    "promo_lift_ratio",           # v6: incr/base lift ratio this week (AR dynamic — 0 in base forecast)
    # v8: dropped is_bogo_week (0.06% gain; arp_dollar_discount already encodes BOGO price signal)
    "promo_lift_median",          # v7: typical lift for this SKU×account (static distributional)
    "promo_lift_p90",             # v7: extreme event lift (static; identifies BOGO-class series)
    "promo_lift_n_events",        # v7: how frequently this SKU is promoted (static)
    "promo_lift_std",             # v7: variance of promo response (static; widens PI for volatile SKUs)
    # v8: promo activity + mechanic signals (AR dynamic — set to 0 in base forward forecast)
    "is_promo_week",              # v8: any promo activity at stores this week (binary)
    "promo_intensity",            # v8: fraction of units at promo stores (0–1)
    "units_lift_tpr",             # v8: % lift from Temporary Price Reduction
    "units_lift_any_display",     # v8: % lift from display / placement
    "units_lift_any_feature",     # v8: % lift from feature ad / circular
    # v8: forward promo prediction signals (leakage-free from historical cadence)
    "promo_52w_lag",              # v8: was promo same calendar week last year? (binary)
    "promo_rate_woy",             # v8: historical promo frequency at this WoY per series
    # Seasonality — cyclical encoding (sin+cos pair encodes position AND slope of cycle)
    # Annual cycle (52-week): encodes where in the year and whether demand is rising/falling
    "week_sin", "week_cos",
    # Semi-annual cycle (26-week): captures mid-year fitness / back-to-school patterns
    "week_sin26", "week_cos26",   # v6: derived from week_of_year in __main__ below
    # Autoregressive lags (seeded with actuals at train time; fed from q50 predictions in MO_27)
    "base_units_lag1", "base_units_lag4", "base_units_lag13",
    # YAGO — year-ago lags
    "base_units_lag52", "velocity_spm_lag52",
    # v5 growth-aware features (MO_77)
    "tdp_lag52",
    "velocity_per_tdp",
    "base_units_13wk_momentum",
    "base_units_4wk_momentum",
    # Categorical — LightGBM native category encoding
    "channel_outlet",
    "retail_account",             # v6: Kroger / Albertsons / Publix / UNFI / etc.
    "pack_count",                 # v6: pack ladder (1 / 4 / 8 / 12 / 18)
    "spins_flavor_canonical",     # v8: canonical flavor group (override+family normalization)
    "source_brand",               # v12: authoritative SPINS sub-brand (BUILT BAR / PUFF / SOUR PUFF)
    # spins_flavor_canonical (already listed above) now carries 35 override-corrected SPINS
    # families instead of 2. Root cause of the old 2-value version: MO_25's enrichment join
    # filtered `source_brand = 'BUILT'`, but that column holds the SUB-brand (BUILT PUFF /
    # BUILT BAR / BUILT SOUR PUFF) and only 2 UPCs carry the bare 'BUILT'. Fixed to
    # `parent_brand = 'BUILT'` -> 146 UPCs. So from v9b the model finally has real flavour
    # resolution; v8 and v9a effectively had none.
    # NOT added (ablation candidate): specific_flavor_normalized — 76 typo-corrected specific
    # flavours. It is the right field for comparing pack sizes WITHIN one true flavour
    # (family BROWNIE lumps Brownie Batter with Candy Cane Brownie), but at 76 levels over
    # ~2,740 series it averages ~36 series/level, so it must earn its slot by ablation
    # rather than assumption. It is in the panel either way for the pack-mix analysis.
    # NOT added: spins_flavor_raw — un-normalised family with duplicate levels
    # (COOKIES & CREAM vs COOKIES AND CREAM; CHOCOLATE & MINT vs CHOCOLATE MINT vs
    # MINT CHOCOLATE CHIP). Superseded by spins_flavor_canonical.
    # NOT added: nfp_protein_range. Extracted by MO_25 (it belongs in the panel), but it is a
    # CONSTANT — 95.3% of rows are "15 TO < 20G PROTEIN" and the remainder are null/empty.
    # Every BUILT SKU sits in the same protein band, so it is a brand-level constant rather
    # than a product differentiator and carries zero split information.
    # NOTE for a future ablation: spins_flavor_canonical is now strictly redundant given
    # spins_flavor_raw (raw subsumes both of canonical's real levels). Kept for v8
    # comparability; a candidate for removal once v9 is measured.
    # NOT added: geography_raw. It looked like the obvious v9 win (README update 190,
    # and retail_account is the #1 feature by gain) but measurement says otherwise.
    # geography_level is a deterministic function of channel_outlet, and once the 20
    # zero-volume geographies are filtered, geography_raw is 1:1 with
    # retail_account x channel_outlet for 99.1% of rows — one remaining multi-variant
    # combo (Circle K, 1,392 rows). The apparent signal was entirely the phantom AK/HI
    # markets, which drop_zero_volume_geographies() now removes. Adding it would buy
    # 154 levels of redundancy and the overfitting that comes with them. It stays a
    # GROUP_COL (series key) and stays in CAT_COLS so it is never coerced to numeric.
    # Removed by ablation: implied_elasticity, elasticity_band, max_donor_cannibal_prob,
    # cannibal_rate, price_elasticity_effect (MO_50–MO_56)
    # Catalog audit-only: built_tdp_share, arp_discount_pct
]

# Total-units model swaps base_units AR lags for total_units lags; same demand-driver features
TOTAL_UNIT_FEATURE_COLS = [
    c for c in FEATURE_COLS
    if not c.startswith("base_units_lag")
] + ["total_units_lag1", "total_units_lag4", "total_units_lag13", "total_units_lag52"]

LGBM_BASE = dict(
    boosting_type="gbdt",
    n_estimators=4000,
    learning_rate=0.04,
    num_leaves=63,
    min_child_samples=20,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=5,
    reg_alpha=0.1,
    reg_lambda=0.2,
    random_state=42,
    n_jobs=-1,
    verbose=-1,
)


def pinball(y_true: np.ndarray, y_pred: np.ndarray, q: float) -> float:
    err = y_true - y_pred
    return float(np.mean(np.where(err >= 0, q * err, (q - 1) * err)))


if __name__ == "__main__":
    parquet_path = Path("outputs/retailer_sales_weekly.parquet")
    print(f"Loading {parquet_path} …")
    df = pd.read_parquet(parquet_path)
    print(f"  Rows: {len(df):,} | UPCs: {df['upc'].nunique()} "
          f"| Series: {df.groupby(GROUP_COLS).ngroups:,}")

    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    # ── Derive semi-annual cyclical seasonality ──────────────────────────────
    # week_sin/cos (annual, 52-week) already in parquet from MO_25.
    # week_sin26/cos26 (semi-annual, 26-week) encode mid-year patterns.
    if "week_of_year" in df.columns:
        woy = pd.to_numeric(df["week_of_year"], errors="coerce").fillna(1)
        df["week_sin26"] = np.sin(2 * np.pi * woy / 26)
        df["week_cos26"] = np.cos(2 * np.pi * woy / 26)

    # ── Numeric coercion ────────────────────────────────────────────────────
    # CAT_COLS is module-level — do NOT shadow it with a local copy. MO_27 carried
    # three divergent copies of this set and v8 updated only two of them, which
    # silently nulled source_brand + spins_flavor_canonical at inference.
    num_cols = [c for c in FEATURE_COLS if c not in CAT_COLS]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # ── Categorical encoding ─────────────────────────────────────────────────
    if "spins_flavor_canonical" in df.columns:
        df["spins_flavor_canonical"] = df["spins_flavor_canonical"].fillna("UNKNOWN").astype(str)
    if "source_brand" in df.columns:
        # "UNKNOWN", not "BUILT BAR": 2,750 rows (1.5%) have a null source_brand, and
        # filling them with a real brand asserts a fact the data does not support —
        # it teaches the model that unlabelled rows behave like BUILT BAR. A distinct
        # level lets the tree learn what unlabelled actually looks like.
        # (38 rows also carry the legacy value "BUILT" rather than a sub-brand.)
        df["source_brand"] = df["source_brand"].fillna("UNKNOWN").astype(str)
    # v9 categoricals: fill before the .astype("category") pass so NaN becomes an
    # explicit level instead of a missing value the tree routes by default.
    for _c in ("geography_raw", "spins_flavor_raw", "nfp_protein_range"):
        if _c in df.columns:
            df[_c] = (df[_c].fillna("UNKNOWN").astype(str).str.strip()
                            .replace("", "UNKNOWN"))
    for cat_col in CAT_COLS:
        if cat_col in df.columns:
            df[cat_col] = df[cat_col].astype("category")

    # ── Drop rows where target is null (can't train or evaluate on these) ──────
    before = len(df)
    df = df.dropna(subset=["base_units"]).copy()
    if len(df) < before:
        print(f"  Dropped {before - len(df):,} rows with null base_units")

    # ── v9: drop geographies with zero volume across their entire history ──────
    # Nulls were already handled above; zeros were NOT, so ~14% of training weight
    # sat on phantom AK/HI market definitions and no-distribution accounts.
    print("\n  ── Panel rules (v9) ──")
    # Order matters. Military accounts and phantom markets come out first so that by the
    # time RMA priority runs, every surviving retailer genuinely has an RMA feed and the
    # CRMA-fallback branch correctly never fires. Short RMA histories are NOT a reason to
    # fall back to CRMA: Target (66 wks), BJ's (57), Walgreens (86) and Giant Eagle (105)
    # were all verified as real launch ramps (Target 119 -> 2,165 -> 15,904 -> ... ->
    # 144,148 u/wk), i.e. correct distribution-expansion history, not feed gaps.
    df = fill_promo_mechanic_nulls(df)
    df = drop_military_accounts(df)
    df = drop_zero_volume_geographies(df, target="base_units")
    df = apply_rma_priority(df)
    # Was MO_25.MIN_WEEKS (extract-time). Moved here so BUILT's newest launches stay
    # in the parquet and remain reachable by MO_27/analysis, while still being kept out
    # of the LightGBM fit, where lag13/roll13/lag52 would all be NaN for them.
    df = drop_short_series(df)
    # Categorical dtypes retain dropped levels after a row filter; unused levels
    # would be carried into the model's category universe and inflate split search.
    for cat_col in CAT_COLS:
        if cat_col in df.columns and isinstance(df[cat_col].dtype, pd.CategoricalDtype):
            df[cat_col] = df[cat_col].cat.remove_unused_categories()

    # ── Log-transform target: log1p compresses heavy tail, forces positivity ───
    # Predictions are in log-space; MO_27 inverts with expm1 before output.
    p99 = df["base_units"].quantile(0.99)
    print(f"  p99 base_units: {p99:.0f}  (no clip needed — log transform handles scale)")
    df["log_base_units"] = np.log1p(df["base_units"])

    has_total = bool("total_units" in df.columns and df["total_units"].notna().any())
    if has_total:
        df["log_total_units"] = np.log1p(df["total_units"].clip(lower=0).fillna(0))

    # ── Temporal train / val split (last 13 weeks = val) ────────────────────
    cutoff = df["__time"].max() - pd.Timedelta(weeks=13)
    train  = df[df["__time"] <= cutoff].copy()
    val    = df[df["__time"] >  cutoff].copy()
    print(f"\n  Train: {len(train):,} rows | Val: {len(val):,} rows "
          f"(cutoff {cutoff.date()})")

    available = [c for c in FEATURE_COLS if c in df.columns]
    missing   = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"  WARNING — feature columns not found (will be skipped): {missing}")

    # Silently training on fewer features than FEATURE_COLS declares is how a
    # feature regression ships unnoticed: the v8 PKLs carry source_brand, but the
    # committed parquet does not, so a v9 run against a stale parquet would drop
    # brand and still report success. week_sin26/week_cos26 are derived in-script
    # above, so they are legitimately absent from the parquet and exempt here.
    _DERIVED_IN_SCRIPT = {"week_sin26", "week_cos26"}
    _unexpected = [c for c in missing if c not in _DERIVED_IN_SCRIPT]
    if _unexpected and not ALLOW_MISSING_FEATURES:
        raise SystemExit(
            f"\nFATAL: {len(_unexpected)} declared feature(s) absent from the parquet:\n"
            f"  {_unexpected}\n"
            f"  Re-run MO_25 to regenerate outputs/retailer_sales_weekly.parquet, or pass\n"
            f"  --allow-missing-features to train without them deliberately."
        )

    X_train = train[available]
    y_train = train["log_base_units"].values          # log-space target
    X_val   = val[available]
    y_val_log   = val["log_base_units"].values        # log-space for pinball
    y_val_units = val["base_units"].values            # original units for MAE/RMSE

    # Recency-weighted training: exponential decay λ=0.02 over weeks_ago.
    # Rationale: BUILT is a hyper-growth brand — recent data (last 26 weeks) better
    # represents current distribution trajectory and velocity patterns than data from
    # 2+ years ago when the brand had far fewer stores. Downweighting older rows lets
    # the model align to the current growth regime without discarding history entirely.
    # λ=0.02: row from 52wk ago → weight ≈ 0.35; row from 104wk ago → weight ≈ 0.12.
    # Explainability: "the model trusts recent performance more than old baselines."
    _cutoff_ts    = train["__time"].max()
    _weeks_ago    = (_cutoff_ts - train["__time"]).dt.total_seconds() / (7 * 24 * 3600)
    sample_weights = np.exp(-0.02 * _weeks_ago.clip(lower=0).values)
    print(f"  Recency weights: min={sample_weights.min():.3f}  "
          f"mean={sample_weights.mean():.3f}  max={sample_weights.max():.3f}")

    # ── Train base_units models (q10/q50/q90) ────────────────────────────────
    models  = {}
    metrics = {}

    for q, tag in zip(QUANTILES, Q_TAGS):
        print(f"\nTraining base_units quantile={q} ({tag}) …")
        model = lgb.LGBMRegressor(
            objective="quantile",
            alpha=q,
            **LGBM_BASE,
        )
        model.fit(
            X_train, y_train,
            sample_weight=sample_weights,
            eval_set=[(X_val, y_val_log)],
            callbacks=[
                lgb.early_stopping(50, verbose=False),
                lgb.log_evaluation(100),
            ],
        )
        preds_log   = model.predict(X_val)
        preds_units = np.expm1(np.clip(preds_log, 0, None))   # back to unit scale
        pb   = pinball(y_val_log, preds_log, q)                # pinball in log-space
        mae  = float(np.mean(np.abs(y_val_units - preds_units))) if q == 0.50 else None
        rmse = float(np.sqrt(np.mean((y_val_units - preds_units) ** 2))) if q == 0.50 else None
        print(f"  Best iter: {model.best_iteration_}  |  Pinball (log): {pb:.4f}"
              + (f"  |  MAE: {mae:.1f}  |  RMSE: {rmse:.1f}" if mae is not None else ""))

        models[tag] = model
        metrics[tag] = {
            "quantile": q,
            "best_iteration": int(model.best_iteration_),
            "val_pinball_loss": pb,
            **({"val_mae": mae, "val_rmse": rmse} if mae is not None else {}),
        }

    # ── Save base_units models ───────────────────────────────────────────────
    for tag, model in models.items():
        path = f"outputs/model_retailer_sales_{tag}_{MODEL_VERSION}.pkl"
        with open(path, "wb") as f:
            pickle.dump(model, f)
        print(f"  Saved {path}")

    # ── Feature importance (q50 model) ───────────────────────────────────────
    imp = pd.Series(
        models["q50"].feature_importances_,
        index=models["q50"].feature_name_,
    ).sort_values(ascending=False)
    print("\nTop 15 features — base_units q50:")
    print(imp.head(15).to_string())

    # ── Train total_units models (q10/q50/q90) ────────────────────────────────
    models_total  = {}
    metrics_total = {}

    if has_total:
        avail_total = [c for c in TOTAL_UNIT_FEATURE_COLS if c in df.columns]
        miss_total  = [c for c in TOTAL_UNIT_FEATURE_COLS if c not in df.columns]
        if miss_total:
            print(f"  WARNING — total_units features missing: {miss_total}")

        X_train_t = train[avail_total]
        y_train_t = train["log_total_units"].values
        X_val_t   = val[avail_total]
        y_val_log_t   = val["log_total_units"].values
        y_val_total   = val["total_units"].clip(lower=0).fillna(0).values

        for q, tag in zip(QUANTILES, Q_TAGS):
            print(f"\nTraining total_units quantile={q} ({tag}) …")
            model_t = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                **LGBM_BASE,
            )
            model_t.fit(
                X_train_t, y_train_t,
                eval_set=[(X_val_t, y_val_log_t)],
                callbacks=[
                    lgb.early_stopping(50, verbose=False),
                    lgb.log_evaluation(100),
                ],
            )
            preds_log_t   = model_t.predict(X_val_t)
            preds_total   = np.expm1(np.clip(preds_log_t, 0, None))
            pb_t  = pinball(y_val_log_t, preds_log_t, q)
            mae_t = float(np.mean(np.abs(y_val_total - preds_total))) if q == 0.50 else None
            rmse_t= float(np.sqrt(np.mean((y_val_total - preds_total) ** 2))) if q == 0.50 else None
            print(f"  Best iter: {model_t.best_iteration_}  |  Pinball (log): {pb_t:.4f}"
                  + (f"  |  MAE: {mae_t:.1f}  |  RMSE: {rmse_t:.1f}" if mae_t is not None else ""))

            models_total[tag] = model_t
            metrics_total[tag] = {
                "quantile": q,
                "best_iteration": int(model_t.best_iteration_),
                "val_pinball_loss": pb_t,
                **({"val_mae": mae_t, "val_rmse": rmse_t} if mae_t is not None else {}),
            }

        for tag, model_t in models_total.items():
            path = f"outputs/model_total_units_{tag}_{MODEL_VERSION}.pkl"
            with open(path, "wb") as f:
                pickle.dump(model_t, f)
            print(f"  Saved {path}")

        imp_t = pd.Series(
            models_total["q50"].feature_importances_,
            index=models_total["q50"].feature_name_,
        ).sort_values(ascending=False)
        print("\nTop 15 features — total_units q50:")
        print(imp_t.head(15).to_string())
    else:
        print("\n  Skipping total_units training (column not found in parquet).")
        avail_total = []
        miss_total  = []

    # ── Full-data final retrain ──────────────────────────────────────────────
    # Standard practice: val split found best_iteration_ via early stopping;
    # now retrain on ALL data with that fixed n_estimators for production deployment.
    # These "full" models are what MO_27 loads — more training data, same stopping point.
    X_full = df[available]
    y_full = df["log_base_units"].values
    _weeks_ago_full = (df["__time"].max() - df["__time"]).dt.total_seconds() / (7 * 24 * 3600)
    weights_full    = np.exp(-0.02 * _weeks_ago_full.clip(lower=0).values)

    models_full = {}
    for q, tag in zip(QUANTILES, Q_TAGS):
        best_n = models[tag].best_iteration_
        print(f"\nFull-data retrain base_units quantile={q} ({tag}), n_estimators={best_n} …")
        m_full = lgb.LGBMRegressor(
            objective="quantile",
            alpha=q,
            **{**LGBM_BASE, "n_estimators": best_n},
        )
        m_full.fit(X_full, y_full, sample_weight=weights_full)
        models_full[tag] = m_full
        path = f"outputs/model_retailer_sales_{tag}_{MODEL_VERSION}_full.pkl"
        with open(path, "wb") as f:
            pickle.dump(m_full, f)
        print(f"  Saved {path}")

    if has_total:
        X_full_t = df[avail_total]
        y_full_t = df["log_total_units"].values
        for q, tag in zip(QUANTILES, Q_TAGS):
            best_n_t = models_total[tag].best_iteration_
            print(f"\nFull-data retrain total_units quantile={q} ({tag}), n_estimators={best_n_t} …")
            m_full_t = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                **{**LGBM_BASE, "n_estimators": best_n_t},
            )
            m_full_t.fit(X_full_t, y_full_t)
            path = f"outputs/model_total_units_{tag}_{MODEL_VERSION}_full.pkl"
            with open(path, "wb") as f:
                pickle.dump(m_full_t, f)
            print(f"  Saved {path}")

    # ── Save metrics + feature list ──────────────────────────────────────────
    meta = {
        "model_version":    MODEL_VERSION,
        "trained_at":       datetime.now(timezone.utc).isoformat(),
        "features_used":    available,
        "features_missing": missing,
        "train_rows":       int(len(train)),
        "val_rows":         int(len(val)),
        "train_date_range": [str(train["__time"].min().date()), str(train["__time"].max().date())],
        "val_date_range":   [str(val["__time"].min().date()),   str(val["__time"].max().date())],
        "target_p99_clip":  float(p99 * 2),
        "quantile_metrics": metrics,
        "top_features_q50": imp.head(20).to_dict(),
        "total_units_trained":        has_total,
        "total_units_features_used":  avail_total,
        "total_units_features_missing": miss_total,
        "total_units_quantile_metrics": metrics_total,
    }
    # Write a version-stamped copy ALONGSIDE the legacy unversioned path.
    # The unversioned file is shared mutable state — whichever training run finishes
    # last owns it regardless of MODEL_VERSION. That is how v8 broke: a v7 archival
    # retrain clobbered v8's metadata, leaving MO_27 with a 48-feature features_used
    # pointed at 56-feature v8 models. MO_27 prefers the versioned file and asserts
    # model_version matches, so a future clobber cannot go unnoticed.
    meta_versioned = f"outputs/retailer_sales_train_metrics_{MODEL_VERSION}.json"
    meta_legacy    = "outputs/retailer_sales_train_metrics.json"
    for meta_path in (meta_versioned, meta_legacy):
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        print(f"\n  Metrics → {meta_path}")
