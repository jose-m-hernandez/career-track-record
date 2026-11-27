"""Tests for ci/hygiene.py and for the rule it holds: a new test builds its child environment
from nothing and asserts with a boolean and a fixed message. All sources here are invented."""

import ast
import os
import tempfile
import unittest

from ci import hygiene

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")

CLEAN = (
    "import unittest\n"
    "class T(unittest.TestCase):\n"
    "    def test_a(self):\n"
    "        self.assertTrue(1 == 1, 'a fixed message')\n"
    "        self.assertFalse(1 == 2, 'a fixed message')\n"
    "        code = 0\n"
    "        self.assertEqual(code, 0, 'a fixed message')\n"
    "        with self.assertRaises(ValueError):\n"
    "            int('x')\n"
    "        self.fail('a fixed message')\n"
)

MUTANTS = {
    "environ": "import os\nvalue = os.environ\n",
    "assertTrue with no message": "class T:\n    def t(self):\n        self.assertTrue(1)\n",
    "assertFalse with a computed message": (
        "class T:\n    def t(self):\n        self.assertFalse(1, 'a' + 'b')\n"),
    "assertEqual on something but code": (
        "class T:\n    def t(self):\n        self.assertEqual(1, 1, 'm')\n"),
    "assertEqual of code to True": (
        "class T:\n    def t(self):\n        self.assertEqual(code, True, 'm')\n"),
    "assertEqual of code to False": (
        "class T:\n    def t(self):\n        self.assertEqual(code, False, 'm')\n"),
    "assertRaises not a context manager": (
        "class T:\n    def t(self):\n        self.assertRaises(ValueError)\n"),
    "fail with a computed message": "class T:\n    def t(self):\n        self.fail(str(1))\n",
    "another assert form": "class T:\n    def t(self):\n        self.assertIn(1, [1])\n",
}


def parse(source):
    return ast.parse(source)


