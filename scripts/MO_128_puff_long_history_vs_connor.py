#!/usr/bin/env python
"""MO_128 - On long-history PUFF items, does our model beat Connor's methods?

WHERE THIS CAME FROM
--------------------
Jason, 2026-10-07: find the BUILT PUFF focal SKUs with the most history (2023-10-15
through 2026-09-06) and test whether our model, with the source_brand stratifier, can
beat Connor's extrapolation on them. His workbook defaults to L12W on 100% of Retail_Build
rows (README 224); L4W is only his "new item ramping up" rule, so L12W is the real
benchmark. Long-history items have the best chance of showing seasonality, trend,
velocity and distribution effects.

MO_127 removed the seasonal look-ahead from the yardstick. Honest result: conn_L4W (no
seasonal) beats the model on long-history PUFF at cell x week (23.1 vs 30.0) and account x
month (20.3 vs 27.1). At PUFF x month it is close (19.5 vs 20.4): the model wins Q2 and Q3
2026, loses Q1 2026, and is biased 0.912 (under-forecast). This experiment adds Connor's
real default and the brand stratifier, and widens the test to 52+ week PUFF across all 7
quarters.

PRIOR WORK (docs/SETTLED_FINDINGS.md, DRAFT 2026-10-07)
-------------------------------------------------------
  MO_124/MO_125  conn_L12W (Connor's default) worse than flat (17.5 vs 16.0 pm);
                 conn_L4W best. PROVISIONAL, and both scored WITH the full-panel seasonal
                 index, which MO_127 showed is look-ahead. Re-scored here without it.
  MO_121 / README 223  exclude BAR from training -1.34pp (pooled, all 7 qtrs);
                 per-brand -1.14pp; PUFF -0.99. PROVISIONAL (levels not stated). Re-scored
                 here at all 3 levels on PUFF.
  MO_126 / MO_127  route by history band; model worse than flat on 52+ wks (open blocker
                 0.3), not an index artefact.
  Method rules (SETTLED): all 3 levels, history-band breakout, parity at import.

ARMS. No arm carries a seasonal factor except the model's own production path, which
uses the honest pre-cutoff index (MO_127 build_pre_index). On 52+ wk series the YAGO blend
fires instead, so the index does not reach them (MO_127: identical across index variants).
  model         REFERENCE: shipped config (MO_27 step mode, pooled training)
  model_noBAR   same, BUILT BAR rows excluded from training (source_brand stratifier)
  conn_L12W     12-wk Base U/S/W x current doors  (Connor's default)
  conn_L4W      4-wk Base U/S/W x current doors   (Connor's new-item rule)
  flat          last actual week

LEVELS: cell x week, account x month, and portfolio x month within each view, plus bias.
Each is broken out by history band (<13 / 13-25 / 26-51 / 52+ wks) and by quarter.
VIEWS:
  all       every scored series (context and the protocol band table)
  puff52    BUILT PUFF / SOUR PUFF with 52+ wks at the cutoff, all 7 quarters
  puff104   BUILT PUFF / SOUR PUFF with 104+ wks at the cutoff (2026 quarters only)
  focal     UPCs 08-40229-30362 / 30037 (Brownie Batter, Coconut 1.41oz single) and
            30380 / 30381 (4-pk), per retailer series WITH 52+ wks at the cutoff, all 7
            quarters. (Narrowed after the smoke test, before the real run: unfiltered, the
            4 UPCs span 313 retailer series, many short-history.)

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1  puff104, cell x week: conn_L12W is worse than conn_L4W (a shorter window tracks a
      growing brand better). If it FAILS, Connor's default is the better anchor here.
  P2  puff104, cell x week: the model is worse than conn_L12W. If it FAILS, the model
      already beats Connor's real default on these items at item level.
  P3  puff52, portfolio x month, by quarter: the model beats conn_L12W in at least 4 of 7
      quarters (the model's edge, if any, is at aggregate monthly level). If it FAILS, the
      model has no aggregate edge over Connor's default either.
  P4  puff104, cell x week: model_noBAR beats model by >= 1pp (MO_121 found -0.99 on PUFF).
      If it FAILS, the stratifier does not help long-history PUFF.
  P5  focal, cell x week: the model beats conn_L4W on fewer than a third of focal series.
      If it FAILS, the model is competitive on the flagship SKUs.
  P6  puff52, bias at portfolio x month in the Q1 quarters (Q1 2025, Q1 2026): the model
      under-forecasts (bias < 0.95). If it FAILS, the growth under-forecast is not
      concentrated at the New Year turn.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# Reuse MO_127's tested pieces rather than retyping them: the pre-cutoff index builder,
# the per-cutoff fit cache, the velocity definition and the history bands.
from MO_127_seasonal_index_lookahead import BANDS, band_of, build_pre_index, patch_fit, velocity

warnings.filterwarnings("ignore")

OUT = Path("outputs/mo128_puff_vs_connor.json")
OUT_FOCAL = Path("outputs/mo128_focal_series.csv")
TREES = None                      # None = production cap (MO_80.TREES_CAP); was 800 in the original run
PUFF_BRANDS = {"BUILT PUFF", "BUILT SOUR PUFF"}
FOCAL_UPCS = {"08-40229-30362": "PUFF Brownie Batter 1.41oz", "08-40229-30037": "PUFF Coconut 1.41oz",
              "08-40229-30380": "PUFF Brownie Batter 4pk", "08-40229-30381": "PUFF Coconut 4pk"}
ARMS = ["model", "model_noBAR", "conn_L12W", "conn_L4W", "flat"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=TREES)
    ap.add_argument("--quarters", default="", help="comma list, e.g. 'Q3 2026'")
    a = ap.parse_args()

    import MO_59_stl_changepoints as S
    import MO_80_quarterly_honest_backtest as M

    os.environ["MO_SEASONAL_MODE"] = "step"            # the shipped mode
    importlib.reload(M)
    assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"
    patch_fit(M)

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v11_full.pkl", "rb")).feature_name_)   # production (MO_27 v11)
    df = M.load_panel(feats)
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    df["_brand"] = df["source_brand"].astype(str)
    nb = df[df["_brand"] != "BUILT BAR"]
    raw = S.load_data()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]
    if a.quarters:
        want = {s.strip() for s in a.quarters.split(",")}
        quarters = [q for q in quarters if q[0] in want]
    GC = M.GROUP_COLS
    ai, ui = GC.index("retail_account"), GC.index("upc")

    print("MO_128 - on long-history PUFF, does our model beat Connor's methods?")
    print("  reference = model (shipped step mode, pooled training, honest pre-cutoff index)\n")

    recs = []
    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        pre_idx, n_pre = build_pre_index(S, raw, cut)
        truth = {(k[:-1], k[-1]): float(v) for k, v in
                 act.groupby(GC + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        tr = df[df["__time"] <= cut]
        p_model = M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, pre_idx)
        p_nobar = M.run_production(nb, feats, cut, qs, qe, ek, a.trees, fw, pre_idx)
        print(f"  {ql}: cutoff {qc}, index from {n_pre} series, "
              f"model {len(p_model):,} / noBAR {len(p_nobar):,} predictions")

        for key, g in tr.groupby(GC, observed=True):
            if key not in ek:
                continue
            g = g.sort_values("__time")
            bu = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
            td = list(pd.to_numeric(g["tdp"], errors="coerce").ffill().fillna(0))
            if len(bu) < 4:
                continue
            n_hist = len(bu)
            brand = str(g["_brand"].iloc[-1])
            doors = float(td[-1])
            last = float(bu[-1])
            v12, v4 = velocity(bu, td, 12), velocity(bu, td, 4)
            c12 = v12 * doors if np.isfinite(v12) else last
            c4 = v4 * doors if np.isfinite(v4) else last
            upc = str(key[ui])
            for fd in fw[:M.HORIZON]:
                if not (qs <= fd <= qe) or (key, fd) not in truth:
                    continue
                pm_ = p_model.get((key, fd))
                if pm_ is None:
                    continue
                recs.append({
                    "quarter": ql, "date": fd, "account": key[ai], "upc": upc,
                    "series": f"{upc} @ {key[ai]}", "band": band_of(n_hist), "hist_wks": n_hist,
                    "puff52": brand in PUFF_BRANDS and n_hist >= 52,
                    "puff104": brand in PUFF_BRANDS and n_hist >= 104,
                    "focal": upc in FOCAL_UPCS and n_hist >= 52,
                    "actual": truth[(key, fd)], "model": pm_,
                    # BAR-free training cannot score BAR rows; fall back so rows align
                    "model_noBAR": p_nobar.get((key, fd), pm_),
                    "conn_L12W": max(0.0, c12), "conn_L4W": max(0.0, c4),
                    "flat": max(0.0, last)})

    r = pd.DataFrame(recs)
    if r.empty:
        print("no rows"); return
    r["month"] = pd.to_datetime(r["date"]).dt.to_period("M").astype(str)
    print(f"\n  scored {len(r):,} cell-weeks  (puff52 {r['puff52'].sum():,}; "
          f"puff104 {r['puff104'].sum():,}; focal {r['focal'].sum():,})\n")

    def wmape(g, arm):
        d = np.abs(g["actual"]).sum()
        return float(np.abs(g["actual"] - g[arm]).sum() / d * 100) if d > 0 else np.nan

    LEVELS = (("cell x week", None), ("account x month", ["account", "month"]),
              ("portfolio x month", ["month"]))

    def table(sub, title):
        out = {}
        print(f"=== {title} ===")
        for lbl, keys in LEVELS:
            g = sub if keys is None else sub.groupby(keys, as_index=False)[["actual"] + ARMS].sum()
            out[lbl] = {**{arm: wmape(g, arm) for arm in ARMS}, "n": len(g), "by_band": {}}
            for _, _, b in BANDS:                      # BY HISTORY BAND
                sb = sub[sub["band"] == b]
                if sb.empty:
                    continue
                gb = sb if keys is None else sb.groupby(keys, as_index=False)[["actual"] + ARMS].sum()
                out[lbl]["by_band"][b] = {**{arm: wmape(gb, arm) for arm in ARMS}, "n": len(gb)}
        pm = sub.groupby("month", as_index=False)[["actual"] + ARMS].sum()
        out["bias"] = {arm: float(pm[arm].sum() / pm["actual"].sum()) for arm in ARMS}
        out["by_quarter_pm"], out["bias_by_quarter"] = {}, {}
        for q, sq in sub.groupby("quarter"):
            gq = sq.groupby("month", as_index=False)[["actual"] + ARMS].sum()
            out["by_quarter_pm"][q] = {arm: wmape(gq, arm) for arm in ARMS}
            out["bias_by_quarter"][q] = {arm: float(gq[arm].sum() / gq["actual"].sum()) for arm in ARMS}

        print(f"  {'arm':<13s}{'cell x wk':>11s}{'acct x mo':>11s}{'month':>9s}{'bias':>8s}")
        for arm in ARMS:
            print(f"  {arm:<13s}{out['cell x week'][arm]:>11.2f}{out['account x month'][arm]:>11.2f}"
                  f"{out['portfolio x month'][arm]:>9.2f}{out['bias'][arm]:>8.3f}")
        print("  (n: " + ", ".join(f"{l} {out[l]['n']:,}" for l, _ in LEVELS) + ")")
        print("  BY HISTORY BAND, cell x week")
        for b, v in out["cell x week"]["by_band"].items():
            print(f"    {b:<10s} n={v['n']:>6,}  " + "  ".join(f"{arm}={v[arm]:.1f}" for arm in ARMS))
        print("  BY QUARTER, month level (error / bias)")
        for q in sorted(out["by_quarter_pm"]):
            v, bq = out["by_quarter_pm"][q], out["bias_by_quarter"][q]
            print(f"    {q:<8s} " + "  ".join(f"{arm}={v[arm]:.1f}/{bq[arm]:.2f}" for arm in ARMS))
        print()
        return out

    res = {"all": table(r, "ALL SERIES (context; protocol band table)"),
           "puff52": table(r[r["puff52"]], "PUFF / SOUR PUFF, 52+ wks at cutoff, all quarters")}
    if r["puff104"].any():
        res["puff104"] = table(r[r["puff104"]], "PUFF / SOUR PUFF, 104+ wks at cutoff (2026 quarters)")

    # ── focal SKUs, one row per retailer series ─────────────────────────────
    f = r[r["focal"]]
    rows = []
    for s, g in f.groupby("series"):
        gm = g.groupby("month", as_index=False)[["actual"] + ARMS].sum()
        row = {"series": s, "sku": FOCAL_UPCS[g["upc"].iloc[0]], "account": g["account"].iloc[0],
               "cell_weeks": len(g), "units": float(g["actual"].sum())}
        row.update({f"{arm}_cw": wmape(g, arm) for arm in ARMS})
        row.update({f"{arm}_mo": wmape(gm, arm) for arm in ARMS})
        row["model_bias"] = float(g["model"].sum() / g["actual"].sum())
        rows.append(row)
    fs = pd.DataFrame(rows).sort_values("units", ascending=False)
    fs.to_csv(OUT_FOCAL, index=False)
    if not fs.empty:
        res["focal"] = table(f, "FOCAL SKUs (Brownie Batter / Coconut, single + 4pk), all quarters")
        print("=== FOCAL SKUs by retailer: item x week error (series x month error) ===")
        print(f"  {'series':<44s}{'model':>13s}{'noBAR':>13s}{'L12W':>13s}{'L4W':>13s}{'flat':>13s}  bias")
        for _, x in fs.head(25).iterrows():          # top 25 by volume; all in the CSV
            print(f"  {x['sku'][:22] + ' @ ' + str(x['account'])[:18]:<44s}" + "".join(
                f"{x[arm + '_cw']:>6.1f} ({x[arm + '_mo']:>4.1f})" for arm in ARMS)
                + f"  {x['model_bias']:.2f}")
        wins = {c: int((fs["model_cw"] < fs[f"{c}_cw"]).sum()) for c in ("conn_L12W", "conn_L4W", "flat")}
        print(f"  model beats, of {len(fs)} focal series (item x week): " +
              ", ".join(f"{c} {n}" for c, n in wins.items()))
        res["focal_wins_cw"] = {**wins, "n_series": len(fs)}

    # ── close the loop ─────────────────────────────────────────────────────
    CW, PM = "cell x week", "portfolio x month"
    checks = []
    if "puff104" in res:
        P = res["puff104"][CW]
        checks.append(("P1", P["conn_L12W"] > P["conn_L4W"],
                       f"puff104 cw L12W {P['conn_L12W']:.2f} vs L4W {P['conn_L4W']:.2f} (pred L12W worse)"))
        checks.append(("P2", P["model"] > P["conn_L12W"],
                       f"puff104 cw model {P['model']:.2f} vs L12W {P['conn_L12W']:.2f} (pred model worse)"))
        checks.append(("P4", P["model"] - P["model_noBAR"] >= 1.0,
                       f"puff104 cw model - noBAR = {P['model'] - P['model_noBAR']:+.2f}pp (pred >= +1)"))
    else:
        for pid in ("P1", "P2", "P4"):
            checks.append((pid, None, "no puff104 rows"))
    bq = res["puff52"]["by_quarter_pm"]
    nwin = sum(v["model"] < v["conn_L12W"] for v in bq.values())
    checks.append(("P3", nwin >= 4, f"puff52 month: model beats L12W in {nwin} of {len(bq)} quarters (pred >= 4)"))
    if "focal_wins_cw" in res:
        fw_ = res["focal_wins_cw"]
        checks.append(("P5", fw_["conn_L4W"] < fw_["n_series"] / 3,
                       f"focal: model beats L4W on {fw_['conn_L4W']} of {fw_['n_series']} series (pred < 1/3)"))
    else:
        checks.append(("P5", None, "no focal rows"))
    q1 = {q: v["model"] for q, v in res["puff52"]["bias_by_quarter"].items() if q.startswith("Q1")}
    checks.append(("P6", bool(q1) and all(b < 0.95 for b in q1.values()),
                   f"puff52 model bias in Q1 quarters {q1} (pred all < 0.95)"))
    print("PREDICTIONS")
    res["predictions"] = {}
    for pid, ok, msg in sorted(checks):
        tag = "UNTESTABLE" if ok is None else ("HOLDS" if ok else "FAILS")
        res["predictions"][pid] = {"result": tag, "detail": msg}
        print(f"  {pid} {tag:<10s} {msg}")

    b52 = res["all"][CW]["by_band"].get("52+ wks")
    if b52 and b52["model"] > b52["flat"]:
        print(f"  ⚠️ BLOCKER still open: model worse than flat on 52+ wk series at cell x week "
              f"({b52['model']:.1f} vs {b52['flat']:.1f})")

    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT} and {OUT_FOCAL}")


if __name__ == "__main__":
    main()
