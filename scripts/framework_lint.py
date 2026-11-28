#!/usr/bin/env python3
"""Lint the agent and skill files of the framework. Standard library only (PyYAML is used as an extra
check when it happens to be installed).

    python3 scripts/framework_lint.py                 # whole framework; exit 1 on any error
    python3 scripts/framework_lint.py --strict        # size warnings become errors
    python3 scripts/framework_lint.py --staged        # only files staged in git, staged deletions included
                                                      # (the pre-commit hook does not use it: it runs --root on a
                                                      # temp copy of the staged index)
    python3 scripts/framework_lint.py --root <dir>    # directory holding agents/ and skills/

Checks
  frontmatter   present, valid YAML (a plain value containing ": " must be quoted), no duplicate keys
  name          equals the file name (agents/<name>.md) or the folder name (skills/<name>/SKILL.md)
  description   present, at most 1024 characters
  agents        `model` is opus, sonnet or haiku; `tools` never lists Agent or AskUserQuestion
                (subagents cannot spawn subagents or ask the user; they return open items to the caller),
                an entry outside KNOWN_TOOLS and `mcp__*` is a warning (an error with --strict), and the legacy name
                `Task` is an error; `permissionMode` is one of PERMISSION_MODES
  keys          (warning) a frontmatter key outside AGENT_KEYS or SKILL_KEYS is probably a typo
  index         skills/SKILL-INDEX.md lists every skill folder and nothing else
  slices        (only when docs/slices/INDEX.md sits beside the lint root) each Mermaid `class` line matches
                the slice's Status column; see check_slice_index
  size          agent file <= 16 KB, skill file <= 7 KB (warning; an error with --strict); measured with CRLF
                normalised to LF. Other .md files inside a skill folder: no budget is stated, so a warning above
                16 KB that --strict does not turn into an error
  layout        (warning) .md files in a subfolder of agents/ are not loaded as agents (the agents folder is not
                searched recursively)
  coherence     (only when agents/_SHARED-PATTERNS.md exists, and it is itself checked as the owner) single
                owner of two shared rules: rule 7 (KB unreachable fallback) and "What blocks"; see
                check_shared_rules. It reads the working tree under the lint root, so it does not honour
                --staged's per-file reader; the pre-commit hook instead runs --root on a temp copy of the
                staged index (git checkout-index), which is how the staged content is coherence-checked.

Agents and skills live in `.claude/`. A fresh template checkout keeps them in `claude-staging/` until you
move them; the default root falls back to that folder with a notice. Files starting with `_` (for
example agents/_SHARED-PATTERNS.md) are shared documents, not agents: they are size-checked only.
"""
import sys  # builtin: cannot be shadowed. Nothing else is imported before the next statement (not even `from __future__`, which imports a module)
if __name__ == "__main__" and not sys.flags.isolated and not getattr(sys.flags, "safe_path", False) and sys.path and sys.path[0]:
    del sys.path[0]  # the script directory: a planted scripts/<stdlib-name>.* must not shadow the standard library (OD-032)

import argparse
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS = ("opus", "sonnet", "haiku")
FORBIDDEN_TOOLS = ("Agent", "AskUserQuestion")
KNOWN_TOOLS = ("Read", "Write", "Edit", "Grep", "Glob", "Bash", "Skill", "Agent", "WebFetch", "WebSearch",
               "NotebookEdit", "TodoWrite")  # plus any `mcp__*` tool; FORBIDDEN_TOOLS have their own error
LEGACY_TOOLS = {"Task": "Agent"}
PERMISSION_MODES = ("default", "acceptEdits", "plan", "dontAsk", "bypassPermissions", "auto")
AGENT_KEYS = ("name", "description", "tools", "disallowedTools", "model", "effort", "color", "memory", "permissionMode",
              "maxTurns", "skills", "hooks", "mcpServers", "isolation", "background", "initialPrompt")
SKILL_KEYS = ("name", "description", "when_to_use", "allowed-tools", "disable-model-invocation", "user-invocable",
              "argument-hint", "model", "effort", "context", "agent", "hooks", "license", "metadata", "version", "paths")
