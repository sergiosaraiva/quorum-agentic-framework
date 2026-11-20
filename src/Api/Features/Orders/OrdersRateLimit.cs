using System.Globalization;
using System.Security.Claims;
using System.Threading.RateLimiting;
using Api.Options;
using Microsoft.AspNetCore.RateLimiting;

namespace Api.Features.Orders;

/// <summary>
/// Per-user rate limit for the order list and search endpoint (TQ-007, decided in OD-018). The limits come from
/// <see cref="RateLimitingOptions"/>; the policy name and the anonymous partition key are protocol constants.
/// </summary>
public static class OrdersRateLimit
{
    public const string PolicyName = "orders-list";

    public const string TooManyRequestsTitle = "Too many requests.";

    /// <summary>Problem type for 429 (RFC 6585 section 4); the framework defaults carry no type for this status. A protocol constant.</summary>
    public const string TooManyRequestsType = "https://www.rfc-editor.org/rfc/rfc6585#section-4";

    /// <summary>
    /// Shared bucket for callers without an identifiable principal. Authentication rejects them before the limiter in
    /// practice; the shared key keeps the partition count bounded if that ever changes.
    /// </summary>
    internal const string AnonymousPartitionKey = "anonymous";

    /// <summary>Partition key: the authenticated principal's stable id (never a name or customer data), else the anonymous bucket.</summary>
    internal static string PartitionKey(ClaimsPrincipal? user) =>
        user?.Identity?.IsAuthenticated == true
            ? user.FindFirstValue(ClaimTypes.NameIdentifier) ?? user.FindFirstValue("sub") ?? AnonymousPartitionKey
            : AnonymousPartitionKey;

    public static void AddOrdersListPolicy(this RateLimiterOptions options, RateLimitingOptions limits)
    {
        options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
        options.AddPolicy(PolicyName, context =>
            RateLimitPartition.GetFixedWindowLimiter(PartitionKey(context.User), _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = limits.PermitLimit,
                Window = TimeSpan.FromSeconds(limits.WindowSeconds),
                QueueLimit = 0,
            }));

        options.OnRejected = async (context, ct) =>
        {
            var http = context.HttpContext;
            if (context.Lease.TryGetMetadata(MetadataName.RetryAfter, out var retryAfter))
            {
                http.Response.Headers.RetryAfter = ((int)Math.Ceiling(retryAfter.TotalSeconds)).ToString(CultureInfo.InvariantCulture);
            }

            http.Response.StatusCode = StatusCodes.Status429TooManyRequests;
            // Written through IProblemDetailsService so the body has the same shape (type, traceId) as every other
            // problem response; the title is fixed and echoes nothing from the request.
            await http.RequestServices.GetRequiredService<IProblemDetailsService>().WriteAsync(new ProblemDetailsContext
            {
                HttpContext = http,
                ProblemDetails = { Status = StatusCodes.Status429TooManyRequests, Title = TooManyRequestsTitle, Type = TooManyRequestsType },
            });
        };
    }
}
