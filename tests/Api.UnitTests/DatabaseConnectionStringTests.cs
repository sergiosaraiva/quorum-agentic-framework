using Api.Common;
using Npgsql;

namespace Api.UnitTests;

/// <summary>TQ-016: the configured pool size is applied to the connection string through the Npgsql builder.</summary>
public class DatabaseConnectionStringTests
{
    private const string Base = "Host=db.invalid;Database=app;Username=app;Password=${DB_PASSWORD}";

    [Theory]
    [InlineData(1)]
    [InlineData(20)]
    [InlineData(1000)]
    public void WithMaxPoolSize_SetsTheMaximumPoolSize(int size)
    {
        var result = DatabaseConnectionString.WithMaxPoolSize(Base, size);

        Assert.Equal(size, new NpgsqlConnectionStringBuilder(result).MaxPoolSize);
    }

    [Fact]
    public void WithMaxPoolSize_KeepsTheOtherSettings()
    {
        var result = new NpgsqlConnectionStringBuilder(DatabaseConnectionString.WithMaxPoolSize(Base, 7));

        Assert.Equal("db.invalid", result.Host);
        Assert.Equal("app", result.Database);
        Assert.Equal("app", result.Username);
        Assert.Equal("${DB_PASSWORD}", result.Password);
    }

    [Fact]
    public void WithMaxPoolSize_OptionWinsOverAValueInTheConnectionString()
    {
        var result = DatabaseConnectionString.WithMaxPoolSize(Base + ";Maximum Pool Size=500", 12);

        Assert.Equal(12, new NpgsqlConnectionStringBuilder(result).MaxPoolSize);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("  ")]
    public void WithMaxPoolSize_MissingConnectionString_IsPassedThrough(string? connectionString) =>
        Assert.Equal(connectionString, DatabaseConnectionString.WithMaxPoolSize(connectionString, 20));
}
