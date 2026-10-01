"""MO_59b — Rebuild the portfolio seasonal index from ALL qualifying series.

WHY
---
MO_59 builds `outputs/mo59_seasonal_index.csv` as the median STL seasonal component across
`qualifying[:20]` — the top 20 series by volume with >=104 weeks. (NOT `TOP_N = 3`; that
constant only picks the 3 series for the decomposition chart. An earlier version of this
docstring claimed 3 and was wrong.) 281 series qualify on the 2026-10-01 panel.

That index drives the ENTIRE seasonal signal for the ~55% of series with no year-ago anchor
— MO_27's `elif seasonal_lookup` branch, ~line 569 — including 51% of Target's volume.

Two problems, both measured:

1. THE LIVE CSV IS STALE AND UNREPRODUCIBLE. It is dated 2026-09-24, is untracked, and
   peaks at week 40 (October) with a week-36 trough. Re-running the same n=20 logic today
   gives a week-6 peak and week-36 trough on BOTH the Sep-30 and Oct-1 panels. So the
   production curve cannot be reproduced from any panel we still have.

2. SAMPLE SIZE CHANGES THE CURVE, mostly at the trough:
       n= 20   median peak wk  6   volwtd peak wk 11   trough wk 36 (September)
       n=265   median peak wk  9   volwtd peak wk 10   trough wk 52 (December)
   Documented BUILT seasonality is a March peak (~+30%) and a December trough (~-28%).
   n=265 agrees on BOTH ends; n=20 agrees on the peak but puts the trough in September.

3. THE CURVE IS BIMODAL and the median's argmax is unstable because of it. There is a real
   March mode and a real October secondary bump, nearly tied. Across the two panels at
   n=80 the median's peak moved 30 weeks (wk 40 -> wk 10) while correlation stayed at
   0.9851 — so correlation is the WRONG stability metric here. Volume-weighting breaks the
   tie consistently toward March (peak shift 0 weeks, r=0.9948).

Separately: single-series STL is numerically fragile at this history length. With period=52
and only ~2.9 annual cycles, one extra week of data flipped a 3-series index's peak from
week 40 to week 10. Averaging over hundreds of series is what makes the estimate usable.

CONCLUSION: use ALL qualifying series, VOLUME-WEIGHTED. Stable across panels and matching
documented seasonality at both peak and trough.

This script does NOT overwrite mo59_seasonal_index.csv; it writes alongside for comparison.

Run:  python MO_59b_seasonal_index_rebuild.py [--min-weeks 104] [--limit 0]
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

warnings.filterwarnings("ignore")

PARQUET     = Path("outputs/retailer_sales_weekly.parquet")
CURRENT_CSV = Path("outputs/mo59_seasonal_index.csv")
OUT_CSV     = Path("outputs/mo59b_seasonal_index_allseries.csv")
OUT_JSON    = Path("outputs/mo59b_seasonal_comparison.json")

STL_PERIOD  = 52
EXCLUDE_GEO = {"CRMA"}          # same as MO_59: MULO aggregates double-count retailers
GRAIN       = ["retail_account", "upc"]   # same grain as MO_59, for a like-for-like compare


def load() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df["base_units"] = pd.to_numeric(df["base_units"], errors="coerce")
    if "geography_level" in df.columns:
        df = df[~df["geography_level"].isin(EXCLUDE_GEO)].copy()
    return df


def extract(df: pd.DataFrame, acct: str, upc: str) -> pd.Series:
    s = (df[(df["retail_account"] == acct) & (df["upc"] == upc)]
         .groupby("__time")["base_units"].sum().sort_index())
    return s.asfreq("W-SUN", fill_value=np.nan).ffill().fillna(0)


def seasonal_rows(s: pd.Series) -> pd.DataFrame | None:
    """STL seasonal component of one series, normalised by its own mean level."""
    try:
        res = STL(s, period=STL_PERIOD, robust=True).fit()
    except Exception:
        return None
    base = s[s > 0].mean()
    if not base or not np.isfinite(base):
        return None
    return pd.DataFrame({
        "week_of_year": res.seasonal.index.isocalendar().week.astype(int).values,
        "seasonal_norm": res.seasonal.values / base,
        "level": base,
    })


def build_index(rows: list[pd.DataFrame], weighted: bool) -> pd.Series:
    c = pd.concat(rows, ignore_index=True)
    if weighted:
        c["w"] = c["level"]
        g = (c.groupby("week_of_year")
               .apply(lambda d: np.average(d["seasonal_norm"], weights=d["w"])))
    else:
        g = c.groupby("week_of_year")["seasonal_norm"].median()
    g = g.reindex(range(1, 53))
    g = g.interpolate().bfill().ffill()
    return g - g.mean()          # centre at zero, as MO_59 does


def monthly(idx: pd.Series) -> pd.Series:
    """Mean index by calendar month, for comparison against documented seasonality."""
    wk = pd.Series(idx.index, index=idx.index)
    month = (pd.Timestamp("2026-01-01") + pd.to_timedelta((wk - 1) * 7, unit="D")).dt.month
    return idx.groupby(month.values).mean()


def main(min_weeks: int, limit: int):
    df = load()
    lens = df.groupby(GRAIN)["base_units"].size()
    vols = df.groupby(GRAIN)["base_units"].sum()
    qual = lens[lens >= min_weeks].index
    print(f"Panel {len(df):,} rows (CRMA excluded) | series {len(lens):,} | "
          f">= {min_weeks} wks: {len(qual):,}")

    ranked = vols.loc[qual].sort_values(ascending=False)
    mo59_n = 20           # MO_59 uses qualifying[:20]; match it for a like-for-like arm
    top20 = list(ranked.index[:mo59_n])
    use = list(ranked.index[:limit]) if limit else list(ranked.index)
    print(f"MO_59 uses qualifying[:{mo59_n}]; this run uses {len(use):,}\n")

    rows, kept, skipped = [], [], 0
    for i, (acct, upc) in enumerate(use, 1):
        r = seasonal_rows(extract(df, acct, upc))
        if r is None:
            skipped += 1
            continue
        rows.append(r); kept.append((acct, upc))
        if i % 50 == 0:
            print(f"  {i}/{len(use)} fitted …")
    print(f"\nFitted {len(rows):,} series ({skipped} skipped)")

    rows20 = [r for r in (seasonal_rows(extract(df, a, u)) for a, u in top20) if r is not None]

    idx_all_med = build_index(rows,  weighted=False)
    idx_all_wt  = build_index(rows,  weighted=True)
    idx_mo59    = build_index(rows20, weighted=False)   # reproduces MO_59's method today

    cur = None
    if CURRENT_CSV.exists():
        c = pd.read_csv(CURRENT_CSV)
        cur = pd.Series(c["seasonal_index"].values,
                        index=c["week_of_year"].astype(int).values).reindex(range(1, 53))

    print(f"\n{'='*74}")
    print("MEAN SEASONAL INDEX BY MONTH  (multiplier = 1 + index)")
    print(f"  {'mon':>4s} {'live CSV':>11s} {'rebuilt n=20':>13s} "
          f"{'ALL median':>11s} {'ALL vol-wtd':>12s}")
    mm = {"cur": monthly(cur) if cur is not None else None,
          "n20": monthly(idx_mo59), "med": monthly(idx_all_med), "wt": monthly(idx_all_wt)}
    names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    for m in range(1, 13):
        c_ = f"{mm['cur'].get(m, float('nan')):+.3f}" if mm["cur"] is not None else "   n/a"
        print(f"  {names[m-1]:>4s} {c_:>11s} {mm['n20'].get(m, float('nan')):>+13.3f} "
              f"{mm['med'].get(m, float('nan')):>+11.3f} {mm['wt'].get(m, float('nan')):>+12.3f}")

    def peak_trough(s, label):
        print(f"  {label:<14s} peak wk {int(s.idxmax()):>2d} ({s.max():+.3f})   "
              f"trough wk {int(s.idxmin()):>2d} ({s.min():+.3f})   "
              f"amplitude {s.max()-s.min():.3f}")
    print()
    if cur is not None: peak_trough(cur, "live CSV")
    peak_trough(idx_mo59, f"rebuilt n={mo59_n}")
    peak_trough(idx_all_med, "ALL median")
    peak_trough(idx_all_wt, "ALL vol-wtd")

    if cur is not None:
        print(f"\n  correlation live CSV vs ALL median : "
              f"{cur.corr(idx_all_med):.3f}")
        print(f"  correlation live CSV vs ALL vol-wtd: {cur.corr(idx_all_wt):.3f}")
    print(f"  correlation ALL median vs ALL vol-wtd: {idx_all_med.corr(idx_all_wt):.3f}")

    pd.DataFrame({"week_of_year": idx_all_med.index,
                  "seasonal_index": idx_all_med.values,
                  "seasonal_index_volwtd": idx_all_wt.values}).to_csv(OUT_CSV, index=False)
    OUT_JSON.write_text(json.dumps({
        "min_weeks": min_weeks, "series_qualifying": int(len(qual)),
        "series_fitted": len(rows), "mo59_uses": mo59_n,
        "grain": GRAIN, "excluded_geography_level": sorted(EXCLUDE_GEO),
        "monthly": {k: ({str(i): float(v) for i, v in s.items()} if s is not None else None)
                    for k, s in mm.items()},
        "peak_trough": {
            k: {"peak_week": int(s.idxmax()), "peak": float(s.max()),
                "trough_week": int(s.idxmin()), "trough": float(s.min()),
                "amplitude": float(s.max() - s.min())}
            for k, s in (("live_csv", cur), ("rebuilt_n20", idx_mo59),
                         ("all_median", idx_all_med), ("all_volwtd", idx_all_wt))
            if s is not None},
        "note": ("MO_59's TOP_N=3 constant is labelled 'series to show in decomposition "
                 "grid' and is reused as the seasonal-index sample. This index drives the "
                 "entire seasonal signal for the ~55% of series with no year-ago anchor "
                 "(MO_27 'elif seasonal_lookup' branch). Does NOT overwrite "
                 "mo59_seasonal_index.csv."),
    }, indent=2))
    print(f"\n  → {OUT_CSV}\n  → {OUT_JSON}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-weeks", type=int, default=104)
    ap.add_argument("--limit", type=int, default=0, help="0 = all qualifying series")
    a = ap.parse_args()
    main(a.min_weeks, a.limit)
