#!/usr/bin/env python3
r"""PreToolUse guard for the Bash tool: a best-effort second layer behind the `deny` list in .claude/settings.json.

BEST EFFORT, NOT A SANDBOX. It catches the common ways a model reaches a blocked command by accident; it does not stop
a determined or prompt-injected one (see Known gaps). The real boundaries are the permission prompt (default mode) and an
OS sandbox. Do not rely on this hook in bypassPermissions or auto mode.

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

Covered, beyond the rules in RULES: `git` global options (`-C`, `-c`, `--git-dir`...) and `-c alias.*`, `-c clean.requireForce=false` and a
dashed git binary (`/usr/lib/git-core/git-push` is `git push`); env assignments and wrappers (sudo, env, command, time, nice,
ionice, setsid, stdbuf, flock, timeout, xargs, busybox...) including short-option clusters read like getopt (`sudo -Eu root`);
the comma form of brace expansion in an unquoted word (`git push {--force,origin}`); `dotnet build|test|run|msbuild|publish|pack`
(also after `watch`) with `-p:PreBuildEvent=` or `-p:PostBuildEvent=` (they run commands); `sh -c '<script>'`
(also after `--`); substitutions `$(...)`, backticks and `<(...)` anywhere outside single quotes; `find -exec|-execdir|-ok|-okdir
<command>`; unambiguous long-option prefixes of 3+ characters (`--recur`, `--forc`); heredocs recognised only outside quotes and
comments, with the body (or here-string word, `bash <<< '...'`) skipped as data unless it feeds a shell (checked as a script; text fed
to python, perl, node... is data, only a download piped into it is blocked) or the
closing delimiter never appears (then the rest is checked as commands in the same parser); downloads piped into a shell or
interpreter, including `/dev/stdin`, `-`, `sh -c "$(cat)"`, `busybox sh` and a `( ... )` wrapper; ANSI-C quoting `$'...'`
(decoded: \n \t \' \\ \xHH and the other common escapes) and locale quoting `$"..."`; arithmetic `$(( ))`, `(( ))` and
`$[ ]` (opaque, so `1 << 2` is a shift, not a heredoc); reserved words that hide the command (`if then elif else do while
until ! coproc function {`, and `fi done esac }` as terminators), so `for f in a; do git push -f; done` is checked.

Known gaps (not fixed; best effort, not a sandbox):
- Commands built at runtime (`$VAR`, `eval`, `source /dev/stdin`, `bash <(curl u)`, `sh -c "$(curl u)"`); commands inside
  `$(( ))`, `(( ))` and `$[ ]` arithmetic, including substitutions such as `(( $(git push -f) ))` (blocked before the
  arithmetic spans became opaque, which fixed `1 << 2` being read as a heredoc), and inside unquoted-heredoc bodies; a
  quoted `((` or `))` inside arithmetic, which shifts where the span is taken to end; `for ((...)) do` without a `;`;
  a NUL inside `$'...'` (Bash cuts the word there, e.g. `$'--force\0x'`); scripts that run a destructive command internally
  and heredoc bodies or here-strings fed to interpreters (`python3 - <<EOF`), which are not inspected at all; nesting deeper than
  MAX_NEST or MAX_DEPTH (blocked, fail closed).
- Wrapper long options that take a separate value: `sudo --user root ...`, `timeout --signal KILL 5 ...`, `nice --adjustment 5`,
  `ionice --class 3`, `env --chdir d` and `env --unset X`, `stdbuf --output L`, `xargs --max-args 1` and `xargs -a f` /
  `--arg-file f`; `env -S` / `--split-string`; `flock f --command '...'`; wrappers not listed (su -c, ssh, docker run,
  watch...).
- Brace sequences (`{a..b}`) are not expanded, and a brace expansion that yields over MAX_BRACE words is blocked (fail closed).
- dotnet: a build event set through the environment (`PostBuildEvent=cmd dotnet build`), `Directory.Build.props`, a response file
  (`@x.rsp`) or the project file. Loggers and adapters load code and are not blocked here (they have legitimate uses); the
  settings `ask` list prompts for them: `dotnet <args> -l*`, `/l*`, `-L*`, `-P*`, `/P*`, `-dl*`, `/dl*`, `-distributedlogger*`,
  `-logger*`, `--logger*` and `--test-adapter-path*`, and for any property option: `-p*`, `/p*`, `--property*`, `--p *`, `--p=*`,
  `-rp*`, `/rp*` and `-restoreProperty*`. Also asked: `--p:` (`Bash(dotnet * --p:**)`, a glob: a rule ending in `:*` is always a prefix rule,
  so `dotnet * --p:*` never matches; `dotnet * --p*` would also prompt for `--project`). Not covered by the `ask` list: an option
  that is the first argument after `dotnet` (`dotnet -l:x` has no subcommand to anchor `dotnet * -l*`), an option set through
  `@x.rsp`, `MSBUILD*` environment variables or the project file, and spellings beyond those prefixes.
- Destructive commands not covered by RULES: `git update-ref -d`, `git stash clear|drop`, `git worktree remove --force`,
  `git branch -M|-C` (force rename or copy over a branch), `gh api -X DELETE` (the settings `ask` list covers it). `gh pr merge`
  is not blocked here; it is under `ask` in settings.json, so the user is prompted.
- git: `--config-env x` and `--attr-source x` with a separated value, `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_n` /
  `GIT_CONFIG_VALUE_n` environment configuration, `-c remote.*.mirror` and `-c remote.*.push`, aliases defined in config files
  and other `-c` hooks (`core.pager`, `core.sshCommand`); `git checkout <path>`, `git checkout -f` and `git restore <file>`
  without `.`; 1-2 character long-option prefixes (`--ha`).
- Interpreters and shells: option values before stdin (`bash -o x`, `bash --rcfile f`, `python3 -W x`, `python3 -X x`,
  `perl -I d`, `node -r m`) hide that the interpreter reads stdin; `bash -c -o pipefail '...'` (option after `-c`); stdin passed
  into a nested shell (`curl u | sh -c "sh"`); uncommon shells and interpreters (mksh, pwsh, bun, lua, tclsh, `awk -f -`);
  `curl u | (cat; sh)`.
"""
import functools
import json
import os
import re
import sys

