using System.ComponentModel.DataAnnotations;
using System.Security.Claims;
using Api.Features.Orders;
using Api.Options;

namespace Api.UnitTests;

/// <summary>TQ-007 (OD-018) options are validated at startup (ValidateDataAnnotations + ValidateOnStart); these tests prove the ranges.</summary>
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

    [Theory]
    [InlineData(1, true)]
    [InlineData(1000, true)]
    [InlineData(0, false)]
    [InlineData(1001, false)]
    public void RateLimitingOptions_ConcurrentRequestsPerUser_IsRangeChecked(int value, bool expected) =>
        Assert.Equal(expected, IsValid(new RateLimitingOptions { ConcurrentRequestsPerUser = value }));

    [Theory]
    [InlineData(1, true)]
    [InlineData(3600, true)]
    [InlineData(0, false)]
    [InlineData(3601, false)]
    public void DatabaseOptions_RetryAfterSeconds_IsRangeChecked(int value, bool expected) =>
        Assert.Equal(expected, IsValid(new DatabaseOptions { RetryAfterSeconds = value }));

    [Theory]
    [InlineData(1, true)]
    [InlineData(1000, true)]
    [InlineData(0, false)]
    [InlineData(-1, false)]
    [InlineData(1001, false)]
    public void DatabaseOptions_MaxPoolSize_IsRangeChecked(int value, bool expected) =>
        Assert.Equal(expected, IsValid(new DatabaseOptions { MaxPoolSize = value }));

    [Fact]
    public void Defaults_ConcurrencyAndRetryAfter_AreTheChosenValues()
    {
        Assert.Equal(4, new RateLimitingOptions().ConcurrentRequestsPerUser);
        Assert.Equal(5, new DatabaseOptions().RetryAfterSeconds);
        Assert.Equal(20, new DatabaseOptions().MaxPoolSize);
    }

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
    [InlineData("5\0", null, false)]
    [InlineData(null, "\0", false)]
    [InlineData("1e3", null, false)]
    [InlineData("1,000", null, false)]
    [InlineData("١٢", null, false)] // non-ASCII digits are not accepted
    public void PagingQuery_Parse_AcceptsOnlyInvariantIntegers(string? page, string? pageSize, bool valid)
    {
        var errors = new Dictionary<string, string[]>();

        PagingQuery.Parse(page, pageSize, int.MaxValue, errors);

        Assert.Equal(valid, errors.Count == 0);
    }

    [Fact]
    public void PagingQuery_Parse_ReturnsParsedValuesAndKeysErrorsByParameterName()
    {
        var errors = new Dictionary<string, string[]>();

        var (page, size) = PagingQuery.Parse("-3", "x", 10, errors);

        Assert.Equal(-3, page);
        Assert.Null(size);
        Assert.Equal(["pageSize"], errors.Keys);
    }

    [Theory]
    [InlineData("10", true)]
    [InlineData("9", true)]
    [InlineData("11", false)]
    [InlineData("2147483647", false)]
    [InlineData("0", true)]
    [InlineData("-5", true)]
    public void PagingQuery_Parse_PageAboveMaxPageNumber_IsRejectedAtTheBoundary(string page, bool valid)
    {
        var errors = new Dictionary<string, string[]>();

        var (parsed, _) = PagingQuery.Parse(page, null, 10, errors);

        Assert.Equal(valid, errors.Count == 0);
        Assert.Equal(valid, parsed is not null);
        if (!valid)
        {
            Assert.Equal(["page"], errors.Keys);
            Assert.Equal(["page must be at most 10."], errors["page"]);
        }
    }

    [Fact]
    public void PagingQuery_Parse_PageSizeIsNotCappedByMaxPageNumber()
    {
        var errors = new Dictionary<string, string[]>();

        var (_, size) = PagingQuery.Parse(null, "50", 10, errors);

        Assert.Empty(errors);
        Assert.Equal(50, size);
    }

    [Theory]
    [InlineData(1, true)]
    [InlineData(1_000_000, true)]
    [InlineData(0, false)]
    [InlineData(-1, false)]
    [InlineData(1_000_001, false)]
    public void OrdersOptions_MaxPageNumber_IsRangeChecked(int value, bool expected) =>
        Assert.Equal(expected, IsValid(new OrdersOptions { MaxPageNumber = value }));

    [Fact]
    public void OrdersOptions_Defaults_AreValidAndBoundTheOffset()
    {
        var options = new OrdersOptions();

        Assert.True(IsValid(options));
        Assert.Equal(1000, options.MaxPageNumber);
        Assert.True((long)(options.MaxPageNumber - 1) * options.MaxPageSize < int.MaxValue);
    }

    [Fact]
    public void DatabaseOptions_DefaultTimeout_IsTenSeconds() =>
        Assert.Equal(10, new DatabaseOptions().CommandTimeoutSeconds);

    private static ClaimsPrincipal Principal(bool authenticated, params Claim[] claims) =>
        new(authenticated ? new ClaimsIdentity(claims, "Test") : new ClaimsIdentity(claims));

    [Fact]
    public void PartitionKey_NullPrincipal_IsAnonymous() =>
        Assert.Equal("anonymous", OrdersRateLimit.PartitionKey(null));

    [Fact]
    public void PartitionKey_Unauthenticated_IsAnonymousEvenWithClaims() =>
        Assert.Equal("anonymous", OrdersRateLimit.PartitionKey(Principal(false, new Claim(ClaimTypes.NameIdentifier, "u1"))));

    [Fact]
    public void PartitionKey_NameIdentifier_IsUsed() =>
        Assert.Equal("u1", OrdersRateLimit.PartitionKey(Principal(true, new Claim(ClaimTypes.NameIdentifier, "u1"), new Claim("sub", "s1"))));

    [Fact]
    public void PartitionKey_OnlySub_IsUsed() =>
        Assert.Equal("s1", OrdersRateLimit.PartitionKey(Principal(true, new Claim("sub", "s1"))));

    [Fact]
    public void PartitionKey_AuthenticatedWithoutIdClaims_IsAnonymous() =>
        Assert.Equal("anonymous", OrdersRateLimit.PartitionKey(Principal(true, new Claim("name", "x"))));
}
