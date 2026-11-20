using System.Diagnostics;
using System.Globalization;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using Api.Features.Orders;
using Api.Options;
using Infrastructure.Persistence;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Npgsql;
using Testcontainers.PostgreSql;

namespace Api.IntegrationTests;

/// <summary>
/// TQ-016: a local, single-machine measurement of the order list at scale. NOT part of the normal run: every test here is
/// <c>Explicit</c>, so <c>dotnet test</c> skips it. Run it with the command in <c>tests/CLAUDE.md</c> (Gates). It seeds a lab
/// table with a set-based <c>generate_series</c> fill (skill scaling-performance-test-data), then drives the real API through
/// <c>WebApplicationFactory</c> (no network, authenticated test user, the per-user fixed-window limit raised and nothing else
/// changed: the real concurrency limit, command timeout and pool settings stay in force). The numbers are one data point from
/// one machine, never a production figure.
/// </summary>
public class LoadMeasurementTests
{
    // Parameters (environment variables, so no source edit is needed to change a run).
    private static int Rows => Env("QUORUM_LOAD_ROWS", 1_000_000);
    private static int Repetitions => Env("QUORUM_LOAD_REPS", 30);
    private static int Rounds => Env("QUORUM_LOAD_ROUNDS", 5);
    private static int? MaxPageNumberOverride => Env("QUORUM_LOAD_MAX_PAGE_NUMBER", 0) is var v and > 0 ? v : null;
    private static int[] PoolSizes => EnvList("QUORUM_LOAD_POOL_SIZES", "100,50,20,10");
    private static int[] UserCounts => EnvList("QUORUM_LOAD_USERS", "1,5,25,50");

    private const int Warmups = 3;
    private const int SweepMaxPageNumber = 10_000;

    // Lab data constants. The fixed timestamp keeps the fill reproducible (skill: scaling-performance-test-data).
    private const string FixedNow = "2026-11-20T00:00:00Z";
    private const int HistoryDays = 1095;
    private const int RecentWindowDays = 90;

    private static readonly string[] Given =
        ["Ana", "Ben", "Chen", "Dara", "Eli", "Fay", "Gus", "Hana", "Ivo", "Jun", "Kai", "Lea", "Mo", "Nia", "Omar", "Pia", "Quinn", "Ravi", "Sol", "Tess"];

