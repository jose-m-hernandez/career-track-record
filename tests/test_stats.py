"""Tests for career_track_record.stats: the exact binomial p-value and the Wilson interval.

The expected values are the known answers of docs/specs/reader-ab.md section 6.1, and
the same arithmetic done independently.
"""

import os
import sys
import unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record.stats import binomial_p, fisher_p, p_text, wilson  # noqa: E402


class StatsCase(unittest.TestCase):

    def test_p_text_of_binomial_p(self):
        cases = [
            ((6, 6), "0.0313"),
            ((6, 6, "greater"), "0.0156"),
            ((6, 6, "less"), "1.0000"),
            ((4, 6), "0.6875"),
            ((7, 7), "0.0156"),
            ((0, 5), "0.0625"),
            ((8, 8), "0.0078"),
            ((7, 8), "0.0703"),
            ((1, 6), "0.2188"),
            ((6, 6, "two", Fraction(3, 4)), "0.3560"),
            ((0, 6, "two", Fraction(3, 4)), "0.0005"),
        ]
        for args, want in cases:
            with self.subTest(args=args):
                self.assertEqual(p_text(binomial_p(*args)), want)

    def test_binomial_p_is_an_exact_fraction(self):
        self.assertEqual(binomial_p(6, 6), Fraction(1, 32))
        self.assertIsInstance(binomial_p(6, 6), Fraction)

    def test_p_text_rounds_half_up_and_floors_small_values(self):
        self.assertEqual(p_text(Fraction(1, 20000)), "0.0001")
        self.assertEqual(p_text(Fraction(1, 20001)), "< 0.0001")

    def test_wilson(self):
        cases = [
            ((6, 6), ("0.609", "1.000")),
            ((0, 6), ("0.000", "0.391")),
            ((4, 6), ("0.299", "0.904")),
            ((7, 7), ("0.645", "1.000")),
            ((0, 5), ("0.000", "0.435")),
            ((1, 6), ("0.030", "0.564")),
            ((3, 6), ("0.187", "0.813")),
        ]
        for args, want in cases:
            with self.subTest(args=args):
                self.assertEqual(wilson(*args), want)

    def test_bad_arguments_raise_value_error(self):
        calls = [
            lambda: binomial_p(0, 0),
            lambda: binomial_p(3, 2),
            lambda: binomial_p(1, 2, "both"),
            lambda: binomial_p(1, 2, "two", Fraction(0)),
            lambda: binomial_p(1, 2, "two", Fraction(1)),
            lambda: wilson(0, 0),
            lambda: wilson(-1, 3),
        ]
        for i, call in enumerate(calls):
            with self.subTest(i=i):
                with self.assertRaises(ValueError):
                    call()


class FisherCase(unittest.TestCase):

    ROWS = [
        ((6, 6, 6, 6), Fraction(1), "1.0000"),
        ((6, 6, 0, 6), Fraction(1, 462), "0.0022"),
        ((5, 6, 1, 6), Fraction(37, 462), "0.0801"),
        ((4, 6, 1, 5), Fraction(8, 33), "0.2424"),
        ((2, 3, 6, 6), Fraction(1, 3), "0.3333"),
        ((3, 6, 0, 6), Fraction(2, 11), "0.1818"),
        ((1, 4, 3, 4), Fraction(17, 35), "0.4857"),
    ]

    def test_fisher_p_known_values(self):
        for args, want, text in self.ROWS:
            with self.subTest(args=args):
                self.assertEqual(fisher_p(*args), want)
                self.assertEqual(p_text(fisher_p(*args)), text)

    def test_fisher_p_is_exact_and_symmetric(self):
        for args, _want, _text in self.ROWS:
            k1, n1, k2, n2 = args
            with self.subTest(args=args):
                self.assertIsInstance(fisher_p(*args), Fraction)
                self.assertEqual(fisher_p(k1, n1, k2, n2), fisher_p(k2, n2, k1, n1))
                self.assertEqual(fisher_p(k1, n1, k2, n2),
                                 fisher_p(n1 - k1, n1, n2 - k2, n2))

    def test_fisher_p_with_an_empty_side_is_one(self):
        self.assertEqual(fisher_p(0, 0, 3, 6), Fraction(1))
        self.assertEqual(fisher_p(4, 6, 0, 0), Fraction(1))
        self.assertEqual(fisher_p(0, 0, 0, 0), Fraction(1))

    def test_fisher_p_refuses_bad_counts(self):
        for args in [(-1, 6, 0, 6), (7, 6, 0, 6), (0, 6, 7, 6),
                     (0, -1, 0, 6), (0, 6, 0, -1), (0, 6, -1, 6)]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    fisher_p(*args)


if __name__ == "__main__":
    unittest.main()
