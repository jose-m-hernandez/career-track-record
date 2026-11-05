"""Tests for ``track-record claims``, the claim gate. All data here is invented.

Every list, sentence and control below is made up (Example Corp., the Example importer).
Files and lists are written into a temporary folder at run time; no fixture file is used.
PDF cases put a small stand-in ``pdftotext`` first on PATH. Invisible characters, hyphens,
dashes and curly quotes are written as escapes, never raw.
"""

import os
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

import career_track_record.claims as claims  # noqa: E402
from career_track_record import barred, tone  # noqa: E402

SYSTEM_PATH = "/usr/bin:/bin"
LIST_NAME = "the-list-9-18.tsv"

# List L1 of spec section 9 (tab-separated; invented).
L1 = (
    "# invented list\n"
    "approved\tLed a team of six engineers at Example Corp.\tnotes/offer-letter.txt\n"
    "approved\tShipped the Example importer in 2021.\n"
    "approved\tJoined Example Corp. in 2019.\tnotes/start.txt\tinvented note\n"
    "approved\tBuilt an end-to-end import pipeline.\n"
    "proposed\tCut build times by forty percent.\tnotes/draft.txt\n"
    "refused\tIncreased revenue tenfold.\n"
)

HELP = (
    "usage: track-record claims --list FILE --control TEXT [--control TEXT]...\n"
    "    [--stale-check] [--check-sources] FILE...\n"
    "\n"
    "Fail on any sentence your claims list has not approved.\n"
    "\n"
    "  --list FILE      the claims list (required)\n"
    "  --control TEXT   a string each file must hold (repeatable, any one counts)\n"
    "  --stale-check    also report approved entries no file uses\n"
    "  --check-sources  also check each quote against the source file it cites\n"
    "  -h, --help       show this summary and exit\n"
    "\n"
    "exit: 0 every sentence approved, 1 a sentence not approved, "
    "2 a DEAD file or cannot run;\n"
    "    with --check-sources, also 1 a quote not found, 2 a source that cannot be read\n"
)

SIX = "Led a team of six engineers at Example Corp."
SHIPPED = "Shipped the Example importer in 2021."


def ok(label, count):
    return "OK    %s: %d sentences, all approved (control found)\n" % (label, count)


def fail(label, bad, total):
    return "FAIL  %s: %d of %d sentences not approved\n" % (label, bad, total)


def finding(label, line, kind, sentence):
    return "%s:%d: %s: %s\n" % (label, line, kind, sentence)


def stand_in(directory, body):
    path = os.path.join(directory, "pdftotext")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IRUSR)


class ClaimsCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = os.path.join(self._tmp.name, "work")
        self.bin = os.path.join(self._tmp.name, "bin")
        os.mkdir(self.dir)
        os.mkdir(self.bin)
        self.write(LIST_NAME, L1)

    def write(self, name, data):
        mode = "wb" if isinstance(data, bytes) else "w"
        kwargs = {} if mode == "wb" else {"encoding": "utf-8", "newline": ""}
        with open(os.path.join(self.dir, name), mode, **kwargs) as handle:
            handle.write(data)

    def claims(self, args, path=SYSTEM_PATH, stdout=None):
        env = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1", PATH=path)
        env.pop("BARRED_STRINGS_PATH", None)
        with open(os.devnull, "rb") as devnull:
            proc = subprocess.run(
                [sys.executable, "-m", "career_track_record", "claims"] + list(args),
                cwd=self.dir, env=env, stdin=devnull,
                stdout=subprocess.PIPE if stdout is None else stdout,
                stderr=subprocess.PIPE)
        out = proc.stdout.decode("utf-8") if proc.stdout is not None else None
        return proc.returncode, out, proc.stderr.decode("utf-8")

    def gate(self, text, control="example", list_name=LIST_NAME, extra=(), name="f.txt"):
        """Write text as a file, run the gate on it with one control; (code, out, err)."""
        self.write(name, text)
        args = ["--list", list_name, "--control", control] + list(extra) + [name]
        return self.claims(args)

    def with_list(self, list_text):
        self.write("other-list.tsv", list_text)
        return "other-list.tsv"

    def expect(self, got, out, code=0, err=""):
        self.assertEqual(got, (code, out, err))


# ---------------------------------------------------------------- the known answers

# Each row: (input text, control, extra arguments, expected stdout, expected exit code).
CASES = {
    1: (SIX + " " + SHIPPED, "example", [], ok("f.txt", 2), 0),
    2: ("led a team of six  engineers\nat EXAMPLE corp", "example", [],
        ok("f.txt", 1), 0),
    3: ("Led a team of seven engineers at Example Corp.", "example", [],
        fail("f.txt", 1, 1)
        + finding("f.txt", 1, "unlisted", "Led a team of seven engineers at Example Corp."), 1),
    4: ("Led a team of six engineers at Example Corp and Example Two.", "example", [],
        fail("f.txt", 1, 1)
        + finding("f.txt", 1, "unlisted",
                  "Led a team of six engineers at Example Corp and Example Two."), 1),
    5: ("Example work. Cut build times by forty percent.", "example", [],
        fail("f.txt", 2, 2)
        + finding("f.txt", 1, "unlisted", "Example work.")
        + finding("f.txt", 1, "proposed, entry #5", "Cut build times by forty percent."), 1),
    6: ("Example: Increased revenue tenfold.\n\nIncreased revenue tenfold.\n", "example", [],
        fail("f.txt", 2, 2)
        + finding("f.txt", 1, "unlisted", "Example: Increased revenue tenfold.")
        + finding("f.txt", 3, "refused, entry #6", "Increased revenue tenfold."), 1),
    7: ("- Led a team of six engineers at Example Corp\n"
        "- Shipped the Example importer in 2021\n", "example", [], ok("f.txt", 2), 0),
    8: ("- Shipped the Example importer in 2021\n- Mentored interns\n", "example", [],
        fail("f.txt", 1, 2) + finding("f.txt", 2, "unlisted", "Mentored interns"), 1),
    9: ("Joined Example Corp. in 2019.", "example", [], ok("f.txt", 2), 0),
    10: ("Built an end\u2011to\u2011end import pipeline.", "pipeline", [], ok("f.txt", 1), 0),
    11: ("Built an end\u2013to\u2013end import pipeline.", "pipeline", [],
         fail("f.txt", 1, 1)
         + finding("f.txt", 1, "unlisted", "Built an end\u2013to\u2013end import pipeline."), 1),
    12: ("Built an end-\nto-end import pipeline.", "pipeline", [], ok("f.txt", 1), 0),
    13: (SIX, "example", ["--stale-check"],
         ok("f.txt", 1) + "stale entry #2\nstale entry #3\nstale entry #4\n", 1),
}


