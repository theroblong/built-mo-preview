"""MO_73 — Promo Lift Rate Framework

Builds a reference table of historical SPINS promotional lift rates for BUILT,
by retailer × SKU × promo mechanic × discount depth bucket.  Joins MO_72 causal
scores (ROBUST/MODERATE) where available to provide a counterfactual estimate
alongside the observational SPINS lift.

Outputs
-------
  outputs/promo_lift_events.csv    one row per weekly promo event (raw)
  outputs/promo_lift_summary.csv   one row per (retailer × UPC × discount_bucket)
  outputs/promo_lift_lookup.json   JSON summary for mockup embedding

Lift signal hierarchy
---------------------
  1. causal_impact_pct (MO_72 ROBUST/MODERATE) — BSTS counterfactual, highest quality
  2. SPINS incr_units / base_units             — observational lift from SPINS MRM
  3. units_lift_tpr / _display / _feature      — mechanic-specific SPINS lift indices

Coverage
--------
  Retailers with SPINS data (~80 of Connor's 100).
  Data-dark retailers (Winco, HEB, TJ's) will appear in summary as no_coverage=True.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from mo_druid_client import query_druid

# ── Config ────────────────────────────────────────────────────────────────────
MULO_CHANNEL  = "CONVENTIONAL|MULTI OUTLET"
MULO_GEOS     = "'MULO', 'W/ AK/HI', 'MULO W/ C-STORES', 'W/ C-STORES'"
BUILT_BRANDS  = ("'BUILT'", "'BUILT BAR'", "'BUILT PUFF'", "'BUILT SOUR PUFF'")
LOOKBACK_DAYS = 156 * 7  # 3 years ≈ 156 weeks
OUT_DIR       = Path("outputs")
OUT_DIR.mkdir(exist_ok=True)

# Discount depth buckets (matches existing pipeline convention at Q16 in register)
DEPTH_BUCKETS = [
    (0.30, "30pct_plus",  "≥30% off"),
    (0.20, "20_30pct",   "20–30% off"),
    (0.10, "10_20pct",   "10–20% off"),
    (0.00, "0_10pct",    "<10% off"),
]

# Minimum base_units to compute a meaningful lift rate (avoid div-by-zero noise)
MIN_BASE_UNITS = 5


# ── 1. Pull weekly promo data from built_filtered_weekly ──────────────────────
print("1/3  Pulling SPINS promo events from built_filtered_weekly …")

brands_sql = ", ".join(BUILT_BRANDS)

df_raw = query_druid(f"""
    SELECT
        TIME_FLOOR(__time, 'P1W')                          AS week,
        upc,
        LATEST(description)                                AS description,
        LATEST(source_brand)                               AS source_brand,
        channel_outlet,
        retail_account,

        -- Volume
        SUM(CAST(base_units  AS DOUBLE))                   AS base_units,
        SUM(CAST(incr_units  AS DOUBLE))                   AS incr_units,
        SUM(CAST(units       AS DOUBLE))                   AS total_units,

        -- Promo depth (already an avg/pct in SPINS — take weighted avg via dollars)
        SUM(CAST(arp_pct_discount_any_promo AS DOUBLE)
            * CAST(units AS DOUBLE))
          / NULLIF(SUM(CAST(units AS DOUBLE)), 0)          AS discount_depth,

        -- Mechanic-specific lift indices (SPINS MRM model outputs, %-based)
        AVG(CAST(units_lift_tpr          AS DOUBLE))       AS lift_tpr,
        AVG(CAST(units_lift_any_display  AS DOUBLE))       AS lift_display,
        AVG(CAST(units_lift_any_feature  AS DOUBLE))       AS lift_feature,

        -- Price context
        AVG(CAST(arp      AS DOUBLE))                      AS arp,
        AVG(CAST(base_arp AS DOUBLE))                      AS base_arp,

        -- Distribution
        AVG(CAST(tdp AS DOUBLE))                           AS tdp

    FROM "built_filtered_weekly"
    WHERE
        source_brand IN ({brands_sql})
        AND channel_outlet <> '{MULO_CHANNEL}'
        AND geography_raw NOT IN ({MULO_GEOS})
        AND __time >= CURRENT_TIMESTAMP - INTERVAL '{LOOKBACK_DAYS}' DAY
        -- Only weeks with measurable promotional activity
        AND (
            CAST(incr_units AS DOUBLE) > 0
            OR CAST(arp_pct_discount_any_promo AS DOUBLE) > 0.05
        )

    GROUP BY 1, 2, 5, 6
    ORDER BY retail_account, upc, week
