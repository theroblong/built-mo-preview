"""MO_27f — What should SEASONAL_BLEND_WEIGHT be? (and is the forecast biased?)

MO_27e settled two things and opened one.

SETTLED — swapping the YAGO blend for the STL multiplier is NOT justified: STL wins at 3 of 4
cutoffs but fails badly at 2026-03-08 (40.35 vs 33.65). Its apparent benefit tracks whether the
multiplier DEFLATES or INFLATES, not whether it captures season, which is the signature of a
level correction rather than a seasonal one.

SETTLED — turning the blend OFF beats production at 3 of 4 cutoffs (+8.84, +9.33, +1.14, -1.12;
mean +4.55pp). So W=0.40 is too strong. Consistent with the yoy_ratio clamp [0.5, 2.0] binding
on 57% of series (17% at the 2.0 ceiling with median TRUE growth 5.6x; 40% at the 0.5 floor).

OPEN — the right W is a parameter, not a binary. This sweeps it across every cutoff.

Also reports BIAS (sum predicted / sum actual) per arm. If the forecast is systematically high,
then any downward adjustment flatters it and any upward one hurts, which would explain the whole
STL pattern without seasonality being involved at all. The median mature series declines 34%
year-over-year while the recursive forecast predicts +3%, so a high bias is the live hypothesis.

Run:  python MO_27f_blend_weight_sweep.py [--weights 0 0.1 0.2 0.3 0.4]
"""
from __future__ import annotations
import argparse, importlib.util, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

_e = importlib.util.spec_from_file_location("e", str(Path(__file__).parent / "MO_27e_multicutoff_verify.py"))
E = importlib.util.module_from_spec(_e); _e.loader.exec_module(E)
H, OUT = 13, Path("outputs/mo27f_blend_weight_sweep.json")


def main(weights, backs):
    model, feats, stl, df = E.prep()
    end = df["__time"].max()
    print(f"panel ends {end.date()} | horizon {H} | weights {weights} | cutoffs {backs}\n")
    grid = {w: {"pred": 0.0, "act": 0.0, "abs": 0.0, "per_cut": {}} for w in weights}

    for back in backs:
        cut = end - pd.Timedelta(weeks=back)
        per = {w: {"pred": 0.0, "act": 0.0, "abs": 0.0} for w in weights}
        n = 0
        for keys, g in df.groupby(E.GROUP_COLS, observed=True):
            g = g.sort_values("__time")
            seed = g[g["__time"] <= cut]; fut = g[g["__time"] > cut].head(H)
            if len(seed) < 52 or len(fut) < 6: continue     # YAGO band only — W only acts here
            n += 1
            latest = seed.iloc[-1]; hist0 = seed["base_units"].astype(float).tolist(); N = len(hist0)
            lag52 = [float(hist0[N-53+k]) if 0 <= (N-53+k) < N else np.nan for k in range(1, len(fut)+1)]
            ya = float(hist0[N-52]) if N >= 52 else None
            yoy = float(np.clip(hist0[-1]/ya, 0.5, 2.0)) if (ya and ya > 0) else None
            static = {c: float(pd.to_numeric(latest.get(c), errors="coerce") or 0)
                      for c in feats if c not in E.SKIP}
            cats = {c: E.mo27._cat_str(latest.get(c), "UNKNOWN") for c in E.CAT_COLS if c in feats}
            arp = float(pd.to_numeric(latest.get("arp"), errors="coerce") or 0)
            wsl = int(pd.to_numeric(latest.get("weeks_since_launch"), errors="coerce") or 0)
            act = fut["base_units"].astype(float).tolist()

            # base (unblended) predictions once; the blend is a post-hoc mix so one pass suffices
            hist = list(hist0); base = []
            for step in range(1, len(fut)+1):
                woy = int((cut + pd.Timedelta(weeks=step)).isocalendar().week)
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
                      "base_units_lag52": lag52[step-1]}
                p = float(max(0.0, np.expm1(model.predict(E.mo27._build_feature_row(st, feats, model=model))[0])))
                base.append(p); hist.append(p)
            # NOTE: the AR feed uses the UNBLENDED path. Production feeds the blended value
            # back as the next lag, so this isolates the blend's direct effect and slightly
            # understates compounding. Stated rather than hidden.
            for w in weights:
                for i, p in enumerate(base):
                    l = lag52[i]
                    q = ((1-w)*p + w*(l*yoy)) if (w > 0 and yoy is not None and np.isfinite(l) and l > 0) else p
                    q = max(0.0, q)
                    per[w]["pred"] += q; per[w]["act"] += act[i] if i < len(act) else 0
                    per[w]["abs"] += abs((act[i] if i < len(act) else 0) - q)

        print(f"cutoff {cut.date()}  (n={n})")
        print(f"   {'W':>5s} {'wMAPE':>8s} {'bias pred/act':>14s}")
        for w in weights:
            d = per[w]; wm = d["abs"]/d["act"]*100 if d["act"] else float('nan')
            bias = d["pred"]/d["act"] if d["act"] else float('nan')
            print(f"   {w:>5.2f} {wm:>8.2f} {bias:>14.3f}")
            grid[w]["per_cut"][str(cut.date())] = {"wmape": wm, "bias": bias, "n": n}
            for k in ("pred","act","abs"): grid[w][k] += d[k]
        print()

    print("POOLED ACROSS ALL CUTOFFS")
    print(f"   {'W':>5s} {'wMAPE':>8s} {'bias pred/act':>14s}  {'wins':>5s}")
    best = None
    for w in weights:
        d = grid[w]; wm = d["abs"]/d["act"]*100; bias = d["pred"]/d["act"]
        wins = sum(1 for c, v in grid[w]["per_cut"].items()
                   if v["wmape"] == min(grid[x]["per_cut"][c]["wmape"] for x in weights))
        grid[w]["pooled"] = {"wmape": wm, "bias": bias, "cutoff_wins": wins}
        print(f"   {w:>5.2f} {wm:>8.2f} {bias:>14.3f}  {wins:>5d}")
        if best is None or wm < grid[best]["pooled"]["wmape"]: best = w
    print(f"\n   best pooled W = {best}  (production is 0.40)")
    b = grid[best]["pooled"]["bias"]
    print(f"   bias at that W = {b:.3f} -> forecast runs "
          f"{'HIGH' if b > 1.02 else 'LOW' if b < 0.98 else 'roughly unbiased'}")
    if b > 1.02:
        print("   A high bias explains the STL pattern without seasonality: any DEFLATING")
        print("   multiplier helps and any INFLATING one hurts, regardless of season.")
    OUT.write_text(json.dumps({str(k): v for k, v in grid.items()}, indent=2, default=float))
    print(f"\n  → {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=float, nargs="+", default=[0.0, 0.1, 0.2, 0.3, 0.4])
    ap.add_argument("--backs", type=int, nargs="+", default=[13, 26, 39, 52])
    a = ap.parse_args(); main(a.weights, a.backs)
