#!/usr/bin/env python
"""MO_145 - neural forecasting timing test (one forecast date) on the RunPod GPU worker.

PLAIN WORDS: before paying for a full neural-model backtest (TFT, N-HiTS, TCN on all 18 forecast dates), measure
how long these models take to train on our data, how much GPU memory they use, and that they run at all in the
worker image (neuralforecast 3.1.9, PyTorch 2.6.0+cu124). This is NOT an accuracy test: each model trains for a
short fixed number of steps, and only speed, memory and output shape are recorded. The full test's cost is then
projected from this job's RunPod-billed cost (labeled Estimate).

Data: the same panel as the main harness (retailer_sales_weekly.parquet, the MO_140 dataset). One series = item x
channel x account x geography (mo_panel.GROUP_COLS); target = base_units; weekly, weeks ending Sunday. Forecast date
2025-01-01: training data strictly before it; series need at least 26 weeks of history; gaps inside a series are
filled with 0 so every series is a regular weekly sequence (neuralforecast requires that).
Models (horizon 13 weeks, 26-week input window, STEPS training steps each, MAE loss, default sizes otherwise):
  NHITS, TCN, TFT (hidden_size 64). Each model is timed separately; results are written after each model, and no
  new model starts once BUDGET_S seconds have passed, so the job ends well inside its 5-minute limit.
Outputs ($AEVAH_RESULTS_DIR): mo145_timing.json (per model: fit seconds, seconds per step, predict seconds, peak
GPU memory, forecasts produced), mo145_<model>_forecast.parquet.
Usage: python MO_145_neural_timing.py [--steps 200] [--budget 200] [--prep-only --panel PATH]

PREDICTIONS (written 2026-10-13, before any run; timing, not accuracy):
  P1 All three models train and forecast without error on the worker GPU.
  P2 NHITS and TCN each finish 200 steps in under 60 s; TFT in under 120 s.
  P3 Peak GPU memory stays under 8 GB for every model (the card has 24 GB).
"""
from __future__ import annotations

# protocol: not-a-forecast-arm (timing/feasibility test; no accuracy is scored)
import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]   # mo_panel.GROUP_COLS
ORIGIN = pd.Timestamp("2025-01-01")
H, INPUT = 13, 26
T0 = time.time()


def prep(panel_path: str) -> pd.DataFrame:
    p = pd.read_parquet(panel_path, columns=GROUP_COLS + ["__time", "base_units"])
    p["ds"] = pd.to_datetime(p["__time"]).dt.tz_localize(None)
    p = p[p.ds < ORIGIN]
    p["unique_id"] = p[GROUP_COLS].astype(str).agg("|".join, axis=1)
    p = p.groupby(["unique_id", "ds"], as_index=False).base_units.sum().rename(columns={"base_units": "y"})
    out = []
    for uid, g in p.groupby("unique_id"):
        idx = pd.date_range(g.ds.min(), g.ds.max(), freq="W-SUN")
        if len(idx) < INPUT:
            continue
        s = g.set_index("ds").y.reindex(idx).fillna(0.0)
        out.append(pd.DataFrame({"unique_id": uid, "ds": idx, "y": s.values}))
    df = pd.concat(out, ignore_index=True)
    df["y"] = df.y.clip(lower=0).astype("float32")
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--budget", type=float, default=200.0)
    ap.add_argument("--prep-only", action="store_true")
    ap.add_argument("--panel", default=os.path.join(os.environ.get("AEVAH_DATASET_DIR", "."), "retailer_sales_weekly.parquet"))
    a = ap.parse_args()
    out_dir = Path(os.environ.get("AEVAH_RESULTS_DIR", "outputs/mo145"))
    out_dir.mkdir(parents=True, exist_ok=True)
    df = prep(a.panel)
    info = {"origin": str(ORIGIN.date()), "series": int(df.unique_id.nunique()), "rows": int(len(df)),
            "weeks_max": int(df.groupby("unique_id").size().max()), "prep_s": round(time.time() - T0, 1),
            "steps": a.steps, "models": {}}
    print(json.dumps({k: v for k, v in info.items() if k != "models"}), flush=True)
    if a.prep_only:
        return
    import torch
    from neuralforecast import NeuralForecast
    from neuralforecast.models import NHITS, TCN, TFT
    gpu = torch.cuda.is_available()
    info.update({"cuda": gpu, "gpu": torch.cuda.get_device_name(0) if gpu else None, "torch": torch.__version__,
                 "import_s": round(time.time() - T0, 1)})
    tk = dict(accelerator="gpu" if gpu else "cpu", devices=1, enable_checkpointing=False, logger=False,
              enable_progress_bar=False, default_root_dir=os.environ.get("TMPDIR", "/tmp"))
    specs = [("NHITS", lambda: NHITS(h=H, input_size=INPUT, max_steps=a.steps, scaler_type="robust", **tk)),
             ("TCN", lambda: TCN(h=H, input_size=INPUT, max_steps=a.steps, scaler_type="robust", **tk)),
             ("TFT", lambda: TFT(h=H, input_size=INPUT, hidden_size=64, max_steps=a.steps, scaler_type="robust", **tk))]
    for name, make in specs:
        if time.time() - T0 > a.budget:
            info["models"][name] = {"status": "skipped (time budget)"}
            continue
        try:
            if gpu:
                torch.cuda.reset_peak_memory_stats()
            nf = NeuralForecast(models=[make()], freq="W-SUN")
            t = time.time()
            nf.fit(df=df)
            fit_s = time.time() - t
            t = time.time()
            fc = nf.predict()
            pred_s = time.time() - t
            col = [c for c in fc.columns if c not in ("unique_id", "ds")][0]
            fc.to_parquet(out_dir / f"mo145_{name}_forecast.parquet")
            info["models"][name] = {"status": "ok", "fit_s": round(fit_s, 2), "s_per_step": round(fit_s / a.steps, 4),
                                    "predict_s": round(pred_s, 2), "forecast_rows": int(len(fc)),
                                    "forecast_total": float(np.nansum(fc[col].values)),
                                    "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 1e9, 3) if gpu else None}
        except Exception as e:  # record and continue; a failed model is a timing-test result too
            info["models"][name] = {"status": f"error: {type(e).__name__}: {str(e)[:300]}"}
        info["elapsed_s"] = round(time.time() - T0, 1)
        (out_dir / "mo145_timing.json").write_text(json.dumps(info, indent=2))
        print(name, json.dumps(info["models"][name]), flush=True)
    ok = info["models"]
    info["predictions"] = {
        "P1": all(v.get("status") == "ok" for v in ok.values()),
        "P2": all(ok.get(n, {}).get("fit_s", 1e9) < lim for n, lim in (("NHITS", 60), ("TCN", 60), ("TFT", 120))),
        "P3": all((v.get("peak_gpu_gb") or 0) < 8 for v in ok.values() if v.get("status") == "ok"),
    }
    info["elapsed_s"] = round(time.time() - T0, 1)
    (out_dir / "mo145_timing.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info["predictions"]), "elapsed", info["elapsed_s"], flush=True)


if __name__ == "__main__":
    main()
