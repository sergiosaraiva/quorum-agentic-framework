---
chunk_id: QF-027
title: Local AI CI before pushing
topics: [ai-ci, review]
links: [QF-028, QF-026, QF-029, QF-031]
sources: ["scripts/ai_review_local.py", ".claude/skills/running-local-ai-review/SKILL.md", "docs/concepts/08-ai-ci-local-and-github.md"]
---
The local AI CI is the script `scripts/ai_review_local.py`, the required AI review, together with the in-session review pair. It uses the `claude` CLI with the user's own sign-in and needs no API key. It runs before the first push.

How it works: it collects `git diff <base>...HEAD` (default `origin/main`); splits the diff into chunks (60000 bytes by default) without dropping code; builds one prompt per chunk from the `pr-review` skill, the quality-guardian and regression-detective instructions, and the Immutable Rules of `CLAUDE.md`, all read from the base revision (the branch's own `CLAUDE.md` files, settings, the files the reviewer reads and the script itself still come from the branch); runs `claude -p` read-only (`--tools Read,Grep,Glob`, no write, web or MCP tools, reads fenced to the repository); merges the findings; and writes `findings.md`, `findings.json` and `state.json` to `.ai-review/`.

| Option | Meaning |
|--------|---------|
| `--base` | Diff base; the parent branch for a stacked pull request |
| `--model` | Model alias or id; default `sonnet` |
| `--max-rounds` | Round cap, default 3 |
| `--require` | Exit 2 instead of skipping when the `claude` CLI is missing, or when HEAD has no commits the base lacks; use it for the gate |
| `--reset` | Reset the round counter after a human review |
| `--dry-run` | Print the first prompt without calling a model |

Exit codes: 0 no blocking findings, or skipped when the `claude` CLI is missing and `--require` is not set; 1 blocking findings; 2 usage or environment error, including malformed model output; 3 round cap reached.

Choose the model by risk: a routine branch uses the default Sonnet; authentication, data model, migrations, money or core logic use `--model opus`. Each later round receives the previous findings and re-reports only those still present.

The local review is the required gate only together with the in-session review pair over the whole branch; it does not replace that pair or the human merge decision. The GitHub AI review is an optional second gate that needs `ANTHROPIC_API_KEY`. Run tests and format first.
