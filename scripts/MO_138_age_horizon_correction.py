#!/usr/bin/env python
"""MO_138 - Correct the fixed direct model's item-age bias with factors learned only from earlier forecasts.

PLAIN WORDS: the 5-seed fixed direct model forecasts items that are new at a retailer about 13-15% too low, and the
gap grows with weeks ahead; established items drift a little high (MO_137b). This test multiplies each forecast by a
correction factor for its item-age group and weeks-ahead group, where each factor is learned ONLY from earlier
forecasts whose actual sales were already known on the forecast date. No model is retrained (laptop only).
Example of how it reads to FP&A: "items under 13 weeks at a retailer, 10-13 weeks out: the model has run 20% low on
past forecasts, so this forecast is raised by that much (capped)."

WHERE THIS CAME FROM
--------------------
MO_137b (item-age bias diagnostic, 2026-10-12): direct_avg5 bias (forecast / actual) recent <13 wks 0.865, 13-25
0.975, 26-51 1.052, 52+ 1.032; 2025 0.849 / 0.969 / 1.081 / 1.022; for new items 0.945 in weeks 1-4 -> 0.784 in weeks
10-13 (recent). Last value and L4W velocity x stores over-forecast new items instead, so the under-forecast is
specific to the direct models. MO_137 skeptic: account totals hide it (29% of the age-group error cancels inside
account-month totals on recent dates). Jason approved this test 2026-10-12. (The item-attributes test moves to MO_139.)

PRIOR WORK (docs/SETTLED_FINDINGS.md incl. pending; README)
  A single q90 calibration constant exists for the recursive model's high forecast (MO_67b, x1.0059, May 2026, older
  model). No item-age or weeks-ahead correction of the central forecast has been tested. New items under 13 weeks are
  handled by last value in the recursive production path (MO_79); the direct model forecasts them itself.

DESIGN, FIXED BEFORE ANY RESULT
  Model corrected: direct_avg5 (MO_133 worker seeds 42, 1, 2, 3, 4; stored in outputs/mo137_rows.parquet).
  Cells: item-age group at the forecast date (<13, 13-25, 26-51, 52+ wks) x weeks ahead (1-4, 5-9, 10-13).
  Learning set for forecast date o: every stored forecast row from earlier forecast dates whose target week is on or
    before o's cutoff (its actual was known on the forecast date) -- no look-ahead.
  Raw factor = sum(actual) / sum(forecast) in the cell. Shrunk toward 1: f = 1 + (raw - 1) x n / (n + 2000), where n =
    learning rows in the cell; capped to [0.75, 1.35]. No learning rows -> f = 1 (forecast unchanged).
  Lapsed and new-distribution rows (forecast 0) are left unchanged.
  Arms: cal = age x weeks-ahead factors; cal_age = age-only factors (same rules, cells by age only).

LEVELS: item x week (cw), account x month (am), portfolio x month (pm; also scored within history bands); BY HISTORY
BAND (<13 / 13-25 / 26-51 / 52+ wks); recent (2025-12+) first, all 18 dates, 2025 no-harm; per-origin account x month
wins with an exact sign test (the 6 recent dates overlap, so p-values are optimistic); every comparison also without
Walmart and within history bands per date (MO_136/137 skeptic rule).

DEFINITION OF "BEATS" (recorded before the run): cal beats direct_avg5 if, on the recent dates, it is better at account
x month AND at portfolio x month scored within bands, and not worse by more than 0.3 at item x week. Production use
still needs docs/PRODUCTION_DECISION_PREREG.md Amendment 1 (cal is named there before results).

PREDICTIONS, RECORDED BEFORE ANY RESULT:
  P1  Recent bias for items under 13 weeks moves from 0.865 to within 0.95-1.05 under cal.
  P2  cal beats direct_avg5 (definition above) on the recent dates.
  P3  cal improves item x week in the <13 band on recent dates by at least 1.0 point.
  P4  2025 no harm: cal is not worse than direct_avg5 by more than 0.5 at account x month on 2025 dates.
  P5  cal (age x weeks ahead) is better than cal_age (age only) at item x week on recent dates.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"
import MO_80_quarterly_honest_backtest as M        # import asserts forecast + training parity; scoring
import MO_133_ensembles as E                         # band-separated scoring
import MO_134_recursive_fair_settings as B           # seasonal bias by year

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

ROWS = Path("outputs/mo137_rows.parquet")
OUT = Path("outputs/mo138_age_horizon_correction.json")
OUT_ROWS = Path("outputs/mo138_rows.parquet")
RECENT = "2025-12"
BANDS = ["<13 wks", "13-25 wks", "26-51 wks", "52+ wks"]
SHRINK_N, LO, HI = 2000, 0.75, 1.35


def hgroup(h: pd.Series) -> pd.Series:
    return pd.cut(h, [0, 4, 9, 13], labels=["1-4", "5-9", "10-13"]).astype(str)


def factors(r: pd.DataFrame, cells: list[str], base: str = "direct_avg5") -> pd.Series:
    """Per (origin, cell) correction factor learned from earlier origins' rows already observed at the cutoff."""
    cut = {o[0]: M._utc(o[1]) for o in M.ORIGINS_MONTHLY}
    elig = r[r["band"].isin(BANDS)]
    out = []
    for o in sorted(r["origin"].unique()):
        learn = elig[(elig["origin"] < o) & (elig["date"] <= cut[o])]
        g = learn.groupby(cells, observed=True).agg(a=("actual", "sum"), f=(base, "sum"), n=("actual", "size"))
        raw = (g["a"] / g["f"].where(g["f"] > 0)).fillna(1.0)
        f = (1 + (raw - 1) * g["n"] / (g["n"] + SHRINK_N)).clip(LO, HI)
        out.append(f.rename("factor").reset_index().assign(origin=o))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def apply(r: pd.DataFrame, fac: pd.DataFrame, cells: list[str], name: str) -> pd.DataFrame:
    m = r.merge(fac, on=["origin"] + cells, how="left")
    assert len(m) == len(r)
    ok = m["band"].isin(BANDS) & ~m["is_new"]
    r[name] = np.where(ok, m["direct_avg5"] * m["factor"].fillna(1.0), m["direct_avg5"])
    return r


