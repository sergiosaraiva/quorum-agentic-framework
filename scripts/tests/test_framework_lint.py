"""Tests for scripts/framework_lint.py. Run: python3 -m unittest discover -s scripts/tests"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        with mock.patch.object(fl, "NO_BASH_AGENTS", ()), mock.patch.object(fl, "REVIEWER_AGENTS", ()), \
                mock.patch.object(fl, "PROBE_AGENTS", ()):
            r = self.run_lint({"_SHARED-PATTERNS": "# no frontmatter, shared document\nField `unverified` here; `probe_requests`.\n7. KB MCP unreachable: stop\n## Common Tool Permissions\n"}, {})
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

    def test_staged_deletion_of_a_skill_is_seen_and_checks_the_index(self):
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-qm", "base",
                 "--no-verify")
        self.git("rm", "-rq", ".claude/skills/s")
        self.assertIn(".claude/skills/s/SKILL.md", fl.staged_paths(self.repo))
        errors = self.run_staged().errors
        self.assertTrue(any("lists 's'" in e for e in errors), errors)  # SKILL-INDEX.md still lists the skill

    def test_staged_deletion_kept_in_the_working_tree_is_not_read_and_still_checks_the_index(self):
        # `git rm --cached` removes the path from the index but leaves the file: reading `git show :path` would fail
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-qm", "base",
                 "--no-verify")
        self.git("rm", "-rq", "--cached", ".claude/skills/s", ".claude/agents/a.md")
        self.assertTrue((self.root / "skills" / "s" / "SKILL.md").exists())
        errors = self.run_staged().errors  # must not raise OSError
        self.assertTrue(any("lists 's'" in e for e in errors), errors)


class FrontmatterVocabularyTests(unittest.TestCase):
    def run_lint(self, agents=None, skills=None, strict=False, extra=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(Path(tmp) / ".claude", agents or {}, skills or {})
            for rel, data in (extra or {}).items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            return fl.lint(root, strict)

    def agent_with(self, tools):
        return GOOD_AGENT.format(n="a").replace("Read, Grep", tools)

    def test_unknown_tool_name_is_a_warning_and_an_error_with_strict(self):
        report = self.run_lint({"a": self.agent_with("Read, Grpe")})
        self.assertFalse(any("unknown tool" in e for e in report.errors), report.errors)
        self.assertTrue(any("unknown tool 'Grpe'" in w for w in report.warnings), report.warnings)
        strict = self.run_lint({"a": self.agent_with("Read, Grpe")}, strict=True)
        self.assertTrue(any("unknown tool 'Grpe'" in e for e in strict.errors), strict.errors)

    def test_legacy_task_tool_is_an_error_that_suggests_agent(self):
        errors = self.run_lint({"a": self.agent_with("Read, Task")}).errors
        self.assertTrue(any("'Task'" in e and "'Agent'" in e for e in errors), errors)

    def test_builtin_and_mcp_tools_are_accepted(self):
        tools = ", ".join(t for t in fl.KNOWN_TOOLS if t != "Agent") + ", mcp__qa-kb__search, Bash(git diff:*)"
        self.assertEqual(self.run_lint({"a": self.agent_with(tools)}).errors, [])

    def test_agent_tool_keeps_its_own_forbidden_error_not_unknown(self):
        errors = self.run_lint({"a": self.agent_with("Read, Agent")}).errors
        self.assertTrue(any("must not list Agent" in e for e in errors))
        self.assertFalse(any("unknown tool" in e for e in errors))

    def test_permission_mode_is_validated(self):
        base = GOOD_AGENT.format(n="a")
        for mode in fl.PERMISSION_MODES:
            ok = base.replace("tools:", f"permissionMode: {mode}\ntools:")
            self.assertEqual(self.run_lint({"a": ok}).errors, [], mode)
        bad = base.replace("tools:", "permissionMode: yolo\ntools:")
        self.assertTrue(any("permissionMode 'yolo'" in e for e in self.run_lint({"a": bad}).errors))

    def test_unknown_frontmatter_keys_warn_for_agents_and_skills_even_when_strict(self):
        agent = GOOD_AGENT.format(n="a").replace("tools:", "permisionMode: plan\ntools:")
        skill = GOOD_SKILL.format(n="s").replace("description:", "allowed_tools: Read\ndescription:")
        r = self.run_lint({"a": agent}, {"s": skill}, strict=True)
        self.assertEqual(r.errors, [])
        text = "\n".join(r.warnings)
        self.assertIn("permisionMode", text)
        self.assertIn("allowed_tools", text)

    def test_known_keys_do_not_warn(self):
        agent = GOOD_AGENT.format(n="a").replace("tools:", "effort: high\ncolor: blue\nmaxTurns: 5\ntools:")
        skill = GOOD_SKILL.format(n="s").replace("description:", "when_to_use: x\nallowed-tools: Read\ndescription:")
        self.assertEqual(self.run_lint({"a": agent}, {"s": skill}).warnings, [])


class SizeAndLayoutTests(unittest.TestCase):
    def run_lint(self, agents=None, skills=None, strict=False, extra=None):
        return FrontmatterVocabularyTests.run_lint(self, agents, skills, strict, extra)

    def test_crlf_does_not_inflate_the_size(self):
        lf = GOOD_SKILL.format(n="s") + "x\n" * 3000  # about 6 KB with LF, about 9 KB with CRLF
        self.assertLess(len(lf.encode()), fl.MAX_SKILL_BYTES)
        with tempfile.TemporaryDirectory() as tmp:
            root = build(Path(tmp) / ".claude", {}, {"s": GOOD_SKILL.format(n="s")})
            (root / "skills" / "s" / "SKILL.md").write_bytes(lf.replace("\n", "\r\n").encode())
            r = fl.lint(root)
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_supporting_skill_markdown_is_size_checked_as_warning_only(self):
        big = b"x" * (fl.MAX_SKILL_SUPPORT_BYTES + 1)
        r = self.run_lint(skills={"s": GOOD_SKILL.format(n="s")}, strict=True,
                          extra={"skills/s/reference/big.md": big, "skills/s/reference/small.md": b"ok"})
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("big.md", r.warnings[0])

    def test_markdown_in_an_agents_subfolder_warns(self):
        r = self.run_lint(agents={"a": GOOD_AGENT.format(n="a")}, extra={"agents/team/helper.md": b"# nested\n"})
        self.assertEqual(r.errors, [])
        self.assertTrue(any("helper.md" in w and "subfolder" in w for w in r.warnings), r.warnings)


SHARED = """# Shared
Field `unverified` (optional list): defined here. Subagent Limits: `probe_requests` entries.
7. KB MCP unreachable (sole statement), in order:
   - First, agents with `Bash` use `python3 scripts/kb/search.py "<q>"`.
   - Neither works, authoring agents (`doc-writer`): stop.
   - Reviewing agents (`doc-reviewer`): list unverified.

