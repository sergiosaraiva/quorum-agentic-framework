using System.Net;
using System.Net.Http.Json;
using Api.Features.Orders;

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
        Assert.Equal("open", fetched?.Status);
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
    public async Task List_HugePageNumber_ReturnsEmptyPageNotServerError()
    {
        var client = factory.CreateClient();

        var response = await client.GetAsync($"/api/orders?page={int.MaxValue}&pageSize=50", TestContext.Current.CancellationToken);

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
        Assert.Contains("totalAmount", text, StringComparison.OrdinalIgnoreCase);
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
