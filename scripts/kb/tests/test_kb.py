"""Unit tests. Run from the repo root: python3 -m unittest discover -s scripts/kb/tests"""
import json
import sys
import tempfile
import unittest
from datetime import date
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

    def test_http_provider_without_config_gives_a_clear_error(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"EMBED_PROVIDER": "http"}, clear=False):
            for k in ("EMBED_BASE_URL", "EMBED_MODEL"):
                os.environ.pop(k, None)
            with self.assertRaisesRegex(RuntimeError, "EMBED_BASE_URL"):
                lib.embed("x")


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


class RelatedSymmetryTests(unittest.TestCase):
    def lint(self, a_related, b_related):
        with tempfile.TemporaryDirectory() as tmp:
            kb, qa = Path(tmp) / "kb", Path(tmp) / "qa"
            (kb / "chunks").mkdir(parents=True)
            (qa / "records").mkdir(parents=True)
            for rid, rel in (("TQ-001", a_related), ("TQ-002", b_related)):
                (qa / "records" / f"{rid}.md").write_text(
                    f"---\nid: {rid}\nkind: TQ\ntitle: {rid}\nstatus: open\ndecider: tech-lead\n"
                    f"asked: 2026-01-01\nrelated: {rel}\n---\nbody\n")
            warnings: list[str] = []
            errors = check_chunks.lint(kb, qa, warnings=warnings)
            return errors, warnings

    def test_symmetric_links_are_clean(self):
        self.assertEqual(self.lint("[TQ-002]", "[TQ-001]"), ([], []))

    def test_one_way_link_warns_without_failing(self):
        errors, warnings = self.lint("[TQ-002]", "[]")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, ["TQ-001.md: related TQ-002 is one-way (TQ-002 does not list TQ-001)"])


class IdCollisionTests(unittest.TestCase):
    def setUp(self):
        import subprocess
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.qa = self.repo / "questions"
        (self.qa / "records").mkdir(parents=True)
        self.git = lambda *a: subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t",
                                              *a], check=True, capture_output=True)
        self.git("init", "-q", "-b", "main")

    def tearDown(self):
        self._tmp.cleanup()

    def record(self, rid, title):
        (self.qa / "records" / f"{rid}.md").write_text(
            f"---\nid: {rid}\nkind: TQ\ntitle: {title}\nstatus: open\ndecider: tech-lead\nasked: 2026-01-01\n---\nb\n")

    def test_same_id_different_title_on_other_branch_warns(self):
        self.record("TQ-001", "Base")
        self.git("add", "-A"); self.git("commit", "-qm", "base")
        self.git("checkout", "-qb", "other")
        self.record("TQ-002", "Other branch question")
        self.git("add", "-A"); self.git("commit", "-qm", "other")
        self.git("checkout", "-q", "main")
        self.record("TQ-002", "Main branch question")
        out = check_chunks.id_collisions(["other"], self.qa, self.repo)
        self.assertEqual(len(out), 1)
        self.assertIn("TQ-002: title differs on other", out[0])

    def test_same_title_and_unique_ids_are_clean(self):
        self.record("TQ-001", "Base")
        self.git("add", "-A"); self.git("commit", "-qm", "base")
        self.git("checkout", "-qb", "other")
        self.record("TQ-002", "Only there")
        self.git("add", "-A"); self.git("commit", "-qm", "other")
        self.git("checkout", "-q", "main")
        self.record("TQ-003", "Only here")
        self.assertEqual(check_chunks.id_collisions(["other"], self.qa, self.repo), [])

    def test_unknown_ref_is_reported_not_raised(self):
        self.record("TQ-001", "Base")
        self.git("add", "-A"); self.git("commit", "-qm", "base")
        out = check_chunks.id_collisions(["nope"], self.qa, self.repo)
        self.assertEqual(len(out), 1)
        self.assertIn("--against nope", out[0])