class KnownAnswers(ClaimsCase):
    def known(self, number):
        text, control, extra, out, code = CASES[number]
        self.expect(self.gate(text, control=control, extra=extra), out, code)

    def test_9_01_two_approved_sentences_pass(self):
        self.known(1)

    def test_9_02_case_spacing_and_a_missing_full_stop_do_not_matter(self):
        self.known(2)

    def test_9_03_a_changed_word_is_a_new_sentence(self):
        self.known(3)

    def test_9_04_containing_an_entry_is_not_matching_it(self):
        self.known(4)

    def test_9_05_an_unlisted_and_a_proposed_sentence(self):
        self.known(5)

    def test_9_06_an_unlisted_line_and_a_refused_line(self):
        self.known(6)

    def test_9_07_bullets_without_full_stops_pass(self):
        self.known(7)

    def test_9_08_an_unlisted_bullet_fails_on_its_own_line(self):
        self.known(8)

    def test_9_09_a_run_of_two_sentences_is_covered_by_one_entry(self):
        self.known(9)

    def test_9_10_non_breaking_hyphens_fold(self):
        self.known(10)

    def test_9_11_an_en_dash_is_not_a_hyphen(self):
        self.known(11)

    def test_9_12_a_line_end_hyphen_joins(self):
        self.known(12)

    def test_9_13_stale_entries_are_listed_in_order(self):
        self.known(13)

    def test_9_14_control_not_found_is_dead(self):
        self.expect(self.gate(CASES[1][0], control="zebra"),
                    "DEAD  f.txt: control not found\n", 2)

    def test_9_15_only_markers_is_dead_no_checked_sentence(self):
        self.expect(self.gate("- * -\n\n- * -\n", control="-"),
                    "DEAD  f.txt: no checked sentence\n", 2)

    def test_9_16_two_entries_with_the_same_sentence_cannot_run(self):
        name = self.with_list(
            L1 + "approved\tled a team of six engineers at example corp\n")
        self.expect(self.gate(SIX, list_name=name), "", 2,
                    "cannot run: entries #1 and #7 are the same sentence\n")

    def test_9_17_an_unknown_status_cannot_run(self):
        name = self.with_list(L1 + "maybe\tExample.\n")
        self.expect(self.gate(SIX, list_name=name), "", 2,
                    "cannot run: unknown status in entry #7\n")

    def test_9_18_no_note_source_or_list_path_reaches_any_output(self):
        for number in range(1, 14):
            with self.subTest(case=number):
                text, control, extra, _out, _code = CASES[number]
                code, out, err = self.gate(text, control=control, extra=extra)
                for secret in ("notes/", "invented note", LIST_NAME):
                    self.assertNotIn(secret, out)
                    self.assertNotIn(secret, err)

    def test_9_19_help_alongside_other_arguments(self):
        for args in (["--help"], ["-h"], ["--list", LIST_NAME, "--help", "f.txt"],
                     ["f.txt", "-h", "--bogus"], ["--help", "--help"]):
            with self.subTest(args=args):
                self.expect(self.claims(args), HELP, 0)

    def test_the_readme_example(self):
        self.write("claims.txt", L1)
        self.write("copy.txt", "Led a team of seven engineers at Example Corp.\n")
        got = self.claims(["--list", "claims.txt", "--control", "example", "copy.txt"])
        self.expect(got, "FAIL  copy.txt: 1 of 1 sentences not approved\n"
                    "copy.txt:1: unlisted: Led a team of seven engineers at Example Corp.\n",
                    1)


# ---------------------------------------------------------------- the build readings

