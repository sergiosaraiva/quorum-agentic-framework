---
chunk_id: QF-006
title: Who reviews code in Quorum: the review agents
topics: [agents, validation]
links: [QF-024, QF-025, QF-026, QF-003]
sources: [".claude/agents/quality-guardian.md", ".claude/agents/regression-detective.md", ".claude/agents/_SHARED-PATTERNS.md", "docs/concepts/07-independent-validation.md"]
---
Code in Quorum is reviewed by two core reviewer agents, quality-guardian and regression-detective, plus ux-usability-specialist when UI paths changed. All three run on Opus at high effort. quality-guardian and regression-detective have no Write or Edit tools, and their Bash is limited to reading, building and testing. ux-usability-specialist has only `Write`, for scratch mockups in the temporary directory, and no `Edit`. They are started together in one message so they run concurrently and cannot anchor on each other's findings. security-engineer reviews authentication, data and infrastructure changes proactively, outside this pair.

quality-guardian protects correctness, security and design. It owns pattern compliance for endpoints, services, DTOs and Angular components, security, EF Core query safety such as N+1 and unbounded queries, resource and memory safety, and all findings against the design principles. It also verifies the `chunk_id` claims in an alignment result against the knowledge base; a missing alignment result for an in-scope change is a High finding, which blocks.

regression-detective finds what a change quietly breaks elsewhere. It uses the skill `detecting-regressions` for the B1 to B6 patterns (contract drift, sibling-branch parity, config coupling breaks, formula duplication drift, required-invariant violations, silent exception swallowing) and `verifying-cross-file-coupling` for the C1 to C6 coupling series. Each finding carries a `test_would_catch` hint that test-automator turns into a test.

ux-usability-specialist reviews usability and rendered behaviour of UI changes.

documentation-reviewer plays the same independent role for docs and chunks. quality-guardian and regression-detective also review framework changes to agents, skills and governed sections of `CLAUDE.md`.

Subagents cannot spawn subagents. An instruction to re-invoke a writer is addressed to the orchestrating session, never to the reviewer.
