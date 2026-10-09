#!/usr/bin/env python
"""Build load-ready files for Druid from BUILT-provided sources (Rob loads them).
# protocol: not-a-forecast-arm

Outputs (data/druid_loads/, CSV, snake_case, ISO dates, UTC):
  trade_promotions.csv           Brian's Sept 30 "FULL HISTORY" file, Details tab (one row per promotion x product group)
  trade_promotions_overview.csv  same file, Overview tab (one row per promotion: revenue, spend, ROI)
  item_attributes.csv            one row per 11-digit UPC key: Connor's Item_Assumptions + NetSuite ItemDim + SPINS
  item_master_rows.csv           every source row before de-duplication (audit trail)
  customer_bridge.csv            Ebad's SalesRepCustomerMap (retailer <-> BUILT customer <-> NetSuite ID <-> SPINS customer)
  sales_reps.csv                 Ebad's SalesRepDim WITHOUT email addresses
  forecast_versions.csv.gz       saved forecasts in forecasts_registered/, long format, append-only by version_id

UPC key (scripts/README 2026-10-09 check): SPINS '08-40229-30119' -> last 11 digits; a 12-digit retail
UPC '840229301195' -> first 11 digits (drop the check digit). Placeholders (TBD-n) get no key.
Run from the repo root:  python3 scripts/build_druid_loads.py
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DOCS, OUT = ROOT / "docs", ROOT / "data" / "druid_loads"
PROMO = DOCS / "Promotions,_Sep_30,_2026  FULL HISTORY For Aevah.xlsx"
CONNOR = DOCS / "Connor's Model Extracts for Aevah 89 2026.xlsx"
ITEMDIM = DOCS / "ItemDim.xlsx"
SALESREP = DOCS / "SalesRepTables.xlsx"
PANEL = ROOT / "scripts" / "outputs" / "retailer_sales_weekly.parquet"
REG = ROOT / "forecasts_registered"
BUILT_ON = date.today().isoformat()


def snake(c: str) -> str:
    c = re.sub(r"[%]", "pct", str(c))
    c = re.sub(r"[$]", "usd", c)
    return re.sub(r"[^0-9a-z]+", "_", c.lower()).strip("_")


def digits(s) -> str:
    return re.sub(r"\D", "", str(s).split(".")[0]) if pd.notna(s) else ""


def key_full(s) -> str:            # 12-digit retail UPC (with check digit) -> first 11 digits
    d = digits(s)
    return d[-12:][:11] if len(d) >= 12 else ""


def key_spins(s) -> str:           # SPINS '0' + 11 digits -> last 11 digits
    d = digits(s)
    return d[-11:] if len(d) >= 11 else ""


def promotions() -> None:
    for sheet, name, start in (("Details", "trade_promotions", "promotion_start_date"),
                               ("Overview", "trade_promotions_overview", "run_dates_start")):
        d = pd.read_excel(PROMO, sheet_name=sheet)
        d.columns = [snake(c) for c in d.columns]
        for c in [c for c in d.columns if "date" in c]:
            d[c] = pd.to_datetime(d[c], errors="coerce").dt.strftime("%Y-%m-%d")
        d.insert(0, "__time", pd.to_datetime(d[start], errors="coerce").dt.strftime("%Y-%m-%dT00:00:00Z"))
        d["source_file"], d["as_of_date"] = PROMO.name, "2026-09-30"
        d = d[d["__time"].notna()]
        d.to_csv(OUT / f"{name}.csv", index=False)
        print(f"  {name}: {len(d):,} rows, {d['__time'].min()[:10]} .. {d['__time'].max()[:10]}")


def items() -> None:
    ia = pd.read_excel(CONNOR, sheet_name="Item_Assumptions", header=3).dropna(how="all", axis=1)
    ia = ia[ia["Built Item No."].notna()].copy()
    ia.columns = [snake(c) for c in ia.columns]
    ia = ia.rename(columns={"bars_per_unit": "bars_per_unit"})
    notes = ia["notes"].fillna("").astype(str).str.strip()
    desc = ia["built_item_description"].fillna("").astype(str)
    ia["key11"] = [key_spins(s) or key_full(b) for s, b in zip(ia["spins_upc"], ia["built_upc"])]
    ia["match_method"] = ["connor_spins_upc" if key_spins(s) else ("connor_built_upc" if key_full(b) else "none")
                          for s, b in zip(ia["spins_upc"], ia["built_upc"])]
    ia["exclusive_to"] = notes.str.extract(r"^(.*) Exclusive$")[0]
    ia["is_shipper_or_display"] = (notes.str.contains("Shipper|Display", case=False)
                                   | desc.str.contains(r"Shipper|Display|PDQ|Power Wing|Countertop", case=False))
    ia["is_inner_caddy"] = notes.str.contains("Inner Caddy", case=False) | desc.str.contains("Inner Caddy", case=False)
    ia["is_discontinued"] = notes.str.contains("Discontinued", case=False) | desc.str.contains("Do not sell", case=False)
    ia["is_2027_innovation"] = notes.str.contains("2027 Retail Innovation", case=False)
    ia["is_tbd"] = ia["built_item_no"].astype(str).str.startswith("TBD") | ia["built_upc"].astype(str).str.startswith("TBD")
    ia["source"] = "connor_item_assumptions_2026-07-22"
    nd = pd.read_excel(ITEMDIM, dtype={"UPC": str})
    nd.columns = ["netsuite_" + snake(c) for c in nd.columns]
    nd["key11"] = nd["netsuite_upc"].map(key_full)
    nd = nd[nd["key11"] != ""].drop_duplicates("key11")
    sp = pd.read_parquet(PANEL, columns=["upc", "description"]).drop_duplicates("upc")
    sp["key11"] = sp["upc"].map(key_spins)
    sp = sp.rename(columns={"upc": "spins_upc_panel", "description": "spins_description_panel"}).drop_duplicates("key11")
    rows = ia.merge(nd, on="key11", how="left").merge(sp, on="key11", how="left")
    rows.to_csv(OUT / "item_master_rows.csv", index=False)
    # one row per key: prefer the consumer unit (Built UPC == SPINS UPC), then any row with a key
    keyed = rows[rows["key11"] != ""].copy()
    keyed["_pref"] = (keyed["built_upc"].map(key_full) == keyed["key11"]).astype(int)
    one = keyed.sort_values("_pref", ascending=False).drop_duplicates("key11").drop(columns="_pref")
    extra_nd = nd[~nd["key11"].isin(one["key11"])].assign(match_method="netsuite_upc", source="netsuite_itemdim")
    extra_sp = sp[~sp["key11"].isin(set(one["key11"]) | set(extra_nd["key11"]))].assign(match_method="spins_only",
                                                                                      source="spins_panel")
    att = pd.concat([one, extra_nd, extra_sp], ignore_index=True)
    sd = att["spins_description_panel"].fillna("").astype(str)
    att["pack_count_from_spins"] = sd.str.extract(r"\((\d+)\s*(?:pk|ct|count)", flags=re.I)[0]
    att["line_from_spins"] = sd.str.extract(r"(Sour Puff|Chunk|Duos|Puff|Bar)", flags=re.I)[0].str.title()
    att["built_on"] = BUILT_ON
    att.to_csv(OUT / "item_attributes.csv", index=False)
    print(f"  item_attributes: {len(att):,} keys ({att['match_method'].value_counts().to_dict()}); "
          f"item_master_rows: {len(rows):,}")


def customers() -> None:
    m = pd.read_excel(SALESREP, sheet_name="SalesRepCustomerMap")
    m.columns = [snake(c) for c in m.columns]
    m["source_file"] = SALESREP.name
    m.to_csv(OUT / "customer_bridge.csv", index=False)
    r = pd.read_excel(SALESREP, sheet_name="SalesRepDim")
    r = r.drop(columns=[c for c in r.columns if c.lower() == "email"])      # no personal emails in Druid
    r.columns = [snake(c) for c in r.columns]
    r.to_csv(OUT / "sales_reps.csv", index=False)
    print(f"  customer_bridge: {len(m)} rows; sales_reps: {len(r)} rows (email dropped)")


def forecasts() -> None:
    parts = []
    for f in sorted(REG.glob("????-??-??.parquet")):
        cutoff = f.stem
        reg = pd.read_parquet(f)
        dims = ["series", "upc", "channel_outlet", "retail_account", "geography_raw", "date", "h", "lapsed"]
        models = [c for c in ("served_v11d", "recursive", "flat", "conn_L4W", "mo130", "blend") if c in reg.columns]
        for add in sorted(REG.glob(f"{cutoff}.add-*.parquet")):
            a = pd.read_parquet(add)
            reg = reg.merge(a, on=["series", "date"], how="left")
            models += [c for c in a.columns if c not in ("series", "date")]
        long = reg.melt(id_vars=dims, value_vars=models, var_name="model", value_name="forecast_units")
        long["cutoff"], long["version_id"] = cutoff, f"{cutoff}_saved"
        parts.append(long)
    fv = pd.concat(parts, ignore_index=True)
    fv["model"] = fv["model"].replace({"conn_L4W": "l4w_velocity_x_stores", "flat": "last_week_carried_forward",
                                       "served_v11d": "served_direct_v11d", "rec_dirfix": "recursive_plus_direct_fixed"})
    fv.insert(0, "__time", pd.to_datetime(fv["date"], utc=True).dt.strftime("%Y-%m-%dT00:00:00Z"))
    fv = fv.drop(columns=["date"])
    fv.to_csv(OUT / "forecast_versions.csv.gz", index=False, compression="gzip")
    print(f"  forecast_versions: {len(fv):,} rows; models {sorted(fv['model'].unique())}")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    promotions(); items(); customers(); forecasts()
