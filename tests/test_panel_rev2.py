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
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 reads left out]", lines)
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
                self.assertIn("rule r1 (l1) verdict: PASS [not blind: 0 reads left out]",
                              lines)

    def test_10_35_not_blind_counts(self):
        s, result, lines = self.done(
            readers=["r1 | fake", "r2 | fake | not-blind"], fake_reader=RANK,
            rules=["recruiter | " + SIX_PASS,
                   "overall | PASS if score at least 7 in 12 of 12; otherwise INCONCLUSIVE"])
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 3 reads left out]", lines)
        self.assertIn("rule r2 (overall) verdict: INCONCLUSIVE [not blind: 6 reads left out]",
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
        self.assertIn("rule r2 (l2) verdict: INCONCLUSIVE [not blind: 0 reads left out]",
                      lines)
        self.assertEqual([x for x in lines if x.startswith("rule r2") and "p = " in x], [])

    def test_ab_and_panel_share_the_validity_text(self):
        s, result, lines = self.done(fake_reader=RANK, rules=["recruiter | " + SIX_PASS])
        found = [x for x in lines if x.startswith("validity: ")]
        self.assertEqual(found, [reader_harness.VALIDITY_LINE])
        self.assertIs(ab.VALIDITY_LINE, reader_harness.VALIDITY_LINE)


class MissingReadsCase(unittest.TestCase):
    """Revision 2 section 6.1: missing reads, completions and the DEAD line."""

    ONE_MISSING = RANK + ["recruiter | version | omit SCORE | read 5"]

    def done(self, **overrides):
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def one_missing(self, rule, extra=()):
        return self.done(fake_reader=self.ONE_MISSING, rules=["recruiter | " + rule] + list(extra))

    def test_10_33_one_missing_version_read(self):
        s, result, lines = self.done(fake_reader=self.ONE_MISSING,
                                     rules=["recruiter | " + SIX_PASS])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("missing l1 version: 1 of 6 planned reads (failed 1, not run 0)", lines)
        self.assertIn("missing l2 version: 0 of 6 planned reads (failed 0, not run 0)", lines)
        self.assertIn("rule r1 (l1) completions (missing reads: 1): unsettled: PASS, "
                      "INCONCLUSIVE possible", lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]",
                      lines)
        self.assertEqual([x for x in lines if x.startswith("DEAD:")], [])

    def test_10_34_dead_run(self):
        s, result, lines = self.done(fake_reader=["omit SCORE"],
                                     rules=["recruiter | " + SIX_PASS])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("DEAD: 0 of 20 planned reads are valid", lines)
        for arm in ("l1", "l2"):
            self.assertIn("anchor gate %s: not evaluated (0 valid anchor reads of 4 planned)"
                          % arm, lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]",
                      lines)
        self.assertEqual([x for x in lines if " completions (" in x], [])

    def test_one_read_decides_every_score_clause_at_once(self):
        s, result, lines = self.one_missing(
            "PASS if score at least 7 in 6 of 6; FAIL if score at most 6 in 1 or more; "
            "otherwise INCONCLUSIVE")
        self.assertIn("rule r1 (l1) completions (missing reads: 1): unsettled: PASS, FAIL "
                      "possible", lines)

    def test_a_flag_clause_completes_both_ways(self):
        s, result, lines = self.one_missing(
            "FAIL if DOUBTS flagged in 1 or more; otherwise INCONCLUSIVE")
        self.assertIn("rule r1 (l1) completions (missing reads: 1): unsettled: FAIL, "
                      "INCONCLUSIVE possible", lines)

    def test_overall_completes_counted_lenses(self):
        s, result, lines = self.one_missing(
            SIX_PASS,
            ["overall | PASS if score at least 7 in 12 of 12; otherwise INCONCLUSIVE"])
        self.assertIn("rule r2 (overall) completions (missing reads: 1): unsettled: PASS, "
                      "INCONCLUSIVE possible", lines)

    def test_settled_when_the_missing_read_cannot_matter(self):
        s, result, lines = self.one_missing(
            "PASS if score at least 7 in 5 or more; otherwise INCONCLUSIVE")
        self.assertIn("rule r1 (l1) completions (missing reads: 1): settled: PASS", lines)

    def test_a_lens_not_counted_has_no_completions(self):
        s, result, lines = self.done(fake_reader=RANK + ["manager | omit SCORE | read 1"],
                                     rules=["manager | " + SIX_PASS])
        self.assertIn("missing l2 version: 0 of 6 planned reads (failed 0, not run 0)", lines)
        self.assertEqual([x for x in lines if x.startswith("rule r1 (l2) completions")], [])


    def test_no_dead_line_while_anchor_reads_are_valid(self):
        s, result, lines = self.done(fake_reader=RANK + ["version | omit SCORE"],
                                     rules=["recruiter | " + SIX_PASS])
        self.assertIn("missing l1 version: 6 of 6 planned reads (failed 6, not run 0)", lines)
        self.assertEqual([x for x in lines if x.startswith("DEAD:")], [])


