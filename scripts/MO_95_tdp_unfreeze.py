#!/usr/bin/env python
"""MO_95 - what is unfreezing TDP actually worth?

Jason: "should we pause optuna and test the per-cell TDP projection? that is, are
we optimizing before we confirm the model to optimize?" Yes. This is the
architecture question that has to be settled before hyperparameters mean anything.

Measured facts that motivate it (MO_93/94 session, 2026-10-03):
  - units scale ~1:1 with TDP WITHIN a cell: median elasticity 1.05, 84% >= 0.8
  - TDP moves a median 21.7% over 13 weeks; 67% of windows move >10%
  - yet ALL 7 TDP features are frozen at the anchor row for all 13 steps
  - and tdp_wow_delta / tdp_4w_momentum are frozen at NON-ZERO values, so the
    model is told distribution is still moving while the level never changes

Arms (all share one fitted model per cutoff, so only the INFERENCE loop differs):
  frozen     production today: every TDP feature held at the anchor value
  coherent   level held, but the momentum/delta features zeroed -- removes the
             internal contradiction without needing any projection or new data
  projected  per-cell damped linear TDP trend, fit on data <= cut only (honest)
  oracle     actual future TDP fed in -- NOT shippable, it is the CEILING

The oracle is the decision-maker. If oracle ~= frozen, this direction is dead and
we stop. If oracle is large, it justifies both building a projector and asking
BUILT for authorization / planned-distribution data.

MO_27g is not a counter-example: it applied a SINGLE GLOBAL growth rate, and the
real 13-week change distribution is median 22% / mean 226% / p90 148%. One rate
cannot fit that. Wrong shape of fix, not a wrong idea.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

import MO_80_quarterly_honest_backtest as M
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo95_tdp_unfreeze.json")
TREES = 800
ARMS = ("frozen", "coherent", "projected", "oracle")
TREND_WEEKS = 13      # window for the per-cell damped linear fit
DAMP = 0.85           # per-step damping on the projected slope


def project_tdp(hist_tdp: np.ndarray, n: int) -> np.ndarray:
    """Damped linear extrapolation of a cell's own TDP, from history only."""
    h = hist_tdp[~np.isnan(hist_tdp)]
    if len(h) == 0:
        return np.full(n, np.nan)
    last = float(h[-1])
    if len(h) < 4:
        return np.full(n, last)
    w = h[-TREND_WEEKS:]
    x = np.arange(len(w), dtype=float)
    slope = np.polyfit(x, w, 1)[0]
    out, cur, s = [], last, slope
    for _ in range(n):
        cur = max(0.0, cur + s)
        out.append(cur)
        s *= DAMP
    return np.array(out)


