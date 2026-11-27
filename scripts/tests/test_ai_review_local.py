"""Tests for scripts/ai_review_local.py. Run: python3 -m unittest discover -s scripts/tests"""
import json
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


class CanonicalNamesTests(unittest.TestCase):
    CANON = {"severity": "High", "category": "c", "file": "a.py", "anchor": "func f", "title": "t",
             "scenario": "input X fails", "fix": "do Y"}

    def test_render_accepts_canonical_finding_names(self):
        text = air.render_markdown([self.CANON], 1, "m", "main")
        self.assertIn("Failing scenario: input X fails", text)
        self.assertIn("Suggestion: do Y", text)
        self.assertIn("`a.py:func f`", text)

    def test_render_still_prefers_contract_names(self):
        f = {**self.CANON, "failing_scenario": "S", "suggestion": "G", "evidence": "E", "line": 7}
        text = air.render_markdown([f], 1, "m", "main")
        self.assertIn("Failing scenario: S", text)
        self.assertIn("Suggestion: G", text)
        self.assertIn("Evidence: E", text)
        self.assertIn("`a.py:7`", text)

    def test_prior_text_adds_contract_names_for_canonical_findings(self):
        shown = json.loads(air._prior_text([self.CANON]))[0]
        self.assertEqual((shown["failing_scenario"], shown["suggestion"]), ("input X fails", "do Y"))


class StateTests(unittest.TestCase):
    def test_corrupt_state_exits_2_and_mentions_reset(self):
        import contextlib
        import io
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "state.json").write_text("{not json", encoding="utf-8")
            err = io.StringIO()
            with mock.patch.object(air, "state_path", return_value=Path(tmp) / "state.json"), contextlib.redirect_stderr(err):
                code = air.main(["--out-dir", tmp, "--base", "HEAD"])
            self.assertEqual(code, 2)
            self.assertIn("--reset", err.getvalue())

    def test_missing_claude_cli_skips_unless_required(self):
        import contextlib
        import io
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(air, "state_path", return_value=Path(tmp) / "state.json"), \
                mock.patch.object(air, "get_diff", return_value="diff --git a/x b/x\n+x\n"), \
                mock.patch.object(air, "current_branch", return_value="t"):
            args = ["--out-dir", tmp, "--claude-bin", "no-such-claude-binary"]
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(air.main(args), 0)
            self.assertIn("skipped", err.getvalue())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(air.main(args + ["--require"]), 2)

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
                        mock.patch.object(air, "state_path", return_value=Path(tmp) / "state.json"), \
                        mock.patch.object(air, "current_branch", return_value=branch), \
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                    self.assertEqual(air.main(args), 0)
                return err.getvalue()

            self.assertIn("round 1/3", run_on("feature/b"))  # a new branch starts fresh
            self.assertIn("round 4/3", run_on("feature/a"))  # feature/a keeps its own count

    def test_default_round_cap_is_five(self):
        import contextlib
        import io
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            args = ["--out-dir", tmp, "--base", "origin/main", "--dry-run"]  # no --max-rounds: the default applies
            err = io.StringIO()
            with mock.patch.object(air, "get_diff", return_value=make_diff("a.cs", ["x"])), \
                    mock.patch.object(air, "state_path", return_value=Path(tmp) / "state.json"), \
                    mock.patch.object(air, "current_branch", return_value="feature/c"), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                self.assertEqual(air.main(args), 0)
            self.assertIn("round 1/5", err.getvalue())


