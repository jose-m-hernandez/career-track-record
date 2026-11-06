"""Tests for ``track-record barred`` reading each PDF in layout mode too (spec section 3.2).

All data here is invented. The committed fixtures used are, in tests/fixtures/barred/,
hyphmid.pdf, twocol.pdf, softhyph.pdf, pagewrap.pdf and page3wrap.pdf, the lists
list-l1.txt, list-l2.txt, list-l3.txt and list-l4.txt, and the text fixtures of the
spec's sections 10.1 to 10.9 named in LAYOUT_ROWS below. They are written by
tests/fixtures/barred/make_fixtures.py, whose one_page_pdf also builds the PDFs that
section B writes at run time. Tests that need the real pdftotext go through one gate:
they run where it is installed, fail in CI where it is not, and skip elsewhere. Section C
puts a stand-in pdftotext first on PATH instead. No test reads a real list:
BARRED_STRINGS_PATH and BARRED_STRINGS are removed from every environment passed.
"""

import importlib.util
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures", "barred")
sys.path.insert(0, SRC)

from career_track_record import pdf_text  # noqa: E402

L1 = "list-l1.txt"
L2 = "list-l2.txt"
L3 = "list-l3.txt"
L4 = "list-l4.txt"
CTRL = ["--control", "Example Corp"]
PAD = "Example Corp shipped a reporting tool for teams."
SOFT_HYPHEN = chr(0xAD)
LINE_BREAK = re.compile(r"\r\n|\r|\n")

L1_ENTRIES = [("turnkey synergy", False), ("rockstar ninja", False), ("—", False),
              ("moonshot", False), ("fix it", False)]
L3_ENTRIES = [("zebra-word", False)]
L4_ENTRIES = [("zebra", True), ("word", True)]
ACROSS_COLUMNS = "turnkey right column"


def pdftotext_gate(found, environ):
    """Run the real-program test if pdftotext is installed; fail in CI if not; else skip."""
    if found:
        return "run"
    if environ.get("GITHUB_ACTIONS") == "true":
        return "fail"
    return "skip"


def clean_env(extra=None):
    env = dict(os.environ)
    env.pop("BARRED_STRINGS_PATH", None)
    env.pop("BARRED_STRINGS", None)
    env["PYTHONPATH"] = SRC
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra or {})
    return env


