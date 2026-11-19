-- Business KB tables (PostgreSQL 16+ with pgvector).
-- Applied by scripts/kb/ingest.py. The vector dimension (384) is replaced at ingest time by EMBED_DIM.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS kb_chunks (
    chunk_id    text PRIMARY KEY,
    title       text        NOT NULL,
    topics      text[]      NOT NULL DEFAULT '{}',
    links       text[]      NOT NULL DEFAULT '{}',
    sources     text[]      NOT NULL DEFAULT '{}',
    body        text        NOT NULL,
    word_count  integer     NOT NULL,
    embedding   vector(384) NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Directed edges from the `links` frontmatter; traversal treats them as undirected.
CREATE TABLE IF NOT EXISTS kb_links (
    src text NOT NULL REFERENCES kb_chunks (chunk_id) ON DELETE CASCADE,
    dst text NOT NULL REFERENCES kb_chunks (chunk_id) ON DELETE CASCADE,
    PRIMARY KEY (src, dst)
);

CREATE INDEX IF NOT EXISTS kb_chunks_topics_gin ON kb_chunks USING gin (topics);
-- Add an ANN index once the KB is large (hundreds of chunks), for example:
--   CREATE INDEX kb_chunks_embedding_hnsw ON kb_chunks USING hnsw (embedding vector_cosine_ops);
