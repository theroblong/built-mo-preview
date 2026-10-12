#!/usr/bin/env python
"""Back up and rebuild built_filtered_weekly with the Q0 MULO label fix (2026-10-12), batch by batch.

Commands (run from the repo root):
  python3 scripts/run_q0_rebuild.py backup  [--wait-task ID]      copy built_filtered_weekly -> backup table
  python3 scripts/run_q0_rebuild.py rebuild [--batches R1,R2,R3,R4] [--max-num-tasks 4] [--dry-run]
  then: python3 scripts/verify_built_filtered_weekly.py

Rules this script enforces (docs/SPINS_INGEST_RUNBOOK.md, README 141-142, docs/mo_druid_query_register.md Q0):
  * The Q0 SQL is read straight from the register (the reviewed text, not a copy). Each batch's bounds are
    substituted into BOTH the OVERWRITE WHERE and the WHERE __time clauses, and both are asserted.
  * Write mode is REPLACE ... OVERWRITE WHERE: the SQL-ingestion equivalent of appendToExisting=false, limited to
    the batch window. INSERT INTO (append) is refused; it would duplicate every row in the window.
  * Tasks are polled through the Druid Tasks API (poll_task_api), never the statements API, which expires after a
    few minutes on long tasks (the 2026-09-23 incident where a 404 was read as success).
  * Every batch is gated on data, not only task status: after each batch the window's row count must equal the
    expected count (backup: the source window; rebuild: the same filter counted on spins_full). Any failure stops
    the run before the next batch.
  * rebuild refuses to run unless the backup table exists and matches the source row count.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mo_druid_client import poll_task_api, query_druid, submit_msq  # noqa: E402

REGISTER = Path(__file__).resolve().parent.parent / "docs" / "mo_druid_query_register.md"
TARGET = "built_filtered_weekly"
BACKUP = "built_filtered_weekly_bak_20261012"
BATCHES = {"R1": ("2023-01-01", "2024-01-01"), "R2": ("2024-01-01", "2025-01-01"),
           "R3": ("2025-01-01", "2026-01-01"), "R4": ("2026-01-01", "2027-01-01")}
TEMPLATE_BOUNDS = ("2023-01-01", "2024-01-01")   # the bounds written in the register's Q0 SQL
TASK_TIMEOUT = 4 * 3600


def count(table: str, t0: str, t1: str, extra: str = "") -> int:
    df = query_druid(f'SELECT COUNT(*) n FROM "{table}" WHERE __time >= TIMESTAMP \'{t0}\' '
                     f"AND __time < TIMESTAMP '{t1}' {extra}", timeout=600, retries=2)
    return int(df.n[0])


def settled_count(table: str, t0: str, t1: str, want: int, tries: int = 20, wait: int = 30) -> int:
    """Count a window, re-checking while freshly published segments load (a lagging count is not a mismatch)."""
    got = count(table, t0, t1)
    for _ in range(tries):
        if got == want:
            return got
        time.sleep(wait)
        got = count(table, t0, t1)
    return got


def tables() -> set[str]:
    return set(query_druid("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='druid'",
                           timeout=60)["TABLE_NAME"])


def run_task(sql: str, label: str, max_num_tasks: int) -> None:
    assert sql.lstrip().startswith("REPLACE INTO") and "INSERT INTO" not in sql, "only REPLACE is allowed"
    qid = submit_msq(sql, context={"maxNumTasks": max_num_tasks})
    print(f"{label}: submitted {qid} (maxNumTasks={max_num_tasks})", flush=True)
    if not poll_task_api(qid, label=label, interval=60, timeout=TASK_TIMEOUT):
        sys.exit(f"STOP: {label} task {qid} did not succeed")


def q0_sql() -> str:
    s = REGISTER.read_text()
    blk = s[s.index("## Q0 Category extract normalization"):s.index('<a id="q1"></a>')]
    blocks = [b.split("```")[0] for b in blk.split("```sql")[1:]]
    main = [b for b in blocks if f'REPLACE INTO "{TARGET}"' in b and "MULO FIX" in b]
    assert len(main) == 1, f"expected exactly one Q0 SQL block with the MULO fix, found {len(main)}"
    sql = main[0]
    assert sql.count("MULO FIX") == 3, "Q0 must carry all three MULO FIX lines"
    lines = [ln for ln in sql.splitlines() if not ln.lstrip().startswith("--")]
    return "\n".join(ln.split("--")[0].rstrip() if "--" in ln else ln for ln in lines)


def expected_rebuild_count(t0: str, t1: str) -> int:
    """Rows Q0 should write for the window: the same brand/subcategory filter and MULO rule, counted on spins_full."""
    return count("spins_full", t0, t1, extra="""AND ("Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF')
                      OR "Subcategory" = 'WELLNESS & NUTRITION BARS')
                 AND NOT ("Geography" LIKE '%MULO + CONV%' AND __time >= TIMESTAMP '2025-08-17')""")


def backup(a) -> None:
    if a.wait_task:
        print(f"waiting for already-submitted task {a.wait_task}", flush=True)
        if not poll_task_api(a.wait_task, label="pending backup batch", interval=60, timeout=TASK_TIMEOUT):
            sys.exit(f"STOP: task {a.wait_task} did not succeed")
    have = tables()
    for name, (t0, t1) in BATCHES.items():
        src = count(TARGET, t0, t1)
        if BACKUP in have and settled_count(BACKUP, t0, t1, src) == src:
            print(f"backup {name} {t0}..{t1}: already complete ({src:,} rows)", flush=True)
            continue
        run_task(f'''REPLACE INTO "{BACKUP}"
OVERWRITE WHERE __time >= TIMESTAMP '{t0}' AND __time < TIMESTAMP '{t1}'
SELECT * FROM "{TARGET}"
WHERE __time >= TIMESTAMP '{t0}' AND __time < TIMESTAMP '{t1}'
PARTITIONED BY DAY
CLUSTERED BY upc, channel_outlet, retail_account, geography_raw''', f"backup {name}", a.max_num_tasks)
        have = tables()
        got = settled_count(BACKUP, t0, t1, src)
        if got != src:
            sys.exit(f"STOP: backup {name} has {got:,} rows, source has {src:,}")
        print(f"backup {name} {t0}..{t1}: verified {got:,} rows", flush=True)
    s = query_druid(f'SELECT COUNT(*) n, SUM(units) u FROM "{TARGET}"', timeout=600)
    b = query_druid(f'SELECT COUNT(*) n, SUM(units) u FROM "{BACKUP}"', timeout=600)
    ok = int(s.n[0]) == int(b.n[0]) and abs(float(s.u[0]) - float(b.u[0])) < 1
    print(f"BACKUP {'MATCHES' if ok else 'MISMATCH'}: source {int(s.n[0]):,} rows / {float(s.u[0]):,.0f} units; "
          f"backup {int(b.n[0]):,} rows / {float(b.u[0]):,.0f} units", flush=True)
    if not ok:
        sys.exit(1)


def rebuild(a) -> None:
    base = q0_sql()
    assert base.count(f"TIMESTAMP '{TEMPLATE_BOUNDS[0]}'") == 2 and base.count(f"TIMESTAMP '{TEMPLATE_BOUNDS[1]}'") == 2
    if not a.dry_run and not a.execute:
        sys.exit("refusing to write without --execute (the full chain runner is scripts/druid_pipeline.py)")
    if not a.dry_run:
        if BACKUP not in tables():
            sys.exit(f"refusing to run: backup table {BACKUP} not found (run the backup command first)")
        nb = int(query_druid(f'SELECT COUNT(*) n FROM "{BACKUP}"', timeout=600).n[0])
        nt = int(query_druid(f'SELECT COUNT(*) n FROM "{TARGET}"', timeout=600).n[0])
        if nb != nt and not a.resume:
            sys.exit(f"refusing to run: backup has {nb:,} rows, {TARGET} has {nt:,} (pass --resume only if an "
                     "earlier rebuild batch already ran)")
    for name in a.batches.split(","):
        t0, t1 = BATCHES[name]
        sql = (base.replace(f"TIMESTAMP '{TEMPLATE_BOUNDS[0]}'", f"TIMESTAMP '{t0}'")
                   .replace(f"TIMESTAMP '{TEMPLATE_BOUNDS[1]}'", f"TIMESTAMP '{t1}'"))
        assert sql.count(f"TIMESTAMP '{t0}'") == 2 and sql.count(f"TIMESTAMP '{t1}'") == 2
        if a.dry_run:
            print(f"--- {name} {t0}..{t1} ---\n{sql}\n")
            continue
        want = expected_rebuild_count(t0, t1)
        print(f"rebuild {name} {t0}..{t1}: expect {want:,} rows", flush=True)
        run_task(sql, f"rebuild {name}", a.max_num_tasks)
        got = count(TARGET, t0, t1)
        if got != want:
            sys.exit(f"STOP: rebuild {name} wrote {got:,} rows, expected {want:,}")
        print(f"rebuild {name}: verified {got:,} rows", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["backup", "rebuild"])
    ap.add_argument("--batches", default="R1,R2,R3,R4")
    ap.add_argument("--max-num-tasks", type=int, default=4,
                    help="MSQ maxNumTasks (controller + workers; Druid default 2). Q0 is a scan, so more helps")
    ap.add_argument("--wait-task", default="", help="backup: an already-submitted backup task to wait for first")
    ap.add_argument("--resume", action="store_true", help="rebuild: allow continuing after earlier batches ran")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true", help="rebuild: required to write")
    a = ap.parse_args()
    backup(a) if a.cmd == "backup" else rebuild(a)


if __name__ == "__main__":
    main()
