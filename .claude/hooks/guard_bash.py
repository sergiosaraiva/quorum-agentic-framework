#!/usr/bin/env python3
"""PreToolUse guard for the Bash tool: the deterministic second layer behind the `deny` list in .claude/settings.json.

Why: Bash permission rules match command text, so `git -C . push --force` or `curl u | sh` slip past
`Bash(git push --force:*)` / `Bash(curl * | sh:*)` (https://code.claude.com/docs/en/permissions, "What a Bash rule
doesn't match"; compound commands are split on && || ; | |& & newline). This hook lexes the command like Bash does
(quotes, comments, heredocs, substitutions), normalises it and blocks.

Contract (https://code.claude.com/docs/en/hooks, "PreToolUse input" and "Exit code output"): the hook gets JSON on stdin
with `tool_name` and `tool_input.command`. To block it prints on stdout, exit 0:
  {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}
The reason is shown to the model. Printing nothing and exiting 0 leaves the normal permission flow in charge.

Platform: Linux, macOS and WSL Bash. It does not cover the Windows PowerShell tool. Fail open: a malformed payload exits 0
with a stderr note, and a missing python3 interpreter does not block anything either (`onFailure` is not set in
settings.json on purpose, so a missing interpreter cannot block every Bash call). The deny rules still apply as the first
layer. stdin is read as bytes and decoded as UTF-8 with replacement, so a non-UTF-8 locale cannot turn a non-ASCII
command into a fail-open.

Covered, beyond the rules in RULES: `git` global options (`-C`, `-c`, `--git-dir`...) and `-c alias.*`; env assignments and
wrappers (sudo, env, command, time, nice, ionice, setsid, stdbuf, flock, timeout, xargs, busybox...); `sh -c '<script>'`
(also after `--`); substitutions `$(...)`, backticks and `<(...)` anywhere outside single quotes; `find -exec|-execdir|-ok|-okdir
<command>`; unambiguous long-option prefixes of 3+ characters (`--recur`, `--forc`); heredocs recognised only outside quotes and
comments, with the body skipped as data unless it feeds a shell or stdin-reading interpreter (checked as a script) or the
closing delimiter never appears (then the rest is checked as commands); downloads piped into a shell or interpreter,
including `/dev/stdin`, `-`, `sh -c "$(cat)"`, `busybox sh` and a `( ... )` wrapper.

Known gaps (best effort, not a sandbox): commands built at runtime (`$VAR`, `eval`, `source /dev/stdin`); commands inside
`$(( ))` arithmetic and inside unquoted-heredoc bodies; `bash <(curl u)`; scripts that run a destructive command internally
and heredoc bodies fed to interpreters (`python3 - <<EOF`) beyond what a shell parse of the text shows; nesting deeper than
MAX_NEST or MAX_DEPTH (blocked, fail closed); git aliases defined in config files and other `-c` hooks (`core.pager`,
`core.sshCommand`); `git checkout <path>`, `git checkout -f` and `git restore <file>` without `.`; 1-2 character long-option prefixes
(`--ha`); `curl u | (cat; sh)` and `{ ...; }` groups; wrappers not listed (su -c, ssh, docker run, watch...).
"""
import json
import os
import re
import sys

SHELL_RE = re.compile(r"^(ba|z|da|k|c|tc|fi|a)?sh$")
INTERP_RE = re.compile(r"^(python[\d.]*|perl|ruby|node|php|deno)$")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# wrapper -> options that consume the next token (stripped before matching the real command)
WRAPPERS = {"sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"}, "env": {"-u", "-C", "-S"}, "command": set(),
            "builtin": set(), "exec": set(), "time": set(), "nohup": set(), "nice": {"-n"}, "timeout": {"-s", "-k"},
            "xargs": {"-I", "-n", "-P", "-d", "-E", "-L", "-s"}, "setsid": set(), "stdbuf": {"-i", "-o", "-e"},
            "ionice": {"-c", "-n", "-p", "-P", "-u"}, "flock": {"-w", "-E", "--timeout", "--conflict-exit-code"},
            "busybox": set()}
