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
        self.assertTrue(pattern_matches("pwd", "pwd"))
        self.assertFalse(pattern_matches("pwd", "pwd -P"))


if __name__ == "__main__":
    unittest.main()