MAX_SKILL_SUPPORT_BYTES = 16 * 1024
MAX_DESCRIPTION = 1024
MAX_AGENT_BYTES = 16 * 1024
MAX_SKILL_BYTES = 7 * 1024
SHARED_FILE = "_SHARED-PATTERNS.md"
KB_TOOL_PREFIXES = ("mcp__business-kb", "mcp__qa-kb")
# Agents without Bash by design. rule 7 names them as authoring agents but does not state that they have no Bash; the shared file's "Common Tool Permissions" table does
# (Analysts and prompt-engineer rows), and check_shared_rules cross-checks the constant against that table.
NO_BASH_AGENTS = ("requirements-analyst", "solution-architect", "prompt-engineer")
# Agents whose output contract lists unverified items; each must name the field `unverified`, defined once in the shared
# file's "Finding form". The two retired field names must not come back anywhere under the lint root.
REVIEWER_AGENTS = ("security-engineer", "documentation-reviewer", "infrastructure-engineer", "quality-guardian",
                   "regression-detective", "ux-usability-specialist")
RETIRED_UNVERIFIED_FIELDS = ("areas_not_reviewed", "coverage_gaps")
# Contract form: a JSON key `"unverified":` or a table row whose first cell is `unverified` (quality-guardian, regression-detective).
UNVERIFIED_FIELD = r'"unverified"\s*:|^\|\s*`?unverified`?\s*\|'
UNVERIFIED_DEFINITION = r"^Field `unverified`"
RETIRED_PHRASE = r"coverage gaps?"
# No-Bash agents that must name `probe_requests` (defined in the shared file, Subagent Limits).
PROBE_AGENTS = ("requirements-analyst", "solution-architect")
KB_UNREACHABLE = r"\bKB\b.{0,20}?unreachable"
BLOCK_WORD = r"\bblock(?:s|ing|ed)?\b"
BLOCKING_STATUSES = ("ungrounded", "fabricated-citation", "stale", "conflict", "gate-failure")


# ------------------------------------------------------------------ frontmatter


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Return (frontmatter block, body). The block ends at the first line that is exactly `---`."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].rstrip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None, text


_DQ = re.compile(r'^"(?:[^"\\]|\\.)*"$')
_SQ = re.compile(r"^'(?:[^']|'')*'$")


def _scalar(raw: str, where: str, errors: list[str]):
    raw = raw.strip()
    if raw.startswith('"'):
        if not _DQ.match(raw):
            errors.append(f"{where}: malformed double-quoted value")
        return raw[1:-1]
    if raw.startswith("'"):
        if not _SQ.match(raw):
            errors.append(f"{where}: malformed single-quoted value")
        return raw[1:-1].replace("''", "'")
    if raw.startswith("[") or raw.startswith("{"):
        if raw.startswith("{"):
            errors.append(f"{where}: inline mappings are not supported in frontmatter")
            return raw
        if not raw.endswith("]"):
            errors.append(f"{where}: unterminated [ list")
            return []
        inner = raw[1:-1].strip()
        return [_scalar(p, where, errors) for p in inner.split(",")] if inner else []
    raw = re.split(r"\s#", raw, maxsplit=1)[0].rstrip()  # trailing comment
    if ": " in raw or raw.endswith(":"):
        errors.append(f'{where}: a plain value containing ": " is invalid YAML; wrap the value in double quotes')
    if raw[:1] in "@`%*&!|>":
        errors.append(f"{where}: a plain value cannot start with {raw[:1]!r}; wrap it in double quotes")
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    return raw


def parse_frontmatter(block: str) -> tuple[dict, list[str]]:
    """Parse the YAML subset used in frontmatter: scalars, quoted strings, [a, b], '- item' lists, > and | blocks."""
    data: dict = {}
    errors: list[str] = []
    lines = block.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        n = i + 1
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":
            errors.append(f"line {n}: unexpected indentation")
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):(?:[ \t]+(.*))?$", line)
        if not m:
            errors.append(f"line {n}: expected `key: value`, got {line[:50]!r}")
            continue
        key, val = m.group(1), (m.group(2) or "").rstrip()
        if key in data:
            errors.append(f"line {n}: duplicate key {key!r}")
        cont: list[str] = []
        while i < len(lines) and (not lines[i].strip() or lines[i][0] in " \t"):
            cont.append(lines[i])
            i += 1
        while cont and not cont[-1].strip():
            cont.pop()
        if re.fullmatch(r"[>|][+-]?\d*", val):
            parts = [c.strip() for c in cont]
            data[key] = ("\n" if val[0] == "|" else " ").join(p for p in parts if p or val[0] == "|")
        elif val == "":
            items = [c.strip() for c in cont if c.strip()]
            if items and all(c.startswith("- ") for c in items):
                data[key] = [_scalar(c[2:], f"line {n} ({key})", errors) for c in items]
            elif items:
                data[key] = " ".join(items)
            else:
                data[key] = ""
        else:
            value = _scalar(val, f"line {n} ({key})", errors)
            if cont and isinstance(value, str) and val[:1] not in "\"'":
                value = " ".join([value] + [c.strip() for c in cont if c.strip()])
            elif any(c.strip() for c in cont):
                errors.append(f"line {n}: unexpected indented text after a quoted or list value")
            data[key] = value
    return data, errors


