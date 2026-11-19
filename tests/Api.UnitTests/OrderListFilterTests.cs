using Api.Features.Orders;
using Infrastructure.Persistence.Entities;

namespace Api.UnitTests;

public class OrderListFilterTests
{
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("  ")]
    public void Parse_AllAbsent_ReturnsNoneWithoutErrors(string? blank)
    {
        var (filter, errors) = OrderListFilter.Parse(blank, blank, blank);

        Assert.Equal(OrderListFilter.None, filter);
        Assert.Empty(errors);
    }

    [Fact]
    public void Parse_ValidDates_ReturnsDates()
    {
        var (filter, errors) = OrderListFilter.Parse("2026-11-19", "2026-11-20", null);

        Assert.Empty(errors);
        Assert.Equal(new DateOnly(2026, 11, 19), filter.CreatedFrom);
        Assert.Equal(new DateOnly(2026, 11, 20), filter.CreatedTo);
    }

    [Fact]
    public void Parse_FromEqualsTo_IsAccepted()
    {
        var (filter, errors) = OrderListFilter.Parse("2026-11-19", "2026-11-19", null);

        Assert.Empty(errors);
        Assert.Equal(filter.CreatedFrom, filter.CreatedTo);
    }

    public static TheoryData<string, string> MalformedDates()
    {
        var data = new TheoryData<string, string>();
        foreach (var key in new[] { OrderListFilter.CreatedFromKey, OrderListFilter.CreatedToKey })
        {
            foreach (var value in new[] { "2026-13-40", "19/11/2026", "11/19/2026", "2026-11-19T10:00:00", "2026-1-5", "abc" })
            {
                data.Add(key, value);
            }
        }

        return data;
    }

    [Theory]
    [MemberData(nameof(MalformedDates))]
    public void Parse_MalformedDate_ReturnsErrorKeyedByParameter(string key, string value)
    {
        var (_, errors) = key == OrderListFilter.CreatedFromKey
            ? OrderListFilter.Parse(value, null, null)
            : OrderListFilter.Parse(null, value, null);

        var message = Assert.Single(Assert.Single(errors, e => e.Key == key).Value);
        Assert.DoesNotContain(value, message, StringComparison.Ordinal);
    }

    [Fact]
    public void Parse_FromAfterTo_ReturnsCreatedToError()
    {
        var (_, errors) = OrderListFilter.Parse("2026-11-20", "2026-11-19", null);

        Assert.Equal([OrderListFilter.CreatedToKey], errors.Keys);
    }

    [Fact]
    public void Parse_MalformedFromAndTooLongName_ReturnsBothErrors()
    {
        var (_, errors) = OrderListFilter.Parse("abc", null, new string('x', Order.CustomerNameMaxLength + 1));

        Assert.Contains(OrderListFilter.CreatedFromKey, errors.Keys);
        Assert.Contains(OrderListFilter.CustomerNameKey, errors.Keys);
    }

    [Fact]
    public void Parse_CustomerNameAtLimit_IsAccepted()
    {
        var (filter, errors) = OrderListFilter.Parse(null, null, new string('x', Order.CustomerNameMaxLength));

        Assert.Empty(errors);
        Assert.Equal(Order.CustomerNameMaxLength, filter.CustomerName?.Length);
    }

    [Fact]
    public void Parse_CustomerNameOverLimit_ReturnsCustomerNameError()
    {
        var (_, errors) = OrderListFilter.Parse(null, null, new string('x', Order.CustomerNameMaxLength + 1));

        Assert.Equal([OrderListFilter.CustomerNameKey], errors.Keys);
    }

    [Fact]
    public void Parse_CustomerNamePaddedOverLimit_IsTrimmedBeforeTheCheck()
    {
        var padded = "  " + new string('x', Order.CustomerNameMaxLength) + "  ";

        var (_, errors) = OrderListFilter.Parse(null, null, padded);

        Assert.Empty(errors);
    }

    [Fact]
    public void Parse_CustomerNameWithSpaces_IsTrimmed()
    {
        var (filter, _) = OrderListFilter.Parse(null, null, "  acme  ");

        Assert.Equal("acme", filter.CustomerName);
    }

    [Theory]
    [InlineData("50%", "50\\%")]
    [InlineData("a_b", "a\\_b")]
    [InlineData("a\\b", "a\\\\b")]
    [InlineData("\\%", "\\\\\\%")]
    [InlineData("Acme", "Acme")]
    public void EscapeLikePattern_SpecialCharacters_AreEscaped(string term, string expected)
    {
        Assert.Equal(expected, OrdersService.EscapeLikePattern(term));
    }
}
