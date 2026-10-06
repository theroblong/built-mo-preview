#!/usr/bin/env python
"""MO_107 - can we ROUTE between methods, and is there headroom worth chasing?

Three things that need no new data, tested together because they interact.

THE SYNTHESIS. MO_83 tested hierarchical top-down allocation and rejected it:
"it ties naive pooled, but wins 10-14pp at exactly the cutoffs where the simple
methods collapse. That is a routing signal we cannot identify ex ante, so it is
not shippable today." We may now HAVE that signal. Predictability is measurable
from history alone:

  volume-weighted lag-1 autocorr of first differences  -0.011  (random walk)
  median series                                        -0.269  (mean-reverting)
  69% of series have |autocorr| > 0.2 ... but only 38% of VOLUME

For a random walk, flat carry-forward is not a weak baseline -- it is the
mathematically optimal forecast. For a mean-reverting series it is not. If we can
tell them apart BEFORE forecasting, we can use each method where it is right.

Arms (all on identical folds, all scored the same way):
  flat        carry last observed value forward
  recursive   production path, seasonal off (MO_102: zero is optimal)
  direct      one model per horizon, no lag chain
  hier        top-down: forecast the ACCOUNT aggregate, allocate by trailing share
  blend       0.5*flat + 0.5*recursive -- ensembling often beats routing, and it
              is the honest cheap control for any routing claim
  ORACLE      per series, pick the best arm in hindsight. NOT shippable. This is
              the CEILING: it says how much routing could ever be worth.
  routed      per series, pick using ONLY pre-cutoff autocorrelation. Shippable.

The oracle is the point of the run. If oracle ~= best single arm, routing cannot
help and we stop. If oracle is far better, the question becomes how much of that
gap a real signal can capture.
"""
from __future__ import annotations

import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import MO_80_quarterly_honest_backtest as M
from mo_panel import CAT_COLS, GROUP_COLS

OUT = Path("outputs/mo107_routing_and_hierarchy.json")
TREES = 1200
CUTOFFS_BACK = (13, 26, 39, 52)
H = 13
SHARE_WEEKS = 13          # trailing window for top-down share allocation
MIN_FOR_SIGNAL = 20       # weeks needed before an autocorr estimate is trusted


def predictability(hist_series) -> float:
    """lag-1 autocorrelation of FIRST DIFFERENCES, from pre-cutoff data only.

    ~0 means random walk -> flat is optimal.
    <0 means mean-reverting -> a model has something to exploit.
    """
    v = pd.to_numeric(hist_series, errors="coerce").dropna()
    if len(v) < MIN_FOR_SIGNAL:
        return np.nan
    d = v.diff().dropna()
    if len(d) < 10 or d.std() < 1e-9:
        return np.nan
    a = d.autocorr(1)
    return float(a) if np.isfinite(a) else np.nan


def hier_topdown(df, cut, fw, eval_keys):
    """Forecast the ACCOUNT x CHANNEL aggregate, allocate down by trailing share.

    Aggregation is where signal survives: item-week error runs ~50% at h=13 while
    portfolio-13wk runs ~21%. If shares are stable, top-down inherits the better
    aggregate error. Shares are computed pre-cutoff only.
    """
    hist = df[df["__time"] <= cut]
    recent = hist[hist["__time"] > cut - pd.Timedelta(weeks=SHARE_WEEKS)]
    grp_cols = ["channel_outlet", "retail_account"]
    agg_tot = recent.groupby(grp_cols, observed=True)["base_units"].sum()
    item_tot = recent.groupby(GROUP_COLS, observed=True)["base_units"].sum()

    # aggregate forecast = that aggregate's own flat level (its last 4-week mean)
    last4 = hist[hist["__time"] > cut - pd.Timedelta(weeks=4)]
    agg_level = last4.groupby(grp_cols, observed=True)["base_units"].sum() / 4.0

    out = {}
    for key in eval_keys:
        g = (key[1], key[2])                     # channel, account
        tot = float(agg_tot.get(g, 0.0))
        if tot <= 0:
            continue
        share = float(item_tot.get(key, 0.0)) / tot
        lvl = float(agg_level.get(g, 0.0)) * share
        for fd in fw:
            out[(key, fd)] = max(0.0, lvl)
    return out


def score_by_series(truth, pred):
    per = {}
    for (key, t), a in truth.items():
        p = pred.get((key, t))
        if p is None:
            continue
        r = per.setdefault(key, {"ae": 0.0, "den": 0.0})
        r["ae"] += abs(a - p); r["den"] += abs(a)
    return per


def wmape_of(per, keys=None):
    rows = [r for k, r in per.items() if (keys is None or k in keys) and r["den"] > 0]
    if not rows:
        return float("nan")
    return float(sum(r["ae"] for r in rows) / sum(r["den"] for r in rows) * 100)


