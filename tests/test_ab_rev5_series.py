"""Tests for revision 5 of the Reader A/B spec, the series file (cases SR1 to SR40 of the series
spec). All data here is invented.

The series file of the spec is ``F/labs.series.tsv`` and the plan sits in ``F/r1/`` with
``series: ../labs.series.tsv``; here ``F`` is a fresh temporary folder and ``Round`` is a plan
folder in it. The clock of the series code is the ``now`` parameter of ``ab.freeze``, ``ab.run``
and ``ab.score``: each case runs at 2026-11-16T10:00:00Z unless it says otherwise.

Where a case says what a wrong rule would give, the comment beside the assertion names that
wrong answer: it is the mutant the assertion must turn red.

Each case id has one test method named test_srN_...; a case that needed more than one method
has the others as test_srNb_..., test_srNc_... .
"""

import datetime
import errno
import fcntl
import hashlib
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from career_track_record import ab, record_check, series  # noqa: E402
from tests.test_ab import FIXTURES, FX, PREFER_GLANCE, SIX, Setup, default_values, items  # noqa: E402
from tests.test_ab import sha256_of  # noqa: E402
from tests.test_ab_rev4 import READERS  # noqa: E402
from tests.test_ab_rev5_tie import FOUR, FOUR_TWO, T1_AA, aa  # noqa: E402

UTC = datetime.timezone.utc
CLOCK = datetime.datetime(2026, 11, 16, 10, 0, 0, tzinfo=UTC)
HEADER = "draft\tparent\tfile_sha256\tposting_sha256\tround\tplan_sha256\tresult\tdate\tnote"
GLANCE_CLEARLY = items(PREFER_GLANCE, strength="clearly")
BASE_SHA = sha256_of(os.path.join(FX, "base.txt"))
NO_FCNTL = "series needs a POSIX file lock (fcntl), which this platform does not have"
FOLDER_MESSAGE = ("the folder name holds a character a series row cannot carry (; @ or a "
                  "control character)")
SECOND_ROUND = ("%s: the series already holds this draft (line %d); a second round of a draft "
                "is a follow-up plan, with extends, amends or replicate-of")
TWELVE = ("SUPPORTED if skills-top preferred in 12 of 12; REFUTED if base preferred in 8 or "
          "more; otherwise INCONCLUSIVE")
AT_LEAST_TWO_BASE = "SUPPORTED if base preferred in 2 or more; otherwise INCONCLUSIVE"
SIX_OF_SIX_BASE = "SUPPORTED if base preferred in 6 of 6; otherwise INCONCLUSIVE"
SIX_OF_SIX = "SUPPORTED if skills-top preferred in 6 of 6; otherwise INCONCLUSIVE"


def hand_row(draft, parent="", file_sha=BASE_SHA, posting="", round_="", plan="", result="",
             date="2026-11-15", note=""):
    return "\t".join([draft, parent, file_sha, posting, round_, plan, result, date, note])


BASE_ROW = hand_row("base", note="the one you start from")


def starting(lines, prefix):
    return [x for x in lines if x.startswith(prefix)]


class Round(Setup):
    """A plan folder ``name`` in the folder that holds the series file: the four fixtures and a
    plan written from the default values, with the series key and the fake reader that prefers
    "At a glance"."""

    def __init__(self, case, root, name="r1", **overrides):
        self.case = case
        self.folder = os.path.join(root, name)
        os.makedirs(self.folder, exist_ok=True)
        for fixture in FIXTURES:
            shutil.copyfile(os.path.join(FX, fixture), os.path.join(self.folder, fixture))
        self.plan_path = os.path.join(self.folder, "plan.txt")
        self.values = default_values()
        self.values.update(readers=list(READERS), hypotheses=[SIX], fake_reader=GLANCE_CLEARLY,
                           series="../labs.series.tsv")
        self.now = CLOCK
        self.change(**overrides)

    def freeze(self):
        return ab.freeze(self.plan_path, now=self.now)

    def run(self, live=False):
        return ab.run(self.plan_path, live=live, now=self.now)

    def score(self):
        return ab.score(self.plan_path, now=self.now)

    def sha(self, name):
        return sha256_of(self.path(name))

    def plan_sha(self):
        return self.sha("plan.txt")

    def refused(self):
        """Freeze, which must exit 2 with no freeze file: the problem lines."""
        result = self.freeze()
        self.case.assertEqual((result.exit_code, result.ran), (2, False), result.text)
        self.case.assertFalse(self.exists("plan.txt.freeze"))
        return result.error.splitlines()


