"""Tests for revision 2 of the Reader A/B spec (docs/specs/reader-ab.md § 6.1 and its tests 10.42 to 10.57). All data here is invented."""

import os
import sys
import unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab  # noqa: E402
from tests.test_ab import (  # noqa: E402
    PREFER_GLANCE, SIX, SHORT_SIX, TOO_LONG, TWO, WITHOUT_GLANCE, WRITE_TOO_LONG, Setup,
    items)

ALPHA_MESSAGE = "alpha is written as 0. followed by digits, not all zero"
SIDEDNESS_MESSAGE = "sidedness is two, greater or less"


class PlanKeysCase(unittest.TestCase):
    def assertRefused(self, s, line_text, message):
        """Freeze exits 2, names the plan line number, and writes no freeze file."""
        result = s.freeze()
        self.assertEqual(result.exit_code, 2, result.error)
        self.assertFalse(result.ran)
        number = s.line_of(line_text)
        self.assertIn("plan line %d: %s" % (number, message), result.error.splitlines())
        self.assertFalse(s.exists("plan.txt.freeze"))
        self.assertFalse(s.exists(ab.READS_DIR))

    def test_10_53_bad_alpha_and_sidedness_values_are_refused_by_freeze(self):
        cases = [("alpha", value, ALPHA_MESSAGE) for value in ("0", "0.0", "1", "1/20", ".05")]
        cases += [("sidedness", value, SIDEDNESS_MESSAGE) for value in ("both", "Two")]
        for key, value, message in cases:
            with self.subTest(key=key, value=value):
                s = Setup(self, **{key: value})
                self.assertRefused(s, key + ":", message)

    def test_10_53_good_values_freeze(self):
        s = Setup(self, alpha="0.05", sidedness="less")
        result = s.freeze()
        self.assertEqual(result.exit_code, 0, result.error)
        plan = s.plan
        self.assertEqual(plan.alpha, Fraction(1, 20))
        self.assertEqual(plan.alpha_text, "0.05")
        self.assertEqual(plan.sidedness, "less")

    def test_defaults_when_the_keys_are_absent(self):
        plan = Setup(self).plan
        self.assertEqual(plan.sidedness, "two")
        self.assertEqual(plan.alpha, Fraction(1, 20))
        self.assertEqual(plan.alpha_text, "0.05")

    def test_alpha_is_kept_as_written(self):
        plan = Setup(self, alpha="0.010").plan
        self.assertEqual(plan.alpha, Fraction(1, 100))
        self.assertEqual(plan.alpha_text, "0.010")

    def test_greater_and_two_freeze(self):
        for value in ("greater", "two"):
            with self.subTest(sidedness=value):
                result = Setup(self, sidedness=value).freeze()
                self.assertEqual(result.exit_code, 0, result.error)


VALIDITY = ("validity: the readers are models standing in for human screeners, and that "
            "stand-in has not been checked against human ratings. Reads from one model and "
            "prompt may not be independent, so each p-value assumes independence and may be "
            "too small.")
CORRELATED = "(reads may be correlated; may be too small)"
AA_STRONG = "aa | random seed 1 non-tie | strongly"
NO_VALID = ["aa | omit PREFER", "all | omit PREFER"]


