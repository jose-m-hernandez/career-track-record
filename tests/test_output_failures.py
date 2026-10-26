"""Output that cannot be written, a closed standard error, and term patterns that cannot compile."""

import errno
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
KW = os.path.join(ROOT, "tests", "fixtures", "keywords")
BX = os.path.join(ROOT, "tests", "fixtures", "barred")
CMD = [sys.executable, "-m", "career_track_record"]
NO_OUTPUT = "cannot run: cannot write output\n"

sys.path.insert(0, SRC)

from career_track_record import cli  # noqa: E402


def env():
    e = dict(os.environ)
    e.pop("BARRED_STRINGS_PATH", None)
    e.pop("BARRED_STRINGS", None)
    e["PYTHONPATH"] = SRC
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def closed(args, cwd, fd):
    """Run with file descriptor fd (1 or 2) closed. Returns (code, stdout, stderr)."""
    redirect = ">&-" if fd == 1 else "2>&-"
    p = subprocess.run(["/bin/sh", "-c", 'exec "$0" "$@" ' + redirect] + CMD + list(args),
                       cwd=cwd, env=env(), stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


def broken(args, cwd):
    """Run with stdout a pipe whose reader is already gone. Returns (code, stderr)."""
    r, w = os.pipe()
    os.close(r)
    try:
        p = subprocess.run(CMD + list(args), cwd=cwd, env=env(), stdin=subprocess.DEVNULL,
                           stdout=w, stderr=subprocess.PIPE)
    finally:
        os.close(w)
    return p.returncode, p.stderr.decode("utf-8")


def broken_err(args, cwd):
    """Run with stderr a pipe whose reader is already gone. Returns (code, stdout)."""
    r, w = os.pipe()
    os.close(r)
    try:
        p = subprocess.run(CMD + list(args), cwd=cwd, env=env(), stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=w)
    finally:
        os.close(w)
    return p.returncode, p.stdout.decode("utf-8")


def normal(args, cwd):
    p = subprocess.run(CMD + list(args), cwd=cwd, env=env(), stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


KW_OK = ["keywords", "coverage", "--terms", "terms-t1.tsv", "copy.txt"]
KW_CANNOT = ["keywords", "coverage", "--terms", "missing.tsv", "copy.txt"]
B_LIST = ["barred", "--list", "list-l1.txt", "--control", "Example Corp"]
B_OK = B_LIST + ["clean.txt"]
B_FAIL = B_LIST + ["two.txt"]
B_CANNOT = ["barred", "--list", "list-l1.txt", "clean.txt"]
T_CWD = os.path.join(ROOT, "tests", "fixtures", "tone")
T_OK = ["tone", "--rules", "rules-r1.json", "case-11-01.txt"]  # spec 11.1: exit 1
T_CANNOT = ["tone", "--rules", "rules-r1.json"]                 # no input file: exit 2
T1 = os.path.join(KW, "terms-t1.tsv")

RUNS = [
    ("KW_OK", KW_OK, KW, 0),
    ("B_OK", B_OK, BX, 0),
    ("B_FAIL", B_FAIL, BX, 1),
    ("T_OK", T_OK, T_CWD, 1),
]
CANNOT = [("KW_CANNOT", KW_CANNOT, KW), ("B_CANNOT", B_CANNOT, BX),
          ("T_CANNOT", T_CANNOT, T_CWD)]
HELP = [["--help"], ["-h"], ["keywords", "--help"], ["keywords", "-h"],
        ["keywords", "demand", "--help"], ["keywords", "demand", "-h"],
        ["keywords", "coverage", "--help"], ["keywords", "coverage", "-h"],
        ["keywords", "report", "--help"], ["keywords", "report", "-h"]]


class _FullBuffer(object):
    def write(self, data):
        raise OSError(errno.ENOSPC, "No space left on device")

    def flush(self):
        pass


class _Full(object):
    buffer = _FullBuffer()

    def write(self, text):
        raise OSError(errno.ENOSPC, "No space left on device")

    def flush(self):
        pass


def _joined(args, cwd):
    """The args with every file the row names joined onto cwd (no chdir needed)."""
    out = list(args)
    for i, arg in enumerate(out):
        if arg.endswith((".tsv", ".txt", ".json")) and not arg.startswith("-") \
                and arg != "Example Corp" and (i == 0 or out[i - 1] != "--control"):
            out[i] = os.path.join(cwd, arg)
    return out


class OutputFailureCase(unittest.TestCase):
    def _table(self, pattern):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "terms.tsv")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("family\tpattern\tnote\nx\t%s\tn\n" % pattern)
        return path

    def _case_9(self, pattern, error):
        with self.assertRaises(error):
            re.compile(pattern, re.IGNORECASE)
        path = self._table(pattern)
        code, out, err = normal(["keywords", "coverage", "--terms", path, "copy.txt"], KW)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.splitlines()), 1)
        self.assertTrue(err.startswith(
            "cannot run: term pattern is not a valid regular expression: %s (" % pattern),
            err[:200])
        self.assertNotIn("Traceback", err)

    def test_the_runs_are_valid(self):
        for name, args, cwd, normal_code in RUNS:
            with self.subTest(run=name):
                code, out, err = normal(args, cwd)
                self.assertEqual(code, normal_code)
                self.assertNotEqual(out, "")
                self.assertEqual(err, "")
        for name, args, cwd in CANNOT:
            with self.subTest(run=name):
                code, out, err = normal(args, cwd)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertEqual(len(err.splitlines()), 1)
                self.assertTrue(err.startswith("cannot run: "), err)

    def test_closed_stdout_exits_2_with_one_line(self):
        for name, args, cwd, _code in RUNS:
            with self.subTest(run=name):
                self.assertEqual(closed(args, cwd, 1), (2, "", NO_OUTPUT))

    def test_broken_pipe_exits_2_with_one_line(self):
        for name, args, cwd, _code in RUNS:
            with self.subTest(run=name):
                self.assertEqual(broken(args, cwd), (2, NO_OUTPUT))

    def test_closed_stderr_keeps_a_cannot_run_at_2(self):
        for name, args, cwd in CANNOT:
            with self.subTest(run=name):
                self.assertEqual(closed(args, cwd, 2), (2, "", ""))

    def test_closed_stderr_keeps_a_normal_status(self):
        for name, args, cwd, _code in RUNS:
            with self.subTest(run=name):
                code, out, _err = normal(args, cwd)
                self.assertEqual(closed(args, cwd, 2), (code, out, ""))

    def test_failing_stderr_keeps_the_status(self):
        for name, args, cwd in CANNOT:
            with self.subTest(run=name):
                self.assertEqual(broken_err(args, cwd), (2, ""))
        for name, args, cwd, code in RUNS:
            with self.subTest(run=name):
                normal_code, normal_out, _ = normal(args, cwd)
                self.assertEqual(broken_err(args, cwd), (normal_code, normal_out))

    def test_a_full_disk_exits_2_with_one_line(self):
        for name, args, cwd, _code in RUNS:
            with self.subTest(run=name):
                stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
                with unittest.mock.patch.object(sys, "stdout", _Full()), \
                        unittest.mock.patch.object(sys, "stderr", stderr):
                    code = cli.main(_joined(args, cwd), environ={})
                    stderr.flush()
                    written = stderr.buffer.getvalue()
                self.assertEqual(code, 2)
                self.assertEqual(written, NO_OUTPUT.encode("utf-8"))

    def test_help_still_prints_to_stdout(self):
        for args in HELP:
            with self.subTest(args=args):
                code, out, err = normal(args, KW)
                self.assertEqual(code, 0)
                self.assertTrue(out.startswith("usage: track-record"), out[:80])
                self.assertEqual(err, "")

    def test_help_with_closed_stdout_exits_2_with_one_line(self):
        for args in HELP:
            with self.subTest(args=args):
                self.assertEqual(closed(args, KW, 1), (2, "", NO_OUTPUT))

    def test_help_with_broken_pipe_exits_2_with_one_line(self):
        for args in HELP:
            with self.subTest(args=args):
                self.assertEqual(broken(args, KW), (2, NO_OUTPUT))

    def test_help_with_closed_stderr_keeps_0(self):
        for args in HELP:
            with self.subTest(args=args):
                code, out, _ = normal(args, KW)
                self.assertEqual(closed(args, KW, 2), (0, out, ""))

    def test_help_on_a_full_disk_exits_2_with_one_line(self):
        for args in HELP:
            with self.subTest(args=args):
                stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
                with unittest.mock.patch.object(sys, "stdout", _Full()), \
                        unittest.mock.patch.object(sys, "stderr", stderr):
                    code = cli.main(list(args), environ={})
                    stderr.flush()
                    written = stderr.buffer.getvalue()
                self.assertEqual(code, 2)
                self.assertEqual(written, NO_OUTPUT.encode("utf-8"))

    def test_an_overflowing_pattern_is_case_9(self):
        self._case_9("x{99999999999}", OverflowError)

    def test_a_deeply_nested_pattern_is_case_9(self):
        self._case_9("(" * 2000, RecursionError)

    def test_an_invalid_pattern_is_still_case_9(self):
        self._case_9("x(", re.error)

    def test_the_spec_known_answers(self):
        with self.subTest(spec="barred 10.5"):
            self.assertEqual(closed(B_OK, BX, 1), (2, "", NO_OUTPUT))
            code, out, _err = closed(B_LIST, BX, 2)
            self.assertEqual((code, out), (2, ""))
            self.assertEqual(
                closed(B_OK, BX, 2),
                (0, "OK    clean.txt: 0 of 5 entries (control found; 1209 chars)\n", ""))
        with self.subTest(spec="keyword scan 11.7"):
            a = tempfile.mkdtemp()
            e = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, a)
            self.addCleanup(shutil.rmtree, e)
            shutil.copy(os.path.join(KW, "postings-p1", "2026-01-15-example-a.txt"), a)
            demand = ["keywords", "demand", "--postings", a, "--terms", T1]
            self.assertEqual(closed(demand, KW, 1), (2, "", NO_OUTPUT))
            code, out, _err = closed(demand, KW, 2)
            self.assertEqual((code, out), (0, normal(demand, KW)[1]))
            code, out, _err = closed(
                ["keywords", "demand", "--postings", e, "--terms", T1], KW, 2)
            self.assertEqual((code, out), (2, ""))
            path = self._table("(")
            code, out, err = normal(["keywords", "coverage", "--terms", path, "copy.txt"], KW)
            self.assertEqual((code, out), (2, ""))
            self.assertEqual(len(err.splitlines()), 1)
            self.assertTrue(err.startswith("cannot run: term pattern"), err)
        with self.subTest(spec="tone 11.49-11.51"):
            self.assertEqual(closed(T_OK, T_CWD, 1), (2, "", NO_OUTPUT))
            code, out, _err = closed(T_CANNOT, T_CWD, 2)
            self.assertEqual((code, out), (2, ""))
            code, out, _err = closed(T_OK, T_CWD, 2)
            self.assertEqual((code, out), (1, normal(T_OK, T_CWD)[1]))


if __name__ == "__main__":
    unittest.main()