    private static readonly string[] Family =
        ["Almeida", "Baker", "Chowdhury", "Dubois", "Evans", "Fischer", "Garcia", "Haddad", "Ito", "Jensen", "Kowalski", "Lopez", "Moreau", "Nakamura", "Okafor", "Petrov", "Quispe", "Rossi", "Silva", "Tanaka"];

    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    [Fact(Explicit = true)]
    public async Task Measure_OrderListLatencyAndConnectionPool()
    {
        var report = new StringBuilder();
        void Line(string text = "")
        {
            report.AppendLine(text);
            TestContext.Current.TestOutputHelper?.WriteLine(text);
        }

        await using var postgres = new PostgreSqlBuilder("postgres:16-alpine").Build();
        await postgres.StartAsync(Ct);
        var connectionString = postgres.GetConnectionString();

        await using (var migrator = new MeasurementHost(connectionString, poolSize: null, maxPageNumber: null))
        {
            using var scope = migrator.Services.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            db.Database.SetCommandTimeout(TimeSpan.FromMinutes(2));
            await db.Database.MigrateAsync(Ct);
        }

        var seedWatch = Stopwatch.StartNew();
        var dataset = await SeedAsync(connectionString, Rows);
        seedWatch.Stop();

        Line("# TQ-016 local load measurement (single machine, no network, seeded data)");
        Line();
        Line($"Machine: {Environment.ProcessorCount} logical CPUs, {GC.GetGCMemoryInfo().TotalAvailableMemoryBytes / (1024 * 1024 * 1024)} GiB visible memory, {RuntimeInformation.OSDescription}, {RuntimeInformation.FrameworkDescription}");
        Line($"Host load at start (/proc/loadavg, 1/5/15 min): {LoadAverage()}; the machine may be shared, so figures are noisy and pessimistic");
        Line($"Database: {dataset.ServerVersion}, max_connections={dataset.MaxConnections}, default server settings, one container, API in-process");
        Line($"Data: {dataset.Rows:N0} orders, {dataset.Customers:N0} distinct customers, created_at {dataset.MinCreated:yyyy-MM-dd} to {dataset.MaxCreated:yyyy-MM-dd}, table+indexes {dataset.TotalSizeMb} MB, seeded in {seedWatch.Elapsed.TotalSeconds:F1} s, ANALYZE run");
        Line($"Status mix: {dataset.StatusMix}");
        Line($"Parameters: repetitions={Repetitions} (after {Warmups} discarded warm-ups), rounds={Rounds}, pool sizes={string.Join("/", PoolSizes)}, users={string.Join("/", UserCounts)}");
        Line();

        // (a) Sequential latency at the real defaults (pool size and limits as shipped).
        await using var host = new MeasurementHost(connectionString, poolSize: null, MaxPageNumberOverride);
        var orders = host.Services.GetRequiredService<IOptions<OrdersOptions>>().Value;
        var limits = host.Services.GetRequiredService<IOptions<RateLimitingOptions>>().Value;
        var database = host.Services.GetRequiredService<IOptions<DatabaseOptions>>().Value;
        var size = orders.MaxPageSize;
        var deep = orders.MaxPageNumber;
        Line($"Settings under test: MaxPageNumber={deep}, MaxPageSize={size} (deepest offset {(long)(deep - 1) * size:N0} rows), ConcurrentRequestsPerUser={limits.ConcurrentRequestsPerUser}, CommandTimeoutSeconds={database.CommandTimeoutSeconds}, MaxPoolSize={database.MaxPoolSize}, ConnectionWaitTimeoutSeconds={database.ConnectionWaitTimeoutSeconds}");
        Line();

        var from = DateOnly.FromDateTime(DateTime.Parse(FixedNow, CultureInfo.InvariantCulture, DateTimeStyles.AdjustToUniversal)).AddDays(-RecentWindowDays);
        var to = DateOnly.FromDateTime(DateTime.Parse(FixedNow, CultureInfo.InvariantCulture, DateTimeStyles.AdjustToUniversal));
        var range = $"createdFrom={from:yyyy-MM-dd}&createdTo={to:yyyy-MM-dd}";
        var scenarios = new (string Name, string Query)[]
        {
            ("page 1, no filter", $"page=1&pageSize={size}"),
            ("deepest page, no filter", $"page={deep}&pageSize={size}"),
            ("page 1, selective customerName", $"page=1&pageSize={size}&customerName={dataset.SelectiveTerm}"),
            ("deepest page, selective customerName", $"page={deep}&pageSize={size}&customerName={dataset.SelectiveTerm}"),
            ("deepest page, broad customerName (family name)", $"page={deep}&pageSize={size}&customerName={dataset.BroadTerm}"),
            ("page 1, status=paid", $"page=1&pageSize={size}&status=paid"),
            ("deepest page, status=paid", $"page={deep}&pageSize={size}&status=paid"),
            ($"page 1, last {RecentWindowDays} days", $"page=1&pageSize={size}&{range}"),
            ($"deepest page, last {RecentWindowDays} days", $"page={deep}&pageSize={size}&{range}"),
        };

        var client = host.CreateClient();
        client.DefaultRequestHeaders.Add(ApiFactory.UserHeader, "measure-sequential");
        var results = new List<(string Name, LatencyStats Stats, int Total, int Items)>();
        foreach (var (name, query) in scenarios)
        {
            var times = new List<double>(Repetitions);
            var (total, items) = (0, 0);
            for (var i = 0; i < Warmups + Repetitions; i++)
            {
                var watch = Stopwatch.StartNew();
                var response = await client.GetAsync($"/api/orders?{query}", Ct);
                var body = await response.Content.ReadAsStringAsync(Ct);
                watch.Stop();
                Assert.Equal(HttpStatusCode.OK, response.StatusCode);
                if (i == 0)
                {
                    (total, items) = ReadCounts(body);
                }

                if (i >= Warmups)
                {
                    times.Add(watch.Elapsed.TotalMilliseconds);
                }
            }

            results.Add((name, LatencyStats.From(times), total, items));
        }

        Line("## (a) Sequential latency, one user, ms per request (including JSON read)");
        Line();
        Line("| Scenario | total matches | items on page | p50 | p95 | p99 | max |");
        Line("|---|---:|---:|---:|---:|---:|---:|");
        foreach (var (name, stats, total, items) in results)
        {
            Line($"| {name} | {total:N0} | {items} | {stats.P50:F0} | {stats.P95:F0} | {stats.P99:F0} | {stats.Max:F0} |");
        }

        Line();

        // (a2) Depth sweep: the offset cost without a filter, to size MaxPageNumber against the latency budget.
        Line($"## (a2) Depth sweep, no filter, pageSize={size}, ms per request");
        Line();
        Line("| page | offset (rows skipped) | p50 | p95 | p99 | max |");
        Line("|---:|---:|---:|---:|---:|---:|");
        // Its own host with a raised cap, so the curve shows the cost beyond the default cap too.
        await using var sweepHost = new MeasurementHost(connectionString, poolSize: null, SweepMaxPageNumber);
        var sweepClient = sweepHost.CreateClient();
        sweepClient.DefaultRequestHeaders.Add(ApiFactory.UserHeader, "measure-sweep");
        foreach (var page in new[] { 1, 500, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 7500, 10_000 })
        {
            var times = new List<double>(Repetitions);
            for (var i = 0; i < Warmups + Repetitions; i++)
            {
                var watch = Stopwatch.StartNew();
                var response = await sweepClient.GetAsync($"/api/orders?page={page}&pageSize={size}", Ct);
                await response.Content.ReadAsStringAsync(Ct);
                watch.Stop();
                Assert.Equal(HttpStatusCode.OK, response.StatusCode);
                if (i >= Warmups)
                {
                    times.Add(watch.Elapsed.TotalMilliseconds);
                }
            }

            var stats = LatencyStats.From(times);
            Line($"| {page} | {(long)(page - 1) * size:N0} | {stats.P50:F0} | {stats.P95:F0} | {stats.P99:F0} | {stats.Max:F0} |");
        }

        Line();

        // (b) Concurrency: K distinct users, each holding the allowed number of the slowest deep request at once.
        var slowest = results.Where(r => r.Name.StartsWith("deepest", StringComparison.Ordinal)).MaxBy(r => r.Stats.P95);
        var slowQuery = scenarios.First(s => s.Name == slowest.Name).Query;
        var perUser = limits.ConcurrentRequestsPerUser;
        Line($"## (b) Concurrency: K distinct users x {perUser} simultaneous requests of '{slowest.Name}' (the slowest deep scenario in (a)), {Rounds} rounds");
        Line();
        Line("| Pool size | users K | concurrent requests | 200 | 429 | 503 | 500/other | p50 | p95 | p99 | max | peak client connections | peak active | peak parallel workers | logged error causes |");
        Line("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|");
        foreach (var pool in PoolSizes)
        {
            foreach (var users in UserCounts)
            {
                NpgsqlConnection.ClearAllPools();
                await using var poolHost = new MeasurementHost(connectionString, pool, MaxPageNumberOverride);
                // Warm the host (JIT, first connections) with one request before sampling.
                var warm = poolHost.CreateClient();
                warm.DefaultRequestHeaders.Add(ApiFactory.UserHeader, "measure-warm");
                await warm.GetAsync("/api/orders?page=1&pageSize=1", Ct);

                using var sampler = new ConnectionSampler(connectionString);
                var counts = new Dictionary<string, int> { ["200"] = 0, ["429"] = 0, ["503"] = 0, ["other"] = 0 };
                var times = new List<double>();
                var clients = Enumerable.Range(0, users).Select(u =>
                {
                    var c = poolHost.CreateClient();
                    c.DefaultRequestHeaders.Add(ApiFactory.UserHeader, $"measure-user-{u}");
                    return c;
                }).ToArray();

                for (var round = 0; round < Rounds; round++)
                {
                    var gate = new TaskCompletionSource();
                    var tasks = clients.SelectMany(c => Enumerable.Range(0, perUser).Select(async _ =>
                    {
                        await gate.Task;
                        var watch = Stopwatch.StartNew();
                        var response = await c.GetAsync($"/api/orders?{slowQuery}", Ct);
                        await response.Content.ReadAsStringAsync(Ct);
                        watch.Stop();
                        return (Status: (int)response.StatusCode, Ms: watch.Elapsed.TotalMilliseconds);
                    })).ToArray();
                    gate.SetResult();
                    foreach (var (status, ms) in await Task.WhenAll(tasks))
                    {
                        var key = status is 200 or 429 or 503 ? status.ToString(CultureInfo.InvariantCulture) : "other";
                        counts[key]++;
                        if (status == 200)
                        {
                            times.Add(ms);
                        }
                    }
                }

                var stats = times.Count > 0 ? LatencyStats.From(times) : new LatencyStats(0, 0, 0, 0);
                var (peakConnections, peakActive, peakWorkers) = sampler.Peak();
                Line($"| {pool} | {users} | {users * perUser} | {counts["200"]} | {counts["429"]} | {counts["503"]} | {counts["other"]} | {stats.P50:F0} | {stats.P95:F0} | {stats.P99:F0} | {stats.Max:F0} | {peakConnections} | {peakActive} | {peakWorkers} | {poolHost.Errors.Summary()} |");
            }
        }

        Line();
        Line("Latency columns in (b) cover the 200 responses only. Single machine, in-process host (no network), one table shape, seeded data, default server settings: not a production figure.");

        // The runner hides the output of a passing test, so the report is also written to a file (TestResults/ is gitignored).
        var outPath = Environment.GetEnvironmentVariable("QUORUM_LOAD_OUT") is { Length: > 0 } custom
            ? custom
            : Path.Combine(Directory.GetCurrentDirectory(), "TestResults", "load-measurement.md");
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
        await File.WriteAllTextAsync(outPath, report.ToString(), Ct);
    }

