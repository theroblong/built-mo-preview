#!/usr/bin/env python3
"""PreToolUse(Bash) gate on `git commit` in THIS repo. Two checks:

1. agents/project_memory.md must be in the commit (the durable instruction in
   agents/brad.yaml). Escape hatch: "[no-memory]" in the commit message.
2. If the README or memory lines being added read as a reversal ("reversed",
   "withdrawn", "wrong", "supersedes", "inverted", "overturned"), then
   docs/SETTLED_FINDINGS.md must be in the commit too. Escape hatch:
   "[no-findings-change]".

Commits in other repos (e.g. customer-built-doc during /end-session) are not affected:
the target repo is resolved from `git -C <dir>` or a preceding `cd <dir>`.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

MEM = "agents/project_memory.md"
FINDINGS = "docs/SETTLED_FINDINGS.md"
REVERSAL = re.compile(r"\b(revers(ed|al|es)|withdrawn|wrong|supersed(es|ed)|inverted|overturned)\b",
                      re.IGNORECASE)

payload = json.load(sys.stdin)
cmd = payload.get("tool_input", {}).get("command", "")
if "commit" not in cmd:
    sys.exit(0)

project = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
cwd = Path(payload.get("cwd") or project)


def git(*args: str, at: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(at), *args], capture_output=True, text=True)


def toplevel(p: Path) -> Path | None:
    r = git("rev-parse", "--show-toplevel", at=p)
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 else None


# Walk the command's segments, tracking `cd`, and check each `git ... commit`.
reasons: list[str] = []
here = cwd
for seg in re.split(r"&&|\|\||;|\|", cmd):
    try:
        toks = shlex.split(seg)
    except ValueError:
        toks = seg.split()
    if not toks:
        continue
    if toks[0] == "cd" and len(toks) > 1:
        here = (here / os.path.expanduser(toks[1])).resolve()
        continue
    if toks[0] != "git":
        continue
    at, rest = here, toks[1:]
    while len(rest) >= 2 and rest[0] == "-C":
        at, rest = (at / os.path.expanduser(rest[1])).resolve(), rest[2:]
    if not rest or rest[0] != "commit":
        continue
    if toplevel(at) != project:
        continue  # a commit in another repo
    # `git commit -a` / `-am` stages tracked modifications itself, so judge the
    # working tree against HEAD instead of the index.
    all_flag = any(re.fullmatch(r"-[a-zA-Z]*a[a-zA-Z]*", t) for t in rest[1:])
    diff_base = ["diff", "HEAD"] if all_flag else ["diff", "--cached"]
    changed = set(git(*diff_base, "--name-only", at=project).stdout.split())

    if MEM not in changed and "[no-memory]" not in cmd:
        reasons.append(
            f"{MEM} is not staged. Per agents/brad.yaml, update it with the decisions, "
            f"artifacts, open questions and commit notes from this work, `git add {MEM}`, "
            f"then commit again. If this commit truly carries no project context, include "
            f"[no-memory] in the message.")

    # A reversal recorded in the README or memory must update the settled-findings list
    # in the same commit, or the list keeps asserting something the team no longer believes.
    if (project / FINDINGS).exists() and FINDINGS not in changed \
            and "[no-findings-change]" not in cmd:
        added = [l[1:] for l in git(*diff_base, "-U0", "--", "README.md", MEM,
                                    at=project).stdout.splitlines()
                 if l.startswith("+") and not l.startswith("+++")]
        hits = [l.strip() for l in added if REVERSAL.search(l)]
        if hits:
            reasons.append(
                f"this commit records what reads as a reversal, but {FINDINGS} is not "
                f"staged. First matching line: \"{hits[0][:160]}\". Mark the affected entry "
                f"REVERSED (or add the new finding), `git add {FINDINGS}`, and commit again. "
                f"If nothing was reversed, include [no-findings-change] in the message.")

if reasons:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "Commit blocked:\n- " + "\n- ".join(dict.fromkeys(reasons)),
    }}))