class OptionTests(unittest.TestCase):
    def test_abbreviated_options_are_rejected_with_exit_2(self):
        # `--res` must not act as `--reset`, `--max-r 99` as `--max-rounds`, `--cl x` as `--claude-bin`: the ask rules in
        # .claude/settings.json match the full spelling only.
        import contextlib
        import io
        for args in (["--res"], ["--max-r", "99"], ["--cl", "x"], ["--out", "d"], ["--max-rounds=2", "--res"]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as raised:
                    air.main([*args, "--dry-run"])
                self.assertEqual(raised.exception.code, 2)
                self.assertIn("unrecognized arguments", err.getvalue())

    def test_the_full_spellings_are_still_accepted(self):
        import contextlib
        import io
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(air, "state_path", return_value=Path(tmp) / "state.json"), \
                mock.patch.object(air, "get_diff", return_value=""), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(air.main(["--reset", "--max-rounds", "9", "--out-dir", tmp, "--claude-bin", "x"]), 0)


class SeverityMappingTests(unittest.TestCase):
    def test_each_mapping(self):
        import contextlib
        import io
        cases = {"blocking": "blocking", "warning": "warning", "info": "info", "Critical": "blocking",
                 "HIGH": "blocking", "high": "blocking", "Blocker": "blocking", "blocker": "blocking",
                 "Medium": "warning", "Low": "info", "low": "info"}
        for raw, want in cases.items():
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(air.normalize_severity(raw), want, raw)
            self.assertEqual(err.getvalue(), "", raw)  # known names print no notice

    def test_unknown_severity_is_warning_with_notice(self):
        import contextlib
        import io
        for raw in ("Major", "", None, 3):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(air.normalize_severity(raw), "warning")
            self.assertIn("unknown severity", err.getvalue())

    def test_severity_is_stripped(self):
        self.assertEqual(air.normalize_severity(" High "), "blocking")
        self.assertEqual(air.normalize_severity("\tlow\n"), "info")

    def exit_code(self, severity: str) -> int:
        import contextlib
        import io
        import tempfile
        from unittest import mock
        reply = json.dumps({"findings": [{"severity": severity, "file": "a.py", "line": 1, "title": "t",
                                          "scenario": "s", "fix": "f"}]})
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(air, "state_path", return_value=Path(tmp) / "state.json"), \
                mock.patch.object(air, "get_diff", return_value=make_diff("a.py", ["x"])), \
                mock.patch.object(air, "current_branch", return_value="t"), \
                mock.patch.object(air.shutil, "which", return_value="/bin/claude"), \
                mock.patch.object(air, "call_model", return_value=reply), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return air.main(["--out-dir", tmp, "--base", "origin/main"])

    def test_canonical_high_and_critical_fail_the_gate(self):
        self.assertEqual(self.exit_code("High"), 1)
        self.assertEqual(self.exit_code("Critical"), 1)

    def test_medium_low_and_info_do_not_fail_the_gate(self):
        for sev in ("Medium", "Low", "Info", "warning"):
            self.assertEqual(self.exit_code(sev), 0, sev)


class MergeTests(unittest.TestCase):
    def test_canonical_findings_with_different_anchors_are_not_collapsed(self):
        a = {"severity": "warning", "file": "a.py", "anchor": "func f", "scenario": "s1", "fix": "x"}
        b = {"severity": "warning", "file": "a.py", "anchor": "func g", "scenario": "s2", "fix": "y"}
        self.assertEqual(len(air.merge([a, b])), 2)
        c = {"severity": "warning", "file": "a.py", "anchor": "func f", "scenario": "s1"}
        d = {**c, "severity": "blocking"}
        merged = air.merge([c, dict(c), d])
        self.assertEqual([f["severity"] for f in merged], ["blocking"])

    def test_merge_keeps_most_severe_duplicate(self):
        merged = air.merge([
            {"file": "a", "line": 1, "title": "t", "severity": "warning"},
            {"file": "a", "line": 1, "title": "t", "severity": "blocking"},
        ])
        self.assertEqual([f["severity"] for f in merged], ["blocking"])


class ReadOnlyReviewerTests(unittest.TestCase):
    def call(self) -> dict:
        from unittest import mock
        seen = {}

        def fake_run(cmd, **kw):
            seen.update(cmd=cmd, **kw)
            return mock.Mock(returncode=0, stdout="{}", stderr="")

        with mock.patch.object(air, "run", side_effect=fake_run):
            air.call_model("prompt", "sonnet", "claude", 5)
        return seen

    def built_command(self) -> list[str]:
        return self.call()["cmd"]

    def flag_value(self, cmd: list[str], flag: str) -> set[str]:
        return set(cmd[cmd.index(flag) + 1].replace(" ", ",").split(","))

    def test_command_restricts_tools_not_only_preapproves(self):
        cmd = self.built_command()
        self.assertEqual(self.flag_value(cmd, "--tools"), {"Read", "Grep", "Glob"})
        self.assertEqual(self.flag_value(cmd, "--allowedTools"), {"Read", "Grep", "Glob"})

    def test_command_denies_shell_write_and_every_mcp_tool_and_skips_configured_mcp_servers(self):
        cmd = self.built_command()
        self.assertLessEqual({"Bash", "Edit", "Write", "mcp__*"}, self.flag_value(cmd, "--disallowedTools"))
        self.assertIn("--strict-mcp-config", cmd)
        self.assertNotIn("--mcp-config", cmd)

    def test_claude_ai_connectors_are_switched_off_and_the_rest_of_the_environment_is_kept(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"KEEP_ME": "1"}):
            env = self.call()["env"]
        self.assertEqual(env["ENABLE_CLAUDEAI_MCP_SERVERS"], "false")
        self.assertEqual(env["KEEP_ME"], "1")
        self.assertIn("PATH", env)

    def test_file_reads_outside_the_working_directories_are_blocked(self):
        cmd = self.built_command()
        settings = json.loads(cmd[cmd.index("--settings") + 1])
        self.assertIs(settings["permissions"]["blockReadsOutsideWorkingDirectories"], True)


