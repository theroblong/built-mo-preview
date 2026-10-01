"""MO_27e — GATE: does the YAGO->STL swap hold across multiple cutoffs?

MO_27d measured, at a single cutoff (2026-06-07), that MO_27's year-ago seasonal blend is
actively harmful on the YAGO band: 22.35% pure AR / 19.51% +STL / 31.19% +YAGO (production).
That would make swapping YAGO for STL worth ~11.7pp on 58% of demand.

One window is not enough to change production. That window sat in the seasonal trough
(Jun-Sep, mean STL multiplier x0.890), and a downward multiplier flatters any forecast whose
level is too high. If the result is real it must survive cutoffs in rising periods too.

So: the same recursive loop at four cutoffs, both bands, three arms. The swap is only
justified if +STL beats +YAGO at every cutoff -- not on average.

Band membership is recomputed per cutoff from history length AT that cutoff, matching how
production decides which branch fires.

Run:  python MO_27e_multicutoff_verify.py [--backs 13 26 39 52]
"""
from __future__ import annotations
import argparse, importlib.util, json, pickle, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

_s = importlib.util.spec_from_file_location("mo27", str(Path(__file__).parent / "MO_27_retailer_sales_forecast.py"))
mo27 = importlib.util.module_from_spec(_s); _s.loader.exec_module(mo27)
from mo_panel import (CAT_COLS, drop_zero_volume_geographies, apply_rma_priority,
                      fill_promo_mechanic_nulls, drop_military_accounts,
                      drop_short_series, GROUP_COLS)

MV, H, W = "v9", 13, 0.40
OUT = Path("outputs/mo27e_multicutoff_verify.json")


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = np.abs(a).sum()
    return float(np.abs(a - p).sum() / d * 100) if d > 0 else float("nan")


def prep():
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
    return model, feats, stl, df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)


SKIP = CAT_COLS | {"week_of_year","week_sin","week_cos","week_sin26","week_cos26",
    "is_promo_week","promo_intensity","units_lift_tpr","units_lift_any_display",
    "units_lift_any_feature","promo_52w_lag","promo_rate_woy","base_units_lag1",
    "base_units_lag4","base_units_lag13","base_units_lag52","arp_lag1","arp_wow_delta",
    "arp_roll8_avg","arp_roll8_std","arp"}


def run_cutoff(model, feats, stl, df, cutoff):
    out = {b: {a: [] for a in ("pure_AR", "plus_STL", "plus_YAGO")} for b in ("no_yago", "yago")}
    for keys, g in df.groupby(GROUP_COLS, observed=True):
        g = g.sort_values("__time")
        seed = g[g["__time"] <= cutoff]; fut = g[g["__time"] > cutoff].head(H)
        if len(seed) < 13 or len(fut) < 6: continue
        band = "yago" if len(seed) >= 52 else "no_yago"
        latest = seed.iloc[-1]; hist0 = seed["base_units"].astype(float).tolist(); N = len(hist0)
        lag52_seq = [float(hist0[N-53+k]) if 0 <= (N-53+k) < N else np.nan
                     for k in range(1, len(fut)+1)]
        ya = float(hist0[N-52]) if N >= 52 else None
        yoy = float(np.clip(hist0[-1]/ya, 0.5, 2.0)) if (ya and ya > 0) else None
        static = {c: float(pd.to_numeric(latest.get(c), errors="coerce") or 0)
                  for c in feats if c not in SKIP}
        cats = {c: mo27._cat_str(latest.get(c), "UNKNOWN") for c in CAT_COLS if c in feats}
        arp = float(pd.to_numeric(latest.get("arp"), errors="coerce") or 0)
        wsl = int(pd.to_numeric(latest.get("weeks_since_launch"), errors="coerce") or 0)
        act = fut["base_units"].astype(float).tolist()
        for arm in ("pure_AR", "plus_STL", "plus_YAGO"):
            if arm == "plus_YAGO" and band == "no_yago": continue
            hist = list(hist0); preds = []
            for step in range(1, len(fut)+1):
                woy = int((cutoff + pd.Timedelta(weeks=step)).isocalendar().week)
                l52 = lag52_seq[step-1]
                st = {**static, **cats,
                      "week_sin": np.sin(2*np.pi*woy/52), "week_cos": np.cos(2*np.pi*woy/52),
                      "week_sin26": np.sin(2*np.pi*woy/26), "week_cos26": np.cos(2*np.pi*woy/26),
                      "weeks_since_launch": wsl+step, "arp": arp, "arp_lag1": arp,
                      "arp_wow_delta": 0.0, "arp_roll8_avg": arp, "arp_roll8_std": 0.0,
                      "is_promo_week": 0.0, "promo_intensity": 0.0, "units_lift_tpr": 0.0,
                      "units_lift_any_display": 0.0, "units_lift_any_feature": 0.0,
                      "promo_52w_lag": 0.0, "promo_rate_woy": 0.0,
                      "base_units_lag1": hist[-1],
                      "base_units_lag4": hist[-4] if len(hist) >= 4 else np.nan,
                      "base_units_lag13": hist[-13] if len(hist) >= 13 else np.nan,
                      "base_units_lag52": l52 if band == "yago" else np.nan}
                p = float(max(0.0, np.expm1(model.predict(mo27._build_feature_row(st, feats, model=model))[0])))
                if arm == "plus_YAGO" and yoy is not None and np.isfinite(l52) and l52 > 0 and p > 0:
                    p = max(0.0, (1-W)*p + W*(l52*yoy))
                elif arm == "plus_STL":
                    p = max(0.0, p * max(0.1, 1.0 + stl.get(woy, 0.0)))
                preds.append(p); hist.append(p)
            out[band][arm].append((act[:len(preds)], preds))
    res = {}
    for band, arms in out.items():
        res[band] = {}
        for arm, rows in arms.items():
            if not rows: continue
            a = np.concatenate([np.asarray(x[0]) for x in rows])
            p = np.concatenate([np.asarray(x[1]) for x in rows])
            res[band][arm] = {"wmape": wmape(a, p), "n_series": len(rows)}
    return res


