"""MO_29 — Tree-budget probe: where does q50 actually converge?

ONE question, ONE model fit. MO_26's q50 has pegged its n_estimators cap at every
version — v6 at 2000, v7 at 2999/3000, v8 at 4000, v9 at 3998/4000 — always with
validation loss still falling. So the cap, not convergence, has been setting the tree
count, and the tuned learning_rate has been compensating for a truncated budget.

Running all 12 MO_26 fits at a higher cap costs ~an hour. Only the medians are
capacity-hungry (v9: q10 1097, q90 1203, q50 3998), so this fits q50 base_units alone
at a high cap with generous patience and reports where early stopping actually lands.

Mechanical point that drove the design: with patience P and cap C, a triggered stop
puts best_iteration at or below C - P. v9 returned 3998 against a 4000 cap with P=50,
which is proof it never triggered. So the cap must exceed true convergence by at least
P for the probe to mean anything — hence a deliberately generous cap here.

Outputs the convergence point and whether it is still budget-limited. That number sets
N_ESTIMATORS_MAX for MO_28 and n_estimators for MO_26.

Run:  python MO_29_tree_budget_probe.py [--cap 12000] [--patience 300]
"""

import argparse
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from datetime import datetime, timezone
from pathlib import Path

from mo_panel import (CAT_COLS, drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_ak_hi_market_variants, warn_nested_rma_duplicates,
                      drop_short_series, GROUP_COLS)

# Import MO_26's exact feature list and params so the probe measures the real model,
# not an approximation of it.
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "mo26", str(Path(__file__).parent / "MO_26_retailer_sales_train.py"))
_mo26 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mo26)   # __main__ guard means this only loads definitions

FEATURE_COLS   = _mo26.FEATURE_COLS
LGBM_BASE      = dict(_mo26.LGBM_BASE)
RECENCY_LAMBDA = 0.02
VAL_WEEKS      = 13
QUANTILE       = 0.50


