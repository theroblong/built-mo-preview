#!/usr/bin/env python
"""MO_136 step 1 - weekly category (competitor) totals from spins_full, retailer rows only, for category features.

Source: spins_full (raw SPINS, 215 columns, 2023-01-08..2026-09-06; Wellness & Nutrition Bars and Granola & Snack
Bars; competitor use on cloud compute cleared by Rob 2026-10-09). Table choice (Jason, 2026-10-12): spins_full is the
source of truth; built_filtered_weekly is a derived, nutrition-bars-only copy with a MULO label problem
(docs/DRUID_REBUILD_PLAN_2026-10.md). Only rows with a named retail account are pulled (RMA, KEY ACCOUNT, retailer
CRMA rows); geographic rollups (TOTAL US, regions, markets, MULO+C) are excluded, so the MULO label duplication
does not enter. Retailer rows in the two tables agree within ~0.5%.

Output: outputs/mo136_category_weekly.parquet, one row per week x channel_outlet x retail_account x geography_raw x
subcategory x is_built x nfp_protein_range with summed base_units / units / tdp and the number of selling UPCs.
The forecast panel's series key is upc x channel_outlet x retail_account x geography_raw (MO_25 GROUP_COLS), so
these join on the last three. This file is raw history only; features are built as of each forecast date later
(no look-ahead). Pulled one quarter at a time to stay under the Druid SQL timeout.
"""
from __future__ import annotations

# protocol: not-a-forecast-arm (raw data extract; the MO_136 experiment script carries predictions and band breakouts)
import time
from pathlib import Path

import pandas as pd

from mo_druid_client import query_druid

OUT = Path("outputs/mo136_category_weekly.parquet")
SQL = """
SELECT __time,
       "Channel/Outlet"  AS channel_outlet,
       "Retail Account"  AS retail_account,
       "Geography"       AS geography_raw,
       "Geography Level" AS geography_level,
       "Subcategory"     AS subcategory,
       CASE WHEN "Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF') THEN 1 ELSE 0 END AS is_built,
       COALESCE("NFP RANGES - PROTEIN VALUE", 'UNKNOWN') AS nfp_protein_range,
       SUM(CAST("Base Units" AS DOUBLE)) AS base_units,
       SUM(CAST("Units" AS DOUBLE))      AS units,
       SUM(CAST("TDP" AS DOUBLE))        AS tdp,
       COUNT(DISTINCT "UPC")             AS upcs_selling
FROM "spins_full"
WHERE __time >= TIMESTAMP '{t0}' AND __time < TIMESTAMP '{t1}'
  AND "Retail Account" IS NOT NULL AND "Retail Account" <> ''
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
"""
KEY = ["__time", "channel_outlet", "retail_account", "geography_raw", "subcategory", "is_built", "nfp_protein_range"]


def main() -> None:
    t_start = time.time()
    edges = pd.date_range("2023-01-01", "2026-10-01", freq="QS")
    parts = []
    for t0, t1 in zip(edges[:-1], edges[1:]):
        df = query_druid(SQL.format(t0=t0.date(), t1=t1.date()), timeout=600, retries=2)
        print(f"  {t0.date()}..{t1.date()}: {len(df):,} rows", flush=True)
        parts.append(df)
    cat = pd.concat(parts, ignore_index=True)
    cat["__time"] = pd.to_datetime(cat["__time"], utc=True)
    for c in ("base_units", "units", "tdp", "upcs_selling"):
        cat[c] = pd.to_numeric(cat[c], errors="coerce")
    assert not cat.duplicated(KEY).any(), "duplicate keys in the category extract"
    assert not cat["geography_raw"].str.contains("MULO \\+ CONV|MULO W/ CONV", regex=True).any(), "MULO rollup rows leaked in"
    cat.to_parquet(OUT)
    nb = cat[cat.subcategory == "WELLNESS & NUTRITION BARS"]
    print(f"wrote {OUT}: {len(cat):,} rows, weeks {cat['__time'].min().date()}..{cat['__time'].max().date()}, "
          f"accounts {cat['retail_account'].nunique()}, levels {sorted(cat['geography_level'].unique())}; "
          f"nutrition-bar competitor share of base units {1 - nb.loc[nb.is_built == 1, 'base_units'].sum() / nb['base_units'].sum():.3f} "
          f"({time.time() - t_start:,.0f}s)")


if __name__ == "__main__":
    main()
