#!/usr/bin/env python3
"""
MO_60 — Causal Sensitivity Analysis
=====================================
For each SIGNIFICANT event from MO_72, re-run the BSTS counterfactual
under 9 parameter variants (3 control-similarity thresholds × 3 price-
stability thresholds). The goal is explainable trust-building: every
result gets a plain-English verdict that Rob or Brian can read.

Two questions are being tested:
  1. "How similar must comparison stores be?" — Pearson threshold
  2. "How stable must comparison-store prices be?" — ARP tolerance

If a result holds across all 9 variants → ROBUST  (safe to cite)
If it holds in 4–6 variants → MODERATE             (cite with caveat)
If it holds in ≤ 3 variants → FRAGILE              (don't surface to BUILT)
Events with only 1 control store are pre-flagged FRAGILE with no re-run.

Output: outputs/causal_impact_sensitivity.parquet
  One row per SIGNIFICANT event from MO_72 with:
    stability_score    — 0–9  count of variants confirming the result
    robust_verdict     — ROBUST / MODERATE / FRAGILE (plain English)
    narrative          — 2-sentence human-readable explanation
    variant_detail     — JSON array of the 9 variant results (for drill-down)
"""

import os
import json
import logging
import warnings
import multiprocessing
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, norm

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── pandas 2.x monkey-patch (same as MO_72) ──────────────────────────────────
import pandas.core.common as _pcc
if not hasattr(_pcc, "SettingWithCopyWarning"):
    import pandas.errors as _pe
    _pcc.SettingWithCopyWarning = _pe.SettingWithCopyWarning

# ── paths ─────────────────────────────────────────────────────────────────────
_HERE       = Path(__file__).parent
SCORES_PATH = _HERE / "outputs" / "causal_impact_scores.parquet"
WEEKLY_PATH = _HERE / "outputs" / "retailer_sales_weekly.parquet"
OUT_PATH    = _HERE / "outputs" / "causal_impact_sensitivity.parquet"

# ── sensitivity grid ──────────────────────────────────────────────────────────
# Plain-English label is what surfaces in the narrative and log output.
# Each variant is one combination of:
#   pearson  — minimum pre-period correlation a control store must have with focal
#   arp_tol  — maximum allowed price gap (%) between focal and control store
PARAM_GRID = [
    {"pearson": 0.30, "arp_tol": 0.10, "label": "loose similarity, wide price tolerance"},
    {"pearson": 0.30, "arp_tol": 0.05, "label": "loose similarity, standard price tolerance"},
    {"pearson": 0.30, "arp_tol": 0.03, "label": "loose similarity, tight price tolerance"},
    {"pearson": 0.40, "arp_tol": 0.10, "label": "standard similarity, wide price tolerance"},
    {"pearson": 0.40, "arp_tol": 0.05, "label": "BASELINE (MO-72 defaults)"},
    {"pearson": 0.40, "arp_tol": 0.03, "label": "standard similarity, tight price tolerance"},
    {"pearson": 0.50, "arp_tol": 0.10, "label": "strict similarity, wide price tolerance"},
    {"pearson": 0.50, "arp_tol": 0.05, "label": "strict similarity, standard price tolerance"},
    {"pearson": 0.50, "arp_tol": 0.03, "label": "strictest (highest-confidence controls only)"},
]
N_VARIANTS = len(PARAM_GRID)

MIN_PRE_WEEKS  = 8   # same gate as MO_72
MIN_POST_WEEKS = 8   # same gate as MO_72
MAX_CONTROLS   = 3   # same cap as MO_72 — keeps BSTS tractable

# ── worker-process globals ────────────────────────────────────────────────────
_weekly_pivot: pd.DataFrame = None
_arp_pivot:    pd.DataFrame = None


def _init_worker(parquet_path: str):
    """Load the weekly parquet once per worker process."""
    import pandas.core.dtypes.common as _pc
    import pandas as _pd

    def _patch(arr_or_dtype):
        return (_pd.api.types.is_datetime64_any_dtype(arr_or_dtype) or
                _pd.api.types.is_timedelta64_dtype(arr_or_dtype))
    _pc.is_datetime_or_timedelta_dtype = _patch

    global _weekly_pivot, _arp_pivot
    import warnings
    warnings.filterwarnings("ignore")

    df = _pd.read_parquet(parquet_path)
    df["__time"] = _pd.to_datetime(df["__time"], utc=True).dt.tz_localize(None)
    df["item_id"] = (df["upc"].astype(str) + "|" +
                     df["channel_outlet"].astype(str) + "|" +
                     df["retail_account"].astype(str) + "|" +
                     df["geography_raw"].astype(str))

    _weekly_pivot = df.pivot_table(
        index="__time", columns="item_id", values="base_units", aggfunc="sum"
    )
    _arp_pivot = df.pivot_table(
        index="__time", columns="item_id", values="arp", aggfunc="mean"
    )


