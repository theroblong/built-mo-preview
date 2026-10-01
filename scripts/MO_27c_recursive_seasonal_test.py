"""MO_27c — RECURSIVE backtest: does the STL seasonal multiplier help in production?

Supersedes MO_27b, which was INVALID for this question. MO_27b evaluated the multiplier on
MO_26's teacher-forced validation split, where predictions use ACTUAL lags that already carry
the seasonal decline — so the multiplier double-counted and showed a spurious 8.5pp
degradation. The validation window also sat in the trough (mean multiplier x0.890), making the
result close to an arithmetic artifact of an 11% haircut.

Production is different. MO_27 runs RECURSIVELY: lag1 comes from the previous step's own
prediction. Its own comment on SEASONAL_BLEND_WEIGHT states the consequence —
"autoregressive convergence causes the 13-week forward forecast to collapse to a flat mean
after ~4 steps" — which is precisely the gap the seasonal layer exists to fill. So the
multiplier must be judged in the recursive setting, not the teacher-forced one.

DESIGN
  * Reuses MO_27's own `_build_feature_row` (imported) rather than reimplementing feature
    construction, so categorical handling and column order match production exactly.
  * Cutoff 13 weeks before the panel end; forecast 13 steps recursively; compare to actuals.
  * Restricted to series with <52 weeks of history AT the cutoff — the only series where the
    YAGO blend cannot fire and the STL branch actually applies in production.
  * Two arms: multiplier OFF vs ON.

SELF-CHECK ON THIS LOOP
  If MO_27's flattening claim is right, the OFF arm should show forecast variance across the
  13 steps collapsing relative to actual variance. That is reported. If it does NOT flatten,
  this loop is not reproducing production behaviour and its verdict should be discarded.

Run:  python MO_27c_recursive_seasonal_test.py
"""
from __future__ import annotations
import importlib.util, json, pickle, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

_s = importlib.util.spec_from_file_location("mo27", str(Path(__file__).parent / "MO_27_retailer_sales_forecast.py"))
mo27 = importlib.util.module_from_spec(_s); _s.loader.exec_module(mo27)   # __main__-guarded

from mo_panel import (CAT_COLS, drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_short_series, GROUP_COLS)

MV, H, OUT = "v9", 13, Path("outputs/mo27c_recursive_seasonal_test.json")


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = np.abs(a).sum()
    return float(np.abs(a - p).sum() / d * 100) if d > 0 else float("nan")