    private static (int Total, int Items) ReadCounts(string json)
    {
        using var doc = System.Text.Json.JsonDocument.Parse(json);
        var root = doc.RootElement;
        return (root.GetProperty("totalCount").GetInt32(), root.GetProperty("items").GetArrayLength());
    }

    private static string LoadAverage() =>
        File.Exists("/proc/loadavg") ? string.Join("/", File.ReadAllText("/proc/loadavg").Split(' ').Take(3)) : "unavailable";

    private static int Env(string name, int fallback) =>
        int.TryParse(Environment.GetEnvironmentVariable(name), NumberStyles.None, CultureInfo.InvariantCulture, out var v) && v > 0 ? v : fallback;

    private static int[] EnvList(string name, string fallback) =>
        (Environment.GetEnvironmentVariable(name) is { Length: > 0 } raw ? raw : fallback)
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(s => int.Parse(s, CultureInfo.InvariantCulture)).ToArray();

    /// <summary>
    /// Set-based fill: skewed customers (heavy tail), skewed recent-heavy dates, five weighted statuses, integrity on, one
    /// seeded session, a fixed timestamp instead of now(). Ids are gen_random_uuid() (v4), not the application's v7: ids are
    /// not part of the list's access path beyond the tie-break, so this does not change the plans measured here.
    /// </summary>
    private static async Task<Dataset> SeedAsync(string connectionString, int rows)
    {
        var customers = Math.Max(1000, rows / 20);
        await using var conn = new NpgsqlConnection(connectionString);
        await conn.OpenAsync(Ct);

        async Task Exec(string sql, params (string Name, object Value)[] args)
        {
            await using var cmd = new NpgsqlCommand(sql, conn) { CommandTimeout = 1800 };
            foreach (var (n, v) in args)
            {
                cmd.Parameters.AddWithValue(n, v);
            }

            await cmd.ExecuteNonQueryAsync(Ct);
        }

        await Exec("SELECT setseed(0.42)");
        await Exec(
            """
            CREATE TEMP TABLE tmp_customer AS
            SELECT g AS rank,
                   (@given)[1 + (g % @givenCount)] || ' ' || (@family)[1 + ((g / @givenCount) % @familyCount)] || ' ' || lpad(g::text, 6, '0') AS name
            FROM generate_series(1, @customers) g
            """,
            ("given", Given), ("family", Family), ("givenCount", Given.Length), ("familyCount", Family.Length), ("customers", customers));
        await Exec(
            $"""
            INSERT INTO "order" (id, customer_name, total_amount, status, created_at, updated_at)
            SELECT gen_random_uuid(), c.name, round((r.amount * 5000)::numeric, 2),
                   CASE WHEN r.s < 0.40 THEN 'closed' WHEN r.s < 0.60 THEN 'shipped' WHEN r.s < 0.75 THEN 'paid'
                        WHEN r.s < 0.90 THEN 'placed' ELSE 'draft' END,
                   @fixed::timestamptz - (power(r.d, 1.5) * {HistoryDays} * interval '1 day'),
                   @fixed::timestamptz - (power(r.d, 1.5) * {HistoryDays} * interval '1 day')
            FROM (SELECT 1 + floor(power(random(), 3) * @customers)::int AS rank, random() AS s, random() AS d, random() AS amount
                  FROM generate_series(1, @rows)) r
            JOIN tmp_customer c ON c.rank = r.rank
            """,
            ("fixed", DateTimeOffset.Parse(FixedNow, CultureInfo.InvariantCulture)), ("customers", customers), ("rows", rows));
        await Exec("ANALYZE \"order\"");

        await using var q = new NpgsqlCommand(
            """
            SELECT (SELECT count(*) FROM "order"), (SELECT count(DISTINCT customer_name) FROM "order"),
                   (SELECT min(created_at) FROM "order"), (SELECT max(created_at) FROM "order"),
                   (SELECT pg_total_relation_size('"order"') / 1048576), version(), current_setting('max_connections'),
                   (SELECT string_agg(status || ' ' || pct || '%', ', ' ORDER BY n DESC)
                      FROM (SELECT status, count(*) n, round(100.0 * count(*) / (SELECT count(*) FROM "order"), 1) pct
                            FROM "order" GROUP BY status) s)
            """, conn);
        await using var reader = await q.ExecuteReaderAsync(Ct);
        await reader.ReadAsync(Ct);
        var mid = customers / 2;
        return new Dataset(
            reader.GetInt64(0), reader.GetInt64(1), reader.GetFieldValue<DateTimeOffset>(2), reader.GetFieldValue<DateTimeOffset>(3),
            reader.GetInt64(4), reader.GetString(5).Split(',')[0], reader.GetString(6), reader.GetString(7),
            SelectiveTerm: mid.ToString("D6", CultureInfo.InvariantCulture), BroadTerm: Family[6]);
    }

