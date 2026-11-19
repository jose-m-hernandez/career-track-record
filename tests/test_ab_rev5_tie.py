"""Tests for revision 5 of the Reader A/B spec, the TIE verdict inside the A/A band (cases T1
to T24 of the revision 5 TIE spec). All data here is invented.

The plans here name their readers reader-1 and reader-2, as the spec's default plan does, so
that the lines the spec gives are asserted as they are written. "Reads a to b prefer
containing X" is the fake rule ``prefer containing "X" | clearly | read k``, written once per
read, as test 10.81 in tests/test_ab_rev4.py writes its two reads.

Where a case says what a wrong rule would give, the comment beside the assertion names that
wrong answer: it is the mutant the assertion must turn red.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab  # noqa: E402
from tests.test_ab import (  # noqa: E402
    PREFER_GLANCE, WITHOUT_GLANCE, Setup, items, sha256_of)
from tests.test_ab_rev3 import FIVE_OF_SIX, LIFT_5, OMIT_1  # noqa: E402
from tests.test_ab_rev4 import READERS, versions  # noqa: E402
from tests.test_ab_rev4_runs import RunsBase, rel  # noqa: E402
from tests.test_panel import Setup as PanelSetup  # noqa: E402

FOUR = "SUPPORTED if skills-top preferred in 4 or more; otherwise INCONCLUSIVE"
THREE = "SUPPORTED if skills-top preferred in 3 or more; otherwise INCONCLUSIVE"
TWO = "SUPPORTED if skills-top preferred in 2 or more; otherwise INCONCLUSIVE"
FIVE = "SUPPORTED if skills-top preferred in 5 or more; otherwise INCONCLUSIVE"
THREE_OF_SIX = "SUPPORTED if skills-top preferred in 3 of 6; otherwise INCONCLUSIVE"
WITH_REFUTED = ("SUPPORTED if skills-top preferred in 4 or more; REFUTED if base preferred in "
                "4 or more; otherwise INCONCLUSIVE")
EXTEND = ("an extension may change only reads-per-reader and the number of readers of each "
          "model: ")
AMEND = "an amendment may not change aa-band from the plan it amends"
VERDICT_SUPPORTED = "hypothesis h1 verdict: SUPPORTED [not blind: 0 reads left out]"
VERDICT_TIE = "hypothesis h1 verdict: TIE [not blind: 0 reads left out]"
FLAG_P = ("hypothesis h1 flag: evidence disagrees: SUPPORTED at p = 0.6875, at or above alpha "
          "0.05")
SECOND_SUPPORTED = "hypothesis h1 second reading (slightly as TIE): SUPPORTED"


def glance(reads, without=()):
    """Comparison reads: ``reads`` prefer containing "At a glance", ``without`` prefer without
    it, every one clearly, so the second reading agrees with the first (10.82)."""
    rules = items(PREFER_GLANCE, reads=list(reads), strength="clearly")
    if without:
        rules += items(WITHOUT_GLANCE, reads=list(without), strength="clearly")
    return rules


def aa(slot_a=(), slot_b=()):
    """A/A reads: ``slot_a`` prefer slot A, ``slot_b`` prefer slot B."""
    rules = []
    if slot_a:
        rules += items("prefer slot A", reads=list(slot_a), arm="aa")
    if slot_b:
        rules += items("prefer slot B", reads=list(slot_b), arm="aa")
    return rules


# 4 pairs for skills-top, 2 for base, as 10.44: reads 1 to 8 with the glance, 9 to 12 without.
FOUR_TWO = glance(range(1, 9), range(9, 13))
# Pairs 1-2 and 3-4 of reader-1 each name different slots: k is 2 of 6.
T1_AA = aa([1, 3], [2, 4])


def setup(case, **overrides):
    """The spec's default plan with ``aa-band: on``; the key is left out with aa_band=None."""
    overrides.setdefault("readers", list(READERS))
    overrides.setdefault("hypotheses", [FOUR])
    overrides.setdefault("aa_band", "on")
    return Setup(case, **overrides)


def done(case, **overrides):
    s = setup(case, **overrides)
    result = s.frozen_run()
    return s, result, s.result_lines()


