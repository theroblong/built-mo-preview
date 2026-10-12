#!/usr/bin/env python
"""Run the Druid Q-series (Q0 -> Q22) from the query register, one checked step at a time.

Plan and rules: docs/DRUID_REBUILD_PLAN_2026-10.md. SQL source: docs/mo_druid_query_register.md (read at run time;
this file holds no SQL of its own except read-only checks).

    python3 scripts/druid_pipeline.py plan                       # read-only: preflight + EXPLAIN every step
    python3 scripts/druid_pipeline.py run --execute [--from STEP] [--only STEP,...]
    python3 scripts/druid_pipeline.py status                     # what is done, from the state file

Nothing is written to Druid without --execute. Lessons built in (error register E03-E26, README 141-145):
  * REPLACE only. OVERWRITE WHERE for batched steps (Q0, Q2), OVERWRITE ALL for the rest. The single INSERT is
    Q22b, allowed only right after Q22a succeeds in the same run (E26). Any other INSERT stops the run.
  * maxNumTasks = 4 for every step (8 task slots on the cluster; 8 was no faster than 4 for Q2). Other settings come
    from the register's SET lines and are passed as query context.
  * Tasks API polling only; a 404 is "not visible yet", never success (2026-09-23 incident).
  * A data check after every step, retried while new segments load, so a lagging count is not read as failure
    (README 142). A row-count change outside -50%/+50% of the pre-run baseline pauses the run for review.
  * Day-aligned batch bounds substituted into every __time clause of the step, each asserted (E17, E20).
  * Preflight (read-only): no other Druid tasks running, enough free slots, new-UPC and duplicate-UPC gates (QS1),
    backup present and equal to the source before Q0, fresh baseline counts.
  * State file records each finished-and-checked step; a rerun resumes at the first unfinished step.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mo_druid_client import _AUTH, _HEADERS, DRUID_HOST, poll_task_api, query_druid, submit_msq  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "docs" / "mo_druid_query_register.md"
OUT = ROOT / "scripts" / "outputs"
STATE = OUT / "druid_pipeline_state.json"
BASELINE = OUT / "druid_pipeline_baseline.json"
DRYRUN_DIR = OUT / "druid_pipeline_dryrun"
BACKUP = "built_filtered_weekly_bak_20261012"
MAX_NUM_TASKS = 4
PROBE = "zz_explain_probe_do_not_use"   # EXPLAIN target name; EXPLAIN never writes, this is belt and braces
YEARS = [("2023-01-01", "2024-01-01"), ("2024-01-01", "2025-01-01"), ("2025-01-01", "2026-01-01"),
         ("2026-01-01", "2027-01-01")]

# key, register heading, target, statement kind, template bounds (batched only), timeout hours, checks
STEPS: list[dict] = []
for i, (t0, t1) in enumerate(YEARS, 1):
    STEPS.append(dict(key=f"Q0:R{i}", head="Q0", target="built_filtered_weekly", kind="REPLACE",
                      template=("2023-01-01", "2024-01-01"), bounds=(t0, t1), n_bound=2, hours=2, check="q0"))
STEPS.append(dict(key="Q1", head="Q1", target="built_enriched_weekly", kind="REPLACE", hours=6, check="equals_bfw"))
for t0, t1 in YEARS:
    STEPS.append(dict(key=f"Q2:{t0[:4]}", head="Q2", target="comparison_pool_weekly", kind="REPLACE",
                      template=("2025-01-01", "2027-01-01"), bounds=(t0, t1), n_bound=3, hours=20, check="window"))
for k, tgt, h in (("Q3", "built_prepost_features", 2), ("Q4", "donor_prepost_features", 4),
                  ("Q5", "ml_training_features", 2), ("Q6", "event_detection_weekly", 2),
                  ("Q7", "new_upc_candidates", 2), ("Q8", "new_upc_classifications", 2),
                  ("Q9", "new_product_ramp_monitor", 2), ("Q14", "price_elasticity_weekly_features", 2),
                  ("Q15", "price_pack_ladder_weekly", 2), ("Q16", "price_competitive_weekly", 8),
                  ("Q17", "price_elasticity_training_features", 2), ("Q20", "mulo_food_pack_size_norms", 2),
                  ("Q21", "flavor_protein_driver_features", 3)):
    STEPS.append(dict(key=k, head=k, target=tgt, kind="REPLACE", hours=h, check="table"))
STEPS.append(dict(key="Q22a", head="Q22", target="price_event_queue", kind="REPLACE", hours=1, check="table"))
STEPS.append(dict(key="Q22b", head="Q22", target="price_event_queue", kind="INSERT", hours=1, check="grew"))
KEYS = [s["key"] for s in STEPS]


# ---------------------------------------------------------------- register parsing
def section(head: str) -> str:
    s = REGISTER.read_text()
    m = re.search(rf"^## {re.escape(head)} ", s, re.M)
    assert m, f"register has no section '## {head} '"
    nxt = re.search(r"^## ", s[m.end():], re.M)
    return s[m.start(): m.end() + (nxt.start() if nxt else len(s))]


def statement(step: dict) -> tuple[str, dict]:
    """The step's SQL (SET lines removed) and its query context."""
    blocks = [b.split("```")[0] for b in section(step["head"]).split("```sql")[1:]]
    head = f'{"REPLACE INTO" if step["kind"] == "REPLACE" else "INSERT INTO"} "{step["target"]}"'
    hits = [b for b in blocks if head in b]
    assert len(hits) == 1, f"{step['key']}: expected one block with {head}, found {len(hits)}"
    sql = hits[0]
    other = "INSERT INTO" if step["kind"] == "REPLACE" else "REPLACE INTO"
    assert other not in sql, f"{step['key']}: block mixes REPLACE and INSERT"
    if step["kind"] == "INSERT":
        assert step["key"] == "Q22b", "INSERT is allowed only for Q22b"
    ctx: dict = {}
    keep = []
    for ln in sql.splitlines():
        m = re.match(r"\s*SET\s+(\w+)\s*=\s*([^;]+);", ln)
        if m:
            k, v = m.group(1), m.group(2).strip().strip("'\"")
            ctx[k] = True if v.lower() == "true" else False if v.lower() == "false" else int(v) if v.isdigit() else v
        else:
            keep.append(ln)
    ctx["maxNumTasks"] = MAX_NUM_TASKS
    sql = "\n".join(keep).strip()
    if step["kind"] == "REPLACE":
        mode = "WHERE" if "template" in step else "ALL"
        assert f"OVERWRITE {mode}" in sql, f"{step['key']}: expected OVERWRITE {mode}"
    if "template" in step:
        (a0, a1), (b0, b1), n = step["template"], step["bounds"], step["n_bound"]
        for t in (a0, a1):
            assert sql.count(f"TIMESTAMP '{t}'") == n, f"{step['key']}: template bound {t} appears {sql.count(f'TIMESTAMP {t!r}')}x, expected {n}"
        sql = sql.replace(f"TIMESTAMP '{a0}'", "TIMESTAMP '@@T0@@'").replace(f"TIMESTAMP '{a1}'", "TIMESTAMP '@@T1@@'")
        sql = sql.replace("@@T0@@", b0).replace("@@T1@@", b1)
        for t in (b0, b1):
            assert sql.count(f"TIMESTAMP '{t}'") >= n, f"{step['key']}: bound {t} not substituted {n}x"
    if step["head"] == "Q0":
        assert sql.count("MULO FIX") == 3, "Q0 must carry all three MULO FIX lines"
    return sql, ctx