# ── parameterized control selection ──────────────────────────────────────────

def _select_controls(focal_id, upc, channel, pre_start, post_start, post_end,
                     pearson_thresh, arp_tol):
    """
    Parameterized version of MO_72 select_controls.

    ARP stability check: the CONTROL store's own first-to-last ARP change
    must be < arp_tol. This filters out controls that had their own price
    event during the window — not a comparison of the control's price level
    to the focal's (which would always fail when the focal had a price cut).

    Pearson check: pre-period correlation between focal and control >= pearson_thresh.
    """
    focal_units = _weekly_pivot.get(focal_id)
    if focal_units is None:
        return []

    focal_pre = focal_units.loc[pre_start : post_start - pd.Timedelta(weeks=1)].dropna()
    if len(focal_pre) < MIN_PRE_WEEKS:
        return []

    prefix = f"{upc}|{channel}|"
    candidates = [c for c in _weekly_pivot.columns
                  if c.startswith(prefix) and c != focal_id]

    valid = []
    for cand_id in candidates:
        # ARP stability: did the CONTROL have its own material price move?
        cand_arp = _arp_pivot.get(cand_id)
        if cand_arp is None:
            continue
        cand_arp_window = cand_arp.loc[pre_start:post_end].dropna()
        if len(cand_arp_window) < 2:
            continue
        arp_pct_chg = ((cand_arp_window.iloc[-1] - cand_arp_window.iloc[0])
                       / max(cand_arp_window.iloc[0], 0.01))
        if abs(arp_pct_chg) >= arp_tol:
            continue   # control had its own price event — confounded, skip

        # Pre-period correlation
        cand_units = _weekly_pivot.get(cand_id)
        if cand_units is None:
            continue
        cand_pre = cand_units.loc[pre_start : post_start - pd.Timedelta(weeks=1)].dropna()
        aligned = pd.concat([focal_pre, cand_pre], axis=1).dropna()
        if len(aligned) < MIN_PRE_WEEKS:
            continue
        r, _ = pearsonr(aligned.iloc[:, 0].values, aligned.iloc[:, 1].values)
        if r >= pearson_thresh:
            valid.append((r, cand_id))

    valid.sort(reverse=True)
    return [cid for _, cid in valid[:MAX_CONTROLS]]


# ── single variant run ────────────────────────────────────────────────────────

