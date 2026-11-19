# VS-nnn: <slice name>

Status: see [`../INDEX.md`](../INDEX.md) (not copied here). Owner: `<role>`.

## Goal

One or two sentences in business terms: who can do what that they could not before.

## Grounding

| Claim | Source (chunk id or record id) |
|-------|--------------------------------|
| `<behaviour>` | `BC-nnn` / `OD-nnn` |

Gaps: list each as a BQ/TQ with its decider. If none, write "none".

## Acceptance criteria

| # | Given / when / then | Test |
|---|---------------------|------|
| 1 | | unit / integration / e2e |

## Scope

In: ... Out: ... Deferred (and why): ...

## Design

| Layer | Change |
|-------|--------|
| Data | entities, migration |
| API | endpoints, DTOs, auth policy |
| Frontend | components, states |
| Ops | config, alarms |

Simplest option chosen and why each extra layer is needed (or "none").

## Dependencies

Hard: `VS-...`. Soft: `VS-...`.

## Rungs

| Rung | Files | PR |
|------|-------|----|
| R1 | | |

## Revision log

| Date | Change |
|------|--------|
