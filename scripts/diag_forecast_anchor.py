from mo_druid_client import query_druid
import pandas as pd

# Find series where the anchor rate (last 8 weeks of actuals) was non-zero
# Data ends ~4/19/26, so last 8 weeks = approx 2026-02-22 through 2026-04-19
rows = query_druid("""
    SELECT focal_upc, focal_description, channel_outlet, retail_account, geography_raw,
           AVG(CAST(cannibalization_rate AS DOUBLE)) AS avg_rate_last8,
           MAX(CAST(cannibalization_rate AS DOUBLE)) AS max_rate_last8
    FROM "cannibalization_rate_weekly"
    WHERE __time >= '2026-02-22'
    GROUP BY focal_upc, focal_description, channel_outlet, retail_account, geography_raw
    HAVING AVG(CAST(cannibalization_rate AS DOUBLE)) > 0
    ORDER BY AVG(CAST(cannibalization_rate AS DOUBLE)) DESC
    LIMIT 20
""")
df = pd.DataFrame(rows)
if df.empty:
    print("No series with non-zero rate in the last 8 weeks of data.")
else:
    print(f"{len(df)} series with active cannibalization in final 8 weeks:\n")
    print(df.to_string(index=False))
