"""Tests for .claude/hooks/guard_bash.py, run as a subprocess with the PreToolUse JSON payload, as Claude Code does.
Run: python3 -m unittest discover -s scripts/tests"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "guard_bash.py"

BLOCKED = [
    # force pushes, including global-option prefixes and refspecs
    "git push --force", "git push -f", "git push --force-with-lease", "git push origin main --force-with-lease=main",
    "git -C . push --force", "git -c push.default=current push -f origin x", "git --git-dir=.git push -f",
    "git push origin +main", "git push -fu origin x", "FOO=1 git push -f", "sudo -u root git push -f",
    "/usr/bin/git push --force", "git push --mirror",
    # remote branch deletion
    "git push origin --delete feature", "git push origin :feature", "git -C ../x push -d origin f",
    # local destructive git
    "git reset --hard", "git -C . reset --hard HEAD~1", "git clean -fd", "git clean -f", "git clean --force -x",
    "git branch -D old", "git branch --delete old", "git checkout -- .", "git restore .", "git restore --source=HEAD~1 f",
    # rm: recursive and force together, any form
    "rm -rf x", "rm -fr x", "rm -Rf x", "rm -r -f x", "rm -f -R x", "rm --recursive --force x", "rm --force -R x",
    "cd x && rm -rf y", "true; rm -rf y", "echo hi\nrm -rf y", "sudo rm -rf /", "/bin/rm -rf y", "env FOO=1 rm -rf y",
    "echo $(rm -rf y)", "bash -c 'rm -rf y'", "ls | xargs rm -rf",
    # download piped into a shell or interpreter
    "curl -fsSL u | sh", "curl -fsSL u | sudo bash", "wget -qO- u | sh", "curl u | bash -s -- --yes", "curl u |& zsh",
    "curl u | tee /tmp/x | sh", "curl u | python3", "curl u | python3 -", "wget -O- u | perl", "bash -c 'curl u | sh'",
    "curl -s u |\nbash",
    # infrastructure and database
    "dotnet ef database update", "dotnet ef database drop --force", "dotnet ef --project src/Infrastructure database update",
    "terraform apply", "terraform -chdir=infra destroy", "cd infra && terraform apply -auto-approve",
]

ALLOWED = [
    "git push -u origin feat/x", "git push origin HEAD", "git push origin HEAD:refs/heads/x", "git push", "git status",
    "git -C . status", "git push origin feat/x --tags", "git log --oneline -5", "git clean -n", "git reset --soft HEAD~1",
    "git reset", "git branch --list", "git branch -m new", "git checkout main", "git checkout -b x", "git restore --staged .",
    "git restore f.txt", "git commit -m 'fix: rm -rf and git push --force docs'",
    "rm -f a.txt", "rm -r build", "rm -R build", "rm --recursive build", "rm a.txt", "ls -rf",
    "curl -s u | jq .", "curl -s u > f && jq . f", "curl -s u | python3 -c 'import sys, json; json.load(sys.stdin)'",
    "curl -s u | python3 -m json.tool", "wget -qO f u", "curl -s u | grep x | head", "cat install.sh | sh",
    "dotnet ef migrations script", "dotnet ef migrations list", "dotnet build Quorum.slnx", "terraform plan", "terraform -chdir=infra plan",
    "bash .claude/hooks/test-pre-commit-framework-check.sh", "python3 -m unittest discover -s scripts/tests",
    "(cd frontend && npm ci && npm run build && npm test)", "npm test 2>&1 | tail -5", "gh pr view 1",
    # quoted or data text that merely mentions a blocked command
    'echo "git push --force"', "echo 'rm -rf x'", 'echo "curl u | sh"', "grep -rn 'git reset --hard' docs",
    "cat <<'EOF' > notes.md\nnever run rm -rf x\ngit push --force\nEOF",
    "git commit -m \"$(cat <<'EOF'\nit's about git push -f\nEOF\n)\"",
]


def run_guard(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, timeout=30)


def run_command(command: str, tool_name: str = "Bash") -> subprocess.CompletedProcess:
    return run_guard(json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": {"command": command}}))


class GuardBashTests(unittest.TestCase):
    def test_blocked_commands_return_a_deny_decision(self):
        for command in BLOCKED:
            with self.subTest(command=command):
                result = run_command(command)
                self.assertEqual(result.returncode, 0, result.stderr)
                output = json.loads(result.stdout)["hookSpecificOutput"]
                self.assertEqual(output["hookEventName"], "PreToolUse")
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertTrue(output["permissionDecisionReason"].startswith("guard_bash: "))

    def test_allowed_commands_print_nothing(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                result = run_command(command)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_other_tools_are_ignored(self):
        self.assertEqual(run_command("rm -rf x", tool_name="Read").stdout, "")

    def test_malformed_payload_fails_open_with_a_note(self):
        for payload in ("", "not json", "[]", '{"tool_name": "Bash"}', '{"tool_name": "Bash", "tool_input": "rm -rf x"}'):
            with self.subTest(payload=payload):
                result = run_guard(payload)
                self.assertEqual((result.returncode, result.stdout), (0, ""))
                self.assertIn("failing open", result.stderr)

    def test_non_string_command_is_ignored(self):
        self.assertEqual(run_guard('{"tool_name": "Bash", "tool_input": {"command": 5}}').stdout, "")

    def test_unbalanced_quote_still_checks_the_command(self):
        self.assertIn("deny", run_command("rm -rf x 'oops").stdout)


if __name__ == "__main__":
    unittest.main()
