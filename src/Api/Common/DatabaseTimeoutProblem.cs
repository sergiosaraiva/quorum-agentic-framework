using System.Globalization;
using Api.Options;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Options;
using Npgsql;

namespace Api.Common;

/// <summary>
/// Maps a database command timeout to a 503 problem response (TQ-015, decided in OD-025). Only a timeout is mapped;
/// every other exception keeps the handler's default status. The response text is fixed and never carries exception text;
/// the <c>Retry-After</c> header comes from <see cref="DatabaseOptions.RetryAfterSeconds"/> (OD-029).
/// </summary>
public static class DatabaseTimeoutProblem
{
    public const string Title = "Service temporarily unavailable.";

    public const string Detail = "The request could not be completed in time. Try again later.";

    /// <summary>Problem type for 503 (RFC 9110 section 15.6.4); the framework defaults carry the same link. A protocol constant.</summary>
    public const string Type = "https://www.rfc-editor.org/rfc/rfc9110#section-15.6.4";

    /// <summary>Bounds the walk down an inner-exception chain.</summary>
    private const int MaxChainDepth = 8;

    /// <summary>
    /// True when a <see cref="TimeoutException"/> or a server-side query cancellation (SQLSTATE 57014) is found within
    /// <see cref="MaxChainDepth"/> levels of the exception chain. Npgsql reports a client-side command or connection timeout as an
    /// <see cref="NpgsqlException"/> whose cause is a <see cref="TimeoutException"/>. An exception whose outermost type is an
    /// <see cref="OperationCanceledException"/> is a caller cancel, even when it wraps SQLSTATE 57014, and is not a timeout.
    /// </summary>
    public static bool IsTimeout(Exception? exception)
    {
        if (exception is OperationCanceledException)
        {
            return false;
        }

        var current = exception;
        for (var depth = 0; current is not null && depth < MaxChainDepth; depth++, current = current.InnerException)
        {
            if (current is TimeoutException or PostgresException { SqlState: PostgresErrorCodes.QueryCanceled })
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>Status for the exception handler: a client error keeps its own status, a timeout is 503, anything else 500.</summary>
    public static int SelectStatusCode(Exception exception) =>
        exception switch
        {
            BadHttpRequestException bad => bad.StatusCode,
            _ when IsTimeout(exception) => StatusCodes.Status503ServiceUnavailable,
            _ => StatusCodes.Status500InternalServerError,
        };

    /// <summary>Replaces the title and detail of a timeout response with the fixed text, whatever the environment.</summary>
    public static void Customize(ProblemDetailsContext context)
    {
        var error = context.Exception ?? context.HttpContext.Features.Get<IExceptionHandlerFeature>()?.Error;
        if (context.ProblemDetails.Status == StatusCodes.Status503ServiceUnavailable && IsTimeout(error))
        {
            context.ProblemDetails.Title = Title;
            context.ProblemDetails.Detail = Detail;
            context.ProblemDetails.Type = Type;
            var retryAfter = context.HttpContext.RequestServices.GetRequiredService<IOptions<DatabaseOptions>>().Value.RetryAfterSeconds;
            context.HttpContext.Response.Headers.RetryAfter = retryAfter.ToString(CultureInfo.InvariantCulture);
        }
    }
}
