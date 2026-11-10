"""Tests for the reader panel (career_track_record.panel). All data here is invented.

Every plan in these tests is written as plan text, in the syntax of docs/specs/reader-panel.md,
and read by ``panel.parse``; a test names only the lines it changes from the default plan.
Each test builds its run folder in a fresh temporary folder from the fixtures in
tests/fixtures/panel (and the version and posting from tests/fixtures/ab); nothing is ever
written into tests/fixtures. The test numbers (10.1 and so on) are those of
docs/specs/reader-panel.md, section 10.

A "live" reader here is a stub script run by this Python, as in test_ab_live: no test starts
a reader that reaches a network or uses credentials.
"""

import hashlib
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures", "panel")
FX_AB = os.path.join(ROOT, "tests", "fixtures", "ab")
sys.path.insert(0, SRC)

from career_track_record import ab, barred, cli, panel, reader_harness  # noqa: E402
from tests.test_ab import plan_text, sha256_of  # noqa: E402
from tests.test_ab_live import stub_command  # noqa: E402
from tests.test_cli import track  # noqa: E402

PANEL_FIXTURES = ("anchor-strong.txt", "anchor-weak.txt", "recruiter.lens.txt",
                  "hiring-manager.lens.txt")
AB_FIXTURES = (("base.txt", "version.txt"), ("posting.txt", "posting.txt"))

ANCHORS = ["strong | anchor-strong.txt", "weak | anchor-weak.txt"]
LENSES = ["recruiter | recruiter.lens.txt", "manager | hiring-manager.lens.txt"]
# The control lenses: each ranks the anchors the right way round and scores the version 7.
RANK = ["recruiter | strong | score 9", "recruiter | weak | score 2",
        "recruiter | version | score 7",
        "manager | strong | score 8", "manager | weak | score 3", "manager | version | score 7"]
RANK_RECRUITER = RANK[:3]
FLAT_MANAGER = ["manager | score 5"]
SIX_PASS = ("PASS if score at least 7 in 6 of 6; FAIL if score at most 4 in 2 or more; "
            "otherwise INCONCLUSIVE")
SIX_RULE = "PASS if score at least 7 in 6 of 6; FAIL if score at most 4 in 2 or more"
VALID_REPLY = ("READ: anything\nPRIOR: nothing\nSCORE: 8\nSTRENGTHS: x\nDOUBTS: none\n"
               "UNDERSOLD: none\nOVEREXPLAINED: none\nOWNED: y\nFLAG-FIXES: none\n")


def default_values():
    """The default plan of the spec (section 10): two lenses, two fake readers with 3 version
    reads and 1 anchor read each, thresholds 7 and 4."""
    return dict(
        posting="posting.txt",
        version="version.txt",
        anchors=list(ANCHORS),
        lenses=list(LENSES),
        readers=["r1 | fake", "r2 | fake"],
        reads_per_reader="3",
        anchor_reads_per_reader="1",
        anchor_strong_at_least="7",
        anchor_weak_at_most="4",
    )


def reply_stub(**fields):
    """Source of a stub that prints a valid panel reply, with some fields replaced."""
    text = VALID_REPLY
    for label, value in fields.items():
        lines = [line for line in text.splitlines() if not line.startswith(label + ":")]
        text = "".join(line + "\n" for line in lines) + "%s: %s\n" % (label, value)
    return "import sys\nsys.stdout.write(%r)\n" % text


