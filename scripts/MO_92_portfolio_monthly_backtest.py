#!/usr/bin/env python
"""MO_92 - portfolio monthly honest backtest, in the units finance actually uses.

Everything else we report is wMAPE on series. A finance team asks a different
question: for a given month, how far off was the number, in percent and in
dollars? This produces exactly that table, reproducibly, so it can go in a
report without hand-computed figures behind it.

Design
  - rolling monthly origins; at each origin the model is retrained on data
    <= origin only (MO_80's recursive production path, reused not reimplemented)
  - predictions aggregated to calendar months, then compared two ways:
      MATCHED  actuals restricted to cells the model forecast  -> model skill
      FULL     all actual units in the month                   -> what finance feels
    The gap between them IS the new-cell structural gap measured in MO_91.
  - dollars from the panel's own `arp` (average retail price), volume-weighted
    per month. No assumed price.

Horizons reported: 1-month-ahead (origin+1) and the full 13-week block.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from MO_80_quarterly_honest_backtest import fit, load_panel, run_recursive  # noqa: F401
from mo_panel import GROUP_COLS

OUT_JSON = Path("outputs/mo92_portfolio_monthly_backtest.json")
OUT_CSV = Path("outputs/mo92_portfolio_monthly_backtest.csv")
TREES = 2000
ORIGINS = pd.period_range("2025-01", "2026-05", freq="M")
PKL_CANDIDATES = [
    "outputs/model_retailer_sales_q50_v11_full.pkl",
    "outputs/model_retailer_sales_q50_v10_full.pkl",
]


def feature_list() -> list[str]:
    for p in PKL_CANDIDATES:
        if Path(p).exists():
            with open(p, "rb") as fh:
                return list(pickle.load(fh).feature_name_)
    raise SystemExit(f"MO_92: no model pickle found among {PKL_CANDIDATES}")


def main() -> None:
    feats = feature_list()
    df = load_panel(feats)
    df["ym"] = df["__time"].dt.tz_convert("UTC").dt.to_period("M")
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))

    # month-level average retail price, volume weighted, from the panel's own arp
    arp = df.dropna(subset=["arp"]).copy()
    arp["w"] = arp["base_units"].clip(lower=0)
    price = (arp.groupby("ym").apply(
        lambda g: np.average(g["arp"], weights=g["w"]) if g["w"].sum() > 0 else np.nan,
        include_groups=False))

    print("MO_92 - portfolio monthly honest backtest (retrained at every origin)")
    print(f"  panel {len(df):,} rows - "
          f"{df.groupby(GROUP_COLS, observed=True).ngroups:,} series - "
          f"through {df['__time'].max().date()}")
    print(f"  {len(feats)} features - {TREES} trees - {len(ORIGINS)} monthly origins\n")

    rows = []
    for origin in ORIGINS:
        cut_candidates = weeks[weeks <= pd.Timestamp(origin.end_time, tz="UTC")]
        if len(cut_candidates) == 0:
            continue
        cut = cut_candidates[-1]
        fweeks = list(weeks[weeks > cut][:13])
        if not fweeks:
            continue
        qs, qe = fweeks[0], fweeks[-1]

        hist = df[df["__time"] <= cut]
        eval_keys = set(hist.groupby(GROUP_COLS, observed=True).groups.keys())
        pred = run_recursive(df, feats, cut, qs, qe, eval_keys, TREES, fweeks)
        if not pred:
            print(f"  {origin}: no predictions - skipped")
            continue

        P = pd.DataFrame(
            [{"key": k, "__time": t, "pred": v} for (k, t), v in pred.items()])
        P["ym"] = P["__time"].dt.tz_convert("UTC").dt.to_period("M")

        fut = df[(df["__time"] >= qs) & (df["__time"] <= qe)].copy()
        fut["key"] = list(zip(*[fut[c] for c in GROUP_COLS]))

        # One row per target month (so each lead is comparable to MO_91's
        # single-month flat benchmark), plus the whole 13-week block.
        months_in_window = sorted(P["ym"].unique())
        arms = [(f"T+{(m - origin).n}", [m]) for m in months_in_window]
        arms.append(("13wk", months_in_window))
        for lbl, sel in arms:
            pm = P[P["ym"].isin(sel)]
            fm = fut[fut["ym"].isin(sel)]
            if pm.empty or fm.empty:
                continue
            forecast = float(pm["pred"].sum())
            matched = float(fm.loc[fm["key"].isin(set(pm["key"])), "base_units"].sum())
            full = float(fm["base_units"].sum())
            px = float(np.nanmean([price.get(m, np.nan) for m in sel]))
            rows.append(dict(
                origin=str(origin), horizon=lbl,
                target=",".join(str(m) for m in sel),
                forecast_units=forecast, matched_units=matched, full_units=full,
                err_matched=(forecast - matched) / matched if matched else np.nan,
                err_full=(forecast - full) / full if full else np.nan,
                arp=px,
                dollar_diff_matched=(forecast - matched) * px,
                dollar_diff_full=(forecast - full) * px,
                n_cells=int(pm["key"].nunique()),
            ))
        print(f"  {origin} done - {P['key'].nunique():,} cells forecast")

    R = pd.DataFrame(rows)
    if R.empty:
        raise SystemExit("MO_92: produced no rows")
    R.to_csv(OUT_CSV, index=False)

    for lbl in sorted(R["horizon"].unique(), key=lambda x: (x == "13wk", x)):
        s = R[R["horizon"] == lbl]
        if s.empty:
            continue
        print(f"\n=== {lbl} horizon ===")
        print(f"  {'origin':<9s} {'target':<26s} {'actual':>11s} {'forecast':>11s} "
              f"{'% off':>8s} {'$ off':>12s} {'% off full':>11s}")
        for _, r in s.iterrows():
            print(f"  {r.origin:<9s} {r.target[:26]:<26s} {r.matched_units:>11,.0f} "
                  f"{r.forecast_units:>11,.0f} {r.err_matched:>+7.1%} "
                  f"{r.dollar_diff_matched:>+12,.0f} {r.err_full:>+10.1%}")
        for col, name in (("err_matched", "matched cells"), ("err_full", "full portfolio")):
            e = s[col].dropna()
            print(f"  {name:<16s} median |err| {e.abs().median():>6.1%}  "
                  f"mean |err| {e.abs().mean():>6.1%}  bias {e.mean():>+6.1%}  "
                  f"within +-7% {(e.abs() <= 0.07).mean():>4.0%}")

    OUT_JSON.write_text(json.dumps({
        "trees": TREES, "n_features": len(feats),
        "origins": [str(o) for o in ORIGINS],
        "rows": R.to_dict("records"),
        "summary": {
            lbl: {
                col: {
                    "median_abs": float(R.loc[R.horizon == lbl, col].abs().median()),
                    "mean_abs": float(R.loc[R.horizon == lbl, col].abs().mean()),
                    "bias": float(R.loc[R.horizon == lbl, col].mean()),
                    "within_7pct": float((R.loc[R.horizon == lbl, col].abs() <= 0.07).mean()),
                } for col in ("err_matched", "err_full")
            } for lbl in sorted(R["horizon"].unique())
        },
    }, indent=2, default=str))
    print(f"\nwrote {OUT_CSV}\nwrote {OUT_JSON}")


if __name__ == "__main__":
    main()