class AcceptedRiskTests(unittest.TestCase):
    """OD records with `accepted_risk: true` and `expires`."""
    TODAY = date(2026, 6, 1)

    def lint(self, od_front="accepted_risk: true\nexpires: 2026-12-31", od_body="## Decision\n\nAccepted until the owner answers.\n",
             od_extra="answered: 2026-03-01", related="[TQ-001]", kind="OD", today=None):
        with tempfile.TemporaryDirectory() as tmp:
            kb, qa = Path(tmp) / "kb", Path(tmp) / "qa"
            (kb / "chunks").mkdir(parents=True)
            (qa / "records").mkdir(parents=True)
            (qa / "records" / "TQ-001.md").write_text(
                "---\nid: TQ-001\nkind: TQ\ntitle: Q\nstatus: open\ndecider: tech-lead\nasked: 2026-01-01\n"
                f"related: [{kind}-002]\n---\nbody\n")
            (qa / "records" / f"{kind}-002.md").write_text(
                f"---\nid: {kind}-002\nkind: {kind}\ntitle: D\nstatus: decided\ndecider: tech-lead\nasked: 2026-02-01\n"
                f"{od_extra}\nrelated: {related}\n{od_front}\n---\n{od_body}")
            warnings: list[str] = []
            errors = check_chunks.lint(kb, qa, today=today or self.TODAY, warnings=warnings)
            return errors, warnings

    def test_valid_accepted_risk_is_clean(self):
        self.assertEqual(self.lint(), ([], []))

    def test_loader_keeps_fields_in_extra(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "OD-002.md"
            p.write_text("---\nid: OD-002\nkind: OD\ntitle: D\nstatus: decided\ndecider: x\nasked: 2026-02-01\n"
                         "accepted_risk: true\nexpires: 2026-12-31\n---\n## Decision\nx\n")
            r = lib.record_from_file(p)
            self.assertIs(r.extra["accepted_risk"], True)
            self.assertEqual(r.extra["expires"], "2026-12-31")

    def test_only_on_od(self):
        errors, _ = self.lint(kind="TQ", od_front="accepted_risk: false")
        self.assertIn("TQ-002.md: accepted_risk is allowed only on kind OD", errors)

    def test_must_be_boolean(self):
        errors, _ = self.lint(od_front="accepted_risk: yes\nexpires: 2026-12-31")
        self.assertIn("OD-002.md: accepted_risk must be true or false, got 'yes'", errors)

    def test_requires_expires(self):
        errors, _ = self.lint(od_front="accepted_risk: true")
        self.assertIn("OD-002.md: accepted_risk true requires expires: YYYY-MM-DD", errors)

    def test_expires_without_accepted_risk(self):
        for front in ("expires: 2026-12-31", "accepted_risk: false\nexpires: 2026-12-31"):
            errors, _ = self.lint(od_front=front)
            self.assertIn("OD-002.md: expires requires accepted_risk: true", errors)

    def test_expires_must_be_a_valid_date_after_answered(self):
        errors, _ = self.lint(od_front="accepted_risk: true\nexpires: 2026-13-45")
        self.assertIn("OD-002.md: expires '2026-13-45' is not a valid YYYY-MM-DD date", errors)
        errors, _ = self.lint(od_front="accepted_risk: true\nexpires: 2026-03-01")
        self.assertIn("OD-002.md: expires 2026-03-01 must be after answered 2026-03-01", errors)

    def test_expires_falls_back_to_asked(self):
        errors, _ = self.lint(od_front="accepted_risk: true\nexpires: 2026-01-15", od_extra="")
        self.assertIn("OD-002.md: expires 2026-01-15 must be after asked 2026-02-01", errors)

    def test_needs_related_bq_or_tq(self):
        errors, _ = self.lint(related="[]")
        self.assertIn("OD-002.md: accepted_risk needs a related BQ/TQ record (the question that raised it)", errors)

    def test_related_must_include_a_bq_or_tq_not_just_any_record(self):
        errors, _ = self.lint(related="[OD-003]")  # OD-003 does not resolve either, but the prefix rule must fire
        self.assertIn("OD-002.md: accepted_risk needs a related BQ/TQ record (the question that raised it)", errors)

    def test_needs_non_empty_decision(self):
        for body in ("No section here\n", "## Decision\n\n## History\n\nx\n"):
            errors, _ = self.lint(od_body=body)
            self.assertIn("OD-002.md: accepted_risk needs a non-empty '## Decision' section", errors)

    def test_expired_is_a_warning_not_an_error(self):
        errors, warnings = self.lint(today=date(2027, 1, 1))
        self.assertEqual(errors, [])
        self.assertEqual(warnings, ["OD-002.md: accepted risk expired on 2026-12-31; re-decide or close it"])

    def test_closed_record_past_expiry_does_not_warn(self):
        for status, expect in (("closed", []), ("decided", 1)):
            with tempfile.TemporaryDirectory() as tmp:
                kb, qa = Path(tmp) / "kb", Path(tmp) / "qa"
                (kb / "chunks").mkdir(parents=True)
                (qa / "records").mkdir(parents=True)
                (qa / "records" / "TQ-001.md").write_text(
                    "---\nid: TQ-001\nkind: TQ\ntitle: Q\nstatus: open\ndecider: t\nasked: 2026-01-01\nrelated: [OD-002]\n---\nb\n")
                (qa / "records" / "OD-002.md").write_text(
                    f"---\nid: OD-002\nkind: OD\ntitle: D\nstatus: {status}\ndecider: t\nasked: 2026-02-01\n"
                    "related: [TQ-001]\naccepted_risk: true\nexpires: 2026-12-31\n---\n## Decision\n\nx\n")
                w: list[str] = []
                self.assertEqual(check_chunks.lint(kb, qa, today=date(2027, 1, 1), warnings=w), [])
                self.assertEqual(w if expect == [] else len(w), expect)

    def test_empty_answered_falls_back_to_asked(self):
        errors, _ = self.lint(od_front="accepted_risk: true\nexpires: 2026-01-15", od_extra="answered:")
        self.assertIn("OD-002.md: expires 2026-01-15 must be after asked 2026-02-01", errors)

    def test_quoted_boolean_and_trailing_comment_hints(self):
        errors, _ = self.lint(od_front='accepted_risk: "true"\nexpires: 2026-12-31')
        self.assertTrue(any("got 'true' (unquote the value" in e for e in errors), errors)
        errors, _ = self.lint(od_front="accepted_risk: true\nexpires: 2026-12-31 # note")
        self.assertTrue(any("no trailing comment" in e for e in errors), errors)

    def test_expiry_day_itself_is_not_expired(self):
        self.assertEqual(self.lint(today=date(2026, 12, 31)), ([], []))


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
