---
name: creating-cli-tools
description: Creates .NET CLI tools with System.CommandLine for admin tasks and CI/CD utilities that need the EF model or domain code. Check its "When NOT to Build" section first; scripts, migrations and jobs usually fit better. Use when an operator or pipeline needs a command-line entry point to application code.
---

# Creating CLI Tools

Design Principles: `.claude/agents/_SHARED-PATTERNS.md`. Tooling code goes through `code-engineer`.

## When NOT to Build a .NET CLI Tool

- The task does not need the EF model or domain code: use a Bash/Python/PowerShell script under `scripts/`
- Schema changes are EF Core migrations (`writing-postgresql-migrations`), never a tool. Reference data that must exist in every database belongs in a migration, not a seeder
- One argument needs no `System.CommandLine`: read `args[0]`. Use the library for several options or subcommands
- Recurring or operator-visible work is a job (scheduled workload, see `implementing-infrastructure-as-code`), or an in-process `BackgroundService` if it is idempotent per replica (`managing-application-lifecycle`)
- A new tool project needs a stated need that existing scripts cannot meet

## Quick Reference

- Own project at `scripts/<tool-name>/`, referencing `src/Infrastructure` for data access, so no web-hosting dependencies leak in. Pin `System.CommandLine` in `Directory.Packages.props` (verify the current stable version) with the first tool
- Exit codes: `0` success, non-zero on any failure; CI depends on it
- stdout for normal output, stderr for errors and warnings
- Resolve connection strings and secrets exactly as the API does (env var, user-secrets, secrets manager); reuse the shared `DbContext` configuration, never duplicate connection logic
- Any command that mutates data supports `--dry-run`; irreversible ones also need `--yes`
- A tool touching per-tenant data takes the tenant explicitly and fails closed; it never loops over a guessed connection string

## Decision Tree

```
Admin task needing the EF model (optional or environment-specific data, backfill)? -> scripts/<tool>/Program.cs
Runs on a schedule?  -> not a CLI tool: scheduled job, or a BackgroundService if safe per replica
Needs DB access?     -> reference src/Infrastructure and reuse the DbContext configuration helper
```

## Examples

```csharp
// scripts/data-seeder/Program.cs
var envOption = new Option<string>("--environment") { Required = true };
var dryRunOption = new Option<bool>("--dry-run") { DefaultValueFactory = _ => false };

var rootCommand = new RootCommand("Seeds optional environment-specific data")
{
    Options = { envOption, dryRunOption },
};

rootCommand.SetAction(async (parseResult, ct) =>
{
    var environment = parseResult.GetValue(envOption)!;
    using var db = CreateDb(environment);   // connection string from configuration, never a literal
    if (parseResult.GetValue(dryRunOption))
    {
        Console.WriteLine($"[dry-run] Would seed {PendingSeeds(db).Count} records");
        return 0;
    }
    try
    {
        await SeedAsync(db, ct);
        return 0;
    }
    catch (SeedConflictException ex)
    {
        Console.Error.WriteLine($"Seed failed: {ex.Message}");
        return 1;
    }
});

return await rootCommand.Parse(args).InvokeAsync();
```

`System.CommandLine` assembles options and subcommands with object initializers and reads values from `parseResult.GetValue(...)` inside `SetAction`; verify against the pinned version's API (it changed between previews and stable).

## Quality Checklist

- [ ] `--help` documents every option
- [ ] Destructive operations support `--dry-run` (and `--yes` when irreversible)
- [ ] Exit code non-zero on every failure; errors on stderr
- [ ] Connection strings and secrets resolved like the main app; tunables are arguments or Options
- [ ] Per-tenant tools take the tenant explicitly and fail closed

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| `Console.WriteLine` for errors, exit code 0 | `Console.Error.WriteLine` and non-zero exit |
| Hard-coded connection string "just for this script" | Same configuration resolution as the API |
| New tool project for what a 20-line script or a migration does | Extend `scripts/` or write a migration |
| Destructive command with no preview | `--dry-run` and `--yes` |

## Related Skills

`database`, `writing-postgresql-migrations`, `managing-application-lifecycle`, `implementing-infrastructure-as-code`.
