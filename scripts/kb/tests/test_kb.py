"""Unit tests. Run from the repo root: python3 -m unittest discover -s scripts/kb/tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backends  # noqa: E402
import check_chunks  # noqa: E402
import lib  # noqa: E402
import mcp_server  # noqa: E402


class FrontmatterTests(unittest.TestCase):
    def test_parse_inline_and_block_lists(self):
        meta, body = lib.parse_frontmatter("---\nchunk_id: X-001\ntopics: [a, b]\nlinks:\n  - X-002\nexample: true\n---\nHello")
        self.assertEqual(meta["topics"], ["a", "b"])
        self.assertEqual(meta["links"], ["X-002"])
        self.assertIs(meta["example"], True)
        self.assertEqual(body, "Hello")

    def test_missing_frontmatter_raises(self):
        with self.assertRaises(ValueError):
            lib.parse_frontmatter("no frontmatter")


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = backends.LocalStore()

    def test_bm25_finds_refund_chunk(self):
        hits = self.store.chunk_search("refund window after delivery", k=3)
        self.assertEqual(hits[0]["chunk_id"], "BC-003")

    def test_graph_depth(self):
        one = {n["chunk_id"] for n in self.store.chunk_graph("BC-005", 1)["nodes"]}
        two = {n["chunk_id"] for n in self.store.chunk_graph("BC-005", 2)["nodes"]}
        self.assertEqual(one, {"BC-002", "BC-003"})
        self.assertTrue(one < two)

    def test_open_records_only_open(self):
        self.assertTrue(all(r["status"] == "open" for r in self.store.record_open()))

    def test_related_includes_inverse(self):
        ids = {r["id"] for r in self.store.record_related("OD-001")["records"]}
        self.assertIn("TQ-002", ids)
        self.assertIn("BQ-001", ids)  # BQ-001 lists OD-001 in `related`


class EmbeddingTests(unittest.TestCase):
    def test_hash_embedding_deterministic_and_normalised(self):
        a, b = lib.hash_embedding("refund policy", 64), lib.hash_embedding("refund policy", 64)
        self.assertEqual(a, b)
        self.assertAlmostEqual(sum(x * x for x in a), 1.0, places=6)


class LintTests(unittest.TestCase):
    def test_shipped_examples_are_clean(self):
        self.assertEqual(check_chunks.lint(), [])

    def test_detects_dangling_link_and_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb, qa = Path(tmp) / "kb", Path(tmp) / "qa"
            (kb / "chunks").mkdir(parents=True)
            (qa / "records").mkdir(parents=True)
            text = "---\nchunk_id: BC-001\ntitle: T\ntopics: [t]\nlinks: [BC-999]\nsources: [s]\n---\n" + "word " * 50
            (kb / "chunks" / "BC-001-a.md").write_text(text)
            (kb / "chunks" / "BC-001-b.md").write_text(text)
            errors = check_chunks.lint(kb, qa)
            self.assertTrue(any("does not resolve" in e for e in errors))
            self.assertTrue(any("duplicate" in e for e in errors))


class McpTests(unittest.TestCase):
    def test_protocol_roundtrip(self):
        srv = mcp_server.Server("business", backends.LocalStore())
        init = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "business-kb")
        self.assertIsNone(srv.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        names = {t["name"] for t in srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]}
        self.assertEqual(names, {"search", "chunk", "graph_traverse", "stats"})
        call = srv.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                           "params": {"name": "chunk", "arguments": {"chunk_id": "BC-001"}}})
        self.assertEqual(json.loads(call["result"]["content"][0]["text"])["chunk_id"], "BC-001")
        missing = srv.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                              "params": {"name": "chunk", "arguments": {"chunk_id": "NOPE"}}})
        self.assertTrue(missing["result"]["isError"])

    def test_qa_tools(self):
        srv = mcp_server.Server("qa", backends.LocalStore())
        names = {t["name"] for t in srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]}
        self.assertEqual(names, {"search", "get", "open", "related"})


class McpRobustnessTests(unittest.TestCase):
    def setUp(self):
        self.srv = mcp_server.Server("business", backends.LocalStore())

    def call(self, name, arguments, mid=1):
        return self.srv.handle({"jsonrpc": "2.0", "id": mid, "method": "tools/call",
                                "params": {"name": name, "arguments": arguments}})

    def test_non_object_messages_get_invalid_request(self):
        for bad in ([], [{"jsonrpc": "2.0", "id": 1, "method": "ping"}], 5, "x", None):
            resp = self.srv.handle(bad)
            self.assertEqual(resp["error"]["code"], -32600, bad)

    def test_serve_survives_garbage_lines(self):
        import io
        out = io.StringIO()
        lines = '[1,2]\nnot json\n{"jsonrpc":"2.0","id":7,"method":"ping"}\n'
        self.srv.serve(io.StringIO(lines), out)
        replies = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual([r.get("error", {}).get("code") for r in replies], [-32600, -32700, None])
        self.assertEqual(replies[2]["id"], 7)

    def test_unknown_tool_is_invalid_params(self):
        self.assertEqual(self.call("nope", {})["error"]["code"], -32602)

    def test_missing_required_argument_is_invalid_params(self):
        resp = self.call("chunk", {})
        self.assertEqual(resp["error"]["code"], -32602)
        self.assertIn("chunk_id", resp["error"]["message"])

    def test_non_object_params_and_arguments(self):
        bad_params = self.srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": [1]})
        self.assertEqual(bad_params["error"]["code"], -32602)
        self.assertEqual(self.call("chunk", ["BC-001"])["error"]["code"], -32602)

    def test_huge_depth_and_k_are_clamped(self):
        graph = json.loads(self.call("graph_traverse", {"chunk_id": "BC-001", "depth": 10**9})["result"]["content"][0]["text"])
        self.assertEqual(graph["depth"], lib.MAX_DEPTH)
        hits = json.loads(self.call("search", {"query": "order", "k": 10**9})["result"]["content"][0]["text"])
        self.assertLessEqual(len(hits), lib.MAX_K)

    def test_negative_depth_is_clamped_to_zero(self):
        graph = json.loads(self.call("graph_traverse", {"chunk_id": "BC-001", "depth": -3})["result"]["content"][0]["text"])
        self.assertEqual(graph["nodes"], [])

    def test_wrongly_typed_arguments_are_invalid_params(self):
        cases = [("graph_traverse", {"chunk_id": "BC-001", "depth": ["x"]}),
                 ("graph_traverse", {"chunk_id": "BC-001", "depth": "2"}),
                 ("graph_traverse", {"chunk_id": "BC-001", "depth": True}),
                 ("graph_traverse", {"chunk_id": 5}),
                 ("search", {"query": ["a"]}),
                 ("search", {"query": "order", "k": 2.5}),
                 ("chunk", {"chunk_id": None})]
        for name, args in cases:
            resp = self.call(name, args)
            self.assertEqual(resp.get("error", {}).get("code"), -32602, (name, args))

    def test_null_optional_argument_means_not_given(self):
        resp = self.call("search", {"query": "order", "k": None})
        self.assertNotIn("error", resp)

    def test_qa_server_rejects_non_string_filters(self):
        qa = mcp_server.Server("qa", backends.LocalStore())
        resp = qa.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "search", "arguments": {"query": "x", "status": 3}}})
        self.assertEqual(resp["error"]["code"], -32602)


class GraphTests(unittest.TestCase):
    def test_bfs_stops_when_frontier_is_empty(self):
        adj = {"A": {"B"}, "B": {"A"}}
        self.assertEqual(lib.bfs(adj, "A", 10**9), [{"chunk_id": "B", "depth": 1}])

    def test_search_cli_clamps_depth(self):
        import contextlib
        import io
        import search
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(search.main(["--graph", "BC-001", "--depth", "999999"]), 0)
        self.assertEqual(json.loads(buf.getvalue())["depth"], lib.MAX_DEPTH)


class IngestTests(unittest.TestCase):
    class FakeCursor:
        def __init__(self, dims):
            self.dims, self.table = dims, None

        def execute(self, sql, params=()):
            self.table = params[0]

        def fetchone(self):
            dim = self.dims.get(self.table)
            return None if dim is None else (dim,)

    def test_matching_or_absent_tables_pass(self):
        import ingest
        self.assertEqual(ingest.dimension_mismatches(self.FakeCursor({"kb_chunks": 384}), 384), [])

    def test_mismatch_is_reported_per_table(self):
        import ingest
        problems = ingest.dimension_mismatches(self.FakeCursor({"kb_chunks": 384, "qa_records": 1024}), 1024)
        self.assertEqual(len(problems), 1)
        self.assertIn("kb_chunks", problems[0])
        self.assertIn("384", problems[0])


if __name__ == "__main__":
    unittest.main()
