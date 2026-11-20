using System.ComponentModel.DataAnnotations;

namespace Api.Options;

/// <summary>Database client settings. The connection string itself stays under <c>ConnectionStrings:Default</c>.</summary>
public sealed class DatabaseOptions
{
    public const string SectionName = "Database";

    /// <summary>
    /// Command timeout in seconds for every EF Core command (TQ-007, OD-018): bounds a slow order search. The default is 10
    /// (TQ-015, OD-025): the worst measured search took 0.4 to 1.6 seconds at 1M rows. A migration job sets its own larger value.
    /// </summary>
    [Range(1, 600)]
    public int CommandTimeoutSeconds { get; init; } = 10;

    /// <summary>Value of the <c>Retry-After</c> header, in seconds, on the 503 answered for a command timeout (OD-029). A chosen default.</summary>
    [Range(1, 3600)]
    public int RetryAfterSeconds { get; init; } = 5;

    /// <summary>
    /// Npgsql <c>Maximum Pool Size</c>: the most connections this process opens to the database (TQ-016, OD-030). Set it so that
    /// instances times this value stays below the server's <c>max_connections</c> (default 100). The default 20 comes from a
    /// single-machine measurement (OD-030): the Npgsql default of 100 reached the server limit and answered 500; 20 kept the
    /// connection count bounded and turned overload into the 503 with <c>Retry-After</c>. Re-measure on the deployment target.
    /// </summary>
    [Range(1, 1000)]
    public int MaxPoolSize { get; init; } = 20;
}
