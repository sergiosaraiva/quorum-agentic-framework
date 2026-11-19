# VS-004: Order search and filters (example)

Status: see [`INDEX.md`](INDEX.md) (not copied here). Owner: `product-owner`. EXAMPLE DATA (invented "Acme Orders" domain).

## Goal

A user of the orders list can narrow it down by criteria and find an order without paging through everything.

## Grounding

| Claim | Source (chunk id or record id) |
|-------|--------------------------------|
| An order has a lifecycle status, a customer, a total and one currency | `BC-001`, `BC-005` |
| Money is `numeric(18,2)` plus a currency code | `OD-001` |
| List endpoints take `page` and `pageSize`, clamp to a configured maximum | `src/Api/CLAUDE.md` (Pagination convention; not a KB record) |

Decided 2026-11-19: filters are status, created-date range and customer name, no amount filter (`BQ-003`, `OD-002`); customer name is a case-insensitive substring match (`BQ-004`, `OD-003`); order statuses are aligned to BC-001 in follow-up `VS-005` (`TQ-003`, `OD-004`).

Open, non-blocking (working assumptions): sort order `BQ-005`, visibility `BQ-006`, currency for a deferred amount filter `TQ-004`.

## Acceptance criteria

| # | Given / when / then | Test |
|---|---------------------|------|
| 1 | Given orders exist, when `GET /api/orders` is called with no filter, then the response equals the VS-001 list (same order, paging, total) | integration |
| 2 | Given a filter that matches nothing, when listed, then 200 with empty `items` and `totalCount` 0 | integration |
| 3 | Given several filters, when combined, then only orders matching all of them are returned (assumption, see readiness S2) | unit + integration |
| 4 | Given a filter, when paged, then `totalCount` counts the filtered set and `pageSize` is clamped as in VS-001 | integration |
| 5 | Given an invalid filter value (unparseable date, from after to, unknown status), then 400 problem details | integration |
| 6 | Given no credentials, then 401 (group auth inherited) | integration |
| 7 | R1: given orders created on different dates, when a created-date range (from, to, both optional) is given, then only orders created in the range are returned, bounds inclusive | unit + integration |
| 8 | R1: given a customer-name text, when searched, then orders whose name contains it, ignoring case, are returned (`OD-003`); special characters are matched literally | unit + integration |
| 9 | R2: given a status, when filtered, then only orders in that BC-001 state are returned; an unknown status gives 400 (needs `VS-005`) | unit + integration |

## Scope

In: backend filtering of the existing order list (query parameters). Out: frontend, amount filter (`OD-002`, `TQ-004`), selectable sorting (until `BQ-005`), per-caller visibility changes (`BQ-006`). Deferred: database indexes for the chosen filters, until the filter set is decided and a query shows a need.

## Design

See the readiness analysis S3 below; the R1 design is in "S3 Design: R1 (solution-architect)".

| Layer | Change (R1) |
|-------|-------------|
| Data | no schema or model change, no migration; one constant `Order.CustomerNameMaxLength` added to `Order` |
| API | `GET /api/orders` gains optional `createdFrom`, `createdTo`, `customerName`; 400 validation problem details; auth inherited from the group |
| Frontend | none (out of scope) |
| Ops | none: no new configuration key, no new alarm |

Simplest option chosen: filter the existing `IQueryable` in `OrdersService.ListAsync` before the count. Extra layers, abstractions or config: none beyond one parsed-filter record (`OrderListFilter`), which carries validated values from the endpoint to the service.

## Dependencies

Hard: `VS-001` (all rungs); `VS-005` (rung R2 only, the status filter). Soft: none.

## Rungs

| Rung | Files | PR |
|------|-------|----|
| Docs | this file, `INDEX.md`, question records (spec and readiness, merged first) | - |
| R1 | date-range and customer-name filters: `src/Api/Features/Orders/` (service, endpoint, DTO), tests | - |
| R2 | status filter on the BC-001 states, after `VS-005` lands: same folder, tests | - |

## Revision log