def starting(lines, prefix):
    return [x for x in lines if x.startswith(prefix)]


def no_band_text(case, lines):
    """No line of the revision 5 TIE spec: no band, no margin, no TIE."""
    case.assertEqual(starting(lines, "A/A band"), [])
    case.assertEqual([x for x in lines if "margin:" in x], [])
    case.assertEqual(starting(lines, "TIE:"), [])
    case.assertEqual([x for x in lines if "verdict: TIE" in x], [])


class TieRuleCase(unittest.TestCase):
    def test_t1_a_margin_inside_the_band_is_a_tie(self):
        s, result, lines = done(self, fake_reader=FOUR_TWO + T1_AA)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        for text in (result.text.splitlines(), lines):
            self.assertIn("A/A gate: passed (4 of 12 valid A/A reads non-TIE, at any strength; "
                          "threshold 1/2)", text)
            self.assertIn("A/A band: identical drafts picked a side in 2 of 6 valid A/A "
                          "pairs; band 2 pairs", text)
            self.assertIn("hypothesis h1 margin: 2 pairs (skills-top 4 picks, base 2 picks) "
                          "against band 2 pairs", text)
            self.assertIn(VERDICT_TIE, text)
            self.assertIn("TIE: h1: the margin of 2 pairs is inside this run's A/A band "
                          "(identical drafts picked a side in 2 of 6 pairs). The versions are "
                          "not shown to differ.", text)
            self.assertIn(SECOND_SUPPORTED, text)
            # Revision 4 printed this flag for the same reads; a TIE has none.
            self.assertEqual(starting(text, "hypothesis h1 flag"), [])
        # the lines sit where the spec puts them
        at = lines.index(VERDICT_TIE)
        self.assertTrue(lines[at + 1].startswith("TIE: h1: "))
        self.assertEqual(lines[at + 2], SECOND_SUPPORTED)
        self.assertTrue(lines[at + 3].startswith("hypothesis h1 margin: "))
        self.assertTrue(lines[at + 4].startswith("hypothesis h1 family "))
        interval = lines.index([x for x in lines if x.startswith("A/A gate interval: ")][0])
        self.assertTrue(lines[interval + 1].startswith("A/A band: "))
        # the verdict TIE has no "holds only one way" sentence
        self.assertEqual([x for x in lines if "holds only when" in x], [])

    def test_t2_a_margin_above_the_band_stays_supported(self):
        s, result, lines = done(self, fake_reader=FOUR_TWO + aa([1], [2]))
        self.assertIn("A/A band: identical drafts picked a side in 1 of 6 valid A/A pairs; "
                      "band 1 pairs", lines)
        self.assertIn(VERDICT_SUPPORTED, lines)
        self.assertIn("hypothesis h1 margin: 2 pairs (skills-top 4 picks, base 2 picks) "
                      "against band 1 pairs", lines)
        self.assertEqual(starting(lines, "TIE:"), [])
        self.assertIn(FLAG_P, lines)

    def test_t3_all_tie_a_a_has_band_zero(self):
        s, result, lines = done(self, fake_reader=FOUR_TWO)
        self.assertIn("A/A band: identical drafts picked a side in 0 of 6 valid A/A pairs; "
                      "band 0 pairs", lines)
        self.assertIn(VERDICT_SUPPORTED, lines)
        self.assertEqual(starting(lines, "TIE:"), [])

    def test_t4_the_unit_is_the_pair(self):
        # Reads 1, 3 and 5 are each in a different pair: no pair has two non-TIE reads.
        s, result, lines = done(self, fake_reader=FOUR_TWO + aa([1, 3, 5]))
        self.assertIn("A/A gate: passed (3 of 12 valid A/A reads non-TIE, at any strength; "
                      "threshold 1/2)", lines)
        # Counting reads, as revision 4's unit does, would give a band of 3: a TIE here.
        self.assertIn("A/A band: identical drafts picked a side in 0 of 6 valid A/A pairs; "
                      "band 0 pairs", lines)
        self.assertIn(VERDICT_SUPPORTED, lines)

    def test_t7_a_negative_margin_is_inside_the_band(self):
        rules = glance(range(1, 5), range(5, 11))
        s, result, lines = done(self, fake_reader=rules, hypotheses=[TWO])
        self.assertIn("A/A band: identical drafts picked a side in 0 of 6 valid A/A pairs; "
                      "band 0 pairs", lines)
        self.assertIn("hypothesis h1 margin: -1 pairs (skills-top 2 picks, base 3 picks) "
                      "against band 0 pairs", lines)
        self.assertIn(VERDICT_TIE, lines)
        self.assertIn("TIE: h1: the margin of -1 pairs is inside this run's A/A band "
                      "(identical drafts picked a side in 0 of 6 pairs). The versions are "
                      "not shown to differ.", lines)

    def test_t8_refuted_is_untouched(self):
        rules = glance(range(1, 5), range(5, 13)) + T1_AA
        s, result, lines = done(self, fake_reader=rules, hypotheses=[WITH_REFUTED])
        self.assertIn("hypothesis h1 verdict: REFUTED [not blind: 0 reads left out]", lines)
        self.assertEqual(starting(lines, "hypothesis h1 margin"), [])
        self.assertEqual(starting(lines, "TIE:"), [])
        self.assertIn("A/A band: identical drafts picked a side in 2 of 6 valid A/A pairs; "
                      "band 2 pairs", lines)

    def test_t9_inconclusive_is_untouched(self):
        s, result, lines = done(self, fake_reader=FOUR_TWO + T1_AA, hypotheses=[FIVE])
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]",
                      lines)
        self.assertEqual(starting(lines, "hypothesis h1 margin"), [])
        self.assertEqual(starting(lines, "TIE:"), [])
        self.assertEqual([x for x in lines if "verdict: TIE" in x], [])
        self.assertIn("A/A band: identical drafts picked a side in 2 of 6 valid A/A pairs; "
                      "band 2 pairs", lines)

    def test_t10_a_tripped_gate_has_a_band_line_and_no_verdict_of_it(self):
        both = items("prefer slot A | strongly", reads=[1, 3, 5, 7, 9, 11], arm="aa")
        both += items("prefer slot B | strongly", reads=[2, 4, 6, 8, 10, 12], arm="aa")
        s, result, lines = done(self, fake_reader=FOUR_TWO + both)
        self.assertIn("A/A band: identical drafts picked a side in 6 of 6 valid A/A pairs; "
                      "band 6 pairs", lines)
        self.assertIn("hypothesis h1 reason: the A/A gate tripped", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]",
                      lines)
        self.assertEqual(starting(lines, "hypothesis h1 margin"), [])
        self.assertEqual(starting(lines, "TIE:"), [])

    def test_t11_no_band_when_the_gate_is_not_evaluated(self):
        s, result, lines = done(self, fake_reader=FOUR_TWO + ["aa | omit PREFER | read 1"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("A/A gate: not evaluated (11 valid reads of 12 planned)", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]",
                      lines)
        no_band_text(self, lines)

    def test_t12_not_blind_reads_stay_out(self):
        readers = ["reader-1 | fake | family m1", "reader-2 | fake | family m2 | not-blind"]
        rules = glance([1, 2, 3, 4]) + aa([1, 7, 9], [2, 8, 10])
        s, result, lines = done(self, readers=readers, fake_reader=rules, hypotheses=[TWO])
        self.assertIn("A/A band: identical drafts picked a side in 1 of 3 valid A/A pairs; "
                      "band 1 pairs", lines)
        # Counting reader-2's two side-picking pairs would give a band of 2 and a TIE.
        self.assertIn("hypothesis h1 verdict: SUPPORTED [not blind: 6 reads left out]", lines)
        self.assertIn("hypothesis h1 margin: 2 pairs (skills-top 2 picks, base 0 picks) "
                      "against band 1 pairs", lines)
        self.assertEqual(starting(lines, "TIE:"), [])

    def test_t13_the_family_rule_comes_first(self):
        rules = glance(range(1, 7)) + T1_AA
        s, result, lines = done(self, fake_reader=rules, hypotheses=[THREE],
                                versions=versions("model m1"))
        self.assertIn("hypothesis h1 reason: the other family did not agree", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]",
                      lines)
        self.assertEqual(starting(lines, "hypothesis h1 margin"), [])
        self.assertEqual(starting(lines, "TIE:"), [])

    def test_t14_a_lifted_verdict_is_tested_too(self):
        rules = [PREFER_GLANCE, OMIT_1] + T1_AA
        s, result, lines = done(self, fake_reader=rules, hypotheses=[FIVE_OF_SIX],
                                min_valid_reads="5")
        self.assertIn("hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly "
                      "counts as a pick [not blind: 0 reads left out]", lines)
        self.assertIn(LIFT_5, lines)
        self.assertIn("hypothesis h1 margin: 5 pairs (skills-top 5 picks, base 0 picks) "
                      "against band 2 pairs", lines)
        self.assertEqual(starting(lines, "TIE:"), [])

    def test_t14b_lifted_then_tie_prints_no_reason_line(self):
        # A reading the plan pinned (the spec says the reason lines of revision 4 are not used
        # for TIE): a lift that ends in TIE prints no `lifted from INCONCLUSIVE` reason line.
        rules = glance(range(3, 9), range(9, 13)) + [OMIT_1] + T1_AA
        s, result, lines = done(self, fake_reader=rules, hypotheses=[THREE_OF_SIX],
                                min_valid_reads="5")
        self.assertIn("hypothesis h1 verdict: TIE [not blind: 0 reads left out]", lines)
        self.assertIn("hypothesis h1 margin: 1 pairs (skills-top 3 picks, base 2 picks) "
                      "against band 2 pairs", lines)
        self.assertEqual(starting(lines, "hypothesis h1 reason:"), [])
        self.assertEqual(len(starting(lines, "TIE: h1: ")), 1)

    def test_t25_a_tie_prints_no_flag_even_when_p_is_below_alpha(self):
        # A reading the plan pinned: a TIE never reaches the flag block, even where the
        # evidence p is below alpha. Arithmetic: 2 readers x 8 reads = 8 pairs, so P = n = 8
        # and the band is k. Reads 1-14 of the A/A arm pair up as 7 pairs naming different
        # slots, so k = 7 and b = 7 (14 of 16 reads non-TIE, under the raised 9/10 threshold,
        # so the gate passes). The comparison has 7 pairs for skills-top, 0 for base, 1 pair
        # of unmatched reads: margin 7 <= 7 is TIE, and p = 1/128 two-sided 2/128 < 0.05.
        # A mutant that lets TIE fall through to `elif p < plan.alpha` prints
        # "hypothesis h1 flag: evidence disagrees: INCONCLUSIVE ..." and turns this red.
        rules = glance(range(1, 15)) + aa(range(1, 15, 2), range(2, 15, 2))
        s, result, lines = done(self, fake_reader=rules, reads_per_reader="8",
                                noise_threshold="9/10", hypotheses=[FOUR])
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertTrue([x for x in lines if x.startswith("hypothesis h1 verdict: TIE")], lines)
        evidence = starting(lines, "hypothesis h1 evidence: ")
        self.assertEqual(len(evidence), 1)
        self.assertIn("p = 0.0", evidence[0])
        self.assertEqual(starting(lines, "hypothesis h1 flag:"), [])

    def test_t15_scoring_twice_gives_the_same_tie(self):
        s, result, lines = done(self, fake_reader=FOUR_TWO + T1_AA)
        first = s.read("result-1.txt")
        again = s.score()
        self.assertEqual(again.exit_code, 0, again.error)
        self.assertEqual(s.read("result-1.txt"), first)
        second = s.result_lines(2)
        self.assertEqual(starting(second, "TIE: h1: "), starting(lines, "TIE: h1: "))
        self.assertEqual(len(starting(second, "TIE: h1: ")), 1)
        self.assertIn(VERDICT_TIE, second)


