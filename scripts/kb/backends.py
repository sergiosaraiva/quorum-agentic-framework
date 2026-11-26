"""Two interchangeable stores behind one interface: LocalStore (Markdown files, BM25) and PgStore (pgvector).

Methods (both stores):
  chunk_search, chunk_get, chunk_graph, chunk_stats,
  record_search, record_get, record_open, record_related
Results are plain JSON-serialisable dicts.
"""
from __future__ import annotations

import os
from pathlib import Path

import lib


class LocalStore:
    """Zero-dependency mode: reads kb/chunks and questions/records directly."""

    name = "local"

    def __init__(self, kb_dir: Path = lib.KB_DIR, qa_dir: Path = lib.QA_DIR):
        self.chunks = {c.chunk_id: c for c in lib.load_chunks(kb_dir)}
        self.records = {r.id: r for r in lib.load_records(qa_dir)}
        self._adj = lib.build_adjacency(list(self.chunks.values()))
        self._cidx = lib.BM25([(c.chunk_id, c.search_text()) for c in self.chunks.values()])
        self._ridx = lib.BM25([(r.id, r.search_text()) for r in self.records.values()])

    # -- business KB
    def chunk_search(self, query: str, k: int = 5, topic: str | None = None) -> list[dict]:
        out = []
        for cid, score in self._cidx.search(query, k=len(self.chunks) or 1):
            c = self.chunks[cid]
            if topic and topic not in c.topics:
                continue
            out.append({**c.to_dict(with_body=False), "score": score, "snippet": _snippet(c.body)})
            if len(out) >= k:
                break
        return out

    def chunk_get(self, chunk_id: str) -> dict:
        return self.chunks[chunk_id].to_dict()

    def chunk_graph(self, chunk_id: str, depth: int = 1) -> dict:
        depth = lib.clamp_int(depth, 0, lib.MAX_DEPTH, 1)
        nodes = lib.bfs(self._adj, chunk_id, depth)
        for n in nodes:
            n["title"] = self.chunks[n["chunk_id"]].title
        return {"start": chunk_id, "depth": depth, "nodes": nodes}

    def chunk_stats(self) -> dict:
        topics: dict[str, int] = {}
        for c in self.chunks.values():
            for t in c.topics:
                topics[t] = topics.get(t, 0) + 1
        words = [c.word_count for c in self.chunks.values()]
        return {"backend": self.name, "chunks": len(self.chunks), "words": sum(words),
                "edges": sum(len(v) for v in self._adj.values()) // 2, "topics": dict(sorted(topics.items()))}

    # -- Q&A KB
    def record_search(self, query: str, k: int = 5, kind: str | None = None, status: str | None = None) -> list[dict]:
        out = []
        for rid, score in self._ridx.search(query, k=len(self.records) or 1):
            r = self.records[rid]
            if (kind and r.kind != kind) or (status and r.status != status):
                continue
            out.append({**r.to_dict(with_body=False), "score": score, "snippet": _snippet(r.body)})
            if len(out) >= k:
                break
        return out

    def record_get(self, record_id: str) -> dict:
        return self.records[record_id].to_dict()

    def record_open(self, kind: str | None = None, decider: str | None = None) -> list[dict]:
        rows = [r for r in self.records.values() if r.status == "open"
                and (not kind or r.kind == kind) and (not decider or r.decider == decider)]
        rows.sort(key=lambda r: (r.priority or "P9", r.id))
        return [r.to_dict(with_body=False) for r in rows]

    def record_related(self, record_id: str) -> dict:
        r = self.records[record_id]
        inverse = [o.id for o in self.records.values() if record_id in o.related]
        rel_ids = sorted(set(r.related) | set(inverse))
        return {"id": record_id,
                "records": [self.records[i].to_dict(with_body=False) for i in rel_ids if i in self.records],
                "chunks": [self.chunks[c].to_dict(with_body=False) for c in r.chunks if c in self.chunks]}


class PgStore:
    """PostgreSQL + pgvector mode. Requires `psycopg` (v3) and DATABASE_URL; load data with ingest.py first."""

    name = "pg"

    def __init__(self, dsn: str | None = None):
        try:
            import psycopg  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError("pg backend needs `pip install 'psycopg[binary]'`") from exc
        self._psycopg = psycopg
        self.dsn = dsn or os.environ.get("DATABASE_URL", "")
        if not self.dsn:
            raise RuntimeError("set DATABASE_URL (see .env.example)")

    def _q(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._psycopg.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else []

    # -- business KB
    def chunk_search(self, query: str, k: int = 5, topic: str | None = None) -> list[dict]:
        vec = lib.vector_literal(lib.embed(query))
        rows = self._q(
            "SELECT chunk_id, title, topics, links, sources, word_count, left(body, 600), "
            "1 - (embedding <=> %s::vector) AS score FROM kb_chunks "
            "WHERE (%s::text IS NULL OR %s = ANY(topics)) ORDER BY embedding <=> %s::vector LIMIT %s",
            (vec, topic, topic, vec, k))
        return [{"chunk_id": r[0], "title": r[1], "topics": r[2], "links": r[3], "sources": r[4],
                 "word_count": r[5], "snippet": _snippet(r[6]), "score": round(float(r[7]), 4)} for r in rows]

    def chunk_get(self, chunk_id: str) -> dict:
        rows = self._q("SELECT chunk_id, title, topics, links, sources, word_count, body FROM kb_chunks "
                       "WHERE chunk_id = %s", (chunk_id,))
        if not rows:
            raise KeyError(chunk_id)
        r = rows[0]
        return {"chunk_id": r[0], "title": r[1], "topics": r[2], "links": r[3], "sources": r[4],
                "word_count": r[5], "body": r[6]}

    def chunk_graph(self, chunk_id: str, depth: int = 1) -> dict:
        adj: dict[str, set[str]] = {}
        titles = {r[0]: r[1] for r in self._q("SELECT chunk_id, title FROM kb_chunks")}
        for cid in titles:
            adj[cid] = set()
        for src, dst in self._q("SELECT src, dst FROM kb_links"):
            if src in adj and dst in adj:
                adj[src].add(dst)
                adj[dst].add(src)
        depth = lib.clamp_int(depth, 0, lib.MAX_DEPTH, 1)
        nodes = lib.bfs(adj, chunk_id, depth)
        for n in nodes:
            n["title"] = titles[n["chunk_id"]]
        return {"start": chunk_id, "depth": depth, "nodes": nodes}

    def chunk_stats(self) -> dict:
        n, words = self._q("SELECT count(*), coalesce(sum(word_count), 0) FROM kb_chunks")[0]
        edges = self._q("SELECT count(*) FROM kb_links")[0][0]
        topics = {t: c for t, c in self._q(
            "SELECT t, count(*) FROM kb_chunks, unnest(topics) t GROUP BY t ORDER BY t")}
        return {"backend": self.name, "chunks": n, "words": int(words), "edges": edges, "topics": topics}

    # -- Q&A KB
    _RCOLS = "id, kind, title, status, decider, priority, asked, related, chunks"

    @staticmethod
    def _rec(r: tuple, body: str | None = None) -> dict:
        d = {"id": r[0], "kind": r[1], "title": r[2], "status": r[3], "decider": r[4], "priority": r[5],
             "asked": r[6], "related": r[7], "chunks": r[8]}
        if body is not None:
            d["body"] = body
        return d

    def record_search(self, query: str, k: int = 5, kind: str | None = None, status: str | None = None) -> list[dict]:
        vec = lib.vector_literal(lib.embed(query))
        rows = self._q(
            f"SELECT {self._RCOLS}, left(body, 600), 1 - (embedding <=> %s::vector) FROM qa_records "
            "WHERE (%s::text IS NULL OR kind = %s) AND (%s::text IS NULL OR status = %s) "
            "ORDER BY embedding <=> %s::vector LIMIT %s", (vec, kind, kind, status, status, vec, k))
        return [{**self._rec(r), "snippet": _snippet(r[9]), "score": round(float(r[10]), 4)} for r in rows]

    def record_get(self, record_id: str) -> dict:
        rows = self._q(f"SELECT {self._RCOLS}, body FROM qa_records WHERE id = %s", (record_id,))
        if not rows:
            raise KeyError(record_id)
        return self._rec(rows[0], rows[0][9])

    def record_open(self, kind: str | None = None, decider: str | None = None) -> list[dict]:
        rows = self._q(f"SELECT {self._RCOLS} FROM qa_records WHERE status = 'open' "
                       "AND (%s::text IS NULL OR kind = %s) AND (%s::text IS NULL OR decider = %s) "
                       "ORDER BY COALESCE(NULLIF(priority, ''), 'P9'), id", (kind, kind, decider, decider))
        return [self._rec(r) for r in rows]

    def record_related(self, record_id: str) -> dict:
        rec = self.record_get(record_id)
        rows = self._q(f"SELECT {self._RCOLS} FROM qa_records WHERE id = ANY(%s) OR %s = ANY(related) "
                       "ORDER BY id", (rec["related"], record_id))
        chunks = []
        for cid in rec["chunks"]:
            try:
                chunk = self.chunk_get(cid)
            except KeyError:  # dangling chunk id: skipped, as LocalStore does
                continue
            chunk.pop("body", None)
            chunks.append(chunk)
        return {"id": record_id, "records": [self._rec(r) for r in rows if r[0] != record_id], "chunks": chunks}


def _snippet(body: str, n: int = 240) -> str:
    flat = " ".join(body.split())
    return flat if len(flat) <= n else flat[: n - 3] + "..."


def make_store(backend: str = "local"):
    if backend == "local":
        return LocalStore()
    if backend == "pg":
        return PgStore()
    raise ValueError(f"unknown backend {backend!r} (local|pg)")
