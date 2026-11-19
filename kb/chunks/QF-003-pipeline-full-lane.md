---
chunk_id: QF-003
title: The Quorum pipeline stages in the full lane
topics: [pipeline, agents]
links: [QF-004, QF-005, QF-006, QF-007, QF-026]
sources: [".claude/agents/_SHARED-PATTERNS.md", "docs/concepts/01-overview-and-pipeline.md", "CLAUDE.md"]
---
The full lane of the Quorum pipeline runs these stages in order:

1. requirements-analyst checks the request against both knowledge bases, lists gaps and records each as a question with a decider.
2. solution-architect produces a design and a dependency-ordered plan, stating the simplest viable option and what is deferred.
3. ux-usability-specialist runs only when a screen is added or redesigned and no approved design exists. It defines flows, states and acceptance criteria before any code.
4. code-engineer implements the design and never reviews its own work.
5. quality-guardian and regression-detective run in parallel, started in one message, each with no Write or Edit tools and a fresh context. They do not overlap: quality-guardian owns correctness, security, data-access safety and design findings; regression-detective owns contract drift, parity between sibling branches, duplicated formulas and swallowed exceptions. For UI changes ux-usability-specialist joins the same message.
6. test-automator runs after every reviewer has returned, and turns the reviewers' `test_would_catch` hints into tests.
7. documentation-curator writes the docs, then documentation-reviewer checks they are grounded.

security-engineer and infrastructure-engineer sit outside the linear order and run proactively when a change touches authentication, data access, secrets, infrastructure or deployment configuration. prompt-engineer runs on request, ahead of any agent.

Before any coding or documentation task, the orchestrating session states the pipeline in one line: the lane, each stage with a few words of reason for any skip, and whether the alignment gate applies.
