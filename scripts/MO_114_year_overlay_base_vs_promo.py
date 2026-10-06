#!/usr/bin/env python
"""MO_114 - year-over-year overlays for BASE units and PROMO-LIFTED units.

MO_108 overlaid base_units only. That is what the model forecasts, but it is not what
BUILT sells, and the difference is the whole promo question. The measures reconcile
exactly across the panel:

    base_units   427,230,030     SPINS' modeled baseline  <- the forecast target
  + incr_units   158,826,288     the promo lift
  = total_units  586,056,201     actual units sold (identical to `units`)
    units_promo  206,018,137     volume sold UNDER promo conditions, a different cut:
                                 it includes base volume that would have sold anyway,
                                 which is why it exceeds incr_units

WHY THIS MATTERS RIGHT NOW
--------------------------
MO_113 just found that seasonality applied to the BASE forecast does not pay in any
form (target 48.57 / anchor 57.81 / off 45.43 — `off` wins). One explanation worth
testing before concluding "there is no seasonality" is that the seasonality is not in
the base at all: BUILT and its retailers may simply PROMOTE harder in Q1, in which
case the Jan-March ramp Jason sees in the actuals lives in incr_units while base stays
comparatively flat. Those two worlds look identical in a total-units chart and call for
opposite modeling decisions:

  seasonal BASE   -> a seasonal factor on the base forecast is the right instrument
  seasonal LIFT   -> the base should stay flat and the promo calendar carries Q1;
                     a seasonal factor on base is then double-counting, and the fact
                     that `off` wins is exactly what you would expect

So the panel that actually decides something is the LIFT RATIO (total / base) by
week-of-year, overlaid by year. If that ratio has a repeatable Q1 hump, the
seasonality is promotional.

PANELS, per entity
  base_units    what the model forecasts
  total_units   what actually sold
  incr_units    the lift on its own
  lift ratio    total / base -- the diagnostic above

COLUMNS
  raw        honest about growth; BUILT grew ~20x so early years flatten
  indexed    each year divided by its OWN mean, the only fair SHAPE comparison

Coverage caveats, both real and marked on the figure:
  panel starts 2023-10-15, so 2023 is only ~weeks 42-52
  panel ends   2026-09-06, so 2026 is only ~weeks 1-36
The dip at the right edge of 2026 is the end of the data, not a decline.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from mo_panel import (apply_rma_priority, drop_ak_hi_market_variants,
                      drop_military_accounts, drop_zero_volume_geographies,
                      fill_promo_mechanic_nulls)

PARQUET = "outputs/retailer_sales_weekly.parquet"
OUT_DIR = Path("outputs")
OUT_CSV = OUT_DIR / "mo114_year_overlay_base_vs_promo.csv"
OUT_JSON = OUT_DIR / "mo114_year_overlay_base_vs_promo.json"

MEASURES = ["base_units", "total_units", "incr_units"]
# Fixed year -> color, assigned in order and never cycled (dataviz: colour follows the
# entity, never its rank, so adding a year must not repaint the others).
YEAR_COLOR = {2023: "#94a3b8", 2024: "#38bdf8", 2025: "#f59e0b", 2026: "#ef4444"}
INK, INK2, GRID = "#0f2744", "#475569", "#cbd5e1"
MONTH_TICKS = ((10, "Mar"), (23, "Jun"), (36, "Sep"), (49, "Dec"))
PARTIAL_WEEKS = 45     # fewer observed weeks than this -> dashed and labelled partial


def load() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    for c in MEASURES:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for fn in (fill_promo_mechanic_nulls, drop_military_accounts,
               drop_ak_hi_market_variants, apply_rma_priority):
        df = fn(df, verbose=False)
    df = drop_zero_volume_geographies(df, target="base_units", verbose=False)
    # Rows missing base_units are dropped (as every other script does); rows missing
    # only incr_units are KEPT with the lift treated as zero, because dropping them
    # would silently remove non-promoted weeks and inflate every lift ratio.
    df = df.dropna(subset=["base_units"]).copy()
    df["incr_units"] = df["incr_units"].fillna(0.0)
    df["total_units"] = df["total_units"].fillna(df["base_units"] + df["incr_units"])
    return df


def weekly(df: pd.DataFrame) -> pd.DataFrame:
    iso = df["__time"].dt.isocalendar()
    d = df.assign(yr=iso.year.values, wk=iso.week.values)
    w = d.groupby(["yr", "wk"], as_index=False)[MEASURES].sum()
    # Ratio of SUMS, never a mean of per-row ratios -- the latter lets a tiny cell with a
    # freak ratio outweigh a whole retailer.
    w["lift_ratio"] = np.where(w["base_units"] > 0,
                               w["total_units"] / w["base_units"], np.nan)
    return w


def panel(ax, w, col, title, mode):
    for yr in sorted(w["yr"].unique()):
        s = w[w["yr"] == yr].sort_values("wk")
        if len(s) < 4:
            continue
        y = s[col].to_numpy(float)
        if mode == "indexed":
            mu = np.nanmean(y)
            if not np.isfinite(mu) or mu == 0:
                continue
            y = y / mu
        partial = len(s) < PARTIAL_WEEKS
        ax.plot(s["wk"], y, color=YEAR_COLOR.get(yr, "#64748b"), lw=2.0,
                ls="--" if partial else "-", solid_capstyle="round",
                label=f"{yr}{' (partial)' if partial else ''}")
    ax.set_title(title, fontsize=10.5, loc="left", color=INK)
    ax.grid(alpha=.25, lw=.6)
    ax.set_xlim(1, 53)
    ax.tick_params(labelsize=8, colors=INK2)
    for m, lbl in MONTH_TICKS:
        ax.axvline(m, color=GRID, lw=.8, ls=":", zorder=0)
        ax.text(m, ax.get_ylim()[1], lbl, fontsize=7, color="#94a3b8",
                ha="center", va="bottom")
    if mode == "indexed":
        ax.axhline(1.0, color="#64748b", lw=.9, alpha=.5)
        ax.set_ylabel("÷ that year's own mean", fontsize=8.5, color=INK2)
    elif mode == "ratio":
        ax.axhline(1.0, color="#64748b", lw=.9, alpha=.5)
        ax.set_ylabel("total ÷ base", fontsize=8.5, color=INK2)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:.2f}×"))
    else:
        ax.set_ylabel("weekly units", fontsize=8.5, color=INK2)
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, p: f"{v/1000:,.0f}K"))


def figure(name, w, path):
    rows = [("base_units", "BASE units — what the model forecasts"),
            ("total_units", "TOTAL units — what actually sold (base + promo lift)"),
            ("incr_units", "INCREMENTAL units — the promo lift on its own")]
    fig, axes = plt.subplots(4, 2, figsize=(15, 15.5))
    fig.suptitle(f"{name} — each year overlaid on a common week-of-year axis",
                 fontsize=14, color=INK, x=0.012, ha="left", y=0.988)
    for r, (col, lbl) in enumerate(rows):
        panel(axes[r][0], w, col, f"{lbl} — raw", "raw")
        panel(axes[r][1], w, col, f"{lbl} — indexed", "indexed")
    # Row 4: the diagnostic. Indexing a ratio would hide its LEVEL, which is the
    # interesting part, so the right column holds the base-vs-total shape comparison.
    panel(axes[3][0], w, "lift_ratio",
          "LIFT RATIO total ÷ base — a repeatable Q1 hump here means the\n"
          "seasonality is PROMOTIONAL, not in the base", "ratio")
    ax = axes[3][1]
    for col, ls, lbl in (("base_units", "-", "base"), ("total_units", "--", "total")):
        prof = (w.groupby("wk")[col].sum()
                / w.groupby("wk")[col].sum().mean())
        ax.plot(prof.index, prof.values, lw=2.0, ls=ls,
                color="#0ea5e9" if col == "base_units" else "#f43f5e", label=lbl)
    ax.axhline(1.0, color="#64748b", lw=.9, alpha=.5)
    ax.set_title("All years pooled: base vs total shape by week-of-year\n"
                 "(each ÷ its own mean — if these diverge in Q1, the lift is seasonal)",
                 fontsize=10.5, loc="left", color=INK)
    ax.set_ylabel("÷ own mean", fontsize=8.5, color=INK2)
    ax.grid(alpha=.25, lw=.6); ax.set_xlim(1, 53); ax.tick_params(labelsize=8, colors=INK2)
    for m, lbl in MONTH_TICKS:
        ax.axvline(m, color=GRID, lw=.8, ls=":", zorder=0)
    ax.legend(fontsize=8.5, frameon=False, loc="upper right")

    for r in range(4):
        axes[r][0].set_xlabel("week of year", fontsize=8.5, color=INK2)
        axes[r][1].set_xlabel("week of year", fontsize=8.5, color=INK2)
    axes[0][0].legend(fontsize=8.5, frameon=False, loc="upper left")
    fig.text(0.012, 0.009,
             "Panel covers 2023-10-15 to 2026-09-06. Dashed lines are partial years "
             "(2023 ≈ weeks 42–52, 2026 ≈ weeks 1–36) — the drop at the right edge of "
             "2026 is the end of the data, not a decline.\n"
             "Indexed columns are the only fair SHAPE comparison: the portfolio grew "
             "roughly 20× across the window, so on a raw axis the early years flatten "
             "to nothing. Lift ratios are ratios of SUMS, not means of ratios.",
             fontsize=8.5, color=INK2, va="bottom")
    fig.tight_layout(rect=[0, 0.042, 1, 0.968])
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)


def quarter_profile(w: pd.DataFrame) -> dict:
    """Per-year Q1 index for each measure: is Q1 above or below that year's own mean?"""
    out = {}
    q1 = w["wk"].between(1, 13)
    for yr, s in w.groupby("yr"):
        if len(s) < 20 or not s["wk"].between(1, 13).any():
            continue
        row = {}
        for col in MEASURES:
            mu = s[col].mean()
            row[col] = float(s.loc[s["wk"].between(1, 13), col].mean() / mu) if mu else None
        sq = s[q1.loc[s.index]]
        row["lift_ratio_q1"] = (float(sq["total_units"].sum() / sq["base_units"].sum())
                                if sq["base_units"].sum() else None)
        row["lift_ratio_year"] = (float(s["total_units"].sum() / s["base_units"].sum())
                                  if s["base_units"].sum() else None)
        row["weeks"] = int(len(s))
        out[int(yr)] = row
    return out


