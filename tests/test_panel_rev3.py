"""Tests for revision 3 of the reader panel spec (docs/specs/reader-panel.md). All data here is invented."""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from career_track_record import panel  # noqa: E402
from tests.test_panel import Setup, RANK, RANK_RECRUITER, SIX_PASS  # noqa: E402

NB = ["r1 | fake", "r2 | fake | not-blind"]
THREE_UP = "recruiter | PASS if score at least 7 in 3 or more; otherwise INCONCLUSIVE"
OVERALL_12 = "overall | PASS if score at least 7 in 12 of 12; otherwise INCONCLUSIVE"
GOLDEN = os.path.join(os.path.dirname(SRC), "tests", "fixtures", "panel", "golden")
PANEL_PROMPT_SHA256_0_7_0 = "79657b05dbea178a019140c4f8bba1fddd1eba4c044d2b191f07dd849579ae1c"
GOLDEN_PLANS = {
    "10-1": dict(fake_reader=RANK, rules=["recruiter | " + SIX_PASS]),
    "10-3": dict(fake_reader=RANK_RECRUITER + ["manager | strong | score 2", "manager | weak | score 9",
                                               "manager | version | score 9"],
                 rules=["manager | " + SIX_PASS]),
}


class PanelReaderGroupCase(unittest.TestCase):
    def done(self, **overrides):
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def grouped(self):
        return self.done(
            readers=["reader-1 | fake | reader-group f1", "reader-2 | fake | reader-group f2"],
            fake_reader=RANK, rules=["recruiter | " + SIX_PASS])

    def test_10_44_groups_count_version_and_anchor_reads(self):
        s, result, lines = self.grouped()
        self.assertEqual([x for x in lines if x.startswith("reader-group ")],
                         ["reader-group f1: 10 valid reads", "reader-group f2: 10 valid reads"])
        self.assertTrue([x for x in lines if x.startswith("rule r1 (l1) verdict: PASS [")])
        self.assertEqual(result.exit_code, 0)

    def test_the_panel_group_lines_come_just_before_the_validity_line(self):
        s, result, lines = self.grouped()
        last = max(i for i, x in enumerate(lines) if x.startswith("reader-group "))
        self.assertTrue(lines[last + 1].startswith("validity: "))


