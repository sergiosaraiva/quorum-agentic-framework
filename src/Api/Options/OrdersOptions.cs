using System.ComponentModel.DataAnnotations;

namespace Api.Options;

public sealed class OrdersOptions
{
    public const string SectionName = "Orders";

    [Range(1, 1000)]
    public int MaxPageSize { get; init; } = 100;

    [Range(1, 1000)]
    public int DefaultPageSize { get; init; } = 20;
}
