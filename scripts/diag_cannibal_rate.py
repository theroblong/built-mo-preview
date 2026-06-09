from mo_druid_client import query_druid
import pandas as pd

print("=== cannibalization_rate_weekly distribution ===")
dist = query_druid("""
    SELECT
        COUNT(*)                                              AS total_rows,
        SUM(CASE WHEN CAST(donor_count AS BIGINT) > 0 THEN 1 ELSE 0 END) AS rows_with_donors,
        MAX(CAST(cannibalization_rate AS DOUBLE))             AS max_rate,
        AVG(CAST(cannibalization_rate AS DOUBLE))             AS avg_rate
    FROM "cannibalization_rate_weekly"
""")
print(pd.DataFrame(dist).to_string(index=False))

print("\n=== Top 10 focal UPCs by max rate ===")
top = query_druid("""
    SELECT
        focal_upc, focal_description,
        MAX(CAST(cannibalization_rate AS DOUBLE)) AS max_rate,
        MAX(CAST(donor_count AS BIGINT))          AS max_donor_count
    FROM "cannibalization_rate_weekly"
    GROUP BY focal_upc, focal_description
    ORDER BY MAX(CAST(cannibalization_rate AS DOUBLE)) DESC
    LIMIT 10
""")
print(pd.DataFrame(top).to_string(index=False))

print("\n=== Geography overlap check ===")
print("Donor geographies in scored_cannibalization (sample):")
donor_geos = query_druid("""
    SELECT DISTINCT donor_upc, channel_outlet, retail_account, geography_raw
    FROM "scored_cannibalization"
    WHERE cannibal_status IN ('Cannibalizing', 'Watch')
    LIMIT 5
""")
print(pd.DataFrame(donor_geos).to_string(index=False))

print("\nSame donor UPCs in event_detection_weekly (sample):")
if not donor_geos.empty:
    sample_donor = donor_geos.iloc[0]["donor_upc"]
    edw = query_druid(f"""
        SELECT DISTINCT upc, channel_outlet, retail_account, geography_raw
        FROM "event_detection_weekly"
        WHERE upc = '{sample_donor}'
        LIMIT 5
    """)
    print(pd.DataFrame(edw).to_string(index=False))
