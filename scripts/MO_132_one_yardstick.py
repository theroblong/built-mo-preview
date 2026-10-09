#!/usr/bin/env python
"""MO_132 - Everything on one yardstick, Tier 1: which forecast is best, in level AND shape?

WHERE THIS CAME FROM
--------------------
Jason, 2026-10-08: "compare everything we've tried and consider what was in play at the
time versus what we've learned since"; "use all of the data"; and, about the v5 Bracken
chart, the forecast lines "more closely match the shape and trend of the actuals". Every
result before README 230 was scored on a test bench that was not production, so the old
rankings (incl. MO_103 "direct beats recursive") are unconfirmed. This run puts every
existing approach on the fixed MO_80 bench: all 18 monthly origins (Dec 2024 - May 2026),
3 levels, history bands, and -- new -- SHAPE scores next to the level scores.

PRIOR WORK (docs/SETTLED_FINDINGS.md DRAFT; live notes 2026-10-07/08)
  MO_129  clean baseline (existing, cw/am/pm): recursive 35.45/22.95/13.77, flat
          32.59/21.12/12.84, conn_L4W 32.93/20.69/12.61, conn_L12W 35.93/23.79/16.82.
  MO_130  v8 32.41/21.45/13.69 (8th tuned config); 50/50 mo130+flat blend 30.70/19.83/10.73
          found post hoc. Jan-Mar fix overturned (bias 2025 0.729, 2026 1.072).
  MO_103  direct beat recursive at every horizon (32.83 vs 36.44) -- OLD bench, which froze
          the recursive model's per-step inputs; reopened here.
  MO_104  SES ties flat (alpha -> 1) -- old bench; re-measured here.
  Code fact 2026-10-08: the served direct model (MO_26D v11d) is trained on targets only up
          to 13 weeks before its cutoff and never refit; targets are a ROW shift, so series
          with gaps get mislabeled targets.

ARMS (lapsed and new series = 0 for every arm, production's scoring convention; the served
direct file uses an expected resume value for lapsed series, ~0.02% of volume)
  from outputs/mo130_rows_full_v8.parquet (MO_129 + MO_130 runs, same rows, same bench):
    recursive    MO_27 production path (was "model" in MO_129)
    flat, conn_L4W, conn_L12W, mo130
  computed here:
    blend         0.5 x mo130 + 0.5 x flat (MO_130 review)
    direct_served MO_26D exactly as production trains it, at each cutoff: row-shift targets,
                  holdout = last 13 target weeks, early stopping, NO refit; MO_26D's own
                  settings (lr 0.05, 3000 trees, patience 100); inputs via cutoff_frame
    direct_fixed  same settings, two defects fixed: calendar-week targets (no gap
                  mislabeling) and a refit on ALL targets at the early-stopped tree count
    ses, holt_damped, ets   statsforecast on each series' observed weekly history
                  (gaps treated as consecutive, as flat does); fallback = last value
    snaive        same week last year (fallback = last value)
    *_lvlL4W      "shape from the model, level from Connor": the parent's 13-week path
                  rescaled so its mean equals conn_L4W (recursive, direct_served, direct_fixed)
  VELOCITY (units per store per week; Jason 2026-10-08) -- forecast velocity, then x TDP at
  the cutoff (current doors), like Connor's method:
    ses_vel, holt_damped_vel, ets_vel   the statistical arms on velocity = base_units / TDP
    direct_vel    direct_fixed with velocity as the target
  (conn_L4W, conn_L12W and mo130 are already velocity x doors.)

VELOCITY VIEW: every arm re-scored as a velocity forecast. Implied velocity = forecast units /
TDP at the cutoff; graded at the ACTUAL TDP of the target week (forecast x TDP_actual /
TDP_cutoff vs actual units). Door changes cannot be forecast from SPINS, so this isolates
sales-rate skill (Brian's per-store-week view). Rows without a usable TDP stay unadjusted.

LEVELS: cell x week, account x month, portfolio x month (complete months only), bias, by
history band and origin (MO_80.score_levels). CIs: moving-block bootstrap over the 18
origins, every arm vs direct_served (what BUILT is served) and vs flat; descriptive (no
multiple-comparison correction -- no decision rule is attached to this run).
SHAPE (new): within each origin's 13-week horizon --
    direction  share of real moves (|change| >= 2%) whose direction the arm got right; a
               flat arm (change < 0.5%) counts as a miss
    change r   correlation of period-over-period % changes, forecast vs actual
    turns      share of actual peaks/troughs (3-week smoothed) the arm matches within +/-2 wks
  at portfolio x week, account x month, and Kroger x week (the v5 chart's view).
LEVEL BIAS BY DISTRIBUTION TREND: TDP last 4 wks vs weeks 9-13 before the cutoff:
growing > 1.10, shrinking < 0.90, else steady.
CHART: mockups/mo132_quarterly_lines.html -- v5-style lines (13 weeks history + 13 weeks
forecast) for the quarterly origins, all BUILT and Kroger.

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1  flat and conn_L4W stay within 1pp of each other at cell x week, and both beat
      recursive and direct_served there.
  P2  |direct_served - recursive| < 2pp at cell x week (closer than MO_103's 3.6pp).
  P3  direct_fixed beats direct_served at cell x week by >= 0.5pp.
  P4  Shape, portfolio x week: direct_served change r > recursive change r (the recursive
      path flattens by step 3).
  P5  At least one *_lvlL4W arm beats BOTH its parent and conn_L4W at account x month.
  P6  Every arm under-forecasts series with growing distribution (bias < 0.90) and
      over-forecasts series with shrinking distribution (bias > 1.10).
  P7  ses within 0.5pp of flat at cell x week; holt_damped and ets no better than flat.
  P8  (added with the velocity arms, before any velocity result) Velocity view: every arm's
      cell x week error drops vs the units view, and the LightGBM arms (recursive,
      direct_served) close at least half their gap to flat.
  P9  Velocity targets help: direct_vel beats direct_fixed, and ses_vel beats ses, at
      cell x week in the units view.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import time
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ["MO_SEASONAL_MODE"] = "step"
import MO_80_quarterly_honest_backtest as M        # import asserts forecast + training parity
import MO_26D_direct_multihorizon_train as D26      # production direct settings, in lockstep

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"
assert M.NEUTRALIZE_DONOR_FEATURES, "backtests neutralize look-ahead donor features"

ROOT = Path(__file__).resolve().parent.parent
ROWS_IN = Path("outputs/mo130_rows_full_v8.parquet")
CACHE = Path("outputs/mo132_cache")
OUT = Path("outputs/mo132_one_yardstick.json")
OUT_ROWS = Path("outputs/mo132_rows.parquet")
CHART = ROOT / "mockups" / "mo132_quarterly_lines.html"
DIRECT_META = Path("outputs/direct_multihorizon_metrics_v11d.json")
D26_VAL_WEEKS = 13                                   # v11d: val_cutoff 2026-06-07 = data end - 13 wks
H = M.HORIZON
G = M.GROUP_COLS

BASE_ARMS = ["recursive", "flat", "conn_L4W", "conn_L12W", "mo130"]
STAT_ARMS = ["ses", "holt_damped", "ets", "snaive"]
VEL_STAT_ARMS = ["ses_vel", "holt_damped_vel", "ets_vel"]
DIRECT_ARMS = ["direct_served", "direct_fixed", "direct_vel"]
LVL_PARENTS = ["recursive", "direct_served", "direct_fixed"]
ARMS = (BASE_ARMS + ["blend"] + DIRECT_ARMS + STAT_ARMS + VEL_STAT_ARMS
        + [f"{p}_lvlL4W" for p in LVL_PARENTS])
TDP_FLOOR = 0.05                                     # MO_129.connor: no usable doors below this
QUARTER_ORIGINS = ["2024-12", "2025-03", "2025-06", "2025-09", "2025-12", "2026-03", "2026-05"]


def sid_of(keys) -> list[str]:
    return [" | ".join(map(str, k)) for k in keys]


# ---------------------------------------------------------------- direct (MO_26D) arms
def last_tdp(tr: pd.DataFrame) -> pd.Series:
    """Doors at the cutoff: each series' last non-missing TDP (MO_129.connor's `doors`)."""
    t = tr[G + ["tdp"]].dropna(subset=["tdp"])
    s = t.groupby(G, observed=True)["tdp"].last()
    s.index = sid_of(s.index)
    return s


def direct_frame(tr: pd.DataFrame, h: int, calendar: bool, velocity: bool = False) -> pd.DataFrame:
    d = tr.copy()
    if calendar:                                     # target = the series' row dated t + h weeks
        nxt = tr[G + ["__time", "base_units", "tdp"]].copy()
        nxt["y"] = (nxt["base_units"] / nxt["tdp"].where(nxt["tdp"] > TDP_FLOOR)) if velocity else nxt["base_units"]
        nxt = nxt[G + ["__time", "y"]].assign(__time=nxt["__time"] - pd.Timedelta(weeks=h))
        d = d.merge(nxt, on=G + ["__time"], how="left")
    else:                                            # production MO_26D:135 -- row shift
        d["y"] = d.groupby(G, observed=True)["base_units"].shift(-h)
    d["t_target"] = d["__time"] + pd.Timedelta(weeks=h)
    tw = d["t_target"].dt.isocalendar().week.astype(float)
    d["week_sin"], d["week_cos"] = np.sin(2 * np.pi * tw / 52), np.cos(2 * np.pi * tw / 52)
    d["week_sin26"], d["week_cos26"] = np.sin(2 * np.pi * tw / 26), np.cos(2 * np.pi * tw / 26)
    return d.dropna(subset=["y"])


def fit_direct(d: pd.DataFrame, feats: list[str], cut, refit: bool):
    """MO_26D:144-158 at this cutoff; `refit` adds a final fit on all targets <= cut."""
    val_cut = cut - pd.Timedelta(weeks=D26_VAL_WEEKS)
    tr, va = d[d["t_target"] <= val_cut], d[(d["__time"] <= val_cut) & (d["t_target"] > val_cut)]
    if len(tr) < 500 or len(va) < 50:
        return None, 0

    def w(x):
        wk = ((x["__time"].max() - x["__time"]).dt.days / 7).clip(lower=0)
        return np.exp(-D26.RECENCY_LAMBDA * wk)
    m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=D26.N_ESTIMATORS, **D26.LGBM_BASE)
    m.fit(tr[feats], np.log1p(tr["y"]), sample_weight=w(tr),
          eval_set=[(va[feats], np.log1p(va["y"]))], eval_metric="quantile",
          callbacks=[lgb.early_stopping(D26.EARLY_STOP, verbose=False), lgb.log_evaluation(-1)])
    best = int(m.best_iteration_ or D26.N_ESTIMATORS)
    if refit:
        al = d[d["t_target"] <= cut]
        m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=best, **D26.LGBM_BASE)
        m.fit(al[feats], np.log1p(al["y"]), sample_weight=w(al))
    return m, best


def run_direct(tr: pd.DataFrame, feats: list[str], cut, refit: bool, calendar: bool,
               velocity: bool = False) -> pd.DataFrame:
    last = tr.groupby(G, observed=True).tail(1).reset_index(drop=True)
    doors = last_tdp(tr)
    out, iters = [], []
    for h in range(1, H + 1):
        fd = cut + pd.Timedelta(weeks=h)
        m, best = fit_direct(direct_frame(tr, h, calendar, velocity), feats, cut, refit)
        iters.append(best)
        if m is None:
            continue
        X = last.copy()
        tw = float(fd.isocalendar().week)
        X["week_sin"], X["week_cos"] = np.sin(2 * np.pi * tw / 52), np.cos(2 * np.pi * tw / 52)
        X["week_sin26"], X["week_cos26"] = np.sin(2 * np.pi * tw / 26), np.cos(2 * np.pi * tw / 26)
        p = np.clip(np.expm1(m.predict(X[feats])), 0, None)
        sids = sid_of(X[G].itertuples(index=False))
        if velocity:                                 # velocity x doors at the cutoff; NaN -> flat later
            dv = doors.reindex(sids).values
            p = np.where(dv > TDP_FLOOR, p * dv, np.nan)
        out.append(pd.DataFrame({"series": sids, "date": fd, "value": p}))
    print(f"      trees by h: {iters}")
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------- statistical arms
def run_stats(tr: pd.DataFrame, cut, velocity: bool = False) -> pd.DataFrame:
    from statsforecast import StatsForecast
    from statsforecast.models import AutoETS, Naive, SimpleExponentialSmoothingOptimized
    s = tr[G + ["__time", "base_units", "tdp"]].copy()
    s["unique_id"] = sid_of(s[G].itertuples(index=False))
    s["y"] = pd.to_numeric(s["base_units"], errors="coerce").clip(lower=0)
    if velocity:                                     # units per store per week
        s["y"] = s["y"] / s["tdp"].where(s["tdp"] > TDP_FLOOR)
    s = s.dropna(subset=["y"]).sort_values(["unique_id", "__time"])
    s["ds"] = s.groupby("unique_id").cumcount() + 1
    sf = StatsForecast(models=[SimpleExponentialSmoothingOptimized(alias="ses"),
                               AutoETS(season_length=1, model="AAN", damped=True, alias="holt_damped"),
                               AutoETS(season_length=1, model="ZZN", alias="ets")],
                       freq=1, fallback_model=Naive(), n_jobs=-1)
    fc = sf.forecast(df=s[["unique_id", "ds", "y"]], h=H)
    fc = fc.reset_index() if "unique_id" not in fc.columns else fc
    n = s.groupby("unique_id")["ds"].max()
    fc["h"] = fc["ds"] - fc["unique_id"].map(n)
    fc["date"] = [cut + pd.Timedelta(weeks=int(h)) for h in fc["h"]]
    out = fc.rename(columns={"unique_id": "series"})[["series", "date", "ses", "holt_damped", "ets"]]
    for c in ("ses", "holt_damped", "ets"):
        out[c] = out[c].clip(lower=0)
    if velocity:                                     # x doors at the cutoff; NaN -> flat later
        dv = last_tdp(tr).reindex(out["series"]).values
        for c in ("ses", "holt_damped", "ets"):
            out[c] = np.where(dv > TDP_FLOOR, out[c] * dv, np.nan)
        return out.rename(columns={c: f"{c}_vel" for c in ("ses", "holt_damped", "ets")})
    # seasonal naive: the same series, same week last year
    yr = s.set_index(["unique_id", "__time"])["y"]
    lastv = s.groupby("unique_id")["y"].last()
    out["snaive"] = [float(yr.get((sid, d - pd.Timedelta(weeks=52)), lastv.get(sid, 0.0)))
                     for sid, d in zip(out["series"], out["date"])]
    return out


# ---------------------------------------------------------------- shape + trend scoring
def _changes(r, arms, keys, period):
    """Period-over-period % change on MATCHED series: each pair of consecutive periods uses
    only series with rows in both, so items dropping in and out (rows exist only where a
    series sold) cannot fake movement -- a flat forecast then has exactly zero change."""
    cols = ["actual"] + arms
    # Per-week average over the weeks each series has rows: 5-Sunday months and weeks a
    # series did not report are not "movement". (Weekly periods: one row, so mean = sum.)
    s = r.groupby(keys + ["series", period], observed=True, as_index=False)[cols].mean()
    s["_k"] = s.groupby("origin", observed=True)[period].rank(method="dense").astype(int)
    m = s.merge(s.assign(_k=s["_k"] + 1), on=keys + ["series", "_k"], suffixes=("", "_p"))
    cur = m.groupby(keys + ["_k"], observed=True)[cols].sum()
    pre = m.groupby(keys + ["_k"], observed=True)[[c + "_p" for c in cols]].sum()
    pre.columns = cols
    return ((cur - pre) / pre.where(pre.abs() > 1e-9)).dropna(how="all")


def _shape_metrics(sub: pd.DataFrame, arm: str) -> tuple[float, float, float, float]:
    """direction % of real moves called right (a non-call counts as a miss); precision % of
    calls that were right (chance = 50); call rate %; rank correlation of changes (chance = 0)."""
    a, f = sub["actual"], sub[arm]
    ok = a.notna() & f.notna()
    real = (a.abs() >= 0.02) & ok
    called = real & (f.abs() >= 0.005)
    right = called & (np.sign(f) == np.sign(a))
    n_real, n_called = int(real.sum()), int(called.sum())
    # rank correlation: small accounts' huge % swings would swamp a Pearson r
    rr = a[ok].corr(f[ok], method="spearman") if ok.sum() > 2 and f[ok].std() > 1e-12 else 0.0
    return (right.sum() / n_real * 100 if n_real else np.nan,
            right.sum() / n_called * 100 if n_called else np.nan,
            n_called / n_real * 100 if n_real else np.nan, float(rr))


def shape_scores(r: pd.DataFrame, arms: list[str], keys: list[str], period: str,
                 n_boot: int = 400, block: int = 3) -> dict:
    """Shape skill with margins of error: moving-block bootstrap over ORIGINS (the 13-week
    horizons overlap, so periods inside an origin are not independent). Chance baselines:
    precision 50%, change correlation 0 (skeptic 2026-10-08: report precision + CIs)."""
    ch = _changes(r, arms, keys, period)
    by_o = {o: g for o, g in ch.groupby(level="origin")}
    origins = sorted(by_o)
    blocks = [origins[i:i + block] for i in range(max(1, len(origins) - block + 1))]
    k = int(np.ceil(len(origins) / block))
    rng = np.random.default_rng(0)
    picks = [[o for bi in rng.integers(0, len(blocks), k) for o in blocks[bi]] for _ in range(n_boot)]
    samples = [pd.concat([by_o[o] for o in p]) for p in picks]
    out = {}
    for arm in arms:
        d, p, c, rr = _shape_metrics(ch, arm)
        bs = np.array([_shape_metrics(s, arm) for s in samples], dtype=float)
        lo, hi = np.nanpercentile(bs, 2.5, axis=0), np.nanpercentile(bs, 97.5, axis=0)
        out[arm] = {"direction": float(d), "precision": float(p), "call_rate": float(c), "change_r": rr,
                    "precision_ci": (float(lo[1]), float(hi[1])), "change_r_ci": (float(lo[3]), float(hi[3])),
                    "beats_chance": bool(lo[1] > 50 and lo[3] > 0)}
    out["n_moves"] = int((ch["actual"].abs() >= 0.02).sum())
    out["n_origins"] = len(origins)
    return out


def _turns(x: np.ndarray, dead: float = 0.01) -> list[tuple[int, int]]:
    s = pd.Series(x).rolling(3, center=True, min_periods=2).mean().values
    d = np.diff(s) / np.where(np.abs(s[:-1]) > 1e-9, np.abs(s[:-1]), np.nan)
    sg = np.where(d > dead, 1, np.where(d < -dead, -1, 0))
    t, last = [], 0
    for i, v in enumerate(sg):
        if v != 0 and last != 0 and v != last:
            t.append((i, -v))                        # +1 = trough (down then up), -1 = peak
        if v != 0:
            last = v
    return t


def turn_scores(r: pd.DataFrame, arms: list[str]) -> dict:
    # weekly path per origin chained from matched-series changes (composition-free)
    ch = _changes(r, arms, ["origin"], "date").fillna(0.0)
    pw = (1 + ch).groupby(level="origin").cumprod()
    res = {a: [0, 0, 0] for a in arms}
    n_actual = 0
    for _, g in pw.groupby(level="origin"):
        at = _turns(g["actual"].values)
        n_actual += len(at)
        for a in arms:
            ft = _turns(g[a].values)
            res[a][0] += sum(any(ft_t == t and abs(fi - i) <= 2 for fi, ft_t in ft) for i, t in at)
            res[a][1] += len(ft)
            res[a][2] += sum(any(t == ft_t and abs(fi - i) <= 2 for i, t in at) for fi, ft_t in ft)
    # turns_hit = actual turns matched (recall); turns_precision = called turns that were real
    return {a: {"turns_hit": (v[0] / n_actual * 100) if n_actual else np.nan, "turns_called": v[1],
                "turns_precision": (v[2] / v[1] * 100) if v[1] else np.nan}
            for a, v in res.items()} | {"actual_turns": n_actual}


def tdp_trend(df: pd.DataFrame, cut) -> pd.Series:
    t = df[(df["__time"] <= cut) & (df["__time"] > cut - pd.Timedelta(weeks=13))]
    t = t.assign(_recent=t["__time"] > cut - pd.Timedelta(weeks=4),
                 _old=t["__time"] <= cut - pd.Timedelta(weeks=8))
    rec = t[t["_recent"]].groupby(G, observed=True)["tdp"].median()
    old = t[t["_old"]].groupby(G, observed=True)["tdp"].median()
    ratio = (rec / old.where(old > M.DIST_MIN_TDP)).dropna()
    cls = pd.Series(np.where(ratio > 1.10, "growing", np.where(ratio < 0.90, "shrinking", "steady")),
                    index=ratio.index)
    cls.index = sid_of(cls.index)
    return cls


# ---------------------------------------------------------------- chart
def write_chart(df: pd.DataFrame, r: pd.DataFrame, path: Path) -> None:
    show = ["recursive", "direct_served", "direct_fixed", "flat", "conn_L4W", "direct_served_lvlL4W"]
    acct = df["retail_account"].astype(str)
    kroger_accts = sorted({a for a in acct.unique() if "KROGER" in a.upper()})
    panels = []
    for o in QUARTER_ORIGINS:
        cut = next(M._utc(c) for lbl, c, *_ in M.ORIGINS_MONTHLY if lbl == o)
        for scope, mask_r, mask_d in (("All BUILT", slice(None), slice(None)),
                                      ("Kroger", r["account"].isin(kroger_accts), acct.isin(kroger_accts))):
            hist = df.loc[mask_d] if scope == "Kroger" else df
            hist = hist[(hist["__time"] <= cut) & (hist["__time"] > cut - pd.Timedelta(weeks=13))]
            hv = hist.groupby("__time")["base_units"].sum()
            rr = r[(r["origin"] == o)]
            rr = rr[mask_r[rr.index]] if scope == "Kroger" else rr
            fw = rr.groupby("date")[["actual"] + show].sum().sort_index()
            panels.append({"origin": o, "scope": scope, "cutoff": str(cut.date()),
                           "hist": {"dates": [str(d.date()) for d in hv.index], "actual": hv.round(0).tolist()},
                           "fc": {"dates": [str(pd.Timestamp(d).date()) for d in fw.index],
                                  **{c: fw[c].round(0).tolist() for c in ["actual"] + show}}})
    names = {"recursive": "Recursive (v5 chart model)", "direct_served": "Direct, as served",
             "direct_fixed": "Direct, fixed", "flat": "Flat (last week)", "conn_L4W": "Connor L4W",
             "direct_served_lvlL4W": "Direct shape, L4W level"}
    html = _CHART_HTML.replace("__DATA__", json.dumps({"panels": panels, "names": names, "arms": show}))
    path.write_text(html)
    print(f"  wrote {path}")


_CHART_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MO_132 Quarterly Lines</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{--bg:#ffffff;--fg:#1d2433;--muted:#5b6475;--card:#f6f7f9;--line:#d9dde4}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#12151b;--fg:#e6e9ef;--muted:#9aa3b2;--card:#1b2029;--line:#2c3340}}
:root[data-theme="dark"]{--bg:#12151b;--fg:#e6e9ef;--muted:#9aa3b2;--card:#1b2029;--line:#2c3340}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p{color:var(--muted);margin:0 0 18px;max-width:900px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,520px),1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.card h2{font-size:15px;margin:0 0 8px}
</style></head><body>
<h1>Forecast lines vs actuals, measured fairly</h1>
<p>Each panel: 13 weeks of actual base units before the forecast date (grey), then 13 weeks of
actuals (black) against each forecast. Every forecast was made using only data available on
its forecast date. Internal working view (MO_132); not for client distribution.</p>
<div class="grid" id="g"></div>
<script>
const D = __DATA__;
const colors = ["#2f6fdf","#d9480f","#2b8a3e","#868e96","#ae3ec9","#f08c00"];
D.panels.forEach((p, i) => {
  const c = document.createElement("div"); c.className = "card";
  c.innerHTML = `<h2>${p.scope} &middot; forecast made ${p.cutoff}</h2><canvas id="c${i}" height="220"></canvas>`;
  document.getElementById("g").appendChild(c);
  const labels = p.hist.dates.concat(p.fc.dates);
  const pad = Array(p.hist.dates.length).fill(null);
  const ds = [{label: "Actual (before)", data: p.hist.actual.concat(Array(p.fc.dates.length).fill(null)),
               borderColor: "#adb5bd", borderWidth: 2, pointRadius: 0},
              {label: "Actual", data: pad.concat(p.fc.actual), borderColor: getComputedStyle(document.body).color,
               borderWidth: 2.5, pointRadius: 0}];
  D.arms.forEach((a, j) => ds.push({label: D.names[a], data: pad.concat(p.fc[a]), borderColor: colors[j],
                                    borderWidth: 1.5, pointRadius: 0, borderDash: a.includes("lvl") ? [5,3] : []}));
  new Chart(document.getElementById("c" + i), {type: "line", data: {labels, datasets: ds},
    options: {animation: false, plugins: {legend: {labels: {boxWidth: 12, font: {size: 11}}}},
              scales: {x: {ticks: {maxTicksLimit: 8}}, y: {beginAtZero: false}}}});
});
</script></body></html>"""


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origins", default="", help="comma list of origin labels (default: all 18)")
    ap.add_argument("--arms", default="stats,stats_vel,direct_served,direct_fixed,direct_vel",
                    help="arms to compute")
    ap.add_argument("--score-only", action="store_true", help="score cached arms, compute nothing")
    a = ap.parse_args()
    t0 = time.time()

    feats_r = list(pickle.load(open("outputs/model_retailer_sales_q50_v11_full.pkl", "rb")).feature_name_)
    feats_d = list(json.loads(DIRECT_META.read_text())["features_used"])
    df = M.load_panel(list(dict.fromkeys(feats_r + feats_d)))
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    df["series"] = sid_of(df[G].itertuples(index=False))
    assert (D26.N_ESTIMATORS, D26.EARLY_STOP, D26.RECENCY_LAMBDA) == (3000, 100, 0.02), "MO_26D settings changed"

    origins = M.ORIGINS_MONTHLY
    if a.origins:
        want = {s.strip() for s in a.origins.split(",")}
        origins = [o for o in origins if o[0] in want]
    todo = set(a.arms.split(",")) if not a.score_only else set()
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"MO_132 - one yardstick: {len(origins)} origins, computing {sorted(todo) or 'nothing'}")

    for lbl, c, *_ in origins:
        cut = M._utc(c)
        tr = None
        for arm in ("stats", "stats_vel", "direct_served", "direct_fixed", "direct_vel"):
            p = CACHE / f"{arm}_{lbl}.parquet"
            if arm not in todo or p.exists():
                continue
            if tr is None:
                tr = M.cutoff_frame(df, cut)
            t1 = time.time()
            if arm.startswith("stats"):
                out = run_stats(tr, cut, velocity=(arm == "stats_vel"))
            else:
                fixed = arm in ("direct_fixed", "direct_vel")
                out = run_direct(tr, feats_d, cut, refit=fixed, calendar=fixed,
                                 velocity=(arm == "direct_vel")).rename(columns={"value": arm})
            tmp = p.with_suffix(f".{os.getpid()}.tmp")
            out.to_parquet(tmp)
            os.replace(tmp, p)
            print(f"  {lbl} {arm}: {len(out):,} forecasts | {time.time() - t1:,.0f}s | total {time.time() - t0:,.0f}s")

    # ---- assemble rows
    r = pd.read_parquet(ROWS_IN).rename(columns={"model": "recursive"})
    r = r.drop(columns=[c for c in r.columns if c.startswith("model_seed")])
    r["date"] = pd.to_datetime(r["date"], utc=True)
    if a.origins:
        r = r[r["origin"].isin([o[0] for o in origins])]
    r = r.reset_index(drop=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values      # positional; merges below keep row order
    have = {"stats": STAT_ARMS, "stats_vel": VEL_STAT_ARMS, "direct_served": ["direct_served"],
            "direct_fixed": ["direct_fixed"], "direct_vel": ["direct_vel"]}
    fallback = {}
    for arm, cols in have.items():
        parts = [pd.read_parquet(CACHE / f"{arm}_{o[0]}.parquet").assign(origin=o[0])
                 for o in origins if (CACHE / f"{arm}_{o[0]}.parquet").exists()]
        if len(parts) < len(origins):
            print(f"  ⚠️ {arm}: cached for {len(parts)}/{len(origins)} origins -- left out of scoring")
            for c_ in cols:
                ARMS.remove(c_)
                if c_ in LVL_PARENTS:
                    ARMS.remove(f"{c_}_lvlL4W"); LVL_PARENTS.remove(c_)
            continue
        cp = pd.concat(parts, ignore_index=True)
        cp["date"] = pd.to_datetime(cp["date"], utc=True)
        n0 = len(r)
        r = r.merge(cp[["origin", "series", "date"] + cols], on=["origin", "series", "date"], how="left")
        assert len(r) == n0, f"{arm}: duplicate forecasts changed the row count"
        for c_ in cols:
            miss = r[c_].isna().values & ~zero
            fallback[c_] = int(miss.sum())
            r[c_] = np.where(zero, 0.0, np.where(miss, r["flat"], r[c_]))
    r["blend"] = 0.5 * r["mo130"] + 0.5 * r["flat"]
    for p_ in LVL_PARENTS:
        mean_p = r.groupby(["origin", "series"])[p_].transform("mean")
        r[f"{p_}_lvlL4W"] = np.where(mean_p > 0, r[p_] * r["conn_L4W"] / mean_p.where(mean_p > 0, 1), r["conn_L4W"])
    arms = [x for x in ARMS if x in r.columns]
    print(f"  rows {len(r):,} | arms {arms} | fell back to flat (no forecast): {fallback}")
    r.drop(columns=[c for c in ("key",) if c in r.columns]).to_parquet(OUT_ROWS)

    # ---- level scores
    ex = r[~r["is_new"]]
    res = {"existing": M.score_levels(ex, arms), "planning_total": M.score_levels(r, arms),
           "fallback_to_flat_rows": fallback, "arms": arms}
    E = res["existing"]
    print("\n=== EXISTING SERIES: error (lower is better) and bias ===")
    print(f"  {'arm':<22s}{'cell x wk':>10s}{'acct x mo':>10s}{'port x mo':>10s}{'bias':>8s}")
    for x in sorted(arms, key=lambda k: E["cell x week"][k]):
        print(f"  {x:<22s}{E['cell x week'][x]:>10.2f}{E['account x month'][x]:>10.2f}"
              f"{E['portfolio x month'][x]:>10.2f}{E['portfolio_bias'][x]:>8.3f}")
    for lvl, _ in M.LEVELS_V2:
        print(f"  BY HISTORY BAND, {lvl}")
        for b, v in E[lvl]["by_band"].items():
            best = min(arms, key=lambda k: v[k])
            print(f"    {b:<10s} n={v['n']:>7,}  best {best} {v[best]:.1f} | recursive {v['recursive']:.1f} "
                  f"| direct_served {v.get('direct_served', np.nan):.1f} | flat {v['flat']:.1f} | conn_L4W {v['conn_L4W']:.1f}")

    # ---- velocity view: grade each forecast at the ACTUAL doors of the target week
    tdp_act = df.groupby(["series", "__time"], observed=True)["tdp"].mean()
    tdp_cut = pd.concat([last_tdp(df[df["__time"] <= M._utc(c)]).rename("tdp_cut").to_frame().assign(origin=lbl)
                         for lbl, c, *_ in origins]).rename_axis("series").reset_index()
    vx = ex.merge(tdp_cut, on=["origin", "series"], how="left")
    vx["tdp_act"] = tdp_act.reindex(pd.MultiIndex.from_arrays([vx["series"], vx["date"]])).values
    ok = (vx["tdp_cut"] > TDP_FLOOR) & (vx["tdp_act"] > TDP_FLOOR)
    ratio = np.where(ok, vx["tdp_act"] / vx["tdp_cut"].where(ok, 1), 1.0)
    for x in arms:
        vx[x] = vx[x] * ratio
    res["velocity_view"] = M.score_levels(vx, arms)
    res["velocity_view_adjusted_share"] = float(vx.loc[ok, "actual"].sum() / vx["actual"].sum())
    V = res["velocity_view"]
    print(f"\n=== VELOCITY VIEW: graded at actual doors ({res['velocity_view_adjusted_share']:.0%} of volume adjusted) ===")
    print(f"  {'arm':<22s}{'cell x wk':>10s}{'acct x mo':>10s}{'port x mo':>10s}{'bias':>8s}   (units view cw)")
    for x in sorted(arms, key=lambda k: V["cell x week"][k]):
        print(f"  {x:<22s}{V['cell x week'][x]:>10.2f}{V['account x month'][x]:>10.2f}"
              f"{V['portfolio x month'][x]:>10.2f}{V['portfolio_bias'][x]:>8.3f}   ({E['cell x week'][x]:.2f})")

    # ---- CIs vs what BUILT is served, and vs flat
    res["ci"] = {}
    refs = [x for x in ("direct_served", "flat") if x in arms]
    print("\nMARGINS OF ERROR (moving-block bootstrap over origins; descriptive, no correction)")
    for ref in refs:
        for x in arms:
            if x == ref:
                continue
            for lvl, _ in M.LEVELS_V2:
                b = M.bootstrap_diff(ex, x, ref, level=lvl, n=2000)
                res["ci"][f"{x}-{ref} | {lvl}"] = b
            row = [res["ci"][f"{x}-{ref} | {l}"] for l, _ in M.LEVELS_V2]
            print(f"  {x:>22s} - {ref:<13s} " + "  ".join(
                f"{v['diff']:+6.2f} [{v['ci95'][0]:+.1f},{v['ci95'][1]:+.1f}]{'*' if v['significant'] else ' '}" for v in row))

    # ---- shape
    exs = M._prep_scoring(ex, arms)
    kro = exs[exs["account"].str.upper().str.contains("KROGER")]
    res["shape"] = {"portfolio x week": shape_scores(exs, arms, ["origin"], "date"),
                    "account x month": shape_scores(exs[exs["full_month"]], arms, ["origin", "account"], "month"),
                    "kroger x week": shape_scores(kro, arms, ["origin"], "date"),
                    "turns (portfolio x week)": turn_scores(exs, arms)}
    S = res["shape"]
    print("\n=== SHAPE with 95% margins (origin block bootstrap). Chance: precision 50%, r 0 ===")
    print("  precision = share of the arm's up/down calls that were right; calls = share of real")
    print("  moves the arm called at all; r = rank correlation of changes; * = beats chance on both")
    for lvl in ("portfolio x week", "account x month", "kroger x week"):
        Sl = S[lvl]
        print(f"  {lvl} ({Sl['n_moves']} real moves, {Sl['n_origins']} origins)")
        for x in sorted(arms, key=lambda k: -(Sl[k]["change_r"] or 0)):
            v = Sl[x]
            print(f"    {x:<22s} precision {v['precision']:5.1f} [{v['precision_ci'][0]:5.1f},{v['precision_ci'][1]:5.1f}]"
                  f"  calls {v['call_rate']:5.1f}%  r {v['change_r']:+.2f} [{v['change_r_ci'][0]:+.2f},{v['change_r_ci'][1]:+.2f}]"
                  f"{'  *' if v['beats_chance'] else ''}")
    tu = S["turns (portfolio x week)"]
    print(f"  turns (portfolio x week, {tu['actual_turns']} actual): " + "; ".join(
        f"{x} matched {tu[x]['turns_hit']:.0f}% / called {tu[x]['turns_called']} / right {tu[x]['turns_precision']:.0f}%"
        for x in arms if tu[x]["turns_called"]))

    # ---- level bias by distribution trend
    trend = pd.concat([tdp_trend(df, M._utc(c)).rename("trend").to_frame().assign(origin=lbl)
                       for lbl, c, *_ in origins]).rename_axis("series").reset_index()
    et = ex.merge(trend, on=["origin", "series"], how="left").fillna({"trend": "unknown"})
    res["bias_by_trend"] = {t: {x: float(g[x].sum() / g["actual"].sum()) for x in arms} | {"n": len(g),
                                "actual_share": float(g["actual"].sum() / et["actual"].sum())}
                            for t, g in et.groupby("trend")}
    print("\n=== LEVEL BIAS BY DISTRIBUTION TREND (1.00 = right level) ===")
    for t, v in res["bias_by_trend"].items():
        print(f"  {t:<10s} ({v['actual_share']:.0%} of volume)  " + "  ".join(
            f"{x}={v[x]:.2f}" for x in ("recursive", "direct_served", "direct_fixed", "flat", "conn_L4W", "mo130") if x in v))

    # ---- predictions
    CW, AM = "cell x week", "account x month"
    g_ = lambda x, l=CW: E[l].get(x, np.nan)
    pw = S["portfolio x week"]
    lv = [p for p in LVL_PARENTS if f"{p}_lvlL4W" in arms]
    bt = res["bias_by_trend"]
    checks = [
        ("P1", abs(g_("flat") - g_("conn_L4W")) < 1 and max(g_("flat"), g_("conn_L4W")) < min(g_("recursive"), g_("direct_served")),
         f"cw flat {g_('flat'):.2f} conn_L4W {g_('conn_L4W'):.2f} recursive {g_('recursive'):.2f} direct_served {g_('direct_served'):.2f}"),
        ("P2", abs(g_("direct_served") - g_("recursive")) < 2, f"cw direct_served {g_('direct_served'):.2f} vs recursive {g_('recursive'):.2f}"),
        ("P3", g_("direct_served") - g_("direct_fixed") >= 0.5, f"cw direct_fixed {g_('direct_fixed'):.2f} vs served {g_('direct_served'):.2f}"),
        ("P4", pw.get("direct_served", {}).get("change_r", np.nan) > pw["recursive"]["change_r"],
         f"portfolio wk change r: direct_served {pw.get('direct_served', {}).get('change_r', np.nan):.2f} vs recursive {pw['recursive']['change_r']:.2f}"),
        ("P5", any(g_(f"{p}_lvlL4W", AM) < min(g_(p, AM), g_("conn_L4W", AM)) for p in lv),
         "am: " + ", ".join(f"{p}_lvlL4W {g_(p + '_lvlL4W', AM):.2f} vs {p} {g_(p, AM):.2f} / L4W {g_('conn_L4W', AM):.2f}" for p in lv)),
        ("P6", "growing" in bt and "shrinking" in bt and all(bt["growing"][x] < 0.9 for x in arms) and all(bt["shrinking"][x] > 1.1 for x in arms),
         f"growing max bias {max(bt.get('growing', {x: np.nan for x in arms})[x] for x in arms):.2f}, "
         f"shrinking min bias {min(bt.get('shrinking', {x: np.nan for x in arms})[x] for x in arms):.2f}"),
        ("P7", abs(g_("ses") - g_("flat")) < 0.5 and g_("holt_damped") >= g_("flat") and g_("ets") >= g_("flat"),
         f"cw ses {g_('ses'):.2f} holt_damped {g_('holt_damped'):.2f} ets {g_('ets'):.2f} flat {g_('flat'):.2f}"),
        ("P8", all(V[CW][x] < E[CW][x] for x in arms) and all(
            (V[CW][x] - V[CW]["flat"]) <= 0.5 * (E[CW][x] - E[CW]["flat"]) for x in ("recursive", "direct_served") if x in arms),
         "cw gap to flat, units -> velocity view: " + ", ".join(
             f"{x} {E[CW][x] - E[CW]['flat']:+.2f} -> {V[CW][x] - V[CW]['flat']:+.2f}" for x in ("recursive", "direct_served") if x in arms)),
        ("P9", g_("direct_vel") < g_("direct_fixed") and g_("ses_vel") < g_("ses"),
         f"cw direct_vel {g_('direct_vel'):.2f} vs direct_fixed {g_('direct_fixed'):.2f}; ses_vel {g_('ses_vel'):.2f} vs ses {g_('ses'):.2f}"),
    ]
    print("\nPREDICTIONS")
    res["predictions"] = {}
    for pid, ok, msg in checks:
        tag = "UNTESTABLE" if ok is None or (isinstance(ok, float) and np.isnan(ok)) else ("HOLDS" if ok else "FAILS")
        res["predictions"][pid] = {"result": tag, "detail": msg}
        print(f"  {pid} {tag:<10s} {msg}")

    OUT.write_text(json.dumps(res, indent=2, default=str))
    if not a.origins:
        write_chart(df, r, CHART)
    print(f"\nwrote {OUT} and {OUT_ROWS} ({time.time() - t0:,.0f}s)")


if __name__ == "__main__":
    main()
