from mo_druid_client import query_druid
import pandas as pd

rows = query_druid("""
    SELECT __time,
           CAST(cannibalization_rate AS DOUBLE) AS rate,
           CAST(donor_count AS BIGINT)          AS donors
    FROM "cannibalization_rate_weekly"
    WHERE focal_upc      = '08-40229-30115'
      AND channel_outlet = 'CONVENTIONAL|MULTI OUTLET'
      AND retail_account = 'WALGREENS BOOTS ALLIANCE'
    ORDER BY __time
""")
df = pd.DataFrame(rows)
df["rate"] = pd.to_numeric(df["rate"])
df["donors"] = pd.to_numeric(df["donors"])
print(f"Total weeks: {len(df)}")
print(f"Non-zero rate weeks: {(df['rate'] > 0).sum()}")
print(f"\nNon-zero weeks:")
print(df[df["rate"] > 0][["__time", "rate", "donors"]].to_string(index=False))
