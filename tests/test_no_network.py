"""Structural test: no tool module imports a network or mail capability.

Names as written; aliases, getattr and built strings are not tracked."""

import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "career_track_record")

BARRED_IMPORTS = frozenset([
    "socket", "ssl", "http", "urllib", "ftplib", "smtplib", "poplib", "imaplib",
    "telnetlib", "xmlrpc", "asyncio", "subprocess", "multiprocessing", "webbrowser",
    "requests", "importlib", "builtins", "ctypes",
])
BARRED_NAMES = frozenset(["__import__", "eval", "exec", "compile", "importlib",
                          "__builtins__"])
BARRED_ATTRIBUTES = frozenset(["__import__", "import_module"])
BARRED_CALLED_ATTRIBUTES = frozenset(["system", "popen"])
# One module may run a program: pdf_text.py starts pdftotext to read a PDF. It is excused
# only for the exact problem strings listed here; any other problem in it still fails, and
# the tests below check that it makes exactly one such call.
ALLOWED_SUBPROCESS_ATTRIBUTES = frozenset(["run", "DEVNULL", "TimeoutExpired"])
ALLOWED_RUN_KEYWORDS = frozenset(["stdin", "capture_output", "timeout", "check"])
ALLOW_LIST = {"pdf_text.py": frozenset(["imports subprocess"])}


def python_files(directory=SRC):
    found = []
    for folder, _dirs, names in os.walk(directory):
        for name in names:
            if name.endswith(".py"):
                found.append(os.path.join(folder, name))
    return sorted(found)


def problems(path):
    with open(path, encoding="utf-8") as handle:
        return problems_in_source(handle.read(), filename=path)


def problems_in_source(source, filename="<string>"):
    tree = ast.parse(source, filename=filename)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BARRED_IMPORTS:
                    found.append("imports %s" % alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.split(".")[0] in BARRED_IMPORTS:
                found.append("imports from %s" % node.module)
            for alias in node.names:
                if alias.name in BARRED_CALLED_ATTRIBUTES:
                    found.append("imports the name %s" % alias.name)
                elif alias.name == "*":
                    found.append("uses a star import")
        elif isinstance(node, ast.Name) and node.id in BARRED_NAMES:
            found.append("uses the name %s" % node.id)
        elif isinstance(node, ast.Attribute) and node.attr in BARRED_ATTRIBUTES:
            found.append("uses the attribute %s" % node.attr)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr in BARRED_CALLED_ATTRIBUTES):
            found.append("calls the attribute %s" % node.func.attr)
    return found


def unexcused(relative, found):
    allowed = ALLOW_LIST.get(relative, frozenset())
    return [item for item in found if item not in allowed]


def scan(src_dir):
    """Relative path -> unexcused problems, for every .py file under src_dir; clean files left out."""
    report = {}
    for path in python_files(src_dir):
        relative = os.path.relpath(path, src_dir)
        found = unexcused(relative, problems(path))
        if found:
            report[relative] = found
    return report


def subprocess_calls(source):
    """Every call whose function is an attribute of the name subprocess, whatever it is."""
    calls = []
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"):
            calls.append(node)
    return calls


def pdftotext_call_problems(source):
    """Empty when there is exactly one subprocess call, run, with ["pdftotext", ...]."""
    calls = subprocess_calls(source)
    if len(calls) != 1:
        return ["%d subprocess calls" % len(calls)]
    if calls[0].func.attr != "run":
        return ["the call is subprocess.%s, not run" % calls[0].func.attr]
    args = calls[0].args
    if not (args and isinstance(args[0], ast.List) and args[0].elts
            and isinstance(args[0].elts[0], ast.Constant)
            and args[0].elts[0].value == "pdftotext"):
        return ["the call does not start with a list literal naming pdftotext"]
    return []


