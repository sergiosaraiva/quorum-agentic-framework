using System.ComponentModel.DataAnnotations;

namespace Api.Options;

/// <summary>Database client settings. The connection string itself stays under <c>ConnectionStrings:Default</c>.</summary>
public sealed class DatabaseOptions
{
    public const string SectionName = "Database";

    /// <summary>Command timeout in seconds for every EF Core command (TQ-007, OD-018): bounds a slow order search.</summary>
    [Range(1, 600)]
    public int CommandTimeoutSeconds { get; init; } = 30;
}
