"""Tests for revision 3 of the Reader A/B spec (docs/specs/reader-ab.md). All data here is invented."""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab  # noqa: E402
from tests.test_ab import (  # noqa: E402
    PREFER_GLANCE, SIX, TOO_LONG, WITHOUT_GLANCE, WRITE_TOO_LONG, Setup, items)

NB = ["r1 | fake", "r2 | fake | not-blind"]
THREE = "SUPPORTED if skills-top preferred in 3 or more; otherwise INCONCLUSIVE"
REFUTED_AT_TWO = "REFUTED if base preferred in 2 or more; otherwise INCONCLUSIVE"
GOLDEN = os.path.join(ROOT, "tests", "fixtures", "ab", "golden")
AB_PROMPT_SHA256_0_7_0 = "567b9bc16d86abfe4af935a844e28a1b6d2d257aa4f93b6ab3de8e97ce1fdd14"

GOLDEN_PLANS = {
    "10-1": dict(hypotheses=[SIX], fake_reader=[PREFER_GLANCE]),
    "10-8": dict(hypotheses=[SIX], fake_reader=[PREFER_GLANCE]
                 + items("random seed 1 non-tie", arm="aa", strength="strongly")),
    "10-9": dict(hypotheses=[SIX], fake_reader=[PREFER_GLANCE, "omit PREFER | read 1"]),
    "10-11": dict(hypotheses=[SIX], mechanisms=[TOO_LONG],
                  fake_reader=items(WRITE_TOO_LONG, reads=[1, 2, 3, 4])),
}


