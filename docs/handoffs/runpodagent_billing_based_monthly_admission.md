# Change request for runpodagent: monthly admission based on actual RunPod charges

**For:** the coding agent responsible for `github.com/AevahLLC/runpodagent`
**From:** Jason Brazeal (Aevah), administrator decision of 2026-10-16
**Base commit:** `12fc757` ("Return all job cost estimates in one compute_budget call") on `main`
**Status:** implemented and tested on a local branch (`billing-based-monthly-admission`, local commit `463a7ac`). Jason has no write access to the repo, so the full diff is included at the end of this file.

## Problem

`TrainingService.run` in `src/aevah_compute/serverless.py` decides whether to admit a job by adding up the reservation of every Serverless job created this month:

```python
spent = sum(Decimal(r["reservation"]) for r in records if r["month"] == month)
if spent + reservation + p.monthly_storage_reserve_usd > p.monthly_target_usd:
    raise ComputeError("monthly_limit", "Monthly conservative reservations exhausted.")
```

- A job's reservation is its worst case: the full runtime plus the termination margin, charged at the endpoint's hourly ceiling of $1.10.
- Reservations are never released after a job finishes.
- A 4.5-hour job therefore reserves $4.99 for the rest of the month, even if RunPod bills it $1–2.

On 2026-10-16 the October reservations totalled $129.09, while RunPod's actual October charges were about $40. With the $150 target and $20 storage reserve, admission refused new $4.99 jobs although real spending was far below the target.

## Required behavior

1. **Admission total:** the account's RunPod-billed charges for the current UTC month, plus the full reservation of every job that has not settled. Admit a job only if this total, plus the new job's reservation and `monthly_storage_reserve_usd`, does not exceed `monthly_target_usd`.
2. **Billed charges:** read them with the existing read-only billing call (`ServerlessProvider.billing("", {startTime, endTime, bucketSize: "month"})`). Use `metadata.totals.totalAmount` for the whole account, rounded up to cents.
   - Make this call before the ledger transaction, so no network call happens while the database is locked.
3. **A job is settled when both of these hold:**
   - its status is terminal (COMPLETED, FAILED, CANCELLED, TIMED_OUT or EXPIRED);
   - now ≥ the latest moment it could have run + 2 hours (`BILLING_LAG_SECONDS = 7200`), because RunPod bills in hourly buckets and the current hour may be incomplete.

   The latest moment it could have run is `worker_result.finished_at` when recorded. Otherwise use `submitted_at` (or `created_at`) + `ttl_seconds` (or `seconds` + `queue_seconds`) + `termination_margin_seconds`.
4. **Who holds a reservation:**
   - Running, queued, UNKNOWN (lost submission response) and recently finished jobs hold their full reservation, whatever month they were created in.
   - A job that was never submitted (no `job_id`) holds nothing.
5. **Fail closed:** if billing cannot be read (any `ComputeError`, or a missing, non-numeric, negative or non-finite amount), use the previous rule: count every reservation made this month.
6. **Refusal messages** keep the code `monthly_limit`:
   - With billing: "Monthly target reached: RunPod-billed charges plus open reservations."
   - Fallback: "Monthly conservative reservations exhausted." (unchanged)
7. **Must not change:**
   - `policy.yaml` limits ($150 target, $20 storage reserve, $5 / 8-hour per-job cap, $1.10/hr Serverless ceiling);
   - the per-job reservation math and concurrency limits;
   - the ledger format;
   - the legacy Pod path (`jobs.py`) and its expiry gate;
   - `compute_budget` output (local limits still never appear in it).

The rule deliberately overcounts a little, which is the safe direction:
- billed charges include storage, and the $20 storage reserve is still added;
- a running job's charges so far are counted both in billing and in its full reservation.

## Acceptance tests

These are added to `tests/test_serverless.py`. The fake `Provider` gains a `billing()` method returning a configurable `totalAmount`, or raising `ComputeError` when it is set to `None`.

| Test | Setup | Expected |
|---|---|---|
| Finished jobs count at billed charges | 30 COMPLETED jobs at $4.99 (=$149.70), finished 3 days ago; billed $40 | admitted |
| Fallback without billing | same 30 jobs; billing raises | refused, "reservations exhausted" |
| Billed charges alone reach the target | billed $129.95 (+ $0.09 job + $20 reserve > $150) | refused, "RunPod-billed charges" |
| Unsettled jobs hold their reservation (parametrized) | one job IN_PROGRESS / UNKNOWN / COMPLETED 10 min ago / FAILED with no finish time submitted 1 h ago (TTL 19,800 s); billed $125.50 | refused (125.50 + 4.99 + 0.09 + 20 > 150) |
| Settled and never-submitted jobs release | COMPLETED 3 h ago; FAILED submitted 4 days ago; FAILED with no job_id; billed $125.50 | admitted |