def main() -> None:
    df = load()
    kr = df[(df["retail_account"] == "KROGER") &
            (df["channel_outlet"] == "CONVENTIONAL|FOOD")]
    sets = [("Whole portfolio", weekly(df), OUT_DIR / "mo114_overlay_portfolio.png"),
            ("KROGER · Conventional Food", weekly(kr), OUT_DIR / "mo114_overlay_kroger.png")]

    print("MO_114 - base vs promo-lifted units, year overlays\n")
    res = {}
    rows = []
    for name, w, path in sets:
        figure(name, w, path)
        prof = quarter_profile(w)
        res[name] = prof
        print(f"  {name}")
        print(f"    {'yr':<5s} {'wks':>4s} {'Q1 idx base':>12s} {'Q1 idx total':>13s} "
              f"{'Q1 idx incr':>12s} {'lift Q1':>8s} {'lift yr':>8s} {'Q1 lift gap':>12s}")
        for yr, r in prof.items():
            lq, ly = r["lift_ratio_q1"], r["lift_ratio_year"]
            gap = (lq - ly) if (lq and ly) else float("nan")
            print(f"    {yr:<5d} {r['weeks']:>4d} {r['base_units']:>12.3f} "
                  f"{r['total_units']:>13.3f} {r['incr_units']:>12.3f} "
                  f"{lq:>7.3f}× {ly:>7.3f}× {gap:>+12.3f}")
        # Verdict per entity, using full years only -- 2023 and 2026 are partial and a
        # partial year's "Q1 index" is measured against a mean that excludes half the year.
        full = {y: r for y, r in prof.items() if r["weeks"] >= PARTIAL_WEEKS}
        if full:
            b = np.mean([r["base_units"] for r in full.values()])
            t = np.mean([r["total_units"] for r in full.values()])
            g = np.mean([r["lift_ratio_q1"] - r["lift_ratio_year"] for r in full.values()
                         if r["lift_ratio_q1"] and r["lift_ratio_year"]])
            print(f"\n    full years only ({', '.join(str(y) for y in full)}):")
            print(f"      Q1 base index  {b:.3f}   Q1 total index {t:.3f}")
            print(f"      mean Q1 lift-ratio gap vs year {g:+.3f}")
            if g > 0.02 and t > b:
                print("      -> Q1 is lifted MORE than the year average AND total is more "
                      "seasonal than base.\n"
                      "         The Q1 ramp is at least partly PROMOTIONAL, which is a "
                      "reason a seasonal\n"
                      "         factor on the BASE forecast fails (MO_113) — it is the "
                      "wrong instrument.")
            elif abs(g) <= 0.02:
                print("      -> promo intensity in Q1 matches the year. The Q1 ramp is in "
                      "the BASE,\n         so MO_113's result is not explained by promo "
                      "seasonality.")
            else:
                print("      -> Q1 is promoted LESS than the year average; the ramp is "
                      "base-driven.")
        print(f"    wrote {path}\n")
        w2 = w.copy(); w2["entity"] = name
        rows.append(w2)

    pd.concat(rows).to_csv(OUT_CSV, index=False)
    OUT_JSON.write_text(json.dumps(res, indent=2, default=str))
    print(f"wrote {OUT_CSV}\nwrote {OUT_JSON}")


if __name__ == "__main__":
    main()
