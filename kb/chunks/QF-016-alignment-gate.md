---
chunk_id: QF-016
title: The pre-development alignment gate
topics: [grounding, process, gate]
links: [QF-015, QF-012, QF-014, QF-006]
sources: [".claude/agents/_SHARED-PATTERNS.md", "docs/concepts/04-never-invent.md"]
---
The pre-development alignment gate checks the specification against the current knowledge bases before the first line of a change to `src/`, `frontend/src/` or `tests/` that implements specified behaviour. It runs once per change, because the knowledge base can change while work is queued.

| Step | Action |
|------|--------|
| 1 Scope | List the spec parts the change implements, with every cited `chunk_id` |
| 2 Re-fetch | `chunk` each cited id; `search` and `graph_traverse` for new or changed chunks; `stats` to judge silence |
| 3 Recall | Search the Q&A knowledge base for recorded decisions and answers on the topic |
| 4 Classify | Confirmed, Contradicted, KB silent or Missing |
| 5 Resolve | Contradicted or Missing: stop the affected change and return all items to the session, which routes a spec fix or asks the owner in one batch. A recorded owner decision settles it. KB silent: proceed and mark "unverified in KB". Never implement against a known conflict |
| 6 Record | The alignment result lists chunk ids, conflicts, silences and recalled record ids, or `none found` with the queries. Until a pull request exists it travels in each review prompt and is kept in the slice spec or the session hand-off; the pull request description then carries it in an `Alignment check` section |

The gate does not apply to changes that touch only `.github/`, `scripts/`, `.claude/`, `docs/`, build files, Dockerfiles or generated output; those state "Not applicable" with a reason.

Roles: requirements-analyst and solution-architect run steps 1 to 5 during analysis and design. code-engineer runs the gate first on every in-scope change, unless the session passes a result produced this session for this change. test-automator has the same duty when only tests change. quality-guardian verifies the chunk-id claims in a passed result, and treats a missing result for an in-scope change as a High finding, which blocks.
