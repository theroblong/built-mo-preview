"""MO_27d — THE CONTROL: recursive accuracy on the YAGO band (>=52 weeks).

MO_27c measured the no-YAGO band (<52 wks, 40.9% of demand) at 37.12% recursive wMAPE with
the forecast collapsing to last_actual x 1.03 by step 3. The open question that determines
the entire roadmap:

  * If the YAGO band comes back ~10%, then 37% is specifically a COLD-START penalty, the
    year-ago anchor is what rescues mature series, and projecting TDP forward for young series
    is clearly the top priority.
  * If the YAGO band also comes back ~30%, then recursive AR is weak EVERYWHERE, the problem is
    the forecasting method rather than cold-start, and the roadmap changes materially — the
    horse race would need to cover all series, not just short ones.

Do not assume which. Three hypotheses were wrong today already.

Production logic reproduced for this band (MO_27 ~line 553):
    seasonal_ref = lag52 * yoy_ratio        # yoy_ratio clipped to [0.5, 2.0]
    blended      = (1 - W) * pred + W * seasonal_ref,   W = SEASONAL_BLEND_WEIGHT = 0.40
applied only when yoy_ratio exists and lag52 > 0. lag52 comes from ACTUALS (index
N_actual - 53 + k is always an actual, never a prediction), matching production.

Three arms so the YAGO blend's own contribution is visible:
    pure AR      no seasonal adjustment at all
    + STL        the portfolio multiplier (what no-YAGO series get)
    + YAGO       the year-ago blend (what these series actually get in production)

Run:  python MO_27d_yago_band_test.py
"""
from __future__ import annotations
import importlib.util, json, pickle, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

_s = importlib.util.spec_from_file_location("mo27", str(Path(__file__).parent / "MO_27_retailer_sales_forecast.py"))
mo27 = importlib.util.module_from_spec(_s); _s.loader.exec_module(mo27)
from mo_panel import (CAT_COLS, drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_short_series, GROUP_COLS)

MV, H, W = "v9", 13, 0.40
OUT = Path("outputs/mo27d_yago_band_test.json")


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = np.abs(a).sum()
    return float(np.abs(a - p).sum() / d * 100) if d > 0 else float("nan")


