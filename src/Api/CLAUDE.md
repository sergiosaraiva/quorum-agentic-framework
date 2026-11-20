# src/Api guide

This file exists because it is loaded when you work under `src/Api/`; the nearest CLAUDE.md wins and adds API-specific conventions to the root guide.

## Layout

| Path | Holds |
|------|-------|
| `Program.cs` | composition root only: options, auth, health checks, endpoint mapping |
| `Features/<Feature>/` | `<Feature>Endpoints.cs`, `<Feature>Service.cs`, `Dtos.cs`; nothing shared between features except via `Common/` once 3 features need it |
| `Options/` | typed options classes, one per config section, validated at startup |

## Conventions

| Topic | Rule |
|-------|------|
| Endpoints | static `Map<Feature>Endpoints(this IEndpointRouteBuilder)` returning a `RouteGroup`; the group calls `RequireAuthorization("<feature policy>")` explicitly with a named policy per feature group, registered in `Program.cs` from a constant in the feature folder (the seam for roles; Immutable Rule 7). A test asserts every endpoint outside the anonymous allow-list (health, OpenAPI) carries authorization metadata. An anonymous endpoint needs `AllowAnonymous()` plus a comment saying why |
| DTOs | `record` types; validate with DataAnnotations or FluentValidation at the boundary; never expose EF entities |
| Services | concrete classes, scoped; add an interface only at a real seam (external I/O, test boundary) |
| Options | `services.AddOptions<T>().BindConfiguration("Section").ValidateDataAnnotations().ValidateOnStart()`; no `IConfiguration["x"]` reads in logic |
| Auth | JWT bearer from the `Auth` section (`Authority`, `Audience`); the identity provider authenticates, the API authorizes via policies |
| Errors | `Results.Problem` (RFC 9457 problem details); never leak exception text. `ValidationProblem` error keys are camelCase on every endpoint and tests assert them case-sensitively. A `BadHttpRequestException` maps to its own 4xx through `ExceptionHandlerOptions.StatusCodeSelector`, so Development never answers a client error with a 500. A custom problem response (for example 429) is written through `IProblemDetailsService`. A database command timeout is a 503 problem response with fixed text (`Common/DatabaseTimeoutProblem`, OD-025); every other exception keeps its status |
| Pagination | every list endpoint takes `page` and `pageSize` as `string?`, parses them explicitly (`PagingQuery.Parse`; reject text, decimals, NUL and out-of-range values with `Results.ValidationProblem` keyed by the parameter name), clamps `pageSize` to a configured maximum and rejects a `page` above `Orders:MaxPageNumber` with a 400 keyed `page` (fixed message, TQ-015, OD-025); paging arithmetic must not overflow on a huge `page` |
| Limits | a list or search endpoint is rate limited per user with the built-in rate limiter, and every EF command has a command timeout (default 10 s, OD-025); both values come from validated Options (`RateLimiting`, `Database`). The rate-limit partition is the `NameIdentifier` claim, then `sub`: the identity provider must issue one of them for every token that calls the orders API; tokens with neither share one bucket (OD-026). Each adopter confirms its provider and records a TQ if it differs |
| Health | `/health/live` (anonymous, no dependencies) and `/health/ready` (anonymous, returns no data, includes the database check tagged `ready`) for liveness and readiness probes |
| Logging | `ILogger<T>` structured messages; no secrets, tokens or personal data in logs |

## Do not

- Put business rules in endpoint lambdas; they call the service.
- Return `IQueryable` or tracked entities from a service.
- Add a feature folder dependency on another feature; extract to `Common/` at the third consumer.
