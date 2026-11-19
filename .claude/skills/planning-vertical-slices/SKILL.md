---
name: planning-vertical-slices
description: Builds a plan as vertical slices - each slice a user-visible outcome cutting through every layer, with an id (VS-NNN), dependencies, readiness analysis, priority score, PR-sized rungs, critical path and an INDEX status table. Use when planning a feature or release, breaking a spec into work, ordering the backlog, or deciding whether a slice is ready to build. Not for implementing a slice (implementing-vertical-slice-features) or recording questions (recording-decisions).
---

# Planning vertical slices

A slice delivers one user-visible outcome end to end: entity, migration, service, endpoint, Angular client, component, tests. Never plan by layer ("all the tables first").

## Artifacts

| Artifact | Path |
|----------|------|
| Status table, dependencies, priority | `docs/slices/INDEX.md` |
| Process rules, ladder, PR budget | `docs/slices/IMPLEMENTATION-GUIDE.md`, `docs/slices/CLAUDE.md` |
| One slice spec | `docs/slices/templates/slice.md` (copy to `docs/slices/VS-nnn-<name>.md`) |
| Readiness record | `docs/slices/templates/readiness-analysis.md` |

## Slice definition

| Field | Content |
|-------|---------|
| Id | `VS-001`, next free; never reuse (check open PRs and sibling branches first) |
| Outcome | One sentence: who can do what that they could not before |
| Layers touched | Data, API, UI, infra, jobs; each with the change |
| Depends on | Other slice ids or external items; no cycles |
| Grounding | Business KB chunk ids and record ids the behaviour rests on |
| Acceptance | Observable checks, including empty and error states |
| Rungs | Ordered PR-sized increments, each independently mergeable |

Slice too big (more than ~6 rungs or two outcomes)? Split. A slice with no user-visible outcome is a task inside another slice.

## Readiness analysis (before any code)

| Check | Pass condition |
|-------|----------------|
| Spec grounded | Every behaviour cites a `business-kb` chunk or a decided record; silence is a BQ, not a guess |
| Open questions | None blocking; each open BQ/TQ has a decider and a working assumption (`recording-decisions`) |
| Data model ready | Entities, keys, constraints, tenancy and migration approach known |
| UX defined | Flows, states (loading, empty, error, data), microcopy, acceptance criteria; mockup approved if the screen is new |
| Contracts | Request/response DTOs, errors, auth decision per endpoint, Angular client shape |
| Test strategy | Unit, integration, e2e, and any performance or mutation gate named |
| Security and infra | Auth, secrets, new AWS resources identified (`security-engineer`, `cloud-infrastructure-engineer`) |

Steps S1..S5 are defined in `docs/slices/IMPLEMENTATION-GUIDE.md` section 4. Result: `Ready` (zero open blockers), or `Blocked` with each blocker, owner and record id. Stamp the analysis with the baseline commit; at pickup, diff the baseline against current main (delta check) and re-analyse if the area changed.

## Priority scoring

`priority = (2*Value + 2*Urgency + Unblocks) / Effort` (as in `docs/slices/IMPLEMENTATION-GUIDE.md` section 5). Inputs are integers 1-5 (Unblocks 0-5); the score is computed, not guessed.

| Factor | Meaning |
|--------|---------|
| Value | Business benefit |
| Urgency | Cost of delay |
| Unblocks | How many other slices wait on it |
| Effort | Relative size: rungs and uncertainty |

The highest priority among `Ready` slices whose hard dependencies are `Done` is picked first; ties go to the slice that unblocks more. Dependencies override score.

## Rungs and critical path

- A rung is one PR: small, reviewable, green on its own, unreachable or flagged off until complete if partial.
- Order rungs data -> service -> endpoint -> client -> UI -> hardening, each with its tests.
- Critical path = longest dependency chain by rungs; schedule it first and protect it. List it in `INDEX.md`.
- Draw the dependency graph (Mermaid `graph LR`) in `INDEX.md`.

## INDEX status table

| Id | Slice | Depends on | Value | Urgency | Unblocks | Effort | Priority | Readiness | Status | Rung | PR |
|----|-------|------------|-------|---------|----------|--------|----------|-----------|--------|------|----|

Status: `Proposed`, `Analysed`, `Ready`, `In progress`, `Done`, `Blocked`. Every code PR updates its slice row and rung.

## Workflow

1. `requirements-analyst` extracts outcomes from the spec and records gaps.
2. `solution-architect` cuts slices, sets dependencies and rungs, scores priority.
3. Run the readiness analysis per slice; record blockers.
4. Fill `INDEX.md`; hand the first `ready` slice to the pipeline.
