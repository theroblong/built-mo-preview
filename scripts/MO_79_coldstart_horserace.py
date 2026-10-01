"""MO_79 — Cold-start horse race: what should forecast a short-history series?

THE QUESTION
------------
MO_27 gated every series with <13 weeks of history out of the forecast entirely: 473 of
2,137 series, spanning 110 of 133 focal UPCs, returned nothing. That is unacceptable for a
brand whose growth comes from new flavours, new pack sizes and new doors — those are exactly
the series a planner needs a number for.

It has now been replaced by a carry-forward path (level x lifecycle ramp x seasonal index).
But "better than a blank" is a low bar. This script measures which method is actually best,
per history band, against held-out actuals.

Judging the gap by share of HISTORICAL volume is circular — new items are small today BECAUSE
they are new. So this reports units AND series counts per band and never ranks a band by its
current volume share.

WHY THIS AND NOT THE EXISTING BENCHMARKS
----------------------------------------
MO_62 (Chronos/TimesFM/Moirai/Granite) and MO_65 (AutoGluon) both set MIN_HISTORY = 52, so
every foundation-model result we have was measured on MATURE series. That is the regime where
domain features win by construction (6% vs 30-60% wMAPE) and it says NOTHING about the band
this script is about. MO_34 compared LightGBM vs ETS but on the old CRMA-inflated panel and
with series eligibility defined on full history.

STAGE A (this file) is deliberately the cheap arms only — naive, window average, drift,
ETS-Holt, the shipped carry-forward, and a donor surrogate. Never deploy a complex model
without first knowing what a heuristic scores. Stage B (MO_79b) adds Chronos-2 and the
production LightGBM recursive path, scored on this same harness, once the bar is known.

LEAKAGE DISCIPLINE (the part that makes or breaks a backtest)
-------------------------------------------------------------
Every arm sees ONLY data at or before the cutoff. Specifically:
  * band eligibility is `weeks of history AS OF THE CUTOFF`, never full-panel history.
    Using full-panel history would let a series that is mature today be scored as if it had
    been new, which is the single easiest way to fake a cold-start result.
  * the lifecycle ramp curve is refitted per cutoff on pre-cutoff rows only.
  * the seasonal index is refitted per cutoff on pre-cutoff rows only. NOTE: this is a cheap
    volume-weighted week-of-year index, NOT the production MO_59 STL index, because the
    production index is fitted on the full panel and would leak the holdout. Numbers here are
    therefore not directly comparable to production wMAPE; the comparison BETWEEN ARMS is the
    point, and all arms share the same index.
  * donor series are truncated at the cutoff before their shape is borrowed.

Run:  python MO_79_coldstart_horserace.py [--horizon 13] [--cutoffs 13,26,39,52]
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from mo_panel import (GROUP_COLS, fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_ak_hi_market_variants, warn_nested_rma_duplicates,
                      drop_zero_volume_geographies, apply_rma_priority)

warnings.filterwarnings("ignore")

PARQUET  = Path("outputs/retailer_sales_weekly.parquet")
OUT_JSON = Path("outputs/mo79_coldstart_horserace.json")
OUT_CSV  = Path("outputs/mo79_coldstart_per_series.csv")

# Bands are defined on weeks of history AT THE CUTOFF. 13 is MIN_SERIES_WEEKS (the old gate)
# and 52 is the YAGO threshold, so the bands line up with the two real cliffs in the pipeline.
BANDS = [("1-4", 1, 4), ("5-12", 5, 12), ("13-25", 13, 25), ("26-51", 26, 51), ("52+", 52, 10**6)]

MIN_TEST_WEEKS = 4        # need enough holdout to be worth scoring
RAMP_MAX_WEEK  = 80


# ── metrics ──────────────────────────────────────────────────────────────────
def wmape(a: np.ndarray, f: np.ndarray) -> float:
    d = np.abs(a).sum()
    return float(np.abs(a - f).sum() / d * 100) if d > 0 else float("nan")


def bias(a: np.ndarray, f: np.ndarray) -> float:
    d = a.sum()
    return float((f.sum() - d) / d * 100) if d > 0 else float("nan")


# ── pre-cutoff fits (refit per cutoff; never see the holdout) ────────────────
def fit_ramp(hist: pd.DataFrame) -> dict[int, float]:
    """Median demand index by weeks_since_launch, each series normalised to its own wks 5-8.

    This is the same construction MO_27 uses in production, but refitted on pre-cutoff rows
    so the backtest cannot borrow the future.
    """
    p = hist[hist["weeks_since_launch"].between(1, RAMP_MAX_WEEK)].copy()
    if not len(p):
        return {}
    b = (p[p["weeks_since_launch"].between(5, 8)]
         .groupby(GROUP_COLS, observed=True)["base_units"].mean().rename("_b"))
    p = p.merge(b, on=GROUP_COLS, how="inner")
    p = p[p["_b"] > 0]
    if not len(p):
        return {}
    p["_n"] = p["base_units"] / p["_b"]
    return (p.groupby(p["weeks_since_launch"].astype(int))["_n"]
            .median().clip(0.2, 5.0).to_dict())


def fit_seasonal(hist: pd.DataFrame) -> dict[int, float]:
    """Volume-weighted week-of-year index, centred at zero, from pre-cutoff rows only.

    Each series is normalised by its OWN mean so a big retailer does not simply set the shape,
    then weighted by that mean so a 3-unit series does not count as much as a 30,000-unit one.
    Deliberately not STL: with ~2-3 annual cycles STL is numerically fragile per series, and
    the production STL index is fitted on the full panel and would leak here.
    """
    h = hist[hist["base_units"] > 0].copy()
    if not len(h):
        return {}
    lvl = h.groupby(GROUP_COLS, observed=True)["base_units"].transform("mean")
    h = h[lvl > 0]
    if not len(h):
        return {}
    h["_norm"] = h["base_units"] / lvl
    h["_w"] = lvl[h.index]
    g = h.groupby(h["week_of_year"].astype(int)).apply(
        lambda d: np.average(d["_norm"], weights=d["_w"]))
    g = g.reindex(range(1, 54)).interpolate().bfill().ffill()
    g = g - g.mean()
    return {int(k): float(v) for k, v in g.items()}


def build_donor_pool(hist: pd.DataFrame, min_weeks: int = 52) -> dict:
    """Shape donors: week-of-year profiles from series that ARE mature as of the cutoff.

    Two tiers, strongest first:
      exact  — the SAME UPC at a different account. 46 of 108 short-series UPCs have one.
               This is not a 'look-alike', it is the identical item with a real history.
      sibling— same flavour family + pack count, any UPC.
    """
    n = hist.groupby(GROUP_COLS, observed=True)["base_units"].transform("count")
    mat = hist[n >= min_weeks].copy()
    if not len(mat):
        return {"exact": {}, "sibling": {}}

    def profile(d: pd.DataFrame) -> dict[int, float]:
        lvl = d["base_units"].mean()
        if not lvl or lvl <= 0 or not np.isfinite(lvl):
            return {}
        p = d.groupby(d["week_of_year"].astype(int))["base_units"].mean() / lvl
        return {int(k): float(v) for k, v in p.items()}

    exact = {u: profile(d) for u, d in mat.groupby("upc", observed=True)}
    sibling = {}
    for key, d in mat.groupby(["spins_flavor_canonical", "pack_count"], observed=True):
        sibling[key] = profile(d)
    return {"exact": {k: v for k, v in exact.items() if v},
            "sibling": {k: v for k, v in sibling.items() if v}}


# ── the arms ─────────────────────────────────────────────────────────────────
def arm_naive(y, **_):
    return np.full(_["h"], y[-1])


def arm_window4(y, **_):
    return np.full(_["h"], float(np.mean(y[-min(4, len(y)):])))


def arm_drift(y, **_):
    """Last value plus the average per-week change, damped and floored at zero.

    Cheapest way to carry a launch ramp: with 6 weeks of history the recent slope IS the ramp,
    so this needs no lifecycle curve at all. Damped 0.9^s because an unchecked linear
    extrapolation off 6 noisy points runs away over 13 weeks.
    """
    h = _["h"]
    if len(y) < 2:
        return np.full(h, y[-1])
    k = min(8, len(y))
    slope = float(np.polyfit(np.arange(k), y[-k:], 1)[0])
    s = np.arange(1, h + 1)
    return np.maximum(0.0, y[-1] + slope * np.cumsum(0.9 ** s))


def arm_ets(y, **_):
    """Holt damped-trend. Falls back to window average when too short or non-finite."""
    h = _["h"]
    if len(y) < 4:
        return arm_window4(y, **_)
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        f = ExponentialSmoothing(np.asarray(y, dtype=float), trend="add",
                                 damped_trend=True, seasonal=None,
                                 initialization_method="estimated").fit()
        p = np.asarray(f.forecast(h), dtype=float)
        if not np.all(np.isfinite(p)):
            return arm_window4(y, **_)
        return np.maximum(0.0, p)
    except Exception:
        return arm_window4(y, **_)


def arm_carry_ramp_season(y, *, h, w0, ramp, seasonal, woys, **_):
    """The method MO_27 now ships for short series. Level x lifecycle ramp x seasonal index."""
    lvl = float(np.mean(y[-min(4, len(y)):]))
    b0 = ramp.get(w0, 1.0) or 1.0
    out = []
    for s in range(1, h + 1):
        rf = (ramp.get(w0 + s, b0) or b0) / b0
        sf = 1.0 + seasonal.get(woys[s - 1], 0.0) if seasonal else 1.0
        out.append(max(0.0, lvl * rf * max(0.1, sf)))
    return np.asarray(out)


def arm_donor(y, *, h, upc, flavour, pack, donors, woys, hist_woys, **_):
    """Borrow a mature series' week-of-year SHAPE, scale it to this series' own level.

    Level comes from this series (what we know); shape comes from the donor (what we don't).
    The donor profile is re-based on the weeks we actually observed, so we transfer the
    RELATIVE move from here to the horizon rather than the donor's absolute seasonality.
    """
    prof = donors["exact"].get(upc) or donors["sibling"].get((flavour, pack)) or {}
    if not prof:
        return arm_window4(y, h=h)
    obs = [prof[w] for w in hist_woys[-min(4, len(y)):] if w in prof]
    base = float(np.mean(obs)) if obs else float(np.mean(list(prof.values())))
    if not base or base <= 0 or not np.isfinite(base):
        return arm_window4(y, h=h)
    lvl = float(np.mean(y[-min(4, len(y)):]))
    mean_prof = float(np.mean(list(prof.values()))) or 1.0
    return np.asarray([max(0.0, lvl * (prof.get(w, mean_prof) / base)) for w in woys])


ARMS = {
    "naive_last":        arm_naive,
    "window_avg4":       arm_window4,
    "drift_damped":      arm_drift,
    "ets_holt_damped":   arm_ets,
    "carry_ramp_season": arm_carry_ramp_season,
    "donor_surrogate":   arm_donor,
}


def load_panel() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    for c in ("base_units", "weeks_since_launch", "week_of_year", "pack_count"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["base_units"])
    print("  ── Panel rules (must match MO_26/MO_27) ──")
    df = fill_promo_mechanic_nulls(df)
    df = drop_military_accounts(df)
    # AK/HI supplementary markets are nested duplicates of the base market (Circle K was
    # being counted twice). Excluded BY DEFINITION, not by their happening to be zero-volume.
    df = drop_ak_hi_market_variants(df)
    df = drop_zero_volume_geographies(df, target="base_units")
    df = apply_rma_priority(df)
    df["spins_flavor_canonical"] = df["spins_flavor_canonical"].fillna("UNKNOWN").astype(str)
    return df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


def run_cutoff(df: pd.DataFrame, cutoff: pd.Timestamp, h: int) -> pd.DataFrame:
    hist_all = df[df["__time"] <= cutoff]
    fut_all  = df[(df["__time"] > cutoff) & (df["__time"] <= cutoff + pd.Timedelta(weeks=h))]
    if not len(hist_all) or not len(fut_all):
        return pd.DataFrame()

    ramp     = fit_ramp(hist_all)
    seasonal = fit_seasonal(hist_all)
    donors   = build_donor_pool(hist_all)
    print(f"    pre-cutoff fits: ramp {len(ramp)} pts | seasonal {len(seasonal)} wks | "
          f"donors {len(donors['exact'])} exact-UPC, {len(donors['sibling'])} sibling")

    fut_g = {k: v for k, v in fut_all.groupby(GROUP_COLS, observed=True)}
    rows = []
    for keys, g in hist_all.groupby(GROUP_COLS, observed=True):
        f = fut_g.get(keys)
        if f is None or len(f) < MIN_TEST_WEEKS:
            continue
        y = g["base_units"].to_numpy(dtype=float)
        if len(y) < 1 or not np.isfinite(y).all():
            continue
        n_hist = len(y)
        last = g.iloc[-1]
        w0 = int(last["weeks_since_launch"]) if np.isfinite(last["weeks_since_launch"]) else n_hist
        woys = [int((cutoff + pd.Timedelta(weeks=s)).isocalendar().week) for s in range(1, h + 1)]
        hist_woys = [int(w) for w in g["week_of_year"].fillna(1).to_numpy()]
        kw = dict(h=h, w0=w0, ramp=ramp, seasonal=seasonal, woys=woys,
                  hist_woys=hist_woys, upc=keys[0],
                  flavour=last["spins_flavor_canonical"], pack=last["pack_count"],
                  donors=donors)

        a = f["base_units"].to_numpy(dtype=float)
        n_test = len(a)
        band = next(b for b, lo, hi in BANDS if lo <= n_hist <= hi)
        rec = {"cutoff": str(cutoff.date()), "band": band, "n_hist": n_hist,
               "n_test": n_test, "actual_units": float(a.sum()),
               "upc": keys[0], "channel_outlet": keys[1],
               "retail_account": keys[2], "geography_raw": keys[3],
               "has_exact_donor": keys[0] in donors["exact"]}
        for name, fn in ARMS.items():
            p = np.asarray(fn(y, **kw), dtype=float)[:n_test]
            rec[f"wmape_{name}"] = wmape(a, p)
            rec[f"pred_{name}"] = float(p.sum())
        rows.append(rec)
    return pd.DataFrame(rows)


def main(horizon: int, cutoffs: list[int]):
    print(f"MO_79 — cold-start horse race | horizon {horizon}w | "
          f"cutoffs {cutoffs} weeks back\n")
    df = load_panel()
    end = df["__time"].max()
    print(f"\n  Panel ends {end.date()} | {len(df):,} rows | "
          f"{df.groupby(GROUP_COLS, observed=True).ngroups:,} series | "
          f"{df['upc'].nunique()} UPCs\n")

    parts = []
    for wk in cutoffs:
        cut = end - pd.Timedelta(weeks=wk)
        print(f"  cutoff {cut.date()}  ({wk} weeks back)")
        p = run_cutoff(df, cut, horizon)
        print(f"    scored {len(p):,} series")
        parts.append(p)
    per = pd.concat(parts, ignore_index=True)
    if per.empty:
        raise SystemExit("FATAL: no series scored — check cutoffs vs panel end.")
    per.to_csv(OUT_CSV, index=False)

    arm_names = list(ARMS)
    print(f"\n{'='*104}")
    print("POOLED wMAPE BY HISTORY-AT-CUTOFF BAND  (lower is better; winner starred)")
    print(f"  {'band':>6s} {'series':>7s} {'units':>12s}  " +
          "  ".join(f"{n[:16]:>16s}" for n in arm_names))

    summary = {}
    for band, _lo, _hi in BANDS:
        d = per[per["band"] == band]
        if d.empty:
            continue
        # Pooled (unit-weighted) wMAPE: sum|a-f| / sum a across the band, reconstructed from
        # per-series totals so one large series cannot be averaged away by many tiny ones.
        vals = {}
        for n in arm_names:
            w = d[f"wmape_{n}"] * d["actual_units"]
            vals[n] = float(w.sum() / d["actual_units"].sum()) if d["actual_units"].sum() else np.nan
        best = min(vals, key=lambda k: (np.inf if np.isnan(vals[k]) else vals[k]))
        cells = "  ".join(f"{('*' if n == best else '') + f'{vals[n]:.1f}':>16s}" for n in arm_names)
        print(f"  {band:>6s} {len(d):>7,} {d['actual_units'].sum():>12,.0f}  {cells}")
        summary[band] = {"series": int(len(d)), "actual_units": float(d["actual_units"].sum()),
                         "wmape": vals, "winner": best}

    print(f"\n  PER-SERIES WIN RATE (share of series where the arm has the lowest wMAPE)")
    print(f"  {'band':>6s}  " + "  ".join(f"{n[:16]:>16s}" for n in arm_names))
    for band, _lo, _hi in BANDS:
        d = per[per["band"] == band]
        if d.empty:
            continue
        wm = d[[f"wmape_{n}" for n in arm_names]].to_numpy()
        win = np.nanargmin(np.where(np.isnan(wm), np.inf, wm), axis=1)
        share = {n: float((win == i).mean() * 100) for i, n in enumerate(arm_names)}
        summary[band]["win_rate_pct"] = share
        print(f"  {band:>6s}  " + "  ".join(f"{share[n]:>15.0f}%" for n in arm_names))

    print(f"\n  BIAS (pooled, % — positive = over-forecast)")
    print(f"  {'band':>6s}  " + "  ".join(f"{n[:16]:>16s}" for n in arm_names))
    for band, _lo, _hi in BANDS:
        d = per[per["band"] == band]
        if d.empty:
            continue
        b = {n: float((d[f"pred_{n}"].sum() - d["actual_units"].sum())
                      / d["actual_units"].sum() * 100) for n in arm_names}
        summary[band]["bias_pct"] = b
        print(f"  {band:>6s}  " + "  ".join(f"{b[n]:>+15.1f}%" for n in arm_names))

    # Does the exact-UPC donor actually beat the sibling fallback? If the donor arm only wins
    # where an exact donor exists, the tier is what matters, not the method.
    sub = per[per["band"].isin(["1-4", "5-12"])]
    if len(sub):
        print(f"\n  DONOR TIER CHECK on bands 1-4 + 5-12 (donor_surrogate wMAPE)")
        for flag, lbl in ((True, "exact UPC donor"), (False, "sibling only")):
            d = sub[sub["has_exact_donor"] == flag]
            if not len(d) or not d["actual_units"].sum():
                continue
            v = float((d["wmape_donor_surrogate"] * d["actual_units"]).sum() / d["actual_units"].sum())
            print(f"    {lbl:<18s} n={len(d):>4,}  wMAPE {v:>6.1f}")

    OUT_JSON.write_text(json.dumps({
        "horizon_weeks": horizon, "cutoffs_weeks_back": cutoffs,
        "panel_end": str(end.date()), "arms": arm_names,
        "bands": summary,
        "leakage_notes": [
            "band = weeks of history AS OF CUTOFF, not full-panel history",
            "ramp, seasonal index and donor pool all refitted per cutoff on pre-cutoff rows",
            "seasonal index is a cheap volume-weighted week-of-year index, NOT production "
            "MO_59 STL (which is full-panel fitted and would leak); all arms share it, so "
            "cross-arm comparison is valid but absolute wMAPE is not comparable to production",
        ],
        "stage": "A — cheap arms only; Stage B (MO_79b) adds Chronos-2 and production LightGBM",
    }, indent=2))
    print(f"\n  → {OUT_CSV}\n  → {OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=13)
    ap.add_argument("--cutoffs", type=str, default="13,26,39,52")
    a = ap.parse_args()
    main(a.horizon, [int(x) for x in a.cutoffs.split(",")])