class Setup(object):
    """A run folder in a fresh temporary folder, holding the fixtures and a plan file written
    from the default values with keyword overrides."""

    def __init__(self, case, **overrides):
        self._tmp = tempfile.TemporaryDirectory()
        case.addCleanup(self._tmp.cleanup)
        self.case = case
        self.folder = self._tmp.name
        for name in PANEL_FIXTURES:
            shutil.copyfile(os.path.join(FX, name), os.path.join(self.folder, name))
        for source, target in AB_FIXTURES:
            shutil.copyfile(os.path.join(FX_AB, source), os.path.join(self.folder, target))
        self.plan_path = os.path.join(self.folder, "plan.txt")
        self.values = default_values()
        self.change(**overrides)

    def change(self, **overrides):
        self.values.update(overrides)
        self.write("plan.txt", plan_text(self.values))

    @property
    def plan(self):
        return panel.parse(self.plan_path)

    def line_of(self, text):
        for number, line in enumerate(self.read("plan.txt").split("\n"), 1):
            if text in line:
                return number
        raise AssertionError("not in the plan: %r" % text)

    def path(self, *names):
        return os.path.join(self.folder, *names)

    def write(self, name, text):
        with open(self.path(name), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def read(self, *names):
        with open(self.path(*names), encoding="utf-8", newline="") as handle:
            return handle.read()

    def edit(self, name, change):
        self.write(name, change(self.read(name)))

    def exists(self, *names):
        return os.path.exists(self.path(*names))

    def freeze(self):
        return panel.freeze(self.plan_path)

    def run(self, live=False):
        return panel.run(self.plan_path, live=live)

    def score(self):
        return panel.score(self.plan_path)

    def frozen_run(self, live=False):
        frozen = self.freeze()
        self.case.assertEqual(frozen.exit_code, 0, frozen.error)
        return self.run(live=live)

    def result_names(self):
        return sorted(n for n in os.listdir(self.folder) if n.startswith(panel.RESULT_STEM))

    def result_lines(self, number=1):
        return self.read("%s%d.txt" % (panel.RESULT_STEM, number)).splitlines()

    def read_folder(self, arm, number):
        return self.path(panel.READS_DIR, arm, str(number))

    def reply_count(self, arm):
        folder = self.path(panel.READS_DIR, arm)
        if not os.path.isdir(folder):
            return 0
        return len([n for n in os.listdir(folder)
                    if os.path.isfile(os.path.join(folder, n, panel.READ_REPLY))])

    def tree_hashes(self):
        found = {}
        for folder, _dirs, names in os.walk(self.folder):
            for name in names:
                path = os.path.join(folder, name)
                with open(path, "rb") as handle:
                    found[os.path.relpath(path, self.folder)] = hashlib.sha256(
                        handle.read()).hexdigest()
        return found


class GateCase(unittest.TestCase):
    """The anchor gate: the control that every verdict depends on."""

    def done(self, **overrides):
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def test_10_1_a_lens_that_ranks_the_anchors_is_counted_and_its_rule_passes(self):
        s, result, lines = self.done(fake_reader=RANK, rules=["recruiter | " + SIX_PASS])
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("anchor gate l1: passed (strong scores 9, 9, all at least 7; weak "
                      "scores 2, 2, all at most 4)", lines)
        self.assertIn("lens l1: counted", lines)
        self.assertIn("lens l2: counted", lines)
        self.assertIn("counted lenses: l1 l2", lines)
        self.assertIn("rule r1 (l1): " + SIX_RULE, lines)
        self.assertIn("rule r1 (l1) count: score at least 7: 6 of 6 valid reads", lines)
        self.assertIn("rule r1 (l1) count: score at most 4: 0 of 6 valid reads", lines)
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 reads left out]", lines)
        self.assertEqual([line for line in lines if "reason" in line], [])
        self.assertIn("read l1/5: reader=r1 document=version score=7 flagged=none flags=none",
                      lines)
        self.assertEqual(result.text, s.read("result-1.txt"))
        self.assertIn("exit status: 0", lines)

    def test_10_2_a_flat_lens_is_inconclusive_and_the_control_lens_is_counted(self):
        # The manager lens scores every document 5: it cannot tell the anchors apart, so its
        # reads of the version are reported INCONCLUSIVE and not counted. The recruiter lens
        # in the same run is the control: it ranks the anchors and is counted.
        rules = ["recruiter | " + SIX_PASS, "manager | " + SIX_PASS]
        _s, result, lines = self.done(fake_reader=RANK_RECRUITER + FLAT_MANAGER, rules=rules)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("anchor gate l2: failed (strong read l2/1 scored 5, below 7; strong "
                      "read l2/2 scored 5, below 7; weak read l2/3 scored 5, above 4; weak "
                      "read l2/4 scored 5, above 4)", lines)
        self.assertIn("lens l2: not counted (the anchor gate failed on l2)", lines)
        self.assertIn("rule r2 (l2) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertIn("rule r2 (l2) reason: the anchor gate failed on l2", lines)
        self.assertIn("rule r2 (l2) count: score at least 7: 0 of 0 valid reads", lines)
        # The version's scores under the voided lens are still shown, not counted.
        self.assertIn("scores l2 version: scores=6 total=30 mean=5.00 lowest=5 highest=5",
                      lines)
        self.assertIn("lens l1: counted", lines)
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 reads left out]", lines)
        self.assertIn("counted lenses: l1", lines)

    def test_10_3_a_lens_that_ranks_the_anchors_backwards_fails_the_gate(self):
        backwards = ["manager | strong | score 2", "manager | weak | score 9",
                     "manager | version | score 9"]
        _s, _result, lines = self.done(fake_reader=RANK_RECRUITER + backwards,
                                       rules=["manager | " + SIX_PASS])
        self.assertIn("anchor gate l2: failed (strong read l2/1 scored 2, below 7; strong "
                      "read l2/2 scored 2, below 7; weak read l2/3 scored 9, above 4; weak "
                      "read l2/4 scored 9, above 4)", lines)
        self.assertIn("rule r1 (l2) count: score at least 7: 0 of 0 valid reads", lines)
        self.assertIn("rule r1 (l2) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)

    def test_one_anchor_read_off_its_threshold_fails_the_gate(self):
        # Every anchor read must land on its side: one weak read at 5 fails the gate.
        rules = RANK + ["manager | weak | score 5 | read 4"]
        _s, _result, lines = self.done(fake_reader=rules, rules=["manager | " + SIX_PASS])
        self.assertIn("anchor gate l2: failed (weak read l2/4 scored 5, above 4)", lines)
        self.assertIn("lens l2: not counted (the anchor gate failed on l2)", lines)
        # At the threshold the gate passes: strong 7 and weak 4 are on their sides.
        edge = RANK_RECRUITER + ["manager | strong | score 7", "manager | weak | score 4",
                                 "manager | version | score 7"]
        _s, _result, lines = self.done(fake_reader=edge, rules=["manager | " + SIX_PASS])
        self.assertIn("anchor gate l2: passed (strong scores 7, 7, all at least 7; weak "
                      "scores 4, 4, all at most 4)", lines)
        self.assertIn("rule r1 (l2) verdict: PASS [not blind: 0 reads left out]", lines)

    def test_10_4_a_failed_anchor_read_leaves_the_gate_not_evaluated(self):
        rules = RANK + ["manager | omit SCORE | read 1"]
        _s, result, lines = self.done(fake_reader=rules, rules=["manager | " + SIX_PASS,
                                                                "recruiter | " + SIX_PASS])
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(), ["failed read l2/1: missing SCORE"])
        self.assertIn("read l2/1: reader=r1 document=strong FAILED (missing SCORE)", lines)
        self.assertIn("anchor gate l2: not evaluated (3 valid anchor reads of 4 planned)",
                      lines)
        self.assertIn("lens l2: not counted (the anchor gate was not evaluated on l2)", lines)
        self.assertIn("rule r1 (l2) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertIn("rule r1 (l2) reason: the anchor gate was not evaluated on l2", lines)
        self.assertIn("rule r2 (l1) verdict: PASS [not blind: 0 reads left out]", lines)
        self.assertIn("failed reads: 1", lines)

    def test_10_5_overall_rules_count_only_counted_lenses(self):
        rules = ["overall | PASS if score at least 7 in 12 of 12; otherwise INCONCLUSIVE",
                 "overall | PASS if score at least 7 in 6 or more; otherwise INCONCLUSIVE"]
        # Both lenses counted: 12 version reads, all at 7.
        _s, _result, lines = self.done(fake_reader=RANK, rules=rules)
        self.assertIn("rule r1 (overall) count: score at least 7: 12 of 12 valid reads", lines)
        self.assertIn("rule r1 (overall) verdict: PASS [not blind: 0 reads left out]", lines)
        self.assertIn("rule r2 (overall) verdict: PASS [not blind: 0 reads left out]", lines)
        # The manager lens voided: its 6 reads leave the count, so "12 of 12" cannot hold
        # and "6 or more" still does.
        _s, _result, lines = self.done(fake_reader=RANK_RECRUITER + FLAT_MANAGER, rules=rules)
        self.assertIn("rule r1 (overall) count: score at least 7: 6 of 6 valid reads", lines)
        self.assertIn("rule r1 (overall) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertIn("rule r2 (overall) verdict: PASS [not blind: 0 reads left out]", lines)
        self.assertEqual([line for line in lines if line.startswith("rule") and "reason" in
                          line], [])

    def test_10_6_no_counted_lens_makes_overall_rules_inconclusive(self):
        rules = ["overall | PASS if score at least 7 in 1 or more; otherwise INCONCLUSIVE"]
        _s, result, lines = self.done(fake_reader=["score 9"], rules=rules)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("counted lenses: none", lines)
        self.assertIn("rule r1 (overall) count: score at least 7: 0 of 0 valid reads", lines)
        self.assertIn("rule r1 (overall) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertIn("rule r1 (overall) reason: no lens is counted", lines)


class RuleCase(unittest.TestCase):
    def done(self, **overrides):
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def test_10_7_a_flagged_field_rule_counts_fields_that_say_more_than_none(self):
        rules = RANK + ['recruiter | version | write "too long" in DOUBTS | read %d' % n
                        for n in (5, 6, 7, 8)]
        rules += ['recruiter | version | write "none" in UNDERSOLD']
        plan_rules = ["recruiter | FAIL if DOUBTS flagged in 3 or more; PASS if score at "
                      "least 7 in 6 of 6; otherwise INCONCLUSIVE",
                      "recruiter | PASS if UNDERSOLD not flagged in 6 of 6; otherwise "
                      "INCONCLUSIVE",
                      "recruiter | PASS if OWNED flagged in 1 or more; otherwise INCONCLUSIVE"]
        _s, result, lines = self.done(fake_reader=rules, rules=plan_rules)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("flagged l1 version DOUBTS: 4 of 6 valid reads", lines)
        self.assertIn("flagged l1 version UNDERSOLD: 0 of 6 valid reads", lines)
        self.assertIn("flagged l1 version OWNED: 0 of 6 valid reads", lines)
        self.assertIn("read l1/5: reader=r1 document=version score=7 flagged=DOUBTS "
                      "flags=none", lines)
        self.assertIn("rule r1 (l1) count: DOUBTS flagged: 4 of 6 valid reads", lines)
        self.assertIn("rule r1 (l1) verdict: FAIL [not blind: 0 reads left out]", lines)
        self.assertIn("rule r2 (l1) count: UNDERSOLD not flagged: 6 of 6 valid reads", lines)
        self.assertIn("rule r2 (l1) verdict: PASS [not blind: 0 reads left out]", lines)
        self.assertIn("rule r3 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)

    def test_10_22_the_first_clause_that_holds_decides(self):
        pass_first = ("PASS if score at least 7 in 3 or more; FAIL if score at least 7 in "
                      "2 or more; otherwise INCONCLUSIVE")
        fail_first = ("FAIL if score at least 7 in 2 or more; PASS if score at least 7 in "
                      "3 or more; otherwise INCONCLUSIVE")
        _s, _result, lines = self.done(fake_reader=RANK, rules=["recruiter | " + pass_first,
                                                                "recruiter | " + fail_first])
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 reads left out]", lines)
        self.assertIn("rule r2 (l1) verdict: FAIL [not blind: 0 reads left out]", lines)

    def test_k_of_m_needs_exactly_m_valid_reads(self):
        five_of_six = "PASS if score at least 7 in 5 of 6; otherwise INCONCLUSIVE"
        rules = RANK + ["recruiter | version | omit SCORE | read 5"]
        _s, result, lines = self.done(fake_reader=rules, rules=["recruiter | " + five_of_six])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("rule r1 (l1) count: score at least 7: 5 of 5 valid reads", lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        _s, _result, lines = self.done(fake_reader=RANK, rules=["recruiter | " + five_of_six])
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 reads left out]", lines)

    def test_at_most_and_a_failing_version(self):
        low = RANK_RECRUITER[:2] + ["recruiter | version | score 3"]
        _s, _result, lines = self.done(fake_reader=low, rules=["recruiter | " + SIX_PASS])
        self.assertIn("rule r1 (l1) count: score at most 4: 6 of 6 valid reads", lines)
        self.assertIn("rule r1 (l1) verdict: FAIL [not blind: 0 reads left out]", lines)
        self.assertIn("scores l1 version: scores=6 total=18 mean=3.00 lowest=3 highest=3",
                      lines)


class ReadsCase(unittest.TestCase):
    def test_10_8_a_read_folder_holds_the_document_posting_lens_and_prompt(self):
        s = Setup(self, fake_reader=RANK)
        self.assertEqual(s.frozen_run().exit_code, 0)
        for arm, number, document, lens in (("l1", 1, "anchor-strong.txt", "recruiter.lens.txt"),
                                            ("l1", 3, "anchor-weak.txt", "recruiter.lens.txt"),
                                            ("l2", 5, "version.txt", "hiring-manager.lens.txt")):
            folder = s.read_folder(arm, number)
            self.assertEqual(sorted(os.listdir(folder)),
                             ["DOCUMENT.txt", "LENS.txt", "POSTING.txt", "PROMPT.txt",
                              "REPLY.txt"])
            for name, expected in (("DOCUMENT.txt", s.read(document)),
                                   ("LENS.txt", s.read(lens)),
                                   ("POSTING.txt", s.read("posting.txt")),
                                   ("PROMPT.txt", panel.PROMPT)):
                with open(os.path.join(folder, name), encoding="utf-8", newline="") as handle:
                    self.assertEqual(handle.read(), expected, (arm, number, name))
        rows = [line.split("\t") for line in s.read(panel.KEY_FILE).splitlines()]
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0], ["l1/1", "r1", "strong"])
        self.assertEqual(rows[3], ["l1/4", "r2", "weak"])
        self.assertEqual(rows[4], ["l1/5", "r1", "version"])
        self.assertEqual(rows[9], ["l1/10", "r2", "version"])
        self.assertEqual(rows[10], ["l2/1", "r1", "strong"])
        self.assertIn("key l2/5: reader=r1 document=version", s.result_lines())

    def test_10_18_read_counts_follow_the_plan(self):
        s = Setup(self, readers=["r1 | fake"], reads_per_reader="2",
                  anchor_reads_per_reader="2", lenses=LENSES[:1])
        self.assertEqual(s.frozen_run().exit_code, 0)
        rows = [line.split("\t") for line in s.read(panel.KEY_FILE).splitlines()]
        self.assertEqual([row[2] for row in rows],
                         ["strong", "strong", "weak", "weak", "version", "version"])
        self.assertEqual([row[0] for row in rows], ["l1/%d" % n for n in range(1, 7)])
        lines = s.result_lines()
        self.assertIn("reads l1 strong: valid=2 of 2 planned", lines)
        self.assertIn("reads all readers l1 version: valid=2 of 2 planned", lines)
        self.assertIn("anchor gate l1: failed (strong read l1/1 scored 5, below 7; strong "
                      "read l1/2 scored 5, below 7; weak read l1/3 scored 5, above 4; weak "
                      "read l1/4 scored 5, above 4)", lines)

    def test_the_anchors_of_a_lens_run_before_its_version(self):
        s = Setup(self, fake_reader=RANK)
        self.assertEqual(s.freeze().exit_code, 0)
        seen = []
        real = panel.fake_reply

        def watching(read, rules, text):
            seen.append((read.id, read.document, s.exists(panel.KEY_FILE)))
            return real(read, rules, text)

        with mock.patch.object(panel, "fake_reply", watching):
            self.assertEqual(s.run().exit_code, 0)
        self.assertEqual([d for _i, d, _k in seen[:10]],
                         ["strong", "strong", "weak", "weak"] + ["version"] * 6)
        self.assertEqual([i for i, _d, _k in seen[10:13]], ["l2/1", "l2/2", "l2/3"])
        self.assertTrue(all(key for _i, _d, key in seen))

    def test_10_12_the_spend_ceiling_cuts_between_reads_after_the_anchors(self):
        s = Setup(self, fake_reader=RANK, spend_ceiling="6",
                  rules=["recruiter | " + SIX_PASS, "manager | " + SIX_PASS])
        result = s.frozen_run()
        self.assertEqual(result.exit_code, 1)
        self.assertEqual((s.reply_count("l1"), s.reply_count("l2")), (6, 0))
        self.assertEqual(s.read(panel.RUN_LOG).splitlines(), [
            "planned reads: 20", "reads run: 6", "spend: 6", "spend ceiling: 6", "cut: yes",
            "key sha256: " + sha256_of(s.path(panel.KEY_FILE))])
        lines = s.result_lines()
        self.assertIn("cut: ran 6 of 20 planned reads at spend ceiling 6", lines)
        self.assertIn("anchor gate l1: passed (strong scores 9, 9, all at least 7; weak "
                      "scores 2, 2, all at most 4)", lines)
        self.assertIn("rule r1 (l1) count: score at least 7: 2 of 2 valid reads", lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertIn("read l1/7: reader=r1 document=version not run", lines)
        self.assertIn("anchor gate l2: not evaluated (0 valid anchor reads of 4 planned)",
                      lines)
        self.assertIn("rule r2 (l2) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertIn("exit status: 1", lines)

    def test_10_15_the_fake_reader_can_score_by_the_document_text(self):
        # A blind rule: the score follows the text, not the key. "Brightmoor" is only in the
        # strong anchor, "synergy" only in the weak one.
        blind = ['score containing "Brightmoor" 9', 'score containing "synergy" 1',
                 'score containing "Glimmerpine" 8']
        s = Setup(self, fake_reader=blind, rules=["recruiter | " + SIX_PASS])
        self.assertEqual(s.frozen_run().exit_code, 0)
        lines = s.result_lines()
        self.assertIn("anchor gate l1: passed (strong scores 9, 9, all at least 7; weak "
                      "scores 1, 1, all at most 4)", lines)
        self.assertIn("scores l1 version: scores=6 total=48 mean=8.00 lowest=8 highest=8",
                      lines)
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 reads left out]", lines)
        # A rule whose text is in no document leaves the default score of 5.
        t = Setup(self, fake_reader=['score containing "no such text" 9'])
        self.assertEqual(t.frozen_run().exit_code, 0)
        self.assertTrue(all("score=5" in line for line in t.result_lines()
                            if line.startswith("read ")))

    def test_10_21_not_blind_reads_are_flagged_and_counted_separately(self):
        s = Setup(self, readers=["r1 | fake | not-blind", "r2 | fake"], fake_reader=RANK)
        self.assertEqual(s.frozen_run().exit_code, 0)
        lines = s.result_lines()
        self.assertIn("read l1/5: reader=r1 document=version score=7 flagged=none "
                      "flags=not-blind reader", lines)
        self.assertIn("read l1/8: reader=r2 document=version score=7 flagged=none flags=none",
                      lines)
        self.assertIn("reads blind readers l1 version: valid=3 of 3 planned", lines)
        self.assertIn("reads not-blind readers l1 version: valid=3", lines)
        self.assertFalse([x for x in lines if x.startswith("scores l1 reader r1 ")])

    def test_10_23_the_fake_reader_starts_no_program(self):
        s = Setup(self, fake_reader=RANK)
        self.assertEqual(s.freeze().exit_code, 0)
        with mock.patch("career_track_record.ab_reader_command.run_reader_command",
                        side_effect=AssertionError("a program was started")):
            self.assertEqual(s.run().exit_code, 0)

    def test_10_14_scoring_twice_keeps_the_first_result(self):
        s = Setup(self, fake_reader=RANK, rules=["recruiter | " + SIX_PASS])
        self.assertEqual(s.frozen_run().exit_code, 0)
        first = s.read("result-1.txt")
        self.assertEqual(s.score().exit_code, 0)
        self.assertEqual(s.result_names(), ["result-1.txt", "result-2.txt"])
        self.assertEqual(s.read("result-1.txt"), first)
        self.assertEqual(s.read("result-2.txt"), first)

    def test_scoring_reads_the_replies_not_the_fake_rules(self):
        s = Setup(self, fake_reader=RANK, rules=["recruiter | " + SIX_PASS])
        self.assertEqual(s.frozen_run().exit_code, 0)
        with open(os.path.join(s.read_folder("l1", 5), panel.READ_REPLY), "w",
                  encoding="utf-8") as handle:
            handle.write("READ: l1/5\nSCORE: 2\nDOUBTS: thin\n")
        self.assertEqual(s.score().exit_code, 0)
        later = s.result_lines(2)
        self.assertIn("read l1/5: reader=r1 document=version score=2 flagged=DOUBTS "
                      "flags=PRIOR missing", later)
        self.assertIn("rule r1 (l1) count: score at least 7: 5 of 6 valid reads", later)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]", later)

    def test_10_24_a_second_run_is_refused_and_a_run_needs_a_freeze(self):
        s = Setup(self, fake_reader=RANK)
        for call in (s.run, s.score):
            result = call()
            self.assertEqual(result.exit_code, 2)
            self.assertIn("no freeze file: plan.txt.freeze", result.error.splitlines())
        self.assertEqual(s.frozen_run().exit_code, 0)
        again = s.run()
        self.assertEqual(again.exit_code, 2)
        self.assertEqual(again.error.splitlines(), [
            "the run folder already holds a run: reads",
            "the run folder already holds a run: key.txt",
            "the run folder already holds a run: run-log.txt"])


class FreezeCase(unittest.TestCase):
    def test_10_9_freeze_hashes_every_input_and_a_changed_lens_stops_the_run(self):
        s = Setup(self)
        result = s.freeze()
        self.assertEqual((result.exit_code, result.ran, result.error), (0, True, ""))
        self.assertEqual(result.text, "freeze written: plan.txt.freeze\n")
        expected = ["%s  %s" % (sha256_of(s.path(name)), name) for name in (
            "plan.txt", "posting.txt", "version.txt", "anchor-strong.txt", "anchor-weak.txt",
            "recruiter.lens.txt", "hiring-manager.lens.txt")]
        expected.append("%s  %s" % (panel.prompt_sha256(), panel.PROMPT_LABEL))
        self.assertEqual(s.read("plan.txt.freeze").splitlines(), expected)
        self.assertNotEqual(panel.prompt_sha256(), ab.prompt_sha256())
        s.edit("recruiter.lens.txt", lambda text: text + "Be kind.\n")
        ran = s.run()
        self.assertEqual(ran.exit_code, 2)
        self.assertEqual(ran.error.splitlines(),
                         ["changed since the freeze: recruiter.lens.txt"])
        self.assertFalse(s.exists(panel.READS_DIR))
        self.assertFalse(s.exists(panel.KEY_FILE))

    def test_every_changed_file_is_named(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        s.write("plan.txt", "# edited\n")
        s.edit("anchor-weak.txt", lambda text: text + " \n")
        s.edit("version.txt", lambda text: text + " \n")
        self.assertEqual(s.run().error.splitlines(), [
            "changed since the freeze: plan.txt", "changed since the freeze: version.txt",
            "changed since the freeze: anchor-weak.txt"])

    def test_freeze_refuses_a_missing_input_a_freeze_or_a_reply(self):
        s = Setup(self)
        os.remove(s.path("hiring-manager.lens.txt"))
        result = s.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["missing input: hiring-manager.lens.txt"])
        self.assertFalse(s.exists("plan.txt.freeze"))
        t = Setup(self, fake_reader=RANK)
        self.assertEqual(t.frozen_run().exit_code, 0)
        again = t.freeze()
        self.assertEqual(again.exit_code, 2)
        self.assertEqual(again.error.splitlines()[0],
                         "a freeze file already exists: plan.txt.freeze")
        self.assertIn("the run folder already holds a reply: reads/l1/1/REPLY.txt",
                      again.error.splitlines())

    def test_a_prompt_that_differs_from_the_frozen_one_exits_2(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        with mock.patch.object(panel, "PROMPT", panel.PROMPT + "One more line.\n"):
            result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["changed since the freeze: PROMPT.txt (built into the tool)"])

    def test_10_19_an_amendment_names_both_freezes(self):
        first = Setup(self, fake_reader=RANK)
        self.assertEqual(first.frozen_run().exit_code, 0)
        first_hashes = first.tree_hashes()
        first_freeze = sha256_of(first.path("plan.txt.freeze"))
        second = Setup(self, fake_reader=RANK, amends=first.path("plan.txt.freeze"))
        self.assertEqual(second.freeze().exit_code, 0)
        self.assertEqual(second.run().exit_code, 0)
        second_freeze = sha256_of(second.path("plan.txt.freeze"))
        lines = second.result_lines()
        self.assertIn("freeze sha256: " + second_freeze, lines)
        self.assertIn("amended freeze sha256: " + first_freeze, lines)
        self.assertEqual(first.tree_hashes(), first_hashes)

    def test_10_10_documents_that_do_not_differ_stop_the_run_before_reading(self):
        s = Setup(self, anchors=["strong | anchor-strong.txt", "weak | anchor-strong.txt"])
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "the strong anchor and the weak show no changed line; the gate needs documents "
            "that differ"])
        self.assertFalse(s.exists(panel.READS_DIR))
        self.assertFalse(s.exists(panel.KEY_FILE))
        # The version under test must differ from both anchors too, even by only its text.
        t = Setup(self, version="padded.txt")
        t.write("padded.txt", "\n\n".join(t.read("anchor-weak.txt").split("\n")))
        self.assertEqual(t.freeze().exit_code, 0)
        result = t.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "the weak anchor and the version show no changed line; the gate needs documents "
            "that differ"])

    def test_an_unreadable_document_or_blank_lens_is_named(self):
        s = Setup(self)
        with open(s.path("anchor-weak.txt"), "wb") as handle:
            handle.write(b"\xff\xfe not text\n")
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["cannot read anchor-weak.txt: not valid UTF-8"])
        t = Setup(self)
        t.write("recruiter.lens.txt", "  \n\n")
        self.assertEqual(t.freeze().exit_code, 0)
        result = t.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["cannot read recruiter.lens.txt: the lens file is blank"])
        self.assertFalse(t.exists(panel.READS_DIR))


