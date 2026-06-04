-- Druid SQL artifact: weekly delta features using raw SPINS-style fields
--
-- This version is intentionally aligned to the column naming pattern found in
-- All_items_extract_100.csv, for example:
-- - "Geography"
-- - "Time Period"
-- - "Time Period End Date"
-- - "UPC"
-- - "Units"
-- - "Base Units"
-- - "Incr Units"
--
-- Important limitation:
-- The current All_items_extract_100.csv sample is a rolled-up extract and is
-- not a true weekly panel. A real LAG-based week-over-week feature requires a
-- weekly-grain SPINS datasource with one row per UPC + geography + week.
--
-- In other words:
-- - this SQL is correct for a weekly SPINS table that uses the same headers
-- - this SQL should not be expected to produce meaningful WoW deltas from the
--   current 52-week-style sample extract by itself


-- ---------------------------------------------------------------------------
-- Pattern 1: weekly SPINS table using raw SPINS headers
-- ---------------------------------------------------------------------------
--
-- Assumed source:
-- a Druid datasource loaded from SPINS weekly exports with columns matching
-- the SPINS naming pattern seen in All_items_extract_100.csv.
--
-- Assumed grain:
-- one row per "UPC" + "Geography" + "Time Period End Date"
--
-- If your real weekly feed includes additional dimensions such as retailer,
-- channel, or store, add them to both SELECT and PARTITION BY.

WITH spins_weekly_base AS (
  SELECT
    CAST("Time Period End Date" AS TIMESTAMP) AS week_end_date,
    "Geography" AS geography_name,
    "Brand" AS brand,
    "UPC" AS upc,
    "Description" AS description,
    CAST("Units" AS DOUBLE) AS units,
    CAST("Base Units" AS DOUBLE) AS base_units,
    CAST("Incr Units" AS DOUBLE) AS incr_units,
    CAST("Units, Promo" AS DOUBLE) AS units_promo,
    CAST("Units, Non-Promo" AS DOUBLE) AS units_non_promo,
    CAST("TDP" AS DOUBLE) AS tdp,
    CAST("Dollars" AS DOUBLE) AS dollars,
    CAST("ARP" AS DOUBLE) AS arp
  FROM spins_weekly_raw
  WHERE "Time Period" IN ('1 Week', 'Latest 1 Weeks')
),
spins_weekly_with_lags AS (
  SELECT
    week_end_date,
    geography_name,
    brand,
    upc,
    description,
    units,
    base_units,
    incr_units,
    units_promo,
    units_non_promo,
    tdp,
    dollars,
    arp,
    LAG(units, 1) OVER (
      PARTITION BY upc, geography_name
      ORDER BY week_end_date
    ) AS units_lag_1,
    LAG(base_units, 1) OVER (
      PARTITION BY upc, geography_name
      ORDER BY week_end_date
    ) AS base_units_lag_1,
    LAG(tdp, 1) OVER (
      PARTITION BY upc, geography_name
      ORDER BY week_end_date
    ) AS tdp_lag_1,
    LAG(arp, 1) OVER (
      PARTITION BY upc, geography_name
      ORDER BY week_end_date
    ) AS arp_lag_1
  FROM spins_weekly_base
)
SELECT
  week_end_date,
  geography_name,
  brand,
  upc,
  description,
  units,
  base_units,
  incr_units,
  units_promo,
  units_non_promo,
  tdp,
  dollars,
  arp,
  units_lag_1,
  base_units_lag_1,
  tdp_lag_1,
  arp_lag_1,
  units - units_lag_1 AS units_wow_delta,
  base_units - base_units_lag_1 AS base_units_wow_delta,
  tdp - tdp_lag_1 AS tdp_wow_delta,
  arp - arp_lag_1 AS arp_wow_delta,
  CASE
    WHEN units_lag_1 IS NULL OR units_lag_1 = 0 THEN NULL
    ELSE (units / units_lag_1) - 1
  END AS units_wow_pct,
  CASE
    WHEN base_units_lag_1 IS NULL OR base_units_lag_1 = 0 THEN NULL
    ELSE (base_units / base_units_lag_1) - 1
  END AS base_units_wow_pct,
  CASE
    WHEN tdp_lag_1 IS NULL OR tdp_lag_1 = 0 THEN NULL
    ELSE (tdp / tdp_lag_1) - 1
  END AS tdp_wow_pct,
  units - base_units AS promo_gap_units
FROM spins_weekly_with_lags
ORDER BY upc, geography_name, week_end_date;


-- ---------------------------------------------------------------------------
-- Pattern 2: optional filtered version for a single brand or UPC set
-- ---------------------------------------------------------------------------
--
-- This is useful for validation when you want to inspect a small subset of
-- BUILT products before pushing the logic into a wider feature pipeline.

WITH built_weekly_base AS (
  SELECT
    CAST("Time Period End Date" AS TIMESTAMP) AS week_end_date,
    "Geography" AS geography_name,
    "Brand" AS brand,
    "UPC" AS upc,
    "Description" AS description,
    CAST("Units" AS DOUBLE) AS units,
    CAST("Base Units" AS DOUBLE) AS base_units,
    CAST("Incr Units" AS DOUBLE) AS incr_units
  FROM spins_weekly_raw
  WHERE "Time Period" IN ('1 Week', 'Latest 1 Weeks')
    AND UPPER("Brand") LIKE 'BUILT%'
),
built_weekly_with_lags AS (
  SELECT
    week_end_date,
    geography_name,
    brand,
    upc,
    description,
    units,
    base_units,
    incr_units,
    LAG(units, 1) OVER (
      PARTITION BY upc, geography_name
      ORDER BY week_end_date
    ) AS units_lag_1,
    LAG(base_units, 1) OVER (
      PARTITION BY upc, geography_name
      ORDER BY week_end_date
    ) AS base_units_lag_1
  FROM built_weekly_base
)
SELECT
  week_end_date,
  geography_name,
  brand,
  upc,
  description,
  units,
  base_units,
  incr_units,
  units - units_lag_1 AS units_wow_delta,
  base_units - base_units_lag_1 AS base_units_wow_delta,
  CASE
    WHEN units_lag_1 IS NULL OR units_lag_1 = 0 THEN NULL
    ELSE (units / units_lag_1) - 1
  END AS units_wow_pct,
  CASE
    WHEN base_units_lag_1 IS NULL OR base_units_lag_1 = 0 THEN NULL
    ELSE (base_units / base_units_lag_1) - 1
  END AS base_units_wow_pct
FROM built_weekly_with_lags
ORDER BY upc, geography_name, week_end_date;


-- ---------------------------------------------------------------------------
-- Notes for interpretation
-- ---------------------------------------------------------------------------
--
-- 1. "Incr Units" is a promo-attributed measure, not a generic weekly delta.
-- 2. "units_wow_delta" captures observed sales movement from one week to the next.
-- 3. "base_units_wow_delta" is usually the cleaner cannibalization signal because
--    it reduces promo distortion.
-- 4. "tdp_wow_delta" helps separate true demand shifts from distribution changes.
-- 5. If your weekly source has gaps, consider building a complete UPC x geography
--    x week spine before applying LAG so missing weeks do not hide sharp changes.
