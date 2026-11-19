---
name: tuning-postgresql-queries
description: Diagnoses and verifies PostgreSQL query performance. Identifies the query, measures it on a lab database at a stated data tier, reads the EXPLAIN plan, proposes candidates in order (query rewrite, index, extended statistics, settings) and accepts one only with before/after buffer and plan evidence. Use for a slow-query request, an EF Core query on a large table flagged in review, or to measure whether a new index earns its place. Not per diff, and not for API-level load tests.
---

# Tuning PostgreSQL Queries

Runs as test-automator's explicitly triggered database performance stream, never on every diff. Triggers: a `quality-guardian` EF query-safety finding, a slow-query report, or a request to prove an index.

## Quick Reference

- The model proposes, measurement decides. Every candidate is verified on real data with a real `EXPLAIN`; LLM index suggestions vary between runs
- The stream proposes and never changes production code. An accepted index goes to `code-engineer` as a migration (`writing-postgresql-migrations`, concurrent build on populated tables)
- Stop rule: if the proposed index already exists (check the migrations and the table's documented indexes), report it and propose nothing
- No index without a named consumer query (`database`: no speculative schema)
- Evidence: total buffers touched (`shared hit + read`) and plan shape under stated settings are primary; timing is secondary. Absent an agreed target, report relative change and plan regressions, not absolute pass or fail
- Lab rules: local Docker (Testcontainers) only, never CI, never a shared or live database, no ad hoc `psql` against shared systems. Populate data with `scaling-performance-test-data`; a plan measured on a near-empty database proves nothing
- Run on the lowest PostgreSQL major you support in production; a win that rests on a newer-only feature is not accepted alone

## Method

| Step | Action |
|------|--------|
| 1. Identify | Capture the exact SQL (EF: `ToQueryString()` or logged SQL with parameters), its frequency and the table sizes |
| 2. Reproduce | Lab database at a stated tier with a manifest; record the settings that matter (`shared_buffers`, `work_mem`, `effective_cache_size`, `random_page_cost`, `jit`, `max_parallel_workers_per_gather`) |
| 3. Baseline | `VACUUM (ANALYZE)` the tables, warm run, then `EXPLAIN (ANALYZE, BUFFERS, SETTINGS)` as the application role; run it several times |
| 4. Read the plan | Seq scan on a selective filter, wrong join order or type, sort/hash spilling to disk, misestimated rows (estimate vs actual), nested loop over large inputs, repeated index scans (N+1 shape) |
| 5. Candidates in order | (a) rewrite the query or EF projection (filter earlier, drop `Include`, keyset pagination, set-based update); (b) an index; (c) extended statistics for correlated columns (`CREATE STATISTICS`); (d) settings, last and only with a stated reason |
| 6. Verify | Re-run step 3 with the candidate; compare buffers and plan shape; check write cost and size of the new index |
| 7. Report | Before/after table, plan excerpts, candidate rejected-or-accepted with reason, hand-off |

## Candidate patterns

| Symptom | Candidate |
|---------|-----------|
| Equality + range filter on a large table | btree on `(equality_cols, range_col)` |
| Filter on a small subset (status, `deleted_at IS NULL`) | partial index with the same predicate |
| Query reads few columns, heap fetches dominate | covering index (`INCLUDE`) |
| Estimate far from actual with correlated columns | `CREATE STATISTICS (dependencies, ndistinct) ...`, `ANALYZE` |
| `ILIKE '%x%'` | trigram GIN (`pg_trgm`), or rethink the feature |
| OFFSET pagination slow on deep pages | keyset pagination |
| JSON containment | GIN on the expression, only if queried |
| Lock-heavy bulk write | batched set-based statements |

Never recommend `random_page_cost` or `work_mem` changes from one query's plan without checking the workload; settings are a platform decision.

## Report template

```
Query: <sql or EF source>   Tier: golden-1x   Image: postgres:<major>   Settings: <non-default>
Baseline: buffers 48,210 (hit 40,100 / read 8,110), plan: Seq Scan on sales."order" ...
Candidate: CREATE INDEX CONCURRENTLY ix_order_customer_id_status ON sales."order"(customer_id, status)
After: buffers 212, plan: Index Scan using ix_order_customer_id_status
Cost: index 38 MB, write overhead on insert measured +4%
Decision: accept -> code-engineer migration (concurrent)
```

## Quality Checklist

- [ ] Measured on a populated lab at a stated tier, not an empty database
- [ ] Before and after buffers plus plan shape reported, not recalled
- [ ] Candidate order respected; index justified by a named query and not already present
- [ ] Write cost and index size reported
- [ ] Nothing applied outside the lab; hand-off goes through code-engineer

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Trusting an index suggestion without `EXPLAIN` | Verify on data |
| Judging a plan on 1,000 rows | Use a realistic tier |
| Timing a cold first run | Warm runs, buffers first |
| Index for every FK "just in case" | Index only named queries |
| Tuning settings before rewriting the query | Rewrite, index, statistics, settings |

## Related Skills

`scaling-performance-test-data`, `database`, `writing-postgresql-migrations`, `load-and-performance-testing`.