class SeriesCase(unittest.TestCase):
    """A folder F holding ``labs.series.tsv`` with its header and the hand row ``base``."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.series = os.path.join(self.root, "labs.series.tsv")
        self.write_series([BASE_ROW])

    def write_series(self, rows, header=HEADER):
        with open(self.series, "w", encoding="utf-8", newline="") as handle:
            handle.write("".join(line + "\n" for line in [header] + list(rows)))

    def write_raw(self, data):
        with open(self.series, "wb") as handle:
            handle.write(data)

    def raw(self):
        with open(self.series, "rb") as handle:
            return handle.read()

    def text(self):
        return self.raw().decode("utf-8")

    def lines(self):
        return self.text().split("\n")[:-1]

    def cells(self, line):
        return self.lines()[line - 1].split("\t")

    def lock_path(self):
        return self.series + ".lock"

    def round(self, name="r1", **overrides):
        return Round(self, self.root, name, **overrides)

    def done(self, name="r1", **overrides):
        """A frozen and run round: (round, run result)."""
        r = self.round(name, **overrides)
        frozen = r.freeze()
        self.assertEqual(frozen.exit_code, 0, frozen.error)
        return r, r.run()

    def admitted(self, name="r1", **overrides):
        r, result = self.done(name, **overrides)
        self.assertEqual(result.exit_code, 0, result.error)
        return r, result

    def folder_files(self):
        return sorted(os.listdir(self.root))

    def expected_row(self, r, draft="skills-top", parent="base", verdicts="h1 SUPPORTED",
                     round_=None, date="2026-11-16", note="", file_name=None):
        return "\t".join([draft, parent, r.sha(file_name or draft + ".txt"), r.sha("posting.txt"),
                          round_ or os.path.basename(r.folder), r.plan_sha(),
                          "%s@%s: %s" % (round_ or os.path.basename(r.folder), r.plan_sha(),
                                         verdicts),
                          date, note])

    def record(self, declaration="labs.series.tsv"):
        """``record`` with the declaration of section 7 of the spec, on the series file."""
        with open(os.path.join(self.root, "record.txt"), "w", encoding="utf-8") as handle:
            handle.write("tables:\n  series | %s | tsv | draft\nrequired:\n  series | "
                         "file_sha256\n  series | date\ndates:\n  series | date\ncorrections:\n"
                         "  series | parent | date\n" % declaration)
        return record_check.run(os.path.join(self.root, "record.txt"))


class AdmitCase(SeriesCase):
    def test_sr1_an_admitting_round_adds_one_row(self):
        before = self.lines()
        r, result = self.done()
        self.assertEqual((result.exit_code, result.error), (0, ""))
        after = self.lines()
        self.assertEqual(after[:2], before)
        self.assertEqual(len(after), 3)
        self.assertEqual(after[2], self.expected_row(r))
        self.assertTrue(after[2].endswith("\t"))
        self.assertEqual(self.cells(3)[8], "")
        self.assertEqual(result.text.splitlines()[-1],
                         "series: added row skills-top to ../labs.series.tsv")
        # the line is in what the command prints, and never in the result file
        self.assertEqual([x for x in r.result_lines() if x.startswith("series:")], [])
        self.assertTrue(r.read("result-1.txt").endswith("exit status: 0\n"))
        found = self.record()
        self.assertEqual((found.exit_code, found.text), (0, found.text), found.text)

    def test_sr2_the_note_is_the_plans_series_note(self):
        r, result = self.admitted(series_note="shorter summary")
        self.assertEqual(self.cells(3)[8], "shorter summary")
        self.assertEqual(self.lines()[2], self.expected_row(r, note="shorter summary"))

    def test_sr3_scoring_again_changes_nothing(self):
        r, result = self.admitted()
        after_run = self.raw()
        again = r.score()
        self.assertEqual((again.exit_code, again.error), (0, ""))
        self.assertTrue(r.exists("result-2.txt"))
        self.assertEqual(self.raw(), after_run)
        self.assertEqual(again.text.splitlines()[-1],
                         "series: no change: plan %s is already recorded in row skills-top "
                         "(line 3)" % r.plan_sha()[:12])

    def test_sr4_a_tie_is_written_as_the_word(self):
        # T1's A/A and comparison reads with aa-band on: the verdict is TIE.
        r, result = self.done(fake_reader=FOUR_TWO + T1_AA, hypotheses=[FOUR], aa_band="on")
        self.assertEqual(result.exit_code, 0, result.error)
        self.assertIn("hypothesis h1 verdict: TIE [not blind: 0 reads left out]",
                      r.result_lines())
        self.assertEqual(len(starting(r.result_lines(), "TIE: h1: ")), 1)
        self.assertEqual(self.cells(3)[6], "r1@%s: h1 TIE" % r.plan_sha())
        # the cell never holds the TIE sentence: a cell with it would give the wrong word
        self.assertNotIn("not shown to differ", self.text())

    def test_sr4b_two_hypotheses_are_written_in_plan_order(self):
        r, result = self.done(hypotheses=[SIX_OF_SIX, SIX_OF_SIX_BASE])
        self.assertEqual(result.exit_code, 0, result.error)
        self.assertEqual(self.cells(3)[6], "r1@%s: h1 SUPPORTED, h2 INCONCLUSIVE" % r.plan_sha())

    def test_sr4c_a_tie_beside_a_supported(self):
        # Band 1 (one A/A pair picks a side); h1 names base, whose margin is -2, h2 names
        # skills-top, whose margin is 2.
        r, result = self.done(fake_reader=FOUR_TWO + aa([1], [2]),
                              hypotheses=[AT_LEAST_TWO_BASE, FOUR], aa_band="on")
        self.assertEqual(result.exit_code, 0, result.error)
        self.assertEqual(self.cells(3)[6], "r1@%s: h1 TIE, h2 SUPPORTED" % r.plan_sha())

    def test_sr5_a_cut_run_is_a_round(self):
        readers = ["reader-1 | fake | family m1 | cost 5", "reader-2 | fake | family m2 | cost 5"]
        r, result = self.done(readers=readers, spend_ceiling="20")
        self.assertEqual(result.exit_code, 1, result.error)
        self.assertIn("cut: ran", r.read("result-1.txt"))
        self.assertEqual(self.cells(3)[6], "r1@%s: h1 INCONCLUSIVE" % r.plan_sha())
        self.assertEqual(result.text.splitlines()[-1],
                         "series: added row skills-top to ../labs.series.tsv")

    def test_sr5b_a_failed_read_is_a_round(self):
        r, result = self.done(fake_reader=GLANCE_CLEARLY + ["omit PREFER | read 1"])
        self.assertEqual(result.exit_code, 1, result.error)
        self.assertEqual(self.cells(3)[6], "r1@%s: h1 INCONCLUSIVE" % r.plan_sha())

    def test_sr5c_a_dead_run_is_a_round(self):
        r, result = self.done(fake_reader=["omit PREFER", "aa | omit PREFER"])
        self.assertEqual(result.exit_code, 1, result.error)
        self.assertIn("DEAD: 0 of 24 planned reads are valid", r.result_lines())
        self.assertEqual(self.cells(3)[6], "r1@%s: h1 INCONCLUSIVE" % r.plan_sha())

    def test_sr5d_a_result_with_exit_status_2_changes_nothing(self):
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        real = ab.fake_reply
        calls = []

        def interrupted(read, rules, text_a, text_b):
            calls.append(read.id)
            if len(calls) == 3:
                raise KeyboardInterrupt()
            return real(read, rules, text_a, text_b)

        with mock.patch.object(ab, "fake_reply", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                r.run()
        before = self.raw()
        result = r.score()
        # a stopped run scores what it has, with exit status 2, and that result adds no row
        self.assertEqual((result.exit_code, result.ran), (2, True))
        self.assertIn("exit status: 2", r.result_lines())
        self.assertEqual(self.raw(), before)
        self.assertEqual(starting(result.text.splitlines(), "series:"), [])
        self.assertFalse(os.path.exists(self.lock_path()))


class FreezeRefusalCase(SeriesCase):
    def test_sr6_the_parent_must_be_a_row(self):
        self.write_series([])
        lines = self.round().refused()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("base:"), lines)
        self.write_series([hand_row("base2")])
        lines = self.round("r2").refused()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("base:"), lines)

    def test_sr7_a_second_round_that_is_not_a_follow_up_is_refused_at_freeze(self):
        self.write_series([BASE_ROW, hand_row("skills-top", parent="base")])
        r = self.round()
        self.assertEqual(r.refused(), [SECOND_ROUND % ("skills-top", 3)])

    def test_sr7b_a_row_of_another_plan_stops_run_before_any_read(self):
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        other = "b" * 64
        self.write_series([BASE_ROW, hand_row(
            "skills-top", parent="base", posting="c" * 64, round_="r0", plan=other,
            result="r0@%s: h1 SUPPORTED" % other)])
        before = self.raw()
        result = r.run()
        self.assertEqual((result.exit_code, result.ran), (2, False))
        self.assertEqual(result.error.splitlines(), [SECOND_ROUND % ("skills-top", 3)])
        for name in (ab.READS_DIR, ab.KEY_FILE, ab.RUN_LOG, "result-1.txt"):
            self.assertFalse(r.exists(name), name)
        self.assertEqual(self.raw(), before)

    def test_sr7c_the_same_at_score_of_a_finished_folder(self):
        r, result = self.admitted()
        other = "b" * 64
        self.write_series([BASE_ROW, hand_row(
            "skills-top", parent="base", posting="c" * 64, round_="r0", plan=other,
            result="r0@%s: h1 SUPPORTED" % other)])
        before = self.raw()
        again = r.score()
        self.assertEqual((again.exit_code, again.ran), (2, False))
        self.assertEqual(again.error.splitlines(), [SECOND_ROUND % ("skills-top", 3)])
        self.assertFalse(r.exists("result-2.txt"))
        self.assertEqual(self.raw(), before)

    def test_sr8_a_parent_file_edited_after_its_row(self):
        r = self.round()
        r.edit("base.txt", lambda text: text + "one more line\n")
        lines = r.refused()
        self.assertEqual(lines, [
            "base: the plan's file is not the file the series records (computed %s from the "
            "file's bytes; the row holds %s)" % (r.sha("base.txt"), BASE_SHA)])
        # a mutant that compared nothing would let this freeze

    def pdf_round(self, name, extension, row_sha):
        """A round whose parent is a PDF; pdftotext is stood in for by a function that gives
        one fixed text, so the plan's file bytes are never what the readers saw."""
        versions = ["base | base.%s | drafted-by user" % extension,
                    "skills-top | skills-top.txt | drafted-by user",
                    "skills-top-short | skills-top-short.txt | drafted-by user"]
        self.write_series([hand_row("base", file_sha=row_sha)])
        r = self.round(name, versions=versions)
        r.write("base." + extension, "not really a pdf\n")
        return r

    def test_sr8b_a_pdf_parent_is_hashed_as_its_extracted_text(self):
        text = "Extracted base text\n"
        text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        for number, extension in enumerate(("pdf", "PDF")):
            with self.subTest(extension=extension):
                # distinct folder names: the file system may fold case
                r = self.pdf_round("p%d" % number, extension, text_sha)
                with mock.patch("career_track_record.pdf_text.pdf_text", return_value=text):
                    self.assertEqual(r.freeze().exit_code, 0)

    def test_sr8c_a_row_holding_the_hash_of_the_pdf_bytes_is_refused(self):
        text = "Extracted base text\n"
        text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        for number, extension in enumerate(("pdf", "PDF")):
            with self.subTest(extension=extension):
                r = self.pdf_round("q%d" % number, extension, "0" * 64)
                bytes_sha = r.sha("base." + extension)
                self.write_series([hand_row("base", file_sha=bytes_sha)])
                with mock.patch("career_track_record.pdf_text.pdf_text", return_value=text):
                    lines = r.refused()
                # the hash of the PDF's bytes would pass if the extension test were
                # case-sensitive for BASE.PDF, or if PDFs were hashed as bytes
                self.assertEqual(lines, [
                    "base: the plan's file is not the file the series records (computed %s from "
                    "the pdftotext text of the file; the row holds %s)" % (text_sha, bytes_sha)])

    def test_sr9_the_plan_folder_is_strictly_below_the_series_folder(self):
        own = self.round("", series="labs.series.tsv")
        lines = own.refused()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("not strictly below", lines[0])
        # a plan folder outside the series file's folder: its round would need ..
        os.makedirs(os.path.join(self.root, "deep"))
        outside = os.path.join(self.root, "deep", "labs.series.tsv")
        shutil.copyfile(self.series, outside)
        out = self.round("r2", series="../deep/labs.series.tsv")
        lines = out.refused()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("not strictly below", lines[0])

    def test_sr9b_two_levels_below_is_accepted_and_the_round_is_the_path(self):
        r = self.round("sub/r1", series="../../labs.series.tsv")
        self.assertEqual(r.freeze().exit_code, 0)
        result = r.run()
        self.assertEqual(result.exit_code, 0, result.error)
        self.assertEqual(self.cells(3)[4], "sub/r1")
        self.assertEqual(self.cells(3)[6], "sub/r1@%s: h1 SUPPORTED" % r.plan_sha())
        self.assertEqual(self.record().exit_code, 0)

    def test_sr10_series_files_that_break_check_1(self):
        base = BASE_ROW
        plain = hand_row("base")
        shown = "../labs.series.tsv"
        h = "a" * 64
        h2 = "b" * 64
        h3 = "c" * 64

        def third(**kw):
            fields = dict(draft="skills-top", parent="base", file_sha=h, posting="", round_="",
                          plan="", result="", date="2026-11-16", note="")
            fields.update(kw)
            return hand_row(**fields)

        def filled(**kw):
            fields = dict(posting=h3, round_="r0", plan=h2, result="r0@%s: h1 SUPPORTED" % h2)
            fields.update(kw)
            return third(**fields)

        file_cases = [
            ("a wrong header", ("rows", [base], "draft\tparent"), ":1:", ""),
            ("no final line break", ("raw", (HEADER + "\n" + base).encode("utf-8")), ":2:",
             "line break"),
            ("a CR", ("raw", (HEADER + "\r\n" + base + "\n").encode("utf-8")), ":1:", "carriage"),
            ("eight fields", ("rows", [plain[:-1]]), ":2:", "fields 8"),
            ("ten fields", ("rows", [plain + "\t"]), ":2:", "fields 10"),
            ("a byte-order mark", ("raw", b"\xef\xbb\xbf" + (HEADER + "\n" + base + "\n").encode(
                "utf-8")), ":1:", "byte-order mark"),
            ("invalid UTF-8", ("raw", (HEADER + "\n").encode("utf-8") + b"base\t\xff\n"), ":2:",
             "UTF-8"),
        ]
        column_cases = [
            ("a draft with a space", [third(draft="a b")], "draft"),
            ("a draft with an underscore", [third(draft="a_b")], "draft"),
            ("a draft with a dot", [third(draft="a.b")], "draft"),
            ("a repeated draft", [third(draft="base")], "draft"),
            ("a parent that is no earlier row", [third(parent="nowhere")], "parent"),
            ("a file_sha256 of 63 digits", [third(file_sha=h[:63])], "file_sha256"),
            ("a file_sha256 of 65 digits", [third(file_sha=h + "a")], "file_sha256"),
            ("an upper-case digit", [third(file_sha="A" + h[1:])], "file_sha256"),
            ("an empty file_sha256", [third(file_sha="")], "file_sha256"),
            ("a posting_sha256 with a non-hex digit", [third(posting="g" * 64)],
             "posting_sha256"),
            ("a plan_sha256 with a non-hex digit", [third(plan="g" * 64)], "plan_sha256"),
            ("a round filled and plan_sha256 empty", [filled(plan="")], "plan_sha256"),
            ("a plan_sha256 filled and round empty", [third(plan=h2)], "plan_sha256"),
            ("a round filled and posting_sha256 empty", [filled(posting="")], "posting_sha256"),
            ("a round empty and posting_sha256 filled", [third(posting=h3)], "posting_sha256"),
            ("a round of /abs", [filled(round_="/abs")], "round"),
            ("a round of a//b", [filled(round_="a//b")], "round"),
            ("a round of a/", [filled(round_="a/")], "round"),
            ("a round of ./a", [filled(round_="./a")], "round"),
            ("a round of a/../b", [filled(round_="a/../b")], "round"),
            ("a filled round with an empty result", [filled(result="")], "result"),
            ("a result digest that differs from the row's",
             [filled(result="r0@%s: h1 SUPPORTED" % h3)], "result"),
            ("a first item with a kind", [filled(result="r0@%s extends: h1 SUPPORTED" % h2)],
             "result"),
            ("a kind of other", [filled(result="r0@%s other: h1 SUPPORTED" % h2)], "result"),
            ("a verdict of h1 MAYBE", [filled(result="r0@%s: h1 MAYBE" % h2)], "result"),
            ("a verdict of h1SUPPORTED", [filled(result="r0@%s: h1SUPPORTED" % h2)], "result"),
            ("a verdict of h1 TIED", [filled(result="r0@%s: h1 TIED" % h2)], "result"),
            ("a verdict of h1 tie", [filled(result="r0@%s: h1 tie" % h2)], "result"),
            ("the old TIE sentence", [filled(result="r0@%s: TIE: h1: the margin of 2 pairs is "
                                            "inside this run's A/A band" % h2)], "result"),
            ("a date of 2026-02-30", [third(date="2026-02-30")], "date"),
        ]
        number = 0
        for label, spec, where, word in file_cases:
            number += 1
            with self.subTest(case=label):
                if spec[0] == "rows":
                    self.write_series(spec[1], *spec[2:])
                else:
                    self.write_raw(spec[1])
                r = self.round("f%d" % number)
                lines = r.refused()
                self.assertEqual(len(lines), 1, lines)
                self.assertTrue(lines[0].startswith(shown + where), lines)
                self.assertIn(word, lines[0])
        for label, rows, column in column_cases:
            number += 1
            with self.subTest(case=label):
                self.write_series([base] + rows)
                r = self.round("f%d" % number)
                lines = r.refused()
                self.assertEqual(len(lines), 1, lines)
                self.assertTrue(lines[0].startswith("%s:3: %s: " % (shown, column)), lines)
        with self.subTest(case="a note holding a tab"):
            self.write_series([base, third(note="a\tb")])
            lines = self.round("fnote").refused()
            self.assertTrue(lines[0].startswith("%s:3: fields 10" % shown), lines)
        with self.subTest(case="a missing file"):
            os.remove(self.series)
            lines = self.round("fmissing").refused()
            self.assertTrue(lines[0].startswith(shown + ":"), lines)
            self.assertFalse(os.path.exists(self.series))
        with self.subTest(case="a symbolic link"):
            real = os.path.join(self.root, "real.tsv")
            with open(real, "w", encoding="utf-8") as handle:
                handle.write(HEADER + "\n" + base + "\n")
            os.symlink(real, self.series)
            lines = self.round("flink").refused()
            self.assertTrue(lines[0].startswith(shown + ":"), lines)
            self.assertIn("symbolic link", lines[0])

    def test_sr11_a_plan_with_series_has_exactly_one_comparison(self):
        r = self.round(comparisons=["base vs skills-top", "base vs skills-top-short"],
                       hypotheses=["base vs skills-top | " + SIX_OF_SIX], fake_reader=None)
        lines = r.refused()
        self.assertIn("plan line %d: a plan with series has exactly one comparison"
                      % r.line_of("series: "), lines)

    def test_sr11b_a_plan_without_series_leaves_the_series_file_alone(self):
        before, stat_before = self.raw(), os.stat(self.series)
        r = self.round(series=None)
        self.assertEqual(r.freeze().exit_code, 0)
        self.assertEqual(r.run().exit_code, 0)
        self.assertEqual(r.score().exit_code, 0)
        self.assertEqual(self.raw(), before)
        self.assertEqual(os.stat(self.series).st_mtime_ns, stat_before.st_mtime_ns)
        self.assertEqual(self.folder_files(), ["labs.series.tsv", "r1"])

    def test_sr15b_a_series_value_with_a_nul_byte_is_refused_at_freeze(self):
        # No traceback: the same refusal as a series file that is not there. A plan with the
        # value cannot reach run or score: the changed plan fails the freeze's hash first.
        r = self.round(series="x\x00y")
        result = r.freeze()
        self.assertEqual((result.exit_code, result.ran), (2, False), result.text)
        self.assertFalse(r.exists("plan.txt.freeze"))
        self.assertIn("x\\x00y: no such file; a person makes the series file by hand",
                      result.error.splitlines()[-1])
        ok = self.round("r2")
        self.assertEqual(ok.freeze().exit_code, 0)
        ok.change(series="x\x00y")
        for step in (ok.run, ok.score):
            after = step()
            self.assertEqual(after.exit_code, 2, after.text)
            self.assertIn("changed since the freeze: plan.txt", after.error)

    def test_sr15_a_series_note_with_a_tab_is_refused_at_freeze(self):
        r = self.round(series_note="shorter\tsummary")
        self.assertEqual(r.refused(), ["plan line %d: series-note holds a tab"
                                       % r.line_of("series-note")])

    def test_sr41_a_plan_with_series_and_no_hypothesis_is_refused_at_freeze(self):
        r = self.round(hypotheses=[])
        self.assertIn("hypotheses:\nfake-reader:", r.read("plan.txt"))
        self.assertEqual(r.refused(), ["the plan names a series file but no hypothesis; add a "
                                       "hypothesis, or remove the series line"])
        # nothing was read: no reads folder, and no file in the folder beyond the fixtures
        self.assertFalse(r.exists(ab.READS_DIR))
        self.assertFalse(r.exists("result-1.txt"))

    def test_sr42_a_series_note_without_series_is_refused_at_freeze(self):
        r = self.round(series=None, series_note="a note")
        self.assertEqual(r.refused(), [
            "plan line %d: series-note is set but the plan names no series file; add a series "
            "line, or remove series-note" % r.line_of("series-note")])
        # nothing was read: no reads folder, and no file in the folder beyond the fixtures
        self.assertFalse(r.exists(ab.READS_DIR))
        self.assertFalse(r.exists("result-1.txt"))

    def test_sr18_the_versions_swapped_relative_to_the_series(self):
        r = self.round(comparisons=["skills-top vs base"])
        lines = r.refused()
        # skills-top is no row; base, now the draft, is one already, which is refused too
        self.assertTrue(lines[0].startswith("skills-top:"), lines)

    def test_sr14_a_parent_dated_after_today_stops_freeze_run_and_score(self):
        self.write_series([hand_row("base", date="2999-01-01")])
        r = self.round()
        lines = r.refused()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("base", lines[0])
        self.assertIn("2999-01-01", lines[0])
        # run: frozen when the clock is later, then run when it is not
        r.now = datetime.datetime(2999, 6, 1, tzinfo=UTC)
        self.assertEqual(r.freeze().exit_code, 0)
        r.now = CLOCK
        before = self.raw()
        result = r.run()
        self.assertEqual((result.exit_code, result.ran), (2, False))
        self.assertIn("2999-01-01", result.error)
        self.assertFalse(r.exists(ab.READS_DIR))
        self.assertFalse(r.exists("result-1.txt"))
        self.assertEqual(self.raw(), before)

    def test_sr14b_score_of_a_finished_folder_with_a_parent_dated_after_today(self):
        r, result = self.admitted()
        self.write_series([hand_row("base", date="2999-01-01")])
        before = self.raw()
        again = r.score()
        self.assertEqual((again.exit_code, again.ran), (2, False))
        self.assertIn("2999-01-01", again.error)
        self.assertFalse(r.exists("result-2.txt"))
        self.assertEqual(self.raw(), before)


