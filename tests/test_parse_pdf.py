"""Tests for ``track-record parse`` on PDFs (spec: docs/specs/parse.md, section 7).

Cases P1 to P5, P8 and P9 run the command on PDFs generated in the test run by
tests/fixtures/barred/make_fixtures.py, through its ``pages_pdf``. P6 puts an empty directory
on PATH, and P7 puts a stand-in ``pdftotext`` there. Tests that need the real pdftotext go
through one gate: they run where it is installed, fail in CI where it is not, and skip
elsewhere. All data here is invented.
"""

import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures", "barred")
sys.path.insert(0, SRC)

from career_track_record import parse, pdf_text  # noqa: E402

TAIL = ("; fix them in the document the PDF was made from, make the PDF again, and run "
        "this again")
NO_TEXT = ("no text; the PDF holds no selectable text (a scan?), so export it again from the "
           "document")
NAME_NOT_FOUND = ("name not found; check that the name you gave matches the PDF, and that "
                  "its text can be selected")


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


def env(extra=None):
    e = dict(os.environ)
    for name in ("BARRED_STRINGS_PATH", "BARRED_STRINGS", "CTR_CONFIG_DIR", "XDG_CONFIG_HOME"):
        e.pop(name, None)
    e["PYTHONPATH"] = SRC
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


def run_cli(args, cwd=ROOT, env_extra=None):
    proc = subprocess.run([sys.executable, "-m", "career_track_record", "parse"] + list(args),
                          cwd=cwd, env=env(env_extra), stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def heading_lines(path, headings, page=1):
    """The 1-based line number, on its page, of each heading in pdftotext's own default text."""
    lines = pdf_text.pdf_text(path).split("\f")[page - 1].split("\n")
    return [lines.index(heading) + 1 for heading in headings]


class GateCase(unittest.TestCase):
    def test_the_gate_runs_fails_or_skips(self):
        self.assertEqual(pdftotext_gate(True, {}), "run")
        self.assertEqual(pdftotext_gate(True, {"GITHUB_ACTIONS": "true"}), "run")
        self.assertEqual(pdftotext_gate(False, {"GITHUB_ACTIONS": "true"}), "fail")
        self.assertEqual(pdftotext_gate(False, {"GITHUB_ACTIONS": "false"}), "skip")
        self.assertEqual(pdftotext_gate(False, {}), "skip")


class ExampleFileCase(unittest.TestCase):
    def test_the_committed_example_is_the_generator_s_base_fixture_byte_for_byte(self):
        with open(os.path.join(ROOT, "examples", "good.pdf"), "rb") as handle:
            committed = handle.read()
        self.assertEqual(committed, load_make_fixtures().parse_good_pdf())
        committed.decode("utf-8")


class PdfCase(unittest.TestCase):
    """A case that needs pdftotext, and a temporary folder holding the generated PDFs."""

    def setUp(self):
        gate = pdftotext_gate(shutil.which("pdftotext") is not None, os.environ)
        if gate == "skip":
            self.skipTest("pdftotext is not installed")
        if gate == "fail":
            self.fail("pdftotext is not installed in CI; install poppler-utils so the parse "
                      "PDF tests run")
        self.m = load_make_fixtures()
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name, data):
        path = os.path.join(self.tmp, name)
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def sections_line(self, path, found):
        """The sections line of a file with the given (family, heading) pairs, line numbers
        taken from pdftotext itself."""
        numbers = heading_lines(path, [heading for _family, heading in found])
        return "  sections: " + ", ".join(
            "%s found (page 1 line %d: %s)" % (family, number, heading)
            for (family, heading), number in zip(found, numbers))