| Date | Change |
|------|--------|
| 2026-11-19 | Spec and readiness analysis created (requirements-analyst, trial) |
| 2026-11-19 | Owner answers recorded (`OD-002`, `OD-003`, `OD-004`); slice split into R1 (date range, customer name) and R2 (status filter, after `VS-005`); criteria 7-9 written |
| 2026-11-19 | R1 design added under S3 "S3 Design: R1 (solution-architect)" and the Design table filled; `TQ-005`, `TQ-006` raised (non-blocking); a time-zone BQ returned to the session to record (solution-architect, trial) |
| 2026-11-19 | `BQ-007` recorded and answered (`OD-005`, UTC days), so the date assumption is a recorded decision; `OD-006` records the pickup exception for R1 (requirements-analyst, trial) |
| 2026-11-19 | R1 implemented (date-range and customer-name filters, unit and integration tests); status In progress in `INDEX.md`; rung and PR stay `-` until merge (code-engineer, trial) |

---

# Readiness analysis: VS-004

Baseline commit: `f1b0adc` (2026-11-19, branch `feat/pipeline-trial-slice`, clean tree). Analyst: `requirements-analyst`. Result: `Ready` for R1 (date-range and customer-name filters); R2 (status filter) is `Blocked by VS-005`. Updated 2026-11-19 after the owner answers; the first analysis result was `Blocked by BQ-003, BQ-004, TQ-003`. Steps S1, S2, S3 (requirements-level), S4, S5 done; S2b not applicable. The KB MCP tools were unavailable in this session; the same sources were read from `kb/chunks` and `questions/records` and via `scripts/kb/search.py`.

## S1 Ground

| Question | Finding | Source |
|----------|---------|--------|
| What must the product do? | Orders have five states (draft, placed, paid, shipped, closed); one currency per order; amounts have two decimals. No chunk mentions search, filtering, sorting or page size (searches: "order search filter", "list orders page size", "sort order", "text search customer"; `stats`: 39 chunks, none on listing) | `BC-001`, `BC-004`, `BC-005` |
| Prior decisions that apply | Money type and rounding (`OD-001`). No record on search, filters or sorting (qa search "search filter orders"; open records: BQ-001, TQ-001) | `OD-001` |
| Silent or conflicting | Silent: filterable fields, text semantics, sort order, visibility. Conflict: code statuses `open/paid/cancelled` vs `BC-001` states. Gap: no currency column vs `BC-005` | `BQ-003`, `BQ-004`, `BQ-005`, `BQ-006`, `TQ-003`, `TQ-004` |

Landed VS-001 facts (code, not KB): `GET /api/orders?page&pageSize` returns `PagedResponse` sorted by `CreatedAt` desc then `Id`; paging via `OrdersOptions` (default 20, max 100); group `RequireAuthorization()`; order has `CustomerName`, `TotalAmount`, `Status`, `CreatedAt`; index `ix_order_created_at`.

## S2 Scope

See the spec above. Assumptions (safe, flagged): filters combine with AND; additive optional query parameters on the existing route, so no new endpoint and no change when none is given; filtered `totalCount`; invalid filter values give 400 problem details (`src/Api/CLAUDE.md` Errors); no frontend.

## S2b UX

Not applicable (backend only in this trial).

## S3 Design

Simplest viable option: extend `OrdersService.ListAsync` with an optional filter object applied to the `IQueryable` before the count, and bind it from query parameters in the existing endpoint; no new project, layer or interface. Data model delta: none until indexes are justified (a migration would then be needed and reviewed, Immutable Rule 2). API: `GET /api/orders` plus optional parameters for the three filters; 200, 400 (problem details), 401; auth inherited from the group. Risks: the status vocabulary changes under `VS-005`, so R2 must not be built on the old values; a case-insensitive substring match cannot use a plain b-tree index and may need a trigram index on a large table (`OD-003`); text must be escaped so `%` and `_` match literally; visibility (`BQ-006`) may add auth work. Page size and filter limits come from `OrdersOptions`, not literals (Design Principle 3). Rungs: R1 (date range, customer name) and R2 (status filter, after `VS-005`), each service, endpoint and tests; an index, if justified, needs its own reviewed migration. Skills: `backend`, `creating-dtos-and-validation`, `creating-application-services`, `writing-integration-tests`. Deferred: indexes, sorting, amount filter, frontend.