# ---------------------------------------------------------------- Druid helpers
def running_tasks() -> list:
    return requests.get(f"{DRUID_HOST}/druid/indexer/v1/runningTasks", auth=_AUTH, timeout=30).json() + \
        requests.get(f"{DRUID_HOST}/druid/indexer/v1/pendingTasks", auth=_AUTH, timeout=30).json()


def free_slots() -> int:
    ws = requests.get(f"{DRUID_HOST}/druid/indexer/v1/workers", auth=_AUTH, timeout=30).json()
    return sum(w["worker"]["capacity"] - w["currCapacityUsed"] for w in ws)


def tables() -> set[str]:
    return set(query_druid("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='druid'",
                           timeout=60)["TABLE_NAME"])


def rows(table: str, t0: str | None = None, t1: str | None = None, where: str = "") -> int:
    w = f"WHERE __time >= TIMESTAMP '{t0}' AND __time < TIMESTAMP '{t1}' {where}" if t0 else (f"WHERE {where}" if where else "")
    return int(query_druid(f'SELECT COUNT(*) n FROM "{table}" {w}', timeout=900, retries=2).n[0])


def hwm(table: str) -> str:
    return str(query_druid(f'SELECT MAX(__time) t FROM "{table}"', timeout=300, retries=2).t[0])[:10]