def run_cli(args, cwd=FX, env_extra=None):
    proc = subprocess.run(
        [sys.executable, "-m", "career_track_record", "barred"] + list(args),
        cwd=cwd, env=clean_env(env_extra), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def contains_entry(text, entry, word):
    """Independent search: the literal entry, and for a word entry the boundary rule.

    A copy of tests/test_barred.py's helper of the same name."""
    start = 0
    while True:
        at = text.find(entry, start)
        if at < 0:
            return False
        if not word:
            return True
        end = at + len(entry)

        def edge(ch):
            category = unicodedata.category(ch)
            return not (category.startswith("L") or category == "Nd")

        if (at == 0 or edge(text[at - 1])) and (end == len(text) or edge(text[end])):
            return True
        start = at + 1


def fail_one(label, line, count=1):
    return "FAIL  %s: 1 entries\n%s:%d: entry #1 (%d x)\n" % (label, label, line, count)


def fx(name):
    return os.path.join(FX, name)


def line_number(lines, test):
    """The 1-based number of the first line for which test(line) holds, or None."""
    for index, line in enumerate(lines):
        if test(line):
            return index + 1
    return None


def load_make_fixtures():
    spec = importlib.util.spec_from_file_location("make_fixtures", fx("make_fixtures.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GateCase(unittest.TestCase):
    def test_the_gate_runs_fails_or_skips(self):
        self.assertEqual(pdftotext_gate(True, {}), "run")
        self.assertEqual(pdftotext_gate(True, {"GITHUB_ACTIONS": "true"}), "run")
        self.assertEqual(pdftotext_gate(False, {"GITHUB_ACTIONS": "true"}), "fail")
        self.assertEqual(pdftotext_gate(False, {"GITHUB_ACTIONS": "false"}), "skip")
        self.assertEqual(pdftotext_gate(False, {}), "skip")


class GatedCase(unittest.TestCase):
    def need_pdftotext(self):
        gate = pdftotext_gate(shutil.which("pdftotext") is not None, os.environ)
        if gate == "skip":
            self.skipTest("pdftotext is not installed")
        if gate == "fail":
            self.fail("pdftotext is not installed in CI; install poppler-utils so the "
                      "layout-mode tests run")

    def across_columns_list(self, tmp):
        path = os.path.join(tmp, "list-across.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(ACROSS_COLUMNS + "\n")
        return path


class RealPdftotextCase(GatedCase):
    """A: the committed PDF fixtures, read by the real pdftotext."""

    def test_a1_the_positive_control_is_a_wrap_inside_a_page(self):
        self.need_pdftotext()
        default = pdf_text.pdf_text(fx("hyphmid.pdf"))
        layout = pdf_text.pdf_text(fx("hyphmid.pdf"), layout=True)
        self.assertIn("a zebraword here", default)
        self.assertNotIn("zebra-", default)
        lines = LINE_BREAK.split(layout)
        pairs = [i for i in range(len(lines) - 1)
                 if lines[i].endswith("a zebra-") and lines[i + 1].startswith("word here")]
        self.assertEqual(len(pairs), 1, lines)

    def test_a2_both_halves_of_the_wrap_match_as_words(self):
        self.need_pdftotext()
        self.assertEqual(run_cli(["--list", L4] + CTRL + ["hyphmid.pdf"]),
                         (1, "FAIL  hyphmid.pdf: 2 entries\nhyphmid.pdf:13: entry #1 (1 x)\n"
                             "hyphmid.pdf:14: entry #2 (1 x)\n", ""))

    def test_a3_the_default_text_still_finds_what_it_found_before(self):
        self.need_pdftotext()
        layout = pdf_text.pdf_text(fx("twocol.pdf"), layout=True)
        self.assertNotIn("turnkey synergy", " ".join(layout.split()))
        self.assertEqual(run_cli(["--list", L1] + CTRL + ["twocol.pdf"]),
                         (1, fail_one("twocol.pdf", 13), ""))

    # Known limit: in a page set in columns, a wrap at a hyphen with another column's text beside it is not matched (spec section 3.2).
    def test_a4_a_wrap_beside_another_column_is_missed(self):
        self.need_pdftotext()
        code, out, err = run_cli(["--list", L3] + CTRL + ["twocol.pdf"])
        self.assertEqual((code, err), (0, ""))
        self.assertRegex(out, r"\AOK    twocol\.pdf: 0 of 1 entries \(control found; "
                              r"[0-9]+ chars\)\n\Z")

    # Known limit: in a page set in columns, an entry can match across the gap between two columns (spec section 3.2).
    def test_a5_an_entry_can_match_across_two_columns(self):
        self.need_pdftotext()
        with tempfile.TemporaryDirectory() as tmp:
            listing = self.across_columns_list(tmp)
            self.assertEqual(run_cli(["--list", listing] + CTRL + ["twocol.pdf"]),
                             (1, fail_one("twocol.pdf", 13), ""))

    def test_a6_a_soft_hyphen_at_a_line_end_counts_as_a_hyphen(self):
        self.need_pdftotext()
        self.assertEqual(run_cli(["--list", L1] + CTRL + ["softhyph.pdf"]),
                         (1, fail_one("softhyph.pdf", 13), ""))

    def test_a7_a_wrap_at_a_page_break_still_matches(self):
        self.need_pdftotext()
        self.assertEqual(run_cli(["--list", L3] + CTRL + ["pagewrap.pdf"]),
                         (1, fail_one("pagewrap.pdf", 13), ""))

    def test_a8_a_match_found_only_in_the_layout_text_has_its_line(self):
        self.need_pdftotext()
        layout = LINE_BREAK.split(pdf_text.pdf_text(fx("page3wrap.pdf"), layout=True))
        default = LINE_BREAK.split(pdf_text.pdf_text(fx("page3wrap.pdf")))
        layout_line = line_number(layout, lambda line: line.endswith("a zebra-"))
        default_line = line_number(default, lambda line: "zebraword" in line)
        self.assertIsNotNone(layout_line)
        self.assertIsNotNone(default_line)
        self.assertNotEqual(layout_line, default_line)
        self.assertEqual(run_cli(["--list", L3] + CTRL + ["page3wrap.pdf"]),
                         (1, fail_one("page3wrap.pdf", layout_line), ""))

    def test_a9_no_run_prints_an_entry_or_a_list_path(self):
        self.need_pdftotext()
        with tempfile.TemporaryDirectory() as tmp:
            across = self.across_columns_list(tmp)
            runs = [(L4, "hyphmid.pdf"), (L1, "twocol.pdf"), (L3, "twocol.pdf"),
                    (across, "twocol.pdf"), (L1, "softhyph.pdf"), (L3, "pagewrap.pdf"),
                    (L3, "page3wrap.pdf")]
            checks = L1_ENTRIES + L3_ENTRIES + L4_ENTRIES + [(ACROSS_COLUMNS, False)]
            for listing, name in runs:
                with self.subTest(listing=os.path.basename(listing), name=name):
                    _code, out, err = run_cli(["--list", listing] + CTRL + [name])
                    captured = (out + err).lower()
                    for entry, word in checks:
                        self.assertFalse(contains_entry(captured, entry, word), entry)
                    for path in (L1, L2, L3, L4, "list-across.txt", FX, tmp):
                        self.assertNotIn(path.lower(), captured)


# B: the layout run of the known answers of spec sections 10.1 to 10.9. Rows left out:
# - soft zw nbsp lig emdash endash nbhyph decomp lrm fold bom: characters the ASCII-only
#   generator cannot carry;
# - badutf8: not UTF-8;
# - nocontrol: a line longer than the page;
# - hyphff1 hyphff2: form feeds, which are page breaks in a PDF (covered by A7);
# - the source files and strip.txt: stripping never applies to a PDF (10.4);
# - the file-name cases (10.7);
# - the option and list cases with no extraction (10.5, and 10.6's list-format runs).
LAYOUT_ROWS = (
    [(stem, L1) for stem in "plain case wrap hyph hyphcrlf hyphcr hyphsp clean compound "
                            "note two substr early short".split()]
    + [(stem, L2) for stem in "trim word word2 canary clean".split()]
    + [(stem, L3) for stem in "hyphkeep hyphkeepcrlf nokeep clean".split()]
)

# The one row whose PDF run differs from its text fixture: default mode removes the
# line-end hyphen and the line break, so the length is 2 less than the fixture's 1196.
PDF_EXCEPTIONS = {
    ("nokeep", L3): "OK    nokeep.pdf: 0 of 1 entries (control found; 1194 chars)\n",
}


def fixture_lines(stem):
    with open(fx(stem + ".txt"), "rb") as handle:
        pieces = LINE_BREAK.split(handle.read().decode("utf-8"))
    if pieces and pieces[-1] == "":
        pieces.pop()
    return pieces


class LayoutKnownAnswersCase(GatedCase):
    def test_b_layout_text_and_pdf_give_the_known_answers(self):
        self.need_pdftotext()
        make_fixtures = load_make_fixtures()
        self.assertEqual(len(LAYOUT_ROWS), 23)
        used = set()
        for stem, listing in LAYOUT_ROWS:
            with tempfile.TemporaryDirectory() as tmp:
                pdf = os.path.join(tmp, stem + ".pdf")
                with open(pdf, "wb") as handle:
                    handle.write(make_fixtures.one_page_pdf(fixture_lines(stem)))
                args = ["--list", fx(listing)] + CTRL
                code, out, err = run_cli(args + [stem + ".txt"])
                with self.subTest(stem=stem, listing=listing, leg="layout"):
                    with open(os.path.join(tmp, stem + ".txt"), "w",
                              encoding="utf-8", newline="") as handle:
                        handle.write(pdf_text.pdf_text(pdf, layout=True))
                    self.assertEqual(run_cli(args + [stem + ".txt"], cwd=tmp),
                                     (code, out, err))
                with self.subTest(stem=stem, listing=listing, leg="pdf"):
                    want = (code, out.replace(stem + ".txt", stem + ".pdf"), err)
                    if (stem, listing) in PDF_EXCEPTIONS:
                        used.add((stem, listing))
                        exception = (0, PDF_EXCEPTIONS[(stem, listing)], "")
                        self.assertNotEqual(want, exception)
                        want = exception
                    self.assertEqual(run_cli(args + [stem + ".pdf"], cwd=tmp), want)
        self.assertEqual(used, set(PDF_EXCEPTIONS))


def printf(text):
    """A shell printf line that writes text's UTF-8 bytes, non-printing ones as octal."""
    out = []
    for byte in text.encode("utf-8"):
        char = chr(byte)
        if 0x20 <= byte < 0x7F and char not in "'\\%":
            out.append(char)
        else:
            out.append("\\%03o" % byte)
    return "printf '" + "".join(out) + "'"


def page(block, pad=PAD):
    return "".join(line + "\n" for line in [pad] * 12 + list(block) + [pad] * 12)


NOTHING = page(["nothing listed"])
FOUND = page(["a turnkey synergy here"])


class StandInCase(unittest.TestCase):
    """C: a stand-in pdftotext that answers the default read and the layout read apart."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = os.path.join(self._tmp.name, "work")
        self.bin = os.path.join(self._tmp.name, "bin")
        for folder in (self.work, self.bin):
            os.mkdir(folder)
        with open(os.path.join(self.work, "x.pdf"), "wb") as handle:
            handle.write(b"not really a pdf\n")

    def stand_in(self, body):
        path = os.path.join(self.bin, "pdftotext")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\n" + body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IRUSR)

    def run_with(self, default, layout):
        """default and layout are each a text to print or an int exit status."""
        def action(answer):
            return "exit %d" % answer if isinstance(answer, int) else printf(answer)

        self.stand_in('case " $* " in\n*" -layout "*) %s;;\n*) %s;;\nesac\n'
                      % (action(layout), action(default)))
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        return run_cli(["--list", fx(L1)] + CTRL + ["x.pdf"], cwd=self.work,
                       env_extra={"PATH": path})

    def assertOk(self, result):
        code, out, err = result
        self.assertEqual((code, err), (0, ""))
        self.assertRegex(out, r"\AOK    x\.pdf: 0 of 5 entries \(control found; "
                              r"[0-9]+ chars\)\n\Z")

    def test_c1_a_failed_layout_read_is_dead(self):
        self.assertEqual(self.run_with(NOTHING, 1), (2, "DEAD  x.pdf: pdftotext failed\n", ""))

    def test_c2_a_failed_default_read_is_dead(self):
        self.assertEqual(self.run_with(1, FOUND), (2, "DEAD  x.pdf: pdftotext failed\n", ""))

    def test_c3_found_only_in_the_layout_text(self):
        self.assertEqual(self.run_with(NOTHING, page(["a turnkey syn-", "ergy plan"])),
                         (1, fail_one("x.pdf", 13), ""))

    def test_c4_found_only_in_the_default_text(self):
        self.assertEqual(self.run_with(FOUND, NOTHING), (1, fail_one("x.pdf", 13), ""))

    def test_c5_the_default_line_wins(self):
        layout = "".join(line + "\n" for line in
                         [PAD] * 4 + ["a turnkey synergy here"] + [PAD] * 20)
        self.assertEqual(self.run_with(FOUND, layout), (1, fail_one("x.pdf", 13), ""))

    def test_c6_the_count_is_the_larger(self):
        layout = page(["a turnkey synergy and a turnkey synergy"])
        self.assertEqual(self.run_with(FOUND, layout), (1, fail_one("x.pdf", 13, 2), ""))

    def test_c6b_the_default_count_can_be_the_larger(self):
        default = page(["a turnkey synergy and a turnkey synergy"])
        self.assertEqual(self.run_with(default, FOUND), (1, fail_one("x.pdf", 13, 2), ""))

    def test_c7_the_length_is_the_default_texts(self):
        same = self.run_with(NOTHING, NOTHING)
        longer = self.run_with(NOTHING, NOTHING + "".join(PAD + "\n" for _ in range(10)))
        self.assertOk(same)
        self.assertEqual(longer, same)

    def test_c8_the_control_is_the_default_texts(self):
        default = page(["nothing listed"], pad="Another firm shipped a reporting tool for teams.")
        self.assertEqual(self.run_with(default, NOTHING),
                         (2, "DEAD  x.pdf: control not found\n", ""))

    def test_c9_a_line_end_soft_hyphen_in_the_layout_text_is_a_hyphen(self):
        for end in ("", "  ", "\t "):
            with self.subTest(end=end):
                layout = page(["a turnkey syn" + SOFT_HYPHEN + end, "ergy plan"])
                self.assertEqual(self.run_with(NOTHING, layout),
                                 (1, fail_one("x.pdf", 13), ""))

    def test_c10_a_soft_hyphen_not_after_a_word_character_is_removed(self):
        self.assertOk(self.run_with(NOTHING, page(["a turnkey syn " + SOFT_HYPHEN,
                                                   "ergy plan"])))

    def test_c10b_a_soft_hyphen_not_after_a_word_character_is_not_a_hyphen(self):
        listing = os.path.join(self.work, "list-spaced.txt")
        with open(listing, "w", encoding="utf-8") as handle:
            handle.write("syn - ergy\n")
        layout = page(["a turnkey syn " + SOFT_HYPHEN, "ergy plan"])
        self.stand_in('case " $* " in\n*" -layout "*) %s;;\n*) %s;;\nesac\n'
                      % (printf(layout), printf(NOTHING)))
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        code, out, err = run_cli(["--list", listing] + CTRL + ["x.pdf"], cwd=self.work,
                                 env_extra={"PATH": path})
        self.assertEqual((code, err), (0, ""))
        self.assertRegex(out, r"\AOK    x\.pdf: 0 of 1 entries \(control found; "
                              r"[0-9]+ chars\)\n\Z")

    def test_c11_a_soft_hyphen_in_the_default_text_is_not_converted(self):
        self.assertOk(self.run_with(page(["a turnkey syn" + SOFT_HYPHEN, "ergy plan"]),
                                    NOTHING))

    def test_c12_the_two_calls(self):
        log = os.path.join(self._tmp.name, "calls.txt")
        self.assertNotIn("'", log)
        self.stand_in("for arg in \"$@\"; do printf '%%s\\n' \"$arg\" >> '%s'; done\n%s\n"
                      % (log, printf(NOTHING)))
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        self.assertOk(run_cli(["--list", fx(L1)] + CTRL + ["x.pdf"], cwd=self.work,
                              env_extra={"PATH": path}))
        with open(log, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "x.pdf\n-\nx.pdf\n-\n-layout\n")

    def test_c13_the_layout_read_runs_for_pdf_in_any_case(self):
        os.remove(os.path.join(self.work, "x.pdf"))
        with open(os.path.join(self.work, "X.PDF"), "wb") as handle:
            handle.write(b"not really a pdf\n")
        layout = page(["a turnkey syn-", "ergy plan"])
        self.stand_in('case " $* " in\n*" -layout "*) %s;;\n*) %s;;\nesac\n'
                      % (printf(layout), printf(NOTHING)))
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        self.assertEqual(run_cli(["--list", fx(L1)] + CTRL + ["X.PDF"], cwd=self.work,
                                 env_extra={"PATH": path}),
                         (1, fail_one("X.PDF", 13), ""))

    def test_c14_the_layout_read_passes_a_leading_dash_path_safely(self):
        with open(os.path.join(self.work, "-x.pdf"), "wb") as handle:
            handle.write(b"not really a pdf\n")
        self.stand_in('case "$1" in -*) exit 9;; esac\n'
                      'case " $* " in\n*" -layout "*) %s;;\n*) %s;;\nesac\n'
                      % (printf(FOUND), printf(NOTHING)))
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        self.assertEqual(run_cli(["--list", fx(L1)] + CTRL + ["--", "-x.pdf"],
                                 cwd=self.work, env_extra={"PATH": path}),
                         (1, fail_one("-x.pdf", 13), ""))

    def test_c15_a_layout_line_that_is_only_a_soft_hyphen(self):
        self.assertOk(self.run_with(NOTHING, page([SOFT_HYPHEN])))

    def test_c16_a_digit_or_underscore_before_a_line_end_soft_hyphen(self):
        listing = os.path.join(self.work, "list-digit.txt")
        with open(listing, "w", encoding="utf-8") as handle:
            handle.write("abc1-def\nab_-cd\n")
        layout = page(["x abc1" + SOFT_HYPHEN, "def y", "x ab_" + SOFT_HYPHEN, "cd y"])
        self.stand_in('case " $* " in\n*" -layout "*) %s;;\n*) %s;;\nesac\n'
                      % (printf(layout), printf(NOTHING)))
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        self.assertEqual(run_cli(["--list", listing] + CTRL + ["x.pdf"], cwd=self.work,
                                 env_extra={"PATH": path}),
                         (1, "FAIL  x.pdf: 2 entries\nx.pdf:13: entry #1 (1 x)\n"
                             "x.pdf:15: entry #2 (1 x)\n", ""))

    def test_c17_punctuation_before_a_line_end_soft_hyphen(self):
        listing = os.path.join(self.work, "list-dot.txt")
        with open(listing, "w", encoding="utf-8") as handle:
            handle.write("a.- b\n")
        layout = page(["x a." + SOFT_HYPHEN, "b y"])
        self.stand_in('case " $* " in\n*" -layout "*) %s;;\n*) %s;;\nesac\n'
                      % (printf(layout), printf(NOTHING)))
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        code, out, err = run_cli(["--list", listing] + CTRL + ["x.pdf"], cwd=self.work,
                                 env_extra={"PATH": path})
        self.assertEqual((code, err), (0, ""))
        self.assertRegex(out, r"\AOK    x\.pdf: 0 of 1 entries \(control found; "
                              r"[0-9]+ chars\)\n\Z")

    def test_c18_strip_comments_never_applies_to_the_layout_text(self):
        layout = page(["// turnkey synergy here"])
        self.stand_in('case " $* " in\n*" -layout "*) %s;;\n*) %s;;\nesac\n'
                      % (printf(layout), printf(NOTHING)))
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        self.assertEqual(run_cli(["--list", fx(L1)] + CTRL + ["--strip-comments", "x.pdf"],
                                 cwd=self.work, env_extra={"PATH": path}),
                         (1, fail_one("x.pdf", 13), ""))

    def test_c19_the_soft_hyphen_rule_splits_on_crlf_and_lone_cr(self):
        text = page(["a turnkey syn" + SOFT_HYPHEN, "ergy plan"])
        for name, newline in (("crlf", "\r\n"), ("cr", "\r")):
            with self.subTest(newline=name):
                layout = printf(text.replace("\n", newline)).replace("\\015", "\\r")
                self.stand_in('case " $* " in\n*" -layout "*) %s;;\n*) %s;;\nesac\n'
                              % (layout, printf(NOTHING)))
                path = self.bin + os.pathsep + os.environ.get("PATH", "")
                self.assertEqual(run_cli(["--list", fx(L1)] + CTRL + ["x.pdf"],
                                         cwd=self.work, env_extra={"PATH": path}),
                                 (1, fail_one("x.pdf", 13), ""))

    def test_c20_a_mixed_case_pdf_name(self):
        os.remove(os.path.join(self.work, "x.pdf"))
        with open(os.path.join(self.work, "doc.PdF"), "wb") as handle:
            handle.write(b"not really a pdf\n")
        layout = page(["a turnkey syn-", "ergy plan"])
        self.stand_in('case " $* " in\n*" -layout "*) %s;;\n*) %s;;\nesac\n'
                      % (printf(layout), printf(NOTHING)))
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        self.assertEqual(run_cli(["--list", fx(L1)] + CTRL + ["doc.PdF"], cwd=self.work,
                                 env_extra={"PATH": path}),
                         (1, fail_one("doc.PdF", 13), ""))

    def test_c21_the_layout_reads_own_not_found(self):
        # PATH holds only the stand-in's folder, so the stand-in uses builtins and
        # absolute paths; once it has removed itself, no pdftotext can be found.
        self.stand_in('case " $* " in\n*" -layout "*) exit 1;;\n'
                      '*) %s; /bin/rm -f -- "$0";;\nesac\n' % printf(NOTHING))
        stand_in = os.path.join(self.bin, "pdftotext")
        self.assertEqual(run_cli(["--list", fx(L1)] + CTRL + ["x.pdf"], cwd=self.work,
                                 env_extra={"PATH": self.bin}),
                         (2, "DEAD  x.pdf: pdftotext not found\n", ""))
        self.assertFalse(os.path.exists(stand_in))

    def test_c22_the_layout_texts_joined_form_counts(self):
        listing = os.path.join(self.work, "list-joined.txt")
        with open(listing, "w", encoding="utf-8") as handle:
            handle.write("syn- ergy\n")
        layout = page(["a turnkey syn-", "ergy plan"])
        self.stand_in('case " $* " in\n*" -layout "*) %s;;\n*) %s;;\nesac\n'
                      % (printf(layout), printf(NOTHING)))
        path = self.bin + os.pathsep + os.environ.get("PATH", "")
        self.assertEqual(run_cli(["--list", listing] + CTRL + ["x.pdf"], cwd=self.work,
                                 env_extra={"PATH": path}),
                         (1, fail_one("x.pdf", 13), ""))


class FixturePresenceCase(unittest.TestCase):
    def test_the_layout_fixtures_exist(self):
        for name in (L4, "twocol.pdf", "softhyph.pdf", "pagewrap.pdf", "page3wrap.pdf"):
            self.assertTrue(os.path.isfile(fx(name)), name)


if __name__ == "__main__":
    unittest.main()
