---
name: recording-decisions
description: Recalls recorded questions, answers and decisions before asking or assuming, and records every new answer or decision as a record under questions/records/ (BQ business question, TQ technical question, OD owner decision). Use before asking the user or owner anything, before relying on a prior decision, scope or expected behaviour, before describing a slice, and whenever the user gives an answer or decision in a session. Not for the record file format details (questions/README.md) or business facts (those live in the Business KB).
---

# Recording decisions

The Q&A KB (`questions/`, MCP server `qa-kb`) is the shared memory of every question, answer and decision. Never assume: look it up first. Never leave an answer only in the conversation. File format and lint: `questions/README.md`, `questions/CLAUDE.md`.

## Record types

| Type | Prefix | Holds | Typical decider |
|------|--------|-------|-----------------|
| Business question | BQ | Product behaviour, rules, scope, wording | business role |
| Technical question | TQ | Architecture, tooling, data model, infra | technical role |
| Owner decision | OD | A decision taken (scope, trade-off, process) | the owner |

Ids are `BQ-001`, `TQ-001`, `OD-001` (zero padded, next free number, never reused). Files: `questions/records/<ID>.md`.

The OD-versus-answer rule (confirmed in OD-022). An `OD` is mandatory for a waiver of a rule or gate (for example a slice pickup exception), a scope change and an accepted risk. An answered BQ/TQ settles a design choice by itself; it needs an `OD` only when the choice binds work beyond the question. The `decider` is the role that owns the subject of the decision, not the person present: one person holding both roles answers each record in the role it belongs to, and `## History` says so ("answered as technical lead"). When the subject has no clear owner role, record a TQ asking which role decides.

## Record fields (as shipped)

Frontmatter:

| Field | Content |
|-------|---------|
| `id`, `kind`, `title` | Prefix plus number; `kind` matches the prefix; one-line searchable title |
| `status` | `open`, `answered`, `decided` or `closed` (no other value) |
| `decider` | Role that owns the answer (a role, not a person); required |
| `priority` | `P1` (blocks work, or must be answered before a milestone named in `## Question`; confirmed in OD-022) to `P3`. A change of priority edits the frontmatter and adds a History line with the reason in the same edit; the frontmatter is the current value |
| `asked` | Date raised (`YYYY-MM-DD`) |
| `answered` | Optional date the answer or decision was recorded |
| `related` | Other record ids; lint fails on an unknown id |
| `chunks` | Business KB chunk ids the record concerns; lint fails on an unknown id |
| `accepted_risk`, `expires` | Optional, `OD` only: `accepted_risk: true` needs `expires: YYYY-MM-DD` and a `related` BQ/TQ; the owner has accepted a known risk (`## Decision`: risk, owner, mitigation, expiry action). `expires` must follow `answered` or `asked` and is an error without `accepted_risk: true`; past it, lint prints `WARN` unless the OD is `closed` (lint checks the Decision is non-empty, not its content) |
| `example` | Optional `true` for demo content to delete on adoption |

Body sections: `## Question`, `## Options` (recommended first, one-line trade-offs), `## Answer` (or `## Decision` for an OD; required once `answered` or `decided`), `## History` (append-only dated lines: opened, answered, who).

Status flow: `open` -> `answered` (a question answered) or `decided` (an owner decision) -> `closed` (retired). To replace a record, set the old one to `closed` and add the line "Superseded by <id>" under its `## History`; there is no `superseded` status. Never delete or rewrite earlier text.

## Recall before asking or assuming (mandatory)

| Step | Action |
|------|--------|
| 1 | Search `qa-kb`: `mcp__qa-kb__search` (filters `query`, `k`, `kind`, `status`) with the topic, synonyms and the slice id; then `mcp__qa-kb__get` for the id. Without MCP: `_SHARED-PATTERNS.md` Never Invent rule 7 |
| 2 | Re-read the record; a `closed` record's History may point to its replacement. Never cite an id from memory |
| 3 | Found and `decided` or `answered`: act on it, cite the id, no question |
| 4 | Found, records conflict: flag both ids; ask once, batched |
| 5 | Found, `open`: if it blocks you and is the user's, ask citing the id; otherwise proceed on its working assumption and flag the id |
| 6 | Not found: check the Business KB (`business-kb`) for product behaviour; pass `topic` to its `search` (a topic from `stats`) so `QF-*` chunks do not outrank domain ones (unknown-topic behaviour: rule 7). Still silent: record a BQ or TQ with a decider; proceed with unblocked work only |

## Record every answer (mandatory)

| Rule | Detail |
|------|--------|
| When | In the session the answer is given |
| Where | Update the existing record; else create one with the next free id. Before the first push run `python3 scripts/kb/check_chunks.py --against origin/main` (and per sibling branch; fetch first): a warning means a colliding new id or a retitled record; renumber only a new record (the later branch). Without Bash (`requirements-analyst`, `solution-architect`) list both runs as `probe_requests` (`command`, `expected`); the session runs them (`_SHARED-PATTERNS.md` Subagent Limits) |
| Who | An agent whose role includes records (`requirements-analyst`, `solution-architect`, `documentation-curator`) writes it itself. Every other agent, and every read-only agent, returns `questions_to_record` (kind, question, decider, recommended option) in its final message; the calling session or `documentation-curator` writes the record |
| Duplicates | Search first; update, or close and supersede; never silently overwrite |
| Attribution | Decider role, date, who gave the answer |
| Review ids | A review finding id (`SEC-001`, `RD-1`) is not stable. Cite the record id everywhere; the finding id may appear once, in History, as origin |
| Then | Run `python3 scripts/kb/check_chunks.py`; re-ingest the Q&A KB if you use the pgvector backend (`questions/README.md`) |

## Flag is not ask

"Flag it" and "do not guess" mean: record the item (record, PR description, deferred list) and carry on with unblocked work. Ask the user only when blocked on a decision that is theirs: product behaviour where KB and spec conflict or are silent, a scope change, or a destructive or outward-facing action the request did not cover. A subagent cannot ask: it returns the open items to the calling session. A question that belongs to another role is recorded with that `decider`, not asked. When a stop is warranted, finish all unblocked work, then ask every open item in one batched round, recommended option first.

## Anti-patterns

| Wrong | Right |
|-------|-------|
| Asking a question already `decided` | Search, cite the id, act |
| Chat or personal memory as the only copy of a decision | Record it |
| One question per turn | Batch |
| Editing an old decision in place | New record, close the old one with "Superseded by <id>" |
