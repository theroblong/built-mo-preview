---
name: onboard
description: Set up this repo's shared Claude Code configuration on a collaborator's machine, doing all technical work for them -- pull the update, register related repos, commit machine-only memory files, retire superseded local memories, answer open questions, then verify the hooks after one window reload. Use when the user says onboard, set me up, I just pulled the update, or when the session context says onboarding is pending.
---

# Onboard this machine

## How to work with this user

Assume the user is **not a developer**. You do all the technical work: git, files,
checks. Ask them only for:
- decisions, phrased as plain yes/no or pick-one questions;
- the few clicks only they can make: "Allow" on a permission prompt, reloading VS Code.

Rules:
- No jargon in what you say to them. Say "save and share the changes", not "commit and
  push"; "your copy of the project", not "working tree".
- One short line after each step saying what you did.
- If something fails, fix it yourself if you can. Otherwise explain what happened in one
  sentence and what you need from them.
- At the start, tell them VS Code may show "Allow" buttons for commands, and that
  clicking Allow is safe during setup.

The work runs in two phases with one window reload between them. Claude Code loads hooks
only when a conversation starts, so the reload cannot be avoided.

---

## Phase 1 -- setup (first conversation)

### 1. Get the update

- Run `git status --short`. If there are local changes, set them aside with
  `git stash push -u -m "before onboarding"`.
- Run `git pull`. Then, if you stashed, run `git stash pop`.
- If conflicts appear, resolve them yourself:
  - **`agents/project_memory.md` and `README.md`**: keep both sides' lines. Never drop an
    entry; order them by date.
  - **Anything else**: show the user both versions in plain words and ask which to keep.
- Check python3 is 3.9 or newer with `python3 --version`. The hooks need it. If it is
  missing, stop and tell them in one sentence that Robert needs to help install Python.

### 2. Find the related projects

Run `python3 .claude/hooks/check_refs.py`. For each `REPO NOT LOCATED`:
- Search for a copy by its GitHub address (listed in `.claude/related-repos.json`): run
  `find ~ -maxdepth 6 -type d -name .git -not -path '*/node_modules/*' 2>/dev/null`, then
  for each candidate run `git -C <candidate>/.. remote get-url origin`.
- Found: tell them where you found it, e.g. "I found customer-built-doc in
  Documents/…".
- Not found: ask whether they have it somewhere else. If not, ask whether you should
  download a copy, and where (suggest a folder next to this one).
- Record the paths in `.claude/related-repos.local.json` as
  `{"<repo name>": "<absolute path>"}`.

Re-run `check_refs.py` until no project is reported as unlocated.

### 3. Files that only exist on this computer

`check_refs.py` reports each `MISSING:` wiki-link; its name is the slug. Look in this
machine's assistant memory with `ls ~/.claude/projects/*/memory/`, treating `-` and `_`
as the same character. For each file you find:
- Summarize what it says in two or three lines.
- Say where it will go:
  - `feedback-*` → `docs/working-agreements/<slug>.md`
  - `project_*` → `memory/<slug>.md`
- Ask: "OK to add this to the shared project?" It may mention clients or people, so it
  is their call.
- Copy only the files they say yes to.

### 4. Retire old local copies of the agreements

The files in `docs/working-agreements/` are now the rules everyone follows. In
`~/.claude/projects/*/memory/`, look for older private copies of the same agreements
(e.g. `feedback_log_everything.md`). For each one:
- Tell them in one line how it differs from the shared copy.
- With their OK, replace its contents with a single line pointing to the shared file.
- Never delete the file.

### 5. Their questions

Read `## Live session notes` in `agents/project_memory.md`. Ask every open question
addressed to this user, one at a time, in plain words. For example:

> "Robert set Claude to use the same model and thinking level for both of you, so
> results are consistent. OK?"

Record each answer as a new note:
`- YYYY-MM-DD Decision (<their name>): ...`

Also add a note listing:
- which related projects were found,
- which files were added in step 3,
- anything that could not be found.

### 6. Save and share

- Stage only:
  - `agents/project_memory.md`
  - the files added in step 3
  - their own changes **only if they say so**
- Commit with the message `Onboard <name>'s machine`.
- Ask: "Shall I share these changes with Robert now?" Push only on yes.

### 7. Hand over to phase 2

Write `.claude/onboarding.local.json`:

```json
{"status": "verify-pending", "user": "<name>", "date": "<YYYY-MM-DD>"}
```

This file is per-machine and git ignores it. Then tell them exactly this:

> Almost done -- one click left. Press **Cmd+Shift+P**, type **Reload Window**, press
> Enter. Then click **New conversation** in the Claude panel and type **hi**. I'll
> finish the setup automatically.

---

## Phase 2 -- verify (after the reload)

The session-start context says `ONBOARDING VERIFICATION PENDING`. Before anything else:

### 1. Was the context loaded at session start?

That pending notice is proof the session-start hook ran. Say so in one line.

### 2. Is the commit check active?

- With `agents/project_memory.md` not staged, run
  `git commit --dry-run -m "onboarding check"`. `--dry-run` never creates a commit.
- **Expected:** the hook refuses it.
- **If git answers instead,** the hooks are not active. Ask them to open the Claude
  panel's **Customize** menu → **Hooks** and say what they see, or to accept any
  "trust this workspace" prompt. Then reload once more.
- Do not mark setup complete until this test is refused.

### 3. Which model is running?

Compare the model you are running as with `model` in `.claude/settings.json`.
- **Same:** say so.
- **Different** (their plan may not include it): tell them in one line. Add a live note
  so Robert knows the two machines use different models.

### 4. Finish

- Set `status` to `"done"` in `.claude/onboarding.local.json`.
- Tell them, in three short lines:
  - it is set up;
  - when they finish a working session, type **end session**, and Claude logs
    everything and saves it;
  - anything still open from phase 1.
