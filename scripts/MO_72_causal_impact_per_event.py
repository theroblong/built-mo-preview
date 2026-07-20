"""MO_72 — Automated Per-Event CausalImpact (BSTS Counterfactual)

For every material price event in price_elasticity_training_features
(|Δprice/bar| ≥ 5%, ≥8 pre-weeks, ≥8 post-weeks), runs a Bayesian
Structural Time Series counterfactual using cross-account control series
to estimate the causal demand impact of the price move.

Enables the Causal Analysis drawer in Mo UI (Event Detail Modal).
MO_43 proved the method on one event; this script makes it systematic.

Output schema (causal_impact_scores.parquet → Druid):
  __time              — window_end_date (end of 13-week post period)
  upc, description, channel_outlet, retail_account, geography_raw
  price_pct_chg       — observed price change (+ = price up)
  causal_impact_pct   — % unit impact attributable to price move (posterior mean)
  causal_impact_units — unit impact (actual_post_sum - counterfactual_post_sum)
  causal_impact_low   — 95% CI lower (units)
  causal_impact_high  — 95% CI upper (units)
  causal_p_value      — p-value approximation (normal CI-based)
  causal_verdict      — SIGNIFICANT / MARGINAL / INCONCLUSIVE
  n_control_series    — number of cross-account controls used
  control_accounts    — pipe-separated list of control retail_accounts
  pre_weeks_used      — actual pre-period weeks
  post_weeks_used     — actual post-period weeks
  scored_at

Usage:
  python scripts/MO_72_causal_impact_per_event.py            # all eligible
  python scripts/MO_72_causal_impact_per_event.py --limit 200
  python scripts/MO_72_causal_impact_per_event.py --min-pct-chg 0.10
  python scripts/MO_72_causal_impact_per_event.py --workers 6
"""

# ── pandas 2.x monkey-patch (causalimpact 0.2.6 compat) ──────────────────────
import pandas as pd
import pandas.core.dtypes.common as _pdcommon

def _is_dt_or_td(arr_or_dtype):
    return (pd.api.types.is_datetime64_any_dtype(arr_or_dtype) or
            pd.api.types.is_timedelta64_dtype(arr_or_dtype))

_pdcommon.is_datetime_or_timedelta_dtype = _is_dt_or_td

# ─────────────────────────────────────────────────────────────────────────────

import argparse
import json
import os
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError
from datetime import datetime, timezone

warnings.filterwarnings("ignore")
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mo_druid_client import query_druid

PARQUET    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs",
                          "retailer_sales_weekly.parquet")
GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

MIN_PCT_CHG      = 0.05   # |Δprice/bar| threshold
MIN_PRE_WEEKS    = 8
MIN_POST_WEEKS   = 8
MIN_CORR         = 0.40   # minimum pre-period correlation for a valid control
MAX_CONTROLS     = 3      # cap controls per event to keep BSTS tractable
TIMEOUT_SEC      = 45     # per-event timeout (seconds)
N_WORKERS        = 4

# Significance thresholds for causal_verdict
P_SIGNIFICANT = 0.05
P_MARGINAL    = 0.10


# ── Worker-process globals ────────────────────────────────────────────────────
# Loaded once per worker via initializer; avoids re-serializing on every call.

_weekly_pivot: pd.DataFrame = None   # item_id × week date (base_units)
_arp_pivot:    pd.DataFrame = None   # item_id × week date (arp)


def _init_worker(parquet_path: str):
    global _weekly_pivot, _arp_pivot

    import pandas.core.dtypes.common as _pc
    import pandas as _pd

    def _patch(arr_or_dtype):
        return (_pd.api.types.is_datetime64_any_dtype(arr_or_dtype) or
                _pd.api.types.is_timedelta64_dtype(arr_or_dtype))
    _pc.is_datetime_or_timedelta_dtype = _patch

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


# ── Control series selection ──────────────────────────────────────────────────

