"""Tests added after the independent review of Reader A/B (career_track_record.ab).

Each test is named for one deliberate wrong change (a mutant) that an earlier suite let
through: ``test_vr1_<mutant name>``. A test builds the scenario that tells the right code
from the mutant and asserts whole result lines or exact exit codes. All data here is
invented. The plans are written in the syntax of docs/specs/reader-ab.md, as in test_ab.py.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab  # noqa: E402
from tests.test_ab import (  # noqa: E402
    PREFER_GLANCE, SCOPE, TWO, Setup, items)

MECH_XX = "xx | default | supported at 3 or more"


def done(case, **overrides):
    """A frozen and run setup: (setup, result, result file lines)."""
    s = Setup(case, **overrides)
    result = s.frozen_run()
    return s, result, s.result_lines()


def refused(case, s, line_text, message):
    """Freeze exits 2 and names the plan line and the message."""
    result = s.freeze()
    case.assertEqual(result.exit_code, 2, result.error)
    case.assertIn("plan line %d: %s" % (s.line_of(line_text), message),
                  result.error.splitlines())
    case.assertFalse(s.exists("plan.txt.freeze"))


class NoiseControlCase(unittest.TestCase):
    def test_vr1_d_aa_version_ignored(self):
        # The plan names aa-version "base", which is not the default (the second version of
        # the first comparison, skills-top).
        s, result, lines = done(self, aa_version="base")
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("A/A arm: added by the tool, using version base", lines)
        self.assertIn("A/A version: named by aa-version in the plan", lines)
        self.assertNotIn("A/A arm: added by the tool, using version skills-top", lines)
        self.assertIn("key aa/1: reader=r1 A=base B=base", lines)
        self.assertIn("key aa/6: reader=r2 A=base B=base", lines)
        self.assertEqual(s.plan.effective_aa_version(), "base")
        self.assertEqual(s.read(ab.KEY_FILE).splitlines()[0], "aa/1\tr1\tbase\tbase")


class MechanismCase(unittest.TestCase):
    def test_vr1_den_mech_planned(self):
        # Reads c1/1 to c1/3 match, c1/4 is a failed read: 3 of 5 valid, against an A/A floor
        # of 3 of 6. Shares of the valid reads: 60% against 50%, so the mechanism separates.
        rules = items('write "xx" in DOUBTS', reads=[1, 2, 3])
        rules += items('write "xx" in DOUBTS', reads=[1, 2, 3], arm="aa")
        rules += ["omit PREFER | read 4"]
        _s, result, lines = done(self, mechanisms=[MECH_XX], fake_reader=rules)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("mechanism xx in c1 count: 3 of 5 valid reads", lines)
        self.assertIn("mechanism xx in c1 A/A floor: 3 of 6 valid reads", lines)
        self.assertIn("mechanism xx in c1 separation: separates the versions from the A/A "
                      "floor", lines)
        self.assertIn("mechanism xx in c1 verdict: SUPPORTED (SUPPORTED at 3 or more)", lines)

    def test_vr1_den_mech_counts_not_shares(self):
        # 3 of 6 is a lower share than the floor's 2 of 3, though the count is higher.
        rules = items('write "xx" in DOUBTS', reads=[1, 2, 3])
        rules += items('write "xx" in DOUBTS', reads=[1, 2], arm="aa")
        rules += items("omit PREFER", reads=[4, 5, 6], arm="aa")
        _s, result, lines = done(self, mechanisms=[MECH_XX], fake_reader=rules)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("mechanism xx in c1 count: 3 of 6 valid reads", lines)
        self.assertIn("mechanism xx in c1 A/A floor: 2 of 3 valid reads", lines)
        self.assertIn("mechanism xx in c1 separation: unable to separate the versions", lines)
        self.assertIn("mechanism xx in c1 verdict: INCONCLUSIVE (SUPPORTED at 3 or more)",
                      lines)

    def test_vr1_mech_matches_not_replies(self):
        # One reply holds the pattern in two fields: it is one matching reply, not two.
        rules = items('write "xx" in DOUBTS', reads=[1])
        rules += items('write "xx" in UNDERSOLD', reads=[1])
        _s, result, lines = done(self, fake_reader=rules,
                                 mechanisms=["xx | default | supported at 2 or more"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("mechanism xx in c1 count: 1 of 6 valid reads", lines)
        self.assertIn("mechanism xx in c1 A/A floor: 0 of 6 valid reads", lines)
        self.assertIn("mechanism xx in c1 separation: separates the versions from the A/A "
                      "floor", lines)
        self.assertIn("mechanism xx in c1 verdict: INCONCLUSIVE (SUPPORTED at 2 or more)",
                      lines)

    def test_vr1_mech_k_gt(self):
        # "supported at 3 or more" holds with exactly 3 matching replies.
        rules = items('write "xx" in DOUBTS', reads=[1, 2, 3])
        _s, result, lines = done(self, mechanisms=[MECH_XX], fake_reader=rules)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("mechanism xx in c1 count: 3 of 6 valid reads", lines)
        self.assertIn("mechanism xx in c1 verdict: SUPPORTED (SUPPORTED at 3 or more)", lines)
        fewer = items('write "xx" in DOUBTS', reads=[1, 2])
        _s, _result, lines = done(self, mechanisms=[MECH_XX], fake_reader=fewer)
        self.assertIn("mechanism xx in c1 verdict: INCONCLUSIVE (SUPPORTED at 3 or more)",
                      lines)

    def test_vr1_mech_prefer_whole_line(self):
        # The strength word is part of the PREFER line and is not rationale text, so the
        # default fields do not match it. The picks give the line "B, slightly" on every read.
        _s, result, lines = done(self, fake_reader=[PREFER_GLANCE],
                                 mechanisms=["slightly | default | supported at 3 or more"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("mechanism slightly in c1 count: 0 of 6 valid reads", lines)
        self.assertIn("mechanism slightly in c1 A/A floor: 0 of 6 valid reads", lines)
        self.assertIn("mechanism slightly in c1 separation: unable to separate the versions",
                      lines)
        self.assertIn("mechanism slightly in c1 verdict: INCONCLUSIVE "
                      "(SUPPORTED at 3 or more)", lines)


class HypothesisCountCase(unittest.TestCase):
    def test_vr1_kofn_ge(self):
        # "3 of 4" needs exactly 4 valid reads; 6 valid reads, all for skills-top, do not do.
        rule = "SUPPORTED if skills-top preferred in 3 of 4; otherwise INCONCLUSIVE"
        _s, result, lines = done(self, hypotheses=[rule], fake_reader=[PREFER_GLANCE])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hypothesis h1 rule: SUPPORTED if skills-top preferred in 3 of 4", lines)
        self.assertIn("hypothesis h1 counts: valid=6 base=0 skills-top=6 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertEqual([x for x in lines if x.startswith("hypothesis h1 reason")], [])


class PositionCase(unittest.TestCase):
    ONE_OR_MORE = "SUPPORTED if skills-top preferred in 1 or more; otherwise INCONCLUSIVE"

    def test_vr1_pos_lt3(self):
        # Exactly two non-TIE picks, both in slot A: two or more picks can be assessed.
        rules = items("prefer slot A", reads=[1, 2])
        _s, result, lines = done(self, hypotheses=[self.ONE_OR_MORE], fake_reader=rules)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("position c1: 2 of 2 non-TIE picks in slot A (100%): INCONCLUSIVE",
                      lines)
        self.assertIn("position overall: 2 of 2 non-TIE picks in slot A (100%): INCONCLUSIVE",
                      lines)
        # The count alone would support it (skills-top is picked once, in slot A of read 2).
        self.assertIn("hypothesis h1 counts: valid=6 base=1 skills-top=1 tie=4", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("hypothesis h1 reason: position is INCONCLUSIVE on c1", lines)

    def test_vr1_pos_overall_lt1(self):
        # One pick is too few for the arm and for the whole run.
        rules = items(PREFER_GLANCE, reads=[2])
        _s, result, lines = done(self, hypotheses=[self.ONE_OR_MORE], fake_reader=rules)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("position c1: 1 of 1 non-TIE picks in slot A (100%): not assessable",
                      lines)
        self.assertIn("position overall: 1 of 1 non-TIE picks in slot A (100%): "
                      "not assessable", lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED", lines)

    def test_vr1_pos_overall_for_arm(self):
        # c1 is all slot B, so its position is INCONCLUSIVE; the position of the whole run
        # (3 of 12 in slot A) is not. A hypothesis on c1 follows c1's position.
        rules = ["base vs skills-top | prefer slot B",
                 "base vs skills-top-short | " + PREFER_GLANCE]
        three = "SUPPORTED if skills-top preferred in 3 or more; otherwise INCONCLUSIVE"
        _s, result, lines = done(self, comparisons=TWO, hypotheses=[
            "base vs skills-top | " + three], fake_reader=rules)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("position c1: 0 of 6 non-TIE picks in slot A (0%): INCONCLUSIVE", lines)
        self.assertIn("position overall: 3 of 12 non-TIE picks in slot A (25%): no slot bias",
                      lines)
        # The counts alone would support it: skills-top is picked 3 times of 6.
        self.assertIn("hypothesis h1 counts: valid=6 base=3 skills-top=3 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("hypothesis h1 reason: position is INCONCLUSIVE on c1", lines)


class SpendInTheNoiseArmCase(unittest.TestCase):
    def test_vr1_spend_not_aa(self):
        # The ceiling counts the A/A reads too: 3 reads, and they are all A/A reads.
        s, result, lines = done(self, spend_ceiling="3", hypotheses=[
            "SUPPORTED if skills-top preferred in 1 or more; otherwise INCONCLUSIVE"],
            fake_reader=[PREFER_GLANCE])
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(),
                         ["cut: ran 3 of 12 planned reads at spend ceiling 3"])
        self.assertEqual(s.read(ab.RUN_LOG).splitlines()[:5], [
            "planned reads: 12", "reads run: 3", "spend: 3", "spend ceiling: 3", "cut: yes"])
        self.assertEqual((s.reply_count("aa"), s.reply_count("c1")), (3, 0))
        self.assertIn("A/A gate: not evaluated (3 valid reads of 6 planned)", lines)
        self.assertIn("cut: ran 3 of 12 planned reads at spend ceiling 3", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("hypothesis h1 reason: the A/A gate was not evaluated", lines)
        self.assertIn("exit status: 1", lines)


class ChangeScopeMatchingCase(unittest.TestCase):
    def test_vr1_iso_scope_ignorecase(self):
        # A scope pattern is case-sensitive: "^skills$" does not cover the heading "Skills".
        scope = ["^skills$"] + SCOPE[1:]
        s = Setup(self, change_scope=scope)
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["c1: changed line outside the change scope: - Skills"])
        self.assertFalse(s.exists(ab.READS_DIR))
        self.assertFalse(s.exists(ab.KEY_FILE))

    def test_vr1_iso_scope_match_not_search(self):
        # A scope pattern is searched for in the line, not matched from its start.
        scope = ["glance$", "Languages: Python", "Skills", "Tools:", "Practices:"]
        s = Setup(self, change_scope=scope)
        result = s.frozen_run()
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertEqual(s.reply_count("c1"), 6)


class PlanParserCase(unittest.TestCase):
    def test_vr1_pp_hyp_bar_ok(self):
        # A bar inside a hypothesis field is a plan error, with or without a comparison.
        rule = "SUPPORTED if skills-top preferred in 3 of 3; otherwise INCONCLUSIVE"
        message = "a hypothesis is written: [comparison |] rule"
        s = Setup(self, hypotheses=[rule + " | extra"])
        refused(self, s, "| extra", message)
        t = Setup(self, hypotheses=["base vs skills-top | " + rule + " | extra"])
        refused(self, t, "| extra", message)
        u = Setup(self, hypotheses=["base vs skills-top | " + rule])
        self.assertEqual(u.freeze().exit_code, 0)

    def test_vr1_pp_read_k_range(self):
        one = ["r1 | fake"]
        s = Setup(self, readers=one, fake_reader=["prefer slot A | read 4"])
        refused(self, s, "read 4", "read 4 is outside the arm's reads (1 to 3)")
        t = Setup(self, readers=one, fake_reader=["prefer slot A | read 3"])
        self.assertEqual(t.freeze().exit_code, 0)
        u = Setup(self, readers=one, fake_reader=["prefer slot A | read 1"])
        self.assertEqual(u.freeze().exit_code, 0)

    def test_vr1_pp_fields_trim_removed(self):
        # Spaces around a field are not part of it.
        s = Setup(self, versions=["base   |   base.txt", "skills-top  |  skills-top.txt  ",
                                  "skills-top-short |  skills-top-short.txt"],
                  readers=["r1  |   fake  ", "r2 |   fake   |  cost  2  "])
        plan = s.plan
        self.assertEqual(plan.versions, [("base", "base.txt"), ("skills-top", "skills-top.txt"),
                                         ("skills-top-short", "skills-top-short.txt")])
        self.assertEqual([(r.name, r.command, r.cost) for r in plan.readers],
                         [("r1", "fake", 1), ("r2", "fake", 1)])
        freeze = s.freeze()
        self.assertEqual((freeze.exit_code, freeze.error), (0, ""))
        labels = [line.split("  ", 1)[1] for line in s.read("plan.txt.freeze").splitlines()]
        self.assertEqual(labels[:5], ["plan.txt", "posting.txt", "base.txt", "skills-top.txt",
                                      "skills-top-short.txt"])

    def test_vr1_pp_noise_decimal(self):
        for value in ("1", "0", "0.5", "1/", "/2", "1/2/3", "-1/2", "1 / 2"):
            with self.subTest(value):
                s = Setup(self, noise_threshold=value)
                refused(self, s, "noise-threshold",
                        "noise-threshold is written as a fraction n/d")
        s = Setup(self, noise_threshold="2/3")
        self.assertEqual(s.freeze().exit_code, 0)


class ReplyScoreCase(unittest.TestCase):
    def test_vr1_rp_score_float_ok(self):
        # A score that is not a whole number fails the read, even when it reads as a number.
        s, _result, _lines = done(self, fake_reader=[PREFER_GLANCE])
        path = os.path.join(s.read_folder("c1", 1), ab.READ_REPLY)
        for value, label in (("6.0", "SCORE-A"), ("7.5", "SCORE-B")):
            with self.subTest(value):
                a, b = (value, "5") if label == "SCORE-A" else ("5", value)
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("READ: c1/1\nPRIOR: nothing\nSCORE-A: %s\nSCORE-B: %s\n"
                                 "PREFER: B, slightly\n" % (a, b))
                result = s.score()
                self.assertEqual(result.exit_code, 1)
                self.assertEqual(result.error.splitlines(),
                                 ["failed read c1/1: %s is not an integer" % label])
                self.assertIn("read c1/1: reader=r1 A=base B=skills-top FAILED "
                              "(%s is not an integer)" % label, result.text.splitlines())
                with open(path, encoding="utf-8") as handle:
                    self.assertEqual(ab.parse_reply(handle.read()).failure,
                                     "%s is not an integer" % label)


class FakeRuleReachCase(unittest.TestCase):
    def test_vr1_sc_onread_applies_to_aa(self):
        # A rule limited to read 2 acts on read 2 of the comparison only, never on the A/A
        # arm's read 2, whether or not it names its comparison.
        rules = ["prefer slot A | read 2", "base vs skills-top | prefer slot A | read 4",
                 "score 1 9 | read 2", 'write "xx" in DOUBTS | read 2']
        s, result, lines = done(self, fake_reader=rules, mechanisms=[
            "xx | default | supported at 1 or more"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("reads all readers aa: valid=6 skills-top=0 tie=6", lines)
        self.assertIn("reads all readers c1: valid=6 base=0 skills-top=2 tie=4", lines)
        self.assertIn("read aa/2: reader=r1 A=skills-top B=skills-top scores=5/5 prefer=TIE "
                      "flags=none", lines)
        self.assertIn("read c1/2: reader=r1 A=skills-top B=base scores=1/9 prefer=A, slightly "
                      "flags=none", lines)
        self.assertIn("A/A score spread: 0 (highest 5, lowest 5)", lines)
        self.assertIn("mechanism xx in c1 A/A floor: 0 of 6 valid reads", lines)
        self.assertIn("mechanism xx in c1 count: 1 of 6 valid reads", lines)


if __name__ == "__main__":
    unittest.main()