    private sealed record Dataset(
        long Rows, long Customers, DateTimeOffset MinCreated, DateTimeOffset MaxCreated, long TotalSizeMb,
        string ServerVersion, string MaxConnections, string StatusMix, string SelectiveTerm, string BroadTerm);

    private readonly record struct LatencyStats(double P50, double P95, double P99, double Max)
    {
        public static LatencyStats From(List<double> samples)
        {
            var sorted = samples.Order().ToArray();
            double Rank(double p) => sorted[Math.Max(0, (int)Math.Ceiling(p * sorted.Length) - 1)];
            return new LatencyStats(Rank(0.50), Rank(0.95), Rank(0.99), sorted[^1]);
        }
    }

    /// <summary>Polls pg_stat_activity from a separate, unpooled connection: how many server connections the API held at peak.</summary>
    private sealed class ConnectionSampler : IDisposable
    {
        private readonly CancellationTokenSource _stop = new();
        private readonly Task _loop;
        private int _peak;
        private int _peakActive;
        private int _peakWorkers;
        private volatile string? _failure;

        public ConnectionSampler(string connectionString)
        {
            var builder = new NpgsqlConnectionStringBuilder(connectionString) { Pooling = false };
            var token = _stop.Token;
            _loop = Task.Run(async () =>
            {
                try
                {
                    await using var conn = new NpgsqlConnection(builder.ConnectionString);
                    await conn.OpenAsync(token);
                    await using var cmd = new NpgsqlCommand(
                        """
                        SELECT count(*) FILTER (WHERE backend_type = 'client backend'),
                               count(*) FILTER (WHERE backend_type = 'client backend' AND state = 'active'),
                               count(*) FILTER (WHERE backend_type = 'parallel worker')
                        FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid()
                        """, conn);
                    while (!token.IsCancellationRequested)
                    {
                        await using (var r = await cmd.ExecuteReaderAsync(token))
                        {
                            await r.ReadAsync(token);
                            _peak = Math.Max(_peak, r.GetInt32(0));
                            _peakActive = Math.Max(_peakActive, r.GetInt32(1));
                            _peakWorkers = Math.Max(_peakWorkers, r.GetInt32(2));
                        }

                        await Task.Delay(20, token);
                    }
                }
                catch (OperationCanceledException)
                {
                    // Stopped on purpose by Dispose.
                }
                catch (Exception ex)
                {
                    // A broken sampler must never show up as a number: the report prints the reason instead.
                    _failure = ex is PostgresException pg ? $"SQLSTATE {pg.SqlState}" : $"{ex.GetType().Name}: {ex.Message}";
                }
            });
        }

