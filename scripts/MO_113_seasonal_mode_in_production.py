#!/usr/bin/env python
"""MO_113 - score the anchor-relative seasonal fix INSIDE the real production path.

MO_109 measured the fix in a BARE recursive loop, portfolio-wide, and found it worth
3.12pp against the form that shipped. Then MO_80's production arm -- the full MO_27
path, on Kroger -- came back at 54.1 wMAPE against bare recursive's 40.6, with Q1
over-forecasting badly (Q1 2025 bias 1.538, Q1 2026 bias 1.269). Those two results
cannot both be the whole story, so this script resolves them.

TWO THINGS MO_109 MISSED
------------------------
1. Production applies the seasonal index in **two** places, not one:
     - the LightGBM STL fallback (what MO_109 patched)
     - the short/lapsed router's `last_value_seasonal`, which multiplies the series'
       LAST ACTUAL by the index
   The second is where the reference-point error does the MOST damage, because the
   last actual sits exactly at the anchor week's seasonal level and nothing else in
   that path damps the factor. It was still on the old form.

2. MO_109's loop had no seasonal BLEND. Production also pulls each step toward
   lag52 x yoy_ratio at weight 0.10, and that blend fires in preference to the STL
   fallback. So in production the STL branch only reaches series with no usable
   lag52 -- a different and much smaller population than MO_109 scored.

Both sites now route through MO_80._seasonal_mult, switched by MO_SEASONAL_MODE, so
one mode applies consistently and the arms differ in nothing else.

ARMS
  target   index(target)                        what shipped before 2026-10-06
  anchor   index(target) / index(anchor)        the MO_109 fix
  step     index(target_h) / index(target_h-1)  the same intended level, composed
                                                through the recursion instead of
                                                imposed on top of it -- see the
                                                MO_113 note in MO_80
  off      no seasonal factor

FIRST RESULT (3 modes, portfolio-wide): target 48.57 / anchor 57.81 / off 45.43. The
MO_109 fix is 9.23pp WORSE than what shipped once the full production path is used,
with Q1 2025 56.4 -> 101.9 and Q1 2026 50.0 -> 96.2 at bias 1.46. The cause is
feedback: the loop appends the multiplied prediction to history, so a cumulative ratio
applied every step compounds. `step` is the arm that tests the repair.

Run:  python MO_113_seasonal_mode_in_production.py [--account KROGER] [--all]
`--all` evaluates portfolio-wide instead of one account, which is the number worth
quoting; the default single account is the fast check.
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

OUT = Path("outputs/mo113_seasonal_mode_in_production.json")
MODES = ["target", "anchor", "step", "off"]
TREES = 800


def run_mode(mode: str, account: str | None, channel: str, trees: int):
    """Reimport MO_80 under a given MO_SEASONAL_MODE and score its production arm.

    The mode is read at module import, so it has to be set BEFORE the reload rather
    than poked onto the module afterwards -- `_seasonal_mult` closes over the
    module-level name, and a stale import would silently score the wrong arm.
    """
    os.environ["MO_SEASONAL_MODE"] = mode
    import MO_80_quarterly_honest_backtest as M
    importlib.reload(M)
    assert M.SEASONAL_MODE == mode, f"reload did not take: {M.SEASONAL_MODE!r}"

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    seasonal = M.load_seasonal_index()
    df = M.load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))

    ev = df["channel_outlet"] == channel
    if account:
        ev &= df["retail_account"] == account

    rows = {}
    for ql, qc, q1, q2 in M.QUARTERS:
        if ql == "Q4 2026":
            continue
        cut = pd.Timestamp(qc, tz="UTC")
        qs, qe = pd.Timestamp(q1, tz="UTC"), pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[ev & (df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {(k[:-1], k[-1]): float(v) for k, v in
                 act.groupby(M.GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        pred = M.run_production(df, feats, cut, qs, qe, ek, trees, fw, seasonal)
        s = M.score(truth, pred)
        if s:
            # Share of the quarter's predicted volume that came from the short/lapsed
            # router rather than LightGBM. If the fix only moves the total when this is
            # large, the lever is the router, not the model.
            rows[ql] = s
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="KROGER")
    ap.add_argument("--channel", default="CONVENTIONAL|FOOD")
    ap.add_argument("--trees", type=int, default=TREES)
    ap.add_argument("--all", action="store_true",
                    help="evaluate portfolio-wide (ignore --account)")
    a = ap.parse_args()
    acct = None if a.all else a.account
    scope = "PORTFOLIO-WIDE" if a.all else f"{a.account} {a.channel}"

    print(f"MO_113 - seasonal mode inside the production path · {scope}\n")
    res = {m: run_mode(m, acct, a.channel, a.trees) for m in MODES}

    quarters = [q for q in res["anchor"]]
    print(f"  {'quarter':<9s} " + "  ".join(f"{m:>15s}" for m in MODES))
    for q in quarters:
        cells = []
        for m in MODES:
            r = res[m].get(q)
            cells.append(f"{r['wmape']:>8.1f} {r['bias']:>6.3f}" if r else f"{'--':>15s}")
        print(f"  {q:<9s} " + "  ".join(cells))

    print(f"\n  {'mode':<8s} {'wMAPE':>8s} {'bias':>7s}  {'|bias-1|':>8s}")
    means = {}
    for m in MODES:
        w = np.nanmean([r["wmape"] for r in res[m].values()])
        b = np.nanmean([r["bias"] for r in res[m].values()])
        ab = np.nanmean([abs(r["bias"] - 1) for r in res[m].values()])
        means[m] = {"wmape": float(w), "bias": float(b), "abs_bias_err": float(ab)}
        print(f"  {m:<8s} {w:>8.2f} {b:>7.3f}  {ab:>8.3f}")

    d_fix = means["anchor"]["wmape"] - means["target"]["wmape"]
    d_off = means["anchor"]["wmape"] - means["off"]["wmape"]
    print(f"\n  anchor vs target (what shipped): {d_fix:+.2f}pp")
    print(f"  anchor vs off   (no seasonal)  : {d_off:+.2f}pp")
    best = min(MODES, key=lambda m: means[m]["wmape"])
    print(f"  BEST: {best}  ({means[best]['wmape']:.2f})")
    msg = {
        "off": "inside the full production path seasonality does not pay at all. Ship "
               "`off` and stop carrying the index.",
        "anchor": "the cumulative ratio holds up even under feedback.",
        "step": "the compounding diagnosis was right: the same intended level, composed "
                "through the recursion, is the form to ship.",
        "target": "the form that already shipped is still the best of these. Do not "
                  "ship a change on this evidence.",
    }[best]
    print(f"  -> {msg}")

    OUT.write_text(json.dumps({"scope": scope, "by_quarter": res, "means": means,
                               "anchor_vs_target_pp": d_fix,
                               "anchor_vs_off_pp": d_off}, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