def _run_variant(event, variant):
    """
    Run CausalImpact for one event under one parameter variant.
    Returns a small dict with verdict, n_controls, impact_pct.
    """
    from causalimpact import CausalImpact

    focal_id   = event["focal_id"]
    upc        = event["upc"]
    channel    = event["channel_outlet"]
    post_end   = pd.Timestamp(event["post_end"])
    post_start = pd.Timestamp(event["post_start"])
    pre_start  = pd.Timestamp(event["pre_start"])

    focal_units = _weekly_pivot.get(focal_id)
    if focal_units is None:
        return {"verdict": "NO_DATA", "n_controls": 0, "impact_pct": None}

    controls = _select_controls(focal_id, upc, channel, pre_start, post_start, post_end,
                                variant["pearson"], variant["arp_tol"])
    if not controls:
        return {"verdict": "NO_CONTROLS", "n_controls": 0, "impact_pct": None}

    series = focal_units.loc[pre_start:post_end].dropna()
    ctrl_series = [_weekly_pivot[c].loc[pre_start:post_end].rename(f"c{i}")
                   for i, c in enumerate(controls)]
    data = pd.concat([series.rename("y")] + ctrl_series, axis=1).dropna()

    actual = data.index
    pre_rows  = actual[actual < post_start]
    post_rows = actual[actual >= post_start]
    if len(pre_rows) < MIN_PRE_WEEKS or len(post_rows) < MIN_POST_WEEKS:
        return {"verdict": "INSUFFICIENT_DATA", "n_controls": len(controls), "impact_pct": None}

    try:
        ci = CausalImpact(data, [pre_rows[0], pre_rows[-1]], [post_rows[0], post_rows[-1]])
        ci.run()
        inf      = ci.inferences
        post_inf = inf.loc[post_rows[0]:post_rows[-1]]
        if post_inf.empty:
            return {"verdict": "INSUFFICIENT_DATA", "n_controls": len(controls), "impact_pct": None}
        actual  = float(post_inf["response"].sum())
        effect  = float(post_inf["point_effect"].sum())
        eff_lo  = float(post_inf["point_effect_lower"].sum())
        eff_hi  = float(post_inf["point_effect_upper"].sum())
        cf      = actual - effect   # counterfactual = actual - attributed effect
        if cf == 0:
            return {"verdict": "INCONCLUSIVE", "n_controls": len(controls), "impact_pct": 0}
        impact_pct = round(effect / max(abs(cf), 1) * 100, 2)
        if eff_lo == eff_hi:
            p = 1.0
        else:
            se = (eff_hi - eff_lo) / (2 * 1.96)
            z  = effect / max(abs(se), 1e-9)
            p  = 2 * (1 - norm.cdf(abs(z)))
        verdict = "SIGNIFICANT" if p < 0.05 else ("MARGINAL" if p < 0.10 else "INCONCLUSIVE")
        return {"verdict": verdict, "n_controls": len(controls), "impact_pct": impact_pct,
                "p_value": round(p, 4)}
    except Exception as exc:
        return {"verdict": "ERROR", "n_controls": len(controls), "impact_pct": None,
                "error": str(exc)[:80]}


# ── sensitivity for one event (all 9 variants) ───────────────────────────────

def _sensitivity_one(event):
    """
    Run all 9 variants for a single event.
    Returns the event dict enriched with stability_score, robust_verdict, narrative.
    """
    baseline_direction = 1 if event["causal_impact_pct"] > 0 else -1
    variant_results = []

    for v in PARAM_GRID:
        r = _run_variant(event, v)
        r["label"]   = v["label"]
        r["pearson"] = v["pearson"]
        r["arp_tol"] = v["arp_tol"]
        variant_results.append(r)

    runnable = [r for r in variant_results
                if r["verdict"] not in ("NO_DATA", "NO_CONTROLS", "INSUFFICIENT_DATA", "ERROR")]
    confirmed = [r for r in runnable
                 if r["verdict"] == "SIGNIFICANT"
                 and r["impact_pct"] is not None
                 and (1 if r["impact_pct"] > 0 else -1) == baseline_direction]

    n_run       = len(runnable)
    score       = len(confirmed)
    robust      = ("ROBUST" if score >= 7 else "MODERATE" if score >= 4 else "FRAGILE")
    # direction_consistent: True only when price and demand move in opposite directions
    # (price cut → demand up, or price increase → demand down) — standard elasticity logic.
    # Wrong-direction ROBUST events need investigation before surfacing to BUILT.
    direction_ok = (
        (event["price_pct_chg"] < 0 and event["causal_impact_pct"] > 0) or
        (event["price_pct_chg"] > 0 and event["causal_impact_pct"] < 0)
    )
    narrative   = _make_narrative(event, score, n_run, variant_results,
                                   baseline_direction, direction_ok)

    return {
        **event,
        "stability_score":      score,
        "n_variants_run":       n_run,
        "robust_verdict":       robust,
        "direction_consistent": direction_ok,
        "narrative":            narrative,
        "variant_detail":       json.dumps(variant_results),
    }


# ── plain-English narrative ───────────────────────────────────────────────────