# Comparison reads 1, 3 and 5 fail, so pairs 1 to 3 of reader-1 are not valid: 3 of 6 comparison
# pairs are valid and all 3 prefer skills-top (margin 3). A/A pairs 1 to 4 each name different
# slots: k is 4 of 6 on a noise-threshold raised to 3/4 (8 of 12 reads are non-TIE).
PLANNED_RULES = (glance(range(1, 13)) + aa([1, 3, 5, 7], [2, 4, 6, 8])
                 + ["omit PREFER | read %d" % n for n in (1, 3, 5)])


class PlannedPairsCase(unittest.TestCase):
    def test_t26_p_is_the_planned_blind_pairs_not_the_valid_ones(self):
        s, result, lines = done(self, fake_reader=PLANNED_RULES, hypotheses=[TWO],
                                noise_threshold="3/4")
        self.assertEqual(result.exit_code, 1, result.error)  # failed reads: exit 1, as in T11
        self.assertIn("missing c1: 3 of 12 planned reads (failed 3, not run 0), costing 3 of 6 "
                      "planned pairs", lines)
        self.assertIn("hypothesis h1 pair counts: valid=3 base=0 skills-top=3 tie=0", lines)
        # P = 6 planned pairs: band ceil(4 * 6 / 6) = 4. Counting the 3 valid pairs (the
        # mutant at ab.py band_of's call) gives band 2, and the margin of 3 stays SUPPORTED.
        self.assertIn("A/A band: identical drafts picked a side in 4 of 6 valid A/A pairs; "
                      "band 4 pairs", lines)
        self.assertIn("hypothesis h1 margin: 3 pairs (skills-top 3 picks, base 0 picks) "
                      "against band 4 pairs", lines)
        self.assertIn(VERDICT_TIE, lines)
        self.assertEqual(len(starting(lines, "TIE: h1: the margin of 3 pairs")), 1)


