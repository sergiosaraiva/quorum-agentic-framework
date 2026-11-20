using Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace Infrastructure.Persistence.Configurations;

public sealed class OrderConfiguration : IEntityTypeConfiguration<Order>
{
    /// <summary>The five BC-001 states built so far; `cancelled` is added with a cancellation feature (OD-013) (VS-005, OD-004), generated from <see cref="OrderStatuses.All"/>.</summary>
    internal static readonly string StatusCheck =
        $"status in ({string.Join(",", OrderStatuses.All.Select(s => $"'{s}'"))})";

    public void Configure(EntityTypeBuilder<Order> builder)
    {
        builder.ToTable("order", t => t.HasCheckConstraint("ck_order_status", StatusCheck));
        builder.HasKey(o => o.Id);
        builder.Property(o => o.Id).ValueGeneratedNever();
        builder.Property(o => o.CustomerName).HasMaxLength(Order.CustomerNameMaxLength).IsRequired();
        builder.Property(o => o.TotalAmount).HasPrecision(18, 2);
        builder.Property(o => o.Status).HasMaxLength(20).IsRequired();
        builder.Property(o => o.CreatedAt).HasColumnType("timestamptz");
        builder.Property(o => o.UpdatedAt).HasColumnType("timestamptz");
        builder.HasIndex(o => o.CreatedAt).HasDatabaseName("ix_order_created_at");
    }
}