def explain(sql: str, ctx: dict, target: str) -> str:
    probe = sql.replace(f'"{target}"', f'"{PROBE}"', 1)
    r = requests.post(f"{DRUID_HOST}/druid/v2/sql/task", json={"query": "EXPLAIN PLAN FOR " + probe, "context": ctx},
                      auth=_AUTH, headers=_HEADERS, timeout=300)
    if r.status_code == 200:
        return "OK"
    try:
        return "ERROR: " + r.json().get("error", {}).get("errorMessage", r.text)[:300]
    except ValueError:
        return f"ERROR {r.status_code}: {r.text[:300]}"


def expected_q0(t0: str, t1: str) -> int:
    return rows("spins_full", t0, t1, where="""AND ("Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF')
        OR "Subcategory" = 'WELLNESS & NUTRITION BARS')
        AND NOT ("Geography" LIKE '%MULO + CONV%' AND __time >= TIMESTAMP '2025-08-17')""")


# ---------------------------------------------------------------- state
def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {"done": {}}


def save_state(st: dict) -> None:
    STATE.write_text(json.dumps(st, indent=2))


# ---------------------------------------------------------------- checks
def check(step: dict, base: dict, st: dict) -> dict:
    """Data gate after a step. Retries for ~15 minutes while segments load, then fails."""
    last = None
    for attempt in range(30):
        try:
            res = _check_once(step, base, st)
            if res["ok"]:
                return res
            last = res
        except Exception as e:  # noqa: BLE001 -- a query error during segment handoff is retried
            last = {"ok": False, "detail": f"check query error: {e}"}
        print(f"    check not yet satisfied (attempt {attempt + 1}/30): {last['detail']}", flush=True)
        time.sleep(30)
    return last


def _check_once(step: dict, base: dict, st: dict) -> dict:
    t = step["target"]
    if step["check"] == "q0":
        t0, t1 = step["bounds"]
        want, got = expected_q0(t0, t1), rows(t, t0, t1)
        return {"ok": got == want, "rows": got, "detail": f"window rows {got:,}, expected {want:,}"}
    if step["check"] == "equals_bfw":
        a, b = rows(t), rows("built_filtered_weekly")
        ha, hb = hwm(t), hwm("built_filtered_weekly")
        return {"ok": a == b and ha == hb, "rows": a, "detail": f"rows {a:,} vs built_filtered_weekly {b:,}; latest week {ha} vs {hb}"}
    if step["check"] == "window":
        t0, t1 = step["bounds"]
        got = rows(t, t0, t1)
        was = base.get(f"{t}:{t0[:4]}")
        return _ratio({"rows": got, "detail": f"{t0[:4]} rows {got:,} (before {was:,})" if was is not None else f"{got:,}"}, got, was)
    if step["check"] == "grew":
        before = st["done"].get("Q22a", {}).get("rows")
        got = rows(t)
        return {"ok": before is not None and got > before, "rows": got, "detail": f"rows {got:,} after Q22a's {before}"}
    got = rows(t)
    res = {"rows": got, "detail": f"rows {got:,} (before {base.get(t, 0):,})"}
    if step["key"] == "Q17":
        mx = int(query_druid(f'SELECT MAX(post_13w_weeks_count) m FROM "{t}"', timeout=300).m[0])
        res["detail"] += f"; max post_13w_weeks_count {mx}"
        if mx > 13:
            return {**res, "ok": False}
    return _ratio(res, got, base.get(t))