class PooledBandCase(RunsBase):
    """The band of a run that pools: A/A pairs are formed inside each run and scaled by share."""

    def pooled(self, first, **overrides):
        overrides.setdefault("fake_reader", FOUR_TWO)
        overrides.setdefault("hypotheses", [FOUR])
        return setup(self, aa_pool=[rel(first, "plan.txt.freeze")], **overrides)

    def first(self, **overrides):
        overrides.setdefault("hypotheses", [FOUR])
        first = setup(self, **overrides)
        self.freeze_ok(first)
        result = first.run()
        self.assertEqual(result.exit_code, 0, result.error)
        return first

    def run_pooled(self, second):
        self.freeze_ok(second)
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        return result.text.splitlines()

    def test_t5_the_pool_scales_the_band(self):
        first = self.first(fake_reader=FOUR_TWO + T1_AA)
        lines = self.run_pooled(self.pooled(first))
        self.assertIn("A/A pool: 1 earlier runs, 24 valid A/A reads in the gate", lines)
        self.assertIn("A/A band: identical drafts picked a side in 2 of 12 valid A/A pairs; "
                      "band 1 pairs", lines)
        # An unscaled count (band 2) would give TIE.
        self.assertIn(VERDICT_SUPPORTED, lines)
        self.assertIn("hypothesis h1 margin: 2 pairs (skills-top 4 picks, base 2 picks) "
                      "against band 1 pairs", lines)
        self.assertEqual(starting(lines, "TIE:"), [])

    def test_t6_the_band_rounds_up(self):
        first = self.first(fake_reader=FOUR_TWO + aa([1], [2]))
        rules = glance(range(1, 7), range(7, 11))
        lines = self.run_pooled(self.pooled(first, fake_reader=rules, hypotheses=[THREE]))
        self.assertIn("A/A band: identical drafts picked a side in 1 of 12 valid A/A pairs; "
                      "band 1 pairs", lines)
        # Rounding down (band 0) would give SUPPORTED.
        self.assertIn(VERDICT_TIE, lines)
        self.assertIn("TIE: h1: the margin of 1 pairs is inside this run's A/A band "
                      "(identical drafts picked a side in 1 of 12 pairs). The versions are "
                      "not shown to differ.", lines)

    def test_t16_an_extension_measures_its_first_run_with_the_first_runs_own_band(self):
        # Reading of the case, flagged in the report: an extension must carry its first run's
        # fake-reader rules unchanged (only the sample size may differ), so the extension's A/A
        # reads follow the first run's rules and are not "all TIE" as the spec's T16 says. The
        # pooled arithmetic is therefore: k 2 + 2 of n 12, P 12, band 4, margin 4.
        first = self.first(fake_reader=FOUR_TWO + T1_AA)
        second = setup(self, extends=rel(first, "plan.txt.freeze"), fake_reader=FOUR_TWO + T1_AA,
                       reads_per_reader="6", hypotheses=[FOUR])
        lines = self.run_pooled(second)
        self.assertIn("hypothesis h1 rule at the pooled pairs: SUPPORTED if skills-top "
                      "preferred in 8 or more", lines)
        self.assertIn("A/A band: identical drafts picked a side in 4 of 12 valid A/A pairs; "
                      "band 4 pairs", lines)
        self.assertIn("hypothesis h1 margin: 4 pairs (skills-top 8 picks, base 4 picks) "
                      "against band 4 pairs", lines)
        # The first run's verdict is its own, with its own band (2 of 6): TIE. Without the
        # band it would print `first run SUPPORTED`.
        self.assertIn("hypothesis h1 extension: first run TIE, pooled TIE", lines)
        self.assertIn(VERDICT_TIE, lines)

    def test_t27_a_first_run_margin_between_its_own_band_and_the_pooled_band(self):
        """Career's "T25" request is this test; T25 is already taken in this file.

        First run: 5 pairs for skills-top, 1 for base (margin 4), A/A k 2 of 6 (own band 2):
        SUPPORTED. The extension carries the same fake-reader lines, so pooled k is 4 of 12
        (band 4), pooled pairs 10 to 2 (margin 8, above 4): pooled SUPPORTED. The first run's
        own band (2) and the pooled band (4) give different verdicts for the first run: with
        the pooled band it would read `first run TIE`.
        """
        rules = glance(range(1, 11), range(11, 13)) + T1_AA
        first = self.first(fake_reader=rules)
        own = first.result_lines()
        self.assertIn("A/A band: identical drafts picked a side in 2 of 6 valid A/A pairs; "
                      "band 2 pairs", own)
        self.assertIn("hypothesis h1 margin: 4 pairs (skills-top 5 picks, base 1 picks) "
                      "against band 2 pairs", own)
        self.assertIn(VERDICT_SUPPORTED, own)
        second = setup(self, extends=rel(first, "plan.txt.freeze"), fake_reader=rules,
                       reads_per_reader="6", hypotheses=[FOUR])
        lines = self.run_pooled(second)
        self.assertIn("A/A band: identical drafts picked a side in 4 of 12 valid A/A pairs; "
                      "band 4 pairs", lines)
        self.assertIn("hypothesis h1 margin: 8 pairs (skills-top 10 picks, base 2 picks) "
                      "against band 4 pairs", lines)
        self.assertEqual(starting(lines, "hypothesis h1 extension: "),
                         ["hypothesis h1 extension: first run SUPPORTED, pooled SUPPORTED"])

    def test_t27_the_first_runs_own_band_also_counts_planned_pairs(self):
        first = setup(self, fake_reader=PLANNED_RULES, hypotheses=[TWO], noise_threshold="3/4")
        self.assertEqual(first.frozen_run().exit_code, 1)
        second = setup(self, extends=rel(first, "plan.txt.freeze"), fake_reader=PLANNED_RULES,
                       noise_threshold="3/4", reads_per_reader="6", hypotheses=[TWO])
        self.freeze_ok(second)
        result = second.run()
        self.assertEqual(result.exit_code, 1, result.error)
        lines = result.text.splitlines()
        # The first run's verdict is its own, with its own band of 4 (6 planned pairs): TIE.
        # The valid-pair count (3) gives band 2 and `first run SUPPORTED`.
        self.assertEqual(starting(lines, "hypothesis h1 extension: "),
                         ["hypothesis h1 extension: first run TIE, pooled TIE"])

    def test_t20_a_pooled_run_need_not_carry_the_key(self):
        first = self.first(fake_reader=FOUR_TWO + T1_AA, aa_band=None)
        self.assertNotIn("aa-band", first.read("plan.txt"))
        lines = self.run_pooled(self.pooled(first))
        self.assertIn("A/A pool: 1 earlier runs, 24 valid A/A reads in the gate", lines)
        self.assertIn("A/A band: identical drafts picked a side in 2 of 12 valid A/A pairs; "
                      "band 1 pairs", lines)
        self.assertIn(VERDICT_SUPPORTED, lines)


