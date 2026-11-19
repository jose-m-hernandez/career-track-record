"""Tests for the runs that revision 4 of the reader panel spec ties together (docs/specs/reader-panel.md).
All data here is invented.

This module covers the calibration run (a plan that reads the anchors only, and a run that
names one), an amendment that restates a rule's counts at the same share, and an extension that
changes the sample size and pools the first run's reads. Each case builds its run folders side
by side in a private temporary parent, because an extension looks beside its own folder for
another extension of the same first run. No test starts a live reader: every reader is the
built-in fake reader.
"""

import hashlib
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from career_track_record import panel  # noqa: E402
from tests.test_panel import (  # noqa: E402
    ANCHORS, EXAMPLE_PLAN, FLAT_MANAGER, FX, FX_AB, LENSES, PANEL_FIXTURES, RANK,
    RANK_RECRUITER, SIX_PASS, Setup, default_values)

TAG = " [not blind: 0 reads left out] [uncalibrated]"
PLAIN = " [not blind: 0 reads left out]"
SIX = "recruiter | " + SIX_PASS
OVERALL_6 = "overall | PASS if score at least 7 in 6 of 6; otherwise INCONCLUSIVE"
EARLIER = "frozen under an earlier revision: %s"
AMEND = "an amendment may restate a rule's counts at the same share, and change nothing else: "
EXTEND = ("an extension may change only reads-per-reader, anchor-reads-per-reader and the "
          "number of readers of each model: ")
FIRST_NAMED = ("extends must name a first run, not an amendment, a replicate, an extension or "
               "a calibration: %s")


class Place(Setup):
    """A run folder named ``name`` inside ``parent``, otherwise as Setup."""

    def __init__(self, case, parent, name, **overrides):
        self.case = case
        self.folder = os.path.join(parent, name)
        os.mkdir(self.folder)
        for fixture in PANEL_FIXTURES:
            shutil.copyfile(os.path.join(FX, fixture), os.path.join(self.folder, fixture))
        shutil.copyfile(os.path.join(FX_AB, "base.txt"), os.path.join(self.folder, "version.txt"))
        shutil.copyfile(os.path.join(FX_AB, "posting.txt"),
                        os.path.join(self.folder, "posting.txt"))
        self.plan_path = os.path.join(self.folder, "plan.txt")
        self.values = default_values()
        self.change(**overrides)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Runs(unittest.TestCase):
    def setUp(self):
        self.parent = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.parent, True)

    def place(self, name, **overrides):
        return Place(self, self.parent, name, **overrides)

    def rel(self, name, what="plan.txt.freeze"):
        return os.path.join("..", name, what)

    def freeze_ok(self, s):
        result = s.freeze()
        self.assertEqual((result.exit_code, result.error), (0, ""))
        return result

    def done(self, s):
        result = s.frozen_run()
        self.assertIn(result.exit_code, (0, 1), result.error)
        return result, s.result_lines()

    def refused(self, s, message):
        """The freeze of ``s`` exits 2 naming ``message`` and writes no freeze file."""
        result = s.freeze()
        self.assertEqual(result.exit_code, 2, result.error)
        self.assertFalse(result.ran)
        self.assertIn(message, result.error.splitlines())
        self.assertFalse(s.exists("plan.txt.freeze"))
        return result.error.splitlines()

    def snapshot(self, *places):
        return [p.tree_hashes() for p in places]


