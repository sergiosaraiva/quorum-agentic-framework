# VS-005: Orders: align statuses to the BC-001 lifecycle (example)

Status: see [`INDEX.md`](INDEX.md) (not copied here). Owner: `tech-lead`. EXAMPLE DATA (invented "Acme Orders" domain).

## Goal

Orders carry the lifecycle states the business defines (draft, placed, paid, shipped, closed) instead of the three the first build used (open, paid, cancelled), so that later features, starting with the VS-004 status filter, speak one vocabulary.

## Grounding

| Claim | Source (chunk id or record id) |
|-------|--------------------------------|
| An order has five states: draft, placed, paid, shipped, closed | `BC-001` |
| A draft is edited freely; placing freezes lines and prices | `BC-001` |
| An order is cancelled only in draft or placed; after payment a refund is used, not cancellation | `BC-001` |
| The code's statuses are replaced by the BC-001 states in a separate VS-001 follow-up | `TQ-003`, `OD-004` |
| Enums are stored as text with a check constraint | `src/Infrastructure/CLAUDE.md` (Enums convention; not a KB record) |
| A destructive or narrowing schema change needs a recorded decision and a reviewed migration | `src/Infrastructure/CLAUDE.md`, root `CLAUDE.md` Immutable Rule 2 (not KB records) |

Gaps (non-blocking, working assumptions below): how legacy rows and new orders map to BC-001 (`TQ-010`, answered by `OD-007`); how a cancelled order is represented, since BC-001 has no such state (`BQ-009`, product owner).

## Acceptance criteria

| # | Given / when / then | Test |
|---|---------------------|------|
| 1 | Given the migration, when applied to a database holding `open` and `paid` rows, then they become `draft` and `paid` and no other column changes | integration (own container, migrate to `InitialCreate`, insert, migrate forward) |
| 2 | Given a `cancelled` row, when the migration runs, then it fails with a message citing `BQ-009`, nothing is changed and the migration is not recorded as applied | integration |
| 3 | Given the migrated database, when a row with any of the five BC-001 states is inserted, then it is accepted; `open`, `cancelled`, a wrongly cased value and an empty string violate `ck_order_status` | integration |
| 4 | Given the migration is reverted, then draft and placed rows become `open`, and paid, shipped and closed rows become `paid` (lossy, documented) | integration |
| 5 | Given `POST /api/orders`, when an order is created, then its status is `draft` and `GET` returns it | integration |
| 6 | Given the status vocabulary, then it is defined once (`OrderStatuses.All`, BC-001 order) and the check constraint is generated from it | unit |
| 7 | Given the model, then `dotnet ef migrations has-pending-model-changes` reports no changes | command |

## Scope

In: the five-state vocabulary in `Infrastructure` (constants), the check constraint, the data-mapping migration, the create default, tests, the frontend test fixture. Out: transitions (placing, paying, shipping, closing; BC-001 transition rules and the recorded timestamp and acting user), cancellation (`BQ-009`), a status field in `CreateOrderRequest`, the status filter itself (`VS-004` R2). Deferred: transition endpoints and the state-change audit trail, until a slice asks for them.

## Design

| Layer | Change |
|-------|--------|
| Data | `OrderStatuses` constants (`src/Infrastructure/Persistence/Entities/Order.cs`); `ck_order_status` generated from `OrderStatuses.All`; migration `AlignOrderStatusesToBc001`: drop constraint, abort if a `cancelled` row exists, `open` -> `draft`, add the new constraint. `status` stays `varchar(20)` (the longest value is 7 characters) |
| API | `OrdersService.CreateAsync` writes `draft`; the response shape is unchanged (`status` is still a string) |
| Frontend | none in code: the component renders `status` as text and models it as `string`; the unit-test fixture uses `draft` |
| Ops | the migration is applied by the deploy job, not at API startup (Infrastructure guide); it needs review before a shared environment |

Simplest option chosen: string constants beside the entity (Infrastructure cannot reference Api, and Api needs them for the default and for the R2 filter), one migration. Rejected: a C# enum with a value converter (a converter, a mapping table for the text values and no consumer needing more than strings); a transitional constraint accepting both vocabularies (a two-step rollout is only needed if old and new API versions share a database, see `TQ-010`, `OD-007`); a `Domain` project (none exists, no logic to hold).

Mapping (decided in `OD-007`; `BQ-009` open):

| Old | New | Reason |
|-----|-----|--------|
| `open` | `draft` | an `open` row has only a name and a total and nothing says it was placed; `placed` would claim frozen lines and prices (BC-001) that nothing enforced |
| `paid` | `paid` | exact match |
| `cancelled` | migration aborts | BC-001 has no cancelled state; `closed` would claim delivery or refund and a settled invoice. No code path ever wrote `cancelled`, so none is expected; an abort loses nothing and invents nothing |
| new order | `draft` | BC-001: a draft is edited freely |

