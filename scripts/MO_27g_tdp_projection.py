"""MO_27g — Project TDP forward in the recursive loop. The actual fix.

DIAGNOSIS SO FAR
  * The recursive forecast collapses to last_actual x 1.03 by step 3 (SD ratio 0.062).
  * 31 of 56 features are FROZEN across the horizon, including every TDP/velocity feature.
  * The lifecycle ramp is TDP-driven: TDP climbs 1.01 -> 1.69 over a series' first 60 weeks
    while demand doubles. TDP is pinned to a constant, so the model CANNOT produce a ramp.
  * The forecast runs 7.9% HIGH (pooled bias 1.079), and both seasonal knobs (STL multiplier,
    YAGO blend) have been acting as accidental bias correctors rather than seasonality.

So the model has the right features — tdp is #8 and velocity_per_tdp #15 by gain — and the loop
simply never moves them. This projects TDP forward instead of freezing it, which is the fix
Jason proposed early ("most recent week's demand adjusted for any additional TDP expansion").

WHAT MOVES, AND WHY
  tdp              projected at a capped weekly growth rate estimated from recent actuals
  tdp_wow_delta    recomputed from the projected path, so it stays internally consistent
  tdp_4w_momentum  set to the projected 4-week momentum
  velocity_per_tdp DELIBERATELY HELD at its last observed value. It is units-per-TDP-point, a
                   per-store rate; holding it while TDP rises is exactly the signal "more doors,
                   same velocity", which is what should drive incremental units. Moving it too
                   would double-count.
  tdp_z8, tdp_lag52, velocity_spm_* stay frozen — they need rolling history the loop lacks.

CAP SWEEP: 0 (frozen, = production) through 1.0%/week. A cap is essential because forward TDP is
itself a forecast; an uncapped extrapolation of a steep recent ramp would inject large error. The
sweep shows whether there is a cap that helps without over-reaching.

Reports wMAPE, bias (sum pred / sum act) and the flattening ratio, so we can see whether the
forecast stops being a flat line, not just whether the error moves.

Run:  python MO_27g_tdp_projection.py [--caps 0 0.0025 0.005 0.01] [--backs 13 26 39 52]
"""
from __future__ import annotations
import argparse, importlib.util, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

_e = importlib.util.spec_from_file_location("e", str(Path(__file__).parent / "MO_27e_multicutoff_verify.py"))
E = importlib.util.module_from_spec(_e); _e.loader.exec_module(E)
H, W_BLEND, OUT = 13, 0.10, Path("outputs/mo27g_tdp_projection.json")
LOOKBACK = 13          # weeks of actual TDP used to estimate the growth rate


def tdp_growth(tdp_hist, lookback=LOOKBACK):
    """Mean weekly log-growth of TDP over the lookback, or 0 if not estimable."""
    s = [v for v in tdp_hist[-lookback:] if v is not None and np.isfinite(v) and v > 0]
    if len(s) < 4: return 0.0
    g = (np.log(s[-1]) - np.log(s[0])) / (len(s) - 1)
    return float(g) if np.isfinite(g) else 0.0


