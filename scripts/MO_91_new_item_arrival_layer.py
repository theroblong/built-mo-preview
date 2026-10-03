#!/usr/bin/env python
"""MO_91 - new-item arrival layer.

Finding that motivates this: at a 13-week horizon a median 14.4% of a target
month's actual volume comes from (upc, channel, account, geography) cells that
did not exist at forecast time. No model of existing series can recover that,
so a chronic under-forecast is structural, not a tuning problem.

The asset we have is ~1,000 observed launches in 3 years of SPINS - far more
information than the 2 observed Januaries a seasonal model gets. This script
estimates, using only data available at each origin:

  arrivals/month   trailing mean count of new cells
  launch curve     mean units at age 0..12 weeks, from fully-observed cohorts

and adds  sum_L arrivals * sum_w curve[age(w, L)]  to the existing-cell total.

Arms
  A  existing cells only, flat last-4-week mean           (the current shape)
  B  A + new-cell arrival layer (count x launch curve)
  C  B + launch-curve ramp for young existing cells (<13wk) instead of flat
  D  A uplifted by a trailing-3mo realized new-cell share  (self-calibrating)
  E  same with a trailing-6mo window

D/E exist because B's count x curve estimator over-corrects once arrival count
and volume-per-arrival move in opposite directions, which is what 2026 does.
The realized-share estimator tracks that automatically: it asks what fraction of
recent months' volume came from cells that were invisible h months earlier.

Honest backtest: every quantity is estimated from data <= origin. The only
future information used is the calendar (which weeks fall in which month).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mo_panel import (
    GROUP_COLS,
    apply_rma_priority,
    drop_ak_hi_market_variants,
    drop_military_accounts,
    drop_zero_volume_geographies,
    fill_promo_mechanic_nulls,
)

PARQUET = "outputs/retailer_sales_weekly.parquet"
TARGET = "base_units"
RAMP_WEEKS = 13          # length of the launch curve
ARRIVAL_LOOKBACK = 6     # months of trailing arrivals to average
COHORT_LOOKBACK = 12     # months of launch cohorts feeding the curve
ORIGINS = pd.period_range("2025-03", "2026-05", freq="M")
ARMS = ("A", "B", "C", "D", "E")
HORIZONS = (1, 2, 3)


def load_panel() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")
    for fn in (
        fill_promo_mechanic_nulls,
        drop_military_accounts,
        drop_ak_hi_market_variants,
        apply_rma_priority,
    ):
        df = fn(df, verbose=False)
    df = drop_zero_volume_geographies(df, target=TARGET, verbose=False)
    df = df.dropna(subset=[TARGET])
    df["key"] = list(zip(*[df[c] for c in GROUP_COLS]))
    df["ym"] = df["__time"].dt.to_period("M")
    # drop partial months at either end of the file
    weeks = df.groupby("ym")["__time"].nunique()
    return df[df["ym"].isin(set(weeks[weeks >= 4].index))].copy()


def launch_curve(hist: pd.DataFrame, first: pd.Series, cut: pd.Timestamp) -> np.ndarray:
    """Mean units at age 0..RAMP_WEEKS-1, from cohorts fully observed by `cut`."""
    observed_by = cut - pd.Timedelta(weeks=RAMP_WEEKS)
    cohort_start = (cut.to_period("M") - COHORT_LOOKBACK).start_time.tz_localize("UTC")
    eligible = first[(first <= observed_by) & (first >= cohort_start)]
    if len(eligible) < 20:
        eligible = first[first <= observed_by]
    if eligible.empty:
        return np.zeros(RAMP_WEEKS)

    sub = hist[hist["key"].isin(set(eligible.index))].copy()
    sub["t0"] = sub["key"].map(eligible)
    sub = sub.dropna(subset=["t0"])
    sub["age"] = (sub["__time"] - sub["t0"]).dt.days // 7
    sub = sub[(sub["age"] >= 0) & (sub["age"] < RAMP_WEEKS)]
    # sum per (cell, age) then mean across the full cohort so absent weeks
    # count as zero rather than being silently dropped
    per = sub.groupby("age")[TARGET].sum()
    n = len(eligible)
    return np.array([per.get(a, 0.0) / n for a in range(RAMP_WEEKS)])


def arrival_rate(first: pd.Series, cut_m: pd.Period) -> float:
    months = [cut_m - i for i in range(ARRIVAL_LOOKBACK)]
    t0m = first.dt.to_period("M")
    counts = [int((t0m == m).sum()) for m in months]
    return float(np.mean(counts)) if counts else 0.0


def new_cell_volume(
    curve: np.ndarray, rate: float, origin: pd.Period, target: pd.Period,
    week_dates: list[pd.Timestamp],
) -> float:
    """Expected volume in `target` month from cells launching after `origin`."""
    total = 0.0
    launch_months = [origin + i for i in range(1, (target - origin).n + 1)]
    for lm in launch_months:
        lstart = lm.start_time.tz_localize("UTC")
        for w in week_dates:
            age = (w - lstart).days // 7
            if 0 <= age < RAMP_WEEKS:
                total += rate * curve[age]
    return total


def realized_new_share(
    hist: pd.DataFrame, first_seen: pd.Series, origin: pd.Period, h: int, window: int
) -> float:
    """Trailing mean share of a month's volume from cells unseen h months earlier.

    Estimated only on months that have already happened at `origin`, so it
    adapts when arrival count and volume-per-arrival diverge.
    """
    shares = []
    for i in range(window):
        m = origin - i
        sub = hist[hist["ym"] == m]
        if sub.empty:
            continue
        total = sub[TARGET].sum()
        if total <= 0:
            continue
        # cells that first appeared after the month h months before m
        as_of = pd.Timestamp((m - h).end_time, tz="UTC")
        unseen = set(first_seen[first_seen > as_of].index)
        shares.append(sub.loc[sub["key"].isin(unseen), TARGET].sum() / total)
    if not shares:
        return 0.0
    return float(np.mean(shares))


def main() -> None:
    df = load_panel()
    first = df.groupby("key")["__time"].min()
    all_weeks = sorted(df["__time"].unique())

    rows = []
    for origin in ORIGINS:
        cut = pd.Timestamp(origin.end_time, tz="UTC")
        hist = df[df["__time"] <= cut]
        if hist.empty:
            continue
        first_seen = hist.groupby("key")["__time"].min()
        curve = launch_curve(hist, first_seen, cut)
        rate = arrival_rate(first_seen, origin)

        # --- existing-cell level: flat mean of the last 4 observed weeks ---
        recent = hist[hist["__time"] > cut - pd.Timedelta(weeks=4)]
        flat = recent.groupby("key")[TARGET].sum() / 4.0
        age_at_cut = ((cut - first_seen).dt.days // 7)
        young = set(age_at_cut[age_at_cut < RAMP_WEEKS].index)

        for h in HORIZONS:
            target = origin + h
            wk = [pd.Timestamp(w) for w in all_weeks
                  if pd.Timestamp(w).to_period("M") == target]
            if not wk:
                continue
            actual = df.loc[df["ym"] == target, TARGET].sum()

            # A: flat carry-forward on every existing cell
            a_total = float(flat.sum()) * len(wk)

            # B: + arrival layer
            new_vol = new_cell_volume(curve, rate, origin, target, wk)
            b_total = a_total + new_vol

            # C: young existing cells continue along the launch curve
            ramp_adj = 0.0
            for k in young:
                t0 = first_seen[k]
                base = float(flat.get(k, 0.0))
                for w in wk:
                    age = (w - t0).days // 7
                    if 0 <= age < RAMP_WEEKS:
                        ramp_adj += curve[age] - base
            c_total = b_total + ramp_adj

            # D / E: uplift A by the trailing realized new-cell share
            r3 = realized_new_share(hist, first_seen, origin, h, 3)
            r6 = realized_new_share(hist, first_seen, origin, h, 6)
            d_total = a_total / (1.0 - r3) if r3 < 0.9 else a_total
            e_total = a_total / (1.0 - r6) if r6 < 0.9 else a_total

            rows.append(
                dict(origin=str(origin), h=h, target=str(target), actual=actual,
                     A=a_total, B=b_total, C=c_total, D=d_total, E=e_total,
                     new_vol=new_vol, rate=rate, curve_sum=curve.sum(),
                     r3=r3, r6=r6)
            )

    R = pd.DataFrame(rows)
    if R.empty:
        raise SystemExit("MO_91: no rows produced - check origins vs panel coverage")

    for arm in ARMS:
        R[f"e{arm}"] = (R[arm] - R["actual"]) / R["actual"]

    print("MO_91 - new-item arrival layer, honest monthly backtest")
    print(f"ramp={RAMP_WEEKS}wk  arrival_lookback={ARRIVAL_LOOKBACK}mo  "
          f"cohort_lookback={COHORT_LOOKBACK}mo\n")

    for h in HORIZONS:
        s = R[R["h"] == h]
        if s.empty:
            continue
        print(f"=== horizon T+{h} month  ({len(s)} origins) ===")
        print(f"  {'target':<9s} {'actual':>11s} "
              + " ".join(f"{a+' err':>9s}" for a in ARMS))
        for _, r in s.iterrows():
            print(f"  {r.target:<9s} {r.actual:>11,.0f} "
                  + " ".join(f"{r[f'e{a}']:>+8.1%}" for a in ARMS))
        print(f"  {'':<9s} {'median |err|':>11s} "
              + " ".join(f"{s[f'e{a}'].abs().median():>8.1%}" for a in ARMS))
        print(f"  {'':<9s} {'mean |err|':>11s} "
              + " ".join(f"{s[f'e{a}'].abs().mean():>8.1%}" for a in ARMS))
        print(f"  {'':<9s} {'bias':>11s} "
              + " ".join(f"{s[f'e{a}'].mean():>+8.1%}" for a in ARMS))
        print(f"  {'':<9s} {'within +-7%':>11s} "
              + " ".join(f"{(s[f'e{a}'].abs()<=0.07).mean():>8.0%}" for a in ARMS))
        print()

    R.to_csv("outputs/mo91_arrival_layer_backtest.csv", index=False)
    print("wrote outputs/mo91_arrival_layer_backtest.csv")


if __name__ == "__main__":
    main()
