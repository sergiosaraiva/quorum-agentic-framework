#!/usr/bin/env python3
"""PreToolUse guard for the Bash tool: the deterministic second layer behind the `deny` list in .claude/settings.json.

Why: Bash permission rules match command text, so `git -C . push --force` or `curl u | sh` slip past
`Bash(git push --force:*)` / `Bash(curl * | sh:*)` (https://code.claude.com/docs/en/permissions, "What a Bash rule
doesn't match"; compound commands are split on && || ; | |& & newline). This hook normalises the command and blocks.

Contract (https://code.claude.com/docs/en/hooks, "PreToolUse input" and "Exit code output"): the hook gets JSON on stdin
with `tool_name` and `tool_input.command`. To block it prints on stdout, exit 0:
  {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}
The reason is shown to the model. Printing nothing and exiting 0 leaves the normal permission flow in charge.

Fail open: a malformed payload exits 0 with a stderr note, so a hook bug can never brick the session (any other crash is a
non-blocking error per the docs). The deny rules still apply as the first layer.

Known gaps (best effort, not a sandbox): commands built at runtime (`$VAR`, `eval`), `$(...)` inside double quotes,
`bash <(curl u)`, scripts that run a destructive command internally.
"""
import json
import os
import re
import shlex
import sys

SHELL_RE = re.compile(r"^(ba|z|da|k|c|tc|fi)?sh$")
INTERP_RE = re.compile(r"^(python[\d.]*|perl|ruby|node|php|deno)$")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# wrapper -> options that consume the next token (stripped before matching the real command)
WRAPPERS = {"sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"}, "env": {"-u", "-C", "-S"}, "command": set(),
            "builtin": set(), "exec": set(), "time": set(), "nohup": set(), "nice": {"-n"}, "timeout": {"-s", "-k"},
            "xargs": {"-I", "-n", "-P", "-d", "-E", "-L", "-s"}}
SEPARATOR_CHARS = set(";&|()\n")
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


def has_flag(args, short, *long):
    """True if a short flag letter (also inside a cluster such as -fu) or an exact/prefixed long flag is present."""
    for a in args:
        if a == "--":
            break
        if a.startswith("--"):
            if any(a == f or a.startswith(f + "=") for f in long):
                return True
        elif a.startswith("-") and set(a[1:]) & set(short):
            return True
    return False


def refspec(args, prefix):  # push refspec `+main` forces, `:branch` deletes
    return any(a[:1] == prefix and len(a) > 1 for a in args)


def discards_changes(args):  # git checkout -- <path>, restore ., restore --source
    if args[:2] == ["checkout", "--"]:
        return True
    return args[:1] == ["restore"] and (any(a.startswith("--source") for a in args)
                                        or ("." in args and ("--staged" not in args or "--worktree" in args)))


def rm_force_recursive(args):
    return has_flag(args, "rR", "--recursive") and has_flag(args, "f", "--force")


# (name, predicate(cmd, args), reason). For git, args[0] is the subcommand with global options already removed.
RULES = [
    ("git push force", lambda c, a: c == "git" and a[:1] == ["push"] and (has_flag(a, "f", "--force", "--force-with-lease", "--force-if-includes", "--mirror") or refspec(a[1:], "+")),
     "Force pushes (--force, -f, --force-with-lease, +refspec) are blocked. Push normally; a human force-pushes if truly needed."),
    ("git push delete", lambda c, a: c == "git" and a[:1] == ["push"] and (has_flag(a, "d", "--delete") or refspec(a[1:], ":")),
     "Deleting remote branches (--delete, :branch) is blocked. Ask the user to do it."),
    ("git reset --hard", lambda c, a: c == "git" and a[:1] == ["reset"] and "--hard" in a,
     "git reset --hard discards work and is blocked. Use git stash or a targeted checkout after asking."),
    ("git clean force", lambda c, a: c == "git" and a[:1] == ["clean"] and has_flag(a, "f", "--force"),
     "git clean -f deletes untracked files and is blocked. Preview with git clean -n and ask the user."),
    ("git branch delete", lambda c, a: c == "git" and a[:1] == ["branch"] and has_flag(a, "dD", "--delete"),
     "Deleting local branches is blocked. Ask the user."),
    ("git discard changes", lambda c, a: c == "git" and discards_changes(a),
     "Discarding working-tree changes (checkout --, restore ., restore --source) is blocked. Ask the user."),
    ("rm -rf", lambda c, a: c == "rm" and rm_force_recursive(a),
     "rm with recursive and force together is blocked. Delete specific files, or rm -r without -f, or ask the user."),
    ("dotnet ef database", lambda c, a: c == "dotnet" and "ef" in a and "database" in a and bool({"update", "drop"} & set(a)),
     "dotnet ef database update|drop is blocked: migrations are reviewed first and applied by the deploy pipeline (Immutable Rule 2). Use migrations script."),
    ("terraform apply", lambda c, a: c == "terraform" and next((x for x in a if not x.startswith("-")), "") in ("apply", "destroy"),
     "terraform apply|destroy is blocked: infrastructure changes go through reviewed code and the pipeline."),
]


