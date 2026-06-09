import pandas as pd
import numpy as np
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

JOIN_KEYS = [
    "focal_upc", "donor_upc", "channel_outlet", "retail_account",
    "geography_raw", "window_type", "comparison_type",
]

NUMERIC_COLS = [
    "cannibal_prob", "pack_distance", "relationship_distance",
    "donor_base_units_pct_chg", "focal_tdp_pct_chg",
    "focal_velocity_spm_pct_chg", "donor_velocity_spm_pct_chg",
    "shap_value_1", "shap_value_2", "shap_value_3",
]


def assign_event(row) -> tuple[str, str, str]:
    """Return (event_type, event_label, event_color)."""
    donor_chg  = float(row.get("donor_base_units_pct_chg") or 0)
    tdp_chg    = float(row.get("focal_tdp_pct_chg") or 0)
    vel_chg    = float(row.get("focal_velocity_spm_pct_chg") or 0)
    rel_dist   = int(float(row.get("relationship_distance") or 0))
    donor_desc = row.get("donor_description") or "?"

    if donor_chg < -0.10:
        return "DEMAND_TRANSFER", "Significant Demand Transfer Detected", "red"
    if tdp_chg > 0.15 and vel_chg < -0.03:
        return "DEMAND_TRANSFER", "Distribution-Led Gain Detected", "amber"
    if donor_chg < -0.05 and rel_dist in (3, 4):
        return "CROSS_FLAVOR_SIGNAL", f"Cross-Flavor Signal: {donor_desc} Declining", "amber"
    if donor_chg < -0.05:
        return "PACK_OVERLAP_RISK", "Pack Overlap Risk Elevated", "amber"
    return "PACK_OVERLAP_RISK", "Watch — Monitor Before Expanding", "green"


if __name__ == "__main__":
    print("Loading scored_cannibalization from Druid...")
    scored = query_druid('SELECT * FROM "scored_cannibalization"')
    print(f"  Scored rows: {len(scored):,}")

    print("Loading ml_training_features from Druid...")
    features = query_druid("""
        SELECT
            focal_upc, donor_upc, channel_outlet, retail_account,
            geography_raw, window_type, comparison_type,
            donor_base_units_pct_chg, focal_tdp_pct_chg,
            focal_velocity_spm_pct_chg, donor_velocity_spm_pct_chg,
            demand_vs_dist, incremental_share, cannibalization_rate
        FROM "ml_training_features"
        WHERE label_deterministic != 'NEUTRAL'
          AND focal_post_weeks_count >= 8
          AND donor_pre_13w_weeks_count >= 8
    """)
    print(f"  Feature rows: {len(features):,}")

    df = scored.merge(features, on=JOIN_KEYS, how="left", suffixes=("", "_mf"))

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Only surface Cannibalizing rows, plus high/medium confidence Watch rows
    surfaceable = (
        (df["cannibal_status"] == "Cannibalizing") |
        ((df["cannibal_status"] == "Watch") & (df["cannibal_confidence"].isin(["High", "Medium"])))
    )
    events_df = df[surfaceable].copy()
    print(f"  Surfaceable events: {len(events_df):,}")

    results = events_df.apply(assign_event, axis=1, result_type="expand")
    results.columns = ["event_type", "event_label", "event_color"]
    events_df = pd.concat([events_df, results], axis=1)

    events_df["assembled_at"] = datetime.now(timezone.utc).isoformat()

    output_cols = [
        "focal_upc", "focal_description",
        "donor_upc", "donor_description",
        "channel_outlet", "retail_account", "geography_raw", "geography_level",
        "window_type", "comparison_type",
        "pack_distance", "relationship_distance",
        "event_type", "event_label", "event_color",
        "cannibal_prob", "cannibal_status", "cannibal_confidence",
        "shap_feature_1", "shap_value_1",
        "shap_feature_2", "shap_value_2",
        "shap_feature_3", "shap_value_3",
        "donor_base_units_pct_chg", "focal_tdp_pct_chg",
        "demand_vs_dist", "incremental_share", "cannibalization_rate",
        "model_version", "assembled_at",
    ]
    out = events_df[[c for c in output_cols if c in events_df.columns]].copy()

    write_back(out, "event_queue", timestamp_col="assembled_at")
