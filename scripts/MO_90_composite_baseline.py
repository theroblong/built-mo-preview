"""MO_90 — Estimate each component where it IS estimable. The composite baseline.

THE CONSTRAINT WE DISCOVERED
----------------------------
At the Q4 2025 cutoff, **zero series have 104+ weeks of history**. The panel starts 2023-10-15,
so the maximum possible history is 103 weeks — just under TWO annual cycles.

    <26 wks   539 series
    26-51     246
    52-103    370
    >=104       0      <- every classical seasonal method needs this

That is why ETS / Theta / MSTL / SARIMA could not even fit (statsforecast raised a broadcast
error rather than a result), why seasonal features earn only ~4% of model gain, and why every
seasonal fix we tried failed. We were trying to extract a per-series signal that is not yet
estimable from this panel.

It also explains why flat wins: with under two cycles, "this week" genuinely is the best available
estimate of next week.

THE IDEA THIS TESTS
-------------------
Individual series cannot support annual seasonality. **The portfolio can** — 152 weeks pooled is
2.9 cycles, and the detrended year-over-year shape correlates +0.66 with a Dec->Jan pivot that
repeats at +0.112 and +0.107 in independent years.

So estimate each component at the level where it is actually measurable, instead of asking one
model to learn all three per series:

    level         PER SERIES   — flat wins outright (32.0 SKU-week / 14.3 portfolio-month)
    trend         PORTFOLIO    — BUILT grew 4.01x then 1.63x; per-series trend is far too noisy
                                 (lin52 scored 61.3, worse than everything)
    seasonality   PORTFOLIO    — +0.66 detrended YoY correlation; unusable per series

        forecast[s, t] = last_value[s] x growth^h x (seas[woy(t)] / seas[woy(anchor)])

Everything is fitted on PRE-CUTOFF data only. The seasonal index is detrended with a TRAILING
window (never centred — that would peek ahead).

ARMS
----
  flat                  hold last observed value — the incumbent
  flat_x_seas           flat x pooled seasonal ratio
  flat_x_growth         flat x pooled growth
  flat_x_seas_x_growth  both
  SES_opt               simple exponential smoothing, optimised alpha — no seasonality, so it
                        fits on short history where ETS/Theta cannot
  Holt_damped           damped linear trend, no seasonality
  AutoETS_ns            AutoETS with season_length=1 (non-seasonal, so it will actually fit)
  AutoTheta_ns          Theta with season_length=1
  lightgbm              reference

Prior results for context: Ridge 60-81 and Lasso 57-80 (MO_38) — regularised linear regression on
the feature set is far worse than naive. N-BEATS 46-118 (MO_32A), also losing to naive.

Run:  python MO_90_composite_baseline.py [--quarters 4]
"""
from __future__ import annotations

import argparse
import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from mo_panel import (GROUP_COLS, fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_zero_volume_geographies, apply_rma_priority, drop_ak_hi_market_variants)

PARQUET  = Path("outputs/retailer_sales_weekly.parquet")
OUT_JSON = Path("outputs/mo90_composite_baseline.json")
HORIZON  = 13
QUARTERS = [("Q1 2025", "2024-12-29"), ("Q2 2025", "2025-03-30"), ("Q3 2025", "2025-06-29"),
            ("Q4 2025", "2025-09-28"), ("Q1 2026", "2025-12-28"), ("Q2 2026", "2026-03-29"),
            ("Q3 2026", "2026-06-29")]
ARMS = ["flat", "flat_x_seas", "flat_x_growth", "flat_x_seas_x_growth",
        "SES_opt", "Holt_damped", "AutoETS_ns", "AutoTheta_ns"]


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = np.abs(a).sum()
    return float(np.abs(a - p).sum() / d * 100) if d > 0 else float("nan")


def load_panel():
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df["base_units"] = pd.to_numeric(df["base_units"], errors="coerce")
    df = df.dropna(subset=["base_units"])
    for fn in (fill_promo_mechanic_nulls, drop_military_accounts, drop_ak_hi_market_variants,
               apply_rma_priority):
        df = fn(df, verbose=False)
    df = drop_zero_volume_geographies(df, target="base_units", verbose=False)
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


