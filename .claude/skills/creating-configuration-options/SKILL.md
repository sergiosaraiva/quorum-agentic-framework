---
name: creating-configuration-options
description: Owns the no-hard-coded-values pattern, strongly-typed configuration classes bound through the Options pattern and validated at startup, and when NOT to add configuration at all. Use when a value (URL, limit, timeout, threshold, page size, feature switch, name) would otherwise appear as a literal in logic, or when adding a new setting.
---

# Creating Configuration Options

This skill owns the "no hard-coded values" rule; other skills point here. Principle: `.claude/agents/_SHARED-PATTERNS.md`.

## Quick Reference

- A value that can differ per environment, tenant or deployment, or that someone may need to tune (URLs, ids, names, thresholds, limits, rates, timeouts, page sizes, feature switches) never appears as a literal in logic. It comes from typed Options (appsettings/env vars), the database (tenant-varying), or deployment values (Helm). Secrets never in source
- A fixed domain or protocol constant (HTTP header name, unit conversion factor, state-machine status string) is a named `const` declared once in the owning type, not an Options property
- One `sealed class` per logical section, bound once, injected as `IOptions<T>`. `IOptionsMonitor<T>` only when the value genuinely changes without a restart
- Validate at startup: `ValidateDataAnnotations().ValidateOnStart()`. Fail fast, not three requests into production
- Never read `IConfiguration["Some:Key"]` in services; bind once, inject the typed options
- Defaults must be safe (a conservative limit, never `int.MaxValue`); a required value has no default and fails startup when missing

## Decision Tree

```
Can the value ever differ by environment, tenant or deployment, or will someone tune it?
  No  -> named const in the owning type; no Options class
  Yes -> continue
Differs per tenant?           -> database (tenant data), not appsettings
Differs per environment?      -> Options class, value from appsettings / env (Helm `env` values)
Changes only on redeploy?     -> IOptions<T>
Changes at runtime (flag)?    -> IOptionsMonitor<T>
Is a secret?                  -> secrets manager surfaced as env/config; user-secrets locally; never appsettings.json
Extending an existing section?-> add a property to that class; a new class only for a new logical section
```

## Examples

```csharp
public sealed class ReportingOptions
{
    public const string SectionName = "Reporting";

    [Range(1, 500)] public int MaxRowsPerExport { get; init; } = 100;
    [Required] public string ExportBucketName { get; init; } = string.Empty;
}

// Program.cs
builder.Services.AddOptions<ReportingOptions>()
    .Bind(builder.Configuration.GetSection(ReportingOptions.SectionName))
    .ValidateDataAnnotations()
    .ValidateOnStart();

public sealed class ReportExportService(IOptions<ReportingOptions> options)
{
    private const string KeyPrefix = "exports/";   // never varies -> const, not config
    private readonly ReportingOptions _options = options.Value;
    // use _options.MaxRowsPerExport, _options.ExportBucketName
}
```

Secrets: locally `builder.Configuration.AddUserSecrets<Program>()` (`dotnet user-secrets set "Database:ConnectionString" "${VALUE}"`); in AWS an external-secrets sync surfaces the value as a normal configuration key. App code is identical; only the provider differs. Put an actionable message on `[Required]` telling a developer which `user-secrets set` command to run. `[Required]` on a non-nullable `int` with a default is redundant; use `int?` when "unset" must be distinguishable.

## Quality Checklist

- [ ] No literal URL, id, name, threshold, limit, rate, timeout, page size or switch in logic
- [ ] Nothing that can never vary became a config knob
- [ ] One options class per logical section, `SectionName` const beside it, no speculative properties
- [ ] `ValidateDataAnnotations().ValidateOnStart()` on every registration
- [ ] No secret in any `appsettings*.json`
- [ ] A new option is also set where each environment is configured (Helm values, `.env.example`, `appsettings.json`); drift is checked by `verifying-cross-file-coupling`

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| `if (rows > 500)`, `TimeSpan.FromSeconds(10)`, a literal vendor URL | Validated Options property |
| Options property for something identical everywhere forever | `private const` |
| `configuration["A:B"]` scattered in services | Bind once to a typed class |
| Secret committed to appsettings | Secrets manager / user-secrets |
| Tenant-specific value in appsettings | Tenant data in the database |
| No startup validation | `ValidateOnStart()` |
| One mega `AppOptions` | One class per section |

## Related Skills

`creating-application-services`, `deploying-to-aws` (how values and secrets reach the pod), `verifying-cross-file-coupling`.