def _split_top_level(text: str) -> list[str]:
    """Split on commas that are not inside parentheses, so `Agent(a, b)` stays one entry."""
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def tool_names(value) -> list[str]:
    """Tool names from `tools` (comma-separated string or list), each cut before any `(`:
    `Agent(worker)` is the tool `Agent`; `Bash(git diff:*)` is `Bash`."""
    raw = [str(v) for v in value] if isinstance(value, list) else _split_top_level(str(value or ""))
    return [r.split("(", 1)[0].strip() for r in raw if r.strip()]


# ------------------------------------------------------------------ checks


class Report:
    def __init__(self, strict: bool):
        self.strict = strict
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, path: Path, msg: str):
        self.errors.append(f"ERROR {path}: {msg}")

    def advise(self, path: Path, msg: str):
        """A warning that --strict never turns into an error (no budget or rule states a limit)."""
        self.warnings.append(f"WARN  {path}: {msg}")

    def warn(self, path: Path, msg: str):
        (self.errors if self.strict else self.warnings).append(f"{'ERROR' if self.strict else 'WARN'}  {path}: {msg}")


def check_file(path: Path, kind: str, expected_name: str, report: Report, reader=None) -> None:
    """kind is 'agent' or 'skill'. `reader(path) -> bytes` defaults to the working-tree file."""
    raw = reader(path) if reader else path.read_bytes()
    limit = MAX_AGENT_BYTES if kind == "agent" else MAX_SKILL_BYTES
    size = len(raw.replace(b"\r\n", b"\n"))  # a CRLF checkout must not count its extra bytes
    if size > limit:
        report.warn(path, f"{size} bytes exceeds the {limit // 1024} KB {kind} budget; move detail into a reference file or a skill")
    block, _ = split_frontmatter(raw.decode("utf-8", errors="replace"))
    if block is None:
        report.error(path, "missing frontmatter: the file must start with a line `---` and close with a line `---`")
        return
    data, problems = parse_frontmatter(block)
    for p in problems:
        report.error(path, f"frontmatter {p}")
    try:  # extra validity check when PyYAML is installed
        import yaml  # type: ignore
        try:
            loaded = yaml.safe_load(block)
            if not isinstance(loaded, dict):
                report.error(path, "frontmatter is not a YAML mapping")
        except yaml.YAMLError as exc:
            report.error(path, f"frontmatter is not valid YAML: {str(exc).splitlines()[0]}")
    except ImportError:
        pass

    name = data.get("name")
    if not name or not isinstance(name, str):
        report.error(path, "missing `name`")
    elif name != expected_name:
        report.error(path, f"name {name!r} must equal {expected_name!r}")
    desc = data.get("description")
    if not desc or not isinstance(desc, str):
        report.error(path, "missing `description`")
    elif len(desc) > MAX_DESCRIPTION:
        report.error(path, f"description is {len(desc)} characters; the limit is {MAX_DESCRIPTION}")
    unknown = sorted(k for k in data if k not in (AGENT_KEYS if kind == "agent" else SKILL_KEYS))
    if unknown:
        report.advise(path, f"unknown frontmatter key(s) {', '.join(unknown)}; check the spelling "
                            f"(known: {', '.join(AGENT_KEYS if kind == 'agent' else SKILL_KEYS)})")
    if kind == "agent":
        mode = data.get("permissionMode")
        if mode is not None and mode not in PERMISSION_MODES:
            report.error(path, f"permissionMode {mode!r} must be one of {', '.join(PERMISSION_MODES)}")
        if data.get("model") not in MODELS:
            report.error(path, f"model {data.get('model')!r} must be one of {', '.join(MODELS)}")
        bad = [t for t in tool_names(data.get("tools")) if t in FORBIDDEN_TOOLS]
        if bad:
            report.error(path, f"tools must not list {', '.join(bad)}: subagents cannot spawn agents or ask the user; "
                               "return open items to the calling session instead")
        for t in tool_names(data.get("tools")):
            if t in LEGACY_TOOLS:
                report.error(path, f"tool {t!r} is the legacy name of {LEGACY_TOOLS[t]!r} (and subagents must not list it)")
            elif t not in KNOWN_TOOLS and t not in FORBIDDEN_TOOLS and not t.startswith("mcp__"):
                # A warning, not an error: Claude Code adds tools over time, so a name outside the list may be new
                # rather than a typo. --strict turns it into an error.
                report.warn(path, f"unknown tool {t!r} (typo, or a tool newer than this list?); known: "
                                  f"{', '.join(KNOWN_TOOLS)} or an mcp__<server>__<tool> name")