def select_controls(focal_id: str, upc: str, channel: str,
                    pre_start: pd.Timestamp, post_start: pd.Timestamp,
                    post_end: pd.Timestamp) -> list[str]:
    """
    Find cross-account control series for a focal price event.

    Criteria:
      1. Same UPC + channel_outlet, different retail_account.
      2. ARP stable during [pre_start, post_end] (|Δ| < 5%) — not confounded.
      3. Pre-period Pearson correlation with focal series ≥ MIN_CORR.

    Uses actual available parquet data for pre-period (pre_start may be before
    the parquet start — correlation computed on whatever overlap exists).
    Returns up to MAX_CONTROLS item_ids sorted by descending pre-period correlation.
    """
    focal_units = _weekly_pivot.get(focal_id)
    focal_arp   = _arp_pivot.get(focal_id)
    if focal_units is None:
        return []

    # Use actual available pre-period data (may be shorter than Druid's 13w)
    focal_pre = focal_units.loc[pre_start : post_start - pd.Timedelta(weeks=1)].dropna()
    if len(focal_pre) < MIN_PRE_WEEKS:
        return []

    prefix = f"{upc}|{channel}|"
    candidates = [c for c in _weekly_pivot.columns
                  if c.startswith(prefix) and c != focal_id]

    valid = []
    for cand_id in candidates:
        cand_arp = _arp_pivot.get(cand_id)
        if cand_arp is None:
            continue

        # ARP stability check: candidate must not have its own material price move
        cand_arp_window = cand_arp.loc[pre_start:post_end].dropna()
        if len(cand_arp_window) < 2:
            continue
        arp_pct_chg = (cand_arp_window.iloc[-1] - cand_arp_window.iloc[0]) / max(
            cand_arp_window.iloc[0], 0.01
        )
        if abs(arp_pct_chg) >= MIN_PCT_CHG:
            continue  # confounded — skip

        # Pre-period correlation
        cand_units = _weekly_pivot.get(cand_id)
        if cand_units is None:
            continue
        cand_pre = cand_units.loc[pre_start : post_start - pd.Timedelta(weeks=1)].dropna()
        aligned   = pd.concat([focal_pre, cand_pre], axis=1).dropna()
        if len(aligned) < MIN_PRE_WEEKS:
            continue
        r, _ = stats.pearsonr(aligned.iloc[:, 0], aligned.iloc[:, 1])
        if r >= MIN_CORR:
            valid.append((r, cand_id))

    valid.sort(reverse=True)
    return [cid for _, cid in valid[:MAX_CONTROLS]]


# ── Single-event CausalImpact ─────────────────────────────────────────────────