def portfolio_components(hist):
    """Pooled seasonal index and weekly growth rate, from PRE-CUTOFF data only.

    The index is detrended with a TRAILING rolling mean so nothing peeks ahead: at forecast time
    only past weeks are available, and a centred window would use the future.
    """
    wk = hist.groupby("__time")["base_units"].sum().sort_index()
    if len(wk) < 60:
        return {}, 1.0
    trend = wk.rolling(52, min_periods=26).mean()          # trailing, not centred
    ratio = (wk / trend).dropna()
    woy = ratio.index.isocalendar().week.astype(int)
    seas = ratio.groupby(woy.values).mean()
    seas = seas.reindex(range(1, 54)).interpolate().bfill().ffill()
    seas = seas / seas.mean()
    # weekly growth from a log-linear fit on the last 52 portfolio weeks
    tail = wk.tail(52)
    g = 1.0
    if len(tail) >= 26 and (tail > 0).all():
        b = np.polyfit(np.arange(len(tail)), np.log(tail.values), 1)
        g = float(np.exp(b[0]))
        g = float(np.clip(g, 0.98, 1.03))                  # cap: +-1.5x/yr, guards runaway
    return {int(k): float(v) for k, v in seas.items()}, g


def stat_forecasts(hist, keys, h, arms):
    """Non-seasonal statsforecast models — these FIT on short history, unlike seasonal ones."""
    out = {a: {} for a in arms}
    try:
        from statsforecast import StatsForecast
        from statsforecast.models import (SimpleExponentialSmoothingOptimized, Holt,
                                          AutoETS, AutoTheta)
    except Exception as e:
        print(f"      statsforecast unavailable: {e}")
        return out
    recs = []
    for key, g in hist.groupby(GROUP_COLS, observed=True):
        if key not in keys:
            continue
        g = g.sort_values("__time")
        y = pd.to_numeric(g["base_units"], errors="coerce").fillna(0).values
        if len(y) < 10:
            continue
        uid = "|".join(map(str, key))
        idx = pd.date_range(g["__time"].min().tz_localize(None),
                            g["__time"].max().tz_localize(None), freq="W-SUN")
        s = (pd.Series(y, index=pd.DatetimeIndex(g["__time"].dt.tz_localize(None)))
             .reindex(idx).fillna(0.0))
        for t, v in s.items():
            recs.append({"unique_id": uid, "ds": t, "y": float(v)})
    if not recs:
        return out
    sdf = pd.DataFrame(recs)
    models, names = [], []
    if "SES_opt" in arms:
        models.append(SimpleExponentialSmoothingOptimized()); names.append("SES_opt")
    if "Holt_damped" in arms:
        models.append(AutoETS(season_length=1, damped=True)); names.append("Holt_damped")
    if "AutoETS_ns" in arms:
        models.append(AutoETS(season_length=1)); names.append("AutoETS_ns")
    if "AutoTheta_ns" in arms:
        models.append(AutoTheta(season_length=1)); names.append("AutoTheta_ns")
    if not models:
        return out
    try:
        sf = StatsForecast(models=models, freq="W-SUN", n_jobs=-1)
        fc = sf.forecast(df=sdf, h=h).reset_index()
    except Exception as e:
        print(f"      statsforecast FAILED: {type(e).__name__}: {str(e)[:90]}")
        return out
    fc = fc.sort_values(["unique_id", "ds"])
    fc["_step"] = fc.groupby("unique_id").cumcount()
    cols = [c for c in fc.columns if c not in ("unique_id", "ds", "_step")]
    for _, r in fc.iterrows():
        key = tuple(str(r["unique_id"]).split("|"))
        st = int(r["_step"])
        for c, nm in zip(cols, names[:len(cols)]):
            v = r[c]
            if np.isfinite(v):
                out[nm][(key, st)] = max(0.0, float(v))
    return out