### S3 Design: R1 (solution-architect)

Designed 2026-11-19 against baseline `f1b0adc` plus the uncommitted VS-004 records. Scope: acceptance criteria 1-8; criterion 9 (status filter, R2) is out of scope.

Pipeline: full lane (new query contract on an API) · requirements-analyst done (readiness above) · ux-usability-specialist skip (no UI) · code-engineer -> quality-guardian || regression-detective -> test-automator · security-engineer applies (user input reaches a query; see Security notes) · infrastructure-engineer skip (no resource) · docs: this spec and the `INDEX.md` row in the R1 PR · Alignment Gate: applies (`src/`, `tests/`).

Pickup condition: `docs/slices/CLAUDE.md` says a slice cannot start while a hard dependency is below `Done`, and `VS-001` is `In progress` in `INDEX.md`. The owner granted an exception for R1 on the landed list endpoint (`OD-006`). It does not cover R2.

#### Alignment check (steps 1-5)

| Behaviour | Source | Class |
|-----------|--------|-------|
| Filters are created-date range and customer name (R1); no amount filter | `OD-002` | Confirmed |
| Customer-name match is a case-insensitive substring | `OD-003` | Confirmed |
| Filters combine with AND; `totalCount` counts the filtered set | readiness S2 assumption | KB silent (searches "order search filter", "date range filter time zone"; `stats`: 39 chunks, none on listing) |
| Special characters match literally | criterion 8 | KB silent |
| A calendar date means a UTC day | `OD-005` (`BQ-007`) | Confirmed (was KB silent: search "created date time zone day boundary") |
| Newest first, then `Id` | landed code `OrdersService.ListAsync` | KB silent, `BQ-005` open, non-blocking |
| Any authenticated caller sees all orders | landed code, group `RequireAuthorization()` | KB silent, `BQ-006` open, non-blocking |

No Contradicted or Missing item for R1. Chunks read: `BC-001`, `BC-005` (`BC-005` currency is untouched by R1, `TQ-004`). Records recalled: `OD-002`, `OD-003`, `OD-004`, `BQ-005`, `BQ-006`, `TQ-004`. Pass this table to the R1 PR under `Alignment check`.

#### Decision summary

