using System.ComponentModel.DataAnnotations;
using System.Globalization;
using Infrastructure.Persistence.Entities;

namespace Api.Features.Orders;

public sealed record CreateOrderRequest(
    [property: Required, StringLength(Order.CustomerNameMaxLength, MinimumLength = 1)] string CustomerName,
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