class CalibrationRunCase(Runs):
    def cal(self, name="cal", fake=None, **overrides):
        return self.place(name, calibration_only="yes", rules=None,
                          fake_reader=RANK_RECRUITER + FLAT_MANAGER if fake is None else fake,
                          **overrides)

    def test_10_53_a_calibration_run_reads_no_version(self):
        s = self.place("cal", calibration_only="yes", rules=None, fake_reader=RANK)
        result, lines = self.done(s)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        key = s.read("key.txt").splitlines()
        self.assertEqual(len(key), 16)
        self.assertEqual([x.split("\t")[2] for x in key], ["strong"] * 4 + ["weak"] * 4
                         + ["strong"] * 4 + ["weak"] * 4)
        self.assertEqual(sorted(os.listdir(s.path("reads"))), ["l1", "l2"])
        for arm in ("l1", "l2"):
            self.assertEqual(sorted(os.listdir(s.path("reads", arm)), key=int),
                             [str(n) for n in range(1, 9)])
        self.assertEqual(s.reply_count("l1") + s.reply_count("l2"), 16)
        self.assertIn("calibration only: no version read", lines)
        # no version score, flag, missing, headroom, rule or uncalibrated line, and no
        # calibration header line
        for line in lines:
            self.assertFalse(line.startswith(("calibration:", "headroom", "rule ", "missing ",
                                              "flagged ", "scores l1 version",
                                              "scores l2 version")), line)
            self.assertNotIn("[uncalibrated]", line)
            self.assertNotIn("document=version", line)
        self.assertEqual([x for x in lines if x.startswith("reads ") and "version" in x], [])
        self.assertIn("counted lenses: l1 l2", lines)
        self.assertIn("scores l1 strong: scores=4 total=36 mean=9.00 lowest=9 highest=9", lines)
        self.assertIn("scores l1 weak: scores=4 total=8 mean=2.00 lowest=2 highest=2", lines)

    def test_a_calibration_run_prints_its_lines_after_the_counted_lenses(self):
        s = self.cal(fake=RANK)
        _result, lines = self.done(s)
        at = lines.index("counted lenses: l1 l2")
        self.assertEqual(lines[at + 1], "calibration only: no version read")
        for arm in ("l1", "l2"):
            line = lines.index("calibration %s: passed (strong median %s, weak median %s)"
                               % (arm, "9" if arm == "l1" else "8", "2" if arm == "l1" else "3"))
            self.assertLess(line, at)
        self.assertEqual(lines[lines.index("anchor gate l1: passed (strong scores 9, 9, 9, 9, "
                                           "all at least 7; weak scores 2, 2, 2, 2, all at "
                                           "most 4)") + 1], "lens l1: counted")

    def test_10_54_a_flat_lens_fails_calibration(self):
        s = self.cal()
        _result, lines = self.done(s)
        self.assertIn("calibration l1: passed (strong median 9, weak median 2)", lines)
        self.assertIn("calibration l2: failed (strong median 5, weak median 5)", lines)

    def test_the_calibration_uses_the_median_not_the_mean(self):
        # strong reads 9, 9, 9, 0: the median is 9, the mean 6.75 is below 7
        s = self.cal(fake=RANK_RECRUITER + ["recruiter | strong | score 0 | read 4"]
                     + ["manager | strong | score 8", "manager | weak | score 3"])
        _result, lines = self.done(s)
        self.assertIn("calibration l1: passed (strong median 9, weak median 2)", lines)
        self.assertIn("anchor gate l1: failed (strong read l1/4 scored 0, below 7)", lines)
        weak = self.cal("weak", fake=["recruiter | strong | score 9", "recruiter | weak | score 2",
                                      "recruiter | weak | score 9 | read 7",
                                      "recruiter | weak | score 9 | read 8",
                                      "manager | strong | score 8", "manager | weak | score 3"])
        _result, lines = self.done(weak)
        # weak reads 2, 2, 9, 9: the median is 5.5, above 4
        self.assertIn("calibration l1: failed (strong median 9, weak median 5.5)", lines)

    def test_a_calibration_judges_blind_readers_reads_only(self):
        # reader r2's strong reads (3 and 4) score 0, and r2 is not blind
        fake = RANK + ["recruiter | strong | score 0 | read 3",
                       "recruiter | strong | score 0 | read 4"]
        s = self.cal(fake=fake, readers=["r1 | fake", "r2 | fake | not-blind"])
        _result, lines = self.done(s)
        self.assertIn("calibration l1: passed (strong median 9, weak median 2)", lines)
        t = self.cal("blind", fake=fake)
        _result, lines = self.done(t)
        self.assertIn("calibration l1: failed (strong median 4.5, weak median 2)", lines)

    def test_an_anchor_with_no_valid_read_is_not_assessable(self):
        s = self.cal(fake=RANK + ["manager | strong | omit SCORE"])
        result, lines = self.done(s)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("calibration l2: failed (strong median not assessable, weak median 3)",
                      lines)
        self.assertIn("calibration l1: passed (strong median 9, weak median 2)", lines)
        t = self.cal("both", fake=RANK + ["manager | omit SCORE"])
        _result, lines = self.done(t)
        self.assertIn("calibration l2: failed (strong median not assessable, weak median "
                      "not assessable)", lines)

    def test_a_calibration_only_amendment_may_change_a_lens_file(self):
        first = self.cal("first")
        self.done(first)
        revised = self.cal("revised", fake=RANK, amends=self.rel("first"))
        revised.edit("hiring-manager.lens.txt", lambda text: text + "\nA revised lens.\n")
        self.freeze_ok(revised)
        _result, lines = self.done_run(revised)
        self.assertIn("calibration l1: passed (strong median 9, weak median 2)", lines)
        self.assertIn("calibration l2: passed (strong median 8, weak median 3)", lines)
        self.assertEqual(
            [x for x in lines if x.startswith("amended freeze sha256: ")],
            ["amended freeze sha256: " + sha256_text(first.read("plan.txt.freeze"))])

    def done_run(self, s):
        result = s.run()
        self.assertIn(result.exit_code, (0, 1), result.error)
        return result, s.result_lines()

    def test_an_amendment_keeps_calibration_only_as_the_plan_it_amends_has_it(self):
        first = self.cal("first")
        self.freeze_ok(first)
        s = self.place("second", fake_reader=RANK, amends=self.rel("first"), rules=[SIX])
        self.refused(s, "an amendment keeps calibration-only as the plan it amends has it")
        plain = self.place("plain", fake_reader=RANK, rules=[SIX])
        self.freeze_ok(plain)
        t = self.cal("third", fake=RANK, amends=self.rel("plain"))
        self.refused(t, "an amendment keeps calibration-only as the plan it amends has it")

    def test_a_calibration_run_with_a_failed_read_exits_1(self):
        s = self.cal(fake=RANK + ["recruiter | omit SCORE | read 1"])
        result, lines = self.done(s)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("exit status: 1", lines)
        self.assertEqual(result.error.splitlines(), ["failed read l1/1: missing SCORE"])


