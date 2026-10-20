"""Structural test: no tool module imports a network or mail capability.

Names as written; aliases and getattr are not tracked."""

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
ALLOW_LIST = {}  # empty: no fetch tool exists yet


def python_files():
    found = []
    for folder, _dirs, names in os.walk(SRC):
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


class NoNetworkCase(unittest.TestCase):
    def test_scans_at_least_four_files(self):
        self.assertGreaterEqual(len(python_files()), 4)

    def test_no_barred_import_or_dynamic_loading(self):
        report = {}
        for path in python_files():
            found = problems(path)
            if found and os.path.relpath(path, SRC) not in ALLOW_LIST:
                report[os.path.relpath(path, SRC)] = found
        self.assertEqual(report, {})

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


if __name__ == "__main__":
    unittest.main()
