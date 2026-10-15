"""MO_156 - Do fuel prices and other macro signals help explain or forecast BUILT demand, now that 2026 brought an
energy shock?

WHERE THIS CAME FROM: Jason (2026-10-15): producer prices and energy costs affect supplier pricing; consumer confidence
and share-of-wallet signals should inform protein bar purchases; "gas prices had been relatively consistent until this
year". Rob (2026-10-15): "My suspicion is gas prices affect consumer spending. Diesel prices affect shelf price on a lag".
Checked: on the correct FRED series, gasoline averaged $3.0-3.6 through 2025 and $4.20 in Q2 2026 ($4.33 on 2026-10-12);
diesel ~$3.5-4.0 -> $6.18. MO_76 used mislabeled series (GASDESW = diesel as "gas"; WPU115 = computer PPI as "food").

PRIOR WORK (docs/SETTLED_FINDINGS.md / README; topic words: macro, FRED, gas, diesel, sentiment, PPI):
- MO_76 (PROVISIONAL, pre-correction bench): macro group gain sat in one window; archived; reopen-if 2+ more years of data
  "or regime-split training". This test meets the regime reopen-if (2026 energy shock) and corrects the series.
- No prior test of shelf-price pass-through from diesel.

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong: P1-P8 below, one block per part.

DATA: outputs/mo156_fred_first_release.parquet -- first-published values with their release dates (FRED output_type=4).
Each week (SPINS week ending Sunday) sees only values released on or before that Sunday: gasoline and diesel the same
week; monthly series 26-76 days after the month they describe. No revised values.

PART H1 (Rob: gas -> consumer spending). Laptop, no training. Production-candidate forecasts (direct_avg5 in
outputs/mo140_rows.parquet) made at the 2026-03/04/05 forecast dates (covering Apr-Aug 2026, after the gasoline jump) vs
those made at 2025-03/04/05 (Apr-Aug 2025, gasoline flat). Measure: actual / forecast by channel, existing series.
  P1  Total: actual/forecast in 2026 is at least 3% lower than in 2025 (spending squeeze shows up as over-forecasting).
  P2  Convenience channel's 2026-minus-2025 change is at least 5 points more negative than conventional food's (fuel-stop
      traffic). If P1/P2 fail, the gasoline jump is not visible in BUILT's forecast misses at this aggregation.

PART H2 (Rob: diesel -> shelf price on a lag). Laptop, Druid read-only. Same-item category base price index: for every
UPC selling in both week t and t-13 (all retailers except multi-outlet totals, all brands except BUILT), the base-units-
weighted median of log(base price_t / base price_t-13); BUILT separately.
  P3  The category index's 13-week change correlates positively with diesel's 13-week change at some lag between 4 and 16
      weeks, peak correlation > 0.3, and is higher than at lag 0.
  P4  The category's same-item base price rises more from March to August 2026 than over March to August 2025.
  If P3/P4 fail, diesel pass-through to protein-bar shelf prices is not visible in SPINS at this horizon.

PART M (model inputs; worker). The fixed direct model with release-aligned macro inputs added (gasoline and diesel
level, 13-week change and year-over-year change; sentiment level and year-over-year change; year-over-year change in PPI
processed foods, CPI food at home, grocery sales, payrolls; savings rate level), 5 seeds (macro_avg5) vs direct_avg5,
same harness, all 18 forecast dates; BY HISTORY BAND (<13 / 13-25 / 26-51 / 52+ wks) at all three levels.
  P5  base_s42 equals direct_fixed_s42 exactly (parity).
  P6  macro_avg5 is within +/-0.5 of direct_avg5 at recent account x month.
  P7  On the forecast dates that cover the shock (2026-03/04/05), macro_avg5 beats direct_avg5 at account x month by at
      least 0.3 (the regime effect). If P7 fails, the model cannot learn a shock it never saw in training; forward weeks
      remain the test.
  P8  macro_avg5 does not pass the switching rule (Amendment 1 + 2).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"               # same harness settings as MO_133..MO_155
import importlib                                      # noqa: E402

import MO_80_quarterly_honest_backtest as M           # noqa: E402  import asserts forecast + training parity

importlib.reload(M)
import MO_148_product_line_models as L                # noqa: E402  shared engine (same harness settings)

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

PREFIX = "mo156"
SEEDS = (42, 1, 2, 3, 4)
ARMS = ["base_s42"] + [f"macro_s{s}" for s in SEEDS]
CANDIDATES = ("macro",)
BANDS = [(0, 13, "<13 wks"), (13, 26, "13-25 wks"), (26, 52, "26-51 wks"), (52, 10_000, "52+ wks")]
FRED = Path("outputs/mo156_fred_first_release.parquet")
MACRO_WEEKLY = Path("outputs/mo156_macro_weekly.parquet")
MACRO_FEATS = ["m_gasoline", "m_gasoline_chg13", "m_gasoline_yoy", "m_diesel", "m_diesel_chg13", "m_diesel_yoy",
               "m_sentiment", "m_sentiment_yoy", "m_ppi_food_yoy", "m_cpi_food_home_yoy", "m_grocery_sales_yoy",
               "m_payrolls_yoy", "m_savings_rate"]


# ---------------------------------------------------------------- macro table (release-aligned)
def build_weekly(weeks: pd.DatetimeIndex) -> pd.DataFrame:
    """For each SPINS week (ending Sunday), the latest first-published value released on or before that Sunday."""
    f = pd.read_parquet(FRED)
    f["released"] = pd.to_datetime(f["released"]).dt.tz_localize("UTC")
    out = pd.DataFrame(index=weeks)
    for name, g in f.groupby("series"):
        g = g.sort_values("obs_date")
        g["yoy"] = g["value"] / g["value"].shift(52 if name in ("gasoline", "diesel") else 12) - 1
        g["chg13"] = g["value"] / g["value"].shift(13) - 1 if name in ("gasoline", "diesel") else np.nan
        avail = g.sort_values("released")
        vals = {c: [] for c in ("value", "yoy", "chg13")}
        for w in weeks:
            a = avail[avail["released"] <= w]
            a = a[a["obs_date"] == a["obs_date"].max()] if len(a) else a
            for c in vals:
                vals[c].append(float(a[c].iloc[-1]) if len(a) else np.nan)
        out[f"m_{name}"] = vals["value"]
        out[f"m_{name}_yoy"] = vals["yoy"]
        if name in ("gasoline", "diesel"):
            out[f"m_{name}_chg13"] = vals["chg13"]
    out.index.name = "__time"
    return out.reset_index()


def add_macro(df: pd.DataFrame) -> pd.DataFrame:
    mw = pd.read_parquet(MACRO_WEEKLY)
    mw["__time"] = pd.to_datetime(mw["__time"], utc=True)
    keep = ["__time"] + [c for c in MACRO_FEATS if c in mw.columns]
    n0 = len(df)
    df = df.merge(mw[keep], on="__time", how="left")
    assert len(df) == n0
    return df


# ---------------------------------------------------------------- H1: forecast misses vs gasoline
def h1() -> dict:
    r = pd.read_parquet("outputs/mo140_rows.parquet",
                        columns=["origin", "series", "date", "actual", "direct_avg5", "is_new", "band"])
    r = r[(~r["is_new"]) & (r["band"] != "lapsed")]
    r["channel"] = r["series"].str.split(" | ", regex=False).str[1]
    r["period"] = np.where(r["origin"].isin(["2026-03", "2026-04", "2026-05"]), "2026",
                           np.where(r["origin"].isin(["2025-03", "2025-04", "2025-05"]), "2025", None))
    r = r[r["period"].notna()]
    tot = r.groupby("period")[["actual", "direct_avg5"]].sum()
    ratio_tot = (tot["actual"] / tot["direct_avg5"]).to_dict()
    ch = r.groupby(["channel", "period"])[["actual", "direct_avg5"]].sum()
    ch["ratio"] = ch["actual"] / ch["direct_avg5"]
    piv = ch["ratio"].unstack()
    piv["change"] = piv["2026"] - piv["2025"]
    vol = r[r["period"] == "2026"].groupby("channel")["actual"].sum()
    piv["actual_2026"] = vol
    piv = piv.sort_values("actual_2026", ascending=False)
    conv = [c for c in piv.index if "CONVENIENCE" in c.upper()]
    food = [c for c in piv.index if c.upper().startswith("CONVENTIONAL|FOOD")]
    res = {"ratio_total": ratio_tot, "by_channel": piv.round(4).to_dict(orient="index"),
           "convenience_channels": conv, "food_channels": food}
    print("H1 actual/forecast, 2025 vs 2026 (Apr-Aug):", {k: round(v, 3) for k, v in ratio_tot.items()})
    print(piv.head(12).round(3).to_string())
    c_chg = float(piv.loc[conv, "change"].mean()) if conv else np.nan
    f_chg = float(piv.loc[food, "change"].mean()) if food else np.nan
    res["P1 total 2026 >=3% lower"] = {"2025": ratio_tot.get("2025"), "2026": ratio_tot.get("2026"),
                                        "holds": ratio_tot.get("2026", 1) <= ratio_tot.get("2025", 1) - 0.03}
    res["P2 convenience >=5 pts more negative than food"] = {"convenience": c_chg, "food": f_chg,
                                                            "holds": bool(c_chg <= f_chg - 0.05)}
    return res


# ---------------------------------------------------------------- H2: diesel -> shelf price
def h2() -> dict:
    sys.path.insert(0, ".")
    from mo_druid_client import query_druid
    q = ('SELECT __time, upc, source_brand, SUM(base_dollars) AS bd, SUM(base_units) AS bu '
         'FROM "built_filtered_weekly" WHERE channel_outlet <> \'CONVENTIONAL|MULTI OUTLET\' '
         'AND __time >= TIMESTAMP \'2023-01-01\' GROUP BY 1, 2, 3')
    d = query_druid(q)
    d["__time"] = pd.to_datetime(d["__time"], utc=True)
    d["bd"], d["bu"] = pd.to_numeric(d["bd"], errors="coerce"), pd.to_numeric(d["bu"], errors="coerce")
    d = d[(d["bu"] > 0) & (d["bd"] > 0)]
    d["p"] = d["bd"] / d["bu"]
    d["built"] = d["source_brand"].astype(str).str.upper().str.startswith("BUILT")
    weeks = sorted(d["__time"].unique())
    idx = {}
    for grp, sub in (("category", d[~d["built"]]), ("built", d[d["built"]])):
        piv_p = sub.pivot_table(index="__time", columns="upc", values="p", aggfunc="mean")
        piv_u = sub.pivot_table(index="__time", columns="upc", values="bu", aggfunc="sum")
        vals = {}
        for i in range(13, len(piv_p)):
            a, b = piv_p.iloc[i], piv_p.iloc[i - 13]
            ok = a.notna() & b.notna()
            if ok.sum() < 20:
                continue
            lr = np.log(a[ok] / b[ok])
            w = piv_u.iloc[i][ok].fillna(0).values
            o = np.argsort(lr.values)
            cw = np.cumsum(w[o]) / w.sum()
            vals[piv_p.index[i]] = float(lr.values[o][np.searchsorted(cw, 0.5)])
        idx[grp] = pd.Series(vals).sort_index()
    f = pd.read_parquet(FRED)
    ds = f[f["series"] == "diesel"].set_index("obs_date")["value"].sort_index()
    ds.index = pd.to_datetime(ds.index, utc=True)
    dsw = ds.resample("W-SUN").last().ffill()
    d13 = np.log(dsw / dsw.shift(13))
    res = {}
    for grp, s in idx.items():
        cors = {}
        for lag in range(0, 27):
            x = d13.shift(lag).reindex(s.index)
            ok = x.notna() & s.notna()
            cors[lag] = float(np.corrcoef(x[ok], s[ok])[0, 1]) if ok.sum() > 20 else np.nan
        res[grp] = {"corr_by_lag": cors, "n_weeks": int(s.notna().sum()),
                    "chg_mar_aug_2025": float(s[(s.index >= "2025-08-01") & (s.index < "2025-09-01")].mean()),
                    "chg_mar_aug_2026": float(s[(s.index >= "2026-08-01") & (s.index < "2026-09-01")].mean())}
        best = max(range(4, 17), key=lambda L: cors.get(L, -9) if np.isfinite(cors.get(L, np.nan)) else -9)
        res[grp]["best_lag_4_16"] = best
        print(f"H2 {grp}: weeks {res[grp]['n_weeks']} | corr lag0 {cors[0]:.2f} | best lag {best} corr {cors[best]:.2f} | "
              f"13-wk same-item price change in Aug 2025 {res[grp]['chg_mar_aug_2025']:+.3f}, Aug 2026 {res[grp]['chg_mar_aug_2026']:+.3f}")
    c = res["category"]
    res["P3 diesel leads category price (lag 4-16, r>0.3, > lag 0)"] = {
        "best_lag": c["best_lag_4_16"], "r": c["corr_by_lag"][c["best_lag_4_16"]], "r_lag0": c["corr_by_lag"][0],
        "holds": bool(c["corr_by_lag"][c["best_lag_4_16"]] > 0.3 and c["corr_by_lag"][c["best_lag_4_16"]] > c["corr_by_lag"][0])}
    res["P4 category price rose more Mar-Aug 2026 than 2025"] = {
        "2025": c["chg_mar_aug_2025"], "2026": c["chg_mar_aug_2026"], "holds": bool(c["chg_mar_aug_2026"] > c["chg_mar_aug_2025"])}
    return res


# ---------------------------------------------------------------- M: model inputs (worker compute, laptop score)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "h1", "h2", "compute", "score"])
    ap.add_argument("--origins", default="")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default=os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo156_cache"))
    ap.add_argument("--feats-dir", default="outputs")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--results", default="")
    a = ap.parse_args()
    sp = lambda s: [x for x in s.split(",") if x]
    if a.cmd == "build":
        p = pd.read_parquet("outputs/retailer_sales_weekly.parquet", columns=["__time"])
        weeks = pd.DatetimeIndex(sorted(pd.to_datetime(p["__time"].unique(), utc=True)))
        mw = build_weekly(weeks)
        mw.to_parquet(MACRO_WEEKLY)
        print("weeks", len(mw), "| non-null share:", mw.drop(columns="__time").notna().mean().round(2).to_dict())
        return
    if a.cmd in ("h1", "h2"):
        res = h1() if a.cmd == "h1" else h2()
        Path(f"../outputs/mo156_{a.cmd}.json").write_text(json.dumps(res, indent=2, default=float))
        for k, v in res.items():
            if k.startswith("P"):
                print(k, "HOLDS" if v["holds"] else "FAILS", {kk: vv for kk, vv in v.items() if kk != "holds"})
        return
    fd = Path(a.feats_dir)
    feats_r = json.loads((fd / "feats_recursive.json").read_text())
    feats_d = list(json.loads((fd / "direct_multihorizon_metrics_v11d.json").read_text())["features_used"])
    if a.cmd == "score":
        out = "../outputs/mo156_macro_inputs.json"
        res = L.score_candidates(sp(a.results), PREFIX, CANDIDATES, out, "outputs/mo156_rows.parquet", feats_r, feats_d)
        R = res["with Walmart"]["recent"]
        print("\nBY HISTORY BAND (<13 / 13-25 / 26-51 / 52+ wks), recent origins, macro_avg5 vs direct_avg5:")
        for lvl in (L.CW, L.AM, L.PM):
            for b, v in R[lvl]["by_band"].items():
                if b in [x[2] for x in BANDS]:
                    print(f"  {lvl:<18s} {b:<10s} n={v['n']:>7,}  direct_avg5={v['direct_avg5']:.2f}  macro_avg5={v['macro_avg5']:.2f}")
        po = res["per_origin"]["with Walmart: macro_avg5"]["diffs"]
        shock = [po[o] for o in ("2026-03", "2026-04", "2026-05") if o in po]
        res["predictions"] = {
            "P5 parity": {"max": max(res["parity_max_abs_diff_by_origin"].values()),
                          "holds": max(res["parity_max_abs_diff_by_origin"].values()) < 1e-6},
            "P6 recent am within 0.5": {"macro": R[L.AM]["macro_avg5"], "direct": R[L.AM]["direct_avg5"],
                                        "holds": abs(R[L.AM]["macro_avg5"] - R[L.AM]["direct_avg5"]) <= 0.5},
            "P7 shock dates better by >=0.3 am": {"mean_diff": float(np.mean(shock)), "holds": float(np.mean(shock)) <= -0.3},
            "P8 does not pass": {"passes": res["rule"]["macro_avg5"].get("passes backtest part"),
                                 "holds": not res["rule"]["macro_avg5"].get("passes backtest part")},
        }
        Path(out).write_text(json.dumps(res, indent=2, default=float))
        for k, v in res["predictions"].items():
            print(k, "HOLDS" if v["holds"] else "FAILS", {kk: vv for kk, vv in v.items() if kk != "holds"})
        return
    origins = sp(a.origins) or [o[0] for o in M.ORIGINS_MONTHLY]
    t0 = time.time()
    summary = L.compute(origins, a.arms.split(","), a.out, feats_r, feats_d, a.threads, a.parallel,
                        prefix=PREFIX, variants={"base": L.v_base, "macro": L.v_base}, prep=add_macro,
                        extra_feats=tuple(MACRO_FEATS))
    Path(a.out, f"{PREFIX}_compute_{'_'.join(origins)}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done {len(origins)} origin(s) in {time.time() - t0:,.0f}s", flush=True)


if __name__ == "__main__":
    main()