The parametrized test sets `max_concurrent_experiments=3` and `endpoint_max_workers=3`, so that the concurrency check does not refuse first.

## Verification done on the local branch

- `.venv/bin/pytest`: 138 passed.
- `ruff check src tests scripts`, `ruff format --check src tests scripts` and `mypy src` are clean.
- `scripts/check-docs.py` and `scripts/check-secrets.py` pass.
- **Live run:** after the MCP server reloaded, two Optuna Stage 3 jobs ($4.99 reservation each) were admitted. The previous rule had refused them.
- **Reload needed after merging:** a running `aevah-mcp` process keeps the old code until it is reconnected.

## Docs updated in the same change

- **`docs/ADMIN.md`, "Cost accounting":** the new rule and the fallback.
- **`README.md`:** the limits bullet now describes the new admission.
- **`docs/ARCHITECTURE.md`:** reservation-only accounting is now described as the legacy Pod rule, with Serverless using the new admission.
- **`SECURITY.md`:** reservations are held until a job settles, and the fallback when billing is unreadable.

## Full diff (apply to `12fc757` with `git apply`)

Save the block below as `change.patch` and run `git apply --check change.patch && git apply change.patch`.
Alternatively, re-implement from the spec above.

```diff
diff --git a/README.md b/README.md
index 9ab900d..022979f 100644
--- a/README.md
+++ b/README.md
@@ -67,7 +67,8 @@ The worker reads `/runpod-volume/aevah/{code,datasets}/<hash>/files/` and writes
   claim prevents the provider retrying training after a worker crash.
 - New experiments resume from `previous-experiment/checkpoints/file`; training code must implement
   checkpoint save/load. The wrapper exposes paths, not framework-specific checkpoint logic.
-- Conservative reservations retain the $150 monthly target, $20 storage reserve, $5/8-hour
+- Monthly admission counts RunPod-billed charges plus the reservations of unsettled jobs (every
+  reservation if billing is unreadable); see docs/ADMIN.md. Limits: $150 monthly target, $20 storage reserve, $5/8-hour
   training ceiling and $1.10 hourly Serverless GPU ceiling (legacy Pods remain $0.75). Serverless pricing is separate from Pod
   pricing; the administrator supplies a current ceiling. No expensive-GPU exception is exposed
   through this v1 MCP. Reservations are not a provider billing cap.
diff --git a/SECURITY.md b/SECURITY.md
index e9b9a97..a9e048e 100644
--- a/SECURITY.md
+++ b/SECURITY.md
@@ -13,7 +13,9 @@ treat them as untrusted and review before sharing. Code exclusions are not a ful
 S3 credentials live only on the submitting Mac. No credentials appear in job payloads.
 
 Do not reuse the legacy Pod ledger as a combined Serverless budget. Serverless reservations are
-conservative, retained after failures, and do not replace provider billing reconciliation.
+held until a job has settled (terminal plus a two-hour billing lag), after which RunPod-billed
+charges stand in for them; if billing is unreadable every reservation counts. Admission
+accounting does not replace provider billing reconciliation.
 
 ---
 
diff --git a/docs/ADMIN.md b/docs/ADMIN.md
index c2546d5..230da3e 100644
--- a/docs/ADMIN.md
+++ b/docs/ADMIN.md
@@ -89,10 +89,16 @@ already claimed experiment. Resume explicitly with a new ID and a known checkpoi
 ## Cost accounting
 
 Reservations use the configured hourly ceiling, runtime and existing termination margin, rounded
-up to cents. They are retained after completion, failure and ambiguous submissions. Monthly
-admission includes the $20 storage reserve and $150 target. This is conservative local accounting,
-not a provider billing guarantee: startup, idle, storage, taxes and activity outside this dedicated
-controller require reconciliation. Serverless state is separate from the legacy Pod ledger;
+up to cents. Monthly admission (administrator decision, October 16, 2026) counts the account's
+RunPod-billed charges for the current UTC month plus the full reservation of every job not yet
+settled, and refuses a job when that total, its own reservation and the $20 storage reserve would
+pass the $150 target. A job is settled once it is terminal and two hours have passed since the
+latest moment it could have run (its worker finish time, or submission + TTL + termination margin);
+until then its reservation is held, so running, uncertain and just-finished jobs are never
+undercounted while billing catches up. Jobs that were never submitted hold nothing. If billing
+cannot be read, admission falls back to counting every reservation made this month. This is
+admission accounting, not a provider billing guarantee: taxes and activity outside this dedicated
+controller still require reconciliation. Serverless state is separate from the legacy Pod ledger;
 never run both against a shared budget. No ordinary MCP tool releases reservations or edits limits.
 
 ## Recovery
diff --git a/docs/ARCHITECTURE.md b/docs/ARCHITECTURE.md
index 5aa177b..6e67184 100644
--- a/docs/ARCHITECTURE.md
+++ b/docs/ARCHITECTURE.md
@@ -20,7 +20,7 @@ The worker has no account API credential. It saves results on the network volume
 
 SQLite admission serializes MCP, CLI and watchdog processes on one controller. It is not a distributed lock across Macs. Provider account checks are useful reconciliation but cannot atomically exclude another independent API client. Use a dedicated account and a single authoritative controller initially.
 
-The monthly figure is a conservative reservation ledger. It does not pretend to be live RunPod billing. No automatic refund occurs. Provider-enforced dollar caps, adversarial same-user isolation, a remote cleanup broker, and organization-wide distributed admission are not implemented.
+The legacy Pod monthly figure is a conservative reservation ledger. It does not pretend to be live RunPod billing. No automatic refund occurs. Serverless admission instead counts RunPod-billed charges plus reservations of unsettled jobs, falling back to every reservation when billing is unreadable (docs/ADMIN.md). Provider-enforced dollar caps, adversarial same-user isolation, a remote cleanup broker, and organization-wide distributed admission are not implemented.
 
 ## Future VS Code sidebar
 
diff --git a/src/aevah_compute/serverless.py b/src/aevah_compute/serverless.py
index 89c9694..5391ee2 100644
--- a/src/aevah_compute/serverless.py
+++ b/src/aevah_compute/serverless.py
@@ -18,6 +18,9 @@ from .models import ComputeError, TrainingRequest
 from .staging import VolumeStore, relative, snapshot
 
 TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT", "EXPIRED"}
+# RunPod bills in hourly buckets and the current hour may be incomplete. A finished job keeps its
+# full reservation until two hours after it could last have run, then counts at billed charges.
+BILLING_LAG_SECONDS = 7200
 
 
 COST_METHOD = (
@@ -325,6 +328,7 @@ class TrainingService:
         spec["fingerprint"] = fingerprint
         month = datetime.now(UTC).strftime("%Y-%m")
         self.provider.preflight()
+        billed = self.month_billed()
         with self.ledger.transaction() as db:
             records = [json.loads(r[0]) for r in db.execute("SELECT record FROM training")]
             for record in records:
@@ -339,9 +343,14 @@ class TrainingService:
                 raise ComputeError(
                     "concurrency_limit", "Resolve an active or uncertain experiment first."
                 )
-            spent = sum(Decimal(r["reservation"]) for r in records if r["month"] == month)
+            spent = self.committed(records, month, billed)
             if spent + reservation + p.monthly_storage_reserve_usd > p.monthly_target_usd:
-                raise ComputeError("monthly_limit", "Monthly conservative reservations exhausted.")
+                raise ComputeError(
+                    "monthly_limit",
+                    "Monthly conservative reservations exhausted."
+                    if billed is None
+                    else "Monthly target reached: RunPod-billed charges plus open reservations.",
+                )
             record = dict(
                 spec,
                 status="STAGING",
@@ -382,6 +391,57 @@ class TrainingService:
         job_id = self.provider.submit(spec, request.seconds, request.seconds + s.queue_seconds)
         return self.update(request.experiment, status="IN_QUEUE", job_id=job_id)
 
+    def month_billed(self):
+        """RunPod-billed charges for the whole account this UTC month, or None when billing is
+        unreadable (admission then falls back to counting every reservation)."""
+        now = datetime.now(UTC)
+        month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
+        try:
+            totals = self.provider.billing(
+                "",
+                {
+                    "startTime": iso(month.timestamp()),
+                    "endTime": iso(now.timestamp()),
+                    "bucketSize": "month",
+                },
+            )["metadata"]["totals"]
+            amount = Decimal(str(totals.get("totalAmount") or 0))
+        except (ComputeError, ArithmeticError, KeyError, TypeError, ValueError):
+            return None
+        if not amount.is_finite() or amount < 0:
+            return None
+        return amount.quantize(Decimal(".01"), rounding=ROUND_UP)
+
+    def settled(self, record, now):
+        """A job whose charges RunPod has billed: terminal, and past the billing lag after the
+        latest moment it could have run. Never-submitted jobs have nothing to bill."""
+        if record["status"] not in TERMINAL:
+            return False
+        if not record.get("job_id"):
+            return True
+        end = (record.get("worker_result") or {}).get("finished_at")
+        if not isinstance(end, int | float):
+            start = record.get("submitted_at") or record["created_at"]
+            ttl = record.get("ttl_seconds") or (
+                record["seconds"] + self.settings.serverless.queue_seconds
+            )
+            end = start + ttl + self.policy.termination_margin_seconds
+        return now >= end + BILLING_LAG_SECONDS
+
+    def committed(self, records, month, billed, now=None):
+        """Monthly admission total. With billing: RunPod-billed charges this month plus the full
+        reservation of every job not yet settled (running, uncertain or recently finished).
+        Without billing: every reservation made this month, as before."""
+        if billed is None:
+            return sum(
+                (Decimal(r["reservation"]) for r in records if r["month"] == month), Decimal(0)
+            )
+        now = time.time() if now is None else now
+        held = sum(
+            (Decimal(r["reservation"]) for r in records if not self.settled(r, now)), Decimal(0)
+        )
+        return billed + held
+
     def budget(self, experiment="", per_job=False):
         """RunPod-provided figures only; local limits are admission controls, not costs."""
         if experiment:
diff --git a/tests/test_serverless.py b/tests/test_serverless.py
index 40e0796..45fb56a 100644
--- a/tests/test_serverless.py
+++ b/tests/test_serverless.py
@@ -71,10 +71,16 @@ class Provider:
         self.calls = []
         self.state = "IN_PROGRESS"
         self.fail = False
+        self.billed = 0
 
     def preflight(self):
         pass
 
+    def billing(self, path, params):
+        if self.billed is None:
+            raise ComputeError("billing_forbidden", "No billing access")
+        return {"records": [], "metadata": {"totals": {"totalAmount": self.billed}}}
+
     def submit(self, spec, seconds, ttl):
         self.calls.append((spec, seconds, ttl))
         if self.fail:
@@ -716,6 +722,79 @@ def test_serverless_rate_above_approved_ceiling_denied(training):
         service.run(request)
 
 
+def add_job(service, name, status="COMPLETED", reservation="4.99", finished_ago=None, **fields):
+    now = time.time()
+    record = {
+        "experiment": name,
+        "fingerprint": name,
+        "status": status,
+        "job_id": "job-" + name,
+        "month": datetime.now(UTC).strftime("%Y-%m"),
+        "reservation": reservation,
+        "seconds": 16200,
+        "created_at": now - 4 * 86400,
+        "submitted_at": now - 4 * 86400,
+        "ttl_seconds": 16200 + 3600,
+    }
+    if finished_ago is not None:
+        record["worker_result"] = {"status": "completed", "finished_at": now - finished_ago}
+    record.update(fields)
+    with service.ledger.transaction() as db:
+        db.execute("INSERT INTO training VALUES (?,?)", (name, json.dumps(record)))
+
+
+def test_monthly_admission_counts_finished_jobs_at_billed_charges(training):
+    service, request, _, _ = training
+    for i in range(30):  # $149.70 reserved, far more than the $130 left under the $150 target
+        add_job(service, f"old{i}", finished_ago=3 * 86400)
+    service.provider.billed = 40.0
+    assert service.run(request)["status"] == "IN_QUEUE"
+
+
+def test_monthly_admission_without_billing_counts_every_reservation(training):
+    service, request, _, _ = training
+    for i in range(30):
+        add_job(service, f"old{i}", finished_ago=3 * 86400)
+    service.provider.billed = None
+    with pytest.raises(ComputeError, match="reservations exhausted"):
+        service.run(request)
+
+
+def test_monthly_admission_refuses_when_billed_charges_reach_target(training):
+    service, request, _, _ = training
+    service.provider.billed = 129.95  # + $0.09 request + $20 storage reserve > $150
+    with pytest.raises(ComputeError, match="RunPod-billed charges"):
+        service.run(request)
+
+
+@pytest.mark.parametrize(
+    ("status", "fields"),
+    [
+        ("IN_PROGRESS", {}),  # still running
+        ("UNKNOWN", {}),  # lost submission response
+        ("COMPLETED", {"finished_ago": 600}),  # finished inside the billing lag
+        ("FAILED", {"submitted_at": time.time() - 3600}),  # no finish time: could still be billing
+    ],
+)
+def test_unsettled_jobs_hold_their_full_reservation(training, status, fields):
+    service, request, _, _ = training
+    service.policy = Policy(max_concurrent_experiments=3)
+    service.settings.serverless.endpoint_max_workers = 3
+    add_job(service, "open", status=status, **fields)
+    service.provider.billed = 125.50  # + $4.99 held + $0.09 + $20 > $150
+    with pytest.raises(ComputeError, match="monthly_limit|Monthly target"):
+        service.run(request)
+
+
+def test_settled_and_never_submitted_jobs_count_at_billed_charges(training):
+    service, request, _, _ = training
+    add_job(service, "done", finished_ago=3 * 3600)
+    add_job(service, "expired", status="FAILED")  # submitted 4 days ago, ttl long past
+    add_job(service, "staging_failed", status="FAILED", job_id=None, created_at=time.time())
+    service.provider.billed = 125.50
+    assert service.run(request)["status"] == "IN_QUEUE"
+
+
 def billing_client(seen, hourly=None, status=200):
     def handle(http_request):
         seen.append(http_request)
```
