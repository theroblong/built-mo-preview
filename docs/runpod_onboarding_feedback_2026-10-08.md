# Aevah Compute (RunPod) onboarding feedback: Jason's Mac, 2026-10-08

For Rob, the administrator of github.com/AevahLLC/runpodagent. From Jason's first install and
live tests, run through Claude Code in VS Code. No credentials appear in this note.

## Result

**Onboarding complete; both live tests passed.**

- **Setup.** Fresh clone, then `scripts/install-mac.sh`. The setup questions arrived one at a
  time: endpoint ID → image digest → GPU types and rate → enable → Keychain API key → S3
  profile. Both `training-status` and `training-readiness` report ready (config, endpoint
  readback, S3).
- **`jason-smoke-001`** (5 min / $0.50, submitted from FirstAgent through the MCP tools):
  completed with exit 0 in about 1.3 minutes from submission. It ran steps 1–3 and the
  results were downloaded. $0.09 reserved.
- **`jason-smoke-002`** (resumed from `jason-smoke-001/checkpoints/last.json`): ran steps 4–6
  and completed with exit 0. It reused the code and dataset snapshots, so nothing was
  re-uploaded. It queued for about 16 minutes before a GPU started (see GPU availability).
  $0.09 reserved.
- **`live_validation.verified` is still false.** That is expected: it needs the admin's
  validation record, deadline verification and observed scale-to-zero.

## Three practical constraints before real forecasting work

1. **10-minute job limit.**
   - Endpoint `i38s9kq55vxghm` has a 600-second execution timeout.
   - Our honest backtests take 1–2 hours on the M3 laptop (e.g. MO_129 ran 98 minutes; MO_130
     ran 66 minutes), and every Optuna trial is a full multi-origin backtest.
   - Options:
     - (a) a second training endpoint with a longer timeout, under the same policy ceilings
       ($0.75/h, $5 per 8-hour run, $150/month target);
     - (b) splitting work into under-10-minute chunks that checkpoint and resume, which
       `jason-smoke-002` proved works.
   - (a) is simpler for us. (b) needs every job written for chunking.
2. **GPU availability in EU-RO-1.** The resume job waited about 16 minutes for a free GPU of
   the three approved types. Queue time isn't billed, but it adds wall-clock time and makes
   chunked jobs (option b above) slow. More detail below.
3. **24-hour pricing approval.**
   - `rate_valid_until` is 2026-10-09 13:44 UTC (9:44 AM ET).
   - After that, every job is refused until pricing is reconfirmed. That is correct
     behavior, but at a 24-hour cadence someone has to re-approve almost daily whenever we
     use GPUs.
   - Is there a sensible longer window (a week?), or a reminder before it lapses?

## GPU region availability

**Observed.**
- **First job:** a worker started within about a minute.
- **Second job, 3 minutes later:** about 16 minutes in `IN_QUEUE` with no provider error.
  The worker had scaled to zero after the 5-second idle timeout, as designed, and then had to
  wait for capacity.
- **Approved GPU types:** NVIDIA RTX A5000, NVIDIA GeForce RTX 3090, NVIDIA L4. The console
  price is $0.69/h against a local ceiling of $0.75/h.

**Why region matters.** The network volume `oonje2c8lx` is bound to EU-RO-1, so every job
runs there. Our datasets, code snapshots and checkpoints live on that volume.

**Options to consider.** We haven't checked current availability elsewhere; these are
questions, not recommendations.
1. **Approve more GPU types in EU-RO-1,** within the $0.75/h ceiling, so the queue has more
   capacity to draw on.
2. **Check RunPod's availability for these GPU types by region.** If another data center is
   consistently better stocked, a second volume and endpoint there could serve longer
   training jobs. This also means another storage reserve, and staged data duplicated per
   region.
3. **Keep a minimum of 1 warm worker during active work sessions.** This removes cold starts
   but bills idle time; it is a policy decision, and the readback currently requires minimum
   workers 0.
4. **Track queue times per job.** That would tell us whether 16 minutes was a one-off or
   typical. The agent already records submit and finish times, and a queue-time field in
   `compute_status` would make this easy.

## Onboarding friction (suggested improvements)

1. **Setup answers must be hand-edited.**
   - `aevah answer` only accepts `name` / `goal`. The endpoint ID, image digest, GPU types,
     rate, rate expiry and `enabled` all had to be edited into `config/local.yaml`.
   - The project's own permissions deny Claude reading that file, so Claude had to edit known
     lines blind.
   - Suggestion: `aevah configure set serverless.<key> <value>` with validation (64-character
     digest, timestamp from an ISO date).
2. **The AWS CLI was not installed.** The installer could check for it, and offer
   `brew install awscli`.
3. **S3 credentials file.**
   - `config/credentials.txt` is git-ignored (good), but plain text and world-readable
     (`-rw-r--r--`).
   - Claude loaded it into the `runpod` AWS profile without displaying the values; Jason kept
     the file.
   - Suggestion: an import command that writes the profile and offers to delete the file, or
     at least document `chmod 600`.
4. **Connecting the MCP server to another project.**
   - The VS Code extension has no `claude` CLI, so the server was added to FirstAgent with a
     per-machine `.mcp.json` holding an absolute path to `scripts/mcp-launch.sh`.
   - That file and `.claude/settings.local.json` (`MCP_TOOL_TIMEOUT`) are git-ignored in
     FirstAgent.
   - Tools load only at session start, so a reload is needed.
   - Suggestion: put this snippet in ONBOARDING.md.
5. **`live_validation` stays false after successful smoke and resume runs, with no reason
   given.** Status could list what's missing (admin record, deadline test, scale-to-zero).

## Note on workload fit

Our main forecasting model is LightGBM, which is mostly CPU-bound. GPU workers help most with
the planned deep-model challenger (TFT / DeepAR / Chronos-2) and with running many jobs in
parallel. Worth deciding which workloads go to RunPod first, alongside the timeout question.

## Open questions for Rob

1. Can we have a longer execution timeout, or a second endpoint, for 1–2 hour jobs?
2. Who refreshes the rate approval, and can the window be longer than 24 hours?
3. Should we add GPU types in EU-RO-1, or look at a second region for training?
4. Are you OK with the friction suggestions? I can draft PRs for 1, 3, 4 and 5.
