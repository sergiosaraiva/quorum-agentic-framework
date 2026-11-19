---
name: implementing-observability
description: Implements structured logging, metrics and distributed tracing for an ASP.NET Core + Angular app on AWS with ILogger JSON logs, OpenTelemetry (OTLP) and CloudWatch alarms that page a human on user-impact signals. Use when adding logging, tracing or metrics, wiring OpenTelemetry, defining alarms, or reviewing what a service emits.
---

# Implementing Observability

Design Principles: `.claude/agents/_SHARED-PATTERNS.md`. Observability is a required concern; do it with the least machinery that answers real operational questions.

## Proportionality

- Baseline for every service: structured `ILogger` logging with scopes plus the `/health/*` endpoints (`managing-application-lifecycle`). A new endpoint needs nothing more by default
- Use OpenTelemetry's built-in instrumentations (ASP.NET Core, EF Core, `HttpClient`, runtime) once. Hand-write an `ActivitySource` or `Meter` only when a named SLO or a recurring incident cannot be answered by the built-ins
- Alarm only on user-impact signals you would act on at 3am (error rate, p99 latency, queue depth). Each alarm has an owner and a runbook line
- No logging or telemetry abstraction over `ILogger`/OpenTelemetry. Pick the right level (no chatty `Information` in loops). Never log PII, secrets or tokens
- Sampling rate, exporter endpoint, service name and thresholds are configuration (`OTEL_*` env vars, Options, Helm values), not literals
- Audit (for auditors: who did what, append-only) and logging (technical diagnostics) are separate concerns with separate storage

## Quick Reference

- JSON console logs with scopes so CloudWatch Logs Insights can query fields
- Structured message templates (`{ReportId}`), never string interpolation
- A correlation id (trace id) on every log line; propagate it to outbound calls and return it in error responses
- Request-scoped context (tenant, user id) is added once by middleware through `logger.BeginScope`, not repeated at each call
- Instrument every external dependency (database, object store, third-party API) so a trace shows the full path
- Frontend errors reach the backend through a small error-reporting endpoint or a browser telemetry exporter; verify the choice before adding a vendor SDK

## Decision Tree

```
Debug one request?             -> structured logs with the trace id
Is the system healthy now?     -> metrics + CloudWatch alarms
Where is the time going?       -> distributed tracing (OpenTelemetry -> X-Ray or your OTLP collector)
Would this page someone at 3am?-> alarm on error rate or p99, not raw CPU
Need an audit trail?           -> separate append-only audit table/service, not logs
```

## Examples

```csharp
// Program.cs
builder.Logging.AddJsonConsole(o =>
{
    o.IncludeScopes = true;
    o.JsonWriterOptions = new JsonWriterOptions { Indented = false };
});

builder.Services.AddOpenTelemetry()
    .ConfigureResource(r => r.AddService(builder.Configuration["OTEL_SERVICE_NAME"] ?? "app-api"))
    .WithTracing(t => t
        .AddAspNetCoreInstrumentation()
        .AddEntityFrameworkCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter())              // endpoint/sampling from OTEL_* env vars
    .WithMetrics(m => m
        .AddAspNetCoreInstrumentation()
        .AddRuntimeInstrumentation()
        .AddOtlpExporter());

// In a service: structured fields, no tenant parameter (the middleware scope carries it)
logger.LogInformation("Report {ReportId} exported in {DurationMs}ms", reportId, elapsedMs);
```

Verify current package names and versions before pinning `OpenTelemetry.*` in `Directory.Packages.props`; add them with the first real use.

Alarm sketch (user-impact signals):

| Alarm | Signal | Action |
|-------|--------|--------|
| API 5xx rate | 5xx / requests over 5 min above an agreed threshold | page on-call, runbook link |
| p99 latency | p99 above SLO for 10 min | page or ticket by severity |
| Queue depth/age | oldest message age growing | ticket, page if customer-visible |

Alarm definitions are infrastructure: define them as code with the tool your team chose (`implementing-infrastructure-as-code`); flag it if no path is confirmed. Do not click alarms into the console.

## Quality Checklist

- [ ] JSON logs with scopes; templates, not interpolation; no PII, secrets or tokens
- [ ] Trace id correlates logs, traces and error responses
- [ ] Built-in OpenTelemetry instrumentation only, until a named question requires more
- [ ] Config via env vars/Options; no literal endpoint or sampling rate
- [ ] Each alarm has an owner and a runbook line; audit stays separate from logs

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| `LogInformation($"Report {id} exported")` | Message template with named fields |
| Logging a token or a full request body | Log ids and outcomes |
| Alarm on CPU% | Alarm on error rate or p99 |
| Custom metrics for every endpoint | Built-ins first |
| Tenant id passed to every log call | One scope in middleware |
| Audit events written only to application logs | Dedicated audit record |

## Related Skills

`managing-application-lifecycle`, `deploying-to-aws`, `implementing-infrastructure-as-code`, `creating-configuration-options`.
