# `.claude/` — Claude Code configuration

This repo intentionally commits **no** `settings.json` permission baseline.
Permissions inherit from the user-global Claude Code settings
(`~/.claude*/settings.json`), the same as the sibling researcher repos
(lng-terminals, pipelines, refineries) — kept identical on purpose so no repo
prompts differently from the others (settled 2026-07-16; the committed
per-repo baselines had drifted, e.g. only lng-terminals prompted on
`git push`).

Personal per-machine overrides go in `.claude/settings.local.json`
(gitignored, never committed). Settings layer as: enterprise policy → CLI
flags → `settings.local.json` → this repo's `settings.json` (absent) →
user-global.

The guardrails that matter for this project are not permission rules — they
live in `CLAUDE.md`. Secrets live in `.env`, which is gitignored and denied
to Claude's Read tool at the user-global layer.