class FollowUpBase(SeriesCase):
    """Rounds that follow an admitting round r1 of skills-top: an extension, an amendment and a
    replicate, as the spec's cases SR21 and SR22 write them."""

    def extension(self, name="r1x", **overrides):
        overrides.setdefault("hypotheses", [SIX_OF_SIX])
        overrides.setdefault("reads_per_reader", "4")
        return self.round(name, extends="../r1/plan.txt.freeze", **overrides)

    def first(self, **overrides):
        overrides.setdefault("hypotheses", [SIX_OF_SIX])
        return self.admitted(**overrides)

    def amendment(self, name, first, **overrides):
        return self.round(name, amends="../%s/plan.txt.freeze" % first, **overrides)

    def replicate(self, name, first="r1"):
        r = self.round(name)
        source = os.path.join(self.root, first, "plan.txt")
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        r.write("plan.txt", text + "replicate-of: ../%s/plan.txt.freeze\n" % first)
        return r

    def frozen(self, r):
        frozen = r.freeze()
        self.assertEqual(frozen.exit_code, 0, frozen.error)
        return r

    def run_ok(self, r):
        result = r.run()
        self.assertEqual(result.exit_code, 0, result.error)
        return result


class FollowUpCase(FollowUpBase):
    def test_sr21_an_extension_adds_an_item_and_no_row(self):
        self.first(series_note="shorter summary")
        before = self.lines()
        x = self.frozen(self.extension(series_note="shorter summary"))
        result = self.run_ok(x)
        after = self.lines()
        self.assertEqual(len(after), 3)
        self.assertEqual(after[:2], before[:2])
        self.assertEqual(result.text.splitlines()[-1],
                         "series: added result of r1x to row skills-top in ../labs.series.tsv")
        old, new = before[2].split("\t"), after[2].split("\t")
        self.assertEqual(new[:6], old[:6])
        self.assertEqual(new[7:], old[7:])
        self.assertEqual(new[6], old[6] + "; r1x@%s extends: h1 SUPPORTED" % x.plan_sha())
        self.assertEqual(self.record().exit_code, 0)

    def test_sr22_an_amendment_adds_an_item_of_kind_amends(self):
        first, _result = self.first(hypotheses=[SIX])
        a1 = self.frozen(self.amendment("r1a", "r1", hypotheses=[TWELVE],
                                        reads_per_reader="12"))
        result = self.run_ok(a1)
        self.assertEqual(result.text.splitlines()[-1],
                         "series: added result of r1a to row skills-top in ../labs.series.tsv")
        self.assertEqual(self.cells(3)[6], "r1@%s: h1 SUPPORTED; r1a@%s amends: h1 SUPPORTED"
                         % (first.plan_sha(), a1.plan_sha()))
        again = a1.score()
        self.assertEqual(again.text.splitlines()[-1],
                         "series: no change: plan %s is already recorded in row skills-top "
                         "(line 3)" % a1.plan_sha()[:12])

    def test_sr22b_a_replicate_adds_an_item_of_kind_replicate_with_its_own_hash(self):
        first, _result = self.first(hypotheses=[SIX])
        rep = self.frozen(self.replicate("r1r"))
        self.run_ok(rep)
        self.assertNotEqual(rep.plan_sha(), first.plan_sha())
        self.assertEqual(self.cells(3)[6], "r1@%s: h1 SUPPORTED; r1r@%s replicate: h1 SUPPORTED"
                         % (first.plan_sha(), rep.plan_sha()))
        again = rep.score()
        self.assertEqual(again.text.splitlines()[-1],
                         "series: no change: plan %s is already recorded in row skills-top "
                         "(line 3)" % rep.plan_sha()[:12])
        self.assertEqual(self.record().exit_code, 0)

    def test_sr23_a_follow_up_whose_draft_has_no_row(self):
        self.first()
        x = self.extension()
        self.write_series([BASE_ROW])
        lines = x.refused()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("skills-top:"), lines)

    def test_sr23b_a_follow_up_whose_draft_file_is_not_the_rows(self):
        first, _result = self.first()
        x = self.extension()
        cells = self.cells(3)
        cells[2] = "d" * 64
        self.write_series([BASE_ROW, "\t".join(cells)])
        self.assertEqual(x.refused(), [
            "skills-top: the plan's file is not the file the series records (computed %s from "
            "the file's bytes; the row holds %s)" % (first.sha("skills-top.txt"), "d" * 64)])

    def test_sr23c_a_named_earlier_plan_the_row_does_not_record(self):
        self.first()
        x = self.extension()
        cells = self.cells(3)
        other = "e" * 64
        cells[5] = other
        cells[6] = "r1@%s: h1 SUPPORTED" % other
        self.write_series([BASE_ROW, "\t".join(cells)])
        lines = x.refused()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("extends:"), lines)
        self.assertIn("skills-top", lines[0])

    def test_sr23d_a_wrong_parent(self):
        self.first()
        x = self.extension()
        cells = self.cells(3)
        cells[1] = "base2"
        self.write_series([BASE_ROW, hand_row("base2"), "\t".join(cells)])
        lines = x.refused()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("skills-top:"), lines)
        self.assertIn("base2", lines[0])

    def test_sr24_only_the_one_cell_changes(self):
        self.first()
        before = self.text()
        x = self.frozen(self.extension())
        self.run_ok(x)
        item = "; r1x@%s extends: h1 SUPPORTED" % x.plan_sha()
        lines = before.split("\n")
        fields = lines[2].split("\t")
        fields[6] += item
        lines[2] = "\t".join(fields)
        self.assertEqual(self.text(), "\n".join(lines))

    def test_sr24b_a_builder_that_changes_another_byte_is_kept_out(self):
        self.first()
        x = self.frozen(self.extension())
        before = self.raw()
        real = series._build

        def changes_the_date(old, rows, facts, item):
            return real(old, rows, facts, item).replace("2026-11-15", "2026-11-14", 1)

        with mock.patch.object(series, "_build", changes_the_date):
            result = x.run()
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.text.splitlines()[-1].startswith("series: not written: "))
        self.assertEqual(self.raw(), before)
        self.assertTrue(x.exists("result-1.txt"))

    def test_sr28_the_whole_digest_is_compared_for_a_scored_plan(self):
        self.first()
        x = self.frozen(self.extension())
        cells = self.cells(3)
        fake = x.plan_sha()[:12] + "f" * 52
        self.assertNotEqual(fake, x.plan_sha())
        cells[6] += "; fake@%s extends: h1 SUPPORTED" % fake
        self.write_series([BASE_ROW, "\t".join(cells)])
        result = self.run_ok(x)
        # a test of the first 12 digits only would say "no change" here
        self.assertEqual(result.text.splitlines()[-1],
                         "series: added result of r1x to row skills-top in ../labs.series.tsv")
        self.assertTrue(self.cells(3)[6].endswith("; fake@%s extends: h1 SUPPORTED; r1x@%s "
                                                  "extends: h1 SUPPORTED" % (fake, x.plan_sha())))

    def test_sr28b_a_follow_up_naming_the_real_plan_is_refused_when_only_a_prefix_matches(self):
        first, _result = self.first()
        x = self.extension()
        cells = self.cells(3)
        fake = first.plan_sha()[:12] + "f" * 52
        cells[5] = fake
        cells[6] = "r1@%s: h1 SUPPORTED" % fake
        self.write_series([BASE_ROW, "\t".join(cells)])
        lines = x.refused()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("extends:"), lines)

    def test_sr29_a_follow_up_of_a_follow_up(self):
        first, _result = self.first(hypotheses=[SIX])
        a1 = self.frozen(self.amendment("r1a", "r1", hypotheses=[TWELVE],
                                        reads_per_reader="12"))
        self.run_ok(a1)
        twenty_four = TWELVE.replace("12 of 12", "24 of 24").replace("8 or more", "16 or more")
        a2 = self.frozen(self.amendment("r1b", "r1a", hypotheses=[twenty_four],
                                        reads_per_reader="24"))
        self.run_ok(a2)
        self.assertEqual(self.cells(3)[6], "r1@%s: h1 SUPPORTED; r1a@%s amends: h1 SUPPORTED; "
                         "r1b@%s amends: h1 SUPPORTED"
                         % (first.plan_sha(), a1.plan_sha(), a2.plan_sha()))
        self.assertEqual(self.record().exit_code, 0)

    def test_sr29b_the_same_when_the_first_amendment_is_not_in_the_row(self):
        self.first(hypotheses=[SIX])
        a1 = self.frozen(self.amendment("r1a", "r1", hypotheses=[TWELVE],
                                        reads_per_reader="12"))
        self.run_ok(a1)
        cells = self.cells(3)
        cells[6] = cells[6].split("; ")[0]
        self.write_series([BASE_ROW, "\t".join(cells)])
        twenty_four = TWELVE.replace("12 of 12", "24 of 24").replace("8 or more", "16 or more")
        a2 = self.amendment("r1b", "r1a", hypotheses=[twenty_four], reads_per_reader="24")
        lines = a2.refused()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("amends:"), lines)
        self.assertIn("skills-top", lines[0])

    def test_sr33_no_hash_is_abbreviated_in_the_file(self):
        first, _result = self.first(hypotheses=[SIX])
        a = self.frozen(self.amendment("r1a", "r1", hypotheses=[TWELVE], reads_per_reader="12"))
        self.run_ok(a)
        rep = self.frozen(self.replicate("r1r"))
        self.run_ok(rep)
        for item in self.cells(3)[6].split("; "):
            digest = item.split("@")[1].split(":")[0].split(" ")[0]
            self.assertEqual(len(digest), 64, item)
        for line in self.lines()[1:]:
            fields = line.split("\t")
            for cell in (fields[2], fields[3], fields[5]):
                self.assertIn(len(cell), (0, 64), line)
        # the messages hold the first 12 digits and no more
        for follow, other in ((a, rep), (rep, a)):
            line = follow.score().text.splitlines()[-1]
            self.assertIn("plan %s is already" % follow.plan_sha()[:12], line)
            self.assertNotIn(follow.plan_sha()[:13], line)
            self.assertNotIn(other.plan_sha()[:12], line)


