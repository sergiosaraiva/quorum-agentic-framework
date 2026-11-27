"""Regression test (OD-032): an allow-listed standalone gate script must not import from its own directory.

Why: `python3 scripts/<x>.py` puts scripts/ first on sys.path, so a planted scripts/json.py, scripts/json/__init__.py, a sourceless
scripts/json.pyc or an extension module (scripts/json.cpython-312-*.so) would replace a standard library module and run without a
prompt (the Edit ask rules only cover `scripts/*.py` and `scripts/*/__init__.py`, and a shell redirect can write the other forms).
Each script drops its own directory from sys.path as its first statement, before any import (`from __future__` imports a module
too, so the scripts do not use it). This test copies each script next to planted standard-library names and runs it.
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
ALLOW_PYTHON_SCRIPT = re.compile(r"^Bash\(python3 scripts/([A-Za-z0-9_]+\.py)[: )]")
MARKER = "PLANTED-MODULE-RAN"
# Names that cannot or need not be shadowed: builtin, and loaded at interpreter start-up before the script directory is added.
SKIP = {"sys", "builtins", "this", "antigravity", "site", "encodings", "codecs", "io", "abc", "os", "stat", "posixpath", "ntpath",
        "genericpath", "importlib", "zipimport", "marshal", "time", "itertools", "errno", "signal", "winreg", "msvcrt"}


def allow_listed_standalone_scripts() -> list[str]:
    allow = json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]["allow"]
    return sorted({m.group(1) for m in (ALLOW_PYTHON_SCRIPT.match(rule) for rule in allow) if m})


def plant(directory: Path) -> None:
    """Plant every standard-library module name in the directory, in the forms Python resolves from a script directory."""
    code = f"import sys\nsys.stderr.write('{MARKER}\\n')\nsys.stdout.write('{MARKER}\\n')\n"
    names = sorted(n for n in sys.stdlib_module_names if not n.startswith("_") and n not in SKIP)
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
        self.assertTrue({"ai_review_local.py", "framework_lint.py", "coverage_changed.py"} <= set(allow_listed_standalone_scripts()))

    def test_planted_standard_library_names_next_to_a_script_do_not_run(self):
        with tempfile.TemporaryDirectory() as raw:
            scripts = Path(raw).resolve() / "scripts"
            scripts.mkdir()
            plant(scripts)
            control = scripts / "control.py"  # no guard: proves the planted modules do shadow the standard library here
            control.write_text("import json\nprint('control imported json')\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(control)], capture_output=True, text=True, cwd=raw, env=clean_env(), timeout=60)
            self.assertIn(MARKER, result.stdout + result.stderr, "the plant does not shadow anything, so this test proves nothing")
            for name in allow_listed_standalone_scripts():
                with self.subTest(script=name):
                    copy = scripts / name
                    copy.write_text((ROOT / "scripts" / name).read_text(encoding="utf-8"), encoding="utf-8")
                    result = subprocess.run([sys.executable, str(copy), "--help"], capture_output=True, text=True, cwd=raw,
                                            env=clean_env(), timeout=60)
                    self.assertNotIn(MARKER, result.stdout + result.stderr)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("usage:", result.stdout)

    def test_every_gate_script_drops_its_directory_before_any_other_import(self):
        for name in allow_listed_standalone_scripts():
            with self.subTest(script=name):
                lines = (ROOT / "scripts" / name).read_text(encoding="utf-8").splitlines()
                statements = [ln for ln in lines if re.match(r"(import |from )", ln)]
                self.assertTrue(statements[0].startswith("import sys"), statements[:2])
                self.assertFalse(any(ln.startswith("from __future__") for ln in lines), "`from __future__` imports a module")
                self.assertTrue(any("del sys.path[0]" in ln for ln in lines))


if __name__ == "__main__":
    unittest.main()
