#!/usr/bin/env python3
"""Find what the always-loaded guidance refers to but this machine cannot reach.

Run at SessionStart (from session_context.sh). Prints a short report, or nothing when
everything resolves. Two kinds of gap, handled differently:

  * Related repo not located -- the reference is committed somewhere, but this machine
    has no clone registered in .claude/related-repos.local.json. Ask the user for the
    path and write it there.
  * Reference missing -- not in this repo, nor in any located related repo. It probably
    lives only on one person's machine (an assistant memory, a local note). Ask the user
    to get it committed, here or in the repo it belongs to.

Scans only the curated guidance files, not the README changelog, whose old references
are history rather than instructions.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
SCAN = ["CLAUDE.md", "docs/working-agreements/*.md", "agents/*.yaml", "memory/*.md",
        ".claude/skills/*/SKILL.md", ".claude/agents/*.md"]
# Where a [[wiki-link]] slug may live, as <slug>.md with - and _ treated alike.
LINK_DIRS = ["docs/working-agreements", "memory", "agents", "docs"]


def norm(s: str) -> str:
    return s.lower().replace("_", "-")


def remote_of(path: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(path), "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def locate_repos() -> tuple[dict[str, Path], list[dict]]:
    cfg = json.loads((ROOT / ".claude/related-repos.json").read_text())
    local_f = ROOT / ".claude/related-repos.local.json"
    local = json.loads(local_f.read_text()) if local_f.exists() else {}
    found, unlocated = {}, []
    for r in cfg["repos"]:
        if r.get("self"):
            continue
        cands = [Path(local[r["name"]]).expanduser()] if r["name"] in local else []
        cands += [ROOT.parent / r["name"], ROOT.parent.parent / r["name"]]
        hit = next((c for c in cands if c.is_dir() and remote_of(c) == r["remote"]), None)
        if hit:
            found[r["name"]] = hit
        else:
            unlocated.append(r)
    return found, unlocated


def main() -> None:
    found, unlocated = locate_repos()
    cfg = json.loads((ROOT / ".claude/related-repos.json").read_text())
    prefix_owner = {p: r["name"] for r in cfg["repos"] for p in r.get("resolves", [])}

    link_files = {norm(p.stem) for d in LINK_DIRS for p in (ROOT / d).glob("**/*.md")}
    missing: dict[str, set[str]] = {}
    needs_repo: dict[str, set[str]] = {}

    for pattern in SCAN:
        for f in sorted(ROOT.glob(pattern)):
            text = f.read_text(encoding="utf-8", errors="replace")
            src = str(f.relative_to(ROOT))
            for slug in re.findall(r"\[\[([^\]]+)\]\]", text):
                if norm(slug) not in link_files:
                    missing.setdefault(f"[[{slug}]]", set()).add(src)
            for ref in set(re.findall(r"\bwiki/(\d+)", text)):
                owner = prefix_owner.get("wiki/")
                if owner in found:
                    if not list((found[owner] / "wiki").glob(f"{int(ref):02d}-*.md")):
                        missing.setdefault(f"wiki/{ref} (in {owner})", set()).add(src)
                else:
                    needs_repo.setdefault(owner or "?", set()).add(f"wiki/{ref}")

    lines = []
    for r in unlocated:
        refs = sorted(needs_repo.get(r["name"], []))
        why = f" -- needed for {', '.join(refs)}" if refs else ""
        lines.append(f"- REPO NOT LOCATED: {r['name']} ({r['remote']}){why}. "
                     f"Ask the user for the local path (or offer to clone it) and record it "
                     f"in .claude/related-repos.local.json.")
    for ref, srcs in sorted(missing.items()):
        lines.append(f"- MISSING: {ref}, referenced from {', '.join(sorted(srcs))}. Not "
                     f"committed anywhere reachable; likely on one person's machine only. "
                     f"Ask the user to get it committed.")
    if lines:
        print("### Unresolved references (raise these with the user early in the session)")
        print("\n".join(lines))


if __name__ == "__main__":
    main()