class MultiplePlansCase(SeriesCase):
    def test_sr19_two_admitting_plans_make_two_rows(self):
        first, _result = self.admitted()
        second = self.round("r2", comparisons=["skills-top vs skills-top-short"],
                            hypotheses=["SUPPORTED if skills-top-short preferred in 6 of 6; "
                                        "otherwise INCONCLUSIVE"], fake_reader=None)
        self.assertEqual(second.freeze().exit_code, 0, second.freeze().error)
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        self.assertEqual(len(self.lines()), 4)
        self.assertEqual(self.cells(4)[:2], ["skills-top-short", "skills-top"])
        self.assertEqual(self.cells(4)[4], "r2")
        self.assertEqual(self.record().exit_code, 0)


class RecordCase(SeriesCase):
    def declared(self, rows):
        self.write_series(rows)
        return self.record()

    def test_sr12_the_declaration_finds_each_fault(self):
        h = "a" * 64
        ok = lambda d, p="", date="2026-11-15": hand_row(d, p, file_sha=h, date=date)  # noqa
        child = ok("kid", "base", "2026-11-16")
        short = "\t".join(["x", "base", h, "", "", "", "", "2026-11-16"])
        cases = [
            ("a root written none", [ok("base", "none")], "corrects a missing row"),
            ("a parent that is the row itself", [ok("base"), ok("a", "a")], "corrects itself"),
            ("a parent that is a later row", [ok("base"), ok("a", "b"), ok("b", "base")],
             "corrects a later row, line 4"),
            ("a parent that is no row", [ok("base"), ok("a", "zzz")], "corrects a missing row"),
            ("a child dated before its parent", [ok("base", date="2026-11-16"), ok("a", "base")],
             "dated before the row it corrects, line 2"),
            ("a row with its trailing tabs missing", [ok("base"), child, short],
             "fields 8, the header has 9"),
        ]
        for label, rows, finding in cases:
            with self.subTest(case=label):
                found = self.declared(rows)
                self.assertEqual(found.exit_code, 1, found.text)
                self.assertIn(finding, found.text)
        with self.subTest(case="every parent earlier and the root's parent empty"):
            found = self.declared([ok("base"), child])
            self.assertEqual(found.exit_code, 0, found.text)

    def test_sr13_root_child_grandchild_and_a_repeated_draft(self):
        h = "a" * 64
        rows = [hand_row("base", file_sha=h), hand_row("kid", "base", file_sha=h,
                                                          date="2026-11-15"),
                hand_row("grandkid", "kid", file_sha=h, date="2026-11-16")]
        found = self.declared(rows)
        self.assertEqual(found.exit_code, 0, found.text)
        found = self.declared(rows[:2] + [rows[1]])
        self.assertEqual(found.exit_code, 1, found.text)
        self.assertIn("repeated key, first on line 3", found.text)


