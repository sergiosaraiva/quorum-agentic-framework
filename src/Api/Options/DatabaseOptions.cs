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
}
