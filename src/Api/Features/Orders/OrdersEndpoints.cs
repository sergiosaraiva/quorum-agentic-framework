using System.ComponentModel.DataAnnotations;

namespace Api.Features.Orders;

public static class OrdersEndpoints
{
    public static IEndpointRouteBuilder MapOrdersEndpoints(this IEndpointRouteBuilder app)
    {
        // Explicit auth decision (Immutable Rule 7): the whole group requires an authenticated caller.
        var group = app.MapGroup("/api/orders").WithTags("Orders").RequireAuthorization();

        // The filter values bind as strings and are parsed explicitly, so a malformed value gives
        // validation problem details (TQ-005) and a calendar date is exactly yyyy-MM-dd (OD-005).
        group.MapGet("/", async (
            int? page, int? pageSize, string? createdFrom, string? createdTo, string? customerName,
            OrdersService service, CancellationToken ct) =>
        {
            var (filter, errors) = OrderListFilter.Parse(createdFrom, createdTo, customerName);
            return errors.Count > 0
                ? Results.ValidationProblem(errors)
                : Results.Ok(await service.ListAsync(page, pageSize, filter, ct));
        });

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
            .GroupBy(x => x.member)
            .ToDictionary(g => g.Key, g => g.Select(x => x.message).ToArray());
    }
}
