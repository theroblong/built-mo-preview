"""MO_84 — Make the seasonal blend weight CONDITIONAL. The Q1 turning-point fix.

THE FAILURE, MEASURED
---------------------
Kroger CONVENTIONAL|FOOD, Q1 2026 (cutoff 2025-12-28), honest retrained backtest:

                 week 1      week 13     slope
    actual       38,263      58,570      +1,647/wk   RISING 53%
    Mo           28,883      16,947        -928/wk   FALLING 41%   <-- wrong way
    year-ago     20,279      26,494        +518/wk   rising (right DIRECTION, wrong LEVEL)

The model does not merely under-call, it points the wrong way. Compare the two Q1 cutoffs:

    cutoff 2024-12-29   prior 13 wks 6,220 -> 6,690   flat        -> Mo went flat, ratio 0.527
    cutoff 2025-12-28   prior 13 wks 43,147 -> 33,611  -22% dive   -> Mo extrapolated the dive

MECHANISM: at the December cutoff every momentum feature (`base_units_wow_delta`,
`base_units_4wk_momentum`, `base_units_z8`) encodes the seasonal trough, and the recursive loop
extrapolates that decline straight through the January-March peak. In Dec 2024 BUILT was small
and the pre-cutoff window was flat, so there was no momentum to extrapolate and the model merely
stalled. By Dec 2025 BUILT was ~7x larger and the trough was steep, so the same mechanism became
a 41% decline against a 53% rise.

The division of labour is the whole insight:
    year-ago reference  RIGHT SHAPE, wrong level (BUILT grew ~2x YoY, so lag52 sits far too low)
    the model           RIGHT LEVEL, wrong shape (anchors near reality, then heads downhill)

Combining them is exactly what SEASONAL_BLEND_WEIGHT does. It is currently a CONSTANT 0.10,
lowered from 0.40 this morning on MO_27f evidence that 0.40 "never wins" — but that was POOLED
across cutoffs, and pooling is precisely what hides this. In an ordinary quarter a low weight is
right; at a turning point it is catastrophic. We tuned a knob on the average and broke it at the
one place it decides the answer.

WHAT THIS TESTS
---------------
Blending is applied AFTER the model prediction, so each cutoff is trained ONCE and every weight
policy is evaluated on the same predictions. That makes the sweep nearly free.

    forecast[t] = (1 - W) * model[t] + W * (lag52[t] * yoy_ratio)
    yoy_ratio   = clip(anchor_units / yago_anchor, 0.5, 2.0)      # as MO_27 does today

Policies:
    w0.00 / w0.10 (current) / w0.20 / w0.40      constant, for reference
    turn_hi                                       W=0.60 when the year-ago path and recent
                                                  momentum DISAGREE in direction, else 0.10
    turn_mid                                      same test, W=0.40 / 0.10
    turn_only                                     W=0.60 on disagreement, 0.00 otherwise

"Disagreement" is computed strictly from pre-cutoff information: the sign of the series' recent
4-week momentum versus the sign of the year-ago path's slope across the horizon. A turning point
is when the past says down and last year says up (or vice versa).

Run:  python MO_84_conditional_seasonal_weight.py [--trees 800]
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
OUT_JSON = Path("outputs/mo84_conditional_seasonal_weight.json")
HORIZON  = 13
DYNAMIC_MOMENTUM = False   # True = also advance roll/z/momentum (production freezes them)
RECENCY_LAMBDA = 0.02
LGBM = dict(learning_rate=0.05, num_leaves=63, min_child_samples=20,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1, verbose=-1)

QUARTERS = [("Q1 2025", "2024-12-29"), ("Q2 2025", "2025-03-30"), ("Q3 2025", "2025-06-29"),
            ("Q4 2025", "2025-09-28"), ("Q1 2026", "2025-12-28"), ("Q2 2026", "2026-03-29"),
            ("Q3 2026", "2026-06-29")]

POLICIES = {"w0.10": ("const", 0.10), "w0.40": ("const", 0.40), "w0.60": ("const", 0.60),
            "w0.80": ("const", 0.80), "w1.00": ("const", 1.00),
            "turn_hi": ("turn", 0.60, 0.10), "turn_full": ("turn", 1.00, 0.10),
            # Jason's observation: even a FLAT line beats a downward slope, and last year's
            # arc suggests a climb then a gentle descent. Two arms that use no model at all:
            "flat_anchor": ("flat",),            # hold the anchor week constant, 13 weeks
            "yago_shape": ("shape",),            # anchor x (yago[t] / yago[anchor week])
            "shape_x_model": ("shapemix", 0.5)}  # half that arc, half the model


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
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


def main(trees, account, channel):
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v11_full.pkl", "rb")).feature_name_)
    df = load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    ev = (df["retail_account"] == account) & (df["channel_outlet"] == channel)
    print(f"MO_84 — conditional seasonal blend weight | {account} {channel}")
    print(f"  one model fit per cutoff; every weight policy scored on the same predictions\n")

    results = {}
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
        eval_keys = {k[0] for k in truth}

        tr = hist_all
        va = tr.tail(max(200, len(tr) // 10))
        m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=trees, **LGBM)
        wkago = ((tr["__time"].max() - tr["__time"]).dt.days / 7).clip(lower=0)
        m.fit(tr[feats], np.log1p(tr["base_units"]), sample_weight=np.exp(-RECENCY_LAMBDA * wkago),
              eval_set=[(va[feats], np.log1p(va["base_units"]))], eval_metric="quantile",
              callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])

        raw, yago, turn, anchors, shape = {}, {}, {}, {}, {}
        for key, g in hist_all[ev.reindex(hist_all.index, fill_value=False)].groupby(
                GROUP_COLS, observed=True):
            if key not in eval_keys:
                continue
            g = g.sort_values("__time")
            if len(g) < 4:
                continue
            s = pd.to_numeric(g.set_index("__time")["base_units"], errors="coerce").fillna(0)
            hist = list(s.values)
            anchor = float(hist[-1])
            # year-ago path for the horizon, strictly from pre-cutoff actuals
            yg = [float(s.get(fd - pd.Timedelta(weeks=52), np.nan)) for fd in fw]
            yg_anchor = float(s.get(cut - pd.Timedelta(weeks=52), np.nan))
            ratio = float(np.clip(anchor / yg_anchor, 0.5, 2.0)) if (
                np.isfinite(yg_anchor) and yg_anchor > 0) else np.nan
            # turning point: recent momentum sign vs year-ago path slope sign
            recent = np.polyfit(range(min(4, len(hist))), hist[-min(4, len(hist)):], 1)[0] \
                if len(hist) >= 2 else 0.0
            ygv = [v for v in yg if np.isfinite(v)]
            ygs = np.polyfit(range(len(ygv)), ygv, 1)[0] if len(ygv) >= 2 else 0.0
            turn[key] = bool(recent * ygs < 0)
            anchors[key] = anchor
            # Last year's SHAPE re-based to this year's level: anchor x (yago[t]/yago[anchor]).
            # Transfers the arc without importing last year's (much lower) absolute level.
            for _i, _fd in enumerate(fw):
                shape[(key, _fd)] = (anchor * (yg[_i] / yg_anchor)
                                     if (np.isfinite(yg[_i]) and np.isfinite(yg_anchor)
                                         and yg_anchor > 0) else np.nan)
            state = g.iloc[-1].copy()
            h2 = list(hist)
            # ── lag52 sequence, precomputed from ACTUALS as MO_27 does ───────────────
            # THIS IS THE ONE THAT MATTERS. Production advances base_units_lag52 every step so
            # the model sees what happened in the SAME WEEK last year. An earlier version of
            # this harness left it frozen at the anchor row's value for all 13 steps, which in
            # a December cutoff meant the model was told "last year = December" while it was
            # being asked about January-March. It therefore could not see the Q1 climb, and the
            # resulting "flat beats the model" conclusion was an artifact of this harness, not
            # a property of the model. Never reimplement the production loop by hand.
            n_act = len(hist)
            lag52_seq = [float(hist[n_act - 53 + i]) if 0 <= (n_act - 53 + i) < n_act else np.nan
                         for i in range(1, len(fw) + 1)]
            arp_hist = list(pd.to_numeric(g["arp"], errors="coerce").fillna(method="ffill").values)
            for i, fd in enumerate(fw):
                t2 = float(fd.isocalendar().week)
                state["week_sin"] = np.sin(2 * np.pi * t2 / 52)
                state["week_cos"] = np.cos(2 * np.pi * t2 / 52)
                state["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
                state["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
                # autoregressive lags from actuals + prior predictions, exactly as MO_27
                state["base_units_lag1"]  = h2[-1]
                state["base_units_lag4"]  = h2[-4]  if len(h2) >= 4  else np.nan
                state["base_units_lag13"] = h2[-13] if len(h2) >= 13 else np.nan
                state["base_units_lag52"] = lag52_seq[i]
                # PRODUCTION FREEZES these at the anchor row (they are NOT in MO_27's `skip`
                # set, so they come from static_feats and never move). At a December cutoff that
                # means the model is shown December-trough momentum for all 13 weeks. Measuring
                # production faithfully requires leaving them frozen; DYNAMIC_MOMENTUM=True tests
                # whether unfreezing them is an improvement.
                _w8, _w13 = h2[-8:], h2[-13:]
                if not DYNAMIC_MOMENTUM:
                    pass
                else:
                    state["base_units_roll4_avg"]  = float(np.mean(h2[-4:]))
                    state["base_units_roll8_avg"]  = float(np.mean(_w8))
                    state["base_units_roll13_avg"] = float(np.mean(_w13))
                    state["base_units_roll8_std"]  = float(np.std(_w8))  if len(_w8) > 1 else 0.0
                    state["base_units_roll13_std"] = float(np.std(_w13)) if len(_w13) > 1 else 0.0
                    _m8, _s8 = float(np.mean(_w8)), (float(np.std(_w8)) if len(_w8) > 1 else 0.0)
                    _m13, _s13 = float(np.mean(_w13)), (float(np.std(_w13)) if len(_w13) > 1 else 0.0)
                    state["base_units_z8"]  = (h2[-1] - _m8) / _s8 if _s8 > 0 else 0.0
                    state["base_units_z13"] = (h2[-1] - _m13) / _s13 if _s13 > 0 else 0.0
                    state["base_units_wow_delta"] = h2[-1] - h2[-2] if len(h2) > 1 else 0.0
                    state["base_units_4wk_momentum"] = (
                        float(np.mean(h2[-4:])) / float(np.mean(h2[-8:-4])) - 1.0
                        if len(h2) >= 8 and float(np.mean(h2[-8:-4])) > 0 else 0.0)
                    state["base_units_13wk_momentum"] = (
                        float(np.mean(h2[-13:])) / float(np.mean(h2[-26:-13])) - 1.0
                        if len(h2) >= 26 and float(np.mean(h2[-26:-13])) > 0 else 0.0)
                # ARP held flat forward (MO_27 does the same); rolling stats from history
                if arp_hist:
                    _ac = arp_hist[-1]
                    state["arp"] = _ac
                    state["arp_lag1"] = arp_hist[-2] if len(arp_hist) >= 2 else _ac
                    _aw = arp_hist[-8:]
                    state["arp_roll8_avg"] = float(np.nanmean(_aw))
                    state["arp_roll8_std"] = float(np.nanstd(_aw)) if len(_aw) > 1 else 0.0
                    state["arp_wow_delta"] = 0.0
                state["weeks_since_launch"] = float(
                    pd.to_numeric(g.iloc[-1].get("weeks_since_launch"), errors="coerce") or 0) + i + 1
                X = pd.DataFrame([state])[feats]
                for c, cc in cats.items():
                    if c in X.columns:
                        X[c] = pd.Categorical(X[c], categories=cc)
                p = float(np.clip(np.expm1(m.predict(X))[0], 0, None))
                h2.append(p)
                raw[(key, fd)] = p
                yago[(key, fd)] = (yg[i] * ratio) if (np.isfinite(yg[i])
                                                      and np.isfinite(ratio)) else np.nan

        row = {"cutoff": qc, "n_series": len(eval_keys),
               "pct_turning": float(np.mean([turn.get(k, False) for k in eval_keys]) * 100)}
        for name, pol in POLICIES.items():
            preds = {}
            for k in raw:
                if pol[0] == "flat":
                    preds[k] = anchors.get(k[0], raw[k]); continue
                if pol[0] == "shape":
                    sv = shape.get(k, np.nan)
                    preds[k] = sv if np.isfinite(sv) else anchors.get(k[0], raw[k]); continue
                if pol[0] == "shapemix":
                    sv = shape.get(k, np.nan)
                    preds[k] = (pol[1] * sv + (1 - pol[1]) * raw[k]) if np.isfinite(sv) else raw[k]
                    continue
                w = pol[1] if pol[0] == "const" else (pol[1] if turn.get(k[0]) else pol[2])
                y = yago.get(k, np.nan)
                preds[k] = raw[k] if (w == 0 or not np.isfinite(y)) else (1 - w) * raw[k] + w * y
            ks = [k for k in truth if k in preds]
            if not ks:
                continue
            a = np.array([truth[k] for k in ks]); p = np.array([preds[k] for k in ks])
            row[name] = {"wmape": wmape(a, p),
                         "bias": float(p.sum() / a.sum()) if a.sum() else float("nan")}
        results[ql] = row
        print(f"  {ql:<9s} ({row['pct_turning']:>4.0f}% turning)  " + "  ".join(
            f"{n}={row[n]['wmape']:.1f}" for n in POLICIES if n in row))

    print(f"\n{'='*86}")
    print(f"  {'policy':<12s} " + " ".join(f"{q.split()[0]+q.split()[1][-2:]:>7s}" for q, _ in QUARTERS) + f" {'MEAN':>7s}")
    summary = {}
    for name in POLICIES:
        vals = [results[q][name]["wmape"] for q, _ in QUARTERS
                if q in results and name in results[q]]
        if not vals:
            continue
        summary[name] = {"mean_wmape": float(np.mean(vals)),
                         "per_quarter": {q: results[q][name]["wmape"] for q, _ in QUARTERS
                                         if q in results and name in results[q]}}
        cells = " ".join(f"{results[q][name]['wmape']:>7.1f}" for q, _ in QUARTERS
                         if q in results and name in results[q])
        print(f"  {name:<12s} {cells} {np.mean(vals):>7.1f}")
    if summary:
        best = min(summary, key=lambda k: summary[k]["mean_wmape"])
        cur = summary.get("w0.10", {}).get("mean_wmape")
        print(f"\n  BEST: {best} at {summary[best]['mean_wmape']:.1f}")
        if cur:
            print(f"  Current production (w0.10) {cur:.1f}  -> "
                  f"{cur - summary[best]['mean_wmape']:+.1f}pp available")
        q1 = {n: summary[n]["per_quarter"].get("Q1 2026") for n in summary}
        print(f"\n  Q1 2026 specifically (the black eye):")
        for n, v in sorted(q1.items(), key=lambda x: (x[1] is None, x[1])):
            if v is not None:
                print(f"    {n:<12s} {v:>6.1f}")
    OUT_JSON.write_text(json.dumps({"per_quarter": results, "summary": summary,
                                    "policies": {k: list(v) for k, v in POLICIES.items()}},
                                   indent=2, default=float))
    print(f"\n  → {OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=800)
    ap.add_argument("--dynamic-momentum", action="store_true")
    ap.add_argument("--account", default="KROGER")
    ap.add_argument("--channel", default="CONVENTIONAL|FOOD")
    a = ap.parse_args()
    DYNAMIC_MOMENTUM = a.dynamic_momentum
    globals()["DYNAMIC_MOMENTUM"] = DYNAMIC_MOMENTUM
    print(f"  DYNAMIC_MOMENTUM = {DYNAMIC_MOMENTUM}\n")
    main(a.trees, a.account, a.channel)
