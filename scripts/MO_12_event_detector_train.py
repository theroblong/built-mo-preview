import os
import pickle
import lightgbm as lgb
import pandas as pd
from mo_druid_client import query_druid

os.makedirs("outputs", exist_ok=True)

MODEL_VERSION = "v1"

FEATURE_COLS = [
    "donor_base_units_pct_chg", "focal_base_units_pct_chg",
    "focal_tdp_pct_chg", "focal_velocity_spm_pct_chg",
    "donor_velocity_spm_pct_chg", "pack_distance", "relationship_distance",
    "focal_post_promo_weeks", "promo_confounded",
]


def label_significant(row) -> int:
    donor_chg = row.get("donor_base_units_pct_chg") or 0
    focal_chg = row.get("focal_base_units_pct_chg") or 0
    return int(abs(donor_chg) > 0.05 and abs(focal_chg) > 0.03)


if __name__ == "__main__":
    print("Loading training data from Druid...")
    sql = """
    SELECT *
    FROM "ml_training_features"
    WHERE label_deterministic != 'NEUTRAL'
      AND pre_13w_weeks_count >= 8
      AND post_13w_weeks_count >= 8
    """
    df = query_druid(sql)
    print(f"Rows: {len(df):,}")

    df["significant"] = df.apply(label_significant, axis=1)
    print(f"Significant events: {df['significant'].sum():,} / {len(df):,} ({df['significant'].mean():.1%})")

    available = [c for c in FEATURE_COLS if c in df.columns]
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"WARNING: missing feature columns: {missing}")

    X = df[available].fillna(0).astype(float)
    y = df["significant"]

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(X, y)

    model_path = f"outputs/model_event_{MODEL_VERSION}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"\nSaved {model_path}")
    print("Done.")
