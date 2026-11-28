using System.Net;
using System.Text.Json;

namespace Api.IntegrationTests;

public class OpenApiMappingTests
{
    [Fact]
    public async Task OpenApi_InDevelopment_IsServed()
    {
        await using var factory = new DevelopmentApiFactory();
        await factory.InitializeAsync();
        var client = factory.CreateClient();

        var response = await client.GetAsync("/openapi/v1.json", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Theory]
    [InlineData("/api/orders", "get", new[] { "200", "400" }, "200", "PagedResponse")]
    [InlineData("/api/orders/{id}", "get", new[] { "200", "404" }, "200", "OrderResponse")]
    [InlineData("/api/orders", "post", new[] { "201", "400" }, "201", "OrderResponse")]
    public async Task OpenApi_InDevelopment_DocumentsTheOrdersResponseStatuses(string path, string method, string[] statuses, string successStatus, string successSchema)
    {
        await using var factory = new DevelopmentApiFactory();
        await factory.InitializeAsync();
        var client = factory.CreateClient();

        var json = await client.GetStringAsync("/openapi/v1.json", TestContext.Current.CancellationToken);

        using var document = JsonDocument.Parse(json);
        var responses = document.RootElement.GetProperty("paths").GetProperty(path).GetProperty(method).GetProperty("responses");
        foreach (var status in statuses)
        {
            Assert.True(responses.TryGetProperty(status, out _), $"{method} {path} does not document {status}");
        }

        var reference = responses.GetProperty(successStatus).GetProperty("content").GetProperty("application/json")
            .GetProperty("schema").GetProperty("$ref").GetString();
        Assert.Contains(successSchema, reference);
    }

    [Fact]
    public async Task EveryMappedEndpoint_InDevelopment_OutsideTheAnonymousAllowList_RequiresAuthorization()
    {
        await using var factory = new DevelopmentApiFactory();
        await factory.InitializeAsync();

        Assert.Empty(AnonymousAllowList.Unprotected(factory.Services));
    }

    [Fact]
    public async Task OpenApi_InTesting_IsNotMapped()
    {
        await using var factory = new ApiFactory();
        await factory.InitializeAsync();
        var client = factory.CreateClient();

        var response = await client.GetAsync("/openapi/v1.json", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }
}

public class BrokenDatabaseHealthTests
{
    [Fact]
    public async Task Ready_WithUnreachableDatabase_Returns503WhileLiveStays200()
    {
        await using var factory = new BrokenDatabaseApiFactory();
        var client = factory.CreateClient();

        var ready = await client.GetAsync("/health/ready", TestContext.Current.CancellationToken);
        var live = await client.GetAsync("/health/live", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.ServiceUnavailable, ready.StatusCode);
        Assert.Equal(HttpStatusCode.OK, live.StatusCode);
    }
}
