"""MO_87 — Target transform x objective sweep. The two levers we have NEVER tested.

WHY THIS, AND WHY NOW
---------------------
A straight 52-week linear trend line beats our model on Q1 2026 by 21.7 points (37.0 vs 58.7).
Jason spotted it by eye on the Kroger chart. The data agrees, and the mechanism is specific:

  * production FREEZES every trend feature (`base_units_4wk_momentum`, `13wk_momentum`,
    `wow_delta`, all rolling means and z-scores) at the anchor row for the whole horizon. At a
    December cutoff the model's entire trend signal reads "declining," for all 13 weeks of the
    January-March ramp. A 52-week linear fit sees three years of growth; the model sees one
    stale December reading.
  * a constant-leaf GBDT also cannot predict beyond its training range (verified: trained to
    60.1, max prediction 59.39 where truth needed 80.17). In Q1 2026, 292 of 957 series (30.5%)
    peaked above their own pre-cutoff max, carrying 39.0% of the quarter's volume.

Six NATIVE fixes were tried in MO_86 — year-over-year differencing, a seasonal-ratio feature,
four Fourier harmonics, power-law weighting, no weighting. **All six lost to baseline on the
mean**, and none moved Q1 2026 by more than ~1pp. Notably `seasonal_diff` won two quarters big
and then blew up in Q2 2026 (80.4 vs 43.6), because `lag52 x exp(growth)` amplifies error wherever
the year-ago anchor is small or noisy.

So feature engineering is not the lever. These two are, and neither has ever been touched:

TARGET TRANSFORM — we have only ever trained on `log1p(units)`.
  log1p        current. Predicts a LEVEL, so the extrapolation ceiling binds directly.
  ratio13      `y_t / roll13_avg`. The level moves to the DENOMINATOR, so the target is a
               growth-invariant multiplier that stays in range however large the series gets.
               This is the robust cousin of MO_86's failed lag52 differencing: `roll13` is always
               available and never near zero, where `lag52` frequently is.
  ratio52      same idea on a 52-week base — slower-moving, more stable, less responsive.
  raw          no transform at all, as a control.

OBJECTIVE — we use `quantile(alpha=0.5)` by DEFAULT, never by evidence.
  quantile     current. Needed for q10/q90 bands, but nothing says it is right for q50.
  l2           plain squared error.
  huber        robust to the outlier weeks that pepper this panel.
  poisson      log-link, designed for count data. Demand IS counts.
  tweedie      log-link, handles the zero-inflated / intermittent weeks we have plenty of.
  mape         optimises RELATIVE error directly, which is what wMAPE measures.

⚠️ poisson/tweedie/l2/huber/mape all predict on their own link scale — each arm inverts its own
transform. Only `quantile` and `l2` are scale-free here.
⚠️ `monotone_constraints` is unusable with `quantile` (hard LightGBM error) but IS available with
tweedie/poisson — worth noting for later, not tested here.

Scored on the honest quarterly harness: both the model and every arm retrain at EVERY cutoff on
pre-cutoff data only, then run the full production recursive loop.

Baselines: production 37.9 mean / 58.7 Q1 2026 | flat 32.7 | lin52 46.1 mean but 37.0 on Q1 2026.

Run:  python MO_87_target_objective_sweep.py [--trees 600] [--stage targets|objectives|both]
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
OUT_JSON = Path("outputs/mo87_target_objective_sweep.json")
OUT_PORT = Path("outputs/mo87_portfolio_objectives.json")
HORIZON  = 13
BASE = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)
QUARTERS = [("Q1 2025", "2024-12-29"), ("Q2 2025", "2025-03-30"), ("Q3 2025", "2025-06-29"),
            ("Q4 2025", "2025-09-28"), ("Q1 2026", "2025-12-28"), ("Q2 2026", "2026-03-29"),
            ("Q3 2026", "2026-06-29")]

# (target, objective) combinations. Stage 1 holds the objective fixed and moves the target;
# stage 2 holds the winning target and moves the objective.
TARGETS    = ["log1p", "ratio13", "ratio52", "raw"]
OBJECTIVES = ["quantile", "l2", "poisson", "tweedie"]   # huber/mape dropped: huber lost, mape crashes


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
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    g = df.groupby(GROUP_COLS, observed=True)["base_units"]
    # Trailing bases (shift(1) first) so nothing peeks at the current week.
    df["_base13"] = g.transform(lambda s: s.shift(1).rolling(13, min_periods=4).mean())
    df["_base52"] = g.transform(lambda s: s.shift(1).rolling(52, min_periods=13).mean())
    return df


def make_target(tr, kind):
    y = tr["base_units"].astype(float)
    if kind == "log1p":
        return np.log1p(y), None
    if kind == "raw":
        return y, None
    base = tr["_base13"] if kind == "ratio13" else tr["_base52"]
    ok = base.notna() & (base > 0)
    return (y / base).where(ok), ok


def invert(pred, kind, base_val):
    if kind == "log1p":
        return float(np.clip(np.expm1(pred), 0, None))
    if kind == "raw":
        return float(max(0.0, pred))
    if base_val is None or not np.isfinite(base_val) or base_val <= 0:
        return float("nan")
    return float(max(0.0, pred * base_val))


def fit(X, y, w, objective, trees):
    kw = dict(BASE)
    if objective == "quantile":
        mdl = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=trees, **kw)
    elif objective == "l2":
        mdl = lgb.LGBMRegressor(objective="regression", n_estimators=trees, **kw)
    elif objective == "huber":
        mdl = lgb.LGBMRegressor(objective="huber", n_estimators=trees, **kw)
    elif objective == "poisson":
        mdl = lgb.LGBMRegressor(objective="poisson", n_estimators=trees, **kw)
    elif objective == "tweedie":
        mdl = lgb.LGBMRegressor(objective="tweedie", tweedie_variance_power=1.3,
                                n_estimators=trees, **kw)
    elif objective == "mape":
        mdl = lgb.LGBMRegressor(objective="mape", n_estimators=trees, **kw)
    else:
        raise ValueError(objective)
    mdl.fit(X, y, sample_weight=w)
    return mdl


def run_combo(df, feats, cats, ev, weeks, target, objective, trees):
    """Score one (target, objective) pair across all quarters."""
    out = {}
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
        keys = {k[0] for k in truth}
        y, ok = make_target(hist_all, target)
        tr = hist_all if ok is None else hist_all[ok.fillna(False)]
        yv = y if ok is None else y[ok.fillna(False)]
        m = yv.notna() & np.isfinite(yv)
        tr, yv = tr[m.values], yv[m.values]
        # poisson/tweedie require a non-negative target
        if objective in ("poisson", "tweedie", "mape") and (yv < 0).any():
            tr, yv = tr[yv >= 0], yv[yv >= 0]
        if len(tr) < 500:
            continue
        age = ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0)
        try:
            mdl = fit(tr[feats], yv, np.exp(-0.02 * age).values, objective, trees)
        except Exception as e:
            out[ql] = {"error": f"{type(e).__name__}: {str(e)[:70]}"}
            continue
        preds = {}
        for key, g in hist_all[ev.reindex(hist_all.index, fill_value=False)].groupby(
                GROUP_COLS, observed=True):
            if key not in keys:
                continue
            g = g.sort_values("__time")
            if len(g) < 4:
                continue
            s_ = pd.to_numeric(g.set_index("__time")["base_units"], errors="coerce").fillna(0)
            hist = list(s_.values); n = len(hist)
            lag52_seq = [float(hist[n - 53 + i]) if 0 <= (n - 53 + i) < n else np.nan
                         for i in range(1, len(fw) + 1)]
            state = g.iloc[-1].copy(); h2 = list(hist)
            arp_h = list(pd.to_numeric(g["arp"], errors="coerce").ffill().values)
            for i, fd in enumerate(fw):
                t2 = float(fd.isocalendar().week)
                state["week_sin"] = np.sin(2 * np.pi * t2 / 52)
                state["week_cos"] = np.cos(2 * np.pi * t2 / 52)
                state["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
                state["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
                state["base_units_lag1"]  = h2[-1]
                state["base_units_lag4"]  = h2[-4]  if len(h2) >= 4  else np.nan
                state["base_units_lag13"] = h2[-13] if len(h2) >= 13 else np.nan
                state["base_units_lag52"] = lag52_seq[i]
                if arp_h:
                    _ac = arp_h[-1]; _aw = arp_h[-8:]
                    state["arp"] = _ac
                    state["arp_lag1"] = arp_h[-2] if len(arp_h) >= 2 else _ac
                    state["arp_roll8_avg"] = float(np.nanmean(_aw))
                    state["arp_roll8_std"] = float(np.nanstd(_aw)) if len(_aw) > 1 else 0.0
                    state["arp_wow_delta"] = 0.0
                X = pd.DataFrame([state])[feats]
                for c, cc in cats.items():
                    if c in X.columns:
                        X[c] = pd.Categorical(X[c], categories=cc)
                raw = float(mdl.predict(X)[0])
                # the ratio base advances with the forecast — it is the model's own recent level
                bval = (float(np.mean(h2[-13:])) if target == "ratio13"
                        else float(np.mean(h2[-52:])) if target == "ratio52" else None)
                p = invert(raw, target, bval)
                if not np.isfinite(p):
                    p = h2[-1]
                h2.append(p); preds[(key, fd)] = p
        ks = [k for k in truth if k in preds]
        if ks:
            a = np.array([truth[k] for k in ks]); p = np.array([preds[k] for k in ks])
            out[ql] = {"wmape": wmape(a, p),
                       "bias": float(p.sum() / a.sum()) if a.sum() else float("nan")}
    return out


def main(trees, stage, account, channel):
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v11_full.pkl", "rb")).feature_name_)
    df = load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    if account is None:
        ev = pd.Series(True, index=df.index)
        scope = "FULL PORTFOLIO"
    else:
        ev = (df["retail_account"] == account) & (df["channel_outlet"] == channel)
        scope = f"{account} {channel}"
    print(f"MO_87 — target x objective sweep | {scope}")
    print(f"  baselines: production 37.9 mean / 58.7 Q1'26 | flat 32.7 | lin52 46.1 mean / 37.0 Q1'26\n")
    results = {}
    qnames = [q for q, _ in QUARTERS]

    def report(label, res):
        vals = [res[q]["wmape"] for q in qnames if q in res and "wmape" in res[q]]
        q1 = res.get("Q1 2026", {}).get("wmape")
        cells = " ".join(f"{res[q]['wmape']:>6.1f}" if q in res and 'wmape' in res[q] else f"{'err':>6s}"
                         for q in qnames)
        mean = float(np.mean(vals)) if vals else float("nan")
        print(f"  {label:<22s} {cells} {mean:>7.1f}")
        return {"per_quarter": {q: res[q].get("wmape") for q in qnames if q in res},
                "mean_wmape": mean, "q1_2026": q1}

    print(f"  {'arm':<22s} " + " ".join(f"{q.split()[0]+q.split()[1][-2:]:>6s}" for q in qnames) + f" {'MEAN':>7s}")
    if stage in ("targets", "both"):
        for t in TARGETS:
            results[f"target:{t}"] = report(f"target={t}",
                                            run_combo(df, feats, cats, ev, weeks, t, "quantile", trees))
    if stage in ("objectives", "both"):
        for o in OBJECTIVES:
            results[f"obj:{o}"] = report(f"obj={o}",
                                         run_combo(df, feats, cats, ev, weeks, "log1p", o, trees))

    ok = {k: v for k, v in results.items() if np.isfinite(v.get("mean_wmape", np.nan))}
    if ok:
        bm = min(ok, key=lambda k: ok[k]["mean_wmape"])
        bq = min((k for k in ok if ok[k].get("q1_2026")), key=lambda k: ok[k]["q1_2026"])
        print(f"\n  BEST MEAN    : {bm} at {ok[bm]['mean_wmape']:.1f}   (production 37.9)")
        print(f"  BEST Q1 2026 : {bq} at {ok[bq]['q1_2026']:.1f}   (production 58.7, lin52 37.0)")
    (OUT_PORT if account is None else OUT_JSON).write_text(json.dumps(results, indent=2, default=float))
    print(f"\n  → {OUT_PORT if account is None else OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=600)
    ap.add_argument("--stage", default="both", choices=["targets", "objectives", "both"])
    ap.add_argument("--account", default="KROGER")
    ap.add_argument("--channel", default="CONVENTIONAL|FOOD")
    ap.add_argument("--portfolio", action="store_true",
                    help="evaluate on the FULL panel, not one retailer/channel")
    a = ap.parse_args()
    main(a.trees, a.stage, None if a.portfolio else a.account, a.channel)
