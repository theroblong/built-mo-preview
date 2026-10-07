#!/usr/bin/env bash
# SessionStart: put current project state in front of Claude so it does not depend on
# someone remembering to read an 8,000-line README or a 45KB memory file.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}"

ctx=$(
  # Onboarding state comes first: it decides what Claude does before anything else.
  ob=.claude/onboarding.local.json
  if [ -f "$ob" ] && grep -q '"verify-pending"' "$ob"; then
    echo "## ONBOARDING VERIFICATION PENDING"
    echo "Before anything else, whatever the user's first message says: read .claude/skills/onboard/SKILL.md and run Phase 2 (verify). The user is not a developer; do the work and use plain language."
    echo
  elif [ ! -f "$ob" ] && [ ! -f .claude/related-repos.local.json ]; then
    echo "## THIS MACHINE HAS NOT BEEN ONBOARDED"
    echo "Before other work, offer in one plain sentence to set it up, then read .claude/skills/onboard/SKILL.md and run Phase 1 from step 2 if they agree (the update is already pulled). The user may not be a developer."
    echo
  fi
  echo "## Current project state (injected by .claude/hooks/session_context.sh)"
  echo
  echo "### Latest README update (top of README.md)"
  # The newest update is the first '## README update' block; stop at the next one.
  awk '/^## README update/{n++} n==1' README.md | head -60
  echo
  echo "### agents/project_memory.md"
  grep -m1 '^Last synced' agents/project_memory.md
  echo
  awk '/^## Open Follow-Ups/{f=1} /^## Live session notes/{f=0} f' agents/project_memory.md | head -30
  # Notes left behind mean a session ended without /end-session.
  live=$(awk '/^## Live session notes/{f=1; next} /^## /{f=0} f' agents/project_memory.md | grep -v -e '^[[:space:]]*$' -e '^[[:space:]]*<!--')
  if [ -n "$live" ]; then
    echo
    echo "### Live session notes NOT yet logged (a previous session skipped /end-session) -- tell the user and offer to run it"
    echo "$live"
  fi
  echo
  echo "### Recent commits"
  git log --oneline -8
  echo
  echo "Experiments follow docs/FORECAST_TEST_PLAN_V12.md (Protocol section). New MO_ scripts: use the new-experiment skill."
  echo
  python3 .claude/hooks/check_refs.py 2>&1
)

# python3 rather than jq: python is already required by the project, jq may not be installed.
printf '%s' "$ctx" | python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": sys.stdin.read()}}))'