def index_names(index_path: Path, reader=None) -> set[str]:
    names = set()
    text = reader(index_path).decode("utf-8", errors="replace") if reader else index_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.match(r"^\|\s*`?([a-z0-9][a-z0-9-]*)`?\s*\|", line)
        if m and m.group(1) not in ("skill",):
            names.add(m.group(1))
    return names


def staged_paths(repo: Path = REPO_ROOT) -> list[str]:
    """Staged paths, deletions included (deleting a skill must update SKILL-INDEX.md)."""
    proc = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACDMR"],
                          cwd=repo, text=True, capture_output=True)
    if proc.returncode != 0:
        sys.exit(f"git diff --cached failed: {proc.stderr.strip()}")
    return [p for p in proc.stdout.splitlines() if p]


def staged_reader(repo: Path = REPO_ROOT):
    """Reader returning the STAGED blob (`git show :path`), not the working-tree file, so what is linted is
    what would be committed."""
    def read(path: Path) -> bytes:
        rel = path.resolve().relative_to(repo.resolve()).as_posix()
        proc = subprocess.run(["git", "show", f":{rel}"], cwd=repo, capture_output=True)
        if proc.returncode != 0:
            raise OSError(f"{rel} is not staged: {proc.stderr.decode(errors='replace').strip()}")
        return proc.stdout
    return read


def resolve_root(arg: str | None) -> Path:
    if arg:
        return Path(arg).resolve()
    primary, fallback = REPO_ROOT / ".claude", REPO_ROOT / "claude-staging"
    if primary.is_dir():
        return primary
    if fallback.is_dir():
        print("notice: .claude/ not found; linting claude-staging/ (move it to .claude/ when you adopt the template)",
              file=sys.stderr)
        return fallback
    sys.exit("error: neither .claude/ nor claude-staging/ exists; pass --root <dir>")


