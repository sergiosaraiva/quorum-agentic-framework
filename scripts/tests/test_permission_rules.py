"""Regression test: every Bash allow rule in .claude/settings.json that can run repository code must be matched by a deny
entry of the CI reviewer (`--disallowedTools` in .github/workflows/ai-pr-review.yml).

Why: the reviewer job loads the base settings.json, so its allow rules apply; a deny rule wins over an allow rule, but only
when its text matches the command. A new allow rule such as `Bash(scripts/run-mutation-tests.sh:*)` without a matching deny
would let a prompt-injected diff run code from the checked-out PR.

Matching follows https://code.claude.com/docs/en/permissions: `Bash(X:*)` and `Bash(X *)` match the command X or a command
starting with `X `; a rule with `*` elsewhere is a glob where `*` matches any characters; otherwise an exact match.
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


def representative_command(pattern: str) -> str:
    """A command the allow pattern matches: `X:*` and `X *` -> `X --x`, other `*` -> `x`, exact -> itself."""
    if pattern.endswith(":*"):
        return pattern[:-2] + " --x"
    if pattern.endswith(" *"):
        return pattern[:-2] + " --x"
    return pattern.replace("*", "x")


def pattern_matches(pattern: str, command: str) -> bool:
    # `X:*` is the legacy prefix form only when X has no `*`; `dotnet * -p:*` is a glob whose last `:*` is a literal colon
    # followed by a wildcard (it must match `dotnet build -p:Prop=x`). Whether Claude Code reads it that way is unverified here.
    if pattern.endswith(":*") and "*" not in pattern[:-2]:
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
            "npm audit --registry=https://r.example fix", "npm audit fix", "npm audit --fix",
            "dotnet build /l:X,evil.dll", "dotnet build -l:X,evil.dll", "dotnet test --logger x", "dotnet build -logger:evil.dll",
            "dotnet test --test-adapter-path ./adapters", "dotnet build -dl:X", "dotnet build -distributedlogger:X",
            "dotnet build --p PreBuildEvent=x", "dotnet build --p=PreBuildEvent=x", "dotnet build -p PostBuildEvent=x",
            "dotnet build -p:PreBuildEvent=x", "dotnet build /p:PreBuildEvent=x", "dotnet build --property PreBuildEvent=x",
            "dotnet build -p=PreBuildEvent=x", "dotnet build -P:X=1", "dotnet restore -rp:X=1", "dotnet build /rp:X=1",
            "dotnet build -restoreProperty:X=1",
            "gh api -X DELETE repos/o/r", "gh api repos/o/r -XDELETE", "gh api repos/o/r --method=DELETE", "gh api repos/o/r --method DELETE",
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
            "dotnet test --project x", "dotnet build Quorum.slnx", "dotnet test --solution Quorum.slnx",
            "dotnet build Quorum.slnx --no-restore -c Release", "dotnet format Quorum.slnx --verify-no-changes", "dotnet restore",
            f"{script} --base origin/main --require", f"{script} --base origin/main --require --model opus", f"{script} --model opus --base origin/main",
            f"{script} --dry-run", f"{script} --base origin/main --require --timeout 900", "npm audit", "npm audit --json",
            "gh pr view 1", "gh api repos/o/r", "git log -1",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertFalse(any(pattern_matches(p, command) for p in ask), command)

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
        self.assertTrue(pattern_matches("dotnet * -p:*", "dotnet build -p:PreBuildEvent=x"))
        self.assertFalse(pattern_matches("dotnet * -p:*", "dotnet build -c Release"))
        self.assertTrue(pattern_matches("pwd", "pwd"))
        self.assertFalse(pattern_matches("pwd", "pwd -P"))


if __name__ == "__main__":
    unittest.main()
