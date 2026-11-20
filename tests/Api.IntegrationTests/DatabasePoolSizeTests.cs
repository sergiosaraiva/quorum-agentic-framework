using Infrastructure.Persistence;
using Microsoft.AspNetCore.Hosting;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;

namespace Api.IntegrationTests;

/// <summary>TQ-016: <c>Database:MaxPoolSize</c> reaches the connection string the DbContext really uses.</summary>
public class DatabasePoolSizeTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    [Fact]
    public void DbContext_WithoutOverride_UsesTheConfiguredDefaultPoolSize()
    {
        using var scope = factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();

        var size = new NpgsqlConnectionStringBuilder(db.Database.GetConnectionString()).MaxPoolSize;

        Assert.Equal(new Api.Options.DatabaseOptions().MaxPoolSize, size);
    }

    [Fact]
    public void DbContext_WithConfiguredPoolSize_UsesIt()
    {
        using var configured = factory.WithWebHostBuilder(b => b.UseSetting("Database:MaxPoolSize", "7"));

        using var scope = configured.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();

        Assert.Equal(7, new NpgsqlConnectionStringBuilder(db.Database.GetConnectionString()).MaxPoolSize);
    }
}
