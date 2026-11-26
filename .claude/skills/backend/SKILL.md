---
name: backend
description: Creates ASP.NET Core Minimal API endpoints with explicit authorization, typed results, validated DTO binding, server-capped pagination and delegation to an application service. Use when adding or changing an HTTP endpoint, a route group or API error handling under src/Api/.
---

# Creating Minimal API Endpoints

Design Principles (simplest design, no speculative abstractions, no hard-coded values): `.claude/agents/_SHARED-PATTERNS.md`.

## Quick Reference

- One feature folder: `src/Api/Features/<Feature>/{<Feature>Endpoints.cs, <Feature>Service.cs, Dtos.cs}`. `Map<Feature>Endpoints(this IEndpointRouteBuilder app)` calls `app.MapGroup("/api/<feature>")` itself (landed `src/Api/Features/Orders/OrdersEndpoints.cs`); `Program.cs` calls `app.Map<Feature>Endpoints()`. No version segment: OD-024 decided that routes stay `/api/<feature>`; `/api/v1/<feature>` later needs a superseding OD
- Every endpoint declares `.Produces<T>(status)` for each response shape, or returns `Results<...>` typed results (`TypedResults` is the recommended form for OpenAPI metadata). The landed Orders endpoints predate it and return untyped `Results.Ok`/`Results.ValidationProblem`: TQ-018 asks whether to move them
- Every endpoint has an explicit auth decision: `.RequireAuthorization("<feature policy>")` on the group: a named policy per feature, registered in Program.cs (Orders uses `OrdersAuthorization.PolicyName`; OD-011), or a one-line comment "intentionally anonymous: <reason>"
- Input binds to a typed `record` DTO; never parse `HttpContext.Request` by hand. Simple rules: DataAnnotations via `Validator.TryValidateObject` returning a validation problem (Orders default); FluentValidation for cross-field rules (`creating-dtos-and-validation`)
- The endpoint holds no business logic or EF query: it validates, calls the service, maps the result to a status code
- `await` everything; never `.Result`/`.Wait()`; thread `CancellationToken` into every awaited call
- No controllers, mediator/CQRS, endpoint base classes or generic CRUD helpers until a third endpoint repeats the code
- Tunables (page-size cap, limits) come from Options (`creating-configuration-options`); route segments stay literal

## Decision Tree

```
New feature area?   -> Features/<Name>/<Name>Endpoints.cs (MapGroup inside) + Map call in Program.cs
Needs pagination?   -> page/pageSize query params, cap and default from the feature Options, return `PagedResponse<T>` (Items, Page, PageSize, TotalCount)
Needs a service?    -> inject the concrete service (interface only at a real seam: creating-application-services)
Auth?               -> group-level `RequireAuthorization("<feature policy>")`, with roles or scopes added to that policy where they differ; resource-level checks (ownership, tenant) belong in the service
Error from service? -> catch specific exceptions; unexpected ones reach the global handler (ProblemDetails)
Public anonymous?   -> health checks and documented public routes only; comment why
```

## Examples

Illustrative (Reports is not template code); the landed shape is `src/Api/Features/Orders/`.

```csharp
// Features/Reports/ReportsEndpoints.cs
public static class ReportsEndpoints
{
    public static IEndpointRouteBuilder MapReportsEndpoints(this IEndpointRouteBuilder app)
    {
        // named policy on the group = the explicit auth decision
        var group = app.MapGroup("/api/reports").WithTags("Reports")
            .RequireAuthorization(ReportsAuthorization.PolicyName);
        group.MapGet("/{id:guid}", GetAsync).WithName("GetReport");
        group.MapPost("/", CreateAsync);
        return app;
    }

    private static async Task<Results<Ok<ReportDto>, NotFound>> GetAsync(
        Guid id, ReportService service, CancellationToken ct)
        => await service.GetAsync(id, ct) is { } dto ? TypedResults.Ok(dto) : TypedResults.NotFound();

    private static async Task<Results<Created<ReportDto>, ValidationProblem>> CreateAsync(
        CreateReportRequest request, IValidator<CreateReportRequest> validator,
        ReportService service, CancellationToken ct)
    {
        var validation = await validator.ValidateAsync(request, ct);
        if (!validation.IsValid) return TypedResults.ValidationProblem(validation.ToDictionary());
        var dto = await service.CreateAsync(request, ct);
        return TypedResults.Created($"/api/reports/{dto.Id}", dto);
    }
}

// Program.cs
app.MapReportsEndpoints();
```

Pagination: bind `string? page, string? pageSize` and parse them with `PagingQuery.Parse`, so a malformed value returns `Results.ValidationProblem` keyed `page` or `pageSize` (TQ-005, OD-016); a page above `OrdersOptions.MaxPageNumber` is a 400 keyed `page` (TQ-015, OD-025); `DatabaseTimeoutProblem.SelectStatusCode` (`ExceptionHandlerOptions.StatusCodeSelector`) maps a `BadHttpRequestException` to its own 4xx and a database timeout to 503 with `Retry-After` (OD-029). Error keys are camelCase (TQ-008, OD-019). The service normalises the parsed `int?` values (`OrdersService.NormalizePaging`): `Math.Max(page ?? 1, 1)` for the page and `Math.Clamp(pageSize ?? options.DefaultPageSize, 1, options.MaxPageSize)` for the size. The feature options (`OrdersOptions` in `src/Api/Options/`) declare `MaxPageSize` and `DefaultPageSize` as `[Range(1, 1000)]` (and `MaxPageNumber` as `[Range(1, 1_000_000)]`) and are bound with `ValidateOnStart()`, so an out-of-range value fails startup. Compute the skip in `long` and clamp it (`ComputeSkip`) so a huge `page` cannot overflow `int` (`src/Api/CLAUDE.md`). `PagedResponse<T>` (`src/Api/Features/Orders/Dtos.cs`) is the list response; move to `Common/` at the third feature.

## Quality Checklist

- [ ] `.Produces` / typed results cover every status the endpoint can return
- [ ] Explicit auth decision present (group policy)
- [ ] Input is a record DTO, validated before the service is called (DataAnnotations: `Validator.TryValidateObject`; FluentValidation needs an explicit call or filter)
- [ ] Page size capped server-side from Options
- [ ] No business logic, EF query, interface or base class the endpoint does not need
- [ ] `CancellationToken` threaded through; `Map<Feature>Endpoints()` called in `Program.cs`

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| EF Core query inside the endpoint method | Delegate to the service |
| No auth call and no comment | Policy or an "intentionally anonymous" comment |
| `catch (Exception) { return Results.Problem(); }` | Specific catches; global handler for the rest |
| Unbounded or literal `pageSize` cap | `Math.Clamp(pageSize ?? options.DefaultPageSize, 1, options.MaxPageSize)` (`Math.Min` lets 0 and negatives through) |
| `IReportService` injected "for testability" | Concrete service; integration-test the endpoint |
| Generic `CrudEndpoints<T>` before the third repeat | Write endpoints out; extract at the third use |

## Related Skills

`creating-dtos-and-validation` (DTOs), `creating-application-services` (logic behind the endpoint), `database` (entities), `creating-configuration-options` (caps), `implementing-vertical-slice-features` (full feature order).