Down: draft and placed -> `open`, paid, shipped and closed -> `paid`; information is lost by necessity (five states into three).

## Dependencies

Hard: `VS-001` (the orders entity and endpoints; still `In progress` in `INDEX.md`; waived by `OD-008`). Soft: none. Dependents: `VS-004` R2.

## Rungs

| Rung | Files | PR |
|------|-------|----|
| R1 (single rung: the slice is small) | `src/Infrastructure/Persistence` (entity constants, configuration), `src/Infrastructure/Migrations/*AlignOrderStatusesToBc001*`, `src/Api/Features/Orders/OrdersService.cs`, `tests/Api.IntegrationTests` (migration, endpoint, seed), `tests/Api.UnitTests`, frontend spec fixture, this file, `INDEX.md`, question records | - |

## Revision log

| Date | Change |
|------|--------|
| 2026-11-20 | Spec and readiness analysis created; implementation on branch `feat/vs005-vs004-r2`; `TQ-010`, `BQ-009` recorded (code-engineer and requirements-analyst; independent review pending) |
| 2026-11-20 | Owner decisions: `TQ-010` answered (`OD-007`), dependency waiver (`OD-008`); `BQ-009` stays open, non-blocking (code-engineer) |

---

# Readiness analysis: VS-005

Baseline commit: `2a74f27` (2026-11-20, `main`, branch `feat/vs005-vs004-r2`). Analyst: `requirements-analyst` role (done in the same session as the build; independent reviewers run afterwards). Result: `Ready` (no blocking record; `TQ-010` answered by `OD-007`, dependency waived by `OD-008`, `BQ-009` open and non-blocking). The KB MCP tools were not used; the same sources were read from `kb/chunks` and `questions/records`.

## S1 Ground

| Question | Finding | Source |
|----------|---------|--------|
| What must the product do? | Five states in a fixed lifecycle; cancellation only in draft or placed; no state for a cancelled order; the initial state is not named | `BC-001` |
| Prior decisions that apply | Align the code to BC-001 in a follow-up | `TQ-003`, `OD-004` |
| Silent or conflicting | Silent: legacy-row mapping, the initial state, the representation of cancellation. Conflict (resolved by `OD-004`): code statuses vs BC-001 | `TQ-010`, `BQ-009` |

Landed code facts (not KB): status is a `varchar(20)` text column with `ck_order_status` (`open`, `paid`, `cancelled`); the only writer sets `open`; no code path sets `paid` or `cancelled`; the frontend shows the status as text.

## S2 Scope

See the spec above. Assumptions (flagged): the mapping table; no transition behaviour is built, so a `placed`, `shipped` or `closed` order cannot yet occur through the API.

## S2b UX

Not applicable: the component prints the status string; no new design.

## S3 Design

See the spec above. Risks: an irreversible mapping (Down is lossy; take a backup before a shared environment); old API instances writing `open` after the migration would fail the constraint (a deploy-order concern: migrate first, then start the new API; side-by-side old and new instances need a two-step rollout, `OD-007`); an unexpected `cancelled` row stops the migration by design.

## S4 Dependencies

| Depends on | Type (hard/soft) | Status | Conflict with open PR? |
|------------|------------------|--------|------------------------|
| VS-001 | hard | `In progress` in `INDEX.md`; the entity and endpoints exist in code; waived for VS-005 by `OD-008` | none known; the branch `feat/trial-e11-f4-a4-vs004r2-vs005` was not inspected and may touch the same ids and files |

## S5 Decisions and blockers

| Record | Type | Decider | Blocks which rung | Resolved? |
|--------|------|---------|-------------------|-----------|
| TQ-003 | TQ | tech-lead | the slice itself | yes, `OD-004` |
| TQ-010 | TQ | tech-lead | none | yes, `OD-007` |
| OD-008 | OD | product-owner | pickup (hard dependency VS-001 not `Done`) | yes, exception for VS-005 and VS-004 R2 only |
| BQ-009 | BQ | product-owner | none (migration aborts on a cancelled row; no filter value for it) | no, non-blocking |

## Priority inputs

Value 3, Urgency 3, Unblocks 1, Effort 2, as scored in `INDEX.md` (priority 6.50): needed by the VS-004 status filter; small, one migration.

## Pickup delta log

| Date | Compared with | Result (unchanged / deltas) |
|------|---------------|-----------------------------|
| 2026-11-20 | `main` `2a74f27` (first analysis, written with the build) | n/a. Hard dependency VS-001 is `In progress`: the guide's rule (a slice cannot start while a hard dependency is below `Done`) is not met by itself; the owner waived it for VS-005 and VS-004 R2 on 2026-11-20 (`OD-008`, pattern of `OD-006`). Mapping and deploy order decided in `OD-007` |