class CalibratedRunCase(Runs):
    def flat(self):
        s = self.place("flat", calibration_only="yes", rules=None,
                       fake_reader=RANK_RECRUITER + FLAT_MANAGER)
        self.done(s)
        return s

    def test_10_55_revise_before_any_version_read(self):
        first = self.flat()
        revised = self.place("revised", calibration_only="yes", rules=None, fake_reader=RANK,
                             amends=self.rel("flat"))
        revised.edit("hiring-manager.lens.txt", lambda text: text + "\nA revised lens.\n")
        self.freeze_ok(revised)
        revised.run()
        self.assertIn("calibration l2: passed (strong median 8, weak median 3)",
                      revised.result_lines())
        run = self.place("run", fake_reader=RANK, rules=[SIX], calibration=self.rel("revised"))
        run.edit("hiring-manager.lens.txt", lambda text: text + "\nA revised lens.\n")
        before = self.snapshot(first, revised)
        result, lines = self.done(run)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        at = [i for i, x in enumerate(lines) if x.startswith("prompt sha256:")][0]
        self.assertEqual(lines[at + 1], "calibration: " + sha256_text(
            revised.read("plan.txt.freeze")))
        self.assertIn("rule r1 (l1) verdict: PASS" + PLAIN, lines)
        for line in lines:
            self.assertNotIn("[uncalibrated]", line)
            self.assertFalse(line.startswith("calibration l"), line)
        self.assertNotIn("calibration: none; scores are uncalibrated", lines)
        self.assertEqual(self.snapshot(first, revised), before)
        self.assertEqual(run.score().exit_code, 0)
        self.assertEqual(self.snapshot(first, revised), before)

    def test_10_56_a_failed_calibration_voids_its_lens(self):
        flat = self.flat()
        rules = [SIX, "manager | " + SIX_PASS, OVERALL_6]
        run = self.place("run", fake_reader=RANK, rules=rules, calibration=self.rel("flat"))
        before = self.snapshot(flat)
        result, lines = self.done(run)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("lens l2: not counted (l2 failed its calibration)", lines)
        self.assertIn("lens l1: counted", lines)
        self.assertIn("counted lenses: l1", lines)
        self.assertIn("rule r2 (l2) verdict: INCONCLUSIVE" + PLAIN, lines)
        self.assertIn("rule r2 (l2) reason: l2 failed its calibration", lines)
        self.assertIn("rule r1 (l1) verdict: PASS" + PLAIN, lines)
        # the overall rule counts the recruiter's 6 reads only
        self.assertIn("rule r3 (overall) verdict: PASS" + PLAIN, lines)
        self.assertIn("rule r3 (overall) count: score at least 7: 6 of 6 valid reads", lines)
        self.assertEqual(self.snapshot(flat), before)
        # a lens file other than the one the calibration recorded is refused, naming the lens
        other = self.place("other", fake_reader=RANK, rules=rules, calibration=self.rel("flat"))
        other.edit("hiring-manager.lens.txt", lambda text: text + "\nEdited.\n")
        self.refused(other, "the lens file differs from the calibration's: manager")
        both = self.place("both", fake_reader=RANK, rules=rules, calibration=self.rel("flat"))
        both.edit("recruiter.lens.txt", lambda text: text + "\nEdited.\n")
        both.edit("hiring-manager.lens.txt", lambda text: text + "\nEdited.\n")
        self.assertEqual(self.refused(both, "the lens file differs from the calibration's: "
                                      "recruiter"),
                         ["the lens file differs from the calibration's: recruiter",
                          "the lens file differs from the calibration's: manager"])

    def test_a_failed_calibration_is_the_reason_even_when_the_gate_fails_too(self):
        flat = self.flat()
        run = self.place("run", fake_reader=RANK_RECRUITER + FLAT_MANAGER,
                         rules=[SIX, "manager | " + SIX_PASS], calibration=self.rel("flat"))
        _result, lines = self.done(run)
        self.assertIn("anchor gate l2: failed (strong read l2/1 scored 5, below 7; strong read "
                      "l2/2 scored 5, below 7; strong read l2/3 scored 5, below 7; strong read "
                      "l2/4 scored 5, below 7; weak read l2/5 scored 5, above 4; weak read "
                      "l2/6 scored 5, above 4; weak read l2/7 scored 5, above 4; weak read "
                      "l2/8 scored 5, above 4)", lines)
        self.assertIn("lens l2: not counted (l2 failed its calibration)", lines)
        self.assertIn("rule r2 (l2) reason: l2 failed its calibration", lines)
        self.assertEqual(flat.result_names(), ["result-1.txt"])

    def test_a_lens_is_matched_to_the_calibration_by_name(self):
        flat = self.flat()
        # the lenses swap their arms: the manager is l1 here and the recruiter l2
        run = self.place("swapped", fake_reader=RANK, calibration=self.rel("flat"),
                         lenses=[LENSES[1], LENSES[0]],
                         rules=["manager | " + SIX_PASS, "recruiter | " + SIX_PASS])
        _result, lines = self.done(run)
        self.assertIn("rule r1 (l1) reason: l1 failed its calibration", lines)
        self.assertIn("rule r2 (l2) verdict: PASS" + PLAIN, lines)
        self.assertEqual(flat.result_names(), ["result-1.txt"])
        # a lens the calibration holds no hash for is refused, naming the lens
        extra = self.place("extra", fake_reader=RANK_RECRUITER, calibration=self.rel("flat"),
                           lenses=[LENSES[0], "peer | hiring-manager.lens.txt | "
                                   "author-edited-version no"])
        self.refused(extra, "the calibration recorded no hash for the lens: peer")

    def test_the_calibration_must_be_a_calibration_only_run_of_another_folder(self):
        plain = self.place("plain", fake_reader=RANK)
        self.freeze_ok(plain)
        run = self.place("run", fake_reader=RANK, calibration=self.rel("plain"))
        self.refused(run, "calibration must name a calibration-only run: ../plain/plan.txt")
        same = self.place("same", fake_reader=RANK, calibration="plan.txt.freeze")
        same.write("plan.txt.freeze", "x  y\n")
        result = same.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("calibration names a run in this folder: plan.txt.freeze",
                      result.error.splitlines())
        bad = self.place("bad", fake_reader=RANK, calibration=self.rel("plain", "plan.txt"))
        self.assertIn("calibration must name a .freeze file",
                      " ".join(bad.freeze().error.splitlines()))

    def test_a_calibration_that_changed_or_was_frozen_earlier_is_refused(self):
        flat = self.flat()
        run = self.place("run", fake_reader=RANK, calibration=self.rel("flat"))
        flat.edit("plan.txt", lambda text: text + "# edited\n")
        self.refused(run, "changed since the freeze: ../flat/plan.txt")
        old = self.place("old", calibration_only="yes", rules=None, fake_reader=RANK)
        self.freeze_ok(old)
        old.edit("plan.txt.freeze", lambda text: text.replace("revision: 4\n", ""))
        run = self.place("run2", fake_reader=RANK, calibration=self.rel("old"))
        self.refused(run, EARLIER % self.rel("old"))
        gone = self.place("gone", calibration_only="yes", rules=None, fake_reader=RANK)
        self.freeze_ok(gone)
        os.remove(gone.path("plan.txt"))
        run = self.place("run3", fake_reader=RANK, calibration=self.rel("gone"))
        self.refused(run, "the calibration plan is missing: ../gone/plan.txt")

    def test_a_run_waits_for_its_calibration_and_writes_nothing_there(self):
        waiting = self.place("waiting", calibration_only="yes", rules=None, fake_reader=RANK)
        self.freeze_ok(waiting)
        run = self.place("run", fake_reader=RANK, calibration=self.rel("waiting"))
        self.freeze_ok(run)
        before = self.snapshot(waiting)
        message = "the calibration run has not been run yet: ../waiting"
        result = run.run()
        self.assertEqual((result.exit_code, result.error.splitlines()), (2, [message]))
        self.assertEqual(self.snapshot(waiting), before)
        self.assertFalse(run.exists("reads"))
        self.assertEqual(run.result_names(), [])
        # scoring a run whose calibration lost its key names it the same way
        flat = self.flat()
        again = self.place("again", fake_reader=RANK, calibration=self.rel("flat"))
        self.done(again)
        os.remove(flat.path("key.txt"))
        before = self.snapshot(flat)
        scored = again.score()
        self.assertEqual((scored.exit_code, scored.error.splitlines()),
                         (2, ["the calibration run has not been run yet: ../flat"]))
        self.assertEqual(self.snapshot(flat), before)

    def test_the_calibration_freeze_is_one_of_the_plans_inputs(self):
        flat = self.flat()
        run = self.place("run", fake_reader=RANK, calibration=self.rel("flat"))
        self.freeze_ok(run)
        self.assertIn(self.rel("flat"), run.read("plan.txt.freeze"))
        flat.edit("plan.txt.freeze", lambda text: text + "# edited\n")
        result = run.run()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("changed since the freeze: " + self.rel("flat"),
                      result.error.splitlines())

    def test_a_calibration_from_an_earlier_revision_names_the_freeze(self):
        for key in ("amends", "calibration"):
            with self.subTest(key):
                first = self.place("first-" + key, calibration_only="yes", rules=None,
                                   fake_reader=RANK)
                self.freeze_ok(first)
                first.edit("plan.txt.freeze", lambda text: text.replace("revision: 4\n", ""))
                extra = {key: self.rel("first-" + key)}
                s = self.place("second-" + key, calibration_only="yes" if key == "amends" else None,
                               rules=None if key == "amends" else [SIX], fake_reader=RANK,
                               **extra)
                self.refused(s, EARLIER % self.rel("first-" + key))