def main():
    with open(f"outputs/model_retailer_sales_q50_{MV}_full.pkl", "rb") as f:
        model = pickle.load(f)
    feats = list(model.feature_name_)
    seas = pd.read_csv("outputs/mo59_seasonal_index.csv")
    stl = dict(zip(seas["week_of_year"].astype(int), seas["seasonal_index"]))

    df = pd.read_parquet("outputs/retailer_sales_weekly.parquet")
    df["__time"] = pd.to_datetime(df["__time"], utc=True)
    for c in [c for c in feats if c not in CAT_COLS]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    for c, fv in (("spins_flavor_canonical","UNKNOWN"),("source_brand","UNKNOWN"),
                  ("geography_raw","UNKNOWN"),("spins_flavor_raw","UNKNOWN"),
                  ("nfp_protein_range","UNKNOWN")):
        if c in df.columns: df[c] = df[c].fillna(fv).astype(str).str.strip().replace("", fv)
    df = df.dropna(subset=["base_units"]).copy()
    for fn in (fill_promo_mechanic_nulls, drop_military_accounts,
               drop_zero_volume_geographies, apply_rma_priority, drop_short_series):
        df = fn(df, verbose=False)
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    cutoff = df["__time"].max() - pd.Timedelta(weeks=H)
    print(f"cutoff {cutoff.date()} | horizon {H} wks | panel to {df['__time'].max().date()}")

    rows_off, rows_on, flat = [], [], []
    n_series = 0
    for keys, g in df.groupby(GROUP_COLS, observed=True):
        g = g.sort_values("__time")
        seed = g[g["__time"] <= cutoff]
        fut  = g[(g["__time"] > cutoff) & (g["__time"] <= cutoff + pd.Timedelta(weeks=H))]
        if len(seed) < 13 or len(fut) < 6:        continue
        if len(seed) >= 52:                        continue   # YAGO would fire; STL not used
        n_series += 1
        latest = seed.iloc[-1]
        static = {}
        skip = CAT_COLS | {"week_of_year","week_sin","week_cos","week_sin26","week_cos26",
                "is_promo_week","promo_intensity","units_lift_tpr","units_lift_any_display",
                "units_lift_any_feature","promo_52w_lag","promo_rate_woy",
                "base_units_lag1","base_units_lag4","base_units_lag13","base_units_lag52",
                "arp_lag1","arp_wow_delta","arp_roll8_avg","arp_roll8_std","arp"}
        for c in feats:
            if c not in skip:
                static[c] = float(pd.to_numeric(latest.get(c), errors="coerce") or 0)
        cats = {c: mo27._cat_str(latest.get(c), "UNKNOWN") for c in CAT_COLS if c in feats}
        arp = float(pd.to_numeric(latest.get("arp"), errors="coerce") or 0)
        wsl = int(pd.to_numeric(latest.get("weeks_since_launch"), errors="coerce") or 0)

        for arm, use_seas in (("off", False), ("on", True)):
            hist = seed["base_units"].astype(float).tolist()
            preds = []
            for step in range(1, len(fut) + 1):
                fdate = cutoff + pd.Timedelta(weeks=step)
                woy = int(fdate.isocalendar().week)
                st = {**static, **cats,
                      "week_sin": np.sin(2*np.pi*woy/52), "week_cos": np.cos(2*np.pi*woy/52),
                      "week_sin26": np.sin(2*np.pi*woy/26), "week_cos26": np.cos(2*np.pi*woy/26),
                      "weeks_since_launch": wsl + step, "arp": arp, "arp_lag1": arp,
                      "arp_wow_delta": 0.0, "arp_roll8_avg": arp, "arp_roll8_std": 0.0,
                      "is_promo_week": 0.0, "promo_intensity": 0.0, "units_lift_tpr": 0.0,
                      "units_lift_any_display": 0.0, "units_lift_any_feature": 0.0,
                      "promo_52w_lag": 0.0, "promo_rate_woy": 0.0,
                      "base_units_lag1":  hist[-1]  if len(hist) >= 1  else np.nan,
                      "base_units_lag4":  hist[-4]  if len(hist) >= 4  else np.nan,
                      "base_units_lag13": hist[-13] if len(hist) >= 13 else np.nan,
                      "base_units_lag52": np.nan}
                X = mo27._build_feature_row(st, feats, model=model)
                p = float(max(0.0, np.expm1(model.predict(X)[0])))
                if use_seas:
                    p = max(0.0, p * max(0.1, 1.0 + stl.get(woy, 0.0)))
                preds.append(p); hist.append(p)
            act = fut["base_units"].astype(float).tolist()[:len(preds)]
            (rows_on if use_seas else rows_off).append((act, preds))
            if not use_seas:
                flat.append((np.std(preds), np.std(act)))

    print(f"series tested (no-YAGO, <52 wks at cutoff): {n_series}\n")

    # SELF-CHECK: does the OFF arm flatten, as MO_27's comment claims?
    fs = np.array([f for f, _ in flat]); as_ = np.array([a for _, a in flat])
    ratio = float(np.median(fs[as_ > 0] / as_[as_ > 0]))
    print(f"SELF-CHECK — forecast flattening in the OFF arm:")
    print(f"  median SD(forecast)/SD(actual) across 13 steps = {ratio:.3f}")
    print(f"  {'OK — forecast is flatter than actuals, consistent with MO_27s comment' if ratio < 0.7 else 'WARNING — no flattening; this loop may not reproduce production. Treat verdict as void.'}")

    def agg(rows):
        a = np.concatenate([np.asarray(x[0]) for x in rows])
        p = np.concatenate([np.asarray(x[1]) for x in rows])
        return wmape(a, p)
    off, on = agg(rows_off), agg(rows_on)
    print(f"\n  RECURSIVE wMAPE, no-YAGO band:")
    print(f"    multiplier OFF : {off:.2f}%")
    print(f"    multiplier ON  : {on:.2f}%   ({on-off:+.2f}pp)")
    print(f"    verdict: {'HELPS' if on < off else 'HURTS'}")
    per = [(wmape(*r_off), wmape(*r_on)) for r_off, r_on in zip(rows_off, rows_on)]
    per = [(o, n) for o, n in per if np.isfinite(o) and np.isfinite(n)]
    helped = float(np.mean([n < o for o, n in per]))
    print(f"    per-series: HELPS {helped*100:.0f}% / HURTS {(1-helped)*100:.0f}%  (n={len(per)})")

    OUT.write_text(json.dumps({
        "cutoff": str(cutoff.date()), "horizon": H, "n_series": n_series,
        "wmape_off": off, "wmape_on": on, "delta_pp": on - off,
        "verdict": "HELPS" if on < off else "HURTS",
        "per_series_helped_frac": helped,
        "flattening_ratio_sd_forecast_over_actual": ratio,
        "self_check_passed": bool(ratio < 0.7),
        "note": ("Recursive loop with predicted lags, reusing MO_27._build_feature_row. "
                 "Supersedes MO_27b which was teacher-forced and therefore invalid for this "
                 "question. Approximations vs production MO_27: ARP held flat, promo flags 0, "
                 "no YAGO branch (by construction), no q90 calibration."),
    }, indent=2)); print(f"\n  → {OUT}")


if __name__ == "__main__":
    main()
