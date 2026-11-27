#!/usr/bin/env python3
"""Remove the example domain from the knowledge bases.

    python3 scripts/kb/remove_examples.py            # dry run: list the files that would be deleted
    python3 scripts/kb/remove_examples.py --apply    # delete them, regenerate kb/TOC.md, list leftover citations
    python3 scripts/kb/remove_examples.py --root DIR # work on another tree (default: this repository)

An example file is a chunk under `kb/chunks/` or a record under `questions/records/` whose frontmatter has
`example: true`. `--apply` is plain file deletion; commit the result yourself. After deleting it regenerates
`kb/TOC.md` (when the file exists) and prints, grouped by file, every remaining citation of a removed id in the
files the dangling-reference check of check_chunks.py scans (ids listed in scripts/kb/ref-ignore.txt are skipped).
A delete that fails (a read-only file, a permission error) is reported on stderr and does not stop the run: the TOC is still
regenerated and the remaining citations are still listed. Exit code 0 on success, 2 on a usage or I/O error or when any
delete failed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import check_chunks
import lib

CLOSING = ("Rewrite or delete the passages above, then run `python3 scripts/kb/check_chunks.py`. The Orders sample "
           "code under src/, tests/ and frontend/ and the example slices in docs/slices/ are removed separately.")


def find_examples(root: Path) -> list[tuple[Path, str]]:
    """(file, id) for every `example: true` chunk and record under `root`, sorted by path. The id is the frontmatter
    id, else the filename stem. A file whose frontmatter cannot be parsed is reported on stderr and left alone."""
    found: list[tuple[Path, str]] = []
    for sub, key in (("kb/chunks", "chunk_id"), ("questions/records", "id")):
        for path in sorted((root / sub).glob("*.md")):
            try:
                meta, _ = lib.parse_frontmatter(path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                print(f"warning: skipping {path.name}: {exc}", file=sys.stderr)
                continue
            if meta.get("example") is True:
                found.append((path, str(meta.get(key) or path.stem)))
    return found


def remaining_citations(root: Path, removed: set[str]) -> dict[str, list[str]]:
    """file -> removed ids it still cites, over the files the dangling-reference check scans."""
    kb_dir, qa_dir = root / "kb", root / "questions"
    defined = {c.chunk_id for c in lib.load_chunks(kb_dir)} | {r.id for r in lib.load_records(qa_dir)}
    ignore = check_chunks.load_ref_ignore(root / check_chunks.REF_IGNORE_FILE)
    out: dict[str, list[str]] = {}
    for rel, rid in check_chunks.dangling_refs(root, defined, ignore=ignore, cited=removed):
        if rid in removed:
            out.setdefault(rel, []).append(rid)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="delete the files (default: dry run)")
    ap.add_argument("--root", type=Path, default=lib.REPO_ROOT, help="tree to work on (default: this repository)")
    a = ap.parse_args(argv)
    root = a.root
    if not (root / "kb" / "chunks").is_dir() or not (root / "questions" / "records").is_dir():
        print(f"error: {root} has no kb/chunks and questions/records", file=sys.stderr)
        return 2

    examples = find_examples(root)
    if not a.apply:
        for path, _ in examples:
            print(f"would delete  {path.relative_to(root).as_posix()}")
        print(f"{len(examples)} example file(s) with `example: true`")
        print("dry run: nothing deleted; re-run with --apply to delete them")
        return 0

    failed: list[Path] = []
    deleted: set[str] = set()
    for path, rid in examples:  # a `delete` line is printed only once the file is really gone
        try:
            path.unlink()
        except OSError as exc:
            print(f"error: cannot delete {path.relative_to(root).as_posix()}: {exc}", file=sys.stderr)
            failed.append(path)
        else:
            deleted.add(rid)
            print(f"delete  {path.relative_to(root).as_posix()}")
    print(f"{len(examples)} example file(s) with `example: true`")

    try:
        toc = root / "kb" / "TOC.md"
        if toc.is_file():
            check_chunks.write_toc(root / "kb")
            print("regenerated kb/TOC.md")
        citations = remaining_citations(root, deleted)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if citations:
        total = sum(len(ids) for ids in citations.values())
        print(f"\n{total} remaining citation(s) of a removed id in {len(citations)} file(s):")
        for rel in sorted(citations):
            print(f"  {rel}: {', '.join(sorted(citations[rel]))}")
    else:
        print("\nno remaining citation of a removed id")
    print(CLOSING)
    if failed:
        print(f"error: {len(failed)} file(s) could not be deleted; fix the cause and run again", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
