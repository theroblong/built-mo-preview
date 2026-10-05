#!/usr/bin/env python
"""MO_100 - rebuild the seasonal index at the level where the signal actually lives.

The earlier verdict that "seasonality does not repeat" was measured on WEEKLY
shape PER SERIES and returned a median year-over-year correlation of +0.079. That
was the wrong granularity: at individual-series weekly resolution this brand is
mostly noise. Measured on the MONTHLY AGGREGATE the signal is clear and stable:

    month-shape correlation   2024 vs 2025  +0.434
                              2024 vs 2026  +0.385
                              2025 vs 2026  +0.704

    March  +0.155 / +0.375 / +0.297  -> positive in ALL THREE years, ~1.32x
    Dec    -0.219 / -0.029 / -0.236  -> negative in ALL THREE years, ~0.85x

That independently reproduces the documented "March peak +30%". So the seasonal
capability should be REBUILT, not removed — which is what Jason argued.

What this fixes versus the live MO_59 index:
  - **Reproducible.** The live mo59 CSV was found to be stale and not reproducible
    from any recorded recipe. This script is the recipe.
  - **Monthly, pooled, volume-weighted** by construction (it sums units across all
    series), instead of per-series weekly argmax, which was unstable on a bimodal
    curve.
  - **Shrunk.** With only 2-3 observations per calendar month, a raw mean is noisy.
    Each month is shrunk toward 1.0 by its own evidence: months that disagree
    across years, or have fewer observations, move less.
  - **Cutoff-aware, so backtests stop leaking.** The index can be built from data
    <= a cutoff. The live index is built on ALL data and then used inside
    backtests of earlier periods, which leaks the future into the seasonal factor.

Output is a week_of_year -> multiplicative index, matching what MO_27 consumes,
interpolated from the monthly curve rather than estimated weekly.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from mo_panel import (GROUP_COLS, apply_rma_priority, drop_ak_hi_market_variants,
                      drop_military_accounts, drop_zero_volume_geographies,
                      fill_promo_mechanic_nulls)

PARQUET = "outputs/retailer_sales_weekly.parquet"
OUT_CSV = Path("outputs/mo100_seasonal_index.csv")
OUT_JSON = Path("outputs/mo100_seasonal_index_meta.json")
SHRINK_K = 1.5          # months with fewer/noisier observations shrink toward 1.0
MIN_WEEKS_IN_MONTH = 4  # a month counts only if it has >= this many panel weeks


def load_panel() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df["base_units"] = pd.to_numeric(df["base_units"], errors="coerce")
    for fn in (fill_promo_mechanic_nulls, drop_military_accounts,
               drop_ak_hi_market_variants, apply_rma_priority):
        df = fn(df, verbose=False)
    df = drop_zero_volume_geographies(df, target="base_units", verbose=False)
    return df.dropna(subset=["base_units"])


def monthly_index(df: pd.DataFrame, cutoff: pd.Timestamp | None = None, verbose=True):
    """Pooled monthly seasonal index from data <= cutoff. Returns (index, detail)."""
    d = df if cutoff is None else df[df["__time"] <= cutoff]
    d = d.copy()
    d["ym"] = d["__time"].dt.to_period("M")
    weeks = d.groupby("ym")["__time"].nunique()
    full = set(weeks[weeks >= MIN_WEEKS_IN_MONTH].index)
    d = d[d["ym"].isin(full)]
    m = d.groupby("ym")["base_units"].sum().sort_index()
    if len(m) < 14:
        if verbose:
            print(f"  only {len(m)} full months <= cutoff — index not estimable")
        return None, None

    # detrend: 13-month centered rolling mean on log volume
    lg = np.log(m)
    trend = lg.rolling(13, center=True, min_periods=7).mean()
    resid = (lg - trend).dropna()

    T = pd.DataFrame({"m": [x.month for x in resid.index],
                      "yr": [x.year for x in resid.index],
                      "r": resid.values})
    out = {}
    for mo, g in T.groupby("m"):
        n = len(g)
        mu = float(g["r"].mean())
        sd = float(g["r"].std(ddof=0)) if n > 1 else 1.0
        # shrink toward 0 (index 1.0): more observations and tighter agreement -> less shrink
        w = n / (n + SHRINK_K * (1.0 + sd))
        out[mo] = {"n": n, "raw_mean": mu, "sd": sd, "weight": w,
                   "shrunk": mu * w, "index": float(np.exp(mu * w))}
    return out, T


def to_weekly(idx: dict) -> pd.DataFrame:
    """Interpolate the monthly curve onto week_of_year, circularly."""
    # anchor each month at its middle week
    anchors = []
    for mo, v in sorted(idx.items()):
        mid = pd.Timestamp(2025, mo, 15)
        anchors.append((float(mid.isocalendar().week), v["index"]))
    anchors.sort()
    w = np.array([a[0] for a in anchors])
    y = np.array([a[1] for a in anchors])
    # wrap for circular interpolation
    w_ext = np.r_[w - 52.0, w, w + 52.0]
    y_ext = np.r_[y, y, y]
    weeks = np.arange(1, 54)
    vals = np.interp(weeks, w_ext, y_ext)
    vals = vals / np.average(vals)        # renormalize so the year averages 1.0
    return pd.DataFrame({"week_of_year": weeks, "seasonal_index": vals})


def main() -> None:
    df = load_panel()
    print("MO_100 - pooled monthly seasonal index\n")
    idx, T = monthly_index(df)
    if idx is None:
        raise SystemExit("not estimable")

    names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
             7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
    print(f"  {'month':<6s} {'n yrs':>5s} {'raw':>8s} {'sd':>7s} {'shrink w':>9s} "
          f"{'index':>7s}  per-year residuals")
    for mo in sorted(idx):
        v = idx[mo]
        yrs = T[T.m == mo].sort_values("yr")
        print(f"  {names[mo]:<6s} {v['n']:>5d} {v['raw_mean']:>+8.3f} {v['sd']:>7.3f} "
              f"{v['weight']:>9.2f} {v['index']:>7.2f}x  "
              + " ".join(f"{r.yr}:{r.r:+.3f}" for r in yrs.itertuples()))

    wk = to_weekly(idx)
    wk.to_csv(OUT_CSV, index=False)
    peak = wk.loc[wk.seasonal_index.idxmax()]
    trough = wk.loc[wk.seasonal_index.idxmin()]
    print(f"\n  weekly curve: peak wk {int(peak.week_of_year)} ({peak.seasonal_index:.3f}), "
          f"trough wk {int(trough.week_of_year)} ({trough.seasonal_index:.3f})")
    print(f"  amplitude peak/trough = {peak.seasonal_index/trough.seasonal_index:.2f}x")

    # stability: leave-one-year-out
    print("\n  Leave-one-year-out stability (does one year drive the curve?)")
    yrs = sorted(T.yr.unique())
    base = np.array([idx[m]["index"] for m in sorted(idx)])
    for drop in yrs:
        sub = T[T.yr != drop]
        alt = {}
        for mo, g in sub.groupby("m"):
            n = len(g); mu = float(g["r"].mean())
            sd = float(g["r"].std(ddof=0)) if n > 1 else 1.0
            alt[mo] = float(np.exp(mu * (n / (n + SHRINK_K * (1.0 + sd)))))
        common = sorted(set(alt) & set(idx))
        a = np.array([alt[m] for m in common]); b = np.array([idx[m]["index"] for m in common])
        print(f"    without {drop}: corr {np.corrcoef(a,b)[0,1]:+.3f}  "
              f"max month shift {np.abs(a-b).max():.3f}")

    OUT_JSON.write_text(json.dumps({
        "built_at": str(pd.Timestamp.utcnow()),
        "panel_end": str(df["__time"].max().date()),
        "shrink_k": SHRINK_K,
        "monthly": {str(k): v for k, v in idx.items()},
        "method": "log monthly aggregate, 13-mo centered rolling detrend, "
                  "per-month mean shrunk toward 1.0, interpolated to week_of_year",
    }, indent=2, default=str))
    print(f"\nwrote {OUT_CSV}\nwrote {OUT_JSON}")


if __name__ == "__main__":
    main()
