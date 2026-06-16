"""MO_23 — Build competitor_pack_size_norms.

WHY THIS EXISTS
---------------
The MULO Norms screen previously compared BUILT ARP to an all-of-MULO-food average,
which gives no pricing strategy signal (BUILT bars are not competing against every
food SKU). This script computes pack-step discount norms specifically from competitor
bars/snacks already paired with BUILT in price_competitive_weekly — the universe that
actually matters for pricing decisions.

The key insight: a 4-pack should cost less per bar than a 1-pack. How much less is the
"industry norm" step discount. If BUILT's step discount is smaller than the norm, their
multipack is relatively overpriced vs. competitors.

WHAT IT DOES
------------
1. Loads price_competitive_weekly and deduplicates to one row per
   (competitor_upc, channel_outlet, retail_account, geography_raw) using the latest week.
2. Filters to pack_count values with at least MIN_SKUS competitors (avoids
   one-SKU norms that are just a point estimate).
3. Computes median price_per_bar and velocity_spm by pack_count at three scope levels:
     account  — per (channel_outlet, retail_account)
     channel  — per (channel_outlet), retail_account = "ALL"
     overall  — all data pooled, channel_outlet = retail_account = "ALL"
4. Adds pack_size_bucket label, step_discount_vs_1ct, and norm_scope flag.
5. Writes all three scopes to competitor_pack_size_norms via MinIO → Druid batch.

OUTPUT SCHEMA
-------------
__time                  ISO — run timestamp (Druid timestamp)
norm_scope              str  — "account" | "channel" | "overall"
channel_outlet          str  — actual value or "ALL"
retail_account          str  — actual value or "ALL"
pack_count              int
pack_size_bucket        str  — e.g. "1ct", "4pk", "8pk"
norm_sku_count          int  — distinct competitor UPCs in this bucket × scope
norm_median_price_bar   float — median competitor price per bar
norm_median_velocity    float — median competitor velocity SPM (may be null)
step_discount_vs_1ct    float — (1ct norm - this_pack norm) / 1ct norm; null for 1ct rows
scored_at               str  — ISO UTC run timestamp

API USAGE
---------
In get_norms(), cascade:
  1. SELECT from competitor_pack_size_norms WHERE norm_scope='account' AND channel=... AND account=...
  2. If count < MIN_SKUS, fall back to norm_scope='channel' WHERE channel=...
  3. If still sparse, fall back to norm_scope='overall'
Then join BUILT's own pack-step discounts from built_prepost_features for comparison.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

MIN_SKUS  = 3   # minimum distinct competitor SKUs to publish a norm row
SCORED_AT = datetime.now(timezone.utc).isoformat()
RUN_TIME  = SCORED_AT  # Druid __time


def _pack_bucket(pack_count: int) -> str:
    if pack_count == 1:
        return "1ct"
    if pack_count <= 3:
        return "2-3pk"
    if pack_count <= 5:
        return "4pk"
    if pack_count <= 9:
        return "8pk"
    if pack_count <= 14:
        return "12pk"
    if pack_count <= 17:
        return "16pk"
    if pack_count <= 20:
        return "18pk"
    return f"{pack_count}pk"


def _add_step_discount(df: pd.DataFrame) -> pd.DataFrame:
    """Add step_discount_vs_1ct within each (norm_scope, channel_outlet, retail_account) group."""
    ref = (
        df[df["pack_count"] == 1]
        .set_index(["norm_scope", "channel_outlet", "retail_account"])["norm_median_price_bar"]
        .rename("ref_price_1ct")
    )
    df = df.join(ref, on=["norm_scope", "channel_outlet", "retail_account"])
    df["step_discount_vs_1ct"] = np.where(
        (df["pack_count"] == 1) | df["ref_price_1ct"].isna() | (df["ref_price_1ct"] == 0),
        np.nan,
        (df["ref_price_1ct"] - df["norm_median_price_bar"]) / df["ref_price_1ct"],
    )
    df["step_discount_vs_1ct"] = df["step_discount_vs_1ct"].round(4)
    return df.drop(columns=["ref_price_1ct"])


def _aggregate(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    agg = (
        df.groupby(group_cols + ["pack_count"])
        .agg(
            norm_sku_count     =("competitor_upc", "nunique"),
            norm_median_price_bar=("competitor_price_per_bar", "median"),
            norm_median_velocity =("competitor_velocity_spm",  "median"),
        )
        .reset_index()
    )
    agg = agg[agg["norm_sku_count"] >= MIN_SKUS].copy()
    agg["pack_size_bucket"]      = agg["pack_count"].apply(_pack_bucket)
    agg["norm_median_price_bar"] = agg["norm_median_price_bar"].round(4)
    agg["norm_median_velocity"]  = agg["norm_median_velocity"].round(4)
    return agg


if __name__ == "__main__":

    # ── 1. Load price_competitive_weekly — aggregated in SQL ─────────────────
    # Push aggregation to Druid to avoid streaming the full table.
    # Filter to last 26 weeks and average price/velocity per (competitor_upc, dims).
    print("Loading price_competitive_weekly (last 26 weeks, aggregated in SQL)...")
    raw = query_druid("""
        SELECT
            channel_outlet,
            retail_account,
            geography_raw,
            competitor_upc,
            competitor_pack_count,
            AVG(competitor_price_per_bar) AS competitor_price_per_bar,
            AVG(competitor_velocity_spm)  AS competitor_velocity_spm
        FROM "price_competitive_weekly"
        WHERE competitor_price_per_bar IS NOT NULL
          AND competitor_pack_count    IS NOT NULL
          AND __time >= TIMESTAMPADD(WEEK, -26, CURRENT_TIMESTAMP)
        GROUP BY
            channel_outlet, retail_account, geography_raw,
            competitor_upc, competitor_pack_count
    """, timeout=300)
    print(f"  Rows (one per competitor × dims): {len(raw):,}")

    if raw.empty:
        raise SystemExit("No data in price_competitive_weekly for the last 26 weeks — check Druid.")

    # ── 2. Type coercion (SQL GROUP BY already deduped) ───────────────────────
    raw["competitor_pack_count"]    = pd.to_numeric(raw["competitor_pack_count"], errors="coerce")
    raw["competitor_price_per_bar"] = pd.to_numeric(raw["competitor_price_per_bar"], errors="coerce")
    raw["competitor_velocity_spm"]  = pd.to_numeric(raw["competitor_velocity_spm"], errors="coerce")

    dedup = (
        raw
        .dropna(subset=["competitor_pack_count", "competitor_price_per_bar"])
        .copy()
    )
    dedup["competitor_pack_count"] = dedup["competitor_pack_count"].astype(int)
    dedup = dedup.rename(columns={"competitor_pack_count": "pack_count"})
    print(f"  Valid rows after type coercion: {len(dedup):,}")

    # ── 3. Compute norms at three scope levels ────────────────────────────────

    # Account scope
    print("\nAggregating at account scope...")
    acct = _aggregate(dedup, ["channel_outlet", "retail_account"])
    acct["norm_scope"]     = "account"
    acct["geography_raw"]  = "ALL"
    print(f"  Rows: {len(acct):,}")

    # Channel scope (pool across all accounts in a channel)
    print("Aggregating at channel scope...")
    chan_df = dedup.copy()
    chan_df["retail_account"] = "ALL"
    chan = _aggregate(chan_df, ["channel_outlet", "retail_account"])
    chan["norm_scope"]     = "channel"
    chan["geography_raw"]  = "ALL"
    print(f"  Rows: {len(chan):,}")

    # Overall scope
    print("Aggregating at overall scope...")
    ovr_df = dedup.copy()
    ovr_df["channel_outlet"] = "ALL"
    ovr_df["retail_account"] = "ALL"
    ovr = _aggregate(ovr_df, ["channel_outlet", "retail_account"])
    ovr["norm_scope"]     = "overall"
    ovr["geography_raw"]  = "ALL"
    print(f"  Rows: {len(ovr):,}")

    # ── 4. Combine, add step discounts ────────────────────────────────────────
    combined = pd.concat([acct, chan, ovr], ignore_index=True)
    combined = _add_step_discount(combined)

    combined["pack_count"]    = combined["pack_count"].astype(int)
    combined["norm_sku_count"] = combined["norm_sku_count"].astype(int)
    combined["scored_at"]     = SCORED_AT
    combined["__time"]        = RUN_TIME

    col_order = [
        "__time", "norm_scope",
        "channel_outlet", "retail_account", "geography_raw",
        "pack_count", "pack_size_bucket",
        "norm_sku_count",
        "norm_median_price_bar", "norm_median_velocity",
        "step_discount_vs_1ct",
        "scored_at",
    ]
    combined = combined[col_order]

    print(f"\nTotal norm rows: {len(combined):,}")
    print(combined.groupby("norm_scope")["norm_scope"].count().to_string())
    print("\nSample:")
    print(combined.head(10).to_string(index=False))

    # ── 5. Write back ─────────────────────────────────────────────────────────
    write_back(
        combined,
        datasource="competitor_pack_size_norms",
        timestamp_col="__time",
    )
