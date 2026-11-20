using Microsoft.AspNetCore.Authorization;

namespace Api.Features.Orders;

/// <summary>
/// Named authorization policy of the orders endpoints (BQ-006, decided in OD-011: any authenticated caller sees
/// all orders). It requires an authenticated user and nothing else. It is the seam for staff/customer roles: change the
/// requirement here and every orders endpoint follows. The name is a protocol constant, not a tunable.
/// </summary>
public static class OrdersAuthorization
{
    public const string PolicyName = "orders";

    public static void AddOrdersPolicy(this AuthorizationOptions options) =>
        options.AddPolicy(PolicyName, policy => policy.RequireAuthenticatedUser());
}
