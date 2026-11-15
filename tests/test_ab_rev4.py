"""Tests for revision 4 of the Reader A/B spec (docs/specs/reader-ab.md, tests 10.77 to 10.94).
All data here is invented.

The plans here name their readers reader-1 and reader-2, as the spec's default plan does, so
that the lines the spec gives are asserted as they are written.
"""

import os
import shutil
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab  # noqa: E402
from tests.test_ab import (  # noqa: E402
    EIGHT, PREFER_GLANCE, SIX, TOO_LONG, WITHOUT_GLANCE, WRITE_TOO_LONG, Setup, items,
    sha256_of)

READERS = ["reader-1 | fake | family m1", "reader-2 | fake | family m2"]
BOTH_M1 = ["reader-1 | fake | family m1", "reader-2 | fake | family m1"]
ODD_MESSAGE = "reads-per-reader must be an even number, read in pairs (revision 4)"
THREE = "SUPPORTED if skills-top preferred in 3 or more; otherwise INCONCLUSIVE"
FIVE = "SUPPORTED if skills-top preferred in 5 or more; otherwise INCONCLUSIVE"
# 10.83 (b): skills-top is preferred on reader-1's reads only.
READER_1_ONLY = items(PREFER_GLANCE, reads=[1, 2, 3, 4, 5, 6])
EARLIER = ("frozen under an earlier revision: plan.txt has no family on a reader or no "
           "drafted-by on a version; score it with the release that froze it, or rewrite it "
           "as a new plan")


def versions(skills_top="user", base="user"):
    """The default versions, with who drafted skills-top and base."""
    return ["base | base.txt | drafted-by " + base,
            "skills-top | skills-top.txt | drafted-by " + skills_top,
            "skills-top-short | skills-top-short.txt | drafted-by user"]


def reasons(lines):
    return [x for x in lines if x.startswith("hypothesis h1 reason: ")]


def setup(case, **overrides):
    overrides.setdefault("readers", list(READERS))
    overrides.setdefault("hypotheses", [SIX])
    return Setup(case, **overrides)


def done(case, **overrides):
    s = setup(case, **overrides)
    result = s.frozen_run()
    return s, result, s.result_lines()