| Decision | Chosen | Rejected and why |
|----------|--------|------------------|
| Where filtering lives | `OrdersService.ListAsync` applies the filter to the `IQueryable` before `CountAsync`; the endpoint parses and validates | A new endpoint or search service: no second consumer; the same route with optional parameters keeps criterion 1 |
| Binding of the new parameters | `string?`, parsed by `OrderListFilter.Parse`, errors returned with `Results.ValidationProblem` | Typed `DateOnly?`: a malformed value gives a bodiless 400 in Production and a 500 in Development, and `11/19/2026` or `2026-11-19T10:00:00` are accepted silently (probe, `TQ-005`). This would fail criterion 5 |
| Date semantics | `yyyy-MM-dd` calendar dates as UTC days (`OD-005`); `created_at >= from 00:00Z` and `created_at < (to + 1 day) 00:00Z`, so both bounds are inclusive (criterion 7) | Full ISO instants (`DateTimeOffset`): the caller picks the zone, but "bounds inclusive" over instants is ambiguous, and `OD-005` fixed UTC days |
| Case-insensitive substring | `EF.Functions.ILike(o.CustomerName, pattern, "\\")` with `pattern = "%" + EscapeLikePattern(term) + "%"`; the SQL is `customer_name ILIKE @pattern ESCAPE '\'` (verified with `ToQueryString()` on Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3) | `CustomerName.ToLower().Contains(term)`: EF escapes the pattern itself (verified), but it folds the column in PostgreSQL (`lower()`) and the term in .NET, which can disagree on non-ASCII letters, and a future trigram index would have to be an expression index |
| Wildcard escaping | Escape `\` first, then `%` and `_`, each prefixed with `\` | Escaping `[`, `]`, `^` as the Npgsql XML doc for `ILike` suggests: those are SQL Server wildcards; PostgreSQL `LIKE`/`ILIKE` has only `%` and `_` |
| Length cap for `customerName` | Reject more than `Order.CustomerNameMaxLength` (200) characters: a longer term cannot match a stored name, and the cap bounds the input | A new Options key: the limit is a fact of the column, not a tunable |
| Index or migration | None. `ix_order_created_at` already serves the date range and the ordering | A `pg_trgm` GIN index for `ILIKE '%x%'`: needs `CREATE EXTENSION` and a reviewed migration; deferred until a measured query shows a need (`tuning-postgresql-queries`) |

#### Simplicity statement

| Item | Why |
|------|-----|
| `OrderListFilter` record | Carries the parsed, validated values from the endpoint to the service (one consumer, so the service never parses strings) |
| `Order.CustomerNameMaxLength` constant | The literal `200` already appears twice (`CreateOrderRequest` `StringLength`, `OrderConfiguration` `HasMaxLength`); the filter is the third use. The constant lives on the entity because `Infrastructure` cannot reference `Api`. The model does not change, so no migration |
| New project, layer, interface, Options key, dependency | none |

Deferred: trigram index (measured need); caller-selectable sort (`BQ-005`); per-caller visibility (`BQ-006`); status filter (R2, `VS-005`); typed-binding problem details for `page`/`pageSize` (`TQ-005`, a VS-001 follow-up); non-ASCII case folding independent of the database locale (`TQ-006`); frontend.

#### Contract

`GET /api/orders?page&pageSize&createdFrom&createdTo&customerName`. Auth: inherited from the `/api/orders` group `RequireAuthorization()` (Immutable Rule 7); no endpoint-level change.

| Parameter | Type on the wire | Rule | Absent or empty |
|-----------|------------------|------|-----------------|
| `page`, `pageSize` | integer | unchanged from VS-001 (`NormalizePaging`, `ComputeSkip`, `OrdersOptions`) | defaults |
| `createdFrom` | string `yyyy-MM-dd` | `DateOnly.TryParseExact(value, OrderListFilter.DateFormat, CultureInfo.InvariantCulture, DateTimeStyles.None, out _)` | null, empty or whitespace: no lower bound |
| `createdTo` | string `yyyy-MM-dd` | same parse; must not be before `createdFrom` when both are given; `9999-12-31` means no upper bound (avoids the `AddDays(1)` overflow) | null, empty or whitespace: no upper bound |
| `customerName` | string | trimmed; at most `Order.CustomerNameMaxLength` characters after trimming | null, empty or whitespace: no name filter |

Responses:

| Status | When | Body |
|--------|------|------|
| 200 | valid input | `PagedResponse<OrderResponse>` unchanged: `items`, `page`, `pageSize`, `totalCount` (the filtered count) |
| 400 | any filter value invalid | `Results.ValidationProblem(errors)`: `application/problem+json`, `title` "One or more validation errors occurred.", `status` 400, `errors` keyed by parameter name. All errors are reported at once |
| 401 | no credentials | from the group |

Error keys and messages (messages never echo the input):

| Key | Message | Trigger |
|-----|---------|---------|
| `createdFrom` | `createdFrom must be a date in the format yyyy-MM-dd.` | unparseable |
| `createdTo` | `createdTo must be a date in the format yyyy-MM-dd.` | unparseable |
| `createdTo` | `createdTo must not be before createdFrom.` | both valid, `to < from` |
| `customerName` | `customerName must be at most 200 characters.` (the number comes from the constant) | too long |

Ordering: unchanged, `CreatedAt` descending, then `Id` ascending (`BQ-005` working assumption). Filters combine with AND.

#### Implementation plan for code-engineer

| Order | Task | File | Skill | Depends on | Test |
|-------|------|------|-------|------------|------|
| 1 | Add `public const int CustomerNameMaxLength = 200;` to `Order`; use it in `HasMaxLength(Order.CustomerNameMaxLength)` | `src/Infrastructure/Persistence/Entities/Order.cs`, `src/Infrastructure/Persistence/Configurations/OrderConfiguration.cs` | `database` | - | `dotnet ef migrations has-pending-model-changes --project src/Infrastructure --startup-project src/Api` reports no changes |
| 2 | `CreateOrderRequest`: `StringLength(Order.CustomerNameMaxLength, MinimumLength = 1)`. Add `OrderListFilter` (below) | `src/Api/Features/Orders/Dtos.cs` | `creating-dtos-and-validation` | 1 | existing `Create_CustomerNameOf201Characters_ReturnsValidationProblem` stays green; unit tests U1-U5 |
| 3 | `ListAsync(int? page, int? pageSize, OrderListFilter filter, CancellationToken ct)`; add `ApplyFilter` and `EscapeLikePattern` (below); apply before `CountAsync` | `src/Api/Features/Orders/OrdersService.cs` | `creating-application-services` | 2 | U6; integration I1-I9 |
| 4 | List handler takes `string? createdFrom, string? createdTo, string? customerName`, calls `OrderListFilter.Parse`, returns `Results.ValidationProblem(errors)` on errors, else `Results.Ok(await service.ListAsync(page, pageSize, filter, ct))` | `src/Api/Features/Orders/OrdersEndpoints.cs` | `backend` | 3 | I5, I6 |
| 5 | Unit tests | `tests/Api.UnitTests/OrderListFilterTests.cs` (new) | `creating-xunit-tests` | 2, 3 | U1-U6 |
| 6 | Integration tests | `tests/Api.IntegrationTests/OrdersSearchTests.cs` (new, own `IClassFixture<ApiFactory>`) | `writing-integration-tests` | 4 | I1-I9 |
| 7 | `INDEX.md` row (status, rung) and this file's revision log | `docs/slices/INDEX.md`, this file | `updating-internal-docs` | 6 | - |

Shapes (names are binding; bodies are the code-engineer's):

```csharp
// Dtos.cs
public sealed record OrderListFilter(DateOnly? CreatedFrom, DateOnly? CreatedTo, string? CustomerName)
{
    public const string DateFormat = "yyyy-MM-dd";
    public static readonly OrderListFilter None = new(null, null, null);

