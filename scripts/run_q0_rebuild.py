#!/usr/bin/env python
"""Run the Q0 rebuild of built_filtered_weekly (MULO label fix, 2026-10-12) batch by batch.

Reads the Q0 SQL straight from docs/mo_druid_query_register.md (the reviewed text, not a copy), substitutes each
batch's bounds into BOTH the OVERWRITE WHERE and the WHERE __time clauses, submits it through the Druid SQL
statements API and waits for SUCCESS before the next batch. Refuses to run unless the backup table exists.
Usage (repo root): python3 scripts/run_q0_rebuild.py --batches R1,R2,R3,R4 [--max-num-tasks 4] [--dry-run]
Write mode: REPLACE ... OVERWRITE WHERE (the SQL-ingestion equivalent of appendToExisting=false, limited to the
batch window). Never INSERT INTO here: INSERT appends and would duplicate every row in the window.
Then: python3 scripts/verify_built_filtered_weekly.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mo_druid_client import poll_msq, query_druid, submit_msq  # noqa: E402

REGISTER = Path(__file__).resolve().parent.parent / "docs" / "mo_druid_query_register.md"
BACKUP = "built_filtered_weekly_bak_20261012"
BATCHES = {"R1": ("2023-01-01", "2024-01-01"), "R2": ("2024-01-01", "2025-01-01"),
           "R3": ("2025-01-01", "2026-01-01"), "R4": ("2026-01-01", "2027-01-01")}
TEMPLATE_BOUNDS = ("2023-01-01", "2024-01-01")   # the bounds written in the register's Q0 SQL


def q0_sql() -> str:
    s = REGISTER.read_text()
    blk = s[s.index("## Q0 Category extract normalization"):s.index('<a id="q1"></a>')]
    sql = blk.split("```sql")[2].split("```")[0]
    assert 'REPLACE INTO "built_filtered_weekly"' in sql and sql.count("MULO FIX") == 3, "unexpected Q0 text"
    lines = [ln for ln in sql.splitlines() if not ln.lstrip().startswith("--")]
    return "\n".join(ln.split("--")[0].rstrip() if "-- MULO FIX" in ln or "--   copy" in ln else ln for ln in lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", default="R1,R2,R3,R4")
    ap.add_argument("--max-num-tasks", type=int, default=4,
                    help="MSQ maxNumTasks (controller + workers); default 2 if unset. Q0 is a scan, so more helps")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    base = q0_sql()
    assert base.count(f"TIMESTAMP '{TEMPLATE_BOUNDS[0]}'") == 2 and base.count(f"TIMESTAMP '{TEMPLATE_BOUNDS[1]}'") == 2
    tables = set(query_druid("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='druid'",
                             timeout=60)["TABLE_NAME"])
    if BACKUP not in tables and not a.dry_run:
        sys.exit(f"refusing to run: backup table {BACKUP} not found")
    assert base.lstrip().startswith("REPLACE INTO") and "INSERT INTO" not in base, "Q0 must REPLACE, not INSERT"
    for name in a.batches.split(","):
        t0, t1 = BATCHES[name]
        sql = (base.replace(f"TIMESTAMP '{TEMPLATE_BOUNDS[0]}'", f"TIMESTAMP '{t0}'")
                   .replace(f"TIMESTAMP '{TEMPLATE_BOUNDS[1]}'", f"TIMESTAMP '{t1}'"))
        assert sql.count(f"TIMESTAMP '{t0}'") == 2 and sql.count(f"TIMESTAMP '{t1}'") == 2
        if a.dry_run:
            print(f"--- {name} {t0}..{t1} ---\n{sql}\n")
            continue
        qid = submit_msq(sql, context={"maxNumTasks": a.max_num_tasks})
        print(f"{name} {t0}..{t1}: submitted {qid} (maxNumTasks={a.max_num_tasks})", flush=True)
        poll_msq(qid, interval=30, timeout=7200)
        n = query_druid(f"""SELECT COUNT(*) n FROM "built_filtered_weekly"
                            WHERE __time >= TIMESTAMP '{t0}' AND __time < TIMESTAMP '{t1}'""", timeout=300)
        print(f"{name}: SUCCESS, {int(n.n[0]):,} rows in window", flush=True)


if __name__ == "__main__":
    main()
