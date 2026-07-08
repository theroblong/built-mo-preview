"""MO_25 v8 — Build retailer_sales_weekly: historical panel for sales forecasting.

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
2. built_filtered_weekly   — (a) focal BUILT UPCs: weekly arp + promo units
                             (b) top-3 donors per focal: competitor TDP, units, ARP
                             (c) aggregated all brands: category TDP + category units
3. built_prepost_features  — description, first_week_selling, pack_count;
                             post_13w_arp retained only as last-resort ARP fallback
4. scored_price_elasticity — implied_elasticity, elasticity_band per series (static)
5. scored_cannibalization  — (a) max_donor_cannibal_prob, donor_count (static)
                             (b) top-3 donor UPC identities (for step 2b above)

ARP FALLBACK CASCADE (v4 change from v3)
----------------------------------------
v3 used post_13w_arp (launch-period price) when live ARP was missing.
v4 uses a three-tier cascade to maximise recency:
  Tier 1: live ARP from built_filtered_weekly         arp_source = "live"
  Tier 2: rolling 13w mean of past live ARPs           arp_source = "roll13"
  Tier 3: post_13w_arp from built_prepost_features     arp_source = "prepost"
The arp_source audit column documents which tier each row used.

PROMO SIGNALS (v5 update from v4)
-----------------------------------
v4 used arp_discount_pct (percentage-based: 5% of $10 = $0.50 threshold — too wide).
v5 fixes detection to use absolute dollar discount ≥ $0.05 (nickel standard):
  units_promo present → is_promo_units (promo_intensity > 10%)
  units_promo absent  → is_promo_arp (arp_dollar_discount > $0.05)
New: promo_lift_ratio = total_units / base_units − 1 (display lift independent of price)
promo_source audit column: "units_promo" | "arp_inferred" | "none"

DONOR SIGNALS — BRAND-SPLIT (v5 addition)
------------------------------------------
Intra-BUILT cannibalization (own-brand donor steals from focal SKU) and competitor
cannibalization are fundamentally different signals and tracked separately.
Donor UPCs are classified via built_upc_set (all focal BUILT UPCs in EDW):
  competitor_donor_count   — donors from other brands (market share dynamics)
  competitor_donor_tdp_sum — TDP of competitor donors (external shelf pressure)
  competitor_donor_units_sum / _arp_wavg / _units_wow
  competitor_price_gap     — focal ARP vs competitor donor TDP-weighted ARP
  built_donor_count        — donors that are BUILT sibling SKUs (own-brand cannibal risk)
  built_donor_tdp_sum      — TDP of BUILT sibling donors
  built_donor_units_wow    — sibling unit acceleration (cannibalization leading indicator)
top_donor_* (mixed BUILT+competitor) retained for backward compatibility.

TDP CHANGE SIGNALS (v5 addition)
----------------------------------
Raw tdp (absolute distribution level) and tdp_z8 are already in the feature set.
Distribution *growth* is the CPG-proven leading indicator, not the level or share.
  tdp_wow_delta    — WoW stores gained/lost (distribution expansion speed)
  tdp_4w_momentum  — 4-week net distribution change (monthly trend direction)
built_tdp_share (focal/category ratio) retained as audit column; not a model feature.

CATEGORY / SHELF SIGNALS (v4 addition)
----------------------------------------
category_tdp_sum  — total TDP of ALL brands at same channel×retailer×geo×week (audit)
built_tdp_share   — focal TDP / category_tdp_sum (audit only; not a model feature)

HOLIDAY / SEASONAL FLAGS (v4 + v6 update)
------------------------------------------
holiday_week — integer code (audit only; ordinal encoding conflates event magnitudes)
  1 = New Year health kick (w1–2)
  2 = Super Bowl (w5)
  3 = Memorial Day (w21)
  4 = Labor Day (w36)
  5 = Thanksgiving / Black Friday (w47)
  6 = Christmas / Holiday (w52)

v6 adds per-event binary flags so the model can learn each event's magnitude
independently (New Year protein bar spike >> Super Bowl for this category):
  is_new_year_week      — weeks 1–2 (New Year health resolution spike)
  is_superbowl_week     — week 5
  is_memorial_day_week  — week 21
  is_labor_day_week     — week 36
  is_thanksgiving_week  — week 47
  is_christmas_week     — week 52

CANNIBALIZATION RATE — TIME-VARYING SIGNAL (v7 addition)
----------------------------------------------------------
Previous versions used `scored_cannibalization.cannibal_prob` — a one-time static score,
identical every week per (focal, donor) pair. In a temporal model this has ICC=1.0:
zero week-to-week predictive power (confirmed MO_41).

`cannibalization_rate_weekly` (MO_19 output) is already aggregated to (focal, week):
  cannibalization_rate = sum(cannibal_prob × max(0, -donor_wow_delta)) / focal_base_units

It rises when sibling donors are accelerating at the focal's expense, fades as consumers
habituate. This IS time-varying signal we want. The MO_50 failure (73% null) was simply
because null = focal not in any active cannibal pair = 0 pressure — not missing data.
Fix: join + fillna(0). New column: `cannibal_rate` (float 0–1, filled to 0 when no pair).

ELASTICITY INTERACTION TERM (v7 addition)
------------------------------------------
`implied_elasticity` (ε) is static per (upc, retailer). Used standalone it's constant
per series — same ICC problem. ε is a multiplier: its value is realized only when price
actually changes. Correct feature: `price_elasticity_effect = arp_pct_change × ε`.
  arp_pct_change = (arp − arp_lag1) / arp_lag1  (signed: negative when price drops)
  price_elasticity_effect = arp_pct_change × implied_elasticity
When price drops 5% and ε=−1.8 → effect=+0.09 (expected +9% demand lift).
Time-varying, nonzero only in price-event weeks, causally interpretable.
Null ε → 0. Clipped to [−1.5, 1.5] to suppress outliers.

AUDIT COLUMNS (not model features)
------------------------------------
arp_source        str   — "live" | "roll13" | "prepost"
promo_source      str   — "units_promo" | "arp_inferred" | "none"
arp_discount_pct  float — % drop vs 8w baseline (audit; model uses arp_dollar_discount)
category_tdp_sum  float — denominator for built_tdp_share
built_tdp_share   float — BUILT shelf share (audit; model uses tdp_wow_delta / tdp_4w_momentum)
arp_pct_change    float — signed % price change WoW (audit; model uses price_elasticity_effect)

OUTPUT SCHEMA (retailer_sales_weekly.parquet)
---------------------------------------------
Existing columns preserved; new v5 columns appended.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from mo_druid_client import query_druid

SCORED_AT  = datetime.now(timezone.utc).isoformat()
LOOKBACK   = "INTERVAL '3' YEAR"
GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]
MIN_WEEKS  = 13

HOLIDAY_WEEK_MAP = {
    1: 1, 2: 1,   # New Year health kick
    5: 2,          # Super Bowl
    21: 3,         # Memorial Day
    36: 4,         # Labor Day
    47: 5,         # Thanksgiving / Black Friday
    52: 6,         # Christmas / Holiday
}

TOP_N_DONORS = 3   # how many top donors to aggregate for competitor signals


if __name__ == "__main__":

    # ── 1. Foundation: event_detection_weekly ───────────────────────────────
    print("=" * 70)
    print("MO_25 v8 — Retailer Sales Actuals")
    print("=" * 70)
    print("\n[1] Loading event_detection_weekly …")
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
          f"| Range: {edw['__time'].min()[:10]} – {edw['__time'].max()[:10]}")

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

    # Capture BUILT UPC universe — used in step 8 to classify donors as own-brand vs competitor
    built_upc_set = set(edw["upc"].unique())
    print(f"  BUILT focal UPCs: {len(built_upc_set):,}")

    # ── 2. Focal brand weekly ARP + promo units ──────────────────────────────
    print("\n[2] Loading focal ARP + promo units from built_filtered_weekly …")
    bfw = query_druid(f"""
        SELECT
            __time,
            upc,
            channel_outlet,
            retail_account,
            geography_raw,
            arp,
            units_promo,
            units_non_promo
        FROM "built_filtered_weekly"
        WHERE __time >= CURRENT_TIMESTAMP - {LOOKBACK}
          AND retail_account IS NOT NULL
          AND retail_account <> ''
          AND arp > 0
    """)
    print(f"  Rows: {len(bfw):,} | ARP coverage: {bfw['arp'].notna().sum():,}")
    for c in ["arp", "units_promo", "units_non_promo"]:
        bfw[c] = pd.to_numeric(bfw[c], errors="coerce")
    bfw = bfw.drop_duplicates(subset=["__time"] + GROUP_COLS)
    bfw["__time"] = pd.to_datetime(bfw["__time"], utc=True)

    # ── 3. Merge focal ARP + promo onto foundation ───────────────────────────
    print("\n[3] Merging focal ARP + promo onto event_detection_weekly …")
    df = edw.merge(bfw, on=["__time"] + GROUP_COLS, how="left")
    df["arp_fallback"] = 0
    df["arp_source"]   = "live"
    df["total_units"]  = df["base_units"] + df["units_promo"].fillna(0)
    print(f"  Rows after merge: {len(df):,} | "
          f"Live ARP: {df['arp'].notna().sum():,} / {len(df):,} "
          f"({df['arp'].notna().mean()*100:.1f}%) | "
          f"Promo coverage: {df['units_promo'].notna().sum():,} / {len(df):,} "
          f"({df['units_promo'].notna().mean()*100:.1f}%)")

    # ── 4. Metadata: description, first_week_selling, pack_count ────────────
    print("\n[4] Loading built_prepost_features …")
    pp = query_druid("""
        SELECT
            upc,
            channel_outlet,
            retail_account,
            geography_raw,
            description,
            first_week_selling,
            pack_count,
            post_13w_arp
        FROM "built_prepost_features"
        WHERE retail_account IS NOT NULL
          AND retail_account <> ''
    """)
    pp = pp.drop_duplicates(subset=GROUP_COLS)
    pp["pack_count"]   = pd.to_numeric(pp["pack_count"],   errors="coerce").fillna(1).astype(int)
    pp["post_13w_arp"] = pd.to_numeric(pp["post_13w_arp"], errors="coerce")
    df = df.merge(pp[GROUP_COLS + ["description", "first_week_selling", "pack_count", "post_13w_arp"]],
                  on=GROUP_COLS, how="left")

    # ── 5. Weeks since launch ────────────────────────────────────────────────
    df["first_week_selling"] = pd.to_datetime(df["first_week_selling"], utc=True, errors="coerce")
    df["weeks_since_launch"] = (
        (df["__time"] - df["first_week_selling"]).dt.days // 7
    ).clip(lower=0).fillna(0).astype(int)

    # ── 6. ARP fallback cascade (v4: rolling 13w > post_13w_arp) ────────────
    # Sort first so rolling windows are computed in chronological order
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    # Tier 2: rolling 13w mean of PAST live ARP values (shift(1) = no leakage)
    df["_arp_roll13_fallback"] = (
        df.groupby(GROUP_COLS)["arp"]
        .transform(lambda s: s.shift(1).rolling(13, min_periods=4).mean())
    )

    # Apply cascade: Tier 2 first (more recent than Tier 3)
    mask_t2 = df["arp"].isna() & df["_arp_roll13_fallback"].notna()
    df.loc[mask_t2, "arp"]        = df.loc[mask_t2, "_arp_roll13_fallback"]
    df.loc[mask_t2, "arp_fallback"] = 1
    df.loc[mask_t2, "arp_source"] = "roll13"

    # Tier 3: post_13w_arp from built_prepost_features (last resort — stale)
    mask_t3 = df["arp"].isna() & df["post_13w_arp"].notna()
    df.loc[mask_t3, "arp"]          = df.loc[mask_t3, "post_13w_arp"]
    df.loc[mask_t3, "arp_fallback"] = 1
    df.loc[mask_t3, "arp_source"]   = "prepost"

    df = df.drop(columns=["_arp_roll13_fallback", "post_13w_arp"])

    arp_src = df["arp_source"].value_counts()
    print(f"\n  ARP source breakdown: live={arp_src.get('live', 0):,}  "
          f"roll13={arp_src.get('roll13', 0):,}  "
          f"prepost={arp_src.get('prepost', 0):,}  "
          f"null={df['arp'].isna().sum():,}")

    # ── 7. Price elasticity ──────────────────────────────────────────────────
    print("\n[7] Loading scored_price_elasticity …")
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

    # ── 8. Cannibalization — static signals + donor identity ─────────────────
    print("\n[8] Loading scored_cannibalization …")
    can_full = query_druid("""
        SELECT
            focal_upc,
            donor_upc,
            channel_outlet,
            retail_account,
            geography_raw,
            CAST(cannibal_prob AS DOUBLE) AS cannibal_prob
        FROM "scored_cannibalization"
        WHERE retail_account IS NOT NULL
    """)
    can_full["cannibal_prob"] = pd.to_numeric(can_full["cannibal_prob"], errors="coerce")

    focal_group = ["focal_upc", "channel_outlet", "retail_account", "geography_raw"]

    # 8a. Static aggregate signals — split by own-brand vs competitor donors
    # Intra-BUILT cannibalization (own SKU → own SKU) ≠ competitor market share dynamics
    can_full["_donor_is_built"] = can_full["donor_upc"].isin(built_upc_set)

    can_agg = can_full.groupby(focal_group).agg(
        max_donor_cannibal_prob=("cannibal_prob", "max"),
        donor_count=("donor_upc", "count"),
    ).reset_index().rename(columns={"focal_upc": "upc"})

    _comp_donors = can_full[~can_full["_donor_is_built"]]
    _comp_agg = (
        _comp_donors.groupby(focal_group)
        .agg(competitor_donor_count=("donor_upc", "count"))
        .reset_index().rename(columns={"focal_upc": "upc"})
    )

    _built_donors_pool = can_full[can_full["_donor_is_built"]]
    _built_agg = (
        _built_donors_pool.groupby(focal_group)
        .agg(built_donor_count=("donor_upc", "count"))
        .reset_index().rename(columns={"focal_upc": "upc"})
    )

    can_agg = (
        can_agg
        .merge(_comp_agg,  on=GROUP_COLS, how="left")
        .merge(_built_agg, on=GROUP_COLS, how="left")
    )
    can_agg["max_donor_cannibal_prob"]  = can_agg["max_donor_cannibal_prob"].fillna(0)
    can_agg["donor_count"]              = can_agg["donor_count"].fillna(0).astype(int)
    can_agg["competitor_donor_count"]   = can_agg["competitor_donor_count"].fillna(0).astype(int)
    can_agg["built_donor_count"]        = can_agg["built_donor_count"].fillna(0).astype(int)

    df = df.merge(can_agg, on=GROUP_COLS, how="left")
    df["max_donor_cannibal_prob"]  = df["max_donor_cannibal_prob"].fillna(0)
    df["donor_count"]              = df["donor_count"].fillna(0).astype(int)
    df["competitor_donor_count"]   = df["competitor_donor_count"].fillna(0).astype(int)
    df["built_donor_count"]        = df["built_donor_count"].fillna(0).astype(int)
    print(f"  Donor split: "
          f"competitor_donors avg={df['competitor_donor_count'].mean():.2f}  "
          f"built_donors avg={df['built_donor_count'].mean():.2f}")

    # 8b. Top-N donor identities (for competitor weekly signals in step 9)
    can_full["_rank"] = can_full.groupby(focal_group)["cannibal_prob"].rank(
        ascending=False, method="first"
    )
    top_donors = can_full[can_full["_rank"] <= TOP_N_DONORS].copy()
    donor_upcs = top_donors["donor_upc"].unique().tolist()
    print(f"  Focal series: {len(can_agg):,} | "
          f"Unique top-{TOP_N_DONORS} donor UPCs: {len(donor_upcs):,}")

    # ── 8c. Cannibalization rate — time-varying focal pressure ───────────────
    # cannibalization_rate_weekly is already (focal, week) aggregated from MO_19.
    # null = focal not in any active cannibalization pair = 0 pressure, NOT missing.
    print("\n[8c] Loading cannibalization_rate_weekly …")
    crw = query_druid(f"""
        SELECT
            __time,
            focal_upc,
            channel_outlet,
            retail_account,
            geography_raw,
            CAST(cannibalization_rate AS DOUBLE) AS cannibal_rate
        FROM "cannibalization_rate_weekly"
        WHERE __time >= CURRENT_TIMESTAMP - {LOOKBACK}
          AND retail_account IS NOT NULL
          AND retail_account <> ''
    """)
    crw["__time"]       = pd.to_datetime(crw["__time"], utc=True)
    crw["cannibal_rate"] = pd.to_numeric(crw["cannibal_rate"], errors="coerce").clip(0, 1)
    crw = crw.drop_duplicates(
        subset=["__time", "focal_upc", "channel_outlet", "retail_account", "geography_raw"]
    ).rename(columns={"focal_upc": "upc"})

    df = df.merge(
        crw[["__time", "upc", "channel_outlet", "retail_account", "geography_raw", "cannibal_rate"]],
        on=["__time"] + GROUP_COLS, how="left"
    )
    df["cannibal_rate"] = df["cannibal_rate"].fillna(0)
    cannibal_active = (df["cannibal_rate"] > 0).sum()
    print(f"  cannibal_rate > 0: {cannibal_active:,} / {len(df):,} rows "
          f"({cannibal_active / len(df) * 100:.1f}%)")

    # ── 9. Competitor / donor weekly signals ─────────────────────────────────
    print(f"\n[9] Loading top-{TOP_N_DONORS} donor weekly data from built_filtered_weekly …")
    if donor_upcs:
        upc_list = "', '".join(donor_upcs)
        donor_bfw = query_druid(f"""
            SELECT
                __time,
                upc,
                channel_outlet,
                retail_account,
                geography_raw,
                CAST(tdp AS DOUBLE)        AS tdp,
                CAST(base_units AS DOUBLE)  AS base_units,
                CAST(arp AS DOUBLE)         AS arp
            FROM "built_filtered_weekly"
            WHERE __time >= CURRENT_TIMESTAMP - {LOOKBACK}
              AND upc IN ('{upc_list}')
              AND retail_account IS NOT NULL
              AND retail_account <> ''
        """)
        donor_bfw["__time"]     = pd.to_datetime(donor_bfw["__time"], utc=True)
        donor_bfw["tdp"]        = pd.to_numeric(donor_bfw["tdp"],        errors="coerce").fillna(0)
        donor_bfw["base_units"] = pd.to_numeric(donor_bfw["base_units"], errors="coerce").fillna(0)
        donor_bfw["arp"]        = pd.to_numeric(donor_bfw["arp"],        errors="coerce")
        print(f"  Donor rows loaded: {len(donor_bfw):,}")

        # Join focal identity back onto donor rows
        donor_weekly = donor_bfw.merge(
            top_donors[["donor_upc"] + focal_group].rename(columns={"focal_upc": "upc_focal"}),
            left_on =["upc", "channel_outlet", "retail_account", "geography_raw"],
            right_on=["donor_upc", "channel_outlet", "retail_account", "geography_raw"],
            how="inner",
        )

        # Brand-split: classify each donor as BUILT sibling or competitor
        donor_weekly["_is_built_donor"] = donor_weekly["upc"].isin(built_upc_set)

        def _tdp_weighted_arp(grp):
            total_tdp = grp["tdp"].sum()
            if total_tdp < 1e-9 or grp["arp"].isna().all():
                return np.nan
            valid = grp.dropna(subset=["arp"])
            return (valid["arp"] * valid["tdp"]).sum() / valid["tdp"].sum()

        _agg_key = ["__time", "upc_focal", "channel_outlet", "retail_account", "geography_raw"]

        # All donors combined (backward compat)
        donor_agg_weekly = (
            donor_weekly
            .groupby(_agg_key)
            .apply(lambda g: pd.Series({
                "top_donor_tdp_sum":  g["tdp"].sum(),
                "top_donor_units_sum": g["base_units"].sum(),
                "top_donor_arp_wavg": _tdp_weighted_arp(g),
            }))
            .reset_index()
            .rename(columns={"upc_focal": "upc"})
        )

        # Competitor donors only (cross-brand market share dynamics)
        _comp_dw = donor_weekly[~donor_weekly["_is_built_donor"]]
        if not _comp_dw.empty:
            comp_agg_weekly = (
                _comp_dw.groupby(_agg_key)
                .apply(lambda g: pd.Series({
                    "competitor_donor_tdp_sum":   g["tdp"].sum(),
                    "competitor_donor_units_sum": g["base_units"].sum(),
                    "competitor_donor_arp_wavg":  _tdp_weighted_arp(g),
                }))
                .reset_index()
                .rename(columns={"upc_focal": "upc"})
            )
        else:
            comp_agg_weekly = None

        # BUILT sibling donors only (intra-brand cannibalization risk)
        _built_dw = donor_weekly[donor_weekly["_is_built_donor"]]
        if not _built_dw.empty:
            built_agg_weekly = (
                _built_dw.groupby(_agg_key)
                .apply(lambda g: pd.Series({
                    "built_donor_tdp_sum":   g["tdp"].sum(),
                    "built_donor_units_sum": g["base_units"].sum(),
                }))
                .reset_index()
                .rename(columns={"upc_focal": "upc"})
            )
        else:
            built_agg_weekly = None

        for col in ["top_donor_tdp_sum", "top_donor_units_sum", "top_donor_arp_wavg"]:
            donor_agg_weekly[col] = pd.to_numeric(donor_agg_weekly[col], errors="coerce")

        df = df.merge(donor_agg_weekly, on=["__time"] + GROUP_COLS, how="left")

        if comp_agg_weekly is not None:
            for col in ["competitor_donor_tdp_sum", "competitor_donor_units_sum", "competitor_donor_arp_wavg"]:
                comp_agg_weekly[col] = pd.to_numeric(comp_agg_weekly[col], errors="coerce")
            df = df.merge(comp_agg_weekly, on=["__time"] + GROUP_COLS, how="left")
        else:
            for c in ["competitor_donor_tdp_sum", "competitor_donor_units_sum", "competitor_donor_arp_wavg"]:
                df[c] = np.nan

        if built_agg_weekly is not None:
            for col in ["built_donor_tdp_sum", "built_donor_units_sum"]:
                built_agg_weekly[col] = pd.to_numeric(built_agg_weekly[col], errors="coerce")
            df = df.merge(built_agg_weekly, on=["__time"] + GROUP_COLS, how="left")
        else:
            for c in ["built_donor_tdp_sum", "built_donor_units_sum"]:
                df[c] = np.nan

        print(f"  top_donor_tdp_sum coverage: "
              f"{df['top_donor_tdp_sum'].notna().sum():,} / {len(df):,} rows "
              f"({df['top_donor_tdp_sum'].notna().mean()*100:.1f}%)")
        print(f"  competitor_donor coverage: "
              f"{df['competitor_donor_tdp_sum'].notna().sum():,} / {len(df):,} "
              f"({df['competitor_donor_tdp_sum'].notna().mean()*100:.1f}%)")
        print(f"  built_donor coverage: "
              f"{df['built_donor_tdp_sum'].notna().sum():,} / {len(df):,} "
              f"({df['built_donor_tdp_sum'].notna().mean()*100:.1f}%)")
    else:
        for c in ["top_donor_tdp_sum", "top_donor_units_sum", "top_donor_arp_wavg",
                  "competitor_donor_tdp_sum", "competitor_donor_units_sum", "competitor_donor_arp_wavg",
                  "built_donor_tdp_sum", "built_donor_units_sum"]:
            df[c] = np.nan
        print("  No donors found — donor columns set to NaN.")

    # Competitor price gap: focal ARP vs TDP-weighted *competitor* donor ARP only
    # (v5 fix: v4 mixed BUILT siblings into this gap, diluting the competitive signal)
    df["competitor_price_gap"] = df["arp"] - df["competitor_donor_arp_wavg"]

    # Mixed-donor WoW (backward compat) + brand-split WoW signals
    df["top_donor_units_wow"]       = df.groupby(GROUP_COLS)["top_donor_units_sum"].diff()
    df["competitor_donor_units_wow"] = df.groupby(GROUP_COLS)["competitor_donor_units_sum"].diff()
    df["built_donor_units_wow"]      = df.groupby(GROUP_COLS)["built_donor_units_sum"].diff()

    # ── 10. Category TDP — BUILT shelf share ─────────────────────────────────
    print("\n[10] Loading category TDP from built_filtered_weekly (all brands) …")
    cat = query_druid(f"""
        SELECT
            __time,
            channel_outlet,
            retail_account,
            geography_raw,
            SUM(CAST(tdp AS DOUBLE))       AS category_tdp_sum,
            SUM(CAST(base_units AS DOUBLE)) AS category_units_sum
        FROM "built_filtered_weekly"
        WHERE __time >= CURRENT_TIMESTAMP - {LOOKBACK}
          AND retail_account IS NOT NULL
          AND retail_account <> ''
        GROUP BY 1, 2, 3, 4
    """)
    cat["__time"]             = pd.to_datetime(cat["__time"], utc=True)
    cat["category_tdp_sum"]   = pd.to_numeric(cat["category_tdp_sum"],   errors="coerce")
    cat["category_units_sum"] = pd.to_numeric(cat["category_units_sum"], errors="coerce")

    cat_group = ["channel_outlet", "retail_account", "geography_raw"]
    df = df.merge(cat[["__time"] + cat_group + ["category_tdp_sum", "category_units_sum"]],
                  on=["__time"] + cat_group, how="left")

    # BUILT TDP share: fraction of category shelf presence BUILT holds
    df["built_tdp_share"] = (
        df["tdp"] / df["category_tdp_sum"].clip(lower=0.001)
    ).clip(0, 1)
    print(f"  category_tdp_sum coverage: "
          f"{df['category_tdp_sum'].notna().sum():,} / {len(df):,} rows "
          f"({df['category_tdp_sum'].notna().mean()*100:.1f}%) | "
          f"Avg BUILT TDP share: {df['built_tdp_share'].mean():.3f}")

    # ── 11. Time-series feature engineering (no data leakage) ────────────────
    print("\n[11] Computing time-series features …")

    df["week_of_year"]  = df["__time"].dt.isocalendar().week.astype(int)
    df["holiday_week"]  = df["week_of_year"].map(HOLIDAY_WEEK_MAP).fillna(0).astype(int)

    # v8: Fourier encoding — sin/cos correctly represents week 52 → week 1 adjacency.
    # Raw integer week_of_year implies week 52 is far from week 1; Fourier fixes this.
    df["week_sin"] = np.sin(2 * np.pi * df["week_of_year"] / 52.178)
    df["week_cos"] = np.cos(2 * np.pi * df["week_of_year"] / 52.178)

    # v6: per-event binary flags — model learns each event magnitude independently
    df["is_new_year_week"]      = df["week_of_year"].isin([1, 2]).astype(int)
    df["is_superbowl_week"]     = (df["week_of_year"] == 5).astype(int)
    df["is_memorial_day_week"]  = (df["week_of_year"] == 21).astype(int)
    df["is_labor_day_week"]     = (df["week_of_year"] == 36).astype(int)
    df["is_thanksgiving_week"]  = (df["week_of_year"] == 47).astype(int)
    df["is_christmas_week"]     = (df["week_of_year"] == 52).astype(int)

    # Autoregressive lags on base_units
    # v8: add lag2 + lag3 — fills gap between lag1 (adjacent) and lag4 (monthly)
    for lag, col in [
        (1, "base_units_lag1"), (2, "base_units_lag2"), (3, "base_units_lag3"),
        (4, "base_units_lag4"), (13, "base_units_lag13"),
    ]:
        df[col] = df.groupby(GROUP_COLS)["base_units"].shift(lag)

    # YAGO
    df["base_units_lag52"]   = df.groupby(GROUP_COLS)["base_units"].shift(52)
    df["velocity_spm_lag52"] = df.groupby(GROUP_COLS)["avg_weekly_units_spm"].shift(52)

    # Autoregressive lags on total_units
    for lag, col in [(1, "total_units_lag1"), (4, "total_units_lag4"), (13, "total_units_lag13")]:
        df[col] = df.groupby(GROUP_COLS)["total_units"].shift(lag)
    df["total_units_lag52"] = df.groupby(GROUP_COLS)["total_units"].shift(52)

    # ARP lags and rolling stats
    for lag, col in [(1, "arp_lag1"), (4, "arp_lag4")]:
        df[col] = df.groupby(GROUP_COLS)["arp"].shift(lag)

    df["arp_wow_delta"]  = df["arp"] - df["arp_lag1"]
    # Signed pct change: negative when price drops (promotional), positive when price rises.
    # Audit column — the model feature is price_elasticity_effect (interaction with ε).
    df["arp_pct_change"] = (
        df["arp_wow_delta"] / df["arp_lag1"].clip(lower=0.01)
    ).clip(-0.5, 0.5).fillna(0)

    # v8: price_change_bin — 4-level categorical capturing price regime semantics.
    # Bins aligned with existing thresholds ($0.05 nickel standard, 5% event threshold).
    # Most rows (~90-95%) land in stable(0); minority bins capture TPR/clearance events.
    # Encoded as signed int, cast to LightGBM category in MO_57 ablation.
    _abs_drop = (-df["arp_wow_delta"]).clip(lower=0)  # positive when price falls
    _pct_abs  = df["arp_pct_change"].abs()
    df["price_change_bin"] = pd.cut(
        _abs_drop,
        bins=[-np.inf, 0.05, 0.25, np.inf],
        labels=[0, 1, 2],
    ).astype(float)
    # Price increases override with -1
    df.loc[df["arp_wow_delta"] > 0.05, "price_change_bin"] = -1
    # Stable override: if pct change also < 2%, force to 0 regardless of dollar amount
    df.loc[_pct_abs < 0.02, "price_change_bin"] = 0
    df["price_change_bin"] = df["price_change_bin"].fillna(0).astype(int)

    df["arp_roll8_avg"] = (
        df.groupby(GROUP_COLS)["arp"]
        .transform(lambda s: s.shift(1).rolling(8, min_periods=2).mean())
    )
    df["arp_roll8_std"] = (
        df.groupby(GROUP_COLS)["arp"]
        .transform(lambda s: s.shift(1).rolling(8, min_periods=2).std())
    )

    # TDP change signals — distribution expansion is a leading indicator of unit sales.
    # The *level* (tdp, tdp_z8) is already in LAYER_DEMAND; the *change rate* adds new signal.
    df["tdp_wow_delta"]   = df.groupby(GROUP_COLS)["tdp"].diff()
    df["tdp_4w_momentum"] = df.groupby(GROUP_COLS)["tdp"].diff(4)
    print(f"  tdp_wow_delta non-null: {df['tdp_wow_delta'].notna().sum():,} / {len(df):,}")

    # Elasticity interaction — expected demand response given this SKU's sensitivity and
    # this week's actual price move. Zero when price is flat or elasticity is unknown.
    df["price_elasticity_effect"] = (
        df["arp_pct_change"] * df["implied_elasticity"].fillna(0)
    ).clip(-1.5, 1.5).fillna(0)
    pe_active = (df["price_elasticity_effect"].abs() > 0.001).sum()
    print(f"  price_elasticity_effect nonzero: {pe_active:,} / {len(df):,} rows "
          f"({pe_active / len(df) * 100:.1f}%)")

    # ── 12. Promo signals (after ARP rolling stats are available) ────────────
    # promo_intensity: fraction of total units that were in promo display
    df["promo_intensity"] = (
        df["units_promo"] / df["total_units"].clip(lower=1)
    ).clip(0, 1).fillna(0)

    # is_promo_units: clear signal when units_promo is present and material
    df["is_promo_units"] = (df["promo_intensity"] > 0.10).astype(float)

    # arp_discount_pct: percentage drop vs 8w baseline — audit column only.
    # At 5% of $10 = $0.50 threshold, this misses nickel-level TPR events.
    # v5 replaces the detection logic with arp_dollar_discount (absolute $).
    df["arp_discount_pct"] = (
        (df["arp_roll8_avg"] - df["arp"]) / df["arp_roll8_avg"].clip(lower=0.01)
    ).clip(0, 1).fillna(0)

    # arp_dollar_discount: absolute dollar ARP drop vs 8w baseline (model feature).
    # $0.05 threshold = nickel standard consistent with MO_17 price guardrail.
    df["arp_dollar_discount"] = (df["arp_roll8_avg"] - df["arp"]).clip(lower=0).fillna(0)

    # is_promo_arp: inferred promo when units_promo absent and ARP dropped > $0.05 absolute
    promo_missing = df["units_promo"].isna() | (df["units_promo"] == 0)
    df["is_promo_arp"] = (promo_missing & (df["arp_dollar_discount"] > 0.05)).astype(float)

    # promo_lift_ratio: incremental unit lift from display (total vs base demand).
    # Captures promo volume response independent of price — a $0 display event
    # still shows promo lift; a shelf price reduction shows arp_dollar_discount.
    df["promo_lift_ratio"] = (
        (df["total_units"] / df["base_units"].clip(lower=1)) - 1
    ).clip(0, 5).fillna(0)

    # Combined promo flag (model feature)
    df["is_promo_week"] = (
        (df["is_promo_units"] == 1) | (df["is_promo_arp"] == 1)
    ).astype(int)

    # Promo source audit (not a model feature)
    df["promo_source"] = np.where(
        df["is_promo_units"] == 1, "units_promo",
        np.where(df["is_promo_arp"] == 1, "arp_inferred", "none")
    )

    promo_src = df["promo_source"].value_counts()
    print(f"\n  Promo source breakdown: "
          f"units_promo={promo_src.get('units_promo', 0):,}  "
          f"arp_inferred={promo_src.get('arp_inferred', 0):,}  "
          f"none={promo_src.get('none', 0):,}")
    print(f"  is_promo_week=1: {df['is_promo_week'].sum():,} rows "
          f"({df['is_promo_week'].mean()*100:.1f}%)")
    print(f"  arp_dollar_discount>$0.05: {(df['arp_dollar_discount']>0.05).sum():,} rows")
    print(f"  promo_lift_ratio>0: {(df['promo_lift_ratio']>0).sum():,} rows  "
          f"mean={df['promo_lift_ratio'].mean():.3f}")

    # Clean up intermediate promo flags (audit columns only need promo_source)
    df = df.drop(columns=["is_promo_units", "is_promo_arp"])

    # ── 13. MO_46 rolling signals join ───────────────────────────────────────
    _rolling_path = Path("outputs/rolling_signals_weekly.parquet")
    if _rolling_path.exists():
        print("\n[13] Joining MO_46 rolling signals …")
        rolling = pd.read_parquet(_rolling_path)
        rolling["__time"] = pd.to_datetime(rolling["__time"], utc=True)
        for _c in ["rolling_cannibal_pressure", "rolling_cannibal_trend", "rolling_elasticity"]:
            if _c in rolling.columns:
                rolling[_c] = pd.to_numeric(rolling[_c], errors="coerce")
        _join_cols = [c for c in
                      ["rolling_cannibal_pressure", "rolling_cannibal_trend",
                       "rolling_elasticity", "rolling_elas_valid"]
                      if c in rolling.columns]
        df = df.merge(rolling[GROUP_COLS + ["__time"] + _join_cols],
                      on=GROUP_COLS + ["__time"], how="left")
        for _c in _join_cols:
            cov = df[_c].notna().sum()
            print(f"  {_c}: {cov:,} / {len(df):,} ({cov / len(df) * 100:.1f}%)")
    else:
        print("\n[13] Skipping MO_46 rolling signals (run MO_46 first).")
        for _c in ["rolling_cannibal_pressure", "rolling_cannibal_trend",
                   "rolling_elasticity", "rolling_elas_valid"]:
            df[_c] = np.nan

    # ── 14. Quality filters ──────────────────────────────────────────────────
    print("\n[14] Applying quality filters …")
    series_len = df.groupby(GROUP_COLS)["base_units"].transform("count")
    before = len(df)
    df = df[series_len >= MIN_WEEKS].copy()
    print(f"  Dropped {before - len(df):,} rows (series < {MIN_WEEKS} weeks)")

    df = df.dropna(subset=["base_units_lag1"]).copy()
    print(f"  After lag1 dropna: {len(df):,} rows")

    # ── 15. Assemble output ──────────────────────────────────────────────────
    df["first_week_selling"] = df["first_week_selling"].dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    df["scored_at"] = SCORED_AT

    output_cols = [
        # Identity
        "__time",
        "upc", "description",
        "channel_outlet", "retail_account", "geography_raw", "geography_display", "geography_level",
        # Lifecycle
        "first_week_selling", "weeks_since_launch", "pack_count",
        # Demand — raw
        "base_units", "total_units", "units_promo", "avg_weekly_units_spm", "tdp", "arp",
        # ARP audit
        "arp_fallback", "arp_source",
        # Demand — pre-computed rolling (from event_detection_weekly)
        "base_units_roll4_avg",
        "base_units_roll8_avg",  "base_units_roll8_std",
        "base_units_roll13_avg", "base_units_roll13_std",
        "base_units_wow_delta",  "base_units_z8", "base_units_z13",
        "velocity_spm_roll8_avg", "velocity_spm_roll13_avg",
        "velocity_spm_z8", "velocity_spm_z13", "tdp_z8",
        # Price lags + rolling (computed in Python)
        "arp_lag1", "arp_lag4", "arp_roll8_avg", "arp_roll8_std", "arp_wow_delta",
        # Demand AR lags (v8: lag2 + lag3 added)
        "base_units_lag1", "base_units_lag2", "base_units_lag3",
        "base_units_lag4", "base_units_lag13",
        # YAGO
        "base_units_lag52", "velocity_spm_lag52",
        # Total-units model lags
        "total_units_lag1", "total_units_lag4", "total_units_lag13", "total_units_lag52",
        # Seasonality — integer + Fourier encoding (v8) + per-event binary flags
        "week_of_year", "week_sin", "week_cos", "holiday_week",
        "is_new_year_week", "is_superbowl_week", "is_memorial_day_week",
        "is_labor_day_week", "is_thanksgiving_week", "is_christmas_week",
        # Promo signals (model features)
        "is_promo_week", "promo_intensity", "arp_dollar_discount", "promo_lift_ratio",
        # Promo audit (not model features)
        "arp_discount_pct", "promo_source",
        # Elasticity — static coefficient + time-varying interaction term (v7)
        "implied_elasticity", "elasticity_band",
        "arp_pct_change",           # audit: signed WoW price change
        "price_change_bin",         # model candidate (v8): 4-level categorical (-1/0/1/2)
        "price_elasticity_effect",  # model candidate: arp_pct_change × implied_elasticity
        # Cannibalization — static signals + time-varying rate (v7)
        "cannibal_rate",            # model candidate: time-varying focal pressure (null→0)
        "max_donor_cannibal_prob", "donor_count",
        "competitor_donor_count", "built_donor_count",
        # Mixed donor signals (backward compat)
        "top_donor_tdp_sum", "top_donor_units_sum", "top_donor_arp_wavg", "top_donor_units_wow",
        # Competitor-only donor signals (cross-brand market share dynamics)
        "competitor_donor_tdp_sum", "competitor_donor_units_sum",
        "competitor_donor_arp_wavg", "competitor_price_gap", "competitor_donor_units_wow",
        # BUILT sibling donor signals (intra-brand cannibalization risk)
        "built_donor_tdp_sum", "built_donor_units_sum", "built_donor_units_wow",
        # Category shelf signals (audit only — not model features)
        "category_tdp_sum", "built_tdp_share",
        # TDP change signals (model features — distribution expansion as leading indicator)
        "tdp_wow_delta", "tdp_4w_momentum",
        # MO_46 rolling signals (NaN if MO_46 not yet run)
        "rolling_cannibal_pressure", "rolling_cannibal_trend",
        "rolling_elasticity", "rolling_elas_valid",
        # Meta
        "scored_at",
    ]
    out = df[[c for c in output_cols if c in df.columns]].copy()

    print(f"\n{'='*70}")
    print("MO_25 v8 COMPLETE")
    print(f"{'='*70}")
    print(f"  Total rows:        {len(out):,}")
    print(f"  Weeks covered:     {out['__time'].nunique():,}")
    print(f"  Unique UPCs:       {out['upc'].nunique():,}")
    print(f"  Series:            {out.groupby(GROUP_COLS).ngroups:,}")
    print(f"  ARP fallback:      {out['arp_fallback'].sum():,} rows "
          f"({out['arp_fallback'].mean()*100:.1f}%)")
    print(f"    roll13:          {(out['arp_source']=='roll13').sum():,}")
    print(f"    prepost:         {(out['arp_source']=='prepost').sum():,}")
    print(f"  Promo week flag:   {out['is_promo_week'].sum():,} rows "
          f"({out['is_promo_week'].mean()*100:.1f}%)")
    print(f"    units_promo:     {(out['promo_source']=='units_promo').sum():,}")
    print(f"    arp_inferred:    {(out['promo_source']=='arp_inferred').sum():,}")
    print(f"  Competitor TDP:    {out['top_donor_tdp_sum'].notna().sum():,} rows "
          f"({out['top_donor_tdp_sum'].notna().mean()*100:.1f}%)")
    print(f"  BUILT TDP share:   {out['built_tdp_share'].notna().sum():,} rows | "
          f"Avg: {out['built_tdp_share'].mean():.3f}")
    print(f"  ARP range:         ${out['arp'].min():.2f} – ${out['arp'].max():.2f}")
    print(f"  Base units range:  {out['base_units'].min():.0f} – {out['base_units'].max():.0f}")
    print(f"  cannibal_rate>0:   {(out['cannibal_rate']>0).sum():,} rows "
          f"({(out['cannibal_rate']>0).mean()*100:.1f}%) | "
          f"mean(nonzero)={out.loc[out['cannibal_rate']>0,'cannibal_rate'].mean():.4f}")
    print(f"  price_elas_eff≠0:  {(out['price_elasticity_effect'].abs()>0.001).sum():,} rows "
          f"({(out['price_elasticity_effect'].abs()>0.001).mean()*100:.1f}%) | "
          f"range [{out['price_elasticity_effect'].min():.3f}, {out['price_elasticity_effect'].max():.3f}]")
    print(f"  New columns vs v3: holiday_week, is_promo_week, promo_intensity,")
    print(f"                     arp_discount_pct, top_donor_tdp_sum, top_donor_units_sum,")
    print(f"                     top_donor_arp_wavg, competitor_price_gap,")
    print(f"                     top_donor_units_wow, category_tdp_sum, built_tdp_share")
    print(f"  v6 binary flags:   is_new_year_week, is_superbowl_week, is_memorial_day_week,")
    print(f"                     is_labor_day_week, is_thanksgiving_week, is_christmas_week")
    print(f"  v7 time-varying:   cannibal_rate (from cannibalization_rate_weekly, null→0)")
    print(f"                     arp_pct_change (audit), price_elasticity_effect (arp_pct×ε)")

    out.to_parquet("outputs/retailer_sales_weekly.parquet", index=False)
    print("\n  Saved → outputs/retailer_sales_weekly.parquet")
    print("\nNext: run MO_56 ablation — test cannibal_rate + price_elasticity_effect")
    print("      on event-context series (wsl≤26 or |arp_pct_change|>5%) vs stable series.")
