#!/usr/bin/env python
"""Verify built_filtered_weekly after a Q0 run (docs/mo_druid_query_register.md, Q0; MULO label fix 2026-10-12).

Week by week (Druid can't group the whole table at once on this cluster):
  1. duplicate keys (upc x channel_outlet x retail_account x geography_raw) -- must be 0
  2. rows still carrying an old MULO label ('MULO + CONV...') -- must be 0
  3. MULO TOTAL US units, printed around 2025-08-17 and 2026-04-19 (should run smoothly, no 2x / 0.5x step)
  4. if built_filtered_weekly_bak_20261012 exists: retailer-row units (retail_account not null) vs the backup.
     Expected: identical outside 2025-10-05..2026-04-12; inside it, small moves (current SPINS delivery).
Run from the repo root: python3 scripts/verify_built_filtered_weekly.py [--backup NAME]
Writes outputs/verify_built_filtered_weekly.csv and exits non-zero if check 1 or 2 fails.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mo_druid_client import query_druid as q  # noqa: E402

T = "built_filtered_weekly"
STALE = ("2025-10-05", "2026-04-12")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup", default="built_filtered_weekly_bak_20261012")
    a = ap.parse_args()
    tables = set(q("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='druid'", timeout=60)["TABLE_NAME"])
    has_bak = a.backup in tables
    print(f"backup {a.backup}: {'found' if has_bak else 'not found (skipping check 4)'}")
    weeks = [w[:10] for w in q(f'SELECT DISTINCT __time FROM "{T}" ORDER BY 1', timeout=120)["__time"]]
    rows = []
    for w in weeks:
        at = f"__time = TIMESTAMP '{w}'"
        dup = q(f"""SELECT COUNT(*) k FROM (SELECT upc, channel_outlet, retail_account, geography_raw FROM "{T}"
                    WHERE {at} GROUP BY 1,2,3,4 HAVING COUNT(*) > 1)""", timeout=300, retries=2)
        agg = q(f"""SELECT COUNT(*) n,
                      SUM(CASE WHEN geography_raw LIKE '%MULO + CONV%' OR channel_outlet LIKE '%MULO + CONV%' THEN 1 ELSE 0 END) old_lbl,
                      SUM(CASE WHEN geography_level = 'TOTAL US' AND channel_outlet LIKE '%MULO%' THEN units ELSE 0 END) mulo_us,
                      SUM(CASE WHEN retail_account IS NOT NULL AND retail_account <> '' THEN units ELSE 0 END) retailer_units
                    FROM "{T}" WHERE {at}""", timeout=300, retries=2)
        r = {"week": w, "rows": int(agg.n[0]), "dup_keys": int(dup.k[0]), "old_label_rows": int(agg.old_lbl[0]),
             "mulo_total_us_units": float(agg.mulo_us[0] or 0), "retailer_units": float(agg.retailer_units[0] or 0)}
        if has_bak:
            b = q(f"""SELECT SUM(CASE WHEN retail_account IS NOT NULL AND retail_account <> '' THEN units ELSE 0 END) u
                      FROM "{a.backup}" WHERE {at}""", timeout=300, retries=2)
            r["retailer_units_backup"] = float(b.u[0] or 0)
            r["retailer_pct_change"] = (r["retailer_units"] / r["retailer_units_backup"] - 1) * 100 if r["retailer_units_backup"] else None
        rows.append(r)
        print(r, flush=True)
    df = pd.DataFrame(rows)
    out = Path("scripts/outputs/verify_built_filtered_weekly.csv")
    df.to_csv(out, index=False)
    print(f"\nweeks {len(df)} | {df.week.min()}..{df.week.max()} | rows {df.rows.sum():,}")
    print(f"1. duplicate keys: {df.dup_keys.sum():,} (weeks with any: {(df.dup_keys > 0).sum()})")
    print(f"2. old MULO label rows: {df.old_label_rows.sum():,}")
    m = df.set_index("week")["mulo_total_us_units"]
    print("3. MULO TOTAL US units around the label switch and the April break:")
    print(m.loc["2025-07-27":"2025-09-07"].round(0).to_string())
    print(m.loc["2026-03-29":"2026-05-03"].round(0).to_string())
    if has_bak:
        out_win = df[(df.week < STALE[0]) | (df.week > STALE[1])]
        in_win = df[(df.week >= STALE[0]) & (df.week <= STALE[1])]
        print(f"4. retailer units vs backup: outside {STALE[0]}..{STALE[1]} max |change| "
              f"{out_win.retailer_pct_change.abs().max():.4f}%; inside, range "
              f"{in_win.retailer_pct_change.min():+.2f}% .. {in_win.retailer_pct_change.max():+.2f}%")
    print(f"wrote {out}")
    if df.dup_keys.sum() or df.old_label_rows.sum():
        sys.exit("FAILED: duplicates or old labels remain")
    print("PASSED checks 1 and 2")


if __name__ == "__main__":
    main()
