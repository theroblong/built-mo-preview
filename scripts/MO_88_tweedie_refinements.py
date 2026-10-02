"""MO_88 — Three changes on top of the tweedie winner: dynamic momentum, variance power, monotonicity.

WHERE WE ARE
------------
MO_87 found the first real win of the project by turning a knob nobody had turned: the OBJECTIVE.
We had used `quantile(alpha=0.5)` since the beginning by default, never by evidence.

  quantile 38.0 (shipping) | l2 37.1 | huber 42.4 | poisson 36.4 | TWEEDIE 35.8 | mape 35.4*
  tweedie on Q1 2026: 50.5 vs quantile's 58.5  (-8.0pp)

  *mape's figure is over SIX quarters — it crashed on Q2 2025. On equal footing tweedie 34.85
   beats mape 35.42, poisson 35.58 and quantile 37.55.

Everything else tried has failed: six native seasonal arms (MO_86), two families of target
transform tried twice over (ratio13 54.0, ratio52 50.7, seasonal_diff 43.6 — all blow up when a
ratio is fed back through the recursive loop), raw `week_of_year` (MO_85), TDP projection (MO_27g).

THE REMAINING DIAGNOSED DEFECT
------------------------------
A 52-week linear trend line beats the model on Q1 2026 by 21.7 points — 37.0 vs 58.7 — which
Jason spotted by eye on the Kroger chart. The cause is mechanical and still unfixed: production
FREEZES every trend feature at the anchor row for the whole 13-week horizon:

    base_units_roll4_avg / roll8_avg / roll13_avg / roll8_std / roll13_std
    base_units_z8 / z13 / 4wk_momentum / 13wk_momentum

At a December cutoff that means the model is shown a declining December reading for every week of
the January-March ramp, while a linear fit sees three years of growth. Measured in isolation,
unfreezing them was worth **+6.2pp on Q1 2026** (56.9 -> 50.7) but cost 3-9pp in stable quarters,
because there the recomputed values just measure the model's own drift. Arm 2 retests that on top
of tweedie rather than on top of quantile.

ARMS
----
  tweedie_base        the MO_87 winner as-is (variance_power 1.3, momentum frozen)
  tweedie_dynamic_mom momentum/rolling/z features ADVANCE each recursive step
  tweedie_p1.1/1.5/1.7 `tweedie_variance_power` sweep — 1.3 was chosen arbitrarily and it is a real
                      hyperparameter. ->1 approaches Poisson, ->2 approaches Gamma.
  tweedie_mono_lag52  monotone constraint forcing `base_units_lag52` to push predictions UP.
                      This was impossible under quantile (LightGBM errors outright); tweedie
                      permits it. If the model will not use the year-ago signal voluntarily — it
                      ranks 33rd of 56 — this makes it.

Scored on the honest quarterly harness; every arm retrains at EVERY cutoff on pre-cutoff data only
and then runs the full production recursive loop.

Baselines: quantile 38.0 mean / 58.5 Q1'26 | tweedie 35.8 / 50.5 | flat 32.7 | lin52 46.1 / 37.0.

Run:  python MO_88_tweedie_refinements.py [--trees 600]
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
OUT_JSON = Path("outputs/mo88_tweedie_refinements.json")
OUT_PORT = Path("outputs/mo88_portfolio.json")
HORIZON  = 13
BASE = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)
QUARTERS = [("Q1 2025", "2024-12-29"), ("Q2 2025", "2025-03-30"), ("Q3 2025", "2025-06-29"),
            ("Q4 2025", "2025-09-28"), ("Q1 2026", "2025-12-28"), ("Q2 2026", "2026-03-29"),
            ("Q3 2026", "2026-06-29")]

# (target, objective) combinations. Stage 1 holds the objective fixed and moves the target;
# stage 2 holds the winning target and moves the objective.
ARMS = ["tweedie_base", "tweedie_dynamic_mom", "tweedie_p1.1", "tweedie_p1.5",
        "tweedie_p1.7", "tweedie_mono_lag52"]


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


def fit(X, y, w, arm, trees, feats=None):
    kw = dict(BASE)
    power = {"tweedie_p1.1": 1.1, "tweedie_p1.5": 1.5, "tweedie_p1.7": 1.7}.get(arm, 1.3)
    if arm == "tweedie_mono_lag52":
        # Only available because we moved off quantile — LightGBM refuses monotone_constraints
        # with the quantile objective. 1 = this feature may only push the prediction UP.
        mc = [1 if f == "base_units_lag52" else 0 for f in feats]
        kw["monotone_constraints"] = mc
        kw["monotone_constraints_method"] = "advanced"   # least over-constraining per the docs
    mdl = lgb.LGBMRegressor(objective="tweedie", tweedie_variance_power=power,
                            n_estimators=trees, **kw)
    mdl.fit(X, y, sample_weight=w)
    return mdl


def _unused(X, y, w, objective, trees):
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


def run_combo(df, feats, cats, ev, weeks, arm, trees):
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
        y, ok = make_target(hist_all, "log1p")
        tr = hist_all if ok is None else hist_all[ok.fillna(False)]
        yv = y if ok is None else y[ok.fillna(False)]
        m = yv.notna() & np.isfinite(yv)
        tr, yv = tr[m.values], yv[m.values]
        # poisson/tweedie require a non-negative target
        if (yv < 0).any():
            tr, yv = tr[yv >= 0], yv[yv >= 0]
        if len(tr) < 500:
            continue
        age = ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0)
        try:
            mdl = fit(tr[feats], yv, np.exp(-0.02 * age).values, arm, trees, feats)
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
                if arm == "tweedie_dynamic_mom":
                    _w8, _w13 = h2[-8:], h2[-13:]
                    _m8 = float(np.mean(_w8)); _s8 = float(np.std(_w8)) if len(_w8) > 1 else 0.0
                    _m13 = float(np.mean(_w13)); _s13 = float(np.std(_w13)) if len(_w13) > 1 else 0.0
                    state["base_units_roll4_avg"] = float(np.mean(h2[-4:]))
                    state["base_units_roll8_avg"] = _m8
                    state["base_units_roll13_avg"] = _m13
                    state["base_units_roll8_std"] = _s8
                    state["base_units_roll13_std"] = _s13
                    state["base_units_z8"] = (h2[-1] - _m8) / _s8 if _s8 > 0 else 0.0
                    state["base_units_z13"] = (h2[-1] - _m13) / _s13 if _s13 > 0 else 0.0
                    state["base_units_wow_delta"] = h2[-1] - h2[-2] if len(h2) > 1 else 0.0
                    state["base_units_4wk_momentum"] = (
                        float(np.mean(h2[-4:])) / float(np.mean(h2[-8:-4])) - 1.0
                        if len(h2) >= 8 and float(np.mean(h2[-8:-4])) > 0 else 0.0)
                    state["base_units_13wk_momentum"] = (
                        float(np.mean(h2[-13:])) / float(np.mean(h2[-26:-13])) - 1.0
                        if len(h2) >= 26 and float(np.mean(h2[-26:-13])) > 0 else 0.0)
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
                p = invert(raw, "log1p", None)
                if not np.isfinite(p):
                    p = h2[-1]
                h2.append(p); preds[(key, fd)] = p
        ks = [k for k in truth if k in preds]
        if ks:
            a = np.array([truth[k] for k in ks]); p = np.array([preds[k] for k in ks])
            out[ql] = {"wmape": wmape(a, p),
                       "bias": float(p.sum() / a.sum()) if a.sum() else float("nan")}
    return out


def main(trees, _unused_stage, account, channel):
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
    print(f"MO_88 — tweedie refinements | {scope}")
    print(f"  baselines: quantile 38.0 / 58.5 Q1'26 | tweedie 35.8 / 50.5 | flat 32.7 | lin52 46.1 / 37.0 Q1'26\n")
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
    for arm in ARMS:
        results[arm] = report(arm, run_combo(df, feats, cats, ev, weeks, arm, trees))

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

    ap.add_argument("--account", default="KROGER")
    ap.add_argument("--channel", default="CONVENTIONAL|FOOD")
    ap.add_argument("--portfolio", action="store_true",
                    help="evaluate on the FULL panel, not one retailer/channel")
    a = ap.parse_args()
    main(a.trees, None, None if a.portfolio else a.account, a.channel)
