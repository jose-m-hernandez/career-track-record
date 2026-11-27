"""Tests for the parts of ci/forced_failures.py, on an invented mini-tree written to a temporary
folder. They do not run the script over the repository: that takes minutes. The Main tests call
main() on small invented git repositories, so they need git."""

import ast
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from ci import forced_failures

MARKER = "leak-marker-zz81"

MINI = (
    "import sys\n"
    "import unittest\n"
    "\n"
    "\n"
    "class Mini(unittest.TestCase):\n"
    "    def test_clean(self):\n"
    "        self.assertTrue(1 == 1, 'a fixed message')\n"
    "\n"
    "    def test_leaks(self):\n"
    "        self.assertTrue(1 == 1, '" + MARKER + "')\n"
    "\n"
    "    def test_cannot_fail_when_flipped(self):\n"
    "        if sys.maxsize < 0:\n"
    "            self.assertTrue(1 == 2, 'a fixed message')\n"
    "\n"
    "\n"
    "class Base(unittest.TestCase):\n"
    "    def helper(self):\n"
    "        self.assertEqual(1, 1, 'a fixed message')\n"
    "\n"
    "\n"
    "class Child(Base):\n"
    "    def test_uses_helper(self):\n"
    "        self.helper()\n"
)


NOT_FORCED_SOURCE = (
    "import unittest\n"
    "\n"
    "\n"
    "class N(unittest.TestCase):\n"
    "    def test_a(self):\n"
    "        with self.assertRaises(ValueError):\n"
    "            int('x')\n"
    "        self.fail('a fixed message')\n"
    "        self.assertTrue(1 == 1, 'a fixed message')\n"
)


def write_mini(folder):
    os.makedirs(os.path.join(folder, "tests"))
    with open(os.path.join(folder, "tests", "__init__.py"), "wb") as handle:
        handle.write(b"")
    path = os.path.join(folder, "tests", "test_mini.py")
    with open(path, "wb") as handle:
        handle.write(MINI.encode("utf-8"))
    return path


def read_all(path):
    with open(path, "rb") as handle:
        return handle.read()


class Parts(unittest.TestCase):
    # Known limit: a self.fail(...) or self.assertRaises(...) site is not forced; only
    # assertTrue, assertFalse and assertEqual calls are. The others are counted on the
    # `not flipped` line.
    # Known limit: a marker that also occurs in the test's own source gives a false BAD,
    # because a traceback prints the source line; the leaking row below is BAD for that reason
    # as well as for the marker in its message.
    # Known limit: a clean row does not prove a test is meaningful, only that its failure
    # prints nothing captured.
    def test_sites_find_every_assertion_in_source_order(self):
        found = forced_failures.sites(ast.parse(MINI), None)
        self.assertTrue([s.attr for s in found] == [
            "assertTrue", "assertTrue", "assertTrue", "assertEqual"],
            "the calls found are not the four in the mini module")
        self.assertTrue([s.lineno for s in found] == sorted(s.lineno for s in found),
                        "the calls are not in source order")

    def test_not_flipped_counts_assert_raises_and_fail(self):
        self.assertTrue(forced_failures.not_flipped(ast.parse(NOT_FORCED_SOURCE), None) == 2,
                        "the assertRaises and fail calls are not counted as two")
        self.assertTrue(forced_failures.not_flipped(ast.parse(MINI), None) == 0,
                        "the mini module has no call left unflipped, but one is counted")

    def test_sites_can_be_limited_to_a_class(self):
        found = forced_failures.sites(ast.parse(MINI), ("Base",))
        self.assertTrue([s.fn for s in found] == ["helper"], "the class filter did not apply")

    def test_flip_changes_exactly_one_call(self):
        tree = ast.parse(MINI)
        for site in forced_failures.sites(tree, None):
            with self.subTest(line=site.lineno):
                flipped = forced_failures.flip(MINI, site)
                old = MINI.split("\n")
                new = flipped.split("\n")
                changed = [i for i in range(len(old)) if old[i] != new[i]]
                self.assertTrue(len(old) == len(new) and changed == [site.lineno - 1],
                                "flipping changed a line other than the one call")
                swapped = old[site.lineno - 1].replace(
                    site.attr, forced_failures.FLIP[site.attr])
                self.assertTrue(new[site.lineno - 1] == swapped,
                                "the changed line differs by more than the call's name")

    def test_flip_swaps_the_names(self):
        site = forced_failures.sites(ast.parse(MINI), None)[0]
        self.assertTrue("self.assertFalse(1 == 1, 'a fixed message')" in
                        forced_failures.flip(MINI, site), "assertTrue did not become assertFalse")
        site = forced_failures.sites(ast.parse(MINI), None)[3]
        self.assertTrue("self.assertNotEqual(1, 1," in forced_failures.flip(MINI, site),
                        "assertEqual did not become assertNotEqual")

    def test_a_helper_runs_every_test_of_its_class_and_of_classes_inheriting_it(self):
        ids = forced_failures.test_ids(ast.parse(MINI), "tests.test_mini", "Base", "helper")
        self.assertTrue(ids == ["tests.test_mini.Child.test_uses_helper"],
                        "the helper does not map to the inheriting test")

    def test_judge(self):
        secrets = ["secret-text"]
        failing = "FAIL: test_a (x.Y)\n"
        self.assertTrue(forced_failures.judge(1, failing, secrets)[0], "a clean failure is not clean")
        self.assertFalse(forced_failures.judge(0, failing, secrets)[0], "an exit of 0 is clean")
        self.assertFalse(forced_failures.judge(1, "OK\n", secrets)[0], "no FAIL line is clean")
        self.assertFalse(forced_failures.judge(1, failing + "ERROR: test_b (x.Y)\n", secrets)[0],
                         "an ERROR line is clean")
        self.assertFalse(forced_failures.judge(1, failing + "secret-text\n", secrets)[0],
                         "a leaked secret is clean")


