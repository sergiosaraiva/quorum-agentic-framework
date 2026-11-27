---
chunk_id: QF-027
title: Local AI CI before pushing
topics: [ai-ci, review]
links: [QF-028, QF-026, QF-029, QF-031]
sources: ["scripts/ai_review_local.py", ".claude/skills/running-local-ai-review/SKILL.md", "docs/concepts/08-ai-ci-local-and-github.md"]
---
The local AI CI is the script `scripts/ai_review_local.py`, the required AI review together with the in-session review pair. It uses the `claude` CLI with the user's sign-in; no API key.

How it works: it collects `git diff <base>...HEAD` (default `origin/main`); splits the diff into chunks without dropping code; builds one prompt per chunk from the `pr-review` skill, the quality-guardian and regression-detective instructions, and the Immutable Rules of `CLAUDE.md`, all read at the merge-base of the base and HEAD; the branch's own files still come from the branch; runs `claude -p` read-only with reads fenced to the repository; merges the findings; and writes `findings.md`, `findings.json` and `state.json` to `.ai-review/`.

| Option | Meaning |
|--------|---------|
| `--base` | Diff base; the parent branch for a stacked pull request |
| `--model` | Model alias or id; default `sonnet` |
| `--max-rounds` | Round cap, default 5 |
| `--require` | Exit 2 instead of skipping when the `claude` CLI is missing, HEAD is detached, HEAD has no commits the base lacks, or, with a remote, the base is not a remote-tracking ref or a branch cut from one (`HEAD~1` fails); the branch's own upstream is not an anchor and `origin/HEAD` is used when present; use it for the gate |
| `--reset` | Reset the round counter after a human review; with `--max-rounds`, `--claude-bin` and `--out-dir` it needs approval (`ask`) in settings |
| `--dry-run` | Print the first prompt without calling a model |

Flags are exact, not abbreviated. The round state is always `.ai-review/state.json`, even with `--out-dir`.

Exit codes: 0 no blocking findings, or skipped when the `claude` CLI is missing and `--require` is not set; 1 blocking findings; 2 usage or environment error, including malformed model output; 3 round cap reached.

Use the default Sonnet for routine branches and `--model opus` for authentication, data model, migrations, money or core logic. Later rounds re-report only findings still present.

It does not replace the in-session pair or the human merge. The GitHub AI review is an optional second gate that needs `ANTHROPIC_API_KEY`.
