"""MO_153 - Which forecast should Mo show for items with little history (under 26 weeks at a retailer)?

WHERE THIS CAME FROM: the Mo API shows a damped-trend ETS forecast when an item has no stored model forecast
(customer-built-mo-api app/routers/retailer.py:53-110, 1180-1192). The MO_146-era skeptic flagged that ETS has no
model explainability and an unseeded random range. Jason (2026-10-15 standup): ETS was a backup so every item has a
chart; lean toward the model for consistent explainability; compare it with last value, L4W velocity x stores, a
short trend line and a proxy-item overlay.

PRIOR WORK (docs/SETTLED_FINDINGS.md, topic words: cold start, last value, ETS, proxy, analog, under 13):
- MO_79 (PROVISIONAL, pre-correction bench): naive last value wins every band for cold start; the lifecycle ramp and
  the donor surrogate lose. Reopen-if (re-run under parity, by band) is met here: this is the corrected harness.
- MO_126: last value re-validated for <13-week items (pre-correction). README 227: L4W velocity x stores loses ~7 pts in
  the <13-week band. MO_104: SES ties flat (alpha -> 1). MO_144: launch SIZE cannot be learned from history (store-count
  swings); this test covers items that already have some weeks of history, not brand-new launches.
- MO_149 (SURVIVES WITH CAVEATS): the model with velocity inputs is better for <13-week items at all levels -> the
  model itself may already beat last value for young items on the corrected bench.

ARMS (scored on existing series in the '<13 wks' and '13-25 wks' bands; same rows for every arm):
  direct_avg5    production candidate: 5-seed fixed direct LightGBM (from outputs/mo140_rows.parquet; REFERENCE)
  direct_served  the model as served (v11d settings) on the honest harness (mo140_rows)
  flat           last observed base units held flat (harness 'flat')
  conn_L4W       L4W velocity x current stores (harness)
  ets            damped Holt ETS fitted to the series' weekly base units up to the cutoff, exactly the Mo API's settings
                 (trend='add', damped_trend=True, optimized, remove_bias=True); needs >= 4 weeks, else flat
  trend          least-squares line through the last up-to-8 weekly base units (needs >= 3, else flat), extended
                 forward, clipped to [0, 1.5 x the series' max] (SETTLED MO_97/98 1.5x cap)
  proxy          automatic proxy: another series at the SAME retailer and channel with the same pack count and at least
                 (age + 13) weeks since its own first week, all before the cutoff, chosen by the highest correlation
                 of the two TDP launch ramps over the focal series' weeks so far (the Mo API's TDP-ramp score; the
                 API's 40% price part is omitted). Forecast = proxy base units at the same weeks-since-launch x
                 (focal last-4-week mean / proxy mean over the same launch weeks) x the API's monthly seasonal ratio.
                 No eligible proxy -> flat (share reported). Base units throughout (the API overlays total units).

LEVELS: cell x week, account x month, portfolio x month (young-series subset), bias at portfolio x month; by band
(<13 wks, 13-25 wks); recent (2025-12..2026-05) vs 2025 origins; with and without Walmart.

DECISION RULE (written before running): the fallback Mo shows for little-history items is the arm with the lowest
account x month error in the <13-week band over all 18 origins; if direct_avg5 or direct_served is within 0.5 points of
that arm, use the model (explainability, Jason 2026-10-15). ETS is kept only if it is best by more than 0.5.

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1  ets is worse than flat at cell x week in the <13-week band (all origins): a damped trend on a few noisy weeks
      overshoots. If it fails, short-history trends carry real signal and ETS deserves its place.
  P2  direct_avg5 beats flat at account x month in the <13-week band (all origins), per MO_149's young-item gain.
      If it fails, last value remains the right young-item fallback on the corrected bench.
  P3  conn_L4W is worse than flat at cell x week in the <13-week band (README 227). If it fails, the band inversion
      was a pre-correction artifact.
  P4  trend is worse than flat at cell x week in the <13-week band. If it fails, a capped short line is a usable
      simple fallback.
  P5  proxy is worse than flat at account x month in the <13-week band (MO_79 donor result). If it fails, an
      automatic proxy adds information a user-picked proxy could build on.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"               # same harness settings as MO_133..MO_149
import importlib                                      # noqa: E402

import MO_80_quarterly_honest_backtest as M           # noqa: E402  import asserts forecast + training parity

importlib.reload(M)
assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

ROWS_IN = Path("outputs/mo140_rows.parquet")
OUT_JSON = Path("../outputs/mo153_young_item_fallback.json")
OUT_ROWS = Path("outputs/mo153_rows.parquet")
RECENT = "2025-12"
BANDS = [(0, 13, "<13 wks"), (13, 26, "13-25 wks"), (26, 52, "26-51 wks"), (52, 10_000, "52+ wks")]
YOUNG = ("<13 wks", "13-25 wks")
ARMS = ["direct_avg5", "direct_served", "flat", "conn_L4W", "ets", "trend", "proxy"]
CW, AM, PM = "cell x week", "account x month", "portfolio x month"
MONTHLY_INDEX = [0, 1.15, 1.20, 1.30, 1.10, 1.05, 0.98, 0.95, 0.97, 1.00, 1.02, 1.00, 0.72]   # Mo API retailer.py


def sid(df: pd.DataFrame) -> pd.Series:
    return df[M.GROUP_COLS].astype(str).agg(" | ".join, axis=1)


def ets_path(y: np.ndarray, steps: int) -> np.ndarray | None:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    if len(y) < 4:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = ExponentialSmoothing(np.maximum(y, 0.0), trend="add", damped_trend=True).fit(
                optimized=True, remove_bias=True)
            return np.maximum(fit.forecast(steps), 0.0)
    except Exception:
        return None


def trend_path(y: np.ndarray, steps: int) -> np.ndarray | None:
    z = y[-8:]
    if len(z) < 3:
        return None
    x = np.arange(len(z), dtype=float)
    b, a = np.polyfit(x, z, 1)
    fx = a + b * (len(z) - 1 + np.arange(1, steps + 1))
    return np.clip(fx, 0.0, 1.5 * float(np.max(y)))


def origin_forecasts(lbl: str, cut: pd.Timestamp, hist: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    """ETS, trend and proxy forecasts for the young series scored at this origin (rows: their target dates)."""
    tr = hist[hist["__time"] <= cut]
    tr = tr.assign(series=sid(tr))
    want = set(rows["series"])
    by = {s: g.sort_values("__time") for s, g in tr.groupby("series", sort=False)}
    meta = (tr.sort_values("__time").groupby("series")
            .agg(first=("__time", "first"), acct=("retail_account", "first"), ch=("channel_outlet", "first"),
                 upc=("upc", "first"), pack=("pack_count", "last")))
    out = []
    for s, g in rows.groupby("series", sort=False):
        if s not in by:
            continue
        h = by[s]
        y = h["base_units"].astype(float).values
        last_wk = h["__time"].iloc[-1]
        dates = pd.to_datetime(g["date"], utc=True)
        k = np.round((dates - last_wk).dt.days / 7).astype(int).values           # steps after the last observed week
        steps = int(max(k.max(), 1))
        e, t = ets_path(y, steps), trend_path(y, steps)
        res = pd.DataFrame({"origin": lbl, "series": s, "date": g["date"].values})
        res["ets"] = e[np.clip(k, 1, steps) - 1] if e is not None else np.nan
        res["trend"] = t[np.clip(k, 1, steps) - 1] if t is not None else np.nan
        # ---- proxy
        m0 = meta.loc[s]
        launch = m0["first"]
        age = int(round((cut - launch).days / 7)) + 1
        cands = meta[(meta["acct"] == m0["acct"]) & (meta["ch"] == m0["ch"]) & (meta["upc"] != m0["upc"])
                     & (meta["pack"] == m0["pack"]) & (((cut - meta["first"]).dt.days / 7) >= age + 13)]
        best, best_r = None, -2.0
        f_t = h.set_index("__time")["tdp"].astype(float)
        f_idx = np.round((f_t.index - launch).days / 7).astype(int)
        for c in cands.index:
            ph = by[c]
            p_idx = np.round((ph["__time"] - meta.at[c, "first"]).dt.days / 7).astype(int).values
            p_t = pd.Series(ph["tdp"].astype(float).values, index=p_idx)
            common = [i for i in f_idx if i in p_t.index]
            if len(common) >= 2:
                a_, b_ = f_t.values[[list(f_idx).index(i) for i in common]], p_t.loc[common].values
                r = np.corrcoef(a_, b_)[0, 1] if np.std(a_) > 0 and np.std(b_) > 0 else 0.0
            else:
                r = 0.0
            if r > best_r:
                best, best_r = c, r
        res["proxy"] = np.nan
        res["proxy_found"] = best is not None
        if best is not None:
            ph = by[best]
            p_idx = np.round((ph["__time"] - meta.at[best, "first"]).dt.days / 7).astype(int).values
            p_u = pd.Series(ph["base_units"].astype(float).values, index=p_idx)
            p_u = p_u[~p_u.index.duplicated()]
            f_last = h.tail(4)
            f_li = np.round((f_last["__time"] - launch).dt.days / 7).astype(int).values
            denom = p_u.reindex(f_li).mean()
            scale = float(f_last["base_units"].mean() / denom) if denom and denom > 0 else np.nan
            tgt_li = np.round((dates - launch).dt.days / 7).astype(int).values
            p_launch = meta.at[best, "first"]
            sadj = [MONTHLY_INDEX[d.month] / max(MONTHLY_INDEX[(p_launch + pd.Timedelta(weeks=int(i))).month], 0.01)
                    for d, i in zip(dates, tgt_li)]
            res["proxy"] = p_u.reindex(tgt_li).values * scale * np.array(sadj)
        out.append(res)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def predictions(res: dict) -> dict:
    A = res["with Walmart"]["all"]

    def band(lvl, arm, b="<13 wks"):
        return A[lvl]["by_band"][b][arm]
    return {
        "P1 ets worse than flat (<13 cw)": {"ets": band(CW, "ets"), "flat": band(CW, "flat"),
                                             "holds": band(CW, "ets") > band(CW, "flat")},
        "P2 direct_avg5 beats flat (<13 am)": {"direct_avg5": band(AM, "direct_avg5"), "flat": band(AM, "flat"),
                                               "holds": band(AM, "direct_avg5") < band(AM, "flat")},
        "P3 conn_L4W worse than flat (<13 cw)": {"conn_L4W": band(CW, "conn_L4W"), "flat": band(CW, "flat"),
                                                 "holds": band(CW, "conn_L4W") > band(CW, "flat")},
        "P4 trend worse than flat (<13 cw)": {"trend": band(CW, "trend"), "flat": band(CW, "flat"),
                                              "holds": band(CW, "trend") > band(CW, "flat")},
        "P5 proxy worse than flat (<13 am)": {"proxy": band(AM, "proxy"), "flat": band(AM, "flat"),
                                              "holds": band(AM, "proxy") > band(AM, "flat")},
    }


def decide(res: dict) -> dict:
    am = {a: res["with Walmart"]["all"][AM]["by_band"]["<13 wks"][a] for a in ARMS}
    best = min(am, key=am.get)
    model = min(("direct_avg5", "direct_served"), key=am.get)
    pick = model if am[model] - am[best] <= 0.5 else best
    return {"am_<13_all_origins": am, "best": best, "pick": pick,
            "rule": "lowest <13-week account x month over all origins; model if within 0.5"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origins", default="")
    a = ap.parse_args()
    t0 = time.time()
    r = pd.read_parquet(ROWS_IN)
    r["date"] = pd.to_datetime(r["date"], utc=True)
    r = r[(~r["is_new"]) & r["band"].isin(YOUNG)].reset_index(drop=True)
    hist = M.load_panel(["base_units", "tdp", "pack_count"])
    hist = hist[M.GROUP_COLS + ["__time", "base_units", "tdp", "pack_count"]].copy()
    hist["tdp"] = pd.to_numeric(hist["tdp"], errors="coerce").fillna(0.0)
    hist["pack_count"] = hist["pack_count"].astype(str)
    origins = [o for o in M.ORIGINS_MONTHLY if not a.origins or o[0] in a.origins.split(",")]
    parts = []
    for lbl, c, _, _ in origins:
        cut = M._utc(c)
        f = origin_forecasts(lbl, cut, hist, r[r["origin"] == lbl])
        parts.append(f)
        print(f"  {lbl}: {f['series'].nunique() if len(f) else 0} young series, proxy found "
              f"{f.groupby('series')['proxy_found'].first().mean() if len(f) else 0:.0%} | {time.time() - t0:.0f}s",
              flush=True)
    F = pd.concat(parts, ignore_index=True)
    F["date"] = pd.to_datetime(F["date"], utc=True)
    r = r[r["origin"].isin([o[0] for o in origins])].merge(F, on=["origin", "series", "date"], how="left")
    fb = {}
    for arm in ("ets", "trend", "proxy"):                       # no fit / no proxy -> last value (stated above)
        miss = r[arm].isna()
        fb[arm] = int(miss.sum())
        r.loc[miss, arm] = r.loc[miss, "flat"]
    print("rows falling back to last value:", fb, "of", len(r))
    r[["origin", "series", "date", "actual", "account", "band", "is_new", "wmt", "hist_wks"] + ARMS
      + ["proxy_found"]].to_parquet(OUT_ROWS)
    res = {"rows": int(len(r)), "fallback_to_flat": fb,
           "proxy_found_share_series": float(r.groupby(["origin", "series"])["proxy_found"].first().fillna(False).mean())}
    for scope, sub0 in (("with Walmart", r), ("without Walmart", r[~r["wmt"]])):
        res[scope] = {}
        for nm, sub in (("all", sub0), ("recent", sub0[sub0.origin >= RECENT]), ("2025", sub0[sub0.origin < RECENT])):
            Sx = M.score_levels(sub, ARMS)
            res[scope][nm] = Sx
            print(f"\n=== {scope.upper()}, {nm.upper()} origins, young existing series: cw / am / pm | bias ===")
            for x in ARMS:
                print(f"  {x:<14s}{Sx[CW][x]:7.2f}{Sx[AM][x]:7.2f}{Sx[PM][x]:7.2f}   bias {Sx['portfolio_bias'][x]:.3f}")
            print("  BY HISTORY BAND (<13 / 13-25 wks), account x month:")
            for b, v in Sx[AM]["by_band"].items():
                print(f"    {b:<10s} n={v['n']:>6,}  " + "  ".join(f"{x}={v[x]:.1f}" for x in ARMS))
            print("  BY HISTORY BAND, cell x week:")
            for b, v in Sx[CW]["by_band"].items():
                print(f"    {b:<10s} n={v['n']:>6,}  " + "  ".join(f"{x}={v[x]:.1f}" for x in ARMS))
    per = {}
    for o, g in r[r["band"] == "<13 wks"].groupby("origin"):
        s = M.score_levels(g, ARMS)[AM]
        per[o] = {x: round(s[x], 2) for x in ARMS}
    res["per_origin_am_<13"] = per
    res["predictions"] = predictions(res)
    res["decision"] = decide(res)
    OUT_JSON.write_text(json.dumps(res, indent=2, default=float))
    print()
    for k, v in res["predictions"].items():
        print(k, "HOLDS" if v["holds"] else "FAILS", {kk: round(vv, 2) for kk, vv in v.items() if kk != "holds"})
    print("DECISION:", res["decision"])
    print(f"done in {time.time() - t0:,.0f}s")


if __name__ == "__main__":
    main()
