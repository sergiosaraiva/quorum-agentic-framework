using Api.Options;
using Infrastructure.Persistence;
using Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;

namespace Api.Features.Orders;

public sealed class OrdersService(AppDbContext db, IOptions<OrdersOptions> options, TimeProvider clock)
{
    public async Task<OrderResponse> CreateAsync(CreateOrderRequest request, CancellationToken ct)
    {
        var now = clock.GetUtcNow();
        var order = new Order
        {
            Id = Guid.CreateVersion7(),
            CustomerName = request.CustomerName.Trim(),
            TotalAmount = request.TotalAmount,
            Status = "open",
            CreatedAt = now,
            UpdatedAt = now,
        };
        db.Orders.Add(order);
        await db.SaveChangesAsync(ct);
        return ToResponse(order);
    }

    public async Task<OrderResponse?> GetAsync(Guid id, CancellationToken ct) =>
        await db.Orders.AsNoTracking().Where(o => o.Id == id).Select(o => ToResponse(o)).SingleOrDefaultAsync(ct);

    public async Task<PagedResponse<OrderResponse>> ListAsync(int? page, int? pageSize, CancellationToken ct)
    {
        var (p, size) = NormalizePaging(page, pageSize, options.Value);
        var query = db.Orders.AsNoTracking();
        var total = await query.CountAsync(ct);
        var items = await query
            .OrderByDescending(o => o.CreatedAt).ThenBy(o => o.Id)
            .Skip(ComputeSkip(p, size)).Take(size)
            .Select(o => ToResponse(o))
            .ToListAsync(ct);
        return new PagedResponse<OrderResponse>(items, p, size, total);
    }

    internal static (int Page, int PageSize) NormalizePaging(int? page, int? pageSize, OrdersOptions options) =>
        (Math.Max(page ?? 1, 1), Math.Clamp(pageSize ?? options.DefaultPageSize, 1, options.MaxPageSize));

    /// <summary>Row offset computed in long and clamped, so a huge page number cannot overflow int.</summary>
    internal static int ComputeSkip(int page, int pageSize) =>
        (int)Math.Min((long)(page - 1) * pageSize, int.MaxValue);

    private static OrderResponse ToResponse(Order o) =>
        new(o.Id, o.CustomerName, o.TotalAmount, o.Status, o.CreatedAt);
}
