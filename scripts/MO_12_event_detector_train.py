import os
import pickle
import lightgbm as lgb
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
from mo_druid_client import query_druid

os.makedirs("outputs", exist_ok=True)

MODEL_VERSION = "v1"

# focal_*_pct_chg columns are structurally NULL (no focal pre-window in SPINS
# before first_week_selling) and contribute zero variance — excluded.
FEATURE_COLS = [
    "donor_base_units_pct_chg",
    "donor_velocity_spm_pct_chg",
    "pack_distance",
    "relationship_distance",
    "focal_post_promo_weeks",
    "promo_confounded",
]


def label_significant(row) -> int:
    # focal_base_units_pct_chg is NULL for all rows — focal items have no
    # pre-window data in SPINS before first_week_selling (confirmed Q5).
    # Use donor decline as the signal: donor is an established product
    # with real pre/post data.
    if str(row.get("label_deterministic") or "") != "CANNIBALIZING":
        return 0
    try:
        return int(float(row.get("donor_base_units_pct_chg")) < -0.05)
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    print("Loading training data from Druid...")
    sql = """
    SELECT *
    FROM "ml_training_features"
    WHERE label_deterministic != 'NEUTRAL'
      AND focal_post_weeks_count >= 8
      AND donor_pre_13w_weeks_count >= 8
    """
    df = query_druid(sql)
    print(f"Rows: {len(df):,}")

    df["significant"] = df.apply(label_significant, axis=1)
    print(f"Significant events: {df['significant'].sum():,} / {len(df):,} ({df['significant'].mean():.1%})")

    available = [c for c in FEATURE_COLS if c in df.columns]
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"WARNING: missing feature columns: {missing}")

    X = df[available].apply(pd.to_numeric, errors="coerce").fillna(0)

    # Clip extreme pct_chg outliers — values like 5098% are data artifacts
    # (tiny pre-window denominators) and break LightGBM's histogram binning.
    for col in ["donor_base_units_pct_chg", "donor_velocity_spm_pct_chg"]:
        if col in X.columns:
            X[col] = X[col].clip(-1.0, 2.0)

    y = df["significant"]

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y,
    )

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
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

    model_path = f"outputs/model_event_{MODEL_VERSION}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"\nSaved {model_path}")
    print("Done.")