class KeyCase(RunsBase):
    def test_t18_only_on_freezes(self):
        for value in ("off", "yes", "On", ""):
            with self.subTest(value=value):
                s = setup(self, fake_reader=FOUR_TWO, aa_band=value)
                result = s.freeze()
                self.assertEqual((result.exit_code, result.ran), (2, False))
                lines = result.error.splitlines()
                self.assertEqual(len(lines), 1, lines)
                self.assertTrue(lines[0].startswith("plan line %d: " % s.line_of("aa-band")),
                                lines)
                self.assertFalse(s.exists("plan.txt.freeze"))
        with self.subTest(value="a repeated line"):
            s = setup(self, fake_reader=FOUR_TWO)
            s.edit("plan.txt", lambda text: text + "aa-band: on\n")
            result = s.freeze()
            self.assertEqual(result.exit_code, 2)
            lines = result.error.splitlines()
            self.assertEqual(lines, ["plan line %d: the key aa-band is given twice"
                                     % len(s.read("plan.txt").splitlines())])
            self.assertFalse(s.exists("plan.txt.freeze"))
        with self.subTest(value="on"):
            s = setup(self, fake_reader=FOUR_TWO)
            self.assertEqual(s.freeze().exit_code, 0)
        for how, change in (("changed", lambda t: t.replace("aa-band: on", "aa-band: off")),
                            ("removed", lambda t: t.replace("aa-band: on\n", ""))):
            with self.subTest(after_freeze=how):
                s = setup(self, fake_reader=FOUR_TWO)
                self.assertEqual(s.freeze().exit_code, 0)
                s.edit("plan.txt", change)
                result = s.run()
                self.assertEqual(result.exit_code, 2)
                self.assertEqual(result.error.splitlines(),
                                 ["changed since the freeze: plan.txt"])
                self.assertFalse(s.exists(ab.READS_DIR))

    def test_t19_panel_is_unchanged(self):
        s = PanelSetup(self)
        result = s.frozen_run()
        self.assertEqual(result.exit_code, 0, result.error)
        for text in (result.text.splitlines(), s.result_lines()):
            self.assertEqual([x for x in text if "A/A band" in x or "margin" in x
                              or "TIE" in x], [])
        refused = PanelSetup(self, aa_band="on")
        result = refused.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("plan line %d: unknown key aa-band" % refused.line_of("aa-band"),
                      result.error.splitlines())
        self.assertFalse(refused.exists("plan.txt.freeze"))

    def first(self, **overrides):
        first = setup(self, fake_reader=FOUR_TWO, **overrides)
        self.freeze_ok(first)
        return first

    def test_t21_an_amendment_may_not_change_the_key(self):
        twelve = ("SUPPORTED if skills-top preferred in 8 or more; otherwise INCONCLUSIVE")
        wide = glance(range(1, 17), range(17, 25))
        for what, first_key, second_key in (("dropped", "on", None), ("added", None, "on")):
            with self.subTest(what=what):
                first = self.first(aa_band=first_key)
                second = setup(self, fake_reader=wide, hypotheses=[twelve],
                               reads_per_reader="12", aa_band=second_key,
                               amends=rel(first, "plan.txt.freeze"))
                self.assertEqual(self.refused(second), [AMEND])
        with self.subTest(what="kept"):
            first = self.first()
            second = setup(self, fake_reader=wide, hypotheses=[twelve], reads_per_reader="12",
                           amends=rel(first, "plan.txt.freeze"))
            self.freeze_ok(second)

    def test_t22_an_extension_may_not_change_the_key(self):
        for what, first_key, second_key in (("added", None, "on"), ("removed", "on", None)):
            with self.subTest(what=what):
                first = self.first(aa_band=first_key)
                self.assertEqual(first.run().exit_code, 0)
                second = setup(self, fake_reader=FOUR_TWO, reads_per_reader="12",
                               aa_band=second_key, extends=rel(first, "plan.txt.freeze"))
                self.assertEqual(self.refused(second), [EXTEND + "aa-band"])


