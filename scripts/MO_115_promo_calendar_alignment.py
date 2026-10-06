#!/usr/bin/env python
"""MO_115 - does the realized promo calendar explain the seasonal shape? And does
Brian's own metric -- base units per store per week -- behave better than base units?

WHY, AND WHOSE IDEA THIS IS
---------------------------
From wiki/18 (BUILT x Aevah cadence, Oct 3), Brian named the metric he wants:

  ⭐ "base units per store per week" -- his reasoning, verbatim in the log: units per
     store per week removes the PROMOTIONAL factor, and the per-store basis removes
     the DISTRIBUTION component. He distinguished it explicitly from promoted units.

That is the same correction MO_114 arrived at from the other direction. MO_114 found
the raw Q1 index is 0.685 (looks like a trough) while the DETRENDED index is 1.101 (a
real peak), because on a business growing ~190%/yr a year-mean index mostly measures
growth. Brian's metric removes the growth by dividing by stores rather than by a fitted
trend -- a better instrument, because distribution IS the growth
(project_growth_is_distribution: 61% of growth is new series appearing).

So this script tests his metric directly, using TDP as the store proxy.

Brian also explained the summer 2026 jump: "We also had a back to school event... we
did pretty well, I think, in Albertsons or a couple of retailers for back to school."
That is checkable -- weeks 30-36, by retailer, year over year.

THE QUESTIONS
  1. Is the Q1 peak PROMOTIONAL or BASE? MO_114 found promo lift far more seasonal
     than base (detrended Q1 1.697 vs 1.101). Split each year's volume into promo and
     non-promo weeks and see which carries the shape.
  2. Does `base_units / tdp` (Brian's metric) have a cleaner, more repeatable seasonal
     profile than `base_units`? Measured as year-over-year correlation of the
     week-of-year profile -- the thing that decides whether a seasonal factor can work.
  3. Is there a back-to-school signal in weeks 30-36, and is it concentrated in
     Albertsons as Brian remembered?
  4. Does realized promo intensity CORRELATE with the detrended seasonal residual? If
     it does, the seasonal factor and the promo signal are measuring the same thing and
     stacking them double-counts.

WHAT THIS CANNOT DO, AND WHY IT MATTERS
  SPINS promo fields are REALIZED, at grocery POS level -- they say what happened, not
  what is planned. The forward promo calendar is a separate artifact that BUILT has not
  sent yet: per wiki/18 they are building 2027 now with Q1 2027 "reasonably baked in",
  but PromoMash is being phased out and the plans are "100 spreadsheets in a pile", all
  the same format, with Rob having asked for two or three samples to parse. And per
  project_trade_vs_consumer_promo, Brian's 2026 PROMO file is TRADE COMMITMENTS, not
  confirmed TPRs, so it cannot be used as a hard forward flag even once parsed.
  Everything here is therefore a RETROSPECTIVE attribution, not a forward feature.
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

import MO_114_year_overlay_base_vs_promo as P

OUT_DIR = Path("outputs")
OUT_JSON = OUT_DIR / "mo115_promo_calendar_alignment.json"
OUT_PNG = OUT_DIR / "mo115_promo_calendar_alignment.png"
BTS_WEEKS = (30, 36)        # late July - early Sept, the back-to-school window
YEAR_COLOR = P.YEAR_COLOR
INK, INK2, GRID = P.INK, P.INK2, P.GRID
FULL_YEAR = P.PARTIAL_WEEKS


def load() -> pd.DataFrame:
    df = P.load()
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    df["is_promo_week"] = pd.to_numeric(df["is_promo_week"], errors="coerce").fillna(0)
    df["promo_intensity"] = pd.to_numeric(df["promo_intensity"], errors="coerce").fillna(0)
    iso = df["__time"].dt.isocalendar()
    df["yr"], df["wk"] = iso.year.values, iso.week.values
    return df


def weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Weekly aggregate including Brian's metric and a promo/non-promo split."""
    g = df.groupby(["yr", "wk"], as_index=False).agg(
        base_units=("base_units", "sum"),
        total_units=("total_units", "sum"),
        incr_units=("incr_units", "sum"),
        tdp=("tdp", "sum"),
        promo_rows=("is_promo_week", "sum"),
        rows=("is_promo_week", "size"),
    )
    pr = df[df["is_promo_week"] > 0].groupby(["yr", "wk"])["base_units"].sum()
    np_ = df[df["is_promo_week"] == 0].groupby(["yr", "wk"])["base_units"].sum()
    g = g.merge(pr.rename("base_promo_wk"), on=["yr", "wk"], how="left")
    g = g.merge(np_.rename("base_nonpromo_wk"), on=["yr", "wk"], how="left")
    g[["base_promo_wk", "base_nonpromo_wk"]] = g[["base_promo_wk", "base_nonpromo_wk"]].fillna(0)
    # Brian's metric. TDP is Total Distribution Points, our only store proxy -- it is
    # items x stores, so base/tdp is closer to "base units per item per store per week"
    # than to his exact phrase. Stated rather than glossed over.
    g["base_per_tdp"] = np.where(g["tdp"] > 0, g["base_units"] / g["tdp"], np.nan)
    g["promo_share_rows"] = np.where(g["rows"] > 0, g["promo_rows"] / g["rows"], np.nan)
    g["lift_ratio"] = np.where(g["base_units"] > 0, g["total_units"] / g["base_units"], np.nan)
    return g.sort_values(["yr", "wk"]).reset_index(drop=True)


