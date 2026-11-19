---
chunk_id: QF-027
title: Local AI CI before pushing
topics: [ai-ci, review]
links: [QF-028, QF-026, QF-029, QF-031]
sources: ["scripts/ai_review_local.py", ".claude/skills/running-local-ai-review/SKILL.md", "docs/concepts/08-ai-ci-local-and-github.md"]
---
The local AI CI is the script `scripts/ai_review_local.py`, a cheap rehearsal of the GitHub review. It runs before the first push so that blocking defects are fixed before they cost a GitHub review round. The skill `running-local-ai-review` describes when to use it.

How it works: it collects `git diff <base>...HEAD`, by default against `origin/main`; splits the diff into chunks under a byte limit (60000 by default) without dropping code; builds one prompt per chunk from the `pr-review` skill, the instructions of quality-guardian and regression-detective only, and the Immutable Rules of the root `CLAUDE.md`; runs `claude -p` headless with the read-only tools `Read Grep Glob`; merges the findings; and writes `findings.md`, `findings.json` and `state.json` to `.ai-review/`.

| Option | Meaning |
|--------|---------|
| `--base` | Diff base; the parent branch for a stacked pull request |
| `--model` | Model alias or id; default `sonnet`, or `haiku` for a cheaper first pass |
| `--max-rounds` | Round cap, default 3 |
| `--reset` | Reset the round counter after a human review |
| `--dry-run` | Print the first prompt without calling a model |

Exit codes: 0 no blocking findings, 1 blocking findings, 2 usage or environment error, including malformed model output, 3 round cap reached.

Choose the model by risk: a routine branch uses the default Sonnet, while authentication, data model, migrations, money or core logic can use `--model opus`, which is closer to the Opus default of the GitHub review. Each later round receives the previous findings and re-reports only those still present. The standard prompt is fixed so results compare round to round.

The local review is a rehearsal and does not replace the gate. It runs only two reviewer prompts, with no security or infrastructure reviewer, on a cheaper model. It does not replace the review pair in the pipeline, the GitHub AI review or a human merge decision. Run tests and format first, then the local review, then push.