def _ratio(res: dict, got: int, was: int | None) -> dict:
    if got <= 0:
        return {**res, "ok": False}
    if was:
        r = got / was
        res["ratio"] = round(r, 3)
        if not 0.5 <= r <= 1.5:
            return {**res, "ok": False, "pause": True, "detail": res["detail"] + f" -- change x{r:.2f} is outside 0.5-1.5: PAUSE for review"}
    return {**res, "ok": True}


# ---------------------------------------------------------------- preflight
def preflight(selected: list[dict], execute: bool) -> dict:
    print("PREFLIGHT (read-only)")
    others = [t for t in running_tasks()]
    print(f"  running/pending Druid tasks: {len(others)} {[t.get('dataSource') for t in others]}")
    slots = free_slots()
    print(f"  free task slots: {slots} (need {MAX_NUM_TASKS})")
    newupc = query_druid('''SELECT COUNT(*) n FROM (SELECT DISTINCT s."UPC" FROM "spins_full" s
        LEFT JOIN "flavor_mapping" fm ON s."UPC" = fm.upc
        WHERE s."Brand" IN ('BUILT', 'BUILT BAR', 'BUILT PUFF', 'BUILT SOUR PUFF') AND fm.upc IS NULL)''', timeout=600).n[0]
    dup = query_druid('SELECT COUNT(*) n FROM (SELECT upc FROM "flavor_mapping" GROUP BY upc HAVING COUNT(*) > 1)', timeout=60).n[0]
    print(f"  new BUILT UPCs missing from flavor_mapping: {newupc} (must be 0)")
    print(f"  duplicate UPCs in flavor_mapping: {dup} (must be 0)")
    problems = []
    if others:
        problems.append("other Druid tasks are running or pending (agree a quiet window with Rob)")
    if slots < MAX_NUM_TASKS:
        problems.append(f"only {slots} free task slots")
    if newupc or dup:
        problems.append("QS1 gate failed: update and re-run QS1 first (runbook Part 2)")
    if any(s["head"] == "Q0" for s in selected):
        have = tables()
        if BACKUP not in have:
            problems.append(f"backup {BACKUP} missing")
        else:
            nb, nt = rows(BACKUP), rows("built_filtered_weekly")
            print(f"  backup rows {nb:,} vs built_filtered_weekly {nt:,}")
            if nb != nt and not load_state()["done"]:
                problems.append("backup does not match built_filtered_weekly")
    base = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    if execute and not load_state()["done"]:
        base = {}
        for s in STEPS:
            if s["check"] in ("table", "equals_bfw") and s["target"] not in base:
                base[s["target"]] = rows(s["target"])
        for t0, t1 in YEARS:
            base[f"comparison_pool_weekly:{t0[:4]}"] = rows("comparison_pool_weekly", t0, t1)
        base["_taken"] = datetime.now(timezone.utc).isoformat()
        BASELINE.write_text(json.dumps(base, indent=2))
        print(f"  baseline counts written to {BASELINE}")
    for p in problems:
        print(f"  PROBLEM: {p}")
    return {"ok": not problems, "base": base}



# ---------------------------------------------------------------- commands
def cmd_plan(selected: list[dict]) -> None:
    pre = preflight(selected, execute=False)
    DRYRUN_DIR.mkdir(parents=True, exist_ok=True)
    print("\nSTEPS (EXPLAIN = parsed and planned by Druid's MSQ engine without running; nothing is written)")
    bad = 0
    for s in selected:
        sql, ctx = statement(s)
        (DRYRUN_DIR / f"{s['key'].replace(':', '_')}.sql").write_text(sql + "\n")
        ex = explain(sql, ctx, s["target"])
        bad += ex != "OK"
        mode = "INSERT (append)" if s["kind"] == "INSERT" else ("OVERWRITE WHERE " + "..".join(s["bounds"]) if "bounds" in s else "OVERWRITE ALL")
        print(f"  {s['key']:<8} -> {s['target']:<36} {mode:<38} timeout {s['hours']}h  check={s['check']}  "
              f"context={ {k: v for k, v in ctx.items()} }  EXPLAIN {ex}")
    print(f"\nfull SQL per step written to {DRYRUN_DIR}/")
    print(f"preflight {'OK' if pre['ok'] else 'HAS PROBLEMS (see above)'}; EXPLAIN failures: {bad}")


