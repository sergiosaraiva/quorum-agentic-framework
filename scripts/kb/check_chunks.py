#!/usr/bin/env python3
"""Lint KB chunks and Q&A records; optionally regenerate kb/TOC.md.

    python3 scripts/kb/check_chunks.py             # lint both; exit 1 on any error
    python3 scripts/kb/check_chunks.py --write-toc # also rewrite kb/TOC.md

Chunk rules: frontmatter has chunk_id/title/topics/links/sources; ids unique and match the filename;
every link resolves; body within WORD_MIN..WORD_MAX words; no self-link.
Record rules: id/kind/title/status/decider/asked present; id unique, prefix matches kind and equals the filename
stem; status valid; `priority` (when given) is P1|P2|P3; `asked` and `answered` (when given) are YYYY-MM-DD; a
frontmatter key may appear only once (chunks too); related ids and chunk ids resolve;
answered/decided records contain an Answer or Decision section.
A malformed file is reported as `ERROR <file>: ...`; it never aborts the run.
Accepted-risk rules (kind OD only): `accepted_risk` is true/false and allowed only on OD; true requires `expires`
(YYYY-MM-DD, after the `answered`, else `asked`, date), a `related` BQ/TQ record and a non-empty `## Decision`;
`expires` without `accepted_risk: true` is an error. An accepted risk past `expires` is a WARNING (exit code unchanged).
Symmetry (WARNING): a record that lists `related: X` while X does not list it back.
Id collisions (WARNING, opt-in, offline): `--against REF` compares record ids with the records on another git ref
(a local branch, or a remote-tracking branch from your last fetch) and warns when the same id carries a different title.
It cannot see ids that exist only on a branch you have not fetched; fetch first.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import lib

WORD_MIN, WORD_MAX = 40, 350
ID_RE = re.compile(r"^[A-Z]{2,4}-\d{3,}$")


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _date(value) -> date | None:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _decision_text(body: str) -> str:
    m = re.search(r"^## Decision\b[^\n]*\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    return m.group(1).strip() if m else ""


def check_accepted_risk(r: lib.Record, name: str, errors: list[str], warnings: list[str], today: date) -> None:
    """Rules for the optional `accepted_risk` / `expires` fields (kept in Record.extra by the loader)."""
    has_flag, has_expires = "accepted_risk" in r.extra, "expires" in r.extra
    if not has_flag and not has_expires:
        return
    flag, expires = r.extra.get("accepted_risk"), r.extra.get("expires")
    if has_flag:
        if r.kind != "OD":
            errors.append(f"{name}: accepted_risk is allowed only on kind OD")
        if not isinstance(flag, bool):
            hint = " (unquote the value: accepted_risk: true)" if isinstance(flag, str) and flag.lower() in ("true", "false") else ""
            errors.append(f"{name}: accepted_risk must be true or false, got {flag!r}{hint}")
    if has_expires and flag is not True:
        errors.append(f"{name}: expires requires accepted_risk: true")
    if flag is not True or r.kind != "OD":
        return
    exp = _date(expires)
    if not has_expires or expires in ("", []):
        errors.append(f"{name}: accepted_risk true requires expires: YYYY-MM-DD")
    elif exp is None:
        hint = " (no trailing comment: expires: 2026-12-31)" if isinstance(expires, str) and re.match(
            r"^\d{4}-\d{2}-\d{2}\s+#", expires) else ""
        errors.append(f"{name}: expires {expires!r} is not a valid YYYY-MM-DD date{hint}")
    else:
        ref_field = "answered" if r.extra.get("answered") not in (None, "", []) else "asked"
        ref = _date(r.extra.get("answered")) if ref_field == "answered" else _date(r.asked)
        if ref is None:
            errors.append(f"{name}: accepted_risk needs a valid {ref_field} date (YYYY-MM-DD) to check expires against")
        elif exp <= ref:
            errors.append(f"{name}: expires {expires} must be after {ref_field} {ref.isoformat()}")
        if exp < today and r.status != "closed":
            warnings.append(f"{name}: accepted risk expired on {expires}; re-decide or close it")
    if not any(o.startswith(("BQ-", "TQ-")) for o in r.related):
        errors.append(f"{name}: accepted_risk needs a related BQ/TQ record (the question that raised it)")
    if not _decision_text(r.body):
        errors.append(f"{name}: accepted_risk needs a non-empty '## Decision' section")


PRIORITIES = ("P1", "P2", "P3")


def lint(kb_dir: Path = lib.KB_DIR, qa_dir: Path = lib.QA_DIR, today: date | None = None,
         warnings: list[str] | None = None, counts: dict[str, int] | None = None) -> list[str]:
    """Return the errors. Warnings (which never fail the run) are appended to `warnings` when a list is given;
    `counts`, when given, receives the number of chunks and records that parsed; `today` defaults to date.today()."""
    today = today or date.today()
    warnings = warnings if warnings is not None else []
    errors: list[str] = []
    chunks, records = [], []
    for p in sorted((kb_dir / "chunks").glob("*.md")):
        try:
            chunks.append(lib.chunk_from_file(p))
        except (ValueError, OSError) as exc:
            errors.append(f"{p.name}: {exc}")
    for p in sorted((qa_dir / "records").glob("*.md")):
        try:
            records.append(lib.record_from_file(p))
        except (ValueError, OSError) as exc:
            errors.append(f"{p.name}: {exc}")
    if counts is not None:
        counts.update(chunks=len(chunks), records=len(records))

    ids: dict[str, str] = {}
    for c in chunks:
        name = Path(c.path).name
        if not c.chunk_id:
            errors.append(f"{name}: missing chunk_id")
            continue
        if not ID_RE.match(c.chunk_id):
            errors.append(f"{name}: chunk_id {c.chunk_id!r} must look like BC-001")
        if c.chunk_id in ids:
            errors.append(f"{name}: duplicate chunk_id {c.chunk_id} (also {ids[c.chunk_id]})")
        ids[c.chunk_id] = name
        if not name.startswith(c.chunk_id):
            errors.append(f"{name}: filename should start with the chunk_id {c.chunk_id}")
        if not c.title:
            errors.append(f"{name}: missing title")
        if not c.topics:
            errors.append(f"{name}: needs at least one topic")
        if not c.sources:
            errors.append(f"{name}: needs at least one source (use 'example: invented' for examples)")
        if not WORD_MIN <= c.word_count <= WORD_MAX:
            errors.append(f"{name}: body has {c.word_count} words, allowed {WORD_MIN}-{WORD_MAX}")
        for t in c.links:
            if t == c.chunk_id:
                errors.append(f"{name}: links to itself")
            elif t not in {x.chunk_id for x in chunks}:
                errors.append(f"{name}: link {t} does not resolve")

    rids: dict[str, str] = {}
    chunk_ids = {c.chunk_id for c in chunks}
    for r in records:
        name = Path(r.path).name
        if not r.id:
            errors.append(f"{name}: missing id")
        elif Path(r.path).stem != r.id:
            errors.append(f"{name}: filename must be {r.id}.md (the record id)")
        if r.id in rids:
            errors.append(f"{name}: duplicate record id {r.id}")
        rids[r.id] = name
        if r.kind not in lib.RECORD_KINDS:
            errors.append(f"{name}: kind {r.kind!r} not in {lib.RECORD_KINDS}")
        elif not r.id.startswith(r.kind + "-") or not ID_RE.match(r.id):
            errors.append(f"{name}: id {r.id!r} must be {r.kind}-NNN")
        if r.status not in lib.RECORD_STATUSES:
            errors.append(f"{name}: status {r.status!r} not in {lib.RECORD_STATUSES}")
        if not r.title:
            errors.append(f"{name}: missing title")
        if not r.decider:
            errors.append(f"{name}: missing decider")
        if r.priority and r.priority not in PRIORITIES:
            errors.append(f"{name}: priority {r.priority!r} not in {PRIORITIES}")
        if not r.asked:
            errors.append(f"{name}: missing asked (YYYY-MM-DD)")
        elif _date(r.asked) is None:
            errors.append(f"{name}: asked {r.asked!r} is not a valid YYYY-MM-DD date")
        answered = r.extra.get("answered")
        if answered not in (None, "", []) and _date(answered) is None:
            errors.append(f"{name}: answered {answered!r} is not a valid YYYY-MM-DD date")
        if r.status in ("answered", "decided") and not re.search(r"^## (Answer|Decision)\b", r.body, re.M):
            errors.append(f"{name}: status {r.status} but no '## Answer' or '## Decision' section")
        for c in r.chunks:
            if c not in chunk_ids:
                errors.append(f"{name}: chunk {c} does not resolve")
        check_accepted_risk(r, name, errors, warnings, today)
    rec_ids = set(rids)
    for r in records:
        for o in r.related:
            if o not in rec_ids:
                errors.append(f"{Path(r.path).name}: related {o} does not resolve")
    by_id = {r.id: r for r in records}
    for r in records:
        for o in r.related:
            if o in by_id and o != r.id and r.id not in by_id[o].related:
                warnings.append(f"{Path(r.path).name}: related {o} is one-way ({o} does not list {r.id})")
    return errors


def id_collisions(refs: list[str], qa_dir: Path = lib.QA_DIR, repo: Path | None = None) -> list[str]:
    """Warnings for record ids whose title differs on another git ref. Reads git objects only (no network)."""
    if not refs:
        return []
    repo = repo or lib.REPO_ROOT
    local = {r.id: r for r in lib.load_records(qa_dir)}
    out: list[str] = []
    rel = (qa_dir / "records").resolve().relative_to(repo.resolve()).as_posix()

    def git(*args: str) -> str:
        res = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise ValueError(res.stderr.strip() or f"git {' '.join(args)} failed")
        return res.stdout

    for ref in refs:
        if ref.startswith("-"):
            out.append(f"--against {ref}: a ref must not start with '-'")
            continue
        try:
            names = [n for n in git("ls-tree", "-r", "--name-only", ref, "--", rel).splitlines() if n.endswith(".md")]
        except ValueError as exc:
            out.append(f"--against {ref}: {exc}")
            continue
        for n in names:
            try:
                other, _ = lib.parse_frontmatter(git("show", f"{ref}:{n}"))
            except ValueError:
                continue
            rid, title = other.get("id"), other.get("title")
            if rid in local and title is not None and title != local[rid].title:
                out.append(f"{rid}: title differs on {ref} ({title!r} there, {local[rid].title!r} here); "
                           "either a colliding new id or a retitled record; renumber only if the record is new")
    return out


def toc_markdown(chunks: list[lib.Chunk]) -> str:
    by_topic: dict[str, list[lib.Chunk]] = {}
    for c in chunks:
        for t in c.topics:
            by_topic.setdefault(t, []).append(c)
    lines = ["# Business KB table of contents", "",
             "Generated by `python3 scripts/kb/check_chunks.py --write-toc`. Do not edit by hand.", "",
             f"{len(chunks)} chunks, {sum(c.word_count for c in chunks)} words.", ""]
    for topic in sorted(by_topic):
        lines += [f"## {topic}", ""]
        lines += [f"- `{c.chunk_id}` {c.title} ({c.word_count} words)" for c in sorted(by_topic[topic], key=lambda x: x.chunk_id)]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write-toc", action="store_true")
    ap.add_argument("--against", action="append", default=[], metavar="REF",
                    help="git ref to compare record ids with (repeatable; offline, uses fetched refs only)")
    a = ap.parse_args(argv)
    warnings: list[str] = []
    counts: dict[str, int] = {}
    errors = lint(warnings=warnings, counts=counts)
    warnings += id_collisions(a.against)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    if a.write_toc and not errors:
        (lib.KB_DIR / "TOC.md").write_text(toc_markdown(lib.load_chunks()), encoding="utf-8")
        print("wrote kb/TOC.md")
    n_c, n_r = counts["chunks"], counts["records"]
    print(f"checked {n_c} chunks, {n_r} records: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
