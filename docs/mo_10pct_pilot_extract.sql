-- Mo / BUILT cannibalization pilot extract for Druid storage-constrained upload
-- Purpose: choose a useful ~10% slice without breaking time-series continuity.
-- Principle: do not random-sample rows. Keep complete weekly histories for
-- selected UPC x retail account x geography cells.

-- Replace `full_spins_export` with the client's source table or external table.
-- Replace <N_CELLS_THAT_FITS_10_PERCENT> after estimating row counts.

WITH built_cells AS (
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
  FROM full_spins_export
  WHERE "Subcategory" = 'WELLNESS & NUTRITION BARS'
    AND "Channel/Outlet" <> 'CONVENTIONAL|MILITARY'
  GROUP BY 1,2,3,4,5
),
ranked_cells AS (
  SELECT
    *,
    ROW_NUMBER() OVER (ORDER BY built_tdp DESC, built_units DESC) AS built_cell_rank
  FROM built_cells
),
selected_rows AS (
  SELECT s.*
  FROM full_spins_export s
  LEFT JOIN ranked_cells c
    ON s."Channel/Outlet" = c."Channel/Outlet"
   AND s."Retail Account" = c."Retail Account"
   AND s."Retail Account Level" = c."Retail Account Level"
   AND s."Geography Level" = c."Geography Level"
   AND s."Geography" = c."Geography"
  WHERE
    s."Subcategory" = 'WELLNESS & NUTRITION BARS'
    AND s."Channel/Outlet" <> 'CONVENTIONAL|MILITARY'
    AND (
      -- Always keep BUILT complete history.
      s."Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF')

      -- Keep Tier 1 competitor complete history in the top BUILT cells.
      OR (
        c.built_cell_rank <= <N_CELLS_THAT_FITS_10_PERCENT>
        AND s."Brand" IN (
          'RXBAR', 'BAREBELLS', 'QUEST', 'PERFECT BAR', 'THINK!',
          'ALOHA', 'NO COW', 'FULFIL', 'PURE PROTEIN',
          '1ST PHORM', 'SIMPLYPROTEIN', 'NUGO NUTRITION'
        )
      )
    )
)
SELECT *
FROM selected_rows;

-- Validation queries to run before upload:
--
-- SELECT COUNT(*) FROM selected_rows;
-- SELECT COUNT(DISTINCT "UPC") FROM selected_rows;
-- SELECT MIN("Time Period End Date"), MAX("Time Period End Date") FROM selected_rows;
-- SELECT "Brand", COUNT(*) FROM selected_rows GROUP BY 1 ORDER BY 2 DESC;
-- SELECT "Channel/Outlet", "Geography Level", COUNT(*) FROM selected_rows GROUP BY 1,2 ORDER BY 3 DESC;
