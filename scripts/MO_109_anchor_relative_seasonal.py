#!/usr/bin/env python
"""MO_109 - the seasonal factor is applied against the WRONG REFERENCE POINT.

Jason, looking at the year-overlay charts: "Each and every January shows a ramp up
and not down. That is what bugs me about the Q1 2026 down forecast. That made no
sense."

He is right, and the cause is a reference-point error in how the seasonal index is
applied. MO_27 and MO_80 both do:

    stl_mult   = max(0.1, 1.0 + stl_idx)       # TARGET week's index
    units_base = units_base * stl_mult

The index is a level RELATIVE TO THE YEAR'S MEAN. But the autoregressive
prediction it multiplies is already anchored near the CUTOFF week's level. So the
correct multiplier is the RATIO of the two indices, not the target index alone:

    correct = index(target_week) / index(anchor_week)

Q1 2026 was anchored on 2025-12-28, in the December trough. Our index has
Dec 0.90, Jan 0.94, Feb 0.99, Mar 1.20:

    week      applied   correct (ratio to Dec)
    Jan         0.94     0.94/0.90 = 1.044
    Feb         0.99     0.99/0.90 = 1.10
    Mar         1.20     1.20/0.90 = 1.33

**January gets pushed DOWN 6% when it should go UP 4%** -- roughly a 10-point
error in the wrong direction, right across the quarter the client is watching.

This also explains two results that never made sense:
  - more seasonal amplitude made things monotonically WORSE (MO_102) -- it was
    amplifying a sign error
  - zero seasonal tested optimal -- no correction beats a wrong correction

Arms:
  none              no seasonal factor (the current measured optimum)
  as_applied        today's production behaviour: multiply by index(target)
  anchor_relative   the fix: multiply by index(target) / index(anchor)

If anchor_relative beats `none`, this is the first genuine seasonal win and the
Q1 behaviour should visibly correct.
"""
from __future__ import annotations

import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

warnings.filterwarnings("ignore")

import MO_80_quarterly_honest_backtest as M
import MO_100_monthly_seasonal_index as S
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo109_anchor_relative_seasonal.json")
TREES = 1200
BASE = dict(num_leaves=63, min_child_samples=20, learning_rate=0.05,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1,
            verbose=-1, alpha=0.5)


def run(df, feats, cats, cut, qs, qe, eval_keys, fw, idx, mode):
    """Recursive loop with the seasonal factor applied three different ways."""
    tr = df[df["__time"] <= cut]
    va = tr.tail(max(200, len(tr) // 10))
    m = lgb.LGBMRegressor(objective="quantile", n_estimators=TREES, **BASE)
    m.fit(tr[feats], np.log1p(tr["base_units"]),
          eval_set=[(va[feats], np.log1p(va["base_units"]))],
          callbacks=[lgb.early_stopping(80, verbose=False), lgb.log_evaluation(-1)])

    anchor_wk = int(pd.Timestamp(cut).isocalendar().week)
    anchor_idx = idx.get(anchor_wk, 1.0) if idx else 1.0

    out = {}
    for key, g in tr.groupby(GROUP_COLS, observed=True):
        if key not in eval_keys:
            continue
        g = g.sort_values("__time")
        if len(g) < 4:
            continue
        hist = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
        state = g.iloc[-1].copy()
        for fd in fw[:M.HORIZON]:
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
            X = pd.DataFrame([state])[feats]
            for c, cc in cats.items():
                if c in X.columns:
                    X[c] = pd.Categorical(X[c], categories=cc)
            p = float(np.clip(np.expm1(m.predict(X))[0], 0, None))

            if mode != "none" and idx:
                tgt = idx.get(int(fd.isocalendar().week), 1.0)
                mult = tgt if mode == "as_applied" else (
                    tgt / anchor_idx if anchor_idx > 0 else 1.0)
                p = max(0.0, p * max(0.1, mult))

            hist.append(p)
            if qs <= fd <= qe:
                out[(key, fd)] = p
    return out


def main() -> None:
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    raw = S.load_panel()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]
    modes = ["none", "as_applied", "anchor_relative"]

    print("MO_109 - is the seasonal factor applied against the wrong reference?\n")
    print(f"  {'quarter':<9s} {'anchor wk':>9s} {'idx@anchor':>11s}  "
          + " ".join(f"{m:>16s}" for m in modes))

    acc = {m: [] for m in modes}
    detail = {}
    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)

        # index built HONESTLY from data <= cutoff
        mi, _ = S.monthly_index(raw, cutoff=cut, verbose=False)
        idx = {}
        if mi:
            wk = S.to_weekly(mi)
            idx = dict(zip(wk["week_of_year"].astype(int), wk["seasonal_index"]))
        a_wk = int(pd.Timestamp(cut).isocalendar().week)

        cells, row = [], {}
        for mode in modes:
            pred = run(df, feats, cats, cut, qs, qe, ek, fw, idx, mode)
            A = [truth[k] for k in truth if k in pred]
            P = [pred[k] for k in truth if k in pred]
            A_, P_ = np.array(A), np.array(P)
            w = float(np.abs(A_ - P_).sum() / np.abs(A_).sum() * 100)
            b = float(P_.sum() / A_.sum())
            acc[mode].append((w, b)); row[mode] = {"wmape": w, "bias": b}
            cells.append(f"{w:>9.1f} {b:>6.3f}")
        detail[ql] = row
        print(f"  {ql:<9s} {a_wk:>9d} {idx.get(a_wk, float('nan')):>11.3f}  "
              + " ".join(cells))

    print(f"\n  {'mode':<18s} {'wMAPE':>8s} {'bias':>7s}")
    res = {}
    for m in modes:
        w = np.nanmean([x[0] for x in acc[m]]); b = np.nanmean([x[1] for x in acc[m]])
        res[m] = {"wmape": float(w), "bias": float(b)}
        print(f"  {m:<18s} {w:>8.2f} {b:>7.3f}")

    d = res["anchor_relative"]["wmape"] - res["none"]["wmape"]
    print(f"\n  anchor_relative vs none: {d:+.2f}pp")
    if d < -0.3:
        print("  -> THE FIX WORKS. Seasonality helps once applied against the right reference.")
    elif d > 0.3:
        print("  -> still worse than no seasonal; the reference point was not the whole story.")
    else:
        print("  -> neutral. The reference error was real but seasonality still adds nothing.")

    OUT.write_text(json.dumps({"by_quarter": detail, "means": res}, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
