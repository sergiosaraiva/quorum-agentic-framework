---
name: implementing-vertical-slice-features
description: "Implements a full feature as a vertical slice, end to end: entity, migration, DTOs, service, endpoint, backend tests, Angular API client, component, frontend tests and docs, in the order that prevents broken imports. Use when building a brand-new feature that spans database, API and Angular, or when planning the file sequence of a slice."
---

# Implementing Vertical Slice Features

Design Principles: `.claude/agents/_SHARED-PATTERNS.md`. A slice is the smallest set of files that delivers the stated requirement; each row below is conditional on the feature needing it.

## Quick Reference

Sequence: **Entity -> Migration -> DTOs/validation -> Service -> Endpoint -> Backend tests -> Angular API client -> Component/state -> Angular tests -> CLAUDE.md update**

Never reorder: a service cannot be written against a DTO that does not exist yet; a component cannot be written against a client that does not exist yet. Documentation describes what was built, so it is written last.

Before the Entity step: ground behaviour in the KBs (`business-kb`, `qa-kb`), cite chunk and record ids, and record a BQ/TQ question when they are silent or conflict. For a new or redesigned screen, an approved UX definition comes first (`ux-usability-specialist`). Slice ids, dependencies and rung status live in `docs/slices/INDEX.md`; read `docs/slices/CLAUDE.md` before slice work and update the slice status in the same PR.

## When to Use / Not Use

| Use | Do not use |
|-----|------------|
| New feature touching database + API + Angular | Bug fix (touch only the broken layer) |
| 3+ layer skills apply to the planned files | One field added to an existing slice (extend its files) |
| A feature whose slice delivers only some layers (for example backend only): use the rows it needs, see "Partial slices" | A change to existing files that adds no new feature (extend them) |

## The Sequence

| # | File | Skill | Why this order |
|---|------|-------|----------------|
| 1 | `src/Infrastructure/Persistence/Entities/<Schema>/<Entity>.cs` | `database` | Nothing downstream can reference a missing type |
| 2 | `.../Configurations/<Schema>/<Entity>Configuration.cs` + migration | `database`, `writing-postgresql-migrations` | Shape follows the entity |
| 3 | `src/Api/Features/<Feature>/Dtos.cs` | `creating-dtos-and-validation` | The service needs request/response shapes |
| 4 | `src/Api/Features/<Feature>/<Feature>Service.cs` | `creating-application-services` | The endpoint delegates to it |
| 5 | `src/Api/Features/<Feature>/<Feature>Endpoints.cs` | `backend` | Route registration once the service exists |
| 6 | `tests/Api.IntegrationTests/<Feature>Endpoints*Tests.cs` (one or more files named for the behaviour, for example `OrdersEndpointsTests.cs`, `OrdersSearchTests.cs`; + unit tests only for logic separable from the database) | `writing-integration-tests`, `creating-xunit-tests` | Backend proven before the frontend consumes it |
| 7 | `frontend/src/app/core/api/<resource>.api.ts` | `creating-angular-api-clients` | The component needs a typed client |
| 8 | `frontend/src/app/features/<feature>/` (+ a signal store only if state is shared across unrelated components) | `frontend`, `managing-state-with-signals` | Built on the existing client |
| 9 | `frontend/**/*.spec.ts` | `writing-angular-tests` | Tests the finished component |
| 10 | Root or sub-`CLAUDE.md`, slice status | `updating-internal-docs` | Documents what was built |

Invoke each named skill when you reach its step; the table is a routing pointer, not a substitute for its rules.

## Partial slices

A slice spec (`docs/slices/`) may deliver only some layers. Keep the order and drop the rows the spec does not deliver; do not add a layer to fill the table.

| Slice delivers | Rows to run | Notes |
|----------------|-------------|-------|
| Backend only (for example VS-004 R1) | 1 to 6, 10 | Row 1 and 2 only if the schema changes. The API contract (DTOs, routes, error shape) is the hand-off to a later frontend slice; record it in the slice spec |
| Frontend only | 7 to 10 | The backend contract must already exist; read its DTOs before the client (`verifying-cross-file-coupling`) |

Whole-feature requests from the agents route here either way (`.claude/agents/code-engineer.md`).

## Example

```
Feature: "Team invites" - a user invites a teammate by email.
1. TeamInvite.cs (Id, Email, Status, ExpiresAt)
2. TeamInviteConfiguration.cs + migration AddTeamInvite
3. Dtos.cs: CreateInviteRequest(Email), InviteDto(Id, Email, Status, ExpiresAt)
4. TeamInviteService (concrete): CreateAsync, ListPendingAsync
5. TeamInviteEndpoints: POST / and GET / under /api/invites, RequireAuthorization("invites:write")
6. TeamInviteEndpointTests: create 201, invalid email 400, anonymous 401
7. core/api/invites.api.ts
8. features/invites/invite-list.ts + invite-form.ts (loading, error, empty and data states)
9. invite-list.spec.ts
10. Update the Api CLAUDE.md feature table and docs/slices/INDEX.md
```

## Quality Checklist

- [ ] Order respected; every layer the feature needs exists, none it does not
- [ ] Each step used its skill's rules (auth decision, validation, `HasPrecision`, no `any`, OnPush)
- [ ] DTO shape and TypeScript interface agree (`verifying-cross-file-coupling`)
- [ ] Migration reviewed; tests green; slice status updated

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Component first against an imagined API | Client from the real DTOs first |
| Whole sequence re-run for a one-field change | Extend existing files |
| Docs written as a plan before code | Docs written last, from what exists |
| Skipping KB grounding for business rules | Cite ids or record a question |

## Related Skills

`routing-to-skills`, `backend`, `database`, `frontend`, `writing-integration-tests`.
