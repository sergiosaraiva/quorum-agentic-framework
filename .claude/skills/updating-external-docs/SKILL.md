---
name: updating-external-docs
description: Use when writing or updating human-facing docs in full natural language - READMEs, guides, API references, release notes, ADRs. Plain, active, precise prose grounded in shipped behaviour. Mutually exclusive with updating-internal-docs.
---

# Updating External Docs

## Quick Reference

- Full sentences. Explain an internal term in one clause the first time.
- The reader is a person reading once: optimize for clarity, not density.
- Every behaviour claim is grounded in shipped code or a KB record, never aspirational. Product behaviour comes from the business KB; cite the chunk id where the doc keeps references.
- Release notes say what changed and why it matters to the reader, not an implementation diary.
- Code, identifiers, commands, paths and legal or contractual text are quoted verbatim.

## When to Use

- A feature shipped and the README or guide needs it
- New or changed endpoint: API reference
- Release notes or changelog entry
- Architecture Decision Record for a significant decision

## When NOT to Use

| Case | Use instead |
|------|-------------|
| `CLAUDE.md`, agent bodies, internal reference | `updating-internal-docs` |
| KB chunks | KB chunk rules in `kb/CLAUDE.md` |
| Generated docs | regenerate through the owning script; never hand-edit |

## Style Contract

| Do | Do not |
|----|--------|
| Say why, not just what | Assume the reader has your context |
| Define an internal term on first use | Drop an unexpanded acronym |
| Show a concrete example of the feature in use | Describe abstractly |
| Active voice, present tense for current behaviour | Passive voice; mixing "will" and "does" |
| One term per concept for the whole doc | Switch between "workspace" and "environment" |
| Positive instructions ("Set X before Y") | "Do not forget to..." |

## Sentence Rules

Adapted from Orwell's rules and Simplified Technical English (apply as guidance; precision wins over any rule).

1. No stock metaphor ("under the hood", "move the needle").
2. Short word over long: use not utilize, start not initiate.
3. Cut every word you can ("in order to", "the fact that").
4. Active voice; name the actor when it matters.
5. Everyday word over an insider term when equally accurate; keep a term that carries real technical precision.
6. One main statement per sentence; split at "and it also" or a semicolon.
7. Procedures: one action per step, imperative, in order, with the expected result.
8. Break any rule sooner than write something unclear.

## Templates

**API reference entry**

```markdown
### POST /api/reports

Creates a report. Requires the `reports.write` permission.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| title | string | yes | 1 to 200 characters |

Returns `201 Created` with a `Location` header and the report body.
Returns `400` with a problem-details body when validation fails.
Returns `401` when the token is missing or invalid, `403` when the permission is missing.
```

**Release note**

```markdown
### Report export is faster

Exporting a report with more than 10,000 rows now streams the file instead of building it in memory. Large exports finish in seconds, and the page no longer times out. No action is needed.
```

**ADR**

```markdown
# ADR-001: Use PostgreSQL full-text search

Status: accepted (2026-03-01). Context: why a decision was needed. Decision: what we chose. Options considered: each with one line on why not. Consequences: what gets easier, what gets harder, what is deferred.
```

## Accessibility of docs

Descriptive link text, headings in order, alt text for images, tables with header rows, no information conveyed by colour alone.

## Quality Checklist

- [ ] Every claim true of the shipped system; planned items labelled "planned"
- [ ] One term per concept; internal terms defined once
- [ ] Active voice, short sentences, no stock metaphors
- [ ] Concrete example or request/response included
- [ ] Code and identifiers verbatim; no line-number citations
- [ ] Reviewed by `documentation-reviewer` (grounding plus style spot-check)

## Related Skills

- `updating-internal-docs`: the agent-facing style
- `reviewing-documentation`: grounding and style review