WRAPPER_POSITIONALS = {"timeout": 1, "flock": 1}  # leading non-option arguments (duration, lock file) before the command
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
STDIN_PATHS = {"-", "/dev/stdin", "/dev/fd/0", "/proc/self/fd/0"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
MAX_DEPTH = 3  # nested `sh -c`, heredoc scripts and find -exec commands
MAX_NEST = 8  # nested substitutions while lexing


def has_flag(args, short, *long):
    """True if a short flag letter (also inside a cluster such as -fu) or a long flag is present. Long flags also match an
    unambiguous prefix of 3+ characters after `--` (git and GNU tools accept `--recur`), with or without `=value`."""
    for a in args:
        if a == "--":
            break
        if a.startswith("--"):
            name = a.split("=", 1)[0]
            if any(name == f or (len(name) >= 5 and f.startswith(name)) for f in long):
                return True
        elif a.startswith("-") and set(a[1:]) & set(short):
            return True
    return False


def refspec(args, prefix):  # push refspec `+main` forces, `:branch` deletes
    return any(a[:1] == prefix and len(a) > 1 for a in args)


def discards_changes(args):
    """checkout . | checkout <rev> -- <paths> | switch -f | restore . | restore -s/--source | restore -W/--worktree."""
    sub, rest = args[:1], args[1:]
    if sub == ["checkout"]:
        return ("--" in rest and rest.index("--") < len(rest) - 1) or "." in rest
    if sub == ["switch"]:
        return has_flag(rest, "f", "--discard-changes", "--force")
    if sub == ["restore"]:
        staged_only = has_flag(rest, "S", "--staged") and not has_flag(rest, "W", "--worktree")
        return has_flag(rest, "sW", "--source", "--worktree") or ("." in rest and not staged_only)
    return False


def rm_force_recursive(args):
    return has_flag(args, "rR", "--recursive") and has_flag(args, "f", "--force")


# (name, predicate(cmd, args), reason). For git, args[0] is the subcommand with global options already removed.
RULES = [
    ("git push force", lambda c, a: c == "git" and a[:1] == ["push"] and (has_flag(a, "f", "--force", "--force-with-lease", "--force-if-includes", "--mirror") or refspec(a[1:], "+")),
     "Force pushes (--force, -f, --force-with-lease, +refspec) are blocked. Push normally; a human force-pushes if truly needed."),
    ("git push delete", lambda c, a: c == "git" and a[:1] == ["push"] and (has_flag(a, "d", "--delete", "--prune") or refspec(a[1:], ":")),
     "Deleting remote branches (--delete, --prune, :branch) is blocked. Ask the user to do it."),
    ("git reset --hard", lambda c, a: c == "git" and a[:1] == ["reset"] and has_flag(a, "", "--hard"),
     "git reset --hard discards work and is blocked. Use git stash or a targeted checkout after asking."),
    ("git clean force", lambda c, a: c == "git" and a[:1] == ["clean"] and has_flag(a, "f", "--force"),
     "git clean -f deletes untracked files and is blocked. Preview with git clean -n and ask the user."),
    ("git branch delete", lambda c, a: c == "git" and a[:1] == ["branch"] and has_flag(a, "dD", "--delete"),
     "Deleting local branches is blocked. Ask the user."),
    ("git discard changes", lambda c, a: c == "git" and discards_changes(a),
     "Discarding working-tree changes (checkout . or -- <paths>, switch -f, restore . or --source or --worktree) is blocked. Ask the user."),
    ("rm -rf", lambda c, a: c == "rm" and rm_force_recursive(a),
     "rm with recursive and force together is blocked. Delete specific files, or rm -r without -f, or ask the user."),
    ("dotnet ef database", lambda c, a: c == "dotnet" and "ef" in a and "database" in a and bool({"update", "drop"} & set(a)),
     "dotnet ef database update|drop is blocked: migrations are reviewed first and applied by the deploy pipeline (Immutable Rule 2). Use migrations script."),
    ("terraform apply", lambda c, a: c == "terraform" and next((x for x in a if not x.startswith("-")), "") in ("apply", "destroy"),
     "terraform apply|destroy is blocked: infrastructure changes go through reviewed code and the pipeline."),
]
DOWNLOAD_REASON = "Piping a download into a shell or interpreter (curl|wget ... | sh) is blocked. Download to a file, review it, then run it."
ALIAS_REASON = "git -c alias.* defines a command that the rules cannot see and is blocked. Run the git command directly."
DEEP_REASON = "The command nests substitutions, scripts or find -exec too deeply to inspect and is blocked. Simplify it."


class TooDeep(Exception):
    """Raised when substitutions nest deeper than MAX_NEST: the caller blocks (fail closed)."""


class Seg:
    """One simple command: its words, whether it is piped into the next command, and the heredoc bodies it receives."""
    __slots__ = ("words", "piped", "bodies")

    def __init__(self):
        self.words, self.piped, self.bodies = [], False, []


class Parser:
    """Quote-aware Bash lexer: segments split on && || ; | |& & ( ) and newlines. Comments start only at a word start.
    Redirections are dropped together with their target word. Substitutions ($(...), `...`, <(...)) outside single quotes
    are parsed into `extra` segments and kept as raw text in the word. A heredoc operator is recognised only outside
    quotes and comments; its body (read at the next newline) is attached to the owning segment. When Bash and this lexer
    could disagree the text is treated as a command, never as data."""

    def __init__(self, s, i=0, depth=0, extra=None):
        self.s, self.i, self.depth = s, i, depth
        self.extra = [] if extra is None else extra
        self.segs, self.cur, self.pending = [], Seg(), []
        self.word, self.has_word, self.skip_word = [], False, False

    def add(self, text):
        self.word.append(text)
        self.has_word = True

    def end_word(self):
        if self.has_word and not self.skip_word:
            self.cur.words.append("".join(self.word))
        if self.has_word:
            self.skip_word = False
        self.word, self.has_word = [], False

    def end_seg(self, piped=False):
        self.end_word()
        self.cur.piped, self.skip_word = piped, False
        self.segs.append(self.cur)
        self.cur = Seg()

    def run(self, in_subst=False):
        """Lex to the end of the text, or (in_subst) to the `)` that closes a `$(`; returns the segments."""
        s, parens = self.s, 0
        while self.i < len(s):
            c = s[self.i]
            if c in " \t\r":
                self.end_word()
                self.i += 1
            elif c == "\n":
                self.end_seg()
                self.i += 1
                self.read_heredocs()
            elif c == "\\":
                if s[self.i + 1:self.i + 2] != "\n":  # backslash-newline joins lines; else the next char is literal
                    self.add(s[self.i + 1:self.i + 2])
                self.i += 2
            elif c == "#" and not self.has_word:
                end = s.find("\n", self.i)
                self.i = len(s) if end < 0 else end
            elif c == "'":
                end = s.find("'", self.i + 1)
                end = len(s) if end < 0 else end
                self.add(s[self.i + 1:end])
                self.i = end + 1
            elif c == '"':
                self.i += 1
                self.double_quoted()
            elif c == "`" or s.startswith("$(", self.i) or s.startswith(("<(", ">("), self.i):
                self.substitution()
            elif c in "<>" or (c == "&" and s[self.i + 1:self.i + 2] == ">"):
                self.redirect()
            elif c == "(":
                parens += 1
                self.i += 1
                self.end_seg()
            elif c == ")":
                self.i += 1
                if in_subst and parens == 0:
                    break
                parens = max(parens - 1, 0)
                self.end_seg()
            elif c in ";|&":
                op = s[self.i:self.i + 2] if s[self.i:self.i + 2] in ("&&", "||", "|&", ";;") else c
                self.i += len(op)
                self.end_seg(piped=op in ("|", "|&"))
            else:
                self.add(c)
                self.i += 1
        self.end_seg()
        return self.segs

    def double_quoted(self):
        s = self.s
        self.has_word = True
        while self.i < len(s):
            c = s[self.i]
            if c == '"':
                self.i += 1
                return
            if c == "\\":
                nxt = s[self.i + 1:self.i + 2]
                if nxt in ('$', '`', '"', "\\"):
                    self.add(nxt)
                elif nxt != "\n":
                    self.add("\\" + nxt)
                self.i += 2
            elif c == "`" or s.startswith("$(", self.i):
                self.substitution()
            else:
                self.add(c)
                self.i += 1

    def nested(self, text_or_none=None, start=0):
        if self.depth >= MAX_NEST:
            raise TooDeep
        return Parser(self.s if text_or_none is None else text_or_none, start, self.depth + 1, self.extra)

    def substitution(self):
        s, i = self.s, self.i
        if s[i] == "`":
            j = i + 1
            while j < len(s) and s[j] != "`":
                j += 2 if s[j] == "\\" else 1
            self.extra.extend(self.nested(s[i + 1:j].replace("\\`", "`")).run())
            self.add(s[i:j + 1])
            self.i = j + 1
        elif s.startswith("$((", i) and self.arithmetic_end() > 0:
            end = self.arithmetic_end()
            self.add(s[i:end])  # arithmetic is opaque: `1<<y` is a shift here, not a heredoc
            self.i = end
        else:
            sub = self.nested(start=i + 2)
            self.extra.extend(sub.run(in_subst=True))
            self.add(s[i:sub.i])
            self.i = sub.i

    def arithmetic_end(self):
        """Index after the `))` closing `$((` at self.i, or -1 when it is really `$( (subshell) ... )`."""
        s, depth, k = self.s, 2, self.i + 3
        while k < len(s):
            depth += {"(": 1, ")": -1}.get(s[k], 0)
            k += 1
            if depth == 0:
                return k if s[k - 2] == ")" else -1
        return -1

    def redirect(self):
        s, i = self.s, self.i
        if s.startswith("<<", i) and not s.startswith("<<<", i):
            return self.heredoc_operator()
        if self.has_word and "".join(self.word).isdigit():  # `2>&1`: the digits are the file descriptor
            self.word, self.has_word = [], False
        else:
            self.end_word()
        op = next(o for o in ("<<<", "&>>", "&>", ">>", ">&", ">|", "<&", "<>", "<", ">") if s.startswith(o, i))
        self.i += len(op)
        self.skip_word = True  # the redirect target is a file name, not an argument

    def heredoc_operator(self):
        s, i = self.s, self.i + 2
        strip_tabs = s[i:i + 1] == "-"
        i += strip_tabs
        while s[i:i + 1] in (" ", "\t") and i < len(s):
            i += 1
        delim = []
        while i < len(s) and s[i] not in " \t\r\n;&|()<>":
            c = s[i]
            if c in "'\"":
                end = s.find(c, i + 1)
                end = len(s) if end < 0 else end
                delim.append(s[i + 1:end])
                i = end + 1
            elif c == "\\":
                delim.append(s[i + 1:i + 2])
                i += 2
            else:
                delim.append(c)
                i += 1
        self.i = i
        self.end_word()
        if delim:
            self.pending.append((self.cur, "".join(delim), strip_tabs))

    def read_heredocs(self):
        s = self.s
        for seg, delim, strip_tabs in self.pending:
            lines, closed = [], False
            while self.i < len(s) and not closed:
                end = s.find("\n", self.i)
                end = len(s) if end < 0 else end
                line = s[self.i:end]
                self.i = end + 1
                closed = (line.lstrip("\t") if strip_tabs else line) == delim
                if not closed:
                    lines.append(line)
            if closed:
                seg.bodies.append("\n".join(lines))
            else:  # never closed: Bash runs to the end of input, we check the text as commands (fail closed)
                self.extra.extend(self.nested("\n".join(lines)).run())
        self.pending = []


def parse(command):
    """All segments of a command: the top-level ones in order, then those found in substitutions."""
    parser = Parser(command)
    segs = parser.run()
    return segs + parser.extra


def normalise(tokens):
    """Strip env assignments, wrappers (sudo, env, command ...) and git global options.
    Return (command basename, args, git -c / --config-env values)."""
    while tokens:
        base = os.path.basename(tokens[0])
        if ASSIGN_RE.match(tokens[0]):
            tokens = tokens[1:]
        elif base in WRAPPERS:
            rest = tokens[1:]
            while rest and (rest[0].startswith("-") or ASSIGN_RE.match(rest[0])):
                rest = rest[2:] if rest[0] in WRAPPERS[base] else rest[1:]
            tokens = rest[WRAPPER_POSITIONALS.get(base, 0):]
            if base == "flock" and tokens[:1] in (["-c"], ["--command"]):
                tokens = ["sh"] + tokens  # flock <file> -c '<script>' runs the script in a shell
        else:
            break
    if not tokens:
        return "", [], []
    cmd, args, config = os.path.basename(tokens[0]), tokens[1:], []
    if cmd == "git":
        while args and args[0].startswith("-"):
            if args[0] == "-c" and len(args) > 1:
                config.append(args[1])
            elif args[0].startswith("--config-env="):
                config.append(args[0].split("=", 1)[1])
            args = args[2:] if args[0] in GIT_VALUE_OPTS else args[1:]
    return cmd, args, config


def reads_stdin(args):  # an interpreter runs piped input unless given inline code (-c ...) or a script/module argument
    positional = [a for a in args if not a.startswith("-")]
    return "-s" in args or "-" in args or not positional or positional[0] in STDIN_PATHS


def shell_script(args):
    """The script text of `sh -c <script>` (options and `--` between -c and the script are skipped), else None."""
    for i, a in enumerate(args):
        if a.startswith("-") and not a.startswith("--") and "c" in a:
            rest = [x for x in args[i + 1:] if not x.startswith("-")]
            return rest[0] if rest else None
    return None


def find_exec_commands(args):
    """The commands given to find -exec|-execdir|-ok|-okdir ... ; or +."""
    found, i = [], 0
    while i < len(args):
        if args[i] in FIND_EXEC:
            end = next((j for j in range(i + 1, len(args)) if args[j] in (";", "+")), len(args))
            found.append(args[i + 1:end])
            i = end
        i += 1
    return found


def check(command, depth=0):
    """Return the reason string if the command must be blocked, else None."""
    try:
        return check_segments(parse(command), depth)
    except TooDeep:
        return DEEP_REASON


def check_segments(segs, depth):
    if depth > MAX_DEPTH:
        return DEEP_REASON
    downloaded, carried = False, []  # carried: heredoc bodies of the previous command when it is piped into this one
    for seg in segs:
        if not seg.words:  # a `(` or newline after a pipe: keep the pipe state (`curl u | (sh)`)
            continue
        cmd, args, config = normalise(seg.words)
        is_shell, is_script_reader = bool(SHELL_RE.match(cmd)), bool(SHELL_RE.match(cmd) or INTERP_RE.match(cmd))
        script = shell_script(args) if is_shell else None
        if downloaded and is_script_reader and reads_stdin(args):
            return DOWNLOAD_REASON
        if downloaded and script and re.search(r"\$\(\s*cat\b|`\s*cat\b", script):
            return DOWNLOAD_REASON
        if cmd == "git" and any(v.lower().startswith("alias.") for v in config):
            return ALIAS_REASON
        for _, predicate, reason in RULES:
            if predicate(cmd, args):
                return reason
        inner_scripts = [script] if script else []
        if is_script_reader and reads_stdin(args):  # heredoc or piped heredoc text that the command runs
            inner_scripts += seg.bodies + carried
        for text in inner_scripts:
            inner = check(text, depth + 1)
            if inner:
                return inner
        for words in find_exec_commands(args) if cmd == "find" else []:
            exec_seg = Seg()
            exec_seg.words = words
            inner = check_segments([exec_seg], depth + 1)
            if inner:
                return inner
        downloaded = (downloaded or cmd in ("curl", "wget")) if seg.piped else False
        carried = seg.bodies if seg.piped else []
    return None


def main():
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
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
