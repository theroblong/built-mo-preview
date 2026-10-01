"""MO_27 — Generate 13-week rolling retailer sales forecast.

Reads outputs/retailer_sales_weekly.parquet (MO_25) and model PKLs (MO_26).
Produces 13 forward weekly rows per (upc, retailer, channel, geo) series.

FORECAST METHOD
---------------
Autoregressive rolling forecast: same pattern as MO_21 (cannibal rate).
  • Seed each series from its last 13 actual weeks (enough for lag13).
  • At each step, build a feature row from static series attributes +
    autoregressive lags (lag1 comes from the PREVIOUS step's q50 prediction).
  • Clamp all forecasts to 0 (unit sales can't go negative).

DOLLAR CONVERSION
-----------------
Each forecast row carries `forecast_dollars_*` = forecast_units * arp.
ARP used is the last observed weekly arp for the series. If arp_fallback=1
for that series, the period-average post_13w_arp was used — noted in output.

OUTPUT TABLE: retailer_sales_forecast (Druid)
---------------------------------------------
__time                  ISO  — forecast week timestamp
upc                     str
description             str
channel_outlet          str
retail_account          str
geography_raw           str
geography_display       str
geography_level         str
anchor_date             str  — last actual week date (ISO)
anchor_base_units       float — last actual week's base_units
anchor_arp              float — last observed ARP
forecast_week_number    int  — 1 through 13
forecast_units_low      float — q10 (base units, promo-stripped)
forecast_units_base     float — q50
forecast_units_high     float — q90
forecast_dollars_low    float — q10 × arp
forecast_dollars_base   float — q50 × arp
forecast_dollars_high   float — q90 × arp
forecast_total_units_low  float — q10 total scan volume (base + promo); null if total_units model not trained
forecast_total_units_base float — q50 total
forecast_total_units_high float — q90 total
weeks_since_launch      int  — at the forecast week (increments per step)
arp_fallback            int  — 1 if ARP came from post_13w_arp fallback
model_version           str
scored_at               str  ISO
"""

import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from mo_writeback import write_back

MODEL_VERSION  = "v9"   # must match the MO_26 run whose PKLs + metrics this loads;
                        # the guard in _load_models_and_meta() hard-fails on a mismatch
FORECAST_WEEKS = 13
Q_TAGS         = ["q10", "q50", "q90"]

# Seasonal blend weight: fraction of each forecast step pulled toward the
# year-ago seasonal reference (lag52 × current-YoY-ratio).  Without this,
# autoregressive convergence causes the 13-week forward forecast to collapse
# to a flat mean after ~4 steps — the AR lags become self-predictions and
# drown out the weekly seasonal variation in lag52.
# 0.0 = pure AR (flat); 1.0 = pure seasonal naive.  0.40 is the default.
SEASONAL_BLEND_WEIGHT = 0.40

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]

# CAT_COLS comes from mo_panel — do NOT redefine it here. Three separate copies of
# this set used to live in this file (the numeric-coercion step, the static-feature
# skip set, and _build_feature_row's cat_names list) and v8 updated only two of the
# three, silently coercing source_brand + spins_flavor_canonical to NaN and killing
# both categoricals at inference. Anything in CAT_COLS is exempt from pd.to_numeric
# and must be supplied explicitly in `state`.
from mo_panel import (CAT_COLS, drop_zero_volume_geographies,  # noqa: E402
                      apply_rma_priority, fill_promo_mechanic_nulls,
                      drop_military_accounts, drop_short_series,
                      MIN_SERIES_WEEKS)


# Category values seen at inference that the model was never trained on.
# Collected across all series and reported once at the end of the run.
_UNSEEN_CATS: dict[str, set[str]] = {}


def _cat_str(val, default: str) -> str:
    """Categorical value as a string, with a fallback that survives NaN.

    `str(val or default)` is wrong here: float('nan') is truthy, so the fallback
    never fires and the literal string "nan" reaches pd.Categorical, where it is
    absent from the trained category universe and silently becomes missing.
    """
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    s = str(val).strip()
    return default if s in ("", "nan", "None", "NaN", "<NA>") else s


def _ordered_cat_names(features_used: list[str]) -> list[str]:
    """Categorical feature names in training-column order.

    LightGBM's Booster.pandas_categorical is a positional list: index i holds the
    category universe of the i-th categorical column *as ordered in the training
    DataFrame*. MO_26 trains on df[[c for c in FEATURE_COLS if c in df.columns]],
    so that order is simply the order within features_used.
    """
    return [c for c in features_used if c in CAT_COLS]


