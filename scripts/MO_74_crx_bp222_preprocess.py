"""
MO_74 — Circana CRX BP222 Preprocessing
Reads raw BP222 CSV, normalizes fields, and writes a clean Parquet file
ready for Druid batch ingestion into costco_crx_weekly.

Usage:
    python MO_74_crx_bp222_preprocess.py <path/to/BP222.csv>
    python MO_74_crx_bp222_preprocess.py <path/to/BP222.csv> --output outputs/costco_crx_weekly.parquet

What it does:
    1. Renames 32 BP222 headers to clean snake_case names
    2. Parses "N week ending MM-DD-YYYY" → ISO date (week_ending)
    3. Strips Circana currency formatting: "$1,234.56" → 1234.56, "($19.99)" → -19.99
    4. Parses comma-formatted numeric strings
    5. Adds derived columns: is_mvm (Coupon Units > 0), dpwpw ($/WH/week)
    6. Writes Parquet — ready for Druid ingestion spec (see docs/CRX_Druid_Ingestion_Guide.md)

Target Druid table: costco_crx_weekly
Primary time column: week_ending (Sunday of the Costco Mon–Sun week)

NOTE — Week boundary: BP222 weeks end Sunday (matches SPINS week_ending).
       Direct join on week_ending is valid. No date offset needed.

NOTE — Units: 1 CRX unit = 1 Club Pack (16 or 18 BUILT Bars). Not individual bars.
       Do not compare unit_sales directly to SPINS base_units without pack conversion.
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

# BP222 column headers → clean names
COLUMN_MAP = {
    "Item":                                  "item_desc",
    "Venue":                                 "warehouse_name",
    "Time":                                  "time_raw",
    "Region [ Region_warehouse ]":           "region",
    "Dollar Sales":                          "dollar_sales",
    "Unit Sales":                            "unit_sales",
    "Days of Supply":                        "days_of_supply",
    "Inventory Turns":                       "inventory_turns",
    "Inventory On Hand":                     "on_hand",
    "On Order":                              "on_order",
    "In Transit":                            "in_transit",
    "Quantity Received":                     "qty_received",
    "OOS":                                   "oos",
    "Warehouses Selling":                    "warehouses_selling",
    "Number of Warehouses":                  "num_warehouses",
    "Flavor":                                "flavor",
    "Flavor / Scent":                        "flavor_scent",
    "% Discount":                            "pct_discount",
    "Average Coupon Value":                  "avg_coupon_value",
    "Average Promoted Price":                "avg_promoted_price",
    "Coupon Dollars":                        "coupon_dollars",
    "Coupon Units":                          "coupon_units",
    "Non Promoted Dollars":                  "non_promoted_dollars",
    "Non Promoted Units":                    "non_promoted_units",
    "Promoted Dollars":                      "promoted_dollars",
    "Promoted Units":                        "promoted_units",
    "Total Discount Dollars":                "total_discount_dollars",
    "Average Diesel Fuel Price per gallon":  "fuel_price_diesel",
    "Average Regular Gas Price per gallon":  "fuel_price_regular",
    "Average Mid-grade Gas Price per gallon":"fuel_price_midgrade",
    "Average Premium Gas Price per gallon":  "fuel_price_premium",
    "In Stock %":                            "in_stock_pct",
}

# Circana-formatted dollar strings: "$1,234.56" or "($19.99)"
DOLLAR_COLS = [
    "dollar_sales", "avg_coupon_value", "avg_promoted_price",
    "coupon_dollars", "non_promoted_dollars", "promoted_dollars",
    "total_discount_dollars", "fuel_price_diesel", "fuel_price_regular",
    "fuel_price_midgrade", "fuel_price_premium",
]

# Comma-formatted numeric strings: "1,234"
NUMERIC_COLS = [
    "unit_sales", "days_of_supply", "inventory_turns", "on_hand", "on_order",
    "in_transit", "qty_received", "oos", "warehouses_selling", "num_warehouses",
    "pct_discount", "coupon_units", "non_promoted_units", "promoted_units",
    "in_stock_pct",
]


def parse_dollar(val):
    if pd.isna(val) or str(val).strip() == "":
        return None
    s = str(val).strip()
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[$(,)]", "", s).strip()
    try:
        return -float(s) if neg else float(s)
    except ValueError:
        return None


def parse_numeric(val):
    if pd.isna(val) or str(val).strip() == "":
        return None
    s = str(val).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_week_ending(val):
    """'1 week ending 09-14-2026' → '2026-09-14' (Sunday = CRX week end date)"""
    if pd.isna(val):
        return None
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{4})", str(val))
    if m:
        mm, dd, yyyy = m.groups()
        return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
    return None


def main():
    parser = argparse.ArgumentParser(
        description="BP222 CRX preprocessing — outputs clean Parquet for Druid"
    )
    parser.add_argument("input", help="Path to raw BP222 CSV file")
    parser.add_argument(
        "--output",
        default="outputs/costco_crx_weekly.parquet",
        help="Output Parquet path (default: outputs/costco_crx_weekly.parquet)",
    )
    args = parser.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"ERROR: Input file not found: {src}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {src} ...")
    df = pd.read_csv(src, low_memory=False)
    print(f"  Loaded  {len(df):,} rows x {len(df.columns)} columns")

    # Rename to clean names (ignore any BP222 columns not in map)
    df = df.rename(columns=COLUMN_MAP)

    # Parse week_ending from "N week ending MM-DD-YYYY"
    df = df.copy()
    df.loc[:, "week_ending"] = df["time_raw"].apply(parse_week_ending)
    bad_dates = df["week_ending"].isna().sum()
    if bad_dates:
        print(f"  WARNING: {bad_dates:,} rows with unparseable Time — dropped")
    df = df[df["week_ending"].notna()].copy()

    # Parse dollar fields
    for col in DOLLAR_COLS:
        if col in df.columns:
            df.loc[:, col] = df[col].apply(parse_dollar)

    # Parse numeric fields
    for col in NUMERIC_COLS:
        if col in df.columns:
            df.loc[:, col] = df[col].apply(parse_numeric)

    # Derived: MVM flag — promoted_units > 0 is the correct signal.
    # coupon_units is stored as a negative number by Circana (deduction from non-promoted);
    # promoted_units is the positive counterpart and is the reliable MVM indicator.
    df["is_mvm"] = (df["promoted_units"].fillna(0) > 0).astype(int)

    # Derived: DPWPW — best Costco velocity metric
    df["dpwpw"] = df.apply(
        lambda r: (
            r["dollar_sales"] / r["warehouses_selling"]
            if pd.notna(r["dollar_sales"])
            and pd.notna(r["warehouses_selling"])
            and r["warehouses_selling"] > 0
            else None
        ),
        axis=1,
    )

    df = df.drop(columns=["time_raw"], errors="ignore")

    # Summary
    print(f"  Output  {len(df):,} rows")
    print(f"  Dates   {df['week_ending'].min()} → {df['week_ending'].max()}")
    print(f"  Items   {df['item_desc'].nunique()} distinct SKU descriptions")
    print(f"  WHs     {df['warehouse_name'].nunique()} distinct warehouses")
    print(f"  MVM wks {int(df['is_mvm'].sum()):,} rows flagged as MVM")
    null_dollar = df["dollar_sales"].isna().sum()
    print(f"  Sparse  {null_dollar:,} rows with null dollar_sales ({100*null_dollar/len(df):.1f}%)")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    size_mb = out.stat().st_size / 1e6
    print(f"  Written → {out}  ({size_mb:.1f} MB)")
    print()
    print("Next step: upload to MinIO, then run Druid ingestion spec.")
    print("See docs/CRX_Druid_Ingestion_Guide.md")


if __name__ == "__main__":
    main()
