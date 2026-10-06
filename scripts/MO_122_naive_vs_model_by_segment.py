#!/usr/bin/env python
"""MO_122 - where does the model actually beat carrying last week forward?

THE QUESTION, IN JASON'S WORDS
------------------------------
    "We should know things like BAR is trending down; so our next week forecast for BAR
     is down and more accurate than flat last value. This is just common sense."

He is right, and it is falsifiable. Established BUILT BAR series shed distribution at
-3.36%/wk (MO_121 context). A flat carry-forward MUST systematically over-forecast a
cohort like that. If our model does not beat flat there, that is a defect in the model,
not a property of the data.

He is also right that a straight line cannot represent the December trough -- which is
why TREND and SEASONALITY have to be separate terms rather than one fitted slope. The
production model has a seasonal index. It has NO trend term at all: 72% of its SHAP sits
on base_units_lag1 and base_units_roll4_avg, both pure LEVEL features. There is no
mechanism by which it can say "this is going down".

AND THE SECOND HALF OF THE QUESTION
-----------------------------------
A macro number nobody can drill into is worthless, because the first thing an FP&A
analyst does is decompose it. So the same forecast is scored at four levels. We forecast
bottom-up and sum, so macro and micro are the same numbers by construction and always
reconcile -- asserted here rather than assumed.

ARMS
  flat          last observed value carried forward. The thing to beat.
  drift         flat + damped recent slope. The TREND TERM the model lacks.
  seasonal_naive  lag52 scaled by the current YoY ratio. CAN represent the December
                trough, which a linear trend cannot.
  model         the production path (MO_80.run_production, frozen features, anchor mode)
  model_drift   the model's level, plus the same damped drift term

SEGMENTS, measured on PRE-CUTOFF data only
  trend direction   declining / flat / growing, from the slope of the last 13 weeks
                    normalised by the series' own level
  brand             BAR / PUFF / SOUR PUFF -- the direct test of the claim above
  lifecycle         ramping (<26wk) / mature (>=26wk)

LEVELS
  cell x week · account x month · portfolio x month, plus a coherence assertion.

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  1. flat beats the model on mature-stable cells (the random-walk result)
  2. drift beats flat on declining cells, and by a wide margin on BAR
  3. the model beats neither on declining cells, because it has no trend term
If (2) fails on a cohort losing 3.36% of distribution a week, my reading of the data is
wrong and that needs saying.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("outputs/mo122_naive_vs_model_by_segment.json")
TREES = 800
TREND_WINDOW = 13
TREND_DAMP = 0.85
DECLINE_THRESH = -0.005      # slope/level per week: below this = declining
GROW_THRESH = 0.005


def seg_trend(hist: list[float]) -> tuple[str, float]:
    """Direction and normalised slope from the last TREND_WINDOW weeks, pre-cutoff."""
    w = [v for v in hist[-TREND_WINDOW:] if np.isfinite(v)]
    if len(w) < 6:
        return "unknown", 0.0
    lvl = float(np.mean(w))
    if lvl <= 0:
        return "unknown", 0.0
    slope = float(np.polyfit(np.arange(len(w), dtype=float), np.asarray(w, float), 1)[0])
    r = slope / lvl
    return ("declining" if r < DECLINE_THRESH else
            "growing" if r > GROW_THRESH else "flat"), r


def drift_path(hist: list[float], n: int) -> list[float]:
    """Flat level plus a DAMPED recent slope — the trend term the model lacks.

    Damped because a 13-week slope is not a permanent growth rate; undamped linear
    extrapolation is exactly the failure mode that makes naive look good by comparison.
    """
    last = float(hist[-1]) if hist else 0.0
    w = [v for v in hist[-TREND_WINDOW:] if np.isfinite(v)]
    if len(w) < 6:
        return [max(0.0, last)] * n
    slope = float(np.polyfit(np.arange(len(w), dtype=float), np.asarray(w, float), 1)[0])
    out, cur, s = [], last, slope
    for _ in range(n):
        cur = max(0.0, cur + s)
        s *= TREND_DAMP
        out.append(cur)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=TREES)
    a = ap.parse_args()

    os.environ["MO_SEASONAL_MODE"] = "anchor"
    import MO_80_quarterly_honest_backtest as M
    importlib.reload(M)
    assert M.FEATURE_REFRESH == "freeze", "harness must match MO_27"
    GC = M.GROUP_COLS

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    df["_brand"] = df["source_brand"].astype(str)
    seasonal = M.load_seasonal_index()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]
    ARMS = ["flat", "drift", "seasonal_naive", "model", "model_drift"]

    print("MO_122 - where does the model beat carrying last week forward?")
    print(f"  mode={M.SEASONAL_MODE} refresh={M.FEATURE_REFRESH} · "
          f"declining = slope/level < {DECLINE_THRESH:+.3f}/wk\n")

    recs = []          # one row per (quarter, key, week, arm) collapsed to per-arm preds
    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {(k[:-1], k[-1]): float(v) for k, v in
                 act.groupby(GC + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        tr = df[df["__time"] <= cut]

        model = M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, seasonal)

        for key, g in tr.groupby(GC, observed=True):
            if key not in ek:
                continue
            g = g.sort_values("__time")
            hist = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
            if len(hist) < 6:
                continue
            direction, slope_r = seg_trend(hist)
            brand = str(g["_brand"].iloc[-1])
            age = len(hist)
            lifecycle = "ramping" if age < 26 else "mature"
            last = float(hist[-1])
            dpath = drift_path(hist, M.HORIZON)
            # seasonal naive: last year's week scaled by the current YoY ratio
            yago = float(hist[-52]) if len(hist) >= 52 else np.nan
            yoy = (float(np.clip(last / yago, 0.5, 2.0))
                   if np.isfinite(yago) and yago > 0 else 1.0)
            for h, fd in enumerate(fw[:M.HORIZON], start=1):
                if not (qs <= fd <= qe) or (key, fd) not in truth:
                    continue
                idx = len(hist) - 53 + h
                sn = (float(hist[idx]) * yoy if 0 <= idx < len(hist) else last)
                mv = model.get((key, fd))
                if mv is None:
                    continue
                recs.append({
                    "quarter": ql, "key": key, "date": fd, "h": h,
                    "account": key[GC.index("retail_account")],
                    "brand": brand, "direction": direction, "lifecycle": lifecycle,
                    "actual": truth[(key, fd)],
                    "flat": last,
                    "drift": dpath[h - 1],
                    "seasonal_naive": max(0.0, sn),
                    "model": mv,
                    "model_drift": max(0.0, mv + (dpath[h - 1] - last) * 0.5),
                })

    r = pd.DataFrame(recs)
    if r.empty:
        print("no rows"); return
    r["month"] = pd.to_datetime(r["date"]).dt.to_period("M").astype(str)
    print(f"  scored {len(r):,} cell-weeks across {r['quarter'].nunique()} quarters\n")

    def wmape(g, arm):
        d = np.abs(g["actual"]).sum()
        return float(np.abs(g["actual"] - g[arm]).sum() / d * 100) if d > 0 else np.nan

    def table(g):
        return {arm: wmape(g, arm) for arm in ARMS}

    res = {}

    print("CELL x WEEK — by trend direction (the test of the BAR claim)\n")
    print(f"  {'segment':<24s} {'n':>8s} " + " ".join(f"{a:>14s}" for a in ARMS))
    res["by_direction"] = {}
    for d_, g in r.groupby("direction"):
        t = table(g); res["by_direction"][d_] = {**t, "n": len(g)}
        best = min(ARMS, key=lambda a: t[a])
        print(f"  {d_:<24s} {len(g):>8,} "
              + " ".join(f"{t[a]:>13.1f}{'*' if a == best else ' '}" for a in ARMS))

    print("\nCELL x WEEK — by brand\n")
    print(f"  {'segment':<24s} {'n':>8s} " + " ".join(f"{a:>14s}" for a in ARMS))
    res["by_brand"] = {}
    for b, g in r.groupby("brand"):
        if len(g) < 200:
            continue
        t = table(g); res["by_brand"][b] = {**t, "n": len(g)}
        best = min(ARMS, key=lambda a: t[a])
        print(f"  {b[:23]:<24s} {len(g):>8,} "
              + " ".join(f"{t[a]:>13.1f}{'*' if a == best else ' '}" for a in ARMS))

    print("\nCELL x WEEK — by lifecycle\n")
    print(f"  {'segment':<24s} {'n':>8s} " + " ".join(f"{a:>14s}" for a in ARMS))
    res["by_lifecycle"] = {}
    for l_, g in r.groupby("lifecycle"):
        t = table(g); res["by_lifecycle"][l_] = {**t, "n": len(g)}
        best = min(ARMS, key=lambda a: t[a])
        print(f"  {l_:<24s} {len(g):>8,} "
              + " ".join(f"{t[a]:>13.1f}{'*' if a == best else ' '}" for a in ARMS))

    # ── aggregation levels; bottom-up so they reconcile by construction ───────
    print("\nTHE SAME FORECAST AT EVERY LEVEL (bottom-up, so it always reconciles)\n")
    print(f"  {'level':<24s} {'n':>8s} " + " ".join(f"{a:>14s}" for a in ARMS))
    res["by_level"] = {}
    levels = {
        "cell x week": None,
        "account x month": ["account", "month"],
        "portfolio x month": ["month"],
    }
    for lbl, keys in levels.items():
        g = r if keys is None else r.groupby(keys, as_index=False)[
            ["actual"] + ARMS].sum()
        t = table(g); res["by_level"][lbl] = {**t, "n": len(g)}
        best = min(ARMS, key=lambda a: t[a])
        print(f"  {lbl:<24s} {len(g):>8,} "
              + " ".join(f"{t[a]:>13.1f}{'*' if a == best else ' '}" for a in ARMS))

    # coherence: summing cells must equal the aggregate, exactly
    cw = r[["actual"] + ARMS].sum()
    pm = r.groupby("month", as_index=False)[["actual"] + ARMS].sum()[["actual"] + ARMS].sum()
    coh = {a: float(abs(cw[a] - pm[a])) for a in ["actual"] + ARMS}
    print(f"\n  coherence (|cell-sum − month-sum|): max {max(coh.values()):.6f} "
          f"— {'EXACT, drill-down always reconciles' if max(coh.values()) < 1e-6 else 'MISMATCH'}")
    res["coherence_max_abs_diff"] = max(coh.values())

    print("\nVERDICT")
    dec = res["by_direction"].get("declining", {})
    if dec:
        b = min(ARMS, key=lambda a: dec[a])
        print(f"  declining cells: best = {b} ({dec[b]:.1f}); "
              f"flat {dec['flat']:.1f}, model {dec['model']:.1f}, drift {dec['drift']:.1f}")
        if dec["drift"] < dec["flat"] - 0.5:
            print("  -> PREDICTION 2 HOLDS: a trend term beats flat on declining series.")
        else:
            print("  -> PREDICTION 2 FAILS: drift does NOT beat flat on declining series.")
    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
