"""Tests for scripts/ai_review_local.py. Run: python3 -m unittest discover -s scripts/tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_review_local as air  # noqa: E402


def make_diff(path: str, lines: list[str], hunks: int = 1) -> str:
    out = [f"diff --git a/{path} b/{path}\n", f"--- a/{path}\n", f"+++ b/{path}\n"]
    for h in range(hunks):
        out.append(f"@@ -1,{len(lines)} +1,{len(lines)} @@\n")
        out += [f"+{line}\n" for line in lines]
    return "".join(out)


class SplitDiffTests(unittest.TestCase):
    def added_lines(self, chunks):
        return [ln for c in chunks for ln in c.splitlines() if ln.startswith("+") and not ln.startswith("+++")]

    def test_small_diff_is_one_chunk(self):
        diff = make_diff("a.cs", ["one", "two"])
        self.assertEqual(air.split_diff(diff, 10_000), [diff])

    def test_oversize_hunk_is_split_by_lines_and_no_code_is_lost(self):
        lines = [f"line number {i:04d}" for i in range(400)]
        diff = make_diff("big.cs", lines)
        chunks = air.split_diff(diff, 1_000)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c.encode()) <= 1_000 for c in chunks))
        self.assertEqual(self.added_lines(chunks), [f"+{ln}" for ln in lines])
        self.assertTrue(all("diff --git a/big.cs" in c for c in chunks))  # header repeated in every piece

    def body_text(self, chunks):
        """All non-header text of the chunks, concatenated with newlines and diff '+' markers removed."""
        skip = ("diff --git", "--- ", "+++ ", "@@ ")
        text = "".join(ln for c in chunks for ln in c.splitlines(keepends=True) if not ln.startswith(skip))
        return text.replace("\n", "").replace("+", "")

    def test_single_giant_line_is_sliced_not_dropped(self):
        giant = "x" * 5_000
        chunks = air.split_diff(make_diff("min.js", [giant]), 800)
        self.assertEqual(self.body_text(chunks), giant)
        self.assertTrue(all(len(c.encode()) <= 800 for c in chunks))

    def test_multibyte_text_stays_within_limit(self):
        chunks = air.split_diff(make_diff("u.md", ["é€😀" * 300]), 600)
        self.assertTrue(all(len(c.encode()) <= 600 for c in chunks))
        self.assertEqual(self.body_text(chunks), "é€😀" * 300)

    def test_several_files_group_without_loss(self):
        diff = "".join(make_diff(f"f{i}.cs", [f"body {i}"]) for i in range(6))
        chunks = air.split_diff(diff, 400)
        self.assertEqual(sorted(self.added_lines(chunks)), sorted(f"+body {i}" for i in range(6)))


class ParseFindingsTests(unittest.TestCase):
    def test_valid_object_with_findings(self):
        out = air.parse_findings('{"findings": [{"severity": "BLOCKER", "file": "a", "line": 1, "title": "t"}]}')
        self.assertEqual(out[0]["severity"], "blocking")

    def test_empty_findings_list_is_clean(self):
        self.assertEqual(air.parse_findings('{"findings": []}'), [])

    def test_prose_and_fences_around_json(self):
        text = 'Here is my review {not json}\n```json\n{"findings": [{"severity": "warning"}]}\n```\nthanks'
        self.assertEqual(air.parse_findings(text)[0]["severity"], "warning")

    def test_unknown_missing_or_non_string_severity_becomes_warning_with_notice(self):
        import contextlib
        import io
        for raw in ('{"severity": "huge"}', "{}", '{"severity": 5}', '{"severity": null}', '{"severity": ["blocking"]}'):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                sev = air.parse_findings('{"findings": [' + raw + ']}')[0]["severity"]
            self.assertEqual(sev, "warning", raw)
            self.assertIn("treated as warning", err.getvalue(), raw)

    def test_missing_findings_key_is_an_error(self):
        with self.assertRaises(ValueError):
            air.parse_findings('{"result": "ok"}')

    def test_no_json_is_an_error(self):
        with self.assertRaises(ValueError):
            air.parse_findings("looks fine to me")

    def test_findings_not_a_list_is_an_error(self):
        with self.assertRaises(ValueError):
            air.parse_findings('{"findings": "none"}')

    def test_finding_not_an_object_is_an_error(self):
        with self.assertRaises(ValueError):
            air.parse_findings('{"findings": ["a string"]}')

    def test_truncated_json_is_an_error(self):
        with self.assertRaises(ValueError):
            air.parse_findings('{"findings": [{"severity": "blocking"')


class PromptTests(unittest.TestCase):
    def test_prior_findings_are_capped_by_item_count_and_stay_valid_json(self):
        import json
        prior = [{"severity": "warning", "title": f"finding {i}", "evidence": "e" * 500} for i in range(air.MAX_PRIOR_FINDINGS + 12)]
        text = air._prior_text(prior)
        body, _, note = text.partition("\n(")
        self.assertEqual(len(json.loads(body)), air.MAX_PRIOR_FINDINGS)
        self.assertIn("12 more earlier findings omitted", note)

    def test_prior_findings_under_the_cap_are_complete(self):
        import json
        prior = [{"title": "a" * 400} for _ in range(5)]
        self.assertEqual(json.loads(air._prior_text(prior)), prior)

    def test_read_body_strips_frontmatter_written_with_crlf(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.md"
            f.write_bytes(b"---\r\nname: a\r\ndescription: d\r\n---\r\n\r\nBody text\r\n")
            self.assertEqual(air.read_body(f), "Body text")


class StateTests(unittest.TestCase):
    def test_corrupt_state_exits_2_and_mentions_reset(self):
        import contextlib
        import io
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "state.json").write_text("{not json", encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = air.main(["--out-dir", tmp, "--base", "HEAD"])
            self.assertEqual(code, 2)
            self.assertIn("--reset", err.getvalue())

    def test_wrong_shape_state_is_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            for bad in ("[]", '{"rounds": 2}', '{"branches": {"x": {"rounds": "2", "findings": []}}}'):
                p.write_text(bad, encoding="utf-8")
                with self.assertRaises(ValueError, msg=bad):
                    air.load_state(p)

    def test_missing_state_file_is_empty(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(air.load_state(Path(tmp) / "none.json"), {"branches": {}})

    def test_rounds_are_keyed_by_branch(self):
        import contextlib
        import io
        import json
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "state.json").write_text(json.dumps({"branches": {
                "feature/a": {"rounds": 3, "findings": [{"title": "old"}]}}}), encoding="utf-8")
            diff = make_diff("a.cs", ["x"])
            args = ["--out-dir", tmp, "--base", "origin/main", "--max-rounds", "3", "--dry-run"]

            def run_on(branch: str) -> str:
                err = io.StringIO()
                with mock.patch.object(air, "get_diff", return_value=diff), \
                        mock.patch.object(air, "current_branch", return_value=branch), \
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                    self.assertEqual(air.main(args), 0)
                return err.getvalue()

            self.assertIn("round 1/3", run_on("feature/b"))  # a new branch starts fresh
            self.assertIn("round 4/3", run_on("feature/a"))  # feature/a keeps its own count


class MergeTests(unittest.TestCase):
    def test_merge_keeps_most_severe_duplicate(self):
        merged = air.merge([
            {"file": "a", "line": 1, "title": "t", "severity": "warning"},
            {"file": "a", "line": 1, "title": "t", "severity": "blocking"},
        ])
        self.assertEqual([f["severity"] for f in merged], ["blocking"])


if __name__ == "__main__":
    unittest.main()
