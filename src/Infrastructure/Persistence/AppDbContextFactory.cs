using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace Infrastructure.Persistence;

/// <summary>Design-time factory for `dotnet ef`; the connection string comes from the environment, never from source.</summary>
public sealed class AppDbContextFactory : IDesignTimeDbContextFactory<AppDbContext>
{
    public AppDbContext CreateDbContext(string[] args)
    {
        var connection = Environment.GetEnvironmentVariable("ConnectionStrings__Default")
            ?? "Host=localhost;Database=design_time_only";
        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseNpgsql(connection)
            .UseSnakeCaseNamingConvention()
            .Options;
        return new AppDbContext(options);
    }
}
