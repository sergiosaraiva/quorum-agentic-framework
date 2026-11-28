---
name: writing-postgresql-migrations
description: "Generates, reviews and applies EF Core migrations against PostgreSQL safely: additive-first, reviewed before touching any shared environment, expand/contract for renames and drops, and concurrent index builds on populated tables. Use when adding or changing a migration, reviewing one for lock risk or reversibility, or deciding how a schema change reaches an environment."
---

# Writing PostgreSQL Migrations

Design Principles: `.claude/agents/_SHARED-PATTERNS.md`.

## Quick Reference

- `dotnet ef migrations add <Name>` generates; a reviewer (never the author alone) reads `Up` and `Down` before it runs anywhere but a local or CI database. Check the generated SQL with `dotnet ef migrations script <from> <to>`
- Shared environments apply migrations through a pipeline step (an `efbundle` or equivalent), never through application startup and never `dotnet ef database update` from a laptop. `EnsureCreated()` is local dev and tests only
- Additive-first: add nullable, backfill, then add `NOT NULL` in a later migration. Never one migration adding a `NOT NULL` column without a default to a populated table
- Never edit a migration already applied to a shared environment; write a new one
- One migration per current requirement: no speculative columns, tables or indexes (deferral is recorded, adding later is additive)
- Data a migration ships: schema plus reference rows that must exist everywhere (natural-code keyed) and seeded single-row settings. Environment-varying values (endpoints, TTLs, switches, credentials) never go in a migration
- Review EF-generated names and types: precision on decimals, `timestamptz`, constraint names under 63 bytes, no unintended `DROP` of a column that EF thinks was renamed
- Hand-written SQL (`EXCLUDE USING gist`, functional indexes, triggers) goes in embedded `.sql` files applied from `Up()`; write `Down()` explicitly and test both directions on a populated database

## Decision Tree

```
Nullable column?                     -> one migration, safe
NOT NULL column on populated table?  -> add nullable -> backfill -> NOT NULL in a follow-up migration
Rename a column or table?            -> expand/contract: add new, dual-write/backfill, move readers, drop old in a later release
Drop a column or table?              -> grep the solution and confirm nothing reads it; ship the drop one release after readers are gone
Change a column type?                -> add a new column and backfill, or a table rewrite only in a maintenance window
Index on a table that holds data?    -> concurrent build in its own migration (below)
New index on a table created in the same migration, or known empty? -> plain CreateIndex
Large backfill?                      -> batched, set-based, outside the schema migration transaction, resumable
```

## Index on a populated table

A plain `CREATE INDEX` blocks every write for the whole build. `CREATE INDEX CONCURRENTLY` holds a lighter lock (reads and writes continue; `ALTER TABLE` waits) at the cost of about two table scans, and it cannot run inside a transaction.

Hypothetical schema for the rows below: an `<schema>."order"` table with a `customer_id` FK to a `customer` table (the landed `order` has neither).

| Part | Pattern |
|------|---------|
| Migration | Holds nothing else: EF commits the transactional part, then runs the build, then writes the history row, so a mixed migration that fails leaves a committed half and an INVALID index |
| `Up` | `migrationBuilder.Sql("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_order_customer_id ON <schema>.\"order\" (customer_id);", suppressTransaction: true);` one statement per call, ending with `;` |
| `Down` | `migrationBuilder.Sql("DROP INDEX CONCURRENTLY IF EXISTS <schema>.ix_order_customer_id;", suppressTransaction: true);` |
| Idempotent | `IF NOT EXISTS` so a crash between the build and the history row can be re-run |
| Fail closed | A failed or cancelled build leaves `pg_index.indisvalid = false`; a bare rerun reports success while the index stays invalid. Run a preflight first that raises if any index in a non-system schema is invalid, naming it and the `DROP INDEX CONCURRENTLY` fix |
| Model | The raw-SQL index is not in the EF model; document it with the table so a parity test can credit it |
| Role | The migrating role owns the table and has `CREATE` on the schema |

Recovery: remove the cause (duplicates for a unique index, a timeout), drop the invalid index concurrently as the migrator role, rerun the migration step. Review with `dotnet ef migrations script <from> <to>`, not `--idempotent`, which wraps the build in a `DO` block PostgreSQL rejects.

## Per-tenant rollout (database-per-tenant only)

A pipeline job loops over tenant databases, applies the bundle per tenant, records per-tenant success, stops the wave on the first failure, and gates the application rollout on every tenant reaching the target schema version. Set `statement_timeout`, `lock_timeout` and `idle_in_transaction_session_timeout` on the migrator connection deliberately; verify their effect on a concurrent build before relying on them.

## Quality Checklist

- [ ] Reviewed by someone other than the author; `Up` and `Down` both read
- [ ] No `NOT NULL` without default on a populated table; no bare rename or drop
- [ ] Indexes on populated tables are concurrent, in their own migration, with preflight
- [ ] Generated types and precision match the entity conventions (`database`)
- [ ] Migration applied by the pipeline, not at app startup; tested against a populated database in a Testcontainers run
- [ ] No environment-specific value or secret in the migration

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Edit an applied migration | New migration |
| `Migrate()` on app start in a shared environment | Pipeline migrate step |
| One migration: create table, backfill and concurrent index | Separate migrations |
| `--idempotent` script containing a concurrent build | Per-migration script review |
| Bare rename of a live column | Expand/contract |
| `Down()` left as the generated stub for hand SQL | Write and test it |

## Related Skills

`database`, `deploying-the-application` (migrate step), `tuning-postgresql-queries` (does the index earn its place), `writing-integration-tests`.
