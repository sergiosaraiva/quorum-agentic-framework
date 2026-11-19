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

    public async Task<PagedResponse<OrderResponse>> ListAsync(int? page, int? pageSize, OrderListFilter filter, CancellationToken ct)
    {
        var (p, size) = NormalizePaging(page, pageSize, options.Value);
        var query = ApplyFilter(db.Orders.AsNoTracking(), filter);
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

    /// <summary>PostgreSQL LIKE escape character; a protocol constant, not a tunable.</summary>
    private const string LikeEscapeCharacter = "\\";

    /// <summary>Escapes LIKE wildcards so caller text matches literally; the escape character itself goes first.</summary>
    internal static string EscapeLikePattern(string term) =>
        term.Replace("\\", "\\\\").Replace("%", "\\%").Replace("_", "\\_");

    /// <summary>Applies the filters with AND semantics. Date bounds are UTC days (OD-005); the name is ILIKE on an escaped pattern (OD-003).</summary>
    internal static IQueryable<Order> ApplyFilter(IQueryable<Order> query, OrderListFilter filter)
    {
        if (filter.CreatedFrom is { } from)
        {
            var lower = new DateTimeOffset(from.ToDateTime(TimeOnly.MinValue), TimeSpan.Zero);
            query = query.Where(o => o.CreatedAt >= lower);
        }

        // DateOnly.MaxValue means no upper bound: AddDays(1) would overflow.
        if (filter.CreatedTo is { } to && to != DateOnly.MaxValue)
        {
            var upperExclusive = new DateTimeOffset(to.AddDays(1).ToDateTime(TimeOnly.MinValue), TimeSpan.Zero);
            query = query.Where(o => o.CreatedAt < upperExclusive);
        }

        if (filter.CustomerName is { } name)
        {
            var pattern = "%" + EscapeLikePattern(name) + "%";
            query = query.Where(o => EF.Functions.ILike(o.CustomerName, pattern, LikeEscapeCharacter));
        }

        return query;
    }

    private static OrderResponse ToResponse(Order o) =>
        new(o.Id, o.CustomerName, o.TotalAmount, o.Status, o.CreatedAt);
}
