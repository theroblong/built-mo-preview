"""MO_81 — The same forecast, scored at every aggregation level and by every common metric.

THE QUESTION
------------
BUILT's team reports ~7% forecast error. Our honest SKU x retailer x week 13-week backtest is
~37% wMAPE. Is a smart analyst with a spreadsheet really beating gradient boosting on three years
of history?

Almost certainly the two numbers are not measuring the same thing. This script takes ONE set of
predictions and scores it four ways, so the comparison can be made like-for-like instead of
argued about:

  LEVEL      SKU x retailer x week   (what MO_80 reports; the hardest possible cut)
             retailer x week         (sum SKUs)
             retailer x month        (sum SKUs and weeks)
             portfolio x month       (sum everything)

  METRIC     wMAPE  = sum|actual - forecast| / sum(actual)
             TOTAL  = |sum(forecast) - sum(actual)| / sum(actual)

TOTAL is the one that matters for this argument. It is what most companies mean by "forecast
error" when they quote a single low number, and it is a BIAS measure: offsetting SKU errors
cancel, so it is always <= wMAPE and usually far smaller. Reporting it as "accuracy" is not
dishonest, it is just a different question — "did we plan the right total volume" rather than
"did we get each item right".

Also reports error by horizon, because a single 13-week average hides that h=1 is a different
problem from h=13.

NOT CONTROLLED FOR HERE: shipments vs sell-through. BUILT forecasts what it ships; SPINS measures
what consumers buy. Shipments are smoother and partly under BUILT's own control, so that gap
cannot be closed by any amount of modelling on POS data — it has to be stated, not computed.

Run:  python MO_81_aggregation_level_error.py [--cutoff 2026-03-29] [--trees 800]
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
OUT_JSON = Path("outputs/mo81_aggregation_level_error.json")
HORIZON  = 13
RECENCY_LAMBDA = 0.02
LGBM = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = np.abs(a).sum()
    return float(np.abs(a - p).sum() / d * 100) if d > 0 else float("nan")


def total_err(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = a.sum()
    return float(abs(p.sum() - d) / d * 100) if d > 0 else float("nan")


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


def main(cutoff: str, trees: int, account: str | None):
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cut = pd.Timestamp(cutoff, tz="UTC")
    fweeks = list(weeks[weeks > cut][:HORIZON])
    print(f"MO_81 — one forecast, scored at four aggregation levels")
    print(f"  cutoff {cut.date()} | horizon {len(fweeks)} weeks "
          f"({fweeks[0].date()} .. {fweeks[-1].date()})")
    scope = df if account is None else df[df["retail_account"] == account]
    print(f"  scope: {'FULL PORTFOLIO' if account is None else account} "
          f"| {scope.groupby(GROUP_COLS, observed=True).ngroups:,} series\n")

    g = df.groupby(GROUP_COLS, observed=True)
    anchors = scope[scope["__time"] <= cut].groupby(GROUP_COLS, observed=True).tail(1)
    rows = []
    for h, fd in enumerate(fweeks, 1):
        d = df.copy()
        d["y"] = g["base_units"].shift(-h)
        d["t_target"] = d["__time"] + pd.Timedelta(weeks=h)
        tw = d["t_target"].dt.isocalendar().week.astype(float)
        d["week_sin"] = np.sin(2 * np.pi * tw / 52); d["week_cos"] = np.cos(2 * np.pi * tw / 52)
        d["week_sin26"] = np.sin(2 * np.pi * tw / 26); d["week_cos26"] = np.cos(2 * np.pi * tw / 26)
        tr = d.dropna(subset=["y"])
        tr = tr[tr["t_target"] <= cut]
        if len(tr) < 500:
            continue
        va = tr.tail(max(200, len(tr) // 10))
        m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=trees, **LGBM)
        m.fit(tr[feats], np.log1p(tr["y"]),
              eval_set=[(va[feats], np.log1p(va["y"]))], eval_metric="quantile",
              callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])
        X = anchors.copy()
        t2 = float(fd.isocalendar().week)
        X["week_sin"] = np.sin(2 * np.pi * t2 / 52); X["week_cos"] = np.cos(2 * np.pi * t2 / 52)
        X["week_sin26"] = np.sin(2 * np.pi * t2 / 26); X["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
        p = np.clip(np.expm1(m.predict(X[feats])), 0, None)
        for i, (_, r) in enumerate(X.iterrows()):
            rows.append({"upc": r["upc"], "retail_account": r["retail_account"],
                         "channel_outlet": r["channel_outlet"], "geography_raw": r["geography_raw"],
                         "__time": fd, "h": h, "pred": float(p[i])})
        print(f"    h={h:>2d} {fd.date()} trained")

    pred = pd.DataFrame(rows)
    act = scope[(scope["__time"] >= fweeks[0]) & (scope["__time"] <= fweeks[-1])][
        GROUP_COLS + ["__time", "base_units"]]
    j = act.merge(pred, on=GROUP_COLS + ["__time"], how="inner")
    print(f"\n  matched {len(j):,} (series x week) points, "
          f"{j['base_units'].sum():,.0f} actual units\n")

    j["month"] = j["__time"].dt.to_period("M")
    levels = {
        "SKU x retailer x week": GROUP_COLS + ["__time"],
        "retailer x week":       ["retail_account", "__time"],
        "retailer x month":      ["retail_account", "month"],
        "portfolio x month":     ["month"],
        "portfolio x quarter":   [],
    }
    print(f"  {'aggregation level':<24s} {'n':>7s} {'wMAPE':>8s} {'TOTAL err':>11s}")
    out = {"cutoff": str(cut.date()), "scope": account or "FULL_PORTFOLIO",
           "actual_units": float(j["base_units"].sum()), "levels": {}}
    for name, keys in levels.items():
        if keys:
            agg = j.groupby(keys, observed=True)[["base_units", "pred"]].sum()
            a, p = agg["base_units"].values, agg["pred"].values
        else:
            a = np.array([j["base_units"].sum()]); p = np.array([j["pred"].sum()])
        w, t = wmape(a, p), total_err(a, p)
        out["levels"][name] = {"n": int(len(a)), "wmape": w, "total_err": t}
        print(f"  {name:<24s} {len(a):>7,} {w:>8.1f} {t:>10.1f}%")

    print(f"\n  By horizon (SKU x retailer x week):")
    print(f"  {'h':>3s} {'n':>6s} {'wMAPE':>8s} {'TOTAL err':>11s}")
    out["by_horizon"] = {}
    for h, s in j.groupby("h"):
        w, t = wmape(s["base_units"], s["pred"]), total_err(s["base_units"], s["pred"])
        out["by_horizon"][int(h)] = {"wmape": w, "total_err": t, "n": int(len(s))}
        print(f"  {int(h):>3d} {len(s):>6,} {w:>8.1f} {t:>10.1f}%")

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\n  → {OUT_JSON}")
    print("\n  NOTE: 'TOTAL err' is |sum(forecast) - sum(actual)| / sum(actual) — a BIAS measure.")
    print("  It is what a single low 'forecast error' figure usually means, and offsetting")
    print("  item-level errors cancel inside it. Not comparable to wMAPE.")
    print("  NOT controlled for: shipments vs sell-through. BUILT forecasts what it ships;")
    print("  SPINS measures consumer takeaway. That gap cannot be closed by modelling POS.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", default="2026-03-29")
    ap.add_argument("--trees", type=int, default=800)
    ap.add_argument("--account", default=None)
    main(*vars(ap.parse_args()).values())