def loglin_profile(w: pd.DataFrame, col: str):
    """Week-of-year profile after removing a log-linear trend, renormalised to mean 1.

    Log-linear rather than a centred rolling mean because growth here is ~exponential
    (190%/yr) and, unlike a centred window, it uses every week -- so the same method
    works at a cutoff, where there is no future to centre on.
    """
    s = pd.to_numeric(w[col], errors="coerce").to_numpy(float)
    ok = np.isfinite(s) & (s > 0)
    if ok.sum() < 60:
        return None
    t = np.arange(len(s), dtype=float)
    b = np.polyfit(t[ok], np.log(s[ok]), 1)
    r = s / np.exp(np.polyval(b, t))
    d = pd.DataFrame({"wk": w["wk"], "yr": w["yr"], "r": r}).replace(
        [np.inf, -np.inf], np.nan).dropna()
    prof = d.groupby("wk")["r"].mean()
    return (prof / prof.mean()), d, float(np.expm1(b[0] * 52))


def yoy_repeatability(d: pd.DataFrame) -> float:
    """Mean pairwise correlation of the week-of-year profile ACROSS years.

    This, not amplitude, is what decides whether a seasonal factor can work: a large
    pattern that does not repeat is unusable, a small one that repeats is usable.
    Full years only -- a partial year's profile is a different set of weeks.
    """
    piv = d.pivot_table(index="wk", columns="yr", values="r", aggfunc="mean")
    piv = piv.loc[:, [c for c in piv.columns if piv[c].notna().sum() >= FULL_YEAR]]
    if piv.shape[1] < 2:
        return float("nan")
    cs = []
    cols = list(piv.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a = piv[[cols[i], cols[j]]].dropna()
            if len(a) >= 20:
                cs.append(np.corrcoef(a.iloc[:, 0], a.iloc[:, 1])[0, 1])
    return float(np.mean(cs)) if cs else float("nan")


def main() -> None:
    df = load()
    kr = df[(df["retail_account"] == "KROGER") &
            (df["channel_outlet"] == "CONVENTIONAL|FOOD")]
    sets = [("Whole portfolio", df), ("KROGER · Conventional Food", kr)]
    res = {}

    print("MO_115 - promo calendar alignment, and Brian's metric\n")
    print("Q1+Q2  Does Brian's metric (base per store-week) repeat better than base units?\n")
    print(f"  {'entity':<28s} {'measure':<18s} {'Q1 idx':>7s} {'ampl':>6s} "
          f"{'peak':>5s} {'trough':>7s} {'YoY repeat':>11s}")
    profiles = {}
    for name, sub in sets:
        w = weekly(sub)
        res[name] = {"growth_per_yr": None, "measures": {}}
        for col, lbl in (("base_units", "base_units"),
                         ("base_per_tdp", "base per store-wk"),
                         ("total_units", "total_units"),
                         ("incr_units", "incr (promo lift)"),
                         ("base_nonpromo_wk", "base, NON-promo wks"),
                         ("base_promo_wk", "base, promo wks")):
            r = loglin_profile(w, col)
            if r is None:
                print(f"  {name:<28s} {lbl:<18s} {'insufficient data':>38s}")
                continue
            prof, d, gr = r
            rep = yoy_repeatability(d)
            q1 = prof.loc[prof.index <= 13].mean()
            res[name]["growth_per_yr"] = gr if col == "base_units" else res[name]["growth_per_yr"]
            res[name]["measures"][lbl] = {
                "q1_index": float(q1), "amplitude": float(prof.max() - prof.min()),
                "peak_week": int(prof.idxmax()), "trough_week": int(prof.idxmin()),
                "yoy_repeatability": rep, "growth_per_yr": gr}
            profiles[(name, lbl)] = prof
            print(f"  {name:<28s} {lbl:<18s} {q1:>7.3f} "
                  f"{prof.max() - prof.min():>6.3f} {int(prof.idxmax()):>5d} "
                  f"{int(prof.idxmin()):>7d} {rep:>11.3f}")
        print()

    for name, _ in sets:
        m = res[name]["measures"]
        if "base_units" in m and "base per store-wk" in m:
            a, b = m["base_units"]["yoy_repeatability"], m["base per store-wk"]["yoy_repeatability"]
            better = "BETTER" if b > a else "NOT better"
            print(f"  {name}: Brian's metric repeats {better} than base units "
                  f"({b:+.3f} vs {a:+.3f}); growth removed = "
                  f"{res[name]['growth_per_yr'] * 100:.0f}%/yr")
    print()

    # ── Q3: back-to-school, weeks 30-36, by retailer ──────────────────────────
    print(f"Q3  Back-to-school window (weeks {BTS_WEEKS[0]}-{BTS_WEEKS[1]}) by retailer — "
          "Brian recalled Albertsons\n")
    lo, hi = BTS_WEEKS
    bts = {}
    top = (df.groupby("retail_account")["base_units"].sum()
             .sort_values(ascending=False).head(10).index)
    print(f"  {'retailer':<22s} " + " ".join(f"{y:>14d}" for y in (2024, 2025, 2026)))
    print(f"  {'':<22s} " + " ".join(f"{'BTS idx  share':>14s}" for _ in range(3)))
    for acct in top:
        a = df[df["retail_account"] == acct]
        cells, row = [], {}
        for yr in (2024, 2025, 2026):
            s = a[a["yr"] == yr]
            if s.empty or s["wk"].nunique() < 20:
                cells.append(f"{'--':>14s}"); continue
            win = s[s["wk"].between(lo, hi)]
            # Index against the year's own weekly mean, and the window's share of the
            # year. Both are needed: the index says "was this window strong", the share
            # says "was it big enough to matter".
            mu = s.groupby("wk")["total_units"].sum().mean()
            wmu = win.groupby("wk")["total_units"].sum().mean() if not win.empty else np.nan
            idx = wmu / mu if (mu and np.isfinite(wmu)) else np.nan
            share = win["total_units"].sum() / s["total_units"].sum() if s["total_units"].sum() else np.nan
            row[yr] = {"bts_index": float(idx) if np.isfinite(idx) else None,
                       "bts_share": float(share) if np.isfinite(share) else None}
            cells.append(f"{idx:>8.3f} {share * 100:>5.1f}%")
        bts[acct] = row
        print(f"  {acct[:21]:<22s} " + " ".join(cells))
    res["back_to_school"] = {"window_weeks": list(BTS_WEEKS), "by_retailer": bts}
    print("\n  BTS idx > 1.0 means that window ran above the retailer's own yearly weekly "
          "average.\n  2026 is partial (panel ends 2026-09-06) so its yearly mean excludes Q4 —\n"
          "  that INFLATES every 2026 index and the column is not comparable to 2024/2025.")

    # ── Q4: does promo intensity explain the detrended residual? ──────────────
    print("\nQ4  Does realized promo intensity explain the detrended seasonal residual?\n")
    corr = {}
    for name, sub in sets:
        w = weekly(sub)
        r = loglin_profile(w, "base_units")
        rt = loglin_profile(w, "total_units")
        if r is None or rt is None:
            continue
        pi = (sub.groupby(["yr", "wk"])["promo_intensity"].mean()
                 .rename("pi").reset_index())
        for lbl, rr in (("base", r), ("total", rt)):
            d = rr[1].merge(pi, on=["yr", "wk"], how="inner").dropna()
            if len(d) < 40:
                continue
            c = float(np.corrcoef(d["r"], d["pi"])[0, 1])
            corr[f"{name} · {lbl}"] = c
            print(f"  {name:<28s} detrended {lbl:<6s} vs promo intensity  r={c:+.3f}  "
                  f"(n={len(d)})")
    res["promo_intensity_corr"] = corr
    # The verdict must look at BASE only. `total` mechanically CONTAINS the promo lift,
    # so a correlation there is an identity, not evidence -- including it in the max
    # would manufacture a "material overlap" finding out of arithmetic.
    if corr:
        base_only = {k: v for k, v in corr.items() if k.endswith("base")}
        mx = max(abs(v) for v in base_only.values()) if base_only else 0.0
        if mx < 0.2:
            print(f"\n  -> weak on BASE (|r| <= {mx:.2f}). The base seasonal residual and "
                  "the promo calendar are\n     measuring DIFFERENT things, so a seasonal "
                  "factor and a promo feature are complementary\n     rather than "
                  "double-counting. (The `total` rows correlate by construction — total "
                  "CONTAINS\n     the lift — so they are not evidence either way.)")
        else:
            print(f"\n  -> material on BASE (|r| up to {mx:.2f}). The seasonal factor and "
                  "the promo signal overlap;\n     stacking both risks double-counting the "
                  "same effect.")

    # ── figure ────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    fig.suptitle("Detrended week-of-year profiles — Brian's metric vs base units, "
                 "and promo vs non-promo weeks",
                 fontsize=13.5, color=INK, x=0.012, ha="left", y=0.985)
    plots = [("Whole portfolio", ["base_units", "base per store-wk"],
              "Portfolio — does per-store-week clean up the shape?"),
             ("Whole portfolio", ["base, NON-promo wks", "base, promo wks", "incr (promo lift)"],
              "Portfolio — where does the seasonality live?"),
             ("KROGER · Conventional Food", ["base_units", "base per store-wk"],
              "Kroger — same comparison"),
             ("KROGER · Conventional Food",
              ["base, NON-promo wks", "base, promo wks", "incr (promo lift)"],
              "Kroger — where does the seasonality live?")]
    # One fixed colour per MEASURE, assigned in order and never cycled.
    mc = {"base_units": "#0ea5e9", "base per store-wk": "#8b5cf6",
          "base, NON-promo wks": "#10b981", "base, promo wks": "#f59e0b",
          "incr (promo lift)": "#f43f5e"}
    for ax, (ent, cols, title) in zip(axes.ravel(), plots):
        for c in cols:
            p = profiles.get((ent, c))
            if p is None:
                continue
            ax.plot(p.index, p.values, lw=2.0, color=mc[c], label=c, solid_capstyle="round")
        ax.axhline(1.0, color="#64748b", lw=.9, alpha=.5)
        ax.set_title(title, fontsize=10.5, loc="left", color=INK)
        ax.set_xlabel("week of year", fontsize=8.5, color=INK2)
        ax.set_ylabel("÷ own mean, trend removed", fontsize=8.5, color=INK2)
        ax.grid(alpha=.25, lw=.6); ax.set_xlim(1, 53)
        ax.tick_params(labelsize=8, colors=INK2)
        ax.axvspan(lo, hi, color="#fde68a", alpha=.30, zorder=0)
        ax.text((lo + hi) / 2, ax.get_ylim()[1], "back-to-school", fontsize=7,
                color="#92400e", ha="center", va="bottom")
        for m, lbl in P.MONTH_TICKS:
            ax.axvline(m, color=GRID, lw=.8, ls=":", zorder=0)
        ax.legend(fontsize=8, frameon=False, loc="upper right")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:.2f}"))
    fig.text(0.012, 0.010,
             "Trend removed log-linearly before profiling, because growth here is "
             "~190%/yr and a year-mean index on that mostly measures growth, not season "
             "(MO_114). Shaded band is weeks 30–36,\nthe back-to-school window Brian "
             "named. TDP is items × stores, so 'per store-week' is a proxy for his exact "
             "phrase, not a literal store count.",
             fontsize=8.5, color=INK2, va="bottom")
    fig.tight_layout(rect=[0, 0.055, 1, 0.962])
    fig.savefig(OUT_PNG, dpi=150, facecolor="white")
    plt.close(fig)

    OUT_JSON.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT_PNG}\nwrote {OUT_JSON}")


if __name__ == "__main__":
    main()
