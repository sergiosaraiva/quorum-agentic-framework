using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Api.Features.Orders;
using Api.Options;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace Api.IntegrationTests;

/// <summary>TQ-005 (OD-016): explicit paging parameter parsing and the BadHttpRequestException mapping.</summary>
public class OrdersListParsingTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    private static CancellationToken Ct => TestContext.Current.CancellationToken;

    [Theory]
    [InlineData("page=abc", "page")]
    [InlineData("page=1.5", "page")]
    [InlineData("page=1.0", "page")]
    [InlineData("page=99999999999", "page")]
    [InlineData("page=-99999999999", "page")]
    [InlineData("page=5%00", "page")]
    [InlineData("pageSize=%005", "pageSize")]
    [InlineData("pageSize=abc", "pageSize")]
    [InlineData("pageSize=2147483648", "pageSize")]
    [InlineData("page=1&pageSize=x%00y", "pageSize")]
    public async Task List_MalformedPaging_ReturnsValidationProblemKeyedByParameter(string query, string expectedKey)
    {
        var response = await factory.CreateClient().GetAsync("/api/orders?" + query, Ct);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
        using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync(Ct));
        var errors = doc.RootElement.GetProperty("errors");
        Assert.True(errors.TryGetProperty(expectedKey, out var messages));
        Assert.Matches("^(page|pageSize) must be a whole number", messages[0].GetString());
    }

    [Fact]
    public async Task List_MalformedPagingAndFilters_ReportsAllKeysAtOnce()
    {
        var response = await factory.CreateClient().GetAsync("/api/orders?page=abc&pageSize=def&createdFrom=nope", Ct);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync(Ct));
        var keys = doc.RootElement.GetProperty("errors").EnumerateObject().Select(p => p.Name).Order(StringComparer.Ordinal).ToList();
        Assert.Equal(["createdFrom", "page", "pageSize"], keys);
    }

    [Theory]
    [InlineData("page=-5", 1)]
    [InlineData("page=0", 1)]
    [InlineData("page=%2B3", 3)]
    [InlineData("page=%203%20", 3)]
    public async Task List_NonPositivePage_IsClampedNotRejected(string query, int expectedPage)
    {
        var response = await factory.CreateClient().GetAsync("/api/orders?" + query, Ct);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadFromJsonAsync<PagedResponse<OrderResponse>>(Ct);
        Assert.Equal(expectedPage, body!.Page);
    }

    [Theory]
    [InlineData("pageSize=0", 1)]
    [InlineData("pageSize=-7", 1)]
    [InlineData("pageSize=2147483647", -1)] // -1: the configured maximum
    public async Task List_PageSizeOutOfRange_IsClampedNotRejected(string query, int expectedSize)
    {
        var max = factory.Services.GetRequiredService<IOptions<OrdersOptions>>().Value.MaxPageSize;

        var response = await factory.CreateClient().GetAsync("/api/orders?" + query, Ct);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadFromJsonAsync<PagedResponse<OrderResponse>>(Ct);
        Assert.Equal(expectedSize == -1 ? max : expectedSize, body!.PageSize);
    }

    [Theory]
    [InlineData("page=", 1)]
    [InlineData("page=%20", 1)]
    public async Task List_EmptyPaging_UsesDefaults(string query, int expectedPage)
    {
        var response = await factory.CreateClient().GetAsync("/api/orders?" + query, Ct);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadFromJsonAsync<PagedResponse<OrderResponse>>(Ct);
        Assert.Equal(expectedPage, body!.Page);
        Assert.Equal(factory.Services.GetRequiredService<IOptions<OrdersOptions>>().Value.DefaultPageSize, body.PageSize);
    }

    [Fact]
    public async Task List_PagingErrorDoesNotEchoInput()
    {
        var response = await factory.CreateClient().GetAsync("/api/orders?page=zzsecretzz", Ct);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.DoesNotContain("zzsecretzz", await response.Content.ReadAsStringAsync(Ct), StringComparison.Ordinal);
    }
}

/// <summary>
/// TQ-005 (OD-016): in Development the framework throws BadHttpRequestException for a malformed request instead of answering 400.
/// The exception handler must map it to its own client-error status with problem details, never a 500.
/// </summary>
public class BadHttpRequestMappingTests
{
    [Fact]
    public async Task Post_InvalidJsonBody_InDevelopment_Returns400ProblemDetailsWithoutExceptionText()
    {
        await using var factory = new DevelopmentApiFactory();
        await factory.InitializeAsync();
        var body = new StringContent("{not json", Encoding.UTF8, "application/json");

        var response = await factory.CreateClient().PostAsync("/api/orders", body, TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
        var text = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        using var doc = JsonDocument.Parse(text);
        Assert.Equal(400, doc.RootElement.GetProperty("status").GetInt32());
        Assert.DoesNotContain("BadHttpRequestException", text, StringComparison.Ordinal);
        Assert.DoesNotContain("not json", text, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ExceptionHandler_StatusCodeSelector_OnlyBadRequestsBecomeClientErrors()
    {
        // The selector must not turn every exception into a client error: a service failure stays a 500.
        await using var factory = new DevelopmentApiFactory();
        await factory.InitializeAsync();
        var options = factory.Services.GetRequiredService<IOptions<Microsoft.AspNetCore.Builder.ExceptionHandlerOptions>>().Value;

        Assert.NotNull(options.StatusCodeSelector);
        Assert.Equal(500, options.StatusCodeSelector!(new InvalidOperationException()));
        Assert.Equal(400, options.StatusCodeSelector(new Microsoft.AspNetCore.Http.BadHttpRequestException("x")));
        Assert.Equal(413, options.StatusCodeSelector(new Microsoft.AspNetCore.Http.BadHttpRequestException("x", 413)));
    }
}
