# Design: settled-findings list and the agent roster

Status: **approved by Robert 2026-10-07; built 2026-10-07** (agents, routing, PRIOR WORK gate,
reversal check, draft list). The list awaits Robert + Jason review before it is loaded.
Change it here, by commit, before building something different.

## Why

1. **Context cost.** Most tokens in this repo go on *reading*: the README (637KB),
   `outputs/*.json`, 155 scripts and logs. Judgment uses few tokens but needs the
   strongest model. So cheap agents read and return condensed results; the main session
   decides.
2. **Closed questions get reopened.** Conclusions are scattered through 8,000 lines of
   README. Closed questions get re-tested, and conclusions that have since been
   overturned get trusted.

## Part 1 -- Agent roster

Each agent is a file in `.claude/agents/<name>.md` whose header sets `model:` and
`effort:`. A per-call `model` override beats the header.

| Agent | Model / effort | Tools | Job |
|---|---|---|---|
| `scout` | haiku / low | Read, Grep, Glob (read-only) | Search README history, docs, scripts, outputs. Return **quotes with file:line**, never whole files. |
| `runner` | sonnet / medium | Bash, Read | Run an MO script. Return the tables by band × level, bias, and HOLDS/FAILS per recorded prediction. |
| `scribe` | sonnet / medium | Read, Edit, Write, Bash | **Already built.** Writes wiki/18, project memory and the README entry from a confirmed summary. |
| `skeptic` | opus / high | Read, Grep, Glob, Bash | Adversarial check before a finding is written up. Try to break it: by band, by level, for leakage, for harness parity, and against the settled-findings list. Report what survived. |
| main session | opus / high (project pin) | all | Plan, choose arms, decide. |

Add a routing section to `CLAUDE.md`:
- Any request with more than about 3 steps starts with a written plan that names the
  agent, model and effort for each step, and the user approves it.
- Bulk reading goes to `scout`, never the main context.
- A finding goes to `skeptic` before it reaches the README.

Tune with `/cost` after a few sessions: downgrade an agent that never changes an
outcome; raise effort on one that misses things.

## Part 2 -- Settled-findings list

**File:** `docs/SETTLED_FINDINGS.md`, imported from `CLAUDE.md` (loaded every session).
Keep it under about 150 lines: one entry per closed question, newest first.

**Entry format.** The Scope and Harness fields matter most. Several conclusions in this
repo reversed once the harness was corrected or results were broken down by band.

```
MO_54 · holiday binary flags · PROVISIONAL (closed 2026-07-07)
  Finding:   all 6 flags worse (+0.05–0.15pp); week_of_year already captures the spikes
  Scope:     LightGBM, item×week, Dec-2025 cutpoint, pooled (no band breakout)
  Harness:   before the 2026-10-06 parity correction (MO_118)
  Reopen if: a non-tree model is used, OR re-scored by band and level
  Source:    scripts/MO_54_holiday_ablation.py · README update <n>
```

**Status rules:**
- `SETTLED`: measured on the current harness (after MO_118), at all three levels, and
  by history band.
- `PROVISIONAL`: anything else. These are candidates to re-check, not facts.
- `REVERSED`: kept with a pointer to the result that overturned it. A reversal is itself
  a lesson.
- `FACT` (added at build): data / infra / design facts that do not depend on the
  forecast harness (README 222: panel-level findings stand).

As built, entries are one compact bullet each (status, finding with numbers, scope,
reopen-if, `file:line`) rather than the six-line block above, so ~75 entries fit.

**Building the first version:**
1. `sonnet` extracts candidate entries from the README history and `agents/project_memory.md`.
   Every field is backed by a quote with file:line. Not haiku: telling settled from
   provisional needs judgment.
2. `opus` assigns each entry's status using the rules above.
3. **Robert and Jason review before it is committed.** Nothing goes into the always-loaded
   list unreviewed.

**Enforcement:**
- **Read before testing.** `protocol_gate.py` additionally requires a `PRIOR WORK`
  section in the docstring of MO_127+ scripts. It cites related list entries by MO number,
  or says `none found`. The `new-experiment` skill gets a matching step.
- **Update on reversal.** The commit hook (`require_memory_in_commit.py`) blocks a commit
  when either is true and `docs/SETTLED_FINDINGS.md` is not staged:
  - the staged README diff contains *reversed / withdrawn / wrong / supersedes / inverted*;
  - `agents/project_memory.md` says a finding was overturned.

## Build order

1. The three agent files and the CLAUDE.md routing section. Small, and useful at once.
2. The `PRIOR WORK` gate and the reversal check, with pipe-tests for each case.
3. The settled-findings draft (sonnet extracts, opus assigns status), then Robert and
   Jason review it.
4. Import the reviewed list into CLAUDE.md and commit.

`memory/project_mo54_holiday_ablation.md` stays where it is. Its content seeds the MO_54
entry; do not move or delete it.