def _load_models_and_meta() -> tuple[dict, dict, dict]:
    # Load _full models (trained on all data) for production deployment.
    # Val-split models are used only for backtest evaluation in build_forecast_chart_data.py.
    models = {}
    for tag in Q_TAGS:
        path = f"outputs/model_retailer_sales_{tag}_{MODEL_VERSION}_full.pkl"
        if not Path(path).exists():
            path = f"outputs/model_retailer_sales_{tag}_{MODEL_VERSION}.pkl"
        with open(path, "rb") as f:
            models[tag] = pickle.load(f)
        print(f"  Loaded {path}")
    # ── Metadata: prefer the version-stamped file, then guard, then trust the PKL ──
    # The unversioned metrics file is shared mutable state: whichever MO_26 run
    # finishes last owns it, regardless of MODEL_VERSION. That is exactly how v8
    # broke — a v7 archival retrain clobbered the v8 metadata, leaving a 48-feature
    # features_used pointed at 56-feature v8 models. Three defences, in order:
    #   1. read outputs/retailer_sales_train_metrics_<version>.json when present
    #   2. hard-fail on a version mismatch rather than mispredicting quietly
    #   3. take features_used from the model artifact itself, which cannot drift
    meta_versioned = Path(f"outputs/retailer_sales_train_metrics_{MODEL_VERSION}.json")
    meta_legacy    = Path("outputs/retailer_sales_train_metrics.json")
    meta_path      = meta_versioned if meta_versioned.exists() else meta_legacy
    with open(meta_path) as f:
        meta = json.load(f)
    print(f"  Loaded {meta_path}")

    meta_version = meta.get("model_version")
    if meta_version != MODEL_VERSION:
        raise SystemExit(
            f"\nFATAL: model metadata version mismatch.\n"
            f"  {meta_path} reports model_version={meta_version!r}\n"
            f"  MO_27 MODEL_VERSION={MODEL_VERSION!r} (loading *_{MODEL_VERSION}_full.pkl)\n"
            f"  Re-run MO_26 with MODEL_VERSION={MODEL_VERSION!r} to regenerate metadata."
        )

    # features_used from the booster — authoritative, immune to metadata drift.
    pkl_features = list(models["q50"].feature_name_)
    meta_features = meta.get("features_used", [])
    if meta_features and list(meta_features) != pkl_features:
        print(f"  WARNING: features_used disagrees with the q50 booster "
              f"(metadata {len(meta_features)}, model {len(pkl_features)}) — "
              f"using the model's feature list")
        print(f"    only in metadata: {sorted(set(meta_features) - set(pkl_features))}")
        print(f"    only in model:    {sorted(set(pkl_features) - set(meta_features))}")
    meta["features_used"] = pkl_features

    # Verify the positional categorical contract _build_feature_row depends on.
    n_cat_model = len(models["q50"]._Booster.pandas_categorical or [])
    cat_names   = _ordered_cat_names(pkl_features)
    if n_cat_model != len(cat_names):
        raise SystemExit(
            f"\nFATAL: categorical count mismatch.\n"
            f"  q50 booster carries {n_cat_model} pandas_categorical list(s)\n"
            f"  MO_27 CAT_COLS resolves to {len(cat_names)}: {cat_names}\n"
            f"  CAT_COLS in MO_27 must mirror MO_26 for the model version being loaded."
        )
    print(f"  Features: {len(pkl_features)} | categoricals: {cat_names}")

    models_total = {}
    if meta.get("total_units_trained"):
        for tag in Q_TAGS:
            path = f"outputs/model_total_units_{tag}_{MODEL_VERSION}_full.pkl"
            if not Path(path).exists():
                path = f"outputs/model_total_units_{tag}_{MODEL_VERSION}.pkl"
            if Path(path).exists():
                with open(path, "rb") as f:
                    models_total[tag] = pickle.load(f)
                print(f"  Loaded {path}")
    return models, meta, models_total