## Common Tool Permissions

| Agent class | Tools |
|---|---|
| Analysts (`doc-analyst`) | Read, Grep, Glob |

## Next

What blocks.
"""
KB = "mcp__business-kb__search, mcp__qa-kb__get"


REVIEWER_BODY = "| KB unreachable | `_SHARED-PATTERNS.md` Never Invent rule 7 |\n\"unverified\": [\"optional\"]\n"


def agent(n, tools, body="| KB unreachable | `_SHARED-PATTERNS.md` Never Invent rule 7 |\n"):
    return f"---\nname: {n}\ndescription: d\nmodel: sonnet\ntools: {tools}\n---\n\n{body}"


class SharedRuleTests(unittest.TestCase):
    """check_shared_rules: rule 7 and 'What blocks' have one owner; tools match rule 7."""

    def setUp(self):
        for attr, value in (("NO_BASH_AGENTS", ("doc-analyst",)), ("REVIEWER_AGENTS", ("doc-reviewer",)),
                             ("PROBE_AGENTS", ("doc-analyst",))):
            patch = mock.patch.object(fl, attr, value)
            patch.start()
            self.addCleanup(patch.stop)

    def errors(self, agents, skills=None, shared=SHARED):
        agents = {"_SHARED-PATTERNS": shared, **agents}
        with tempfile.TemporaryDirectory() as tmp:
            root = build(Path(tmp) / ".claude", {}, skills or {})
            for name, text in agents.items():
                (root / "agents" / f"{name}.md").write_text(text, encoding="utf-8")
            report = fl.Report(False)
            fl.check_shared_rules(root, report)
            return report.errors

    def good(self):
        return {"doc-writer": agent("doc-writer", f"Read, Bash, {KB}"), "doc-reviewer": agent("doc-reviewer", f"Read, Bash, {KB}", REVIEWER_BODY),
                "doc-analyst": agent("doc-analyst", f"Read, {KB}", "| KB unreachable | rule 7 |\n`probe_requests`\n")}

    def test_passing_case(self):
        self.assertEqual(self.errors(self.good()), [])

    def test_absent_shared_file_skips_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(Path(tmp) / ".claude", {"a": GOOD_AGENT.format(n="a")}, {})
            report = fl.Report(False)
            fl.check_shared_rules(root, report)
            self.assertEqual(report.errors, [])

    def test_cli_fallback_restated_in_agent(self):
        a = self.good()
        a["doc-writer"] = agent("doc-writer", f"Read, Bash, {KB}", "| KB unreachable | rule 7; run `python3 scripts/kb/search.py x` |\n")
        self.assertTrue(any("restates the rule 7 CLI fallback" in e for e in self.errors(a)))

    def test_cli_fallback_restated_in_skill(self):
        e = self.errors(self.good(), {"s": "---\nname: s\ndescription: d\n---\nrun python3 scripts/kb/search.py x\n"})
        self.assertTrue(any("skills" in x and "CLI fallback" in x for x in e))

    def test_three_branch_restated(self):
        a = self.good()
        a["doc-writer"] = agent("doc-writer", f"Read, Bash, {KB}", "KB unreachable (rule 7):\n- Neither works, stop.\n")
        self.assertTrue(any("Neither works" in e for e in self.errors(a)))

    def test_kb_unreachable_without_rule_7_pointer(self):
        a = self.good()
        a["doc-writer"] = agent("doc-writer", f"Read, Bash, {KB}", "| KB unreachable | stop and ask |\n")
        e = self.errors(a)
        self.assertTrue(any("must point to Never Invent 'rule 7'" in x for x in e))
        self.assertTrue(any("no 'KB unreachable' line pointing to rule 7" in x for x in e))

    def test_kb_agent_without_unreachable_row(self):
        a = self.good()
        a["doc-writer"] = agent("doc-writer", f"Read, Bash, {KB}", "nothing\n")
        self.assertTrue(any("no 'KB unreachable' line" in e for e in self.errors(a)))

    def test_still_blocking_and_blocking_when_header(self):
        s = {"s": "---\nname: s\ndescription: d\n---\n0.5 is Still Blocking\n| Status | Blocking when |\n"}
        e = self.errors(self.good(), s)
        self.assertTrue(any("'still blocking'" in x for x in e))
        self.assertTrue(any("'Blocking when'" in x for x in e))

    def test_blocking_status_list_needs_what_blocks(self):
        line = "Blocking: `ungrounded`, `fabricated-citation`, `stale`, `conflict` or `gate-failure`.\n"
        s = lambda t: {"s": "---\nname: s\ndescription: d\n---\n" + t}
        self.assertTrue(any("lists the blocking statuses" in x for x in self.errors(self.good(), s(line))))
        self.assertEqual(self.errors(self.good(), s(line.rstrip() + " (\"What blocks\")\n")), [])
        self.assertEqual(self.errors(self.good(), s('"status": "ungrounded|stale|fabricated-citation|conflict|gate-failure"\n')), [])

    def test_retired_unverified_field_names_fail(self):
        for old in ("areas_not_reviewed", "coverage_gaps"):
            a = self.good()
            a["doc-writer"] = agent("doc-writer", f"Read, Bash, {KB}", f"| KB unreachable | rule 7 |\n\"{old}\": []\n")
            self.assertTrue(any(f"retired field name `{old}`" in e for e in self.errors(a)), old)

    def test_retired_names_and_phrase_fail_in_shared_file_too(self):
        for bad in ("coverage_gaps", "areas_not_reviewed", "Coverage Gaps"):
            e = self.errors(self.good(), shared=SHARED + f"\n{bad}\n")
            self.assertTrue(any("retired" in x for x in e), bad)

    def test_retired_phrase_fails_in_a_skill(self):
        e = self.errors(self.good(), skills={"s": "---\nname: s\ndescription: reports coverage gaps\n---\n"})
        self.assertTrue(any("coverage gaps" in x for x in e))

    def test_shared_file_must_define_unverified(self):
        e = self.errors(self.good(), shared=SHARED.replace("Field `unverified`", "Field x"))
        self.assertTrue(any("does not define the field" in x for x in e))

    def test_prose_mention_is_not_the_contract_form(self):
        a = self.good()
        a["doc-reviewer"] = agent("doc-reviewer", f"Read, Bash, {KB}", "| KB unreachable | rule 7 |\nthe `unverified` list\n")
        self.assertTrue(any("lacks the `unverified` field" in e for e in self.errors(a)))

    def test_table_row_is_the_contract_form(self):
        a = self.good()
        a["doc-reviewer"] = agent("doc-reviewer", f"Read, Bash, {KB}", "| KB unreachable | rule 7 |\n| unverified | optional list |\n")
        self.assertEqual(self.errors(a), [])

    def test_listed_agent_without_file_fails_closed(self):
        for attr in ("REVIEWER_AGENTS", "PROBE_AGENTS"):
            with mock.patch.object(fl, attr, ("ghost-agent",)):
                e = self.errors(self.good())
            self.assertTrue(any("'ghost-agent' is listed" in x for x in e), attr)

    def test_probe_agent_must_name_probe_requests(self):
        a = self.good()
        a["doc-analyst"] = agent("doc-analyst", f"Read, {KB}")
        self.assertTrue(any("probe_requests" in e for e in self.errors(a)))

    def test_shared_file_must_define_probe_requests(self):
        e = self.errors(self.good(), shared=SHARED.replace("`probe_requests`", "x"))
        self.assertTrue(any("does not define `probe_requests`" in x for x in e))

    def test_reviewer_without_unverified_field_fails(self):
        a = self.good()
        a["doc-reviewer"] = agent("doc-reviewer", f"Read, Bash, {KB}")
        self.assertTrue(any("lacks the `unverified` field" in e for e in self.errors(a)))

    def test_no_bash_agent_listing_bash(self):
        a = self.good()
        a["doc-analyst"] = agent("doc-analyst", f"Read, Bash, {KB}")
        self.assertTrue(any("tools lists Bash" in e for e in self.errors(a)))

    def test_kb_agent_without_bash(self):
        a = self.good()
        a["doc-writer"] = agent("doc-writer", f"Read, {KB}")
        self.assertTrue(any("KB MCP tools but no Bash" in e for e in self.errors(a)))

    def test_rule_7_names_agent_without_file(self):
        a = self.good()
        del a["doc-reviewer"]
        self.assertTrue(any("'doc-reviewer' but agents/doc-reviewer.md does not exist" in e for e in self.errors(a)))

    def test_no_bash_constant_must_match_permissions_table(self):
        e = self.errors(self.good(), shared=SHARED.replace("Read, Grep, Glob |", "Read, Bash |"))
        self.assertTrue(any("NO_BASH_AGENTS lists 'doc-analyst'" in x for x in e))

    def test_earlier_table_row_does_not_mask_the_permissions_row(self):
        earlier = "| Role | Duty |\n|---|---|\n| `doc-analyst` | Steps 1-5 |\n\n"
        shared = SHARED.replace("## Common Tool Permissions", earlier + "## Common Tool Permissions")
        self.assertEqual(self.errors(self.good(), shared=shared), [])
        bad = shared.replace("Read, Grep, Glob |", "Read, Bash |")
        self.assertTrue(any("NO_BASH_AGENTS lists 'doc-analyst'" in e for e in self.errors(self.good(), shared=bad)))

    def test_row_after_the_permissions_section_does_not_count(self):
        shared = SHARED.replace("## Next", "## Next\n\n| `doc-analyst` | Read, Grep |\n").replace(
            "| Analysts (`doc-analyst`) | Read, Grep, Glob |", "| Analysts (`other`) | Read |")
        self.assertTrue(any("NO_BASH_AGENTS lists" in e for e in self.errors(self.good(), shared=shared)))

    def test_missing_permissions_section_fails_closed(self):
        shared = SHARED.replace("## Common Tool Permissions", "## Something else")
        self.assertTrue(any("'## Common Tool Permissions' not found" in e for e in self.errors(self.good(), shared=shared)))

    def test_blocking_when_matches_only_a_table_header_cell(self):
        s = lambda t: {"s": "---\nname: s\ndescription: d\n---\n" + t}
        for ok in ("A question is non-blocking when the work can continue.\n",
                   "| Status | Not blocking when x |\n", "Blocking when the build fails.\n"):
            self.assertEqual(self.errors(self.good(), s(ok)), [], ok)
        for bad in ("| Status | Blocking when |\n", "  | A | blocking WHEN | C |\n"):
            self.assertTrue(any("'Blocking when'" in e for e in self.errors(self.good(), s(bad))), bad)

    def test_neither_works_matches_only_the_bullet_form(self):
        s = lambda t: {"s": "---\nname: s\ndescription: d\n---\n" + t}
        self.assertEqual(self.errors(self.good(), s("If neither works, ask a human.\nNeither works well.\n")), [])
        for bad in ("- Neither works, stop.\n", "   * neither works: stop\n"):
            self.assertTrue(any("Neither works" in e for e in self.errors(self.good(), s(bad))), bad)

    def test_any_bash_row_in_permissions_section_fails(self):  # kills any() -> all() on the row check
        shared = SHARED.replace("| Analysts (`doc-analyst`) | Read, Grep, Glob |",
                                "| Analysts (`doc-analyst`) | Read, Grep, Glob |\n| Also (`doc-analyst`) | Read, Bash |")
        self.assertTrue(any("NO_BASH_AGENTS lists 'doc-analyst'" in e for e in self.errors(self.good(), shared=shared)))

    def test_status_list_threshold_is_exactly_three(self):  # kills >= 3 -> >= 4
        s = lambda t: {"s": "---\nname: s\ndescription: d\n---\n" + t}
        three = "Blocking: `ungrounded`, `stale`, `conflict` here.\n"
        two = "Blocking: `ungrounded`, `stale` here.\n"
        self.assertTrue(any("lists the blocking statuses" in e for e in self.errors(self.good(), s(three))))
        self.assertEqual(self.errors(self.good(), s(two)), [])

    def test_unblocked_is_not_a_blocking_word(self):
        line = "Continue with unblocked work: `ungrounded`, `fabricated-citation`, `stale`, `conflict`.\n"
        self.assertEqual(self.errors(self.good(), {"s": "---\nname: s\ndescription: d\n---\n" + line}), [])

    def test_loosened_restatement_patterns(self):
        s = lambda t: {"s": "---\nname: s\ndescription: d\n---\n" + t}
        for text, frag in (("run python scripts/kb/search.py x\n", "CLI fallback"),
                           ("run python3.12 scripts/kb/search.py x\n", None),
                           ("  - NEITHER  WORKS: stop\n", "Neither works"),
                           ("If the KB MCP is unreachable, stop\n", "'rule 7'")):
            e = self.errors(self.good(), s(text))
            if frag is None:
                self.assertEqual(e, [], text)  # python3.12 is not matched: only python / python3
            else:
                self.assertTrue(any(frag in x for x in e), text)

    def test_missing_rule_7(self):
        self.assertTrue(any("rule 7" in e for e in self.errors(self.good(), shared="# Shared\n")))


SLICE_INDEX = """| Id | Slice | Status | Rung |
|----|-------|--------|------|
| VS-001 | A | {s1} | - |
| VS-002 | B | {s2} | - |