class Readings(ClaimsCase):
    def test_r1_k_counts_sentences_and_a_run_prints_one_finding_line(self):
        name = self.with_list("proposed\tShipped it. Fixed it.\n")
        self.expect(self.gate("Shipped it. Fixed it.", control="it", list_name=name),
                    fail("f.txt", 2, 2) + finding("f.txt", 1, "proposed, entry #1",
                                                  "Shipped it. Fixed it."), 1)
        name = self.with_list("refused\tShipped it. Fixed it.\n")
        self.expect(self.gate("Shipped it. Fixed it. Done it.", control="it", list_name=name),
                    fail("f.txt", 3, 3) + finding("f.txt", 1, "refused, entry #1",
                                                  "Shipped it. Fixed it.")
                    + finding("f.txt", 1, "unlisted", "Done it."), 1)

    def test_r2_a_finding_prints_the_run_as_in_the_file(self):
        self.expect(self.gate("Built an end-\nto-end import pipelines.", control="pipelines"),
                    fail("f.txt", 1, 1) + finding("f.txt", 1, "unlisted",
                                                  "Built an end- to-end import pipelines."), 1)

    def test_r2_a_finding_is_not_folded_and_keeps_its_case_and_curly_quotes(self):
        text = "WE didn\u2019t Ship Example \u201cOne\u201d."
        self.expect(self.gate(text),
                    fail("f.txt", 1, 1) + finding("f.txt", 1, "unlisted", text), 1)

    def test_r3_a_dead_file_suppresses_every_stale_line(self):
        self.write("a.txt", SIX)
        self.write("b.txt", "nothing here\n")
        got = self.claims(["--list", LIST_NAME, "--control", "example", "--stale-check",
                           "a.txt", "b.txt"])
        self.expect(got, ok("a.txt", 1) + "DEAD  b.txt: control not found\n", 2)

    def test_r4_counts_are_literal(self):
        self.expect(self.gate(SIX), ok("f.txt", 1), 0)
        code, out, err = self.gate("Mentored interns at Example Corp.")
        self.assertTrue(out.startswith("FAIL  f.txt: 1 of 1 sentences not approved\n"), out)

    def test_r5_dead_reasons(self):
        self.write("blank.txt", "\n")
        got = self.claims(["--list", LIST_NAME, "--control", "x", "nowhere.txt"])
        self.expect(got, "DEAD  nowhere.txt: cannot read\n", 2)
        self.expect(self.gate("Hello.", control="zebra"),
                    "DEAD  f.txt: control not found\n", 2)
        self.expect(self.gate("", control="\u2013"),
                    "DEAD  f.txt: control not found\n", 2)
        self.expect(self.gate("- - -", control="-"),
                    "DEAD  f.txt: no checked sentence\n", 2)
        self.write("x.pdf", b"not a pdf\n")
        got = self.claims(["--list", LIST_NAME, "--control", "x", "x.pdf"], path=self.bin)
        self.expect(got, "DEAD  x.pdf: pdftotext not found\n", 2)

    def test_r5_a_directory_is_cannot_read(self):
        os.mkdir(os.path.join(self.dir, "folder"))
        got = self.claims(["--list", LIST_NAME, "--control", "x", "folder"])
        self.expect(got, "DEAD  folder: cannot read\n", 2)

    def test_r6_each_cannot_run_reason(self):
        base = ["--list", LIST_NAME, "--control", "example"]
        self.write("f.txt", SIX)
        cases = [
            (["--list", LIST_NAME, "--control", "example"], "no input file"),
            (["--list", LIST_NAME, "f.txt"], "no --control given"),
            (["--list", LIST_NAME, "--control", "", "f.txt"], "no usable --control given"),
            (["--list", LIST_NAME, "--control", "  \t ", "f.txt"], "no usable --control given"),
            (["--list", LIST_NAME, "--control", "\u200b", "f.txt"], "no usable --control given"),
            (["--control", "example", "f.txt"], "no list (give --list)"),
            (base + ["--list", LIST_NAME, "f.txt"], "--list given twice"),
            (["--list", "nowhere.tsv", "--control", "example", "f.txt"],
             "the list file cannot be read"),
            (base + ["--bogus", "f.txt"], "unknown option --bogus"),
            (base + ["f.txt", "--bo\ngus"], "unknown option --bo\\ngus"),
        ]
        for args, reason in cases:
            with self.subTest(reason=reason, args=args):
                self.expect(self.claims(args), "", 2, "cannot run: %s\n" % reason)

    def test_r6_entry_problems(self):
        cases = [
            ("approved\n", "entry #1 has no sentence"),
            ("approved\t\n", "entry #1 has no sentence"),
            ("approved\t.\n", "entry #1 has no sentence"),
            ("approved\tFine.\nrefused\t \u200b ?\"\n", "entry #2 has no sentence"),
            ("\tFine.\n", "unknown status in entry #1"),
            ("approved\tFine.\nmaybe\tFine two.\n", "unknown status in entry #2"),
            ("approved\tFine.\nrefused\tOther.\nproposed\tfine\n",
             "entries #1 and #3 are the same sentence"),
            ("approved\tA.\nrefused\tB.\nproposed\tb\nproposed\ta\n",
             "entries #2 and #3 are the same sentence"),
        ]
        for list_text, reason in cases:
            with self.subTest(reason=reason):
                name = self.with_list(list_text)
                self.expect(self.gate(SIX, list_name=name), "", 2,
                            "cannot run: %s\n" % reason)

    def test_r6_a_list_with_no_entries_is_usable_and_every_sentence_is_unlisted(self):
        name = self.with_list("# only a comment\n\n   \n")
        self.expect(self.gate(SIX, list_name=name),
                    fail("f.txt", 1, 1) + finding("f.txt", 1, "unlisted", SIX), 1)
        self.expect(self.gate(SIX, list_name=name, extra=["--stale-check"]),
                    fail("f.txt", 1, 1) + finding("f.txt", 1, "unlisted", SIX), 1)

    def test_r6_a_list_with_a_byte_order_mark_crlf_and_comments(self):
        name = self.with_list(
            "\ufeff# invented\r\napproved\t" + SIX + "\tnotes/a.txt\r\n\r\n"
            "  \r\n# note\rrefused\tIncreased revenue tenfold.\r")
        self.expect(self.gate(SIX + " Increased revenue tenfold.", list_name=name),
                    fail("f.txt", 1, 2)
                    + finding("f.txt", 1, "refused, entry #2", "Increased revenue tenfold."), 1)

    def test_r6_an_option_that_needs_a_value(self):
        self.write("f.txt", SIX)
        for args in (["--list"], ["--control"], ["--list", "--control", "x", "f.txt"],
                     ["--control", "--stale-check", "f.txt"]):
            with self.subTest(args=args):
                code, out, err = self.claims(args)
                self.assertEqual((code, out), (2, ""))
                self.assertRegex(err, r"\Acannot run: --(list|control) needs a value\n\Z")

    def test_r6_equals_forms(self):
        self.write("f.txt", SIX)
        got = self.claims(["--list=" + LIST_NAME, "--control=example", "f.txt"])
        self.expect(got, ok("f.txt", 1), 0)
        got = self.claims(["--list", LIST_NAME, "--control", "example", "--stale-check=1",
                           "f.txt"])
        self.expect(got, "", 2, "cannot run: unknown option --stale-check=1\n")

    def test_r7_the_line_end_join_comes_before_blocks(self):
        name = self.with_list("approved\tBuilt an end-1. Led the team\n")
        self.expect(self.gate("Built an end-\n1. Led the team.\n", control="team",
                              list_name=name), ok("f.txt", 2), 0)

    def test_r7_a_digit_in_a_marker_is_any_character_that_folds_to_an_ascii_digit(self):
        name = self.with_list("approved\tLed the team\n")
        self.expect(self.gate("\uff12. Led the team.\n", control="team", list_name=name),
                    ok("f.txt", 1), 0)
        self.expect(self.gate("\u0662. Led the team.\n", control="team", list_name=name),
                    fail("f.txt", 1, 2) + finding("f.txt", 1, "unlisted", "\u0662."), 1)

    # Reading 8: section 6's privacy promise makes the list, given as an input, a DEAD file.
    def test_r8_the_list_given_as_an_input_is_dead_and_not_read(self):
        os.symlink(LIST_NAME, os.path.join(self.dir, "link.tsv"))
        for name in (LIST_NAME, "./" + LIST_NAME, "link.tsv"):
            with self.subTest(name=name):
                got = self.claims(["--list", LIST_NAME, "--control", "example", name])
                self.expect(got, "DEAD  file #1: is the list\n", 2)
                for secret in ("notes/", "invented note", LIST_NAME):
                    self.assertNotIn(secret, got[1])
                    self.assertNotIn(secret, got[2])

    # Reading 8: the label is the position among the input files, and no stale line follows.
    def test_r8_the_label_is_the_position_and_no_stale_line_is_printed(self):
        self.write("a.txt", SIX)
        got = self.claims(["--list", LIST_NAME, "--control", "example", "--stale-check",
                           "a.txt", LIST_NAME])
        self.expect(got, ok("a.txt", 1) + "DEAD  file #2: is the list\n", 2)

    # Reading 8: the list is never given to pdftotext, whatever its name.
    def test_r8_a_list_named_like_a_pdf_is_never_given_to_pdftotext(self):
        marker = os.path.join(self._tmp.name, "pdftotext-ran")
        stand_in(self.bin, 'touch "%s"\nexit 1\n' % marker)
        self.write("list.pdf", L1)
        got = self.claims(["--list", "list.pdf", "--control", "example", "list.pdf"],
                          path=self.bin + ":" + SYSTEM_PATH)
        self.expect(got, "DEAD  file #1: is the list\n", 2)
        self.assertFalse(os.path.exists(marker))

    # Reading 8: the same file under another link is the list; a path comparison would miss it.
    def test_r8_a_hardlink_to_the_list_is_the_list(self):
        os.link(os.path.join(self.dir, LIST_NAME), os.path.join(self.dir, "hard.tsv"))
        got = self.claims(["--list", LIST_NAME, "--control", "example", "hard.tsv"])
        self.expect(got, "DEAD  file #1: is the list\n", 2)
        for secret in ("notes/", "invented note", LIST_NAME):
            self.assertNotIn(secret, got[1])
            self.assertNotIn(secret, got[2])

    # Reading 8: <i> is the position among the input files, whatever the files before it print.
    def test_r8_the_label_counts_files_not_output_lines(self):
        self.write("a.txt", "Mentored interns at Example Corp.\nCoached staff at Example Corp.")
        got = self.claims(["--list", LIST_NAME, "--control", "example", "a.txt", LIST_NAME])
        self.expect(got, fail("a.txt", 2, 2)
                    + finding("a.txt", 1, "unlisted", "Mentored interns at Example Corp.")
                    + finding("a.txt", 2, "unlisted", "Coached staff at Example Corp.")
                    + "DEAD  file #2: is the list\n", 2)