def main(cap: int, patience: int):
    print(f"MO_29 tree-budget probe — q50 base_units, cap={cap:,}, patience={patience}")
    print(f"  (MO_26 v9 returned best_iter 3998 against a 4000 cap with patience 50,")
    print(f"   i.e. it never triggered — validation loss was still falling.)\n")

    df = pd.read_parquet("outputs/retailer_sales_weekly.parquet")
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    if "week_of_year" in df.columns:
        woy = pd.to_numeric(df["week_of_year"], errors="coerce").fillna(1)
        df["week_sin26"] = np.sin(2 * np.pi * woy / 26)
        df["week_cos26"] = np.cos(2 * np.pi * woy / 26)

    for c in [c for c in FEATURE_COLS if c not in CAT_COLS]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c, fill in (("spins_flavor_canonical", "UNKNOWN"), ("source_brand", "UNKNOWN"),
                    ("geography_raw", "UNKNOWN"), ("spins_flavor_raw", "UNKNOWN"),
                    ("nfp_protein_range", "UNKNOWN")):
        if c in df.columns:
            df[c] = df[c].fillna(fill).astype(str).str.strip().replace("", fill)
    for c in CAT_COLS:
        if c in df.columns:
            df[c] = df[c].astype("category")

    df = df.dropna(subset=["base_units"]).copy()
    print("  ── Panel rules (must match MO_26) ──")
    df = fill_promo_mechanic_nulls(df)
    df = drop_military_accounts(df)
    # AK/HI supplementary markets are nested duplicates of the base market (Circle K was
    # being counted twice). Excluded BY DEFINITION, not by their happening to be zero-volume.
    df = drop_ak_hi_market_variants(df)
    df = drop_zero_volume_geographies(df, target="base_units")
    df = apply_rma_priority(df)
    df = drop_short_series(df)
    for c in CAT_COLS:
        if c in df.columns and isinstance(df[c].dtype, pd.CategoricalDtype):
            df[c] = df[c].cat.remove_unused_categories()
    df["log_base_units"] = np.log1p(df["base_units"])

    cutoff = df["__time"].max() - pd.Timedelta(weeks=VAL_WEEKS)
    train, val = df[df["__time"] <= cutoff], df[df["__time"] > cutoff]
    available = [c for c in FEATURE_COLS if c in df.columns]
    print(f"\n  Train {len(train):,} | Val {len(val):,} | features {len(available)} "
          f"| cutoff {cutoff.date()}")

    t_max = train["__time"].max()
    weeks_ago = (t_max - train["__time"]).dt.total_seconds() / (7 * 24 * 3600)
    sw = np.exp(-RECENCY_LAMBDA * weeks_ago.clip(lower=0).values)

    params = {**LGBM_BASE, "objective": "quantile", "alpha": QUANTILE,
              "n_estimators": cap}
    model = lgb.LGBMRegressor(**params)
    print(f"\n  Fitting (lr={params['learning_rate']}, num_leaves={params['num_leaves']}) …\n")
    model.fit(train[available], train["log_base_units"].values,
              sample_weight=sw,
              eval_set=[(val[available], val["log_base_units"].values)],
              eval_metric="quantile",
              callbacks=[lgb.early_stopping(patience, verbose=False),
                         lgb.log_evaluation(250)])

    best = int(model.best_iteration_ or cap)
    hit_cap = best > cap - patience
    curve = model.evals_result_["valid_0"]["quantile"]

    print(f"\n{'='*64}")
    print(f"  best_iteration : {best:,}  of cap {cap:,}  (patience {patience})")
    print(f"  best score     : {min(curve):.6f}")
    print(f"  CURVE IS ASYMPTOTIC: {hit_cap}"
          f"{'  <-- never converges; see min_delta simulation below' if hit_cap else '  <-- genuine convergence'}")
    print(f"\n  Marginal value of trees beyond 4000 (v9's cap):")
    for n in (1000, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 12000):
        if n <= len(curve):
            delta = (curve[3999] - curve[n - 1]) / curve[3999] * 100 if len(curve) > 3999 else float("nan")
            print(f"    {n:>6,} trees  score {curve[n-1]:.6f}"
                  f"{f'   {delta:+.2f}% vs 4000' if n != 4000 and len(curve) > 3999 else ''}")

    # ── min_delta knee simulation ────────────────────────────────────────────
    # The curve is ASYMPTOTIC, not convergent: it pegged the cap with patience 300 and
    # was still improving. So there is no convergence point to find at any cap, and
    # plain early stopping can never fire — a fourth-decimal improvement resets the
    # patience counter forever. That is why every version since v6 has pegged its cap;
    # it was never evidence of capacity starvation.
    #
    # LightGBM's early_stopping(min_delta=...) fixes this: an improvement smaller than
    # min_delta does not count as improvement, so stopping lands on the
    # diminishing-returns knee instead of chasing noise to the ceiling.
    #
    # Simulated from the saved curve rather than refitting per threshold — one fit
    # answers every candidate, which is the whole point of keeping the curve.
    def simulate(md: float, pat: int) -> int:
        best_s, best_i, since = float("inf"), 0, 0
        for i, s in enumerate(curve):
            if s < best_s - md:
                best_s, best_i, since = s, i, 0
            else:
                since += 1
                if since >= pat:
                    return best_i + 1
        return len(curve)

    print(f"\n  min_delta knee simulation (patience 50, as MO_26 uses):")
    print(f"    {'min_delta':>10s} {'stops at':>9s} {'score':>10s} {'vs 12k cap':>11s} {'trees saved':>12s}")
    knees = {}
    full = curve[-1]
    for md in (0.0, 1e-6, 5e-6, 1e-5, 2e-5, 5e-5, 1e-4):
        it = simulate(md, 50)
        sc = curve[it - 1]
        knees[f"{md:g}"] = {"stops_at": it, "score": float(sc),
                            "pct_worse_than_cap": float((sc - full) / full * 100)}
        print(f"    {md:>10g} {it:>9,} {sc:>10.6f} {(sc-full)/full*100:>10.2f}% "
              f"{len(curve)-it:>12,}")

    out = {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "cap": cap, "patience": patience,
        "best_iteration": best, "best_score": float(min(curve)),
        "still_budget_limited": bool(hit_cap),
        "curve_is_asymptotic": bool(hit_cap),
        "v9_reference": {"best_iteration": 3998, "cap": 4000, "patience": 50},
        "score_at": {str(n): float(curve[n - 1]) for n in
                     (1000, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 12000)
                     if n <= len(curve)},
        "min_delta_knees": knees,
        "validation_curve": [float(x) for x in curve],   # keep it: re-simulating is free
        "panel_rows": int(len(df)), "n_features": len(available),
        "caveat": ("Single 13-week holdout window (cutoff shown above), so these numbers "
                   "describe one future window and span the Aug-Sep seasonal trough. "
                   "n_estimators is a COMPUTE BUDGET decision, not a hyperparameter — more "
                   "always helps with decaying returns. Confirm any choice with MO_28's "
                   "3-fold walk-forward CV. Also note the convergence behaviour is a "
                   "property of lr=%s / num_leaves=%s, not of the data: a higher learning "
                   "rate reaches a given loss in fewer trees, so the tree count moves "
                   "whenever Optuna moves lr." % (params["learning_rate"], params["num_leaves"])),
    }
    _pick = knees.get("1e-05") or knees.get("1e-06")
    out["recommendation"] = (
        f"curve is asymptotic - do NOT chase the cap. Use early_stopping(min_delta=1e-5) so "
        f"the tree count self-selects (knee ~{_pick['stops_at']:,} trees, "
        f"{_pick['pct_worse_than_cap']:+.2f}% vs the {cap:,}-tree ceiling); keep n_estimators "
        f"as a generous budget ceiling, not a tuned value."
        if hit_cap else
        f"genuine convergence at {best:,}; set n_estimators >= {best + patience:,}")

    p = Path("outputs/mo29_tree_budget_probe.json")
    p.write_text(json.dumps(out, indent=2))
    print(f"\n  → {p}")
    print(f"  RECOMMENDATION: {out['recommendation']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=12000)
    ap.add_argument("--patience", type=int, default=300)
    main(**vars(ap.parse_args()))