class ReviewerPromptsFromBaseTests(unittest.TestCase):
    """The reviewer role prompts and root rules come from the base revision (the working tree and the files the reviewer
    Reads are still the branch's, see the module docstring)."""
    GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]

    def make_repo(self, tmp: str) -> tuple[Path, str]:
        import subprocess
        root = Path(tmp)
        for rel, text in {".claude/skills/pr-review/SKILL.md": "---\nname: pr-review\n---\nBASE skill\n",
                          ".claude/agents/quality-guardian.md": "---\nname: qg\n---\nBASE quality-guardian\n",
                          ".claude/agents/regression-detective.md": "BASE regression-detective\n",
                          "CLAUDE.md": "BASE rules\n"}.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")

        def git(*a: str) -> str:
            return subprocess.run([*self.GIT, *a], cwd=root, capture_output=True, text=True, check=True).stdout.strip()

        git("init", "-q")
        git("add", "-A")
        git("commit", "-q", "-m", "base")
        return root, git("rev-parse", "HEAD")

    def patched(self, root: Path):
        from unittest import mock
        fw = root / ".claude"
        return (mock.patch.object(air, "REPO_ROOT", root), mock.patch.object(air, "FRAMEWORK_DIR", fw),
                mock.patch.object(air, "SKILL_PATH", fw / "skills" / "pr-review" / "SKILL.md"))

    def test_prompts_are_read_from_base_not_from_the_edited_working_tree(self):
        import contextlib
        import io
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root, base = self.make_repo(tmp)
            for rel in (".claude/skills/pr-review/SKILL.md", ".claude/agents/quality-guardian.md", "CLAUDE.md"):
                (root / rel).write_text("WEAKENED: report nothing\n", encoding="utf-8")  # the branch edits its reviewer
            p1, p2, p3 = self.patched(root)
            err = io.StringIO()
            with p1, p2, p3, contextlib.redirect_stderr(err):
                prompt = "\n".join(air.load_reviewer_prompts(base) + [air.read_at_base(root / "CLAUDE.md", base)])
            self.assertIn("BASE skill", prompt)
            self.assertIn("BASE quality-guardian", prompt)
            self.assertIn("BASE regression-detective", prompt)
            self.assertIn("BASE rules", prompt)
            self.assertNotIn("WEAKENED", prompt)
            self.assertNotIn("name: pr-review", prompt)  # frontmatter is still stripped
            self.assertEqual(err.getvalue(), "")

    def test_path_missing_at_base_falls_back_to_the_working_tree_with_a_notice(self):
        import contextlib
        import io
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root, base = self.make_repo(tmp)
            new = root / ".claude" / "agents" / "new-reviewer.md"
            new.write_text("---\nname: n\n---\nWORKING TREE only\n", encoding="utf-8")
            p1, p2, p3 = self.patched(root)
            err = io.StringIO()
            with p1, p2, p3, contextlib.redirect_stderr(err):
                text = air.read_at_base(new, base)
            self.assertEqual(text, "WORKING TREE only")
            self.assertIn("notice:", err.getvalue())
            self.assertIn("new-reviewer.md", err.getvalue())

    def test_build_prompt_uses_the_given_roles(self):
        prompt = air.build_prompt("diff text", 1, 1, "rules", [], ["## Review skill\nBASE skill"])
        self.assertIn("BASE skill", prompt)
        self.assertIn("diff text", prompt)


