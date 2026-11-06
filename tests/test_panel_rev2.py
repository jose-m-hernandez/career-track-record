"""Tests for revision 2 of the reader panel spec (docs/specs/reader-panel.md § 6.1 and its tests 10.29 to 10.38). All data here is invented."""

import os
import sys
import unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from career_track_record import ab, panel, reader_harness  # noqa: E402
from tests.test_panel import (Setup, LENSES, SIX_PASS, RANK, RANK_RECRUITER,  # noqa: E402
                              FLAT_MANAGER)


class PlanKeysCase(unittest.TestCase):
    def assertRefused(self, s, line_text, message):
        result = s.freeze()
        self.assertEqual(result.exit_code, 2, result.error)
        self.assertFalse(result.ran)
        number = s.line_of(line_text)
        self.assertIn("plan line %d: %s" % (number, message), result.error.splitlines())
        self.assertFalse(s.exists("plan.txt.freeze"))

    def test_10_37_bad_values_are_refused_by_freeze(self):
        share = "null-share is written n/d, strictly between 0 and 1"
        for value in ("0/4", "4/4", "0.5"):
            with self.subTest(null_share=value):
                s = Setup(self, rules=["recruiter | " + SIX_PASS + " | null-share " + value])
                self.assertRefused(s, "null-share", share)
        for value in ("x", "7.5"):
            with self.subTest(max=value):
                s = Setup(self, lenses=["recruiter | recruiter.lens.txt | max " + value,
                                        LENSES[1]])
                self.assertRefused(s, "max " + value,
                                   "a lens's max is a whole number: " + value)
        with self.subTest(sidedness="both"):
            s = Setup(self, sidedness="both")
            self.assertRefused(s, "sidedness:", "sidedness is two, greater or less")

    def test_10_32_a_max_below_the_strong_threshold_is_refused(self):
        s = Setup(self, lenses=["recruiter | recruiter.lens.txt | max 6", LENSES[1]])
        self.assertRefused(s, "max 6", "max 6 is below anchor-strong-at-least (7)")

    def test_good_values_are_kept(self):
        s = Setup(self, lenses=["recruiter | recruiter.lens.txt | max 10", LENSES[1]])
        self.assertEqual(s.freeze().exit_code, 0)
        self.assertEqual(s.plan.lenses[0].max, 10)
        self.assertIsNone(s.plan.lenses[1].max)
        s = Setup(self, lenses=["recruiter | recruiter.lens.txt | max 7", LENSES[1]])
        self.assertEqual(s.freeze().exit_code, 0)
        self.assertEqual(s.plan.lenses[0].max, 7)
        s = Setup(self, rules=["recruiter | " + SIX_PASS + " | null-share 2/4"])
        self.assertEqual(s.freeze().exit_code, 0)
        self.assertEqual(s.plan.rules[0].null_share, Fraction(1, 2))
        self.assertEqual(s.plan.rules[0].null_share_text, "2/4")
        s = Setup(self, rules=["recruiter | " + SIX_PASS])
        self.assertEqual(s.freeze().exit_code, 0)
        self.assertIsNone(s.plan.rules[0].null_share)
        s = Setup(self, sidedness="greater")
        self.assertEqual(s.freeze().exit_code, 0)
        self.assertEqual(s.plan.sidedness, "greater")
        self.assertEqual(Setup(self).plan.sidedness, "two")

    def test_the_old_three_field_messages_still_hold(self):
        s = Setup(self, lenses=["one | two | three"])
        self.assertRefused(s, "one | two | three", "a lens is written: name | file")
        s = Setup(self, rules=["recruiter | " + SIX_PASS + " | extra"])
        self.assertRefused(s, "| extra", "a rule is written: <lens> | <rule>, or overall | "
                           "<rule>, with the lens written as in lenses")