TZ_SCRIPT = textwrap.dedent("""
    import datetime
    import sys
    import time
    sys.path.insert(0, sys.argv[1])
    time.tzset()
    from career_track_record import ab
    now = datetime.datetime.strptime(sys.argv[3], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc)
    sys.exit(ab.run(sys.argv[2], now=now).exit_code)
""")


class DateCase(SeriesCase):
    def date_of_row(self, now, name):
        r = self.round(name)
        r.now = now
        self.assertEqual(r.freeze().exit_code, 0)
        result = r.run()
        self.assertEqual(result.exit_code, 0, result.error)
        return self.cells(3)[7]

    def test_sr14c_the_date_is_the_utc_day(self):
        for number, (now, expected) in enumerate((
                (datetime.datetime(2026, 11, 16, 23, 59, 59, tzinfo=UTC), "2026-11-16"),
                (datetime.datetime(2026, 11, 17, 0, 0, 0, tzinfo=UTC), "2026-11-17"))):
            with self.subTest(now=now.isoformat()):
                self.write_series([BASE_ROW])
                self.assertEqual(self.date_of_row(now, "d%d" % number), expected)

    def test_sr14d_a_clock_in_another_zone_is_read_as_the_instant_it_is(self):
        plus_two = datetime.timezone(datetime.timedelta(hours=2))
        now = datetime.datetime(2026, 11, 17, 1, 0, 0, tzinfo=plus_two)
        # 2026-11-16T23:00:00Z: local time gives the 17th, the UTC day is the 16th
        self.assertEqual(self.date_of_row(now, "z1"), "2026-11-16")

    def test_sr14e_the_date_does_not_follow_the_process_time_zone(self):
        zones = (("Pacific/Pago_Pago", "2026-11-17T00:00:00Z", "2026-11-17"),
                 ("Pacific/Kiritimati", "2026-11-16T23:59:59Z", "2026-11-16"))
        for number, (zone, instant, expected) in enumerate(zones):
            with self.subTest(zone=zone):
                if not os.path.exists("/usr/share/zoneinfo/" + zone):
                    self.skipTest("no zoneinfo for " + zone)
                self.write_series([BASE_ROW])
                r = self.round("tz%d" % number)
                self.assertEqual(r.freeze().exit_code, 0)
                env = dict(os.environ, TZ=zone)
                done = subprocess.run(
                    [sys.executable, "-I", "-c", TZ_SCRIPT, SRC, r.plan_path, instant],
                    env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
                self.assertEqual(done.returncode, 0, done.stderr.decode("utf-8"))
                # a date read from local time would be the other day, in each zone
                self.assertEqual(self.cells(3)[7], expected)

    def test_sr14f_with_no_clock_given_the_date_is_the_utc_day_now(self):
        before = time.strftime("%Y-%m-%d", time.gmtime())
        day = series.utc_day(None)
        after = time.strftime("%Y-%m-%d", time.gmtime())
        self.assertIn(day, (before, after))


class ResultFileCase(SeriesCase):
    def test_sr16_a_failed_replacement_keeps_the_result_and_the_old_file(self):
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        before = self.raw()
        broken = OSError(errno.EIO, "Input/output error")
        with mock.patch.object(series, "_replace", side_effect=broken):
            result = r.run()
        # SR1's run would have exited 0
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.text.splitlines()[-1],
                         "series: not written: Input/output error")
        self.assertEqual(self.raw(), before)
        self.assertTrue(r.read("result-1.txt").endswith("exit status: 0\n"))
        self.assertEqual([x for x in r.result_lines() if x.startswith("series:")], [])
        again = r.score()
        self.assertEqual((again.exit_code, again.error), (0, ""))
        self.assertEqual(again.text.splitlines()[-1],
                         "series: added row skills-top to ../labs.series.tsv")
        self.assertEqual(self.cells(3)[6], "r1@%s: h1 SUPPORTED" % r.plan_sha())

    def test_sr16b_a_failed_write_never_exits_2(self):
        # a cut run exits 1 on its own; the failed write leaves it 1 and never 2
        readers = ["reader-1 | fake | family m1 | cost 5", "reader-2 | fake | family m2 | cost 5"]
        r = self.round(readers=readers, spend_ceiling="20")
        self.assertEqual(r.freeze().exit_code, 0)
        with mock.patch.object(series, "_replace", side_effect=OSError(errno.EIO, "boom")):
            result = r.run()
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.ran)

    def test_sr17_a_series_file_without_its_final_line_break_stops_score(self):
        r, result = self.admitted()
        self.write_raw(self.raw()[:-1])
        before = self.raw()
        again = r.score()
        self.assertEqual((again.exit_code, again.ran), (2, False))
        self.assertIn("line break", again.error)
        self.assertFalse(r.exists("result-2.txt"))
        self.assertEqual(self.raw(), before)

    def test_sr20_names_are_printed_escaped(self):
        escape = chr(27)
        self.series = os.path.join(self.root, "labs%s.series.tsv" % escape)
        self.write_series([BASE_ROW])
        r = self.round(series="../labs%s.series.tsv" % escape)
        self.assertEqual(r.freeze().exit_code, 0)
        result = r.run()
        self.assertEqual(result.exit_code, 0, result.error)
        line = result.text.splitlines()[-1]
        self.assertEqual(line, "series: added row skills-top to ../labs\\x1b.series.tsv")
        self.assertNotIn(escape, result.text)
        again = r.score()
        self.assertNotIn(escape, again.text)

    def test_sr20b_a_bidirectional_control_in_the_name_is_escaped_too(self):
        mark = chr(0x202E)
        self.series = os.path.join(self.root, "labs%s.series.tsv" % mark)
        self.write_series([BASE_ROW])
        r = self.round(series="../labs%s.series.tsv" % mark)
        self.assertEqual(r.freeze().exit_code, 0)
        result = r.run()
        self.assertNotIn(mark, result.text)
        self.assertEqual(result.text.splitlines()[-1],
                         "series: added row skills-top to ../labs\\u202e.series.tsv")

    def test_sr32_the_lock_file_is_never_read(self):
        junk = b"not a series file \xff\xfe\n"
        with open(self.lock_path(), "wb") as handle:
            handle.write(junk)
        os.chmod(self.lock_path(), 0o600)
        r, result = self.admitted()
        with open(self.lock_path(), "rb") as handle:
            self.assertEqual(handle.read(), junk)
        self.assertEqual(self.record().exit_code, 0)