class BlindOnlyCase(unittest.TestCase):
    def done(self, **overrides):
        overrides.setdefault("hypotheses", [SIX])
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def test_10_71_six_of_six_is_inconclusive_with_three_blind_reads(self):
        # 0.7.0: hypothesis h1 verdict: SUPPORTED [not blind: 3 of 6 valid reads]
        s, result, lines = self.done(readers=NB, fake_reader=[PREFER_GLANCE])
        self.assertIn("reads blind readers c1: valid=3 base=0 skills-top=3 tie=0", lines)
        self.assertIn("reads not-blind readers c1: valid=3 base=0 skills-top=3 tie=0", lines)
        self.assertIn("hypothesis h1 counts: valid=3 base=0 skills-top=3 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 3 reads left out]", lines)
        self.assertIn("A/A gate: passed (0 of 3 valid A/A reads clearly or strongly "
                      "non-TIE; threshold 1/2)", lines)
        self.assertIn("hypothesis h1 evidence: skills-top 3 of 3 non-TIE picks, 0 TIE; "
                      "p = 0.2500 two-sided (reads may be correlated; may be too small); "
                      "95% interval 0.438 to 1.000", lines)
        self.assertFalse([x for x in lines if x.startswith("hypothesis h1 reason:")])
        self.assertFalse([x for x in lines if x.startswith("hypothesis h1 flag:")])
        self.assertEqual(result.exit_code, 0)

    def test_or_more_clause_loses_the_not_blind_picks(self):
        # 0.7.0: hypothesis h1 verdict: REFUTED [not blind: 3 of 6 valid reads]
        s, result, lines = self.done(
            readers=NB, fake_reader=items(WITHOUT_GLANCE, reads=[1, 2, 4, 5]))
        self.assertIn("hypothesis h1 counts: valid=3 base=2 skills-top=0 tie=1", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 3 reads left out]", lines)
        self.assertIn("position c1: 1 of 2 non-TIE picks in slot A (50%): no slot bias", lines)

    def test_not_blind_aa_noise_no_longer_trips_the_gate(self):
        # 0.7.0: A/A gate: tripped (3 of 6 valid A/A reads clearly or strongly non-TIE, 50%;
        # threshold 1/2) and hypothesis h1 verdict: INCONCLUSIVE [not blind: 3 of 6 valid reads]
        s, result, lines = self.done(
            readers=NB, hypotheses=[THREE],
            fake_reader=[PREFER_GLANCE]
            + items("random seed 1 non-tie", reads=[4, 5, 6], arm="aa", strength="strongly"))
        self.assertIn("A/A gate: passed (0 of 3 valid A/A reads clearly or strongly "
                      "non-TIE; threshold 1/2)", lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED [not blind: 3 reads left out]", lines)
        self.assertFalse([x for x in lines if x.startswith("hypothesis h1 reason:")])
        self.assertEqual(result.exit_code, 0)

    def test_a_failed_not_blind_aa_read_leaves_the_gate_evaluated(self):
        # 0.7.0: A/A gate: not evaluated (5 valid reads of 6 planned) and
        # hypothesis h1 verdict: INCONCLUSIVE [not blind: 3 of 6 valid reads]
        s, result, lines = self.done(
            readers=NB, hypotheses=[THREE],
            fake_reader=[PREFER_GLANCE, "aa | omit PREFER | read 4"])
        self.assertIn("A/A gate: passed (0 of 3 valid A/A reads clearly or strongly "
                      "non-TIE; threshold 1/2)", lines)
        self.assertIn("missing aa: 0 of 3 planned reads (failed 0, not run 0)", lines)
        self.assertIn("read aa/4: reader=r2 A=skills-top B=skills-top FAILED (missing PREFER)",
                      lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED [not blind: 3 reads left out]", lines)
        self.assertIn("failed reads: 1", lines)
        self.assertEqual(result.exit_code, 1)

    def test_position_counts_blind_picks_only(self):
        # 0.7.0: position c1: 3 of 6 non-TIE picks in slot A (50%): no slot bias and
        # hypothesis h1 verdict: REFUTED [not blind: 3 of 6 valid reads]
        s, result, lines = self.done(
            readers=NB, hypotheses=[REFUTED_AT_TWO],
            fake_reader=items("prefer slot A", reads=[1, 2, 3])
            + items("prefer slot B", reads=[4, 5, 6]))
        self.assertIn("hypothesis h1 counts: valid=3 base=2 skills-top=1 tie=0", lines)
        self.assertIn("position c1: 3 of 3 non-TIE picks in slot A (100%): INCONCLUSIVE", lines)
        self.assertIn("position overall: 3 of 3 non-TIE picks in slot A (100%): INCONCLUSIVE",
                      lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 3 reads left out]", lines)
        self.assertIn("hypothesis h1 reason: position is INCONCLUSIVE on c1", lines)

    def test_mechanism_count_and_floor_are_blind_only(self):
        # 0.7.0: mechanism too long in c1 count: 4 of 6 valid reads and
        # mechanism too long in c1 verdict: SUPPORTED (SUPPORTED at 3 or more)
        # [not blind: 3 of 6 valid reads]
        s, result, lines = self.done(
            readers=NB, mechanisms=[TOO_LONG],
            fake_reader=items(WRITE_TOO_LONG, reads=[1, 4, 5, 6]))
        self.assertIn("mechanism too long in c1 count: 1 of 3 valid reads", lines)
        self.assertIn("mechanism too long in c1 A/A floor: 0 of 3 valid reads", lines)
        self.assertIn("mechanism too long in c1 verdict: INCONCLUSIVE "
                      "(SUPPORTED at 3 or more) [not blind: 3 reads left out]", lines)

    def test_every_reader_not_blind_counts_nothing(self):
        # 0.7.0: hypothesis h1 verdict: SUPPORTED [not blind: 6 of 6 valid reads]
        s, result, lines = self.done(
            readers=["r1 | fake | not-blind", "r2 | fake | not-blind"],
            fake_reader=[PREFER_GLANCE])
        self.assertIn("A/A gate: not evaluated (0 valid reads of 0 planned)", lines)
        self.assertIn("hypothesis h1 counts: valid=0 base=0 skills-top=0 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 6 reads left out]", lines)
        self.assertIn("hypothesis h1 reason: the A/A gate was not evaluated", lines)
        self.assertIn("hypothesis h1 evidence: no non-TIE pick, 0 TIE; "
                      "p and interval not computed", lines)
        self.assertIn("reads blind readers c1: valid=0 base=0 skills-top=0 tie=0", lines)
        self.assertFalse([x for x in lines if x.startswith("DEAD")])
        self.assertEqual(result.exit_code, 0)

    def test_the_suffix_counts_valid_not_blind_reads_only(self):
        # 0.7.0: hypothesis h1 verdict: INCONCLUSIVE [not blind: 2 of 5 valid reads]
        s, result, lines = self.done(
            readers=NB, fake_reader=[PREFER_GLANCE, "omit PREFER | read 4"])
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 2 reads left out]", lines)
        self.assertIn("missing c1: 0 of 3 planned reads (failed 0, not run 0)", lines)
        self.assertEqual(result.exit_code, 1)

    def test_10_62_results_without_a_not_blind_reader_match_0_7_0(self):
        for name, overrides in GOLDEN_PLANS.items():
            with self.subTest(golden=name):
                s = Setup(self, **overrides)
                result = s.frozen_run()
                with open(os.path.join(GOLDEN, name + ".txt"), encoding="utf-8",
                          newline="") as handle:
                    golden = handle.read()
                # Slice 5 will add the `sensitivity gate: not tested` line to this transformation.
                want = re.sub(r" \[not blind: ([0-9]+) of [0-9]+ valid reads\]",
                              r" [not blind: \1 reads left out]", golden)
                self.assertEqual(result.text, want)

    def test_the_prompt_is_unchanged_from_0_7_0(self):
        self.assertEqual(ab.prompt_sha256(), AB_PROMPT_SHA256_0_7_0)

    def test_scores_count_blind_reads_only(self):
        # 0.7.0: A/A score spread: 8 (highest 9, lowest 1); scores c1 version base: scores=6 total=26 mean=4.33
        s, result, lines = self.done(
            readers=NB,
            fake_reader=items("score 9 1", reads=[4, 5, 6], arm="aa") + items("score 9 1", reads=[4, 5, 6]))
        self.assertIn("A/A score spread: 0 (highest 5, lowest 5)", lines)
        self.assertIn("scores c1 version base: scores=3 total=15 mean=5.00", lines)
        self.assertIn("scores c1 separation: 3 of 3 valid reads give both slots the same score",
                      lines)
        self.assertFalse([x for x in lines if x.startswith("scores c1 reader r2 ")])


class ReaderGroupCase(unittest.TestCase):
    def done(self, **overrides):
        overrides.setdefault("hypotheses", [SIX])
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def assertRefused(self, s, line_text, message):
        """Freeze exits 2, names the plan line number, and writes no freeze file."""
        result = s.freeze()
        self.assertEqual(result.exit_code, 2, result.error)
        self.assertFalse(result.ran)
        number = s.line_of(line_text)
        self.assertIn("plan line %d: %s" % (number, message), result.error.splitlines())
        self.assertFalse(s.exists("plan.txt.freeze"))
        self.assertFalse(s.exists(ab.READS_DIR))

    def two_groups(self):
        return self.done(readers=["r1 | fake | reader-group g2", "r2 | fake | reader-group g1"],
                         fake_reader=[PREFER_GLANCE])

    def test_10_76_one_group_counts_every_valid_read(self):
        s, result, lines = self.done(
            readers=["reader-1 | fake | reader-group f1", "reader-2 | fake | reader-group f1"],
            fake_reader=[PREFER_GLANCE])
        self.assertIn("reader-group f1: 12 valid reads", lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED [not blind: 0 reads left out]", lines)
        self.assertEqual(result.exit_code, 0)

    def test_groups_are_listed_in_order_of_first_appearance(self):
        s, result, lines = self.two_groups()
        self.assertEqual([x for x in lines if x.startswith("reader-group ")],
                         ["reader-group g2: 6 valid reads", "reader-group g1: 6 valid reads"])

    def test_a_group_counts_not_blind_reads_and_skips_failed_ones(self):
        s, result, lines = self.done(
            readers=["r1 | fake | not-blind | reader-group g", "r2 | fake | reader-group g"],
            fake_reader=[PREFER_GLANCE, "omit PREFER | read 1"])
        self.assertIn("reader-group g: 11 valid reads", lines)

    def test_no_group_line_without_a_group(self):
        s, result, lines = self.done(fake_reader=[PREFER_GLANCE])
        self.assertFalse([x for x in lines if x.startswith("reader-group ")])

    def test_the_group_lines_come_just_before_the_validity_line(self):
        s, result, lines = self.two_groups()
        i = lines.index("reader-group g2: 6 valid reads")
        self.assertEqual(lines[i + 1], "reader-group g1: 6 valid reads")
        self.assertTrue(lines[i + 2].startswith("validity: "))

    def test_reader_group_fields_freeze_and_parse(self):
        s = Setup(self, hypotheses=[SIX],
                  readers=["r1 | fake | reader-group a-1",
                           "r2 | fake | cost 2 | not-blind | reader-group B2",
                           "r3 | fake"])
        result = s.freeze()
        self.assertEqual(result.exit_code, 0, result.error)
        readers = s.plan.readers
        self.assertEqual([r.group for r in readers], ["a-1", "B2", None])
        self.assertTrue(readers[1].not_blind)

    def test_reader_group_refusals(self):
        extra = ("a reader's extra field is not-blind, cost <n> or reader-group <name>, "
                 "once each: ")
        cases = [
            ("r1 | fake | reader-group g | reader-group h", "reader-group h",
             extra + "reader-group h"),
            ("r1 | fake | reader-group a_b", "a_b",
             "a name holds letters, digits and - only: a_b"),
            ("r1 | fake | reader-group", "| reader-group", extra + "reader-group"),
        ]
        for reader, line_text, message in cases:
            with self.subTest(reader=reader):
                s = Setup(self, hypotheses=[SIX], readers=[reader, "r2 | fake"])
                self.assertRefused(s, line_text, message)


if __name__ == "__main__":
    unittest.main()
