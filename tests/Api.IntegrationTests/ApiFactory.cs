using System.Security.Claims;
using System.Text.Encodings.Web;
using Api.Features.Orders;
using Infrastructure.Persistence;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.AspNetCore.Routing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Testcontainers.PostgreSql;

namespace Api.IntegrationTests;

/// <summary>Real HTTP pipeline against a real PostgreSQL container; JWT validation is replaced by a test scheme.</summary>
public class ApiFactory : WebApplicationFactory<Program>, IAsyncLifetime
{
    public const string TestScheme = "Test";
    public const string AnonymousHeader = "X-Test-Anonymous";

    /// <summary>Optional header naming the test principal; default is <see cref="DefaultTestUser"/>. Lets a test prove per-user partitioning.</summary>
    public const string UserHeader = "X-Test-User";
    public const string DefaultTestUser = "test-user";

    /// <summary>Hosting environment for the test host; override to test environment-specific behaviour.</summary>
    protected virtual string EnvironmentName => "Testing";

    /// <summary>
    /// Configuration overrides applied last. The base host gets a limit no test reaches, so the shared fixtures never
    /// trip the rate limiter; a test of the limiter itself overrides it with a tiny value.
    /// </summary>
    protected virtual IReadOnlyDictionary<string, string?> ExtraSettings { get; } = new Dictionary<string, string?>
    {
        ["RateLimiting:PermitLimit"] = "100000",
    };

    private static readonly TimeSpan MigrationCommandTimeout = TimeSpan.FromMinutes(2);

    private readonly PostgreSqlContainer _postgres = new PostgreSqlBuilder("postgres:16-alpine").Build();

    public async ValueTask InitializeAsync()
    {
        await _postgres.StartAsync();
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        // Migrations on a cold container can outlast a tiny configured command timeout; give this one context room.
        db.Database.SetCommandTimeout(MigrationCommandTimeout);
        await db.Database.MigrateAsync();
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment(EnvironmentName);
        builder.ConfigureAppConfiguration((_, config) =>
        {
            config.AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["ConnectionStrings:Default"] = _postgres.GetConnectionString(),
                ["Auth:Authority"] = "https://idp.invalid",
                ["Auth:Audience"] = "test",
            });
            config.AddInMemoryCollection(ExtraSettings);
        });
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

    public new async ValueTask DisposeAsync()
    {
        await base.DisposeAsync();
        await _postgres.DisposeAsync();
    }
}

/// <summary>Same host in the Development environment (for the Development-only OpenAPI mapping).</summary>
public sealed class DevelopmentApiFactory : ApiFactory
{
    protected override string EnvironmentName => "Development";
}

/// <summary>Host with a tiny per-user rate limit and a one-second command timeout (TQ-007, OD-018).</summary>
public sealed class TinyLimitsApiFactory : ApiFactory
{
    public const int PermitLimit = 2;
    public const int WindowSeconds = 3600;

    protected override IReadOnlyDictionary<string, string?> ExtraSettings { get; } = new Dictionary<string, string?>
    {
        ["RateLimiting:PermitLimit"] = PermitLimit.ToString(System.Globalization.CultureInfo.InvariantCulture),
        ["RateLimiting:WindowSeconds"] = WindowSeconds.ToString(System.Globalization.CultureInfo.InvariantCulture), // far longer than a test run, so the window never rolls over mid-test
        ["Database:CommandTimeoutSeconds"] = "1",
        ["Database:RetryAfterSeconds"] = RetryAfterSeconds.ToString(System.Globalization.CultureInfo.InvariantCulture),
        ["RateLimiting:ConcurrentRequestsPerUser"] = "1",
    };

    public const int RetryAfterSeconds = 7;

    /// <summary>Test-only routes that run a command longer than the timeout, or throw an unrelated exception with a recognisable message.</summary>
    public const string SlowRoute = "/__test/slow";
    public const string BoomRoute = "/__test/boom";
    public const string BoomMessage = "zzsecret-exception-text-zz";

    /// <summary>Test-only route under the orders list rate-limit policy that stays in flight until <see cref="ReleaseHold"/> is called.</summary>
    public const string HoldRoute = "/__test/hold";

    private readonly TaskCompletionSource _holdEntered = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private readonly TaskCompletionSource _holdRelease = new(TaskCreationOptions.RunContinuationsAsynchronously);

    public Task HoldEntered => _holdEntered.Task;

    public void ReleaseHold() => _holdRelease.TrySetResult();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        base.ConfigureWebHost(builder);
        builder.ConfigureServices(services => services.AddSingleton<IStartupFilter>(_ => new TestRoutesStartupFilter(this)));
    }

    private sealed class TestRoutesStartupFilter(TinyLimitsApiFactory owner) : IStartupFilter
    {
        public Action<IApplicationBuilder> Configure(Action<IApplicationBuilder> next) => app =>
        {
            next(app);
            app.UseEndpoints(e =>
            {
                e.MapGet(SlowRoute, async (AppDbContext db, CancellationToken ct) =>
                {
                    await db.Database.ExecuteSqlRawAsync("SELECT pg_sleep(5)", ct);
                    return Results.Ok();
                });
                e.MapGet(HoldRoute, async () =>
                {
                    owner._holdEntered.TrySetResult();
                    await owner._holdRelease.Task;
                    return Results.Ok();
                }).RequireRateLimiting(OrdersRateLimit.PolicyName);
                e.MapGet(BoomRoute, () => { throw new InvalidOperationException(BoomMessage); });
            });
        };
    }
}

/// <summary>Host with invalid options and no container; building it must fail at start (ValidateOnStart).</summary>
public sealed class InvalidOptionsApiFactory(string key, string value) : WebApplicationFactory<Program>
{
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["ConnectionStrings:Default"] = "Host=127.0.0.1;Port=1;Database=none;Username=none;Password=none",
            ["Auth:Authority"] = "https://idp.invalid",
            ["Auth:Audience"] = "test",
            [key] = value,
        }));
    }
}

/// <summary>Host whose database is unreachable; no container. Proves readiness fails while liveness stays up.</summary>
public sealed class BrokenDatabaseApiFactory : WebApplicationFactory<Program>
{
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["ConnectionStrings:Default"] = "Host=127.0.0.1;Port=1;Database=none;Username=none;Password=none;Timeout=2;Command Timeout=2",
            ["Auth:Authority"] = "https://idp.invalid",
            ["Auth:Audience"] = "test",
        }));
    }
}

public sealed class TestAuthHandler(
    IOptionsMonitor<AuthenticationSchemeOptions> options, ILoggerFactory logger, UrlEncoder encoder)
    : AuthenticationHandler<AuthenticationSchemeOptions>(options, logger, encoder)
{
    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (Request.Headers.ContainsKey(ApiFactory.AnonymousHeader))
        {
            return Task.FromResult(AuthenticateResult.NoResult());
        }

        var user = Request.Headers.TryGetValue(ApiFactory.UserHeader, out var named) && !string.IsNullOrEmpty(named)
            ? named.ToString()
            : ApiFactory.DefaultTestUser;
        var identity = new ClaimsIdentity([new Claim(ClaimTypes.NameIdentifier, user)], ApiFactory.TestScheme);
        return Task.FromResult(AuthenticateResult.Success(
            new AuthenticationTicket(new ClaimsPrincipal(identity), ApiFactory.TestScheme)));
    }
}
