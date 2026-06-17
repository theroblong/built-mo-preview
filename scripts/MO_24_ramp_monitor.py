"""MO_24 — Build new_product_ramp_monitor.

WHY THIS EXISTS
---------------
New SKU launches need a different view from the standard cannibalization
scorer.  For the first 12 weeks (Brian's standard launch window), there is
not enough post-launch data for a reliable cannibalization verdict.  This
script tracks each new SKU week-by-week through its launch ramp, assigns a
scoring_status (SUPPRESSED → LOW_CONFIDENCE → ACTIVE), and generates the
ui_ramp_ribbon text shown in the Launch Monitor tab.

12-WEEK WINDOW STANDARD
-----------------------
Brian confirmed 12 weeks as the BUILT standard launch window.  Weeks are
0-indexed (week 0 = first scanning week).  Status thresholds:

  Weeks  0 –  5  (6 wks)  SUPPRESSED    — too early to score
  Weeks  6 –  7  (2 wks)  LOW_CONFIDENCE — early signal visible
  Weeks  8 – 10  (3 wks)  ACTIVE         — signal maturing
  Week  11        (1 wk)  ACTIVE         — scoring fully active

Products are tracked only through week 11 (12 rows max per dim combo).

WHAT IT DOES
------------
1. Loads all BUILT weekly scanner data from event_detection_weekly.
2. Computes first_week_selling = MIN(__time) per UPC×channel×account×geo.
3. Filters to SKUs whose first_week_selling is within LOOKBACK_MONTHS.
4. Calculates weeks_since_launch (0-indexed) and clips to LAUNCH_WINDOW.
5. Computes per-week ramp metrics: peak_tdp, rolling averages, trends.
6. Assigns scoring_status, ramp_confidence, and ui_ramp_ribbon text.
7. Joins built_prepost_features for description, geography_display,
   geography_level, and ARP (post_4w_arp is the closest period average
   available without a week-level ARP table).
8. Writes new_product_ramp_monitor via MinIO → Druid native batch pipeline.

OUTPUT SCHEMA
-------------
__time                   ISO — the SPINS week timestamp (Druid primary time)
upc                      str
description              str
channel_outlet           str
retail_account           str
geography_raw            str
geography_display        str
geography_level          str
first_week_selling       str ISO
weeks_since_launch       int  0-indexed
tdp                      float
avg_weekly_units_spm     float
base_units               float
pct_stores_selling       float  (approximated as tdp — same SPINS measure)
arp                      float  (post_4w_arp from built_prepost_features)
peak_tdp                 float  running max tdp through this week
rolling_4w_avg_velocity_spm float  4-week trailing avg velocity
tdp_4w_change            float  tdp minus tdp 4 weeks prior (None if < 4 wks)
velocity_vs_4w_avg_ratio float  current / 4w rolling avg (1.0 when no history)
distribution_trend       str   RAMPING / PEAKED / DECLINING / STABLE
scoring_status           str   SUPPRESSED / LOW_CONFIDENCE / ACTIVE
ramp_confidence          str   None / Low / Medium / High
ui_ramp_ribbon           str   display text for Launch Monitor ribbon
underperforming_flag     int   1 if velocity < 80% of 4w rolling avg
tdp_ratio_to_peak        float tdp / peak_tdp
tdp_now_slash_peak       str   "X.X / Y.Y" for display
scored_at                str   ISO UTC run timestamp

PIPELINE POSITION
-----------------
Runs after MO_13 (cannibal score) and before MO_14_7 (price events), which
reads new_product_ramp_monitor for NEW_ITEM_PRICE_BASELINE detection.
Recommended label: MO_14.0 in the run order.

HUMAN REVIEW
------------
write_back() generates a Druid ingestion spec in outputs/ and prints a
prompt.  A human must POST the spec to Druid before the Launch Monitor tab
reflects the new data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from mo_druid_client import query_druid
from mo_writeback import write_back

# ── Configuration ─────────────────────────────────────────────────────────────
LAUNCH_WINDOW      = 12   # track weeks 0–11 (Brian's 12-week standard)
SUPPRESSED_THRU    = 5    # weeks 0–5: scoring suppressed
LOW_CONF_THRU      = 7    # weeks 6–7: early signal, low confidence
SIGNAL_MATURE_THRU = 10   # weeks 8–10: signal maturing; week 11: fully active
LOOKBACK_MONTHS    = 6    # only enroll products first sold in the last N months
SCORED_AT          = datetime.now(timezone.utc).isoformat()

DIM_KEYS = ["upc", "channel_outlet", "retail_account", "geography_raw"]


def _assign_status(week: int) -> tuple[str, str | None]:
    """Return (scoring_status, ramp_confidence) for a given launch week."""
    if week <= SUPPRESSED_THRU:
        return "SUPPRESSED", None
    if week <= LOW_CONF_THRU:
        return "LOW_CONFIDENCE", "Low"
    if week <= SIGNAL_MATURE_THRU:
        return "ACTIVE", "Medium"
    return "ACTIVE", "High"


def _ribbon(week: int, status: str) -> str:
    """Build ui_ramp_ribbon display text (1-indexed week, of LAUNCH_WINDOW)."""
    w = week + 1  # 1-indexed for display
    prefix = f"RAMP WEEK {w} of {LAUNCH_WINDOW}"
    if status == "SUPPRESSED":
        return f"{prefix} · Cannibalization scoring suppressed"
    if status == "LOW_CONFIDENCE":
        return f"{prefix} · Early signal · Low confidence"
    if week <= SIGNAL_MATURE_THRU:
        return f"{prefix} · Signal maturing"
    return f"{prefix} · Scoring fully active"


def _distribution_trend(group: pd.DataFrame) -> pd.Series:
    """
    Classify each week's distribution trend relative to the trailing 4-week TDP.
    RAMPING  : TDP increasing (vs 4w ago or vs start)
    PEAKED   : TDP at/near peak but now declining
    DECLINING: TDP > 10% below peak
    STABLE   : TDP flat (< 5% change vs 4w ago)
    """
    tdp = group["tdp"].astype(float)
    peak = tdp.cummax()
    tdp_4w_ago = tdp.shift(4)
    ratio_to_peak = tdp / peak.replace(0, np.nan)

    trends = []
    for i in range(len(group)):
        t = tdp.iloc[i]
        p = peak.iloc[i]
        prior = tdp_4w_ago.iloc[i] if not pd.isna(tdp_4w_ago.iloc[i]) else t
        rtp = ratio_to_peak.iloc[i] if not pd.isna(ratio_to_peak.iloc[i]) else 1.0

        if pd.isna(prior) or prior == 0:
            trends.append("RAMPING")
        elif t > prior * 1.05:
            trends.append("RAMPING")
        elif rtp < 0.90:
            trends.append("DECLINING")
        elif t < prior * 0.95 and rtp >= 0.90:
            trends.append("PEAKED")
        else:
            trends.append("STABLE")
    return pd.Series(trends, index=group.index)


def build_ramp_rows(weekly: pd.DataFrame, prepost: pd.DataFrame) -> pd.DataFrame:
    """Compute ramp monitor rows from weekly scanner data."""
    weekly = weekly.copy()
    for col in ["tdp", "avg_weekly_units_spm", "base_units"]:
        weekly[col] = pd.to_numeric(weekly[col], errors="coerce").fillna(0.0)
    weekly["__time"] = pd.to_datetime(weekly["__time"], utc=True)

    # ── first_week_selling per dim combo ──────────────────────────────────────
    fws = (
        weekly.groupby(DIM_KEYS)["__time"]
        .min()
        .reset_index()
        .rename(columns={"__time": "first_week_selling"})
    )
    weekly = weekly.merge(fws, on=DIM_KEYS, how="left")

    # ── filter: only products launched within LOOKBACK_MONTHS ─────────────────
    cutoff = pd.Timestamp.now(tz="UTC") - pd.DateOffset(months=LOOKBACK_MONTHS)
    weekly = weekly[weekly["first_week_selling"] >= cutoff].copy()
    if weekly.empty:
        print("  No new launches found within lookback window.")
        return pd.DataFrame()

    # ── weeks_since_launch (0-indexed) ────────────────────────────────────────
    weekly["weeks_since_launch"] = (
        (weekly["__time"] - weekly["first_week_selling"])
        .dt.days // 7
    ).astype(int)

    # ── clip to LAUNCH_WINDOW ─────────────────────────────────────────────────
    weekly = weekly[weekly["weeks_since_launch"] < LAUNCH_WINDOW].copy()

    # ── join prepost for description, geography, ARP ──────────────────────────
    prepost_slim = prepost[
        DIM_KEYS + ["description", "geography_display", "geography_level", "post_4w_arp"]
    ].drop_duplicates(subset=DIM_KEYS)
    weekly = weekly.merge(prepost_slim, on=DIM_KEYS, how="left")

    # ── per-group rolling metrics ──────────────────────────────────────────────
    rows = []
    for key, grp in weekly.sort_values("weeks_since_launch").groupby(DIM_KEYS):
        grp = grp.sort_values("weeks_since_launch").reset_index(drop=True)
        vel = grp["avg_weekly_units_spm"].astype(float)
        tdp = grp["tdp"].astype(float)
        peak_tdp = tdp.cummax()

        roll4_vel   = vel.rolling(4, min_periods=1).mean()
        tdp_4w_ago  = tdp.shift(4)
        tdp_4w_chg  = tdp - tdp_4w_ago
        vel_ratio   = (vel / roll4_vel.replace(0, np.nan)).fillna(1.0)
        trends      = _distribution_trend(grp)

        for i, row in grp.iterrows():
            week = int(row["weeks_since_launch"])
            status, conf = _assign_status(week)
            p_tdp = float(peak_tdp.iloc[i])
            t_tdp = float(tdp.iloc[i])
            ratio = (t_tdp / p_tdp) if p_tdp > 0 else 1.0

            rows.append({
                "__time":                    row["__time"].isoformat(),
                "upc":                       row["upc"],
                "description":               row.get("description"),
                "channel_outlet":            row["channel_outlet"],
                "retail_account":            row["retail_account"],
                "geography_raw":             row["geography_raw"],
                "geography_display":         row.get("geography_display"),
                "geography_level":           row.get("geography_level"),
                "first_week_selling":        row["first_week_selling"].isoformat(),
                "weeks_since_launch":        week,
                "tdp":                       t_tdp,
                "avg_weekly_units_spm":      float(vel.iloc[i]),
                "base_units":                float(row["base_units"]),
                "pct_stores_selling":        t_tdp,  # same SPINS measure as TDP
                "arp":                       float(row.get("post_4w_arp") or 0),
                "peak_tdp":                  p_tdp,
                "rolling_4w_avg_velocity_spm": float(roll4_vel.iloc[i]),
                "tdp_4w_change":             float(tdp_4w_chg.iloc[i]) if not pd.isna(tdp_4w_chg.iloc[i]) else None,
                "velocity_vs_4w_avg_ratio":  float(vel_ratio.iloc[i]),
                "distribution_trend":        trends.iloc[i],
                "scoring_status":            status,
                "ramp_confidence":           conf,
                "ui_ramp_ribbon":            _ribbon(week, status),
                "underperforming_flag":      int(vel_ratio.iloc[i] < 0.80),
                "tdp_ratio_to_peak":         round(ratio, 4),
                "tdp_now_slash_peak":        f"{t_tdp:.1f} / {p_tdp:.1f}",
                "scored_at":                 SCORED_AT,
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    # ── 1. Load weekly scanner data ───────────────────────────────────────────
    cutoff_sql = (
        datetime.now(timezone.utc) - timedelta(days=LOOKBACK_MONTHS * 31)
    ).strftime("%Y-%m-%d")

    print("Loading event_detection_weekly...")
    weekly = query_druid(f"""
        SELECT
            __time, upc, channel_outlet, retail_account, geography_raw,
            geography_display, geography_level,
            tdp, avg_weekly_units_spm, base_units
        FROM "event_detection_weekly"
        WHERE __time >= TIMESTAMP '{cutoff_sql}'
    """)
    print(f"  Rows: {len(weekly):,}")
    if weekly.empty:
        print("No weekly data — exiting.")
        raise SystemExit(0)

    # ── 2. Load built_prepost_features for description + ARP ──────────────────
    print("Loading built_prepost_features (description, geography, ARP)...")
    prepost = query_druid("""
        SELECT
            upc, channel_outlet, retail_account, geography_raw,
            description, geography_display, geography_level,
            post_4w_arp
        FROM "built_prepost_features"
    """)
    print(f"  Rows: {len(prepost):,}")

    # ── 3. Build ramp rows ────────────────────────────────────────────────────
    print(f"Building ramp monitor rows (LAUNCH_WINDOW={LAUNCH_WINDOW} weeks)...")
    out = build_ramp_rows(weekly, prepost)
    if out.empty:
        print("No output rows — nothing to write.")
        raise SystemExit(0)

    # Summary
    status_counts = out["scoring_status"].value_counts().to_dict()
    n_upcs = out["upc"].nunique()
    print(f"  Output rows: {len(out):,} | UPCs: {n_upcs} | statuses: {status_counts}")

    # ── 4. Write to Druid ─────────────────────────────────────────────────────
    write_back(out, "new_product_ramp_monitor", timestamp_col="__time")