class PairRuleCase(unittest.TestCase):
    def test_10_77_an_odd_read_count_is_refused_at_freeze(self):
        for value in ("3", "5"):
            with self.subTest(reads_per_reader=value):
                s = setup(self, reads_per_reader=value)
                result = s.freeze()
                self.assertEqual((result.exit_code, result.ran), (2, False))
                self.assertEqual(result.error.splitlines(), [
                    "plan line %d: %s" % (s.line_of("reads-per-reader"), ODD_MESSAGE)])
                self.assertFalse(s.exists("plan.txt.freeze"))
        s = setup(self, reads_per_reader="6")
        self.assertEqual(s.freeze().exit_code, 0)

    def test_10_1_under_the_default_read_count(self):
        # With no reads-per-reader line, each reader reads 6 times: 12 reads per arm.
        s, result, lines = done(self, reads_per_reader=None, fake_reader=[PREFER_GLANCE])
        self.assertEqual(s.plan.reads_per_reader, 6)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("missing c1: 0 of 12 planned reads (failed 0, not run 0), costing 0 of 6 "
                      "planned pairs", lines)
        self.assertIn("hypothesis h1 pair counts: valid=6 base=0 skills-top=6 tie=0", lines)
        self.assertIn("hypothesis h1 evidence: skills-top 6 of 6 non-TIE paired picks, 0 TIE; "
                      "p = 0.0313 two-sided (reads may be correlated; may be too small); "
                      "95% interval 0.609 to 1.000", lines)

    def test_10_78_each_pair_is_one_paired_pick(self):
        s, result, lines = done(self, fake_reader=[PREFER_GLANCE])
        self.assertIn("reads all readers c1: valid=12 base=0 skills-top=12 tie=0", lines)
        self.assertIn("hypothesis h1 pair counts: valid=6 base=0 skills-top=6 tie=0", lines)
        self.assertIn("order consistency reader-1 c1: 3 of 3 pairs pick the same version in "
                      "both orders", lines)
        self.assertIn("order consistency reader-2 c1: 3 of 3 pairs pick the same version in "
                      "both orders", lines)
        self.assertIn("hypothesis h1 family m1: skills-top 3 of 3 paired picks", lines)
        self.assertIn("hypothesis h1 family m2: skills-top 3 of 3 paired picks", lines)

    def test_10_79_an_order_split_pair_is_a_tie(self):
        s, result, lines = done(self, fake_reader=["prefer slot A"])
        self.assertIn("hypothesis h1 evidence: no non-TIE paired pick, 6 TIE; p and interval "
                      "not computed", lines)
        self.assertIn("hypothesis h1 pair counts: valid=6 base=0 skills-top=0 tie=6", lines)
        for reader in ("reader-1", "reader-2"):
            self.assertIn("order consistency %s c1: 0 of 3 pairs pick the same version in "
                          "both orders" % reader, lines)

    def test_order_consistency_follows_position_overall(self):
        s, result, lines = done(self, fake_reader=[PREFER_GLANCE])
        at = lines.index([x for x in lines if x.startswith("position overall: ")][0])
        self.assertTrue(lines[at + 1].startswith("order consistency reader-1 c1: "))
        self.assertTrue(lines[at + 2].startswith("order consistency reader-2 c1: "))
        self.assertTrue(lines[at + 3].startswith("hypothesis h1 rule: "))

    def test_a_pick_and_a_tie_in_one_pair_is_a_tie(self):
        # Read 1 picks skills-top and read 2 is a TIE: that pair is a TIE; the other pairs pick.
        rules = items(PREFER_GLANCE, reads=[1] + list(range(3, 13)))
        s, result, lines = done(self, fake_reader=rules)
        self.assertIn("hypothesis h1 pair counts: valid=6 base=0 skills-top=5 tie=1", lines)
        self.assertIn("order consistency reader-1 c1: 2 of 2 pairs pick the same version in "
                      "both orders", lines)

    def test_a_failed_read_costs_its_pair(self):
        s, result, lines = done(self, fake_reader=[PREFER_GLANCE, "omit PREFER | read 1",
                                                   "omit PREFER | read 2",
                                                   "omit PREFER | read 3"])
        self.assertIn("missing c1: 3 of 12 planned reads (failed 3, not run 0), costing 2 of 6 "
                      "planned pairs", lines)
        self.assertIn("hypothesis h1 pair counts: valid=4 base=0 skills-top=4 tie=0", lines)
        # Reads 1 and 2 are a pair with both reads missing; it may complete either way.
        self.assertIn("hypothesis h1 completions (missing pairs: 2): unsettled: SUPPORTED, "
                      "INCONCLUSIVE possible; p from 0.0313 to 0.3750", lines)

    def test_order_consistency_is_printed_for_blind_readers_only(self):
        readers = ["reader-1 | fake | family m1", "reader-2 | fake | family m2 | not-blind"]
        s, result, lines = done(self, readers=readers, fake_reader=[PREFER_GLANCE])
        self.assertEqual([x for x in lines if x.startswith("order consistency ")], [
            "order consistency reader-1 c1: 3 of 3 pairs pick the same version in both orders"])


