"""Tests for revision 4 of the Reader A/B spec that relate one run folder to another
(docs/specs/reader-ab.md, tests 10.86 to 10.88): amendments of the read count, extensions of the
sample size, and A/A reads pooled across runs. All data here is invented.

Each Setup is a run folder in a fresh temporary folder, and the temporary folders are siblings,
so one plan names another run's freeze file by a path such as ../tmpabc/plan.txt.freeze.
"""

import hashlib
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab  # noqa: E402
from tests.test_ab import (  # noqa: E402
    EIGHT, PREFER_GLANCE, SIX, TOO_LONG, WITHOUT_GLANCE, WRITE_TOO_LONG, items)
from tests.test_ab_rev4 import READERS, setup  # noqa: E402

SIX_OF_SIX = "SUPPORTED if skills-top preferred in 6 of 6; otherwise INCONCLUSIVE"
TWELVE = ("SUPPORTED if skills-top preferred in 12 of 12; REFUTED if base preferred in 8 or "
          "more; otherwise INCONCLUSIVE")
AMEND = "an amendment may restate a rule's counts at the same share, and change nothing else: "
EXTEND = ("an extension may change only reads-per-reader and the number of readers of each "
          "model: ")
READER_3 = "reader-3 | fake | family m2"
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "ab")


def rel(s, name):
    return os.path.join("..", os.path.basename(s.folder), name)


