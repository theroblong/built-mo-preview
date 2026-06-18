"""MO_25 — Build retailer_sales_weekly: historical panel for sales forecasting.

WHY THIS EXISTS
---------------
The existing pipeline (MO_19–21) forecasts cannibalization rates, not absolute
sales volumes. Finance and account management need forward-looking dollar sales
by retailer per SKU — "what will Walmart sell next quarter?" This script builds
the weekly panel data that feeds the MO_26 training step.

DATA SOURCES
------------
1. event_detection_weekly  — foundation: base_units, velocity, TDP, pre-computed
                             rolling stats, z-scores (covers all BUILT UPCs post-Q6)
2. built_filtered_weekly   — joined for weekly `arp` (average retail price per week),
                             the raw SPINS measure not carried into event_detection_weekly.
                             Weekly ARP is critical: price trend over time is one of the
                             strongest forward-looking signals.
3. built_prepost_features  — description, first_week_selling (→ weeks_since_launch),
                             pack_count, post_13w_arp (fallback if weekly arp missing)
4. scored_price_elasticity — implied_elasticity, elasticity_band per (upc, channel,
                             account, geo). Static signal: price sensitivity context.
5. scored_cannibalization  — max_donor_cannibal_prob, donor_count aggregated per focal.
                             Competitive pressure context for the forecast.

OUTPUT SCHEMA (retailer_sales_weekly.parquet)
---------------------------------------------
__time                    str ISO  — SPINS week timestamp
upc                       str
description               str
channel_outlet            str
retail_account            str
geography_raw             str
geography_display         str
geography_level           str
first_week_selling        str ISO  — lifecycle anchor
weeks_since_launch        int      — 0-indexed; negative = pre-launch (clipped to 0)
pack_count                int
base_units                float    — primary demand signal (promo-stripped)
avg_weekly_units_spm      float    — velocity
tdp                       float    — distribution proxy
arp                       float    — weekly avg retail price (from built_filtered_weekly)
arp_fallback              int      — 1 if arp came from built_prepost_features fallback
base_units_roll4_avg      float    — pre-computed rolling stats from event_detection_weekly
base_units_roll8_avg      float
base_units_roll8_std      float
base_units_roll13_avg     float
base_units_roll13_std     float
base_units_wow_delta      float
base_units_z8             float
base_units_z13            float
velocity_spm_roll8_avg    float
velocity_spm_roll13_avg   float
velocity_spm_z8           float
velocity_spm_z13          float
tdp_z8                    float
arp_lag1                  float    — computed in Python
arp_lag4                  float
arp_roll8_avg             float
arp_roll8_std             float
arp_wow_delta             float    — week-over-week ARP change (captures price moves)
base_units_lag1           float    — autoregressive lags (no data leakage)
base_units_lag4           float
base_units_lag13          float
week_of_year              int      — seasonality signal
implied_elasticity        float    — from scored_price_elasticity (static per series)
elasticity_band           str
max_donor_cannibal_prob   float    — from scored_cannibalization (static per focal)
donor_count               int
scored_at                 str ISO
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

SCORED_AT      = datetime.now(timezone.utc).isoformat()
LOOKBACK       = "INTERVAL '3' YEAR"   # full available SPINS history
GROUP_COLS     = ["upc", "channel_outlet", "retail_account", "geography_raw"]
MIN_WEEKS      = 13                     # series shorter than this are dropped


if __name__ == "__main__":
    # ── 1. Foundation: event_detection_weekly ───────────────────────────────
    print("Loading event_detection_weekly …")
    edw = query_druid(f"""
        SELECT
            __time,
            upc,
            channel_outlet,
            retail_account,
            geography_raw,
            geography_display,
            geography_level,
            base_units,
            avg_weekly_units_spm,
            tdp,
            base_units_roll4_avg,
            base_units_roll8_avg,
            base_units_roll8_std,
            base_units_roll13_avg,
            base_units_roll13_std,
            base_units_wow_delta,
            base_units_z8,
            base_units_z13,
            velocity_spm_roll8_avg,
            velocity_spm_roll13_avg,
            velocity_spm_z8,
            velocity_spm_z13,
            tdp_z8
        FROM "event_detection_weekly"
        WHERE __time >= CURRENT_TIMESTAMP - {LOOKBACK}
          AND retail_account IS NOT NULL
          AND retail_account <> ''
    """)
    print(f"  Rows: {len(edw):,} | UPCs: {edw['upc'].nunique()} "
          f"| Date range: {edw['__time'].min()[:10]} – {edw['__time'].max()[:10]}")

    edw_num = [
        "base_units", "avg_weekly_units_spm", "tdp",
        "base_units_roll4_avg", "base_units_roll8_avg", "base_units_roll8_std",
        "base_units_roll13_avg", "base_units_roll13_std",
        "base_units_wow_delta", "base_units_z8", "base_units_z13",
        "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
        "velocity_spm_z8", "velocity_spm_z13", "tdp_z8",
    ]
    for c in edw_num:
        if c in edw.columns:
            edw[c] = pd.to_numeric(edw[c], errors="coerce")

    edw = edw.drop_duplicates(subset=["__time"] + GROUP_COLS)
    edw["__time"] = pd.to_datetime(edw["__time"], utc=True)

    # ── 2. Raw SPINS weekly ARP — built_filtered_weekly ─────────────────────
    # Weekly avg retail price is NOT carried into event_detection_weekly.
    # It's one of the strongest leading signals: a price cut 2–4 weeks out
    # typically drives measurable unit lift, and vice versa for price increases.
    print("\nLoading built_filtered_weekly for weekly ARP …")
    bfw = query_druid(f"""
        SELECT
            __time,
            upc,
            channel_outlet,
            retail_account,
            geography_raw,
            arp
        FROM "built_filtered_weekly"
        WHERE __time >= CURRENT_TIMESTAMP - {LOOKBACK}
          AND retail_account IS NOT NULL
          AND retail_account <> ''
          AND arp > 0
    """)
    print(f"  Rows: {len(bfw):,}")
    bfw["arp"] = pd.to_numeric(bfw["arp"], errors="coerce")
    bfw = bfw.drop_duplicates(subset=["__time"] + GROUP_COLS)
    bfw["__time"] = pd.to_datetime(bfw["__time"], utc=True)

    # ── 3. Merge ARP onto event_detection_weekly ─────────────────────────────
    df = edw.merge(bfw, on=["__time"] + GROUP_COLS, how="left")
    df["arp_fallback"] = 0
    print(f"\n  After ARP join: {len(df):,} rows | ARP coverage: "
          f"{df['arp'].notna().sum():,} / {len(df):,}")

    # ── 4. Prepost: description, first_week_selling, pack_count, arp fallback
    print("\nLoading built_prepost_features …")
    pp = query_druid("""
        SELECT
            upc,
            description,
            channel_outlet,
            retail_account,
            geography_raw,
            first_week_selling,
            pack_count,
            post_13w_arp
        FROM "built_prepost_features"
        WHERE retail_account IS NOT NULL
          AND retail_account <> ''
    """)
    pp = pp.drop_duplicates(subset=GROUP_COLS)
    pp["pack_count"]   = pd.to_numeric(pp["pack_count"], errors="coerce").fillna(1).astype(int)
    pp["post_13w_arp"] = pd.to_numeric(pp["post_13w_arp"], errors="coerce")

    df = df.merge(pp[GROUP_COLS + ["description", "first_week_selling", "pack_count", "post_13w_arp"]],
                  on=GROUP_COLS, how="left")

    # Fill missing weekly ARP from post_13w_arp (period average fallback)
    arp_missing = df["arp"].isna()
    df.loc[arp_missing, "arp"] = df.loc[arp_missing, "post_13w_arp"]
    df.loc[arp_missing, "arp_fallback"] = 1
    df = df.drop(columns=["post_13w_arp"])

    # ── 5. Weeks since launch ────────────────────────────────────────────────
    df["first_week_selling"] = pd.to_datetime(df["first_week_selling"], utc=True, errors="coerce")
    df["weeks_since_launch"] = (
        (df["__time"] - df["first_week_selling"]).dt.days // 7
    ).clip(lower=0).fillna(0).astype(int)

    # ── 6. Elasticity: implied_elasticity, elasticity_band ──────────────────
    print("Loading scored_price_elasticity …")
    elas = query_druid("""
        SELECT
            upc,
            channel_outlet,
            retail_account,
            geography_raw,
            implied_elasticity,
            elasticity_band
        FROM "scored_price_elasticity"
        WHERE retail_account IS NOT NULL
          AND implied_elasticity BETWEEN -10 AND 5
    """)
    elas = elas.drop_duplicates(subset=GROUP_COLS)
    elas["implied_elasticity"] = pd.to_numeric(elas["implied_elasticity"], errors="coerce")
    df = df.merge(elas, on=GROUP_COLS, how="left")

    # ── 7. Cannibal pressure: max_donor_cannibal_prob, donor_count ───────────
    print("Loading scored_cannibalization for donor pressure …")
    can = query_druid("""
        SELECT
            focal_upc AS upc,
            channel_outlet,
            retail_account,
            geography_raw,
            MAX(CAST(cannibal_prob AS DOUBLE)) AS max_donor_cannibal_prob,
            COUNT(*) AS donor_count
        FROM "scored_cannibalization"
        WHERE retail_account IS NOT NULL
        GROUP BY 1, 2, 3, 4
    """)
    can = can.drop_duplicates(subset=GROUP_COLS)
    can["max_donor_cannibal_prob"] = pd.to_numeric(can["max_donor_cannibal_prob"], errors="coerce").fillna(0)
    can["donor_count"]             = pd.to_numeric(can["donor_count"], errors="coerce").fillna(0).astype(int)
    df = df.merge(can, on=GROUP_COLS, how="left")
    df["max_donor_cannibal_prob"] = df["max_donor_cannibal_prob"].fillna(0)
    df["donor_count"]             = df["donor_count"].fillna(0).astype(int)

    # ── 8. Time-series feature engineering (no data leakage) ────────────────
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    df["week_of_year"] = df["__time"].dt.isocalendar().week.astype(int)

    # Autoregressive lags on base_units (past-only, no leakage)
    for lag, col in [(1, "base_units_lag1"), (4, "base_units_lag4"), (13, "base_units_lag13")]:
        df[col] = df.groupby(GROUP_COLS)["base_units"].shift(lag)

    # ARP rolling stats and lags (price trend signal)
    for lag, col in [(1, "arp_lag1"), (4, "arp_lag4")]:
        df[col] = df.groupby(GROUP_COLS)["arp"].shift(lag)

    df["arp_wow_delta"]   = df["arp"] - df["arp_lag1"]
    df["arp_roll8_avg"]   = (
        df.groupby(GROUP_COLS)["arp"]
          .transform(lambda s: s.shift(1).rolling(8, min_periods=2).mean())
    )
    df["arp_roll8_std"]   = (
        df.groupby(GROUP_COLS)["arp"]
          .transform(lambda s: s.shift(1).rolling(8, min_periods=2).std())
    )

    # ── 9. Quality filters ───────────────────────────────────────────────────
    # Drop series with fewer than MIN_WEEKS usable rows
    series_len = df.groupby(GROUP_COLS)["base_units"].transform("count")
    before = len(df)
    df = df[series_len >= MIN_WEEKS].copy()
    print(f"\n  Dropped {before - len(df):,} rows from series with < {MIN_WEEKS} weeks")

    # Drop rows where base_units lag1 is not yet available (first row per series)
    df = df.dropna(subset=["base_units_lag1"]).copy()

    # ── 10. Assemble output ──────────────────────────────────────────────────
    df["first_week_selling"] = df["first_week_selling"].dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    df["scored_at"] = SCORED_AT

    output_cols = [
        "__time",
        "upc", "description",
        "channel_outlet", "retail_account", "geography_raw", "geography_display", "geography_level",
        "first_week_selling", "weeks_since_launch", "pack_count",
        "base_units", "avg_weekly_units_spm", "tdp", "arp", "arp_fallback",
        "base_units_roll4_avg",
        "base_units_roll8_avg",  "base_units_roll8_std",
        "base_units_roll13_avg", "base_units_roll13_std",
        "base_units_wow_delta",  "base_units_z8", "base_units_z13",
        "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
        "velocity_spm_z8", "velocity_spm_z13", "tdp_z8",
        "arp_lag1", "arp_lag4", "arp_roll8_avg", "arp_roll8_std", "arp_wow_delta",
        "base_units_lag1", "base_units_lag4", "base_units_lag13",
        "week_of_year",
        "implied_elasticity", "elasticity_band",
        "max_donor_cannibal_prob", "donor_count",
        "scored_at",
    ]
    out = df[[c for c in output_cols if c in df.columns]].copy()

    print(f"\n  Total retailer_sales_weekly rows: {len(out):,}")
    print(f"  Weeks covered:  {out['__time'].nunique():,}")
    print(f"  Unique UPCs:    {out['upc'].nunique():,}")
    print(f"  Series (upc×retailer×channel): {out.groupby(GROUP_COLS).ngroups:,}")
    print(f"  ARP fallback:   {out['arp_fallback'].sum():,} rows ({out['arp_fallback'].mean()*100:.1f}%)")
    print(f"  Base units range: {out['base_units'].min():.0f} – {out['base_units'].max():.0f}")
    print(f"  ARP range:        ${out['arp'].min():.2f} – ${out['arp'].max():.2f}")

    out.to_parquet("outputs/retailer_sales_weekly.parquet", index=False)
    print("\n  Saved → outputs/retailer_sales_weekly.parquet")