```mermaid
graph LR
  VS001["A"] --> VS002["B"]
  classDef inprogress fill:#fff;
  classDef proposed fill:#eef;
  class VS001 {c1};
  class VS002 {c2};
```
"""


class SliceIndexTests(unittest.TestCase):
    def run_index(self, s1="In progress", s2="Analysed", c1="inprogress", c2="proposed", text=None):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = build(tmp / ".claude", {"a": GOOD_AGENT.format(n="a")}, {"s": GOOD_SKILL.format(n="s")})
            (tmp / "docs" / "slices").mkdir(parents=True)
            (tmp / "docs" / "slices" / "INDEX.md").write_text(
                text if text is not None else SLICE_INDEX.format(s1=s1, s2=s2, c1=c1, c2=c2), encoding="utf-8")
            return fl.lint(root).errors

    def test_matching_classes_pass(self):
        self.assertEqual(self.run_index(), [])

    def test_status_change_without_class_change_fails(self):
        errs = self.run_index(s2="In progress")
        self.assertEqual(len(errs), 1)
        self.assertIn("VS-002", errs[0])
        self.assertIn("'inprogress'", errs[0])

    def test_ready_and_proposed_share_a_class(self):
        self.assertEqual(self.run_index(s2="Ready"), [])

    def test_unknown_status_fails(self):
        self.assertTrue(any("unknown Status" in e for e in self.run_index(s1="Started")))

    def test_slice_missing_from_graph_fails(self):
        text = SLICE_INDEX.format(s1="In progress", s2="Analysed", c1="inprogress", c2="proposed").replace(
            '  class VS002 proposed;\n', "").replace('VS002["B"]', "X")
        self.assertTrue(any("no node" in e for e in self.run_index(text=text)))

    def test_missing_class_line_fails(self):
        text = SLICE_INDEX.format(s1="In progress", s2="Analysed", c1="inprogress", c2="proposed").replace(
            "  class VS002 proposed;\n", "")
        self.assertTrue(any("found None" in e for e in self.run_index(text=text)))

    def test_grouped_class_line_is_read(self):
        text = SLICE_INDEX.format(s1="Analysed", s2="Analysed", c1="x", c2="x").replace(
            "  class VS001 x;\n  class VS002 x;\n", "  class VS001,VS002 proposed;\n")
        self.assertEqual(self.run_index(text=text), [])

    def base(self, **kw):
        return SLICE_INDEX.format(**{"s1": "In progress", "s2": "Analysed", "c1": "inprogress", "c2": "proposed", **kw})

    def test_header_is_case_insensitive(self):
        text = self.base().replace("| Id |", "| ID |").replace("| Status |", "| STATUS |")
        self.assertEqual(self.run_index(text=text), [])

    def test_missing_status_column_is_an_error(self):
        text = self.base().replace("| Status ", "| State ")
        self.assertTrue(any("no table header" in e for e in self.run_index(text=text)))

    def test_row_with_wrong_cell_count_is_an_error(self):
        text = self.base().replace("| VS-002 | B | Analysed | - |", "| VS-002 | B | x | Analysed | - |")
        self.assertTrue(any("5 cells" in e for e in self.run_index(text=text)))

    def test_node_openers_round_and_curly(self):
        text = self.base().replace('VS001["A"]', "VS001(A)").replace('VS002["B"]', "VS002{B}")
        self.assertEqual(self.run_index(text=text), [])

    def test_class_line_without_semicolon(self):
        text = self.base().replace("class VS001 inprogress;", "class VS001 inprogress")
        self.assertEqual(self.run_index(text=text), [])

    def test_triple_colon_shorthand(self):
        text = self.base().replace("  class VS001 inprogress;\n", "").replace('VS001["A"]', 'VS001["A"]:::inprogress')
        self.assertEqual(self.run_index(text=text), [])
        wrong = text.replace(":::inprogress", ":::proposed")
        self.assertTrue(any("found 'proposed'" in e for e in self.run_index(text=wrong)))

    def test_done_and_blocked_have_their_own_classes(self):
        self.assertEqual(self.run_index(s1="Done", s2="Blocked", c1="done", c2="blocked"), [])
        self.assertTrue(self.run_index(s1="Done", c1="inprogress"))

    def test_other_tables_with_slice_ids_are_not_status_rows(self):  # kills the table-end reset
        text = self.base() + "\n## Blockers\n\n| Slice | Record |\n|---|---|\n| VS-001 | TQ-001 |\n"
        self.assertEqual(self.run_index(text=text), [])

    def test_triple_colon_does_not_span_nodes(self):  # a label match must stay inside one node
        text = self.base(c2="x").replace("class VS002 x;\n", "").replace("class VS001 inprogress;", "class VS001 inprogress;").replace(
            '--> VS002["B"]', '--> VS002["B"]:::proposed')
        self.assertEqual(self.run_index(text=text), [])
        bad = text.replace(':::proposed', ':::inprogress')
        self.assertTrue(any("VS-002" in e and "found 'inprogress'" in e for e in self.run_index(text=bad)))
        self.assertFalse(any("VS-001" in e for e in self.run_index(text=bad)))

    def test_triple_colon_overrides_a_class_line(self):
        text = self.base().replace('--> VS002["B"]', '--> VS002["B"]:::inprogress')
        self.assertTrue(any("VS-002" in e for e in self.run_index(text=text)))

    def test_class_line_with_trailing_comment(self):
        text = self.base().replace("class VS001 inprogress;", "class VS001 inprogress; %% hand edited")
        self.assertEqual(self.run_index(text=text), [])
        self.assertEqual(self.run_index(text=self.base().replace("class VS001 inprogress;", "class VS001 inprogress %% c")), [])

    def test_triple_colon_after_round_and_curly_nodes(self):
        for opener, closer in (("(", ")"), ("{", "}")):
            text = self.base(c2="x").replace("class VS002 x;\n", "").replace('VS002["B"]', f"VS002{opener}B{closer}:::inprogress")
            self.assertTrue(any("VS-002" in e and "found 'inprogress'" in e for e in self.run_index(text=text)), opener)

    def test_no_index_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(Path(tmp) / ".claude", {"a": GOOD_AGENT.format(n="a")}, {"s": GOOD_SKILL.format(n="s")})
            self.assertEqual(fl.lint(root).errors, [])


if __name__ == "__main__":
    unittest.main()
