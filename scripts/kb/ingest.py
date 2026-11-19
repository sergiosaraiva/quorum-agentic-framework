#!/usr/bin/env python3
"""Load kb/chunks and questions/records into PostgreSQL + pgvector.

    DATABASE_URL=postgresql://user:pass@localhost:5432/app python3 scripts/kb/ingest.py
    python3 scripts/kb/ingest.py --dry-run          # parse + embed, no database

Embedding provider comes from env (see lib.embed): EMBED_PROVIDER=hash (default, offline demo stub,
NOT semantic) or http (OpenAI-compatible endpoint: EMBED_BASE_URL, EMBED_MODEL, EMBED_API_KEY, EMBED_DIM).
Ingest applies kb/schema.sql and questions/schema.sql itself (vector size taken from EMBED_DIM), re-embeds
every chunk and record on each run (it is not incremental), is idempotent (upsert) and removes rows whose
file was deleted. If the tables already exist with a different vector size it stops with a clear message
instead of failing mid-run: drop the tables and run again after changing EMBED_DIM or the model.
"""
from __future__ import annotations

import argparse
import os
import sys

import lib


def _schema(path, dim: int) -> str:
    return path.read_text(encoding="utf-8").replace("vector(384)", f"vector({dim})")


VECTOR_TABLES = ("kb_chunks", "qa_records")


def dimension_mismatches(cur, dim: int) -> list[str]:
    """Messages for existing tables whose `embedding` vector size differs from `dim` (empty when all match)."""
    problems = []
    for table in VECTOR_TABLES:
        cur.execute(
            "SELECT a.atttypmod FROM pg_attribute a WHERE a.attrelid = to_regclass(%s) "
            "AND a.attname = 'embedding' AND NOT a.attisdropped", (table,))
        row = cur.fetchone()
        if row is not None and row[0] != dim:
            problems.append(f"{table}.embedding is vector({row[0]}) but EMBED_DIM={dim}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="parse and embed only; do not touch the database")
    ap.add_argument("--no-schema", action="store_true", help="skip applying schema.sql files")
    args = ap.parse_args(argv)

    dim = lib.embed_dim()
    chunks, records = lib.load_chunks(), lib.load_records()
    chunk_rows = [(c, lib.vector_literal(lib.embed(c.search_text()))) for c in chunks]
    rec_rows = [(r, lib.vector_literal(lib.embed(r.search_text()))) for r in records]
    provider = os.environ.get("EMBED_PROVIDER", "hash")
    print(f"provider={provider} dim={dim} chunks={len(chunks)} records={len(records)}")
    if provider == "hash":
        print("note: hash embeddings are a deterministic offline stub, not semantic; see scripts/kb/README.md")
    if args.dry_run:
        return 0

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("error: set DATABASE_URL (see .env.example)", file=sys.stderr)
        return 2
    try:
        import psycopg  # type: ignore
    except ImportError:
        print("error: pip install 'psycopg[binary]'", file=sys.stderr)
        return 2

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        problems = dimension_mismatches(cur, dim)
        if problems:
            print("error: " + "; ".join(problems) + ". The vector column size is fixed when the table is created.\n"
                  "Fix EMBED_DIM to match the existing tables, or drop them and re-run:\n"
                  "  DROP TABLE kb_links, kb_chunks, qa_records;", file=sys.stderr)
            return 2
        if not args.no_schema:
            cur.execute(_schema(lib.KB_DIR / "schema.sql", dim))
            cur.execute(_schema(lib.QA_DIR / "schema.sql", dim))
        for c, vec in chunk_rows:
            cur.execute(
                "INSERT INTO kb_chunks (chunk_id, title, topics, links, sources, body, word_count, embedding) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::vector) ON CONFLICT (chunk_id) DO UPDATE SET "
                "title=EXCLUDED.title, topics=EXCLUDED.topics, links=EXCLUDED.links, sources=EXCLUDED.sources, "
                "body=EXCLUDED.body, word_count=EXCLUDED.word_count, embedding=EXCLUDED.embedding, updated_at=now()",
                (c.chunk_id, c.title, c.topics, c.links, c.sources, c.body, c.word_count, vec))
        cur.execute("DELETE FROM kb_chunks WHERE NOT (chunk_id = ANY(%s))", ([c.chunk_id for c in chunks],))
        cur.execute("DELETE FROM kb_links")
        ids = {c.chunk_id for c in chunks}
        for c in chunks:
            for dst in c.links:
                if dst in ids:  # dangling links are reported by check_chunks.py
                    cur.execute("INSERT INTO kb_links (src, dst) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                                (c.chunk_id, dst))
        for r, vec in rec_rows:
            cur.execute(
                "INSERT INTO qa_records (id, kind, title, status, decider, priority, asked, related, chunks, body, embedding) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector) ON CONFLICT (id) DO UPDATE SET "
                "kind=EXCLUDED.kind, title=EXCLUDED.title, status=EXCLUDED.status, decider=EXCLUDED.decider, "
                "priority=EXCLUDED.priority, asked=EXCLUDED.asked, related=EXCLUDED.related, chunks=EXCLUDED.chunks, "
                "body=EXCLUDED.body, embedding=EXCLUDED.embedding, updated_at=now()",
                (r.id, r.kind, r.title, r.status, r.decider, r.priority, r.asked, r.related, r.chunks, r.body, vec))
        cur.execute("DELETE FROM qa_records WHERE NOT (id = ANY(%s))", ([r.id for r in records],))
    print("ingest complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
