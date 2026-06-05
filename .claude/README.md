# Claude Code permissions — what this config does and why

`.claude/settings.json` controls what Claude Code can do without stopping to ask you. It's checked into the repo so the behavior is consistent across machines. This file explains the choices; you can delete it or keep it as a reference.

## The goal

As permissive as possible for the routine batch workflow, without ever turning on `bypassPermissions` (the "skip all checks" mode). The model runs freely on the things you do every batch — pull the backend, fetch CSB, verify URLs, build the workbook, commit — and only stops to ask on the handful of actions that are irreversible or touch the public remote.

## How the rules evaluate

Claude Code checks rules in the order **deny → ask → allow**, first match wins. So a deny always beats an allow, and an ask beats an allow. Anything that matches no rule falls through to `defaultMode`.

## defaultMode: acceptEdits

This auto-accepts file edits anywhere in the working tree and auto-runs common filesystem commands (`mkdir`, `touch`, `mv`, `cp`). It does **not** auto-run arbitrary shell commands — those still need to be on the allow list or they prompt. This is the right default here because you're constantly iterating on scripts and SOPs; having every edit prompt would be miserable, and edits are reversible via git.

Read-only bash commands (`ls`, `cat`, `grep`, `head`, `tail`, `diff`, `wc`, `git status`, `git log`, etc.) run without prompts in every mode — that's built into Claude Code, not something this file configures.

## allow — the batch workflow

- **`Bash(python scripts/*)`** and the pytest/ruff entries cover running the scripts plus the optional dev tooling. The workflow blocks in `CLAUDE.md` invoke them as `python scripts/<name>.py` from the repo root precisely so they match this rule. (Claude Code strips wrappers like `timeout`, so `timeout 60 python scripts/csb_fetch.py samsung` is also covered.)
- **`Bash(curl *)`** — the SOPs require `curl -A "Mozilla/5.0"` for the Google Sheets export and chinashipbuild.com (web_fetch is blocked for those). curl here is always a read-only GET with no auth, so a broad allow is low-risk. See the caveat below.
- **`Bash(git add/commit/checkout/branch/...)`** — the whole local git flow except the things that reach the remote or destroy history.
- **`Edit(...)` / `Write(...)`** — scoped to the project directories. Largely redundant with `acceptEdits` but documents intent and survives a mode change.
- **`WebFetch(domain:...)`** — the sources the SOPs name (CSB, Google Docs, marinetraffic.org, DART, KIND, and the main trade-press sites). WebFetch to other domains will prompt.

## ask — confirm first, then proceed

- **`Bash(git push *)`, `Bash(git remote *)`, `Bash(gh *)`** — anything that touches the public remote. CLAUDE.md already says never push without approval; this enforces it at the harness level. Put in `ask` rather than `deny` so you *can* approve a push in-conversation when you mean to.
- **`Bash(pip install *)`, `Bash(npm *)`** — installing new packages is worth a glance. The two specific installs you'll actually run (`pip install -e .` and `pip install -e .[dev]`) are on the allow list, so those don't prompt; anything else does.

## deny — never, even if asked

- **`rm -rf` / `rm -fr`, `git reset --hard`, `git clean`, `git push --force`** — irreversible destruction of files or history. These match before any allow rule, so they're blocked outright. (Note `git push --force` is also caught here even though plain `git push` is only `ask` — force-push is a different risk class.)
- **Credential reads** — `.env`, `*.pem`, SSH/AWS/gh config, private keys. This repo has no secrets, but it's a public repo and this is cheap defense-in-depth: it stops an accidental `cat ~/.ssh/id_rsa` from ever happening.
- **`Edit(/.git/**)`** — never hand-edit git internals.

## The one real caveat: curl

Claude Code's docs are explicit that bash patterns can't reliably constrain `curl` to specific domains (options, redirects, variables, and protocol changes all defeat a `Bash(curl <domain> *)` pattern). So `Bash(curl *)` here is genuinely broad — Claude could curl any URL without prompting. For this workflow that's an acceptable trade because:

1. Every curl in the SOPs is an unauthenticated read (GET), no POST/PUT/credentials.
2. The repo holds no secrets to exfiltrate.

If you ever want to tighten this, the robust options (from the Claude Code docs) are: deny `curl`/`wget` entirely and rely on the `WebFetch(domain:...)` allows instead, or add a PreToolUse hook that validates the URL. Not necessary for now, but noted.

## Adjusting

Run `/permissions` inside a Claude Code session to see the active rules and where each came from. The healthy way to grow this list: add a rule the *second* time a prompt annoys you, not the first — the first time is a signal, the second is a pattern. Adding rules speculatively just creates an allow list full of commands you've never run.