def tree(folder):
    digest = hashlib.sha256()
    for where, dirs, names in os.walk(folder):
        dirs.sort()
        for name in sorted(names):
            path = os.path.join(where, name)
            digest.update(os.path.relpath(path, folder).encode("utf-8") + b"\0")
            with open(path, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()


def sha(s, name):
    with open(s.path(name), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class RunsBase(unittest.TestCase):
    def setUp(self):
        # An extension looks beside its run folder for another extension of the same first run,
        # so these run folders live in a folder of their own, not among every temporary folder.
        parent = tempfile.mkdtemp()
        previous = tempfile.tempdir
        tempfile.tempdir = parent
        self.addCleanup(shutil.rmtree, parent, True)
        self.addCleanup(setattr, tempfile, "tempdir", previous)

    def freeze_ok(self, s):
        result = s.freeze()
        self.assertEqual(result.exit_code, 0, result.error)
        return result

    def refused(self, s):
        result = s.freeze()
        self.assertEqual(result.exit_code, 2, result.error)
        self.assertFalse(s.exists("plan.txt.freeze"))
        return result.error.splitlines()

    def first_run(self, exit_code=0, **overrides):
        first = setup(self, **overrides)
        result = first.frozen_run()
        self.assertEqual(result.exit_code, exit_code, result.error)
        return first

    def frozen_first(self, **overrides):
        first = setup(self, **overrides)
        self.freeze_ok(first)
        return first


class AmendmentCase(RunsBase):
    def test_10_86_a_restated_rule_at_the_same_share_freezes(self):
        first = self.frozen_first(hypotheses=[SIX])
        second = setup(self, hypotheses=[TWELVE], reads_per_reader="12",
                       amends=rel(first, "plan.txt.freeze"))
        self.freeze_ok(second)
        self.assertIn("%s  %s" % (sha(first, "plan.txt.freeze"), rel(first, "plan.txt.freeze")),
                      second.read("plan.txt.freeze").splitlines())

    def test_10_86_the_rule_kept_as_written_is_refused_naming_the_rule(self):
        first = self.frozen_first(hypotheses=[SIX])
        second = setup(self, hypotheses=[SIX], reads_per_reader="12",
                       amends=rel(first, "plan.txt.freeze"))
        self.assertEqual(self.refused(second), [AMEND + "h1"])

    def test_10_86_a_share_with_no_whole_number_is_refused_naming_the_rule(self):
        # Two thirds of 8 pairs is not a whole number, so 4 or more of 6 has no restatement.
        first = self.frozen_first(hypotheses=[SIX])
        rule = ("SUPPORTED if skills-top preferred in 8 of 8; REFUTED if base preferred in 5 "
                "or more; otherwise INCONCLUSIVE")
        second = setup(self, hypotheses=[rule], reads_per_reader="8",
                       amends=rel(first, "plan.txt.freeze"))
        self.assertEqual(self.refused(second), [AMEND + "h1"])

    def test_10_86_a_threshold_setting_is_refused_naming_it(self):
        first = self.frozen_first(hypotheses=[SIX])
        for change, setting in ((dict(noise_threshold="1/3"), "noise-threshold"),
                                (dict(alpha="0.01"), "alpha"),
                                (dict(min_valid_reads="3"), "min-valid-reads")):
            with self.subTest(setting=setting):
                second = setup(self, hypotheses=[TWELVE], reads_per_reader="12",
                               amends=rel(first, "plan.txt.freeze"), **change)
                self.assertEqual(self.refused(second), [
                    "an amendment may not change %s from the plan it amends" % setting])

    def test_10_86_the_sensitivity_threshold_is_refused_naming_it(self):
        versions = ["base | base.txt | drafted-by user", "skills-top | skills-top.txt | "
                    "drafted-by user", "base-weak | base-weak.txt | drafted-by user"]
        pair = dict(versions=versions, sensitivity="base vs base-weak",
                    sensitivity_scope=["^hours to "])
        first = setup(self, hypotheses=[SIX], **pair)
        shutil.copyfile(os.path.join(FIXTURES, "base-weak.txt"), first.path("base-weak.txt"))
        self.freeze_ok(first)
        second = setup(self, hypotheses=[TWELVE], reads_per_reader="12",
                       sensitivity_threshold="3/4", amends=rel(first, "plan.txt.freeze"),
                       **pair)
        shutil.copyfile(os.path.join(FIXTURES, "base-weak.txt"), second.path("base-weak.txt"))
        self.assertEqual(self.refused(second), [
            "an amendment may not change sensitivity-threshold from the plan it amends"])

    def test_a_threshold_written_as_its_default_is_no_change(self):
        first = self.frozen_first(hypotheses=[SIX], noise_threshold=None)
        second = setup(self, hypotheses=[TWELVE], reads_per_reader="12", noise_threshold="1/2",
                       amends=rel(first, "plan.txt.freeze"))
        self.freeze_ok(second)

    def test_an_amendment_may_not_add_or_drop_a_hypothesis_or_change_a_clause(self):
        first = self.frozen_first(hypotheses=[SIX])
        other = "SUPPORTED if base preferred in 12 of 12; otherwise INCONCLUSIVE"
        for rules, named in (([TWELVE, TWELVE], "h2"), ([other], "h1")):
            with self.subTest(rules=rules):
                second = setup(self, hypotheses=rules, reads_per_reader="12",
                               amends=rel(first, "plan.txt.freeze"))
                self.assertEqual(self.refused(second), [AMEND + named])

    def test_a_mechanism_count_keeps_its_share_of_the_planned_reads(self):
        first = self.frozen_first(hypotheses=[SIX], mechanisms=[TOO_LONG])
        good = setup(self, hypotheses=[TWELVE], reads_per_reader="12",
                     mechanisms=["too long | default | supported at 6 or more"],
                     amends=rel(first, "plan.txt.freeze"))
        self.freeze_ok(good)
        bad = setup(self, hypotheses=[TWELVE], reads_per_reader="12", mechanisms=[TOO_LONG],
                    amends=rel(first, "plan.txt.freeze"))
        self.assertEqual(self.refused(bad), [AMEND + "too long"])

    def test_the_amended_plan_must_be_there_unchanged_and_readable(self):
        first = self.frozen_first(hypotheses=[SIX])
        second = setup(self, hypotheses=[TWELVE], reads_per_reader="12",
                       amends=rel(first, "plan.txt.freeze"))
        os.remove(first.path("plan.txt"))
        self.assertEqual(self.refused(second), [
            "the amended plan is missing: %s" % rel(first, "plan.txt")])
        first.write("plan.txt", "# edited\n")
        self.assertEqual(self.refused(second), [
            "changed since the freeze: %s" % rel(first, "plan.txt")])


class ExtensionCase(RunsBase):
    def extension(self, first, readers=None, **overrides):
        overrides.setdefault("hypotheses", [SIX_OF_SIX])
        overrides.setdefault("fake_reader", [PREFER_GLANCE])
        return setup(self, readers=readers or list(READERS), extends=rel(first, "plan.txt.freeze"),
                     **overrides)

    def first(self, **overrides):
        overrides.setdefault("hypotheses", [SIX_OF_SIX])
        overrides.setdefault("fake_reader", [PREFER_GLANCE])
        return self.first_run(**overrides)

    def test_10_87_reads_per_reader_changed_pools_the_first_runs_pairs(self):
        first = self.first()
        before = tree(first.folder)
        second = self.extension(first, reads_per_reader="4")
        self.freeze_ok(second)
        self.assertIn("%s  %s" % (sha(first, "plan.txt.freeze"), rel(first, "plan.txt.freeze")),
                      second.read("plan.txt.freeze").splitlines())
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        for lines in (result.text.splitlines(), second.result_lines()):
            self.assertIn("extends: %s; the sample size changed after a result was seen"
                          % sha(first, "plan.txt.freeze"), lines)
            self.assertIn("hypothesis h1 extension: first run SUPPORTED, pooled SUPPORTED",
                          lines)
            self.assertIn("hypothesis h1 rule: SUPPORTED if skills-top preferred in 6 of 6",
                          lines)
            self.assertIn("hypothesis h1 rule at the pooled pairs: SUPPORTED if skills-top "
                          "preferred in 10 of 10", lines)
            self.assertIn("hypothesis h1 evidence: skills-top 10 of 10 non-TIE paired picks, 0 "
                          "TIE; p = 0.0020 two-sided (reads may be correlated; may be too "
                          "small); 95% interval 0.722 to 1.000", lines)
            self.assertIn("extension pool c1: first run 12 valid reads of 12 planned, this run "
                          "8 of 8", lines)
            self.assertIn("extension pool aa: first run 12 valid reads of 12 planned, this run "
                          "8 of 8", lines)
        self.assertEqual(second.score().exit_code, 0)
        self.assertEqual(tree(first.folder), before)

    def test_the_extends_line_follows_the_prompt_hash(self):
        first = self.first()
        second = self.extension(first)
        self.freeze_ok(second)
        lines = second.run().text.splitlines()
        at = [i for i, x in enumerate(lines) if x.startswith("prompt sha256: ")][0]
        self.assertTrue(lines[at + 1].startswith("extends: "), lines[at + 1])
        self.assertTrue(lines[at + 2].startswith("A/A arm: "), lines[at + 2])

    def test_10_87_an_added_reader_of_a_model_that_already_read_pools_too(self):
        first = self.first()
        second = self.extension(first, readers=list(READERS) + [READER_3])
        self.freeze_ok(second)
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        lines = result.text.splitlines()
        self.assertIn("hypothesis h1 extension: first run SUPPORTED, pooled SUPPORTED", lines)
        self.assertIn("hypothesis h1 rule at the pooled pairs: SUPPORTED if skills-top "
                      "preferred in 15 of 15", lines)
        evidence = [x for x in lines if x.startswith("hypothesis h1 evidence: ")]
        self.assertTrue(evidence[0].startswith(
            "hypothesis h1 evidence: skills-top 15 of 15 non-TIE paired picks, 0 TIE; "),
            evidence)

    def test_the_extension_line_gives_the_first_runs_own_verdict(self):
        rules = items(PREFER_GLANCE, reads=list(range(1, 13)))
        first = self.first(fake_reader=rules)
        second = self.extension(first, readers=list(READERS) + [READER_3], fake_reader=rules)
        self.freeze_ok(second)
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        lines = result.text.splitlines()
        self.assertIn("hypothesis h1 rule at the pooled pairs: SUPPORTED if skills-top "
                      "preferred in 15 of 15", lines)
        self.assertIn("hypothesis h1 pair counts: valid=15 base=0 skills-top=12 tie=3", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)
        self.assertIn("hypothesis h1 extension: first run SUPPORTED, pooled INCONCLUSIVE", lines)

    def test_10_87_the_example_rule_needs_a_whole_number_at_the_pooled_pairs(self):
        first = self.first(hypotheses=[SIX])
        refused = self.extension(first, hypotheses=[SIX], reads_per_reader="4")
        self.assertEqual(self.refused(refused), [
            "an extension's pooled pairs give no whole number for h1"])
        second = self.extension(first, hypotheses=[SIX], reads_per_reader="6")
        self.freeze_ok(second)
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        self.assertIn("hypothesis h1 rule at the pooled pairs: SUPPORTED if skills-top "
                      "preferred in 12 of 12; REFUTED if base preferred in 8 or more",
                      result.text.splitlines())

    def test_10_87_a_mechanism_count_follows_the_pooled_reads(self):
        first = self.first(hypotheses=[SIX], mechanisms=[TOO_LONG],
                           fake_reader=items(WRITE_TOO_LONG, reads=EIGHT))
        second = self.extension(first, hypotheses=[SIX], mechanisms=[TOO_LONG],
                                reads_per_reader="6", fake_reader=items(WRITE_TOO_LONG,
                                                                        reads=EIGHT))
        self.freeze_ok(second)
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        self.assertIn("mechanism too long in c1 count: 16 of 24 valid reads",
                      result.text.splitlines())
        self.assertIn("mechanism too long in c1 verdict: SUPPORTED (SUPPORTED at 6 or more) "
                      "(what readers wrote, not a cause) [not blind: 0 reads left out]",
                      result.text.splitlines())

    def test_renaming_every_reader_cannot_hide_the_first_runs_other_family(self):
        # First run, 12 reads per reader: the m1 reader reads 1 to 12 and prefers skills-top;
        # the m2 reader reads 13 to 24 and prefers base. The extension renames every reader and
        # asks for four of 6 reads each, ordered m2, m1, m1, m2, under the same fake-reader
        # rules: its first m2 reader (reads 1 to 6) prefers skills-top and its second (reads 19
        # to 24) prefers base, so the extension's own m2 pairs split 3 of 6, which meets a
        # one-half share. Pooled with the first run's m2 pairs (none for skills-top) the share is
        # 3 of 12, short of the 6 that one half of 12 asks for. The pooled count of skills-top,
        # 12 of 24, meets the rule. So the family check, given the extension's readers alone,
        # would find agreement and leave SUPPORTED; only given the first run's readers too does
        # it say that the other family did not agree. Were the first run's readers dropped, the
        # family lines would also count the extension's pairs alone.
        # docs/specs/reader-ab.md section 3.2: an extension "may change the sample size only",
        # so both plans carry the same fake-reader rules, and the freeze must accept them.
        half = "SUPPORTED if skills-top preferred in 6 or more; otherwise INCONCLUSIVE"
        arm = "base vs skills-top"
        versions = ["base | base.txt | drafted-by user",
                    "skills-top | skills-top.txt | drafted-by model m1",
                    "skills-top-short | skills-top-short.txt | drafted-by user"]
        rules = (items(PREFER_GLANCE, reads=list(range(1, 13)), arm=arm)
                 + items(WITHOUT_GLANCE, reads=list(range(13, 25)), arm=arm))
        first = self.first(hypotheses=[half], versions=versions, fake_reader=rules,
                           reads_per_reader="12")
        second = self.extension(first, hypotheses=[half], versions=versions,
                                fake_reader=rules, reads_per_reader="6",
                                readers=["reader-a | fake | family m2",
                                         "reader-b | fake | family m1",
                                         "reader-c | fake | family m1",
                                         "reader-d | fake | family m2"])
        frozen = second.freeze()
        self.assertEqual(frozen.exit_code, 0, frozen.error)
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        lines = result.text.splitlines()
        self.assertIn("hypothesis h1 rule at the pooled pairs: SUPPORTED if skills-top "
                      "preferred in 12 or more", lines)
        self.assertIn("hypothesis h1 pair counts: valid=24 base=12 skills-top=12 tie=0", lines)
        self.assertIn("hypothesis h1 family m1: skills-top 9 of 12 paired picks", lines)
        self.assertIn("hypothesis h1 family m2: skills-top 3 of 12 paired picks", lines)
        self.assertIn("hypothesis h1 reason: the other family did not agree", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]", lines)

    def slightly_extension(self, first_reads, extension_reads):
        # Both plans carry the same fake-reader rules, so the two runs differ only in how many
        # reads each reader makes. A/A reads 1 to 4 are "slightly" picks in both runs.
        rules = [PREFER_GLANCE] + items("prefer slot A", reads=[1, 2, 3, 4], arm="aa",
                                        strength="slightly")
        pairs = int(first_reads)
        rule = ("SUPPORTED if skills-top preferred in %d of %d; otherwise INCONCLUSIVE"
                % (pairs // 2, pairs))
        first = self.first(hypotheses=[rule], reads_per_reader=first_reads, fake_reader=rules)
        second = self.extension(first, hypotheses=[rule], reads_per_reader=extension_reads,
                                fake_reader=rules)
        frozen = second.freeze()
        self.assertEqual(frozen.exit_code, 0, frozen.error)
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        return result.text.splitlines()

    def test_the_slightly_rate_does_not_count_the_first_runs_a_a_reads(self):
        # The first run made 4 A/A reads and the extension 24; reads 1 to 4 are slightly picks
        # in each, so the extension's own rate is 4 of 24. The gate still counts 28 reads.
        lines = self.slightly_extension("2", "12")
        self.assertIn("A/A slightly rate: 4 of 24 valid A/A reads are slightly", lines)
        gate = [x for x in lines if x.startswith("A/A gate: ")]
        self.assertEqual(len(gate), 1, gate)
        self.assertIn("of 28 valid A/A reads", gate[0])

    def test_the_slightly_rate_counts_all_of_the_extensions_own_a_a_reads(self):
        # The first run made 24 A/A reads and the extension 4: the extension's own rate is
        # 4 of 4, and the gate counts 28 reads.
        lines = self.slightly_extension("12", "2")
        self.assertIn("A/A slightly rate: 4 of 4 valid A/A reads are slightly", lines)
        gate = [x for x in lines if x.startswith("A/A gate: ")]
        self.assertEqual(len(gate), 1, gate)
        self.assertIn("of 28 valid A/A reads", gate[0])

    def test_10_87_each_change_of_anything_but_the_sample_size_is_refused(self):
        first = self.first()
        cases = [("alpha", dict(alpha="0.01"), [EXTEND + "alpha"]),
                 ("noise", dict(noise_threshold="1/3"), [EXTEND + "noise-threshold"]),
                 ("rule", dict(hypotheses=[SIX]), [EXTEND + "hypotheses"]),
                 ("family m3", dict(readers=list(READERS) + ["reader-3 | fake | family m3"]),
                  [EXTEND + "readers"]),
                 ("not-blind", dict(readers=list(READERS)
                                    + ["reader-3 | fake | family m2 | not-blind"]),
                  [EXTEND + "readers"]),
                 ("command", dict(readers=list(READERS)
                                  + ["reader-3 | /usr/bin/other-reader | family m2"]),
                  [EXTEND + "readers"])]
        for name, change, expected in cases:
            with self.subTest(change=name):
                second = self.extension(first, **change)
                self.assertEqual(self.refused(second), expected)

    def test_10_87_a_changed_version_or_posting_is_refused_naming_the_file(self):
        first = self.first()
        for name in ("skills-top.txt", "posting.txt"):
            with self.subTest(name=name):
                second = self.extension(first)
                second.edit(name, lambda text: text + "\n")
                self.assertEqual(self.refused(second), [
                    "changed since the first freeze: %s" % name])

    def test_10_87_a_second_extension_of_the_same_first_run_is_refused(self):
        first = self.first()
        one = self.extension(first)
        self.freeze_ok(one)
        two = self.extension(first, reads_per_reader="4")
        self.assertEqual(self.refused(two), [
            "the first run already has an extension: %s" % os.path.basename(one.folder)])

    def test_10_87_extends_with_amends_or_replicate_of_is_refused(self):
        first = self.first()
        for key in ("amends", "replicate_of"):
            with self.subTest(key=key):
                second = self.extension(first, **{key: rel(first, "plan.txt.freeze")})
                result = second.freeze()
                self.assertEqual(result.exit_code, 2)
                self.assertIn("plan line %d: a plan may not carry extends with amends, "
                              "replicate-of or aa-pool" % second.line_of("extends"),
                              result.error.splitlines())

    def test_extends_names_a_freeze_file_of_a_first_run(self):
        first = self.first()
        second = self.extension(first)
        second.change(extends=rel(first, "plan.txt"))
        result = second.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "plan line %d: extends must name a .freeze file" % second.line_of("extends")])
        middle = self.extension(first)
        self.freeze_ok(middle)
        third = self.extension(middle, readers=list(READERS))
        self.assertEqual(self.refused(third), [
            "extends must name a first run, not an amendment, a replicate or an extension: %s"
            % rel(middle, "plan.txt")])

    def test_an_extension_waits_for_its_first_run(self):
        first = self.frozen_first(hypotheses=[SIX_OF_SIX], fake_reader=[PREFER_GLANCE])
        second = self.extension(first)
        self.freeze_ok(second)
        result = second.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "the first run has not been run yet: ../%s" % os.path.basename(first.folder)])


