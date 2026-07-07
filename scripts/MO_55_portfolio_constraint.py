"""MO_55 — Portfolio Cannibalization Constraint.

PURPOSE
-------
MO_27 generates independent forecasts for each (upc, channel, retailer, geo) series.
Individual series have no awareness of sibling BUILT products. When a new BUILT flavor
launches and cannibalizes an incumbent, the incumbent's AR lags haven't yet captured
the decline — both series forecast independently, and their sum overstates total BUILT
demand at the retailer.

This script adds a post-processing layer: for BUILT UPCs in their launch window
(weeks_since_launch ≤ LAUNCH_WINDOW), apply a demand redistribution from BUILT
sibling donors using the scored_cannibalization transition matrix. The redistribution
is zero-sum — total BUILT portfolio demand is conserved.

WHEN TO APPLY
-------------
Focal UPC is a launch-phase product (weeks_since_launch ≤ LAUNCH_WINDOW) AND has
BUILT siblings in scored_cannibalization with cannibal_prob > CANNIBAL_THRESHOLD.

Mature products (weeks_since_launch > LAUNCH_WINDOW) are left unchanged — their AR
lags already reflect competitive dynamics, and redistribution would double-count.

ALGORITHM
---------
For each (retail_account, channel_outlet, geography_raw, forecast_week_number):
  For each cold-start focal UPC:
    decay = 1 − (weeks_since_launch / LAUNCH_WINDOW)   # 1.0 at week 1, 0 at week 26
    For each qualifying BUILT sibling donor:
      raw_transfer = cannibal_prob × sibling_q50 × decay
      capped_transfer = min(raw_transfer, sibling_q50 × MAX_TRANSFER_PCT)
    focal_adj   += sum(capped_transfers from all siblings)
    sibling_adj -= capped_transfer (each sibling gives proportionally)

OUTPUTS
-------
  outputs/retailer_sales_forecast_adj.parquet  — adjusted forecast + audit columns
  outputs/mo55_portfolio_summary.csv           — per-series redistribution summary
  outputs/v2_mo55_redistribution.png           — redistribution magnitude chart
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timezone
from mo_druid_client import query_druid

# ── Config ────────────────────────────────────────────────────────────────────
OUTPUT_DIR       = os.path.join(os.path.dirname(__file__), "outputs")
FORECAST_PARQUET = os.path.join(OUTPUT_DIR, "retailer_sales_forecast.parquet")
ADJ_PARQUET      = os.path.join(OUTPUT_DIR, "retailer_sales_forecast_adj.parquet")
SUMMARY_CSV      = os.path.join(OUTPUT_DIR, "mo55_portfolio_summary.csv")
CHART_PATH       = os.path.join(OUTPUT_DIR, "v2_mo55_redistribution.png")

LAUNCH_WINDOW      = 26    # weeks — apply redistribution for focal UPCs ≤ this age
CANNIBAL_THRESHOLD = 0.30  # min cannibal_prob for a pair to trigger redistribution
MAX_TRANSFER_PCT   = 0.20  # cap: sibling donates at most 20% of its forecast TOTAL across all focals
MAX_RECEIVE_PCT    = 0.50  # cap: focal receives at most 50% of its own weekly forecast
MIN_FOCAL_UNITS    = 10.0  # focal must forecast ≥ this many units/week to be eligible

GROUP_COLS = ["retail_account", "channel_outlet", "geography_raw"]
SERIES_KEY = ["upc"] + GROUP_COLS


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_built_upc_set() -> set:
    """All BUILT focal UPCs from event_detection_weekly."""
    print("  Loading BUILT UPC set from event_detection_weekly …")
    edw = query_druid("""
        SELECT DISTINCT upc
        FROM "event_detection_weekly"
    """)
    s = set(edw["upc"].tolist())
    print(f"  BUILT UPC set: {len(s):,} UPCs")
    return s


def load_cannibalization_pairs(built_upc_set: set) -> pd.DataFrame:
    """BUILT-to-BUILT cannibalization pairs from scored_cannibalization.

    Returns rows where BOTH focal_upc and donor_upc are BUILT UPCs,
    with cannibal_prob >= CANNIBAL_THRESHOLD.
    """
    print("  Loading scored_cannibalization from Druid …")
    sc = query_druid("""
        SELECT
            focal_upc, donor_upc,
            retail_account, channel_outlet, geography_raw,
            cannibal_prob
        FROM "scored_cannibalization"
    """)
    print(f"  Raw rows loaded: {len(sc):,}")
    sc["cannibal_prob"] = pd.to_numeric(sc["cannibal_prob"], errors="coerce")
    sc = (
        sc.groupby(["focal_upc", "donor_upc", "retail_account", "channel_outlet", "geography_raw"])
        ["cannibal_prob"].max()
        .reset_index()
    )
    print(f"  Raw pairs (after dedup): {len(sc):,}")

    # Filter to BUILT-to-BUILT only
    sc = sc[
        sc["focal_upc"].isin(built_upc_set) &
        sc["donor_upc"].isin(built_upc_set) &
        (sc["focal_upc"] != sc["donor_upc"])
    ].copy()
    print(f"  BUILT-to-BUILT pairs: {len(sc):,}")

    # Apply probability threshold
    sc = sc[sc["cannibal_prob"] >= CANNIBAL_THRESHOLD].copy()
    print(f"  After threshold ({CANNIBAL_THRESHOLD}): {len(sc):,} pairs")
    return sc


def apply_portfolio_constraint(
    forecast: pd.DataFrame,
    pairs: pd.DataFrame,
) -> pd.DataFrame:
    """Apply zero-sum demand redistribution for launch-phase BUILT UPCs.

    Returns adjusted forecast with audit columns appended.
    """
    df = forecast.copy()
    df["portfolio_adj_delta"]    = 0.0
    df["portfolio_adj_type"]     = "NONE"
    df["portfolio_adj_source_upc"] = ""

    # Index forecast by (upc, retail_account, channel_outlet, geography_raw, forecast_week_number)
    # for fast lookup when applying adjustments
    idx_cols = SERIES_KEY + ["forecast_week_number"]
    df = df.set_index(idx_cols)

    # Get cold-start focal UPCs (weeks_since_launch ≤ LAUNCH_WINDOW)
    launch_focals = (
        forecast[forecast["weeks_since_launch"] <= LAUNCH_WINDOW]
        [SERIES_KEY + ["weeks_since_launch"]]
        .drop_duplicates()
    )
    print(f"\n  Cold-start focal series (weeks_since_launch ≤ {LAUNCH_WINDOW}): "
          f"{len(launch_focals):,}")
    if launch_focals.empty:
        print("  No cold-start series found — no redistribution applied.")
        return df.reset_index()

    n_pairs_applied = 0
    n_skipped_low_presence = 0
    n_skipped_receive_cap = 0
    n_series_adjusted = set()
    total_units_redistributed = 0.0

    # Iterate over actual (focal, forecast_week) rows where wsl ≤ LAUNCH_WINDOW.
    # This ensures each (focal_key) is processed exactly once — no double-counting
    # from multiple wsl values in the outer loop.
    launch_focal_weeks = forecast[
        forecast["weeks_since_launch"] <= LAUNCH_WINDOW
    ][SERIES_KEY + ["forecast_week_number", "weeks_since_launch"]].copy()

    print(f"\n  Eligible (focal, week) slots (weeks_since_launch ≤ {LAUNCH_WINDOW}): "
          f"{len(launch_focal_weeks):,}")

    # Pre-index sibling pairs by (focal_upc, retail_account, channel_outlet, geography_raw)
    pairs_indexed = pairs.set_index(
        ["focal_upc", "retail_account", "channel_outlet", "geography_raw"]
    ).sort_index()

    for _, row in launch_focal_weeks.iterrows():
        focal_upc   = row["upc"]
        ret_account = row["retail_account"]
        chan_outlet = row["channel_outlet"]
        geo_raw     = row["geography_raw"]
        wk          = row["forecast_week_number"]
        wsl         = row["weeks_since_launch"]

        focal_key = (focal_upc, ret_account, chan_outlet, geo_raw, wk)
        if focal_key not in df.index:
            continue

        focal_q50 = df.at[focal_key, "forecast_units_base"]

        # Skip focal if not meaningfully present at this retailer this week
        if focal_q50 < MIN_FOCAL_UNITS:
            n_skipped_low_presence += 1
            continue

        # Decay weight: full effect early in launch, fades to 0 at LAUNCH_WINDOW
        decay = max(0.0, 1.0 - (wsl / LAUNCH_WINDOW))

        # Find BUILT siblings for this focal at this (retail, channel, geo)
        idx = (focal_upc, ret_account, chan_outlet, geo_raw)
        if idx not in pairs_indexed.index:
            continue
        sibling_rows = pairs_indexed.loc[[idx]]

        # Cap on total units focal can receive this week
        max_receivable = focal_q50 * MAX_RECEIVE_PCT
        focal_received_so_far = max(0.0, df.at[focal_key, "portfolio_adj_delta"])
        focal_receive_budget = max(0.0, max_receivable - focal_received_so_far)

        if focal_receive_budget <= 0:
            n_skipped_receive_cap += 1
            continue

        total_transfer = 0.0

        for _, pair in sibling_rows.iterrows():
            donor_upc  = pair["donor_upc"]
            cannibal_p = pair["cannibal_prob"]

            donor_key = (donor_upc, ret_account, chan_outlet, geo_raw, wk)
            if donor_key not in df.index:
                continue

            donor_q50_current = df.at[donor_key, "forecast_units_base"]
            if donor_q50_current <= 0:
                continue

            # Donor global budget: at most MAX_TRANSFER_PCT of original forecast total
            donor_already_donated = abs(min(0.0, df.at[donor_key, "portfolio_adj_delta"]))
            donor_q50_original    = donor_q50_current + donor_already_donated
            donor_budget          = max(0.0, donor_q50_original * MAX_TRANSFER_PCT
                                        - donor_already_donated)
            if donor_budget <= 0:
                continue

            raw_transfer    = cannibal_p * donor_q50_original * decay
            # Apply both donor budget and focal receive budget caps
            remaining_focal = focal_receive_budget - total_transfer
            capped_transfer = min(raw_transfer, donor_budget, remaining_focal)
            if capped_transfer <= 1e-6:
                continue

            # Apply to donor
            df.at[donor_key, "forecast_units_base"] -= capped_transfer
            df.at[donor_key, "portfolio_adj_delta"]  -= capped_transfer
            df.at[donor_key, "portfolio_adj_type"]    = "DONOR"
            df.at[donor_key, "portfolio_adj_source_upc"] = focal_upc

            total_transfer += capped_transfer
            n_pairs_applied += 1

            if total_transfer >= focal_receive_budget:
                break  # focal receive budget exhausted

        if total_transfer > 0:
            df.at[focal_key, "forecast_units_base"] += total_transfer
            df.at[focal_key, "portfolio_adj_delta"]  += total_transfer
            df.at[focal_key, "portfolio_adj_type"]    = "FOCAL_LAUNCH"
            total_units_redistributed += total_transfer
            n_series_adjusted.add((focal_upc, ret_account, chan_outlet, geo_raw))

    print(f"    Skipped (low presence < {MIN_FOCAL_UNITS} units/wk): {n_skipped_low_presence:,}")
    print(f"    Skipped (focal receive budget exhausted):             {n_skipped_receive_cap:,}")

    df = df.reset_index()

    # Recompute dollar estimates using anchor_arp
    arp_col = "anchor_arp"
    if arp_col in df.columns:
        df["forecast_dollars_base_adj"] = (
            df["forecast_units_base"] * df[arp_col]
        ).clip(lower=0)
    else:
        df["forecast_dollars_base_adj"] = df["forecast_units_base"] * 3.5  # fallback

    # Clip units to 0 (no negative forecasts)
    df["forecast_units_base"] = df["forecast_units_base"].clip(lower=0)

    print(f"\n  Redistribution applied:")
    print(f"    Series adjusted:          {len(n_series_adjusted):,}")
    print(f"    Pair-week interactions:   {n_pairs_applied:,}")
    print(f"    Total units redistributed: {total_units_redistributed:,.0f}")

    return df


def chart_redistribution(df_adj: pd.DataFrame, out_path: str):
    """Bar chart: weekly redistribution magnitude by retailer."""
    moved = df_adj[df_adj["portfolio_adj_delta"] != 0].copy()
    if moved.empty:
        print("  No redistribution to chart.")
        return

    # Total abs units redistributed per week
    weekly = (
        moved.groupby("forecast_week_number")["portfolio_adj_delta"]
        .apply(lambda x: x[x > 0].sum())
        .reset_index()
    )
    weekly.columns = ["week", "units_received"]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(weekly["week"], weekly["units_received"], color="#2980b9")
    ax.set_xlabel("Forecast Week Number")
    ax.set_ylabel("Units Redistributed (from donors to focals)")
    ax.set_title("MO_55: Portfolio Cannibalization Redistribution by Forecast Week")
    ax.set_xticks(range(1, 14))
    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close()
    print(f"  Chart saved → {out_path}")


def build_summary(df_raw: pd.DataFrame, df_adj: pd.DataFrame) -> pd.DataFrame:
    """Per-series 13-week summary of adjustments (one row per series)."""
    raw_total = (
        df_raw.groupby(SERIES_KEY)["forecast_units_base"]
        .sum()
        .rename("raw_13w_units")
    )
    adj_total = (
        df_adj.groupby(SERIES_KEY)["forecast_units_base"]
        .sum()
        .rename("adj_13w_units")
    )
    delta = (
        df_adj.groupby(SERIES_KEY)["portfolio_adj_delta"]
        .sum()
        .rename("total_adj_delta")
    )
    adj_type = (
        df_adj.groupby(SERIES_KEY)["portfolio_adj_type"]
        .apply(lambda x: x[x != "NONE"].iloc[0] if (x != "NONE").any() else "NONE")
        .rename("portfolio_adj_type")
    )
    wsl_anchor = (
        df_raw.groupby(SERIES_KEY)["weeks_since_launch"]
        .min()
        .rename("wsl_anchor")
    )
    summary = pd.concat(
        [raw_total, adj_total, delta, adj_type, wsl_anchor], axis=1
    ).reset_index()
    summary["total_adj_delta"] = summary["total_adj_delta"].fillna(0)
    summary["adj_pct"] = (
        summary["total_adj_delta"] / summary["raw_13w_units"].clip(lower=0.01) * 100
    )
    summary["portfolio_adj_type"] = summary["portfolio_adj_type"].fillna("NONE")
    return summary


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("MO_55 — Portfolio Cannibalization Constraint")
    print("=" * 70)
    print(f"  LAUNCH_WINDOW:      {LAUNCH_WINDOW} weeks")
    print(f"  CANNIBAL_THRESHOLD: {CANNIBAL_THRESHOLD}")
    print(f"  MAX_TRANSFER_PCT:   {MAX_TRANSFER_PCT * 100:.0f}%")

    # ── 1. Load MO_27 forecast ───────────────────────────────────────────────
    print(f"\n[1] Loading forecast from {FORECAST_PARQUET} …")
    forecast = pd.read_parquet(FORECAST_PARQUET)
    print(f"  Rows: {len(forecast):,} | Series: {forecast.groupby(SERIES_KEY).ngroups:,}")
    print(f"  weeks_since_launch range: "
          f"{forecast['weeks_since_launch'].min()} – {forecast['weeks_since_launch'].max()}")

    wsl_counts = (
        forecast[forecast["weeks_since_launch"] <= LAUNCH_WINDOW]
        .groupby("weeks_since_launch")["upc"].nunique()
    )
    if len(wsl_counts) > 0:
        print(f"  UPCs in launch window (≤{LAUNCH_WINDOW}w):")
        for wsl, n in wsl_counts.items():
            print(f"    week {wsl:>3}: {n} UPCs")
    else:
        print(f"  No UPCs in launch window ≤ {LAUNCH_WINDOW} weeks")

    # ── 2. Load BUILT UPC set ────────────────────────────────────────────────
    print("\n[2] Loading BUILT UPC set …")
    built_upc_set = load_built_upc_set()

    # Cross-check: which forecast UPCs are in BUILT set?
    forecast_upcs = set(forecast["upc"].unique())
    built_in_forecast = forecast_upcs & built_upc_set
    print(f"  Forecast UPCs in BUILT set: {len(built_in_forecast):,} / {len(forecast_upcs):,} total")

    # ── 3. Load cannibalization pairs ────────────────────────────────────────
    print("\n[3] Loading BUILT-to-BUILT cannibalization pairs …")
    pairs = load_cannibalization_pairs(built_upc_set)

    # Filter pairs to only those where donor is also in the forecast
    pairs = pairs[
        pairs["focal_upc"].isin(forecast_upcs) &
        pairs["donor_upc"].isin(forecast_upcs)
    ].copy()
    print(f"  Pairs where both focal+donor have forecasts: {len(pairs):,}")

    if pairs.empty:
        print("\n  No qualifying BUILT-to-BUILT pairs found in forecast — no redistribution.")
        print("  Saving original forecast as adj parquet (no changes).")
        forecast["portfolio_adj_delta"]      = 0.0
        forecast["portfolio_adj_type"]       = "NONE"
        forecast["portfolio_adj_source_upc"] = ""
        forecast["forecast_dollars_base_adj"] = forecast["forecast_dollars_base"]
        forecast.to_parquet(ADJ_PARQUET, index=False)
        print(f"  Saved → {ADJ_PARQUET}")
        raise SystemExit(0)

    # ── 4. Apply portfolio constraint ────────────────────────────────────────
    print("\n[4] Applying portfolio constraint …")
    forecast_raw = forecast.copy()  # preserve for comparison
    forecast_adj = apply_portfolio_constraint(forecast, pairs)

    # ── 5. Validation: portfolio totals ─────────────────────────────────────
    print("\n[5] Validating portfolio totals …")
    # Group by (retail_account, channel_outlet, geography_raw, forecast_week_number)
    # Compare raw vs adj sums — should be equal for zero-sum redistribution
    grp_cols = GROUP_COLS + ["forecast_week_number"]
    raw_totals = (
        forecast_raw[forecast_raw["upc"].isin(built_upc_set)]
        .groupby(grp_cols)["forecast_units_base"]
        .sum()
    )
    adj_totals = (
        forecast_adj[forecast_adj["upc"].isin(built_upc_set)]
        .groupby(grp_cols)["forecast_units_base"]
        .sum()
    )

    delta = (adj_totals - raw_totals).abs()
    max_delta = delta.max()
    mean_delta = delta.mean()
    print(f"  Portfolio total drift (should be near 0):")
    print(f"    Max abs delta:  {max_delta:.4f} units")
    print(f"    Mean abs delta: {mean_delta:.4f} units")
    if max_delta > 0.5:
        print(f"  WARNING: portfolio drift > 0.5 units — check redistribution logic")
    else:
        print(f"  ✓ Zero-sum constraint satisfied")

    # ── 6. Summary table ─────────────────────────────────────────────────────
    print("\n[6] Building series summary …")
    summary = build_summary(forecast_raw, forecast_adj)
    adjusted_series = summary[summary["total_adj_delta"] != 0].sort_values("adj_pct")
    print(f"  Series with non-zero adjustment: {len(adjusted_series):,}")
    if not adjusted_series.empty:
        print(f"\n  Largest donations (13-week totals):")
        donors = adjusted_series[adjusted_series["total_adj_delta"] < 0].head(10)
        if not donors.empty:
            print(donors[["upc", "retail_account", "wsl_anchor",
                          "raw_13w_units", "total_adj_delta", "adj_pct"]].to_string(index=False))
        print(f"\n  Focal launches receiving units (13-week totals):")
        focals = adjusted_series[adjusted_series["total_adj_delta"] > 0].tail(10)
        if not focals.empty:
            print(focals[["upc", "retail_account", "wsl_anchor",
                          "raw_13w_units", "total_adj_delta", "adj_pct"]].to_string(index=False))

    summary.to_csv(SUMMARY_CSV, index=False)
    print(f"\n  Summary saved → {SUMMARY_CSV}")

    # ── 7. Chart ──────────────────────────────────────────────────────────────
    print("\n[7] Generating chart …")
    chart_redistribution(forecast_adj, CHART_PATH)

    # ── 8. Save adjusted parquet ──────────────────────────────────────────────
    print("\n[8] Saving adjusted forecast …")
    forecast_adj.to_parquet(ADJ_PARQUET, index=False)
    print(f"  Saved → {ADJ_PARQUET}")
    print(f"  Rows: {len(forecast_adj):,}")
    print(f"  New columns: portfolio_adj_delta, portfolio_adj_type, "
          f"portfolio_adj_source_upc, forecast_dollars_base_adj")

    # ── 9. Summary ────────────────────────────────────────────────────────────
    total_redistributed = forecast_adj[forecast_adj["portfolio_adj_delta"] > 0][
        "portfolio_adj_delta"
    ].sum()
    pct_of_portfolio = (
        total_redistributed /
        forecast_adj[forecast_adj["upc"].isin(built_upc_set)]["forecast_units_base"].sum()
        * 100
    )

    print(f"\n{'='*70}")
    print("MO_55 COMPLETE")
    print(f"{'='*70}")
    n_focal_series = forecast_adj[forecast_adj["portfolio_adj_type"] == "FOCAL_LAUNCH"].groupby(SERIES_KEY).ngroups
    print(f"  Launch-phase series adjusted:  {n_focal_series:,}")
    print(f"  Total units redistributed:     {total_redistributed:,.0f}")
    print(f"  As % of BUILT portfolio total: {pct_of_portfolio:.2f}%")
    print(f"  Adjusted forecast saved:       {ADJ_PARQUET}")
    print(f"\nNext: review adjusted forecasts, then optionally upload to S3 and ingest")
    print(f"      into Druid as 'retailer_sales_forecast_adj' datasource.")
    print(f"      UI wire-up: SkuRetailerView forecast drawer can show both raw + adj.")