def cmd_run(selected: list[dict], a) -> None:
    if not a.execute:
        sys.exit("refusing to write without --execute (use the plan command to review first)")
    pre = preflight(selected, execute=True)
    if not pre["ok"]:
        sys.exit("STOP: preflight problems (see above); nothing was submitted")
    st = load_state()
    st.setdefault("started", datetime.now(timezone.utc).isoformat())
    for s in selected:
        if s["key"] in st["done"]:
            print(f"{s['key']}: already done and checked ({st['done'][s['key']]['detail']}); skipping")
            continue
        if s["key"] == "Q22b" and "Q22a" not in st["done"]:
            sys.exit("STOP: Q22b (INSERT) may only run after Q22a succeeded")
        busy = running_tasks()
        if busy:
            sys.exit(f"STOP before {s['key']}: other Druid tasks running {[t.get('dataSource') for t in busy]}")
        sql, ctx = statement(s)
        ex = explain(sql, ctx, s["target"])
        if ex != "OK":
            sys.exit(f"STOP before {s['key']}: EXPLAIN failed: {ex}")
        qid = submit_msq(sql, context=ctx)
        print(f"{s['key']}: submitted {qid} -> {s['target']} (context {ctx})", flush=True)
        st.setdefault("submitted", {})[s["key"]] = qid
        save_state(st)
        if not poll_task_api(qid, label=s["key"], interval=60, timeout=int(s["hours"] * 3600)):
            sys.exit(f"STOP: {s['key']} task {qid} did not succeed (see the Druid console task log). "
                     "Every step is a REPLACE, so rerunning this command retries it safely.")
        res = check(s, pre["base"], st)
        if not res["ok"]:
            sys.exit(f"STOP after {s['key']}: {res['detail']}. Review; to accept and continue, rerun with --accept {s['key']}"
                     if res.get("pause") else f"STOP after {s['key']}: data check failed: {res['detail']}")
        st["done"][s["key"]] = {"task": qid, "rows": res["rows"], "detail": res["detail"],
                                "at": datetime.now(timezone.utc).isoformat()}
        save_state(st)
        print(f"{s['key']}: DONE and checked: {res['detail']}", flush=True)
    print("all selected steps done. Next: python3 scripts/verify_built_filtered_weekly.py (if Q0 ran), then the Python steps.")


def cmd_accept(key: str) -> None:
    st = load_state()
    s = next(x for x in STEPS if x["key"] == key)
    st["done"][key] = {"rows": rows(s["target"]), "detail": "accepted after review (ratio outside 0.5-1.5)",
                       "at": datetime.now(timezone.utc).isoformat()}
    save_state(st)
    print(f"{key} marked done after review")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "run", "status", "accept"])
    ap.add_argument("--execute", action="store_true", help="required for run: actually write to Druid")
    ap.add_argument("--from", dest="start", default="", help="first step key, e.g. Q2:2025")
    ap.add_argument("--only", default="", help="comma-separated step keys")
    ap.add_argument("--accept", default="", help="with the accept command: the paused step to mark done")
    a = ap.parse_args()
    selected = STEPS
    if a.only:
        want = a.only.split(",")
        assert all(k in KEYS for k in want), f"unknown step; valid: {KEYS}"
        selected = [s for s in STEPS if s["key"] in want]
    elif a.start:
        assert a.start in KEYS, f"unknown step; valid: {KEYS}"
        selected = STEPS[KEYS.index(a.start):]
    if a.cmd == "plan":
        cmd_plan(selected)
    elif a.cmd == "run":
        cmd_run(selected, a)
    elif a.cmd == "accept":
        cmd_accept(a.accept)
    else:
        st = load_state()
        for k in KEYS:
            print(f"  {k:<8} {'DONE  ' + st['done'][k]['detail'] if k in st['done'] else '-'}")


if __name__ == "__main__":
    main()
