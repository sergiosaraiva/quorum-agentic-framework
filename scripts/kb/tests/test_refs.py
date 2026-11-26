"""Dangling-reference and stale-TOC checks of check_chunks.py. Run: python3 -m unittest discover -s scripts/kb/tests

Every test works on a temp copy of the fixture tree, never on the live kb/ and questions/."""
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

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run_main(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = check_chunks.main(list(argv))
    return code, out.getvalue()


class TreeCase(unittest.TestCase):
    """A temp repo root holding a copy of the fixture kb/ and questions/, with a current kb/TOC.md."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        check_chunks.write_toc(self.root / "kb")

    def refs(self):
        return check_chunks.dangling_messages(self.root, self.root / "kb", self.root / "questions")


class DanglingRefTests(TreeCase):
    def test_fixture_tree_has_no_dangling_reference(self):
        self.assertEqual(self.refs(), [])

    def test_undefined_id_is_reported_per_file_and_id_once(self):
        write(self.root / "CLAUDE.md", "See OD-001 and OD-777, again OD-777 and BC-404.\n")
        self.assertEqual(self.refs(), ["CLAUDE.md: cites BC-404, which no chunk or record defines",
                                       "CLAUDE.md: cites OD-777, which no chunk or record defines"])

    def test_scanned_locations_nested_claude_md_agents_skills_docs_readme_chunks_records(self):
        for rel in ("src/Api/CLAUDE.md", ".claude/agents/a.md", ".claude/skills/s/SKILL.md", "docs/x/y.md",
                    "README.md"):
            write(self.root / rel, "cites TQ-900\n")
        chunk = self.root / "kb" / "chunks" / "BC-001-order-lifecycle.md"
        chunk.write_text(chunk.read_text(encoding="utf-8") + "\nSee QF-900.\n", encoding="utf-8")
        record = self.root / "questions" / "records" / "OD-001.md"
        record.write_text(record.read_text(encoding="utf-8") + "\nSee BQ-900.\n", encoding="utf-8")
        files = sorted(m.split(":")[0] for m in self.refs())
        self.assertEqual(files, [".claude/agents/a.md", ".claude/skills/s/SKILL.md", "README.md", "docs/x/y.md",
                                 "kb/chunks/BC-001-order-lifecycle.md", "questions/records/OD-001.md",
                                 "src/Api/CLAUDE.md"])

    def test_other_markdown_and_vendored_directories_are_not_scanned(self):
        write(self.root / "notes.md", "TQ-900\n")
        write(self.root / "frontend" / "node_modules" / "pkg" / "CLAUDE.md", "TQ-900\n")
        write(self.root / "frontend" / "CLAUDE.md", "fine\n")
        self.assertEqual(self.refs(), [])

    def test_prefix_of_an_existing_chunk_is_recognised(self):
        write(self.root / "kb" / "chunks" / "ZZ-001-x.md",
              "---\nchunk_id: ZZ-001\ntitle: T\ntopics: [t]\nlinks: []\nsources: [s]\n---\n" + "word " * 50)
        write(self.root / "CLAUDE.md", "ZZ-001 exists, ZZ-002 does not, XY-001 is not an id of this tree.\n")
        self.assertEqual(self.refs(), ["CLAUDE.md: cites ZZ-002, which no chunk or record defines"])

    def test_ignore_list_by_id_by_path_and_by_glob_with_comments(self):
        write(self.root / "CLAUDE.md", "BQ-901 BQ-902 BQ-903\n")
        write(self.root / "docs" / "a.md", "BQ-901 BQ-902 BQ-903\n")
        write(self.root / check_chunks.REF_IGNORE_FILE,
              "# comment\n\nBQ-901  # ignored everywhere\nCLAUDE.md:BQ-902\ndocs/*.md:BQ-903\n")
        self.assertEqual(self.refs(), ["CLAUDE.md: cites BQ-903, which no chunk or record defines",
                                       "docs/a.md: cites BQ-902, which no chunk or record defines"])

    def test_missing_ignore_file_is_empty(self):
        self.assertEqual(check_chunks.load_ref_ignore(self.root / "nope.txt"), [])

    def test_extra_cited_ids_are_found_whatever_their_prefix(self):
        write(self.root / "CLAUDE.md", "VS-123 and VS-124\n")
        defined = {c.chunk_id for c in lib.load_chunks(self.root / "kb")} | {
            r.id for r in lib.load_records(self.root / "questions")}
        self.assertEqual(check_chunks.dangling_refs(self.root, defined), [])
        found = check_chunks.dangling_refs(self.root, defined, cited={"VS-123"})
        self.assertEqual(found, [("CLAUDE.md", "VS-123")])

    def test_main_warns_by_default_and_fails_with_strict_refs(self):
        write(self.root / "CLAUDE.md", "OD-777\n")
        code, out = run_main("--root", str(self.root))
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  CLAUDE.md: cites OD-777, which no chunk or record defines", out)
        self.assertIn("0 error(s), 1 warning(s)", out)
        code, out = run_main("--root", str(self.root), "--strict-refs")
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR CLAUDE.md: cites OD-777, which no chunk or record defines", out)
        self.assertIn("1 error(s), 0 warning(s)", out)

    def test_strict_refs_does_not_hide_the_stale_toc_or_block_write_toc(self):
        write(self.root / "CLAUDE.md", "OD-777\n")
        chunk = self.root / "kb" / "chunks" / "BC-001-order-lifecycle.md"
        chunk.write_text(chunk.read_text(encoding="utf-8") + "\nOne more sentence of text.\n", encoding="utf-8")
        code, out = run_main("--root", str(self.root), "--strict-refs")
        self.assertEqual(code, 1, out)
        self.assertIn("WARN  kb/TOC.md is stale", out)
        code, out = run_main("--root", str(self.root), "--strict-refs", "--write-toc")
        self.assertEqual(code, 1, out)
        self.assertIn("wrote kb/TOC.md", out)
        self.assertEqual(check_chunks.stale_toc(self.root / "kb"), [])

    def test_main_on_the_clean_fixture_tree_reports_nothing(self):
        code, out = run_main("--root", str(self.root), "--strict-refs")
        self.assertEqual(code, 0, out)
        self.assertIn("checked 5 chunks, 5 records: 0 error(s), 0 warning(s)", out)


class StaleTocTests(TreeCase):
    def test_current_toc_gives_no_warning(self):
        self.assertEqual(check_chunks.stale_toc(self.root / "kb"), [])

    def test_missing_toc_warns_unless_there_is_no_chunk(self):
        (self.root / "kb" / "TOC.md").unlink()
        self.assertEqual(len(check_chunks.stale_toc(self.root / "kb")), 1)
        for p in (self.root / "kb" / "chunks").glob("*.md"):
            p.unlink()
        self.assertEqual(check_chunks.stale_toc(self.root / "kb"), [])

    def test_changed_chunk_makes_the_toc_stale_and_write_toc_fixes_it(self):
        chunk = self.root / "kb" / "chunks" / "BC-001-order-lifecycle.md"
        chunk.write_text(chunk.read_text(encoding="utf-8") + "\nOne more sentence of text.\n", encoding="utf-8")
        code, out = run_main("--root", str(self.root))
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  kb/TOC.md is stale", out)
        code, out = run_main("--root", str(self.root), "--write-toc")
        self.assertIn("wrote kb/TOC.md", out)
        code, out = run_main("--root", str(self.root))
        self.assertNotIn("TOC", out)

    def test_lint_errors_skip_the_toc_check(self):
        write(self.root / "kb" / "chunks" / "BC-009-bad.md", "no frontmatter\n")
        code, out = run_main("--root", str(self.root))
        self.assertEqual(code, 1, out)
        self.assertNotIn("TOC", out)


if __name__ == "__main__":
    unittest.main()
