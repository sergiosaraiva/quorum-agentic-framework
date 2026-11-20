using System.ComponentModel.DataAnnotations;

namespace Api.Options;

public sealed class OrdersOptions
{
    public const string SectionName = "Orders";

    [Range(1, 1000)]
    public int MaxPageSize { get; init; } = 100;

    /// <summary>Highest page number a caller may request; bounds the row offset to <c>(MaxPageNumber - 1) * MaxPageSize</c> (TQ-015, OD-025).</summary>
    [Range(1, 1_000_000)]
    public int MaxPageNumber { get; init; } = 10_000;

    [Range(1, 1000)]
    public int DefaultPageSize { get; init; } = 20;
}
