# Mo Cannibalization Tool: 10% Pilot Extract Recommendation

## Executive Recommendation

For the 78GB expanded SPINS CSV stored in the client’s S3-compatible MinIO bucket, we should not load the full file into a separate SQL database just to create the 10% pilot sample.

Recommended approach:

1. Use **DuckDB** for the first pilot extraction if this is a one-time or analyst-controlled process.
2. Use **Spark / PySpark** if the client expects repeated large-scale extracts, multiple files, or distributed processing needs.
3. Export the selected pilot slice to **Parquet**, then ingest Parquet into Druid.

The key point: the “10% sample” should not be random rows. It should be a **complete-history, business-relevant slice** that preserves full weekly time series for selected UPC × retail account × geography cells.

## Why Not Random 10% Sampling?

Random row sampling would break the core cannibalization logic:

- Pre/post launch windows would be incomplete.
- Prior-quarter comparisons would be unreliable.
- Year-over-year same-period checks would be damaged.
- New UPC and ramp detection could miss critical weeks.
- Druid and LightGBM features would be trained on discontinuous time series.

For this project, preserving time continuity is more valuable than preserving a random percentage of total rows.

## Recommended 10% Selection Strategy

Upload a complete-history pilot slice:

1. **100% of BUILT rows**
   - Required for focal SKU history, pack ladders, ramp monitoring, and all client-facing examples.

2. **Top BUILT retail/geography cells**
   - Rank cells by BUILT TDP and units.
   - Keep complete weekly history for selected cells.

3. **Tier 1 competitor rows in the same cells**
   - Include brands such as RXBAR, BAREBELLS, QUEST, PERFECT BAR, THINK!, ALOHA, NO COW, FULFIL, PURE PROTEIN, 1ST PHORM, SIMPLYPROTEIN, and NUGO NUTRITION.

4. **Full time history**
   - Preferred: 104 weeks.
   - Minimum useful history: 65 weeks.
   - Do not drop random weeks.

5. **All expanded SPINS columns**
   - Keep the 214-column expanded schema from `All_items_extract_41926-h100.csv`.
   - Storage pressure should be handled by row selection first, not by dropping fields that may be needed for QA, seasonality, promo controls, or future model features.

## Recommended Tooling

### Option 1: DuckDB

Best for:

- Fast pilot extract
- Minimal infrastructure
- Analyst or engineer running from a laptop, Azure VM, or lightweight job runner
- Direct querying from S3-compatible MinIO

Benefits:

- Reads CSV directly from MinIO.
- Can execute SQL filters and joins.
- Can write Parquet directly back to object storage.
- Much less setup than a full SQL database or Spark cluster.

### Option 2: Spark / PySpark

Best for:

- Repeated production-scale extracts
- Multiple large files
- Client already has Spark infrastructure
- Need distributed processing and fault tolerance

Benefits:

- More scalable for repeated large jobs.
- Better for multi-file pipelines.
- Strong fit if this becomes a scheduled production process.

### Option 3: Trino / Presto

Best for:

- Client already has Trino/Presto over object storage.
- Team wants a SQL service over MinIO.

Benefits:

- Good query interface over object storage.
- More infrastructure than DuckDB, less custom code than Spark.

## Suggested Pilot Flow

1. Read the 78GB CSV directly from MinIO.
2. Rank retail/geography cells by BUILT TDP and BUILT units.
3. Select enough top cells to fit the storage budget.
4. Keep all BUILT rows and Tier 1 competitor rows for those cells.
5. Preserve full weekly history.
6. Write the result to Parquet.
7. Load the Parquet pilot into Druid.
8. Run Druid SQL feature engineering and Python/LightGBM model tests.

## Example DuckDB Pattern

```sql
INSTALL httpfs;
LOAD httpfs;

SET s3_endpoint='minio-host:9000';
SET s3_access_key_id='...';
SET s3_secret_access_key='...';
SET s3_use_ssl=false;
SET s3_url_style='path';

CREATE TABLE spins AS
SELECT *
FROM read_csv_auto('s3://bucket/path/full_spins.csv', header=true);
```

Rank cells:

```sql
CREATE TABLE built_cells AS
SELECT
  "Channel/Outlet",
  "Retail Account",
  "Retail Account Level",
  "Geography Level",
  "Geography",
  SUM(CASE
    WHEN "Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF')
    THEN COALESCE("TDP", 0)
    ELSE 0
  END) AS built_tdp,
  SUM(CASE
    WHEN "Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF')
    THEN COALESCE("Units", 0)
    ELSE 0
  END) AS built_units
FROM spins
WHERE "Subcategory" = 'WELLNESS & NUTRITION BARS'
GROUP BY 1,2,3,4,5;
```

Export selected pilot rows to Parquet:

```sql
COPY (
  SELECT s.*
  FROM spins s
  JOIN built_cells c
    USING (
      "Channel/Outlet",
      "Retail Account",
      "Retail Account Level",
      "Geography Level",
      "Geography"
    )
  WHERE s."Subcategory" = 'WELLNESS & NUTRITION BARS'
    AND (
      s."Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF')
      OR s."Brand" IN (
        'RXBAR', 'BAREBELLS', 'QUEST', 'PERFECT BAR', 'THINK!',
        'ALOHA', 'NO COW', 'FULFIL', 'PURE PROTEIN',
        '1ST PHORM', 'SIMPLYPROTEIN', 'NUGO NUTRITION'
      )
    )
)
TO 's3://bucket/path/mo_pilot_10pct/'
(FORMAT PARQUET);
```

## Recommendation for Client Discussion

For Friday’s client meeting, recommend:

- Use **DuckDB or Spark to query directly from MinIO**.
- Export the pilot slice as **Parquet**, not CSV.
- Ingest the Parquet slice into Druid.
- Keep complete time series for selected cells.
- Use row/cell selection to manage storage, not random row sampling.
- Confirm whether the storage constraint is driven by raw object storage, Druid segment size, retained history, or total row count.

## Bottom Line

The best 10% pilot is not a random 10%. It is a complete, strategically selected slice:

**100% BUILT + Tier 1 competitors + top BUILT retail/geography cells + complete weekly history + all expanded SPINS fields.**

That gives us enough continuity to test Druid ingestion, feature engineering, pre/post logic, Pool Health, year-over-year controls, and LightGBM model definition without loading the entire 78GB file.

---

## Quick Email Text

Subject: Recommendation for 10% SPINS Pilot Extract from MinIO

Hi [Boss Name],

For the 78GB expanded SPINS CSV in the client’s MinIO/S3 bucket, I recommend we avoid random row sampling and avoid loading the full file into a separate SQL database just to create the pilot.

Instead, we should query the file directly from MinIO using DuckDB for the first pilot, or Spark if the client prefers a distributed production approach. The output should be written to Parquet and then loaded into Druid.

The 10% sample should be a complete-history business slice: 100% of BUILT rows, Tier 1 competitor rows in the same selected retail/geography cells, full weekly history, and all expanded SPINS columns. This preserves pre/post windows, prior-quarter comparisons, YoY checks, ramp detection, and LightGBM feature engineering.

In short: do not random-sample 10% of rows. Select the highest-value retail/geography cells by BUILT TDP/units, keep the complete time series, export to Parquet, then ingest into Druid.

I’ve drafted a short recommendation document and sample SQL for this approach.

Thanks,
[Your Name]
