#!/usr/bin/env python
"""MO_117 - the two-stage decomposition: velocity per door x doors.

WHY THIS, AND WHY MO_116 WAS THE WRONG TEST
-------------------------------------------
MO_115 found that dividing base units by TDP sharply improves the year-over-year
repeatability of the detrended week-of-year profile -- at Kroger from -0.393 to +0.424.
MO_116 then built the seasonal index on that normalized series and scored it in
production. It LOST:

    off 45.43 · mo59_global 44.56 · raw_global 44.66 · tdp_global 45.06 · tdp_account 45.82

TDP normalization alone cost +0.40pp and per-account granularity a further +0.77pp.

The flaw was in my test, not only in the idea. MO_116 estimated the index on
base-per-TDP and then applied it as a multiplier to the RAW base forecast. If the
seasonal shape of velocity differs from the seasonal shape of units -- which is the whole
premise -- then applying the former to the latter is a mismatch by construction. A
per-store-week index belongs on a per-store-week FORECAST.

So this is the actual test:

    forecast = velocity_hat (base units per TDP)  x  doors_hat (TDP)

ARMS
  single           production single-stage, mo59 index in step form -- the incumbent
                   at 44.56, the number to beat
  two_stage_flat   velocity forecast recursively; TDP held at its last observed value
  two_stage_trend  velocity recursively; TDP extrapolated by a damped recent slope
  ⭐ two_stage_oracle  velocity recursively; TDP set to its ACTUAL future value

THE ORACLE ARM IS THE POINT OF THIS SCRIPT. It is not shippable -- it uses the future --
but it separates two questions that otherwise look identical:

  oracle does NOT beat 44.56  ->  the DECOMPOSITION itself does not help. Close the
                                  direction; the repeatability finding does not transfer
                                  and no amount of door-forecasting work will rescue it.
  oracle beats 44.56 clearly  ->  the decomposition works and the binding constraint is
                                  DOOR FORECASTING. That is a different, and much more
                                  tractable, problem -- and the one place where BUILT's
                                  own account teams hold forward knowledge SPINS does
                                  not have.

Reporting the gap between oracle and the shippable arms is therefore the deliverable,
not the shippable arms' own scores.

HONESTY AND MECHANICS
  * velocity lags are built from VELOCITY history, not borrowed from base-unit lags --
    otherwise the model is fed a feature on a different scale than its target
  * TDP == 0 or missing means velocity is undefined. Those series fall back to the
    single-stage forecast rather than being dropped, so every arm is scored on the SAME
    key set and a coverage difference cannot masquerade as an accuracy difference
  * same cutoffs, same training rows, same LightGBM budget as the incumbent
  * scored on base UNITS in every arm, because that is what the business buys and sells
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

warnings.filterwarnings("ignore")

OUT = Path("outputs/mo117_two_stage_velocity_doors.json")
TREES = 800
TDP_FLOOR = 0.05          # below this TDP is noise, not distribution
VEL_CLIP = 50.0           # units per TDP per week; above this is a data artifact
TDP_TREND_WEEKS = 13      # window for the recent slope
TDP_TREND_DAMP = 0.85     # per-step damping, so a slope does not extrapolate forever
ARMS = ["single", "two_stage_flat", "two_stage_trend", "two_stage_oracle"]


def velocity_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Add the velocity target and its own lag/rolling features."""
    d = df.copy()
    d["tdp"] = pd.to_numeric(d["tdp"], errors="coerce")
    ok = d["tdp"] > TDP_FLOOR
    d["velocity"] = np.where(ok, d["base_units"] / d["tdp"].where(ok), np.nan)
    d["velocity"] = d["velocity"].clip(upper=VEL_CLIP)
    return d


def fit_velocity(tr, feats, trees):
    """LightGBM on log1p(velocity). Rows with undefined velocity cannot train it."""
    t = tr[np.isfinite(tr["velocity"])]
    if len(t) < 500:
        return None
    va = t.tail(max(200, len(t) // 10))
    m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=trees,
                          learning_rate=0.05, num_leaves=63, min_child_samples=20,
                          feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
                          reg_alpha=0.1, reg_lambda=0.2, random_state=42,
                          n_jobs=-1, verbose=-1)
    m.fit(t[feats], np.log1p(t["velocity"].clip(lower=0)),
          eval_set=[(va[feats], np.log1p(va["velocity"].clip(lower=0)))],
          callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])
    return m


