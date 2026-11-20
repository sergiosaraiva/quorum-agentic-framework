using System.Net;

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
