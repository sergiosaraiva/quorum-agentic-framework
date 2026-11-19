---
chunk_id: QF-009
title: Default model and effort per Quorum agent
topics: [models, agents, cost]
links: [QF-030, QF-024, QF-031]
sources: ["docs/reference/model-selection-and-costs.md", ".claude/agents/", "docs/concepts/01-overview-and-pipeline.md"]
---
Each Quorum agent has a default model and effort level, set in the `model:` and `effort:` lines of its file in `.claude/agents/`.

| Agent | Model | Effort | Reason |
|-------|-------|--------|--------|
| requirements-analyst | sonnet | high | Structured gap analysis grounded in the knowledge bases |
| solution-architect | opus | high | Design errors are the most expensive errors |
| ux-usability-specialist | opus | high | Judgment-heavy review |
| code-engineer | sonnet | high | Implements an already approved design |
| quality-guardian | opus | high | Independent reviewer |
| regression-detective | opus | high | Independent reviewer |
| test-automator | sonnet | high | Verified by running the tests |
| documentation-curator | sonnet | medium | Low-risk writing that is then reviewed |
| documentation-reviewer | sonnet | high | Checks claims against sources, mostly lookup |
| security-engineer | opus | high | Security misses are the costliest |
| infrastructure-engineer | opus | high | Infrastructure mistakes have a large blast radius |
| prompt-engineer | haiku | not set | Short, cheap, easy to inspect |

The rationale is to spend on the checker and save on the maker: a reviewer error costs an escaped defect, while an implementer error costs a review round. A reviewer weaker than the author cannot reliably catch the author's mistakes, so no reviewer is set lower than the tier of the agent whose work it reviews.

Agents use the aliases `opus`, `sonnet` and `haiku`, which resolve to the current model of that tier. A full model id is pinned only for reproducible evaluation runs. `scripts/framework_lint.py` and the pre-commit hook in `.claude/hooks/pre-commit-framework-check.sh` reject any other `model` value in an agent file. documentation-reviewer runs Sonnet, the same tier as the curator it checks, because grounding is mechanical lookup. Change a default with evidence, one agent at a time.
