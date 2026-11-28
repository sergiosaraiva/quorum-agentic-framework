"""Tests for scripts/coverage_changed.py. Run: python3 -m unittest discover -s scripts/tests"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import coverage_changed as cc  # noqa: E402


def report(root: Path, name: str, filename: str, hits: list[int]) -> Path:
    body = "".join(f'<line number="{i + 1}" hits="{h}"/>' for i, h in enumerate(hits))
    p = root / name
    p.write_text(f'<coverage><packages><package><classes><class filename="{filename}"><lines>{body}</lines>'
                 "</class></classes></package></packages></coverage>")
    return p


class CoverageTests(unittest.TestCase):
    def test_percentage_over_changed_files_only(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            r = report(root, "a.xml", str(root / "src/A.cs"), [1, 0, 0, 1])
            lines = cc.merged_lines([r], root)
            out = cc.summarize(["src/A.cs"], lines)
            self.assertEqual(out["changed_files_pct"], 50.0)
            self.assertEqual(out["files"], {"src/A.cs": 50.0})

    def test_reports_merge_by_any_hit(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            r1 = report(root, "a.xml", str(root / "src/A.cs"), [1, 0, 0, 0])
            r2 = report(root, "b.xml", str(root / "src/A.cs"), [0, 1, 1, 0])
            out = cc.summarize(["src/A.cs"], cc.merged_lines([r1, r2], root))
            self.assertEqual(out["changed_files_pct"], 75.0)

    def test_unmeasured_file_is_listed_not_counted(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            r = report(root, "a.xml", str(root / "src/A.cs"), [1, 1])
            out = cc.summarize(["src/A.cs", "src/B.cs"], cc.merged_lines([r], root))
            self.assertEqual(out["changed_files_pct"], 100.0)
            self.assertEqual(out["not_measured"], ["src/B.cs"])

    def test_no_measured_files_is_zero_with_everything_listed(self):
        out = cc.summarize(["src/B.cs"], {})
        self.assertEqual((out["changed_files_pct"], out["not_measured"]), (None, ["src/B.cs"]))
        self.assertIn('"changed_files_pct": null', cc.json.dumps(out))

    def test_missing_report_exits_2(self):
        self.assertEqual(cc.main(["--base", "main", "/nonexistent/report.xml"]), 2)

    def test_malformed_report_exits_2(self):
        with tempfile.TemporaryDirectory() as t:
            bad = Path(t) / "bad.xml"
            bad.write_text("<coverage")
            self.assertEqual(cc.main(["--base", "main", str(bad)]), 2)

    def test_non_integer_line_number_or_hits_exits_2(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as t:
            for attr in ('number="x" hits="1"', 'number="1" hits="many"'):
                bad = Path(t) / "bad.xml"
                bad.write_text('<coverage><packages><package><classes><class filename="src/A.cs"><lines>'
                               f"<line {attr}/></lines></class></classes></package></packages></coverage>")
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(cc.main(["--base", "HEAD", str(bad)]), 2, attr)
                self.assertIn("coverage_changed:", err.getvalue())

    def test_base_starting_with_dash_is_rejected(self):
        self.assertEqual(cc.main(["--base=--output=x", "r.xml"]), 2)


if __name__ == "__main__":
    unittest.main()
