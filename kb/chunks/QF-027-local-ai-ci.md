---
chunk_id: QF-027
title: Local AI CI before pushing
topics: [ai-ci, review]
links: [QF-028, QF-026, QF-029, QF-031]
sources: ["scripts/ai_review_local.py", ".claude/skills/running-local-ai-review/SKILL.md", "docs/concepts/08-ai-ci-local-and-github.md"]
---
The local AI CI is the script `scripts/ai_review_local.py`, the required AI review together with the in-session review pair. It uses the `claude` CLI with the user's sign-in.

How it works: it collects `git diff <base>...HEAD`; splits the diff into chunks, dropping no code; builds one prompt per chunk from the `pr-review` skill, the quality-guardian and regression-detective instructions and the Immutable Rules, read at the merge-base; runs `claude -p` read-only; merges the findings (on later rounds it re-checks earlier findings and re-reports one only if still present); and writes `findings.md`, `findings.json` and `state.json` to `.ai-review/`.

| Option | Meaning |
|--------|---------|
| `--base` | Diff base, default `origin/main`; a stacked rung uses `origin/main` too under `--require` (TQ-022), a parent base is fine only without `--require` (not the gate) |
| `--model` | Model alias or id, default `sonnet` |
| `--max-rounds` | Round cap, default 5 |
| `--require` | Exit 2 instead of skipping when `claude` is missing, HEAD has no new commits or, with a remote, HEAD is detached or the base is not the remote default branch (`origin/main`) at the fork point (`git remote set-head <remote> -a` if `<remote>/HEAD` is missing); use it for the gate. Flags are exact; reads are fenced to the repository |
| `--reset` | Reset the round counter after a human review; each of `--reset`, `--max-rounds`, `--claude-bin` and `--out-dir` has its own `ask` rule in settings |
| `--dry-run` | Print the first prompt, no model call |

`--out-dir` moves only the findings files; round state stays in `.ai-review/state.json`. A branch rename starts a new round count.

Exit codes: 0 no blocking findings, or skipped when `claude` is missing without `--require`; 1 blocking findings; 2 usage or environment error, including malformed model output; 3 round cap reached.

Use the default Sonnet for routine branches and `--model opus` for risky changes (authentication, data model, migrations, money, core logic).

It does not replace the in-session pair or the human merge. The GitHub AI review is an optional second gate needing `ANTHROPIC_API_KEY`.
