"""MO_89 — Decomposition horse race: can anything separate growth trend from seasonality here?

WHY WE ARE HERE
---------------
Measured portfolio-wide on honest retrained holdouts, flat ("hold last week") beats our LightGBM
at EVERY aggregation level, and the gap WIDENS as you aggregate:

    level                      flat   MODEL
    SKU x retailer x week      32.0    35.1
    retailer x month           21.9    24.5
    portfolio x month          14.3    18.1
    portfolio x quarter        14.1    18.1

A gap that survives aggregation is not random noise — it is **systematic directional bias**.
That is the signature of a learner that cannot extrapolate a growing trend: it under-calls,
consistently, everywhere.

Confirmed mechanically. A gradient-boosted tree predicts a CONSTANT in each leaf, so it is a
lookup table with no slope term. It cannot continue a direction at any hyperparameter setting.
Verified: trained on targets to 60.1, max prediction 59.39 where the truth needed 80.17. In
Q1 2026, 292 of 957 series (30.5%) peaked above their own pre-cutoff max, carrying 39% of the
quarter's volume. And a plain 52-week linear fit beats the model on Q1 2026 by 21.7 points
(37.0 vs 58.7).

Exhausted already, all portfolio-confirmed negative: six seasonal feature arms (MO_86), two
families of target transform tried twice (MO_86/87), four objectives (MO_87 — tweedie's Kroger
win did NOT replicate portfolio-wide), tweedie variance power + monotone constraints + dynamic
momentum (MO_88), raw week_of_year (MO_85), TDP projection (MO_27g).

So the question is no longer "which knob" but "which decomposition". BUILT is a high-growth brand
with real annual seasonality (detrended year-over-year shape correlates +0.66; the Dec->Jan pivot
repeats at +0.112 and +0.107 in independent years). Classical decomposition exists precisely for
this shape of problem.

THE ARMS
--------
Baselines
  flat              hold the last observed value. The incumbent to beat: 32.0 / 14.3.
  seasonal_naive52  same week last year. Pure seasonality, no trend.
  lin52             52-week linear trend extrapolated. Pure trend, no seasonality.
  lightgbm          the current production model.

Classical decomposition — trend and seasonality separated explicitly
  AutoETS           automatic error/trend/seasonal selection. Multiplicative forms handle a
                    growing brand natively, which is exactly our failure mode.
  AutoTheta         Theta — repeatedly among the strongest performers in the M competitions.
  DynOptTheta       dynamic optimised Theta.
  AutoCES           complex exponential smoothing.
  MSTL              STL decomposition with an ETS trend forecast. Jason's preferred shape:
                    separate signal from noise, forecast the components, recombine.

The hybrid — each tool doing only what it is provably good at
  lin52_gbdt        fit a 52-week linear trend PER SERIES, subtract it, train LightGBM on the
                    RESIDUAL, add the trend back at forecast time.
                    The trend is computed once per series and never passes through the recursive
                    loop, so there is nothing to amplify — which is why this differs from the
                    ratio targets that exploded in MO_86/87.
                    Division of labour: the line supplies growth (trees structurally cannot);
                    LightGBM supplies seasonality, promo, price and cannibalization (a line
                    cannot). We have never combined them.

Scored at SKU x retailer x week AND at portfolio x month, because the business plans at the
latter and the two can disagree.

Run:  python MO_89_decomposition_horserace.py [--quarters 4] [--arms ...]
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

from mo_panel import (CAT_COLS, GROUP_COLS, fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_zero_volume_geographies, apply_rma_priority, drop_ak_hi_market_variants)

PARQUET  = Path("outputs/retailer_sales_weekly.parquet")
OUT_JSON = Path("outputs/mo89_decomposition_horserace.json")
HORIZON  = 13
SEASON   = 52
QUARTERS = [("Q4 2025", "2025-09-28"), ("Q1 2026", "2025-12-28"),
            ("Q2 2026", "2026-03-29"), ("Q3 2026", "2026-06-29")]
LGBM = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)
STAT_ARMS = {"AutoETS", "AutoTheta", "DynOptTheta", "AutoCES", "MSTL", "seasonal_naive52"}


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = np.abs(a).sum()
    return float(np.abs(a - p).sum() / d * 100) if d > 0 else float("nan")


def load_panel(feats):
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
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
    for fn in (fill_promo_mechanic_nulls, drop_military_accounts, drop_ak_hi_market_variants,
               apply_rma_priority):
        df = fn(df, verbose=False)
    df = drop_zero_volume_geographies(df, target="base_units", verbose=False)
    for c in CAT_COLS:
        if c in df.columns:
            df[c] = df[c].astype("category")
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


def trend_fit(y, win=SEASON):
    """Per-series linear trend on the last `win` observations. Returns (slope, intercept, n)."""
    k = min(win, len(y))
    if k < 8:
        return 0.0, float(y[-1]), k
    b = np.polyfit(np.arange(k), np.asarray(y[-k:], float), 1)
    return float(b[0]), float(b[1]), k


def run_stat_models(hist, keys, fw, arms):
    """statsforecast arms, fitted per series on pre-cutoff data only."""
    from statsforecast import StatsForecast
    from statsforecast.models import (AutoETS, AutoTheta, DynamicOptimizedTheta, AutoCES,
                                      MSTL, SeasonalNaive)
    recs = []
    for key, g in hist.groupby(GROUP_COLS, observed=True):
        if key not in keys:
            continue
        g = g.sort_values("__time")
        y = pd.to_numeric(g["base_units"], errors="coerce").fillna(0).values
        if len(y) < 8:
            continue
        uid = "|".join(map(str, key))
        for t, v in zip(g["__time"].values, y):
            recs.append({"unique_id": uid, "ds": t, "y": float(v)})
    if not recs:
        return {}
    sdf = pd.DataFrame(recs)
    sdf["ds"] = pd.to_datetime(sdf["ds"]).dt.tz_localize(None)
    # statsforecast requires a COMPLETE regular frequency grid per series. Our panel has gaps
    # (a SKU that stops selling at a retailer for a few weeks simply has no row), and passing
    # a ragged grid raises "could not broadcast input array from shape (11,) into shape (13,)".
    # Reindex every series onto its own full weekly range and fill gaps with 0 — a missing week
    # in SPINS means no recorded sales, which is genuinely zero for forecasting purposes.
    full = []
    for uid, g in sdf.groupby("unique_id", sort=False):
        g = g.sort_values("ds").drop_duplicates("ds")
        idx = pd.date_range(g["ds"].min(), g["ds"].max(), freq="W-SUN")
        if len(idx) < 8:
            continue
        r = (g.set_index("ds")["y"].reindex(idx).fillna(0.0)
             .rename_axis("ds").reset_index())
        r["unique_id"] = uid
        full.append(r[["unique_id", "ds", "y"]])
    if not full:
        return {}
    sdf = pd.concat(full, ignore_index=True)
    want = []
    if "AutoETS" in arms:      want.append(AutoETS(season_length=SEASON))
    if "AutoTheta" in arms:    want.append(AutoTheta(season_length=SEASON))
    if "DynOptTheta" in arms:  want.append(DynamicOptimizedTheta(season_length=SEASON))
    if "AutoCES" in arms:      want.append(AutoCES(season_length=SEASON))
    if "MSTL" in arms:         want.append(MSTL(season_length=SEASON))
    if "seasonal_naive52" in arms: want.append(SeasonalNaive(season_length=SEASON))
    if not want:
        return {}
    sf = StatsForecast(models=want, freq="W-SUN", n_jobs=-1, fallback_model=None)
    try:
        fc = sf.forecast(df=sdf, h=len(fw))
    except Exception as e:
        print(f"      statsforecast FAILED: {type(e).__name__}: {str(e)[:90]}")
        return {}
    fc = fc.reset_index() if "unique_id" not in fc.columns else fc
    name_map = {"AutoETS": "AutoETS", "AutoTheta": "AutoTheta",
                "DynamicOptimizedTheta": "DynOptTheta", "CES": "AutoCES",
                "AutoCES": "AutoCES", "MSTL": "MSTL", "SeasonalNaive": "seasonal_naive52"}
    out = {a: {} for a in arms if a in STAT_ARMS}
    # map each forecast step back to our real panel weeks by POSITION within each series,
    # not by date — the statsforecast grid is regular, our panel weeks may not be.
    fc = fc.sort_values(["unique_id", "ds"])
    fc["_step"] = fc.groupby("unique_id").cumcount()
    dmap = {i: fw[i] for i in range(len(fw))}
    for _, r in fc.iterrows():
        key = tuple(str(r["unique_id"]).split("|"))
        fd = dmap.get(int(r["_step"]))
        if fd is None:
            continue
        for col in fc.columns:
            arm = name_map.get(col)
            if arm and arm in out:
                v = r[col]
                if np.isfinite(v):
                    out[arm][(key, fd)] = max(0.0, float(v))
    return out


def main(nq, arms, trees):
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v11_full.pkl", "rb")).feature_name_)
    df = load_panel(feats)
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    print("MO_89 — decomposition horse race | FULL PORTFOLIO")
    print(f"  arms: {arms}")
    print(f"  incumbent to beat: flat 32.0 SKU-week / 14.3 portfolio-month\n")
    allrows = []
    for ql, qc in QUARTERS[:nq]:
        cut = pd.Timestamp(qc, tz="UTC")
        fw = list(weeks[weeks > cut][:HORIZON])
        hist = df[df["__time"] <= cut]
        fut = df[(df["__time"] > cut) & (df["__time"] <= fw[-1])]
        if fut.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 fut.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        keys = {k[0] for k in truth}
        print(f"  {ql} (cutoff {qc}) — {len(keys):,} series")
        P = {a: {} for a in arms}

        # ── per-series simple arms + trend fits ──
        tfit = {}
        for key, g in hist.groupby(GROUP_COLS, observed=True):
            if key not in keys:
                continue
            g = g.sort_values("__time")
            y = pd.to_numeric(g["base_units"], errors="coerce").fillna(0).values
            if len(y) < 4:
                continue
            sl, ic, k = trend_fit(y)
            tfit[key] = (sl, ic, k)
            for i, fd in enumerate(fw, 1):
                if "flat" in P:  P["flat"][(key, fd)] = float(y[-1])
                if "lin52" in P: P["lin52"][(key, fd)] = max(0.0, sl * (k - 1 + i) + ic)

        # ── statsforecast arms ──
        sa = [a for a in arms if a in STAT_ARMS]
        if sa:
            print(f"      fitting {sa} …")
            for a, d in run_stat_models(hist, keys, fw, sa).items():
                P[a] = d

        # ── LightGBM arms (plain, and trend-decomposed) ──
        for arm in [a for a in arms if a in ("lightgbm", "lin52_gbdt")]:
            tr = hist.copy()
            if arm == "lin52_gbdt":
                # subtract each series' own linear trend from the target
                tcol = np.full(len(tr), np.nan)
                for key, idx in tr.groupby(GROUP_COLS, observed=True).indices.items():
                    y = pd.to_numeric(tr["base_units"].iloc[idx], errors="coerce").fillna(0).values
                    sl, ic, k = trend_fit(y)
                    n = len(y)
                    pos = np.arange(n) - (n - k)      # align to the fitted window
                    tcol[idx] = sl * pos + ic
                tr["_trend"] = tcol
                y_tr = tr["base_units"].astype(float) - tr["_trend"]
            else:
                y_tr = np.log1p(tr["base_units"].astype(float))
            ok = np.isfinite(y_tr)
            tr, y_tr = tr[ok.values], y_tr[ok.values]
            age = ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0)
            m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=trees, **LGBM)
            m.fit(tr[feats], y_tr, sample_weight=np.exp(-0.02 * age).values)
            for key, g in hist.groupby(GROUP_COLS, observed=True):
                if key not in keys:
                    continue
                g = g.sort_values("__time")
                if len(g) < 4:
                    continue
                s_ = pd.to_numeric(g.set_index("__time")["base_units"], errors="coerce").fillna(0)
                h = list(s_.values); n = len(h)
                l52 = [float(h[n - 53 + i]) if 0 <= (n - 53 + i) < n else np.nan
                       for i in range(1, len(fw) + 1)]
                sl, ic, k = tfit.get(key, (0.0, float(h[-1]), min(SEASON, n)))
                st = g.iloc[-1].copy(); h2 = list(h)
                for i, fd in enumerate(fw):
                    t2 = float(fd.isocalendar().week)
                    st["week_sin"] = np.sin(2 * np.pi * t2 / 52)
                    st["week_cos"] = np.cos(2 * np.pi * t2 / 52)
                    st["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
                    st["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
                    st["base_units_lag1"]  = h2[-1]
                    st["base_units_lag4"]  = h2[-4]  if len(h2) >= 4  else np.nan
                    st["base_units_lag13"] = h2[-13] if len(h2) >= 13 else np.nan
                    st["base_units_lag52"] = l52[i]
                    X = pd.DataFrame([st])[feats]
                    for c, cc in cats.items():
                        if c in X.columns:
                            X[c] = pd.Categorical(X[c], categories=cc)
                    raw = float(m.predict(X)[0])
                    if arm == "lin52_gbdt":
                        p = max(0.0, (sl * (k - 1 + i + 1) + ic) + raw)   # trend back in
                    else:
                        p = float(np.clip(np.expm1(raw), 0, None))
                    h2.append(p); P[arm][(key, fd)] = p

        for (key, fd), tv in truth.items():
            r = {"q": ql, "upc": key[0], "acct": key[2], "t": fd, "actual": tv}
            for a in arms:
                r[a] = P.get(a, {}).get((key, fd), np.nan)
            allrows.append(r)

    J = pd.DataFrame(allrows)
    J["month"] = pd.to_datetime(J["t"]).dt.to_period("M")
    print(f"\n{'='*94}")
    print(f"  {len(J):,} matched points across {nq} quarters, full portfolio\n")
    levels = [("SKU x retailer x week", ["upc", "acct", "t"]),
              ("retailer x month", ["acct", "month"]),
              ("portfolio x month", ["month"])]
    print(f"  {'arm':<18s} " + "".join(f"{n:>22s}" for n, _ in levels))
    summary = {}
    for a in arms:
        if a not in J.columns or J[a].notna().sum() == 0:
            print(f"  {a:<18s} {'— no predictions —':>22s}")
            continue
        sub = J[J[a].notna()]
        cells, rec = "", {}
        for nm, kk in levels:
            g = sub.groupby(kk, observed=True)[["actual", a]].sum()
            v = wmape(g["actual"], g[a]); rec[nm] = v
            cells += f"{v:>22.1f}"
        summary[a] = rec
        print(f"  {a:<18s}{cells}")
    if summary:
        for nm, _ in levels:
            b = min(summary, key=lambda k: summary[k][nm])
            print(f"\n  BEST @ {nm:<22s} {b}  ({summary[b][nm]:.1f})")
    OUT_JSON.write_text(json.dumps(summary, indent=2, default=float))
    print(f"\n  → {OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarters", type=int, default=4)
    ap.add_argument("--trees", type=int, default=600)
    ap.add_argument("--arms", default="flat,lin52,lightgbm,lin52_gbdt,AutoETS,AutoTheta,"
                                      "DynOptTheta,MSTL,seasonal_naive52")
    a = ap.parse_args()
    main(a.quarters, [x.strip() for x in a.arms.split(",")], a.trees)
