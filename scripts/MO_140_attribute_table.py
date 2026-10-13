#!/usr/bin/env python
"""MO_140 step 1 - build a fixed product-attribute table (one row per 11-digit UPC key) for the attributes test.

PLAIN WORDS: collects facts about each BUILT product that do not change week to week, so MO_140 can test whether
giving them to the forecast model helps (especially for new items, which could borrow from similar products):
  majority_type    Connor's product line (Puff / Sour Puff / Chunk Puff / Duos Puff / Bar), item_attributes.csv
  price_per_bar    Connor's retail sale price per bar (item_attributes.csv; whether it is list price is unverified)
  exclusive        1 if Connor lists the item as exclusive to a retailer, else 0
  protein_g, sugar_g, calories   SPINS nutrition label (spins_full), the most common non-blank value per UPC
NOT included: discontinued / 2027-innovation flags (today's status applied to past dates would leak the future),
bars per unit (same as pack_count, already an input; SETTLED: MO_96 do not re-add).
Key: SPINS UPC '08-40229-30119' -> last 11 digits; Connor's sheet already carries key11 (build_druid_loads.py rule).
Output: outputs/mo140_item_attributes.parquet
"""
from __future__ import annotations

# protocol: not-a-forecast-arm (static attribute table; the MO_140 experiment script carries predictions and bands)
import re
from pathlib import Path

import pandas as pd

from mo_druid_client import query_druid

OUT = Path("outputs/mo140_item_attributes.parquet")
IA = Path("../data/druid_loads/item_attributes.csv")


def key11(u) -> str:
    return re.sub(r"\D", "", str(u))[-11:]


def num(s: str | None) -> float:
    m = re.search(r"[-+]?\d*\.?\d+", str(s or ""))
    return float(m.group()) if m else float("nan")


def main() -> None:
    ia = pd.read_csv(IA, dtype=str)
    a = pd.DataFrame({"key11": ia["key11"],
                      "majority_type": ia["majority_type"].fillna("UNKNOWN").str.strip(),
                      "price_per_bar": pd.to_numeric(ia["retail_sale_price_per_bar"], errors="coerce"),
                      "exclusive": ia["exclusive_to"].notna().astype(int)})
    assert not a["key11"].duplicated().any(), "item_attributes key11 must be unique"
    n = query_druid("""SELECT "UPC" upc, "NFP - PROTEIN" pr, "NFP - SUGARS" su, "NFP - CALORIES" ca, COUNT(*) n
                       FROM "spins_full" WHERE "Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF')
                       GROUP BY 1, 2, 3, 4""", timeout=300)
    n["key11"] = n["upc"].map(key11)
    out = []
    for k, g in n.groupby("key11"):
        row = {"key11": k}
        for col, name in (("pr", "protein_g"), ("su", "sugar_g"), ("ca", "calories")):
            v = g.assign(x=g[col].map(num)).dropna(subset=["x"])
            row[name] = float(v.groupby("x")["n"].sum().idxmax()) if len(v) else float("nan")
        out.append(row)
    nut = pd.DataFrame(out)
    t = nut.merge(a, on="key11", how="outer")
    t["majority_type"] = t["majority_type"].fillna("UNKNOWN")
    t["exclusive"] = t["exclusive"].fillna(0).astype(int)
    t.to_parquet(OUT)
    print(f"wrote {OUT}: {len(t)} keys; majority_type {t['majority_type'].value_counts().to_dict()}; "
          f"protein known {t['protein_g'].notna().sum()}, sugar {t['sugar_g'].notna().sum()}, "
          f"calories {t['calories'].notna().sum()}, price {t['price_per_bar'].notna().sum()}, exclusive {int(t['exclusive'].sum())}")
    print(t.describe().round(2).to_string())


if __name__ == "__main__":
    main()
