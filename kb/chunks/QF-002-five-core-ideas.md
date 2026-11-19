---
chunk_id: QF-002
title: The five core ideas behind Quorum
topics: [overview, principles]
links: [QF-001, QF-015, QF-024, QF-020]
sources: ["docs/presentation/quorum-framework.md", "README.md", ".claude/agents/_SHARED-PATTERNS.md"]
---
Quorum rests on five ideas, and the rest of the framework follows from them.

1. Ground it. Two knowledge bases are the team's memory: the business knowledge base holds what the product must do, and the questions-and-decisions knowledge base holds what is open and what was decided.
2. Never invent. An agent consults the knowledge bases, cites the chunk or record ids a decision rests on, and when both are silent or in conflict it records a question with a decider instead of guessing.
3. Specialize. Twelve agents each have one role, a tool allow-list and a model sized to the job, for example Opus for reviewers and Sonnet for implementers.
4. Validate independently. The agent that produced a change never approves it. A different role with fresh context, no Write or Edit tools (ux-usability-specialist: scratch Write only) and an equal or stronger model reviews it, and findings carry evidence.
5. Slice vertically. Features are planned and shipped end to end as vertical slices, in small ordered increments, each with an id, dependencies and a readiness analysis.

The shared patterns file `.claude/agents/_SHARED-PATTERNS.md` lists the same principles as a table: never invent, no single point of failure, evidence over verdicts, vertical slices, and delegate (product code goes through the pipeline, because a quick direct edit skips the review pair).

Each idea has a mechanism that enforces it: knowledge-base tools in the agents' allow-lists, the alignment gate before code, reviewer agents without Write or Edit tools, a three-round review cap, and a slice index that is updated in every code pull request.
