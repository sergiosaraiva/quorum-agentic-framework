using Api.Common;
using Api.Features.Orders;
using Api.Options;
using Infrastructure.Persistence;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOptions<AuthOptions>()
    .BindConfiguration(AuthOptions.SectionName).ValidateDataAnnotations().ValidateOnStart();
builder.Services.AddOptions<OrdersOptions>()
    .BindConfiguration(OrdersOptions.SectionName).ValidateDataAnnotations().ValidateOnStart();

builder.Services.AddOptions<DatabaseOptions>()
    .BindConfiguration(DatabaseOptions.SectionName).ValidateDataAnnotations().ValidateOnStart();
builder.Services.AddOptions<RateLimitingOptions>()
    .BindConfiguration(RateLimitingOptions.SectionName).ValidateDataAnnotations().ValidateOnStart();

builder.Services.AddDbContext<AppDbContext>((sp, o) =>
{
    var database = sp.GetRequiredService<IOptions<DatabaseOptions>>().Value;
    // TQ-016: the pool bound comes from the validated Database options, never from a literal.
    o.UseNpgsql(
            DatabaseConnectionString.WithMaxPoolSize(builder.Configuration.GetConnectionString("Default"), database.MaxPoolSize),
            npgsql => npgsql.CommandTimeout(database.CommandTimeoutSeconds))
        .UseSnakeCaseNamingConvention();
});
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddScoped<OrdersService>();

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer();
builder.Services.AddOptions<JwtBearerOptions>(JwtBearerDefaults.AuthenticationScheme)
    .Configure<IOptions<AuthOptions>>((jwt, auth) =>
    {
        jwt.Authority = auth.Value.Authority;
        jwt.Audience = auth.Value.Audience;
    });
builder.Services.AddAuthorization(o => o.AddOrdersPolicy());

// TQ-007 (OD-018): built-in per-user rate limiter; limits come from the validated RateLimiting options.
builder.Services.AddRateLimiter(_ => { });
builder.Services.AddOptions<RateLimiterOptions>()
    .Configure<IOptions<RateLimitingOptions>>((rl, limits) => rl.AddOrdersListPolicy(limits.Value));

builder.Services.AddProblemDetails(o => o.CustomizeProblemDetails = DatabaseTimeoutProblem.Customize);
// TQ-005 (OD-016): a malformed request (for example invalid JSON) is a client error, not a 500, also in Development where
// the framework throws BadHttpRequestException instead of answering 400 itself. TQ-015 (OD-025): a database command timeout is a 503;
// any other exception stays a 500.
builder.Services.Configure<ExceptionHandlerOptions>(o => o.StatusCodeSelector = DatabaseTimeoutProblem.SelectStatusCode);
builder.Services.AddOpenApi();
builder.Services.AddHealthChecks().AddDbContextCheck<AppDbContext>(tags: ["ready"]);

var app = builder.Build();

app.UseExceptionHandler();
app.UseAuthentication();
app.UseAuthorization();
app.UseRateLimiter(); // after authentication: the limiter partitions on the authenticated principal

// Anonymous on purpose: Liveness and readiness probes carry no credentials and the responses hold no data.
// Liveness runs no checks (never touches the database); readiness runs the checks tagged "ready" (database).
app.MapHealthChecks("/health/live", new HealthCheckOptions { Predicate = _ => false }).AllowAnonymous();
app.MapHealthChecks("/health/ready", new HealthCheckOptions { Predicate = c => c.Tags.Contains("ready") }).AllowAnonymous();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi().AllowAnonymous(); // development only; not mapped elsewhere
}

app.MapOrdersEndpoints();

app.Run();

public partial class Program;
