using System.Net;
using System.Net.Http.Json;
using Api.Features.Orders;
using Api.Options;
using Infrastructure.Persistence.Entities;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Authorization.Infrastructure;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace Api.IntegrationTests;

public class OrdersEndpointsTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    [Fact]
    public async Task Create_ValidRequest_ReturnsCreatedAndIsReadable()
    {
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/orders", new CreateOrderRequest("Acme Ltd", 125.50m), TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        var created = await response.Content.ReadFromJsonAsync<OrderResponse>(TestContext.Current.CancellationToken);
        Assert.NotNull(created);
        var fetched = await client.GetFromJsonAsync<OrderResponse>($"/api/orders/{created.Id}", TestContext.Current.CancellationToken);
        Assert.Equal("Acme Ltd", fetched?.CustomerName);
        Assert.Equal(OrderStatuses.Draft, fetched?.Status);
    }

    [Fact]
    public async Task Create_InvalidAmount_ReturnsValidationProblem()
    {
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/orders", new CreateOrderRequest("Acme Ltd", 0m), TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task List_WithoutCredentials_ReturnsUnauthorized()
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Add(ApiFactory.AnonymousHeader, "1");

        var response = await client.GetAsync("/api/orders", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task HealthLive_WithoutCredentials_ReturnsOk()
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Add(ApiFactory.AnonymousHeader, "1");

        var response = await client.GetAsync("/health/live", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task Create_WithoutCredentials_ReturnsUnauthorized()
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Add(ApiFactory.AnonymousHeader, "1");

        var response = await client.PostAsJsonAsync("/api/orders", new CreateOrderRequest("Acme Ltd", 10m), TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task GetById_WithoutCredentials_ReturnsUnauthorized()
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Add(ApiFactory.AnonymousHeader, "1");

        var response = await client.GetAsync($"/api/orders/{Guid.NewGuid()}", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task Create_CustomerNameOf201Characters_ReturnsValidationProblem()
    {
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/orders", new CreateOrderRequest(new string('x', 201), 10m), TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task List_PageAtMaxPageNumber_ReturnsEmptyPageNotServerError()
    {
        var client = factory.CreateClient();
        var max = factory.Services.GetRequiredService<IOptions<OrdersOptions>>().Value;

        // The largest accepted offset: (MaxPageNumber - 1) * MaxPageSize (TQ-015, OD-025). Above the cap is a 400, see OrdersListParsingTests.
        var response = await client.GetAsync($"/api/orders?page={max.MaxPageNumber}&pageSize={max.MaxPageSize}", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task HealthReady_WithDatabase_ReturnsOk()
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Add(ApiFactory.AnonymousHeader, "1");

        var response = await client.GetAsync("/health/ready", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Theory]
    [InlineData("10.001")]
    [InlineData("0.015")]
    public async Task Create_MoreThanTwoDecimalPlaces_ReturnsValidationProblem(string amount)
    {
        var client = factory.CreateClient();
        var body = new StringContent($"{{\"customerName\":\"Acme Ltd\",\"totalAmount\":{amount}}}", System.Text.Encoding.UTF8, "application/json");

        var response = await client.PostAsync("/api/orders", body, TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        var text = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        Assert.Contains("\"totalAmount\"", text, StringComparison.Ordinal);
    }

    [Fact]
    public async Task Create_InvalidRequest_ErrorKeysAreExactlyTheCamelCaseMemberNames()
    {
        var client = factory.CreateClient();
        var body = new StringContent("{\"customerName\":\"\",\"totalAmount\":0}", System.Text.Encoding.UTF8, "application/json");

        var response = await client.PostAsync("/api/orders", body, TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        using var doc = System.Text.Json.JsonDocument.Parse(await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken));
        var keys = doc.RootElement.GetProperty("errors").EnumerateObject().Select(p => p.Name).Order(StringComparer.Ordinal).ToList();
        Assert.Equal(["customerName", "totalAmount"], keys);
    }

    // TQ-009 (OD-020): PostgreSQL rejects 0x00 in text; the create path answers 400 in the same shape, never a 500.
    [Theory]
    [InlineData("\u0000")]
    [InlineData("Ac\u0000me")]
    public async Task Create_CustomerNameWithNul_ReturnsValidationProblemKeyedCustomerName(string name)
    {
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/orders", new CreateOrderRequest(name, 10m), TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
        using var doc = System.Text.Json.JsonDocument.Parse(await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken));
        var errors = doc.RootElement.GetProperty("errors");
        Assert.Equal(["customerName"], errors.EnumerateObject().Select(p => p.Name).ToList());
        Assert.Equal("The field CustomerName must not contain the NUL character.", errors.GetProperty("customerName")[0].GetString());
    }

    // BQ-006 (OD-011): the named policy seam: every orders endpoint carries the policy, not a bare RequireAuthorization().
    [Fact]
    public void OrdersEndpoints_AllCarryTheNamedOrdersPolicy()
    {
        var endpoints = factory.Services.GetRequiredService<EndpointDataSource>().Endpoints
            .OfType<RouteEndpoint>()
            .Where(e => e.RoutePattern.RawText?.StartsWith("/api/orders", StringComparison.Ordinal) == true)
            .ToList();

        Assert.NotEmpty(endpoints);
        foreach (var endpoint in endpoints)
        {
            Assert.Contains(endpoint.Metadata.GetOrderedMetadata<IAuthorizeData>(), a => a.Policy == OrdersAuthorization.PolicyName);
        }
    }

    [Fact]
    public async Task OrdersPolicy_IsRegisteredAndRequiresAnAuthenticatedUser()
    {
        var provider = factory.Services.GetRequiredService<IAuthorizationPolicyProvider>();

        var policy = await provider.GetPolicyAsync(OrdersAuthorization.PolicyName);

        Assert.NotNull(policy);
        Assert.Contains(policy.Requirements, r => r is DenyAnonymousAuthorizationRequirement);
    }

    [Fact]
    public async Task List_Authenticated_ReturnsOk()
    {
        var response = await factory.CreateClient().GetAsync("/api/orders", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task Create_TwoDecimalPlaces_ResponseEqualsStoredValue()
    {
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/orders", new CreateOrderRequest("Acme Ltd", 10.25m), TestContext.Current.CancellationToken);
        var created = await response.Content.ReadFromJsonAsync<OrderResponse>(TestContext.Current.CancellationToken);
        var fetched = await client.GetFromJsonAsync<OrderResponse>($"/api/orders/{created!.Id}", TestContext.Current.CancellationToken);

        Assert.Equal(created.TotalAmount, fetched!.TotalAmount);
    }
}

/// <summary>Anonymous on purpose: health probes carry no credentials and hold no data; OpenAPI is mapped in Development only.</summary>
internal static class AnonymousAllowList
{
    private static readonly string[] Prefixes = ["/health/", "/openapi/"];

    /// <summary>Routes of endpoints that neither sit on the allow-list nor carry authorization metadata.</summary>
    public static List<string> Unprotected(IServiceProvider services) =>
        services.GetRequiredService<EndpointDataSource>().Endpoints
            .OfType<RouteEndpoint>()
            .Where(e => !Prefixes.Any(p => (e.RoutePattern.RawText ?? "").StartsWith(p, StringComparison.Ordinal)))
            .Where(e => !e.Metadata.GetOrderedMetadata<IAuthorizeData>().Any()
                        || e.Metadata.GetMetadata<IAllowAnonymous>() is not null)
            .Select(e => e.RoutePattern.RawText ?? e.DisplayName ?? "?")
            .ToList();
}
