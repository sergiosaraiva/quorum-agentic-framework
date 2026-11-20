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
| Image tag | Declared in the factory (`ApiFactory.cs`); a test that starts its own container uses the same tag |
| Migrations | Real migrations (`MigrateAsync`) in the fixture; one that does not apply fails the suite |
| Fixture | One container per test class (`IClassFixture`, `tests/CLAUDE.md`), not per test; sharing needs a recorded decision. Unique ids per test |
| Overrides | Test-only service swaps via `ConfigureTestServices`; configuration via in-memory config, never edit `appsettings.json` |
| Auth | Test authentication scheme in the factory instead of JWT bearer (`tests/CLAUDE.md`; `TestAuthHandler`, `X-Test-Anonymous` in `ApiFactory.cs`); test authenticated and anonymous calls |
| Cancellation | Pass `TestContext.Current.CancellationToken` |
| Error keys | Assert the exact key casing the API returns, case-sensitively, never `OrdinalIgnoreCase`: it hides a casing defect (TQ-008). The create path returns member names (`CustomerName`), list filters camelCase; TQ-008 is open (recommended: camelCase), so update the assertion when it is decided. Landed: `OrdersSearchTests.List_InvalidFilters_ErrorKeysAreExactlyTheCamelCaseParameterNames` |
| Scope | Contract, validation, auth, persistence, status codes, Problem Details. Pure logic: `creating-xunit-tests` |

## Decision Tree

```
Endpoint, auth, validation, persistence?   -> WebApplicationFactory + Testcontainers
Migration applies cleanly?                 -> fresh container, MigrateAsync, no exception
Query behaviour (filters, constraints, concurrency)? -> real container, assert rows
Race or duplicate protection?              -> N concurrent requests, assert the invariant (one row, one winner)
Pure service logic, no I/O?                -> creating-xunit-tests
External HTTP dependency?                  -> fake that client via ConfigureTestServices
```

## Example: factory and endpoint test

Shape of the landed `ApiFactory` (`tests/Api.IntegrationTests/ApiFactory.cs`, the source of truth); the Reports endpoints are an example.

```csharp
public class ApiFactory : WebApplicationFactory<Program>, IAsyncLifetime
{
    public const string TestScheme = "Test";
    public const string AnonymousHeader = "X-Test-Anonymous";

    private readonly PostgreSqlContainer _postgres = new PostgreSqlBuilder("postgres:16-alpine").Build();

    public async ValueTask InitializeAsync()
    {
        await _postgres.StartAsync(TestContext.Current.CancellationToken);
        using var scope = Services.CreateScope();
        await scope.ServiceProvider.GetRequiredService<AppDbContext>().Database.MigrateAsync();
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["ConnectionStrings:Default"] = _postgres.GetConnectionString(),
            ["Auth:Authority"] = "https://idp.invalid",
            ["Auth:Audience"] = "test",
        }));
        builder.ConfigureServices(services =>
        {
            services.AddAuthentication(TestScheme).AddScheme<AuthenticationSchemeOptions, TestAuthHandler>(TestScheme, _ => { });
            services.PostConfigure<AuthenticationOptions>(o =>
            {
                o.DefaultAuthenticateScheme = TestScheme;
                o.DefaultChallengeScheme = TestScheme;
            });
        });
    }
}

public sealed class ReportsEndpointTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    [Fact]
    public async Task PostReports_ValidRequest_ReturnsCreatedWithLocation()
    {
        // Arrange: the factory migrated; the test scheme authenticates every call
        var client = factory.CreateClient();

        // Act
        var response = await client.PostAsJsonAsync("/api/reports", new { title = "Q1 report" },
            TestContext.Current.CancellationToken);

        // Assert
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        Assert.NotNull(response.Headers.Location);
    }

    [Fact]
    public async Task PostReports_Anonymous_Returns401()
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Add(ApiFactory.AnonymousHeader, "1");   // no identity

        var response = await client.PostAsJsonAsync("/api/reports", new { title = "x" },
            TestContext.Current.CancellationToken);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }
}
```

## Example: validation and migration

```csharp
[Fact]
public async Task PostReports_EmptyTitle_Returns400ProblemDetails()
{
    var client = factory.CreateClient();
    var response = await client.PostAsJsonAsync("/api/reports", new { title = "" }, TestContext.Current.CancellationToken);
    Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    var problem = await response.Content.ReadFromJsonAsync<ValidationProblemDetails>(TestContext.Current.CancellationToken);
    Assert.Contains("Title", problem!.Errors.Keys);   // member name, case-sensitive
}

[Fact]
public async Task Migrations_ApplyCleanlyToFreshDatabase()
{
    await using var db = new PostgreSqlBuilder("postgres:16-alpine").Build();   // factory's tag
    await db.StartAsync(TestContext.Current.CancellationToken);
    var options = new DbContextOptionsBuilder<AppDbContext>().UseNpgsql(db.GetConnectionString()).Options;
    await using var context = new AppDbContext(options);
    await context.Database.MigrateAsync(TestContext.Current.CancellationToken);
}
```

## Quality Checklist

- [ ] Real PostgreSQL via Testcontainers; real migrations applied
- [ ] One container per class; data isolated between tests
- [ ] Auth tested both ways (401 without token, 403 wrong role, 2xx allowed)
- [ ] Validation, error body shape and status codes asserted
- [ ] Image tag declared in the factory; error keys exact and case-sensitive; no secrets in source
- [ ] Concurrency or duplicate-protection test where the code claims it

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| EF in-memory provider | Testcontainers PostgreSQL |
| Container started per test | One fixture per class |
| Skipping the anonymous case | Send `X-Test-Anonymous`, assert 401 |
| Shared rows, order dependence | Unique data per test |
| Asserting only 200 | Assert body, headers and the persisted row |

## Related Skills

- `creating-xunit-tests`: pure logic
- `writing-playwright-e2e-tests`: browser journeys
- `load-and-performance-testing`: concurrency at scale
