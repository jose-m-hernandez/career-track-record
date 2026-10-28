"""Tests for reading PDFs in ``track-record tone``. All data here is invented.

Most tests put a small stand-in ``pdftotext`` first on PATH; one runs the real program.
Rule files are written into a temporary folder at run time. No BARRED_STRINGS* variable
is passed to any command.
"""

import copy
import functools
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures", "tone")
BARRED_FX = os.path.join(ROOT, "tests", "fixtures", "barred")
sys.path.insert(0, SRC)

from career_track_record import barred, pdf_text, tone  # noqa: E402

WHY = "invented rationale"
SYSTEM_PATH = "/usr/bin:/bin"


def notfound(p):
    return "cannot run: cannot read %s: pdftotext not found" % p


def failed(p):
    return "cannot run: cannot read %s: pdftotext failed or timed out" % p


def unreadable(p):
    return "cannot run: cannot read %s" % p


def badutf8(p):
    return "cannot run: %s is not valid UTF-8" % p


def run_cli(args, cwd, path):
    env = dict(os.environ)
    env.pop("BARRED_STRINGS_PATH", None)
    env.pop("BARRED_STRINGS", None)
    env["PYTHONPATH"] = SRC
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = path
    with open(os.devnull, "rb") as devnull:
        proc = subprocess.run(
            [sys.executable, "-m", "career_track_record", "tone"] + list(args),
            cwd=cwd, env=env, stdin=devnull,
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


def finding(name, line, level, rule, sentence, category=None):
    label = "" if category is None else " [%s]" % category
    return "%s:%d: %s %s%s: %s\n    %s\n" % (name, line, level, rule, label, WHY, sentence)


def summary(files, errors, warnings):
    return "%d file(s), %d error(s), %d warning(s)\n" % (files, errors, warnings)


def r3_rules():
    rules = []
    for rule_id, text in (("end-dollar", "done$"), ("end-z", "done\\Z")):
        rules.append({"id": rule_id, "level": "warn", "kind": "regex", "text": text,
                      "case": "insensitive", "rationale": WHY,
                      "must_fire": ["It was done"], "must_not": ["done here"]})
    return {"rules": rules}


class PdfCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = os.path.join(self._tmp.name, "work")
        self.bin = os.path.join(self._tmp.name, "bin")
        self.empty = os.path.join(self._tmp.name, "empty")
        for folder in (self.work, self.bin, self.empty):
            os.mkdir(folder)
        for name in ("x.pdf", "X.PDF", "-x.pdf", "fake.pdf"):
            self.write(name, b"not really a pdf\n")
        # A rule file written at run time (a copy of R1, the spec's first rule file).
        self.rules = os.path.join(self.work, "rules.json")
        shutil.copyfile(os.path.join(FX, "rules-r1.json"), self.rules)

    def write(self, name, data):
        with open(os.path.join(self.work, name), "wb") as handle:
            handle.write(data)

    def scratch(self, name, data):
        path = os.path.join(self.work, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return path

    def path_with(self, body):
        stand_in(self.bin, body)
        return self.bin + os.pathsep + SYSTEM_PATH

    def run_with(self, body, args, name="x.pdf", rules=None):
        path = self.path_with(body)
        return run_cli(["--rules", rules or self.rules] + list(args) + [name],
                       self.work, path)

    def run_empty(self, args, rules=None):
        return run_cli(["--rules", rules or self.rules] + list(args), self.work, self.empty)

    def timed_out_run(self, name):
        """tone.run with a stand-in that outlasts a 1 s time limit: (Result, seconds)."""
        stand_in(self.bin, "exec sleep 5\n")
        short = functools.partial(pdf_text.pdf_text, timeout=1)
        started = time.time()
        with mock.patch.dict(os.environ, {"PATH": self.bin + os.pathsep + SYSTEM_PATH}):
            with mock.patch("career_track_record.pdf_text.pdf_text", short):
                result = tone.run(rules_path=self.rules,
                                  files=[os.path.join(self.work, name)])
        return result, time.time() - started

    def read_both(self, body, name="x.pdf"):
        """(tone's PDF read, barred's read) of the same stand-in output."""
        stand_in(self.bin, body)
        target = os.path.join(self.work, name)
        with mock.patch.dict(os.environ, {"PATH": self.bin + os.pathsep + SYSTEM_PATH}):
            return tone._read_pdf(target), barred._read_text(target, False)

    # ------------------------------------------------------------ the tests

    def test_pdf_text_is_checked(self):
        body = prints("One.\nTwo.\nA turnkey plan.\n")
        code, out, err = self.run_with(body, [])
        self.assertEqual((code, out, err), (
            1, finding("x.pdf", 3, "error", "turnkey", "A turnkey plan.")
            + summary(1, 1, 0), ""))

    def test_extension_is_matched_in_any_case(self):
        body = prints("One.\nTwo.\nA turnkey plan.\n")
        code, out, err = self.run_with(body, [], name="X.PDF")
        self.assertEqual((code, out, err), (
            1, finding("X.PDF", 3, "error", "turnkey", "A turnkey plan.")
            + summary(1, 1, 0), ""))

    def test_clean_pdf_is_clean(self):
        code, out, err = self.run_with(prints("Nothing to flag here.\n"), [])
        self.assertEqual((code, out, err), (0, "x.pdf: clean\n" + summary(1, 0, 0), ""))

    def test_pdftotext_not_found(self):
        code, out, err = self.run_empty(["x.pdf"])
        self.assertEqual((code, out, err), (2, "", notfound("x.pdf") + "\n"))

    def test_pdftotext_failed(self):
        code, out, err = self.run_with(prints("A turnkey plan.\n") + "exit 3\n", [])
        self.assertEqual((code, out, err), (2, "", failed("x.pdf") + "\n"))

    def test_pdftotext_timeout_is_failed(self):
        result, seconds = self.timed_out_run("x.pdf")
        target = os.path.join(self.work, "x.pdf")
        self.assertEqual((result.exit_code, result.text, result.error),
                         (2, "", failed(target)))
        self.assertLess(seconds, 4)

    def test_missing_pdf_cannot_be_read(self):
        code, out, err = self.run_with(prints("Fine.\n"), [], name="absent.pdf")
        self.assertEqual((code, out, err), (2, "", unreadable("absent.pdf") + "\n"))

    def test_all_inputs_read_before_output(self):
        self.write("good.txt", b"A turnkey plan.\n")
        path = self.path_with(prints("Fine.\n") + "exit 3\n")
        code, out, err = run_cli(["--rules", self.rules, "good.txt", "x.pdf"],
                                 self.work, path)
        self.assertEqual((code, out, err), (2, "", failed("x.pdf") + "\n"))

    def test_leading_dash_pdf_is_passed_safely(self):
        body = 'case "$1" in -*) exit 1;; esac\n' + prints("A turnkey plan.\n")
        code, out, err = self.run_with(body, ["--"], name="-x.pdf")
        self.assertEqual((code, out, err), (
            1, finding("-x.pdf", 1, "error", "turnkey", "A turnkey plan.")
            + summary(1, 1, 0), ""))

    def test_form_feed_is_not_a_line_break(self):
        code, out, err = self.run_with(prints("first\n\fturnkey here\n"), [])
        self.assertEqual((code, out, err), (
            1, finding("x.pdf", 2, "error", "turnkey", "first turnkey here")
            + summary(1, 1, 0), ""))

    def test_invalid_utf8_output_cannot_be_read(self):
        code, out, err = self.run_with("printf 'ok \\377\\n'\n", [])
        self.assertEqual((code, out, err), (2, "", badutf8("x.pdf") + "\n"))

    def test_parity_with_barred(self):
        for label, body in (("plain", prints("Plain text.\nSecond line.\n")),
                            ("form feed", prints("Page one.\n\fPage two.\n"))):
            with self.subTest(label):
                ours, theirs = self.read_both(body)
                self.assertEqual(ours.encode("utf-8"), theirs.encode("utf-8"))
                self.assertIn("Page" if "feed" in label else "Plain", ours)

    def test_pdf_error_lines_print_the_name_escaped(self):
        odd = "a\nb.pdf"
        self.write(odd, b"not really a pdf\n")
        with self.subTest("failed"):
            self.assertEqual(self.run_with("exit 1\n", [], name=odd), (
                2, "", "cannot run: cannot read a\\nb.pdf: pdftotext failed or timed out\n"))
        with self.subTest("not found"):
            self.assertEqual(self.run_empty([odd]), (
                2, "", "cannot run: cannot read a\\nb.pdf: pdftotext not found\n"))
        with self.subTest("not UTF-8"):
            self.assertEqual(self.run_with("printf 'ok \\377\\n'\n", [], name=odd), (
                2, "", "cannot run: a\\nb.pdf is not valid UTF-8\n"))
        with self.subTest("missing"):
            self.assertEqual(self.run_with(prints("Fine.\n"), [], name="c\nd.pdf"), (
                2, "", "cannot run: cannot read c\\nd.pdf\n"))

    def test_known_answers_from_rev6(self):
        r3 = self.scratch("r3.json", r3_rules())
        # 11.55 and 11.56 (regex `$`), text files.
        with self.subTest("11.55"):
            self.write("done.txt", b"It was done\n")
            code, out, err = run_cli(["--rules", r3, "done.txt"], self.work, self.empty)
            self.assertEqual((code, out, err), (
                0, finding("done.txt", 1, "warn", "end-dollar", "It was done")
                + summary(1, 0, 1), ""))
        with self.subTest("11.56"):
            self.write("lf2.txt", b"It was done\n\n")
            self.write("crlf.txt", b"It was done\r\n")
            code, out, err = run_cli(["--rules", r3, "lf2.txt", "crlf.txt"],
                                     self.work, self.empty)
            self.assertEqual((code, out, err), (
                0, "lf2.txt: clean\ncrlf.txt: clean\n" + summary(2, 0, 0), ""))
        turnkey = finding("x.pdf", 1, "error", "turnkey", "A turnkey plan.") + summary(1, 1, 0)
        with self.subTest("11.57"):
            self.assertEqual(self.run_with(prints("A turnkey plan.\n"), []),
                             (1, turnkey, ""))
        with self.subTest("11.58"):
            code, out, err = self.run_with(prints("A turnkey plan.\n"), [], name="X.PDF")
            self.assertEqual((code, out, err), (
                1, turnkey.replace("x.pdf", "X.PDF"), ""))
        with self.subTest("11.59"):
            code, out, err = self.run_with(prints("Then we moved on. We stayed.\n"), [])
            self.assertEqual((code, out, err), (
                0, finding("x.pdf", 1, "warn", "lower-we", "Then we moved on.")
                + summary(1, 0, 1), ""))
        page_two = "Page one.\n\fturnkey here\n"
        with self.subTest("11.60"):
            code, out, err = self.run_with(prints(page_two), [])
            self.assertEqual((code, out, err), (
                1, finding("x.pdf", 2, "error", "turnkey", "turnkey here")
                + summary(1, 1, 0), ""))
        with self.subTest("11.61"):
            ours, theirs = self.read_both(prints(page_two))
            self.assertEqual(ours.encode("utf-8"), theirs.encode("utf-8"))
            self.assertEqual(ours, page_two)
        with self.subTest("11.62"):
            code, out, err = self.run_empty(["x.pdf"])
            self.assertEqual((code, out), (2, ""))
        with self.subTest("11.63 failing pdftotext"):
            code, out, err = self.run_with("exit 1\n", [], name="fake.pdf")
            self.assertEqual((code, out), (2, ""))
        with self.subTest("11.63 slow pdftotext"):
            result, seconds = self.timed_out_run("fake.pdf")
            self.assertEqual((result.exit_code, result.text), (2, ""))
            self.assertLess(seconds, 4)
        with self.subTest("11.64"):
            with open(self.rules, encoding="utf-8") as handle:
                data = copy.deepcopy(json.load(handle))
            for rule in data["rules"]:
                if rule["id"] == "turnkey":
                    del rule["must_fire"]
            scratch = self.scratch("r1-no-must-fire.json", data)
            code, out, err = self.run_empty(["x.pdf"], rules=scratch)
            self.assertEqual((code, out, err), (
                2, "", "self-test: rule turnkey: must_fire is missing\n"))


class RealPdftotextCase(unittest.TestCase):
    def test_real_pdftotext_reads_the_sample(self):
        if shutil.which("pdftotext") is None:
            self.skipTest("pdftotext is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            rules = os.path.join(tmp, "rules.json")
            with open(rules, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps({"rules": [{
                    "id": "synergy", "level": "error", "kind": "phrase",
                    "text": "turnkey synergy", "case": "insensitive", "rationale": WHY,
                    "must_fire": ["a turnkey synergy here"],
                    "must_not": ["turnkey and synergy"]}]}) + "\n")
            code, out, err = run_cli(["--rules", rules, "sample.pdf"], BARRED_FX,
                                     os.environ.get("PATH", ""))
        self.assertEqual(code, 1)
        self.assertEqual(err, "")
        self.assertTrue(out.startswith("sample.pdf:13: error synergy: " + WHY + "\n"), out)
        self.assertTrue(out.endswith(summary(1, 1, 0)), out)


if __name__ == "__main__":
    unittest.main()