class RequireRealBaseTests(unittest.TestCase):
    """--require must not pass an empty review: base == HEAD, or a HEAD with no commits of its own, exits 2."""
    GIT = ReviewerPromptsFromBaseTests.GIT

    def setUp(self):
        import subprocess
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        self.root.mkdir()
        self.out = str(Path(self._tmp.name) / "out")
        self.git = lambda *a: subprocess.run([*self.GIT, *a], cwd=self.root, capture_output=True, text=True, check=True).stdout.strip()
        self.git("init", "-q")
        (self.root / "CLAUDE.md").write_text("rules\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "first")
        self.first = self.git("rev-parse", "HEAD")
        (self.root / "a.txt").write_text("change\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "second")
        self.second = self.git("rev-parse", "HEAD")

    def main_code(self, *args: str) -> tuple[int, str, str]:
        import contextlib
        import io
        from unittest import mock
        fw = self.root / ".claude"
        with mock.patch.object(air, "REPO_ROOT", self.root), mock.patch.object(air, "FRAMEWORK_DIR", fw), \
                mock.patch.object(air, "SKILL_PATH", fw / "skills" / "pr-review" / "SKILL.md"), \
                contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()) as out:
            code = air.main(["--out-dir", self.out, "--claude-bin", "no-such-claude-bin-xyz", *args])
        return code, out.getvalue(), err.getvalue()

    def test_base_equal_to_head_exits_2_under_require(self):
        code, _, err = self.main_code("--base", "HEAD", "--require")
        self.assertEqual(code, 2)
        self.assertIn("same commit as HEAD", err)

    def test_base_equal_to_head_by_sha_or_branch_name_exits_2_under_require(self):
        for base in (self.second, self.git("rev-parse", "--abbrev-ref", "HEAD")):
            with self.subTest(base=base):
                self.assertEqual(self.main_code("--base", base, "--require")[0], 2)

    def test_base_equal_to_head_without_require_keeps_exiting_0(self):
        code, out, _ = self.main_code("--base", "HEAD")
        self.assertEqual(code, 0)
        self.assertIn("nothing to review", out)

    def test_head_behind_base_exits_2_under_require(self):
        self.git("checkout", "-q", "--detach", self.first)  # HEAD is behind the base: the diff is empty, not a review
        code, _, err = self.main_code("--base", self.second, "--require")
        self.assertEqual(code, 2)
        self.assertIn("no commits that base", err)
        self.assertEqual(self.main_code("--base", self.second)[0], 0)  # without --require: today's behaviour

    def test_base_that_moved_on_after_the_branch_point_passes_the_check(self):
        # The normal team flow: main gains a commit after the branch is cut; base...HEAD is still this branch's work.
        self.git("checkout", "-q", "-b", "feat", self.first)
        (self.root / "b.txt").write_text("feature\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "feature")
        code, _, err = self.main_code("--base", self.second, "--require", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertNotIn("no commits that base", err)

    def test_unresolvable_base_exits_2_under_require(self):
        self.assertEqual(self.main_code("--base", "no-such-ref-xyz", "--require")[0], 2)

    def test_real_base_passes_the_check_and_reaches_the_next_step(self):
        code, _, err = self.main_code("--base", self.first, "--require")
        self.assertEqual(code, 2)  # stopped later, by the missing claude binary, not by the base check
        self.assertIn("not found on PATH", err)
        self.assertNotIn("same commit", err)
        self.assertEqual(self.main_code("--base", self.first, "--require", "--dry-run")[0], 0)


class AnchoredBaseTests(unittest.TestCase):
    """--require with a remote configured: the base must be anchored to shared history, so `--base HEAD~1` (a producer
    narrowing the review to the last commit, with the reviewer prompts read from a branch commit) is rejected."""
    GIT = ReviewerPromptsFromBaseTests.GIT
    main_code = RequireRealBaseTests.main_code

    def commit(self, name: str, text: str = "x\n") -> str:
        (self.root / name).parent.mkdir(parents=True, exist_ok=True)
        (self.root / name).write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", name)
        return self.git("rev-parse", "HEAD")

    def setUp(self):
        import subprocess
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        self.root, self.remote, self.out = tmp / "repo", tmp / "remote.git", str(tmp / "out")
        self.root.mkdir()
        self.git = lambda *a: subprocess.run([*self.GIT, *a], cwd=self.root, capture_output=True, text=True, check=True).stdout.strip()
        self.git("init", "-q", "-b", "main")
        self.commit(".claude/skills/pr-review/SKILL.md", "SKILL v1\n")
        self.commit("a.txt")
        self.fork = self.git("rev-parse", "HEAD")

    def with_remote(self):
        """A bare remote holding main, so that origin/main exists as a remote-tracking ref."""
        import subprocess
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True, capture_output=True)
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "-q", "origin", "main")

    def feature_branch(self, push: bool = False):
        self.git("checkout", "-q", "-b", "feat")
        self.commit("f1.txt")
        self.commit("f2.txt")
        if push:
            self.git("push", "-q", "origin", "feat")

    def test_head_minus_one_is_rejected_when_a_remote_exists_even_after_the_branch_is_pushed(self):
        self.with_remote()
        self.set_head()
        self.feature_branch(push=True)  # origin/feat now contains HEAD~1
        code, _, err = self.main_code("--base", "HEAD~1", "--require", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("not anchored to shared history", err)

    def test_head_minus_one_is_rejected_before_the_branch_is_pushed(self):
        self.with_remote()
        self.feature_branch()
        self.assertEqual(self.main_code("--base", "HEAD~1", "--require", "--dry-run")[0], 2)

    def test_the_branchs_own_remote_counterpart_is_rejected_as_a_base(self):
        self.with_remote()
        self.set_head()
        self.feature_branch(push=True)
        self.commit("f3.txt")
        code, _, err = self.main_code("--base", "origin/feat", "--require", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("not anchored", err)

    def test_origin_main_is_accepted(self):
        self.with_remote()
        self.set_head()
        self.feature_branch(push=True)
        code, _, err = self.main_code("--base", "origin/main", "--require", "--dry-run")
        self.assertEqual(code, 0, err)

    def test_a_remote_without_origin_head_is_refused_with_the_set_head_hint_whatever_the_base(self):
        # No symbolic fallback: without refs/remotes/origin/HEAD the integration branch is unknown, so nothing anchors.
        self.with_remote()
        self.feature_branch()
        for base in ("main", "origin/main"):
            with self.subTest(base=base):
                code, _, err = self.main_code("--base", base, "--require", "--dry-run")
                self.assertEqual(code, 2)
                self.assertIn("git remote set-head origin -a", err)
                self.assertIn("git remote set-head origin <integration-branch>", err)

    def test_a_pushed_parent_branch_is_refused_without_origin_head(self):
        self.with_remote()
        self.feature_branch(push=True)
        self.git("checkout", "-q", "-b", "feat2")
        self.commit("g1.txt")
        code, _, err = self.main_code("--base", "origin/feat", "--require", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("set-head", err)

    def test_a_branch_pushed_to_a_temporary_name_cannot_anchor_head_minus_one(self):
        self.with_remote()
        self.set_head()
        self.feature_branch()
        self.git("push", "-q", "origin", "HEAD~1:refs/heads/tmp")
        self.assertEqual(self.git("rev-parse", "origin/tmp"), self.git("rev-parse", "HEAD~1"))
        code, _, err = self.main_code("--base", "origin/tmp", "--require", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("not anchored", err)

    def test_set_head_to_the_branchs_own_remote_counterpart_cannot_re_anchor_the_review(self):
        self.with_remote()
        self.feature_branch(push=True)
        self.git("remote", "set-head", "origin", "feat")  # refs/remotes/origin/HEAD -> origin/feat
        self.assertEqual(self.git("symbolic-ref", "--short", "refs/remotes/origin/HEAD"), "origin/feat")
        self.commit("f3.txt")  # HEAD is one commit ahead of origin/feat, so without the check `origin/feat` and HEAD~1 would anchor
        for base in ("HEAD~1", "origin/feat"):
            with self.subTest(base=base):
                code, _, err = self.main_code("--base", base, "--require", "--dry-run")
                self.assertEqual(code, 2)
                self.assertIn("not anchored", err)
                self.assertIn("own remote counterpart", err)

    def test_a_branch_made_with_switch_from_origin_main_is_accepted_when_origin_head_is_set(self):
        # `git switch -c x origin/main` sets the upstream to origin/main: it must not count as the branch's own ref.
        self.with_remote()
        self.set_head()
        self.git("switch", "-q", "-c", "x", "origin/main")
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "@{upstream}"), "origin/main")
        self.commit("x1.txt")
        code, _, err = self.main_code("--base", "origin/main", "--require", "--dry-run")
        self.assertEqual(code, 0, err)

    def test_a_normal_clone_with_a_moved_remote_is_accepted(self):
        import subprocess
        self.with_remote()
        subprocess.run(["git", "--git-dir", str(self.remote), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)  # like a hosted remote
        clone = Path(self._tmp.name) / "clone"
        subprocess.run(["git", "clone", "-q", "-b", "main", str(self.remote), str(clone)], check=True, capture_output=True)
        self.root = clone  # as a developer's own clone
        self.assertEqual(self.git("symbolic-ref", "--short", "refs/remotes/origin/HEAD"), "origin/main")  # set by `git clone`
        self.git("switch", "-q", "-c", "feat")
        self.commit("f1.txt")
        other = Path(self._tmp.name) / "other"
        subprocess.run(["git", "clone", "-q", "-b", "main", str(self.remote), str(other)], check=True, capture_output=True)
        self.root = other
        self.commit("m1.txt")
        self.git("push", "-q", "origin", "main")  # main moved on after feat was cut
        self.root = clone
        self.git("fetch", "-q", "origin")
        code, _, err = self.main_code("--base", "origin/main", "--require", "--dry-run")
        self.assertEqual(code, 0, err)

    def test_a_linked_worktree_is_accepted(self):
        self.with_remote()
        self.set_head()
        tree = Path(self._tmp.name) / "tree"
        self.git("worktree", "add", "-q", "-b", "wt", str(tree))
        self.root = tree
        self.commit("w1.txt")
        code, _, err = self.main_code("--base", "origin/main", "--require", "--dry-run")
        self.assertEqual(code, 0, err)

    def test_a_diverged_base_is_accepted(self):
        self.with_remote()
        self.set_head()
        self.feature_branch()
        self.git("checkout", "-q", "main")
        self.commit("m1.txt")
        self.git("push", "-q", "origin", "main")  # main moved on after feat was cut
        self.git("checkout", "-q", "feat")
        code, _, err = self.main_code("--base", "origin/main", "--require", "--dry-run")
        self.assertEqual(code, 0, err)

    def set_head(self):
        self.git("remote", "set-head", "origin", "main")  # refs/remotes/origin/HEAD, as every clone has it

    def test_a_detached_head_is_rejected_under_require(self):
        self.with_remote()
        self.set_head()
        self.feature_branch()
        self.git("checkout", "-q", "--detach")
        code, _, err = self.main_code("--base", "origin/main", "--require", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("detached", err)
        self.assertEqual(self.main_code("--base", "origin/main", "--dry-run")[0], 0)  # without --require: today's behaviour

    def test_a_branch_pushed_under_another_name_cannot_anchor_head_minus_one_when_origin_head_is_set(self):
        self.with_remote()
        self.set_head()
        self.feature_branch()
        self.git("push", "-q", "origin", "HEAD:refs/heads/feature/other")  # origin/feature/other now contains HEAD~1
        code, _, err = self.main_code("--base", "HEAD~1", "--require", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("not anchored", err)

    def test_a_branch_pushed_with_a_different_upstream_name_cannot_anchor_itself(self):
        self.with_remote()
        self.set_head()
        self.feature_branch()
        self.git("push", "-q", "-u", "origin", "HEAD:refs/heads/feature/other")  # upstream is origin/feature/other, not origin/feat
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "@{upstream}"), "origin/feature/other")
        code, _, err = self.main_code("--base", "HEAD~1", "--require", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("not anchored", err)

    def test_the_integration_branch_is_accepted_when_origin_head_is_set(self):
        self.with_remote()
        self.set_head()
        self.feature_branch(push=True)
        for base in ("origin/main", "main"):
            with self.subTest(base=base):
                code, _, err = self.main_code("--base", base, "--require", "--dry-run")
                self.assertEqual(code, 0, err)

    def test_a_diverged_base_is_accepted_when_origin_head_is_set(self):
        self.with_remote()
        self.set_head()
        self.feature_branch()
        self.git("checkout", "-q", "main")
        self.commit("m1.txt")
        self.git("push", "-q", "origin", "main")  # main moved on after feat was cut
        self.git("checkout", "-q", "feat")
        for base in ("origin/main", "main"):
            with self.subTest(base=base):
                code, _, err = self.main_code("--base", base, "--require", "--dry-run")
                self.assertEqual(code, 0, err)

    def test_a_branch_of_a_branch_is_rejected_when_origin_head_is_set(self):
        # feat2 is cut from feat, which is not on the integration branch: base `feat` would review only feat2's own commits.
        self.with_remote()
        self.set_head()
        self.feature_branch(push=True)
        self.git("checkout", "-q", "-b", "feat2")
        self.commit("g1.txt")
        self.assertEqual(self.main_code("--base", "feat", "--require", "--dry-run")[0], 2)
        self.assertEqual(self.main_code("--base", "origin/main", "--require", "--dry-run")[0], 0)

    def revert_branch(self):
        """main gains m1.txt (pushed); feat is cut from it, deletes m1.txt again and adds f1.txt."""
        self.with_remote()
        self.commit("m1.txt", "main change\n")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "-b", "feat")
        self.git("rm", "-q", "m1.txt")
        self.git("commit", "-q", "-m", "revert m1")
        self.commit("f1.txt")

    def test_an_older_ancestor_of_the_integration_branch_is_refused_whatever_origin_head_says(self):
        # origin/main~1 is contained in origin/main, but its diff would hide a commit of main that the branch reverts.
        for with_head in (True, False):
            with self.subTest(origin_head=with_head):
                self.setUp()
                self.revert_branch()
                if with_head:
                    self.set_head()
                for base in ("origin/main~1", "origin/main^", self.fork):
                    code, _, err = self.main_code("--base", base, "--require", "--dry-run")
                    self.assertEqual(code, 2, (base, err))
                    self.assertIn("not anchored" if with_head else "set-head", err)

    def test_the_integration_branch_shows_the_commit_the_branch_reverts_in_the_diff(self):
        self.revert_branch()
        self.set_head()
        code, out, err = self.main_code("--base", "origin/main", "--require", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn("diff --git a/m1.txt b/m1.txt", out)
        self.assertIn("deleted file mode", out)

    def test_the_error_names_the_integration_branch_and_how_to_change_the_default(self):
        self.with_remote()
        self.set_head()
        self.feature_branch()
        _, _, err = self.main_code("--base", "HEAD~1", "--require", "--dry-run")
        for text in ("integration branch", "origin/main", "stacked branch", "git remote set-head <remote> <branch>"):
            self.assertIn(text, err)

    def test_help_and_module_docstring_state_the_integration_branch_rule_and_the_branch_name_limit(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            air.main(["--help"])
        help_text = " ".join(out.getvalue().split())
        for text in ("integration branch the remote's HEAD points at", "origin/main", "stacked branch", "git remote set-head <remote> <branch>"):
            self.assertIn(text, help_text)
        doc = " ".join(air.__doc__.split())
        for text in ("must exist", "git remote set-head <remote> -a", "own remote counterpart", "There is no fallback", "detached HEAD is refused too"):
            self.assertIn(text, doc)
        self.assertIn("own remote counterpart", help_text)
        for text in (help_text, doc):
            self.assertIn("only for a non-default integration branch, never this branch or its parent", text)
        self.assertNotIn("changes the default", help_text + doc)
        self.assertIn("keyed by branch name", doc)
        self.assertIn("renaming or copying the branch", doc)
        self.assertNotIn("only --reset", doc)

    def test_a_remote_without_fetched_branches_cannot_anchor_a_base(self):
        import subprocess
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True, capture_output=True)
        self.git("remote", "add", "origin", str(self.remote))  # never pushed or fetched: no remote-tracking refs
        self.feature_branch()
        self.assertEqual(self.main_code("--base", "main", "--require", "--dry-run")[0], 2)

    def test_without_any_remote_the_old_behaviour_stays_with_a_notice(self):
        self.feature_branch()
        code, _, err = self.main_code("--base", "HEAD~1", "--require", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn("no git remote is configured", err)

    def test_without_require_the_base_is_not_checked_against_the_remote(self):
        self.with_remote()
        self.feature_branch()
        self.assertEqual(self.main_code("--base", "HEAD~1", "--dry-run")[0], 0)

    def test_prompts_are_read_at_the_merge_base_not_at_a_base_that_moved_on(self):
        self.with_remote()
        self.feature_branch()
        self.git("checkout", "-q", "main")
        self.commit(".claude/skills/pr-review/SKILL.md", "SKILL v2 moved on\n")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "feat")
        import contextlib
        import io
        from unittest import mock
        fw = self.root / ".claude"
        out = io.StringIO()
        with mock.patch.object(air, "REPO_ROOT", self.root), mock.patch.object(air, "FRAMEWORK_DIR", fw), \
                mock.patch.object(air, "SKILL_PATH", fw / "skills" / "pr-review" / "SKILL.md"), \
                contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(out):
            self.assertEqual(air.main(["--out-dir", self.out, "--base", "origin/main", "--dry-run"]), 0)
            self.assertEqual(air.review_revision("origin/main"), self.fork)
        self.assertIn("SKILL v1", out.getvalue())
        self.assertNotIn("moved on", out.getvalue())


class StateLocationTests(unittest.TestCase):
    """The round state is `<repo>/.ai-review/state.json` whatever --out-dir says, so a new --out-dir cannot reset the cap (OD-031)."""
    GIT = ReviewerPromptsFromBaseTests.GIT
    main_code = RequireRealBaseTests.main_code
    setUp = RequireRealBaseTests.setUp

    def branch(self) -> str:
        return self.git("rev-parse", "--abbrev-ref", "HEAD")

    def write_state(self, rounds: int) -> Path:
        path = self.root / ".ai-review" / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"branches": {self.branch(): {"rounds": rounds, "findings": []}}}), encoding="utf-8")
        return path

    def test_a_new_out_dir_does_not_reset_the_round_cap(self):
        self.write_state(rounds=5)
        for out in (str(Path(self._tmp.name) / "fresh"), "elsewhere", "."):
            with self.subTest(out_dir=out):
                code, stdout, _ = self.main_code("--base", self.first, "--out-dir", out)
                self.assertEqual(code, 3)
                self.assertIn("Round cap 5 reached", stdout)

    def test_the_state_is_written_to_the_fixed_path_and_findings_to_out_dir(self):
        from unittest import mock
        with mock.patch.object(air, "call_model", return_value='{"findings": []}'), \
                mock.patch.object(air.shutil, "which", return_value="/bin/claude"):
            code, _, err = self.main_code("--base", self.first)
        self.assertEqual(code, 0, err)
        state = json.loads((self.root / ".ai-review" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["branches"][self.branch()]["rounds"], 1)
        self.assertTrue((Path(self.out) / "findings.json").exists())
        self.assertFalse((Path(self.out) / "state.json").exists())

    def test_reset_drops_the_fixed_state_whatever_out_dir_is(self):
        from unittest import mock
        path = self.write_state(rounds=5)
        with mock.patch.object(air, "call_model", return_value='{"findings": []}'), \
                mock.patch.object(air.shutil, "which", return_value="/bin/claude"):
            code, _, err = self.main_code("--base", self.first, "--reset")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["branches"][self.branch()]["rounds"], 1)


class ExtractJsonObjectTests(unittest.TestCase):
    def test_empty_example_before_real_findings_does_not_mask_them(self):
        text = ('An empty result looks like {"findings": []}. Actual: '
                '{"findings":[{"severity":"critical","file":"a.py","line":1,"title":"t"}]}')
        out = air.parse_findings(text)
        self.assertEqual([f["severity"] for f in out], ["blocking"])

    def test_empty_object_after_real_findings_does_not_mask_them_either(self):
        text = '{"findings":[{"severity":"high","title":"t"}]} (a clean chunk would be {"findings": []})'
        self.assertEqual(len(air.parse_findings(text)), 1)

    def test_several_non_empty_candidates_are_all_kept_without_duplicates(self):
        a, b = '{"severity":"low","title":"a"}', '{"severity":"low","title":"b"}'
        out = air.parse_findings(f'{{"findings":[{a}]}} then {{"findings":[{a},{b}]}}')
        self.assertEqual([f["title"] for f in out], ["a", "b"])

    def test_several_candidates_all_empty_is_clean(self):
        self.assertEqual(air.parse_findings('{"findings": []} and again {"findings": []}'), [])


class EnvironmentErrorTests(unittest.TestCase):
    def main_code(self, *args: str) -> tuple[int, str]:
        import contextlib
        import io
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as err, \
                contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(air, "state_path", lambda: Path(tmp) / "state.json"):  # never read the real .ai-review/state.json
            code = air.main(["--out-dir", tmp, *args])
        return code, err.getvalue()

    def test_unknown_base_exits_2_with_a_message(self):
        code, err = self.main_code("--base", "origin/no-such-branch-xyz")
        self.assertEqual(code, 2)
        self.assertIn("git diff failed", err)

    def test_option_like_base_is_rejected_and_writes_nothing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "injected.txt"
            code, err = self.main_code(f"--base=--output={target}")
            self.assertEqual(code, 2)
            self.assertIn("must not start with '-'", err)
            self.assertFalse(target.exists())

    def test_non_utf8_bytes_in_command_output_are_replaced_not_fatal(self):
        proc = air.run([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'ok \\xff\\xfe end')"])
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(proc.stdout.startswith("ok ") and proc.stdout.endswith(" end"))

    def test_non_scalar_file_line_and_title_do_not_crash_parse_or_merge(self):
        text = json.dumps({"findings": [
            {"severity": "low", "file": {"p": "a.py"}, "line": [3, 4], "title": ["t"]},
            {"severity": "high", "file": {"p": "a.py"}, "line": [3, 4], "title": ["t"]},
            {"severity": "low", "file": "b.py", "line": 7, "title": "u"}]})
        merged = air.merge(air.parse_findings(text))
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["severity"], "blocking")  # duplicates collapse, most severe wins
        self.assertIsInstance(merged[0]["line"], str)
        self.assertIn("a.py", air.render_markdown(merged, 1, "m", "main"))

    def test_merge_alone_tolerates_unhashable_values(self):
        self.assertEqual(len(air.merge([{"severity": "info", "file": ["x"], "line": {"a": 1}, "title": [1]}])), 1)


if __name__ == "__main__":
    unittest.main()
