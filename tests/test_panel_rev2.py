"""Tests for revision 2 of the reader panel spec (docs/specs/reader-panel.md § 6.1 and its tests 10.29 to 10.38). All data here is invented."""

import os
import sys
import unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from tests.test_panel import Setup, LENSES, SIX_PASS  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
