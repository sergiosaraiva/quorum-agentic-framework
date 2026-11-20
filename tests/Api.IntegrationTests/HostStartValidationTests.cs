using Microsoft.Extensions.Options;

namespace Api.IntegrationTests;

/// <summary>
/// Hosts expected to fail at start run alone: <c>WebApplicationFactory</c> hooks the program entry point for the whole
/// process, so a host that starts in parallel with another can take the other's startup exception, and the
/// <c>OptionsValidationException</c> this test looks for is then missing from the chain (seen once in CI and once locally).
/// </summary>
[CollectionDefinition("host-start", DisableParallelization = true)]
public sealed class HostStartCollection;

[Collection("host-start")]
public class HostStartValidationTests
{
    // ValidateOnStart proof: an invalid value stops the host before it serves anything.
    [Theory]
    [InlineData("RateLimiting:PermitLimit", "0")]
    [InlineData("RateLimiting:WindowSeconds", "0")]
    [InlineData("Database:CommandTimeoutSeconds", "0")]
    [InlineData("Orders:MaxPageNumber", "0")]
    [InlineData("RateLimiting:ConcurrentRequestsPerUser", "0")]
    [InlineData("Database:RetryAfterSeconds", "0")]
    [InlineData("Database:MaxPoolSize", "0")]
    [InlineData("Database:MaxPoolSize", "1001")]
    [InlineData("Database:ConnectionWaitTimeoutSeconds", "0")]
    [InlineData("Database:ConnectionWaitTimeoutSeconds", "301")]
    public void Host_InvalidOptionValue_FailsAtStart(string key, string value)
    {
        using var invalid = new InvalidOptionsApiFactory(key, value);

        var ex = Assert.ThrowsAny<Exception>(() => invalid.CreateClient());

        var chain = Chain(ex).ToList();
        var validation = Assert.Single(chain.OfType<OptionsValidationException>().Take(1));
        Assert.Contains(key[(key.IndexOf(':') + 1)..], validation.Message, StringComparison.Ordinal);
    }

    /// <summary>Walks inner exceptions and flattens aggregates, so the validation failure is found wherever the host wrapped it.</summary>
    private static IEnumerable<Exception> Chain(Exception? ex)
    {
        if (ex is null)
        {
            yield break;
        }

        yield return ex;
        var inner = ex is AggregateException aggregate ? aggregate.InnerExceptions : ex.InnerException is { } one ? [one] : [];
        foreach (var child in inner)
        {
            foreach (var e in Chain(child))
            {
                yield return e;
            }
        }
    }
}
