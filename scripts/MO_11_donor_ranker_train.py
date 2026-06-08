import os
import pickle
import lightgbm as lgb
import pandas as pd
from mo_druid_client import query_druid

os.makedirs("outputs", exist_ok=True)

MODEL_VERSION = "v1"

FEATURE_COLS = [
    "donor_base_units_pct_chg", "donor_velocity_spm_pct_chg",
    "base_units_delta_diff", "velocity_spm_delta_diff",
    "pack_distance", "relationship_distance",
    "pre_13w_base_units", "post_13w_weeks_count",
    "focal_tdp_pct_chg", "focal_base_units_pct_chg",
]


def load_ranking_data() -> tuple[pd.DataFrame, list[int]]:
    sql = """
    SELECT *
    FROM "ml_training_features"
    WHERE label_deterministic != 'NEUTRAL'
      AND pre_13w_weeks_count >= 8
      AND post_13w_weeks_count >= 8
    """
    df = query_druid(sql)

    # Must sort by focal_upc before computing group sizes —
    # LGBMRanker requires rows physically ordered by group.
    # ORDER BY is not supported in Druid top-level scans (E08/E09),
    # so sorting happens here in Python.
    df = df.sort_values("focal_upc").reset_index(drop=True)

    rel_map = {"CANNIBALIZING": 2, "WATCH": 1, "INCREMENTAL": 0}
    df["relevance"] = df["label_deterministic"].map(rel_map).fillna(0).astype(int)

    group_sizes = df.groupby("focal_upc", sort=False).size().tolist()
    return df, group_sizes


if __name__ == "__main__":
    print("Loading ranking data from Druid...")
    df, group_sizes = load_ranking_data()
    print(f"Rows: {len(df):,}  |  Groups (focal UPCs): {len(group_sizes):,}")
    print(f"Relevance distribution:\n{df['relevance'].value_counts().sort_index()}")

    available = [c for c in FEATURE_COLS if c in df.columns]
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"WARNING: missing feature columns: {missing}")

    X = df[available].fillna(0)
    y = df["relevance"]

    model = lgb.LGBMRanker(
        objective="lambdarank",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        label_gain=[0, 1, 3, 7],
        random_state=42,
    )
    model.fit(X, y, group=group_sizes)

    model_path = f"outputs/model_ranker_{MODEL_VERSION}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"\nSaved {model_path}")
    print("Done.")