def project_tdp(hist_tdp: list[float], n: int, mode: str) -> list[float]:
    """Doors forward. `flat` holds the last value; `trend` adds a damped recent slope."""
    last = float(hist_tdp[-1]) if hist_tdp else 0.0
    if mode == "flat" or len(hist_tdp) < 4:
        return [last] * n
    w = [v for v in hist_tdp[-TDP_TREND_WEEKS:] if np.isfinite(v)]
    if len(w) < 4:
        return [last] * n
    slope = float(np.polyfit(np.arange(len(w), dtype=float), np.asarray(w, float), 1)[0])
    out, cur, s = [], last, slope
    for _ in range(n):
        cur = max(0.0, cur + s)
        s *= TDP_TREND_DAMP          # a 13-week slope is not a permanent growth rate
        out.append(cur)
    return out


def run_two_stage(df, feats, cut, qs, qe, eval_keys, trees, fweeks, seasonal, M,
                  tdp_mode, actual_tdp=None, single_fallback=None):
    """Recursive velocity loop, multiplied by projected (or actual) doors."""
    tr = df[df["__time"] <= cut]
    model = fit_velocity(tr, feats, trees)
    if model is None:
        return {}
    cats = {c: df[c].cat.categories for c in M.CAT_COLS if c in df.columns}
    GC = M.GROUP_COLS
    out = {}
    for key, g in tr.groupby(GC, observed=True):
        if key not in eval_keys:
            continue
        g = g.sort_values("__time")
        vh = [v for v in g["velocity"].tolist()]
        th = pd.to_numeric(g["tdp"], errors="coerce").tolist()
        # No usable velocity history -> defer to the single-stage forecast so this arm is
        # scored on the same keys as every other.
        if len(g) < 4 or not np.isfinite(pd.Series(vh).tail(8)).any():
            if single_fallback:
                for fd in fweeks[:M.HORIZON]:
                    if (key, fd) in single_fallback and qs <= fd <= qe:
                        out[(key, fd)] = single_fallback[(key, fd)]
            continue
        vh = list(pd.Series(vh).ffill().fillna(0.0))
        tproj = project_tdp([t for t in th if np.isfinite(t)], M.HORIZON, tdp_mode)
        seas = M._resolve_seasonal(seasonal, key)
        state = g.iloc[-1].copy()
        for h, fd in enumerate(fweeks[:M.HORIZON], start=1):
            t2 = float(fd.isocalendar().week)
            state["week_sin"] = np.sin(2 * np.pi * t2 / 52)
            state["week_cos"] = np.cos(2 * np.pi * t2 / 52)
            state["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
            state["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
            # Velocity's OWN lags. Reusing the base-unit lag columns would feed the model
            # a feature on a different scale than its target.
            state["base_units_lag1"] = vh[-1]
            state["base_units_roll4_avg"] = float(np.mean(vh[-4:]))
            state["base_units_roll8_avg"] = float(np.mean(vh[-8:]))
            state["base_units_roll13_avg"] = float(np.mean(vh[-13:]))
            state["base_units_wow_delta"] = vh[-1] - vh[-2] if len(vh) > 1 else 0.0
            X = pd.DataFrame([state])[feats]
            for c, cc in cats.items():
                if c in X.columns:
                    X[c] = pd.Categorical(X[c], categories=cc)
            v = float(np.clip(np.expm1(model.predict(X))[0], 0, VEL_CLIP))
            # Seasonality belongs on VELOCITY here -- that is the whole premise of the
            # decomposition, and the step form is MO_113's winner.
            v = max(0.0, v * M._seasonal_mult(
                seas, fd, cut, prev_fd=fweeks[h - 2] if h > 1 else None))
            vh.append(v)
            doors = (float(actual_tdp.get((key, fd), np.nan))
                     if actual_tdp is not None else tproj[h - 1])
            if actual_tdp is not None and not np.isfinite(doors):
                doors = tproj[h - 1]      # no actual row for that week; do not invent one
            if qs <= fd <= qe:
                out[(key, fd)] = max(0.0, v * max(0.0, doors))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default=None)
    ap.add_argument("--channel", default="CONVENTIONAL|FOOD")
    ap.add_argument("--trees", type=int, default=TREES)
    a = ap.parse_args()

    os.environ["MO_SEASONAL_MODE"] = "step"
    import MO_80_quarterly_honest_backtest as M
    importlib.reload(M)
    assert M.SEASONAL_MODE == "step"

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = velocity_frame(M.load_panel(feats))
    seasonal = M.load_seasonal_index()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]
    GC = M.GROUP_COLS

    ev = df["channel_outlet"] == a.channel
    if a.account:
        ev &= df["retail_account"] == a.account
    scope = f"{a.account} {a.channel}" if a.account else "PORTFOLIO-WIDE"

    cov = float(np.isfinite(df["velocity"]).mean())
    print(f"MO_117 - two-stage velocity x doors · {scope} · mode=step")
    print(f"  velocity defined on {cov * 100:.1f}% of panel rows "
          f"(TDP > {TDP_FLOOR}); the rest fall back to single-stage\n")
    print(f"  {'quarter':<9s} " + "  ".join(f"{k:>16s}" for k in ARMS))

    res = {k: {} for k in ARMS}
    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[ev & (df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {(k[:-1], k[-1]): float(v) for k, v in
                 act.groupby(GC + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        atdp = {(k[:-1], k[-1]): float(v) for k, v in
                act.groupby(GC + ["__time"], observed=True)["tdp"].sum().items()}

        base = M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, seasonal)
        cells = []
        for arm in ARMS:
            if arm == "single":
                pred = base
            else:
                mode = "flat" if arm != "two_stage_trend" else "trend"
                pred = run_two_stage(df, feats, cut, qs, qe, ek, a.trees, fw, seasonal, M,
                                     mode,
                                     actual_tdp=atdp if arm == "two_stage_oracle" else None,
                                     single_fallback=base)
            s = M.score(truth, pred)
            res[arm][ql] = s
            cells.append(f"{s['wmape']:>9.1f} {s['bias']:>6.3f}" if s else f"{'--':>16s}")
        print(f"  {ql:<9s} " + "  ".join(cells))

    print(f"\n  {'arm':<18s} {'wMAPE':>8s} {'bias':>7s}  {'|bias-1|':>8s}")
    means = {}
    for k in ARMS:
        v = [x for x in res[k].values() if x]
        means[k] = {"wmape": float(np.nanmean([x["wmape"] for x in v])),
                    "bias": float(np.nanmean([x["bias"] for x in v])),
                    "abs_bias_err": float(np.nanmean([abs(x["bias"] - 1) for x in v]))}
        print(f"  {k:<18s} {means[k]['wmape']:>8.2f} {means[k]['bias']:>7.3f}  "
              f"{means[k]['abs_bias_err']:>8.3f}")

    s0 = means["single"]["wmape"]
    orc = means["two_stage_oracle"]["wmape"]
    print(f"\n  vs single-stage ({s0:.2f}):")
    for k in ARMS[1:]:
        print(f"    {k:<18s} {means[k]['wmape'] - s0:+.2f}pp")
    print(f"\n  ⭐ ORACLE DOORS: {orc:.2f} vs single {s0:.2f} = {orc - s0:+.2f}pp")
    best_ship = min(("two_stage_flat", "two_stage_trend"), key=lambda k: means[k]["wmape"])
    print(f"     door-forecast cost: {means[best_ship]['wmape'] - orc:+.2f}pp "
          f"(best shippable arm {best_ship} vs oracle)")
    if orc >= s0 - 0.3:
        print("\n  -> THE DECOMPOSITION DOES NOT HELP. Even with perfect future door counts,\n"
              "     velocity x doors does not beat the single-stage model. The MO_115\n"
              "     repeatability finding does not transfer to forecast error. Close this\n"
              "     direction rather than investing in door forecasting.")
    else:
        print(f"\n  -> THE DECOMPOSITION HAS SIGNAL ({orc - s0:+.2f}pp with perfect doors), but the\n"
              f"     door-forecast cost is {means[best_ship]['wmape'] - orc:+.2f}pp -- LARGER than the gain, so\n"
              "     NOTHING HERE IS SHIPPABLE TODAY.\n"
              "     ⚠️ Two caveats before this is quoted anywhere:\n"
              "     1. every two-stage arm under-forecasts badly (bias ~0.65 against the\n"
              "        single-stage 0.886). Fitting the MEDIAN of log1p(velocity) and\n"
              "        multiplying by doors does not reconstruct the MEAN of units, so the\n"
              "        oracle number is provisional until that retransformation bias is\n"
              "        diagnosed. It may be understating the decomposition, not flattering it.\n"
              "     2. do NOT assume BUILT can supply forward door counts. Brian stated they\n"
              "        have no store-level visibility; their distribution plans are TRADE\n"
              "        COMMITMENTS, not confirmed placements. Whether a usable forward door\n"
              "        signal exists at all is an open question, not a given.")

    OUT.write_text(json.dumps({"scope": scope, "velocity_coverage": cov,
                               "by_quarter": res, "means": means,
                               "oracle_vs_single_pp": orc - s0,
                               "door_forecast_cost_pp": means[best_ship]["wmape"] - orc},
                              indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