SHELL_RE = re.compile(r"^(ba|z|da|k|c|tc|fi|a)?sh$")
INTERP_RE = re.compile(r"^(python[\d.]*|perl|ruby|node|php|deno)$")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# wrapper -> options that consume the next token (stripped before matching the real command)
WRAPPERS = {"sudo": {"-u", "-g", "-h", "-p", "-r", "-t", "-C", "-D", "-R", "-T", "-U"}, "env": {"-u", "-C", "-S"}, "command": set(),
            "builtin": set(), "exec": set(), "time": set(), "nohup": set(), "nice": {"-n"}, "timeout": {"-s", "-k"},
            "xargs": {"-I", "-n", "-P", "-d", "-E", "-L", "-s"}, "setsid": set(), "stdbuf": {"-i", "-o", "-e"},
            "ionice": {"-c", "-n", "-p", "-P", "-u"}, "flock": {"-w", "-E", "--timeout", "--conflict-exit-code"},
            "busybox": set()}
WRAPPER_POSITIONALS = {"timeout": 1, "flock": 1}  # leading non-option arguments (duration, lock file) before the command
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
# Reserved words that start a command or end a compound one; the real command follows (or the next segment starts).
RESERVED_WORDS = {"if", "then", "elif", "else", "do", "while", "until", "!", "{", "fi", "done", "esac", "}"}
ANSI_ESCAPES = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v",
                "\\": "\\", "'": "'", '"': '"', "?": "?"}
