"""Shared helpers: frontmatter parsing, chunk/record loading, tokenizing, BM25, link graph, embeddings.

Pure standard library. Python 3.11+.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KB_DIR = REPO_ROOT / "kb"
QA_DIR = REPO_ROOT / "questions"

RECORD_KINDS = ("BQ", "TQ", "OD")
RECORD_STATUSES = ("open", "answered", "decided", "closed")

# ---------------------------------------------------------------- frontmatter


def _scalar(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    return value


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse a minimal YAML subset: `key: value`, `key: [a, b]`, block lists with `- item`."""
    m = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(.*)\Z", text, re.S)
    if not m:
        raise ValueError("missing frontmatter block (--- ... ---)")
    meta: dict = {}
    key = None
    for raw in m.group(1).splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("- ") and key is not None and isinstance(meta.get(key), list):
            meta[key].append(_scalar(line.lstrip()[2:]))
            continue
        k, sep, v = line.partition(":")
        if not sep:
            raise ValueError(f"bad frontmatter line: {raw!r}")
        key, v = k.strip(), v.strip()
        if v == "":
            meta[key] = []  # block list follows (or empty)
        elif v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            meta[key] = [_scalar(p) for p in inner.split(",")] if inner else []
        else:
            meta[key] = _scalar(v)
    return meta, m.group(2).strip()


def _as_list(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v) != ""]
    return [str(value)]


def _as_str(value) -> str:
    return "" if value is None or isinstance(value, list) else str(value)


# ---------------------------------------------------------------- data classes


@dataclass
class Chunk:
    chunk_id: str
    title: str
    topics: list[str]
    links: list[str]
    sources: list[str]
    body: str
    path: str = ""
    example: bool = False

    @property
    def word_count(self) -> int:
        return len(self.body.split())

    def search_text(self) -> str:
        return f"{self.title} {' '.join(self.topics)} {self.body}"

    def to_dict(self, with_body: bool = True) -> dict:
        d = {"chunk_id": self.chunk_id, "title": self.title, "topics": self.topics,
             "links": self.links, "sources": self.sources, "word_count": self.word_count}
        if with_body:
            d["body"] = self.body
        return d


@dataclass
class Record:
    id: str
    kind: str
    title: str
    status: str
    decider: str
    priority: str
    asked: str
    related: list[str]
    chunks: list[str]
    body: str
    path: str = ""
    example: bool = False
    extra: dict = field(default_factory=dict)

    def search_text(self) -> str:
        return f"{self.id} {self.title} {self.kind} {self.status} {self.body}"

    def to_dict(self, with_body: bool = True) -> dict:
        d = {"id": self.id, "kind": self.kind, "title": self.title, "status": self.status,
             "decider": self.decider, "priority": self.priority, "asked": self.asked,
             "related": self.related, "chunks": self.chunks}
        if with_body:
            d["body"] = self.body
        return d


def chunk_from_file(path: Path) -> Chunk:
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return Chunk(chunk_id=_as_str(meta.get("chunk_id")), title=_as_str(meta.get("title")),
                 topics=_as_list(meta.get("topics")), links=_as_list(meta.get("links")),
                 sources=_as_list(meta.get("sources")), body=body, path=str(path),
                 example=meta.get("example") is True)


def record_from_file(path: Path) -> Record:
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    known = {"id", "kind", "title", "status", "decider", "priority", "asked", "related", "chunks", "example"}
    return Record(id=_as_str(meta.get("id")), kind=_as_str(meta.get("kind")), title=_as_str(meta.get("title")),
                  status=_as_str(meta.get("status")), decider=_as_str(meta.get("decider")),
                  priority=_as_str(meta.get("priority")), asked=_as_str(meta.get("asked")),
                  related=_as_list(meta.get("related")), chunks=_as_list(meta.get("chunks")),
                  body=body, path=str(path), example=meta.get("example") is True,
                  extra={k: v for k, v in meta.items() if k not in known})


def load_chunks(kb_dir: Path = KB_DIR) -> list[Chunk]:
    return [chunk_from_file(p) for p in sorted((kb_dir / "chunks").glob("*.md"))]


def load_records(qa_dir: Path = QA_DIR) -> list[Record]:
    return [record_from_file(p) for p in sorted((qa_dir / "records").glob("*.md"))]


# ---------------------------------------------------------------- tokenizing

STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was were will with "
    "not no but if then so than can may must should".split())