class PanelBlindOnlyCase(unittest.TestCase):
    def done(self, **overrides):
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def test_10_39_six_of_six_is_inconclusive_with_three_blind_reads(self):
        # 0.7.0: rule r1 (l1) verdict: PASS [not blind: 3 of 6 counted reads]
        s, result, lines = self.done(readers=NB, fake_reader=RANK, rules=["recruiter | " + SIX_PASS])
        for line in [
                "reads l1 strong blind readers: valid=1 of 1 planned",
                "reads l1 weak blind readers: valid=1 of 1 planned",
                "reads l1 version blind readers: valid=3 of 3 planned",
                "reads l1 version not-blind readers: valid=3",
                "anchor gate l1: passed (strong scores 9, all at least 7; weak scores 2, all at most 4)",
                "scores l1 strong: scores=1 total=9 mean=9.00 lowest=9 highest=9",
                "rule r1 (l1) count: score at least 7: 3 of 3 valid reads",
                "rule r1 (l1) verdict: INCONCLUSIVE [not blind: 3 reads left out]",
                "rule r1 (l1) evidence: score at least 7: 3 of 3 counted reads; 95% interval 0.438 to 1.000"]:
            self.assertIn(line, lines)
        self.assertFalse([x for x in lines if x.startswith("rule r1 (l1) reason:")])
        self.assertEqual(result.exit_code, 0)

    def test_a_not_blind_anchor_read_no_longer_fails_the_gate(self):
        # 0.7.0: anchor gate l1: failed (strong read l1/2 scored 5, below 7)
        # 0.7.0: rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 of 0 counted reads]
        s, result, lines = self.done(readers=NB, fake_reader=RANK + ["recruiter | strong | score 5 | read 2"],
                                     rules=[THREE_UP])
        for line in [
                "read l1/2: reader=r2 document=strong score=5 flagged=none flags=not-blind reader",
                "anchor gate l1: passed (strong scores 9, all at least 7; weak scores 2, all at most 4)",
                "lens l1: counted",
                "rule r1 (l1) verdict: PASS [not blind: 3 reads left out]"]:
            self.assertIn(line, lines)
        self.assertEqual(result.exit_code, 0)

    def test_10_35_overall_twelve_of_twelve_is_inconclusive(self):
        # 0.7.0: rule r2 (overall) verdict: PASS [not blind: 6 of 12 counted reads]
        s, result, lines = self.done(readers=NB, fake_reader=RANK,
                                     rules=["recruiter | " + SIX_PASS, OVERALL_12])
        for line in [
                "rule r2 (overall) count: score at least 7: 6 of 6 valid reads",
                "rule r2 (overall) verdict: INCONCLUSIVE [not blind: 6 reads left out]",
                "rule r1 (l1) verdict: INCONCLUSIVE [not blind: 3 reads left out]"]:
            self.assertIn(line, lines)
        self.assertEqual(result.exit_code, 0)

    def test_a_failed_not_blind_anchor_read_leaves_the_gate_evaluated(self):
        # 0.7.0: anchor gate l1: not evaluated (3 valid anchor reads of 4 planned)
        s, result, lines = self.done(readers=NB, fake_reader=RANK + ["recruiter | strong | omit SCORE | read 2"],
                                     rules=[THREE_UP])
        for line in [
                "reads l1 strong blind readers: valid=1 of 1 planned",
                "anchor gate l1: passed (strong scores 9, all at least 7; weak scores 2, all at most 4)",
                "lens l1: counted",
                "rule r1 (l1) verdict: PASS [not blind: 3 reads left out]"]:
            self.assertIn(line, lines)
        self.assertEqual(result.exit_code, 1)

    def test_every_reader_not_blind_counts_nothing(self):
        # 0.7.0: rule r1 (l1) verdict: PASS [not blind: 6 of 6 counted reads]
        s, result, lines = self.done(readers=["r1 | fake | not-blind", "r2 | fake | not-blind"],
                                     fake_reader=RANK, rules=["recruiter | " + SIX_PASS, OVERALL_12])
        for line in [
                "reads l1 strong blind readers: valid=0 of 0 planned",
                "reads l1 version blind readers: valid=0 of 0 planned",
                "anchor gate l1: not evaluated (0 valid anchor reads of 0 planned)",
                "lens l1: not counted (the anchor gate was not evaluated on l1)",
                "counted lenses: none",
                "missing l1 version: 0 of 0 planned reads (failed 0, not run 0)",
                "rule r1 (l1) verdict: INCONCLUSIVE [not blind: 6 reads left out]",
                "rule r1 (l1) reason: the anchor gate was not evaluated on l1",
                "rule r2 (overall) verdict: INCONCLUSIVE [not blind: 12 reads left out]",
                "rule r2 (overall) reason: no lens is counted",
                "scores l1 version spread: not assessable"]:
            self.assertIn(line, lines)
        self.assertFalse([x for x in lines if x.startswith("DEAD")])
        self.assertEqual(result.exit_code, 0)

    def test_flag_counts_are_blind_only(self):
        # 0.7.0: flagged l1 version DOUBTS: 1 of 6 valid reads
        s, result, lines = self.done(
            readers=NB, fake_reader=RANK + ['recruiter | version | write "thin" in DOUBTS | read 8'],
            rules=["recruiter | PASS if DOUBTS not flagged in 3 or more; otherwise INCONCLUSIVE"])
        for line in [
                "flagged l1 version DOUBTS: 0 of 3 valid reads",
                "rule r1 (l1) count: DOUBTS not flagged: 3 of 3 valid reads",
                "rule r1 (l1) verdict: PASS [not blind: 3 reads left out]"]:
            self.assertIn(line, lines)

    def test_missing_reads_and_the_suffix_count_blind_reads_only(self):
        # 0.7.0: missing l1 version: 1 of 6 planned reads (failed 1, not run 0)
        # 0.7.0: rule r1 (l1) verdict: INCONCLUSIVE [not blind: 2 of 5 counted reads]
        s, result, lines = self.done(readers=NB, fake_reader=RANK + ["recruiter | version | omit SCORE | read 8"],
                                     rules=["recruiter | " + SIX_PASS])
        for line in [
                "missing l1 version: 0 of 3 planned reads (failed 0, not run 0)",
                "reads l1 version not-blind readers: valid=2",
                "rule r1 (l1) verdict: INCONCLUSIVE [not blind: 2 reads left out]"]:
            self.assertIn(line, lines)
        self.assertFalse([x for x in lines if x.startswith("rule r1 (l1) completions")])
        self.assertEqual(result.exit_code, 1)

    def test_scores_count_blind_reads_only(self):
        # 0.7.0: scores l1 version: scores=6 total=38 mean=6.33 lowest=3 highest=7
        # 0.7.0: scores l1 version spread: 4 (highest 7, lowest 3)
        s, result, lines = self.done(readers=NB, fake_reader=RANK + ["recruiter | version | score 3 | read 8"],
                                     rules=[THREE_UP])
        for line in [
                "scores l1 version: scores=3 total=21 mean=7.00 lowest=7 highest=7",
                "scores l1 reader r1 version: scores=3 total=21 mean=7.00 lowest=7 highest=7",
                "scores l1 version against strong anchor: lowest version score 7, highest strong-anchor score 9",
                "scores l1 version spread: 0 (highest 7, lowest 7)",
                "scores l1: every read gives the version the same score"]:
            self.assertIn(line, lines)
        self.assertFalse([x for x in lines if x.startswith("scores l1 reader r2 ")])

    def test_10_62_results_without_a_not_blind_reader_match_0_7_0(self):
        for name in sorted(GOLDEN_PLANS):
            with self.subTest(name=name):
                s = Setup(self, **GOLDEN_PLANS[name])
                result = s.frozen_run()
                with open(os.path.join(GOLDEN, name + ".txt"), encoding="utf-8", newline="") as handle:
                    golden = handle.read()
                want = re.sub(r" \[not blind: ([0-9]+) of [0-9]+ counted reads\]",
                              r" [not blind: \1 reads left out]", golden)
                self.assertEqual(result.text, want)

    def test_the_prompt_is_unchanged_from_0_7_0(self):
        self.assertEqual(panel.prompt_sha256(), PANEL_PROMPT_SHA256_0_7_0)


