---
name: writing-kb-chunks
description: Style rules for authoring and editing knowledge-base chunks meant for semantic (embedding) retrieval - one topic, self-contained, 40-350 words (aim for 80 to 300), required frontmatter, no AI slop, no redundancy. Use when creating or editing any file under kb/chunks/, or writing a prompt that generates chunks. Not for CLAUDE.md files (updating-internal-docs) or READMEs and guides (updating-external-docs).
---

# Writing knowledge-base chunks

A chunk is retrieved alone, out of order, by vector similarity search, with no neighbours. Every rule follows from that. Test: will this text ever be retrieved as an isolated fragment? If yes, this skill applies.

## Chunk file

Path `kb/chunks/<chunk_id>-<slug>.md` (flat folder; the filename starts with the chunk id, for example `BC-003-refund-policy.md`). Frontmatter, as enforced by `scripts/kb/check_chunks.py` and described in `kb/CLAUDE.md`:

```yaml
---
chunk_id: BC-003
title: Refund eligibility and amounts
topics: [refunds, billing]
links: [BC-001, BC-002, BC-004]
sources: ["docs/briefs/refunds.md"]
example: true            # optional; demo content to delete on adoption
---
```

| Field | Rule |
|-------|------|
| `chunk_id` | `BC-NNN` (letters, dash, 3+ digits), unique, stable, never reused; the filename starts with it |
| `title` | Names the concept; reads as the subject of an answer |
| `topics` | At least one topic; 1-3 is typical |
| `links` | `chunk_id`s of related chunks (the graph); must resolve, no self-link; other topics' mechanisms are linked, not re-explained |
| `sources` | Required, never empty: where the facts come from (brief, spec, code path, record id). Invented demo content uses `"example: invented"` |
| `example` | Optional `true` for demo content |

There is no `status`, `tags` or `source_refs` field.

## Style contract

| Do | Do not |
|----|--------|
| First sentence names the concept and domain and already looks like an answer | Open with "This chunk covers" or "In this section" |
| One topic per chunk; two jobs = two chunks | Mix mechanisms |
| Self-contained: name the subject, never "it", "the above", "as before" across chunks | Depend on a neighbour for meaning |
| State each fact once, precisely | Restate it in other words |
| Same term for the same concept everywhere | Vary vocabulary for style (synonym drift pushes related chunks apart) |
| Plain prose or a short flat list; active voice; one idea per sentence | Deep nesting, wide tables, heavy Markdown, HTML, images |
| 40-350 words (lint limit), aim for 80 to 300 | Under 40 or over 350 (lint fails); padding to reach a target |
| Ground every claim in the cited source; "not shown in the source" is not "not implemented" | Add general-knowledge claims or invent behaviour |
| Cite the source in `sources` | Copy conversion noise (anchors, page numbers, TOC fragments) |

## Zero-slop checklist

- No hedging padding ("it is important to note", "generally", "typically" without a source)
- No meta-commentary and no summary sentence repeating the body
- No restated title as the first sentence
- No marketing adjectives
- No unresolved placeholders; if the source is silent, record a BQ (`recording-decisions`) and omit the claim
- Numbers, limits and names exactly as in the source

## Workflow

1. Read the source and existing chunks on the topic (`mcp__business-kb__search`); extend or link rather than duplicate.
2. Draft the chunk.
3. Run `python3 scripts/kb/check_chunks.py --write-toc` (frontmatter, ids, links, length) and re-ingest if you use the pgvector backend.
4. Hand to `documentation-reviewer`, who applies `reviewing-kb-chunks`. The author never approves its own chunk.
