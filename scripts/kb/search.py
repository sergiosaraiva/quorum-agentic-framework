#!/usr/bin/env python3
"""Search the business KB or the Q&A KB from the command line.

    python3 scripts/kb/search.py "refund after delivery"                 # business KB, local BM25
    python3 scripts/kb/search.py --kb qa "invoice numbers" --backend pg  # Q&A KB, pgvector
    python3 scripts/kb/search.py --graph BC-001 --depth 2                # link-graph traversal
    python3 scripts/kb/search.py --get BC-002 | --kb qa --get BQ-001
    python3 scripts/kb/search.py --stats          # business KB only
    python3 scripts/kb/search.py --kb qa --open
"""
import sys  # builtin: cannot be shadowed. Nothing else is imported before the next statement (not even `from __future__`, which imports a module)
if __name__ == "__main__" and not sys.flags.isolated and not getattr(sys.flags, "safe_path", False) and sys.path and sys.path[0]:
    _here = sys.path.pop(0)  # the script directory: a planted scripts/kb/<stdlib-name>.* must not shadow the standard library (OD-032); not even last on the path (nt, psycopg ... are imported when absent)
    import importlib.util  # the sibling modules are loaded by path and registered under their names, so `import lib` below finds them
    for _name in ("lib", "backends"):
        _spec = importlib.util.spec_from_file_location(_name, _here + "/" + _name + ".py")
        sys.modules[_name] = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(sys.modules[_name])

import argparse
import json
from pathlib import Path

import backends
import lib


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", help="free-text query")
    ap.add_argument("--kb", choices=("business", "qa"), default="business")
    ap.add_argument("--backend", choices=("local", "pg"), default="local")
    ap.add_argument("-k", type=int, default=5, help="max results")
    ap.add_argument("--get", metavar="ID", help="print one chunk or record")
    ap.add_argument("--graph", metavar="CHUNK_ID", help="traverse the chunk link graph (business only)")
    ap.add_argument("--depth", type=int, default=1, help="hops, clamped to 0..10")
    ap.add_argument("--related", metavar="ID", help="records and chunks related to a record (qa only)")
    ap.add_argument("--open", action="store_true", help="list open records (qa only)")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--topic", help="business: filter by topic")
    ap.add_argument("--kind", help="qa: BQ|TQ|OD")
    ap.add_argument("--status", help="qa: open|answered|decided|closed")
    ap.add_argument("--json", action="store_true", help="raw JSON output")
    ap.add_argument("--root", type=Path, help="local backend: directory holding kb/chunks and questions/records "
                                              "(default: this repository)")
    a = ap.parse_args(argv)
    a.depth = lib.clamp_int(a.depth, 0, lib.MAX_DEPTH, 1)
    a.k = lib.clamp_int(a.k, 1, lib.MAX_K, 5)

    if a.stats and a.kb != "business":
        ap.error("--stats reports the business KB only; drop --kb qa")
    if a.root is not None:
        if a.backend != "local":
            ap.error("--root only applies to the local backend; the pg backend reads the database. Drop --root or use --backend local")
        missing = [rel for rel in ("kb/chunks", "questions/records") if not (a.root / rel).is_dir()]
        if missing:
            ap.error(f"--root {a.root} has no {' and no '.join(missing)}; point it at a directory holding kb/chunks and questions/records")
    try:
        store = backends.make_store(a.backend, a.root)
    except (ValueError, RuntimeError) as exc:  # unknown backend, or pg without psycopg or DATABASE_URL
        print(f"error: {exc}", file=sys.stderr)
        return 2
    biz = a.kb == "business"
    try:
        if a.stats:
            out = store.chunk_stats()
        elif a.get:
            out = store.chunk_get(a.get) if biz else store.record_get(a.get)
        elif a.graph:
            out = store.chunk_graph(a.graph, a.depth)
        elif a.related:
            out = store.record_related(a.related)
        elif a.open:
            out = store.record_open(a.kind)
        elif a.query:
            out = (store.chunk_search(a.query, a.k, a.topic) if biz
                   else store.record_search(a.query, a.k, a.kind, a.status))
        else:
            ap.error("give a query or one of --get/--graph/--related/--open/--stats")
    except KeyError as exc:
        print(f"not found: {exc.args[0]}", file=sys.stderr)
        return 1

    if a.json or not isinstance(out, list):
        print(json.dumps(out, indent=2))
    else:
        for row in out:
            rid = row.get("chunk_id") or row.get("id")
            print(f"{row.get('score', ''):>7}  {rid:<8} {row['title']}")
            if row.get("snippet"):
                print(f"         {row['snippet']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