def main(caps, backs):
    model, feats, stl, df = E.prep()
    end = df["__time"].max()
    print(f"panel ends {end.date()} | horizon {H} | caps {caps} | blend W={W_BLEND}\n")
    grid = {c: {} for c in caps}

    for back in backs:
        cut = end - pd.Timedelta(weeks=back)
        acc = {c: {b: {"pred": 0., "act": 0., "abs": 0., "flat": []} for b in ("no_yago", "yago")} for c in caps}
        n = {"no_yago": 0, "yago": 0}
        for keys, g in df.groupby(E.GROUP_COLS, observed=True):
            g = g.sort_values("__time")
            seed = g[g["__time"] <= cut]; fut = g[g["__time"] > cut].head(H)
            if len(seed) < 13 or len(fut) < 6: continue
            band = "yago" if len(seed) >= 52 else "no_yago"; n[band] += 1
            latest = seed.iloc[-1]
            hist0 = seed["base_units"].astype(float).tolist(); N = len(hist0)
            tdp_hist = pd.to_numeric(seed["tdp"], errors="coerce").tolist()
            tdp0 = float(tdp_hist[-1]) if tdp_hist and np.isfinite(tdp_hist[-1]) else 0.0
            graw = tdp_growth(tdp_hist)
            lag52 = [float(hist0[N-53+k]) if 0 <= (N-53+k) < N else np.nan for k in range(1, len(fut)+1)]
            ya = float(hist0[N-52]) if N >= 52 else None
            yoy = float(np.clip(hist0[-1]/ya, 0.5, 2.0)) if (ya and ya > 0) else None
            static = {c: float(pd.to_numeric(latest.get(c), errors="coerce") or 0)
                      for c in feats if c not in E.SKIP}
            cats = {c: E.mo27._cat_str(latest.get(c), "UNKNOWN") for c in E.CAT_COLS if c in feats}
            arp = float(pd.to_numeric(latest.get("arp"), errors="coerce") or 0)
            wsl = int(pd.to_numeric(latest.get("weeks_since_launch"), errors="coerce") or 0)
            act = fut["base_units"].astype(float).tolist()

            for cap in caps:
                gr = float(np.clip(graw, -cap, cap)) if cap > 0 else 0.0
                hist = list(hist0); preds = []; prev_tdp = tdp0
                for step in range(1, len(fut)+1):
                    woy = int((cut + pd.Timedelta(weeks=step)).isocalendar().week)
                    tdp_t = tdp0 * float(np.exp(gr * step)) if (cap > 0 and tdp0 > 0) else tdp0
                    st = {**static, **cats,
                          "week_sin": np.sin(2*np.pi*woy/52), "week_cos": np.cos(2*np.pi*woy/52),
                          "week_sin26": np.sin(2*np.pi*woy/26), "week_cos26": np.cos(2*np.pi*woy/26),
                          "weeks_since_launch": wsl+step, "arp": arp, "arp_lag1": arp,
                          "arp_wow_delta": 0., "arp_roll8_avg": arp, "arp_roll8_std": 0.,
                          "is_promo_week": 0., "promo_intensity": 0., "units_lift_tpr": 0.,
                          "units_lift_any_display": 0., "units_lift_any_feature": 0.,
                          "promo_52w_lag": 0., "promo_rate_woy": 0.,
                          "base_units_lag1": hist[-1],
                          "base_units_lag4": hist[-4] if len(hist) >= 4 else np.nan,
                          "base_units_lag13": hist[-13] if len(hist) >= 13 else np.nan,
                          "base_units_lag52": lag52[step-1] if band == "yago" else np.nan}
                    if cap > 0 and tdp0 > 0:
                        st["tdp"] = tdp_t
                        st["tdp_wow_delta"] = tdp_t - prev_tdp
                        st["tdp_4w_momentum"] = float(np.exp(gr*4) - 1.0)
                    p = float(max(0., np.expm1(model.predict(E.mo27._build_feature_row(st, feats, model=model))[0])))
                    if band == "yago" and yoy is not None and np.isfinite(lag52[step-1]) and lag52[step-1] > 0 and p > 0:
                        p = max(0., (1-W_BLEND)*p + W_BLEND*(lag52[step-1]*yoy))
                    preds.append(p); hist.append(p); prev_tdp = tdp_t
                a = acc[cap][band]
                for i, pv in enumerate(preds):
                    av = act[i] if i < len(act) else 0.
                    a["pred"] += pv; a["act"] += av; a["abs"] += abs(av - pv)
                sa = np.std(act[:len(preds)])
                if sa > 0: a["flat"].append(np.std(preds)/sa)

        print(f"cutoff {cut.date()}   (no-YAGO n={n['no_yago']}, YAGO n={n['yago']})")
        print(f"   {'cap/wk':>8s} {'band':>9s} {'wMAPE':>8s} {'bias':>7s} {'flatten':>8s}")
        for cap in caps:
            for band in ("no_yago", "yago"):
                a = acc[cap][band]
                if a["act"] <= 0: continue
                wm, bi = a["abs"]/a["act"]*100, a["pred"]/a["act"]
                fl = float(np.median(a["flat"])) if a["flat"] else float("nan")
                grid[cap].setdefault(str(cut.date()), {})[band] = {"wmape": wm, "bias": bi, "flatten": fl}
                print(f"   {cap*100:>7.2f}% {band:>9s} {wm:>8.2f} {bi:>7.3f} {fl:>8.3f}")
        print()

    print("POOLED ACROSS CUTOFFS")
    print(f"   {'cap/wk':>8s} {'band':>9s} {'wMAPE':>8s} {'bias':>7s}")
    pooled = {}
    for cap in caps:
        for band in ("no_yago", "yago"):
            ws = [v[band]["wmape"] for v in grid[cap].values() if band in v]
            bs = [v[band]["bias"] for v in grid[cap].values() if band in v]
            if not ws: continue
            pooled[(cap, band)] = (float(np.mean(ws)), float(np.mean(bs)))
            print(f"   {cap*100:>7.2f}% {band:>9s} {np.mean(ws):>8.2f} {np.mean(bs):>7.3f}")
    for band in ("no_yago", "yago"):
        cand = {c: v for (c, b), v in pooled.items() if b == band}
        if not cand: continue
        best = min(cand, key=lambda c: cand[c][0]); base = cand.get(0.0, (float('nan'),))[0]
        print(f"\n   {band}: best cap {best*100:.2f}%/wk -> {cand[best][0]:.2f} wMAPE "
              f"(frozen = {base:.2f}, delta {cand[best][0]-base:+.2f}pp)")
    OUT.write_text(json.dumps({str(k): v for k, v in grid.items()}, indent=2, default=float))
    print(f"\n  → {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--caps", type=float, nargs="+", default=[0.0, 0.0025, 0.005, 0.01])
    ap.add_argument("--backs", type=int, nargs="+", default=[13, 26, 39, 52])
    a = ap.parse_args(); main(a.caps, a.backs)
