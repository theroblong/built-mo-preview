#!/usr/bin/env python
"""MO_147 - Does blending the 5-seed direct model 50/50 with a second forecast pass the full switching rule?

PLAIN WORDS: MO_146 found that averaging the main forecast (the fixed direct model, 5 seeds) with a second forecast
cut the typical retailer-month miss by about a point, and that a simple second forecast ("recent weekly sales rate x
current stores") did as well as the neural models. This test scores the named blends under the full pre-registered
switching rule, including the new Amendment 2 criterion (no established history band may get worse at portfolio x
month), so we know whether any blend is a real production candidate or just averages away errors in one place while
adding them in another. Scoring only; no models are trained (laptop, no cost).

WHERE THIS CAME FROM: MO_146 skeptic (2026-10-14) and Jason's decisions (2026-10-14): run MO_147; add Amendment 2.

PRIOR WORK (docs/SETTLED_FINDINGS.md, README):
  - MO_146 (PROVISIONAL, README 243): neural models do not beat direct_avg5; the blend gain is generic averaging.
    Reopen-if met here: MO_147 tests the blends under Amendment 2.
  - MO_133 (b)/(c) (PROVISIONAL): blends help, but on established series they do not beat last value.
  - MO_125 (PROVISIONAL): "ship L4W alone, not blended"; MO_126: a blend only in a band. MO_146's skeptic said
    the L4W blend reopens both; this test scores it.
  - MO_80 / MO_132 harness rules; Amendment 1 + 2 in docs/PRODUCTION_DECISION_PREREG.md.
DISCLOSURE: the MO_146 skeptic already computed, descriptively, recent cell x week / account x month / portfolio x
month and band-separated portfolio figures for dir_l4w, dir_l12w and the flat 50/50 blend, and band-separated
portfolio for dir_neural_only. Predictions below are only about things not yet seen: per-band criterion 7, the
seasonal and 2025 checks, per-date consistency, the new dir_flat15 arm, and the overall verdict.

ARMS (direct_avg5 = status quo; inputs from scripts/outputs/mo140_rows.parquet and the MO_146 neural forecasts):
  direct_avg5      production reference
  dir_l4w          0.5 direct_avg5 + 0.5 L4W velocity x stores (conn_L4W)
  dir_l12w         0.5 direct_avg5 + 0.5 L12W velocity x stores (conn_L12W)
  dir_flat15       0.5 direct_avg5 + 0.5 last value, only for series with < 15 weeks of history; direct_avg5 otherwise
  dir_neural_only  0.5 direct_avg5 + 0.5 neural average where a neural forecast exists; direct_avg5 otherwise
  dir_neural       as written in MO_146 (neural average, last value where no neural forecast)
LEVELS: cell x week, account x month, portfolio x month (+ within each history band), bias; BY HISTORY BAND
(<13 / 13-25 / 26-51 / 52+ wks); with and without Walmart; recent (2025-12+), all 18, 2025.
RULE: Amendment 1 criteria 1-4 (backtest part) + Amendment 2 criterion 7 (recent portfolio x month within each of
the 13-25, 26-51 and 52+ bands not worse than direct_avg5).

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1 No candidate passes all of criteria 1-4 and 7. (fails -> a blend is a real candidate: save it forward)
  P2 dir_l4w fails criterion 7 (worse in at least one established band).
  P3 dir_flat15 changes recent account x month by less than 0.5 point vs direct_avg5 (it only touches young series).
  P4 Every blend's Oct-Dec 2025 bias is within 0.03 of direct_avg5's (blends barely move the seasonal miss).
  P5 dir_neural_only is worse than dir_l4w at recent account x month (the neural half adds nothing over L4W).
Output: outputs/mo147_blends.json, scripts/outputs/mo147_rows.parquet
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"                # same harness settings as MO_133..MO_146
import MO_80_quarterly_honest_backtest as M          # import asserts forecast + training parity
importlib.reload(M)
assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"
import MO_133_ensembles as E                          # band-separated portfolio diff
import MO_134_recursive_fair_settings as B            # seasonal bias by year
import MO_136_signals as S                            # sign test

ROWS = Path("outputs/mo140_rows.parquet")
NEURAL = Path("/Users/jasonbrazeal/Documents/dev/aevah-jobs/mo146/aevah-results")
NEURAL_JOBS = ("jason-mo146-004", "jason-mo146-005", "jason-mo146-006")
RECENT = "2025-12"
ESTABLISHED = ("13-25 wks", "26-51 wks", "52+ wks")
ARMS = ["direct_avg5", "dir_l4w", "dir_l12w", "dir_flat15", "dir_neural_only", "dir_neural"]
CW, AM, PM = "cell x week", "account x month", "portfolio x month"


def neural_avg(r: pd.DataFrame) -> pd.Series:
    """Mean over N-HiTS, TCN, TFT of each model's 5-seed mean; NaN where no neural forecast exists."""
    per = []
    for name in ("NHITS", "TCN", "TFT"):
        parts = []
        for s in range(1, 6):
            fs = [f for j in NEURAL_JOBS for f in (NEURAL / j).glob(f"mo146_{name}_s{s}_*.parquet")]
            x = pd.concat([pd.read_parquet(f).assign(origin=f.stem.rsplit("_", 1)[1]) for f in fs], ignore_index=True)
            x["date"] = pd.to_datetime(x["date"]).dt.tz_localize("UTC")
            parts.append(x.set_index(["origin", "series", "date"]).value.rename(s))
        m = pd.concat(parts, axis=1).mean(axis=1).rename(name)
        per.append(m)
    nn = pd.concat(per, axis=1).mean(axis=1).rename("neural").reset_index()
    out = r[["origin", "series", "date"]].merge(nn, on=["origin", "series", "date"], how="left")
    return out["neural"]


