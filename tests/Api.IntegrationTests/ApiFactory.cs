using System.Security.Claims;
using System.Text.Encodings.Web;
using Infrastructure.Persistence;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
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

    /// <summary>Hosting environment for the test host; override to test environment-specific behaviour.</summary>
    protected virtual string EnvironmentName => "Testing";

    private readonly PostgreSqlContainer _postgres = new PostgreSqlBuilder("postgres:16-alpine").Build();

    public async ValueTask InitializeAsync()
    {
        await _postgres.StartAsync();
        using var scope = Services.CreateScope();
        await scope.ServiceProvider.GetRequiredService<AppDbContext>().Database.MigrateAsync();
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment(EnvironmentName);
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

        var identity = new ClaimsIdentity([new Claim(ClaimTypes.NameIdentifier, "test-user")], ApiFactory.TestScheme);
        return Task.FromResult(AuthenticateResult.Success(
            new AuthenticationTicket(new ClaimsPrincipal(identity), ApiFactory.TestScheme)));
    }
}
