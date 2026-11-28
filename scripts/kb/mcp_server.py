#!/usr/bin/env python3
"""Minimal stdio MCP server (JSON-RPC 2.0, newline-delimited). No third-party SDK.

    python3 scripts/kb/mcp_server.py --kb business   # tools: search, chunk, graph_traverse, stats
    python3 scripts/kb/mcp_server.py --kb qa         # tools: search, get, open, related

Backend: --backend local (default, Markdown files) or pg (needs DATABASE_URL); env KB_BACKEND also works.
Implements: initialize, notifications/initialized, ping, tools/list, tools/call. Read-only.
Logs go to stderr only; stdout carries protocol messages exclusively.
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
import io
import json
import os

import backends
import lib

PROTOCOL_VERSION = "2024-11-05"


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or []}


class InvalidParams(ValueError):
    """Maps to JSON-RPC -32602."""


def _k(a: dict) -> int:
    return lib.clamp_int(a.get("k"), 1, lib.MAX_K, 5)


def _depth(a: dict) -> int:
    return lib.clamp_int(a.get("depth"), 0, lib.MAX_DEPTH, 1)


_S = {"type": "string"}
_I = {"type": "integer"}

BUSINESS_TOOLS = {
    "search": ("Search business KB chunks by free text; returns ids, titles, scores, snippets.",
               _obj({"query": _S, "k": _I, "topic": _S}, ["query"]),
               lambda s, a: s.chunk_search(a["query"], _k(a), a.get("topic"))),
    "chunk": ("Return one chunk (frontmatter and full body) by chunk_id.",
              _obj({"chunk_id": _S}, ["chunk_id"]),
              lambda s, a: s.chunk_get(a["chunk_id"])),
    "graph_traverse": ("List chunks linked to a chunk within `depth` hops (default 1).",
                       _obj({"chunk_id": _S, "depth": _I}, ["chunk_id"]),
                       lambda s, a: s.chunk_graph(a["chunk_id"], _depth(a))),
    "stats": ("Counts of chunks, words, link edges and topics.", _obj({}),
              lambda s, a: s.chunk_stats()),
}

QA_TOOLS = {
    "search": ("Search questions and decisions (BQ business, TQ technical, OD decision) by free text.",
               _obj({"query": _S, "k": _I, "kind": _S, "status": _S}, ["query"]),
               lambda s, a: s.record_search(a["query"], _k(a), a.get("kind"), a.get("status"))),
    "get": ("Return one record (question, answer or decision, history) by id.",
            _obj({"id": _S}, ["id"]), lambda s, a: s.record_get(a["id"])),
    "open": ("List records still open, optionally by kind (BQ|TQ|OD) or decider.",
             _obj({"kind": _S, "decider": _S}), lambda s, a: s.record_open(a.get("kind"), a.get("decider"))),
    "related": ("Records and business KB chunks related to a record.",
                _obj({"id": _S}, ["id"]), lambda s, a: s.record_related(a["id"])),
}


_PY_TYPES = {"string": str, "integer": int}


def _check_types(schema: dict, args: dict) -> None:
    """Reject arguments whose JSON type differs from the tool schema (-32602), instead of failing inside the tool."""
    for key, value in args.items():
        spec = schema["properties"].get(key)
        if spec is None or (value is None and key not in schema["required"]):
            continue  # unknown keys are ignored; null for an optional argument means "not given"
        expected = _PY_TYPES[spec["type"]]
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            raise InvalidParams(f"argument {key!r} must be a {spec['type']}")


class Server:
    def __init__(self, kb: str, store):
        self.kb = kb
        self.store = store
        self.tools = BUSINESS_TOOLS if kb == "business" else QA_TOOLS

    def handle(self, msg: dict) -> dict | None:
        """Return a response dict, or None for notifications."""
        if not isinstance(msg, dict):  # arrays (batches), numbers, strings, null
            return {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32600, "message": "invalid request: expected a JSON object (batches are not supported)"}}
        method, mid = msg.get("method"), msg.get("id")
        if not isinstance(method, str):  # also covers a missing method; the reply carries the id when there is one
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32600, "message": "invalid request: `method` must be a string"}}
        if "id" not in msg:  # notification; an explicit `"id": null` is still a request and gets a reply
            return None
        try:
            if method == "initialize":
                result = {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}},
                          "serverInfo": {"name": f"{self.kb}-kb", "version": "0.1.0"}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": [{"name": n, "description": d, "inputSchema": schema}
                                    for n, (d, schema, _) in self.tools.items()]}
            elif method == "tools/call":
                result = self._call(msg.get("params") or {})
            else:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
        except InvalidParams as exc:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": str(exc)}}
        except Exception as exc:  # protocol-level failure
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": f"{type(exc).__name__}: {exc}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def _call(self, params: dict) -> dict:
        if not isinstance(params, dict):
            raise InvalidParams("params must be an object")
        name, args = params.get("name"), params.get("arguments") or {}
        if not isinstance(name, str) or name not in self.tools:
            raise InvalidParams(f"unknown tool: {name!r}")
        if not isinstance(args, dict):
            raise InvalidParams("arguments must be an object")
        missing = [r for r in self.tools[name][1]["required"] if r not in args]
        if missing:
            raise InvalidParams(f"missing required argument(s): {', '.join(missing)}")
        _check_types(self.tools[name][1], args)
        try:
            data = self.tools[name][2](self.store, args)
            return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}
        except KeyError as exc:
            return {"isError": True, "content": [{"type": "text", "text": f"not found: {exc.args[0]}"}]}
        except Exception as exc:  # tool-level failure, reported to the model
            return {"isError": True, "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}]}

    def serve(self, stdin=None, stdout=None) -> None:
        """Read newline-delimited JSON-RPC from `stdin`, write replies to `stdout`.

        Defaults to the binary streams of sys.stdin and sys.stdout: lines are decoded as UTF-8 (undecodable bytes
        replaced) inside the try, and replies are written as UTF-8 bytes, so neither the locale nor a stray byte
        can kill the server or garble its output. Text streams (tests) are accepted too."""
        stdin = sys.stdin.buffer if stdin is None else stdin
        stdout = sys.stdout.buffer if stdout is None else stdout
        for raw in stdin:
            try:
                line = (raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw).strip()
                if not line:
                    continue
                resp = self.handle(json.loads(line))
            except json.JSONDecodeError:
                resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
            except Exception as exc:  # never let one bad message kill the server
                resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": f"{type(exc).__name__}: {exc}"}}
            if resp is not None:
                text = json.dumps(resp) + "\n"
                stdout.write(text.encode("utf-8") if isinstance(stdout, (io.RawIOBase, io.BufferedIOBase)) else text)
                stdout.flush()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kb", choices=("business", "qa"), required=True)
    ap.add_argument("--backend", choices=("local", "pg"), default=os.environ.get("KB_BACKEND", "local"))
    a = ap.parse_args(argv)
    print(f"{a.kb}-kb MCP server starting (backend={a.backend})", file=sys.stderr)
    try:
        store = backends.make_store(a.backend)
    except (ValueError, RuntimeError) as exc:  # unknown backend (env KB_BACKEND is not checked by argparse), no psycopg
        print(f"error: {exc}", file=sys.stderr)
        return 2
    Server(a.kb, store).serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