def _build_feature_row(state: dict, features_used: list[str], model=None) -> pd.DataFrame:
    row = {col: state.get(col, np.nan) for col in features_used}
    df  = pd.DataFrame([row])
    # Derived from CAT_COLS in training-column order, not hardcoded — a hardcoded
    # list silently mis-indexes pandas_categorical whenever FEATURE_COLS changes.
    cat_names = _ordered_cat_names(features_used)
    if model is not None:
        _pc = model._Booster.pandas_categorical
        for i, cname in enumerate(cat_names):
            if cname in df.columns and i < len(_pc):
                _raw = df[cname].astype(str)
                df[cname] = pd.Categorical(_raw, categories=_pc[i])
                # An out-of-universe value becomes NaN here with no error. That is
                # correct behaviour for a genuinely new retailer/geography, but it
                # must be visible — a systematic mismatch (e.g. a renamed channel)
                # otherwise degrades every forecast while looking perfectly healthy.
                if df[cname].isna().any() and _raw.notna().any():
                    _UNSEEN_CATS.setdefault(cname, set()).add(_raw.iloc[0])
    else:
        for cname in cat_names:
            if cname in df.columns:
                df[cname] = df[cname].astype("category")
    return df


if __name__ == "__main__":
    # ── 1. Load models ───────────────────────────────────────────────────────
    print("Loading models and metadata …")
    models, meta, models_total = _load_models_and_meta()
    features_used       = meta["features_used"]
    features_used_total = meta.get("total_units_features_used", [])
    forecast_total      = bool(models_total)

    # ── 1b. Load MO_67 q90 calibration constant (conformal post-hoc) ────────
    # MO_67 found q90 coverage = 82.1% on the Jan–Apr 2026 val set (target 90%).
    # MO_67b computed a multiplicative constant (1.0124×) that restores coverage
    # to 89.8%. Applied to units_high after seasonal blend, before writing parquet.
    _cal_path = Path("outputs/mo67_calibration_constants.json")
    _q90_cal_factor = 1.0
    if _cal_path.exists():
        with open(_cal_path) as _f:
            _cal = json.load(_f)
        if _cal.get("calibration_type") == "multiplicative":
            _q90_cal_factor = float(_cal.get("q90_constant", 1.0))
        elif _cal.get("calibration_type") == "additive":
            _q90_cal_factor = None  # handled separately below
            _q90_cal_offset = float(_cal.get("q90_constant", 0.0))
        print(f"  q90 calibration: {_cal['calibration_type']} "
              f"constant={_cal['q90_constant']:.4f}  "
              f"(coverage {_cal['uncalibrated_coverage']*100:.1f}% → "
              f"{_cal['calibrated_coverage']*100:.1f}%)")
    else:
        print("  q90 calibration constants not found — applying raw q90 predictions")

    # ── 1c. Load MO_59 seasonal index (week_of_year → stl_seasonal_index) ───
    # This curve is the ONLY seasonal signal for the ~55% of series with no year-ago
    # anchor (the `elif seasonal_lookup` branch below), including 51% of Target's volume.
    # It therefore shapes the majority of the forecast and is checked before use.
    #
    # MO_59c measured that its peak week needs ~200 contributing series to be reliable:
    # at n=20 the March mode beats the October mode in only 41% of bootstrap draws — a
    # coin flip — while correlation to the full-sample curve is already 0.77. So
    # correlation CANNOT validate this; only the contributing series count can.
    # Only ~281 series qualify, so the headroom is thin and worth asserting on.
    _seas_path = Path("outputs/mo59_seasonal_index.csv")
    _seas_meta = Path("outputs/mo59_seasonal_index_meta.json")
    SEASONAL_MIN_SERIES = 200
    if _seas_path.exists():
        _seas_df = pd.read_csv(_seas_path)
        seasonal_lookup: dict[int, float] = dict(
            zip(_seas_df["week_of_year"].astype(int), _seas_df["seasonal_index"])
        )
        if _seas_meta.exists():
            _sm = json.loads(_seas_meta.read_text())
            _n = int(_sm.get("n_series", 0))
            print(f"  Loaded STL seasonal index ({len(seasonal_lookup)} weeks) — "
                  f"n_series={_n}, peak wk {_sm.get('peak_week')}, "
                  f"trough wk {_sm.get('trough_week')}, built {_sm.get('generated_at','?')[:10]}")
            if _n < SEASONAL_MIN_SERIES:
                print(f"  *** WARNING: seasonal index built from {_n} series; "
                      f"~{SEASONAL_MIN_SERIES} needed for a reliable peak week.")
                print(f"      Its peak is close to a coin flip between the March and October")
                print(f"      modes, and it drives the seasonal signal for every series")
                print(f"      without a year-ago anchor. Re-run MO_59 or treat with caution.")
        else:
            # No provenance = we cannot tell what this curve was built from. That is
            # exactly the state that let a stale, unreproducible index ship: the old CSV
            # was untracked and unstamped, so there was no way to date or reproduce it.
            print(f"  *** WARNING: {_seas_meta.name} missing — cannot verify how many series")
            print(f"      the seasonal index was built from, or when. Re-run MO_59 to stamp it.")
    else:
        seasonal_lookup = {}
        print("  STL seasonal index not found — stl_seasonal_index will be 0.0")

    # ── 2. Load actuals panel (seed data) ────────────────────────────────────
    print("\nLoading retailer_sales_weekly.parquet …")
    df_actual = pd.read_parquet("outputs/retailer_sales_weekly.parquet")
    df_actual["__time"] = pd.to_datetime(df_actual["__time"], utc=True)

    # v9: same zero-volume geography filter as training. Forecasting a market that
    # has never sold a unit produces rows the UI must then explain, and it is the
    # training/inference symmetry that matters — the model has not seen these.
    print("\n  ── Panel rules (v9) — MUST match MO_26 exactly ──")
    df_actual = fill_promo_mechanic_nulls(df_actual)
    df_actual = drop_military_accounts(df_actual)
    df_actual = drop_zero_volume_geographies(df_actual, target="base_units")
    df_actual = apply_rma_priority(df_actual)

    # Short-series gate. MO_27 has NO minimum-history check of its own and NO ETS
    # fallback — ETS lives only in MO_30–MO_37 and the chart builder, and MO_34's
    # data-maturity router ("new/expanding -> ETS, mature -> LightGBM") is analysis, not
    # production code. Now that MIN_WEEKS no longer runs at extract, these series DO
    # reach the parquet, so without this gate MO_27 would build feature rows whose
    # lag13 / roll13 / lag52 are all NaN and serve the predictions as if they were sound.
    # Skipping with a logged, named list is the honest behaviour until a real ETS route
    # is wired in — these are BUILT's newest launches and they need one.
    _pre = df_actual.groupby(GROUP_COLS, observed=True).ngroups
    _short = df_actual.groupby(GROUP_COLS, observed=True)["base_units"].transform("count") < MIN_SERIES_WEEKS
    if _short.any():
        _skipped_upcs = sorted(set(df_actual.loc[_short, "upc"]))
        _skipped_series = df_actual.loc[_short].groupby(GROUP_COLS, observed=True).ngroups
        print(f"\n  NOT FORECAST — {_skipped_series:,} series across {len(_skipped_upcs)} UPC(s) "
              f"have <{MIN_SERIES_WEEKS} weeks of history:")
        for _u in _skipped_upcs[:12]:
            _s = df_actual[(df_actual["upc"] == _u) & _short]
            _d = str(_s["description"].iloc[0])[:44] if "description" in _s else ""
            print(f"      {_u}  {int(_s['base_units'].sum()):>9,} units  "
                  f"{_s['retail_account'].nunique():>3} accounts  {_d}")
        if len(_skipped_upcs) > 12:
            print(f"      … and {len(_skipped_upcs) - 12} more")
        print(f"      These need an ETS / cold-start route (MO_34 establishes the rule);")
        print(f"      LightGBM cannot forecast them — lag13/roll13/lag52 are all NaN.")
    df_actual = drop_short_series(df_actual, verbose=False)
    print(f"  Series to forecast: {df_actual.groupby(GROUP_COLS, observed=True).ngroups:,} "
          f"of {_pre:,}")

    # CAT_COLS from mo_panel — NOT a local copy. geography_raw is a GROUP_COL, so
    # coercing it to numeric turns the whole column to NaN and groupby(GROUP_COLS)
    # then drops every row (pandas dropna=True) for a silent zero-series forecast
    # that still exits 0.
    num_cols = [c for c in features_used if c not in CAT_COLS and c != "week_of_year"]
    for c in num_cols:
        if c in df_actual.columns:
            df_actual[c] = pd.to_numeric(df_actual[c], errors="coerce")
    # Derive semi-annual seasonality if not in parquet
    if "week_of_year" in df_actual.columns:
        _woy = df_actual["week_of_year"].fillna(1)
        df_actual["week_sin26"] = np.sin(2 * np.pi * _woy / 26)
        df_actual["week_cos26"] = np.cos(2 * np.pi * _woy / 26)

    df_actual = df_actual.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    # Keep enough trailing weeks: lag13 needs 13, YAGO (lag52) needs 52 + 13 = 65
    df_seed = (
        df_actual
        .groupby(GROUP_COLS)
        .tail(65)
        .reset_index(drop=True)
    )
    anchor_date = df_actual["__time"].max()
    print(f"  Anchor date:      {anchor_date.date()}")
    _n_series = df_seed.groupby(GROUP_COLS).ngroups
    print(f"  Series to forecast: {_n_series:,}")

    # Fail loudly on an empty panel. groupby(GROUP_COLS) drops rows with a NaN in
    # ANY key column, so one all-NaN group key (e.g. geography_raw wrongly run
    # through pd.to_numeric) silently yields zero series and a clean exit 0.
    if _n_series == 0:
        _null_keys = {c: int(df_actual[c].isna().sum()) for c in GROUP_COLS}
        raise SystemExit(
            f"\nFATAL: zero series to forecast from {len(df_actual):,} actual rows.\n"
            f"  Nulls per GROUP_COL: {_null_keys}\n"
            f"  A GROUP_COL that is 100% null was almost certainly coerced by\n"
            f"  pd.to_numeric — check that every categorical is listed in CAT_COLS."
        )

    # ── 3. Rolling 13-week autoregressive forecast ───────────────────────────
    scored_at = datetime.now(timezone.utc).isoformat()
    all_rows  = []

    for group_keys, g in df_seed.groupby(GROUP_COLS):
        g = g.sort_values("__time")
        upc, channel, account, geo = group_keys

        # Seed lag history from actuals
        units_history = g["base_units"].tolist()
        arp_history   = g["arp"].tolist()
        # total_units history (base + promo); mirrors units_history structure
        total_history = g["total_units"].fillna(g["base_units"]).tolist() if forecast_total and "total_units" in g.columns else []

        # YAGO: precompute year-ago base_units for each of the 13 forecast steps.
        # At step k (1-indexed), lag52 = actual at anchor - (52 - k) weeks.
        # Index in units_history: N_actual - 53 + k  (always an actual, never a prediction)
        N_actual  = len(units_history)
        lag52_seq = [
            float(units_history[N_actual - 53 + k])
            if 0 <= (N_actual - 53 + k) < N_actual else np.nan
            for k in range(1, FORECAST_WEEKS + 1)
        ]

        # Year-over-year ratio at the anchor point.
        # Used in the forecast loop to scale lag52_seq into a seasonal reference:
        #   seasonal_ref[k] = lag52_seq[k] * yoy_ratio
        # This projects the actual year-ago weekly curve forward, adjusted for
        # how current demand is tracking relative to last year (up/down/flat).
        _yago_anchor = float(units_history[N_actual - 52]) if N_actual >= 52 else None
        if _yago_anchor and _yago_anchor > 0:
            _anchor_units = float(units_history[-1])
            # Sanity-clamp: cap at 2× up or down to avoid outlier series blowing up
            yoy_ratio = float(np.clip(_anchor_units / _yago_anchor, 0.5, 2.0))
        else:
            yoy_ratio = None

        # Parallel YAGO seq + ratio for total_units
        N_total = len(total_history)
        if forecast_total and N_total > 0:
            lag52_total_seq = [
                float(total_history[N_total - 53 + k])
                if 0 <= (N_total - 53 + k) < N_total else np.nan
                for k in range(1, FORECAST_WEEKS + 1)
            ]
            _yago_total = float(total_history[N_total - 52]) if N_total >= 52 else None
            if _yago_total and _yago_total > 0:
                yoy_ratio_total = float(np.clip(float(total_history[-1]) / _yago_total, 0.5, 2.0))
            else:
                yoy_ratio_total = None
        else:
            lag52_total_seq = []
            yoy_ratio_total = None

        # Latest row for static features
        latest = g.iloc[-1]

        meta_fields = {
            "upc":                  upc,
            "description":          latest.get("description"),
            "channel_outlet":       channel,
            "retail_account":       account,
            "geography_raw":        geo,
            "geography_display":    latest.get("geography_display", geo),
            "geography_level":      latest.get("geography_level"),
            "anchor_date":          latest["__time"].isoformat(),
            "anchor_base_units":    float(latest["base_units"]) if pd.notna(latest["base_units"]) else 0.0,
            "anchor_arp":           float(latest["arp"]) if pd.notna(latest["arp"]) else 0.0,
            "arp_fallback":         int(latest.get("arp_fallback") or 0),
        }

        # MO_46 rolling signals — static seed values (last observed; held flat across horizon)
        _cp  = latest.get("rolling_cannibal_pressure")
        _ct  = latest.get("rolling_cannibal_trend")
        _re  = latest.get("rolling_elasticity")
        rolling_seed = {
            "rolling_cannibal_pressure": float(_cp) if pd.notna(_cp) else np.nan,
            "rolling_cannibal_trend":    float(_ct) if pd.notna(_ct) else np.nan,
            "rolling_elasticity":        float(_re) if pd.notna(_re) else np.nan,
        }

        # v8: precompute promo-52w history for leakage-free forward promo cadence signal
        if "is_promo_week" in g.columns:
            promo_hist  = g["is_promo_week"].fillna(0).tolist()
            N_promo     = len(promo_hist)
            promo_52w_seq = [
                float(promo_hist[N_promo - 53 + k])
                if 0 <= (N_promo - 53 + k) < N_promo else 0.0
                for k in range(1, FORECAST_WEEKS + 1)
            ]
        else:
            promo_52w_seq = [0.0] * FORECAST_WEEKS

        # v8: per-series × week-of-year promo rate from history (no future leakage)
        if "is_promo_week" in g.columns and "week_of_year" in g.columns:
            _woy_num = pd.to_numeric(g["week_of_year"], errors="coerce")
            promo_rate_by_woy = (
                g.assign(_woy_int=_woy_num.fillna(0).astype(int))
                .groupby("_woy_int")["is_promo_week"]
                .mean()
                .to_dict()
            )
        else:
            promo_rate_by_woy = {}

        # Static features (unchanged across forecast horizon)
        static_feats = {}
        skip = CAT_COLS | {"week_of_year", "week_sin", "week_cos", "week_sin26", "week_cos26",
                # v8: AR dynamic promo activity flags — set to 0 in base forecast
                "is_promo_week", "promo_intensity",
                "units_lift_tpr", "units_lift_any_display", "units_lift_any_feature",
                # v8: promo cadence signals — computed per step from history
                "promo_52w_lag", "promo_rate_woy",
                "base_units_lag1", "base_units_lag4", "base_units_lag13",
                "base_units_lag52",                          # dynamic — updated per step
                "total_units_lag1", "total_units_lag4", "total_units_lag13",
                "total_units_lag52",                         # dynamic — updated per step
                "arp_lag1", "arp_lag4", "arp_wow_delta",
                "arp_roll8_avg", "arp_roll8_std", "arp",
                "rolling_cannibal_pressure", "rolling_cannibal_trend", "rolling_elasticity"}
        for col in features_used:
            if col not in skip:
                val = latest.get(col)
                static_feats[col] = float(pd.to_numeric(val, errors="coerce") or 0)

        retail_acct_val = str(latest.get("retail_account") or account)
        pack_count_val  = str(latest.get("pack_count") or "")

        # ARP for dollar conversion — assume flat (user can slide in UI)
        forecast_arp = meta_fields["anchor_arp"] or float(latest.get("post_13w_arp") or 0)

        for step in range(1, FORECAST_WEEKS + 1):
            forecast_date = anchor_date + pd.Timedelta(weeks=step)
            wsl = int(latest.get("weeks_since_launch") or 0) + step

            # Autoregressive lags from combined actuals + prior predictions
            lag1  = units_history[-1]  if len(units_history) >= 1  else np.nan
            lag4  = units_history[-4]  if len(units_history) >= 4  else np.nan
            lag13 = units_history[-13] if len(units_history) >= 13 else np.nan
            lag52 = lag52_seq[step - 1]     # precomputed from actuals — no leakage

            arp_cur   = arp_history[-1] if arp_history else forecast_arp
            arp_lag1  = arp_history[-2] if len(arp_history) >= 2 else arp_cur
            arp_lag4  = arp_history[-4] if len(arp_history) >= 4 else np.nan

            # ARP rolling stats (trailing 8 prior ARP values)
            arp_window    = arp_history[-8:]
            arp_roll8_avg = float(np.nanmean(arp_window)) if arp_window else np.nan
            arp_roll8_std = float(np.nanstd(arp_window))  if len(arp_window) > 1 else 0.0
            arp_wow_delta = (arp_cur - arp_lag1) if pd.notna(arp_lag1) else 0.0

            # Cyclical seasonality — computed from forecast date each step
            _fw     = int(forecast_date.isocalendar().week)
            _wsin   = float(np.sin(2 * np.pi * _fw / 52))
            _wcos   = float(np.cos(2 * np.pi * _fw / 52))
            _wsin26 = float(np.sin(2 * np.pi * _fw / 26))
            _wcos26 = float(np.cos(2 * np.pi * _fw / 26))

            # total_units AR lags (from combined actuals + prior predictions)
            t_lag1  = total_history[-1]  if len(total_history) >= 1  else np.nan
            t_lag4  = total_history[-4]  if len(total_history) >= 4  else np.nan
            t_lag13 = total_history[-13] if len(total_history) >= 13 else np.nan
            t_lag52 = lag52_total_seq[step - 1] if lag52_total_seq else np.nan

            state = {
                **static_feats,
                **rolling_seed,             # MO_46: static competitive signals
                "channel_outlet":           channel,
                "retail_account":           retail_acct_val,
                "pack_count":               pack_count_val,
                # _cat_str, not `x or default` — NaN is truthy in Python, so the
                # `or` fallback never fires and str(nan) leaks the string "nan"
                # into the category lookup, which then resolves to missing.
                "spins_flavor_canonical":   _cat_str(latest.get("spins_flavor_canonical"), "UNKNOWN"),
                "source_brand":             _cat_str(latest.get("source_brand"), "UNKNOWN"),
                "geography_raw":            _cat_str(geo, "UNKNOWN"),   # v9: 6th categorical
                "week_sin":                 _wsin,
                "week_cos":                 _wcos,
                "week_sin26":               _wsin26,
                "week_cos26":               _wcos26,
                "weeks_since_launch":       wsl,
                # v8: AR dynamic promo flags — 0 in base forecast (no promo assumed)
                "is_promo_week":            0.0,
                "promo_intensity":          0.0,
                "units_lift_tpr":           0.0,
                "units_lift_any_display":   0.0,
                "units_lift_any_feature":   0.0,
                # v8: promo cadence signals from history (leakage-free)
                "promo_52w_lag":            promo_52w_seq[step - 1],
                "promo_rate_woy":           promo_rate_by_woy.get(_fw, 0.0),
                "arp":                      arp_cur,
                "arp_lag1":                 arp_lag1,
                "arp_lag4":                 arp_lag4,
                "arp_roll8_avg":            arp_roll8_avg,
                "arp_roll8_std":            arp_roll8_std,
                "arp_wow_delta":            arp_wow_delta,
                "base_units_lag1":          lag1,
                "base_units_lag4":          lag4,
                "base_units_lag13":         lag13,
                "base_units_lag52":         lag52,
                "total_units_lag1":         t_lag1,
                "total_units_lag4":         t_lag4,
                "total_units_lag13":        t_lag13,
                "total_units_lag52":        t_lag52,
            }

            X = _build_feature_row(state, features_used, model=models["q50"])

            # Models predict in log1p space — invert with expm1
            units_low  = float(np.expm1(max(0, models["q10"].predict(X)[0])))
            units_base = float(np.expm1(max(0, models["q50"].predict(X)[0])))
            units_high = float(np.expm1(max(0, models["q90"].predict(X)[0])))

            # Seasonal blend: prevent the AR collapse-to-flat problem.
            # After ~4 steps, lag1/lag4/lag13 become self-predictions and the
            # dominant AR signal drowns out lag52's weekly seasonal variation.
            # We bend each step toward a seasonal reference:
            #   seasonal_ref = this_week's_yago × yoy_ratio
            # which projects the year-ago seasonal curve forward at the current
            # year-over-year level.  All three quantiles shift by the same
            # multiplicative factor to preserve the band shape.
            if (yoy_ratio is not None and pd.notna(lag52)
                    and lag52 > 0 and units_base > 0):
                seasonal_ref = lag52 * yoy_ratio
                blend_mult = (
                    (1.0 - SEASONAL_BLEND_WEIGHT) * units_base
                    + SEASONAL_BLEND_WEIGHT * seasonal_ref
                ) / units_base
                units_low  = max(0.0, units_low  * blend_mult)
                units_base = max(0.0, units_base * blend_mult)
                units_high = max(0.0, units_high * blend_mult)

            # Layer 1 — STL seasonal index (portfolio-level pattern from MO_59).
            # Applied ONLY when the YAGO blend above did not fire (lag52 unavailable).
            # For new SKUs without a year-ago reference, this borrows the portfolio
            # seasonal curve as the sole seasonal signal — complementary to YAGO,
            # not a replacement.
            elif seasonal_lookup and units_base > 0:
                woy = int(forecast_date.isocalendar().week)
                stl_idx = seasonal_lookup.get(woy, 0.0)
                if stl_idx != 0.0:
                    stl_mult = max(0.1, 1.0 + stl_idx)
                    units_low  = max(0.0, units_low  * stl_mult)
                    units_base = max(0.0, units_base * stl_mult)
                    units_high = max(0.0, units_high * stl_mult)

            # MO_67b: apply q90 conformal calibration constant (after all blending).
            # Coverage without this: 82.1%; with: 89.8% on Jan–Apr 2026 holdout.
            if _q90_cal_factor and _q90_cal_factor != 1.0:
                units_high = max(0.0, units_high * _q90_cal_factor)
            elif not _q90_cal_factor:  # additive path (unlikely to be selected)
                units_high = max(0.0, units_high + _q90_cal_offset)

            # Feed blended q50 back as next step's lag seed (keeps AR and
            # seasonal blend consistent across the full 13-step horizon)
            units_history.append(units_base)
            arp_history.append(arp_cur)  # hold ARP flat (no external signal yet)

            # ── Parallel total_units forecast ────────────────────────────────
            total_low = total_base = total_high = None
            if forecast_total and features_used_total:
                X_t = _build_feature_row(state, features_used_total)
                total_low  = float(np.expm1(max(0, models_total["q10"].predict(X_t)[0])))
                total_base = float(np.expm1(max(0, models_total["q50"].predict(X_t)[0])))
                total_high = float(np.expm1(max(0, models_total["q90"].predict(X_t)[0])))
                if (yoy_ratio_total is not None and pd.notna(t_lag52)
                        and t_lag52 > 0 and total_base > 0):
                    s_ref_t = t_lag52 * yoy_ratio_total
                    bm_t = ((1.0 - SEASONAL_BLEND_WEIGHT) * total_base
                            + SEASONAL_BLEND_WEIGHT * s_ref_t) / total_base
                    total_low  = max(0.0, total_low  * bm_t)
                    total_base = max(0.0, total_base * bm_t)
                    total_high = max(0.0, total_high * bm_t)
                # Coherence clamp: total_units >= base_units (promo units cannot be negative)
                if total_low  is not None: total_low  = max(total_low,  units_low)
                if total_base is not None: total_base = max(total_base, units_base)
                if total_high is not None: total_high = max(total_high, units_high)
                total_history.append(total_base)

            all_rows.append({
                **meta_fields,
                "__time":               forecast_date,
                "forecast_week_number": step,
                "forecast_units_low":   units_low,
                "forecast_units_base":  units_base,
                "forecast_units_high":  units_high,
                "forecast_dollars_low":  round(units_low  * forecast_arp, 2),
                "forecast_dollars_base": round(units_base * forecast_arp, 2),
                "forecast_dollars_high": round(units_high * forecast_arp, 2),
                "forecast_total_units_low":  total_low,
                "forecast_total_units_base": total_base,
                "forecast_total_units_high": total_high,
                "weeks_since_launch":   wsl,
                "model_version":        MODEL_VERSION,
                "scored_at":            scored_at,
            })

    # ── 4. Assemble + diagnostics ────────────────────────────────────────────
    out = pd.DataFrame(all_rows)
    print(f"\n  Total forecast rows:   {len(out):,}")
    print(f"  Forecast weeks:        {out['forecast_week_number'].max()}")
    print(f"  Unique UPCs:           {out['upc'].nunique()}")
    print(f"  Series forecast:       {out.groupby(GROUP_COLS).ngroups:,}")
    print(f"  q50 unit range:        {out['forecast_units_base'].min():.0f} – {out['forecast_units_base'].max():.0f}")
    print(f"  q50 dollar range:      ${out['forecast_dollars_base'].min():.0f} – ${out['forecast_dollars_base'].max():.0f}")
    print(f"  Median band width:     {(out['forecast_units_high'] - out['forecast_units_low']).median():.0f} units")

    # Unseen categoricals — these predicted with the category treated as missing.
    if _UNSEEN_CATS:
        print("\n  WARNING: category values absent from the trained model:")
        for _c, _vals in sorted(_UNSEEN_CATS.items()):
            _shown = sorted(_vals)[:5]
            print(f"    {_c}: {len(_vals)} unseen — {_shown}"
                  f"{' …' if len(_vals) > 5 else ''}")
        print("    These series predicted with that categorical as missing. "
              "Expected for genuinely new doors; retrain if it is systematic.")
    if forecast_total and "forecast_total_units_base" in out.columns and out["forecast_total_units_base"].notna().any():
        print(f"  q50 total_units range: {out['forecast_total_units_base'].min():.0f} – {out['forecast_total_units_base'].max():.0f}")
        promo_est = out["forecast_total_units_base"] - out["forecast_units_base"]
        print(f"  Median promo contribution: {promo_est.median():.0f} units/week")

    if out.empty:
        print("No rows to write.")
    else:
        out.to_parquet("outputs/retailer_sales_forecast.parquet", index=False)
        print("  Saved → outputs/retailer_sales_forecast.parquet")
        write_back(out, "retailer_sales_forecast", timestamp_col="__time")