def _make_narrative(event, score, n_run, variants, baseline_direction, direction_ok=True):
    """
    Generate a 2-sentence plain-English explanation.
    Written so Rob or Brian can read it without statistical training.
    """
    pct      = event["causal_impact_pct"]
    price    = event["price_pct_chg"] * 100
    desc     = event["description"]
    account  = event["retail_account"]
    n_ctrl   = event["n_control_series"]

    price_str  = f"{'−' if price < 0 else '+' }{abs(price):.1f}% price {'cut' if price < 0 else 'increase'}"
    impact_str = f"+{pct:.1f}%" if pct > 0 else f"{pct:.1f}%"
    ctrl_str   = (f"one comparison store"
                  if n_ctrl == 1 else f"{n_ctrl} comparison stores")

    if n_run == 0:
        runnable_note = ("No sensitivity variants could be run — "
                         "no comparison stores met any of the 9 test criteria.")
    elif score == n_run:
        runnable_note = (f"The result held in all {n_run} runnable tests, "
                         "regardless of how strictly we required comparison stores to match.")
    elif score == 0:
        runnable_note = (f"The result did not hold in any of the {n_run} runnable tests. "
                         "The baseline result depends entirely on the specific comparison "
                         "stores selected and should not be cited.")
    else:
        failing = [v["label"] for v in variants
                   if v["verdict"] not in ("NO_DATA", "NO_CONTROLS", "INSUFFICIENT_DATA", "ERROR")
                   and not (v["verdict"] == "SIGNIFICANT"
                            and v["impact_pct"] is not None
                            and (1 if v["impact_pct"] > 0 else -1) == baseline_direction)]
        runnable_note = (f"The result held in {score} of {n_run} runnable tests. "
                         f"It broke down under: {'; '.join(failing[:2])}.")

    direction_note = ""
    if not direction_ok:
        if event["price_pct_chg"] > 0 and event["causal_impact_pct"] > 0:
            direction_note = (
                " Note: price increase coinciding with demand increase is atypical — "
                "a seasonal event, distribution change, or competitor promotion may "
                "be responsible. Investigate before citing as causal evidence."
            )
        elif event["price_pct_chg"] < 0 and event["causal_impact_pct"] < 0:
            direction_note = (
                " Note: price cut coinciding with demand decline is atypical — "
                "a concurrent negative event (distribution loss, out-of-stock, "
                "competitor promotion) may be suppressing the price effect. "
                "Investigate before citing as causal evidence."
            )

    return (
        f"{desc} at {account}: {price_str} → estimated {impact_str} demand lift "
        f"(based on {ctrl_str}). "
        f"{runnable_note}"
        f"{direction_note}"
    )