EXAMPLE_PLAN = """\
posting: posting.txt
version: resume.txt
anchors:
  strong | anchor-strong.txt
  weak | anchor-weak.txt
lenses:
  recruiter | recruiter.lens.txt
  hiring-manager | hiring-manager.lens.txt
readers:
  reader-1 | fake
  reader-2 | /path/to/my-reader.sh --model small | not-blind | cost 3
reads-per-reader: 3
anchor-reads-per-reader: 1
anchor-strong-at-least: 7
anchor-weak-at-most: 4
rules:
  recruiter | PASS if score at least 7 in 5 of 6; FAIL if score at most 4 in 2 or more; otherwise INCONCLUSIVE
  hiring-manager | FAIL if DOUBTS flagged in 3 or more; PASS if score at least 7 in 5 of 6; otherwise INCONCLUSIVE
  overall | PASS if score at least 7 in 10 or more; otherwise INCONCLUSIVE
spend-ceiling: 40
fake-reader:
  strong | score 9
  weak | score 2
  version | score 7
  hiring-manager | version | write "no numbers" in DOUBTS | read 5
"""


class PlanFileCase(unittest.TestCase):
    def assertRefused(self, s, line_text, message):
        result = s.freeze()
        self.assertEqual(result.exit_code, 2, result.error)
        self.assertFalse(result.ran)
        number = s.line_of(line_text)
        self.assertIn("plan line %d: %s" % (number, message), result.error.splitlines())
        self.assertFalse(s.exists("plan.txt.freeze"))

    def test_10_25_the_example_of_the_spec_is_read_as_written(self):
        plan = panel.parse_text(EXAMPLE_PLAN)
        self.assertEqual((plan.posting, plan.version), ("posting.txt", "resume.txt"))
        self.assertEqual(plan.anchors, {"strong": "anchor-strong.txt",
                                        "weak": "anchor-weak.txt"})
        self.assertEqual([(lens.name, lens.path, lens.arm) for lens in plan.lenses],
                         [("recruiter", "recruiter.lens.txt", "l1"),
                          ("hiring-manager", "hiring-manager.lens.txt", "l2")])
        self.assertEqual([(r.name, r.command, r.not_blind, r.cost, r.kind)
                          for r in plan.readers],
                         [("reader-1", "fake", False, 1, "fake"),
                          ("reader-2", "/path/to/my-reader.sh --model small", True, 3, "live")])
        self.assertEqual((plan.reads_per_reader, plan.anchor_reads_per_reader,
                          plan.strong_at_least, plan.weak_at_most, plan.spend_ceiling,
                          plan.read_timeout, plan.amends), (3, 1, 7, 4, 40, 600, None))
        self.assertEqual(plan.reads_per_lens(), 10)
        rules = plan.rules
        self.assertEqual([(r.name, r.lens) for r in rules],
                         [("r1", "l1"), ("r2", "l2"), ("r3", None)])
        self.assertEqual([(kind, c.kind, c.threshold, c.field, c.k, c.n)
                          for kind, c in rules[0].clauses],
                         [("PASS", "at least", 7, None, 5, 6), ("FAIL", "at most", 4, None, 2,
                                                                None)])
        self.assertEqual([(kind, c.kind, c.field, c.k, c.n) for kind, c in rules[1].clauses],
                         [("FAIL", "flagged", "DOUBTS", 3, None),
                          ("PASS", "at least", None, 5, 6)])
        self.assertEqual([(r.kind, r.score, r.lenses, r.documents, r.on_reads)
                          for r in plan.fake_rules[:3]],
                         [("score", 9, None, frozenset(["strong"]), None),
                          ("score", 2, None, frozenset(["weak"]), None),
                          ("score", 7, None, frozenset(["version"]), None)])
        last = plan.fake_rules[3]
        self.assertEqual((last.kind, last.field, last.text, last.lenses, last.documents,
                          last.on_reads),
                         ("write", "DOUBTS", "no numbers", frozenset(["l2"]),
                          frozenset(["version"]), frozenset([5])))

    def test_defaults(self):
        plan = panel.parse_text(
            "posting: p.txt\nversion: v.txt\nanchors:\n  strong | s.txt\n  weak | w.txt\n"
            "lenses:\n  one | one.txt\nreaders:\n  r | fake\nanchor-strong-at-least: 8\n"
            "anchor-weak-at-most: 3\n")
        self.assertEqual((plan.reads_per_reader, plan.anchor_reads_per_reader,
                          plan.spend_ceiling, plan.read_timeout, plan.amends,
                          plan.rules, plan.fake_rules), (3, 1, None, 600, None, [], []))
        self.assertEqual(plan.reads_per_lens(), 5)

    def test_a_plan_that_names_nothing_lists_every_gap(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "plan.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# nothing\n")
        self.assertEqual(panel.freeze(path).error.splitlines(), [
            "the plan names no posting", "the plan names no version",
            "the plan names no strong anchor", "the plan names no weak anchor",
            "the plan names no lens", "the plan has no reader",
            "the plan sets no anchor-strong-at-least", "the plan sets no anchor-weak-at-most"])

    def test_10_13_every_plan_error_is_found_by_freeze_with_its_line(self):
        cases = [
            (dict(anchor_strong_at_least="4"), "anchor-strong-at-least",
             "anchor-strong-at-least must be greater than anchor-weak-at-most"),
            (dict(anchor_strong_at_least="high"), "anchor-strong-at-least",
             "anchor-strong-at-least must be a whole number"),
            (dict(anchor_weak_at_most="4.5"), "anchor-weak-at-most",
             "anchor-weak-at-most must be a whole number"),
            (dict(anchors=["strong | a.txt", "middling | b.txt"]), "middling",
             "an anchor is written: strong | file, or weak | file"),
            (dict(anchors=ANCHORS + ["weak | other.txt"]), "weak | other.txt",
             "the anchor weak is named twice"),
            (dict(lenses=["strong | x.txt"]), "strong | x.txt",
             "a lens may not be named strong"),
            (dict(lenses=["overall | x.txt"]), "overall | x.txt",
             "a lens may not be named overall"),
            (dict(lenses=LENSES + ["recruiter | again.txt"]), "again.txt",
             "the lens recruiter is named twice"),
            (dict(lenses=["bad name | x.txt"]), "bad name",
             "a name holds letters, digits and - only: bad name"),
            (dict(lenses=["one | two | three"]), "one | two", "a lens is written: name | file"),
            (dict(rules=["nobody | " + SIX_PASS]), "nobody",
             "a rule is written: <lens> | <rule>, or overall | <rule>, with the lens "
             "written as in lenses"),
            (dict(rules=[SIX_PASS]), "PASS if",
             "a rule is written: <lens> | <rule>, or overall | <rule>, with the lens "
             "written as in lenses"),
            (dict(rules=["recruiter | PASS if score at least 7 in 6 of 6"]), "6 of 6",
             "a rule ends with: otherwise INCONCLUSIVE"),
            (dict(rules=["recruiter | otherwise INCONCLUSIVE"]), "otherwise",
             "a rule needs at least one PASS or FAIL clause"),
            (dict(rules=["recruiter | PASS if score at least 7 in 7 of 6; otherwise "
                         "INCONCLUSIVE"]), "7 of 6", "7 of 6 asks for more reads than it counts"),
            (dict(rules=["recruiter | PASS if PRIOR flagged in 1 or more; otherwise "
                         "INCONCLUSIVE"]), "PRIOR flagged",
             "not a reply field a rule can test: PRIOR"),
            (dict(rules=["recruiter | SUPPORTED if score at least 7 in 6 of 6; otherwise "
                         "INCONCLUSIVE"]), "SUPPORTED",
             "a clause is written: PASS (or FAIL) if score at least (or at most) <n> in "
             "<k> of <m> (or <k> or more), or <FIELD> flagged (or not flagged) in <k> of "
             "<m> (or <k> or more): SUPPORTED if score at least 7 in 6 of 6"),
            (dict(fake_reader=["score nine"]), "score nine", "not a fake-reader rule: "
             "score nine"),
            (dict(fake_reader=["score 9 | strongly"]), "strongly",
             "after the rule comes [| read <k>]: strongly"),
            (dict(fake_reader=["score 9 | read 11"]), "read 11",
             "read 11 is outside the arm's reads (1 to 10)"),
            (dict(fake_reader=["recruiter | middling | score 9"]), "middling",
             "after the rule comes [| read <k>]: score 9"),
            (dict(fake_reader=['write "x" in NOPE']), "NOPE", "not a reply field: NOPE"),
            (dict(fake_reader=["omit NOPE"]), "omit NOPE", "not a reply field: NOPE"),
            (dict(readers=["r1 | python3 stub.py"], fake_reader=["score 9"]), "score 9",
             "fake-reader rules, but the plan has no fake reader"),
            (dict(reads_per_reader="0"), "reads-per-reader",
             "reads-per-reader must be a positive whole number"),
            (dict(anchor_reads_per_reader="0"), "anchor-reads-per-reader",
             "anchor-reads-per-reader must be a positive whole number"),
            (dict(colour="blue"), "colour", "unknown key colour"),
        ]
        for overrides, text, message in cases:
            with self.subTest(message):
                s = Setup(self, **overrides)
                self.assertRefused(s, text, message)

    def test_a_pass_bar_above_the_strong_threshold_is_refused_by_freeze(self):
        # The gate showed a lens can give a score of at least anchor-strong-at-least (7) and
        # no more, so a version cannot be required to beat that.
        def rule(n, verdict="PASS"):
            return ["recruiter | %s if score at least %d in 6 of 6; otherwise INCONCLUSIVE"
                    % (verdict, n)]

        s = Setup(self, rules=rule(8))
        self.assertRefused(s, "at least 8",
                           "a PASS clause asks for score at least 8, above "
                           "anchor-strong-at-least (7): a version cannot be required to beat "
                           "a score the gate did not show the lens can give")
        s = Setup(self, rules=["overall | PASS if score at least 9 in 10 or more; "
                               "otherwise INCONCLUSIVE"])
        self.assertRefused(s, "at least 9",
                           "a PASS clause asks for score at least 9, above "
                           "anchor-strong-at-least (7): a version cannot be required to beat "
                           "a score the gate did not show the lens can give")
        for n in (7, 6):
            with self.subTest(n):
                self.assertEqual(Setup(self, rules=rule(n)).freeze().exit_code, 0)
        # Only a PASS bar is held to the gate; a FAIL clause may sit anywhere.
        self.assertEqual(Setup(self, rules=rule(9, "FAIL")).freeze().exit_code, 0)

    def test_the_lens_owns_its_scale(self):
        # A lens that scores five criteria 0 to 2 and sums them gives 0 to 10; a 0 is a score.
        s = Setup(self, anchor_strong_at_least="8", anchor_weak_at_most="1",
                  fake_reader=["strong | score 10", "weak | score 0", "version | score 7"],
                  rules=["recruiter | PASS if score at least 7 in 6 of 6; otherwise "
                         "INCONCLUSIVE"])
        s.write("recruiter.lens.txt", "Your role: a recruiter. Score five criteria from 0 "
                "to 2 each and reply with their sum, 0 to 10.\n")
        self.assertEqual(s.frozen_run().exit_code, 0)
        lines = s.result_lines()
        self.assertIn("anchor gate l1: passed (strong scores 10, 10, all at least 8; weak "
                      "scores 0, 0, all at most 1)", lines)
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 reads left out]", lines)
        self.assertEqual(panel.parse_reply(reply_text(SCORE="0")).score, 0)
        self.assertIsNone(panel.parse_reply(reply_text(SCORE="0")).failure)

    def test_the_built_in_prompt_fixes_no_scale(self):
        self.assertIsNone(re.search(r"[0-9]+\s*(to|-|\u2013)\s*[0-9]+", panel.PROMPT))
        score_line = [x for x in panel.PROMPT.splitlines() if x.startswith("SCORE:")]
        self.assertEqual(len(score_line), 1)
        self.assertIsNone(re.search("[0-9]", score_line[0]))

    def test_the_frozen_prompt_tells_each_free_text_field_to_write_none(self):
        sentence = "write exactly `none` if you have nothing material"
        self.assertEqual(panel.PROMPT.count(sentence), len(panel.FREE_TEXT_FIELDS))
        for field in panel.FREE_TEXT_FIELDS:
            line = [x for x in panel.PROMPT.splitlines() if x.startswith(field + ":")]
            self.assertEqual(len(line), 1, field)
            self.assertEqual(line[0].count(sentence), 1, field)
        # It is part of the frozen prompt: a change to it changes the prompt's hash.
        before = panel.prompt_sha256()
        with mock.patch.object(panel, "PROMPT", panel.PROMPT.replace(sentence, "x")):
            self.assertNotEqual(panel.prompt_sha256(), before)

    def test_negative_thresholds_and_scores_are_allowed(self):
        s = Setup(self, anchor_strong_at_least="0", anchor_weak_at_most="-5",
                  fake_reader=["strong | score 0", "weak | score -5", "version | score -1"],
                  rules=["recruiter | PASS if score at least -1 in 6 of 6; otherwise "
                         "INCONCLUSIVE"])
        self.assertEqual(s.frozen_run().exit_code, 0)
        self.assertIn("anchor gate l1: passed (strong scores 0, 0, all at least 0; weak "
                      "scores -5, -5, all at most -5)", s.result_lines())
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 reads left out]", s.result_lines())