class EvidenceCase(unittest.TestCase):
    def done(self, **overrides):
        overrides.setdefault("hypotheses", [SIX])
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def assertNoFlag(self, lines):
        self.assertEqual([x for x in lines if x.startswith("hypothesis h1 flag:")], [])

    def test_10_42_evidence_line_and_no_flag(self):
        s, result, lines = self.done(fake_reader=[PREFER_GLANCE])
        self.assertIn("hypothesis h1 evidence: skills-top 6 of 6 non-TIE picks, 0 TIE; "
                      "p = 0.0313 two-sided " + CORRELATED + "; 95% interval 0.609 to 1.000",
                      lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED [not blind: 0 of 6 valid reads]", lines)
        self.assertNoFlag(lines)

    def test_10_43_one_sided(self):
        s, result, lines = self.done(fake_reader=[PREFER_GLANCE], sidedness="greater")
        self.assertIn("hypothesis h1 evidence: skills-top 6 of 6 non-TIE picks, 0 TIE; "
                      "p = 0.0156 one-sided greater " + CORRELATED
                      + "; 95% interval 0.609 to 1.000", lines)
        self.assertNoFlag(lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED [not blind: 0 of 6 valid reads]", lines)
        s, result, lines = self.done(fake_reader=[PREFER_GLANCE], sidedness="less")
        self.assertIn("hypothesis h1 evidence: skills-top 6 of 6 non-TIE picks, 0 TIE; "
                      "p = 1.0000 one-sided less " + CORRELATED
                      + "; 95% interval 0.609 to 1.000", lines)
        self.assertIn("hypothesis h1 flag: one-sided test: this direction not tested", lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED [not blind: 0 of 6 valid reads]", lines)

    def test_10_44_supported_at_a_large_p_is_flagged(self):
        s, result, lines = self.done(
            hypotheses=["SUPPORTED if skills-top preferred in 4 or more; otherwise INCONCLUSIVE"],
            fake_reader=items(PREFER_GLANCE, reads=[1, 2, 3, 4])
            + items(WITHOUT_GLANCE, reads=[5, 6]))
        self.assertIn("hypothesis h1 evidence: skills-top 4 of 6 non-TIE picks, 0 TIE; "
                      "p = 0.6875 two-sided " + CORRELATED + "; 95% interval 0.299 to 0.904",
                      lines)
        self.assertIn("hypothesis h1 flag: evidence disagrees: SUPPORTED at p = 0.6875, "
                      "at or above alpha 0.05", lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED [not blind: 0 of 6 valid reads]", lines)

    def test_10_45_inconclusive_at_a_small_p_is_flagged(self):
        s, result, lines = self.done(
            reads_per_reader="4",
            hypotheses=["SUPPORTED if skills-top preferred in 8 of 8; otherwise INCONCLUSIVE"],
            fake_reader=[PREFER_GLANCE, "omit PREFER | read 8"])
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 of 7 valid reads]",
                      lines)
        self.assertIn("hypothesis h1 evidence: skills-top 7 of 7 non-TIE picks, 0 TIE; "
                      "p = 0.0156 two-sided " + CORRELATED + "; 95% interval 0.645 to 1.000",
                      lines)
        self.assertIn("hypothesis h1 flag: evidence disagrees: INCONCLUSIVE at p = 0.0156, "
                      "below alpha 0.05", lines)
        self.assertEqual(result.exit_code, 1)

    def test_10_46_refuted_at_a_large_p_is_flagged(self):
        s, result, lines = self.done(fake_reader=[WITHOUT_GLANCE, "omit PREFER | read 1"])
        self.assertIn("hypothesis h1 evidence: skills-top 0 of 5 non-TIE picks, 0 TIE; "
                      "p = 0.0625 two-sided " + CORRELATED + "; 95% interval 0.000 to 0.435",
                      lines)
        self.assertIn("hypothesis h1 flag: evidence disagrees: REFUTED at p = 0.0625, "
                      "at or above alpha 0.05", lines)
        self.assertIn("hypothesis h1 verdict: REFUTED [not blind: 0 of 5 valid reads]", lines)
        self.assertEqual(result.exit_code, 1)

    def test_10_47_no_valid_read(self):
        s, result, lines = self.done(fake_reader=NO_VALID)
        self.assertIn("A/A gate interval: not computed", lines)
        self.assertIn("hypothesis h1 evidence: no non-TIE pick, 0 TIE; "
                      "p and interval not computed", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 of 0 valid reads]",
                      lines)
        self.assertNoFlag(lines)
        self.assertEqual(result.exit_code, 1)

    def test_10_50_not_blind_counts_on_both_verdict_lines(self):
        s, result, lines = self.done(
            readers=["r1 | fake", "r2 | fake | not-blind"], mechanisms=[TOO_LONG],
            fake_reader=items(WRITE_TOO_LONG, reads=[1, 2, 3, 4]))
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 3 of 6 valid reads]",
                      lines)
        self.assertIn("mechanism too long in c1 verdict: SUPPORTED (SUPPORTED at 3 or more) "
                      "[not blind: 3 of 6 valid reads]", lines)

    def test_10_51_exactly_one_validity_line(self):
        for name, reader in (("tie", ["tie"]), ("aa", [AA_STRONG]), ("none", NO_VALID)):
            with self.subTest(plan=name):
                s, result, lines = self.done(fake_reader=reader)
                self.assertEqual(len([x for x in lines if x == VALIDITY]), 1)

    def test_10_52_alpha_is_compared_and_printed_as_written(self):
        s, result, lines = self.done(alpha="0.01", fake_reader=[PREFER_GLANCE])
        self.assertIn("hypothesis h1 flag: evidence disagrees: SUPPORTED at p = 0.0313, "
                      "at or above alpha 0.01", lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED [not blind: 0 of 6 valid reads]", lines)

    def test_10_54_aa_gate_interval(self):
        s, result, lines = self.done(fake_reader=[AA_STRONG])
        self.assertIn("A/A gate interval: 0.609 to 1.000 (95%, Wilson)", lines)
        s, result, lines = self.done(fake_reader=[PREFER_GLANCE])
        self.assertIn("A/A gate interval: 0.000 to 0.391 (95%, Wilson)", lines)

    def test_10_55_always_tie(self):
        s, result, lines = self.done(fake_reader=["tie"])
        self.assertIn("hypothesis h1 evidence: no non-TIE pick, 6 TIE; "
                      "p and interval not computed", lines)
        self.assertNoFlag(lines)

    def test_10_56_a_tripped_gate_gets_no_flag(self):
        s, result, lines = self.done(fake_reader=[AA_STRONG, PREFER_GLANCE])
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 of 6 valid reads]",
                      lines)
        self.assertIn("hypothesis h1 reason: the A/A gate tripped", lines)
        self.assertIn("hypothesis h1 evidence: skills-top 6 of 6 non-TIE picks, 0 TIE; "
                      "p = 0.0313 two-sided " + CORRELATED + "; 95% interval 0.609 to 1.000",
                      lines)
        self.assertNoFlag(lines)

    def test_10_57_the_prompt_is_unchanged(self):
        self.assertEqual(
            ab.prompt_sha256(),
            "567b9bc16d86abfe4af935a844e28a1b6d2d257aa4f93b6ab3de8e97ce1fdd14")
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)

    def test_a_position_reason_gets_no_flag(self):
        s, result, lines = self.done(
            hypotheses=["SUPPORTED if skills-top preferred in 3 or more; otherwise INCONCLUSIVE"],
            fake_reader=["prefer slot A"])
        self.assertIn("hypothesis h1 evidence: skills-top 3 of 6 non-TIE picks, 0 TIE; "
                      "p = 1.0000 two-sided " + CORRELATED + "; 95% interval 0.187 to 0.813",
                      lines)
        self.assertIn("hypothesis h1 reason: position is INCONCLUSIVE on c1", lines)
        self.assertNoFlag(lines)