class MiniTree(unittest.TestCase):
    def run_mini(self):
        with tempfile.TemporaryDirectory() as folder:
            root = os.path.join(folder, "copy")
            path = write_mini(root)
            before = read_all(path)
            rows = forced_failures.force(root, [("tests/test_mini.py", ("Mini",))],
                                         [sys.executable], [MARKER], folder)
            after = read_all(path)
        return rows, before, after

    def test_a_clean_a_leaking_and_an_unfailing_assertion(self):
        rows, _, _ = self.run_mini()
        self.assertTrue([r["ok"] for r in rows] == [True, False, False],
                        "the three rows are not clean, BAD and BAD")

    def test_the_file_is_byte_identical_afterwards(self):
        _, before, after = self.run_mini()
        self.assertTrue(before == after, "the file differs after the run")

    def test_a_helper_assertion_in_a_class_with_a_child_is_forced(self):
        with tempfile.TemporaryDirectory() as folder:
            root = os.path.join(folder, "copy")
            write_mini(root)
            rows = forced_failures.force(root, [("tests/test_mini.py", ("Base",))],
                                         [sys.executable], [MARKER], folder)
        self.assertTrue([r["ok"] for r in rows] == [True], "the helper row is not clean")

    def test_totals_line(self):
        rows = [{"ok": True}, {"ok": False}, {"ok": False}]
        self.assertTrue(forced_failures.totals(rows) == "assertions forced: 3; not clean: 2",
                        "the totals line is not as documented")

    def test_a_bad_row_prints_no_output(self):
        rows, _, _ = self.run_mini()
        text = "\n".join(forced_failures.row_text(r) for r in rows)
        self.assertTrue(MARKER not in text and "Traceback" not in text,
                        "a row holds captured output")


GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "gc.auto=0",
       "-c", "maintenance.auto=false", "-c", "commit.gpgsign=false"]

CLEAN_MODULE = (
    "import subprocess\n"
    "import unittest\n"
    "\n"
    "\n"
    "class M(unittest.TestCase):\n"
    "    def test_a(self):\n"
    "        self.assertTrue(1 == 1, 'a fixed message')\n"
)

LEAKING_MODULE = (
    "import subprocess\n"
    "import unittest\n"
    "\n"
    "\n"
    "class M(unittest.TestCase):\n"
    "    def test_leaks(self):\n"
    "        self.assertTrue(1 == 1, '" + MARKER + "')\n"
)

FAIL_ONLY_MODULE = (
    "import subprocess\n"
    "import unittest\n"
    "\n"
    "\n"
    "class M(unittest.TestCase):\n"
    "    def test_a(self):\n"
    "        self.fail('a fixed message')\n"
)

PLAIN_MODULE = (
    "import unittest\n"
    "\n"
    "\n"
    "class M(unittest.TestCase):\n"
    "    def test_a(self):\n"
    "        self.assertTrue(1 == 1, 'a fixed message')\n"
)


