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

CONTENDERS (saved; definitions in docs/FORECAST_PREREGISTRATION.md)
  served_v11d  the forecast BUILT is actually served: scripts/outputs/retailer_sales_forecast.parquet
            (MO_27D direct multi-horizon v11d; lapsed series at the expected resume value).
            Copied byte for byte into the registration with its SHA-256 (skeptic 2026-10-08:
            the draft registered the recursive path as "champion", which is not what is served).
  recursive MO_80.run_production (production-equivalent MO_27 recursive path, step mode,
            ROUTER_SEASONAL off, production training). Forward forecasts use production's
            donor features (no look-ahead going forward). Was "champion" in the draft.
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
  P4  The recursive model trails flat at cell x week.
  P5  Jan-Mar 2027 target weeks: flat, conn_L4W and the recursive model have bias < 0.90;
      mo130 and blend fall within 0.90-1.10.

DECISION RULE: not attached to these saved forecasts. The skeptic (2026-10-08) found the
6-cutoff rule unsound; Jason asked for all data and no arbitrary windows, so the rule is
rewritten under MO_132 (all 18 backtest origins + every new week, always-valid intervals).

TAMPER-PROOFING (skeptic must-fix #7): real registrations refuse --trees/--cutoff, refuse a
dirty scripts/ tree, and record SHA-256 of the panel, seasonal index, model, code and the
registration file itself. Bands (run, tdp_recent, lapsed) are saved at registration so
scoring does not recompute them from a restated panel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
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
SCRIPTS = ROOT / "scripts"
TEST_MODE = "MO_REG_DIR" in os.environ                                       # env override = tests only
REG_DIR = Path(os.environ.get("MO_REG_DIR", ROOT / "forecasts_registered"))
SCOREBOARD = REG_DIR / "scoreboard.json"
SERVED = SCRIPTS / "outputs" / "retailer_sales_forecast.parquet"
MODEL_PKL = SCRIPTS / "outputs" / "model_retailer_sales_q50_v11_full.pkl"
CONTENDERS = ["served_v11d", "recursive", "flat", "conn_L4W", "mo130", "blend"]
BASELINE = "served_v11d"                                                     # what BUILT sees today
CODE_FILES = ["MO_131_forward_tracker.py", "MO_80_quarterly_honest_backtest.py",
              "MO_129_honest_rebaseline.py", "MO_130_anchor_plus_corrections.py", "mo_panel.py",
              "MO_27_retailer_sales_forecast.py", "MO_27D_direct_forecast.py"]
MO130_SETTINGS = SimpleNamespace(min_rows=13, val="series", drift=False, recal=0, recal_oot=True,
                                 target="velocity", recency=0.02)
H = M.HORIZON


def _git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return "unknown"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _dirty_scripts() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no",
                               "--", "scripts"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as e:
        return f"git status failed: {e}"


def _served(fw) -> pd.Series:
    """The served forecast as a (series, date) -> base units lookup; must cover the same weeks."""
    s = pd.read_parquet(SERVED)
    s["date"] = pd.to_datetime(s["__time"], utc=True)
    s["series"] = [" | ".join(map(str, k)) for k in s[M.GROUP_COLS].itertuples(index=False)]
    assert set(s["date"]) == set(fw), f"served weeks {sorted(set(s['date']))[:2]}... != registration weeks"
    assert not s.duplicated(["series", "date"]).any(), "served file has duplicate series-weeks"
    return s.set_index(["series", "date"])["forecast_units_base"].astype(float)


def _load():
    feats = list(pickle.load(open(MODEL_PKL, "rb")).feature_name_)
    df = M.load_panel(feats)
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    return feats, df


def register(trees: int | None, cutoff: str | None = None) -> None:
    # --trees / --cutoff are for END-TO-END TESTS only and must write to a scratch MO_REG_DIR;
    # real registrations use the latest data week, production trees and a clean scripts/ tree.
    test = TEST_MODE or trees is not None or cutoff is not None
    if (trees is not None or cutoff is not None) and not TEST_MODE:
        raise SystemExit("--trees/--cutoff are test-only: set MO_REG_DIR to a scratch folder")
    if not test and (dirty := _dirty_scripts()):
        raise SystemExit(f"scripts/ has uncommitted changes -- commit first so code_commit is true:\n{dirty}")
    feats, df = _load()
    cut = M._utc(cutoff) if cutoff else df["__time"].max()
    tag = str(cut.date())
    out = REG_DIR / f"{tag}.parquet"
    meta_p = REG_DIR / f"{tag}.meta.json"
    if out.exists():
        print(f"already registered: {out} -- refusing to overwrite"); return
    t0 = time.time()
    print(f"MO_131 register: cutoff {tag} (latest data week), {H} weeks ahead{' [TEST]' if test else ''}")
    tr = df[df["__time"] <= cut]
    fw = [cut + pd.Timedelta(weeks=h) for h in range(1, H + 1)]
    qs, qe = fw[0], fw[-1] + pd.Timedelta(days=6)
    keys = set(tr.groupby(M.GROUP_COLS, observed=True).size().index)
    served = _served(fw) if cutoff is None else None               # past test cutoffs have no served file

    # recursive: production-equivalent MO_27 path; going forward the donor features carry no
    # look-ahead, so they are used as production uses them.
    M.NEUTRALIZE_DONOR_FEATURES = False
    champ = M.run_production(df, feats, cut, qs, qe, keys, trees, fw, M.seasonal_index_at(cut))
    fit_c = M.FIT_LOG[-1]
    print(f"  recursive: {len(champ):,} forecasts | best_iter {fit_c['best_iteration']} | {time.time()-t0:,.0f}s")

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
        info = ht.loc[key] if key in ht.index else None
        lapsed = bool(info["lapsed"]) if info is not None else True
        sid = " | ".join(map(str, key))
        for h, fd in enumerate(fw, start=1):
            fdn = fd.tz_localize(None)
            c = 0.0 if lapsed else float(champ.get((key, fd), np.nan))
            m130 = 0.0 if lapsed else float(p130.get((sid, fdn), np.nan))
            f = 0.0 if lapsed else last
            sv = float(served.get((sid, fd), np.nan)) if served is not None else np.nan
            rows.append({"series": sid, **dict(zip(M.GROUP_COLS, map(str, key))), "date": fd, "h": h,
                         "lapsed": lapsed, "run_weeks": int(info["run"]) if info is not None else 0,
                         "tdp_recent": float(info["tdp_recent"]) if info is not None else 0.0,
                         "served_v11d": sv, "recursive": c, "flat": f,
                         "conn_L4W": 0.0 if lapsed else l4, "mo130": m130,
                         "blend": 0.5 * m130 + 0.5 * f if np.isfinite(m130) else np.nan})
    r = pd.DataFrame(rows)
    contenders = CONTENDERS if served is not None else [c for c in CONTENDERS if c != "served_v11d"]
    miss = {c: int(r[c].isna().sum()) for c in contenders}
    REG_DIR.mkdir(exist_ok=True)
    r.to_parquet(out)
    hashes = {"registration": _sha256(out), "panel": _sha256(SCRIPTS / M.PARQUET),
              "seasonal_index": _sha256(SCRIPTS / M.SEASONAL_INDEX_CSV), "model_pkl": _sha256(MODEL_PKL),
              "code": {f: _sha256(SCRIPTS / f) for f in CODE_FILES}}
    if served is not None:
        shutil.copy2(SERVED, REG_DIR / f"{tag}.served_v11d.parquet")   # byte-for-byte archive
        hashes["served_v11d"] = _sha256(REG_DIR / f"{tag}.served_v11d.parquet")
        assert hashes["served_v11d"] == _sha256(SERVED)
    meta = {"cutoff": tag, "test": test,
            "registered_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "code_commit": _git_head(), "scripts_tree_clean": not _dirty_scripts(),
            "data_max_week": str(df["__time"].max().date()), "sha256": hashes,
            "n_series": int(r["series"].nunique()), "n_rows": len(r), "missing_by_contender": miss,
            "recursive_fit": fit_c, "recursive_trees_cap": trees or M.TREES_CAP,
            "mo130_fit": {k: fit[k] for k in ("rows", "val_share", "shift", "best", "n_series")},
            "mo130_settings": vars(MO130_SETTINGS), "mo130_trees_cap": cap, "contenders": contenders,
            "baseline": BASELINE if served is not None else "recursive",
            "decision_rule": "none attached; rewritten under MO_132 (all data, always-valid intervals)",
            "preregistration": "docs/FORECAST_PREREGISTRATION.md"}
    meta_p.write_text(json.dumps(meta, indent=2, default=str))
    print(f"  wrote {out} ({len(r):,} rows, {r['series'].nunique():,} series; "
          f"missing {miss}) and {meta_p.name} | {time.time()-t0:,.0f}s")
    print("  COMMIT these files now -- the commit timestamp proves the forecasts predate their outcomes."
          if not test else "  (TEST registration -- never commit)")


ADD_PREDICTIONS = {
    "direct_fixed": "MO_132 direct_fixed (MO_26D settings, calendar-week targets, refit on all targets).",
    "rec_dirfix": ("0.5 x recursive + 0.5 x direct_fixed. Found post hoc in MO_132 (exploratory "
                   "32.18 / 20.29 / 10.47); registered here instead of claimed. PREDICTION: beats "
                   "recursive at all three levels; ties flat at cell x week and account x month; beats "
                   "flat at portfolio x month."),
}


def register_add() -> None:
    """Add challengers to the newest registration WITHOUT touching it (Jason 2026-10-08):
    direct_fixed and the 50/50 recursive + direct_fixed combination, in their own file."""
    import MO_132_one_yardstick as P                # MO_132 asserts donor neutralization at import
    if not TEST_MODE and (dirty := _dirty_scripts()):
        raise SystemExit(f"scripts/ has uncommitted changes -- commit first:\n{dirty}")
    feats_d = list(json.loads((SCRIPTS / P.DIRECT_META).read_text())["features_used"])
    feats_r = list(pickle.load(open(MODEL_PKL, "rb")).feature_name_)
    df = M.load_panel(list(dict.fromkeys(feats_r + feats_d)))
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    cut = df["__time"].max()
    tag = str(cut.date())
    reg_p = REG_DIR / f"{tag}.parquet"
    out = REG_DIR / f"{tag}.add-direct_fixed.parquet"
    if not reg_p.exists():
        raise SystemExit(f"no registration at the latest data week {tag}")
    if out.exists():
        print(f"already added: {out} -- refusing to overwrite"); return
    t0 = time.time()
    # Forward forecasts: donor features carry no look-ahead going forward, as for `recursive`.
    M.NEUTRALIZE_DONOR_FEATURES = False
    p = P.run_direct(M.cutoff_frame(df, cut), feats_d, cut, refit=True, calendar=True)
    reg = pd.read_parquet(reg_p)[["series", "date", "lapsed", "recursive", "flat"]]
    reg["date"] = pd.to_datetime(reg["date"], utc=True)
    p["date"] = pd.to_datetime(p["date"], utc=True)
    r = reg.merge(p, on=["series", "date"], how="left")
    miss = int((r["value"].isna() & ~r["lapsed"]).sum())
    r["direct_fixed"] = np.where(r["lapsed"], 0.0, r["value"].fillna(r["flat"]))
    r["rec_dirfix"] = 0.5 * r["recursive"] + 0.5 * r["direct_fixed"]
    r = r[["series", "date", "direct_fixed", "rec_dirfix"]]
    r.to_parquet(out)
    meta = {"cutoff": tag, "test": TEST_MODE, "adds_to": reg_p.name,
            "registered_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "code_commit": _git_head(), "scripts_tree_clean": not _dirty_scripts(),
            "data_max_week": tag, "contenders": list(ADD_PREDICTIONS), "definitions": ADD_PREDICTIONS,
            "fell_back_to_flat": miss, "n_rows": len(r),
            "sha256": {"add": _sha256(out), "base_registration": _sha256(reg_p),
                       "panel": _sha256(SCRIPTS / M.PARQUET),
                       "code": {f: _sha256(SCRIPTS / f) for f in CODE_FILES + ["MO_132_one_yardstick.py",
                                                                             "MO_26D_direct_multihorizon_train.py"]}},
            "decision_rule": "none attached; rewritten under MO_132 (all data, always-valid intervals)"}
    (REG_DIR / f"{tag}.add-direct_fixed.meta.json").write_text(json.dumps(meta, indent=2, default=str))
    print(f"  wrote {out.name} ({len(r):,} rows; fell back to flat {miss}) | {time.time() - t0:,.0f}s")
    print("  COMMIT these files now." if not TEST_MODE else "  (TEST -- never commit)")


def score() -> None:
    feats, df = _load()
    panel_end = df["__time"].max()
    board = json.loads(SCOREBOARD.read_text()) if SCOREBOARD.exists() else {"scored": {}}
    for f in sorted(REG_DIR.glob("????-??-??.parquet")):      # registrations only, not *.scored_rows
        tag = f.stem
        if tag in board["scored"]:
            continue
        meta = json.loads((REG_DIR / f"{tag}.meta.json").read_text())
        if meta.get("test") and not TEST_MODE:
            print(f"  {tag}: TEST registration -- never scored on the real board"); continue
        cons = meta.get("contenders", CONTENDERS)
        reg = pd.read_parquet(f)
        if _sha256(f) != meta.get("sha256", {}).get("registration", _sha256(f)):
            raise SystemExit(f"{f.name} changed after it was saved -- refusing to score")
        for af in sorted(REG_DIR.glob(f"{tag}.add-*.parquet")):     # challengers added later
            am = json.loads(af.with_suffix(".meta.json").read_text())   # <tag>.add-<x>.meta.json
            if am.get("test") and not TEST_MODE:
                continue
            if _sha256(af) != am["sha256"]["add"]:
                raise SystemExit(f"{af.name} changed after it was saved -- refusing to score")
            add = pd.read_parquet(af)
            add["date"] = pd.to_datetime(add["date"], utc=True)
            reg["date"] = pd.to_datetime(reg["date"], utc=True)
            reg = reg.merge(add, on=["series", "date"], how="left")
            cons = cons + [c for c in am["contenders"] if c not in cons]
        last_wk = pd.to_datetime(reg["date"], utc=True).max()
        if last_wk > panel_end:
            print(f"  {tag}: horizon ends {last_wk.date()}, data ends {panel_end.date()} -- not yet scorable")
            continue
        cut = M._utc(tag)
        ev = M.build_eval_rows(df, cut, cut + pd.Timedelta(weeks=1), cut + pd.Timedelta(weeks=H))
        ev["series"] = [" | ".join(map(str, k)) for k in ev["key"]]
        ev["origin"] = tag
        reg["date"] = pd.to_datetime(reg["date"], utc=True)
        ev = ev.merge(reg[["series", "date"] + cons], on=["series", "date"], how="left")
        ev.loc[ev["is_new"], cons] = 0.0                             # unseen at the cutoff
        # Series with no saved row (e.g. history restated after the cutoff) are counted, not
        # silently lost; TODO MO_132: score them as new (0) for every contender.
        gone = ev[cons].isna().any(axis=1)
        dropped = {"rows": int(gone.sum()), "actual_units": float(ev.loc[gone, "actual"].sum()),
                   "share_of_actual": float(ev.loc[gone, "actual"].sum() / max(ev["actual"].sum(), 1e-9))}
        ev = ev[~gone]
        ex = ev[~ev["is_new"]]
        res = {"existing": M.score_levels(ex, cons), "planning_total": M.score_levels(ev, cons),
               "dropped_unsaved_series": dropped, "contenders": cons}
        q = ex.assign(_y=pd.to_datetime(ex["date"], utc=True).dt.year,
                      _m=pd.to_datetime(ex["date"], utc=True).dt.month)
        res["season_bias_by_year"] = {
            f"{name} {y}": {c: float(g[c].sum() / g["actual"].sum()) for c in cons}
            for name, mm in (("Jan-Mar", (1, 2, 3)), ("Oct-Dec", (10, 11, 12)))
            for y, g in q[q["_m"].isin(mm)].groupby("_y")}
        board["scored"][tag] = res
        E = res["existing"]
        print(f"  {tag}: scored -- cw/am/pm: " + "; ".join(
            f"{c} {E['cell x week'][c]:.1f}/{E['account x month'][c]:.1f}/{E['portfolio x month'][c]:.1f}"
            for c in cons))
        ev.drop(columns=["key"]).to_parquet(REG_DIR / f"{tag}.scored_rows.parquet")
    board["updated_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    board["n_scored"] = len(board["scored"])
    REG_DIR.mkdir(exist_ok=True)
    SCOREBOARD.write_text(json.dumps(board, indent=2, default=str))
    print(f"  scoreboard: {board['n_scored']} origin(s) scored -> {SCOREBOARD}")
    # Pooled comparisons are descriptive only; the decision rule is rewritten under MO_132.
    if board["n_scored"] >= 3:
        allrows = pd.concat([pd.read_parquet(REG_DIR / f"{t}.scored_rows.parquet") for t in board["scored"]])
        ex = allrows[~allrows["is_new"]]
        base = BASELINE if BASELINE in ex.columns and ex[BASELINE].notna().all() else "recursive"
        for y in [c for c in CONTENDERS if c != base and c in ex.columns and ex[c].notna().all()]:
            for lvl, _ in M.LEVELS_V2:
                b = M.bootstrap_diff(ex, y, base, level=lvl, n=2000)
                print(f"    {y:>11s} - {base} {lvl:<18s} {b['diff']:+.2f} CI {b['ci95']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["register", "register-add", "score"])
    ap.add_argument("--trees", type=int, default=None, help="cap for smoke tests; None = production")
    ap.add_argument("--cutoff", default=None, help="TESTS ONLY: register at a past week")
    a = ap.parse_args()
    if a.cmd == "register":
        register(a.trees, a.cutoff)
    elif a.cmd == "register-add":
        register_add()
    else:
        score()


if __name__ == "__main__":
    main()