""")

print(f"    → {len(df_raw):,} promo event weeks across "
      f"{df_raw['retail_account'].nunique()} retailers, "
      f"{df_raw['upc'].nunique()} UPCs")


# ── 2. Feature engineering ────────────────────────────────────────────────────
print("2/3  Computing lift rates and discount buckets …")

df = df_raw.copy()

# Observational lift rate: incr_units / base_units (SPINS MRM definition)
df["lift_rate_obs"] = np.where(
    (df["base_units"] > MIN_BASE_UNITS) & (df["incr_units"] > 0),
    df["incr_units"] / df["base_units"],
    np.nan,
)

# Clip extreme outliers (>5× lift rate is almost certainly a data anomaly)
df["lift_rate_obs"] = df["lift_rate_obs"].clip(upper=5.0)

# Normalize discount_depth from 0-100 scale (SPINS stores arp_pct_discount as %) to 0-1
df["discount_depth"] = df["discount_depth"] / 100

# Discount depth bucket
def depth_bucket(d):
    if pd.isna(d) or d <= 0:
        return ("no_promo", "No price reduction")
    for threshold, code, label in DEPTH_BUCKETS:
        if d >= threshold:
            return (code, label)
    return ("0_10pct", "<10% off")

df[["discount_bucket", "discount_label"]] = pd.DataFrame(
    df["discount_depth"].apply(depth_bucket).tolist(),
    index=df.index,
)

# Dominant mechanic flag (which SPINS-attributed mechanic drove the most lift)
def dominant_mechanic(row):
    m = {
        "TPR":     row["lift_tpr"]     if pd.notna(row["lift_tpr"])     else 0,
        "Display": row["lift_display"] if pd.notna(row["lift_display"]) else 0,
        "Feature": row["lift_feature"] if pd.notna(row["lift_feature"]) else 0,
    }
    if max(m.values()) <= 0:
        return "Unknown"
    return max(m, key=m.get)

df["dominant_mechanic"] = df.apply(dominant_mechanic, axis=1)

# Save raw event log
df.to_csv(OUT_DIR / "promo_lift_events.csv", index=False)
print(f"    → promo_lift_events.csv ({len(df):,} rows)")


# ── 3. Pull MO_72 causal scores (ROBUST + MODERATE) ──────────────────────────
print("3a/3  Pulling MO_72 causal scores …")

try:
    # causal_impact_pct/causal_p_value are ingested as doubleFirst metrics
    # (COMPLEX<serializablePairLongDouble>). LATEST() decodes them; AVG() nesting fails.
    # Group by robust_verdict in SQL; aggregate across events in pandas.
    df_causal_raw = query_druid("""
        SELECT
            upc,
            retail_account,
            channel_outlet,
            LATEST(causal_impact_pct) AS causal_impact_pct,
            LATEST(causal_p_value)    AS causal_p_value,
            robust_verdict
        FROM "causal_impact_scores"
        WHERE
            causal_verdict   = 'SIGNIFICANT'
            AND robust_verdict IN ('ROBUST', 'MODERATE')
        GROUP BY 1, 2, 3, 6
    """)
    df_causal = (
        df_causal_raw
        .groupby(["upc", "retail_account", "channel_outlet"])
        .agg(
            causal_impact_pct = ("causal_impact_pct", "mean"),
            causal_p_value    = ("causal_p_value",    "mean"),
            n_causal_events   = ("robust_verdict",    "count"),
            robust_verdict    = ("robust_verdict",
                                 lambda x: x.value_counts().index[0]),
        )
        .reset_index()
    )
    print(f"    → {len(df_causal):,} causal-scored series")
except Exception as e:
    print(f"    ⚠ causal_impact_scores unavailable ({e}); continuing without causal layer")
    df_causal = pd.DataFrame(columns=[
        "upc", "retail_account", "channel_outlet",
        "causal_impact_pct", "causal_p_value", "n_causal_events", "robust_verdict"
    ])


# ── 4. Aggregate to summary ───────────────────────────────────────────────────
print("3b/3  Aggregating to retailer × UPC × discount_bucket summary …")

summary = (
    df.groupby(["retail_account", "channel_outlet", "upc", "description",
                "discount_bucket", "discount_label"])
    .agg(
        n_promo_weeks    = ("week",          "count"),
        lift_rate_mean   = ("lift_rate_obs", "mean"),
        lift_rate_median = ("lift_rate_obs", "median"),
        lift_rate_p25    = ("lift_rate_obs", lambda x: x.quantile(0.25)),
        lift_rate_p75    = ("lift_rate_obs", lambda x: x.quantile(0.75)),
        lift_tpr_avg     = ("lift_tpr",      "mean"),
        lift_display_avg = ("lift_display",  "mean"),
        lift_feature_avg = ("lift_feature",  "mean"),
        discount_avg     = ("discount_depth","mean"),
        arp_avg          = ("arp",           "mean"),
        base_arp_avg     = ("base_arp",      "mean"),
        most_recent_promo= ("week",          "max"),
        dominant_mechanic= ("dominant_mechanic", lambda x: x.value_counts().index[0]),
    )
    .reset_index()
)

# Round for readability
pct_cols = ["lift_rate_mean", "lift_rate_median", "lift_rate_p25", "lift_rate_p75",
            "lift_tpr_avg", "lift_display_avg", "lift_feature_avg", "discount_avg"]
for c in pct_cols:
    summary[c] = summary[c].round(4)
summary["arp_avg"]      = summary["arp_avg"].round(2)
summary["base_arp_avg"] = summary["base_arp_avg"].round(2)

# Join causal scores (by UPC × retailer × channel — average across all events for this series)
if not df_causal.empty:
    summary = summary.merge(
        df_causal[["upc", "retail_account", "channel_outlet",
                   "causal_impact_pct", "robust_verdict", "n_causal_events"]],
        on=["upc", "retail_account", "channel_outlet"],
        how="left",
    )
else:
    summary["causal_impact_pct"] = np.nan
    summary["robust_verdict"]    = None
    summary["n_causal_events"]   = 0

# Best estimate: prefer causal where available, fall back to observational
summary["best_lift_estimate"] = np.where(
    summary["causal_impact_pct"].notna(),
    summary["causal_impact_pct"],
    summary["lift_rate_mean"],
)
summary["estimate_source"] = np.where(
    summary["causal_impact_pct"].notna(),
    "causal_" + summary["robust_verdict"].fillna("").str.lower(),
    "observational",
)

summary.to_csv(OUT_DIR / "promo_lift_summary.csv", index=False)
print(f"    → promo_lift_summary.csv ({len(summary):,} rows)")


# ── 5. Build JSON lookup for mockup ──────────────────────────────────────────
print("    Building promo_lift_lookup.json …")


def _safe(v):
    """Convert NaN/inf to None for JSON."""
    if v is None:
        return None
    try:
        if np.isnan(v) or np.isinf(v):
            return None
        return round(float(v), 4)
    except Exception:
        return None


# Top retailers by promo event count (for mockup)
top_retailers = (
    df.groupby("retail_account")["week"].count()
    .sort_values(ascending=False)
    .head(20)
    .index.tolist()
)

# Per-retailer × UPC summary (all buckets collapsed to overall stats)
rollup = (
    df.groupby(["retail_account", "channel_outlet", "upc", "description"])
    .agg(
        n_promo_weeks     = ("week",           "count"),
        lift_mean_all     = ("lift_rate_obs",  "mean"),
        lift_median_all   = ("lift_rate_obs",  "median"),
        discount_avg_all  = ("discount_depth", "mean"),
        most_recent_promo = ("week",           "max"),
        dominant_mechanic = ("dominant_mechanic", lambda x: x.value_counts().index[0]),
    )
    .reset_index()
)

# Per-bucket detail for each series
bucket_detail = (
    summary.groupby(["retail_account", "channel_outlet", "upc"])
    .apply(lambda g: [
        {
            "bucket":   row["discount_bucket"],
            "label":    row["discount_label"],
            "n":        int(row["n_promo_weeks"]),
            "lift_mean": _safe(row["lift_rate_mean"]),
            "lift_p25":  _safe(row["lift_rate_p25"]),
            "lift_p75":  _safe(row["lift_rate_p75"]),
            "mechanic":  row["dominant_mechanic"],
        }
        for _, row in g.iterrows()
    ])
    .reset_index(name="buckets")
)

lookup = {}
for _, row in rollup.iterrows():
    key = f"{row['retail_account']}|{row['channel_outlet']}|{row['upc']}"
    bd  = bucket_detail[
        (bucket_detail["retail_account"] == row["retail_account"]) &
        (bucket_detail["channel_outlet"] == row["channel_outlet"]) &
        (bucket_detail["upc"]            == row["upc"])
    ]

    # Causal score for this series
    cs = summary[
        (summary["retail_account"] == row["retail_account"]) &
        (summary["channel_outlet"] == row["channel_outlet"]) &
        (summary["upc"]            == row["upc"])
    ]
    causal_pct    = _safe(cs["causal_impact_pct"].iloc[0]) if len(cs) else None
    robust_v      = cs["robust_verdict"].iloc[0] if len(cs) else None
    _nc = cs["n_causal_events"].iloc[0] if len(cs) else 0
    n_causal = int(_nc) if pd.notna(_nc) else 0

    lookup[key] = {
        "retail_account":    row["retail_account"],
        "channel_outlet":    row["channel_outlet"],
        "upc":               row["upc"],
        "description":       row["description"],
        "n_promo_weeks":     int(row["n_promo_weeks"]),
        "lift_mean":         _safe(row["lift_mean_all"]),
        "lift_median":       _safe(row["lift_median_all"]),
        "discount_avg":      _safe(row["discount_avg_all"]),
        "most_recent_promo": str(row["most_recent_promo"])[:10] if pd.notna(row["most_recent_promo"]) else None,
        "dominant_mechanic": row["dominant_mechanic"],
        "causal_impact_pct": causal_pct,
        "robust_verdict":    robust_v,
        "n_causal_events":   n_causal,
        "best_estimate":     causal_pct if causal_pct is not None else _safe(row["lift_mean_all"]),
        "estimate_source":   f"causal_{str(robust_v).lower()}" if causal_pct is not None else "observational",
        "buckets":           bd["buckets"].iloc[0] if len(bd) else [],
    }

meta = {
    "generated_at":   datetime.now(timezone.utc).isoformat(),
    "n_series":       len(lookup),
    "n_retailers":    rollup["retail_account"].nunique(),
    "n_upcs":         rollup["upc"].nunique(),
    "top_retailers":  top_retailers,
    "causal_series":  int(rollup.shape[0]) - int((rollup["upc"].isin(
        df_causal["upc"].tolist() if not df_causal.empty else []
    )).sum()),
    "coverage_note":  (
        "Data-dark retailers (Winco, HEB, Trader Joe's) absent — "
        "no SPINS category data available for those accounts."
    ),
}

output = {"meta": meta, "lookup": lookup}

with open(OUT_DIR / "promo_lift_lookup.json", "w") as f:
    json.dump(output, f, default=str, indent=2)

print(f"    → promo_lift_lookup.json ({len(lookup):,} series, "
      f"{rollup['retail_account'].nunique()} retailers)")

# ── Summary stats ─────────────────────────────────────────────────────────────
print("\n── Summary ──────────────────────────────────────────────────────────────")
print(f"  Promo event weeks:      {len(df):,}")
print(f"  Unique retailers:       {df['retail_account'].nunique()}")
print(f"  Unique BUILT UPCs:      {df['upc'].nunique()}")
print(f"  Median obs lift rate:   {df['lift_rate_obs'].median():.1%}")
print(f"  Median discount depth:  {df['discount_depth'].median():.1%}  (of promo weeks with a measured discount)")
print(f"  Causal-scored series:   {len(df_causal)}")
print(f"\n  Mechanic breakdown (dominant):")
print(df["dominant_mechanic"].value_counts().to_string())
print(f"\n  Discount bucket breakdown:")
print(df["discount_bucket"].value_counts().to_string())
print("\nDone.")
