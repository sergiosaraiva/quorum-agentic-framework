using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Api.Features.Orders;
using Api.Options;
using Infrastructure.Persistence;
using Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace Api.IntegrationTests;

/// <summary>VS-004 R1 list filters against real PostgreSQL. Each test seeds its own rows (explicit CreatedAt) under a unique name token or its own far-past year.</summary>
public class OrdersSearchTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    private static string Token() => $"zq{Guid.NewGuid():N}";

    private static DateTimeOffset Utc(int year, int month, int day, int hour = 0, int minute = 0, int second = 0, int microsecond = 0) =>
        new DateTimeOffset(year, month, day, hour, minute, second, TimeSpan.Zero).AddTicks(microsecond * 10L);

    private async Task<Guid> SeedAsync(string customerName, DateTimeOffset createdAt, Guid? id = null)
    {
        using var scope = factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var order = new Order
        {
            Id = id ?? Guid.CreateVersion7(),
            CustomerName = customerName,
            TotalAmount = 10m,
            Status = "open",
            CreatedAt = createdAt,
            UpdatedAt = createdAt,
        };
        db.Orders.Add(order);
        await db.SaveChangesAsync(Ct);
        return order.Id;
    }

    private async Task<PagedResponse<OrderResponse>> ListAsync(string query)
    {
        var response = await factory.CreateClient().GetAsync("/api/orders" + query, Ct);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadFromJsonAsync<PagedResponse<OrderResponse>>(Ct);
        Assert.NotNull(body);
        return body;
    }

    private static HashSet<Guid> Ids(PagedResponse<OrderResponse> page) => page.Items.Select(i => i.Id).ToHashSet();

    [Fact]
    public async Task List_NoFilter_ReturnsSameAsUnfilteredOrderAndTotal()
    {
        var token = Token();
        var older = await SeedAsync($"{token} a", Utc(1990, 1, 1));
        var newer = await SeedAsync($"{token} b", Utc(1990, 1, 2));
        var pageSize = factory.Services.GetRequiredService<IOptions<OrdersOptions>>().Value.DefaultPageSize;
        int expectedTotal;
        List<Guid> expectedIds;
        using (var scope = factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            expectedTotal = await db.Orders.CountAsync(Ct);
            expectedIds = await db.Orders.OrderByDescending(o => o.CreatedAt).ThenBy(o => o.Id)
                .Take(pageSize).Select(o => o.Id).ToListAsync(Ct);
        }

        var unfiltered = await ListAsync("");
        var emptyFilters = await ListAsync("?createdFrom=&createdTo=&customerName=");

        // Against the database directly, so a default predicate added for "no filter" would be caught.
        Assert.Equal(expectedTotal, unfiltered.TotalCount);
        Assert.Equal(expectedIds, unfiltered.Items.Select(i => i.Id));
        Assert.Equal(unfiltered.TotalCount, emptyFilters.TotalCount);
        Assert.Equal(unfiltered.Items.Select(i => i.Id), emptyFilters.Items.Select(i => i.Id));
        // Seeded rows are the oldest, so check their order through the name filter, not the first page.
        var seeded = await ListAsync($"?customerName={token}");
        Assert.Equal([newer, older], seeded.Items.Select(i => i.Id));
    }

    [Fact]
    public async Task List_FilterMatchesNothing_ReturnsEmptyItemsAndZeroTotal()
    {
        var page = await ListAsync($"?customerName={Token()}");

        Assert.Empty(page.Items);
        Assert.Equal(0, page.TotalCount);
    }

    [Fact]
    public async Task List_DateRangeAndName_ReturnsOnlyOrdersMatchingBoth()
    {
        var token = Token();
        var match = await SeedAsync($"{token} match", Utc(1991, 6, 15, 12));
        await SeedAsync($"{token} too early", Utc(1991, 6, 9, 12));
        await SeedAsync($"other {Token()}", Utc(1991, 6, 15, 12));

        var page = await ListAsync($"?createdFrom=1991-06-10&createdTo=1991-06-20&customerName={token}");

        Assert.Equal([match], Ids(page));
        Assert.Equal(1, page.TotalCount);
    }

    [Fact]
    public async Task List_FilteredSecondPage_TotalCountIsFilteredSet()
    {
        var token = Token();
        for (var i = 0; i < 3; i++)
        {
            await SeedAsync($"{token} {i}", Utc(1992, 3, 1, i));
        }

        await SeedAsync($"unrelated {Token()}", Utc(1992, 3, 1));

        var page = await ListAsync($"?customerName={token}&pageSize=2&page=2");

        Assert.Single(page.Items);
        Assert.Equal(3, page.TotalCount);
    }

    [Fact]
    public async Task List_FilteredHugePageSize_IsClampedToMaxPageSize()
    {
        var max = factory.Services.GetRequiredService<IOptions<OrdersOptions>>().Value.MaxPageSize;
        var token = Token();
        await SeedAsync($"{token} a", Utc(1993, 1, 1));

        var page = await ListAsync($"?customerName={token}&pageSize={int.MaxValue}");

        Assert.Equal(max, page.PageSize);
        Assert.Equal(1, page.TotalCount);
    }

    [Theory]
    [InlineData("createdFrom=2026-13-40", "createdFrom")]
    [InlineData("createdFrom=11/19/2026", "createdFrom")]
    [InlineData("createdTo=abc", "createdTo")]
    [InlineData("createdFrom=2026-11-20&createdTo=2026-11-19", "createdTo")]
    [InlineData("customerName=%00", "customerName")]
    [InlineData("customerName=ac%00me", "customerName")]
    public async Task List_InvalidFilter_ReturnsValidationProblem(string query, string expectedKey)
    {
        var response = await factory.CreateClient().GetAsync("/api/orders?" + query, Ct);

        await AssertValidationProblemAsync(response, expectedKey);
    }

    [Fact]
    public async Task List_CustomerNameOver200Characters_ReturnsValidationProblem()
    {
        var response = await factory.CreateClient().GetAsync(
            "/api/orders?customerName=" + new string('x', Order.CustomerNameMaxLength + 1), Ct);

        await AssertValidationProblemAsync(response, "customerName");
    }

    [Fact]
    public async Task List_SeveralInvalidFilters_ReportsAllErrorsAtOnce()
    {
        var response = await factory.CreateClient().GetAsync("/api/orders?createdFrom=abc&createdTo=def", Ct);

        var errors = await AssertValidationProblemAsync(response, "createdFrom");
        Assert.True(errors.TryGetProperty("createdTo", out _));
    }

    [Fact]
    public async Task List_InvalidFilters_ErrorKeysAreExactlyTheCamelCaseParameterNames()
    {
        var response = await factory.CreateClient().GetAsync(
            "/api/orders?createdFrom=abc&createdTo=def&customerName=" + new string('x', Order.CustomerNameMaxLength + 1), Ct);

        var errors = await AssertValidationProblemAsync(response, "createdFrom");
        var keys = errors.EnumerateObject().Select(p => p.Name).Order(StringComparer.Ordinal).ToList();
        Assert.Equal(["createdFrom", "createdTo", "customerName"], keys);
    }

    private static async Task<JsonElement> AssertValidationProblemAsync(HttpResponseMessage response, string expectedKey)
    {
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
        using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync(Ct));
        var errors = doc.RootElement.GetProperty("errors").Clone();
        Assert.True(errors.TryGetProperty(expectedKey, out _));
        return errors;
    }

    [Fact]
    public async Task List_FilterWithoutCredentials_ReturnsUnauthorized()
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Add(ApiFactory.AnonymousHeader, "1");

        var response = await client.GetAsync("/api/orders?customerName=x", Ct);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task List_DateRange_BoundsAreInclusiveUtcDays()
    {
        // Own year 1994: from 1994-05-10, to 1994-05-12.
        var firstInstant = await SeedAsync("in first", Utc(1994, 5, 10, 0, 0, 0));
        var lastInstant = await SeedAsync("in last", Utc(1994, 5, 12, 23, 59, 59, 999999));
        var justBefore = await SeedAsync("out before", Utc(1994, 5, 9, 23, 59, 59, 999999));
        var justAfter = await SeedAsync("out after", Utc(1994, 5, 13, 0, 0, 0));

        var range = Ids(await ListAsync("?pageSize=1000&createdFrom=1994-05-10&createdTo=1994-05-12"));
        var fromOnly = Ids(await ListAsync("?pageSize=1000&createdFrom=1994-05-10"));
        var toOnly = Ids(await ListAsync("?pageSize=1000&createdTo=1994-05-12"));

        Assert.Contains(firstInstant, range);
        Assert.Contains(lastInstant, range);
        Assert.DoesNotContain(justBefore, range);
        Assert.DoesNotContain(justAfter, range);
        Assert.Contains(justAfter, fromOnly);
        Assert.DoesNotContain(justBefore, fromOnly);
        Assert.Contains(justBefore, toOnly);
        Assert.Contains(lastInstant, toOnly);
        Assert.DoesNotContain(justAfter, toOnly);
    }

    [Fact]
    public async Task List_CreatedToMaxDate_MeansNoUpperBound()
    {
        var token = Token();
        var id = await SeedAsync($"{token} a", Utc(1995, 1, 1));

        var page = await ListAsync($"?customerName={token}&createdTo=9999-12-31");

        Assert.Equal([id], Ids(page));
    }

    [Fact]
    public async Task List_EqualCreatedAt_AreOrderedByIdAscending()
    {
        // Ids differ in the first byte, so PostgreSQL's uuid order equals the order of these hex strings.
        var suffix = Guid.NewGuid().ToString()[^12..];
        var low = Guid.Parse($"10000000-0000-0000-0000-{suffix}");
        var high = Guid.Parse($"20000000-0000-0000-0000-{suffix}");
        var token = Token();
        var sameInstant = Utc(1998, 4, 1, 8);
        // Insert the higher id first, so the physical row order cannot produce the expected order by accident.
        await SeedAsync($"{token} high", sameInstant, high);
        await SeedAsync($"{token} low", sameInstant, low);

        var page = await ListAsync($"?customerName={token}");

        Assert.Equal([low, high], page.Items.Select(i => i.Id));
    }

    [Theory]
    [InlineData("createdFrom=0001-01-01&createdTo=9999-12-31", true)]
    [InlineData("createdFrom=0001-01-01", true)]
    [InlineData("createdTo=9999-12-31", true)]
    [InlineData("createdTo=0001-01-01", false)]
    [InlineData("createdFrom=9999-12-31", false)]
    public async Task List_ExtremeDates_ReturnOkAndMatchByRange(string dates, bool expectRow)
    {
        var token = Token();
        var id = await SeedAsync($"{token} a", Utc(1999, 7, 1));

        var page = await ListAsync($"?customerName={token}&{dates}");

        Assert.Equal(expectRow ? [id] : [], Ids(page));
        Assert.Equal(expectRow ? 1 : 0, page.TotalCount);
    }

    [Fact]
    public async Task List_CustomerName_MatchesCaseInsensitiveSubstring()
    {
        var token = Token();
        var id = await SeedAsync($"{token} ACME Widgets", Utc(1996, 1, 1));

        foreach (var term in new[] { "acme", "WIDG", "me wi", token })
        {
            var page = await ListAsync($"?customerName={Uri.EscapeDataString(term)}");
            Assert.Contains(id, Ids(page));
        }
    }

    [Fact]
    public async Task List_CustomerNameAccented_MatchesCaseInsensitivelyInTestContainerLocale()
    {
        // Documents the container locale (TQ-006): the postgres image defaults to en_US.utf8.
        var token = Token();
        var id = await SeedAsync($"{token} ÉCOLE", Utc(1996, 2, 1));

        var page = await ListAsync($"?customerName={Uri.EscapeDataString(token + " école")}");

        Assert.Equal([id], Ids(page));
    }

    [Fact]
    public async Task List_CustomerName_WildcardsMatchLiterally()
    {
        var token = Token();
        var percent = await SeedAsync($"{token} 50% off", Utc(1997, 1, 1));
        await SeedAsync($"{token} 500 off", Utc(1997, 1, 2));
        var underscore = await SeedAsync($"{token} a_b", Utc(1997, 1, 3));
        await SeedAsync($"{token} axb", Utc(1997, 1, 4));
        var backslash = await SeedAsync($"{token} back\\slash", Utc(1997, 1, 5));
        await SeedAsync($"{token} backslash", Utc(1997, 1, 6));

        var percentPage = await ListAsync($"?customerName={Uri.EscapeDataString(token + " 50%")}");
        var underscorePage = await ListAsync($"?customerName={Uri.EscapeDataString(token + " a_b")}");
        var backslashPage = await ListAsync($"?customerName={Uri.EscapeDataString("k\\s")}&createdFrom=1997-01-01&createdTo=1997-01-06");
        var percentOnly = await ListAsync($"?customerName={Uri.EscapeDataString("%")}&createdFrom=1997-01-01&createdTo=1997-01-06");

        Assert.Equal([percent], Ids(percentPage));
        Assert.Equal([underscore], Ids(underscorePage));
        Assert.Equal([backslash], Ids(backslashPage));
        // "%" alone matches only names that contain a percent sign, not every name in range.
        Assert.Equal([percent], Ids(percentOnly));
    }
}
