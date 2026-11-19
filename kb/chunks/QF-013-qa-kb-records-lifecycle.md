---
chunk_id: QF-013
title: Questions and decisions records: BQ, TQ, OD and their lifecycle
topics: [qa-kb, decisions]
links: [QF-014, QF-015, QF-017]
sources: ["docs/concepts/03-questions-and-decisions-kb.md", "questions/README.md", "scripts/kb/lib.py", "scripts/kb/check_chunks.py"]
---
The Quorum questions-and-decisions knowledge base holds one Markdown file per record in `questions/records/`. Its purpose is that a question is asked once, an answer is never lost in a chat, and a later session cannot contradict a decision it never saw.

| Prefix | Kind | Raised about | Decided by |
|--------|------|--------------|------------|
| BQ | Business question | Behaviour, rules, scope, priorities | The business or product owner |
| TQ | Technical question | Architecture, tooling, data model, infrastructure | The technical lead |
| OD | Decision | A choice that changes what gets built, including conflicts between sources | The role named in the record |

Frontmatter fields are `id`, `kind`, `title`, `status`, `decider`, `priority` (`P1` blocks work, down to `P3`), `asked`, optional `answered`, `related` (record ids) and `chunks` (business chunk ids). The lint in `scripts/kb/check_chunks.py` accepts exactly the kinds BQ, TQ and OD, requires the id prefix to match the kind, and requires related and chunk ids to resolve.

There are exactly four statuses: `open`, `answered`, `decided` and `closed`. A record that is `answered` or `decided` must contain an `## Answer` or `## Decision` section.

Lifecycle: an agent records a question as `open`; the decider answers it, making it `answered`; an answer that changes scope or design becomes a decision, `decided`; once applied to chunks or code it is `closed`. Applying an answer means documentation-curator updates the affected chunks and code changes follow through the normal pipeline.

Supersession uses no extra status. When a later decision replaces an earlier one, the old record becomes `closed` and gains a line "Superseded by <id>" under `## History`, which points readers to the live record. Records are never deleted.
