"""Regression test: every Bash allow rule in .claude/settings.json that can run repository code must be matched by a deny
entry of the CI reviewer (`--disallowedTools` in .github/workflows/ai-pr-review.yml).

Why: the reviewer job loads the base settings.json, so its allow rules apply; a deny rule wins over an allow rule, but only
when its text matches the command. A new allow rule such as `Bash(scripts/run-mutation-tests.sh:*)` without a matching deny
would let a prompt-injected diff run code from the checked-out PR.

Matching follows https://code.claude.com/docs/en/permissions and the Claude Code source: ANY rule ending in `:*` is a prefix
rule (regex `^(.+):[*]$`), even when an earlier `*` is present (that earlier part is then literal, so such a rule never matches as
intended and is forbidden in settings); `Bash(X *)` with no other `*` matches the command X or a command starting with `X `; any
other rule with `*` is a glob where `*` matches any characters (so a rule ending in `**`, such as `git checkout -- **`, is a glob,
never a prefix rule); otherwise an exact match.
Edit and Write rules are gitignore patterns relative to the working directory (`./path`); `path_rule_matches` mirrors that.
Run: python3 -m unittest discover -s scripts/tests"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / ".claude" / "settings.json"
WORKFLOW = ROOT / ".github" / "workflows" / "ai-pr-review.yml"

# Allow rules that only read: the command text starts with one of these, so no deny entry is needed.
# git is NOT read-only: `git log|diff|show --output=<path>` writes any file (e.g. .git/config with core.fsmonitor, which
# the next `git status` executes), so every allow-listed git rule must be denied for the CI reviewer too.
READ_ONLY_PREFIXES = ("ls", "pwd")
READ_ONLY_GH = re.compile(r"^gh [a-z-]+ (view|list|diff|checks)$")

RULE = re.compile(r"^Bash\((.*)\)$")


def bash_pattern(rule: str) -> str | None:
    """The inner text of a `Bash(...)` rule, else None (Read, Edit, mcp__..., Agent(...) rules)."""
    match = RULE.match(rule.strip())
    return match.group(1) if match else None


def path_rule_matches(pattern: str, path: str) -> bool:
    """Does the path part of an `Edit(...)`/`Write(...)` rule match `path` (relative to the working directory)?

    gitignore syntax (https://code.claude.com/docs/en/permissions, "How path patterns match"): `./` anchors at the working
    directory; `*` and `?` stay inside one path segment; `**/` matches zero or more directories, so `./**/x` also matches a
    root-level `x`; a bare name (no slash) matches at any depth. Only the forms the settings use are handled (no `[]`, no `!`)."""
    anchored = pattern.startswith("./")
    pattern = pattern[2:] if anchored else pattern
    anchored = anchored or "/" in pattern.rstrip("/")
    regex, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            regex += "(?:.*/)?"
            i += 3
        elif pattern.startswith("/**", i) and i + 3 == len(pattern):
            regex += "/.*"
            i += 3
        elif pattern[i] == "*":
            regex += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            regex += "[^/]"
            i += 1
        else:
            regex += re.escape(pattern[i])
            i += 1
    return re.fullmatch(regex if anchored else f"(?:.*/)?{regex}", path) is not None


def representative_command(pattern: str) -> str:
    """A command the allow pattern matches: `X:*` and `X *` -> `X --x`, other `*` -> `x`, exact -> itself."""
    if pattern.endswith(":*"):
        return pattern[:-2] + " --x"
    if pattern.endswith(" *"):
        return pattern[:-2] + " --x"
    return pattern.replace("*", "x")


def pattern_matches(pattern: str, command: str) -> bool:
    if pattern.endswith("**"):  # a glob (`*` matches any characters, also none), never a prefix rule: `dotnet * --p:**`, `git push * :**`
        return re.fullmatch(".*".join(re.escape(part) for part in pattern.split("*")), command, re.DOTALL) is not None
    # Claude Code reads any rule ending in `:*` as a prefix rule (regex `^(.+):[*]$`), so `dotnet * -p:*` means the literal prefix
    # `dotnet * -p` and never matches `dotnet build -p:X=1`.
    if pattern.endswith(":*"):
        prefix = pattern[:-2]
        return command == prefix or command.startswith(prefix + " ")
    if pattern.endswith(" *") and "*" not in pattern[:-2]:
        prefix = pattern[:-2]
        return command == prefix or command.startswith(prefix + " ")
    if "*" in pattern:
        return re.fullmatch(".*".join(re.escape(part) for part in pattern.split("*")), command, re.DOTALL) is not None
    return command == pattern


def is_read_only(pattern: str) -> bool:
    prefix = pattern[:-2] if pattern.endswith(":*") else pattern
    if READ_ONLY_GH.match(prefix):
        return True
    return any(prefix == p or prefix.startswith(p + " ") for p in READ_ONLY_PREFIXES)


def deny_patterns(workflow_text: str) -> list[str]:
    """The `Bash(...)` entries of the --disallowedTools string in claude_args."""
    found = re.search(r'--disallowedTools\s+"([^"]*)"', workflow_text)
    if not found:
        raise AssertionError("no --disallowedTools string found in the workflow")
    return [m.group(1) for m in re.finditer(r"Bash\(([^)]*)\)", found.group(1))]


def allow_patterns(settings_text: str) -> list[str]:
    allow = json.loads(settings_text)["permissions"]["allow"]
    return [p for p in map(bash_pattern, allow) if p is not None]


def uncovered(allow: list[str], deny: list[str]) -> list[str]:
    """Allow patterns that can run repository code and that no deny entry matches for a representative command."""
    missing = []
    for pattern in allow:
        if is_read_only(pattern):
            continue
        command = representative_command(pattern)
        if not any(pattern_matches(d, command) for d in deny):
            missing.append(pattern)
    return missing


class PermissionRuleTests(unittest.TestCase):
    def setUp(self):
        self.allow = allow_patterns(SETTINGS.read_text(encoding="utf-8"))
        self.deny = deny_patterns(WORKFLOW.read_text(encoding="utf-8"))

    def test_the_files_were_parsed(self):
        self.assertIn("scripts/run-mutation-tests.sh:*", self.allow)
        self.assertIn("python3 scripts/kb/search.py:*", self.allow)
        self.assertIn("dotnet:*", self.deny)

    def test_every_allow_rule_that_can_run_repository_code_is_denied_for_the_ci_reviewer(self):
        self.assertEqual(uncovered(self.allow, self.deny), [])

    def test_the_read_only_exemption_is_narrow(self):
        exempt = {p for p in self.allow if is_read_only(p)}
        self.assertIn("pwd", exempt)
        for pattern in ("git log:*", "git diff:*", "git status:*", "scripts/run-mutation-tests.sh:*", "python3 scripts/kb/search.py:*", "dotnet build:*", "npm test"):
            self.assertFalse(is_read_only(pattern), pattern)

    def test_local_sessions_ask_before_git_output(self):
        # git log|diff|show --output=<path> writes files; the allow-listed git rules must not run it unprompted.
        ask = [m.group(1) for m in (RULE.match(r) for r in json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]["ask"]) if m]
        self.assertTrue(any(pattern_matches(p, "git log -1 --format=x --output=.git/config") for p in ask), ask)

    def test_local_sessions_ask_before_commands_that_run_code_or_change_shared_state(self):
        # The guard cannot block these without blocking legitimate use, so the user is prompted instead.
        ask = [m.group(1) for m in (RULE.match(r) for r in json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]["ask"]) if m]
        for command in ("dotnet build -p:PreBuildEvent=x", "npm audit fix --force",
                        "python3 scripts/ai_review_local.py --base origin/main --reset", "gh pr merge 1"):
            with self.subTest(command=command):
                self.assertTrue(any(pattern_matches(p, command) for p in ask), command)

    def ask_patterns(self) -> list[str]:
        return [m.group(1) for m in (RULE.match(r) for r in json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]["ask"]) if m]

    def test_local_sessions_ask_before_the_forms_that_slip_past_a_prefix_rule(self):
        # First-position and `=` forms, attached or separated values, and the other spellings of the same options: each
        # must be matched by some ask rule, because the allow rules (`dotnet build:*`, `python3 scripts/ai_review_local.py:*`,
        # `npm audit:*`) would otherwise run them unprompted. If one fails, the settings lack a pattern: add it there.
        ask = self.ask_patterns()
        script = "python3 scripts/ai_review_local.py"
        commands = (
            f"{script} --reset", f"{script} --max-rounds 99 --base origin/main --require", f"{script} --max-rounds=99",
            f"{script} --claude-bin ./x", f"{script} --claude-bin=./x", f"{script} --out-dir .ai-review-2", f"{script} --out-dir=.ai-review-2",
            f"{script} --base origin/main --require --reset",
            "npm audit --registry=https://r.example fix", "npm audit fix", "npm audit --force fix",
            "dotnet build /l:X,evil.dll", "dotnet build -l:X,evil.dll", "dotnet test --logger x", "dotnet build -logger:evil.dll",
            "dotnet test --test-adapter-path ./adapters", "dotnet build -dl:X", "dotnet build -distributedlogger:X",
            "dotnet build --p PreBuildEvent=x", "dotnet build --p=PreBuildEvent=x", "dotnet build -p PostBuildEvent=x",
            "dotnet build -p:PreBuildEvent=x", "dotnet build /p:PreBuildEvent=x", "dotnet build --property PreBuildEvent=x",
            "dotnet build -p=PreBuildEvent=x", "dotnet build -P:X=1", "dotnet restore -rp:X=1", "dotnet build /rp:X=1",
            "dotnet build -restoreProperty:X=1", "dotnet build --p:CustomAfterMicrosoftCommonTargets=/x.targets", "dotnet build --p:X=1",
            "gh api -X DELETE repos/o/r", "gh api -X=DELETE repos/o/r", "gh api repos/o/r -XDELETE", "gh api repos/o/r --method=DELETE", "gh api repos/o/r --method DELETE",
            "gh api repos/o/r --method=delete", "gh api -X delete repos/o/r",
            "gh pr merge 1",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(any(pattern_matches(p, command) for p in ask), command)

    def test_local_sessions_are_not_asked_for_the_routine_commands(self):
        # No needless prompts: the verification commands and the normal review run stay allowed without a question.
        ask = self.ask_patterns()
        script = "python3 scripts/ai_review_local.py"
        commands = (
            "dotnet test --project x", "dotnet build --project x.csproj", "dotnet build Quorum.slnx", "dotnet test --solution Quorum.slnx",
            "dotnet build Quorum.slnx --no-restore -c Release", "dotnet format Quorum.slnx --verify-no-changes", "dotnet restore",
            f"{script} --base origin/main --require", f"{script} --base origin/main --require --model opus", f"{script} --model opus --base origin/main",
            f"{script} --dry-run", f"{script} --base origin/main --require --timeout 900", "npm audit", "npm audit --json",
            "npm audit --prefix frontend", "gh pr view 1", "gh api repos/o/r", "gh api repos/o/r --jq .delete_branch_on_merge", "git log -1",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertFalse(any(pattern_matches(p, command) for p in ask), command)

    def test_the_precise_npm_audit_and_gh_api_ask_rules_prompt_only_for_the_risky_forms(self):
        ask = self.ask_patterns()
        for command in ("npm audit fix", "npm audit --force fix", "gh api -X DELETE repos/o/r", "gh api repos/o/r --method=delete"):
            with self.subTest(ask=command):
                self.assertTrue(any(pattern_matches(p, command) for p in ask), command)
        for command in ("npm audit --prefix frontend", "gh api repos/o/r --jq .delete_branch_on_merge"):
            with self.subTest(no_ask=command):
                self.assertFalse(any(pattern_matches(p, command) for p in ask), command)

    def test_no_rule_combines_an_inner_wildcard_with_a_trailing_colon_star(self):
        # Claude Code treats a rule ending in `:*` as a prefix rule and the earlier `*` as literal text, so it never matches.
        permissions = json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]
        for kind in ("allow", "ask", "deny"):
            for rule in permissions[kind]:
                inner = bash_pattern(rule)
                if inner is not None and inner.endswith(":*"):
                    with self.subTest(kind=kind, rule=rule):
                        self.assertNotIn("*", inner[:-2], f"{rule} would never match as intended; use a glob such as `Bash(a * -x*)`")

    def test_no_prefix_rule_ends_in_whitespace(self):
        # Claude Code collapses runs of whitespace in a command, so `Bash(X :*)` (prefix `X `) can never match: the command is
        # `X` or `X <args>` with the prefix followed by one space, which a prefix that already ends in a space cannot satisfy.
        permissions = json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]
        for kind in ("allow", "ask", "deny"):
            for rule in permissions[kind]:
                inner = bash_pattern(rule)
                if inner is not None and inner.endswith(":*"):
                    with self.subTest(kind=kind, rule=rule):
                        self.assertEqual(inner[:-2], inner[:-2].rstrip(), f"{rule} has a prefix ending in whitespace and never matches")

    def path_ask_patterns(self, tool: str) -> list[str]:
        rules = json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]["ask"]
        return [m.group(1) for m in (re.match(rf"^{tool}\((.*)\)$", r) for r in rules) if m]

    def test_local_sessions_ask_before_editing_the_gate_scripts_and_msbuild_project_files(self):
        # TQ-020 option 1 and OD-032: `Edit(./scripts/**)` and `Edit(./src/**)` are allowed, but the allow-listed gate scripts run
        # with scripts/ first on sys.path, so a new single-file module (scripts/json.py) or a new regular package
        # (scripts/json/__init__.py, also argparse, yaml) at the top of scripts/ would hijack the stdlib import and run unprompted.
        # Both are gated. A namespace package (a directory without __init__.py) does NOT shadow: a stdlib regular module wins over
        # a namespace portion (scratch probe: scripts/json/x.py leaves `import json` on the stdlib), so scripts/kb/tests/ and
        # scripts/tests/ stay free. The scripts/kb/*.py files are gated too: allow-listed scripts there run the code of lib.py and
        # backends.py, which they load by path. MSBuild builds any *.*proj and auto-loads Directory.Build.rsp, *.props, *.targets and
        # <Project>.csproj.user. Ask rules beat allow rules.
        gated = ("scripts/json.py", "scripts/argparse.py", "scripts/json/__init__.py", "scripts/argparse/__init__.py",
                 "scripts/yaml/__init__.py", "scripts/kb/__init__.py", "scripts/ai_review_local.py", "scripts/framework_lint.py",
                 "scripts/kb/lib.py", "scripts/kb/check_chunks.py", "scripts/kb/backends.py",
                 "src/Api/Api.csproj", "src/x.fsproj", "build.proj", "src/Api/Directory.Build.rsp", "src/Api/Api.csproj.user",
                 "Directory.Build.props", "tests/X/X.csproj", "src/Api/Foo.targets", "Directory.Packages.props",
                 "a/b/c/Directory.Build.targets")
        free = ("scripts/kb/tests/test_kb.py", "scripts/tests/test_x.py", "src/Api/Program.cs", "src/x.xml", "docs/x.md",
                "scripts/ai_review_local.py.bak", "src/Api/csproj", "scripts/json/x.py", "scripts/kb/tests/__init__.py")
        # Claude Code 2.1.332 applies only `Edit(...)` rules to file permission checks, whichever file tool writes (a `Write(...)`
        # rule is not matched), so the Edit rules are the effective ones. The Write twins are kept because they document intent
        # and cost nothing; this test keeps both sets in step. A shell redirect from an allow-listed command is checked against
        # Edit allow rules only, never ask rules, so .claude/hooks/guard_bash.py asks for redirects into the repository (OD-032).
        for tool in ("Edit", "Write"):
            ask = self.path_ask_patterns(tool)
            for path in gated:
                with self.subTest(tool=tool, ask=path):
                    self.assertTrue(any(path_rule_matches(p, path) for p in ask), path)
            for path in free:
                with self.subTest(tool=tool, no_ask=path):
                    self.assertFalse(any(path_rule_matches(p, path) for p in ask), path)

    def test_the_path_matcher_follows_gitignore_semantics(self):
        self.assertTrue(path_rule_matches("./**/*.props", "Directory.Build.props"))   # `**/` matches zero directories
        self.assertTrue(path_rule_matches("./**/*.props", "src/Directory.Build.props"))
        self.assertFalse(path_rule_matches("./**/*.props", "src/x.props/y"))
        self.assertTrue(path_rule_matches("./src/**", "src/Api/Program.cs"))
        self.assertFalse(path_rule_matches("./src/**", "other/src/a.cs"))
        self.assertTrue(path_rule_matches("./scripts/framework_lint.py", "scripts/framework_lint.py"))
        self.assertFalse(path_rule_matches("./scripts/framework_lint.py", "x/scripts/framework_lint.py"))
        self.assertFalse(path_rule_matches("./scripts/*.py", "scripts/kb/a.py"))   # `*` stays inside one segment
        self.assertTrue(path_rule_matches("./scripts/*/__init__.py", "scripts/json/__init__.py"))
        self.assertFalse(path_rule_matches("./scripts/*/__init__.py", "scripts/kb/tests/__init__.py"))
        self.assertTrue(path_rule_matches("./**/*.*proj", "build.proj"))
        self.assertTrue(path_rule_matches("./**/*.*proj", "src/x.fsproj"))
        self.assertFalse(path_rule_matches("./**/*.*proj", "src/a.proj/b.cs"))

    def test_the_inner_wildcard_check_catches_the_never_matching_form(self):
        self.assertFalse(pattern_matches("dotnet * --p:*", "dotnet build --p:PreBuildEvent=x"))

    def deny_settings(self) -> list[str]:
        return [m.group(1) for m in (RULE.match(r) for r in json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]["deny"]) if m]

    def test_local_sessions_deny_the_remote_branch_delete_and_the_checkout_discard_forms(self):
        # `Bash(git push origin :*)` and `Bash(git checkout -- :*)` were prefix rules ending in a space and never matched; the
        # globs `git push * :**` and `git checkout -- **` do. Ordinary pushes and checkouts must stay allowed.
        deny = self.deny_settings()
        for command in ("git push origin :feature", "git checkout -- src/a.cs"):
            with self.subTest(denied=command):
                self.assertTrue(any(pattern_matches(p, command) for p in deny), command)
        for command in ("git push origin main:main", "git push -u origin fix/x", "git checkout -b x", "git checkout main"):
            with self.subTest(not_denied=command):
                self.assertFalse(any(pattern_matches(p, command) for p in deny), command)

    def test_a_rule_ending_in_double_star_is_a_glob(self):
        self.assertTrue(pattern_matches("dotnet * --p:**", "dotnet build --p:X=1"))
        self.assertFalse(pattern_matches("dotnet * --p:**", "dotnet build --project x.csproj"))
        self.assertTrue(pattern_matches("git push * :**", "git push origin :feature"))
        self.assertFalse(pattern_matches("git push * :**", "git push origin main:main"))
        self.assertTrue(pattern_matches("git checkout -- **", "git checkout -- src/a.cs"))
        self.assertFalse(pattern_matches("git checkout -- **", "git checkout -b x"))

    def test_the_guard_blocks_the_build_events_in_the_double_dash_property_form_too(self):
        import subprocess
        import sys
        guard = ROOT / ".claude" / "hooks" / "guard_bash.py"
        for command, blocked in (("dotnet build --p:PreBuildEvent=x", True), ("dotnet build --p:PostBuildEvent=x", True),
                                 ("dotnet build --p:Configuration=Release", False)):
            with self.subTest(command=command):
                payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
                out = subprocess.run([sys.executable, "-I", str(guard)], input=payload, capture_output=True, text=True, check=True).stdout
                self.assertEqual("deny" in out, blocked, out)

    def test_removing_the_git_deny_makes_the_check_fail(self):
        # git log|diff|show --output=<path> writes files, so the allow-listed git rules must stay denied in CI.
        self.assertIn("git log:*", uncovered(self.allow, [d for d in self.deny if d != "git:*"]))

    def test_removing_the_script_denies_makes_the_check_fail(self):
        # The case the check exists for: the allow rule names a repository script and nothing denies it.
        weakened = [d for d in self.deny if d not in ("scripts/run-mutation-tests.sh:*", "scripts/*")]
        self.assertNotEqual(len(weakened), len(self.deny), "expected both script deny entries in the workflow")
        self.assertIn("scripts/run-mutation-tests.sh:*", uncovered(self.allow, weakened))

    def test_either_script_deny_alone_is_enough(self):
        for keep in ("scripts/run-mutation-tests.sh:*", "scripts/*"):
            with self.subTest(keep=keep):
                partial = [d for d in self.deny if d not in ("scripts/run-mutation-tests.sh:*", "scripts/*") or d == keep]
                self.assertNotIn("scripts/run-mutation-tests.sh:*", uncovered(self.allow, partial))

    def test_matching_follows_the_documented_rules(self):
        self.assertTrue(pattern_matches("npm:*", "npm"))
        self.assertTrue(pattern_matches("npm:*", "npm run build"))
        self.assertFalse(pattern_matches("npm:*", "npmx run"))
        self.assertTrue(pattern_matches("npm *", "npm test"))
        self.assertFalse(pattern_matches("npm *", "npmx test"))
        self.assertTrue(pattern_matches("scripts/*", "scripts/run-mutation-tests.sh --solution x"))
        self.assertFalse(pattern_matches("scripts/*", "xscripts/a"))
        self.assertFalse(pattern_matches("scripts/:*", "scripts/run.sh"))
        # a rule ending in `:*` is a prefix rule whatever precedes it: the inner `*` is literal, so it never matches as intended
        self.assertFalse(pattern_matches("dotnet * -p:*", "dotnet build -p:PreBuildEvent=x"))
        self.assertTrue(pattern_matches("dotnet * -p:*", "dotnet * -p"))
        self.assertTrue(pattern_matches("dotnet * -p:*", "dotnet * -p --x"))
        self.assertTrue(pattern_matches("dotnet * -p*", "dotnet build -p:PreBuildEvent=x"))
        self.assertFalse(pattern_matches("dotnet * -p*", "dotnet build -c Release"))
        self.assertTrue(pattern_matches("pwd", "pwd"))
        self.assertFalse(pattern_matches("pwd", "pwd -P"))


if __name__ == "__main__":
    unittest.main()
