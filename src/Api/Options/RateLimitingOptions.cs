using System.ComponentModel.DataAnnotations;

namespace Api.Options;

/// <summary>Per-user rate limit of the order list and search endpoint (TQ-007, OD-018). A fixed window, no queueing.</summary>
public sealed class RateLimitingOptions
{
    public const string SectionName = "RateLimiting";

    /// <summary>Requests one user may make per window.</summary>
    [Range(1, 100_000)]
    public int PermitLimit { get; init; } = 60;

    /// <summary>
    /// Requests of one user that may run at the same time on the limited endpoint; any further one is a 429 (no queue).
    /// A chosen default under the owner's delegation (OD-029), not a measured limit. Bounds the database work one user can hold.
    /// </summary>
    [Range(1, 1000)]
    public int ConcurrentRequestsPerUser { get; init; } = 4;

    /// <summary>Window length in seconds.</summary>
    [Range(1, 86_400)]
    public int WindowSeconds { get; init; } = 60;
}
