import os
import pickle
import json
import lightgbm as lgb
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
from mo_druid_client import query_druid

os.makedirs("outputs", exist_ok=True)

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
LABEL_COL = "label_deterministic"


def load_training_data() -> pd.DataFrame:
    sql = """
    SELECT *
    FROM "ml_training_features"
    WHERE label_deterministic NOT IN ('NEUTRAL')
      AND focal_post_weeks_count >= 8
      AND donor_pre_13w_weeks_count >= 8
      AND donor_pre_13w_base_units > 0
    """
    df = query_druid(sql)
    df["label_binary"] = (df[LABEL_COL] == "CANNIBALIZING").astype(int)
    return df


def train(df: pd.DataFrame):
    available = [c for c in FEATURE_COLS if c in df.columns]
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"WARNING: {len(missing)} feature columns not found in data: {missing}")
    X = df[available].apply(pd.to_numeric, errors="coerce").fillna(0)
    y = df["label_binary"]

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y,
    )

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=63,
        feature_fraction=0.8,
        bagging_fraction=0.8,
        bagging_freq=5,
        min_child_samples=20,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)],
    )

    y_pred_prob = model.predict_proba(X_val)[:, 1]
    auc = roc_auc_score(y_val, y_pred_prob)
    print(f"\nVal ROC-AUC: {auc:.4f}")
    print(classification_report(y_val, (y_pred_prob >= 0.5).astype(int)))
    return model, auc, available


if __name__ == "__main__":
    print("Loading training data from Druid...")
    df = load_training_data()
    print(f"Rows: {len(df):,}  |  CANNIBALIZING: {df['label_binary'].sum():,}  |  OTHER: {(df['label_binary'] == 0).sum():,}")
    print(f"Columns available: {list(df.columns)}")

    model, auc, used_features = train(df)

    model_path = f"outputs/model_cannibal_{MODEL_VERSION}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"\nSaved {model_path}")

    fi = pd.Series(model.feature_importances_, index=used_features).sort_values(ascending=False)
    fi.to_csv(f"outputs/cannibal_feature_importance.csv")

    json.dump(
        {"roc_auc": round(auc, 4), "model_version": MODEL_VERSION,
         "n_train": len(df), "features_used": used_features},
        open(f"outputs/cannibal_train_metrics.json", "w"), indent=2,
    )
    print("Done.")