def run_arm(arm, df, feats, cut, qs, qe, eval_keys, fweeks, seasonal):
    """One fitted model, four inference loops. Only TDP handling differs."""
    tr = df[df["__time"] <= cut]
    if len(tr) < 500:
        return {}
    va = tr.tail(max(200, len(tr) // 10))
    model = M.fit(tr[feats], np.log1p(tr["base_units"]),
                  va[feats], np.log1p(va["base_units"]), TREES)
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}

    # future TDP actuals, for the oracle arm only
    fut = df[(df["__time"] > cut) & (df["__time"] <= fweeks[-1])]
    fut_tdp = {(k, t): v for (u, c, a, g, t), v in
               fut.groupby(GROUP_COLS + ["__time"], observed=True)["tdp"].mean().items()
               for k in [(u, c, a, g)]}

    out = {}
    for key, g in tr.groupby(GROUP_COLS, observed=True):
        if key not in eval_keys or len(g) < 4:
            continue
        g = g.sort_values("__time")
        hist = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
        tdp_hist = pd.to_numeric(g["tdp"], errors="coerce").to_numpy()
        anchor_tdp = float(tdp_hist[-1]) if np.isfinite(tdp_hist[-1]) else np.nan
        proj = project_tdp(tdp_hist, len(fweeks))

        state = g.iloc[-1].copy()
        tdp_seq = []
        for h, fd in enumerate(fweeks[:M.HORIZON], start=1):
            t2 = float(fd.isocalendar().week)
            state["week_sin"] = np.sin(2 * np.pi * t2 / 52)
            state["week_cos"] = np.cos(2 * np.pi * t2 / 52)
            state["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
            state["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
            state["base_units_lag1"] = hist[-1]
            state["base_units_roll4_avg"] = float(np.mean(hist[-4:]))
            state["base_units_roll8_avg"] = float(np.mean(hist[-8:]))
            state["base_units_roll13_avg"] = float(np.mean(hist[-13:]))
            state["base_units_wow_delta"] = hist[-1] - hist[-2] if len(hist) > 1 else 0.0

            # ── the only thing that differs between arms ────────────────────
            if arm == "coherent":
                # level stays put, so say so: nothing is moving
                for c in ("tdp_wow_delta", "tdp_4w_momentum"):
                    if c in feats:
                        state[c] = 0.0
            elif arm in ("projected", "oracle"):
                if arm == "oracle":
                    tv = fut_tdp.get((key, fd), np.nan)
                    if not np.isfinite(tv):
                        tv = proj[h - 1]
                else:
                    tv = proj[h - 1]
                if np.isfinite(tv):
                    tdp_seq.append(float(tv))
                    prev = tdp_seq[-2] if len(tdp_seq) > 1 else anchor_tdp
                    if "tdp" in feats:
                        state["tdp"] = tv
                    if "tdp_wow_delta" in feats and np.isfinite(prev):
                        state["tdp_wow_delta"] = tv - prev
                    if "tdp_4w_momentum" in feats:
                        base4 = tdp_seq[-5] if len(tdp_seq) >= 5 else anchor_tdp
                        if np.isfinite(base4) and base4 > 0:
                            state["tdp_4w_momentum"] = tv / base4 - 1.0
                    if "velocity_per_tdp" in feats and tv > 0:
                        state["velocity_per_tdp"] = hist[-1] / tv

            X = pd.DataFrame([state])[feats]
            for c, cc in cats.items():
                if c in X.columns:
                    X[c] = pd.Categorical(X[c], categories=cc)
            p = float(np.clip(np.expm1(model.predict(X))[0], 0, None))
            hist.append(p)
            if qs <= fd <= qe:
                out[(key, fd)] = p
    return out


def main() -> None:
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    seasonal = M.load_seasonal_index()
    df = M.load_panel(feats)
    WEEKS = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    ev = (df["retail_account"] == "KROGER") & (df["channel_outlet"] == "CONVENTIONAL|FOOD")

    print("MO_95 - what is unfreezing TDP worth? (KROGER CONVENTIONAL|FOOD)")
    print(f"  arms: {', '.join(ARMS)}   [oracle = ceiling, not shippable]\n")
    print(f"  {'quarter':<9s} " + " ".join(f"{a:>16s}" for a in ARMS))

    results = {}
    for ql, qc, q1, q2 in [q for q in M.QUARTERS if q[0] != "Q4 2026"]:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[ev & (df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        eval_keys = {k[0] for k in truth}
        fweeks = M.future_weeks(WEEKS, cut, M.HORIZON)
        row, cells = {}, []
        for arm in ARMS:
            pred = run_arm(arm, df, feats, cut, qs, qe, eval_keys, fweeks, seasonal)
            sc = M.score(truth, pred)
            row[arm] = sc
            cells.append(f"{sc['wmape']:>9.1f} {sc['bias']:>6.3f}" if sc else f"{'--':>16s}")
        results[ql] = row
        print(f"  {ql:<9s} " + " ".join(cells))

    print(f"\n  {'arm':<11s} {'mean wMAPE':>11s} {'mean |bias-1|':>14s} {'vs frozen':>11s}")
    base = np.mean([results[q]["frozen"]["wmape"] for q in results if results[q].get("frozen")])
    for arm in ARMS:
        w = [results[q][arm]["wmape"] for q in results if results[q].get(arm)]
        b = [abs(results[q][arm]["bias"] - 1) for q in results if results[q].get(arm)]
        print(f"  {arm:<11s} {np.mean(w):>11.1f} {np.mean(b):>14.3f} {np.mean(w)-base:>+10.1f}pp")

    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT}")
    print("\n  Read the ORACLE row first: it is the ceiling on everything this")
    print("  direction can deliver, including perfect authorization data.")


if __name__ == "__main__":
    main()
