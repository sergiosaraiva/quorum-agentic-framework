---
name: writing-integration-tests
description: Use when testing an endpoint end to end or anything that depends on real PostgreSQL behaviour (queries, constraints, migrations). WebApplicationFactory plus Testcontainers PostgreSQL, real HTTP pipeline, no mocked persistence, xUnit v3 built-in Assert.
---

# Writing Integration Tests

## Quick Reference

| Topic | Rule |
|-------|------|
| Stack | `WebApplicationFactory<Program>` + Testcontainers `PostgreSqlBuilder` + xUnit v3 `Assert` |
| Database | Real PostgreSQL in a container; never the EF in-memory provider or SQLite as a substitute |
| Image tag | One constant (for example `TestDatabase.Image`) shared by tests and `compose.yaml`; never hard-code a tag twice |
| Migrations | Apply the real migrations (`MigrateAsync`) in the fixture; a migration that does not apply fails the suite |
| Fixture | Container per test class or collection (`IClassFixture` / `ICollectionFixture`), not per test. Reset data between tests (unique ids per test, or Respawn-style cleanup) |
| Overrides | Test-only service swaps via `ConfigureTestServices`; override configuration with `UseSetting`/in-memory config, never edit `appsettings.json` |
| Auth | Issue a test JWT signed with a test key and configure the JWT bearer options to trust it; test both authorized and unauthorized calls |
| Cancellation | Pass `TestContext.Current.CancellationToken` |
| Scope | Contract, validation, auth, persistence, status codes, Problem Details shape. Pure logic belongs in `creating-xunit-tests` |

## Decision Tree

```
Endpoint request/response incl. auth, validation, persistence? -> WebApplicationFactory + Testcontainers
Migration applies cleanly?                 -> start container, MigrateAsync on a fresh DB, no exception
Query behaviour (filters, constraints, concurrency)? -> real container, assert rows
Race condition or duplicate protection?    -> fire N concurrent requests, assert the invariant (one row, one winner)
Pure service logic, no I/O?                -> creating-xunit-tests
External HTTP dependency?                  -> replace that client with a fake via ConfigureTestServices
```

## Example: factory and endpoint test

```csharp
public sealed class ApiFactory : WebApplicationFactory<Program>, IAsyncLifetime
{
    private readonly PostgreSqlContainer _db = new PostgreSqlBuilder(TestDatabase.Image).Build();

    public async ValueTask InitializeAsync() => await _db.StartAsync(TestContext.Current.CancellationToken);

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        builder.UseSetting("ConnectionStrings:Default", _db.GetConnectionString());
        builder.ConfigureTestServices(services =>
        {
            services.PostConfigureAll<JwtBearerOptions>(o =>
                o.TokenValidationParameters.IssuerSigningKey = TestJwt.SigningKey);
        });
    }

    public override async ValueTask DisposeAsync()
    {
        await _db.DisposeAsync();
        await base.DisposeAsync();
    }
}

public sealed class ReportsEndpointTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    [Fact]
    public async Task PostReports_ValidRequest_ReturnsCreatedWithLocation()
    {
        // Arrange
        using (var scope = factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            await db.Database.MigrateAsync(TestContext.Current.CancellationToken);
        }
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new("Bearer", TestJwt.Create("user-1"));

        // Act
        var response = await client.PostAsJsonAsync("/api/v1/reports", new { title = "Q1 report" },
            TestContext.Current.CancellationToken);

        // Assert
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        Assert.NotNull(response.Headers.Location);
    }

    [Fact]
    public async Task PostReports_NoToken_Returns401()
    {
        var response = await factory.CreateClient().PostAsJsonAsync("/api/v1/reports", new { title = "x" },
            TestContext.Current.CancellationToken);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }
}
```

Migrating inside a test class runs once per class; move it to the fixture's `InitializeAsync` when many classes share the factory (use `ICollectionFixture`). Verify the exact Testcontainers and `UseSetting` configuration keys against your project.

## Example: validation and migration

```csharp
[Fact]
public async Task PostReports_EmptyTitle_Returns400ProblemDetails()
{
    var client = factory.CreateAuthorizedClient();
    var response = await client.PostAsJsonAsync("/api/v1/reports", new { title = "" }, TestContext.Current.CancellationToken);
    Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    var problem = await response.Content.ReadFromJsonAsync<ValidationProblemDetails>(TestContext.Current.CancellationToken);
    Assert.Contains("title", problem!.Errors.Keys, StringComparer.OrdinalIgnoreCase);
}

[Fact]
public async Task Migrations_ApplyCleanlyToFreshDatabase()
{
    await using var db = new PostgreSqlBuilder(TestDatabase.Image).Build();
    await db.StartAsync(TestContext.Current.CancellationToken);
    var options = new DbContextOptionsBuilder<AppDbContext>().UseNpgsql(db.GetConnectionString()).Options;
    await using var context = new AppDbContext(options);
    await context.Database.MigrateAsync(TestContext.Current.CancellationToken);   // an exception fails the test
}
```

## Quality Checklist

- [ ] Real PostgreSQL via Testcontainers; real migrations applied
- [ ] Container shared per class or collection; data isolated between tests
- [ ] Auth tested both ways (401 without token, 403 wrong role, 2xx allowed)
- [ ] Validation, error body shape and status codes asserted
- [ ] One image-tag constant; no secrets or real connection strings in source
- [ ] Concurrency or duplicate-protection test where the code claims it

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| EF in-memory provider | Testcontainers PostgreSQL |
| Container started per test | Fixture per class or collection |
| Tests share rows and depend on order | Unique data per test |
| Asserting only 200 | Assert body, headers and the persisted row |
| Skipping the unauthorized case | Always test it |

## Related Skills

- `creating-xunit-tests`: pure logic
- `writing-playwright-e2e-tests`: browser journeys
- `load-and-performance-testing`: concurrency at scale
