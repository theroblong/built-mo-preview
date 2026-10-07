@agents/brad.yaml

# Working agreements (committed copies are the source of truth)

@docs/working-agreements/log-everything.md

- Files in this repo override any assistant memory on an individual machine. If a local
  memory conflicts with a committed file, follow the committed file and tell the user.
- Run `/end-session` to close a session; it performs the routine above in order.
- Any forecast-accuracy number or metric in something others will read (Mo Chat, reports,
  decks, wiki, marketing): take it from `docs/ACCURACY_CLAIMS_REGISTER.md` section 2, never
  a retired figure from section 3, and explain it in plain language per section 1 (the
  audience is CFO/FP&A, not data scientists; no bare acronyms like wMAPE). Log every
  correction in its section 4.

# Unresolved references

The session-start context lists references this machine cannot reach (a related repo not
located, or a file committed nowhere, such as a memory that exists only on one person's
machine). Raise them with the user early, not at the end:
- Repo not located: ask for the local path, or offer to clone it, then record it in
  `.claude/related-repos.local.json` (per machine, gitignored).
- Missing file: ask the user to get it committed, here or in the repo it belongs to. If
  the user pastes the content, offer to commit it in the right place.
Re-check any time with `python3 .claude/hooks/check_refs.py`.
