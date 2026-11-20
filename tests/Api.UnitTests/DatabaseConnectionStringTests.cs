using Api.Common;
using Npgsql;

namespace Api.UnitTests;

/// <summary>TQ-016: the configured pool settings are applied to the connection string through the Npgsql builder.</summary>
public class DatabaseConnectionStringTests
{
    private const string Base = "Host=db.invalid;Database=app;Username=app;Password=${DB_PASSWORD}";

    private static NpgsqlConnectionStringBuilder Apply(string connectionString, int size = 20, int wait = 5) =>
        new(DatabaseConnectionString.WithPoolSettings(connectionString, size, wait));

    [Theory]
    [InlineData(1)]
    [InlineData(20)]
    [InlineData(1000)]
    public void WithPoolSettings_SetsTheMaximumPoolSize(int size) =>
        Assert.Equal(size, Apply(Base, size).MaxPoolSize);

    [Theory]
    [InlineData(1)]
    [InlineData(5)]
    [InlineData(300)]
    public void WithPoolSettings_SetsTheConnectionWaitTimeout(int wait) =>
        Assert.Equal(wait, Apply(Base, wait: wait).Timeout);

    [Fact]
    public void WithPoolSettings_KeepsTheOtherSettings()
    {
        var result = Apply(Base, 7);

        Assert.Equal("db.invalid", result.Host);
        Assert.Equal("app", result.Database);
        Assert.Equal("app", result.Username);
        Assert.Equal("${DB_PASSWORD}", result.Password);
    }

    [Fact]
    public void WithPoolSettings_OptionsWinOverValuesInTheConnectionString()
    {
        var result = Apply(Base + ";Maximum Pool Size=500;Timeout=60", 12, 3);

        Assert.Equal(12, result.MaxPoolSize);
        Assert.Equal(3, result.Timeout);
    }

    [Fact]
    public void WithPoolSettings_PoolingFalseInTheString_DoesNotDisableTheBound() =>
        Assert.True(Apply(Base + ";Pooling=false").Pooling);

    [Fact]
    public void WithPoolSettings_MinimumPoolSizeAboveTheMaximum_IsCappedAtTheMaximum()
    {
        var result = Apply(Base + ";Minimum Pool Size=50", 10);

        Assert.Equal(10, result.MinPoolSize);
        Assert.Equal(10, result.MaxPoolSize);
    }

    [Fact]
    public void WithPoolSettings_MinimumPoolSizeBelowTheMaximum_IsKept() =>
        Assert.Equal(3, Apply(Base + ";Minimum Pool Size=3", 10).MinPoolSize);

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("  ")]
    public void WithPoolSettings_MissingConnectionString_IsPassedThrough(string? connectionString) =>
        Assert.Equal(connectionString, DatabaseConnectionString.WithPoolSettings(connectionString, 20, 5));
}
