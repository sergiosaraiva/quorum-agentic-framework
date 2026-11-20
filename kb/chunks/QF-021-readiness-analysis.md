---
chunk_id: QF-021
title: Slice readiness analysis steps S1 to S5 and the pickup delta check
topics: [slices, planning]
links: [QF-020, QF-022, QF-014]
sources: ["docs/slices/IMPLEMENTATION-GUIDE.md", "docs/slices/templates/readiness-analysis.md", "docs/concepts/06-vertical-slices-and-planning.md"]
---
Before a Quorum slice is built it gets a readiness analysis, done by requirements-analyst and then solution-architect and recorded with the template `docs/slices/templates/readiness-analysis.md`.

| Step | Question | Output |
|------|----------|--------|
| S1 Ground | What do the knowledge bases say and what was already decided | Cited chunk and record ids, gaps listed |
| S2 Scope | What is in, out and deferred | One acceptance criterion per behaviour |
| S2b UX | Does a design exist (UI slices only) | Flows and states, or a define pass by ux-usability-specialist |
| S3 Design | Simplest design, data-model delta, API contract, risks | Rungs and files per rung, written once in the slice spec; the analysis links to it |
| S4 Dependencies | Hard and soft dependencies, conflicts with open pull requests | `Depends on` column and graph updated |
| S5 Decide | Open BQ or TQ records and the rung each blocks | Each recorded with a decider; `Ready`, or `Ready for <rung>`, when no unresolved record blocks that rung |

Status moves `Proposed`, `Analysed`, `Ready`, `In progress`, `Done`. Each analysis records a baseline stamp, the commit it was written against.

The pickup delta check runs before starting a slice or rung analysed earlier. It compares the baseline with `HEAD`: new commits touching the slice's paths, open or merged pull requests for the same slice id or files (a sibling session may already have built it), and changes to the knowledge-base chunks and records the slice cites. The result, `unchanged` or a list of deltas, goes in the revision log, and a material delta moves the slice back to `Analysed`. The revision log is append-only: earlier rows are never edited.

A blocker is an open question with no recorded working assumption that the slice cannot proceed without (confirmed in OD-022). A question can block one rung only, such as the service rung, while the entity and migration rung proceeds; the result is then `Ready for <rung>`.
