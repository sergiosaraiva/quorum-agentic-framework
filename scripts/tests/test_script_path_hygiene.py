"""Regression test (OD-032): an allow-listed standalone gate script must not import from its own directory.

Why: `python3 scripts/<x>.py` puts scripts/ first on sys.path, so a planted scripts/json.py, scripts/json/__init__.py, a sourceless
scripts/json.pyc or an extension module (scripts/json.cpython-312-*.so) would replace a standard library module and run without a
prompt (the Edit ask rules only cover `scripts/*.py` and `scripts/*/__init__.py`, and a shell redirect can write the other forms).
Each script drops its own directory from sys.path as its first statement, before any import (`from __future__` imports a module
too, so the scripts do not use it). The scripts/kb scripts import their siblings (`lib`, `backends`), so after dropping the directory
they load those by path and register them under their names. Moving the directory to the END of sys.path is not enough: modules the
standard library imports optionally and this platform lacks (`nt` from pathlib, `psycopg` from the pg backend) would still be found
there. Covered: every `python3 scripts/<path>.py` allow rule in .claude/settings.json and every script in .mcp.json (the KB MCP
server). This test copies each script and its sibling modules next to planted standard-library names and runs it.
Run: python3 -m unittest discover -s scripts/tests"""
import importlib.machinery
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / ".claude" / "settings.json"
MCP_CONFIG = ROOT / ".mcp.json"
ALLOW_PYTHON_SCRIPT = re.compile(r"^Bash\(python3 scripts/((?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+\.py)[: )]")
GUARD_LINES = ("del sys.path[0]", "= sys.path.pop(0)")
MARKER = "PLANTED-MODULE-RAN"
# Names that cannot or need not be shadowed: builtin, and loaded at interpreter start-up before the script directory is added.
SKIP = {"sys", "builtins", "this", "antigravity", "site", "encodings", "codecs", "io", "abc", "os", "stat", "posixpath", "ntpath",
        "genericpath", "importlib", "zipimport", "marshal", "time", "itertools", "errno", "signal", "winreg", "msvcrt"}


def allow_listed_standalone_scripts() -> list[str]:
    """Paths relative to scripts/ of every script that runs without a prompt: allow-listed, or started by .mcp.json."""
    allow = json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]["allow"]
    found = {m.group(1) for m in (ALLOW_PYTHON_SCRIPT.match(rule) for rule in allow) if m}
    for server in json.loads(MCP_CONFIG.read_text(encoding="utf-8"))["mcpServers"].values():
        if server.get("command") == "python3" and server.get("args", [""])[0].startswith("scripts/"):
            found.add(server["args"][0][len("scripts/"):])
    return sorted(found)


def plant(directory: Path) -> None:
    """Plant every standard-library module name in the directory, in the forms Python resolves from a script directory."""
    code = f"import sys\nsys.stderr.write('{MARKER}\\n')\nsys.stdout.write('{MARKER}\\n')\n"
    names = sorted(n for n in sys.stdlib_module_names if (not n.startswith("_") or n == "__future__") and n not in SKIP)
    for name in names:
        (directory / f"{name}.py").write_text(code, encoding="utf-8")
    # a regular package, a sourceless .pyc and a (garbage) extension module: the last one raises ImportError if it is loaded
    for name in ("xml", "yaml", "argparse"):
        (directory / name).mkdir(exist_ok=True)
        (directory / name / "__init__.py").write_text(code, encoding="utf-8")
    source = directory / "_planted_source.py"
    source.write_text(code, encoding="utf-8")
    for name in ("pathlib", "subprocess"):
        (directory / f"{name}.py").unlink()
        py_compile.compile(str(source), cfile=str(directory / f"{name}.pyc"), doraise=True)
    source.unlink()
    for name in ("datetime", "shutil"):
        (directory / f"{name}.py").unlink()
        (directory / f"{name}{importlib.machinery.EXTENSION_SUFFIXES[0]}").write_bytes(b"not a shared object")


def clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}


class ScriptPathHygieneTests(unittest.TestCase):
    def test_the_settings_allow_list_names_the_gate_scripts_this_test_covers(self):
        covered = set(allow_listed_standalone_scripts())
        self.assertTrue({"ai_review_local.py", "framework_lint.py", "coverage_changed.py"} <= covered)
        self.assertTrue({"kb/check_chunks.py", "kb/search.py", "kb/mcp_server.py"} <= covered)

    def test_no_sibling_module_of_a_covered_script_has_a_standard_library_name(self):
        # a sibling named like a standard library module would be loaded by path, and shadow the real one for the whole process
        for directory in {(ROOT / "scripts" / name).parent for name in allow_listed_standalone_scripts()}:
            for module in directory.glob("*.py"):
                with self.subTest(module=str(module.relative_to(ROOT))):
                    self.assertNotIn(module.stem, sys.stdlib_module_names)

    def test_planted_standard_library_names_next_to_a_script_do_not_run(self):
        for name in allow_listed_standalone_scripts():
            with self.subTest(script=name), tempfile.TemporaryDirectory() as raw:
                real = (ROOT / "scripts" / name).parent
                directory = Path(raw).resolve() / "scripts" / real.relative_to(ROOT / "scripts")
                directory.mkdir(parents=True)
                for sibling in real.glob("*.py"):  # the script and the modules it imports (scripts/kb: lib, backends)
                    (directory / sibling.name).write_text(sibling.read_text(encoding="utf-8"), encoding="utf-8")
                plant(directory)
                control = directory / "control.py"  # no guard: proves the planted modules do shadow the standard library here
                control.write_text("import json\nprint('control imported json')\n", encoding="utf-8")
                result = subprocess.run([sys.executable, str(control)], capture_output=True, text=True, cwd=raw, env=clean_env(), timeout=60)
                self.assertIn(MARKER, result.stdout + result.stderr, "the plant does not shadow anything, so this test proves nothing")
                result = subprocess.run([sys.executable, str(directory / Path(name).name), "--help"], capture_output=True, text=True,
                                        cwd=raw, env=clean_env(), timeout=60)
                self.assertNotIn(MARKER, result.stdout + result.stderr)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_every_gate_script_guards_its_directory_before_any_other_import(self):
        for name in allow_listed_standalone_scripts():
            with self.subTest(script=name):
                lines = (ROOT / "scripts" / name).read_text(encoding="utf-8").splitlines()
                statements = [ln for ln in lines if re.match(r"(import |from )", ln)]
                self.assertTrue(statements[0].startswith("import sys"), statements[:2])
                self.assertFalse(any(ln.startswith("from __future__") for ln in lines), "`from __future__` imports a module")
                self.assertTrue(any(guard in ln for ln in lines for guard in GUARD_LINES))
                guard = next(i for i, ln in enumerate(lines) if any(g in ln for g in GUARD_LINES))
                self.assertEqual([ln for ln in lines[:guard] if re.match(r"(import |from )", ln)], [statements[0]])


if __name__ == "__main__":
    unittest.main()