class FolderNameCase(SeriesCase):
    def test_sr30_a_folder_name_that_a_row_cannot_carry_is_refused(self):
        names = [("a semicolon", "r1;x"), ("an at sign", "r1@x"), ("a tab", "r1\tx"),
                 ("a CR", "r1\rx"), ("an LF", "r1\nx"), ("an ESC", "r1" + chr(27) + "x"),
                 ("U+0085", "r1" + chr(0x85) + "x")]
        for label, name in names:
            with self.subTest(case=label):
                self.write_series([BASE_ROW])
                before = self.raw()
                r = self.round(name)
                result = r.freeze()
                self.assertEqual((result.exit_code, result.ran), (2, False), result.text)
                self.assertFalse(r.exists("plan.txt.freeze"))
                self.assertEqual(len(result.error.splitlines()), 1, result.error)
                self.assertEqual(result.error, "%s: %s" % (ab._show(name), FOLDER_MESSAGE))
                # printed escaped, as every other ab line is
                for raw in ("\t", "\r", "\n", chr(27), chr(0x85)):
                    self.assertNotIn(raw, result.error.replace(FOLDER_MESSAGE, ""))
                self.assertEqual(self.raw(), before)

    def test_sr30b_names_that_are_accepted_are_read_back_without_ambiguity(self):
        names = ["a b", "c,d", "e:f", "r1.2", "2026.11.17", "labs.r1", "review, final"]
        for number, name in enumerate(names):
            with self.subTest(name=name):
                self.write_series([BASE_ROW])
                r = self.round(name)
                self.assertEqual(r.freeze().exit_code, 0)
                result = r.run()
                self.assertEqual(result.exit_code, 0, result.error)
                self.assertEqual(self.cells(3)[4], name)
                self.assertEqual(self.cells(3)[6], "%s@%s: h1 SUPPORTED" % (name, r.plan_sha()))
                # check 1 reads the row back: scoring again finds the plan in it
                again = r.score()
                self.assertEqual(again.exit_code, 0, again.error)
                self.assertTrue(again.text.splitlines()[-1].startswith("series: no change: "),
                                again.text)

    def test_sr30c_a_dot_segment_is_refused(self):
        own = self.round("", series="labs.series.tsv")
        self.assertIn("not strictly below", own.refused()[0])
        os.makedirs(os.path.join(self.root, "deep"))
        shutil.copyfile(self.series, os.path.join(self.root, "deep", "labs.series.tsv"))
        out = self.round("r2", series="../deep/labs.series.tsv")
        self.assertIn("not strictly below", out.refused()[0])


