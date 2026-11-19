-- Q&A KB tables (PostgreSQL 16+ with pgvector).
-- Applied by scripts/kb/ingest.py. The vector dimension (384) is replaced at ingest time by EMBED_DIM.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS qa_records (
    id          text PRIMARY KEY,                       -- BQ-001, TQ-001, OD-001
    kind        text        NOT NULL CHECK (kind IN ('BQ', 'TQ', 'OD')),
    title       text        NOT NULL,
    status      text        NOT NULL CHECK (status IN ('open', 'answered', 'decided', 'closed')),
    decider     text        NOT NULL DEFAULT '',
    priority    text        NOT NULL DEFAULT 'P2',
    asked       text        NOT NULL DEFAULT '',
    related     text[]      NOT NULL DEFAULT '{}',      -- other record ids
    chunks      text[]      NOT NULL DEFAULT '{}',      -- business KB chunk ids
    body        text        NOT NULL,
    embedding   vector(384) NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS qa_records_status ON qa_records (status, kind);
