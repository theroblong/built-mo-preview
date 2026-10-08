#!/usr/bin/env python
"""MO_131 - Forward tracker: which contender actually forecasts best on data nobody has seen?

WHERE THIS CAME FROM
--------------------
MO_129 and MO_130 used every historical origin for design, and their 13-week horizons
overlap, so no untouched history is left for a clean confirmation (MO_130 skeptic review,
2026-10-08). The clean test is NEW SPINS weeks. This script implements the
pre-registration in docs/FORECAST_PREREGISTRATION.md:

  register  at the newest data week (the cutoff), forecast h = 1..13 for every series with
            every contender and save to forecasts_registered/ (a TRACKED folder: the commit
            timestamp proves the forecasts predate their outcomes). Refuses to overwrite.
  score     for each registered cutoff whose 13 forecast weeks are now in the panel, score
            all contenders with the MO_80 yardstick (3 levels, history bands, per-year
            two-sided seasonal bias) and update forecasts_registered/scoreboard.json.

PRIOR WORK (docs/SETTLED_FINDINGS.md DRAFT + live notes 2026-10-07/08)
  MO_129  clean baseline: shipped model trails flat at cw/am, ties at pm; flat ~= L4W.
  MO_130  anchor + corrections ties flat/L4W at every level; Jan-Mar "fix" did not survive.
  MO_130 review  50/50 mo130+flat average looked best (post-hoc) -> registered here as a
          contender instead of being claimed.

CONTENDERS (frozen; definitions in docs/FORECAST_PREREGISTRATION.md)
  champion  shipped model: MO_80.run_production (production-equivalent MO_27 path, step
            mode, ROUTER_SEASONAL off, production training). Forward forecasts use
            production's donor features (no look-ahead going forward).
  flat      last reported week (MO_129)
  conn_L4W  4-calendar-week Base U/S/W x current TDP (MO_129)
  mo130     MO_130 v8 (--min-rows 13 --val series --target velocity --recency 0.02 --recal-oot)
  blend     0.5 x mo130 + 0.5 x flat
  Lapsed series (>= 9 weeks without data at the cutoff) = 0 for every contender; series that
  first appear after the cutoff are scored at 0 for every contender.

LEVELS: cell x week, account x month, portfolio x month (complete months), bias; every
level by history band (new / lapsed / low-TDP / <13 / 13-25 / 26-51 / 52+); Jan-Mar and
Oct-Dec bias PER CALENDAR YEAR, two-sided. Headline = existing series.

PREDICTIONS, RECORDED BEFORE ANY OUTCOME EXISTS (also in docs/FORECAST_PREREGISTRATION.md):
  P1  flat and conn_L4W tie at cell x week (|difference| < 1pp).
  P2  mo130 ties flat at all three levels (CIs include 0).
  P3  blend beats flat at account x month by >= 1pp with a CI excluding 0.
  P4  The champion trails flat at cell x week.
  P5  Jan-Mar 2027 target weeks: flat, conn_L4W and the champion have bias < 0.90; mo130
      and blend fall within 0.90-1.10.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

os.environ["MO_SEASONAL_MODE"] = "step"
import MO_80_quarterly_honest_backtest as M        # import asserts forecast + training parity
import MO_129_honest_rebaseline as B129             # flat / Connor definitions
import MO_130_anchor_plus_corrections as B130       # mo130 fit_forecast()

assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"

ROOT = Path(__file__).resolve().parent.parent
REG_DIR = Path(os.environ.get("MO_REG_DIR", ROOT / "forecasts_registered"))   # env override = tests only
SCOREBOARD = REG_DIR / "scoreboard.json"
CONTENDERS = ["champion", "flat", "conn_L4W", "mo130", "blend"]
MO130_SETTINGS = SimpleNamespace(min_rows=13, val="series", drift=False, recal=0, recal_oot=True,
                                 target="velocity", recency=0.02)
H = M.HORIZON


def _git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return "unknown"


def _load():
    feats = list(pickle.load(open("outputs/model_retailer_sales_q50_v11_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    return feats, df


def register(trees: int | None, cutoff: str | None = None) -> None:
    feats, df = _load()
    # --cutoff is for END-TO-END TESTS only (register at a past date, then score at once);
    # real registrations always use the latest data week.
    cut = M._utc(cutoff) if cutoff else df["__time"].max()
    tag = str(cut.date())
    out = REG_DIR / f"{tag}.parquet"
    meta_p = REG_DIR / f"{tag}.meta.json"
    if out.exists():
        print(f"already registered: {out} -- refusing to overwrite"); return
    t0 = time.time()
    print(f"MO_131 register: cutoff {tag} (latest data week), {H} weeks ahead")
    tr = df[df["__time"] <= cut]
    fw = [cut + pd.Timedelta(weeks=h) for h in range(1, H + 1)]
    qs, qe = fw[0], fw[-1] + pd.Timedelta(days=6)
    keys = set(tr.groupby(M.GROUP_COLS, observed=True).size().index)

    # champion: production-equivalent path; going forward the donor features carry no
    # look-ahead, so they are used as production uses them.
    M.NEUTRALIZE_DONOR_FEATURES = False
    champ = M.run_production(df, feats, cut, qs, qe, keys, trees, fw, M.seasonal_index_at(cut))
    fit_c = M.FIT_LOG[-1]
    print(f"  champion: {len(champ):,} forecasts | best_iter {fit_c['best_iteration']} | {time.time()-t0:,.0f}s")

    # mo130 v8
    cap = trees or M.TREES_CAP
    params = dict(objective="quantile", alpha=0.5, **M.PROD_LGBM)
    fit = B130.fit_forecast(df, cut, MO130_SETTINGS, cap, B130.FEATS, params)
    p130 = fit["p"].set_index(["series", "date_y"])["mo130"]
    print(f"  mo130: {len(p130):,} forecasts | shift {fit['shift']:+.3f} | best_iter {fit['best']} | {time.time()-t0:,.0f}s")

    # flat / Connor, and lapse status, per series at the cutoff
    ht = M.history_table(tr, cut)
    tr2 = tr.copy()
    tr2["_t"] = pd.to_datetime(tr2["__time"], utc=True).dt.tz_localize(None)
    cut_n = cut.tz_localize(None)
    rows = []
    for key, g in tr2.groupby(M.GROUP_COLS, observed=True):
        bu = pd.to_numeric(g["base_units"], errors="coerce").dropna()
        last = float(bu.iloc[-1]) if len(bu) else 0.0
        l4 = B129.connor(g, cut_n, 4, last)
        lapsed = bool(ht.loc[key, "lapsed"]) if key in ht.index else True
        sid = " | ".join(map(str, key))
        for h, fd in enumerate(fw, start=1):
            fdn = fd.tz_localize(None)
            c = 0.0 if lapsed else float(champ.get((key, fd), np.nan))
            m130 = 0.0 if lapsed else float(p130.get((sid, fdn), np.nan))
            f = 0.0 if lapsed else last
            rows.append({"series": sid, **dict(zip(M.GROUP_COLS, map(str, key))), "date": fd, "h": h,
                         "lapsed": lapsed, "champion": c, "flat": f,
                         "conn_L4W": 0.0 if lapsed else l4, "mo130": m130,
                         "blend": 0.5 * m130 + 0.5 * f if np.isfinite(m130) else np.nan})
    r = pd.DataFrame(rows)
    miss = {c: int(r[c].isna().sum()) for c in CONTENDERS}
    REG_DIR.mkdir(exist_ok=True)
    r.to_parquet(out)
    meta = {"cutoff": tag, "registered_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "code_commit": _git_head(), "data_max_week": tag, "n_series": int(r["series"].nunique()),
            "n_rows": len(r), "missing_by_contender": miss,
            "champion_fit": fit_c, "mo130_fit": {k: fit[k] for k in ("rows", "val_share", "shift", "best", "n_series")},
            "mo130_settings": vars(MO130_SETTINGS), "contenders": CONTENDERS,
            "preregistration": "docs/FORECAST_PREREGISTRATION.md"}
    meta_p.write_text(json.dumps(meta, indent=2, default=str))
    print(f"  wrote {out} ({len(r):,} rows, {r['series'].nunique():,} series; "
          f"missing {miss}) and {meta_p.name} | {time.time()-t0:,.0f}s")
    print("  COMMIT these files now -- the commit timestamp is the proof of pre-registration."
          if not cutoff else "  (test registration at a past cutoff -- never commit)")


def score() -> None:
    feats, df = _load()
    panel_end = df["__time"].max()
    board = json.loads(SCOREBOARD.read_text()) if SCOREBOARD.exists() else {"scored": {}}
    for f in sorted(REG_DIR.glob("????-??-??.parquet")):      # registrations only, not *.scored_rows
        tag = f.stem
        if tag in board["scored"]:
            continue
        reg = pd.read_parquet(f)
        last_wk = pd.to_datetime(reg["date"], utc=True).max()
        if last_wk > panel_end:
            print(f"  {tag}: horizon ends {last_wk.date()}, data ends {panel_end.date()} -- not yet scorable")
            continue
        cut = M._utc(tag)
        ev = M.build_eval_rows(df, cut, cut + pd.Timedelta(weeks=1), cut + pd.Timedelta(weeks=H))
        ev["series"] = [" | ".join(map(str, k)) for k in ev["key"]]
        ev["origin"] = tag
        reg["date"] = pd.to_datetime(reg["date"], utc=True)
        ev = ev.merge(reg[["series", "date"] + CONTENDERS], on=["series", "date"], how="left")
        ev.loc[ev["is_new"], CONTENDERS] = 0.0                       # unseen at the cutoff
        ev = ev.dropna(subset=CONTENDERS)
        ex = ev[~ev["is_new"]]
        res = {"existing": M.score_levels(ex, CONTENDERS), "planning_total": M.score_levels(ev, CONTENDERS)}
        q = ex.assign(_y=pd.to_datetime(ex["date"], utc=True).dt.year,
                      _m=pd.to_datetime(ex["date"], utc=True).dt.month)
        res["season_bias_by_year"] = {
            f"{name} {y}": {c: float(g[c].sum() / g["actual"].sum()) for c in CONTENDERS}
            for name, mm in (("Jan-Mar", (1, 2, 3)), ("Oct-Dec", (10, 11, 12)))
            for y, g in q[q["_m"].isin(mm)].groupby("_y")}
        board["scored"][tag] = res
        E = res["existing"]
        print(f"  {tag}: scored -- cw/am/pm: " + "; ".join(
            f"{c} {E['cell x week'][c]:.1f}/{E['account x month'][c]:.1f}/{E['portfolio x month'][c]:.1f}"
            for c in CONTENDERS))
        ev.drop(columns=["key"]).to_parquet(REG_DIR / f"{tag}.scored_rows.parquet")
    board["updated_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    board["n_scored"] = len(board["scored"])
    REG_DIR.mkdir(exist_ok=True)
    SCOREBOARD.write_text(json.dumps(board, indent=2, default=str))
    print(f"  scoreboard: {board['n_scored']} origin(s) scored -> {SCOREBOARD}")
    if board["n_scored"] >= 3:                                   # pooled view + CIs once meaningful
        allrows = pd.concat([pd.read_parquet(REG_DIR / f"{t}.scored_rows.parquet") for t in board["scored"]])
        ex = allrows[~allrows["is_new"]]
        for y in ("flat", "conn_L4W", "mo130", "blend"):
            for lvl, _ in M.LEVELS_V2:
                b = M.bootstrap_diff(ex, y, "champion", level=lvl, n=2000)
                print(f"    {y:>8s} - champion {lvl:<18s} {b['diff']:+.2f} CI {b['ci95']}{' *' if b['significant'] else ''}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["register", "score"])
    ap.add_argument("--trees", type=int, default=None, help="cap for smoke tests; None = production")
    ap.add_argument("--cutoff", default=None, help="TESTS ONLY: register at a past week")
    a = ap.parse_args()
    register(a.trees, a.cutoff) if a.cmd == "register" else score()


if __name__ == "__main__":
    main()