def main(nq, arms):
    df = load_panel()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    print("MO_90 — composite baseline: estimate each component where it IS estimable")
    print("  incumbent: flat 32.0 SKU-week / 14.3 portfolio-month (4-quarter portfolio run)\n")
    rows = []
    for ql, qc in QUARTERS[:nq]:
        cut = pd.Timestamp(qc, tz="UTC")
        fw = list(weeks[weeks > cut][:HORIZON])
        if not fw:
            continue
        hist = df[df["__time"] <= cut]
        fut = df[(df["__time"] > cut) & (df["__time"] <= fw[-1])]
        if fut.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 fut.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        keys = {k[0] for k in truth}
        seas, growth = portfolio_components(hist)
        anchor_woy = int(cut.isocalendar().week)
        s_anchor = seas.get(anchor_woy, 1.0) or 1.0
        print(f"  {ql}: {len(keys):,} series | portfolio growth {growth:.4f}/wk "
              f"({growth**52:.2f}x/yr) | seasonal index {len(seas)} weeks")
        sp = stat_forecasts(hist, keys, len(fw),
                            [a for a in arms if a in ("SES_opt", "Holt_damped",
                                                      "AutoETS_ns", "AutoTheta_ns")])
        for key, g in hist.groupby(GROUP_COLS, observed=True):
            if key not in keys:
                continue
            g = g.sort_values("__time")
            y = pd.to_numeric(g["base_units"], errors="coerce").fillna(0).values
            if len(y) < 4:
                continue
            lv = float(y[-1])
            for i, fd in enumerate(fw):
                woy = int(fd.isocalendar().week)
                sr = (seas.get(woy, 1.0) or 1.0) / s_anchor
                gr = growth ** (i + 1)
                r = {"q": ql, "upc": key[0], "acct": key[2], "t": fd,
                     "actual": truth.get((key, fd), np.nan)}
                r["flat"] = lv
                r["flat_x_seas"] = lv * sr
                r["flat_x_growth"] = lv * gr
                r["flat_x_seas_x_growth"] = lv * sr * gr
                for nm in ("SES_opt", "Holt_damped", "AutoETS_ns", "AutoTheta_ns"):
                    r[nm] = sp.get(nm, {}).get((key, i), np.nan)
                rows.append(r)
    J = pd.DataFrame(rows).dropna(subset=["actual"])
    J["month"] = pd.to_datetime(J["t"]).dt.to_period("M")
    print(f"\n{'='*86}\n  {len(J):,} matched points, {nq} quarters, full portfolio\n")
    levels = [("SKU x retailer x week", ["upc", "acct", "t"]),
              ("retailer x month", ["acct", "month"]),
              ("portfolio x month", ["month"])]
    print(f"  {'arm':<22s} " + "".join(f"{n:>22s}" for n, _ in levels))
    summ = {}
    for a in arms:
        if a not in J.columns or J[a].notna().sum() == 0:
            print(f"  {a:<22s} {'— no predictions —':>22s}"); continue
        sub = J[J[a].notna()]
        cells, rec = "", {}
        for nm, kk in levels:
            gg = sub.groupby(kk, observed=True)[["actual", a]].sum()
            v = wmape(gg["actual"], gg[a]); rec[nm] = v; cells += f"{v:>22.1f}"
        summ[a] = rec
        print(f"  {a:<22s}{cells}")
    for nm, _ in levels:
        ok = {k: v for k, v in summ.items() if np.isfinite(v.get(nm, np.nan))}
        if ok:
            b = min(ok, key=lambda k: ok[k][nm])
            base = ok.get("flat", {}).get(nm)
            d = f"  ({ok[b][nm]-base:+.1f}pp vs flat)" if base else ""
            print(f"\n  BEST @ {nm:<22s} {b}  ({ok[b][nm]:.1f}){d}")
    OUT_JSON.write_text(json.dumps(summ, indent=2, default=float))
    print(f"\n  → {OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarters", type=int, default=4)
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args()
    main(a.quarters, [x.strip() for x in a.arms.split(",")])