# ---------------------------------------------------------------- one change at a time

class Variations(ClaimsCase):
    def test_x1_each_line_marker_starts_a_block(self):
        for marker in ("-", "*", "+", "\u2022", "1.", "12)", "###", "  \t- "):
            with self.subTest(marker=marker):
                text = SHIPPED[:-1] + "\n" + marker + " Mentored interns"
                self.expect(self.gate(text),
                            fail("f.txt", 1, 2) + finding("f.txt", 2, "unlisted",
                                                          "Mentored interns"), 1)
        # The same lines with no marker are one block, and so one unlisted sentence.
        text = SHIPPED[:-1] + "\nMentored interns"
        self.expect(self.gate(text),
                    fail("f.txt", 1, 1) + finding("f.txt", 1, "unlisted",
                                                  "Shipped the Example importer in 2021 "
                                                  "Mentored interns"), 1)

    def test_x1_a_marker_is_not_part_of_the_sentence(self):
        for marker in ("-", "*", "+", "\u2022", "1.", "999)", "######"):
            with self.subTest(marker=marker):
                self.expect(self.gate(marker + "\t" + SHIPPED[:-1]), ok("f.txt", 1), 0)

    def test_x2_seven_hashes_and_hash_without_a_space_are_not_markers(self):
        for marker in ("#######", "#x", "12345)", "1.x", "-x", "**"):
            with self.subTest(marker=marker):
                text = SHIPPED[:-1] + "\n" + marker + " Mentored interns"
                self.expect(self.gate(text),
                            fail("f.txt", 1, 1)
                            + finding("f.txt", 1, "unlisted",
                                      "Shipped the Example importer in 2021 " + marker
                                      + " Mentored interns"), 1)

    def test_x3_a_combining_mark_matches_the_composed_letter(self):
        name = self.with_list("approved\tShipped the caf\u00e9 menu for Example Corp.\n")
        self.expect(self.gate("Shipped the cafe\u0301 menu for Example Corp.", list_name=name),
                    ok("f.txt", 1), 0)
        # The other way round, and with a changed word: the finding prints the file's form.
        name = self.with_list("approved\tShipped the cafe\u0301 menu for Example Corp.\n")
        self.expect(self.gate("Shipped the caf\u00e9 menu for Example Corp.", list_name=name),
                    ok("f.txt", 1), 0)
        self.expect(self.gate("Shipped the cafe\u0301 bar for Example Corp.", list_name=name),
                    fail("f.txt", 1, 1)
                    + finding("f.txt", 1, "unlisted",
                              "Shipped the cafe\u0301 bar for Example Corp."), 1)

    def test_x3_a_combining_mark_after_a_sentence_end_does_not_move_the_line(self):
        text = "Mentored interns.\n\ne\u0301e Mentored again.\n"
        code, out, err = self.gate(text, control="mentored")
        self.assertEqual((code, err), (1, ""))
        self.assertIn("f.txt:3: unlisted: e\u0301e Mentored again.\n", out)

    # Pins spec section 4 "a run is prepared from its whole text": U+1100 U+1161 compose to U+AC00 only when folded together.
    def test_x3_conjoining_jamo_match_the_composed_syllable(self):
        name = self.with_list("approved\t\uac00 Example importer.\n")
        text = "\u1100\u1161 Example importer."
        self.expect(self.gate(text, list_name=name), ok("f.txt", 1), 0)

    # Barred form 3 joins across "one line break, then any whitespace", so the join crosses a blank line; it fails closed.
    def test_a_line_end_join_crosses_a_blank_line(self):
        text = "Led the team-\n\nShipped it."
        self.expect(self.gate(text, control="team"),
                    fail("f.txt", 1, 1)
                    + finding("f.txt", 1, "unlisted", "Led the team- Shipped it."), 1)

    def test_whitespace_around_a_status_is_trimmed_and_the_set_stays_closed(self):
        name = self.with_list(" approved \tShipped the Example importer in 2021.\n")
        self.expect(self.gate(SHIPPED, list_name=name), ok("f.txt", 1), 0)
        name = self.with_list("approve\tShipped the Example importer in 2021.\n")
        self.expect(self.gate(SHIPPED, list_name=name), "", 2,
                    "cannot run: unknown status in entry #1\n")

    # A line marker takes one to three digits, so a four-digit year then a full stop is a sentence (spec section 4).
    def test_a_four_digit_number_is_not_a_line_marker(self):
        self.expect(self.gate("2021. " + SIX),
                    fail("f.txt", 1, 2) + finding("f.txt", 1, "unlisted", "2021."), 1)

    # A lone CR is one line break, as in barred.md, so a line-end hyphen before it joins the word.
    def test_a_lone_cr_before_a_line_end_hyphen_joins_the_word(self):
        self.expect(self.gate("Built an end-to-\rend import pipeline. Example."),
                    fail("f.txt", 1, 2) + finding("f.txt", 2, "unlisted", "Example."), 1)

    # A line holding only a tab is blank, so it ends the block (spec section 4).
    def test_a_tab_only_line_ends_a_block(self):
        self.expect(self.gate("Led a team of six\n\t\nengineers at Example Corp."),
                    fail("f.txt", 2, 2)
                    + finding("f.txt", 1, "unlisted", "Led a team of six")
                    + finding("f.txt", 3, "unlisted", "engineers at Example Corp."), 1)

    # A lone - is a file name, as in barred: not an option and not standard input.
    def test_a_file_named_a_single_hyphen_is_a_file(self):
        self.write("-", SIX)
        self.expect(self.claims(["--list", LIST_NAME, "--control", "example", "-"]),
                    ok("-", 1), 0)

    def test_x4_curly_quotes_and_ligatures_fold(self):
        name = self.with_list(
            "approved\tWe didn't miss Example's goal\n"
            "approved\tCalled it \"Example\" a win\n"
            "approved\tFiled the final report for Example Corp.\n")
        text = ("We didn\u2019t miss Example\u2018s goal. "
                "Called it \u201cExample\u201d a win. "
                "Filed the \ufb01nal report for Example Corp.")
        self.expect(self.gate(text, list_name=name), ok("f.txt", 3), 0)

    def test_x4_a_straight_quote_entry_is_not_a_prefix_match(self):
        name = self.with_list("approved\tWe didn't miss Example's goal\n")
        text = "We didn\u2019t miss Example\u2019s goals."
        self.expect(self.gate(text, list_name=name),
                    fail("f.txt", 1, 1) + finding("f.txt", 1, "unlisted", text), 1)

    def test_x5_a_final_exclamation_and_a_final_question_mark_with_a_quote_are_dropped(self):
        name = self.with_list("approved\tShipped Example\napproved\tDid it ship Example\n")
        self.expect(self.gate("Shipped Example! Did it ship Example?\"", list_name=name),
                    ok("f.txt", 2), 0)
        self.expect(self.gate("Shipped Example!", list_name=name), ok("f.txt", 1), 0)
        self.expect(self.gate("Did it ship Example?)", list_name=name), ok("f.txt", 1), 0)
        self.expect(self.gate("Shipped Example", list_name=name), ok("f.txt", 1), 0)
        # Only one final mark goes: two are a different sentence.
        self.expect(self.gate("Shipped Example!!", list_name=name),
                    fail("f.txt", 1, 1) + finding("f.txt", 1, "unlisted",
                                                  "Shipped Example!!"), 1)

    def test_x6_a_sentence_with_no_letter_or_digit_is_not_counted(self):
        name = self.with_list("approved\tExample work\napproved\tShipped Example\n")
        self.expect(self.gate("Example work. -- !! Shipped Example.", list_name=name),
                    ok("f.txt", 2), 0)
        self.expect(self.gate("Example work.\n\n?\n\n(*)\n", list_name=name), ok("f.txt", 1), 0)

    def test_x7_crlf_and_lone_cr_files_give_the_right_line_numbers(self):
        data = (SIX + "\r\nMentored interns.\r\n" + SHIPPED + "\rLast bit.\r\n"
                "\r\n  \r- Fifth block\r\n").encode("utf-8")
        self.write("f.txt", data)
        got = self.claims(["--list", LIST_NAME, "--control", "example", "f.txt"])
        self.expect(got, fail("f.txt", 3, 5)
                    + finding("f.txt", 2, "unlisted", "Mentored interns.")
                    + finding("f.txt", 4, "unlisted", "Last bit.")
                    + finding("f.txt", 7, "unlisted", "Fifth block"), 1)

    def test_x7_a_run_over_a_crlf_break_is_covered_and_the_next_line_counted(self):
        self.write("f.txt", b"Joined Example Corp.\r\nin 2019. Mentored.\r\n")
        got = self.claims(["--list", LIST_NAME, "--control", "example", "f.txt"])
        self.expect(got, fail("f.txt", 1, 3) + finding("f.txt", 2, "unlisted", "Mentored."), 1)

    def test_x8_an_invalid_utf8_byte_gives_an_unlisted_sentence_not_dead(self):
        self.write("f.txt", SIX[:-1].encode("utf-8") + b".\xff\n")
        got = self.claims(["--list", LIST_NAME, "--control", "example", "f.txt"])
        self.expect(got, fail("f.txt", 1, 1)
                    + finding("f.txt", 1, "unlisted", SIX + "\ufffd"), 1)

    def test_x9_a_list_that_is_not_utf8_cannot_run(self):
        self.write("bad.tsv", b"approved\tLed the team\xff.\n")
        self.write("f.txt", SIX)
        got = self.claims(["--list", "bad.tsv", "--control", "example", "f.txt"])
        self.expect(got, "", 2, "cannot run: the list is not valid UTF-8\n")

    def test_x10_two_controls_and_only_the_second_is_present(self):
        self.write("f.txt", SIX)
        got = self.claims(["--list", LIST_NAME, "--control", "zebra", "--control", "example",
                           "f.txt"])
        self.expect(got, ok("f.txt", 1), 0)
        got = self.claims(["--list", LIST_NAME, "--control", "zebra", "--control", "yak",
                           "f.txt"])
        self.expect(got, "DEAD  f.txt: control not found\n", 2)

    def test_x10_an_empty_control_beside_a_usable_one_is_ignored(self):
        self.write("f.txt", SIX)
        got = self.claims(["--list", LIST_NAME, "--control", "", "--control", "example", "f.txt"])
        self.expect(got, ok("f.txt", 1), 0)

    def test_x10_the_control_is_prepared_like_text(self):
        self.write("f.txt", "Led a team of six engineers at Example Corp.\n")
        for control in ("EXAMPLE  CORP", "six\nengineers", "Corp."):
            with self.subTest(control=control):
                got = self.claims(["--list", LIST_NAME, "--control", control, "f.txt"])
                self.expect(got, ok("f.txt", 1), 0)

    def test_x11_stale_check_twice_equals_once(self):
        once = self.gate(SIX, extra=["--stale-check"])
        twice = self.gate(SIX, extra=["--stale-check", "--stale-check"])
        self.assertEqual(once, twice)
        self.assertEqual(once[0], 1)

    def test_x11_stale_check_counts_covered_runs_in_every_file_and_ignores_other_statuses(self):
        self.write("a.txt", SIX)
        self.write("b.txt", "Mentored interns at Example Corp.\n"
                   + SHIPPED + " Joined Example Corp. in 2019. Cut build times by forty percent.")
        got = self.claims(["--list", LIST_NAME, "--control", "example", "--stale-check",
                           "a.txt", "b.txt"])
        self.expect(got, ok("a.txt", 1)
                    + fail("b.txt", 2, 5)
                    + finding("b.txt", 1, "unlisted", "Mentored interns at Example Corp.")
                    + finding("b.txt", 2, "proposed, entry #5",
                              "Cut build times by forty percent.")
                    + "stale entry #4\n", 1)

    def test_x11_stale_check_with_everything_used_exits_0(self):
        self.write("f.txt", " ".join([SIX, SHIPPED, "Joined Example Corp. in 2019.",
                                      "Built an end-to-end import pipeline."]))
        got = self.claims(["--list", LIST_NAME, "--control", "example", "--stale-check", "f.txt"])
        self.expect(got, ok("f.txt", 5), 0)

    def test_x11_without_the_flag_nothing_is_said_about_staleness(self):
        self.expect(self.gate(SIX), ok("f.txt", 1), 0)

    def test_x12_after_two_hyphens_help_is_a_file_name(self):
        self.write("--help", SIX)
        got = self.claims(["--list", LIST_NAME, "--control", "example", "--", "--help"])
        self.expect(got, ok("--help", 1), 0)
        self.write("--list", SIX)
        got = self.claims(["--list", LIST_NAME, "--control", "example", "--", "--list", "-h"])
        self.expect(got, ok("--list", 1) + "DEAD  -h: cannot read\n", 2)

    def test_x13_help_wins_over_a_bad_option_and_over_a_missing_list(self):
        for args in (["--bogus", "--help"], ["--help", "--bogus"], ["-h"],
                     ["--control", "x", "-h"], ["--list", "--help"], ["--list", "-h", "--list"],
                     ["--list", "a", "--list", "b", "-h"], ["--stale-check=1", "-h"]):
            with self.subTest(args=args):
                self.expect(self.claims(args), HELP, 0)

    def test_x13_help_reads_nothing(self):
        self.expect(self.claims(["--list", "nowhere.tsv", "nowhere.txt", "--help"]), HELP, 0)

    def test_x13_a_file_named_like_an_option_value_is_not_help(self):
        self.write("f.txt", SIX)
        got = self.claims(["--control", "example", "--list", LIST_NAME, "f.txt"])
        self.expect(got, ok("f.txt", 1), 0)

    def test_x14_closed_standard_output_exits_2_with_one_line_and_no_traceback(self):
        self.write("f.txt", SIX)
        for args in (["--list", LIST_NAME, "--control", "example", "f.txt"], ["--help"]):
            with self.subTest(args=args):
                r, w = os.pipe()
                os.close(r)
                try:
                    code, _out, err = self.claims(args, stdout=w)
                finally:
                    os.close(w)
                self.assertEqual((code, err), (2, "cannot run: cannot write output\n"))

    def test_x15_a_path_with_a_line_feed_prints_escaped(self):
        name = "a\nb\tc.txt"
        self.expect(self.gate(SIX, name=name), ok("a\\nb\\tc.txt", 1), 0)
        self.expect(self.gate("Mentored interns at Example Corp.", name=name),
                    fail("a\\nb\\tc.txt", 1, 1)
                    + finding("a\\nb\\tc.txt", 1, "unlisted",
                              "Mentored interns at Example Corp."), 1)
        got = self.claims(["--list", LIST_NAME, "--control", "x", "no\nwhere.txt"])
        self.expect(got, "DEAD  no\\nwhere.txt: cannot read\n", 2)

    def test_x15_a_finding_escapes_what_it_prints(self):
        text = "Mentored \u200b\u202einterns \\ at Example Corp.\u001b"
        code, out, err = self.gate(text)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("unlisted: Mentored \\u200b\\u202einterns \\\\ at Example Corp.\\x1b\n",
                      out)

    def test_x16_a_pdf_through_a_stand_in_pdftotext(self):
        self.write("x.pdf", b"not really a pdf\n")
        stand_in(self.bin, "printf '%s' 'Led a team of six engineers at Example Corp.'\n")
        path = self.bin + os.pathsep + SYSTEM_PATH
        args = ["--list", LIST_NAME, "--control", "example", "x.pdf"]
        self.expect(self.claims(args, path=path), ok("x.pdf", 1), 0)
        stand_in(self.bin, "printf '%s' 'Led a team of six engineers at Example Corp.\n"
                 "Mentored interns at Example Corp.\n'\n")
        self.expect(self.claims(args, path=path),
                    fail("x.pdf", 1, 2)
                    + finding("x.pdf", 2, "unlisted", "Mentored interns at Example Corp."), 1)

    def test_x16_a_pdf_name_in_any_case_is_read_as_a_pdf(self):
        self.write("X.PDF", b"not really a pdf\n")
        stand_in(self.bin, "printf '%s' 'Led a team of six engineers at Example Corp.'\n")
        path = self.bin + os.pathsep + SYSTEM_PATH
        got = self.claims(["--list", LIST_NAME, "--control", "example", "X.PDF"], path=path)
        self.expect(got, ok("X.PDF", 1), 0)

    def test_x16_a_missing_or_failing_pdftotext_is_barreds_dead_reason(self):
        self.write("x.pdf", b"not really a pdf\n")
        args = ["--list", LIST_NAME, "--control", "example", "x.pdf"]
        self.expect(self.claims(args, path=self.bin), "DEAD  x.pdf: pdftotext not found\n", 2)
        stand_in(self.bin, "exit 3\n")
        self.expect(self.claims(args, path=self.bin + os.pathsep + SYSTEM_PATH),
                    "DEAD  x.pdf: pdftotext failed\n", 2)
        got = self.claims(["--list", LIST_NAME, "--control", "example", "missing.pdf"],
                          path=self.bin + os.pathsep + SYSTEM_PATH)
        self.expect(got, "DEAD  missing.pdf: cannot read\n", 2)

    def test_x17_an_approved_and_a_refused_entry_with_one_sentence_cannot_run(self):
        name = self.with_list("approved\tShipped it.\nrefused\tshipped IT\n")
        self.expect(self.gate(SIX, list_name=name), "", 2,
                    "cannot run: entries #1 and #2 are the same sentence\n")

    def test_x18_statuses_in_any_case_are_read(self):
        name = self.with_list("APPROVED\tShipped it.\nRefused\tFixed it.\nPrOpOsEd\tDone it.\n")
        self.expect(self.gate("Shipped it. Fixed it. Done it.", control="it", list_name=name),
                    fail("f.txt", 2, 3) + finding("f.txt", 1, "refused, entry #2", "Fixed it.")
                    + finding("f.txt", 1, "proposed, entry #3", "Done it."), 1)

    def test_x19_a_source_and_a_note_never_appear_in_any_output(self):
        secrets = ("SRC-ALPHA", "NOTE-BETA", "SRC-GAMMA", "NOTE-DELTA", "SRC-EPSILON", LIST_NAME)
        name = self.with_list(
            "approved\tShipped it.\tSRC-ALPHA\tNOTE-BETA\n"
            "proposed\tFixed it.\tSRC-GAMMA\n"
            "refused\tDone it.\tSRC-EPSILON\tNOTE-DELTA\n"
            "approved\tNever used in any file.\tSRC-ALPHA\n")
        self.write("a.txt", "Shipped it. Fixed it. Done it. Other it.")
        self.write("b.txt", "nothing\n")
        runs = [
            ["--list", name, "--control", "it", "a.txt"],
            ["--list", name, "--control", "it", "--stale-check", "a.txt"],
            ["--list", name, "--control", "it", "a.txt", "b.txt", "missing.txt"],
            ["--list", name, "--control", "it", "--stale-check", "a.txt", "b.txt"],
            ["--list", name, "--control", "", "a.txt"],
            ["--list", name, "--control", "it"],
            ["--list", name, "--bogus", "a.txt"],
            ["--list", name, "--list", name, "--control", "it", "a.txt"],
        ]
        for args in runs:
            with self.subTest(args=args):
                code, out, err = self.claims(args)
                for secret in secrets + (name,):
                    self.assertNotIn(secret, out)
                    self.assertNotIn(secret, err)
        # A list that cannot be used says nothing of the entry's text either.
        bad = self.with_list("approved\tSecret claim one SRC-ALPHA\nbogus\tSecret claim two\n")
        code, out, err = self.claims(["--list", bad, "--control", "it", "a.txt"])
        self.assertEqual((code, out, err), (2, "", "cannot run: unknown status in entry #2\n"))
        bad = self.with_list("approved\tSecret claim\tSRC-ALPHA\nrefused\tsecret CLAIM\tNOTE-BETA\n")
        code, out, err = self.claims(["--list", bad, "--control", "it", "a.txt"])
        self.assertEqual((code, out, err),
                         (2, "", "cannot run: entries #1 and #2 are the same sentence\n"))

    def test_x19_the_sentence_of_an_entry_that_covered_nothing_is_not_printed(self):
        code, out, err = self.gate(SIX, extra=["--stale-check"])
        for text in ("Shipped the Example importer", "Joined Example Corp", "pipeline",
                     "Cut build times"):
            self.assertNotIn(text, out)
            self.assertNotIn(text, err)

    def test_x20_the_reused_private_names_exist(self):
        for name in ("fold", "_keep_hyphen", "printed_path", "_read_text", "_Dead", "_is_the_list",
                     "Result"):
            with self.subTest(module="barred", name=name):
                self.assertTrue(hasattr(barred, name))
        for name in ("_sentence_ends", "_CLOSERS", "_line_starts", "_blank_lines"):
            with self.subTest(module="tone", name=name):
                self.assertTrue(hasattr(tone, name))
        self.assertIs(claims.fold, barred.fold)
        self.assertIs(claims._keep_hyphen, barred._keep_hyphen)
        self.assertIs(claims.printed_path, barred.printed_path)
        self.assertIs(claims._read_text, barred._read_text)
        self.assertIs(claims._Dead, barred._Dead)
        self.assertIs(claims._is_the_list, barred._is_the_list)
        self.assertIs(claims._sentence_ends, tone._sentence_ends)
        self.assertIs(claims._CLOSERS, tone._CLOSERS)

    def test_a_file_read_twice_in_one_run_is_checked_twice(self):
        self.write("f.txt", SIX)
        got = self.claims(["--list", LIST_NAME, "--control", "example", "f.txt", "f.txt"])
        self.expect(got, ok("f.txt", 1) + ok("f.txt", 1), 0)

    def test_status_lines_follow_argument_order_and_the_highest_exit_wins(self):
        self.write("a.txt", "Mentored interns at Example Corp.")
        self.write("b.txt", SIX)
        got = self.claims(["--list", LIST_NAME, "--control", "example", "b.txt", "a.txt"])
        self.expect(got, ok("b.txt", 1) + fail("a.txt", 1, 1)
                    + finding("a.txt", 1, "unlisted", "Mentored interns at Example Corp."), 1)
        got = self.claims(["--list", LIST_NAME, "--control", "example", "a.txt", "gone.txt"])
        self.assertEqual(got[0], 2)

    def test_the_longest_run_wins_and_the_search_goes_on_after_it(self):
        name = self.with_list("approved\tJoined Example Corp.\napproved\tJoined Example Corp. in 2019\n"
                              "refused\tin 2019 Mentored\n")
        self.expect(self.gate("Joined Example Corp. in 2019. Led them.", list_name=name),
                    fail("f.txt", 1, 3) + finding("f.txt", 1, "unlisted", "Led them."), 1)

    def test_a_run_never_crosses_a_block(self):
        self.expect(self.gate("Joined Example Corp.\n\nin 2019.\n"),
                    fail("f.txt", 2, 2) + finding("f.txt", 1, "unlisted", "Joined Example Corp.")
                    + finding("f.txt", 3, "unlisted", "in 2019."), 1)
        self.expect(self.gate("- Joined Example Corp.\n- in 2019.\n"),
                    fail("f.txt", 2, 2) + finding("f.txt", 1, "unlisted", "Joined Example Corp.")
                    + finding("f.txt", 2, "unlisted", "in 2019."), 1)

    def test_a_sentence_end_needs_whitespace_or_the_end_after_it(self):
        self.expect(self.gate("Shipped the Example importer in 2021.Led more."),
                    fail("f.txt", 1, 1)
                    + finding("f.txt", 1, "unlisted",
                              "Shipped the Example importer in 2021.Led more."), 1)

    def test_a_closing_quote_after_a_sentence_end_stays_with_its_sentence(self):
        name = self.with_list("approved\tShe said \"shipped Example.\"\napproved\tThen left\n")
        self.expect(self.gate("She said \"shipped Example.\" Then left.", list_name=name),
                    ok("f.txt", 2), 0)

    def test_an_entry_in_a_different_script_case_matches_by_full_case_folding(self):
        name = self.with_list("approved\tStra\u00dfe at Example\n")
        self.expect(self.gate("STRASSE at EXAMPLE", list_name=name), ok("f.txt", 1), 0)

    def test_invisible_characters_do_not_change_the_result(self):
        text = "Led a te\u200bam of six engi\u00adneers at Example\u2060 Corp."
        self.expect(self.gate(text), ok("f.txt", 1), 0)
        text = "Mentored\u200b interns at Example Corp."
        self.expect(self.gate(text),
                    fail("f.txt", 1, 1) + finding("f.txt", 1, "unlisted",
                                                  "Mentored\\u200b interns at Example Corp."), 1)

    def test_a_hyphen_kept_at_a_line_end_fails_closed_for_a_split_word(self):
        self.expect(self.gate("Led a team of six engi-\nneers at Example Corp."),
                    fail("f.txt", 1, 1)
                    + finding("f.txt", 1, "unlisted",
                              "Led a team of six engi- neers at Example Corp."), 1)
        name = self.with_list("approved\tLed a team of six engi-neers at Example Corp.\n")
        self.expect(self.gate("Led a team of six engi-\nneers at Example Corp.",
                              list_name=name), ok("f.txt", 1), 0)

    def test_a_long_block_is_checked_quickly(self):
        text = " ".join("Sentence number %d at Example Corp." % n for n in range(3000))
        code, out, err = self.gate(text)
        self.assertEqual((code, err), (1, ""))
        self.assertTrue(out.startswith("FAIL  f.txt: 3000 of 3000 sentences"), out[:80])

    def test_the_summary_in_the_top_level_help(self):
        env = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run([sys.executable, "-m", "career_track_record", "--help"],
                              cwd=self.dir, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertIn("    claims    fail on sentences your claims list hasn't approved",
                      proc.stdout.decode("utf-8").splitlines())


# ---------------------------------------------------------------- the known limits

class KnownLimits(ClaimsCase):
    # Known limit: Markdown inline markup is ordinary text (spec section 4).
    def test_inline_markup_is_text(self):
        name = self.with_list("approved\t**Led** the team\n")
        self.expect(self.gate("**Led** the team.", control="team", list_name=name),
                    ok("f.txt", 1), 0)
        self.expect(self.gate("Led the team.", control="team", list_name=name),
                    fail("f.txt", 1, 1) + finding("f.txt", 1, "unlisted", "Led the team."), 1)
        name = self.with_list("approved\tled the team\n")
        self.expect(self.gate("**Led** the team.", control="team", list_name=name),
                    fail("f.txt", 1, 1) + finding("f.txt", 1, "unlisted", "**Led** the team."),
                    1)

    # Known limit: table rows and block quotes are ordinary text, not line markers (spec section 4).
    def test_table_rows_and_block_quotes_are_ordinary_text(self):
        name = self.with_list("approved\tLed the team\n")
        self.expect(self.gate("| Led the team | 2019 |\n> Led the team.\n", control="team",
                              list_name=name),
                    fail("f.txt", 1, 1)
                    + finding("f.txt", 1, "unlisted", "| Led the team | 2019 | > Led the team."),
                    1)

    # Known limit: the sentence rule has no abbreviation list; an entry written with the
    # split in it always matches (spec section 4).
    def test_the_sentence_rule_has_no_abbreviation_list(self):
        name = self.with_list("approved\tJoined Example Corp.\n")
        self.expect(self.gate("Joined Example Corp. in 2019.", list_name=name),
                    fail("f.txt", 1, 2) + finding("f.txt", 1, "unlisted", "in 2019."), 1)
        # Today's behaviour: the first sentence of the split is covered, the rest is not.
        name = self.with_list("approved\tJoined Example Corp. in 2019.\n")
        self.expect(self.gate("Joined Example Corp. in 2019.", list_name=name),
                    ok("f.txt", 2), 0)

    # Known limit: a PDF line wrap inside a page cannot be told from a line break (barred spec
    # section 3.2); a word that layout split with a hyphen fails until it is fixed or approved.
    def test_a_hyphen_split_by_layout_fails_until_approved(self):
        self.expect(self.gate("Led a team of six engi-\nneers at Example Corp."),
                    fail("f.txt", 1, 1)
                    + finding("f.txt", 1, "unlisted",
                              "Led a team of six engi- neers at Example Corp."), 1)

    # Known limit (reading 8): the list is known by the file itself, not by its content.
    def test_a_renamed_copy_of_the_list_is_checked_like_any_file(self):
        self.write("copy.tsv", L1)
        code, out, err = self.claims(["--list", LIST_NAME, "--control", "example", "copy.tsv"])
        self.assertEqual(code, 1)
        self.assertEqual(err, "")
        self.assertTrue(out.startswith("FAIL  copy.tsv: 7 of 7 sentences not approved\n"))
        self.assertIn("notes/start.txt", out)
        self.assertIn("invented note", out)


if __name__ == "__main__":
    unittest.main()
