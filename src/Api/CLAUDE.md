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
| Endpoints | static `Map<Feature>Endpoints(this IEndpointRouteBuilder)` returning a `RouteGroup`; the group calls `RequireAuthorization()` explicitly (Immutable Rule 7). An anonymous endpoint needs `AllowAnonymous()` plus a comment saying why |
| DTOs | `record` types; validate with DataAnnotations or FluentValidation at the boundary; never expose EF entities |
| Services | concrete classes, scoped; add an interface only at a real seam (external I/O, test boundary) |
| Options | `services.AddOptions<T>().BindConfiguration("Section").ValidateDataAnnotations().ValidateOnStart()`; no `IConfiguration["x"]` reads in logic |
| Auth | JWT bearer from the `Auth` section (`Authority`, `Audience`); the identity provider authenticates, the API authorizes via policies |
| Errors | `Results.Problem` (RFC 9457 problem details); never leak exception text |
| Pagination | every list endpoint takes `page` and `pageSize`, clamps `pageSize` to a configured maximum; paging arithmetic must not overflow on a huge `page` |
| Health | `/health/live` (anonymous, no dependencies) and `/health/ready` (anonymous, returns no data, includes the database check tagged `ready`) for the Kubernetes probes |
| Logging | `ILogger<T>` structured messages; no secrets, tokens or personal data in logs |

## Do not

- Put business rules in endpoint lambdas; they call the service.
- Return `IQueryable` or tracked entities from a service.
- Add a feature folder dependency on another feature; extract to `Common/` at the third consumer.
