"""
Quick integration test for Q2e UNION ALL CTE query.
Picks the focal UPC × geo × channel with the most forecast weeks as test params.
"""
import pandas as pd
from mo_druid_client import query_druid

# ── 1. Pick test parameters from live data ───────────────────────────────────
print("Selecting test parameters from cannibalization_rate_forecast_weekly...")
params_df = query_druid("""
    SELECT
        focal_upc, channel_outlet, retail_account, geography_raw,
        COUNT(*) AS week_count
    FROM "cannibalization_rate_forecast_weekly"
    GROUP BY focal_upc, channel_outlet, retail_account, geography_raw
    ORDER BY week_count DESC
    LIMIT 1
""")
if params_df.empty:
    print("ERROR: cannibalization_rate_forecast_weekly is empty.")
    raise SystemExit(1)

row = params_df.iloc[0]
focal_upc      = row["focal_upc"]
channel_outlet = row["channel_outlet"]
retail_account = row["retail_account"]
geography_raw  = row["geography_raw"]
print(f"  focal_upc:      {focal_upc}")
print(f"  channel_outlet: {channel_outlet}")
print(f"  retail_account: {retail_account}")
print(f"  geography_raw:  {geography_raw}")

# ── 2a. Q2e — actuals query ──────────────────────────────────────────────────
print("\nRunning Q2e actuals query...")
actuals = query_druid(f"""
SELECT
    __time,
    'ACTUAL'                          AS series_type,
    AVG(cannibalization_rate)                  AS cannibalization_rate,
    CAST(NULL AS DOUBLE)                       AS forecast_rate_low,
    CAST(NULL AS DOUBLE)                       AS forecast_rate_high,
    AVG(cannibal_weighted_donor_loss)          AS estimated_donor_units_lost,
    MAX(CAST(donor_count AS BIGINT))           AS donor_count,
    MAX(CAST(max_donor_cannibal_prob AS DOUBLE)) AS max_donor_cannibal_prob
FROM "cannibalization_rate_weekly"
WHERE focal_upc      = '{focal_upc}'
  AND channel_outlet = '{channel_outlet}'
  AND retail_account = '{retail_account}'
  AND geography_raw  = '{geography_raw}'
  AND __time >= TIMESTAMPADD(WEEK, -8, CURRENT_TIMESTAMP)
GROUP BY __time
ORDER BY __time
""")
print(f"  Actuals rows: {len(actuals)}")

# ── 2b. Q2e — forecast query ─────────────────────────────────────────────────
print("Running Q2e forecast query...")
forecast = query_druid(f"""
SELECT
    __time,
    'FORECAST'           AS series_type,
    forecast_rate_base   AS cannibalization_rate,
    forecast_rate_low,
    forecast_rate_high,
    CAST(NULL AS DOUBLE) AS estimated_donor_units_lost,
    donor_count,
    max_donor_cannibal_prob
FROM "cannibalization_rate_forecast_weekly"
WHERE focal_upc      = '{focal_upc}'
  AND channel_outlet = '{channel_outlet}'
  AND retail_account = '{retail_account}'
  AND geography_raw  = '{geography_raw}'
ORDER BY __time
""")
print(f"  Forecast rows: {len(forecast)}")

# ── 2c. Merge in Python (UI layer would do the same) ─────────────────────────
result = pd.concat([actuals, forecast], ignore_index=True).sort_values("__time")

for col in ["cannibalization_rate", "forecast_rate_low", "forecast_rate_high",
            "estimated_donor_units_lost", "donor_count", "max_donor_cannibal_prob"]:
    if col in result.columns:
        result[col] = pd.to_numeric(result[col], errors="coerce")

print(f"\n  Total rows: {len(result)}  (ACTUAL: {(result['series_type']=='ACTUAL').sum()}  FORECAST: {(result['series_type']=='FORECAST').sum()})")
print("\nFull result (sorted by __time):")
print(result[["__time", "series_type", "cannibalization_rate",
              "forecast_rate_low", "forecast_rate_high"]].to_string(index=False))