ONE_MISSING = RANK + ["recruiter | version | omit SCORE | read 5"]
FIVE_OF_SIX = "recruiter | PASS if score at least 7 in 5 of 6; otherwise INCONCLUSIVE"
BACKWARDS = ["recruiter | strong | score 2", "recruiter | weak | score 9",
             "recruiter | version | score 7"] + RANK[3:]
LIFT_5 = ("rule r1 (l1) reason: lifted from INCONCLUSIVE: settled under every completion of "
          "1 missing reads; read floor 5 met")


class PanelReadFloorCase(unittest.TestCase):
    def done(self, **overrides):
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def test_10_40_below_the_floor(self):
        s, result, lines = self.done(fake_reader=ONE_MISSING, rules=["recruiter | " + SIX_PASS],
                                     min_valid_reads="6")
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertIn("rule r1 (l1) reason: below the read floor (5 counted reads, floor 6)", lines)
        self.assertEqual(result.exit_code, 1)

    def test_at_the_floor_an_unsettled_rule_stays_as_it_is(self):
        s, result, lines = self.done(fake_reader=ONE_MISSING, rules=["recruiter | " + SIX_PASS],
                                     min_valid_reads="5")
        self.assertIn("rule r1 (l1) completions (missing reads: 1): unsettled: PASS, "
                      "INCONCLUSIVE possible", lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertFalse([x for x in lines if x.startswith("rule r1 (l1) reason:")])

    def test_10_41_without_a_floor_nothing_is_lifted(self):
        s, result, lines = self.done(fake_reader=ONE_MISSING, rules=[FIVE_OF_SIX])
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertIn("rule r1 (l1) completions (missing reads: 1): settled: PASS", lines)
        self.assertFalse([x for x in lines if x.startswith("rule r1 (l1) reason:")])
        self.assertEqual(result.exit_code, 1)

    def test_10_41_a_floor_met_lifts_a_settled_completion(self):
        s, result, lines = self.done(fake_reader=ONE_MISSING, rules=[FIVE_OF_SIX],
                                     min_valid_reads="5")
        verdict = "rule r1 (l1) verdict: PASS [not blind: 0 reads left out]"
        self.assertIn(verdict, lines)
        self.assertEqual(lines[lines.index(verdict) + 1], LIFT_5)
        own = [x for x in lines if x.startswith("rule r1 (l1) ")]
        self.assertEqual(own[-1], "rule r1 (l1) completions (missing reads: 1): settled: PASS")
        self.assertEqual(result.exit_code, 1)

    def test_10_42_nothing_is_lifted_under_the_gate(self):
        s, result, lines = self.done(
            fake_reader=BACKWARDS + ["recruiter | version | omit SCORE | read 5"],
            rules=[FIVE_OF_SIX], min_valid_reads="5")
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        gate = lines.index("rule r1 (l1) reason: the anchor gate failed on l1")
        self.assertEqual(lines[gate + 1],
                         "rule r1 (l1) reason: below the read floor (0 counted reads, floor 5)")
        self.assertFalse([x for x in lines if "lifted from" in x])
        self.assertFalse([x for x in lines if x.startswith("rule r1 (l1) completions")])

    def test_no_counted_lens_gives_both_reasons(self):
        s, result, lines = self.done(
            fake_reader=["recruiter | score 5", "manager | score 5",
                         "recruiter | version | omit SCORE | read 5"],
            rules=["overall | PASS if score at least 5 in 11 of 12; otherwise INCONCLUSIVE"],
            min_valid_reads="1")
        self.assertIn("counted lenses: none", lines)
        gate = lines.index("rule r1 (overall) reason: no lens is counted")
        self.assertEqual(lines[gate + 1],
                         "rule r1 (overall) reason: below the read floor (0 counted reads, floor 1)")
        self.assertFalse([x for x in lines if "lifted from" in x])

    def test_a_settled_fail_is_lifted(self):
        s, result, lines = self.done(
            fake_reader=RANK + ["recruiter | version | score 3",
                                "recruiter | version | omit SCORE | read 5"],
            rules=["recruiter | FAIL if score at most 4 in 5 of 6; otherwise INCONCLUSIVE"],
            min_valid_reads="5")
        self.assertIn("rule r1 (l1) completions (missing reads: 1): settled: FAIL", lines)
        self.assertIn("rule r1 (l1) verdict: FAIL [not blind: 0 reads left out]", lines)
        self.assertIn(LIFT_5, lines)

    def test_a_settled_inconclusive_lifts_nothing(self):
        s, result, lines = self.done(
            fake_reader=RANK + ["recruiter | version | score 5",
                                "recruiter | version | omit SCORE | read 5"],
            rules=["recruiter | " + SIX_PASS], min_valid_reads="5")
        self.assertIn("rule r1 (l1) completions (missing reads: 1): settled: INCONCLUSIVE", lines)
        self.assertFalse([x for x in lines if x.startswith("rule r1 (l1) reason:")])

    def test_no_missing_read_means_no_lift(self):
        s, result, lines = self.done(
            fake_reader=RANK,
            rules=["recruiter | FAIL if score at most 4 in 5 of 6; otherwise INCONCLUSIVE"],
            min_valid_reads="5")
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertFalse([x for x in lines if x.startswith("rule r1 (l1) completions")
                          or x.startswith("rule r1 (l1) reason:")])

    def test_an_overall_rule_is_lifted_too(self):
        s, result, lines = self.done(
            fake_reader=ONE_MISSING,
            rules=["overall | PASS if score at least 7 in 11 of 12; otherwise INCONCLUSIVE"],
            min_valid_reads="11")
        self.assertIn("rule r1 (overall) verdict: PASS [not blind: 0 reads left out]", lines)
        self.assertIn("rule r1 (overall) reason: lifted from INCONCLUSIVE: settled under every "
                      "completion of 1 missing reads; read floor 11 met", lines)
        self.assertIn("rule r1 (overall) completions (missing reads: 1): settled: PASS", lines)

    def test_the_floor_counts_blind_reads_only(self):
        s, result, lines = self.done(readers=NB, fake_reader=RANK, rules=[THREE_UP],
                                     min_valid_reads="4")
        self.assertIn("rule r1 (l1) reason: below the read floor (3 counted reads, floor 4)", lines)

    def test_min_valid_reads_refusals(self):
        for value in ("0", "x"):
            with self.subTest(value=value):
                s = Setup(self, fake_reader=RANK, min_valid_reads=value)
                result = s.freeze()
                self.assertEqual(result.exit_code, 2, result.error)
                number = s.line_of("min-valid-reads")
                self.assertIn("plan line %d: min-valid-reads must be a positive whole number"
                              % number, result.error.splitlines())
                self.assertFalse(s.exists("plan.txt.freeze"))


if __name__ == "__main__":
    unittest.main()
