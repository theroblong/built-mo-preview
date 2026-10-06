#!/usr/bin/env python
"""MO_110 - Prophet, retested because MO_109 invalidated the result that closed it.

WHY THIS IS BEING REOPENED
--------------------------
`project_extrapolation_and_seasonal_methods` closed Prophet on the grounds that
"seasonality does not repeat" -- median per-series year-over-year correlation
+0.079, only 4% of series above 0.6, so Prophet would fit noise. That measurement
was taken at PER-SERIES WEEKLY granularity. Two things have since changed:

  1. Jason pushed back correctly: at MONTHLY AGGREGATE granularity seasonality
     plainly does repeat -- March is positive in all three observed years, with
     correlations up to +0.704, and every January ramps UP.
  2. MO_109 found the seasonal factor was applied against the wrong reference
     point. Every prior seasonal result -- including the ones used to close this
     avenue -- was measured through a sign error.

So the honest position is that Prophet has not actually been tested at the
granularity where the signal exists.

THE DESIGN POINT
----------------
Prophet is used here the way the data supports, not the way the suggestion framed
it. A 70/30 LightGBM/Prophet blend fits Prophet PER SERIES, where the noise
objection still stands. The defensible use is to learn the SHAPE on the aggregate,
where it is measurable, and apply it per series as an anchor-relative multiplier --
exactly the slot the STL index occupies today, but with a TREND term the STL index
does not have. BUILT grew ~20x across this window and the recursive loop freezes
every distribution feature, so a trend term is the one thing Prophet brings that
nothing in production has.

PART 1 - multiplier source (same model, same loop, only the multiplier differs)
  none             no seasonal factor
  monthly_anchor   MO_100 monthly index, anchor-relative (the MO_109 incumbent)
  prophet_yearly   Prophet yearly component only, anchor-relative. Isolates SHAPE.
  prophet_full     Prophet yhat ratio: trend AND yearly. Adds GROWTH extrapolation.
  prophet_cohort   prophet_full, but the aggregate is built from the CONTINUING
                   cohort only (series with >=52wk history at the cutoff).
                   ** This arm exists because of a trap: 61% of portfolio growth is
                   NEW series appearing (project_growth_is_distribution). An
                   aggregate trend fitted over all series embeds that arrival
                   growth, and applying it to continuing series double-counts it.
                   The cohort aggregate is the like-for-like trend. **

PART 2 - Prophet as a forecaster, and the blend claim, scored directly
  per-series Prophet on the series carrying most volume, then
  w*prophet + (1-w)*lgbm for w in 0, 0.25, 0.3, 0.5, 0.7, 0.75, 1.0
  (0.3 is there because "70% LightGBM + 30% Prophet" was the specific proposal.)

Honesty constraints held throughout: Prophet is fitted ONLY on data <= cutoff, once
per quarter; the multiplier is anchor-relative by construction; the LightGBM arm and
every Prophet arm see identical training rows.
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

warnings.filterwarnings("ignore")
for _n in ("cmdstanpy", "prophet", "numexpr"):
    logging.getLogger(_n).setLevel(logging.CRITICAL)

from prophet import Prophet

import MO_80_quarterly_honest_backtest as M
import MO_100_monthly_seasonal_index as S
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo110_prophet.json")
TREES = 1200
BASE = dict(num_leaves=63, min_child_samples=20, learning_rate=0.05,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
            reg_alpha=0.1, reg_lambda=0.2, random_state=42, n_jobs=-1,
            verbose=-1, alpha=0.5)

# Weekly data over <3 years. Prophet's default yearly Fourier order of 10 has 20 free
# parameters for ~150 points and will happily fit noise; 6 is the usual weekly-data
# compromise. changepoint_prior_scale is raised from 0.05 because the series really
# does bend -- BUILT's growth is not a straight line -- but not so far that the trend
# chases the last few weeks.
PROPHET_KW = dict(weekly_seasonality=False, daily_seasonality=False,
                  yearly_seasonality=6, seasonality_mode="multiplicative",
                  changepoint_prior_scale=0.10, interval_width=0.8)
MULT_FLOOR, MULT_CEIL = 0.5, 2.0   # a multiplier outside this is a fit failure, not a forecast
BLEND_W = [0.0, 0.25, 0.30, 0.50, 0.70, 0.75, 1.0]
PART2_VOLUME_SHARE = 0.80          # per-series Prophet on the series carrying this much volume
PART2_MAX_SERIES = 200


# ── Prophet multipliers, learned on an aggregate ──────────────────────────────
def _fit_prophet(agg: pd.DataFrame):
    if len(agg) < 60 or (agg["y"] <= 0).all():
        return None
    try:
        m = Prophet(**PROPHET_KW)
        m.fit(agg)
        return m
    except Exception:
        return None


def prophet_multipliers(df, cut, fweeks, cohort_only=False):
    """{date: (yearly_mult, full_mult)} anchored on the cutoff week.

    Returned multipliers are RATIOS to the anchor by construction, so there is no way
    to reintroduce the MO_109 reference-point error here.
    """
    tr = df[df["__time"] <= cut]
    if cohort_only:
        # Series with >=52 weeks at the cutoff. Their aggregate grows only by
        # like-for-like velocity, not by new cells arriving.
        cnt = tr.groupby(GROUP_COLS, observed=True)["base_units"].count()
        keep = set(cnt[cnt >= 52].index)
        if len(keep) < 20:
            return {}
        idx = pd.MultiIndex.from_frame(tr[GROUP_COLS])
        tr = tr[idx.isin(keep)]
    agg = (tr.groupby("__time", as_index=False)["base_units"].sum()
             .rename(columns={"__time": "ds", "base_units": "y"}))
    agg["ds"] = agg["ds"].dt.tz_localize(None)
    m = _fit_prophet(agg)
    if m is None:
        return {}
    anchor = pd.Timestamp(cut).tz_localize(None)
    fut = pd.DataFrame({"ds": [anchor] + [pd.Timestamp(d).tz_localize(None) for d in fweeks]})
    try:
        fc = m.predict(fut).set_index("ds")
    except Exception:
        return {}
    if anchor not in fc.index:
        return {}
    a_year = 1.0 + float(fc.loc[anchor, "yearly"]) if "yearly" in fc else 1.0
    a_yhat = float(fc.loc[anchor, "yhat"])
    out = {}
    for d in fweeks:
        ds = pd.Timestamp(d).tz_localize(None)
        if ds not in fc.index:
            continue
        y = 1.0 + float(fc.loc[ds, "yearly"]) if "yearly" in fc else 1.0
        yh = float(fc.loc[ds, "yhat"])
        ym = y / a_year if a_year > 0 else 1.0
        fm = yh / a_yhat if a_yhat > 0 else 1.0
        out[d] = (float(np.clip(ym, MULT_FLOOR, MULT_CEIL)),
                  float(np.clip(fm, MULT_FLOOR, MULT_CEIL)))
    return out


# ── the shared recursive loop; ONLY the multiplier varies ─────────────────────
def fit_lgbm(df, feats, cut):
    tr = df[df["__time"] <= cut]
    va = tr.tail(max(200, len(tr) // 10))
    m = lgb.LGBMRegressor(objective="quantile", n_estimators=TREES, **BASE)
    m.fit(tr[feats], np.log1p(tr["base_units"]),
          eval_set=[(va[feats], np.log1p(va["base_units"]))],
          callbacks=[lgb.early_stopping(80, verbose=False), lgb.log_evaluation(-1)])
    return m, tr


def recursive(model, tr, feats, cats, qs, qe, eval_keys, fweeks, mult_fn):
    out = {}
    for key, g in tr.groupby(GROUP_COLS, observed=True):
        if key not in eval_keys:
            continue
        g = g.sort_values("__time")
        if len(g) < 4:
            continue
        hist = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
        state = g.iloc[-1].copy()
        for fd in fweeks[:M.HORIZON]:
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
            p = float(np.clip(np.expm1(model.predict(X))[0], 0, None))
            p = max(0.0, p * mult_fn(fd))
            hist.append(p)
            if qs <= fd <= qe:
                out[(key, fd)] = p
    return out


# ── Part 2: Prophet per series, and the blend ────────────────────────────────
def prophet_per_series(tr, keys, fweeks, qs, qe):
    out = {}
    fut = pd.DataFrame({"ds": [pd.Timestamp(d).tz_localize(None) for d in fweeks]})
    for key, g in tr.groupby(GROUP_COLS, observed=True):
        if key not in keys:
            continue
        g = g.sort_values("__time")
        agg = pd.DataFrame({"ds": g["__time"].dt.tz_localize(None),
                            "y": pd.to_numeric(g["base_units"], errors="coerce").fillna(0)})
        kw = dict(PROPHET_KW)
        # Below two years there is not enough of a second cycle to identify a yearly
        # term; asking for one guarantees it fits noise.
        if len(agg) < 104:
            kw["yearly_seasonality"] = False
        if (agg["y"] <= 0).any():
            kw["seasonality_mode"] = "additive"   # multiplicative needs y>0
        try:
            m = Prophet(**kw)
            m.fit(agg)
            fc = m.predict(fut).set_index("ds")
        except Exception:
            continue
        for d in fweeks:
            ds = pd.Timestamp(d).tz_localize(None)
            if ds in fc.index and qs <= d <= qe:
                out[(key, d)] = max(0.0, float(fc.loc[ds, "yhat"]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-part2", action="store_true")
    ap.add_argument("--part2-account", default=None,
                    help="restrict part 2 to one account instead of top-volume series")
    a = ap.parse_args()

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    raw = S.load_panel()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    cats = {c: df[c].cat.categories for c in CAT_COLS if c in df.columns}
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]

    arms = ["none", "monthly_anchor", "prophet_yearly", "prophet_full", "prophet_cohort"]
    acc = {k: [] for k in arms}
    detail = {}
    blend_acc = {w: [] for w in BLEND_W}

    print("MO_110 - Prophet trend and seasonality, portfolio-wide, honest folds\n")
    print("PART 1 - multiplier source (identical model and loop in every arm)\n")
    print(f"  {'quarter':<9s} " + " ".join(f"{k:>15s}" for k in arms))

    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        truth = {(k[:-1], k[-1]): float(v) for k, v in
                 act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)

        # monthly index, built honestly from data <= cutoff, anchor-relative
        mi, _ = S.monthly_index(raw, cutoff=cut, verbose=False)
        midx = {}
        if mi:
            wk = S.to_weekly(mi)
            midx = dict(zip(wk["week_of_year"].astype(int), wk["seasonal_index"]))
        a_idx = 1.0 + midx.get(int(pd.Timestamp(cut).isocalendar().week), 0.0)

        pm_all = prophet_multipliers(df, cut, fw, cohort_only=False)
        pm_coh = prophet_multipliers(df, cut, fw, cohort_only=True)

        model, tr = fit_lgbm(df, feats, cut)
        mult_fns = {
            "none": lambda d: 1.0,
            "monthly_anchor": lambda d: max(0.1, (1.0 + midx.get(int(d.isocalendar().week), 0.0)) / a_idx) if (midx and a_idx > 0) else 1.0,
            "prophet_yearly": lambda d: pm_all.get(d, (1.0, 1.0))[0],
            "prophet_full": lambda d: pm_all.get(d, (1.0, 1.0))[1],
            "prophet_cohort": lambda d: pm_coh.get(d, (1.0, 1.0))[1],
        }

        row, cells = {}, []
        preds = {}
        for k in arms:
            pred = recursive(model, tr, feats, cats, qs, qe, ek, fw, mult_fns[k])
            preds[k] = pred
            s = M.score(truth, pred)
            row[k] = s
            acc[k].append((s["wmape"], s["bias"]) if s else (np.nan, np.nan))
            cells.append(f"{s['wmape']:>8.1f} {s['bias']:>6.3f}" if s else f"{'--':>15s}")
        detail[ql] = row
        print(f"  {ql:<9s} " + " ".join(cells))

        # ── Part 2, same fold: Prophet per series and the blend ──────────────
        if a.skip_part2:
            continue
        if a.part2_account:
            sub = {k for k in ek if k[1] == a.part2_account} or ek
        else:
            vol = (act.groupby(GROUP_COLS, observed=True)["base_units"].sum()
                      .sort_values(ascending=False))
            cum = vol.cumsum() / vol.sum()
            sub = set(vol.index[:max(1, min(PART2_MAX_SERIES,
                                            int((cum <= PART2_VOLUME_SHARE).sum()) + 1))])
        pp = prophet_per_series(tr, sub, fw, qs, qe)
        lg = preds["none"]
        common = [k for k in truth if k in pp and k in lg]
        if common:
            A = np.array([truth[k] for k in common])
            P = np.array([pp[k] for k in common])
            L = np.array([lg[k] for k in common])
            for w in BLEND_W:
                B = w * P + (1 - w) * L
                blend_acc[w].append(M.wmape(A, B))
            detail[ql]["_part2"] = {"n_series": len(sub), "n_points": len(common),
                                    "vol_share": float(A.sum() / sum(truth.values()))}

    print(f"\n  {'arm':<16s} {'wMAPE':>8s} {'bias':>7s}")
    means = {}
    for k in arms:
        w = np.nanmean([x[0] for x in acc[k]]); b = np.nanmean([x[1] for x in acc[k]])
        means[k] = {"wmape": float(w), "bias": float(b)}
        print(f"  {k:<16s} {w:>8.2f} {b:>7.3f}")
    best = min(arms, key=lambda k: means[k]["wmape"])
    print(f"\n  BEST multiplier source: {best} ({means[best]['wmape']:.2f})")
    for k in ("prophet_yearly", "prophet_full", "prophet_cohort"):
        print(f"    {k:<15s} vs monthly_anchor {means[k]['wmape'] - means['monthly_anchor']['wmape']:+.2f}pp"
              f"   vs none {means[k]['wmape'] - means['none']['wmape']:+.2f}pp")

    blend_means = {}
    if not a.skip_part2 and any(blend_acc[w] for w in BLEND_W):
        print("\nPART 2 - Prophet per series, and the blend "
              f"(top-volume series, {len(blend_acc[0.0])} folds)\n")
        print(f"  {'w (Prophet weight)':<20s} {'wMAPE':>8s}")
        for w in BLEND_W:
            if not blend_acc[w]:
                continue
            v = float(np.nanmean(blend_acc[w]))
            blend_means[w] = v
            tag = ""
            if w == 0.0:
                tag = "  <- LightGBM alone"
            elif w == 1.0:
                tag = "  <- Prophet alone"
            elif w == 0.30:
                tag = "  <- the proposed 70/30"
            print(f"  {w:<20.2f} {v:>8.2f}{tag}")
        if blend_means:
            bw = min(blend_means, key=blend_means.get)
            print(f"\n  BEST w = {bw:.2f} ({blend_means[bw]:.2f}); "
                  f"LightGBM alone {blend_means[0.0]:.2f}, "
                  f"the proposed 0.30 {blend_means.get(0.30, float('nan')):.2f}")
            if bw == 0.0:
                print("  -> no blend weight beats LightGBM alone. The 70/30 proposal is refuted "
                      "on our data.")

    OUT.write_text(json.dumps({"part1": {"by_quarter": detail, "means": means},
                               "part2_blend": blend_means}, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