def reply_text(**changes):
    fields = [("READ", "l1/1"), ("PRIOR", "nothing"), ("SCORE", "7"), ("STRENGTHS", "x"),
              ("DOUBTS", "none"), ("UNDERSOLD", "none"), ("OVEREXPLAINED", "none"),
              ("OWNED", "none"), ("FLAG-FIXES", "none")]
    out = []
    for label, value in fields:
        key = label.replace("-", "_")
        if key in changes:
            value = changes[key]
        if value is not None:
            out.append("%s: %s\n" % (label, value))
    return "".join(out)


class ReplyParserCase(unittest.TestCase):
    def test_10_16_a_good_reply(self):
        reply = panel.parse_reply(reply_text(DOUBTS="thin on numbers"))
        self.assertIsNone(reply.failure)
        self.assertEqual((reply.read_id, reply.score), ("l1/1", 7))
        self.assertEqual(reply.flagged, ("STRENGTHS", "DOUBTS"))
        self.assertIsNone(reply.prior_flag)

    def test_10_16_the_read_value_is_not_checked(self):
        for value in ("l1/1", "anything at all", "", "7"):
            with self.subTest(value):
                self.assertIsNone(panel.parse_reply(reply_text(READ=value)).failure)

    def test_10_16_a_missing_or_non_integer_score_is_a_failed_read(self):
        self.assertEqual(panel.parse_reply(reply_text(SCORE=None)).failure, "missing SCORE")
        self.assertEqual(panel.parse_reply(reply_text(READ=None)).failure, "missing READ")
        for value in ("7.5", "seven", "", "7/10", "+7", "7 points"):
            with self.subTest(value):
                self.assertEqual(panel.parse_reply(reply_text(SCORE=value)).failure,
                                 "SCORE is not an integer")
        for value in ("0", "11", "-3", "1000"):
            with self.subTest(value):
                self.assertEqual(panel.parse_reply(reply_text(SCORE=value)).score, int(value))

    def test_10_16_a_field_is_flagged_unless_it_is_none_or_absent(self):
        for value, flagged in (("none", False), ("", False), (None, False), ("None", True),
                               ("none.", True), ("nothing", True), ("  none  ", False),
                               ("none\nmore", True)):
            with self.subTest(repr(value)):
                reply = panel.parse_reply(reply_text(STRENGTHS="none", OWNED=value))
                self.assertEqual("OWNED" in reply.flagged, flagged)

    def test_a_field_that_appears_twice_is_a_failed_read(self):
        for label in panel.LABELS:
            with self.subTest(label):
                reply = panel.parse_reply(reply_text() + "%s: again\n" % label)
                self.assertEqual(reply.failure, "%s appears twice" % label)

    def test_prior_is_unflagged_only_when_exactly_nothing(self):
        self.assertIsNone(panel.parse_reply(reply_text(PRIOR="nothing")).prior_flag)
        self.assertEqual(panel.parse_reply(reply_text(PRIOR="a colleague")).prior_flag,
                         "PRIOR is not nothing: a colleague")
        self.assertEqual(panel.parse_reply(reply_text(PRIOR=None)).prior_flag, "PRIOR missing")

    def test_a_prior_other_than_nothing_is_flagged_in_the_result(self):
        s = Setup(self, fake_reader=RANK + ['recruiter | version | write "a former colleague" '
                                            'in PRIOR | read 6'])
        self.assertEqual(s.frozen_run().exit_code, 0)
        self.assertIn("read l1/6: reader=r1 document=version score=7 flagged=none "
                      "flags=PRIOR is not nothing: a former colleague", s.result_lines())

    def test_a_label_inside_a_line_does_not_start_a_field(self):
        reply = panel.parse_reply(reply_text(DOUBTS="see OWNED: below\n  OWNED: indented"))
        self.assertEqual(reply.fields["DOUBTS"], "see OWNED: below\n  OWNED: indented")
        self.assertEqual(reply.fields["OWNED"], "none")


