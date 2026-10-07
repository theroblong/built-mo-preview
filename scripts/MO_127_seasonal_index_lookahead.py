#!/usr/bin/env python
"""MO_127 - Is the forecasts' seasonal advantage real, or did the seasonal index see the future?

WHERE THIS CAME FROM
--------------------
Skeptic check of 2026-10-07 (live notes in agents/project_memory.md). The MO_59 seasonal
index (outputs/mo59_seasonal_index.csv) was built ONCE, on 2026-10-01, from every series
with 104+ weeks in the full panel, and every backtest loads it once and applies it at every
historical cutoff. The flat baseline gets no seasonal adjustment at all.

Step 1 of this plan (read-only count, same series rule as MO_59) showed the panel starts
2023-10-15, so ZERO series have 104 weeks of pre-cutoff history at the four 2025 cutoffs,
and 160 / 206 / 265 at the three 2026 cutoffs (about 28% of trailing volume). At the 2025
cutoffs no honest STL index could have existed. The look-ahead there is certain; the only
question is how much it is worth.

It matters because the headline v12 candidate's edge at the planning level is entirely
seasonal: conn_L4W 10.71 vs conn_L4W_noseas 16.42 vs flat 16.0 at portfolio x month
(MO_125, README 226).

PRIOR WORK (docs/SETTLED_FINDINGS.md, DRAFT 2026-10-07)
-------------------------------------------------------
  MO_125  conn_L4W beats flat and the model at all 3 levels. PROVISIONAL (pm n=21).
          Reopen-if met: its seasonal input is now in question.
  MO_126  route the anchor by history band. PROVISIONAL. Re-scored here, by band,
          with honest seasonal inputs.
  MO_113  anchor seasonal mode best under the corrected harness (40.08 vs 41.25).
          PROVISIONAL. That gain was measured with the full-panel index.
  README 223 (MO_122)  model beats flat at portfolio x month. PROVISIONAL, and the
          2026-10-07 skeptic check proposes NOT SETTLED. Same index.
  MO_59 / MO_59b / MO_59c  FACT: volume-weighted index over all qualifying series; YoY
          shape barely repeats (median r = +0.079); no series had 104+ weeks at the
          Q4 2025 cutoff. Step 1 extends that to all four 2025 cutoffs.
  Method rules (SETTLED): all 3 levels, history-band breakout, harness parity at import.

ARMS. Every arm is scored on the same cell-weeks. The index variants are:
  full = the current full-panel MO_59 index (what every backtest so far used)
  pre  = MO_59's own compute_seasonal_index, run only on data <= the cutoff (104w STL rule).
         At the 2025 cutoffs no series qualifies, so pre = no seasonal. This is the honest
         "as it would have been" input, across all 7 quarters.
  off  = no seasonal factor
Arms:
  model_step_full    REFERENCE: the shipped config (MO_27 step-over-step) as backtested so far
  model_step_pre     the shipped config with an honest index
  model_off          the model with no seasonal factor (the YAGO blend still runs)
  model_anchor_full  README 223 / MO_125 candidate arm, as previously scored
  model_anchor_pre   the same with an honest index
  conn_L4W_{full,pre,off}  trailing 4-wk Base U/S/W x current doors x anchor-relative seasonal
  flat_{full,pre,off}      last actual week x anchor-relative seasonal (flat_off = MO_122 flat)

LEVELS: cell x week, account x month, portfolio x month, plus bias at portfolio x month.
Each is broken out by history band (<13 / 13-25 / 26-51 / 52+ wks) and by quarter. Windows:
ALL 7 quarters (honest arms) and 2026 ONLY (the 3 quarters where an honest index exists:
the primary seasonal comparison). Separate view: BUILT PUFF / SOUR PUFF series with 104+
weeks of history at the cutoff (Jason, 2026-10-07).

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1  2026 quarters, portfolio x month: conn_L4W_pre is worse than conn_L4W_full by >= 2pp.
      If it FAILS, the look-ahead is not material where an honest index exists.
  P2  ALL 7 quarters, portfolio x month: conn_L4W_pre is within 1.5pp of flat_off (the
      velocity method's planning-level edge over flat mostly disappears). If it FAILS
      because conn_L4W_pre still beats flat_off by more, the edge is real without the leak.
  P3  Cell x week, all 7 quarters: |pre - full| < 1pp for conn_L4W and model_step (the
      index matters little at item-week). If it FAILS, seasonality matters at item level too.
  P4  ALL 7 quarters, portfolio x month: flat_full beats flat_off by > 2pp, and flat_pre
      gains less than half of that. If it FAILS, the full index was not handing every method
      a free gain.
  P5  2026 quarters, portfolio x month: model_step_pre is within 1pp of model_step_full,
      because the index only reaches short / no-lag52 series (the YAGO blend dominates). If
      it FAILS, the shipped forecast itself leans on the leaked index.
  P6  PUFF 104+ wk view, cell x week: conn_L4W_pre beats model_step_pre (MO_126's 52+ band
      result carries to long-history PUFF). If it FAILS, MO_126's 52+ result does not
      transfer.
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

warnings.filterwarnings("ignore")

OUT = Path("outputs/mo127_seasonal_lookahead.json")
OUT_IDX = Path("outputs/mo127_pre_cutoff_index.csv")
TREES = None                      # None = production cap (MO_80.TREES_CAP); was 800 in the original run
TDP_FLOOR = 0.05
PUFF_BRANDS = {"BUILT PUFF", "BUILT SOUR PUFF"}
PUFF_MIN_WKS = 104
YEARS_2026 = {"Q1 2026", "Q2 2026", "Q3 2026"}

BANDS = [(0, 13, "<13 wks"), (13, 26, "13-25 wks"), (26, 52, "26-51 wks"), (52, 10_000, "52+ wks")]

ARMS = ["model_step_full", "model_step_pre", "model_off",
        "model_anchor_full", "model_anchor_pre",
        "conn_L4W_full", "conn_L4W_pre", "conn_L4W_off",
        "flat_full", "flat_pre", "flat_off"]


def band_of(n: int) -> str:
    for lo, hi, lbl in BANDS:
        if lo <= n < hi:
            return lbl
    return BANDS[-1][2]


def velocity(bu, td, w=4):
    b = np.asarray(bu[-w:], float); t = np.asarray(td[-w:], float)
    ok = np.isfinite(b) & np.isfinite(t)
    if not ok.any():
        return np.nan
    st = t[ok].sum()
    return float(b[ok].sum() / st) if st > TDP_FLOOR else np.nan


def anchor_mult(idx: dict, fd, cut) -> float:
    """Anchor-relative one-shot level factor, as MO_125 applied it to conn_L4W."""
    if not idx:
        return 1.0
    tgt = 1.0 + idx.get(int(pd.Timestamp(fd).isocalendar().week), 0.0)
    ref = 1.0 + idx.get(int(pd.Timestamp(cut).isocalendar().week), 0.0)
    return max(0.1, tgt / ref) if ref > 0 else max(0.1, tgt)


# ── the pre-cutoff index: MO_59's own code, run on data <= cutoff ─────────────
def build_pre_index(S, raw: pd.DataFrame, cut) -> tuple[dict, int]:
    sub = raw if cut is None else raw[raw["__time"] <= cut]
    n_rows = sub.groupby(["retail_account", "upc"]).size()        # MO_59 main(): row count
    pairs = sub[["retail_account", "upc", "description"]].drop_duplicates()
    ok = n_rows[n_rows >= S.MIN_WEEKS].index
    qual = [tuple(r) for r in pairs.itertuples(index=False)
            if (r.retail_account, r.upc) in ok]
    if not qual:
        return {}, 0
    try:
        idx_df, n_fit = S.compute_seasonal_index(sub, qual, weighted=True, return_n=True)
    except ValueError:                                            # nothing survived STL
        return {}, 0
    return dict(zip(idx_df["week_of_year"].astype(int),
                    idx_df["seasonal_index"].astype(float))), n_fit


# ── train once per cutoff; the index only post-processes predictions ────────
_FIT_CACHE: dict = {}


def patch_fit(M) -> None:
    # Wraps the harness's production-equivalent trainer (MO_80 train_like_production,
    # 2026-10-07). The original MO_127 run used the legacy M.fit (800-tree cap).
    orig = M.train_like_production

    def cached(tr, feats, target, trees=None, alpha=0.5, time_col="__time"):
        k = (len(tr), round(float(pd.to_numeric(tr[target], errors="coerce").sum()), 6),
             str(tr[time_col].max()), trees, alpha, target, time_col, tuple(feats))
        if k not in _FIT_CACHE:
            _FIT_CACHE[k] = orig(tr, feats, target, trees, alpha=alpha, time_col=time_col)
        return _FIT_CACHE[k]
    M.train_like_production = cached


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=TREES)
    ap.add_argument("--quarters", default="", help="comma list, e.g. 'Q1 2026,Q2 2026'")
    a = ap.parse_args()

    import MO_59_stl_changepoints as S
    import MO_80_quarterly_honest_backtest as M

    def load(mode):
        os.environ["MO_SEASONAL_MODE"] = mode
        importlib.reload(M)
        assert M.SEASONAL_MODE == mode and M.FEATURE_REFRESH == "freeze", \
            "harness must match MO_27"
        patch_fit(M)
        return M

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    load("step")
    df = M.load_panel(feats)
    df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
    df["_brand"] = df["source_brand"].astype(str)
    full_idx = M.load_seasonal_index()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]
    if a.quarters:
        want = {s.strip() for s in a.quarters.split(",")}
        quarters = [q for q in quarters if q[0] in want]
    GC = M.GROUP_COLS
    ai = GC.index("retail_account")

    print("MO_127 - is the seasonal advantage real, or did the index see the future?")
    print("  reference = model_step_full (shipped step-over-step config, full-panel index)\n")

    # Validity check: MO_59's code on the whole panel must reproduce the committed CSV,
    # or "pre" differs from "full" for a reason other than the cutoff.
    raw = S.load_data()
    rebuilt, n_full = build_pre_index(S, raw, None)
    common = sorted(set(rebuilt) & set(full_idx))
    gap = max(abs(rebuilt[w] - full_idx[w]) for w in common) if common else float("nan")
    print(f"  index rebuild check: {n_full} series, max |rebuilt - committed CSV| = {gap:.4f}")
    if not np.isfinite(gap) or gap > 0.02:
        print("  ⚠️ BLOCKER: rebuilt full-panel index does not reproduce the CSV; "
              "pre vs full would confound the cutoff with a code/panel difference.")

    pre_rows, recs = [], []
    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        if act.empty:
            continue
        pre_idx, n_pre = build_pre_index(S, raw, cut)
        corr = (np.corrcoef([pre_idx[w] for w in common if w in pre_idx],
                            [full_idx[w] for w in common if w in pre_idx])[0, 1]
                if pre_idx else float("nan"))
        print(f"  {ql}: cutoff {qc}, pre-cutoff index from {n_pre} series"
              + (f" (r vs full {corr:+.2f})" if pre_idx else " -> none possible, pre = off"))
        for w, v in sorted(pre_idx.items()):
            pre_rows.append({"quarter": ql, "cutoff": qc, "week_of_year": w,
                             "seasonal_index": v, "n_series": n_pre})

        truth = {(k[:-1], k[-1]): float(v) for k, v in
                 act.groupby(GC + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        tr = df[df["__time"] <= cut]

        def run(mode, idx):
            load(mode)
            return M.run_production(df, feats, cut, qs, qe, ek, a.trees, fw, idx)

        p = {"model_step_full": run("step", full_idx), "model_off": run("step", {})}
        p["model_step_pre"] = run("step", pre_idx) if pre_idx else p["model_off"]
        p["model_anchor_full"] = run("anchor", full_idx)
        p["model_anchor_pre"] = run("anchor", pre_idx) if pre_idx else p["model_off"]
        idxs = {"full": full_idx, "pre": pre_idx, "off": {}}

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
            v4 = velocity(bu, td)
            last = float(bu[-1])
            base_v = v4 * float(td[-1]) if np.isfinite(v4) else last
            for fd in fw[:M.HORIZON]:
                if not (qs <= fd <= qe) or (key, fd) not in truth:
                    continue
                if any(p[m].get((key, fd)) is None for m in p):
                    continue
                row = {"quarter": ql, "date": fd, "account": key[ai],
                       "band": band_of(n_hist), "hist_wks": n_hist,
                       "puff_long": brand in PUFF_BRANDS and n_hist >= PUFF_MIN_WKS,
                       "actual": truth[(key, fd)]}
                row.update({m: p[m][(key, fd)] for m in p})
                for tag, idx in idxs.items():
                    mult = anchor_mult(idx, fd, cut)
                    row[f"conn_L4W_{tag}"] = max(0.0, base_v * mult)
                    row[f"flat_{tag}"] = max(0.0, last * mult)
                recs.append(row)

    r = pd.DataFrame(recs)
    if r.empty:
        print("no rows"); return
    r["month"] = pd.to_datetime(r["date"]).dt.to_period("M").astype(str)
    pd.DataFrame(pre_rows).to_csv(OUT_IDX, index=False)
    print(f"\n  scored {len(r):,} cell-weeks  (2026 quarters: "
          f"{r['quarter'].isin(YEARS_2026).sum():,}; PUFF 104+ wk: {r['puff_long'].sum():,})\n")

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
            t = {arm: wmape(g, arm) for arm in ARMS}
            out[lbl] = {**t, "n": len(g)}
            # BY HISTORY BAND: a band's month totals are built from that band's cells only
            out[lbl]["by_band"] = {}
            for _, _, b in BANDS:
                sb = sub[sub["band"] == b]
                if sb.empty:
                    continue
                gb = sb if keys is None else sb.groupby(keys, as_index=False)[["actual"] + ARMS].sum()
                out[lbl]["by_band"][b] = {**{arm: wmape(gb, arm) for arm in ARMS}, "n": len(gb)}
        pm = sub.groupby("month", as_index=False)[["actual"] + ARMS].sum()
        out["portfolio_bias"] = {arm: float(pm[arm].sum() / pm["actual"].sum()) for arm in ARMS}
        out["by_quarter_pm"] = {}
        for q, sq in sub.groupby("quarter"):
            gq = sq.groupby("month", as_index=False)[["actual"] + ARMS].sum()
            out["by_quarter_pm"][q] = {arm: wmape(gq, arm) for arm in ARMS}

        hdr = f"  {'arm':<19s}" + "".join(f"{l.split(' x ')[0][:9]:>11s}" for l, _ in LEVELS) + "   bias"
        print(hdr)
        for arm in ARMS:
            print(f"  {arm:<19s}" + "".join(f"{out[l][arm]:>11.2f}" for l, _ in LEVELS)
                  + f"  {out['portfolio_bias'][arm]:>5.3f}")
        print(f"  (n: " + ", ".join(f"{l} {out[l]['n']:,}" for l, _ in LEVELS) + ")")
        for lbl, _ in LEVELS:
            print(f"  BY HISTORY BAND, {lbl}")
            for b, v in out[lbl]["by_band"].items():
                print(f"    {b:<10s} n={v['n']:>6,}  " + "  ".join(
                    f"{arm.replace('model_', 'm_').replace('conn_L4W', 'conn')}={v[arm]:.1f}"
                    for arm in ("model_step_full", "model_step_pre", "conn_L4W_full",
                                "conn_L4W_pre", "flat_off", "flat_pre")))
        print("  BY QUARTER, portfolio x month")
        for q, v in out["by_quarter_pm"].items():
            print(f"    {q:<8s} " + "  ".join(
                f"{arm.replace('model_', 'm_').replace('conn_L4W', 'conn')}={v[arm]:.1f}"
                for arm in ("model_step_full", "model_step_pre", "conn_L4W_full",
                            "conn_L4W_pre", "flat_off")))
        print()
        return out

    res = {"index_rebuild_gap": gap, "n_series_full_index": n_full,
           "all_7": table(r, "ALL QUARTERS (honest arms = *_pre)"),
           "q2026": table(r[r["quarter"].isin(YEARS_2026)],
                          "2026 QUARTERS ONLY (primary seasonal comparison)")}
    pl = r[r["puff_long"]]
    if not pl.empty:
        res["puff_104"] = table(pl, f"PUFF / SOUR PUFF with {PUFF_MIN_WKS}+ wks of history")

    # ── close the loop ─────────────────────────────────────────────────────
    A, Q = res["all_7"], res["q2026"]
    PM, CW = "portfolio x month", "cell x week"
    checks = []
    d1 = Q[PM]["conn_L4W_pre"] - Q[PM]["conn_L4W_full"]
    checks.append(("P1", d1 >= 2.0, f"2026 pm conn pre-full = {d1:+.2f}pp (pred >= +2)"))
    d2 = A[PM]["conn_L4W_pre"] - A[PM]["flat_off"]
    checks.append(("P2", abs(d2) <= 1.5 or d2 > 0,
                   f"all pm conn_pre - flat_off = {d2:+.2f}pp (pred within 1.5 or worse)"))
    d3c = abs(A[CW]["conn_L4W_pre"] - A[CW]["conn_L4W_full"])
    d3m = abs(A[CW]["model_step_pre"] - A[CW]["model_step_full"])
    checks.append(("P3", d3c < 1 and d3m < 1, f"cw |pre-full| conn {d3c:.2f}, model {d3m:.2f} (pred < 1)"))
    g_full = A[PM]["flat_off"] - A[PM]["flat_full"]
    g_pre = A[PM]["flat_off"] - A[PM]["flat_pre"]
    checks.append(("P4", g_full > 2 and g_pre < g_full / 2,
                   f"all pm flat gain: full {g_full:+.2f}, pre {g_pre:+.2f} (pred full > 2, pre < half)"))
    d5 = abs(Q[PM]["model_step_pre"] - Q[PM]["model_step_full"])
    checks.append(("P5", d5 < 1, f"2026 pm |model_step pre-full| = {d5:.2f} (pred < 1)"))
    if "puff_104" in res:
        P = res["puff_104"][CW]
        checks.append(("P6", P["conn_L4W_pre"] < P["model_step_pre"],
                       f"PUFF cw conn_pre {P['conn_L4W_pre']:.2f} vs model_step_pre "
                       f"{P['model_step_pre']:.2f} (pred conn lower)"))
    else:
        checks.append(("P6", None, "no PUFF 104+ wk rows -- cannot test"))
    print("PREDICTIONS")
    res["predictions"] = {}
    for pid, ok, msg in checks:
        tag = "UNTESTABLE" if ok is None else ("HOLDS" if ok else "FAILS")
        res["predictions"][pid] = {"result": tag, "detail": msg}
        print(f"  {pid} {tag:<10s} {msg}")

    # Unexplained behavior is a blocker, not a footnote.
    for b, v in A[CW]["by_band"].items():
        if b == "52+ wks" and v["model_step_pre"] > v["flat_off"]:
            print(f"  ⚠️ BLOCKER still open: model worse than flat on 52+ wk series at cell x week "
                  f"({v['model_step_pre']:.1f} vs {v['flat_off']:.1f}), honest index")

    OUT.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {OUT} and {OUT_IDX}")


if __name__ == "__main__":
    main()
