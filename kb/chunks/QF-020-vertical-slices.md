---
chunk_id: QF-020
title: Vertical slices, ids, rungs and the dependency graph
topics: [slices, planning]
links: [QF-021, QF-022, QF-003]
sources: ["docs/concepts/06-vertical-slices-and-planning.md", "docs/slices/IMPLEMENTATION-GUIDE.md", "docs/slices/INDEX.md", "docs/slices/CLAUDE.md"]
---
Quorum plans and builds software as vertical slices. A slice cuts through every layer for one user-visible capability: entity, migration, service, endpoint, Angular client, component and tests, so each slice ends with something a user can try. A layered plan builds all entities, then all services, then all screens, so nothing works until the end and mistakes surface late.

Ids and status: slices are numbered `VS-001`, `VS-002` and so on, never reused or renumbered; check open pull requests and sibling branches before taking the next id. The single status source is the table in `docs/slices/INDEX.md`, with states `Proposed`, `Analysed`, `Ready`, `In progress`, `Done` and `Blocked`. Every code pull request updates the INDEX in the same change (state, last rung merged, pull request link), and a pull request number is never predicted; open the pull request first, then record it.

Rungs are small, independently mergeable pull requests:

| Rung | Content | Gate |
|------|---------|------|
| R0 | Spec and readiness analysis merged | Slice `Ready` |
| R1 | Entity, configuration, migration | Migration reviewed |
| R2 | Service and endpoints with tests | Tests green |
| R3 | Angular client and component with loading, error, empty and data states | Frontend tests green |
| R4 | End-to-end journey, observability, docs | Slice `Done` |

A small slice may need fewer rungs. Small pull requests matter because AI review quality and tool limits degrade on large diffs.

Dependencies: each slice lists its hard dependencies, which must be `Done` first, and the Mermaid dependency graph in section 2 of the INDEX is updated when a dependency changes. The longest chain is the critical path.