class MissingReadsCase(unittest.TestCase):
    def done(self, **overrides):
        overrides.setdefault("hypotheses", [SIX])
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def assertNoLineStarting(self, lines, prefix):
        self.assertEqual([x for x in lines if x.startswith(prefix)], [])

    def test_10_45_missing_and_completions_unsettled(self):
        s, result, lines = self.done(
            reads_per_reader="4",
            hypotheses=["SUPPORTED if skills-top preferred in 8 of 8; otherwise INCONCLUSIVE"],
            fake_reader=[PREFER_GLANCE, "omit PREFER | read 8"])
        self.assertIn("missing c1: 1 of 8 planned reads (failed 1, not run 0)", lines)
        self.assertIn("missing aa: 0 of 8 planned reads (failed 0, not run 0)", lines)
        self.assertIn("hypothesis h1 completions (missing reads: 1): "
                      "unsettled: SUPPORTED, INCONCLUSIVE possible; p from 0.0078 to 0.0703",
                      lines)
        self.assertNoLineStarting(lines, "DEAD:")
        self.assertEqual(result.exit_code, 1)

    def test_10_46_completions_settled(self):
        s, result, lines = self.done(fake_reader=[WITHOUT_GLANCE, "omit PREFER | read 1"])
        self.assertIn("hypothesis h1 completions (missing reads: 1): "
                      "settled: REFUTED; p from 0.0313 to 0.2188", lines)
        self.assertEqual(result.exit_code, 1)

    def test_10_47_dead_run(self):
        s, result, lines = self.done(fake_reader=["aa | omit PREFER", "all | omit PREFER"])
        self.assertIn("DEAD: 0 of 12 planned reads are valid", lines)
        self.assertIn("missing aa: 6 of 6 planned reads (failed 6, not run 0)", lines)
        self.assertIn("missing c1: 6 of 6 planned reads (failed 6, not run 0)", lines)
        self.assertIn("hypothesis h1 completions (missing reads: 6): "
                      "unsettled: SUPPORTED, REFUTED, INCONCLUSIVE possible; "
                      "p from 0.0313 to 1.0000", lines)
        self.assertEqual(result.exit_code, 1)

    def test_a_cut_counts_reads_not_run(self):
        s, result, lines = self.done(
            comparisons=TWO, spend_ceiling="8",
            hypotheses=["base vs skills-top | " + SIX,
                        "base vs skills-top-short | " + SHORT_SIX],
            fake_reader=[PREFER_GLANCE])
        self.assertIn("missing aa: 0 of 6 planned reads (failed 0, not run 0)", lines)
        self.assertIn("missing c1: 4 of 6 planned reads (failed 0, not run 4)", lines)
        self.assertIn("missing c2: 6 of 6 planned reads (failed 0, not run 6)", lines)
        self.assertIn("hypothesis h1 completions (missing reads: 4): "
                      "unsettled: SUPPORTED, REFUTED, INCONCLUSIVE possible; "
                      "p from 0.0313 to 1.0000", lines)
        self.assertIn("hypothesis h2 completions (missing reads: 6): "
                      "unsettled: SUPPORTED, INCONCLUSIVE possible; p from 0.0313 to 1.0000",
                      lines)
        self.assertNoLineStarting(lines, "DEAD:")
        self.assertEqual(result.exit_code, 1)

    def test_no_missing_read_no_completions_line(self):
        s, result, lines = self.done(fake_reader=[PREFER_GLANCE])
        self.assertIn("missing c1: 0 of 6 planned reads (failed 0, not run 0)", lines)
        self.assertNoLineStarting(lines, "hypothesis h1 completions")

    def test_completions_ignore_the_gate(self):
        s, result, lines = self.done(
            fake_reader=["aa | random seed 1 non-tie | strongly", PREFER_GLANCE,
                         "omit PREFER | read 1"])
        self.assertIn("hypothesis h1 completions (missing reads: 1): "
                      "unsettled: SUPPORTED, INCONCLUSIVE possible; p from 0.0313 to 0.2188",
                      lines)

    def test_a_p_equal_to_alpha_is_flagged(self):
        s, result, lines = self.done(fake_reader=[WITHOUT_GLANCE, "omit PREFER | read 1"],
                                     alpha="0.0625")
        self.assertIn("hypothesis h1 flag: evidence disagrees: REFUTED at p = 0.0625, "
                      "at or above alpha 0.0625", lines)

    def test_no_dead_line_while_the_aa_arm_has_valid_reads(self):
        s, result, lines = self.done(fake_reader=["all | omit PREFER"])
        self.assertIn("missing c1: 6 of 6 planned reads (failed 6, not run 0)", lines)
        self.assertNoLineStarting(lines, "DEAD:")

    def test_completions_use_the_plans_side(self):
        s, result, lines = self.done(fake_reader=[WITHOUT_GLANCE, "omit PREFER | read 1"],
                                     sidedness="greater")
        self.assertIn("hypothesis h1 completions (missing reads: 1): "
                      "settled: REFUTED; p from 0.9844 to 1.0000", lines)


