---
chunk_id: QF-011
title: Local files versus PostgreSQL with pgvector for the knowledge bases
topics: [business-kb, search, infrastructure]
links: [QF-010, QF-012, QF-023]
sources: ["scripts/kb/README.md", "scripts/kb/backends.py", "scripts/kb/ingest.py", "kb/schema.sql"]
---
The Quorum knowledge bases can be searched through two backends that read the same content. The Markdown files are the source of truth and are reviewed in pull requests; the database is a derived index that can be rebuilt.

Local mode is the default and needs no setup. `LocalStore` in `scripts/kb/backends.py` loads the chunk and record files on every start and ranks results with BM25 (a keyword scoring method) over title, topics and body. Link-graph traversal is separate: `graph_traverse` walks chunk `links`. It uses only the Python standard library and suits hundreds of chunks. Example: `python3 scripts/kb/search.py "refund window"`.

PostgreSQL mode uses PostgreSQL 16 or later with the `pgvector` extension. `PgStore.chunk_search` orders results by vector distance only: there is no keyword component and no combined ranking, so search quality equals embedding quality. With the default hash stub embedding it matches shared words only and is not semantic (the embedding stub chunk QF-023 covers this).

Setup: start the database with `docker compose up -d postgres`, install `psycopg[binary]`, set `DATABASE_URL`, then run `scripts/kb/ingest.py`. Ingest applies `kb/schema.sql` and `questions/schema.sql` itself (tables `kb_chunks`, `kb_links` and `qa_records`, with an embedding column of 384 dimensions by default, replaced by `EMBED_DIM`). It re-embeds every chunk and record on each run, so it is not incremental, upserts rows and deletes rows whose file is gone. Search with `--backend pg`, or set `KB_BACKEND=pg` for the MCP server.

Switching modes needs no change to agents, because both expose the same tools. Re-run ingest after editing chunks or records, and after changing the embedding model or its dimension.