RANK_9 = ["recruiter | strong | score 9", "recruiter | weak | score 2",
          "recruiter | version | score 7",
          "manager | strong | score 9", "manager | weak | score 3", "manager | version | score 7"]
RULE_6 = "recruiter | " + SIX_PASS
CANNOT = "scores %s: the version scores at or above the strong anchor; this lens cannot rank it higher"
SAME = "scores %s: every read gives the version the same score"


class ScaleCase(unittest.TestCase):
    """Revision 2 section 6.1: the top of the scale and the room above the strong anchor."""

    def done(self, **overrides):
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def test_10_31_version_below_the_strong_anchor(self):
        s, result, lines = self.done(fake_reader=RANK_9, rules=[RULE_6])
        for arm in ("l1", "l2"):
            self.assertIn("scores %s version against strong anchor: lowest version score 7, "
                          "highest strong-anchor score 9" % arm, lines)
            self.assertIn("scores %s version spread: 0 (highest 7, lowest 7)" % arm, lines)
            self.assertIn(SAME % arm, lines)
        self.assertEqual([x for x in lines if x.endswith("this lens cannot rank it higher")], [])

    def test_10_31_version_at_the_strong_anchor(self):
        reader = [x.replace("version | score 7", "version | score 9") for x in RANK_9]
        s, result, lines = self.done(
            fake_reader=reader,
            rules=["recruiter | PASS if score at least 7 in 6 of 6; otherwise INCONCLUSIVE"])
        for arm in ("l1", "l2"):
            self.assertIn(CANNOT % arm, lines)

    def test_10_32_room_above_the_strong_anchor(self):
        s, result, lines = self.done(
            fake_reader=RANK_9, rules=[RULE_6],
            lenses=["recruiter | recruiter.lens.txt | max 10", "manager | hiring-manager.lens.txt"])
        self.assertIn("scores l1 room above the strong anchor: 1 (scale maximum 10)", lines)
        self.assertEqual([x for x in lines if x.startswith("scores l2 room above")], [])

    def test_the_strong_anchors_highest_score_is_used(self):
        s, result, lines = self.done(
            fake_reader=RANK_9 + ["recruiter | strong | score 8 | read 1"],
            rules=["recruiter | " + SIX_PASS],
            lenses=["recruiter | recruiter.lens.txt | max 10", "manager | hiring-manager.lens.txt"])
        self.assertIn("scores l1 version against strong anchor: lowest version score 7, "
                      "highest strong-anchor score 9", lines)
        self.assertIn("scores l1 room above the strong anchor: 1 (scale maximum 10)", lines)

    def test_room_not_assessable_without_a_strong_read(self):
        s, result, lines = self.done(
            fake_reader=RANK_9 + ["recruiter | strong | omit SCORE"], rules=[RULE_6],
            lenses=["recruiter | recruiter.lens.txt | max 10", "manager | hiring-manager.lens.txt"])
        self.assertIn("scores l1 room above the strong anchor: not assessable "
                      "(scale maximum 10)", lines)
        self.assertIn("scores l1 version against strong anchor: not assessable", lines)

    def test_a_spread(self):
        s, result, lines = self.done(
            fake_reader=RANK_9 + ["recruiter | version | score 8 | read 5"], rules=[RULE_6])
        self.assertIn("scores l1 version spread: 1 (highest 8, lowest 7)", lines)
        self.assertNotIn(SAME % "l1", lines)

    def test_one_version_read_is_not_a_spread(self):
        s, result, lines = self.done(
            readers=["r1 | fake"], reads_per_reader="1", fake_reader=RANK_9,
            rules=["recruiter | PASS if score at least 7 in 1 of 1; otherwise INCONCLUSIVE"])
        self.assertIn("scores l1 version spread: 0 (highest 7, lowest 7)", lines)
        self.assertNotIn(SAME % "l1", lines)

    def test_no_valid_version_read(self):
        s, result, lines = self.done(
            fake_reader=RANK_9 + ["recruiter | version | omit SCORE"], rules=[RULE_6])
        self.assertIn("scores l1 version spread: not assessable", lines)
        self.assertIn("scores l1 version against strong anchor: not assessable", lines)


if __name__ == "__main__":
    unittest.main()
