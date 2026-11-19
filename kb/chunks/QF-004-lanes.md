---
chunk_id: QF-004
title: Quorum lanes: full, iterate, trivial and spike
topics: [pipeline, process]
links: [QF-003, QF-016, QF-026]
sources: [".claude/agents/_SHARED-PATTERNS.md", "docs/concepts/01-overview-and-pipeline.md"]
---
Quorum scales process to risk with four lanes, all defined in `.claude/agents/_SHARED-PATTERNS.md`. The orchestrating session names the lane in its one-line pipeline statement before it starts.

| Lane | When | Stages |
|------|------|--------|
| Trivial | A one-line fix or typo with no behaviour change | Edit directly; no review gate; normal CI still runs |
| Iterate | Small, low-risk, reversible change in one slice, with no new contract, no migration and no auth, data or infrastructure change | code-engineer; the review pair at the gate before push; test-automator only for behaviour no test covers |
| Full | Anything else: a new feature, a contract change, a migration, authentication, a multi-layer change | Every stage of the pipeline, each skippable only with a stated reason |
| Spike | The owner explicitly asks for a throwaway exploration | Local only, no review, never merged; the code is discarded or rebuilt through the Full lane |

Iterate batches one review pair per batch of changes instead of per change, and always runs cheap checks such as build, format and affected tests. A change that touches migrations, entity changes, authentication or authorization, tenancy, integrity safeguards or secrets goes back to the Full lane. The size threshold is an example that an adopting team tunes: about 150 added lines and 5 files.

Never waived in any lane: the Immutable Rules in the root `CLAUDE.md` and the grounding rule. Outside the Trivial lane (no review gate) and the Spike lane (never merged), every change also passes the review pair and the local AI review, and the GitHub AI review when `ANTHROPIC_API_KEY` is set.
