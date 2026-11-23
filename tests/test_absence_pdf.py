"""Tests for ``track-record absence`` on PDFs (spec: docs/specs/absence.md, sections 3.3 and 9.6).

Case 9.6 runs the real ``pdftotext`` on a text file named as a PDF, which it cannot convert. A
real PDF is generated in the test run by tests/fixtures/barred/make_fixtures.py. The two reads
that must both succeed are tested with a stand-in ``pdftotext`` on PATH that fails in one mode
only, and a missing ``pdftotext`` with an empty folder on PATH. Tests that need the real
pdftotext go through one gate: they run where it is installed, fail in CI where it is not, and
skip elsewhere. All data here is invented.
"""

import hashlib
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures", "barred")
CMD = [sys.executable, "-m", "career_track_record"]
TERMS = "# an invented list\norbit-lantern\nvelvet compass\nquill\tword\nlanternfish\n"
FILES = "files: found %d, read %d, excluded %d, unreadable %d, links not followed %d\n"
STAND_IN = """#!/bin/sh
# A stand-in pdftotext: it fails in layout mode and gives fixed text in the default mode.
for arg in "$@"; do
  if [ "$arg" = "-layout" ]; then exit 1; fi
done
echo "a stand-in text"
"""


def pdftotext_gate(found, environ):
    """Run the real-program test if pdftotext is installed; fail in CI if not; else skip."""
    if found:
        return "run"
    if environ.get("GITHUB_ACTIONS") == "true":
        return "fail"
    return "skip"