def subprocess_use_problems(source):
    """Empty only when subprocess is used in the one known shape (pdf_text.py's)."""
    tree = ast.parse(source)
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    found = []
    plain_imports = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] != "subprocess":
                    continue
                if alias.name == "subprocess" and alias.asname is None:
                    plain_imports += 1
                else:
                    found.append("imports subprocess other than as plain 'import subprocess'")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "subprocess":
                found.append("imports from subprocess")
        elif isinstance(node, ast.Name):
            if node.id == "getattr":
                found.append("uses getattr")
            elif node.id == "subprocess":
                parent = parents.get(node)
                if not (isinstance(parent, ast.Attribute) and parent.value is node
                        and isinstance(parent.ctx, ast.Load)
                        and parent.attr in ALLOWED_SUBPROCESS_ATTRIBUTES):
                    found.append("uses the name subprocess other than as run, DEVNULL "
                                 "or TimeoutExpired")
                elif parent.attr == "run":
                    grand = parents.get(parent)
                    if not (isinstance(grand, ast.Call) and grand.func is parent):
                        found.append("subprocess.run is used other than as the function "
                                     "of a call")
        elif isinstance(node, ast.Attribute) and node.attr == "getattr":
            found.append("uses the attribute getattr")
    if plain_imports != 1:
        found.append("%d plain imports of subprocess" % plain_imports)
    runs = [n for n in subprocess_calls(source) if n.func.attr == "run"]
    if len(runs) != 1:
        found.append("%d calls of subprocess.run" % len(runs))
    for call in runs:
        if any(k.arg is None or k.arg == "shell" for k in call.keywords):
            found.append("subprocess.run is given shell or **keywords")
        if any(k.arg not in ALLOWED_RUN_KEYWORDS for k in call.keywords):
            found.append("subprocess.run is given a keyword outside "
                         "stdin, capture_output, timeout and check")
    return found


def pdf_text_source():
    with open(os.path.join(SRC, "pdf_text.py"), encoding="utf-8") as handle:
        return handle.read()