        /// <summary>The peaks as text, or <c>sampler failed: reason</c> when polling broke (never a misleading number).</summary>
        public (string Connections, string Active, string Workers) Peak() =>
            _failure is { } reason
                ? ($"sampler failed: {reason}", "n/a", "n/a")
                : (_peak.ToString(CultureInfo.InvariantCulture), _peakActive.ToString(CultureInfo.InvariantCulture), _peakWorkers.ToString(CultureInfo.InvariantCulture));

        public void Dispose()
        {
            _stop.Cancel();
            // The loop handles its own cancellation and records other faults, so a fault here is real and must surface.
            _loop.Wait(TimeSpan.FromSeconds(5));
            _stop.Dispose();
        }
    }

    /// <summary>Counts server-side errors by cause (SQLSTATE, or the exception type and message start), so a 500 or 503 can be explained.</summary>
    private sealed class ErrorTally : ILoggerProvider, ILogger
    {
        private readonly System.Collections.Concurrent.ConcurrentDictionary<string, int> _causes = new();

        public string Summary() => _causes.IsEmpty ? "none" : string.Join("; ", _causes.OrderByDescending(c => c.Value).Select(c => $"{c.Key} x{c.Value}"));

        public ILogger CreateLogger(string categoryName) => this;

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;

        public bool IsEnabled(LogLevel logLevel) => logLevel >= LogLevel.Error;

        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
        {
            if (exception is null || logLevel < LogLevel.Error)
            {
                return;
            }

            for (var e = exception; e is not null; e = e.InnerException)
            {
                if (e is PostgresException pg)
                {
                    _causes.AddOrUpdate($"SQLSTATE {pg.SqlState}", 1, (_, n) => n + 1);
                    return;
                }
            }

            var root = exception;
            while (root.InnerException is { } inner)
            {
                root = inner;
            }

            var message = root.Message.Length > 70 ? root.Message[..70] : root.Message;
            _causes.AddOrUpdate($"{root.GetType().Name}: {message}", 1, (_, n) => n + 1);
        }