ANSI_NUMERIC = re.compile(r"x[0-9A-Fa-f]{1,2}|[0-7]{1,3}|u[0-9A-Fa-f]{1,4}|U[0-9A-Fa-f]{1,8}")
STDIN_PATHS = {"-", "/dev/stdin", "/dev/fd/0", "/proc/self/fd/0"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
MAX_DEPTH = 3  # nested `sh -c`, heredoc scripts and find -exec commands
MAX_NEST = 8  # nested substitutions while lexing
MAX_BRACE = 1024  # words one brace expansion may produce; beyond it the command is blocked (fail closed)
# Unquoted `{`, `,` and `}` are kept as private-use marks while a word is lexed, so that quoted or escaped ones are not
# brace-expanded and `${x}` is left alone; the marks are mapped back when the word ends.
BRACE_MARKS = {"{": "\ue000", ",": "\ue001", "}": "\ue002"}
BRACE_OPEN, BRACE_COMMA, BRACE_CLOSE = BRACE_MARKS.values()
BRACE_RESTORE = str.maketrans({v: k for k, v in BRACE_MARKS.items()})
DOTNET_BUILD_COMMANDS = {"build", "test", "run", "msbuild", "publish", "pack"}
# A property option of dotnet/msbuild (-p, --p, -property, /p, and the restore forms -rp, -restoreProperty); the value follows a
# `:` or `=`, or is the next token. A build event in the value runs a command.
PROPERTY_OPTION = re.compile(r"^(--?|/)(p|property|rp|restoreproperty)([:=]|$)", re.IGNORECASE)
BUILD_EVENT_VALUE = re.compile(r"(pre|post)buildevent", re.IGNORECASE)
GIT_FALSE_VALUES = {"false", "no", "off", "0", ""}


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


BRANCH_VALUE_OPTIONS = ("--sort", "--format", "--points-at")  # git branch long options whose separate value may look like a flag


def branch_deletes(args):
    """git branch with -d, -D or --delete. The value after --sort, --format or --points-at is skipped (`--sort -committerdate`
    is not -d); --contains, --merged and their --no- forms only take a dash-free value, and --color and --column only an
    `=value`, so nothing is skipped after them (`--merged -D x` still deletes)."""
    kept, skip = [], False
    for a in args[1:]:
        if skip:
            skip = False
            continue
        kept.append(a)
        name = a.split("=", 1)[0]
        if a.startswith("--") and "=" not in a and any(name == f or (len(name) >= 5 and f.startswith(name)) for f in BRANCH_VALUE_OPTIONS):
            skip = True
    return has_flag(kept, "dD", "--delete")


def takes_value(option, value_options):
    """True if a wrapper option consumes the next token. A short-option cluster is read like getopt: letters are
    scanned in order, and the first one that takes a value either ends the cluster (attached value, `-uroot`) or, as the
    last letter, takes the next token (`-Eu root`)."""
    if option in value_options:
        return True
    if not option.startswith("-") or option.startswith("--") or len(option) < 3:
        return False
    for k, letter in enumerate(option[1:], 1):
        if "-" + letter in value_options:
            return k == len(option) - 1
    return False


def expand_braces(word):
    """Comma brace expansion of a word whose unquoted braces and commas are BRACE_MARKS: `--{force,x}` -> `--force`, `--x`.
    The leftmost group with a top-level comma is expanded first. `{a..b}` sequences are not expanded (Known gaps).
    Raises TooDeep when the result would pass MAX_BRACE words (counted by result words, so ten chained `{a,b}` groups, 1024
    words, are fine and eleven are blocked). Iterative, so a deeply nested group cannot hit the recursion limit."""
    out, pending = [], [word]
    while pending:
        current = pending.pop()
        best = None
        if BRACE_COMMA in current:
            stack = []
            for k, ch in enumerate(current):
                if ch == BRACE_OPEN:
                    stack.append((k, []))
                elif ch == BRACE_COMMA and stack:
                    stack[-1][1].append(k)
                elif ch == BRACE_CLOSE and stack:
                    opened, commas = stack.pop()
                    if commas and (best is None or opened < best[0]):
                        best = (opened, k, commas)
        if best is None:
            out.append(current)
        else:
            opened, closed, commas = best
            bounds = [opened, *commas, closed]
            # reversed, so the stack yields the alternatives in order
            pending.extend(current[:opened] + current[lo + 1:hi] + current[closed + 1:] for lo, hi in reversed(list(zip(bounds, bounds[1:]))))
        if len(out) + len(pending) > MAX_BRACE:  # every pending word yields at least one result
            raise TooDeep
    return out


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


def git_output_option(args):  # `--output` and `--output=<path>`; --output-indicator-* is a harmless display option
    return any(x == "--output" or x.startswith("--output=") for x in args)


def clean_unforced(config):
    """True if a git `-c clean.requireForce=<false>` (or --config-env) lets `git clean` delete without -f."""
    for value in config:
        key, _, setting = value.partition("=")
        if key.lower() == "clean.requireforce" and "=" in value and setting.strip().lower() not in ("true", "yes", "on", "1"):
            return True
    return False


def dotnet_build_event(args):
    """`dotnet [watch] build|test|run|msbuild|publish|pack` with a property override of PreBuildEvent or PostBuildEvent, which runs
    an arbitrary command: -p:X, -p=X, --p X (separated value), -property:, --property:, /p:, and the restore forms -rp:,
    /rp:, -restoreProperty:. After `--` the arguments belong to the application (`dotnet run -- -p:X`)."""
    if "--" in args:
        args = args[:args.index("--")]
    words = [x for x in args if not x.startswith("-")]
    # `dotnet watch <build command> ...` runs the same build: skip the `watch`; any later word that names a build command counts
    # (`dotnet watch --project x.csproj run`, where the option's value comes before the subcommand).
    candidates = words[1:] if words[:1] == ["watch"] else words[:1]
    if not any(x in DOTNET_BUILD_COMMANDS for x in candidates):
        return False
    for i, arg in enumerate(args):
        option = PROPERTY_OPTION.match(arg)
        if not option:
            continue
        value = arg[option.end():] or "".join(args[i + 1:i + 2])  # no attached value: the next token is the value
        if BUILD_EVENT_VALUE.search(value):
            return True
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
     "git reset --hard discards work and is blocked. Check git status or git stash instead, or ask the user to run it."),
    ("git clean force", lambda c, a: c == "git" and a[:1] == ["clean"] and has_flag(a, "f", "--force"),
     "git clean -f deletes untracked files and is blocked. List untracked files with git status and ask the user to run it."),
    ("git branch delete", lambda c, a: c == "git" and a[:1] == ["branch"] and branch_deletes(a),
     "Deleting local branches is blocked. Ask the user."),
    ("git discard changes", lambda c, a: c == "git" and discards_changes(a),
     "Discarding working-tree changes (checkout . or -- <paths>, switch -f, restore . or --source or --worktree) is blocked. Ask the user."),
    ("git --output", lambda c, a: c == "git" and a[:1] in (["log"], ["diff"], ["show"], ["whatchanged"])
     and git_output_option(a[1:]),
     "git log|diff|show --output=<path> writes files (for example .git/config) and is blocked. Redirect stdout instead."),
    ("rm -rf", lambda c, a: c == "rm" and rm_force_recursive(a),
     "rm with recursive and force together is blocked. Delete specific paths one by one, or ask the user."),
    ("dotnet build event", lambda c, a: c == "dotnet" and dotnet_build_event(a),
     "dotnet with -p:PreBuildEvent=... or -p:PostBuildEvent=... runs an arbitrary command and is blocked. Set build events in the project file, reviewed."),
    ("dotnet ef database", lambda c, a: c == "dotnet" and "ef" in a and "database" in a and bool({"update", "drop"} & set(a)),
     "dotnet ef database update|drop is blocked: migrations are reviewed first and applied by the deploy pipeline (Immutable Rule 2). Use migrations script."),
    ("terraform apply", lambda c, a: c == "terraform" and next((x for x in a if not x.startswith("-")), "") in ("apply", "destroy"),
     "terraform apply|destroy is blocked: infrastructure changes go through reviewed code and the pipeline."),
]
DOWNLOAD_REASON = "Piping a download into a shell or interpreter (curl|wget ... | sh) is blocked. Download to a file, review it, then run it."
CLEAN_REASON = "git -c clean.requireForce=false lets git clean delete untracked files without -f and is blocked. List untracked files with git status and ask the user to run it."
ALIAS_REASON = "git -c alias.* defines a command that the rules cannot see and is blocked. Run the git command directly."
DEEP_REASON = "The command nests substitutions, scripts or find -exec too deeply to inspect and is blocked. Simplify it."


