---
chunk_id: QF-030
title: Choosing a model and an effort level
topics: [models, cost]
links: [QF-009, QF-031, QF-024]
sources: ["docs/reference/model-selection-and-costs.md"]
---
The Quorum model guide assigns models by the cost of being wrong, and it treats every price as a snapshot re-verified on 2026-11-19 against the Anthropic pricing page and API reference (the guide itself was written 2026-11-18). The current family is Fable 5.2, Opus 5.5, Sonnet 5.5 and Haiku 5.5, each listed with a one-million-token context; Haiku 5.5 is billed at a higher tier above 100K tokens.

| Situation | Model |
|-----------|-------|
| Independent review (quality, regression, security) | Opus, because a reviewer must be at least as capable as the author |
| Architecture and dependency-ordered planning | Opus |
| Implementation from an approved design, tests, docs, chunks | Sonnet |
| Requirements analysis | Sonnet at high effort; escalate to Opus for ambiguous multi-system specs |
| Prompt sharpening, classification, routing, bulk triage | Haiku |
| A task that failed twice on Sonnet | Opus once, then back to Sonnet |
| Local AI CI rehearsal | Sonnet by default, Haiku for a first pass |
| GitHub AI CI on every pull request | Opus by default, overridable with the repository variable `AI_REVIEW_MODEL` |
| Hardest long-horizon work | Fable 5.2, reserved because it costs twice the Opus input price |

The rule of thumb is to spend on the checker and save on the maker.

Effort sets how much the model thinks and is the main quality-versus-cost dial inside one model. `low` suits simple subagent tasks, `medium` documentation and straightforward edits, `high` coding, review and requirements analysis, `xhigh` hard agentic tasks where measured results improve, and `max` measuring a ceiling. Measure on real tasks before raising a default, tune per agent and judge cost per finished task. Lowering effort on a newer model often matches the previous generation at high effort, so try that before a model cascade, since caches are model-scoped.

The advisor pattern is a related idea: a Sonnet executor consults a stronger Opus advisor at key points. It is cheap early correction and does not replace the independent reviewer agents.
