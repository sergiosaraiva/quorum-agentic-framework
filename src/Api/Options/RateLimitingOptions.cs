using System.ComponentModel.DataAnnotations;

namespace Api.Options;

/// <summary>Per-user rate limit of the order list and search endpoint (TQ-007). A fixed window, no queueing.</summary>
public sealed class RateLimitingOptions
{
    public const string SectionName = "RateLimiting";

    /// <summary>Requests one user may make per window.</summary>
    [Range(1, 100_000)]
    public int PermitLimit { get; init; } = 60;

    /// <summary>Window length in seconds.</summary>
    [Range(1, 86_400)]
    public int WindowSeconds { get; init; } = 60;
}