class LockCase(SeriesCase):
    """The lock and the commit phase (series spec section 5)."""

    def hold(self):
        """A descriptor holding the lock on ``<series file>.lock``, closed at cleanup."""
        fd = os.open(self.lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(self.release, [fd])
        fcntl.flock(fd, fcntl.LOCK_EX)
        return [fd]

    def release(self, box):
        if box:
            try:
                os.close(box.pop())
            except OSError:
                pass

    def bounded(self, seconds):
        """Fail, rather than hang, if the block runs longer than ``seconds``."""
        def stop(signum, frame):
            raise AssertionError("hung for more than %d seconds" % seconds)
        previous = signal.signal(signal.SIGALRM, stop)
        signal.alarm(seconds)
        self.addCleanup(signal.signal, signal.SIGALRM, previous)
        self.addCleanup(signal.alarm, 0)

    def test_sr26_a_lock_that_cannot_be_taken_does_not_block_and_leaves_the_file(self):
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        before = self.raw()
        holder = self.hold()
        started = time.monotonic()
        with mock.patch.object(series, "LOCK_DEADLINE", 0.3):
            result = r.run()
        elapsed = time.monotonic() - started
        self.assertEqual(result.exit_code, 1)
        line = result.text.splitlines()[-1]
        self.assertTrue(line.startswith(
            "series: not written: cannot take ../labs.series.tsv.lock: "), line)
        self.assertEqual(self.raw(), before)
        # the default wait is ten seconds: a test that ignored the shortened one would be slower
        self.assertLess(elapsed, 5)
        with mock.patch.object(series, "LOCK_DEADLINE", 0.3):
            held = r.score()
        self.assertEqual(held.exit_code, 1, held.error)
        self.assertTrue(held.text.splitlines()[-1].startswith("series: not written: cannot take"))
        self.assertEqual(self.raw(), before)
        self.assertTrue(os.path.exists(self.lock_path()))
        self.release(holder)
        again = r.score()
        self.assertEqual((again.exit_code, again.error), (0, ""))
        self.assertEqual(again.text.splitlines()[-1],
                         "series: added row skills-top to ../labs.series.tsv")
        self.assertEqual(self.cells(3)[6], "r1@%s: h1 SUPPORTED" % r.plan_sha())

    def test_sr27_the_row_is_built_on_the_file_as_it_is_under_the_lock(self):
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        other = hand_row("skills-top-short", parent="base")
        real = series._take_lock

        def another_process_wrote_first(facts, started):
            self.write_series([BASE_ROW, other])
            return real(facts, started)

        with mock.patch.object(series, "_take_lock", another_process_wrote_first):
            result = r.run()
        self.assertEqual((result.exit_code, result.error), (0, ""))
        lines = self.lines()
        self.assertEqual(lines[1:3], [BASE_ROW, other])
        self.assertEqual(lines[3], self.expected_row(r))
        self.assertEqual(self.record().exit_code, 0)

    def test_sr27b_a_change_that_breaks_a_rule_is_kept_as_it_is(self):
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        real = series._take_lock

        def another_process_broke_it(facts, started):
            self.write_raw(self.raw() + b"not a row\n")
            return real(facts, started)

        with mock.patch.object(series, "_take_lock", another_process_broke_it):
            result = r.run()
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.text.splitlines()[-1].startswith("series: not written: "))
        self.assertIn("fields 1", result.text.splitlines()[-1])
        self.assertTrue(self.text().endswith("not a row\n"))
        self.assertTrue(r.exists("result-1.txt"))

    def test_sr31_new_bytes_that_break_the_grammar_never_replace_the_file(self):
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        before = self.raw()
        real = series._build

        def bad_item(old, rows, facts, item):
            return real(old, rows, facts, item.replace(": h1 SUPPORTED", ": h1 MAYBE"))

        with mock.patch.object(series, "_build", bad_item):
            result = r.run()
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.text.splitlines()[-1].startswith("series: not written: "))
        self.assertEqual(self.raw(), before)
        self.assertEqual(self.folder_files(), ["labs.series.tsv", "labs.series.tsv.lock", "r1"])

    def test_sr34_a_new_lock_file_is_made_owner_readable_and_writable(self):
        for umask in (0o022, 0o277):
            with self.subTest(umask=oct(umask)):
                for name in os.listdir(self.root):
                    if name.endswith(".lock"):
                        os.remove(os.path.join(self.root, name))
                self.write_series([BASE_ROW])
                rounds = []
                for number, draft in enumerate(("skills-top", "skills-top-short")):
                    r = self.round("u%d-%d" % (umask, number), comparisons=[
                        "base vs " + draft], hypotheses=[
                        "SUPPORTED if %s preferred in 6 of 6; otherwise INCONCLUSIVE" % draft],
                        fake_reader=None)
                    self.assertEqual(r.freeze().exit_code, 0)
                    with mock.patch.object(series, "after_result",
                                           return_value=("", "", False)):
                        self.assertEqual(r.run().exit_code, 0)
                    rounds.append((r, draft))
                before = os.umask(umask)
                try:
                    for r, draft in rounds:
                        recorded = dict(ab.harness.read_freeze(r.path("plan.txt.freeze")))
                        line, warning, failed = series.after_result(
                            ab.parse(r.plan_path), r.plan_path, recorded, [("h1", "INCONCLUSIVE")],
                            CLOCK)
                        # a lock file left at 0o400 (no fchmod) fails the second write
                        self.assertEqual((failed, warning), (False, ""), line)
                        self.assertEqual(line, "series: added row %s to ../labs.series.tsv"
                                         % draft)
                finally:
                    os.umask(before)
                self.assertEqual(stat.S_IMODE(os.stat(self.lock_path()).st_mode), 0o600)
                self.assertEqual(len(self.lines()), 4)

    def test_sr34b_an_existing_lock_file_keeps_its_mode(self):
        with open(self.lock_path(), "w") as handle:
            handle.write("")
        os.chmod(self.lock_path(), 0o644)
        self.admitted()
        self.assertEqual(stat.S_IMODE(os.stat(self.lock_path()).st_mode), 0o644)

    def not_written(self, r, expect="series: not written: cannot take "):
        before = self.raw()
        result = r.run()
        self.assertEqual(result.exit_code, 1, result.text)
        line = result.text.splitlines()[-1]
        self.assertTrue(line.startswith(expect + "") and "labs.series.tsv.lock: " in line, line)
        self.assertEqual(self.raw(), before)
        self.assertTrue(r.exists("result-1.txt"))
        return line

    def test_sr35_an_unwritable_lock_file_is_not_taken_read_only(self):
        if os.geteuid() == 0:
            self.skipTest("the owner of a read-only file can still write it as root")
        with open(self.lock_path(), "w") as handle:
            handle.write("")
        os.chmod(self.lock_path(), 0o444)
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        self.not_written(r)
        self.assertTrue(os.path.exists(self.lock_path()))

    def test_sr35b_a_lock_file_that_is_a_symbolic_link(self):
        target = os.path.join(self.root, "elsewhere")
        with open(target, "w") as handle:
            handle.write("")
        os.symlink(target, self.lock_path())
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        self.not_written(r)
        self.assertTrue(os.path.islink(self.lock_path()))

    def test_sr35c_a_lock_file_that_is_a_directory(self):
        os.mkdir(self.lock_path())
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        self.not_written(r)
        self.assertTrue(os.path.isdir(self.lock_path()))

    def test_sr36_a_fifo_for_a_lock_file_is_refused_without_opening_it(self):
        self.bounded(30)
        os.mkfifo(self.lock_path())
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        started = time.monotonic()
        with mock.patch.object(series, "LOCK_DEADLINE", 0.5), \
                mock.patch.object(series, "_open", wraps=series._open) as opened:
            self.not_written(r)
        # refused by the lstat: the leaf is never opened (a mutant without the lstat opens it)
        self.assertEqual(opened.call_count, 0)
        self.assertLess(time.monotonic() - started, 5)
        self.assertTrue(stat.S_ISFIFO(os.lstat(self.lock_path()).st_mode))

    def test_sr36b_a_leaf_swapped_for_a_fifo_after_the_lstat_is_refused_by_the_fstat(self):
        self.bounded(30)
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        real = series._open

        def swapped(path, flags, mode):
            os.mkfifo(path)
            return real(path, flags, mode)

        with mock.patch.object(series, "_open", swapped):
            line = self.not_written(r)
        self.assertIn("not a regular file", line)

    def test_sr36d_a_leaf_swapped_for_a_symbolic_link_after_the_lstat_is_not_followed(self):
        # The lstat sees no lock file; a link to a regular file appears before the open. Only
        # O_NOFOLLOW refuses it (a mutant without it opens the target and takes the lock).
        self.bounded(30)
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        target = os.path.join(self.root, "elsewhere")
        with open(target, "w") as handle:
            handle.write("")
        real = series._open

        def swapped(path, flags, mode):
            os.symlink(target, path)
            return real(path, flags, mode)

        with mock.patch.object(series, "_open", swapped):
            self.not_written(r)
        self.assertTrue(os.path.islink(self.lock_path()))
        self.assertEqual(os.path.getsize(target), 0)

    def test_sr36c_an_open_that_would_block_ends_at_the_deadline(self):
        self.bounded(30)
        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        started = time.monotonic()
        blocked = BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable")
        with mock.patch.object(series, "LOCK_DEADLINE", 0.4), \
                mock.patch.object(series, "_open", side_effect=blocked):
            self.not_written(r)
        elapsed = time.monotonic() - started
        # no later than the deadline plus one retry interval (and the rest of the run)
        self.assertLess(elapsed, 5)

    def test_sr38_the_lock_file_stays(self):
        r, result = self.admitted()
        self.assertTrue(os.path.exists(self.lock_path()))
        self.assertEqual(os.path.getsize(self.lock_path()), 0)
        other = self.round("r2", comparisons=["base vs skills-top-short"], hypotheses=[
            "SUPPORTED if skills-top-short preferred in 6 of 6; otherwise INCONCLUSIVE"],
            fake_reader=None)
        self.assertEqual(other.freeze().exit_code, 0)
        with mock.patch.object(series, "_replace", side_effect=OSError(errno.EIO, "boom")):
            self.assertEqual(other.run().exit_code, 1)
        self.assertTrue(os.path.exists(self.lock_path()))

    def test_sr39_every_failure_under_the_lock_releases_it(self):
        real_write = series._write_temp

        def leaves_a_temp_file(path, data, mode):
            real_write(path, data, mode)
            raise OSError(errno.ENOSPC, "No space left on device")

        injections = [
            ("the reread", "_reread", dict(side_effect=OSError(errno.EIO, "Input/output error"))),
            ("the build", "_build", dict(side_effect=RuntimeError("boom"))),
            ("the temporary file write", "_write_temp", dict(side_effect=leaves_a_temp_file)),
            ("os.replace", "_replace", dict(side_effect=OSError(errno.EXDEV, "cross-device"))),
        ]
        for number, (label, seam, options) in enumerate(injections):
            with self.subTest(failure=label):
                self.write_series([BASE_ROW])
                r = self.round("l%d" % number)
                self.assertEqual(r.freeze().exit_code, 0)
                before = self.raw()
                with mock.patch.object(series, seam, **options):
                    result = r.run()
                self.assertEqual(result.exit_code, 1, result.text)
                self.assertTrue(result.text.splitlines()[-1].startswith("series: not written: "))
                self.assertEqual(self.raw(), before)
                names = self.folder_files()
                self.assertEqual([n for n in names if n not in (
                    "labs.series.tsv", "labs.series.tsv.lock") and not n.startswith("l")], [])
                self.assertEqual([n for n in names if ".tmp" in n], [])
                # a second write in the same process takes the lock at once
                with mock.patch.object(series, "LOCK_DEADLINE", 1.0):
                    again = r.score()
                self.assertEqual((again.exit_code, again.error), (0, ""))
                self.assertEqual(again.text.splitlines()[-1],
                                 "series: added row skills-top to ../labs.series.tsv")
                self.assertEqual(len(self.lines()), 3)

    def test_sr39b_an_error_after_the_replacement_is_never_not_written(self):
        real_close = series._close

        def closes_then_fails(fd):
            real_close(fd)
            raise OSError(errno.EIO, "Input/output error")

        r = self.round()
        self.assertEqual(r.freeze().exit_code, 0)
        with mock.patch.object(series, "_close", closes_then_fails):
            result = r.run()
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertEqual(result.text.splitlines()[-1],
                         "series: added row skills-top to ../labs.series.tsv")
        self.assertNotIn("not written", result.text)
        self.assertEqual(result.warnings,
                         "series: lock release failed after the write: Input/output error\n")
        self.assertEqual(self.lines()[2], self.expected_row(r))