class AmendmentCase(Runs):
    def first(self, **overrides):
        s = self.place("first", fake_reader=RANK, rules=[SIX], **overrides)
        self.freeze_ok(s)
        return s

    def amend(self, rule=None, name="second", **overrides):
        return self.place(name, fake_reader=RANK, amends=self.rel("first"),
                          rules=[rule or SIX], **overrides)

    def test_10_60_an_amendment_restates_a_count_at_the_same_share(self):
        first = self.first()
        twelve = ("recruiter | PASS if score at least 7 in 12 of 12; FAIL if score at most 4 "
                  "in 4 or more; otherwise INCONCLUSIVE")
        s = self.amend(twelve, reads_per_reader="6")
        self.freeze_ok(s)
        _result, lines = s.run(), s.result_lines()
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)
        self.assertEqual(first.result_names(), [])
        # the first count kept: refused, naming the rule
        self.refused(self.amend(name="kept", reads_per_reader="6"), AMEND + "r1")
        # a count with no whole number at the new size: five sixths of 8
        five = "recruiter | PASS if score at least 7 in 5 of 6; otherwise INCONCLUSIVE"
        first_five = self.place("five", fake_reader=RANK, rules=[five])
        self.freeze_ok(first_five)
        for text in (five, five.replace("5 of 6", "6 of 8"), five.replace("5 of 6", "7 of 8")):
            with self.subTest(text):
                s = self.place("fives", fake_reader=RANK, amends=self.rel("five"),
                               rules=[text], reads_per_reader="4")
                self.refused(s, AMEND + "r1")
                shutil.rmtree(s.folder)

    def test_a_threshold_or_a_bar_may_not_change(self):
        self.first()
        s = self.amend(anchor_strong_at_least="8")
        self.refused(s, "an amendment may not change anchor-strong-at-least from the plan it "
                     "amends")
        shutil.rmtree(s.folder)
        s = self.amend(anchor_weak_at_most="3")
        self.refused(s, "an amendment may not change anchor-weak-at-most from the plan it "
                     "amends")
        shutil.rmtree(s.folder)
        for text in (SIX.replace("at least 7", "at least 6"),
                     SIX.replace("at most 4", "at most 3"),
                     SIX.replace("PASS if", "FAIL if"),
                     SIX.replace("FAIL if", "FAIL if DOUBTS flagged in 2 or more; FAIL if"),
                     SIX + " | null-share 1/2",
                     SIX.replace("score at most 4 in 2 or more", "DOUBTS flagged in 2 or more"),
                     SIX.replace("in 6 of 6", "in 6 or more"),
                     SIX.replace("recruiter |", "manager |")):
            with self.subTest(text):
                s = self.amend(text, name="changed")
                self.refused(s, AMEND + "r1")
                shutil.rmtree(s.folder)
        s = self.amend(rule=SIX, name="more")
        s.change(rules=[SIX, OVERALL_6])
        self.refused(s, AMEND + "r2")

    def test_a_lens_file_and_the_readers_may_change_with_the_counts_kept(self):
        self.first()
        s = self.amend(readers=["r1 | fake", "r2 | fake | cost 2"])
        s.edit("recruiter.lens.txt", lambda text: text + "\nA revised lens.\n")
        self.freeze_ok(s)

    def test_the_counts_follow_the_blind_readers_and_the_lenses(self):
        # a not-blind reader plans no counted read: 2 readers, one not blind, 3 reads each
        first = self.place("first", fake_reader=RANK,
                           rules=["recruiter | PASS if score at least 7 in 3 of 3; otherwise "
                                  "INCONCLUSIVE", OVERALL_6],
                           readers=["r1 | fake", "r2 | fake | not-blind"])
        self.freeze_ok(first)
        s = self.place("second", fake_reader=RANK, amends=self.rel("first"),
                       readers=["r1 | fake", "r2 | fake | not-blind"], reads_per_reader="6",
                       rules=["recruiter | PASS if score at least 7 in 6 of 6; otherwise "
                              "INCONCLUSIVE", OVERALL_6.replace("6 of 6", "12 of 12")])
        self.freeze_ok(s)
        t = self.place("third", fake_reader=RANK, amends=self.rel("first"),
                       readers=["r1 | fake", "r2 | fake | not-blind"], reads_per_reader="6",
                       rules=["recruiter | PASS if score at least 7 in 6 of 6; otherwise "
                              "INCONCLUSIVE", OVERALL_6])
        self.refused(t, AMEND + "r2")

    def test_an_amendment_with_counts_of_many_digits_is_refused_not_crashed(self):
        big = "7" * 4400
        rule = ("recruiter | PASS if score at least 7 in %s or more; otherwise INCONCLUSIVE"
                % big)
        first = self.place("first", fake_reader=RANK, rules=[rule])
        self.freeze_ok(first)
        s = self.place("second", fake_reader=RANK, amends=self.rel("first"), rules=[rule],
                       reads_per_reader="4")
        self.refused(s, AMEND + "r1")
        kept = self.place("kept", fake_reader=RANK, amends=self.rel("first"), rules=[rule])
        self.freeze_ok(kept)

    def test_an_amendment_names_the_earlier_plan_it_cannot_use(self):
        first = self.first()
        s = self.amend()
        first.edit("plan.txt", lambda text: text + "# edited\n")
        self.refused(s, "changed since the freeze: ../first/plan.txt")
        old = self.place("old", fake_reader=RANK)
        self.freeze_ok(old)
        old.edit("plan.txt.freeze", lambda text: text.replace("revision: 4\n", ""))
        s = self.place("third", fake_reader=RANK, amends=self.rel("old"))
        self.refused(s, EARLIER % self.rel("old"))
        gone = self.place("gone", fake_reader=RANK)
        self.freeze_ok(gone)
        os.remove(gone.path("plan.txt"))
        s = self.place("fourth", fake_reader=RANK, amends=self.rel("gone"))
        self.refused(s, "the amended plan is missing: ../gone/plan.txt")


