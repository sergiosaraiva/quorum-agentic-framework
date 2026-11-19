using System.ComponentModel.DataAnnotations;

namespace Api.Features.Orders;

public sealed record CreateOrderRequest(
    [property: Required, StringLength(200, MinimumLength = 1)] string CustomerName,
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
