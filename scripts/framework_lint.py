#!/usr/bin/env python3
"""Lint the agent and skill files of the framework. Standard library only (PyYAML is used as an extra
check when it happens to be installed).

    python3 scripts/framework_lint.py                 # whole framework; exit 1 on any error
    python3 scripts/framework_lint.py --strict        # size warnings become errors
    python3 scripts/framework_lint.py --staged        # only files staged in git (used by the pre-commit hook)
    python3 scripts/framework_lint.py --root <dir>    # directory holding agents/ and skills/

Checks
  frontmatter   present, valid YAML (a plain value containing ": " must be quoted), no duplicate keys
  name          equals the file name (agents/<name>.md) or the folder name (skills/<name>/SKILL.md)
  description   present, at most 1024 characters
  agents        `model` is opus, sonnet or haiku; `tools` never lists Agent or AskUserQuestion
                (subagents cannot spawn subagents or ask the user; they return open items to the caller)
  index         skills/SKILL-INDEX.md lists every skill folder and nothing else
  size          agent file <= 16 KB, skill file <= 7 KB (warning; an error with --strict)

Agents and skills live in `.claude/`. A fresh template checkout keeps them in `claude-staging/` until you
move them; the default root falls back to that folder with a notice. Files starting with `_` (for
example agents/_SHARED-PATTERNS.md) are shared documents, not agents: they are size-checked only.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS = ("opus", "sonnet", "haiku")
FORBIDDEN_TOOLS = ("Agent", "AskUserQuestion")
MAX_DESCRIPTION = 1024
MAX_AGENT_BYTES = 16 * 1024
MAX_SKILL_BYTES = 7 * 1024


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

    def warn(self, path: Path, msg: str):
        (self.errors if self.strict else self.warnings).append(f"{'ERROR' if self.strict else 'WARN'}  {path}: {msg}")


def check_file(path: Path, kind: str, expected_name: str, report: Report, reader=None) -> None:
    """kind is 'agent' or 'skill'. `reader(path) -> bytes` defaults to the working-tree file."""
    raw = reader(path) if reader else path.read_bytes()
    limit = MAX_AGENT_BYTES if kind == "agent" else MAX_SKILL_BYTES
    if len(raw) > limit:
        report.warn(path, f"{len(raw)} bytes exceeds the {limit // 1024} KB {kind} budget; move detail into a reference file or a skill")
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
    if kind == "agent":
        if data.get("model") not in MODELS:
            report.error(path, f"model {data.get('model')!r} must be one of {', '.join(MODELS)}")
        bad = [t for t in tool_names(data.get("tools")) if t in FORBIDDEN_TOOLS]
        if bad:
            report.error(path, f"tools must not list {', '.join(bad)}: subagents cannot spawn agents or ask the user; "
                               "return open items to the calling session instead")


def index_names(index_path: Path, reader=None) -> set[str]:
    names = set()
    text = reader(index_path).decode("utf-8", errors="replace") if reader else index_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.match(r"^\|\s*`?([a-z0-9][a-z0-9-]*)`?\s*\|", line)
        if m and m.group(1) not in ("skill",):
            names.add(m.group(1))
    return names


def staged_paths(repo: Path = REPO_ROOT) -> list[str]:
    proc = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
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
    for f in sorted(agents_dir.glob("*.md")) if agents_dir.is_dir() else []:
        if only is not None and f.resolve() not in only:
            continue
        if f.name.startswith("_"):
            size = len(reader(f) if reader else f.read_bytes())
            if size > MAX_AGENT_BYTES:
                report.warn(f, f"{size} bytes exceeds the {MAX_AGENT_BYTES // 1024} KB budget")
            continue
        check_file(f, "agent", f.stem, report, reader)
    skill_dirs = sorted(d for d in skills_dir.iterdir() if d.is_dir()) if skills_dir.is_dir() else []
    for d in skill_dirs:
        skill = d / "SKILL.md"
        if not skill.exists():
            report.error(d, "skill folder has no SKILL.md")
            continue
        if only is not None and skill.resolve() not in only:
            continue
        check_file(skill, "skill", d.name, report, reader)
    index = skills_dir / "SKILL-INDEX.md"
    if index.exists() and (only is None or index.resolve() in only or any(p.name == "SKILL.md" for p in only)):
        listed, present = index_names(index, reader if only is not None and index.resolve() in only else None), {d.name for d in skill_dirs if (d / "SKILL.md").exists()}
        for missing in sorted(present - listed):
            report.error(index, f"skill {missing!r} exists but is not listed in SKILL-INDEX.md")
        for ghost in sorted(listed - present):
            report.error(index, f"SKILL-INDEX.md lists {ghost!r} but skills/{ghost}/SKILL.md does not exist")
    elif not index.exists() and skill_dirs:
        report.error(skills_dir, "SKILL-INDEX.md is missing")
    return report


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
