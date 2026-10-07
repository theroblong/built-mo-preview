# Working agreement: log everything

Source of truth: this file (supersedes machine-local copies). Agreed 2026-09-25; condensed 2026-10-07.

Purpose: if it isn't logged, it doesn't exist for the system — BUILT and future clients
get better service only from what is recorded.

Log as it happens, not from recall at the end. Capture each item **the same turn** as a
dated bullet under `## Live session notes` at the bottom of `agents/project_memory.md`
(in this repo, so it survives a crash or compaction):
- Email/message from Brian, Rob or others → verbatim quote + takeaways
- New open question → the question, and who raised it
- Decision → what was decided, by whom
- Feedback affecting product or process → what it changes

`/end-session` turns those notes into the wiki/18 entry (async section, outstanding-items
table), the project memory update and the README entry, then commits; it pushes only on
confirmation. Memory never substitutes for wiki/18; both stay current (wiki/18 =
client-facing, memory = assistant index).

See also: [[feedback-meeting-prep-process]]