def lint(root: Path, strict: bool = False, only: set[Path] | None = None, reader=None) -> Report:
    """Lint everything under `root`, or only the files in `only` (absolute paths) when given.
    `reader` supplies file bytes (the staged blob for --staged)."""
    report = Report(strict)
    agents_dir, skills_dir = root / "agents", root / "skills"

    def in_index(f: Path) -> bool:
        """False for a staged path that is gone from the index (`git rm --cached` leaves the working copy):
        such a file is a deletion, not something to read or to count as present."""
        if reader is None or only is None or f.resolve() not in only:
            return True
        try:
            reader(f)
        except OSError:
            return False
        return True

    for f in sorted(agents_dir.glob("*.md")) if agents_dir.is_dir() else []:
        if (only is not None and f.resolve() not in only) or not in_index(f):
            continue
        if f.name.startswith("_"):
            size = len((reader(f) if reader else f.read_bytes()).replace(b"\r\n", b"\n"))
            if size > MAX_AGENT_BYTES:
                report.warn(f, f"{size} bytes exceeds the {MAX_AGENT_BYTES // 1024} KB budget")
            continue
        check_file(f, "agent", f.stem, report, reader)
    for f in sorted(agents_dir.rglob("*.md")) if agents_dir.is_dir() else []:
        if f.parent != agents_dir and (only is None or f.resolve() in only):
            report.advise(f, "is in a subfolder of agents/, which is not searched: it will not load as an agent; "
                             "move it up one level or rename the folder away from agents/")
    skill_dirs = sorted(d for d in skills_dir.iterdir() if d.is_dir()) if skills_dir.is_dir() else []
    for d in skill_dirs:
        skill = d / "SKILL.md"
        if not skill.exists():
            report.error(d, "skill folder has no SKILL.md")
            continue
        for f in sorted(d.rglob("*.md")):
            if f != skill and (only is None or f.resolve() in only) and in_index(f):
                size = len((reader(f) if reader else f.read_bytes()).replace(b"\r\n", b"\n"))
                if size > MAX_SKILL_SUPPORT_BYTES:
                    report.advise(f, f"{size} bytes; supporting skill files have no stated budget, "
                                     f"consider splitting past {MAX_SKILL_SUPPORT_BYTES // 1024} KB")
        if (only is not None and skill.resolve() not in only) or not in_index(skill):
            continue
        check_file(skill, "skill", d.name, report, reader)
    index = skills_dir / "SKILL-INDEX.md"
    if index.exists() and (only is None or index.resolve() in only
                                or any(skills_dir.resolve() in p.parents for p in only)):
        listed, present = index_names(index, reader if only is not None and index.resolve() in only else None), {d.name for d in skill_dirs if (d / "SKILL.md").exists() and in_index(d / "SKILL.md")}
        for missing in sorted(present - listed):
            report.error(index, f"skill {missing!r} exists but is not listed in SKILL-INDEX.md")
        for ghost in sorted(listed - present):
            report.error(index, f"SKILL-INDEX.md lists {ghost!r} but skills/{ghost}/SKILL.md does not exist")
    elif not index.exists() and skill_dirs:
        report.error(skills_dir, "SKILL-INDEX.md is missing")
    check_shared_rules(root, report)
    check_slice_index(root, report)
    return report


def _rule7(shared: str) -> str | None:
    m = re.search(r"^7\. KB MCP unreachable.*(?:\n[ \t]+.*)*", shared, re.M)
    return m.group(0) if m else None


