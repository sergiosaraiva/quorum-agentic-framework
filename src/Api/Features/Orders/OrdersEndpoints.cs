using System.ComponentModel.DataAnnotations;
using System.Text.Json;
using Api.Options;
using Microsoft.Extensions.Options;

namespace Api.Features.Orders;

public static class OrdersEndpoints
{
    public static IEndpointRouteBuilder MapOrdersEndpoints(this IEndpointRouteBuilder app)
    {
        // Explicit auth decision (Immutable Rule 7): the whole group requires the named orders policy.
        // BQ-006 (OD-011): any authenticated caller sees all orders. The policy only requires an
        // authenticated user today; it is the seam where staff/customer roles attach later, without touching the endpoints.
        var group = app.MapGroup("/api/orders").WithTags("Orders").RequireAuthorization(OrdersAuthorization.PolicyName);

        // The paging and filter values bind as strings and are parsed explicitly, so a malformed value gives
        // validation problem details (TQ-005, OD-016) and a calendar date is exactly yyyy-MM-dd (OD-005).
        // Rate limited per user (TQ-007, OD-018): each call costs two scans.
        group.MapGet("/", async (
            string? page, string? pageSize, string? createdFrom, string? createdTo, string? customerName, string? status,
            OrdersService service, IOptions<OrdersOptions> orders, CancellationToken ct) =>
        {
            var (filter, errors) = OrderListFilter.Parse(createdFrom, createdTo, customerName, status);
            var (pageNumber, size) = PagingQuery.Parse(page, pageSize, orders.Value.MaxPageNumber, errors);
            return errors.Count > 0
                ? Results.ValidationProblem(errors)
                : Results.Ok(await service.ListAsync(pageNumber, size, filter, ct));
        }).RequireRateLimiting(OrdersRateLimit.PolicyName);

        group.MapGet("/{id:guid}", async (Guid id, OrdersService service, CancellationToken ct) =>
            await service.GetAsync(id, ct) is { } order ? Results.Ok(order) : Results.NotFound());

        group.MapPost("/", async (CreateOrderRequest request, OrdersService service, CancellationToken ct) =>
        {
            var errors = Validate(request);
            if (errors.Count > 0)
            {
                return Results.ValidationProblem(errors);
            }

            var created = await service.CreateAsync(request, ct);
            return Results.Created($"/api/orders/{created.Id}", created);
        });

        return app;
    }

    private static Dictionary<string, string[]> Validate(CreateOrderRequest request)
    {
        var results = new List<ValidationResult>();
        Validator.TryValidateObject(request, new ValidationContext(request), results, validateAllProperties: true);
        return results
            .SelectMany(r => r.MemberNames.DefaultIfEmpty(""), (r, member) => (member, message: r.ErrorMessage ?? "Invalid"))
            // TQ-008 (OD-019): error keys are camelCase everywhere, matching the JSON property names and the list filters.
            .GroupBy(x => JsonNamingPolicy.CamelCase.ConvertName(x.member))
            .ToDictionary(g => g.Key, g => g.Select(x => x.message).ToArray());
    }
}
