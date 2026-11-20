---
name: backend
description: Creates ASP.NET Core Minimal API endpoints with explicit authorization, typed results, validated DTO binding, server-capped pagination and delegation to an application service. Use when adding or changing an HTTP endpoint, a route group or API error handling under src/Api/.
---

# Creating Minimal API Endpoints

Design Principles (simplest design, no speculative abstractions, no hard-coded values): `.claude/agents/_SHARED-PATTERNS.md`.

## Quick Reference

- One feature folder: `src/Api/Features/<Feature>/{<Feature>Endpoints.cs, <Feature>Service.cs, Dtos.cs}`. Group routes with `app.MapGroup("/api/<feature>")` (as the landed `src/Api/Features/Orders/OrdersEndpoints.cs` does) and register the group in `Program.cs`. Add a version segment (`/api/v1/<feature>`) only when an owner decision (OD) records API versioning; none does today
- Every endpoint declares `.Produces<T>(status)` for each response shape, or returns `Results<...>` typed results
- Every endpoint has an explicit auth decision: `.RequireAuthorization()` on the group (as Orders does), a named policy `.RequireAuthorization("<policy>")` where roles or scopes differ, or a one-line comment "intentionally anonymous: <reason>"
- Input binds to a typed `record` DTO; never parse `HttpContext.Request` by hand. Simple rules use DataAnnotations checked with `Validator.TryValidateObject` and return `Results.ValidationProblem` (the Orders default); FluentValidation is for cross-field rules (`creating-dtos-and-validation`)
- The endpoint method holds no business logic and no EF Core query: it validates, calls the service, maps the result to a status code
- `await` everything; never `.Result` / `.Wait()`. Thread `CancellationToken` into every awaited call
- No controllers, mediator/CQRS pipeline, endpoint base classes or generic CRUD helpers until a third endpoint repeats the same code
- Tunables (page-size cap, limits) come from Options (`creating-configuration-options`). Route segments are protocol constants and stay literal

## Decision Tree

```
New feature area?   -> Features/<Name>/<Name>Endpoints.cs + MapGroup in Program.cs
Needs pagination?   -> page/pageSize query params, cap and default from the feature Options, return `PagedResponse<T>` (Items, Page, PageSize, TotalCount)
Needs a service?    -> inject the concrete service (interface only at a real seam: creating-application-services)
Auth?               -> group-level `RequireAuthorization()`, or a named policy where roles differ; resource-level checks (ownership, tenant) belong in the service
Error from service? -> catch specific exception types; let unexpected ones reach the global exception handler (ProblemDetails)
Public anonymous?   -> only health checks and documented public routes; comment why
```

## Examples

The example below is illustrative (Reports is not template code). For the landed shape read `src/Api/Features/Orders/`.

```csharp
// Features/Reports/ReportsEndpoints.cs
public static class ReportsEndpoints
{
    public static RouteGroupBuilder MapReportsEndpoints(this RouteGroupBuilder group)
    {
        group.MapGet("/{id:guid}", GetAsync)
            .WithName("GetReport").Produces<ReportDto>().Produces(StatusCodes.Status404NotFound)
            .RequireAuthorization("reports:read");
        group.MapPost("/", CreateAsync)
            .Produces<ReportDto>(StatusCodes.Status201Created).ProducesValidationProblem()
            .RequireAuthorization("reports:write");
        return group;
    }

    private static async Task<Results<Ok<ReportDto>, NotFound>> GetAsync(
        Guid id, ReportService service, CancellationToken ct)
        => await service.GetAsync(id, ct) is { } dto ? TypedResults.Ok(dto) : TypedResults.NotFound();

    private static async Task<Results<Created<ReportDto>, ValidationProblem>> CreateAsync(
        CreateReportRequest request, IValidator<CreateReportRequest> validator,
        ReportService service, CancellationToken ct)
    {
        var validation = await validator.ValidateAsync(request, ct);   // validate before any service call
        if (!validation.IsValid) return TypedResults.ValidationProblem(validation.ToDictionary());
        var dto = await service.CreateAsync(request, ct);
        return TypedResults.Created($"/api/reports/{dto.Id}", dto);
    }
}

// Program.cs
app.MapGroup("/api/reports").MapReportsEndpoints();
```

Pagination: take `int? page, int? pageSize` and clamp the page size with `Math.Clamp(pageSize ?? options.DefaultPageSize, 1, options.MaxPageSize)`, where the feature options (`OrdersOptions` in `src/Api/Options/`) declare `MaxPageSize` and `DefaultPageSize` as `[Range(1, 1000)]` and are bound with `ValidateOnStart()`, so an out-of-range value fails startup instead of returning zero rows. `PagedResponse<T>` (`src/Api/Features/Orders/Dtos.cs`) is the list response; move it to `Common/` at the third feature that needs it (`src/Api/CLAUDE.md`).

## Quality Checklist

- [ ] `.Produces` / typed results cover every status the endpoint can return
- [ ] Explicit auth decision present
- [ ] Input is a record DTO, validated before the service is called (DataAnnotations: `Validator.TryValidateObject`; FluentValidation needs an explicit call or filter)
- [ ] Page size capped server-side from Options
- [ ] No business logic, EF query, interface or base class the endpoint does not need
- [ ] `CancellationToken` threaded through; group registered in `Program.cs`

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| EF Core query inside the endpoint method | Delegate to the service |
| No auth call and no comment | Policy or an "intentionally anonymous" comment |
| `catch (Exception) { return Results.Problem(); }` | Specific catches; global handler for the rest |
| Unbounded or literal `pageSize` cap | `Math.Min(pageSize, options.MaxPageSize)` |
| `IReportService` injected "for testability" | Concrete service; integration-test the endpoint |
| Generic `CrudEndpoints<T>` before the third repeat | Write endpoints out; extract at the third use |

## Related Skills

`creating-dtos-and-validation` (DTOs), `creating-application-services` (logic behind the endpoint), `database` (entities), `creating-configuration-options` (caps), `implementing-vertical-slice-features` (full feature order).