@functools.lru_cache(maxsize=32)
def paren_matches(s):
    """Index of each `(` -> index of its matching `)` by raw nesting (quotes ignored), computed once per text so that many
    `((` in one command stay linear."""
    stack, pairs = [], {}
    for k, ch in enumerate(s):
        if ch == "(":
            stack.append(k)
        elif ch == ")" and stack:
            pairs[stack.pop()] = k
    return pairs


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
    quotes and comments; its body (read at the next newline) is attached to the owning segment. Where the lexer knows it
    cannot tell (an unclosed heredoc, quote or substitution) the text is checked as commands rather than skipped as data.
    It is not a full Bash grammar: forms it misreads are listed under Known gaps in the module docstring."""

    def __init__(self, s, i=0, depth=0, extra=None):
        self.s, self.i, self.depth = s, i, depth
        self.extra = [] if extra is None else extra
        self.segs, self.cur, self.pending = [], Seg(), []
        self.word, self.has_word, self.skip_word, self.herestring = [], False, False, False
        self.unclosed = set()  # heredoc (delimiter, strip_tabs) pairs already known to have no closing line

    def add(self, text):
        self.word.append(text)
        self.has_word = True

    def end_word(self):
        text = "".join(self.word)
        if self.has_word and not self.skip_word:
            variants = expand_braces(text)
            if len(variants) > 1:  # an empty result of `{,git}` is removed by Bash
                variants = [v for v in variants if v]
            self.cur.words.extend(v.translate(BRACE_RESTORE) for v in variants)
        elif self.has_word and self.herestring:  # `bash <<< 'script'`: the word is data for the command, like a heredoc body
            self.cur.bodies.append(text.translate(BRACE_RESTORE))
        if self.has_word:
            self.skip_word = self.herestring = False
        self.word, self.has_word = [], False

    def end_seg(self, piped=False):
        self.end_word()
        self.cur.piped, self.skip_word, self.herestring = piped, False, False
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
            elif s.startswith("$'", self.i):
                self.ansi_quoted()
            elif s.startswith('$"', self.i):
                self.i += 1  # locale quoting: the `$` is not part of the word, the string is a double-quoted one
            elif s.startswith("$[", self.i):
                self.legacy_arithmetic()
            elif c == "(" and s.startswith("((", self.i) and not self.has_word and self.arithmetic_end(self.i) > 0:
                end = self.arithmetic_end(self.i)  # `((x = 1 << 2))` and `for ((...))`: opaque, not heredocs
                self.add(s[self.i:end])
                self.i = end
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
                dollar_brace = c == "{" and self.i > 0 and s[self.i - 1] == "$"  # `${x}` is not a brace expansion
                self.add(c if dollar_brace else BRACE_MARKS.get(c, c))
                self.i += 1
        self.end_seg()
        return self.segs

    def ansi_quoted(self):
        """`$'...'`: backslash escapes are decoded (\\n, \\', \\xHH...), so `$'--force'` is the word `--force` and `\\'` does
        not end the string."""
        s, i = self.s, self.i + 2
        self.has_word = True
        while i < len(s) and s[i] != "'":
            if s[i] != "\\" or i + 1 >= len(s):
                self.add(s[i])
                i += 1
                continue
            nxt = s[i + 1]
            numeric = ANSI_NUMERIC.match(s, i + 1)
            if nxt in ANSI_ESCAPES:
                self.add(ANSI_ESCAPES[nxt])
                i += 2
            elif numeric:
                digits = numeric.group()
                value = int(digits[1:] if digits[0] in "xuU" else digits, 16 if digits[0] in "xuU" else 8)
                try:
                    self.add(chr(value))
                except (ValueError, OverflowError):  # beyond Unicode: keep the text
                    self.add("\\" + digits)
                i = numeric.end()
            else:
                self.add("\\" + nxt)
                i += 2
        self.i = i + 1

    def legacy_arithmetic(self):
        """`$[ ... ]`: opaque up to the matching `]`. Unclosed: the `$` is an ordinary character."""
        s, depth, k = self.s, 0, self.i + 1
        while k < len(s):
            depth += {"[": 1, "]": -1}.get(s[k], 0)
            k += 1
            if depth == 0:
                break
        if depth:
            self.add("$")
            self.i += 1
        else:
            self.add(s[self.i:k])
            self.i = k

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
        elif s.startswith("$((", i) and self.arithmetic_end(i + 1) > 0:
            end = self.arithmetic_end(i + 1)
            self.add(s[i:end])  # arithmetic is opaque: `1<<y` is a shift here, not a heredoc
            self.i = end
        else:
            sub = self.nested(start=i + 2)
            self.extra.extend(sub.run(in_subst=True))
            self.add(s[i:sub.i])
            self.i = sub.i

    def arithmetic_end(self, i):
        """Index after the `))` that closes the `((` at `i`, or -1 when it is really `( (subshell) ... )`."""
        # Bash's rule: `((` is arithmetic only when the inner `(` closes right before the outer `)`; otherwise it is
        # nested subshells such as `((a) ; (b))`, which run commands and must be lexed as such.
        pairs = paren_matches(self.s)
        close = pairs.get(i, -1)
        if close <= i + 2 or pairs.get(i + 1) != close - 1:
            return -1
        # A quote or backslash in the span can hide a paren from this raw matcher: lex it as commands (fail closed).
        return -1 if any(q in self.s[i:close] for q in "'\"\\") else close + 1

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
        self.herestring = op == "<<<"

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
            key = (delim, strip_tabs)
            match = None
            if key not in self.unclosed:
                tabs = "\t*" if strip_tabs else ""
                match = re.compile("^" + tabs + re.escape(delim) + "$", re.MULTILINE).search(s, self.i)
            if match is None:
                # Never closed: Bash runs to the end of input. Fail closed: lex the rest as commands in this same parser
                # (no nesting, so a script with several `x = 1 << 3` lines is not mistaken for deep nesting). A later
                # operator with the same delimiter cannot close either, which keeps long runs of `<<EOF` linear.
                self.unclosed.add(key)
                self.pending = []
                return
            body = s[self.i:match.start()]
            seg.bodies.append(body[:-1] if body.endswith("\n") else body)
            self.i = match.end() + 1
        self.pending = []


def parse(command):
    """All segments of a command: the top-level ones in order, then those found in substitutions."""
    parser = Parser(command)
    segs = parser.run()
    return segs + parser.extra


def normalise(tokens):
    """Strip env assignments, reserved words (if, do, !, { ...), wrappers (sudo, env, command ...) and git global options.
    Return (command basename, args, git -c / --config-env values)."""
    while tokens:
        base = os.path.basename(tokens[0])
        if ASSIGN_RE.match(tokens[0]) or tokens[0] in RESERVED_WORDS:
            tokens = tokens[1:]
        elif tokens[0] == "function":  # `function name {`: the name is not the command
            tokens = tokens[2:]
        elif tokens[0] == "coproc":  # `coproc cmd ...` or `coproc NAME { cmd; }`
            tokens = tokens[2:] if tokens[2:3] == ["{"] else tokens[1:]
        elif base in WRAPPERS:
            rest = tokens[1:]
            while rest and (rest[0].startswith("-") or ASSIGN_RE.match(rest[0])):
                rest = rest[2:] if takes_value(rest[0], WRAPPERS[base]) else rest[1:]
            tokens = rest[WRAPPER_POSITIONALS.get(base, 0):]
            if base == "flock" and tokens[:1] in (["-c"], ["--command"]):
                tokens = ["sh"] + tokens  # flock <file> -c '<script>' runs the script in a shell
        else:
            break
    if not tokens:
        return "", [], []
    cmd, args, config = os.path.basename(tokens[0]), tokens[1:], []
    if cmd.startswith("git-") and len(cmd) > 4:  # /usr/lib/git-core/git-push is `git push`
        cmd, args = "git", [cmd[4:], *args]
    if cmd == "git":
        while args and args[0].startswith("-"):
            if args[0] == "-c" and len(args) > 1:
                config.append(args[1])
            elif args[0].startswith("--config-env="):
                config.append(args[0].split("=", 1)[1])
            args = args[2:] if args[0] in GIT_VALUE_OPTS else args[1:]
    return cmd, args, config


def reads_stdin(args, is_shell):
    """A shell or interpreter runs piped input unless given inline code (-c ...) or a script/module argument. `-s` reads the
    script from stdin for a shell only (for python it skips the user site directory)."""
    positional = [a for a in args if not a.startswith("-")]
    return (is_shell and "-s" in args) or "-" in args or not positional or positional[0] in STDIN_PATHS


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
        if downloaded and is_script_reader and reads_stdin(args, is_shell):
            return DOWNLOAD_REASON
        if downloaded and script and re.search(r"\$\(\s*cat\b|`\s*cat\b", script):
            return DOWNLOAD_REASON
        if cmd == "git" and any(v.lower().startswith("alias.") for v in config):
            return ALIAS_REASON
        if cmd == "git" and args[:1] == ["clean"] and clean_unforced(config):
            return CLEAN_REASON
        for _, predicate, reason in RULES:
            if predicate(cmd, args):
                return reason
        inner_scripts = [script] if script else []
        if is_shell and reads_stdin(args, is_shell):  # heredoc or piped text that a shell runs; text fed to an interpreter is data
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