class FakeReaderCase(unittest.TestCase):
    def read(self, arm="l1", number=5, document="version"):
        return panel.PlannedRead(arm, number, "r1", document)

    def test_the_rules(self):
        reply = panel.parse_reply(panel.fake_reply(self.read(), [], "text"))
        self.assertIsNone(reply.failure)
        self.assertEqual((reply.score, reply.flagged, reply.fields["PRIOR"]),
                         (5, (), "nothing"))
        rules = [panel.FakeRule.score_of(9, documents=["strong"]),
                 panel.FakeRule.score_of(2, documents=["weak"]),
                 panel.FakeRule.score_containing("marker", 8, lenses=["l2"])]
        got = [panel.parse_reply(panel.fake_reply(read, rules, text)).score
               for read, text in ((self.read(document="strong"), "x"),
                                  (self.read(document="weak"), "x"),
                                  (self.read(), "x"),
                                  (self.read("l2"), "a marker here"),
                                  (self.read("l2"), "no"),
                                  (self.read("l1"), "a marker here"))]
        self.assertEqual(got, [9, 2, 5, 8, 5, 5])

    def test_the_last_score_rule_that_fires_wins(self):
        rules = [panel.FakeRule.score_of(1), panel.FakeRule.score_of(3),
                 panel.FakeRule.score_of(7, on_reads=[2])]
        self.assertEqual(panel.parse_reply(panel.fake_reply(self.read(), rules, "x")).score, 3)
        self.assertEqual(panel.parse_reply(panel.fake_reply(self.read(number=2), rules,
                                                            "x")).score, 7)

    def test_write_and_omit(self):
        rules = [panel.FakeRule.write("DOUBTS", "too long"),
                 panel.FakeRule.write("DOUBTS", "and dense"),
                 panel.FakeRule.write("PRIOR", "somebody"),
                 panel.FakeRule.omit("OWNED"), panel.FakeRule.omit("STRENGTHS"),
                 panel.FakeRule.write("STRENGTHS", "ignored")]
        reply = panel.parse_reply(panel.fake_reply(self.read(), rules, "x"))
        self.assertIsNone(reply.failure)
        self.assertEqual(reply.fields["DOUBTS"], "too long and dense")
        self.assertEqual(reply.flagged, ("DOUBTS",))
        self.assertEqual(reply.prior_flag, "PRIOR is not nothing: somebody")
        self.assertNotIn("OWNED", reply.fields)
        self.assertNotIn("STRENGTHS", reply.fields)

    def test_a_rule_cannot_name_an_unknown_field_kind_or_document(self):
        with self.assertRaises(ValueError):
            panel.FakeRule.write("NOPE", "x")
        with self.assertRaises(ValueError):
            panel.FakeRule("loud")
        with self.assertRaises(ValueError):
            panel.FakeRule.score_of(1, documents=["middling"])


