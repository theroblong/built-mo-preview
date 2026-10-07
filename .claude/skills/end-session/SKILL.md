---
name: end-session
description: Close a working session per docs/working-agreements/log-everything.md -- log to wiki/18, update project memory, add the README entry, then commit (and push only with confirmation) across the related repos. Use when the user says end session, wrap up, close out, or log this session.
---

# End-of-session routine

Implements the routine in `docs/working-agreements/log-everything.md`, in its order. A
step that cannot run is reported, never silently skipped.

## 1. Preflight

Run `python3 .claude/hooks/check_refs.py`.
- customer-built-doc not located → wiki/18 cannot be written. Ask the user for the path
  now (record it in `.claude/related-repos.local.json`) or agree to skip step 2 and
  say so in the final report.
- Missing references → list them in the final report as still uncommitted.

## 2. Write the session summary (main session, not the scribe)

Start from the `## Live session notes` at the bottom of `agents/project_memory.md` (the
items captured as they happened), then add anything from this conversation they missed.
Bullets under these headings, exactly as they happened:
- **Decided** -- each decision and who made it
- **Received** -- emails or messages from Brian, Rob or others: sender, date, verbatim quote
- **Found** -- results, with the numbers and which MO script produced them
- **Open questions** -- new ones, and existing ones now answered
- **Artifacts** -- files created or changed

Show it to the user and ask whether anything is missing or wrong. The user's correction
is the only check that the record matches what actually happened. Do not continue until
the user confirms.

## 3. Hand the writing to the scribe

Spawn the `scribe` agent (sonnet, medium) with the confirmed summary. It updates:
1. `wiki/18-built-aevah-cadence.md` in customer-built-doc
2. Project memory -- `agents/project_memory.md`
3. The README entry -- the next `## README update N` at the top of README.md

Read its report. Spot-check one edit per file with `git diff`. If it could not record
something, resolve that with the user before committing.

## 4. Commit

For each repo with changes -- this repo and any located repo from
`.claude/related-repos.json` -- show `git status --short`, then commit with a message
naming the session's main finding or decision. This repo's commit must include
`agents/project_memory.md` (the commit hook enforces it).

## 5. Push -- confirm first

Per the agreement, push on confirmation: list exactly what will be pushed (repo, branch,
commits) and ask the user. Push only what is confirmed.

## 6. Report

One short list: each repo -- committed / pushed / skipped and why. Then any unresolved
references from step 1.
