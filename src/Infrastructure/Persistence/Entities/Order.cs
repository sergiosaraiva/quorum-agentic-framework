namespace Infrastructure.Persistence.Entities;

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
