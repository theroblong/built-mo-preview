#!/usr/bin/env python
"""MO_104 - add SES/ETS to the by-horizon comparison. The only method that ever beat flat.

SES_opt scored 30.8 at SKU-week against flat's 32.4 -- a 1.7pp win, and the ONLY
method in this whole effort that has beaten carry-forward. It has never been
tested by horizon, never at portfolio level, and never alongside direct
multi-horizon. MO_103 gave us recursive 36.44, direct 32.83, flat 32.95; this
drops the exponential-smoothing family into the same frame on the same folds.

Arms:
  SES_opt      simple exponential smoothing, alpha optimized -- the prior winner
  AutoETS_ns   automatic ETS, NON-seasonal (season_length=1)
  ETS_damped   damped-trend ETS -- the natural candidate for a growth brand
  flat         carry-forward, carried through as the reference

All NON-seasonal by construction: no series in this panel has the two complete
annual cycles a seasonal ETS needs, and MO_102 showed zero seasonal is optimal
anyway.

⚠️ Every model is given an explicit alias. statsforecast silently returns NOTHING
when two models resolve to the same name, which previously caused four arms to
come back empty across two runs while still exiting 0.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import MO_80_quarterly_honest_backtest as M
from mo_panel import GROUP_COLS

OUT = Path("outputs/mo104_ets_by_horizon.json")
CUTOFFS_BACK = (13, 26, 39, 52)
H = 13
MIN_OBS = 8        # exponential smoothing needs a minimum history to fit


def main() -> None:
    from statsforecast import StatsForecast
    from statsforecast.models import (
        SimpleExponentialSmoothingOptimized, AutoETS)

    df = M.load_panel([])
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    end = df["__time"].max()
    cuts = [end - pd.Timedelta(weeks=w) for w in CUTOFFS_BACK]

    df = df.copy()
    df["uid"] = [f"{a}|{b}|{c}|{d}" for a, b, c, d in
                 zip(*[df[g] for g in GROUP_COLS])]

    models = [
        SimpleExponentialSmoothingOptimized(alias="SES_opt"),
        AutoETS(season_length=1, alias="AutoETS_ns"),
        # `damped` is an AutoETS argument, not a Holt one -- Holt has no such kwarg.
        AutoETS(season_length=1, damped=True, alias="ETS_damped"),
    ]
    names = [m.alias for m in models]
    print("MO_104 - exponential smoothing by horizon")
    print(f"  arms: {', '.join(names)} (+ flat reference)")
    print(f"  folds {[str(c.date()) for c in cuts]}\n")

    per_fold = []
    for cut in cuts:
        fw = list(weeks[weeks > cut][:H])
        hist = df[df["__time"] <= cut]
        cnt = hist.groupby("uid")["base_units"].count()
        keep = set(cnt[cnt >= MIN_OBS].index)

        panel = (hist[hist["uid"].isin(keep)][["uid", "__time", "base_units"]]
                 .rename(columns={"__time": "ds", "base_units": "y"}))
        panel["ds"] = panel["ds"].dt.tz_localize(None)
        panel = panel.groupby(["uid", "ds"], as_index=False)["y"].sum()

        sf = StatsForecast(models=models, freq="W-SUN", n_jobs=-1)
        fc = sf.forecast(df=panel.rename(columns={"uid": "unique_id"}), h=H)
        fc = fc.reset_index() if "unique_id" not in fc.columns else fc
        missing = [n for n in names if n not in fc.columns]
        if missing:
            raise SystemExit(
                f"\nFATAL: statsforecast returned no column for {missing}.\n"
                f"  got: {list(fc.columns)}\n"
                f"  This is the duplicate-alias failure — it returns nothing rather than erroring.")

        fut = df[(df["__time"] > cut) & (df["__time"] <= fw[-1])]
        truth = fut.groupby(["uid", "__time"], observed=True)["base_units"].sum()
        tmap = {(u, t): v for (u, t), v in truth.items()}
        dmap = {pd.Timestamp(d).tz_localize(None): h for h, d in enumerate(fw, 1)}

        rows = {n: {h: ([], []) for h in range(1, H + 1)} for n in names + ["flat"]}
        last = hist.groupby("uid")["base_units"].last().to_dict()
        for r in fc.itertuples(index=False):
            h = dmap.get(pd.Timestamp(r.ds))
            if h is None:
                continue
            key = (r.unique_id, [d for d in fw if pd.Timestamp(d).tz_localize(None) == pd.Timestamp(r.ds)][0])
            a = tmap.get(key)
            if a is None:
                continue
            for n in names:
                rows[n][h][0].append(a)
                rows[n][h][1].append(max(0.0, float(getattr(r, n))))
            rows["flat"][h][0].append(a)
            rows["flat"][h][1].append(float(last.get(r.unique_id, 0.0)))

        fold = {}
        for n in names + ["flat"]:
            fold[n] = {}
            for h in range(1, H + 1):
                a, p = rows[n][h]
                if not a:
                    fold[n][h] = (float("nan"), float("nan"), 0); continue
                a_, p_ = np.array(a), np.array(p)
                fold[n][h] = (float(np.abs(a_ - p_).sum() / np.abs(a_).sum() * 100),
                              float(p_.sum() / a_.sum()), len(a_))
        per_fold.append(fold)
        print(f"  fold {str(cut.date())} done - {len(keep):,} series fitted")

    print(f"\n  {'h':>3s} " + " ".join(f"{n:>16s}" for n in names + ["flat"]))
    curve = {}
    for h in range(1, H + 1):
        cells, curve[h] = [], {}
        for n in names + ["flat"]:
            w = np.nanmean([f[n][h][0] for f in per_fold])
            b = np.nanmean([f[n][h][1] for f in per_fold])
            curve[h][n] = {"wmape": float(w), "bias": float(b)}
            cells.append(f"{w:>9.1f} {b:>6.3f}")
        print(f"  {h:>3d} " + " ".join(cells))

    print(f"\n  {'arm':<14s} {'mean wMAPE':>11s}   vs MO_103: direct 32.83 / flat 32.95 / recursive 36.44")
    overall = {}
    for n in names + ["flat"]:
        v = float(np.nanmean([np.nanmean([f[n][h][0] for h in range(1, H + 1)])
                              for f in per_fold]))
        overall[n] = v
        print(f"  {n:<14s} {v:>11.2f}")

    OUT.write_text(json.dumps({"curve": curve, "overall": overall}, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
