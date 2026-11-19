using Api.Features.Orders;
using Api.Options;

namespace Api.UnitTests;

public class OrdersPagingTests
{
    private static readonly OrdersOptions Options = new() { DefaultPageSize = 20, MaxPageSize = 50 };

    [Fact]
    public void NormalizePaging_NoInput_UsesDefaults()
    {
        var (page, size) = OrdersService.NormalizePaging(null, null, Options);

        Assert.Equal(1, page);
        Assert.Equal(20, size);
    }

    [Theory]
    [InlineData(0, 1)]
    [InlineData(-5, 1)]
    [InlineData(7, 7)]
    public void NormalizePaging_PageBelowOne_ClampsToOne(int input, int expected)
    {
        var (page, _) = OrdersService.NormalizePaging(input, null, Options);

        Assert.Equal(expected, page);
    }

    [Theory]
    [InlineData(0, 1)]
    [InlineData(25, 25)]
    [InlineData(10_000, 50)]
    public void NormalizePaging_PageSize_ClampsToConfiguredMaximum(int input, int expected)
    {
        var (_, size) = OrdersService.NormalizePaging(null, input, Options);

        Assert.Equal(expected, size);
    }

    [Theory]
    [InlineData(1, 20, 0)]
    [InlineData(3, 20, 40)]
    [InlineData(int.MaxValue, 50, int.MaxValue)]
    [InlineData(int.MaxValue, 1, int.MaxValue - 1)]
    public void ComputeSkip_HugePage_DoesNotOverflow(int page, int size, int expected)
    {
        Assert.Equal(expected, OrdersService.ComputeSkip(page, size));
    }
}
