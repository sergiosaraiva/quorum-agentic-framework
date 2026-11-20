#!/usr/bin/env python3
"""Line coverage of the changed C# files, for the test-automator `coverage` object.

    dotnet test --solution Quorum.slnx --coverage --coverage-output-format cobertura --results-directory TestResults
    python3 scripts/coverage_changed.py --base origin/main TestResults/*.cobertura.xml

Prints one JSON object: {"changed_files_pct": <float>, "files": {"<path>": <pct>}, "not_measured": ["<path>"]}.
Several Cobertura files (unit and integration projects) are merged: a line counts as covered if any file covers it.
Changed `.cs` files under `src/` that no report mentions are listed in `not_measured`, not counted as 0 or 100.
A figure is context, never the goal (`test-automator`, "Coverage").
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def merged_lines(reports: list[Path], root: Path = REPO_ROOT) -> dict[str, dict[int, bool]]:
    """Map repo-relative file path -> {line number: covered}, merged across reports."""
    out: dict[str, dict[int, bool]] = {}
    for rep in reports:
        for cls in ET.parse(rep).getroot().iter("class"):
            fn = cls.get("filename", "")
            p = Path(fn)
            try:
                rel = (p.resolve().relative_to(root.resolve()) if p.is_absolute() else p).as_posix()
            except ValueError:
                continue
            lines = out.setdefault(rel, {})
            for ln in cls.iter("line"):
                n, hit = int(ln.get("number", "0")), int(ln.get("hits", "0")) > 0
                lines[n] = lines.get(n, False) or hit
    return out


def summarize(changed: list[str], lines: dict[str, dict[int, bool]]) -> dict:
    files, covered, valid, missing = {}, 0, 0, []
    for f in sorted(changed):
        data = lines.get(f)
        if not data:
            missing.append(f)
            continue
        c = sum(data.values())
        covered, valid = covered + c, valid + len(data)
        files[f] = round(100 * c / len(data), 1)
    return {"changed_files_pct": round(100 * covered / valid, 1) if valid else 0.0,
            "files": files, "not_measured": missing}


def changed_cs_files(base: str, root: Path = REPO_ROOT) -> list[str]:
    res = subprocess.run(["git", "-C", str(root), "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD"],
                         capture_output=True, text=True, check=True)
    return [n for n in res.stdout.splitlines() if n.startswith("src/") and n.endswith(".cs")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="origin/main", help="git ref the change is measured against")
    ap.add_argument("reports", nargs="+", type=Path, help="Cobertura XML files")
    a = ap.parse_args(argv)
    print(json.dumps(summarize(changed_cs_files(a.base), merged_lines(a.reports))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
