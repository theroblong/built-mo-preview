#!/usr/bin/env python3
"""PreToolUse(Bash) gate: a `git commit` in THIS repo must include agents/project_memory.md.

Enforces the durable instruction in agents/brad.yaml rather than relying on recall.
Commits in other repos (e.g. customer-built-doc during /end-session) are not affected:
the target repo is resolved from `git -C <dir>` or a preceding `cd <dir>`.
Escape hatch for commits that genuinely carry no project context: put "[no-memory]" in
the commit message.
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

payload = json.load(sys.stdin)
cmd = payload.get("tool_input", {}).get("command", "")
if "commit" not in cmd or "[no-memory]" in cmd:
    sys.exit(0)

project = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
cwd = Path(payload.get("cwd") or project)


def git(*args: str, at: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(at), *args], capture_output=True, text=True)


def toplevel(p: Path) -> Path | None:
    r = git("rev-parse", "--show-toplevel", at=p)
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 else None


# Walk the command's segments, tracking `cd`, and check each `git ... commit`.
blocked = False
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
    staged = git("diff", "--cached", "--name-only", at=project).stdout.split()
    if MEM in staged:
        continue
    # `git commit -a` / `-am` stages tracked modifications itself.
    if any(re.fullmatch(r"-[a-zA-Z]*a[a-zA-Z]*", t) for t in rest[1:]) and \
            git("diff", "--quiet", "--", MEM, at=project).returncode != 0:
        continue
    blocked = True

if blocked:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            f"Commit blocked: {MEM} is not staged. Per agents/brad.yaml, update it with the "
            f"decisions, artifacts, open questions and commit notes from this work, "
            f"`git add {MEM}`, then commit again. If this commit truly carries no project "
            f"context, include [no-memory] in the message."),
    }}))
