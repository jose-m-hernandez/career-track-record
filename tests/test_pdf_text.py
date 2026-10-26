"""Tests for reading PDFs in ``track-record barred``. All data here is invented.

Most tests put a small stand-in ``pdftotext`` first on PATH; one runs the real program.
No test reads a real list: BARRED_STRINGS_PATH and BARRED_STRINGS are removed from every
environment passed.
"""

import os
import inspect
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures", "barred")
sys.path.insert(0, SRC)

from career_track_record import pdf_text  # noqa: E402

PAD = "Example Corp shipped a reporting tool for teams."
CTRL = ["--control", "Example Corp"]
LIST_L1 = os.path.join(FX, "list-l1.txt")


def page(block):
    return "".join(line + "\n" for line in [PAD] * 12 + list(block) + [PAD] * 12)


def run_cli(args, cwd, path):
    env = dict(os.environ)
    env.pop("BARRED_STRINGS_PATH", None)
    env.pop("BARRED_STRINGS", None)
    env["PYTHONPATH"] = SRC
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = path
    proc = subprocess.run(
        [sys.executable, "-m", "career_track_record", "barred"] + list(args),
        cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def stand_in(directory, body):
    path = os.path.join(directory, "pdftotext")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IRUSR)


def prints(text):
    assert "'" not in text
    return "printf '%s' '" + text + "'\n"


class PdfSeamCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = os.path.join(self._tmp.name, "work")
        self.bin = os.path.join(self._tmp.name, "bin")
        self.empty = os.path.join(self._tmp.name, "empty")
        for folder in (self.work, self.bin, self.empty):
            os.mkdir(folder)
        for name in ("x.pdf", "X.PDF"):
            with open(os.path.join(self.work, name), "wb") as handle:
                handle.write(b"not really a pdf\n")

    def run_with(self, body, args, name="x.pdf"):
        stand_in(self.bin, body)
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        return run_cli(["--list", LIST_L1] + CTRL + list(args) + [name], self.work, path)

    def test_text_is_read(self):
        code, out, err = self.run_with(prints(page(["a turnkey synergy here"])), [])
        self.assertEqual((code, out, err), (1, "FAIL  x.pdf: 1 entries\n"
                                                "x.pdf:13: entry #1 (1 x)\n", ""))

    def test_extension_is_matched_in_any_case(self):
        code, out, err = self.run_with(prints(page(["a turnkey synergy here"])), [],
                                       name="X.PDF")
        self.assertEqual((code, out, err), (1, "FAIL  X.PDF: 1 entries\n"
                                                "X.PDF:13: entry #1 (1 x)\n", ""))

    def test_strip_comments_never_applies_to_a_pdf(self):
        code, out, err = self.run_with(prints(page(["// turnkey synergy"])),
                                       ["--strip-comments"])
        self.assertEqual((code, out, err), (1, "FAIL  x.pdf: 1 entries\n"
                                                "x.pdf:13: entry #1 (1 x)\n", ""))

    def test_form_feed_between_pages_is_not_a_line_break(self):
        first = "".join(PAD + "\n" for _ in range(12))
        second = "turnkey synergy on page two\n" + "".join(PAD + "\n" for _ in range(12))
        code, out, err = self.run_with(prints(first + "\f" + second + "\f"), [])
        self.assertEqual((code, out, err), (1, "FAIL  x.pdf: 1 entries\n"
                                                "x.pdf:13: entry #1 (1 x)\n", ""))

    def test_pdftotext_failed(self):
        code, out, err = self.run_with("exit 1\n", [])
        self.assertEqual((code, out, err), (2, "DEAD  x.pdf: pdftotext failed\n", ""))

    def test_failed_run_never_passes_a_file(self):
        code, out, err = self.run_with(prints(page(["fine"])) + "exit 3\n", [])
        self.assertEqual((code, out, err), (2, "DEAD  x.pdf: pdftotext failed\n", ""))

    def test_pdftotext_not_found(self):
        code, out, err = run_cli(["--list", LIST_L1] + CTRL + ["x.pdf"], self.work, self.empty)
        self.assertEqual((code, out, err), (2, "DEAD  x.pdf: pdftotext not found\n", ""))

    def test_missing_pdf_cannot_be_read(self):
        stand_in(self.bin, prints(page(["fine"])))
        code, out, err = run_cli(["--list", LIST_L1] + CTRL + ["absent.pdf"], self.work,
                                 self.bin)
        self.assertEqual((code, out, err), (2, "DEAD  absent.pdf: cannot read\n", ""))

    def test_clean_pdf_is_ok(self):
        code, out, err = self.run_with(prints(page(["nothing listed"])), [])
        self.assertEqual((code, err), (0, ""))
        self.assertRegex(out, r"\AOK    x.pdf: 0 of 5 entries \(control found; [0-9]+ chars\)\n\Z")

    def test_a_leading_dash_path_is_passed_safely(self):
        with open(os.path.join(self.work, "-x.pdf"), "wb") as handle:
            handle.write(b"not really a pdf\n")
        body = ('case "$1" in -*) exit 1;; esac\n'
                + prints(page(["turnkey synergy"])))
        code, out, err = self.run_with(body, ["--"], name="-x.pdf")
        self.assertEqual((code, out, err), (1, "FAIL  -x.pdf: 1 entries\n"
                                                "-x.pdf:13: entry #1 (1 x)\n", ""))

    def test_module_reasons(self):
        stand_in(self.bin, "exit 1\n")
        old = os.environ.get("PATH")
        try:
            os.environ["PATH"] = self.bin
            with self.assertRaises(pdf_text.PdfTextError) as failed:
                pdf_text.pdf_text(os.path.join(self.work, "x.pdf"))
            os.environ["PATH"] = self.empty
            with self.assertRaises(pdf_text.PdfTextError) as missing:
                pdf_text.pdf_text(os.path.join(self.work, "x.pdf"))
        finally:
            if old is None:
                del os.environ["PATH"]
            else:
                os.environ["PATH"] = old
        self.assertEqual(failed.exception.reason, "failed")
        self.assertEqual(missing.exception.reason, "not found")


    def test_invalid_bytes_become_replacement_characters_and_break_a_match(self):
        with open(os.path.join(self.work, "list.txt"), "w", encoding="utf-8") as handle:
            handle.write("turnkey synergy\n")
        body = (prints("".join(PAD + "\n" for _ in range(12)))
                + "printf 'turnkey syn\\377ergy\\n'\n"
                + prints("".join(PAD + "\n" for _ in range(12))))
        stand_in(self.bin, body)
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        code, out, err = run_cli(["--list", "list.txt"] + CTRL + ["x.pdf"], self.work, path)
        self.assertEqual((code, out, err),
                         (0, "OK    x.pdf: 0 of 1 entries (control found; 1193 chars)\n", ""))

    def test_a_slow_pdftotext_is_stopped_by_the_timeout(self):
        stand_in(self.bin, "exec sleep 5\n")
        old = os.environ.get("PATH")
        started = time.time()
        try:
            os.environ["PATH"] = self.bin
            with self.assertRaises(pdf_text.PdfTextError) as slow:
                pdf_text.pdf_text(os.path.join(self.work, "x.pdf"), timeout=1)
        finally:
            if old is None:
                del os.environ["PATH"]
            else:
                os.environ["PATH"] = old
        self.assertLess(time.time() - started, 4)
        self.assertEqual(slow.exception.reason, "failed")

    def test_the_default_timeout_is_60_seconds(self):
        self.assertEqual(inspect.signature(pdf_text.pdf_text).parameters["timeout"].default,
                         60)

    def _call_with_invalid_bytes(self, **kwargs):
        stand_in(self.bin, "printf 'ok \\377\\n'\n")
        old = os.environ.get("PATH")
        try:
            os.environ["PATH"] = self.bin
            return pdf_text.pdf_text(os.path.join(self.work, "x.pdf"), **kwargs)
        finally:
            if old is None:
                del os.environ["PATH"]
            else:
                os.environ["PATH"] = old

    def test_strict_errors_raise_on_invalid_utf8(self):
        with self.assertRaises(UnicodeDecodeError):
            self._call_with_invalid_bytes(errors="strict")

    def test_default_still_replaces_invalid_utf8(self):
        self.assertEqual(self._call_with_invalid_bytes(), "ok �\n")


class RealPdftotextCase(unittest.TestCase):
    def test_real_pdftotext_reads_the_sample(self):
        if shutil.which("pdftotext") is None:
            self.skipTest("pdftotext is not installed")
        code, out, err = run_cli(["--list", "list-l1.txt"] + CTRL + ["sample.pdf"], FX,
                                 os.environ.get("PATH", ""))
        self.assertEqual((code, out, err), (1, "FAIL  sample.pdf: 1 entries\n"
                                                "sample.pdf:13: entry #1 (1 x)\n", ""))


if __name__ == "__main__":
    unittest.main()
