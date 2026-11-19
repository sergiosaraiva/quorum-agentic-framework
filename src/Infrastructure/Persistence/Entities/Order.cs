namespace Infrastructure.Persistence.Entities;

public sealed class Order
{
    public Guid Id { get; set; }
    public required string CustomerName { get; set; }
    public decimal TotalAmount { get; set; }
    public required string Status { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
}
