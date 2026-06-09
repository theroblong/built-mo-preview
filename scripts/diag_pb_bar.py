from mo_druid_client import query_druid
import pandas as pd

rows = query_druid("""
    SELECT channel_outlet, retail_account, geography_raw,
           MAX(CAST(donor_count AS BIGINT))             AS max_donors,
           MAX(CAST(cannibalization_rate AS DOUBLE))    AS max_rate
    FROM "cannibalization_rate_weekly"
    WHERE focal_upc = '08-40229-30115'
      AND CAST(donor_count AS BIGINT) > 0
    GROUP BY channel_outlet, retail_account, geography_raw
    ORDER BY MAX(CAST(cannibalization_rate AS DOUBLE)) DESC
    LIMIT 10
""")
print(pd.DataFrame(rows).to_string(index=False))
