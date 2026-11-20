using Npgsql;

namespace Api.Common;

/// <summary>
/// Applies <c>Database:MaxPoolSize</c> (TQ-016) to the configured connection string. The connection string stays in
/// configuration (<c>ConnectionStrings:Default</c>); only the pool bound is set from Options, so it is validated and tunable per
/// deployment without editing the string. The option always wins over a <c>Maximum Pool Size</c> written in the string.
/// </summary>
public static class DatabaseConnectionString
{
    public static string? WithMaxPoolSize(string? connectionString, int maxPoolSize)
    {
        if (string.IsNullOrWhiteSpace(connectionString))
        {
            return connectionString;
        }

        return new NpgsqlConnectionStringBuilder(connectionString) { MaxPoolSize = maxPoolSize }.ConnectionString;
    }
}