class Scope(unittest.TestCase):
    def test_legacy_names_exist(self):
        missing = [n for n in hygiene.LEGACY if not os.path.isfile(os.path.join(TESTS, n))]
        with self.subTest(missing=", ".join(missing)):
            self.assertTrue(not missing, "a name in LEGACY is not a file in tests/")

    def test_legacy_is_sorted_and_has_no_duplicates(self):
        self.assertTrue(list(hygiene.LEGACY) == sorted(set(hygiene.LEGACY)),
                        "LEGACY is not sorted, one name per line")

    def test_class_keys_exist_and_hold_their_classes(self):
        for name, classes in sorted(hygiene.CLASSES.items()):
            path = os.path.join(TESTS, name)
            with self.subTest(module=name):
                self.assertTrue(os.path.isfile(path), "a key of CLASSES is not a file in tests/")
                _, tree = hygiene.read_tree(path)
                held = [n.name for n in hygiene.class_nodes(tree, classes)]
                self.assertTrue(sorted(held) == sorted(classes),
                                "a class named in CLASSES is not in its module")

    def test_a_new_module_is_in_scope_and_a_legacy_one_is_not(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("test_brand_new.py", "test_ab.py", "test_example_reader.py"):
                with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
                    handle.write("x = 1\n")
            got = dict(hygiene.scope(folder))
        self.assertTrue("test_brand_new.py" in got and got["test_brand_new.py"] is None,
                        "a module not in LEGACY is not checked whole")
        self.assertTrue("test_ab.py" not in got, "a legacy module is checked")
        self.assertTrue(got.get("test_example_reader.py") == hygiene.CLASSES["test_example_reader.py"],
                        "a legacy module with CLASSES is not checked for those classes")


class Tree(unittest.TestCase):
    def test_no_finding_in_any_module_or_class_in_scope(self):
        found = hygiene.scan(TESTS)
        with self.subTest(findings="; ".join(found)):
            self.assertTrue(not found, "a test in scope breaks the hygiene rule")

    def test_scope_is_not_empty(self):
        names = [n for n, _ in hygiene.scope(TESTS)]
        self.assertTrue("test_test_hygiene.py" in names, "this module is not in scope")


class Rule(unittest.TestCase):
    def test_the_clean_source_has_no_finding(self):
        self.assertTrue(hygiene.findings(parse(CLEAN), True) == [],
                        "the clean source gives a finding")

    def test_each_mutant_gives_exactly_one_finding(self):
        for label, source in sorted(MUTANTS.items()):
            with self.subTest(mutant=label):
                self.assertTrue(len(hygiene.findings(parse(source), True)) == 1,
                                "a broken form does not give exactly one finding")


def count(source):
    """Findings for a module source, with the child-process question asked of the source."""
    tree = parse(source)
    return len(hygiene.findings(tree, hygiene.is_child_process(tree)))


def child(source):
    return hygiene.is_child_process(parse(source))


ASSERTS = (
    "class T:\n    def t(self):\n        self.assertEqual(a, b)\n        self.assertIn(a, b)\n")
HELPERS = (
    "import subprocess\nclass T:\n    def t(self):\n        self.assertRun(x)\n"
    "        self.assertRefused(x)\n        self.assertCannot(x)\n        self.assertCannotRun(x)\n")


class ChildProcess(unittest.TestCase):
    def test_a_module_that_imports_nothing_special_may_assert_as_it_likes(self):
        self.assertTrue(count(ASSERTS) == 0, "a plain module gives a finding")
        self.assertFalse(child(ASSERTS), "a plain module is a child-process module")

    def test_subprocess_makes_a_child_process_module(self):
        source = "import subprocess\n" + ASSERTS
        self.assertTrue(count(source) == 2, "not one finding per assertion")
        self.assertTrue(child(source), "subprocess is not a child-process module")

    def test_importing_from_another_test_module_makes_one(self):
        source = "from tests.test_ab import Setup\n" + ASSERTS
        self.assertTrue(count(source) == 2, "not one finding per assertion")
        self.assertTrue(child(source), "an import from a test module is not a child-process module")

    def test_a_relative_import_from_a_test_module_makes_one(self):
        source = "from .test_ab import Setup\n"
        self.assertTrue(child(source) is True,
                        "a relative import from a test module is not a child-process module")
        self.assertTrue(count(source + ASSERTS) == 2, "not one finding per assertion")

    def test_a_relative_import_of_a_test_module_makes_one(self):
        self.assertTrue(child("from . import test_ab\n") is True,
                        "a relative import of a test module is not a child-process module")

    # Known limit: only os.system and os.popen are read as starting a child process; os.exec*,
    # os.spawn*, os.posix_spawn, multiprocessing and pty are not detected.
    def test_os_system_makes_one(self):
        source = "import os\nos.system('true')\n" + ASSERTS
        self.assertTrue(child(source) is True, "os.system is not a child-process module")
        self.assertTrue(count(source) == 2, "not one finding per assertion")

    def test_os_popen_through_an_alias_makes_one(self):
        self.assertTrue(child("import os as o\no.popen('true')\n" + ASSERTS) is True,
                        "popen through an alias of os is not a child-process module")

    def test_system_imported_from_os_makes_one(self):
        self.assertTrue(child("from os import system\n" + ASSERTS) is True,
                        "system imported from os is not a child-process module")

    def test_another_use_of_os_makes_none(self):
        source = "import os\nx = os.path.join('a', 'b')\n" + ASSERTS
        self.assertTrue(child(source) is False, "os.path makes a child-process module")
        self.assertTrue(count(source) == 0, "a plain use of os gives a finding")

    def test_the_forced_failures_import_makes_one(self):
        self.assertTrue(child("from ci import forced_failures\n"),
                        "forced_failures is not a child-process module")

    def test_the_project_helpers_are_allowed(self):
        self.assertTrue(count(HELPERS) == 0, "a listed helper gives a finding")

    def test_another_helper_is_a_finding(self):
        source = "import subprocess\nclass T:\n    def t(self):\n        self.assertSomethingElse(x)\n"
        self.assertTrue(count(source) == 1, "an unlisted helper does not give one finding")

    def test_environ_binds_everywhere(self):
        self.assertTrue(count("import os\nx = os.environ\n") == 1, "environ gives no finding")

    def test_environ_imported_by_name_is_a_finding(self):
        self.assertTrue(count("from os import environ\n") == 1,
                        "an environ imported by name gives no finding")

    def test_environ_imported_under_another_name_is_one_finding_at_the_import(self):
        self.assertTrue(count("from os import environ as env\nvalue = env.copy()\n") == 1,
                        "an environ imported as another name is not one finding")

    def test_another_name_from_os_is_no_finding(self):
        self.assertTrue(count("from os import path\n") == 0,
                        "another name from os gives a finding")

    def test_environ_through_a_module_alias_is_a_finding(self):
        self.assertTrue(count("import os as o\nvalue = o.environ\n") == 1,
                        "environ through a module alias gives no finding")


class Helpers(unittest.TestCase):
    def test_a_listed_function_import_is_a_finding_without_a_call(self):
        self.assertTrue(count("from tests.test_cli import track\n") == 1, "no finding")

    def test_a_renamed_import_is_a_finding(self):
        self.assertTrue(count("from tests.test_cli import track as run\n") == 1, "no finding")

    def test_a_module_alias_use_is_a_finding(self):
        source = "from tests import test_cli\ntest_cli.track('x')\n"
        self.assertTrue(count(source) == 1, "no finding")

    def test_a_dotted_import_use_is_a_finding(self):
        source = "import tests.test_cli as c\nc.track('x')\n"
        self.assertTrue(count(source) == 1, "no finding")

    def test_a_listed_class_import_is_a_finding(self):
        source = "from tests.test_claims import ClaimsCase\nclass X(ClaimsCase):\n    pass\n"
        self.assertTrue(count(source) == 1, "no finding")

    def test_an_unlisted_import_gives_no_r2_finding(self):
        self.assertTrue(count("from tests.test_ab import Setup\n") == 0, "a finding")

    def test_a_relative_renamed_import_is_a_finding(self):
        self.assertTrue(count("from .test_cli import track as run\n") == 1, "no finding")

    def test_a_relative_module_alias_use_is_a_finding(self):
        source = "from . import test_cli\ntest_cli.track('x')\n"
        self.assertTrue(count(source) == 1, "no finding")

    def test_an_unlisted_relative_import_gives_no_r2_finding(self):
        self.assertTrue(count("from .test_ab import Setup\n") == 0, "a finding")

    def test_the_import_is_reported_once_for_a_class(self):
        source = "from tests.test_cli import track\nclass A:\n    pass\nclass B:\n    pass\n"
        tree = parse(source)
        got = list(hygiene.import_findings(tree))
        for node in hygiene.class_nodes(tree, ("A", "B")):
            got.extend(hygiene.findings(node, False, tree))
        self.assertTrue(len(got) == 1, "the import is not reported exactly once")


def module_tree(name):
    return hygiene.read_tree(os.path.join(TESTS, name))[1]


def holds_environ(node):
    return any(isinstance(n, ast.Attribute) and n.attr == "environ" for n in ast.walk(node))


class Data(unittest.TestCase):
    def test_every_listed_helper_is_a_top_level_function_that_uses_environ(self):
        for name, func in hygiene.ENV_HELPERS:
            with self.subTest(module=name, function=func):
                found = [n for n in module_tree(name).body
                         if isinstance(n, ast.FunctionDef) and n.name == func]
                self.assertTrue(len(found) == 1, "not a top-level function of that file")
                self.assertTrue(holds_environ(found[0]), "the function does not use environ")

    def test_every_listed_class_is_a_top_level_class_that_uses_environ(self):
        for name, cls in hygiene.ENV_CLASSES:
            with self.subTest(module=name, cls=cls):
                found = [n for n in module_tree(name).body
                         if isinstance(n, ast.ClassDef) and n.name == cls]
                self.assertTrue(len(found) == 1, "not a top-level class of that file")
                methods = [n for n in found[0].body if isinstance(n, ast.FunctionDef)]
                self.assertTrue(any(holds_environ(m) for m in methods),
                                "no method of the class uses environ")

    def test_each_tuple_is_sorted_with_no_duplicate(self):
        for label in ("ASSERT_HELPERS", "CHILD_MODULES", "OS_CHILD", "ENV_HELPERS", "ENV_CLASSES"):
            data = list(getattr(hygiene, label))
            with self.subTest(tuple=label):
                self.assertTrue(data == sorted(set(data)), "not sorted, or has a duplicate")


if __name__ == "__main__":
    unittest.main()