def _stem(tok: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if tok.endswith(suffix) and len(tok) - len(suffix) >= 3:
            return tok[: -len(suffix)]
    return tok


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


# ---------------------------------------------------------------- BM25 (pure Python)


class BM25:
    """Okapi BM25 over a list of (doc_id, text)."""

    def __init__(self, docs: list[tuple[str, str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.ids = [d for d, _ in docs]
        self.tfs: list[dict[str, int]] = []
        self.df: dict[str, int] = {}
        for _, text in docs:
            tf: dict[str, int] = {}
            for tok in tokenize(text):
                tf[tok] = tf.get(tok, 0) + 1
            self.tfs.append(tf)
            for tok in tf:
                self.df[tok] = self.df.get(tok, 0) + 1
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 0.0

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        n = len(self.ids)
        q = tokenize(query)
        scored = []
        for i, tf in enumerate(self.tfs):
            score = 0.0
            for tok in q:
                f = tf.get(tok, 0)
                if not f:
                    continue
                idf = math.log(1 + (n - self.df[tok] + 0.5) / (self.df[tok] + 0.5))
                denom = f + self.k1 * (1 - self.b + self.b * self.lens[i] / (self.avg or 1))
                score += idf * f * (self.k1 + 1) / denom
            if score > 0:
                scored.append((self.ids[i], round(score, 4)))
        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored[:k]


# ---------------------------------------------------------------- link graph


def build_adjacency(chunks: list[Chunk]) -> dict[str, set[str]]:
    """Undirected adjacency from chunk `links` (only edges whose target exists)."""
    ids = {c.chunk_id for c in chunks}
    adj: dict[str, set[str]] = {i: set() for i in ids}
    for c in chunks:
        for t in c.links:
            if t in ids and t != c.chunk_id:
                adj[c.chunk_id].add(t)
                adj[t].add(c.chunk_id)
    return adj


MAX_DEPTH = 10  # graph traversal hop limit; larger requests are clamped
MAX_K = 50      # search result limit; larger requests are clamped


def clamp_int(value, lo: int, hi: int, default: int) -> int:
    """Coerce a tool or CLI argument to an int within [lo, hi]; None gives `default`. Raises ValueError on junk."""
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"expected an integer, got {value!r}")
    return max(lo, min(hi, int(value)))


def bfs(adj: dict[str, set[str]], start: str, depth: int = 1) -> list[dict]:
    """Breadth-first neighbours of `start` up to `depth` hops (clamped to MAX_DEPTH), with the hop distance."""
    if start not in adj:
        raise KeyError(start)
    seen = {start: 0}
    frontier = [start]
    for d in range(1, clamp_int(depth, 0, MAX_DEPTH, 1) + 1):
        if not frontier:
            break
        nxt = []
        for node in frontier:
            for nb in sorted(adj[node]):
                if nb not in seen:
                    seen[nb] = d
                    nxt.append(nb)
        frontier = nxt
    return [{"chunk_id": n, "depth": d} for n, d in sorted(seen.items(), key=lambda x: (x[1], x[0])) if n != start]


# ---------------------------------------------------------------- embeddings

DEFAULT_DIM = 384


def embed_dim() -> int:
    return int(os.environ.get("EMBED_DIM", DEFAULT_DIM))


def hash_embedding(text: str, dim: int = DEFAULT_DIM) -> list[float]:
    """DEMO STUB, not semantic. Deterministic signed hashing of tokens into `dim` buckets, L2-normalised.

    Gives lexical-overlap similarity only; lets the pgvector pipeline run offline with no model or key.
    """
    vec = [0.0] * dim
    for tok in tokenize(text):
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        vec[int.from_bytes(h[:4], "big") % dim] += 1.0 if h[4] & 1 else -1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _http_embedding(text: str, dim: int) -> list[float]:
    """OpenAI-compatible `POST {EMBED_BASE_URL}/embeddings` (verify the request shape for your provider)."""
    base, model = os.environ.get("EMBED_BASE_URL", ""), os.environ.get("EMBED_MODEL", "")
    if not base or not model:
        raise RuntimeError("EMBED_PROVIDER=http needs EMBED_BASE_URL and EMBED_MODEL (EMBED_API_KEY is optional); "
                           "unset EMBED_PROVIDER to use the keyless hash stub")
    base = base.rstrip("/")
    payload = json.dumps({"model": model, "input": text}).encode()
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("EMBED_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{base}/embeddings", data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - URL comes from operator env
        vec = json.load(resp)["data"][0]["embedding"]
    if len(vec) != dim:
        raise ValueError(f"embedding has {len(vec)} dims but EMBED_DIM={dim}; fix EMBED_DIM and re-ingest")
    return vec


def embed(text: str) -> list[float]:
    """Pluggable provider chosen by env: EMBED_PROVIDER=hash (default) | http.

    To add another provider, add a branch here (output length must equal EMBED_DIM).
    """
    provider = os.environ.get("EMBED_PROVIDER", "hash").lower()
    dim = embed_dim()
    if provider == "hash":
        return hash_embedding(text, dim)
    if provider == "http":
        return _http_embedding(text, dim)
    raise ValueError(f"unknown EMBED_PROVIDER={provider!r} (use hash or http)")


def vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