def main(backs):
    model, feats, stl, df = prep()
    end = df["__time"].max()
    print(f"panel ends {end.date()} | horizon {H} wks | cutoffs {backs} weeks back\n")
    allres = {}
    for b in backs:
        cut = end - pd.Timedelta(weeks=b)
        r = run_cutoff(model, feats, stl, df, cut)
        allres[str(cut.date())] = r
        y = r.get("yago", {}); ny = r.get("no_yago", {})
        sm = np.mean([1 + stl.get(int((cut + pd.Timedelta(weeks=k)).isocalendar().week), 0)
                      for k in range(1, H+1)])
        print(f"cutoff {cut.date()}  (mean STL multiplier over horizon x{sm:.3f})")
        if y:
            swap = y.get("plus_YAGO", {}).get("wmape", float('nan')) - y.get("plus_STL", {}).get("wmape", float('nan'))
            print(f"   YAGO band  n={y.get('pure_AR',{}).get('n_series',0):3d}  "
                  f"pureAR {y.get('pure_AR',{}).get('wmape',float('nan')):6.2f}  "
                  f"+STL {y.get('plus_STL',{}).get('wmape',float('nan')):6.2f}  "
                  f"+YAGO {y.get('plus_YAGO',{}).get('wmape',float('nan')):6.2f}   "
                  f"STL beats YAGO by {swap:+6.2f}pp  {'YES' if swap > 0 else 'NO'}")
        if ny:
            print(f"   no-YAGO    n={ny.get('pure_AR',{}).get('n_series',0):3d}  "
                  f"pureAR {ny.get('pure_AR',{}).get('wmape',float('nan')):6.2f}  "
                  f"+STL {ny.get('plus_STL',{}).get('wmape',float('nan')):6.2f}")
        print()
    wins = [1 for r in allres.values()
            if "yago" in r and r["yago"].get("plus_STL", {}).get("wmape", 9e9) < r["yago"].get("plus_YAGO", {}).get("wmape", -1)]
    print(f"VERDICT: STL beats YAGO at {len(wins)} of {len(allres)} cutoffs")
    print("  -> SWAP JUSTIFIED" if len(wins) == len(allres) else
          "  -> NOT justified at every cutoff; the single-window result does not generalise")
    OUT.write_text(json.dumps(allres, indent=2)); print(f"\n  → {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backs", type=int, nargs="+", default=[13, 26, 39, 52])
    main(ap.parse_args().backs)
