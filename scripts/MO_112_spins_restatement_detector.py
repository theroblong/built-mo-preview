#!/usr/bin/env python
"""MO_112 - does SPINS restate history, and by how much?

This is the right-sized version of the "Evidently AI" suggestion. Evidently is a
drift-monitoring library; the drift we actually have a documented exposure to is
not consumer behaviour, it is SPINS REWRITING WEEKS WE HAVE ALREADY TRAINED AND
BACKTESTED ON. That is a leakage risk with a specific shape:

  - a backtest cut at 2025-12-28 trains on the version of history we hold TODAY
  - but the version that existed ON 2025-12-28 may have been different
  - so every "honest" holdout is honest about the CUTOFF and silent about the
    REVISION, and the model is quietly scored with information from the future

Nobody has measured it, so nobody knows whether it is a rounding artifact or a
material fraction of our reported accuracy. This script measures it, with no new
dependency: two panel snapshots are already on disk one day apart, and git holds
older ones.

  outputs/retailer_sales_weekly.parquet          2026-09-30 (stale git copy)
  scripts/outputs/retailer_sales_weekly.parquet  2026-10-01 (LIVE)

(See feedback_pipeline_artifact_paths: scripts/outputs/ is live, root is the
stale committed copy. That staleness is the asset here.)

What counts as what:
  NEW WEEKS    keys present only in the newer snapshot and dated after the older
               snapshot's last week. Normal weekly growth, not a restatement.
  ARRIVALS     keys only in the newer snapshot but dated INSIDE the shared window.
               A cell that was absent and is now present -- backfill.
  DISAPPEARED  keys only in the older snapshot inside the shared window.
  RESTATED     keys in BOTH, inside the shared window, with a changed value. This
               is the number that matters.

Reported as a share of volume, not of rows, because a 0.01% row change on the
largest cells is worse than a 5% row change on the tail.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from mo_panel import GROUP_COLS

# Default pair is the two copies already on disk. Pass two paths to compare any
# other pair -- git holds genuinely different SPINS VINTAGES, which is the only way
# to test revision rather than pipeline determinism:
#   git show <sha>:outputs/retailer_sales_weekly.parquet > /tmp/panel_<sha>.parquet
import sys
_a = [x for x in sys.argv[1:] if not x.startswith("-")]
OLD = Path(_a[0]) if len(_a) > 1 else Path("../outputs/retailer_sales_weekly.parquet")
NEW = Path(_a[1]) if len(_a) > 1 else Path("outputs/retailer_sales_weekly.parquet")
_tag = f"_{OLD.stem}__{NEW.stem}" if len(_a) > 1 else ""
OUT = Path(f"outputs/mo112_spins_restatement{_tag}.json")

# Columns worth checking for revision. base_units is the model target, so it is the
# one that can move an accuracy number; the others move derived features.
MEASURES = ["base_units", "units", "units_promo", "dollars", "tdp", "total_units"]
TOL = 1e-6          # float round-trip through parquet, not a restatement
MATERIAL = 0.01     # a cell is "changed" if it moves more than 1%, OR more than ATOL units
ATOL = 1.0


def load(p: Path, cols: list[str]) -> pd.DataFrame:
    df = pd.read_parquet(p, columns=cols)
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    for c in cols:
        if c not in GROUP_COLS + ["__time"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # Deliberately NO mo_panel filtering. The question is whether the SOURCE moved,
    # and a filter that drops a row would hide a restatement inside it.
    return df


def main() -> None:
    o_cols = set(pd.read_parquet(OLD).head(0).columns)
    n_cols = set(pd.read_parquet(NEW).head(0).columns)
    measures = [m for m in MEASURES if m in o_cols and m in n_cols]
    keys = GROUP_COLS + ["__time"]
    cols = keys + measures

    old = load(OLD, cols)
    new = load(NEW, cols)

    print("MO_112 - SPINS restatement detector\n")
    print(f"  OLD {OLD}  {len(old):>9,} rows  through {old['__time'].max().date()}")
    print(f"  NEW {NEW}  {len(new):>9,} rows  through {new['__time'].max().date()}")
    print(f"  measures compared: {', '.join(measures)}")
    print(f"  schema: {len(o_cols)} -> {len(n_cols)} columns"
          + (f"  ADDED {sorted(n_cols - o_cols)}" if n_cols - o_cols else "")
          + (f"  REMOVED {sorted(o_cols - n_cols)}" if o_cols - n_cols else ""))

    shared_end = min(old["__time"].max(), new["__time"].max())
    print(f"  shared window ends {shared_end.date()} — "
          f"everything after it is new data, not a revision\n")

    m = old.merge(new, on=keys, how="outer", suffixes=("_o", "_n"), indicator=True)
    inside = m["__time"] <= shared_end

    new_weeks = m[(m["_merge"] == "right_only") & (m["__time"] > shared_end)]
    arrivals = m[(m["_merge"] == "right_only") & inside]
    gone = m[(m["_merge"] == "left_only") & inside]
    both = m[(m["_merge"] == "both") & inside]

    res = {"old": str(OLD), "new": str(NEW),
           "old_rows": len(old), "new_rows": len(new),
           "shared_window_end": str(shared_end.date()),
           "schema_added": sorted(n_cols - o_cols),
           "schema_removed": sorted(o_cols - n_cols),
           "counts": {"new_weeks": len(new_weeks), "arrivals_inside": len(arrivals),
                      "disappeared_inside": len(gone), "matched_inside": len(both)},
           "measures": {}}

    print(f"  {'bucket':<26s} {'rows':>9s} {'base_units':>14s}")
    for lbl, sub, col in (("new weeks (after window)", new_weeks, "base_units_n"),
                          ("arrivals INSIDE window", arrivals, "base_units_n"),
                          ("disappeared INSIDE window", gone, "base_units_o"),
                          ("matched INSIDE window", both, "base_units_n")):
        v = float(pd.to_numeric(sub[col], errors="coerce").fillna(0).sum()) if len(sub) else 0.0
        print(f"  {lbl:<26s} {len(sub):>9,} {v:>14,.0f}")

    print(f"\n  RESTATEMENTS among matched rows inside the shared window:\n")
    print(f"  {'measure':<13s} {'rows chgd':>10s} {'% rows':>7s} "
          f"{'vol chgd':>13s} {'% of vol':>9s} {'net drift':>12s} {'% net':>7s} {'max |%|':>9s}")
    for meas in measures:
        a = pd.to_numeric(both[f"{meas}_o"], errors="coerce")
        b = pd.to_numeric(both[f"{meas}_n"], errors="coerce")
        ok = a.notna() & b.notna()
        a, b = a[ok], b[ok]
        if not len(a):
            continue
        d = b - a
        rel = np.where(np.abs(a) > TOL, np.abs(d) / np.abs(a).clip(lower=TOL), np.inf)
        chg = (np.abs(d) > ATOL) & (rel > MATERIAL)
        denom = float(np.abs(a).sum()) or 1.0
        row = {"rows_changed": int(chg.sum()), "rows_total": int(len(a)),
               "pct_rows": float(chg.sum() / len(a) * 100),
               "volume_changed": float(np.abs(a[chg]).sum()),
               "pct_of_volume": float(np.abs(a[chg]).sum() / denom * 100),
               "net_drift": float(d.sum()), "pct_net": float(d.sum() / denom * 100),
               "max_abs_pct": float(np.nanmax(rel[np.isfinite(rel)]) * 100) if np.isfinite(rel).any() else float("nan")}
        res["measures"][meas] = row
        print(f"  {meas:<13s} {row['rows_changed']:>10,} {row['pct_rows']:>6.2f}% "
              f"{row['volume_changed']:>13,.0f} {row['pct_of_volume']:>8.2f}% "
              f"{row['net_drift']:>12,.0f} {row['pct_net']:>6.2f}% {row['max_abs_pct']:>8.1f}%")

    # How far back do revisions reach? A restatement confined to the last 2-3 weeks is
    # a normal reporting lag and harmless to a backtest cut months earlier. One that
    # reaches back a year contaminates every fold.
    a = pd.to_numeric(both["base_units_o"], errors="coerce")
    b = pd.to_numeric(both["base_units_n"], errors="coerce")
    ok = a.notna() & b.notna()
    d = (b - a)[ok]
    rel = np.where(np.abs(a[ok]) > TOL, np.abs(d) / np.abs(a[ok]).clip(lower=TOL), np.inf)
    chg = (np.abs(d) > ATOL) & (rel > MATERIAL)
    sub = both[ok][chg]
    if len(sub):
        age = ((shared_end - sub["__time"]).dt.days / 7).round().astype(int)
        print(f"\n  How far back base_units revisions reach "
              f"(weeks before {shared_end.date()}):")
        hist = age.value_counts().sort_index()
        vol = pd.to_numeric(sub["base_units_o"], errors="coerce").abs().groupby(age).sum()
        for wk in hist.index[:20]:
            print(f"    {wk:>3d} wks back  {hist[wk]:>7,} rows  "
                  f"{vol.get(wk, 0):>12,.0f} units")
        if len(hist) > 20:
            print(f"    ... {len(hist) - 20} more lags, deepest {int(age.max())} weeks back")
        res["deepest_revision_weeks"] = int(age.max())
        res["revision_age_rows"] = {int(k): int(v) for k, v in hist.items()}
    else:
        res["deepest_revision_weeks"] = 0
        print("\n  No material base_units revisions inside the shared window.")

    bu = res["measures"].get("base_units", {})
    pv = bu.get("pct_of_volume", 0.0)
    deep = res.get("deepest_revision_weeks", 0)
    print("\n  VERDICT")
    if pv < 0.1:
        print(f"    base_units restatement touches {pv:.3f}% of volume — immaterial. "
              "Backtest leakage from revisions can be closed as a risk.")
    elif deep <= 4:
        print(f"    {pv:.2f}% of volume restated but only within {deep} weeks of the "
              "panel edge — a reporting lag. Backtests cut >1 month back are unaffected;\n"
              "    the exposure is the FORWARD anchor, not the folds.")
    else:
        print(f"    MATERIAL: {pv:.2f}% of volume restated, reaching {deep} weeks back. "
              "Every honest fold is scored against revised history.\n"
              "    Fix: snapshot the panel at each ingest and backtest against the "
              "AS-OF version, or accept and state the bias.")

    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
