# Readiness analysis: VS-nnn

Baseline commit: `<sha>` (date). Analyst: `<agent or person>`. Result: `Ready` / `Blocked by <ids>`.

## S1 Ground

| Question | Finding | Source |
|----------|---------|--------|
| What must the product do? | | `BC-nnn` |
| Prior decisions that apply | | `OD-nnn`, `BQ-nnn`, `TQ-nnn` |
| Silent or conflicting | | recorded as BQ/TQ |

## S2 Scope

In / out / deferred, then acceptance criteria (one per behaviour, each testable).

## S2b UX (UI slices only)

Existing design or the `ux-usability-specialist` define output: flows, states (loading, error, empty, data), microcopy.

## S3 Design

Simplest viable option; data model delta; API contract (routes, DTOs, status codes, auth); frontend components; risks; what is deferred. Rungs and files per rung.

## S4 Dependencies

| Depends on | Type (hard/soft) | Status | Conflict with open PR? |
|------------|------------------|--------|------------------------|

## S5 Decisions and blockers

| Record | Type | Decider | Blocks which rung | Resolved? |
|--------|------|---------|-------------------|-----------|

The slice is `Ready` only when no row is unresolved.

## Priority inputs

Value, Urgency, Unblocks, Effort (1-5 each) with one line of reason per score.

## Pickup delta log

| Date | Compared with | Result (unchanged / deltas) |
|------|---------------|-----------------------------|
