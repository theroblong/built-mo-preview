import pandas as pd
from datetime import datetime, timezone
from mo_druid_client import query_druid
from mo_writeback import write_back


def build_new_pack_events(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        pack_desc = row.get("description") or "?"
        partner_desc = row.get("closest_pack_partner_description")
        label = f"New pack size detected: {pack_desc}"
        if partner_desc:
            label += f" (closest partner: {partner_desc})"

        rows.append({
            "focal_upc":                    row["upc"],
            "focal_description":            pack_desc,
            "pack_count":                   row.get("pack_count"),
            "size_oz":                      row.get("size_oz"),
            "closest_pack_partner_upc":     row.get("closest_pack_partner_upc"),
            "closest_pack_partner_description": partner_desc,
            "flavor_taxonomy_conflict":     row.get("flavor_taxonomy_conflict"),
            "manual_review_needed":         row.get("manual_review_needed"),
            "event_type":                   "NEW_PACK_SIZE",
            "event_label":                  label,
            "event_color":                  "amber",
            "cannibal_prob":                None,
            "cannibal_status":              "Watch",
            "cannibal_confidence":          "Medium",
            "model_version":                "deterministic",
            "assembled_at":                 datetime.now(timezone.utc).isoformat(),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("Loading new_upc_classifications from Druid...")
    df = query_druid("""
        SELECT *
        FROM "new_upc_classifications"
        WHERE upc_classification = 'NEW_PACK_SIZE'
    """)
    print(f"  New pack size UPCs: {len(df):,}")

    if df.empty:
        print("No new pack size records — nothing to enroll.")
    else:
        events = build_new_pack_events(df)
        print(f"  Events to write: {len(events):,}")
        write_back(events, "event_queue", timestamp_col="assembled_at")
