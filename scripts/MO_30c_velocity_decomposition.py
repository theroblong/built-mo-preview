"""MO_30c — Forecast DISTRIBUTION x VELOCITY instead of units. Breaking the collinearity.

WHY
  MO_30b (direct multi-horizon) cured the bias (0.998 vs the recursive loop's 1.079) but exposed
  a second defect: `base_units_roll4_avg` is the #1 feature at EVERY horizon and the TDP family
  contributes 0.0% of gain from h=4 onward. TDP drops out of the top 8 entirely.

  That is collinearity, exactly as Jason predicted ("some of these calculated values may be
  highly correlated with other metrics"). A SKU's recent 4-week unit average already encodes how
  many doors it is in, so the tree takes the simpler proxy and distribution never surfaces as a
  separate lever. The model ends up doing "recent average, adjusted by retailer" — a moving
  average with extra steps — which is why it cannot express a distribution-driven ramp.

THE DECOMPOSITION
  demand = distribution x velocity.  Forecast the RATE, not the LEVEL:

      target        = base_units / tdp          (units per TDP point)
      forecast      = velocity_pred x tdp_path

  This breaks the collinearity by construction: a rolling average of UNITS cannot proxy for a
  RATE, so the model has to find what actually drives per-door velocity (flavour, pack, price,
  promo character, lifecycle, season). Distribution re-enters multiplicatively, where it belongs
  and where it can carry the ramp.

  It also matches how the lifecycle ramp actually works: TDP climbs 1.01 -> 1.69 over a series'
  first 60 weeks while demand doubles, so most of the ramp IS distribution, and velocity is the
  part worth modelling.

ARMS
  units            MO_30b baseline — predict units directly
  velocity_flat    predict velocity, multiply by LAST OBSERVED tdp (no forward distribution)
  velocity_proj    predict velocity, multiply by a capped-momentum TDP path

  The flat arm matters: if it already beats the units arm, the gain is from decomposition alone
  and needs no forward-TDP forecast. If only the projected arm wins, the benefit depends on
  predicting distribution, which is a harder and riskier claim.

Run:  python MO_30c_velocity_decomposition.py [--horizons 1 4 8 13] [--cap 0.005]
"""
from __future__ import annotations
import argparse, importlib.util, json, warnings
from pathlib import Path
import numpy as np, pandas as pd, lightgbm as lgb
warnings.filterwarnings("ignore")

_b = importlib.util.spec_from_file_location("b", str(Path(__file__).parent / "MO_30b_direct_multihorizon.py"))
B = importlib.util.module_from_spec(_b); _b.loader.exec_module(B)
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo30c_velocity_decomposition.json")
RECENCY_LAMBDA = 0.02
MIN_TDP = 1.0            # below this, velocity is numerically meaningless


def fit_predict(tr, te, feats, target, sw):
    m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=1200,
                          learning_rate=0.05, num_leaves=63, min_child_samples=20,
                          feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
                          reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)
    m.fit(tr[feats], np.log1p(tr[target]), sample_weight=sw,
          eval_set=[(te[feats], np.log1p(te[target]))],
          callbacks=[lgb.early_stopping(60, verbose=False), lgb.log_evaluation(-1)])
    return m, np.clip(np.expm1(m.predict(te[feats])), 0, None)


