---
name: managing-application-lifecycle
description: Manages ASP.NET Core host startup and shutdown, background services, health checks and graceful draining for Kubernetes (EKS) deployments. Use when adding a BackgroundService or hosted service, health/readiness endpoints, probes in Helm values, startup validation, or shutdown behaviour.
---

# Managing Application Lifecycle

Design Principles: `.claude/agents/_SHARED-PATTERNS.md`.

## When NOT to Add Lifecycle Machinery

- No `BackgroundService` for work a request, a migration step or an existing job already does. Add one only for recurring work that is idempotent in every replica. Work needing exactly-once, submit/status/cancel/requeue or cron semantics is a job (separate workload), not a hand-rolled coordinator
- No custom start/stop choreography, startup-gate framework or health-check abstraction: `AddHealthChecks()`, `BackgroundService` and the default graceful shutdown suffice
- One cheap health check per real dependency (the database), tagged `ready`. Never put a dependency check on `/health/live`
- No `preStop` hook or raised grace period unless in-flight requests are measured to exceed the default; never `Environment.Exit`
- Intervals, batch sizes and timeouts are Options (`creating-configuration-options`), never literals

## Quick Reference

- Minimal hosting (`WebApplication.CreateBuilder`), no `Startup.cs`
- `/health/live`: the process is up (no dependency checks, `Predicate = _ => false`). `/health/ready`: dependencies reachable. Both anonymous, documented as such. Set the paths explicitly in the Helm values probes; do not assume the chart supplies defaults (verify against the chart's schema and render with `helm template`)
- Use a `startup` probe for slow warm-up so liveness does not kill a starting pod
- Recurring work: `BackgroundService` via `AddHostedService<T>()`, honouring `stoppingToken`, one `PeriodicTimer` loop, exceptions caught and logged so one failure does not end the loop
- Kubernetes sends `SIGTERM`, then `SIGKILL` after `terminationGracePeriodSeconds`. The host drains in-flight requests by default; keep `HostOptions.ShutdownTimeout` below the grace period
- A background worker that handles per-tenant data takes the tenant only from the message envelope, one DI scope per message, never from the payload body
- Fail fast on bad configuration (`ValidateOnStart()`), so a bad deploy never becomes ready

## Decision Tree

```
Is the process alive?                 -> /health/live, no dependency checks
Can it serve traffic?                 -> /health/ready (database, cache), tag "ready"
Recurring idempotent work in each replica? -> BackgroundService
Needs exactly-once / job semantics?   -> separate scheduled or queue-driven workload (implementing-infrastructure-as-code)
In-flight requests outlive default drain? -> measure first, then grace period / preStop
```

## Examples

```csharp
// Program.cs
builder.Services.AddHealthChecks()
    .AddDbContextCheck<AppDbContext>("database", tags: ["ready"]);
builder.Services.Configure<HostOptions>(o => o.ShutdownTimeout = TimeSpan.FromSeconds(25));  // from Options in real code

app.MapHealthChecks("/health/live", new HealthCheckOptions { Predicate = _ => false }).AllowAnonymous();
app.MapHealthChecks("/health/ready", new HealthCheckOptions { Predicate = c => c.Tags.Contains("ready") }).AllowAnonymous();
```

```csharp
public sealed class ExpiredInviteCleaner(
    IServiceScopeFactory scopes, IOptions<CleanupOptions> options, ILogger<ExpiredInviteCleaner> logger)
    : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(options.Value.Interval);
        while (await timer.WaitForNextTickAsync(stoppingToken))
        {
            try
            {
                using var scope = scopes.CreateScope();            // DbContext is scoped
                var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
                var removed = await db.Invites.Where(i => i.ExpiresAt < DateTimeOffset.UtcNow)
                    .ExecuteDeleteAsync(stoppingToken);            // idempotent: safe in every replica
                logger.LogInformation("Removed {Count} expired invites", removed);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { }
            catch (Exception ex) { logger.LogError(ex, "Invite cleanup failed"); }
        }
    }
}
builder.Services.AddHostedService<ExpiredInviteCleaner>();
```

Helm values probes (keys verified against your chart's schema):

```yaml
probes:
  startup:   { httpGet: { path: /health/live,  port: 8080 }, failureThreshold: 30, periodSeconds: 2 }
  liveness:  { httpGet: { path: /health/live,  port: 8080 } }
  readiness: { httpGet: { path: /health/ready, port: 8080 } }
```

## Quality Checklist

- [ ] Liveness has no dependency checks; readiness checks only real dependencies
- [ ] Probe paths set explicitly in Helm values; health routes carry an explicit anonymous decision
- [ ] Background work is idempotent per replica, uses a new scope per iteration, honours `stoppingToken`
- [ ] Intervals and timeouts come from Options; `ValidateOnStart()` on options
- [ ] Shutdown timeout is below the pod grace period

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Database check on `/health/live` (restart loop when the DB blips) | Liveness without dependencies |
| `DbContext` injected into a singleton hosted service | `IServiceScopeFactory`, scope per iteration |
| `while(true)` + `Task.Delay` ignoring `stoppingToken` | `PeriodicTimer` + token |
| Unhandled exception ends the loop silently | Catch, log, continue |
| Exactly-once work in a per-replica loop | A job workload |
| Migrations on startup in a shared environment | Pipeline migrate step |

## Related Skills

`implementing-observability`, `deploying-to-aws`, `implementing-infrastructure-as-code`, `creating-application-services`.
