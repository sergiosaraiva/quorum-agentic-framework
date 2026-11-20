using System.ComponentModel.DataAnnotations;
using System.Globalization;
using Infrastructure.Persistence.Entities;

namespace Api.Features.Orders;

public sealed record CreateOrderRequest(
    [property: Required, StringLength(Order.CustomerNameMaxLength, MinimumLength = 1), NoNulCharacter] string CustomerName,
    [property: Range(0.01, 1_000_000_000), MaxDecimalPlaces(2)] decimal TotalAmount);

/// <summary>Rejects values with more decimal places than the column stores (numeric(18,2)), so the 201 response equals the stored value.</summary>
[AttributeUsage(AttributeTargets.Property | AttributeTargets.Parameter)]
public sealed class MaxDecimalPlacesAttribute(int places) : ValidationAttribute
{
    public override bool IsValid(object? value) =>
        value is not decimal d || decimal.Round(d, places) == d;

    public override string FormatErrorMessage(string name) =>
        $"The field {name} must have at most {places} decimal places.";
}

/// <summary>
/// Rejects U+0000 (TQ-009, decided in OD-020): PostgreSQL refuses 0x00 in text (error 22021), which would otherwise be a 500.
/// Same rule as the list filter. The message never echoes the input.
/// </summary>
[AttributeUsage(AttributeTargets.Property | AttributeTargets.Parameter)]
public sealed class NoNulCharacterAttribute : ValidationAttribute
{
    public override bool IsValid(object? value) =>
        value is not string s || !s.Contains('\0');

    public override string FormatErrorMessage(string name) =>
        $"The field {name} must not contain the NUL character.";
}

/// <summary>
/// Explicit parsing of <c>page</c> and <c>pageSize</c> (TQ-005, decided in OD-016): they bind as strings so a malformed value
/// gives validation problem details keyed by the parameter name instead of a bodiless 400 (or a 500 in Development).
/// Any value that fits an <see cref="int"/> is accepted, including zero and negatives; the service clamps them
/// (<see cref="OrdersService.NormalizePaging"/>). Text, decimals and values beyond the <see cref="int"/> range are rejected,
/// and so is a page above the configured maximum page number (TQ-015, OD-025), which bounds the row offset. Messages never echo input.
/// </summary>
public static class PagingQuery
{
    public const string PageKey = "page";
    public const string PageSizeKey = "pageSize";

    internal static (int? Page, int? PageSize) Parse(string? page, string? pageSize, int maxPageNumber, Dictionary<string, string[]> errors)
    {
        var parsedPage = ParseInt(page, PageKey, errors);
        if (parsedPage > maxPageNumber)
        {
            errors[PageKey] = [$"{PageKey} must be at most {maxPageNumber}."];
            parsedPage = null;
        }

        return (parsedPage, ParseInt(pageSize, PageSizeKey, errors));
    }

    private static int? ParseInt(string? value, string key, Dictionary<string, string[]> errors)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        // Number parsing tolerates a trailing U+0000 ("5\0" parses as 5); every other input rule here rejects NUL, so this does too.
        if (!value.Contains('\0') && int.TryParse(value.Trim(), NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture, out var parsed))
        {
            return parsed;
        }

        errors[key] = [$"{key} must be a whole number between {int.MinValue} and {int.MaxValue}."];
        return null;
    }
}

public sealed record OrderResponse(
    Guid Id,
    string CustomerName,
    decimal TotalAmount,
    string Status,
    DateTimeOffset CreatedAt);

public sealed record PagedResponse<T>(IReadOnlyList<T> Items, int Page, int PageSize, int TotalCount);

/// <summary>
/// Validated list filters (VS-004 R1, OD-002, OD-003, OD-005). Dates are UTC calendar days, both bounds inclusive;
/// the name is a case-insensitive substring. R2 (VS-004, OD-002, OD-004, TQ-011): the status is an exact,
/// case-sensitive match on one BC-001 state. Built only through <see cref="Parse"/>.
/// </summary>
public sealed record OrderListFilter(DateOnly? CreatedFrom, DateOnly? CreatedTo, string? CustomerName, string? Status = null)
{
    public const string DateFormat = "yyyy-MM-dd";
    public const string CreatedFromKey = "createdFrom";
    public const string CreatedToKey = "createdTo";
    public const string CustomerNameKey = "customerName";
    public const string StatusKey = "status";

    public static readonly OrderListFilter None = new(null, null, null, null);

    /// <summary>Parses raw query values; Errors is empty when Filter is usable. Messages never echo input.</summary>
    internal static (OrderListFilter Filter, Dictionary<string, string[]> Errors) Parse(
        string? createdFrom, string? createdTo, string? customerName, string? status = null)
    {
        var errors = new Dictionary<string, string[]>();
        var from = ParseDate(createdFrom, CreatedFromKey, errors);
        var to = ParseDate(createdTo, CreatedToKey, errors);
        if (from is { } f && to is { } t && t < f)
        {
            errors[CreatedToKey] = [$"{CreatedToKey} must not be before {CreatedFromKey}."];
        }

        string? name = null;
        if (!string.IsNullOrWhiteSpace(customerName))
        {
            name = customerName.Trim();
            if (name.Length > Order.CustomerNameMaxLength)
            {
                errors[CustomerNameKey] = [$"{CustomerNameKey} must be at most {Order.CustomerNameMaxLength} characters."];
                name = null;
            }
            else if (name.Contains('\0'))
            {
                // PostgreSQL rejects 0x00 in text (error 22021), which would surface as a 500; other control characters are valid text.
                errors[CustomerNameKey] = [$"{CustomerNameKey} must not contain the NUL character."];
                name = null;
            }
        }

        string? validStatus = null;
        if (!string.IsNullOrWhiteSpace(status))
        {
            validStatus = status.Trim();
            if (!OrderStatuses.IsKnown(validStatus))
            {
                // Lists the allowed values, never the input. Repeated parameters arrive joined with a comma and land here too.
                errors[StatusKey] = [$"{StatusKey} must be one of: {string.Join(", ", OrderStatuses.All)}."];
                validStatus = null;
            }
        }

        return (new OrderListFilter(from, to, name, validStatus), errors);
    }

    private static DateOnly? ParseDate(string? value, string key, Dictionary<string, string[]> errors)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        if (DateOnly.TryParseExact(value, DateFormat, CultureInfo.InvariantCulture, DateTimeStyles.None, out var date))
        {
            return date;
        }

        errors[key] = [$"{key} must be a date in the format {DateFormat}."];
        return null;
    }
}