    /// Parses raw query values; Errors is empty when Filter is usable. Messages never echo input.
    internal static (OrderListFilter Filter, Dictionary<string, string[]> Errors) Parse(
        string? createdFrom, string? createdTo, string? customerName);
}

// OrdersService.cs
private const string LikeEscapeCharacter = "\\";   // PostgreSQL LIKE escape; protocol constant, not a tunable
internal static string EscapeLikePattern(string term);      // "\" -> "\\", then "%" -> "\%", "_" -> "\_"
internal static IQueryable<Order> ApplyFilter(IQueryable<Order> query, OrderListFilter filter);
```

`ApplyFilter` rules:
- Compute the bounds into locals before the lambdas: `new DateTimeOffset(from.ToDateTime(TimeOnly.MinValue), TimeSpan.Zero)`. Keep the offset zero (UTC), as `CreatedAt` is stamped; the SQL probe used only zero offsets, so a non-zero offset is unverified with Npgsql.
- Skip the upper bound when `CreatedTo == DateOnly.MaxValue`.
- Build `pattern` into a local, so EF sends it as a parameter.
- No logging of filter values (see Security notes).

#### Test list (for code-engineer, test-automator and the reviewers)

Unit (`tests/Api.UnitTests/OrderListFilterTests.cs`, no database):

| Id | Test | Criterion |
|----|------|-----------|
| U1 | `Parse_AllAbsent_ReturnsNoneWithoutErrors` (null, `""`, `"  "` for each parameter) | 1 |
| U2 | `Parse_ValidDates_ReturnsDates`, including `from == to` | 7 |
| U3 | `Parse_MalformedDate_ReturnsErrorKeyedByParameter`: theory over `2026-13-40`, `19/11/2026`, `11/19/2026`, `2026-11-19T10:00:00`, `2026-1-5`, `abc`, for each of `createdFrom` and `createdTo` | 5 |
| U4 | `Parse_FromAfterTo_ReturnsCreatedToError`; `Parse_MalformedFromAndTooLongName_ReturnsBothErrors` | 5 |
| U5 | `Parse_CustomerName_TrimsAndCapsLength`: 200 characters accepted, 201 rejected (key `customerName`), `"  acme  "` gives `"acme"` | 8 |
| U6 | `EscapeLikePattern_SpecialCharacters_AreEscaped`: `50%` -> `50\%`, `a_b` -> `a\_b`, `a\b` -> `a\\b`, `\%` -> `\\\%`, `Acme` unchanged | 8 |

Integration (`tests/Api.IntegrationTests/OrdersSearchTests.cs`, real PostgreSQL).

Isolation rules:
- Seed rows through `AppDbContext` from `factory.Services.CreateScope()` with an explicit `CreatedAt`; the POST endpoint stamps the system clock.
- Each test uses a unique name token (for example `$"zq{Guid.NewGuid():N}"`) and, for tests without a name filter, its own far-past year that no other test uses.
- Use whole-microsecond times. PostgreSQL rounds to microseconds, so `23:59:59.9999999` would become the next day.
- Every 400 test asserts the status, the content type `application/problem+json`, and the `errors` key.

| Id | Test | Criterion |
|----|------|-----------|
| I1 | `List_NoFilter_ReturnsSameAsUnfilteredOrderAndTotal`: newest first, then `Id`, `totalCount` equals all rows | 1 |
| I2 | `List_FilterMatchesNothing_ReturnsEmptyItemsAndZeroTotal` | 2 |
| I3 | `List_DateRangeAndName_ReturnsOnlyOrdersMatchingBoth`: seed in-range/out-of-range by name and by date | 3 |
| I4 | `List_FilteredSecondPage_TotalCountIsFilteredSet` (seed 3 matches plus non-matches, `pageSize=2&page=2`: 1 item, `totalCount` 3); `List_FilteredHugePageSize_IsClampedToMaxPageSize` | 4 |
| I5 | `List_InvalidFilter_ReturnsValidationProblem`: theory over `createdFrom=2026-13-40`, `createdFrom=11/19/2026`, `createdTo=abc`, `createdFrom=2026-11-20&createdTo=2026-11-19`, `customerName=<201 x>`, asserting the key for each | 5 |
| I6 | `List_FilterWithoutCredentials_ReturnsUnauthorized` (`AnonymousHeader` with `customerName=x`) | 6 |
| I7 | `List_DateRange_BoundsAreInclusiveUtcDays`: rows at `from 00:00:00Z` and `to 23:59:59.999999Z` are in; `from-1 23:59:59.999999Z` and `to+1 00:00:00Z` are out; plus from-only and to-only cases; `createdTo=9999-12-31` returns 200 | 7 |
| I8 | `List_CustomerName_MatchesCaseInsensitiveSubstring`: `"<token> ACME Widgets"` found by `acme`, `WIDG`, `me wi`, `<token>`; one accented case (`ÉCOLE` found by `école`) documents the container locale (`TQ-006`) | 8 |
| I9 | `List_CustomerName_WildcardsMatchLiterally`: names `"<token> 50% off"`, `"<token> 500 off"`, `"<token> a_b"`, `"<token> axb"`, `"<token> back\slash"`, `"<token> backslash"`. Searching `50%` finds only the first, `a_b` only `a_b`, `k\s` only `back\slash`, and `%` alone (with the token) does not match everything | 8 |

#### Security notes (security-engineer: applies)

The trigger is an API contract change in which caller input reaches a database query (`_SHARED-PATTERNS.md` "run proactively on auth, data, API ... changes"; `security-engineer` review area "Input and API"). The review covers the R1 diff alongside the review pair.

| Topic | Design position | For the reviewer to confirm |
|-------|-----------------|-----------------------------|
| Injection | Every value reaches SQL as a parameter (`@pattern`, bounds); the escape character is a constant | No string concatenation into SQL; `ToQueryString()` shows parameters |
| Pattern amplification | Caller wildcards are escaped, so the pattern is always `%literal%`; length is capped at 200 | Escape order (`\` first) and tests I9, U6 |
| Error content | Messages are fixed text, never echo input; no exception text | I5 bodies |
| Personal data | A customer name may identify a person. It travels in the query string, so it can land in access logs, proxy logs and OpenTelemetry `url.query`. The design does not log the term. Moving to POST is not proposed | Classification call: is a customer name personal data here; is query-string redaction needed in observability (adopter's backend, not yet configured) |
| Visibility | Any authenticated caller can search all orders, which makes name enumeration easier than paging. This is the same exposure as the VS-001 list (`BQ-006` working assumption) | Whether `BQ-006` must be answered before R1 ships |
| Rate limiting | None exists in the API; R1 adds none | Whether a search endpoint needs one now |

#### Risks and questions

| Id | Type | Decider | Blocks R1? | Topic |
|----|------|---------|------------|-------|
| `TQ-005` | TQ | tech-lead | no | Problem details for malformed typed query parameters (VS-001 `page`/`pageSize` gap) |
| `TQ-006` | TQ | tech-lead | no | Non-ASCII case-insensitivity depends on the database `LC_CTYPE` |
| `BQ-007` | BQ | product-owner | no | Time zone of a calendar day for the created-date filter: answered, UTC days (`OD-005`) |
| `BQ-005`, `BQ-006` | BQ | product-owner | no | unchanged working assumptions |

## S4 Dependencies

| Depends on | Type (hard/soft) | Status | Conflict with open PR? |
|------------|------------------|--------|------------------------|
| VS-005 | hard, R2 only | Proposed (status vocabulary alignment) | none known |
| VS-001 | hard | In progress (INDEX); list endpoint present in code; pickup exception for R1 by `OD-006` | none known; no open PR branches besides `chore/frontend-lockfile`, `docs/local-review-is-the-gate`, `docs/verify-model-prices` (not inspected for overlap: touch docs/frontend only by name) |

## S5 Decisions and blockers

| Record | Type | Decider | Blocks which rung | Resolved? |
|--------|------|---------|-------------------|-----------|
| BQ-003 | BQ | product-owner | R1, R2 (filter set) | yes, `OD-002` |
| BQ-004 | BQ | product-owner | R1 (text search) | yes, `OD-003` |
| TQ-003 | TQ | tech-lead | R2 (status filter) | yes, `OD-004`; delivery tracked as `VS-005` |
| BQ-005 | BQ | product-owner | none (assume newest first) | no, non-blocking, owner chose to leave open |
| BQ-006 | BQ | product-owner | none (assume VS-001 visibility, flag to security-engineer) | no, non-blocking |
| TQ-004 | TQ | tech-lead | none (amount filter excluded by `OD-002`) | no, non-blocking |
| TQ-005 | TQ | tech-lead | none (R1 binds its new parameters as strings) | no, non-blocking (added by solution-architect) |
| TQ-006 | TQ | tech-lead | none (ASCII folding is locale-independent; R1 tests the container locale) | no, non-blocking (added by solution-architect) |
| BQ-007 | BQ | product-owner | R1 (date semantics, was a working assumption) | yes, `OD-005` |
| OD-006 | OD | product-owner | R1 pickup (hard dependency VS-001 not `Done`) | yes, exception for R1 only |

Blockers (rows that block a rung) are all resolved for R1. The three open rows are non-blocking by owner decision; the folder rule says `Ready` needs zero open blockers, which these are not. R2 additionally waits for `VS-005` to be `Done`.

## Priority inputs

Value 3 (finding orders is useful, not core), Urgency 2 (no deadline), Unblocks 0 (no slice waits), Effort 2 (one rung, small). Priority (2*3 + 2*2 + 0) / 2 = 5.00.

## Pickup delta log

| Date | Compared with | Result (unchanged / deltas) |
|------|---------------|-----------------------------|
| 2026-11-19 | baseline `f1b0adc` (analysis written against it) | n/a, first analysis |
| 2026-11-19 | `HEAD` `f1b0adc` (R1 design) | unchanged: no commit since the baseline; the working tree differs only by the uncommitted VS-004 docs and records |
| 2026-11-19 | `OD-006` (pickup exception for R1); `HEAD` `f1b0adc` unchanged since the baseline | unchanged. The hard dependency VS-001 is `In progress` in the INDEX: R1 may start by `OD-006`, R2 may not (waits for VS-005) |