def check_shared_rules(root: Path, report: Report) -> None:
    """Keep two rules in one place: Never Invent rule 7 and "What blocks" (both in agents/_SHARED-PATTERNS.md).
    Skipped when the shared file is absent. All checks read the working tree under `root`.

    rule 7   outside the shared file no .md file under root has `python3 scripts/kb/search.py`, the phrase
             a list bullet starting "Neither works", or `scripts/kb/search.py` in an agent file; any line saying "KB unreachable" /
             "KB MCP unreachable" must say "rule 7"; every agent with KB MCP tools has such a line.
    blocks   outside the shared file no .md file has "still blocking" or a table header cell "Blocking when"; a line with
             at least 3 of the five blocking statuses and the word "block" must name "What blocks"
             (a line merely enumerating statuses, e.g. an output enum, has no "block" and passes).
    unverified  *.md files only (the shared file included): none uses a retired field name
             (RETIRED_UNVERIFIED_FIELDS) or the phrase "coverage gaps" (case-insensitive); the shared file defines
             the field (a line starting "Field `unverified`"); every agent in REVIEWER_AGENTS has the contract form,
             a JSON key `"unverified":` or a table row whose first cell is `unverified`
    probes   the shared file defines `probe_requests`; every agent in PROBE_AGENTS names it; a name in either list
             with no agent file is an error (fail closed)
    tools    agents in NO_BASH_AGENTS (checked against Common Tool Permissions) must not list Bash; every other
             agent with KB MCP tools must list Bash; every agent named in rule 7 has a file."""
    shared_path = root / "agents" / SHARED_FILE
    if not shared_path.is_file():
        return
    shared = shared_path.read_text(encoding="utf-8")
    rule7 = _rule7(shared)
    if rule7 is None:
        report.error(shared_path, "Never Invent rule 7 ('7. KB MCP unreachable ...') not found")
        return
    agents_dir = root / "agents"
    agent_files = {f.stem: f for f in sorted(agents_dir.glob("*.md")) if not f.name.startswith("_")}

    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for old in RETIRED_UNVERIFIED_FIELDS:
            if old in text:
                report.error(path, f"uses the retired field name `{old}`; unverified items go in `unverified` "
                                   f"(defined once in {SHARED_FILE}, Finding form)")
        if re.search(RETIRED_PHRASE, text, re.I):
            report.error(path, "uses the retired phrase 'coverage gaps'; unverified items go in `unverified`, "
                               "undocumented surface is an `incomplete` finding")
        if path == shared_path:
            continue
        is_agent = path.parent == agents_dir
        if re.search(r"python3?\s+scripts/kb/search\.py", text):
            report.error(path, "restates the rule 7 CLI fallback (`python3 scripts/kb/search.py`); "
                               f"point to {SHARED_FILE} Never Invent rule 7 instead")
        elif is_agent and "scripts/kb/search.py" in text:
            report.error(path, f"mentions scripts/kb/search.py; the KB fallback lives only in {SHARED_FILE} rule 7")
        if re.search(r"^[ \t]*[-*][ \t]+neither\s+works", text, re.I | re.M):
            report.error(path, f"restates the rule 7 branches ('Neither works'); point to {SHARED_FILE} rule 7")
        if re.search(r"still blocking", text, re.I):
            report.error(path, f"contains 'still blocking'; blocking is decided only by {SHARED_FILE} 'What blocks'")
        if any(ln.lstrip().startswith("|") and any(c.strip().lower() == "blocking when" for c in ln.split("|"))
               for ln in text.splitlines()):
            report.error(path, f"has a 'Blocking when' column; blocking is decided only by {SHARED_FILE} 'What blocks'")
        for n, line in enumerate(text.splitlines(), 1):
            if re.search(KB_UNREACHABLE, line, re.I) and not re.search(r"rule 7", line, re.I):
                report.error(path, f"line {n}: 'KB unreachable' must point to Never Invent 'rule 7'")
            if re.search(BLOCK_WORD, line, re.I) and "What blocks" not in line \
                    and sum(s in line for s in BLOCKING_STATUSES) >= 3:
                report.error(path, f"line {n}: lists the blocking statuses as a decision; "
                                   f"blocking is decided only by {SHARED_FILE} 'What blocks'; name it instead of copying it")

    for name in sorted(set(re.findall(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`", rule7))):
        if not name.endswith("-kb") and name not in agent_files:
            report.error(shared_path, f"rule 7 names agent {name!r} but agents/{name}.md does not exist")

    section = re.search(r"^## Common Tool Permissions[ \t]*\n(.*?)(?=^## |\Z)", shared, re.M | re.S)
    perm_rows = [ln for ln in section.group(1).splitlines() if ln.startswith("|")] if section else []
    if section is None:
        report.error(shared_path, "section '## Common Tool Permissions' not found; NO_BASH_AGENTS cannot be verified")
    for name in NO_BASH_AGENTS if section else ():
        rows = [ln for ln in perm_rows if f"`{name}`" in ln]
        if not rows or any("Bash" in ln for ln in rows):
            report.error(shared_path, f"NO_BASH_AGENTS lists {name!r} but the Common Tool Permissions table "
                                      "has no Bash-free row for it; update the table or NO_BASH_AGENTS in framework_lint.py")

    if not re.search(UNVERIFIED_DEFINITION, shared, re.M):
        report.error(shared_path, "the Finding form paragraph does not define the field (a line starting \"Field `unverified`\")")
    if "probe_requests" not in shared:
        report.error(shared_path, "Subagent Limits does not define `probe_requests`")
    for name in REVIEWER_AGENTS + PROBE_AGENTS:
        if name not in agent_files:
            report.error(agents_dir, f"{name!r} is listed in REVIEWER_AGENTS or PROBE_AGENTS but agents/{name}.md does not exist; "
                                     "update the constant in framework_lint.py")
    for name in REVIEWER_AGENTS:
        if name in agent_files and not re.search(UNVERIFIED_FIELD, agent_files[name].read_text(encoding="utf-8", errors="replace"), re.M):
            report.error(agent_files[name], 'reviewer contract lacks the `unverified` field: add a JSON key "unverified": '
                                            f"or a field-table row `unverified` (see {SHARED_FILE}, Finding form)")
    for name in PROBE_AGENTS:
        if name in agent_files and "probe_requests" not in agent_files[name].read_text(encoding="utf-8", errors="replace"):
            report.error(agent_files[name], f"no-Bash agent does not name `probe_requests` (see {SHARED_FILE}, Subagent Limits)")

    for name, path in agent_files.items():
        block, _ = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        data = parse_frontmatter(block)[0] if block is not None else {}
        tools = tool_names(data.get("tools"))
        has_kb = any(t.startswith(KB_TOOL_PREFIXES) for t in tools)
        if name in NO_BASH_AGENTS and "Bash" in tools:
            report.error(path, "tools lists Bash but this agent has none by design (rule 7 fallback is Read/Grep only)")
        if has_kb and name not in NO_BASH_AGENTS and "Bash" not in tools:
            report.error(path, "has KB MCP tools but no Bash: rule 7 sends it to the CLI fallback, which needs Bash")
        if has_kb and not any(re.search(KB_UNREACHABLE, ln, re.I) and re.search(r"rule 7", ln, re.I)
                              for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()):
            report.error(path, "has KB MCP tools but no 'KB unreachable' line pointing to rule 7")


SLICE_STATUS_CLASS = {"proposed": "proposed", "analysed": "proposed", "ready": "proposed",
                      "in progress": "inprogress", "done": "done", "blocked": "blocked"}


def check_slice_index(root: Path, report: Report) -> None:
    """The Mermaid `class` lines in docs/slices/INDEX.md are hand edited; keep them equal to the Status column.
    Skipped when the file is absent. Every table row `VS-nnn` needs a node `VSnnn` in the graph (opened by `[`, `(`
    or `{`), a class that names it (`class A,B name`, trailing `;` optional, or `VSnnn:::name`) and the class
    SLICE_STATUS_CLASS gives for its status. Errors: an unknown status, a row with a different cell count than
    the header, and a file that has `VS-` rows but no header with an `Id` and a `Status` column (case-insensitive)."""
    index = root.parent / "docs" / "slices" / "INDEX.md"
    if not index.is_file():
        return
    text = index.read_text(encoding="utf-8")
    status: dict[str, str] = {}
    cols: list[str] = []
    status_tables = 0
    any_rows = False
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            cols = []
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if re.fullmatch(r"VS-\d+", cells[0]):
            any_rows = True
        if cells[0].lower() == "id":
            cols = [c.lower() for c in cells]
            status_tables += "status" in cols
        elif cols and re.fullmatch(r"VS-\d+", cells[0]):
            if len(cells) != len(cols):
                report.error(index, f"{cells[0]}: {len(cells)} cells, the header has {len(cols)}")
            elif "status" in cols:
                status[cells[0].replace("-", "")] = cells[cols.index("status")]
    if any_rows and not status_tables:
        report.error(index, "slice rows found but no table header with an Id and a Status column")
        return
    block = re.search(r"```mermaid\n(.*?)```", text, re.S)
    graph = block.group(1) if block else ""
    nodes = set(re.findall(r"\b(VS\d+)\s*[\[({]", graph))
    classed: dict[str, str] = {}
    for m in re.finditer(r"^\s*class\s+([\w,\s]+?)\s+(\w+)\s*;?\s*(?:%%.*)?$", graph, re.M):
        for n in re.split(r"[,\s]+", m.group(1).strip()):
            classed[n] = m.group(2)
    for m in re.finditer(r"\b(VS\d+)(?:\s*(?:\[[^\]\n]*\]|\([^)\n]*\)|\{[^}\n]*\}))?:::(\w+)", graph):
        classed[m.group(1)] = m.group(2)
    for node, st in sorted(status.items()):
        want = SLICE_STATUS_CLASS.get(st.lower())
        if want is None:
            report.error(index, f"{node[:2]}-{node[2:]}: unknown Status {st!r}")
        elif node not in nodes:
            report.error(index, f"{node[:2]}-{node[2:]} has no node in the Mermaid graph")
        elif classed.get(node) != want:
            report.error(index, f"{node[:2]}-{node[2:]}: Status {st!r} needs Mermaid class {want!r}, found {classed.get(node)!r}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help="directory holding agents/ and skills/ (default: .claude, else claude-staging)")
    ap.add_argument("--strict", action="store_true", help="treat size warnings as errors")
    ap.add_argument("--staged", action="store_true", help="lint only files staged in git")
    args = ap.parse_args(argv)

    root = resolve_root(args.root)
    only = None
    if args.staged:
        only = {(REPO_ROOT / p).resolve() for p in staged_paths()
                if (REPO_ROOT / p).resolve().is_relative_to(root.resolve())}
        if not only:
            return 0
    report = lint(root, args.strict, only, staged_reader() if args.staged else None)
    for line in report.warnings + report.errors:
        print(line)
    scope = "staged files" if only is not None else str(root.relative_to(REPO_ROOT) if root.is_relative_to(REPO_ROOT) else root)
    print(f"framework lint ({scope}): {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