def _make_narrative_fragile_single(event):
    pct      = event["causal_impact_pct"]
    price    = event["price_pct_chg"] * 100
    desc     = event["description"]
    account  = event["retail_account"]
    price_str  = f"{'−' if price < 0 else '+'}{abs(price):.1f}% price {'cut' if price < 0 else 'increase'}"
    impact_str = f"+{pct:.1f}%" if pct > 0 else f"{pct:.1f}%"
    return (
        f"{desc} at {account}: {price_str} → estimated {impact_str} demand lift "
        f"(based on 1 comparison store — sensitivity analysis not run). "
        f"With only one comparison store available, this result cannot be stress-tested. "
        f"Treat as directional only; do not cite as causal proof to BUILT."
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("━" * 65)
    log.info("MO_60 — Causal Sensitivity Analysis")
    log.info("━" * 65)

    if not SCORES_PATH.exists():
        log.error(f"Missing: {SCORES_PATH}"); return
    if not WEEKLY_PATH.exists():
        log.error(f"Missing: {WEEKLY_PATH}"); return

    scores = pd.read_parquet(SCORES_PATH)
    scores["window_end_date"] = pd.to_datetime(scores["window_end_date"])

    sig = scores[scores["causal_verdict"] == "SIGNIFICANT"].copy()
    log.info(f"SIGNIFICANT events from MO_72: {len(sig)}")

    multi_ctrl = sig[sig["n_control_series"] >= 2].copy()
    single_ctrl = sig[sig["n_control_series"] < 2].copy()
    log.info(f"  n_controls ≥ 2 (sensitivity candidates): {len(multi_ctrl)}")
    log.info(f"  n_controls = 1 (pre-flagged FRAGILE, no re-run): {len(single_ctrl)}")

    # Reconstruct event periods from stored fields
    for df in (multi_ctrl, single_ctrl):
        df["post_end"]   = df["window_end_date"]
        df["post_start"] = df["post_end"] - pd.to_timedelta(df["post_weeks_used"] * 7, unit="D")
        df["pre_end"]    = df["post_start"] - pd.Timedelta(weeks=1)
        df["pre_start"]  = df["pre_end"] - pd.to_timedelta(df["pre_weeks_used"] * 7, unit="D")
        df["focal_id"]   = (df["upc"].astype(str) + "|" +
                            df["channel_outlet"].astype(str) + "|" +
                            df["retail_account"].astype(str) + "|" +
                            df["geography_raw"].astype(str))

    # ── Run sensitivity for multi-control events ──────────────────────────────
    records = multi_ctrl.to_dict("records")
    results = []
    n_workers = max(1, multiprocessing.cpu_count() - 2)
    log.info(f"\nRunning {len(records)} events × {N_VARIANTS} variants "
             f"({n_workers} workers) …")

    with ProcessPoolExecutor(max_workers=n_workers,
                             initializer=_init_worker,
                             initargs=(str(WEEKLY_PATH),)) as pool:
        futures = {pool.submit(_sensitivity_one, ev): ev for ev in records}
        for i, fut in enumerate(as_completed(futures)):
            ev = futures[fut]
            try:
                results.append(fut.result())
                if (i + 1) % 5 == 0 or (i + 1) == len(records):
                    log.info(f"  {i + 1}/{len(records)} done")
            except Exception as exc:
                log.warning(f"  FAILED: {ev['upc']} @ {ev['retail_account']} — {exc}")

    # ── Pre-flag single-control events as FRAGILE ─────────────────────────────
    fragile_singles = []
    for rec in single_ctrl.to_dict("records"):
        dir_ok = (
            (rec["price_pct_chg"] < 0 and rec["causal_impact_pct"] > 0) or
            (rec["price_pct_chg"] > 0 and rec["causal_impact_pct"] < 0)
        )
        fragile_singles.append({
            **rec,
            "stability_score":      0,
            "n_variants_run":       0,
            "robust_verdict":       "FRAGILE",
            "direction_consistent": dir_ok,
            "narrative":            _make_narrative_fragile_single(rec),
            "variant_detail":       "[]",
        })

    # ── Combine and save ──────────────────────────────────────────────────────
    out = pd.DataFrame(results + fragile_singles)

    # Drop reconstruction columns not needed downstream
    out.drop(columns=["focal_id", "post_end", "post_start", "pre_end", "pre_start"],
             errors="ignore", inplace=True)

    out.sort_values(["robust_verdict", "stability_score"],
                    key=lambda s: s.map({"ROBUST": 0, "MODERATE": 1, "FRAGILE": 2})
                                   if s.name == "robust_verdict" else -s,
                    inplace=True)

    out.to_parquet(OUT_PATH, index=False)
    log.info(f"\nSaved → {OUT_PATH}  ({len(out)} rows)")

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("\n" + "━" * 65)
    log.info("SENSITIVITY SUMMARY")
    log.info("━" * 65)
    for verdict in ("ROBUST", "MODERATE", "FRAGILE"):
        n = len(out[out["robust_verdict"] == verdict])
        pct = 100 * n / len(out) if len(out) else 0
        log.info(f"  {verdict:<10} {n:>3}  ({pct:.0f}%)")

    robust_dir = out[(out["robust_verdict"] == "ROBUST") & out["direction_consistent"]]
    robust_inv = out[(out["robust_verdict"] == "ROBUST") & ~out["direction_consistent"]]
    log.info(f"  → of which ROBUST + correct direction: {len(robust_dir)}  "
             f"(safe to cite; price and demand moved as expected)")
    log.info(f"  → of which ROBUST + wrong direction:  {len(robust_inv)}  "
             f"(robust but atypical — investigate confounders before citing)")

    log.info("\n── ROBUST + correct direction (safe to cite to BUILT) ──────")
    robust = out[(out["robust_verdict"] == "ROBUST") & out["direction_consistent"]].sort_values(
        "stability_score", ascending=False)
    for _, row in robust.head(10).iterrows():
        log.info(f"\n  [{row['stability_score']}/9]  {row['description'][:55]}")
        log.info(f"  {row['retail_account']}  |  {row['price_pct_chg']*100:+.1f}% price  "
                 f"→  {row['causal_impact_pct']:+.1f}% demand")
        log.info(f"  {row['narrative']}")

    log.info("\n── FRAGILE events (do not surface to BUILT) ─────────────────")
    fragile = out[out["robust_verdict"] == "FRAGILE"].head(5)
    for _, row in fragile.iterrows():
        log.info(f"\n  [{row['stability_score']}/9]  {row['description'][:55]}")
        log.info(f"  {row['narrative']}")

    log.info("\n" + "━" * 65)
    log.info("Next step: review ROBUST events → wire robust_verdict into")
    log.info("           causal_impact_scores Druid table (add column)")
    log.info("           so the Mo UI can filter to ROBUST events only.")
    log.info("━" * 65)


if __name__ == "__main__":
    main()
