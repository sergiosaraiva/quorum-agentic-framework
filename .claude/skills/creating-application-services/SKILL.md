---
name: creating-application-services
description: Creates DI-registered application services with correct lifetimes and constructor injection, the business-logic layer behind Minimal API endpoints. Concrete classes by default; an interface only at a real seam (external I/O, tenant-varying behaviour). Includes typed HTTP clients. Use when adding business logic, orchestration, or an external API client behind an endpoint.
---

# Creating Application Services

Design Principles: `.claude/agents/_SHARED-PATTERNS.md`.

## Quick Reference

- A feature service is a `sealed class` registered as itself (`AddScoped<ReportService>()`). No interface by default
- Add an interface only for a present reason: external I/O (typed HTTP client, cloud SDK client), tenant-varying behaviour, or 2+ real implementations today. "So it can be mocked" is not a reason for a service over `AppDbContext`: cover it with integration tests against real PostgreSQL
- No repository/unit-of-work over EF Core (the `DbContext` already is one), no generic base service, no mediator/CQRS pipeline
- Default lifetime `Scoped`. `Singleton` only for stateless or thread-safe helpers, never one holding a `DbContext`
- Constructor injection only; no service locator (`IServiceProvider.GetService` inside a method)
- Async all the way: I/O methods return `Task`/`Task<T>` and accept a `CancellationToken`
- Limits, URLs, timeouts, page sizes come from Options (`creating-configuration-options`). A fixed domain constant is one named `const` in the owning type
- Authorization that depends on the resource (ownership, tenant, grant) is enforced here, before the query

## Decision Tree

```
Logic beyond one DbContext read/write (rules, orchestration, calculation)? -> a service class; otherwise keep the endpoint thin
Needs an interface?   -> only external I/O, tenant-varying behaviour, or 2+ real implementations (state which in a comment)
Needs DbContext?      -> Scoped
Pure, stateless?      -> Singleton acceptable
Mutable per-call state-> Scoped or Transient, never Singleton
Calls an external API?-> AddHttpClient<T>() typed client; base URL and timeout from Options; never new HttpClient()
Long-running/background work? -> BackgroundService (managing-application-lifecycle), not a request-scoped method
Same logic in a second service? -> copies that must agree: extract one composed helper now; merely similar: tolerate, extract at the third use. Prefer a helper over a base class
```

## Examples

```csharp
// Features/Reports/ReportService.cs
public sealed class ReportService(AppDbContext db, ILogger<ReportService> logger)
{
    public async Task<ReportDto?> GetAsync(Guid id, CancellationToken ct)
    {
        var entity = await db.Reports.AsNoTracking().FirstOrDefaultAsync(r => r.Id == id, ct);
        return entity is null ? null : ReportDto.FromEntity(entity);
    }

    public async Task<ReportDto> CreateAsync(CreateReportRequest request, CancellationToken ct)
    {
        var entity = new Report { Id = Guid.CreateVersion7(), Title = request.Title };
        // created_at/created_by are stamped by the SaveChanges interceptor (database skill), never here
        db.Reports.Add(entity);
        await db.SaveChangesAsync(ct);
        logger.LogInformation("Report {ReportId} created", entity.Id);   // structured fields, no PII
        return ReportDto.FromEntity(entity);
    }
}
// Program.cs
builder.Services.AddScoped<ReportService>();
```

Typed HTTP client (a real seam, so an interface is justified because tests must not call the real service):

```csharp
public sealed class GeocodingOptions
{
    public const string SectionName = "Geocoding";
    [Required, Url] public string BaseUrl { get; init; } = string.Empty;
    [Range(1, 60)] public int TimeoutSeconds { get; init; }
}
public interface IGeocodingService { Task<GeoLocation?> LookupAsync(string address, CancellationToken ct); }
public sealed class GeocodingService(HttpClient http) : IGeocodingService
{
    public async Task<GeoLocation?> LookupAsync(string address, CancellationToken ct)
    {
        var response = await http.GetAsync($"/geocode?q={Uri.EscapeDataString(address)}", ct);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<GeoLocation>(ct);
    }
}
// Program.cs (options bound with ValidateDataAnnotations().ValidateOnStart())
builder.Services.AddHttpClient<IGeocodingService, GeocodingService>((sp, c) =>
{
    var o = sp.GetRequiredService<IOptions<GeocodingOptions>>().Value;
    c.BaseAddress = new Uri(o.BaseUrl);
    c.Timeout = TimeSpan.FromSeconds(o.TimeoutSeconds);
});
```

Do not wrap `HttpClient` in a further generic "ApiClient". Add the standard resilience handler (`AddStandardResilienceHandler()`) when a measured need exists.

## Quality Checklist

- [ ] No interface, repository, base service or mediator without a stated seam
- [ ] Correct DI lifetime registered in `Program.cs`; anything but `Scoped` justified in a comment
- [ ] Constructor injection; `CancellationToken` threaded; `AsNoTracking()` on pure reads
- [ ] Resource-level authorization enforced in the service or by the endpoint's documented policy
- [ ] External calls via typed client with validated Options; no hard-coded URL, limit or timeout

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| `IReportService` for every service | Concrete class; interface only at a seam |
| `ReportRepository` wrapping `AppDbContext` | Use the `DbContext` directly |
| `AddSingleton` for a service holding a `DbContext` | `AddScoped` |
| `new HttpClient()` in a method | Typed client via `AddHttpClient<T>()` |
| Caller-supplied connection string or tenant id as a parameter | Resolve at the infrastructure layer from validated claims |
| `.Result` on a `Task<T>` | `await` |

## Related Skills

`backend`, `database`, `creating-dtos-and-validation`, `creating-configuration-options`, `implementing-caching-strategies`.
