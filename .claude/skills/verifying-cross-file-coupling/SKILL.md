---
name: verifying-cross-file-coupling
description: Use when verifying that files which must agree have not drifted. Six coupling categories C1-C6 (DTO and TypeScript, EF Core and raw SQL, options and deployment configuration, container and app config, dependency and image-tag pins, duplicated formulas). Used by regression-detective and documentation-reviewer.
---

# Verifying Cross-File Coupling

## Quick Reference

| Code | Coupling | File A | File B |
|------|----------|--------|--------|
| C1 | DTO and TypeScript interface | `src/Api/Features/**/Dtos.cs` | `frontend/src/app/**/*.model.ts` or inline interface |
| C2 | EF Core entity or query shape and raw SQL | `src/Infrastructure/**/Entities`, configurations | hand-written SQL: migrations, reports, seed scripts |
| C3 | `appsettings*.json` / `IOptions<T>` and deployment configuration | `**/*Options.cs`, `appsettings.json` | Deployment configuration `env` entries (possibly in another repo) |
| C4 | Container or deployment config and app startup expectations | `Dockerfile`, compose file, deployment health checks/resources/`env` | `Program.cs` required config, health endpoints |
| C5 | Version pins and their other pin sites | `*.csproj`, `package.json`, an image tag | lock files; every other file pinning the same image (compose, Testcontainers constant, `Dockerfile FROM`) must show the identical tag |
| C6 | Duplicated business formula | any two files computing the "same" thing | - |

**Cross-repo note**: if deployment configuration lives in a separate repository, check C3/C4 only when that file is supplied with the diff. Otherwise report them as `unaudited (blocked)`; never reconstruct a values file from memory.

## Workflow

For each category the diff touches:

1. Identify File A and File B.
2. Read both; never infer B from A's name.
3. Diff the shapes: field names, types, nullability, casing. Verify the real JSON casing (default `System.Text.Json` web policy is camelCase) against what the TypeScript side expects.
4. Report drift with both file:line citations and the runtime consequence.

## Examples

**C1**
```csharp
// Dtos.cs
public sealed record ReportDto(Guid Id, string Title, string Status);
```
```typescript
// report.model.ts
export interface ReportDto { id: string; title: string; state: string }   // drift: wire name is "status"
```
Finding: `state` is always `undefined` at runtime. The compiler cannot catch it because HTTP responses are untyped at the boundary.

**C3**
```csharp
public sealed class ReportingOptions { [Required] public string ExportBucketName { get; init; } = ""; }
```
```yaml
env:
  - name: Reporting__ExportBucket        # should be Reporting__ExportBucketName
    value: ${EXPORT_BUCKET}
```
Finding: startup fails (or silently binds empty) because the double-underscore key does not match the bound property. `ValidateOnStart()` turns this into a loud failure; verify it is enabled.

**C5**
```
compose.yaml: postgres:16.4        Testcontainers constant: postgres:16.3
```
Finding: tests run against a different server version than local dev. Use one constant for the tag.

**C6**
```csharp
// ReportService: items.Sum(i => i.Price * i.Quantity) * (1 - discountRate)
// InvoiceService: items.Sum(i => i.UnitPrice * i.Qty) * (1 - discount)   // rounding fixed only in ReportService
```
Finding: copies that must agree have already drifted. Extract one shared calculator (source of truth). If the copies are merely similar and need not agree, leave them; duplication beats the wrong abstraction.

## Quality Checklist

- [ ] Both sides of every claimed coupling were actually read
- [ ] JSON casing and nullability verified, not assumed
- [ ] Config keys checked against the real binding path (section nesting with `__`)
- [ ] Every pin site of an image or package compared
- [ ] Formula findings recommend extraction when copies must agree
- [ ] Unreachable files reported as `unaudited`, not skipped silently

## Related Skills

- `detecting-regressions`: B1, B3, B4 map onto C1, C3, C6
- `creating-angular-api-clients`: the C1 TypeScript side