class EvidenceCase(unittest.TestCase):
    """Revision 2 section 6.1: the evidence printed beside each verdict."""

    VALIDITY = ("validity: the readers are models standing in for human screeners, and that "
                "stand-in has not been checked against human ratings. Reads from one model "
                "and prompt may not be independent, so each p-value assumes independence "
                "and may be too small.")

    def done(self, **overrides):
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def test_10_29_intervals_and_no_p(self):
        s, result, lines = self.done(fake_reader=RANK, rules=["recruiter | " + SIX_PASS])
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("rule r1 (l1) evidence: score at least 7: 6 of 6 counted reads; "
                      "95% interval 0.609 to 1.000", lines)
        self.assertIn("rule r1 (l1) evidence: score at most 4: 0 of 6 counted reads; "
                      "95% interval 0.000 to 0.391", lines)
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 of 6 counted reads]", lines)
        self.assertEqual([x for x in lines if "p = " in x], [])

    def test_10_30_p_against_a_declared_share(self):
        tail = " (reads may be correlated; may be too small); 95%% interval %s"
        cases = [
            ("1/2", "two", "p = 0.0313 two-sided against 1/2", "p = 0.0313 two-sided against 1/2"),
            ("3/4", "two", "p = 0.3560 two-sided against 3/4", "p = 0.0005 two-sided against 3/4"),
            ("1/2", "greater", "p = 0.0156 one-sided greater against 1/2", None),
        ]
        for share, side, first, second in cases:
            with self.subTest(share=share, sidedness=side):
                s, result, lines = self.done(
                    fake_reader=RANK, sidedness=side,
                    rules=["recruiter | " + SIX_PASS + " | null-share " + share])
                self.assertEqual((result.exit_code, result.error), (0, ""))
                self.assertIn("rule r1 (l1) evidence: score at least 7: 6 of 6 counted reads; "
                              + first + tail % "0.609 to 1.000", lines)
                if second is not None:
                    self.assertIn("rule r1 (l1) evidence: score at most 4: 0 of 6 counted "
                                  "reads; " + second + tail % "0.000 to 0.391", lines)
                self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 of 6 counted reads]",
                              lines)

    def test_10_35_not_blind_counts(self):
        s, result, lines = self.done(
            readers=["r1 | fake", "r2 | fake | not-blind"], fake_reader=RANK,
            rules=["recruiter | " + SIX_PASS,
                   "overall | PASS if score at least 7 in 12 of 12; otherwise INCONCLUSIVE"])
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 3 of 6 counted reads]", lines)
        self.assertIn("rule r2 (overall) verdict: PASS [not blind: 6 of 12 counted reads]",
                      lines)

    def test_10_36_exactly_one_validity_line(self):
        plans = {
            "10.2": dict(fake_reader=RANK_RECRUITER + FLAT_MANAGER,
                         rules=["recruiter | " + SIX_PASS, "manager | " + SIX_PASS]),
            "10.34": dict(fake_reader=["omit SCORE"], rules=["recruiter | " + SIX_PASS]),
        }
        for name, overrides in plans.items():
            with self.subTest(plan=name):
                s, result, lines = self.done(**overrides)
                self.assertEqual(lines.count(self.VALIDITY), 1)

    def test_10_38_the_prompt_is_unchanged(self):
        self.assertEqual(panel.prompt_sha256(),
                         "79657b05dbea178a019140c4f8bba1fddd1eba4c044d2b191f07dd849579ae1c")
        s, result, lines = self.done()
        self.assertEqual((result.exit_code, result.error), (0, ""))

    def test_an_uncounted_lens_prints_no_interval_and_no_p(self):
        s, result, lines = self.done(
            fake_reader=RANK_RECRUITER + FLAT_MANAGER,
            rules=["recruiter | " + SIX_PASS, "manager | " + SIX_PASS + " | null-share 1/2"])
        self.assertIn("rule r2 (l2) evidence: score at least 7: 0 of 0 counted reads; "
                      "interval not computed", lines)
        self.assertIn("rule r2 (l2) verdict: INCONCLUSIVE [not blind: 0 of 0 counted reads]",
                      lines)
        self.assertEqual([x for x in lines if x.startswith("rule r2") and "p = " in x], [])

    def test_ab_and_panel_share_the_validity_text(self):
        s, result, lines = self.done(fake_reader=RANK, rules=["recruiter | " + SIX_PASS])
        found = [x for x in lines if x.startswith("validity: ")]
        self.assertEqual(found, [reader_harness.VALIDITY_LINE])
        self.assertIs(ab.VALIDITY_LINE, reader_harness.VALIDITY_LINE)


if __name__ == "__main__":
    unittest.main()
