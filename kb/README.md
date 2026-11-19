# Business knowledge base

The business KB is the source of truth about what `{{PRODUCT_NAME}}` must do: rules, states, calculations, vocabulary. Agents read it before designing or coding behaviour and cite chunk ids in their output. It is read through the MCP server `business-kb` (`search`, `chunk`, `graph_traverse`, `stats`) or the CLI `scripts/kb/search.py`.

The five chunks shipped here (`BC-001` to `BC-005`) are examples about an invented "Acme Orders" domain (orders, invoices, refunds). Delete them and write your own; they exist so the whole pipeline can be demonstrated on day one.

## Included sample content

| Set | Ids | What it is |
|-----|-----|------------|
| Acme Orders domain examples | `BC-001` to `BC-005` | Invented orders, invoices and refunds rules (`example: true`); delete once you have real chunks |
| Quorum framework KB | `QF-001` to `QF-034` | Plain-Markdown chunks about Quorum itself: pipeline, agents, knowledge bases, validation, AI CI, slices, models and costs. Each cites real repository paths in `sources`. Keep them as a self-documenting reference or delete them |

Try it: `python3 scripts/kb/search.py "how many review rounds"`.

## Layout

| Path | Purpose |
|------|---------|
| `kb/chunks/BC-NNN-slug.md` | one chunk per file: frontmatter plus a short body |
| `kb/TOC.md` | generated table of contents by topic (`python3 scripts/kb/check_chunks.py --write-toc`) |
| `kb/schema.sql` | PostgreSQL + pgvector tables used by `scripts/kb/ingest.py` |
| `kb/CLAUDE.md` | authoring rules for agents and humans |

## Chunk format

```markdown
---
chunk_id: BC-006
title: Short noun phrase naming the one topic
topics: [orders, shipping]
links: [BC-001, BC-004]
sources: ["spec: orders-v2.pdf section 3", "interview: 2026-01-05"]
---
Self-contained body, 40 to 350 words (aim for 80 to 300).
```

`links` form the graph that `graph_traverse` walks (treated as undirected). `sources` say where the knowledge came from; never leave it empty. Example chunks also carry `example: true`.

## Workflow

1. Write or edit a chunk (the `documentation-curator` agent does this; the `documentation-reviewer` checks grounding).
2. Lint: `python3 scripts/kb/check_chunks.py --write-toc`.
3. Local search works immediately from the files. For vector search, start PostgreSQL (`docker compose up -d postgres`) and run `python3 scripts/kb/ingest.py` (it applies the schema itself and re-embeds everything on each run).

See `scripts/kb/README.md` for the two search backends and for plugging in a real embedding model.
