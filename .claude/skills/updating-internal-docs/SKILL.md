---
name: updating-internal-docs
description: Use when editing any CLAUDE.md, an agent body under .claude/agents, or an internal reference doc. Compact, terse, table-first style for text that models read on every task; minimal edits, nothing lost, no placeholder docs.
---

# Updating CLAUDE.md and Agent Files

## Quick Reference

- Audience is an agent reading on every task, not a human reading once: terse, compact, tables over prose.
- Common abbreviations are fine (`DTO`, `EF Core`, `JWT`); do not spell out what every reader knows.
- Minimal edits: change what is wrong or new; do not rewrite unrelated sections.
- Immutable rules stay immutable: add a new row; never soften an existing one without an explicit recorded decision.
- Compact without losing information: every rule, id, path, threshold and dated decision survives a rewrite. If something moves, leave a pointer to its new owner.
- Document what exists. A planned layer or option appears only when labelled "planned".
- Size budgets: root `CLAUDE.md` bounded, agent body at most 16 KB and SKILL.md at most 7 KB (`python3 scripts/framework_lint.py` warns above); new detailed rules go into a skill, not the root file.

## When to Use

- A new architectural pattern or convention was established
- A layer met its "add when" condition and needs its own sub-`CLAUDE.md`
- A documented pattern changed and the old text is now wrong
- A governed section of root `CLAUDE.md` or an agent body changes

## When NOT to Use

| Case | Use instead |
|------|-------------|
| Single bug fix, no pattern change | nothing |
| User-facing behaviour docs, README, release notes | `updating-external-docs` |
| `.claude/skills/**` bodies | skill-authoring conciseness: one purpose, a description that starts with "Use when", short body, detail in `reference/` |
| KB chunks | the KB chunk authoring rules in `kb/CLAUDE.md` |

Edits to governed sections (agents, skills, root rules) go through `documentation-curator`, then `quality-guardian` || `regression-detective`, then `documentation-reviewer`.

## Style Contract

| Do | Do not |
|----|--------|
| Tables for 3+ comparable rows | Long prose paragraphs |
| One sentence per bullet, key fact first | Multi-sentence "why" unless the why is non-obvious |
| Snippets only when a table cannot state the pattern | Long worked examples; list of alternatives instead of one default plus an escape hatch |
| Cite path plus anchor (symbol, heading, quoted literal) | "the service layer"; line numbers (they rot) |
| Imperative, present tense | Hedging ("might", "perhaps") |

## Example: add a row

```markdown
| File | Layer | Add when |
|------|-------|----------|
| `frontend/CLAUDE.md` | Angular conventions | first 3 feature components exist |
| `frontend/src/app/core/CLAUDE.md` | interceptors, guards, shared services | first 3 cross-cutting core services exist |
```

The `core/CLAUDE.md` row is an illustration of the format; that file does not exist in the template. Create a sub-guide only when its "add when" condition is met.

## Example: new immutable rule

```markdown
9. **Every outbound HTTP call has a timeout and a retry budget from Options.** A bare `HttpClient` call without both is a High review finding.
```

State the rule, its consequence and who enforces it in one or two lines.

## Process

1. Read the current file and its neighbours; find the owner of the fact (one owner, others point to it).
2. Edit the smallest region. Keep ids, paths and thresholds.
3. Check no contradiction with root `CLAUDE.md` or `_SHARED-PATTERNS.md`.
4. Check size budgets and that cross-references resolve.
5. Hand to review; do not self-approve.

## Quality Checklist

- [ ] Tables where 3+ comparable rows exist
- [ ] No information lost; moved items have pointers
- [ ] No contradiction with the root file or shared patterns
- [ ] Planned items labelled "planned"; no placeholder sections
- [ ] Cross-references resolve; no line-number citations
- [ ] Within the size budget

## Related Skills

- `updating-external-docs`: the human-reader style
- `reviewing-documentation`: grounding check afterwards