class OptInCase(unittest.TestCase):
    # The line kinds revision 4 writes for this plan, read from the scorer's `out.append` calls
    # and from a result at `cc6b1c9`. A plan without the key may print no other kind.
    REVISION_4 = (
        "plan sha256: ", "freeze sha256: ", "prompt sha256: ", "A/A arm: ", "A/A version: ",
        "key ", "slot split ", "read ", "reads ", "missing ", "A/A gate", "sensitivity gate",
        "A/A slightly rate: ", "position ", "order consistency ", "hypothesis h1 rule: ",
        "hypothesis h1 pair counts: ", "hypothesis h1 verdict: ",
        "hypothesis h1 second reading ", "hypothesis h1 family ", "hypothesis h1 evidence: ",
        "hypothesis h1 flag: ", "scores ", "A/A score spread: ", "spend tally: ",
        "failed reads", "cut", "exit status: ")

    def test_t17_the_key_is_opt_in(self):
        s, result, lines = done(self, fake_reader=FOUR_TWO + T1_AA, aa_band=None)
        self.assertNotIn("aa-band", s.read("plan.txt"))
        self.assertIn("A/A gate: passed (4 of 12 valid A/A reads non-TIE, at any strength; "
                      "threshold 1/2)", lines)
        self.assertIn(VERDICT_SUPPORTED, lines)
        self.assertIn(FLAG_P, lines)
        for text in (result.text.splitlines(), lines):
            no_band_text(self, text)
            for line in text:
                self.assertTrue(line.startswith(self.REVISION_4) or line == ab.VALIDITY_LINE,
                                "a line revision 4 does not write: " + line)
        # What this compares: the freeze file is exactly one hash per input and the prompt
        # hash, as tests/test_ab.py pins it for every plan; and no result line is of a kind
        # revision 4 does not write (the whitelist of line prefixes above), so a plan without
        # the key gains no line. The review compares the whole result with the one `cc6b1c9`
        # writes for the same plan.
        names = ("plan.txt", "posting.txt", "base.txt", "skills-top.txt", "skills-top-short.txt")
        expected = ["%s  %s" % (sha256_of(s.path(name)), name) for name in names]
        expected.append("%s  %s" % (ab.prompt_sha256(), ab.PROMPT_LABEL))
        self.assertEqual(s.read("plan.txt.freeze").splitlines(), expected)