def score_one_event(event: dict) -> dict | None:
    """Run CausalImpact for a single price event; return result dict or None."""
    from causalimpact import CausalImpact

    upc         = event["upc"]
    channel     = event["channel_outlet"]
    account     = event["retail_account"]
    geo         = event["geography_raw"]
    window_end  = pd.Timestamp(event["window_end_date"])
    pre_weeks   = int(event["pre_13w_weeks_count"])
    post_weeks  = int(event["post_13w_weeks_count"])
    price_pct   = float(event["price_pct_chg"])

    focal_id    = f"{upc}|{channel}|{account}|{geo}"

    # Derive date bounds from window_end
    post_end    = window_end
    post_start  = window_end - pd.Timedelta(weeks=post_weeks)
    pre_end     = post_start - pd.Timedelta(weeks=1)
    # Use the Druid-stated pre_weeks as a target; actual lookback is limited
    # to whatever the parquet covers — handled below in the alignment step.
    pre_start   = pre_end   - pd.Timedelta(weeks=pre_weeks)

    # Pull focal series
    focal_units = _weekly_pivot.get(focal_id)
    if focal_units is None:
        return None

    # Use all available parquet data in [pre_start, post_end]; don't require
    # the full Druid-stated pre_weeks (parquet may not go back that far).
    series_window = focal_units.loc[pre_start:post_end].dropna()

    # Control series
    controls    = select_controls(focal_id, upc, channel, pre_start, post_start, post_end)
    n_controls  = len(controls)

    # Build CausalImpact DataFrame
    ctrl_dfs = []
    for i, cid in enumerate(controls):
        s = _weekly_pivot[cid].loc[pre_start:post_end]
        s.name = f"ctrl_{i}"
        ctrl_dfs.append(s)

    data = pd.concat([series_window.rename("response")] + ctrl_dfs, axis=1).dropna()
    if len(data) < (MIN_PRE_WEEKS + MIN_POST_WEEKS):
        return None

    # Align pre / post periods to actual available dates
    actual_dates  = data.index
    pre_rows      = actual_dates[actual_dates < post_start]
    post_rows     = actual_dates[actual_dates >= post_start]
    if len(pre_rows) < MIN_PRE_WEEKS or len(post_rows) < 4:
        return None

    pre_period  = [pre_rows[0],  pre_rows[-1]]
    post_period = [post_rows[0], post_rows[-1]]

    try:
        ci = CausalImpact(data, pre_period, post_period)
        ci.run()
    except Exception:
        return None

    inf = ci.inferences
    post_inf = inf.loc[post_rows[0]:post_rows[-1]]
    if post_inf.empty:
        return None

    # Extract summary metrics from inferences
    actual_sum  = float(post_inf["response"].sum())
    effect_sum  = float(post_inf["point_effect"].sum())
    effect_low  = float(post_inf["point_effect_lower"].sum())
    effect_high = float(post_inf["point_effect_upper"].sum())

    counterfactual_sum = actual_sum - effect_sum
    if counterfactual_sum == 0:
        return None

    impact_pct = effect_sum / max(abs(counterfactual_sum), 1) * 100

    # p-value approximation from CI (normal-based)
    if effect_low == effect_high:
        p_value = 1.0
    else:
        se = (effect_high - effect_low) / (2 * 1.96)
        z  = effect_sum / max(abs(se), 1e-9)
        p_value = float(2 * (1 - stats.norm.cdf(abs(z))))

    if p_value < P_SIGNIFICANT:
        verdict = "SIGNIFICANT"
    elif p_value < P_MARGINAL:
        verdict = "MARGINAL"
    else:
        verdict = "INCONCLUSIVE"

    control_accounts = "|".join(
        cid.split("|")[2] for cid in controls
    )

    return {
        "window_end_date":    window_end.strftime("%Y-%m-%d"),
        "upc":                upc,
        "description":        event.get("description", ""),
        "channel_outlet":     channel,
        "retail_account":     account,
        "geography_raw":      geo,
        "price_pct_chg":      round(price_pct, 4),
        "causal_impact_pct":  round(impact_pct, 2),
        "causal_impact_units": round(effect_sum, 1),
        "causal_impact_low":  round(effect_low, 1),
        "causal_impact_high": round(effect_high, 1),
        "causal_p_value":     round(p_value, 4),
        "causal_verdict":     verdict,
        "n_control_series":   n_controls,
        "control_accounts":   control_accounts,
        "pre_weeks_used":     len(pre_rows),
        "post_weeks_used":    len(post_rows),
        "scored_at":          datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ── Chart ─────────────────────────────────────────────────────────────────────

def chart_summary(df: pd.DataFrame, out_path: str):
    sig   = df[df["causal_verdict"] == "SIGNIFICANT"]
    marg  = df[df["causal_verdict"] == "MARGINAL"]
    incon = df[df["causal_verdict"] == "INCONCLUSIVE"]

    fig, axes = plt.subplots(1, 3, figsize=(17, 6))
    fig.patch.set_facecolor("#f8f9fa")
    fig.suptitle(
        f"MO_72 — Automated CausalImpact  |  {len(df):,} events scored",
        fontsize=13, y=1.01,
    )

    # Panel 1: verdict distribution
    ax = axes[0]
    counts  = [len(sig), len(marg), len(incon)]
    labels  = ["Significant\n(p<0.05)", "Marginal\n(p<0.10)", "Inconclusive"]
    colors  = ["#22c55e", "#f59e0b", "#94a3b8"]
    bars    = ax.bar(labels, counts, color=colors, edgecolor="white", width=0.6)
    for bar, v in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, v + max(counts) * 0.02,
                str(v), ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_title("Verdict Distribution", fontsize=11)
    ax.set_facecolor("#f8f9fa")
    ax.spines[["top", "right"]].set_visible(False)

    # Panel 2: distribution of causal_impact_pct for significant events
    ax2 = axes[1]
    if len(sig) > 0:
        ax2.hist(sig["causal_impact_pct"].clip(-100, 200), bins=30,
                 color="#1f77b4", edgecolor="white", alpha=0.85)
        ax2.axvline(0, color="black", linewidth=1, linestyle="--")
        ax2.axvline(sig["causal_impact_pct"].median(), color="#e84444",
                    linewidth=1.5, linestyle="-",
                    label=f"Median {sig['causal_impact_pct'].median():.1f}%")
        ax2.legend(fontsize=9)
    ax2.set_title("Causal Impact % (Significant events)", fontsize=11)
    ax2.set_xlabel("% unit impact vs. counterfactual")
    ax2.set_facecolor("#f8f9fa")
    ax2.spines[["top", "right"]].set_visible(False)

    # Panel 3: price change vs causal impact scatter (significant only)
    ax3 = axes[2]
    if len(sig) > 0:
        sc = ax3.scatter(
            sig["price_pct_chg"] * 100,
            sig["causal_impact_pct"],
            alpha=0.4, s=20, c="#1f4e79",
        )
        ax3.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax3.axvline(0, color="black", linewidth=0.8, linestyle="--")
    ax3.set_xlabel("Price change (%)")
    ax3.set_ylabel("Causal demand impact (%)")
    ax3.set_title("Price Change vs. Demand Impact\n(Significant events)", fontsize=11)
    ax3.set_facecolor("#f8f9fa")
    ax3.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#f8f9fa")
    plt.close()
    print(f"Saved {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MO_72 — Automated CausalImpact")
    parser.add_argument("--limit",       type=int,   default=None,
                        help="Max events to score (default: all eligible)")
    parser.add_argument("--min-pct-chg", type=float, default=MIN_PCT_CHG,
                        help=f"Min |price change| threshold (default {MIN_PCT_CHG})")
    parser.add_argument("--workers",     type=int,   default=N_WORKERS,
                        help=f"Parallel workers (default {N_WORKERS})")
    args = parser.parse_args()

    print("=" * 65)
    print("MO_72 — Automated Per-Event CausalImpact")
    print(f"  Min |Δprice/bar|  : {args.min_pct_chg:.0%}")
    print(f"  Min pre/post weeks: {MIN_PRE_WEEKS}/{MIN_POST_WEEKS}")
    print(f"  Parallel workers  : {args.workers}")
    print("=" * 65)

    # ── 1. Load eligible events from Druid ────────────────────────────────────
    print("\nQuerying price_elasticity_training_features …")
    sql = f"""
    SELECT
      TIME_FORMAT(__time, 'yyyy-MM-dd')  AS window_end_date,
      upc, description, channel_outlet, retail_account, geography_raw,
      price_per_bar_pct_chg              AS price_pct_chg,
      pre_13w_weeks_count, post_13w_weeks_count,
      pre_13w_base_units, post_13w_base_units,
      pre_13w_avg_price_per_bar, post_13w_avg_price_per_bar
    FROM price_elasticity_training_features
    WHERE pre_13w_weeks_count  >= {MIN_PRE_WEEKS}
      AND post_13w_weeks_count >= {MIN_POST_WEEKS}
      AND pre_13w_base_units    > 0
      AND ABS(price_per_bar_pct_chg) >= {args.min_pct_chg}
    """
    events_df = query_druid(sql)
    for col in ["pre_13w_weeks_count", "post_13w_weeks_count",
                "pre_13w_base_units", "post_13w_base_units",
                "price_pct_chg", "pre_13w_avg_price_per_bar",
                "post_13w_avg_price_per_bar"]:
        events_df[col] = pd.to_numeric(events_df[col], errors="coerce")

    print(f"  Total eligible rows: {len(events_df):,}")

    # Deduplicate: 1 event per focal series — largest |price change|
    events_df["abs_pct_chg"] = events_df["price_pct_chg"].abs()
    events_df = (
        events_df
        .sort_values("abs_pct_chg", ascending=False)
        .drop_duplicates(subset=["upc", "channel_outlet", "retail_account", "geography_raw"])
        .reset_index(drop=True)
    )
    print(f"  After dedup (1 per series): {len(events_df):,}")

    if args.limit:
        events_df = events_df.head(args.limit)
        print(f"  After --limit {args.limit}: {len(events_df):,}")

    events = events_df.to_dict("records")
    n_events = len(events)

    # ── 2. Run CausalImpact in parallel ──────────────────────────────────────
    print(f"\nScoring {n_events:,} events with {args.workers} workers …")
    print("  (45s timeout per event; errors logged as SKIPPED)\n")

    results = []
    n_success = n_skipped = n_error = 0
    t0 = time.time()

    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=_init_worker,
        initargs=(PARQUET,),
    ) as pool:
        futures = {pool.submit(score_one_event, ev): i for i, ev in enumerate(events)}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                res = fut.result(timeout=TIMEOUT_SEC)
                if res is not None:
                    results.append(res)
                    n_success += 1
                else:
                    n_skipped += 1
            except TimeoutError:
                n_skipped += 1
            except Exception:
                n_error += 1

            if i % 50 == 0 or i == n_events:
                elapsed = time.time() - t0
                rate    = i / elapsed
                eta     = (n_events - i) / max(rate, 0.01)
                print(f"  {i:>5}/{n_events}  "
                      f"success={n_success}  skipped={n_skipped}  err={n_error}  "
                      f"rate={rate:.1f}/s  ETA={eta/60:.0f}min")

    print(f"\n  Total elapsed: {(time.time() - t0)/60:.1f} min")

    if not results:
        print("  No results — check data availability and parquet path")
        return

    # ── 3. Collect and save ───────────────────────────────────────────────────
    out_df = pd.DataFrame(results)
    out_df["__time"] = pd.to_datetime(out_df["window_end_date"])

    parquet_path = os.path.join(OUTPUT_DIR, "causal_impact_scores.parquet")
    out_df.to_parquet(parquet_path, index=False)
    print(f"\nSaved {parquet_path}  ({len(out_df):,} rows)")

    json_path = os.path.join(OUTPUT_DIR, "mo72_causal_impact_summary.json")
    sig   = out_df[out_df["causal_verdict"] == "SIGNIFICANT"]
    marg  = out_df[out_df["causal_verdict"] == "MARGINAL"]
    incon = out_df[out_df["causal_verdict"] == "INCONCLUSIVE"]

    summary = {
        "script":          "MO_72",
        "scored_at":       datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_scored":    len(out_df),
        "n_success":       n_success,
        "n_skipped":       n_skipped,
        "n_error":         n_error,
        "significant":     len(sig),
        "marginal":        len(marg),
        "inconclusive":    len(incon),
        "significant_pct": round(len(sig) / len(out_df) * 100, 1),
        "median_impact_pct_significant":
            round(float(sig["causal_impact_pct"].median()), 2) if len(sig) else None,
        "median_impact_pct_all":
            round(float(out_df["causal_impact_pct"].median()), 2),
        "median_p_value":  round(float(out_df["causal_p_value"].median()), 4),
        "n_with_controls": int((out_df["n_control_series"] > 0).sum()),
    }
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved {json_path}")

    # ── 4. Chart ──────────────────────────────────────────────────────────────
    chart_summary(out_df, os.path.join(OUTPUT_DIR, "mo72_causal_impact_chart.png"))

    # ── 5. Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)
    print(f"  Events scored      : {len(out_df):,}")
    print(f"  SIGNIFICANT (p<.05): {len(sig):,}  ({len(sig)/len(out_df)*100:.0f}%)")
    print(f"  MARGINAL (p<.10)   : {len(marg):,}  ({len(marg)/len(out_df)*100:.0f}%)")
    print(f"  INCONCLUSIVE       : {len(incon):,}  ({len(incon)/len(out_df)*100:.0f}%)")
    if len(sig) > 0:
        print(f"\n  Significant events:")
        print(f"    Median impact   : {sig['causal_impact_pct'].median():+.1f}%")
        print(f"    Median p-value  : {sig['causal_p_value'].median():.4f}")
        print(f"    % price down    : {(sig['price_pct_chg'] < 0).mean()*100:.0f}%")
        print(f"    % demand up     : {(sig['causal_impact_pct'] > 0).mean()*100:.0f}%")
        print(f"\n  Top 10 significant events by |impact %|:")
        top10 = (sig.nlargest(10, "causal_impact_pct")
                    [["retail_account", "upc", "price_pct_chg",
                      "causal_impact_pct", "causal_p_value", "n_control_series"]])
        top10["price_pct_chg"]   = (top10["price_pct_chg"] * 100).round(1)
        top10["causal_impact_pct"] = top10["causal_impact_pct"].round(1)
        top10["causal_p_value"]  = top10["causal_p_value"].round(4)
        print(top10.to_string(index=False))

    print("\nNext step: ingest causal_impact_scores.parquet → Druid (Rob)")
    print("  Then wire causal_impact_pct + causal_p_value into Event Detail Modal")
    print("=" * 65)


if __name__ == "__main__":
    main()
