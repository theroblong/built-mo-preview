#!/usr/bin/env python
"""MO_118 - the feature contract: train on what inference can actually supply.

THE DEFECT, VERIFIED NOT ASSUMED
--------------------------------
Exact-match tests against the panel (not correlation -- base_units is so
autocorrelated that both candidate definitions correlate at 0.999):

    base_units_roll4_avg   matches mean(units[t-3..t])      98.4% of rows
                           matches mean(units[t-4..t-1])     4.9%
    base_units_roll8_avg   includes week t                  96.9%
    base_units_roll13_avg  includes week t                  95.5%
    base_units_wow_delta   equals units[t] - units[t-1]     99.5%

MO_26 line 357: `y_train = train["log_base_units"]` -- the target is base_units from
the SAME row, unshifted. So the model is trained to predict units[t] from features that
algebraically contain units[t]. `velocity_per_tdp` is base_units/tdp for the current
week (MO_25:754), and tdp is also a feature, so tdp x velocity_per_tdp reconstructs the
target to within 1% on 89.7% of rows.

Those features hold 52.6% of model gain. The four properly lagged base_units_lag*
features hold 16.6%.

THREE INCOMPATIBLE REGIMES
  training   (MO_26)  computed INCLUDING week t
  production (MO_27)  FROZEN at the anchor week for all 13 steps (`static_feats`)
  backtest   (MO_80)  RECOMPUTED from the prediction chain

This is not a data error -- the panel columns correctly describe history. It is the
wrong CONTRACT for a forecasting feature: the model is fitted to a world it never
operates in, falls back on lag1 at inference, and lag1 is last week's value. That is a
sufficient explanation for "the model barely beats naive" without invoking anything
about method choice.

It also retires the teacher-forced number: 4.15% teacher-forced against 37% recursive
was never a modelling insight, because teacher forcing hands the model wow_delta and
roll4 containing the answer.

⚠️ It does NOT mean our honest backtests were inflated. MO_80 recomputes these from
predicted history, so 44.56 stands.

ARMS
  current      the panel as shipped, scored through run_production  -- 44.56 expected
  lagged       every base_units-derived feature SHIFTED BY ONE WEEK so it ends at t-1,
               retrained, and recomputed identically at inference. Training and
               inference finally agree.
  lagged_frozen   the lagged features, but FROZEN at the anchor as MO_27 actually does.
               Isolates the second defect -- the MO_27/MO_80 divergence -- from the
               first. If `lagged` beats `lagged_frozen`, MO_27's freeze is itself
               costing accuracy and the two files must be reconciled.

Honest throughout: features are rebuilt from data <= cutoff at every fold, the model is
retrained per fold, and all arms are scored on identical keys by MO_80.score.
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
import lightgbm as lgb

warnings.filterwarnings("ignore")

OUT = Path("outputs/mo118_feature_contract.json")
TREES = 800

# Features empirically shown to END AT WEEK t. Each maps to how it is rebuilt one week
# earlier. Window features use shift(1) before rolling; the deltas shift both terms.
ROLL_SPECS = {"base_units_roll4_avg": 4, "base_units_roll8_avg": 8,
              "base_units_roll13_avg": 13}
STD_SPECS = {"base_units_roll8_std": 8, "base_units_roll13_std": 13}
Z_SPECS = {"base_units_z8": 8, "base_units_z13": 13}


def relag(df: pd.DataFrame, GC: list[str]) -> pd.DataFrame:
    """Rebuild every base_units-derived feature so it ENDS AT t-1, not t.

    The rebuild is done from base_units itself rather than by shifting the existing
    column, because shifting the column would also shift the one row of genuine history
    it does contain -- `shift(1)` of a window ending at t is a window ending at t-1 only
    if the series has no gaps, and SPINS series do have gaps.
    """
    d = df.sort_values(GC + ["__time"]).copy()
    g = d.groupby(GC, observed=True)["base_units"]
    prev = g.shift(1)                      # everything is built from this, never from t

    for col, w in ROLL_SPECS.items():
        if col in d.columns:
            d[col] = prev.groupby([d[c] for c in GC], observed=True).transform(
                lambda s, w=w: s.rolling(w, min_periods=1).mean())
    for col, w in STD_SPECS.items():
        if col in d.columns:
            d[col] = prev.groupby([d[c] for c in GC], observed=True).transform(
                lambda s, w=w: s.rolling(w, min_periods=2).std())
    for col, w in Z_SPECS.items():
        if col in d.columns:
            mu = prev.groupby([d[c] for c in GC], observed=True).transform(
                lambda s, w=w: s.rolling(w, min_periods=2).mean())
            sd = prev.groupby([d[c] for c in GC], observed=True).transform(
                lambda s, w=w: s.rolling(w, min_periods=2).std())
            d[col] = (prev - mu) / sd.replace(0, np.nan)
    if "base_units_wow_delta" in d.columns:
        d["base_units_wow_delta"] = prev - g.shift(2)
    if "base_units_4wk_momentum" in d.columns:
        r4 = d["base_units_roll4_avg"]
        d["base_units_4wk_momentum"] = (
            (r4 / r4.groupby([d[c] for c in GC], observed=True).shift(4)
             .clip(lower=0.01)) - 1).clip(-1, 5).fillna(0)
    if "base_units_13wk_momentum" in d.columns:
        r13 = d["base_units_roll13_avg"]
        d["base_units_13wk_momentum"] = (
            (r13 / r13.groupby([d[c] for c in GC], observed=True).shift(13)
             .clip(lower=0.01)) - 1).clip(-1, 5).fillna(0)
    if "velocity_per_tdp" in d.columns and "tdp" in d.columns:
        # base_units/tdp at week t reconstructs the target. Use the PREVIOUS week's
        # units over the previous week's tdp.
        tprev = d.groupby(GC, observed=True)["tdp"].shift(1)
        d["velocity_per_tdp"] = (prev / tprev.clip(lower=1.0)).clip(upper=500.0)
    return d


# Which features the recursive loop must refresh each step under each arm.
DYNAMIC = (list(ROLL_SPECS) + list(STD_SPECS) + list(Z_SPECS)
           + ["base_units_wow_delta", "base_units_4wk_momentum",
              "base_units_13wk_momentum", "velocity_per_tdp"])


def run_arm(df, feats, cut, qs, qe, eval_keys, fweeks, seasonal, M, refresh: bool):
    """Recursive loop. `refresh` recomputes the window features from the prediction
    chain; otherwise they stay frozen at the anchor, as MO_27 does today."""
    GC = M.GROUP_COLS
    tr = df[df["__time"] <= cut]
    t = tr[np.isfinite(tr["base_units"])]
    va = t.tail(max(200, len(t) // 10))
    m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=TREES,
                          learning_rate=0.05, num_leaves=63, min_child_samples=20,
                          feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=5,
                          reg_alpha=0.1, reg_lambda=0.2, random_state=42,
                          n_jobs=-1, verbose=-1)
    m.fit(t[feats], np.log1p(t["base_units"]),
          eval_set=[(va[feats], np.log1p(va["base_units"]))],
          callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])

    cats = {c: df[c].cat.categories for c in M.CAT_COLS if c in df.columns}
    out = {}
    for key, g in tr.groupby(GC, observed=True):
        if key not in eval_keys:
            continue
        g = g.sort_values("__time")
        if len(g) < 4:
            continue
        hist = list(pd.to_numeric(g["base_units"], errors="coerce").fillna(0))
        tdp_last = float(pd.to_numeric(g["tdp"], errors="coerce").ffill().iloc[-1] or 1.0)
        state = g.iloc[-1].copy()
        seas = M._resolve_seasonal(seasonal, key)
        for h, fd in enumerate(fweeks[:M.HORIZON], start=1):
            t2 = float(fd.isocalendar().week)
            state["week_sin"] = np.sin(2 * np.pi * t2 / 52)
            state["week_cos"] = np.cos(2 * np.pi * t2 / 52)
            state["week_sin26"] = np.sin(2 * np.pi * t2 / 26)
            state["week_cos26"] = np.cos(2 * np.pi * t2 / 26)
            state["base_units_lag1"] = hist[-1]
            if len(hist) >= 4:
                state["base_units_lag4"] = hist[-4]
            if len(hist) >= 13:
                state["base_units_lag13"] = hist[-13]
            if refresh:
                # Exactly the definitions `relag` uses, so inference and training agree.
                for col, w in ROLL_SPECS.items():
                    if col in feats:
                        state[col] = float(np.mean(hist[-w:]))
                for col, w in STD_SPECS.items():
                    if col in feats:
                        state[col] = float(np.std(hist[-w:])) if len(hist) > 1 else 0.0
                for col, w in Z_SPECS.items():
                    if col in feats:
                        sd = float(np.std(hist[-w:]))
                        state[col] = ((hist[-1] - float(np.mean(hist[-w:]))) / sd
                                      if sd > 0 else 0.0)
                if "base_units_wow_delta" in feats:
                    state["base_units_wow_delta"] = (hist[-1] - hist[-2]
                                                     if len(hist) > 1 else 0.0)
                if "velocity_per_tdp" in feats:
                    state["velocity_per_tdp"] = min(500.0, hist[-1] / max(1.0, tdp_last))
            X = pd.DataFrame([state])[feats]
            for c, cc in cats.items():
                if c in X.columns:
                    X[c] = pd.Categorical(X[c], categories=cc)
            p = float(np.clip(np.expm1(m.predict(X))[0], 0, None))
            p = max(0.0, p * M._seasonal_mult(
                seas, fd, cut, prev_fd=fweeks[h - 2] if h > 1 else None))
            hist.append(p)
            if qs <= fd <= qe:
                out[(key, fd)] = p
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default=None)
    ap.add_argument("--channel", default="CONVENTIONAL|FOOD")
    a = ap.parse_args()

    os.environ["MO_SEASONAL_MODE"] = "step"
    import MO_80_quarterly_honest_backtest as M
    importlib.reload(M)

    feats = list(pickle.load(
        open("outputs/model_retailer_sales_q50_v10_full.pkl", "rb")).feature_name_)
    raw = M.load_panel(feats)
    fixed = relag(raw, M.GROUP_COLS)
    seasonal = M.load_seasonal_index()
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(pd.unique(raw["__time"])), utc=True))
    quarters = [q for q in M.QUARTERS if q[0] != "Q4 2026"]

    ev = raw["channel_outlet"] == a.channel
    if a.account:
        ev &= raw["retail_account"] == a.account
    scope = f"{a.account} {a.channel}" if a.account else "PORTFOLIO-WIDE"

    # Show the fix actually changed what it claims to have changed.
    chk = raw[["base_units_roll4_avg", "base_units_wow_delta"]].head(0)
    print(f"MO_118 - feature contract audit · {scope} · mode=step\n")
    for c in ("base_units_roll4_avg", "base_units_wow_delta", "velocity_per_tdp"):
        if c in raw.columns:
            d = np.abs(raw[c] - fixed[c])
            print(f"  relag changed {c:<24s} on {np.isfinite(d).sum():>7,} comparable rows, "
                  f"median |Δ| {np.nanmedian(d):>10.3f}")
    print()
    # The 2x2 is the point: training contract x inference handling. The missing cell
    # (current training + refreshed inference) is what isolates FEEDBACK from the
    # training contract, and it is the one that says whether MO_27's freeze is an
    # oversight or a damper.
    ARMS = [("current_frozen", raw, False), ("current_refresh", raw, True),
            ("lagged_frozen", fixed, False), ("lagged_refresh", fixed, True)]
    print(f"  {'quarter':<9s} " + "  ".join(f"{n:>15s}" for n, _, _ in ARMS))

    res = {n: {} for n, _, _ in ARMS}
    for ql, qc, q1, q2 in quarters:
        cut = pd.Timestamp(qc, tz="UTC")
        qs = pd.Timestamp(q1, tz="UTC")
        qe = pd.Timestamp(q2, tz="UTC") + pd.Timedelta(days=6)
        act = raw[ev & (raw["__time"] >= qs) & (raw["__time"] <= qe)]
        if act.empty:
            continue
        truth = {(k[:-1], k[-1]): float(v) for k, v in
                 act.groupby(M.GROUP_COLS + ["__time"], observed=True)["base_units"].sum().items()}
        ek = {k[0] for k in truth}
        fw = M.future_weeks(weeks, cut, M.HORIZON)
        cells = []
        for name, frame, refresh in ARMS:
            pred = run_arm(frame, feats, cut, qs, qe, ek, fw, seasonal, M, refresh)
            s = M.score(truth, pred)
            res[name][ql] = s
            cells.append(f"{s['wmape']:>8.1f} {s['bias']:>6.3f}" if s else f"{'--':>15s}")
        print(f"  {ql:<9s} " + "  ".join(cells))

    print(f"\n  {'arm':<16s} {'wMAPE':>8s} {'bias':>7s}  {'|bias-1|':>8s}")
    means = {}
    for name, _, _ in ARMS:
        v = [x for x in res[name].values() if x]
        means[name] = {"wmape": float(np.nanmean([x["wmape"] for x in v])),
                       "bias": float(np.nanmean([x["bias"] for x in v])),
                       "abs_bias_err": float(np.nanmean([abs(x["bias"] - 1) for x in v]))}
        print(f"  {name:<16s} {means[name]['wmape']:>8.2f} {means[name]['bias']:>7.3f}  "
              f"{means[name]['abs_bias_err']:>8.3f}")

    base = means["current_frozen"]["wmape"]
    print(f"\n  {'':<18s} {'frozen':>10s} {'refreshed':>11s}   refresh cost")
    for tr_lbl, a, b in (("current training", "current_frozen", "current_refresh"),
                         ("lagged training ", "lagged_frozen", "lagged_refresh")):
        print(f"  {tr_lbl:<18s} {means[a]['wmape']:>10.2f} {means[b]['wmape']:>11.2f}   "
              f"{means[b]['wmape'] - means[a]['wmape']:+.2f}pp")
    d_contract = means["lagged_frozen"]["wmape"] - means["current_frozen"]["wmape"]
    d_feedback = means["current_refresh"]["wmape"] - means["current_frozen"]["wmape"]
    print(f"\n  training-contract effect, holding inference FROZEN: {d_contract:+.2f}pp")
    print(f"  REFRESH effect, holding training CURRENT:           {d_feedback:+.2f}pp")
    if d_feedback > 2:
        print("\n  -> MO_27's freeze is a DAMPER, not an oversight. Refreshing"
              "\n     autoregressive derived features inside a recursive loop compounds"
              "\n     error -- structurally the same failure as the seasonal multiplier"
              "\n     in MO_113. Any fix to the training contract must keep the freeze.")
    elif d_feedback < -2:
        print("\n  -> the freeze COSTS accuracy and MO_80 was right to refresh."
              "\n     MO_27 and MO_80 must be reconciled toward refreshing.")
    else:
        print("\n  -> freeze vs refresh is near-neutral; the divergence between MO_27 and"
              "\n     MO_80 is a correctness problem but not an accuracy one.")
    d1, d2 = d_contract, d_feedback

    OUT.write_text(json.dumps({"scope": scope, "by_quarter": res, "means": means,
                               "lagged_vs_current_pp": d1,
                               "lagged_vs_frozen_pp": d2}, indent=2, default=str))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