class NotBlindCase(unittest.TestCase):
    def test_t23_no_blind_reader_no_band_and_no_division_by_zero(self):
        readers = ["reader-1 | fake | family m1 | not-blind",
                   "reader-2 | fake | family m2 | not-blind"]
        s, result, lines = done(self, readers=readers, fake_reader=FOUR_TWO + T1_AA)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("A/A gate: not evaluated (0 valid reads of 0 planned)", lines)
        self.assertIn("hypothesis h1 reason: the A/A gate was not evaluated", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 12 reads left out]",
                      lines)
        no_band_text(self, lines)

    def test_t24_slot_preference_alone_does_not_widen_the_band(self):
        s, result, lines = done(self, fake_reader=FOUR_TWO + aa([1, 2, 3, 4]))
        self.assertIn("A/A gate: passed (4 of 12 valid A/A reads non-TIE, at any strength; "
                      "threshold 1/2)", lines)
        # pair_pick on the A/A arm returns the one version for two same-slot reads, which
        # would give k 2 and a TIE here; the slot letters give k 0.
        self.assertIn("A/A band: identical drafts picked a side in 0 of 6 valid A/A pairs; "
                      "band 0 pairs", lines)
        self.assertIn(VERDICT_SUPPORTED, lines)
        self.assertEqual(starting(lines, "TIE:"), [])
        self.assertIn("position aa: 4 of 4 non-TIE reads in slot A (100%): INCONCLUSIVE", lines)


if __name__ == "__main__":
    unittest.main()
