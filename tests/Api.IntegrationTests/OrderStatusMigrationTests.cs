using Infrastructure.Persistence;
using Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql;
using Testcontainers.PostgreSql;

namespace Api.IntegrationTests;

/// <summary>
/// VS-005 (OD-004, TQ-010, BQ-009): the status migration maps real rows. ApiFactory migrates an empty database, so
/// these tests migrate to InitialCreate, insert rows in the old vocabulary and then migrate forward. Own container per test class.
/// </summary>
public class OrderStatusMigrationTests : IAsyncLifetime
{
    private const string InitialMigration = "20261118161849_InitialCreate";
    private const string StatusMigration = "20261120011427_AlignOrderStatusesToBc001";

    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    private readonly PostgreSqlContainer _postgres = new PostgreSqlBuilder("postgres:16-alpine").Build();

    public async ValueTask InitializeAsync() => await _postgres.StartAsync(Ct);

    public async ValueTask DisposeAsync() => await _postgres.DisposeAsync();

    private AppDbContext NewContext() =>
        new(new DbContextOptionsBuilder<AppDbContext>()
            .UseNpgsql(_postgres.GetConnectionString())
            .UseSnakeCaseNamingConvention()
            .Options);

    private async Task MigrateToAsync(string? target)
    {
        await using var db = NewContext();
        await db.GetService<IMigrator>().MigrateAsync(target, Ct);
    }

    private async Task InsertRawAsync(Guid id, string status)
    {
        await using var connection = new NpgsqlConnection(_postgres.GetConnectionString());
        await connection.OpenAsync(Ct);
        await using var command = new NpgsqlCommand(
            """
            INSERT INTO "order" (id, customer_name, total_amount, status, created_at, updated_at)
            VALUES (@id, 'Acme Ltd', 10.00, @status, now(), now())
            """, connection);
        command.Parameters.AddWithValue("id", id);
        command.Parameters.AddWithValue("status", status);
        await command.ExecuteNonQueryAsync(Ct);
    }

    private async Task<string?> StatusOfAsync(Guid id)
    {
        await using var connection = new NpgsqlConnection(_postgres.GetConnectionString());
        await connection.OpenAsync(Ct);
        await using var command = new NpgsqlCommand("""SELECT status FROM "order" WHERE id = @id""", connection);
        command.Parameters.AddWithValue("id", id);
        return (string?)await command.ExecuteScalarAsync(Ct);
    }

    private async Task<(string Name, decimal Total, DateTimeOffset Created, DateTimeOffset Updated)> OtherColumnsOfAsync(Guid id)
    {
        await using var connection = new NpgsqlConnection(_postgres.GetConnectionString());
        await connection.OpenAsync(Ct);
        await using var command = new NpgsqlCommand(
            """SELECT customer_name, total_amount, created_at, updated_at FROM "order" WHERE id = @id""", connection);
        command.Parameters.AddWithValue("id", id);
        await using var reader = await command.ExecuteReaderAsync(Ct);
        Assert.True(await reader.ReadAsync(Ct));
        return (reader.GetString(0), reader.GetDecimal(1), reader.GetFieldValue<DateTimeOffset>(2), reader.GetFieldValue<DateTimeOffset>(3));
    }

    [Fact]
    public async Task Model_MatchesTheMigrations_HasNoPendingChanges()
    {
        await using var db = NewContext();

        Assert.False(db.Database.HasPendingModelChanges());
    }

    [Fact]
    public async Task Up_OpenAndPaidRows_AreMappedToDraftAndPaid()
    {
        await MigrateToAsync(InitialMigration);
        var open = Guid.CreateVersion7();
        var paid = Guid.CreateVersion7();
        await InsertRawAsync(open, "open");
        await InsertRawAsync(paid, "paid");

        var openBefore = await OtherColumnsOfAsync(open);
        var paidBefore = await OtherColumnsOfAsync(paid);

        await MigrateToAsync(null);

        Assert.Equal(OrderStatuses.Draft, await StatusOfAsync(open));
        Assert.Equal(OrderStatuses.Paid, await StatusOfAsync(paid));
        Assert.Equal(openBefore, await OtherColumnsOfAsync(open));
        Assert.Equal(paidBefore, await OtherColumnsOfAsync(paid));
    }

    [Fact]
    public async Task Up_CancelledRowExists_RefusesToMigrateAndKeepsTheData()
    {
        await MigrateToAsync(InitialMigration);
        var cancelled = Guid.CreateVersion7();
        var open = Guid.CreateVersion7();
        await InsertRawAsync(cancelled, "cancelled");
        await InsertRawAsync(open, "open");

        var error = await Assert.ThrowsAnyAsync<Exception>(() => MigrateToAsync(null));

        Assert.Contains("BQ-009", error.ToString(), StringComparison.Ordinal);
        // Npgsql runs each migration in a transaction, so nothing was changed.
        Assert.Equal("cancelled", await StatusOfAsync(cancelled));
        Assert.Equal("open", await StatusOfAsync(open));
        await using var db = NewContext();
        Assert.Contains(InitialMigration, await db.Database.GetAppliedMigrationsAsync(Ct));
        Assert.DoesNotContain(StatusMigration, await db.Database.GetAppliedMigrationsAsync(Ct));
    }

    [Fact]
    public async Task Up_AfterMigration_ConstraintAcceptsBc001StatesAndRejectsTheOldVocabulary()
    {
        await MigrateToAsync(null);

        foreach (var state in OrderStatuses.All)
        {
            await InsertRawAsync(Guid.CreateVersion7(), state);
        }

        foreach (var old in new[] { "open", "cancelled", "Paid", "" })
        {
            var error = await Assert.ThrowsAsync<PostgresException>(() => InsertRawAsync(Guid.CreateVersion7(), old));
            Assert.Equal("ck_order_status", error.ConstraintName);
        }
    }

    [Fact]
    public async Task Down_Bc001Rows_AreMappedBackIntoTheOldVocabulary()
    {
        await MigrateToAsync(null);
        var expected = new Dictionary<string, string>
        {
            [OrderStatuses.Draft] = "open",
            [OrderStatuses.Placed] = "open",
            [OrderStatuses.Paid] = "paid",
            [OrderStatuses.Shipped] = "paid",
            [OrderStatuses.Closed] = "paid",
        };
        var ids = new Dictionary<string, Guid>();
        foreach (var state in expected.Keys)
        {
            ids[state] = Guid.CreateVersion7();
            await InsertRawAsync(ids[state], state);
        }

        await MigrateToAsync(InitialMigration);

        foreach (var (state, old) in expected)
        {
            Assert.Equal(old, await StatusOfAsync(ids[state]));
        }

        // The old constraint is back: the BC-001-only values are rejected and the old ones accepted.
        var error = await Assert.ThrowsAsync<PostgresException>(() => InsertRawAsync(Guid.CreateVersion7(), OrderStatuses.Draft));
        Assert.Equal("ck_order_status", error.ConstraintName);
        await InsertRawAsync(Guid.CreateVersion7(), "open");
    }
}
