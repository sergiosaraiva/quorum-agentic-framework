using System.ComponentModel.DataAnnotations;

namespace Api.Options;

public sealed class OrdersOptions
{
    public const string SectionName = "Orders";

    [Range(1, 1000)]
    public int MaxPageSize { get; init; } = 100;

    /// <summary>
    /// Highest page number a caller may request; bounds the row offset to <c>(MaxPageNumber - 1) * MaxPageSize</c> (TQ-015, OD-025).
    /// The default 1000 (offset 99,900 at page size 100) comes from a single-machine measurement at 1M rows (TQ-016, OD-030):
    /// the old default 10000 took p95 0.8 to 2.2 s for the deepest page, over the 300 ms budget. Re-measure on the deployment target.
    /// </summary>
    [Range(1, 1_000_000)]
    public int MaxPageNumber { get; init; } = 1000;

    [Range(1, 1000)]
    public int DefaultPageSize { get; init; } = 20;
}