# Known limit: as in ab, a reader's standard output and standard error are held in memory
# with no size limit; read-timeout bounds time only.
class LiveReaderCase(unittest.TestCase):
    def live(self, source, cost=None, **overrides):
        """A setup with a fake reader first and the stub second, one lens, one version read
        and one anchor read each per document."""
        reader = "r2 | " + stub_command(self, source)
        if cost is not None:
            reader += " | cost %d" % cost
        overrides.setdefault("reads_per_reader", "1")
        overrides.setdefault("lenses", LENSES[:1])
        return Setup(self, readers=["r1 | fake", reader], **overrides)

    def test_10_11_live_reader_without_live_flag_only_prints(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        marker = os.path.join(tmp.name, "marker.txt")
        source = "open(%r, 'w').write('ran')\n" % marker + reply_stub()
        s = self.live(source, cost=3)
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual((result.exit_code, result.ran, result.error), (0, True, ""))
        self.assertFalse(os.path.exists(marker))
        self.assertIn("reader r2: ", result.text)
        self.assertIn("(cost 3 per read)", result.text)
        self.assertIn("planned reads: 6\n", result.text)
        self.assertIn("estimated spend: 12 (the sum of the planned reads' declared costs; "
                      "the tool cannot see real spend)\n", result.text)
        self.assertIn("nothing was started and no reply was written", result.text)
        self.assertEqual(sorted(os.listdir(s.folder)), sorted(
            ["plan.txt", "plan.txt.freeze", "posting.txt", "version.txt"]
            + list(PANEL_FIXTURES)))
        ran = s.run(live=True)
        self.assertEqual((ran.exit_code, ran.error), (0, ""))
        self.assertTrue(os.path.exists(marker))

    def test_10_17_a_live_stub_sees_four_files_and_the_frozen_lens(self):
        source = (
            "import hashlib, os, sys\n"
            "names = sorted(os.listdir('.'))\n"
            "def digest(name):\n"
            "    with open(name, 'rb') as handle:\n"
            "        return hashlib.sha256(handle.read()).hexdigest()\n"
            "doubts = 'files=' + ','.join(names) + ' lens=' + digest('LENS.txt')\n"
            "doubts += ' document=' + digest('DOCUMENT.txt') + ' prompt=' + digest('PROMPT.txt')\n"
            "doubts += ' posting=' + digest('POSTING.txt') + ' argv=' + repr(sys.argv[1:])\n"
            "sys.stdout.write('READ: anything\\nPRIOR: nothing\\nSCORE: 6\\n"
            "DOUBTS: ' + doubts + '\\n')\n")
        s = self.live(source)
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run(live=True)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        # Read 2 of l1 is the stub's read of the strong anchor; read 6 its read of the version.
        for number, document in ((2, "anchor-strong.txt"), (6, "version.txt")):
            reply = panel.parse_reply(s.read(panel.READS_DIR, "l1", str(number),
                                             panel.READ_REPLY))
            self.assertIsNone(reply.failure)
            doubts = dict(part.split("=", 1) for part in reply.fields["DOUBTS"].split(" "))
            self.assertEqual(doubts["files"], "DOCUMENT.txt,LENS.txt,POSTING.txt,PROMPT.txt")
            self.assertEqual(doubts["document"], sha256_of(s.path(document)))
            self.assertEqual(doubts["lens"], sha256_of(s.path("recruiter.lens.txt")))
            self.assertEqual(doubts["posting"], sha256_of(s.path("posting.txt")))
            self.assertEqual(doubts["argv"], "[]")
            frozen = [line.split("  ", 1)[0] for line in s.read("plan.txt.freeze").splitlines()
                      if line.endswith("  recruiter.lens.txt")]
            self.assertEqual(frozen, [doubts["lens"]])
            prompt = [line.split("  ", 1)[0] for line in s.read("plan.txt.freeze").splitlines()
                      if line.endswith("  " + panel.PROMPT_LABEL)]
            self.assertEqual(prompt, [doubts["prompt"]])
        self.assertEqual(sorted(os.listdir(s.read_folder("l1", 6))),
                         ["DOCUMENT.txt", "LENS.txt", "POSTING.txt", "PROMPT.txt",
                          "REPLY.txt", "STDERR.txt"])

    def test_10_17_a_stub_that_exits_nonzero_is_a_failed_read(self):
        source = ("import sys\nsys.stdout.write(%r)\nsys.stderr.write('stub failed\\n')\n"
                  "sys.exit(3)\n" % VALID_REPLY)
        s = self.live(source, rules=["recruiter | PASS if score at least 7 in 1 or more; "
                                     "otherwise INCONCLUSIVE"])
        result = s.frozen_run(live=True)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(), [
            "failed read l1/2: exit status 3", "failed read l1/4: exit status 3",
            "failed read l1/6: exit status 3"])
        lines = s.result_lines()
        self.assertIn("read l1/6: reader=r2 document=version FAILED (exit status 3)", lines)
        self.assertIn("anchor gate l1: not evaluated (2 valid anchor reads of 4 planned)",
                      lines)
        self.assertEqual(s.read(panel.READS_DIR, "l1", "6", panel.READ_STDERR), "stub failed\n")
        self.assertFalse(s.exists(panel.READS_DIR, "l1", "6", panel.READ_REPLY))
        self.assertIn("exit status: 1", lines)

    def test_a_live_reply_is_scored_like_any_other(self):
        fake = ["strong | score 9", "weak | score 2"]
        s = self.live(reply_stub(SCORE="9"), fake_reader=fake,
                      rules=["recruiter | PASS if score at least 7 in 1 or more; otherwise "
                             "INCONCLUSIVE"])
        result = s.frozen_run(live=True)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        lines = s.result_lines()
        # The stub scores every document 9, so the gate fails on its weak read.
        self.assertIn("read l1/6: reader=r2 document=version score=9 flagged=STRENGTHS,OWNED "
                      "flags=none", lines)
        self.assertIn("anchor gate l1: failed (weak read l1/4 scored 9, above 4)", lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)


