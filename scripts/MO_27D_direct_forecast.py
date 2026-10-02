"""MO_27D — 13-week forecast from DIRECT multi-horizon models. Replaces MO_27's recursive loop.

Emits the identical `retailer_sales_forecast` schema as MO_27, so the API and UI are unchanged.

WHAT IS DIFFERENT FROM MO_27
----------------------------
MO_27 forecasts recursively: predict week 1, feed it back as `lag1`, predict week 2, and so on.
Measured consequence — it reaches a fixed point by step 3 and flatlines at last_actual x 1.03,
keeping 6% of real week-to-week variation, because `lag1` becomes the model's own prior output
and 31 of 56 features are frozen for the whole horizon.

Here each horizon has its OWN model (MO_26D). One feature row per series, built once from the
last observed week, is scored by 13 different models. There is no feedback and no self-reference,
so:
  * `lag1` stays a genuine lag and its influence decays naturally with h
  * seasonality, TDP, promo character and lifecycle can actually drive the curve
  * short series need no lag chain — they score natively instead of being excluded

TARGET-WEEK SEASONALITY: week_sin/cos must describe the week being PREDICTED (t+h), exactly as
MO_26D trained them. Passing the anchor week's values would silently mismatch train and score.

LAPSED SERIES GET AN EXPECTED VALUE, NOT A ZERO
-----------------------------------------------
513 series have no recorded SPINS row for 9+ weeks. Carrying their stale level forward invents
demand; forecasting a hard zero is equally wrong, because measurement says lapses are often not
terminal. Across 878 lapse episodes (365 resumed, 513 still silent), a series resumes within 13
weeks with probability 17.5% at 9-13 weeks silent, 20.0% at 14-26, decaying to 0.5-1.7% beyond
two years — and when it resumes it comes back at ~1.06x its pre-gap level.

So a lapsed SKU is forecast at `pre-gap level x P(resume | weeks silent) x 1.06`, which decays
smoothly toward zero with staleness instead of snapping to it. Total across all 513 series is
~134 units/week against a ~770K portfolio (0.02%), so this is about being explainable and
defensible rather than about accuracy.

Each lapsed row also carries `same_shelf_launch_upc` when a DIFFERENT SKU launched beside it on
the same shelf (138 of 513; 91 of those BAR<->PUFF). That is an observational label only — every
UPC is its own SKU with its own forecast, no history is transferred between them, and the label
never changes a number.

Run:  python MO_27D_direct_forecast.py [--version v11d] [--no-writeback]
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

warnings.filterwarnings("ignore")

from mo_panel import (CAT_COLS, GROUP_COLS, drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_ak_hi_market_variants, warn_nested_rma_duplicates,
                      lapse_resume_probability, find_same_shelf_launches,
                      classify_lapse_cause, LAPSE_TDP_MULT, LAPSE_RESUME_LEVEL)
from mo_writeback import write_back

PARQUET        = Path("outputs/retailer_sales_weekly.parquet")
FORECAST_WEEKS = 13
Q_TAGS         = ["q10", "q50", "q90"]
LAPSE_WEEKS    = 9
SEASONAL_FEATS = ("week_sin", "week_cos", "week_sin26", "week_cos26")


def load_models(version: str) -> tuple[dict, dict, list[str]]:
    models, meta_path = {}, Path(f"outputs/direct_multihorizon_metrics_{version}.json")
    if not meta_path.exists():
        raise SystemExit(f"FATAL: {meta_path} not found — run MO_26D first.")
    meta = json.loads(meta_path.read_text())
    if meta.get("model_version") != version:
        raise SystemExit(f"FATAL: metrics file says {meta.get('model_version')!r}, want {version!r}")
    for h in range(1, FORECAST_WEEKS + 1):
        models[h] = {}
        for tag in Q_TAGS:
            p = Path(f"outputs/model_direct_h{h:02d}_{tag}_{version}.pkl")
            if not p.exists():
                raise SystemExit(f"FATAL: missing {p}")
            models[h][tag] = pickle.load(open(p, "rb"))
    # features_used from the booster itself, never from metadata — metadata can drift
    feats = list(models[1]["q50"].feature_name_)
    print(f"  Loaded {len(models)*3} direct models ({version}) | {len(feats)} features")
    return models, meta, feats


def build_panel(feats: list[str]) -> pd.DataFrame:
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
    print("  ── Panel rules (must match MO_26D exactly) ──")
    df = fill_promo_mechanic_nulls(df)
    df = drop_military_accounts(df)
    df = drop_ak_hi_market_variants(df)
    df = drop_zero_volume_geographies(df, target="base_units")
    df = apply_rma_priority(df)
    warn_nested_rma_duplicates(df)
    for c in CAT_COLS:
        if c in df.columns:
            df[c] = df[c].astype("category")
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


def main(version: str, writeback: bool):
    print(f"MO_27D — direct multi-horizon forecast | version {version}\n")
    models, meta, feats = load_models(version)
    df = build_panel(feats)

    anchor_date = df["__time"].max()
    n_series = df.groupby(GROUP_COLS, observed=True).ngroups
    print(f"\n  Anchor date: {anchor_date.date()} | {len(df):,} rows | {n_series:,} series")

    # ── Lapse gate (carried over from MO_27) ──
    last_seen = df.groupby(GROUP_COLS, observed=True)["__time"].max()
    lapse_wks = ((anchor_date - last_seen).dt.days / 7).round()
    lapsed = {tuple(k): float(v) for k, v in lapse_wks[lapse_wks >= LAPSE_WEEKS].items()}
    print(f"  Lapse handling: {len(lapsed):,} series with no SPINS row in {LAPSE_WEEKS}+ weeks")
    print(f"      forecast = pre-gap level x P(resume | weeks silent) x {LAPSE_RESUME_LEVEL}")
    print(f"      (NOT a hard zero — 365 of 878 historical lapses resumed at ~1.06x)")
    co_launch = find_same_shelf_launches(df)
    # Pre-gap level: mean of each lapsed series' last up-to-4 OBSERVED weeks.
    pre_level = (df.groupby(GROUP_COLS, observed=True)["base_units"]
                 .apply(lambda s: float(pd.to_numeric(s.tail(4), errors="coerce").mean()))
                 .to_dict())
    # Why each lapsed series went quiet, from its pre-lapse TDP trend. A stockout stops selling
    # while still distributed; a delisting winds TDP down first. Measured 45.2% vs 31.7% resume.
    cause = (df.groupby(GROUP_COLS, observed=True)["tdp"].apply(classify_lapse_cause).to_dict()
             if "tdp" in df.columns else {})
    if cause:
        from collections import Counter
        _c = Counter(cause[k] for k in lapsed if k in cause)
        print("      lapse cause (pre-lapse TDP trend): "
              + ", ".join(f"{k}={v}" for k, v in _c.most_common()))
    print(f"  Direct-model series: {n_series - len(lapsed):,}\n")

    # One feature row per series, taken from its last observed week.
    last = df.groupby(GROUP_COLS, observed=True).tail(1).reset_index(drop=True)
    scored_at = datetime.now(timezone.utc).isoformat()
    rows = []

    for h in range(1, FORECAST_WEEKS + 1):
        fd = anchor_date + pd.Timedelta(weeks=h)
        X = last.copy()
        # Target-week seasonality — must match MO_26D's training construction.
        tw = float(fd.isocalendar().week)
        X["week_sin"] = np.sin(2 * np.pi * tw / 52)
        X["week_cos"] = np.cos(2 * np.pi * tw / 52)
        X["week_sin26"] = np.sin(2 * np.pi * tw / 26)
        X["week_cos26"] = np.cos(2 * np.pi * tw / 26)
        preds = {t: np.clip(np.expm1(models[h][t].predict(X[feats])), 0, None) for t in Q_TAGS}
        # Quantile crossing: independently fitted quantiles can invert. Sort so low<=base<=high.
        lo, bs, hi = (np.minimum(preds["q10"], preds["q50"]), preds["q50"],
                      np.maximum(preds["q90"], preds["q50"]))
        for i, r in X.iterrows():
            key = tuple(r[c] for c in GROUP_COLS)
            is_lapsed = key in lapsed
            if is_lapsed:
                _cause = cause.get(key, "unknown")
                _p = lapse_resume_probability(lapsed[key]) * LAPSE_TDP_MULT.get(_cause, 1.0)
                _lvl = pre_level.get(key, 0.0)
                _e = (0.0 if not np.isfinite(_lvl)
                      else max(0.0, _lvl * _p * LAPSE_RESUME_LEVEL))
                # Band spans "stays gone" to "comes back at full strength" — that IS the
                # uncertainty, and a narrow band here would misrepresent it.
                u_lo, u_b, u_hi = 0.0, _e, (0.0 if not np.isfinite(_lvl)
                                            else max(0.0, _lvl * LAPSE_RESUME_LEVEL))
            else:
                u_lo, u_b, u_hi = lo[i], bs[i], hi[i]
            arp = float(pd.to_numeric(r.get("arp"), errors="coerce") or 0.0)
            wsl = pd.to_numeric(r.get("weeks_since_launch"), errors="coerce")
            rows.append({
                "upc": r["upc"], "description": r.get("description"),
                "channel_outlet": r["channel_outlet"], "retail_account": r["retail_account"],
                "geography_raw": r["geography_raw"],
                "geography_display": r.get("geography_display", r["geography_raw"]),
                "geography_level": r.get("geography_level"),
                "anchor_date": r["__time"].isoformat(),
                "anchor_base_units": float(r["base_units"]) if pd.notna(r["base_units"]) else 0.0,
                "anchor_arp": arp,
                "arp_fallback": int(pd.to_numeric(r.get("arp_fallback"), errors="coerce") or 0),
                "__time": fd, "forecast_week_number": h,
                "forecast_units_low": round(float(u_lo), 2),
                "forecast_units_base": round(float(u_b), 2),
                "forecast_units_high": round(float(u_hi), 2),
                "forecast_dollars_low": round(float(u_lo) * arp, 2),
                "forecast_dollars_base": round(float(u_b) * arp, 2),
                "forecast_dollars_high": round(float(u_hi) * arp, 2),
                "forecast_total_units_low": round(float(u_lo), 2),
                "forecast_total_units_base": round(float(u_b), 2),
                "forecast_total_units_high": round(float(u_hi), 2),
                "weeks_since_launch": int(wsl + h) if np.isfinite(wsl) else None,
                "model_version": version,
                "forecast_method": ("lapsed_resume_expected_value" if is_lapsed
                                    else "direct_multihorizon"),
                "weeks_silent": round(lapsed[key], 0) if is_lapsed else 0,
                "lapse_cause": cause.get(key, "unknown") if is_lapsed else None,
                "same_shelf_launch_upc": co_launch.get(key) if is_lapsed else None,
                "scored_at": scored_at,
            })
        print(f"    h={h:>2d} week {fd.date()}  q50 sum {bs.sum():>12,.0f}")

    out = pd.DataFrame(rows)
    print(f"\n  Rows: {len(out):,} | series {out.groupby(GROUP_COLS).ngroups:,} "
          f"| weeks {out['forecast_week_number'].nunique()}")
    print(out["forecast_method"].value_counts().to_string())

    # Flattening check — the entire reason this script exists. If the direct forecast is as flat
    # as the recursive one was (0.062), the change did not work and must not be shipped quietly.
    piv = out[out.forecast_method == "direct_multihorizon"].pivot_table(
        index=GROUP_COLS, columns="forecast_week_number", values="forecast_units_base")
    cv_f = (piv.std(axis=1) / piv.mean(axis=1).replace(0, np.nan)).dropna()
    hist = df[df["__time"] > anchor_date - pd.Timedelta(weeks=13)]
    cv_a = (hist.groupby(GROUP_COLS, observed=True)["base_units"].std()
            / hist.groupby(GROUP_COLS, observed=True)["base_units"].mean().replace(0, np.nan)).dropna()
    print(f"\n  Within-series CV across 13 weeks: forecast {cv_f.median():.4f} "
          f"| actuals {cv_a.median():.4f}  -> {cv_a.median()/max(cv_f.median(),1e-9):.1f}x flatter")
    print(f"  (MO_27 recursive was 3.6x flatter; lower is better)")

    out.to_parquet("outputs/retailer_sales_forecast_direct.parquet", index=False)
    print(f"  Saved -> outputs/retailer_sales_forecast_direct.parquet")
    if writeback:
        write_back(out, "retailer_sales_forecast", timestamp_col="__time")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v11d")
    ap.add_argument("--no-writeback", action="store_true")
    a = ap.parse_args()
    main(a.version, not a.no_writeback)
