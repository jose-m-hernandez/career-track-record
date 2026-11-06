"""Tests for revision 2 of the Reader A/B spec (docs/specs/reader-ab.md § 6.1 and its tests 10.42 to 10.57). All data here is invented."""

import os
import sys
import unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab  # noqa: E402
from tests.test_ab import Setup  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
