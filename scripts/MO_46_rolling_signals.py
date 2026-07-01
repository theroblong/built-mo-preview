"""MO_46 — Rolling cannibalization pressure and elasticity signals.

WHY THIS EXISTS
---------------
The static signals in scored_cannibalization (max_donor_cannibal_prob) and
scored_price_elasticity (implied_elasticity) reflect historical averages —
they don't know whether a competitive substitution dynamic is heating up *right
now* or whether the focal SKU has become more or less price-sensitive recently.

Rolling signals capture that live movement. They're the enabling layer for the
"pre-trained pathways with attached narratives" product vision: when a signal
contributes to a forecast, Mo can say *which* signal and *when* it shifted,
not just output a number.

ROLLING CANNIBALIZATION PRESSURE (8-week trailing Pearson)
----------------------------------------------------------
For each (focal_upc, channel, account, geo) series at week T:

  • Collect the last 8 weeks of focal base_units.
  • Collect the last 8 weeks of sum(donor base_units) across all donors with
    cannibal_status IN ('Cannibalizing', 'Watch') — same filter as MO_19 and
    the Pool Health API endpoint.
  • Compute Pearson r between focal and donor_sum trajectories.
  • rolling_cannibal_pressure = -r   (range [-1, +1])
    - +1: focal falling as donor_sum rises (or vice versa) — maximum competitive
          tension; zero-sum dynamic active.
    - 0:  no relationship — independent movements.
    - -1: focal and donor_sum co-moving — market expansion, not zero-sum.
  • rolling_cannibal_trend = pressure_4w − pressure_8w
    Positive = competition is accelerating; negative = tension easing.
  • Requires ≥ 5 valid weeks in window; flat series → NaN.

ROLLING ELASTICITY (13-week trailing OLS)
-----------------------------------------
For each series at week T:

  • Collect the last 13 weeks of (arp, base_units) pairs.
  • Apply $0.05 price guardrail: if max(arp)−min(arp) < $0.05 in the window,
    there is insufficient price variation for a reliable OLS estimate → NaN.
  • Require ≥ 5 valid (non-NaN, arp > 0, units > 0) weeks.
  • OLS: log1p(base_units) ~ log1p(arp); slope = rolling_elasticity.
  • Clip to [−5, 3] to suppress noise from structural breaks.
  • rolling_elas_valid: 1 if guardrail passed; 0 otherwise.

These signals are joined into retailer_sales_weekly.parquet by MO_25 (see
the MO_46 join block near the end of that script) and used as features in
MO_26 v3 / MO_27 v3.

DATA SOURCES
------------
1. event_detection_weekly   — focal + donor weekly base_units, velocity
2. built_filtered_weekly    — weekly ARP (not in event_detection_weekly)
3. scored_cannibalization   — donor pairs (focal_upc → donor_upc per context)

OUTPUT: outputs/rolling_signals_weekly.parquet
Join key: (upc, channel_outlet, retail_account, geography_raw, __time)

COLUMNS
-------
upc                        str
channel_outlet             str
retail_account             str
geography_raw              str
__time                     ISO UTC
rolling_cannibal_pressure  float  [-1, 1] — active competitive tension this week
rolling_cannibal_trend     float  — 4w minus 8w pressure (acceleration)
rolling_elasticity         float  [-5, 3] — trailing OLS ε; NaN = guardrail failed
rolling_elas_valid         int    0/1 — 1 = elasticity estimate is reliable
scored_at                  str    ISO UTC
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid

CANNIBAL_WINDOW  = 8
CANNIBAL_WINDOW_SHORT = 4      # for trend: 4w vs 8w pressure
ELAS_WINDOW      = 13
MIN_VALID_WEEKS  = 5
PRICE_GUARDRAIL  = 0.05        # $/bar — from MO_17's guardrail
ELAS_CLIP        = (-5.0, 3.0)

GROUP_COLS = ["upc", "channel_outlet", "retail_account", "geography_raw"]
LOOKBACK   = "INTERVAL '3' YEAR"


def _upc_sql_list(upcs: list[str]) -> str:
    return ", ".join(f"'{u.replace(chr(39), chr(39)*2)}'" for u in upcs)


def _add_cannibal_pressure(g: pd.DataFrame) -> pd.DataFrame:
    """Adds rolling_cannibal_pressure and rolling_cannibal_trend to a single series group."""
    g = g.sort_values("__time").copy()

    has_donors = "donor_sum_units" in g.columns and g["donor_sum_units"].notna().any()
    if not has_donors:
        g["rolling_cannibal_pressure"] = np.nan
        g["rolling_cannibal_trend"]    = np.nan
        return g

    focal_s  = g["base_units"].astype(float)
    donor_s  = g["donor_sum_units"].fillna(0).astype(float)

    corr_8w = focal_s.rolling(CANNIBAL_WINDOW,      min_periods=MIN_VALID_WEEKS).corr(donor_s)
    corr_4w = focal_s.rolling(CANNIBAL_WINDOW_SHORT, min_periods=min(MIN_VALID_WEEKS, CANNIBAL_WINDOW_SHORT)).corr(donor_s)

    g["rolling_cannibal_pressure"] = -corr_8w           # negative correlation = positive pressure
    g["rolling_cannibal_trend"]    = (-corr_4w) - (-corr_8w)   # positive = accelerating tension
    return g


def _add_rolling_elasticity(g: pd.DataFrame) -> pd.DataFrame:
    """Adds rolling_elasticity and rolling_elas_valid to a single series group."""
    g = g.sort_values("__time").reset_index(drop=True).copy()
    n = len(g)
    elas_vals  = np.full(n, np.nan)
    valid_flag = np.zeros(n, dtype=int)

    for i in range(n):
        start = max(0, i - ELAS_WINDOW + 1)    # trailing window that includes row i
        w = g.iloc[start : i + 1]
        a = pd.to_numeric(w["arp"],        errors="coerce").values
        u = pd.to_numeric(w["base_units"], errors="coerce").values
        mask = np.isfinite(a) & np.isfinite(u) & (a > 0) & (u > 0)
        if mask.sum() < MIN_VALID_WEEKS:
            continue
        arp_v = a[mask]
        if arp_v.max() - arp_v.min() < PRICE_GUARDRAIL:
            continue
        # np.polyfit is faster than scipy.linregress for small windows
        slope = np.polyfit(np.log1p(arp_v), np.log1p(u[mask]), 1)[0]
        elas_vals[i]  = float(np.clip(slope, *ELAS_CLIP))
        valid_flag[i] = 1

    g["rolling_elasticity"] = elas_vals
    g["rolling_elas_valid"] = valid_flag
    return g


if __name__ == "__main__":
    print("=== MO_46: Rolling Cannibalization Pressure + Elasticity ===\n")
    scored_at = datetime.now(timezone.utc).isoformat()

    # ── 1. Load donor pairs from scored_cannibalization ──────────────────────
    print("Loading scored_cannibalization for donor pairs …")
    sc = query_druid("""
        SELECT DISTINCT
            focal_upc,
            donor_upc,
            channel_outlet,
            retail_account,
            geography_raw
        FROM "scored_cannibalization"
        WHERE cannibal_status IN ('Cannibalizing', 'Watch')
          AND retail_account IS NOT NULL
          AND retail_account <> ''
    """)
    print(f"  Active pairs: {len(sc):,} | Focal UPCs: {sc['focal_upc'].nunique()} "
          f"| Donor UPCs: {sc['donor_upc'].nunique()}")
    if sc.empty:
        raise SystemExit("No pairs found in scored_cannibalization — cannot proceed.")

    all_focal_upcs = sc["focal_upc"].unique().tolist()
    all_donor_upcs = sc["donor_upc"].unique().tolist()
    all_upcs       = list(set(all_focal_upcs + all_donor_upcs))

    # ── 2. Load weekly base_units for all relevant UPCs ─────────────────────
    # Single query covers both focal and donor UPCs — avoids two round-trips.
    print(f"\nLoading event_detection_weekly for {len(all_upcs)} UPCs …")
    edw = query_druid(f"""
        SELECT
            __time,
            upc,
            channel_outlet,
            retail_account,
            geography_raw,
            base_units,
            avg_weekly_units_spm
        FROM "event_detection_weekly"
        WHERE __time >= CURRENT_TIMESTAMP - {LOOKBACK}
          AND retail_account IS NOT NULL
          AND retail_account <> ''
          AND upc IN ({_upc_sql_list(all_upcs)})
    """)
    edw["__time"]              = pd.to_datetime(edw["__time"], utc=True)
    edw["base_units"]          = pd.to_numeric(edw["base_units"],          errors="coerce")
    edw["avg_weekly_units_spm"] = pd.to_numeric(edw["avg_weekly_units_spm"], errors="coerce")
    edw = edw.drop_duplicates(subset=["__time"] + GROUP_COLS)
    print(f"  Rows: {len(edw):,} | Date range: "
          f"{edw['__time'].min().date()} – {edw['__time'].max().date()}")

    # ── 3. Load weekly ARP for focal UPCs ────────────────────────────────────
    print(f"\nLoading built_filtered_weekly ARP for {len(all_focal_upcs)} focal UPCs …")
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
          AND upc IN ({_upc_sql_list(all_focal_upcs)})
    """)
    bfw["__time"] = pd.to_datetime(bfw["__time"], utc=True)
    bfw["arp"]    = pd.to_numeric(bfw["arp"], errors="coerce")
    bfw = bfw.drop_duplicates(subset=["__time"] + GROUP_COLS)
    print(f"  Rows: {len(bfw):,}")

    # ── 4. Build focal weekly panel ───────────────────────────────────────────
    focal_edw = edw[edw["upc"].isin(all_focal_upcs)].copy()
    df = focal_edw.merge(
        bfw[GROUP_COLS + ["__time", "arp"]],
        on=GROUP_COLS + ["__time"],
        how="left",
    )
    df = df.sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)
    print(f"\n  Focal panel: {len(df):,} rows | ARP coverage: "
          f"{df['arp'].notna().sum():,} / {len(df):,} "
          f"({df['arp'].notna().mean()*100:.1f}%)")

    # ── 5. Build donor_sum panel via vectorized join ──────────────────────────
    # Rename donor_upc → upc so it joins onto edw on the same column.
    print("\nBuilding donor_sum panel …")
    donor_pairs = sc.rename(columns={"donor_upc": "upc"})   # focal_upc, upc(=donor), ctx
    donor_edw   = (
        donor_pairs
        .merge(
            edw[GROUP_COLS + ["__time", "base_units"]],
            on=["upc", "channel_outlet", "retail_account", "geography_raw"],
        )
    )
    donor_sum_panel = (
        donor_edw
        .groupby(["focal_upc", "channel_outlet", "retail_account", "geography_raw", "__time"],
                 observed=True)["base_units"]
        .sum()
        .reset_index()
        .rename(columns={"base_units": "donor_sum_units", "focal_upc": "upc"})
    )
    print(f"  Donor-sum rows: {len(donor_sum_panel):,} "
          f"| Series with donors: {donor_sum_panel.groupby(GROUP_COLS).ngroups:,}")

    df = df.merge(donor_sum_panel, on=GROUP_COLS + ["__time"], how="left")

    # ── 6. Rolling cannibalization pressure (pandas rolling.corr — vectorized) ─
    print("\nComputing rolling cannibalization pressure …")
    frames_cannibal = []
    for group_keys, g in df.groupby(GROUP_COLS, observed=True):
        frames_cannibal.append(_add_cannibal_pressure(g))
    df = pd.concat(frames_cannibal).sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    cp_coverage = df["rolling_cannibal_pressure"].notna().sum()
    print(f"  Pressure coverage: {cp_coverage:,} / {len(df):,} "
          f"({cp_coverage / len(df) * 100:.1f}%)")
    print(f"  Pressure stats:   mean={df['rolling_cannibal_pressure'].mean():.3f}  "
          f"std={df['rolling_cannibal_pressure'].std():.3f}  "
          f"p25={df['rolling_cannibal_pressure'].quantile(.25):.3f}  "
          f"p75={df['rolling_cannibal_pressure'].quantile(.75):.3f}")

    # ── 7. Rolling elasticity (per-series trailing 13w OLS) ───────────────────
    print("\nComputing rolling elasticity (13-week trailing OLS) …")
    n_series = df.groupby(GROUP_COLS, observed=True).ngroups
    print(f"  Processing {n_series:,} series …")
    frames_elas = []
    for i, (group_keys, g) in enumerate(df.groupby(GROUP_COLS, observed=True)):
        frames_elas.append(_add_rolling_elasticity(g))
        if (i + 1) % 500 == 0:
            print(f"    {i + 1:,} / {n_series:,} series done")
    df = pd.concat(frames_elas).sort_values(GROUP_COLS + ["__time"]).reset_index(drop=True)

    el_coverage = df["rolling_elas_valid"].sum()
    print(f"  Elasticity coverage: {el_coverage:,} / {len(df):,} "
          f"({el_coverage / len(df) * 100:.1f}%)")
    print(f"  Elasticity stats:  mean={df['rolling_elasticity'].mean():.3f}  "
          f"std={df['rolling_elasticity'].std():.3f}  "
          f"p25={df['rolling_elasticity'].quantile(.25):.3f}  "
          f"p75={df['rolling_elasticity'].quantile(.75):.3f}")

    # ── 8. Assemble and save ─────────────────────────────────────────────────
    output_cols = GROUP_COLS + [
        "__time",
        "rolling_cannibal_pressure",
        "rolling_cannibal_trend",
        "rolling_elasticity",
        "rolling_elas_valid",
    ]
    out = df[[c for c in output_cols if c in df.columns]].copy()
    out["scored_at"] = scored_at

    print(f"\n  Output rows:         {len(out):,}")
    print(f"  Series covered:      {out.groupby(GROUP_COLS).ngroups:,}")
    print(f"  Weeks covered:       {out['__time'].nunique():,}")

    out.to_parquet("outputs/rolling_signals_weekly.parquet", index=False)
    print("\n  Saved → outputs/rolling_signals_weekly.parquet")
    print("\nNext: run MO_25 to join rolling signals into retailer_sales_weekly.parquet,")
    print("      then MO_26 v3 (train) and MO_27 v3 (forecast).")
