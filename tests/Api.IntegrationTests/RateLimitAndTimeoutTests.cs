using System.Net;
using System.Text.Json;
using Api.Common;
using Api.Features.Orders;
using Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;
using Npgsql;

namespace Api.IntegrationTests;

/// <summary>TQ-007 (OD-018): per-user rate limit on the list endpoint and the database command timeout, from Options.</summary>
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
        var delta = limited.Headers.RetryAfter?.Delta;
        Assert.NotNull(delta);
        Assert.True(delta > TimeSpan.Zero && delta <= TimeSpan.FromSeconds(TinyLimitsApiFactory.WindowSeconds), delta.ToString());
        using var doc = JsonDocument.Parse(await limited.Content.ReadAsStringAsync(Ct));
        Assert.Equal(429, doc.RootElement.GetProperty("status").GetInt32());
        Assert.Equal(OrdersRateLimit.TooManyRequestsTitle, doc.RootElement.GetProperty("title").GetString());
        // Same shape as every other problem response (written through IProblemDetailsService).
        Assert.Equal(OrdersRateLimit.TooManyRequestsType, doc.RootElement.GetProperty("type").GetString());
        Assert.False(string.IsNullOrEmpty(doc.RootElement.GetProperty("traceId").GetString()));
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

    // TQ-015 (OD-025): a command timeout is a 503 problem response with fixed text; any other exception stays a 500.
    [Fact]
    public async Task CommandTimeout_Returns503ProblemDetailsWithFixedTextAndNoExceptionText()
    {
        var response = await factory.CreateClient().GetAsync(TinyLimitsApiFactory.SlowRoute, Ct);

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
        var text = await response.Content.ReadAsStringAsync(Ct);
        using var doc = JsonDocument.Parse(text);
        Assert.Equal(503, doc.RootElement.GetProperty("status").GetInt32());
        Assert.Equal(DatabaseTimeoutProblem.Title, doc.RootElement.GetProperty("title").GetString());
        Assert.Equal(DatabaseTimeoutProblem.Detail, doc.RootElement.GetProperty("detail").GetString());
        Assert.Equal(DatabaseTimeoutProblem.Type, doc.RootElement.GetProperty("type").GetString());
        Assert.False(string.IsNullOrEmpty(doc.RootElement.GetProperty("traceId").GetString()));
        foreach (var leak in new[] { "pg_sleep", "Npgsql", "TimeoutException", "57014", "Exception", "   at " })
        {
            Assert.DoesNotContain(leak, text, StringComparison.Ordinal);
        }
    }

    [Fact]
    public async Task OtherException_StillReturns500WithoutExceptionText()
    {
        var response = await factory.CreateClient().GetAsync(TinyLimitsApiFactory.BoomRoute, Ct);

        Assert.Equal(HttpStatusCode.InternalServerError, response.StatusCode);
        var text = await response.Content.ReadAsStringAsync(Ct);
        Assert.DoesNotContain(TinyLimitsApiFactory.BoomMessage, text, StringComparison.Ordinal);
        Assert.DoesNotContain(DatabaseTimeoutProblem.Detail, text, StringComparison.Ordinal);
    }

    // ValidateOnStart proof: an invalid value stops the host before it serves anything.
    [Theory]
    [InlineData("RateLimiting:PermitLimit", "0")]
    [InlineData("RateLimiting:WindowSeconds", "0")]
    [InlineData("Database:CommandTimeoutSeconds", "0")]
    [InlineData("Orders:MaxPageNumber", "0")]
    public void Host_InvalidOptionValue_FailsAtStart(string key, string value)
    {
        using var invalid = new InvalidOptionsApiFactory(key, value);

        var ex = Assert.ThrowsAny<Exception>(() => invalid.CreateClient());

        Assert.Contains(Chain(ex), e => e is OptionsValidationException);
    }

    private static IEnumerable<Exception> Chain(Exception ex)
    {
        for (var e = ex; e is not null; e = e.InnerException)
        {
            yield return e;
        }
    }
}