class ScaleCase(unittest.TestCase):
    def done(self, **overrides):
        overrides.setdefault("hypotheses", [SIX])
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def ceiling(self, arm, c, v):
        return ("scores %s ceiling: %d of %d valid reads score both slots at 10 or more"
                % (arm, c, v))

    def separation(self, arm, n, v):
        return ("scores %s separation: %d of %d valid reads give both slots the same score"
                % (arm, n, v))

    def at_ceiling(self, arm):
        return "scores %s: at the ceiling; preference is the only measure" % arm

    def test_10_48_both_arms_at_the_ceiling(self):
        s, result, lines = self.done(
            fake_reader=[PREFER_GLANCE, "all | score 10 10", "aa | score 10 10"])
        for arm in ("aa", "c1"):
            self.assertIn(self.ceiling(arm, 6, 6), lines)
            self.assertIn(self.separation(arm, 6, 6), lines)
            self.assertIn(self.at_ceiling(arm), lines)

    def test_10_49_no_score_rule(self):
        s, result, lines = self.done(fake_reader=[PREFER_GLANCE])
        for arm in ("aa", "c1"):
            self.assertIn(self.ceiling(arm, 0, 6), lines)
            self.assertIn(self.separation(arm, 6, 6), lines)
            self.assertNotIn(self.at_ceiling(arm), lines)

    def test_10_49_above_ten_and_unequal(self):
        s, result, lines = self.done(fake_reader=[PREFER_GLANCE, "all | score 10 12"])
        self.assertIn(self.ceiling("c1", 6, 6), lines)
        self.assertIn(self.separation("c1", 0, 6), lines)
        self.assertIn(self.at_ceiling("c1"), lines)
        self.assertIn(self.ceiling("aa", 0, 6), lines)
        self.assertNotIn(self.at_ceiling("aa"), lines)

    def test_one_slot_at_ten_is_not_the_ceiling(self):
        s, result, lines = self.done(fake_reader=[PREFER_GLANCE, "all | score 10 9"])
        self.assertIn(self.ceiling("c1", 0, 6), lines)
        self.assertNotIn(self.at_ceiling("c1"), lines)

    def test_no_valid_read(self):
        s, result, lines = self.done(fake_reader=["aa | omit PREFER", "all | omit PREFER"])
        self.assertIn(self.ceiling("aa", 0, 0), lines)
        self.assertIn(self.separation("c1", 0, 0), lines)
        self.assertEqual([x for x in lines if x.endswith(
            "at the ceiling; preference is the only measure")], [])


if __name__ == "__main__":
    unittest.main()
