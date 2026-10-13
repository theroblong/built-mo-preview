#!/usr/bin/env python
"""MO_146 - Do neural forecasting models (N-HiTS, TCN, TFT) beat the 5-seed fixed direct model on the honest bench?

PLAIN WORDS: the production candidate is LightGBM-based (the fixed direct model trained five times and averaged).
This tests three neural "global" models -- one network trained on all item x retailer series at once, as is
standard for neural forecasting -- on the same 18 forecast dates, the same series and the same scoring:
  N-HiTS: stacks of simple layers that look at the series at several time scales (fast, often strong);
  TCN:    a convolutional network over the recent weeks;
  TFT:    an attention-based network (heavier, interpretable attention weights).
Each is trained 5 times with different random seeds and averaged, like the direct model. Also tested: the average
of the three neural models, and a 50/50 blend of the direct model with that neural average.

WHERE THIS CAME FROM: roadmap (Jason, 2026-10-12/13): neural models after the LightGBM inputs are settled, with a
timing test first; MO_145 (2026-10-13) showed all three train in seconds on the worker GPU with <1 GB memory.

PRIOR WORK (docs/SETTLED_FINDINGS.md, README, memory):
  - MO_38 / MO_66 (README ~3405, ~4657): TFT / N-BEATS / Chronos-2 attempts failed on the laptop (torch/torchvision
    conflict); one TFT evaluation on the pre-fix bench (README ~9543) is PROVISIONAL. The worker image now has
    neuralforecast 3.1.9 -> this is the first neural test on the corrected bench.
  - memory 2026-10 roadmap: "TFT/RNN deprioritised on data scale (~260 long series, <3 yrs)" -- expected handicap.
  - SETTLED: "flat beats ~20 approaches on continuing series" (growth is distribution, MO_90 era) and the
    5-seed fixed direct model is the current best (MO_133..MO_140 all failed to beat it under Amendment 1).
  - MO_145 (timing only): none found on accuracy.

ARMS (all scored against the production reference direct_avg5 = MO_133's 5-seed fixed direct model, from
scripts/outputs/mo140_rows.parquet; new and lapsed series are 0 in every arm, as in the harness):
  direct_avg5  production reference (status quo for the rule)
  nhits5, tcn5, tft5   each neural model, 5 seeds averaged
  neural_avg   mean of the three neural arms
  dir_neural   0.5 x direct_avg5 + 0.5 x neural_avg
Neural setup: target = weekly base units per series (same as the harness), series = M.GROUP_COLS joined; training
data strictly up to each forecast date; each series padded with zeros to a regular weekly grid ending at the
forecast date (so all forecasts start the week after it); horizon 13, input window 26 weeks, short series padded
at the start (start_padding_enabled); robust per-series scaling; MAE loss; 1,000 training steps; seeds 1..5.
LEVELS: cell x week, account x month, portfolio x month (+ within history bands), bias; BY HISTORY BAND
(<13 / 13-25 / 26-51 / 52+ wks); with and without Walmart; recent (2025-12+), all 18, 2025; Amendment 1 criteria.

PREDICTIONS, RECORDED BEFORE RUNNING so they can be wrong:
  P1 neural_avg is worse than direct_avg5 at recent account x month (data are small for deep models).
     (fails -> neural models are a real challenger; run the full rule and save them forward)
  P2 dir_neural is within +/-1.0 point of direct_avg5 at recent account x month.
     (fails downward -> the blend helps; fails upward -> neural errors are large enough to hurt a blend)
  P3 Every neural arm's recent portfolio bias is within 0.85-1.15.
  P4 N-HiTS is at least as accurate as TFT at recent account x month (simpler beats heavier on small data).
  P5 Parity: direct_avg5's recent account x month reproduces MO_140's 16.17 exactly (same rows, same scoring).
Usage:
  worker:  python MO_146_neural_backtest.py compute --origins 2024-12,2025-03 [--seeds 1,2,3,4,5 --steps 1000]
  laptop:  python MO_146_neural_backtest.py score --results <dir1,dir2,dir3>
Outputs: compute -> $AEVAH_RESULTS_DIR/mo146_<model>_s<seed>_<origin>.parquet; score -> outputs/mo146_neural.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]   # = mo_panel.GROUP_COLS (asserted in score)
H, INPUT = 13, 26
MODELS = ("NHITS", "TCN", "TFT")
ARM_OF = {"NHITS": "nhits5", "TCN": "tcn5", "TFT": "tft5"}
RECENT = "2025-12"


# ---------------------------------------------------------------- compute (worker GPU; no harness import needed)
def origin_cuts() -> dict[str, pd.Timestamp]:
    """Same dates as MO_80.ORIGINS_MONTHLY: last Sunday of each month, Dec 2024 .. May 2026 (asserted in score)."""
    out = {}
    for me in pd.date_range("2024-12-01", "2026-05-31", freq="ME"):
        cut = me - pd.Timedelta(days=(me.dayofweek + 1) % 7)
        out[cut.strftime("%Y-%m")] = cut
    return out


def training_frame(panel: pd.DataFrame, universe: set, cut: pd.Timestamp) -> pd.DataFrame:
    p = panel[panel.ds <= cut]
    p = p[p.unique_id.isin(universe)]
    p = p.groupby(["unique_id", "ds"], as_index=False).y.sum()
    first = p[p.y > 0].groupby("unique_id").ds.min()
    out = []
    for uid, g in p[p.unique_id.isin(first.index)].groupby("unique_id"):
        idx = pd.date_range(first[uid], cut, freq="W-SUN")
        s = g.set_index("ds").y.reindex(idx).fillna(0.0)
        out.append(pd.DataFrame({"unique_id": uid, "ds": idx, "y": s.values.astype("float32")}))
    return pd.concat(out, ignore_index=True)


def compute(origins: list[str], seeds: list[int], steps: int) -> None:
    import torch
    from neuralforecast import NeuralForecast
    from neuralforecast.models import NHITS, TCN, TFT
    data = Path(os.environ["AEVAH_DATASET_DIR"])
    out = Path(os.environ["AEVAH_RESULTS_DIR"])
    t0 = time.time()
    panel = pd.read_parquet(data / "retailer_sales_weekly.parquet", columns=GROUP_COLS + ["__time", "base_units"])
    panel["ds"] = pd.to_datetime(panel["__time"]).dt.tz_localize(None)
    panel["unique_id"] = panel[GROUP_COLS].astype(str).agg(" | ".join, axis=1)
    panel["y"] = panel.base_units.fillna(0).clip(lower=0)
    universe = set(pd.read_parquet(data / "series_universe.parquet").series)
    gpu = torch.cuda.is_available()
    tk = dict(accelerator="gpu" if gpu else "cpu", devices=1, enable_checkpointing=False, logger=False,
              enable_progress_bar=False, default_root_dir=os.environ.get("TMPDIR", "/tmp"))
    make = {"NHITS": lambda s: NHITS(h=H, input_size=INPUT, max_steps=steps, scaler_type="robust", random_seed=s,
                                     start_padding_enabled=True, **tk),
            "TCN": lambda s: TCN(h=H, input_size=INPUT, max_steps=steps, scaler_type="robust", random_seed=s,
                                 start_padding_enabled=True, **tk),
            "TFT": lambda s: TFT(h=H, input_size=INPUT, hidden_size=64, max_steps=steps, scaler_type="robust",
                                 random_seed=s, start_padding_enabled=True, **tk)}
    cuts = origin_cuts()
    timing = {"gpu": torch.cuda.get_device_name(0) if gpu else None, "steps": steps, "seeds": seeds, "origins": {}}
    for o in origins:
        cut = cuts[o]
        df = training_frame(panel, universe, cut)
        timing["origins"][o] = {"series": int(df.unique_id.nunique()), "rows": int(len(df)), "fits": {}}
        for name in MODELS:
            for s in seeds:
                f = out / f"mo146_{name}_s{s}_{o}.parquet"
                if f.exists():                       # resume after an interruption
                    continue
                t = time.time()
                nf = NeuralForecast(models=[make[name](s)], freq="W-SUN")
                nf.fit(df=df)
                fc = nf.predict().reset_index()
                col = [c for c in fc.columns if c not in ("index", "unique_id", "ds")][0]
                fc = fc.rename(columns={"unique_id": "series", "ds": "date", col: "value"})[["series", "date", "value"]]
                fc["value"] = fc.value.clip(lower=0).astype(float)
                fc.to_parquet(f)
                timing["origins"][o]["fits"][f"{name}_s{s}"] = round(time.time() - t, 1)
                print(o, name, s, round(time.time() - t, 1), "s", flush=True)
        (out / f"mo146_timing_{'_'.join(origins)}.json").write_text(json.dumps(timing, indent=2))
    print("done", round(time.time() - t0, 1), "s", flush=True)


# ---------------------------------------------------------------- score (laptop; honest harness)
def score(dirs: list[str], seeds: list[int]) -> None:
    import importlib
    os.environ["MO_SEASONAL_MODE"] = "step"               # same harness settings as MO_133..MO_140
    import MO_80_quarterly_honest_backtest as M          # import asserts forecast + training parity
    importlib.reload(M)
    assert M.SEASONAL_MODE == "step" and M.FEATURE_REFRESH == "freeze", "harness must match MO_27"
    import MO_133_ensembles as E                          # band-separated portfolio diff
    import MO_134_recursive_fair_settings as B            # seasonal bias by year
    import MO_136_signals as S                            # sign test
    assert list(M.GROUP_COLS) == GROUP_COLS
    assert {lbl: M._utc(c) for lbl, c, *_ in M.ORIGINS_MONTHLY} == {k: M._utc(v) for k, v in origin_cuts().items()}
    r = pd.read_parquet("outputs/mo140_rows.parquet")
    r["date"] = pd.to_datetime(r["date"], utc=True)
    zero = (r["is_new"] | (r["band"] == "lapsed")).values
    for name in MODELS:
        parts = []
        for s in seeds:
            fs = [f for d in dirs for f in Path(d).glob(f"mo146_{name}_s{s}_*.parquet")]
            x = pd.concat([pd.read_parquet(f).assign(origin=f.stem.rsplit("_", 1)[1]) for f in fs], ignore_index=True)
            x["date"] = pd.to_datetime(x["date"]).dt.tz_localize("UTC")
            parts.append(x.rename(columns={"value": f"{name}_s{s}"}).set_index(["origin", "series", "date"]))
        m = pd.concat(parts, axis=1).reset_index()
        r = r.merge(m, on=["origin", "series", "date"], how="left")
        cols = [f"{name}_s{s}" for s in seeds]
        r[ARM_OF[name]] = r[cols].mean(axis=1)
        miss = r[ARM_OF[name]].isna().values & ~zero
        print(f"  {name}: origins {m.origin.nunique()}, seeds {len(seeds)}, fell back to flat {int(miss.sum()):,}")
        r[ARM_OF[name]] = np.where(zero, 0.0, np.where(miss, r["flat"], r[ARM_OF[name]]))
    r["neural_avg"] = r[["nhits5", "tcn5", "tft5"]].mean(axis=1)
    r["dir_neural"] = 0.5 * r["direct_avg5"] + 0.5 * r["neural_avg"]
    arms = ["direct_avg5", "nhits5", "tcn5", "tft5", "neural_avg", "dir_neural"]
    r[["origin", "series", "date", "actual", "account", "band", "is_new", "wmt"] + arms].to_parquet("outputs/mo146_rows.parquet")
    ex = r[~r["is_new"]]
    res = {"arms": arms}
    CW, AM, PM = "cell x week", "account x month", "portfolio x month"
    for scope, sub0 in (("with Walmart", ex), ("without Walmart", ex[~ex["wmt"]])):
        res[scope] = {}
        for nm, sub in (("recent", sub0[sub0.origin >= RECENT]), ("all", sub0), ("2025", sub0[sub0.origin < RECENT])):
            Sx = M.score_levels(sub, arms)
            res[scope][nm] = Sx
            print(f"\n=== {scope.upper()}, {nm.upper()} origins, existing series: cw / am / pm | bias ===")
            for x in arms:
                print(f"  {x:<12s}{Sx[CW][x]:7.2f}{Sx[AM][x]:7.2f}{Sx[PM][x]:7.2f}   bias {Sx['portfolio_bias'][x]:.3f}")
            if scope == "with Walmart":
                for lvl, _ in M.LEVELS_V2:
                    print(f"  BY HISTORY BAND, {lvl} (<13 / 13-25 / 26-51 / 52+ wks)")
                    for b, v in Sx[lvl]["by_band"].items():
                        print(f"    {b:<10s} n={v['n']:>7,}  " + "  ".join(f"{x}={v[x]:.1f}" for x in arms))
    print("\nPER-ORIGIN account x month, recent (candidate - direct_avg5; negative = better)")
    res["per_origin"] = {}
    for scope, sub0 in (("with Walmart", ex), ("without Walmart", ex[~ex["wmt"]])):
        rec = sub0[sub0.origin >= RECENT]
        per = {o: M.score_levels(g, arms)[AM] for o, g in rec.groupby("origin")}
        for y in arms[1:]:
            diffs = {o: round(v[y] - v["direct_avg5"], 2) for o, v in per.items()}
            wins = sum(d < 0 for d in diffs.values())
            pb = E.band_separated_diff(rec, y, "direct_avg5")["diff"]
            res["per_origin"][f"{scope}: {y}"] = {"diffs": diffs, "wins": wins, "sign_p": S.sign_test(wins, len(diffs)),
                                                  "pm_by_band": pb}
            print(f"  [{scope}] {y:<11s} wins {wins}/{len(diffs)}  pm-by-band {pb:+.2f}  "
                  + " ".join(f"{o}:{d:+.2f}" for o, d in diffs.items()))
    res["season_bias"] = B.season_bias(ex, arms)
    print("\nSEASONAL BIAS (forecast / actual):")
    for k, v in res["season_bias"].items():
        print(f"  {k}: " + "  ".join(f"{a}={v[a]:.3f}" for a in arms))
    # Amendment 1 check for each candidate vs direct_avg5
    R, R25 = res["with Walmart"]["recent"], res["with Walmart"]["2025"]
    rule = {}
    for y in arms[1:]:
        po = res["per_origin"][f"with Walmart: {y}"]
        c1 = (R[AM][y] < R[AM]["direct_avg5"] and po["pm_by_band"] < 0 and R[CW][y] <= R[CW]["direct_avg5"])
        c2 = po["wins"] >= 5
        c3 = R25[AM][y] <= R25[AM]["direct_avg5"] + 2.0
        c4 = all(abs(v[y] - 1) <= 0.10 or abs(v[y] - 1) <= abs(v["direct_avg5"] - 1) for v in res["season_bias"].values())
        rule[y] = {"1 recent accuracy": bool(c1), "2 consistency >=5/6": bool(c2), "3 2025 no-harm": bool(c3),
                   "4 seasonal bias": bool(c4), "passes backtest part": bool(c1 and c2 and c3 and c4)}
    res["amendment1"] = rule
    print("\nAMENDMENT 1 (backtest part; forward confirmation still required):")
    for y, v in rule.items():
        print(f"  {y:<11s} " + "  ".join(f"{k}={'Y' if b else 'n'}" for k, b in v.items()))
    preds = {
        "P1": {"neural_avg": R[AM]["neural_avg"], "direct_avg5": R[AM]["direct_avg5"],
               "holds": bool(R[AM]["neural_avg"] > R[AM]["direct_avg5"])},
        "P2": {"dir_neural": R[AM]["dir_neural"], "direct_avg5": R[AM]["direct_avg5"],
               "holds": bool(abs(R[AM]["dir_neural"] - R[AM]["direct_avg5"]) <= 1.0)},
        "P3": {a: R["portfolio_bias"][a] for a in ("nhits5", "tcn5", "tft5", "neural_avg")},
        "P4": {"nhits5": R[AM]["nhits5"], "tft5": R[AM]["tft5"], "holds": bool(R[AM]["nhits5"] <= R[AM]["tft5"])},
        "P5": {"direct_avg5_recent_am": R[AM]["direct_avg5"], "holds": bool(round(R[AM]["direct_avg5"], 2) == 16.17)},
    }
    preds["P3"]["holds"] = bool(all(0.85 <= v <= 1.15 for k, v in preds["P3"].items() if k != "holds"))
    res["predictions"] = preds
    Path("../outputs/mo146_neural.json").write_text(json.dumps(res, indent=2, default=float))
    print()
    for k, v in preds.items():
        print(k, "HOLDS" if v["holds"] else "FAILS", {kk: (round(vv, 3) if isinstance(vv, float) else vv)
                                                    for kk, vv in v.items() if kk != "holds"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["compute", "score", "prep-check"])
    ap.add_argument("--origins", default="")
    ap.add_argument("--seeds", default="1,2,3,4,5")
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--results", default="")
    a = ap.parse_args()
    seeds = [int(x) for x in a.seeds.split(",")]
    if a.cmd == "compute":
        compute(a.origins.split(","), seeds, a.steps)
    elif a.cmd == "score":
        score(a.results.split(","), seeds)
    else:   # laptop check of the training frames (no neural library needed)
        data = Path(os.environ.get("AEVAH_DATASET_DIR", "."))
        panel = pd.read_parquet(data / "retailer_sales_weekly.parquet", columns=GROUP_COLS + ["__time", "base_units"])
        panel["ds"] = pd.to_datetime(panel["__time"]).dt.tz_localize(None)
        panel["unique_id"] = panel[GROUP_COLS].astype(str).agg(" | ".join, axis=1)
        panel["y"] = panel.base_units.fillna(0).clip(lower=0)
        universe = set(pd.read_parquet(data / "series_universe.parquet").series)
        for o in a.origins.split(","):
            t = time.time()
            df = training_frame(panel, universe, origin_cuts()[o])
            print(o, "series", df.unique_id.nunique(), "rows", len(df), "last ds", df.ds.max().date(),
                  f"{time.time() - t:.1f}s")


if __name__ == "__main__":
    main()
