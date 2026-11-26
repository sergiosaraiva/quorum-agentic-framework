"""remove_examples.py on a temp copy of the fixture tree. Run: python3 -m unittest discover -s scripts/kb/tests"""
import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_chunks  # noqa: E402
import lib  # noqa: E402
import remove_examples  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
KEPT_CHUNK = ("---\nchunk_id: QF-001\ntitle: Kept chunk\ntopics: [kept]\nlinks: []\nsources: [s]\n---\n"
              + "word " * 50)
KEPT_RECORD = ("---\nid: TQ-100\nkind: TQ\ntitle: Kept record\nstatus: open\ndecider: tech-lead\n"
               "asked: 2026-01-01\n---\nThe refund rule in BC-003 still needs a product answer.\n")


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = remove_examples.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class RemoveExamplesTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        # What an adopter has next to the examples: one kept chunk and record, and prose that cites ids.
        (self.root / "kb" / "chunks" / "QF-001-kept.md").write_text(KEPT_CHUNK, encoding="utf-8")
        (self.root / "questions" / "records" / "TQ-100.md").write_text(KEPT_RECORD, encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("Money rules: OD-001. Refunds: BC-003 and QF-001.\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "a.md").write_text("BQ-001, OD-001 and TQ-100.\n", encoding="utf-8")
        check_chunks.write_toc(self.root / "kb")
        self.chunks = self.root / "kb" / "chunks"
        self.records = self.root / "questions" / "records"

    def test_dry_run_lists_every_example_and_deletes_nothing(self):
        before = sorted(p.name for p in self.root.rglob("*.md"))
        code, out, _ = run("--root", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(out.count("would delete"), 10)
        self.assertIn("would delete  kb/chunks/BC-003-refund-policy.md", out)
        self.assertIn("would delete  questions/records/OD-001.md", out)
        self.assertNotIn("QF-001-kept", out)
        self.assertNotIn("TQ-100", out)
        self.assertIn("10 example file(s)", out)
        self.assertIn("dry run: nothing deleted", out)
        self.assertEqual(sorted(p.name for p in self.root.rglob("*.md")), before)

    def test_apply_deletes_only_example_files(self):
        code, out, _ = run("--root", str(self.root), "--apply")
        self.assertEqual(code, 0, out)
        self.assertEqual([p.name for p in self.chunks.glob("*.md")], ["QF-001-kept.md"])
        self.assertEqual([p.name for p in self.records.glob("*.md")], ["TQ-100.md"])

    def test_apply_regenerates_the_toc(self):
        _, out, _ = run("--root", str(self.root), "--apply")
        self.assertIn("regenerated kb/TOC.md", out)
        toc = (self.root / "kb" / "TOC.md").read_text(encoding="utf-8")
        self.assertIn("QF-001", toc)
        self.assertNotIn("BC-001", toc)
        self.assertEqual(check_chunks.stale_toc(self.root / "kb"), [])

    def test_apply_does_not_create_a_missing_toc(self):
        (self.root / "kb" / "TOC.md").unlink()
        _, out, _ = run("--root", str(self.root), "--apply")
        self.assertNotIn("TOC", out)
        self.assertFalse((self.root / "kb" / "TOC.md").exists())

    def test_apply_lists_remaining_citations_grouped_by_file(self):
        code, out, _ = run("--root", str(self.root), "--apply")
        self.assertEqual(code, 0)
        self.assertIn("5 remaining citation(s) of a removed id in 3 file(s):", out)
        self.assertIn("  CLAUDE.md: BC-003, OD-001\n", out)
        self.assertIn("  docs/a.md: BQ-001, OD-001\n", out)
        self.assertIn("  questions/records/TQ-100.md: BC-003\n", out)
        self.assertNotIn("QF-001,", out)  # defined, kept ids are not citations of a removed id
        self.assertTrue(out.rstrip().endswith("are removed separately."))
        self.assertIn("src/, tests/ and frontend/", out)
        self.assertIn("docs/slices/", out)

    def test_apply_respects_the_ignore_list_and_reports_a_clean_tree(self):
        (self.root / "scripts" / "kb").mkdir(parents=True)
        (self.root / check_chunks.REF_IGNORE_FILE).write_text(
            "CLAUDE.md:BC-003\nCLAUDE.md:OD-001\ndocs/a.md:BQ-001\ndocs/a.md:OD-001\n"
            "questions/records/TQ-100.md:BC-003\n", encoding="utf-8")
        _, out, _ = run("--root", str(self.root), "--apply")
        self.assertIn("no remaining citation of a removed id", out)
        self.assertIn("removed separately", out)

    def test_ids_are_reported_even_when_their_prefix_is_gone(self):
        (self.root / "CLAUDE.md").write_text("Only BC-001.\n", encoding="utf-8")
        _, out, _ = run("--root", str(self.root), "--apply")
        self.assertIn("  CLAUDE.md: BC-001\n", out)

    def test_after_apply_the_surviving_tree_lints_clean_apart_from_the_citations(self):
        run("--root", str(self.root), "--apply")
        errors = check_chunks.lint(self.root / "kb", self.root / "questions")
        self.assertEqual(errors, [])

    def test_second_apply_finds_nothing_to_delete(self):
        run("--root", str(self.root), "--apply")
        code, out, _ = run("--root", str(self.root), "--apply")
        self.assertEqual(code, 0)
        self.assertIn("0 example file(s)", out)
        self.assertIn("no remaining citation of a removed id", out.replace("QF-001", ""))

    def test_only_a_true_example_flag_counts_and_malformed_files_are_skipped(self):
        for name, flag in (("TQ-101.md", "example: false"), ("TQ-102.md", 'example: "true"'), ("TQ-103.md", "")):
            (self.records / name).write_text(KEPT_RECORD.replace("TQ-100", name[:-3]).replace(
                "asked: 2026-01-01\n", f"asked: 2026-01-01\n{flag}\n"), encoding="utf-8")
        (self.records / "TQ-104.md").write_text("no frontmatter\n", encoding="utf-8")
        code, out, err = run("--root", str(self.root), "--apply")
        self.assertEqual(code, 0)
        self.assertIn("skipping TQ-104.md", err)
        self.assertEqual(sorted(p.name for p in self.records.glob("*.md")),
                         ["TQ-100.md", "TQ-101.md", "TQ-102.md", "TQ-103.md", "TQ-104.md"])

    def test_root_without_a_kb_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as empty:
            code, _, err = run("--root", empty)
        self.assertEqual(code, 2)
        self.assertIn("no kb/chunks", err)

    def test_unknown_option_exits_2(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            remove_examples.main(["--nope"])
        self.assertEqual(cm.exception.code, 2)

    def test_delete_failure_exits_2(self):
        from unittest import mock
        with mock.patch.object(Path, "unlink", side_effect=PermissionError("denied")):
            code, _, err = run("--root", str(self.root), "--apply")
        self.assertEqual(code, 2)
        self.assertIn("denied", err)

    def test_frontmatter_id_is_used_not_the_filename(self):
        (self.records / "OD-001.md").unlink()
        (self.records / "scratch.md").write_text(
            KEPT_RECORD.replace("id: TQ-100", "id: TQ-555").replace("asked:", "example: true\nasked:"),
            encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("TQ-555 only.\n", encoding="utf-8")
        _, out, _ = run("--root", str(self.root), "--apply")
        self.assertIn("  CLAUDE.md: TQ-555\n", out)
        self.assertEqual([r.id for r in lib.load_records(self.root / "questions")], ["TQ-100"])


if __name__ == "__main__":
    unittest.main()