def main() -> None:
    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    df = M.load_panel(feats)
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(df["__time"])), utc=True))
    end = df["__time"].max()
    cuts = [end - pd.Timedelta(weeks=w) for w in CUTOFFS_BACK]

    print("MO_107 - routing, hierarchy, and the oracle ceiling")
    print(f"  {len(df):,} rows - folds {[str(c.date()) for c in cuts]}\n")

    fold_rows = []
    for cut in cuts:
        fw = M.future_weeks(weeks, cut, H)
        qs, qe = fw[0], fw[-1]
        act = df[(df["__time"] >= qs) & (df["__time"] <= qe)]
        truth = {((u, c, a, g), t): float(v) for (u, c, a, g, t), v in
                 act.groupby(GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        hist = df[df["__time"] <= cut]

        # pre-cutoff predictability signal, per series
        sig = {}
        for key, g in hist.groupby(GROUP_COLS, observed=True):
            if key in ek:
                sig[key] = predictability(g.sort_values("__time")["base_units"])

        preds = {}
        flat = {}
        for key, g in hist.groupby(GROUP_COLS, observed=True):
            if key not in ek:
                continue
            v = pd.to_numeric(g.sort_values("__time")["base_units"], errors="coerce").fillna(0)
            if len(v):
                for fd in fw:
                    flat[(key, fd)] = float(v.iloc[-1])
        preds["flat"] = flat
        rec = M.run_production(df, feats, cut, qs, qe, ek, TREES, fw, {})
        preds["recursive"] = {k: (v["q50"] if isinstance(v, dict) else v) for k, v in rec.items()}
        anchors = hist.groupby(GROUP_COLS, observed=True).tail(1)
        preds["direct"] = M.run_direct(df, feats, cut, qs, qe, anchors, TREES, fw)
        preds["hier"] = hier_topdown(df, cut, fw, ek)
        preds["blend"] = {k: 0.5 * v + 0.5 * preds["recursive"].get(k, v)
                          for k, v in flat.items() if k in preds["recursive"]}

        per = {name: score_by_series(truth, p) for name, p in preds.items()}
        fold_rows.append({"cut": str(cut.date()), "per": per, "sig": sig,
                          "keys": set(ek)})
        print(f"  fold {str(cut.date())} done - {len(ek):,} series")

    arms = ["flat", "recursive", "direct", "hier", "blend"]
    print(f"\n  {'arm':<12s} {'wMAPE':>8s}   per-fold")
    results = {}
    for a in arms:
        vals = [wmape_of(f["per"].get(a, {})) for f in fold_rows]
        results[a] = float(np.nanmean(vals))
        print(f"  {a:<12s} {np.nanmean(vals):>8.2f}   " + " ".join(f"{v:5.1f}" for v in vals))

    # ---- ORACLE: best arm per series, in hindsight. The ceiling. ----
    orc_vals, route_vals, cover = [], [], []
    for f in fold_rows:
        ae = den = 0.0
        for key in f["keys"]:
            best = None
            for a in arms:
                r = f["per"].get(a, {}).get(key)
                if r and r["den"] > 0 and (best is None or r["ae"] < best["ae"]):
                    best = r
            if best:
                ae += best["ae"]; den += best["den"]
        orc_vals.append(ae / den * 100 if den else np.nan)
    print(f"\n  {'ORACLE':<12s} {np.nanmean(orc_vals):>8.2f}   "
          + " ".join(f"{v:5.1f}" for v in orc_vals) + "   <- ceiling, NOT shippable")
    results["ORACLE"] = float(np.nanmean(orc_vals))

    best_single = min(results[a] for a in arms)
    gap = best_single - results["ORACLE"]
    print(f"\n  best single arm {best_single:.2f} | oracle {results['ORACLE']:.2f} "
          f"| headroom {gap:.2f}pp")
    if gap < 1.0:
        print("  -> routing CANNOT help: the arms agree on which series are hard. Stop here.")
    else:
        print(f"  -> {gap:.2f}pp of headroom exists IF a real signal can find it.")

    # ---- REALISTIC routing on pre-cutoff autocorrelation ----
    print(f"\n  Routing on pre-cutoff autocorrelation (flat if ~random walk, else model):")
    print(f"  {'threshold':>10s} {'wMAPE':>8s} {'% routed to flat':>18s}")
    for thr in (-0.40, -0.30, -0.20, -0.10, 0.0):
        vals, shares = [], []
        for f in fold_rows:
            ae = den = n_flat = n_tot = 0.0
            for key in f["keys"]:
                s = f["sig"].get(key, np.nan)
                # more negative = more mean-reverting = model should help
                use = "recursive" if (np.isfinite(s) and s < thr) else "flat"
                r = f["per"].get(use, {}).get(key)
                if r and r["den"] > 0:
                    ae += r["ae"]; den += r["den"]
                    n_tot += 1; n_flat += (use == "flat")
            vals.append(ae / den * 100 if den else np.nan)
            shares.append(n_flat / n_tot if n_tot else np.nan)
        print(f"  {thr:>10.2f} {np.nanmean(vals):>8.2f} {np.nanmean(shares):>17.0%}")
        results[f"routed@{thr}"] = float(np.nanmean(vals))

    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