def load_make_fixtures():
    spec = importlib.util.spec_from_file_location(
        "make_fixtures", os.path.join(FX, "make_fixtures.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def env(path=None):
    e = dict(os.environ)
    for name in ("BARRED_STRINGS_PATH", "BARRED_STRINGS", "CTR_CONFIG_DIR", "XDG_CONFIG_HOME"):
        e.pop(name, None)
    e["PYTHONPATH"] = SRC
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    if path is not None:
        e["PATH"] = path
    return e


class GateCase(unittest.TestCase):
    def test_the_gate_runs_fails_or_skips(self):
        self.assertEqual(pdftotext_gate(True, {}), "run")
        self.assertEqual(pdftotext_gate(False, {"GITHUB_ACTIONS": "true"}), "fail")
        self.assertEqual(pdftotext_gate(False, {"GITHUB_ACTIONS": "false"}), "skip")
        self.assertEqual(pdftotext_gate(False, {}), "skip")


class AbsencePdfCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        self.write("terms.txt", TERMS.encode("utf-8"))
        self.write("notes/vendors.txt", b"Approved vendors: Example Corp and Sample Ltd.\n")
        self.write("notes/plan.txt", b"The team sharpened its quills before the review.\n")
        self.write("summary.txt", b"A quarterly summary of invented work.\n")

    def write(self, rel, data):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)

    def declaration(self, exclusions=()):
        lines = ["label: no-vendor-terms", "list: terms.txt", "search:", "  notes",
                 "  summary.txt", "place: notes/vendors.txt", "control: approved vendors"]
        if exclusions:
            lines.append("exclusions:")
            lines.extend("  " + item for item in exclusions)
        data = ("\n".join(lines) + "\n").encode("utf-8")
        self.write("absence.txt", data)
        return "declaration sha256 %s\n" % hashlib.sha256(data).hexdigest()

    def run_cli(self, path=None):
        proc = subprocess.run(CMD + ["absence", "absence.txt"], cwd=self.root,
                              env=env(path), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        got = (proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8"))
        self.assertNotIn("Traceback", got[2])
        return got

    def need_pdftotext(self):
        verdict = pdftotext_gate(shutil.which("pdftotext") is not None, os.environ)
        if verdict == "fail":
            self.fail("pdftotext is not installed, and CI must run this test")
        if verdict == "skip":
            self.skipTest("pdftotext is not installed")

    def bin_dir(self, script=None):
        folder = os.path.join(self.root, "bin")
        os.makedirs(folder)
        if script is not None:
            target = os.path.join(folder, "pdftotext")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(script)
            os.chmod(target, stat.S_IRWXU)
        return folder

    # ---------------------------------------------------------------- 9.6

    def test_case_9_6_an_unreadable_file(self):
        """9.6: a text file named as a PDF, on which pdftotext fails, is unreadable and DEAD."""
        self.need_pdftotext()
        self.write("notes/broken.pdf", b"this is plain text, not a PDF\n")
        head = self.declaration()
        self.assertEqual(
            self.run_cli(),
            (2, head + FILES % (4, 3, 0, 1, 0) +
             "DEAD   no-vendor-terms: 1 unreadable files\n", ""))

    def test_case_9_6_with_an_exclusion_it_is_listed_not_dead(self):
        """9.6: excluded, it is counted as not read and the run is CLEAN."""
        self.need_pdftotext()
        self.write("notes/broken.pdf", b"this is plain text, not a PDF\n")
        head = self.declaration(("notes/broken.pdf | a scan with no text layer",))
        expected = (head + "excluded notes/broken.pdf: 0 hits in 1 files, 1 not read\n" +
                    FILES % (4, 3, 1, 0, 0) +
                    "CLEAN  no-vendor-terms: 0 hits in 3 files, 0 links not followed, "
                    "control found; excluding notes/broken.pdf\n")
        self.assertEqual(self.run_cli(), (0, expected, ""))
        self.assertNotIn("scan with no text layer", expected)

    # ---------------------------------------------------------------- PDF reads

    def test_a_term_in_a_real_pdf_is_found(self):
        """3.3: a PDF is read through pdftotext, and the file counts as read."""
        self.need_pdftotext()
        pdf = load_make_fixtures().pages_pdf([[["a velvet compass in a PDF"]]])
        self.write("notes/real.pdf", pdf)
        head = self.declaration()
        expected = (head + "hit notes/real.pdf: 1 hits, entries #2\n" + FILES % (4, 4, 0, 0, 0) +
                    "FOUND  no-vendor-terms: 1 hits in 4 files, 1 with hits, 0 links not "
                    "followed, control found\n")
        self.assertEqual(self.run_cli(), (1, expected, ""))

    def test_a_pdf_that_fails_in_layout_mode_only_is_unreadable(self):
        """3.3 and barred.md 7, case 6: a failure on either of the two reads is a failure."""
        self.write("notes/real.pdf", b"%PDF-1.4 a stand-in decides\n")
        head = self.declaration()
        folder = self.bin_dir(STAND_IN)
        self.assertEqual(
            self.run_cli(folder),
            (2, head + FILES % (4, 3, 0, 1, 0) +
             "DEAD   no-vendor-terms: 1 unreadable files\n", ""))

    def test_a_missing_pdftotext_makes_a_pdf_unreadable_and_a_text_file_still_read(self):
        """3.3: pdftotext is missing, so the PDF is unreadable; nothing else needs it."""
        self.write("notes/real.pdf", b"%PDF-1.4\n")
        head = self.declaration()
        folder = self.bin_dir()
        self.assertEqual(
            self.run_cli(folder),
            (2, head + FILES % (4, 3, 0, 1, 0) +
             "DEAD   no-vendor-terms: 1 unreadable files\n", ""))

    def test_a_pdf_name_is_searched_even_when_it_cannot_be_read(self):
        """4: the name check does not need the file to be readable; the run is still DEAD."""
        self.write("notes/orbit-lantern.pdf", b"%PDF-1.4\n")
        head = self.declaration()
        folder = self.bin_dir()
        code, out, err = self.run_cli(folder)
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, head + FILES % (4, 3, 0, 1, 0) +
                         "DEAD   no-vendor-terms: 1 unreadable files\n")
        self.assertNotIn("orbit-lantern", out)


if __name__ == "__main__":
    unittest.main()
