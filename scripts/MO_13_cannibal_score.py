import pickle
import shap
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

MODEL_VERSION = "v1"

FEATURE_COLS = [
    "donor_base_units_pct_chg", "focal_base_units_pct_chg",
    "base_units_delta_diff", "focal_tdp_pct_chg",
    "focal_velocity_spm_pct_chg", "donor_velocity_spm_pct_chg",
    "velocity_spm_delta_diff", "pack_distance", "relationship_distance",
    "focal_price_per_unit", "focal_post_promo_weeks", "donor_post_13w_promo_weeks",
    "focal_post_units_pct_promo", "donor_post_13w_units_pct_promo",
    "focal_post_arp_discount", "donor_post_13w_arp_discount",
    "focal_arp_pct_chg", "focal_promo_week_delta", "donor_promo_week_delta",
]


def assign_confidence(pre_wks, post_wks) -> str:
    try:
        pre_wks, post_wks = float(pre_wks or 0), float(post_wks or 0)
    except (TypeError, ValueError):
        return "Low"
    if pre_wks >= 12 and post_wks >= 10:
        return "High"
    if pre_wks >= 8 and post_wks >= 8:
        return "Medium"
    return "Low"


def top_shap_drivers(shap_row, feature_names, n=3):
    idx = np.argsort(np.abs(shap_row))[::-1][:n]
    return [(feature_names[i], float(shap_row[i])) for i in idx]


if __name__ == "__main__":
    print("Loading models...")
    with open(f"outputs/model_cannibal_{MODEL_VERSION}.pkl", "rb") as f:
        model_cannibal = pickle.load(f)
    with open(f"outputs/model_ranker_{MODEL_VERSION}.pkl", "rb") as f:
        model_ranker = pickle.load(f)

    print("Loading scoring data from Druid...")
    sql = """
    SELECT *
    FROM "ml_training_features"
    WHERE label_deterministic != 'NEUTRAL'
      AND focal_post_weeks_count >= 8
      AND donor_pre_13w_weeks_count >= 8
    """
    df = query_druid(sql)
    print(f"Rows: {len(df):,}")

    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].apply(pd.to_numeric, errors="coerce").fillna(0)

    print("Scoring cannibalization probability...")
    df["cannibal_prob"] = model_cannibal.predict_proba(X)[:, 1]
    df["cannibal_status"] = pd.cut(
        df["cannibal_prob"],
        bins=[-0.001, 0.35, 0.65, 1.001],
        labels=["Incremental", "Watch", "Cannibalizing"],
    ).astype(str)

    print("Computing SHAP drivers...")
    explainer = shap.TreeExplainer(model_cannibal)
    shap_matrix = explainer.shap_values(X)
    if isinstance(shap_matrix, list):
        shap_matrix = shap_matrix[1]
    drivers = [top_shap_drivers(row, available) for row in shap_matrix]
    df["shap_feature_1"] = [d[0][0] if len(d) > 0 else None for d in drivers]
    df["shap_value_1"]   = [d[0][1] if len(d) > 0 else None for d in drivers]
    df["shap_feature_2"] = [d[1][0] if len(d) > 1 else None for d in drivers]
    df["shap_value_2"]   = [d[1][1] if len(d) > 1 else None for d in drivers]
    df["shap_feature_3"] = [d[2][0] if len(d) > 2 else None for d in drivers]
    df["shap_value_3"]   = [d[2][1] if len(d) > 2 else None for d in drivers]

    df["cannibal_confidence"] = [
        assign_confidence(r.get("focal_pre_weeks_count"), r.get("focal_post_weeks_count"))
        for _, r in df.iterrows()
    ]
    df["model_version"] = MODEL_VERSION
    df["scored_at"] = datetime.now(timezone.utc).isoformat()

    output_cols = [
        "focal_upc", "focal_description", "donor_upc", "donor_description",
        "channel_outlet", "retail_account", "geography_raw", "geography_level",
        "window_type", "comparison_type", "pack_distance", "relationship_distance",
        "cannibal_prob", "cannibal_status", "cannibal_confidence",
        "shap_feature_1", "shap_value_1",
        "shap_feature_2", "shap_value_2",
        "shap_feature_3", "shap_value_3",
        "model_version", "scored_at",
    ]
    out = df[[c for c in output_cols if c in df.columns]].copy()

    write_back(out, "scored_cannibalization", timestamp_col="scored_at")