def main():
    model = pickle.load(open(f"outputs/model_retailer_sales_q50_{MV}_full.pkl", "rb"))
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
    print(f"cutoff {cutoff.date()} | horizon {H}")

    arms = {"pure_AR": [], "plus_STL": [], "plus_YAGO": []}
    flat = {k: [] for k in arms}
    n = 0
    for keys, g in df.groupby(GROUP_COLS, observed=True):
        g = g.sort_values("__time")
        seed = g[g["__time"] <= cutoff]; fut = g[g["__time"] > cutoff].head(H)
        if len(seed) < 52 or len(fut) < 6: continue      # YAGO band only
        n += 1
        latest = seed.iloc[-1]
        hist0 = seed["base_units"].astype(float).tolist()
        N = len(hist0)
        # lag52 sequence from ACTUALS, and the YoY ratio, exactly as MO_27 builds them
        lag52_seq = [float(hist0[N - 53 + k]) if 0 <= (N - 53 + k) < N else np.nan
                     for k in range(1, len(fut) + 1)]
        yago_anchor = float(hist0[N - 52]) if N >= 52 else None
        yoy = float(np.clip(hist0[-1] / yago_anchor, 0.5, 2.0)) if (yago_anchor and yago_anchor > 0) else None

        skip = CAT_COLS | {"week_of_year","week_sin","week_cos","week_sin26","week_cos26",
                "is_promo_week","promo_intensity","units_lift_tpr","units_lift_any_display",
                "units_lift_any_feature","promo_52w_lag","promo_rate_woy",
                "base_units_lag1","base_units_lag4","base_units_lag13","base_units_lag52",
                "arp_lag1","arp_wow_delta","arp_roll8_avg","arp_roll8_std","arp"}
        static = {c: float(pd.to_numeric(latest.get(c), errors="coerce") or 0)
                  for c in feats if c not in skip}
        cats = {c: mo27._cat_str(latest.get(c), "UNKNOWN") for c in CAT_COLS if c in feats}
        arp = float(pd.to_numeric(latest.get("arp"), errors="coerce") or 0)
        wsl = int(pd.to_numeric(latest.get("weeks_since_launch"), errors="coerce") or 0)
        act = fut["base_units"].astype(float).tolist()

        for arm in arms:
            hist = list(hist0); preds = []
            for step in range(1, len(fut) + 1):
                fdate = cutoff + pd.Timedelta(weeks=step); woy = int(fdate.isocalendar().week)
                l52 = lag52_seq[step - 1]
                st = {**static, **cats,
                      "week_sin": np.sin(2*np.pi*woy/52), "week_cos": np.cos(2*np.pi*woy/52),
                      "week_sin26": np.sin(2*np.pi*woy/26), "week_cos26": np.cos(2*np.pi*woy/26),
                      "weeks_since_launch": wsl + step, "arp": arp, "arp_lag1": arp,
                      "arp_wow_delta": 0.0, "arp_roll8_avg": arp, "arp_roll8_std": 0.0,
                      "is_promo_week": 0.0, "promo_intensity": 0.0, "units_lift_tpr": 0.0,
                      "units_lift_any_display": 0.0, "units_lift_any_feature": 0.0,
                      "promo_52w_lag": 0.0, "promo_rate_woy": 0.0,
                      "base_units_lag1": hist[-1],
                      "base_units_lag4": hist[-4] if len(hist) >= 4 else np.nan,
                      "base_units_lag13": hist[-13] if len(hist) >= 13 else np.nan,
                      "base_units_lag52": l52}
                p = float(max(0.0, np.expm1(model.predict(mo27._build_feature_row(st, feats, model=model))[0])))
                if arm == "plus_YAGO" and yoy is not None and np.isfinite(l52) and l52 > 0 and p > 0:
                    p = max(0.0, (1 - W) * p + W * (l52 * yoy))
                elif arm == "plus_STL":
                    p = max(0.0, p * max(0.1, 1.0 + stl.get(woy, 0.0)))
                preds.append(p); hist.append(p)
            arms[arm].append((act[:len(preds)], preds))
            sa = np.std(act[:len(preds)])
            if sa > 0: flat[arm].append(np.std(preds) / sa)

    print(f"YAGO-band series (>=52 wks at cutoff): {n}\n")
    print(f"  {'arm':>12s} {'wMAPE':>8s} {'flatten SD ratio':>18s}")
    res = {}
    for arm, rows in arms.items():
        a = np.concatenate([np.asarray(x[0]) for x in rows])
        p = np.concatenate([np.asarray(x[1]) for x in rows])
        w = wmape(a, p); fr = float(np.median(flat[arm]))
        res[arm] = {"wmape": w, "flatten_ratio": fr, "n_series": n}
        print(f"  {arm:>12s} {w:>8.2f} {fr:>18.3f}")

    print(f"\n  CONTROL COMPARISON")
    print(f"    no-YAGO band (MO_27c, <52 wks) : 37.12% pure AR / 34.47% +STL")
    print(f"    YAGO band    (this, >=52 wks)  : {res['pure_AR']['wmape']:.2f}% pure AR / "
          f"{res['plus_YAGO']['wmape']:.2f}% +YAGO (production)")
    gap = 37.12 - res["plus_YAGO"]["wmape"]
    print(f"\n    gap = {gap:+.2f}pp")
    if res["plus_YAGO"]["wmape"] < 20:
        print("    => COLD-START PENALTY. The year-ago anchor rescues mature series;")
        print("       projecting TDP forward for young series is the top priority.")
    else:
        print("    => RECURSIVE AR IS WEAK EVERYWHERE. The problem is the method, not")
        print("       cold-start. The horse race must cover ALL series, not just short ones.")
    res["_control"] = {"no_yago_pure_AR": 37.12, "no_yago_plus_STL": 34.47,
                       "gap_pp": gap, "cutoff": str(cutoff.date())}
    OUT.write_text(json.dumps(res, indent=2)); print(f"\n  → {OUT}")


if __name__ == "__main__":
    main()
