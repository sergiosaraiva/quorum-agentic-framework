---
chunk_id: QF-027
title: Local AI CI before pushing
topics: [ai-ci, review]
links: [QF-028, QF-026, QF-029, QF-031]
sources: ["scripts/ai_review_local.py", ".claude/skills/running-local-ai-review/SKILL.md", "docs/concepts/08-ai-ci-local-and-github.md"]
---
The local AI CI is the script `scripts/ai_review_local.py`, the required AI review together with the in-session review pair. It uses the `claude` CLI with the user's sign-in.

How it works: it collects `git diff <base>...HEAD`; splits the diff into chunks, dropping no code; builds one prompt per chunk from the `pr-review` skill, the quality-guardian and regression-detective instructions and the Immutable Rules, all read at the merge-base; runs `claude -p` read-only with reads fenced to the repository; merges the findings; and writes `findings.md`, `findings.json` and `state.json` to `.ai-review/`.

| Option | Meaning |
|--------|---------|
| `--base` | Diff base, default `origin/main`; a stacked rung uses `origin/main` too under `--require` (TQ-022), a parent base is fine only without `--require` (not the gate) |
| `--model` | Model alias or id; default `sonnet` |
| `--max-rounds` | Round cap, default 5 |
| `--require` | Exit 2 instead of skipping when the `claude` CLI is missing or HEAD has no commits the base lacks; with a remote, also when HEAD is detached or the base is not the remote default branch (`origin/HEAD`, else a remote-tracking tip) at the fork point, so `HEAD~1` fails; without a remote, a notice only; use it for the gate |
| `--reset` | Reset the round counter after a human review; each of `--reset`, `--max-rounds`, `--claude-bin` and `--out-dir` has its own `ask` rule in settings |
| `--dry-run` | Print the first prompt without calling a model |

Flags are exact, not abbreviated. `--out-dir` moves only `findings.json` and `findings.md`; the round state is always `.ai-review/state.json`. A branch rename starts a new round count (known limit).

Exit codes: 0 no blocking findings, or skipped when the `claude` CLI is missing and `--require` is not set; 1 blocking findings; 2 usage or environment error, including malformed model output; 3 round cap reached.

Use the default Sonnet for routine branches and `--model opus` for risky changes (authentication, data model, migrations, money).

It does not replace the in-session pair or the human merge. The GitHub AI review is an optional second gate that needs `ANTHROPIC_API_KEY`.