class SpecPdfCases(PdfCase):
    def test_P1_planted_positive_the_sample_of_the_spec(self):
        path = self.write("good.pdf", self.m.parse_good_pdf())
        l1, l2, l3 = heading_lines(path, ["Experience", "Education", "Skills"])
        code, out, err = run_cli(["--name", "Ada Example", "--contact", "ada@example.com", path])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, "OK    %s\n"
                              "  text: 2 pages, 2 with text\n"
                              "  name: page 1\n"
                              '  contact "ada@example.com": page 1\n'
                              "  sections: experience found (page 1 line %d: Experience), "
                              "skills found (page 1 line %d: Skills), education found "
                              "(page 1 line %d: Education)\n"
                              "  dates: 1 format (Mon YYYY 5)\n"
                              "  wrapped compounds: none\n" % (path, l1, l3, l2))

    def test_P2_negative_control_a_name_that_is_not_there(self):
        path = self.write("good.pdf", self.m.parse_good_pdf())
        code, out, err = run_cli(["--name", "Bo Example", path])
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "DEAD  %s: %s\n  text: 2 pages, 2 with text\n"
                         % (path, NAME_NOT_FOUND))

    def test_P3_the_name_only_on_page_two(self):
        path = self.write("late.pdf", self.m.parse_name_page2_pdf())
        code, out, err = run_cli(["--name", "Ada Example", path])
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, "FAIL  %s: 1 finding%s\n"
                              "  text: 2 pages, 2 with text\n"
                              "  name: found on page 2, not page 1\n"
                              "%s\n"
                              "  dates: 1 format (Mon YYYY 1)\n"
                              "  wrapped compounds: none\n" % (
                                  path, TAIL, self.sections_line(
                                      path, [("experience", "Experience"),
                                             ("skills", "Skills")])))

    def test_P4_page_two_empty(self):
        path = self.write("empty2.pdf", self.m.parse_empty_page2_pdf())
        code, out, err = run_cli(["--name", "Ada Example", path])
        self.assertEqual((code, err), (1, ""))
        l1, l2, l3 = heading_lines(path, ["Experience", "Education", "Skills"])
        self.assertEqual(out, "FAIL  %s: 1 finding%s\n"
                              "  text: 2 pages, 1 with text\n"
                              "  page 2: little or no text (0 letters or digits)\n"
                              "  name: page 1\n"
                              "  sections: experience found (page 1 line %d: Experience), "
                              "skills found (page 1 line %d: Skills), education found "
                              "(page 1 line %d: Education)\n"
                              "  dates: 1 format (Mon YYYY 5)\n"
                              "  wrapped compounds: none\n" % (path, TAIL, l1, l3, l2))

    def test_P5_a_one_page_empty_pdf_is_dead(self):
        path = self.write("blank.pdf", self.m.parse_empty_pdf())
        code, out, err = run_cli(["--name", "Ada Example", path])
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "DEAD  %s: %s\n  text: 1 page, 0 with text\n"
                              "  page 1: little or no text (0 letters or digits)\n"
                         % (path, NO_TEXT))

    def test_P8_three_files_give_three_blocks_in_order(self):
        good = self.write("good.pdf", self.m.parse_good_pdf())
        late = self.write("late.pdf", self.m.parse_name_page2_pdf())
        notes = self.write("notes.txt", b"Ada Example")
        code, out, err = run_cli(["--name", "Ada Example", good, late, notes])
        self.assertEqual((code, err), (2, ""))
        starts = [line for line in out.splitlines() if not line.startswith("  ")]
        self.assertEqual(starts, ["OK    " + good,
                                  "FAIL  %s: 1 finding%s" % (late, TAIL),
                                  "DEAD  %s: not a PDF; give the PDF file" % notes])
        self.assertEqual(run_cli(["--name", "Ada Example", good, late])[0], 1)
        self.assertEqual(run_cli(["--name", "Ada Example", good])[0], 0)

    def test_P9_two_columns_the_result_as_found_today(self):
        # Known limit (spec section 8): the command does not check reading order in a
        # multi-column page. This pins today's behaviour for twocol.pdf, so a change to
        # column handling shows up as a changed case.
        path = os.path.join(FX, "twocol.pdf")
        code, out, err = run_cli(["--name", "Example Corp", path])
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, "FAIL  %s: 2 findings%s\n"
                              "  text: 1 page, 1 with text\n"
                              "  name: page 1\n"
                              "  sections: experience missing, skills missing\n"
                              "  dates: no date ranges found\n"
                              "  wrapped compounds: none\n" % (path, TAIL))



class StandInCases(unittest.TestCase):
    """P6 and P7 do not need the real pdftotext."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.pdf = os.path.join(self.tmp, "a.pdf")
        with open(self.pdf, "wb") as handle:
            handle.write(b"%PDF stand-in")

    def stand_in(self, body):
        directory = os.path.join(self.tmp, "bin")
        os.mkdir(directory)
        script = os.path.join(directory, "pdftotext")
        with open(script, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("#!/bin/sh\n" + body)
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
        return directory + ":/bin:/usr/bin"

    def test_P6_pdftotext_missing_is_dead_with_barred_s_reason(self):
        empty = os.path.join(self.tmp, "empty-bin")
        os.mkdir(empty)
        code, out, err = run_cli(["--name", "Ada Example", self.pdf],
                                 env_extra={"PATH": empty})
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "DEAD  %s: pdftotext not found\n" % self.pdf)

    def test_P7_a_failed_layout_read_is_dead_after_the_text_line(self):
        path = self.stand_in('case " $* " in *" -layout "*) exit 3 ;; esac\n'
                             'printf "Ada Example\\nExperience\\nSkills\\n"\n')
        code, out, err = run_cli(["--name", "Ada Example", self.pdf], env_extra={"PATH": path})
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "DEAD  %s: pdftotext failed\n  text: 1 page, 1 with text\n"
                         % self.pdf)

    def test_no_text_is_dead_before_a_failed_layout_read_is_looked_at(self):
        # Spec section 5: a file is DEAD at the first reason that holds; reason 4 (no text)
        # comes before reason 5 (pdftotext failed), and the layout read is not made first.
        log = os.path.join(self.tmp, "calls.log")
        path = self.stand_in('echo run >> "%s"\n'
                             'case " $* " in *" -layout "*) exit 1 ;; esac\n'
                             'printf "\\f"\n' % log)
        with mock.patch.dict(os.environ, {"PATH": path}):
            status, lines = parse.check_file(self.pdf, "Ada Example", [], ["skills"], 1)
        self.assertEqual(status, "DEAD")
        self.assertEqual(lines, ["DEAD  %s: %s" % (self.pdf, NO_TEXT), "  text: 1 page, 0 with text",
                                 "  page 1: little or no text (0 letters or digits)"])
        with open(log, encoding="utf-8") as handle:
            self.assertEqual(handle.read().count("run"), 1)

    def test_the_same_stand_in_failing_the_default_read_covers_an_encrypted_file(self):
        path = self.stand_in("exit 1\n")
        code, out, err = run_cli(["--name", "Ada Example", self.pdf], env_extra={"PATH": path})
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "DEAD  %s: pdftotext failed\n" % self.pdf)


if __name__ == "__main__":
    unittest.main()