def main(horizons, cap, cutoff_back):
    df, feats, n_all, n_use = B.build(include_short=False)
    df["tdp_n"] = pd.to_numeric(df["tdp"], errors="coerce")
    g = df.groupby(GROUP_COLS, observed=True)
    # per-series capped weekly TDP growth from the trailing 13 actual weeks
    df["tdp_g"] = g["tdp_n"].transform(
        lambda s: np.clip((np.log(max(s.iloc[-1], MIN_TDP)) - np.log(max(s.iloc[max(0, len(s)-13)], MIN_TDP)))
                          / max(1, min(13, len(s)) - 1), -cap, cap) if len(s) >= 4 else 0.0)
    cut = df["__time"].max() - pd.Timedelta(weeks=cutoff_back)
    print(f"series {n_use} | cutoff {cut.date()} | TDP cap {cap*100:.2f}%/wk | horizons {horizons}\n")
    print(f"  {'h':>3s} {'arm':>14s} {'wMAPE':>8s} {'bias':>7s}  top gain features")
    res, pooled = {}, {}
    for h in horizons:
        d = df.copy()
        d["y_units"] = g["base_units"].shift(-h)
        d["tdp_fut"] = g["tdp_n"].shift(-h)
        d["t_target"] = d["__time"] + pd.Timedelta(weeks=h)
        tw = d["t_target"].dt.isocalendar().week.astype(float)
        d["week_sin"] = np.sin(2*np.pi*tw/52); d["week_cos"] = np.cos(2*np.pi*tw/52)
        d["week_sin26"] = np.sin(2*np.pi*tw/26); d["week_cos26"] = np.cos(2*np.pi*tw/26)
        # velocity target uses the FUTURE tdp as denominator — that is the true rate at t+h
        d["y_vel"] = d["y_units"] / d["tdp_fut"].clip(lower=MIN_TDP)
        d = d.dropna(subset=["y_units", "y_vel"])
        d = d[d["tdp_n"].fillna(0) >= MIN_TDP]
        tr = d[d["t_target"] <= cut]; te = d[(d["__time"] <= cut) & (d["t_target"] > cut)].copy()
        if len(tr) < 500 or len(te) < 50: continue
        sw = np.exp(-RECENCY_LAMBDA * ((tr["__time"].max() - tr["__time"]).dt.days/7).clip(lower=0))
        act = te["y_units"].values
        res[h] = {}
        # arm 1 — units direct
        mu, pu = fit_predict(tr, te, feats, "y_units", sw)
        # arm 2/3 — velocity, then multiply by a TDP path
        mv, pv = fit_predict(tr, te, feats, "y_vel", sw)
        tdp_flat = te["tdp_n"].clip(lower=MIN_TDP).values
        tdp_proj = tdp_flat * np.exp(te["tdp_g"].values * h)
        for name, pred in (("units", pu),
                           ("velocity_flat", pv * tdp_flat),
                           ("velocity_proj", pv * tdp_proj)):
            w, b = B.wmape(act, pred), float(np.sum(pred)/np.sum(act))
            res[h][name] = {"wmape": w, "bias": b}
            pooled.setdefault(name, [[], []])
            pooled[name][0].append(act); pooled[name][1].append(pred)
            mdl = mu if name == "units" else mv
            imp = pd.Series(mdl.booster_.feature_importance("gain"), index=feats).sort_values(ascending=False)
            tdp_share = sum(v for k, v in imp.head(10).items() if "tdp" in k or "velocity" in k)/max(imp.head(10).sum(), 1)
            res[h][name]["tdp_share_top10"] = float(tdp_share)
            print(f"  {h:>3d} {name:>14s} {w:>8.2f} {b:>7.3f}  "
                  + ", ".join(imp.head(3).index) + f"   [TDP-family {tdp_share*100:.0f}%]")
        print()
    print("POOLED")
    print(f"  {'arm':>14s} {'wMAPE':>8s} {'bias':>7s}")
    best = None
    for name, (A, P) in pooled.items():
        a, p = np.concatenate(A), np.concatenate(P)
        w, b = B.wmape(a, p), float(p.sum()/a.sum())
        res.setdefault("_pooled", {})[name] = {"wmape": w, "bias": b}
        print(f"  {name:>14s} {w:>8.2f} {b:>7.3f}")
        if best is None or w < res["_pooled"][best]["wmape"]: best = name
    print(f"\n  best arm: {best}")
    u = res["_pooled"]["units"]["wmape"]
    for name in ("velocity_flat", "velocity_proj"):
        if name in res["_pooled"]:
            print(f"    {name} vs units: {res['_pooled'][name]['wmape']-u:+.2f}pp")
    OUT.write_text(json.dumps(res, indent=2, default=float)); print(f"\n  → {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizons", type=int, nargs="+", default=[1, 4, 8, 13])
    ap.add_argument("--cap", type=float, default=0.005)
    ap.add_argument("--cutoff-back", type=int, default=13)
    a = ap.parse_args(); main(a.horizons, a.cap, a.cutoff_back)