class ExtensionCase(Runs):
    def first(self, fake=None, rules=None, name="first", run=True, **overrides):
        s = self.place(name, fake_reader=RANK if fake is None else fake,
                       rules=[SIX] if rules is None else rules, **overrides)
        if run:
            result = s.frozen_run()
            self.assertEqual((result.exit_code, result.error), (0, ""))
        else:
            self.freeze_ok(s)
        return s

    def extend(self, name="second", fake=None, rules=None, first="first", **overrides):
        values = dict(fake_reader=RANK if fake is None else fake,
                      rules=[SIX] if rules is None else rules, extends=self.rel(first))
        values.update(overrides)
        return self.place(name, **values)

    def test_10_59_an_extension_changes_the_sample_size_only(self):
        first = self.first()
        s = self.extend(reads_per_reader="6")
        self.freeze_ok(s)
        before = self.snapshot(first)
        result = s.run()
        self.assertEqual((result.exit_code, result.error), (0, ""))
        lines = s.result_lines()
        first_sha = sha256_text(first.read("plan.txt.freeze"))
        at = [i for i, x in enumerate(lines) if x.startswith("prompt sha256:")][0]
        self.assertEqual(lines[at + 1], "extends: %s; the sample size changed after a result "
                         "was seen" % first_sha)
        self.assertEqual(lines[at + 2], "calibration: none; scores are uncalibrated")
        verdict = lines.index("rule r1 (l1) verdict: PASS" + TAG)
        self.assertEqual(lines[verdict + 1:verdict + 3], [
            "rule r1 (l1) at the pooled reads: PASS if score at least 7 in 18 of 18; FAIL if "
            "score at most 4 in 6 or more",
            "rule r1 (l1) extension: first run PASS, pooled PASS"])
        self.assertIn("rule r1 (l1): PASS if score at least 7 in 6 of 6; FAIL if score at most "
                      "4 in 2 or more", lines)
        self.assertIn("rule r1 (l1) count: score at least 7: 18 of 18 valid reads", lines)
        self.assertIn("rule r1 (l1) count: score at most 4: 0 of 18 valid reads", lines)
        # this run's reads are the ones shown
        self.assertIn("scores l1 version: scores=12 total=84 mean=7.00 lowest=7 highest=7",
                      lines)
        self.assertEqual(s.read("key.txt").count("\n"), 2 * (8 + 12))
        self.assertEqual(self.snapshot(first), before)
        scored = s.score()
        self.assertEqual(scored.exit_code, 0)
        self.assertEqual(self.snapshot(first), before)

    def test_10_59_a_count_with_no_whole_number_at_the_pooled_reads_is_refused(self):
        self.first()
        s = self.extend(reads_per_reader="4")
        self.refused(s, "an extension's pooled reads give no whole number for r1")

    def test_10_59_a_setting_other_than_the_sample_size_is_refused_naming_it(self):
        self.first()
        cases = (
            (dict(anchor_strong_at_least="8"), EXTEND + "anchor-strong-at-least"),
            (dict(anchor_weak_at_most="3"), EXTEND + "anchor-weak-at-most"),
            (dict(rules=[SIX.replace("at least 7", "at least 6")]), EXTEND + "rules"),
            (dict(min_valid_reads="3"), EXTEND + "min-valid-reads"),
            (dict(sidedness="greater"), EXTEND + "sidedness"),
            (dict(spend_ceiling="500"), EXTEND + "spend-ceiling"),
            (dict(read_timeout="30"), EXTEND + "read-timeout"),
            (dict(fake=RANK + ["manager | score 5 | read 14"]), EXTEND + "fake-reader"),
            (dict(lenses=[LENSES[0]], fake=RANK_RECRUITER), EXTEND + "lenses"),
            (dict(anchors=[ANCHORS[0], "weak | anchor-weak.txt | written-by unknown"]),
             EXTEND + "anchors"),
            (dict(calibration="../x/plan.txt.freeze"), EXTEND + "calibration"),
        )
        for overrides, message in cases:
            with self.subTest(message):
                s = self.extend(**overrides)
                self.refused(s, message)
                shutil.rmtree(s.folder)

    def test_10_59_a_changed_lens_file_or_document_is_refused_naming_it(self):
        self.first()
        s = self.extend(reads_per_reader="6")
        s.edit("recruiter.lens.txt", lambda text: text + "\nEdited.\n")
        s.edit("posting.txt", lambda text: text + "\nEdited.\n")
        s.edit("anchor-strong.txt", lambda text: text + "\nEdited.\n")
        error = self.refused(s, "changed since the first freeze: recruiter.lens.txt")
        self.assertIn("changed since the first freeze: posting.txt", error)
        self.assertIn("changed since the first freeze: anchor-strong.txt", error)

    def test_the_readers_are_the_same_models_in_any_number(self):
        self.first()
        # a model the first plan did not have, or a name used for another model
        for name, readers in (("new", ["r1 | fake", "r2 | fake", "r3 | fake | not-blind"]),
                              ("command", ["r1 | fake", "r2 | /usr/bin/true"]),
                              ("group", ["r1 | fake", "r2 | fake | reader-group g"])):
            with self.subTest(name):
                t = self.extend(name, readers=readers)
                self.refused(t, EXTEND + "readers")
        # the same model in another number is the sample size, as are the reads per reader
        s = self.extend(readers=["r1 | fake", "r2 | fake", "r3 | fake", "r4 | fake"])
        self.freeze_ok(s)
        self.first(name="other")
        u = self.extend("anchors", first="other", anchor_reads_per_reader="3",
                        reads_per_reader="6")
        self.freeze_ok(u)

    def test_a_fake_readers_cost_is_not_part_of_its_model(self):
        self.first()
        s = self.extend(readers=["r1 | fake", "r2 | fake | cost 5"])
        self.freeze_ok(s)
        # a live reader's cost is part of its model: the tool does not ignore it
        self.first(name="live", run=False, readers=["r1 | fake", "r2 | /usr/bin/true | cost 2"])
        t = self.extend("dearer", first="live",
                        readers=["r1 | fake", "r2 | /usr/bin/true | cost 3"])
        self.refused(t, EXTEND + "readers")
        u = self.extend("same", first="live", readers=["r1 | fake", "r2 | /usr/bin/true | cost 2"],
                        reads_per_reader="6")
        self.freeze_ok(u)

    def test_the_first_run_is_extended_once(self):
        self.first()
        one = self.extend("one", reads_per_reader="6")
        self.freeze_ok(one)
        two = self.extend("two", reads_per_reader="9")
        self.refused(two, "the first run already has an extension: one")

    def test_an_extension_is_not_extended_and_a_calibration_is_not_extended(self):
        self.first()
        one = self.extend("one", reads_per_reader="6")
        self.freeze_ok(one)
        again = self.extend("again", first="one", reads_per_reader="9")
        self.refused(again, FIRST_NAMED % "../one/plan.txt")
        cal = self.place("cal", calibration_only="yes", rules=None, fake_reader=RANK)
        self.done(cal)
        over = self.extend("over", first="cal", reads_per_reader="6")
        self.refused(over, FIRST_NAMED % "../cal/plan.txt")

    def test_an_amendment_is_not_extended(self):
        self.first()
        amended = self.place("amended", fake_reader=RANK, amends=self.rel("first"),
                             rules=[SIX])
        self.freeze_ok(amended)
        s = self.extend("over", first="amended", reads_per_reader="6")
        self.refused(s, FIRST_NAMED % "../amended/plan.txt")

    def test_an_extension_names_the_first_plan_it_cannot_use(self):
        first = self.first(run=False)
        s = self.extend(reads_per_reader="6")
        first.edit("plan.txt", lambda text: text + "# edited\n")
        self.refused(s, "changed since the freeze: ../first/plan.txt")
        old = self.first(name="old", run=False)
        old.edit("plan.txt.freeze", lambda text: text.replace("revision: 4\n", ""))
        t = self.extend("third", first="old", reads_per_reader="6")
        self.refused(t, EARLIER % self.rel("old"))

    def test_the_extension_waits_for_the_first_run_and_writes_nothing_there(self):
        first = self.first(run=False)
        s = self.extend(reads_per_reader="6")
        self.freeze_ok(s)
        before = self.snapshot(first)
        result = s.run()
        self.assertEqual((result.exit_code, result.error.splitlines()),
                         (2, ["the first run has not been run yet: ../first"]))
        self.assertEqual(self.snapshot(first), before)
        self.assertEqual(s.result_names(), [])
        # scoring an extension whose first run lost its key names it the same way
        done = self.first(name="done")
        t = self.extend("later", first="done", reads_per_reader="6")
        self.assertEqual(t.frozen_run().exit_code, 0)
        os.remove(done.path("key.txt"))
        before = self.snapshot(done)
        scored = t.score()
        self.assertEqual((scored.exit_code, scored.error.splitlines()),
                         (2, ["the first run has not been run yet: ../done"]))
        self.assertEqual(self.snapshot(done), before)

    def test_the_first_runs_verdict_is_its_own_beside_the_pooled_one(self):
        # two of the first run's version reads score 6: alone, 4 of 6 reach no PASS; pooled
        # with a 12-read extension, 16 of 18 is above 15 of 18 (five sixths)
        rule = "recruiter | PASS if score at least 7 in 5 of 6; otherwise INCONCLUSIVE"
        fake = RANK + ["recruiter | version | score 6 | read 9",
                       "recruiter | version | score 6 | read 10"]
        first = self.first(fake=fake, rules=[rule])
        alone = [x for x in first.result_lines() if x.startswith("rule r1 (l1) verdict:")]
        self.assertEqual(alone, ["rule r1 (l1) verdict: INCONCLUSIVE" + TAG])
        readers = ["r1 | fake", "r2 | fake", "r3 | fake", "r4 | fake"]
        s = self.extend(fake=fake, rules=[rule], readers=readers)
        self.freeze_ok(s)
        s.run()
        lines = s.result_lines()
        self.assertIn("rule r1 (l1) at the pooled reads: PASS if score at least 7 in 15 of 18",
                      lines)
        self.assertIn("rule r1 (l1) extension: first run INCONCLUSIVE, pooled PASS", lines)
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)
        self.assertIn("rule r1 (l1) count: score at least 7: 16 of 18 valid reads", lines)

    def test_a_fail_count_is_read_at_its_share_of_the_pooled_reads(self):
        # three of the first run's version reads score 4: alone, they meet 2 or more; pooled
        # with 18 planned reads, 2 or more is 6 or more, and 3 reads do not meet it
        fake = RANK + ["recruiter | version | score 4 | read %d" % n for n in (9, 10, 11)]
        first = self.first(fake=fake)
        alone = [x for x in first.result_lines() if x.startswith("rule r1 (l1) verdict:")]
        self.assertEqual(alone, ["rule r1 (l1) verdict: FAIL" + TAG])
        readers = ["r1 | fake", "r2 | fake", "r3 | fake", "r4 | fake"]
        s = self.extend(fake=fake, readers=readers)
        self.freeze_ok(s)
        s.run()
        lines = s.result_lines()
        self.assertIn("rule r1 (l1) at the pooled reads: PASS if score at least 7 in 18 of 18; "
                      "FAIL if score at most 4 in 6 or more", lines)
        self.assertIn("rule r1 (l1) count: score at most 4: 3 of 18 valid reads", lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE" + TAG, lines)
        self.assertIn("rule r1 (l1) extension: first run FAIL, pooled INCONCLUSIVE", lines)

    def test_the_headroom_reads_the_pooled_reads(self):
        # the first run's strong reads are 9, 9, 9, 9 and the extension's 9, 9, 9, 9, 7, 7, 7, 7
        # (its reads 5 to 8 are strong anchor reads, the first run's are weak): the pooled median
        # is 9, above the version's 8, while the extension's own median, 8, is not
        fake = [x.replace("recruiter | version | score 7", "recruiter | version | score 8")
                for x in RANK] + ["recruiter | strong | score 7 | read %d" % n
                                  for n in (5, 6, 7, 8)]
        rule = "recruiter | PASS if score at least 7 in 6 of 6; otherwise INCONCLUSIVE"
        self.first(fake=fake, rules=[rule])
        s = self.extend(fake=fake, rules=[rule],
                        readers=["r1 | fake", "r2 | fake", "r3 | fake", "r4 | fake"])
        self.freeze_ok(s)
        s.run()
        lines = s.result_lines()
        self.assertIn("anchor gate l1: passed (strong scores 9, 9, 9, 9, 9, 9, 9, 9, 7, 7, 7, "
                      "7, all at least 7; weak scores %s, all at most 4)"
                      % ", ".join(["2"] * 12), lines)
        self.assertIn("headroom l1: strong anchor median 9, version median 8", lines)
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)
        self.assertIn("rule r1 (l1) extension: first run PASS, pooled PASS", lines)

    def test_the_gate_reads_the_pooled_reads_and_the_first_run_keeps_its_own(self):
        # the extension's read 5 is a strong anchor read that scores 5; the first run's is weak
        fake = RANK + ["recruiter | strong | score 5 | read 5"]
        self.first(fake=fake)
        s = self.extend(fake=fake, readers=["r1 | fake", "r2 | fake", "r3 | fake", "r4 | fake"])
        self.freeze_ok(s)
        s.run()
        lines = s.result_lines()
        self.assertIn("anchor gate l1: failed (strong read l1/5 scored 5, below 7)", lines)
        self.assertIn("lens l1: not counted (the anchor gate failed on l1)", lines)
        self.assertIn("rule r1 (l1) reason: the anchor gate failed on l1", lines)
        self.assertIn("rule r1 (l1) extension: first run PASS, pooled INCONCLUSIVE", lines)

    def test_a_missing_read_of_the_first_run_counts_in_the_pooled_completions(self):
        # read 9 fails in the first run and in the extension: the pooled run has 16 valid reads of
        # 18 planned, and every completion of the 2 missing ones passes 15 of 18
        fake = RANK + ["recruiter | version | omit SCORE | read 9"]
        rule = "recruiter | PASS if score at least 7 in 5 of 6; otherwise INCONCLUSIVE"
        first = self.place("first", fake_reader=fake, rules=[rule], min_valid_reads="3")
        self.assertEqual(first.frozen_run().exit_code, 1)
        s = self.extend(fake=fake, rules=[rule], min_valid_reads="3", reads_per_reader="6")
        self.freeze_ok(s)
        self.assertEqual(s.run().exit_code, 1)
        lines = s.result_lines()
        # this run's missing line shows its own read; the completions count both runs' reads
        self.assertIn("missing l1 version: 1 of 12 planned reads (failed 1, not run 0)", lines)
        self.assertIn("rule r1 (l1) completions (missing reads: 2): settled: PASS", lines)
        self.assertIn("rule r1 (l1) reason: lifted from INCONCLUSIVE: settled under every "
                      "completion of 2 missing reads; read floor 3 met", lines)
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)

    def test_an_extension_with_counts_of_many_digits_is_scored(self):
        count = "6" * 4400
        rule = ("recruiter | PASS if score at least 7 in %s or more; otherwise INCONCLUSIVE"
                % count)
        self.first(rules=[rule])
        s = self.extend(rules=[rule], reads_per_reader="6")
        self.freeze_ok(s)
        result = s.run()
        self.assertEqual((result.exit_code, result.error), (0, ""))
        with panel.harness.unlimited_int_digits():
            pooled = str(int(count) * 3)
        self.assertIn("rule r1 (l1) at the pooled reads: PASS if score at least 7 in %s or more"
                      % pooled, s.result_lines())
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE" + TAG, s.result_lines())


class ExampleCase(Runs):
    def test_10_25_the_example_plan_still_freezes(self):
        s = self.place("example")
        s.write("plan.txt", EXAMPLE_PLAN)
        shutil.copyfile(s.path("version.txt"), s.path("resume.txt"))
        self.assertIn("spend-ceiling: 56", EXAMPLE_PLAN)
        result = s.freeze()
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertTrue(s.exists("plan.txt.freeze"))
        self.assertEqual(s.read("plan.txt.freeze").splitlines()[-1], "revision: 4")


if __name__ == "__main__":
    unittest.main()
