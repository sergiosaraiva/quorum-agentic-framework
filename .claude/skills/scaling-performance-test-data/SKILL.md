---
name: scaling-performance-test-data
description: Builds, scales and verifies a PostgreSQL lab dataset for performance work at stated tiers (seed, reference-1x, load-2-3x, stress-10x), using structural clone with key remap, seeded set-based volume fill with measured skew, per-table verification and a reproducible lab manifest. Use when query tuning needs a populated database in a Testcontainers lab, or when asked to multiply reference data into artificial data for load scenarios. Not for functional test fixtures or k6 scripts.
---

# Scaling Performance Test Data

Feeds `tuning-postgresql-queries`. Functional fixtures belong to `writing-integration-tests`; load scripts to `load-and-performance-testing`.

## Quick Reference

- Output: a lab database at a stated tier plus a lab manifest, built inside `dotnet test` with Testcontainers. Never a shared, staging or live database; never CI
- Skew is measured, never assumed: read `pg_stats` (`n_distinct`, `most_common_vals`, correlation) on the real tables and reproduce that shape. Never multiply uniformly
- Source order: reference dataset if one exists, else the seed rows plus synthetic fill. Never invent master data from scratch
- Row targets are multiples of the loaded dataset's per-table counts. With no dataset loaded they are assumptions: record `targets_assumed: true` and the source of each target
- Integrity stays on: never `session_replication_role = replica`, never `ALTER TABLE ... DISABLE TRIGGER`. Load parents before children in foreign-key order. `SET CONSTRAINTS ALL DEFERRED` only affects constraints declared `DEFERRABLE`
- Reproducible: same seed, identical statements, one session started with `SELECT setseed(0.42)`. Fill timestamps from one fixed constant (not `now()`). Leave generated keys out of any hash
- Personal data: use synthetic or pseudonymized values only, never a production copy

## Tiers

| Tier | Size | Source | Purpose |
|------|------|--------|---------|
| `seed` | seed rows only | `seed` | schema and plan smoke checks |
| `reference-1x` | the reference dataset as loaded | `reference` | reference plans |
| `load-2-3x` | 2x to 3x loaded | `reference` clone or `synthetic` | expected-load plans |
| `stress-10x` | about 10x loaded | clone or synthetic | breaking-point plans |

Compute targets from the loaded dataset and record them. Keep only the retention window the product really keeps online; a tier spanning more history is an upper bound.

## Method

| Step | Action |
|------|--------|
| 1. Measure | Row counts and `pg_stats` per table; list parents-before-children order from `pg_constraint` |
| 2. Clone | Copy the reference rows N times with a key remap: new UUIDv7 (or `bigint` offset) per copy, remapped through a temp mapping table so foreign keys stay valid; unique natural keys get a suffix per copy |
| 3. Fill | Set-based `INSERT ... SELECT generate_series(...)` with distributions drawn from the measured skew (`floor(power(random(), k) * n)` for heavy tails); never row-by-row loops |
| 4. Verify | Row count per table within tolerance of target; zero FK violations; unique indexes valid; `pg_stats` shape within tolerance after `ANALYZE`; no table left unanalyzed |
| 5. Manifest | Write the manifest next to the test output |

```sql
-- Skewed foreign-key fill (placeholders; statuses and scale 2 follow the Acme example, OD-004 and OD-001): 80% of orders to 5% of customers
-- The rank is drawn per row first: a scalar subquery with random() inside is uncorrelated, runs once (InitPlan) and gives every row the same customer
WITH picks AS (
    SELECT g, 1 + floor(power(random(), 4) * :customer_count)::int AS rn
    FROM generate_series(1, :order_target) g
)
INSERT INTO sales."order" (id, customer_id, status, total_amount, created_at)
SELECT uuidv7(),
       c.id,
       (ARRAY['draft','placed','paid','shipped','closed'])[1 + floor(random() * 5)::int],
       round((random() * 5000)::numeric, 2),
       :fixed_timestamp::timestamptz - (random() * interval '365 days')
FROM picks p
JOIN tmp_customer_rank c USING (rn);
```

`uuidv7()` is built in from PostgreSQL 18; on 16 or 17 generate keys in the test or with an extension (verify). Run `ANALYZE` and `VACUUM` after load, and create indexes after bulk fill when the plan under test allows it.

## Lab manifest (example)

```json
{ "tier": "load-2-3x", "source": "reference", "seed": 0.42, "image": "postgres:16",
  "targets_assumed": false,
  "tables": { "sales.order": { "reference_rows": 120000, "target": 300000, "actual": 300000, "skew_source": "pg_stats" } },
  "fk_violations": 0, "analyzed": true, "generated_at": "<fixed-timestamp>" }
```

## Quality Checklist

- [ ] Skew measured from `pg_stats`, not guessed or uniform
- [ ] FK order respected, constraints and triggers enabled, zero violations
- [ ] Deterministic: seed set, fixed timestamp constant, set-based SQL
- [ ] Per-table verification and a manifest produced; targets_assumed stated
- [ ] No production personal data; lab only, never CI or a shared database

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Multiplying every table uniformly | Reproduce measured skew |
| Disabling triggers or FKs to load faster | Load in FK order with integrity on |
| `now()` and unseeded `random()` in fill SQL | Fixed constant and `setseed` |
| Loop-per-row inserts | `generate_series` set-based |
| Forgetting `ANALYZE` after load | Analyze, then measure |
| Copying production data | Synthetic or pseudonymized |

## Related Skills

`tuning-postgresql-queries`, `database`, `writing-integration-tests`, `load-and-performance-testing`.
