"""Tests for scripts/framework_lint.py. Run: python3 -m unittest discover -s scripts/tests"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import framework_lint as fl  # noqa: E402

GOOD_AGENT = "---\nname: {n}\ndescription: Does a thing\nmodel: sonnet\ntools: Read, Grep\n---\n\n# Body\n"
GOOD_SKILL = "---\nname: {n}\ndescription: Does a thing\n---\n\n# Body\n"
INDEX = "# Index\n\n| Skill | Purpose | Used by |\n|---|---|---|\n{rows}"


def build(root: Path, agents: dict[str, str], skills: dict[str, str], index_rows: list[str] | None = None) -> Path:
    (root / "agents").mkdir(parents=True)
    (root / "skills").mkdir(parents=True)
    for name, text in agents.items():
        (root / "agents" / f"{name}.md").write_text(text, encoding="utf-8")
    for name, text in skills.items():
        (root / "skills" / name).mkdir()
        (root / "skills" / name / "SKILL.md").write_text(text, encoding="utf-8")
    rows = index_rows if index_rows is not None else list(skills)
    (root / "skills" / "SKILL-INDEX.md").write_text(
        INDEX.format(rows="".join(f"| {r} | x | y |\n" for r in rows)), encoding="utf-8")
    return root


class LintTests(unittest.TestCase):
    def run_lint(self, agents, skills, index_rows=None, strict=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(Path(tmp) / ".claude", agents, skills, index_rows)
            return fl.lint(root, strict)

    def test_clean_framework_passes(self):
        r = self.run_lint({"a": GOOD_AGENT.format(n="a")}, {"s": GOOD_SKILL.format(n="s")})
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_name_must_match_file_and_folder(self):
        r = self.run_lint({"a": GOOD_AGENT.format(n="other")}, {"s": GOOD_SKILL.format(n="wrong")})
        self.assertEqual(sum("must equal" in e for e in r.errors), 2)

    def test_description_over_1024_is_an_error(self):
        long_skill = "---\nname: s\ndescription: " + "x" * 1025 + "\n---\nbody\n"
        r = self.run_lint({}, {"s": long_skill})
        self.assertTrue(any("1025 characters" in e for e in r.errors))

    def test_unquoted_colon_in_description_is_invalid_yaml(self):
        bad = "---\nname: s\ndescription: Use when: the user asks\n---\nbody\n"
        r = self.run_lint({}, {"s": bad})
        self.assertTrue(any('": "' in e for e in r.errors))

    def test_quoted_colon_is_fine(self):
        ok = '---\nname: s\ndescription: "Use when: the user asks"\n---\nbody\n'
        self.assertEqual(self.run_lint({}, {"s": ok}).errors, [])

    def test_missing_frontmatter_and_unclosed_frontmatter(self):
        r = self.run_lint({"a": "# no frontmatter\n"}, {"s": "---\nname: s\ndescription: d\nno closing\n"})
        self.assertEqual(sum("missing frontmatter" in e for e in r.errors), 2)

    def test_dash_inside_description_does_not_confuse_parsing(self):
        ok = "---\nname: s\ndescription: a --- b -- c\n---\nbody --- more\n"
        self.assertEqual(self.run_lint({}, {"s": ok}).errors, [])

    def test_duplicate_key_is_an_error(self):
        dup = "---\nname: s\nname: s\ndescription: d\n---\nbody\n"
        self.assertTrue(any("duplicate key" in e for e in self.run_lint({}, {"s": dup}).errors))

    def test_agent_model_must_be_known(self):
        bad = GOOD_AGENT.format(n="a").replace("sonnet", "gpt")
        self.assertTrue(any("model" in e for e in self.run_lint({"a": bad}, {}).errors))

    def test_agent_tools_must_not_include_agent_or_askuserquestion(self):
        bad = GOOD_AGENT.format(n="a").replace("Read, Grep", "Read, Agent, AskUserQuestion, Grep")
        errors = self.run_lint({"a": bad}, {}).errors
        self.assertTrue(any("Agent, AskUserQuestion" in e for e in errors))

    def test_tool_named_like_agent_prefix_is_not_flagged(self):
        ok = GOOD_AGENT.format(n="a").replace("Read, Grep", "Read, mcp__x__Agent_thing")
        self.assertEqual(self.run_lint({"a": ok}, {}).errors, [])

    def test_block_list_tools_are_checked(self):
        bad = "---\nname: a\ndescription: d\nmodel: opus\ntools:\n  - Read\n  - Agent\n---\nbody\n"
        self.assertTrue(any("Agent" in e for e in self.run_lint({"a": bad}, {}).errors))

    def test_index_must_match_skill_folders(self):
        r = self.run_lint({}, {"s": GOOD_SKILL.format(n="s"), "t": GOOD_SKILL.format(n="t")}, index_rows=["s", "ghost"])
        text = "\n".join(r.errors)
        self.assertIn("'t' exists but is not listed", text)
        self.assertIn("lists 'ghost'", text)

    def test_oversize_files_warn_and_strict_errors(self):
        big_skill = GOOD_SKILL.format(n="s") + "x" * (8 * 1024)
        warn = self.run_lint({}, {"s": big_skill})
        self.assertEqual(warn.errors, [])
        self.assertEqual(len(warn.warnings), 1)
        self.assertEqual(len(self.run_lint({}, {"s": big_skill}, strict=True).errors), 1)

    def test_shared_patterns_file_is_not_treated_as_an_agent(self):
        r = self.run_lint({"_SHARED-PATTERNS": "# no frontmatter, shared document\n"}, {})
        self.assertEqual(r.errors, [])

    def test_skill_folder_without_skill_md_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(Path(tmp) / ".claude", {}, {})
            (root / "skills" / "empty").mkdir()
            self.assertTrue(any("no SKILL.md" in e for e in fl.lint(root).errors))

    def test_only_filter_lints_just_the_given_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(Path(tmp) / ".claude", {"a": "# broken\n", "b": GOOD_AGENT.format(n="b")}, {})
            r = fl.lint(root, only={(root / "agents" / "b.md").resolve()})
            self.assertEqual(r.errors, [])


class ParserTests(unittest.TestCase):
    def test_folded_block_and_flow_list(self):
        data, errors = fl.parse_frontmatter("name: x\ndescription: >\n  one\n  two\ntopics: [a, b]\n")
        self.assertEqual(errors, [])
        self.assertEqual(data["description"], "one two")
        self.assertEqual(data["topics"], ["a", "b"])

    def test_unterminated_quote_is_reported(self):
        _, errors = fl.parse_frontmatter('name: x\ndescription: "oops\n')
        self.assertTrue(errors)


class ToolNameTests(unittest.TestCase):
    def test_names_are_cut_before_parentheses(self):
        self.assertEqual(fl.tool_names("Read, Agent(worker, other), Bash(git diff:*)"), ["Read", "Agent", "Bash"])
        self.assertEqual(fl.tool_names(["Agent(x)", "Grep"]), ["Agent", "Grep"])

    def test_agent_with_argument_is_flagged(self):
        bad = "---\nname: a\ndescription: d\nmodel: opus\ntools: Read, Agent(worker, helper), Grep\n---\nbody\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = build(Path(tmp) / ".claude", {"a": bad}, {})
            self.assertTrue(any("Agent" in e for e in fl.lint(root).errors))

    def test_agent_prefix_of_another_tool_is_not_flagged(self):
        self.assertEqual(fl.tool_names("AgentSmith, mcp__x__Agent"), ["AgentSmith", "mcp__x__Agent"])


class StagedTests(unittest.TestCase):
    """Uses a throwaway git repository: --staged must lint the staged blob, not the working tree."""

    def setUp(self):
        import subprocess
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.git = lambda *a: subprocess.run(["git", *a], cwd=self.repo, check=True, capture_output=True, text=True)
        self.git("init", "-q")
        self.root = build(self.repo / ".claude", {"a": GOOD_AGENT.format(n="a")}, {"s": GOOD_SKILL.format(n="s")})
        self.agent = self.root / "agents" / "a.md"

    def tearDown(self):
        self.tmp.cleanup()

    def run_staged(self):
        paths = {(self.repo / p).resolve() for p in fl.staged_paths(self.repo)}
        return fl.lint(self.root, only=paths, reader=fl.staged_reader(self.repo))

    def test_staged_bad_blob_is_reported_even_if_working_tree_was_fixed(self):
        self.agent.write_text(GOOD_AGENT.format(n="a").replace("sonnet", "gpt"), encoding="utf-8")
        self.git("add", ".")
        self.agent.write_text(GOOD_AGENT.format(n="a"), encoding="utf-8")  # fixed, but not staged
        self.assertTrue(any("model" in e for e in self.run_staged().errors))

    def test_staged_good_blob_passes_even_if_working_tree_is_broken(self):
        self.git("add", ".")
        self.agent.write_text("# broken, unstaged edit\n", encoding="utf-8")
        self.assertEqual(self.run_staged().errors, [])

    def test_only_staged_files_are_linted(self):
        self.git("add", ".")
        (self.root / "agents" / "b.md").write_text("# untracked and broken\n", encoding="utf-8")
        self.assertEqual(self.run_staged().errors, [])

    def test_staged_agent_tool_with_argument_is_reported(self):
        self.agent.write_text(GOOD_AGENT.format(n="a").replace("Read, Grep", "Read, Agent(w)"), encoding="utf-8")
        self.git("add", ".")
        self.assertTrue(any("Agent" in e for e in self.run_staged().errors))


if __name__ == "__main__":
    unittest.main()
