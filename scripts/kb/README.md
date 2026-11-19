# KB tooling

Python 3.11+, standard library only for local mode. Run all commands from the repository root.

| Script | Purpose |
|--------|---------|
| `lib.py` | frontmatter parser, chunk and record loaders, BM25, link graph, embedding providers |
| `backends.py` | `LocalStore` (Markdown files) and `PgStore` (pgvector) behind one interface |
| `search.py` | CLI search, `--get`, `--graph`, `--open`, `--related`, `--stats` |
| `mcp_server.py` | stdio MCP server, `--kb business` or `--kb qa` |
| `ingest.py` | applies `kb/schema.sql` and `questions/schema.sql`, loads chunks and records with embeddings |
| `check_chunks.py` | lint (unique ids, links resolve, word limits, frontmatter); `--write-toc` regenerates `kb/TOC.md` |
| `tests/` | `python3 -m unittest discover -s scripts/kb/tests` |

## What each backend actually does

| Backend | Ranking | Notes |
|---------|---------|-------|
| `local` (default) | BM25 over title, topics and body, plus link-graph traversal | computed in memory from the files on every start; fine for hundreds of chunks; nothing to install |
| `pg` | pgvector cosine distance on the embeddings only | no keyword (BM25) component and no rank fusion; quality is exactly the quality of the embedding model |

With the default `hash` embedding stub, `pg` mode matches shared words only. It is **not semantic** and is for exercising the pipeline offline, not for judging retrieval quality. Link-graph traversal (`--graph`, `graph_traverse`) works the same in both backends.

## Local mode (default, no setup)

```bash
python3 scripts/kb/search.py "refund window"
python3 scripts/kb/search.py --graph BC-001 --depth 2     # depth is clamped to 0..10
python3 scripts/kb/search.py --kb qa --open
```

## PostgreSQL + pgvector mode

```bash
cp .env.example .env                     # set POSTGRES_PASSWORD
set -a; source .env; set +a              # export the variables: docker compose and the scripts read the environment
docker compose up -d postgres            # published on 127.0.0.1 only
pip install "psycopg[binary]"
export DATABASE_URL=postgresql://app_user:${POSTGRES_PASSWORD}@127.0.0.1:5432/app
python3 scripts/kb/ingest.py             # applies the schemas itself; re-run after editing chunks
python3 scripts/kb/search.py --backend pg "refund window"
```

`ingest.py` creates the tables from `kb/schema.sql` and `questions/schema.sql` (the vector size comes from `EMBED_DIM`), so do not apply the SQL files by hand. It re-embeds every chunk and record on each run (it is not incremental), upserts rows and deletes rows whose file is gone. `--dry-run` parses and embeds without touching the database.

Use the same backend in MCP with `--backend pg` or `KB_BACKEND=pg`.

## Embeddings: stub by default, swap for a real model

`EMBED_PROVIDER=hash` (default) is a deterministic hashing stub for offline demos (see above: not semantic).

For a real model set `EMBED_PROVIDER=http` with an OpenAI-compatible embeddings endpoint (verify the request and response shape for your provider):

```bash
export EMBED_PROVIDER=http
export EMBED_BASE_URL=https://your-provider.example/v1
export EMBED_MODEL=your-embedding-model
export EMBED_API_KEY=${YOUR_PROVIDER_KEY}   # from your secret store, never committed
export EMBED_DIM=1024                        # must equal the model's output size
python3 scripts/kb/ingest.py
```

The vector column size is fixed when the table is created. If you change the model or `EMBED_DIM` after a first ingest, `ingest.py` stops with a message naming the mismatching table instead of failing half way; drop the tables and run it again: `DROP TABLE kb_links, kb_chunks, qa_records;`. Other providers (a local model, a cloud SDK): add a branch in `lib.embed()` returning a list of `EMBED_DIM` floats.

## MCP registration

`.mcp.json` registers both servers (`business-kb`, `qa-kb`) with `python3`. Tool names seen by agents: `mcp__business-kb__search|chunk|graph_traverse|stats` and `mcp__qa-kb__search|get|open|related`. The servers are read-only. The `qa-kb` `search` tool filters by `kind` and `status` only (plus `query` and `k`).

Protocol behaviour: one JSON object per line; a non-object message (including a batch array) gets `-32600`; an unknown tool or a missing required argument gets `-32602`; an unexpected failure gets `-32603`; `k` is clamped to 1..50 and `depth` to 0..10.
