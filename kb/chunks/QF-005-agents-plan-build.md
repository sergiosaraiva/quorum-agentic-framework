---
chunk_id: QF-005
title: Plan and build agents in Quorum
topics: [agents, pipeline]
links: [QF-003, QF-009, QF-024, QF-033]
sources: [".claude/agents/requirements-analyst.md", ".claude/agents/solution-architect.md", ".claude/agents/ux-usability-specialist.md", ".claude/agents/code-engineer.md", ".claude/agents/test-automator.md"]
---
Five Quorum agents plan and build the work. All are Markdown files in `.claude/agents/` with frontmatter naming a model, an effort level and a tool allow-list that includes the business and questions knowledge-base read tools. None can spawn another agent or ask the user: each returns open items (`questions_to_record`) to the calling session.

requirements-analyst (Sonnet, high effort) turns a request into a grounded, testable specification and a list of open questions. It runs the alignment gate steps 1 to 5 during analysis and records gaps as BQ or TQ records instead of guessing. It has Write and Edit only for question records, the requirements document, the slice spec and the slice's row in `docs/slices/INDEX.md` (up to status `Ready`); later status upkeep belongs to the documentation-curator.

solution-architect (Opus, high effort) produces the design and the dependency-ordered plan, cuts vertical slices, and states the simplest viable option, why any extra layer is needed, and what is deferred. A design error costs the most downstream, which is why it runs on the stronger model. It may write only question records and the design document, no slice spec or INDEX row.

ux-usability-specialist (Opus, high effort) defines the UX of a new screen before it is built, producing flows, states, microcopy, acceptance criteria and a clickable mockup for the owner to approve, and reviews built screens for usability. It writes no repository file, only a scratch mockup in the temporary directory.

code-engineer (Sonnet, high effort) implements the approved design and nothing more. It runs the alignment gate first and loads the matching skill before every task. Its work is never self-approved.

test-automator (Sonnet, high effort) writes tests under `tests/`, `*.spec.ts` and `frontend/e2e/**` and runs them; it never edits product code, and a product bug goes back to code-engineer. It implements the `test_would_catch` hints from regression-detective and rejects vacuous tests.
