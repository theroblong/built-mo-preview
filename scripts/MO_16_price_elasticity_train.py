import os
import pickle
import json
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from mo_druid_client import query_druid

os.makedirs("outputs", exist_ok=True)

MODEL_VERSION = "v1"

# Confirmed columns from Q17 (price_elasticity_training_features).
# log_price_change and log_unit_change are computed below from pre/post price and units.
OWN_PRICE_FEATURES = [
    "pre_13w_avg_price_per_bar",
    "post_13w_avg_price_per_bar",
    "log_price_change",
    "pre_13w_velocity_spm",
    "pre_13w_weeks_count",
    "post_13w_weeks_count",
    "pack_count",
]

# These columns may or may not be present in Q17 depending on what was built.
# They'll be added to the feature set only if found in the data.
OPTIONAL_FEATURES = [
    "naive_price_elasticity",
    "promo_confounded",
]


def load_elasticity_data() -> pd.DataFrame:
    sql = """
    SELECT *
    FROM "price_elasticity_training_features"
    WHERE pre_13w_weeks_count >= 8
      AND post_13w_weeks_count >= 8
      AND pre_13w_base_units > 0
      AND pre_13w_avg_price_per_bar > 0
    """
    df = query_druid(sql)

    # Druid returns numeric columns as object dtype in JSON response
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
    df["log_unit_change"] = np.log(
        (df["post_13w_base_units"] + 1) /
        (df["pre_13w_base_units"] + 1)
    )
    return df


def train_own_price(df: pd.DataFrame):
    optional_available = [c for c in OPTIONAL_FEATURES if c in df.columns]
    feature_cols = OWN_PRICE_FEATURES + optional_available
    missing = [c for c in OWN_PRICE_FEATURES if c not in df.columns]
    if missing:
        print(f"WARNING: missing required feature columns: {missing}")

    valid = df[feature_cols + ["log_unit_change"]].dropna()
    print(f"Training rows after dropna: {len(valid):,} (dropped {len(df) - len(valid):,} rows with nulls)")

    X = valid[feature_cols]
    y = valid["log_unit_change"]

    X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
    )
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(30), lgb.log_evaluation(30)],
    )

    preds = model.predict(X_val)
    mae = mean_absolute_error(y_val, preds)
    r2 = r2_score(y_val, preds)
    print(f"\nOwn-price  MAE={mae:.4f}  R²={r2:.4f}")
    return model, mae, r2, feature_cols


if __name__ == "__main__":
    print("Loading elasticity training data from Druid...")
    df = load_elasticity_data()
    print(f"Rows: {len(df):,}")
    print(f"Columns available: {list(df.columns)}")

    model_own, mae, r2, features_used = train_own_price(df)

    model_path = f"outputs/model_own_price_elasticity_{MODEL_VERSION}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model_own, f)
    print(f"\nSaved {model_path}")

    json.dump(
        {"mae": round(mae, 4), "r2": round(r2, 4), "model_version": MODEL_VERSION,
         "n_train": len(df), "features_used": features_used},
        open(f"outputs/price_elasticity_train_metrics.json", "w"), indent=2,
    )
    print("Done.")
