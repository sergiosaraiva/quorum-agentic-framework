# Q&A knowledge base (questions and decisions)

This is the project's memory of what was asked and decided. Before asking a human or assuming anything, agents search it; when it is silent they record a new question and continue with unblocked work. It is read through the MCP server `qa-kb` (`search`, `get`, `open`, `related`) or `scripts/kb/search.py --kb qa`.

The five records shipped here (`BQ-001`, `BQ-002`, `TQ-001`, `TQ-002`, `OD-001`) are examples for an invented "Acme Orders" domain. Replace them with your own.

## Record kinds

| Kind | Meaning | Typical decider | Statuses |
|------|---------|-----------------|----------|
| `BQ` | Business question: behaviour, scope, rules | product owner | `open`, `answered`, `closed` |
| `TQ` | Technical question: design, tooling, data model | tech lead | `open`, `answered`, `closed` |
| `OD` | Owner decision: a recorded choice that binds later work, or an accepted risk (`accepted_risk: true`) | whoever owns it, or the role that owns the risk | `decided`, `closed` |

An answered question that settles a design choice usually also produces an `OD` that cites it. An accepted risk is an `OD` too: the owner accepts a known, unfixed finding for a limited time (see `accepted_risk` and `expires` below).

## Layout and format

One file per record in `questions/records/<ID>.md`.

```markdown
---
id: BQ-003
kind: BQ
title: One-line question
status: open
decider: product-owner
priority: P1
asked: 2026-01-10
answered: 2026-01-12
related: [TQ-001]
chunks: [BC-003]
example: true
---
## Question
## Options
## Answer        (or "## Decision" for an OD)
## History
```

| Field | Meaning |
|-------|---------|
| `id`, `kind`, `title` | `BQ-nnn` / `TQ-nnn` / `OD-nnn`; the prefix must match `kind` |
| `status` | `open`, `answered`, `decided` or `closed` (no other value; lint and `schema.sql` reject it) |
| `decider` | role that must answer (required) |
| `priority` | `P1` (blocks work) to `P3` |
| `asked` | date the record was raised (`YYYY-MM-DD`) |
| `answered` | optional date (`YYYY-MM-DD`) the answer or decision was recorded; lint uses it as the reference for `expires`. It is kept with the record but is not a database column and not a search filter |
| `related` | other record ids; lint fails on an unknown id |
| `chunks` | business KB chunk ids the record concerns; lint fails on an unknown id |
| `accepted_risk` | optional, `true` or `false`; only on kind `OD`. `true` marks a recorded risk acceptance and requires `expires`, a `related` BQ/TQ record (the question that raised the risk) and a non-empty `## Decision` stating the risk, the owner who accepted it, the mitigation and what happens at expiry |
| `expires` | `YYYY-MM-DD`; required when `accepted_risk` is `true`, an error otherwise; must be after `answered` (or `asked` when `answered` is absent). From the day after this date, lint prints a WARNING (the exit code is unchanged). Like `answered`, it is kept with the record, not stored in the database and not returned by the MCP tools |
| `example` | optional `true` marks demo content to delete when you adopt the template |

Statuses `answered` and `decided` require an `## Answer` or `## Decision` section (lint enforces it). To retire a record that a later one replaces, set its status to `closed` and add a line "Superseded by <id>" under `## History`; no other status exists. The MCP `search` tool filters only by `query`, `k`, `kind` and `status`. Rules for writing records: `questions/CLAUDE.md`. Tables: `questions/schema.sql` (the ingest script applies it).
