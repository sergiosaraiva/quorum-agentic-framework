---
chunk_id: QF-015
title: The never-invent grounding rule
topics: [grounding, principles]
links: [QF-012, QF-013, QF-016, QF-017]
sources: ["CLAUDE.md", "docs/concepts/04-never-invent.md", ".claude/agents/_SHARED-PATTERNS.md"]
---
The never-invent rule says that every product, business or behaviour claim an agent makes must rest on a record, not on recall. A record is a chunk in the business knowledge base or a question or decision in the questions-and-decisions knowledge base. The root `CLAUDE.md` states it once, and every agent restates it in role-specific form.

The agent follows four steps:

1. Consult both knowledge bases before relying on recall.
2. Cite the chunk ids and record ids the decision rests on, in the code comment, design, doc or pull request.
3. If both are silent, or disagree with each other or with the code, say so and record a question: a BQ for a business owner or a TQ for a technical owner, with a decider; the requirements-analyst, solution-architect and documentation-curator write the record themselves, and every other agent returns it as `questions_to_record` to the calling session. Do not fill the gap with a guess.
4. Continue with whatever the gap does not block.

Silence is a finding. If a search returns nothing relevant, the agent runs `stats` to see whether the topic is covered at all, and treats the result as "the knowledge base does not say", never as permission. A conflict is handled the same way: if a chunk says 30 days and the code says 45, neither is assumed right and both are cited in a new question.

The rule covers behaviour, not craftsmanship. A conventional variable name or the standard way to validate a request needs no record. The test for any claim is whether a reviewer can follow the citation and find the same statement there; if not, the claim is an invention.

Related shared rules in `_SHARED-PATTERNS.md`: cite only ids retrieved this session, never claim tests pass without command output, and verify that any file, symbol or skill exists before citing it.
