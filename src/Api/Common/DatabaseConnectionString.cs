using Npgsql;

namespace Api.Common;

/// <summary>
/// Applies the pool settings of the <c>Database</c> options (<c>MaxPoolSize</c>, <c>ConnectionWaitTimeoutSeconds</c>; TQ-016, OD-030)
/// to the configured connection string. The connection string stays in configuration (<c>ConnectionStrings:Default</c>); only these
/// bounds are set from Options, so they are validated and tunable per deployment without editing the string. The options always win
/// over the same keys written in the string, and pooling is always on, so the bound cannot be switched off by <c>Pooling=false</c>.
/// </summary>
public static class DatabaseConnectionString
{
    public static string? WithPoolSettings(string? connectionString, int maxPoolSize, int connectionWaitTimeoutSeconds)
    {
        if (string.IsNullOrWhiteSpace(connectionString))
        {
            return connectionString;
        }

        var builder = new NpgsqlConnectionStringBuilder(connectionString)
        {
            Pooling = true,
            MaxPoolSize = maxPoolSize,
            Timeout = connectionWaitTimeoutSeconds,
        };
        // A minimum above the maximum would make the pool configuration invalid; cap it at the maximum.
        builder.MinPoolSize = Math.Min(builder.MinPoolSize, maxPoolSize);
        return builder.ConnectionString;
    }
}
