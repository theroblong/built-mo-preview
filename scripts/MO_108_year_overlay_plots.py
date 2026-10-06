#!/usr/bin/env python
"""MO_108 - year-over-year overlay of actual demand, Kroger and whole portfolio.

Jason wants to eyeball the trend and seasonal patterns directly: each year drawn
on a common week-of-year axis so the shapes sit on top of one another.

Two views per entity, because one view cannot show both things:

  RAW UNITS  shows the growth trajectory honestly. But BUILT grew roughly 20x
             across this window, so 2023 and 2024 flatten to near-zero lines and
             their shape becomes unreadable.
  INDEXED    each year divided by its OWN mean, so every year is centred on 1.0.
             This is the only way to compare the SHAPE of 2024 against 2026 when
             one is twenty times the size of the other.

A log-scale panel is included as well: on a log axis a constant growth RATE is a
constant vertical offset, so parallel lines mean the years are growing at the
same proportional rate and converging/diverging lines mean they are not.

Coverage caveats, both real:
  - the panel starts 2023-10-15, so 2023 is only ~weeks 42-52
  - it ends 2026-09-06, so 2026 is only ~weeks 1-36
Partial years are drawn but clearly marked, because reading a "decline" into the
end of 2026 would be reading the edge of the data.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from mo_panel import (apply_rma_priority, drop_ak_hi_market_variants,
                      drop_military_accounts, drop_zero_volume_geographies,
                      fill_promo_mechanic_nulls)

PARQUET = "outputs/retailer_sales_weekly.parquet"
OUT_PNG = Path("outputs/mo108_year_overlay.png")
OUT_CSV = Path("outputs/mo108_year_overlay.csv")

# fixed year -> colour, assigned in order and never cycled
YEAR_COLOR = {2023: "#94a3b8", 2024: "#38bdf8", 2025: "#f59e0b", 2026: "#ef4444"}


def load():
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df["base_units"] = pd.to_numeric(df["base_units"], errors="coerce")
    for fn in (fill_promo_mechanic_nulls, drop_military_accounts,
               drop_ak_hi_market_variants, apply_rma_priority):
        df = fn(df, verbose=False)
    df = drop_zero_volume_geographies(df, target="base_units", verbose=False)
    return df.dropna(subset=["base_units"])


def weekly(df):
    iso = df["__time"].dt.isocalendar()
    d = df.assign(yr=iso.year.values, wk=iso.week.values)
    return d.groupby(["yr", "wk"], as_index=False)["base_units"].sum()


def panel(ax, w, title, mode):
    for yr in sorted(w["yr"].unique()):
        s = w[w["yr"] == yr].sort_values("wk")
        if len(s) < 4:
            continue
        y = s["base_units"].values.astype(float)
        if mode == "indexed":
            y = y / y.mean()
        partial = len(s) < 45
        ax.plot(s["wk"], y, color=YEAR_COLOR.get(yr, "#64748b"), lw=2.0,
                ls="--" if partial else "-",
                label=f"{yr}{' (partial)' if partial else ''}")
    ax.set_title(title, fontsize=11, loc="left", color="#0f2744")
    ax.set_xlabel("week of year", fontsize=9)
    ax.grid(alpha=.25, lw=.6)
    ax.set_xlim(1, 53)
    for m, lbl in ((10, "Mar"), (23, "Jun"), (36, "Sep"), (49, "Dec")):
        ax.axvline(m, color="#cbd5e1", lw=.8, ls=":", zorder=0)
        ax.text(m, ax.get_ylim()[1], lbl, fontsize=7, color="#94a3b8",
                ha="center", va="bottom")
    if mode == "indexed":
        ax.axhline(1.0, color="#64748b", lw=.9, ls="-", alpha=.5)
        ax.set_ylabel("units ÷ that year's own mean", fontsize=9)
    elif mode == "log":
        ax.set_yscale("log")
        ax.set_ylabel("weekly units (log scale)", fontsize=9)
    else:
        ax.set_ylabel("weekly units", fontsize=9)
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda v, p: f"{v/1000:,.0f}K"))


def main() -> None:
    df = load()
    kr = df[(df["retail_account"] == "KROGER") &
            (df["channel_outlet"] == "CONVENTIONAL|FOOD")]
    sets = [("Whole portfolio", weekly(df)), ("KROGER · Conventional Food", weekly(kr))]

    fig, axes = plt.subplots(2, 3, figsize=(19, 9.5))
    fig.suptitle("BUILT actual demand — each year overlaid on a common week-of-year axis",
                 fontsize=14, color="#0f2744", x=0.012, ha="left", y=0.985)
    for r, (name, w) in enumerate(sets):
        panel(axes[r][0], w, f"{name} — raw units", "raw")
        panel(axes[r][1], w, f"{name} — indexed to each year's own mean", "indexed")
        panel(axes[r][2], w, f"{name} — raw units, log scale", "log")
        axes[r][0].legend(fontsize=8, frameon=False, loc="upper left")
    fig.text(0.012, 0.012,
             "Panel covers 2023-10-15 to 2026-09-06. Dashed lines are partial years "
             "(2023 ≈ weeks 42–52, 2026 ≈ weeks 1–36) — the apparent drop at the right "
             "edge of 2026 is the end of the data, not a decline.\n"
             "Indexed panel is the only fair shape comparison: the portfolio grew roughly "
             "20× across the window, so on a raw axis the early years flatten to nothing. "
             "On the log panel, parallel lines = same growth RATE.",
             fontsize=8.5, color="#475569", va="bottom")
    fig.tight_layout(rect=[0, 0.055, 1, 0.965])
    fig.savefig(OUT_PNG, dpi=150, facecolor="white")

    rows = []
    for name, w in sets:
        w = w.copy(); w["entity"] = name
        w["indexed"] = w.groupby("yr")["base_units"].transform(lambda s: s / s.mean())
        rows.append(w)
    pd.concat(rows).to_csv(OUT_CSV, index=False)

    print("MO_108 - year overlay\n")
    for name, w in sets:
        print(f"  {name}")
        tot = w.groupby("yr")["base_units"].agg(["sum", "count", "mean"])
        for yr, r in tot.iterrows():
            peak = w[w.yr == yr].sort_values("base_units").iloc[-1]
            trough = w[w.yr == yr].sort_values("base_units").iloc[0]
            flag = "  (partial)" if r["count"] < 45 else ""
            print(f"    {yr}  {int(r['count']):>2d} wks | total {r['sum']:>12,.0f} | "
                  f"mean/wk {r['mean']:>10,.0f} | peak wk {int(peak.wk):>2d} "
                  f"| trough wk {int(trough.wk):>2d}{flag}")
        print()
    print(f"wrote {OUT_PNG}\nwrote {OUT_CSV}")


if __name__ == "__main__":
    main()