def main() -> None:
    r = pd.read_parquet(ROWS).reset_index(drop=True)
    r["date"] = pd.to_datetime(r["date"], utc=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    nn = neural_avg(r).values
    has_nn = ~np.isnan(nn) & ~zero
    d = r["direct_avg5"].values
    r["dir_l4w"] = 0.5 * d + 0.5 * r["conn_L4W"].values
    r["dir_l12w"] = 0.5 * d + 0.5 * r["conn_L12W"].values
    r["dir_flat15"] = np.where(r["hist_wks"].values < 15, 0.5 * d + 0.5 * r["flat"].values, d)
    r["dir_neural_only"] = np.where(has_nn, 0.5 * d + 0.5 * np.nan_to_num(nn), d)
    r["dir_neural"] = 0.5 * d + 0.5 * np.where(has_nn, np.nan_to_num(nn), r["flat"].values)
    for a in ARMS:
        r[a] = np.where(zero, 0.0, r[a])
    print(f"rows {len(r):,}; neural forecast present on {int(has_nn.sum()):,} existing rows; "
          f"<15-week rows (existing) {int(((r.hist_wks < 15) & ~r.is_new).sum()):,}")
    r[["origin", "series", "date", "actual", "account", "band", "is_new", "wmt", "hist_wks"] + ARMS].to_parquet(
        "outputs/mo147_rows.parquet")
    ex = r[~r["is_new"]]
    res = {"arms": ARMS}
    for scope, sub0 in (("with Walmart", ex), ("without Walmart", ex[~ex["wmt"]])):
        res[scope] = {}
        for nm, sub in (("recent", sub0[sub0.origin >= RECENT]), ("all", sub0), ("2025", sub0[sub0.origin < RECENT])):
            Sx = M.score_levels(sub, ARMS)
            res[scope][nm] = Sx
            print(f"\n=== {scope.upper()}, {nm.upper()} origins, existing series: cw / am / pm | bias ===")
            for x in ARMS:
                print(f"  {x:<16s}{Sx[CW][x]:7.2f}{Sx[AM][x]:7.2f}{Sx[PM][x]:7.2f}   bias {Sx['portfolio_bias'][x]:.3f}")
            if scope == "with Walmart":
                for lvl, _ in M.LEVELS_V2:
                    print(f"  BY HISTORY BAND, {lvl} (<13 / 13-25 / 26-51 / 52+ wks)")
                    for b, v in Sx[lvl]["by_band"].items():
                        print(f"    {b:<10s} n={v['n']:>7,}  " + "  ".join(f"{x}={v[x]:.1f}" for x in ARMS))
    print("\nPER-ORIGIN account x month, recent (candidate - direct_avg5; negative = better)")
    res["per_origin"] = {}
    for scope, sub0 in (("with Walmart", ex), ("without Walmart", ex[~ex["wmt"]])):
        rec = sub0[sub0.origin >= RECENT]
        per = {o: M.score_levels(g, ARMS)[AM] for o, g in rec.groupby("origin")}
        for y in ARMS[1:]:
            diffs = {o: round(v[y] - v["direct_avg5"], 2) for o, v in per.items()}
            wins = sum(dd < 0 for dd in diffs.values())
            pb = E.band_separated_diff(rec, y, "direct_avg5")["diff"]
            res["per_origin"][f"{scope}: {y}"] = {"diffs": diffs, "wins": wins, "sign_p": S.sign_test(wins, len(diffs)),
                                                  "pm_by_band": pb}
            print(f"  [{scope}] {y:<15s} wins {wins}/{len(diffs)}  pm-by-band {pb:+.2f}  "
                  + " ".join(f"{o}:{dd:+.2f}" for o, dd in diffs.items()))
    res["season_bias"] = B.season_bias(ex, ARMS)
    print("\nSEASONAL BIAS (forecast / actual):")
    for k, v in res["season_bias"].items():
        print(f"  {k}: " + "  ".join(f"{a}={v[a]:.3f}" for a in ARMS))
    R, R25 = res["with Walmart"]["recent"], res["with Walmart"]["2025"]
    rule = {}
    for y in ARMS[1:]:
        po = res["per_origin"][f"with Walmart: {y}"]
        c1 = R[AM][y] < R[AM]["direct_avg5"] and po["pm_by_band"] < 0 and R[CW][y] <= R[CW]["direct_avg5"]
        c2 = po["wins"] >= 5
        c3 = R25[AM][y] <= R25[AM]["direct_avg5"] + 2.0
        c4 = all(abs(v[y] - 1) <= 0.10 or abs(v[y] - 1) <= abs(v["direct_avg5"] - 1) for v in res["season_bias"].values())
        bands = R[PM]["by_band"]
        c7_detail = {b: round(bands[b][y] - bands[b]["direct_avg5"], 2) for b in ESTABLISHED if b in bands}
        c7 = all(v <= 0 for v in c7_detail.values())
        rule[y] = {"1 recent accuracy": bool(c1), "2 consistency >=5/6": bool(c2), "3 2025 no-harm": bool(c3),
                   "4 seasonal bias": bool(c4), "7 no established band worse": bool(c7),
                   "7 detail (pm diff by band)": c7_detail, "passes backtest part": bool(c1 and c2 and c3 and c4 and c7)}
    res["rule"] = rule
    print("\nAMENDMENT 1 + 2 (backtest part; forward confirmation still required):")
    for y, v in rule.items():
        print(f"  {y:<16s} " + "  ".join(f"{k}={'Y' if b else 'n'}" for k, b in v.items() if isinstance(b, bool))
              + f"  band diffs {v['7 detail (pm diff by band)']}")
    sb = res["season_bias"]
    od = next(k for k in sb if k.startswith("Oct-Dec 2025"))
    preds = {
        "P1": {"passing": [y for y, v in rule.items() if v["passes backtest part"]],
               "holds": not any(v["passes backtest part"] for v in rule.values())},
        "P2": {"dir_l4w_band_diffs": rule["dir_l4w"]["7 detail (pm diff by band)"],
               "holds": not rule["dir_l4w"]["7 no established band worse"]},
        "P3": {"dir_flat15": R[AM]["dir_flat15"], "direct_avg5": R[AM]["direct_avg5"],
               "holds": bool(abs(R[AM]["dir_flat15"] - R[AM]["direct_avg5"]) < 0.5)},
        "P4": {a: round(sb[od][a] - sb[od]["direct_avg5"], 3) for a in ARMS[1:]},
        "P5": {"dir_neural_only": R[AM]["dir_neural_only"], "dir_l4w": R[AM]["dir_l4w"],
               "holds": bool(R[AM]["dir_neural_only"] > R[AM]["dir_l4w"])},
    }
    preds["P4"]["holds"] = bool(all(abs(v) <= 0.03 for k, v in preds["P4"].items() if k != "holds"))
    res["predictions"] = preds
    Path("../outputs/mo147_blends.json").write_text(json.dumps(res, indent=2, default=float))
    print()
    for k, v in preds.items():
        print(k, "HOLDS" if v["holds"] else "FAILS", {kk: vv for kk, vv in v.items() if kk != "holds"})


if __name__ == "__main__":
    main()
