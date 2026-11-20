using System.Net;
using System.Text.Json;
using Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;

namespace Api.IntegrationTests;

/// <summary>TQ-007: per-user rate limit on the list endpoint and the database command timeout, from Options.</summary>
public class RateLimitAndTimeoutTests(TinyLimitsApiFactory factory) : IClassFixture<TinyLimitsApiFactory>
{
    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    private HttpClient ClientFor(string user)
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Add(ApiFactory.UserHeader, user);
        return client;
    }

    [Fact]
    public async Task List_BeyondPermitLimit_Returns429ProblemDetailsWithRetryAfter()
    {
        var client = ClientFor($"limit-{Guid.NewGuid():N}");

        for (var i = 0; i < TinyLimitsApiFactory.PermitLimit; i++)
        {
            Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/orders", Ct)).StatusCode);
        }

        var limited = await client.GetAsync("/api/orders", Ct);

        Assert.Equal(HttpStatusCode.TooManyRequests, limited.StatusCode);
        Assert.Equal("application/problem+json", limited.Content.Headers.ContentType?.MediaType);
        Assert.NotNull(limited.Headers.RetryAfter);
        using var doc = JsonDocument.Parse(await limited.Content.ReadAsStringAsync(Ct));
        Assert.Equal(429, doc.RootElement.GetProperty("status").GetInt32());
    }

    [Fact]
    public async Task List_LimitIsPerUser_AnotherUserIsUnaffected()
    {
        var heavy = ClientFor($"heavy-{Guid.NewGuid():N}");
        var other = ClientFor($"other-{Guid.NewGuid():N}");
        for (var i = 0; i <= TinyLimitsApiFactory.PermitLimit; i++)
        {
            await heavy.GetAsync("/api/orders", Ct);
        }

        Assert.Equal(HttpStatusCode.TooManyRequests, (await heavy.GetAsync("/api/orders", Ct)).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await other.GetAsync("/api/orders", Ct)).StatusCode);
    }

    [Fact]
    public async Task OtherOrdersEndpoints_AreNotRateLimitedByTheListPolicy()
    {
        var client = ClientFor($"byid-{Guid.NewGuid():N}");

        for (var i = 0; i <= TinyLimitsApiFactory.PermitLimit + 1; i++)
        {
            Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync($"/api/orders/{Guid.NewGuid()}", Ct)).StatusCode);
        }
    }

    [Fact]
    public async Task List_Anonymous_Returns401NotRateLimited()
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Add(ApiFactory.AnonymousHeader, "1");

        for (var i = 0; i <= TinyLimitsApiFactory.PermitLimit + 1; i++)
        {
            Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/api/orders", Ct)).StatusCode);
        }
    }

    [Fact]
    public async Task Database_CommandTimeoutFromOptions_IsAppliedToTheContext()
    {
        using var scope = factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();

        Assert.Equal(1, db.Database.GetCommandTimeout());

        // The timeout is enforced by the real server: a command that outlives it fails instead of hanging.
        var ex = await Assert.ThrowsAnyAsync<Exception>(() => db.Database.ExecuteSqlRawAsync("SELECT pg_sleep(5)", Ct));
        Assert.True(ex is NpgsqlException || ex.InnerException is NpgsqlException || ex is TimeoutException, ex.GetType().Name);
    }
}