def split_segments(cmd):
    """Return [(tokens, piped_into_next)] split on && || ; | |& & and newlines, honouring quotes (so echo "a | b" is one word)."""
    cmd = re.sub(r"\\\n", " ", cmd)
    kept, delim = [], None  # drop heredoc bodies: they are data, not commands
    for line in cmd.split("\n"):
        if delim is not None:
            delim = None if line.strip() == delim else delim
            continue
        kept.append(line)
        m = re.search(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_]\w*)\1", line)
        delim = m.group(2) if m else None
    cmd = "\n".join(kept)
    lex = shlex.shlex(cmd, posix=True, punctuation_chars="".join(SEPARATOR_CHARS | set("<>")))
    lex.whitespace, lex.whitespace_split = " \t\r", True
    try:
        tokens = list(lex)
    except ValueError:  # unbalanced quote: fall back to a stricter naive split rather than skipping the check
        tokens = re.sub(r"(&&|\|\||\|&|[;&|()\n])", r" \1 ", cmd).split()
    segs, cur = [], []
    for t in tokens:
        if t and set(t) <= SEPARATOR_CHARS:
            segs.append((cur, t.strip("\n") in ("|", "|&")))
            cur = []
        elif not set(t) <= SEPARATOR_CHARS | set("<>"):  # a leftover operator token is a redirect: drop it
            cur.append(t)
    return segs + [(cur, False)]


def normalise(tokens):
    """Strip env assignments, wrappers (sudo, env, command ...) and git global options; return (command basename, args)."""
    while tokens:
        base = os.path.basename(tokens[0])
        if ASSIGN_RE.match(tokens[0]):
            tokens = tokens[1:]
        elif base in WRAPPERS:
            rest = tokens[1:]
            while rest and (rest[0].startswith("-") or ASSIGN_RE.match(rest[0])):
                rest = rest[2:] if rest[0] in WRAPPERS[base] else rest[1:]
            tokens = rest[1:] if base == "timeout" and rest else rest  # timeout takes a duration
        else:
            break
    if not tokens:
        return "", []
    cmd, args = os.path.basename(tokens[0]), tokens[1:]
    if cmd == "git":
        while args and args[0].startswith("-"):
            args = args[2:] if args[0] in GIT_VALUE_OPTS else args[1:]
    return cmd, args


def reads_stdin(args):  # an interpreter runs piped input unless given inline code (-c ...) or a script/module argument
    return "-s" in args or "-" in args or not any(not a.startswith("-") for a in args)


def check(command, depth=0):
    """Return the reason string if the command must be blocked, else None."""
    downloaded = False
    for tokens, piped in split_segments(command):
        cmd, args = normalise(tokens)
        if downloaded and (SHELL_RE.match(cmd) or INTERP_RE.match(cmd)) and reads_stdin(args):
            return "Piping a download into a shell or interpreter (curl|wget ... | sh) is blocked. Download to a file, review it, then run it."
        for _, predicate, reason in RULES:
            if predicate(cmd, args):
                return reason
        if SHELL_RE.match(cmd) and depth < 3:  # sh -c '<script>': check the inner script too
            for i, a in enumerate(args[:-1]):
                if a.startswith("-") and not a.startswith("--") and "c" in a:
                    inner = check(args[i + 1], depth + 1)
                    if inner:
                        return inner
        downloaded = (downloaded or cmd in ("curl", "wget")) if piped else False
    return None


def main():
    try:
        payload = json.load(sys.stdin)
        command = payload["tool_input"]["command"] if payload.get("tool_name") == "Bash" else ""
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"guard_bash: ignoring malformed hook payload ({exc}); failing open", file=sys.stderr)
        return 0
    reason = check(command) if isinstance(command, str) else None
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": f"guard_bash: {reason}"}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