class PoolCase(RunsBase):
    def pooled(self, first, **overrides):
        overrides.setdefault("hypotheses", [SIX_OF_SIX])
        overrides.setdefault("fake_reader", [PREFER_GLANCE])
        return setup(self, aa_pool=[rel(first, "plan.txt.freeze")], **overrides)

    def first(self, **overrides):
        overrides.setdefault("hypotheses", [SIX_OF_SIX])
        overrides.setdefault("fake_reader", [PREFER_GLANCE])
        return self.first_run(**overrides)

    def test_10_88_the_gate_counts_the_a_a_reads_of_both_runs(self):
        first = self.first()
        before = tree(first.folder)
        second = self.pooled(first)
        self.freeze_ok(second)
        self.assertIn("%s  %s" % (sha(first, "plan.txt.freeze"), rel(first, "plan.txt.freeze")),
                      second.read("plan.txt.freeze").splitlines())
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        lines = result.text.splitlines()
        at = lines.index("A/A pool: 1 earlier runs, 24 valid A/A reads in the gate")
        self.assertEqual(lines[at + 1], "A/A gate: passed (0 of 24 valid A/A reads non-TIE, at "
                                        "any strength; threshold 1/2)")
        self.assertIn("A/A slightly rate: 0 of 12 valid A/A reads are slightly", lines)
        self.assertEqual(tree(first.folder), before)

    def test_10_88_pooled_non_tie_reads_trip_the_gate(self):
        first = self.first(fake_reader=[PREFER_GLANCE, "aa | prefer slot A | clearly"])
        second = self.pooled(first)
        self.freeze_ok(second)
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        self.assertIn("A/A gate: tripped (12 of 24 valid A/A reads non-TIE, at any strength, "
                      "50%; threshold 1/2)", result.text.splitlines())
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE [not blind: 0 reads left out]",
                      result.text.splitlines())

    def test_10_88_a_pooled_run_that_shares_less_than_all_four_is_refused(self):
        cases = [("the prompt", dict(document="essay")),
                 ("the reader commands", dict(readers=["reader-1 | /usr/bin/other-reader | family m1",
                                                       READERS[1]])),
                 ("the A/A version file", dict(aa_version="base"))]
        for what, change in cases:
            with self.subTest(what=what):
                first = self.frozen_first(hypotheses=[SIX_OF_SIX], **change)
                second = self.pooled(first)
                self.assertEqual(self.refused(second), [
                    "the pooled run differs in %s: %s" % (what, rel(first, "plan.txt.freeze"))])
        first = setup(self, hypotheses=[SIX_OF_SIX])
        first.edit("posting.txt", lambda text: text + "\nmore\n")
        self.freeze_ok(first)
        second = self.pooled(first)
        self.assertEqual(self.refused(second), [
            "the pooled run differs in the posting: %s" % rel(first, "plan.txt.freeze")])

    def test_10_88_a_freeze_file_that_does_not_exist_yet_is_refused(self):
        first = setup(self)
        second = setup(self, aa_pool=[rel(first, "plan.txt.freeze")])
        self.assertEqual(self.refused(second), [
            "missing input: %s" % rel(first, "plan.txt.freeze")])

    def test_a_pool_item_names_a_freeze_file_once(self):
        first = self.first()
        item = rel(first, "plan.txt.freeze")
        second = setup(self, aa_pool=[item, item])
        result = second.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "plan line %d: aa-pool names %s twice" % (second.line_of(item) + 1, item)])

    def test_a_pooled_run_that_has_not_run_is_waited_for(self):
        first = self.frozen_first(hypotheses=[SIX_OF_SIX])
        second = self.pooled(first)
        self.freeze_ok(second)
        result = second.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "the pooled run has not been run yet: ../%s" % os.path.basename(first.folder)])

    def test_the_gate_is_not_evaluated_when_a_pooled_runs_a_a_arm_is_incomplete(self):
        first = self.first(exit_code=1,
                           fake_reader=[PREFER_GLANCE, "aa | omit PREFER | read 1"])
        second = self.pooled(first)
        self.freeze_ok(second)
        result = second.run()
        self.assertEqual(result.exit_code, 0, result.error)
        lines = result.text.splitlines()
        self.assertIn("A/A pool: 1 earlier runs, 23 valid A/A reads in the gate", lines)
        self.assertIn("A/A gate: not evaluated (23 valid reads of 24 planned)", lines)

    def test_the_mechanism_floor_never_uses_the_pooled_reads(self):
        first = self.first(mechanisms=[TOO_LONG], fake_reader=[
            PREFER_GLANCE, 'aa | write "too long" in DOUBTS'])
        second = self.pooled(first, mechanisms=[TOO_LONG], fake_reader=items(
            WRITE_TOO_LONG, reads=EIGHT))
        self.freeze_ok(second)
        result = second.run()
        self.assertIn("mechanism too long in c1 A/A floor: 0 of 12 valid reads",
                      result.text.splitlines())


if __name__ == "__main__":
    unittest.main()