class AaGateCase(unittest.TestCase):
    def test_10_80_slightly_aa_picks_trip_the_gate(self):
        s, result, lines = done(self, fake_reader=[PREFER_GLANCE,
                                                   "aa | prefer slot A | slightly"])
        self.assertIn("A/A gate: tripped (12 of 12 valid A/A reads non-TIE, at any strength, "
                      "100%; threshold 1/2)", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertIn("hypothesis h1 reason: the A/A gate tripped", lines)
        self.assertIn("A/A slightly rate: 12 of 12 valid A/A reads are slightly", lines)
        self.assertIn("A/A gate interval: 0.757 to 1.000 (95%, Wilson)", lines)

    def test_10_81_the_slightly_rate_and_a_passing_gate(self):
        s, result, lines = done(self, fake_reader=[
            PREFER_GLANCE, "aa | prefer slot A | slightly | read 1",
            "aa | prefer slot B | clearly | read 2"])
        self.assertIn("A/A slightly rate: 1 of 12 valid A/A reads are slightly", lines)
        self.assertIn("A/A gate: passed (2 of 12 valid A/A reads non-TIE, at any strength; "
                      "threshold 1/2)", lines)
        self.assertIn("A/A gate interval: 0.046 to 0.449 (95%, Wilson)", lines)

    def test_the_slightly_rate_follows_the_gate_interval(self):
        s, result, lines = done(self, fake_reader=[PREFER_GLANCE])
        at = lines.index([x for x in lines if x.startswith("A/A gate interval: ")][0])
        self.assertEqual(lines[at + 1], "A/A slightly rate: 0 of 12 valid A/A reads are slightly")

    def test_the_slightly_rate_counts_blind_readers_only(self):
        # Reads 7 to 12 of the A/A arm are reader-2's, who is not blind: they are left out.
        readers = ["reader-1 | fake | family m1", "reader-2 | fake | family m2 | not-blind"]
        reader_2_slightly = items("prefer slot A | slightly", reads=[7, 8, 9, 10, 11, 12],
                                  arm="aa")
        s, result, lines = done(self, readers=readers,
                                fake_reader=[PREFER_GLANCE] + reader_2_slightly)
        self.assertIn("A/A slightly rate: 0 of 6 valid A/A reads are slightly", lines)
        self.assertIn("A/A gate: passed (0 of 6 valid A/A reads non-TIE, at any strength; "
                      "threshold 1/2)", lines)


class MechanismMarginCase(unittest.TestCase):
    def test_10_85_a_mechanism_needs_a_margin_over_its_floor(self):
        s, result, lines = done(self, mechanisms=[TOO_LONG],
                                fake_reader=items(WRITE_TOO_LONG, reads=EIGHT))
        self.assertIn("mechanism too long in c1 margin: Fisher exact p = 0.0013 two-sided "
                      "against the A/A floor", lines)
        self.assertIn("mechanism too long in c1 verdict: SUPPORTED (SUPPORTED at 3 or more) "
                      "(what readers wrote, not a cause) [not blind: 0 reads left out]", lines)
        self.assertFalse([x for x in lines if x.startswith("mechanism too long in c1 reason")])
        # Revision 3's count, 4 of the 12 reads: above the floor, but with no margin.
        s, result, lines = done(self, mechanisms=[TOO_LONG],
                                fake_reader=items(WRITE_TOO_LONG, reads=[1, 2, 3, 4]))
        self.assertIn("mechanism too long in c1 count: 4 of 12 valid reads", lines)
        self.assertIn("mechanism too long in c1 separation: separates the versions from the "
                      "A/A floor", lines)
        self.assertIn("mechanism too long in c1 margin: Fisher exact p = 0.0932 two-sided "
                      "against the A/A floor", lines)
        self.assertIn("mechanism too long in c1 verdict: INCONCLUSIVE (SUPPORTED at 3 or more) "
                      "(what readers wrote, not a cause) [not blind: 0 reads left out]", lines)
        self.assertIn("mechanism too long in c1 reason: no margin over the A/A floor", lines)

    def test_the_margin_is_compared_with_the_plans_alpha(self):
        s, result, lines = done(self, mechanisms=[TOO_LONG], alpha="0.001",
                                fake_reader=items(WRITE_TOO_LONG, reads=EIGHT))
        self.assertIn("mechanism too long in c1 margin: Fisher exact p = 0.0013 two-sided "
                      "against the A/A floor", lines)
        self.assertIn("mechanism too long in c1 verdict: INCONCLUSIVE (SUPPORTED at 3 or more) "
                      "(what readers wrote, not a cause) [not blind: 0 reads left out]", lines)
        self.assertIn("mechanism too long in c1 reason: no margin over the A/A floor", lines)

    def test_the_margin_reason_comes_first(self):
        s, result, lines = done(self, mechanisms=[TOO_LONG], min_valid_reads="7",
                                fake_reader=items(WRITE_TOO_LONG, reads=[1, 2, 3, 4]))
        reasons = [x for x in lines if x.startswith("mechanism too long in c1 reason: ")]
        self.assertEqual(reasons, [
            "mechanism too long in c1 reason: no margin over the A/A floor",
            "mechanism too long in c1 reason: below the read floor (6 valid pairs, floor 7)"])

    def test_no_margin_without_a_valid_read_in_an_arm(self):
        s, result, lines = done(self, mechanisms=[TOO_LONG],
                                fake_reader=["aa | omit PREFER", "all | omit PREFER"])
        self.assertIn("mechanism too long in c1 margin: not computed (an arm has no valid "
                      "read)", lines)

    def test_the_margin_line_follows_the_separation_line(self):
        s, result, lines = done(self, mechanisms=[TOO_LONG],
                                fake_reader=items(WRITE_TOO_LONG, reads=EIGHT))
        at = lines.index("mechanism too long in c1 separation: separates the versions from "
                         "the A/A floor")
        self.assertTrue(lines[at + 1].startswith("mechanism too long in c1 margin: "))
        self.assertTrue(lines[at + 2].startswith("mechanism too long in c1 verdict: "))


class ReadFloorCase(unittest.TestCase):
    def test_10_90_the_read_floor_counts_pairs(self):
        s, result, lines = done(self, fake_reader=[PREFER_GLANCE, "omit PREFER | read 1"],
                                min_valid_reads="6")
        self.assertIn("hypothesis h1 reason: below the read floor (5 valid pairs, floor 6)",
                      lines)
        s, result, lines = done(self, fake_reader=[PREFER_GLANCE], min_valid_reads="12")
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertIn("hypothesis h1 reason: below the read floor (6 valid pairs, floor 12)",
                      lines)

    def test_position_blocks_a_lift(self):
        # The rule alone is INCONCLUSIVE (it needs all 6 pairs) and every completion is
        # SUPPORTED, so only the position stands in the lift's way.
        s, result, lines = done(
            self, hypotheses=["SUPPORTED if skills-top preferred in 0 of 6; otherwise "
                              "INCONCLUSIVE"],
            min_valid_reads="5", fake_reader=["prefer slot A", "omit PREFER | read 2"])
        self.assertIn("position c1: 11 of 11 non-TIE reads in slot A (100%): INCONCLUSIVE", lines)
        self.assertIn("hypothesis h1 completions (missing pairs: 1): settled: SUPPORTED; p from "
                      "1.0000 to 1.0000", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertEqual(reasons(lines), ["hypothesis h1 reason: position is INCONCLUSIVE on c1"])
        self.assertFalse([x for x in lines if "lifted from" in x])


class SensitivityPairsCase(unittest.TestCase):
    def test_the_sensitivity_missing_line_counts_pairs(self):
        s = setup(self, versions=["base | base.txt | drafted-by user",
                                  "skills-top | skills-top.txt | drafted-by user",
                                  "base-weak | base-weak.txt | drafted-by user"],
                  sensitivity="base vs base-weak", sensitivity_scope=["^hours to "],
                  fake_reader=[PREFER_GLANCE, 's | prefer containing "ninety minutes"',
                               "s | omit PREFER | read 7"])
        shutil.copyfile(os.path.join(ROOT, "tests", "fixtures", "ab", "base-weak.txt"),
                        s.path("base-weak.txt"))
        result = s.frozen_run()
        lines = s.result_lines()
        self.assertEqual(result.exit_code, 1)
        self.assertIn("missing s: 1 of 12 planned reads (failed 1, not run 0), costing 1 of 6 "
                      "planned pairs", lines)
        self.assertIn("sensitivity gate: not evaluated (5 valid pairs of 6 planned)", lines)


class FamilyRuleCase(unittest.TestCase):
    def test_10_83_a_the_other_family_agrees(self):
        s, result, lines = done(self, versions=versions("model m1"), fake_reader=[PREFER_GLANCE])
        self.assertIn("hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly counts as a pick [not blind: 0 reads left out]", lines)
        self.assertEqual(reasons(lines), [])
        self.assertIn("hypothesis h1 family m2: skills-top 3 of 3 paired picks", lines)

    def test_10_83_b_the_other_family_did_not_agree(self):
        s, result, lines = done(self, versions=versions("model m1"), hypotheses=[THREE],
                                fake_reader=READER_1_ONLY)
        self.assertIn("hypothesis h1 pair counts: valid=6 base=0 skills-top=3 tie=3", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertEqual(reasons(lines), ["hypothesis h1 reason: the other family did not agree"])
        self.assertIn("hypothesis h1 family m1: skills-top 3 of 3 paired picks", lines)
        self.assertIn("hypothesis h1 family m2: skills-top 0 of 3 paired picks", lines)
        # The family reason, like the gates', leaves no flag line.
        self.assertFalse([x for x in lines if x.startswith("hypothesis h1 flag:")])
        # The control: drafted by the user, the same reads are SUPPORTED.
        s, result, lines = done(self, hypotheses=[THREE], fake_reader=READER_1_ONLY)
        self.assertIn("hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly counts as a pick [not blind: 0 reads left out]", lines)

    def test_10_83_c_too_few_pairs_from_another_family(self):
        s, result, lines = done(self, versions=versions("model m1"), hypotheses=[FIVE],
                                fake_reader=[PREFER_GLANCE, "omit PREFER | read 7"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("hypothesis h1 pair counts: valid=5 base=0 skills-top=5 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertEqual(reasons(lines), [
            "hypothesis h1 reason: too few pairs from another family"])
        self.assertIn("hypothesis h1 family m2: skills-top 2 of 2 paired picks", lines)

    def test_the_share_is_rounded_up(self):
        # The other family has 1 pick in 3 valid pairs; a share of 3 of 6 asks for 2 of 3.
        rules = items(PREFER_GLANCE, reads=[1, 2, 3, 4, 5, 6, 7, 8])
        s, result, lines = done(self, versions=versions("model m1"), hypotheses=[THREE],
                                fake_reader=rules)
        self.assertIn("hypothesis h1 family m2: skills-top 1 of 3 paired picks", lines)
        self.assertEqual(reasons(lines), ["hypothesis h1 reason: the other family did not agree"])

    def test_10_84_a_no_reader_of_another_family(self):
        s, result, lines = done(self, versions=versions("model m1"), readers=BOTH_M1,
                                fake_reader=[PREFER_GLANCE])
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertEqual(reasons(lines), ["hypothesis h1 reason: no reader of another family"])
        self.assertIn("hypothesis h1 family m1: skills-top 6 of 6 paired picks", lines)
        self.assertFalse([x for x in lines if x.startswith("hypothesis h1 family m2")])

    def test_10_84_b_unknown_is_checked_with_each_family_as_the_drafter(self):
        s, result, lines = done(self, versions=versions("unknown"), fake_reader=[PREFER_GLANCE])
        self.assertIn("hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly counts as a pick [not blind: 0 reads left out]", lines)
        s, result, lines = done(self, versions=versions("unknown"), hypotheses=[THREE],
                                fake_reader=READER_1_ONLY)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertEqual(reasons(lines), ["hypothesis h1 reason: the other family did not agree"])
        s, result, lines = done(self, versions=versions("unknown"), readers=BOTH_M1,
                                fake_reader=[PREFER_GLANCE])
        self.assertEqual(reasons(lines), ["hypothesis h1 reason: no reader of another family"])

    def test_10_84_c_a_refuted_verdict_favours_the_version_its_clause_names(self):
        s, result, lines = done(self, versions=versions(base="model m1"),
                                fake_reader=[WITHOUT_GLANCE])
        self.assertIn("hypothesis h1 verdict: REFUTED; the verdict holds only when slightly counts as a pick [not blind: 0 reads left out]", lines)
        self.assertIn("hypothesis h1 family m2: skills-top 0 of 3 paired picks", lines)
        s, result, lines = done(self, versions=versions(base="model m1"), readers=BOTH_M1,
                                fake_reader=[WITHOUT_GLANCE])
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertEqual(reasons(lines), ["hypothesis h1 reason: no reader of another family"])

    def test_every_family_of_a_drafted_by_list_drafts(self):
        s, result, lines = done(self, versions=versions("model m3, model m1"),
                                hypotheses=[THREE], fake_reader=READER_1_ONLY)
        self.assertEqual(reasons(lines), ["hypothesis h1 reason: the other family did not agree"])

    def test_families_compare_after_lower_casing(self):
        for skills_top, readers in (("model M1", READERS),
                                    ("model m1", ["reader-1 | fake | family M1",
                                                  "reader-2 | fake | family m2"])):
            with self.subTest(skills_top=skills_top, readers=readers):
                s, result, lines = done(self, versions=versions(skills_top), readers=readers,
                                        hypotheses=[THREE], fake_reader=READER_1_ONLY)
                self.assertEqual(reasons(lines), [
                    "hypothesis h1 reason: the other family did not agree"])
                self.assertIn("hypothesis h1 family m1: skills-top 3 of 3 paired picks", lines)

    def test_a_not_blind_reader_is_not_another_family(self):
        readers = READERS + ["reader-3 | fake | family m2 | not-blind"]
        rules = READER_1_ONLY + items(PREFER_GLANCE, reads=[13, 14, 15, 16, 17, 18])
        s, result, lines = done(self, versions=versions("model m1"), readers=readers,
                                hypotheses=[THREE], fake_reader=rules)
        self.assertEqual(reasons(lines), ["hypothesis h1 reason: the other family did not agree"])
        self.assertIn("hypothesis h1 family m2: skills-top 0 of 3 paired picks", lines)

    def test_a_lifted_verdict_meets_the_family_rule(self):
        # reader-1 and reader-2 are of m1, the drafting family; reader-3 is of m2. Read 1
        # fails, so the rule alone is INCONCLUSIVE and every completion is SUPPORTED; the
        # lift would carry it, but reader-3 has 2 of the 3 picks a share of 7 of 9 asks for.
        readers = ["reader-1 | fake | family m1", "reader-2 | fake | family m1",
                   "reader-3 | fake | family m2"]
        rule = "SUPPORTED if skills-top preferred in 7 of 9; otherwise INCONCLUSIVE"
        rules = (items(PREFER_GLANCE, reads=list(range(2, 17))) + ["omit PREFER | read 1"])
        s, result, lines = done(self, versions=versions("model m1"), readers=readers,
                                hypotheses=[rule], fake_reader=rules, min_valid_reads="8")
        self.assertIn("hypothesis h1 completions (missing pairs: 1): settled: SUPPORTED; "
                      "p from 0.0078 to 0.0156", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertEqual(reasons(lines), ["hypothesis h1 reason: the other family did not agree"])
        self.assertFalse([x for x in lines if "lifted from" in x])
        # The control: drafted by the user, the same reads are lifted to SUPPORTED.
        s, result, lines = done(self, readers=readers, hypotheses=[rule], fake_reader=rules,
                                min_valid_reads="8")
        self.assertIn("hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly counts as a pick [not blind: 0 reads left out]", lines)
        self.assertIn("hypothesis h1 reason: lifted from INCONCLUSIVE: settled under every "
                      "completion of 1 missing pairs; read floor of 8 pairs met", lines)

    def test_the_family_lines_follow_the_reasons(self):
        s, result, lines = done(self, versions=versions("model m1"), hypotheses=[THREE],
                                fake_reader=READER_1_ONLY)
        at = lines.index("hypothesis h1 reason: the other family did not agree")
        self.assertEqual(lines[at + 1], "hypothesis h1 second reading (slightly as TIE): "
                         "INCONCLUSIVE")
        self.assertEqual(lines[at + 2], "hypothesis h1 family m1: skills-top 3 of 3 paired picks")
        self.assertEqual(lines[at + 3], "hypothesis h1 family m2: skills-top 0 of 3 paired picks")
        self.assertTrue(lines[at + 4].startswith("hypothesis h1 evidence: "))


class PlanFormsCase(unittest.TestCase):
    def refused(self, s, line_text, message):
        result = s.freeze()
        self.assertEqual((result.exit_code, result.ran), (2, False))
        self.assertIn("plan line %d: %s" % (s.line_of(line_text), message),
                      result.error.splitlines())
        self.assertFalse(s.exists("plan.txt.freeze"))

    def test_10_89_drafted_by_and_family_are_required_at_freeze(self):
        forms = ("drafted-by is user, third-party, unknown or model <family>, with more models "
                 "as a comma list: ")
        s = setup(self, versions=["base | base.txt"] + versions()[1:])
        self.refused(s, "base | base.txt", "a version needs drafted-by (revision 4): base")
        for bad in ("drafted-by model", "drafted-by models m1", "drafted-by me",
                    "drafted-by model m1,model m2", "written-by user"):
            with self.subTest(bad=bad):
                s = setup(self, versions=["base | base.txt | " + bad] + versions()[1:])
                self.refused(s, "base | base.txt", forms + bad)
        s = setup(self, versions=["base | base.txt | drafted-by user | x"] + versions()[1:])
        self.refused(s, "base | base.txt", forms + "x")
        s = setup(self, readers=["reader-1 | fake", "reader-2 | fake | family m2"])
        self.refused(s, "reader-1 | fake", "a reader needs a family (revision 4): reader-1")
        s = setup(self, readers=["reader-1 | fake | family m_1", "reader-2 | fake | family m2"])
        self.refused(s, "reader-1 | fake", "a family is one token of letters, digits and -: m_1")
        s = setup(self, readers=["reader-1 | fake | family m1 | family m2",
                                 "reader-2 | fake | family m2"])
        self.refused(s, "reader-1 | fake", "a reader's extra fields may be not-blind, cost "
                     "<n>, reader-group <name> and family <name>, each at most once: family m2")
        s = setup(self, versions=versions("model M1, model m3"))
        self.assertEqual(s.freeze().exit_code, 0)
        self.assertEqual(s.plan.drafted_by["skills-top"], ("m1", "m3"))
        for who in ("user", "third-party", "unknown"):
            self.assertEqual(setup(self, versions=versions(who)).plan.drafted_by["skills-top"],
                             who)

    def test_10_89_a_lower_cased_drafter_with_10_83_a_reads(self):
        s, result, lines = done(self, versions=versions("model M1, model m3"),
                                fake_reader=[PREFER_GLANCE])
        self.assertIn("hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly counts as a pick [not blind: 0 reads left out]", lines)

    def test_a_family_and_a_reader_group_are_separate(self):
        s = setup(self, readers=["reader-1 | fake | reader-group g | family m1",
                                 "reader-2 | fake | family m2 | reader-group g"])
        self.assertEqual(s.freeze().exit_code, 0)
        self.assertEqual([(r.family, r.group) for r in s.plan.readers],
                         [("m1", "g"), ("m2", "g")])


GLANCE_CLEARLY = PREFER_GLANCE + " | clearly"
ONE_WAY = "; the verdict holds only when slightly counts as a pick"


def second(lines):
    return [x for x in lines if x.startswith("hypothesis h1 second reading")]


class SecondReadingCase(unittest.TestCase):
    def test_10_82_a_verdict_of_slightly_picks_holds_one_way(self):
        s, result, lines = done(self, fake_reader=[PREFER_GLANCE])
        self.assertIn("hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly "
                      "counts as a pick [not blind: 0 reads left out]", lines)
        self.assertEqual(second(lines), [
            "hypothesis h1 second reading (slightly as TIE): INCONCLUSIVE"])

    def test_10_82_a_verdict_of_clearly_picks_holds_both_ways(self):
        s, result, lines = done(self, fake_reader=[GLANCE_CLEARLY])
        self.assertIn("hypothesis h1 verdict: SUPPORTED [not blind: 0 reads left out]", lines)
        self.assertEqual(second(lines), [
            "hypothesis h1 second reading (slightly as TIE): SUPPORTED"])

    def test_10_82_slightly_is_a_tie_before_pairing(self):
        rules = items(PREFER_GLANCE, reads=range(1, 12), strength="clearly")
        rules += items(PREFER_GLANCE, reads=[12])
        s, result, lines = done(self, fake_reader=rules)
        self.assertIn("hypothesis h1 pair counts: valid=6 base=0 skills-top=6 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly "
                      "counts as a pick [not blind: 0 reads left out]", lines)
        # Reads 11 and 12 are a pick and a TIE on the second reading: 5 of 6.
        self.assertEqual(second(lines), [
            "hypothesis h1 second reading (slightly as TIE): INCONCLUSIVE"])

    def test_the_family_rule_does_not_act_on_the_second_reading(self):
        s, result, lines = done(self, versions=versions("model m1"), hypotheses=[THREE],
                                fake_reader=items(PREFER_GLANCE, reads=[1, 2, 3, 4, 5, 6],
                                                  strength="clearly"))
        self.assertEqual(reasons(lines), ["hypothesis h1 reason: the other family did not agree"])
        # An INCONCLUSIVE verdict carries no one-way sentence, whatever the second reading.
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertEqual(second(lines), [
            "hypothesis h1 second reading (slightly as TIE): SUPPORTED"])

    def test_the_read_floor_does_not_act_on_the_second_reading(self):
        s, result, lines = done(self, fake_reader=[GLANCE_CLEARLY], min_valid_reads="12")
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertEqual(second(lines), [
            "hypothesis h1 second reading (slightly as TIE): SUPPORTED"])

    def test_position_does_not_act_on_the_second_reading(self):
        # Position INCONCLUSIVE on c1 needs every non-TIE read in one slot, which leaves no
        # paired pick on either reading, so both readings agree here.
        s, result, lines = done(self, fake_reader=["prefer slot A | clearly"],
                                hypotheses=["REFUTED if base preferred in 0 or more; "
                                            "otherwise INCONCLUSIVE"])
        self.assertIn("hypothesis h1 reason: position is INCONCLUSIVE on c1", lines)
        self.assertEqual(second(lines), [
            "hypothesis h1 second reading (slightly as TIE): REFUTED"])

    def test_the_lift_does_not_act_on_the_second_reading(self):
        rule = "SUPPORTED if skills-top preferred in 5 of 6; otherwise INCONCLUSIVE"
        s, result, lines = done(self, hypotheses=[rule], min_valid_reads="5",
                                fake_reader=[GLANCE_CLEARLY, "omit PREFER | read 1"])
        self.assertIn("hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly "
                      "counts as a pick [not blind: 0 reads left out]", lines)
        self.assertEqual(second(lines), [
            "hypothesis h1 second reading (slightly as TIE): INCONCLUSIVE"])

    def test_the_gates_act_on_the_second_reading(self):
        s, result, lines = done(self, fake_reader=[GLANCE_CLEARLY, "aa | prefer slot A"])
        self.assertIn("hypothesis h1 reason: the A/A gate tripped", lines)
        self.assertEqual(second(lines), [
            "hypothesis h1 second reading (slightly as TIE): INCONCLUSIVE"])

    def test_the_second_reading_follows_the_reasons(self):
        s, result, lines = done(self, fake_reader=[PREFER_GLANCE], min_valid_reads="12")
        at = lines.index("hypothesis h1 reason: below the read floor (6 valid pairs, floor 12)")
        self.assertEqual(lines[at + 1],
                         "hypothesis h1 second reading (slightly as TIE): INCONCLUSIVE")
        self.assertEqual(lines[at + 2], "hypothesis h1 family m1: skills-top 3 of 3 paired picks")

    def test_a_refuted_verdict_of_slightly_picks_holds_one_way(self):
        s, result, lines = done(self, fake_reader=["prefer without \"At a glance\""])
        self.assertIn("hypothesis h1 verdict: REFUTED" + ONE_WAY
                      + " [not blind: 0 reads left out]", lines)


def earlier_plan_text(text):
    """A plan's text as the previous release wrote it: no family, no drafted-by."""
    for gone in (" | drafted-by user", " | family m1", " | family m2"):
        text = text.replace(gone, "")
    return text


def write_earlier_freeze(s):
    """A freeze file in the previous release's format, for the plan as it is now."""
    labels = ["plan.txt", "posting.txt", "base.txt", "skills-top.txt", "skills-top-short.txt"]
    lines = ["%s  %s\n" % (sha256_of(s.path(label)), label) for label in labels]
    lines.append("%s  %s\n" % (ab.prompt_sha256(), ab.PROMPT_LABEL))
    s.write("plan.txt.freeze", "".join(lines))


class EarlierRevisionCase(unittest.TestCase):
    def test_10_94_run_refuses_a_plan_frozen_by_the_previous_release(self):
        s = setup(self, fake_reader=[PREFER_GLANCE])
        s.write("plan.txt", earlier_plan_text(s.read("plan.txt")))
        self.assertNotIn("family", s.read("plan.txt"))
        write_earlier_freeze(s)
        result = s.run()
        self.assertEqual((result.exit_code, result.ran), (2, False))
        self.assertEqual(result.error.splitlines(), [EARLIER])
        self.assertFalse(s.exists(ab.READS_DIR))
        self.assertFalse(s.exists(ab.KEY_FILE))
        self.assertEqual(s.result_names(), [])

    def test_10_94_score_refuses_a_folder_run_by_the_previous_release(self):
        s = setup(self, fake_reader=[PREFER_GLANCE])
        self.assertEqual(s.frozen_run().exit_code, 0)
        s.write("plan.txt", earlier_plan_text(s.read("plan.txt")))
        write_earlier_freeze(s)
        result = s.score()
        self.assertEqual((result.exit_code, result.ran), (2, False))
        self.assertEqual(result.error.splitlines(), [EARLIER])
        self.assertEqual(s.result_names(), ["result-1.txt"])

    def test_10_57_a_plan_frozen_before_revision_4_is_no_longer_run(self):
        self.assertEqual(ab.prompt_sha256(),
                         "567b9bc16d86abfe4af935a844e28a1b6d2d257aa4f93b6ab3de8e97ce1fdd14")
        s = setup(self)
        s.write("plan.txt", earlier_plan_text(s.read("plan.txt")))
        write_earlier_freeze(s)
        self.assertEqual(s.run().error, EARLIER)
        self.assertEqual(s.score().error, EARLIER)

    def test_a_plan_edited_since_its_freeze_is_named_as_changed(self):
        s = setup(self)
        s.write("plan.txt", earlier_plan_text(s.read("plan.txt")))
        write_earlier_freeze(s)
        s.edit("plan.txt", lambda text: text + "# edited\n")
        self.assertEqual(s.run().error.splitlines(), ["changed since the freeze: plan.txt"])

    def test_freeze_names_each_missing_field(self):
        s = setup(self)
        s.write("plan.txt", earlier_plan_text(s.read("plan.txt")))
        result = s.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertNotIn("frozen under an earlier revision", result.error)
        self.assertIn("a reader needs a family (revision 4): reader-1", result.error)
        self.assertIn("a version needs drafted-by (revision 4): base", result.error)


if __name__ == "__main__":
    unittest.main()