WORKER = textwrap.dedent("""
    import datetime
    import sys
    sys.path.insert(0, sys.argv[1])
    from career_track_record import ab, series
    plan, marker = sys.argv[2], sys.argv[3]
    series.LOCK_DEADLINE = 120.0
    real = series._flock

    def flock(fd):
        try:
            real(fd)
        except BlockingIOError:
            open(marker, "w").close()
            raise

    series._flock = flock
    now = datetime.datetime(2026, 11, 16, 10, 0, 0, tzinfo=datetime.timezone.utc)
    result = ab.run(plan, now=now)
    sys.stdout.write(result.text)
    sys.exit(result.exit_code)
""")


class TwoProcessesCase(FollowUpBase):
    """Two ``ab run`` processes, each released into the write while the test holds the lock until
    both are waiting for it."""

    def both(self, first, second):
        holder = os.open(self.lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(holder, fcntl.LOCK_EX)
        processes = []
        for number, r in enumerate((first, second)):
            marker = os.path.join(self.root, "waiting-%d" % number)
            processes.append((subprocess.Popen(
                [sys.executable, "-I", "-c", WORKER, SRC, r.plan_path, marker],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE), marker))
        try:
            limit = time.monotonic() + 90
            while not all(os.path.exists(marker) for _p, marker in processes):
                self.assertLess(time.monotonic(), limit, "a process never reached the lock")
                for process, _marker in processes:
                    self.assertIsNone(process.poll(), "a process ended before the lock")
                time.sleep(0.05)
        finally:
            os.close(holder)
        for process, _marker in processes:
            out, err = process.communicate(timeout=90)
            self.assertEqual(process.returncode, 0, (out + err).decode("utf-8"))

    def short(self, name):
        return self.round(name, comparisons=["base vs skills-top-short"], hypotheses=[
            "SUPPORTED if skills-top-short preferred in 6 of 6; otherwise INCONCLUSIVE"],
            fake_reader=None)

    def test_sr25_two_admitting_plans_both_survive(self):
        one = self.frozen(self.round("r1"))
        two = self.frozen(self.short("r2"))
        self.both(one, two)
        lines = self.lines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[1], BASE_ROW)
        self.assertEqual(sorted(x.split("\t")[0] for x in lines[2:]),
                         ["skills-top", "skills-top-short"])
        self.assertEqual(self.record().exit_code, 0)

    def test_sr25b_two_follow_ups_of_two_drafts_both_survive(self):
        first, _r = self.admitted("r1")
        second_first = self.frozen(self.short("r2"))
        self.assertEqual(second_first.run().exit_code, 0)
        one = self.frozen(self.replicate("r1r", "r1"))
        two = self.frozen(self.replicate("r2r", "r2"))
        self.both(one, two)
        for line in self.lines()[2:]:
            fields = line.split("\t")
            self.assertEqual(len(fields[6].split("; ")), 2, line)
        self.assertEqual(self.record().exit_code, 0)

    def test_sr25c_one_admitting_plan_and_one_follow_up_both_survive(self):
        first, _r = self.admitted("r1")
        follow = self.frozen(self.replicate("r1r", "r1"))
        admitting = self.frozen(self.short("r2"))
        self.both(follow, admitting)
        lines = self.lines()
        self.assertEqual(len(lines), 4)
        items = dict((x.split("\t")[0], len(x.split("\t")[6].split("; "))) for x in lines[2:])
        self.assertEqual(items, {"skills-top": 2, "skills-top-short": 1})
        self.assertEqual(self.record().exit_code, 0)


class CapabilityCase(FollowUpBase):
    def hidden(self):
        return mock.patch.dict(sys.modules, {"fcntl": None})

    def test_sr37_a_plan_with_series_is_refused_at_freeze_without_fcntl(self):
        r = self.round()
        with self.hidden():
            lines = r.refused()
        self.assertEqual(lines, ["plan line %d: %s" % (r.line_of("series: ../labs"), NO_FCNTL)])

    def test_sr37b_and_at_run_before_any_read(self):
        r = self.frozen(self.round())
        before = self.raw()
        with self.hidden():
            result = r.run()
        self.assertEqual((result.exit_code, result.ran), (2, False))
        self.assertEqual(result.error.splitlines(),
                         ["plan line %d: %s" % (r.line_of("series: ../labs"), NO_FCNTL)])
        for name in (ab.READS_DIR, ab.KEY_FILE, "result-1.txt"):
            self.assertFalse(r.exists(name), name)
        self.assertEqual(self.raw(), before)

    def test_sr37c_and_at_score_before_any_result(self):
        r, _result = self.admitted()
        before = self.raw()
        with self.hidden():
            result = r.score()
        self.assertEqual((result.exit_code, result.ran), (2, False))
        self.assertEqual(result.error.splitlines(),
                         ["plan line %d: %s" % (r.line_of("series: ../labs"), NO_FCNTL)])
        self.assertFalse(r.exists("result-2.txt"))
        self.assertEqual(self.raw(), before)

    def test_sr37d_a_plan_without_series_is_unchanged_with_fcntl_hidden(self):
        r = self.round(series=None)
        with self.hidden():
            self.assertEqual(r.freeze().exit_code, 0)
            self.assertEqual(r.run().exit_code, 0)
            self.assertEqual(r.score().exit_code, 0)

    def test_sr37e_the_modules_import_with_fcntl_hidden(self):
        script = ("import sys\nsys.modules['fcntl'] = None\nsys.path.insert(0, sys.argv[1])\n"
                  "import career_track_record.ab, career_track_record.series, "
                  "career_track_record.cli\n")
        done = subprocess.run([sys.executable, "-I", "-c", script, SRC], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(done.returncode, 0, done.stderr.decode("utf-8"))

    def test_sr40_the_three_commands_refuse_with_the_one_message(self):
        r, _result = self.admitted("r1")
        fresh = self.round("r2", comparisons=["base vs skills-top-short"], hypotheses=[
            "SUPPORTED if skills-top-short preferred in 6 of 6; otherwise INCONCLUSIVE"],
            fake_reader=None)
        frozen = self.frozen(self.round("r3", comparisons=["base vs skills-top-short"],
                                        hypotheses=["SUPPORTED if skills-top-short preferred in "
                                                    "6 of 6; otherwise INCONCLUSIVE"],
                                        fake_reader=None))
        with self.hidden():
            messages = [fresh.refused()[0], frozen.run().error, r.score().error]
        wanted = ["plan line %d: %s" % (x.line_of("series: ../labs"), NO_FCNTL)
                  for x in (fresh, frozen, r)]
        self.assertEqual(messages, wanted)

    def test_sr40b_fcntl_is_never_imported_for_a_plan_without_series(self):
        r = self.round(series=None)
        script = textwrap.dedent("""
            import sys
            sys.path.insert(0, sys.argv[1])
            from career_track_record import ab, cli
            sys.modules.pop("fcntl", None)

            class Fail(object):
                def find_spec(self, name, path=None, target=None):
                    if name == "fcntl":
                        raise SystemExit("fcntl was imported")
                    return None

            sys.meta_path.insert(0, Fail())
            plan = sys.argv[2]
            codes = [ab.freeze(plan).exit_code, ab.run(plan).exit_code, ab.score(plan).exit_code]
            print(codes, "fcntl" in sys.modules)
        """)
        done = subprocess.run([sys.executable, "-I", "-c", script, SRC, r.plan_path],
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        self.assertEqual(done.returncode, 0, done.stderr.decode("utf-8"))
        self.assertEqual(done.stdout.decode("utf-8").strip(), "[0, 0, 0] False")


if __name__ == "__main__":
    unittest.main()
