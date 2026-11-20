namespace Infrastructure.Persistence.Entities;

/// <summary>
/// The five BC-001 order lifecycle states built so far; `cancelled` is added with a cancellation feature (OD-013) (aligned by VS-005, OD-004). Stored as text under check constraint
/// <c>ck_order_status</c>, which is built from <see cref="All"/>, so the vocabulary has one source.
/// </summary>
public static class OrderStatuses
{
    public const string Draft = "draft";
    public const string Placed = "placed";
    public const string Paid = "paid";
    public const string Shipped = "shipped";
    public const string Closed = "closed";

    /// <summary>BC-001 order: draft, placed, paid, shipped, closed.</summary>
    public static readonly IReadOnlyList<string> All = [Draft, Placed, Paid, Shipped, Closed];

    public static bool IsKnown(string value) => All.Contains(value, StringComparer.Ordinal);
}

public sealed class Order
{
    /// <summary>Column length of <see cref="CustomerName"/>; shared by the EF configuration, the create request and the list filter.</summary>
    public const int CustomerNameMaxLength = 200;

    public Guid Id { get; set; }
    public required string CustomerName { get; set; }
    public decimal TotalAmount { get; set; }
    public required string Status { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
}
