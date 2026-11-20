using System.ComponentModel.DataAnnotations;
using Api.Features.Orders;
using Api.Options;

namespace Api.UnitTests;

/// <summary>TQ-007 options are validated at startup (ValidateDataAnnotations + ValidateOnStart); these tests prove the ranges.</summary>
public class OptionsValidationTests
{
    private static bool IsValid(object options) =>
        Validator.TryValidateObject(options, new ValidationContext(options), [], validateAllProperties: true);

    [Theory]
    [InlineData(1, true)]
    [InlineData(100_000, true)]
    [InlineData(0, false)]
    [InlineData(-1, false)]
    [InlineData(100_001, false)]
    public void RateLimitingOptions_PermitLimit_IsRangeChecked(int value, bool expected) =>
        Assert.Equal(expected, IsValid(new RateLimitingOptions { PermitLimit = value }));

    [Theory]
    [InlineData(1, true)]
    [InlineData(86_400, true)]
    [InlineData(0, false)]
    [InlineData(86_401, false)]
    public void RateLimitingOptions_WindowSeconds_IsRangeChecked(int value, bool expected) =>
        Assert.Equal(expected, IsValid(new RateLimitingOptions { WindowSeconds = value }));

    [Theory]
    [InlineData(1, true)]
    [InlineData(600, true)]
    [InlineData(0, false)]
    [InlineData(-30, false)]
    [InlineData(601, false)]
    public void DatabaseOptions_CommandTimeoutSeconds_IsRangeChecked(int value, bool expected) =>
        Assert.Equal(expected, IsValid(new DatabaseOptions { CommandTimeoutSeconds = value }));

    [Fact]
    public void Defaults_AreValid()
    {
        Assert.True(IsValid(new RateLimitingOptions()));
        Assert.True(IsValid(new DatabaseOptions()));
    }

    [Theory]
    [InlineData("Acme", true)]
    [InlineData("", true)]
    [InlineData("a\u0000b", false)]
    [InlineData("\u0000", false)]
    [InlineData("tab\there\u0001", true)]
    public void NoNulCharacter_RejectsOnlyU0000(string value, bool expected) =>
        Assert.Equal(expected, new NoNulCharacterAttribute().IsValid(value));

    [Theory]
    [InlineData(null, null, true)]
    [InlineData("", "  ", true)]
    [InlineData("3", "-4", true)]
    [InlineData("+3", "0", true)]
    [InlineData("2147483647", "-2147483648", true)]
    [InlineData("abc", null, false)]
    [InlineData(null, "1.5", false)]
    [InlineData("1.0", null, false)]
    [InlineData("2147483648", null, false)]
    [InlineData("1e3", null, false)]
    [InlineData("1,000", null, false)]
    [InlineData("١٢", null, false)] // non-ASCII digits are not accepted
    public void PagingQuery_Parse_AcceptsOnlyInvariantIntegers(string? page, string? pageSize, bool valid)
    {
        var errors = new Dictionary<string, string[]>();

        PagingQuery.Parse(page, pageSize, errors);

        Assert.Equal(valid, errors.Count == 0);
    }

    [Fact]
    public void PagingQuery_Parse_ReturnsParsedValuesAndKeysErrorsByParameterName()
    {
        var errors = new Dictionary<string, string[]>();

        var (page, size) = PagingQuery.Parse("-3", "x", errors);

        Assert.Equal(-3, page);
        Assert.Null(size);
        Assert.Equal(["pageSize"], errors.Keys);
    }
}
