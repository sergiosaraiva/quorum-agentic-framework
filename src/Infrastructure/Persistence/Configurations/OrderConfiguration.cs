using Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace Infrastructure.Persistence.Configurations;

public sealed class OrderConfiguration : IEntityTypeConfiguration<Order>
{
    public void Configure(EntityTypeBuilder<Order> builder)
    {
        builder.ToTable("order", t => t.HasCheckConstraint("ck_order_status", "status in ('open','paid','cancelled')"));
        builder.HasKey(o => o.Id);
        builder.Property(o => o.Id).ValueGeneratedNever();
        builder.Property(o => o.CustomerName).HasMaxLength(200).IsRequired();
        builder.Property(o => o.TotalAmount).HasPrecision(18, 2);
        builder.Property(o => o.Status).HasMaxLength(20).IsRequired();
        builder.Property(o => o.CreatedAt).HasColumnType("timestamptz");
        builder.Property(o => o.UpdatedAt).HasColumnType("timestamptz");
        builder.HasIndex(o => o.CreatedAt).HasDatabaseName("ix_order_created_at");
    }
}
