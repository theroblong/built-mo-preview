import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back

MODEL_VERSION = "v1"

OWN_PRICE_FEATURES = [
    "pre_13w_avg_price_per_bar",
    "post_13w_avg_price_per_bar",
    "log_price_change",
    "pre_13w_velocity_spm",
    "pre_13w_weeks_count",
    "post_13w_weeks_count",
    "pack_count",
]

OPTIONAL_FEATURES = ["naive_price_elasticity", "promo_confounded"]


def load_scoring_data() -> pd.DataFrame:
    sql = """
    SELECT *
    FROM "price_elasticity_training_features"
    WHERE pre_13w_weeks_count >= 8
      AND post_13w_weeks_count >= 8
      AND pre_13w_base_units > 0
      AND pre_13w_avg_price_per_bar > 0
    """
    df = query_druid(sql)

    numeric_cols = [
        "pre_13w_avg_price_per_bar", "post_13w_avg_price_per_bar",
        "pre_13w_velocity_spm", "pre_13w_weeks_count", "post_13w_weeks_count",
        "pack_count", "naive_price_elasticity", "promo_confounded",
        "pre_13w_base_units", "post_13w_base_units",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["log_price_change"] = np.log(
        df["post_13w_avg_price_per_bar"].clip(lower=0.01) /
        df["pre_13w_avg_price_per_bar"].clip(lower=0.01)
    )
    return df


if __name__ == "__main__":
    print("Loading model...")
    with open(f"outputs/model_own_price_elasticity_{MODEL_VERSION}.pkl", "rb") as f:
        model = pickle.load(f)

    with open(f"outputs/price_elasticity_train_metrics.json") as f:
        metrics = json.load(f)
    features_used = metrics["features_used"]

    print("Loading scoring data from Druid...")
    df = load_scoring_data()
    print(f"Rows: {len(df):,}")

    available = [c for c in features_used if c in df.columns]
    missing = [c for c in features_used if c not in df.columns]
    if missing:
        print(f"WARNING: missing feature columns: {missing}")

    X = df[available].fillna(0)

    print("Scoring price elasticity...")
    df["predicted_log_unit_change"] = model.predict(X)

    # Convert log-unit-change back to implied elasticity: d(log Q) / d(log P)
    log_price_chg = df["log_price_change"].replace(0, np.nan)
    df["implied_elasticity"] = df["predicted_log_unit_change"] / log_price_chg

    df["elasticity_band"] = pd.cut(
        df["implied_elasticity"],
        bins=[-np.inf, -2.0, -1.0, -0.5, 0.0, np.inf],
        labels=["Highly Elastic", "Elastic", "Moderately Elastic", "Inelastic", "Positive"],
    ).astype(str)

    df["model_version"] = MODEL_VERSION
    df["scored_at"] = datetime.now(timezone.utc).isoformat()

    output_cols = [
        "upc", "description",
        "channel_outlet", "retail_account", "geography_raw", "geography_level",
        "pre_13w_avg_price_per_bar", "post_13w_avg_price_per_bar", "log_price_change",
        "pre_13w_velocity_spm", "pre_13w_weeks_count", "post_13w_weeks_count",
        "naive_price_elasticity", "promo_confounded",
        "predicted_log_unit_change", "implied_elasticity", "elasticity_band",
        "model_version", "scored_at",
    ]
    out = df[[c for c in output_cols if c in df.columns]].copy()

    write_back(out, "scored_price_elasticity", timestamp_col="scored_at")