def sign_test(wins: int, n: int) -> float:
    k = min(wins, n - wins)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def main() -> None:
    t0 = time.time()
    r = pd.read_parquet(ROWS)
    r["date"] = pd.to_datetime(r["date"], utc=True)
    r["direct_avg5"] = r[[f"direct_fixed_s{k}" for k in (42, 1, 2, 3, 4)]].mean(axis=1)
    cut = {o[0]: M._utc(o[1]) for o in M.ORIGINS_MONTHLY}
    r["h"] = ((r["date"] - r["origin"].map(cut)).dt.days // 7).astype(int)
    assert r["h"].between(1, 13).all()
    r["hgrp"] = hgroup(r["h"])
    fac_ah = factors(r, ["band", "hgrp"])
    fac_a = factors(r, ["band"])
    r = apply(r, fac_ah, ["band", "hgrp"], "cal")
    r = apply(r, fac_a, ["band"], "cal_age")
    r["wmt"] = r["account"].astype(str).str.upper().eq("WALMART")
    arms = ["flat", "conn_L4W", "direct_served", "direct_avg5", "cal", "cal_age"]
    r.to_parquet(OUT_ROWS)
    res = {"factors_age_x_weeks": fac_ah.round(4).to_dict(orient="records"), "arms": arms}
    print("CORRECTION FACTORS used at each forecast date (age x weeks ahead), 1.0 = unchanged:")
    print(fac_ah.pivot_table(index="origin", columns=["band", "hgrp"], values="factor").round(3).to_string())
    ex = r[~r["is_new"]]
    CW, AM, PM = "cell x week", "account x month", "portfolio x month"
    for scope, sub0 in (("with Walmart", ex), ("without Walmart", ex[~ex["wmt"]])):
        res[scope] = {}
        for name, sub in (("recent", sub0[sub0.origin >= RECENT]), ("all", sub0), ("2025", sub0[sub0.origin < RECENT])):
            Sx = M.score_levels(sub, arms)
            res[scope][name] = Sx
            print(f"\n=== {scope.upper()}, {name.upper()} origins, existing series: cw / am / pm | bias ===")
            for x in arms:
                print(f"  {x:<14s}{Sx[CW][x]:7.2f}{Sx[AM][x]:7.2f}{Sx[PM][x]:7.2f}   bias {Sx['portfolio_bias'][x]:.3f}")
            if scope == "with Walmart":
                for lvl, _ in M.LEVELS_V2:
                    print(f"  BY HISTORY BAND, {lvl} (<13 / 13-25 / 26-51 / 52+ wks)")
                    for b, v in Sx[lvl]["by_band"].items():
                        print(f"    {b:<10s} n={v['n']:>7,}  " + "  ".join(f"{x}={v[x]:.1f}" for x in arms))
    rec = ex[ex.origin >= RECENT]
    bias_age = {b: {x: float(rec.loc[rec.band == b, x].sum() / rec.loc[rec.band == b, "actual"].sum()) for x in arms}
                for b in BANDS}
    res["recent_bias_by_age"] = bias_age
    print("\nRECENT bias (forecast / actual) by item age:")
    print(pd.DataFrame(bias_age).T.round(3).to_string())
    print("\nPER-ORIGIN, recent dates (candidate - direct_avg5; negative = better); exact sign test (dates overlap)")
    res["per_origin"] = {}

    def pct(d, c):
        return 100 * np.abs(d["actual"] - d[c]).sum() / d["actual"].sum()

    for scope, sub0 in (("with Walmart", rec), ("without Walmart", rec[~rec["wmt"]])):
        pm = M._prep_scoring(sub0, arms)
        g = pm[pm["full_month"]].groupby(["origin", "account", "month"])[["actual"] + arms].sum().reset_index()
        gb = pm[pm["full_month"]].groupby(["origin", "account", "month", "band"])[["actual"] + arms].sum().reset_index()
        for x in ("cal", "cal_age"):
            am = {o: round(pct(d, x) - pct(d, "direct_avg5"), 2) for o, d in g.groupby("origin")}
            amb = {o: round(pct(d, x) - pct(d, "direct_avg5"), 2) for o, d in gb.groupby("origin")}
            pbo = {o: round(E.band_separated_diff(d, x, "direct_avg5")["diff"], 2) for o, d in sub0.groupby("origin")}
            pb = E.band_separated_diff(sub0, x, "direct_avg5")["diff"]
            w1, w2, w3 = (sum(v < 0 for v in z.values()) for z in (am, amb, pbo))
            res["per_origin"][f"{scope}: {x}"] = {"am": am, "am_within_bands": amb, "pm_by_band_per_date": pbo,
                                                  "pm_by_band": pb, "wins": [w1, w2, w3]}
            print(f"  [{scope}] {x:<8s} am wins {w1}/6 (p={sign_test(w1, 6):.2f}) {am}")
            print(f"  [{scope}] {x:<8s} am within bands wins {w2}/6 {amb}")
            print(f"  [{scope}] {x:<8s} pm within bands wins {w3}/6 (pooled {pb:+.2f}) {pbo}")
    res["season_bias"] = B.season_bias(ex, arms)
    print("\nSEASONAL BIAS PER YEAR")
    for k, v in res["season_bias"].items():
        print(f"  {k:<13s} " + "  ".join(f"{a}={v[a]:.3f}" for a in arms))
    R, A, Y = res["with Walmart"]["recent"], res["with Walmart"]["all"], res["with Walmart"]["2025"]
    pbr = res["per_origin"]["with Walmart: cal"]["pm_by_band"]
    beats = R[AM]["cal"] < R[AM]["direct_avg5"] and pbr < 0 and R[CW]["cal"] <= R[CW]["direct_avg5"] + 0.3
    y13 = R[CW]["by_band"].get("<13 wks", {})
    checks = [
        ("P1", 0.95 <= bias_age["<13 wks"]["cal"] <= 1.05, f"recent <13-wk bias cal {bias_age['<13 wks']['cal']:.3f} (direct_avg5 {bias_age['<13 wks']['direct_avg5']:.3f})"),
        ("P2", beats, f"recent am {R[AM]['cal']:.2f} vs {R[AM]['direct_avg5']:.2f}; pm-by-band {pbr:+.2f}; cw {R[CW]['cal']:.2f} vs {R[CW]['direct_avg5']:.2f}"),
        ("P3", y13.get("direct_avg5", np.nan) - y13.get("cal", np.nan) >= 1.0,
         f"recent cw <13 band cal {y13.get('cal', np.nan):.2f} vs direct_avg5 {y13.get('direct_avg5', np.nan):.2f}"),
        ("P4", Y[AM]["cal"] <= Y[AM]["direct_avg5"] + 0.5, f"2025 am cal {Y[AM]['cal']:.2f} vs {Y[AM]['direct_avg5']:.2f}"),
        ("P5", R[CW]["cal"] < R[CW]["cal_age"], f"recent cw cal {R[CW]['cal']:.2f} vs cal_age {R[CW]['cal_age']:.2f}"),
    ]
    print("\nPREDICTIONS")
    res["predictions"] = {}
    for pid, ok, msg in checks:
        res["predictions"][pid] = {"result": "HOLDS" if ok else "FAILS", "detail": msg}
        print(f"  {pid} {'HOLDS' if ok else 'FAILS':<6s} {msg}")
    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT} and {OUT_ROWS} ({time.time() - t0:,.0f}s)")


if __name__ == "__main__":
    main()
