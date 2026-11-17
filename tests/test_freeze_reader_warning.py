"""Tests that ab and panel freeze warn, and still write, when a live reader's program cannot
be started. All data here is invented; no reader is ever started."""

import os
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from tests import test_ab, test_panel  # noqa: E402


def ab_setup(case, command):
    return test_ab.Setup(case, readers=["r1 | fake | family m1",
                                        "r2 | %s | family m2" % command])


def panel_setup(case, command):
    return test_panel.Setup(case, readers=["r1 | fake", "r2 | %s" % command])


class FreezeWarnsCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = os.path.realpath(tmp.name)

    def make(self, name, mode):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\n")
        os.chmod(path, mode)
        return path

    def each(self):
        for label, build in (("ab", ab_setup), ("panel", panel_setup)):
            yield label, build

    def check(self, build, command, *needles):
        s = build(self, command)
        result = s.freeze()
        self.assertEqual((result.exit_code, result.ran, result.error), (0, True, ""))
        self.assertTrue(os.path.isfile(s.path("plan.txt.freeze")))
        lines = result.warnings.splitlines()
        self.assertEqual(len(lines), 1, result.warnings)
        self.assertTrue(lines[0].startswith("warning: reader r2: "), lines[0])
        for needle in needles:
            self.assertIn(needle, lines[0])

    def test_an_absolute_program_that_does_not_exist(self):
        missing = os.path.join(self.dir, "no-such-reader")
        for label, build in self.each():
            with self.subTest(label):
                self.check(build, shlex.quote(missing), "does not exist", missing)

    def test_an_absolute_program_that_is_not_executable(self):
        path = self.make("plain", stat.S_IRUSR | stat.S_IWUSR)
        if os.access(path, os.X_OK):
            self.skipTest("this account can execute any file")
        for label, build in self.each():
            with self.subTest(label):
                self.check(build, shlex.quote(path), "not executable", path)

    def test_a_bare_name_that_is_not_on_path(self):
        for label, build in self.each():
            with self.subTest(label):
                self.check(build, "no-such-reader-zq", "not on PATH", "no-such-reader-zq")

    def test_an_absolute_py_argument_that_does_not_exist(self):
        script = os.path.join(self.dir, "gone.py")
        command = shlex.quote(sys.executable) + " " + shlex.quote(script)
        for label, build in self.each():
            with self.subTest(label):
                self.check(build, command, "script does not exist", script)

    def test_a_reader_that_can_start_gives_no_warning(self):
        script = self.make("here.py", stat.S_IRUSR)
        command = shlex.quote(sys.executable) + " " + shlex.quote(script)
        for label, build in self.each():
            with self.subTest(label):
                result = build(self, command).freeze()
                self.assertEqual((result.exit_code, result.warnings), (0, ""))

    def test_the_freeze_file_is_byte_identical_with_and_without_the_warning(self):
        program = os.path.join(self.dir, "reader")
        command = shlex.quote(program)
        for label, build in self.each():
            with self.subTest(label):
                if os.path.exists(program):
                    os.remove(program)
                first = build(self, command)
                warned = first.freeze()
                self.assertNotEqual(warned.warnings, "")
                with open(first.path("plan.txt.freeze"), "rb") as handle:
                    with_warning = handle.read()
                self.make("reader", stat.S_IRWXU)
                second = build(self, command)
                clear = second.freeze()
                self.assertEqual(clear.warnings, "")
                with open(second.path("plan.txt.freeze"), "rb") as handle:
                    self.assertEqual(handle.read(), with_warning)

    def test_the_command_line_prints_the_warning_on_stderr_and_exits_0(self):
        missing = os.path.join(self.dir, "no-such-reader")
        s = ab_setup(self, shlex.quote(missing))
        env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"),
                   PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run([sys.executable, "-m", "career_track_record", "ab", "freeze",
                               s.plan_path], cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0)
        self.assertIn(b"freeze written", proc.stdout)
        err = proc.stderr.decode("utf-8")
        self.assertEqual(err.count("\n"), 1, err)
        self.assertIn("warning: reader r2: the program does not exist", err)


if __name__ == "__main__":
    unittest.main()
