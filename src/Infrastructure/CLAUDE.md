# src/Infrastructure guide

This file exists because it is loaded when you work under `src/Infrastructure/`; the nearest CLAUDE.md wins and adds persistence rules to the root guide.

## Layout

| Path | Holds |
|------|-------|
| `Persistence/AppDbContext.cs` | the single `DbContext`; applies configurations from the assembly |
| `Persistence/Entities/` | entity classes, grouped by schema or feature |
| `Persistence/Configurations/` | one `IEntityTypeConfiguration<T>` per entity |
| `Migrations/` | EF Core migrations; reviewed before any shared environment |

## Conventions

| Topic | Rule |
|-------|------|
| Naming | snake_case tables and columns (`UseSnakeCaseNamingConvention` or explicit `ToTable`/`HasColumnName`), singular table names, schema-qualified when more than one schema |
| Keys | `Guid` ids generated in the application (`Guid.CreateVersion7()`), never database-generated sequences unless a requirement says so |
| Money and quantities | `numeric(p,s)` with explicit precision, never `double` or `float` |
| Time | `timestamptz`, UTC only (`DateTimeOffset`) |
| Enums | stored as text with a check constraint, not as integers |
| Audit columns | `created_at`, `updated_at` on every entity; soft delete (`deleted_at`) only when a requirement names it |
| Database locale | every environment's database is created with a UTF-8 `LC_CTYPE` (for example `en_US.utf8`), written into the infrastructure code; case-insensitive text search uses `ILIKE` and depends on it for non-ASCII letters (OD-017) |
| Log redaction | required before the first deployment (OD-012, OD-027): proxy and access logs, telemetry `url.query` and database log settings redact or omit the `customerName` query value and bound parameters, set in the infrastructure code of the chosen target and verified by the infrastructure review. Until a target is chosen it is a deployment follow-up: record a TQ at target selection |
| Nullability | entity properties follow nullable reference types; optional means `T?` and a nullable column |

## Migration workflow

1. `dotnet ef migrations add <Name> --project src/Infrastructure --startup-project src/Api`.
2. `dotnet tool restore` first on a fresh checkout: `.config/dotnet-tools.json` pins `dotnet-ef` to the EF Core version in `Directory.Packages.props` (keep them equal when you bump one). After a model change, `dotnet ef migrations has-pending-model-changes --project src/Infrastructure --startup-project src/Api` must report no changes.
3. Read the generated SQL: `dotnet ef migrations script --idempotent`. Prefer additive changes; a destructive change (drop, rename, type narrowing) needs a recorded decision and a two-step rollout.
4. Large tables: create indexes concurrently in a hand-edited migration with `suppressTransaction: true`.
5. Never edit a migration already applied to a shared environment; add a new one.
6. `EnsureCreated()` only in tests; apply migrations at deploy time through a job, not at API startup in production. The API's `Database:CommandTimeoutSeconds` (default 10, OD-025) applies to every command of this host's `DbContext`, migrations included, so the migration run sets its own larger value (the tests set one on the context).

## Do not

- Put business logic in entities or configurations.
- Share one `DbContext` instance across threads.
- Use raw SQL without parameters.