class Main(unittest.TestCase):
    def make_repo(self, folder, files, commit=True):
        """A git repository at folder/repo holding the files, an empty tests/__init__.py and,
        when commit is true, one commit."""
        repo = os.path.join(folder, "repo")
        for rel, text in [("tests/__init__.py", "")] + list(files):
            path = os.path.join(repo, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(text.encode("utf-8"))
        env = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin", "HOME": folder}
        steps = [["init", "-q"]]
        if commit:
            steps += [["add", "-A"], ["commit", "-q", "-m", "invented"]]
        for step in steps:
            proc = subprocess.run(GIT + step, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertTrue(proc.returncode == 0, "git failed")
        return repo

    def run_main(self, folder, repo, argv):
        """main()'s return code, what it printed, and the names in folder afterwards."""
        old = tempfile.tempdir
        tempfile.tempdir = folder
        try:
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                code = forced_failures.main(argv, repo=repo)
        finally:
            tempfile.tempdir = old
        return code, printed.getvalue(), sorted(os.listdir(folder))

    def test_a_clean_repository_exits_0_and_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.make_repo(folder, [("tests/test_mini.py", CLEAN_MODULE)])
            code, text, listing = self.run_main(folder, repo, [])
        self.assertEqual(code, 0, "a clean repository does not exit 0")
        self.assertTrue(text.strip().split("\n")[-1].startswith("assertions forced: 1;"),
                        "the last line does not count the one assertion")
        self.assertTrue(listing == ["repo"], "the run left a folder behind")

    def test_keep_leaves_the_work_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.make_repo(folder, [("tests/test_mini.py", CLEAN_MODULE)])
            code, text, listing = self.run_main(folder, repo, ["--keep"])
            kept = [name for name in listing if name != "repo"]
            for name in kept:
                shutil.rmtree(os.path.join(folder, name))
        self.assertEqual(code, 0, "a clean repository with --keep does not exit 0")
        self.assertTrue(any(line.startswith("kept: ") for line in text.split("\n")),
                        "no line says what was kept")
        self.assertTrue(len(kept) == 1, "--keep did not leave exactly one folder")

    def test_a_repository_with_no_commit_exits_2_and_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.make_repo(folder, [("tests/test_mini.py", CLEAN_MODULE)], commit=False)
            code, text, listing = self.run_main(folder, repo, [])
        self.assertEqual(code, 2, "a repository with no commit does not exit 2")
        self.assertTrue("could not run: git archive failed" in text,
                        "the could-not-run line is missing")
        self.assertTrue(listing == ["repo"], "the failed run left a folder behind")

    def test_an_unclean_row_exits_1(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.make_repo(folder, [("tests/test_mini.py", LEAKING_MODULE)])
            code, _, _ = self.run_main(folder, repo, ["--marker", MARKER])
        self.assertEqual(code, 1, "a row that is not clean does not exit 1")

    def test_a_scope_with_nothing_to_flip_exits_2(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.make_repo(folder, [("tests/test_mini.py", FAIL_ONLY_MODULE)])
            code, text, _ = self.run_main(folder, repo, [])
        self.assertEqual(code, 2, "a scope with nothing to flip does not exit 2")
        self.assertTrue("no assertion in scope" in text, "the could-not-run reason is missing")

    def test_no_child_process_module_exits_2(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.make_repo(folder, [("tests/test_mini.py", PLAIN_MODULE)])
            code, text, _ = self.run_main(folder, repo, [])
        self.assertEqual(code, 2, "a scope with no child-process module does not exit 2")
        self.assertTrue("no assertion in scope" in text, "the could-not-run reason is missing")

    def test_a_module_with_nothing_flipped_is_named_and_exits_1(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.make_repo(folder, [("tests/test_a.py", CLEAN_MODULE),
                                           ("tests/test_b.py", FAIL_ONLY_MODULE)])
            code, text, _ = self.run_main(folder, repo, [])
        lines = text.strip().split("\n")
        self.assertEqual(code, 1, "a module with nothing flipped does not exit 1")
        self.assertTrue("no assertion flipped in: tests/test_b.py" in lines,
                        "the module with nothing flipped is not named")
        self.assertTrue(lines[-1] == "assertions forced: 1; not clean: 0",
                        "the totals line is not last or does not count rows only")

    def test_a_fail_call_is_counted_as_not_flipped(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.make_repo(folder, [("tests/test_mini.py", CLEAN_MODULE + (
                "\n"
                "    def test_b(self):\n"
                "        self.fail('a fixed message')\n"))])
            _, text, _ = self.run_main(folder, repo, [])
        lines = text.strip().split("\n")
        self.assertTrue("not flipped: 1 (assertRaises and fail calls, which this script does not "
                        "force)" in lines, "the not-flipped line does not count the fail call")
        self.assertTrue(lines[-1].startswith("assertions forced: 1;"),
                        "the totals line is not last")


if __name__ == "__main__":
    unittest.main()
