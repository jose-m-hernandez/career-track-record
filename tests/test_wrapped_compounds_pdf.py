"""Tests for ``track-record wrapped-compounds`` on PDFs (spec: docs/specs/wrapped-compounds.md, section 10).

Cases W1, W2, W12 and W13 run the command on PDFs generated in the test run by
tests/fixtures/barred/make_fixtures.py, the generator the barred PDF tests use; the rest read
the committed PDFs of that folder or other generated ones. Tests that need the real
pdftotext go through one gate: they run where it is installed, fail in CI where it is not,
and skip elsewhere. W12 puts an empty directory on PATH instead. All data here is invented.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures", "barred")
sys.path.insert(0, SRC)

from career_track_record import pdf_text  # noqa: E402

CONTROL = "Example Corp"
FINDING_TAIL = ("  next: reword or change the layout so the word does not break at its hyphen, "
                "export the PDF again, and run this again\n")
NOT_A_PDF = "not a PDF; give the PDF file"


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


def run_cli(args, cwd=FX, env_extra=None):
    proc = subprocess.run([sys.executable, "-m", "career_track_record", "wrapped-compounds"]
                          + list(args), cwd=cwd, env=env(env_extra), stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def line_ending(path, suffix, page=1):
    """The 1-based number, on its page, of the first layout line that ends in ``suffix``."""
    text = pdf_text.pdf_text(path, layout=True)
    lines = text.split("\f")[page - 1].split("\n")
    for index, line in enumerate(lines):
        if line.rstrip().endswith(suffix):
            return index + 1
    raise AssertionError("no layout line ends in %r" % suffix)


def fail_block(path, hit_lines):
    return ("FAIL  %s: %d finding(s); lines marked \"finding\" need a fix, other lines are "
            "for information\n" % (path, len(hit_lines)) + "".join(hit_lines) + FINDING_TAIL)


def hit(page, line, compound, joined):
    return ('  wrapped compounds: page %d line %d: "%s" is split across lines; extracted '
            'text reads "%s" (finding)\n' % (page, line, compound, joined))


def ok_line(path, count=0):
    return "OK    %s: %d split compounds looked at, 0 findings (control found)\n" % (path, count)


class PdfCase(unittest.TestCase):
    """A case that needs pdftotext, and a temporary folder holding the generated PDFs."""

    def setUp(self):
        gate = pdftotext_gate(shutil.which("pdftotext") is not None, os.environ)
        if gate == "skip":
            self.skipTest("pdftotext is not installed")
        if gate == "fail":
            self.fail("pdftotext is not installed in CI; install poppler-utils so the "
                      "wrapped-compounds PDF tests run")
        self.m = load_make_fixtures()
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def pdf(self, name, pages):
        path = os.path.join(self.tmp, name)
        with open(path, "wb") as handle:
            handle.write(self.m.pages_pdf(pages))
        return path

    def pad(self, middle):
        """One page: the generator's padding line twelve times, the ``middle`` lines, then
        the padding line twelve times."""
        return [[[self.m.PAD_LINE] * 12 + list(middle) + [self.m.PAD_LINE] * 12]]

    def w1(self, name="w1.pdf"):
        return self.pdf(name, self.pad(["The well-", "known results held."]))

    def w2(self, name="w2.pdf"):
        return self.pdf(name, self.pad(["The well-known results held."]))


class GateCase(unittest.TestCase):
    def test_the_gate_runs_fails_or_skips(self):
        self.assertEqual(pdftotext_gate(True, {}), "run")
        self.assertEqual(pdftotext_gate(True, {"GITHUB_ACTIONS": "true"}), "run")
        self.assertEqual(pdftotext_gate(False, {"GITHUB_ACTIONS": "true"}), "fail")
        self.assertEqual(pdftotext_gate(False, {"GITHUB_ACTIONS": "false"}), "skip")
        self.assertEqual(pdftotext_gate(False, {}), "skip")


class SpecPdfCases(PdfCase):
    def test_w1_planted_positive_and_the_premise(self):
        path = self.w1()
        # The premise: the default text joined the halves and the layout text kept them.
        self.assertIn("wellknown", pdf_text.pdf_text(path))
        self.assertNotIn("well-known", pdf_text.pdf_text(path))
        n = line_ending(path, "well-")
        code, out, err = run_cli(["--control", CONTROL, path])
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, fail_block(path, [hit(1, n, "well-known", "wellknown")]))
        self.assertEqual(n, 13)

    def test_w2_negative_control(self):
        path = self.w2()
        code, out, err = run_cli(["--control", CONTROL, path])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, ok_line(path) + "  wrapped compounds: none\n")

    def test_w12_pdftotext_missing(self):
        path = self.w2()
        empty = os.path.join(self.tmp, "empty-bin")
        os.mkdir(empty)
        code, out, err = run_cli(["--control", CONTROL, path], env_extra={"PATH": empty})
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "DEAD  %s: pdftotext not found\n" % path)

    def test_w13_control_not_found(self):
        path = self.w2()
        code, out, err = run_cli(["--control", "zzqx", path])
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "DEAD  %s: control not found; check that the text in the PDF "
                              "can be selected\n" % path)


class ControlCases(PdfCase):
    def test_one_control_found_is_enough(self):
        path = self.w2()
        for args in (["--control", "zzqx", "--control", CONTROL], ["--control", CONTROL,
                                                                  "--control", "zzqx"]):
            with self.subTest(args=args):
                self.assertEqual(run_cli(args + [path])[0:2],
                                 (0, ok_line(path) + "  wrapped compounds: none\n"))

    def test_an_empty_control_beside_a_good_one_is_dropped_and_the_good_one_is_used(self):
        path = self.w2()
        for empty in ("", "   ", "\t "):
            with self.subTest(empty=repr(empty)):
                self.assertEqual(run_cli(["--control", empty, "--control", CONTROL, path]),
                                 (0, ok_line(path) + "  wrapped compounds: none\n", ""))

    def test_an_empty_control_beside_a_missing_one_is_dead_not_a_usage_error(self):
        path = self.w2()
        code, out, err = run_cli(["--control", "", "--control", "zzqx", path])
        self.assertEqual((code, err), (2, ""))
        self.assertTrue(out.startswith("DEAD  " + path + ": control not found"))

    def test_control_equals_text_and_a_control_with_case_and_spaces(self):
        path = self.w2()
        for control in ("--control=Example Corp", "--control=EXAMPLE   corp"):
            with self.subTest(control=control):
                self.assertEqual(run_cli([control, path])[0], 0)
        self.assertEqual(run_cli(["--control", "  example   CORP ", path])[0], 0)

    def test_a_control_is_matched_in_the_joined_form_of_the_default_text(self):
        # "reporting tool" runs across a space in the padding line, and the control is
        # matched after whitespace runs are collapsed.
        path = self.w2()
        self.assertEqual(run_cli(["--control", "reporting     tool", path])[0], 0)
        self.assertEqual(run_cli(["--control", "tool\nfor", path])[0], 0)


class StatusCases(PdfCase):
    def test_a_dead_file_and_a_failing_file_exit_2_and_both_lines_are_printed(self):
        bad = self.w1("bad.pdf")
        good = self.w2("good.pdf")
        notes = os.path.join(self.tmp, "notes.txt")
        with open(notes, "w", encoding="utf-8") as handle:
            handle.write(CONTROL)
        code, out, err = run_cli(["--control", CONTROL, bad, notes, good])
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, fail_block(bad, [hit(1, 13, "well-known", "wellknown")]) +
                         "DEAD  %s: %s\n" % (notes, NOT_A_PDF) +
                         ok_line(good) + "  wrapped compounds: none\n")

    def test_status_lines_follow_the_argument_order(self):
        a, b = self.w2("a.pdf"), self.w1("b.pdf")
        first = run_cli(["--control", CONTROL, a, b])[1]
        second = run_cli(["--control", CONTROL, b, a])[1]
        self.assertEqual(first.index("OK    " + a) < first.index("FAIL  " + b), True)
        self.assertEqual(second.index("FAIL  " + b) < second.index("OK    " + a), True)

    def test_exit_1_when_a_file_fails_and_none_is_dead(self):
        self.assertEqual(run_cli(["--control", CONTROL, self.w1(), self.w2()])[0], 1)

    def test_a_note_is_not_a_failure(self):
        # Two pages: the word is wrapped on page 1 and printed whole on page 2. The default
        # text reads it unbroken on both, so the wrap is a note and the file is OK.
        path = self.pdf("note.pdf", [
            [[self.m.PAD_LINE] * 12 + ["The manage-", "ment team met."] + [self.m.PAD_LINE] * 12],
            [[self.m.PAD_LINE] * 12 + ["Good management matters."] + [self.m.PAD_LINE] * 12]])
        n = line_ending(path, "manage-")
        code, out, err = run_cli(["--control", CONTROL, path])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, ok_line(path, 1) +
                         '  wrapped compounds: page 1 line %d: "manage-ment" is split across '
                         'lines; extracted text reads "management" (note: "management" also '
                         'appears unwrapped, nothing to fix)\n' % n)

    def test_a_pdf_name_in_capitals_is_a_pdf(self):
        path = self.w1("RESUME.PDF")
        code, out, err = run_cli(["--control", CONTROL, path])
        self.assertEqual((code, err), (1, ""))
        self.assertTrue(out.startswith("FAIL  " + path + ": 1 finding(s)"))

    def test_a_path_that_starts_with_a_dash_is_read(self):
        self.w1("-lead.pdf")
        code, out, err = run_cli(["--control", CONTROL, "--", "-lead.pdf"], cwd=self.tmp)
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, fail_block("-lead.pdf", [hit(1, 13, "well-known", "wellknown")]))

    def test_a_missing_pdf_and_a_file_that_is_not_a_pdf_are_dead_with_barred_s_words(self):
        missing = os.path.join(self.tmp, "missing.pdf")
        junk = os.path.join(self.tmp, "junk.pdf")
        with open(junk, "wb") as handle:
            handle.write(b"this is not a pdf at all")
        code, out, err = run_cli(["--control", CONTROL, missing, junk])
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "DEAD  %s: cannot read\nDEAD  %s: pdftotext failed\n"
                         % (missing, junk))

    def test_a_pdf_with_no_selectable_text_is_dead(self):
        path = self.pdf("blank.pdf", [[[""]]])
        code, out, err = run_cli(["--control", "x", path])
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "DEAD  %s: no text; the PDF holds no selectable text (a scan?), "
                              "so export it again from the document\n" % path)

    def test_a_path_with_a_newline_is_printed_escaped(self):
        name = "line\nbreak.pdf"
        self.w1(name)
        code, out, err = run_cli(["--control", CONTROL, name], cwd=self.tmp)
        self.assertEqual((code, err), (1, ""))
        self.assertTrue(out.startswith("FAIL  line\\nbreak.pdf: 1 finding(s)"))


class PageCases(PdfCase):
    def test_a_wrap_on_page_three_is_found_on_page_three(self):
        pad = [self.m.PAD_LINE] * 12
        path = self.pdf("three.pdf", [[pad], [pad], [pad + ["The well-", "known results."] + pad]])
        n = line_ending(path, "well-", page=3)
        code, out, err = run_cli(["--control", CONTROL, path])
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, fail_block(path, [hit(3, n, "well-known", "wellknown")]))

    def test_a_wrap_at_the_foot_of_a_page_is_not_a_hit(self):
        pad = [self.m.PAD_LINE] * 12
        path = self.pdf("foot.pdf", [[pad + ["The well-"]], [["known results held."] + pad]])
        code, out, err = run_cli(["--control", CONTROL, path])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, ok_line(path) + "  wrapped compounds: none\n")


class CommittedPdfCases(PdfCase):
    def test_the_committed_wrap_inside_a_page_is_a_finding(self):
        path = os.path.join(FX, "hyphmid.pdf")
        n = line_ending(path, "zebra-")
        code, out, err = run_cli(["--control", CONTROL, path])
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, fail_block(path, [hit(1, n, "zebra-word", "zebraword")]))

    def test_the_committed_wrap_on_page_three_is_a_finding(self):
        path = os.path.join(FX, "page3wrap.pdf")
        n = line_ending(path, "zebra-", page=3)
        code, out, err = run_cli(["--control", CONTROL, path])
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, fail_block(path, [hit(3, n, "zebra-word", "zebraword")]))

    def test_known_limit_a_wrap_in_the_left_of_two_columns_is_missed(self):
        # Known limit (spec section 8, W9): in twocol.pdf the hyphen of "a zebra-" is not at
        # the end of the layout line, which goes on into the right column. The check says
        # what it found, and it does not claim to have found every wrap.
        path = os.path.join(FX, "twocol.pdf")
        self.assertEqual(run_cli(["--control", CONTROL, path]),
                         (0, ok_line(path) + "  wrapped compounds: none\n", ""))

    def test_known_limit_a_soft_hyphen_break_is_not_read(self):
        path = os.path.join(FX, "softhyph.pdf")
        self.assertEqual(run_cli(["--control", CONTROL, path]),
                         (0, ok_line(path) + "  wrapped compounds: none\n", ""))

    def test_a_wrap_across_a_page_break_is_not_a_hit(self):
        path = os.path.join(FX, "pagewrap.pdf")
        self.assertEqual(run_cli(["--control", CONTROL, path]),
                         (0, ok_line(path) + "  wrapped compounds: none\n", ""))


class GuideExampleCase(PdfCase):
    def test_the_guide_prints_what_the_command_prints_on_its_example(self):
        code, out, err = run_cli(["--control", "Example Corp", "hyphmid.pdf", "sample.pdf"])
        self.assertEqual((code, err), (1, ""))
        with open(os.path.join(ROOT, "docs", "guides", "wrapped-compounds.md"),
                  encoding="utf-8") as handle:
            guide = handle.read()
        printed = "".join("    " + line + "\n" for line in out.splitlines())
        self.assertEqual(guide.count(printed), 1)
        self.assertIn("    track-record wrapped-compounds --control Example\\ Corp hyphmid.pdf "
                      "sample.pdf\n", guide)


class NoConfigurationPdfCase(PdfCase):
    def test_an_unusable_config_changes_nothing(self):
        path = self.w1()
        cfg = os.path.join(self.tmp, "cfg")
        os.mkdir(cfg)
        with open(os.path.join(cfg, "config.json"), "w", encoding="utf-8") as handle:
            handle.write("not json at all")
        plain = run_cli(["--control", CONTROL, path])
        with_config = run_cli(["--control", CONTROL, path], env_extra={
            "CTR_CONFIG_DIR": cfg, "BARRED_STRINGS_PATH": os.path.join(cfg, "none.txt")})
        self.assertEqual(plain[0], 1)
        self.assertEqual(with_config, plain)


if __name__ == "__main__":
    unittest.main()