        public void Dispose()
        {
        }
    }

    /// <summary>The real host against the lab database: only the per-user window limit is raised; the pool size is set when given.</summary>
    private sealed class MeasurementHost(string connectionString, int? poolSize, int? maxPageNumber) : WebApplicationFactory<Program>
    {
        public ErrorTally Errors { get; } = new();

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Testing");
            builder.ConfigureAppConfiguration((_, config) =>
            {
                var settings = new Dictionary<string, string?>
                {
                    ["ConnectionStrings:Default"] = connectionString,
                    ["Auth:Authority"] = "https://idp.invalid",
                    ["Auth:Audience"] = "test",
                    ["RateLimiting:PermitLimit"] = "100000",
                    ["Logging:LogLevel:Default"] = "Error", // keep the result table readable; errors still show
                };
                if (maxPageNumber is { } maxPage)
                {
                    settings["Orders:MaxPageNumber"] = maxPage.ToString(CultureInfo.InvariantCulture);
                }

                if (poolSize is { } pool)
                {
                    settings["Database:MaxPoolSize"] = pool.ToString(CultureInfo.InvariantCulture);
                }

                config.AddInMemoryCollection(settings);
            });
            builder.ConfigureServices(services =>
            {
                services.AddLogging(l => l.AddProvider(Errors));
                services.AddAuthentication(ApiFactory.TestScheme).AddScheme<AuthenticationSchemeOptions, TestAuthHandler>(ApiFactory.TestScheme, _ => { });
                services.PostConfigure<AuthenticationOptions>(o =>
                {
                    o.DefaultAuthenticateScheme = ApiFactory.TestScheme;
                    o.DefaultChallengeScheme = ApiFactory.TestScheme;
                });
            });
        }
    }
}