class NoNetworkCase(unittest.TestCase):
    def test_scans_at_least_four_files(self):
        self.assertGreaterEqual(len(python_files(directory=SRC)), 4)

    def test_no_barred_import_or_dynamic_loading(self):
        self.assertEqual(scan(SRC), {})

    def test_scan_applies_the_excuse_per_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for name, source in (("pdf_text.py", "import subprocess\nimport socket\n"),
                                 ("other.py", "import subprocess\n")):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as handle:
                    handle.write(source)
            self.assertEqual(scan(tmp), {"pdf_text.py": ["imports socket"],
                                         "other.py": ["imports subprocess"]})

    def test_the_check_itself_catches_things(self):
        import tempfile
        samples = {
            "import socket\n": 1,
            "from urllib.request import urlopen\n": 1,
            "import http.client\n": 1,
            "x = __import__('os')\n": 1,
            "eval('1')\n": 1,
            "import importlib\nimportlib.import_module('x')\n": 2,
            "import json\n": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            for index, (source, count) in enumerate(samples.items()):
                path = os.path.join(tmp, "s%d.py" % index)
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(source)
                self.assertGreaterEqual(len(problems(path)), count, source)
                if count == 0:
                    self.assertEqual(problems(path), [])

    def assertCaught(self, source, needle):
        found = problems_in_source(source)
        self.assertTrue(any(needle in item for item in found), found)

    def test_catches_from_importlib(self):
        self.assertCaught("from importlib import import_module\n", "importlib")

    def test_catches_import_builtins(self):
        self.assertCaught("import builtins\n", "builtins")

    def test_catches_builtins_dunder_import(self):
        self.assertCaught("x = builtins.__import__\n", "__import__")

    def test_catches_ctypes(self):
        self.assertCaught("import ctypes\n", "ctypes")
        self.assertCaught("from ctypes import CDLL\n", "ctypes")

    def test_catches_os_system(self):
        self.assertCaught("os.system('x')\n", "system")

    def test_catches_os_popen(self):
        self.assertCaught("os.popen('x')\n", "popen")

    def test_catches_from_os_import_system(self):
        self.assertCaught("from os import system\n", "system")
        self.assertCaught("from os import system as run\n", "system")

    def test_catches_from_os_import_popen(self):
        self.assertCaught("from os import popen\n", "popen")
        self.assertCaught("from os import popen as run\n", "popen")

    def test_catches_star_import(self):
        self.assertCaught("from os import *\n", "star import")
        self.assertCaught("from json import *\n", "star import")

    def test_the_excuse_covers_only_its_exact_problem(self):
        found = problems_in_source("import subprocess\nimport socket\n")
        self.assertEqual(unexcused("pdf_text.py", found), ["imports socket"])
        self.assertEqual(unexcused("other.py", found), ["imports subprocess", "imports socket"])

    def test_pdf_text_makes_exactly_one_pdftotext_call(self):
        self.assertEqual(pdftotext_call_problems(pdf_text_source()), [])

    def test_a_second_subprocess_call_is_caught(self):
        extra = pdf_text_source() + '\nsubprocess.run(["pdftotext", "x", "-"])\n'
        self.assertNotEqual(pdftotext_call_problems(extra), [])

    def test_other_subprocess_calls_are_caught(self):
        for call in ('subprocess.Popen(["true"])', 'subprocess.call(["true"])',
                     'subprocess.check_output(["true"])'):
            with self.subTest(call):
                planted = pdf_text_source() + "\n" + call + "\n"
                self.assertNotEqual(pdftotext_call_problems(planted), [])

    def test_os_system_planted_in_pdf_text_is_still_reported(self):
        planted = pdf_text_source() + '\nimport os\nos.system("true")\n'
        found = unexcused("pdf_text.py", problems_in_source(planted))
        self.assertTrue(any("calls the attribute system" in item for item in found), found)


    def test_pdf_text_uses_subprocess_in_the_one_known_shape(self):
        self.assertEqual(subprocess_use_problems(pdf_text_source()), [])

    def test_planted_alias_and_popen_is_caught(self):
        planted = pdf_text_source() + '\nimport subprocess as sp\nsp.Popen(["sh"])\n'
        self.assertNotEqual(subprocess_use_problems(planted), [])

    def test_planted_getattr_is_caught(self):
        planted = pdf_text_source() + '\ngetattr(subprocess, "Popen")(["sh"])\n'
        self.assertNotEqual(subprocess_use_problems(planted), [])

    def test_planted_rebinding_is_caught(self):
        planted = pdf_text_source() + '\nr = subprocess\nr.Popen(["sh"])\n'
        self.assertNotEqual(subprocess_use_problems(planted), [])

    def test_planted_shell_keyword_is_caught(self):
        source = pdf_text_source()
        self.assertIn("capture_output=True", source)
        planted = source.replace("capture_output=True", "capture_output=True, shell=True", 1)
        self.assertNotEqual(subprocess_use_problems(planted), [])

    def test_planted_stored_run_is_caught(self):
        planted = pdf_text_source() + '\nr = subprocess.run\nr(["sh"])\n'
        self.assertNotEqual(subprocess_use_problems(planted), [])

    def test_planted_mapped_run_is_caught(self):
        planted = pdf_text_source() + '\nlist(map(subprocess.run, [["sh"]]))\n'
        self.assertNotEqual(subprocess_use_problems(planted), [])

    def test_planted_executable_keyword_is_caught(self):
        source = pdf_text_source()
        self.assertIn("check=False)", source)
        planted = source.replace("check=False)", 'check=False, executable="/bin/sh")', 1)
        self.assertNotEqual(subprocess_use_problems(planted), [])

    def test_planted_env_keyword_is_caught(self):
        source = pdf_text_source()
        self.assertIn("check=False)", source)
        planted = source.replace("check=False)", "check=False, env={})", 1)
        self.assertNotEqual(subprocess_use_problems(planted), [])


if __name__ == "__main__":
    unittest.main()