class CliCase(unittest.TestCase):
    HELPS = [["panel", "-h"], ["panel", "--help"], ["panel", "freeze", "-h"],
             ["panel", "run", "-h"], ["panel", "score", "-h"]]

    def test_10_20_help_at_panel_and_at_each_subcommand(self):
        seen = set()
        for args in self.HELPS:
            with self.subTest(args=args):
                code, out, err = track(*args)
                self.assertEqual((code, err), (0, ""))
                self.assertTrue(out.startswith("usage: track-record panel"), out)
                self.assertTrue(out.endswith("\n"))
                seen.add(out)
        self.assertEqual(len(seen), 4)
        self.assertEqual(track("panel", "-h")[1], cli._PANEL_HELP)
        for name in ("freeze", "run", "score"):
            self.assertEqual(track("panel", name, "-h")[1], cli._PANEL_HELPS[name])
        self.assertNotEqual(cli._PANEL_HELP, cli._AB_HELP)
        code, out, err = track("--help")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("    panel     read one version blind through named lenses",
                      out.splitlines())

    def test_10_20_usage_errors_exit_2_with_one_line_and_no_output(self):
        for args, needle in (
                ([], "panel needs a subcommand"), (["bogus"], "unknown panel subcommand bogus"),
                (["freeze"], "panel freeze needs a PLAN"), (["run"], "panel run needs a PLAN"),
                (["score"], "panel score needs a PLAN"),
                (["freeze", "a", "b"], "takes one PLAN file"),
                (["freeze", "a", "--live"], "unknown option --live"),
                (["run", "a", "--live=1"], "--live takes no value")):
            with self.subTest(args=args):
                code, out, err = track("panel", *args)
                self.assertEqual((code, out), (2, ""), err)
                self.assertEqual(err.count("\n"), 1, err)
                self.assertIn(needle, err)

    def test_end_to_end_10_1_exits_0(self):
        s = Setup(self, fake_reader=RANK, rules=["recruiter | " + SIX_PASS])
        code, out, err = track("panel", "freeze", s.plan_path)
        self.assertEqual((code, out, err), (0, "freeze written: plan.txt.freeze\n", ""))
        code, out, err = track("panel", "run", s.plan_path)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 reads left out]\n", out)
        self.assertIn("lens l1: counted\n", out)
        self.assertEqual(out, s.read("result-1.txt"))
        code, out, err = track("panel", "score", s.plan_path)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, s.read("result-2.txt"))

    def test_end_to_end_10_4_exits_1_and_10_10_exits_2(self):
        s = Setup(self, fake_reader=RANK + ["manager | omit SCORE | read 1"])
        self.assertEqual(track("panel", "freeze", s.plan_path)[0], 0)
        code, out, err = track("panel", "run", s.plan_path)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("failed read l2/1: missing SCORE\n", out)
        t = Setup(self, anchors=["strong | anchor-weak.txt", "weak | anchor-weak.txt"])
        self.assertEqual(track("panel", "freeze", t.plan_path)[0], 0)
        code, out, err = track("panel", "run", t.plan_path)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "cannot run: the strong anchor and the weak show no changed "
                              "line; the gate needs documents that differ\n")
        self.assertFalse(t.exists("reads"))

    def test_a_plan_error_is_one_line_per_problem_and_writes_no_freeze(self):
        s = Setup(self, fake_reader=["score 9 | read 11"])
        code, out, err = track("panel", "freeze", s.plan_path)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "cannot run: plan line %d: read 11 is outside the arm's reads "
                              "(1 to 10)\n" % s.line_of("read 11"))
        self.assertFalse(s.exists("plan.txt.freeze"))


class SharedHarnessCase(unittest.TestCase):
    def test_the_two_commands_share_one_harness(self):
        self.assertIs(panel._show, barred.printed_path)
        self.assertIs(ab._show, panel._show)
        for name in ("Result", "RunFolderError", "collapsed_lines", "changed_lines",
                     "read_text", "READS_DIR", "KEY_FILE", "RUN_LOG", "RESULT_STEM",
                     "PROMPT_LABEL"):
            with self.subTest(name):
                self.assertIs(getattr(ab, name), getattr(panel, name))
                self.assertIs(getattr(ab, name), getattr(reader_harness, name.lstrip("_")))

    def test_a_run_folder_error_line_is_escaped(self):
        error = panel.RunFolderError("write", "a\nb", "c\nd")
        self.assertEqual(error.line, "cannot write a\\nb: c\\nd")


if __name__ == "__main__":
    unittest.main()
