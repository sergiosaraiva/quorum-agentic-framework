---
chunk_id: QF-007
title: Documentation agents in Quorum
topics: [agents, documentation]
links: [QF-010, QF-006, QF-018, QF-024]
sources: [".claude/agents/documentation-curator.md", ".claude/agents/documentation-reviewer.md", ".claude/skills/SKILL-INDEX.md", ".claude/agents/_SHARED-PATTERNS.md"]
---
Two Quorum agents handle documentation, and they are deliberately separate so that the writer is never the approver.

documentation-curator (Sonnet, medium effort) decides which docs need updating after a change and writes them. It uses three styles through three skills: `updating-internal-docs` for terse `CLAUDE.md` files, agent bodies and skill bodies; `updating-external-docs` for READMEs, guides and release notes in plain prose; and `writing-kb-chunks` for business knowledge-base chunks written for embedding retrieval. It runs proactively after a feature ships, an architecture change or a change to a framework rule, and it never approves its own output. Its permission mode is `acceptEdits`.

documentation-reviewer (Sonnet, high effort) verifies that a doc is grounded: every claim must trace to a code path with an anchor, a knowledge-base chunk, a record or an external URL. It also checks completeness and correctness, and it uses `reviewing-documentation` for docs and `reviewing-kb-chunks` for chunks. It has no Write or Edit tools, so it reports findings and never edits. It runs on Sonnet, the same tier as the curator it checks, because grounding is mostly lookup. A finding of status `ungrounded`, `fabricated-citation`, `stale`, `conflict` or `gate-failure` blocks; other statuses, style findings and unverified items (confidence 0.50 to 0.79) do not. For framework or governance docs it runs last, after quality-guardian and regression-detective.

The loop-back rule applies: a blocking finding from documentation-reviewer returns to documentation-curator, and the reviewer runs again.

The root `CLAUDE.md` delegation table routes edits to `kb/**`, `docs/**`, `README.md`, `.claude/agents/**` and `.claude/skills/**` through this curator-then-reviewer pair, and generated files are regenerated rather than hand-edited.
